# Observability

관찰성(Observability) 스택 학습 기록 — metrics·logs·traces 세 축의 운영 경험을 한 곳에 모은다.

## Metrics

- [K8s 위 Spring Boot 앱 메트릭 수집](./prometheus-k8s-remote-write.md) — Prometheus Agent + remote_write 구성
- [Spring Boot 비즈니스 에러 카운터](./spring-boot-business-error-counter.md) — Micrometer로 도메인 에러를 메트릭화하는 방법

## Tracing / APM

- [Datadog APM 실전 투입 가이드](./datadog-apm-observability.md) — Java/Spring 서비스 관측성 스택 구축

## 관련

- [Observability 입문](../../architecture/observability-basics.md) — 개념과 장애 대응
- [OpenTelemetry](../../java/opentelemetry/README.md) — Java 분산 추적
