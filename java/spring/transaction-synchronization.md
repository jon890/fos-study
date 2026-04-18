# [초안] Spring TransactionSynchronization 실전: 커밋 이후 외부 호출을 안전하게 묶는 법

## 1. 왜 이 주제가 중요한가

백엔드에서 가장 자주 발생하는 데이터 정합성 사고 중 하나는 **"DB 트랜잭션은 롤백됐는데 외부 알림은 이미 발송된" 상황**이다. 사용자에게 "주문이 접수됐습니다"라는 알림톡은 이미 갔는데, 정작 주문 테이블에는 데이터가 없다. 반대로 "DB에는 저장됐는데 알림이 안 나간" 사고도 흔하다. 두 사고 모두 원인은 같다 — **트랜잭션 경계와 외부 시스템 호출의 경계가 어긋나 있기 때문**이다.

레거시 시스템을 보면 `@Transactional` 메서드 안에서 곧장 알림톡 API를 호출하거나, Kafka producer.send()를 호출하거나, HTTP 웹훅을 쏘는 코드가 흔하게 있다. 평상시에는 잘 동작하는 것처럼 보이지만, DB 제약 위반 한 건, deadlock 한 건, 후속 처리에서 던진 `RuntimeException` 한 건만 있어도 곧바로 정합성이 깨진다. 외부 호출은 본질적으로 **롤백 불가능한 부수 효과**이기 때문이다.

Spring은 이 문제를 정면으로 풀기 위한 훅 시스템을 제공한다. 그것이 `TransactionSynchronization` 이고, `@TransactionalEventListener(phase = AFTER_COMMIT)` 도 내부적으로 같은 메커니즘 위에서 동작한다. 이 글은 그 메커니즘을 분해하고, 어떤 코드를 어떤 시점으로 옮겨야 안전한지, 그리고 그것조차 부족할 때 왜 Outbox 패턴이 필요한지를 실전 코드 수준으로 정리한다.

시니어 백엔드 면접에서 "트랜잭션과 외부 호출을 어떻게 묶으시나요?"는 거의 항상 물어보는 질문이다. 답을 모호하게 하면 주니어로 분류되고, 이 메커니즘과 한계를 함께 말할 수 있으면 시스템 설계 감각이 있는 사람으로 분류된다.

## 2. TransactionSynchronization 메커니즘 — ThreadLocal 기반 훅 시스템

Spring의 트랜잭션 추상화(`PlatformTransactionManager`)는 트랜잭션이 시작되면 현재 스레드에 대해 `TransactionSynchronizationManager`라는 정적 매니저를 활성화한다. 이 매니저는 내부적으로 여러 ThreadLocal을 들고 있으며, 그중 하나가 등록된 `TransactionSynchronization` 콜백 리스트다.

핵심 동작 흐름은 다음과 같다.

1. `@Transactional` 진입 시 `AbstractPlatformTransactionManager.getTransaction()` 이 호출되고, 새 트랜잭션이면 `prepareSynchronization()`이 호출돼 ThreadLocal 콜백 리스트가 초기화된다.
2. 트랜잭션 도중 비즈니스 코드가 `TransactionSynchronizationManager.registerSynchronization(...)` 를 호출하면 콜백이 ThreadLocal에 쌓인다.
3. 트랜잭션이 commit 단계에 들어가면 `triggerBeforeCommit → doCommit → triggerAfterCommit → triggerAfterCompletion(STATUS_COMMITTED)` 순으로 콜백이 호출된다.
4. 롤백 시에는 `triggerBeforeCompletion → doRollback → triggerAfterCompletion(STATUS_ROLLED_BACK)` 순으로 호출된다 (`afterCommit`은 호출되지 않는다).
5. 트랜잭션 종료 후 `clearSynchronization()` 으로 ThreadLocal이 정리된다.

ThreadLocal 기반이라는 사실은 두 가지를 함의한다.

