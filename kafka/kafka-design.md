# [초안] Kafka 실전 설계: 파티션 전략, 컨슈머 그룹, 전달 보장, 재시도, 순서 보장 트레이드오프

## 왜 이 주제가 중요한가

Kafka를 "메시지 큐로 쓴다"는 말은 맞지만, 그것만으로는 시니어 면접을 통과할 수 없다. 면접관이 묻고 싶은 것은 "파티션을 몇 개로 잡았고 왜 그랬나", "컨슈머가 죽었을 때 리밸런싱은 어떻게 되나", "결제 이벤트인데 순서가 바뀌면 어떻게 처리했나", "메시지 유실은 허용 가능한 도메인인가" 같은 설계 판단이다.

이 문서는 Kafka의 내부 동작을 설계 관점에서 다시 읽는다. 파티션 수 결정, 컨슈머 그룹 병렬성 모델, 전달 보장 방식(at-most-once / at-least-once / exactly-once), 재시도·DLQ 패턴, 순서 보장 트레이드오프를 중심으로 Java + Spring Kafka 기반 예제와 함께 정리한다.

---

## 1. 파티션 설계

### 파티션이 결정하는 것

Kafka에서 파티션은 **병렬성의 단위**이자 **순서 보장의 경계**다. 하나의 파티션 내 메시지는 오프셋 순서대로 저장되고 그 순서대로 소비된다. 서로 다른 파티션 간에는 순서 보장이 없다.

- 프로듀서는 메시지를 파티션에 쓴다. 같은 키를 가진 메시지는 항상 같은 파티션으로 라우팅된다 (기본 파티셔너 기준).
- 컨슈머 그룹 내 한 파티션은 최대 하나의 컨슈머 인스턴스가 소비한다. 컨슈머 인스턴스 수가 파티션 수를 초과하면 초과된 인스턴스는 놀게 된다.

```
파티션 3개, 컨슈머 3개 → 각 컨슈머가 파티션 1개 담당
파티션 3개, 컨슈머 5개 → 2개 컨슈머는 idle
파티션 6개, 컨슈머 3개 → 각 컨슈머가 파티션 2개 담당
```

### 파티션 수 결정 기준

파티션 수를 정하는 공식은 없다. 아래 세 가지 관점을 따져보고 조율한다.

**처리량 기반 계산**

```
목표 처리량 / 단일 파티션 최대 처리량 = 최소 파티션 수
```

예를 들어 초당 10만 건을 처리해야 하고, 컨슈머 1개가 파티션 1개에서 초당 2만 건 처리가 가능하다면 최소 5개 파티션이 필요하다. 실제로는 여유분을 두어 8~10개로 잡는다.

**컨슈머 확장성 기반**

미래에 컨슈머를 몇 개까지 수평 확장할 것인지 먼저 결정한다. 그 수보다 파티션 수가 많아야 의미가 있다. 파티션 수는 나중에 늘릴 수 있지만 줄일 수 없으므로, 예상 최대치를 기준으로 처음부터 넉넉하게 잡는다.

**순서 보장 요구사항 기반**

"같은 사용자 이벤트는 반드시 순서대로 처리해야 한다"는 요구가 있다면, `userId`를 파티션 키로 쓴다. 이 경우 파티션 수가 많을수록 특정 파티션에 특정 사용자 이벤트가 집중될 가능성이 줄어들어 부하가 고르게 분산된다.

### 파티션 키 전략

| 전략 | 방식 | 적합한 상황 |
|------|------|-------------|
| 키 없음 (Round-robin) | 파티션에 순서대로 분산 | 순서 무관, 처리량 최대화 |
| `userId` 키 | 동일 유저 이벤트 → 동일 파티션 | 유저별 이벤트 순서 보장 |
| `orderId` 키 | 동일 주문 이벤트 → 동일 파티션 | 주문 상태 전이 순서 보장 |
| 복합 키 | `tenantId + entityId` 조합 | 멀티테넌트 환경에서 격리와 순서를 동시에 |

**키를 잘못 설계하면 핫 파티션이 생긴다.** 예를 들어 `countryCode`를 키로 쓰면 대한민국 트래픽이 한 파티션에 쏠릴 수 있다. 키의 카디널리티가 낮을수록 핫 파티션 위험이 높다.

