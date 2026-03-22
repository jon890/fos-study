# 슬롯 테스트 공통 템플릿 구축

**진행 기간**: 2025.09 ~ 2025.10

---

## 배경

슬롯이 늘어날수록 테스트 코드의 중복이 문제가 됐다.

새 슬롯을 개발할 때마다 테스트 클래스에서 반복되는 코드가 있었다. Spring 컨텍스트 로드, 정적 데이터 초기화, 베팅 정보 세팅, 개인화 데이터 초기화, 트랜잭션 처리... 슬롯별로 이 코드를 각자 구현하다 보니 슬롯마다 방식이 조금씩 달랐고, 한 곳에서 패턴을 바꾸면 다른 슬롯 테스트에서도 똑같이 바꿔야 했다.

공통 부분을 추상 클래스로 뽑아서 슬롯별로 다른 부분만 구현하도록 바꿨다.

---

## 1. AbstractSlotTest — 핵심 추상 클래스

### 구조

```
AbstractSlotTest<T extends SlotExtra>      ← 모든 슬롯 테스트의 기반
├── AbstractSlotStageTest<T>               ← 스테이지 전환 검증 전용
├── AbstractSlotPerformanceTest<T>         ← 성능 테스트 전용
├── AbstractReactiveSimulatorTest<T>       ← 시뮬레이터 API 테스트 전용
├── AbstractMissionParserTest<T>           ← 미션 파싱 테스트 전용
└── [각 슬롯별 구체적 테스트 클래스들]
```

`SlotExtra`는 슬롯별 추가 설정을 담는 타입이다. 제네릭으로 타입 파라미터를 받기 때문에 슬롯별로 `getSlotExtra()`를 호출하면 자동으로 해당 슬롯의 타입으로 반환된다. 런타임 캐스팅 없이 타입 안전하게 쓸 수 있다.

### 추상 메서드 2개

새 슬롯에서 구현해야 하는 건 딱 두 가지다.

```java
// 슬롯 ID
protected abstract String getSlotId();

// 슬롯 Extra 클래스
protected abstract Class<T> getSlotExtraClass();
```

나머지는 전부 템플릿에서 처리한다.

### 공통 기능

```java
// 스핀 파라미터 빌더
protected final SpinResultParameter.SpinResultParameterBuilder buildParameter()

// 스핀 실행
protected final SlotService getSlotService()

// 개인화 데이터 조회
protected final UserPersonalData findUserPersonalData()
protected final Optional<UserGlobalPersonalData> findUserGlobalPersonalData()

// 트랜잭션 실행
protected final void doInTransactionWithoutResult(SimpleFunction testFunction)
```

### 훅 메서드로 확장

기본값을 오버라이드해서 슬롯별 특수 케이스를 처리할 수 있다.

```java
// 커스텀 JSON 파일 사용 (기본값: 표준 파일)
protected SlotGameTestOptions getSlotGameTestOptions()

// 베팅 정보 오버라이드 (기본값: Fixture 기본값)
protected TotalBetInfo getTotalBetInfo()

// 게임 모드 (기본값: INGAME)
protected GameMode getGameMode()
```

예를 들어 최대 배당 제한(MaxPay) 테스트는 별도 JSON 파일을 써야 한다. 이 경우 `getSlotGameTestOptions()`만 오버라이드하면 된다.

```java
// MaxPay 제한 전용 테스트 클래스
class TomeOfMadnessSlotServiceMaxPayTest extends AbstractSlotTest<TomeOfMadnessSlotExtra> {

  private static final SlotGameTestOptions SLOT_GAME_TEST_OPTIONS = SlotGameTestOptions.builder()
      .reelSettingFileName("reel_setting_base_max_pay.json")
      .slotExtraFileName("slot_extra_max_pay.json")
      .build();

  @Override
  protected SlotGameTestOptions getSlotGameTestOptions() {
    return SLOT_GAME_TEST_OPTIONS;
  }
}
```

---

## 2. JUnit5 Extension으로 정적 데이터 세팅

### 문제: DB에 슬롯 데이터가 있어야 테스트가 돌아간다

슬롯 서비스는 실행 시점에 DB에서 슬롯 게임 정보를 로드한다. 테스트 환경에서도 이 데이터가 있어야 하는데, `@BeforeEach`에 넣으면 테스트마다 중복으로 insert가 일어나고, 슬롯마다 작성 방식이 달라지는 문제가 있었다.

JUnit5 Extension을 활용해서 테스트 클래스 단위로 딱 한 번 초기화하도록 구조를 잡았다.

### SlotGameStaticDataLoaderExtension

