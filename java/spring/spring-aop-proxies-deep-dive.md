# [초안] Spring AOP와 프록시 심층 분석: JDK Dynamic Proxy, CGLIB, ByteBuddy까지

## 1. 왜 이 주제가 중요한가

Spring으로 실무를 하다 보면 `@Transactional`이 걸린 메서드가 이상하게 동작하지 않거나, `@Async`를 붙였는데 같은 스레드에서 실행되거나, `@Cacheable`이 캐시를 태우지 않고 무한히 원본 메서드를 호출하는 상황을 만나게 된다. 대부분의 원인은 코드가 아니라 **프록시(proxy) 메커니즘**에 있다. Spring의 트랜잭션, 비동기, 캐시, 시큐리티, 아키텍처 레벨의 모든 "AOP 스러운 마법"은 예외 없이 프록시 위에서 돌아간다.

시니어 백엔드 개발자에게 "Spring AOP가 내부적으로 어떻게 동작하나요?"라는 질문은 단순히 `@Aspect` 문법을 아는지 묻는 질문이 아니다. 이 질문은 다음을 확인하려는 질문이다.

- 런타임에 프록시가 어떻게 만들어지고 끼어드는지 이해하는가
- JDK Dynamic Proxy와 CGLIB, AspectJ의 차이를 설명할 수 있는가
- self-invocation, final 메서드, private 메서드, 생성자 내부 호출 같은 함정을 겪어봤는가
- 성능·디버깅·테스트 관점에서 프록시의 비용을 알고 있는가

이 문서는 위 질문에 "네, 알고 있습니다"라고 대답할 수 있게 만드는 것을 목표로 한다. 단순 사용법이 아니라 **왜 그렇게 동작하는지**를 밑바닥에서부터 쌓아 올린다.

## 2. AOP가 등장한 배경: OOP만으로는 왜 부족한가

OOP는 공통 기능을 **수직 방향**으로 재사용하기 좋다. 상속, 합성, 인터페이스를 통해 공통 로직을 묶을 수 있다. 그러나 실제 시스템에는 **수평 방향으로 여러 계층을 가로지르는 관심사**가 존재한다.

- 트랜잭션 경계 설정
- 성능 로깅 / 메트릭 수집
- 감사 로그 (누가, 언제, 무엇을 호출했는가)
- 인증/인가 검사
- 캐시 처리
- 재시도 / 서킷 브레이커

이런 관심사는 "모든 서비스 계층 public 메서드에 동일하게 적용"되는 성격을 가진다. OOP만 쓰면 이 로직이 모든 메서드에 다음처럼 흩어진다.

```java
public Order placeOrder(OrderCommand cmd) {
    long start = System.currentTimeMillis();
    try {
        transactionManager.begin();
        securityChecker.check(cmd);
        // 실제 비즈니스 로직
        Order order = ...;
        transactionManager.commit();
        return order;
    } catch (Exception e) {
        transactionManager.rollback();
        throw e;
    } finally {
        log.info("elapsed={}", System.currentTimeMillis() - start);
    }
}
```

템플릿 메서드나 데코레이터로 줄일 수는 있지만, 새로운 **횡단 관심사(cross-cutting concern)** 가 추가될 때마다 전 계층을 수정해야 한다는 근본 문제가 남는다. AOP는 이 횡단 관심사를 **핵심 로직과 분리해서 선언적으로 적용**하기 위해 나온 패러다임이다.

## 3. AOP의 핵심 용어 정리

AOP의 용어는 실무에서 혼용되기 쉽기 때문에 먼저 또렷하게 정의하자.

