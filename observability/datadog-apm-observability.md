# [초안] Datadog APM 실전 투입 가이드: Java/Spring 서비스 관측성 스택 구축하기

## 왜 이 주제가 중요한가

CJ OliveYoung Wellness Platform 같이 트래픽이 일 수백만 건 들어오는 커머스 백엔드는 관측성(observability) 스택이 곧 SRE 생존선이다. 장애 탐지 시간(MTTD)과 복구 시간(MTTR)을 초/분 단위로 줄이려면, 로그만 뒤져서는 답이 안 나온다. 분산 요청이 5~10개 마이크로서비스를 타고 흐르는데 "어디서 느려졌나"를 5분 안에 집어내야 한다.

Datadog은 한국의 대형 커머스(쿠팡, 컬리 등)와 마찬가지로 CJ OliveYoung도 실전 스택으로 쓰는 통합 관측성 플랫폼이다. Metrics / Logs / APM / RUM / Profiler / Synthetics 를 한 UI에서 상관관계로 엮을 수 있다는 것이 Datadog을 다른 도구 대비 붙여 쓰는 가장 큰 이유다. ELK + Prometheus + Jaeger를 각각 운영하는 팀 입장에서는 "같은 요청의 로그와 trace를 한 번의 클릭으로 연결"이라는 경험이 생산성을 결정한다.

이 문서는 일반 observability 이론 팩이 아닌, Datadog을 실전에 투입할 때 반드시 알아야 하는 데이터 모델, 태깅, 샘플링, 비용, 알람, 장애 대응 플레이북을 시니어 백엔드 관점에서 다룬다.

## 1. Datadog 데이터 모델: 4개 제품의 범위와 한계

Datadog을 쓰다 보면 "이 지표를 Metric으로 볼지, Log로 볼지, APM Span으로 볼지" 같은 결정을 자주 한다. 각 제품의 본질적인 차이를 이해해야 비용과 정확도를 동시에 잡을 수 있다.

**Metrics**는 시계열 수치 데이터다. CPU, 메모리, 요청 수, latency p99 같은 값들. 15초 이하 집계 단위로 저장되고 장기 보관(기본 15개월)이 가능하다. 특징은 태그 조합 카디널리티가 폭증하면 비용이 수직 상승한다는 점이다. `user_id`, `order_id` 같은 고유 식별자를 태그로 박으면 재앙이 시작된다.

**Logs**는 구조화된 이벤트다. JSON 로그로 보내면 각 필드가 검색 가능해진다. 보관 계층이 둘로 나뉜다 — 인덱싱된 로그(빠른 검색, 비싸다)와 리하이드레이션 가능한 아카이브(S3, 저렴하지만 즉시 검색은 안 됨). 로그는 "개별 사건" 추적에 강하다.

**APM(Application Performance Monitoring)** 은 요청 단위 분산 trace다. 하나의 HTTP 요청이 Spring Controller → Service → JPA → MySQL → Redis → Kafka Producer로 흐르는 전체 경로를 Span 트리로 재구성한다. 사용자가 "주문이 느려요"라고 할 때, 정확히 어느 span에서 800ms를 태웠는지 본다.

**RUM(Real User Monitoring)** 은 브라우저/모바일 프론트 성능이다. 백엔드 개발자가 직접 다룰 일은 적지만, Frontend trace와 Backend trace를 `x-datadog-trace-id` 헤더로 이어 붙이면 "첫 페이지 로드부터 DB 쿼리까지"의 end-to-end view가 완성된다.

한계도 명확하다. APM은 기본적으로 샘플링되므로 모든 요청을 다 보존하지 않는다. Logs는 오래되면 검색이 느려지거나 인덱싱에서 빠진다. Metrics는 개별 사건 디버깅엔 쓰지 못한다. 이 한계 때문에 **세 제품을 trace_id로 엮는 상관관계 설계**가 실전 포인트가 된다.

