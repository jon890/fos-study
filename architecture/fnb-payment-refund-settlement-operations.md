# [초안] F&B 이커머스 결제·환불·정산 운영 가이드

## 왜 이 주제가 중요한가

F&B 이커머스(예: 빵집, 카페, 외식 브랜드의 온라인 주문/예약/선물하기/모바일 상품권)는 일반 상품 커머스와 다른 결제 운영 특성을 가진다. 단가가 작은 주문이 단시간에 폭증하고(점심·저녁 피크), 매장 단위로 정산이 분기되며, 모바일 상품권·선불충전·카카오페이 머니 같은 "현금이 아닌 결제수단"이 섞이고, 매장 사정으로 인한 부분취소가 매우 잦다. "주문은 됐는데 카드 승인이 안 되었다", "결제는 됐는데 매장에서 거절했다", "모바일 쿠폰을 환불해 달라"는 문의가 매일 들어온다.

이 영역의 핵심 질문은 보통 결제는 됐는데 주문은 실패한 케이스를 어떻게 처리하는지, PG 망 장애 시 결제 상태를 어떻게 복구하는지, 환불 정합성을 어떻게 보장하는지로 좁혀진다. 이는 단순한 결제 SDK 호출 이야기가 아니라, **분산 트랜잭션의 일관성 모델, 멱등성, 상태기계 설계, 정산/대사 운영**에 대한 문제다. 카프카 Outbox Pattern으로 트랜잭션 경계를 다루는 패턴을 결제 도메인 언어로 그대로 옮길 수 있다.

이 문서는 PG 연동의 표면적 흐름을 넘어, 실제 운영에서 마주치는 정합성 깨짐 시나리오, 재시도와 멱등키 설계, 정산·대사 운영, 장애 복구·감사로그까지 한 번에 정리한다.

## 핵심 개념: 결제는 "두 시스템의 합의"다

결제는 본질적으로 **우리 시스템(주문/결제 도메인)과 외부 PG(또는 간편결제사) 사이의 분산 합의 문제**다. 두 시스템이 항상 같은 상태를 보고 있다고 가정하면 사고가 난다.

### PG 결제 라이프사이클

신용카드 결제 흐름은 보통 두 단계로 나뉜다.

- **승인**(Authorization): 카드사가 한도를 잠그고 "이 금액 결제 가능"을 확정. 실제 돈이 매입되는 시점은 아님.
- **매입**(Capture): 가맹점이 매출을 확정 요청하고, 카드사가 실제 돈을 이동시킨다. 보통 D+1~D+2.

PG에 따라 승인/매입을 한 번에 처리하는 모드가 기본이지만, F&B에서 "주문 수령(매장 픽업/배달 출발) 시점에 매입"하는 형태를 쓰는 경우도 있다. 이 경우 취소 비용·정산 흐름이 달라진다.

취소도 두 종류다.

- **승인 취소**(Void): 매입 전에 승인을 무효화. 카드 명세서에 흔적이 거의 안 남는다.
- **환불**(Refund): 매입 후 돈을 되돌려 줌. 카드 명세서에는 매출과 환불이 같이 찍힌다.

### 결제수단별 환불 특성

| 수단 | 즉시 환불 가능성 | 부분 환불 | 운영 함정 |
|------|------------------|-----------|-----------|
| 신용/체크카드 | 승인 당일 Void는 즉시, 매입 후 Refund는 영업일 기준 며칠 | 가능 | Void 마감시간(보통 23:30) 넘기면 자동으로 Refund로 전환 |
| 계좌이체(가상계좌) | 다음 영업일 환불계좌 입금 | 가능하나 PG에 따라 제한 | 환불계좌 검증 필요(예금주 일치) |
| 카카오페이/네이버페이 머니 | 즉시 | 가능 | 포인트 적립분 회수 정책 따로 |
| 모바일 상품권/금액권 | 잔액 복원 또는 결제 취소 | 사용 분 차감 후 환불 | 부분 사용 후 만료된 케이스 |
| 선불충전 잔액 | 잔액 복원 | 가능 | 잔액 → 카드 환불 변환 시 회계 분리 |

이 표는 정책이 아니라 **상태기계 설계의 입력**이다. 결제수단별로 가능한 전이가 다르기 때문이다.