- **콜백 등록 코드가 트랜잭션 컨텍스트 밖에서 실행되면 의미 없는 콜백이 된다.** Spring은 친절하게도 `isSynchronizationActive()`가 false면 등록을 거부하거나 로그로 경고한다.
- **다른 스레드로 작업이 넘어가면 콜백은 따라가지 않는다.** `@Async`, `CompletableFuture.supplyAsync()`, Reactor 의 다른 스케줄러 등으로 넘긴 작업 안에서 외부 호출을 하더라도 부모 트랜잭션의 afterCommit 시점이 보장되지 않는다.

## 3. 네 가지 콜백 시점과 안전성

`TransactionSynchronization` 인터페이스의 주요 콜백은 다음 네 개다.

| 콜백 | 호출 시점 | 안전성 / 위험 |
|------|-----------|---------------|
| `beforeCommit(boolean readOnly)` | flush 직후, 실제 commit SQL 직전 | 여기서 예외를 던지면 트랜잭션이 롤백된다. 추가 검증 적합. 외부 호출은 절대 금지. |
| `beforeCompletion()` | commit/rollback 어느 쪽이든 그 직전 | 리소스 정리(자원 해제, 캐시 비우기) 용도. 예외 던져도 commit/rollback 결정은 바뀌지 않는다. |
| `afterCommit()` | commit이 **성공적으로 끝난 직후** | 외부 시스템 호출의 정석 위치. 단, 여기서 던진 예외는 호출자에게 전파되며 `afterCompletion`까지 영향을 줄 수 있다. |
| `afterCompletion(int status)` | 트랜잭션이 commit이든 rollback이든 종료된 후 | status로 분기 가능. 자원 회수, 메트릭 기록에 적합. |

이 표를 외워두면 면접에서 "왜 afterCommit 안에서 추가 트랜잭션을 다시 열어야 하나요?"라는 질문에 즉답할 수 있다. **afterCommit 시점은 이미 원래 트랜잭션이 끝난 직후라 현재 스레드에 활성 트랜잭션이 없다.** 그 안에서 JPA save를 호출해도 자동 flush되지 않거나, EntityManager가 닫혀 LazyInitializationException을 만나게 된다. 그래서 afterCommit 안에서 DB 작업이 필요하면 `Propagation.REQUIRES_NEW` 로 새 트랜잭션을 명시적으로 열어야 한다.

또 하나 중요한 사실 — `afterCommit`에서 던진 예외는 **이미 커밋된 원본 트랜잭션을 되돌리지 않는다.** 그래서 afterCommit 안의 외부 호출 실패는 별도 보상 로직(재시도 큐, Outbox 등)으로 처리해야지, 예외 전파만으로 해결되지 않는다.

## 4. @TransactionalEventListener의 내부 동작과 한계

Spring 4.2부터 도입된 `@TransactionalEventListener(phase = AFTER_COMMIT)` 은 사실상 위에서 설명한 `TransactionSynchronization` 메커니즘의 얇은 래퍼다. 내부 동작은 이렇다.

1. `ApplicationEventPublisher.publishEvent(event)` 호출 시, `ApplicationListenerMethodTransactionalAdapter` 가 현재 스레드에 활성 트랜잭션이 있는지 확인한다.
2. 활성 트랜잭션이 있으면 `TransactionSynchronizationManager.registerSynchronization()` 를 호출해 phase에 맞는 콜백을 등록한다.
3. 활성 트랜잭션이 없으면 기본적으로 **이벤트가 무시된다**. `fallbackExecution = true` 로 두면 즉시 실행한다.

즉, `@TransactionalEventListener(phase = AFTER_COMMIT)` 의 핵심 한계는 다음과 같다.

- **이벤트 publish 시점에 트랜잭션이 active 해야 한다.** 트랜잭션 밖에서 publish하면 silently 사라진다. 운영 사고로 가장 흔한 케이스.
- **리스너 안에서 새 DB 작업을 하려면 명시적으로 새 트랜잭션을 열어야 한다.** 리스너에 `@Transactional(propagation = REQUIRES_NEW)` 를 추가하지 않으면 JPA save가 의도대로 동작하지 않는다.
- **리스너 메서드는 기본적으로 동기 실행된다.** 같은 스레드에서 commit 직후 실행되므로, 리스너가 5초 걸리면 호출자 응답도 5초 늦어진다. 비동기로 빼려면 `@Async` 를 함께 붙이고 별도 트랜잭션 컨텍스트도 신경 써야 한다.
- **리스너 안에서 던진 예외는 원본 트랜잭션을 롤백하지 못한다.** 이미 커밋된 후이기 때문이다.

