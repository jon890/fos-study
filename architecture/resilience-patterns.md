# [초안] 시니어 백엔드를 위한 Resilience 패턴 실전 가이드 — Timeout, Retry, Circuit Breaker, Bulkhead, Backpressure

## 왜 이 주제가 중요한가

분산 시스템에서 "실패하지 않는 서비스"는 존재하지 않는다. 우리가 만드는 모든 API는 항상 다음 네 가지 실패 모델에 노출되어 있다.

- **업스트림 실패**: 내가 호출하는 외부 API / 내부 마이크로서비스가 느려지거나 죽는다. p99가 평소 120ms인데 갑자기 8초로 튄다.
- **다운스트림 실패**: 내가 의존하는 DB, Redis, Kafka가 커넥션 한도를 넘기거나 특정 키의 hot partition 때문에 응답을 못 준다.
- **네트워크 실패**: TCP RST, DNS 조회 지연, LB의 idle timeout, VPC peering 구간의 packet loss. 애플리케이션은 정상인데 패킷이 못 돌아오는 상황이다.
- **GC / 자원 고갈 실패**: 본인 JVM의 Full GC로 수백 ms~수 초 멈춤, 스레드풀 고갈, 파일 디스크립터 한도, 커넥션풀 고갈.

실패는 "예외 케이스"가 아니라 "항상 일정 확률로 일어나는 사건"이다. 시니어 백엔드 엔지니어의 역할은 **"실패가 발생했을 때 전파를 어디에서 끊을 것인가"** 를 설계하는 것이다. 한 다운스트림의 지연이 내 스레드풀을 다 먹어치우고, 그것이 업스트림의 SLA를 깨뜨리고, 결국 전체 플랫폼이 시나리오 그대로 죽는 **cascading failure**를 막는 것이 핵심이다.

면접에서 "외부 API가 느려지면 어떻게 대응하시나요?" 라는 질문은 사실상 **Timeout → Retry → Circuit Breaker → Bulkhead → Fallback → Backpressure → Graceful Shutdown** 의 스택을 차례로 이해하고 있느냐는 질문이다. 이 문서는 그 전체 스택을 실행 가능한 수준으로 정리한다.

## 핵심 개념: Resilience 패턴 스택

| 계층 | 목적 | 실패 시 효과 |
| --- | --- | --- |
| Timeout | 응답이 오지 않는 호출을 일정 시간 후 포기 | 스레드 / 커넥션 반납, 자원 회수 |
| Retry | 일시적 실패를 자동 재시도 | 가용성 향상 (단, 폭주 위험) |
| Circuit Breaker | 지속적으로 실패하는 대상을 빠르게 차단 | 빠른 실패 + 복구 프로브 |
| Bulkhead | 자원을 격리해서 한 영역의 고갈이 다른 영역을 못 건드리게 | 부분 실패로 제한 |
| Fallback | 실패 시 대체 응답 제공 | 사용자 경험 유지 |
| Backpressure | 유입 속도를 처리 속도에 맞춤 | 큐 폭주 방지 |
| Graceful Shutdown | 배포·축소 시 in-flight 보존 | 5xx 최소화 |

이 스택은 "아무거나 다 붙이면 된다" 가 아니라 **"계층적 조합을 잘못 짜면 오히려 장애를 확대시킨다"** 는 점이 중요하다. 특히 Timeout과 Retry는 Circuit Breaker 없이 붙이면 재시도 폭주(retry storm)를 유발한다.

## 1. Timeout: 모든 Resilience의 출발점

Timeout이 없는 호출은 resilience 전략의 대상이 될 수 없다. "언제 실패로 간주할 것인가" 가 정의되지 않았기 때문이다.

Timeout은 보통 세 계층으로 구분한다.

- **Connection Timeout**: TCP 핸드셰이크가 완료되기까지 기다릴 시간. 보통 1~3초.
- **Read Timeout (Socket Timeout)**: 연결된 소켓에서 바이트가 도착하는 최대 대기 시간. 보통 p99의 2~3배.
- **Call Timeout (Request Timeout)**: 요청 시작부터 응답 완료까지 전체 시간. retry 포함 여부를 고려해서 설계.