```java
// 추상 Extension — 슬롯 공통 초기화 로직
public abstract class SlotGameStaticDataLoaderExtension extends GameStaticDataLoaderExtension {

  @Override
  public void configure(EntityManager entityManager, Builder<? super Game> builder) {
    final SlotGame slotGame = slotGame();
    entityManager.persist(slotGame.getTotalBetItem());
    builder.add(slotGame);
  }

  @Override
  public void afterSaved(EntityManager entityManager, Game game) {
    // SlotAliasTable, ExtraAliasTable, SlotExtraAliasTable 자동 생성
    entityManager.persist(SlotAliasTable.builder()...build());
    ExtraAliasConverter.from(slotGame).forEach(entityManager::persist);
    SlotExtraAliasConverter.from(slotGame).forEach(entityManager::persist);
  }

  abstract SlotGame slotGame();  // 슬롯별로 구현
}
```

### 슬롯별 구현체

```java
// 슬롯 하나당 Extension 구현체 하나
public class WantedOutlawsHoldAndSpinSlotGameStaticDataLoaderExtension
    extends SlotGameStaticDataLoaderExtension {

  @Override
  SlotGame slotGame() {
    return new WantedOutlawsHoldAndSpinModelTest().createWithJson(
        WantedOutlawsHoldAndSpinSlotExtra.class
    );
  }
}
```

### 사용

```java
@NscSpringBootTest
@ExtendWith(WantedOutlawsHoldAndSpinSlotGameStaticDataLoaderExtension.class)
class WantedOutlawsHoldAndSpinBaseReelHelperTest
    extends AbstractSlotTest<WantedOutlawsHoldAndSpinSlotExtra> {

  @Override
  protected String getSlotId() {
    return WantedOutlawsHoldAndSpinConstants.defaultSlotId();
  }

  @Override
  protected Class<WantedOutlawsHoldAndSpinSlotExtra> getSlotExtraClass() {
    return WantedOutlawsHoldAndSpinSlotExtra.class;
  }
}
```

Extension에 슬롯 데이터 초기화를 맡기고, 테스트 클래스에는 슬롯 ID와 타입 정보만 선언한다. 슬롯을 추가할 때마다 Extension 구현체 하나, 테스트 클래스 하나를 만들면 된다.

---

## 3. 치트 데이터로 확정적 테스트 작성

슬롯은 확률 기반이라 일반 스핀으로는 특정 결과를 테스트하기 어렵다. 치트 데이터로 특정 심볼이 특정 위치에 나오도록 강제할 수 있다.

```java
@Test
@DisplayName("3번째 릴에 WILD 심볼이 등장하면 카운터에 기록된다")
void givenWildSymbol_thenRecordSymbolPositions() {
  final SpinResultParameter param = buildParameter()
      .feature(Feature.create(getSlotGame(), SlotStageType.BASE))
      .cheatData(TestCheatUtil.createSymbolCheatData(
          getSlotGame(),
          SymbolConstant.WI1.name(),
          1,        // 릴 인덱스
          3 - 1))   // 위치
      .reelCategory(ReelCategory.CHEAT)  // 치트 모드 활성화
      .build();

  final SpinResult result = getSlotService().makeSpinResult(param);

  final int count = result.getCurrentStage().getCounters()
      .getCount(FuForYouConstants.WILD_COUNTER, SymbolConstant.WIL.name());
  assertTrue(count > 0);
}
```

`buildParameter()`가 반환하는 빌더에 `.cheatData()`와 `.reelCategory(ReelCategory.CHEAT)`를 붙이면 된다. 치트 데이터 생성은 `TestCheatUtil`이 담당한다.

---

## 4. 개인화 데이터 테스트

개인화 데이터는 DB에 저장되기 때문에 트랜잭션 안에서 변경하고, 트랜잭션 후에 검증해야 한다.

```java
@Test
@DisplayName("WILD 심볼 등장 시 개인화 데이터의 wildCount가 증가한다")
void givenWildSymbol_thenUpdateGlobalPersonalData() {
  // 트랜잭션 안에서 스핀 실행 (데이터 변경)
  doInTransactionWithoutResult(() -> {
    final SpinResultParameter param = buildParameter()
        .feature(Feature.create(getSlotGame(), SlotStageType.BASE))
        .cheatData(TestCheatUtil.createSymbolCheatData(...))
        .reelCategory(ReelCategory.CHEAT)
        .build();

    getSlotService().makeSpinResult(param);
  });

  // 트랜잭션 종료 후 데이터 검증
  final FuForYouGlobalPersonalData globalData = findUserGlobalPersonalData()
      .map(it -> it.getGlobalPersonalData(FuForYouGlobalPersonalData.class))
      .orElseThrow();

  assertTrue(globalData.getWildCounter() > 0);
}
```

`doInTransactionWithoutResult()`는 `AbstractSlotTest`에서 제공하는 유틸 메서드다. 트랜잭션 커밋 후 개인화 데이터를 `findUserPersonalData()` / `findUserGlobalPersonalData()`로 조회하면 된다.

