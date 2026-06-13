# [초안] Spring Kafka 컨슈머 오프셋 커밋과 트랜잭션 정렬: AckMode, manual ack, 멱등 처리

## 1. 이 글에서 답하는 질문

이 문서의 결론을 먼저 적으면 하나다.

> "DB 커밋"과 "Kafka 오프셋 커밋"은 원자적으로 묶을 수 없다. 그래서 순서를 `DB 커밋 → 오프셋 커밋`으로 고정해 **at-least-once**로 만들고, 중복 재처리는 **컨슈머 멱등성**으로 흡수한다.

이 한 줄을 코드와 실패 시나리오로 풀어내는 것이 목표다. 다루는 질문은 다음과 같다.

- 리스너가 정상 종료하면 오프셋은 언제, 어떤 AckMode 규칙으로 커밋되는가
- `@Transactional` DB 커밋과 오프셋 커밋의 순서는 무엇이고, 그 순서가 왜 중요한가
- manual ack는 왜 위험한가
- 재전송된 중복 메시지를 unique 제약 위반으로 어떻게 흡수하는가
- Kafka 트랜잭션과 DB 트랜잭션을 묶으려는 시도의 원자성 한계는 어디인가
- `processed_event` 테이블 기반 idempotent consumer는 어떻게 구성하는가

이 글은 메시지를 **소비하는 쪽**(consumer listener)의 오프셋 커밋 메커니즘에 집중한다.
DB 커밋 이후 Kafka로 **발행하는 쪽**의 정렬(afterCommit / Outbox)은 별도 문서에서 다룬다 (마지막 관련 문서 참고).

## 2. 먼저 잡아야 할 사실: 오프셋 커밋은 "어디까지 읽었다"는 약속

Kafka 컨슈머는 메시지를 지우지 않는다. 대신 "이 파티션에서 N번 오프셋까지 처리했다"를 브로커(`__consumer_offsets` 토픽)에 커밋한다.
컨슈머가 죽고 다시 떠서 리밸런싱되면, **마지막으로 커밋된 오프셋 다음**부터 다시 읽는다.

여기서 정합성의 모든 논점이 갈린다.

- 처리가 끝나기 **전에** 오프셋을 커밋하면 → 처리 도중 죽었을 때 그 메시지는 다시 안 온다 → **유실**(at-most-once).
- 처리가 끝난 **후에** 오프셋을 커밋하면 → 커밋 직전에 죽으면 같은 메시지가 다시 온다 → **중복**(at-least-once).

실무 기본값은 후자다. 유실보다 중복이 다루기 쉽기 때문이다. 중복은 멱등성으로 흡수할 수 있지만, 유실된 메시지는 되살릴 방법이 없다.

## 3. Spring Kafka의 AckMode — 오프셋을 언제 커밋할지의 정책

Spring Kafka 컨테이너는 `enable.auto.commit=false`로 두고 **컨테이너가 직접** 오프셋을 커밋한다.
"언제 커밋하느냐"를 결정하는 것이 `ContainerProperties.AckMode`다.

| AckMode | 커밋 시점 | 비고 |
|---|---|---|
| `RECORD` | 레코드 1건 리스너 처리가 끝날 때마다 | 가장 안전, 처리량은 낮음 |
| `BATCH` (기본값) | `poll()`로 가져온 배치 전체 처리가 끝난 뒤 | Spring Kafka 컨테이너 기본값 |
| `TIME` | `ackTime` 경과 후 | 시간 기반 |
| `COUNT` | `ackCount` 건 처리 후 | 건수 기반 |
| `COUNT_TIME` | `ackCount` 또는 `ackTime` 중 먼저 도달 | 혼합 |
| `MANUAL` | `Acknowledgment.acknowledge()` 호출분을 모았다가 다음 `poll()` 때 커밋 | 큐잉 후 배치 커밋 |
| `MANUAL_IMMEDIATE` | `acknowledge()` 호출 즉시 컨슈머 스레드에서 커밋 | 즉시 커밋 |

핵심 오해 하나를 먼저 정리한다.

- **AckMode는 "리스너가 성공적으로 끝났을 때 오프셋을 어느 단위로 커밋할지"를 정하는 것이지, 처리 성공 여부를 바꾸지 않는다.**
- 리스너가 예외를 던지면 AckMode와 무관하게 그 레코드의 오프셋은 커밋되지 않고, 에러 핸들러 정책(재시도 / DLQ / seek)에 따라 다시 처리된다.

