# @StepScope — Step 실행마다 새로운 빈을 만드는 이유

## @StepScope가 뭔가

Spring의 빈 스코프는 기본이 `singleton`이다. 애플리케이션이 시작될 때 한 번 생성되고, 이후로는 같은 인스턴스를 계속 재사용한다.

Spring Batch에는 `@StepScope`라는 커스텀 스코프가 있다. 이 스코프가 붙은 빈은 **Step이 실행될 때마다 새로운 인스턴스가 생성**된다. Step이 끝나면 인스턴스도 함께 소멸한다.

```java
@Bean
@StepScope
public ConfluencePageItemReader confluencePageItemReader(
    @Value("#{jobParameters['spaceKey']}") String spaceKey
) {
    return new ConfluencePageItemReader(spaceKey, ...);
}
```

## 왜 필요한가

### 1. Job Parameter를 빈 생성 시점에 주입받기 위해

`@StepScope` 없이 싱글톤 빈으로 만들면, 애플리케이션 컨텍스트가 로딩되는 시점에 빈이 생성된다. 이 시점에는 Job Parameter가 아직 없다. `@Value("#{jobParameters['spaceKey']}")`를 쓰면 null이 들어온다.

`@StepScope`를 붙이면 Step이 실제로 실행될 때 빈을 만들기 때문에, 그 시점에 이미 Job Parameter가 확정되어 있어서 값을 주입받을 수 있다.

```
애플리케이션 시작 → Job Parameter 없음 → 싱글톤 빈 생성 → null 주입 ❌

배치 실행 요청 (spaceKey=MY_SPACE) → Step 시작 → @StepScope 빈 생성 → "MY_SPACE" 주입 ✅
```

### 2. Step 실행마다 상태를 초기화하기 위해

Reader, Processor 같은 Step 컴포넌트는 내부 상태를 가지는 경우가 많다. 예를 들어 페이지네이션 커서, 읽은 데이터 버퍼 같은 것들이다.

싱글톤이면 두 번째 Job 실행 시 이전 실행의 상태가 남아있을 수 있다. `@StepScope`로 Step마다 새 인스턴스를 만들면 이런 상태 누수를 원천 차단한다.

### 3. 여러 Job이 동시에 실행될 때 격리하기 위해

Job A와 Job B가 같은 Reader 타입을 쓰는데 싱글톤이라면, 두 Job이 같은 Reader 인스턴스를 공유하게 된다. `@StepScope`를 쓰면 각 Step 실행마다 독립적인 인스턴스가 생기므로 Job 간 간섭이 없다.

## 프록시 방식으로 동작한다

`@StepScope` 빈은 애플리케이션 컨텍스트 로딩 시점에 **프록시 객체**가 먼저 등록된다. 실제 인스턴스는 Step이 시작될 때 프록시가 생성해서 반환한다.

이 때문에 한 가지 주의할 점이 있다. `@StepScope` 빈 클래스가 `final`이면 CGLIB 프록시를 만들 수 없어서 예외가 난다.

```java
// ❌ CGLIB 프록시 생성 불가
@StepScope
public final class ConfluencePageItemReader { ... }

// ✅
@StepScope
public class ConfluencePageItemReader { ... }
```

추상 클래스의 메서드가 `final`인 경우도 마찬가지다. 상속이나 프록시로 오버라이드할 수 없기 때문이다.

## @JobScope도 있다

`@StepScope`와 비슷한 개념으로 `@JobScope`도 있다. Job이 실행될 때마다 새로운 빈을 생성한다. Step 간에 공유해야 하는 상태가 있을 때 Tasklet에 주로 쓴다.

```java
@Bean
@JobScope
public StartIndexingJobTasklet startIndexingJobTasklet(
    @Value("#{jobParameters['physicalIndexName']}") String physicalIndexName
) {
    return new StartIndexingJobTasklet(physicalIndexName, ...);
}
```

## 여러 Job이 같은 타입의 @StepScope 빈을 등록할 때

두 Job Config가 각각 같은 타입의 `@StepScope` 빈을 정의하면 문제가 생긴다.

```
expected single matching bean but found 2:
confluencePageItemEmbeddingProcessor,
planGymConfluencePageItemEmbeddingProcessor
```

Spring이 타입으로 의존성을 찾을 때 어느 것을 써야 할지 몰라서 터진다.

해결 방법은 두 가지다.

**1. 공용 빈은 `@Component @StepScope`로 전역 등록하고 `@Qualifier`로 주입**

```java
// 공용으로 쓰는 빈은 @Component 붙여서 등록
@Component
@StepScope
public class SharedContextRefreshIndexTasklet implements Tasklet { ... }

// 주입할 때 이름으로 찾게 함
@Bean
public Step confluenceIndexRefreshStep(
    @Qualifier("sharedContextRefreshIndexTasklet") SharedContextRefreshIndexTasklet tasklet
) { ... }
```

**2. 잡 전용 빈은 각자 Config에서만 정의하고 `@Qualifier`로 명시 주입**

```java
// ConfluenceIndexingJobConfig에서
@Bean
@StepScope
public ConfluencePageItemEmbeddingProcessor confluencePageItemEmbeddingProcessor(
    DefaultConfluenceDocumentMetadataProvider metadataProvider, ...
) { ... }

// PlanGymConfluenceSpaceIndexingJobConfig에서
@Bean
@StepScope
public ConfluencePageItemEmbeddingProcessor planGymConfluencePageItemEmbeddingProcessor(
    PlanGymConfluenceDocumentMetadataProvider metadataProvider, ...
) { ... }

// Step 정의 시 @Qualifier로 명시
@Bean
public Step confluencePageIndexingStep(
    @Qualifier("confluencePageItemEmbeddingProcessor") ConfluencePageItemEmbeddingProcessor processor, ...
) { ... }
```

**테스트 코드에서도 맞춰줘야 한다**

`@BatchComponentTest`처럼 전체 Spring Context를 띄우는 테스트에서 `@Autowired`로 빈을 주입받을 때도 `@Qualifier`를 붙여야 한다. 빠뜨리면 같은 에러가 난다.

```java
@Autowired
@Qualifier("confluencePageItemEmbeddingProcessor")  // 필수
private ConfluencePageItemEmbeddingProcessor processor;
```

## 정리

| 스코프 | 인스턴스 생성 시점 | 소멸 시점 | 주 용도 |
|---|---|---|---|
| `singleton` (기본) | 애플리케이션 시작 | 애플리케이션 종료 | 상태 없는 공용 서비스 |
| `@JobScope` | Job 시작 | Job 종료 | Job Parameter 주입, Job 수준 공유 상태 |
| `@StepScope` | Step 시작 | Step 종료 | Job Parameter 주입, Step 컴포넌트 상태 격리 |

Reader, Processor, Writer처럼 Step 실행 중 상태를 가지는 컴포넌트, 또는 Job Parameter를 생성 시점에 받아야 하는 컴포넌트라면 `@StepScope`를 붙이는 게 원칙이다.
