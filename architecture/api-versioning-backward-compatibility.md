# [초안] API Versioning과 Backward Compatibility: 시니어 백엔드 관점 정리

## 왜 이 주제가 중요한가

API는 한 번 외부에 공개되는 순간부터 "내가 마음대로 못 바꾸는 코드"가 된다. 내부 라이브러리라면 콜러를 한꺼번에 리팩터링하면 되지만, 모바일 앱·파트너사·외부 통합처럼 **내가 배포 시점을 통제할 수 없는 컨슈머**가 한 명이라도 있으면 이야기가 달라진다. 사용자는 앱 스토어 업데이트를 미루고, 파트너사는 분기 단위로 릴리즈를 묶고, B2B 고객은 1년 전 클라이언트를 그대로 쓰고 있다.

시니어 백엔드 인터뷰에서 API versioning이 자주 나오는 이유는 단순히 "URL에 v1을 붙이느냐 헤더에 붙이느냐"를 묻기 위함이 아니다. 면접관은 다음을 본다.

- API를 **계약(contract)** 으로 다루고 있는가
- breaking change와 non-breaking change를 구분할 수 있는가
- 새 버전을 도입할 때 **이전 버전을 어떻게 살려두고 어떻게 죽일지**까지 설계하는가
- 모바일/외부 컨슈머처럼 **업그레이드를 강제할 수 없는 환경**을 고려하는가
- 비즈니스 영향(매출, SLA, 고객 신뢰)과 기술 부채를 균형 있게 판단하는가

코드 한 줄을 잘못 바꾸면 수십만 대의 휴대폰에서 결제가 막히는 영역이다. 그래서 versioning은 인프라보다 먼저 합의되어야 하는 제품 계약 영역에 가깝다.

## 핵심 개념: Compatibility의 두 방향

먼저 backward / forward compatibility의 정의를 정확히 잡고 가자. 면접에서 헷갈려서 거꾸로 말하면 신뢰가 한 번에 깎인다.

- **Backward compatibility**: 새 버전 서버가 **이전 버전 클라이언트** 요청을 깨뜨리지 않고 처리한다. 서버를 올려도 옛날 앱이 그대로 동작한다.
- **Forward compatibility**: 옛 버전 서버 또는 옛 클라이언트가 **새 버전이 추가한 필드/응답**을 만나도 깨지지 않는다. 보통 클라이언트가 모르는 필드는 무시하도록 만들어 둔다.

실제 운영에서 더 자주 다루는 건 backward compatibility다. 서버는 우리가 배포 권한을 갖지만 클라이언트는 그렇지 않기 때문이다. 모바일 앱이 있는 서비스라면 "지금 배포하는 서버 코드가 6개월 전에 깔린 앱에서 도는가"를 항상 자문해야 한다.

### Breaking change의 분류

다음은 breaking change로 분류해야 안전하다.

- 기존 필드의 **삭제**, **이름 변경**, **타입 변경**(예: string → number)
- 응답 필드의 **의미 변경**(예: `status` 값으로 새 enum 추가는 클라이언트가 default 처리 안 하면 깨질 수 있음)
- 기존에 nullable이던 필드를 **non-null로 강제**, 또는 그 반대
- 필수 요청 파라미터 추가
- 인증/인가 정책 강화(예: 기존 익명 가능 → 로그인 필수)
- HTTP 상태코드 변경(200 → 202)
- 페이지네이션 방식 교체(offset → cursor)
- 에러 응답 포맷 변경
- 동기 응답을 비동기 큐 응답으로 변경

다음은 보통 non-breaking으로 본다. 단, **클라이언트가 unknown field를 무시한다는 전제** 하에서다.

- 응답에 **새 optional 필드** 추가
- 새 endpoint 추가
- 기존 enum 값을 그대로 두고 새 값을 추가 — 단, 클라이언트의 default 처리가 보장될 때만 안전
- 기존 필드의 **rate limit 완화**

요약하면 "기존 콜이 같은 결과를 받는가"가 기준이고, enum 추가처럼 표면상 안전해 보이는 변경도 클라이언트 구현에 따라 깨질 수 있다는 점은 면접에서 짚고 넘어가면 좋다.

## Versioning 전략 비교