## 2. Java/Spring 앱에 Datadog Agent + Tracer 붙이기

실전 설치는 크게 두 컴포넌트다. 호스트(또는 Kubernetes DaemonSet)에서 도는 **Datadog Agent**와 애플리케이션 JVM에 attach되는 **dd-java-agent.jar**.

도커/쿠버네티스 환경에서의 최소 구성은 다음과 같다.

```dockerfile
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY build/libs/app.jar /app/app.jar

# Datadog Java tracer
ADD https://dtdg.co/latest-java-tracer /app/dd-java-agent.jar

ENV DD_SERVICE=oliveyoung-order-api
ENV DD_ENV=prod
ENV DD_VERSION=1.42.0
ENV DD_LOGS_INJECTION=true
ENV DD_PROFILING_ENABLED=true
ENV DD_TRACE_SAMPLE_RATE=1.0

ENTRYPOINT ["java", "-javaagent:/app/dd-java-agent.jar", "-jar", "/app/app.jar"]
```

Kubernetes에서는 Datadog Agent를 DaemonSet으로 배포하고, 각 Pod의 `localhost:8126`(APM), `localhost:8125`(StatsD), `localhost:10518`(Logs) 포트로 tracer가 에이전트에 전송한다. Pod annotation이나 환경변수로 Unified Service Tagging을 넣는다.

```yaml
spec:
  containers:
    - name: order-api
      env:
        - name: DD_AGENT_HOST
          valueFrom:
            fieldRef:
              fieldPath: status.hostIP
        - name: DD_SERVICE
          value: oliveyoung-order-api
        - name: DD_ENV
          value: prod
        - name: DD_VERSION
          value: "1.42.0"
```

Auto-instrumentation 범위가 실전에선 매우 넓다. 설정 한 줄 없이 자동으로 trace가 잡히는 것들:

- Spring Web / WebFlux / MVC 컨트롤러 진입점
- JDBC / Hibernate / JPA 쿼리 (rendered SQL + 실행 시간)
- HTTP 클라이언트 (RestTemplate, WebClient, OkHttp, Apache HttpClient)
- Redis (Lettuce, Jedis)
- Kafka (Producer / Consumer, partition, offset, consumer group 태그 자동)
- gRPC, Elasticsearch, MongoDB
- AWS SDK (S3, SQS, DynamoDB 호출에 aws.operation span 태그 자동 부착)

이 자동 계측만으로도 80%의 bottleneck을 잡아낸다. 내가 경험한 MDC / OpenTelemetry 기반의 수동 trace 코드 작업이 Datadog에선 설치와 동시에 제공된다는 점이 가장 큰 생산성 차이다.

## 3. Trace → Span → Service Map으로 Bottleneck 잡기

실전 디버깅 플로우를 예시로 본다. p99 latency alert이 `oliveyoung-order-api` 서비스에서 발생했다고 가정한다.

**1단계 — Service Map 진입.** APM → Service Map 에서 해당 서비스 노드를 클릭한다. 연결된 upstream / downstream 서비스가 화살표로 그려지고, 각 엣지에 requests/s, error %, p99 latency가 뜬다. 예를 들어 order-api → inventory-api 엣지의 p99가 평소 120ms에서 1.8s로 튀어 있으면 문제 지점이 좁혀진다.

**2단계 — Trace 리스트 필터링.** APM → Traces 에서 `service:oliveyoung-order-api env:prod @duration:>1s status:error` 같은 쿼리를 건다. Datadog의 trace query 문법은 로그와 비슷하다. 상위 10개 slow trace를 뽑아 본다.

**3단계 — Flame Graph 분석.** 개별 trace를 열면 flame graph가 펼쳐진다. x축은 시간, y축은 호출 스택. Root span이 `POST /orders`라면 그 밑에 `OrderService.placeOrder` → `InventoryClient.reserve` → `http.request GET /inventory/reserve` → `jdbc.query SELECT ...` 가 펼쳐진다. 어느 span에서 대부분의 시간을 쓰는지 한눈에 보인다.

