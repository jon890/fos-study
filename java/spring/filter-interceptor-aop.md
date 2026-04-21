# [초안] Filter, Interceptor, AOP: Spring 요청 처리 파이프라인에서의 관심사 분리

## 왜 이 주제가 중요한가

Spring 기반 백엔드에서 "요청이 들어와서 컨트롤러에 도달하기 전까지 뭔가 하고 싶다"는 요구는 끊임없이 생긴다. 로깅, 인증, 요청 ID 주입, 요청/응답 바디 감사(audit), 성능 측정, 예외 변환, 트랜잭션 경계 제어, 특정 어노테이션이 붙은 메서드에만 권한 체크 적용 — 이 모든 게 사실상 같은 질문의 변주다. "이 횡단 관심사를 어느 계층에 꽂을 것인가?"

Filter, Interceptor, AOP는 서로 다른 위치에서 이 질문에 답한다. 세 개가 비슷해 보이지만, 실행 시점, 접근 가능한 정보, 예외 전파 경로, 테스트 전략이 전부 다르다. 면접에서도 "필터와 인터셉터의 차이를 말해 달라", "왜 AOP를 쓰지 않고 필터에서 처리했나", "요청 바디 로깅은 어디에 두는 게 맞는가" 같은 형태로 반복적으로 등장한다.

시니어 백엔드 관점에서 이 주제를 제대로 답하려면, 세 기술을 각각 설명하는 것만으로는 부족하다. 각 계층이 **어느 객체에 접근 가능한가**, **Spring 컨텍스트의 어느 시점에 끼어드는가**, **예외를 어디서 잡을 수 있는가**, 그리고 **선택 기준이 무엇인가**를 한 줄로 말할 수 있어야 한다.

## 요청이 통과하는 계층 구조

Spring MVC 애플리케이션에서 하나의 HTTP 요청이 거쳐 가는 계층을 순서대로 늘어놓으면 다음과 같다.

```
Client
  ↓
Servlet Container (Tomcat 등)
  ↓
Filter Chain                      ← javax.servlet.Filter
  ↓
DispatcherServlet
  ↓
HandlerInterceptor.preHandle      ← Spring MVC Interceptor
  ↓
@ControllerAdvice / ArgumentResolver
  ↓
Controller Method                 ← 여기 진입 전/후/주변에 AOP 적용 가능
  ↓
Service (@Transactional, @Cacheable 등) ← AOP proxy
  ↓
Repository
  ↓
Controller Method 복귀
  ↓
HandlerInterceptor.postHandle / afterCompletion
  ↓
Filter (응답 단계, chain.doFilter 이후)
  ↓
Client
```

이 그림이 세 기술의 차이를 거의 다 설명해 준다.

- **Filter**는 `DispatcherServlet` 바깥, 서블릿 컨테이너 레벨에 있다. 즉 Spring이 이 요청을 어떤 핸들러에 라우팅할지 아직 모른다.
- **Interceptor**는 `DispatcherServlet` 내부, 핸들러 매핑이 끝난 뒤에 실행된다. 어떤 컨트롤러/메서드로 갈지 이미 알고 있다.
- **AOP**는 Spring Bean 메서드 호출 주변에 프록시를 감싸는 방식이다. HTTP 요청인지 백그라운드 스케줄러인지조차 상관없다.

이 순서를 머릿속에 고정해 두면, "이 작업은 어디 두는 게 맞는가" 판단이 거의 자동으로 내려진다.

## Filter: 서블릿 레벨의 가장 바깥 관문

Filter는 Servlet 스펙(`javax.servlet.Filter` / `jakarta.servlet.Filter`)의 일부다. Spring에서 만든 게 아니라 Tomcat 같은 서블릿 컨테이너가 실행해 준다. Spring Security의 `SecurityFilterChain`이 Filter로 구현되어 있는 이유가 바로 이것이다 — 인증/인가는 `DispatcherServlet`에 도달하기 전에 끝나야 하는 일이다.

Filter가 다루기 좋은 일:

- 인증 토큰 검증(Spring Security가 하는 일)
- 요청 ID / Correlation ID 생성 및 `MDC` 주입
- 요청/응답 바디 로깅(단, 바디 소비 문제를 주의)
- CORS, XSS, 문자셋 인코딩 강제
- 요청 단위 메트릭 수집(전체 지연, 상태 코드)

Filter의 특징:

