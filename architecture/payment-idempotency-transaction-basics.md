# [초안] 결제 도메인 멱등성과 트랜잭션 재시도 기본기

## 왜 중요한가

F&B 커머스나 외식 프랜차이즈 주문 시스템에서 결제는 단순히 "돈이 빠져나갔다"로 끝나는 이벤트가 아니다. 한 번의 사용자 결제 시도 뒤에는 클라이언트 → 우리 서버 → PG사 → 카드사 → 다시 PG사 → 우리 서버 → 클라이언트라는 분산 호출 사슬이 존재하고, 이 사슬 어느 한 구간에서든 네트워크 타임아웃, 커넥션 끊김, 모바일 백그라운드 전환, 재시도 클릭이 일어날 수 있다. 그 결과는 거의 항상 같은 형태의 사고로 모인다. 사용자는 결제가 실패했다고 믿지만 카드사는 승인 처리했고, 우리 DB의 주문 상태는 어중간하게 남아 있다.

CJ푸드빌처럼 빕스, 뚜레쥬르, 더플레이스 같은 다브랜드/다채널을 운영하는 회사에서 이 문제는 더 까다롭다. 키오스크, 모바일 앱, 배달 플랫폼 연동, 매장 POS가 같은 결제 백엔드를 호출하기 때문에 클라이언트별 재시도 패턴이 다르고, 환불/부분취소/주문 변경 시나리오가 자주 발생한다. 한 건의 중복 결제는 컴플레인 한 통으로 끝나지만, 같은 패턴이 점심 피크 30분 동안 누적되면 정산팀과 CS팀이 며칠을 야근해야 한다.

이 문서는 그 사슬을 안전하게 만드는 가장 기초적인 도구 세 가지에 집중한다. **idempotency key, 주문-결제 상태 분리, Outbox 기반 외부 호출**이다. Saga나 분산 트랜잭션 같은 더 큰 그림은 면접에서 자주 묻지만, 그 답이 설득력 있으려면 결국 이 셋 위에서 설명할 수 있어야 한다.

## 핵심 개념 정리

### 멱등성이란 무엇인가

멱등(idempotent)하다는 것은 같은 요청을 여러 번 보내도 결과가 한 번 보낸 것과 같다는 의미다. HTTP `GET`은 본질적으로 멱등하고 `PUT`/`DELETE`도 의미상 멱등하지만, `POST`는 그렇지 않다. 결제 승인은 거의 언제나 `POST` 호출이고 외부 PG와의 부수효과를 동반한다. 따라서 멱등성은 "공짜로" 따라오지 않고, 우리가 명시적으로 설계해서 보장해야 한다.

핵심 도구는 **idempotency key**다. 클라이언트가 결제 요청을 만들 때 한 번 생성하는 고유 토큰으로, 동일 사용자의 동일 결제 시도임을 식별한다. 서버는 이 키를 본 적이 있다면 이전 처리 결과를 그대로 반환하고, 새 키라면 정상 처리한 뒤 결과를 키와 함께 저장한다. 키의 수명은 보통 24시간 정도, 결제 같은 민감한 영역에서는 7일 이상 보관하는 곳도 많다.

idempotency key를 어디서 만드냐가 첫 갈림길이다. 서버가 만들어 클라이언트에 내려주는 방식(주문 생성 시점에 토큰 발급)이 가장 안정적이다. 클라이언트가 UUID를 직접 만들면 앱 버그로 같은 사용자의 동일 카트에 대해 매번 새 키가 생성되는 사고가 빈번히 일어난다.

### 주문과 결제 상태를 왜 분리하는가

신입 때 가장 흔히 보는 안티패턴은 `Order` 테이블 하나에 `paymentStatus`, `pgTxId`, `paidAmount` 컬럼을 모두 욱여넣는 구조다. 단순한 도메인이라면 동작하지만, F&B 커머스에서는 곧바로 깨진다.

- 주문 자체는 정상이지만 결제만 실패한 경우 (재결제 가능)
- 부분취소(샐러드만 취소, 메인은 유지) 시 한 주문에 여러 결제 트랜잭션
- 포인트+카드 복합결제로 한 주문에 두 결제수단
- 매장 POS에서 현금/카드 분할

