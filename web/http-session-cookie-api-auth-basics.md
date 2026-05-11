# [초안] HTTP / Cookie / Session / Token 인증 기본기 — 레거시 JSP와 모바일 API가 공존하는 백엔드 관점

## 왜 이 주제가 중요한가

CJ푸드빌 같은 디지털 채널 운영사는 사내 어드민과 매장/가맹점용 웹은 여전히 JSP + jQuery + 서버 세션 기반인 경우가 많고, 동시에 자사 앱과 외부 파트너 연동은 토큰 기반 API로 굴린다. 시니어 백엔드 인터뷰에서 "세션이랑 토큰의 차이가 뭐냐"라는 질문은 단순 정의를 보는 게 아니라, **하나의 인증 인프라 위에서 레거시 채널과 신규 채널이 공존하는 상황을 어떻게 설계해 봤는지**를 본다. 인증은 장애가 나면 사용자 전부가 막힌다는 점에서 SLA에 직접 영향을 주는 영역이고, 보안 이슈(CSRF, 세션 고정, 토큰 탈취)는 이력서 한 줄짜리 사고로 직결된다.

이 문서는 HTTP의 stateless 특성에서 출발해 Cookie → Session → Token 순서로 인증 모델을 쌓고, JSP 레거시와 모바일 API가 공존하는 구체 패턴, CSRF/CORS/SameSite의 실전 함정, 흔한 인증 장애 회복 시나리오, 그리고 인터뷰 답변 프레임을 한 번에 정리한다.

## 1. HTTP는 왜 stateless인가, 그리고 그게 무슨 뜻인가

HTTP는 한 번의 요청과 한 번의 응답을 한 단위로 처리한다. 서버는 기본적으로 이전 요청을 기억하지 않는다. 같은 사용자가 보낸 요청이라는 사실조차 프로토콜 자체로는 알 수 없다. 이게 stateless의 핵심이다.

그런데 실서비스에서는 "이 요청을 보낸 사용자가 누구인가"라는 상태가 반드시 필요하다. 결제 요청을 보낸 사용자와 장바구니에 담은 사용자가 동일인이라는 보장이 있어야 하기 때문이다. 그래서 우리는 stateless 위에 인증 상태를 얹는 장치를 추가로 구현한다. Cookie, Session, Token이 모두 그 장치다.

stateless를 "서버가 아무 상태도 안 가진다"로 오해하면 안 된다. 정확히는 **"HTTP 프로토콜 레벨에서 요청 간 연결성이 없다"**는 의미고, 애플리케이션 레벨에서는 거의 항상 무언가 상태를 들고 있다. 다만 그 상태를 어디에 두느냐(서버 메모리 / 외부 저장소 / 클라이언트)에 따라 운영 특성이 완전히 달라진다.

## 2. Cookie — 모든 인증의 운반 수단

Cookie는 서버가 응답에 `Set-Cookie` 헤더를 실어서 클라이언트에 저장시키고, 이후 같은 도메인으로 요청이 갈 때 브라우저가 자동으로 `Cookie` 헤더에 실어 보내는 단순한 키-값이다. Cookie 그 자체는 인증 수단이 아니라 **인증 식별자를 운반하는 수단**이다.

실무에서 반드시 챙겨야 하는 속성:

- `Secure` — HTTPS에서만 전송. 운영 환경 쿠키는 무조건 켠다.
- `HttpOnly` — JavaScript `document.cookie`에서 읽지 못하게 막는다. XSS로 토큰이 탈취되는 가장 흔한 경로를 차단한다.
- `SameSite` — 다른 사이트에서 시작된 요청에 쿠키를 자동 첨부할지 결정한다. `Strict`, `Lax`, `None` 세 가지.
  - `Lax`(브라우저 기본값) — 일반적인 GET 이동에는 쿠키가 가지만, 외부 사이트의 form POST에는 가지 않는다. CSRF 1차 방어선.
  - `None` — 크로스 사이트 요청에도 쿠키를 보낸다. 단, `Secure`가 강제된다. 외부에서 자사 API를 쿠키로 호출하는 도메인 분리 환경에서 필요.
  - `Strict` — 외부 링크 클릭으로 들어와도 쿠키가 안 붙는다. 로그인이 풀린 것처럼 보이기 때문에 사용자 동선에 따라 신중히 적용.
