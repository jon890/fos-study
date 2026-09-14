---
tags: [study]
---

# Kafka 기본 개념: 토픽, 파티션, 오프셋과 복제

Kafka 글을 여러 편 정리하다 보니 "기본 개념을 한 번 모아서 짚는 문서"가 빠져 있었다. 이 글은 Apache Kafka 4.3을 기준으로 토픽, 파티션, 오프셋과 복제를 입문 수준에서 정리한다. 파티션 키 전략, consumer group rebalance와 메시지 전달 보장 같은 운영·설계 영역은 별도 문서에서 다룬다.

- 파티션 수 결정 / 컨슈머 그룹 / 재시도·DLQ 같은 실전 설계 → [Kafka 실전 설계](./kafka-design.md)
- At-most-once, At-least-once와 Exactly-once → [Kafka 실전 설계](./kafka-design.md)
- 멱등성 프로듀서와 `min.insync.replicas` 정합성 옵션 → [Kafka 실전 설계](./kafka-design.md)

---

## Kafka가 한 줄로 무엇인가

> 파티션 단위로 분산된 **append-only 커밋 로그**를 여러 브로커에 복제해두고, 발행자(Producer)와 구독자(Consumer)가 같은 로그를 다른 속도로 읽고 쓸 수 있게 해주는 분산 시스템.

이 한 줄에 등장하는 단어들이 곧 Kafka 의 기본 개념이다. 하나씩 풀어 본다.

## 토픽 (Topic)

토픽은 메시지가 담기는 **논리적 카테고리** 다. RDBMS 의 테이블과 가장 가깝지만 Kafka 토픽은 항상 다음 두 가지 성질을 갖는다.

1. **다중 구독자**(multi-subscriber): 한 토픽을 여러 컨슈머 그룹이 각자의 속도로 동시에 구독할 수 있다. RDBMS 의 큐 테이블처럼 한 번 읽고 지우는 모델이 아니다.
2. **append-only**: 메시지는 끝에만 추가되고, 한 번 쓰인 메시지는 수정되지 않는다. "지운다"는 개념도 사실은 보존 정책(retention)에 따라 오래된 세그먼트를 통째로 버리는 것이다.

토픽은 그 자체로 데이터를 저장하지 않는다. 실제 저장은 토픽을 구성하는 **파티션** 들에서 일어난다.

## 파티션 (Partition)

파티션은 한 토픽을 분할한 **하나의 append-only 로그**다. 토픽이 8개 파티션으로 구성되어 있다면, 그 토픽으로 발행된 메시지는 어떤 규칙에 따라 8개 로그 중 하나에 들어간다.

파티션을 둔 이유는 두 가지다.

- **수평 확장**: 토픽 하나를 여러 브로커에 나눠 저장할 수 있어야 처리량이 단일 디스크/서버 한계를 넘어선다.
- **병렬 소비**: 한 컨슈머 그룹 안에서 컨슈머 인스턴스가 파티션을 나눠 가져가면 그만큼 병렬로 읽을 수 있다.

여기서 입문자가 가장 자주 헷갈리는 사실 하나가 결정된다.

> **순서 보장은 토픽 단위가 아니라 파티션 단위로만 일어난다.**

