# [초안] 커머스 주문 상태와 데이터 정합성 기본기 — CJ푸드빌 면접 대비

## 왜 중요한가

커머스/외식 도메인 백엔드에서 "주문이 두 번 들어갔다", "결제는 됐는데 접수가 안 됐다", "취소했는데 매장에는 조리 지시가 내려갔다" 같은 사고는 거의 전부 **주문 상태 머신과 데이터 정합성 기본기**의 문제다. 신기술이 아니라 트랜잭션, 락, 멱등성, 상태 전이 검증이 무너졌을 때 발생한다.

CJ푸드빌처럼 매장 POS, 키오스크, 모바일 앱, 배달 플랫폼이 동시에 같은 주문 도메인을 건드리는 환경에서는 다음 세 가지가 시니어 백엔드의 기본기로 검증된다.

1. 주문 라이프사이클을 **유한 상태 머신**(FSM)으로 모델링할 수 있는가
2. 모바일 재시도와 네트워크 단절을 견디는 **멱등성**과 **중복 차단**을 설계할 수 있는가
3. 동시성/트랜잭션/이벤트 발행을 **하나의 일관된 경계** 안에서 다룰 수 있는가

면접에서 "주문 처리 어떻게 만들어요?"라는 질문이 들어오면, 시니어와 주니어를 가르는 선은 결국 이 세 줄이다. 이 문서는 그 기본기를 한 번에 정리한다.

본 문서는 **기본기 허브 역할**이다. 상태머신 운영 디테일은 [F&B 주문/매장/픽업 상태머신](./fnb-order-store-pickup-state-machine.md), 결제 멱등성은 [결제 도메인 멱등성과 트랜잭션 재시도](./payment-idempotency-transaction-basics.md), 도메인 분리·Outbox는 [e-Commerce 주문·결제 도메인 모델링](./ecommerce-order-payment-domain-modeling.md), 쿠폰/프로모션 동시성은 [쿠폰 프로모션 동시성 기본기](./coupon-promotion-concurrency-basics.md), Outbox 패턴 자체는 [Outbox Pattern 심화](./distributed-transaction-outbox-pattern.md)를 참고한다.

## 핵심 개념 1 — 주문 상태를 유한 상태 머신으로 본다

주문은 "필드 몇 개 가진 row"가 아니라 **상태**(state)와 **이벤트**(event)의 조합이다. 외식/커머스에서 자주 쓰는 최소 상태 집합은 다음과 같다.

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

```text
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

### F&B/픽업 도메인에서 자주 깨지는 불변 조건 (CJ푸드빌 관점)

| 분류 | 불변 조건 | 깨졌을 때 사고 모습 |
|------|----------|--------------------|
| 상태 | `ACCEPTED` 진입 시점에 결제 1건 이상이 `APPROVED` | "매장 접수 됐는데 결제 미인증" 매출 누락 |
| 상태 | `PREPARING → CANCELED` 직전 매장 동의 플래그 필수 | 조리 중 일방 취소로 매장과 분쟁 |
| 금액 | `total_amount = sum(order_item.qty * price) - discount` | 영수증 금액 불일치, PG 환불 시 회계 충돌 |
| 금액 | `refunded_amount ≤ paid_amount` (CHECK 강제) | 음수 결제 잔액, 정산 오류 |
| 금액 | `paid_amount = sum(payment WHERE status='APPROVED')` | "결제 OK인데 주문 total은 0" |
| 시간 | `pickup_at ≥ ready_at ≥ accepted_at ≥ paid_at` | 픽업 알림이 결제 전 발송 |
| 멀티 결제 | 포인트 + 카드 분할 결제 시 `sum(method_amount) = total_amount` | 부분 환불 시 어느 수단부터 회수할지 불일치 |
| 픽업 | `READY` 후 N분 무수령 시 `NO_SHOW` 전이만 허용 (재조리 불가) | 식어버린 음식 재배출, CS 폭주 |
| 멤버십 | 적립은 `COMPLETED` 시점에만 1회 (`event_id` dedup) | 같은 주문에 CJ ONE 포인트 2배 적립 |

면접에서 가산점을 받는 포인트는 **"어디에 어떤 책임을 두는지"** 를 명확히 답하는 것이다. 같은 불변 조건이 여러 층에 흩어지면 우회 경로로 깨지고, 한 층에만 두면 운영 환경에서 우회당한다. 다층 방어가 정석이다.

| 책임 층 | 다루는 불변 조건 | 도구 |
|---------|------------------|------|
| DB 스키마 | 구조적 정합성 (절대 깨지면 안 되는 것) | `NOT NULL`, `CHECK`, `UNIQUE`, FK |
| 도메인 객체 | 상태 전이 / 금액 식 / 시간 순서 | `canTransitTo`, 생성자 단계 assertion |
| 애플리케이션 서비스 | 동시성 (같은 row 동시 수정 방어) | `SELECT ... FOR UPDATE`, 조건부 update |
| 이벤트 핸들러 | 결과적 일관성 (외부 시스템 동기화) | Outbox + 컨슈머 dedup |
| 모니터링 | "이미 깨진 row" 사후 탐지 | history 스캔 알람, 정합성 배치 |

도메인 메서드 안에서 불변 조건을 모아서 강제하는 패턴은 다음과 같다. **상태 전이 + 금액 식 + 시간 순서**를 한 메서드에서 같이 검증한다.

```java
public void markAccepted(LocalDateTime now) {
    if (!status.canTransitTo(OrderStatus.ACCEPTED)) {
        throw new IllegalOrderTransitionException(status, OrderStatus.ACCEPTED);
    }
    if (paidAmount() <= 0 || paidAmount() < totalAmount) {
        throw new InvariantViolation("ACCEPTED 진입 시 결제 미충족");
    }
    if (paidAt == null || now.isBefore(paidAt)) {
        throw new InvariantViolation("시간 역전: now < paid_at");
    }
    this.status = OrderStatus.ACCEPTED;
    this.acceptedAt = now;
}
```

DB CHECK는 코드 우회를 막는 마지막 안전망이다. MySQL 8.0+ 기준:

```sql
ALTER TABLE orders
  ADD CONSTRAINT chk_refund_le_paid CHECK (refunded_amount <= paid_amount),
  ADD CONSTRAINT chk_total_nonneg  CHECK (total_amount >= 0);
