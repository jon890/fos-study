# DevOps

인프라·배포·모니터링 학습 기록.

## 하위 주제

- [Docker](./docker/README.md) — 컨테이너, HealthCheck, 프로세스 격리
- [Kubernetes](./k8s/README.md) — Pod, Service, Ingress, Helm, Argo CD
- [Observability](./observability/README.md) — Prometheus, Micrometer, Datadog APM

## 네트워크 / 운영

- [Envoy Proxy](./envoy-proxy.md) — L7 프록시, 서비스 메시 기반
- [Graceful Shutdown](./graceful-shutdown.md) — 무중단 배포를 위한 종료 처리
- [종료 신호가 애플리케이션까지 도달하는 과정](./termination-signal-process-layers.md) — 컨테이너와 프로세스 계층별 신호 전달

## 운영 플레이북

- [커머스 관측성 — 첫 5분 운영 플레이북](./commerce-observability-first-five-minutes.md)
- [운영 데이터 정합성 장애 대응](./data-integrity-incident-runbook.md) — 결제 취소 누락·중복 적재의 탐지, 보정, 재발 방지
- [SLO·에러 버짓·장애 대응](./slo-error-budget-incident-response.md) — 신뢰성 운영의 공통 언어
- [F&B 이커머스 운영·모니터링](./fnb-ecommerce-operations-monitoring.md)
