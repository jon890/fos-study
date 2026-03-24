# Spring Data JPA 트랜잭션 흔한 실수들

Spring Data JPA + `@Transactional`을 쓰면서 실수하기 쉬운 패턴들을 정리했다. 대부분 "작동은 하는데 의도대로 작동하지 않는" 케이스들이다.

> InnoDB 트랜잭션/MVCC 기본 개념: [InnoDB 트랜잭션과 잠금](../../database/mysql/transaction-lock.md)

---

## 1. Self-invocation — 같은 빈 안에서 호출하면 트랜잭션이 안 걸린다

`@Transactional`은 Spring AOP 프록시로 동작한다. 프록시 바깥에서 호출할 때만 가로챈다.

```java
@Service
public class OrderService {

    public void process(Long orderId) {
        validate(orderId);      // ← this.validate() 직접 호출
        placeOrder(orderId);    // ← this.placeOrder() 직접 호출
    }

    @Transactional
    public void validate(Long orderId) { ... }

    @Transactional
    public void placeOrder(Long orderId) { ... }
}
```

`process()`에서 `validate()`, `placeOrder()`를 호출하면 같은 객체의 메서드를 직접 호출하는 것이라 프록시를 거치지 않는다. `@Transactional`이 붙어있어도 트랜잭션이 시작되지 않는다.

**해결책**: 트랜잭션이 필요한 진입점에 `@Transactional`을 붙이거나, 별도 빈으로 분리한다.

```java
@Transactional  // 진입점에 선언
public void process(Long orderId) {
    validate(orderId);
    placeOrder(orderId);
}
```

---

## 2. private 메서드에 @Transactional — 조용히 무시된다

Spring AOP 프록시는 `public` 메서드만 가로챌 수 있다. `private`이나 `protected`에 붙은 `@Transactional`은 아무 효과가 없다. 에러도 발생하지 않고 그냥 무시된다.

```java
@Transactional  // ← 동작 안 함
private void saveInternal(Entity entity) {
    repository.save(entity);
}
```

트랜잭션이 필요한 메서드는 반드시 `public`으로 만들어야 한다.

---

## 3. @Transactional(readOnly = true) — 단순 힌트가 아니다

`readOnly = true`는 두 가지 효과가 있다.

1. **Hibernate flush mode MANUAL**: 더티 체킹을 하지 않는다. 조회 메서드에서 엔티티를 수정해도 UPDATE가 발생하지 않는다
2. **JDBC 드라이버/커넥션 풀 힌트**: 읽기 전용 커넥션을 사용하도록 유도할 수 있다 (read replica 라우팅 등)

```java
@Transactional(readOnly = true)
public List<Order> findAll() {
    List<Order> orders = orderRepository.findAll();
    orders.forEach(o -> o.setStatus("MODIFIED"));  // 수정해도 UPDATE 안 나감
    return orders;
}
```

조회 전용 서비스 메서드에는 항상 `readOnly = true`를 붙이는 게 좋다. 성능 최적화 + 의도 명확화.

---

## 4. LazyInitializationException — 트랜잭션 밖에서 Lazy 로딩

JPA의 연관관계 기본 fetch 전략은 `LAZY`다. 엔티티를 조회해온 뒤 트랜잭션이 끝나면 영속성 컨텍스트가 닫히고, 이후 Lazy 필드에 접근하면 터진다.

```java
// Service
@Transactional(readOnly = true)
public Order findOrder(Long id) {
    return orderRepository.findById(id).orElseThrow();
}

// Controller
Order order = orderService.findOrder(1L);
order.getItems().size();  // ← LazyInitializationException!
                          //   트랜잭션 종료 후 접근
```

**해결책 (상황에 따라 선택)**:

```java
// 1. Fetch Join으로 필요한 연관관계 미리 로딩
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.id = :id")
Optional<Order> findWithItems(@Param("id") Long id);

// 2. 트랜잭션 범위를 Controller까지 확장 (Open Session in View)
//    → 권장하지 않음. N+1 문제 숨김, 영속성 컨텍스트 오남용

// 3. DTO로 변환해서 반환 (가장 권장)
@Transactional(readOnly = true)
public OrderDto findOrder(Long id) {
    Order order = orderRepository.findById(id).orElseThrow();
    return new OrderDto(order);  // 트랜잭션 안에서 변환
}
```

---

## 5. REQUIRES_NEW 트랜잭션 중첩 — 예외가 어디서 처리되는가

`REQUIRES_NEW`는 기존 트랜잭션을 일시 중단하고 새 트랜잭션을 연다. 새 트랜잭션이 커밋/롤백해도 외부 트랜잭션은 독립적으로 유지된다.

```java
@Transactional
public void outer() {
    // 외부 트랜잭션 시작
    orderRepository.save(order);
    inner();        // 새 트랜잭션
    // inner 예외가 여기서 다시 던져지면 외부도 롤백됨
}

@Transactional(propagation = Propagation.REQUIRES_NEW)
public void inner() {
    auditRepository.save(auditLog);  // 별도 커밋
    throw new RuntimeException();    // inner 롤백
}
```

