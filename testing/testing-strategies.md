# [초안] 시니어 Java 백엔드를 위한 테스트 전략 완전 정리 — 피라미드부터 TestContainers, JMH, Contract까지

## 1. 왜 테스트 전략이 면접의 핵심 주제가 되는가

"테스트를 잘 짜는가"는 주니어 레벨 질문이지만, "테스트 **전략**을 어떻게 설계하는가"는 시니어 백엔드를 가르는 대표 질문이다. 시니어에게 요구하는 것은 다음 세 가지다.

첫째, **어떤 테스트를 얼마나, 어느 레이어에서 돌릴지 결정**할 수 있어야 한다. 모든 것을 통합 테스트로 붙이면 CI가 15분을 넘어가고, 모든 것을 단위 테스트로만 짜면 서비스 경계에서 터지는 버그를 못 잡는다. 둘째, **flaky test를 제거하는 실질적인 능력**이 있어야 한다. 시니어가 되면 "CI가 가끔 빨갛다"는 문제를 추적해 원인별로 분류하고 팀 관습으로 막아야 한다. 셋째, **테스트를 믿을 수 있도록 기반을 까는 사람**이어야 한다. TestContainers, 트랜잭션 롤백 전략, parallel execution 설정, 공유 상태 봉인 같은 인프라 수준 결정을 내릴 수 있어야 한다.

필자는 실무에서 슬롯 게임 엔진에 **447개의 테스트**를 유지하고, 스핀 엔진 핫패스를 **JMH 마이크로벤치마크로 58배 개선**한 경험이 있다. 또한 팀 차원 테스트 관습을 코드화하기 위해 **Cursor Rules 20종**을 운영해 "PR마다 어떤 테스트가 들어가야 하는가"를 규칙 레벨에서 고정했다. 이 글은 그 경험에서 나온 결정들을 구조화한 것이다.

## 2. 테스트 피라미드: 단위 / 통합 / E2E 비율과 역할 (Spring 관점)

피라미드는 Mike Cohn이 제안한 이후 수십 번 인용된 도형이지만, Spring 백엔드에서는 **4층 구조로 다시 그려야 현실적**이다.

```
                    ┌───────────┐
                    │    E2E    │   ~5%    브라우저/외부 호출 포함
                    └───────────┘
                ┌───────────────────┐
                │  Full Integration │   ~15%  SpringBootTest + TestContainers
                └───────────────────┘
            ┌───────────────────────────┐
            │   Slice / Focused Int.    │   ~30%  @WebMvcTest, @DataJpaTest
            └───────────────────────────┘
        ┌───────────────────────────────────┐
        │            Unit Test              │   ~50%  JUnit5 + Mockito
        └───────────────────────────────────┘
```

- **Unit**: 한 클래스의 로직. 의존성은 mock/stub. 1ms 단위. 서비스 규칙, validator, 도메인 계산, 매퍼가 여기 위치한다.
- **Slice**: Spring의 일부 컨텍스트만 띄운다. `@WebMvcTest`는 컨트롤러+MVC 인프라, `@DataJpaTest`는 JPA 레이어. 200~800ms. 단위로는 검증 불가한 **프레임워크 바인딩**(HTTP 바인딩, JPA 쿼리, JSON 직렬화)을 여기서 잡는다.
- **Full Integration**: `@SpringBootTest` + TestContainers. 실제 MySQL/Redis/Kafka가 뜬다. 결제, 멱등성, 트랜잭션 경계, 락 동작은 여기서만 검증된다. 2~10초.
- **E2E**: 서비스 배포본까지 띄워 API를 외부에서 호출. 선택적.

**비율 가이드**(팀 100명 기준이 아니라 1개 모듈 기준):

- 단위 50% / Slice 30% / 통합 15% / E2E 5% 를 기본값으로 두고
- **돈이 흐르는 도메인**(결제, 지갑, 슬롯 RNG 검증)은 통합 비중을 25~30%까지 올린다.
- CRUD에 가까운 어드민 모듈은 단위 비중을 낮추고 slice 위주로 간다.

필자의 슬롯 엔진(447 테스트) 기준 실제 분포는 단위 58% / slice 22% / 통합 18% / 벤치마크(JMH) 2% 였다. **핫패스는 통합까지 붙여 검증하고, 규칙 계산부는 단위로 빠르게 회전**시키는 원칙이었다.

