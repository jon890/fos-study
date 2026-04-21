# [초안] RabbitMQ vs Kafka — 백엔드 메시징 선택 기준과 실전 운영 관점

## 왜 이 비교가 중요한가

메시지 브로커 선택은 시스템의 처리량, 일관성, 장애 복구 전략을 결정한다. "비동기 처리 = Kafka" 또는 "이벤트 = RabbitMQ" 식의 단순한 선택은 운영 단계에서 비용과 장애로 돌아온다. 면접에서도 "왜 Kafka를 썼나요?", "RabbitMQ를 써본 경험은요?", "두 개를 같이 쓴다면 어디에 어떤 걸 쓰겠어요?" 같은 질문이 단골로 나온다. 이 질문에 답하려면 두 시스템이 어떤 모델을 선택했고, 그 결과 어떤 워크로드에서 빛나고 어떤 워크로드에서 망가지는지를 구조적으로 설명할 수 있어야 한다.

이 문서는 개념 비교에서 멈추지 않고, 실제 백엔드 시스템에서 발생하는 의사결정 지점, 잘못된 사용 패턴, 로컬 실습 환경, 면접 답변 프레임까지 다룬다.

## 두 시스템의 본질적 차이

RabbitMQ와 Kafka는 둘 다 "메시지를 중개한다"는 점에서 비슷해 보이지만, 출발점이 다르다.

**RabbitMQ는 메시지 브로커(Smart Broker / Dumb Consumer)다.** AMQP 0-9-1 프로토콜을 기반으로 시작했고, 브로커가 라우팅, 필터링, 큐잉, 재시도, dead-letter 처리 같은 복잡한 라우팅 의사결정을 모두 담당한다. 컨슈머는 단순히 큐에서 메시지를 꺼내 ACK만 보낸다. 메시지는 컨슈머가 ACK를 보내는 순간 사라지는 것이 기본 모델이다.

**Kafka는 분산 커밋 로그(Dumb Broker / Smart Consumer)다.** 브로커는 파티션이라는 append-only 로그에 메시지를 쌓아둘 뿐, 어떤 컨슈머가 어디까지 읽었는지 신경 쓰지 않는다. 오프셋 관리는 컨슈머의 책임이고, 메시지는 retention 정책이 만료될 때까지 디스크에 그대로 남는다. 동일 메시지를 여러 컨슈머 그룹이 다른 속도로 다른 시점에 다시 읽을 수 있다.

이 한 줄 차이가 처리량, 순서 보장, 재처리, 라우팅 유연성 모든 곳에서 갈라진다.

## 메시지 모델 비교

### RabbitMQ의 메시지 흐름

```
Producer → Exchange(라우팅 규칙) → Queue → Consumer
```

- Exchange 타입: `direct`, `topic`, `fanout`, `headers`
- Queue는 메시지를 저장하는 단위
- Consumer가 ACK를 보내면 메시지는 큐에서 제거됨
- 같은 메시지를 두 번 처리하려면 Exchange를 통해 두 큐에 복제(fanout) 후 각각 컨슈머가 처리해야 함

### Kafka의 메시지 흐름

```
Producer → Topic(Partition 0..N) → Consumer Group(각자 offset 보유)
```

- Topic은 N개의 Partition으로 나뉨
- Partition 단위로만 순서 보장
- Consumer Group은 각자 자기 offset을 가짐 → 같은 메시지를 여러 그룹이 독립적으로 소비
- 메시지는 retention(`log.retention.hours`, `log.retention.bytes`) 만료 전까지 보존

이 모델 차이로 인해 Kafka는 "이벤트 소싱", "스트림 재처리", "로그 수집" 같은 워크로드에 자연스럽고, RabbitMQ는 "작업 큐", "RPC 응답 큐", "복잡한 라우팅 토폴로지"에 자연스럽다.

## 처리량과 지연 특성

