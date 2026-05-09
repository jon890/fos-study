# [초안] Spring 트랜잭션 전파, 커머스 주문/결제에서 실전으로 이해하기

## 왜 지금 이 주제인가

CJ푸드빌처럼 매장/배달/예약/결제가 한 트랜잭션 흐름에서 함께 움직이는 커머스 도메인에서는 "이 메서드 하나가 어떤 트랜잭션 안에서 도는가"가 곧 데이터 정합성의 경계가 된다. 주문 저장은 성공했는데 결제 호출은 실패했다, 또는 결제는 통과했는데 알림 발송이 트랜잭션을 같이 끌고 들어가서 전체 롤백되어 사용자 입장에서 "결제는 됐는데 주문은 없는" 상태가 만들어졌다 — 이런 사건이 거의 다 트랜잭션 전파(propagation)와 예외 처리 규칙을 잘못 잡았을 때 터진다.

그리고 면접에서는 항상 같은 함정 질문이 따라붙는다. `REQUIRES_NEW`를 어디에 쓰면 안 되는지, `rollbackOnly`가 왜 갑자기 던져지는지, `@Transactional` 메서드를 같은 클래스 내부에서 호출하면 왜 동작하지 않는지, `AFTER_COMMIT` 이벤트 리스너에서 다시 DB를 건드리면 왜 위험한지. 이건 단순 암기가 아니라, Spring AOP 프록시와 JDBC 트랜잭션 매뉴얼을 한 번이라도 직접 그려본 사람만 자연스럽게 답할 수 있다.

이 문서는 그걸 한 번 그려두는 글이다. 실제 주문/결제/이벤트 발행 코드를 단순화한 형태로 보여주면서, 실패 사례와 그 이유, 면접에서 나올 만한 후속 질문, 그리고 본인의 Kafka Outbox 경험과 자연스럽게 연결하는 답변 골격까지 같이 정리한다.

## 핵심 개념: 전파(propagation)는 "이 호출이 트랜잭션 경계를 새로 그릴 것인가"의 정책

Spring `@Transactional`의 `propagation` 속성은 "지금 이 메서드를 호출하는 시점에 이미 트랜잭션이 활성 상태일 때 어떻게 행동할지"에 대한 규칙이다. 흔히 쓰는 값과 그 의미를 커머스 시나리오에 매핑하면 다음과 같다.

- **REQUIRED (기본값)**: 호출자에 트랜잭션이 있으면 그 트랜잭션에 합류, 없으면 새로 시작. 같은 논리적 작업 단위에 속하는 일반 비즈니스 로직 대부분이 여기에 해당한다. 주문 저장, 재고 차감, 쿠폰 사용 마킹은 같은 단위로 묶이는 게 자연스럽다.
- **REQUIRES\_NEW**: 호출자 트랜잭션이 있어도 일단 일시 정지(suspend)하고, 물리적으로 새로운 트랜잭션을 시작한다. 호출 끝나면 새 트랜잭션이 커밋/롤백되고 바깥 트랜잭션이 재개된다. 감사 로그, 실패 기록, 외부 호출 결과 저장처럼 "바깥이 어떻게 끝나든 이건 별도로 살아남아야 한다"는 케이스에 쓴다.
- **NESTED**: 새로운 트랜잭션이 아니라 같은 물리 트랜잭션 안에 SAVEPOINT를 만든다. 안쪽이 실패하면 SAVEPOINT까지만 롤백, 바깥이 실패하면 같이 롤백. 사실상 한 트랜잭션 안의 부분 롤백이다. JDBC 기반에서만 동작하고, JPA + Hibernate 1차 캐시와 결합하면 경계가 흐려져 실무에서는 쓰기 까다롭다.
- **MANDATORY**: 반드시 호출자 트랜잭션이 있어야 하고 없으면 예외. 라이브러리/공통 컴포넌트 안전장치로 쓴다.
- **NEVER / NOT\_SUPPORTED / SUPPORTS**: 비-트랜잭셔널 영역에서만 돌거나, 트랜잭션이 있든 없든 신경 쓰지 않는 케이스. 읽기 전용 캐시 조회 같은 곳에 한정적으로.

