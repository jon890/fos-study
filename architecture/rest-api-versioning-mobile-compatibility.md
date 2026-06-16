# [초안] REST API 버저닝과 모바일 앱 하위 호환성 — 디지털 채널 백엔드 관점

## 왜 중요한가

매장·키오스크·모바일 앱·웹·파트너사 연동을 동시에 운영하는 외식 커머스 도메인에서 REST API는 **여러 세대의 클라이언트가 동시에 살아 있는 상태**를 전제로 한다. 백엔드는 일주일에 두세 번 배포할 수 있지만, iOS/Android 앱은 그렇지 않다. 앱스토어 심사, 사용자 강제 업데이트 동의, 구버전 OS 잔존, 사내 매장 단말의 펌웨어 라이프사이클까지 고려하면 "옛날 클라이언트가 오늘도 호출한다"는 사실이 운영의 기본값이다.

이 상태에서 API를 그냥 바꾸면 앱이 흰 화면을 띄우고, 키오스크가 결제 직전에 멈추고, 파트너사 정산 배치가 깨진다. "모바일 앱이 강제 업데이트가 안 되는 환경에서 결제 응답 스키마를 바꿔야 한다면 어떻게 하는가"라는 문제는 단순히 "v2로 올린다"로 끝나지 않는다. **버저닝 전략, 호환성 룰, 폐기 절차, 롤백 안전망, 검증 수단**까지 한 줄기로 이어져야 안전하다.

이 문서는 그 한 줄기를 정리한다. 큰 분류 체계나 RFC 인용을 목표로 하지 않고, 실제 백엔드 엔지니어가 모바일 앱 호환성 사고를 줄이기 위해 **무엇을 안 바꾸고**, **무엇은 어떻게 바꾸고**, **어떻게 측정하는지**를 다룬다.

## 핵심 개념 — 무엇이 깨지는 변경이고 무엇이 안 깨지는가

API 버저닝의 본질은 "버전 번호를 어디 박을 것인가"가 아니라 "이 변경이 기존 클라이언트를 깨뜨리는가"를 정확히 분류하는 일이다. 클라이언트가 자유롭게 업그레이드할 수 있는 환경(서버-서버, 사내 콘솔)과 그렇지 않은 환경(앱스토어를 거치는 모바일 앱, 매장 단말)을 같은 규칙으로 다루면 안 된다.

### Breaking change 정의

다음 변경은 기본적으로 깨지는 변경으로 본다. 모바일 앱처럼 강제 업데이트가 어려운 채널에서는 이 목록을 더 보수적으로 적용한다.

- 필드 제거 (request/response 양쪽 다)
- 필드 타입 변경 (`int` → `string`, `string` → `object`)
- 필드 의미 변경 (`amount`가 KRW였는데 USD로 바뀜)
- 필수 필드 추가 (request에 새 required 필드)
- enum 값 제거 또는 의미 재정의
- HTTP 상태코드 의미 변경
- 에러 응답 스키마 변경
- 인증 헤더 이름·포맷 변경
- 페이징 키, 정렬 기본값 변경

### Non-breaking change

다음은 일반적으로 안전한 additive change로 다룬다. 단, 클라이언트가 strict한 JSON 디시리얼라이저를 쓰면 추가 필드도 사고가 될 수 있으니 **클라이언트 파서 정책을 사전에 합의**하는 것이 전제다.

- response에 새 필드 추가 (클라이언트는 unknown field 허용)
- request에 새 optional 필드 추가
- 새 enum 값 추가 (단, 클라이언트가 unknown enum을 안전하게 처리해야 함 — 뒤에서 자세히 다룸)
- 새 endpoint 추가
- 새 HTTP 메서드 추가
- 응답 헤더 추가

### Tolerant reader 원칙

모바일 채널을 책임지는 백엔드는 클라이언트에게 **우리가 모르는 필드와 enum이 와도 죽지 마라**는 약속을 받아두어야 한다. 이걸 보통 tolerant reader라고 한다. iOS의 `Codable`, Android의 Moshi/Gson, Kotlin Serialization 모두 unknown key 무시 옵션을 제공한다. 백엔드 단독으로 결정할 수 있는 일은 아니지만, 버저닝 정책을 만들 때 모바일팀과 합의해야 할 0순위 항목이다.