`BATCH`가 기본값이라는 점이 실무에서 자주 발을 건다.
배치 중 3번째 레코드에서 죽으면, 같은 배치의 1\~2번째가 이미 DB에 반영됐더라도 오프셋은 배치 단위로만 커밋되므로 **배치 전체가 재전송**된다. 그래서 멱등성이 없으면 1\~2번째가 중복 처리된다.

## 4. `@Transactional` DB 커밋과 오프셋 커밋의 순서

가장 흔한 구성은 리스너 메서드에 DB 트랜잭션만 거는 형태다.

```java
@Component
@RequiredArgsConstructor
public class OrderEventConsumer {

    private final OrderRepository orderRepository;

    @KafkaListener(topics = "order-created", groupId = "order-projection")
    @Transactional // DataSourceTransactionManager (DB 전용)
    public void consume(OrderCreatedEvent event) {
        orderRepository.save(OrderProjection.from(event));
        // 메서드가 정상 반환되는 시점에 DB 커밋
    }
}
```

이때 실제 실행 순서는 다음과 같다.

1. 컨테이너가 `poll()`로 레코드를 가져와 리스너를 호출한다.
2. `@Transactional` 프록시가 DB 트랜잭션을 연다.
3. 비즈니스 로직(`save`)이 실행된다.
4. 리스너 메서드가 정상 반환되면 프록시 경계에서 **DB 커밋**이 일어난다.
5. 제어가 컨테이너로 돌아오고, 컨테이너가 AckMode 규칙에 따라 **Kafka 오프셋을 커밋**한다.

즉 `DB 커밋(4) → 오프셋 커밋(5)` 순서가 보장된다. 이 순서가 정합성의 핵심이다.

- DB 커밋이 먼저이므로, 오프셋 커밋 직전에 죽으면 오프셋이 안 올라간 상태로 재시작한다.
- 재시작하면 같은 메시지를 다시 읽고, DB에는 이미 반영돼 있으므로 **중복 처리**가 된다 → at-least-once.
- 이 중복을 멱등성으로 막으면 결과적으로 "정확히 한 번 처리된 것과 같은 효과"를 얻는다.

반대 순서(오프셋 먼저, DB 나중)는 절대 피해야 한다. `enable.auto.commit=true`로 두거나 처리 시작 시점에 ack를 호출하면 이 함정에 빠진다. 오프셋만 올라가고 DB가 롤백되면 메시지가 영영 사라진다.

## 5. manual ack는 왜 위험한가

`AckMode.MANUAL` / `MANUAL_IMMEDIATE`를 쓰면 리스너 시그니처에 `Acknowledgment`를 받아 직접 커밋을 호출한다.

```java
@KafkaListener(topics = "order-created", groupId = "order-projection")
public void consume(OrderCreatedEvent event, Acknowledgment ack) {
    orderRepository.save(OrderProjection.from(event));
    ack.acknowledge(); // 이 호출 위치가 위험의 원천
}
```

제어권을 손에 쥐는 만큼 실수 지점도 늘어난다.

### 5.1 ack를 먼저 호출하고 뒤에서 실패

```java
public void consume(OrderCreatedEvent event, Acknowledgment ack) {
    ack.acknowledge();              // ⚠️ 오프셋 먼저 커밋
    orderRepository.save(...);      // 여기서 예외 → 오프셋은 이미 올라감 → 메시지 유실
}
```

`MANUAL_IMMEDIATE`에서 특히 치명적이다. ack가 즉시 커밋되므로, 그 뒤 실패한 작업은 재전송으로 복구되지 않는다.
ack는 **모든 부수 효과(특히 DB 커밋)가 끝난 뒤** 호출해야 한다.

### 5.2 ack를 빠뜨림

조건 분기에서 어떤 경로는 ack를 호출하고 어떤 경로는 빠뜨리면, 그 파티션의 오프셋이 영영 안 올라간다.
다음 리밸런싱 때 마지막 커밋 지점부터 다시 읽으므로 **같은 구간을 무한 재처리**하거나 lag가 계속 쌓인다.

### 5.3 다른 스레드에서 ack

`@Async`나 별도 executor로 처리를 넘긴 뒤 그 안에서 ack를 호출하면, 컨테이너 스레드는 이미 다음 `poll()`로 넘어가 있다.
오프셋 순서가 꼬이고, 컨테이너의 단일 스레드 모델이 깨진다. ack는 컨슈머 스레드(리스너 본문) 안에서 호출한다.

