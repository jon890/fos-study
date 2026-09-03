---
tags: [study]
---

# Filter, Interceptor, AOP: Spring 요청 처리 파이프라인에서의 관심사 분리

## 왜 이 주제가 중요한가

Spring 기반 백엔드에서는 로깅, 인증, 요청 ID 주입, 성능 측정처럼 핵심 로직과 직접 관계없는 요구가 반복된다.
이때 중요한 질문은 "횡단 관심사를 어느 계층에 둘 것인가"다.

Filter, Interceptor, AOP는 실행 위치와 접근 가능한 정보가 다르다.
기술의 정의보다 다음 선택 기준을 먼저 이해해야 한다.

- 요청 전체에 적용해야 하는가
- 어떤 컨트롤러 메서드인지 알아야 하는가
- HTTP와 무관한 Bean 메서드에도 적용해야 하는가
- 발생한 예외를 어느 처리 경계에서 변환해야 하는가

## 요청이 통과하는 계층 구조

Spring MVC 애플리케이션에서 하나의 HTTP 요청이 거쳐 가는 계층을 순서대로 늘어놓으면 다음과 같다.

```
Client
  ↓
Servlet Container (Tomcat 등)
  ↓
Filter Chain                      ← jakarta.servlet.Filter
  ↓
DispatcherServlet
  ↓
HandlerMapping / HandlerExecutionChain
  ↓
HandlerInterceptor.preHandle      ← Spring MVC Interceptor
  ↓
ArgumentResolver
  ↓
Controller Method                 ← 여기 진입 전/후/주변에 AOP 적용 가능
  ↓
Service (@Transactional, @Cacheable 등) ← AOP proxy
  ↓
Repository
  ↓
Controller Method 복귀
  ↓
HandlerInterceptor.postHandle (정상 처리) / afterCompletion (완료)
  ↓
Filter (응답 단계, chain.doFilter 이후)
  ↓
Client

Handler 매핑·실행 예외
  → HandlerExceptionResolver / @ControllerAdvice
```

- **Filter**는 `DispatcherServlet` 바깥, 서블릿 컨테이너 레벨에 있다. 즉 Spring이 이 요청을 어떤 핸들러에 라우팅할지 아직 모른다.
- **Interceptor**는 `DispatcherServlet` 내부, 핸들러 매핑이 끝난 뒤에 실행된다. 어떤 컨트롤러/메서드로 갈지 이미 알고 있다.
- **AOP**는 Spring Bean 메서드 호출 주변에 프록시를 감싸는 방식이다. HTTP 요청인지 백그라운드 스케줄러인지조차 상관없다.

## Filter: 서블릿 레벨의 가장 바깥 관문

Filter는 Servlet 스펙의 일부이며 서블릿 컨테이너가 실행한다.
Spring Boot 3 이상에서는 `jakarta.servlet.Filter`를 사용한다.
Spring Security의 `SecurityFilterChain`도 이 계층에서 요청을 처리한다.

Filter가 다루기 좋은 일:

- Spring Security를 통한 인증
- 요청 ID 생성과 `MDC` 주입
- 요청과 응답 본문 로깅
- CORS와 문자셋 처리
- 요청 전체 지연과 상태 코드 측정

Filter의 특징:

- `ServletRequest`/`ServletResponse` 수준에서 다룬다. 즉 어떤 컨트롤러 메서드가 호출될지 아직 모른다.
- 요청 본문 스트림은 한 번만 읽을 수 있으므로 캐싱 래퍼가 필요하다.
- Filter에서 발생한 예외는 MVC의 `@ControllerAdvice`가 자동으로 처리하지 않는다.
- 비동기·오류 디스패치의 중복 실행을 제어해야 한다면 `OncePerRequestFilter`가 유용하다.

요청 ID는 핸들러 매핑 실패와 오류 처리 로그까지 묶어야 한다.
따라서 Interceptor보다 Filter에 두는 편이 자연스럽다.

## Interceptor: Spring MVC 핸들러를 아는 지점

`HandlerInterceptor`는 Spring MVC가 제공한다.
핸들러 매핑이 끝난 뒤 실행되므로 `HandlerMethod`를 통해 컨트롤러와 메서드 정보를 확인할 수 있다.

Interceptor가 다루기 좋은 일:

- 특정 어노테이션이 붙은 컨트롤러 메서드의 부가 검증
- 컨트롤러 진입과 종료 로깅
- 컨트롤러 수행 시간 측정
- 뷰 렌더링 전에 모델에 공통 값 주입

Interceptor에서 발생한 예외는 `DispatcherServlet`의 예외 처리 흐름을 거치므로 `@ControllerAdvice`로 변환할 수 있다.
일관된 JSON 오류 응답이 필요한 핸들러별 검증이라면 Filter보다 다루기 쉽다.

반면 `preHandle`에서 요청 본문 스트림을 읽으면 이후 `@RequestBody` 바인딩이 깨질 수 있다.
본문 로깅은 Filter에서 캐싱 래퍼를 적용하고 요청 처리가 끝난 뒤 읽는 편이 안전하다.

## AOP: Bean 메서드 호출 주변의 프록시

Spring AOP는 HTTP가 아니라 Spring Bean의 메서드 실행을 가로챈다.
`@Transactional`, `@Cacheable`, `@Async` 같은 기능도 프록시 기반으로 적용된다.

