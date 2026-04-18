# [초안] 시니어 백엔드를 위한 보안 / 인증 스터디 팩 — Spring Security, JWT, OAuth2, OWASP Top 10

## 왜 이것이 면접에서 중요한가

"인증을 어떻게 설계하시나요?"는 시니어 백엔드 면접에서 거의 예외 없이 등장하는 질문이다. 이 질문이 겨냥하는 것은 `Spring Security`의 설정 문법이 아니라, 자격증명이 어느 경계에서 검증되고 어떤 저장소에 머물며 탈취되었을 때 어떤 경로로 차단되는지를 설명할 수 있느냐이다. 주니어는 "JWT를 쓴다"에서 멈추지만, 시니어는 "왜 JWT인지, RS256과 HS256 중 무엇을 선택했는지, Refresh Token을 어디에 저장하는지, API Gateway에서 인증을 끝낼지 서비스 내부에서 재검증할지"를 근거 있게 말한다.

보안은 한 번의 실수가 전체 시스템을 무너뜨리는 드문 도메인이다. `SQL Injection` 하나로 전 고객 데이터가 유출되고, `IDOR` 하나로 타인의 주문이 노출된다. 그래서 면접관은 "이론을 아느냐"가 아니라 "실제 장애 시나리오에서 어떻게 탐지하고 차단할 것인가"를 본다. 이 문서는 그 수준을 목표로 한다.

---

## 1. OWASP Top 10 요점과 Java/Spring 방어

### 1.1 SQL Injection (A03: Injection)

공격자가 입력값에 SQL 조각을 섞어 쿼리 의미를 바꾸는 공격이다. 여전히 실전에서 가장 흔한 침해 원인이다.

**나쁜 예:**

```java
@GetMapping("/users")
public User find(@RequestParam String email) {
    String sql = "SELECT * FROM users WHERE email = '" + email + "'";
    return jdbcTemplate.queryForObject(sql, userMapper);
}
```

`email=' OR '1'='1` 을 넣으면 전체 행이 반환된다.

**개선:**

```java
@GetMapping("/users")
public User find(@RequestParam String email) {
    return jdbcTemplate.queryForObject(
        "SELECT * FROM users WHERE email = ?",
        userMapper, email);
}
```

`PreparedStatement` 는 쿼리 구조와 파라미터를 분리하므로 입력값이 SQL 토큰으로 재해석되지 않는다. `JPA`, `MyBatis #{}` 도 같은 원리다. `${}`는 문자열 치환이라 위험하다.

방어 체크리스트: 파라미터 바인딩, ORM 활용, DB 계정 최소 권한(`SELECT`만 필요한 서비스에 `DROP` 권한을 주지 않는다), 에러 메시지에서 SQL 구조 노출 금지.

### 1.2 XSS (A03: Injection — Cross-Site Scripting)

공격자가 스크립트를 페이지에 심어 피해자의 브라우저에서 실행되게 한다. 백엔드 관점에서는 "응답에 들어가는 모든 사용자 입력은 HTML 컨텍스트에서 이스케이프 되어야 한다"가 핵심이다.

`Thymeleaf`는 기본이 이스케이프다. 위험한 것은 `th:utext`, `@ResponseBody` 로 HTML 문자열을 직접 반환하는 경우, 프런트에 넘어가는 JSON 안의 원문 텍스트가 `innerHTML`로 렌더링되는 경우다.

백엔드 방어:
- 응답 헤더 `Content-Security-Policy: default-src 'self'` 로 외부 스크립트 차단
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- HTML을 저장해야 하면 `OWASP Java HTML Sanitizer` 로 화이트리스트 기반 정화

### 1.3 CSRF

로그인된 피해자의 브라우저로 공격자가 원치 않는 요청을 보내게 하는 공격. 인증이 쿠키 기반(자동 전송)일 때만 의미가 있다. 완전한 Bearer 토큰 기반 REST API는 CSRF 리스크가 원천적으로 적다.

Spring Security 기본:

```java
@Bean
public SecurityFilterChain filter(HttpSecurity http) throws Exception {
    return http
        .csrf(csrf -> csrf
            .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()))
        .build();
}
```

세션 쿠키 기반 BFF(Backend For Frontend) 구조에서는 반드시 `SameSite=Lax` 또는 `Strict`, 그리고 CSRF 토큰을 함께 쓴다.

