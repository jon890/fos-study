# 게임 아이템 거래소 엔진 구현기

**진행 기간**: 2022.08
**소속**: 더퓨쳐컴퍼니
**저장소**: https://github.com/jon890/fos-trading-engine

---

## 무엇을 만들었나

게임 내 플레이어 간 아이템을 직접 거래할 수 있는 **P2P 거래소 시스템**이다. 주식 거래소처럼 지정가 주문(limit order)을 제출하면 가격 조건이 맞는 상대 주문과 자동으로 체결되는 방식이다.

거래 가능한 아이템은 세 카테고리로 분리된다.

| 카테고리   | 대상                            |
| ---------- | ------------------------------- |
| `MTK`      | 메인 토큰 (게임 내 기축 화폐)   |
| `RESOURCE` | 일반 자원 (철, 돌, 물, 오일)    |
| `RARE`     | 희귀 아이템 (비식별 레어, 골드) |

각 카테고리는 완전히 독립된 호가창(order book)을 가진다.

---

## 핵심 흐름

```
HTTP 주문 접수 (REST)
      │
 Redis Streams (xAdd)          ← 주문을 스트림에 적재
      │
 스트림 소비자 (xReadGroup)    ← 미처리 주문 구독
      │
 직렬화 게이트 (Redis 플래그)  ← 카테고리당 1건씩 순차 처리 보장
      │
 가격-시간 우선 매칭 엔진      ← RediSearch 쿼리 → Decimal 연산 → 체결
      │
 Redis JSON 호가창 갱신        ← 미체결 잔량 저장
      │
 게임 서버 API 통보            ← 체결 결과를 상위 시스템에 전달
      │
 REST 호가창 조회 (캐시 서빙)  ← 집계 결과를 in-memory 캐시에서 응답
```

---

## 1. Redis Streams — 주문을 큐로 받는다

주문이 들어오면 즉시 체결 로직을 실행하지 않는다. 대신 **Redis Streams에 이벤트를 적재**하고, 별도 소비자 루프가 순서대로 처리한다.

```typescript
// 매수 주문 접수 → 스트림에 적재
await redis.xAdd('MTK_TRADING_STREAM', '*', {
  userId: dto.userId,
  price: dto.price,
  amount: dto.amount,
  tradingType: TradingType.BUYING,
  // ...
});
```

소비자 쪽에서는 `xReadGroup`으로 Consumer Group을 구성해 미전달 메시지만 가져온다.

```typescript
const messages = await redis.xReadGroup(GROUP_KEY, CONSUMER_KEY, { id: '>', key: STREAM_KEY });
```

**왜 이 구조인가?**
주문이 동시에 여러 건 들어와도 스트림이 순서를 보장한다. 체결 로직이 느려져도 HTTP 응답에는 영향이 없다. 주문 이력이 스트림에 로그로 남는다(스트림 크기가 120,000건을 초과하면 오래된 10,000건을 `/logs/`에 파일로 덤프하고 `xTrim`으로 정리한다).

---

## 2. 직렬화 게이트 — Redis 플래그로 동시성을 막는다

체결 엔진이 호가창을 읽고 갱신하는 도중 다른 주문이 끼어들면 데이터 정합성이 깨진다. 이를 막기 위해 **카테고리별 Redis 문자열 키**(`NEXT_CONTRACT_READY`)를 단순한 분산 세마포어로 사용한다.

```
NEXT_CONTRACT_READY = "1"  →  처리 가능
NEXT_CONTRACT_READY = "0"  →  처리 중 (다른 주문 대기)
```

```typescript
while (true) {
  const ready = await redis.get(NEXT_CONTRACT_READY_KEY);
  if (ready === '1') {
    const order = await redis.rPop(PENDING_DATA_KEY);
    if (!order) continue;

    await redis.set(NEXT_CONTRACT_READY_KEY, '0'); // 점유
    await processOrder(order); // 체결
    await redis.set(NEXT_CONTRACT_READY_KEY, '1'); // 해제
  }
}
```

소비자 루프가 스트림에서 꺼낸 주문을 `lPush`(PENDING 리스트 앞에 적재)하고, 게이트 루프가 `rPop`(뒤에서 꺼내기)으로 FIFO 순서를 유지한다. node-redis의 단일 연결 특성과 결합해 카테고리당 한 번에 정확히 한 건의 주문만 처리된다.

---

## 3. 가격-시간 우선 매칭 알고리즘

체결 엔진의 핵심이다. 실제 거래소의 **Price-Time Priority** 원칙을 구현했다.

### RediSearch로 상대 주문 조회

매수 주문이 들어오면 "내 희망 가격 이하의 매도 주문"을 RediSearch로 쿼리한다.

```typescript
// 매수자 희망가 이하의 매도 주문 조회 (가격 오름차순)
const sellOffers = await redis.ft.search('MTK_TRADING_INDEX', `@type:{SELLING} @price:[-inf ${buyPrice}]`, {
  SORTBY: { BY: 'price', DIRECTION: 'ASC' },
});
```

매도는 반대로 "내 희망가 이상의 매수 주문"을 조회한다.

### Decimal.js로 정밀 연산

금융 연산에서 부동소수점 오차는 치명적이다. 모든 수량/가격 연산에 `decimal.js`를 사용한다.

```typescript
let remainAmount = new Decimal(buyOrder.amount);

while (sellOffers.length) {
  const sell = sellOffers.pop(); // 가장 저렴한 매도부터

  if (remainAmount.minus(sell.amount).toNumber() >= 0) {
    completes.push(sell); // 완전 체결
    remainAmount = remainAmount.minus(sell.amount);
  } else {
    partial = sell; // 부분 체결
    partialAmount = remainAmount.toNumber();
    remainAmount = new Decimal(0);
  }
  if (remainAmount.toNumber() === 0) break;
}
```