## 모바일 앱이 강제 업데이트가 어려운 이유 — 백엔드가 알아야 할 만큼만

"왜 강제 업데이트가 어려운가"는 다음 정도로 정리할 수 있다.

- 앱스토어 심사가 길게는 며칠 걸리고, 거절되면 일정이 더 밀린다.
- 강제 업데이트를 띄워도 사용자가 즉시 받아주지 않는다 (셀룰러 데이터 부담, 단말 저장공간, 결제 직전 회피).
- iOS는 Apple 정책상 무리한 강제 업데이트를 권장하지 않는다.
- 매장에 깔린 키오스크/POS는 자동 업데이트가 아니라 점주가 수동으로 동의해야 하는 경우가 있다.
- 결제 SDK 업데이트와 함께 가야 하는 경우, 외부 의존성 일정이 묶인다.

따라서 백엔드가 잡아야 할 가정은 단순하다.
**오늘 배포한 API는 6개월\~1년 뒤에도 같은 의미로 호출될 가능성이 있다.**

이 가정을 받아들이면 v1을 v2로 한 번에 갈아엎는 시나리오는 거의 비현실적이라는 것이 자연스럽게 나온다.

## 버저닝 전략 — URI vs Header

크게 두 가지가 실무에서 살아남는다.

### URI 버저닝 — `/v1/orders`

장점은 단순하고, 캐시 키가 자연스럽게 분리되며, 게이트웨이 라우팅이 쉽다는 것이다. 단점은 버전을 올리면 모든 경로가 새 트리로 분기해 코드 중복이 늘어난다는 점이다.

운영 관점에서는 **메이저 버전만 URI에 박는다**. 마이너 변경(필드 추가, 새 enum 추가)을 위해 v1.1, v1.2 같은 경로를 만드는 순간 라우팅과 문서가 폭발한다.

### Header 버저닝 — `Accept: application/vnd.commerce.v1+json` 또는 `X-API-Version: 2026-04-01`

날짜 기반 버저닝(Stripe 스타일)은 **마이크로 버저닝**이 가능해 모바일 앱에 매우 잘 맞는다. 클라이언트는 빌드 시점의 날짜를 박고, 서버는 그 날짜에 맞춘 응답을 만든다. 단점은 게이트웨이/캐시/관측 도구가 헤더를 인지하도록 추가 설정이 필요하고, 문서화가 URI보다 어렵다는 것이다.

### 실무 절충

모바일 앱 중심 도메인에서는 **메이저는 URI, 마이너는 헤더**의 하이브리드가 자주 보인다.

- `/v1/orders` 경로 자체는 5\~10년 단위로 유지
- 그 안에서 의미가 바뀌는 응답은 `X-API-Version: 2026-04-01` 같은 날짜 헤더로 분기
- 클라이언트는 빌드 시점의 날짜를 빌드 상수로 박음
- 서버는 헤더가 없으면 "가장 보수적인 과거 동작"으로 폴백

## Additive change를 안전하게 하는 패턴

### 응답에 필드를 추가할 때

response에 `loyaltyPoint`를 새로 넣는다고 하자. 깨지지 않으려면 다음을 지킨다.

- 기존 필드의 의미·타입을 건드리지 않는다.
- 새 필드는 nullable로 시작한다. 데이터가 아직 없는 주문도 있기 때문이다.
- 클라이언트가 "필드 없으면 0"이라고 멋대로 해석하지 않도록 의미를 명세에 못박는다 (`null = 미적립 대상`, `0 = 적립 대상이지만 0점`).

```json
{
  "orderId": "ORD-2026-0001",
  "amount": 18900,
  "currency": "KRW",
  "loyaltyPoint": null
}
```

### Request에 필드를 추가할 때

기존 클라이언트는 새 필드를 못 보낸다. 따라서 새 필드는 **항상 optional**이고, 서버는 누락 시 합리적인 기본값을 정의해야 한다. 기본값을 "에러"로 두면 사실상 breaking change다.

