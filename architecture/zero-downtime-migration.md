# [초안] 대규모 트래픽 중 무중단 마이그레이션 — Feature Flag + Shadow Mode 실전

## 왜 이 주제가 중요한가

시니어 백엔드 면접에서 "트래픽이 평소의 10배로 튀는 상황에서 레거시 인증 모듈을 신규 모듈로 교체해야 한다. 어떻게 배포하시겠습니까?"라는 질문은 더 이상 이론 문제가 아니다. 올리브영 세일, 쿠팡 로켓배송 피크, 네이버 쇼핑 라이브 같은 국내 커머스 환경은 초당 수만 요청 단위에서 무중단 마이그레이션을 상시로 요구한다. 재배포 한 번의 rollback 시간은 평균 10~15분이지만, Feature Flag 기반 rollback은 수십 초 이내에 끝난다. 이 차이는 단순한 속도 문제가 아니라 "장애 시간 × 분당 매출"로 환산되는 직접적 비용이며, SRE·백엔드 리더십이 가장 민감하게 보는 지표다.

실제로 CJ 올리브영은 세일 시즌 중 OAuth2 인증 서버를 레거시에서 Spring Authorization Server로 전환하면서 재배포 없이 Feature Flag + Shadow Mode로 점진 전환하는 사례를 공개했다. 단순히 "무중단으로 옮겼다"가 아니라 "런타임 플래그 + 결과 섀도잉 + Circuit Breaker + Jitter"의 조합이 핵심이었다. 이 글은 그 네 축을 실제 코드 수준으로 재구성하고, 면접 답변까지 연결하는 것을 목표로 한다.

## 런타임 플래그가 재배포보다 안전한 이유

운영 환경에서 "신규 코드 경로로 전환"은 본질적으로 두 가지 방법이 있다.

**방법 A — 재배포 기반 전환**
1. 새 코드가 들어간 아티팩트를 빌드한다.
2. 카나리 인스턴스에 배포한다.
3. LB에서 트래픽을 서서히 넘긴다.
4. 문제가 생기면 이전 아티팩트로 롤백한다.

**방법 B — 런타임 플래그 기반 전환**
1. 두 경로(레거시, 신규)를 모두 포함한 아티팩트를 배포한다.
2. Feature Flag로 트래픽 분기 비율을 조절한다.
3. 문제가 생기면 플래그를 OFF로 전환한다.

두 방식의 가장 큰 차이는 **롤백 소요 시간**이다. 쿠버네티스 기준 Deployment 롤백은 이미지 pull → 컨테이너 재시작 → readiness probe 통과 → LB 재등록까지 최소 3~5분, pod 100개 이상 서비스는 10~20분이 걸린다. 반면 Feature Flag는 Redis 또는 DB의 값 하나를 바꾸는 것이므로 전환 지연이 캐시 TTL 이내(보통 1~30초)다. 그리고 재배포는 "컴파일된 코드"를 되돌리기 때문에 롤백 중에도 이미 새 코드로 요청을 받은 세션들이 존재한다. 플래그 방식은 한 프로세스 내에서 분기만 바뀌므로 세션 상태가 깨질 여지가 상대적으로 작다.

단, 플래그 방식에는 비용이 있다. 두 경로의 코드가 동시에 빌드에 존재해야 하므로 **코드베이스 복잡도가 증가**하고, 플래그 제거(cleanup) 시점을 정해두지 않으면 "flag rot"이 쌓인다. 실제로 LinkedIn, Uber 등의 포스트모템을 보면 장기 방치된 플래그가 장애의 트리거가 된 사례가 다수 있다. 따라서 플래그는 항상 "언제 제거할 것인지 티켓으로 남긴다"가 원칙이다.

## Feature Flag 아키텍처 — 세 가지 레벨

### 1. Static config

`application.yml`에 값을 박아두고 부팅 시 주입하는 방식이다.

