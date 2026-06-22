# Java

Java 언어·JVM·생태계 학습 기록. 하위 폴더는 주제별 세부 정리.

## 하위 주제

- [Spring](./spring/README.md) — IoC, 트랜잭션, AOP, JPA, HTTP 클라이언트
- [Spring Batch](./spring-batch/README.md) — 배치 파이프라인, [AsyncItemProcessor](spring-batch/async-item-processor.md), StepScope
- [JDBC](./jdbc/README.md) — 커서, 배치 처리
- [Java Testing](./testing/README.md) — Mockito, JVM 테스트 환경, CI 테스트 안정화
- [OpenTelemetry](./opentelemetry/README.md) — 분산 추적
- [바이트코드 조작과 리플렉션](./더_자바_코드를_조작하는_다양한_방법/README.md)

## JVM과 성능

- [JVM 튜닝 실전](./jvm-tuning.md) — 메모리 구조, GC, Virtual Threads, 프로파일링
- [Virtual Thread와 Project Loom](./virtual-thread.md) — 경량 스레드 개요

## 동시성

- [Concurrency 폴더](./concurrency/README.md) — 락 비교, 동기화 전략 모음
- [Java StampedLock](./stamped-lock.md) — 읽기 폭주에도 쓰기가 밀리지 않는 락
- [Java 동시성 락 정리 — 커머스 메뉴/프로모션 정책 캐시 갱신 관점](./java-concurrency-locks-commerce-cache.md) (초안)

## 관찰성 / 로깅

- [MDC (Mapped Diagnostic Context)](./MDC.md) — 로그에 컨텍스트 태깅
- [OpenTelemetry](./opentelemetry/README.md) — 분산 추적 인덱스
- [Java의 로깅 환경](./logging.md) — SLF4J, Logback
