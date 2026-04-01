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

## 7. 운영 인프라 — 데이터 영속성

### RDB 영속성 구성

Redis는 기본적으로 인메모리라 프로세스가 죽으면 데이터가 사라진다. 거래 주문 데이터 유실을 막기 위해 RDB 스냅샷 영속성을 구성했다.

| 방식 | 동작 | 특징 |
|---|---|---|
| **RDB 스냅샷** | 특정 시점의 전체 데이터를 바이너리 파일로 저장 | 파일 크기 작음, 복구 빠름. 스냅샷 사이 데이터는 유실 가능 |

> **참고**: AOF + Cluster 구성은 검토했으나 실제 코드에는 단일 인스턴스 + RDB만 적용됨. AOF(Append Only File)는 모든 쓰기 명령을 로그로 기록해 데이터 유실을 최소화할 수 있고, Redis Cluster는 데이터를 여러 노드에 분산해 고가용성을 확보하는 방식이다.

---

## 한계점

구현하고 나서 돌아보면 아쉬운 지점이 몇 가지 있다.

### 직렬화 게이트 — 근본적인 처리량 상한

설계에서 가장 큰 병목이다. `while(true)` 폴링 루프가 카테고리당 1건씩만 순차 처리하기 때문에, 아무리 Redis가 빨라도 이 게이트를 통과하는 주문 수는 제한된다.

문제는 세 가지다.

첫째, **busy-wait으로 CPU를 계속 소모한다.** `ready === '1'`이 될 때까지 루프를 돌기 때문에 처리할 주문이 없어도 Redis 연결을 계속 긁는다.

둘째, **수평 확장이 불가능하다.** 인스턴스를 2개 띄우면 두 프로세스가 동시에 `GET NEXT_CONTRACT_READY_KEY`에서 `'1'`을 읽을 수 있다. node-redis 단일 연결 특성이 어느 정도 완화해주지만, 설계 전제 자체가 단일 프로세스다.

셋째, **플래그 게이트가 원자적이지 않다.** `GET` → `SET '0'` 사이에 틈이 존재한다. 진짜 분산 환경에서 쓰려면 Redis `SET NX`나 Lua 스크립트로 원자성을 보장해야 한다.

### 단일 Redis 인스턴스 + RDB만

AOF가 없어서 마지막 스냅샷 이후 들어온 주문은 Redis 프로세스가 죽으면 유실된다. Cluster도 없으니 Redis 노드 하나가 죽으면 전체 서비스가 중단된다. 검토까지는 했는데 실제 적용을 못 한 부분이다.

### 게임 서버 API 실패 처리 부재

체결 완료 후 게임 서버에 아이템 지급을 통보하는데, 이 API 호출이 실패했을 때 재시도하거나 롤백하는 메커니즘이 없다. **체결은 됐는데 아이템이 안 들어오는** 상황이 발생할 수 있다. 보상 트랜잭션(Saga 패턴이나 별도 재시도 큐)을 붙였어야 했다.

### 호가창 캐시 일관성

`cache-manager` in-memory 캐시가 만료되기 전까지 이전 집계 결과를 반환한다. 체결이 일어난 직후 사용자가 호가창을 조회하면 실제 잔량과 다른 값을 볼 수 있다.

### RediSearch 쿼리 비용 누적

`@price:[-inf ${buyPrice}]` 범위 검색은 주문이 쌓일수록 결과 셋이 커진다. 부분 체결이 반복되면 잔량 주문이 인덱스에 계속 남기 때문에, 오래 운영할수록 쿼리 비용이 선형으로 증가한다.

---

## TPS 추정

실제로 이 구조가 얼마나 버텨줄 수 있는지 계산해봤다.

### 주문 1건 처리 비용

주문 하나가 체결 엔진을 통과하는 데 드는 주요 비용을 분해하면 대략 이렇다.

| 단계 | 예상 소요 |
|---|---|
| Redis flag GET/SET × 2회 | ~0.2ms |
| RediSearch 범위 쿼리 | ~1–3ms |
| Redis JSON GET/SET × 3–5회 | ~1–2ms |
| Decimal.js 연산 + Node.js 오버헤드 | ~0.5–1ms |
| **합계** | **약 3–6ms / 건** |

### 카테고리별 TPS

직렬화 게이트 구조상 카테고리당 처리량 상한은 `1 / 처리시간`이다.

```
1건 ≈ 5ms → 카테고리당 이론적 최대 ~200 TPS
3개 카테고리(MTK, RESOURCE, RARE) 독립 처리 → 합산 ~500–600 TPS
```

busy-wait 오버헤드와 Redis 네트워크 지연을 감안하면 **평상시 실효 TPS는 카테고리당 50–100 TPS** 수준으로 떨어진다.

### 게임 규모별 판단

| 동시접속 | 상황 | 판단 |
|---|---|---|
| ~1,000명 | 소규모 게임 | 충분 |
| ~10,000명 | 중규모, 이벤트 피크 | 위험 구간 — RESOURCE 카테고리에서 큐 적체 가능 |
| ~50,000명+ | 대규모 | 한계 초과 — 스트림에 주문이 쌓이기 시작하면 체결 지연이 눈에 띔 |

이 구현은 소규모~중규모 게임의 평상시 트래픽엔 충분히 버티지만, 대형 이벤트나 대규모 서비스에 그대로 쓰기엔 구조적 한계가 있다.

---

## 개선 방향

지금 구조에서 가장 먼저 손봐야 할 부분들을 정리해봤다.

**1. 플래그 게이트 → Redis Lua 스크립트 원자 잠금**

`GET` + `SET` 두 번 오가는 게이트 대신, Lua 스크립트로 읽기-쓰기를 원자적으로 처리한다. `SET NX PX` 조합으로 TTL도 붙이면 프로세스가 죽어도 잠금이 영구히 걸리는 상황을 방지할 수 있다.

**2. 게임 서버 API 실패 → 보상 큐 추가**

체결 후 게임 서버 통보가 실패하면 별도 retry 스트림에 이벤트를 적재해서 멱등하게 재처리한다. 최소한 dead letter queue 형태라도 있어야 유실을 추적할 수 있다.

**3. 수평 확장 — 카테고리를 shard key로**

카테고리(MTK, RESOURCE, RARE)가 이미 독립된 호가창을 가지고 있으니, 이 단위로 인스턴스를 분리하면 자연스럽게 수평 확장이 된다. 카테고리가 늘어날 때마다 인스턴스를 추가하는 방식으로 설계할 수 있다.

**4. AOF + Redis replica 최소 구성**

단일 장애점 제거를 위한 최소 조치다. AOF로 쓰기 명령을 로그로 남기고, replica 1개만 붙여도 Redis 노드 장애 시 복구 시간을 크게 줄일 수 있다.

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
