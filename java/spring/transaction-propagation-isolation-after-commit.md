# [초안] Spring 트랜잭션 전파·격리수준·AFTER_COMMIT 실전 정리: Outbox까지 이어지는 한 덩어리

## 왜 이 주제가 중요한가

시니어 백엔드 면접에서 "트랜잭션 아세요?"라는 질문은 거의 나오지 않는다. 대신 이런 형태로 들어온다.

- "주문이 성공했는데 쿠폰이 안 빠졌어요. 어디부터 볼까요?"
- "결제 승인 이후 Kafka 이벤트가 유실됐는데, 트랜잭션과 어떤 관계가 있을까요?"
- "트랜잭션 안에서 외부 API 호출하면 왜 위험하죠?"
- "`REQUIRES_NEW`를 언제 써봤어요?"

이 질문들은 전부 같은 축을 타고 있다. **트랜잭션 경계가 어디서 시작하고 어디서 끝나는지, 커밋이 완료된 시점이 언제인지, 그리고 커밋 이후 외부 시스템과 어떻게 정렬할 것인지.** CJ 올리브영 Wellness 플랫폼처럼 주문·결제·적립·알림·재고·쿠폰이 동시에 움직이는 도메인에서는 이 축을 놓치는 순간 바로 장애로 이어진다. 주니어는 `@Transactional`을 붙이는 수준이지만, 시니어는 **트랜잭션 경계 밖으로 무엇을 밀어낼지 결정하는 사람**이다.

이 문서는 전파(propagation), 격리수준(isolation), AFTER_COMMIT 훅, Outbox 패턴을 하나의 맥락으로 엮는다. 각 개념을 따로 외우지 말고, "트랜잭션 커밋 전/후로 무엇을 배치할 것인가"라는 축 위에 순서대로 얹어라.

## 트랜잭션이 보호하는 것, 보호하지 못하는 것

먼저 오해를 벗겨야 한다. `@Transactional`은 **만능 가드가 아니다.**

트랜잭션이 보호하는 것:
- 같은 DB 내의 여러 SQL을 원자적 단위(ACID의 A)로 묶어준다.
- 롤백 시 INSERT/UPDATE/DELETE를 되돌린다.
- 같은 커넥션을 공유해 isolation level이 보장하는 가시성 규칙을 적용한다.

트랜잭션이 **보호하지 못하는 것**:
- HTTP 호출, Kafka 발행, 이메일 발송 같은 **외부 I/O는 롤백되지 않는다.** 메시지는 이미 나갔다.
- 다른 DB 소스, 다른 서비스의 트랜잭션은 묶이지 않는다 (분산 트랜잭션 별도 주제).
- 애플리케이션 프로세스가 커밋 직전에 죽으면, DB는 롤백되지만 "내가 이 일을 하려 했다"는 의도는 사라진다.
- 스레드풀에 다른 작업으로 넘긴 경우(`@Async`, `CompletableFuture.runAsync`) — 그 작업은 **호출자의 트랜잭션과 분리된다.**

이 두 번째 목록이 Outbox 패턴과 AFTER_COMMIT 훅이 존재하는 이유 그 자체다. "DB에 커밋했다"와 "Kafka에 발행했다"를 어떻게 원자적으로 묶을 것인가 — 정답은 "완벽히 묶을 수 없으니, 한쪽을 DB에 위임하고 나머지를 커밋 이후로 미룬다"이다.

## 핵심 개념: 전파(Propagation)

전파는 **"현재 스레드에 이미 활성 트랜잭션이 있을 때, 지금 호출되는 메서드가 어떻게 행동할지"** 를 결정한다. 즉 전파는 혼자 동작하는 설정이 아니라 **호출 체인 안에서의 규칙**이다.

### REQUIRED (기본값)

기존 트랜잭션이 있으면 참여(join), 없으면 새로 시작. 99%의 서비스 메서드가 이것으로 충분하다.

```java
@Transactional // REQUIRED
public void placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.of(cmd));
    inventoryService.decrease(cmd.items()); // 같은 트랜잭션에 참여
    pointService.deduct(cmd.userId(), cmd.pointUsage()); // 같은 트랜잭션에 참여
}
```