- `Domain`, `Path` — 어느 범위에서 쿠키가 자동 첨부될지 결정. 서브도메인 분리 환경에서 의도와 다르게 다른 서비스로 쿠키가 새는지 점검한다.
- `Max-Age` / `Expires` — 만료. 세션 쿠키는 굳이 영구 만료를 줄 필요가 없다.

Cookie 자체는 단순하지만 위 속성을 빼먹어서 사고가 나는 경우가 압도적으로 많다.

## 3. Session — 서버가 상태를 들고 있는 모델

Session은 **인증 상태를 서버 측 저장소에 두고, 클라이언트에는 식별자만 쿠키로 내려주는** 패턴이다. 톰캣/스프링 시큐리티 기본 설정도 이 모델이고, JSP 시대부터 가장 익숙한 형태다.

흐름:

1. 사용자가 로그인 요청을 보낸다.
2. 서버가 자격 증명을 검증하고, 사용자 정보를 서버 측 세션 저장소에 기록한다. 이때 무작위 세션 ID가 발급된다.
3. 응답에 `Set-Cookie: JSESSIONID=...; HttpOnly; Secure; SameSite=Lax`를 실어 보낸다.
4. 다음 요청부터 브라우저가 JSESSIONID를 자동 첨부한다.
5. 서버는 JSESSIONID로 세션 저장소를 조회해 사용자 컨텍스트를 복원한다.

세션 저장소 위치는 운영 특성을 좌우한다.

- **WAS 메모리**(in-memory) — 단일 인스턴스에서는 가장 빠르고 단순하지만, 서버를 늘리는 순간 인스턴스마다 세션이 따로 생긴다. 로드밸런서 sticky session으로 임시 봉합 가능하지만 인스턴스 재기동에 약하다.
- **Redis 등 외부 세션 스토어** — 수평 확장 가능. 스프링이라면 `spring-session-data-redis`로 거의 코드 수정 없이 전환된다. 운영 표준에 가깝다.
- **DB** — 가능은 한데 조회 빈도가 너무 높아 비용 대비 효과가 낮다.

세션 모델의 강점은 **로그아웃이 즉시 반영된다**는 점이다. 서버에서 세션을 지우면 끝이다. 이는 토큰 모델 대비 명확한 이점이다.

약점은 **상태가 서버에 있다**는 점에서 온다. 서버를 무중단 배포할 때 세션 호환성을 고려해야 하고, 모바일 앱이나 외부 파트너 API가 쿠키 기반 세션을 쓰는 건 어색하다. 그래서 토큰이 등장한다.

## 4. Token (JWT 포함) — 클라이언트가 상태를 들고 있는 모델

Token 인증은 **인증 정보를 토큰 자체에 넣어 클라이언트가 보관**하고, 매 요청마다 `Authorization: Bearer <token>` 헤더로 실어 보내는 모델이다. JWT(JSON Web Token)가 가장 흔하다.

JWT는 `header.payload.signature` 형태의 점-구분 문자열이다. payload에는 `sub`(사용자 식별자), `exp`(만료 시각), `iat`(발급 시각), 권한 같은 클레임이 base64url로 인코딩되어 들어간다. signature는 비밀키 또는 RSA 키쌍으로 서명되어, 위변조 시 검증에서 실패한다.

핵심: **JWT의 payload는 암호화가 아니라 서명이다.** base64 디코드만 하면 누구나 읽는다. 따라서 비밀번호, 주민번호, 결제 카드 정보를 payload에 넣으면 안 된다. 식별자, 권한 같은 노출돼도 무방한 정보만 담는다.

토큰 모델 특성:

- **Stateless** — 서버는 토큰을 따로 저장할 필요 없이 서명만 검증한다. 수평 확장이 쉽다.
- **다채널 친화적** — 모바일 앱, 외부 파트너, SPA 어디서든 동일한 헤더 규약으로 호출한다.
- **즉시 로그아웃이 어렵다** — 발급된 JWT는 만료 전까지 유효하다. 강제 만료가 필요하면 결국 서버 측에 블랙리스트나 화이트리스트를 둬야 하는데, 그러면 stateless 장점이 일부 희석된다.
- **토큰 탈취 시 영향이 크다** — 서버가 토큰 자체를 들고 있지 않기 때문에, 만료 시각까지 그 토큰으로 다 호출 가능하다. 그래서 access token 수명을 짧게 가져간다.

## 5. Refresh Token — 짧은 access token과 긴 refresh token의 분리

토큰 수명을 짧게 두면 보안은 좋아지지만 사용자 경험이 나빠진다. 그래서 보편 패턴은 다음과 같다.

- **Access Token** — 수명 5\~15분. 매 API 호출에 사용.
- **Refresh Token** — 수명 1\~14일. access token이 만료되면 이걸로 새 access token을 발급받는 데만 쓴다.

Refresh token은 access token과 달리 **서버 측에 저장**해서 폐기 가능 상태로 관리하는 게 일반적이다. 사용자 로그아웃, 비밀번호 변경, 디바이스 강제 로그아웃 시 refresh token 자체를 무효화하면 access token이 만료되는 순간부터 재발급이 막힌다.

저장 위치 선택:

- 모바일 앱 — OS 보안 저장소(Keychain/Keystore).
- 웹 SPA — refresh token은 `HttpOnly` + `Secure` + `SameSite=Strict` 쿠키에 두는 패턴이 안전하다. localStorage에 두면 XSS 한 방에 털린다.

흔한 실수: refresh token으로 새 access token만 받고, refresh token은 그대로 재사용. **rotation**이 권장된다. 즉, refresh 호출마다 새 refresh token을 같이 발급하고 이전 것을 무효화한다. 토큰 재사용 탐지 시 즉시 모든 세션을 만료시키면, 탈취된 refresh token으로 공격자가 활동하는 흔적을 잡을 수 있다.

## 6. Stateful vs Stateless — 어디에 둘 것인가

| 관점 | Session(Stateful) | Token(Stateless) |
|------|------------------|------------------|
| 상태 위치 | 서버 측 저장소 | 클라이언트(JWT 자체) |
| 수평 확장 | 외부 세션 스토어 필요 | 자연스러움 |
| 즉시 로그아웃 | 즉시 가능 | 어려움(블랙리스트 필요) |
| 모바일/외부 API | 어색함 | 자연스러움 |
| 탈취 시 회복 | 세션 삭제로 종료 | 만료까지 유효 |
| 페이로드 노출 | 식별자만 노출 | payload base64로 노출 |
| 디버깅 | 서버 로그로 풍부 | 토큰 디코드로 일부 |

핵심 판단 기준은 **채널 구성**이다. 사내 어드민/JSP 화면처럼 브라우저-서버가 동일 도메인에서 끝나면 세션이 단순하고 강하다. 모바일 앱·외부 파트너·SPA가 끼면 토큰이 자연스럽다. 실무는 둘을 같이 운영하는 경우가 많다.

## 7. JSP/jQuery 레거시 세션 + 모바일 API 토큰 공존 설계

CJ푸드빌처럼 외식·매장 운영 백엔드는 다음 구성이 흔하다.

- 가맹점/매장 어드민 — JSP + jQuery, 톰캣 세션, JSESSIONID 쿠키 기반.
- 자사 앱(주문/멤버십) — REST API + JWT.
- POS/외부 파트너 — API 키 또는 OAuth2 client credentials.

같은 사용자 도메인을 다루지만 인증 채널이 다르다. 설계 포인트:

1. **사용자/권한 모델은 단일화**한다. 인증 방식만 어댑터 레이어에서 분기한다. Spring Security라면 `SecurityFilterChain`을 URL 패턴별로 분리해 어드민 경로는 폼 로그인 + 세션, `/api/**`는 JWT 필터로 묶는다.
2. **세션 쿠키와 토큰의 도메인 책임을 명확히 한다.** 어드민은 `admin.example.com`, API는 `api.example.com`처럼 호스트를 분리하면 쿠키와 토큰이 서로 간섭하지 않는다. 같은 호스트에서 둘 다 받으려면 SameSite/Secure/Path를 정밀하게 잡아야 한다.
3. **CSRF 방어 적용 범위를 다르게 한다.** 세션 + 쿠키 자동 첨부 경로는 CSRF 토큰이 반드시 필요하고, `Authorization` 헤더로 토큰을 명시적으로 싣는 API 경로는 CSRF가 구조적으로 발생하지 않는다. Spring Security 기본 설정에서 `/api/**`는 `csrf.disable()` 또는 `ignoringRequestMatchers`로 빼고, 어드민 경로는 활성화한다.
4. **로그아웃 일관성**을 챙긴다. 어드민 로그아웃은 세션 무효화로 끝, API 로그아웃은 refresh token 삭제. 사용자가 한쪽에서 로그아웃했다고 다른 쪽이 자동 종료되지 않으니 운영자 가이드에 명시한다.
5. **싱글 사이트 멀티 채널 SSO**가 필요하면 OAuth2/OIDC 기반의 IdP를 별도로 두고 각 애플리케이션이 그쪽으로 위임한다. JSP에 직접 토큰 검증을 박는 것보다 reverse proxy(예: Spring Cloud Gateway, Nginx + auth_request)에서 인증을 먼저 끝내는 편이 레거시 변경을 줄인다.

## 8. CSRF, CORS, SameSite — 자주 헷갈리는 셋

이 셋은 다른 문제를 푸는데 같이 등장해서 자주 섞인다.

- **CSRF**(Cross-Site Request Forgery) — 다른 사이트가 사용자의 인증 쿠키가 자동 첨부되는 점을 악용해 의도치 않은 요청을 강제하는 공격. **세션·쿠키 기반 인증에서 발생**한다. 방어는 (1) `SameSite=Lax/Strict`, (2) CSRF 토큰(폼/헤더에 추가 토큰), (3) 중요한 변경은 POST + Origin 검증. `Authorization` 헤더로 토큰을 명시하는 API에는 발생하지 않는다.
- **CORS**(Cross-Origin Resource Sharing) — 브라우저가 다른 origin으로 가는 XHR/fetch를 막는 보안 모델을 풀어주기 위한 헤더 규약. 서버가 `Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials` 등을 응답으로 주면 브라우저가 통과시킨다. **공격 방어가 아니라 합법적 크로스오리진 허용 메커니즘**이라는 점이 중요하다. CORS를 푼다고 CSRF가 같이 풀리는 게 아니다.
- **SameSite** — 위에서 다룬 쿠키 속성. CSRF 1차 방어선이자 동시에 크로스도메인 쿠키 첨부 정책. `None`을 쓰려면 반드시 `Secure`가 같이 필요하다.

흔한 사고: 프론트가 다른 origin으로 분리되며 CORS를 열고 `credentials: include`로 쿠키를 보내려는데 SameSite가 `Lax`라 쿠키가 안 가서 401이 난다. 또는 그걸 풀려고 `SameSite=None; Secure`로 바꿨는데, 운영 환경 HTTPS 인증서가 일부 경로에 누락되어 쿠키가 안 실리는 경우. 둘 다 운영에서 자주 겪는다.

## 9. Bad vs Improved 예제

### Bad — JWT를 localStorage에 저장하고 access token을 24시간 발급

```javascript
// 프론트 - 로그인 응답 처리
const res = await fetch('/api/login', { method: 'POST', body: ... });
const { accessToken } = await res.json();
localStorage.setItem('token', accessToken);

// 매 요청
fetch('/api/orders', { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
```

문제:
- localStorage는 XSS로 그대로 털린다.
- access token 24시간이라 탈취 시 영향 시간이 매우 길다.
- refresh 개념이 없어 강제 로그아웃이 사실상 불가.

### Improved — 짧은 access token + HttpOnly 쿠키 refresh token + rotation

