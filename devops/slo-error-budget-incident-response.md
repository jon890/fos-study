# [초안] 시니어 백엔드를 위한 SLO와 Error Budget 기반 장애 대응

## 왜 이 주제가 중요한가

시니어 백엔드 면접에서 운영 역량을 묻는 질문은 대개 이렇게 시작한다.

- “장애를 어떻게 탐지하고 대응하나요?”
- “알람이 너무 많이 울리면 어떻게 줄이나요?”
- “p99 latency가 튀는데 CPU는 정상입니다. 어디를 보겠습니까?” (p50/p95/p99 가 익숙하지 않으면 [Observability 입문](../architecture/observability-basics.md) 의 "Latency 백분위수" 섹션 참고)
- “신규 기능 출시 속도와 안정성은 어떻게 조율하나요?”

이 질문의 핵심은 도구 이름이 아니다. Prometheus, Grafana, Datadog, OpenTelemetry를 안다는 것보다 중요한 것은 **사용자 영향 기준으로 신뢰성을 정의하고, 그 신뢰성 예산 안에서 출시와 장애 대응을 의사결정하는 능력**이다.

SLO(Service Level Objective)와 Error Budget은 이 의사결정의 언어다. “장애가 났다/안 났다”가 아니라 “이번 달 사용자에게 허용한 실패 예산을 얼마나 태웠는가”로 대화하게 만든다.

이 문서는 시니어 백엔드 관점에서 다음을 정리한다.

- SLI / SLO / SLA 차이
- Error Budget 계산과 운영 의사결정
- Multi-window multi-burn-rate 알림
- Alert fatigue를 줄이는 알림 설계
- Incident Commander 중심의 장애 대응 타임라인
- Postmortem 작성과 재발 방지
- Spring / Micrometer / Prometheus 기반 구현 예시
- 커머스 / 주문 / 결제 도메인 면접 답변 프레임

관련 문서인 [Observability 입문](../architecture/observability-basics.md), [Resilience 패턴](../architecture/resilience-patterns.md), [커머스/F&B 채널 장애 첫 5분](./commerce-observability-first-five-minutes.md)은 “무엇을 볼 것인가”와 “어떻게 격리할 것인가”에 가깝다. 이 문서는 한 단계 위에서 **어떤 기준으로 알리고, 멈추고, 재개할 것인가**를 다룬다.

## SLI / SLO / SLA

### SLI: Service Level Indicator

SLI는 서비스 수준을 나타내는 측정 지표다. “사용자 입장에서 좋은 요청인가?”를 수치로 표현한다.

대표 SLI:

- Availability: 성공 요청 비율
- Latency: 일정 시간 이하로 끝난 요청 비율
- Correctness: 정확한 결과를 반환한 비율
- Freshness: 데이터가 일정 시간 이내에 갱신된 비율
- Durability: 손실 없이 저장된 데이터 비율

커머스 주문 API 예시:

```text
SLI = 정상 주문 생성 요청 수 / 전체 주문 생성 요청 수
정상 주문 생성 = HTTP 2xx 이면서 body.status = SUCCESS 이고 주문번호가 생성됨
```

주의할 점은 HTTP 상태 코드만 보면 안 된다는 것이다. 결제 PG는 `200 OK`로 응답하면서 body 안에 `status=FAIL`을 담는 경우가 많다. 사용자는 결제 실패를 경험했는데 서버 메트릭상 2xx로 집계되면 SLI가 거짓말을 한다.

### SLO: Service Level Objective

SLO는 SLI에 대한 목표치다.

```text
주문 생성 API의 월간 availability SLO는 99.9%다.
결제 승인 API의 99% 요청은 1초 이내에 완료되어야 한다.
상품 상세 API의 95% 요청은 300ms 이내에 응답해야 한다.
```

SLO는 “100%”가 아니다. 100%는 현실적으로 불가능하고, 그 목표를 세우면 팀은 아무것도 출시하지 못한다. 시니어 엔지니어는 “어느 정도의 실패가 비즈니스적으로 허용 가능한가”를 제품·운영·인프라 팀과 합의해야 한다.

### SLA: Service Level Agreement

SLA는 외부 고객과 맺은 계약이다. 보통 위반 시 보상이나 패널티가 있다.

- SLI: 실제 측정 지표
- SLO: 내부 목표
- SLA: 외부 계약