| 항목 | RabbitMQ | Kafka |
|------|----------|-------|
| 단건 지연(latency) | 매우 낮음 (수 ms) | 낮음 (배치 가능, 수~수십 ms) |
| 처리량(throughput) | 수만 msg/s 수준 | 수십만~수백만 msg/s |
| 메시지 크기 | 작은 메시지에 유리 | 작은~중간, 배치 압축 활용 |
| 메시지 순서 | 큐 단위로 단일 컨슈머 시 보장 | Partition 단위 보장 |
| 메시지 보존 | ACK 즉시 삭제 (기본) | retention 기간 내 보존 |

Kafka의 압도적 처리량은 sequential disk write + zero-copy(`sendfile`) + 배치 + 압축의 조합에서 나온다. RabbitMQ는 큐 별로 별도 erlang 프로세스가 돌고 메시지를 하나씩 ack 처리하는 모델이라, 큐 하나당 단일 컨슈머의 처리량 천장이 비교적 낮다. 대신 라우팅과 ack 의미론은 훨씬 풍부하다.

## 신뢰성과 ACK 모델

### RabbitMQ
- Producer publish confirm으로 브로커 도착 보장
- Consumer manual ack로 처리 완료 보장
- ack 못 보내고 컨슈머가 죽으면 메시지는 큐에 그대로 남음(redelivered=true로 다른 컨슈머에 재전달)
- DLX(Dead Letter Exchange)로 실패 메시지 격리
- mirror queue / quorum queue로 HA

### Kafka
- Producer `acks=all` + `min.insync.replicas`로 손실 없음 보장
- 컨슈머는 offset을 commit한 시점까지 처리한 것으로 간주
- "메시지를 처리하지 못했다"는 개념은 컨슈머 책임 → 보통 retry topic / dead letter topic 패턴을 직접 구현
- ISR(In-Sync Replicas) 기반 복제

여기서 중요한 차이: **RabbitMQ의 ack는 "이 메시지 처리 끝"이라는 단건 시그널이고, Kafka의 commit은 "이 offset 이전까지 다 처리했다"는 누적 시그널이다.** 그래서 Kafka에서 메시지 한 건만 실패해서 건너뛰고 싶다면 retry topic을 거쳐 별도 흐름으로 분리하는 것이 정공법이다. 큐에서 단건만 골라서 거부하는 일이 RabbitMQ만큼 자연스럽지 않다.

## 라우팅과 토폴로지

RabbitMQ의 강력함은 라우팅에 있다.

- `direct`: routing key가 정확히 일치하는 큐로
- `topic`: `order.created.kr`, `order.*.kr`, `order.created.#` 같은 패턴 매칭
- `fanout`: 바인딩된 모든 큐로 복제
- `headers`: 메시지 헤더 기반 매칭

이런 라우팅은 Kafka에서 흉내 내려면 별도 Topic을 더 만들거나 Kafka Streams로 분기 처리를 해야 한다. 도메인 이벤트가 다양한 컨슈머 그룹에 다른 조건으로 흩어져야 한다면 RabbitMQ의 exchange 모델이 코드량을 크게 줄여준다.

반대로 "한 토픽에 들어온 모든 이벤트를 N개의 독립 시스템이 각자 자기 시점에 읽고 다시 읽을 수도 있어야 한다"는 요구사항이라면 Kafka가 자연스럽다.

## 실전 백엔드에서의 사용 사례

### RabbitMQ가 더 자연스러운 경우
- 결제, 알림, 이메일 발송 같은 **작업 큐(work queue)** — 한 번만 처리되고 끝나는 단건 작업
- **RPC 스타일 비동기 요청/응답** — reply-to + correlation-id 패턴
- **복잡한 라우팅 규칙** — 우선순위 큐, TTL 큐, 지연 큐(`x-delayed-message` plugin)
- **마이크로서비스 간 명령(command) 전달** — "이 작업을 처리해라"
- 처리 실패 시 단건 재시도, DLQ로 격리하는 운영 모델