## 5. 안티패턴 vs 개선된 패턴

### 5.1 안티패턴 — @Transactional 안에서 직접 외부 호출

```java
@Service
@RequiredArgsConstructor
public class OrderServiceBad {

    private final OrderRepository orderRepository;
    private final AlimtalkClient alimtalkClient;

    @Transactional
    public void placeOrder(OrderCommand cmd) {
        Order order = Order.from(cmd);
        orderRepository.save(order);

        alimtalkClient.send(order.getCustomerPhone(),
            "주문이 접수되었습니다. 주문번호: " + order.getId());

        applyPostProcessing(order);
    }
}
```

이 코드의 문제는 두 가지 시나리오에서 명확하게 드러난다.

- `applyPostProcessing()` 에서 예외가 발생하면 트랜잭션은 롤백되지만 알림톡은 이미 발송된 상태다. 사용자는 "주문 접수" 알림을 받았지만 시스템에는 주문이 없다.
- `alimtalkClient.send()` 가 외부 API 지연으로 5초 걸리면 트랜잭션이 5초간 열려있고, DB 커넥션 풀과 row lock이 그동안 점유된다. TPS가 폭락한다.

### 5.2 개선된 패턴 — afterCommit 훅 + REQUIRES_NEW로 실패 보존

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    public void placeOrder(OrderCommand cmd) {
        Order order = Order.from(cmd);
        orderRepository.save(order);

        eventPublisher.publishEvent(
            new OrderPlacedEvent(order.getId(), order.getCustomerPhone()));
    }
}

@Component
@RequiredArgsConstructor
public class OrderNotificationListener {

    private final AlimtalkClient alimtalkClient;
    private final FailedNotificationRepository failedRepo;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void onOrderPlaced(OrderPlacedEvent event) {
        try {
            alimtalkClient.send(event.phone(),
                "주문이 접수되었습니다. 주문번호: " + event.orderId());
        } catch (Exception e) {
            failedRepo.save(FailedNotification.of(
                event.orderId(), event.phone(), e.getMessage()));
        }
    }
}
```

핵심 변화는 다음과 같다.

- 외부 호출이 commit **이후** 시점으로 이동했다. 롤백된 주문에 대한 알림은 절대 나가지 않는다.
- 외부 호출이 실패하면 `FailedNotification` 테이블에 기록되며, 이 저장은 별도의 `REQUIRES_NEW` 트랜잭션이라 외부 호출 결과와 독립적으로 commit된다.
- DB 트랜잭션은 짧게 유지된다. 외부 API 응답을 기다리는 동안 row lock을 잡고 있지 않는다.

## 6. TransactionSynchronizationManager.registerSynchronization() 직접 사용

`@TransactionalEventListener` 가 추상화 위에서 충분히 깔끔하지만, 제어가 더 필요할 때는 저수준 API를 직접 쓴다. 다음은 "이 트랜잭션이 정말 commit되면 그때 Kafka에 발행하라"를 명시적으로 표현하는 예다.

```java
@Service
@RequiredArgsConstructor
public class PaymentEventPublisher {

    private final KafkaTemplate<String, String> kafka;

