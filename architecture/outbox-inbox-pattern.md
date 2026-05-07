# [초안] Outbox / Inbox Pattern 심화 — 분산 메시징의 정합성 문제를 DB 트랜잭션으로 풀어내기

## 왜 중요한가

분산 시스템에서 백엔드 엔지니어가 가장 자주 마주하는 함정 중 하나는 "DB 커밋과 메시지 발행이 둘 다 성공해야 한다"는 요구다. 결제 승인이 끝났는데 후속 알림 메시지가 누락되거나, 반대로 DB는 롤백되었는데 메시지는 이미 카프카로 나가 버린 경험은 어느 팀이든 한 번씩 한다. 이 문제는 단순한 "한 번 더 publish 하자"로 해결되지 않는다. 네트워크는 신뢰할 수 없고, 두 개의 서로 다른 자원(DB와 Broker)을 동시에 commit/abort 시키는 분산 트랜잭션은 운영상 거의 쓰이지 않는다.

Outbox/Inbox 패턴은 이 본질적인 문제를 "메시지 발행을 DB 트랜잭션 안으로 끌고 들어온다"는 한 줄로 해결한다. 이름은 두 개지만 사실 한 짝이다. 보내는 쪽은 Outbox로 "내가 보낸 메시지의 출고 장부"를 남기고, 받는 쪽은 Inbox로 "내가 처리한 메시지의 입고 장부"를 남긴다. 이 두 장부를 통해 at-least-once 전달 위에 idempotent consumer를 얹어 effectively-once 시멘틱을 구현하는 것이 목표다.

면접에서 "메시지 누락은 어떻게 막느냐", "consumer가 같은 메시지를 두 번 받으면 어떻게 하느냐", "분산 트랜잭션 안 쓰고 어떻게 정합성 맞추느냐" 같은 질문이 나오면 결국 이 패턴 또는 그 변형으로 수렴한다. 시니어 백엔드 면접에서는 패턴 이름을 외운 수준이 아니라, transaction boundary, polling 전략, ordering, replay, 모니터링, broker별 차이까지 자기 언어로 설명할 수 있는지를 본다.

## 핵심 개념 — Dual Write 문제부터 다시 본다

가장 단순한(그리고 잘못된) 코드는 이렇게 생겼다.

```java
@Transactional
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.from(cmd));
    kafkaTemplate.send("order-events", new OrderPlaced(order.getId()));
}
```

이 한 줄에 분산 시스템의 가장 큰 함정이 숨어 있다. `orderRepository.save`는 DB 트랜잭션에 참여하지만 `kafkaTemplate.send`는 별도 자원이다. 두 자원에 대한 commit 순서에 따라 네 가지 시나리오가 갈라진다.

1. DB commit 성공 + Kafka send 성공 — 정상
2. DB commit 성공 + Kafka send 실패 — 메시지 유실
3. DB commit 실패(롤백) + Kafka send 성공 — 유령 이벤트
4. send 호출은 성공했으나 broker ack 도착 전 process crash — 모름

3번과 4번은 특히 사악하다. consumer 입장에서는 "DB에는 없는 주문에 대한 OrderPlaced 이벤트"를 받게 된다. 이를 막기 위해 Kafka 트랜잭션이나 XA 트랜잭션을 도입하면 broker 의존성, 성능, 운영 복잡도가 모두 폭증한다.

Outbox 패턴의 통찰은 단순하다. **메시지 발행을 "DB에 행을 하나 더 쓰는 일"로 바꾼다.** Order를 저장하는 트랜잭션 안에서 같은 DB의 `outbox_event` 테이블에 발행할 메시지를 함께 저장한다. 두 INSERT는 같은 로컬 트랜잭션이므로 원자적이다. 그 다음 별도의 publisher 프로세스(또는 CDC)가 `outbox_event`를 읽어 broker로 내보낸다. broker로의 publish는 실패할 수 있지만, outbox 행이 남아 있는 한 재시도하면 된다.

