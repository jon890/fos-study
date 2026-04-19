# 슬롯 당첨 계산 — Decorator 체인 + 우선순위 정렬

**진행 기간**: 슬롯 엔진 추상화 작업과 병행 (2025 하반기)

슬롯의 "당첨 금액 계산"은 단순해 보이지만, 실제론 여러 단계의 조합이다. 기본 배당, 프리게임 배수, 프로그레시브 보너스, 멀티플라이어 심볼, 구매 기능(BuyFeature)으로 얻은 추가 배수 등이 층층이 쌓인다.

이걸 하나의 `calculateWin()` 메서드 안에 분기로 넣기 시작하면, 슬롯 타입별·이벤트별·프로모션별로 특수 케이스가 추가될 때마다 if문이 폭발한다. 결국 **"당첨 아이템을 원본 → 장식된 형태로 변환하는 단계"를 하나씩 체인으로 묶는** 구조로 바꿨다. Decorator Pattern의 실제 구현이다.

---

## 왜 Decorator인가

처음 후보는 세 가지였다.

1. **분기 기반** — `if (isFreeGame) amount *= multiplier; if (hasBonus) ...` — 가장 익숙하지만 가장 빨리 망가짐
2. **전략 패턴 한 번 더** — `WinCalculator` 인터페이스 + 구현체들. 그런데 "여러 계산을 순차 적용"이 본질이라 단일 선택이 아닌 **순서 있는 조합**이 필요했다
3. **Decorator 체인** — 각 단계가 `PayableItem → PayableItem` 변환 함수. 순서대로 적용하면 누적

본질이 "누적 장식"이었으므로 Decorator가 구조적으로 맞았다.

---

## 인터페이스 설계

Decorator는 네 가지 메서드를 가진다.

```java
public interface PayableItemDecorator<C extends DecoratorContext> {

  // 1. 핵심 변환: PayableItem → PayableItem
  PayableItem decorate(PayableItem payableItem, C context);

  // 2. 이 데코레이터가 현재 상황에 적용 가능한가?
  default boolean isApplicable(C context) { return true; }

  // 3. 체인에서의 실행 순서 (낮을수록 먼저)
  default int getPriority() { return 0; }

  // 4. PostSpinData에서 자기 타입의 컨텍스트를 뽑아내는 책임
  C createContext(PostSpinData postSpinData);
}
```

몇 가지 설계 결정이 숨어 있다.

**컨텍스트 타입을 제네릭화**(`<C extends DecoratorContext>`). 프리게임 배수 데코레이터는 `FreeMultiplierDecoratorContext`(프리게임 여부, 배수 테이블)를 받고, 다른 데코레이터는 자기만의 컨텍스트를 받는다. "모든 데코레이터가 같은 거대한 컨텍스트를 공유"하지 않는다.

**컨텍스트 생성 책임을 데코레이터에게**. 상위 서비스가 "어떤 컨텍스트가 필요한지" 알 필요가 없다. 데코레이터 자신이 `PostSpinData`에서 필요한 것만 추출한다. Law of Demeter를 지키는 방식이다.

**우선순위는 숫자**. 이게 정답은 아니다. "데이터 플로우 그래프" 같은 정교한 순서 표현도 가능하지만, 슬롯 당첨 계산은 선형이라 숫자가 충분했다.

---

## 구체 데코레이터 예시: 프리게임 배수

가장 대표적인 구현체가 `FreeGameMultiplierDecorator`다.

```java
public class FreeGameMultiplierDecorator
    implements PayableItemDecorator<FreeMultiplierDecoratorContext> {

  private final Function<PostSpinData, Integer> multiplierTransformStrategy;

  @Override
  public PayableItem decorate(PayableItem payableItem, FreeMultiplierDecoratorContext context) {
    if (!isApplicable(context)) return payableItem;

    final long originalWinAmount = payableItem.getWinAmount();
    final long multipliedWinAmount =
        originalWinAmount * multiplierTransformStrategy.apply(context.getPostSpinData());

    return payableItem.withWinAmount(multipliedWinAmount);
  }

  @Override
  public boolean isApplicable(FreeMultiplierDecoratorContext context) {
    return context.isFreeGame();
  }

  @Override
  public int getPriority() {
    return 100; // 프리게임 배수는 기본 처리이므로 이른 단계
  }

  @Override
  public FreeMultiplierDecoratorContext createContext(PostSpinData postSpinData) {
    return FreeMultiplierDecoratorContext.create(postSpinData);
  }
}
```

주목할 세 가지.

