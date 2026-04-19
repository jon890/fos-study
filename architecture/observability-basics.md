# [초안] Observability 입문: 시니어 백엔드가 장애를 탐지하고 대응하는 방식

## 왜 중요한가

운영 환경의 분산 시스템은 "돌고 있는 것 같은데 느리다", "일부 사용자만 실패한다", "가끔 5xx가 튄다"처럼 **이분법으로 떨어지지 않는 장애**를 끊임없이 만든다. 단순한 헬스체크(Alive/Dead)로는 이 회색 지대를 설명할 수 없다. Observability(관측가능성)는 시스템의 외부 출력(logs, metrics, traces)만 보고 **내부 상태를 추론할 수 있는 성질**을 말한다. Monitoring이 "미리 정의한 질문에 대답"하는 것이라면, Observability는 "예상하지 못한 질문도 할 수 있게" 만드는 것이다.

시니어 백엔드에게 Observability는 곧 **운영 책임**이다. 새벽 3시에 페이저가 울렸을 때, 어떤 서비스가, 어떤 경로에서, 어떤 사용자에게, 얼마나 오래 실패했는지를 10분 이내에 판단하지 못하면 비즈니스 임팩트가 기하급수적으로 커진다. 면접에서 "SLO", "on-call", "p99 latency", "trace ID 전파" 같은 단어가 튀어나오는 이유다. 코드를 잘 짜는 것과 "코드가 프로덕션에서 뭘 하는지 볼 수 있게 만드는 것"은 완전히 다른 스킬이다.

## 세 기둥: Logs, Metrics, Traces

Observability의 표준 모델은 세 가지 신호(signal)다.

**Logs**는 **이산적 이벤트의 시간순 기록**이다. 개별 요청에서 무슨 일이 일어났는지, 어떤 예외가 터졌는지 자세히 알려준다. 강점은 맥락(context)이 풍부하다는 것, 약점은 **집계 비용이 크고 cardinality가 폭발**하기 쉽다는 것이다. "어제 오후 2시부터 3시 사이에 결제 실패가 몇 건이었나?"를 로그 grep으로 대답하려 하면 무너진다.

**Metrics**는 **시계열 수치 집계**다. 초당 요청 수, 에러율, 지연시간 분포 같은 값을 정해진 주기로 샘플링해서 저장한다. 강점은 **저장/질의 비용이 싸고 알림 걸기 쉽다**는 것, 약점은 **개별 이벤트의 상세 맥락을 잃는다**는 것이다. "p99가 2초로 튀었다"는 알지만 "누가 왜 느렸는지"는 모른다.

**Traces**는 **하나의 요청이 분산 시스템을 가로지르는 경로**를 기록한다. Trace ID 하나로 API Gateway → Auth → Order → Payment → Notification 서비스까지 이어지는 span 트리를 본다. 강점은 **서비스 경계를 넘어가는 병목을 찾는다**는 것, 약점은 **전량 수집 비용**이 크고 sampling이 필수라는 것이다.

세 신호는 **상호 보완적**이다. Metric으로 이상을 감지 → Trace로 느린 요청의 경로 특정 → 해당 span의 Log로 근본 원인 확정. 하나만 잘 갖춰도 안 되고, 하나만 빠져도 안 된다.

한계도 분명하다. **Logs는 cardinality 지옥**에 빠지기 쉽고(사용자 ID, 요청 ID를 로그 라벨로 인덱싱하면 저장 비용이 폭증), **Metrics는 평균의 함정**에 빠진다(평균 200ms인데 p99는 5초일 수 있다), **Traces는 sampling bias**가 있다(1% 샘플링이면 드물게 터지는 장애는 안 잡힌다).

## Structured Logging: JSON, Correlation ID, MDC

Plain text 로그는 기계가 읽기 어렵다. 프로덕션 로그는 **구조화된 JSON**이어야 한다.

나쁜 예:
```
2026-04-18 10:23:11 ERROR Failed to process order for user 12345: timeout after 3000ms on payment api
```

개선된 예:
```json
{
  "ts": "2026-04-18T10:23:11.482Z",
  "level": "ERROR",
  "logger": "com.olive.order.PaymentClient",
  "msg": "payment api call failed",
  "userId": "12345",
  "orderId": "ord_9f21",
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "spanId": "00f067aa0ba902b7",
  "latencyMs": 3000,
  "errorCode": "PAYMENT_TIMEOUT",
  "upstream": "payment-service",
  "env": "prod"
}
```