## 3. Test Doubles: mock / stub / fake / spy / dummy

용어는 Gerard Meszaros의 분류가 표준이다. 시니어 면접에서 섞어 쓰면 감점 요인이다.

| 종류 | 정의 | 예시 | 언제 쓰는가 |
|------|------|------|--------------|
| **Dummy** | 파라미터 자리만 채우는 객체 | `new User(null, null)` | 검증 대상이 해당 인자를 절대 쓰지 않을 때 |
| **Stub** | 정해진 응답을 돌려주는 객체 | `when(repo.find(1L)).thenReturn(u)` | 협력자의 **결과**만 필요할 때 |
| **Spy** | 실제 객체를 감싸 호출을 기록 | `Mockito.spy(realService)` | 기존 구현 대부분은 유지하고 **일부만 엿볼 때** |
| **Mock** | 호출 순서/횟수/인자를 검증 | `verify(repo).save(any())` | **협력자의 호출 자체가 스펙**일 때 |
| **Fake** | 간소화된 **동작하는 대체 구현** | 인메모리 Repository | 실제 인프라가 무거운데 상태 흐름은 검증해야 할 때 |

실전 판단 기준:

- **결과만 필요** → stub
- **어떤 메서드가 호출됐는지가 비즈니스 계약** → mock
- **조회/저장이 반복되는 시나리오 테스트** → fake (인메모리 맵)
- **레거시 거대 클래스 안에서 한 메서드만 가로채야 함** → spy (하지만 spy가 자주 필요하다는 건 설계 냄새다)

슬롯 엔진에서는 RNG(난수 발생기)를 **stub**으로 두어 시나리오별 결정적 스핀 결과를 만들었고, 지갑 어댑터는 **fake**(인메모리 balance Map)로 100개 시나리오를 돌렸으며, "결제 이벤트가 정확히 1회 발행됐는가"는 **mock**으로 검증했다. 같은 도메인 안에서도 더블의 종류가 역할마다 다르다.

## 4. Mockito / spring-boot-test / JUnit5 실전 기법

### 4.1 JUnit 5 구조 고정

```java
@ExtendWith(MockitoExtension.class)
class SpinServiceTest {

    @Mock RngPort rng;
    @Mock WalletPort wallet;
    @InjectMocks SpinService service;

    @Nested
    @DisplayName("잔액이 부족한 경우")
    class InsufficientBalance {

        @Test
        void throws_and_does_not_call_rng() {
            given(wallet.balanceOf(1L)).willReturn(0L);

            assertThatThrownBy(() -> service.spin(1L, 100L))
                .isInstanceOf(InsufficientFundsException.class);

            then(rng).shouldHaveNoInteractions();
        }
    }
}
```

포인트:

- `@Nested`로 "상태 시나리오 → 검증"을 계층화한다. 시니어 리뷰에서 가독성이 달라진다.
- `shouldHaveNoInteractions()`를 통해 **호출하지 않아야 하는 협력자**를 명시한다. 비용이 큰 RNG를 불필요한 경로에서 안 부르는 것도 스펙이다.
- `given / when / then`(BDDMockito)으로 읽히는 테스트를 만든다.

### 4.2 ArgumentCaptor는 최후의 수단

ArgumentCaptor를 쓰는 테스트는 대개 **비즈니스가 객체 내부 상태에 숨어있다**는 신호다. DTO/이벤트 자체가 `equals` 대상이면 captor 없이 `verify(publisher).publish(expectedEvent)`로 끝난다. 값 객체를 만들자.

### 4.3 `@MockBean` 남용 금지

`@SpringBootTest` + `@MockBean`을 남발하면 컨텍스트 캐시가 매번 깨진다. 테스트 실행 시간이 2배가 될 수 있다. **슬라이스 테스트 내부에서 빈 일부를 교체할 때만** `@MockBean`을 쓴다. 그 외에는 `@ExtendWith(MockitoExtension.class)` + 생성자 주입 단위 테스트로 충분하다.

## 5. Spring Slice Tests: 왜 / 언제

