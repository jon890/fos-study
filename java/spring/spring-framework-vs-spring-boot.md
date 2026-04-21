# [초안] Spring Framework vs Spring Boot: 백엔드 개발자가 진짜 알아야 할 차이

## 왜 이 주제가 중요한가

Java 백엔드 면접에서 "Spring Framework와 Spring Boot의 차이를 설명해보세요"는 거의 빠지지 않는 단골 질문이다. 표면적인 답변은 누구나 할 수 있다. "Boot는 자동 설정해주고, 내장 톰캣이 있고, 스타터 의존성이 있어요." 하지만 이 수준의 답변은 신입 수준에서 멈춘다.

경력직 백엔드 개발자에게 면접관이 진짜 듣고 싶은 것은 다음과 같다. **"당신은 Spring Boot의 추상화 뒤에서 실제로 무슨 일이 일어나는지 이해하고 있는가? Auto-configuration이 언제 실패하고, 왜 실패하고, 그걸 어떻게 디버깅하는가? Boot가 제공하는 기본값을 언제 override해야 하고, 언제 그대로 두어야 하는가?"**

이 문서는 단순히 두 가지를 비교하는 표를 나열하지 않는다. 대신 Spring Framework의 핵심 추상(IoC Container, BeanFactory, ApplicationContext)부터 시작해서 Spring Boot가 그 위에 어떤 레이어를 올렸는지, 그리고 그 레이어가 만들어내는 실전 함정들을 풀어본다. 업무 현장에서 `@ConditionalOnMissingBean` 때문에 Bean 덮어쓰기가 안 되는 문제, Auto-configuration 순서 때문에 Flyway가 JPA 스키마 검증 전에 돌지 않는 문제, `application.yml`의 우선순위 때문에 로컬/스테이징 설정이 섞이는 문제 — 이런 것들이 실제로 면접에서 꼬리질문으로 들어온다.

## 핵심 개념: IoC Container가 전부다

Spring Framework의 본질은 IoC(Inversion of Control) Container다. 이 한 문장을 제대로 이해하면 Boot의 모든 기능이 그 위에 올라간 "편의 레이어"라는 것이 보인다.

### Spring Framework의 구조

Spring Framework는 다음 계층으로 구성된다.

- **Core Container**: `BeanFactory`, `ApplicationContext`, `Environment`, `PropertySource`
- **AOP**: 프록시 기반 횡단 관심사 처리
- **Data Access**: `JdbcTemplate`, 트랜잭션 추상, ORM 통합
- **Web**: `DispatcherServlet`, `@Controller`, `HandlerMapping`
- **Test**: `TestContext`, `@ContextConfiguration`

순수 Spring Framework로 웹 앱을 만들려면 다음을 직접 해야 한다.

1. `web.xml` 또는 `WebApplicationInitializer`로 `DispatcherServlet` 등록
2. `@Configuration` 클래스에서 `DataSource`, `EntityManagerFactory`, `TransactionManager`를 수동 빈 정의
3. 톰캣/제티를 외부에 설치하고 WAR로 배포
4. 로깅(Logback/Log4j2) 설정 파일 직접 작성
5. Jackson, Hibernate, HikariCP 등의 버전 호환성 관리

이 모든 과정이 "모든 선택지를 노출한다"는 장점이면서 동시에 "모든 선택지를 결정해야 한다"는 부담이다.

### Spring Boot가 한 일

Spring Boot는 Spring Framework를 대체하지 않는다. Boot의 내부를 까보면 결국 `AnnotationConfigApplicationContext`를 만들고 `@Configuration` 클래스를 등록하는 동일한 Spring Framework 코드가 돈다. Boot가 추가한 것은 다음 네 가지 축이다.

1. **Auto-configuration**: `spring.factories` / `AutoConfiguration.imports`에 등록된 `@Configuration` 클래스들을 조건부로 활성화
2. **Starter Dependencies**: 의존성 버전 매트릭스를 Bill of Materials(BOM)로 관리
3. **Embedded Server**: `Tomcat`, `Jetty`, `Undertow`를 Jar 안에 포함하여 `java -jar`로 실행
4. **Production-ready Features**: Actuator, Metrics, Health Check

핵심은 **Auto-configuration**이다. 나머지 셋은 비교적 단순한 엔지니어링이지만, Auto-configuration은 "조건부 Bean 등록"이라는 Spring Framework의 기존 기능(`@Conditional`)을 극한까지 활용한 메커니즘이다.

