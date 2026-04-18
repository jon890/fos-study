# [초안] 분산 트랜잭션과 Outbox 패턴 — 왜 2PC를 피하고 어떻게 대신할 것인가

## 왜 이 주제가 중요한가

커머스 플랫폼 백엔드에서 주문이 생성되는 순간 무슨 일이 일어나야 하는가. 재고를 차감해야 한다. 결제를 요청해야 한다. 쿠폰이 사용됐다면 쿠폰 상태를 소진으로 바꿔야 한다. 알림을 보내야 한다. 포인트가 적립돼야 한다. 이 중 하나라도 실패하면 시스템 전체가 일관성을 잃는다.

단일 MySQL 데이터베이스 하나에 모든 테이블이 들어있다면 ACID 트랜잭션 하나로 이 모든 것을 해결할 수 있다. 그런데 CJ OliveYoung 규모의 웰니스 플랫폼은 그렇지 않다. 주문 서비스, 재고 서비스, 결제 서비스, 쿠폰 서비스, 알림 서비스가 각자 자신의 데이터베이스를 가지고 독립적으로 배포된다. 서비스 경계를 넘는 순간 단일 DB 트랜잭션은 쓸 수 없다.

이 상황에서 "어떻게 일관성을 유지할 것인가"라는 질문에 대한 실전 답이 바로 Outbox 패턴이다. 시니어 인터뷰에서 이 주제가 나오면 단순히 개념만 아는 사람과 실제로 구현해본 사람이 극명하게 갈린다. 이 문서는 그 차이를 만드는 수준까지 설명한다.

---

## 분산 트랜잭션이 왜 어려운가

### 단일 DB에서 마이크로서비스로 전환할 때 생기는 문제

단일 DB 환경에서는 다음 코드가 아무 문제 없이 동작한다.

```java
@Transactional
public void createOrder(OrderRequest request) {
    Order order = orderRepository.save(new Order(request));
    inventoryRepository.decrease(request.getProductId(), request.getQuantity());
    couponRepository.markUsed(request.getCouponId());
    // 하나라도 실패하면 전부 롤백
}
```

문제는 `inventoryRepository`가 실제로는 별도 서비스에 HTTP 호출을 하고, `couponRepository`는 또 다른 서비스에 gRPC를 날리는 구조가 되는 순간이다. `@Transactional`은 더 이상 이 세 개를 묶어주지 않는다.

주문은 DB에 저장됐는데 재고 차감 API 호출이 실패했다. 이제 어떻게 할 것인가? 주문을 롤백하려면 이미 커밋된 DB 레코드를 지워야 한다. 그런데 그 사이에 다른 프로세스가 그 주문을 읽었을 수도 있다. 보상 트랜잭션을 수행해도 완벽하지 않다.

### 2PC (Two-Phase Commit) 가 있지 않는가

2PC는 분산 트랜잭션의 고전적 해결책이다. 코디네이터가 모든 참여자에게 Prepare를 보내고, 전원이 OK를 보내면 Commit, 하나라도 거절하면 Abort한다.

**Phase 1 (Prepare):** 코디네이터 → 참여자들: "커밋할 준비됐어?"  
**Phase 2 (Commit/Abort):** 모든 참여자 OK → Commit 전파, 하나라도 No → Abort 전파

이론상 완벽해 보인다. 그런데 실전 시스템에서 2PC를 피하는 이유가 분명히 있다.

**문제 1: 블로킹 프로토콜이다.** Phase 1과 Phase 2 사이에 코디네이터가 죽으면 참여자들은 영원히 대기한다. Prepare 메시지를 받고 락을 건 상태에서 코디네이터 응답을 기다리는 참여자는 그 자원을 아무에게도 해제하지 못한다.

**문제 2: 성능이 나쁘다.** 모든 참여자가 동기적으로 응답할 때까지 기다려야 한다. 서비스가 10개라면 가장 느린 서비스의 응답 시간이 전체 트랜잭션의 응답 시간이 된다.

**문제 3: 마이크로서비스 아키텍처와 맞지 않는다.** Kafka, Redis, S3 같은 서비스는 XA 프로토콜을 지원하지 않는다. HTTP API를 제공하는 외부 결제 PG는 당연히 2PC에 참여할 수 없다.

**문제 4: 운영이 너무 복잡하다.** 코디네이터 장애 복구, 참여자 재시작, 인-더블트(in-doubt) 트랜잭션 처리가 DBA 수준의 개입을 요구한다.