일반적으로 SLA는 SLO보다 느슨하게 잡는다. 예를 들어 내부 SLO는 99.95%, 외부 SLA는 99.9%로 둔다. 내부 목표를 더 엄격하게 잡아야 외부 계약 위반 전에 대응할 여유가 생긴다.

## 좋은 SLO의 조건

좋은 SLO는 다음 조건을 만족한다.

1. **사용자 경험과 직접 연결된다.** CPU 80%는 사용자가 느끼는 경험이 아니다. 주문 실패율 1%는 사용자 경험이다.
2. **측정 가능하다.** 로그 grep이 아니라 metric query로 계산되어야 한다.
3. **행동을 유도한다.** SLO를 위반하면 출시 중단, 롤백, 리소스 증설, 장애 대응 같은 결정으로 이어져야 한다.
4. **도메인별로 다르다.** 주문/결제와 추천/리뷰는 같은 SLO를 가지면 안 된다.
5. **너무 많지 않다.** 서비스 하나에 핵심 SLO 2~4개면 충분하다.

커머스 백엔드 예시:

| 도메인 | 권장 SLO | 이유 |
|---|---|---|
| 주문 생성 | availability 99.9% | 매출과 직접 연결 |
| 결제 승인 | success rate 99.5% + p99 2s | 외부 PG 영향 포함 |
| 상품 조회 | p95 300ms | UX 영향 큼, 실패는 캐시 fallback 가능 |
| 추천 영역 | availability 99% | 실패 시 숨김/대체 가능 |
| 포인트 적립 | eventual completion 99.9% within 10m | 동기 성공보다 최종 정합성이 중요 |

시니어 레벨 답변에서는 “모든 API에 99.99%를 붙입니다”가 아니라, **핵심 경로와 보조 경로의 SLO를 다르게 둔다**고 말해야 한다.

## Error Budget

Error Budget은 SLO가 허용하는 실패 예산이다.

월간 availability SLO가 99.9%라면 허용 실패율은 0.1%다.

```text
월 요청 수 = 100,000,000
SLO = 99.9%
허용 실패율 = 0.1%
Error budget = 100,000 실패 요청
```

시간 기준으로 보면 30일 월 기준 허용 다운타임은 약 43.2분이다.

```text
30일 = 43,200분
0.1% = 43.2분
```

99.99%라면 월 4.32분밖에 없다. 이 차이는 운영 난이도를 완전히 바꾼다.

### Error Budget이 중요한 이유

Error Budget은 출시와 안정성의 균형 장치다.

- 예산이 충분히 남아 있다 → 기능 출시와 실험을 계속한다.
- 예산이 빠르게 소진 중이다 → 위험한 배포를 줄이고 안정화에 집중한다.
- 예산을 다 썼다 → 신규 기능 freeze, 장애 재발 방지 작업 우선.

이 방식의 장점은 “안정성이 중요하니 배포하지 말자” 같은 추상적인 논쟁을 줄인다는 것이다. 예산이라는 숫자가 있으므로 제품팀과 엔지니어링팀이 같은 언어로 이야기할 수 있다.

## Burn Rate

Burn rate는 error budget을 얼마나 빠르게 태우고 있는지를 나타낸다.

```text
burn rate = 현재 오류율 / 허용 오류율
```

SLO 99.9%의 허용 오류율은 0.1%다. 현재 오류율이 1%라면:

```text
burn rate = 1% / 0.1% = 10x
```

즉 지금 속도가 계속되면 예산을 정상 속도의 10배로 태운다는 뜻이다.

### 왜 단순 오류율 알림보다 burn rate가 좋은가

단순히 “5xx > 1% for 5m”로 알리면 서비스마다 기준이 달라진다. 99.99% SLO 서비스에서 0.2% 오류는 심각하지만, 99% SLO 서비스에서는 상대적으로 덜 심각할 수 있다.

Burn rate는 SLO 기준으로 정규화하므로 서비스별 중요도를 반영한다.

## Multi-window Multi-burn-rate 알림

Google SRE에서 널리 쓰는 방식이다. 하나의 긴 창과 하나의 짧은 창을 같이 본다.

목표:

- 큰 장애는 빠르게 깨운다.
- 짧은 스파이크로 사람을 깨우지 않는다.
- 천천히 예산을 태우는 장애도 놓치지 않는다.

예시: 30일 SLO 기준

| 종류 | 짧은 창 | 긴 창 | burn rate | 의미 |
|---|---:|---:|---:|---|
| Fast burn page | 5m | 1h | 14.4x | 2% budget을 1시간에 태움 |
| Slow burn ticket | 30m | 6h | 6x | 5% budget을 6시간에 태움 |
| Very slow burn | 2h | 1d | 3x | 장기 품질 저하 |

