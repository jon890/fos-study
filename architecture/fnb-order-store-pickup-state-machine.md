# [초안] F&B 주문/매장/픽업 상태머신 설계 — CJ푸드빌 디지털 채널 백엔드 관점

## 왜 이 주제가 중요한가

F&B 디지털 채널(자사앱, 키오스크, 카카오톡 채널, 배달 플랫폼)에서 주문은 단순한 CRUD가 아니다. 주문이라는 한 건의 트랜잭션은 **사용자 단말, 결제 PG, 매장 POS, 주방 디스플레이(KDS), 픽업/배달 운영, 재고/할인 시스템**을 가로지르는 분산 워크플로다. 이 워크플로는 거의 항상 **부분 실패**(partial failure), **재시도**(retry), **지연**(latency spike)과 함께 살아간다. 모바일은 끊기고, POS는 점심 피크에 응답이 느려지고, 매장 직원은 실수로 주문을 두 번 접수한다.

이걸 if/else와 status 컬럼 한 개로 풀면 다음과 같은 사고가 누적된다.
- 결제는 됐는데 매장에서 주문이 사라짐
- 같은 주문이 두 번 제조됨
- 고객이 도착했는데 픽업대기 상태가 아닌 채로 남아 있음
- 환불 후에도 KDS에 주문이 그대로 떠 있음

이 문서는 4년차 이상 백엔드 엔지니어가 F&B 도메인 면접에서 "주문 상태 모델을 어떻게 설계하시겠습니까"라는 질문을 받았을 때, **상태머신 + 불변조건 + 멱등성 + Outbox + 운영 가시성**을 한 호흡에 설명할 수 있는 수준을 목표로 한다. 모델은 매장 픽업(Store Pickup) 시나리오를 중심에 두되, 부분적으로 배달/포장 시나리오도 포함한다.

관련 인프라 개념이 더 필요하면 별도 문서로 분리한다. 본 문서는 **상태 모델링과 그 운영**에 집중한다. (분산 트랜잭션 일반론은 `architecture/distributed-transactions.md` 같은 별도 문서로 링크하는 것을 권장한다.)

## 핵심 개념 — 왜 상태머신인가

상태머신을 도입하는 이유는 단순하다. **어떤 상태에서 어떤 이벤트가 들어오면 어떤 상태로만 갈 수 있는지를 코드/DB/문서가 모두 똑같이 이해해야 하기 때문**이다. 그렇지 않으면 다음과 같은 비대칭이 발생한다.
- 코드: "취소된 주문도 환불 처리하면 환불완료로 넘어간다"
- DB 데이터: 일부 주문은 취소 → 제조중 → 완료로 점프되어 있음 (운영자가 수동으로 update 함)
- 운영팀의 인식: "취소는 무조건 끝난 상태"

상태머신은 이 인식을 **하나의 진실**로 강제한다.

### 정의

- **State**: 주문이 머무를 수 있는 정적 위치. 예: `PENDING_PAYMENT`, `ACCEPTED`, `IN_PREPARATION`, `READY_FOR_PICKUP`, `COMPLETED`, `CANCELED`, `NO_SHOW`, `FAILED`.
- **Event**: 외부에서 들어오는 신호. 예: `PaymentApproved`, `StoreAccepted`, `KdsStartedCooking`, `PickupReady`, `CustomerPickedUp`, `CustomerNoShow`, `StoreRejected`, `Timeout`.
- **Transition**: (현재 상태, 이벤트) → 다음 상태. 정의되지 않은 조합은 **거절**(reject) 한다. 절대 "어쩌다 통과"되면 안 된다.
- **Guard**: 전이 직전에 만족해야 하는 추가 조건. 예: 매장 영업시간, 재고 잔량, 최소 주문금액.
- **Action / Side effect**: 전이 시 발생하는 부수 효과. 알림 발송, KDS 출력, 재고 차감, 정산 이벤트 발행 등. 이 부분은 반드시 **Outbox**를 거친다.

### 핵심 원칙