여기서 `inventoryService.decrease`가 실패하면 `placeOrder` 전체가 롤백된다. 이것이 REQUIRED의 핵심이다 — **하나의 논리적 작업 단위.**

### REQUIRES_NEW

기존 트랜잭션을 **일시 정지(suspend)** 시키고 **완전히 새로운 트랜잭션**을 시작. 새 트랜잭션이 커밋/롤백되어도 **바깥 트랜잭션은 영향을 받지 않는다.**

언제 써야 하는가:
- 감사 로그(audit log), 실패 이력 같이 **바깥이 롤백되어도 반드시 남겨야 하는 기록.**
- 바깥 트랜잭션과 성공/실패 결정을 분리하고 싶을 때.

```java
@Service
public class OrderFailureLogger {
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void logFailure(Long orderId, String reason) {
        failureLogRepository.save(new FailureLog(orderId, reason));
    }
}
```

이렇게 해두면 `placeOrder`가 롤백되어도 `FailureLog`는 살아남는다.

**주의**: `REQUIRES_NEW`는 새 DB 커넥션을 잡는다. 기존 커넥션은 풀에 반납되지 않고 suspend 상태로 유지되므로 **한 스레드가 동시에 2개의 커넥션을 점유**한다. 트래픽 많은 엔드포인트에서 남용하면 커넥션풀 고갈로 이어진다.

### NESTED

JDBC `SAVEPOINT`를 사용한 중첩 트랜잭션. 내부가 롤백되면 savepoint 지점까지만 되돌리고, 바깥은 계속 진행 가능. JPA + Hibernate에서는 JDBC 드라이버가 savepoint를 지원해야 쓸 수 있고, 실무에선 **거의 안 쓴다**. 알고는 있되 선택하지 말 것.

### SUPPORTS / NOT_SUPPORTED / MANDATORY / NEVER

- `SUPPORTS`: 있으면 참여, 없으면 non-transactional 실행. 읽기 전용 유틸 메서드에 간혹.
- `NOT_SUPPORTED`: 기존 트랜잭션 suspend, 자기는 non-transactional. 리포트성 대량 조회에서 드물게.
- `MANDATORY`: 반드시 기존 트랜잭션이 있어야 함. 없으면 예외. 내부 서비스용 방어 코드.
- `NEVER`: 기존 트랜잭션이 있으면 예외.

**면접 체감 빈도**: REQUIRED >> REQUIRES_NEW >> 나머지. NESTED는 "설명은 할 수 있지만 쓴 적 없다"가 정답에 가깝다.

## 격리수준(Isolation Level) — MySQL/InnoDB 기준

격리수준은 **동시에 실행되는 다른 트랜잭션의 변경을 내 트랜잭션이 얼마나 볼 수 있는지**를 결정한다. 표준 SQL은 4단계를 정의하고 InnoDB는 모두 지원하지만, 동작 방식이 교과서와 살짝 다르다.

### READ UNCOMMITTED
다른 트랜잭션의 커밋되지 않은 변경까지 읽는다. **Dirty read** 발생. 사실상 쓰지 않는다.

### READ COMMITTED
커밋된 것만 읽는다. 같은 쿼리를 두 번 실행하면 그 사이 다른 트랜잭션이 커밋한 값이 보일 수 있음 → **Non-repeatable read** 발생. Oracle, PostgreSQL의 기본값.

### REPEATABLE READ (InnoDB 기본값)
트랜잭션 시작 시점의 스냅샷을 계속 본다(Consistent Nonlocking Read, MVCC). 같은 SELECT를 여러 번 해도 같은 결과.
- 표준 정의로는 Phantom read가 발생할 수 있지만, **InnoDB는 gap lock + next-key lock으로 phantom도 상당 부분 막는다.** 이게 InnoDB REPEATABLE READ의 특이점이다.
- 하지만 이 gap lock이 **교착(deadlock)의 주원인**이 되기도 한다.

### SERIALIZABLE
모든 SELECT에 암묵적 공유 락. 사실상 순차 실행. 처리량 급감. 실무에서 전 구간에 쓰는 경우는 거의 없고, 특정 크리티컬 트랜잭션에만 한정 적용.

### 이상 현상 3종 — Spring + MySQL 예시로