면접에서 "어떤 버저닝 방식을 선호하느냐"는 흔한 질문이다. 정답은 없고 trade-off를 설명할 수 있는지가 핵심이다.

### 1. URI versioning (`/v1/orders`)

가장 흔하고 가장 직관적이다. 라우팅·로그·캐시·gateway 룰을 버전별로 그대로 쪼갤 수 있어 운영이 단순하다. 단점은 REST 원칙상 "같은 리소스에 다른 URI"가 생긴다는 점, 그리고 마이너 변경에도 v2를 찍으면 버전 인플레이션이 생긴다는 점이다. 실무에서는 가장 무난한 default다.

### 2. Header versioning (`Accept: application/vnd.company.v2+json`)

URI는 깨끗해지지만 디버깅이 어렵다. curl로 한 번 칠 때마다 헤더를 신경 써야 하고, CDN/프록시/게이트웨이의 캐시 키 설정이 까다로워진다. 외부 파트너 대상이라면 "헤더로 버전 지정해 주세요"라는 가이드가 잘 안 지켜진다. 내부 마이크로서비스 간 통신에는 괜찮다.

### 3. Query parameter versioning (`?version=2`)

캐싱 측면에서 URI 방식과 비슷하지만 "기본값 없는 호출"이 들어왔을 때 어떻게 처리할지가 모호해진다. 보통 권장하지 않는다.

### 4. Versionless / Evolutionary API

aggressive하게는 "버전을 안 만들고 항상 backward compatible하게만 진화시킨다"는 전략도 있다. Stripe가 자주 인용된다. Stripe는 사실 정확히는 **계정별 API version pinning** + **request 헤더 override**를 결합해서, 신규 가입자는 최신 버전, 기존 가입자는 가입 시점 버전에 묶이는 방식이다. 서버는 내부적으로 모든 과거 버전 호환 어댑터를 가진다.

이 모델은 우아하지만 비싸다. 어댑터/매퍼 레이어가 점점 두꺼워지고, 새로 들어오는 엔지니어가 "이 필드가 왜 이런 모양인지"를 알기 위해 versioning history를 읽어야 한다. 결제처럼 외부 통합이 핵심인 도메인이 아니면 과한 선택일 수 있다.

### 인터뷰용 결론

내부 마이크로서비스나 단일 클라이언트라면 versionless로도 충분히 진화시킬 수 있다. 하지만 외부 파트너 또는 모바일 앱이 컨슈머라면 **URI versioning + 명시적 deprecation 정책 + 호환 어댑터 일부 도입**의 조합이 가장 운영하기 좋다. 정답을 한 줄로 외우기보다 컨슈머 통제 가능성과 도메인 안정성으로 나눠서 답하면 된다.

## 실전 백엔드 적용

### Spring Boot에서 URI versioning

가장 단순한 형태는 컨트롤러 수준에서 분리하는 것이다.

```java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderControllerV1 {
    @GetMapping("/{id}")
    public OrderResponseV1 get(@PathVariable Long id) {
        Order order = orderService.findById(id);
        return OrderResponseV1.from(order);
    }
}

@RestController
@RequestMapping("/api/v2/orders")
public class OrderControllerV2 {
    @GetMapping("/{id}")
    public OrderResponseV2 get(@PathVariable Long id) {
        Order order = orderService.findById(id);
        return OrderResponseV2.from(order);
    }
}
```

핵심은 **도메인 모델은 하나로 유지하고 응답 DTO만 버전별로 분리**한다는 점이다. 도메인까지 버전을 만들기 시작하면 비즈니스 로직이 두 갈래로 갈라져서 유지보수가 무너진다.

요청 쪽도 마찬가지다. v2에서 새 필드가 들어오면 v1 매퍼는 그 필드를 default로 채우고, 도메인 서비스 입장에서는 "v1 호출인지 v2 호출인지" 자체를 모르도록 만든다.

### Header versioning이 필요할 때

같은 URI를 유지하면서 컨텐츠 협상으로 버전을 분리하고 싶다면 Spring에서는 `produces`로 처리할 수 있다.

```java
@GetMapping(value = "/api/orders/{id}",
            produces = "application/vnd.company.order.v2+json")
public OrderResponseV2 getV2(@PathVariable Long id) { ... }
```