### 가격-시간 우선 정렬

동일 가격의 주문이 여러 건이면 먼저 들어온 주문이 우선이다. Redis Streams의 메시지 ID(타임스탬프 기반)를 정렬 기준으로 사용한다.

```typescript
// 매수: 가격 내림차순, 동가격이면 선착순
// 매도: 가격 오름차순, 동가격이면 선착순
static compare(a: TradingStackDto, b: TradingStackDto): number {
  if (a.price !== b.price) {
    return isBuying ? b.price - a.price : a.price - b.price;
  }
  return a.timestamp - b.timestamp;  // 선착순
}
```

---

## 4. 부분 체결 처리

매수 주문 100개 중 매도 주문이 70개뿐이라면?

- 70개는 즉시 체결
- 나머지 30개는 **미체결 잔량으로 호가창에 등록** (Resting Order)

체결 후 처리는 `Promise.all`로 한 번에 실행한다.

```typescript
await Promise.all([
  // 완전 체결된 매도 주문 삭제
  ...completes.map((s) => redis.json.del(`MTK_SELL_STACK:${s.key}`)),
  // 부분 체결된 매도 주문 잔량 갱신
  partial ? redis.json.set(`MTK_SELL_STACK:${partial.key}`, '$.amount', partialAmount) : Promise.resolve(),
  // 미체결 매수 잔량 호가창에 등록
  remainAmount.toNumber() > 0
    ? redis.json.set(`MTK_BUY_STACK:${buyOrder.key}`, '$', { ...buyOrder, amount: remainAmount.toNumber() })
    : Promise.resolve(),
  // 체결 가격 갱신
  redis.set('MTK_LATEST_PRICE', matchedPrice),
]);
```

---

## 5. 호가창(호가 창구) 실시간 집계

클라이언트가 "현재 1,000원에 매물이 몇 개야?" 를 물으면 **RediSearch의 `FT.AGGREGATE`**로 가격대별 수량을 집계한다.

```typescript
const result = await redis.ft.aggregate('MTK_TRADING_INDEX', '@type:{SELLING}', {
  STEPS: [
    {
      type: AggregateSteps.GROUPBY,
      properties: ['@price'],
      REDUCE: [{ type: AggregateGroupByReducers.SUM, property: 'amount', AS: 'totalAmount' }],
    },
    { type: AggregateSteps.SORTBY, BY: [{ BY: '@price', DIRECTION: 'ASC' }] },
    { type: AggregateSteps.LIMIT, from: 0, size: 10 },
  ],
});
```

결과는 `cache-manager` in-memory 캐시에 저장하고, HTTP 요청은 캐시에서 바로 서빙한다. Redis 집계 쿼리 비용을 반복하지 않으면서 최신 데이터에 가까운 응답을 제공한다.

---

## 6. 주문 취소

취소도 일반 주문과 동일한 스트림 경로를 탄다. `TradingType.CANCEL_BUYING` 이벤트를 스트림에 적재하면 게이트 루프가 순서대로 처리하기 때문에 **취소와 체결이 경합하지 않는다**.

```typescript
// 취소 요청 → 스트림에 적재
await redis.xAdd(STREAM_KEY, '*', {
  tradingType: TradingType.CANCEL_BUYING,
  key: orderKey, // 주문의 스트림 ID
  userId: userId, // 소유자 검증용
});

// 체결 엔진에서 처리 시
const order = await redis.json.get(`MTK_BUY_STACK:${key}`);
if (order.userId !== userId) throw new Error('권한 없음');
await redis.json.del(`MTK_BUY_STACK:${key}`);
await gameApi.restoreBalance(userId, order.amount); // 게임 서버에 잔액 복구 요청
```

---

## 배운 것

### Redis 하나로 큐, 저장소, 검색을 전부 커버할 수 있다

일반적으로 거래 데이터는 RDB에 저장하고, 메시지 큐는 별도 브로커(Kafka, RabbitMQ)를 둔다. 이 구현은 **Redis Streams + Redis JSON + RediSearch** 조합으로 이벤트 큐, 주문 저장, 가격 범위 검색, 집계를 단일 인프라 안에서 모두 처리했다. 도구를 깊이 파면 인프라를 단순하게 유지할 수 있다는 걸 배웠다.

### 동시성은 잠금보다 구조로 해결하는 게 낫다

Lock이나 트랜잭션 대신 **스트림 순서 보장 + Redis 플래그 게이트**라는 구조적 제약으로 경쟁 조건을 원천 차단했다. 잠금 경합(lock contention)이 발생할 여지 자체를 없애는 방향이 더 단순하고 안전했다.

### 거래소 도메인은 생각보다 정교하다

Price-Time Priority, 부분 체결(Partial Fill), 잔량 등록(Resting Order), 취소(Cancel)를 직접 구현하면서 실제 거래소가 어떻게 동작하는지 체감했다. 부동소수점 오차 하나가 금액 불일치로 이어질 수 있어서 Decimal.js 같은 정밀 연산 라이브러리가 왜 필요한지도 직접 확인했다.

### 읽기와 쓰기 경로를 분리하면 각자 독립적으로 최적화할 수 있다

주문 접수(Pub) → 체결(Sub) → 조회(Rest) 세 레이어를 분리하니, 체결이 느려져도 주문 접수 응답에는 영향이 없고 호가창 조회는 캐시에서 바로 나갔다. CQRS 패턴이 실제로 효과 있다는 걸 체감한 경험이다.

---

## 기술 스택

`NestJS v9` `TypeScript` `Redis Streams` `Redis JSON` `RediSearch` `Decimal.js` `node-redis v4`