결론: 대부분의 실전 MSA 시스템에서 2PC는 쓰지 않는다.

---

## Saga 패턴 — 결과적 일관성의 기반

2PC 대신 널리 쓰이는 패턴이 Saga다. Saga는 분산 트랜잭션을 여러 개의 로컬 트랜잭션 시퀀스로 분해하고, 각 단계 실패 시 이전 단계들을 보상 트랜잭션으로 되돌린다.

### Choreography vs Orchestration

**Choreography Saga:** 각 서비스가 자신이 처리한 결과를 이벤트로 발행하고, 다음 서비스는 그 이벤트를 구독해서 자신의 처리를 수행한다. 중앙 조율자가 없다.

```
주문서비스 → OrderCreated 이벤트 발행
재고서비스 ← OrderCreated 구독 → StockReserved 이벤트 발행
결제서비스 ← StockReserved 구독 → PaymentCompleted 이벤트 발행
```

**Orchestration Saga:** 중앙 Saga Orchestrator가 각 서비스에 명시적으로 커맨드를 보내고 응답을 받아 다음 단계를 결정한다.

```
SagaOrchestrator
  → ReserveStockCommand → 재고서비스
  ← StockReservedEvent
  → ProcessPaymentCommand → 결제서비스
  ← PaymentCompletedEvent
  → SendNotificationCommand → 알림서비스
```

Choreography는 서비스 간 결합도가 낮지만 전체 흐름 파악이 어렵다. Orchestration은 흐름이 명확하지만 오케스트레이터가 병목이 될 수 있다.

### 보상 트랜잭션의 한계

Saga에서 보상 트랜잭션은 완벽한 롤백이 아니다. 재고를 차감한 다음 결제가 실패했을 때 재고를 다시 늘리는 보상 트랜잭션을 수행하면 된다. 그런데 그 사이에 다른 사용자가 그 재고를 보고 주문을 시도했을 수도 있다. 이게 바로 결과적 일관성(eventual consistency)의 의미다. 일시적으로 비일관된 상태를 허용하되, 결국은 일관된 상태로 수렴한다.

---

## Outbox 패턴의 핵심 아이디어

Saga를 구현하려면 로컬 트랜잭션이 완료된 후 이벤트를 발행해야 한다. 문제는 DB 저장과 Kafka 발행이 원자적이지 않다는 점이다.

### 고전적인 실수

```java
@Transactional
public void createOrder(OrderRequest request) {
    Order order = orderRepository.save(new Order(request));
    // DB 커밋 후
    kafkaTemplate.send("order-created", new OrderCreatedEvent(order));
    // Kafka 발행 실패하면? DB는 이미 커밋됨
}
```

여기서 두 가지 실패 시나리오가 있다.

**시나리오 1:** DB 저장 성공 → Kafka 발행 실패. 주문은 생성됐지만 재고 서비스, 결제 서비스는 이벤트를 받지 못한다. 주문은 영원히 처리되지 않는다.

**시나리오 2:** 만약 `@Transactional` 안에서 Kafka 발행을 하면, Kafka에 이미 메시지가 들어갔는데 DB 롤백이 발생한다. 소비자 서비스는 존재하지 않는 주문에 대한 이벤트를 받는다.

어느 쪽이든 데이터 불일치다.

### Outbox 패턴의 해결책

핵심 아이디어는 단순하다. **이벤트를 Kafka가 아니라 같은 DB의 Outbox 테이블에 저장한다.** DB 트랜잭션 안에서 비즈니스 데이터와 이벤트를 함께 저장하면 원자성이 보장된다. 그 다음 별도 프로세스가 Outbox 테이블을 읽어서 Kafka에 발행한다.

```
[주문 서비스 DB 트랜잭션]
  orders 테이블에 INSERT
  outbox 테이블에 INSERT (이벤트 페이로드 포함)
  → 커밋 (원자적)

[별도 Outbox Publisher]
  outbox 테이블에서 미발행 이벤트 조회
  → Kafka에 발행
  → 발행 완료 표시 (published_at 업데이트)
```

이렇게 하면 DB 커밋과 이벤트 발행이 분리된다. DB 트랜잭션이 성공하면 이벤트는 반드시 Outbox 테이블에 존재한다. Outbox Publisher가 일시적으로 Kafka에 발행하지 못해도 재시도하면 된다.

---

## 실전 구현 — Java + Spring + Kafka

### Outbox 테이블 스키마