- `ServletRequest`/`ServletResponse` 수준에서 다룬다. 즉 어떤 컨트롤러 메서드가 호출될지 아직 모른다.
- 요청 바디는 `InputStream`으로 한 번만 읽힌다. 바디를 로깅하려면 `ContentCachingRequestWrapper` 같은 래퍼로 감싸야 한다.
- Spring의 `@ControllerAdvice` 예외 핸들러가 Filter 단계 예외를 잡지 못한다. 여기서 던진 예외는 서블릿 컨테이너의 기본 에러 페이지로 떨어진다.
- Bean 주입은 가능하지만, `OncePerRequestFilter`를 상속하는 게 사실상 표준이다.

```java
@Component
@Slf4j
public class RequestIdFilter extends OncePerRequestFilter {

    private static final String HEADER = "X-Request-Id";
    private static final String MDC_KEY = "requestId";

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain)
            throws ServletException, IOException {
        String requestId = Optional.ofNullable(request.getHeader(HEADER))
                .filter(s -> !s.isBlank())
                .orElseGet(() -> UUID.randomUUID().toString());

        MDC.put(MDC_KEY, requestId);
        response.setHeader(HEADER, requestId);
        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }
}
```

이 코드가 왜 Filter여야 하는가? Interceptor에 둘 경우 `DispatcherServlet`이 매핑 실패 시점에 찍는 로그에는 requestId가 비어 있다. Filter에 두면 컨트롤러 매핑 실패, 404, 예외 처리 과정에서 찍히는 로그까지 전부 같은 requestId로 묶인다. 이런 "로그 전부를 묶어 줘야 한다"가 Filter의 대표 근거다.

## Interceptor: Spring MVC 핸들러를 아는 지점

`HandlerInterceptor`는 Spring MVC가 제공하는 개념이다. `DispatcherServlet` 안에서 동작하고, 핸들러 매핑이 끝난 후 실행되기 때문에 **어떤 컨트롤러의 어떤 메서드가 호출될지** 이미 알고 있다. `preHandle`의 세 번째 파라미터가 `Object handler`인 이유다. 실제로는 `HandlerMethod`로 캐스팅해서 해당 메서드의 어노테이션을 꺼내 쓰는 패턴이 많다.

Interceptor가 다루기 좋은 일:

- 특정 어노테이션이 붙은 컨트롤러 메서드에만 적용되는 권한/검증
- URL 패턴 기반 접근 제어 (Spring Security를 쓰지 않는 간단한 프로젝트)
- 컨트롤러 단 진입/종료 로깅, 수행 시간 측정
- 모델에 공통 값 주입 (`postHandle`에서 `ModelAndView` 수정)

```java
@Component
public class RequireInternalTokenInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request,
                             HttpServletResponse response,
                             Object handler) {
        if (!(handler instanceof HandlerMethod handlerMethod)) {
            return true;
        }
        RequireInternalToken annotation =
                handlerMethod.getMethodAnnotation(RequireInternalToken.class);
        if (annotation == null) {
            return true;
        }
        String token = request.getHeader("X-Internal-Token");
        if (!isValid(token)) {
            throw new UnauthorizedException("internal token invalid");
        }
        return true;
    }

    private boolean isValid(String token) { /* ... */ return true; }
}

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    private final RequireInternalTokenInterceptor interceptor;

    public WebMvcConfig(RequireInternalTokenInterceptor interceptor) {
        this.interceptor = interceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(interceptor)
                .addPathPatterns("/internal/**");
    }
}
```

Interceptor에서 던진 예외는 `@ControllerAdvice`가 받을 수 있다. Filter와 달리 Spring 예외 처리 파이프라인 안쪽에 있기 때문이다. 이 차이가 실무에서 자주 결정 기준이 된다 — "이 예외를 JSON 응답 포맷으로 변환해서 돌려주고 싶다"면 Interceptor가 편하다.

한편 Interceptor는 **요청 바디**에 직접 접근하기에 애매한 위치다. 바디 파싱은 `HandlerAdapter`가 컨트롤러 진입 직전에 수행하므로, `preHandle`에서 `getInputStream()`을 읽어 버리면 컨트롤러 `@RequestBody` 바인딩이 깨진다. 요청 바디를 들여다봐야 한다면 Filter에서 `ContentCachingRequestWrapper`로 감싸 두고, Interceptor나 AOP는 그 래핑된 캐시를 다시 읽는 패턴이 안전하다.

## AOP: Bean 메서드 호출 주변의 프록시