- **Strategy를 Decorator 안에 품었다**. `multiplierTransformStrategy`는 `Function<PostSpinData, Integer>`로 주입된다. 슬롯마다 배수 계산식이 다르므로 **Decorator + Strategy 조합**이다
- **`withWinAmount()` — 불변 객체로 변환**. 데코레이터는 원본을 변경하지 않고 새 객체를 반환한다. Kotlin의 copy처럼 Java의 builder 또는 `with...` 메서드로 구현
- **`isApplicable()`로 조기 종료**. 프리게임이 아닌 일반 스핀에서는 체인에 포함돼 있어도 아무 변환도 하지 않는다. 체인 자체를 동적으로 재구성하지 않아도 된다

---

## 체인 실행 — `AbstractWinService.applyDecorators()`

데코레이터를 실제로 적용하는 코드는 여기다.

```java
@SuppressWarnings({"rawtypes", "unchecked"})
private PayableItem applyDecorators(PayableItem payableItem, PostSpinData postSpinData) {
  PayableItem result = payableItem;

  // 1. 우선순위 순 정렬
  final List<PayableItemDecorator<?>> sortedDecorators =
      payableItemDecorators().stream()
                             .sorted(Comparator.comparingInt(PayableItemDecorator::getPriority))
                             .toList();

  // 2. 순차 적용
  for (final PayableItemDecorator decorator : sortedDecorators) {
    final DecoratorContext context = decorator.createContext(postSpinData);
    result = decorator.decorate(result, context);
  }

  return result;
}

protected abstract List<PayableItemDecorator<?>> payableItemDecorators();
```

포인트:

- **데코레이터 목록을 하위 슬롯 서비스가 제공한다**(`payableItemDecorators()` 추상 메서드). 슬롯별로 적용할 데코레이터 집합을 다르게 구성할 수 있다. A 슬롯은 프리게임 배수만, B 슬롯은 배수 + 프로그레시브 + 멀티플라이어 심볼 식으로 조립
- **정렬은 매 호출마다 하지만 비용은 무시 가능**. 데코레이터 개수가 한 자릿수라 O(n log n)이 체감되지 않는다. 필요하면 `@PostConstruct`에서 미리 정렬해둘 수도 있다
- **raw type 캐스팅**. 제네릭 `<C>`가 여러 타입을 가진 데코레이터들을 한 리스트에 담는 대가다. 각 데코레이터가 자기 타입의 컨텍스트만 만들어 쓰므로 런타임에 안전하다

`checkPayCondition()`에서 이 `applyDecorators()`를 각 `PayableItem`마다 호출한다.

```java
return results.stream()
              .flatMap(result -> {
                final List<PayableItem> decoratedItems =
                    result.getPayableItems().stream()
                          .map(payableItem -> applyDecorators(payableItem, postSpinData))
                          .toList();
                return decoratedItems.stream().map(PayableItem::toWinResult);
              })
              .toList();
```

---

## 회고

**얻은 것**

- 새 당첨 계산 규칙(예: "럭키 시간대 10% 보너스 이벤트")이 들어오면 **데코레이터 하나 추가 + 해당 슬롯의 `payableItemDecorators()` 리스트에 등록**만 하면 된다. 기존 데코레이터·서비스 코드 미수정
- 단위 테스트가 쉬워졌다. 각 데코레이터는 순수 함수에 가까워서 `decorate(item, context)` 한 번 호출하고 결과 검증만 하면 된다

**고민한 지점**

- **데코레이터 순서 결정**이 매번 논의 포인트다. 프리게임 배수가 먼저인지, 멀티플라이어 심볼이 먼저인지에 따라 결과 금액이 달라지기도 한다. 이건 도메인(기획)이 정해야 하는데, 숫자 우선순위가 그 의사결정을 코드에 고정하는 역할
- **`@SuppressWarnings("unchecked")`**. Factory 패턴 때도 똑같이 마주친 문제. Java 제네릭 한계라 수용하되, 캐스팅 범위를 최소화하는 것만 지켰다

**다음 숙제**

- 데코레이터 간 "이 데코레이터가 이미 적용됐는가"를 알아야 하는 상황이 생기면 현재 구조만으론 부족하다. 그 시점엔 Chain of Responsibility에 가까운 변형이 필요할 것. 아직 그런 요구는 없어서 지금은 선형 체인으로 충분

---

## 관련 문서

- [Decorator & Chain of Responsibility 패턴](../../architecture/decorator-chain-of-responsibility.md) — 개념 정리와 비교
- [슬롯 엔진 추상화](./slot-engine-abstraction.md) — `AbstractWinService`를 포함한 상위 템플릿 구조
- [슬롯 페이 조건 체크 Factory](./slot-payment-factory.md) — 이 데코레이터 체인이 장식하는 `PayableItem`의 출처