주문(order)은 비즈니스 의도이고, 결제(payment)는 그 의도를 화폐로 실현하는 별도의 트랜잭션이다. 따라서 1:N 관계로 분리한다. `payments` 테이블은 PG 호출 단위로 행을 가지고, 각 행은 자체적인 상태머신을 갖는다.

```
PENDING → AUTHORIZED → CAPTURED → (PARTIAL_)REFUNDED
                  └→ FAILED
                  └→ CANCELED
```

`AUTHORIZED`와 `CAPTURED`를 분리하는 이유는 카드사 표준이 그렇기 때문이다. 승인(authorize)은 한도 잡기, 매입(capture)은 실제 청구다. PG에 따라 자동 매입을 묶어주기도 하지만 상태 모델은 분리해두는 편이 안전하다. 추후 "주문 확정 시점에 매입" 같은 정책 변경이 들어와도 코드 구조를 갈아엎지 않는다.

### 트랜잭션 경계와 외부 호출의 충돌

여기가 모든 결제 사고의 진앙지다. PG 승인은 외부 네트워크 호출이고, DB 트랜잭션은 로컬 자원이다. 이 둘을 같은 `@Transactional` 안에 묶으면 다음과 같은 일이 일어난다.

1. DB 트랜잭션 시작
2. PG 호출 → 승인 성공
3. DB commit 직전 OOM 또는 커넥션 끊김
4. DB는 롤백, 그러나 카드사 입장에선 승인 완료

반대로 commit 이후 PG를 부르면, commit은 됐는데 PG 호출 직전에 죽으면 "DB는 결제됐다고 적혀있는데 실제 돈은 안 빠진" 상태가 된다. 즉 **외부 호출과 DB 상태 변경을 동일한 원자성으로 묶는 방법은 없다**. 우리는 이 "이중 쓰기 문제(dual write problem)"를 받아들이고, 그 위에서 안전한 흐름을 만든다.

기본 전략은 두 가지다.

- **상태 기반 단계 분리**: 주문/결제 행을 먼저 `PENDING`으로 만들고 commit, 그 다음 PG 호출, 그 결과를 별도 트랜잭션에서 `AUTHORIZED`/`FAILED`로 갱신한다.
- **Outbox 패턴**: DB와 같은 트랜잭션 안에 "외부에 보낼 메시지"를 outbox 테이블에 저장하고, 별도 워커가 outbox를 폴링하며 외부 호출을 수행한다. 외부 호출의 실패는 worker 재시도로 흡수되고, DB 상태 변경은 원자적으로 끝난다.

결제 승인처럼 동기 응답이 필요한 경우 첫 번째 전략을, 결제 후 알림/적립/회계 연동처럼 사용자 응답과 분리 가능한 경우 Outbox를 쓴다.

## 실전 백엔드 적용

### Idempotency key 저장 전략

가장 직관적인 방법은 별도 테이블이다.

```sql
CREATE TABLE idempotency_keys (
  idem_key       VARCHAR(80)  NOT NULL,
  endpoint       VARCHAR(80)  NOT NULL,
  user_id        BIGINT       NOT NULL,
  request_hash   CHAR(64)     NOT NULL,
  response_body  JSON         NULL,
  status         VARCHAR(20)  NOT NULL, -- IN_PROGRESS, SUCCEEDED, FAILED
  created_at     DATETIME(3)  NOT NULL,
  expires_at     DATETIME(3)  NOT NULL,
  PRIMARY KEY (idem_key, endpoint),
  KEY idx_expires (expires_at)
) ENGINE=InnoDB;
```

핵심 포인트:

- `(idem_key, endpoint)` 복합 PK로 같은 키를 다른 엔드포인트에서 재사용하는 사고를 막는다.
- `request_hash`를 함께 저장한다. 같은 키로 다른 금액이 들어오면 422로 거부한다. 안 그러면 클라이언트 버그로 "1만원 결제 키"로 10만원이 청구되는 사고가 난다.
- `IN_PROGRESS` 상태를 둔다. 동일 키 동시 요청이 두 개 들어왔을 때 늦은 쪽은 잠깐 기다리거나 409로 응답해야 한다.
- `expires_at`을 두고 주기적으로 정리한다. 무한 적재되면 인덱스 비대화로 INSERT 비용이 커진다.