```sql
CREATE TABLE outbox_events (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id   VARCHAR(100) NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        JSON         NOT NULL,
    created_at     DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    published_at   DATETIME(6)  NULL,
    INDEX idx_outbox_unpublished (published_at, created_at)
);
```

`aggregate_type`은 어느 도메인의 이벤트인지(`ORDER`, `PAYMENT` 등), `aggregate_id`는 해당 도메인 객체의 ID, `event_type`은 이벤트 종류(`ORDER_CREATED`, `ORDER_CANCELLED` 등)다.

### 엔티티 및 리포지토리

```java
@Entity
@Table(name = "outbox_events")
public class OutboxEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String aggregateType;

    @Column(nullable = false)
    private String aggregateId;

    @Column(nullable = false)
    private String eventType;

    @Column(nullable = false, columnDefinition = "JSON")
    private String payload;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    private LocalDateTime publishedAt;

    public static OutboxEvent of(String aggregateType, String aggregateId,
                                  String eventType, Object payloadObject) {
        OutboxEvent event = new OutboxEvent();
        event.aggregateType = aggregateType;
        event.aggregateId = aggregateId;
        event.eventType = eventType;
        event.payload = JsonUtils.toJson(payloadObject);
        event.createdAt = LocalDateTime.now();
        return event;
    }

    public boolean isPublished() {
        return publishedAt != null;
    }

    public void markPublished() {
        this.publishedAt = LocalDateTime.now();
    }
}
```

```java
public interface OutboxEventRepository extends JpaRepository<OutboxEvent, Long> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT e FROM OutboxEvent e WHERE e.publishedAt IS NULL ORDER BY e.createdAt ASC")
    List<OutboxEvent> findUnpublishedWithLock(Pageable pageable);
}
```

### 주문 서비스 — 같은 트랜잭션에 이벤트 저장

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final OutboxEventRepository outboxEventRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public Order createOrder(CreateOrderCommand command) {
        Order order = Order.create(command);
        orderRepository.save(order);

        OrderCreatedEvent event = OrderCreatedEvent.from(order);
        outboxEventRepository.save(
            OutboxEvent.of("ORDER", order.getId().toString(), "ORDER_CREATED", event)
        );

        return order;
    }
}
```

중요한 점은 `kafkaTemplate.send()`가 없다는 것이다. 이 트랜잭션이 커밋되면 주문과 이벤트가 동시에 DB에 저장된다. Kafka 발행은 다른 프로세스의 몫이다.

---

## Polling Publisher vs CDC

Outbox 테이블에서 Kafka로 발행하는 방법은 두 가지다.

### Polling Publisher

별도 스케줄러가 주기적으로 Outbox 테이블을 폴링한다.

```java
@Component
@RequiredArgsConstructor
public class OutboxPollingPublisher {

    private final OutboxEventRepository outboxEventRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final TransactionTemplate transactionTemplate;

    @Scheduled(fixedDelay = 1000)  // 1초마다 실행
    public void publishPendingEvents() {
        transactionTemplate.execute(status -> {
            List<OutboxEvent> events = outboxEventRepository
                .findUnpublishedWithLock(PageRequest.of(0, 100));

            for (OutboxEvent event : events) {
                String topic = resolveTopicName(event.getEventType());
                try {
                    kafkaTemplate.send(topic, event.getAggregateId(), event.getPayload())
                        .get(5, TimeUnit.SECONDS);  // 동기적으로 확인
                    event.markPublished();
                } catch (Exception e) {
                    log.error("Failed to publish event: {}", event.getId(), e);
                    // 이번 배치에서 실패하면 다음 폴링에서 재시도
                }
            }
            return null;
        });
    }