- **JoinPoint**: Advice가 적용될 수 있는 "지점". 메서드 호출, 필드 접근, 예외 throw 등 다양한 시점이 이론적으로 존재하지만, **Spring AOP에서 JoinPoint는 사실상 "메서드 실행(method execution)"만을 의미**한다.
- **Pointcut**: JoinPoint 중에서 **실제로 Advice를 적용할 대상을 고르는 식(expression)**. `execution(* com.acme.service..*.*(..))` 같은 표현식으로 정의한다.
- **Advice**: JoinPoint에서 **실행할 부가 동작**. `@Before`, `@After`, `@AfterReturning`, `@AfterThrowing`, `@Around` 다섯 종류가 있다.
- **Aspect**: Pointcut + Advice를 묶은 **모듈**. `@Aspect` 붙은 클래스 자체.
- **Weaving**: Advice를 실제 대상 객체의 호출 경로에 **끼워 넣는 과정**. 컴파일타임/로드타임/런타임 세 가지 방식이 있다.
- **Target**: 원래 호출하려던 **순수 비즈니스 객체**.
- **Proxy**: Target 앞에 서 있는 **대리인**. 실제 호출이 Target으로 가기 전에 Advice를 실행한다.

이 중 Spring AOP가 택한 위빙 전략이 바로 **런타임 프록시 기반 위빙**이다. 이게 AspectJ와의 근본적인 차이다.

## 4. Spring AOP는 왜 프록시 기반인가

AspectJ는 **바이트코드를 직접 수정**한다. 컴파일러를 바꿔치기하거나(compile-time weaving), 클래스 로딩 시점에 바이트코드를 주입한다(load-time weaving). 이 덕분에 AspectJ는 **필드 접근, 생성자 호출, private 메서드, static 메서드, self-invocation, final 메서드**까지 전부 가로챌 수 있다. 대신 빌드 툴체인과 에이전트 설정이 까다롭다.

Spring은 "평범한 Java, 평범한 빌드, 평범한 실행"을 목표로 한다. 별도 에이전트나 특수 컴파일러 없이 **순수 Java 런타임에서 동작**해야 한다. 그래서 Spring은 아래 전략을 택했다.

- 컨테이너가 빈(bean)을 생성할 때, 그 빈이 AOP 대상이면 **원본 객체 대신 프록시 객체를 빈으로 등록**한다.
- 다른 빈이 이 빈을 주입받을 때 받게 되는 건 **원본이 아니라 프록시**다.
- 프록시의 메서드가 호출되면, 프록시가 먼저 Advice 체인을 실행하고 그다음 원본 객체의 메서드를 호출한다.

이 선택에는 장점과 대가가 따른다.

**장점**
- 별도 툴체인 없이 순수 Java로 동작한다.
- 런타임에 AOP 구성을 동적으로 바꾸기 쉽다.
- 진입 장벽이 낮다.

**대가**
- 프록시를 통하지 않는 호출은 Advice가 걸리지 않는다 → **self-invocation 문제**.
- final 클래스/메서드, private 메서드, 생성자에는 끼어들 수 없다.
- 메서드 호출에만 끼어든다. 필드 접근은 가로채지 못한다.

이 대가들이 실무에서 끊임없이 "왜 내 `@Transactional`이 안 먹지?"라는 질문을 만들어낸다.

## 5. JDK Dynamic Proxy의 동작 원리

JDK Dynamic Proxy는 **JDK 1.3부터 포함된 표준 기능**이며, 핵심 구성요소는 두 가지다.

- `java.lang.reflect.Proxy` — 프록시 클래스를 런타임에 생성하는 팩토리
- `java.lang.reflect.InvocationHandler` — 프록시 메서드 호출이 들어왔을 때 실행될 단일 진입점

핵심 제약: **인터페이스가 있어야 한다.** JDK Proxy는 지정된 인터페이스들을 **implements**하는 새로운 클래스를 런타임에 만들어낸다. 대상 객체의 구체 타입은 상관없다. 대신 주입받는 쪽도 **반드시 인터페이스 타입으로** 받아야 한다.

### 5.1 최소 예제: 직접 만들어보는 JDK Proxy

```java
public interface OrderService {
    Order placeOrder(OrderCommand cmd);
}

public class OrderServiceImpl implements OrderService {
    @Override
    public Order placeOrder(OrderCommand cmd) {
        return new Order(cmd.userId(), cmd.amount());
    }
}

public class LoggingInvocationHandler implements InvocationHandler {
    private final Object target;

    public LoggingInvocationHandler(Object target) {
        this.target = target;
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        long start = System.nanoTime();
        try {
            return method.invoke(target, args);
        } finally {
            long elapsed = System.nanoTime() - start;
            System.out.printf("[LOG] %s took %d ns%n", method.getName(), elapsed);
        }
    }
}

public class Demo {
    public static void main(String[] args) {
        OrderService target = new OrderServiceImpl();
        OrderService proxy = (OrderService) Proxy.newProxyInstance(
                OrderService.class.getClassLoader(),
                new Class<?>[] { OrderService.class },
                new LoggingInvocationHandler(target)
        );

        proxy.placeOrder(new OrderCommand("u1", 1000));
    }
}
```