```yaml
feature:
  oauth2:
    new-auth-server-enabled: false
    rollout-percentage: 0
```

장점: 단순하다. 외부 의존 없음. 테스트 쉬움.
단점: **런타임 변경이 불가**하다. 값을 바꾸려면 재배포가 필요하므로 "무중단 전환"이라는 원래 목적을 해친다. Spring Cloud Config를 붙이면 refresh 엔드포인트로 갱신할 수 있으나 분산 환경에서 일관성이 보장되지 않는다.

### 2. DB / 캐시 기반 플래그

운영 DB 또는 Redis에 플래그 값을 두고 서비스가 짧은 TTL로 조회한다.

```sql
CREATE TABLE feature_flag (
  flag_key VARCHAR(100) PRIMARY KEY,
  enabled BOOLEAN NOT NULL,
  rollout_percentage INT NOT NULL DEFAULT 0,
  segment VARCHAR(50),
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

장점: 운영 어드민 화면만 만들면 런타임 전환 가능. 인프라 추가 부담이 적다.
단점: 매 요청마다 DB/Redis를 때릴 수 없으므로 **로컬 캐시**가 필수다. 캐시 TTL이 길면 플래그 반영이 늦고, 짧으면 DB 부하가 올라간다. 보통 Caffeine 로컬 캐시 + 5~30초 TTL + pub/sub으로 invalidation을 푸시하는 조합이 실무 표준이다.

### 3. SaaS (LaunchDarkly, Unleash, Flagsmith 등)

전용 SDK가 persistent connection으로 플래그 변경을 실시간 스트리밍한다.

장점: 세그먼트 기반 롤아웃(특정 사용자 그룹만 ON), 퍼센트 롤아웃(10% → 25% → 50%), A/B 실험, kill switch, 감사 로그 등 운영 기능이 모두 내장. 변경 즉시 전 인스턴스 반영.
단점: 월 비용. 외부 의존성 증가. SaaS 장애 시 플래그가 default 값으로 fallback되는지 반드시 테스트해야 한다. **"플래그 시스템 장애 = 서비스 장애"가 되지 않도록 fail-safe default를 지정하는 것이 핵심**이다.

실무 선택 기준: 플래그 10개 미만이고 팀이 작다면 DB 기반으로 충분하다. 플래그가 50개를 넘고 여러 팀이 공유한다면 SaaS가 유리하다.

### 세그먼트 / 퍼센트 / kill switch

세 가지는 같은 플래그라도 다르게 사용된다.

- **세그먼트 롤아웃**: `internal_user=true`만 먼저 ON. 베타 사용자, 회사 직원 대상 선행 검증에 쓴다.
- **퍼센트 롤아웃**: 해시(userId) % 100 < rolloutPercentage. 사용자별로 결과가 결정적(deterministic)이어야 한다. 그래야 같은 유저가 새로고침마다 다른 경로로 가지 않는다.
- **Kill switch**: 어떤 세그먼트/퍼센트에서도 문제가 생기면 `enabled=false`로 전체 OFF. 이 전환이 **10초 안에 전 인스턴스에 반영**되어야 플래그 시스템이 의미 있다.

## Strategy 패턴으로 Feature Flag 구현하기 — 코드 레벨 분기와 무엇이 다른가

가장 흔한 실수는 플래그를 `if/else`로 도배하는 것이다.

**나쁜 예**

```java
public TokenResponse issueToken(TokenRequest req) {
    if (featureFlag.isEnabled("new-auth-server")) {
        // 신규 Authorization Server 호출
        return newAuthClient.issue(req);
    } else {
        // 레거시 토큰 발급
        return legacyTokenService.issue(req);
    }
}
```

이 패턴은 처음 한두 군데만 있을 때는 괜찮지만, 분기점이 늘면 한 메서드 안에 수십 줄의 조건문이 쌓이고, 테스트는 플래그 값 조합마다 폭발한다. 더 큰 문제는 "플래그 제거" 시점에 if 블록만 삭제하면 될 줄 알았는데 내부에서 레거시 객체에 의존하는 다른 분기들이 얽혀 있어 손대기 어렵다는 점이다.

**개선된 예 — Strategy 패턴 + Flag 라우팅**

```java
public interface TokenIssuer {
    TokenResponse issue(TokenRequest req);
    String name();
}

