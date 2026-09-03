# Observability

관찰성(Observability) 스택 학습 기록 — metrics·logs·traces 세 축의 운영 경험을 한 곳에 모은다.

## Metrics

- [K8s 위 Spring Boot 앱 메트릭 수집](./prometheus-k8s-remote-write.md) — Prometheus Agent와 remote_write 구성

## Tracing / APM

- [Datadog APM 실전 투입 가이드](./datadog-apm-observability.md) — Java/Spring 서비스 관측성 스택 구축

## 관련

- [Observability 입문](../../architecture/observability-basics.md) — 개념과 장애 대응
- [OCR 비즈니스 오류 관측](../../task/ai-service-team/ocr-business-error-monitoring.md) — HTTP 200 응답 안의 오류를 지표와 주간 분류로 연결한 업무
- [로그에 traceId 남기기](../../java/MDC.md) — MDC 부터 OpenTelemetry 까지