| 어노테이션 | 로드되는 빈 | 용도 |
|------------|-------------|------|
| `@WebMvcTest(Controller.class)` | MVC, 지정 컨트롤러, ControllerAdvice, 필터 | HTTP 바인딩, validation, 예외 → HTTP 코드 매핑 |
| `@DataJpaTest` | JPA, EntityManager, (기본) H2 대체 DB | 엔티티 매핑, 쿼리 DSL, 리포지토리 파생 쿼리 |
| `@JsonTest` | Jackson / Gson | 직렬화/역직렬화, `@JsonView`, 날짜 포맷 |
| `@RestClientTest` | `RestTemplate`/`RestClient` + `MockRestServiceServer` | 외부 API 호출부 계약 검증 |

**실전 원칙**: Slice는 "내가 직접 책임지는 어댑터 코드"에만 쓴다. 서비스 로직을 slice에서 검증하려 들면 무의미한 결합이 생긴다.

```java
@WebMvcTest(SpinController.class)
class SpinControllerTest {
    @Autowired MockMvc mvc;
    @MockBean SpinService service;

    @Test
    void bet_over_max_returns_400() throws Exception {
        mvc.perform(post("/api/spin")
                .contentType(APPLICATION_JSON)
                .content("""
                    {"userId":1,"bet":9999999}
                """))
           .andExpect(status().isBadRequest())
           .andExpect(jsonPath("$.code").value("BET_OVER_MAX"));
    }
}
```

`@DataJpaTest`는 **기본이 H2로 대체**된다는 점을 반드시 안다. MySQL 전용 함수(JSON_EXTRACT, 윈도우 함수 일부)를 쓰는 쿼리라면 `@AutoConfigureTestDatabase(replace = Replace.NONE)` + TestContainers로 강제해야 한다.

## 6. TestContainers: 실제 MySQL / Redis / Kafka 통합 테스트

H2로 충분하다는 시대는 끝났다. `utf8mb4`, `JSON` 컬럼, 함수 기반 인덱스, `SELECT ... FOR UPDATE SKIP LOCKED` 같은 MySQL 8 고유 동작을 H2가 에뮬레이트하지 못한다.

### 6.1 기본 패턴

```java
@SpringBootTest
@Testcontainers
class WalletIntegrationTest {

    @Container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0.36")
        .withDatabaseName("wallet")
        .withReuse(true);

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", mysql::getJdbcUrl);
        r.add("spring.datasource.username", mysql::getUsername);
        r.add("spring.datasource.password", mysql::getPassword);
    }
}
```

### 6.2 컨테이너 수명 / 재사용 전략

느리게 쓰는 팀의 전형적 문제는 **클래스마다 컨테이너를 새로 띄우는 것**이다. 세 가지 레벨로 나뉜다.

1. **Per-method** (`@Testcontainers` 필드에 `static` 아님): 가장 느림. 거의 쓰지 않는다.
2. **Per-class** (`static @Container`): 기본 권장.
3. **JVM-wide Singleton**: 추상 기반 클래스에서 `static { container.start(); }`를 돌리고 모든 통합 테스트가 상속한다. CI에서 가장 빠르다.

```java
public abstract class AbstractIntegrationTest {
    static final MySQLContainer<?> MYSQL =
        new MySQLContainer<>("mysql:8.0.36").withReuse(true);
    static {
        MYSQL.start();
    }
    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) { /* ... */ }
}
```

추가로 `~/.testcontainers.properties`에 `testcontainers.reuse.enable=true`를 켜면 **로컬 개발 시 JVM 재시작에도 컨테이너가 살아남는다**. CI에서는 끄는 편이 낫다(격리 때문).

### 6.3 데이터 초기화

- **Flyway/Liquibase**로 스키마를 만들고,
- 테스트 데이터는 `@Sql` 또는 명시적 `testFixture`로 넣고,
- **정리는 트랜잭션 롤백**(`@Transactional` on test) **또는** 테스트 후 `TRUNCATE`.

주의: 멀티스레드/비동기 코드가 트랜잭션 경계를 건너 뛰면 롤백 전략이 깨진다. 이때는 TRUNCATE 전략으로 간다.

## 7. Flaky Test 원인 분류와 대응

447개 테스트를 **flaky 0개**로 유지하려면 원인을 범주화해야 한다.