1. **단일 진실의 원천**(Single Source of Truth): 주문의 현재 상태는 `orders.status` 컬럼 하나로 결정. KDS, POS, 모바일 앱은 모두 이 값을 참조해 자기 표현을 그릴 뿐 자기 상태를 따로 보유하지 않는다.
2. **모든 전이는 명시적**: 허용 표에 없는 전이는 예외를 던진다.
3. **모든 전이는 멱등**: 같은 이벤트를 두 번 받아도 결과가 같아야 한다.
4. **모든 부수 효과는 Outbox**: 상태 변경과 외부 시스템 통지는 같은 트랜잭션 안에서 DB에만 기록하고, 별도 publisher가 비동기로 내보낸다.

## 상태 모델 — Store Pickup 기준

### 상태 목록

| 상태 | 설명 |
|---|---|
| `DRAFT` | 카트 단계, 사용자가 메뉴/옵션 선택 중 |
| `PENDING_PAYMENT` | 결제 진행 중, PG로부터 결과 대기 |
| `PAYMENT_FAILED` | 결제 실패 (단말 취소, 카드 거절, 한도 초과 등) |
| `PENDING_STORE_ACCEPT` | 결제 성공, 매장 POS 접수 대기 |
| `ACCEPTED` | 매장이 주문 접수, KDS로 분배되기 직전 |
| `IN_PREPARATION` | 제조 시작 |
| `READY_FOR_PICKUP` | 픽업대 비치 완료, 고객 알림 발송됨 |
| `COMPLETED` | 고객이 수령 완료 |
| `CANCELED` | 정상 취소(사용자 요청/매장 거절/시스템 이유) |
| `NO_SHOW` | 일정 시간 동안 미수령으로 자동 종결 |
| `REFUND_IN_PROGRESS` | 환불 진행 중(취소/노쇼 후속) |
| `REFUNDED` | 환불 완료 |
| `FAILED` | 회복 불가능한 시스템 실패(드물게 사용) |

### 전이 표

다음은 매장 픽업 기준 핵심 전이만 추린 것이다. 정의되지 않은 조합은 모두 거부.

| 현재 상태 | 이벤트 | 다음 상태 | Guard / 비고 |
|---|---|---|---|
| `DRAFT` | `Checkout` | `PENDING_PAYMENT` | 메뉴 가용/영업시간/최소주문 검증 |
| `PENDING_PAYMENT` | `PaymentApproved` | `PENDING_STORE_ACCEPT` | PG 결제 승인 콜백 |
| `PENDING_PAYMENT` | `PaymentDeclined` | `PAYMENT_FAILED` | |
| `PENDING_PAYMENT` | `Timeout(60s)` | `PAYMENT_FAILED` | PG 응답 미수신 시 |
| `PENDING_STORE_ACCEPT` | `StoreAccepted` | `ACCEPTED` | POS 접수 응답 |
| `PENDING_STORE_ACCEPT` | `StoreRejected` | `REFUND_IN_PROGRESS` | 품절/마감/장애 등 |
| `PENDING_STORE_ACCEPT` | `Timeout(180s)` | `REFUND_IN_PROGRESS` | 매장 응답 없음 |
| `ACCEPTED` | `KdsStartedCooking` | `IN_PREPARATION` | |
| `IN_PREPARATION` | `PickupReady` | `READY_FOR_PICKUP` | KDS 완료 신호 |
| `READY_FOR_PICKUP` | `CustomerPickedUp` | `COMPLETED` | 매장에서 픽업 확인 |
| `READY_FOR_PICKUP` | `Timeout(20m)` | `NO_SHOW` | 정책에 따라 가변 |
| `NO_SHOW` | `RefundDecided` | `REFUND_IN_PROGRESS` | 정책 따라 부분환불 가능 |
| `REFUND_IN_PROGRESS` | `RefundCompleted` | `REFUNDED` | |
| `ACCEPTED`, `IN_PREPARATION` | `UserCanceled` | `REFUND_IN_PROGRESS` | 정책: 제조 시작 후엔 거부할 수도 있음 |

### 시각화

