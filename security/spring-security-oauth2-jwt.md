# [초안] Spring Security 6.x OAuth2 + JWT 상용 인증 설계 — Grant 선택, Resource Server, Refresh Rotation, 로그아웃

> 본 문서는 OAuth2 + JWT 기반 **인증 시스템 설계**에 초점을 둔 deep-dive다.
> 보안 일반(OWASP, XSS, SQL Injection, 암호화, Rate limiting, 비밀 관리)은 [security-auth.md](./security-auth.md) hub 문서를 참고한다.
> Spring Boot 3.x + Spring Security 6.x 기준이며, 모바일 앱·백오피스·외부 API 연동이 공존하는 커머스 환경을 가정한다.

## 왜 이것이 면접에서 중요한가

"인증 시스템 설계하라"는 시니어 백엔드 면접에서 가장 답이 갈리는 질문이다. 주니어는 "JWT 발급해서 헤더에 넣고 서버에서 검증한다"에서 끝나지만, 시니어는 **"누가 발급하고, 누가 검증하고, 어떤 grant로 받고, 만료/회전/탈취 시 어떻게 무효화하는가"**를 클라이언트 유형별로 분리해 설명한다.

특히 커머스/디지털 채널 환경은 한 백엔드가 (A) 모바일 앱, (B) 사내 백오피스 SPA, (C) 외부 파트너 API 연동을 **동시에** 책임진다. 세 클라이언트는 신뢰 수준·세션 모델·토큰 저장 가능성·로그아웃 즉시성 요구가 전부 다르다. "전부 JWT 던지면 된다"는 답은 시니어 면접에서 즉시 탈락 신호다.

이 문서는 그 세 클라이언트를 각각 어떤 grant·어떤 토큰 저장·어떤 검증 경로로 설계해야 하는지, 그리고 Spring Security 6.x DSL로 어떻게 구현하는지를 다룬다.

---

## 1. OAuth2 핵심 용어 다시 정리

OAuth2는 **인가 위임 프로토콜**이다. "사용자가 비밀번호를 클라이언트에게 넘기지 않고도 클라이언트가 사용자 자원에 접근하게 한다"가 본질이다.

| 역할 | 의미 | 예시 |
| --- | --- | --- |
| Resource Owner | 자원 소유자 | 실 사용자 |
| Client | 자원에 접근하려는 애플리케이션 | 모바일 앱, SPA, 백오피스, 파트너 시스템 |
| Authorization Server | 토큰 발급 서버 | Keycloak, Auth0, 사내 OAuth2 서버 |
| Resource Server | 토큰을 검증하고 API를 제공하는 서버 | 우리 백엔드 |

OIDC(OpenID Connect)는 OAuth2 위에 **인증** 레이어를 얹은 표준이다. `id_token`(JWT)을 추가로 발급해 "사용자가 누구인지"를 표준 클레임(`sub`, `email`, `name`)으로 전달한다. **SSO를 직접 구현하려면 OAuth2가 아니라 OIDC가 정답이다.**

---

## 2. Grant Type — 클라이언트 유형별 선택 기준

Spring Security 6.x가 지원하는 OAuth2 grant 중 실무에서 쓰이는 것은 4가지다.

### 2.1 Authorization Code + PKCE — 사용자가 직접 로그인하는 모든 경우

```text
모바일 앱 / SPA / 백오피스 / 일반 웹앱  →  Authorization Code + PKCE
```

흐름:

```text
[User] → [Client]: 로그인 버튼 클릭
[Client]: code_verifier 랜덤 생성, SHA256(code_verifier) = code_challenge
[Client] → [AuthServer]: /authorize?response_type=code&client_id=...&code_challenge=...&redirect_uri=...
[User] ↔ [AuthServer]: 로그인 + 동의 화면
[AuthServer] → [Client]: redirect_uri?code=abc
[Client] → [AuthServer]: /token (code + code_verifier)
[AuthServer] → [Client]: access_token + refresh_token (+ id_token if OIDC)
```

PKCE는 원래 `client_secret` 을 숨길 수 없는 퍼블릭 클라이언트(SPA/모바일)를 위해 추가됐지만, **RFC 9700(2024)부터는 모든 클라이언트에 권장**된다. 컨피덴셜 클라이언트(서버사이드 백오피스)도 PKCE를 함께 쓰면 code injection 공격 방어선이 한 겹 늘어난다.

