# [초안] Strategy Pattern — 분기문을 없애는 설계, 시니어 백엔드 인터뷰 핵심 패턴

---

## 왜 지금 이 패턴인가

코드를 오래 작성하다 보면 반드시 만나는 장면이 있다. 결제 수단이 하나 추가될 때마다 `if-else` 블록이 늘어나는 `PaymentService`, 할인 정책 종류가 바뀔 때마다 손대야 하는 `DiscountCalculator`, 알림 채널이 추가될 때마다 재배포해야 하는 `NotificationDispatcher`. 이 구조는 처음엔 단순해 보이지만, 결국 수백 줄의 거대한 분기문과 테스트 불가능한 메서드, 그리고 "저 코드는 아무도 건드리면 안 됩니다"라는 팀 규칙으로 귀결된다.

Strategy Pattern은 그 분기문을 없애는 대신, **알고리즘(행동)을 독립된 클래스로 캡슐화하고 런타임에 교체 가능**하게 만드는 패턴이다. GoF(Gang of Four)가 정의한 23가지 패턴 중 가장 실무 친화적인 것 중 하나이며, 특히 Java/Spring 백엔드에서 도메인 로직의 복잡도를 관리하는 핵심 수단이다.

시니어 백엔드 면접에서 이 패턴을 물어보는 이유는 단순히 패턴 이름을 알고 있는지 확인하는 게 아니다. **OCP(개방-폐쇄 원칙)를 실제로 코드에 적용할 수 있는지, 테스트 가능한 구조를 의도적으로 설계할 수 있는지**를 보는 것이다.

---

## 핵심 개념: 전략을 행동으로 분리한다

Strategy Pattern의 구조는 세 요소로 구성된다.

- **Strategy 인터페이스**: 알고리즘의 계약(contract)을 정의한다.
- **ConcreteStrategy**: 인터페이스를 구현하는 각각의 알고리즘 클래스.
- **Context**: Strategy를 보유하고 위임(delegation)을 통해 실행한다.

핵심은 Context가 ConcreteStrategy를 직접 알지 않는다는 것이다. Context는 오직 Strategy 인터페이스만 의존한다. 어떤 구체 구현이 주입되는지는 Context 외부에서 결정된다.

```
Client → Context ──uses──▶ «interface» Strategy
                              ▲         ▲         ▲
                    ConcreteA   ConcreteB   ConcreteC
```

이 구조가 단순 `if-else`와 근본적으로 다른 이유는 **새로운 전략을 추가할 때 기존 코드를 수정하지 않아도 된다**는 점이다. 인터페이스만 구현하면 된다. 이것이 OCP가 말하는 "확장에는 열려 있고, 수정에는 닫혀 있다"의 실체다.

---

## 문제 상황: if-else로 가득 찬 결제 서비스

나쁜 예부터 보자. 다음은 결제 수단이 세 가지일 때 흔히 볼 수 있는 구조다.

```java
// BAD: 분기가 비즈니스 로직과 뒤섞인 구조
@Service
public class PaymentService {

    public PaymentResult pay(PaymentRequest request) {
        String method = request.getPaymentMethod();

        if ("CARD".equals(method)) {
            // 카드 결제 로직
            CardGateway gateway = new CardGateway();
            gateway.authorize(request.getCardNumber(), request.getAmount());
            return new PaymentResult("CARD", request.getAmount(), "SUCCESS");

        } else if ("KAKAO_PAY".equals(method)) {
            // 카카오페이 로직
            KakaoPayClient client = new KakaoPayClient();
            client.requestPayment(request.getUserId(), request.getAmount());
            return new PaymentResult("KAKAO_PAY", request.getAmount(), "SUCCESS");

        } else if ("NAVER_PAY".equals(method)) {
            // 네이버페이 로직
            NaverPayApi api = new NaverPayApi();
            api.charge(request.getNaverPayToken(), request.getAmount());
            return new PaymentResult("NAVER_PAY", request.getAmount(), "SUCCESS");

        } else {
            throw new IllegalArgumentException("지원하지 않는 결제 수단: " + method);
        }
    }
}
```