JSON 로그는 Elasticsearch/Loki/Datadog에 인덱싱해 `errorCode=PAYMENT_TIMEOUT AND env=prod` 같은 구조적 질의가 가능하다.

**Correlation ID**는 하나의 요청(또는 작업)에 부여되는 고유 식별자로, 여러 서비스와 로그 라인을 가로지르는 실을 만든다. Spring에서는 **MDC(Mapped Diagnostic Context)**에 주입해 모든 로그 라인에 자동 포함되게 한다.

```java
@Component
public class MdcFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest req,
                                    HttpServletResponse res,
                                    FilterChain chain) throws IOException, ServletException {
        String traceId = Optional.ofNullable(req.getHeader("traceparent"))
                .map(this::extractTraceId)
                .orElseGet(() -> UUID.randomUUID().toString().replace("-", ""));
        try {
            MDC.put("traceId", traceId);
            MDC.put("userId", Optional.ofNullable(req.getHeader("X-User-Id")).orElse("anon"));
            chain.doFilter(req, res);
        } finally {
            MDC.clear();
        }
    }
}
```

Logback 설정에서 MDC 값을 JSON 필드로 꺼낸다:

```xml
<appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
  <encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <includeMdcKeyName>traceId</includeMdcKeyName>
    <includeMdcKeyName>userId</includeMdcKeyName>
  </encoder>
</appender>
```

주의: `@Async`, `CompletableFuture`, `ExecutorService`에 작업을 넘기면 **MDC가 전파되지 않는다**. `TaskDecorator`로 스레드 경계를 넘길 때 MDC 복사를 명시해야 한다.

```java
@Bean
public TaskDecorator mdcTaskDecorator() {
    return runnable -> {
        Map<String, String> copy = MDC.getCopyOfContextMap();
        return () -> {
            if (copy != null) MDC.setContextMap(copy);
            try { runnable.run(); } finally { MDC.clear(); }
        };
    };
}
```

## 메트릭 분류: RED와 USE

모든 서비스에 대해 **어떤 메트릭을 봐야 하나?**라는 질문에 두 가지 정석 답이 있다.

**RED (요청 중심, 보통 API 서비스에 적용)**
- **R**ate: 초당 요청 수
- **E**rrors: 실패한 요청 수(또는 비율)
- **D**uration: 지연시간 분포(p50/p95/p99)

**USE (리소스 중심, 보통 인프라/백엔드 리소스에 적용)**
- **U**tilization: 사용률(CPU 70%)
- **S**aturation: 대기/포화(run queue 길이, DB connection pool wait)
- **E**rrors: 리소스 레벨 에러(디스크 read error, TCP retransmit)

실전에서는 **API 서비스는 RED로, DB/캐시/큐는 USE로** 본다. 둘 다 본다는 것이 핵심이다. Utilization이 60%로 여유로워 보여도 Saturation(예: connection pool이 꽉 차서 대기)이 있으면 사용자는 이미 느려졌다.

## Prometheus: scrape 모델과 4가지 타입

Prometheus는 **pull 기반 scrape 모델**이다. Prometheus 서버가 각 타겟(`/actuator/prometheus` 엔드포인트)을 주기적으로(보통 15s~30s) HTTP GET으로 긁어온다. 이 모델은:

- **서비스 디스커버리와 잘 맞는다** (Kubernetes pod label 기반 자동 타겟팅)
- **타겟의 생존을 자동으로 판단한다** (up=0이면 scrape 실패)
- **클라이언트는 단순 HTTP 서버만 있으면 된다** (에이전트 없음)

네 가지 메트릭 타입:

**Counter**: 단조 증가(monotonic). 누적 요청 수처럼 리셋만 되고 감소하지 않는다.
```
http_requests_total{method="POST",status="200"} 12482
```
쿼리는 `rate(http_requests_total[1m])`로 초당 증가율을 본다.

**Gauge**: 오르내리는 값. 현재 스레드 수, 큐 길이, 메모리 사용량.
```
jvm_threads_live_threads 42
```

**Histogram**: **서버 쪽**에서 사전 정의된 버킷에 카운트한다. Prometheus가 `histogram_quantile()`로 분위수를 계산한다.
```
http_request_duration_seconds_bucket{le="0.1"} 8812
http_request_duration_seconds_bucket{le="0.5"} 12100
http_request_duration_seconds_bucket{le="1.0"} 12400
http_request_duration_seconds_bucket{le="+Inf"} 12482
http_request_duration_seconds_sum 1842.3
http_request_duration_seconds_count 12482
```