### 5.4 manual ack를 쓸 가치가 있을 때

대부분은 `RECORD` 또는 `BATCH`로 충분하다. manual ack는 다음처럼 **커밋 단위를 비즈니스 단위로 직접 통제**해야 할 때만 쓴다.

- 배치 안에서 일부만 처리하고 나머지는 의도적으로 나중에 처리(seek)할 때
- 외부 시스템 응답을 받은 뒤에만 커밋해야 하는 비동기 파이프라인

이 경우에도 "성공 부수 효과 완료 → ack" 순서를 기계적으로 지킨다.

## 6. Kafka 트랜잭션과 DB 트랜잭션의 원자성 한계

"그럼 DB 커밋과 오프셋 커밋을 하나의 트랜잭션으로 묶으면 되지 않나?"가 자연스러운 다음 질문이다.
결론은 **저렴하게는 못 묶는다**이다.

### 6.1 Kafka 트랜잭션이 보장하는 범위

Kafka 트랜잭션(`producer.beginTransaction()` / `sendOffsetsToTransaction()` / `commitTransaction()`)은
**consume-process-produce** 패턴에서 "입력 오프셋 커밋 + 출력 메시지 발행"을 원자적으로 묶는다.
즉 Kafka 안에서 읽고-처리하고-다시 Kafka로 쓰는 경로는 exactly-once가 된다.

```java
// 개념 예시: 입력 오프셋과 출력 발행을 하나의 Kafka 트랜잭션으로
producer.beginTransaction();
producer.send(outputRecord);
producer.sendOffsetsToTransaction(offsets, consumerGroupMetadata);
producer.commitTransaction();
```

문제는 **DB가 Kafka와 다른 자원**이라는 점이다. Kafka 트랜잭션은 DB INSERT를 함께 커밋하지 못한다.

### 6.2 두 자원을 묶으려는 시도와 그 한계

Spring Kafka에는 과거 `ChainedKafkaTransactionManager`로 DB 트랜잭션 매니저와 Kafka 트랜잭션 매니저를 연결하는 방법이 있었다.
하지만 이건 진짜 2단계 커밋(2PC)이 아니라 **커밋을 순서대로 호출하는 동기화**일 뿐이다.

- 안쪽(예: DB)이 먼저 커밋되고, 그 다음 바깥(Kafka)이 커밋된다.
- DB 커밋은 성공했는데 그 직후 Kafka 커밋이 실패하면 — 두 자원의 상태가 어긋난다.
- 즉 **커밋과 커밋 사이의 실패 창**은 여전히 남는다. 원자성이 아니다.

`ChainedKafkaTransactionManager`는 Spring Kafka 2.7부터 deprecated이며 이후 제거 방향이다.
새 코드에서 되살리지 말고, 두 자원의 비원자성을 **설계로 인정**하는 쪽으로 간다.

### 6.3 그래서 현실적인 선택지

진짜 분산 트랜잭션(XA/2PC)은 운영 비용과 성능 부담이 커서 대부분 피한다. 대신 둘 중 하나를 단일 진실원으로 택한다.

- **DB를 진실원으로** → Outbox 패턴. 비즈니스 데이터와 발행할 메시지를 같은 DB 트랜잭션에 INSERT하고, 별도 워커가 Kafka로 발행. (발행 측 정렬)
- **Kafka를 진실원으로** → idempotent consumer. at-least-once로 받고, DB 쪽에서 중복을 흡수. (소비 측 정렬, 이 글의 주제)

## 7. idempotent consumer — `processed_event` 테이블 패턴

소비 측 중복 흡수의 표준은 "이 이벤트를 이미 처리했는가"를 DB unique 제약으로 판정하는 것이다.

### 7.1 스키마

```sql
CREATE TABLE processed_event (
    event_id   VARCHAR(64) NOT NULL,
    consumer   VARCHAR(64) NOT NULL,   -- 같은 이벤트를 여러 컨슈머가 처리하면 그룹별로 구분
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (event_id, consumer)
) ENGINE=InnoDB;
```

- `event_id`는 메시지에 실린 고유 키다. 주문번호나 발행 측이 심은 UUID처럼 **재전송돼도 같은 값**이어야 한다. Kafka의 `offset`은 재전송 시 같지만 토픽/파티션 재구성에 취약하므로 비즈니스 레벨 ID를 쓰는 편이 안전하다.
- `consumer` 컬럼으로 컨슈머 그룹별 처리 여부를 분리한다. 같은 이벤트를 projection용과 알림용이 각자 한 번씩 처리해야 하기 때문이다.

