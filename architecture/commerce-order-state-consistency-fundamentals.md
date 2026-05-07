# [초안] 커머스 주문 상태와 데이터 정합성 기본기 — CJ푸드빌 면접 대비

## 왜 중요한가

커머스/외식 도메인 백엔드에서 "주문이 두 번 들어갔다", "결제는 됐는데 접수가 안 됐다", "취소했는데 매장에는 조리 지시가 내려갔다" 같은 사고는 거의 전부 **주문 상태 머신과 데이터 정합성 기본기**의 문제다. 신기술이 아니라 트랜잭션, 락, 멱등성, 상태 전이 검증이 무너졌을 때 발생한다.

CJ푸드빌처럼 매장 POS, 키오스크, 모바일 앱, 배달 플랫폼이 동시에 같은 주문 도메인을 건드리는 환경에서는 다음 세 가지가 시니어 백엔드의 기본기로 검증된다.

1. 주문 라이프사이클을 **유한 상태 머신(FSM)** 으로 모델링할 수 있는가
2. 모바일 재시도와 네트워크 단절을 견디는 **멱등성**과 **중복 차단**을 설계할 수 있는가
3. 동시성/트랜잭션/이벤트 발행을 **하나의 일관된 경계** 안에서 다룰 수 있는가

면접에서 "주문 처리 어떻게 만들어요?"라는 질문이 들어오면, 시니어와 주니어를 가르는 선은 결국 이 세 줄이다. 이 문서는 그 기본기를 한 번에 정리한다.

## 핵심 개념 1 — 주문 상태를 유한 상태 머신으로 본다

주문은 "필드 몇 개 가진 row"가 아니라 **상태(state)** 와 **이벤트(event)** 의 조합이다. 외식/커머스에서 자주 쓰는 최소 상태 집합은 다음과 같다.

| 상태 | 의미 | 진입 조건 |
|------|------|----------|
| `CREATED` | 장바구니 → 주문 객체 생성, 결제 직전 | 사용자 결제 버튼 클릭 |
| `PAYMENT_PENDING` | PG 호출 대기/진행 중 | PG 인증 시작 |
| `PAID` | 결제 승인 완료 | PG webhook/응답 OK |
| `ACCEPTED` | 매장 POS 접수 완료 | 매장 단말 응답 |
| `PREPARING` | 조리/준비 중 | 매장 상태 업데이트 |
| `READY` | 픽업/서빙 가능 | 매장 완료 보고 |
| `COMPLETED` | 고객 수령/식사 완료 | 종료 트리거 |
| `CANCELED` | 사용자/매장 취소 | 취소 사유 + 환불 정책 통과 |
| `REFUNDED` | 환불 완료 | PG 환불 응답 OK |
| `FAILED` | 결제/접수 영구 실패 | 재시도 정책 소진 |

핵심은 상태가 **임의로** 바뀌면 안 된다는 점이다. 허용된 전이만 정의한다.

```
CREATED → PAYMENT_PENDING → PAID → ACCEPTED → PREPARING → READY → COMPLETED
                       ↘ FAILED
              PAID → CANCELED → REFUNDED
              ACCEPTED → CANCELED → REFUNDED
              PREPARING → (정책에 따라 CANCELED 불가, 부분 환불만 허용)
```

이 표를 코드로 옮기면 다음과 같다.

```java
public enum OrderStatus {
    CREATED, PAYMENT_PENDING, PAID, ACCEPTED, PREPARING,
    READY, COMPLETED, CANCELED, REFUNDED, FAILED;

    private static final Map<OrderStatus, Set<OrderStatus>> ALLOWED = Map.of(
        CREATED,         Set.of(PAYMENT_PENDING, CANCELED),
        PAYMENT_PENDING, Set.of(PAID, FAILED, CANCELED),
        PAID,            Set.of(ACCEPTED, CANCELED),
        ACCEPTED,        Set.of(PREPARING, CANCELED),
        PREPARING,       Set.of(READY),
        READY,           Set.of(COMPLETED),
        COMPLETED,       Set.of(),
        CANCELED,        Set.of(REFUNDED),
        REFUNDED,        Set.of(),
        FAILED,          Set.of()
    );

    public boolean canTransitTo(OrderStatus next) {
        return ALLOWED.getOrDefault(this, Set.of()).contains(next);
    }
}
```