    private String resolveTopicName(String eventType) {
        return switch (eventType) {
            case "ORDER_CREATED" -> "order-events";
            case "ORDER_CANCELLED" -> "order-events";
            case "PAYMENT_COMPLETED" -> "payment-events";
            default -> "general-events";
        };
    }
}
```

**장점:** 구현이 단순하다. 추가 인프라가 필요 없다.  
**단점:** 폴링 주기만큼 지연이 생긴다. DB에 폴링 부하가 생긴다. 인스턴스가 여러 개라면 중복 발행 방지를 위한 락이 필요하다.

### CDC (Change Data Capture) — Debezium

CDC는 DB의 바이너리 로그(MySQL의 binlog)를 읽어서 변경 사항을 스트리밍한다. Debezium은 MySQL binlog를 읽어 Kafka Connect 형태로 Kafka에 발행한다.

```json
{
  "connector.class": "io.debezium.connector.mysql.MySqlConnector",
  "database.hostname": "mysql",
  "database.port": "3306",
  "database.user": "debezium",
  "database.password": "dbz",
  "database.server.name": "order-db",
  "table.include.list": "order_service.outbox_events",
  "transforms": "outbox",
  "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
  "transforms.outbox.table.field.event.id": "id",
  "transforms.outbox.table.field.event.key": "aggregate_id",
  "transforms.outbox.table.field.event.payload": "payload",
  "transforms.outbox.route.by.field": "aggregate_type"
}
```

**장점:** 실시간에 가까운 지연. DB 폴링 부하 없음. 트랜잭션 순서가 binlog 순서로 보장됨.  
**단점:** Debezium, Kafka Connect 인프라가 필요하다. 운영 복잡도가 높다. MySQL 설정에서 `binlog_format=ROW`가 필요하다.

소규모~중규모 시스템에서는 Polling Publisher가 충분히 실용적이다. 대규모, 낮은 레이턴시 요구사항이라면 CDC를 선택한다.

---

## 실패 시나리오와 대응

### 시나리오 1: Outbox Publisher가 Kafka 발행 후 `published_at` 업데이트 전에 죽는다

Kafka에는 이벤트가 이미 들어갔는데 DB에는 `published_at`이 null로 남아있다. 다음 폴링에서 같은 이벤트를 다시 발행한다. 소비자는 같은 이벤트를 두 번 받는다.

**해결책: 소비자의 멱등성(idempotency) 보장.** 이벤트에 고유 ID를 포함시키고, 소비자는 이미 처리한 이벤트 ID를 기록한다.

```java
@KafkaListener(topics = "order-events")
public void handleOrderEvent(ConsumerRecord<String, String> record) {
    OrderEvent event = deserialize(record.value());

    // 이미 처리한 이벤트인지 확인
    if (processedEventRepository.existsByEventId(event.getEventId())) {
        log.info("Duplicate event ignored: {}", event.getEventId());
        return;
    }

    // 처리 + 처리 기록을 같은 트랜잭션에서
    processedEventRepository.save(new ProcessedEvent(event.getEventId()));
    inventoryService.reserveStock(event.getOrderId(), event.getItems());
}
```

### 시나리오 2: 소비자가 처리 중 죽는다

Kafka는 오프셋 커밋 전에 소비자가 죽으면 재전달한다. 소비자가 멱등하게 구현돼 있다면 재처리해도 문제 없다.

### 시나리오 3: Outbox 테이블이 계속 쌓인다

Kafka가 장시간 다운되거나 Publisher가 계속 실패하면 Outbox 테이블에 미발행 이벤트가 쌓인다. 이 경우 알림을 받아야 한다.

```sql
-- 10분 이상 발행되지 않은 이벤트가 있으면 알림
SELECT COUNT(*) FROM outbox_events 
WHERE published_at IS NULL 
  AND created_at < DATE_SUB(NOW(), INTERVAL 10 MINUTE);
