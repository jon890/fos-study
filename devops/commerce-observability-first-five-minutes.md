# [초안] 커머스/F&B 채널 장애 첫 5분과 관측성 기본기

## 왜 이게 중요한가

커머스나 F&B 디지털 채널은 사용자 경험과 매출이 분 단위로 직결된다. 점심·저녁 피크에 주문 실패가 1%만 튀어도 가맹점·콜센터·SNS로 거의 동시에 신호가 들어오고, 30분이 지나면 일일 매출 지표에 흠집이 남는다. 이때 엔지니어가 가장 자주 실패하는 지점은 "장애가 뭔지 몰라서"가 아니라 **첫 5분 동안 무엇을 보고 무엇을 결정해야 하는지 합의되어 있지 않아서**다.

이 문서는 다음을 목표로 한다.

- 점심·저녁 피크 시간대에 주문/결제 실패가 갑자기 튈 때, 첫 5분에 봐야 할 표면 지표와 깊은 지표의 순서를 고정한다.
- latency / error rate / saturation 의 의미를 커머스/F&B 트래픽 패턴에 맞게 다시 정의한다.
- log·metric·trace 세 가지 신호를 traceId 기반으로 연결하는 최소 설계를 정리한다.
- 알람 임계치를 정적으로 잡았을 때의 함정과 시간대 가중 임계치 전략을 다룬다.
- 인터뷰 답변용으로 후보자의 graceful shutdown 503 해결 경험과 같은 사례 카드를 어떻게 묶어 말해야 하는지 정리한다.

대상 독자는 시니어 백엔드 엔지니어 면접을 준비 중인 사람, 그리고 F&B/커머스 도메인에서 SRE 협업이 필요한 백엔드다. 관련 인접 문서가 이미 있다면(예: [task/ai-service-team/graceful-shutdown-503-fix.md](../task/ai-service-team/graceful-shutdown-503-fix.md)) 사례 본문은 그쪽에 두고 이 문서는 첫 5분 운영 플레이북 + 관측성 기본기 hub 역할로 좁힌다.

## 용어 먼저 — golden signals 4종

본문에 들어가기 전에 이 문서가 반복해서 쓰는 네 가지 지표를 짚어둔다. Google SRE 책이 정의한 **golden signals**로, 시스템 상태를 가장 빠르게 파악하기 위한 4종 표면 지표다.

- **Latency**(지연) — 요청 하나가 응답까지 걸린 시간. "느려졌나"를 본다.
- **Traffic**(처리량) — 단위 시간당 요청 수. "얼마나 들어오나"를 본다.
- **Errors**(오류율) — 실패한 요청의 비율. "지금 터지고 있나"를 본다.
- **Saturation**(포화도) — 리소스가 한계 용량에 얼마나 찼는가. "곧 터질까"를 본다.

앞의 셋은 이미 일어난 현재 상태라 직관적이다. **Saturation만 성격이 다르다.** 아직 터지지 않았지만 곧 터질 상태를 미리 보여주는 선행 지표다. 욕조에 물이 얼마나 찼는지와 같다 — 거의 다 차면 조금만 더 부어도 넘친다.

시스템에서 "물"에 해당하는 것은 다음이다.

- CPU·힙(메모리) 사용률
- DB 커넥션 풀 사용률 (풀 10개가 다 쓰이면 11번째 요청은 대기한다)
- HTTP 클라이언트 풀 (특히 외부 PG 호출용)
- 스레드 풀·큐 깊이

커머스/F&B에서 Saturation을 특히 강조하는 이유는, **CPU와 메모리는 멀쩡한데 커넥션 풀만 꽉 차서** 결제 요청이 커넥션을 받지 못하고 timeout 나는 장애가 흔하기 때문이다. CPU 사용률만 보고 있으면 이 유형은 잡지 못한다.

## 첫 5분에 깨야 하는 잘못된 본능

장애 대응에서 흔한 실패 패턴은 다음 셋이다.

