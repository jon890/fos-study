# 응답을 모두 200으로 래핑하는 환경에서 Prometheus 비즈니스 errorCode 메트릭 만들기

**진행 기간**: 2026.04 ~ 2026.05

운영 중인 API 서버에서 "어떤 비즈니스 에러가 얼마나 발생하고 있는지"를 Grafana에서 보고 싶었다. Spring Boot Actuator + Micrometer 조합이면 보통 `http_server_requests_seconds_count{status="4xx"}` 같은 표준 메트릭으로 충분한데, 이 서버는 그게 안 됐다. 모든 응답을 HTTP 200으로 통일하고 비즈니스 에러는 응답 body 안의 코드로 표현하는 **공통 응답 포맷**(response envelope)을 쓰고 있어서, status 라벨이 전부 200으로만 찍혔기 때문이다.

이걸 해결하기 위해 `@RestControllerAdvice`에 직접 Counter를 박아 비즈니스 errorCode 단위 메트릭을 만들었고, PromQL을 두 번 갈아탔다. 이번 글은 그 과정의 How-to + 의사결정 흐름이다.

## 왜 표준 메트릭이 무력화됐나

응답 정책이 다음과 같다.

```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "header": {
    "isSuccessful": false,
    "resultCode": 4010001,
    "resultMessage": "Invalid appKey or secretKey."
  }
}
```

콘솔(관리자) URI를 제외하고는 **무조건 200**이고, 비즈니스 에러는 body의 `resultCode`/`resultMessage`로 표현한다. 이 정책 자체는 클라이언트 단순화·로깅 일관성·게이트웨이 정책 통일 같은 이유로 자리잡아 있어 바꿀 수 없는 전제였다.

부작용은 명확하다. Spring Boot가 자동으로 노출하는 `http_server_requests_seconds_count` 라벨에 `status="200"`만 남으니, "에러 발생 추세" 패널을 만들려고 하면 항상 0이거나 200 카운트만 잡힌다. **HTTP status 기반 알람·대시보드는 전부 무력화되는 환경**이다.

해결 방향은 분명했다. 비즈니스 에러를 직접 Counter로 쌓고, 그 카운터에 의미 있는 라벨을 붙여 Grafana에서 분포·추세를 보는 것.

## 어디서 잡을까: ExceptionController

이 서버는 모든 예외가 `@RestControllerAdvice` 클래스 한 곳(`ExceptionController`)에서 처리된다. Spring 표준 예외, Bean Validation 예외, 비즈니스 예외(`OcrApiException`처럼 `resultCode` 필드가 있는 커스텀 예외) 등 종류별로 `@ExceptionHandler` 메서드가 분리되어 있고, 모두 마지막에 `DomainResponse.create(resultCode)`로 200 래핑된 응답을 만든다.

이 자리가 메트릭을 박기 가장 좋은 지점이다. 모든 비즈니스 에러가 여기를 한 번씩 거치고, 거기서 이미 `ResultCode` enum을 알고 있다.

```java
@Slf4j
@RestControllerAdvice
@RequiredArgsConstructor
public class ExceptionController {

    static final String BUSINESS_ERROR_METRIC_NAME = "ocr.api.business.error";

    private final MeterRegistry meterRegistry;

    @ExceptionHandler(OcrApiException.class)
    public DomainResponse handleException(OcrApiException e, HttpServletRequest request) {
        if (e.getResultCode().isUserError()) {
            log.warn("{} {} {}", e.getResultCode(), request.getMethod(), request.getRequestURL(), e);
        } else {
            log.error("{} {} {}", e.getResultCode(), request.getMethod(), request.getRequestURL(), e);
        }
        recordBusinessError(e.getResultCode(), e);
        return DomainResponse.create(e.getResultCode());
    }

    @ExceptionHandler({BindException.class,
                       MethodArgumentNotValidException.class,
                       HttpMessageNotReadableException.class,
                       ValidationException.class,
                       MultipartException.class})
    public ResponseEntity<DomainResponse> handleInvalidParameterException(Exception e, HttpServletRequest request) {
        var resultCode = ResultCode.BAD_REQUEST;
        log.warn("{} {} {}", resultCode, request.getMethod(), request.getRequestURL(), e);
        recordBusinessError(resultCode, e);
        return createResponseEntity(request.getRequestURI(), resultCode, HttpStatus.BAD_REQUEST);
    }

    // ... NoHandlerFoundException, HttpRequestMethodNotSupportedException 등 동일 패턴
}
```