### Kafka가 더 자연스러운 경우
- **이벤트 소싱 / CDC** — DB 변경을 로그로 흘려보내는 패턴
- **로그/메트릭 파이프라인** — Filebeat → Kafka → Elasticsearch
- **스트림 처리** — Kafka Streams, Flink로 윈도우 집계
- **여러 다운스트림 시스템에 같은 이벤트 분배** — 추천 시스템, 검색 인덱싱, 데이터 웨어하우스가 모두 같은 주문 이벤트를 각자 시점에 소비
- 며칠~몇 주 단위 **재처리(replay)**가 필요한 시스템

### 둘 다 같이 쓰는 패턴
실제 시스템에서는 한쪽만 쓰는 경우가 드물다. 흔한 조합:
- 사용자 액션 → RabbitMQ로 즉시 처리(이메일, 알림)
- 같은 액션을 도메인 이벤트로 Kafka에 발행 → 분석/검색/추천 파이프라인이 각자 소비
- 결제 같은 트랜잭션은 outbox 패턴으로 DB → Kafka, 후속 작업 큐는 RabbitMQ

## Bad vs Improved 예제

### Bad 1: Kafka를 단순 작업 큐로 사용

```java
// 결제 작업을 Kafka로 던지고, 컨슈머에서 처리 실패 시 그냥 throw
@KafkaListener(topics = "payment-jobs")
public void process(PaymentJob job) {
    paymentService.charge(job); // 여기서 예외가 나면?
}
```

**문제점:**
- 예외가 나면 offset commit이 안 되고 같은 메시지를 무한 재시도 → 파티션 전체가 멈춤(consumer lag 폭발)
- 다른 결제 건들은 동일 파티션에 묶여 있으면 같이 블록됨
- 단건 격리가 어렵다

### Improved 1: retry topic / DLT 분리

```java
@RetryableTopic(
    attempts = "3",
    backoff = @Backoff(delay = 1000, multiplier = 2.0),
    dltStrategy = DltStrategy.FAIL_ON_ERROR
)
@KafkaListener(topics = "payment-jobs")
public void process(PaymentJob job) {
    paymentService.charge(job);
}

@DltHandler
public void handleDlt(PaymentJob job) {
    alertService.notifyOps(job);
    deadLetterRepository.save(job);
}
```

또는 처음부터 RabbitMQ를 쓰고 DLX로 격리하는 게 운영 비용이 더 낮을 수 있다.

### Bad 2: RabbitMQ로 대규모 이벤트 스트림을 영구 보존하려는 시도

```text
- 매일 1억 건 이벤트를 RabbitMQ 큐에 쌓아두고 분석 잡이 다음 날 소비
- 큐 길이가 수천만 단위로 길어지며 메모리 압박, paging
- 컨슈머 그룹 추가 시 같은 데이터를 다시 읽을 방법이 없어 fanout으로 큐를 복제 → 디스크 사용량 폭증
```

**개선 방향**: 이런 워크로드는 Kafka의 본 영역. retention만 잡아두면 컨슈머가 며칠 후 새로 합류해도 처음부터 읽을 수 있다.

### Bad 3: 같은 사용자 이벤트를 Kafka 여러 파티션에 흩뿌려 순서 깨짐

```java
producer.send(new ProducerRecord<>("user-events", event)); // key 없음
```

키가 없으면 라운드 로빈으로 파티션 분배 → 같은 사용자 이벤트가 다른 파티션으로 가서 컨슈머가 처리할 때 순서가 뒤집힘.

### Improved 3: 도메인 키 기반 파티셔닝

```java
producer.send(new ProducerRecord<>("user-events", String.valueOf(event.userId()), event));
```

`userId`를 partition key로 두면 같은 사용자 이벤트는 같은 파티션 → 그 파티션을 담당하는 단일 컨슈머가 순차 처리 → 순서 보장.

## 로컬 실습 환경

`docker-compose.yml`로 둘 다 띄워서 직접 비교해 보는 게 가장 빠르다.

