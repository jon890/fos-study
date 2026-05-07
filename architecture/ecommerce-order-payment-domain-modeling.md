# [초안] e-Commerce 주문·결제 도메인 모델링: 상태머신, 멱등성, Outbox/Saga 실전 정리

## 왜 이 주제가 중요한가

CJ푸드빌·F&B 계열 e-Commerce 백엔드는 단순한 "장바구니 → 결제" 흐름이 아니다. 같은 주문 한 건이 매장 픽업, 배달, 예약, 쿠폰 결합, 멤버십 적립, 프로모션 가격 정책, 결제 승인/부분취소/환불, 재고 차감, 매장 운영시간 검증까지 동시에 만족해야 한다. 도메인이 잘못 잘리면 한 가지 실패 시나리오만 발생해도 "결제는 됐는데 주문은 안 들어간다", "쿠폰은 차감됐는데 결제는 취소됐다", "재고는 빠졌는데 매장에서 거절했다" 같은 운영 사고가 그대로 사용자에게 노출된다.

면접에서 이 주제는 단일 모델 설계 문제가 아니라 **분산 환경에서 정합성을 어떻게 지키는가**, **장애가 났을 때 시스템이 어떻게 회복하는가**, **운영 관점에서 무엇을 지표로 보는가**까지 묻는다. 따라서 본 문서는 도메인을 어떻게 자르는지, 상태머신을 어떻게 정의하는지, 멱등성과 Outbox/Saga를 언제 어떻게 적용하는지, 그리고 그 의사결정을 어떻게 답변으로 번역하는지를 한 흐름으로 정리한다.

## 핵심 도메인 경계

도메인을 자를 때는 "데이터 일관성이 같은 트랜잭션 안에 묶여야 하는가"를 기준으로 본다. 같은 트랜잭션이어야 한다면 같은 Aggregate, 다른 시점에 결과가 보장돼도 되면 다른 Bounded Context로 분리한다.

- **주문(Order)**: 주문번호, 주문자, 주문 항목, 결제 예정 금액, 적용된 쿠폰/프로모션 스냅샷, 픽업/배달 정보, 상태. 주문 항목 단가/할인은 주문 시점에 **스냅샷**으로 동결한다. 상품 마스터가 나중에 가격을 바꿔도 주문 금액은 바뀌면 안 된다.
- **결제(Payment)**: PG 승인 트랜잭션, 부분취소/전체취소/환불 이력, 결제수단별 분할(카드+포인트+상품권). Order와 1:N. 결제 자체는 PG 응답이 진실의 원천이라 별도 Aggregate.
- **쿠폰(Coupon)**: 발급된 쿠폰 인스턴스(소유자 ID, 사용 가능 기간, 사용 상태). "쿠폰 정책 마스터(CouponPolicy)"와 "발급 인스턴스(IssuedCoupon)"를 분리한다.
- **프로모션(Promotion)**: 기간/매장/상품 단위 가격 규칙, 1+1, N% 할인, 묶음할인. 정책은 변하므로 주문 시점 적용 결과는 Order에 스냅샷.
- **회원(Member)**: 등급, 멤버십 포인트, 마케팅 수신동의. 포인트 사용/적립은 결제와 같은 트랜잭션에 묶을 수 없는 경우가 많아 Saga 대상.
- **매장/픽업/배달(Store/Fulfillment)**: 매장 운영시간, 픽업 가능 슬롯, 배달 라이더 가용성, 매장 재고. 외부 시스템과의 연동이 잦아 비동기 위주.
- **재고(Inventory)**: 매장 단위 재고 vs 중앙 재고. F&B는 매장 단위 재고가 주이므로 매장 ID + 상품 ID가 자연스러운 키.

원칙: **Order Aggregate 안에서 결제 상세, 매장 운영, 재고를 직접 변경하지 않는다.** 도메인 이벤트로 전파하고 각자 책임지게 한다.

## 주문 상태머신

주문 상태는 명시적으로 정의된 **유한 상태머신**으로 다룬다. 임의 문자열 컬럼이 아니라 enum + 전이 규칙으로 강제한다.

```
CREATED        → PAYMENT_PENDING
PAYMENT_PENDING → PAYMENT_APPROVED | PAYMENT_FAILED | CANCELED_BY_USER
PAYMENT_APPROVED → STORE_ACCEPTED | STORE_REJECTED | CANCELED_BY_USER
STORE_ACCEPTED → PREPARING → READY_FOR_PICKUP/OUT_FOR_DELIVERY → COMPLETED
어디서든 → REFUND_REQUESTED → REFUNDED (정책 검증 후)
```