## 주문과 결제의 상태를 분리하라

가장 흔한 안티패턴은 주문 테이블 하나에 결제 상태까지 우겨넣는 것이다. F&B에서는 다음과 같은 상태가 동시에 존재한다.

- 주문: `RECEIVED → ACCEPTED → PREPARING → READY → COMPLETED` (or `REJECTED`, `CANCELLED`)
- 결제: `PENDING → AUTHORIZED → CAPTURED → REFUNDED(부분/전체)` (or `FAILED`, `VOIDED`)
- 배송/픽업: 별도 상태기계

핵심 원칙은 **주문 상태와 결제 상태를 독립 상태기계로 두고, 둘을 합성한 뷰를 화면/CS에 노출**하는 것이다. 그래야 "결제는 성공했는데 매장에서 거절"이 단순한 케이스가 된다. 결제 상태기계에서는 `CAPTURED → REFUNDED`만 신경 쓰면 되고, 주문 상태기계에서는 `RECEIVED → REJECTED`만 정의하면 된다. 둘을 묶는 책임은 별도 컴포넌트(주문 조정자)가 진다.

## 정합성 깨짐 시나리오

운영에서 반드시 마주치는 4가지 사고 패턴이다.

### 시나리오 1: 결제 성공, 주문 저장 실패

가장 비싼 사고다. PG로부터 승인 응답을 받았는데, 그 직후 주문 영속화에 실패하는 경우.

원인:

- 승인 응답을 받은 직후 DB 커넥션 끊김
- 트랜잭션 안에서 PG 호출까지 같이 한 뒤 PG 응답이 늦어 트랜잭션 타임아웃
- 외부 호출 후 단순한 unchecked exception이 트랜잭션 롤백을 일으킴

처리:

- 결제 시도 직전에 **결제 의도(Payment Intent)를 먼저 저장**한다. 상태는 `PENDING`. 멱등키와 외부 주문번호를 함께 부여한다.
- PG 호출은 트랜잭션 밖에서 한다.
- 응답을 받은 뒤, 별도 짧은 트랜잭션으로 `AUTHORIZED`/`CAPTURED`로 갱신한다.
- 갱신 실패 시에도 **PG 측 거래는 살아있다**고 가정하고, 복구 잡(Reconciliation Job)이 PG의 거래목록을 가져와 우리 쪽 PENDING과 매칭한다. 매칭되지 않은 PG 거래는 자동 Void/Refund 후보다.

### 시나리오 2: 주문 성공, 결제 누락

PG 호출 자체가 타임아웃이 나서 응답을 받지 못한 경우. 이때 절대 안 되는 것이 "타임아웃이니까 실패로 판단해서 같은 멱등키로 다시 호출"하는 것이다. PG 쪽에서는 첫 호출이 살아 승인되어 있을 수 있다.

처리:

- 모든 PG 호출에는 우리가 부여한 **멱등키**(idempotency key)를 담는다. 보통 `paymentIntentId`로 충분하다.
- 타임아웃 시 같은 키로 **재시도하지 말고 조회 API**로 상태를 묻는다.
- 조회가 막히면 일정 시간(예: 30초)뒤 다시 조회. 그 시간 동안 사용자에게는 "결제 확인 중" 상태를 보여 준다.
- 응답 미수신이 길어지면 사용자 화면은 안전한 메시지("결제가 처리 중입니다. 중복 결제 방지를 위해 다시 시도하지 마세요")로 잠근다.

### 시나리오 3: 결제 후 매장 거절

F&B 특유의 케이스다. "주문 들어왔는데 재료가 떨어졌다", "마감 직전이라 못 만든다" 같은 사유.

처리:

- 매장이 거절을 누르면 **취소 사유 코드**를 함께 보낸다.
- 주문 상태를 `REJECTED`로 옮기는 것과 동시에 결제 도메인에 **환불 명령**을 발행한다. 이때 직접 호출이 아니라 **Outbox 메시지**로 발행한다.
- 환불 처리기는 결제수단 종류에 따라 Void/Refund를 선택한다. 같은 날 23:30 이전 카드 결제면 Void가 우선이다.
- 환불은 **부분 실패 가능성이 높다**. 한 주문에 카드 + 포인트 + 쿠폰이 섞여 있으면 카드 환불은 됐는데 쿠폰 복원만 실패할 수 있다. 각 환불을 독립 트랜잭션으로 관리하고, 실패한 건만 재시도 큐에 넣는다.