1. **로그부터 grep하기**: 실패가 1초에 수백 건씩 쌓이는 상황에서 로그를 직접 grep으로 뒤지기 시작하면 5분이 지나간다. 로그는 가설 검증 단계에서 쓰는 도구지, 가설 발견 도구가 아니다.
2. **단일 화면만 보기**: APM 한 화면, 또는 PG사 콘솔 한 화면만 본다. 어디까지가 우리 책임이고 어디부터 외부 의존성인지 같은 화면에서 확인되지 않는다.
3. **문제를 좁히기 전에 롤백 결정**: 직전 배포가 떠오른다는 이유로 5분 안에 롤백한다. 외부 PG 장애나 인프라 문제일 때 롤백은 무의미하고, 다음 배포를 더 두렵게 만든다.

이 문제들을 막으려면 첫 5분의 행동이 **사람에 의존하지 않고 대시보드에 의존**해야 한다.

## 첫 5분 플레이북: 0–5분 단계화

다음은 채널 장애 인지 직후 0–5분 동안 한 사람(온콜)이 따라가야 할 순서다. 가능하면 한 화면, 못해도 두 화면 안에 끝나도록 대시보드를 짠다.

### 0–60초: 표면 비즈니스 지표 확인

가장 먼저 확인하는 것은 기술 지표가 아니라 **비즈니스 표면 지표**다. 기술 지표가 깨끗해 보여도 사용자가 결제를 못 하고 있으면 장애다.

봐야 할 1차 패널:

- 분당 주문 시도 수 (order_attempt_per_min)
- 분당 주문 성공 수 (order_success_per_min)
- 주문 실패율 (order_failure_rate = 1 - 성공/시도)
- 결제 승인 실패율 (payment_decline_rate, PG별로 분리)
- 쿠폰/프로모션 적용 오류율 (coupon_error_rate)

판단 기준:

- 주문 시도 자체가 갑자기 떨어졌다면 → 트래픽이 들어오지 못하는 상황(앞단 LB/CDN/앱 크래시 의심).
- 주문 시도는 정상인데 성공만 떨어졌다면 → 우리 서버 또는 외부 의존성(PG/POS/쿠폰엔진).
- 결제 실패율만 튄다면 → PG 의심. 우리 서버 latency는 정상일 수 있음.
- 쿠폰 오류율만 튄다면 → 프로모션 엔진/캐시 문제.

이 단계에서 절대 하지 않는 것: 로그 본문 열기, 코드 의심하기, 누가 무엇을 배포했는지 추적하기. 아직은 표면만 본다.

### 60–180초: 골든 시그널 4종 확인

비즈니스 지표로 "어디 영역인가"를 좁혔다면, 그 영역에 대해 **golden signals**를 본다. Google SRE 책의 latency / traffic / errors / saturation 4종을 커머스/F&B에 맞게 재정의한다.

- **Latency**: 주문 API p50/p95/p99. 평균은 무시한다 — 백분위수가 익숙하지 않으면 [Observability 입문](../architecture/observability-basics.md) 의 "Latency 백분위수" 섹션 먼저. p99가 200ms → 1.2s로 튀는데 평균은 50ms 정도밖에 안 움직이는 일이 흔하다.
- **Traffic**: 분당 요청 수. 단순 RPS가 아니라 **결제까지 도달한 요청 수**가 더 의미 있다. 장바구니 RPS는 정상인데 결제 RPS만 빠질 수 있다.
- **Errors**: HTTP 5xx, 4xx, 그리고 우리 도메인 에러 코드 셋. 4xx 중 401/409/422는 사용자 측 문제로 보일 수 있어도 인증/재고 락/검증 실패 등 서버 이슈일 수 있다.
- **Saturation**: CPU, 힙 사용률, DB 커넥션 풀 사용률, 외부 호출 큐 깊이. 특히 **커넥션 풀 saturation**이 결제 실패의 가장 흔한 숨은 원인이다.

이 시점에서 답이 나와야 하는 질문은 한 가지다.

> "지금 실패가 우리 코드/리소스 문제인가, 외부 의존성 문제인가?"