@Component
public class LegacyTokenIssuer implements TokenIssuer {
    public TokenResponse issue(TokenRequest req) { ... }
    public String name() { return "legacy"; }
}

@Component
public class NewAuthServerTokenIssuer implements TokenIssuer {
    public TokenResponse issue(TokenRequest req) { ... }
    public String name() { return "new-auth-server"; }
}

@Component
@RequiredArgsConstructor
public class TokenIssuerRouter {
    private final Map<String, TokenIssuer> issuers;
    private final FeatureFlagService flags;

    public TokenIssuer resolve(String userId) {
        boolean useNew = flags.isEnabledFor("oauth2.new-auth-server", userId);
        return issuers.get(useNew ? "new-auth-server" : "legacy");
    }
}
```

각 구현체는 독립적으로 테스트·프로파일링·교체 가능하다. 플래그 제거 시점에는 Router를 단순화하고 Legacy 구현체를 통째로 지우면 된다. 실제 대규모 전환에서는 이 패턴이 "cleanup 공포"를 크게 줄인다.

## Shadow Mode — 결과만 비교하는 조용한 실전 검증

Feature Flag가 "경로를 바꾼다"라면, Shadow Mode는 **"경로는 바꾸지 않고 병렬로 실행해서 결과만 비교한다"**이다.

구조는 이렇다.
1. 요청이 들어온다.
2. 레거시 경로가 요청을 처리하고 실제 응답을 내려준다. **이게 유일한 사용자 응답이다.**
3. 동시에, 같은 입력이 신규 경로에도 비동기로 흘러간다.
4. 신규 경로의 결과는 사용자에게 내려가지 않고 메트릭/로그로만 기록된다.
5. 일정 기간이 지나 두 경로의 결과가 일치하면 Feature Flag로 신규 경로에 실제 트래픽을 넘긴다.

Shadow Mode의 가장 큰 가치는 **"사용자에게 피해 0 + 실제 트래픽 분포로 검증"**이다. 스테이징 환경 부하 테스트는 실제 사용자 패턴을 재현하지 못한다. Shadow는 프로덕션 트래픽 그대로를 신규 경로에 태우므로 엣지 케이스가 그대로 드러난다.

**Shadow 구현 스케치**

```java
@Component
@RequiredArgsConstructor
public class ShadowExecutor {
    private final Executor shadowExecutor; // 별도 스레드풀
    private final MeterRegistry meter;