---

## 2. 컨슈머 그룹 동작 원리

### 컨슈머 그룹과 파티션 할당

컨슈머 그룹은 동일 토픽을 논리적으로 독립해서 소비하는 단위다. 여러 그룹이 같은 토픽을 구독해도 각 그룹은 자신만의 오프셋을 유지하므로 서로 간섭하지 않는다.

```
Topic: order-events (파티션 4개)

그룹 A: notification-service  → 파티션 0,1,2,3을 각각 1개씩 담당
그룹 B: analytics-service     → 파티션 0,1,2,3을 각각 1개씩 독립 소비
```

이 구조를 활용하면 이벤트 하나로 알림, 분석, 정산 등 여러 다운스트림 서비스를 팬아웃할 수 있다.

### 리밸런싱

컨슈머 그룹 멤버가 추가되거나 제거될 때 파티션 할당이 재조정된다. 이것이 **리밸런싱**이다.

리밸런싱 트리거:
- 컨슈머 인스턴스 추가 (배포, 스케일아웃)
- 컨슈머 인스턴스 제거 또는 장애
- `session.timeout.ms` 내에 heartbeat 미수신 → 그룹 코디네이터가 해당 인스턴스를 탈퇴 처리

리밸런싱 중에는 해당 그룹의 전체 소비가 잠시 멈춘다 (**Stop-The-World Rebalance**). Kafka 2.4+부터 도입된 **Incremental Cooperative Rebalancing**은 전체 파티션을 한 번에 재할당하지 않고 점진적으로 이전해 중단 시간을 최소화한다.

```java
// Spring Kafka에서 Cooperative Sticky 할당 전략 설정
@Bean
public ConsumerFactory<String, String> consumerFactory() {
    Map<String, Object> props = new HashMap<>();
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
    props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-consumer-group");
    props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
        CooperativeStickyAssignor.class.getName()); // 점진적 리밸런싱
    props.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, 30000);
    props.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, 3000);
    return new DefaultKafkaConsumerFactory<>(props,
        new StringDeserializer(), new StringDeserializer());
}
```

### 오프셋 커밋 전략

오프셋을 언제 커밋하느냐가 전달 보장 방식을 결정한다.

**자동 커밋 (`enable.auto.commit=true`)**: 주기마다 자동으로 커밋. 처리 전에 커밋되면 메시지가 유실될 수 있다. `at-most-once` 에 가깝다.

**처리 후 수동 커밋**: 비즈니스 로직이 완료된 뒤 명시적으로 커밋. Spring Kafka에서 `AckMode.MANUAL_IMMEDIATE`를 사용한다.

```java
@KafkaListener(topics = "order-events", groupId = "order-consumer-group")
public void consume(ConsumerRecord<String, String> record, Acknowledgment ack) {
    try {
        orderService.process(record.value());
        ack.acknowledge(); // 처리 성공 후에만 오프셋 커밋
    } catch (RecoverableException e) {
        // 재시도 가능한 오류 → 커밋 안 함, 재소비됨
        throw e;
    } catch (NonRecoverableException e) {
        // 재시도 불가 → DLQ로 보내고 커밋
        dlqSender.send(record);
        ack.acknowledge();
    }
}
```

---

## 3. 메시지 전달 보장 방식

Kafka는 설정에 따라 세 가지 전달 보장 수준 중 하나를 선택한다. 어떤 수준을 쓸 것인지는 도메인의 유실 허용 여부와 중복 처리 가능 여부로 결정한다.

### At-Most-Once (최대 한 번)

메시지가 유실될 수는 있지만 중복되지는 않는 방식이다. 프로듀서가 `acks=0`으로 설정하면 브로커 응답을 기다리지 않는다. 컨슈머가 메시지를 읽자마자 오프셋을 커밋하면 처리 전 장애 시 유실이 발생한다.

```yaml
# 프로듀서 설정
spring:
  kafka:
    producer:
      acks: 0  # 응답 대기 없음 → 최고 속도, 유실 가능
    consumer:
      enable-auto-commit: true
      auto-commit-interval: 1000  # 처리 전 커밋 가능성 있음
```

