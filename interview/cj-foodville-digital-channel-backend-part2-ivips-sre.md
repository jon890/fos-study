# [초안] CJ푸드빌 디지털 채널 — Part 2: ivips.co.kr SRE 외부 진단

> 1편 [`cj-foodville-digital-channel-backend.md`](cj-foodville-digital-channel-backend.md) 의 후속.
> 2차 면접관 커피챗 (2026-05-18 월) 어필용 외부 진단 리포트.
> **톤**: 비판이 아니라 **"외부에서 SRE 관점으로 봤을 때 이게 눈에 들어왔고, 합류하면 첫 90일에 이 순서로 보겠다"** 공동 작업자 톤.
> **모든 측정은 합류 전 외부 일반 사용자 환경에서 한 것** — 내부 메트릭·SLO·실사용자 데이터에 접근하지 않은 상태의 추론이라는 점을 분명히 한다.

---

## 분석 환경과 방법 (재현 가능성)

- **대상**: `https://www.ivips.co.kr/` (빕스 공식 사이트)
- **시점**: 2026-05-12
- **도구**:
  - `curl` / `openssl s_client` / `dig` — 정적 헤더, TLS, DNS, 인증서
  - Chrome 148 (CDP 기반 agent-browser) — 실제 JS 렌더링, `window.performance`, HAR 캡처
- **위치**: 한국 (서울) 일반 가정 회선
- **방법**: 1차 콜드 방문 + 2차 웜 방문 (쿠키 보존) 두 차례 측정

> 한계: Lighthouse·RUM·Synthetic monitoring 같은 정식 도구를 못 돌렸다. 실 사용자 RTT 분포 / 4G 회선 / 저사양 디바이스 측정은 빠져 있다. 따라서 아래 수치는 **"최선의 환경에서 본 단편"** 이지, p95 / 모바일 사용자 체감이 아니다.

---

## 한눈에 보는 점수

| 축 | 평가 | 요약 |
|---|---|---|
| **가용성 / DNS / 인증서** | ◯ | CloudFront + AWS ALB 정상, TLS 1.3 + HTTP/3, TLS 1.0/1.1 차단. DNSSEC·CAA 없음. |
| **성능 (홈 1차 방문)** | ✕ | **11.4MB / 111 자원**. Pretendard 9개 weight × 800KB woff2, **unicode-range subset 분할 0**. |
| **캐싱 정책** | △ | `s-maxage=31536000` 인데 매번 `x-cache: Miss`. `Vary` 5개 토큰 → 캐시 키 폭발 의심. |
| **보안 헤더** | ✕ | HSTS·CSP·X-Content-Type-Options·Referrer-Policy 전부 없음. **CORS `*` + `Credentials: true`** 모든 응답에 부착. |
| **쿠키 위생** | △ | `WMONID` Secure·HttpOnly 없음 (1년 만료). `JSESSIONIDSSO` 는 정상. |
| **운영 시그널** | △ | `/favicon.ico` 404 + CloudFront 에러 캐시. 강제 SSO 307 리다이렉트 (첫 방문 +1 RTT). |
| **아키텍처 단서** | ◯ | Next.js App Router + 미들웨어 `brand` 쿠키 기반 멀티브랜드 라우팅 추정. |
| **접근성 / UX** | △ | 모든 `<img>` alt 있음, CLS 0. 그러나 13/16 이미지 width/height 없음, PWA manifest 없음. |

---

## 발견 사항 — 7개 축

### 1. 가용성 / DNS / 인증서

#### 1.1 인프라 토폴로지

- `www.ivips.co.kr` → CNAME `d2626dx9y9r4ln.cloudfront.net` (AWS CloudFront, 서울 엣지 ICN57-P5)
- Origin 응답에 `AWSALBTG` 쿠키 → 원본은 **AWS ALB Target Group sticky session**
- SSO 흐름은 Apache + Tomcat (`JSESSIONIDSSO`) — CJ ONE SSO (`nsso.cjone.com`) 는 JSP 기반
- NS 레코드: AWS Route53 (`awsdns-*`) + `ns1.cj.net` / `ns2.cj.net` 혼재 — 어떤 NS 가 실제 권한자인지 외부에서 모호