Spring AOP는 HTTP와 직접 상관이 없다. Spring이 관리하는 Bean 메서드 호출 주위에 프록시를 씌워서, `@Before`, `@After`, `@Around` 시점에 부가 로직을 끼워 넣는 구조다. `@Transactional`, `@Cacheable`, `@Async`가 모두 이 메커니즘 위에서 동작한다.

AOP가 다루기 좋은 일:

- 서비스 레이어 메서드 단위의 감사 로그, 실행 시간 측정
- 커스텀 어노테이션 기반의 권한 체크 (`@RequireRole("ADMIN")`)
- 재시도(Retry), 회로 차단기(Circuit Breaker) 같은 정책성 부가 로직
- 메서드 파라미터/반환값 기반의 캐시 키 생성

```java
@Aspect
@Component
@Slf4j
public class ExecutionTimeAspect {

    @Around("@annotation(com.example.monitor.LogExecutionTime)")
    public Object measure(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.nanoTime();
        try {
            return pjp.proceed();
        } finally {
            long tookMs = (System.nanoTime() - start) / 1_000_000;
            log.info("method={} tookMs={}",
                    pjp.getSignature().toShortString(), tookMs);
        }
    }
}
```

AOP가 Filter/Interceptor와 결정적으로 다른 점은 두 가지다.

1. **HTTP 요청 외부에서도 동작한다.** `@Scheduled` 메서드, `@KafkaListener` 메서드, 단순 서비스 호출에도 붙는다. "컨트롤러로 들어왔든 카프카 컨슈머로 들어왔든 이 서비스 호출은 감사 로그를 남기고 싶다"가 AOP의 자리다.
2. **프록시 기반이다.** 같은 Bean 내부에서 `this.someMethod()`로 자기 자신을 호출하면 프록시를 거치지 않아 Advice가 동작하지 않는다. 이 "self-invocation" 함정은 실무에서 가장 자주 부딪히는 버그 원인이다.

```java
@Service
public class OrderService {

    @Transactional
    public void placeOrder(Order order) {
        validate(order);
        saveInternal(order); // ← 같은 Bean 내부 호출. @Transactional 재시작 안 됨.
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void saveInternal(Order order) { /* ... */ }
}
```

이 코드에서 `saveInternal`의 `REQUIRES_NEW`는 동작하지 않는다. `placeOrder`가 같은 인스턴스의 메서드를 직접 호출하면 프록시를 경유하지 않기 때문이다. 해결은 자기 자신을 Bean으로 주입받아 호출하거나, `saveInternal`을 별도 Bean으로 분리하는 것이다.

## 잘못된 선택 vs 개선된 선택

### 사례 1: 요청 바디 로깅을 Interceptor에 둔 경우

```java
// Bad: Interceptor에서 바디를 읽어 버림
public boolean preHandle(...) {
    String body = new String(request.getInputStream().readAllBytes());
    log.info("body={}", body);
    return true;
}
```

`@RequestBody`가 비어 있는 상태로 컨트롤러가 호출된다. InputStream은 한 번만 읽힌다.

```java
// Improved: Filter에서 캐싱 래퍼를 씌우고, 실제 로깅은 체인 이후에
public class BodyLoggingFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain)
            throws ServletException, IOException {
        ContentCachingRequestWrapper wrapped =
                new ContentCachingRequestWrapper(request);
        chain.doFilter(wrapped, response);
        log.info("body={}", new String(wrapped.getContentAsByteArray()));
    }
}
```

`ContentCachingRequestWrapper`는 스트림을 읽으면서 내부에 바이트를 저장해 두기 때문에, 컨트롤러의 `@RequestBody` 바인딩과 로깅 모두 동일한 바디를 볼 수 있다.

### 사례 2: 권한 체크를 AOP로 구현했는데 self-invocation에 당한 경우

```java
// Bad: 내부 호출로 AOP 우회
@Service
public class ReportService {
    @RequireRole("ADMIN")
    public Report get(Long id) { /* ... */ }

    public List<Report> getAll(List<Long> ids) {
        return ids.stream().map(this::get).toList(); // 권한 체크 안 걸림
    }
}
```

```java
// Improved: 외부 진입점에만 어노테이션을 두고, 내부 호출은 일반 메서드로
@Service
public class ReportService {
    @RequireRole("ADMIN")
    public List<Report> getAll(List<Long> ids) {
        return ids.stream().map(this::getInternal).toList();
    }

    private Report getInternal(Long id) { /* ... */ }
}
```

권한 체크 어노테이션은 "외부에서 들어올 수 있는 진입점"에만 붙이는 게 원칙이다. 내부 로직 호출은 같은 보호가 보장된 컨텍스트 안이므로 중복 체크가 오히려 혼란을 만든다.