```http
POST /v1/orders
{
  "menuId": "MENU-001",
  "quantity": 2,
  "couponCode": "WELCOME"      // 신규 필드. 누락 시 쿠폰 미적용으로 처리
}
```

### Enum 확장 — 가장 자주 사고 나는 지점

enum은 "추가는 안전하다"고 흔히 말하지만, 클라이언트가 unknown enum을 안전하게 처리하지 못하면 그 자리에서 크래시가 난다. 호환성 사고가 가장 잘 나는 지점이다.

문제 시나리오: `OrderStatus`에 기존 `CREATED`, `PAID`, `CANCELED`만 있었는데 `REFUND_PENDING`을 추가했다. iOS 앱이 `Codable`로 strict하게 디코딩하면 unknown enum에서 throw가 나서 주문 상세 화면 자체가 깨진다.

대응 원칙:

- 클라이언트 측: unknown enum은 `UNKNOWN`으로 폴백하도록 설계하고, 화면에는 "처리 중"처럼 안전한 기본 메시지를 띄운다.
- 백엔드 측: 새 enum 값을 추가할 때 **기존 enum 값에 매핑되는 fallback 의미**를 명세에 같이 적는다. 예: "`REFUND_PENDING`은 1.5.0 이전 클라이언트에서는 `CANCELED`로 다루어도 무방하다."
- 문서: enum이 닫힌(closed) 집합이 아니라 열린(open) 집합이라는 점을 OpenAPI 설명에 명시한다.

### Nullable 필드와 의미 변경

기존에 항상 채워주던 `discountAmount`를 어느 시점부터 null이 올 수 있게 바꾸면, 옛날 클라이언트는 `null.intValue()`에서 NPE가 난다. **"항상 있는 필드"를 nullable로 만드는 것은 사실상 breaking change**다.

해결: 새 의미는 새 필드(`discountDetail`)로 추가하고, 기존 `discountAmount`는 가능한 한 의미를 유지한다.

## Bad vs Improved 예제

### 사례 — 결제 응답 스키마 변경

#### Bad: 그냥 갈아엎기

```http
GET /v1/orders/ORD-2026-0001

// before
{
  "orderId": "ORD-2026-0001",
  "amount": 18900,
  "status": "PAID"
}

// after — 한 번에 변경
{
  "orderId": "ORD-2026-0001",
  "payment": {                  // amount, status가 사라지고
    "totalAmount": 18900,       // 안으로 들어가버림
    "state": "PAID"
  }
}
```

옛날 앱은 `amount`/`status`를 그대로 읽으니 주문 상세 화면이 빈 값으로 뜬다. 문제의 본질은 "필드 위치를 옮긴 것"이 아니라 **기존 필드를 제거한 것**이다.

#### Improved: 점진적 마이그레이션

```http
// 1단계 — additive
{
  "orderId": "ORD-2026-0001",
  "amount": 18900,              // 유지
  "status": "PAID",             // 유지
  "payment": {                  // 신규, 동일 정보 미러링
    "totalAmount": 18900,
    "state": "PAID"
  }
}
```

이 상태로 6개월 \~ 1년 운영하면서 신규 클라이언트는 `payment`를 읽도록 옮긴다. 사용 메트릭으로 옛 필드 호출이 충분히 줄었다는 근거가 모이면, 그때 deprecation 절차를 시작한다.

### 사례 — enum 확장

#### Bad

```http
GET /v1/orders/ORD-2026-0001
{ "status": "REFUND_PENDING" }   // 신규 enum, 기존 앱은 디코딩 실패
```

#### Improved — 헤더 기반 분기

```http
GET /v1/orders/ORD-2026-0001
X-API-Version: 2026-04-01

{ "status": "REFUND_PENDING", "legacyStatus": "CANCELED" }
```

```http
GET /v1/orders/ORD-2026-0001
// 헤더 없음 → 과거 동작
{ "status": "CANCELED" }
```

옛 클라이언트에는 안전한 의미로 매핑한 값을 주고, 새 클라이언트에는 정확한 상태를 준다. 요점은 **서버가 클라이언트 능력에 맞춰 응답을 줄인다**는 것이다.

## API Gateway에서의 호환성 운용

