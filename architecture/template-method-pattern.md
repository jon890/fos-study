# [초안] 템플릿 메서드 패턴 - 백엔드 처리 골격을 강제하는 가장 오래되고 가장 위험한 패턴

## 왜 지금 이 패턴을 다시 봐야 하는가

템플릿 메서드 패턴은 GoF 책에서 가장 먼저 배우는 행위 패턴 중 하나이고, 거의 모든 백엔드 프레임워크 깊은 곳에 박혀 있다. Spring의 `JdbcTemplate`, `RestTemplate`, `TransactionTemplate`, `AbstractApplicationContext.refresh()`, Spring Batch의 `Tasklet`/`ItemReader`-`ItemProcessor`-`ItemWriter` 골격, Servlet의 `HttpServlet.service()` → `doGet`/`doPost`, `JpaRepository`의 쿼리 실행 흐름까지 모두 이 패턴의 변형이다.

그런데 실제 면접에서 "템플릿 메서드 패턴이 뭔가요?"를 물을 때 면접관이 듣고 싶은 건 위키피디아 정의가 아니다. 시니어 레벨에서 검증하려는 것은 다음 세 가지다.

1. 처리 골격을 어떤 기준으로 추상 클래스에 박고, 어떤 단계를 하위 클래스에 위임할지를 본인이 설계할 수 있는가
2. 상속 기반 설계가 가지는 결합도, 확장성, 테스트 용이성의 단점을 인지하고 있고, 언제 전략 패턴 / 함수형 콜백 / 데코레이터로 갈아탈지 판단 기준이 있는가
3. Spring 생태계에서 이 패턴이 어떻게 쓰이는지, 그리고 본인 코드에 도입할 때 트랜잭션 / 예외 처리 / 메트릭 / 로깅 같은 횡단 관심사를 어디에 둘지 결정할 수 있는가

이 글은 이 세 가지 질문에 답할 수 있는 수준까지 끌고 가는 것을 목표로 한다.

## 핵심 개념 - 변하지 않는 골격과 변하는 단계

템플릿 메서드 패턴은 한 문장으로 표현하면 다음과 같다.

> 알고리즘의 골격은 상위 클래스에 고정하고, 알고리즘을 구성하는 일부 단계만 하위 클래스가 오버라이드하게 만든다. 호출 흐름은 항상 상위 클래스가 통제한다.

여기서 "호출 흐름은 항상 상위 클래스가 통제한다"는 부분이 본질이다. 이걸 다른 말로 하면 **헐리우드 원칙(Hollywood Principle, "Don't call us, we'll call you")** 이다. 하위 클래스는 자기가 언제 호출될지 모른다. 단지 약속된 훅 메서드를 구현해 두면, 상위 클래스가 적절한 순간에 자기 단계를 호출해 준다.

이 패턴이 다루는 메서드는 크게 네 종류로 나뉜다.

- **템플릿 메서드(template method)**: 처리 흐름 전체를 정의하는 메서드. 보통 `final`로 막아 흐름 자체를 하위 클래스가 못 바꾸게 한다.
- **추상 단계(abstract operation)**: 하위 클래스가 반드시 구현해야 하는 단계. 이 단계가 없으면 알고리즘이 의미가 없다.
- **훅 메서드(hook)**: 기본 구현이 비어 있거나 기본 동작이 정의된 단계. 하위 클래스가 필요할 때만 오버라이드한다.
- **불변 단계(invariant operation)**: 모든 하위 클래스에 공통으로 필요한 단계. `protected final` 혹은 `private`으로 두고 하위에서 못 건드리게 한다.

이 네 가지를 분명히 구분하는 것만으로도 설계 의도가 코드에 드러난다. 면접에서 "왜 어떤 메서드는 abstract고, 어떤 메서드는 빈 구현이고, 어떤 메서드는 final인가요?"를 물었을 때 답할 수 있어야 한다.

## 가장 흔한 백엔드 적용 - validation → processing → save 골격

실제 백엔드에서 가장 자주 마주치는 패턴은 도메인 명령(Command) 처리 흐름이다. "주문 생성", "쿠폰 발급", "정산 트리거" 같은 것들이 모두 다음과 같은 동일한 골격을 가진다.