**Dirty read**: READ UNCOMMITTED에서만. 실무에서 안 만난다.

**Non-repeatable read**: 같은 행을 두 번 읽었는데 값이 바뀜.
```java
@Transactional(isolation = Isolation.READ_COMMITTED)
public BigDecimal calculate(Long accountId) {
    Account a1 = accountRepository.findById(accountId).orElseThrow(); // 잔액 10000
    externalRiskCheck(); // 이 사이 다른 트랜잭션이 잔액을 5000으로 변경 후 커밋
    Account a2 = accountRepository.findById(accountId).orElseThrow(); // 잔액 5000
    return a1.balance().subtract(a2.balance()); // 0이 아님!
}
```
REPEATABLE READ라면 a1, a2 모두 10000으로 읽힌다.

**Phantom read**: 같은 범위 조건으로 두 번 조회했는데 새로운 행이 나타남. InnoDB REPEATABLE READ에서는 MVCC snapshot 덕분에 순수 SELECT에서는 거의 발생하지 않지만, `SELECT ... FOR UPDATE` 같은 locking read에서는 gap lock이 없으면 나타날 수 있다.

### 실무 선택 가이드
- **그냥 InnoDB 기본 REPEATABLE READ를 유지**하고, 특정 트랜잭션에서만 필요하면 `@Transactional(isolation = ...)`으로 덮어쓴다.
- 일부 팀은 READ COMMITTED로 전역 설정한다 (gap lock 감소, 락 경합 완화, PostgreSQL과 동일한 모델). 이 선택은 **애플리케이션 레벨에서 낙관적/비관적 락을 어떻게 설계하느냐와 트레이드오프**다.
- 격리수준만으로 race condition을 해결하려 하지 말고, `SELECT ... FOR UPDATE`(비관적 락), `@Version`(낙관적 락), Redis 분산락 같은 명시적 동시성 제어를 병행하라.

## AFTER_COMMIT — 커밋 이후로 일을 미루는 기술

### 왜 필요한가

다음 코드는 흔한 함정이다.

```java
@Transactional
public void createOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.of(cmd));
    kafkaTemplate.send("order-created", new OrderCreatedEvent(order.getId())); // ⚠️
}
```

문제:
1. `kafkaTemplate.send`가 먼저 실행되고 그 뒤 DB 커밋 직전에 예외가 터지면 — **Kafka는 이미 나갔고 DB는 롤백.** 컨슈머는 존재하지 않는 주문을 받는다.
2. `kafkaTemplate.send`가 네트워크 타임아웃으로 오래 걸리면 — **DB 트랜잭션이 그만큼 길게 열려 있다.** 락을 쥔 채로.
3. 커밋 직전에 다른 리스너가 예외를 던지면 — Kafka는 나갔지만 DB는 롤백.

근본 원인은 **"DB에 안전하게 저장되었다"가 확정되기도 전에 외부 시스템에 알렸다**는 것이다.

### TransactionSynchronization

Spring은 트랜잭션 생명주기에 훅을 걸 수 있다. 저수준 API는 `TransactionSynchronization`이며 메서드는 다음과 같다.

- `beforeCommit(readOnly)` — 커밋 직전. 여기서 예외 던지면 전체 롤백.
- `beforeCompletion()` — 커밋/롤백 결정 직전.
- `afterCommit()` — **커밋 성공 후**. 여기서 예외가 나도 DB는 이미 커밋됨 (되돌릴 수 없음).
- `afterCompletion(status)` — 최종. 커밋이든 롤백이든 실행.

```java
TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
    @Override
    public void afterCommit() {
        kafkaTemplate.send("order-created", new OrderCreatedEvent(orderId));
    }
});
```

### @TransactionalEventListener(phase = AFTER_COMMIT)

실무에서는 저수준 API 대신 Spring 이벤트 모델을 쓴다.

```java
@Service
@RequiredArgsConstructor
public class OrderService {
    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher publisher;

    @Transactional
    public void createOrder(OrderCommand cmd) {
        Order order = orderRepository.save(Order.of(cmd));
        publisher.publishEvent(new OrderCreatedEvent(order.getId()));
    }
}

@Component
@RequiredArgsConstructor
public class OrderEventHandler {
    private final KafkaTemplate<String, Object> kafkaTemplate;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onOrderCreated(OrderCreatedEvent event) {
        kafkaTemplate.send("order-created", event);
    }
}
```