이 코드의 흐름은 다음과 같다.

1. `Proxy.newProxyInstance`가 런타임에 `com.sun.proxy.$Proxy0` 같은 **동적 클래스**를 만든다. 이 클래스는 `OrderService`를 implements한다.
2. 이 동적 클래스의 `placeOrder` 구현은 실제로 **`InvocationHandler.invoke(...)`를 호출**하도록 되어 있다.
3. 우리가 정의한 `LoggingInvocationHandler.invoke`가 호출되면서 로그를 남기고, `method.invoke(target, args)`로 진짜 구현체를 호출한다.
4. 결과가 proxy → 호출자에게 리턴된다.

즉 JDK Proxy는 **"인터페이스의 모든 메서드를 단일 `invoke`로 몰아주는 구조"** 다. 이 때문에 JDK Proxy의 제약이 자연스럽게 나온다.

- **인터페이스가 없으면 생성 불가** — `Proxy.newProxyInstance`는 인터페이스 배열을 요구한다.
- **인터페이스에 정의되지 않은 메서드는 프록시 대상이 아니다** — 구체 클래스에만 있는 public 메서드는 우회된다.
- **리플렉션 기반 `method.invoke` 호출**이라 순수 호출보다 오버헤드가 있다. 현대 JVM에서는 JIT으로 상당 부분 사라지지만 0은 아니다.

## 6. CGLIB의 동작 원리

대상 객체가 인터페이스를 구현하지 않은 **순수 클래스**라면 JDK Proxy를 쓸 수 없다. 이때 등장하는 것이 **CGLIB**다. CGLIB는 ASM 위에서 동작하는 **바이트코드 조작 라이브러리**로, **대상 클래스를 상속받는 서브클래스를 런타임에 만든다**.

```
OrderServiceImpl            (target class)
        ▲
        │ extends
OrderServiceImpl$$EnhancerByCGLIB$$abc123   (proxy subclass)
```

이 서브클래스는 원본 클래스의 모든 public/protected 메서드를 **오버라이드**하고, 오버라이드된 메서드 안에서 `MethodInterceptor`를 호출한다.

```java
public class LoggingInterceptor implements MethodInterceptor {
    @Override
    public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy)
            throws Throwable {
        long start = System.nanoTime();
        try {
            // super 호출과 동일. JDK Proxy의 method.invoke(target,...)과 대비
            return proxy.invokeSuper(obj, args);
        } finally {
            System.out.printf("[CGLIB] %s took %d ns%n",
                    method.getName(), System.nanoTime() - start);
        }
    }
}

Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(OrderServiceImpl.class);
enhancer.setCallback(new LoggingInterceptor());
OrderServiceImpl proxy = (OrderServiceImpl) enhancer.create();
proxy.placeOrder(new OrderCommand("u1", 1000));
```

CGLIB의 특성이 여기서 드러난다.

- **인터페이스가 필요 없다.** 구체 클래스 타입 그대로 주입받아도 된다.
- **서브클래싱이 기반**이다. 따라서 **`final` 클래스**는 상속 불가 → 프록시 불가, **`final` 메서드**는 오버라이드 불가 → **Advice가 걸리지 않는다**.
- **`private` / `package-private` 메서드**는 오버라이드 의미론적으로 가로챌 수 없다. Spring AOP도 기본적으로 public 메서드에만 적용된다고 말하는 이유가 이것이다.
- **생성자는 한 번 더 호출된다.** 프록시는 서브클래스이므로 부모 생성자가 다시 불린다. 이 때문에 생성자에 무거운 초기화 로직을 넣으면 두 번 실행되는 문제가 생길 수 있다. Spring은 이를 완화하기 위해 `objenesis`를 이용해 생성자를 우회하는 전략을 쓰기도 한다.