Redis로 짧은 TTL만 쓰는 방식도 있지만, 결제처럼 감사 추적이 필요한 영역은 RDB 저장이 기본이고 Redis는 캐시/락 보조로 둔다.

### DB unique constraint를 마지막 방어선으로

idempotency key 테이블이 있어도 동시성 사고를 피하려면 **결제 행 자체에도 unique constraint**를 거는 편이 안전하다. 다중 방어선의 의미다.

```sql
ALTER TABLE payments
  ADD UNIQUE KEY uk_idem_key (idem_key);
```

idempotency 테이블은 "API 응답 캐시"의 의미가 강하고, payments 테이블의 unique key는 "도메인 무결성"의 마지막 보루다. 코드 어딘가의 버그로 같은 키가 두 번 흐르더라도, MySQL 5.7 이상의 InnoDB는 unique violation으로 거절한다. 애플리케이션은 `DuplicateKeyException`을 잡아 기존 행을 조회한 뒤 반환하면 된다.

### 상태머신을 코드로 명확히

상태 전이를 if-else 흐름으로 흩뿌리지 않는다. 명시적으로 enum과 전이 매트릭스를 둔다.

```java
public enum PaymentStatus {
  PENDING, AUTHORIZED, CAPTURED, FAILED, CANCELED, REFUNDED, PARTIAL_REFUNDED;

  private static final Map<PaymentStatus, Set<PaymentStatus>> ALLOWED = Map.of(
    PENDING,    Set.of(AUTHORIZED, FAILED, CANCELED),
    AUTHORIZED, Set.of(CAPTURED, CANCELED, FAILED),
    CAPTURED,   Set.of(REFUNDED, PARTIAL_REFUNDED),
    PARTIAL_REFUNDED, Set.of(REFUNDED, PARTIAL_REFUNDED)
  );

  public void assertCanTransitTo(PaymentStatus next) {
    if (!ALLOWED.getOrDefault(this, Set.of()).contains(next)) {
      throw new IllegalStateTransitionException(this, next);
    }
  }
}
```

이렇게 하면 "AUTHORIZED인 결제에 대해 또 AUTHORIZED를 쓰는 코드"가 컴파일타임에 거의 막히지는 않더라도, 단위테스트에서 즉시 깨진다. 결제 도메인은 상태 위반 한 번이 곧 회계 사고이므로 이 가드는 비싼 게 아니다.

## Bad vs Improved

### 패턴 1: 트랜잭션 안에서 PG 호출

**나쁜 예**

```java
@Transactional
public PaymentResult pay(Long orderId, PayCommand cmd) {
    Order order = orderRepository.findById(orderId).orElseThrow();
    order.assertPayable();

    PgResponse pg = pgClient.authorize(cmd.toPgRequest()); // 외부 호출

    Payment payment = new Payment(order, pg.getTxId(), cmd.getAmount(), AUTHORIZED);
    paymentRepository.save(payment);
    order.markPaid();
    return PaymentResult.from(payment);
}
```

문제는 명백하다. PG 호출이 성공한 뒤 DB commit 단계에서 어떤 이유로든 실패하면 PG는 승인됐는데 우리 DB에는 흔적이 없다. `@Transactional` 안에서 외부 호출을 하면 DB 커넥션도 그 시간만큼 잡혀 있어 커넥션 풀이 빠르게 고갈된다.

**개선된 예**

```java
public PaymentResult pay(Long orderId, PayCommand cmd, String idemKey) {
    Payment pending = txTemplate.execute(s -> reservePayment(orderId, cmd, idemKey));

    try {
        PgResponse pg = pgClient.authorize(cmd.toPgRequest(idemKey));
        return txTemplate.execute(s -> applyAuthorized(pending.getId(), pg));
    } catch (PgTimeoutException e) {
        // 상태는 PENDING으로 남기고 reconciliation worker에 위임
        return PaymentResult.pending(pending);
    } catch (PgRejectedException e) {
        return txTemplate.execute(s -> applyFailed(pending.getId(), e));
    }
}

private Payment reservePayment(Long orderId, PayCommand cmd, String idemKey) {
    return paymentRepository.findByIdemKey(idemKey)
        .orElseGet(() -> paymentRepository.save(Payment.pending(orderId, cmd, idemKey)));
}
```