    public void publishAfterCommit(String topic, String payload) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            kafka.send(topic, payload);
            return;
        }

        TransactionSynchronizationManager.registerSynchronization(
            new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    kafka.send(topic, payload);
                }

                @Override
                public void afterCompletion(int status) {
                    if (status == STATUS_ROLLED_BACK) {
                        log.info("transaction rolled back, skip kafka publish: {}", topic);
                    }
                }
            });
    }
}
```

이 패턴은 라이브러리/공통 컴포넌트에서 주로 쓴다. 호출자가 트랜잭션 안에서 호출하든 밖에서 호출하든 모두 안전하게 동작하도록 방어한다는 점에서, 이벤트 기반보다 결합도가 낮아 재사용이 쉽다.

## 7. Hibernate 이벤트 리스너와의 비교

Hibernate에는 자체 이벤트 시스템이 있고, `PostCommitInsertEventListener`, `PostCommitUpdateEventListener` 같은 인터페이스를 제공한다. Spring의 `TransactionSynchronization` 과 비교하면 결정적인 차이가 있다.

- **레벨이 다르다.** Hibernate 리스너는 ORM 레벨이라, JdbcTemplate, MyBatis 같은 다른 데이터 액세스 경로에서 일어난 변경은 잡지 못한다. Spring 트랜잭션 동기화는 트랜잭션 매니저 레벨이라 모든 데이터 액세스 경로의 commit을 잡는다.
- **트랜잭션 경계와 일치하지 않는다.** Hibernate 리스너는 Hibernate Session/EntityManager 단위로 동작하고, Session이 commit 직후 발화한다. 하지만 Spring 트랜잭션 안에 여러 Session이 끼어들거나 nested 트랜잭션이 있으면 정확히 매칭되지 않는다.
- **테스트 가능성**. Spring 동기화는 `@Transactional` 테스트에서 롤백되므로 afterCommit이 호출되지 않는다. Hibernate `PostCommit*` 도 마찬가지로 호출되지 않는다. 둘 다 통합 테스트에서 의도적으로 commit을 일으켜야 검증 가능하다.

실무에서는 ORM 외 경로(예: 배치 JdbcTemplate)도 알림 대상이 될 가능성이 크기 때문에, Hibernate 리스너보다 Spring 동기화 + 이벤트 패턴을 일관되게 쓰는 편이 안전하다.

## 8. 분산 트랜잭션의 한계와 Outbox 패턴

afterCommit 패턴이 만능은 아니다. 다음 시퀀스를 보자.

1. DB commit 성공
2. afterCommit 콜백 시작
3. Kafka 발행 직전 애플리케이션 프로세스 강제 종료 (OOM kill, 배포 중 SIGTERM, 인스턴스 장애)

이 경우 DB에는 데이터가 들어갔지만 Kafka에는 메시지가 없다. **메모리 안의 콜백은 프로세스가 죽으면 사라진다.** 즉, "DB 커밋"과 "외부 발행"의 원자성은 같은 프로세스 안의 훅으로는 보장되지 않는다.

이 한계가 곧 **Transactional Outbox 패턴**의 존재 이유다. 핵심 아이디어는 단순하다.

1. 비즈니스 트랜잭션 안에서 도메인 데이터와 함께 `outbox` 테이블에 발행할 메시지를 같은 트랜잭션으로 INSERT한다. 이때 두 INSERT는 **하나의 DB 트랜잭션이라 원자적으로 commit된다.**
2. 별도 발행 워커(스케줄러나 CDC 기반)가 outbox 테이블을 읽어 Kafka에 발행하고, 성공 시 outbox row를 처리 완료로 마크한다.
3. 워커가 죽었다 살아나도 outbox에 남은 미처리 row를 다시 읽어 발행한다. **At-least-once 보장.**

afterCommit 훅은 빠르고 단순한 케이스에 적합하고, 정합성이 진짜로 중요한 도메인(결제, 주문, 회계)에는 Outbox로 한 단계 더 강화한다. 면접에서는 이 두 가지를 같이 설명할 수 있어야 한다.

## 9. 레거시 현대화 관점 — 어떤 직결 호출을 감싸는가

레거시 코드를 마이그레이션할 때 가장 자주 만나는 패턴은 다음과 같다.

- 결제 완료 처리 안에서 알림톡 직접 호출
- 회원 가입 트랜잭션 안에서 환영 이메일 SMTP 직접 호출
- 주문 처리 안에서 외부 SCM 시스템 HTTP API 직접 호출
- 게시글 등록 안에서 검색 엔진 색인 API 직접 호출

이런 코드를 단숨에 Outbox로 옮기는 것은 비용이 크다. 1차 단계로 `@TransactionalEventListener(AFTER_COMMIT)` 패턴으로 옮기면, 코드 변경 범위는 작으면서도 다음 효과를 즉시 얻는다.

- DB 롤백 시 알림이 나가지 않는다 (정합성 사고 1번 차단)
- 외부 호출 지연이 트랜잭션에 영향을 주지 않는다 (TPS 안정화)
- 외부 호출 실패가 별도 테이블에 남아 재시도 가능해진다 (운영 가시성 확보)

이후 트래픽과 정합성 요구가 더 강해지면 같은 이벤트 인터페이스를 유지한 채 발행 측을 Outbox로 교체하는 식으로 점진적 진화가 가능하다.

## 10. 로컬 실습 환경

```yaml
# docker-compose.yml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: txsync
    ports:
      - "3306:3306"
