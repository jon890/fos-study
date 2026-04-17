# [초안] Strategy Pattern — 백엔드 설계의 핵심, 조건 분기를 전략으로 바꾸는 법

## 왜 이 패턴이 중요한가

코드를 오래 운영하다 보면 반드시 마주치는 장면이 있다. `if (type.equals("KAKAO")) { ... } else if (type.equals("NAVER")) { ... } else if (type.equals("PAYCO")) { ... }`. 처음에는 두 개였다. 다음 분기에 하나 더 붙었다. 반년 뒤에 그 메서드는 200줄짜리 조건 덩어리가 되어 있고, 아무도 건드리고 싶어하지 않는다.

Strategy Pattern은 이 문제를 "조건"이 아닌 "교체 가능한 행동"으로 다루는 설계다. 인터페이스 하나로 행동을 추상화하고, 각 구현체가 자신의 전략을 캡슐화한다. 호출부는 어떤 전략인지 알 필요 없이 그냥 실행만 한다.

백엔드 실무에서 이 패턴이 등장하는 지점은 정해져 있다. 결제 수단, 할인 정책, 알림 채널, 파싱 포맷, 외부 API 연동 방식. 공통적으로 "같은 입력에 대해 처리 방법이 달라지는" 지점이다. 면접에서는 이 패턴을 단순히 "OCP를 지키는 방법"으로 소개하는 사람이 많다. 그러나 시니어 레벨에서 기대하는 답변은 한 단계 더 들어간다. 언제 쓰고, 언제 쓰지 말고, 테스트 관점에서 어떤 이점이 있는지, 그리고 실제로 코드가 어떻게 바뀌는지까지 설명할 수 있어야 한다.

---

## 핵심 개념 — 패턴의 구조와 의도

GoF(Gang of Four)가 정의한 Strategy Pattern의 의도는 다음과 같다.

> "알고리즘 군을 정의하고, 각각을 캡슐화하여 교환 가능하게 만든다. 전략 패턴을 사용하면 알고리즘을 사용하는 클라이언트와 독립적으로 알고리즘을 변경할 수 있다."

구조는 세 요소로 이루어진다.

1. **Strategy 인터페이스**: 모든 전략이 따르는 계약. 메서드 시그니처를 통일한다.
2. **ConcreteStrategy**: 실제 알고리즘을 구현하는 클래스들.
3. **Context**: Strategy를 주입받아 사용하는 객체. 어떤 ConcreteStrategy인지 모른다.

UML보다 코드로 보는 편이 직관적이다.

```java
// Strategy 인터페이스
public interface DiscountPolicy {
    int calculate(int originalPrice);
}

// ConcreteStrategy A
public class FixedAmountDiscount implements DiscountPolicy {
    private final int discountAmount;

    public FixedAmountDiscount(int discountAmount) {
        this.discountAmount = discountAmount;
    }

    @Override
    public int calculate(int originalPrice) {
        return Math.max(0, originalPrice - discountAmount);
    }
}

// ConcreteStrategy B
public class RateDiscount implements DiscountPolicy {
    private final double discountRate;

    public RateDiscount(double discountRate) {
        this.discountRate = discountRate;
    }

    @Override
    public int calculate(int originalPrice) {
        return (int) (originalPrice * (1 - discountRate));
    }
}

// Context
public class Order {
    private final DiscountPolicy discountPolicy;

    public Order(DiscountPolicy discountPolicy) {
        this.discountPolicy = discountPolicy;
    }

    public int finalPrice(int originalPrice) {
        return discountPolicy.calculate(originalPrice);
    }
}
```

`Order`는 `DiscountPolicy`가 고정 금액인지 비율인지 알지 못한다. 호출부는 전략을 주입할 뿐이다.

---

## 어떤 문제를 해결하는가 — if-else 분기와의 결정적 차이

단순 조건 분기와 전략 패턴의 차이는 **변경의 파급 범위**에 있다.

### 조건 분기 방식 (나쁜 예)