## 7. ByteBuddy는 무엇을 푸는 라이브러리인가

CGLIB는 오래된 라이브러리이고, 오랫동안 거의 유지보수 상태가 아니었다. JDK 9 이후의 모듈 시스템, 불투명한 `sun.misc.Unsafe`, JDK 17+의 강화된 접근 제어 등 **JVM 내부 변화에 취약**했다. CGLIB가 패치를 따라가지 못하는 사이에 등장한 현대적 대안이 **ByteBuddy**다.

- ByteBuddy도 결국 **바이트코드를 만들거나 수정하는 라이브러리**다. CGLIB과 비슷한 서브클래싱 프록시도 만들 수 있고, 더 일반적인 바이트코드 조작도 가능하다.
- 유창한 DSL, 최신 JVM 지원, 자바 에이전트(`java.lang.instrument`) 작성의 사실상 표준.
- **Mockito**의 기본 모킹 엔진이 ByteBuddy로 바뀌었다. Mockito가 final 클래스/메서드까지 모킹할 수 있는 것도 ByteBuddy + JVM agent 조합 덕이다.
- **Spring Framework 6.x / Spring Boot 3.x 이상에서는 내부적으로 CGLIB 대신 ByteBuddy를 쓰는 방향으로 정리되었다.** 이용자 입장에서 달라지는 점은 거의 없지만, "Spring = CGLIB"이라는 인식은 최신 버전에선 부정확하다. 내부 엔진이 ByteBuddy로 이전되면서 서브클래싱 프록시 전략은 유지하되 JVM 호환성이 개선된 상태다.
- **JVM 관측 도구, APM, 트레이싱 에이전트**(예: Datadog, New Relic, OpenTelemetry Java Agent)가 대부분 ByteBuddy를 쓴다. "자바 에이전트 붙여서 메서드 진입/종료 후킹" = ByteBuddy가 기본 도구라는 말과 거의 같다.

정리하면, 우리가 면접에서 "CGLIB으로 프록시를 만듭니다"라고 답해도 개념적으로는 맞지만, 현대 Spring 내부에서는 **"서브클래싱 프록시를 ByteBuddy 기반으로 생성한다"** 가 더 정확하다.

## 8. Spring은 JDK Proxy와 CGLIB 중 무엇을 선택하는가

Spring의 기본 선택 규칙은 대략 이렇다.

1. **`spring.aop.proxy-target-class=true`** 이거나 `@EnableAspectJAutoProxy(proxyTargetClass=true)`이면 → 항상 **CGLIB(서브클래싱 프록시)**.
2. 대상 빈이 **하나 이상의 인터페이스를 구현**하고 있으면 → **JDK Dynamic Proxy**.
3. 대상 빈이 인터페이스를 구현하지 않았다면 → **CGLIB**.

**Spring Boot 2.x 이후 기본값은 `proxyTargetClass=true`** 다. 즉 요즘 Spring Boot 프로젝트는 인터페이스 유무와 무관하게 **사실상 CGLIB 기반 프록시**가 쓰인다. 이것 덕분에 "인터페이스를 분리하지 않은 `@Service` 클래스"에 `@Transactional`을 붙여도 동작한다.

실무에서 기억할 포인트는 다음과 같다.

- 주입 시 **구체 타입**으로 받아도 안전해진다 (CGLIB이니 서브클래스라 캐스팅됨).
- 대신 `final` 메서드에 `@Transactional` 붙이면 조용히 Advice가 사라진다. 컴파일 에러도 안 난다.
- Kotlin은 클래스/메서드가 기본 `final`이라 `open`을 붙이거나 `kotlin-spring` 플러그인을 써야 한다. (현재 우리는 Java 트랙이지만 알아두면 좋다.)

## 9. self-invocation 문제: 왜 `@Transactional`이 동작하지 않는가

이것이 Spring AOP 관련 질문에서 가장 자주 나오는 함정이다.

```java
@Service
public class OrderService {

    public void placeOrder(OrderCommand cmd) {
        validate(cmd);
        save(cmd);
    }

    @Transactional
    public void save(OrderCommand cmd) {
        orderRepository.save(toEntity(cmd));
    }
}
```