    public <T> T runWithShadow(Supplier<T> primary, Supplier<T> shadow, String name) {
        T primaryResult = primary.get();

        shadowExecutor.execute(() -> {
            long start = System.nanoTime();
            try {
                T shadowResult = shadow.get();
                boolean match = Objects.equals(primaryResult, shadowResult);
                meter.counter("shadow.result", "name", name, "match", String.valueOf(match)).increment();
            } catch (Exception e) {
                meter.counter("shadow.error", "name", name, "type", e.getClass().getSimpleName()).increment();
                log.warn("shadow failure name={}", name, e);
            } finally {
                meter.timer("shadow.latency", "name", name).record(System.nanoTime() - start, TimeUnit.NANOSECONDS);
            }
        });

        return primaryResult;
    }
}
```

Shadow 경로는 반드시 **별도 스레드풀**에서 돌아야 한다. 그래야 Shadow 쪽 장애나 지연이 primary 경로에 백프레셔를 주지 않는다. 또한 Shadow 스레드풀은 반드시 **bounded queue + reject policy**를 가져야 한다. 무제한 큐는 메모리 폭증으로 이어진다.

주의할 엣지 케이스 몇 가지가 있다.
- **Side effect가 있는 연산을 Shadow로 돌리면 안 된다.** 결제 승인, 이메일 발송, 외부 쓰기 API는 Shadow에서 절대 실행 금지. 읽기/계산 로직만 대상.
- **멱등성이 없는 DB 쓰기**를 Shadow로 돌리면 중복 레코드가 쌓인다. Shadow 전용 테이블에 쓰거나 read-only로 제한한다.
- **비결정적 로직**(시간, 랜덤 등)은 결과 비교에서 제외하거나 seed를 고정한다.

## Dark Launch vs Shadow Mode vs Canary vs Blue/Green

네 용어는 자주 섞여 쓰이지만 성격이 다르다.

| 기법 | 사용자 응답 영향 | 트래픽 받는가 | 주 용도 |
|---|---|---|---|
| Shadow Mode | 없음(사용자는 레거시 응답만 받음) | 신규 경로도 동일 입력 수신하지만 응답은 버려짐 | 로직 동등성 검증 |
| Dark Launch | 없음 또는 일부 | 기능을 "숨긴 채" 배포하고 플래그로 노출 | UI/기능 출시 타이밍 제어 |
| Canary | 있음(소수 사용자) | 신규 코드에 실제 트래픽 일부(1~10%) | 점진적 전환, 성능·오류율 관찰 |
| Blue/Green | 있음(전체 즉시 전환) | 신규 환경 준비 후 LB 스위치 | 빠른 전환 + 즉시 롤백 |

실전 순서는 보통 이렇다. **Shadow Mode(로직 검증)** → **Canary 1% → 5% → 25%(실사용 부하 관찰)** → **50% → 100%(전환 완료)** → **Legacy 제거**. Blue/Green은 인프라 여유가 있는 조직(특히 쿠버네티스에서 두 deployment를 동시에 유지 가능한 경우)에서 빠른 스위치가 필요할 때 선택한다. OAuth2 같이 **세션/토큰 상태 호환성**이 핵심인 전환은 대부분 Shadow → Canary 순서로 간다. Blue/Green은 토큰 호환 구간을 다루기 까다롭다.

## OAuth2 / Spring Authorization Server 전환 시나리오

레거시 토큰 발급 로직을 Spring Authorization Server로 옮길 때 가장 큰 난제는 **"전환 기간 동안 두 종류의 토큰이 공존한다"**는 점이다.

시나리오를 구체화하면 이렇다.

1. 레거시는 자체 JWT(HS256, secret key 기반)를 발급했다.
2. 신규는 Spring Authorization Server가 RS256(비대칭 키)로 발급한다.
3. 리소스 서버는 **두 종류의 토큰을 모두 검증**할 수 있어야 한다.

**호환 구간 검증 필터**

```java
@Component
public class DualTokenAuthenticationFilter extends OncePerRequestFilter {
    private final LegacyJwtDecoder legacyDecoder;
    private final NimbusJwtDecoder newDecoder;
    private final FeatureFlagService flags;
    private final MeterRegistry meter;

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String token = extractBearer(req);
        if (token == null) { chain.doFilter(req, res); return; }

        Authentication auth = null;
        String issuer = detectIssuer(token); // "iss" claim 확인

        if ("new-auth-server".equals(issuer)) {
            auth = authenticateWith(newDecoder, token);
            meter.counter("token.verify", "issuer", "new").increment();
        } else {
            auth = authenticateWith(legacyDecoder, token);
            meter.counter("token.verify", "issuer", "legacy").increment();
        }