```

CHECK는 마이그레이션 비용이 있고 한 번 추가하면 운영 보정도 같은 제약을 만족시켜야 한다. 그래서 **도메인 검증을 1차, DB CHECK를 2차 안전망**으로 두는 게 일반적이다.

## 핵심 개념 3 — 중복 요청과 모바일 재시도 (멱등성)

모바일 환경에서는 사용자가 결제 버튼을 두 번 누르거나, 네트워크가 끊긴 상태에서 앱이 자동 재시도한다. 서버는 같은 의도가 두 번 들어와도 결과가 한 번만 일어나도록 만들어야 한다.

### 모바일 환경에서 중복이 들어오는 실제 경로

| 시나리오 | 어떻게 두 번 들어오나 | 서버가 보는 모습 |
|---------|---------------------|-----------------|
| 더블 탭 | 결제 버튼 0.3초 안에 두 번 클릭 | 동시에 동일 페이로드 2건 |
| 네트워크 타임아웃 후 재시도 | 응답 못 받고 클라이언트가 자동 재요청 | 첫 요청은 서버에서 정상 처리, 두 번째 요청은 동일 키로 진입 |
| 백그라운드 진입 후 복귀 | OS가 앱을 freeze → resume 시 진행 중이던 호출 재발사 | 5\~60초 후 같은 요청 도착 |
| 앱 강제 종료 + 재진입 | 결제 진행 중 앱 kill, 재실행 후 "결제 진행 중" 화면에서 retry | 클라이언트 retry 헤더 동일 |
| Push notification 딥링크 | "결제 완료" push 중복 수신 → 두 번 클릭 시 "주문 확정" API 두 번 | 동일 user, 동일 order_id에 confirm 2회 |
| PG webhook 재발송 | PG가 응답 timeout 처리 후 재전송 정책 (보통 5\~30분 단위) | 같은 `pg_tid`로 callback 다회 |
| 매장 POS 재동기화 | POS가 네트워크 복귀 후 미동기 주문 일괄 전송 | 동일 주문에 `ACCEPTED` 이벤트 N회 |

각 경로마다 멱등성 키의 발급 주체가 다르다는 점이 핵심이다 — 클라이언트가 발급(Idempotency-Key), PG가 발급(pg_tid), POS가 발급(pos_tx_id). 진입점마다 어느 키로 dedup할지 정확히 매핑해야 한다.

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

### 동시 첫 요청 경합과 in-flight 처리

진짜 까다로운 케이스는 "같은 키로 두 번째 요청이 도착했는데 **첫 번째 요청이 아직 처리 중**"인 상황이다. 두 가지 정책 중 명시적으로 하나를 골라야 한다.

```java
@Transactional
public OrderResponse placeOrder(String idemKey, PlaceOrderCommand cmd) {
    // 1) 행 락으로 처리 진행 여부 확인 — INSERT 시 status='IN_FLIGHT'
    try {
        requestLogRepo.save(RequestLog.inFlight(idemKey, cmd));
    } catch (DataIntegrityViolationException dup) {
        RequestLog existing = requestLogRepo.findByIdForUpdate(idemKey).orElseThrow();
        if (existing.isInFlight()) {
            // 정책 A: 409 Conflict — "처리 중, 다시 시도 마세요"
            throw new RequestInFlightException(idemKey);
            // 정책 B: 첫 처리 완료까지 대기 (락 잡힌 채로 다음 줄 실행)
        }
        return existing.replay();   // 완료된 응답 그대로 반환
    }
    Order order = orderService.create(cmd);
    requestLogRepo.markCompleted(idemKey, OrderResponse.of(order));
    return OrderResponse.of(order);
}
```

정책 A(409)는 모바일 사용자 입장에서 "잠시 기다렸다 새로고침"으로 자연스럽다. 정책 B(대기)는 응답 일관성은 좋지만 락 시간이 길어진다. 결제처럼 짧은 작업은 B, 매장 POS 비동기 호출처럼 긴 작업은 A가 안전하다.

### Idempotency-Key TTL 정책

idempotency 테이블은 무한정 보관하면 인덱스 비대로 성능이 떨어진다. 동시에 너무 짧게 잡으면 "지연된 재시도"가 dedup을 우회한다.

| 진입점 | TTL 권장 | 이유 |
|--------|---------|------|
| 사용자 결제 요청 | 24\~72시간 | 모바일 백그라운드 복귀까지 여유 |
| PG webhook | **30일 이상** | PG 재시도 정책이 길고 정산 검증과 매칭 필요 |
| 매장 POS 동기화 | 7일 | POS 오프라인 복구 + 영업일 단위 |
| Push 딥링크 confirm | 1\~2시간 | 사용자 의도가 살아있을 시간 |

만료 row는 별도 archive 테이블로 이동(원본 테이블은 보관 비용 큼). 결제 정산·CS 대응을 위해 archive는 90일+ 보존.

### 결제·외부 시스템에서의 키 분리

같은 주문이라도 진입점이 다르면 키도 다르다. 한 키로 모든 layer를 dedup하려고 하면 broker 한 군데가 무너지면 전체가 무너진다.

- **클라이언트 → 우리 API**: `Idempotency-Key` 헤더 (UUIDv4)
- **우리 API → PG**: `merchant_uid` (우리가 발급, 동일 주문에 대해 단일)
- **PG → 우리 webhook**: `pg_tid` (PG 발급, webhook dedup 키)
- **우리 → Kafka outbox**: `event_id` (UUID, 컨슈머 dedup 키)
- **우리 → POS**: `pos_tx_id` (우리 발급, POS 재시도 dedup 키)

각 키마다 유니크 제약을 둔다. 면접에서 "어디서 어떻게 막아요?" 질문이 들어왔을 때 위 5개 진입점을 한 번에 짚을 수 있으면 시니어 답변이다.

결제 단계 멱등성(특히 PG 타임아웃 = "결과 미상" 처리)은 별 문서가 더 깊게 다룬다. [결제 도메인 멱등성과 트랜잭션 재시도 기본기](./payment-idempotency-transaction-basics.md) 참조.

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

#### RC vs RR 빠른 비교 (면접용)

| 항목 | READ COMMITTED | REPEATABLE READ (MySQL 기본) |
|------|---------------|------------------------------|
| 같은 트랜잭션 내 재조회 | 다른 결과 가능(non-repeatable read) | 같은 결과 (스냅샷) |
| Phantom row (범위 SELECT) | 발생 가능 | InnoDB는 gap lock으로 방어 가능 |
| Gap lock | **거의 없음** | `SELECT ... FOR UPDATE` 시 범위에 gap lock |
| 대량 update 락 범위 | 좁음 (행 단위) | 넓음 (gap + next-key) |
| 데드락 가능성 | 낮음 | gap lock 인한 데드락이 흔함 |
| 추천 용례 | OLTP 단순 read/write, MySQL Aurora 기본 | 복합 검증 + range 일관성 필요 |

상태 전이 + 범위 일관성이 필요한 주문 도메인은 RR이 자연스럽다. 반면 단순 status update만 많고 deadlock이 잦으면 RC + 조건부 update(`WHERE status = ?`) 조합이 운영에 부담이 적다. **격리 수준은 "성능 vs 일관성 + 데드락 비용"의 trade-off로 답한다.**

#### Gap lock과 Next-Key lock — 데드락 트랩

`SELECT ... FOR UPDATE`로 **인덱스 범위**를 잠그면 RR에서는 빈 공간(gap)까지 잠근다.

```sql
-- 세션 A
START TRANSACTION;
SELECT * FROM orders WHERE user_id = 100 FOR UPDATE;
-- user_id=100 row뿐 아니라 그 인덱스 범위 gap까지 잠금