**Summary**: **클라이언트 쪽**에서 분위수를 사전 계산한다. 서버에서 집계(aggregation)할 수 없다는 치명적 약점이 있다.

### Histogram vs Summary

면접에서 꽂히는 포인트다.

| 항목 | Histogram | Summary |
|---|---|---|
| 분위수 계산 | 서버(Prometheus) | 클라이언트 |
| 여러 인스턴스 합산 | 가능 | **불가능** |
| 정확도 | 버킷 경계에 의존 | 정확 |
| 런타임 비용 | 낮음 | 높음(sliding window) |
| 권장 | ✅ 대부분 | 특수한 경우만 |

여러 파드가 떠 있는 상황에서 전체 서비스 p99를 구하려면 **각 파드에서 이미 계산된 p99를 평균 내는 것은 수학적으로 틀린다**. Histogram은 각 파드의 버킷 카운트를 `sum by (le)`로 더한 뒤 `histogram_quantile`을 호출하므로 전역 분위수가 나온다.

### Cardinality 함정

```java
meter.counter("http.requests",
    "userId", userId,          // ❌
    "path", request.getPath(), // ❌ /users/123/orders 같은 ID 포함 경로
    "ip", clientIp             // ❌
).increment();
```

사용자 100만 명 × 경로 1만 개 × IP 수십만 개 = **수조 개의 타임시리즈**. Prometheus가 OOM 나고 저장 비용이 폭발한다. **메트릭 라벨에는 기수가 낮은(low-cardinality) 값만 넣는다.**

```java
meter.counter("http.requests",
    "method", request.getMethod(),
    "route", "/users/{id}/orders",   // ✅ 정규화된 라우트
    "status_class", "2xx"             // ✅ 200,201 대신 2xx
).increment();
```

사용자 ID나 원본 path는 **로그나 trace**에 둔다. 신호 분리의 핵심.

## Grafana 대시보드: SLO 중심, 10분 판단

대시보드를 **"이 서비스에서 사용할 수 있는 모든 지표"**로 채우는 것은 초보의 함정이다. 장애 초기 10분 안에 **"현재 서비스가 건강한가, 아닌가, 어느 쪽이 문제인가"**를 답할 수 있어야 한다.

설계 원칙:

1. **맨 위는 SLO 상태 한 줄**: "지난 1시간 availability 99.92% / budget 잔여 23%". 빨간색이면 즉시 액션.
2. **두 번째 줄은 RED 3종**: rate, error rate, p95/p99.
3. **그 아래가 의존성**: DB latency, cache hit rate, downstream service error rate.
4. **마지막이 리소스**: JVM heap, GC pause, thread pool.
5. **패널 간 drill-down 링크**: Grafana의 data link로 그래프 클릭 시 해당 시간대 로그/트레이스로 점프.

패널당 쿼리는 한두 개로, 축은 같은 단위끼리 묶는다(`latency ms`와 `count`를 한 축에 섞지 않는다). 범례에는 `method, route, status_class` 정도만 쓴다.

## Distributed Tracing: OpenTelemetry와 샘플링

**Trace**는 하나의 논리적 요청(예: 사용자 결제 하나)이 여러 서비스를 거치며 만든 span의 집합이다. **Span**은 하나의 작업 단위로 이름(`POST /orders`), 시작/종료 시간, attribute, event를 담는다. 각 span은 **parent span ID**를 참조해 트리를 이룬다.

OpenTelemetry(OTel)는 이 모델의 **업계 표준**이다. API(instrumentation 인터페이스), SDK(처리/내보내기), Collector(수집/가공/라우팅)로 구성된다. Java에서는 **OpenTelemetry Java agent**를 `-javaagent`로 붙이면 Spring MVC, JDBC, Kafka, Redis 등 **80+ 라이브러리가 자동 계측**된다.

```bash
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=order-service \
     -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
     -Dotel.traces.sampler=parentbased_traceidratio \
     -Dotel.traces.sampler.arg=0.1 \
     -jar order-service.jar
```

### 샘플링 전략

- **Head-based sampling**: 요청 시작 시점에 확률적으로(예: 10%) 결정. 구현 단순, 하지만 **드물게 터지는 에러를 놓친다**.
- **Tail-based sampling**: Collector가 trace 전체를 일단 버퍼에 모으고, 완료 후 조건(예: 에러 있음, duration > 1s)을 보고 저장 여부 결정. **의미 있는 trace만 저장**되지만 collector 메모리 부담이 크다.
- **Parent-based**: 부모 span의 샘플링 결정을 따라간다. 서비스 경계를 넘어도 일관성 유지.