이 코드의 문제점을 열거하면:

1. **결제 수단이 추가될 때마다 이 메서드를 수정해야 한다.** OCP 위반.
2. **단위 테스트가 불가능하다.** `CardGateway`, `KakaoPayClient`를 직접 `new`로 생성하기 때문에 mock으로 교체할 수 없다.
3. **하나의 메서드가 모든 결제 로직을 안다.** SRP 위반.
4. **실수로 조건을 빠뜨리거나 중복되는 분기가 생기기 쉽다.**

---

## 개선: Strategy Pattern 적용

### 1단계: Strategy 인터페이스 정의

```java
public interface PaymentStrategy {
    PaymentResult pay(PaymentRequest request);
    boolean supports(String paymentMethod);
}
```

`supports()` 메서드는 어떤 전략이 어떤 결제 수단을 처리할 수 있는지 스스로 판단하게 만드는 핵심 장치다. Context가 분기하는 게 아니라 전략 스스로 자기 적용 범위를 선언한다.

### 2단계: ConcreteStrategy 구현

```java
@Component
public class CardPaymentStrategy implements PaymentStrategy {

    private final CardGateway cardGateway;

    public CardPaymentStrategy(CardGateway cardGateway) {
        this.cardGateway = cardGateway;
    }

    @Override
    public PaymentResult pay(PaymentRequest request) {
        cardGateway.authorize(request.getCardNumber(), request.getAmount());
        return new PaymentResult("CARD", request.getAmount(), "SUCCESS");
    }

    @Override
    public boolean supports(String paymentMethod) {
        return "CARD".equals(paymentMethod);
    }
}

@Component
public class KakaoPayStrategy implements PaymentStrategy {

    private final KakaoPayClient kakaoPayClient;

    public KakaoPayStrategy(KakaoPayClient kakaoPayClient) {
        this.kakaoPayClient = kakaoPayClient;
    }

    @Override
    public PaymentResult pay(PaymentRequest request) {
        kakaoPayClient.requestPayment(request.getUserId(), request.getAmount());
        return new PaymentResult("KAKAO_PAY", request.getAmount(), "SUCCESS");
    }

    @Override
    public boolean supports(String paymentMethod) {
        return "KAKAO_PAY".equals(paymentMethod);
    }
}
```

각 ConcreteStrategy는 `@Component`로 Spring Bean으로 등록된다. 의존하는 게이트웨이/클라이언트는 생성자 주입으로 받아 테스트 시 mock으로 교체 가능하다.

### 3단계: Context — Strategy 목록을 주입받아 위임

```java
@Service
public class PaymentService {

    private final List<PaymentStrategy> strategies;

    // Spring이 PaymentStrategy 구현체 전부를 리스트로 자동 주입
    public PaymentService(List<PaymentStrategy> strategies) {
        this.strategies = strategies;
    }

    public PaymentResult pay(PaymentRequest request) {
        PaymentStrategy strategy = strategies.stream()
            .filter(s -> s.supports(request.getPaymentMethod()))
            .findFirst()
            .orElseThrow(() -> new IllegalArgumentException(
                "지원하지 않는 결제 수단: " + request.getPaymentMethod()
            ));

        return strategy.pay(request);
    }
}
```

이제 `PaymentService`는 결제 수단 추가와 완전히 분리됐다. 새 결제 수단 `TossPay`가 추가된다면 `TossPayStrategy`를 `@Component`로 만들면 된다. `PaymentService`는 건드릴 필요가 없다.

---

## 백엔드 실무 적용 패턴 5가지

### 1. 할인 정책 (Discount Policy)

이커머스, 헬스케어 플랫폼에서 할인 구조는 시간이 지날수록 복잡해진다.