```java
public class PaymentService {

    public void pay(String method, int amount) {
        if ("KAKAO_PAY".equals(method)) {
            // 카카오페이 API 호출
            KakaoPayClient client = new KakaoPayClient();
            client.requestPayment(amount);
        } else if ("NAVER_PAY".equals(method)) {
            // 네이버페이 API 호출
            NaverPayClient client = new NaverPayClient();
            client.charge(amount, NaverPayOptions.DEFAULT);
        } else if ("TOSS".equals(method)) {
            // 토스 API 호출
            TossPaymentApi api = new TossPaymentApi(API_KEY);
            api.execute(amount);
        } else {
            throw new IllegalArgumentException("Unknown payment method: " + method);
        }
    }
}
```

이 코드의 문제점은 다음과 같다.

- **새 결제 수단 추가 = `PaymentService` 수정 필요**. 서비스 클래스가 계속 커진다.
- **단위 테스트가 어렵다**. 특정 수단만 테스트하려 해도 `PaymentService` 전체를 인스턴스화해야 한다.
- **의존성이 숨어 있다**. `KakaoPayClient`, `NaverPayClient`, `TossPaymentApi`가 메서드 내부에서 직접 생성된다. 목(Mock) 교체 불가.
- **OCP 위반**. 확장 시 기존 클래스를 수정해야 한다.

### 전략 패턴 방식 (개선된 예)

```java
// 전략 인터페이스
public interface PaymentStrategy {
    void pay(int amount);
}

// 각 구현체
@Component("KAKAO_PAY")
public class KakaoPayStrategy implements PaymentStrategy {
    private final KakaoPayClient client;

    public KakaoPayStrategy(KakaoPayClient client) {
        this.client = client;
    }

    @Override
    public void pay(int amount) {
        client.requestPayment(amount);
    }
}

@Component("NAVER_PAY")
public class NaverPayStrategy implements PaymentStrategy {
    private final NaverPayClient client;

    public NaverPayStrategy(NaverPayClient client) {
        this.client = client;
    }

    @Override
    public void pay(int amount) {
        client.charge(amount, NaverPayOptions.DEFAULT);
    }
}

// Context
@Service
public class PaymentService {
    private final Map<String, PaymentStrategy> strategies;

    public PaymentService(Map<String, PaymentStrategy> strategies) {
        this.strategies = strategies;
    }

    public void pay(String method, int amount) {
        PaymentStrategy strategy = strategies.get(method);
        if (strategy == null) {
            throw new IllegalArgumentException("Unknown payment method: " + method);
        }
        strategy.pay(amount);
    }
}
```

Spring에서 `Map<String, PaymentStrategy>`에 Bean 이름을 키로 주입받는 방식은 실무에서 가장 많이 쓰이는 패턴이다. 새로운 결제 수단이 생기면 구현체 하나를 `@Component("NEW_METHOD")`로 등록하기만 하면 된다. `PaymentService`는 건드리지 않는다.

---

## 실무 백엔드 적용 사례

### 1. 알림 채널 전략

```java
public interface NotificationStrategy {
    void send(String recipient, String message);
}

@Component("EMAIL")
public class EmailNotificationStrategy implements NotificationStrategy {
    @Override
    public void send(String recipient, String message) {
        // JavaMailSender 사용
    }
}

@Component("SMS")
public class SmsNotificationStrategy implements NotificationStrategy {
    @Override
    public void send(String recipient, String message) {
        // SMS API 호출
    }
}

@Component("PUSH")
public class PushNotificationStrategy implements NotificationStrategy {
    @Override
    public void send(String recipient, String message) {
        // FCM 호출
    }
}
```

사용자 설정에 따라 `EMAIL`, `SMS`, `PUSH` 중 하나를 선택하는 로직이 서비스 레이어에 들어올 때, 전략 패턴으로 분리하면 각 채널을 독립적으로 테스트하고 관리할 수 있다.

### 2. 파일 파싱 전략

외부 파트너사마다 주문 파일 포맷이 다른 경우가 있다. CSV, Excel, JSON, XML. 이때 파서를 전략으로 분리한다.

```java
public interface OrderFileParser {
    List<OrderDto> parse(InputStream inputStream);
}

@Component("CSV")
public class CsvOrderParser implements OrderFileParser { ... }

@Component("EXCEL")
public class ExcelOrderParser implements OrderFileParser { ... }

@Component("JSON")
public class JsonOrderParser implements OrderFileParser { ... }
```

파일 포맷 코드를 요청 파라미터로 받아 전략을 선택한다. 새 파트너사가 XML 형식을 요구하면 `XmlOrderParser`만 추가하면 된다.

