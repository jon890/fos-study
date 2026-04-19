# 슬롯 테스트 공통 템플릿 구축

**진행 기간**: 2024.06 ~ 2025.10

---

## 배경

슬롯이 늘어날수록 테스트를 작성하기가 점점 불편해졌다. 새 슬롯에서 테스트를 추가하려면 기존 슬롯에서 반복되는 셋업 코드를 복사해야 했고, 의존성이 바뀌면 슬롯마다 일일이 테스트를 수정해야 했다.

이 과정을 단계별로 개선했다. 단위 테스트에서 출발해서, 통합 테스트로 전환하고, 공통 인프라를 추상화하는 방향으로 진화했다.

---

## 1단계: 단위 테스트의 한계

### 처음 만든 방식 — AbstractSlotUnitTest

초기에는 Spring 없이 순수 Java로 테스트를 돌렸다.

```java
@Deprecated
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public abstract class AbstractSlotUnitTest<T extends SlotExtra> {

  private SlotGame slotGame;

  @BeforeAll
  void setup() {
    // JSON 파일에서 SlotGame 직접 생성
    slotGame = initSlotGame(getSlotGameCreateOptions());
    symbolMap = ...;
    weightInfos = ReelSettingsAliasConverter.from(slotGame);
    ...
  }

  private SlotGame initSlotGame(SlotGameCreateOptions options) {
    final SlotGame slotGame = getModelTest().createWithJson(getSlotExtraClass(), options);

    // id 필드는 private — Reflection으로 강제 주입
    final Field idField = Game.class.getDeclaredField("id");
    idField.setAccessible(true);
    idField.set(slotGame, 9999L);

    return slotGame;
  }
}
```

Spring 컨텍스트 없이 빠르게 실행되는 게 장점이었다. 하지만 슬롯 개발을 진행하면서 문제가 드러났다.

### 문제들

**의존성 변경에 취약하다.**

슬롯 서비스 내부 의존성이 변경될 때마다 Mock 설정을 전부 수정해야 했다. 개발 중에 의존성이 자주 바뀌는 슬롯 개발 특성상 이 비용이 컸다.

```java
// 의존성이 추가될 때마다 Mock 설정 추가
@Mock PersonalDataRepository personalDataRepository;
@Mock ProgressiveJackpotService jackpotService;
@Mock GlobalPersonalDataRepository globalPersonalDataRepository;
// ... 슬롯 의존성이 늘어날수록 Mock 목록도 늘어남
when(jackpotService.getPool(...)).thenReturn(...);
when(personalDataRepository.find(...)).thenReturn(...);
```

**실제 동작과 다를 수 있다.**

잭팟 풀, 개인화 데이터 같은 상태 기반 의존성을 Mock으로 대체하면 테스트는 통과하는데 실제 환경에서 다르게 동작하는 케이스가 생겼다. 특히 잭팟 당첨 조건, 개인화 데이터 초기화 순서 같은 부분이 그랬다.

**Reflection이 남용됐다.**

`id` 필드를 강제 주입하기 위해 Reflection을 쓰는 게 불안정했다. 클래스 구조가 바뀌면 테스트가 이유 없이 깨졌다.

결국 클래스에 `@Deprecated`를 붙이고 TODO를 남겼다.

```java
// todo(kbt): AbstractSlotTest + SlotGameStaticDataLoader를 활용하여,
//            스프링 환경에서 테스트를 진행하자.
@Deprecated
public abstract class AbstractSlotUnitTest<T extends SlotExtra> { ... }
```

---

## 2단계: 통합 테스트로 전환

### AbstractSlotTest — Spring 컨텍스트 안에서

Spring 컨텍스트를 올리고, 실제 빈을 주입받는 방식으로 바꿨다.

