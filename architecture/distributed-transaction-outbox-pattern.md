# [초안] 분산 트랜잭션과 Outbox 패턴 — 왜 2PC를 피하고 어떻게 대신할 것인가

## 왜 이 주제가 중요한가

커머스 플랫폼 백엔드에서 주문이 생성되는 순간 무슨 일이 일어나야 하는가. 재고를 차감해야 한다. 결제를 요청해야 한다. 쿠폰이 사용됐다면 쿠폰 상태를 소진으로 바꿔야 한다. 알림을 보내야 한다. 포인트가 적립돼야 한다. 이 중 하나라도 실패하면 시스템 전체가 일관성을 잃는다.

단일 MySQL 데이터베이스 하나에 모든 테이블이 들어있다면 ACID 트랜잭션 하나로 이 모든 것을 해결할 수 있다. 그런데 CJ OliveYoung 규모의 웰니스 플랫폼은 그렇지 않다. 주문 서비스, 재고 서비스, 결제 서비스, 쿠폰 서비스, 알림 서비스가 각자 자신의 데이터베이스를 가지고 독립적으로 배포된다. 서비스 경계를 넘는 순간 단일 DB 트랜잭션은 쓸 수 없다.

이 상황에서 "어떻게 일관성을 유지할 것인가"라는 질문에 대한 실전 답이 바로 Outbox 패턴이다. 그리고 Outbox를 **폴링 방식**으로 낼 것인지, **CDC(Debezium) 방식**으로 낼 것인지는 면접에서 거의 반드시 따라 나오는 후속 질문이다. 시니어 인터뷰에서 이 주제가 나오면 단순히 개념만 아는 사람과 실제로 구현해본 사람이 극명하게 갈린다. 이 문서는 그 차이를 만드는 수준까지 설명한다.

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

여기서 남는 질문이 바로 **"그러면 그 Publisher를 어떻게 만들 것인가"**다. 이 선택이 Outbox 패턴의 운영 난이도와 시스템의 지연 특성 전부를 결정한다.

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

> CDC 방식(Debezium)을 함께 고려한다면 이 스키마에 두 칼럼을 더 둔다:
> - `tracing_id VARCHAR(64)` — 분산 추적 상관관계 유지용
> - `deleted TINYINT(1) DEFAULT 0` — Debezium Outbox EventRouter가 "tombstone 삭제 이벤트" 판단에 활용

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

## 폴링(스케줄러) Publisher vs CDC(Debezium) 심화 비교

Outbox 테이블에서 Kafka로 발행하는 방법은 본질적으로 두 가지 계열이다. 두 방식은 **"구현은 거의 같은 그림"이지만 운영/장애/성능 특성은 완전히 다르다.** 이 차이를 면접에서 정확하게 설명할 수 있어야 한다.

### 한눈에 비교표