개발자는 "save에 트랜잭션이 걸리길" 기대한다. 하지만 외부에서 `placeOrder`를 호출하면 트랜잭션은 **걸리지 않는다**. 왜 그런가?

호출 스택을 보자.

```
caller -> proxy.placeOrder(cmd)
            -> target.placeOrder(cmd)          // 여기까지는 프록시 통과
                -> this.save(cmd)              // 'this'는 target 자신. 프록시가 아님!
                    -> orderRepository.save(...)  // 트랜잭션 없음
```

`placeOrder` 내부의 `this.save(cmd)` 호출은 **Java의 일반 메서드 호출**이다. `this`는 프록시가 아니라 원본 `OrderServiceImpl` 인스턴스다. 프록시를 우회했으니 Advice(트랜잭션 시작)가 끼어들 틈이 없다.

같은 원리로 다음이 전부 조용히 실패한다.

- `@Transactional`이 self-invocation으로 호출되어 트랜잭션이 안 열림
- `@Async`가 self-invocation으로 호출되어 같은 스레드에서 동기 실행됨
- `@Cacheable`이 self-invocation으로 호출되어 캐시가 전혀 타지 않음

### 9.1 self-invocation 우회 전략

1. **분리 (권장)**
   횡단 관심사가 걸린 메서드를 **다른 빈으로 뽑아낸다**. 그러면 호출이 "다른 빈의 프록시"를 거치게 된다.
   ```java
   @Service
   @RequiredArgsConstructor
   public class OrderFacade {
       private final OrderTxService txService;
       public void placeOrder(OrderCommand cmd) {
           validate(cmd);
           txService.save(cmd);   // 다른 빈의 프록시를 탄다
       }
   }
   ```

2. **`AopContext.currentProxy()` + `exposeProxy=true`**
   프록시 자신을 노출시키고 자기 자신을 프록시로 호출한다. 동작은 하지만 코드 가독성이 떨어져 최후의 수단으로만 쓴다.
   ```java
   @EnableAspectJAutoProxy(exposeProxy = true)
   ...
   ((OrderService) AopContext.currentProxy()).save(cmd);
   ```

3. **AspectJ 위빙으로 전환**
   바이트코드 위빙이라 self-invocation도 잡힌다. 대신 `spring-aspects`, AspectJ 컴파일/에이전트 설정이 필요해 운영 복잡도가 크게 올라간다.

실무 99%는 **"그냥 빈을 분리한다"** 가 정답이다.

## 10. 프록시 기반 AOP의 한계 총정리

- **self-invocation 불가**: 같은 객체 내부 호출은 Advice가 안 걸린다.
- **final 클래스/메서드 불가**: CGLIB은 상속이 필요하므로.
- **private 메서드 불가**: 오버라이드 의미론 상 불가능.
- **생성자, static 메서드 불가**: 프록시가 간섭할 방법이 없다.
- **메서드 호출만 가로챈다**: 필드 접근은 AspectJ가 아니면 불가.
- **프록시 타입 캐스팅 주의**: JDK Proxy는 구체 클래스로 캐스팅 불가. 오직 인터페이스 타입으로만.
- **여러 Advice가 중첩**될 때 순서는 `@Order`로 통제. 기본 순서는 보장되지 않으니 명시해야 한다.

## 11. 호출 스택 관점에서 보는 프록시 개입

Spring Boot에서 다음 코드를 디버깅해보면 실제 스택이 어떻게 보이는지 감을 잡을 수 있다.

```java
@Service
public class PaymentService {
    @Transactional
    public void pay(PayCommand cmd) {
        // breakpoint here
    }
}
```

디버거로 `pay` 메서드 진입 지점에서 멈추면 스택은 보통 이렇게 생긴다.

```
PaymentService.pay(PayCommand)                 // ← 내 코드
PaymentService$$SpringCGLIB$$0.pay(PayCommand) // ← 프록시 서브클래스
CglibAopProxy$DynamicAdvisedInterceptor.intercept(...)
ReflectiveMethodInvocation.proceed()
TransactionInterceptor.invoke(MethodInvocation)
TransactionAspectSupport.invokeWithinTransaction(...)
ReflectiveMethodInvocation.proceed()
CglibAopProxy$DynamicAdvisedInterceptor.intercept(...)
...
PaymentController.pay(...)
```

