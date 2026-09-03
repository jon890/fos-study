# 분산 시스템

서비스 간 통신, 데이터 정합성, 메시지 처리와 장애 격리를 다루는 문서다.

## 데이터와 정합성

- [분산 트랜잭션](./distributed-transaction.md) — 2PC의 제약과 대안
- [분산 트랜잭션과 Outbox 패턴](./distributed-transaction-outbox-pattern.md) — Outbox를 선택하는 이유
- [Outbox와 Inbox 패턴](./outbox-inbox-pattern.md) — 발행 원자성과 멱등 수신
- [Event Sourcing과 CQRS](./event-sourcing-cqrs.md) — 이벤트 기록과 읽기·쓰기 모델 분리
- [캐시 설계 전략](./cache-strategies.md) — 캐시 읽기·쓰기 전략과 Stampede 대응

## 통신과 처리

- [MSA 서비스 간 통신](./msa-service-communication.md) — 동기 호출과 비동기 메시징 조합
- [Spring Batch와 Event-Driven](./spring-batch-vs-event-driven.md) — 처리 모델 선택 기준
- [Resilience 패턴](./resilience-patterns.md) — Timeout, Retry, Circuit Breaker와 Bulkhead