p99 latency가 외부 호출(예: PG 호출) 구간에서만 튀고 우리 서버 saturation은 깨끗하다면 외부 의존성 쪽이다. 반대로 saturation이 함께 차오르면 우리 쪽이 받아내지 못하는 상태다.

### 180–300초: 의존성·배포 이력·트레이스 확인

지금까지의 정보를 가지고 의심 영역을 한 곳으로 좁힌다.

- 외부 의존성 의심 → PG/POS/쿠폰엔진 별 호출 성공률·latency 패널을 본다. circuit breaker가 열렸는지, retry storm이 발생하고 있는지 확인한다.
- 우리 서버 의심 → 직전 30분/2시간/24시간 배포 이벤트를 표시한 패널을 본다. 배포 직후 지표가 꺾였다면 후보 1순위는 그 배포다.
- 인프라 의심 → 노드 교체 이벤트, 오토스케일 이벤트, 네트워크 지표(연결 reset 비율)를 본다.

이 단계에서 비로소 **trace**를 연다. 실패한 주문 1건의 traceId를 잡아 전체 호출 그래프를 본다. 처음부터 trace를 열지 않는 이유는, 단일 요청이 전체 장애를 대표한다고 보장할 수 없기 때문이다. metric으로 "어떤 segment가 느린지"를 좁힌 뒤 trace로 "왜 느린지"를 본다.

5분이 끝나는 시점에는 다음 셋 중 하나를 결정한다.

- **격리**: 외부 의존성 차단(circuit breaker 강제 open), 일부 채널/지점 트래픽 분리.
- **롤백**: 직전 배포가 명백한 후보일 때만.
- **확장**: saturation이 명백하고 외부 의존성은 깨끗할 때 노드/풀 확장.

판단이 안 서면 "관측성을 더 켜는 결정"을 한다 — 임시 로그 레벨 상승, 샘플링률 100% 상승. 단 이 결정 자체도 5분 안에 한다.

## golden signals 재정의: 커머스/F&B 관점

일반적인 골든 시그널 정의를 그대로 가져오면 도메인 특성이 빠진다. 커머스/F&B에서는 다음과 같이 다시 정의해 두는 것이 좋다.

### Latency

- 단일 API의 latency보다 **사용자 여정 latency**가 더 중요하다. "메뉴 조회 → 장바구니 → 주문 → 결제 → 영수증" 한 사이클이 30초 안에 끝나야 한다는 식의 SLO를 둔다.
- p99 외에 **p99.9**까지 보는 것을 추천한다. 점심 피크에 분당 1만 건 주문이라면 p99만 봐도 매분 100건이 느린 사용자다.
- 외부 호출 latency는 우리 latency와 분리해 둔다. 같은 latency 패널에 섞으면 외부 PG 지연이 있을 때 "우리 서버가 느리다"고 오인한다.

### Traffic

- 단순 RPS가 아니라 **funnel 단계별 RPS**를 본다. 메뉴 조회 RPS, 장바구니 추가 RPS, 결제 시도 RPS, 결제 성공 RPS.
- 장애 시 funnel의 어느 단계에서 깔때기가 막혔는지로 영역이 좁혀진다. 결제 시도는 정상인데 결제 성공만 빠진다면 PG 또는 트랜잭션 처리 영역.

### Errors

- HTTP 상태 코드만으로는 부족하다. 도메인 에러 코드를 metric label로 노출한다.
  - `OUT_OF_STOCK`, `COUPON_INVALID`, `PG_DECLINED`, `PG_TIMEOUT`, `IDEMPOTENCY_CONFLICT` 등.
- 5xx만 알람을 거는 함정에 빠지지 않는다. 결제 실패는 종종 200 응답에 본문 status 필드만 FAIL로 내려온다.

### Saturation

- 커머스/F&B 트래픽은 **분 단위 스파이크**가 본질이다. 10분 평균 CPU가 60%여도 매 분 첫 10초만 95%면 사용자에게는 latency 스파이크로 느껴진다.
- DB 커넥션 풀, HTTP 클라이언트 풀, 스레드 풀, 큐 깊이를 모두 본다. 가장 흔한 숨은 saturation은 **외부 PG 호출용 HTTP 커넥션 풀**이다.