```java
public interface DiscountPolicy {
    int calculate(Order order);
    boolean applicable(Order order);
}

@Component
public class MemberGradeDiscountPolicy implements DiscountPolicy {
    @Override
    public int calculate(Order order) {
        return switch (order.getMemberGrade()) {
            case VIP -> (int) (order.getTotalAmount() * 0.1);
            case GOLD -> (int) (order.getTotalAmount() * 0.05);
            default -> 0;
        };
    }

    @Override
    public boolean applicable(Order order) {
        return order.getMemberGrade() != null;
    }
}

@Component
public class CouponDiscountPolicy implements DiscountPolicy {
    @Override
    public int calculate(Order order) {
        return order.getCoupon().getDiscountAmount();
    }

    @Override
    public boolean applicable(Order order) {
        return order.getCoupon() != null && order.getCoupon().isValid();
    }
}
```

할인이 중첩 적용되어야 한다면 `List<DiscountPolicy>`를 모두 순회하며 합산하는 방식으로 확장할 수 있다.

### 2. 알림 채널 (Notification Channel)

```java
public interface NotificationStrategy {
    void send(NotificationMessage message);
    NotificationChannel channel();
}

@Component
public class PushNotificationStrategy implements NotificationStrategy {
    @Override
    public void send(NotificationMessage message) {
        // Firebase FCM 연동 로직
    }

    @Override
    public NotificationChannel channel() {
        return NotificationChannel.PUSH;
    }
}

@Component
public class EmailNotificationStrategy implements NotificationStrategy {
    @Override
    public void send(NotificationMessage message) {
        // SES 또는 SMTP 발송 로직
    }

    @Override
    public NotificationChannel channel() {
        return NotificationChannel.EMAIL;
    }
}
```

### 3. 파싱 전략 (File Format Parsing)

배치나 데이터 수집 파이프라인에서 파일 포맷이 다양한 경우:

```java
public interface FileParsingStrategy {
    List<ProductData> parse(InputStream inputStream);
    boolean supports(String fileExtension);
}

@Component
public class CsvParsingStrategy implements FileParsingStrategy {
    @Override
    public List<ProductData> parse(InputStream inputStream) {
        // CSV 파싱 로직 (OpenCSV 등)
        return new ArrayList<>();
    }

    @Override
    public boolean supports(String fileExtension) {
        return "csv".equalsIgnoreCase(fileExtension);
    }
}

@Component
public class ExcelParsingStrategy implements FileParsingStrategy {
    @Override
    public List<ProductData> parse(InputStream inputStream) {
        // Apache POI 로직
        return new ArrayList<>();
    }

    @Override
    public boolean supports(String fileExtension) {
        return "xlsx".equalsIgnoreCase(fileExtension) || "xls".equalsIgnoreCase(fileExtension);
    }
}
```

### 4. 슬롯 엔진 / 핸들러 분리 (본인 경험과의 연결)

슬롯 게임 엔진처럼 **게임 타입별로 다른 처리 로직**이 필요한 경우가 있다. 각 게임 유형(클래식 슬롯, 멀티라인, 보너스 슬롯 등)이 공통 인터페이스를 구현하는 ConcreteStrategy가 된다.

```java
public interface SlotGameHandler {
    SpinResult process(SpinRequest request);
    boolean supports(GameType gameType);
}

@Component
public class ClassicSlotHandler implements SlotGameHandler {
    @Override
    public SpinResult process(SpinRequest request) {
        // 3릴 클래식 슬롯 처리
        return new SpinResult();
    }

    @Override
    public boolean supports(GameType gameType) {
        return GameType.CLASSIC == gameType;
    }
}

@Component
public class BonusSlotHandler implements SlotGameHandler {
    @Override
    public SpinResult process(SpinRequest request) {
        // 보너스 게임 처리
        return new SpinResult();
    }

    @Override
    public boolean supports(GameType gameType) {
        return GameType.BONUS == gameType;
    }
}

@Service
public class SlotEngineService {
    private final List<SlotGameHandler> handlers;

    public SlotEngineService(List<SlotGameHandler> handlers) {
        this.handlers = handlers;
    }

    public SpinResult spin(SpinRequest request) {
        return handlers.stream()
            .filter(h -> h.supports(request.getGameType()))
            .findFirst()
            .orElseThrow(() -> new GameNotFoundException(request.getGameType()))
            .process(request);
    }
}
```