        SecurityContextHolder.getContext().setAuthentication(auth);
        chain.doFilter(req, res);
    }
}
```

발급 쪽은 Feature Flag로 분기한다.

```java
@PostMapping("/oauth2/token")
public TokenResponse issue(@RequestBody TokenRequest req) {
    TokenIssuer issuer = tokenIssuerRouter.resolve(req.getUserId());
    return issuer.issue(req);
}
```

핵심 주의점:
- **Refresh Token 호환성**: 레거시 refresh token은 신규 서버가 인식할 수 없다. 전환 기간 동안 "어느 쪽에서 발급했는가"를 토큰 자체에 표기하고 refresh 시 같은 발급자로 라우팅한다.
- **Logout(토큰 무효화)**: 블랙리스트 저장소를 공유하거나, 양쪽 모두에 invalidate 요청을 보낸다.
- **Claim 스키마 drift**: 두 발급자가 같은 claim을 다른 타입으로 넣는 순간 리소스 서버의 권한 판정이 깨진다. Shadow Mode로 먼저 claim diff를 수집하는 것이 필수다.

## Resilience4j — Circuit Breaker + Timeout + Retry 3단계 방어

신규 Authorization Server가 트래픽 10배 상황에서 불안정하면, 인증 실패가 전체 서비스로 번진다. 이를 막는 것이 **3단계 방어**다.

```java
@Configuration
public class ResilienceConfig {

    @Bean
    public CircuitBreaker authServerBreaker() {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
            .failureRateThreshold(50)               // 50% 실패면 open
            .slowCallRateThreshold(50)              // 느린 호출 50% 이상도 open
            .slowCallDurationThreshold(Duration.ofMillis(500))
            .waitDurationInOpenState(Duration.ofSeconds(30))
            .permittedNumberOfCallsInHalfOpenState(10)
            .slidingWindowSize(100)
            .build();
        return CircuitBreaker.of("authServer", config);
    }

    @Bean
    public TimeLimiter authServerTimeLimiter() {
        return TimeLimiter.of(TimeLimiterConfig.custom()
            .timeoutDuration(Duration.ofMillis(800))
            .cancelRunningFuture(true)
            .build());
    }

    @Bean
    public Retry authServerRetry() {
        return Retry.of("authServer", RetryConfig.custom()
            .maxAttempts(2)                          // 원샷 + 1회 재시도
            .waitDuration(Duration.ofMillis(100))
            .retryExceptions(IOException.class, TimeoutException.class)
            .ignoreExceptions(AuthenticationException.class) // 인증 실패는 재시도 금지
            .build());
    }
}
```

호출부는 세 개를 체인으로 묶는다.

```java
Supplier<TokenResponse> decorated = Decorators.ofSupplier(() -> newAuthClient.issue(req))
    .withCircuitBreaker(breaker)
    .withRetry(retry)
    .decorate();

CompletableFuture<TokenResponse> future = timeLimiter.executeCompletionStage(
    scheduler, () -> CompletableFuture.supplyAsync(decorated)).toCompletableFuture();