Prometheus 예시:

```yaml
groups:
  - name: order-slo-alerts
    rules:
      - alert: OrderApiFastBurn
        expr: |
          (
            sum(rate(http_server_requests_seconds_count{service="order",outcome="SERVER_ERROR"}[5m]))
            /
            sum(rate(http_server_requests_seconds_count{service="order"}[5m]))
          ) > (14.4 * 0.001)
          and
          (
            sum(rate(http_server_requests_seconds_count{service="order",outcome="SERVER_ERROR"}[1h]))
            /
            sum(rate(http_server_requests_seconds_count{service="order"}[1h]))
          ) > (14.4 * 0.001)
        for: 2m
        labels:
          severity: page
          service: order
        annotations:
          summary: "order-service is burning error budget fast"
          runbook_url: "https://wiki/runbooks/order-slo"
          dashboard: "https://grafana/d/order-slo"
```

여기서 `0.001`은 99.9% SLO의 허용 오류율이다.

핵심은 5분과 1시간을 동시에 만족해야 한다는 점이다. 1~2분짜리 단발 스파이크는 무시하고, 실제 지속 장애만 page한다.

## Latency SLO 설계

Availability만으로는 부족하다. 사용자가 10초 기다린 뒤 성공해도 성공 요청으로 집계되면 SLO는 좋아 보인다.

Latency SLO는 보통 “좋은 요청”의 조건에 latency를 포함한다.

```text
Good event = status success AND duration <= 1s
Total event = all requests
SLI = good event / total event
```

Micrometer histogram bucket으로 계산할 수 있다.

```promql
sum(rate(http_server_requests_seconds_bucket{service="order",le="1.0",status!~"5.."}[5m]))
/
sum(rate(http_server_requests_seconds_count{service="order"}[5m]))
```

주의할 점:

- 평균 latency는 쓰지 않는다.
- p99만 단독으로 알리면 트래픽 적은 시간대에 흔들릴 수 있다.
- 가능하면 “1초 이하 성공 요청 비율”처럼 SLO-friendly한 형태로 바꾼다.

## Spring / Micrometer 구현 포인트

Spring Boot Actuator와 Micrometer를 쓰면 기본 HTTP metric이 나온다.

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,prometheus,info
  metrics:
    tags:
      service: order-service
      env: prod
    distribution:
      percentiles-histogram:
        http.server.requests: true
      slo:
        http.server.requests: 100ms,300ms,500ms,1s,2s,5s
```

도메인 성공/실패는 별도 counter로 노출한다.

```java
@Service
@RequiredArgsConstructor
public class OrderMetrics {
    private final MeterRegistry registry;

    public void orderAttempt(String channel) {
        registry.counter("order_attempt_total", "channel", channel).increment();
    }

    public void orderSuccess(String channel) {
        registry.counter("order_success_total", "channel", channel).increment();
    }

    public void orderFailure(String channel, String reason) {
        registry.counter("order_failure_total",
            "channel", channel,
            "reason", normalize(reason)
        ).increment();
    }

