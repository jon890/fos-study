# Observability — 면접 답변 프레임

운영 중 장애 탐지·추적·재발 방지를 묻는 시니어 백엔드 질문에 어떻게 답할지 정리한 자료. 도구 의존성을 줄이고 **개념**(SLO·RED·trace correlation·deploy diff) 위주로 풀되, 실전 사례로 Datadog 스택을 인용하는 구성이다.

도구 자체에 대한 학습 자료는 별도로 둔다.

- Datadog 운영 가이드 → [devops/observability/datadog-apm-observability.md](../devops/observability/datadog-apm-observability.md)
- 일반 관측성 입문 → [architecture/observability-basics.md](../architecture/observability-basics.md)
- Prometheus + remote_write → [devops/observability/prometheus-k8s-remote-write.md](../devops/observability/prometheus-k8s-remote-write.md)

---

## Q. 운영 중 장애를 어떻게 탐지하고 추적하시나요?

자주 나오는 질문이다. 답변은 다음 4축으로 구조화한다.

### 1) 탐지 — SLO 기반 alert

서비스별로 RED(Rate, Errors, Duration)를 SLI로 정의하고, p99 latency와 error rate threshold가 SLO를 위반하면 monitor가 호출한다. 트래픽 계절성이 있는 지표는 단일 threshold 대신 **anomaly monitor**(베이스라인 대비 이상치 검출)를 쓴다.

### 2) 추적 — APM flame graph가 기본 진입점

Service map에서 어느 서비스 edge가 빨간지 먼저 본다. 문제 서비스의 slow trace 샘플을 열어 flame graph에서 bottleneck span을 찾는다. DB span이면 실행된 쿼리와 connection pool wait time을 span 태그로 확인하고, downstream HTTP call 이면 해당 서비스 trace로 점프한다.

### 3) Trace ↔ Log 상관관계

trace_id 가 SLF4J MDC에 자동 주입되도록 구성한다. Tracer agent가 `dd.trace_id` (또는 OpenTelemetry 의 `trace_id`) 를 MDC 에 박아주고, Logback JSON encoder 가 필드로 출력한다. 그러면 APM trace → Logs 탭으로 바로 이동해 해당 요청의 로그만 뽑아 볼 수 있다.

도구 비교 한 줄로 곁들일 거리:

> 이전에는 OpenTelemetry + Jaeger + ELK 로 trace_id 를 직접 관리했는데, MDC context propagation 이슈와 도구 분리로 디버깅 시간이 길어졌다. Datadog 같은 통합 플랫폼은 auto-instrumentation 범위(JPA, Kafka, Redis 등)가 넓고 한 UI 에서 metric/log/trace 를 넘나들 수 있어 MTTR 에 차이가 난다.

### 4) Regression — Deploy diff

배포 관련 regression 은 **Unified Service Tagging** 의 version 태그로 diff 한다. 배포 전후 버전의 p99 를 중첩해 보고, 특정 엔드포인트에서 regression 이 있으면 Git deploy diff 로 연결해 커밋을 본다. **Feature flag 로 gradual rollout 을 했다면 그쪽을 먼저 off 시키는 게 1차 mitigation** 이다.

---

## 곁다리 질문에 대비할 거리

- **"메트릭 카디널리티 폭발은 어떻게 다루나요?"** — `user_id` / `order_id` 같은 고유 식별자는 메트릭 태그가 아니라 로그/trace 의 필드로 보낸다. Custom metric cardinality 는 주기적으로 모니터링한다.
- **"샘플링 전략은?"** — Tail-based sampling 으로 에러/slow trace 는 100% 보존, 정상은 저율 샘플링한다. 정상 trace 도 일부는 보존해야 baseline 이 흔들리지 않는다.
- **"alert false positive 가 많으면?"** — Composite monitor 로 조건을 결합하거나, anomaly monitor 의 민감도 파라미터를 조정한다. 알람을 끄는 게 아니라 **신호를 정제** 한다.
- **"postmortem 은 어떤 흐름으로 정리하시나요?"** — Notebook 템플릿 사용 (timeline / impact / RCA / action item). 알람 → Service Map → Error Trace → Deploy Diff → Mitigation 순으로 trace 를 따라가며 시간 축을 박제한다.
