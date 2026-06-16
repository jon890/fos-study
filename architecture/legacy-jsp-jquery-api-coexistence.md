# [초안] 레거시 JSP/jQuery 화면과 신규 API가 공존하는 백엔드 운영 전략

## 왜 이 주제가 중요한가

식음료(F&B)·리테일·디지털 채널 같이 오랜 기간 운영된 서비스는 화면 한 장을 들춰보면 거의 항상 JSP/JSTL과 jQuery로 짜인 레거시 페이지가 나온다. 그 위에 모바일 앱과 SPA(React/Vue), 키오스크, 사이니지, 외부 파트너 연동, 그리고 사내 운영툴까지 겹겹이 쌓여 있다. 같은 주문/회원/쿠폰 도메인을 두고 서버 사이드 렌더링과 REST/JSON API가 동시에 살아 있고, 세션 인증과 토큰 인증이 한 시스템에서 같이 돌아간다.

외식 프랜차이즈 디지털 채널처럼 "기존 채널을 깨면 안 되면서, 새 채널을 빨리 붙여야 하는" 환경에서 백엔드의 진짜 역량은 새 기능을 잘 짜는 게 아니라 **레거시를 망가뜨리지 않으면서 새 흐름을 점진적으로 끼워 넣는 능력**이다. 중요한 건 "JSP를 잘 쓸 줄 아느냐"가 아니라 "JSP가 살아 있는 와중에 어떻게 안전하게 SPA/앱을 붙이고, 어떻게 잘라낼 계획을 가지고 있느냐"다. 이 문서는 그 관점에서 한 번에 정리한다.

JSP/jQuery 운영 경험이 적은 Spring 백엔드 개발자에게도 실용적이도록 구성했다. 핵심은 두 가지다. 첫째, 레거시 화면을 깊게 모르는 상태에서도 통제 가능한 경계를 긋는 방법. 둘째, "써본 적 없다"가 아니라 "공존시키는 운영 전략을 안다"로 설명을 구성하는 법.

## 핵심 개념

### 공존 환경의 전형적인 모양

전통적인 JSP/jQuery 시스템은 보통 다음 형태다.

- 서버는 톰캣 위 Spring MVC + JSP. Controller가 Model을 채우고 forward하면 JSP가 HTML을 렌더링한다.
- 화면 안에서 jQuery `$.ajax`로 같은 서버의 `/admin/order/list.do` 같은 엔드포인트를 호출한다. 이 엔드포인트는 흔히 JSON을 반환하지만 응답 포맷, 에러 코드, 상태 코드 규약이 일관성 없다.
- 인증은 `HttpSession` 기반. 로그인 시 세션에 사용자 정보가 들어가고, 인터셉터/필터가 세션을 보고 인가를 결정한다.
- CSRF는 hidden input의 토큰이나 별도 필터로 처리한다.

여기에 모바일 앱과 SPA가 추가되면 다음이 한 시스템에 겹친다.

- `/api/v1/orders` 같이 REST 규약을 지키는 새 API. 인증은 JWT 또는 OAuth2 Bearer.
- `/order/list.do`처럼 JSP 안에서만 부르던 ajax 엔드포인트.
- `/order/detail.jsp` 같은 렌더링 라우트.
- 외부 파트너 webhook, 사이니지, 키오스크용 별도 엔드포인트.

이 상태에서 잘못된 결정의 대부분은 **경계를 명확히 긋지 않았을 때** 발생한다.

### 경계 긋기: 화면용 ajax와 외부 API는 다른 종(species)다

먼저 분리해야 할 두 가지를 구분한다.

- **내부 화면용 ajax 엔드포인트**: 같은 도메인, 같은 세션, 같은 페이지 안에서만 쓰인다. CSRF 토큰이 자동으로 붙고, 응답 포맷이 흐트러져도 화면 한 곳만 깨진다.
- **퍼블릭/세미퍼블릭 API**: 모바일 앱, 외부 파트너, SPA, 사이니지처럼 별도 클라이언트가 호출한다. 버저닝이 필요하고, 인증·인가는 토큰 기반이며, 응답 포맷이 외부 계약(contract)이 된다.

