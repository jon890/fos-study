# InitializingBean 이란?

- `InitializingBean`은 Spring Framework의 **빈 생명주기(Bean LifeCycle)** 인터페이스 중 하나
- 빈의 프로퍼티 설정 (Dependency Injection)이 완료된 후, 추가적인 초기화 작업이 필요할 떄 사용하도록 설계 되었음

```java
public interface InitializingBean {
    void afterPropertiesSet() throws Exception;
}
```

## 동작 타이밍

Spring Bean이 생성될 때의 순서를 보면 이 인터페이스의 위치가 명확해짐

1. Bean 인스턴스 생성 (생성자 호출)
2. 의존성 주입 (Setter 또는 필드 주입)
3. BeanNameAware / BeanFactoryAware 등 Aware 인터페이스 처리
4. BeanPostProcessor의 `postProcessBeforeInitialization` 실행 (여기서 `@PostConstruct`가 처리됨)
5. InitializingBean의 `afterPropertiesSet()` 실행
6. Custom `init-method` 실행 (`@Bean(initMethod = "")`)
7. BeanPostProcessor의 `postProcessAfterInitiailzation` 실행

## 특징과 주의 사항

장점 : 명시적인 초기화 보장

- 필수적인 프로퍼티가 제대로 설정되었는지 검증하거나, 빈이 사용되기 전 커넥션 풀 초기화, 캐시 로딩 등의 작업을 수행하기에 적합

단점 : 프레임워크 종속성

- Spring에 강하게 결합 : 코드에 Spring 인터페이스가 직접 노출됨
  - 이는 POJO 지향 원칙에 어긋남
  - 최근의 비즈니스 로직 개발에서는 지양하는 편
- 더 나은 대안
  - Java 표준인 `PostConstruct`를 사용하면 Spring 종속성을 줄이면서 동일한 효과를 낼 수 있음