```
DRAFT ──Checkout──> PENDING_PAYMENT ──Approved──> PENDING_STORE_ACCEPT ──Accepted──> ACCEPTED
                          │                                │
                       Declined/Timeout                 Rejected/Timeout
                          ▼                                ▼
                     PAYMENT_FAILED                  REFUND_IN_PROGRESS ──Completed──> REFUNDED

ACCEPTED ──KdsStarted──> IN_PREPARATION ──PickupReady──> READY_FOR_PICKUP
                                                              │
                                          ┌───────────────────┼────────────────┐
                                          ▼                   ▼                ▼
                                      PickedUp           Timeout(20m)      UserCanceled
                                          │                   │                │
                                       COMPLETED           NO_SHOW       REFUND_IN_PROGRESS
```

## 불변 조건(Invariants)

상태머신만 그린다고 끝이 아니다. 다음은 데이터 레벨에서 항상 참이어야 하는 불변조건이다. 면접에서 "이 모델의 무결성을 어떻게 지키냐"는 질문이 들어오면 이 목록을 답하면 된다.

1. **결제 없이 ACCEPTED 이상 진입 불가.** `status >= ACCEPTED` 인 주문은 반드시 대응되는 결제 승인 레코드가 존재한다.
2. **COMPLETED는 불가역.** COMPLETED → 다른 상태로 직접 전이 없음. 환불이 필요하면 별도의 `refunds` 엔티티를 통해 처리.
3. **CANCELED/NO_SHOW는 종결.** REFUND_IN_PROGRESS/REFUNDED를 거치는 경로 외에는 분기 없음.
4. **금액 합계 = 라인합계 + 옵션합계 - 할인.** 상태 전이와 무관하게 항상 성립. CHECK 제약 또는 도메인 invariants test로 강제.
5. **하나의 결제는 하나의 주문에 1:1.** 부분 환불은 결제 분할이 아니라 환불 라인으로 표현.
6. **재고 차감은 ACCEPTED 시점.** PENDING_STORE_ACCEPT는 예약 holdo으로만 표현, 실제 차감은 매장 접수 시.

## 실전 백엔드 활용 — 동시성, 중복, 멱등성

### 모바일 재시도 시나리오

가장 흔한 사고: 결제 화면에서 사용자가 "결제하기"를 두 번 탭한다. 또는 네트워크가 끊긴 상태에서 앱이 자동 재시도한다. 그 결과 같은 주문이 두 번 만들어지거나 같은 결제가 두 번 승인된다.

해결 방법은 두 축이다.

**(a) 클라이언트 측 멱등키.** 앱이 주문 시도마다 UUID(예: `idempotency-key: 2c3a...e4b9`)를 발급하고, 같은 키로 재시도. 서버는 `idempotency_keys(key, request_hash, response_snapshot, created_at)` 테이블을 둔다.

**(b) 서버 측 dedupe.** 같은 idempotency-key가 들어오면 새 주문을 만들지 않고 이전 응답을 그대로 돌려준다. 단 `request_hash`가 다르면 충돌로 처리해야 한다(키 재사용 사고 방지).

```sql
-- MySQL 8 예시
CREATE TABLE idempotency_keys (
  key_value     VARCHAR(64)  NOT NULL PRIMARY KEY,
  request_hash  CHAR(64)     NOT NULL,
  status        VARCHAR(16)  NOT NULL, -- IN_PROGRESS / DONE / FAILED
  response_body JSON         NULL,
  created_at    DATETIME(6)  NOT NULL,
  expires_at    DATETIME(6)  NOT NULL
);
```

### 상태 전이의 동시성

매장 직원이 "접수" 버튼을 누르는 동시에 자동 타임아웃 작업이 "거절"로 전이를 시도한다. 둘 중 하나만 이겨야 한다. 두 가지 패턴 중 선택.

**낙관적 락**(권장 기본): `orders` 테이블에 `version` 컬럼을 둔다.

```sql
UPDATE orders
   SET status = 'ACCEPTED',
       version = version + 1,
       accepted_at = NOW(6)
 WHERE order_id = ?
   AND status = 'PENDING_STORE_ACCEPT'
   AND version = ?;
```