여기서 가장 자주 잘못 쓰는 게 `REQUIRES_NEW`다. "분리되니까 안전하겠지"라는 직관과 다르게, 같은 물리 커넥션 풀에서 트랜잭션을 스택처럼 쌓는 구조이기 때문에 부주의하게 남발하면 커넥션 고갈, 자기 자신과의 락 경합, 그리고 외부 트랜잭션이 마치 커밋된 것처럼 안쪽 데이터가 보이지 않는 가시성 함정이 줄줄이 따라온다.

## 예외와 롤백 규칙: 왜 RuntimeException만 자동 롤백인가

Spring은 기본적으로 **unchecked exception(RuntimeException)과 Error**가 던져졌을 때만 트랜잭션을 자동 롤백한다. `IOException` 같은 checked exception은 던져져도 자동 롤백되지 않는다. 이건 EJB 시절의 관례를 그대로 가져온 것으로, "checked는 비즈니스적으로 회복 가능한 흐름"이라는 가정에서 출발한다.

커머스에서 이게 문제가 되는 전형적인 패턴은 결제 게이트웨이 호출이다. 외부 PG 호출이 `IOException`을 던지면 `@Transactional` 메서드는 그 예외를 그대로 위로 던지고, **DB 트랜잭션은 정상 커밋된다**. 결과는 "주문은 저장됐는데 결제 시도는 실패한" 상태. 이걸 막으려면 둘 중 하나다.

```java
@Transactional(rollbackFor = Exception.class)
public OrderResult placeOrder(OrderCommand cmd) { ... }
```

또는 checked exception을 비즈니스 시그니처에서 걷어내고 도메인 RuntimeException으로 감싸 던지는 방식. 후자가 일반적으로 더 깔끔하고, 도메인 계층에 외부 라이브러리 예외 타입이 섞이지 않는다는 부수 효과도 있다.

또 한 가지, `try-catch`로 RuntimeException을 잡아 "삼키면" 자동 롤백 트리거가 사라진다. 그런데 만약 그 예외가 **이미 내부 메서드에서 트랜잭션 매니저에 rollbackOnly 마크를 찍어 둔 뒤** 라면, 바깥에서 잡고 무시해도 커밋 시점에 `UnexpectedRollbackException`이 터진다. 이게 면접 단골 질문 "rollbackOnly 본 적 있어요?"의 본체다.

## 자기 호출(self-invocation) 함정

`@Transactional`은 Spring AOP 프록시를 통해 적용된다. 즉, 같은 빈 안에서 `this.someMethod()`로 호출하면 프록시를 거치지 않고 바로 원본 메서드가 실행되므로 트랜잭션이 시작되지 않는다. 다음 코드는 매우 흔한 실수다.

### Bad

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final PaymentClient paymentClient;

    public OrderResult placeOrder(OrderCommand cmd) {
        Order order = orderRepository.save(Order.from(cmd));
        // 같은 클래스 내부 메서드 호출 -> 프록시 미적용 -> @Transactional 무효
        chargePayment(order);
        return OrderResult.of(order);
    }

    @Transactional
    public void chargePayment(Order order) {
        paymentClient.charge(order.id(), order.amount());
        order.markPaid();
        orderRepository.save(order);
    }
}
```

### Improved

```java
@Service
@RequiredArgsConstructor
public class OrderFacade {

    private final OrderWriter orderWriter;
    private final PaymentApplier paymentApplier;

    public OrderResult placeOrder(OrderCommand cmd) {
        Order order = orderWriter.create(cmd);
        paymentApplier.apply(order);
        return OrderResult.of(order);
    }
}

@Component
@RequiredArgsConstructor
public class PaymentApplier {

    private final PaymentClient paymentClient;
    private final OrderRepository orderRepository;

    @Transactional(rollbackFor = Exception.class)
    public void apply(Order order) {
        paymentClient.charge(order.id(), order.amount());
        order.markPaid();
        orderRepository.save(order);
    }
}
```

해법은 두 가지 중 하나다. 트랜잭션이 필요한 메서드를 **다른 빈으로 분리**하거나, 정 같은 클래스에 둬야 하면 `AopContext.currentProxy()`로 프록시를 가져와 호출하는 방법이 있다. 실무에서는 클래스를 분리하는 쪽이 압도적으로 깨끗하다. 면접에서는 "왜 안 되는지"의 원인을 **CGLIB 또는 JDK 동적 프록시 기반 호출 흐름** 차원에서 설명할 수 있어야 한다.

## REQUIRES\_NEW로 실패 로그 분리하기

주문 트랜잭션이 롤백되더라도 "결제 시도가 있었다"는 사실은 감사/고객문의 대응을 위해 남아 있어야 한다. 이때 `REQUIRES_NEW`가 적절하다.

```java
@Component
@RequiredArgsConstructor
public class PaymentAuditWriter {