### 2.2 Client Credentials — 서버 to 서버, 사용자 없음

```text
파트너 시스템 → 우리 백엔드 (배송 상태 조회, 정산 API 등)  →  Client Credentials
```

흐름:

```text
[PartnerSystem] → [AuthServer]: /token (grant_type=client_credentials, client_id, client_secret, scope)
[AuthServer] → [PartnerSystem]: access_token (refresh_token 없음)
[PartnerSystem] → [OurAPI]: Authorization: Bearer <token>
```

**핵심**: `refresh_token`이 없다. Client Credentials는 클라이언트 자체가 자격증명이라 만료되면 다시 `client_secret`으로 발급받으면 된다. 토큰 수명은 짧게(15분\~1시간), `scope`로 권한을 엄격히 제한한다(`scope=order:read` 만 허용 등).

흔한 실수: **사용자 토큰을 백엔드끼리 그대로 토스해서 쓰는 것**. 사용자 컨텍스트가 필요 없는 시스템 간 호출이면 Client Credentials로 분리해야 한다. 그래야 사용자가 로그아웃해도 시스템 간 배치는 계속 돌고, 권한 범위도 좁힐 수 있다.

### 2.3 Refresh Token Grant — 무한 로그인 유지

Access Token이 짧게(10\~15분) 만료되는 게 보안 기본이라, 자주 만료된다. 사용자가 매번 로그인하지 않게 하려면 Refresh Token으로 새 Access Token을 받는다.

```text
[Client] → [AuthServer]: /token (grant_type=refresh_token, refresh_token=...)
[AuthServer]: 유효성 검증 + 기존 refresh_token 무효화 + 새 access_token + 새 refresh_token 발급(rotation)
[AuthServer] → [Client]: 새 토큰 쌍
```

회전(rotation)은 4번 섹션에서 자세히 다룬다.

### 2.4 Resource Owner Password Credentials (ROPC) — 쓰지 마라

`grant_type=password` 로 사용자 ID/PW를 직접 넘기는 grant. **RFC 9700(2024)에서 공식적으로 deprecated**. 사용자 비밀번호를 클라이언트가 보게 되는 OAuth2 본래 의도 위반. 신규 시스템에서는 채택 금지.

### 2.5 결정 표 — 멀티 클라이언트 환경

| 클라이언트 | Grant | 토큰 저장 | 비고 |
| --- | --- | --- | --- |
| 모바일 앱 (iOS/Android) | Authorization Code + PKCE | Access: 메모리, Refresh: OS Secure Storage (Keychain/Keystore) | PKCE 필수, custom URL scheme + Universal/App Links |
| 사내 백오피스 SPA | Authorization Code + PKCE + BFF | Access: 메모리, Refresh: BFF가 보유, 브라우저는 HttpOnly 세션 쿠키 | XSS 노출면 차단을 위해 BFF 패턴 권장 |
| 외부 파트너 시스템 | Client Credentials | 파트너 시스템 내부 비밀 저장소 | `scope`로 권한 좁히기, IP allowlist 추가 |
| 일반 웹앱 (서버 렌더) | Authorization Code (+ PKCE) | 세션 쿠키(HttpOnly) | Spring `oauth2-client` |
| 내부 마이크로서비스 간 | Client Credentials 또는 mTLS + Service Token | 서비스 내 메모리 캐시 | 토큰 캐싱으로 인가 서버 부하 회피 |

---

## 3. Spring Security 6.x — Resource Server 설정

우리 백엔드는 대부분 **Resource Server**다. 토큰을 발급하지 않고 검증만 한다. Spring Security 5.x에서 6.x로 넘어오며 DSL이 람다 중심으로 바뀌었다.

### 3.1 의존성

```text
implementation 'org.springframework.boot:spring-boot-starter-security'
implementation 'org.springframework.boot:spring-boot-starter-oauth2-resource-server'
```