**4단계 — Span 상세 조사.** SQL span을 클릭하면 실제 실행된 쿼리, DB host, connection pool wait time까지 태그로 붙는다. "connection pool이 고갈되어 300ms 대기 후 실행되었다" 같은 판정이 가능하다.

이 흐름이 실전에서 의미 있는 건, Grafana + Jaeger 조합에서는 같은 작업에 3개 탭을 왔다 갔다 해야 하지만 Datadog은 한 화면에서 끝난다는 점이다.

## 4. Unified Service Tagging: DD_ENV / DD_SERVICE / DD_VERSION

Datadog의 가장 강력한 기능 중 하나가 **Unified Service Tagging**이다. 이 세 태그를 일관되게 부착하면 Metrics, Logs, APM, Profiler가 자동으로 상관관계를 갖게 된다.

- `env` — 환경 (prod, staging, dev, canary)
- `service` — 서비스 이름 (oliveyoung-order-api, oliveyoung-catalog-api 등)
- `version` — 배포 버전 (Git tag, SHA, 빌드 번호)

**배포 단위 비교 시나리오.** v1.42.0 배포 직후 p99가 튄다면, APM 대시보드에서 `version:1.42.0` vs `version:1.41.0` 로 필터를 나눠 latency 분포를 중첩해 본다. 특정 엔드포인트에서만 regression이 생겼는지, 특정 downstream 호출에서 차이가 나는지 즉시 보인다.

**릴리스 추적.** Deploy Tracking 기능을 쓰면 Git provider(GitHub / GitLab)와 연동되어 "이 배포는 어떤 커밋을 포함하나"가 UI에 붙는다. 장애 발생 시간대와 배포 타임라인을 겹쳐 "12:07 배포 → 12:09부터 error rate 급증"이 시각화된다.

**태그 전략 실수 패턴.** `DD_VERSION`을 빌드 번호 `build-1234`로 쓰면 Git 커밋을 역추적하기 어렵다. Git short SHA나 semantic version을 쓰는 게 낫다. `DD_SERVICE`를 인스턴스마다 다르게 넣는 것도 피해야 한다(서비스 = 배포 단위여야 한다).

## 5. Custom Span: @Trace와 비즈니스 경계

Auto-instrumentation이 커버하지 못하는 비즈니스 계층 경계는 직접 span을 만들어야 한다.

```java
import datadog.trace.api.Trace;

@Service
public class OrderService {

    @Trace(operationName = "order.place", resourceName = "OrderService.placeOrder")
    public OrderResult placeOrder(OrderCommand cmd) {
        validateCoupon(cmd);
        reserveInventory(cmd);
        createPayment(cmd);
        publishOrderPlacedEvent(cmd);
        return OrderResult.success();
    }

    @Trace(operationName = "coupon.validate")
    private void validateCoupon(OrderCommand cmd) { /* ... */ }
}
```

`@Trace`는 개별 메서드를 span으로 만든다. 내가 언제 이걸 넣는지 기준:

1. **비즈니스 단계 경계** — `validateCoupon`, `reserveInventory`, `createPayment` 같은 단계. flame graph에서 단계별 시간 분포가 보인다.
2. **복잡한 loop / batch** — for 루프 안에서 무거운 연산을 하면 한 번의 loop iteration을 span으로 뜬다.
3. **Kafka consumer loop** — 자동 계측은 `deliverMessage` 레벨에서만 span을 뜨는 경우가 많다. 메시지별 비즈니스 처리를 span으로 감싸야 "어떤 메시지 타입이 느린가"가 보인다.
4. **외부 호출 직전 afterAction** — retry loop, circuit breaker fallback 같은 지점.

수동 API도 쓸 수 있다.