### 사례 3: 인증을 Interceptor에 구현한 경우

```java
// Bad: 인증을 HandlerInterceptor에 둠
public boolean preHandle(...) {
    if (!tokenService.isValid(request.getHeader("Authorization"))) {
        response.setStatus(401);
        return false;
    }
    return true;
}
```

이 구성은 `DispatcherServlet`이 핸들러 매핑에 실패한 경로(예: 존재하지 않는 API), 정적 리소스 서빙, 에러 페이지 등에서 인증이 적용되지 않는다. 또한 Filter 체인에 있는 로깅/트레이싱이 "인증되지 않은 요청"도 이미 기록해 버린 뒤다.

인증은 Filter 계층, 특히 Spring Security의 `SecurityFilterChain`에서 처리하는 것이 표준이다. Interceptor는 "이미 인증된 사용자"를 전제로 하는 세부 권한 검증에 쓴다.

## 선택 기준 한 줄 정리

- 요청 **진입 자체**를 막거나, **모든 요청**에 공통 적용되어야 하는 것 → **Filter**
- **컨트롤러 메서드가 누구인지 알아야** 동작 가능한 것 (어노테이션 기반 등) → **Interceptor**
- HTTP와 무관하게 **Bean 메서드 호출 주변**을 감싸야 하는 것, 또는 **서비스 레이어**의 횡단 관심사 → **AOP**

## 로컬 실습 환경

Spring Boot 3.x, Java 17 기준. `build.gradle.kts`의 최소 의존성:

```kotlin
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-aop")
    implementation("org.projectlombok:lombok")
    annotationProcessor("org.projectlombok:lombok")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}
```

실습 프로젝트 구조:

```
src/main/java/com/example/pipeline/
  filter/RequestIdFilter.java
  interceptor/RequireInternalTokenInterceptor.java
  aop/ExecutionTimeAspect.java
  web/WebMvcConfig.java
  web/SampleController.java
  web/LogExecutionTime.java
  web/RequireInternalToken.java
```

실행 후 호출:

```bash
curl -i -H "X-Internal-Token: ok" http://localhost:8080/internal/ping
curl -i http://localhost:8080/public/ping
```

로그를 보면 순서가 다음과 같이 나온다.

```
[requestId=...] RequestIdFilter doFilterInternal before chain
[requestId=...] RequireInternalTokenInterceptor preHandle
[requestId=...] ExecutionTimeAspect around start
[requestId=...] SampleController.ping invoked
[requestId=...] ExecutionTimeAspect around end tookMs=...
[requestId=...] RequireInternalTokenInterceptor afterCompletion
[requestId=...] RequestIdFilter doFilterInternal after chain
```

이 로그를 직접 찍어 보는 게 세 계층의 실행 순서를 몸으로 이해하는 가장 빠른 길이다.

## 실전 실습 과제

1. `RequestIdFilter`가 `OncePerRequestFilter`를 상속하지 않고 단순 `Filter`로 구현되어 있을 때, `RequestDispatcher.forward`가 내부에서 일어나면 MDC에 requestId가 어떻게 되는지 확인한다.
2. `HandlerInterceptor.preHandle`에서 예외를 던진 뒤 `@RestControllerAdvice`로 잡아 보고, Filter에서 같은 예외를 던졌을 때와 응답 포맷이 어떻게 달라지는지 비교한다.
3. `@Transactional` 메서드를 같은 Bean 내부에서 호출했을 때 롤백이 동작하지 않는 상황을 재현하고, 자기 자신을 `@Lazy`로 주입받아 해결한다.
4. `@LogExecutionTime`을 `@Repository` 메서드에 붙였을 때와 `@Service` 메서드에 붙였을 때의 측정값 차이를 본다 — `@Transactional`이 감싸는 범위까지 포함되는지 확인한다.
5. `ContentCachingRequestWrapper`와 `ContentCachingResponseWrapper`를 Filter에 도입해 요청/응답 바디를 둘 다 로깅하고, 바이너리 응답(이미지 등)에서 메모리 문제가 생기는 패턴을 재현한다.

## 자주 틀리는 지점