### 3.2 가장 단순한 JWT 검증 (OIDC 발급자)

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://auth.example.com/realms/commerce
```

이 한 줄이면 Spring이 `issuer-uri` 의 `/.well-known/openid-configuration` 에서 JWKS URL을 자동으로 찾아 공개키를 로드하고, RS256 서명 검증·`iss` 검증·`exp` 검증을 켠다.

### 3.3 SecurityFilterChain — 6.x DSL

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class ApiSecurityConfig {

    @Bean
    SecurityFilterChain api(HttpSecurity http,
                            JwtAuthenticationConverter converter) throws Exception {
        return http
            .securityMatcher("/api/**")
            .csrf(csrf -> csrf.disable())
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/orders/**").hasAuthority("SCOPE_order:read")
                .requestMatchers(HttpMethod.POST, "/api/orders/**").hasAuthority("SCOPE_order:write")
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(converter)))
            .exceptionHandling(eh -> eh
                .authenticationEntryPoint((req, res, ex) -> {
                    res.setStatus(HttpStatus.UNAUTHORIZED.value());
                    res.setContentType("application/json");
                    res.getWriter().write("{\"error\":\"unauthorized\"}");
                }))
            .build();
    }
}
```

핵심 변경점:
- `antMatchers` → `requestMatchers` (5.8부터 deprecated, 6.x 강제)
- `.and()` 체이닝 → 람다 DSL
- `WebSecurityConfigurerAdapter` 폐기 → `@Bean SecurityFilterChain` 등록
- `@PreAuthorize` 활성화는 `@EnableMethodSecurity` (구 `@EnableGlobalMethodSecurity` 폐기)

### 3.4 JwtAuthenticationConverter — 클레임을 권한으로

JWT의 `scope` 클레임은 기본적으로 `SCOPE_` 접두사로, `realm_access.roles` 같은 커스텀 클레임은 직접 매핑해야 한다.

```java
@Bean
JwtAuthenticationConverter jwtAuthenticationConverter() {
    JwtGrantedAuthoritiesConverter scopes = new JwtGrantedAuthoritiesConverter();
    scopes.setAuthoritiesClaimName("scope");
    scopes.setAuthorityPrefix("SCOPE_");

    JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
    converter.setJwtGrantedAuthoritiesConverter(jwt -> {
        Collection<GrantedAuthority> auth = new ArrayList<>(scopes.convert(jwt));
        Map<String, Object> realm = jwt.getClaimAsMap("realm_access");
        if (realm != null && realm.get("roles") instanceof List<?> roles) {
            for (Object r : roles) {
                auth.add(new SimpleGrantedAuthority("ROLE_" + r));
            }
        }
        return auth;
    });
    return converter;
}
```

### 3.5 컨트롤러에서 토큰 정보 꺼내기

```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    @GetMapping("/{id}")
    public OrderDto get(@PathVariable Long id,
                        @AuthenticationPrincipal Jwt jwt) {
        String userId = jwt.getSubject();
        String tenant = jwt.getClaimAsString("tenant_id");
        return orderService.findOwned(id, userId, tenant);
    }

    @PreAuthorize("hasAuthority('SCOPE_order:write') and #req.userId == authentication.name")
    @PostMapping
    public OrderDto create(@RequestBody OrderRequest req) {
        return orderService.create(req);
    }
}
```

`@AuthenticationPrincipal Jwt` 가 가장 깔끔하다. URL 기반 인가는 1차, 메서드 레벨 `@PreAuthorize` 는 도메인 규칙에 맞춘 2차 방어다.

---

## 4. JWT Access + Refresh Token 구조와 회전

### 4.1 Access Token 클레임 설계

```json
{
  "iss": "https://auth.example.com/realms/commerce",
  "aud": "commerce-api",
  "sub": "u-7821",
  "iat": 1735900000,
  "exp": 1735900900,
  "jti": "8e2a-...",
  "scope": "order:read order:write profile",
  "tenant_id": "store-42",
  "ver": 3
}
```

원칙:
- **만료(`exp`) 짧게 — 10\~15분.** 탈취 시 피해 윈도우를 좁힌다.
- `aud` 를 반드시 검증해 다른 서비스용 토큰이 들어오는 것을 거부한다.
- `jti` 로 토큰 단위 추적 가능(블랙리스트, 감사로그).
- `ver`(token version) 같은 즉시 무효화용 클레임을 미리 둔다(섹션 5에서 활용).
- 민감정보(`email`, `phone`, `password_hash`)는 절대 넣지 않는다. JWT는 Base64URL일 뿐 암호화가 아니다.