#### 1.2 TLS

- **TLS 1.3** 정상 (Cipher: `AEAD-AES128-GCM-SHA256`)
- TLS 1.0 차단됨 (`alert protocol version`)
- 1차 응답 protocol `h2`, 2차 응답에서 `h3` (HTTP/3) 로 승격 — `alt-svc` 광고 동작 확인

#### 1.3 DNS / DNSSEC / CAA

- `dig DNSKEY` / `DS` / `CAA` 응답 0 → **DNSSEC 미적용, CAA 정책 없음**
- CAA 없음은 인증서 발급 권한 제어가 외부에서 강제되지 않는다는 뜻 → 임의 CA 에서 발급된 인증서를 거부할 수단 없음

#### 1.4 TCP / 핸드셰이크

콜드 방문 timing breakdown:

- DNS: 2.7ms
- TCP connect: 119ms
- TLS handshake: 19ms (connect 위에 추가)
- TTFB: 163ms

서울 엣지인데 TCP connect 119ms 는 한국 사용자 기준 살짝 큼 (일반적으로 30 \~ 50ms). HTTP/3 / QUIC 0-RTT 활성화 시 2차 방문은 거의 0ms 로 떨어짐 — 실측에서 확인됨.

---

### 2. 성능 — 폰트가 가장 큰 단일 비용

#### 2.1 1차 방문 (콜드) 총량

| 지표 | 값 |
|---|---|
| 자원 개수 | 111 |
| 전송량 합 | 11.4 MB |
| TTFB | 113ms |
| DOMContentLoaded | 390ms |
| Load | 1540ms |
| Protocol | h2 |

#### 2.2 폰트가 압도적 단일 비용

`@font-face` 인스펙트 결과:

- Pretendard 폰트 가족 **weight 100 \~ 900 모든 9 단계가 별도 woff2 파일로 등록**
- 9개 파일 모두 `<link rel="preload" as="font">` 로 강제 preload
- 각 파일 800KB+ — Top 5 가 전부 폰트, 합산 약 4MB 추정
- **`unicode-range` 적용된 폰트 룰: 0개** (11개 전체 룰 중 0)

```
font-family: pretendard; weight: 100~900;
src: url("/_next/static/media/{hash}.woff2") format("woff2");
font-display: swap;
unicode-range: (없음)  ← 여기가 핵심
```

##### 왜 이게 SRE 1차 타격감인가

Pretendard 는 한글 폰트라서 통 파일이 무거운 게 정상이다. 하지만 **9개 weight 를 다 preload + unicode-range 미분할**이면 다음이 모두 발생한다:

1. 사이트가 실제로 9개 weight 를 다 쓸 가능성은 낮다 (보통 3 \~ 5개). 안 쓰는 weight 도 강제 다운로드
2. 한글 + 영문/숫자 + 특수문자 글리프가 한 파일에 다 들어있어, 영문/숫자만 그리는 헤더 / 가격 표기에도 통 폰트가 필요
3. 첫 페이지뷰 = 4MB+ 폰트 전송 — 모바일 데이터 / 저속 회선 사용자 체감 LCP 크게 손상

##### 권장 액션 (합류 후 실험)

- 옵션 A: **Pretendard 공식 subset (`Pretendard-subset-*`)** 사용 — 라틴/한글 자주 쓰이는 글리프만, 한 weight 당 \~30KB
- 옵션 B: `unicode-range` 로 [U+0020-007F (영문/숫자)] / [U+AC00-D7A3 (한글 음절)] / [기타] 분할 → 첫 페인트에 영문 chunk 만 다운로드
- 옵션 C: **가변 폰트 (variable font) `PretendardVariable.woff2`** 1개 (\~250KB) 로 9개 weight 통합
- 가장 큰 win 은 B+C 조합. C 단독으로도 800KB × 9 → 250KB × 1 (-96%)