실전에서는 **parent-based + head-based 낮은 비율(1~10%) + tail-based로 에러/slow trace 100% 저장**을 조합한다.

### Trace Context 전파: B3 vs W3C

서비스 A가 B를 호출할 때 HTTP 헤더로 trace context를 넘긴다.

**W3C Trace Context (현재 표준)**:
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
tracestate: congo=t61rcWkgMzE
```
포맷: `version-traceId-spanId-flags`.

**B3 (Zipkin 계열, 레거시)**:
```
X-B3-TraceId: 4bf92f3577b34da6a3ce929d0e0e4736
X-B3-SpanId: 00f067aa0ba902b7
X-B3-Sampled: 1
```

OTel SDK는 **propagator**를 설정해 두 포맷 모두 호환 가능하다. 레거시 서비스와 섞여 있으면 `tracecontext,baggage,b3multi`를 동시 사용한다.

**로그 상관**: trace/span ID를 MDC에 주입해 로그 JSON의 `traceId` 필드와 일치시킨다. 장애 조사 시 Grafana trace view에서 span 선택 → "View logs for this trace" 링크 → Loki 쿼리 `{service="order"} |= "4bf92f..."` 로 즉시 이동한다.

## Alert 설계: Symptom vs Cause

나쁜 알림은 **울리긴 하는데 뭘 하라는 건지 모른다**. oncall이 학습된 무기력에 빠지는 순간 Observability는 실패한 것이다.

원칙:

1. **Symptom-based alert를 우선한다**: 사용자에게 보이는 현상으로 알린다. "결제 API error rate > 2% for 5min"은 symptom. "DB CPU > 80%"는 cause — 이게 꼭 사용자 영향을 뜻하진 않는다.
2. **액션 가능한 알림만 보낸다**: 알림 = "사람이 깨서 무언가 해야 한다"의 요청. 아무 액션 없이 관찰만 하는 알림은 **알림이 아니다**(대시보드로 내린다).
3. **Multi-window, multi-burn-rate**: SLO budget 기반. "1시간 동안 14.4배 속도로 burn"과 "6시간 동안 6배 속도로 burn"을 동시에 만족하면 긴급 페이지(fast burn). 한쪽만이면 덜 긴급한 티켓.
4. **Runbook 링크 포함**: 알림 payload에 `runbook_url`. 새벽 3시에 처음 보는 알림을 5분 안에 대응할 수 있도록.
5. **Flapping 억제**: 최소 지속 시간(for 5m), hysteresis, alert grouping.

예 (Prometheus alertmanager rule):
```yaml
- alert: OrderApiHighErrorRate
  expr: |
    (sum(rate(http_requests_total{service="order",status_class="5xx"}[5m]))
     / sum(rate(http_requests_total{service="order"}[5m]))) > 0.02
  for: 5m
  labels:
    severity: page
  annotations:
    summary: "order-service 5xx rate > 2%"
    runbook_url: "https://wiki/runbooks/order-5xx"
    dashboard: "https://grafana/d/order-red"
