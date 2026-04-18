# [초안] MSA 서비스 간 통신: Redis Cache-Aside × Kafka 이벤트 하이브리드 설계

## 1. 이 주제가 왜 중요한가

모놀리식 환경에서 서비스 간 데이터 연동은 "조인 한 번이면 끝"이었다. 같은 트랜잭션, 같은 DB, 같은 JVM 안에서 데이터는 자연스럽게 일관성을 유지했다. 그러나 MSA로 넘어오는 순간 이 전제가 전부 깨진다. 상품 서비스의 상품 정보를 주문 서비스가 알아야 하고, 재고 서비스의 재고를 장바구니가 참조해야 하며, 알림 서비스는 결제 완료 이벤트를 받아야 한다. 이때 **"어떻게 연동할 것인가"**라는 질문은 단순한 기술 선택이 아니라 **서비스 경계와 도메인 소유권 선언**이다.

실무에서 가장 흔히 마주치는 실패 패턴은 세 가지다.

1. **동기 호출 체인의 장애 전파** — 주문 API가 상품 API를 호출하고, 상품 API가 재고 API를 호출한다. 말단 하나만 느려도 전체가 느려지고, 하나만 죽어도 전체가 죽는다.
2. **비동기 이벤트 남용으로 인한 일관성 블랙홀** — 모든 것을 Kafka 이벤트로 전파하기 시작하면 "이 데이터가 지금 최신인지" 아무도 단언하지 못한다.
3. **캐시를 "그냥 빠른 DB"로 오해한 설계** — TTL만 걸어두고 이벤트 연동을 안 하면, 상품명이 바뀌었는데 장바구니는 옛날 상품명을 30분 동안 보여준다.

시니어 백엔드 면접에서 "MSA 서비스 간 데이터를 어떻게 연동하시나요?"는 단골 질문이다. 이 질문에 **"REST로요"** 혹은 **"Kafka로요"** 한 줄로 답하면 그 순간 끝난다. 커머스 플랫폼의 실제 현실은 그보다 훨씬 미묘하며, CJ OliveYoung이 기술 블로그에서 공개한 "MSA 환경에서 도메인 데이터 연동 전략" 역시 **단일 기술이 아닌 데이터 특성 기반 하이브리드 설계**를 채택하고 있다. 이 문서는 그 설계 흐름을 Java/Spring 백엔드 관점에서 실행 가능한 수준으로 재구성한다.

## 2. MSA에서 서비스 간 데이터 연동이 어려운 근본 이유

### 2.1 소스 오브 트루스(source of truth)의 분산

모놀리식에서는 DB 한 개가 곧 진실이다. MSA에서는 상품 서비스의 PostgreSQL이 상품 정보의 진실, 재고 서비스의 Redis가 재고의 진실, 주문 서비스의 MySQL이 주문의 진실이 된다. 다른 서비스가 이 데이터를 **복제해서 들고 있다면**, 그 복제본은 본질적으로 **stale(오래된)** 상태가 될 위험을 가진다.

이때 설계자가 내려야 할 결정은 두 가지다.

- 이 데이터는 **참조만 할 것인가, 내 DB에 복제해서 저장할 것인가**?
- 복제본을 둔다면 **언제, 어떻게 갱신할 것인가**?

### 2.2 일관성 모델의 선택

분산 시스템에서는 CAP 이론이 말하듯 강한 일관성과 가용성을 동시에 가질 수 없다. 커머스는 **"최종 일관성(eventual consistency)"**을 받아들이는 대신 가용성을 취하는 영역이 대부분이다. 단, 결제·재고 차감처럼 금전과 직결되는 부분은 여전히 강한 일관성을 요구한다.

### 2.3 장애 전파(cascading failure)

동기 호출이 많아질수록 장애는 연쇄한다. 서비스 A → B → C 호출 체인에서 C의 p99 레이턴시가 2초로 튀면, A도 2초로 튄다. Circuit Breaker, Timeout, Bulkhead 같은 패턴은 **"동기를 선택했을 때 발생할 수밖에 없는 피해를 완화"**하는 장치이지, 애초에 동기를 택하지 않아도 된다면 쓰지 않는 게 최선이다.

## 3. 통신 방식 선택 기준: 데이터 특성으로 결정한다

"REST냐 Kafka냐"를 기술 관점에서 고르려 하면 항상 애매해진다. 실무에서 유효한 기준은 **데이터 자체의 특성**이다.