이걸 아예 도메인 메서드 안에서 강제한다.

```java
public void markPaid() {
    if (!status.canTransitTo(OrderStatus.PAID)) {
        throw new IllegalOrderTransitionException(status, OrderStatus.PAID);
    }
    this.status = OrderStatus.PAID;
    this.paidAt = LocalDateTime.now();
}
```

## 핵심 개념 2 — 상태 전이 불변 조건(invariant)

FSM 자체는 절반에 불과하다. 실제 사고는 **불변 조건이 비즈니스 규칙으로 들어가지 않을 때** 발생한다. 외식 도메인에서 자주 깨지는 불변 조건 예시:

- `PAID` 없이는 `ACCEPTED`로 갈 수 없다.
- `CANCELED`된 주문에 추가 결제를 붙일 수 없다.
- `REFUNDED`된 주문은 어떤 이벤트로도 다시 `PREPARING`이 될 수 없다.
- 동일 주문에 대해 `paid_amount = sum(payment.amount where status = APPROVED)`이 항상 성립해야 한다.
- 매장 접수 후 일정 단계(`PREPARING`)부터는 사용자 단독 취소 불가, 매장 동의 또는 부분 환불 정책으로만 처리한다.

이런 규칙은 **DB 제약 + 도메인 코드 + 이벤트 핸들러** 세 곳에 분산되기 쉬운데, 시니어가 면접에서 가산점을 받는 포인트는 "어디에 어떤 책임을 두는지" 명확히 답하는 것이다.

- DB: 외래키, NOT NULL, CHECK, 유니크 제약 (구조적 정합성)
- 도메인 객체: 상태 전이 메서드 (불변 조건)
- 애플리케이션 서비스: 트랜잭션 경계, 락 전략 (동시성)
- 이벤트 핸들러: 외부 시스템 동기화 (결과적 일관성)

## 핵심 개념 3 — 중복 요청과 모바일 재시도 (멱등성)

모바일 환경에서는 사용자가 결제 버튼을 두 번 누르거나, 네트워크가 끊긴 상태에서 앱이 자동 재시도한다. 서버는 같은 의도가 두 번 들어와도 결과가 한 번만 일어나도록 만들어야 한다.

세 가지 전형적인 도구를 같이 쓴다.

1. **Idempotency-Key 헤더**: 클라이언트가 한 트랜잭션마다 UUID를 발급
2. **유니크 제약**: `(idempotency_key)` 또는 `(user_id, client_request_id)` 컬럼에 UNIQUE
3. **요청-응답 캐시**: 같은 키로 들어온 요청은 저장된 응답을 그대로 돌려준다

```sql
CREATE TABLE order_request_log (
    idempotency_key  VARCHAR(64)  NOT NULL,
    user_id          BIGINT       NOT NULL,
    request_hash     CHAR(64)     NOT NULL,
    response_status  INT,
    response_body    JSON,
    order_id         BIGINT,
    created_at       DATETIME(3)  NOT NULL,
    PRIMARY KEY (idempotency_key),
    UNIQUE KEY uk_user_req (user_id, request_hash)
) ENGINE=InnoDB;
```

서비스 흐름:

```java
@Transactional
public OrderResponse placeOrder(String idemKey, PlaceOrderCommand cmd) {
    return requestLogRepo.findById(idemKey)
        .map(this::replay)
        .orElseGet(() -> {
            try {
                Order order = orderService.create(cmd);
                requestLogRepo.save(RequestLog.success(idemKey, cmd, order));
                return OrderResponse.of(order);
            } catch (DataIntegrityViolationException dup) {
                // 동시에 같은 키로 들어온 두 번째 요청
                return replay(requestLogRepo.findById(idemKey).orElseThrow());
            }
        });
}
```

핵심 포인트:
- `INSERT ... ON DUPLICATE KEY` 또는 PK 충돌 예외를 잡아 **두 번째 요청도 첫 번째와 같은 응답**을 받게 한다.
- `request_hash`까지 비교해서 같은 키로 다른 요청이 들어오면 명시적으로 거절한다(키 재사용 방지).
- 이 로그는 결제/접수처럼 외부 부수 효과를 만드는 모든 진입점에 적용한다.

## 핵심 개념 4 — 동시성, 트랜잭션, 락

같은 주문 row를 여러 주체가 동시에 만지는 시나리오는 다음과 같다.

- 사용자가 취소를 누르는 순간, 매장 POS가 접수 처리를 한다.
- PG webhook이 `PAID`로 바꾸려는데, 사용자가 결제 취소 요청을 보낸다.
- 같은 주문에 대해 결제 승인 콜백이 두 번 도착한다.

세 가지 도구를 상황별로 쓴다.

### 1) 비관적 락 (`SELECT ... FOR UPDATE`)

상태 전이가 읽기-수정-쓰기 패턴일 때 가장 안전하다.

```java
@Transactional
public void cancelByUser(Long orderId) {
    Order order = orderRepo.findByIdForUpdate(orderId)   // SELECT ... FOR UPDATE
        .orElseThrow(OrderNotFoundException::new);
    order.cancelByUser();   // 내부에서 canTransitTo 검증
    eventPublisher.publish(new OrderCanceledEvent(order.getId()));
}
```

```sql
SELECT * FROM orders WHERE id = ? FOR UPDATE;
```

매우 짧은 트랜잭션에서만 쓰고, 여러 row를 잠그면 데드락 가능성을 검토한다. **항상 같은 순서로 락을 잡는다**(예: `order_id` 오름차순)는 규율을 정한다.

### 2) 낙관적 락 (`@Version`)

충돌 빈도가 낮고 처리량이 중요할 때 쓴다.

```java
@Entity
class Order {
    @Version
    private Long version;
}
```

업데이트 시 버전 불일치면 `OptimisticLockException`이 터지고, 호출부는 재시도 또는 사용자에게 "다시 시도하세요" 응답을 돌려준다.

### 3) 격리 수준

MySQL InnoDB 기본은 `REPEATABLE READ`다. 주문 도메인에서 자주 헷갈리는 포인트:

- `REPEATABLE READ` + 일반 `SELECT`는 스냅샷을 읽는다(MVCC). 즉, 다른 트랜잭션의 커밋된 변경이 안 보일 수 있다.
- 상태 전이를 검증하는 순간엔 반드시 `SELECT ... FOR UPDATE` 또는 `LOCK IN SHARE MODE`로 **락을 잡고 현재 상태를 읽어야** 한다.
- "방금 read한 status가 PAID였으니까 ACCEPTED로 update하면 되겠지"는 락 없이는 깨질 수 있다.

### 깨지는 예 vs 고친 예

**나쁜 예**: 락 없이 검증

```java
@Transactional
public void accept(Long orderId) {
    Order order = orderRepo.findById(orderId).orElseThrow();
    if (order.getStatus() != OrderStatus.PAID) throw new IllegalStateException();
    order.setStatus(OrderStatus.ACCEPTED);   // 다른 트랜잭션이 이미 CANCELED로 바꿨을 수 있음
}
```

**개선**: 락 + 도메인 메서드 + 조건부 업데이트

```java
@Transactional
public void accept(Long orderId) {
    Order order = orderRepo.findByIdForUpdate(orderId).orElseThrow();
    order.markAccepted();   // 내부 canTransitTo 검사
}
```