    private final PaymentAuditRepository auditRepository;

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordAttempt(PaymentAttempt attempt) {
        auditRepository.save(attempt);
    }
}
```

주의점은 두 가지다. 첫째, 이 메서드가 던지는 예외를 호출자가 잡아 삼키지 않으면 바깥 트랜잭션도 같이 롤백된다. 그래서 보통 호출자에서 `try-catch`로 감사 실패는 별도 로그로만 남기고 비즈니스 흐름은 진행시킨다. 둘째, `REQUIRES_NEW`는 새 커넥션을 점유하므로 같은 풀에서 바깥 트랜잭션이 들고 있는 행에 락 경합이 생기면 자기 자신과 데드락이 난다. 감사 테이블은 별도 테이블이어야 하고, 가능하면 별도 데이터소스나 최소한 다른 행에만 손대는 구조여야 한다.

## NESTED와 SAVEPOINT가 실무에서 잘 안 쓰이는 이유

`NESTED`는 JDBC SAVEPOINT 위에서 동작한다. 이론적으로는 "이 일부 작업만 부분 롤백"이라는 깔끔한 모델이지만, JPA를 같이 쓰면 1차 캐시와 SAVEPOINT 시점이 어긋난다. 안쪽에서 영속화한 엔티티를 SAVEPOINT로 되돌렸는데 1차 캐시에는 남아 있어 이후 조회/플러시가 비정합 상태가 되는 식이다. 그래서 JPA 환경에서는 `NESTED`보다 **REQUIRES\_NEW + 별도 컴포넌트**, 또는 **부분 실패는 도메인 로직으로 흡수**하는 방향을 많이 선택한다.

면접에서 NESTED가 나오면 "동작 원리는 SAVEPOINT 기반이고, JPA와 함께 쓰면 1차 캐시 정합 이슈로 권장하지 않는다"까지 답하면 충분하다.

## @TransactionalEventListener(AFTER\_COMMIT)와 Outbox

도메인 이벤트를 트랜잭션 커밋 직후에 발행하고 싶을 때 흔히 쓰는 패턴이다.

```java
@Component
@RequiredArgsConstructor
public class OrderPaidEventListener {

