# [초안] 분산 아키텍처 완전 정복: Java 백엔드 시니어 인터뷰 대비 실전 가이드

---

## 왜 분산 아키텍처를 알아야 하는가

단일 서버에 모든 기능을 몰아넣는 모놀리식 설계는 처음에는 단순하고 빠르다. 하지만 서비스가 성장하면서 네 가지 한계가 반드시 찾아온다.

**첫째, 규모 확장의 비대칭성.** 결제 트래픽이 폭주한다고 해서 사용자 프로필 서버까지 함께 스케일아웃 하면 비용이 낭비된다. 분산 아키텍처에서는 병목이 되는 서비스만 선택적으로 확장할 수 있다.

**둘째, 배포 단위의 결합.** 모놀리스에서는 쿠폰 기능 하나를 수정해도 전체 서비스를 재배포해야 한다. 잘못 배포되면 전체 서비스가 다운된다.

**셋째, 장애 전파.** 리포트 생성 기능에 메모리 누수가 있으면 같은 JVM에 올라 있는 결제 기능도 영향을 받는다.

**넷째, 기술 스택 고착.** 새로운 언어나 프레임워크를 도입하려면 기존 코드베이스 전체를 건드려야 한다.

분산 아키텍처, 특히 MSA는 이 네 가지 한계를 서비스 경계 분리로 해결한다. 그런데 이 해결책은 새로운 종류의 복잡성을 낳는다. 네트워크는 신뢰할 수 없고, 클록은 드리프트되며, 두 서비스 간 데이터 일관성을 단일 트랜잭션으로 보장할 수 없다. 시니어 백엔드 인터뷰에서 분산 아키텍처를 묻는 이유가 바로 여기 있다. 설계 패턴을 외웠는가가 아니라, 이 트레이드오프를 직접 경험하고 이해하고 있는가를 본다.

---

## 분산 시스템의 근본적 실패 모드

분산 시스템을 다루기 전에 반드시 이해해야 할 전제가 있다. 피터 도이치의 **분산 컴퓨팅의 8가지 오류**(Fallacies of Distributed Computing) 중 핵심은 다음이다.

- **네트워크는 신뢰할 수 없다**: 패킷은 유실되거나, 지연되거나, 순서가 바뀐다
- **레이턴시는 0이 아니다**: 동일 데이터센터 내에서도 수십 밀리초 레이턴시가 발생할 수 있다
- **대역폭은 무한하지 않다**
- **네트워크는 안전하지 않다**
- **토폴로지는 변한다**: 서버가 추가되거나 제거된다
- **단일 관리자는 없다**

실무에서 가장 자주 만나는 실패 모드를 구체적으로 살펴보자.

### 1. 타임아웃 후 부분 성공 (Partial Success After Timeout)

슬롯 서버가 유저 서버에 베팅 차감 HTTP 요청을 보냈다. 유저 서버는 DB를 업데이트하고 커밋했지만, 응답을 돌려주기 직전에 네트워크가 끊겼다. 슬롯 서버는 타임아웃을 에러로 판단해 자신의 트랜잭션을 롤백했다. 결과적으로 유저는 돈을 잃었지만 게임 결과는 없다.

이 시나리오에서 재시도를 하면 또 차감된다. 재시도를 안 하면 돈이 사라진다. 이것이 **멱등성**(Idempotency)이 필수인 이유다.

### 2. 계단식 장애 (Cascading Failure)

서비스 A가 서비스 B를 동기 호출한다. B가 느려지자 A의 스레드 풀이 응답 대기 상태로 쌓이기 시작한다. A의 스레드가 소진되면 A도 느려지고, A를 호출하는 C까지 영향을 받는다. 장애가 시스템 전체로 전파되는 전형적인 패턴이다.

```
클라이언트 → 서비스 A (스레드 200개 중 198개 대기 중)
                ↓
              서비스 B (응답 지연 3초)
                ↓
              DB (커넥션 풀 고갈)
```

### 3. Split-Brain

Redis 클러스터나 Kafka 파티션에서 네트워크 파티션이 발생하면, 두 노드가 각자 자신이 리더라고 판단해 동시에 쓰기를 받아들이는 상황이 생긴다. 데이터가 갈라지는 것이다.