    private String normalize(String reason) {
        return switch (reason) {
            case "PG_TIMEOUT", "PG_DECLINED", "OUT_OF_STOCK", "IDEMPOTENCY_CONFLICT" -> reason;
            default -> "OTHER";
        };
    }
}
```

`reason`에 원본 exception message를 넣으면 cardinality가 폭발한다. 반드시 작은 enum으로 정규화한다.

## Alert Fatigue 줄이기

알림이 많다는 것은 운영이 성숙하다는 뜻이 아니다. 오히려 위험 신호다. 사람이 무시하기 시작하면 진짜 장애도 묻힌다.

좋은 알림의 조건:

1. 사용자 영향이 있다.
2. 사람이 지금 행동해야 한다.
3. 어느 대시보드를 볼지 알려준다.
4. 어느 runbook을 따라야 하는지 알려준다.
5. 중복 알림이 묶인다.

나쁜 알림:

- CPU 80% for 1m
- heap usage 70%
- 특정 로그 문자열 발생
- 단일 인스턴스 5xx 1건
- 원인을 모르는 모든 exception page

좋은 알림:

- 주문 생성 SLO fast burn
- 결제 승인 실패율 PG별 fast burn
- 전체 사용자 여정 latency SLO 위반
- DB connection pool saturation이 주문 실패율 상승과 동시에 발생

원칙은 **cause보다 symptom을 먼저 page한다**는 것이다. CPU, GC, DB connection은 대시보드와 ticket으로 충분한 경우가 많다. 사용자가 실패를 경험할 때 page한다.

## 장애 대응 타임라인

시니어 백엔드는 장애 상황에서 “내가 코드를 고치는 사람”을 넘어 **상황을 구조화하는 사람**이어야 한다.

### 0~5분: 인지와 범위 확정

- 알림 확인
- SLO 대시보드 확인
- 영향 서비스 / 엔드포인트 / 사용자군 확인
- Incident Commander 지정
- 공개 대응 채널 생성

이 단계의 목표는 원인 확정이 아니다. **영향 범위와 심각도 확정**이다.

### 5~15분: 완화 결정

- 롤백할지
- 트래픽을 줄일지
- circuit breaker를 열지
- feature flag를 끌지
- 특정 외부 의존성을 우회할지
- autoscaling / pool 증설을 할지

완화는 근본 원인 분석보다 우선한다. 사용자가 계속 실패하고 있다면 먼저 출혈을 멈춘다.

### 15~30분: 원인 좁히기

- 배포 이벤트 확인
- trace / log로 실패 경로 확인
- dependency dashboard 확인
- saturation 지표 확인
- 재시도 폭주 여부 확인

### 종료 후: 회고와 재발 방지

- timeline 복원
- detection gap 확인
- mitigation gap 확인
- runbook 갱신
- alert rule 조정
- 테스트 추가

## Incident Commander 역할

장애가 커질수록 가장 위험한 것은 모두가 각자 디버깅하는 상황이다. Incident Commander(IC)는 직접 코드를 고치는 사람이 아니라 흐름을 잡는 사람이다.

IC의 역할:

- 현재 severity 선언
- 담당자 분리: 조사 / 완화 / 커뮤니케이션 / 기록
- 10~15분 단위 상태 업데이트
- 의사결정 기록
- “지금은 원인 분석보다 완화 우선” 같은 우선순위 결정

시니어 면접에서 강한 답변은 “제가 로그를 봤습니다”가 아니라 “저는 IC 역할로 범위를 나누고, 한 명은 PG 상태를, 한 명은 직전 배포를, 한 명은 DB saturation을 보게 했습니다”에 가깝다.

## Postmortem

Postmortem은 책임자 찾기가 아니다. 시스템이 왜 그 실패를 허용했는지 찾는 문서다.

최소 템플릿:

```markdown
# Incident: 주문 생성 실패율 상승

## Summary
- 2026-05-15 12:03~12:28 KST 동안 주문 생성 실패율이 0.2%에서 3.8%로 상승.
- 약 1,240건 주문 생성 실패.
- PG A사의 응답 지연과 우리 retry 정책이 결합되어 order-service thread pool saturation 발생.

## Impact
- 영향 사용자 수:
- 실패 주문 수:
- 매출 영향 추정:
- SLA/SLO 영향:

## Timeline
- 12:03 SLO fast burn alert fired
- 12:05 IC 지정, incident channel 생성
- 12:08 PG A latency p99 상승 확인
- 12:12 PG A circuit breaker threshold 수동 조정
- 12:18 retry maxAttempts 3 -> 1 임시 변경
- 12:28 주문 실패율 정상화

## Root Cause
- PG A 응답 지연
- order-service의 PG retry가 짧은 시간에 집중되어 thread pool saturation 유발

## What went well
- SLO fast burn alert가 2분 내 발화
- PG별 dependency dashboard로 범위 빠르게 축소

## What went poorly
- retry storm 여부를 바로 볼 수 있는 대시보드가 없었음
- runbook에 circuit 수동 open 절차가 누락됨