적합한 도메인: 대량 로그 수집, 통계용 클릭 이벤트처럼 한두 건 유실이 비즈니스에 영향이 없는 경우.

### At-Least-Once (최소 한 번)

메시지가 절대 유실되지 않지만 중복 소비가 발생할 수 있는 방식이다. Kafka의 기본 동작 방향이다.

- 프로듀서는 `acks=all`로 브로커 응답을 받을 때까지 재시도한다.
- 컨슈머는 처리 완료 후 수동으로 오프셋을 커밋한다.
- 브로커가 메시지를 저장했지만 네트워크 오류로 프로듀서에 응답을 못 보내면, 프로듀서는 재전송한다 → 중복 발생.

이 방식을 쓸 때는 **컨슈머 로직에 멱등성**을 반드시 구현해야 한다. 같은 메시지를 두 번 처리해도 결과가 동일해야 한다.

```java
// 멱등성 구현 예: DB에서 중복 체크 후 처리
@Transactional
public void processOrder(String orderId, String eventJson) {
    if (processedEventRepository.existsByOrderId(orderId)) {
        log.info("이미 처리된 이벤트. orderId={}", orderId);
        return; // 중복 처리 방지
    }
    // 실제 비즈니스 로직
    orderService.handle(eventJson);
    processedEventRepository.save(new ProcessedEvent(orderId));
}
```

### Exactly-Once (정확히 한 번)

메시지가 유실되지도, 중복되지도 않는 방식이다. Kafka 0.11+부터 **Idempotent Producer**와 **Transaction API**로 구현 가능하다.

**Idempotent Producer**: 프로듀서가 메시지마다 고유한 Sequence Number를 부여한다. 브로커가 중복 번호를 받으면 기록하지 않고 버린다.

**Transactional API**: 여러 토픽에 메시지를 쓰거나 "읽기-처리-쓰기" 과정을 원자적으로 묶는다. 컨슈머는 `isolation.level=read_committed`로 커밋된 메시지만 읽는다.

```java
// 멱등성 프로듀서 설정 (Kafka 0.11+)
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
// enable.idempotence=true 설정 시 자동 조정:
// acks=all, retries=Integer.MAX_VALUE, max.in.flight.requests.per.connection=5

// 트랜잭셔널 프로듀서 (정확히 한 번)
props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-producer-1");
KafkaTemplate<String, String> template = new KafkaTemplate<>(producerFactory);

template.executeInTransaction(t -> {
    t.send("order-events", key, value1);
    t.send("audit-log", key, value2);
    return true; // 두 토픽에 원자적으로 발행
});
```

| 방식 | 유실 가능성 | 중복 가능성 | 난이도 | 주요 설정 |
|------|------------|------------|--------|-----------|
| At-most-once | 있음 | 없음 | 낮음 | `acks=0`, `enable.auto.commit=true` |
| At-least-once | 없음 | 있음 | 보통 | `acks=all`, `retries>0`, 수동 커밋 |
| Exactly-once | 없음 | 없음 | 높음 | `enable.idempotence=true`, `isolation.level=read_committed` |

실무에서는 대부분 **at-least-once + 컨슈머 멱등성** 조합을 쓴다. Exactly-once는 트랜잭션 오버헤드가 크고 운영 복잡도가 높아, 결제나 금융 처리처럼 절대적으로 정확해야 하는 경우에만 선택한다.

---

## 4. 재시도와 데드 레터 큐 (DLQ)

### 왜 재시도 전략이 필요한가

컨슈머에서 처리 실패가 발생하면 두 가지 선택이 있다.

1. 오프셋을 커밋하지 않고 같은 메시지를 계속 재소비한다 → 파티션 처리가 완전히 막힌다 (**blocking**)
2. 실패한 메시지를 별도 토픽으로 보내고 다음 메시지로 넘어간다 → 순서가 깨질 수 있지만 전체 흐름은 유지된다

실무에서는 오류 유형을 분리하는 것이 핵심이다.