핵심은 두 가지다. `MeterRegistry`를 생성자로 주입받고, 모든 핸들러가 마지막에 `recordBusinessError(...)`를 호출한다. 핸들러마다 `ResultCode`만 정해놓으면 카운터는 자동으로 일관되게 쌓인다.

## 라벨 설계 — code/name/category/exception

가장 시간을 쓴 부분이다. 라벨을 잘못 박으면 Prometheus 자체가 흔들릴 수 있어서 그렇다.

### 잠깐, "카디널리티"가 뭔가

이 글에서 "카디널리티가 폭발한다"는 표현이 여러 번 나오니 먼저 정리해두는 편이 낫겠다.

Prometheus는 메트릭 이름과 라벨 조합 하나당 **하나의 시계열**(time series)을 만든다. 예를 들어

```
ocr_api_business_error_total{code="4010001", category="4", exception="OcrApiException"}
```

이건 그 자체로 한 시리즈다. `code` 값이 50개로 늘어나면 (다른 라벨이 같다는 가정에서) 50개의 시리즈가 생긴다.

라벨의 **카디널리티**(cardinality)는 그 라벨이 가질 수 있는 서로 다른 값의 개수다. 그리고 한 메트릭의 총 시리즈 수는 **모든 라벨 카디널리티의 곱**으로 결정된다 — 조합마다 시리즈가 별도로 생기기 때문이다.

```
code(50) × category(3) × exception(10) = 최대 1,500 시리즈
```

"카디널리티가 폭발한다"는 건 라벨에 `user-id`, `request-id`, IP, timestamp처럼 **값이 사실상 무한대로 늘어나는 것**을 박았을 때 시리즈 수가 곱셈으로 터지는 상황을 말한다. 시리즈 하나마다 Prometheus가 메모리·인덱스·쿼리 비용을 지불하므로, 한 메트릭이 수십만 시리즈가 되면 OOM이 나거나 쿼리가 타임아웃 난다. 흔히 인용되는 사고 사례 중 상당수가 무심코 추가한 라벨 하나에서 시작한다.

그래서 라벨을 추가할 때는 항상 "이 라벨이 가질 수 있는 값의 상한이 얼마인가"를 곱셈으로 가늠해본 뒤 결정한다. 아래 4개 라벨도 그 가늠을 거쳐서 통과한 것들이다.

### 최종 결정한 라벨 네 개

이번 메트릭은 `code`, `name`, `category`, `exception` 네 개로 박았다. 코드부터 본다.

```java
private void recordBusinessError(ResultCode resultCode, Exception e) {
    Counter.builder(BUSINESS_ERROR_METRIC_NAME)
            .description("Count of business errors by ResultCode (always-200 wrapped responses).")
            .tag("code", String.valueOf(resultCode.getCode()))
            .tag("name", resultCode.name())
            .tag("category", resolveCategory(resultCode))
            .tag("exception", e.getClass().getSimpleName())
            .register(meterRegistry)
            .increment();
}

private static String resolveCategory(ResultCode resultCode) {
    int code = resultCode.getCode();
    if (code < 0) {
        return "system";
    }
    return String.valueOf(code).substring(0, 1);  // 4xxx -> "4", 5xxx -> "5"
}
```

각 라벨의 의도는 이렇다.