1. 입력 검증
2. 비즈니스 규칙 평가
3. 도메인 객체 변경/생성
4. 영속화
5. 이벤트 발행
6. 응답 변환

요청마다 입력 형태와 비즈니스 규칙은 다르지만, 골격 자체는 동일하다. 이 골격을 매 핸들러마다 복붙하면 다음 문제들이 누적된다.

- 어떤 핸들러는 검증을 빠뜨리고, 어떤 핸들러는 이벤트 발행을 빠뜨린다.
- 트랜잭션 경계와 이벤트 발행 순서가 핸들러마다 미묘하게 다르다.
- 신규 입사자가 "이 흐름을 어디까지 따라야 하는가?"를 매번 다시 학습해야 한다.

이때 템플릿 메서드를 적용하면 골격은 강제하고, 검증/규칙/영속화 단계만 하위 클래스에서 정의하게 된다.

## 실전 Java 예제 1 - 외부 API 통합 템플릿

외부 결제 PG, 외부 마케팅 채널, 외부 정산 시스템 등 외부 API를 호출하는 어댑터들은 모두 다음 흐름이 동일하다.

- 요청 페이로드 빌드
- 인증 헤더 부착
- 호출 + 타임아웃/재시도
- 응답 파싱
- 도메인 예외로 변환
- 메트릭/로그 기록

이 골격을 템플릿 메서드로 정리하면 새 PG를 붙일 때 "이 PG의 요청 페이로드는 어떻게 만들고, 응답을 어떻게 해석하는가?"만 구현하면 된다.

```java
public abstract class ExternalApiTemplate<REQ, RES> {

    private static final Logger log = LoggerFactory.getLogger(ExternalApiTemplate.class);

    private final RestClient restClient;
    private final MeterRegistry meterRegistry;

    protected ExternalApiTemplate(RestClient restClient, MeterRegistry meterRegistry) {
        this.restClient = restClient;
        this.meterRegistry = meterRegistry;
    }

    public final RES execute(REQ request) {
        validate(request);
        HttpHeaders headers = buildHeaders(request);
        Object payload = buildPayload(request);

        Timer.Sample sample = Timer.start(meterRegistry);
        try {
            String raw = restClient.post()
                    .uri(endpoint(request))
                    .headers(h -> h.addAll(headers))
                    .body(payload)
                    .retrieve()
                    .body(String.class);

            RES response = parseResponse(raw);
            verifyBusinessResult(response);
            return response;
        } catch (RestClientResponseException e) {
            throw translateHttpError(e);
        } catch (ExternalBusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new ExternalCallFailedException(channelName(), e);
        } finally {
            sample.stop(meterRegistry.timer("external.api", "channel", channelName()));
        }
    }

    protected abstract String channelName();
    protected abstract String endpoint(REQ request);
    protected abstract HttpHeaders buildHeaders(REQ request);
    protected abstract Object buildPayload(REQ request);
    protected abstract RES parseResponse(String raw);

    protected void validate(REQ request) {
        if (request == null) {
            throw new IllegalArgumentException("request must not be null");
        }
    }

    protected void verifyBusinessResult(RES response) {
        // 기본은 통과. 채널마다 응답 코드 검증 다르므로 훅으로 둠
    }

    protected RuntimeException translateHttpError(RestClientResponseException e) {
        return new ExternalCallFailedException(channelName(), e);
    }
}
```

여기서 중요한 결정들을 짚어 본다.

- `execute`는 `final`이다. 흐름을 하위 클래스가 바꾸지 못한다. 외부 API 호출에서 메트릭 측정과 예외 변환을 빠뜨리는 사고가 자주 나기 때문에, 이걸 강제하는 게 패턴 도입의 핵심 가치다.
- `validate`와 `verifyBusinessResult`는 훅이다. 기본 구현이 있고, 채널별로 추가 검증이 필요하면 오버라이드한다.
- `channelName`, `endpoint`, `buildHeaders`, `buildPayload`, `parseResponse`는 abstract다. 이게 없으면 알고리즘이 성립하지 않는다.
- `translateHttpError`는 protected지만 final이 아니다. 채널마다 4xx 응답을 어떻게 도메인 예외로 매핑할지가 다르기 때문이다.

이 템플릿을 상속한 구체 클래스는 이렇게 짧아진다.