```java
import io.opentracing.Span;
import io.opentracing.Tracer;
import io.opentracing.util.GlobalTracer;

Tracer tracer = GlobalTracer.get();
Span span = tracer.buildSpan("inventory.reserve.retry").start();
try {
    span.setTag("retry.attempt", attempt);
    span.setTag("order.id", orderId);
    doReserve();
} catch (Exception e) {
    span.setTag("error", true);
    span.log(Map.of("event", "error", "error.message", e.getMessage()));
    throw e;
} finally {
    span.finish();
}
```

주의 — 고유 식별자(`order.id`, `user.id`)를 span 태그로 붙일 때는 APM 검색엔 유용하지만, 이걸 그대로 custom metric 태그로 가져가면 cardinality가 폭발한다.

## 6. Log Correlation: trace_id 자동 주입

Datadog이 로그와 trace를 이어주는 핵심이 **MDC(Mapped Diagnostic Context) 자동 주입**이다. `DD_LOGS_INJECTION=true` 환경변수를 켜면 Java tracer가 SLF4J MDC에 `dd.trace_id`, `dd.span_id`, `dd.service`, `dd.env`, `dd.version`을 자동으로 박는다.

Logback 설정 예시:

```xml
<configuration>
    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>dd.trace_id</includeMdcKeyName>
            <includeMdcKeyName>dd.span_id</includeMdcKeyName>
            <includeMdcKeyName>dd.service</includeMdcKeyName>
            <includeMdcKeyName>dd.env</includeMdcKeyName>
            <includeMdcKeyName>dd.version</includeMdcKeyName>
        </encoder>
    </appender>
    <root level="INFO">
        <appender-ref ref="JSON"/>
    </root>
</configuration>
```

출력되는 JSON 로그:

```json
{
  "@timestamp": "2026-04-18T10:23:45.123Z",
  "level": "ERROR",
  "logger_name": "o.c.o.o.OrderService",
  "message": "Inventory reservation failed: SKU=SKU-123",
  "dd.trace_id": "6841823973034827458",
  "dd.span_id": "4821039485720384",
  "dd.service": "oliveyoung-order-api",
  "dd.env": "prod",
  "dd.version": "1.42.0"
}
```

Datadog UI에서는 이 trace_id가 자동 파싱되어, 로그 한 줄 옆에 "View in APM" 버튼이 생긴다. 반대로 APM trace에서 "Logs" 탭을 누르면 해당 요청의 모든 로그가 뜬다. 이 **양방향 점프**가 실전 디버깅의 핵심이다.

수동 MDC 관리 경험이 있다면 자연스럽다. 기존에 OpenTelemetry 기반으로 `MDC.put("traceId", ...)` 해왔다면, Datadog에선 그 작업이 tracer가 자동으로 해주고 필드 네이밍 컨벤션(`dd.trace_id`)만 따르면 된다.

## 7. Monitor / SLO / SLI: RED와 USE

**SLI(Service Level Indicator)** 는 측정 대상 메트릭, **SLO(Service Level Objective)** 는 그 메트릭의 목표값이다.

Backend API 관측에 흔히 쓰는 두 프레임워크:

**RED** — User-facing request 중심.
- Rate — 초당 요청 수
- Errors — 에러율
- Duration — 응답 시간 분포 (p50, p95, p99)

**USE** — Resource 중심.
- Utilization — CPU/Memory 사용률
- Saturation — queue 길이, 대기 시간
- Errors — 에러 카운트

실전 SLO 예: "oliveyoung-order-api의 `/orders` POST 엔드포인트 p99 latency < 800ms, 에러율 < 0.5%, 30일 윈도우 99.5% 준수."

Datadog SLO Widget으로 이걸 추적한다. Error budget이 소진되면 Slack으로 alert이 간다. Monitor 종류:

- **Metric Monitor** — 단순 threshold (`avg(last_5m):p99:trace.servlet.request{service:oliveyoung-order-api} > 0.8`)
- **Anomaly Monitor** — 계절성과 trend를 학습해 "평소 대비 이상"을 탐지. 요일/시간대 패턴이 명확한 커머스 트래픽에 적합하다.
- **Forecast Monitor** — "현재 추세로 7일 내 디스크가 꽉 찬다" 같은 예측 알람.
- **Composite Monitor** — 여러 monitor를 AND/OR로 엮는다. "error rate 상승 AND deploy 이벤트 발생" 같은 조건부 알람에 쓴다.

**언제 어떤 걸 쓰나?**

Threshold monitor는 SLO 위반 같은 명확한 기준이 있을 때. Anomaly는 트래픽 패턴이 주기적이고 절대 threshold를 잡기 어려울 때(예: 심야 주문량 vs 피크 시간 주문량). Forecast는 자원 고갈(디스크, 커넥션 풀). Composite는 false positive를 줄여야 할 때 — 단일 메트릭 튐은 무시하고 복합 조건일 때만 호출.

## 8. Dashboard / Notebook: 장애 초기 10분 판단용 뷰

서비스 온콜을 받았을 때, 10분 안에 "지금 문제가 내 서비스 책임인가, downstream인가"를 판정해야 한다. 그걸 위한 전용 대시보드 구성 예:

**Row 1 — Golden Signals (RED)**
- Request rate (rpm) — 30분 window, 평소 대비 drop/spike 확인
- Error rate (%) — `trace.servlet.request.errors / trace.servlet.request.hits`
- Latency p50/p95/p99 — 각 엔드포인트별

**Row 2 — Dependency Health**
- Downstream HTTP call latency per service (inventory, payment, coupon)
- Redis command duration p99
- MySQL query p99, 특히 `connection_wait_time`
- Kafka consumer lag per topic

**Row 3 — Infrastructure**
- JVM heap usage, GC pause duration
- CPU / Memory per pod
- HTTP 5xx / 4xx 분포
- Pod restart 이벤트

**Row 4 — Business Metrics**
- 주문 성공률, 결제 성공률
- 이상 값이 비즈니스 레벨에 보이는가

Notebook은 incident review 시점에 쓴다. 라이브 대시보드는 현재 상태를 보고, Notebook은 "어제 14:32 장애 회고"를 위해 그 시점 고정 쿼리를 엮어 문서화한다. 팀 포스트모템에 그대로 붙인다.

## 9. Continuous Profiler: CPU/Memory/Lock

Datadog Continuous Profiler는 JVM에서 JFR(Java Flight Recorder)을 상시 돌려 stack trace sample을 계속 수집한다. `DD_PROFILING_ENABLED=true` 하나로 켠다.

제공하는 프로파일 종류:
- **CPU profile** — 어떤 메서드가 CPU time을 먹는가. hot path 식별.
- **Allocation profile** — 어디서 객체가 많이 만들어지는가. GC pressure 원인 추적.
- **Lock profile** — synchronized / ReentrantLock 경합이 어디서 생기나.
- **Exception profile** — 예외가 어느 지점에서 던져지고 캐치되나.

실전 활용 예 — "특정 엔드포인트만 p99가 튀는데 DB는 빠르다." APM trace를 봐도 Java 내부 CPU 시간이 긴 상태라면 Profiler로 가서 같은 시간대의 hot method를 본다. `com.fasterxml.jackson.databind.ObjectMapper` 직렬화가 CPU의 40%를 먹고 있다면, DTO 구조나 JSON 필드 수 문제가 원인이다.

## 10. 비용 관리: Cardinality, Sampling, Indexing

Datadog 비용이 터지는 세 지점:

**Custom Metric Cardinality.** Custom metric당 unique tag 조합 수가 과금 단위다. `order.placed.count` 메트릭에 `{env, service, version}` 태그만 붙이면 태그 조합 수십 개지만, `{env, service, version, user_id, sku_id}` 를 붙이면 수백만 개로 폭발한다. 규칙: **고유 식별자는 로그/span attribute에만, Metric tag에는 절대 금지.**