```java
@NscSpringBootTest  // @SpringBootTest + application-it.properties
public abstract class AbstractSlotTest<T extends SlotExtra> {

  @Autowired SlotStaticDataLoaderImpl slotStaticDataLoader;
  @Autowired SlotServiceFactory slotServiceFactory;
  @Autowired PersonalDataRepositoryFactory personalDataRepositoryFactory;
  @Autowired GlobalPersonalDataRepositoryFactory globalPersonalDataRepositoryFactory;
  @Autowired ProgressiveJackpotServiceFactory jackpotServiceFactory;
  @Autowired TransactionTemplate transactionTemplate;

  @BeforeEach
  void setup() {
    performAdditionalSetup(); // 잭팟, 개인화 데이터 초기화
  }

  // 슬롯별로 구현할 메서드 2개
  protected abstract String getSlotId();
  protected abstract Class<T> getSlotExtraClass();
}
```

의존성을 Mock으로 관리하던 코드가 전부 사라졌다. 슬롯 서비스 내부 의존성이 바뀌어도 테스트를 수정할 필요가 없다. Spring이 알아서 주입한다.

이 변경의 핵심 이유를 커밋 메시지에 그대로 남겼다.

> "SlotUnitTest로 관리 시, 빈 의존관계 설정 등이 곤란함. 더 나은 방법으로 변경."

### 잭팟과 개인화 데이터를 @BeforeEach에서

통합 테스트 전환 후 새로운 과제가 생겼다. 잭팟 풀과 개인화 데이터는 DB 상태에 의존하기 때문에, 테스트마다 초기 상태를 보장해야 한다.

```java
@BeforeEach
void setup() {
  if (requiresProgressiveJackpot()) {
    initializeProgressiveJackpotPool(getSlotGame());
  }
  if (requiresPersonalService()) {
    initializePersonalData(getSlotGame());
  }
  if (requiresGlobalPersonalService()) {
    initializeGlobalPersonalData(getSlotGame());
  }
  performAdditionalSetup(); // 슬롯별 추가 초기화
}
```

`requiresProgressiveJackpot()`은 슬롯 데이터를 보고 자동으로 판단한다. 대부분의 슬롯에서 오버라이드 없이 그대로 쓸 수 있다.

---

## 3단계: 정적 데이터 초기화 문제

### 슬롯 데이터를 DB에 넣어야 테스트가 돌아간다

슬롯 서비스는 시작 시 DB에서 슬롯 게임 정보를 로드한다. 테스트 환경에서도 이 데이터가 있어야 한다.

처음에는 각 테스트 클래스에서 직접 insert 로직을 작성했다. 슬롯마다 작성 방식이 달라지고, 슬롯 데이터 구조가 바뀔 때마다 여러 테스트 클래스를 수정해야 했다.

### GameStaticDataLoaderExtension

JUnit5 Extension으로 분리해서 테스트 클래스와 데이터 초기화 로직을 완전히 분리했다.

```java
// 추상 Extension — 공통 초기화 로직 (AliasTable, ExtraAliasTable 포함)
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
    ExtraAliasConverter.from((SlotGame) game).forEach(entityManager::persist);
    SlotExtraAliasConverter.from((SlotGame) game).forEach(entityManager::persist);
  }

  abstract SlotGame slotGame(); // 슬롯별 구현
}

// 슬롯별 구현체 — slotGame() 하나만 구현
public class LinkGameSlotStaticDataLoaderExtension
    extends SlotGameStaticDataLoaderExtension {

  @Override
  SlotGame slotGame() {
    return new LinkGameSlotModelTest().createWithJson(
        LinkGameSlotExtra.class
    );
  }
}
```

테스트 클래스에서는 `@ExtendWith`로 선언만 하면 된다.

```java
@NscSpringBootTest
@ExtendWith(LinkGameSlotStaticDataLoaderExtension.class)
class LinkGameBaseReelHelperTest
    extends AbstractSlotTest<LinkGameSlotExtra> {

  @Override protected String getSlotId() { return ...; }
  @Override protected Class<...> getSlotExtraClass() { return ...; }
}
```