`inner()`에서 예외가 발생하면 inner 트랜잭션은 롤백된다. 그런데 예외가 `outer()`로 전파되면 outer도 롤백된다. inner를 독립적으로 커밋하고 싶으면 outer에서 예외를 잡아야 한다.

```java
@Transactional
public void outer() {
    orderRepository.save(order);
    try {
        inner();
    } catch (RuntimeException e) {
        // inner 롤백, outer는 계속
    }
}
```

단, self-invocation 문제에 주의. `outer()`에서 같은 빈의 `inner()`를 직접 호출하면 `REQUIRES_NEW`도 동작하지 않는다.

---

## 6. @Version 낙관적 잠금 vs @Lock 비관적 잠금

동시 수정 충돌을 처리하는 두 가지 방식이다.

### 낙관적 잠금 (@Version)

```java
@Entity
public class Product {
    @Id Long id;
    int stock;

    @Version
    Long version;  // 버전 컬럼
}
```

```sql
-- JPA가 생성하는 UPDATE
UPDATE product SET stock=9, version=2 WHERE id=1 AND version=1;
-- version이 바뀌어 있으면 0 rows affected → OptimisticLockException
```

충돌이 드물 때 적합하다. 잠금을 걸지 않아서 동시성이 높고, 충돌 시 예외를 던진다. 재시도 로직을 직접 구현해야 한다.

### 비관적 잠금 (@Lock)

```java
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("SELECT p FROM Product p WHERE p.id = :id")
Optional<Product> findByIdForUpdate(@Param("id") Long id);
```

```sql
SELECT * FROM product WHERE id=1 FOR UPDATE;
```

조회 시점에 X-Lock을 걸어 다른 트랜잭션의 접근을 차단한다. 충돌이 잦거나 재고 차감처럼 정합성이 절대적으로 중요한 경우에 사용한다. Lock wait timeout에 주의.

---

## 7. 트랜잭션 안에서 외부 시스템 호출 — 잠금 유지 시간 문제

트랜잭션 안에서 HTTP 외부 API나 느린 작업을 호출하면 그동안 DB 잠금이 유지된다.

```java
@Transactional
public void processPayment(Long orderId) {
    Order order = orderRepository.findByIdForUpdate(orderId);  // X-Lock 획득

    paymentClient.charge(order);  // ← 외부 결제 API (수백 ms ~ 수 초)
    // 이 시간 동안 lock 유지

    order.setStatus("PAID");
    orderRepository.save(order);
}  // Lock 해제
```

결제 API가 느리면 그만큼 다른 트랜잭션이 대기한다. 잠금이 필요한 DB 작업과 외부 IO를 분리하는 게 좋다.

```java
// 개선: 외부 호출을 트랜잭션 밖으로 꺼냄
public void processPayment(Long orderId) {
    paymentClient.charge(orderId);  // 트랜잭션 밖
    updateOrderStatus(orderId);     // 트랜잭션 안 (빠른 DB 작업만)
}

@Transactional
public void updateOrderStatus(Long orderId) {
    Order order = orderRepository.findByIdForUpdate(orderId);
    order.setStatus("PAID");
}
```

---

## 8. save() 시점 — flush 전까지 SQL이 안 나간다

`repository.save()`를 호출해도 즉시 INSERT/UPDATE SQL이 실행되지 않는다. Hibernate가 영속성 컨텍스트에 모아뒀다가 flush 시점에 한꺼번에 내보낸다.

flush 발생 시점:
- 트랜잭션 커밋 직전
- JPQL/네이티브 쿼리 실행 직전 (dirty 상태면)
- `entityManager.flush()` 직접 호출 시

```java
@Transactional
public void example() {
    Entity e = new Entity("data");
    repository.save(e);      // 아직 INSERT 안 나감

    // JPQL 실행 직전 flush 발생 → INSERT 나감
    repository.findByCondition(...);

    // 트랜잭션 커밋 시 남은 flush 발생
}
```

`save()` 직후 생성된 ID가 필요하면 `saveAndFlush()`를 쓰거나, `@GeneratedValue(strategy = IDENTITY)`라면 `save()` 시점에 INSERT가 바로 나간다 (ID를 알아야 하므로).

---

## 정리

| 실수 | 핵심 원인 | 확인 방법 |
|---|---|---|
| Self-invocation | 프록시 우회 | 외부 빈으로 분리 또는 진입점에 `@Transactional` |
| private 메서드 트랜잭션 | AOP 프록시 제약 | public으로 변경 |
| LazyInitializationException | 트랜잭션 범위 밖 접근 | Fetch Join 또는 DTO 변환 |
| 낙관/비관 잠금 선택 | 충돌 빈도, 정합성 요구 | 충돌 빈도 낮으면 @Version, 높으면 FOR UPDATE |
| 긴 트랜잭션 + 외부 IO | 잠금 유지 시간 증가 | DB 작업과 외부 IO 분리 |