게이트웨이/캐시가 `Accept` 헤더를 cache key에 포함하도록 설정하지 않으면 캐시 hit이 깨질 수 있다. 이 점은 면접에서 짚으면 인프라 감각이 있다고 보인다.

### 응답 진화 — 잘못된 예 vs 개선된 예

#### 나쁜 예: 필드 의미를 조용히 바꿈

```jsonc
// v1 (출시 시점)
{ "status": "PAID" }   // 가능한 값: PAID, FAILED, PENDING

// 어느 날 결제 보류 상태가 추가됨
{ "status": "ON_HOLD" } // 클라이언트가 모르는 값 → switch default에서 NPE 또는 UI 깨짐
```

여기서 가장 흔한 사고 패턴은 "enum 한 줄 추가했을 뿐"이라며 backward compatible로 분류하는 것이다. 새 enum 값은 항상 클라이언트 입장에서 깨질 수 있는 변경으로 봐야 한다.

#### 개선된 예: 필드 추가 + 옛 의미 보존

```jsonc
// v1 호출에는 PAID/FAILED/PENDING 외 값을 절대 보내지 않음
{ "status": "PENDING", "statusReason": "ON_HOLD" }

// v2부터는 status에 ON_HOLD를 직접 보낼 수 있다고 명시
```

옛 클라이언트는 ON_HOLD 상태일 때 "처리 중"으로 표시되어 다소 부정확하지만, 적어도 화면이 깨지지 않는다. v2 클라이언트만 정확한 상태를 본다. 이런 식으로 "정확성을 약간 희생하고 안전성을 확보"하는 패턴은 외부 API에서 자주 쓴다.

#### 나쁜 예: 페이지네이션 응답 구조 변경

```jsonc
// 기존
{ "items": [...], "total": 1234 }

// 변경
{ "data": { "items": [...], "page": { "size": 20, "next": "abc" } } }
```

이건 명백한 breaking change다. v2 endpoint를 새로 파거나 응답에 두 형식을 동시 포함시키는 transition window가 필요하다.

#### 개선된 예: 새 필드 병행 노출

```jsonc
{
  "items": [...],
  "total": 1234,
  "pageInfo": { "size": 20, "next": "abc" }   // 신규 필드, 옛 클라이언트는 무시
}
```

이후 cursor 기반으로 완전히 옮기고 싶다면 별도 endpoint(`/v2/orders`)를 따고 옛 endpoint는 deprecation 절차로 들어간다.

## Deprecation을 설계로 다루기

가장 자주 빠지는 함정이 "v2 만들었으니 v1은 곧 내릴게요"라고만 말하고 절차를 안 만드는 것이다. 시니어 답변은 "어떻게 알리고, 누가 얼마나 쓰는지 측정하고, 어떻게 죽이는지"까지 가야 한다.

### 알리는 단계

- `Deprecation`, `Sunset` HTTP 헤더로 응답에 명시(RFC 8594, RFC 9745). 예:
  ```
  Deprecation: true
  Sunset: Wed, 31 Dec 2026 23:59:59 GMT
  Link: </api/v2/orders>; rel="successor-version"
  ```
- 문서/체인지로그/이메일 공지
- 파트너 대상이라면 deprecated endpoint 호출 발생 시 별도 알림

### 측정하는 단계

- v1 endpoint별 호출량, 호출하는 client_id 또는 API key별 분포 수집
- 모바일이라면 app version별 분포(보통 분석 이벤트로 같이 수집)
- "이번 주 v1 호출 0건, 30일 연속 0건" 같은 retire 조건을 미리 정의

### 강제하는 단계

- 단순 차단 전에 **brownout**: 매주 특정 시간 1~2시간 동안 v1을 503으로 응답시켜 잔존 호출자를 찾아내게 한다
- 잔존 호출자에게 직접 컨택
- 실제 cutoff 날짜에 410 Gone 응답으로 종료

이 흐름을 한 번 답하면 운영 경험이 있다는 신호가 강하게 전달된다.

## 모바일 앱 특수성

웹 클라이언트와 달리 모바일은 다음이 어렵다.

- 즉시 업데이트 강제가 사실상 불가능 (스토어 정책, 사용자 거부)
- 옛 OS 단말은 새 앱 자체를 못 받는 경우 있음
- 일부 사용자는 1~2년 전 앱을 그대로 사용

대응 패턴은 다음과 같다.