이 구조의 장점은 게임 타입이 수십 개로 늘어나도 `SlotEngineService` 코드를 한 줄도 수정하지 않아도 된다는 것이다. 이것이 바로 실무에서 Strategy Pattern이 갖는 진짜 가치다.

### 5. 외부 API 연동 추상화 (Provider Abstraction)

헬스케어 플랫폼에서 여러 물류사, 배송 추적 API를 연동할 때:

```java
public interface ShippingTrackingStrategy {
    TrackingResult track(String trackingNumber);
    ShippingCarrier carrier();
}

// CJ대한통운, 롯데택배, 우체국 등 각각 @Component로 등록
```

---

## 흔한 실수 패턴

### 실수 1: Context가 여전히 분기문을 가진다

```java
// BAD: 전략을 도입했지만 여전히 분기
public PaymentResult pay(PaymentRequest request) {
    if ("CARD".equals(request.getPaymentMethod())) {
        return cardStrategy.pay(request);
    } else if ("KAKAO_PAY".equals(request.getPaymentMethod())) {
        return kakaoPayStrategy.pay(request);
    }
    throw new IllegalArgumentException("...");
}
```

이렇게 되면 Strategy Pattern을 도입한 의미가 없다. `supports()` 메서드나 `Map<String, Strategy>` 기반 디스패치로 완전히 분기를 제거해야 한다.

### 실수 2: 전략을 enum이나 상수로 결정한다

```java
// BAD: 외부에서 전략 타입을 직접 결정
public PaymentResult pay(PaymentRequest request) {
    PaymentStrategyType type = PaymentStrategyType.from(request.getPaymentMethod());
    PaymentStrategy strategy = strategyFactory.get(type); // switch inside factory
    return strategy.pay(request);
}
```

Factory 안에 다시 switch가 생긴다. 이 구조에서 새 전략을 추가하려면 Factory도, enum도 수정해야 한다. 분기가 이동했을 뿐이다.

**개선**: `supports()` 기반 선형 탐색 또는 `Map<String, PaymentStrategy>` 사전 조립.

```java
// IMPROVED: Map으로 사전 조립
@Configuration
public class PaymentStrategyConfig {

    @Bean
    public Map<String, PaymentStrategy> paymentStrategyMap(List<PaymentStrategy> strategies) {
        return strategies.stream()
            .collect(Collectors.toMap(
                s -> s.supportedMethod().name(),
                Function.identity()
            ));
    }
}

@Service
public class PaymentService {
    private final Map<String, PaymentStrategy> strategyMap;

    public PaymentService(Map<String, PaymentStrategy> strategyMap) {
        this.strategyMap = strategyMap;
    }

    public PaymentResult pay(PaymentRequest request) {
        return Optional.ofNullable(strategyMap.get(request.getPaymentMethod()))
            .orElseThrow(() -> new UnsupportedPaymentMethodException(request.getPaymentMethod()))
            .pay(request);
    }
}
```

`Map` 기반은 O(1) 조회로 성능도 더 낫고, 분기가 완전히 제거된다.

### 실수 3: 전략 클래스에 상태(state)를 저장한다

```java
// BAD: 상태를 가진 전략 (thread-safe 하지 않음)
@Component
public class CardPaymentStrategy implements PaymentStrategy {
    private PaymentRequest currentRequest; // 위험!

    @Override
    public PaymentResult pay(PaymentRequest request) {
        this.currentRequest = request; // 동시 요청 시 덮어써짐
        return doProcess();
    }
}
```

