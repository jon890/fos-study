# [초안] Event Sourcing과 CQRS — 상태가 아니라 변화를 저장한다는 발상

이 문서의 목표는 두 가지다.
하나, "현재 상태를 덮어쓰는" 일반적인 CRUD 모델과 "일어난 사건을 append-only로 쌓는" Event Sourcing이 어떻게 다른지 감을 잡는 것.
둘, Event Sourcing과 자주 한 묶음으로 거론되는 CQRS가 사실은 독립된 패턴이며, 언제 함께 쓰고 언제 따로 떼어야 하는지 판단 기준을 세우는 것.

결론부터 말하면, **두 패턴 모두 "기본값으로 깔지 말아야 할" 고급 패턴**이다.
대부분의 서비스는 CRUD + 읽기 전용 복제본으로 충분하고, Event Sourcing은 감사(audit) 요구가 강하거나 상태 변화 이력 자체가 비즈니스 가치인 도메인에서만 비용을 정당화한다.

> 관련 문서: [DDD와 도메인 모델링](./ddd-domain-modeling.md), [Outbox / Inbox Pattern 심화](./outbox-inbox-pattern.md), [Spring Batch vs Event-Driven](./spring-batch-vs-event-driven.md), [분산 트랜잭션과 Outbox 패턴](./distributed-transaction-outbox-pattern.md).
> 본 문서는 "상태를 어떻게 저장하고 읽을 것인가"라는 모델링 축에 집중하고, 위 문서들은 이벤트 발행의 정합성 메커니즘과 도메인 모델 설계에 집중한다.

## 1. CRUD가 잃어버리는 것

전통적인 CRUD 모델은 한 행(row)이 곧 현재 상태다.
주문이 `PAID`에서 `SHIPPED`로 바뀌면 `status` 컬럼을 `UPDATE`로 덮어쓴다.
이 순간 "언제, 왜, 누가 이 전이를 일으켰는가"라는 정보는 **사라진다**.

```sql
-- CRUD: 현재 상태만 남고 변화의 history는 증발한다
UPDATE orders SET status = 'SHIPPED', updated_at = NOW() WHERE id = 1001;
```

물론 별도 history 테이블이나 audit 로그를 두면 이력을 보존할 수 있다.
하지만 그건 "본 모델 옆에 이력을 따로 또 관리한다"는 뜻이고, 본 상태와 이력이 어긋날 위험을 항상 안고 간다.
Event Sourcing의 출발점은 이 질문이다 — **이력이 그렇게 중요하다면, 이력을 본 모델 자체로 삼으면 어떨까?**

## 2. Event Sourcing의 핵심 발상

Event Sourcing은 현재 상태를 저장하지 않는다.
대신 도메인에서 일어난 **사건**(event)을 시간순으로 append-only로 쌓고, 현재 상태는 그 사건들을 처음부터 재생(replay)해 계산한다.

```text
주문 1001의 이벤트 스트림 (append-only, 수정/삭제 없음)
  seq 1  OrderPlaced      { items: [...], amount: 38000 }
  seq 2  PaymentCompleted { method: 'CARD', approvedAt: ... }
  seq 3  OrderShipped     { carrier: 'CJ', trackingNo: ... }
  seq 4  OrderDelivered   { deliveredAt: ... }

현재 상태 = fold(이벤트들)  →  status = DELIVERED
```

여기서 중요한 성질 세 가지를 짚고 간다.

- **이벤트는 과거형 사실이다.** `OrderShipped`는 이미 일어난 일이라 수정·삭제 대상이 아니다. 잘못이 있으면 `UPDATE`가 아니라 보정 이벤트(`ShipmentCanceled` 등)를 새로 추가한다.
- **상태는 파생물이다.** 어느 시점의 상태든 그 시점까지의 이벤트를 접어(fold) 다시 만들 수 있다. 과거 임의 시점의 상태를 복원하는 time-travel이 공짜로 따라온다.
- **append-only다.** 쓰기는 항상 스트림 끝에 덧붙이는 연산이라, 본질적으로 동시 수정 충돌 지점이 한 곳(스트림의 tail)으로 모인다.

### 2-1. 재생 비용과 스냅샷

이벤트가 수천, 수만 개로 쌓이면 매번 처음부터 재생하는 비용이 커진다.
그래서 일정 주기로 **스냅샷**(snapshot)을 떠둔다.
"seq 5000 시점의 상태는 이렇다"를 저장해두고, 그 이후 이벤트만 재생하면 된다.

```text
복원 = 가장 최근 스냅샷(seq 5000) + seq 5001 이후 이벤트만 fold
```