레거시 환경에서 자주 일어나는 사고는 이 둘을 같은 컨트롤러, 같은 서비스, 같은 응답 DTO로 처리하다가, JSP 화면 편의를 위해 응답을 살짝 바꾼 게 모바일 앱 빌드를 깨뜨리는 식이다. 따라서 **공존 전략의 1번 원칙은 두 부류의 엔드포인트를 URL prefix, 모듈, 인증 체계, 응답 규약으로 분리하는 것**이다.

### 인증 공존: 세션과 토큰을 동시에 받기

가장 빈번한 결정 포인트다. 세 가지 패턴이 있다.

1. **세션 + 토큰을 같은 Spring Security 체인에서 처리**: 새 API 경로(`/api/**`)는 토큰 인증 필터, 레거시 경로는 기존 세션 필터. `SecurityFilterChain`을 두 개 만든다.
2. **API 게이트웨이/프론트 BFF가 세션-토큰 변환**: 외부에서 들어오는 토큰을 게이트웨이가 검증한 뒤, 백엔드에는 사용자 식별 헤더만 전달.
3. **세션을 그대로 두고 새 채널만 별도 서비스로 분리**: 모바일/SPA용 백엔드를 새로 만들어 격리.

처음에는 1번이 현실적이다. 두 번째와 세 번째는 트래픽이 일정 수준 이상이거나 도메인 분리가 명확해진 다음에 의미가 있다.

### Strangler Fig: 갑자기 다 못 바꾸니, 잘라먹는다

Strangler Fig 패턴은 마틴 파울러가 제안한 점진적 마이그레이션 전략으로, 레거시를 한 번에 갈아엎는 대신 새 시스템을 옆에 두고 **요청을 라우팅으로 나누어 점차 새 쪽으로 옮긴 뒤, 마지막에 레거시를 제거**하는 방식이다. 핵심은 "잘라낼 단위"를 정확히 잡는 것이다.

좋은 단위 예: 회원가입, 비밀번호 변경, 주문 조회 화면, 쿠폰 발급 페이지.
나쁜 단위 예: "주문 도메인 전체", "관리자 페이지 전체" — 너무 크고, 안에 비표준이 너무 많아 한 번에 끊을 수 없다.

라우팅은 보통 다음 중 하나로 한다.

- nginx/HAProxy의 location 매칭으로 `/order/new` 만 새 SPA로 보내고 나머지는 톰캣으로.
- Spring Cloud Gateway 같은 게이트웨이에서 path/header 기반 분기.
- 세션 안에 A/B 플래그를 넣어 일부 사용자만 새 화면으로 보내기.

## 실무 백엔드 활용

### 패키지/모듈 구조

레거시가 살아 있는 동안 코드 베이스가 누더기가 되는 이유는, 새로 만드는 컨트롤러를 옛 패키지 옆에 그냥 끼워넣기 때문이다. 권장 구조는 다음과 같다.

```
src/main/java/com/foo
├── legacy
│   ├── controller   // JSP forward + 화면 ajax
│   ├── interceptor  // 세션 기반 인터셉터
│   └── support      // 옛 코드가 의존하는 헬퍼
├── api
│   ├── v1
│   │   └── order    // REST 컨트롤러, 토큰 인증
│   └── v2
└── domain           // 두 쪽이 공유하는 도메인 서비스
```

핵심은 도메인 서비스(`domain.OrderService`)는 한 곳에 두고, 컨트롤러 계층만 두 갈래로 나누는 것이다. 두 컨트롤러 모두 같은 서비스를 호출하므로 비즈니스 규칙은 한 번만 작성·검증된다.

### 응답 규약 분리

레거시 ajax는 다음 같은 응답을 흔히 쓴다.

```json
{ "result": "OK", "data": {...}, "msg": "" }
```