**APM Span Sampling.** 프로덕션에서 모든 trace를 보내면 APM 비용이 살인적이다. 두 종류의 샘플링:

- **Head-based sampling** — 요청 시작 시점에 "이 trace를 기록할지"를 결정. `DD_TRACE_SAMPLE_RATE=0.1`로 설정하면 10%만 수집. 단점은 희귀한 에러 trace를 놓칠 수 있다.
- **Tail-based sampling** — trace 종료 후 "이 trace가 에러가 있었나, 느렸나" 보고 결정. 에러 및 slow trace는 100% 보존. Datadog Agent가 Ingestion Control과 연동해 지원한다. 비용과 신호 대비 효율이 훨씬 낫다.

정책 예: "정상 trace 5% + 에러 trace 100% + p99 > 1s trace 100%."

**Log Indexing.** Datadog Logs는 수집(ingestion)과 인덱싱(indexing)이 별도로 과금된다. 수집은 상대적으로 싸고, 인덱싱(7~30일 검색 보관)이 비싸다. Log Pipeline에서 exclusion filter를 걸어 "DEBUG 로그는 인덱싱하지 않는다", "health check 요청 로그는 제외" 같은 규칙을 만든다. 필요하면 장기 아카이브를 S3로 보내 reshydration으로 꺼내 쓴다.

## 11. 장애 대응 플레이북

실제 호출을 받았을 때의 표준 플로우:

1. **APM Alert 확인** — Slack에 뜬 alert link를 연다. Monitor의 context로 영향 받는 서비스와 태그를 파악한다.
2. **Service Map 진입** — 문제 서비스의 upstream/downstream edge 중 red 색상이 어디인지. 내 책임인지 downstream 책임인지 30초 안에 판정.
3. **Error Trace 샘플 분석** — Traces 탭에서 `status:error` 로 필터. 상위 trace 3개를 열어 flame graph에서 실패 지점 확인. 에러 메시지, stack trace 태그 확인.
4. **Deploy Diff 확인** — Deployments 타임라인을 본다. 장애 시작 시각 직전에 내 서비스나 downstream 서비스 배포가 있었나. 있다면 Git diff 링크로 이동.
5. **Feature Flag Toggle** — LaunchDarkly/Unleash 등이 통합되어 있다면 해당 플래그 변경 이력을 본다. 플래그 전환으로 regression이 생긴 거면 즉시 롤백.
6. **Mitigation 선택** — (a) 배포 롤백 (b) feature flag off (c) 트래픽 throttle (d) circuit breaker open 중 가장 빠른 수단.
7. **Postmortem Notebook** — Datadog Notebook에 해당 시간대의 모든 쿼리와 트레이스 스냅샷을 고정 저장해 회고 자료로 쓴다.

## 12. Bad vs Improved 예시

**Bad 예시 1 — Unified Tagging 누락**

```yaml
env:
  - name: DD_SERVICE
    value: api
  - name: DD_VERSION
    value: "latest"
```

`api`라는 이름은 어떤 서비스인지 알 수 없고, `latest`는 롤백 시 버전 비교를 불가능하게 한다. 서비스맵에서 다른 "api" 서비스와 섞여 디버깅이 지옥이 된다.

**Improved**

```yaml
env:
  - name: DD_SERVICE
    value: oliveyoung-order-api
  - name: DD_VERSION
    value: "1.42.0-a1b2c3d"
  - name: DD_ENV
    value: prod
```

**Bad 예시 2 — Custom Metric에 고유 식별자**

```java
statsd.increment("order.placed",
    "user_id:" + userId,
    "order_id:" + orderId);
```

사용자 10만 명 × 주문 수백만 → metric 카디널리티 폭발, 월말 청구서 3~10배 증가.

**Improved — span attribute로 이동, metric은 low cardinality로**