#### 2.3 2차 방문 (웜, HTTP/3 승격)

| 지표 | 값 |
|---|---|
| DNS / TCP / TLS | 0 / 0 / 0ms (전부 재사용) |
| TTFB | 42ms |
| DCL | 296ms |
| Load | 1187ms |
| Protocol | **h3** |
| FCP | 556ms |
| CLS | 0 |
| Long tasks | 0 |
| LCP entry | 측정 안 됨 (headless 환경 한계) |

웜 방문은 양호. HTTP/3 승격 정상. 그러나 첫 방문 11.4MB 가 그대로면 신규 사용자 / 캐시 무효화 후 첫 방문 / 모바일 데이터 사용자에게 그대로 비용 전가됨.

#### 2.4 호스트별 분포

| 호스트 | 요청 | KB | 평균 ms | 비고 |
|---|---|---|---|---|
| `www.ivips.co.kr` | 97 | 11,433 | 126 | 메인 |
| `brand-api.ivips.co.kr` | 7 | 0 | **318** | 별도 API 서브도메인, 응답 시간 큼 |
| `www.googletagmanager.com` | 1 | 0 | 424 | GTM (1개만, 깔끔) |
| `analytics.google.com` | 1 | 0 | 265 | GA4 |
| `stats.g.doubleclick.net` | 1 | 0 | 264 | GA4 redirect |
| `www.google.co.kr` | 1 | 0 | 229 | GA |

**관찰점**:

- 3rd party 스크립트는 GTM 1개만 — 매우 절제됨 (드물게 깔끔한 사례)
- `brand-api.ivips.co.kr` 7회 호출 평균 318ms — **API 서브도메인 응답 시간이 메인 정적 자원보다 2 \~ 3배 느림**. 캐시 가능한 데이터 (매장 목록 / 메뉴 / 프로모션) 인지 확인 필요. 합류 후 가장 먼저 EXPLAIN / 캐시 정책 / TTL 확인할 곳

#### 2.5 캐시 정책 모순

`/` 응답 헤더:

```
cache-control: s-maxage=31536000        ← CDN 1년 캐시 의도
vary: rsc, next-router-state-tree, next-router-prefetch,
      next-router-segment-prefetch, Accept-Encoding
x-cache: Miss from cloudfront            ← 그런데 매번 Miss
x-nextjs-cache: HIT                      ← Next.js 자체 캐시는 HIT
```

**해석**: Next.js ISR / Data Cache 는 HIT 인데 CloudFront 가 매번 origin 까지 간다. 원인 후보:

1. `Vary` 가 5개 토큰 — CloudFront 가 모든 조합마다 별도 캐시 변형 생성 → 사실상 캐시 무효화
2. Set-Cookie 응답에서 `brand=VIPS` 가 매번 갱신 — Set-Cookie 있는 응답은 CloudFront 가 기본적으로 캐시 안 함
3. CloudFront 캐시 정책 (CachePolicy) 에 `s-maxage` 존중 미설정

> 합류 후 액션: CloudFront CachePolicy 설정 확인 → `Vary` 키를 RSC 헤더만 정규화 / Set-Cookie 캐시 정책 검토.

---

### 3. 보안 — 헤더 / 쿠키 / CORS

#### 3.1 응답 헤더에 부재한 것들

`/` 응답 헤더 전수 검사 결과, **다음이 전혀 없다**:

- ❌ `Strict-Transport-Security` (HSTS) — HTTPS 다운그레이드 가능, preload 후보 자격 없음
- ❌ `Content-Security-Policy` (CSP) — XSS 1차 방어선 없음
- ❌ `X-Content-Type-Options: nosniff` — MIME 스니핑 가능
- ❌ `Referrer-Policy` — 외부 링크에 풀 URL referer 누출
- ❌ `Permissions-Policy` — 카메라/마이크/지오로케이션 등 권한 일괄 정책 없음
- ❌ `Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` / `Cross-Origin-Resource-Policy`

