# 슬롯 페이 조건 체크 — Factory + 런타임 타입 해석

**진행 기간**: 슬롯 엔진 추상화 작업과 병행 (2025 하반기)

슬롯 게임은 "당첨 판정" 로직이 슬롯 타입(Payline, Way 등)에 따라 근본적으로 다르다. 가로줄 기준으로 판정하는 Payline 슬롯과, 릴 조합 경로 수로 판정하는 Way 슬롯(예: 243웨이, 1024웨이)은 파라미터 구조·반환 구조·내부 알고리즘이 전부 다르다.

이걸 처음엔 하나의 서비스 안에서 `SlotType` 분기로 처리했는데, 슬롯 타입이 늘어날수록 분기 서비스가 비대해지고, 타입별 전용 파라미터가 서로 섞이면서 제네릭 표현이 어긋나기 시작했다. 결국 **"런타임에 슬롯 타입을 보고 적절한 체커를 골라서 실행"**하는 구조로 바꿨다.

---

## 설계 목표

슬롯 팀에서 정리한 요구 사항은 세 가지다.

- 새 슬롯 타입이 추가될 때 기존 페이 서비스 코드를 건드리지 않는다
- 각 체커가 자기 타입 전용 파라미터·반환 타입을 가진다(타입 안전)
- 상위 서비스(당첨 계산)는 체커 구현 디테일을 알지 않는다

이 세 요구를 `SlotPayConditionChecker<P, I>` 인터페이스 + `SlotPayConditionCheckerFactory`로 풀었다.

---

## 핵심 인터페이스

```java
public interface SlotPayConditionChecker<P extends PayConditionCheckParam,
                                         I extends PayableItem> {

  SlotType paymentType();                       // 이 체커가 담당하는 타입

  P createParam(PostSpinData postSpinData);     // 타입 전용 파라미터 생성

  List<PayConditionResult<I>> check(P param);   // 타입 전용 판정
}
```

제네릭 `<P, I>`가 핵심이다. Payline 구현체는 `SlotPayConditionChecker<PaylineConditionCheckParam, PaylinePayableItem>`이고, Way 구현체는 `SlotPayConditionChecker<WayConditionCheckParam, WayPayableItem>`이다. 각자 자기 타입에 맞는 파라미터 구조와 `PayableItem` 하위 타입을 가진다.

구현체는 전부 `@Component`로 등록된다.

```java
@Component
public class PaylineConditionChecker
    implements SlotPayConditionChecker<PaylineConditionCheckParam, PaylinePayableItem> {

  @Override public SlotType paymentType() { return SlotType.PAYLINE; }
  // ...
}

@Component
public class WayConditionChecker
    implements SlotPayConditionChecker<WayConditionCheckParam, WayPayableItem> {

  @Override public SlotType paymentType() { return SlotType.WAY; }
  // ...
}
```

---

## Factory — 생성자에서 맵을 구성한다

여기서 자주 보는 실수는 Factory 내부에 `switch(slotType)`로 분기하거나, `ApplicationContext`를 주입받아 `getBean()`을 호출하는 것이다. 둘 다 스프링의 **DI 자동 수집**을 제대로 활용하지 못한 구조다.

실제 구현은 이렇다.

```java
@Component
public class SlotPayConditionCheckerFactory {

  private final Map<SlotType, SlotPayConditionChecker<?, ?>> checkerMap;

  public SlotPayConditionCheckerFactory(List<SlotPayConditionChecker<?, ?>> checkers) {
    this.checkerMap = new HashMap<>();
    checkers.forEach(checker -> checkerMap.put(checker.paymentType(), checker));
  }

  public SlotPayConditionChecker<?, ?> getChecker(SlotType slotType) {
    final SlotPayConditionChecker<?, ?> checker = checkerMap.get(slotType);
    if (checker == null) {
      throw new IllegalArgumentException("해당 슬롯 타입에 대한 체커가 없습니다: " + slotType);
    }
    return checker;
  }
}
```

Spring은 `List<SlotPayConditionChecker<?, ?>>` 타입 파라미터를 보고, 컨테이너에 등록된 모든 `SlotPayConditionChecker` 구현체를 수집해 넣어준다. Factory는 생성자에서 한 번만 `Map<SlotType, Checker>`를 만들고 이후엔 **O(1) 조회**만 한다.

**새 슬롯 타입을 추가할 때** — 예를 들어 'Cluster' 타입을 도입한다면 — 다음 두 가지만 하면 된다.

1. `SlotType.CLUSTER` enum 값 추가
2. `ClusterConditionChecker implements SlotPayConditionChecker<ClusterConditionCheckParam, ClusterPayableItem>` 구현체 작성 + `@Component`