받는 쪽도 대칭이다. 메시지를 받자마자 비즈니스 로직을 실행하면 중복 처리 위험이 있으므로, 같은 트랜잭션 안에서 `inbox_event(message_id)`에 INSERT를 시도하고, unique constraint 위반이면 이미 처리된 메시지로 보고 skip한다. 이 INSERT가 idempotency key 역할을 한다.

## Transaction Boundary — 어디까지가 한 트랜잭션인가

이 패턴을 처음 도입할 때 가장 많이 틀리는 부분이 트랜잭션 경계다. 정확히 다음 두 트랜잭션만 같이 커밋되어야 한다.

- **Producer side**: 비즈니스 상태 변경 + outbox INSERT
- **Consumer side**: inbox INSERT(혹은 처리 마킹) + 비즈니스 상태 변경

반면 다음은 **같은 트랜잭션에 묶이면 안 된다.**

- outbox INSERT와 broker publish — broker는 외부 자원, 트랜잭션 안에서 호출하면 다시 dual write
- inbox INSERT와 ack 전송 — ack는 broker 통신 이후

Spring 코드로 적으면 producer 쪽은 다음과 같이 단순하다.

```java
@Service
@RequiredArgsConstructor
public class OrderService {
    private final OrderRepository orderRepository;
    private final OutboxEventRepository outboxRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public void placeOrder(OrderCommand cmd) {
        Order order = orderRepository.save(Order.from(cmd));

        OutboxEvent event = OutboxEvent.builder()
            .aggregateType("order")
            .aggregateId(order.getId().toString())
            .eventType("OrderPlaced")
            .payload(objectMapper.writeValueAsString(new OrderPlaced(order)))
            .createdAt(Instant.now())
            .build();
        outboxRepository.save(event);
    }
}
```

여기서 의도적으로 `kafkaTemplate.send`를 호출하지 않는다. publish는 별도 워커가 책임진다. 트랜잭션 동기화 콜백(`TransactionSynchronization.afterCommit`) 안에서 직접 publish 하는 변형도 있지만, 프로세스가 afterCommit 직후 죽으면 메시지가 유실되므로 outbox 테이블을 진실의 원천으로 유지하는 편이 안전하다.

## 발행 전략 — Polling Publisher vs Transaction Log Tailing

outbox 행을 broker로 내보내는 방식은 크게 두 갈래다.

**Polling publisher**는 워커가 주기적으로 outbox 테이블을 SELECT하고, 발행 후 처리 상태를 업데이트한다. 단순하고 어떤 DB에서도 동작한다. 동시성 제어가 핵심인데, 여러 워커가 같은 행을 잡지 않게 `SELECT ... FOR UPDATE SKIP LOCKED`(MySQL 8.0+)를 쓴다.