읽는 법은 다음과 같다.

- 컨트롤러가 `paymentService.pay(...)`를 호출하면 실제로는 **CGLIB 프록시의 `pay`** 가 먼저 호출된다.
- 프록시는 `DynamicAdvisedInterceptor.intercept(...)`를 거쳐 **Advisor 체인**을 구성한다.
- 체인은 `ReflectiveMethodInvocation.proceed()`를 통해 한 단계씩 앞으로 나아간다.
- `TransactionInterceptor`가 트랜잭션을 시작하고, 체인의 끝에서 **진짜 `PaymentService.pay`** 가 호출된다.
- 메서드가 리턴되면 역순으로 체인이 풀리면서 트랜잭션이 커밋/롤백된다.

이 스택을 한 번이라도 본 개발자와 안 본 개발자는 `@Transactional` 버그를 만났을 때 대응 속도가 완전히 다르다.

## 12. 성능, 디버깅, 테스트 관점의 주의사항

**성능**

- 프록시 오버헤드 자체는 현대 JVM + JIT에서 대부분 무시할 만하다. 문제는 대개 **프록시가 아니라 Advice 로직**에서 발생한다. 예: 인증 Advice에서 매 호출마다 DB 조회.
- CGLIB 서브클래스는 **클래스 로더 메타스페이스에 영구적으로 올라간다.** 테스트에서 매번 새 프록시를 만들면 메타스페이스가 커질 수 있다. Spring TestContext는 이를 고려해 캐싱한다.
- 프록시는 `equals`, `hashCode`, `toString`에 영향을 줄 수 있다. JDK Proxy는 인터페이스에 없는 이 메서드들의 의미론이 살짝 달라진다.

**디버깅**

- 스택 트레이스에 `EnhancerBySpringCGLIB`, `$$SpringCGLIB$$`, `$Proxy` 같은 이름이 보이면 **프록시를 타고 있다는 증거**다.
- 로그에서 `service.getClass()` 를 찍어보면 프록시 타입인지 원본인지 즉시 확인할 수 있다.
- 주입된 빈의 **실제 타입**과 **선언 타입**이 다를 수 있다는 걸 항상 염두에 둔다.

**테스트**

- 단위 테스트에서는 프록시를 거치지 않고 원본을 테스트한다. 따라서 `@Transactional` 같은 AOP 동작은 단위 테스트에서 보장되지 않는다.
- AOP를 검증하려면 **Spring context를 띄우는 통합 테스트**로 가야 한다.
- Mockito로 모킹할 때 **final 클래스/메서드**는 추가 설정(`mockito-inline`, ByteBuddy agent)이 없으면 모킹되지 않는다. 이것도 결국 프록시(서브클래싱) 한계의 연장선이다.

## 13. Bad vs Improved 예제

**Bad: self-invocation으로 트랜잭션 누락**

```java
@Service
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;
    private final MailClient mailClient;

    public void signUp(SignUpCommand cmd) {
        saveUser(cmd);                 // ← @Transactional이 걸리지 않는다
        mailClient.sendWelcome(cmd.email());
    }

    @Transactional
    public void saveUser(SignUpCommand cmd) {
        userRepository.save(new User(cmd));
    }
}
```

문제:
- `signUp` 내부에서 `this.saveUser`를 호출 → 프록시 우회 → 트랜잭션 안 열림.
- `userRepository.save`가 JPA라면 EntityManager가 기대했던 트랜잭션 범위 밖에서 동작해 `TransactionRequiredException` 혹은 자동 커밋 모드 이슈로 이어진다.

**Improved: 책임 분리로 프록시 경계를 확보**

```java
@Service
@RequiredArgsConstructor
public class UserSignUpFacade {
    private final UserRegistrationService registrationService;
    private final MailClient mailClient;

    public void signUp(SignUpCommand cmd) {
        registrationService.register(cmd);
        mailClient.sendWelcome(cmd.email());
    }
}

@Service
@RequiredArgsConstructor
public class UserRegistrationService {
    private final UserRepository userRepository;

    @Transactional
    public void register(SignUpCommand cmd) {
        userRepository.save(new User(cmd));
    }
}
```