Factory 코드, 서비스 코드, 기존 체커 코드 어느 것도 손대지 않는다. 이게 실무에서 **OCP(Open-Closed Principle)가 체감되는 순간**이다.

---

## 호출부 — AbstractWinService의 3단계 조립

상위 서비스에서 실제로 체커를 사용하는 흐름은 아래처럼 짧다.

```java
public abstract class AbstractWinService implements WinService {

  private final SlotPayConditionCheckerFactory checkerFactory;

  public final List<WinResult> checkPayCondition(PostSpinData postSpinData) {
    // 1. Factory에서 타입에 맞는 체커 조회
    final SlotPayConditionChecker<?, ?> checker =
        checkerFactory.getChecker(postSpinData.getSlot().getSlotType());

    // 2. 타입 캐스팅 — 내부에서 한 번만
    @SuppressWarnings("unchecked")
    final SlotPayConditionChecker<PayConditionCheckParam, PayableItem> typedChecker =
        (SlotPayConditionChecker<PayConditionCheckParam, PayableItem>) checker;

    // 3. 파라미터 생성 → 판정 실행
    final PayConditionCheckParam param = typedChecker.createParam(postSpinData);
    final List<PayConditionResult<PayableItem>> results = typedChecker.check(param);

    return results.stream().flatMap(r -> /* 데코레이터 체인 적용 */ ).toList();
  }
}
```

`@SuppressWarnings("unchecked")`가 걸린 타입 캐스팅이 한 줄 있다. 이건 구조적으로 피할 수 없는 지점이다 — 제네릭 `<P, I>`의 파라미터화된 타입 정보는 런타임에 소거되기 때문에, "타입으로 골라낸 체커"의 파라미터 타입을 컴파일러에게 증명할 방법이 없다. 대신 계약상 `paymentType()`과 `createParam()`/`check()`의 실제 타입이 같은 구현체 안에 묶여 있으므로 런타임에 안전하다.

**호출부는 "어떤 슬롯 타입이든 상관없이" 같은 시그니처로 다 처리된다.** 이게 Factory 패턴으로 얻은 최종 이득이다.

---

## Strategy vs Factory — 왜 여기선 Factory 조립이 먼저였나

이 구조를 처음 만들 때 고민한 지점이다. `SlotPayConditionChecker`는 인터페이스 + 여러 구현체라 전형적인 **Strategy Pattern**이지만, 이 글의 제목을 "Factory"로 단 이유는 **체커 선택 로직을 명시적인 Factory 객체로 분리**했기 때문이다.

- Strategy만 쓴다면 — 호출부가 직접 `List<Checker>`를 받아 필터링(`filter(c -> c.paymentType() == x)`)한다. 컬렉션 순회가 매 스핀마다 반복된다
- Factory를 두면 — 생성자에서 Map을 한 번 만들어두고 이후엔 O(1). 호출부는 Factory에만 의존

둘은 배타적이지 않다. "Strategy 패턴을 쓸 때 전략 선택 책임을 어디에 둘 것인가"가 Factory의 역할이다. 이 구조에서 Factory는 **"런타임 타입 디스패치"**를 전담한다.

---

## 회고

- **제네릭 체커 + Map Factory**는 슬롯 타입이 3개를 넘어가면 압도적으로 깔끔해진다. 2개 이하면 `if-else`가 더 단순할 수도 있다. 실제로 초기엔 `if-else`였고, Way 타입이 들어올 즈음 리팩터링했다
- `@SuppressWarnings("unchecked")` 한 줄을 쓰는 게 불편했지만, 이게 Java 제네릭 타입 소거(type erasure)의 구조적 한계라는 걸 받아들이는 게 먼저였다. 대신 캐스팅을 Factory 외부 레이어에 퍼뜨리지 않고 호출부 한 군데에서만 하도록 범위를 좁혔다
- Spring의 **`List<Interface>` 자동 수집**은 이 패턴의 핵심 인프라다. 이걸 안 써도 구현은 가능하지만(`ApplicationContext.getBeansOfType()`), 의존성 방향이 컨테이너 내부로 흐트러진다. 생성자 주입이 가장 깔끔하다

---

## 관련 문서

- [Strategy Pattern](../../architecture/strategy-pattern.md) — 인터페이스 + 구현체 + 런타임 교체의 기본 개념
- [슬롯 엔진 추상화](./slot-engine-abstraction.md) — `SlotTemplate`/`BaseSlotService`와 이 Factory가 결합되는 상위 구조
- [슬롯 당첨 계산 데코레이터 체인](./slot-win-decorator-chain.md) — Factory로 고른 체커의 결과를 다시 Decorator로 장식하는 후속 단계