- **클라이언트가 보내는 X-App-Version 헤더**를 신뢰하고, 일정 버전 이하에서는 v1 응답 매퍼를 강제로 태우는 라우팅
- **soft force update**: 메인 화면 진입 시 서버가 "이 버전 이상으로 업데이트 권장/필수" 플래그 내려주기. 결제처럼 위험한 화면 진입 시에는 hard block
- **kill switch**: 특정 기능 endpoint에 대해 서버에서 비활성화 플래그를 내려, 옛 앱이 이미 위험한 호출을 보내지 않도록 차단
- **의도적 응답 단순화**: 옛 앱 버전에는 새 기능 노출에 필요한 필드를 아예 안 내려서 UI가 새 기능 진입 자체를 못 하게 함

모바일 컨슈머가 있는 도메인 면접이라면 "X-App-Version 라우팅"을 적어도 한 번은 언급하는 게 좋다.

## Schema Evolution 측면 (JSON, gRPC, Avro 비교)

면접에서 "JSON 말고 다른 직렬화도 다뤄봤느냐"가 따라오기 쉽다.

- **JSON**: 가장 관대하다. 알 수 없는 필드 무시 + 새 optional 필드 추가가 사실상 무료. 단, 강한 타입 보장이 없으니 클라이언트 구현 품질에 좌우된다.
- **Protobuf / gRPC**: 필드 번호를 키로 쓰기 때문에 "필드 번호를 재사용하지 않는다"만 지키면 add는 안전하다. 필드 삭제는 reserved로 박아 두는 게 정석. required는 사실상 쓰지 않는 게 권장이다.
- **Avro**: 스키마 레지스트리와 함께 쓰며, reader/writer 스키마 호환성 규칙(forward/backward/full)을 명시적으로 검사한다. Kafka 기반 이벤트 파이프라인에서 자주 쓴다.

핵심 원칙은 같다. **필드 추가는 안전하게, 삭제와 의미 변경은 새 버전으로**.

## 로컬 실습 환경

다음 스택이면 실습이 충분하다.

- JDK 17+, Spring Boot 3.x
- Docker (선택, MySQL/Redis 띄울 때만)
- HTTPie 또는 curl

`build.gradle` 핵심 의존성:

```gradle
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
```

## 실행 가능한 예제

다음은 v1과 v2를 동시에 노출하고, v1은 deprecated 헤더를 자동으로 붙이는 최소 구성이다.

```java
// OrderResponseV1.java
public record OrderResponseV1(Long id, String status, long amount) {
    public static OrderResponseV1 from(Order o) {
        // ON_HOLD를 PENDING으로 매핑 (v1 클라이언트 보호)
        String mapped = switch (o.getStatus()) {
            case ON_HOLD -> "PENDING";
            default -> o.getStatus().name();
        };
        return new OrderResponseV1(o.getId(), mapped, o.getAmount());
    }
}

// OrderResponseV2.java
public record OrderResponseV2(Long id, String status, String statusReason, long amount, String currency) {
    public static OrderResponseV2 from(Order o) {
        return new OrderResponseV2(
            o.getId(),
            o.getStatus().name(),
            o.getStatusReason(),
            o.getAmount(),
            o.getCurrency()
        );
    }
}
```

```java
// OrderController.java
@RestController
public class OrderController {
    private final OrderService service;

    public OrderController(OrderService service) { this.service = service; }

    @GetMapping("/api/v1/orders/{id}")
    public ResponseEntity<OrderResponseV1> v1(@PathVariable Long id) {
        Order o = service.findById(id);
        return ResponseEntity.ok()
            .header("Deprecation", "true")
            .header("Sunset", "Wed, 31 Dec 2026 23:59:59 GMT")
            .header("Link", "</api/v2/orders/" + id + ">; rel=\"successor-version\"")
            .body(OrderResponseV1.from(o));
    }

    @GetMapping("/api/v2/orders/{id}")
    public OrderResponseV2 v2(@PathVariable Long id) {
        return OrderResponseV2.from(service.findById(id));
    }
}
```

호출:

```
http :8080/api/v1/orders/1
http :8080/api/v2/orders/1
```

v1 응답 헤더에서 `Deprecation`, `Sunset`이 떨어지는지 확인한다. 이걸 그대로 운영 환경에 붙이고, deprecation 헤더가 나가는 호출량을 메트릭으로 모으면 retire 의사결정의 근거가 생긴다.