### 3. 슬롯 엔진 / 핸들러 분리 패턴

슬롯 머신처럼 게임 엔진이나 이벤트 처리 시스템을 설계할 때, 각 이벤트 타입(예: `SPIN`, `BONUS`, `FREE_GAME`)에 대한 처리 로직이 다를 수 있다. 이때 핸들러를 전략으로 등록하면 새로운 이벤트 타입 추가 시 엔진 코어 로직을 건드리지 않는다.

```java
public interface GameEventHandler {
    GameResult handle(GameContext context);
    GameEventType supportedType();
}

@Component
public class SpinHandler implements GameEventHandler {
    @Override
    public GameResult handle(GameContext context) {
        // 릴 스핀 로직
    }

    @Override
    public GameEventType supportedType() {
        return GameEventType.SPIN;
    }
}

// 엔진 코어
@Service
public class SlotEngine {
    private final Map<GameEventType, GameEventHandler> handlers;

    public SlotEngine(List<GameEventHandler> handlerList) {
        this.handlers = handlerList.stream()
            .collect(Collectors.toMap(
                GameEventHandler::supportedType,
                Function.identity()
            ));
    }

    public GameResult process(GameEventType type, GameContext context) {
        return Optional.ofNullable(handlers.get(type))
            .orElseThrow(() -> new UnsupportedEventException(type))
            .handle(context);
    }
}
```

`List<GameEventHandler>`를 주입받아 직접 맵을 구성하는 방식은 Bean 이름이 아닌 도메인 타입을 키로 쓸 때 유용하다.

---

## 테스트 가능성 — 전략 패턴이 주는 가장 큰 실용 이점

전략 패턴이 if-else보다 나은 이유를 "OCP 때문에"라고만 말하면 부족하다. 실무에서 가장 체감되는 이점은 **테스트 격리**다.

```java
@Test
void 고정금액_할인이_올바르게_적용된다() {
    DiscountPolicy policy = new FixedAmountDiscount(1000);
    Order order = new Order(policy);

    int result = order.finalPrice(5000);

    assertThat(result).isEqualTo(4000);
}

@Test
void 비율_할인이_올바르게_적용된다() {
    DiscountPolicy policy = new RateDiscount(0.1);
    Order order = new Order(policy);

    int result = order.finalPrice(10000);

    assertThat(result).isEqualTo(9000);
}
```

각 전략을 독립적으로 테스트할 수 있다. `Order`를 테스트할 때는 Mock `DiscountPolicy`를 주입한다.

```java
@Test
void Order는_전략에_위임한다() {
    DiscountPolicy mockPolicy = mock(DiscountPolicy.class);
    when(mockPolicy.calculate(5000)).thenReturn(4500);

    Order order = new Order(mockPolicy);
    int result = order.finalPrice(5000);

    assertThat(result).isEqualTo(4500);
    verify(mockPolicy).calculate(5000);
}
```

if-else 방식이었다면 `PaymentService` 하나에 세 개의 외부 클라이언트가 결합되어 있어, 한 수단만 테스트하기 위해 나머지 두 개를 어떻게든 초기화해야 한다.

---

## 자주 저지르는 실수 패턴

### 실수 1: 전략이 너무 많은 상태를 받는다

```java
// 나쁜 예 — 전략이 전체 주문 도메인 객체를 알아야 한다
public interface DiscountPolicy {
    int calculate(Order order, User user, Coupon coupon, LocalDateTime now);
}
```

전략의 시그니처에 너무 많은 파라미터가 들어가면 전략끼리 결합도가 높아지고 테스트가 어렵다. 필요한 값만 계산해서 넘기거나, 가벼운 DTO를 따로 만들어라.

```java
// 개선된 예
public interface DiscountPolicy {
    int calculate(DiscountContext context);
}

public record DiscountContext(int originalPrice, MemberGrade grade, boolean hasCoupon) {}
```

### 실수 2: 전략 선택 로직이 다시 거대해진다

전략을 만들어 놓고, 어떤 전략을 고를지 결정하는 `StrategySelector`에 if-else가 그대로 쌓이는 경우가 있다.