| 관점 | 폴링(Scheduler) Publisher | CDC (Debezium + Kafka Connect) |
|---|---|---|
| 구현 난이도 | 낮음 — Spring `@Scheduled` + JPA 쿼리로 끝 | 중~상 — Kafka Connect, Debezium 커넥터, binlog 권한, 스키마 전략 필요 |
| 인프라 부담 | 애플리케이션 인스턴스만 있으면 됨 | Kafka Connect 클러스터, 커넥터 모니터링, Schema Registry(선택) 추가 |
| 지연(Latency) | 폴링 주기에 종속 (보통 500ms ~ 수초) | 수십 ms ~ 수백 ms, 사실상 near real-time |
| DB 부하 | 폴링 쿼리 + 업데이트 + 락 경합이 상시 발생 | binlog 읽기만 하므로 애플리케이션 쿼리 부하 없음 |
| 순서 보장 | `created_at`/PK 기준 정렬에 의존 — 파티션 내 순서까지만 보장 | binlog 기록 순서 그대로 보장 — 강함 |
| 중복 발행 | Publisher 크래시 시점에 따라 쉽게 발생 → 소비자 멱등 필수 | 커넥터 offset commit 실패 시 재시작하며 발생 가능 → 소비자 멱등 필수 |
| 트랜잭션 원자성 표현력 | 이벤트 자체는 원자적, 발행은 느슨 | 여러 로우 변경을 하나의 "transaction boundary"로 묶어 소비자에게 전달 가능 |
| 스키마 변경 대응 | 단순 — 앱 코드와 함께 배포 | Debezium 커넥터 설정/트랜스폼 함께 갱신 필요 |
| 다중 인스턴스 실행 | 락(행 잠금, Shedlock, advisory lock 등) 설계가 반드시 필요 | 커넥터가 단일 리더로 동작 → 별도 락 불필요 |
| 장애 복구 난이도 | 낮음 — `published_at = NULL`을 다시 읽으면 끝 | 중 — binlog offset/커넥터 상태/슬롯 관리 필요, binlog 보존 기간이 리텐션 됨 |
| 관측(Observability) | 쿼리 하나로 lag 측정 용이 | Connect REST API + JMX + lag metric 수집 필요 |
| 외부 DB 접근 권한 | 애플리케이션 DB 유저로 충분 | `REPLICATION CLIENT`, `REPLICATION SLAVE` 권한 + binlog 접근 필요 |
| 멀티 테넌트/멀티 DB | 스케줄러가 DB별로 돌면 됨 | 커넥터를 DB별/샤드별로 두어야 하고 관리 부담 증가 |
| 비용 | 낮음 | 중~상 (Kafka Connect 워커, 모니터링 비용) |
| 팀 학습 곡선 | Spring에 익숙하면 하루 | Kafka Connect/Debezium 운영 경험 필요 |

### 지연 시간(latency)을 제대로 이해하기

폴링 방식은 단순 계산으로 `(평균 지연) ≈ 폴링 주기 / 2 + 처리 시간`이다. 1초 폴링이라면 평균 500ms 전후, 최악 1초 이상의 지연이 항상 존재한다. 폴링 주기를 짧게 하면 지연은 줄지만 DB 쿼리/락 경합 비용이 선형적으로 증가한다. 100ms 주기로 내려가면 애플리케이션-DB 사이에 지속적인 읽기 부하가 생기고, HA를 위해 인스턴스를 늘리면 락 경합이 더 심해진다.

CDC는 MySQL binlog가 커밋 직후 쓰이는 순간부터 Debezium이 읽어 Kafka로 밀어내기 때문에 애플리케이션 관점에서는 "DB 커밋과 거의 동시"에 이벤트가 나간다. 실전 운영 환경에서도 수십~수백 ms 내에 소비자 토픽에 도달한다. 초저지연 경쟁이 걸리는 상품 재고/가격/주문 상태 같은 도메인에서 CDC가 선택되는 진짜 이유가 여기 있다.

### 운영 복잡도(Operational complexity)의 본질

폴링 Publisher의 운영은 사실상 "애플리케이션 배포 + 테이블 lag 모니터링" 수준으로 끝난다. Outbox가 쌓이면 `SELECT COUNT(*) ... WHERE published_at IS NULL`만 보면 된다. 장애 복구도 "미발행 이벤트를 다시 읽어서 재발행"으로 자연스럽게 해결된다. 인프라팀이 별도로 관리할 요소가 적다.

CDC는 운영 구성 요소가 최소 세 개다. (1) MySQL 소스(binlog 활성화, 권한, 보존 기간), (2) Kafka Connect 클러스터(워커 HA, 플러그인 버전, 메모리), (3) Debezium 커넥터 자체(상태 관리, 스냅샷 전략, 스키마 변경 대응). binlog 보존 기간이 너무 짧게 설정되면 Debezium이 장시간 다운됐을 때 읽지 못한 구간을 잃는다. 초기 스냅샷이 너무 오래 걸리면 서비스 오픈 타임라인에 영향을 준다. "개념적으로 단순"해 보이지만 실제 장애는 대부분 Connect/커넥터 계층에서 터진다.

### 장애 복구 시나리오별 동작 차이