### 4. 메시지 중복 처리 (Duplicate Processing)

Kafka 컨슈머가 메시지를 처리한 후 오프셋을 커밋하기 전에 재시작되었다. 같은 메시지가 재전송된다. 이것이 At-least-once 시맨틱이다. 비즈니스 로직이 멱등하지 않으면 중복 결제, 중복 포인트 적립이 발생한다.

---

## 서비스 경계를 어떻게 나누는가

서비스 경계를 잘못 나누면 분산 아키텍처의 장점이 모두 사라진다. 서비스 분리는 기술적 레이어(컨트롤러/서비스/레포지토리)가 아니라 **비즈니스 능력**(Business Capability)을 기준으로 해야 한다.

**도메인 주도 설계(DDD)의 바운디드 컨텍스트**가 실용적인 기준이다.

- 주문 컨텍스트에서의 "상품"은 주문 아이템이다 (ID, 수량, 단가)
- 재고 컨텍스트에서의 "상품"은 재고 단위다 (SKU, 위치, 가용 수량)
- 상품 컨텍스트에서의 "상품"은 카탈로그 엔티티다 (이름, 이미지, 설명)

세 컨텍스트가 같은 "상품" 테이블을 공유하면 서비스를 분리해도 DB 레이어에서 강하게 결합된다. **서비스별 독립 DB**가 MSA의 핵심 원칙인 이유다.

잘못된 분리의 징후:
- 두 서비스가 같은 DB 테이블에 직접 접근한다
- 한 서비스를 변경하면 다른 서비스의 코드도 항상 같이 바뀐다
- 서비스 배포 순서를 지켜야 한다

---

## 동기 통신 vs 비동기 통신

### 동기 통신 (HTTP/REST, gRPC)

```
클라이언트 --[요청]--> 서비스 A --[HTTP 호출]--> 서비스 B
                                <--[응답]------
           <--[응답]--
```

**언제 쓰는가**: 결과를 즉시 알아야 하는 경우. 사용자 인증, 재고 조회, 결제 승인 결과 확인.

**문제점**:
- 서비스 B가 다운되면 서비스 A도 기능 불가
- B의 응답 지연이 A의 스레드를 점유
- 서비스 수가 늘어날수록 호출 체인이 깊어지고 레이턴시가 누적된다

```java
// 동기 호출의 전형적인 실수: 타임아웃 미설정
RestTemplate restTemplate = new RestTemplate();
// 이 호출은 서비스 B가 응답 안 하면 영원히 블록된다
UserDto user = restTemplate.getForObject(
    "http://user-service/api/users/" + userId, UserDto.class);
```

```java
// 올바른 설정: 타임아웃 + CircuitBreaker
@Bean
public RestTemplate restTemplate() {
    SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
    factory.setConnectTimeout(1000);  // 연결 타임아웃 1초
    factory.setReadTimeout(3000);     // 읽기 타임아웃 3초
    return new RestTemplate(factory);
}
```

### 비동기 통신 (Kafka, RabbitMQ)

```
서비스 A --[이벤트 발행]--> Kafka Topic
                                ↓
                           서비스 B --[이벤트 소비]
```

**언제 쓰는가**: 결과를 즉시 알 필요가 없는 경우. 주문 후 알림 발송, 결제 후 포인트 적립, 이벤트 로그.

**장점**:
- 서비스 B가 다운돼도 A는 계속 동작 (메시지는 Kafka에 남아 있다)
- B가 처리 속도가 느려도 A에 영향 없음
- 서비스 간 결합도 최소화

**문제점**:
- 결과를 즉시 알 수 없다 (최종 일관성)
- 메시지 순서 보장이 필요하면 추가 설계 필요
- 디버깅이 어렵다 (메시지가 어디서 막혔는지 추적하기 어려움)

---

## CAP 정리와 일관성 트레이드오프

CAP 정리는 분산 시스템이 다음 세 가지를 동시에 보장할 수 없다는 정리다.