이제 Kafka 발행은 **DB 커밋이 성공한 뒤에만** 실행된다. 커밋 실패 시 이벤트는 발행되지 않는다. 이 패턴 하나로 "유령 이벤트" 버그의 상당수가 사라진다.

### AFTER_COMMIT의 안전성 경계 — 여기가 함정이다

`@TransactionalEventListener(AFTER_COMMIT)`는 **DB 커밋이 완료된 후** 같은 스레드에서 실행된다. 주의할 점:

1. **리스너 내부의 DB 작업은 기본적으로 non-transactional.** 이미 바깥 트랜잭션은 커밋되어 끝났다. 이 시점에 `@Transactional` 없이 `repository.save(...)`를 호출하면 각 쿼리가 별도 커넥션/auto-commit으로 나간다.
2. 리스너에서 **새로운 트랜잭션이 필요하면 반드시 `REQUIRES_NEW`** 로 명시해야 한다. `REQUIRED`로 해도 이미 활성 트랜잭션이 없으니 새로 시작하긴 하지만, 의도를 명확히 하려면 `REQUIRES_NEW`가 낫다.
3. **리스너에서 예외가 나면 커밋된 DB는 되돌릴 수 없다.** 이 시점에 실패하면 "주문은 생겼는데 Kafka 이벤트는 실패"라는 상태가 된다.

```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void onOrderCreated(OrderCreatedEvent event) {
    outboxRepository.save(OutboxEntry.from(event)); // 별도 트랜잭션
    // 이 트랜잭션이 실패해도 주문은 이미 커밋된 상태
}
```

이 예시가 중요한 이유는 다음 섹션에서 드러난다.

## Outbox 패턴 — DB와 Kafka를 "정렬"하는 방법

AFTER_COMMIT만으로는 부족한 이유: **커밋 직후, Kafka 발행 직전에 프로세스가 죽으면?** 이벤트는 영영 나가지 않는다. AFTER_COMMIT은 "커밋되지 않은 이벤트가 나가는 것"은 막지만, "커밋된 이벤트가 누락되는 것"은 막지 못한다.

해결: **이벤트 자체를 DB에 먼저 저장한다.** 같은 트랜잭션 안에.

```java
@Transactional
public void createOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.of(cmd));
    outboxRepository.save(OutboxEntry.builder()
        .aggregateType("Order")
        .aggregateId(order.getId().toString())
        .eventType("OrderCreated")
        .payload(serialize(new OrderCreatedEvent(order.getId())))
        .status(OutboxStatus.PENDING)
        .createdAt(Instant.now())
        .build());
}
```

주문 저장과 Outbox 저장이 **같은 트랜잭션**에 있으므로 둘 다 성공하거나 둘 다 롤백된다. 이제 별도 워커(polling 또는 CDC)가 `PENDING` 상태 outbox를 읽어 Kafka로 발행하고 `PUBLISHED`로 마킹한다.

```java
@Scheduled(fixedDelay = 500)
public void dispatchOutbox() {
    List<OutboxEntry> pending = outboxRepository.findTopNByStatusOrderByCreatedAt(
        OutboxStatus.PENDING, 100);
    for (OutboxEntry entry : pending) {
        try {
            kafkaTemplate.send(entry.topic(), entry.payload()).get(3, TimeUnit.SECONDS);
            markPublished(entry.getId());
        } catch (Exception e) {
            incrementRetry(entry.getId(), e.getMessage());
        }
    }
}
```

### AFTER_COMMIT과 Outbox는 어떤 관계인가

- **AFTER_COMMIT**은 "커밋 실패 시 이벤트 누출을 막는다."
- **Outbox**는 "커밋 성공 후 이벤트 유실을 막는다."

이 둘을 같이 쓴다. Outbox 저장은 메인 트랜잭션 안에서, Outbox dispatch는 **별도의 워커 트랜잭션**에서. 후자는 재시도 가능해야 하므로 consumer 쪽이 **멱등(idempotent)** 해야 한다. `eventId`(UUID)를 메시지에 심고 컨슈머가 중복 체크하는 것이 일반적이다.