### 4.2 Refresh Token — 불투명 vs JWT

Refresh Token은 **불투명 난수**가 정답이다. JWT로 만들면 검증은 가벼워도 즉시 폐기·회전 감지가 어렵다.

```java
String refreshRaw = randomBase64Url(32);     // 클라이언트에게 전달
String refreshHash = sha256Hex(refreshRaw);  // 서버 DB에는 해시만
```

DB 유출 시에도 해시만 있으면 재사용 불가. **평문 저장은 데이터 사고 1순위 후회 항목**이다.

### 4.3 Refresh Rotation + 재사용 탐지

```java
@Service
public class TokenService {

    public TokenPair rotate(String refreshRaw) {
        String hash = sha256Hex(refreshRaw);
        RefreshToken stored = refreshRepo.findByHash(hash)
            .orElseThrow(() -> new AuthException("invalid refresh"));

        if (stored.isUsed()) {
            // 이미 한 번 회전된 토큰이 다시 옴 = 도난으로 간주
            refreshRepo.revokeAllByUserId(stored.getUserId());
            auditLog.recordSuspicious(stored.getUserId(), "refresh_reuse_detected");
            kafka.send("auth.session.revoked", stored.getUserId());
            throw new AuthException("token reuse — all sessions revoked");
        }
        if (stored.getExpiresAt().isBefore(Instant.now())) {
            throw new AuthException("refresh expired");
        }
        stored.markUsed();
        refreshRepo.save(stored);
        return issueNewPair(stored.getUserId());
    }
}
```

핵심:
1. **사용한 refresh는 즉시 `used=true` 플래그.** 회전이 끝났다는 의미.
2. **`used=true` 인 토큰이 다시 오면 도난.** 사용자의 모든 refresh를 폐기(`revokeAllByUserId`).
3. 폐기 이벤트는 Kafka로 브로드캐스트해 각 서비스의 토큰 캐시도 무효화.

이 패턴은 RFC 6819(OAuth2 Security BCP)와 RFC 9700(2024)에서 권장된다.

### 4.4 토큰 저장 — XSS/CSRF 노출면

| 저장 위치 | XSS 노출 | CSRF 노출 | 추천 |
| --- | --- | --- | --- |
| `localStorage` | 매우 높음 — JS로 다 읽힘 | 낮음 (자동 전송 안 됨) | **금지** |
| `sessionStorage` | 매우 높음 | 낮음 | **금지** |
| 쿠키 (`HttpOnly`+ `Secure` + `SameSite=Strict`) | 차단 | 토큰 + `SameSite` 필요 | 권장 (BFF 환경) |
| 메모리(JS 변수, 모바일 RAM) | 새 탭에서 사라짐 | 자동 전송 없음 | 권장 (Access Token) |
| OS Secure Storage (Keychain/Keystore) | 앱별 격리 | N/A | 모바일 Refresh 보관 |

**일반 원칙**: Access Token은 메모리, Refresh Token은 HttpOnly 쿠키(웹) 또는 Secure Storage(모바일). BFF 패턴에서는 Refresh Token이 브라우저로 내려가지 않게 BFF가 보관한다.

---

## 5. JWT 환경의 로그아웃 — "무상태 토큰을 어떻게 무효화하는가"

JWT의 가장 큰 약점은 **즉시 무효화가 어렵다**는 것이다. Access Token은 만료 전까지 유효하다. 세 가지 전략을 조합한다.

### 5.1 짧은 수명 + Refresh 폐기 (기본)

- Access Token 수명을 10\~15분으로 짧게 잡고 별도 블랙리스트 없이 자연 만료를 기다린다.
- 로그아웃 시 서버는 Refresh Token만 DB에서 삭제한다. Access는 만료까지 살아있지만, 새 Access를 받을 수 없다.
- 대부분의 도메인에서 이 정도면 충분하다.