새 슬롯을 추가할 때 Extension 구현체 하나, 테스트 클래스 하나를 만들면 된다. 데이터 초기화 방식을 몰라도 된다.

### SlotStaticDataLoader static 메서드 제거

Extension 도입 이전에는 `SlotStaticDataLoader.getSlotProduct()`를 static으로 호출하는 테스트가 있었다.

```java
// 이전 방식: static 호출 — Mocking 불가능
SlotGame game = SlotStaticDataLoader.getSlotProduct(slotId);

// 변경 후: Spring 빈 주입 — 테스트에서 동작 대체 가능
@Autowired SlotStaticDataLoaderImpl slotStaticDataLoader;
SlotGame game = slotStaticDataLoader.getSlotProduct(slotId);
```

static 메서드는 Mockito로 교체할 수 없다. 특수한 설정값으로 슬롯을 로드해야 하는 테스트(MaxPay 제한 테스트 등)에서 막혔다. 빈으로 전환한 뒤 `@RegisterExtension`과 커스텀 `SlotGameTestOptions`로 원하는 JSON 파일을 지정할 수 있게 됐다.

---

## 4단계: 특화 추상 클래스 분리

통합 테스트가 안정되면서 용도별로 추상 클래스를 분리했다.

### AbstractSlotPerformanceTest

100만 스핀을 돌려서 단계별 처리 시간을 측정한다.

```java
public abstract class AbstractSlotPerformanceTest<T extends SlotExtra>
    extends AbstractSlotTest<T> {

  protected int getSpinCount() { return 1_000_000; }

  // 성능 테스트는 메모리 기반 저장소 사용 (Redis I/O 제거)
  @Override
  protected GameMode getGameMode() { return GameMode.SIMULATOR; }

  protected final void executePerformanceTest() {
    // prepare / reel / post / win / process / stage 단계별 나노초 측정
  }
}
```

슬롯 서비스가 100만 스핀 기준으로 어느 단계에서 시간이 걸리는지 파악할 수 있다.

### AbstractSlotStageTest

스테이지 전환(BASE → FREE → BASE 등)을 자동으로 검증한다.

```java
public abstract class AbstractSlotStageTest<T extends SlotExtra>
    extends AbstractSlotTest<T> {

  protected final void executeStageTestTemplate() {
    // 정의된 모든 스테이지 전환 조합을 순서대로 실행
    // MultiKeyMap으로 검증 완료 상태 추적
  }

  protected abstract StageMapper getStageMapper();
}
```

`StageMapper`에 전환 케이스를 정의하고 `executeStageTestTemplate()`을 호출하면 된다. 케이스를 빠뜨리면 테스트에서 잡힌다.

### AbstractMissionParserTest

미션 파싱 결과를 선택적으로 검증하는 헬퍼를 제공한다.

```java
// 보너스, 바이피처, 잭팟 조건을 선택적으로 검증
SlotMissionDataTestParam.create(
    expectedBonus: true,
    expectedBuyFeature: null,  // 검증 안 함
    expectedJackpot: false
).assertEquals(missionData);
```

---

## 치트 데이터: 확률 게임을 확정적으로 테스트하기

통합 테스트 전환 후 남은 문제가 있었다. 슬롯은 확률 기반이라 특정 심볼이 특정 위치에 나오는 케이스를 재현하기 어렵다.

치트 데이터로 릴 결과를 강제 지정하는 방식으로 해결했다.

```java
@Test
@DisplayName("3번째 릴에 WILD 심볼이 등장하면 카운터에 기록된다")
void givenWildSymbol_thenRecordInCounters() {
  final SpinResultParameter param = buildParameter()
      .feature(Feature.create(getSlotGame(), SlotStageType.BASE))
      .cheatData(TestCheatUtil.createSymbolCheatData(
          getSlotGame(), SymbolConstant.WI1.name(), 1, 2))
      .reelCategory(ReelCategory.CHEAT)
      .build();

  final SpinResult result = getSlotService().makeSpinResult(param);

  assertTrue(result.getCurrentStage().getCounters()
      .getCount(WILD_COUNTER, SymbolConstant.WIL.name()) > 0);
}
```