```yaml
version: "3.8"
services:
  rabbitmq:
    image: rabbitmq:3.13-management
    ports:
      - "5672:5672"
      - "15672:15672"   # management UI
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest

  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    depends_on: [zookeeper]
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

실행:

```bash
docker compose up -d
# RabbitMQ UI: http://localhost:15672 (guest/guest)
# Kafka 토픽 생성
docker compose exec kafka kafka-topics --create \
    --topic demo-events --partitions 3 --replication-factor 1 \
    --bootstrap-server localhost:9092
```

## 실행 가능한 예제 (Spring Boot)

### RabbitMQ 작업 큐 예제

`build.gradle`:
```groovy
implementation 'org.springframework.boot:spring-boot-starter-amqp'
```

설정:
```java
@Configuration
class RabbitConfig {
    @Bean Queue paymentQueue() {
        return QueueBuilder.durable("payment.jobs")
            .withArgument("x-dead-letter-exchange", "payment.dlx")
            .build();
    }
    @Bean DirectExchange dlx() { return new DirectExchange("payment.dlx"); }
    @Bean Queue dlq() { return new Queue("payment.dlq"); }
    @Bean Binding dlqBinding() {
        return BindingBuilder.bind(dlq()).to(dlx()).with("payment.jobs");
    }
}
```

발행 / 소비:
```java
@Service
class PaymentPublisher {
    private final RabbitTemplate template;
    void publish(PaymentJob job) {
        template.convertAndSend("payment.jobs", job);
    }
}

@Component
class PaymentWorker {
    @RabbitListener(queues = "payment.jobs")
    public void handle(PaymentJob job) {
        // 실패 시 예외 → 재시도 후 DLQ로 이동
        paymentService.charge(job);
    }
}
```

### Kafka 이벤트 분배 예제

`build.gradle`:
```groovy
implementation 'org.springframework.kafka:spring-kafka'
```

발행:
```java
@Service
class OrderEventPublisher {
    private final KafkaTemplate<String, OrderEvent> kafka;
    void publish(OrderEvent e) {
        kafka.send("order-events", String.valueOf(e.orderId()), e);
    }
}
```

서로 다른 컨슈머 그룹이 같은 토픽을 독립적으로 소비:
```java
@KafkaListener(topics = "order-events", groupId = "search-indexer")
public void index(OrderEvent e) { searchIndex.upsert(e); }