```java
@PostMapping("/auth/logout")
public ResponseEntity<Void> logout(@RequestBody LogoutRequest req,
                                   HttpServletResponse res) {
    refreshRepo.revokeByHash(sha256Hex(req.refreshToken()));
    Cookie clear = new Cookie("refresh_token", "");
    clear.setMaxAge(0);
    clear.setHttpOnly(true);
    clear.setSecure(true);
    clear.setPath("/auth");
    res.addCookie(clear);
    return ResponseEntity.noContent().build();
}
```

### 5.2 `token_version` 클레임 — 즉시 무효화 경로

권한 변경·계정 해킹·관리자 강제 로그아웃처럼 **즉시 차단이 필수**인 경우.

```java
// JWT 발급 시
.withClaim("ver", user.getTokenVersion())

// Resource Server 검증 시
@Bean
OAuth2TokenValidator<Jwt> tokenVersionValidator(UserTokenVersionCache cache) {
    return jwt -> {
        String userId = jwt.getSubject();
        Integer claimVer = jwt.getClaim("ver");
        Integer currentVer = cache.get(userId);
        if (claimVer == null || !claimVer.equals(currentVer)) {
            return OAuth2TokenValidatorResult.failure(
                new OAuth2Error("token_revoked"));
        }
        return OAuth2TokenValidatorResult.success();
    };
}
```

`tokenVersion` 을 +1 하면 기존에 발급된 JWT는 전부 무효가 된다. `UserTokenVersionCache` 는 Redis로 캐시해 ms 단위 조회. 적용 비용은 매 요청당 Redis lookup 한 번 — 운영상 충분히 감당 가능.

### 5.3 jti 블랙리스트 — 특정 토큰만 차단

특정 의심 토큰만 차단하고 싶을 때. Redis SET에 `jti` 를 토큰 남은 수명만큼 저장.

```java
public boolean isRevoked(String jti) {
    return Boolean.TRUE.equals(redis.hasKey("revoked:jti:" + jti));
}
```

5.1 \~ 5.3은 함께 쓴다. 90%는 5.1로 처리하고, 5.2를 비상 경로로 두고, 5.3은 특정 토큰만 잡을 때.

---

## 6. 다중 SecurityFilterChain — 외부 API와 사용자 API 분리

같은 백엔드가 사용자 API(JWT 검증)와 파트너 API(Client Credentials 검증)를 모두 제공할 때, `SecurityFilterChain` 을 둘로 나눈다.

```java
@Bean
@Order(1)
SecurityFilterChain partnerApi(HttpSecurity http) throws Exception {
    return http
        .securityMatcher("/partner-api/**")
        .csrf(csrf -> csrf.disable())
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(auth -> auth
            .anyRequest().hasAuthority("SCOPE_partner:integrate"))
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
        .build();
}

@Bean
@Order(2)
SecurityFilterChain userApi(HttpSecurity http,
                            JwtAuthenticationConverter converter) throws Exception {
    return http
        .securityMatcher("/api/**")
        .csrf(csrf -> csrf.disable())
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/public/**").permitAll()
            .anyRequest().authenticated())
        .oauth2ResourceServer(oauth2 -> oauth2
            .jwt(jwt -> jwt.jwtAuthenticationConverter(converter)))
        .build();
}
```

`@Order` 로 매칭 우선순위를 명시한다. 파트너 API는 IP allowlist를 추가로 두는 게 일반적이다(Spring Cloud Gateway 또는 ALB rule).

---

## 7. 흔한 함정과 디버깅 포인트

### 7.1 `Algorithm Confusion` 공격

```java
// 위험: 라이브러리가 알고리즘을 자동 추론
JWT.decode(token);

// 안전: 알고리즘 고정
NimbusJwtDecoder.withPublicKey(publicKey)
    .signatureAlgorithm(SignatureAlgorithm.RS256)
    .build();
```

RS256으로 발급된 토큰의 공개키를 HS256 비밀로 오인해 검증하면 공격자가 공개키만으로 토큰을 위조할 수 있다. **알고리즘은 코드에서 명시적으로 고정**.

### 7.2 `aud` 미검증

발급자(Auth Server)가 한 명이고 Resource Server가 여러 개일 때, A 서비스용 토큰으로 B 서비스를 호출하면 안 된다. `aud` 클레임 검증은 자동이 아니라 명시적으로 켠다.