새 API는 표준 HTTP 상태 코드 + Problem Details(`application/problem+json`) 또는 일관된 envelope을 쓴다. **두 규약을 한 컨트롤러가 동시에 만족시키려고 하면 어디선가 깨진다.** 응답 어드바이스를 prefix별로 다르게 적용한다.

```java
@RestControllerAdvice(basePackages = "com.foo.api")
public class ApiExceptionAdvice { ... }

@ControllerAdvice(basePackages = "com.foo.legacy")
public class LegacyAjaxExceptionAdvice { ... }
```

이렇게 두면 새 API는 RFC 7807 형식의 에러를 던지면서, 레거시 화면은 기존 jQuery 코드가 기대하는 `{result, msg}`를 유지할 수 있다.

### 인증 체인 구성

Spring Security 6 기준 두 체인 분리 예시다.

```java
@Configuration
public class SecurityConfig {

    @Bean
    @Order(1)
    SecurityFilterChain apiChain(HttpSecurity http) throws Exception {
        http.securityMatcher("/api/**")
            .csrf(c -> c.disable())
            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
            .authorizeHttpRequests(a -> a
                .requestMatchers("/api/v1/auth/**").permitAll()
                .anyRequest().authenticated())
            .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()));
        return http.build();
    }

    @Bean
    @Order(2)
    SecurityFilterChain legacyChain(HttpSecurity http) throws Exception {
        http.securityMatcher("/**")
            .csrf(Customizer.withDefaults())
            .authorizeHttpRequests(a -> a
                .requestMatchers("/login", "/css/**", "/js/**").permitAll()
                .anyRequest().authenticated())
            .formLogin(f -> f.loginPage("/login"))
            .sessionManagement(s -> s
                .maximumSessions(1)
                .expiredUrl("/login?expired"));
        return http.build();
    }
}
```

`@Order(1)`로 API 체인을 먼저 매칭시키고 STATELESS로 두면, 새 채널에 세션이 새로 발급되는 사고를 막을 수 있다. `securityMatcher`와 `requestMatchers`를 헷갈려 정책이 엉키는 게 흔한 실수다.

### CSRF와 SameSite

레거시 페이지의 jQuery ajax는 같은 도메인에서 호출하므로 세션 쿠키가 자동으로 실린다. 여기에 CSRF는 필수다. 반대로 토큰 기반 API는 쿠키가 아니라 `Authorization` 헤더를 쓰므로 CSRF는 불필요하지만, 만약 SPA가 세션 쿠키로 인증한다면 CSRF는 다시 살려야 한다. 또한 모바일 웹뷰에서 도메인이 분리되면 `SameSite=None; Secure` 설정과 CORS preflight가 정상 동작하는지 확인해야 한다.

## 잘못된 예 vs 개선된 예

### 예 1. 컨트롤러가 두 클라이언트를 동시에 책임짐

**잘못된 예**

```java
@Controller
public class OrderController {

    @RequestMapping("/order/list")
    public String list(Model model, HttpServletRequest req,
                       @RequestParam(required = false) String format) {
        var orders = orderService.find(currentUser(req));
        if ("json".equals(format)) {
            // 모바일 앱이 ?format=json 으로 호출
            req.setAttribute("orders", orders);
            return "forward:/order/listJson";
        }
        model.addAttribute("orders", orders);
        return "order/list"; // JSP
    }
}
```

같은 URL이 화면 렌더링과 모바일 JSON 응답을 query 파라미터로 분기한다. 곧 누군가 `format=json` 응답에 화면 편의를 위한 필드를 추가했다가 앱이 깨진다.

**개선된 예**

```java
// 화면 전용
@Controller
@RequestMapping("/order")
public class OrderViewController {
    @GetMapping("/list")
    public String list(Model model, @AuthenticationPrincipal SessionUser user) {
        model.addAttribute("orders", orderService.find(user.id()));
        return "order/list";
    }
}

// API 전용
@RestController
@RequestMapping("/api/v1/orders")
public class OrderApiController {
    @GetMapping
    public OrderListResponse list(@AuthenticationPrincipal JwtUser user) {
        return OrderListResponse.from(orderService.find(user.id()));
    }
}
```