부착되어 있는 것:

- ✅ `X-Frame-Options: SAMEORIGIN` — clickjacking 방어 (CSP `frame-ancestors` 가 없으니 이게 마지막 보호선)

#### 3.2 CORS — 잘못된 조합

```
access-control-allow-origin: *
access-control-allow-credentials: true
```

모든 응답 (홈, robots.txt, sitemap.xml, favicon, _next/static) 에 **일관되게** 이 두 헤더가 붙어 있다.

**문제**: W3C CORS 명세상 `Allow-Origin: *` 과 `Allow-Credentials: true` 조합은 **브라우저가 차단**한다. 즉 이 헤더가 의도한 효과를 못 낸다. 하지만 시그널 자체가 잘못 설정된 상태로 모든 응답에 박혀 있다는 게 더 큰 문제 — 미들웨어 / 글로벌 응답 래퍼 / Next.js middleware 어디선가 `*` 로 박혀 있다.

##### 권장 액션

- 정적 자원에는 CORS 헤더 자체를 빼거나 (불필요)
- API 호출이 필요한 응답에는 명시적 origin 화이트리스트 (`https://www.ivips.co.kr`, `https://*.cjfoodville.co.kr` 등)
- `Allow-Credentials: true` 는 origin 명시 시에만 의미 있음

#### 3.3 쿠키 위생

| 쿠키 | Secure | HttpOnly | SameSite | 만료 | 평가 |
|---|---|---|---|---|---|
| `WMONID` | ❌ | ❌ | (없음) | 1년 | **위험** — 평문 노출 가능, JS 접근 가능, 1년 유효 |
| `JSESSIONIDSSO` | ✅ | ✅ | (없음) | 세션 | 양호 (SameSite 만 추가 권장) |
| `AWSALBTG` | ❌ | (없음) | (없음) | 7일 | ALB sticky |
| `AWSALBTGCORS` | ✅ | (없음) | None | 7일 | CORS 용 별도 변형 |
| `ssoAttempted` | ✅ | (없음) | Lax | 5분 | SSO retry 방지 |
| `skipSso` | (확인 필요) | — | — | — | 2차 방문에서 추가됨 |
| `brand` | ✅ | (없음) | Lax | 30일 | 멀티브랜드 라우팅 키 |

**핵심**: `WMONID` 는 모니터링 / 통계용 쿠키로 보이는데, 1년 유효한 식별자가 평문 + JS 접근 가능 + Secure 없이 노출. 도청 가능한 네트워크에서 사용자 식별 가능. 합류 후 1주 안에 고치고 싶은 항목.

---

### 4. 운영 시그널

#### 4.1 `/favicon.ico` 404 + CloudFront 에러 캐시

```
GET /favicon.ico → HTTP/2 404
x-cache: Error from cloudfront
```

- Next.js 가 파비콘을 `/_next/static/...` 또는 `/brand-assets/favicons/Vips_Pavicon_32.ico` 로 서빙 — 표준 경로 `/favicon.ico` 는 404
- 404 자체는 큰 문제 아니지만 **CloudFront 가 `Error from cloudfront` 를 반환** → 정적 자원 라우팅 또는 origin 응답 코드 처리 이상

검색 봇 / 링크 프리뷰 / 알림 시스템이 표준 경로를 시도하면 매번 origin 까지 가는 404 가 발생. 합류 후 정적 redirect 또는 정적 파일 추가.

#### 4.2 강제 307 SSO 리다이렉트

콜드 방문 시:

```
GET https://www.ivips.co.kr/
→ 307 redirect
→ https://nsso.cjone.com/findCookieRedirectV2.jsp?cjssoq=...&returnUrl=...
→ 다시 https://www.ivips.co.kr/
```

- 모든 신규 방문자 / `ssoAttempted` 쿠키 없는 사용자가 +1 RTT 추가
- `ssoAttempted=true` 쿠키는 **5분만 유효** — 5분 지나면 또 다시 SSO 체크
- 봇 처리: `robots.txt` 에서 NaverBot/Yeti 등 명시 Allow 이지만, **봇은 쿠키 없이 매번 SSO 리다이렉트를 받게 됨** → 봇 크롤 비용 증가 + 색인 품질 손상 가능성