| 장애 | 폴링 방식 동작 | CDC 방식 동작 |
|---|---|---|
| Publisher/커넥터 프로세스 크래시 | 재기동 후 `published_at IS NULL` 조회 — 자연 복구 | 커넥터가 저장된 binlog offset에서 재시작 — 자연 복구 |
| Kafka 브로커 다운 | Outbox 테이블에 계속 쌓임, 모니터링 쿼리로 경보 | 커넥터 퍼블리시 실패, binlog 위치에서 대기, Connect가 재시도 |
| DB 프라이머리 페일오버 | 애플리케이션 재연결만 되면 정상 | binlog 포지션이 바뀔 수 있음 — GTID 기반 커넥터 설정이 필수 |
| Publisher 장기 다운 | `created_at`이 오래된 레코드가 쌓임 — 디스크 여유만 있으면 안전 | binlog 보존 기간 초과 시 **영구 유실 가능** — 운영 리텐션 정책이 생명선 |
| 스키마 변경(칼럼 추가) | 코드와 함께 배포하면 끝 | 커넥터 재설정/스냅샷 재수행 여부 판단 필요, 호환성 전략 설계 필요 |
| 이벤트 특정 건 재발행 | `UPDATE outbox_events SET published_at=NULL WHERE id=?` 한 줄 | 단일 건 재전송 어려움 → 애플리케이션 레벨에서 새 이벤트를 다시 넣는 우회 필요 |

면접에서 자주 꼬이는 포인트는 **"CDC는 알아서 복구되니 더 안전하다"**는 잘못된 일반화다. CDC는 커넥터/Connect/연결 지점에서만 자동 복구될 뿐, **binlog 리텐션을 초과하는 장기 장애에서는 오히려 폴링보다 위험**하다. 폴링은 Outbox 테이블 자체가 장기 버퍼 역할을 하기 때문에 디스크만 버텨주면 잃지 않는다.

### 중복 처리 — 두 방식 모두 At-Least-Once

- **폴링 Publisher**: Kafka에 발행하고 `published_at` UPDATE 커밋 직전에 죽으면 같은 이벤트를 다음 폴링에서 또 발행한다.
- **Debezium CDC**: Kafka Connect의 offset commit이 비동기라서 마지막 커밋 이후 재시작되면 그 뒤 이벤트를 재전송한다. "Debezium은 정확히 한 번"이라는 흔한 오해는 틀렸다.

두 방식 다 **At-Least-Once**가 실전 전제이고, **소비자 멱등성**은 선택이 아니라 필수다. 이벤트에 `eventId`(예: Outbox row PK + 서비스명)를 실어서 소비자가 중복 여부를 검증한다.

```java
@KafkaListener(topics = "order-events")
public void handle(ConsumerRecord<String, String> record) {
    OrderEvent event = deserialize(record.value());

    if (processedEventRepository.existsByEventId(event.getEventId())) {
        log.info("Duplicate event ignored: {}", event.getEventId());
        return;
    }
    processedEventRepository.save(new ProcessedEvent(event.getEventId()));
    inventoryService.reserveStock(event.getOrderId(), event.getItems());
}
```

진짜 Exactly-Once가 필요한 드문 케이스라면 Kafka Transactional Producer + `read_committed` 소비자 조합을 써야 하고, 이 경우 CDC 쪽이 지원 범위가 더 넓다. 다만 처리량은 눈에 띄게 낮아진다.

### 도입 난이도와 팀 역량 관점

- **폴링 방식이 적합한 팀 상황**
  - Kafka Connect/Debezium 운영 경험이 없음
  - DBA 권한(binlog 활성화, REPLICATION 권한)을 쉽게 못 받음
  - 스터디/도입 초기 단계라 "우선 올리고 관찰"이 중요
  - 서비스 트래픽이 분당 수천 건 수준 또는 초당 수십 건
  - 지연이 1~2초여도 비즈니스적으로 허용됨
- **CDC 방식이 적합한 팀 상황**
  - Kafka/Kafka Connect를 이미 프로덕션에 운영 중
  - 초저지연(100ms 이하)이 비즈니스 KPI인 도메인
  - 이벤트 순서가 "도메인 규칙상 반드시" 유지돼야 함
  - 애플리케이션 쪽 폴링 부하를 더 얹을 여유가 없음
  - 여러 서비스에 걸쳐 Outbox 패턴을 표준화해야 함

### 점진적 마이그레이션 전략