- **code**: 비즈니스 에러 식별 숫자(`4010001`, `400`, `415` 등). 가장 세분화된 시리즈
- **name**: `ResultCode` enum의 이름(`INVALID_APPKEY_SECRETKEY`, `BAD_REQUEST`, `UNSUPPORTED_MEDIA_TYPE`). code와 1:1 매핑이라 카디널리티 추가 부담 없음
- **category**: 첫 자리 또는 `system`. "사용자 잘못(4)" vs "시스템 에러(5)"를 한 줄로 가르는 용도
- **exception**: `e.getClass().getSimpleName()`. 같은 `BAD_REQUEST` 코드라도 어떤 예외 타입에서 왔는지 분리해서 보고 싶을 때 유용

### name 라벨은 사실 두 번째 PR에서 추가했다

처음에는 `code` 하나로 충분하다고 봤다. 숫자만 있으면 PromQL 필터링도 되고, Grafana에서도 표시하면 되니까. 그런데 막상 Grafana 패널에 띄워놓고 보니 **`4010001`이 무슨 에러인지 한 번에 안 들어왔다**. 코드 표를 옆에 띄워놓고 비교해야 하는 상황이 반복됐고, 운영 담당자에게 보여줄 때마다 코드 매핑을 설명해야 했다.

해결은 단순했다. `name` 라벨을 같이 넣고, Grafana legend를 `{{code}} {{name}}` 으로 바꿨다. 그러면 한 줄에 `4010001 INVALID_APPKEY_SECRETKEY` 처럼 표시된다.

```
ocr_api_business_error_total{
    category="4",
    code="4010001",
    exception="OcrApiException",
    name="INVALID_APPKEY_SECRETKEY"
} 20.0
```

카디널리티는? `code`와 `name`이 1:1이므로 시리즈 수는 변하지 않는다. **같은 정보를 두 개의 키로 노출**하는 셈이라 비용 부담은 없고, 가독성 이득은 크다.

#### 이 결정이 일반화되는 지점

라벨 추가 비용은 카디널리티에 따라 결정되는데, **기존 라벨과 1:1로 매핑되는 추가 라벨은 시리즈 수가 변하지 않는다**. 그래서 가독성·검색성 이득이 있을 때만 추가 라벨을 붙이는 결정이 합리적이다. 반대로 user-id, request-id, IP 같은 라벨은 카디널리티가 폭발하므로 절대 라벨로 두면 안 된다.

## 단위 테스트 — `SimpleMeterRegistry`로 라벨까지 검증

Counter 코드는 의외로 테스트하기 쉽다. Micrometer가 제공하는 `SimpleMeterRegistry`를 직접 만들어 핸들러에 주입하고, 호출 후 카운터를 조회하면 된다.

```java
class ExceptionControllerMetricTest {

    private SimpleMeterRegistry meterRegistry;
    private ExceptionController controller;

    @BeforeEach
    void setUp() {
        meterRegistry = new SimpleMeterRegistry();
        controller = new ExceptionController(meterRegistry);
    }

    @Test
    @DisplayName("OcrApiException 처리 시 ResultCode 코드/카테고리/예외명 라벨 카운터 증가")
    void recordsCounterForOcrApiException() {
        var request = new MockHttpServletRequest("POST", "/api/v1.0/appkeys/test/general");
        var exception = new OcrApiException(ResultCode.INTERNAL_API_FAIL, "test-app-key");

        controller.handleException(exception, request);

        Counter counter = findCounter(
                "code", String.valueOf(ResultCode.INTERNAL_API_FAIL.getCode()),
                "category", "5",
                "exception", "OcrApiException"
        );
        assertThat(counter).isNotNull();
        assertThat(counter.count()).isEqualTo(1.0);
    }

    private Counter findCounter(String... tagPairs) {
        var search = meterRegistry.find(BUSINESS_ERROR_METRIC_NAME);
        for (int i = 0; i < tagPairs.length; i += 2) {
            search = search.tag(tagPairs[i], tagPairs[i + 1]);
        }
        return search.counter();
    }
}
```