> 합류 후 액션: 봇 user-agent 화이트리스트, SSO 우회 / `ssoAttempted` 쿠키 유효기간 연장 (5분 → 24시간 이상) 검토.

#### 4.3 SEO / 색인성

- `<link rel="canonical" href="https://ivips.co.kr">` — `www.` 없는 버전이 canonical, **그런데 실제 사이트는 `www.ivips.co.kr` 로 서빙됨** → canonical 불일치
- `og:image` `1200×630` 정상
- `naver-site-verification` 부착 — 네이버 서치어드바이저 등록됨
- `robots.txt` 한국 봇 (`NaverBot`, `Yeti`) 명시 Allow — 잘 되어 있음

#### 4.4 응답 헤더 노출 정보

- `Server: Apache` — SSO origin (CJ ONE)
- `x-powered-by: Next.js` — Next.js 노출
- `x-amz-cf-pop`, `via: 1.1 ...cloudfront.net` — CloudFront 노출

`x-powered-by` 정도는 제거 권장 (정보 노출 최소화).

---

### 5. 아키텍처 단서

응답 헤더와 HTML 에서 읽힌 구조:

- **프론트 스택**: Next.js 14+ App Router. 증거 — `x-powered-by: Next.js`, `x-nextjs-cache: HIT`, `x-nextjs-prerender: 1`, RSC (`_rsc=` 쿼리), `<link rel="preload" href="/_next/static/...">`, App Router 디렉터리 구조 (`/app/vips/main/page-*.js`)
- **미들웨어 라우팅**: `x-middleware-rewrite: /vips/main` — 루트 `/` 가 미들웨어에서 `/vips/main` 으로 rewrite. **`brand=VIPS` 쿠키 기반 멀티브랜드 분기**. 이 코드베이스가 빕스 외 다른 브랜드 (뚜레쥬르 등) 도 같은 Next.js 앱에서 서빙할 가능성 강함
- **CDN**: AWS CloudFront. Origin 은 AWS ALB (Target Group sticky)
- **분석/모니터링**: GA4 (`G-89GGQVQKV2`), GTM 1개 — 분석 도구 절제됨
- **별도 API 서브도메인**: `brand-api.ivips.co.kr` — 메뉴 / 매장 / 프로모션 데이터 API 추정

##### 면접 어필 포인트와 직결

이 구조가 정확이라면 멀티브랜드 코드베이스 운영 = 브랜드별 캐시 무효화 / 정책 동기화 / A/B 분기 같은 문제가 NSC 슬롯팀에서 풀던 **다중 서버 인메모리 캐시 정합성** 과 동형. 1편 [`cj-foodville-digital-channel-backend.md`](cj-foodville-digital-channel-backend.md) 의 "강점 매칭" 표 1번이 그대로 매핑된다.

---

### 6. 접근성 / UX

| 항목 | 측정 | 평가 |
|---|---|---|
| `<img>` alt 누락 | 0 / 16 | ◯ |
| `<img>` width/height 누락 | 13 / 16 | ✕ CLS 잠재 위험 |
| `<img loading="lazy">` | 11 / 16 | ◯ lazy 적용됨 |
| `<html lang>` | `ko` | ◯ |
| Skip link (`본문 바로가기`) | 있음 | ◯ |
| Heading 계층 | h1 → h2 → h3 정상 | ◯ |
| Service Worker | 없음 | — |
| PWA `manifest` | 없음 | △ 모바일 앱 설치 미지원 |
| CLS 실측 | 0 | ◯ |

13개 이미지가 명시적 크기 없음에도 실측 CLS=0 이라는 건 컨테이너 크기가 CSS 로 고정되어 있다는 뜻. 그래도 명시적 `width`/`height` 속성은 브라우저 사전 레이아웃 최적화에 도움.

