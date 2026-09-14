# Kafka

Apache Kafka를 자료구조와 기본 용어부터 설계, 애플리케이션 정합성과 운영까지 순서대로 공부하는 학습 경로다.
문서의 버전 의존 설명은 Apache Kafka 4.3을 기준으로 한다.

## 학습 순서

### 기본 구조

1. [Kafka 기본 개념: 토픽, 파티션, 오프셋과 복제](./basic.md)
   토픽, 파티션, 세그먼트, 오프셋, 리더와 ISR을 먼저 익힌다.
2. [Kafka를 로그로 이해하기: 복제, 재처리, 상태와 데이터 통합](./log-as-unifying-abstraction.md)
   로그라는 자료구조에서 복제, 재생, 상태 복원과 대용량 데이터 흐름이 어떻게 이어지는지 이해한다.

### 애플리케이션 설계

3. [Kafka 실전 설계: 파티션 전략, 컨슈머 그룹, 전달 보장, 재시도, 순서 보장 트레이드오프](./kafka-design.md)
   파티션 키와 수, consumer group, 전달 보장, 재시도와 순서 경계를 결정한다.
4. [Spring Kafka 컨슈머 오프셋 커밋과 트랜잭션 정렬: AckMode, manual ack, 멱등 처리](./spring-kafka-listener-offset-commit-transaction.md)
   DB transaction과 offset commit 사이의 실패 구간을 이해하고 멱등한 consumer를 설계한다.

### 운영 심화

5. [Kafka 파티션·리밸런스·컨슈머 지연 운영](./kafka-operations-deepen.md)
   hot partition, consumer lag와 rebalance를 재현하고 원인별 대응을 연습한다.

## 관련

- [분산 트랜잭션과 Outbox 패턴](../architecture/distributed-systems/distributed-transaction-outbox-pattern.md) — Kafka 발행 원자성 보장
- [이벤트 소싱과 CQRS](../architecture/distributed-systems/event-sourcing-cqrs.md) — 이벤트 이력과 읽기 모델 분리