```java
@Component
public class TossPaymentClient extends ExternalApiTemplate<PayRequest, PayResponse> {

    public TossPaymentClient(RestClient tossRestClient, MeterRegistry meterRegistry) {
        super(tossRestClient, meterRegistry);
    }

    @Override protected String channelName() { return "toss"; }

    @Override protected String endpoint(PayRequest request) {
        return "/v1/payments/" + request.paymentKey();
    }

    @Override protected HttpHeaders buildHeaders(PayRequest request) {
        HttpHeaders h = new HttpHeaders();
        h.setBasicAuth(request.secretKey(), "");
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    @Override protected Object buildPayload(PayRequest request) {
        return Map.of("orderId", request.orderId(), "amount", request.amount());
    }

    @Override protected PayResponse parseResponse(String raw) {
        return JsonUtils.read(raw, PayResponse.class);
    }

    @Override protected void verifyBusinessResult(PayResponse response) {
        if (!"DONE".equals(response.status())) {
            throw new ExternalBusinessException("toss", response.code(), response.message());
        }
    }
}
```

`execute`를 호출하는 모든 PG가 동일한 메트릭 키, 동일한 예외 변환, 동일한 로깅 정책을 따르게 된다. 신규 PG를 붙이는 사람은 "골격을 흉내 내자"가 아니라 "이 다섯 개 메서드만 구현하면 된다"는 확정된 계약을 받는다.

## 실전 Java 예제 2 - 배치 잡 파이프라인 골격

Spring Batch가 이 패턴을 가장 노골적으로 쓰는 곳이다. 직접 만든 잡에서도 같은 구조를 빌려올 수 있다. 정산, 메일 발송, 데이터 마이그레이션 같은 잡은 거의 대부분 다음 골격이다.

```java
public abstract class BatchJobTemplate<ITEM> {

    private static final Logger log = LoggerFactory.getLogger(BatchJobTemplate.class);

    private final TransactionTemplate tx;

    protected BatchJobTemplate(TransactionTemplate tx) {
        this.tx = tx;
    }

    public final BatchResult run(BatchContext ctx) {
        beforeJob(ctx);
        int processed = 0;
        int failed = 0;
        try {
            int page = 0;
            while (true) {
                List<ITEM> chunk = readChunk(ctx, page);
                if (chunk.isEmpty()) break;

                for (ITEM item : chunk) {
                    try {
                        tx.executeWithoutResult(status -> {
                            ITEM processedItem = process(item);
                            write(processedItem);
                        });
                        processed++;
                    } catch (Exception e) {
                        failed++;
                        onItemFailed(item, e);
                        if (!continueOnError(e)) throw e;
                    }
                }
                page++;
            }
            return new BatchResult(processed, failed);
        } finally {
            afterJob(ctx, processed, failed);
        }
    }

    protected abstract List<ITEM> readChunk(BatchContext ctx, int page);
    protected abstract ITEM process(ITEM item);
    protected abstract void write(ITEM item);

    protected void beforeJob(BatchContext ctx) {}
    protected void afterJob(BatchContext ctx, int processed, int failed) {}
    protected void onItemFailed(ITEM item, Exception e) {
        log.warn("batch item failed", e);
    }
    protected boolean continueOnError(Exception e) {
        return e instanceof RecoverableBatchException;
    }
}
```

여기서 면접에서 자주 파고드는 디테일이 한 가지 있다. **트랜잭션 경계를 어디에 둘 것인가**다. 위 예제는 chunk 단위가 아니라 item 단위로 트랜잭션을 끊었다. 이유는 다음과 같다.

- chunk 트랜잭션이 길어지면 락 보유 시간이 길어지고 다른 OLTP 트래픽에 영향을 준다.
- 부분 실패 시 어떤 item이 실패했는지 격리하기 쉽다.
- 단점으로 chunk 처리량이 떨어지고 트랜잭션 오버헤드가 늘어난다.

이런 결정이 템플릿 안쪽에 박혀 있어야 잡마다 트랜잭션 정책이 갈라지는 사고를 막을 수 있다. 이걸 훅으로 빼서 하위 클래스가 결정하게 만들면 처음부터 패턴을 적용한 의미가 사라진다.

## Bad vs Improved - 진짜로 잘못 쓰는 패턴

템플릿 메서드 패턴은 잘못 쓰면 상속 지옥을 만든다. 다음은 실제로 자주 보는 안티패턴이다.