```java
decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
    JwtValidators.createDefaultWithIssuer("https://auth.example.com/realms/commerce"),
    new JwtClaimValidator<List<String>>("aud",
        aud -> aud != null && aud.contains("commerce-api"))));
```

### 7.3 JWKS 캐시 만료

Authorization Server가 키를 회전(`kid` 교체)했는데 Resource Server가 옛 JWKS를 캐시하고 있으면 모든 검증이 실패한다. Spring Security 기본 캐시는 5분. 회전 빈도가 낮으면 별 문제 없지만, 운영 트래픽이 크면 캐시 무효화 정책을 별도로 둔다.

### 7.4 `SecurityContextHolder` 가 비어있는 비동기 컨텍스트

`@Async` 메서드에서 `SecurityContextHolder.getContext().getAuthentication()` 이 null. 기본 전략이 `ThreadLocal` 이라 새 스레드에는 전파 안 됨.

```java
@Bean
public DelegatingSecurityContextAsyncTaskExecutor asyncExecutor() {
    ThreadPoolTaskExecutor base = new ThreadPoolTaskExecutor();
    base.initialize();
    return new DelegatingSecurityContextAsyncTaskExecutor(base);
}
```

또는 `SecurityContextHolder.setStrategyName(MODE_INHERITABLETHREADLOCAL)` 을 부팅 초기에 한 번. 단 후자는 스레드 풀과 함께 쓰면 컨텍스트 누수 위험이 있어 비추천.

---

## 8. 로컬 실습 환경

```bash
# Keycloak — OAuth2/OIDC Authorization Server
docker run -p 8080:8080 \
  -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:24.0 start-dev

# Redis — refresh token store + token version cache
docker run -p 6379:6379 redis:7

# 우리 백엔드 (Spring Boot 3.x)
./gradlew bootRun --args='--spring.profiles.active=local'
```

Keycloak realm 생성:
1. `commerce` realm 생성
2. Client 등록: `commerce-mobile` (public, Standard Flow + PKCE only)
3. Client 등록: `partner-shipping` (confidential, Service accounts roles)
4. Scope 정의: `order:read`, `order:write`, `partner:integrate`
5. 테스트 사용자 1명 생성

`application.yml`:

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: http://localhost:8080/realms/commerce
          audiences: commerce-api
```

토큰 발급 테스트:

```bash
# Authorization Code (PKCE) — 브라우저로 /authorize
# Client Credentials (파트너)
curl -X POST http://localhost:8080/realms/commerce/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=partner-shipping" \
  -d "client_secret=<secret>" \
  -d "scope=partner:integrate"