같은 키를 가진 메시지가 같은 파티션에 들어가도록 발행 측에서 보장하지 않으면, "주문 생성 → 결제 → 배송" 이벤트가 서로 다른 파티션에 흩어져 컨슈머가 받는 순서가 뒤집힐 수 있다. 파티션 키 설계는 그래서 입문 단계가 아니라 실전 설계의 핵심 주제로 따로 다룬다 ([파티션 키 전략](./kafka-design.md#파티션-키-전략)).

### 세그먼트 (Segment)

파티션은 디스크 위에서 하나의 거대한 파일이 아니다. **세그먼트** 라고 부르는 일정 크기의 파일들로 나뉘어 저장된다. 새 메시지는 항상 가장 최근 세그먼트(active segment) 의 끝에 추가되고, 일정 크기·일정 시간이 지나면 새 세그먼트가 만들어진다.

세그먼트로 쪼개 두는 이유는 **삭제와 인덱싱이 단순해지기** 때문이다. retention 정책에 따라 오래된 메시지를 지울 때 한 메시지씩 삭제하지 않고 통째로 오래된 세그먼트 파일을 unlink 하면 끝이다. 이건 Kafka 가 임의 삭제 / 임의 수정을 지원하지 않는 대신 얻는 단순함이고, append-only 가정이 가능하게 해주는 구조적 근거이기도 하다.

## 오프셋 (Offset)

오프셋은 **한 파티션 안에서 메시지의 위치를 가리키는 정수**다. 파티션 0 의 첫 메시지가 0, 그다음이 1, 그다음이 2 ... 이런 식으로 단조 증가한다. 오프셋은 파티션 내부에서만 의미가 있다. 파티션 0 의 오프셋 100 과 파티션 1 의 오프셋 100 은 완전히 다른 메시지다.

Kafka 가 다른 메시지 큐와 가장 다른 점이 여기서 드러난다.

> **레코드는 소비 여부와 무관하게 보존되고, consumer가 자신의 읽기 위치를 정한다.**

전통적인 작업 큐는 처리 확인에 따라 메시지를 제거할 수 있다.
Kafka는 consumer가 읽었다는 이유로 record를 제거하지 않고 retention policy에 따라 보존한다.
Consumer group은 어디까지 처리했는지를 offset으로 기록하고,
group coordinator는 이 offset을 `__consumer_offsets`라는 internal topic에 commit한다.
그래서 같은 topic을 consumer group A와 B가 각자 다른 속도로 읽을 수 있고,
consumer가 재시작하면 마지막 committed offset부터 이어서 읽을 수 있다.

오프셋 커밋 전략(자동 커밋 vs 수동 커밋, 처리 전 커밋 vs 처리 후 커밋) 은 메시지 전달 보장과 직결된다. 이건 [Kafka 실전 설계 — 오프셋 커밋 전략](./kafka-design.md#오프셋-커밋-전략)에서 자세히 다룬다.

## 브로커와 KRaft 컨트롤러

브로커는 Kafka 데이터 요청을 처리하는 **서버 노드**다. 여러 브로커가 클러스터를 이루고, 토픽의 파티션은 브로커들에 분산되어 저장된다.

Kafka 4.x에서는 KRaft 컨트롤러가 브로커 등록, 토픽과 파티션 배치, 리더 변경 같은 클러스터 메타데이터를 관리한다.
운영 환경에서는 컨트롤러를 보통 홀수로 구성해 과반수 합의를 유지한다.
브로커와 컨트롤러는 한 프로세스에 함께 둘 수도 있지만,
규모가 큰 운영 클러스터에서는 역할을 분리할 수 있다.

브로커 수와 컨트롤러 수는 같은 기준으로 결정하지 않는다.
브로커 수는 데이터 용량, 처리량과 파티션 복제본 배치가 정하고,
컨트롤러 수는 메타데이터 quorum의 장애 허용 범위가 정한다.

## 복제 구성: Leader, Follower와 ISR

여기서부터가 입문에서 가장 중요한 부분이다. **파티션은 가용성을 위해 여러 복제본(replica) 을 가진다.**

### Replication Factor

토픽을 만들 때 정하는 옵션 중 하나가 `replication.factor` 다. 값이 3이면 그 토픽의 모든 파티션은 클러스터 안에 **3개의 복제본** 을 갖는다는 뜻이다. 이 3개는 가능한 한 서로 다른 브로커에 배치된다 (한 브로커에 같은 파티션의 두 복제본이 들어가면 그 브로커가 죽었을 때 가용성이 깨지므로).

> 즉 replication factor는 리더 1개와 팔로워 N-1개의 합이다. 이 값이 총 복제본 수다.

### Leader vs Follower

같은 파티션의 N 개 복제본 중 정확히 하나가 **리더**(leader) 가 된다. 나머지는 **팔로워**(follower) 다. 둘의 역할은 분명히 다르다.

- **리더**: partition write와 복제 순서를 관리한다. Producer는 leader에 record를 보낸다.
- **팔로워**: leader에서 record를 가져와 같은 offset에 추가한다. 기본 consumer fetch는 leader를 사용하지만 rack-aware replica selector를 구성하면 가까운 follower에서 읽을 수도 있다.

각 partition에는 leader가 하나지만 topic의 partition leader를 여러 broker에 분산하면 write traffic도 분산된다.

### ISR (In-Sync Replicas)

리더와 팔로워가 있다고 해도, 모든 팔로워가 항상 리더와 같은 위치까지 따라잡고 있는 건 아니다. 어떤 팔로워는 GC 잠깐, 디스크 잠깐, 네트워크 잠깐 늦으면서 뒤처질 수 있다.

Kafka 는 이걸 다루기 위해 **ISR**(In-Sync Replicas) 이라는 개념을 둔다.

> ISR = 현재 리더의 로그를 충분히 따라잡고 있는 복제본들의 집합. 리더 자기 자신도 ISR 의 멤버다.

"충분히 따라잡고 있다"의 기준에는 `replica.lag.time.max.ms`가 사용된다.
팔로워가 이 시간보다 오래 리더의 log end offset을 따라잡지 못하면 ISR에서 제거될 수 있다.
단순히 fetch 요청만 보냈다고 ISR이 유지되는 것은 아니다.

이 값이 가지는 트레이드오프가 운영에서 가장 자주 부딪히는 지점이다.

- **너무 짧게 잡으면**: 일시적인 GC, 디스크와 네트워크 지연에도 팔로워가 ISR에서 자주 빠질 수 있다.
- **너무 길게 잡으면**: 느린 팔로워를 기다리는 시간이 길어져 `acks=all` 쓰기의 지연이나 실패 감지가 늦어질 수 있다.

기본값을 그대로 사용할지 여부는 복제 지연, 쓰기 지연과 장애 감지 목표를 함께 측정해 결정한다.

### 커밋된 메시지 (Committed Message)

ISR이 왜 중요한지는 high watermark에서 드러난다.
Kafka는 ISR 복제 상태를 바탕으로 복제가 완료된 범위를 계산하고,
일반 consumer fetch는 high watermark를 넘어 아직 복제가 완료되지 않은 레코드를 반환하지 않는다.

여기서 복제 관점의 commit과 Kafka transaction의 commit은 다른 개념이다.
`isolation.level=read_committed`인 consumer는 high watermark 범위 안에서도 완료되지 않았거나 중단된 transaction의 레코드를 제외한다.

### 리더 장애 시 무슨 일이 일어나는가

리더 브로커가 죽으면 컨트롤러는 **ISR 에 남아 있는 복제본 중 하나** 를 새 리더로 선출한다. 핵심은 "ISR 에 남아 있는" 이다. ISR 에서 빠진 팔로워는 데이터가 뒤처져 있을 수 있으므로 정상 모드에서는 후보가 되지 않는다.

이 정책에 따라오는 트레이드오프가 두 가지 있다.

1. **ISR이 모두 중단되면 파티션을 사용할 수 없을 수 있다.** ISR 복구를 기다리면 데이터 보존을 우선할 수 있다. `unclean.leader.election.enable=true`로 ISR 밖의 복제본을 리더 후보로 허용하면 가용성을 높일 수 있지만 데이터가 유실될 수 있다.
2. **`acks=all`과 `min.insync.replicas`는 ISR 정의 위에서 동작한다.** 프로듀서가 `acks=all`로 발행하면 리더는 ISR의 모든 멤버가 메시지를 적용한 뒤에야 응답한다. `min.insync.replicas`는 쓰기를 허용할 최소 ISR 수다. 둘이 같이 쓰여야 의미가 산다. 자세한 옵션 조합은 [Kafka 실전 설계](./kafka-design.md)에서 다룬다.

## 한 장 정리

```
Cluster
  ├── KRaft Controller Quorum (클러스터 메타데이터 합의)
  ├── Broker들 (데이터 요청 처리와 replica 저장)
  └── Topic (논리적 카테고리, append-only, 다중 구독자)
        └── Partition (분할된 로그, 순서 보장의 단위)
              ├── Leader Replica  (write와 복제 순서 관리)
              ├── Follower Replica × (RF-1)  (leader에서 fetch)
              │     └── ISR 멤버십 = leader의 log end offset을 제한 시간 안에 따라잡았는가
              └── Segment (디스크 저장 단위, retention 단위)
                    └── Record
                          └── Offset (partition 내부 위치)
```

이 그림이 머리에 잡히면 그 다음 단계인 파티션 키 설계, 컨슈머 그룹 리밸런싱, 메시지 전달 보장이 자연스럽게 읽힌다. 모두 이 기본 구조 위에서 트레이드오프를 더하는 이야기이기 때문이다.

## 다음 읽을거리

- [Kafka 실전 설계 — 파티션 / 컨슈머 그룹 / 재시도 / 순서 보장](./kafka-design.md)
- [Kafka를 로그로 이해하기](./log-as-unifying-abstraction.md) — 복제, 재처리, 상태와 데이터 통합을 연결하는 원리
- [분산 트랜잭션과 Outbox 패턴](../architecture/distributed-systems/distributed-transaction-outbox-pattern.md) — Kafka 발행 원자성 보장

---

## 참고 자료

- [Apache Kafka 4.3 — Introduction](https://kafka.apache.org/43/getting-started/introduction/)
- [Apache Kafka 4.3 — Design](https://kafka.apache.org/43/design/design/)
- [Apache Kafka 4.3 — KRaft](https://kafka.apache.org/43/operations/kraft/)
