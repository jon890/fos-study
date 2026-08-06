# Architecture

언어·기술 독립적인 설계 개념 학습 기록. 패턴·분산·대규모 트래픽·관찰성·회복성·무중단 전환을 묶었다.

## 설계 패턴

- [디자인 패턴 허브](./design-pattern.md) — 패턴 전체 빠른 포인터
- [전략 패턴 (Strategy Pattern)](./strategy-pattern.md) — 런타임에 알고리즘 교체
- [템플릿 메서드 패턴](./template-method-pattern.md) — 처리 골격 고정, 변형은 서브클래스
- [Decorator & Chain of Responsibility](./decorator-chain-of-responsibility.md) — 행동을 체인으로 조립하는 두 방식

## 분산 시스템

- [분산 트랜잭션](./distributed-transaction.md) — 2PC와 대안
- [분산 트랜잭션과 Outbox 패턴](./distributed-transaction-outbox-pattern.md) — 왜 2PC를 피하고 어떻게 대신할 것인가
- [Outbox / Inbox 패턴](./outbox-inbox-pattern.md) — exactly-once 전송과 멱등 수신
- [MSA 서비스 간 통신](./msa-service-communication.md) — Redis [Cache-Aside](../database/redis/cache-aside.md) × Kafka 이벤트 하이브리드
- [Spring Batch vs Event-Driven](./spring-batch-vs-event-driven.md) — 배치와 이벤트 드리븐의 선택 기준

## 대규모 트래픽

- [대규모 커머스 트래픽 처리 패턴](./high-traffic-commerce-patterns.md) — 대규모 회원 / 메가 프로모션 대비 설계
- [무중단 마이그레이션](./zero-downtime-migration.md) — Feature Flag + Shadow Mode 실전

## 운영 품질

- [Resilience 패턴](./resilience-patterns.md) — Timeout, Retry, Circuit Breaker, Bulkhead, Backpressure
- [Observability 입문](./observability-basics.md) — 장애 탐지와 대응

## API / 도메인 설계

- [API 설계 실전 스터디 팩](./api-design.md) — REST, 멱등성, 페이지네이션, 버전 전략
- [API 버저닝과 하위 호환성](./api-versioning-backward-compatibility.md) — 모바일 호환성, 폐기 수명주기, 계약 검증과 롤백
- [DDD와 도메인 모델링](./ddd-domain-modeling.md) — 전술/전략 패턴 실전 가이드
- [Event Sourcing과 CQRS](./event-sourcing-cqrs.md) — 상태 변화 이력과 읽기·쓰기 모델 분리

## 캐시

- [캐시 설계 전략 총정리](./cache-strategies.md) — Look-Aside, Read/Write-Through, Cache Stampede

## 커머스/F&B 도메인 (초안)

멀티브랜드 F&B 디지털 채널 백엔드 설계 묶음. 인프라 패턴을 커머스·F&B 설계 언어로 적용하는 학습 노트.

- [F&B · e-Commerce 디지털 채널 도메인 한 장 정리](./fnb-ecommerce-domain-overview.md)
- [커머스 도메인 모델링 — 주문·재고·노출](./commerce-domain-modeling-order-inventory-display.md)
- [커머스 주문 상태와 데이터 정합성 기본기](./commerce-order-state-consistency-fundamentals.md)
- [F&B 주문/매장/픽업 상태머신 설계](./fnb-order-store-pickup-state-machine.md)
- [F&B 쿠폰·프로모션·멤버십·포인트 설계](./fnb-coupon-promotion-membership-design.md)
- [F&B 이커머스 결제·환불·정산 운영 가이드](./fnb-payment-refund-settlement-operations.md)
- [쿠폰/프로모션 동시성과 정합성 기본기](./coupon-promotion-concurrency-basics.md)

## 금융 거래 설계 (학습중)

- [금융 거래 상태와 원장 설계](./financial-transaction-state-and-ledger.md) — 거래 상태, 복식 원장, 잔액, 멱등성
- [금융 거래 취소·정정·대사·일마감 운영](./financial-reversal-correction-reconciliation-close.md) — 확정 거래 복구와 장부 불일치 해소

## 아키텍처 전환과 현대화

- [Hexagonal / Clean Architecture를 Spring 백엔드에 적용하기](./hexagonal-clean-architecture-spring.md)
- [레거시 JSP/jQuery 화면과 신규 API가 공존하는 백엔드 운영 전략](./legacy-jsp-jquery-api-coexistence.md)
- [모듈러 모놀리스에서 MSA로 점진 전환](./modular-monolith-to-msa-migration-lab.md) — 경계 검증, Strangler Fig, 데이터 소유권, 롤백 실습