영향 행 수가 0이면 누군가 먼저 전이했다는 뜻이고, 이쪽은 멱등 응답을 만들거나 비즈니스 에러를 반환한다.

**비관적 락**(필요 시): 한 주문에 대해 매우 짧은 트랜잭션 안에서 `SELECT ... FOR UPDATE`로 잠그고 상태 전이 + Outbox 기록까지 마친다. 트랜잭션 길이를 짧게 유지하는 것이 핵심.

### Guard와 외부 시스템

`PENDING_STORE_ACCEPT`로 가기 전에 매장 영업 여부, 메뉴 품절 여부, 옵션 가용성을 체크해야 한다. 이때 절대 매장 POS 호출을 동기적으로 트랜잭션 안에서 하지 않는다. 다음 패턴을 사용한다.

- 매장/메뉴 가용성은 캐시(Redis) 우선 조회 + 짧은 TTL.
- POS 접수는 비동기 큐를 통해 보내고, 응답은 별도 webhook/콜백으로 수신.
- DB 트랜잭션 안에서는 절대 외부 HTTP를 호출하지 않는다.

## 좋은 예 vs 나쁜 예

### 나쁜 예: enum 분기와 동기 호출

```java
// BAD
@Transactional
public void acceptOrder(Long orderId) {
    Order order = orderRepository.findById(orderId).orElseThrow();
    if (!order.getStatus().equals("PENDING_STORE_ACCEPT")) {
        throw new IllegalStateException("이미 처리됨");
    }
    posClient.send(order);                 // 외부 호출이 트랜잭션 안에 있음
    kdsClient.print(order);                // 두 번 보내질 위험
    notificationClient.push(order.getUserId(), "접수 완료"); // 실패하면 롤백되며 사용자에게 일관성 깨짐
    order.setStatus("ACCEPTED");
    orderRepository.save(order);
}
```

문제점:
- 트랜잭션이 외부 시스템 응답 시간만큼 길어짐 → DB 커넥션 점유 폭증.
- POS 호출은 성공했지만 알림 발송이 실패하면 트랜잭션 롤백 → POS에는 주문이 가 있고 DB는 PENDING.
- 동시에 두 번 호출되면 둘 다 `PENDING_STORE_ACCEPT` 체크를 통과해 KDS에 두 번 출력될 수 있음(read-then-write race).

### 개선된 예: 상태머신 + 낙관적 락 + Outbox

```java
// GOOD
@Transactional
public AcceptResult acceptOrder(AcceptOrderCommand cmd) {
    Order order = orderRepository.findById(cmd.orderId()).orElseThrow();

    Transition t = stateMachine.resolve(order.getStatus(), Event.STORE_ACCEPTED);
    // 정의되지 않은 전이는 여기서 즉시 거부

    int updated = orderRepository.transitionWithVersion(
        cmd.orderId(),
        order.getStatus(),       // expected
        t.next(),                // ACCEPTED
        order.getVersion()
    );
    if (updated == 0) {
        return AcceptResult.alreadyTransitioned();   // 멱등 응답
    }

    outboxRepository.append(
        OutboxEvent.of("OrderAccepted", cmd.orderId(), payload(order))
    );
    return AcceptResult.ok();
}
```

여기에서 외부 호출은 트랜잭션 밖이다. 별도의 OutboxPublisher가 outbox 행을 폴링/CDC로 읽어 KDS, 알림, 정산 시스템으로 이벤트를 비동기 발송한다.

## Outbox 패턴 — 상태 변경과 통지를 안전하게 묶기

상태 전이 + 외부 알림을 한 트랜잭션 안에 묶으려는 시도는 거의 항상 분산 트랜잭션 함정으로 끝난다. Outbox는 이걸 우회한다.

```sql
CREATE TABLE outbox_events (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  aggregate_id  VARCHAR(64) NOT NULL,
  type          VARCHAR(64) NOT NULL,
  payload       JSON        NOT NULL,
  created_at    DATETIME(6) NOT NULL,
  published_at  DATETIME(6) NULL,
  attempts      INT         NOT NULL DEFAULT 0,
  INDEX idx_unpublished (published_at, id)
);
```