### 시나리오 4: 부분 환불

피자 5판 주문 중 1판만 못 만들었다. 1판분만 환불해야 한다.

처리:

- 주문 라인 단위로 가격 분해를 미리 계산해 둔다(쿠폰/적립금 안분 포함).
- 환불 요청은 라인 ID와 금액을 포함한다.
- 결제 수단이 여러 개 섞였으면 **환불 분배 정책**을 명시적으로 결정해 둔다. 보통 "쿠폰/포인트 → 카드" 순으로 환불해서 사용자 카드 명세서를 단순하게 만든다.
- 환불 누적 금액이 매입 금액을 초과하지 않게 DB 제약(체크 제약 또는 트리거)으로 막는다.

## 멱등성, Outbox, Saga: 인프라 패턴의 결제 도메인 적용

### 멱등키 설계

```sql
CREATE TABLE payment_intent (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  intent_key    CHAR(36) NOT NULL,
  order_id      BIGINT   NOT NULL,
  amount        DECIMAL(13,2) NOT NULL,
  currency      CHAR(3)  NOT NULL DEFAULT 'KRW',
  status        VARCHAR(16) NOT NULL,
  pg_provider   VARCHAR(32) NOT NULL,
  pg_tid        VARCHAR(64) NULL,
  created_at    DATETIME(3) NOT NULL,
  updated_at    DATETIME(3) NOT NULL,
  UNIQUE KEY uk_intent_key (intent_key),
  KEY idx_order (order_id),
  KEY idx_status_created (status, created_at)
) ENGINE=InnoDB;
```

멱등키 `intent_key`는 사용자 액션(주문 결제 버튼 누름) 단위로 발급한다. 같은 결제 버튼을 여러 번 눌러도 같은 키가 재사용되도록 클라이언트가 보관한다. 서버는 같은 키가 들어오면 기존 intent를 반환한다.

PG 호출 시 헤더 또는 바디에 이 키를 넣는다. 대부분의 국내 PG는 `Idempotency-Key` 또는 자체 필드명을 지원한다. 지원하지 않더라도 우리 쪽에서 단일 호출만 보장하면 충분하다.

### [Outbox 패턴](distributed-transaction-outbox-pattern.md): 트랜잭션 경계와 메시지 발행 분리

카프카 Outbox 패턴은 결제 도메인에서 다음과 같이 매핑된다.

기존 도메인: "주문이 저장되었으니 검색 색인 업데이트 메시지를 보낸다"
결제 도메인: "결제가 CAPTURED 됐으니 정산 도메인과 알림 도메인에 사실을 알린다"

```java
@Transactional
public void confirmCapture(PaymentIntent intent, PgCaptureResponse res) {
    intent.markCaptured(res.getTid(), res.getApprovedAt());
    paymentIntentRepository.save(intent);

    OutboxEvent event = OutboxEvent.of(
        "payment.captured.v1",
        intent.getId(),
        PaymentCapturedPayload.from(intent, res)
    );
    outboxRepository.save(event);
}
```

핵심은 **결제 상태 변경과 메시지 발행이 동일 트랜잭션 안에서 같은 DB에 기록**된다는 점이다. 별도 발행기(Outbox Poller 또는 Debezium)는 이 테이블을 읽어 카프카로 흘려 보낸다. 정산·알림·CS 사이드의 어떤 컨슈머가 죽어도 결제 본 트랜잭션은 안전하다.

이 흐름을 설계할 때는 트랜잭션 안에서 외부 호출을 시도하다 롤백 시점이 어긋나 정합성이 깨지는 문제를 outbox로 정리한다. 결제는 그 패턴이 가장 강하게 요구되는 도메인이다.

### Saga: 환불 보상 트랜잭션

부분 결제(카드 + 쿠폰 + 포인트)를 환불할 때, 각 사이드 효과를 **보상 가능한 단위 트랜잭션**으로 쪼갠다.