### 7.2 핵심 — dedup INSERT와 비즈니스 로직을 같은 트랜잭션에

```java
@KafkaListener(topics = "order-created", groupId = "order-projection")
@Transactional
public void consume(OrderCreatedEvent event) {
    try {
        processedEventRepository.saveAndFlush(
            new ProcessedEvent(event.eventId(), "order-projection"));
    } catch (DataIntegrityViolationException e) {
        // unique 제약 위반 = 이미 처리한 이벤트 → 비즈니스 로직 건너뜀
        log.info("중복 이벤트 스킵: {}", event.eventId());
        return;
    }
    // 여기까지 왔다는 건 이 이벤트를 처음 본다는 뜻
    orderRepository.save(OrderProjection.from(event));
}
```

`processed_event` INSERT와 `OrderProjection` 저장이 **하나의 DB 트랜잭션**이라, 둘 다 커밋되거나 둘 다 롤백된다.
재전송된 중복은 INSERT 단계에서 unique 위반으로 걸러지고, 비즈니스 로직은 실행되지 않는다.

### 7.3 unique violation 처리에서 자주 틀리는 지점

unique 제약 위반을 catch할 때 주의할 함정이 둘 있다.

- **트랜잭션 오염**: 일부 DB(특히 PostgreSQL)는 제약 위반이 발생하면 현재 트랜잭션을 abort 상태로 만든다. 위반을 catch한 뒤 같은 트랜잭션에서 다른 쿼리를 이어가면 실패한다. 그래서 dedup INSERT는 **트랜잭션의 가장 앞**에 두고, 위반이면 곧장 `return`해 트랜잭션을 깨끗하게 종료시킨다.
- **`saveAndFlush`로 즉시 반영**: JPA에서 그냥 `save`만 하면 flush가 커밋 시점까지 지연돼 위반을 그 자리에서 못 잡는다. `saveAndFlush`로 INSERT를 즉시 DB에 보내 위반을 리스너 본문에서 catch한다.

DB 종류에 따라 `INSERT ... ON CONFLICT DO NOTHING`(PostgreSQL)이나 `INSERT IGNORE`(MySQL)로 처리한 뒤
영향받은 행 수(0이면 중복)로 분기하는 방식도 깔끔하다. 트랜잭션 오염 문제를 피할 수 있어 선호되기도 한다.

### 7.4 Redis 1차 필터(선택)

매번 DB를 때리는 비용이 부담이면, DB 트랜잭션 진입 전에 Redis `SETNX`로 1차 필터링한 뒤 DB unique 제약을 최종 방어선으로 둔다.
Redis는 캐시일 뿐이라 정합성의 최종 책임은 DB 제약에 있어야 한다.

## 8. 전체 그림 — at-least-once + 멱등으로 만드는 effectively-once

지금까지를 한 흐름으로 잇는다.

1. 컨테이너가 메시지를 가져와 리스너 호출.
2. 리스너는 `@Transactional` 안에서 `processed_event` INSERT(dedup) + 비즈니스 로직을 묶어 실행.
3. 메서드 반환 시점에 **DB 커밋**.
4. 컨테이너가 그 뒤 **오프셋 커밋**.
5. 3과 4 사이에서 죽으면 메시지 재전송 → 2의 dedup INSERT가 unique 위반으로 걸러냄 → 비즈니스 로직 미실행.

이 구조에서 정확히 한 번 "전달"은 보장하지 못해도, **정확히 한 번 "처리"한 것과 같은 효과**(effectively-once)를 얻는다.
이것이 실무에서 Kafka 정합성을 다루는 표준 답이다 — exactly-once delivery를 좇기보다 at-least-once + 멱등 설계로 간다.

## 9. 면접 답변 프레임

**Q. 리스너가 정상 종료하면 오프셋은 언제 커밋되나요?**

> Spring Kafka는 `enable.auto.commit=false`로 두고 컨테이너가 직접 커밋합니다. AckMode 기본값이 `BATCH`라 한 `poll()` 배치를 다 처리한 뒤 커밋되고, `RECORD`로 두면 레코드마다 커밋됩니다. 중요한 건 리스너가 예외 없이 반환된 뒤에 커밋된다는 점이고, 그래서 DB 작업이 함께 있으면 DB 커밋이 오프셋 커밋보다 먼저 일어납니다.

**Q. DB 커밋과 오프셋 커밋 순서가 왜 중요한가요?**