## Action Items
- [ ] PG별 retry rate dashboard 추가
- [ ] circuit breaker 수동 open runbook 작성
- [ ] 결제 retry budget 도입
- [ ] 부하 테스트에 PG 2s 지연 시나리오 추가
```

좋은 postmortem은 action item이 코드만이 아니라 **알림 / 플레이북 / 테스트 / 설계**로 나뉜다.

## 커머스 / 주문 / 결제 SLO 예시

### 주문 생성 API

```text
SLI: 성공적으로 주문번호가 생성된 요청 비율
Good: HTTP 2xx AND body.status=SUCCESS AND orderId exists
SLO: 99.9% monthly
Page: 14.4x burn over 5m + 1h
Ticket: 6x burn over 30m + 6h
```

### 결제 승인

```text
SLI: 결제 승인 요청 중 최종 성공 또는 명확한 사용자 실패로 분류된 비율
Good: 승인 성공 OR 사용자의 잔액 부족/카드 거절처럼 시스템 문제가 아닌 실패
Bad: PG_TIMEOUT, PG_5XX, UNKNOWN, 내부 처리 실패
SLO: 99.5% monthly
```

결제는 “실패”의 의미가 까다롭다. 카드 한도 초과는 시스템 장애가 아니다. PG timeout은 시스템 장애다. 이 구분을 metric label에 반영해야 SLO가 정확해진다.

### 상품 조회

```text
SLI: 300ms 이하로 정상 응답한 상품 상세 요청 비율
SLO: 99% over 7d
Fallback: cache stale response 허용
```

상품 조회는 캐시 fallback이 가능하므로 주문/결제와 같은 SLO를 요구하지 않아도 된다.

## 면접 답변 프레임

질문: “장애를 어떻게 탐지하고 대응하시나요?”

답변 구조:

1. “먼저 서비스별 SLO를 사용자 영향 기준으로 둡니다. 주문은 성공 주문 생성 비율, 결제는 PG timeout과 내부 실패율, 조회는 latency 기준을 둡니다.”
2. “알림은 단순 5xx가 아니라 error budget burn rate로 겁니다. 5분/1시간 fast burn을 동시에 만족할 때 page해서 단발 스파이크를 줄입니다.”
3. “장애가 발생하면 IC를 세우고 0~5분 안에 영향 범위와 severity를 확정합니다. 원인 분석보다 완화를 먼저 봅니다.”
4. “완화는 롤백, circuit breaker open, retry 축소, feature flag off, 트래픽 우회 중 하나를 선택합니다.”
5. “종료 후 postmortem에서 detection gap, mitigation gap, prevention gap을 나누고 알림·runbook·테스트를 갱신합니다.”

좋은 한 문장:

> “저는 장애 대응을 개별 로그 분석 문제가 아니라 SLO와 error budget을 기준으로 한 의사결정 문제로 봅니다. 사용자가 실패를 경험하는 지표로 알리고, burn rate로 긴급도를 정하고, 장애 중에는 원인 규명보다 완화를 먼저 선택합니다.”

## 흔한 실수

- HTTP 2xx만 성공으로 보고 body 실패를 놓침
- 모든 API에 같은 SLO를 붙임
- 평균 latency로 알림을 검
- CPU / memory 같은 cause alert로 사람을 깨움
- SLO는 정의했지만 error budget 정책이 없음
- 알림에 runbook / dashboard 링크가 없음
- 장애 중 IC 없이 모두가 같은 로그를 봄
- postmortem action item이 “주의하자”로 끝남
- retry storm이 error budget을 태우는 구조를 못 봄
- low traffic 시간대에 비율 알림만 써서 false positive 발생

## 체크리스트

- [ ] 핵심 API별 SLI가 사용자 성공 기준으로 정의되어 있다.
- [ ] SLO가 도메인 중요도에 따라 다르게 설정되어 있다.
- [ ] Error budget 잔여율을 대시보드에서 볼 수 있다.
- [ ] Fast burn / slow burn 알림이 분리되어 있다.
- [ ] Page 알림은 사용자 영향 symptom 중심이다.
- [ ] 알림 payload에 runbook과 dashboard 링크가 있다.
- [ ] 주문/결제 도메인 실패는 HTTP status가 아니라 business status까지 본다.
- [ ] Metric label cardinality가 통제되어 있다.
- [ ] 장애 시 Incident Commander를 지정하는 절차가 있다.
- [ ] Postmortem 템플릿이 timeline, impact, root cause, action item을 강제한다.
- [ ] Action item이 알림 / 플레이북 / 코드 / 테스트로 나뉜다.
- [ ] Retry, circuit breaker, fallback 지표가 SLO 대시보드와 연결되어 있다.

---

## 관련 문서

- [Observability 입문](../architecture/observability-basics.md)
- [Resilience 패턴 실전 가이드](../architecture/resilience-patterns.md)
- [커머스/F&B 채널 장애 첫 5분과 관측성 기본기](./commerce-observability-first-five-minutes.md)
- [F&B / e-Commerce 운영 장애 대응과 모니터링](./fnb-ecommerce-operations-monitoring-interview.md)