### 예 2. JSP에서 직접 도메인 로직을 돌리는 경우

JSP `<c:if>`나 스크립틀릿 안에서 가격 계산, 권한 체크 같은 로직이 굴러다니는 경우가 흔하다. 새 API에서 같은 화면 데이터를 만들면 결과가 달라진다.

**개선 방향**: 이런 로직은 도메인 서비스로 끌어내려 한 번만 구현하고, JSP는 결과만 출력하게 만든다. JSP 안의 비즈니스 로직을 발견했을 때의 원칙은 명확하다. 당장 다 옮기는 게 아니라, 새 채널이 같은 화면을 그릴 때 양쪽이 같은 결과가 되도록 도메인 함수로 추출하고, JSP는 그것만 호출하게 점진적으로 정리한다.

### 예 3. 레거시 ajax가 도메인 이벤트를 직접 호출

```javascript
$.ajax({ url: "/admin/coupon/issue.do", data: {...} });
```

이 엔드포인트가 내부에서 외부 결제 API, 푸시 발송, 통계 적재까지 동시에 호출하면, 새 API에서 같은 동작을 재현할 때 부작용을 빠뜨리기 쉽다.

**개선 방향**: 컨트롤러가 직접 부수 효과를 일으키지 않게 한다. 도메인 서비스가 이벤트를 발행하고(`ApplicationEventPublisher` 또는 Kafka), 부수 효과는 별도 리스너에서 처리한다. 그러면 새 API 컨트롤러는 같은 서비스만 호출해도 동일한 후속 흐름을 보장할 수 있다.

## 로컬 실습 환경

신규 API와 레거시 JSP가 공존하는 환경을 단일 머신에서 재현하려면 다음 정도면 충분하다.

- JDK 17, Spring Boot 3.x
- 톰캣 임베디드 + JSP 지원: `spring-boot-starter-web` + `org.apache.tomcat.embed:tomcat-embed-jasper`, `jakarta.servlet:jstl`
- nginx 또는 Spring Cloud Gateway 1대(점진 라우팅 실습용)
- MySQL 8 (도메인 데이터)
- Redis (세션 클러스터링 흉내)
- 테스트 클라이언트로 jQuery ajax는 단순 정적 페이지로, API 클라이언트는 `httpie` 또는 Postman

`application.yml` 핵심:

```yaml
spring:
  mvc:
    view:
      prefix: /WEB-INF/views/
      suffix: .jsp
  session:
    store-type: redis
server:
  servlet:
    session:
      cookie:
        same-site: lax
        http-only: true
        secure: true
```

## 실습용 예제

### 두 채널이 공유하는 도메인 서비스

```java
@Service
@RequiredArgsConstructor
public class OrderService {
    private final OrderRepository repo;

    public List<OrderSummary> find(long userId) {
        return repo.findRecent(userId).stream()
            .map(OrderSummary::from)
            .toList();
    }
}
```

JSP 컨트롤러와 REST 컨트롤러가 같은 서비스만 호출하도록 강제하는 것이 첫 번째 실습 목표다.

### 점진 라우팅 실습

nginx 설정으로 `/order/new` 만 새 SPA로 보내본다.

```nginx
location /order/new {
    proxy_pass http://spa-upstream;
}
location / {
    proxy_pass http://legacy-tomcat;
}
```

이렇게 두면 한 페이지만 새 화면으로 잘라낸 효과를 볼 수 있다. 세션 쿠키가 두 업스트림에서 같이 통하도록 도메인을 동일하게 유지하는 부분이 실전에서 중요하다.

### 인증 공존 검증 시나리오