- **C (Consistency)**: 모든 노드에서 같은 시간에 같은 데이터를 읽는다
- **A (Availability)**: 모든 요청이 응답을 받는다 (오류 응답 포함)
- **P (Partition Tolerance)**: 네트워크 파티션이 발생해도 시스템이 동작한다

네트워크 파티션은 실제로 발생하기 때문에 P는 포기할 수 없다. 결국 선택은 **CP** (일관성 우선, 가용성 희생) 또는 **AP** (가용성 우선, 일관성 희생)다.

| 시스템 | 전략 | 이유 |
|--------|------|------|
| ZooKeeper, etcd | CP | 설정값·리더 선출은 일관성이 생명 |
| Cassandra, DynamoDB | AP | 쓰기 가용성 우선, 최종 일관성 허용 |
| MySQL 단일 노드 | CA | 파티션 자체가 없음 |

### ACID vs BASE

| | ACID | BASE |
|--|------|------|
| 일관성 | 강한 일관성 | 최종 일관성 |
| 가용성 | 트랜잭션 실패 시 롤백 | 항상 응답 (stale 데이터 가능) |
| 적용 | 단일 DB 트랜잭션 | 분산 시스템, NoSQL |

MSA에서 여러 서비스에 걸친 비즈니스 로직은 단일 ACID 트랜잭션으로 묶을 수 없다. 서비스별로 ACID를 보장하되, 서비스 간에는 최종 일관성(BASE)으로 설계하는 것이 현실적인 접근이다.

---

## 분산 트랜잭션: Saga와 Outbox 패턴

### 2PC가 MSA에 맞지 않는 이유

2PC는 코디네이터가 모든 참여자에게 "Prepare → Commit" 두 단계를 지시한다. Prepare 단계에서 각 서비스는 자원을 잠근다. 모두 OK를 보내면 Commit 신호가 내려온다.

문제는 Prepare와 Commit 사이에 코디네이터가 죽으면 모든 참여자가 락을 건 채로 무한히 기다린다. 또한 HTTP 서비스는 2PC 프로토콜을 기본 지원하지 않는다. 이것이 2PC를 MSA에서 쓰지 않는 이유다.

### Saga 패턴

Saga는 각 서비스의 로컬 트랜잭션을 순차적으로 실행하고, 실패하면 이미 성공한 단계들을 **보상 트랜잭션**(Compensating Transaction)으로 되돌린다.

**온라인 쇼핑몰 주문 Saga 예시:**

```
1. 주문 서비스: 주문 생성 (상태: PENDING)
   → 성공 → "OrderCreated" 이벤트 발행
   → 실패 시 보상: 없음 (첫 단계)

2. 재고 서비스: 재고 차감
   → 성공 → "InventoryReserved" 이벤트 발행
   → 실패 시 보상: "OrderCreated 이벤트"에 응답해 주문 취소

3. 결제 서비스: 결제 처리
   → 성공 → "PaymentProcessed" 이벤트 발행
   → 실패 시 보상: 재고 서비스에 "InventoryReleased" 이벤트 발행
              + 주문 서비스에 주문 취소

4. 배송 서비스: 배송 준비
   → 성공 → 주문 서비스에 "OrderCompleted" 이벤트 발행
```

**Choreography vs Orchestration:**

```
Choreography: 각 서비스가 이벤트를 발행하고, 다음 서비스가 구독해 반응
- 장점: 중앙 제어 없이 느슨한 결합
- 단점: 전체 흐름을 한눈에 파악하기 어려움, 디버깅 어려움

Orchestration: 별도 오케스트레이터(Saga Manager)가 전체 흐름을 지시
- 장점: 흐름이 한 곳에 명시적으로 정의됨
- 단점: 오케스트레이터가 SPOF(단일 장애점)가 될 수 있음
```

Java에서 Orchestration-based Saga를 구현할 때는 Spring State Machine 또는 Temporal.io를 활용하는 것이 일반적이다.

### Transactional Outbox 패턴

Saga의 가장 큰 함정은 **DB 업데이트와 이벤트 발행의 원자성 보장**이다.

