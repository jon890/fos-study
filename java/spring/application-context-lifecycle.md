# Application Context의 생명주기

- `AbstractApplicationContext.refresh()` 메서드의 흐름과 동일하다.
- 이 과정 중, 단 한 단계라도 예외가 발생하면 리프레시는 중단되며, `has not been refreshed yet` 에러가 발생한다.

## 1. 초기화 단계 (Bootstrap & Refresh)

- **1. 준비 (prepareRefresh)**
  - 컨텍스트의 상태를 'active'로 전환하기 위한 준비 작업을 한다.
  - 시작 시간 기록, 시스템 속성 (Environment) 검증 및 초기화가 일어난다.
  - 아직 빈은 생성되지 않는다.
- **2. BeanFactory 획득 (obtainFreshBeanFactory)**
  - 내부적으로 `DefaultListableBeanFactory`를 생성(또는 갱신)한다.
  - XML, JavaConfig 등 설정 파일로부터 **Bean Definition**(빈 설계도)를 로딩한다.
  - 이 시점에는 "어떤 빈을 만들지"만 알고 있고, 실제 객체는 없다.
- **3. BeanFactory 전처리 (prepareBeanFactory)**
  - BeanFactory에 표준 컨텍스트 구성(ClassLoader, PostProcessor 등)을 설정한다.
  - `ApplicationContextAware` 같은 Aware 인터페이스를 처리할 `BeanPostProcessor`를 등록한다.
- **4. BeanFactory 후처리 (invokeBeanFactoryPostProcessors)**
  - `BeanFactoryPostProcessor`가 실행된다.
  - 빈의 정의(BeanDefinition)을 수정할 수 있는 마지막 방법이다. (프로퍼티 치환, 스코프 변경 등)
- **5. Bean 후처리기 등록 (registerBeanPostProcessors)**
  - 빈 생성 과정에 개입할 `BeanPostProcessor`들을 찾아서 등록한다. (실행은 나중에)
- **6. 메시지 소스 & 이벤트 멀티캐스터 초기화**
  - i18n 처리를 위한 `MessageSource`와 이벤트 발행을 위한 `ApplicationEventMulticaster`를 초기화한다.
- **7. 특정 컨텍스트 초기화 (onRefresh) 🔥**
  - 이 단계는 비어 있는 템플릿 메서드이며, 하위 클래스에서 구현한다.
  - **Spring Boot의 ServletWebServerApplicationContext**의 경우:
    - 이 시점에 내장 톰캣(Tomcat) 같은 웹 서버를 구동한다
    - 포트 충돌이나 서블릿 설정 오류가 있다면 여기서 터지고, 리프레시는 실패한다.
- **8. 리스너 등록 (registerListeners)**
  - `ApplicationListener` 구현체들을 등록한다.
- **9. 싱글 톤 빈 생성 (finishBeanFactoryInitialization) 🔥🔥**
  - 가장 중요한 단계이자 에러의 주범이다.
  - 남아있는 모든 **Non Lazy 싱글톤 빈**을 인스턴스화하고 의존성을 주입(DI)한다.
  - 순서:
    - 인스턴스 생성
    - 의존성 주입
    - Aware 콜백 (setApplicationContext)
    - BeanPostProcessor (Before)
    - `@PostConstruct`
    - BeanPostProcessor (After)
- **10. 리프레시 완료 (finishRefresh)**
  - LifecycleProcessor의 `onRefresh`를 호출한다.
  - `ContextRefreshedEvent` 이벤트를 발행한다.
  - 이 단계까지 에러 없이 도달해야 비로소 컨텍스트가 **완전한 "Refreshed" 상태**가 된다.

## 2. 실행 단계 (Active & Running)

리프레시가 성공적으로 끝나면 컨텍스트는 `Running` 상태가 된다.

- **빈 조회 및 사용**: `getBean()` 요청 시 완성된 빈을 반환한다.
- **이벤트 발행**: `publishEvent()`를 통해 이벤트를 전파한다.
- **웹 요청 처리**: `DispatcherServlet`이 들어오는 요청을 받아 컨트롤러로 라우팅한다.

## 3. 종료 단계 (Destory & Close)

애플리케이션 종료나 테스트 종료 시 `close()`가 호출된다.

- **1. ContextClosedEvent 발행**
  - 종료 이벤트를 알린다
- **2. Lifecycle 빈 종료**
  - `SmartLifecycle` 등의 `stop()` 메서드를 호출한다.
- **3. 싱글톤 빈 파괴**
  - 생성의 역순으로 빈을 제거한다
  - `@PreDestroy` -> `DisposableBean.destroy()` 순으로 실행된다.
- **4. Active 상태 해제**
  - 컨텍스트를 비활성화한다.