```sql
SELECT id, aggregate_type, aggregate_id, event_type, payload
FROM outbox_event
WHERE published_at IS NULL
ORDER BY id
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

`SKIP LOCKED`가 없던 MySQL 5.7 시절에는 워커마다 shard 컬럼(예: `id % N`)을 두거나, advisory lock을 썼다. MySQL 8 이상이라면 `SKIP LOCKED`가 사실상 표준이다. 발행에 성공하면 같은 트랜잭션에서 `UPDATE outbox_event SET published_at = NOW() WHERE id = ?`로 마킹한다. 마킹한 행은 retention 정책에 따라 일정 기간 뒤 archive 또는 delete한다.

**Transaction log tailing(CDC)**은 Debezium이 대표적이다. DB의 binlog를 읽어 outbox 테이블의 INSERT를 broker로 직접 흘려보낸다. 애플리케이션 코드가 보장해야 할 것은 outbox INSERT뿐이고, polling 워커를 운영하지 않아도 된다는 장점이 있다. 반면 Debezium 자체의 운영 부담, schema 변경 시 connector 재배포, binlog retention 관리 같은 다른 비용이 생긴다. CJ 같은 엔터프라이즈 환경에서는 운영 조직의 친숙도와 SRE 인력에 따라 선택이 갈린다.

면접 답변 톤으로 정리하면 이렇다. "트래픽이 크지 않거나 DBA 협조가 어려우면 polling, 트래픽이 크고 운영팀이 Debezium에 익숙하면 CDC를 우선 검토합니다. 어느 쪽이든 outbox INSERT를 비즈니스 트랜잭션과 같이 커밋한다는 본질은 같습니다."

## Duplicate Handling — Idempotent Consumer와 Inbox 테이블

at-least-once 브로커(Kafka, SQS 모두 기본은 at-least-once)에서는 같은 메시지를 두 번 받는 일이 정상이다. retry, rebalance, ack 유실 등 이유는 다양하다. 따라서 consumer는 **반드시 idempotent**해야 한다.

가장 신뢰성 있는 방법이 inbox 테이블이다.

```sql
CREATE TABLE inbox_event (
    message_id   VARCHAR(64)  NOT NULL PRIMARY KEY,
    consumer     VARCHAR(64)  NOT NULL,
    received_at  DATETIME(6)  NOT NULL,
    PRIMARY KEY (message_id, consumer)
) ENGINE=InnoDB;
```

consumer는 메시지를 받으면 다음 흐름을 한 트랜잭션 안에서 처리한다.

```java
@Transactional
public void handle(OrderPlaced event, String messageId) {
    try {
        inboxRepository.save(new InboxEvent(messageId, "shipping-consumer", Instant.now()));
    } catch (DataIntegrityViolationException e) {
        return;
    }
    shippingService.scheduleShipment(event.orderId());
}
```

unique constraint 위반이 발생하면 이미 처리한 메시지이므로 비즈니스 로직을 건너뛴다. 단, 비즈니스 상태 변경과 inbox INSERT가 **반드시 같은 트랜잭션**이어야 한다. 그렇지 않으면 inbox만 찍히고 비즈니스 상태는 누락되거나, 그 반대가 된다.

비즈니스 자체가 자연스럽게 idempotent한 경우(예: `UPDATE order SET status='SHIPPED' WHERE id=? AND status='PAID'`)에는 inbox 테이블을 생략하기도 한다. 다만 외부 API 호출처럼 부수효과가 있는 경우는 inbox로 명시적으로 막는 편이 안전하다.

## Ordering — 순서가 정말 필요한가부터 묻는다

면접에서 자주 나오는 함정이 "Outbox 쓰면 순서 보장됩니까?"다. 정답은 "**파티션 단위로만 보장한다.**" outbox 테이블을 PK 순으로 polling해도, broker가 멀티 파티션이면 consumer 간 처리 순서는 뒤섞인다.

올바른 접근은 "**어떤 단위로 순서가 필요한가**"를 먼저 정의하는 것이다. 일반적으로 aggregate(예: orderId, userId) 단위면 충분하다. 그러면 broker partition key를 aggregateId로 잡으면 된다.

```java
kafkaTemplate.send("order-events", event.aggregateId(), event.payload());
```

같은 aggregateId의 메시지는 같은 파티션에 들어가고, 한 파티션은 하나의 consumer instance가 처리하므로 자연스럽게 순서가 보존된다. 단, **producer가 outbox에서 꺼낼 때도 같은 aggregate 안에서는 PK 오름차순으로 발행해야 한다.** 멀티 워커가 `SKIP LOCKED`로 잡을 때 같은 aggregate가 두 워커에 분산되면 순서가 깨질 수 있으니, aggregate 단위 hashing으로 워커 간 sharding을 하거나 단일 워커로 운영한다.

전체 글로벌 순서가 정말 필요하다는 요구가 들어오면 보통 요구가 잘못된 경우가 많다. "사용자별 알림 순서가 어긋나면 안 된다" 같은 요구는 user 단위 ordering이면 충분하고, 거기서 얻는 처리량이 글로벌 ordering보다 압도적으로 크다.

## Replay — 운영의 마지막 안전망

outbox를 진실의 원천으로 유지하면, 운영 사고 발생 시 특정 기간의 이벤트를 다시 발행할 수 있다.

```sql
UPDATE outbox_event
SET published_at = NULL
WHERE event_type = 'OrderPlaced'
  AND created_at BETWEEN '2026-04-01 00:00:00' AND '2026-04-01 03:00:00';