세 가지가 달라졌다. PG 호출을 트랜잭션 밖으로 뺐고, idempotency key로 먼저 조회해 중복 진입을 막았으며, 타임아웃을 별도 예외로 분리해 "상태 미정"을 1차 응답으로 인정한다.

### 패턴 2: 타임아웃을 실패로 단정

**나쁜 예**

```java
try {
    pg.authorize(...);
} catch (Exception e) {
    payment.markFailed();
    throw e;
}
```

PG 호출의 `SocketTimeoutException`은 "실패"가 아니라 **"결과 미상"**이다. 승인이 됐는데 응답만 못 받았을 가능성이 절반이다. 이 코드는 PG에 승인된 거래를 우리 DB에서 FAILED로 닫고, 사용자가 재시도하면 두 번 청구되는 전형적 사고를 만든다.

**개선된 예**

```java
try {
    PgResponse pg = pgClient.authorize(req);
    payment.applyAuthorized(pg);
} catch (PgRejectedException e) {           // 명확한 거절
    payment.markFailed(e.getCode());
} catch (PgTimeoutException | IOException e) { // 결과 미상
    payment.markPending();                   // 상태 유지, reconciliation 위임
    auditLog.write("PG_TIMEOUT", payment.getId(), e);
}
```

대부분의 PG는 거래 조회 API를 제공한다. reconciliation worker가 PENDING 상태의 결제를 주기적으로 조회해 실제 상태로 동기화한다. 이 분기 한 줄이 정산 사고의 9할을 막는다.

### 패턴 3: Outbox 없이 알림/적립 호출

**나쁜 예**

```java
@Transactional
public void capture(Long paymentId) {
    Payment p = paymentRepository.findById(paymentId).orElseThrow();
    pgClient.capture(p);
    p.markCaptured();
    notificationClient.send(p);     // 외부 호출
    pointService.accrue(p);          // 외부 호출
}
```

알림 실패가 결제 매입 자체를 롤백시킨다. 또는 트랜잭션 종료 후 알림이 실패하면 사용자만 모르고 적립도 누락된다.

**개선된 예**

```java
@Transactional
public void capture(Long paymentId) {
    Payment p = paymentRepository.findById(paymentId).orElseThrow();
    p.markCaptureRequested();
    outboxRepository.save(OutboxEvent.of("PAYMENT_CAPTURE_REQUESTED", p));
}
```

별도 worker가 outbox를 폴링하며 PG capture, 알림, 적립을 단계적으로 호출한다. 각 단계는 자체 idempotency key를 들고, 실패는 백오프 재시도로 흡수한다. DB 트랜잭션은 outbox INSERT까지만 책임진다.

## Outbox와 Saga의 위치

Outbox는 "DB와 메시지 발행을 한 트랜잭션에 묶는" 패턴이다. Saga는 여러 서비스에 걸친 트랜잭션을 보상 트랜잭션의 연쇄로 표현하는 패턴이다. 결제 도메인에서 둘은 자주 같이 쓰인다.

```
[OrderService]                [PaymentService]              [PointService]
    |  주문 생성 + outbox        |                              |
    |---OrderCreated------------>|                              |
    |                            | 결제 + outbox                 |
    |                            |---PaymentCaptured----------->|
    |                            |                              | 적립
    |                            |<--PointAccrued---------------|
    |<--OrderConfirmed-----------|                              |
```

각 단계는 idempotency key를 들고 흐른다. 보상이 필요한 경우 (예: 적립 실패가 정책상 결제 취소를 유발한다면) `PaymentCancelRequested` 이벤트를 역방향으로 흘려보낸다. 면접에서 Saga 질문을 받으면 "이벤트 한 줄 한 줄이 idempotent해야 보상이 안전하다"가 핵심 답이다. 그렇지 않으면 보상이 또 다른 사고를 만든다.