또는 SQL 레벨에서 한 번에 검증:

```sql
UPDATE orders
   SET status = 'ACCEPTED', accepted_at = NOW(3)
 WHERE id = ?
   AND status = 'PAID';
```

업데이트 row 수가 0이면 "이미 다른 상태로 바뀌었다"고 판단해 비즈니스 예외를 던진다. **이 패턴은 면접에서 자주 묻는다**.

## 핵심 개념 5 — 트랜잭션 경계와 이벤트 발행

주문 처리는 거의 항상 외부 부수 효과를 동반한다(매장 POS 호출, 알림 발송, 적립금 차감). 이걸 한 트랜잭션 안에 다 넣으면 DB 락 시간이 길어지고 외부 호출 실패로 정상 처리도 같이 롤백된다. 반대로 트랜잭션 밖에서 호출하면 "DB는 PAID인데 매장에는 접수 요청이 안 갔다"가 발생한다.

기본 패턴은 **Transactional Outbox**다.

```sql
CREATE TABLE outbox (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    aggregate_id BIGINT NOT NULL,
    type         VARCHAR(64) NOT NULL,
    payload      JSON NOT NULL,
    created_at   DATETIME(3) NOT NULL,
    sent_at      DATETIME(3) NULL,
    INDEX idx_unsent (sent_at, id)
) ENGINE=InnoDB;
```

서비스 안에서:

```java
@Transactional
public void markPaid(Long orderId, PaymentApprovedEvent ev) {
    Order order = orderRepo.findByIdForUpdate(orderId).orElseThrow();
    order.markPaid();
    outboxRepo.save(OutboxMessage.of("OrderPaid", order));   // 같은 트랜잭션
}
```

별도의 publisher 워커가 outbox에서 미발송 row를 읽어 Kafka/HTTP로 보낸다. 발송 성공 시 `sent_at`을 업데이트한다.

이 구조의 의미:
- DB 커밋과 이벤트 기록이 **원자적**이다.
- 발송 실패 시 publisher만 재시도하면 된다.
- 컨슈머는 이벤트를 여러 번 받을 수 있다는 가정으로 **멱등 처리**한다(`event_id` 기반 dedup 테이블).

## 핵심 개념 6 — 결제와 환불의 정합성

결제는 외부 PG가 진실의 원천이다. 내가 가진 DB는 **PG 상태의 사본**이라는 점을 잊지 않는다.

원칙:
1. 결제 승인 응답 또는 webhook으로 상태를 갱신한다. webhook은 여러 번 올 수 있으니 PG의 `tid`를 유니크 키로 잡는다.
2. 환불은 항상 **부분 환불 가능 모델**로 만들고, `refunded_amount <= paid_amount` 불변 조건을 DB CHECK 또는 도메인에서 강제한다.
3. 환불 후 매장 도구로 조리 중이라면, "이미 매장에서 처리 중인 주문은 사용자 단독 환불이 안 된다"는 정책을 명시한다.

```sql
CREATE TABLE payment (
    id            BIGINT PRIMARY KEY,
    order_id      BIGINT NOT NULL,
    pg_tid        VARCHAR(64) NOT NULL,
    amount        INT NOT NULL,
    status        VARCHAR(20) NOT NULL,
    approved_at   DATETIME(3),
    UNIQUE KEY uk_pg_tid (pg_tid),
    INDEX idx_order (order_id)
);
```

## 로컬 실습 환경

도커 한 개로 충분하다.

```bash
docker run --name mysql-order -e MYSQL_ROOT_PASSWORD=root \
  -p 3306:3306 -d mysql:8.0
```

스키마와 시드:

```sql
CREATE DATABASE order_demo;
USE order_demo;

CREATE TABLE orders (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    status       VARCHAR(20) NOT NULL,
    total_amount INT NOT NULL,
    version      INT NOT NULL DEFAULT 0,
    created_at   DATETIME(3) NOT NULL,
    updated_at   DATETIME(3) NOT NULL,
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB;

INSERT INTO orders (user_id, status, total_amount, version, created_at, updated_at)
VALUES (1, 'PAID', 24000, 0, NOW(3), NOW(3));
```

## 실습 1 — 동시 취소/접수 충돌 재현

세션 A:

```sql
START TRANSACTION;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 현재 status = PAID
```

세션 B (다른 터미널):

```sql
START TRANSACTION;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;   -- 블록됨
```

세션 A에서:

```sql
UPDATE orders SET status = 'CANCELED', updated_at = NOW(3) WHERE id = 1;
COMMIT;
```

세션 B 블록이 풀리고 다시 읽으면 status는 이미 `CANCELED`다. 여기서 `ACCEPTED`로 가려면 도메인 검증이 막아야 한다. **이 흐름을 직접 한 번 돌려보면 락 동작이 손에 익는다**.

## 실습 2 — 조건부 업데이트로 상태 전이 강제

```sql
UPDATE orders
   SET status = 'ACCEPTED', updated_at = NOW(3)
 WHERE id = 1 AND status = 'PAID';
```

업데이트 row 수가 0이면 도메인 예외. 락 없이도 대부분의 단순 전이는 이 한 줄로 안전하다(단, 같은 트랜잭션 내에서 추가 검증이 필요하면 락이 필요).

## 실습 3 — 멱등성 테이블 직접 만들기

```sql
CREATE TABLE order_request_log (
    idempotency_key VARCHAR(64) PRIMARY KEY,
    order_id        BIGINT,
    response_body   JSON,
    created_at      DATETIME(3) NOT NULL
);

INSERT INTO order_request_log (idempotency_key, order_id, response_body, created_at)
VALUES ('uuid-1', 100, JSON_OBJECT('status','PAID'), NOW(3));

-- 같은 키 재시도 시뮬레이션
INSERT INTO order_request_log (idempotency_key, order_id, response_body, created_at)
VALUES ('uuid-1', 100, JSON_OBJECT('status','PAID'), NOW(3));
-- ERROR 1062: Duplicate entry
```

애플리케이션에서는 이 예외를 잡아 첫 번째 응답을 그대로 돌려준다.

## 자주 깨지는 패턴

- **status 컬럼만 두고 이력 테이블이 없다**: 상태가 어떻게 변했는지 추적이 안 된다. `order_status_history(order_id, from_status, to_status, changed_at, reason)` 테이블을 같은 트랜잭션에서 같이 쓰는 걸 권한다.
- **PG webhook 처리에 락을 안 잡는다**: 같은 webhook이 두 번 와서 두 번 적립금이 깎인다.
- **취소와 환불을 같은 상태로 묶는다**: "취소했지만 환불은 아직"이라는 중간 상태를 못 표현한다. `CANCELED → REFUNDED` 분리.
- **트랜잭션 안에서 외부 HTTP 호출**: DB 락이 외부 응답 시간만큼 잡힌다.
- **이벤트 발행을 트랜잭션 commit 전에 한다**: DB 롤백되어도 이벤트는 나간다. Outbox로 해결.
- **유니크 키 없이 "코드로 중복 검사"**: 동시성에서 그대로 깨진다.

## 면접 답변 프레이밍 (시니어 백엔드 톤)

> "주문 처리 시스템 어떻게 설계할 건가요?"

답변 골격(40\~60초):