### Bad: 흐름을 protected로 열어 둔 경우

```java
public abstract class OrderHandler {
    public Result handle(Command cmd) {
        validate(cmd);
        Result r = process(cmd);
        save(r);
        publish(r);
        return r;
    }
    protected abstract void validate(Command cmd);
    protected abstract Result process(Command cmd);
    protected abstract void save(Result r);
    protected abstract void publish(Result r);
}
```

이 코드의 문제는 `handle`에 `final`이 없다는 것이다. 어떤 하위 클래스는 `handle`을 통째로 오버라이드해서 publish를 빼고, 어떤 하위 클래스는 save 전에 publish를 한다. 골격을 강제하지 못하면 패턴의 가치가 0이 된다.

또 다른 문제는 모든 단계가 abstract라는 점이다. validate가 필요 없는 명령에서도 빈 구현을 강제로 작성해야 한다. 훅과 추상 단계의 구분이 없다.

### Improved: 흐름 잠금 + 훅/추상 분리

```java
public abstract class OrderHandler<C extends Command, R> {

    public final R handle(C cmd) {
        validate(cmd);
        R result = process(cmd);
        persist(result);
        if (shouldPublish(result)) {
            publish(result);
        }
        return result;
    }

    protected void validate(C cmd) {
        Objects.requireNonNull(cmd, "command");
    }

    protected abstract R process(C cmd);
    protected abstract void persist(R result);

    protected boolean shouldPublish(R result) { return true; }
    protected void publish(R result) {}
}
```

차이점은 다음과 같다.

- `handle`이 `final`이라 흐름을 못 바꾼다.
- `validate`는 기본 구현이 있는 훅이다. null 체크는 모두에게 공통이다.
- `process`, `persist`는 abstract다. 이게 없으면 명령 처리가 성립하지 않는다.
- `publish`와 `shouldPublish`는 훅이다. 이벤트가 필요 없는 명령에서도 빈 구현을 강제하지 않는다.

면접에서 "왜 final로 막느냐"를 물으면 답은 명확하다. 패턴의 핵심 가치가 "흐름의 강제"이기 때문에, 흐름을 못 바꾸게 막아야 비로소 패턴이 의도대로 동작한다.

## 흔한 실수 패턴

실무에서 반복적으로 마주치는 실수들을 정리한다.

**1. 추상 클래스가 너무 많은 의존성을 갖는다**

추상 클래스가 `RestClient`, `MeterRegistry`, `TransactionTemplate`, `EventPublisher`, `Validator`, `ObjectMapper`까지 받기 시작하면, 하위 클래스의 단위 테스트가 사실상 불가능해진다. 추상 클래스는 골격을 만들기 위해 필요한 최소 의존성만 가져야 한다. 횡단 관심사가 많아지면 데코레이터/AOP로 분리하는 게 낫다.

**2. 훅이 너무 많아서 흐름을 알 수 없다**

훅이 `beforeValidate`, `afterValidate`, `beforeProcess`, `afterProcess`, ... 식으로 늘어나면 결국 하위 클래스 구현자가 "내가 어디 단계를 오버라이드해야 하는지" 추적이 불가능해진다. 훅은 실제 변동성이 검증된 시점에 한 개씩 추가하는 게 맞다. 미래를 위한 훅은 만들지 않는다.

**3. abstract 단계와 훅을 구분하지 않는다**

모든 단계를 abstract로 두면 새 하위 클래스가 의미 없는 빈 구현을 잔뜩 만든다. 반대로 모두 훅(빈 기본 구현)으로 두면 핵심 단계를 빠뜨린 채 컴파일이 통과해 버린다. "이 단계 없이 알고리즘이 의미가 있는가?"가 abstract와 훅의 분기점이다.

**4. 다중 상속이 필요해진다**

"이 처리 흐름은 A 템플릿이기도 하고 B 템플릿이기도 한데..." 같은 상황이 오면 패턴 선택이 잘못된 것이다. Java는 클래스 다중 상속을 허용하지 않는다. 이 시점이면 전략 패턴으로 갈아타거나, 컴포지션 + 함수형 콜백으로 재설계해야 한다.

**5. 테스트 작성을 위한 protected 노출**