## 부분취소와 환불의 함정

CJ푸드빌 같은 F&B 환경에선 "샐러드 한 개만 취소"가 일상이다. 부분취소는 결제 측면에서 두 가지 변형이 있다.

- **AUTHORIZED 상태에서의 부분취소**: 매입 전이므로 매입 금액을 줄여서 capture한다. 일부 PG는 이를 지원하지 않아 전액 취소 후 재승인이 필요하다.
- **CAPTURED 이후의 부분환불**: PG의 partial refund API를 호출한다. `payments` 테이블에 별도 행으로 환불 트랜잭션을 적재하거나, 같은 결제 행의 누적 환불 금액을 갱신한다.

추천하는 모델은 **결제와 환불을 모두 `payment_transactions` 행으로 균질하게 적는 것**이다.

```
payments(payment_id, order_id, idem_key, status, amount)
payment_transactions(tx_id, payment_id, type, amount, pg_tx_id, idem_key, status)
   type: AUTH, CAPTURE, REFUND, CANCEL
```

이렇게 하면 누적 환불 금액 = `SUM(amount WHERE type=REFUND AND status=SUCCEEDED)` 로 단순 집계되고, 감사로그가 자연스럽게 시계열로 정렬된다. 면접에서 "부분취소를 어떻게 모델링하셨어요"라고 물으면 이 구조를 그릴 수 있어야 한다.

## 감사로그와 재처리

결제는 사후 추적이 가능해야 한다. 모든 상태 전이는 별도 `payment_audit` 테이블에 적재한다.

```sql
CREATE TABLE payment_audit (
  audit_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  payment_id   BIGINT NOT NULL,
  prev_status  VARCHAR(20),
  next_status  VARCHAR(20) NOT NULL,
  actor        VARCHAR(40) NOT NULL,    -- USER, PG_WEBHOOK, RECON_WORKER, ADMIN
  reason       VARCHAR(200),
  payload      JSON,
  created_at   DATETIME(3) NOT NULL,
  KEY idx_payment (payment_id, created_at)
) ENGINE=InnoDB;
```

audit는 결제 행과 같은 트랜잭션에 쓴다. 그래야 "상태는 바뀌었는데 이력은 없는" 행을 만들지 않는다. 실무에서 정산팀과 가장 자주 부딪히는 질문은 "이 결제 왜 두 번 찍혔어요"인데, audit이 actor와 reason을 들고 있으면 5분에 끝난다.

reconciliation worker는 PENDING이 일정 시간 이상 머문 결제를 모아 PG 조회 API로 실제 상태를 받아온다. 워커는 자체 idempotency를 갖는다. 같은 결제를 두 번 reconcile해도 결과는 같아야 한다. 이게 무너지면 worker 자체가 사고의 원인이 된다.

## 로컬 실습 환경

MySQL 8 + Spring Boot 3 기준 최소 구성으로 위 흐름을 손에 익힌다.

```bash
docker run --name mysql-pay -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=pay -p 3306:3306 -d mysql:8.0
```

스키마를 올린다.

```sql
CREATE TABLE orders (
  order_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id   BIGINT NOT NULL,
  amount    INT NOT NULL,
  status    VARCHAR(20) NOT NULL,
  created_at DATETIME(3) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE payments (
  payment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id   BIGINT NOT NULL,
  idem_key   VARCHAR(80) NOT NULL,
  amount     INT NOT NULL,
  status     VARCHAR(20) NOT NULL,
  pg_tx_id   VARCHAR(80),
  created_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  UNIQUE KEY uk_idem (idem_key),
  KEY idx_order (order_id)
) ENGINE=InnoDB;
```

PG는 가짜 클라이언트로 흉내 낸다.

```java
@Component
public class FakePgClient {
    private final Random rand = new Random();

    public PgResponse authorize(PgRequest req) {
        sleepRandom(50, 300);
        int dice = rand.nextInt(100);
        if (dice < 5) throw new PgTimeoutException();   // 5% 타임아웃
        if (dice < 10) throw new PgRejectedException("LIMIT_EXCEEDED"); // 5% 거절
        return new PgResponse("PG-" + UUID.randomUUID(), "AUTHORIZED");
    }
}
```

