# 스프링 프레임워크

## 1. 스프링 IoC Container

- Bean 정의 메타데이터를 읽어서, 객체 그래프를 구성/관리하는 런타임 인프라
  - new와 같이 직접 인스턴스를 생성하지 않고, 컨테이너에 구성 정보(메타데이터)를 주면, 그 정보를 기반으로 객체를 생성한다.
  - 객체 생성 뿐만 아니라, 의존성을 주입하고, 인스턴스의 라이프사이클을 관리한다
  - 필요하면 AOP, 트랜잭션 같은 부가기능을 끼워 넣는다

### 두 축 : BeanFactory vs ApplicationContext

- BeanFactory

  - 최소 단위 컨테이너
  - 핵심 책임 :
    - Bean 정의를 등록
    - 이름/타입으로 Bean을 조회
    - 필요 시 인스턴스를 생성 (대부분 lazy)
  - 기능적으로 보면 "DI 컨테이너의 최소 기능 세트"
  - 현업에서 `BeanFactory`를 직접 쓸 일은 거의 없고, API 레벨에서 "스펙" 역학을 한다고 보면 됨

- ApplicationContext
  - `BeanFactory`를 상속해서 애플리케이션 레벨 기능을 잔뜩 얹은 것
    - 국제화 메시지
    - 환경 / 프로퍼티
    - 이벤트 퍼블리시 / 리스너
    - 리소스 로딩
    - AOP / 트랜잭션 같은 인프라 결합
    - `@Configuration`, `@ComponentScan`, `@Eanble*`등 자바 기반 구성
  - 실제 애플리케이션에선 항상 `ApplicationContext` 계열을 쓴다고 생각하면 됨

### IoC 컨테이너가 "Bean을 관리한다"는 걸 쪼개 보면

1. 구성 정보 읽기

- `@Configuration` 클래스, `@Bean` 메서드
- `@ComponentScan` 결과
- XML, Groovy, 기타 메타데이터 (요즘은 거의 사용 X)

2. Bean 정의 생성

- 클래스 타입
- 스코프 (singleton, prototype, request, session 등)
- 생성자 / 필드 / 메서드 인젝션 정보
- 초기화 / 소멸 메서드 정보
- 조건 (`@Conditional`), 프로필 (`@Profile`) 등

3. 컨텍스트 refresh

- BeanFactory 생성 및 설정
- BeanFactoryPostProcessor 실행
- BeanPostProcessor 등록
- 싱글톤 Bean 인스턴스화 + 의존성 주입
- 초기화 콜백 호출

4. 런타임 관리

- `getBean()` 처리
- 스코프별 인스턴스 제공
- AOP 프록시 적용된 Bean 제공

5. 컨텍스트 종료

- `DisposableBean`, `@PreDestroy`, `destoryMethod` 호출
- 리소스 정리

### 확장 포인트 : PostProcessor 계열

1. BeanFactoryPostProcessor

- `Bean 정의`를 건드리는 후처리기
- 아직 Bean 인스턴스가 생성되기 전에 실행 됨
- 예시 :
  - PropertySourcesPlaceholderConfigurer : `${...}` 치환
  - ConfigurationClassPostProcessor : `@Configuration`, `@Bean`, `@ComponentScan` 처리해서 BeanDefinition 추가
- 즉, "구성 메타데이터 DSL의 엔진" 역할을 많이 한다고 보면 됨

2. BeanPostProcessor

- Bean 인스턴스를 건드리는 후처리기
- Bean 생성 후, 초기화 전 / 후에 콜백
- 예시 :
  - AOP 프록시 생성
  - `@Autowired` 처리
  - `@Transaction`, `@Async` 등 어노테이션 처리
- 결국, 스프링의 "매직" 대부분이 여기서 터진다고 봐도 무방

스프링이 "단순 DI 컨테이너"를 넘어서 프레임워크가 된 구조가 보인다.