| 오류 유형 | 예시 | 처리 방향 |
|-----------|------|-----------|
| 일시적 오류 (Transient) | DB timeout, downstream API 503 | 지수 백오프 후 재시도 |
| 비즈니스 오류 (Business) | 유효하지 않은 주문 ID, 잔액 부족 | DLQ로 이동, 알람 발송 |
| 포맷 오류 (Poison Pill) | 역직렬화 실패, 스키마 불일치 | 즉시 DLQ 이동 |

### 재시도 토픽 패턴

Netflix, Uber 등에서 대중화된 패턴으로, 실패한 메시지를 지연 재처리 전용 토픽으로 보내 단계적으로 재시도한다.

```
order-events           → 메인 토픽
order-events-retry-1   → 30초 지연 후 재시도
order-events-retry-2   → 5분 지연 후 재시도
order-events-retry-3   → 30분 지연 후 재시도
order-events-dlq       → 최종 실패, 사람이 확인
```

Spring Kafka 2.7+의 `RetryTopicConfiguration`을 사용하면 이 토픽들을 자동으로 생성하고 라우팅할 수 있다.

```java
@Configuration
public class RetryTopicConfig {

    @Bean
    public RetryTopicConfiguration orderRetryConfig(KafkaTemplate<String, String> template) {
        return RetryTopicConfigurationBuilder
            .newInstance()
            .maxAttempts(4)                          // 원본 1회 + 재시도 3회
            .exponentialBackoff(1000, 2, 20000)      // 1초 → 2초 → 4초... 최대 20초
            .retryTopicSuffix("-retry")
            .dltSuffix("-dlq")
            .dltHandlerMethod("handleDlq")
            .includeTopic("order-events")
            .create(template);
    }
}

@Component
public class OrderConsumer {

    @KafkaListener(topics = "order-events", groupId = "order-consumer-group")
    public void consume(String message) {
        orderService.process(message); // 실패하면 Spring이 retry 토픽으로 자동 라우팅
    }

    @DltHandler
    public void handleDlq(String message, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {
        log.error("DLQ 도달. topic={}, message={}", topic, message);
        alertService.notifyOnCall(topic, message); // 온콜 알람
    }
}
```

### 지수 백오프와 Jitter

재시도 간격을 고정으로 설정하면 여러 컨슈머가 동시에 재시도해 **Thunder Herd** 현상이 생긴다. 지수 백오프에 랜덤 jitter를 더하면 재시도가 시간적으로 분산된다.

```java
@Retryable(
    value = TransientDataAccessException.class,
    maxAttempts = 5,
    backoff = @Backoff(delay = 1000, multiplier = 2, maxDelay = 20000, random = true)
)
public void process(String message) {
    // 1초, ~2초, ~4초, ~8초, ~16초 → 최대 20초 상한, 각 간격에 jitter 추가
}
```

---

## 5. 순서 보장 트레이드오프

### 파티션 내 순서만 보장된다

Kafka는 **파티션 내에서만 순서를 보장**한다. 이것을 이해하지 못하면 설계 오류가 생긴다.

예를 들어 `주문 생성 → 결제 완료 → 배송 시작` 이 세 이벤트가 서로 다른 파티션에 들어가면, 컨슈머는 어떤 순서로도 소비할 수 있다. 따라서 순서가 중요한 이벤트는 반드시 같은 키로 같은 파티션에 보내야 한다.

```java
// 잘못된 예: 키 없이 발행 → 파티션 분산, 순서 비보장
kafkaTemplate.send("order-events", orderEventJson);

// 올바른 예: orderId를 키로 → 같은 주문의 이벤트는 항상 같은 파티션
kafkaTemplate.send("order-events", order.getId().toString(), orderEventJson);
```

### 순서 보장과 병렬성 사이의 트레이드오프

같은 키의 이벤트를 같은 파티션에 넣으면 순서가 보장되지만, 그 파티션을 담당하는 컨슈머 스레드 1개가 순차 처리해야 한다. 즉, **순서 보장과 병렬 처리는 서로 반비례**한다.

이 문제를 완화하는 실무 패턴:

**1. 파티션 수를 충분히 늘린다**

`orderId`를 키로 쓰면 주문별로 파티션이 나뉜다. 파티션이 100개라면 이론적으로 100개의 주문을 병렬 처리할 수 있다.