### 1.4 SSRF

서버가 신뢰하는 네트워크 위치에서 외부/내부 URL로 요청을 보내게 만드는 공격. AWS EC2 메타데이터(`169.254.169.254`) 탈취 사례가 대표적이다.

방어: 외부 URL을 받는 엔드포인트가 있다면 `URL` 을 파싱해 호스트를 화이트리스트와 대조, 사설망 대역(`10/8`, `172.16/12`, `192.168/16`, `169.254/16`) 차단, `RestTemplate`/`WebClient` 에 리디렉션 제한과 타임아웃 설정.

### 1.5 IDOR (Broken Access Control)

`GET /orders/123` 을 A 사용자가 호출했는데 실제로 123번 주문이 B 소유인 경우. 인증은 통과했지만 **인가**가 깨진 것이다. OWASP Top 10에서 항상 1, 2위권이다.

```java
@GetMapping("/orders/{id}")
public OrderDto get(@PathVariable Long id, @AuthenticationPrincipal UserPrincipal user) {
    Order order = orderRepo.findById(id).orElseThrow();
    if (!order.getOwnerId().equals(user.getId())) {
        throw new AccessDeniedException("not your order");
    }
    return OrderDto.from(order);
}
```

또는 레포지토리 단계에서 `findByIdAndOwnerId(id, ownerId)` 로 강제한다. 리소스 소유권은 **항상 서버에서** 확인한다. 프론트 숨김은 방어가 아니다.

---

## 2. Session vs Token — Stateful vs Stateless

| 구분 | Session (Stateful) | Token (Stateless, JWT) |
| --- | --- | --- |
| 자격 저장 위치 | 서버(메모리/Redis) | 클라이언트 |
| 확장성 | 공유 저장소 필요 | 수평 확장 쉬움 |
| 즉시 로그아웃 | 서버에서 세션 삭제 → 즉시 | 만료까지 유효 (또는 블랙리스트) |
| 크기 | 쿠키엔 세션 ID만 | 매 요청마다 수백 bytes ~ 수 KB |
| 탈취 탐지 | 서버측 로그 | 어려움, 추가 장치 필요 |

**선택 기준:**
- 동일 도메인 웹앱, 사용자 수 중간, 로그아웃 즉시성 중요 → 세션 (Spring Session + Redis)
- 모바일 앱, SPA + 여러 마이크로서비스, 여러 도메인, 서버 무상태 요구 → 토큰(JWT)
- 현실적 조합 → BFF 패턴: 브라우저 ↔ BFF 는 세션 쿠키, BFF ↔ 내부 서비스는 JWT

"무조건 JWT"는 시니어 답변이 아니다. "JWT는 즉시 만료가 어렵기 때문에, 로그아웃/권한변경 즉시 반영이 중요한 도메인에는 세션을 선택한다"가 올바른 시니어 언어다.

---

## 3. JWT 구조와 서명 알고리즘