### Graceful shutdown과의 연결

Kafka Outbox dispatch 워커가 돌고 있는데 배포가 걸려서 SIGTERM이 들어오면?
- `@Scheduled`로 돌고 있는 작업이 한창 `kafkaTemplate.send().get(...)`을 기다리는 중이라면 — `ExecutorService.shutdown()` 후 적절한 `awaitTermination`이 없으면 요청은 중간에 끊긴다.
- Spring Boot `spring.lifecycle.timeout-per-shutdown-phase`와 `server.shutdown=graceful`을 걸어 HTTP 인바운드는 막고, 내부 워커는 **진행 중인 작업을 마칠 시간**을 준다.
- 이미 DB에 outbox가 남아 있으므로, 다음 인스턴스가 뜨면 `PENDING`을 다시 집어 재발행한다 — **이 재시도 안전성이 Outbox 패턴을 쓰는 궁극적 이유다.**

## 실전 Bad vs Improved

### Bad 1: 트랜잭션 안에서 외부 API 호출

```java
@Transactional
public void approvePayment(Long paymentId) {
    Payment p = paymentRepository.findById(paymentId).orElseThrow();
    PgResponse res = pgClient.approve(p.toPgRequest()); // ⚠️ 수 초 걸릴 수 있음
    p.markApproved(res.approvalNumber());
}
```
문제: PG 응답이 3초 걸리면 DB row에 락을 3초간 쥔다. 동시 주문 트래픽에서 락 경합 폭발. PG가 타임아웃 나면 트랜잭션 롤백되지만 **PG는 이미 승인 처리**된 경우도 있음.

### Improved 1: 외부 I/O를 트랜잭션 밖으로

```java
public void approvePayment(Long paymentId) {
    Payment p = paymentService.loadForApproval(paymentId); // 짧은 @Transactional(readOnly=true)
    PgResponse res = pgClient.approve(p.toPgRequest()); // 트랜잭션 밖
    paymentService.persistApproval(paymentId, res); // 별도 짧은 @Transactional
}
```

### Bad 2: self-invocation

```java
@Service
public class OrderService {
    public void placeOrder(OrderCommand cmd) {
        saveOrder(cmd); // this.saveOrder → 프록시 통과 안 함 → @Transactional 무시됨!
    }
    @Transactional
    public void saveOrder(OrderCommand cmd) { ... }
}
```
Spring AOP는 프록시 기반이므로 같은 빈 내부 호출은 어노테이션이 먹지 않는다.

### Improved 2: 분리 또는 self-injection

클래스를 둘로 쪼개거나, 같은 빈을 주입해 프록시 경유 호출을 강제한다. 실무에서는 **도메인 서비스와 응용 서비스를 분리**하는 쪽이 깔끔하다.

### Bad 3: REQUIRES_NEW 남용

```java
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void saveAuditLog(...) { ... }
```
감사 로그는 맞는데, 이걸 **모든 단건 저장에 걸면** 한 요청이 3~4개의 커넥션을 동시 점유한다. 커넥션풀 20개짜리 DB에서 동시 요청 5건만 와도 poolExhausted.

### Improved 3: REQUIRES_NEW는 "바깥 롤백과 결정이 분리되어야 하는 경우"에만

실패 이력, 결제 승인 로그처럼 "바깥이 망해도 반드시 남겨야 하는" 기록에만 한정한다.

### Bad 4: 긴 트랜잭션

```java
@Transactional
public void bulkMigrate() {
    for (Long id : allIds) { // 100만 건
        processOne(id);
    }
}
```
undo log 폭증, 락 보유 시간 폭증, 장애 시 롤백만 수십 분.

### Improved 4: 배치 단위로 커밋

```java
public void bulkMigrate() {
    for (List<Long> chunk : Lists.partition(allIds, 500)) {
        migrationService.processChunk(chunk); // 청크 단위 @Transactional
    }
}
```

## 로컬 실습 환경

MySQL 8 기준 도커 컴포즈:

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: txlab
    ports: ["3306:3306"]
    command: --transaction-isolation=REPEATABLE-READ