```java
statsd.increment("order.placed",
    "env:prod",
    "payment_method:" + paymentMethod,
    "tier:" + userTier);

Span span = GlobalTracer.get().activeSpan();
if (span != null) {
    span.setTag("user.id", userId);
    span.setTag("order.id", orderId);
}
```

**Bad 예시 3 — 로깅과 trace 단절**

```java
log.error("Failed to process order: " + orderId);
```

plain string으로 로그 쓰면 JSON 필드가 아니라 message 전체로 검색해야 한다. trace correlation이 안 된다.

**Improved**

```java
log.error("Failed to process order", 
    kv("order.id", orderId),
    kv("payment.method", paymentMethod),
    kv("error.type", e.getClass().getSimpleName()),
    e);
```

MDC trace_id는 tracer가 자동으로 주입하고, key-value는 로그 필드가 된다. Datadog에서 `@order.id:12345` 로 직접 검색 가능.

## 13. 로컬 실습 환경

Datadog은 30일 trial이 있다. 학습용 환경을 간단히 구축하자.

**Docker Compose로 Datadog Agent + Spring 앱 + MySQL + Redis + Kafka:**

```yaml
version: '3.8'
services:
  datadog-agent:
    image: gcr.io/datadoghq/agent:7
    environment:
      - DD_API_KEY=${DD_API_KEY}
      - DD_SITE=datadoghq.com
      - DD_APM_ENABLED=true
      - DD_APM_NON_LOCAL_TRAFFIC=true
      - DD_LOGS_ENABLED=true
      - DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true
      - DD_DOGSTATSD_NON_LOCAL_TRAFFIC=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc/:/host/proc/:ro
      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
    ports:
      - "8126:8126"
      - "8125:8125/udp"

  order-api:
    build: ./order-api
    environment:
      - DD_AGENT_HOST=datadog-agent
      - DD_SERVICE=order-api
      - DD_ENV=local
      - DD_VERSION=0.1.0
      - DD_LOGS_INJECTION=true
      - DD_TRACE_SAMPLE_RATE=1.0
      - DD_PROFILING_ENABLED=true
    depends_on:
      - datadog-agent
      - mysql
      - redis

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: orders

  redis:
    image: redis:7-alpine
```

**실습 과제:**
1. 위 환경으로 Spring Boot 앱을 띄운다.
2. `POST /orders` 엔드포인트 — validate → inventory check(외부 API call simulation) → save to MySQL → publish to Redis Stream.
3. `curl`로 요청을 100개 쏜다.
4. Datadog UI → APM → Service Map에서 order-api 노드 확인.
5. Traces 리스트에서 individual trace 하나 열고 flame graph 관찰.
6. 의도적으로 `Thread.sleep(2000)`을 중간에 박고 trace에서 해당 구간이 어떻게 표시되는지 확인.
7. Profiler 탭으로 가서 해당 메서드가 CPU profile에 잡히는지 확인.
8. Monitor를 하나 만든다 — `avg(last_5m):avg:trace.servlet.request.duration{service:order-api} > 1`.
9. 부하를 다시 걸어 alert이 Slack에 뜨는지 확인.

## 14. 면접 답변 프레이밍

"운영 중 장애를 어떻게 탐지하고 추적하시나요?" 라는 질문이 자주 나온다. 시니어 백엔드 답변 구조 예:

"장애는 크게 두 층에서 탐지합니다. 첫째는 **SLO 기반 alert** — 서비스별로 RED(Rate, Errors, Duration)를 SLI로 정의하고, p99 latency와 error rate threshold가 SLO를 위반하면 Datadog monitor가 Slack으로 호출합니다. 저희 팀은 트래픽 계절성이 있어서 threshold 대신 **anomaly monitor**를 쓰는 경우도 있습니다.