1. 카드 환불 명령 발행
2. 카드 환불 성공 이벤트 수신 → 쿠폰 복원 명령 발행
3. 쿠폰 복원 성공 이벤트 수신 → 포인트 복원 명령 발행
4. 어느 단계에서 실패하면 **이전 단계의 보상 명령**을 발행

오케스트레이션형 Saga로 가는 경우가 운영상 추적이 쉽다. "환불 작업"이라는 단일 엔티티가 진행 상태를 들고 있어 CS가 한 화면에서 추적할 수 있다.

## 정산: 매장·브랜드·본사 흐름

F&B에서 정산은 일반 셀러 정산과 다르다.

- **매장 정산**: 가맹점/직영점 단위로 매출 - 환불 - 수수료 = 입금액
- **브랜드 정산**: 본사가 브랜드별로 매출을 합산하고 광고비/플랫폼 수수료를 차감
- **본사 정산**: PG 입금 자체는 본사 명의 계좌로 들어오고, 본사가 매장에 재분배

이 흐름은 두 가지 방식으로 구현된다.

1. **본사 일괄 수금 후 분배**: PG 가맹점 등록을 본사 명의로 하고, 매장별 정산을 내부 정산 잡으로 처리. 캐시플로우 단순, 회계 복잡.
2. **하위 가맹점 분리**(서브머천트): PG가 매장 단위 입금 분리를 지원. 회계 단순, PG 연동·KYC 복잡.

운영 관점에서 매일 해야 하는 일은 **대사**(reconciliation)다.

```
PG 정산내역(파일 또는 API) ─┐
                            ├─ 대사 엔진 ─→ 정산 확정 / 차이 리포트
우리 결제 도메인 거래내역 ──┘
```

대사 엔진의 책임:

- PG 거래 ID 단위로 우리 쪽 `payment_intent`와 매칭
- 금액·수수료·환불 금액 차이 검출
- 매칭되지 않는 거래(우리에는 없는데 PG에는 있는 등)를 별도 큐로 분리
- 차이가 임계값을 넘으면 운영 알림(슬랙/이메일/SMS)

### 일별 대사 쿼리 예시

```sql
-- PG가 알려준 일별 매출과 우리 쪽 CAPTURED 합계 비교
SELECT
  d.settle_date,
  d.pg_amount,
  COALESCE(p.our_amount, 0) AS our_amount,
  d.pg_amount - COALESCE(p.our_amount, 0) AS diff
FROM (
  SELECT settle_date, SUM(amount) AS pg_amount
  FROM pg_settlement_daily
  WHERE settle_date BETWEEN '2026-05-01' AND '2026-05-07'
  GROUP BY settle_date
) d
LEFT JOIN (
  SELECT DATE(captured_at) AS settle_date, SUM(amount) AS our_amount
  FROM payment_intent
  WHERE status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
    AND captured_at BETWEEN '2026-05-01 00:00:00' AND '2026-05-08 00:00:00'
  GROUP BY DATE(captured_at)
) p ON p.settle_date = d.settle_date
ORDER BY d.settle_date;
```

이 쿼리에서 `diff`가 0이 아닌 행이 운영 알림으로 떠야 한다.

## 잘못된 설계 vs 개선된 설계

### Bad: 주문 트랜잭션에 PG 호출을 묶기

```java
@Transactional
public Order placeOrder(OrderCommand cmd) {
    Order order = Order.from(cmd);
    orderRepository.save(order);

    // 위험: 외부 호출이 트랜잭션 안에 있음
    PgResponse res = pgClient.approve(order.toPgRequest());

    if (!res.isSuccess()) throw new PaymentFailed(res);
    order.markPaid(res.getTid());
    return order;
}
```

문제:

- PG 응답이 늦으면 DB 트랜잭션이 길게 열려 커넥션 풀을 잠근다
- PG는 승인됐는데 우리 트랜잭션이 롤백되는 사고 가능
- 멱등키 없음, 재시도 시 중복 결제 위험

### Improved: 의도 → 외부 호출 → 확정의 3단계

