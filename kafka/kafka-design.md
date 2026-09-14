---
tags: [study]
---

# Kafka 실전 설계: 파티션 전략, 컨슈머 그룹, 전달 보장, 재시도, 순서 보장 트레이드오프

## 이 문서의 범위

Kafka를 운영하려면 파티션 수, 컨슈머 장애, 메시지 순서와 유실 허용 범위를 함께 결정해야 한다. 설정값 하나보다 각 선택이 처리량과 복구 방식에 미치는 영향을 이해하는 것이 중요하다.
버전에 따라 달라지는 설명과 로컬 실습은 Apache Kafka 4.3을 기준으로 한다.

이 문서는 Kafka의 내부 동작을 설계 관점에서 다시 읽는다. 파티션 수 결정, 컨슈머 그룹 병렬성 모델, 전달 보장 방식, 재시도·DLQ 패턴과 순서 보장 트레이드오프를 Java와 Spring Kafka 예제로 정리한다.

---

## Kafka 기본 동작 원리

설계 결정의 의미를 잡으려면 Kafka가 **어떤 자료구조 위에 동작하는가**를 먼저 봐야 한다. Kafka는 큐가 아니라 **분산 커밋 로그**(Distributed Commit Log)다. 이 한 줄이 뒤이은 모든 트레이드오프를 설명한다.

### 발행 → 저장 → 구독

- **발행**(Produce): 프로듀서가 특정 토픽의 한 파티션에 메시지를 쓴다. 메시지는 그 파티션 안에서 **순차적으로 append**된다.
- **저장**(Store): 브로커는 메시지에 고유 번호인 **오프셋**을 부여해 디스크에 저장한다. 한 번 쓰인 메시지는 변경되지 않는다(append-only).
- **구독**(Consume): 컨슈머는 자신이 어디까지 읽었는지를 **컨슈머 오프셋**으로 관리한다. "5번까지 읽었다"고 커밋하면 다음에는 6번부터 읽기 시작한다.

큐가 메시지를 꺼내는 순간 사라지는 모델이라면, Kafka는 **읽어도 사라지지 않는다**. 같은 메시지를 다른 컨슈머 그룹이 다시 읽을 수 있고, 오프셋을 되감아 재처리할 수도 있다.

### 데이터 복제와 메타데이터 quorum의 분리

Kafka 4.x에서는 데이터 파티션 복제와 KRaft 메타데이터 합의를 구분해야 한다.

- **데이터 파티션**: replication factor와 `min.insync.replicas`가 쓰기를 승인할 복제본 조건을 정한다. 예를 들어 `RF=3`, `min.insync.replicas=2`와 `acks=all`을 함께 사용하면 복제본 하나가 중단돼도 두 ISR이 남아 있는 동안 쓰기를 계속할 수 있다.
- **클러스터 메타데이터**: KRaft controller quorum이 브로커 등록, 토픽과 파티션 배치, 리더 변경의 순서를 합의한다. 컨트롤러는 보통 홀수로 구성하며 세 대면 한 대의 장애를 허용한다.

브로커와 컨트롤러 역할은 같은 프로세스에 함께 둘 수도 있고 운영 규모에 따라 분리할 수도 있다.
따라서 "Kafka는 무조건 브로커 세 대"보다 필요한 데이터 복제본 수와 controller quorum의 장애 허용 범위를 각각 계산해야 한다.

이후 섹션의 파티션 설계·전달 보장·순서 보장 같은 결정은 모두 이 분산 커밋 로그 구조 위에서 의미를 가진다.

---

## 파티션 설계

### 파티션이 결정하는 것

Kafka에서 파티션은 **병렬성의 단위**이자 **순서 보장의 경계**다. 하나의 파티션 내 메시지는 오프셋 순서대로 저장되고 그 순서대로 소비된다. 서로 다른 파티션 간에는 순서 보장이 없다.

- 프로듀서는 메시지를 파티션에 쓴다. 기본 파티셔너에서 같은 키는 파티션 수와 파티셔너가 바뀌지 않는 동안 같은 파티션으로 라우팅된다.
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

예를 들어 초당 10만 건을 처리해야 하고, 같은 크기와 처리 로직으로 검증한 단일 파티션 처리량이 초당 2만 건이라면 계산상 최소 다섯 개가 필요하다.
실제 파티션 수는 장애 시 리더 재배치, 피크 트래픽과 향후 consumer 확장 여유를 더해 부하 시험으로 결정한다.

**컨슈머 확장성 기반**

미래에 컨슈머를 몇 개까지 수평 확장할 것인지 먼저 결정한다.
한 consumer group의 병렬 처리 상한은 파티션 수이지만,
파티션이 늘면 브로커 메타데이터, 파일, 복제와 리더 선출 비용도 증가한다.
예상 최대치만 보고 크게 잡지 않고 부하 시험과 운영 비용을 함께 본다.