```java
// 위험한 코드: DB 커밋 후 Kafka 발행 전에 서버가 죽으면?
@Transactional
public void createOrder(OrderRequest request) {
    Order order = orderRepository.save(new Order(request));
    // 여기서 서버가 죽으면 DB는 커밋되었지만 이벤트는 발행 안 됨
    kafkaTemplate.send("order-events", new OrderCreatedEvent(order.getId()));
}
```

**Outbox 패턴**은 이 문제를 해결한다.

```sql
-- outbox 테이블 (주문 DB에 같이 존재)
CREATE TABLE outbox_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,  -- 'Order'
    aggregate_id VARCHAR(100) NOT NULL,    -- orderId
    event_type VARCHAR(100) NOT NULL,      -- 'OrderCreated'
    payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP NULL,
    INDEX idx_unpublished (published_at) WHERE published_at IS NULL
);
```

```java
@Transactional
public void createOrder(OrderRequest request) {
    Order order = orderRepository.save(new Order(request));
    
    // 같은 트랜잭션 안에서 outbox 테이블에 이벤트 저장
    OutboxEvent event = OutboxEvent.builder()
        .aggregateType("Order")
        .aggregateId(order.getId().toString())
        .eventType("OrderCreated")
        .payload(objectMapper.writeValueAsString(new OrderCreatedEvent(order)))
        .build();
    outboxEventRepository.save(event);
    // DB 커밋: 주문 생성 + outbox 이벤트가 원자적으로 저장됨
}
```

```java
// 별도 스케줄러(또는 CDC)가 outbox를 폴링해 Kafka에 발행
@Scheduled(fixedDelay = 1000)
public void publishOutboxEvents() {
    List<OutboxEvent> events = outboxEventRepository.findUnpublished();
    for (OutboxEvent event : events) {
        kafkaTemplate.send("order-events", event.getPayload());
        event.markAsPublished();
        outboxEventRepository.save(event);
    }
}
```

실무에서는 폴링 방식 대신 **Debezium** 같은 CDC(Change Data Capture) 도구로 DB 바이너리 로그를 읽어 Kafka에 발행하는 방식을 많이 쓴다. 폴링보다 레이턴시가 낮고 DB 부하도 적다.

---

## 멱등성(Idempotency): 재시도를 안전하게 만드는 열쇠

분산 시스템에서 재시도는 필수다. 타임아웃이 났을 때 실제로 처리됐는지 알 수 없으므로 재시도해야 하는데, 재시도가 안전하려면 로직이 멱등해야 한다.

**멱등성**: 동일한 요청을 여러 번 실행해도 결과가 처음 한 번 실행한 것과 같아야 한다.

### 멱등성 키(Idempotency Key) 패턴

```java
// 요청 헤더에 멱등성 키를 포함
POST /api/payments
Idempotency-Key: a3f4c2b1-e8d7-4f9a-b2c3-d5e6f7a8b9c0
Content-Type: application/json

{"orderId": 1001, "amount": 50000}
```

```java
@Service
public class PaymentService {
    
    @Transactional
    public PaymentResult processPayment(String idempotencyKey, PaymentRequest request) {
        // 이미 처리된 요청인지 확인
        Optional<IdempotencyRecord> existing = 
            idempotencyRepository.findByKey(idempotencyKey);
        
        if (existing.isPresent()) {
            // 이미 처리됨: 캐시된 결과 반환
            return existing.get().getResult();
        }
        
        // 실제 결제 처리
        PaymentResult result = paymentGateway.charge(request);
        
        // 멱등성 레코드 저장
        idempotencyRepository.save(IdempotencyRecord.builder()
            .key(idempotencyKey)
            .result(result)
            .expiresAt(LocalDateTime.now().plusDays(1))
            .build());
        
        return result;
    }
}
```

```sql
CREATE TABLE idempotency_records (
    idempotency_key VARCHAR(100) PRIMARY KEY,
    result_payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_expires (expires_at)
);
```

### Kafka 컨슈머 멱등성

Kafka At-least-once에서 중복 메시지를 처리하는 방법:

```java
@KafkaListener(topics = "order-events")
public void handleOrderCreated(OrderCreatedEvent event) {
    // 처리 여부 확인 (이미 처리했다면 스킵)
    if (processedEventRepository.existsByEventId(event.getEventId())) {
        log.info("Duplicate event skipped: {}", event.getEventId());
        return;
    }
    
    // 실제 처리
    inventoryService.reserve(event.getOrderId(), event.getItems());
    
    // 처리 완료 기록 (같은 트랜잭션)
    processedEventRepository.save(new ProcessedEvent(event.getEventId()));
}
```

---

## 재시도와 지수 백오프

재시도를 잘못 설계하면 오히려 시스템을 망가뜨린다. 모든 서비스가 동시에 재시도하면 이미 과부하 상태인 서버에 트래픽을 더 쏟아붓는 **리트라이 스톰**(Retry Storm)이 발생한다.

### Resilience4j를 이용한 재시도 + 지수 백오프

```java
@Configuration
public class ResilienceConfig {
    
    @Bean
    public RetryConfig retryConfig() {
        return RetryConfig.custom()
            .maxAttempts(3)
            .waitDuration(Duration.ofMillis(500))
            // 지수 백오프: 500ms → 1000ms → 2000ms
            .intervalFunction(IntervalFunction.ofExponentialBackoff(500, 2))
            // 지터 추가: 동시 재시도 분산
            .intervalFunction(IntervalFunction.ofExponentialRandomBackoff(500, 2))
            // 재시도할 예외 타입 지정
            .retryExceptions(IOException.class, TimeoutException.class)
            // 재시도하지 않을 예외 (클라이언트 에러는 재시도 무의미)
            .ignoreExceptions(IllegalArgumentException.class)
            .build();
    }
    
    @Bean
    public CircuitBreakerConfig circuitBreakerConfig() {
        return CircuitBreakerConfig.custom()
            .failureRateThreshold(50)       // 50% 실패율에서 OPEN
            .waitDurationInOpenState(Duration.ofSeconds(30))
            .slidingWindowSize(10)
            .build();
    }
}
```

```java
@Service
public class UserServiceClient {
    
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;
    
    public UserDto getUser(Long userId) {
        Supplier<UserDto> supplier = CircuitBreaker
            .decorateSupplier(circuitBreaker,
                Retry.decorateSupplier(retry,
                    () -> restTemplate.getForObject(
                        USER_SERVICE_URL + "/users/" + userId, UserDto.class)));
        
        return Try.ofSupplier(supplier)
            .recover(CallNotPermittedException.class, 
                ex -> getUserFromCache(userId))  // 서킷 브레이커 OPEN 시 캐시 폴백
            .get();
    }
}
```

**서킷 브레이커 상태 전이:**

```
CLOSED (정상)
  → 실패율 50% 초과 → OPEN (차단)
                        → 30초 후 → HALF_OPEN (탐색)
                                      → 요청 성공 → CLOSED
                                      → 요청 실패 → OPEN
```

---

## 분산 락: Redis를 이용한 임계 영역 보호

단일 JVM의 `synchronized`는 다중 서버 환경에서 쓸모없다. 서버 3대가 같은 재고에 동시 접근하면 과다 차감이 발생한다.

```java
// Redisson을 이용한 분산 락
@Service
public class InventoryService {
    
    private final RedissonClient redissonClient;
    
    public boolean reserveInventory(Long productId, int quantity) {
        String lockKey = "inventory:lock:" + productId;
        RLock lock = redissonClient.getLock(lockKey);
        
        try {
            // 최대 3초 대기, 락 유지 10초
            boolean acquired = lock.tryLock(3, 10, TimeUnit.SECONDS);
            if (!acquired) {
                throw new LockAcquisitionException("재고 락 획득 실패: " + productId);
            }
            
            // 임계 영역: 재고 확인 + 차감
            Inventory inventory = inventoryRepository.findByProductId(productId);
            if (inventory.getQuantity() < quantity) {
                return false;
            }
            inventory.decrease(quantity);
            inventoryRepository.save(inventory);
            return true;
            
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

재고 차감처럼 단순한 원자적 감소는 락 없이 `DECR` 명령 하나로 해결할 수 있다. 복잡한 비즈니스 로직(확인 후 차감 패턴)에만 분산 락을 써야 한다.

---

## 관찰 가능성(Observability): 분산 시스템의 눈

단일 서버에서는 로그 하나로 문제를 추적했지만, 분산 시스템에서는 요청이 여러 서비스를 거치기 때문에 어느 서비스에서 무슨 일이 일어났는지 추적하기 어렵다. 관찰 가능성의 세 기둥은 **로그**, **메트릭**, **트레이스**다.

### 분산 트레이싱: Trace ID 전파

```java
// Spring Boot + Micrometer Tracing (Brave/OpenTelemetry)
// application.yml
management:
  tracing:
    sampling:
      probability: 1.0  # 100% 샘플링 (운영에서는 0.1 ~ 0.01)