### Java HTTP Client 예시 (JDK HttpClient)

```java
HttpClient client = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(2))
    .version(HttpClient.Version.HTTP_2)
    .build();

HttpRequest req = HttpRequest.newBuilder()
    .uri(URI.create("https://inventory.internal/api/v1/stock"))
    .timeout(Duration.ofSeconds(1))  // read + 전체 응답 대기
    .GET()
    .build();
```

JDK HttpClient는 `connectTimeout`과 request의 `timeout`만 제공한다. Read timeout을 따로 세밀 조정하고 싶다면 Netty 기반 클라이언트(Reactor Netty, OkHttp)를 쓴다.

### JDBC / HikariCP

```yaml
spring:
  datasource:
    hikari:
      connection-timeout: 3000      # 풀에서 커넥션 얻기까지 대기 (ms)
      validation-timeout: 1000
      max-lifetime: 1800000
      idle-timeout: 600000
      maximum-pool-size: 20
```

추가로 JDBC URL 옵션에 socket timeout을 반드시 걸어준다. MySQL 기준:

```
jdbc:mysql://db:3306/app?connectTimeout=2000&socketTimeout=3000&useSSL=true&serverTimezone=Asia/Seoul
```

`socketTimeout`이 없으면 네트워크 장애 시 커넥션이 영원히 블로킹되어 커넥션풀이 즉시 고갈된다. 장애 사례 중 가장 흔한 패턴이다.

### Lettuce (Redis)

```java
ClientOptions options = ClientOptions.builder()
    .timeoutOptions(TimeoutOptions.enabled(Duration.ofMillis(200)))
    .socketOptions(SocketOptions.builder()
        .connectTimeout(Duration.ofSeconds(1))
        .keepAlive(true)
        .build())
    .disconnectedBehavior(DisconnectedBehavior.REJECT_COMMANDS)
    .build();
```

Redis는 응답이 매우 빠르기 때문에 timeout을 짧게(수십~수백 ms) 잡아야 한다. 길게 잡으면 Redis 한 번의 네트워크 지연에 내 스레드가 통째로 물린다.

## 2. Retry: 멱등성과 백오프가 전부다

Retry는 강력하지만 잘못 쓰면 장애를 직접 만든다. 세 가지 전제를 반드시 확인한다.

1. **멱등성(idempotency) 이 보장되는가?** GET / PUT / DELETE는 보통 안전하다. POST는 요청에 idempotency key를 심어야 재시도 가능하다.
2. **실패의 성격이 일시적(transient) 인가?** 4xx(특히 400, 401, 403, 404, 422)는 재시도해도 똑같다. 재시도 대상은 5xx, timeout, connection reset 정도.
3. **지수 백오프 + jitter 를 쓰는가?** 고정 간격 재시도는 전체 클라이언트가 동시에 재시도하는 thundering herd를 만든다.

### Resilience4j Retry 설정

```java
RetryConfig config = RetryConfig.custom()
    .maxAttempts(3)
    .intervalFunction(IntervalFunction.ofExponentialRandomBackoff(
        /* initialInterval */ Duration.ofMillis(100),
        /* multiplier */     2.0,
        /* randomizationFactor */ 0.5))
    .retryOnException(ex ->
        ex instanceof IOException
            || ex instanceof TimeoutException
            || (ex instanceof HttpServerErrorException hse
                && hse.getStatusCode().is5xxServerError()))
    .failAfterMaxAttempts(true)
    .build();

Retry retry = Retry.of("inventoryApi", config);
```

### Retry Storm 방지

재시도는 **trunk(끝단) 한 곳에서만** 돌리는 것이 원칙이다. A→B→C 호출 체인에서 A, B, C 모두가 각자 3번씩 재시도하면 총 호출은 27배가 된다. 업스트림 장애는 이 순간 끝장난다.