---

### 7. 종합

이 사이트는 **"비교적 모던한 스택 (Next.js + CloudFront + HTTP/3) 위에 운영형 빠진 곳들이 누적된"** 상태로 보인다.

- 잘 된 것: 스택 선택, TLS 1.3 + HTTP/3, 3rd party 절제, 접근성 기본, 코드 스플릿
- 빠진 것: 보안 헤더, 폰트 최적화, 캐시 정책 정합성, 쿠키 위생, 404 처리

**이건 신규 개발 인력 부족이 아니라 "운영 표준 / SRE 관점 점검이 한 번 더 필요한" 상태에 가깝다.** 즉 내가 합류해서 매우 자연스럽게 가치를 만들 영역이 있다는 뜻.

---

## 첫 90일에 본다면 — 우선순위

> 합류 가정 하에 **외부 관점에서** 그린 작업 순서. 실제 합류 후엔 내부 SLO / 사용자 패널 / 비즈니스 우선순위와 다시 조율되어야 한다는 전제 명시.

### Week 1 \~ 2 — 위험·이득비 가장 높은 보안 / 쿠키

| # | 항목 | 변경 | 기대 효과 |
|---|---|---|---|
| 1 | HSTS 헤더 추가 | `Strict-Transport-Security: max-age=31536000; includeSubDomains` | HTTPS 다운그레이드 차단, preload 자격 |
| 2 | `X-Content-Type-Options: nosniff` | 정적·동적 응답 전부 | MIME 스니핑 차단 |
| 3 | `Referrer-Policy: strict-origin-when-cross-origin` | 글로벌 | 외부 referer 누출 최소화 |
| 4 | `WMONID` 쿠키에 `Secure; HttpOnly; SameSite=Lax` 추가 | 발행부 1곳 | 평문/JS 노출 차단 |
| 5 | CORS `*` + `Credentials: true` 제거 | 미들웨어 응답 헤더 | 잘못된 시그널 제거 |

이 5개는 **코드 변경 매우 적고 리스크 낮음**. SRE 관점에서 "1주차에 끝낼 수 있는 보안 점수 올리기" 묶음.

### Week 3 \~ 4 — 성능 (폰트가 가장 큰 single win)

| # | 항목 | 변경 | 기대 효과 |
|---|---|---|---|
| 6 | Pretendard 가변 폰트로 통합 | 9개 weight → 1개 variable woff2 | -96% 폰트 트래픽 |
| 7 | `unicode-range` 분할 | 영문 / 한글 / 기타 chunk | 첫 페인트 시 영문 chunk 만 로드 |
| 8 | preload 정리 | 9개 preload → 본문에 실제 쓰는 weight 만 | 초기 RTT 절감 |
| 9 | 이미지 `width`/`height` 속성 부여 | 13개 `<img>` | 사전 레이아웃, CLS 안정성 |

폰트 1번이 가장 큰 win. 4MB+ → \~250KB 수준. 모바일 데이터 / 신규 사용자 LCP 큰 폭 개선 예상.

### Week 5 \~ 8 — 캐시 / CDN

| # | 항목 | 변경 | 기대 효과 |
|---|---|---|---|
| 10 | CloudFront `Vary` 정규화 | RSC 관련 5개 토큰 정리 | 캐시 키 압축, hit ratio 상승 |
| 11 | `s-maxage=31536000` vs 매번 Miss 원인 진단 | Set-Cookie / CachePolicy / Vary | s-maxage 실효화 |
| 12 | `brand-api.ivips.co.kr` 평균 318ms 진단 | EXPLAIN, 캐시 적용, p95 측정 | API 응답 50ms 이하 목표 |
| 13 | `/favicon.ico` 표준 경로 보장 | rewrite 또는 정적 파일 | Error from cloudfront 제거 |

### Week 9 \~ 12 — 정책 / 거버넌스