치트 데이터가 없으면 "와일드 심볼이 등장했을 때" 케이스를 테스트하려면 수백 번 스핀을 돌려야 할 수도 있다. 치트 데이터로 해당 케이스를 확정적으로 재현하면 테스트가 항상 동일하게 통과한다.

개인화 데이터 변경을 검증할 때는 트랜잭션 경계를 명시적으로 관리했다.

```java
@Test
void givenWildSymbol_thenGlobalPersonalDataUpdated() {
  // 트랜잭션 내에서 스핀 (DB 상태 변경)
  doInTransactionWithoutResult(() ->
      getSlotService().makeSpinResult(buildParameter()
          .cheatData(...)
          .reelCategory(ReelCategory.CHEAT)
          .build())
  );

  // 트랜잭션 종료 후 결과 검증
  final FuForYouGlobalPersonalData data = findUserGlobalPersonalData()
      .map(it -> it.getGlobalPersonalData(FuForYouGlobalPersonalData.class))
      .orElseThrow();
  assertTrue(data.getWildCounter() > 0);
}
```

---

## 결과

단위 테스트 방식에서는 슬롯별로 Mock 의존성 설정 코드가 테스트마다 달랐고, 서비스 레이어 전체를 테스트하기 어려웠다.

통합 테스트 전환 이후:

- **새 슬롯 테스트 작성 시간 단축**: Extension 구현체 하나, 추상 메서드 두 개 구현이 전부다. DB 초기화, 잭팟 풀, 개인화 데이터 준비는 템플릿이 처리한다.
- **의존성 변경에 강해졌다**: 슬롯 서비스 내부 의존성이 바뀌어도 테스트 코드를 수정할 필요가 없다. 이전에는 의존성 하나 추가되면 해당 슬롯 테스트 클래스에서 Mock 설정을 추가해야 했다.
- **커버리지 범위 확대**: 단위 테스트로는 Mock을 통한 서비스 메서드 단위 검증만 가능했다. 통합 테스트로 전환 후 잭팟 당첨 조건, 개인화 데이터 업데이트, 스테이지 전환 등 실제 DB 상태와 연동된 케이스까지 커버할 수 있게 됐다.
- **AbstractSlotUnitTest 완전 삭제**: 레거시 코드를 정리하고 `AbstractSlotTest` 하나로 통일했다.

---

## 배운 것

**단위 테스트가 항상 정답은 아니다.** 도메인 의존성이 복잡하고 자주 변경되는 상황에서는 Mock 관리 비용이 통합 테스트의 속도 손실보다 클 수 있다. 슬롯 서비스처럼 상태 기반 의존성(잭팟 풀, 개인화 데이터)이 많은 경우에는 실제 빈을 쓰는 통합 테스트가 더 신뢰할 수 있는 결과를 준다.

**테스트 인프라도 추상화 대상이다.** 슬롯별로 중복되던 셋업 코드를 추상 클래스와 Extension으로 뽑아내면서 새 슬롯 테스트 작성 비용이 크게 줄었다. 테스트 코드도 프로덕션 코드와 같은 기준으로 설계해야 한다.

**static 메서드는 테스트의 적이다.** `SlotStaticDataLoader.getSlotProduct()`를 static으로 쓰던 시절에는 특정 설정을 주입하는 테스트를 작성할 수 없었다. 빈으로 전환하고 나서야 커스텀 JSON 파일을 사용하는 테스트가 가능해졌다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JUnit 5 (Extension API, `@ExtendWith`, `@RegisterExtension`)
- Spring Test (`@SpringBootTest`, `TransactionTemplate`)