- Filter에서 던진 예외를 `@ControllerAdvice`가 잡아 줄 것이라 기대하는 실수
- `@RequestBody`를 쓰면서 Interceptor에서 바디를 미리 읽어 버리는 실수
- AOP를 같은 클래스 내부 호출에 걸고 동작한다고 믿는 실수
- `@Transactional`을 `private` 메서드에 붙이는 실수 (프록시가 가로챌 수 없다)
- 인증을 Interceptor에 두고 "왜 정적 리소스에는 안 걸리냐"고 디버깅하는 실수
- Interceptor에서 `HttpServletResponse`에 수동으로 바디를 써 두고 `return false`로 끝냈는데, 이후 Filter에서 응답을 다시 감싸는 로직과 충돌하는 실수

## 면접 답변 프레이밍

면접에서 "필터, 인터셉터, AOP의 차이가 무엇인가" 질문이 나오면, 암기한 정의를 늘어놓기보다 **경험 맥락**을 끼워서 답하는 편이 훨씬 설득력 있다. 시니어 백엔드로서의 모범 답변 흐름은 다음과 같다.

> 세 기술은 실행 위치와 알고 있는 정보의 범위가 다릅니다. Filter는 서블릿 컨테이너 레벨에서, DispatcherServlet보다 바깥에서 동작합니다. 그래서 어느 컨트롤러로 라우팅될지 아직 모르는 상태고, 모든 요청에 공통으로 걸고 싶은 것 — 예를 들면 requestId 주입, 인증, 요청/응답 바디 캐싱 — 을 여기 둡니다.
>
> Interceptor는 DispatcherServlet 안쪽에서, 핸들러 매핑이 끝난 뒤에 실행됩니다. HandlerMethod에 접근할 수 있기 때문에 "특정 어노테이션이 붙은 컨트롤러에만 적용되는 권한 체크" 같은, 핸들러를 알아야 가능한 일에 씁니다. Spring의 예외 처리 파이프라인 안쪽이기 때문에 @ControllerAdvice로 예외를 일괄 변환하기도 좋습니다.
>
> AOP는 HTTP와 상관없이 Spring Bean 메서드 호출 주변에 프록시를 씌우는 메커니즘입니다. 컨트롤러뿐 아니라 스케줄러나 Kafka 컨슈머 진입점에도 똑같이 붙일 수 있다는 점이 Filter/Interceptor와 결정적으로 다릅니다. 실행 시간 측정이나 커스텀 어노테이션 기반 정책 같은, 서비스 레이어 횡단 관심사에 적합합니다.
>
> 실무에서는 한 가지를 고르는 게 아니라 겹쳐 씁니다. 인증은 Spring Security Filter로, 내부 API 토큰 같은 핸들러별 추가 체크는 Interceptor로, 도메인 서비스 단의 감사 로그와 실행 시간 측정은 AOP로 분리하는 조합이 가장 유지보수하기 좋았습니다.

이어서 "그럼 요청 바디 로깅은 어디 둘 건가요?" 같은 후속 질문이 나오면 **바디 스트림이 한 번만 읽힌다는 제약**을 언급하고, Filter에서 `ContentCachingRequestWrapper`로 감싼 뒤 체인 이후 로깅하는 패턴을 답하면 된다. "AOP를 쓰는데 왜 @Transactional이 동작 안 하나요?"라는 질문에는 **self-invocation으로 프록시를 우회하는 현상**을 설명하는 것이 핵심이다.

## 체크리스트

- [ ] Filter, Interceptor, AOP의 실행 위치를 DispatcherServlet 기준으로 그릴 수 있다
- [ ] 각 계층이 접근 가능한 객체(Servlet API, HandlerMethod, JoinPoint)를 구분할 수 있다
- [ ] Filter에서 던진 예외와 Interceptor/Controller에서 던진 예외가 `@ControllerAdvice`에 도달하는지 여부를 말할 수 있다
- [ ] `OncePerRequestFilter`가 필요한 이유(forward/include 시 중복 실행 방지)를 안다
- [ ] `ContentCachingRequestWrapper`를 써서 바디 로깅을 구현할 수 있다
- [ ] Spring AOP의 self-invocation 한계를 설명하고 해결책을 두 가지 이상 댈 수 있다
- [ ] `@Transactional`이 private 메서드와 final 메서드에서 왜 동작하지 않는지 설명할 수 있다
- [ ] 인증/권한을 Filter vs Interceptor vs AOP에 둘 때의 trade-off를 한 문장씩 말할 수 있다
- [ ] Filter, Interceptor, AOP를 한 요청에서 모두 거치는 로그 흐름을 실제로 찍어 본 경험이 있다
- [ ] AOP로 실행 시간을 측정하는 `@Around` 어드바이스를 직접 작성할 수 있다