핵심 규칙:

- **결제 승인 전에는 매장에 주문이 가지 않는다.** 결제 승인 전에 매장에 알리면 "주문 들어왔다"고 조리하다 결제 실패하는 사고가 난다.
- **STORE_REJECTED는 결제 자동취소를 트리거한다.** 매장 거절 시 PG에 결제 취소 명령을 보내고, 사용자에게는 환불 진행 중 상태로 노출한다.
- **취소는 시점에 따라 비용이 다르다.** PAYMENT_PENDING 단계 취소는 PG 호출 없이 종료할 수 있고, PAYMENT_APPROVED 이후 취소는 PG 취소/환불 API를 거쳐야 한다. 코드에서 같은 `cancel()` 함수로 묶어버리면 운영 사고가 난다.

상태 전이 함수는 도메인 객체 안에 두고, 잘못된 전이는 예외를 던진다.

```java
public final class Order {
    private OrderStatus status;

    public void approvePayment(PaymentApproved event) {
        if (this.status != OrderStatus.PAYMENT_PENDING) {
            throw new IllegalOrderTransitionException(this.status, "approvePayment");
        }
        this.status = OrderStatus.PAYMENT_APPROVED;
        registerEvent(new OrderPaymentApprovedEvent(this.id, event.paymentId()));
    }
}
```

## 결제 승인/취소/환불 모델링

결제는 PG 응답이 진실의 원천이지만, 자체 시스템에도 결제 트랜잭션 이력을 둔다. **PG와 자체 DB가 어긋날 때 어느 쪽이 진실인가**를 정해 둬야 한다.

권장 모델:

- 결제 시도(`PaymentAttempt`): 사용자가 결제 버튼을 누르면 만들어진다. 멱등키(idempotency key)는 `(orderId, attemptSeq)`.
- 결제 승인(`PaymentApproval`): PG 승인 응답이 도착하면 1건. 같은 PaymentAttempt에 대해 중복 도착해도 1건만 유효하게 만든다(unique 제약).
- 결제 취소/환불(`PaymentRefund`): 부분환불을 지원하려면 금액과 사유, 대상 주문 항목 식별자 보관.

PG 호출 자체가 멱등이 아닌 경우가 많아서 **요청 보내기 전에 자체 DB에 "승인 요청 중" 레코드를 먼저 commit**하고, PG 응답이 와야 그 레코드를 갱신한다. 응답이 안 오면 별도 reconciliation job이 PG에 "이 거래 ID 어떻게 됐냐" 조회해서 맞춘다. 이 패턴이 빠지면 사용자가 결제창을 두 번 눌렀을 때 이중 청구가 발생한다.

## 쿠폰 중복 사용 방지

쿠폰은 "정책"과 "발급 인스턴스"를 분리해야 멱등하게 다룰 수 있다.

- 발급된 쿠폰 인스턴스는 `(coupon_id PK, member_id, status, used_order_id, used_at, version)`을 가진다.
- 쿠폰을 사용하는 트랜잭션은 `UPDATE issued_coupon SET status='USED', used_order_id=?, used_at=NOW() WHERE coupon_id=? AND status='ISSUED'` 한 줄이 핵심이다.
- `affected rows = 1`이면 사용 성공, 0이면 이미 사용/만료된 것. **SELECT 후 UPDATE를 따로 두지 말고 조건부 UPDATE 한 번으로 끝낸다.**

같은 사용자가 동시에 같은 쿠폰을 두 주문에 적용하려 해도 DB의 row lock + 조건부 update가 막아준다. 분산락으로 풀려고 하면 락 점유 시간이 결제 PG 호출까지 길어져서 운영 장애로 번진다.

```sql
-- 쿠폰 사용 시도. 멱등하다.
UPDATE issued_coupon
SET status = 'USED',
    used_order_id = :orderId,
    used_at = NOW(6),
    version = version + 1
WHERE coupon_id = :couponId
  AND member_id = :memberId
  AND status = 'ISSUED'
  AND valid_from <= NOW(6)
  AND valid_until >  NOW(6);
```

결제 실패로 주문이 취소되면 쿠폰을 다시 `ISSUED`로 되돌린다. 이때도 `WHERE status='USED' AND used_order_id=:orderId` 조건을 명시해서 다른 사용자의 쿠폰을 건드리지 않게 한다.