---

## 5. 특화된 추상 클래스들

### AbstractSlotStageTest — 스테이지 전환 검증

슬롯은 BASE, FREE, LINK 등 여러 스테이지를 거친다. 스테이지 전환이 올바른지 검증하는 테스트를 자동화했다.

```java
class WantedOutlawsHoldAndSpinStageTest
    extends AbstractSlotStageTest<WantedOutlawsHoldAndSpinSlotExtra> {

  @Test
  void testAllStageTransitions() {
    executeStageTestTemplate();  // 모든 스테이지 조합을 자동 검증
  }

  @Override
  protected StageMapper getStageMapper() {
    // 각 스테이지 전환 케이스 정의
    return StageMapper.of(...);
  }
}
```

`executeStageTestTemplate()`이 정의된 모든 스테이지 조합을 순서대로 실행하고 결과를 검증한다.

### AbstractSlotPerformanceTest — 성능 테스트

기본 100만 스핀을 돌려서 각 단계별 처리 시간을 측정한다.

```java
class WantedOutlawsHoldAndSpinPerformanceTest
    extends AbstractSlotPerformanceTest<WantedOutlawsHoldAndSpinSlotExtra> {

  @Test
  void performanceTest() {
    executePerformanceTest();  // 준비, 릴, 후처리, 당첨 계산, 스테이지 처리 단계별 타이밍 측정
  }
}
```

성능 테스트에서는 `GameMode.SIMULATOR`를 기본값으로 쓴다. ThreadLocal 기반 메모리 저장소를 사용해서 Redis I/O 없이 순수 계산 성능만 측정한다.

---

## 6. Fixture — 테스트 데이터 관리

반복해서 쓰는 테스트 데이터는 Fixture 클래스로 분리했다.

**공통 Fixture** (모든 슬롯에서 재사용):
- `FixtureTotalBetInfo.getTotalBetA()` — 베팅 금액 프리셋
- `FixtureAdminAccountInfo.basic()` — 관리자 계정 정보

**슬롯별 Fixture** (특정 슬롯의 복잡한 테스트 시나리오):

```java
// 슬롯 41번 (Bingoing) 전용 — 14가지 릴 결과 시나리오 제공
public class BingoingReelResultFixture {
  public static ReelResult[] createBingoCompletionTestReelResults() { ... }
  public static ReelResult[] createWheelBingoLineTestReelResults() { ... }
  public static ReelResult[] createScatterTestReelResults(int scatterCount) { ... }
  // ...
}
```

빙고 슬롯처럼 특정 보드 상태를 재현해야 하는 경우, 릴 결과를 직접 조작하는 Fixture가 없으면 테스트가 비결정적이 된다. Fixture에서 미리 정의해두면 테스트에서 `createBingoCompletionTestReelResults()`만 호출하면 된다.

---

## 리팩토링: AbstractSlotUnitTest → AbstractSlotTest 통합

원래 `AbstractSlotUnitTest`와 `AbstractSlotTest`가 따로 존재했다. 둘의 차이가 점점 모호해지고 관리 포인트가 늘어서 `AbstractSlotTest` 하나로 통합했다.

통합 과정에서 `SlotStaticDataLoader`를 static 메서드 호출 방식에서 Spring 빈으로 전환했다. static 메서드는 테스트에서 Mocking이 불가능해서 테스트 픽스처 설정에 제약이 있었다. 빈으로 바꾸면서 테스트에서도 원하는 동작으로 대체할 수 있게 됐다.

---

## 배운 것

**테스트 인프라가 생산성을 결정한다.** 새 슬롯을 개발할 때 테스트 클래스를 만드는 데 5분도 안 걸리게 됐다. Extension 하나 만들고 추상 메서드 두 개 구현하면 DB 세팅, 의존성 주입, 초기화 로직이 전부 따라온다.

**제네릭과 템플릿 메서드를 조합하면 중복과 타입 안전성 두 가지를 동시에 잡을 수 있다.** `AbstractSlotTest<T extends SlotExtra>`는 146개 테스트 클래스에서 공통 코드를 제거했고, 동시에 슬롯별 타입 안전성도 유지한다.

**치트 데이터는 슬롯 테스트의 필수 도구다.** 확률 기반 게임을 결정론적으로 테스트하려면 특정 릴 결과를 강제할 수 있는 메커니즘이 반드시 필요하다. `TestCheatUtil`이 없으면 엣지 케이스 테스트를 재현하기가 사실상 불가능하다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JUnit 5 (Extension API, `@ExtendWith`, `@RegisterExtension`)
- Spring Test (`@SpringBootTest`, `TransactionTemplate`)