```

응답으로 받은 `access_token` 을 우리 API에 `Authorization: Bearer ...` 로 보내본다.

---

## 9. 면접 답변 프레이밍

### Q. "커머스 백엔드 인증을 어떻게 설계하시겠어요?"

**답변 뼈대 (3분 분량):**

"먼저 클라이언트 유형을 분리합니다. 모바일 앱, 사내 백오피스, 외부 파트너 — 셋이 신뢰 모델이 다릅니다.

모바일과 백오피스는 사용자가 직접 로그인하니까 OIDC + Authorization Code + PKCE를 쓰고, Access Token은 10\~15분 짧은 RS256 JWT, Refresh Token은 서버 해시 저장 + 회전 정책을 둡니다. 모바일은 Refresh를 OS Keychain/Keystore에, 백오피스는 BFF 패턴으로 브라우저에 안 내려보냅니다. `localStorage`는 XSS 한 번에 다 털리니까 절대 안 씁니다.

파트너 시스템 연동은 사용자 컨텍스트가 없으니 Client Credentials grant로 분리합니다. `scope=partner:integrate` 같이 권한을 좁히고, IP allowlist를 추가로 둡니다.

검증은 Spring Security 6.x Resource Server로 — `issuer-uri` 하나 잡으면 JWKS 자동 로드해 RS256 검증·`iss`·`exp` 자동입니다. `aud` 검증은 명시적으로 추가합니다. `JwtAuthenticationConverter` 로 `scope` 와 `realm_access.roles` 를 모두 Spring 권한으로 매핑하고, URL 기반 인가 + `@PreAuthorize` 메서드 인가를 2중으로 둡니다.

로그아웃은 Refresh 폐기 + Access 자연 만료가 기본인데, 권한 변경이나 강제 로그아웃이 필요한 경로용으로 `token_version` 클레임 + Redis 캐시를 둬서 즉시 무효화 경로를 확보합니다."

### Q. "왜 Refresh Token을 JWT로 안 하시나요?"

"즉시 폐기와 회전 감지가 어렵기 때문입니다. JWT는 무상태라 만료 전 폐기를 하려면 별도 블랙리스트가 필요한데, Refresh는 그게 일상 동작이라 차라리 처음부터 불투명 난수 + DB 해시 저장이 깔끔합니다. 회전 감지(`used=true` 인 토큰이 다시 오면 도난)도 DB 상태 변경으로 자연스럽게 됩니다."

### Q. "JWT가 탈취되면요?"

"세 단계입니다. 탐지 — Refresh 회전 재사용 감지, 이상 지역/디바이스 로그인. 즉시 차단 — 해당 사용자의 `token_version` +1 해서 기존 JWT 전부 무효, Refresh 테이블에서 `revokeAll(user_id)`, Kafka로 `auth.session.revoked` 브로드캐스트해 각 서비스 캐시 무효화. 복구 — 강제 재로그인 + MFA, 키 노출 가능성 있으면 서명키 `kid` 회전, XSS·로그 누출·클라이언트 저장소 어디서 샜는지 근본 원인 분석."

### Q. "왜 OAuth2가 아니고 OIDC인가요?"

"OAuth2는 인가 위임 프로토콜이지 사용자 신원을 표준화하지 않습니다. 그래서 OAuth2만으로 SSO를 하면 `userinfo` 엔드포인트 형식·`sub` 의미·`email` claim 위치가 공급자마다 달라집니다. OIDC가 `id_token`(JWT)과 표준 클레임을 정의해서 이걸 해결합니다. 사용자 로그인을 다룬다면 처음부터 OIDC가 정답입니다."

---

## 10. 체크리스트

- [ ] 클라이언트 유형별로 grant가 분리되어 있는가 (사용자 → Code+PKCE, 시스템 → Client Credentials)
- [ ] ROPC(`grant_type=password`) 를 신규 시스템에서 채택하지 않았는가
- [ ] Access Token 수명 ≤ 15분
- [ ] Refresh Token이 평문이 아니라 SHA-256 해시로 DB에 저장되는가
- [ ] Refresh Token Rotation + 재사용 탐지가 구현되어 있는가
- [ ] JWT 알고리즘이 코드에서 고정되어 있는가 (`alg: none` 거부)
- [ ] `iss`, `aud`, `exp` 검증이 모두 켜져 있는가
- [ ] JWT 페이로드에 비밀번호/PII가 들어가지 않는가
- [ ] `token_version` 또는 `jti` 블랙리스트 같은 즉시 무효화 경로가 있는가
- [ ] `localStorage`/`sessionStorage`에 토큰을 저장하지 않는가
- [ ] 모바일 Refresh가 Keychain/Keystore에 저장되는가
- [ ] BFF 패턴 또는 HttpOnly+Secure+SameSite 쿠키로 브라우저 토큰을 보호하는가
- [ ] 파트너 API에 `scope` 제한 + IP allowlist가 적용되어 있는가
- [ ] 사용자 API와 파트너 API의 `SecurityFilterChain` 이 분리되어 있는가
- [ ] `JwtAuthenticationConverter` 로 커스텀 클레임이 Spring 권한으로 매핑되는가
- [ ] `@PreAuthorize` 메서드 인가가 URL 인가의 2차 방어로 사용되는가
- [ ] JWKS 키 회전 시 캐시 무효화 정책이 있는가
- [ ] 비동기/스레드풀 컨텍스트에서 `SecurityContextHolder` 전파가 보장되는가
- [ ] 인증 실패·refresh 재사용 탐지가 감사 로그와 알림으로 연결되어 있는가
- [ ] 보안 일반 항목(OWASP, 암호화, Rate limiting)은 [security-auth.md](./security-auth.md) 체크리스트로 보강했는가