## log / metric / trace를 traceId로 묶기

세 신호를 따로따로 운영하면 첫 5분에 절대 답이 안 나온다. 최소한 다음 두 가지 규칙은 코드 베이스에 박혀 있어야 한다.

### 규칙 1: 모든 요청에 traceId가 있다

진입 단계(API Gateway 또는 첫 번째 서버)에서 traceId를 생성하거나 inbound header(`traceparent`, `X-Request-ID`)에서 받아 그대로 전파한다. 모든 외부 호출, 모든 로그, 모든 metric exemplar에 같은 traceId가 붙는다.

Spring Boot 기준 최소 구현 예:

```java
@Component
public class TraceIdFilter extends OncePerRequestFilter {
    private static final String HEADER = "X-Request-ID";
    private static final String MDC_KEY = "traceId";

    @Override
    protected void doFilterInternal(HttpServletRequest req,
                                    HttpServletResponse res,
                                    FilterChain chain) throws ServletException, IOException {
        String traceId = req.getHeader(HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = UUID.randomUUID().toString().replace("-", "");
        }
        MDC.put(MDC_KEY, traceId);
        res.setHeader(HEADER, traceId);
        try {
            chain.doFilter(req, res);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }
}
```

logback 패턴에 `%X{traceId}`를 박아 두면, 이후 어떤 로그를 검색해도 traceId 한 개로 한 사용자 요청 흐름을 복원할 수 있다.

### 규칙 2: 도메인 이벤트마다 구조화 로그를 남긴다

장애 시 grep할 게 아니라, 검색 가능한 필드를 미리 박아 둔다.

```java
log.info("order_attempt {} {} {} {} {}",
    kv("order_id", orderId),
    kv("user_id", userId),
    kv("store_id", storeId),
    kv("amount", amount),
    kv("payment_method", method));
```

JSON 로그로 쌓고 `order_id`, `store_id`, `payment_method` 같은 필드를 인덱싱하면, 첫 5분 안에 "강남점에서만 결제가 실패한다"는 사실을 한 줄 쿼리로 잡을 수 있다.

### 규칙 3: metric에 exemplar로 traceId 붙이기

Prometheus / OpenTelemetry는 metric 데이터 포인트에 exemplar를 붙일 수 있다. p99 latency가 튄 시점의 exemplar를 클릭하면 바로 그 요청의 trace로 점프한다. metric → trace 점프가 1클릭으로 되면 첫 5분 분석 비용이 크게 떨어진다.

## bad vs improved: 흔히 보는 안티패턴

### 안티패턴 1: 평균 latency 알람

```
alert: order_api_avg_latency > 500ms
```

평균은 long-tail을 가린다. 1만 요청 중 100건이 5초여도 평균은 별로 안 움직인다.

개선:

```
alert: histogram_quantile(0.99, order_api_latency_bucket) > 1s for 3m
alert: histogram_quantile(0.999, order_api_latency_bucket) > 3s for 3m
```

`for 3m`을 둬서 단발 스파이크에 깨우지 않는다.

### 안티패턴 2: 24시간 고정 임계치

심야에는 분당 10건만 들어와도 정상이고, 점심 피크에는 분당 5천 건이 정상이다. 같은 임계치를 쓰면 둘 다 잘못 운다.

개선: **동시간대 baseline 대비 편차**를 본다.

```
alert: order_failure_rate
       > 1.5 * avg_over_time(order_failure_rate[7d] @ same_time_of_day)
```

또는 단순하게라도 시간대별 임계치 테이블(점심/저녁/심야)을 두 개 이상 둔다.

### 안티패턴 3: 5xx만 알람

PG 응답이 200 OK + body status FAIL로 오는 경우를 놓친다. 결제 실패는 비즈니스 metric(`payment_decline_rate`)에 별도 알람을 건다.