게이트웨이(예: Spring Cloud Gateway, Kong, AWS API Gateway)는 버저닝의 1차 방어선이다. 게이트웨이가 다음을 책임지면 백엔드 코드가 단순해진다.

- URI prefix → 내부 서비스로 라우팅 (`/v1/orders` → orders-service v1.x, `/v2/orders` → orders-service v2.x)
- 필수 헤더 검증 (`X-Client-Version`, `X-Platform`)
- 클라이언트 버전이 너무 낮으면 426 Upgrade Required 반환
- 응답에 `Deprecation`, `Sunset` 헤더 부착 (RFC 8594/9745)
- 호출량을 클라이언트 버전별로 라벨링해 관측

여기서 중요한 운영 디테일은 **버전별 트래픽을 측정 가능하게 만들어 두는 것**이다. 측정이 없으면 폐기 결정을 감으로 하게 된다.

## Deprecation과 Sunset — 폐기 절차

지속 가능한 정책은 다음 정도면 충분하다.

1. **공지 **(T+0) — 새 버전을 배포하면서 옛 응답에 `Deprecation: true`, `Sunset: Wed, 31 Dec 2026 23:59:59 GMT`, `Link: </docs/migration-v2>; rel="deprecation"` 헤더를 부착한다.
2. **계측 **(T+0 \~ T+90일) — 옛 엔드포인트/필드 호출을 클라이언트 버전·플랫폼·매장 단위로 집계한다.
3. **권고 업데이트 **(T+90일 전후) — 모바일 앱이 자연 업데이트로 충분히 옮겨갔는지 확인한다. 보통 80\~90%가 임계값.
4. **강제 업그레이드 **(T+180일 전후) — 너무 오래된 클라이언트에는 426을 반환하고, 앱은 업데이트 화면으로 유도한다.
5. **삭제 **(T+365일 전후) — 호출량이 무시할 수준일 때만 실제 코드를 제거한다.

요점은 "절차를 미리 합의해 두는 것"이지, 정확한 일자 자체가 아니다. 이 5단계를 자기 언어로 정리해 두면 폐기 결정을 감으로 하지 않게 된다.

## Consumer-Driven Contract — 회귀를 코드로 잡기

문서와 리뷰만으로는 호환성이 깨지지 않는다는 것을 보장하기 어렵다. **consumer-driven contract test **(CDC)가 이 자리를 메운다.

핵심 아이디어:

- 클라이언트(consumer, 예: 모바일 앱 모듈)가 "나는 이런 응답을 기대한다"는 계약(contract)을 JSON으로 publish한다.
- 백엔드(provider, 예: orders-service)는 빌드 파이프라인에서 그 계약들을 받아서, 자기 응답이 모든 계약을 만족하는지 검증한다.
- 계약을 깨는 변경은 PR 단계에서 빨갛게 표시된다.

대표 도구: Pact. JVM 백엔드는 `pact-jvm-provider`로 검증하고, 모바일은 각 플랫폼 SDK로 계약을 등록한다. 사내에 Pact Broker를 띄우면 contract 버전을 관리할 수 있다.

한 줄 요약: "OpenAPI 스키마 비교만으로는 unknown enum 처리, nullable 의미, 헤더 기반 분기 같은 동작 계약을 잡지 못한다. 모바일 채널 핵심 API에는 Pact 기반 CDC를 두고 백엔드 빌드에서 검증한다."

## 롤백 안전망

버저닝과 짝이 되는 안전장치는 **즉시 되돌릴 수 있는 배포**다.

- 게이트웨이의 라우팅 룰을 한 줄 토글로 v1 ↔ v2 사이를 옮길 수 있게 둔다.
- DB 마이그레이션은 expand → migrate → contract 3단계로 끊는다. 컬럼 삭제·rename은 contract 단계에서만 한다. v2 응답을 만든다고 컬럼을 즉시 rename하면 v1을 다시 띄울 수 없다.
- 응답 스키마 변경과 데이터 모델 변경을 같은 배포에 묶지 않는다.
- 카나리/링 배포로 일부 트래픽에만 v2를 노출하고, 에러율·p95 응답시간·앱 크래시율을 같이 본다.