규칙:

- 재시도는 **가장 바깥 layer 또는 가장 안쪽 layer 한 곳** 에서만.
- 재시도 횟수 × 시도당 timeout 이 **상위 call timeout을 초과하면 안 된다**.
- 재시도 예산(retry budget) 을 둬서, 전체 요청 중 재시도 비율이 10% 를 넘으면 재시도 자체를 중단한다.

## 3. Circuit Breaker: 빠른 실패와 자가 복구

Circuit Breaker는 "지속적으로 실패하는 대상을 일정 기간 차단해서, 의미 없는 호출을 빠르게 실패시키는" 장치다. 세 상태를 갖는다.

- **Closed**: 평소 상태. 호출을 그대로 통과시키면서 실패율을 측정한다.
- **Open**: 실패율 임계값을 넘으면 회로 열림. 모든 호출을 즉시 실패 처리(CallNotPermittedException). 스레드는 기다리지 않는다.
- **Half-Open**: 일정 시간 후 제한된 수의 프로브 호출만 허용. 성공하면 Closed, 실패하면 다시 Open.

### Resilience4j 설정

```java
CircuitBreakerConfig config = CircuitBreakerConfig.custom()
    .slidingWindowType(SlidingWindowType.COUNT_BASED)
    .slidingWindowSize(50)
    .minimumNumberOfCalls(20)
    .failureRateThreshold(50.0f)            // 50% 이상 실패 시 open
    .slowCallRateThreshold(80.0f)
    .slowCallDurationThreshold(Duration.ofSeconds(1))
    .waitDurationInOpenState(Duration.ofSeconds(10))
    .permittedNumberOfCallsInHalfOpenState(5)
    .automaticTransitionFromOpenToHalfOpenEnabled(true)
    .recordExceptions(IOException.class, TimeoutException.class)
    .ignoreExceptions(BusinessValidationException.class)
    .build();

CircuitBreaker cb = CircuitBreaker.of("inventoryApi", config);

Supplier<Stock> decorated = CircuitBreaker
    .decorateSupplier(cb, () -> inventoryClient.getStock(sku));
```

핵심은 `ignoreExceptions` 설정이다. 비즈니스 예외(예: "재고 없음")는 시스템 실패가 아니므로 실패율 계산에 포함하면 안 된다. 이걸 놓치면 정상 동작 중에도 회로가 열린다.

### 서킷과 Retry의 조합 순서

Resilience4j의 데코레이션 순서는 **바깥쪽이 먼저 실행**된다. 일반적으로 권장되는 순서:

```
Bulkhead → TimeLimiter → CircuitBreaker → Retry → 실제 호출
```

즉 가장 안쪽에 Retry, 그 바깥에 CircuitBreaker. 이렇게 해야 Retry가 열린 회로를 계속 때리지 않는다. 반대로 두면 Retry가 서킷을 넘어서 계속 재시도를 시도하게 된다.

## 4. Bulkhead: 자원 격리로 blast radius 줄이기

Bulkhead는 배의 격벽에서 따온 이름이다. 한 부분이 침수되어도 전체가 가라앉지 않도록 **자원을 물리적으로 격리**한다.

전형적인 실패 사례: Tomcat default worker thread가 200인데, 이 중 190개가 느려진 결제 API 호출로 블록되어 있으면, 빠르게 끝나야 할 상품 조회 API도 나머지 10개 쓰레드로 처리해야 한다. 결국 상품 조회까지 장애로 전파된다.

### 스레드풀 격리 (Semaphore / ThreadPool Bulkhead)

```java
ThreadPoolBulkheadConfig tpCfg = ThreadPoolBulkheadConfig.custom()
    .maxThreadPoolSize(20)
    .coreThreadPoolSize(10)
    .queueCapacity(50)
    .build();

ThreadPoolBulkhead paymentBulkhead =
    ThreadPoolBulkhead.of("paymentApi", tpCfg);
```

결제 API 전용 스레드풀을 따로 둬서, 결제 장애가 전체 tomcat worker를 잠식하지 않게 한다.