스냅샷은 최적화일 뿐 진실의 원천이 아니다.
스냅샷을 통째로 날려도 이벤트 스트림만 살아 있으면 언제든 다시 만들 수 있어야 한다 — 이 불변식이 깨지면 Event Sourcing의 장점이 무너진다.

## 3. CQRS — 읽기 모델과 쓰기 모델의 분리

CQRS는 **Command Query Responsibility Segregation**의 약자다.
이름이 길지만 핵심은 단순하다 — **상태를 바꾸는 경로**(Command)와 **상태를 읽는 경로**(Query)를 서로 다른 모델로 분리한다.

흔한 오해부터 정리하면, **CQRS는 Event Sourcing을 요구하지 않는다.**
둘은 독립 패턴이다. CQRS는 단지 "쓰기용 모델과 읽기용 모델을 같은 스키마로 강제하지 말자"는 주장이다.

- **Command 측**: 비즈니스 규칙과 불변식을 책임진다. 정규화된 도메인 모델, 트랜잭션 일관성이 중요하다.
- **Query 측**: 화면이 필요로 하는 모양 그대로 비정규화된 읽기 모델(read model / projection)을 둔다. 조인 없이 한 번에 읽히도록 미리 펼쳐둔다.

```text
              Command (쓰기)                    Query (읽기)
  요청 ──▶ 도메인 모델 ──▶ 이벤트/변경 ──▶ projection ──▶ 조회 전용 뷰
            (불변식 검증)        │                          (비정규화, 조인 없음)
                                └── 비동기 반영 가능
```

### 3-1. Event Sourcing과의 자연스러운 결합

CQRS가 Event Sourcing과 자주 붙어 다니는 이유는, ES에서 이벤트 스트림이 **읽기에 매우 불편하기** 때문이다.
"배송 중인 주문 목록을 보여줘" 같은 질의를 이벤트를 매번 재생해서 답할 수는 없다.

그래서 이벤트를 구독해 **읽기 전용 projection**을 미리 만들어 둔다.
`OrderShipped` 이벤트가 나올 때마다 `shipping_orders` 읽기 테이블에 행을 넣고, `OrderDelivered`가 나오면 빼는 식이다.
쓰기 모델(이벤트 스트림)과 읽기 모델(projection)이 자연히 갈라지므로, ES를 쓰면 CQRS는 거의 필연적으로 따라온다.

반대 방향은 성립하지 않는다 — CQRS만 쓰고 쓰기 측은 평범한 RDB `UPDATE`로 처리해도 전혀 문제없다.

## 4. 자주 빠지는 함정

### 4-1. 결과적 일관성을 일관성 버그로 착각

projection이 비동기로 갱신되면, 쓰기 직후 읽으면 옛 데이터가 보일 수 있다.
사용자가 주문을 넣자마자 목록을 새로고침했는데 안 보이는 상황이다.
이건 버그가 아니라 **결과적 일관성**(eventual consistency)의 정상 동작이다.

설계 단계에서 "이 화면은 읽기 지연을 몇 초까지 허용하는가"를 명시해야 한다.
허용 못 하는 화면(예: 결제 직후 결제 결과)이라면 그 부분만 쓰기 모델에서 직접 동기로 읽거나, projection 갱신을 동기 트랜잭션 안에 묶는 절충을 둔다.

### 4-2. 이벤트 스키마 진화를 미루기

이벤트는 영원히 남는다.
2년 전 `OrderPlaced` 이벤트도 오늘 재생 가능해야 한다.
그런데 그동안 이벤트 구조가 바뀌면(필드 추가/이름 변경) 옛 이벤트를 어떻게 읽을 것인가가 큰 숙제가 된다.

- 가능하면 **하위 호환되는 변경만** 한다(필드 추가는 OK, 의미 변경·삭제는 위험).
- 깨지는 변경이 불가피하면 **upcasting**(옛 버전 이벤트를 읽을 때 신버전 구조로 변환하는 계층)을 둔다.
- 이벤트에 `schemaVersion`을 처음부터 넣어 둔다.

### 4-3. 이벤트에 "왜"가 아니라 "결과"만 담기

`OrderStatusChanged { from: PAID, to: CANCELED }`처럼 상태 전이 결과만 담으면, CRUD의 `UPDATE`를 이벤트로 포장한 것에 불과하다.
도메인 의도를 살리려면 `OrderCanceledByCustomer { reason: ... }`처럼 **무슨 일이 왜 일어났는지**를 담아야 한다.
이 차이가 나중에 "고객 변심 취소율"과 "재고 부족 취소율"을 분석할 수 있느냐를 가른다.

### 4-4. 모든 것에 이벤트 소싱을 깔기