`meterRegistry.find(...).tag(...).tag(...).counter()` 가 **부분 매칭**이라는 점이 좋다. 위 테스트는 `name` 라벨을 검사하지 않지만, 나중에 새 라벨을 추가해도 기존 테스트가 깨지지 않는다. 라벨 하나만 검증하는 좁은 테스트와, 모든 라벨을 검증하는 넓은 테스트를 따로 두면 회귀 안전성과 가독성 둘 다 챙길 수 있다.

신규 라벨을 추가했을 때는 검증 케이스 한 개만 더 붙이면 된다.

```java
@Test
@DisplayName("ResultCode enum 이름이 name 라벨로 함께 기록됨")
void recordsResultCodeNameLabel() {
    var request = new MockHttpServletRequest("POST", "/api/v1.0/appkeys/test/general");
    var exception = new OcrApiException(ResultCode.DUPLICATED_APPKEY, "test-app-key");

    controller.handleException(exception, request);

    Counter counter = findCounter(
            "code", String.valueOf(ResultCode.DUPLICATED_APPKEY.getCode()),
            "name", ResultCode.DUPLICATED_APPKEY.name(),
            "category", "4",
            "exception", "OcrApiException"
    );
    assertThat(counter.count()).isEqualTo(1.0);
}
```

## PromQL을 두 번 갈아탔다

여기가 글의 진짜 본론이다. 같은 메트릭을 띄우는 데 세 가지 PromQL 방식을 다 써봤고, 각 단계에서 "이건 안 되겠다" 싶은 이유가 명확했다.

### 1차: `rate(ocr_api_business_error_total[5m])`

가장 흔한 시작점. 분당 발생률을 시계열로 그리는 패턴이다.

```promql
sum by (code) (rate(ocr_api_business_error_total{cluster="$cluster"}[5m]))
```

배포 직후 패널을 켜고 트래픽을 흘렸는데 **신규 시리즈가 안 보였다**. 분명히 카운터는 올라가고 있는데 패널은 비어 있는 상태가 1~2분 지속됐다.

원인은 알면 단순하다. `rate()`/`increase()`는 윈도우 안에 **최소 2개의 sample**이 있어야 의미 있는 값을 계산한다. scrape 간격이 15초인 환경이라면, 첫 에러 발생 후 두 번째 scrape이 도착할 때까지(15~30초) 시리즈가 표시되지 않는다. 1분에 한 번 발생하는 드문 에러라면 더 길어진다.

데모·검증 단계에서 "방금 발생시켰는데 왜 안 보이지?" 질문이 반복적으로 나왔다.

### 2차: 누적 `sum`

신규 시리즈 보임 문제를 해결하려고 누적 합으로 갔다.

```promql
sum by (code) (ocr_api_business_error_total{cluster="$cluster"})
```

Counter는 **단조 증가**(monotonically increasing)하는 본성이라 이 식은 "전체 누적"을 그대로 보여준다. 첫 sample부터 즉시 값이 표시되고, 신규 시리즈도 즉시 라인에 등장한다.

문제는 다른 데서 터졌다. **에러가 멈춰도 라인이 사라지지 않는다.** Grafana 시간 범위 안의 누적값을 그대로 그리니, 한 번 발생한 코드는 시간 범위가 끝날 때까지 계단식 라인이 남는다. "지금 발생 중인 에러"와 "한참 전에 발생한 잔존 라인"이 시각적으로 구분되지 않았다.

운영 입장에서 **"지금 문제가 있나?"를 한눈에 보기 위한 패널**이 그 본질을 잃은 셈이었다.

### 최종: `increase(...[$__rate_interval])`

윈도우를 다시 쓰되, 신규 시리즈 함정을 알고 윈도우 길이를 조정하는 방향으로 갔다.