**2. 컨슈머 내부에서 동시성을 높인다**

```java
@Bean
public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory() {
    ConcurrentKafkaListenerContainerFactory<String, String> factory =
        new ConcurrentKafkaListenerContainerFactory<>();
    factory.setConsumerFactory(consumerFactory());
    factory.setConcurrency(3); // 컨슈머 스레드 3개 → 파티션 3개 담당
    return factory;
}
```

**3. 비순서 허용 도메인에는 키를 쓰지 않는다**

조회 이벤트, 로그, 통계 이벤트처럼 순서가 의미 없는 도메인에는 Round-robin 방식을 써서 처리량을 최대화한다.

### 프로듀서 재시도와 순서 역전

`acks=all`, `retries > 0` 설정에서 재시도가 발생하면 메시지 순서가 바뀔 수 있다. 예를 들어 메시지 A 전송 실패 → 메시지 B 전송 성공 → 메시지 A 재전송 성공 순으로 되면 브로커에는 B, A 순서로 저장된다.

이를 방지하려면 `max.in.flight.requests.per.connection=1`로 설정하거나, 멱등성 프로듀서를 활성화해야 한다.

```java
// 멱등성 프로듀서 설정 (Kafka 0.11+)
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
// enable.idempotence=true 설정 시 아래 값들이 자동으로 조정됨:
// acks=all, retries=Integer.MAX_VALUE, max.in.flight.requests.per.connection=5
```

---

## 6. 로컬 실습 환경 구성 (Docker Compose)

### docker-compose.yml

```yaml
version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    depends_on:
      - kafka
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
```

### 토픽 및 실습 CLI 명령어

```bash
# 컨테이너 기동
docker compose up -d

# 토픽 생성 (파티션 3개, 복제 계수 1개)
docker exec -it <kafka-container-id> \
  kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --partitions 3 \
  --replication-factor 1

# 토픽 목록 확인
docker exec -it <kafka-container-id> \
  kafka-topics --list --bootstrap-server localhost:9092

# 파티션 정보 확인
docker exec -it <kafka-container-id> \
  kafka-topics --describe --topic order-events --bootstrap-server localhost:9092

# 키 있는 메시지 발행 (키|값 형식)
docker exec -it <kafka-container-id> \
  kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --property "parse.key=true" \
  --property "key.separator=|"
# 입력: order-1001|{"status":"CREATED","amount":50000}
# 입력: order-1001|{"status":"PAID","amount":50000}

# 컨슈머 그룹으로 소비 (파티션 정보 함께 출력)
docker exec -it <kafka-container-id> \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --group test-group \
  --from-beginning \
  --property print.key=true \
  --property print.partition=true

# 컨슈머 그룹 lag 확인 (중요: 적체량 모니터링)
docker exec -it <kafka-container-id> \
  kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group test-group
```

lag 출력 예시:

```
GROUP           TOPIC          PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
test-group      order-events   0          5               10              5
test-group      order-events   1          8               8               0
test-group      order-events   2          3               3               0
```

파티션 0의 lag가 5라는 것은 컨슈머가 5개 메시지를 아직 처리하지 못했다는 의미다. lag가 지속적으로 증가하면 컨슈머 처리 속도가 프로듀서 발행 속도를 따라가지 못하는 것이므로, 파티션 수와 컨슈머 수를 늘려야 한다.

### Spring Boot 의존성 (build.gradle)

```groovy
dependencies {
    implementation 'org.springframework.kafka:spring-kafka'
    testImplementation 'org.springframework.kafka:spring-kafka-test'
}
```

---

## 7. 실행 가능한 Java 예제

### 프로듀서 설정

```java
@Configuration
public class KafkaProducerConfig {

    @Bean
    public ProducerFactory<String, String> producerFactory() {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);  // 멱등성 프로듀서
        props.put(ProducerConfig.ACKS_CONFIG, "all");               // 모든 ISR 확인
        props.put(ProducerConfig.RETRIES_CONFIG, 3);
        props.put(ProducerConfig.DELIVERY_TIMEOUT_MS_CONFIG, 120_000);
        props.put(ProducerConfig.BATCH_SIZE_CONFIG, 16384);         // 배치 크기 16KB
        props.put(ProducerConfig.LINGER_MS_CONFIG, 5);              // 5ms 대기 후 배치 전송
        return new DefaultKafkaProducerFactory<>(props);
    }

    @Bean
    public KafkaTemplate<String, String> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}
```