ES/CQRS는 인지 비용과 운영 복잡도가 높다.
재생 로직, 스냅샷, projection 재구축, 이벤트 버전 관리, 결과적 일관성 대응이 전부 따라온다.
단순 CRUD로 충분한 도메인(설정 관리, 단순 게시판)에 깔면 얻는 것 없이 복잡도만 떠안는다.

## 5. 설계·운영 체크포인트

도입을 검토할 때 점검할 항목들이다.

- **이벤트 저장소의 동시성 제어**: 같은 스트림에 두 쓰기가 동시에 오면? 보통 `(streamId, expectedVersion)` 기반 optimistic concurrency로 막는다. 버전이 어긋나면 거절하고 재시도한다.
- **projection 재구축 절차**: 읽기 모델 버그를 고친 뒤 처음부터 이벤트를 재생해 projection을 다시 만드는 운영 절차가 있는가. ES의 강점은 "읽기 모델을 언제든 버리고 다시 만들 수 있다"는 점이라, 이 절차가 없으면 강점을 못 쓴다.
- **이벤트 발행과 저장의 원자성**: 이벤트를 저장하면서 동시에 외부로 발행해야 한다면, 저장과 발행이 둘 다 성공해야 하는 분산 트랜잭션 문제가 생긴다. 이건 [Outbox 패턴](./outbox-inbox-pattern.md)의 영역이다.
- **멱등성**(idempotency): projection 핸들러가 같은 이벤트를 두 번 받아도(at-least-once 전달) 결과가 같아야 한다. seq나 eventId로 중복 적용을 막는다.
- **삭제·개인정보 처리**: append-only라 "지운다"가 어렵다. 개인정보 삭제 요구(GDPR 등)에 대응하려면 crypto-shredding(키 폐기로 복호화 불능화) 같은 별도 전략이 필요하다.

## 6. 손으로 정리하는 미니 모델

작은 주문 애그리거트를 이벤트 fold로 복원하는 형태를 의사코드로 그려보면 핵심이 잡힌다.

```ts
type OrderEvent =
  | { type: 'OrderPlaced'; amount: number }
  | { type: 'PaymentCompleted' }
  | { type: 'OrderShipped' }
  | { type: 'OrderCanceledByCustomer'; reason: string };

interface OrderState {
  status: 'NEW' | 'PAID' | 'SHIPPED' | 'CANCELED';
  amount: number;
}

// 현재 상태 = 초기 상태에서 이벤트를 하나씩 접어(fold) 계산
function apply(state: OrderState, e: OrderEvent): OrderState {
  switch (e.type) {
    case 'OrderPlaced':            return { status: 'NEW', amount: e.amount };
    case 'PaymentCompleted':       return { ...state, status: 'PAID' };
    case 'OrderShipped':           return { ...state, status: 'SHIPPED' };
    case 'OrderCanceledByCustomer':return { ...state, status: 'CANCELED' };
  }
}

function rehydrate(events: OrderEvent[]): OrderState {
  return events.reduce(apply, { status: 'NEW', amount: 0 });
}
```

여기서 `apply`는 순수 함수다.
같은 이벤트 목록이면 항상 같은 상태가 나온다 — 이 결정성(determinism)이 재생·스냅샷·projection 재구축을 모두 가능하게 하는 토대다.

## 7. 스스로 점검하는 질문

아래 질문에 막힘없이 답할 수 있으면 개념이 잡힌 것이다.

1. Event Sourcing과 CQRS는 왜 독립 패턴인가. 한쪽만 쓰는 예를 각각 들 수 있는가.
2. 이벤트 스트림이 수만 개로 길어졌을 때 현재 상태를 빠르게 얻는 방법은. 스냅샷이 진실의 원천이 아닌 이유는.
3. 쓰기 직후 읽기에서 옛 데이터가 보이는 현상은 버그인가. 어떻게 설계로 다뤄야 하는가.
4. 2년 전 이벤트 구조와 지금이 다를 때 옛 이벤트를 어떻게 읽는가(upcasting, schemaVersion).
5. `OrderStatusChanged`와 `OrderCanceledByCustomer` 중 무엇이 더 좋은 이벤트인가. 이유는.
6. append-only 저장소에서 개인정보 삭제 요구는 어떻게 대응하는가.
7. 이벤트 저장과 외부 발행을 모두 성공시켜야 할 때 분산 트랜잭션을 어떻게 피하는가([Outbox](./outbox-inbox-pattern.md)).

## 8. 한 줄 요약

상태를 덮어쓰지 않고 사건을 쌓는 것이 Event Sourcing, 읽기 모델과 쓰기 모델을 분리하는 것이 CQRS다.
둘 다 강력하지만 비용이 크므로, 이력 자체가 가치이거나 읽기/쓰기 부하 특성이 크게 갈리는 도메인에서만 선택적으로 도입한다.