```java
// 나쁜 예 — 선택 로직이 다시 복잡해짐
public PaymentStrategy select(String method) {
    if ("KAKAO".equals(method)) return kakaoPayStrategy;
    else if ("NAVER".equals(method)) return naverPayStrategy;
    else if ("TOSS".equals(method)) return tossStrategy;
    ...
}
```

Spring의 Bean 이름 기반 Map 주입, 또는 각 전략이 자신이 지원하는 조건을 직접 알고 있는 `supports()` 메서드 방식으로 해결한다.

```java
public interface PaymentStrategy {
    void pay(int amount);
    boolean supports(String method);
}

@Service
public class PaymentStrategyResolver {
    private final List<PaymentStrategy> strategies;

    public PaymentStrategyResolver(List<PaymentStrategy> strategies) {
        this.strategies = strategies;
    }

    public PaymentStrategy resolve(String method) {
        return strategies.stream()
            .filter(s -> s.supports(method))
            .findFirst()
            .orElseThrow(() -> new IllegalArgumentException("Unknown: " + method));
    }
}
```

### 실수 3: 전략을 stateful하게 만든다

Spring Bean은 기본이 싱글톤이다. 전략 구현체를 Bean으로 등록할 때 상태를 필드로 가지면 동시 요청 시 데이터가 섞인다.

```java
// 위험한 예 — 상태를 필드로 갖는 전략 Bean
@Component
public class KakaoPayStrategy implements PaymentStrategy {
    private int lastAmount; // 위험!

    @Override
    public void pay(int amount) {
        this.lastAmount = amount; // 스레드 불안전
        ...
    }
}
```

전략 구현체는 가능한 한 **무상태(stateless)**로 만들어야 한다. 필요한 상태는 메서드 파라미터로 전달하라.

### 실수 4: 2개짜리 분기에 전략 패턴을 강요한다

전략이 단 2개이고 앞으로도 늘어날 가능성이 없다면, 인터페이스와 구현체 3개를 만드는 것은 오버엔지니어링이다. boolean 파라미터나 enum 분기가 더 읽기 쉽다. 패턴은 목적이 아니라 도구다.

---

## 언제 쓰고 언제 쓰지 않는가

| 상황 | 판단 |
|---|---|
| 분기 타입이 3개 이상이고 앞으로 늘어날 것이 확실 | 전략 패턴 적용 |
| 각 분기의 처리 로직이 독립적으로 테스트되어야 함 | 전략 패턴 적용 |
| 분기 처리 로직이 5줄 이하이고 추가될 여지가 없음 | 단순 조건 분기 유지 |
| 분기가 2개이며 boolean 의미가 명확 | 단순 if-else |
| 전략이 런타임에 교체되어야 함 (사용자 설정 기반) | 전략 패턴 적용 |
| 분기 로직이 상태를 공유해야 함 | 전략보다 Template Method 고려 |

---

## 로컬 실습 환경 구성

Java 17 + Spring Boot 3.x 환경에서 다음과 같이 바로 실습할 수 있다.

```bash
# Spring Initializr로 프로젝트 생성
# Dependencies: Spring Web, Lombok

mkdir strategy-pattern-lab && cd strategy-pattern-lab
```

### 실습 시나리오: 할인 정책 교체

```java
// 1. 인터페이스 정의
public interface DiscountPolicy {
    int apply(int price);
    String name();
}

// 2. 구현체 3개
@Component
public class NoDiscount implements DiscountPolicy {
    public int apply(int price) { return price; }
    public String name() { return "NO_DISCOUNT"; }
}

@Component
public class SummerSaleDiscount implements DiscountPolicy {
    public int apply(int price) { return (int)(price * 0.8); }
    public String name() { return "SUMMER_SALE"; }
}

@Component
public class VipDiscount implements DiscountPolicy {
    public int apply(int price) { return (int)(price * 0.7); }
    public String name() { return "VIP"; }
}

// 3. Resolver
@Service
public class DiscountPolicyResolver {
    private final Map<String, DiscountPolicy> policyMap;

    public DiscountPolicyResolver(List<DiscountPolicy> policies) {
        this.policyMap = policies.stream()
            .collect(Collectors.toMap(DiscountPolicy::name, Function.identity()));
    }

    public DiscountPolicy resolve(String name) {
        return Optional.ofNullable(policyMap.get(name))
            .orElseThrow(() -> new IllegalArgumentException("정책 없음: " + name));
    }
}

// 4. REST 엔드포인트로 확인
@RestController
@RequestMapping("/discount")
public class DiscountController {
    private final DiscountPolicyResolver resolver;

    public DiscountController(DiscountPolicyResolver resolver) {
        this.resolver = resolver;
    }

    @GetMapping
    public int calculate(@RequestParam String policy, @RequestParam int price) {
        return resolver.resolve(policy).apply(price);
    }
}
```

