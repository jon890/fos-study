# Java

Java 언어·JVM·생태계 학습 기록. 하위 폴더는 주제별 세부 정리.

## 하위 주제

- [Spring](./spring/README.md) — IoC, 트랜잭션, AOP, JPA, HTTP 클라이언트
- [Spring Batch](./spring-batch/README.md) — 배치 파이프라인, AsyncItemProcessor, StepScope
- [JDBC](./jdbc/README.md) — 커서, 배치 처리
- [OpenTelemetry](./opentelemetry/README.md) — 분산 추적
- [바이트코드 조작과 리플렉션](./더_자바_코드를_조작하는_다양한_방법/README.md)

## JVM과 성능

- [JVM 튜닝 실전](./jvm-tuning.md) — 메모리 구조, GC, Virtual Threads, 프로파일링
- [Virtual Thread와 Project Loom](./virtual-thread.md) — 경량 스레드 개요

## 동시성

- [Java StampedLock](./stamped-lock.md) — 읽기 폭주에도 쓰기가 밀리지 않는 락

## 관찰성 / 로깅

- [MDC (Mapped Diagnostic Context)](./MDC.md) — 로그에 컨텍스트 태깅
- [OpenTelemetry란 무엇인가?](./OPEN_TELEMETRY.md) — 개요
- [Java의 로깅 환경](./logging.md) — SLF4J, Logback