-- 세션 B
INSERT INTO orders (user_id, ...) VALUES (100, ...);   -- 블록
```

문제는 두 세션이 서로 다른 인덱스 범위를 다른 순서로 잠글 때다. **항상 같은 순서로 락을 잡는다**는 규율이 그래서 나온다. 실전 패턴:

- 여러 주문을 한 트랜잭션에서 잠가야 하면 `order_id ASC`로 정렬 후 잠근다.
- 같은 user의 여러 row를 잠가야 하면 `user_id`에 단일 락 + 각 order row는 `id` 순서로.
- 인덱스에 없는 컬럼으로 `WHERE`를 걸면 InnoDB가 테이블 전체에 락을 거는 사고가 난다 — 락 쿼리는 **항상 인덱스 잘 타는 컬럼**으로.

#### 흔한 데드락 패턴 3개

```text
[패턴 1] 사용자 + 매장 동시 취소·접수
  세션 A: lock(order) → call(POS)
  세션 B: lock(POS row) → lock(order)
  → 두 세션이 서로의 락 해제 대기

[패턴 2] outbox + orders 락 순서 역전
  세션 A: lock(orders) → insert(outbox)
  세션 B: lock(outbox) → update(orders)
  → 같은 트랜잭션 안에서 항상 (orders → outbox) 순서로 고정