```promql
# 시계열 패널 (errorCode, exception types, system errors)
sum by (code, name) (increase(ocr_api_business_error_total{cluster="$cluster"}[$__rate_interval]))

# Instant 계열 패널 (Top-5, Pie chart)
topk(5, sum by (code, name) (increase(ocr_api_business_error_total{cluster="$cluster"}[1h])))
sum by (category) (increase(ocr_api_business_error_total{cluster="$cluster"}[1h]))
```

정리하면:

| 패널 종류 | 윈도우 | 의도 |
|---|---|---|
| 시계열 (시간 흐름) | `$__rate_interval` | refresh 간격에 맞춰 자동 조정. 발생 멈추면 윈도우 끝나는 시점부터 0으로 떨어짐 |
| Instant (현재값) | `[1h]` | "최근 1시간 분포" — 첫 scrape 한 번이면 충분히 잡힘, 신규 시리즈도 거의 즉시 보임 |

`$__rate_interval`은 Grafana가 패널 refresh 간격에 맞춰 자동 계산하는 변수다. refresh 10초 패널이면 자동으로 적절한 윈도우(보통 1분 이상)를 잡아주고, 패널 너비/시간 범위가 바뀌어도 다시 계산한다. 이걸 직접 `[5m]` 같이 고정하면 시간 범위에 따라 곡선이 너무 거칠어지거나 너무 부드러워진다.

신규 시리즈 함정은 시계열 패널에서는 여전히 남아 있지만, 정상 운영 트래픽 수준이라면 1~2분 안에 보인다. 정말 처음 발생한 코드를 즉시 보고 싶을 때는 Top-5 같은 instant 패널에서 `[1h]` 윈도우로 잡힌다.

#### 의사결정 요약

세 단계는 결국 다음 트레이드오프를 따라 움직였다.

| 방식 | 신규 시리즈 노출 | 발생 멈춤 시 라인 사라짐 | 데모 검증 적합도 | 운영 모니터링 적합도 |
|---|---|---|---|---|
| `rate([5m])` | 느림 (≥2 sample 필요) | 자연스러움 | 나쁨 | 나쁨 (느린 노출) |
| 누적 `sum` | 즉시 | 사라지지 않음 | 좋음 | 나쁨 (잔존 라인) |
| `increase([$__rate_interval])` | 시계열은 보통, instant는 빠름 | 자연스러움 | 적당 | 좋음 |

운영 모니터링이 1순위라 최종은 세 번째다. 데모 시나리오에서 "방금 발생시켰는데 안 보임" 문제는 instant 계열 패널을 적극 활용하고, 시계열 패널은 "시간 흐름이 중요한 영역"에만 둠으로써 절충했다.

## Grafana 패널 5종 — PromQL과 legend

최종적으로 만든 대시보드는 다음과 같다.

| # | 패널 | 시각화 | PromQL | legend |
|---|---|---|---|---|
| 1 | errorCode | Time series (stacked) | `sum by (code, name) (increase(ocr_api_business_error_total[$__rate_interval]))` | `{{code}} {{name}}` |
| 2 | User vs System Errors | Pie chart | `sum by (category) (increase(ocr_api_business_error_total[1h]))` | displayName override로 `User Errors` / `System Errors` |
| 3 | Top-5 errorCodes | Bar gauge | `topk(5, sum by (code, name) (increase(ocr_api_business_error_total[1h])))` | `{{code}} {{name}}` |
| 4 | Exception types | Time series (stacked) | `sum by (exception) (increase(ocr_api_business_error_total[$__rate_interval]))` | `{{exception}}` |
| 5 | System errors (category=5) | Time series + threshold | `sum by (code, name) (increase(ocr_api_business_error_total{category="5"}[$__rate_interval]))` | `{{code}} {{name}}` |

#### 색상도 그냥 두면 안 됐다

처음에 5번 패널을 빼고는 모두 `palette-classic`(자동 색상)으로 두었는데, 시리즈가 7~8개를 넘어가면 색상이 비슷해 보이는 짝이 생겼다. 시각적 식별이 안 되면 패널 자체의 가치가 떨어진다.

해결은 두 가지를 썼다.