- 시나리오 A: 브라우저로 로그인 후 `/order/list.jsp` 진입 → 200, JSP 렌더링.
- 시나리오 B: 같은 브라우저에서 `/api/v1/orders` 호출 → 401(쿠키 무시, 토큰 없음). 의도한 동작이다.
- 시나리오 C: `/api/v1/auth/login`으로 토큰 발급 후 `Authorization: Bearer ...`로 호출 → 200.
- 시나리오 D: 모바일 앱에서 토큰만 들고 `/order/list.jsp` 호출 → 302 리다이렉트. 화면용 경로는 모바일에서 호출하지 않는다는 계약을 코드로 못 박은 셈이다.

이 네 시나리오가 바뀌지 않게 하는 통합 테스트를 두면 인증 체인이 흐트러지는 사고를 거의 다 잡는다.

### Strangler Fig 단위 절단 실습

회원가입 한 화면만 SPA로 옮긴다고 가정하고 다음 순서로 진행한다.

1. 새 SPA에서 호출할 `/api/v1/signup` 작성, 도메인 서비스는 기존 것 재사용.
2. 통합 테스트로 새 API가 기존 JSP 가입과 동일한 결과(이메일 발송, 약관 기록, 포인트 적립)를 만드는지 검증.
3. nginx에서 `/signup`만 SPA로 라우팅. 기존 JSP 경로는 잠시 유지.
4. 일정 기간 모니터링 후 JSP 가입 페이지를 410 Gone으로 내리고 코드 제거.

이 4단계를 머리로만 그리지 말고 한 번 손으로 굴려보면, Strangler Fig를 어떻게 적용하는지 구체적인 사례로 설명할 수 있다.

## 테스트와 모니터링

레거시 공존 환경의 테스트는 단위 테스트보다 **계약 테스트와 회귀 테스트**가 핵심이다.

- 도메인 서비스에는 단위 테스트를 두텁게.
- 컨트롤러 계층은 `MockMvc`로 응답 envelope과 상태 코드 회귀 테스트.
- 외부 계약(앱/SPA가 의존하는 API)은 Pact 또는 OpenAPI 스냅샷 테스트로 응답 스키마가 깨지지 않는지 검증.
- 레거시 JSP는 Selenium/Playwright로 핵심 플로우 몇 개만 골라 e2e.

모니터링은 **레거시 경로와 새 경로의 메트릭을 분리**하는 게 핵심이다. URL 패턴별 응답시간/에러율을 따로 보고, 새 API로 트래픽이 옮겨갈수록 레거시 쪽 호출이 줄어드는지를 추적한다. 그래프가 그려지지 않으면 점진 마이그레이션을 했다고 말할 수 없다.

장애 대응 측면에서는 다음을 미리 정해 둔다.

- 새 API에서 문제가 생기면 nginx 설정 한 줄로 레거시 경로로 되돌릴 수 있는가?
- 세션 저장소(Redis)가 죽으면 로그인 화면이 어떻게 동작하는가?
- 토큰 검증 실패가 폭증할 때 새 API가 캐시에 의존하는지, 매 요청 JWT 파싱하는지.

## 보안 체크리스트

- 레거시 ajax 엔드포인트에 CSRF 토큰이 강제되는가.
- 새 API는 STATELESS인가, 세션 쿠키가 새로 발급되지 않는가.
- 토큰 만료/회전 정책이 명시되어 있는가.
- JSP 화면 안의 출력에 `<c:out>` 또는 `${fn:escapeXml(...)}`이 들어가 XSS가 막히는가.
- 새 API의 입력은 Bean Validation과 도메인 검증을 모두 통과하는가.
- 레거시·신규 둘 다 같은 인가 규칙을 갖는가(같은 사용자가 양쪽에서 같은 자원을 보거나 못 보는지).
- SQL Injection: 레거시 MyBatis 매퍼에 `${}` 바인딩이 남아 있는지 grep로 한 번 훑기.
- 모니터링 로그에 토큰/세션 ID/주민번호 등이 평문으로 찍히지 않는지.

## 정리 — 공존 운영 전략의 핵심

JSP/jQuery 실무 경험이 적은 Java/Spring 백엔드 개발자라면, 초점을 "기술 사용 경험" 축이 아니라 "공존 운영 전략" 축으로 옮기는 게 핵심이다.