개선 포인트:
- `signUp` → `registrationService.register`는 **다른 빈의 프록시** 호출 → 트랜잭션 정상 진입.
- 메일 발송은 트랜잭션 **밖**에서 실행되어 DB 롤백과 메일 발송이 분리됨. (실서비스에서는 트랜잭션 커밋 후 이벤트로 발행하는 게 더 안전하다 — `@TransactionalEventListener` 활용.)
- 트랜잭션 경계와 비즈니스 플로우가 **물리적으로 분리**되어 테스트, 리팩터링, 추적이 전부 쉬워짐.

## 14. 로컬 실습 환경

최소 환경:
- JDK 17 이상
- Spring Boot 3.2+
- Gradle 또는 Maven
- H2 인메모리 DB (실습용)
- IntelliJ IDEA (디버거로 프록시 스택 확인)

`build.gradle` 핵심:

```groovy
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-aop'
    runtimeOnly   'com.h2database:h2'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
```

`application.yml`:

```yaml
spring:
  datasource:
    url: jdbc:h2:mem:demo;MODE=MySQL
  jpa:
    hibernate.ddl-auto: create-drop
    show-sql: true
logging:
  level:
    org.springframework.transaction: TRACE
    org.springframework.aop: DEBUG
```

`TRACE` 로그를 켜두면 트랜잭션 Advisor가 언제 시작·커밋·롤백되는지 콘솔에 그대로 찍힌다. self-invocation으로 트랜잭션이 누락되면 **아예 로그가 안 찍힌다.** 이게 가장 빠른 진단 방법이다.

## 15. 실행 가능한 미니 예제: 커스텀 Aspect 만들기

```java
@Aspect
@Component
public class TimingAspect {

    private static final Logger log = LoggerFactory.getLogger(TimingAspect.class);

    @Around("execution(public * com.example.demo.service..*(..))")
    public Object time(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.nanoTime();
        try {
            return pjp.proceed();
        } finally {
            long elapsedUs = (System.nanoTime() - start) / 1_000;
            log.info("[TIMING] {}.{} took {} us",
                    pjp.getSignature().getDeclaringType().getSimpleName(),
                    pjp.getSignature().getName(),
                    elapsedUs);
        }
    }
}
```

확인 포인트:
- `service..*(..)` 표현식으로 `service` 패키지의 **모든 public 메서드**를 대상으로 함.
- `ProceedingJoinPoint.proceed()`를 호출해야 원본 메서드가 실행된다. 빼먹으면 비즈니스 로직이 증발한다 — 실제 운영 장애로 보고된 적이 여러 번 있는 흔한 실수다.
- Advice 자체에서 예외가 나면 비즈니스 로직이 실행되지 않는다. Advice 안에서는 **빠르고 가볍고 실패하지 않는 작업**만 하도록 설계한다.

## 16. 면접 답변 프레임: 1분 버전과 3분 버전

**1분 답변 (엘리베이터 버전)**

> Spring AOP는 런타임 프록시 기반입니다. 빈이 생성될 때 대상 객체 대신 프록시 객체가 컨테이너에 등록되고, 이 프록시가 Advice 체인을 먼저 실행한 뒤 원본 메서드를 호출합니다. 인터페이스가 있으면 JDK Dynamic Proxy, 없거나 `proxyTargetClass=true`면 CGLIB 서브클래싱 프록시가 만들어집니다. Spring Boot 기본값은 CGLIB 쪽입니다. 프록시를 거치지 않는 호출, 즉 같은 객체의 내부 메서드 호출(self-invocation)에는 Advice가 걸리지 않아서 `@Transactional`, `@Async`, `@Cacheable`이 조용히 안 먹는 현상이 자주 발생합니다. 해결은 보통 해당 메서드를 다른 빈으로 분리합니다.

**3분 답변 (심화 버전)**