**순서 보장 요구사항 기반**

"같은 사용자 이벤트는 반드시 순서대로 처리해야 한다"는 요구가 있다면 `userId`를 파티션 키 후보로 검토한다.
파티션 수가 많아도 활동량이 큰 키 하나의 레코드는 한 파티션에 모이므로,
키별 트래픽 분포와 단일 키의 최대 처리량을 따로 확인해야 한다.

### 파티션 키 전략

| 전략 | 방식 | 적합한 상황 |
|------|------|-------------|
| 키 없음 | batch를 효율적으로 만들 수 있는 파티션에 분산 | 개체별 순서가 필요 없는 이벤트 |
| `userId` 키 | 동일 유저 이벤트 → 동일 파티션 | 유저별 이벤트 순서 보장 |
| `orderId` 키 | 동일 주문 이벤트 → 동일 파티션 | 주문 상태 전이 순서 보장 |
| 복합 키 | `tenantId`와 `entityId` 조합 | 멀티테넌트 환경에서 격리와 순서를 동시에 |

**키를 잘못 설계하면 핫 파티션이 생긴다.** 예를 들어 `countryCode`를 키로 쓰면 대한민국 트래픽이 한 파티션에 쏠릴 수 있다. 키의 카디널리티가 낮을수록 핫 파티션 위험이 높다.

---

## 컨슈머 그룹 동작 원리

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

classic protocol에서 eager assignor를 사용하면 기존 파티션을 모두 반납하고 다시 할당하므로 group 전체 처리가 잠시 멈출 수 있다.
`CooperativeStickyAssignor`는 이동이 필요한 파티션을 점진적으로 넘겨 중단 범위를 줄인다.
Kafka 4.x의 새 consumer rebalance protocol은 broker가 할당을 계산하고 증분 방식으로 파티션 소유권을 조정하지만,
클라이언트 호환성을 확인하고 `group.protocol=consumer`를 명시해야 한다.

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

처리와 오프셋 커밋의 순서가 소비 측 전달 보장을 결정한다.

**자동 커밋**(`enable.auto.commit=true`): `poll()`로 반환된 레코드의 위치를 주기적으로 커밋한다. 애플리케이션 처리가 완료됐는지 알지 못하므로 처리 중 장애가 발생하면 누락 또는 중복이 생길 수 있다.

**컨테이너 관리 커밋**: Spring Kafka는 `enable.auto.commit=false`에서 리스너가 정상 반환된 뒤 `AckMode` 규칙에 따라 커밋할 수 있다. 대부분은 `BATCH`나 `RECORD`로 처리 완료와 커밋 순서를 맞추고, 직접 ack가 필요한 특수한 경우에만 manual mode를 사용한다.

```java
@KafkaListener(topics = "order-events", groupId = "order-consumer-group")
public void consume(ConsumerRecord<String, String> record) {
    orderService.process(record.value());
    // 정상 반환 뒤 컨테이너가 AckMode에 따라 커밋한다.
    // 실패는 error handler가 재시도 또는 DLT 정책으로 처리한다.
}
```

---

## 메시지 전달 보장 방식

전달 보장은 producer의 기록 승인 조건,
consumer의 처리와 offset commit 순서,
출력 대상이 Kafka인지 외부 DB인지에 따라 달라진다.
이 세 경계를 합치지 않고 나눠서 판단해야 한다.

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

정상적인 재시도와 복제 조건 안에서 유실을 피하는 대신 중복 처리를 허용하는 방식이다.

- 프로듀서는 `acks=all`로 브로커 응답을 받을 때까지 재시도한다.
- 컨슈머는 처리 완료 후 컨테이너 관리 또는 수동 방식으로 오프셋을 커밋한다.
- 브로커가 메시지를 저장했지만 producer가 응답을 받지 못하면 재시도할 수 있다. 멱등성이 꺼져 있으면 같은 레코드가 중복 기록될 수 있다.

이 방식을 쓸 때는 **컨슈머 로직에 멱등성**을 반드시 구현해야 한다. 같은 메시지를 두 번 처리해도 결과가 동일해야 한다.

```java
// 개념 예시: DB의 unique 제약으로 동시 중복도 차단한다.
@Transactional
public void processOrder(String eventId, String eventJson) {
    int inserted = processedEventRepository.insertIfAbsent(eventId);
    if (inserted == 0) {
        return;
    }
    orderService.handle(eventJson);
}
```

### Exactly-Once (정확히 한 번)

Kafka의 exactly-once는 **범위가 정해진 보장**이다.
Idempotent Producer는 한 producer session의 재시도로 같은 레코드가 중복 기록되는 문제를 막고,
Transaction API는 Kafka 안에서 여러 write와 consumer offset commit을 원자적으로 묶는다.

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