또는 Spring WebFlux / reactive 환경에서는 `Schedulers.newBoundedElastic(...)` 을 도메인별로 분리해서 같은 효과를 낸다.

### 커넥션풀 격리

- 주 DB 쓰기용 / 읽기 복제용 / 배치용 HikariCP를 각각 분리
- Redis 캐시용 / Redis 세션용 Lettuce 클라이언트 분리
- 외부 API 클라이언트는 호출 대상별로 connection pool 분리 (Apache HttpClient `PoolingHttpClientConnectionManager` 의 route별 제한 활용)

### 실제 장애 사례 패턴

"쇼핑몰 홈 API가 추천 서비스 호출이 느려지자 전체 홈이 3초 이상 지연됨"이라는 장애는 bulkhead 부재의 전형이다. 홈 컴포지션에서 추천을 **독립 스레드풀 + 200ms timeout + 서킷** 으로 감싸고, 실패 시 **"인기 상품 캐시"** 로 fallback하면 추천 API가 죽어도 홈은 정상 응답한다.

## 5. Fallback 전략

Fallback은 "실패를 숨기는 것"이 아니라 "실패했을 때 무엇을 보여줄 것인가" 에 대한 제품 결정이다.

- **캐시 fallback**: 직전에 성공한 응답을 Redis / Caffeine에 TTL 길게 저장. 조회 실패 시 stale cache 반환.
- **기본값 fallback**: "이 상품의 리뷰 평균"을 못 가져오면 "평점 정보 없음"으로 표시.
- **축약 응답(degraded mode)**: 추천/개인화 영역을 빼고 기본 상품 카드만 내려주기.
- **비동기 처리로 대체**: 동기 호출이 실패하면 Kafka / SQS에 이벤트를 쌓고 "요청이 접수되었습니다" 응답. 결제 웹훅, 포인트 적립 등에 활용.

```java
Supplier<Recommendations> recoCall = () -> recoClient.get(userId);
Supplier<Recommendations> withFallback = () -> {
    try {
        return CircuitBreaker.decorateSupplier(cb, recoCall).get();
    } catch (Exception e) {
        meterRegistry.counter("reco.fallback").increment();
        return popularCache.getOrDefault(category, Recommendations.empty());
    }
};
```

Fallback은 **항상 메트릭으로 측정**해야 한다. "Fallback으로 응답했다"는 곧 사용자에게 열화된 경험을 줬다는 뜻이기 때문에, fallback rate는 SLO의 핵심 지표가 된다.

## 6. Backpressure: 유입을 처리 속도에 맞추기

Resilience는 "실패 처리"뿐 아니라 "과부하를 받지 않기" 이기도 하다. 서버가 처리 속도보다 빠르게 요청을 받으면 큐가 무한히 쌓이고, 결국 OOM이나 전체 지연으로 이어진다.

### 블로킹 환경에서의 backpressure

- Tomcat `server.tomcat.accept-count`, `max-connections`, `max-threads`를 유한하게 잡는다.
- 애플리케이션 레벨 Semaphore로 동시 처리 수를 제한한다.
- 큐가 꽉 차면 **429 Too Many Requests** 또는 **503 Service Unavailable + Retry-After** 를 반환한다. 큐에 쌓아두지 않는다.

### 리액티브 환경

Project Reactor의 `Flux.onBackpressureBuffer(maxSize, overflowStrategy)`, `limitRate(prefetch)` 등으로 producer → consumer 간 요청 속도를 제어한다.

```java
Flux.from(incoming)
    .onBackpressureBuffer(1000, BufferOverflowStrategy.DROP_OLDEST)
    .limitRate(100)
    .flatMap(this::handle, /* concurrency */ 32)
    .subscribe();
```

### 상태 코드 의미 복습