    private final OutboxAppender outboxAppender;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void on(OrderPaidEvent event) {
        outboxAppender.appendInNewTransaction(event);
    }
}
```

여기서 가장 자주 빠지는 함정이 두 개다.

첫째, `AFTER_COMMIT` 시점에는 **이미 원래 트랜잭션이 커밋되어 닫혀 있다**. 이 리스너 안에서 그냥 `@Transactional`도 안 붙이고 JPA save를 호출하면, 트랜잭션 없는 상태에서 영속성 컨텍스트가 끝까지 살아남지 못해 의도와 다르게 동작한다. 그래서 리스너 본문에서 다시 DB를 건드리려면 명시적으로 새 트랜잭션을 열어야 한다 — 보통 `REQUIRES_NEW` 짜리 별도 컴포넌트 메서드를 호출하는 형태로 분리한다.

둘째, 이벤트 리스너 안에서 발행 자체(예: Kafka producer 호출)를 직접 하면 **외부 시스템과 DB 사이에 이중 쓰기 정합성 문제**가 다시 생긴다. DB 커밋 후 발행 직전에 프로세스가 죽으면 이벤트가 사라진다. 그래서 실무에서는 발행을 직접 하지 않고, **같은 DB 트랜잭션 안에서 outbox 테이블에 이벤트 row를 함께 저장**하고, 별도 publisher 프로세스가 outbox를 폴링/CDC해서 Kafka로 흘려보내는 구조로 간다. 이 패턴이 Transactional Outbox다.

`AFTER_COMMIT` 리스너는 이 흐름에서 보조적으로 쓴다. 예를 들어 outbox가 이미 도메인 트랜잭션 안에서 채워졌다면, `AFTER_COMMIT`에서는 publisher를 깨우는 신호 정도만 보내고 실제 발행은 publisher 쪽에서 책임지게 한다. 만약 outbox 저장 자체에 실패해 별도 데드레터로 옮겨야 하는 케이스가 생기면, 그건 다시 `REQUIRES_NEW` 트랜잭션으로 실패 기록을 남기는 흐름과 합쳐진다.

## rollbackOnly와 UnexpectedRollbackException

전파가 `REQUIRED`인 메서드 안에서 RuntimeException이 발생하면 Spring 트랜잭션 매니저는 **현재 트랜잭션에 rollbackOnly 플래그**를 세운다. 이걸 호출자가 잡아서 무시해도, 가장 바깥 트랜잭션이 커밋을 시도하는 순간 매니저는 "이미 롤백 마킹된 트랜잭션을 커밋하라고요?"라며 `UnexpectedRollbackException`을 던진다.

```java
@Transactional
public void placeOrder(...) {
    try {
        paymentApplier.apply(order); // REQUIRED, 안에서 RuntimeException
    } catch (PaymentException e) {
        // 삼키면 위에서 UnexpectedRollbackException 발생
        log.warn("결제 실패, 무시하고 진행", e);
    }
    // 여기서 다른 일 더 함 -> 결국 커밋 시점에 폭발
}
```

해결책은 두 가지다. 정말 분리하고 싶으면 안쪽을 `REQUIRES_NEW`로 두거나, 분리할 게 아니면 예외를 삼키지 말고 위로 흘려보낸다. "삼키되 진행"은 보통 잘못된 설계다.

## 로컬 실습 환경

MySQL 8 + Spring Boot 3 + JPA로 충분하다.

```yaml
# application.yml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/commerce_lab?useSSL=false&serverTimezone=UTC
    username: lab
    password: lab
  jpa:
    hibernate:
      ddl-auto: update
    properties:
      hibernate.format_sql: true
logging:
  level:
    org.springframework.transaction.interceptor: TRACE
    org.hibernate.SQL: DEBUG