실전에서 자주 쓰는 방법은 **"처음에 폴링으로 시작하고, 필요해지면 CDC로 전환"**이다. Outbox 테이블 스키마와 소비자 계약(이벤트 JSON 포맷, 파티션 키, eventId 전략)을 처음부터 CDC 호환으로 맞춰 두면 전환 비용이 크지 않다. 구체적으로는:

1. Outbox 스키마에 `tracing_id`, 필요 시 `deleted` 플래그를 미리 넣는다.
2. `aggregate_id`를 Kafka 파티션 키로 이미 쓰고 있게 한다.
3. 이벤트 JSON 구조에 `eventId`, `occurredAt`, `aggregateType`, `eventType`을 명시한다.
4. 소비자는 처음부터 멱등 처리를 전제로 작성한다.
5. 트래픽/지연 요구가 올라오면 Debezium Outbox EventRouter로 스위치한다.

이 순서로 가면 팀은 "복잡한 인프라부터 도입"하는 리스크 없이 Outbox 패턴의 이득을 조기에 가져가고, 필요해지는 시점에 CDC로 옮길 수 있다.

### 선택 기준 요약 — 의사결정 체크리스트

- [ ] 요구 지연이 1초 이상 허용되는가? → 예, 폴링 우선 검토
- [ ] 애플리케이션 DB에 폴링 추가 부하를 얹을 수 있는가? → 아니오면 CDC 쪽으로 이동
- [ ] 팀에 Kafka Connect 운영 경험이 있는가? → 없으면 폴링 먼저
- [ ] binlog 권한과 리텐션 정책을 통제할 수 있는가? → 아니오면 CDC는 운영 리스크
- [ ] 이벤트 순서가 도메인에서 엄격한가? → 엄격하면 CDC가 유리
- [ ] 다중 Outbox 서비스가 늘어날 예정인가? → CDC로 표준화 이득
- [ ] 초기 스냅샷을 감당할 수 있는가? → 큰 히스토리 테이블은 CDC 도입 타이밍을 신중히
- [ ] SLA가 “이벤트 유실 0” 수준인가? → 폴링 + 디스크/모니터링 쪽이 장기 장애에 더 관대함

---

## 폴링 Publisher 레퍼런스 구현

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

다중 인스턴스 환경에서는 `SELECT ... FOR UPDATE SKIP LOCKED` 혹은 Shedlock/advisory lock으로 중복 발행을 막는다. 배치 단위(예: 100건)는 Kafka 브로커의 `acks=all` 지연 특성과 DB 락 유지 시간을 함께 고려해 결정한다. 처리량이 중요한 경우 배치 내에서 Kafka 발행을 `CompletableFuture`로 병렬화하고 결과를 모아 한 번에 `markPublished`를 반영한다.

## CDC(Debezium) 레퍼런스 구성

```json
{
  "connector.class": "io.debezium.connector.mysql.MySqlConnector",
  "database.hostname": "mysql",
  "database.port": "3306",
  "database.user": "debezium",
  "database.password": "dbz",
  "database.server.name": "order-db",
  "database.server.id": "184054",
  "database.include.list": "order_service",
  "table.include.list": "order_service.outbox_events",
  "snapshot.mode": "schema_only",
  "tombstones.on.delete": "false",
  "transforms": "outbox",
  "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
  "transforms.outbox.table.field.event.id": "id",
  "transforms.outbox.table.field.event.key": "aggregate_id",
  "transforms.outbox.table.field.event.payload": "payload",
  "transforms.outbox.route.by.field": "aggregate_type",
  "transforms.outbox.route.topic.replacement": "${routedByValue}-events"
}
```

주요 포인트:

- `database.server.id`는 replica 식별자로, 각 커넥터별로 유일해야 한다.
- `snapshot.mode=schema_only`는 "과거 데이터는 이미 다른 채널로 소비됐다"를 전제로 한다. 기존 Outbox 행까지 재처리하고 싶으면 `initial`을 쓴다.
- `EventRouter`는 `aggregate_type` 값에 따라 `order-events`, `payment-events` 등으로 토픽을 라우팅한다. 주문 도메인과 결제 도메인을 하나의 Outbox 테이블에 두면서 토픽은 도메인별로 분리하는 설계가 그대로 나온다.
- GTID 기반 운영(`gtid.source.includes`)을 권장한다. 프라이머리 페일오버 시 binlog 포지션이 아닌 GTID로 재개해야 유실/중복이 최소화된다.
- `tombstones.on.delete=false`로 두면 Outbox 행 삭제가 별도 tombstone 이벤트로 흘러가지 않는다. Outbox 행은 보통 "발행 후 TTL 삭제"이므로 소비자에게 노출되면 안 된다.