Spring `@Component`로 등록된 Bean은 기본이 싱글턴이다. 동시 요청이 들어오면 인스턴스 변수를 공유한다. 전략 클래스는 **무상태(stateless)**여야 한다. 필요한 데이터는 메서드 파라미터로 전달해야 한다.

### 실수 4: 전략이 너무 많아지는 Over-Engineering

전략 패턴은 **알고리즘의 변형이 명확히 구분되고, 앞으로도 추가될 가능성이 있을 때** 써야 한다. 두 개의 경우가 있고 앞으로도 거의 바뀌지 않을 거라면 단순 `if-else`나 `switch`가 더 읽기 좋다. 패턴은 복잡도를 관리하는 도구이지, 복잡도를 추가하는 도구가 아니다.

---

## 테스트 가능성: 전략 패턴의 숨은 장점

Strategy Pattern의 가장 큰 장점 중 하나는 **각 전략을 독립적으로 테스트**할 수 있다는 것이다.

```java
class CardPaymentStrategyTest {

    private CardGateway mockGateway;
    private CardPaymentStrategy strategy;

    @BeforeEach
    void setUp() {
        mockGateway = mock(CardGateway.class);
        strategy = new CardPaymentStrategy(mockGateway);
    }

    @Test
    void 카드결제_성공_시_SUCCESS_반환() {
        // given
        PaymentRequest request = PaymentRequest.builder()
            .paymentMethod("CARD")
            .cardNumber("1234-5678-9012-3456")
            .amount(50000)
            .build();

        doNothing().when(mockGateway).authorize(anyString(), anyInt());

        // when
        PaymentResult result = strategy.pay(request);

        // then
        assertThat(result.getStatus()).isEqualTo("SUCCESS");
        assertThat(result.getAmount()).isEqualTo(50000);
        verify(mockGateway, times(1)).authorize("1234-5678-9012-3456", 50000);
    }

    @Test
    void 게이트웨이_실패_시_예외_전파() {
        PaymentRequest request = PaymentRequest.builder()
            .paymentMethod("CARD")
            .cardNumber("0000-0000-0000-0000")
            .amount(50000)
            .build();

        doThrow(new GatewayException("카드 거절")).when(mockGateway).authorize(anyString(), anyInt());

        assertThatThrownBy(() -> strategy.pay(request))
            .isInstanceOf(GatewayException.class)
            .hasMessageContaining("카드 거절");
    }
}
```

Context인 `PaymentService` 테스트도 간단해진다.

```java
class PaymentServiceTest {

    @Test
    void 지원하지_않는_결제수단_요청_시_예외() {
        PaymentStrategy fakeStrategy = mock(PaymentStrategy.class);
        when(fakeStrategy.supports(anyString())).thenReturn(false);

        PaymentService service = new PaymentService(List.of(fakeStrategy));

        assertThatThrownBy(() -> service.pay(
            PaymentRequest.builder().paymentMethod("BITCOIN").build()
        )).isInstanceOf(IllegalArgumentException.class);
    }
}
```

`if-else` 구조라면 이런 테스트는 내부 구현 전체를 거쳐야 했을 것이다.

---

## Strategy vs 유사 패턴 비교

| 관점 | Strategy | Template Method | Chain of Responsibility | State |
|------|----------|----------------|------------------------|-------|
| **변하는 것** | 알고리즘 전체 | 알고리즘의 일부 단계 | 요청 처리 순서 | 객체의 상태 |
| **구조** | 위임(Delegation) | 상속(Inheritance) | 링크드 핸들러 체인 | 상태별 전략 |
| **런타임 교체** | 가능 | 불가 | 부분적 | 가능 |
| **Spring 활용** | Bean List 주입 | abstract class | Filter Chain | State machine |
| **OCP** | 완전 지원 | 부분 지원 | 지원 | 지원 |

**Template Method와의 차이**: Template Method는 상속 기반이라 클래스 계층을 강제한다. 런타임에 알고리즘을 교체할 수 없다. Strategy는 인터페이스 기반이라 더 유연하고 테스트하기 쉽다. 실무에서는 Strategy를 더 선호하는 추세다.