```http
POST /auth/login → 200
Set-Cookie: refresh=eyJ...; HttpOnly; Secure; SameSite=Strict; Path=/auth; Max-Age=604800
Body: { "accessToken": "eyJ...", "expiresIn": 600 }

GET /api/orders
Authorization: Bearer eyJ...

POST /auth/refresh   (브라우저가 refresh 쿠키 자동 첨부)
→ 200
Set-Cookie: refresh=eyJ_NEW...; HttpOnly; Secure; SameSite=Strict; Path=/auth
Body: { "accessToken": "eyJ_NEW...", "expiresIn": 600 }
```

핵심:
- access token은 메모리에만 보관(JS 변수). 새로고침 시 refresh로 다시 받는다.
- refresh token은 `HttpOnly` 쿠키라 JS가 못 읽음 → XSS로 못 빼간다.
- `Path=/auth`로 다른 API 호출에는 자동 첨부되지 않게 범위 제한.
- 서버는 refresh token rotation + DB 저장으로 강제 무효화 가능.

### Bad — 어드민 폼이 GET으로 권한 변경

```html
<a href="/admin/users/42/grant?role=ADMIN">관리자로 승격</a>
```

문제: 외부 사이트가 `<img src="https://admin.example.com/admin/users/42/grant?role=ADMIN">`만 심어두면, 운영자 브라우저에 JSESSIONID가 자동 첨부되어 호출이 성공한다. 전형적 CSRF.

### Improved — 상태 변경은 POST + CSRF 토큰 + SameSite=Lax

```html
<form method="post" action="/admin/users/42/grant">
  <input type="hidden" name="_csrf" value="${_csrf.token}">
  <input type="hidden" name="role" value="ADMIN">
  <button>관리자로 승격</button>
</form>
```

서버는 세션에 보관한 CSRF 토큰과 폼 토큰을 비교한다. SameSite=Lax가 같이 걸려 있으면 외부 form POST에는 JSESSIONID 자체가 안 붙어 1차 방어가 더해진다.

## 10. 로컬 실습 환경

Spring Boot 3 + Spring Security 6 기준이면 충분하다. 별도 인증 서버 없이 같은 애플리케이션에서 두 채널을 모두 흉내 낼 수 있다.

```bash
mkdir auth-lab && cd auth-lab
curl https://start.spring.io/starter.tgz \
  -d dependencies=web,security,thymeleaf,session \
  -d type=gradle-project -d language=java -d javaVersion=21 \
  -d groupId=com.example -d artifactId=auth-lab \
  | tar -xzvf -
./gradlew bootRun
```

세션 모델 확인:
```bash
curl -i -c cookies.txt -b cookies.txt -X POST localhost:8080/login \
  -d username=user -d password=...
curl -i -b cookies.txt localhost:8080/admin
```
응답 헤더에서 `Set-Cookie: JSESSIONID=...; HttpOnly`가 보이는지, 두 번째 호출에서 같은 세션이 유지되는지 확인한다.

JWT 모델은 `spring-boot-starter-oauth2-resource-server`를 추가하고 `OncePerRequestFilter`에서 `Authorization` 헤더를 파싱하는 방식으로 작은 필터를 직접 구현해도 학습 효과가 크다.

`SameSite` 동작 확인:
```bash
docker run -it --rm -p 8080:8080 nginxdemos/hello   # 다른 origin 흉내
```
다른 origin에서 `<form action="http://localhost:8081/transfer">`를 만들어 제출했을 때 JSESSIONID가 첨부되는지 브라우저 개발자도구 Network 탭에서 직접 확인한다. 쿠키 속성을 `Lax → None; Secure → Strict`로 바꿔가며 동작이 변하는 걸 눈으로 본다.

## 11. 자주 만나는 인증 장애 시나리오