```

## Logging Anti-patterns

실무에서 가장 자주 보는 실수들.

**과다 로깅**: 핫패스에서 `log.debug` 남발 → 디스크/네트워크 포화 → 서비스가 로그 I/O로 느려진다. 루프 안 로깅, request/response body 전량 덤프는 금지. **level은 의미 있게** 분리: INFO는 상태 변화, WARN은 비정상이지만 복구됨, ERROR는 사람이 봐야 함.

**PII 노출**: 주민번호, 전화번호, 카드번호, 이메일을 그대로 로그에 찍는 순간 법적 리스크. 마스킹 필터를 Logback `encoder` 레벨에 꽂는다.

```java
public class PiiMaskingConverter extends ClassicConverter {
    private static final Pattern PHONE = Pattern.compile("01[016789]-?\\d{3,4}-?\\d{4}");
    @Override
    public String convert(ILoggingEvent e) {
        return PHONE.matcher(e.getFormattedMessage()).replaceAll("***-****-****");
    }
}
```

**토큰 누출**: `Authorization: Bearer eyJ...` 헤더를 trace/log에 그대로 넣는 사고. OTel `tracing.http.capture-headers`에서 민감 헤더는 명시적으로 제외하고, 로그 필터에서 `authorization`, `cookie`, `set-cookie`를 drop한다.

**스택트레이스 남용**: catch한 뒤 원인을 이해하지도 않고 `log.error("error", e)`로 모든 레이어마다 스택트레이스를 찍으면, 하나의 예외가 로그 5번 찍혀 경보가 5배 튄다. **예외는 책임지는 한 레이어에서만 로깅**하고 나머지는 재던진다.

**로그 메시지에 가변 필드 concat**: `log.info("user " + userId + " paid " + amount)` → grep/aggregation 불가능. 항상 **구조화 필드로 분리**: `log.info("payment completed", kv("userId", userId), kv("amount", amount))`.

## 로컬 실습 환경

Docker Compose로 **Prometheus + Grafana + Tempo(trace) + Loki(log) + OpenTelemetry Collector** 스택을 띄운다.

```yaml
version: "3.9"
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel.yaml"]
    volumes: ["./otel.yaml:/etc/otel.yaml"]
    ports: ["4317:4317", "4318:4318"]
  prometheus:
    image: prom/prometheus:latest
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]
    ports: ["9090:9090"]
  tempo:
    image: grafana/tempo:latest
    command: ["-config.file=/etc/tempo.yaml"]
    volumes: ["./tempo.yaml:/etc/tempo.yaml"]
    ports: ["3200:3200"]
  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]
  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
```

Spring Boot 앱에 의존성:

```gradle
implementation "org.springframework.boot:spring-boot-starter-actuator"
implementation "io.micrometer:micrometer-registry-prometheus"
implementation "net.logstash.logback:logstash-logback-encoder:7.4"
```

`application.yml`:
```yaml
management:
  endpoints.web.exposure.include: "health,prometheus,info"
  metrics.distribution:
    percentiles-histogram:
      http.server.requests: true
    slo:
      http.server.requests: 50ms, 100ms, 200ms, 500ms, 1s
```

Java agent는 앱 실행 시 attach:
```bash
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.exporter.otlp.endpoint=http://localhost:4317 \
     -Dotel.service.name=order-service \
     -jar build/libs/order-service.jar
```

부하 생성: `hey -z 30s -c 20 http://localhost:8080/orders`. Grafana에서 RED 대시보드, trace view, log drill-down을 실제로 연결해 보면 **세 신호가 trace ID 하나로 묶이는 경험**을 얻는다.

## 실습 예제: 의도된 장애

연습용 엔드포인트 하나를 추가해 5% 확률로 느리게, 1% 확률로 500을 낸다.

```java
@RestController
@RequiredArgsConstructor
public class OrdersController {
    private final MeterRegistry meter;
    private final Tracer tracer;

    @PostMapping("/orders")
    public ResponseEntity<?> create(@RequestBody OrderReq req) {
        Span span = tracer.spanBuilder("create-order").startSpan();
        try (Scope s = span.makeCurrent()) {
            span.setAttribute("user.id", req.userId());
            if (ThreadLocalRandom.current().nextDouble() < 0.05) {
                Thread.sleep(2000);
            }
            if (ThreadLocalRandom.current().nextDouble() < 0.01) {
                meter.counter("order.failed", "reason", "injected").increment();
                throw new RuntimeException("injected failure");
            }
            return ResponseEntity.ok(Map.of("orderId", "ord_" + UUID.randomUUID()));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } finally {
            span.end();
        }
    }
}
```

부하를 주면 Grafana RED 패널에서 p99가 튀고 error rate가 1%로 형성된다. **알림을 `error rate > 0.5% for 5m`으로 설정해 실제로 발화시키고, 알림 → 대시보드 → slow trace → trace 안의 span → span 태그의 userId → 해당 userId 로그**까지 점프하는 경로를 몸으로 익힌다.

## 면접 답변 프레임

**질문: "장애를 어떻게 탐지하고 대응하나요?"**

구조화된 답:

1. **탐지 레이어**: "저희는 SLO 기반 multi-burn-rate 알림을 씁니다. 사용자에게 보이는 symptom(error rate, p99 latency)을 1차로 알리고, cause 레벨 지표(DB connection saturation, GC pause)는 대시보드로만 봅니다. 액션 가능한 알림만 페이지로 보내는 게 원칙입니다."

2. **초기 10분 판단**: "알림이 오면 RED 대시보드 한 화면으로 'rate 유지, error 튐' 같이 범위를 좁힙니다. 어느 서비스, 어느 엔드포인트, 어느 상태코드인지 10분 안에 답하는 게 목표입니다."