## 프로모션 정책과 가격 스냅샷

프로모션은 시간에 따라 바뀌는 정책이다. "2026-04-21 18:00에 1+1 적용된 가격으로 주문이 들어왔다"는 사실은 그 순간 동결되어야 한다. 그래서 Order 항목에는 다음 스냅샷을 보관한다.

- 적용 정책 ID와 정책 버전(`promotion_id`, `promotion_version`)
- 정책 적용 후 단가(`unit_price_after_promotion`)
- 할인 사유 코드(고객 주문서 표시용)
- 멤버십 등급 기준 시각

정책 마스터 테이블을 직접 join하지 않고 스냅샷을 읽는다. 이렇게 해야 정책이 변경되거나 폐기되어도 과거 주문 금액이 흔들리지 않고, 정산/환불 시점에 동일한 금액으로 계산할 수 있다.

## 재고와 매장 가용성

F&B 도메인의 재고는 e-Commerce 일반과 다르다. 매장 단위 한정 수량 + 운영시간이 변수다. 두 가지 패턴이 나뉜다.

- **사전 차감(Reserve-then-Confirm)**: 결제 진입 시 재고를 잠시 예약(`reserved_qty++`), 결제 승인 후 확정(`reserved_qty--`, `sold_qty++`), 실패 시 예약 해제. 동시성이 높은 인기 상품은 이 패턴이 안전하다.
- **사후 차감**: 결제 승인 직후 재고 차감. 단순하지만 동시 승인 폭주 시 음수 재고가 날 수 있어서 `qty - sold_qty > 0` 조건부 update가 필수다.

매장 운영시간 검증은 **주문 생성 시점과 매장 수락 시점에 두 번** 한다. 사용자가 마감 1분 전에 주문을 넣고 결제 진행 중에 마감 시각이 지나면 매장 수락 단계에서 거절한다. 이 거절을 자연스러운 흐름으로 처리할 수 있어야 운영자가 야간에 호출당하지 않는다.

## 정합성, 멱등성, Outbox/Saga

서비스 경계가 여러 개라면 분산 트랜잭션 대신 **Outbox 패턴 + 보상 트랜잭션(Saga)** 조합을 쓴다. 면접에서는 이 부분이 가장 자주 나온다.

### Outbox 패턴 한 줄 요약

도메인 변경과 메시지 발행을 같은 RDB 트랜잭션에 묶고, 별도 발행기(publisher)가 outbox 테이블을 폴링/CDC해서 Kafka로 보낸다. 메시지 발행 자체에는 멱등키(`event_id`)를 함께 싣는다.

```sql
CREATE TABLE outbox_message (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  aggregate    VARCHAR(64)  NOT NULL,
  aggregate_id VARCHAR(64)  NOT NULL,
  event_type   VARCHAR(64)  NOT NULL,
  payload      JSON         NOT NULL,
  event_id     CHAR(36)     NOT NULL UNIQUE,
  created_at   DATETIME(6)  NOT NULL,
  published_at DATETIME(6)  NULL,
  KEY idx_published (published_at, id)
) ENGINE=InnoDB;
```

Order의 `approvePayment()` 결과로 발생한 `OrderPaymentApprovedEvent`는 같은 트랜잭션에서 `outbox_message`에 INSERT된다. 매장 알림 서비스, 적립 서비스, 정산 서비스는 Kafka 컨슈머로 이 이벤트를 받아 자기 일을 처리한다.

### Saga: 매장 거절 시 결제 보상 취소

매장 거절은 분산 환경의 정상 시나리오다.

1. `OrderPaymentApprovedEvent` 수신 → 매장 알림 서비스가 매장 POS에 주문 전달
2. 매장이 거절(재료 부족, 마감 임박) → `StoreRejectedEvent` 발행
3. 결제 서비스가 컨슈머로 받아 PG 취소 호출 → `PaymentCanceledEvent` 발행
4. 주문 서비스가 받아 Order 상태를 `CANCELED_BY_STORE`로 전이, 쿠폰 복구 이벤트 발행

각 단계는 멱등해야 한다. 같은 이벤트가 중복 도착해도 동일 결과여야 한다. 결제 취소 컨슈머는 `(orderId, paymentId)` 기준으로 이미 취소 이력이 있으면 no-op으로 끝낸다.

## 멱등성 처리 패턴

멱등키는 사용자 입력 단계부터 일관되게 흐르게 한다.