```java
public PaymentIntent prepare(OrderCommand cmd, String idempotencyKey) {
    return paymentIntentRepository
        .findByIntentKey(idempotencyKey)
        .orElseGet(() -> paymentIntentRepository.save(
            PaymentIntent.pending(cmd, idempotencyKey)
        ));
}

public PaymentIntent capture(PaymentIntent intent) {
    PgResponse res;
    try {
        res = pgClient.approve(intent.toPgRequest()); // 트랜잭션 밖
    } catch (PgTimeoutException e) {
        res = pgClient.inquiry(intent.getIntentKey()); // 같은 키로 조회
    }

    return updateAfterPg(intent.getId(), res);
}

@Transactional
protected PaymentIntent updateAfterPg(Long intentId, PgResponse res) {
    PaymentIntent intent = paymentIntentRepository.findById(intentId).orElseThrow();
    if (res.isApproved()) intent.markCaptured(res.getTid(), res.getApprovedAt());
    else intent.markFailed(res.getCode(), res.getMessage());

    outboxRepository.save(OutboxEvent.from(intent));
    return intent;
}
```

핵심 차이:

- 외부 호출이 트랜잭션 밖
- 멱등키로 중복 시도 방지
- 타임아웃 시 재호출 대신 조회 API
- 상태 변경과 outbox 발행이 같은 트랜잭션

## 로컬 실습 환경

MySQL 8과 도커로 충분히 시뮬레이션할 수 있다.

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpw
      MYSQL_DATABASE: payments
    ports: ["3306:3306"]
    command:
      - --character-set-server=utf8mb4
      - --default-time-zone=+09:00
  redis:
    image: redis:7
    ports: ["6379:6379"]
  kafka:
    image: bitnami/kafka:3.7
    ports: ["9092:9092"]
    environment:
      KAFKA_CFG_NODE_ID: "1"
      KAFKA_CFG_PROCESS_ROLES: "broker,controller"
      KAFKA_CFG_LISTENERS: "PLAINTEXT://:9092,CONTROLLER://:9093"
      KAFKA_CFG_ADVERTISED_LISTENERS: "PLAINTEXT://localhost:9092"
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: "1@localhost:9093"
      KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT"