AOP가 다루기 좋은 일:

- 서비스 메서드 단위의 감사 로그와 실행 시간 측정
- 커스텀 어노테이션 기반의 감사와 정책 적용
- 재시도와 회로 차단기 같은 정책성 부가 로직
- 메서드 파라미터/반환값 기반의 캐시 키 생성

AOP는 스케줄러나 메시지 소비자에서 호출되는 서비스 메서드처럼 HTTP 요청 밖에서도 적용할 수 있다.
반면 같은 Bean 안에서 `this.someMethod()`로 호출하면 프록시를 거치지 않아 Advice가 적용되지 않는다.

프록시 선택과 자기 호출 문제는 [Spring AOP와 프록시](./spring-aop-proxies-deep-dive.md)에서 자세히 다룬다.
트랜잭션에 미치는 영향은 [Spring Data JPA 트랜잭션 흔한 실수들](./jpa-transaction.md)을 참고한다.

## 자주 잘못 배치하는 사례

### 요청 본문 로깅을 Interceptor에 둔다

`preHandle`에서 요청 스트림을 읽으면 컨트롤러가 읽을 본문이 사라진다.
Filter에서 `ContentCachingRequestWrapper`로 감싼 뒤, 요청 처리가 본문을 읽은 다음 캐시를 확인해야 한다.

래퍼는 본문을 미리 읽어 캐시하지 않는다.
따라서 Filter 체인 실행 전에는 캐시가 비어 있을 수 있다.

응답에 `ContentCachingResponseWrapper`를 사용했다면 마지막에 `copyBodyToResponse()`를 호출해야 실제 응답 본문이 전달된다.
대용량·바이너리·민감 정보는 로깅 대상에서 제외하거나 크기를 제한한다.

### 인증을 Interceptor에 둔다

인증은 MVC 핸들러보다 먼저 적용되어야 한다.
따라서 Spring Security의 `SecurityFilterChain`에 두고, Interceptor는 인증된 사용자를 전제로 한 핸들러별 부가 검증에 사용한다.

실제 Interceptor 활용 사례는 [점검 모드 화이트리스트](../../task/sb-dev-team/whitelist.md)에서 확인할 수 있다.

### 메서드 권한 검사를 AOP에만 의존한다

같은 Bean 내부 호출은 프록시를 우회할 수 있다.
보안 경계를 AOP 어노테이션 하나에만 맡기지 말고 외부 진입점에서 먼저 차단한다.
서비스 메서드 수준의 검사가 필요하다면 호출 경계와 자기 호출 여부를 함께 검증한다.

## 선택 기준 한 줄 정리

- 요청 **진입 자체**를 막거나, **모든 요청**에 공통 적용되어야 하는 것 → **Filter**
- **컨트롤러 메서드 정보**가 필요한 것 → **Interceptor**
- HTTP와 무관한 **Bean 메서드 실행**을 감싸야 하는 것 → **AOP**

세 가지를 함께 쓰는 것도 자연스럽다.
예를 들어 인증은 Filter, 핸들러별 검증은 Interceptor, 서비스 실행 시간 측정은 AOP로 나눌 수 있다.

## 검증 방법

동작 경계를 확인하려면 다음 순서로 로그를 남긴다.

1. Filter의 `chain.doFilter` 호출 전후
2. Interceptor의 `preHandle`과 `afterCompletion`
3. AOP의 `@Around` 실행 전후
4. 컨트롤러와 서비스 메서드 진입

다음 실패 사례도 직접 비교한다.

- Filter와 Interceptor에서 같은 예외를 던졌을 때의 응답 차이
- Interceptor에서 요청 본문을 읽었을 때 `@RequestBody` 바인딩 결과
- 같은 Bean 내부에서 AOP 대상 메서드를 호출했을 때 Advice 실행 여부

## 면접 답변 구조

차이는 실행 위치와 알고 있는 정보의 범위로 설명한다.

1. Filter는 `DispatcherServlet` 바깥에서 요청 전체를 다룬다.
2. Interceptor는 핸들러 매핑 이후 컨트롤러 정보를 활용한다.
3. AOP는 HTTP와 무관하게 Spring Bean 메서드 실행을 감싼다.
4. 실제 선택 사례와 해당 계층의 제약을 덧붙인다.

요청 본문 로깅 질문에는 스트림을 한 번만 읽을 수 있다는 제약을 설명한다.
AOP 적용 실패 질문에는 자기 호출이 프록시를 우회한다는 점을 설명한다.

## 관련 문서

- [Spring AOP와 프록시](./spring-aop-proxies-deep-dive.md)
- [Spring Data JPA 트랜잭션 흔한 실수들](./jpa-transaction.md)
- [점검 모드 화이트리스트](../../task/sb-dev-team/whitelist.md)
- [관측성 입문](../../architecture/observability-basics.md)

## 공식 참고 자료

- [Spring MVC Filters](https://docs.spring.io/spring-framework/reference/web/webmvc/filters.html)
- [Spring MVC Interception](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-servlet/handlermapping-interceptor.html)
- [ContentCachingRequestWrapper](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/web/util/ContentCachingRequestWrapper.html)
- [Spring AOP Proxying Mechanisms](https://docs.spring.io/spring-framework/reference/core/aop/proxying.html)
- [Spring Security Servlet Architecture](https://docs.spring.io/spring-security/reference/servlet/architecture.html)