테스트 때문에 private을 protected로 풀어 두고, 테스트 전용 더미 하위 클래스를 만들기 시작하면 캡슐화가 깨진다. 단위 테스트는 구체 클래스의 public 진입점을 통해서 검증하고, 흐름 자체를 테스트하고 싶다면 추상 클래스에 대한 "테스트용 미니 구현"을 같은 패키지에 두는 정도로 끝내는 게 낫다.

## 전략 패턴과의 차이 - 면접 단골

이 비교는 면접에서 90% 확률로 나온다. 핵심 차이를 명확히 정리한다.

| 관점 | 템플릿 메서드 | 전략 패턴 |
|------|---------------|-----------|
| 변동성을 어떻게 분리 | **상속**으로 단계만 교체 | **합성**으로 알고리즘 전체를 교체 |
| 변동의 단위 | 알고리즘의 일부 단계 | 알고리즘 전체 |
| 호출 흐름 통제 | 추상 클래스가 통제 | 컨텍스트가 전략 객체에 위임 |
| 런타임 교체 | 어렵다(상속 시점에 결정) | 쉽다(주입만 바꾸면 됨) |
| 결합도 | 높다(상속 결합) | 낮다(인터페이스 결합) |
| 적합한 경우 | 흐름 골격이 안정적이고, 변하는 단계가 적을 때 | 알고리즘 자체가 자주 갈리거나 런타임에 갈아끼워야 할 때 |

면접에서 본인이 직접 답을 정리해 둔다.

> 템플릿 메서드는 "흐름은 고정인데 일부 단계만 다르다"가 명확할 때 쓰고, 전략 패턴은 "알고리즘 자체가 갈린다"가 핵심일 때 쓴다. 외부 API 통합처럼 호출/예외 변환/메트릭 골격이 회사 표준으로 고정되어 있고 채널별로 페이로드/응답만 다르면 템플릿이 적합하다. 반면 할인 정책처럼 정책 자체가 런타임에 바뀌고, 정책끼리 조합도 필요하면 전략으로 가는 게 맞다.

추가로 함수형 콜백과의 비교도 같이 준비한다. Spring의 `JdbcTemplate.query(sql, RowMapper)`는 사실상 "템플릿 + 1개짜리 전략"이다. 변하는 단계가 한두 개뿐이면 추상 클래스 상속보다 함수형 인터페이스 콜백이 가볍다. Java 8 이후에는 "단계가 1~2개면 람다, 3개 이상이고 안정적이면 추상 클래스" 정도의 감각을 가지면 된다.

## 테스트 가능성 트레이드오프

템플릿 메서드 패턴은 단위 테스트 관점에서 양면성이 있다.

**좋은 점**

- 흐름이 추상 클래스 한 곳에 있으니, 흐름 자체에 대한 테스트는 구체 클래스 한두 개로 통합 검증할 수 있다.
- 새 하위 클래스를 추가할 때 단계 메서드만 격리해 테스트하기 쉽다(입력 → 출력이 메서드 단위로 명확함).

**나쁜 점**

- 흐름 통제가 추상 클래스에 있기 때문에, 하위 클래스를 단독으로 테스트하면서 흐름까지 검증하려면 결국 추상 클래스의 `final` 메서드를 통과시켜야 한다. 즉 단위 테스트가 통합 테스트화된다.
- 추상 클래스에 외부 의존성(예: `RestClient`, `MeterRegistry`)이 박혀 있으면, 모든 하위 클래스 테스트에서 그 의존성을 매번 모킹해야 한다.
- 흐름 변경이 추상 클래스에서 일어나면 모든 하위 클래스 테스트가 한 번에 깨질 수 있다. 이게 안정성의 측면이기도 하지만, 빠른 변경을 막는 비용이기도 하다.

실무 가이드라인.

- 추상 클래스의 의존성은 가능한 한 좁게 가져간다(그 의존성이 골격에 진짜 필수인가?).
- 흐름 검증은 "테스트용 가짜 하위 클래스"를 만들어서 한 번만 한다.
- 단계 검증은 진짜 하위 클래스 단위 테스트에서 한다.
- 횡단 관심사(메트릭, 로깅, 트랜잭션)가 많아지면 템플릿이 아니라 데코레이터/AOP로 분리한다.

## 로컬 실습 환경