```

이 쿼리를 모니터링 대시보드에 연결하거나 AlertManager에 등록한다.

---

## 메시지 순서와 중복 처리

### Kafka에서 순서 보장

Kafka는 같은 파티션 내에서만 순서를 보장한다. 주문 ID를 파티션 키로 사용하면 같은 주문의 이벤트는 항상 같은 파티션으로 간다.

```java
kafkaTemplate.send(
    new ProducerRecord<>("order-events",
        null,                    // partition: null → key로 결정
        order.getId().toString(), // key: 파티션 결정에 사용
        eventJson
    )
);
```

파티션 키가 다르면 `ORDER_CREATED`가 `ORDER_CANCELLED`보다 늦게 처리될 수 있다. 다른 주문의 이벤트 간에는 순서가 보장되지 않는다. 이는 정상이다.

### 중복 발행 (At-Least-Once Delivery)

Outbox 패턴은 기본적으로 At-Least-Once를 제공한다. 적어도 한 번은 발행된다는 뜻이고, 경우에 따라 두 번 이상 발행될 수 있다는 뜻이기도 하다. 소비자가 멱등하게 구현되면 이 문제는 해결된다.

정확히 한 번(Exactly-Once)을 원하면 Kafka Transactions를 사용해야 하는데, 그 경우 Kafka Producer와 Consumer 모두 트랜잭션 설정이 필요하고 처리량이 낮아진다. 대부분의 비즈니스 이벤트에서는 At-Least-Once + 소비자 멱등성 조합이 실용적이다.

---

## 커머스/플랫폼 시나리오에 적용

### 주문 생성 플로우

```
1. 주문서비스: orders INSERT + outbox(ORDER_CREATED) INSERT [같은 트랜잭션]
2. Outbox Publisher: ORDER_CREATED → order-events 토픽 발행
3. 재고서비스: ORDER_CREATED 소비 → 재고 차감 + outbox(STOCK_RESERVED) INSERT
4. 결제서비스: STOCK_RESERVED 소비 → 결제 요청 + outbox(PAYMENT_COMPLETED) INSERT
5. 주문서비스: PAYMENT_COMPLETED 소비 → 주문 상태를 CONFIRMED로 변경
6. 알림서비스: PAYMENT_COMPLETED 소비 → 푸시 알림 발송
```

### 결제 실패 시 보상 트랜잭션 플로우

```
결제서비스: 결제 실패 → outbox(PAYMENT_FAILED) INSERT
재고서비스: PAYMENT_FAILED 소비 → 차감했던 재고 복구 + outbox(STOCK_RELEASED) INSERT
쿠폰서비스: PAYMENT_FAILED 소비 → 사용 처리한 쿠폰 취소
주문서비스: PAYMENT_FAILED 소비 → 주문 상태를 PAYMENT_FAILED로 변경
알림서비스: PAYMENT_FAILED 소비 → 결제 실패 알림 발송
```

여기서 중요한 점은 재고 복구와 쿠폰 취소가 `PAYMENT_FAILED` 이벤트 하나를 각각 독립적으로 소비한다는 것이다. 서비스 간 직접 호출이 없다.

---

## 나쁜 구현 vs 개선된 구현

### Bad: 트랜잭션 밖에서 Kafka 발행

```java
@Transactional
public Order createOrder(CreateOrderCommand command) {
    Order order = orderRepository.save(Order.create(command));
    return order;
}

// 트랜잭션 커밋 후 호출자가 별도로 이벤트 발행
public void publishOrderCreated(Order order) {
    kafkaTemplate.send("order-events", new OrderCreatedEvent(order));
}
```

이 코드는 `createOrder`와 `publishOrderCreated` 사이에 프로세스가 죽으면 이벤트가 유실된다. 호출 순서에 대한 강제가 없어서 개발자 실수도 유발한다.

### Bad: 트랜잭션 안에서 Kafka 발행

```java
@Transactional
public Order createOrder(CreateOrderCommand command) {
    Order order = orderRepository.save(Order.create(command));
    kafkaTemplate.send("order-events", new OrderCreatedEvent(order)).get();
    // Kafka는 성공했는데 이후 로직에서 예외 발생 → DB 롤백, Kafka는 이미 발행됨
    inventoryClient.reserve(order); // 만약 여기서 예외가 나면?
    return order;
}
```

Kafka 발행이 완료됐는데 그 이후 코드에서 예외가 터지면 DB는 롤백되지만 Kafka 메시지는 이미 나가있다.

### Good: Outbox 패턴으로 원자성 보장

```java
@Transactional
public Order createOrder(CreateOrderCommand command) {
    Order order = orderRepository.save(Order.create(command));
    outboxEventRepository.save(
        OutboxEvent.of("ORDER", order.getId().toString(), "ORDER_CREATED",
            OrderCreatedEvent.from(order))
    );
    return order;
    // 트랜잭션이 커밋되면 order와 outbox event가 함께 저장됨
    // Kafka 발행은 별도 Publisher의 책임
}
```

---

## 로컬 실습 환경 구성

### Docker Compose로 MySQL + Kafka 구성

```yaml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: order_service
    ports:
      - "3306:3306"
    command: --binlog-format=ROW --log-bin=mysql-bin --server-id=1

  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

### Spring Boot application.yml

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/order_service
    username: root
    password: root
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      acks: all
      retries: 3
    consumer:
      group-id: inventory-service
      auto-offset-reset: earliest
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.apache.kafka.common.serialization.StringDeserializer
```

### 실습 시나리오

```bash
# 1. 주문 생성 API 호출
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"productId": 1, "quantity": 2, "userId": 100}'

# 2. Outbox 테이블에 이벤트가 저장됐는지 확인
mysql -u root -proot order_service \
  -e "SELECT id, aggregate_type, event_type, published_at FROM outbox_events ORDER BY id DESC LIMIT 5;"

# 3. Kafka 토픽에서 이벤트 확인
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic order-events --from-beginning