```

`build.gradle` 의존성:

```gradle
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-web'
    runtimeOnly 'com.mysql:mysql-connector-j'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
```

스키마:

```sql
CREATE TABLE orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_phone VARCHAR(20) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE failed_notifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    phone VARCHAR(20) NOT NULL,
    error_message TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    last_tried_at DATETIME(6),
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL,
    INDEX idx_resolved_retry (resolved, retry_count)
) ENGINE=InnoDB;
```

## 11. 실행 가능한 풀 예제 — 알림 발행 + 실패 저장 + 스케줄러 재전송

도메인 이벤트:

```java
public record OrderPlacedEvent(Long orderId, String phone) {}
```

비즈니스 서비스:

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    public Long placeOrder(String phone, BigDecimal amount) {
        Order order = Order.create(phone, amount);
        orderRepository.save(order);

        eventPublisher.publishEvent(new OrderPlacedEvent(order.getId(), phone));
        return order.getId();
    }
}
```

알림 리스너:

```java
@Component
@RequiredArgsConstructor
@Slf4j
public class OrderNotificationListener {

    private final AlimtalkClient alimtalkClient;
    private final FailedNotificationRepository failedRepo;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void onOrderPlaced(OrderPlacedEvent event) {
        try {
            alimtalkClient.send(event.phone(),
                "주문이 접수되었습니다. 주문번호: " + event.orderId());
        } catch (Exception e) {
            log.warn("알림 발송 실패. 보상 큐에 적재: orderId={}", event.orderId(), e);
            failedRepo.save(FailedNotification.of(
                event.orderId(), event.phone(), e.getMessage()));
        }
    }
}
```

재전송 스케줄러:

```java
@Component
@RequiredArgsConstructor
@Slf4j
public class FailedNotificationRetryJob {

    private static final int MAX_RETRY = 5;
    private final FailedNotificationRepository failedRepo;
    private final AlimtalkClient alimtalkClient;

    @Scheduled(fixedDelay = 30_000)
    @Transactional
    public void retry() {
        List<FailedNotification> targets =
            failedRepo.findTop100ByResolvedFalseAndRetryCountLessThanOrderByIdAsc(MAX_RETRY);

        for (FailedNotification n : targets) {
            try {
                alimtalkClient.send(n.getPhone(),
                    "주문이 접수되었습니다. 주문번호: " + n.getOrderId());
                n.markResolved();
            } catch (Exception e) {
                n.incrementRetry(e.getMessage());
                log.warn("재전송 실패: id={}, count={}", n.getId(), n.getRetryCount());
            }
        }
    }
}
```

검증 시나리오:

1. 정상 흐름 — `placeOrder()` 호출 → orders INSERT → commit → afterCommit 발화 → 알림 발송 OK.
2. 외부 API 다운 — `AlimtalkClient` 가 예외를 던지도록 stub → orders는 commit, failed_notifications에 row 1건 적재.
3. 비즈니스 롤백 — `placeOrder()` 끝부분에 강제 RuntimeException 추가 → orders 롤백, afterCommit 미호출, 알림 미발송.
4. 스케줄러 재전송 — failed_notifications에 적재된 row가 30초 뒤 재시도되어 resolved=true 마킹.

이 네 가지를 통합 테스트로 자동화하면 면접에서 "직접 검증해봤다"고 말할 근거가 생긴다.

## 12. 면접 답변 프레이밍

**Q. 외부 알림을 트랜잭션과 어떻게 묶으시나요?**