## Auto-configuration 내부 동작

Spring Boot 앱을 시작할 때 `@SpringBootApplication`은 세 가지 어노테이션의 합성이다.

```java
@SpringBootConfiguration
@EnableAutoConfiguration
@ComponentScan
public @interface SpringBootApplication { }
```

이 중 `@EnableAutoConfiguration`이 `AutoConfigurationImportSelector`를 통해 classpath의 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` 파일을 읽는다. (Boot 2.7 이하는 `META-INF/spring.factories`)

이 파일에는 `DataSourceAutoConfiguration`, `JpaRepositoriesAutoConfiguration`, `WebMvcAutoConfiguration` 같은 수백 개의 `@Configuration` 클래스가 나열되어 있다. 각 클래스는 `@Conditional*` 어노테이션으로 보호된다.

```java
@AutoConfiguration
@ConditionalOnClass({ DataSource.class, EmbeddedDatabaseType.class })
@ConditionalOnMissingBean(type = "io.r2dbc.spi.ConnectionFactory")
@EnableConfigurationProperties(DataSourceProperties.class)
public class DataSourceAutoConfiguration {
    // ...
}
```

여기서 조건이 중요하다.

- `@ConditionalOnClass`: classpath에 특정 클래스가 있을 때만 활성화
- `@ConditionalOnMissingBean`: 같은 타입의 Bean이 아직 없을 때만 등록
- `@ConditionalOnProperty`: `application.yml`의 특정 프로퍼티 값에 따라 활성화
- `@ConditionalOnWebApplication`: 웹 환경일 때만 활성화

**경력 개발자가 반드시 이해해야 할 포인트**: `@ConditionalOnMissingBean`은 사용자가 직접 Bean을 정의하면 자동 설정이 비켜주는 구조다. 즉, Boot는 "합리적 기본값"을 제공할 뿐, 사용자가 override하면 그것을 존중한다. 이 철학을 이해하면 "Boot가 내 설정을 덮어쓰는 것 같은데요?"라는 문제의 90%는 Bean 정의 순서와 조건 평가 문제라는 것이 보인다.

## 실전 백엔드에서의 활용

### 상황 1: DataSource를 커스터마이징하고 싶을 때

순수 Spring Framework에서는 `@Bean`으로 `DataSource`를 정의하면 끝이다. Boot에서는 세 가지 선택지가 있다.

**선택지 A: 프로퍼티만 오버라이드**
```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/app
    username: app_user
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 20
      connection-timeout: 3000
```

이 경우 `DataSourceAutoConfiguration`이 HikariCP 기반 `DataSource`를 만들고 위 프로퍼티를 주입한다.

**선택지 B: Bean을 직접 정의**
```java
@Configuration
public class DataSourceConfig {
    @Bean
    @ConfigurationProperties("spring.datasource.hikari")
    public DataSource dataSource() {
        return DataSourceBuilder.create()
            .type(HikariDataSource.class)
            .build();
    }
}
```

이 순간 `@ConditionalOnMissingBean(DataSource.class)` 조건이 false가 되고 Auto-configuration은 물러선다.

**선택지 C: 멀티 DataSource**
두 개 이상의 DB가 필요하면 Auto-configuration을 완전히 벗어나서 수동으로 `@Primary`, `@Qualifier`와 각각의 `EntityManagerFactory`, `TransactionManager`, `LocalContainerEntityManagerFactoryBean`을 정의해야 한다. 이 때 Boot의 스타터는 의존성 번들로만 쓰고 Auto-configuration은 `@SpringBootApplication(exclude = DataSourceAutoConfiguration.class)`로 제외하는 패턴이 흔하다.

면접에서 "멀티 DB를 붙여본 적 있나요?"가 나오면 이 세 번째 선택지를 풀어서 설명할 수 있어야 한다.

### 상황 2: 로깅 레벨을 동적으로 바꾸고 싶을 때

Spring Framework만 쓰면 Logback 설정 파일을 직접 편집하거나 JMX로 건드려야 한다. Boot는 Actuator의 `/loggers` 엔드포인트로 런타임에 레벨을 바꿀 수 있다.

```bash
curl -X POST http://localhost:8080/actuator/loggers/com.example.service \
  -H "Content-Type: application/json" \
  -d '{"configuredLevel": "DEBUG"}'