```

순서가 중요하다. **Timeout → Retry → Circuit Breaker** 바깥 쪽부터. Timeout이 가장 안쪽이면 재시도가 전체 타임아웃을 무시한다. 재시도 가능한 예외와 재시도 금지 예외를 구분하는 것도 필수다. 인증 실패(401)는 재시도해도 결과가 같으므로 오히려 백엔드 부하만 증가시킨다.

Fallback은 "플래그를 OFF로 강제"가 되는 경우가 많다.

```java
try {
    return decorated.get();
} catch (CallNotPermittedException e) {
    // Circuit Open → 플래그 강제 OFF 후 레거시로
    flags.forceOff("oauth2.new-auth-server", Duration.ofMinutes(5));
    return legacyIssuer.issue(req);
}
```

## Jitter로 Peak TPS 40% 감소시키는 원리

OAuth2 전환 중 실제 관찰된 현상: 토큰 만료 시각이 동일한 사용자 수백만이 **같은 초에** refresh 요청을 보내면서 초당 TPS가 10배로 튀었다. 이를 해결한 방법이 **Jitter(±30초 랜덤 지연)**이다.

**왜 TPS가 40% 감소하는가.** 원래 TPS = (동시 만료 사용자 수) / (1초). 여기에 ±30초 uniform jitter를 더하면 만료 이벤트가 60초 구간에 균등 분산된다. 피크가 평평하게 펴지므로 순간 TPS는 1/60에 가까워진다. 실전에서는 사용자 행동이 완전 uniform은 아니므로 이론치만큼 내려가지 않고 **30~40% 감소**가 현실적 수치다.

```java
public LocalDateTime computeExpiry(LocalDateTime base, Duration ttl) {
    long jitterSeconds = ThreadLocalRandom.current().nextLong(-30, 31);
    return base.plus(ttl).plusSeconds(jitterSeconds);
}
```

Jitter는 토큰 만료뿐 아니라 **캐시 만료, 스케줄러 실행, 재시도 백오프**에도 동일하게 적용된다. 재시도 백오프는 `exponential backoff + full jitter`가 AWS 권장 패턴이다. 핵심은 "완전 동기화는 서버를 죽인다, 적당한 desync가 서버를 살린다"이다.

## 모니터링 — 두 경로를 실시간으로 비교하는 대시보드

Shadow Mode와 Canary가 의미 있으려면 **"두 경로의 차이"를 실시간으로 봐야 한다**. 보통 Micrometer + Prometheus + Grafana 스택을 쓴다.

수집해야 하는 최소 메트릭:

```java
meter.timer("token.issue.latency", "path", "legacy").record(...);
meter.timer("token.issue.latency", "path", "new").record(...);
meter.counter("token.issue.result", "path", "legacy", "outcome", "success").increment();
meter.counter("token.issue.result", "path", "new", "outcome", "success").increment();
meter.counter("shadow.diff", "field", "scope").increment();
```

대시보드 구성:
1. **P95 레이턴시 비교**: 두 경로를 같은 패널에 겹쳐 그린다. 신규가 레거시보다 20% 이상 느리면 경고.
2. **성공률 비교**: `success / (success + failure)`. 0.1%p 차이만 나도 즉시 인지해야 한다.
3. **Shadow diff rate**: Shadow 경로에서 결과가 불일치한 비율. 이게 내려가지 않으면 Canary로 넘어가면 안 된다.
4. **Circuit Breaker 상태**: open/half-open/closed 타임라인.
5. **Feature Flag 현재 값**: 대시보드 상단에 상수처럼 고정 표시. "지금 몇 퍼센트에 켜져 있는가"를 항상 보이게 한다.

알람은 **성공률**과 **P95**에 걸고, 레이턴시 알람은 반드시 **baseline 대비 상대값**으로 설정한다. 절대값 알람은 트래픽이 낮은 새벽에 오탐이 폭주한다.

## 실전 Java/Spring 예제 — @ConditionalOnProperty, FeatureFlagFilter

`@ConditionalOnProperty`는 static config 레벨에서 빈 자체를 켜고 끌 때 쓴다. 런타임 전환은 아니지만 **"이 기능을 아예 빌드에서 비활성화"**하는 경우에 유용하다.

```java
@Configuration
@ConditionalOnProperty(name = "feature.oauth2.new-auth-server.enabled", havingValue = "true")
public class NewAuthServerConfig {
    @Bean
    public NewAuthServerClient newAuthClient(...) { ... }
}
```

런타임 플래그는 필터 레벨에서 적용하는 것이 깔끔하다.

```java
@Component
@RequiredArgsConstructor
public class FeatureFlagFilter extends OncePerRequestFilter {
    private final FeatureFlagService flags;

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String userId = resolveUserId(req);
        boolean useNew = flags.isEnabledFor("oauth2.new-auth-server", userId);
        req.setAttribute("feature.oauth2.path", useNew ? "new" : "legacy");
        chain.doFilter(req, res);
    }
}
```

`FeatureFlagService` 구현에서 가장 중요한 것은 **deterministic bucketing**이다.

```java
public boolean isEnabledFor(String key, String userId) {
    FeatureFlag flag = flagCache.get(key);
    if (flag == null || !flag.isEnabled()) return false;
    if (flag.getRolloutPercentage() >= 100) return true;
    int bucket = Math.floorMod(Hashing.murmur3_32().hashString(key + ":" + userId, UTF_8).asInt(), 100);
    return bucket < flag.getRolloutPercentage();
}
```

사용자별 해시이므로 같은 userId는 항상 같은 분기를 받는다. 10% 롤아웃에 걸린 유저가 새로고침했더니 경로가 바뀌는 버그는 이 bucketing을 생략했을 때 전형적으로 발생한다.

## 로컬 실습 환경

1. **Docker Compose로 최소 스택 구성**
   - Redis(플래그 캐시 pub/sub), MySQL(플래그 저장), Prometheus, Grafana.
2. **Spring Boot 3.2 + Spring Authorization Server 1.2** 샘플 앱 두 개
   - `legacy-auth`: 자체 JWT 발급
   - `new-auth-server`: Spring Authorization Server
3. **Resource Server** 하나를 띄우고 `DualTokenAuthenticationFilter` 적용
4. **k6 또는 JMeter**로 1,000 RPS 부하 + 10초마다 피크 스파이크 시나리오
5. **flag CLI 스크립트**로 rolloutPercentage를 0 → 10 → 50 → 100으로 단계적 변경
6. **Grafana 대시보드**에 P95 / 성공률 / Shadow diff rate / Circuit Breaker 상태 패널 구성

실습 체크포인트: rolloutPercentage 10%에서 신규 경로 P95가 레거시보다 높으면 자동으로 알람이 울려야 하고, `enabled=false` 전환 후 **30초 이내**에 모든 인스턴스가 레거시로 복귀하는지 로그로 확인한다.

## 흔한 실수 패턴

- **플래그 default가 "enabled"인 경우**: SaaS 장애 시 기본값이 ON이면 장애가 번진다. default는 항상 "안전한 쪽(보통 OFF)".
- **Shadow 결과 비교를 동기로 실행**: primary 지연이 커진다. 반드시 비동기.
- **플래그를 매 요청 DB 조회**: DB가 bottleneck. Caffeine 캐시 + 짧은 TTL.
- **퍼센트 롤아웃을 Math.random()으로**: 사용자별 일관성 깨짐. 반드시 hash(userId).
- **Circuit Breaker 임계값 50% + 슬라이딩 윈도우 10개**: 샘플이 너무 작아 flapping 발생. 윈도우는 최소 100건 이상.
- **Legacy 경로를 먼저 지우고 나중에 플래그 제거**: 순서가 반대다. 플래그 제거 → 하드코딩 → legacy 삭제.
- **Jitter 없이 스케줄러 여러 개**: 매 정각마다 스파이크.

## 면접 답변 Framing — "트래픽 10배에 배포를 어떻게 하시나요"

다음은 시니어 백엔드 포지션에서 바로 쓸 수 있는 1~2분 답변 구조다.

> 평소의 10배 트래픽 상황에서 인증 모듈 같은 핵심 경로를 교체해야 한다면, 저는 재배포 기반 전환이 아닌 **Feature Flag + Shadow Mode 조합**을 선택합니다. 이유는 rollback 시간 차이 때문인데, 재배포 롤백은 이미지 pull부터 LB 재등록까지 10분 이상 걸리지만 플래그는 30초 이내에 복구됩니다. 트래픽 10배 상황에서 10분은 매출 손실로 직결되니까요.
>
> 구체적으로는 네 단계로 진행합니다. 첫째, 신규 경로를 **Strategy 패턴**으로 구현해 레거시 경로와 같은 인터페이스로 주입합니다. if/else 분기는 유지보수가 안 됩니다. 둘째, **Shadow Mode**로 프로덕션 트래픽을 신규 경로에도 흘려 결과를 비교하되 사용자에게는 레거시 응답만 내보냅니다. 이 단계에서 claim drift, 응답 타입 불일치 같은 엣지 케이스를 발견합니다. 셋째, Shadow diff rate가 충분히 낮아지면 **Feature Flag로 1% → 5% → 25% → 50% → 100%**로 canary 롤아웃합니다. 이때 **Resilience4j로 Circuit Breaker, Timeout, Retry 3단계**를 걸어 신규 경로가 흔들려도 레거시로 자동 fallback되게 합니다. 넷째, 전환 완료 후 플래그와 Legacy 코드를 같은 PR에서 제거합니다.
>
> 여기에 특히 토큰/캐시 만료가 피크를 만드는 경우 **±30초 Jitter**를 넣어 TPS 피크를 평탄화합니다. 이전 슬롯팀 배포에서도 비슷한 패턴으로 재배포 없이 쿼리 경로를 교체한 적이 있고, 그레이스풀 셧다운 troubleshooting 과정에서 in-flight 요청이 두 경로에 섞이는 문제를 해결했던 경험이 있어 이 방식의 함정을 실제로 알고 있습니다.

이 답변이 강한 이유는 (1) 왜 이 방식인지(rollback 시간), (2) 단계가 분명함(Strategy → Shadow → Canary → Cleanup), (3) 방어 장치가 구체적(Resilience4j 3단계 + Jitter), (4) 본인 경험으로 마무리한다는 점이다. 면접관은 "이 사람이 실제로 해봤는가"를 가장 중요하게 본다.

## 후속 질문 대비

면접관이 깊게 파고들 가능성이 높은 후속 질문과 짧은 답변 가이드.

- **"Shadow Mode에서 side effect 있는 로직은 어떻게 처리하죠?"** → Shadow는 read-only 영역에만 적용한다. 쓰기 경로는 멱등성 키 기반 Canary로 직접 검증하거나, Shadow 전용 샌드박스 테이블에 기록한다.
- **"플래그 시스템 자체가 죽으면?"** → SDK는 last-known-good 값을 메모리 캐시에 유지하고, 그마저 없으면 fail-safe default로 fallback. SaaS 의존 시 반드시 chaos test로 검증.
- **"Refresh token 호환성은?"** → 토큰 자체에 `iss` claim을 넣고 리소스 서버에서 발급자별 decoder 라우팅. 전환 완료 후 일정 기간 레거시 decoder 유지.
- **"퍼센트 롤아웃 중 사용자가 새로고침하면?"** → hash(userId) 기반 bucketing이므로 동일 유저는 동일 경로 고정. Math.random() 쓰면 이 질문에서 바로 걸린다.

## 최종 체크리스트

- [ ] 플래그는 런타임 전환 가능한가 (재배포 없이 30초 내 반영)
- [ ] 플래그 fail-safe default가 OFF인가
- [ ] 퍼센트 롤아웃이 hash(userId)로 deterministic한가
- [ ] Strategy 패턴으로 if/else 분기를 제거했는가
- [ ] Shadow 경로가 별도 스레드풀 + bounded queue인가
- [ ] Shadow는 read-only 로직에만 적용되었는가
- [ ] 두 경로의 P95와 성공률을 실시간으로 볼 수 있는 대시보드가 있는가
- [ ] Shadow diff rate에 알람이 걸려 있는가
- [ ] Resilience4j Timeout → Retry → CircuitBreaker 순서로 체인되었는가
- [ ] 재시도 가능 예외와 금지 예외가 구분되었는가
- [ ] 만료 시각/스케줄러에 Jitter가 적용되었는가
- [ ] OAuth2 전환 시 `iss` claim으로 토큰 발급자를 구분하는가
- [ ] Refresh token이 발급자별로 올바르게 라우팅되는가
- [ ] 플래그 cleanup 티켓이 만들어져 있는가
- [ ] 롤백 시나리오가 문서화되어 있고 실제 drill로 검증되었는가