| 원인 | 증상 | 대응 |
|------|------|------|
| **타이밍/레이스** | `Thread.sleep(100)`이 있음, 느린 머신에서 실패 | `Awaitility.await().atMost(5, SECONDS).until(...)`, CountDownLatch |
| **순서 의존** | 단독 실행은 성공, 함께 돌리면 실패 | 공유 static 상태 제거, `@DirtiesContext`는 최후 수단 |
| **공유 상태** | 이전 테스트의 DB 잔재, 파일 시스템 | 트랜잭션 롤백, per-test TRUNCATE, `@TempDir` |
| **외부 시스템** | 네트워크, 시계, 환경변수, 포트 | WireMock, `Clock` 주입, 랜덤 포트, TestContainers |
| **비결정 입력** | `LocalDateTime.now()`, `UUID.randomUUID()`, RNG | `Clock`/`Supplier<UUID>`/RNG를 포트로 빼서 stub |
| **병렬 실행 충돌** | 같은 컨텍스트에서 서로 쓰는 전역 상태 | `@Execution(SAME_THREAD)` 지정 또는 리소스 락 |

실무에서 가장 흔한 두 가지는 **시계**와 **RNG**다. 둘 다 인터페이스로 추출해 프로덕션에서만 `Clock.systemUTC()`를 바인딩하자.

```java
public interface Clock { Instant now(); }

@Primary @Component
class SystemClock implements Clock {
    public Instant now() { return Instant.now(); }
}
```

## 8. 테스트 독립성 / 병렬 실행 / DB 초기화 전략

### 8.1 병렬 실행 켜기

`src/test/resources/junit-platform.properties`:

```properties
junit.jupiter.execution.parallel.enabled=true
junit.jupiter.execution.parallel.mode.default=concurrent
junit.jupiter.execution.parallel.mode.classes.default=concurrent
junit.jupiter.execution.parallel.config.strategy=fixed
junit.jupiter.execution.parallel.config.fixed.parallelism=4
```

단위 테스트는 거의 그대로 병렬이 돌지만, **통합 테스트는 리소스 락을 걸어야 안전**하다.

```java
@ResourceLock(value = "DB", mode = READ_WRITE)
class PaymentIntegrationTest { ... }
```

### 8.2 DB 초기화 선택

| 전략 | 장점 | 단점 |
|------|------|------|
| `@Transactional` + 롤백 | 빠름, 자동 정리 | 비동기/배치/실제 커밋 필요한 시나리오 불가 |
| 테스트 후 `TRUNCATE` | 모든 시나리오 동작 | 느림, 순서 주의 |
| DB 스냅샷 복원 | 가장 현실적 | 환경 세팅 부담 |

기본은 `@Transactional` 롤백. 결제/락/외부 이벤트 발행은 TRUNCATE로 간다.

## 9. JMH 마이크로벤치마크: 58배 개선 실무

단위 테스트는 **정확성**을, JMH는 **성능**을 검증한다. JUnit 안에서 `System.nanoTime()`으로 돌린 수치는 전부 거짓말이다. JIT warm-up, dead code elimination, on-stack replacement 때문이다.

### 9.1 필수 개념

- **Warm-up**: JIT이 안정화될 때까지 반복.
- **Measurement**: 실제 측정 구간.
- **Mode**: `Throughput`, `AverageTime`, `SampleTime` 등.
- **State scope**: `Benchmark`(공유), `Thread`(스레드별), `Group`.
- **Blackhole**: JIT이 결과를 버리지 못하게 소비.

### 9.2 실전 벤치

```java
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 2)
@Measurement(iterations = 5, time = 3)
@Fork(1)
@State(Scope.Benchmark)
public class SpinEvaluatorBench {

    SpinEvaluator engine;
    Reels reels;

    @Setup public void setup() {
        engine = new SpinEvaluator(RuleBook.load());
        reels  = Reels.fixture();
    }

    @Benchmark
    public SpinResult eval(Blackhole bh) {
        SpinResult r = engine.evaluate(reels, 100L);
        bh.consume(r);
        return r;
    }
}
```

슬롯 엔진 스핀 평가 로직을 JMH로 계측했을 때 **평균 1.73ms → 0.030ms (약 58배)** 개선이 나왔다. 주 원인은 (1) 릴 심볼 매칭을 `List<Symbol>` 선형 탐색에서 사전계산된 `int[]` 비트마스크로 전환, (2) `BigDecimal` 배당 계산을 정밀도 손실 없는 `long` cents 단위로 치환, (3) `stream().filter().count()`를 인덱스 루프로 대체한 것이었다. **측정 없이는 어떤 최적화도 거짓**이다.

### 9.3 JMH 돌릴 때 실수