```

PG는 실제 연동 없이 가짜 서버(WireMock 또는 간단 Spring Boot 앱)로 돌린다. 시나리오 시뮬레이터를 만들어 두면 실습 효과가 크다.

```java
// FakePg: 시나리오별 응답
@PostMapping("/approve")
public PgResponse approve(@RequestBody PgRequest req) {
    String scenario = req.getScenario();
    return switch (scenario) {
        case "OK"        -> PgResponse.approved("TID-" + UUID.randomUUID());
        case "TIMEOUT"   -> sleepThen(95_000, () -> PgResponse.approved("TID-LATE"));
        case "DECLINED"  -> PgResponse.declined("LIMIT_EXCEEDED");
        case "DUPLICATE" -> PgResponse.duplicate(); // 같은 멱등키 두 번째 호출
        default          -> PgResponse.approved("TID-" + UUID.randomUUID());
    };
}
```

## 실행 가능한 실습 시나리오

다음 5개 시나리오를 직접 실행해 보면 운영 감각이 빠르게 잡힌다.

1. **타임아웃 시나리오**: PG 응답을 95초 지연시켜 보고, 클라이언트가 60초 타임아웃을 만나도록 설정. 그 후 조회 API로 복구되는지 확인.
2. **중복 클릭 시나리오**: 같은 `intent_key`로 동시에 두 번 호출. 두 번째 호출이 새 거래를 만들지 않고 기존 의도를 반환하는지 확인.
3. **부분 환불 시나리오**: 라인 3개 중 1개 환불. 카드 환불액 + 쿠폰 복원액 합계가 라인 가격과 일치하는지 확인.
4. **23:30 경계 시나리오**: 23:25, 23:35에 각각 환불 호출. 하나는 Void, 하나는 Refund 경로로 라우팅되는지 확인.
5. **대사 차이 시나리오**: PG 정산 파일에 우리에 없는 거래 1건을 일부러 추가. 대사 엔진이 차이를 감지하고 운영 알림 큐에 넣는지 확인.

## 핵심 설계 질문과 정리

### 질문 A: 결제는 됐는데 주문이 실패한 케이스를 어떻게 처리하는가

핵심은 세 단계다.

1. 주문 트랜잭션과 PG 호출을 분리한다. 결제 의도(Intent)를 먼저 영속화하고, PG 호출은 트랜잭션 밖에서 한다.
2. PG 응답을 받은 뒤 짧은 트랜잭션으로 의도를 확정하고, 같은 트랜잭션에서 outbox로 사실을 발행한다.
3. 그래도 갈라지는 케이스는 대사 잡으로 잡는다. 우리 DB의 PENDING이 일정 시간 이상 살아 있으면 PG 조회 API로 실제 상태를 확인하고, 우리만 모르는 매입 거래는 자동 환불 후보로 분리한다.

이 설계의 뿌리는 동일하다. 트랜잭션 안에서 카프카 발행을 묶으면 발행은 됐는데 DB는 롤백되는 사고가 나므로 outbox로 옮기는 패턴을 결제에 그대로 적용한 것이다.

### 질문 B: PG가 잠시 죽으면 어떻게 운영하는가

- 회로차단기로 단기 격리
- 그 사이 들어오는 결제는 의도(Intent)만 만들고, 사용자에게는 "결제 처리 중" 페이지를 보여 준다
- PG 복구되면 큐에 쌓인 의도를 차례로 처리. 멱등키로 중복 방지
- 일정 시간 미해소 의도는 자동 취소로 전환. 사용자에게 별도 알림
- 운영 채널에 결제 성공률·평균 응답시간 그래프를 항상 띄워 둔다

### 질문 C: 환불 정합성을 어떻게 보장하는가

- 환불은 결제 수단별 라인 분해 후 각 수단별 독립 트랜잭션
- Saga로 단계별 보상 정의
- DB 레벨에서 누적 환불 ≤ 매입 제약
- 실패한 단계는 재시도 큐로, 일정 횟수 초과 시 수동 운영
- 모든 환불은 감사로그 테이블에 액터·이전 상태·다음 상태·근거 PG 응답 원본을 남긴다

## 운영·감사·알림

- **감사로그**: 결제·환불의 모든 상태 전이를 별도 테이블에 append-only로 적재. 행에는 `actor`, `actor_type`(USER/STAFF/SYSTEM), `before_status`, `after_status`, `reason_code`, `pg_raw_response`, `created_at`. 회계 감사 대응에 직결된다.
- **알림 임계치**: 결제 실패율 > 평소 × 2, 분당 환불 건수 급증, 대사 차이 금액 > X원, PG 응답 P99 > Y초.
- **운영 도구**: CS가 결제 의도 한 건의 전체 타임라인(주문, 결제, 환불, PG 원시 응답, 감사로그)을 한 화면에서 볼 수 있어야 한다. 이게 안 되면 야간 장애가 곧 트라우마가 된다.

## 체크리스트

- [ ] 주문 상태와 결제 상태를 별도 상태기계로 분리했는가
- [ ] 결제 의도(Intent)를 PG 호출 전에 영속화하고 멱등키를 부여했는가
- [ ] PG 호출은 DB 트랜잭션 밖에서 일어나는가
- [ ] PG 타임아웃 시 같은 키로 재호출하지 않고 조회 API로 상태를 확인하는가
- [ ] 상태 변경과 메시지 발행이 outbox로 같은 트랜잭션 안에 묶여 있는가
- [ ] 환불을 결제수단별 독립 트랜잭션과 Saga로 모델링했는가
- [ ] 부분 환불 시 라인 단위 가격 분해와 누적 환불 제약이 있는가
- [ ] 23:30 같은 결제 마감 경계가 환불 라우팅에 반영되어 있는가
- [ ] 매일 자동 대사 잡이 돌고, 차이가 임계치를 넘으면 운영 알림이 가는가
- [ ] 모든 결제·환불 상태 전이가 감사로그에 append-only로 남는가
- [ ] CS가 한 결제건의 전체 타임라인을 한 화면에서 볼 수 있는가
- [ ] 매장·브랜드·본사 정산 흐름과 PG 입금 구조(통합 vs 서브머천트)가 문서화되어 있는가

## 관련

- [F&B 주문/매장/픽업 상태머신 설계](./fnb-order-store-pickup-state-machine.md) — 환불 흐름이 묶여 있는 주문 상태머신