# Kafka 메시지에 Trace ID를 헤더로 전파
```

```java
@KafkaListener(topics = "order-events")
public void handleOrderCreated(
        @Payload OrderCreatedEvent event,
        @Headers MessageHeaders headers) {
    // Micrometer가 자동으로 Trace ID를 추출해 현재 Span에 연결
    // Zipkin/Jaeger 대시보드에서 전체 요청 흐름을 추적 가능
    log.info("Processing order: {}", event.getOrderId());
    inventoryService.reserve(event);
}
```

### 구조화 로깅 (Structured Logging)

```java
// 일반 로그: 파싱 불가
log.info("주문 처리 완료, 주문 ID: " + orderId + ", 금액: " + amount);

// 구조화 로그: Elasticsearch/Loki에서 필터링 가능
log.info("Order processed",
    kv("orderId", orderId),
    kv("amount", amount),
    kv("userId", userId),
    kv("duration_ms", duration));
```

```json
{
  "timestamp": "2026-04-17T10:30:00.123Z",
  "level": "INFO",
  "message": "Order processed",
  "traceId": "3f4c2b1e8d7f9ab2",
  "spanId": "c3d5e6f7a8b9c0d1",
  "orderId": 1001,
  "amount": 50000,
  "userId": 42,
  "duration_ms": 87
}
```

### 핵심 메트릭

분산 서비스에서 모니터링해야 할 메트릭을 **RED 방법론**으로 정리한다.

- **R (Rate)**: 초당 요청 수
- **E (Errors)**: 에러율 (5xx 비율)
- **D (Duration)**: 응답 시간 (p50, p95, p99)

```java
@Component
public class OrderMetrics {
    
    private final MeterRegistry meterRegistry;
    private final Counter orderCreatedCounter;
    private final Timer orderProcessingTimer;
    
    public OrderMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        this.orderCreatedCounter = Counter.builder("order.created")
            .tag("service", "order-service")
            .register(meterRegistry);
        this.orderProcessingTimer = Timer.builder("order.processing.duration")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);
    }
    
    public void recordOrderCreated() {
        orderCreatedCounter.increment();
    }
    
    public void recordProcessingTime(Runnable task) {
        orderProcessingTimer.record(task);
    }
}
```

---

## 잘못된 설계 vs 개선된 설계

### Case 1: 동기 호출 체인으로 인한 성능 저하

**Before (잘못된 설계):**

```java
// 주문 생성 시 4개의 동기 HTTP 호출
@PostMapping("/orders")
public OrderResponse createOrder(@RequestBody OrderRequest request) {
    UserDto user = userClient.getUser(request.getUserId());         // 50ms
    ProductDto product = productClient.getProduct(request.getProductId()); // 30ms
    boolean reserved = inventoryClient.reserve(request);            // 40ms
    PaymentResult payment = paymentClient.charge(request);          // 100ms
    // 총 220ms + 각 서비스의 불안정성이 직접 전파됨
    return new OrderResponse(order);
}
```

**After (개선된 설계):**

```java
@PostMapping("/orders")
public OrderResponse createOrder(@RequestBody OrderRequest request) {
    // 1. 유효성 검사에 필요한 데이터만 동기로 조회
    UserDto user = userClient.getUser(request.getUserId()); // 필수 동기
    
    // 2. 주문을 PENDING 상태로 즉시 생성
    Order order = orderRepository.save(Order.pending(request, user));
    
    // 3. 나머지는 이벤트로 비동기 처리
    // (재고 예약, 결제 처리는 Saga로)
    outboxEventRepository.save(
        OutboxEvent.of("OrderCreated", order.getId(), order));
    
    // 응답을 즉시 반환: 주문은 처리 중
    return OrderResponse.accepted(order.getId());
}
```

### Case 2: 재시도 없는 Kafka 컨슈머

**Before:**

```java
@KafkaListener(topics = "payment-events")
public void handlePayment(PaymentEvent event) {
    // 외부 PG 연동이 실패하면 메시지를 그냥 버린다
    try {
        pgService.confirm(event.getPaymentId());
    } catch (Exception e) {
        log.error("PG 연동 실패", e);
        // 예외를 삼켜버림: 메시지 처리 완료로 간주, 오프셋 커밋됨
    }
}
```

**After (DLQ 적용):**

```java
@KafkaListener(topics = "payment-events")
public void handlePayment(PaymentEvent event) {
    pgService.confirm(event.getPaymentId());
    // 예외가 발생하면 Spring Kafka가 재시도 후 DLQ로 이동
}