- 단위 테스트처럼 `./gradlew test`로 같이 돌리지 말 것. 빌드를 분리하고 CI에서 주간/야간으로 돌린다.
- `@Fork(0)`은 디버깅용. 실제 수치는 반드시 `@Fork(>=1)`.
- `System.out.println`을 Benchmark 안에 두면 수치가 망가진다.

## 10. Contract Testing (Pact): 언제 필요한가

마이크로서비스가 3개 이상이고 팀도 분리되면, "B가 쓰는 A의 API 응답 형식이 바뀌었다"는 상황이 반복된다. Contract Test는 **소비자가 원하는 계약을 공급자가 지키는지**를 별도 파이프라인에서 검증한다.

```java
// Consumer 측 (B 서비스)
@PactTestFor(providerName = "wallet-service", port = "0")
class WalletContractTest {

    @Pact(consumer = "game-service")
    public RequestResponsePact balancePact(PactDslWithProvider b) {
        return b.given("user 1 has 10000 balance")
                .uponReceiving("balance query")
                .path("/wallet/1").method("GET")
                .willRespondWith()
                .status(200)
                .body(newJsonBody(o -> {
                    o.numberType("userId", 1);
                    o.numberType("balance", 10000);
                }).build())
                .toPact();
    }
}
```

소비자가 pact 파일을 발행하면 공급자 CI가 해당 계약을 자신의 실제 구현으로 검증한다. E2E를 돌릴 필요 없이 **양 서비스의 CI만으로 호환성이 계약화**된다.

**도입 기준**: (1) 서비스 간 경계를 서로 다른 팀이 소유할 때, (2) 소비자가 2개 이상일 때, (3) E2E 환경을 매번 띄우기가 경제적이지 않을 때. 모놀리식이면 오버엔지니어링이다.

## 11. TDD의 실전 적용 범위와 한계 (시니어 관점)

TDD를 무조건 실천한다는 답은 시니어답지 않다. TDD가 빛나는 구역과 아닌 구역을 구분해 말하는 게 시니어다.

**TDD가 잘 먹히는 곳**

- 도메인 규칙이 명세로 뚜렷한 영역(슬롯 배당 계산, 세율 계산, 권한 검사).
- 리그레션이 치명적인 영역(결제, 지갑).
- 입력/출력이 값으로 정의되는 함수형 코드.

**TDD가 잘 안 먹히는 곳**

- 인프라/프레임워크 학습 구간. 무엇을 짤지 모를 때 테스트를 먼저 쓸 수 없다. 스파이크로 탐색한 뒤 버리고 다시 TDD.
- UI/그래픽, 게임 퍼즐 피드백이 필요한 영역.
- 성능 최적화. 먼저 측정이다(JMH). 테스트로 성능을 검증할 수는 없다.

**Red-Green-Refactor**에서 시니어가 자주 건너뛰는 실수는 Refactor 단계다. 초록불이 들어오면 바로 다음 Red로 가지 말고, **중복과 네이밍을 즉시 정리**한다. Cursor Rules 20종 중 하나는 "Green 직후 중복 제거 없이 다음 테스트로 넘어가는 PR은 리뷰 반려"였다.

## 12. 로컬 실습 환경

```bash
# build.gradle (Kotlin DSL 예시는 생략)
dependencies {
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.testcontainers:junit-jupiter:1.19.7'
    testImplementation 'org.testcontainers:mysql:1.19.7'
    testImplementation 'org.awaitility:awaitility:4.2.1'
    testImplementation 'org.mockito:mockito-junit-jupiter:5.11.0'

    // JMH
    jmh 'org.openjdk.jmh:jmh-core:1.37'
    jmhAnnotationProcessor 'org.openjdk.jmh:jmh-generator-annprocess:1.37'

    // Pact
    testImplementation 'au.com.dius.pact.consumer:junit5:4.6.11'
}
```

```bash
# 로컬에서 한번 찍어보기
./gradlew test --tests "*UnitTest"              # 단위만
./gradlew test --tests "*IntegrationTest"       # 통합
./gradlew jmh                                    # 벤치
```

Docker Desktop 또는 colima/podman이 떠 있어야 TestContainers가 동작한다. CI에서는 Docker-in-Docker 또는 호스트 Docker 소켓 마운트 중 하나를 택한다.

## 13. 면접 답변 프레이밍: "테스트를 어떻게 설계하시나요?"