### 안티패턴 4: 한 사람 머릿속의 첫 5분

플레이북이 위키에만 있고 알람 본문에 없으면, 새벽 3시에 깨어난 사람은 못 따라간다. 알람 메시지에 다음을 박는다.

- 직접 클릭 가능한 대시보드 링크
- "지금 0–60초에 볼 패널" 라벨
- 비상 연락 채널과 의사결정 권한자

## graceful shutdown 503 사례를 첫 5분 흐름과 묶기

후보자 프로필에 들어 있는 graceful shutdown 503 해결 경험은 첫 5분 플레이북과 직접 연결된다. 사례를 다음 흐름으로 재구성하면 인터뷰 답변이 자연스럽다.

1. **표면 신호**: 배포 직후 `5xx_rate`가 분당 수십 건씩 튐. 트래픽이나 비즈니스 KPI는 정상. → 우리 쪽 문제.
2. **golden signal**: latency는 정상, error만 튐. 패턴이 배포와 정확히 정렬됨.
3. **trace**: 실패 요청들이 모두 종료 중인 인스턴스로 가서 connection reset.
4. **원인**: LB가 graceful shutdown 시작 직후에도 새 트래픽을 보내고 있었음. readiness/preStop과 종료 sequence가 어긋남.
5. **조치**: preStop hook에서 readiness를 먼저 false로 만들고 LB drain 시간을 확보. 동시에 in-flight 요청은 정상 처리.
6. **검증**: 같은 배포 시나리오에서 `5xx_rate` 스파이크가 사라짐. 이후 알람에 "배포 직후 30초 5xx 스파이크" 패턴을 별도 알람으로 추가.

이 답변이 인터뷰에서 강한 이유는 "장애를 풀었다"가 아니라 "관측성·플레이북 자체를 영구적으로 개선했다"까지 들어가기 때문이다.

## 로컬 실습 환경: docker-compose로 첫 5분 시뮬레이션

면접 직전에도 빠르게 손에 익히려면 다음 4개 컨테이너로 충분하다.

```yaml
version: "3.9"
services:
  app:
    image: openjdk:21-slim
    working_dir: /app
    command: ["java", "-jar", "/app/order-app.jar"]
    volumes:
      - ./build:/app
    ports: ["8080:8080"]
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel:4318
      OTEL_SERVICE_NAME: order-app

  otel:
    image: otel/opentelemetry-collector:0.103.0
    command: ["--config=/etc/otel.yaml"]
    volumes:
      - ./otel.yaml:/etc/otel.yaml
    ports: ["4318:4318"]

  prometheus:
    image: prom/prometheus:v2.55.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:11.2.0
    ports: ["3000:3000"]
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
```

prometheus.yml에서 `app:8080/actuator/prometheus`를 스크랩하고, Grafana에 Prometheus를 연결한 뒤 다음 패널을 만든다.

- 분당 `order_attempt_total` rate
- 분당 `order_success_total` rate
- `1 - rate(order_success_total[1m]) / rate(order_attempt_total[1m])` (실패율)
- p99: `histogram_quantile(0.99, sum by (le) (rate(http_server_requests_seconds_bucket[1m])))`
- DB 커넥션 풀 사용률(HikariCP의 `hikaricp_connections_active`)

부하는 k6로 흘린다.

```javascript
import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    lunch_peak: {
      executor: "ramping-arrival-rate",
      startRate: 50, timeUnit: "1s",
      preAllocatedVUs: 200,
      stages: [
        { target: 200, duration: "30s" },
        { target: 800, duration: "1m" },
        { target: 800, duration: "2m" },
        { target: 100, duration: "30s" },
      ],
    },
  },
};

export default function () {
  const res = http.post("http://localhost:8080/orders",
    JSON.stringify({ storeId: "S001", amount: 12000 }),
    { headers: { "Content-Type": "application/json" } });
  check(res, { "ok": (r) => r.status === 200 });
}
```