핵심 규칙:
- 비즈니스 트랜잭션은 `orders` UPDATE + `outbox_events` INSERT 까지만 수행.
- 별도 publisher가 `published_at IS NULL` 행을 폴링하거나, Debezium 등의 CDC가 binlog에서 읽어 Kafka에 발행.
- 컨슈머는 `event_id` 기준 멱등 처리. 같은 이벤트가 두 번 와도 KDS에 두 번 출력되지 않게 컨슈머 측에서도 dedupe.
- payload에는 비즈니스 의사결정에 필요한 데이터를 함께 넣어 컨슈머가 다시 DB를 조회하지 않아도 되게 한다.

## 운영 모니터링

상태머신 자체보다 **운영자가 무엇을 보고 있는가**가 사고 시 회복 시간을 결정한다. 다음 지표를 갖춘다.

- 상태별 체류 시간 분포(p50/p95/p99). 특히 `PENDING_STORE_ACCEPT`, `IN_PREPARATION`, `READY_FOR_PICKUP`.
- 상태별 stuck 카운트: 임계 시간을 넘긴 주문 수. 알람 임계값은 매장 평균 운영 시간을 기반으로 결정.
- 비정상 전이 시도 카운트(허용 표에 없는 전이가 들어온 경우). 0이어야 한다. 1이라도 뜨면 즉시 조사.
- Outbox lag: `created_at`과 `published_at`의 차이. 1분 이상 lag 시 알람.
- POS 콜백 실패율, 멱등키 충돌 카운트, 환불 진행 중에서 24시간 이상 머문 건수.

운영 화면에서는 단일 주문에 대한 **state transition timeline**을 무조건 노출한다. 사고 분석 시 가장 먼저 보는 화면이다.

## 로컬 실습 환경

MySQL 8 + Spring Boot 기준의 미니 실습 셋을 그려둔다. 면접 직전 점검용으로 충분하다.

### 스키마

```sql
CREATE TABLE orders (
  order_id     BIGINT      NOT NULL PRIMARY KEY,
  store_id     BIGINT      NOT NULL,
  user_id      BIGINT      NOT NULL,
  status       VARCHAR(32) NOT NULL,
  total_amount INT         NOT NULL,
  version      INT         NOT NULL DEFAULT 0,
  created_at   DATETIME(6) NOT NULL,
  updated_at   DATETIME(6) NOT NULL,
  INDEX idx_store_status (store_id, status, updated_at)
);

CREATE TABLE order_state_logs (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id      BIGINT      NOT NULL,
  from_status   VARCHAR(32),
  to_status     VARCHAR(32) NOT NULL,
  event_type    VARCHAR(32) NOT NULL,
  actor         VARCHAR(64),
  occurred_at   DATETIME(6) NOT NULL,
  INDEX idx_order (order_id, occurred_at)
);
```

`order_state_logs`는 audit log이자 상태머신 디버깅 도구다. 운영자가 "왜 이 상태로 갔는가"를 답할 수 있게 만든다.

### 전이 표 코드