> Spring AOP를 이해하려면 세 가지 레이어를 구분해야 합니다. 첫째, 개념 레이어: Pointcut이 JoinPoint를 고르고, 거기에 Advice를 끼워 넣는 것이 AOP의 본질입니다. 둘째, 구현 레이어: AspectJ는 바이트코드 위빙으로 해결하는 데 반해 Spring은 순수 Java로 동작하는 런타임 프록시를 택했습니다. 셋째, 프록시 생성 레이어: 인터페이스가 있으면 JDK Dynamic Proxy를 써서 `InvocationHandler` 기반으로 단일 진입점을 통해 호출을 위임하고, 인터페이스가 없거나 `proxyTargetClass=true`면 서브클래싱 기반 프록시를 씁니다. 과거에는 CGLIB이었고 최근 Spring에서는 ByteBuddy 기반으로 현대화되었습니다.
>
> 이 선택 때문에 실무에서 중요한 함정들이 따라옵니다. CGLIB은 서브클래싱이라 `final` 클래스/메서드에 Advice를 걸 수 없고, JDK Proxy는 인터페이스에 선언되지 않은 메서드를 가로챌 수 없습니다. 가장 큰 이슈는 self-invocation입니다. 같은 클래스 안에서 `this.someMethod()`를 호출하면 프록시를 우회하기 때문에 트랜잭션, 비동기, 캐시가 전부 동작하지 않습니다. 해결책은 우선순위 순으로 (1) 해당 메서드를 별도 빈으로 분리, (2) `exposeProxy=true`와 `AopContext.currentProxy()`, (3) AspectJ 위빙 도입입니다. 대부분 (1)로 해결합니다.
>
> 디버깅 측면에서는 스택 트레이스에 `SpringCGLIB`, `DynamicAdvisedInterceptor`, `ReflectiveMethodInvocation.proceed` 같은 프레임이 보이면 프록시를 제대로 타고 있다는 신호입니다. 반대로 `@Transactional`을 걸었는데 로그 레벨을 TRACE로 올려도 트랜잭션 시작 로그가 안 찍히면 self-invocation이나 final 메서드를 의심합니다. 저는 이 원리를 기반으로 팀에 "AOP가 걸리는 메서드는 반드시 프록시 경계를 넘어서 호출되어야 한다"는 규약을 정해두고 리뷰에서 체크하는 편입니다.

## 17. 체크리스트

학습 완료 기준으로 자신에게 묻는다. 모두 Yes여야 한다.

- [ ] Pointcut, JoinPoint, Advice, Weaving을 한 문장씩 정확하게 정의할 수 있다.
- [ ] Spring AOP가 왜 프록시 기반인지, AspectJ와의 차이를 설명할 수 있다.
- [ ] JDK Dynamic Proxy가 왜 인터페이스를 요구하는지 원리 수준에서 설명할 수 있다.
- [ ] CGLIB이 왜 `final`에 약한지, 생성자가 한 번 더 호출될 수 있는지 설명할 수 있다.
- [ ] ByteBuddy가 CGLIB 대비 어떤 맥락에서 등장했는지, Mockito/Spring/APM 에이전트와의 관계를 설명할 수 있다.
- [ ] Spring이 런타임에 JDK Proxy vs CGLIB 중 무엇을 고르는지 규칙을 안다.
- [ ] self-invocation이 왜 발생하는지 호출 스택 수준에서 설명할 수 있고, 세 가지 해결책을 제시할 수 있다.
- [ ] `@Transactional`, `@Async`, `@Cacheable`이 동작하지 않는 증상을 보고 프록시 함정을 가장 먼저 의심할 수 있다.
- [ ] 스택 트레이스에서 프록시 프레임을 읽어낼 수 있다.
- [ ] 간단한 `@Around` Aspect를 직접 작성해서 걸고, 걸리지 않는 케이스를 재현할 수 있다.
- [ ] 면접에서 1분 / 3분 버전 답변을 둘 다 막힘없이 말할 수 있다.

이 체크리스트를 전부 통과하면 "Spring AOP는 내부적으로 프록시로 동작합니다" 수준의 대답에서 벗어나, **"프록시 생성 전략과 호출 스택 관점에서 AOP의 범위와 한계를 지배하는 개발자"** 로 면접관에게 읽힌다. 이 지점이 시니어 백엔드 면접에서 기대되는 깊이다.