3. **원인 추적**: "메트릭으로 범위가 좁혀지면 같은 시간대 slow/error trace를 tail-based 샘플링한 Tempo에서 열어 span 경로를 봅니다. DB span이 튀었는지, 외부 API가 느린지, lock contention이 있는지 span attribute로 구분합니다."

4. **근본 원인 확정**: "특정 span의 trace ID로 Loki에서 로그를 걸어 예외 stack과 request context를 봅니다. MDC로 trace ID가 로그에 박혀 있어서 grep 한 번이면 요청 수명 전체가 재구성됩니다."

5. **실전 에피소드**: "한번은 결제 서비스 p99가 500ms에서 3초로 튀었는데 대시보드상 CPU/메모리는 정상이었습니다. Trace를 열어 보니 `payment-gateway` 호출 span이 3초에 박혀 있었고, log의 `errorCode=CONN_TIMEOUT`과 함께 upstream 쪽 connection pool exhaustion이 원인이었습니다. Hikari max pool을 조정하고 retry에 circuit breaker를 걸어 SLO를 회복시켰습니다."

6. **회고**: "사후에는 postmortem에 '탐지까지 걸린 시간', 'MTTR', '알림이 액션으로 이어졌는가'를 적고, 알림 rule이나 runbook을 갱신합니다. Observability는 한 번 세팅하면 끝이 아니라, 장애마다 지표/알림이 진화합니다."

이 구조는 면접관이 듣고 싶은 것 — **도구 이름 나열이 아니라 의사결정의 흐름** — 을 정확히 채운다.

## 자주 나오는 후속 질문

- "왜 Summary 대신 Histogram을 쓰나요?" → 여러 인스턴스의 분위수 합산 가능성.
- "Sampling 1%인데 드문 에러는 어떻게 잡나요?" → Tail-based sampling으로 에러/slow trace는 100% 저장.
- "로그 비용이 폭발합니다. 어떻게 줄이나요?" → 레벨 조정, PII/payload 제거, 구조화 + 집계로 대체 가능한 신호는 metric으로 이동, 인덱스 필드 축소(라벨 cardinality 관리).
- "trace ID를 어떻게 전파하나요?" → W3C `traceparent` 헤더, OTel propagator, 비동기 경계는 `TaskDecorator`/context propagation API.
- "Prometheus의 한계는?" → 장기 저장 한계(Thanos/Mimir로 보완), push 기반 워크로드(short-lived job은 pushgateway), high-cardinality 취약.

## 체크리스트

- [ ] 로그가 JSON 구조화되어 있고 `traceId`, `spanId`, `userId`가 모든 라인에 실려 있다.
- [ ] MDC가 `@Async`와 `ExecutorService`에서도 전파된다(`TaskDecorator` 확인).
- [ ] 메트릭 라벨에 userId/raw path/IP 같은 high-cardinality 값이 없다.
- [ ] API 서비스는 RED, 리소스는 USE로 대시보드를 나눈다.
- [ ] SLO가 정의되어 있고 burn-rate 기반 알림이 걸려 있다.
- [ ] 알림마다 runbook_url과 dashboard 링크가 붙어 있다.
- [ ] OpenTelemetry Java agent가 붙어 있고 W3C Trace Context로 서비스 경계를 넘는다.
- [ ] Tail-based sampling으로 에러/slow trace는 100% 저장된다.
- [ ] 로그에 PII, 토큰, 쿠키가 마스킹 필터로 제거된다.
- [ ] 로컬 compose 스택(Prometheus + Grafana + Tempo + Loki + OTel Collector)에서 end-to-end로 drill-down이 동작한다.
- [ ] 최근 장애 1건에 대해 "탐지 → 판단 → 원인 → 회복 → 회고"를 한 문단으로 설명할 수 있다.
- [ ] Histogram과 Summary의 차이, 여러 인스턴스 p99 계산 방식을 말로 설명할 수 있다.
- [ ] Symptom alert와 cause alert의 차이, 왜 symptom을 우선하는지 설명할 수 있다.

---

## 관련 문서

- [Resilience 패턴](./resilience-patterns.md) — Circuit Breaker 상태와 Observability 연결
- [Datadog APM 실전 투입 가이드](../observability/datadog-apm-observability.md) — Java/Spring 관측성 스택
- [OpenTelemetry (Java)](../java/opentelemetry/README.md) — traceId 생성과 전파