[패턴 3] 인덱스 안 타는 update가 잡는 광범위 락
  UPDATE orders SET status='CANCELED' WHERE user_id=? AND status='PAID'
  → user_id 인덱스 없으면 테이블 락. 다른 트랜잭션 전부 대기
```

데드락이 생기면 InnoDB가 한 트랜잭션을 강제 롤백한다(`ERROR 1213`). 애플리케이션은 **이걸 재시도 가능한 예외**로 보고 1\~3회 백오프 재시도하는 패턴이 일반적이다.

```java
@Retryable(value = DeadlockLoserDataAccessException.class,
           maxAttempts = 3, backoff = @Backoff(delay = 50, multiplier = 2))
@Transactional
public void cancelByUser(Long orderId) { ... }
```

데드락이 자주 보이면 코드 수정 전에 먼저 `SHOW ENGINE INNODB STATUS\G`의 `LATEST DETECTED DEADLOCK` 섹션을 본다. 어떤 두 쿼리가 어떤 락을 서로 기다렸는지가 명확히 나온다.

#### SERIALIZABLE은 거의 안 쓴다

면접에서 "그럼 SERIALIZABLE 쓰면 되지 않냐"는 질문이 따라올 수 있다. 답변 골격:

- 모든 SELECT가 `LOCK IN SHARE MODE`로 변해서 락 경합이 폭발한다.
- 실무에서는 RR + 조건부 update + Outbox 조합이 동일 효과를 더 낮은 비용으로 제공한다.
- SERIALIZABLE은 정산 reconciliation 배치처럼 동시성 0이 보장된 잡에서만 가끔 쓴다.

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

### Publisher 워커 구현 패턴

면접에서 "Outbox 어떻게 발행해요?"가 따라오면, 단순 "스케줄러가 polling 한다"로 끝내지 않는다. 실제로 운영하면 다음 3가지가 문제다.

1. **여러 publisher 인스턴스가 같은 row를 동시에 집어가지 않게**
2. **순서가 중요한 이벤트끼리는 같은 파티션으로 가게**
3. **발송 후 DB 업데이트 사이에 죽으면 어떻게 되는지**

#### 1) 워커 동시 진입 방지 — `SKIP LOCKED`

MySQL 8.0+ / PostgreSQL 9.5+에서 `FOR UPDATE SKIP LOCKED`로 worker 간 row를 분배한다. 같은 row를 두 worker가 동시에 잡지 않는다.

```sql
SELECT id, aggregate_id, type, payload
  FROM outbox
 WHERE sent_at IS NULL
 ORDER BY id
 LIMIT 100
 FOR UPDATE SKIP LOCKED;