| 기준 | 동기(REST/gRPC) 적합 | 비동기(Kafka/SQS) 적합 |
|------|---------------------|---------------------|
| 사용 시점 | 호출 시점에 반드시 최신 | 조금 늦어도 괜찮음 |
| 변경 빈도 | 자주 변함 + 즉시 반영 필요 | 자주 변함 + 지연 수용 가능 |
| 라이프사이클 | 요청-응답 완결 | 발행-소비 분리 |
| 결과 의존성 | 응답값이 다음 로직 결정 | 결과와 무관하게 진행 |
| 실패 시 | 호출자에게 즉시 실패 전달 | 재시도/DLQ로 흡수 |

예를 들어 **결제 시점의 잔액 조회**는 반드시 동기여야 한다. 반면 **주문 완료 후 포인트 적립**은 반드시 비동기여야 한다. 이 구분이 깨지면 결제는 느려지고, 적립은 유실된다.

### 3.1 변경이 적은 데이터 → Cache-Aside

상품 카테고리, 브랜드 정보, 매장 메타데이터처럼 **하루에 몇 번 변하지 않는 데이터**는 다른 서비스가 호출할 때마다 원천 서비스 API를 때릴 이유가 없다. Cache-Aside 패턴으로 Redis에 태워두고, 변경 이벤트가 올 때 무효화한다.

```java
public Category getCategory(Long categoryId) {
    String key = "category:" + categoryId;
    Category cached = redisTemplate.opsForValue().get(key);
    if (cached != null) {
        return cached;
    }
    Category fresh = categoryClient.findById(categoryId); // 원천 API 호출
    redisTemplate.opsForValue().set(key, fresh, Duration.ofHours(6));
    return fresh;
}
```

이때 TTL만 걸고 끝내면 stale 데이터가 TTL 동안 유지된다. 해결책은 **카테고리 변경 이벤트를 Kafka로 구독해 해당 키를 삭제**하는 것이다.

```java
@KafkaListener(topics = "category.changed", groupId = "order-service")
public void onCategoryChanged(CategoryChangedEvent event) {
    redisTemplate.delete("category:" + event.categoryId());
}
```

### 3.2 실시간성 이벤트 → "이벤트 알림 + 선택적 API 조회" 하이브리드

OliveYoung 블로그에서 실제로 언급된 핵심 아이디어는 **"이벤트로 전체 데이터를 실어 나르지 않는다"**는 것이다. 이벤트에는 **"어떤 리소스가 바뀌었다"**는 키만 담고, **정말 필요할 때 원천 서비스에 API로 재조회**한다.

왜 이렇게 하는가?

- 이벤트 페이로드에 전체 DTO를 담으면 스키마가 커지고, 버전 관리가 지옥이 된다.
- Consumer 입장에서 필요 없는 필드까지 매번 받는 건 낭비다.
- 원천 서비스가 "진짜 최신 값"의 책임을 유지할 수 있다.

흐름은 다음과 같다.

1. 원천 서비스가 데이터 변경 시 `{"productId": 12345, "event": "updated"}` 수준의 가벼운 이벤트만 발행.
2. 구독 서비스는 이벤트를 받아 **로컬 캐시의 해당 키만 무효화**.
3. 이후 트래픽이 그 키를 요청하면 그때 원천 API를 한 번 호출해 캐시를 채움.

결과적으로 **변경 빈도와 조회 빈도가 디커플링**된다. 변경은 자주 일어나도, 아직 아무도 조회하지 않는 데이터는 원천 API를 건드리지 않는다.

## 4. 이 패턴을 안 쓰면 생기는 실패 모드

### 4.1 N+1 API Call

상품 목록 100개를 보여주기 위해 상품 서비스 API를 100번 호출하는 순간 끝이다. 배치 API를 제공하거나, 미리 캐시를 데워 놓아야 한다.

### 4.2 Cache Stampede

TTL이 만료된 직후 수백 개 요청이 동시에 원천 API를 때린다. 원천 서비스가 쓰러지면 장애가 호출자 전체로 번진다.

방어 기법:
- **Probabilistic Early Expiration** — TTL이 끝나기 직전 일부 요청만 미리 갱신.
- **StampedLock / Mutex 기반 캐시 갱신** — 같은 키에 대해 한 스레드만 원천을 재조회.
- **Stale-While-Revalidate** — 만료됐어도 옛날 값을 잠깐 반환하면서 백그라운드로 갱신.

지원자의 실제 경험 중 **StampedLock 기반 캐시 정합성 확보**가 바로 이 stampede 방어와 맞닿아 있다. 면접에서 "왜 ReentrantLock이 아니라 StampedLock인가?"는 바로 **"read-heavy 워크로드에서 optimistic read가 lock 획득 비용을 없애주기 때문"**이다.