JDK 17 + Maven/Gradle만 있으면 된다. Spring 없이 순수 Java로도 충분히 실습할 수 있다.

```bash
# 디렉터리 준비
mkdir -p template-method-lab/src/main/java/lab
mkdir -p template-method-lab/src/test/java/lab
cd template-method-lab

# Gradle 프로젝트라면
gradle init --type java-application --dsl groovy --test-framework junit-jupiter
```

`build.gradle`의 의존성에 다음을 더한다.

```groovy
dependencies {
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
    testImplementation 'org.assertj:assertj-core:3.24.2'
}
```

## 실행 가능한 예제 - 파서 프레임워크

CSV/TSV/JSON Lines 파서를 동일한 골격으로 묶는 예제다. 면접에서 "한 가지 예시를 직접 짜 본 적 있나요?"를 물었을 때 입에서 바로 나올 만한 작은 예제로 적당하다.

```java
package lab;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.util.ArrayList;
import java.util.List;

public abstract class LineBasedParser<T> {

    public final List<T> parse(Reader reader) {
        List<T> result = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(reader)) {
            beforeParse();
            String line;
            int lineNo = 0;
            while ((line = br.readLine()) != null) {
                lineNo++;
                if (shouldSkip(line, lineNo)) continue;
                try {
                    T item = parseLine(line, lineNo);
                    if (item != null) result.add(item);
                } catch (Exception e) {
                    onParseError(line, lineNo, e);
                }
            }
            afterParse(result);
            return result;
        } catch (IOException e) {
            throw new ParseFailedException(e);
        }
    }

    protected abstract T parseLine(String line, int lineNo);

    protected boolean shouldSkip(String line, int lineNo) {
        return line.isBlank();
    }

    protected void beforeParse() {}
    protected void afterParse(List<T> items) {}

    protected void onParseError(String line, int lineNo, Exception e) {
        throw new ParseFailedException("line " + lineNo + ": " + line, e);
    }

    public static class ParseFailedException extends RuntimeException {
        public ParseFailedException(String msg, Throwable cause) { super(msg, cause); }
        public ParseFailedException(Throwable cause) { super(cause); }
    }
}
```

CSV 구체 클래스.

```java
package lab;

public class CsvUserParser extends LineBasedParser<User> {

    private boolean headerSeen = false;

    @Override
    protected boolean shouldSkip(String line, int lineNo) {
        if (super.shouldSkip(line, lineNo)) return true;
        if (!headerSeen) { headerSeen = true; return true; }
        return false;
    }

    @Override
    protected User parseLine(String line, int lineNo) {
        String[] cols = line.split(",", -1);
        if (cols.length < 3) {
            throw new IllegalArgumentException("expected 3 cols, got " + cols.length);
        }
        return new User(Long.parseLong(cols[0].trim()), cols[1].trim(), cols[2].trim());
    }
}
```

테스트.

```java
package lab;

import org.junit.jupiter.api.Test;

import java.io.StringReader;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CsvUserParserTest {

    @Test
    void skipsHeaderAndBlankLines() {
        String csv = "id,name,email\n1,kim,kim@a.com\n\n2,lee,lee@b.com\n";
        List<User> users = new CsvUserParser().parse(new StringReader(csv));
        assertThat(users).extracting(User::name).containsExactly("kim", "lee");
    }

    @Test
    void invalidLineThrowsByDefault() {
        String csv = "id,name,email\nbroken-line\n";
        assertThatThrownBy(() -> new CsvUserParser().parse(new StringReader(csv)))
                .isInstanceOf(LineBasedParser.ParseFailedException.class);
    }
}
```

이 작은 예제만 직접 손으로 쳐 봐도, "흐름은 final, 단계는 abstract, 변동성은 hook" 감각이 잡힌다.

## 면접 답변 프레이밍

면접에서 받는 질문 유형별로 답을 미리 짜 둔다.

**Q. 템플릿 메서드 패턴이 뭔가요?**

알고리즘의 골격을 상위 클래스에 고정하고, 변하는 단계만 하위 클래스가 구현하게 하는 행위 패턴입니다. 핵심은 흐름 통제 권한이 항상 상위 클래스에 있다는 점이고, 그래서 보통 템플릿 메서드 자체는 final로 막아 흐름을 강제합니다. Spring의 `JdbcTemplate`이나 Spring Batch의 chunk 기반 잡 흐름이 대표적인 예입니다.