| 방식 | 장애 시 결과 | 적용 범위 | 주요 조건 |
|------|------------|----------|-----------|
| At-most-once | 처리되지 않은 레코드가 생길 수 있음 | consumer 처리 | 처리 전에 위치를 확정 |
| At-least-once | 같은 레코드를 다시 처리할 수 있음 | consumer 처리 | 처리 완료 뒤 위치를 확정하고 멱등성 적용 |
| Exactly-once | 중단된 transaction의 출력이 보이지 않음 | Kafka의 read-process-write | transaction과 `read_committed` consumer |

외부 DB나 API는 Kafka transaction에 포함되지 않는다.
Kafka 밖에 부수 효과가 있으면 at-least-once와 멱등한 consumer를 기본으로 검토한다.
구체적인 실패 구간은 [Spring Kafka 컨슈머 오프셋 커밋과 트랜잭션 정렬](./spring-kafka-listener-offset-commit-transaction.md)에서 다룬다.

---

## 재시도와 데드 레터 큐 (DLQ)

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
            .maxAttempts(4)                          // 원본 1회, 재시도 3회
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

## 순서 보장 트레이드오프

### 파티션 내 순서만 보장된다

Kafka는 **파티션 내에서만 순서를 보장**한다. 이것을 이해하지 못하면 설계 오류가 생긴다.

예를 들어 `주문 생성 → 결제 완료 → 배송 시작` 이 세 이벤트가 서로 다른 파티션에 들어가면, 컨슈머는 어떤 순서로도 소비할 수 있다. 따라서 순서가 중요한 이벤트는 반드시 같은 키로 같은 파티션에 보내야 한다.

```java
// 잘못된 예: 키 없이 발행 → 파티션 분산, 순서 비보장
kafkaTemplate.send("order-events", orderEventJson);

// 파티션 수와 파티셔너가 같다면 같은 주문의 이벤트는 같은 파티션
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

조회 이벤트, 로그와 통계 이벤트처럼 개체별 순서가 의미 없는 경우에는 키 없이 보내 batch 효율과 분산을 활용할 수 있다.

### 프로듀서 재시도와 순서 역전

멱등성이 꺼져 있고 `max.in.flight.requests.per.connection`이 1보다 큰 상태에서 재시도가 발생하면 레코드 순서가 바뀔 수 있다.
Kafka 4.3 producer는 충돌하는 설정이 없으면 idempotence가 기본으로 활성화된다.

이를 방지하려면 `max.in.flight.requests.per.connection=1`로 설정하거나, 멱등성 프로듀서를 활성화해야 한다.

```java
// 멱등성 프로듀서 설정 (Kafka 0.11+)
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
// enable.idempotence=true 설정 시 아래 값들이 자동으로 조정됨:
// acks=all, retries=Integer.MAX_VALUE, max.in.flight.requests.per.connection=5
```

---

## 로컬 실습 환경 구성 (Docker Compose)

### Docker Compose

```yaml
services:
  kafka:
    image: apache/kafka:4.3.1
    container_name: kafka
    ports:
      - "9092:9092"
```

공식 이미지는 환경 변수를 따로 주지 않으면 단일 노드 combined KRaft 개발 설정으로 실행된다.
복제 계수 1이므로 장애 허용 구성을 검증하는 용도가 아니라 API와 처리 흐름을 익히는 용도다.

### 토픽 및 실습 CLI 명령어

```bash
# 컨테이너 기동
docker compose up -d

# 토픽 생성 (파티션 3개, 복제 계수 1개)
docker exec -it kafka \
  /opt/kafka/bin/kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --partitions 3 \
  --replication-factor 1

# 토픽 목록 확인
docker exec -it kafka \
  /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# 파티션 정보 확인
docker exec -it kafka \
  /opt/kafka/bin/kafka-topics.sh --describe \
  --topic order-events --bootstrap-server localhost:9092

# 키 있는 메시지 발행 (키|값 형식)
docker exec -it kafka \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --property "parse.key=true" \
  --property "key.separator=|"
# 입력: order-1001|{"status":"CREATED","amount":50000}
# 입력: order-1001|{"status":"PAID","amount":50000}

# 컨슈머 그룹으로 소비 (파티션 정보 함께 출력)
docker exec -it kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --group test-group \
  --from-beginning \
  --property print.key=true \
  --property print.partition=true

# 컨슈머 그룹 lag 확인 (중요: 적체량 모니터링)
docker exec -it kafka \
  /opt/kafka/bin/kafka-consumer-groups.sh \
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