# 4. Publisher가 실행된 후 published_at이 채워지는지 확인
mysql -u root -proot order_service \
  -e "SELECT id, event_type, published_at FROM outbox_events WHERE published_at IS NOT NULL ORDER BY id DESC LIMIT 5;"
```

---

## 인터뷰 답변 프레임

### 예상 질문: "주문 서비스에서 재고와 결제를 어떻게 동기화하나요?"

**미숙한 답:** "Kafka로 이벤트를 보내면 각 서비스가 처리합니다."

**시니어 수준 답:**

"먼저 DB 저장과 이벤트 발행 사이의 원자성 문제를 다뤄야 합니다. 단순히 DB 커밋 후 Kafka로 발행하면, 둘 사이에 프로세스가 죽었을 때 이벤트가 유실됩니다. 반대로 트랜잭션 안에서 Kafka 발행을 하면 Kafka 발행 성공 후 DB 롤백 시 이미 발행된 메시지를 되돌릴 수 없습니다.

이 문제를 해결하기 위해 Outbox 패턴을 씁니다. 비즈니스 데이터와 이벤트를 같은 로컬 트랜잭션으로 DB에 저장하고, 별도 Publisher가 Outbox 테이블을 읽어 Kafka에 발행합니다. At-Least-Once 발행이 되기 때문에 소비자 쪽에서 멱등성을 구현합니다.

보상 트랜잭션 흐름은 Saga 패턴으로 처리하는데, 저는 서비스 수가 많지 않을 때는 Choreography, 복잡한 흐름이라면 Orchestration을 선택합니다. CJ OliveYoung처럼 주문-재고-결제-쿠폰-알림이 모두 엮이는 플로우라면 Orchestration Saga로 Saga Orchestrator 서비스를 두는 게 전체 흐름 파악과 장애 추적에 유리합니다."

### 예상 질문: "Outbox 패턴의 단점은?"

"Outbox 테이블을 관리해야 한다는 운영 부담이 있습니다. 발행 완료된 이벤트는 주기적으로 정리해야 하고, Publisher 프로세스 모니터링도 필요합니다. 폴링 방식은 1~2초 수준의 지연이 있는데, 그 정도 지연이 허용되지 않는 경우라면 Debezium CDC를 도입해야 하고 그 경우 Kafka Connect 인프라가 추가됩니다.

2PC와 비교하면 엄격한 일관성을 포기하고 결과적 일관성을 받아들이는 설계입니다. 잠깐 주문이 CONFIRMED인데 재고가 아직 차감되지 않은 상태가 존재할 수 있습니다. 이를 허용하도록 비즈니스 로직과 모니터링이 설계돼야 합니다."

### 예상 질문: "2PC는 왜 쓰지 않나요?"

"2PC는 블로킹 프로토콜이라 코디네이터 장애 시 모든 참여자가 락을 걸고 대기합니다. 응답 시간이 가장 느린 참여자에 의해 전체 트랜잭션 성능이 제한됩니다. 무엇보다 HTTP REST API나 Kafka 같은 외부 시스템은 XA 프로토콜에 참여할 수 없어서 실제 MSA 환경에서는 쓸 수 없는 경우가 많습니다."

---

## 체크리스트

- [ ] Outbox 테이블의 역할을 설명할 수 있다: 로컬 트랜잭션 안에서 이벤트를 저장하여 원자성 보장
- [ ] Polling Publisher와 CDC의 차이점 및 선택 기준을 설명할 수 있다
- [ ] At-Least-Once 발행과 소비자 멱등성의 관계를 설명할 수 있다
- [ ] Choreography Saga와 Orchestration Saga의 트레이드오프를 설명할 수 있다
- [ ] 2PC가 실전 MSA에서 적합하지 않은 구체적 이유 3가지를 말할 수 있다
- [ ] 결제 실패 시 보상 트랜잭션 플로우를 주문-재고-쿠폰 흐름으로 설명할 수 있다
- [ ] 같은 이벤트 ID를 두 번 처리했을 때 안전한 소비자 코드를 작성할 수 있다
- [ ] Outbox 테이블 모니터링 쿼리를 작성하고 어떤 지표를 봐야 하는지 설명할 수 있다
- [ ] Kafka 파티션 키 선택이 메시지 순서에 미치는 영향을 설명할 수 있다
- [ ] `@Transactional` 안에서 Kafka 발행을 하면 안 되는 이유를 코드 레벨로 설명할 수 있다