**Q. 전략 패턴과 어떻게 다른가요?**

변동성의 단위가 다릅니다. 템플릿은 "흐름은 고정, 단계만 다름"일 때, 전략은 "알고리즘 자체가 다름"일 때 씁니다. 또 템플릿은 상속 기반이라 결합도가 높고 런타임 교체가 어렵고, 전략은 합성 기반이라 런타임에 갈아끼우기 쉽습니다. 변하는 단계가 1~2개라면 추상 클래스보다는 전략(혹은 함수형 콜백)이 더 가벼운 선택일 때가 많습니다.

**Q. 본인이 직접 도입해 본 적이 있나요?**

외부 API 통합 어댑터에서 메트릭, 예외 변환, 로깅을 매 채널마다 빠뜨리는 사고가 반복되어, 외부 호출 골격을 추상 클래스에 final로 박고 채널별 endpoint/payload/response 파싱만 abstract로 노출했습니다. 그 결과 신규 채널 연동 PR의 리뷰 포인트가 "흐름이 맞는가"에서 "이 채널의 페이로드 스펙이 맞는가"로 좁혀져서, 리뷰 시간과 사고가 함께 줄었습니다.

**Q. 단점이나 주의할 점은?**

상속 결합이 강합니다. 추상 클래스의 변경이 모든 하위 클래스에 전파되고, 다중 상속이 필요해지는 순간 패턴이 깨집니다. 또 추상 클래스가 의존성을 너무 많이 가지면 단위 테스트가 통합 테스트화됩니다. 그래서 골격이 진짜 안정적인지, 횡단 관심사를 AOP/데코레이터로 분리할 수 있는지를 먼저 검토합니다. 이게 안 되면 전략 패턴이나 함수형 콜백이 더 맞는 선택입니다.

**Q. 시니어 관점에서 패턴 도입 결정 기준은?**

세 가지를 봅니다. 첫째, 흐름이 회사/팀 표준으로 고정되어야 하는가(예: 외부 호출 메트릭 정책, 트랜잭션 경계). 둘째, 변동성이 단계 수준에 머무르는가, 알고리즘 전체에 걸쳐 있는가. 셋째, 미래에 다중 상속이나 전혀 다른 흐름이 필요해질 가능성이 있는가. 첫째와 둘째가 yes고 셋째가 no일 때만 도입합니다. 이 셋 중 하나라도 흔들리면 전략 패턴이나 함수형 콜백으로 시작해서 필요해질 때 리팩터링합니다.

## 학습 체크리스트

- [ ] 템플릿 메서드, 추상 단계, 훅, 불변 단계 네 가지를 한 줄씩 설명할 수 있다.
- [ ] `final` 템플릿 메서드를 두는 이유를 헐리우드 원칙과 연결해 설명할 수 있다.
- [ ] abstract 단계와 훅의 분기 기준("이 단계 없이 알고리즘이 성립하는가?")을 본인 코드 예시로 설명할 수 있다.
- [ ] 외부 API 통합 / 배치 잡 / 명령 핸들러 / 파서 프레임워크 중 두 개 이상에서 패턴 적용 시나리오를 직접 짤 수 있다.
- [ ] 전략 패턴과의 차이를 "변동성의 단위" 관점으로 1분 안에 설명할 수 있다.
- [ ] 함수형 콜백(`JdbcTemplate` 스타일)과 추상 클래스 상속을 언제 갈라 쓸지 본인 기준이 있다.
- [ ] 상속 결합, 다중 상속 불가, 테스트 통합화 같은 단점을 인지하고 대안(AOP, 데코레이터, 전략)을 제시할 수 있다.
- [ ] Spring `JdbcTemplate`/`TransactionTemplate`/`AbstractApplicationContext.refresh()`/Spring Batch chunk 흐름 중 한 가지 이상의 동작 흐름을 그릴 수 있다.
- [ ] 본인이 직접 작성한 추상 클래스 한 개를 보여주고, 왜 어떤 메서드는 final/abstract/hook인지 설명할 수 있다.
- [ ] 패턴을 도입하지 말아야 할 경우(다중 상속 필요, 알고리즘 전체가 갈림, 흐름이 아직 검증되지 않음)를 명확히 말할 수 있다.