파티션 0의 lag가 5라는 것은 consumer group의 committed offset이 log end offset보다 다섯 뒤에 있다는 의미다.
처리가 진행됐지만 commit되지 않은 레코드도 포함될 수 있으므로 미처리 건수와 항상 같지는 않다.
lag가 계속 증가하면 파티션별 유입률, 처리 시간, 외부 의존성, 오류 재시도와 rebalance를 확인한 뒤 병목에 맞는 조치를 고른다.

### Spring Boot 의존성 (build.gradle)

```groovy
dependencies {
    implementation 'org.springframework.kafka:spring-kafka'
    testImplementation 'org.springframework.kafka:spring-kafka-test'
}
```

---

## 실행 가능한 Java 예제

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
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);  // container가 commit 관리
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
        factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.RECORD);
        return factory;
    }
}

@Component
@Slf4j
@RequiredArgsConstructor
public class OrderEventConsumer {

    private final OrderService orderService;
    @KafkaListener(
        topics = "order-events",
        groupId = "order-consumer-group",
        containerFactory = "kafkaListenerContainerFactory"
    )
    public void consume(ConsumerRecord<String, String> record) {
        log.info("수신. partition={}, offset={}, key={}",
            record.partition(), record.offset(), record.key());

        orderService.handleEvent(record.value());
        // 정상 반환 뒤 container가 RECORD 단위로 commit한다.
        // 예외는 container의 error handler와 DLT 정책에 맡긴다.
    }
}
```

---

## 나쁜 예 vs 개선된 예

### 나쁜 예 1: 키 없는 발행과 순서 의존 비즈니스 로직

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

자동 commit이 애플리케이션 처리보다 먼저 완료된 뒤 프로세스가 중단되면 해당 record는 다시 전달되지 않는다.

```java
// GOOD: 리스너가 정상 반환된 뒤 container가 offset을 commit한다.
public void consume(ConsumerRecord<String, String> record) {
    orderService.process(record.value());
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
// GOOD: RetryTopicConfiguration으로 재시도 횟수 제한 후 DLQ 이동
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

## 체크리스트

### 설계 시 확인 사항

- [ ] 목표 처리량과 consumer 병렬성 및 broker 비용을 함께 측정해 파티션 수 결정
- [ ] 순서 보장이 필요한 이벤트에 파티션 키 설정
- [ ] 키의 카디널리티가 충분히 높아 핫 파티션 위험이 낮음
- [ ] 장애 허용 목표에 맞춰 replication factor, `min.insync.replicas`와 `acks` 조합 결정
- [ ] 멱등성 프로듀서(`enable.idempotence=true`) 활성화
- [ ] 도메인별 전달 보장 수준(at-most-once / at-least-once / exactly-once) 명시적 결정

### 컨슈머 구현 체크리스트

- [ ] `enable.auto.commit=false`에서 처리 완료 뒤 container가 offset을 commit하도록 AckMode 결정
- [ ] 오류 유형별 처리 분기 (일시 오류 → 재시도, 비복구 오류 → DLQ)
- [ ] 컨슈머 로직에 멱등성 보장 (중복 소비 시 결과 동일)
- [ ] DLQ 메시지 모니터링 및 알람 연동
- [ ] client와 broker 호환성에 맞춰 classic cooperative 또는 새 consumer protocol 결정
- [ ] `max.poll.interval.ms` > 실제 처리 시간 × 배치 크기

### 운영 체크리스트

- [ ] 컨슈머 그룹 lag 모니터링 (Kafka UI 또는 Prometheus와 Grafana)
- [ ] DLQ 토픽 메시지 적체 시 알람 설정
- [ ] 배포 시 컨슈머 graceful shutdown 확인 (처리 중 메시지 커밋 완료 후 종료)
- [ ] 토픽 보존 기간(`retention.ms`) 비즈니스 요건에 맞게 설정

---

> **관련 문서**
> - [Kafka 기본 개념](./basic.md)
> - [Kafka를 로그로 이해하기](./log-as-unifying-abstraction.md)
> - [Spring Kafka 컨슈머 오프셋 커밋과 트랜잭션 정렬](./spring-kafka-listener-offset-commit-transaction.md)
> - [분산 트랜잭션과 Outbox 패턴](../architecture/distributed-systems/distributed-transaction-outbox-pattern.md)

## 참고 자료

- [Apache Kafka 4.3 — Design](https://kafka.apache.org/43/design/design/)
- [Apache Kafka 4.3 — Producer Configuration](https://kafka.apache.org/43/configuration/producer-configs/)
- [Apache Kafka 4.3 — Consumer Rebalance Protocol](https://kafka.apache.org/43/operations/consumer-rebalance-protocol/)
- [Apache Kafka 4.3 — Docker](https://kafka.apache.org/43/getting-started/docker/)
- [Spring for Apache Kafka Reference Documentation](https://docs.spring.io/spring-kafka/reference/)