- **palette-classic**: 시리즈 수가 적당한 패널(1, 3, 4)에 적용. 자동이지만 distinct한 색을 우선 배정
- **fixed color**: 시스템 에러 단독 패널(5)은 `red` 단일색. "이 패널이 켜지면 무조건 위험"이라는 시각적 신호

Pie chart의 `category=4` / `category=5`도 `displayName override`로 `User Errors` / `System Errors` 로 바꾸고, 색상도 `orange` / `dark-red`로 고정해서 직관적으로 읽히게 했다.

## 적용 후 알게 된 것들

### Counter는 절대 줄지 않는다 (그래서 retention이 중요하다)

이 글의 PromQL 트레이드오프 전체가 **counter는 단조 증가한다**는 본성에서 출발한다. Pod이 재시작되면 카운터가 0부터 다시 시작하지만, 그건 Prometheus 입장에서 보면 같은 라벨 시리즈에 reset이 감지되는 것이고, 시리즈 자체는 **보관 기간**(retention) 내내 살아 있다.

"한 번 발생한 errorCode가 영원히 남는 것 같은데"는 이 본성 때문이다. 사라지게 하려면 (1) 시간 범위를 짧게 (2) `rate`/`increase` 윈도우 사용 (3) 시리즈 자체가 보관 기간에서 만료. 보통 (2)가 답이다.

### 라벨 카디널리티는 사전에 계산하고 시작한다

실수로 user-id, request-id 같은 unbounded 라벨을 박으면 Prometheus 메모리가 폭발한다. 이번 메트릭은:

- `code` ↔ `name` 1:1: 약 50개 (enum 멤버 수)
- `category`: 3개 (`4`, `5`, `system`)
- `exception`: 약 10개 이내

총 시리즈 수 상한은 `50 × 3 × 10 = 1500` 정도. 클러스터/네임스페이스/pod 라벨이 곱해지더라도 충분히 안전한 범위다. 라벨 하나 추가할 때마다 이런 곱셈을 머릿속에서 한 번씩 해보는 습관이 있어야 사고가 안 난다.

### `$__rate_interval` 의 자동성을 신뢰한다

처음에는 `[5m]` 같이 고정 윈도우를 직접 적었다. 그런데 시간 범위를 30분으로 좁히면 곡선이 거칠어지고, 24시간으로 넓히면 너무 평탄해졌다. `$__rate_interval`로 바꾸고 나서는 이 신경을 쓸 필요가 없어졌다. Grafana 변수 중 가장 underrated 한 것 같다.

### Alert Rule은 운영 데이터가 쌓인 뒤에

대시보드를 만든 직후에는 임계치를 모른다. 1주~2주 정상 트래픽 데이터를 쌓고, "평소 분당 N건"이 어느 수준인지 본 다음에 alert rule을 정해야 false positive가 줄어든다. 그 전에는 패널만 띄워두고 운영자가 자연스럽게 익숙해지게 둔다.

## 마무리

응답을 200으로 통일하는 공통 응답 포맷 정책 자체는 흔치 않지만, 비슷한 환경(예: GraphQL이라 항상 200, gRPC와 status 변환 레이어가 있어서 표준 status가 무력화됨 등)은 의외로 많다. 표준 메트릭이 안 맞으면 직접 박는 게 결국 답인데, 그 과정에서 "어디에 박을지", "어떤 라벨을 붙일지", "PromQL을 어떻게 쓸지" 세 단계 결정이 있다는 걸 이번에 정리하게 됐다.

특히 PromQL 갈아타는 단계는 "처음부터 잘 결정할 수 있었나" 자문해 봤는데, 솔직히 누적 sum까지는 한 번 부딪혀봐야 알 수 있는 영역이었던 것 같다. 데모 검증 vs 운영 모니터링이라는 두 사용처가 생각보다 다르게 동작한다는 걸, 패널을 띄워놓고 며칠 운영해본 뒤에야 체감했다.