- 클라이언트가 주문 생성 요청 시 `Idempotency-Key` 헤더 부여
- 서버는 `(member_id, idempotency_key)` 유니크 제약 테이블에 INSERT 시도
- INSERT 성공 시 새 주문 생성, 실패(중복키)면 기존 주문을 다시 응답
- Kafka 컨슈머는 `processed_event(event_id PK)` 테이블로 중복 차단

멱등키 없이 "재시도하면 안 된다"는 안내로 해결하려는 설계는 모바일 네트워크 환경에서 무너진다.

## Bad vs Improved 예제

### 주문 생성: 잘못된 패턴

```java
// 안 좋음: 정책 join, 동시성 무방비, 이벤트 발행 따로
public OrderId createOrder(CreateOrderCommand cmd) {
    Promotion promo = promotionRepository.findActive(cmd.productId());
    int price = promo.applyTo(productRepository.priceOf(cmd.productId()));
    Coupon coupon = couponRepository.find(cmd.couponId());
    if (coupon.isUsed()) throw new IllegalStateException();
    coupon.markUsed();                       // 같은 트랜잭션 안에서만 안전
    couponRepository.save(coupon);
    Order order = Order.create(cmd, price);
    orderRepository.save(order);
    kafkaTemplate.send("order.created", order); // <-- 트랜잭션 밖
    return order.id();
}
```

문제: 쿠폰 사용 검사가 SELECT 후 UPDATE 분리, 가격 스냅샷 미보관, Kafka 발행이 트랜잭션 밖이라 커밋 후 발행 실패 시 사라진다.

### 주문 생성: 개선된 패턴

```java
@Transactional
public OrderId createOrder(CreateOrderCommand cmd) {
    PriceSnapshot snapshot = pricingService.snapshotFor(cmd);
    int affected = couponRepository.tryUse(cmd.couponId(), cmd.memberId(), cmd.orderId());
    if (affected == 0) throw new CouponAlreadyUsedException(cmd.couponId());
    Order order = Order.create(cmd, snapshot);
    orderRepository.save(order);
    outboxPublisher.append(new OrderCreatedEvent(order.id(), snapshot));
    return order.id();
}
```

차이: 쿠폰은 조건부 UPDATE 한 번으로 검사+사용 동시 처리, 가격은 스냅샷, 이벤트는 outbox에 같이 커밋.

## 로컬 실습 환경 구성

MySQL 8 + Kafka(KRaft 모드) + Spring Boot 한 개 모듈로 작은 실습이 가능하다.

`docker-compose.yml`

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: shop
    ports: ["3306:3306"]
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_0900_ai_ci
  kafka:
    image: bitnami/kafka:3.7
    environment:
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: controller,broker
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
    ports: ["9092:9092"]