탐지 후 추적은 **APM flame graph가 기본 진입점**입니다. Service map에서 어느 서비스 edge가 빨간지 먼저 보고, 문제 서비스의 slow trace 샘플을 열어 flame graph에서 bottleneck span을 찾습니다. DB span이면 실행된 쿼리와 connection pool wait time을 span 태그로 확인하고, downstream HTTP call이면 해당 서비스 trace로 점프합니다.

로그와 trace는 **trace_id로 correlation**이 자동으로 됩니다. 저희 스택에서는 SLF4J MDC에 tracer가 자동으로 dd.trace_id를 박아주고, Logback JSON encoder가 필드로 출력합니다. 그래서 APM trace → Logs 탭으로 바로 이동해 해당 요청의 로그만 뽑아 볼 수 있습니다.

이전에는 OpenTelemetry + Jaeger + ELK로 직접 traceId를 관리했는데, MDC context propagation 이슈와 도구 분리로 디버깅 시간이 길어졌습니다. Datadog은 auto-instrumentation 범위가 넓어 JPA, Kafka, Redis까지 별도 작업 없이 span이 잡히고, 한 UI에서 metric/log/trace를 넘나들 수 있어 MTTR이 크게 줄었습니다.

배포 관련 regression은 **Unified Service Tagging**의 version 태그로 diff합니다. 배포 전후 버전의 p99를 중첩해 보고, 특정 엔드포인트에서 regression이 있으면 Git deploy diff로 연결해 커밋을 봅니다. feature flag로 gradual rollout을 했다면 그쪽을 먼저 off 시키는 게 1차 mitigation입니다."

## 15. 체크리스트

**설치/설정 단계**
- [ ] Datadog Agent를 DaemonSet(K8s) 또는 호스트 데몬(VM)으로 배포했는가
- [ ] dd-java-agent.jar를 모든 JVM에 `-javaagent`로 붙였는가
- [ ] DD_ENV, DD_SERVICE, DD_VERSION을 모든 환경에서 일관되게 지정했는가
- [ ] DD_LOGS_INJECTION=true로 MDC trace_id 자동 주입을 켰는가
- [ ] Logback/Log4j에 `dd.trace_id`, `dd.span_id`, `dd.service`, `dd.env`, `dd.version` MDC 출력을 추가했는가
- [ ] DD_PROFILING_ENABLED=true로 Continuous Profiler를 켰는가

**태깅 / 메트릭 단계**
- [ ] Custom metric 태그에 user_id / order_id 같은 고유 식별자가 들어가지 않는가
- [ ] 비즈니스 단계 경계에 `@Trace` 또는 수동 span을 추가했는가
- [ ] Kafka consumer 처리 루프에 메시지별 span을 감쌌는가

**Monitor / SLO 단계**
- [ ] RED 메트릭(Rate/Errors/Duration)으로 서비스별 SLO를 정의했는가
- [ ] 트래픽 계절성이 있는 지표는 anomaly monitor를 고려했는가
- [ ] 알람 조건이 복합적인 경우 composite monitor로 false positive를 줄였는가
- [ ] Error budget 소진 알람이 설정되어 있는가

**대시보드 단계**
- [ ] 서비스별 "장애 10분 판정용" 대시보드가 있는가
- [ ] Golden Signals, Dependency Health, Infrastructure, Business Metrics 4개 레이어가 한 화면에 있는가

**비용 단계**
- [ ] Tail-based sampling으로 에러/slow trace는 100% 보존, 정상은 저율 샘플링하는가
- [ ] Log Pipeline에 DEBUG / health check exclusion이 적용되어 있는가
- [ ] Custom metric cardinality를 주기적으로 모니터링하는가

**장애 대응 단계**
- [ ] APM alert → Service Map → Error Trace → Deploy Diff → Mitigation 플레이북이 문서화되어 있는가
- [ ] Postmortem Notebook 템플릿이 있는가
- [ ] Feature flag / deploy 이력이 Datadog에 연동되어 있는가
