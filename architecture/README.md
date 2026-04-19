# Architecture

언어·기술 독립적인 설계 개념 학습 기록. 패턴·분산·대규모 트래픽·관찰성·회복성·무중단 전환을 묶었다.

## 설계 패턴

- [디자인 패턴 허브](./design-pattern.md) — 패턴 전체 빠른 포인터
- [전략 패턴 (Strategy Pattern)](./strategy-pattern.md) — 런타임에 알고리즘 교체
- [템플릿 메서드 패턴](./template-method-pattern.md) — 처리 골격 고정, 변형은 서브클래스

## 분산 시스템

- [분산 아키텍처 스터디 팩](./distributed-architecture-study-pack.md) — 서비스 경계, 장애 전파, 일관성, 메시징, 멱등성
- [분산 트랜잭션](./distributed-transaction.md) — 2PC와 대안
- [분산 트랜잭션과 Outbox 패턴](./distributed-transaction-outbox-pattern.md) — 왜 2PC를 피하고 어떻게 대신할 것인가
- [MSA 서비스 간 통신](./msa-service-communication.md) — Redis Cache-Aside × Kafka 이벤트 하이브리드

## 대규모 트래픽

- [시스템 설계 입문](./system-design-basics.md) — 시니어 백엔드를 위한 시스템 설계 스터디 팩
- [대규모 커머스 트래픽 처리 패턴](./high-traffic-commerce-patterns.md) — 1,600만 고객 / 올영세일 대비 설계
- [무중단 마이그레이션](./zero-downtime-migration.md) — Feature Flag + Shadow Mode 실전

## 운영 품질

- [Resilience 패턴](./resilience-patterns.md) — Timeout, Retry, Circuit Breaker, Bulkhead, Backpressure
- [Observability 입문](./observability-basics.md) — 장애 탐지와 대응

## API / 도메인 설계

- [API 설계 실전 스터디 팩](./api-design.md) — REST, 멱등성, 페이지네이션, 버전 전략
- [DDD와 도메인 모델링](./ddd-domain-modeling.md) — 전술/전략 패턴 실전 가이드

## 캐시

- [캐시 설계 전략 총정리](./cache-strategies.md) — Look-Aside, Read/Write-Through, Cache Stampede