1. 주문을 유한 상태 머신으로 모델링한다. 상태와 허용 전이를 enum + 도메인 메서드에 가둔다.
2. 외부 진입점(결제 콜백, 사용자 요청)은 모두 idempotency-key + 유니크 제약으로 중복 차단한다.
3. 상태를 바꾸는 트랜잭션은 짧게 잡고, 같은 row에 대한 동시 수정은 `SELECT ... FOR UPDATE` 또는 조건부 update(`WHERE status = ?`)로 막는다.
4. 외부 시스템 호출(매장 POS, 알림)은 transactional outbox로 분리한다. 컨슈머는 멱등 처리한다.
5. 결제와 환불은 PG가 진실의 원천이고 우리 DB는 사본이다. webhook 멱등 처리, `refunded_amount <= paid_amount` 불변 조건을 강제한다.
6. 운영 관점에서 상태 변경 이력 테이블과 outbox 미발송 카운트를 모니터링한다.

> "재시도가 두 번 들어왔는데 결제가 두 번 되면요?"

→ idempotency-key 유니크 제약으로 막는다. 키 충돌 시 첫 번째 처리 결과를 그대로 응답한다. PG 측에서도 동일 `merchant_uid`로 중복 결제 차단을 켠다. 우리 쪽 outbox/이벤트 컨슈머도 `event_id` 기반 dedup을 둔다.

> "결제는 됐는데 매장 접수가 실패하면요?"

→ 결제 트랜잭션 안에서 outbox에 "POS 접수 요청" 이벤트만 적재하고 커밋한다. publisher가 비동기로 POS를 호출한다. 일정 횟수 실패 시 알림 + 운영 대시보드에 노출하고, 정책에 따라 자동 환불 또는 수동 개입으로 보낸다. 사용자에게는 "접수 지연 중" 상태를 표시한다.

> "MySQL 격리 수준은 뭐 쓰세요?"

→ 기본 `REPEATABLE READ`를 그대로 쓰되, 상태 전이 시점에서는 `SELECT ... FOR UPDATE`로 락을 잡는다. 일반 SELECT는 MVCC 스냅샷이라 다른 트랜잭션의 커밋이 안 보일 수 있다는 점을 인지하고, 검증-갱신 패턴은 락 또는 조건부 update로 처리한다.

> "주문 상태가 잘못된 채로 운영에 나갔어요. 어떻게 복구하나요?"

→ 1) status_history로 잘못된 전이 시점을 특정한다. 2) 영향받은 주문 집합을 식별한다. 3) outbox/이벤트 측 부수 효과 보정 가능 여부를 본다(환불 가능, 적립 회수 가능 등). 4) 보정 스크립트는 항상 dry-run → 샘플 → 전체 순으로 단계화한다. 5) 사후엔 같은 잘못된 전이가 다시 못 일어나도록 도메인 검증 또는 DB CHECK 제약을 추가한다.

## 체크리스트

- [ ] 주문 상태 enum과 허용 전이를 한 곳에 모아두었는가
- [ ] 상태 전이를 도메인 메서드로 강제하고, 직접 `setStatus`를 못 부르게 막았는가
- [ ] 모든 외부 진입점(결제, 사용자 요청, webhook)에 idempotency-key 또는 동등한 유니크 제약이 있는가
- [ ] 상태 전이 트랜잭션은 `SELECT ... FOR UPDATE` 또는 조건부 update로 동시성 안전한가
- [ ] 외부 시스템 호출은 트랜잭션 밖(outbox 등)에서 처리되는가
- [ ] outbox와 컨슈머가 멱등성을 갖추고 있는가
- [ ] `paid_amount`, `refunded_amount` 같은 금액 불변 조건이 도메인 또는 DB CHECK로 강제되는가
- [ ] 상태 변경 이력이 별도 테이블로 남는가
- [ ] PG webhook 중복 수신을 `pg_tid` 유니크로 차단하는가
- [ ] 데드락 가능 경로를 식별하고 락 획득 순서를 통일했는가
- [ ] 운영에서 outbox 미발송, 환불 실패, 상태 불일치를 감지하는 알람이 있는가
- [ ] 면접에서 위 답변 6가지 골격을 60초 안에 막힘없이 말할 수 있는가