### 순서 보장 발행 예제

```java
@Service
@RequiredArgsConstructor
public class OrderEventPublisher {

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    public void publish(OrderEvent event) {
        String key = event.getOrderId().toString();  // 같은 주문 → 같은 파티션
        String value;
        try {
            value = objectMapper.writeValueAsString(event);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("이벤트 직렬화 실패", e);
        }

        kafkaTemplate.send("order-events", key, value)
            .whenComplete((result, ex) -> {
                if (ex != null) {
                    log.error("이벤트 발행 실패. orderId={}", event.getOrderId(), ex);
                } else {
                    log.info("이벤트 발행 완료. orderId={}, partition={}, offset={}",
                        event.getOrderId(),
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
                }
            });
    }
}
```

### 컨슈머 설정 및 처리

```java
@Configuration
public class KafkaConsumerConfig {

    @Bean
    public ConsumerFactory<String, String> consumerFactory() {
        Map<String, Object> props = new HashMap<>();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "order-consumer-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);  // 수동 커밋
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);
        props.put(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, 300_000); // 5분
        props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
            CooperativeStickyAssignor.class.getName());
        return new DefaultKafkaConsumerFactory<>(props,
            new StringDeserializer(), new StringDeserializer());
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
            new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());
        factory.setConcurrency(3);
        factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL_IMMEDIATE);
        return factory;
    }
}

@Component
@Slf4j
@RequiredArgsConstructor
public class OrderEventConsumer {

    private final OrderService orderService;
    private final KafkaTemplate<String, String> kafkaTemplate;

    @KafkaListener(
        topics = "order-events",
        groupId = "order-consumer-group",
        containerFactory = "kafkaListenerContainerFactory"
    )
    public void consume(
        ConsumerRecord<String, String> record,
        Acknowledgment ack
    ) {
        log.info("수신. partition={}, offset={}, key={}",
            record.partition(), record.offset(), record.key());

        try {
            orderService.handleEvent(record.value());
            ack.acknowledge(); // 처리 성공 후 커밋
        } catch (TransientException e) {
            // 일시 오류: 커밋 안 함 → 재소비 (Spring RetryTopic이 처리)
            log.warn("일시 오류 발생. key={}", record.key(), e);
            throw e;
        } catch (Exception e) {
            // 비복구 오류: DLQ로 보내고 커밋 (파티션 차단 방지)
            log.error("처리 불가 이벤트. key={}", record.key(), e);
            kafkaTemplate.send("order-events-dlq", record.key(), record.value());
            ack.acknowledge();
        }
    }
}
```

---

## 8. 나쁜 예 vs 개선된 예

### 나쁜 예 1: 키 없는 발행 + 순서 의존 비즈니스 로직

```java
// BAD: 키 없이 발행하면 파티션 분산 → 순서 비보장
kafkaTemplate.send("order-events", orderJson);
// 컨슈머에서 "결제 완료"가 "주문 생성"보다 먼저 올 수 있음
```

```java
// GOOD: orderId를 키로 사용
kafkaTemplate.send("order-events", order.getId().toString(), orderJson);
```

### 나쁜 예 2: 처리 전 오프셋 자동 커밋

```yaml
# BAD: application.yml
spring:
  kafka:
    consumer:
      enable-auto-commit: true
      auto-commit-interval: 5000
```

처리 중 애플리케이션이 죽으면 오프셋은 이미 커밋되어 해당 메시지는 영원히 유실된다.

```java
// GOOD: 수동 커밋, 처리 완료 후 acknowledge()
public void consume(ConsumerRecord<String, String> record, Acknowledgment ack) {
    orderService.process(record.value());
    ack.acknowledge(); // 성공 후에만 커밋
}
```

### 나쁜 예 3: 오류 시 무한 루프