- **429**: "너의 rate limit 초과". 클라이언트가 지수 백오프로 재시도해야 함.
- **503**: "지금 서버가 과부하/점검". 가능하면 `Retry-After` 헤더 동반.
- **502 / 504**: 게이트웨이 관련. 대개 업스트림 장애 또는 타임아웃 문제로, 내 서비스가 아니라 중간 프록시 이슈일 수 있음.

이 구분은 면접에서 "429와 503의 차이는?" 으로 자주 나온다. 핵심은 **"누구의 책임인가"** 다. 429는 클라이언트 책임, 503은 서버 측 일시 상태.

## 7. 계층적 조합 설계 원칙 (cascading failure 방지)

개별 패턴보다 훨씬 중요한 것이 이들의 조합 규칙이다.

1. **Timeout 예산(timeout budget) 원칙**: 상위 호출의 timeout이 하위 호출 timeout 합보다 커야 한다. 프론트 → API → 결제 → PG 4단 호출에서, API 단에서 3초로 잡아놓고 PG에 5초 타임아웃을 걸면 API는 무조건 먼저 끊긴다. 이때 결제는 PG에는 계속 보내지만 API는 실패로 응답하므로 **"돈은 빠졌는데 주문은 실패"** 같은 일관성 사고가 난다.
2. **재시도는 한 layer에서만**: 전체 스택 중 가장 가까운 한 지점에서만 재시도한다. 그 외 layer는 실패를 그대로 전파한다.
3. **CB는 재시도 바깥**: Retry는 CircuitBreaker 안쪽에서 실행되어야 open 상태를 존중한다.
4. **Bulkhead는 가장 바깥**: 리소스 격리는 모든 내부 로직을 감싸야 의미가 있다.
5. **Fallback은 명시적**: silent fallback 금지. 항상 메트릭과 로그 한 줄이 있어야 한다.
6. **Deadline propagation**: gRPC의 deadline 처럼, 상위에서 남은 시간을 하위로 전파한다. 자체 구현 시 `X-Deadline-Ms` 헤더로 넘긴다.

## 8. Graceful Shutdown: 배포 중에 500을 찍지 않는 법

후보자 경험(오리진 처리 시스템, 쿠팡·NHN 트래픽 운영)에서 가장 자주 마주치는 이슈 중 하나다. 배포·오토스케일 축소 때 in-flight 요청을 중간에 끊으면 사용자는 500을 본다.

### Spring Boot 2.3+ 내장 Graceful Shutdown

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

이 설정만으로 Spring은 SIGTERM을 받으면:

1. Tomcat / Undertow connector가 새 요청 수락을 중단
2. 이미 받아둔 요청을 30초까지 완료 대기
3. 타임아웃 후 강제 종료

### Kubernetes 조합

그런데 Spring 혼자서는 부족하다. 이유는 K8s의 iptables / kube-proxy가 Pod를 **Endpoints에서 제거하는 시점** 과 **Pod에 SIGTERM을 보내는 시점** 이 병렬이기 때문이다. 정리 전 잠깐 동안 해당 Pod로 새 트래픽이 계속 들어올 수 있다.

```yaml
spec:
  terminationGracePeriodSeconds: 60
  containers:
    - name: app
      lifecycle:
        preStop:
          exec:
            command: ["sh", "-c", "sleep 10"]
```

흐름:

1. K8s가 Pod 삭제 → Endpoints 제거 전파 시작 + `preStop` 훅 실행
2. `sleep 10` 동안 LB/서비스 메쉬가 해당 Pod를 드레인
3. `preStop` 종료 후 SIGTERM 전달
4. Spring graceful shutdown이 in-flight 요청 처리
5. `terminationGracePeriodSeconds` 안에 정상 종료

추가 체크 항목:

- **Readiness probe를 먼저 실패시키기**: `/actuator/health/liveness` 와 `/actuator/health/readiness` 를 분리. 종료 시 readiness가 먼저 실패 → 트래픽 차단 → SIGTERM.
- **Kafka consumer**: shutdown hook에서 `consumer.wakeup()` + `close(Duration)` 로 rebalance를 깔끔하게 유도.
- **DB connection drain**: Hikari `allowPoolSuspension` 대신, Spring lifecycle에 맞춰 자연 종료되도록 둔다.