```

두 개의 MySQL 세션(터미널 또는 DBeaver 두 개)을 열고 다음을 재현해본다.

```sql
-- 세션 A
START TRANSACTION;
SELECT balance FROM account WHERE id = 1;

-- 세션 B
START TRANSACTION;
UPDATE account SET balance = balance - 5000 WHERE id = 1;
COMMIT;

-- 세션 A
SELECT balance FROM account WHERE id = 1; -- 여전히 원래 값 (REPEATABLE READ snapshot)
COMMIT;
```

그 다음 세션 A를 `SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;`로 바꾸고 같은 시나리오를 돌리면 두 번째 SELECT 결과가 바뀐다 — non-repeatable read의 실체.

Spring Boot 샘플 프로젝트에서는 `application.yml`에:
```yaml
logging:
  level:
    org.springframework.transaction.interceptor: TRACE
    org.hibernate.SQL: DEBUG
```
로그에서 `Creating new transaction`, `Participating in existing transaction`, `Suspending current transaction` 메시지를 직접 확인하면 전파 동작이 머릿속에 각인된다.

## 면접 답변 프레임

### 1분 버전

> "`@Transactional`은 DB 원자성을 보장하지만 외부 시스템 호출까지 보호하지 않습니다. 그래서 저는 트랜잭션 경계를 짧게 유지하고, Kafka 발행이나 외부 API 호출은 `@TransactionalEventListener(AFTER_COMMIT)` 또는 Outbox 패턴으로 DB 커밋 이후로 미룹니다. 격리수준은 InnoDB 기본인 REPEATABLE READ를 기준으로 가고, 동시성 제어는 격리수준이 아니라 락이나 버전 컬럼으로 명시적으로 설계합니다. 전파 옵션은 REQUIRED를 기본으로 쓰고, 감사 로그처럼 바깥 롤백과 분리돼야 하는 경우에만 REQUIRES_NEW를 씁니다."

### 3분 버전

> "트랜잭션 설계에서 제가 제일 먼저 생각하는 건 **경계의 길이와 그 경계 밖으로 무엇을 밀어낼 것인가** 입니다.
>
> 첫째, 트랜잭션은 DB만 보호합니다. Kafka 발행이나 HTTP 호출은 롤백되지 않으니 트랜잭션 안에 두면 유령 이벤트가 생기고, 길게 두면 락 경합이 커집니다. 그래서 저는 외부 호출을 트랜잭션 밖으로 빼거나, DB 상태와 함께 가야 한다면 Outbox 테이블에 이벤트를 같이 저장하고 워커가 비동기로 Kafka에 발행하게 합니다. 이전 프로젝트에서 Kafka Outbox를 구현하면서 graceful shutdown과 재시도 안전성까지 고려했습니다.
>
> 둘째, 전파는 REQUIRED가 기본입니다. 대부분의 서비스 메서드는 하나의 논리적 작업 단위로 묶이는 게 맞으니까요. REQUIRES_NEW는 감사 로그나 실패 이력처럼 바깥이 롤백돼도 반드시 남겨야 하는 기록에만 씁니다. 남용하면 한 요청이 여러 커넥션을 잡아 풀이 고갈됩니다.
>
> 셋째, 격리수준은 InnoDB 기본 REPEATABLE READ를 유지합니다. MVCC로 non-repeatable read와 phantom read 대부분이 막히지만, gap lock이 교착의 원인이 될 수 있어 테이블/쿼리마다 락 범위를 확인합니다. 진짜 race condition — 예를 들어 쿠폰 차감, 재고 감소 — 은 격리수준이 아니라 `SELECT ... FOR UPDATE` 비관적 락이나 `@Version` 낙관적 락으로 설계합니다.
>
> 넷째, AFTER_COMMIT 훅은 '커밋되지 않은 이벤트 누출'을 막는 장치, Outbox는 '커밋된 이벤트 유실'을 막는 장치로 역할이 다릅니다. 둘은 보완적이고, 컨슈머 멱등성이 전제돼야 전체가 안전해집니다."

### 흔히 따라오는 꼬리 질문과 답변 포인트

- **"REQUIRED와 REQUIRES_NEW 차이가 뭔가요?"** → 기존 트랜잭션 참여 vs 신규 시작, 새 커넥션 점유, 독립 커밋/롤백.
- **"self-invocation은 왜 안 되나요?"** → 프록시 기반 AOP, 같은 빈 내부 호출은 프록시 우회.
- **"트랜잭션 롤백이 안 돼요."** → 기본은 `RuntimeException`만 롤백. checked exception은 `rollbackFor=Exception.class` 필요. 또는 catch로 예외를 먹는 경우.
- **"Kafka와 DB 트랜잭션을 어떻게 묶나요?"** → 완벽히 못 묶는다, Outbox로 DB 쪽에 위임 + 컨슈머 멱등.
- **"phantom read가 InnoDB REPEATABLE READ에서 안 나는 이유?"** → Consistent nonlocking read는 MVCC snapshot, locking read는 next-key lock.

## 후보자 경험과의 연결 포인트

면접에서 이론만 답하면 시니어가 아니다. 아래 축으로 본인 경험에 묶어라.

- **Kafka Outbox**: "이벤트 유실을 막기 위해 DB 저장과 같은 트랜잭션에 Outbox 엔트리를 넣고, 별도 워커가 상태 기반 폴링으로 발행·재시도하도록 구성했다. 컨슈머는 eventId 기반 멱등 처리를 했다."
- **Graceful shutdown**: "SIGTERM 수신 시 HTTP 인바운드를 차단하고, outbox dispatch 워커와 컨슈머가 진행 중인 작업을 마칠 시간을 주도록 lifecycle timeout과 executor awaitTermination을 조정했다. 중단된 작업도 outbox에 PENDING으로 남아 있어 재시도가 안전했다."
- **트랜잭션 경계 설계**: "주문-결제-적립 플로우에서 외부 PG 호출을 트랜잭션 밖으로 꺼내고, 승인 이후 DB 반영은 별도의 짧은 트랜잭션으로 분리해 락 보유 시간을 단축했다."
- **격리수준 의사결정**: "InnoDB 기본 REPEATABLE READ를 유지하되, 높은 경합이 있는 테이블은 낙관적 락(@Version)으로 바꿔 gap lock으로 인한 교착을 줄였다."

## 체크리스트

- [ ] `@Transactional` 메서드 안에서 외부 API/메시지 브로커를 **직접** 호출하지 않는가
- [ ] 트랜잭션 안에 긴 네트워크 I/O나 배치 루프가 들어가 있지 않은가
- [ ] `REQUIRES_NEW`는 "바깥 롤백과 결정이 분리돼야 하는 경우"에만 쓰고 있는가
- [ ] self-invocation으로 `@Transactional`이 무시되는 메서드는 없는가
- [ ] checked exception을 던지는데 `rollbackFor` 없이 기대한 롤백이 동작한다고 가정하고 있지 않은가
- [ ] 이벤트 발행이 DB 커밋 이후로 정렬되어 있는가 (`AFTER_COMMIT` 또는 Outbox)
- [ ] 이벤트 컨슈머가 멱등한가
- [ ] 격리수준을 "뭔가 동시성 문제"의 해결책으로 기대하고 있지 않은가 (락/버전으로 명시적 제어)
- [ ] 장시간 트랜잭션을 청크 단위로 쪼갰는가
- [ ] 배포 시 graceful shutdown으로 진행 중인 outbox/컨슈머 작업이 안전하게 마무리되는가
- [ ] 트랜잭션 로그(TRACE)로 실제 전파 동작(Creating/Participating/Suspending)을 눈으로 확인해본 적이 있는가

---

## 관련 문서

- [TransactionSynchronization 실전](./transaction-synchronization.md) — `registerSynchronization()` 기반 afterCommit 커스터마이징
- [Spring Data JPA 트랜잭션 실수 모음](./jpa-transaction.md)
- [분산 트랜잭션과 Outbox 패턴](../../architecture/distributed-transaction-outbox-pattern.md) — 2PC 대안 아키텍처
- [InnoDB MVCC 완전 분석](../../database/mysql/innodb-mvcc.md) — 격리 수준의 DB 레이어 의미
- [Gap Lock & Next-Key Lock](../../database/mysql/innodb-gap-next-key-lock.md) — RR에서의 gap lock 교착