```java
// BAD: 예외를 던지면 같은 메시지를 영원히 재시도 → 파티션 완전 차단
@KafkaListener(topics = "order-events")
public void consume(String message) {
    orderService.process(message); // DB 장애로 매번 실패
    // 예외 발생 시 오프셋 커밋 안 됨 → 같은 메시지 계속 소비
}
```

```java
// GOOD: RetryTopicConfiguration으로 재시도 횟수 제한 + DLQ 이동
@Bean
public RetryTopicConfiguration retryConfig(KafkaTemplate<String, String> template) {
    return RetryTopicConfigurationBuilder
        .newInstance()
        .maxAttempts(3)
        .exponentialBackoff(1000, 2, 10000)
        .includeTopic("order-events")
        .create(template);
}
```

### 나쁜 예 4: 파티션 수 < 컨슈머 수

```
파티션 2개, 컨슈머 4개 → 2개 컨슈머는 idle, 처리량은 2개 기준으로 제한됨
```

```
해결: 파티션 수를 예상 최대 컨슈머 수 이상으로 설계 (예: 파티션 8개, 컨슈머 4개로 시작)
```

### 나쁜 예 5: 컨슈머 처리 시간이 max.poll.interval.ms 초과

```java
// BAD: 한 번 poll에서 100개 메시지를 받아 각 2초씩 동기 HTTP 호출
// 100 * 2초 = 200초 > max.poll.interval.ms 기본값 300초
// 배치 크기 늘리면 리밸런싱 발생 위험
props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);
// 각 메시지에서 외부 API 동기 호출 200ms → 100개 * 200ms = 20초 → 괜찮음
// 하지만 외부 API가 느려지면 300초 초과 → 리밸런싱 폭탄
```

```java
// GOOD: max.poll.interval.ms를 실제 처리 시간보다 넉넉하게 설정
props.put(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, 600_000); // 10분
// 또는 max.poll.records를 줄여 한 번에 처리하는 메시지 수 제한
props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 10);
```

---

## 9. 면접 답변 프레임

### Q. Kafka 파티션 수는 어떻게 결정하나요?

> 파티션 수는 세 가지를 동시에 고려합니다. 첫째, 처리량 요건입니다. 목표 TPS를 단일 파티션 최대 처리량으로 나눠서 최소치를 구하고, 여유분을 더합니다. 둘째, 수평 확장 계획입니다. 컨슈머를 최대 몇 개까지 띄울 것인지 먼저 정하고, 파티션은 그보다 많아야 의미 있습니다. 셋째, 순서 보장 요구사항입니다. 순서가 중요한 도메인이면 적절한 키를 정해 같은 엔티티 이벤트가 같은 파티션으로 가게 합니다. 파티션 수는 나중에 줄일 수 없으므로 처음부터 넉넉하게 잡는 게 낫습니다.

### Q. 컨슈머가 죽으면 어떻게 되나요?

> 그룹 코디네이터가 `session.timeout.ms` 내에 heartbeat를 받지 못하면 해당 컨슈머를 그룹에서 제거하고 리밸런싱을 시작합니다. 리밸런싱 동안 해당 그룹의 소비가 잠시 중단됩니다. Kafka 2.4+에서는 Cooperative Sticky Assignor를 쓰면 영향받은 파티션만 재할당해 중단 시간을 최소화할 수 있습니다. 중요한 것은, 죽은 컨슈머가 커밋하지 못한 오프셋부터 다른 컨슈머가 이어 받으므로 컨슈머 로직은 멱등성을 보장해야 합니다.

### Q. 메시지 전달 보장 방식을 어떻게 선택하나요?

> 도메인의 유실 허용 여부와 중복 처리 가능 여부로 결정합니다. 로그·통계처럼 한두 건 빠져도 괜찮으면 at-most-once로 속도를 최우선합니다. 대부분의 비즈니스 이벤트는 at-least-once + 컨슈머 멱등성 조합이 가성비가 좋습니다. 멱등성은 DB에 처리 여부를 기록하거나 Redis로 중복 체크 후 진입하는 방식으로 구현합니다. 결제나 금융처럼 절대 중복이 허용되지 않으면 Kafka Transaction API를 써서 exactly-once를 구현하는데, 트랜잭션 오버헤드가 있어 처리량이 다소 낮아집니다.