```bash
# 실행 후 테스트
curl "http://localhost:8080/discount?policy=SUMMER_SALE&price=10000"
# 응답: 8000

curl "http://localhost:8080/discount?policy=VIP&price=10000"
# 응답: 7000
```

새로운 정책이 필요하면 `DiscountPolicy`를 구현하는 클래스를 `@Component`로 등록하기만 하면 된다. `DiscountController`도 `DiscountPolicyResolver`도 수정이 필요 없다.

---

## 면접 답변 프레이밍 — 시니어 레벨 기대치

### Q. 전략 패턴을 실무에서 적용한 사례를 설명해보세요.

**나쁜 답변**: "결제 수단마다 다른 로직이 필요해서 인터페이스를 만들고 각 구현체에 분리했습니다. OCP 원칙을 지킬 수 있었습니다."

**좋은 답변 구조**:
1. **문제 상황 먼저**: "서비스에 결제 수단이 3개였는데 서비스 레이어에 if-else가 쌓이면서 단위 테스트 커버리지가 특정 수단만 검증되고, 신규 수단 추가 시 기존 코드 회귀 위험이 있었습니다."
2. **선택 이유**: "전략 패턴을 선택한 이유는 각 수단의 클라이언트 초기화 방식이 달라 Mock을 주입해서 격리 테스트를 하려면 구조가 필요했기 때문입니다."
3. **구체적 구조**: "Spring Map 주입으로 Bean 이름을 키로 전략을 등록했고, 서비스는 Map에서 꺼내서 실행만 합니다."
4. **트레이드오프**: "전략이 적을 때는 오버헤드가 있습니다. 2개 이하일 때는 단순 조건이 오히려 읽기 쉽습니다. 저희는 초기부터 5개 이상을 예상했기 때문에 선택했습니다."

### Q. 전략 패턴과 팩토리 패턴의 차이가 무엇인가요?

팩토리 패턴은 **객체 생성** 책임을 분리한다. 어떤 객체를 만들지 캡슐화하는 것이다. 전략 패턴은 **행동**을 교체 가능하게 만든다. 두 패턴이 함께 쓰이는 경우가 많다. 팩토리가 전략 구현체를 생성해서 반환하고, Context가 그것을 실행하는 구조다.

### Q. 전략이 많아지면 어떻게 관리하나요?

실무에서 전략이 10개가 넘으면 관리 비용이 생긴다. 몇 가지 접근이 있다.
- **패키지 분리**: `payment/strategy/` 하위에 모아서 탐색 비용을 줄인다.
- **인터페이스에 메타데이터 추가**: `supports()` 메서드로 선택 로직을 전략 내부에 둔다.
- **문서화**: 어떤 전략이 어떤 조건에서 활성화되는지 명세를 남긴다. 신규 입사자가 전략 추가 시 기존 전략과 충돌하지 않도록.

---

## 체크리스트

- [ ] Strategy 인터페이스는 단일 행동 메서드를 갖는가?
- [ ] ConcreteStrategy는 무상태(stateless)인가? Spring Bean으로 안전한가?
- [ ] Context는 특정 ConcreteStrategy를 직접 참조하지 않는가?
- [ ] 전략 선택 로직이 다시 if-else 덩어리가 되지 않았는가?
- [ ] 각 전략을 독립적으로 단위 테스트했는가?
- [ ] 새로운 전략 추가 시 기존 클래스를 수정하지 않아도 되는가?
- [ ] 전략이 2개 이하이고 변경 가능성이 없는 경우, 단순 조건을 선택했는가?
- [ ] 전략 파라미터가 도메인 전체 객체가 아닌 필요한 값만 받는가?
- [ ] 면접에서 문제 상황 → 선택 이유 → 구조 → 트레이드오프 순서로 설명할 수 있는가?