```

스키마 초기화

```sql
CREATE TABLE orders (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no      CHAR(20) NOT NULL UNIQUE,
  member_id     BIGINT NOT NULL,
  status        VARCHAR(32) NOT NULL,
  total_amount  INT NOT NULL,
  created_at    DATETIME(6) NOT NULL,
  KEY idx_member_created (member_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE issued_coupon (
  coupon_id     BIGINT PRIMARY KEY,
  member_id     BIGINT NOT NULL,
  status        VARCHAR(16) NOT NULL,
  used_order_id BIGINT NULL,
  used_at       DATETIME(6) NULL,
  valid_from    DATETIME(6) NOT NULL,
  valid_until   DATETIME(6) NOT NULL,
  version       INT NOT NULL DEFAULT 0,
  KEY idx_member_status (member_id, status)
) ENGINE=InnoDB;
```

실습 시나리오

1. 같은 쿠폰을 두 세션에서 동시에 사용 시도 → 한 쪽만 성공함을 확인.
2. 결제 승인 후 매장 거절 이벤트를 임의로 발행 → Order 상태가 `CANCELED_BY_STORE`로 전이되고 쿠폰이 `ISSUED`로 복구되는지 확인.
3. Outbox publisher를 끄고 주문 생성 → outbox에는 쌓이지만 컨슈머에는 안 가는 상태 확인. 다시 켜면 누락 없이 따라잡는지 확인.
4. 결제 컨슈머에 같은 이벤트를 두 번 흘려서 환불이 한 번만 일어나는지 확인.

## Kafka Outbox·캐시 정합성·장애 대응 경험을 e-Commerce 언어로 옮기는 답변 예시

### 질문: "주문/결제 흐름에서 데이터 정합성을 어떻게 지킬 건가요"

> 핵심은 분산 트랜잭션을 만들지 않는 거라고 봅니다. 도메인 변경과 메시지 발행을 같은 RDB 트랜잭션에 묶는 Outbox 패턴을 기본으로 두고, 그 다음 단계는 Saga로 보상합니다. 이전 업무에서 도메인 변경과 외부 시스템 알림이 분리된 상태에서 메시지가 누락되는 사고를 겪었고, 이후 Outbox로 표준화하면서 누락이 잡혔습니다. e-Commerce에서는 주문 생성·결제 승인·매장 통보·적립이 각자의 책임이라 이 패턴이 그대로 들어맞습니다. 매장 거절은 Saga의 보상 트랜잭션 트리거로 보고, 결제 취소·쿠폰 복구·재고 복구를 멱등 컨슈머로 잇습니다.

### 질문: "캐시 정합성은 어떻게 다루겠습니까"

> 상품 단가, 매장 운영시간, 멤버십 등급 같은 읽기 비중이 큰 데이터를 캐시 대상으로 봅니다. 다만 주문 시점 가격은 캐시에서 읽되 **주문 객체 안에 스냅샷으로 저장**합니다. 정책이 바뀌어도 과거 주문이 흔들리면 안 되니까요. 캐시 갱신은 변경 시점에 publish-then-invalidate로 흘리고, TTL 안전장치를 함께 둬서 invalidate 누락 시에도 자동 회복되게 합니다. 과거에 캐시 stampede로 결제 직전 단가 조회가 폭주하면서 DB 부하가 튄 적이 있어서, 그 뒤로는 단건 캐시 + 짧은 TTL + jitter 패턴으로 정착시켰습니다.

### 질문: "결제 PG 장애가 나면 어떻게 복구하시겠어요"

> 가장 중요한 건 사용자에게 "결제됐는지 안 됐는지" 모호한 상태를 보여주지 않는 겁니다. 그래서 PG 호출 직전에 "승인 요청 중" 레코드를 자체 DB에 먼저 커밋하고, 응답을 못 받았을 때를 대비한 reconciliation job을 따로 운영합니다. 이 잡이 PG에 거래 상태를 다시 조회해서 자체 DB와 맞추고, 사용자에게는 "결제 확인 중" 상태로 노출합니다. 운영 모니터링은 PG 응답시간 p99, 승인 실패율, reconciliation 보정 건수, outbox lag 네 가지를 1분 단위로 봅니다. 이 지표 중 하나라도 임계 초과하면 결제 수단별로 트래픽을 일시 분산하거나 매장 알림 큐를 늦추는 식으로 대응합니다.

## 운영 모니터링 체크리스트

- 결제 승인 후 매장 수락까지의 p95 시간 (5분 넘으면 운영 알림)
- outbox 미발행 메시지 lag (1분 이상 적체 시 알람)
- 쿠폰 사용/복구 미스매치 건수 (일 단위 reconciliation)
- 주문 상태 비정상 분포 (`PAYMENT_PENDING`이 1시간 이상 머무는 건수)
- PG 멱등키 충돌 발생률
- 매장 거절 사유 코드별 비율 (재료 부족 vs 마감 vs 시스템 오류)

## 학습 체크리스트

- [ ] Order Aggregate 안에 결제·재고·매장 변경을 직접 두지 않는 이유를 설명할 수 있다.
- [ ] 주문 상태머신을 enum + 전이 규칙으로 구현하고 잘못된 전이에 예외를 던질 수 있다.
- [ ] 쿠폰 사용을 SELECT-then-UPDATE 없이 조건부 UPDATE 한 번으로 만들 수 있다.
- [ ] 가격/정책 스냅샷을 Order에 동결하는 이유와 방법을 설명할 수 있다.
- [ ] Outbox 테이블 스키마를 직접 작성하고 publisher 흐름을 그림으로 그릴 수 있다.
- [ ] 매장 거절 시 결제 취소까지 이어지는 Saga 단계를 멱등하게 구현할 수 있다.
- [ ] PG 응답 누락 시 reconciliation 잡으로 복구하는 흐름을 답변할 수 있다.
- [ ] 캐시 정합성에서 stampede·invalidate 누락에 대한 안전장치를 설명할 수 있다.
- [ ] 운영 모니터링 지표 4-6개를 근거와 함께 제시할 수 있다.
- [ ] 본인의 Kafka Outbox·캐시·장애 대응 경험을 e-Commerce 도메인 언어로 30초 안에 번역할 수 있다.