> `DB 커밋 → 오프셋 커밋` 순서라야 at-least-once가 됩니다. 둘 사이에서 죽으면 오프셋이 안 올라가 메시지가 재전송되고, DB에는 이미 반영됐으니 중복 처리가 됩니다. 반대 순서면 오프셋만 올라가고 DB가 롤백돼 메시지를 잃습니다. 유실보다 중복이 다루기 쉬우니 전자를 택하고 중복은 멱등성으로 흡수합니다.

**Q. Kafka 트랜잭션으로 DB까지 원자적으로 묶을 수 있나요?**

> Kafka 트랜잭션은 consume-process-produce, 즉 Kafka 안에서 읽고 다시 Kafka로 쓰는 경로의 오프셋 커밋과 발행을 묶어줍니다. 하지만 DB는 다른 자원이라 함께 못 묶습니다. `ChainedKafkaTransactionManager`로 순서대로 커밋할 수는 있었지만 2PC가 아니라 커밋 사이 실패 창이 남고, 지금은 deprecated입니다. 그래서 DB를 진실원으로 하는 Outbox나, Kafka를 진실원으로 하는 idempotent consumer 중 하나로 설계합니다.

**Q. 중복 메시지는 어떻게 막나요?**

> `processed_event` 테이블에 이벤트 고유 ID를 unique 제약으로 두고, dedup INSERT와 비즈니스 로직을 같은 DB 트랜잭션에 넣습니다. 재전송된 중복은 INSERT에서 unique 위반으로 걸러지고 비즈니스 로직은 건너뜁니다. 위반 catch 시 트랜잭션 오염을 피하려고 dedup INSERT를 트랜잭션 맨 앞에 두거나, `ON CONFLICT DO NOTHING` 같은 구문으로 처리합니다.

## 10. 체크리스트

- [ ] 리스너에 DB 작업이 있을 때 `DB 커밋 → 오프셋 커밋` 순서가 보장되는가 (`enable.auto.commit=false` 확인)
- [ ] AckMode가 의도와 맞는가 (기본 `BATCH`의 배치 단위 재전송 영향을 이해했는가)
- [ ] manual ack를 쓴다면 모든 부수 효과 완료 후에만 `acknowledge()`를 호출하는가
- [ ] 분기 경로마다 ack가 빠짐없이 호출되는가 (오프셋 정체로 무한 재처리되지 않는가)
- [ ] ack를 컨슈머 스레드 안에서만 호출하는가 (`@Async`/별도 스레드에서 호출하지 않는가)
- [ ] 컨슈머가 멱등한가 (`processed_event` 또는 동등한 dedup이 있는가)
- [ ] dedup 키가 재전송에도 동일한 비즈니스 레벨 ID인가 (offset 의존이 아닌가)
- [ ] unique 위반 catch가 트랜잭션을 오염시키지 않는가 (dedup INSERT를 앞단에 두거나 ON CONFLICT 사용)
- [ ] dedup INSERT와 비즈니스 로직이 같은 DB 트랜잭션에 묶여 있는가
- [ ] Kafka 트랜잭션과 DB 트랜잭션을 진짜 원자적으로 묶었다고 오해하고 있지 않은가

---

## 관련 문서

- [메시지 전달 신뢰성](./message-delivery-semantics.md) — at-most/least/exactly-once 의미와 컨슈머 멱등 전략
- [Kafka 데이터 정합성 설계](./data-consistency.md) — 멱등 프로듀서, exactly-once, min.insync.replicas
- [Kafka 실전 설계](./kafka-design.md) — 파티션/컨슈머 그룹/재시도 트레이드오프
- [Spring 트랜잭션 전파·격리수준·AFTER_COMMIT 실전](../java/spring/transaction-propagation-isolation-after-commit.md) — DB 커밋 이후 Kafka로 **발행하는 쪽**의 정렬
- [TransactionSynchronization 실전](../java/spring/transaction-synchronization.md) — afterCommit 훅 커스터마이징
- [분산 트랜잭션과 Outbox 패턴](../architecture/distributed-transaction-outbox-pattern.md) — DB를 진실원으로 하는 발행 원자성

## 참고 공식 문서

- [Spring Kafka — Message Listener Containers](https://docs.spring.io/spring-kafka/reference/kafka/receiving-messages/message-listener-container.html)
- [Spring Kafka — Transactions](https://docs.spring.io/spring-kafka/reference/kafka/transactions.html)