```

이 쿼리로 100건을 잡고, Kafka에 전송 후 `UPDATE outbox SET sent_at = NOW() WHERE id IN (...)`로 마킹한다.

#### 2) 순서 보존 — `aggregate_id`를 Kafka partition key로

같은 주문(`aggregate_id`)의 이벤트는 항상 같은 partition으로 가야 컨슈머가 `OrderPaid → OrderAccepted` 순서를 보장 받는다.

```java
ProducerRecord<String, byte[]> record = new ProducerRecord<>(
    "order-events",
    String.valueOf(msg.getAggregateId()),   // partition key
    msg.getPayload()
);
producer.send(record);
```

순서가 무조건 필요하지 않다면 partition key를 안 줘도 된다. 운영 관점에서 보통 `aggregate_id` 정도면 충분하다.

#### 3) 발송 후 죽었을 때 — at-least-once 수용

publisher가 "Kafka 전송 성공 → `sent_at` update 직전" 사이에 죽으면 같은 이벤트가 두 번 발송된다. 이건 피할 수 없다 — **컨슈머가 멱등하다는 가정 위에 시스템 전체를 짠다**.

컨슈머 측 dedup 테이블:

```sql
CREATE TABLE inbox (
    event_id   VARCHAR(64) PRIMARY KEY,
    consumer   VARCHAR(64) NOT NULL,
    handled_at DATETIME(3) NOT NULL
) ENGINE=InnoDB;
```

컨슈머 핸들러 첫 줄에서 `INSERT INTO inbox`가 PK 충돌이면 skip한다.

### Outbox 운영 모니터링

운영에 들어가면 outbox는 빠르게 "감지 못한 사일런트 장애"의 1순위 후보가 된다. 다음 4개 메트릭은 dashboard 필수.

| 메트릭 | 임계 | 의미 |
|--------|------|------|
| `count(*) WHERE sent_at IS NULL` | 임계치(예: 1,000건) 초과 | publisher 죽었거나 Kafka 장애 |
| `now() - min(created_at) WHERE sent_at IS NULL` | 5분 초과 | 미발송 lag — 사고 직전 |
| `count(*) WHERE retried >= 5` | 1건 이상 | poison message — DLQ로 옮길 대상 |
| publisher loop 1회 처리량 | 평소 대비 -50% | DB 락 / Kafka throttling |

발행 실패가 누적되는 row는 일정 횟수 후 **DLQ outbox**로 옮기고 알람을 띄운다. 무한 재시도 + 다른 이벤트까지 지연시키는 게 가장 위험한 패턴이다.

```sql
CREATE TABLE outbox_dlq (
    id           BIGINT PRIMARY KEY,
    original_id  BIGINT NOT NULL,
    aggregate_id BIGINT NOT NULL,
    type         VARCHAR(64) NOT NULL,
    payload      JSON NOT NULL,
    last_error   TEXT,
    moved_at     DATETIME(3) NOT NULL
);
```

### 발행 시점 — 왜 AFTER_COMMIT인가

후보자 본인 경험과 정확히 매칭되는 질문이다. "왜 `@TransactionalEventListener(AFTER_COMMIT)`인가?"

- `@EventListener`만 쓰면 트랜잭션 commit 전에 핸들러가 돈다 → DB rollback 시에도 이벤트가 나간다.
- `AFTER_COMMIT`은 commit이 성공한 다음에만 핸들러를 트리거 → "DB는 있는데 이벤트는 없다"가 발생할 가능성은 있어도, "DB는 없는데 이벤트는 나갔다"는 없다.
- `REQUIRES_NEW`로 발송 실패를 별도 트랜잭션에 기록하는 이유는 **원본 트랜잭션이 이미 commit된 상태**라 같은 트랜잭션에 실패 기록을 쓸 수 없기 때문이다.

이 두 조합을 면접에서 1분 안에 설명할 수 있어야 한다.

Outbox 그 자체의 변형/CDC/Saga 결합은 [Outbox Pattern 심화](./distributed-transaction-outbox-pattern.md)와 [Outbox/Inbox Pattern](./outbox-inbox-pattern.md)에서 더 깊게 다룬다.

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

## 장애 복구 운영 플레이북

운영 사고는 "잘못된 상태가 이미 DB에 박혀서 트래픽을 받는 중"이라는 시점부터 시작된다. 코드 수정만으로 끝나지 않고 **이미 잘못된 row**를 어떻게 되돌릴지가 본격적인 일이다. 면접에서 "운영 사고 어떻게 복구해요?"라는 질문은 사실상 이 플레이북을 보고 있다.

### 시간순 대응 체크리스트 (전이 사고 기준)

| 시간대 | 해야 할 일 | 산출물 |
|--------|------------|--------|
| 0\~5분 | 사고 확정. 알람 채널에서 트래픽 영향 여부 확인 | 사고 티켓 오픈 |
| 5\~15분 | **트래픽 차단** — 잘못된 경로(특정 API / feature flag)를 즉시 off | rollback PR 또는 flag off 로그 |
| 15\~30분 | `order_status_history` 스캔으로 **영향 집합·시간 구간** 추정 | dry-run 쿼리, 영향 row 수 |
| 30\~60분 | **부수 효과 점검** — PG 결제, POS 조리지시, 적립 dedup 상태 | 외부 시스템 상태 표 |
| 1\~2시간 | **샘플 보정** (10\~20건) — history 갱신까지 같은 트랜잭션 | 샘플 보정 로그 |
| 2\~6시간 | **전체 보정** — 청크 단위, lag 모니터링하면서 | 보정 완료 카운트 |
| 6\~24시간 | 사용자 알림 정정, CS 매뉴얼 배포 | CS 가이드 |
| 24\~72시간 | postmortem 초안 + 재발 방지 PR | postmortem 문서 |

이 표를 외워두는 게 면접 가산점이다. "사고 났을 때 첫 5분에 뭐 해요?"는 시니어 백엔드에 자주 들어오는 질문이다 — **트래픽 차단이 코드 수정보다 먼저**라는 답이 핵심.

### 상태 변경 이력 테이블

복구의 출발점은 "언제, 어디서, 무엇이, 왜" 바뀌었는지가 남아 있는가다. 모든 상태 전이가 같은 트랜잭션에서 history에 적재되도록 한다.

```sql
CREATE TABLE order_status_history (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id     BIGINT       NOT NULL,
    from_status  VARCHAR(20)  NOT NULL,
    to_status    VARCHAR(20)  NOT NULL,
    reason       VARCHAR(64)  NOT NULL,
    actor        VARCHAR(64)  NOT NULL,   -- user / pos / pg-webhook / scheduler / admin
    trace_id     VARCHAR(64)  NOT NULL,
    changed_at   DATETIME(3)  NOT NULL,
    INDEX idx_order_time (order_id, changed_at),
    INDEX idx_to_status_time (to_status, changed_at)
) ENGINE=InnoDB;
```

도메인 메서드에서 상태가 바뀔 때마다 항상 history 한 줄을 적재한다. 별도 트랜잭션이 아니라 **같은 트랜잭션**이라는 점이 중요하다 — 그래야 "DB의 status는 PAID인데 history엔 PAID가 없다"가 발생하지 않는다.

### 영향 범위 식별 쿼리

사고가 터지면 가장 먼저 **얼마나 퍼졌는지** 본다. 잘못된 전이를 만든 코드가 며칠 동안 돌았는지에 따라 보정 단위가 다르다.

```sql
-- 사고 의심 구간에서 잘못된 to_status 전이가 일어난 주문 집합
SELECT order_id, changed_at, from_status, to_status, actor, trace_id
  FROM order_status_history
 WHERE changed_at BETWEEN '2026-05-15 10:00:00' AND '2026-05-15 12:30:00'
   AND to_status = 'ACCEPTED'
   AND from_status NOT IN ('PAID');   -- 정상 진입 경로가 아닌 케이스