```java
public enum OrderStatus {
    DRAFT, PENDING_PAYMENT, PAYMENT_FAILED,
    PENDING_STORE_ACCEPT, ACCEPTED, IN_PREPARATION,
    READY_FOR_PICKUP, COMPLETED, CANCELED, NO_SHOW,
    REFUND_IN_PROGRESS, REFUNDED, FAILED
}

public enum OrderEvent {
    CHECKOUT, PAYMENT_APPROVED, PAYMENT_DECLINED,
    STORE_ACCEPTED, STORE_REJECTED, KDS_STARTED,
    PICKUP_READY, CUSTOMER_PICKED_UP, CUSTOMER_NO_SHOW,
    USER_CANCELED, REFUND_DECIDED, REFUND_COMPLETED, TIMEOUT
}

@Component
public class OrderStateMachine {
    private final Map<Key, OrderStatus> transitions = Map.ofEntries(
        Map.entry(Key.of(DRAFT, CHECKOUT),                 PENDING_PAYMENT),
        Map.entry(Key.of(PENDING_PAYMENT, PAYMENT_APPROVED), PENDING_STORE_ACCEPT),
        Map.entry(Key.of(PENDING_PAYMENT, PAYMENT_DECLINED), PAYMENT_FAILED),
        Map.entry(Key.of(PENDING_STORE_ACCEPT, STORE_ACCEPTED), ACCEPTED),
        Map.entry(Key.of(PENDING_STORE_ACCEPT, STORE_REJECTED), REFUND_IN_PROGRESS),
        Map.entry(Key.of(ACCEPTED, KDS_STARTED), IN_PREPARATION),
        Map.entry(Key.of(IN_PREPARATION, PICKUP_READY), READY_FOR_PICKUP),
        Map.entry(Key.of(READY_FOR_PICKUP, CUSTOMER_PICKED_UP), COMPLETED),
        Map.entry(Key.of(READY_FOR_PICKUP, CUSTOMER_NO_SHOW), NO_SHOW),
        Map.entry(Key.of(NO_SHOW, REFUND_DECIDED), REFUND_IN_PROGRESS),
        Map.entry(Key.of(REFUND_IN_PROGRESS, REFUND_COMPLETED), REFUNDED)
        // 나머지 전이는 명시적으로 금지
    );

    public OrderStatus next(OrderStatus current, OrderEvent event) {
        OrderStatus next = transitions.get(Key.of(current, event));
        if (next == null) {
            throw new IllegalStateTransitionException(current, event);
        }
        return next;
    }

    private record Key(OrderStatus s, OrderEvent e) {
        static Key of(OrderStatus s, OrderEvent e) { return new Key(s, e); }
    }
}
```

### 실행 가능한 실습 시나리오

1. 주문 100건을 동시에 생성한다(스레드 풀 20).
2. 각 주문에 대해 결제 승인 이벤트를 두 번 보낸다(중복 시뮬레이션).
3. 절반은 `STORE_ACCEPTED`, 절반은 타임아웃을 발생시킨다.
4. 종료 후 `order_state_logs`를 조회하여 모든 주문이 정의된 경로만 따랐는지 확인.
5. `outbox_events`를 조회해 모든 OrderAccepted/OrderRejected 이벤트가 정확히 1번씩 발행되었는지 확인.

이 실습을 통과하면 **동시성, 중복, 멱등성**이 한 번에 검증된다.

## 자주 보는 실수 패턴

- **상태 컬럼이 두 곳.** `orders.status`와 `order_payments.status`가 따로 살아 있고 둘이 어긋남. → 결제는 별도 엔티티지만 주문 상태의 진실은 `orders`에 있어야 한다.
- **전이 표가 코드에 흩어짐.** `if (status == X) status = Y`가 여러 서비스에 분산되어 있음. → 단일 `StateMachine` 컴포넌트로 모은다.
- **타임아웃을 cron으로만 처리.** 분단위 cron은 사용자 체감을 망친다. → delayed queue 또는 scheduled job per-order.
- **NO_SHOW 정책이 모호.** 환불 가능 여부, 부분 환불 여부, 재주문 정책이 명시되지 않음 → 운영팀과 합의된 표를 코드로 옮긴다.
- **사용자 취소를 "어떤 상태에서든 가능"으로 둠.** → 제조 시작 후 취소 거부 정책을 명시적으로 표에 박는다.
- **Outbox 없이 Kafka 직접 발행.** 트랜잭션 커밋 실패 시 이벤트가 먼저 나가 있는 사고. → 항상 Outbox 경유.
- **상태 변경 메시지를 컨슈머가 dedupe 안 함.** 발행자만 멱등이고 컨슈머는 중복 처리하면 무용지물.

## 면접 답변 프레이밍 — 시니어 백엔드 관점

면접관이 "F&B 매장 픽업 주문 시스템을 설계해 보세요"라고 하면 다음 흐름으로 답하면 좋다.

