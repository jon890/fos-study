# Kafka를 사용하여 **데이터 정합성**은 어떻게 유지해야 할까?

- 메시징 시스템에서 '정확히 한 번 (Exactly-once)'을 보장하기 위한 전략들과 설정들을 살펴보자.

## 1. 데이터 유실 방지 : Producer & Broker 설정

데이터 유실은 보통 Producer가 메시지를 보냈으나 Broker에 안전하게 저장되지 않았을 떄 발생한다.

- `acks=all` (또는 -1) : 리더 파티션뿐만 아니라 `min.insync.replicas`에 설정된 모든 복제본이 메시지를 받았는지 확인한다.
- `min.insync.replicas` : 메시지가 성공적으로 기록되었다고 간주하기 위한 **최소 복제본 수**이다.
  - 예: 복제 계수(RF)가 3이고 `min.isr`이 2라면, 리더를 포함해 최소 2개의 브로커에 데이터가 복제되어야 성공으로 판단한다.
  - 주의 : 브로커가 1개만 남으면 `NotEnoughReplicas` 예외가 발생하여 가용성보다는 데이터 안정성을 택하게 된다.
- **Transactional Outbox Pattern**: DB 업데이트와 메시지 발행을 하나의 트랜잭션으로 묶는 패턴
  - 비즈니스 로직과 함께 보낼 메시지를 DB의 `OUTBOX` 테이블에 저장(로컬 트랜잭션)
  - 별도의 Pooling이나 CDC(Debezium 등)을 통해 이 테이블의 내용을 읽어 Kafka로 발행
  - 이를 통해 **DB는 수정됐는데 Kafka 전송은 실패**하는 상황을 방지한다.

## 2. 중복 처리 방지 : 멱등성 및 컨슈머 설계

네트워크 재시도 등으로 인해 발생할 수 있는 중복은 컨슈머 측에서 처리해야 한다.

### 멱등성 프로듀서 (Idempotent Producer)

`enable.idempotence=true` 설정을 통해 프로듀서 자체에서 중복 발송을 막을 수 있다.

- Kafka는 내부적으로 **Producer ID**와 **Sequence Number**를 메시지에 할당하여, 브로커가 이미 받은 시퀀스라면 무시한다.

### 컨슈머에서의 멱등성 (Idempotent Consumer)

비즈니스 로직 차원에서의 처리가 가장 확실하다.

- Unique Key 활용 : 메시지에 고유 ID(예: 주문 번호, 요청 UUID)를 포함하고, 컨슈머는 이를 DB의 Unique 제약 조건이나 Redis의 Set 드으로 체크하여 이미 처리된 건인지 확인한다.
- Upsert 로직 : 단순하게 데이터를 덮어쓰는(Update or Insert) 방식으로 설계하면 여러 번 실행되어도 결과가 동일하다.

## 3. Kafka 옵션 상세 설명 : min.insync.replicas

`min.isr`은 데이터 유실 방지의 핵심이다.

| 옵션명 | 설명 | 권장 설정 |
| --- | --- | ------- |
| `replication.factor`| 파티션의 전체 복제본 개수 | 보통 3으로 설정 |
| `min.insync.replicas` | `acks=all`일 떄 응답을 기다릴 최소 ISR 수 | 보통 2로 설정 |

왜 `min.isr`을 2로 하나요?

- RF=3, min.isr=1 : 브로커 1개만 살아있어도 쓰기가 가능하지만, 그 1개가 깨지면 데이터가 유실된다.
- RF=3, min.isr=2 : 브로커 1개가 장애가 나도 서비스가 지속되며 데이터 안정성도 확보된다.
- RF=3, min.isr=3 : 브로커 1개라도 점검을 위해 내려가면 전체 서비스의 쓰기 작업이 중단된다 (가용성 저하)

## 4. Exactly-once Semantics

Spring Kafka를 사용한다면 `DefaultKafkaProducerFactory`에서 트랜잭션 매니저를 설정하여 **Kafka 트랜잭션을** 사용할 수 있다.

```kotlin
// 예시 : Kafka Transactional 설정
@Transactional
fun process(data: String) {
  // 1. DB 로직 수행
  repository.save(Entity(data))

  // 2. Kafka 메시지 발행
  kafkaTemplate.send("topic", data)
}
```

이 방식은 `producer.beginTransaction()`과 `commitTransaction()`을 사용하여, DB와 Kafka로의 전송이 원자적으로 처리되도록 한다. (다만, 성능 오버헤드가 있으므로 데이터 중요도에 따라 선택해야 한다)