### 4.3 이벤트 유실

Kafka 프로듀서가 DB 커밋 직후 이벤트 발행 직전에 죽으면, DB에는 반영됐지만 이벤트는 나가지 않는다. 이 문제의 정식 해법이 **Transactional Outbox 패턴**이며, 5장에서 자세히 다룬다.

## 5. Transactional Outbox와 @TransactionalEventListener(AFTER_COMMIT)

### 5.1 문제 상황

```java
@Transactional
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(...);
    kafkaTemplate.send("order.placed", new OrderPlacedEvent(order.getId()));
}
```

이 코드는 **치명적 결함**을 갖는다.

- DB 커밋 성공 + Kafka 발행 실패 → 주문은 있는데 후속 처리(적립, 알림)가 안 됨.
- DB 커밋 실패 + Kafka 발행 성공 → 주문은 없는데 적립은 됨.

### 5.2 해법 1: AFTER_COMMIT 리스너

```java
@Transactional
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(...);
    eventPublisher.publishEvent(new OrderPlacedDomainEvent(order.getId()));
}

@Component
class OrderEventBridge {
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void publish(OrderPlacedDomainEvent event) {
        kafkaTemplate.send("order.placed", event);
    }
}
```

DB 커밋이 확정된 뒤에만 Kafka로 발행되므로 "DB는 롤백됐는데 이벤트는 나간" 상황은 막힌다. 그러나 여전히 **커밋 직후 Kafka 발행 실패**는 유실이다.

### 5.3 해법 2: Transactional Outbox

같은 DB 트랜잭션 안에서 `outbox` 테이블에 이벤트를 함께 INSERT하고, 별도 퍼블리셔가 이 테이블을 폴링해 Kafka로 발행한 뒤 레코드를 지운다.

```sql
CREATE TABLE outbox_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    published_at DATETIME(6) NULL,
    INDEX idx_unpublished (published_at, id)
);
```

```java
@Transactional
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(...);
    outboxRepository.save(OutboxEvent.of(
        "Order", order.getId().toString(),
        "OrderPlaced", toJson(order)
    ));
}

@Scheduled(fixedDelay = 500)
public void flush() {
    List<OutboxEvent> pending = outboxRepository
        .findTop100ByPublishedAtIsNullOrderByIdAsc();
    for (OutboxEvent e : pending) {
        kafkaTemplate.send(e.getTopic(), e.getAggregateId(), e.getPayload())
            .whenComplete((r, ex) -> {
                if (ex == null) outboxRepository.markPublished(e.getId());
            });
    }
}
```

**원자성 보장**: `outbox_event` INSERT와 비즈니스 데이터 변경이 같은 트랜잭션이므로 불일치가 원천적으로 없다. **at-least-once 전제**이기 때문에 Consumer는 반드시 idempotent해야 한다. 지원자의 Kafka Transactional Outbox 구현 경험이 그대로 이 지점에서 설명된다.

## 6. Consumer Idempotency, At-Least-Once, DLQ

Kafka의 기본 전제는 **at-least-once**다. 중복은 반드시 생긴다고 가정한다.

### 6.1 Idempotent Consumer

```java
@KafkaListener(topics = "order.placed", groupId = "point-service")
public void on(OrderPlacedEvent event, Acknowledgment ack) {
    if (processedEventRepository.existsByEventId(event.eventId())) {
        ack.acknowledge();
        return;
    }
    try {
        pointService.accumulate(event.userId(), event.amount());
        processedEventRepository.save(new ProcessedEvent(event.eventId()));
        ack.acknowledge();
    } catch (BusinessException e) {
        // 재시도 대상 아님 → DLQ로
        deadLetterPublisher.send(event, e);
        ack.acknowledge();
    }
}
```

포인트: `event.eventId()`는 **Outbox가 발행 시점에 부여한 UUID**다. Consumer는 이 ID를 기준으로 중복을 거른다.

### 6.2 DLQ 설계

```yaml
spring.kafka.listener.retry.topic.attempts: 3
spring.kafka.listener.retry.topic.backoff.delay: 1000
```

`Spring Kafka`의 `RetryableTopic`을 이용하면 재시도 토픽과 DLQ 토픽을 자동 생성해 준다. DLQ에 쌓인 메시지는 **사람이 보는 큐**다. 자동으로 재처리하면 원인 파악이 안 된다.

## 7. 서비스 경계 결정: 커머스 도메인 예시