| # | 항목 | 변경 | 기대 효과 |
|---|---|---|---|
| 14 | Content-Security-Policy 단계적 도입 | `report-only` → `enforce` 점진 | XSS 방어선 구축 |
| 15 | SSO `ssoAttempted` 만료 5분 → 24시간 | SSO 미들웨어 | 첫 방문 +1 RTT 빈도 감소 |
| 16 | DNSSEC + CAA 검토 | DNS 운영팀 협업 | 도메인 보안 강화 |
| 17 | `WMONID` 데이터 흐름 검토 | 1년 유효 식별자 필요성 자체 | GDPR / 개인정보 관점 정책 정렬 |

> 이 표는 **내가 외부 관찰만으로 짠 초안**이고, 합류 후 실제 운영팀의 우선순위 / 의존성 / 비즈니스 일정과 충돌이 있을 수 있음을 분명히 한다.

---

## 면접 어필 카드 — 3개로 압축

> 커피챗에서 이 문서를 풀로 보여주기보다, **이 3개 카드를 자연스럽게 꺼낼 준비**가 더 중요.

### 카드 1 — 폰트 (가장 강한 단일 사례)

> "외부에서 보니까 Pretendard 9개 weight 가 다 preload 되어 있고 unicode-range subset 이 없어서, 첫 페이지 4MB+ 가 폰트 비용으로 들어가더라구요. 가변 폰트 1개로 통합하면 250KB 수준까지 줄일 수 있을 것 같은데, 실제 비즈니스 영향 (모바일 사용자 비율 / 데이터 회선 / LCP SLO) 을 보면 우선순위가 어떻게 될지 궁금합니다."

→ **관찰 + 가설 + 비즈니스 질문**. 단정/비판 회피. 면접관이 답하면서 자연스럽게 내부 컨텍스트를 공유하게 만드는 톤.

### 카드 2 — 캐싱 정합성 (1편의 핵심 강점과 연결)

> "`s-maxage=31536000` 인데 매번 CloudFront Miss 가 보여서 흥미로웠습니다. Vary 가 5개 토큰이라 캐시 키가 폭발하고 있는 게 가장 의심되는데, 슬롯팀에서 다중 서버 인메모리 캐시 정합성 문제를 풀 때 비슷한 패턴 — '캐시 정책 의도와 실제 hit 동작이 어긋난 케이스' — 을 봤었거든요. 합류하면 CachePolicy 와 origin Set-Cookie 정책부터 보고 싶습니다."