**JSP 환경 운영을 깊이 해보지 않았을 때**

JSP를 깊이 운영해본 경험이 적더라도, 모놀리식 Spring MVC 위에 모바일 API를 추가하는 작업에서 화면 렌더링 경로와 외부 API 경로를 분리해 운영하는 전략은 그대로 적용된다. 구체적으로는 Spring Security 체인을 두 개로 나눠 STATELESS API와 세션 기반 화면을 격리하고, 응답 어드바이스를 prefix 단위로 분리해 외부 계약과 내부 ajax 응답이 서로의 변경에 휘둘리지 않도록 한다. JSP 자체에 대해서는 스크립틀릿 비즈니스 로직을 도메인 서비스로 빼내는 작업과 점진적 마이그레이션 패턴(Strangler Fig)을 익혀 두면, 기존 화면을 학습하면서 새 채널 쪽 변경부터 책임지는 순서로 접근할 수 있다.

**레거시 화면이 살아 있는데 모바일 앱을 새로 붙일 때**

1. 인증 정책부터 정한다. 세션 vs 토큰을 어디서 끊을지 결정.
2. URL prefix와 응답 규약을 분리한다(`/api/v1/**`).
3. 도메인 서비스를 컨트롤러에서 분리해 양쪽이 같은 비즈니스 결과를 만들도록 한다.
4. 외부 계약 테스트(Pact/OpenAPI 스냅샷)로 회귀를 잡는다.
5. 점진 라우팅을 깔고, 한 화면씩 잘라내면서 메트릭을 모니터링한다.
6. 마지막으로 잘라낸 레거시 경로를 410으로 정리한다.

**레거시 변경 리스크를 줄이는 법**

핵심 단어는 **건드리지 않을 자유**다. 레거시는 가능하면 변경 없이 두고, 새 흐름을 옆에 붙인다. 부득이하게 손대야 하면 도메인 서비스 단위로만 손대고, 컨트롤러/JSP는 그대로 둔다. 회귀 테스트와 인스턴스 배포 후 검증 라우팅으로 변경 영향 범위를 좁힌다.

**jQuery ajax 코드를 다 걷어내야 하는가**

그럴 필요는 없다. 비즈니스 가치가 있는 곳부터 잘라내고, 자주 안 바뀌고 안정적으로 도는 화면은 굳이 손대지 않는다. 마이그레이션 자체가 목적이 되면 비용만 늘고 사고가 난다. 이 판단을 할 줄 아는 것이 레거시 공존 운영의 차별점이다.

## 체크리스트

- [ ] 레거시 ajax 엔드포인트와 외부 API 엔드포인트가 URL prefix로 분리되어 있다.
- [ ] Spring Security 체인이 두 갈래로 나뉘어 있고, API 체인이 STATELESS다.
- [ ] 화면용 응답 규약과 외부 API 응답 규약이 별도 어드바이스로 관리된다.
- [ ] 비즈니스 로직이 JSP 안에 남아 있지 않거나, 점진 제거 계획이 있다.
- [ ] 도메인 서비스는 한 곳에 있고, 두 컨트롤러가 같은 서비스를 호출한다.
- [ ] 외부 계약(API)에 대해 스키마/계약 테스트가 있다.
- [ ] 점진 라우팅(nginx/Gateway) 설정이 한 줄로 롤백 가능하다.
- [ ] 레거시 경로와 신규 경로의 트래픽/에러율이 별도 대시보드에 분리되어 있다.
- [ ] CSRF·SameSite·CORS·세션 만료 정책이 두 채널 모두에서 검증되어 있다.
- [ ] Strangler Fig 절단 단위가 화면/기능 단위로 작게 정의되어 있다.
- [ ] 새 API에서 사고 발생 시 즉시 레거시 경로로 회귀할 수 있는 절차가 있다.
- [ ] JSP를 깊이 다뤄보지 않았더라도 공존 운영 전략으로 설계를 설명할 수 있다.