---

## Strategy Pattern을 쓰면 안 되는 경우

1. **알고리즘 변형이 한두 개뿐이고 미래 확장 가능성이 낮을 때**: `if-else`가 더 명확하다.
2. **Context와 전략 간 데이터 교환이 매우 복잡할 때**: 파라미터 객체가 비대해지면서 결합도가 오히려 높아질 수 있다.
3. **알고리즘이 실제로 독립적으로 교체되지 않을 때**: "혹시 나중에 바뀔 수도 있으니까"는 Over-Engineering의 시작이다.
4. **단순 값 계산 로직**: 함수형 인터페이스(`Function<T, R>`)나 람다로 충분한 경우에 굳이 클래스를 만들 필요 없다.

---

## Java 8+ 함수형 인터페이스와의 결합

간단한 전략은 클래스 없이 람다로 표현할 수 있다.

```java
// 전략 인터페이스가 함수형이면 람다 사용 가능
@FunctionalInterface
public interface PricingStrategy {
    int calculate(int basePrice, int quantity);
}

// Context
public class PriceCalculator {
    private final PricingStrategy pricingStrategy;

    public PriceCalculator(PricingStrategy pricingStrategy) {
        this.pricingStrategy = pricingStrategy;
    }

    public int getTotal(int basePrice, int quantity) {
        return pricingStrategy.calculate(basePrice, quantity);
    }
}

// 사용 측
PriceCalculator bulkCalculator = new PriceCalculator(
    (price, qty) -> qty >= 10 ? (int)(price * qty * 0.9) : price * qty
);

PriceCalculator regularCalculator = new PriceCalculator(
    (price, qty) -> price * qty
);
```

단, 람다는 `supports()` 같은 복잡한 메서드나 의존성 주입이 필요한 경우엔 쓸 수 없다. 상태가 없고 단일 메서드로 표현 가능한 간단한 알고리즘에 적합하다.

---

## 로컬 실습 환경 구성

### 최소 프로젝트 구조

```
strategy-demo/
├── src/main/java/com/demo/payment/
│   ├── PaymentStrategy.java
│   ├── PaymentService.java
│   ├── strategy/
│   │   ├── CardPaymentStrategy.java
│   │   ├── KakaoPayStrategy.java
│   │   └── NaverPayStrategy.java
│   └── dto/
│       ├── PaymentRequest.java
│       └── PaymentResult.java
└── src/test/java/com/demo/payment/
    ├── PaymentServiceTest.java
    └── strategy/
        └── CardPaymentStrategyTest.java
```

### Spring Boot 없이 동작 확인하는 최소 Main

```java
public class StrategyPatternDemo {
    public static void main(String[] args) {
        // 수동 조립 (Spring DI 없이)
        List<PaymentStrategy> strategies = List.of(
            new CardPaymentStrategy(new MockCardGateway()),
            new KakaoPayStrategy(new MockKakaoPayClient())
        );

        PaymentService service = new PaymentService(strategies);

        // 카드 결제
        PaymentRequest cardRequest = new PaymentRequest("CARD", 30000);
        System.out.println(service.pay(cardRequest));

        // 카카오페이
        PaymentRequest kakaoRequest = new PaymentRequest("KAKAO_PAY", 15000);
        System.out.println(service.pay(kakaoRequest));

        // 지원하지 않는 수단
        try {
            service.pay(new PaymentRequest("BITCOIN", 100));
        } catch (IllegalArgumentException e) {
            System.out.println("예외 발생: " + e.getMessage());
        }
    }
}
```

---

## 시니어 면접 답변 프레이밍

**Q. Strategy Pattern을 사용한 경험이 있나요?**