이 상태에서 의도적으로 실패를 주입한다. 예: 앱 안에 PG mock을 두고 30% 확률로 200ms\~1.5s 지연 + `PG_DECLINED` 응답을 내린다. 그러면 Grafana에서 latency p99와 실패율이 어떻게 움직이는지, 평균 latency는 얼마나 둔감한지 직접 볼 수 있다.

## 실행 가능한 미니 코드: 의도적 PG 지연 주입

```java
@RestController
@RequestMapping("/orders")
public class OrderController {

    private final Random rnd = new Random();
    private final Counter attempt;
    private final Counter success;
    private final Counter declined;

    public OrderController(MeterRegistry reg) {
        this.attempt  = reg.counter("order_attempt_total");
        this.success  = reg.counter("order_success_total");
        this.declined = reg.counter("order_decline_total", "reason", "PG_DECLINED");
    }

    @PostMapping
    public ResponseEntity<?> create(@RequestBody OrderReq req) throws InterruptedException {
        attempt.increment();
        // 의도적 지연
        long sleep = rnd.nextInt(200);
        if (rnd.nextDouble() < 0.05) sleep += 1200; // long-tail 5%
        Thread.sleep(sleep);

        if (rnd.nextDouble() < 0.30) {
            declined.increment();
            return ResponseEntity.ok(Map.of("status", "FAIL", "reason", "PG_DECLINED"));
        }
        success.increment();
        return ResponseEntity.ok(Map.of("status", "OK"));
    }
}
```

이 단순한 코드만으로도 "200 OK 안에 status FAIL이 섞여 있을 때 5xx 알람만 보면 어떻게 되는지"를 즉시 체감할 수 있다.

## 사후 회고(postmortem) 최소 템플릿

첫 5분 운영을 잘하는 팀은 사후 회고 양식이 단순하다. 길지 않게 다음 항목만 채운다.

- 발생 시각 / 인지 시각 / 완화 시각 / 종료 시각
- 사용자 영향(주문 실패 건수, 결제 실패 건수, 영향 매장 수)
- 표면 신호와 그 신호를 처음 본 사람
- 첫 5분 동안의 의사결정 타임라인
- 근본 원인(코드/설정/외부)
- 재발 방지: 알람·플레이북·코드·테스트 4가지 카테고리에서 각각 항목 추가
- 잘된 점: 칭찬을 명시한다. 다음 사람이 같은 행동을 반복하게 한다.

비난이 아니라 시스템 개선으로 끝나야 한다. "사람이 늦게 알아챘다"가 결론이면, 그건 알람이 잘못 잡혀 있다는 뜻이다.

## 인터뷰 답변 프레임

면접에서 "장애 대응 경험을 말해 보세요" 같은 질문이 나오면 다음 4단 구조를 권한다.

1. **표면**: 어떤 비즈니스 지표가 어떻게 움직였는지부터 말한다. ("분당 결제 실패율이 0.3%에서 4%로 튀었습니다.")
2. **좁히기**: golden signal로 영역을 어떻게 좁혔는지. ("우리 서버 latency와 saturation은 정상이었고, PG 호출 segment의 p99만 튀고 있었습니다.")
3. **결정**: 격리·롤백·확장 중 무엇을 왜 골랐는지. ("외부 의존성 의심이 강해 PG 우회 경로 쪽 트래픽 비중을 30%로 올렸습니다.")
4. **영구 개선**: 알람·플레이북·코드 중 무엇을 바꿨는지. ("이후 PG별 호출 latency·실패율 패널과 알람을 분리했고, circuit breaker 임계치를 시간대별로 다르게 잡도록 했습니다.")

graceful shutdown 503 사례는 위 4단에 정확히 매핑된다. 후보자가 답할 때는 "장애를 빨리 풀었다"보다 **"같은 종류의 장애가 다시 일어나지 않도록 관측성과 배포 sequence를 영구적으로 바꿨다"**를 강조한다.

다음과 같은 follow-up도 미리 준비한다.