// application.yml
spring:
  kafka:
    listener:
      ack-mode: RECORD
    consumer:
      group-id: payment-consumer
      
# Dead Letter Queue 설정
@Bean
public DefaultErrorHandler errorHandler(KafkaTemplate<String, String> kafkaTemplate) {
    DeadLetterPublishingRecoverer recoverer = 
        new DeadLetterPublishingRecoverer(kafkaTemplate,
            (r, e) -> new TopicPartition(r.topic() + ".DLT", r.partition()));
    
    ExponentialBackOffWithMaxRetries backOff = 
        new ExponentialBackOffWithMaxRetries(3);
    backOff.setInitialInterval(1000);
    backOff.setMultiplier(2);
    
    return new DefaultErrorHandler(recoverer, backOff);
}
```

---

## 로컬 연습 환경 구성

### Docker Compose로 분산 시스템 로컬 재현

```yaml
# docker-compose.yml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: order_db
    ports:
      - "3306:3306"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

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
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
```

```bash
# 실행
docker-compose up -d

# Kafka 토픽 생성
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 \
  --create --topic order-events --partitions 3 --replication-factor 1

# 메시지 발행 테스트
docker exec -it kafka kafka-console-producer \
  --bootstrap-server localhost:9092 --topic order-events

# 메시지 소비 테스트
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic order-events \
  --from-beginning --group test-consumer
```

### Outbox 패턴 직접 검증

```sql
-- 주문 생성 후 outbox 테이블 확인
SELECT * FROM outbox_events WHERE published_at IS NULL ORDER BY created_at DESC;

-- 발행 완료 확인
SELECT 
    event_type,
    COUNT(*) as total,
    SUM(CASE WHEN published_at IS NOT NULL THEN 1 ELSE 0 END) as published