```

이 쿼리 자체가 **체크 제약을 안 걸어둔 경우 사고가 어떻게 생기는지** 를 그대로 보여준다. 사후엔 DB CHECK 또는 도메인 검증으로 같은 조합이 못 들어가게 막는다.

### 보정 스크립트 단계화

영향받은 주문 집합을 그대로 update 하지 않는다. 항상 세 단계로 나눈다.

1. **dry-run** — `SELECT`만으로 보정 대상과 보정 후 기대 상태를 출력. 운영에 변경을 일으키지 않는다.
2. **샘플 보정** — 영향 집합 중 10\~20건만 별도 트랜잭션으로 보정. 결과를 history와 외부 시스템(매장 POS / PG / 알림)에서 검증.
3. **전체 보정** — 청크 단위(예: 500건씩) 트랜잭션 분리, 각 청크 사이에 짧은 sleep과 lag 모니터링. 중간 실패 시 어디까지 처리됐는지 history로 추적 가능해야 한다.

```sql
-- 1) dry-run: 보정 후 어떤 상태가 될지만 확인
SELECT o.id, o.status AS current_status, 'CANCELED' AS would_be
  FROM orders o
 WHERE o.id IN (...영향 집합...)
   AND o.status = 'ACCEPTED';

-- 2) 샘플 보정: 한 트랜잭션에서 update + history 적재
START TRANSACTION;
UPDATE orders
   SET status = 'CANCELED', updated_at = NOW(3)
 WHERE id IN (1001, 1002, 1003)
   AND status = 'ACCEPTED';
INSERT INTO order_status_history (order_id, from_status, to_status, reason, actor, trace_id, changed_at)
SELECT id, 'ACCEPTED', 'CANCELED', 'incident-2026-05-15', 'ops-admin', 'recover-batch-1', NOW(3)
  FROM orders WHERE id IN (1001, 1002, 1003);