```

`org.springframework.transaction.interceptor`를 TRACE로 켜면 어떤 메서드가 어떤 propagation으로 트랜잭션을 시작/합류했는지 로그에 그대로 찍힌다. 실습 중에는 이 로그만 따라가도 학습 효율이 크게 올라간다.

## 실습 시나리오

다음 순서로 손으로 직접 재현해 보면 개념이 체화된다.

1. `OrderService.placeOrder` 안에서 같은 클래스의 `@Transactional` 메서드를 `this.method()`로 호출 → 트랜잭션이 시작되지 않는 로그 확인.
2. 그 메서드를 별도 `PaymentApplier` 빈으로 옮기고 다시 호출 → REQUIRED로 합류하는 로그 확인.
3. `PaymentClient`가 `IOException`을 던지도록 만들고 `rollbackFor` 없이 실행 → DB는 커밋되어 데이터가 남는 것 확인. `rollbackFor = Exception.class`를 추가한 뒤 재실행해 롤백되는 것 비교.
4. `PaymentAuditWriter.recordAttempt`를 `REQUIRES_NEW`로 만들고, 바깥 트랜잭션을 인위적으로 롤백시킨 뒤 audit 테이블에는 row가 남아 있는지 확인.
5. `@TransactionalEventListener(AFTER_COMMIT)` 안에서 `@Transactional` 없이 save → 동작이 어색해지는 케이스 재현. 그다음 `OutboxAppender.appendInNewTransaction`을 `REQUIRES_NEW`로 두고 의도대로 분리되는지 확인.
6. REQUIRED 안쪽에서 RuntimeException을 던지고 바깥에서 catch하여 무시 → 커밋 시점 `UnexpectedRollbackException` 재현.

## 면접 답변 프레이밍

면접에서 트랜잭션 전파가 나오면 답변 골격은 이렇게 잡으면 안전하다.

> "REQUIRED는 같은 작업 단위에 합류하는 기본값이라 비즈니스 로직 대부분에 쓰고, REQUIRES\_NEW는 바깥 트랜잭션과 운명을 분리해야 하는 감사 로그·실패 기록 같은 데에만 제한적으로 씁니다. NESTED는 SAVEPOINT 기반이라 JPA와 같이 쓰면 1차 캐시와 어긋날 수 있어 권장하지 않습니다.
>
> 예외 측면에서는 Spring이 기본적으로 unchecked만 자동 롤백하므로 외부 IO 호출이 있는 메서드는 `rollbackFor`를 명시적으로 잡아 두는 편입니다. 자기 호출 함정도 자주 나오는데, 같은 클래스 내부 호출은 프록시를 우회하기 때문에 트랜잭션이 적용되지 않아서, 트랜잭션 단위가 분리될 만하면 빈을 분리합니다.
>
> 이벤트 발행은 `@TransactionalEventListener(AFTER_COMMIT)`로 직접 publish하는 대신, 도메인 트랜잭션 안에서 outbox row를 같이 저장하고 별도 publisher가 발행하는 Transactional Outbox 패턴을 선호합니다. 이전 프로젝트에서 Kafka Outbox를 도입할 때, 결제 성공 후 알림이 누락되는 사고를 막기 위해 publish를 도메인 트랜잭션과 분리하고 outbox 폴러가 재시도까지 담당하게 한 경험이 있어서 그 구조가 손에 익어 있습니다."

여기서 마지막 한 줄이 본인의 Outbox 경험과 자연스럽게 연결되는 지점이다. 면접관은 보통 이 시점에서 "재시도 멱등성은 어떻게 보장했냐", "outbox 폭증은 어떻게 막았냐", "DLQ는 따로 뒀냐" 같은 후속 질문으로 들어오므로 답변 끝에 이 후속 질문을 유도할 만한 키워드(idempotency key, partition key, DLQ)를 의도적으로 깔아 둔다.

자주 나오는 함정 질문과 짧은 정답:

- "REQUIRES\_NEW만 붙이면 안전한가요?" → 아니다. 새 커넥션을 점유하므로 풀 크기와 자기 자신과의 락 경합을 같이 봐야 한다.
- "self-invocation은 왜 안 되죠?" → AOP 프록시를 거치지 않고 원본 객체 메서드를 직접 호출하기 때문. 빈 분리 또는 `AopContext`로 우회.
- "checked exception이면 자동 롤백 안 되는 이유?" → Spring 기본 정책이 unchecked + Error 한정. EJB 관례에서 유래.
- "AFTER\_COMMIT에서 DB save 하면 되나요?" → 트랜잭션이 이미 닫혔으므로 새 트랜잭션을 명시적으로 열어야 한다.
- "rollbackOnly가 뭐예요?" → REQUIRED 트랜잭션 내부에서 롤백 결정이 나면 매니저가 마킹하고, 호출자가 예외를 삼켜도 커밋 시 `UnexpectedRollbackException`으로 노출된다.

## 체크리스트

- [ ] `@Transactional` 메서드를 같은 클래스 내부에서 호출하지 않는다 (필요하면 빈 분리)
- [ ] 외부 IO를 호출하는 트랜잭션 메서드에는 `rollbackFor`를 명시했다
- [ ] `REQUIRES_NEW`는 실패 로그/감사처럼 운명을 분리해야 하는 곳에만 썼다
- [ ] `REQUIRES_NEW` 호출자는 예외를 catch해 바깥 비즈니스 흐름이 그 실패에 끌려가지 않게 했다
- [ ] `@TransactionalEventListener(AFTER_COMMIT)` 안에서는 직접 발행 대신 outbox 활용을 우선 검토했다
- [ ] AFTER\_COMMIT 안에서 DB를 다시 건드릴 때는 `REQUIRES_NEW`로 새 트랜잭션을 명시적으로 열었다
- [ ] outbox 저장 실패 케이스 자체를 별도 dead-letter 테이블에 `REQUIRES_NEW`로 적재할 경로를 정의했다
- [ ] `transaction.interceptor` TRACE 로그로 propagation이 의도대로 적용되는지 한 번 이상 눈으로 확인했다
- [ ] rollbackOnly / `UnexpectedRollbackException` 시나리오를 직접 재현해 봤다
- [ ] 면접 답변에서 본인 Outbox 경험과 트랜잭션 전파 정책을 한 문단 안에서 자연스럽게 연결할 수 있다

## 관련

- [트랜잭션 전파·격리수준·AFTER_COMMIT 실전](./transaction-propagation-isolation-after-commit.md) — 같은 주제의 일반 개념 문서. 격리수준 + Outbox 흐름까지