1. **도메인 분리부터 선언한다.** "주문, 결제, 매장 접수, 제조, 픽업, 정산은 각각 다른 라이프사이클입니다. 단일 주문 엔티티가 모든 라이프사이클을 들고 있게 두면 곧 부서지므로, **주문 상태머신을 코어로 두고 결제/제조/픽업은 각각 별도 컨텍스트로 분리**하겠습니다."
2. **상태머신 기반으로 모델링한다.** "현재/이벤트/다음 상태와 guard, action을 명시적 표로 만들고, 정의되지 않은 전이는 거절합니다."
3. **부분 실패 시나리오를 먼저 꺼낸다.** "결제는 됐는데 매장 접수가 실패한 경우, PG 응답 타임아웃, 모바일 중복 요청, POS 응답 지연. 이 네 가지를 어떤 메커니즘으로 흡수하는지 설명드리겠습니다."
4. **멱등성과 동시성을 숫자로 답한다.** "Idempotency-Key 기반 dedupe + 낙관적 락으로 동시성. 멱등키는 24시간 보존, 낙관락은 version 컬럼."
5. **Outbox로 정합성을 보장한다.** "상태 변경과 외부 통지를 같은 트랜잭션 안에 묶지 않습니다. DB에 outbox 행을 쓰고 별도 publisher가 발행합니다."
6. **운영 가시성으로 마무리한다.** "상태별 체류 시간, stuck count, outbox lag, 비정상 전이 시도를 모두 모니터링하고, 단일 주문에 대해 state transition timeline을 항상 노출하는 운영 화면을 둡니다."

여기서 단골 follow-up 질문과 답변 포인트를 미리 정리해 둔다.

- **"환불은 어떻게 모델링하나요?"** → 별도 `refunds` aggregate. 주문 상태를 환불완료로 직접 바꾸지 않고 환불 라인을 추가, 주문 상태는 `REFUND_IN_PROGRESS` → `REFUNDED`로 천이.
- **"매장 POS가 30분 동안 죽으면?"** → `PENDING_STORE_ACCEPT`에서 타임아웃 정책 발동. 일정 횟수 재시도 후 자동 거절 + 환불. 운영자에게 알림. 신규 주문은 매장 단위 서킷 브레이커로 차단.
- **"픽업 완료 처리를 누가 누르나요?"** → 매장 직원의 픽업 확인 또는 NFC/QR 스캔. 단순 클릭만 두면 누락이 발생하므로, 일정 시간 후 자동 NO_SHOW 처리 정책을 함께 두어 두 안전장치를 가진다.
- **"같은 주문이 두 번 만들어지지 않는 이유는요?"** → 클라이언트 idempotency-key + 서버 dedupe 테이블 + 결제 PG 측 idempotency.
- **"주문 통계는 어디서 뽑나요?"** → `order_state_logs`에서 transition 단위로 통계, 또는 outbox에서 분석 파이프라인으로 stream. orders 테이블을 OLAP 용도로 직접 긁지 않는다.

## 체크리스트

- [ ] 상태 enum과 이벤트 enum을 코드 한 곳에 둔다
- [ ] 전이 표는 단일 컴포넌트(StateMachine)로 집중
- [ ] 정의되지 않은 전이는 명시적 예외
- [ ] 모든 상태 전이는 낙관적 락(version) 적용
- [ ] 모든 외부 통지는 Outbox 경유
- [ ] 클라이언트 idempotency-key 발급/저장/만료 정책 명시
- [ ] 매장 응답 타임아웃 정책(시간/재시도 횟수/서킷 브레이커) 정의
- [ ] NO_SHOW/취소/환불 정책을 운영팀과 합의된 표로 보유
- [ ] `order_state_logs`로 모든 전이를 audit
- [ ] 상태별 체류 시간, stuck count, outbox lag 모니터링 대시보드 보유
- [ ] 운영자용 단일 주문 timeline 화면 제공
- [ ] 비정상 전이 시도 카운트 알람 임계값 설정
- [ ] 부하 테스트로 동시 결제 승인 + 동시 매장 접수 시나리오 통과 확인
- [ ] 트랜잭션 안에서 외부 HTTP를 호출하지 않는지 정적 분석으로 검증

## 관련

- [F&B 이커머스 결제·환불·정산 운영 가이드](./fnb-payment-refund-settlement-operations.md) — 결제·환불 상태가 주문 상태머신과 만나는 지점