## 로컬 실습 환경

호환성 시나리오는 머릿속으로만 돌리면 감이 잘 잡히지 않는다. 작은 환경을 만들어 직접 깨뜨려 보는 게 가장 빠르다.

권장 스택:
- Spring Boot 3.x + Java 21 + Maven 또는 Gradle
- Springdoc OpenAPI로 스키마 자동 생성
- Pact JVM (provider 측)
- Docker로 게이트웨이 한 대(예: Kong 또는 Spring Cloud Gateway 단독)

## 실행 가능한 예제

### 헤더 기반 응답 분기

```java
@RestController
@RequestMapping("/v1/orders")
public class OrderController {

  @GetMapping("/{id}")
  public OrderResponse get(
      @PathVariable String id,
      @RequestHeader(value = "X-API-Version", required = false) String apiVersion) {

    Order order = orderService.findById(id);
    boolean isNew = ApiVersion.isAtLeast(apiVersion, "2026-04-01");

    return OrderResponse.builder()
        .orderId(order.getId())
        .amount(order.getAmount())
        .status(isNew ? order.getStatus().name() : LegacyStatus.map(order.getStatus()))
        .legacyStatus(isNew ? LegacyStatus.map(order.getStatus()) : null)
        .build();
  }
}
```

`ApiVersion.isAtLeast`는 `null`을 가장 보수적인 과거 버전으로 해석한다. 이 한 줄짜리 규칙이 "모르면 옛 동작"이라는 정책을 코드로 표현한다.

### Deprecation 헤더 자동 부착

```java
@Component
public class DeprecationFilter extends OncePerRequestFilter {

  @Override
  protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
      throws ServletException, IOException {
    chain.doFilter(req, res);
    if (req.getRequestURI().startsWith("/v1/orders/legacy-summary")) {
      res.setHeader("Deprecation", "true");
      res.setHeader("Sunset", "Wed, 31 Dec 2026 23:59:59 GMT");
      res.setHeader("Link", "</v2/orders/summary>; rel=\"successor-version\"");
    }
  }
}
```

### Pact provider 검증 스켈레톤

```java
@Provider("orders-service")
@PactBroker(host = "pact-broker.internal", port = "9292")
class OrderProviderContractTest {

  @TestTemplate
  @ExtendWith(PactVerificationInvocationContextProvider.class)
  void verify(PactVerificationContext ctx) {
    ctx.verifyInteraction();
  }

  @State("주문 ORD-2026-0001 이 PAID 상태로 존재한다")
  void seedPaidOrder() {
    orderRepository.save(Order.paid("ORD-2026-0001", 18900));
  }
}
```

### Unknown enum tolerant 디코딩 (Jackson)

```java
@JsonCreator
public static OrderStatus from(@JsonProperty("status") String raw) {
  try {
    return OrderStatus.valueOf(raw);
  } catch (IllegalArgumentException e) {
    return OrderStatus.UNKNOWN;
  }
}
```

서버 사이에서도, 외부 파트너 응답을 수신할 때 같은 패턴이 필요하다. 백엔드 자신이 클라이언트가 되는 순간이 있기 때문이다.

### 호환성 회귀를 막는 단위 테스트

```java
@Test
void v1_response_must_keep_amount_and_status_fields() {
  String body = mvc.perform(get("/v1/orders/ORD-2026-0001"))
      .andReturn().getResponse().getContentAsString();

  DocumentContext json = JsonPath.parse(body);
  assertThat(json.read("$.amount", Integer.class)).isNotNull();
  assertThat(json.read("$.status", String.class)).isNotNull();
}
```

이 테스트는 누군가가 v1 응답에서 `amount`/`status`를 제거하려고 할 때 빌드를 빨갛게 만든다. 호환성 보호의 가장 싼 방어선이다.

## 자주 나오는 잘못된 패턴