```

프로덕션 이슈 중간에 특정 패키지의 로그만 DEBUG로 올리고 재배포 없이 문제를 잡는 건 Boot가 주는 실질적 가치다.

## Bad vs Improved 예제

### 예제 1: Bean Override 함정

**Bad**
```java
@Configuration
public class MyConfig {
    @Bean
    public ObjectMapper objectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        return mapper;
    }
}
```

이 코드는 얼핏 잘 작동하는 것처럼 보인다. 하지만 Boot의 `JacksonAutoConfiguration`이 만드는 `ObjectMapper`는 `Jackson2ObjectMapperBuilder`를 거치면서 `spring.jackson.*` 프로퍼티, `FAIL_ON_UNKNOWN_PROPERTIES=false` 같은 기본값, 등록된 모든 `Module` 빈을 자동 적용한다. 위처럼 `new ObjectMapper()`를 직접 만들면 그 모든 기본값이 사라진다.

**Improved**
```java
@Configuration
public class MyConfig {
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer customizer() {
        return builder -> builder
            .serializationInclusion(JsonInclude.Include.NON_NULL)
            .timeZone(TimeZone.getTimeZone("Asia/Seoul"));
    }
}
```

Boot가 제공하는 확장 훅(`Jackson2ObjectMapperBuilderCustomizer`)을 쓰면 기본값을 유지하면서 필요한 부분만 조정할 수 있다. **Boot의 확장 포인트를 쓰는 게 Bean을 통째로 override하는 것보다 거의 항상 낫다.**

### 예제 2: 트랜잭션 경계

**Bad**
```java
@Service
public class OrderService {
    public void placeOrder(OrderRequest req) {
        Order order = orderRepository.save(new Order(req));
        paymentClient.charge(order.getId(), req.getAmount());
        inventoryService.decrement(req.getItems());
    }
}
```

`@Transactional`이 없다. Spring Framework 시절부터 이어진 고전적 실수다. Boot가 JPA 스타터를 통해 `PlatformTransactionManager`를 자동 등록해주지만, 메서드에 `@Transactional`이 붙지 않으면 각 repository 호출이 자체 트랜잭션(또는 autocommit)으로 실행된다.

**Improved**
```java
@Service
public class OrderService {
    @Transactional
    public Order placeOrder(OrderRequest req) {
        Order order = orderRepository.save(new Order(req));
        inventoryService.decrement(req.getItems());
        return order;
    }
}

@Component
public class PaymentOrchestrator {
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onOrderPlaced(OrderPlacedEvent event) {
        paymentClient.charge(event.orderId(), event.amount());
    }
}
```

외부 결제 호출은 DB 트랜잭션 안에서 하면 안 된다. 결제가 느리면 DB 커넥션이 오래 잡히고, 결제가 성공했는데 트랜잭션이 롤백되면 정합성이 깨진다. `@TransactionalEventListener`로 커밋 이후로 밀어내는 패턴이 정석이다. 이건 Boot 기능이 아니라 Spring Framework의 기능이지만, 대부분의 개발자는 Boot 환경에서 처음 만난다.

## 로컬 실습 환경

MySQL 8, JDK 17, Spring Boot 3.2 기준으로 최소 프로젝트를 만들어본다.

```bash
mkdir spring-compare && cd spring-compare
curl https://start.spring.io/starter.zip \
  -d dependencies=web,data-jpa,actuator,mysql \
  -d javaVersion=17 \
  -d bootVersion=3.2.0 \
  -d type=gradle-project \
  -d language=java \
  -o demo.zip
unzip demo.zip
```

MySQL 8 도커 기동:
```bash
docker run -d --name mysql8 \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=demo \
  -p 3306:3306 \
  mysql:8.0
```

`application.yml`:
```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/demo
    username: root
    password: root
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: true

management:
  endpoints:
    web:
      exposure:
        include: health,loggers,beans,conditions