## 9. 관측성(Observability) 결합

Resilience는 "동작했는지 확인할 수 있어야" 의미가 있다. Resilience4j는 Micrometer 통합을 기본 제공한다.

노출해야 할 핵심 메트릭:

- `resilience4j.circuitbreaker.state{name="inventoryApi"}` → Closed / Open / Half-Open
- `resilience4j.circuitbreaker.calls{kind="failed|successful|not_permitted|slow"}`
- `resilience4j.retry.calls{kind="successful_with_retry|failed_with_retry|successful_without_retry"}`
- `resilience4j.bulkhead.available.concurrent.calls`
- 서비스 레벨: `http_server_requests_seconds_bucket` + fallback counter

대시보드 3종(Grafana 기준):

1. **Upstream health board**: 대상 API별 latency p50/p95/p99, error rate, circuit state
2. **Retry / fallback board**: 재시도율, 재시도 성공률, fallback 비율
3. **Saturation board**: bulkhead / thread pool / connection pool 사용률

알람은 **"회로가 N분 이상 열려 있음"**, **"fallback rate > 5%"**, **"재시도율 > 10%"** 를 기본으로 둔다.

## 로컬 실습 환경

로컬에서 실제로 장애를 주입해가며 확인하는 것이 학습에 가장 효과적이다. 최소 세 가지 도구를 준비한다.

### 실습용 장애 서버 (Python / Node 어느 쪽이든)

```python
# fake_upstream.py
from flask import Flask, jsonify
import random, time

app = Flask(__name__)

@app.get("/flaky")
def flaky():
    r = random.random()
    if r < 0.3:
        time.sleep(5)
    if r < 0.5:
        return "boom", 500
    return jsonify(ok=True)
```

```
pip install flask
python fake_upstream.py
```

### Spring Boot 클라이언트

`build.gradle` 에 `io.github.resilience4j:resilience4j-spring-boot3`, `spring-boot-starter-actuator`, `spring-boot-starter-web` 추가 후:

```java
@RestController
@RequiredArgsConstructor
class DemoController {

    private final RestClient restClient = RestClient.create("http://localhost:5000");

    @GetMapping("/call")
    @CircuitBreaker(name = "upstream", fallbackMethod = "fallback")
    @Retry(name = "upstream")
    @TimeLimiter(name = "upstream")
    public CompletableFuture<String> call() {
        return CompletableFuture.supplyAsync(() ->
            restClient.get().uri("/flaky").retrieve().body(String.class));
    }

    public CompletableFuture<String> fallback(Throwable ex) {
        return CompletableFuture.completedFuture("degraded-response");
    }
}
```

```yaml
resilience4j:
  timelimiter:
    instances:
      upstream:
        timeout-duration: 1s
  retry:
    instances:
      upstream:
        max-attempts: 3
        wait-duration: 200ms
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2
  circuitbreaker:
    instances:
      upstream:
        sliding-window-size: 20
        minimum-number-of-calls: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
        permitted-number-of-calls-in-half-open-state: 3

management:
  endpoints.web.exposure.include: health,metrics,prometheus,circuitbreakers
```

### 부하 주입

```
brew install hey     # 또는 apt install hey
hey -z 60s -c 50 http://localhost:8080/call
```

`/actuator/circuitbreakers` 를 주기적으로 찍어서 상태 전이를 눈으로 확인한다. 부하 중 `fake_upstream.py`에 추가 sleep을 넣거나 500 비율을 높여서 Open 진입을 재현한다.

## 면접 framing: "외부 API가 느려지면 어떻게 대응하시나요?"

시니어 레벨에서 기대되는 답변 구조는 다음과 같다.