Kafka Connect 모니터링은 `/connectors/<name>/status`, `debezium.mysql:type=connector-metrics,*` JMX 메트릭, 그리고 `lag`(binlog 위치 vs 읽은 위치) 지표를 함께 본다. Outbox 행의 `created_at`과 소비자 측 `received_at` 차이를 대시보드로 노출해 실제 end-to-end 지연을 보이게 하면 운영이 편해진다.

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

### 시나리오 4: Debezium 커넥터가 binlog 리텐션을 초과해 재기동된다

CDC 고유 리스크다. 운영에서는 **binlog 리텐션 ≫ 커넥터 최대 예상 다운타임**이 되도록 여유를 가진다(예: 7일 이상). 실제로 초과한 경우에는 `snapshot.mode=initial`로 재스냅샷을 수행하고, 그 사이 누락된 Outbox 행은 애플리케이션이 다시 써주는 보조 복구 스크립트를 미리 준비한다. "어차피 Outbox는 우리가 쓰는 테이블이니 재쓰기가 가능하다"는 점이 이 패턴의 구원자 역할을 한다.

### 시나리오 5: 특정 이벤트만 재발행해야 한다

폴링 방식에서는 `UPDATE outbox_events SET published_at=NULL WHERE id=?` 한 줄로 끝난다. CDC 방식에서는 binlog를 되돌릴 수 없으므로, 일반적으로 **"보정 이벤트"를 새 Outbox row로 추가**해서 소비자가 처리하도록 한다. 이 차이는 운영 SOP(재처리 런북)에 명시해야 한다.

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

CDC 방식에서도 Debezium은 **같은 파티션 키로 라우팅된 이벤트에 대해 binlog 순서를 보존**한다. 즉 `aggregate_id`를 key로 쓰는 한 순서 특성은 폴링/CDC가 같다. 차이는 "순서가 깨질 수 있는 경로가 얼마나 좁은가"이고 CDC 쪽 경로가 더 좁다.

### 중복 발행 (At-Least-Once Delivery)

Outbox 패턴은 기본적으로 At-Least-Once를 제공한다. 적어도 한 번은 발행된다는 뜻이고, 경우에 따라 두 번 이상 발행될 수 있다는 뜻이기도 하다. 소비자가 멱등하게 구현되면 이 문제는 해결된다. 폴링이든 CDC든 이 전제는 동일하다.

정확히 한 번(Exactly-Once)을 원하면 Kafka Transactions를 사용해야 하는데, 그 경우 Kafka Producer와 Consumer 모두 트랜잭션 설정이 필요하고 처리량이 낮아진다. 대부분의 비즈니스 이벤트에서는 At-Least-Once + 소비자 멱등성 조합이 실용적이다.

---

## 커머스/플랫폼 시나리오에 적용

### 주문 생성 플로우

```
1. 주문서비스: orders INSERT + outbox(ORDER_CREATED) INSERT [같은 트랜잭션]
2. Outbox Publisher(폴링 또는 Debezium): ORDER_CREATED → order-events 토픽 발행
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

여기서 중요한 점은 재고 복구와 쿠폰 취소가 `PAYMENT_FAILED` 이벤트 하나를 각각 독립적으로 소비한다는 것이다. 서비스 간 직접 호출이 없다. 폴링이든 CDC든 이 흐름은 동일하고, 차이는 "`PAYMENT_FAILED`가 소비자에 도달하기까지의 지연"에서만 나타난다.

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
    // Kafka 발행은 별도 Publisher(폴링 스케줄러 또는 Debezium)의 책임
}
```

---

## 로컬 실습 환경 구성