| 도메인 | 소유 서비스 | 다른 서비스가 쓰는 방식 |
|--------|-----------|---------------------|
| 상품 메타(이름, 카테고리) | 상품 서비스 | Kafka 이벤트 수신 → Redis 캐시 + 변경 시 키 무효화 |
| 재고 수량 | 재고 서비스 | 주문 시 **동기 gRPC** 차감 호출 (정확성 필수) |
| 주문 | 주문 서비스 | 완료 시 Kafka `order.placed` 발행 |
| 쿠폰 | 쿠폰 서비스 | 사용 시 동기 REST, 발급은 비동기 |
| 알림 | 알림 서비스 | 모든 도메인 이벤트 구독, 발행 쪽에 영향 없음 |

"재고 차감은 왜 동기인가?"라는 질문의 답은 **"비동기로 하면 오버셀(oversell)이 발생하기 때문"**이다. 반대로 알림은 **"조금 늦어도 상관없고, 장애가 나도 주문 자체를 막으면 안 되기 때문"**에 반드시 비동기다.

## 8. 로컬 실습 환경

### 8.1 docker-compose.yml

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: commerce
    ports: ["3306:3306"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  kafka:
    image: bitnami/kafka:3.6
    environment:
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: controller,broker
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 1@localhost:9093
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
    ports: ["9092:9092"]
```

### 8.2 실습 시나리오

1. `product-service`와 `order-service`를 Spring Boot 프로젝트 두 개로 만든다.
2. 상품 서비스에서 상품 이름 변경 → outbox INSERT → Kafka `product.changed` 발행.
3. 주문 서비스 Consumer가 이벤트 수신 → Redis `product:{id}` 키 DEL.
4. 주문 서비스에서 `GET /products/{id}` 요청 → 캐시 miss → 상품 API 호출 → 캐시 set.
5. `kafka-console-producer`로 강제로 중복 이벤트를 주입해 Consumer idempotency 테스트.

## 9. 면접 답변 프레이밍: "서비스 간 데이터 연동을 어떻게 하시나요?"

시니어 백엔드로서 이 질문에는 **3단 구조**로 답한다.

1. **원칙 선언** — "데이터의 사용 시점 최신성, 변경 빈도, 호출 실패 시 허용 수준에 따라 동기와 비동기를 나눕니다."
2. **구체 예시** — "예를 들어 커머스에서 재고 차감은 정확성 요구 때문에 gRPC 동기로, 포인트 적립과 알림은 Kafka 이벤트 기반 비동기로 분리합니다. 상품 메타처럼 변경이 적고 조회가 많은 데이터는 원천 서비스가 변경 이벤트를 발행하면 구독 서비스가 로컬 Redis의 해당 키만 무효화하고, 다음 조회 때 원천 API를 한 번 호출해 캐시를 채우는 하이브리드 방식을 씁니다."
3. **실패 모드와 대응** — "이 구조는 at-least-once 전제이기 때문에 Outbox로 원자성을 보장하고, Consumer는 이벤트 ID 기반 idempotency를 유지하며, 비즈니스 오류는 DLQ로 내보내 사람이 검토합니다. 저는 실제로 Kafka Transactional Outbox를 구현했고, read-heavy 캐시 경합은 StampedLock의 optimistic read로 완화한 경험이 있습니다. RabbitMQ Fanout으로 다중 구독이 필요한 브로드캐스트 연동도 운영해 봤습니다."

이 구조로 답하면 **설계 원칙 → 사례 → 운영 현실**까지 모두 커버된다.

## 10. 체크리스트

- [ ] 데이터별로 동기/비동기 선택 기준을 말로 설명할 수 있다.
- [ ] Cache-Aside에서 TTL만 쓰면 생기는 문제와 이벤트 기반 무효화의 차이를 설명할 수 있다.
- [ ] 이벤트에 전체 DTO를 실을 때와 키만 실을 때의 트레이드오프를 설명할 수 있다.
- [ ] `@TransactionalEventListener(AFTER_COMMIT)`와 Outbox의 차이를 설명할 수 있다.
- [ ] Outbox 테이블 스키마를 손으로 그릴 수 있다.
- [ ] Consumer idempotency를 코드 수준에서 구현할 수 있다.
- [ ] Cache stampede 방어 기법 3가지 이상을 말할 수 있다.
- [ ] 재고 차감을 왜 동기로 두는지, 알림을 왜 비동기로 두는지 한 문장으로 정리할 수 있다.
- [ ] DLQ는 왜 자동 재처리 대상이 아닌지 설명할 수 있다.
- [ ] StampedLock optimistic read가 ReentrantLock보다 유리한 상황을 예시로 들 수 있다.