1. **먼저 실패 모델을 정의한다**: "업스트림 지연 / 에러인지, 우리 쪽 스레드풀 포화인지, 네트워크 구간 문제인지를 메트릭(p95, error rate, connection pool saturation)으로 구분해서 봅니다."
2. **즉시 조치**: "지연이 확인되면 해당 API 호출에 걸린 circuit breaker 상태와 timeout 설정을 먼저 확인합니다. 필요시 수동으로 circuit을 열 수 있는 토글을 둬서 파급을 차단합니다."
3. **자원 격리 확인**: "해당 호출이 다른 API를 사용하는 스레드풀을 잠식하지 않도록 bulkhead가 걸려 있는지 확인합니다. 없으면 핫픽스로 독립 스레드풀을 분리합니다."
4. **Fallback 작동 확인**: "개인화/추천 같은 보조 기능이면 캐시 기반 fallback이 도는지 확인하고, 결제 같은 핵심 경로는 비동기 재처리 큐로 전환 가능한지 봅니다."
5. **재시도 정책 점검**: "retry 횟수 × timeout 이 상위 SLA를 넘지 않는지, 재시도 폭주가 업스트림을 더 때리고 있지 않은지 확인합니다. 필요 시 재시도를 일시 비활성화합니다."
6. **관측성 근거**: "결정은 항상 circuit state, fallback rate, retry rate 메트릭과 대시보드를 근거로 합니다."
7. **사후 개선**: "장애 종료 후 timeout 값, CB threshold, bulkhead 크기를 실측 p99 기준으로 재조정하고, 동일 패턴 감지용 알람을 추가합니다."

여기에 본인 경험을 붙이면 답변이 단단해진다. 예시: *"이전 서비스에서 결제 PG 한 곳의 응답 지연이 우리 주문 API 스레드풀을 잠식해서 홈 화면까지 영향을 준 적이 있었고, 이후 PG 호출을 독립 스레드풀 + 500ms timeout + 서킷으로 묶어 blast radius를 주문 도메인 안으로 제한했습니다."*

## 흔한 실수 패턴 모음

- `socketTimeout` 없는 JDBC URL → 커넥션풀 즉시 고갈
- HTTP 클라이언트에 connect timeout만 걸고 read timeout 없음 → hang
- 모든 layer에서 재시도 3번 → 실제 부하 수십 배
- 비즈니스 예외를 CircuitBreaker가 실패로 카운트 → 정상 상태에서도 open
- 재시도 대상에 4xx 포함 → 무의미한 재시도로 서버 부하만 늘림
- Graceful shutdown만 설정하고 K8s preStop 훅 누락 → 배포마다 500 잠깐 찍힘
- Fallback이 silent → 장애가 메트릭에 안 잡혀 인지 지연
- Lettuce에 timeout 미설정 → Redis 장애가 전체 Tomcat worker를 잠식

## 체크리스트

- [ ] 외부 호출에 connection / read / call timeout 세 계층이 모두 정의되어 있다.
- [ ] 재시도는 멱등한 호출에만, 지수 백오프 + jitter 로 적용된다.
- [ ] 재시도 × 시도당 timeout ≤ 상위 call timeout 을 만족한다.
- [ ] Circuit breaker는 비즈니스 예외를 실패로 카운트하지 않는다.
- [ ] Retry는 CircuitBreaker 안쪽에서 실행된다 (open 상태를 존중한다).
- [ ] 중요한 외부 호출은 전용 스레드풀 또는 Bulkhead로 격리되어 있다.
- [ ] Fallback은 메트릭과 로그로 명시적으로 관측된다.
- [ ] 과부하 시 429 / 503 을 반환하고, 클라이언트에 `Retry-After` 를 제공한다.
- [ ] Spring `server.shutdown: graceful` + K8s `preStop sleep` + readiness probe 분리가 적용되어 있다.
- [ ] CB 상태 / retry rate / fallback rate / bulkhead 사용률이 대시보드와 알람으로 연결되어 있다.
- [ ] 로컬 장애 주입(fake upstream, toxiproxy 등)으로 각 패턴의 전이를 직접 재현해봤다.
- [ ] 면접용 장애 대응 talk-through 를 본인 경험으로 말할 수 있다.