> "네, 슬롯 게임 엔진 개발 시 게임 타입별로 스핀 처리 로직이 달랐는데, 초기엔 `if-else` 구조로 `GameEngine` 클래스 안에서 분기했습니다. 게임 타입이 늘어나면서 클래스가 거대해지고, 특정 타입 수정 시 다른 타입 로직에 영향을 줄 위험이 생겼습니다. 이를 `SlotGameHandler` 인터페이스와 각 게임 타입별 ConcreteStrategy로 분리했고, Spring `@Component` + `List<SlotGameHandler>` 주입 패턴으로 Core 엔진 코드 수정 없이 새 게임 타입을 추가할 수 있게 됐습니다. 이후 단위 테스트도 각 핸들러 별로 독립적으로 작성할 수 있었고, 테스트 커버리지가 유의미하게 올라갔습니다."

**Q. 단순 if-else와 Strategy Pattern의 차이는?**

> "분기 책임이 어디에 있느냐입니다. `if-else`는 Context가 모든 알고리즘의 존재를 알아야 하고, 새 알고리즘 추가 시 Context를 수정해야 합니다. Strategy Pattern에서는 각 알고리즘이 자신의 적용 조건(`supports()`)을 스스로 선언합니다. Context는 전략 목록을 순회하거나 Map에서 찾을 뿐, 개별 알고리즘의 존재를 알지 못합니다. 결과적으로 Context는 새 알고리즘 추가 시 수정이 불필요하고, 알고리즘들은 독립적으로 테스트할 수 있습니다."

**Q. OCP를 어떻게 Strategy Pattern으로 구현했나요?**

> "OCP는 '기존 코드 수정 없이 기능을 확장할 수 있어야 한다'는 원칙입니다. Strategy Pattern에서 새 알고리즘은 인터페이스를 구현하는 새 클래스(확장)로 추가됩니다. 기존의 Context나 다른 ConcreteStrategy는 전혀 수정할 필요가 없습니다. Spring의 경우 `@Component`로 등록만 하면 DI 컨테이너가 자동으로 리스트에 포함시켜 줍니다. 이것이 OCP가 실제로 코드에 실현되는 방식입니다."

**Q. Strategy Pattern의 단점은?**

> "클래스 수가 증가합니다. 알고리즘 변형이 10개면 10개의 클래스가 생깁니다. 그리고 Context와 전략 사이에 주고받아야 하는 데이터가 많아지면 파라미터 객체가 비대해질 수 있습니다. 또한 전략 패턴은 알고리즘이 런타임에 교체될 때 의미가 있는데, 실제로 교체되지 않는 전략을 패턴으로 설계하면 과잉 설계가 됩니다. 판단 기준은 '이 알고리즘의 변형이 앞으로도 독립적으로 추가/수정될 것인가'입니다."

---

## 체크리스트

- [ ] Strategy 인터페이스를 인식하고, Context가 해당 인터페이스만 의존하도록 설계했는가?
- [ ] `supports()` 또는 `Map` 기반 디스패치로 Context 내부에 분기가 없는가?
- [ ] ConcreteStrategy가 무상태(stateless)인가? (인스턴스 변수로 상태 저장 없음)
- [ ] 각 ConcreteStrategy가 독립적인 단위 테스트로 검증 가능한가?
- [ ] Spring에서 `List<Strategy>` 또는 `Map<String, Strategy>` 주입 패턴을 쓰고 있는가?
- [ ] 새 전략 추가 시 기존 코드(Context, 다른 전략들)를 수정하지 않아도 되는가?
- [ ] 패턴 사용 여부를 결정할 때 "알고리즘 변형의 빈도"와 "독립적 확장 필요성"을 기준으로 판단했는가?
- [ ] Template Method, Chain of Responsibility와 Strategy의 차이를 설명할 수 있는가?
- [ ] 람다/함수형 인터페이스로 표현 가능한 단순 전략과, 클래스 기반 전략이 필요한 복잡한 경우를 구분할 수 있는가?
- [ ] 면접에서 자신의 실무 경험(슬롯 엔진 핸들러 분리 등)을 구체적 사례로 연결할 수 있는가?