응용 실습으로 다음을 권장한다.

1. v1 응답에 새 optional 필드를 추가해 본다. v1 통합 테스트(JSON 비교)가 어떻게 깨지고 어떻게 통과시킬지 직접 경험한다.
2. enum에 새 값을 추가하고 v1 매퍼만으로 안전하게 막아 본다.
3. `X-App-Version` 헤더를 받아 특정 버전 이하면 강제로 v1 응답으로 라우팅하는 인터셉터를 만든다.

## 흔히 깨지는 패턴 모음

- "필드 하나 빼는 건 별일 아니지" — 클라이언트가 NPE로 화면 전체가 죽는다.
- "새 enum 값은 추가만 하니까 안전" — switch default가 throw인 클라이언트가 깨진다.
- 응답 JSON에서 0/null 표현을 임의로 바꾼다 (`null` → `0`, `[]` → `null`). 통계 클라이언트가 잘못된 값을 보고한다.
- 페이지네이션 default size 변경. UX와 성능이 동시에 깨진다.
- 인증 정책을 조용히 강화. 백오피스가 아닌 외부 통합이라면 거의 항상 사고로 이어진다.
- v2 만들고 v1을 한 달 만에 내림. 외부 컨슈머는 분기/반기 단위로 움직인다는 점을 무시한 사례다.

## 인터뷰 답변 프레이밍

질문이 "API 버저닝 어떻게 하셨어요" 류로 들어오면 다음 4단으로 답하는 걸 권한다.

1. **컨슈머 분류부터 한다**: 내부 서비스만이면 versionless로 evolutionary하게, 외부/모바일이 끼면 명시적 URI 버저닝이 안전하다는 식.
2. **Breaking 기준을 정의한다**: 필드 삭제/타입 변경/의미 변경/필수 파라미터 추가 등을 breaking으로 본다고 명시.
3. **Deprecation 절차를 설명한다**: Deprecation/Sunset 헤더, 호출량 측정, brownout, 최종 410.
4. **모바일 특수성을 언급한다**: X-App-Version 기반 라우팅, kill switch, soft/hard force update.

가능하면 본인이 실제 겪었던 작은 사고를 곁들이는 게 가장 효과적이다. "필드 의미 변경을 non-breaking으로 잘못 분류해서 옛 앱에서 결제 화면이 깨진 적이 있고, 이후 우리 팀은 의미 변경은 무조건 새 버전 또는 새 필드로 분리하는 룰을 잡았다" 같은 식. 정답이 아니라 학습이 보여야 한다.

추가로 자주 따라붙는 후속 질문도 미리 준비해 두면 좋다.

- "v1을 어떻게 결국 내리셨어요?" → 측정 → brownout → 잔존 컨슈머 컨택 → 410.
- "Stripe식 versionless는 안 고려하셨어요?" → 어댑터 부담과 새 합류자의 인지 비용 trade-off로 답한다.
- "DB 스키마는 어떻게 같이 진화시켰어요?" → expand-and-contract 패턴(컬럼 추가 → 양쪽 쓰기 → 옛 컬럼 제거)으로 답하면 자연스럽게 연결된다.

## 체크리스트

- [ ] 변경이 backward compatible인지 위 분류표로 판단했는가
- [ ] 새 enum 값/필드 의미 변경은 새 버전이나 새 필드로 분리했는가
- [ ] v1과 v2가 같은 도메인 모델을 공유하고 있는가 (DTO만 분리)
- [ ] deprecation 발표 시점과 sunset 날짜가 정해졌는가
- [ ] Deprecation/Sunset/Link 헤더가 응답에 실리는가
- [ ] v1 호출량 메트릭이 client_id, app_version 단위로 수집되는가
- [ ] 모바일 컨슈머가 있다면 X-App-Version 기반 라우팅 또는 soft force update가 준비됐는가
- [ ] retire 직전 brownout 일정을 잡았는가
- [ ] 외부 파트너에 deprecation/sunset이 별도 채널로도 통보되었는가
- [ ] 인터뷰 시 답변 4단(컨슈머 분류 → breaking 기준 → deprecation 절차 → 모바일 특수성)을 한 호흡에 말할 수 있는가