1. **세션 스토어(Redis) 장애** — 모든 사용자가 강제 로그아웃. 회복 후에도 새 세션부터 다시 쌓이므로 고객센터 문의가 폭주한다. 대응은 (1) 세션 스토어 이중화, (2) 일정 시간 동안 인증 우회 가능한 자동 재로그인 토큰을 클라이언트에 같이 보관, (3) 사용자 안내 메시지 사전 준비.
2. **JWT 서명키 유출** — 즉시 키 회전 + 모든 토큰 무효화. 키는 보통 `kid`(key id)로 식별하니, 신규 `kid` 발급 + 구 `kid` 거부 정책으로 점진 전환한다. refresh token까지 모두 폐기 후 강제 재로그인.
3. **시계 동기화 실패로 토큰 만료 오판** — `exp` 기반 검증이라 서버 시계가 어긋나면 모든 토큰이 만료/미만료 오판된다. NTP는 인프라 점검 항목.
4. **쿠키 도메인 잘못 잡아 다른 서비스로 누출** — `Domain=.example.com`으로 설정해 서브도메인 전체에 쿠키가 새는 사고. 점검 포인트는 항상 가장 좁게.
5. **로그아웃 후에도 다른 탭이 계속 호출** — 세션 모델이면 401 후 자연 종료, 토큰 모델이면 만료 전까지 호출이 가능하므로 클라이언트가 401 응답을 받았을 때 토큰을 즉시 폐기하고 재로그인 화면으로 보내야 한다.

## 12. 시니어 백엔드 인터뷰 답변 프레임

질문: **"세션과 토큰의 차이를 설명해 주세요."**

답변 프레임(60초):
1. **상태 위치 비교** — 세션은 서버, 토큰은 클라이언트.
2. **운영 특성** — 세션은 즉시 로그아웃에 강하지만 외부 세션 스토어가 필요. 토큰은 수평 확장과 다채널에 강하지만 즉시 폐기가 어려워 access token을 짧게 가져가고 refresh token을 분리한다.
3. **본인 경험 연결** — JSP 어드민과 모바일 API가 공존하는 상황에서 어드민은 세션, API는 JWT로 분리하고, refresh token은 HttpOnly 쿠키 + rotation 방식으로 운영했다.
4. **trade-off 자각** — 토큰 즉시 무효화가 필요한 케이스(권한 강제 회수 등)에는 서버 측 블랙리스트 또는 짧은 access token + 빠른 refresh로 대응했고, 완전 stateless를 고집하지 않았다.

질문: **"CSRF와 CORS는 다른 문제인가요?"**

답변 프레임:
- 다른 문제다. CSRF는 인증 쿠키 자동 첨부를 악용한 공격, CORS는 브라우저가 크로스 오리진 요청을 합법적으로 허용하기 위한 협상 규약.
- CSRF는 세션 기반 인증에서 발생하고, `Authorization` 헤더 기반 API에서는 구조적으로 발생하지 않는다.
- CORS를 푼다고 CSRF 방어가 풀리지 않는다. 둘은 독립.

질문: **"JWT를 어디에 저장하시나요?"**

답변 프레임:
- access token은 메모리, refresh token은 HttpOnly + Secure + SameSite 쿠키에 둔다.
- localStorage는 XSS 한 방에 털리기 때문에 운영 서비스에서는 피한다.
- 토큰 rotation과 만료 정책을 같이 설명한다.

## 13. 체크리스트

- [ ] 운영 쿠키에 `Secure`, `HttpOnly`, `SameSite` 모두 명시했는가
- [ ] 세션 스토어가 단일 인스턴스에 묶여 있지 않은가, 장애 시나리오 점검했는가
- [ ] JWT 서명키 회전 절차가 문서화되어 있는가
- [ ] access token 수명이 짧고, refresh token rotation을 적용했는가
- [ ] refresh token은 서버 측에서 폐기 가능한 상태로 관리되는가
- [ ] 어드민(세션) 경로는 CSRF 방어가, API(토큰) 경로는 CORS 정책이 분리되어 있는가
- [ ] 상태 변경은 GET이 아닌 POST/PUT/PATCH/DELETE로 강제되는가
- [ ] 쿠키 `Domain` 범위가 의도한 호스트만 포함하는가
- [ ] 로그아웃 시 양쪽 채널(세션·토큰)이 모두 종료되는 흐름이 있는가
- [ ] 401 응답을 받은 클라이언트가 토큰을 즉시 폐기하고 재로그인 흐름으로 들어가는가
- [ ] 인증 모듈 변경 배포 시, 진행 중 세션·토큰 호환성을 점검했는가