이 질문은 실은 네 가지를 한꺼번에 묻는다: 피라미드 / 더블 전략 / 인프라 / 문화. 답을 4블록으로 구조화한다.

**1) 레이어 결정**
"저는 먼저 도메인 위험도에 따라 피라미드 비율을 조정합니다. 돈이 흐르는 도메인에서는 통합 비중을 25~30%까지 올리고, CRUD 성격 모듈은 슬라이스 테스트 위주로 갑니다. 슬롯 엔진에서는 447개 테스트를 단위 58% / slice 22% / 통합 18% / JMH 2%로 운영했습니다."

**2) 더블 전략**
"협력자 결과만 필요하면 stub, 호출 자체가 계약이면 mock, 시나리오 흐름이 길면 fake를 씁니다. RNG나 Clock 같은 비결정 요소는 반드시 포트로 추출해 stub 가능하게 만듭니다."

**3) 인프라**
"MySQL 전용 기능을 쓰는 쿼리는 H2가 아니라 TestContainers로 돌려야 하며, JVM-wide Singleton 패턴과 `withReuse(true)`로 CI 시간을 줄입니다. 병렬 실행은 JUnit 5 properties로 켜되 DB는 `@ResourceLock`으로 묶습니다."

**4) 문화**
"팀 차원에서는 Cursor Rules 20종으로 'PR마다 어떤 테스트가 필요한지'를 규칙화해 리뷰 마찰을 없앴습니다. flaky가 생기면 원인을 5가지(타이밍/순서/공유상태/외부/비결정)로 분류해 즉시 티켓을 끊고, 성능 작업은 JUnit이 아니라 JMH에서 검증합니다. 슬롯 엔진 스핀 로직을 JMH 기반으로 58배 개선한 것도 이 원칙의 결과였습니다."

이 네 블록은 서로 물려 있다. 면접관이 "flaky는 어떻게 잡으시나요?"라고 파고들면 2), 3)을 이어 붙이면 된다. "TDD 하시나요?"가 들어오면 11장 내용을 그대로 답한다 — 영역별로 다르다는 대답이 시니어답다.

## 14. 실전 체크리스트

**코드 레벨**
- [ ] 비결정 요소(시계, 랜덤, 외부 호출, 전역 상태)가 전부 포트로 추출돼 있는가
- [ ] test double 종류가 역할에 맞는가 (mock 남용/stub 남용/spy 의존 없는가)
- [ ] `@MockBean`이 남용돼 컨텍스트 캐시를 깨고 있지 않은가
- [ ] `Thread.sleep`이 테스트 코드에 없는가 (`Awaitility` 사용)

**Spring / 인프라**
- [ ] Slice 테스트를 올바른 대상(컨트롤러/JPA/JSON/RestClient)에만 쓰고 있는가
- [ ] MySQL 전용 기능은 TestContainers에서 검증되는가
- [ ] TestContainers가 per-class 또는 JVM singleton으로 재사용되는가
- [ ] 병렬 실행이 켜져 있고 공유 자원에 `@ResourceLock`이 걸려 있는가

**신뢰성**
- [ ] flaky 테스트 발생 시 원인을 5분류 중 하나로 레이블링하는 프로세스가 있는가
- [ ] DB 초기화 전략이 트랜잭션 롤백 또는 TRUNCATE로 명시돼 있는가
- [ ] CI에서 통합 테스트가 단위 테스트와 별도 잡으로 분리돼 있는가

**성능**
- [ ] 성능 주장 전에 JMH로 측정했는가 (JUnit `System.nanoTime` 측정 금지)
- [ ] JMH 벤치가 `@Fork >= 1`, 충분한 warm-up, Blackhole을 쓰는가

**협업**
- [ ] 서비스 경계가 2팀 이상을 가른다면 Contract Test(Pact)를 도입했는가
- [ ] TDD 적용 범위가 팀 합의로 정의돼 있는가 (전부 TDD가 아니라 "어디서")
- [ ] 테스트 관습이 리뷰 규칙(예: Cursor Rules)로 코드화돼 있는가

이 체크리스트를 한 줄씩 답할 수 있으면 시니어 백엔드 테스트 전략 질문은 방어 가능하다. 모든 항목을 **"왜 이렇게 정했는가"**와 함께 설명할 수 있는 수준이 진짜 목표다.