```

## 실행 가능한 예제: Auto-configuration 디버깅

Auto-configuration이 왜 특정 Bean을 만들었는지(또는 왜 안 만들었는지) 확인하는 게 실전 디버깅의 핵심이다.

```bash
./gradlew bootRun
curl http://localhost:8080/actuator/conditions | jq '.contexts.application.positiveMatches.DataSourceAutoConfiguration'
```

응답 예시:
```json
[
  {
    "condition": "OnClassCondition",
    "message": "@ConditionalOnClass found required classes 'javax.sql.DataSource', 'org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType'"
  }
]
```

`negativeMatches`를 확인하면 "왜 이 자동 설정이 건너뛰어졌는가"를 조건 단위로 볼 수 있다. 프로덕션 장애에서 "로컬에선 되는데 스테이징에선 Bean이 없다고 뜨네요"가 나오면 가장 먼저 봐야 할 곳이다.

```bash
curl http://localhost:8080/actuator/beans | jq '.contexts.application.beans | keys | length'
```

등록된 Bean 개수로 컨텍스트 크기를 체감할 수 있다. 빈 프로젝트도 200개 넘게 나온다.

## 면접 답변 프레이밍

**Q: Spring Framework와 Spring Boot의 차이를 설명해주세요.**

> "Spring Boot는 Spring Framework를 대체하는 것이 아니라 그 위에 올라간 opinionated 레이어입니다. Boot 앱을 시작해도 내부적으로는 동일한 `ApplicationContext`와 `BeanFactory`가 도는데, Boot가 추가한 것은 크게 네 가지입니다. 첫째, `@Conditional` 기반 Auto-configuration. 둘째, 의존성 버전을 BOM으로 관리하는 Starter. 셋째, 내장 서블릿 컨테이너. 넷째, Actuator 같은 프로덕션 기능입니다.
>
> 실무 관점에서 가장 큰 차이는 Auto-configuration의 조건부 활성화입니다. 예를 들어 `DataSourceAutoConfiguration`은 `@ConditionalOnMissingBean`으로 보호돼서, 사용자가 직접 `DataSource` Bean을 정의하면 자동 설정이 비켜줍니다. 이 철학 덕분에 기본값을 받으면서도 필요한 부분만 override할 수 있습니다.
>
> 다만 이게 항상 투명하지는 않아서, 저는 프로덕션 이슈에서 `/actuator/conditions` 엔드포인트로 `positiveMatches`, `negativeMatches`를 확인해 어떤 조건이 어떤 순서로 평가됐는지를 보는 방식으로 디버깅합니다."

**Q: Boot 대신 Framework만 써야 할 때가 있을까요?**

> "거의 없습니다. 다만 레거시 WAR 배포 환경, 엄격한 커스텀 컨테이너, 혹은 모든 설정을 명시적으로 통제해야 하는 규제 환경에서는 순수 Framework가 선택지가 됩니다. 그 외에는 Boot의 Auto-configuration을 쓰되 필요한 곳에서 `exclude`로 끄거나 커스터마이저 훅으로 override하는 게 현실적입니다."

**Q: Auto-configuration 때문에 디버깅이 어려웠던 경험이 있나요?**

이 꼬리 질문에는 실제 경험을 풀되, 원인 → 조사 경로(`/actuator/conditions`, 디버그 로그 `--debug`) → 해결(특정 Auto-config 제외 또는 조건 충족) → 회고(Bean override보다 커스터마이저 사용 선호하게 됨) 순으로 구조화한다.

## 체크리스트

- [ ] `@SpringBootApplication`이 합성하는 세 어노테이션을 설명할 수 있다
- [ ] Auto-configuration이 `AutoConfiguration.imports`에서 로드된다는 것을 안다
- [ ] `@ConditionalOnMissingBean`, `@ConditionalOnClass`, `@ConditionalOnProperty`의 차이를 안다
- [ ] `/actuator/conditions`로 positive/negative matches를 확인할 수 있다
- [ ] `ObjectMapper`를 직접 Bean으로 만드는 것과 `Jackson2ObjectMapperBuilderCustomizer`를 쓰는 것의 차이를 설명할 수 있다
- [ ] `@Transactional` 경계 안에 외부 HTTP 호출을 넣으면 안 되는 이유를 안다
- [ ] 멀티 DataSource 환경에서 `DataSourceAutoConfiguration`을 `exclude`하는 이유를 설명할 수 있다
- [ ] `spring.factories`(Boot 2.7-)와 `AutoConfiguration.imports`(Boot 3+)의 위치 차이를 안다
- [ ] `application.yml`의 프로퍼티 우선순위(커맨드라인 > env > profile-specific > default)를 안다
- [ ] Boot의 내장 톰캣이 standalone WAR 배포와 어떻게 다른지 설명할 수 있다