### Docker Compose로 MySQL + Kafka 구성 (폴링/CDC 겸용)

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
    command: --binlog-format=ROW --log-bin=mysql-bin --server-id=1 --gtid-mode=ON --enforce-gtid-consistency=ON

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

  connect:
    image: debezium/connect:2.5
    depends_on:
      - kafka
      - mysql
    ports:
      - "8083:8083"
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: 1
      CONFIG_STORAGE_TOPIC: connect_configs
      OFFSET_STORAGE_TOPIC: connect_offsets
      STATUS_STORAGE_TOPIC: connect_statuses
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

# 3-a. (폴링 모드) Kafka 토픽 확인 — published_at이 채워지는 걸 본다
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic order-events --from-beginning

# 3-b. (CDC 모드) Debezium 커넥터 등록
curl -X POST -H "Content-Type: application/json" \
  --data @debezium-outbox-connector.json \
  http://localhost:8083/connectors

# 4. 실제 end-to-end 지연 비교
mysql -u root -proot order_service \
  -e "SELECT id, event_type, created_at, published_at,
             TIMESTAMPDIFF(MICROSECOND, created_at, published_at) AS lag_us
      FROM outbox_events ORDER BY id DESC LIMIT 10;"
```

CDC 모드에서는 Outbox 테이블에 `published_at` 칼럼 자체가 필수는 아니지만, **"소비자 측 수신 시각 - 원본 커밋 시각"을 기록하는 보조 로그**를 두면 폴링/CDC 전환 시 지연 비교 데이터를 그대로 쓸 수 있다.

---

## 인터뷰 답변 프레임

### 예상 질문: "주문 서비스에서 재고와 결제를 어떻게 동기화하나요?"

**미숙한 답:** "Kafka로 이벤트를 보내면 각 서비스가 처리합니다."

**시니어 수준 답:**

"먼저 DB 저장과 이벤트 발행 사이의 원자성 문제를 다뤄야 합니다. 단순히 DB 커밋 후 Kafka로 발행하면, 둘 사이에 프로세스가 죽었을 때 이벤트가 유실됩니다. 반대로 트랜잭션 안에서 Kafka 발행을 하면 Kafka 발행 성공 후 DB 롤백 시 이미 발행된 메시지를 되돌릴 수 없습니다.

이 문제를 해결하기 위해 Outbox 패턴을 씁니다. 비즈니스 데이터와 이벤트를 같은 로컬 트랜잭션으로 DB에 저장하고, 별도 Publisher가 Outbox 테이블을 읽어 Kafka에 발행합니다. At-Least-Once 발행이 되기 때문에 소비자 쪽에서 멱등성을 구현합니다.

보상 트랜잭션 흐름은 Saga 패턴으로 처리하는데, 저는 서비스 수가 많지 않을 때는 Choreography, 복잡한 흐름이라면 Orchestration을 선택합니다. CJ OliveYoung처럼 주문-재고-결제-쿠폰-알림이 모두 엮이는 플로우라면 Orchestration Saga로 Saga Orchestrator 서비스를 두는 게 전체 흐름 파악과 장애 추적에 유리합니다."

### 예상 질문: "Outbox Publisher는 폴링으로 가나요, CDC(Debezium)로 가나요?"

**시니어 수준 답:**

"지연 요구와 팀의 인프라 운영 역량, 두 축으로 판단합니다. 1초 내외 지연이 허용되고 팀이 Kafka Connect를 새로 운영해야 하는 상황이면 폴링부터 시작합니다. Spring 스케줄러와 `SELECT ... FOR UPDATE SKIP LOCKED`로 구현할 수 있고, Outbox 테이블 lag을 쿼리 한 줄로 관측할 수 있어서 초기 도입이 안전합니다.

반면 도메인 특성상 100ms 이하의 near real-time이 필요하거나, 폴링으로 인한 애플리케이션-DB 상시 부하가 실서비스에 영향을 줄 정도라면 Debezium CDC로 갑니다. CDC는 binlog를 읽기 때문에 애플리케이션 쿼리 부하가 없고, 순서 보장이 더 강하며, 여러 서비스의 Outbox를 표준화하기 좋습니다.

단, CDC라고 공짜는 아닙니다. Kafka Connect 클러스터, binlog 권한, GTID 설정, binlog 리텐션 정책이 함께 요구되고, 이 중 하나라도 느슨하면 장기 장애 시 이벤트가 영구 유실될 수 있습니다. 폴링은 Outbox 테이블 자체가 장기 버퍼 역할을 해서 디스크만 버티면 복구가 쉽습니다. 그래서 저는 두 방식 모두 '소비자 멱등성'과 'aggregate_id 기반 파티션 키'라는 공통 계약을 먼저 고정하고, 폴링으로 출발해 필요할 때 CDC로 전환하는 경로를 선호합니다. 그러면 전환 비용이 거의 소비자 쪽 변화 없이 Publisher만 교체하는 수준으로 줄어듭니다."

### 예상 질문: "Outbox 패턴의 단점은?"

"Outbox 테이블을 관리해야 한다는 운영 부담이 있습니다. 발행 완료된 이벤트는 주기적으로 정리해야 하고, Publisher 프로세스 모니터링도 필요합니다. 폴링 방식은 1~2초 수준의 지연이 있는데, 그 정도 지연이 허용되지 않는 경우라면 Debezium CDC를 도입해야 하고 그 경우 Kafka Connect 인프라가 추가됩니다.

2PC와 비교하면 엄격한 일관성을 포기하고 결과적 일관성을 받아들이는 설계입니다. 잠깐 주문이 CONFIRMED인데 재고가 아직 차감되지 않은 상태가 존재할 수 있습니다. 이를 허용하도록 비즈니스 로직과 모니터링이 설계돼야 합니다."

### 예상 질문: "2PC는 왜 쓰지 않나요?"

"2PC는 블로킹 프로토콜이라 코디네이터 장애 시 모든 참여자가 락을 걸고 대기합니다. 응답 시간이 가장 느린 참여자에 의해 전체 트랜잭션 성능이 제한됩니다. 무엇보다 HTTP REST API나 Kafka 같은 외부 시스템은 XA 프로토콜에 참여할 수 없어서 실제 MSA 환경에서는 쓸 수 없는 경우가 많습니다."

---

## 체크리스트

- [ ] Outbox 테이블의 역할을 설명할 수 있다: 로컬 트랜잭션 안에서 이벤트를 저장하여 원자성 보장
- [ ] Polling Publisher와 CDC의 지연/부하/순서/운영 복잡도 차이를 표 수준으로 설명할 수 있다
- [ ] Polling Publisher 다중 인스턴스에서 중복 발행을 막는 락 전략을 3가지 이상 말할 수 있다 (`FOR UPDATE SKIP LOCKED`, Shedlock, DB advisory lock 등)
- [ ] Debezium 커넥터가 장애/리스타트/프라이머리 페일오버에서 어떻게 재개되는지 설명할 수 있다
- [ ] binlog 리텐션이 CDC Outbox의 "유실 한계선"임을 이해하고 운영 리텐션을 근거 있게 말할 수 있다
- [ ] At-Least-Once 발행과 소비자 멱등성의 관계를 설명할 수 있다
- [ ] 폴링 → CDC 전환을 최소 비용으로 하기 위한 소비자 계약(파티션 키, eventId, 스키마) 설계 기준을 말할 수 있다
- [ ] Choreography Saga와 Orchestration Saga의 트레이드오프를 설명할 수 있다
- [ ] 2PC가 실전 MSA에서 적합하지 않은 구체적 이유 3가지를 말할 수 있다
- [ ] 결제 실패 시 보상 트랜잭션 플로우를 주문-재고-쿠폰 흐름으로 설명할 수 있다
- [ ] 같은 이벤트 ID를 두 번 처리했을 때 안전한 소비자 코드를 작성할 수 있다
- [ ] Outbox 테이블 모니터링 쿼리와 CDC lag 메트릭을 어떤 지표로 대시보드화할지 설명할 수 있다
- [ ] Kafka 파티션 키 선택이 메시지 순서에 미치는 영향을 설명할 수 있다
- [ ] `@Transactional` 안에서 Kafka 발행을 하면 안 되는 이유를 코드 레벨로 설명할 수 있다
- [ ] 특정 이벤트 재발행 런북을 폴링/CDC 각각에 대해 한 문장으로 설명할 수 있다