→ 1편의 [강점 매칭 1번 (다중 서버 캐시 정합성)](cj-foodville-digital-channel-backend.md#강점-매칭) 과 자연스럽게 연결. 본인 강점을 외부 진단으로 link.

### 카드 3 — 보안 헤더 + SSO 트레이드오프

> "보안 헤더 (HSTS / CSP / Referrer-Policy) 가 비어 있는 부분은 1주 안에 코드 변경 적게 보강 가능해 보였고, 반면 CJ ONE SSO 강제 리다이렉트는 단순히 빼면 안 되는 비즈니스 결합이 있을 거라 합류 후 컨텍스트를 듣고 싶었습니다. 이전 팀에서 NHN Container 503 graceful shutdown 풀 때처럼 — 운영 / 비즈니스 / 인프라 사이 트레이드오프를 명확히 그리고 들어가는 걸 선호합니다."

→ "쉬운 건 빨리, 어려운 건 컨텍스트 확인 후" 라는 SRE 의사결정 톤 어필. 1편의 graceful shutdown 사례 연결.

---

## 부록 A — 측정 raw 데이터

### A.1 1차 방문 (콜드) Navigation Timing

```json
{"ttfb":113,"dcl":390,"load":1540,"transferKB":11436,
 "decodedKB":(미측정),"protocol":"h2","resourceCount":111}
```

### A.2 2차 방문 (웜) Navigation Timing

```json
{"dns":0,"tcp":0,"tls":0,"ttfb":42,"dcl":296,"load":1187,
 "protocol":"h3","redirCount":1,"redirTime":36,
 "transferKB":4,"decodedKB":23,
 "paint":{"first-contentful-paint":556,"first-paint":556},
 "cls":0,"longTaskCount":0}
```

### A.3 Initiator 분포

```
beacon:1  css:17  fetch:15  img:11  link:31  other:2  script:27  xhr:7
```

### A.4 Top 5 가장 큰 자원 (전부 woff2 폰트)

| 파일 | 호스트 | 크기 |
|---|---|---|
| `d587d1c112526568-s.p.woff2` | www.ivips.co.kr | 832,816 |
| `41b9b3ece820718f-s.p.woff2` | www.ivips.co.kr | 829,292 |
| `81b352a4d7a000ae-s.p.woff2` | www.ivips.co.kr | 826,308 |
| `eb9adf802b0a60eb-s.p.woff2` | www.ivips.co.kr | 821,700 |
| `fba9d678ff638e59-s.p.woff2` | www.ivips.co.kr | 814,960 |

### A.5 호스트별 자원 합산

| 호스트 | 요청 | KB | 평균 ms |
|---|---|---|---|
| `www.ivips.co.kr` | 97 | 11,433 | 126 |
| `brand-api.ivips.co.kr` | 7 | 0 | 318 |
| `www.googletagmanager.com` | 1 | 0 | 424 |
| `analytics.google.com` | 1 | 0 | 265 |
| `stats.g.doubleclick.net` | 1 | 0 | 264 |
| `www.google.co.kr` | 1 | 0 | 229 |

### A.6 `@font-face` 룰

- 총 11개 룰, **`unicode-range` 적용 0개**
- Pretendard weight 100, 200, 300, 400, 500, 600, 700, 800, 900 (9 단계) — 모두 `font-display: swap`
- swiper-icons (data URI), Pretendard Fallback (local Arial) 각 1개

### A.7 `<link rel="preload">` 분포

```
font:9  image:4  script:2  style:6
```

### A.8 HAR

- 저장 위치: `/tmp/ivips-sre/ivips.har` (200KB, 48 요청)
- 모든 응답 코드: 200 (46) + 204 (2)
- 추가 prefetch: `_rsc=` 파라미터로 멤버십 / 매장 / 매장 검색 라우트 사전 로드

---

## 부록 B — 후속 검증이 필요한 항목

이 문서의 추론 중 다음은 외부에서 확정 불가, 합류 후 또는 면접에서 확인 권장:

1. `WMONID` 가 실제로 어떤 데이터를 담는지 (개인 식별자인지 / 단순 통계 토큰인지)
2. CORS `*` + Credentials 가 미들웨어에서 박힌 게 의도인지 / 실수인지
3. CloudFront CachePolicy 실제 설정 (Vary 처리, Set-Cookie 처리)
4. 폰트 9개 weight 가 실제로 다 쓰이는지 (사용 통계 확인)
5. `brand-api.ivips.co.kr` 평균 318ms 의 p95 / p99 분포
6. 멀티브랜드 (`brand` 쿠키) 라우팅 — 뚜레쥬르 / 빕스 외 어떤 브랜드가 같은 코드베이스인지
7. SSO `ssoAttempted` 5분 만료가 의도된 정책인지 / 보안 요건인지
8. canonical `https://ivips.co.kr` vs 실 서빙 `https://www.ivips.co.kr` 불일치가 의도인지

---

## 근거 자료

- 1편: [`cj-foodville-digital-channel-backend.md`](cj-foodville-digital-channel-backend.md)
- 측정 도구:
  - agent-browser 0.27.0 (Chromium CDP 기반) — https://github.com/vercel-labs/agent-browser
  - `curl`, `openssl s_client`, `dig` — 표준 CLI
- 빕스 공식 사이트: https://www.ivips.co.kr/
- CJ ONE SSO: https://nsso.cjone.com/findCookieRedirectV2.jsp
- 참고: CloudFront CachePolicy 문서, Pretendard 공식 subset 가이드 (변수 폰트), W3C CORS 명세 (Allow-Origin `*` + Credentials 조합)