### Q. 메시지 처리 실패 시 어떻게 처리하나요?

> 오류 유형을 먼저 분류합니다. DB 타임아웃처럼 일시적 오류는 지수 백오프로 재시도합니다. 잘못된 데이터 포맷처럼 재시도해도 의미 없는 오류는 즉시 DLQ로 이동합니다. Spring Kafka의 RetryTopicConfiguration을 사용하면 재시도 토픽을 단계별로 자동 생성해줘서 메인 파티션 차단 없이 처리할 수 있습니다. DLQ 메시지는 알람을 발송하고, 문제를 수정한 뒤 DLQ 컨슈머로 재처리하거나 수동으로 원본 토픽에 리퍼블리시합니다.

### Q. Kafka에서 순서 보장은 어떻게 하나요?

> Kafka는 파티션 내에서만 순서를 보장합니다. 같은 엔티티 이벤트를 순서대로 처리하려면 엔티티 ID를 파티션 키로 설정해 같은 파티션에 넣어야 합니다. 단, 이렇게 하면 해당 파티션을 담당하는 컨슈머 스레드 하나가 순차 처리하므로 병렬성이 제한됩니다. 순서 요건이 없는 이벤트에는 키를 쓰지 않고 Round-robin으로 분산해 처리량을 최대화합니다. 프로듀서 재시도 시 순서가 역전되는 문제는 `enable.idempotence=true`로 방지합니다.

### Q. 처리량을 높이려면 어떻게 하나요?

> 가장 먼저 파티션 수를 늘리고, 컨슈머 인스턴스 수도 파티션 수에 맞춰 함께 늘립니다. 컨슈머 내부에서는 `ConcurrentKafkaListenerContainerFactory`의 `setConcurrency`로 스레드 수를 조정합니다. `max.poll.records`를 높여 한 번에 더 많은 메시지를 가져올 수도 있지만, 처리 시간이 `max.poll.interval.ms`를 초과하면 리밸런싱이 발생하므로 함께 조정해야 합니다. 프로듀서 쪽에서는 배치 크기(`batch.size`)와 `linger.ms`를 높여 네트워크 I/O를 줄이는 것도 효과적입니다.

---

## 10. 체크리스트

### 설계 시 확인 사항

- [ ] 파티션 수 ≥ 예상 최대 컨슈머 인스턴스 수
- [ ] 순서 보장이 필요한 이벤트에 파티션 키 설정
- [ ] 키의 카디널리티가 충분히 높아 핫 파티션 위험이 낮음
- [ ] 복제 계수 3, `min.insync.replicas` 2로 데이터 안전성 확보
- [ ] 멱등성 프로듀서(`enable.idempotence=true`) 활성화
- [ ] 도메인별 전달 보장 수준(at-most-once / at-least-once / exactly-once) 명시적 결정

### 컨슈머 구현 체크리스트

- [ ] `enable.auto.commit=false`, 처리 완료 후 `ack.acknowledge()` 호출
- [ ] 오류 유형별 처리 분기 (일시 오류 → 재시도, 비복구 오류 → DLQ)
- [ ] 컨슈머 로직에 멱등성 보장 (중복 소비 시 결과 동일)
- [ ] DLQ 메시지 모니터링 및 알람 연동
- [ ] Cooperative Sticky Assignor 설정으로 리밸런싱 영향 최소화
- [ ] `max.poll.interval.ms` > 실제 처리 시간 × 배치 크기

### 운영 체크리스트

- [ ] 컨슈머 그룹 lag 모니터링 (Kafka UI 또는 Prometheus + Grafana)
- [ ] DLQ 토픽 메시지 적체 시 알람 설정
- [ ] 배포 시 컨슈머 graceful shutdown 확인 (처리 중 메시지 커밋 완료 후 종료)
- [ ] 토픽 보존 기간(`retention.ms`) 비즈니스 요건에 맞게 설정

---

> **관련 문서**
> - [메시지 전달 신뢰성 (At-most-once / At-least-once / Exactly-once)](./message-delivery-semantics.md)
> - [Kafka 데이터 정합성 설계](./data-consistency.md)
> - [Kafka 기본 개념 (토픽, 오프셋, 복제)](./basic.md)