```

published_at을 NULL로 되돌리면 polling publisher가 다시 집어 든다. 이때 consumer가 idempotent하지 않으면 재앙이 된다(같은 결제가 두 번 처리되는 식). 그래서 inbox 테이블이 단순한 옵션이 아니라 **replay를 안전하게 하기 위한 전제 조건**이라는 점이 중요하다.

CDC 방식에서는 Kafka의 retention과 consumer offset reset(`--to-datetime`)으로 동일한 효과를 낸다. 어느 쪽이든 "사고 시 재발행할 수 있는가"는 분산 메시징 인프라의 성숙도 지표다.

## Monitoring — 무엇을 보는가

운영 중 outbox/inbox 패턴이 건강한지 보려면 다음 지표가 필요하다.

- **outbox lag**: `MAX(NOW() - created_at) WHERE published_at IS NULL`. 이 값이 늘면 publisher가 broker에 못 따라가고 있다.
- **outbox backlog size**: `COUNT(*) WHERE published_at IS NULL`. 평균 처리량과 비교한다.
- **publish failure rate**: 워커가 broker로 publish 시도 후 실패한 횟수.
- **inbox dedup hit rate**: unique constraint 위반 비율. 0이면 의심해 볼 만하다(중복이 정말 없는지, 아니면 dedup 로직이 안 타는지).
- **consumer lag**: broker 자체 메트릭(Kafka의 consumer group lag, SQS의 ApproximateAgeOfOldestMessage).
- **outbox 테이블 사이즈**: archive/cleanup 정책이 동작하는지 확인. 안 그러면 수억 row까지 쌓인다.

알람은 보통 outbox lag 상한선과 publish failure rate에 건다. lag이 일정 시간 이상 누적되면 publisher 워커 문제이거나 broker 다운이고, publish failure rate가 튀면 broker auth/네트워크/스키마 문제일 가능성이 높다.

## Kafka vs SQS — Broker별 적용 차이

같은 패턴이라도 broker 특성이 달라서 구현 디테일이 갈린다.

**Kafka**

- partition key 기반 ordering이 강점이라 outbox와 잘 맞는다.
- consumer offset commit 시점과 비즈니스 트랜잭션 commit 시점을 분리해서 관리해야 한다. spring-kafka의 `AckMode.MANUAL_IMMEDIATE` + 비즈니스 트랜잭션 커밋 후 ack가 일반적이다.
- Kafka 자체 트랜잭션(`transactional.id` + EOS)은 Kafka→Kafka 파이프라인에서는 효과적이지만, DB→Kafka에서는 결국 outbox가 더 실용적이다.
- replay 시 offset reset이 강력하다. outbox 재발행 vs offset reset 중 운영 정책을 명확히 정한다.

**SQS**

- 기본 standard queue는 ordering을 보장하지 않는다. 순서가 필요하면 FIFO queue를 쓰는데, 처리량이 300 msg/s 수준으로 제한된다(batching 시 3000).
- visibility timeout이 핵심 개념이다. consumer가 message를 받고 처리 중이면 다른 consumer에게 보이지 않다가, 처리 실패 시 자동으로 다시 큐에 돌아온다.
- DLQ(dead letter queue)를 설정해서 N회 실패한 메시지를 분리한다. inbox 패턴과 DLQ는 보완 관계다 — inbox는 중복 방어, DLQ는 독성 메시지(poison pill) 격리.
- standard queue에서는 중복이 더 흔하므로 inbox 테이블의 가치가 더 크다.

면접에서 "Kafka를 왜 골랐냐" 또는 "SQS는 왜 안 됐냐"를 물어보면 ordering, throughput, 운영 친숙도, AWS lock-in, 재처리 정책의 차이로 정리하면 자연스럽다.

## Bad vs Improved 예제

**나쁜 예: 트랜잭션 안에서 broker에 직접 publish**

```java
@Transactional
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.from(cmd));
    kafkaTemplate.send("order-events", new OrderPlaced(order.getId())).get();
}
```

문제는 두 가지다. 첫째, `.get()`이 트랜잭션을 broker 응답까지 잡고 있어 DB 커넥션을 길게 점유한다. 둘째, send 성공 후 commit이 실패하면 유령 이벤트가 나간다.

**개선: outbox 테이블에 INSERT만 하고 publish는 별도 워커**

```java
@Transactional
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.from(cmd));
    outboxRepository.save(OutboxEvent.from(order));
}
```

별도 워커가 `SKIP LOCKED`로 polling하며 발행한다. 비즈니스 트랜잭션은 짧고, broker 장애가 비즈니스 트랜잭션을 막지 않는다.

**나쁜 예: consumer에서 ack 먼저, 처리 나중**

```java
@KafkaListener(topics = "order-events")
public void handle(OrderPlaced event, Acknowledgment ack) {
    ack.acknowledge();
    shippingService.scheduleShipment(event.orderId());
}
```

ack 후 process crash 시 메시지는 유실된다.

**개선: 처리 + inbox INSERT 트랜잭션 commit 후 ack**

```java
@KafkaListener(topics = "order-events")
public void handle(OrderPlaced event, @Header("messageId") String messageId, Acknowledgment ack) {
    consumerService.handle(event, messageId);
    ack.acknowledge();
}
```

`consumerService.handle`이 inbox INSERT와 비즈니스 로직을 한 트랜잭션으로 묶고, 그 트랜잭션이 커밋된 다음에 ack를 보낸다. crash 시 broker가 다시 같은 메시지를 보내고, inbox 덕에 중복 처리가 막힌다.

## 로컬 실습 환경

MySQL 8과 Kafka(KRaft 모드)로 가볍게 띄울 수 있다.

```yaml
version: "3.9"
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: outbox_lab
    ports: ["3306:3306"]
    command: --default-authentication-plugin=mysql_native_password
  kafka:
    image: bitnami/kafka:3.6
    ports: ["9092:9092"]
    environment:
      KAFKA_CFG_NODE_ID: "0"
      KAFKA_CFG_PROCESS_ROLES: "controller,broker"
      KAFKA_CFG_LISTENERS: "PLAINTEXT://:9092,CONTROLLER://:9093"
      KAFKA_CFG_ADVERTISED_LISTENERS: "PLAINTEXT://localhost:9092"
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: "0@localhost:9093"
```

스키마 초기화:

```sql
CREATE TABLE outbox_event (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    aggregate_type  VARCHAR(64)  NOT NULL,
    aggregate_id    VARCHAR(64)  NOT NULL,
    event_type      VARCHAR(64)  NOT NULL,
    payload         JSON         NOT NULL,
    created_at      DATETIME(6)  NOT NULL,
    published_at    DATETIME(6)  NULL,
    INDEX idx_unpub (published_at, id)
) ENGINE=InnoDB;