- "그 알람이 너무 자주 울렸다면 어떻게 튜닝했겠습니까?" → 시간대 baseline + multi-window multi-burn-rate.
- "트래픽이 적은 시간대에는 골든 시그널이 의미가 있습니까?" → 분모가 작을 때는 비율 알람 대신 절대 건수 알람으로 바꾼다.
- "log·metric·trace 중 하나만 가져갈 수 있다면?" → metric. 가장 싸고 가장 빨리 영역을 좁힌다. 단 traceId가 metric exemplar로 붙어 있다는 전제 위에서.

## 점검 리스트

운영 중인 서비스에 다음이 박혀 있는지 한 줄씩 체크한다.

- [ ] 모든 inbound 요청에 traceId가 생성/전파된다.
- [ ] 모든 로그 라인에 traceId가 들어간다(`%X{traceId}`).
- [ ] 도메인 에러 코드가 metric label로 노출된다.
- [ ] 비즈니스 funnel(시도/성공/실패) metric이 분 단위로 그려진다.
- [ ] 외부 의존성(PG/POS/쿠폰) latency·실패율 패널이 우리 서버 패널과 분리되어 있다.
- [ ] DB 커넥션 풀/HTTP 클라이언트 풀 saturation 패널이 있다.
- [ ] p99 / p99.9 latency 알람이 평균 latency 알람을 대체했다.
- [ ] 알람 임계치가 시간대별로 다르거나 baseline 대비로 잡혀 있다.
- [ ] 알람 메시지에 대시보드 링크와 첫 5분 행동 순서가 박혀 있다.
- [ ] 직전 30분/2시간/24시간 배포 이벤트가 대시보드 위에 오버레이된다.
- [ ] metric exemplar로 metric → trace 1클릭 점프가 가능하다.
- [ ] 사후 회고 템플릿이 4영역(알람/플레이북/코드/테스트) 개선을 강제한다.
- [ ] graceful shutdown / readiness / preStop drain 시간이 LB 설정과 정합된다.
- [ ] PG 응답이 200 OK + body FAIL인 경우를 별도 알람으로 잡는다.
- [ ] 점심·저녁 피크의 baseline traffic·실패율을 누구나 같은 화면에서 본다.

이 리스트의 90% 이상이 yes면, 첫 5분에 사람이 아니라 대시보드가 답을 가르쳐 준다.

## 2026-05-19 CJ푸드빌 부트캠프 보강 — 피크타임 장애 알림 기준

F&B 디지털 채널의 장애 대응은 평균 지표보다 피크타임 변화율이 중요하다. 점심 12시, 저녁 18시, 이벤트 쿠폰 오픈 직후에는 정상 트래픽 자체가 급증하므로 단순 요청 수 알림은 노이즈가 되고, 실패율·지연·외부 의존성별 분리가 핵심 신호가 된다.

첫 5분 대시보드에는 다음 패널을 고정한다.

- 주문 시도/성공/실패율: 앱, 웹, POS 연동, 배달 연동 채널별로 분리한다.
- 결제 승인 실패율: PG사, 카드사 응답코드, timeout, 우리 서버 5xx를 나눈다.
- 쿠폰 적용 실패율: 정책 불일치, 이미 사용됨, 재고 소진, 내부 오류를 분리한다.
- POS/매장 연동 지연: 접수 지연 p95/p99와 미접수 주문 수를 같이 본다.
- Outbox backlog: 발행 대기 건수와 oldest age를 함께 본다.
- CS 신호: 동일 에러 코드 문의 증가, SNS/리뷰 유입, 매장 전화 증가를 운영 채널과 연결한다.

알림 기준은 “5분 이동 실패율이 평소 동일 요일/시간대 대비 2배 이상 + 절대 실패 건수 N건 이상”처럼 비율과 건수를 함께 둔다. 장애 종료 후 postmortem에는 감지 시각, 사용자 영향 범위, 매출/주문 영향, 원인, 완화 조치, 재발 방지 액션, 대시보드/알림 보강 항목을 반드시 남긴다. 면접에서는 “롤백 여부를 직전 배포 감이 아니라 비즈니스 지표와 dependency split으로 결정했다”고 말하는 것이 좋다.