JWT는 `header.payload.signature` 3개 블록을 Base64URL로 이은 문자열이다.

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1LTEyMyIsImV4cCI6MTcxMzAwMDAwMH0.signature
```

- **Header**: `{"alg":"HS256","typ":"JWT"}`
- **Payload (Claims)**: `sub`(주체), `iss`(발급자), `aud`(대상), `exp`(만료), `iat`(발급시각), `jti`(고유 ID) + 커스텀 클레임
- **Signature**: `HMACSHA256(base64url(header) + "." + base64url(payload), secret)`

### HS256 vs RS256 실무 선택

- **HS256 (HMAC + 공유 비밀)**: 발급자와 검증자가 같은 조직·같은 비밀키를 공유할 때. 모놀리식 또는 같은 팀의 마이크로서비스.
- **RS256 (RSA 비대칭)**: 발급자는 **개인키로 서명**, 검증자는 **공개키로 검증**. 여러 조직/여러 서비스가 검증해야 하면 RS256. 공개키가 유출되어도 위조 불가.

외부에 열린 OAuth2/OIDC 공급자(Google, Auth0, Keycloak)는 거의 RS256이다. 공개키는 JWKS 엔드포인트(`/.well-known/jwks.json`)로 공개되며, 검증자는 `kid`(key id)로 키를 선택한다.

### 흔한 JWT 취약점

1. **`alg: none` 공격**: 옛 라이브러리가 `alg=none` 을 그대로 수용. 반드시 허용 알고리즘을 명시.
2. **Algorithm Confusion**: RS256 공개키를 HS256 비밀로 오인해 검증. 라이브러리에서 알고리즘 고정 필요.
3. **Payload 암호화 착각**: JWT는 서명이지 암호화가 아니다. `password` 같은 민감정보를 넣으면 그대로 노출.

Spring Boot 예:

```java
@Bean
public JwtDecoder jwtDecoder() {
    return NimbusJwtDecoder.withPublicKey(rsaPublicKey)
        .signatureAlgorithm(SignatureAlgorithm.RS256)
        .build();
}
```

---

## 4. Access Token vs Refresh Token, 회전, 탈취 대응

- **Access Token**: 수명 짧음(5~15분). API 호출마다 전송. 탈취돼도 피해 시간이 제한됨.
- **Refresh Token**: 수명 김(수일~수개월). Access Token을 재발급받는 용도. 서버 저장 필수.

**Refresh Token Rotation (회전):**

```
1. 클라이언트: refresh_token_v1 → 서버
2. 서버: 유효성 검증 + DB에서 v1 무효화 + access_token_new + refresh_token_v2 발급
3. 클라이언트: v2 저장
```

핵심은 "사용된 refresh token은 즉시 폐기"다. 이후 v1이 다시 오면 **도난으로 간주**하고 해당 사용자의 모든 refresh token을 폐기해 강제 재로그인시킨다(RFC 6819, OAuth2 Security BCP).

**저장 위치:**
- Access Token → 메모리 또는 `HttpOnly` 쿠키
- Refresh Token → `HttpOnly; Secure; SameSite=Strict` 쿠키 또는 모바일 Secure Storage
- `localStorage`는 XSS 한 번으로 전부 털린다. 피한다.

**탈취 시 대응 플로:**
1. Refresh Token 회전 이상 감지 → 해당 사용자 모든 세션 폐기
2. 관리 콘솔에서 특정 `user_id`의 `token_version` 을 +1 → 기존 JWT의 `ver` 클레임과 불일치로 전부 무효화
3. Kafka로 `auth.session.revoked` 이벤트 발행 → 각 서비스 캐시 갱신
4. 감사 로그 + 이상 IP/디바이스 기반 강제 MFA

---

## 5. OAuth2 Authorization Code + PKCE, OIDC 차이

**Authorization Code Flow (웹앱):**

```
User → Client: 로그인 클릭
Client → Auth Server: /authorize?response_type=code&client_id=...&redirect_uri=...
User ↔ Auth Server: 로그인 + 동의
Auth Server → Client: redirect_uri?code=abc
Client → Auth Server: /token (code + client_secret)
Auth Server → Client: access_token + refresh_token
```

**PKCE (Proof Key for Code Exchange)**는 SPA/모바일처럼 `client_secret` 을 숨길 수 없는 퍼블릭 클라이언트를 위해 추가됐다.

```
1. Client가 code_verifier 랜덤 생성 → SHA256(code_verifier) = code_challenge
2. /authorize 요청 시 code_challenge 전송
3. 토큰 교환 시 code_verifier 원문 전송 → 서버가 해시 비교
```

중간에 `code`가 탈취되어도 `code_verifier` 없이는 토큰 교환이 불가. **이제 PKCE는 모든 클라이언트에 권장**(RFC 9700, 2024).

**OAuth2 vs OIDC:**
- OAuth2: **인가(Authorization)** — "이 사용자가 이 API를 호출할 권한이 있나?"
- OIDC(OpenID Connect): OAuth2 위에 **인증(Authentication)** 추가 — `id_token`(JWT)을 주어 "사용자가 누구인지" 표준 방식으로 전달

SSO를 직접 구현한다면 OIDC가 정답이다. OAuth2만으로 사용자 신원을 표현하려는 건 흔한 설계 실수다.

---

## 6. Spring Security 필터 체인과 인증/인가 분리

Spring Security는 `DelegatingFilterProxy` → `FilterChainProxy` → 여러 `SecurityFilterChain`으로 구성된다. 주요 필터 순서:

```
SecurityContextPersistenceFilter
→ LogoutFilter
→ UsernamePasswordAuthenticationFilter (또는 BearerTokenAuthenticationFilter)
→ RequestCacheAwareFilter
→ SecurityContextHolderAwareRequestFilter
→ AnonymousAuthenticationFilter
→ SessionManagementFilter
→ ExceptionTranslationFilter
→ FilterSecurityInterceptor / AuthorizationFilter
```

**인증(Authentication)** — "이 사람이 누구인가"는 `AuthenticationFilter` 에서 끝난다. 성공하면 `Authentication` 객체가 `SecurityContext` 에 저장된다.

**인가(Authorization)** — "이 자원에 접근할 수 있는가"는 `AuthorizationFilter` / 메서드 시큐리티 (`@PreAuthorize`)에서 본다.

```java
@Bean
public SecurityFilterChain api(HttpSecurity http) throws Exception {
    return http
        .csrf(csrf -> csrf.disable())
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/public/**").permitAll()
            .requestMatchers("/api/admin/**").hasRole("ADMIN")
            .anyRequest().authenticated())
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
        .build();
}

@Service
public class OrderService {
    @PreAuthorize("hasRole('USER') and #userId == authentication.principal.id")
    public Order find(Long userId, Long orderId) { ... }
}
```

URL 기반은 1차, 메서드 레벨 `@PreAuthorize` 는 도메인 규칙에 맞춘 2차 방어다.

---

## 7. API Gateway 인증 종료 vs 서비스 내부 재검증

두 가지 전략 모두 현장에 존재한다.

**(A) Gateway에서 인증 종료:**
- Gateway가 JWT 서명 검증 → 유효하면 내부에 `X-User-Id` 헤더를 붙여 전달
- 내부 서비스는 네트워크를 신뢰 영역으로 간주하고 헤더만 신뢰
- 장점: 중복 검증 없음, 빠름
- 약점: 내부망 침투 시 `X-User-Id` 위조 가능. **제로트러스트에 부적합**

**(B) 서비스 내부 재검증:**
- 내부 서비스도 JWT 원본을 받아 공개키로 재검증
- 비용이 더 크지만, 라이브러리로 캐시하면 ms 단위
- 장점: 각 서비스가 독립적 보안 경계
- 권장: **공개 API는 Gateway 종료, 내부 마이크로서비스 간에는 서비스 메시(mTLS) + JWT 재검증**

시니어 답변 패턴: "외부에서는 Gateway에서 1차 검증 + Rate limiting, 내부 서비스는 공개키 캐싱으로 JWT 재검증 — `X-User-Id` 같은 위조 가능한 헤더를 단독 신뢰하지 않는다."

---

## 8. CORS / CSRF 토큰 / SameSite — 혼동 정리

| 메커니즘 | 방어 대상 | 작동 위치 |
| --- | --- | --- |
| CORS | 브라우저가 다른 origin으로 요청 보내는 것을 스크립트 레벨에서 허용/차단 | 브라우저 + 서버 응답 헤더 |
| CSRF 토큰 | 로그인된 사용자 브라우저를 통한 위조 요청 | 서버 (토큰 생성/검증) |
| SameSite 쿠키 | 쿠키가 크로스사이트 요청에 자동 첨부되는 것 | 브라우저 (쿠키 속성) |

흔한 오해: "CORS를 잘 설정하면 CSRF가 막힌다" — **틀렸다**. `<form>` POST는 CORS 영향을 받지 않고 그대로 나간다. CSRF는 토큰 또는 `SameSite=Lax`/`Strict`로 막는다.

`Access-Control-Allow-Origin: *` + `credentials: true` 조합은 규격상 금지되며 브라우저가 거부한다. Wildcard를 써야 하면 credentials를 포기해야 한다.

---

## 9. Secret Management

```java
// 안티패턴
@Value("${db.password}")
String password; // application.yml에 하드코딩
```

```yaml
# application.yml (잘못)
db:
  password: "mysecret123"
```

**문제:** Git 히스토리에 영구 노출, 롤링 불가, 전 팀원이 프로덕션 비밀 접근.

**계층별 대안:**

1. 환경변수 — 개발/로컬 한정. 프로세스 목록(`ps eww`)에서 보일 수 있고, 재시작 없이는 회전 불가.
2. AWS Parameter Store / Secrets Manager — IAM 기반 접근 제어, 자동 회전 가능.
3. HashiCorp Vault — 동적 자격증명(요청 시 단명 DB 계정 발급), 감사 로그, KV 시크릿.
4. KMS — 암호화 키 자체의 관리. 애플리케이션이 데이터만 KMS로 감싸 저장. 평문 키는 메모리에만 존재.

Spring Boot + AWS:

```java
@Bean
public DataSource dataSource(SecretsManagerClient sm) {
    GetSecretValueResponse r = sm.getSecretValue(b -> b.secretId("prod/db"));
    DbSecret s = objectMapper.readValue(r.secretString(), DbSecret.class);
    return DataSourceBuilder.create()
        .url(s.url()).username(s.user()).password(s.password()).build();
}
```

기본 원칙: **비밀은 절대 코드 저장소에 들어가지 않는다. 실행 시점에 인출하고, 회전 가능하고, 접근 로그가 남는다.**

---

## 10. Rate Limiting — 계층별 설계

- **Gateway 레벨**: IP 기반, 전체 처리량 보호. Envoy, Nginx, AWS API Gateway, Spring Cloud Gateway RateLimiter.
- **앱 레벨**: `user_id` 기반, 비즈니스 의미 있는 제한(한 사용자가 분당 주문 100건 같은).
- **DB/외부 API 보호**: 커넥션 풀 + 서킷브레이커(Resilience4j).

**Redis 기반 Token Bucket (Spring + Lettuce):**

```java
public class RedisRateLimiter {
    private static final String LUA = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])
        local tokens = tonumber(redis.call('HGET', key, 'tokens') or capacity)
        local ts = tonumber(redis.call('HGET', key, 'ts') or now)
        local delta = math.max(0, now - ts)
        tokens = math.min(capacity, tokens + delta * rate)
        local allowed = 0
        if tokens >= requested then
            tokens = tokens - requested
            allowed = 1
        end
        redis.call('HSET', key, 'tokens', tokens, 'ts', now)
        redis.call('EXPIRE', key, 3600)
        return allowed
        """;

    public boolean allow(String userId, int rate, int capacity) {
        Long ok = redis.execute(
            RedisScript.of(LUA, Long.class),
            List.of("rl:" + userId),
            String.valueOf(rate),
            String.valueOf(capacity),
            String.valueOf(Instant.now().getEpochSecond()),
            "1");
        return ok == 1L;
    }
}
```

Lua 스크립트로 원자성 보장(읽기 → 계산 → 쓰기가 단일 연산). 단일 Redis는 SPOF라 프로덕션에서는 Redis Cluster + fallback policy(장애 시 허용할지 거부할지) 결정이 필요하다.

---

## 11. 암호화 기초

### 대칭 vs 비대칭

- **대칭(AES-256-GCM)**: 같은 키로 암/복호화. 빠르다. DB 필드 암호화, 파일 암호화에 사용. GCM은 AEAD라 무결성까지 보장.
- **비대칭(RSA, ECDSA)**: 공개키로 암호화/검증, 개인키로 복호화/서명. 느리다. TLS 핸드셰이크, JWT 서명, 대칭키 교환에 사용.

**실무 패턴:** 대칭키로 데이터 암호화 → 대칭키 자체는 비대칭키(또는 KMS)로 보호. 이것이 "envelope encryption"이다.

### 비밀번호 해싱 — BCrypt, Argon2

비밀번호는 **해싱**이지 암호화가 아니다. 일방향.

```java
// 잘못
String hash = MessageDigest.getInstance("SHA-256").digest(password.getBytes());
// MD5/SHA-256는 GPU로 초당 수십억 번 시도 가능. 부적합.

// 올바름 (BCrypt)
PasswordEncoder encoder = new BCryptPasswordEncoder(12); // work factor 12
String hash = encoder.encode(rawPassword);
boolean ok = encoder.matches(rawPassword, hash);
```

- **BCrypt**: 2023년 현재 work factor 12 이상 권장. 내장 salt.
- **Argon2id**: OWASP 2024 1순위 권장. 메모리-하드. Spring Security 5.8+에 `Argon2PasswordEncoder` 내장.
- **PBKDF2**: FIPS 인증 필요 환경에서.

### SecureRandom

```java
// 잘못: Math.random(), new Random() — 예측 가능
String token = String.valueOf(new Random().nextLong());

// 올바름
byte[] bytes = new byte[32];
SecureRandom.getInstanceStrong().nextBytes(bytes);
String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
```

토큰, 세션 ID, CSRF 토큰, Refresh Token은 반드시 `SecureRandom`.

### TLS 기본

- TLS 1.2 이상, 1.3 권장. 1.0/1.1은 폐기.
- HSTS 헤더: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- 내부 마이크로서비스 간에도 mTLS — "내부망은 안전하다"는 가정은 **제로트러스트 원칙 위반**.

---

## 12. 로컬 실습 환경

```bash
mkdir security-lab && cd security-lab
# Spring Boot 3.x + Spring Security + JWT 샘플
curl https://start.spring.io/starter.zip \
  -d dependencies=web,security,oauth2-resource-server,data-redis \
  -d javaVersion=21 \
  -d type=gradle-project \
  -o lab.zip
unzip lab.zip

# Keycloak (OIDC 테스트용)
docker run -p 8080:8080 \
  -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:24.0 start-dev

# Redis (Rate limiter / refresh token blacklist)
docker run -p 6379:6379 redis:7

# MySQL 8 (사용자/세션 테이블 실습)
docker run -p 3306:3306 -e MYSQL_ROOT_PASSWORD=root mysql:8.0
```

Keycloak에 realm 생성 후 client를 만들고, Spring Boot의 `application.yml`에:

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: http://localhost:8080/realms/lab
```

이것만으로 JWKS 자동 로드, RS256 검증, 서명 불일치 거부가 된다.

---

## 13. 실행 가능한 예제 — JWT 발급/검증 + Refresh Rotation

### RSA 키 생성

```bash
openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in private.pem -out public.pem
```

### 발급 서비스

```java
@Service
public class TokenService {
    private final RSAPrivateKey priv;
    private final RSAPublicKey pub;
    private final RefreshTokenRepository refreshRepo;

    public TokenPair issue(Long userId) {
        Instant now = Instant.now();
        String access = JWT.create()
            .withSubject(String.valueOf(userId))
            .withIssuer("lab")
            .withAudience("lab-api")
            .withIssuedAt(now)
            .withExpiresAt(now.plusSeconds(600))
            .withJWTId(UUID.randomUUID().toString())
            .sign(Algorithm.RSA256(pub, priv));

        String refreshRaw = randomBase64Url(32);
        String refreshHash = sha256Hex(refreshRaw);
        refreshRepo.save(new RefreshToken(userId, refreshHash,
            now.plus(Duration.ofDays(14)), false));
        return new TokenPair(access, refreshRaw);
    }

    public TokenPair rotate(String refreshRaw) {
        String hash = sha256Hex(refreshRaw);
        RefreshToken stored = refreshRepo.findByHash(hash)
            .orElseThrow(() -> new AuthException("invalid"));
        if (stored.isUsed()) {
            // 재사용 탐지 — 전부 폐기
            refreshRepo.revokeAllByUserId(stored.getUserId());
            throw new AuthException("token reuse detected");
        }
        if (stored.getExpiresAt().isBefore(Instant.now())) {
            throw new AuthException("expired");
        }
        stored.markUsed();
        refreshRepo.save(stored);
        return issue(stored.getUserId());
    }
}
```

핵심 포인트:
- Refresh token 원문을 DB에 **저장하지 않는다**. SHA-256 해시만 저장 → DB 유출 시에도 토큰 재사용 불가.
- 사용됨 플래그가 재사용 탐지의 핵심.

### 검증 필터 (Resource Server)

```java
@Bean
public JwtDecoder jwtDecoder(@Value("classpath:public.pem") Resource pub) throws Exception {
    RSAPublicKey key = (RSAPublicKey) KeyFactory.getInstance("RSA")
        .generatePublic(new X509EncodedKeySpec(pub.getContentAsByteArray()));
    NimbusJwtDecoder decoder = NimbusJwtDecoder.withPublicKey(key)
        .signatureAlgorithm(SignatureAlgorithm.RS256)
        .build();
    decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
        new JwtTimestampValidator(),
        new JwtIssuerValidator("lab"),
        new JwtClaimValidator<List<String>>("aud",
            aud -> aud != null && aud.contains("lab-api"))
    ));
    return decoder;
}
```

---

## 14. 면접 답변 프레이밍

### Q. "인증을 어떻게 설계하시나요?"

**답변 뼈대 (STAR + 설계 선택 근거):**

"저는 먼저 **신뢰 경계**와 **요구사항**부터 정의합니다. 예를 들어 웹 + 모바일 + 3rd party 연동이 있는 시스템이면, 사용자는 OIDC 기반(Authorization Code + PKCE)으로 인증하고 Access Token은 RS256 JWT, 수명 10분, Refresh Token은 불투명 난수로 서버 해시 저장 + 회전 정책을 씁니다.

Access Token은 `sub`, `aud`, `exp`, `roles`, 커스텀으로 `tenant_id` 정도만 넣습니다. 민감정보는 넣지 않습니다. API Gateway에서 서명과 `aud`를 1차 검증하고, 내부 마이크로서비스에서 공개키를 캐시해 재검증합니다. 내부망은 mTLS로 보호합니다.

Rate limiting은 Gateway IP 기반 + 앱 `user_id` 기반 Redis Token Bucket 2중 구조로 두고, 비밀은 AWS Secrets Manager, DB 비밀번호는 Argon2id로 해싱합니다. 로그아웃은 Refresh Token 폐기 + Access Token은 짧은 수명으로 자연 만료를 택하되, 긴급 폐기가 필요한 도메인이면 `token_version` 클레임을 DB와 맞춰 즉시 무효화 경로를 둡니다."

### Q. "토큰이 탈취되면 어떻게 대응하시나요?"

"세 단계로 대응합니다.

**탐지** — Refresh Token Rotation의 재사용 감지, 이상 지역/디바이스 로그인 패턴, 단시간 다중 국가 접근 같은 이상 신호.

**즉시 차단** — 해당 `user_id`의 `token_version`을 +1 → 기존 모든 JWT 무효화, Refresh Token 테이블에서 `revoke_all(user_id)` 실행, 세션 캐시 무효화 이벤트를 Kafka로 브로드캐스트.

**복구와 재발 방지** — 강제 재로그인 + MFA, 감사 로그 리뷰, 키 노출 가능성이 있으면 서명키 회전(`kid` 교체), 유출 경로(XSS, 로그 누출, 클라이언트 저장소 취약점) 근본 원인 분석."

### Q. "왜 JWT를 `localStorage`에 저장하면 안 되나요?"

"XSS 한 번으로 토큰이 유출됩니다. `localStorage`는 JS에서 자유롭게 읽히기 때문입니다. `HttpOnly; Secure; SameSite=Strict` 쿠키가 XSS 노출면에서 안전하지만, CSRF 대응을 별도로 해야 하므로 BFF + CSRF 토큰 조합이 실무 정답입니다."

---

## 15. 체크리스트

- [ ] 모든 DB 쿼리가 파라미터 바인딩을 쓰는가 (`${}` 없는가)
- [ ] 리소스 소유권 검증이 서버에서 강제되는가 (IDOR 방지)
- [ ] 응답에 `Content-Security-Policy`, `X-Content-Type-Options`, `HSTS` 헤더가 있는가
- [ ] JWT 알고리즘이 코드에서 고정되어 있는가 (`alg: none` 거부)
- [ ] Access Token 수명 ≤ 15분, Refresh Token은 회전 정책이 있는가
- [ ] Refresh Token이 평문이 아니라 해시로 DB에 저장되는가
- [ ] 비밀번호가 BCrypt(≥12) 또는 Argon2id로 해싱되는가
- [ ] 토큰/세션 ID가 `SecureRandom`으로 생성되는가
- [ ] Rate limiting이 Gateway + 앱 레벨로 이중인가
- [ ] 비밀이 코드/Git에 없고 Vault/Secrets Manager에서 주입되는가
- [ ] 내부 서비스 간 통신이 mTLS이거나 최소한 JWT 재검증을 수행하는가
- [ ] `localStorage`에 토큰 저장하지 않는가
- [ ] CORS 설정이 `*` + credentials 조합이 아닌가
- [ ] CSRF가 세션 쿠키 기반 엔드포인트에 활성화되어 있는가
- [ ] `exp`, `iss`, `aud` 검증이 모두 켜져 있는가
- [ ] 로그에 토큰 원문, 비밀번호, PII가 찍히지 않는가
- [ ] 강제 로그아웃 경로(`token_version` 또는 세션 폐기)가 준비되어 있는가
- [ ] 인증 실패/이상 패턴이 감사 로그와 알림으로 연결되어 있는가