CREATE TABLE inbox_event (
    message_id   VARCHAR(64) NOT NULL,
    consumer     VARCHAR(64) NOT NULL,
    received_at  DATETIME(6) NOT NULL,
    PRIMARY KEY (message_id, consumer)
) ENGINE=InnoDB;
```

실습 시나리오는 다음 순서로 돌려본다.

1. `placeOrder`를 100건 호출하고 outbox에 100건 쌓이는지 확인
2. publisher 워커를 두 개 띄워 `SKIP LOCKED` 분배가 동작하는지 검증
3. 워커 한 쪽을 SIGKILL 하고 잡고 있던 행이 잠시 후 다른 워커로 넘어가는지 확인
4. 같은 메시지를 의도적으로 두 번 produce 해서 consumer inbox dedup이 동작하는지 확인
5. published_at을 NULL로 되돌려 replay 동작 확인
6. broker를 일부러 중단하고 outbox lag 메트릭이 어떻게 움직이는지 확인

## 인터뷰 답변 프레이밍

면접에서는 패턴 정의보다 "왜 이걸 골랐는지, 어떤 trade-off를 받아들였는지"가 더 중요하다. 다음 흐름으로 답하면 자연스럽다.

1. **문제 정의로 연다.** "DB 상태 변경과 메시지 발행을 둘 다 성공시켜야 하는데, 두 자원에 걸친 분산 트랜잭션은 운영 비용이 커서 피하고 싶었습니다."
2. **선택을 명시한다.** "그래서 메시지 발행을 outbox 테이블 INSERT로 바꿔 비즈니스 트랜잭션 안으로 끌고 들어왔고, 별도 워커가 polling하며 broker로 내보냅니다."
3. **consumer 쪽 대칭을 설명한다.** "broker는 at-least-once이므로 consumer는 inbox 테이블로 idempotent하게 만들었습니다. 비즈니스 로직과 inbox INSERT는 같은 트랜잭션입니다."
4. **운영 디테일로 깊이를 보여 준다.** `SKIP LOCKED`, partition key, ack 시점, replay, outbox lag 모니터링 중 한두 개를 짧게 언급한다.
5. **trade-off를 자기 언어로 짚는다.** "polling은 단순하지만 lag이 생기고, CDC는 lag이 작지만 Debezium 운영 부담이 있습니다. 팀 운영 역량과 트래픽을 보고 골랐습니다."

꼬리 질문 예상은 다음 정도다.

- "outbox 테이블이 너무 커지면?" → archive/partitioning, retention 정책, published_at 인덱스 설계.
- "글로벌 순서가 필요하면?" → 진짜 필요한 단위가 무엇인지부터 다시 묻는다. 대체로 aggregate 단위면 충분하다.
- "Kafka 트랜잭션(EOS) 쓰면 outbox 안 써도 되는 거 아니냐?" → DB→Kafka 경계에서는 여전히 dual write 문제가 남는다. EOS는 Kafka→Kafka 파이프라인에 효과적이다.
- "consumer가 처리 중간에 죽으면?" → ack가 트랜잭션 commit 후라면 broker가 재전송하고, inbox로 dedup된다.
- "Debezium 도입 비용이 부담스러우면?" → polling publisher로 시작해서 트래픽이 일정 수준 넘어가면 CDC로 옮긴다.

## 체크리스트

- [ ] 비즈니스 상태 변경과 outbox INSERT가 **같은 트랜잭션**에 묶여 있는가
- [ ] outbox publish는 트랜잭션 **밖**의 별도 워커가 책임지는가
- [ ] 멀티 워커 환경에서 `SELECT ... FOR UPDATE SKIP LOCKED` 또는 동등한 분배 전략이 있는가
- [ ] partition key 선택이 비즈니스 ordering 단위(aggregateId)와 일치하는가
- [ ] consumer가 inbox 테이블 또는 자연 idempotency로 중복 방어를 하는가
- [ ] consumer의 inbox INSERT와 비즈니스 처리가 **같은 트랜잭션**인가
- [ ] broker ack는 비즈니스 트랜잭션 commit **후**에 보내는가
- [ ] outbox lag, backlog size, publish failure rate에 알람이 걸려 있는가
- [ ] outbox 테이블의 archive/retention 정책이 정의되어 있는가
- [ ] replay 시나리오(published_at 리셋 또는 offset reset)를 한 번이라도 운영 환경에서 리허설했는가
- [ ] DLQ 또는 poison pill 격리 정책이 있는가
- [ ] Kafka/SQS 어느 쪽이든 ordering·throughput·재처리 trade-off를 설명할 수 있는가