> 핵심은 외부 호출이 본질적으로 롤백 불가능한 부수 효과라는 점입니다. 그래서 저는 외부 호출을 `@Transactional` 메서드 안에서 직접 호출하지 않고, Spring의 `@TransactionalEventListener(phase = AFTER_COMMIT)` 으로 commit 이후 시점에 호출되도록 분리합니다. 이 리스너는 내부적으로 `TransactionSynchronizationManager.registerSynchronization()` 의 afterCommit 훅 위에서 동작하고, ThreadLocal에 등록된 콜백을 commit 성공 직후 실행합니다. 이렇게 하면 DB 롤백이 일어난 경우 알림이 나가지 않는 정합성을 1차로 확보할 수 있습니다.

**Q. 그 안에서 또 DB 작업이 필요하면요?**

> afterCommit 시점은 이미 원래 트랜잭션이 종료된 직후라 활성 트랜잭션이 없습니다. 그래서 리스너에 `@Transactional(propagation = REQUIRES_NEW)` 를 명시해 새 트랜잭션을 엽니다. 외부 호출 실패를 보상 테이블에 기록할 때 이 propagation이 반드시 필요합니다.

**Q. 커밋은 됐는데 외부 호출이 실패하면요?**

> 그 경우는 보상 패턴이 필요합니다. afterCommit 안에서 try-catch로 잡고 실패 메시지를 별도 테이블에 적재한 뒤, 스케줄러가 일정 주기로 재시도합니다. 다만 프로세스가 afterCommit 콜백 실행 직전에 죽으면 메모리 안의 훅이 통째로 사라지기 때문에, 진짜 정합성이 중요한 도메인은 Outbox 패턴으로 한 단계 더 강화합니다. 비즈니스 트랜잭션 안에서 메시지를 outbox 테이블에 같이 INSERT해 원자적으로 commit하고, 별도 워커가 그걸 읽어 Kafka에 발행하는 구조입니다.

**Q. 레거시에서 어떻게 이걸 도입하셨나요?**

> 직결 호출을 한 번에 Outbox로 옮기는 건 비용이 커서, 1차로 `@TransactionalEventListener(AFTER_COMMIT)` 만 도입했습니다. 코드 변경 범위는 작으면서 롤백 시 알림 누수, 외부 지연으로 인한 트랜잭션 점유, 실패 후 운영 가시성 부재 같은 가장 심각한 사고 패턴들을 동시에 막을 수 있었습니다. 이후 트래픽이 더 커지면서 같은 이벤트 인터페이스를 유지한 채 발행 측만 Kafka Outbox로 교체했습니다.

## 13. 체크리스트

- [ ] `@Transactional` 메서드 안에서 외부 시스템(HTTP, Kafka, SMTP, SMS) 직접 호출이 남아있지 않은가
- [ ] 외부 호출 위치가 `@TransactionalEventListener(AFTER_COMMIT)` 또는 `registerSynchronization()` 의 afterCommit 으로 옮겨져 있는가
- [ ] 리스너 안에서 DB 작업이 있다면 `@Transactional(propagation = REQUIRES_NEW)` 가 명시돼 있는가
- [ ] 이벤트 publish 시점이 트랜잭션 active 상태인지 확인했는가 (트랜잭션 밖 publish는 silently 사라진다)
- [ ] 외부 호출 실패 시 보상 큐(failed_notifications 등)로 들어가는가
- [ ] 보상 큐 재시도 스케줄러와 max retry / dead letter 처리 정책이 정의돼 있는가
- [ ] 통합 테스트에서 정상 / 외부 실패 / 비즈니스 롤백 세 시나리오가 모두 검증되는가
- [ ] 진짜 정합성이 요구되는 도메인은 Outbox 패턴 도입 검토가 진행됐는가
- [ ] afterCommit 콜백이 호출되는 트랜잭션 매니저가 실제 운영 환경의 트랜잭션 매니저와 동일한지 확인했는가 (멀티 데이터소스 환경 주의)
- [ ] 비동기 처리(`@Async`, 별도 스레드)로 넘긴 작업 안에서 부모 트랜잭션의 afterCommit을 기대하고 있지는 않은가