COMMIT;
```

스크립트 본체는 보통 별도 잡(`Spring Batch`, 운영 콘솔에서 호출하는 admin API)으로 만들고 **항상 dry-run 모드를 기본값**으로 둔다. `--apply` 플래그 없이는 절대 update 하지 않는다.

### 외부 부수 효과 보정

DB만 되돌린다고 사고가 끝나지 않는다. 같이 점검할 외부 효과는 다음과 같다.

- **PG 결제** — 잘못 승인된 결제는 PG API로 환불(`refunded_amount += amount`). 부분 환불 모델이라야 안전하다.
- **매장 POS** — 이미 조리지시가 들어갔다면 매장에 별도 연락. 자동 취소가 안 되는 경우가 많아 운영팀 콜이 끼는 게 정상이다.
- **포인트/쿠폰 적립** — `event_id` 기반 dedup 테이블에서 이미 적립된 케이스를 식별, 회수 가능한 정책일 때만 회수. 회수 불가면 사후 보상 정책으로.
- **사용자 알림** — 이미 "주문 접수 완료" 알림이 나갔다면 정정 알림 + CS 매뉴얼.

각 효과별로 "보정 가능 / 부분 보정 / 보정 불가"를 미리 표로 정리해두면 사고 시점에 의사결정이 빠르다.

### 모니터링 알람

사고를 줄이려면 잘못된 전이가 "사람이 발견하기 전에" 알람으로 잡혀야 한다. 다음 네 가지를 dashboard + 알람으로 운영한다.

- `order_status_history`에서 **허용되지 않은 from→to 조합** 카운트 (정상은 0이어야 한다)
- `outbox`의 미발송 row 수 — 일정 임계치(예: 100건) 이상이면 publisher 또는 컨슈머 문제
- PG webhook 중복 수신율 — 비정상적으로 높아지면 idempotency 문제
- `paid_amount` vs `payment.amount` 합 불일치 row 수 — 결제 정합성 깨짐

### 사후 — 같은 사고를 다시 못 일으키게

복구가 끝나면 반드시 **이 사고가 다시 못 일어나도록** 코드/DB/모니터링 중 한 곳을 막는다. 가장 효과적인 순서:

1. 도메인 검증 추가 (`canTransitTo`에 누락된 케이스) — 코드 한 줄로 막힌다면 그게 1순위
2. DB CHECK 또는 trigger — 마이그레이션이 무겁지만 코드 우회를 막는다
3. 모니터링/알람 — 위 4가지 메트릭이 빠져 있었다면 같은 사고가 한 번 더 일어나기 전에 알람으로 잡힌다

postmortem 문서에는 "재발 방지" 항목 옆에 **PR 번호 또는 알람 ID**를 같이 적어두는 게 좋다. 액션이 실제로 들어갔는지 추적 가능해진다.

## 면접 답변 프레이밍 (시니어 백엔드 톤)

### "주문 처리 시스템 어떻게 설계할 건가요?"

답변 골격(40\~60초):

1. 주문을 유한 상태 머신으로 모델링한다. 상태와 허용 전이를 enum + 도메인 메서드에 가둔다.
2. 외부 진입점(결제 콜백, 사용자 요청)은 모두 idempotency-key + 유니크 제약으로 중복 차단한다.
3. 상태를 바꾸는 트랜잭션은 짧게 잡고, 같은 row에 대한 동시 수정은 `SELECT ... FOR UPDATE` 또는 조건부 update(`WHERE status = ?`)로 막는다.
4. 외부 시스템 호출(매장 POS, 알림)은 transactional outbox로 분리한다. 컨슈머는 멱등 처리한다.
5. 결제와 환불은 PG가 진실의 원천이고 우리 DB는 사본이다. webhook 멱등 처리, `refunded_amount <= paid_amount` 불변 조건을 강제한다.
6. 운영 관점에서 상태 변경 이력 테이블과 outbox 미발송 카운트를 모니터링한다.

### "재시도가 두 번 들어왔는데 결제가 두 번 되면요?"

→ idempotency-key 유니크 제약으로 막는다. 키 충돌 시 첫 번째 처리 결과를 그대로 응답한다. PG 측에서도 동일 `merchant_uid`로 중복 결제 차단을 켠다. 우리 쪽 outbox/이벤트 컨슈머도 `event_id` 기반 dedup을 둔다.

### "결제는 됐는데 매장 접수가 실패하면요?"

→ 결제 트랜잭션 안에서 outbox에 "POS 접수 요청" 이벤트만 적재하고 커밋한다. publisher가 비동기로 POS를 호출한다. 일정 횟수 실패 시 알림 + 운영 대시보드에 노출하고, 정책에 따라 자동 환불 또는 수동 개입으로 보낸다. 사용자에게는 "접수 지연 중" 상태를 표시한다.

### "MySQL 격리 수준은 뭐 쓰세요?"

→ 기본 `REPEATABLE READ`를 그대로 쓰되, 상태 전이 시점에서는 `SELECT ... FOR UPDATE`로 락을 잡는다. 일반 SELECT는 MVCC 스냅샷이라 다른 트랜잭션의 커밋이 안 보일 수 있다는 점을 인지하고, 검증-갱신 패턴은 락 또는 조건부 update로 처리한다.

### "주문 상태가 잘못된 채로 운영에 나갔어요. 어떻게 복구하나요?"

다섯 단계로 답한다.

1. `order_status_history`로 잘못된 전이 시점을 특정한다.
2. 영향받은 주문 집합을 식별한다.
3. outbox/이벤트 측 부수 효과 보정 가능 여부를 본다(환불 가능, 적립 회수 가능 등).
4. 보정 스크립트는 항상 dry-run → 샘플 → 전체 순으로 단계화한다.
5. 사후엔 같은 잘못된 전이가 다시 못 일어나도록 도메인 검증 또는 DB CHECK 제약을 추가한다.

## 후보자 경험을 주문 도메인 언어로 번역하기

면접관이 "이런 거 다뤄보셨어요?"라고 물을 때 대답을 추상으로 두지 말고 본인의 실제 경험을 도메인 용어로 옮긴다.

### Kafka Transactional Outbox 운영 경험

> 슬롯 도메인에서 핵심 API의 동기/비동기 후처리를 분리할 때 Kafka 발행이 DB 커밋 전에 나가는 사고가 무서워서 `@TransactionalEventListener(AFTER_COMMIT)` 기반 Outbox를 깔았습니다. 발행 실패 시 `Propagation.REQUIRES_NEW`로 실패 메시지를 별도 트랜잭션에 저장하고 스케줄러가 재발행하는 구조였고, traceId를 메시지·실패 테이블에 같이 박아 사후 추적이 가능하게 했습니다. 주문 도메인으로 옮기면 그대로 "주문 상태 변경 + outbox 적재가 같은 트랜잭션, POS/알림/적립은 별도 publisher" 구조로 매칭됩니다.

### RabbitMQ Fanout 다중 서버 캐시 정합성 경험

> 정적 설정 데이터를 다중 서버 인메모리에 캐싱하던 환경에서, 어드민 수정 시 서버 간 정합성이 깨지고 갱신 중 NPE가 났습니다. Hibernate `PostCommitUpdateEventListener` → RabbitMQ Fanout으로 전 서버에 무효화 신호를 뿌리고, 갱신 구간은 `StampedLock` writeLock으로 보호, 조회는 `tryReadLock(2.5s)`로 막혔습니다. 주문 도메인의 매장/메뉴/프로모션 정책 캐시도 같은 패턴으로 풉니다.

### StampedLock 정적 데이터 동시성 경험

> 갱신 빈도는 낮고 조회가 압도적인 정적 데이터에서 `synchronized`나 `ReentrantReadWriteLock`로는 reader가 너무 자주 막혔습니다. `StampedLock` + optimistic read로 갱신 없을 때는 락 없이 흐르게 만들었고, writer 진입 시점에만 `tryWriteLock`/타임아웃을 박았습니다. 주문 라우팅에서 매장 메타데이터를 매 요청 조회한다면 동일한 패턴이 적합합니다.

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
- [ ] 본인의 Outbox / RabbitMQ Fanout / StampedLock 경험을 주문 도메인 언어로 30초 안에 번역할 수 있는가

## 관련

- [F&B 주문/매장/픽업 상태머신 설계](./fnb-order-store-pickup-state-machine.md) — Store Pickup 시나리오 중심 상태머신 운영 디테일
- [결제 도메인 멱등성과 트랜잭션 재시도 기본기](./payment-idempotency-transaction-basics.md) — 결제 멱등성, PG 타임아웃, reconciliation
- [e-Commerce 주문·결제 도메인 모델링](./ecommerce-order-payment-domain-modeling.md) — Order / Payment / Coupon / Promotion 도메인 경계 분리
- [쿠폰 프로모션 동시성 기본기](./coupon-promotion-concurrency-basics.md) — 쿠폰 중복 사용 / 선착순 / 분산락
- [Outbox Pattern 심화](./distributed-transaction-outbox-pattern.md) — CDC, 발행 순서, Saga 결합
- [Outbox/Inbox Pattern](./outbox-inbox-pattern.md) — 컨슈머 측 멱등성과 inbox 테이블

## 2026-05-19 CJ푸드빌 부트캠프 보강 — 주문 정합성 답변 프레임

면접에서 주문 정합성을 설명할 때는 “상태 전이 + 멱등키 + 락/격리수준 + 이벤트 발행 + 복구”를 한 문장으로 묶어 말한다. 예를 들어 “모바일 앱 재시도로 동일 주문 요청이 여러 번 들어와도 `order_request_id` unique key로 한 번만 생성하고, 상태 전이는 현재 상태를 조건으로 둔 compare-and-set update로 막으며, 결제 성공 후 POS 접수 이벤트는 Outbox에 남겨 재처리합니다”처럼 답하면 도메인과 기본기가 함께 드러난다.

실전 점검 순서는 다음과 같다.

- 주문 생성 API는 클라이언트 재시도에 대비해 `member_id + order_request_id` unique constraint를 둔다.
- 상태 변경은 `where order_id = ? and status in (...)` 조건부 update로 허용 전이만 통과시킨다.
- 피크타임 중복 클릭은 DB unique constraint를 최후 방어선으로 두고, 애플리케이션 락만 신뢰하지 않는다.
- 결제 성공 후 POS 접수/알림/쿠폰 차감 이벤트는 같은 트랜잭션에서 Outbox row로 저장한다.
- Outbox 발행 실패는 주문 실패가 아니라 “후속 이벤트 지연”으로 분리해 재처리 큐와 운영 알림으로 다룬다.
- 복구 런북에는 `PAID`인데 `ACCEPTED`가 아닌 주문, `CANCELED`인데 환불 이벤트가 없는 주문, 쿠폰 복구 누락 주문을 별도 쿼리로 둔다.

답변의 핵심은 “정합성은 코드 if문이 아니라 DB 제약, 트랜잭션 경계, 상태 전이, 재처리 설계가 같이 보장한다”는 관점이다.