이 위에서 다음 시나리오를 손으로 돌려본다.

1. 같은 idempotency key로 동시에 두 요청을 보내고, payments 행이 한 개만 만들어지는지 확인한다.
2. PG 응답을 1초 지연시킨 뒤 사용자가 재시도하는 상황을 시뮬레이션한다. 두 번째 호출이 첫 번째의 결과를 그대로 받는지 확인한다.
3. PG를 강제로 타임아웃시키고, PENDING 상태의 결제가 reconciliation worker에 의해 정상화되는 흐름을 만든다.
4. CAPTURED 결제에 대해 부분환불을 두 번 적용하고, `SUM(amount)`로 잔여 가능 환불 금액이 정확히 계산되는지 확인한다.

각 시나리오에서 `payment_audit`가 어떻게 쌓이는지 직접 본다. 이 경험이 면접 답변의 디테일을 만든다.

## 인터뷰 답변 프레이밍

질문이 "결제 중복 어떻게 막으셨어요"로 들어오면 다음 순서로 답한다.

1. **레이어를 분리해서 답한다**: 클라이언트 idempotency key, 서버 idempotency 테이블, payments 테이블 unique constraint 세 단계.
2. **타임아웃을 어떻게 다뤘는지를 함께 말한다**: 타임아웃은 실패가 아니라 미상이라는 점, PENDING 상태로 두고 reconciliation에 위임한다는 점.
3. **트랜잭션 경계를 그린다**: PG 호출은 트랜잭션 밖, 상태 전이만 트랜잭션 안. 이게 dual write 문제의 현실적 절충안이다.
4. **부분취소까지 확장**: 결제와 환불을 transaction 행으로 균질화한 모델을 짧게 그린다.
5. **마지막에 한계 인정**: 완벽한 분산 트랜잭션은 없고, 감사로그와 재처리로 최종 일관성을 보장한다.

"트랜잭션 안에서 외부 호출 하면 안 되는 이유는요?"라는 후속 질문이 거의 반드시 따라온다. 답은 두 가지를 묶는다. 첫째, 커넥션 풀이 외부 응답시간만큼 잡혀 동시성이 깨진다. 둘째, commit과 외부 호출의 원자성을 보장할 수 없어서 어차피 실패 시나리오가 남는다. 이 두 답을 같이 하면 "이 사람은 실제로 사고를 본 적이 있구나"로 들린다.

"Saga 써보셨어요?"는 함정이다. 안 써봤다면 솔직히 말하고, 대신 Outbox + 이벤트 기반 보상의 골격을 그려라. Saga 프레임워크 이름을 외워서 답하는 것보다, 보상 가능한 이벤트 설계 원칙을 말하는 편이 점수가 높다.

## 체크리스트

- [ ] idempotency key를 서버에서 발급하는 흐름이 그려지는가
- [ ] idempotency 테이블의 IN_PROGRESS 상태와 동시 요청 처리를 설명할 수 있는가
- [ ] payments 테이블에 unique constraint를 두는 이유를 설명할 수 있는가
- [ ] 주문과 결제를 1:N으로 분리하는 근거를 들 수 있는가
- [ ] PG 호출을 트랜잭션 밖으로 빼는 이유를 두 가지 이상 말할 수 있는가
- [ ] 타임아웃과 거절을 다르게 처리하는 코드를 직접 짤 수 있는가
- [ ] PENDING 결제를 정상화하는 reconciliation worker의 멱등성을 설명할 수 있는가
- [ ] Outbox 패턴이 dual write 문제를 어떻게 우회하는지 그릴 수 있는가
- [ ] 부분취소와 부분환불을 한 모델로 표현할 수 있는가
- [ ] 모든 상태 전이가 audit에 남는지 코드 흐름으로 확인 가능한가
- [ ] 면접 답변을 90초 안에 위 5단계로 압축해서 말할 수 있는가