FROM outbox_events
GROUP BY event_type;
```

---

## 시니어 인터뷰 답변 프레임

### Q1. "분산 트랜잭션을 어떻게 처리하셨나요?"

> "이전 프로젝트에서는 동기 HTTP 호출 기반으로 여러 서비스 간 트랜잭션을 관리했는데, 네트워크 타임아웃이 발생하면 한쪽 서비스는 커밋되고 다른 쪽은 롤백되는 데이터 불일치 문제가 있었습니다. 이 경험을 통해 동기 호출만으로는 분산 원자성을 보장할 수 없다는 것을 실감했습니다.
>
> 개선 방향으로는 Saga 패턴을 적용하되, DB 업데이트와 이벤트 발행의 원자성을 보장하기 위해 Transactional Outbox 패턴을 함께 적용하는 것이 정석입니다. 각 서비스는 자신의 로컬 트랜잭션만 책임지고, 보상 트랜잭션으로 전체 일관성을 복구합니다."

### Q2. "서비스 간 장애 전파를 어떻게 막으셨나요?"

> "서킷 브레이커 패턴을 Resilience4j로 적용했습니다. 핵심 서비스는 반드시 지정해야 할 세 가지가 있습니다. 첫째, 타임아웃 설정 — 설정 안 하면 스레드가 무한히 점유됩니다. 둘째, 서킷 브레이커 — 연속 실패 시 빠르게 실패하고 자원을 보호합니다. 셋째, 폴백 — 캐시된 데이터를 반환하거나 기능을 부분적으로 비활성화합니다. 세 가지를 모두 설정해야 진짜 방어가 됩니다."

### Q3. "Kafka를 쓰면서 중복 메시지는 어떻게 처리했나요?"

> "Kafka는 기본적으로 At-least-once이므로 컨슈머 로직을 멱등하게 만들어야 합니다. 방법은 두 가지입니다. 하나는 처리된 이벤트 ID를 DB에 기록해 중복을 검출하는 방법, 다른 하나는 비즈니스 로직 자체를 멱등하게 설계하는 방법입니다. 재고 차감이라면 `UPDATE SET quantity = quantity - 1 WHERE quantity > 0`처럼 조건을 걸면 중복 실행돼도 재고가 음수가 되지 않습니다. 단, 두 번째 방법은 모든 케이스에 적용 가능하지 않으므로 이벤트 ID 검출을 기본으로 가져갑니다."

### Q4. "CAP 정리를 실제 설계에 어떻게 적용하셨나요?"

> "CAP 정리는 네트워크 파티션이 발생했을 때 일관성과 가용성 중 무엇을 우선할지 선택하는 문제입니다. 결제처럼 데이터 정확성이 중요한 경우에는 파티션 발생 시 에러를 반환하더라도 일관성을 유지하는 CP를 선택합니다. 상품 목록 조회처럼 약간 오래된 데이터를 보여줘도 괜찮은 경우에는 AP를 선택하고 캐시를 활용합니다. 이 판단이 없이 전체 시스템을 동일하게 설계하면 불필요한 곳에 강한 일관성을 요구하거나, 반대로 중요한 데이터에 최종 일관성만 적용하는 실수가 생깁니다."

---

## 핵심 체크리스트

### 설계 원칙

- [ ] 서비스 경계는 비즈니스 능력 기준으로 분리했는가
- [ ] 서비스별 독립 DB를 사용하는가 (DB 공유 없음)
- [ ] 동기/비동기 통신 선택 기준이 명확한가

### 장애 방어

- [ ] 외부 서비스 호출에 타임아웃이 설정되어 있는가
- [ ] 서킷 브레이커가 핵심 외부 의존에 적용되어 있는가
- [ ] 폴백 전략이 정의되어 있는가
- [ ] 재시도에 지수 백오프와 지터가 포함되어 있는가

### 데이터 일관성

- [ ] 분산 트랜잭션 시나리오에 Saga 패턴을 고려했는가
- [ ] DB 업데이트와 이벤트 발행의 원자성을 Outbox 패턴으로 보장했는가
- [ ] 모든 재시도 가능 API가 멱등한가
- [ ] Kafka 컨슈머에 중복 메시지 처리 로직이 있는가

### 관찰 가능성

- [ ] 모든 서비스 간 요청에 Trace ID가 전파되는가
- [ ] 구조화 로깅(JSON 형식)을 사용하는가
- [ ] RED 메트릭(Rate, Error, Duration)을 수집하는가
- [ ] DLT(Dead Letter Topic)로 처리 실패 메시지를 보존하는가

### 인터뷰 준비

- [ ] 타임아웃 후 부분 성공 시나리오를 설명할 수 있는가
- [ ] Saga의 보상 트랜잭션 예시를 직접 설계할 수 있는가
- [ ] CAP 정리를 실제 기술 선택에 연결해 설명할 수 있는가
- [ ] 멱등성 키 구현 방법을 코드 수준에서 설명할 수 있는가

---

## 관련 문서

- [분산 트랜잭션과 Outbox 패턴](./distributed-transaction-outbox-pattern.md) — 2PC 대안, Outbox 테이블 설계
- [Resilience 패턴](./resilience-patterns.md) — Timeout·Retry·Circuit Breaker·Bulkhead·Backpressure
- [분산 트랜잭션](./distributed-transaction.md) — 기본 개념과 1차 방어
- [MSA 서비스 간 통신](./msa-service-communication.md) — Cache-Aside × Kafka 이벤트