- **마이너 버전을 URI에 박는다.** `/v1.1/orders`, `/v1.2/orders`가 늘어나면 라우팅이 폭발한다. 마이너는 헤더로 받는 편이 운영이 단순하다.
- **버전을 올리면서 인증 헤더 이름도 같이 바꾼다.** 두 개의 breaking change를 한 배포에 묶지 않는다. 사고 원인 추적이 어려워진다.
- **OpenAPI 문서만 고치고 실제 응답을 안 본다.** 문서와 응답이 어긋나면 클라이언트는 문서 기준으로 코드를 짜고, 운영에서 깨진다. CDC나 schema diff CI를 둔다.
- **"앱 5%만 옛 버전이니 그냥 끊자"고 결정한다.** 5%가 결제 직전 사용자라면 매출 사고다. 클라이언트 버전·플랫폼·기능별 분포를 본다.
- **Sunset 일자만 적고 강제 업그레이드 절차가 없다.** 일자는 약속이고, 426을 던지는 게이트웨이 룰은 강제력이다. 둘이 같이 있어야 폐기가 끝난다.
- **데이터 모델 변경을 응답 스키마 변경과 같은 배포에 넣는다.** 롤백할 때 DB가 발목을 잡는다. expand/contract로 분리한다.

## 핵심 설계 줄기

전체 전략은 다음 여섯 줄기로 압축된다.

- **현실 인식**: 모바일 앱은 강제 업데이트가 어렵기 때문에 옛 클라이언트가 장기간 살아 있다는 가정으로 시작한다.
- **호환성 룰**: 필드 제거·타입 변경·enum 의미 재정의는 breaking으로 간주하고, 추가·optional·새 enum은 additive로 다룬다. 단, additive도 클라이언트가 tolerant reader여야 안전하다.
- **버저닝 전략**: 메이저는 URI에 박고, 미세한 의미 변화는 `X-API-Version` 같은 날짜 헤더로 처리한다. 헤더가 없으면 가장 보수적인 과거 동작으로 폴백한다.
- **운영 절차**: Deprecation·Sunset 헤더로 공지하고, 클라이언트 버전별 호출량을 측정한 뒤 단계적으로 426을 던진다. 임계값과 일자는 문서로 정의해 둔다.
- **회귀 방지**: OpenAPI 스키마 diff를 CI에 두고, 핵심 API는 Pact 기반 CDC로 모바일팀과 계약을 코드로 묶는다.
- **롤백**: 응답 스키마 변경과 DB 마이그레이션을 분리하고, 게이트웨이 라우팅 토글과 expand/contract 마이그레이션으로 즉시 되돌릴 수 있게 둔다.

문제가 더 좁게 들어오면 그 한 줄기만 깊게 파고든다. 예: "Deprecation 절차를 어떻게 합의하는가"는 5단계(공지·계측·권고·강제·삭제)와 임계값(80\~90% 자연 업데이트)으로 풀어낸다.

## 체크리스트

- [ ] 이번 변경이 breaking인지 additive인지 분류했는가
- [ ] additive라면 클라이언트가 unknown 필드·enum을 안전히 처리하는지 확인했는가
- [ ] 응답에서 필드를 제거하지 않고, 신규 필드를 미러링으로 추가했는가
- [ ] 신규 request 필드를 optional로 두고 기본값을 정의했는가
- [ ] enum 추가 시 옛 클라이언트용 fallback 의미를 명세에 적었는가
- [ ] 메이저 버전은 URI, 마이너는 헤더로 분기하고 있는가
- [ ] 헤더 누락 시 과거 동작으로 폴백하는 정책이 코드로 표현되어 있는가
- [ ] Deprecation·Sunset·Link 헤더가 부착되는가
- [ ] 클라이언트 버전·플랫폼별 호출량을 측정하고 있는가
- [ ] 강제 업그레이드(426) 임계값과 일자가 합의되어 있는가
- [ ] OpenAPI 스키마 diff가 CI에서 깨지면 빌드가 빨개지는가
- [ ] 핵심 API에 Pact 기반 CDC가 있는가
- [ ] 응답 스키마 변경과 DB 마이그레이션을 같은 배포에 묶지 않았는가
- [ ] 게이트웨이 라우팅 토글로 v1↔v2를 즉시 되돌릴 수 있는가
- [ ] DB 마이그레이션이 expand → migrate → contract로 끊어져 있는가
- [ ] 카나리 배포 중 앱 크래시율을 같이 보고 있는가