@KafkaListener(topics = "order-events", groupId = "recommendation")
public void recommend(OrderEvent e) { recommender.update(e); }
```

같은 메시지를 두 컨슈머 그룹이 각자 자기 offset으로 읽는다는 점이 RabbitMQ와의 결정적 차이다.

## 운영 시 자주 부딪히는 함정

### Kafka 쪽
- **Consumer rebalance 폭풍**: `session.timeout.ms`, `max.poll.interval.ms` 튜닝 안 하면 처리 시간이 긴 잡에서 리밸런스 반복
- **파티션 수 변경의 비가역성**: 늘리는 건 가능, 줄이는 건 사실상 불가
- **순서 보장 ↔ 처리량 트레이드오프**: 키 분포가 한쪽으로 쏠리면 특정 파티션 lag만 폭증
- **at-least-once 기본**: exactly-once를 원한다면 transactional producer + isolation_level=read_committed 조합을 이해해야 함

### RabbitMQ 쪽
- **메모리 high watermark**: 큐가 길어지면 메모리 압박으로 publish가 차단됨(Flow Control)
- **mirror queue 성능 저하**: 노드 수 늘릴수록 쓰기 비용이 비례 증가 → quorum queue로 이전 권장
- **prefetch count**: 기본값(혹은 무제한)으로 두면 한 컨슈머가 큐를 통째로 끌어가 처리 분산이 안 됨. `basicQos` 설정 필수
- **DLQ 운영**: dead letter가 다시 원본 큐로 돌아오는 무한 루프 패턴 주의

## 면접 답변 프레임

면접에서 "RabbitMQ vs Kafka 어떻게 선택하시나요?" 같은 질문이 나오면 다음 순서로 풀어가는 게 깔끔하다.

1. **모델 차이부터 짚는다.** "RabbitMQ는 smart broker, Kafka는 분산 커밋 로그입니다. 메시지가 ACK 즉시 사라지는지, 디스크에 retention 기간 동안 남는지가 본질적 차이입니다."
2. **워크로드로 매핑한다.** "단건 작업이고 처리 후 잊어도 되면 RabbitMQ, 같은 이벤트를 여러 시스템이 다른 시점에 다시 읽어야 하면 Kafka를 우선 검토합니다."
3. **트레이드오프를 인정한다.** "Kafka는 처리량과 재처리에 강하지만 단건 격리와 복잡한 라우팅이 약하고, RabbitMQ는 라우팅과 단건 ack 제어에 강하지만 처리량 천장이 낮습니다."
4. **실제 경험을 1-2개 붙인다.** "이전 프로젝트에서 결제 후속 처리는 RabbitMQ로 단건 신뢰성을 챙기고, 같은 결제 이벤트를 Kafka로도 발행해 분석 시스템과 검색 색인이 각자 소비하도록 분리한 적이 있습니다."
5. **운영 관점도 언급한다.** "Kafka는 파티션 설계와 리밸런스 튜닝이 운영 포인트, RabbitMQ는 prefetch와 DLQ 정책이 운영 포인트입니다."

이 5단계는 어떤 변형 질문(왜 Kafka를 골랐나요 / RabbitMQ로 가능한가요 / 둘 다 쓴다면)에도 그대로 적용 가능하다.

## 자주 받는 변형 질문 대비

- **"이벤트 순서 보장 어떻게 하나요?"** → Kafka는 같은 key가 같은 partition으로 가도록 보장하고, 그 partition은 단일 컨슈머가 순차 처리. RabbitMQ는 단일 큐 + 단일 컨슈머 + prefetch=1 조합이 정공법.
- **"중복 메시지 어떻게 막나요?"** → 둘 다 기본은 at-least-once. 컨슈머에서 idempotent 처리(요청 ID 기반 중복 제거 테이블)가 정석. Kafka는 transactional producer + EOS 옵션도 있지만 처리량 비용 있음.
- **"메시지가 유실되면 어떻게 추적하나요?"** → 발행자에서 publish confirm/acks=all로 도착 보장, 처리 단계별 trace id 로깅, DLQ/DLT 적재량 모니터링, lag/queue depth 알람.
- **"배치 vs 스트림 어디에 어떤 걸 쓰나요?"** → 즉시성·단건 워크로드는 RabbitMQ, 대용량 연속 스트림과 후속 분석은 Kafka.

## 실전 체크리스트

- [ ] 이 워크로드는 같은 메시지를 한 번 처리하고 끝인가, 여러 곳에서 다시 읽어야 하는가?
- [ ] 시간당 메시지 수와 평균 메시지 크기를 추정했는가?
- [ ] 순서 보장 단위가 무엇인가(전체, 사용자, 주문, 없음)?
- [ ] 실패 시 단건만 격리할 것인가, 스트림 전체를 멈출 것인가?
- [ ] 컨슈머가 며칠 후에 합류하면 과거 데이터가 필요한가?
- [ ] 라우팅 규칙이 단순한가, exchange 패턴이 필요한가?
- [ ] 운영팀이 Kafka 파티션 / 리밸런스 튜닝에 익숙한가, RabbitMQ 큐 운영에 익숙한가?
- [ ] DLQ / DLT 정책이 정의되어 있는가? 무한 루프 방지 장치가 있는가?
- [ ] 컨슈머 처리는 idempotent한가?
- [ ] 모니터링 지표(lag, queue depth, publish confirm 비율, redelivery 비율)를 수집하고 있는가?

이 체크리스트를 한 줄씩 답해보면 RabbitMQ냐 Kafka냐의 선택은 자연스럽게 좁혀진다. 도구를 먼저 정하고 워크로드를 끼워 맞추는 순서를 뒤집으면 거의 항상 운영 단계에서 비용을 치른다.
