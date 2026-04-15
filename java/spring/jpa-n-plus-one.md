# [초안] JPA N+1 문제 완전 정복 — 발생 원인부터 EXPLAIN 분석까지

---

## 왜 이 주제가 중요한가

JPA N+1 문제는 면접에서 "JPA를 실무에서 써봤나요?"라는 질문 뒤에 반드시 따라오는 주제다. 단순히 "fetch join 쓰면 됩니다"라고 답하는 지원자는 주니어 수준으로 평가된다. 시니어 백엔드 엔지니어라면 다음 세 가지를 함께 설명할 수 있어야 한다.

1. **왜 N+1이 발생하는가** — JPA 프록시와 지연 로딩의 작동 방식
2. **어떤 SQL이 실제로 나가는가** — 쿼리 로그 설정과 SQL 검증
3. **상황에 따른 해결책 선택** — fetch join, batch size, DTO 프로젝션의 트레이드오프

CJ OliveYoung 같은 커머스 플랫폼에서는 주문-상품-리뷰처럼 연관 관계가 깊은 도메인이 많다. 상품 목록 100건을 조회할 때 연관 엔티티마다 쿼리가 100번 추가로 나가면 응답 시간이 수 초 단위로 늘어난다. 이 문제를 제대로 이해하고 있지 않으면 실제 서비스에서 장애로 이어진다.

---

## N+1이 발생하는 원인

### 지연 로딩(Lazy Loading)과 프록시

JPA는 연관 엔티티를 기본적으로 **프록시 객체**로 채운다. 프록시는 실제 데이터를 갖지 않고, 처음 접근할 때 SELECT 쿼리를 실행해 데이터를 채운다. 이것이 **지연 로딩(LAZY)**이다.

```java
@Entity
public class Order {
    @Id
    private Long id;

    // 기본값: FetchType.LAZY
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id")
    private Member member;

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> orderItems = new ArrayList<>();
}
```

`orderRepository.findAll()`을 호출하면 JPA는 `Order` 테이블만 조회한다 — 이것이 **1번**의 쿼리다.

```sql
SELECT * FROM orders;
```

이후 각 `Order`의 `orderItems`에 접근하는 순간, JPA 프록시가 해당 주문의 아이템을 가져오기 위해 쿼리를 날린다.

```sql
SELECT * FROM order_item WHERE order_id = 1;
SELECT * FROM order_item WHERE order_id = 2;
SELECT * FROM order_item WHERE order_id = 3;
-- ... 주문 수(N)만큼 반복
```

주문이 100건이면 총 **101번**의 쿼리가 실행된다. 이것이 N+1 문제다.

### 즉시 로딩(EAGER)도 N+1을 피하지 못한다

흔한 오해 중 하나가 "EAGER로 바꾸면 N+1이 해결된다"는 생각이다. 오히려 더 나빠질 수 있다.

`FetchType.EAGER`로 설정하면 JPA는 `Order`를 로드할 때마다 연관된 엔티티를 즉시 가져오려 한다. 그러나 `JPQL`로 `findAll()`을 실행하면 JPA는 JPQL 쿼리를 그대로 실행하고, 이후 각 결과 행에 대해 EAGER 연관을 별도 쿼리로 채운다. 결과는 동일하게 N+1이다.

```
[WARN] EAGER 연관을 JPQL에서 사용하면 fetch join 없이는 여전히 N+1 발생
```

---

## 발생하는 SQL을 직접 확인하는 방법

### 쿼리 로그 설정 (application.yml)

```yaml
spring:
  jpa:
    show-sql: true
    properties:
      hibernate:
        format_sql: true
        use_sql_comments: true

logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.orm.jdbc.bind: TRACE  # 바인딩 파라미터 확인 (Hibernate 6+)
```

> Hibernate 5 이하에서는 `org.hibernate.type.descriptor.sql: TRACE`를 사용한다.

### p6spy로 실제 파라미터가 포함된 SQL 확인

`show-sql`은 `?` 플레이스홀더만 보여준다. 실제 파라미터까지 포함된 완성된 SQL을 보려면 **p6spy**를 쓴다.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>p6spy</groupId>
    <artifactId>p6spy</artifactId>
    <version>3.9.1</version>
</dependency>
```

```yaml
# application.yml
spring:
  datasource:
    driver-class-name: com.p6spy.engine.spy.P6SpyDriver
    url: jdbc:p6spy:mysql://localhost:3306/careeros
```

```properties
# spy.properties (src/main/resources)
appender=com.p6spy.engine.spy.appender.Slf4JLogger
logMessageFormat=com.p6spy.engine.spy.appender.MultiLineFormat
```

이제 로그에 실제 SQL이 파라미터와 함께 찍히므로 N+1이 몇 번 발생하는지 카운트할 수 있다.

### 테스트 환경에서 쿼리 횟수 검증

```java
@DataJpaTest
class OrderRepositoryTest {

    @Autowired
    private OrderRepository orderRepository;

    @PersistenceContext
    private EntityManager em;

    @Test
    void n_plus_1_발생_확인() {
        // given: 주문 3건 + 각 주문에 아이템 2건씩 저장
        saveTestData();
        em.flush();
        em.clear();

        // when
        List<Order> orders = orderRepository.findAll();
        orders.forEach(o -> o.getOrderItems().size()); // LAZY 접근 강제

        // 쿼리 카운터가 4번 (1 + 3) 실행되었는지 확인
        // QueryCountInspector 또는 datasource-proxy 라이브러리 활용
    }
}
```

실제 프로젝트에서는 **datasource-proxy**와 `@Transactional` 테스트를 조합해 쿼리 수를 단언(assertion)하는 패턴이 많이 사용된다.

---

## 해결책 1: Fetch Join

### 기본 사용법

JPQL에서 `JOIN FETCH`를 명시하면 JPA가 연관 엔티티를 한 번의 JOIN 쿼리로 함께 가져온다.

```java
// Repository
public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query("SELECT DISTINCT o FROM Order o JOIN FETCH o.orderItems WHERE o.status = :status")
    List<Order> findWithItemsByStatus(@Param("status") OrderStatus status);
}
```

실행되는 SQL:

```sql
SELECT DISTINCT o.*, oi.*
FROM orders o
INNER JOIN order_item oi ON oi.order_id = o.id
WHERE o.status = 'COMPLETED';
```

한 번의 쿼리로 모든 데이터를 가져온다.

### `DISTINCT`가 필요한 이유

`OneToMany` fetch join은 카르테시안 곱(Cartesian Product)이 발생해 `Order` 행이 아이템 수만큼 중복된다. `DISTINCT`는 JPA 레벨에서 중복을 제거한다 (SQL DISTINCT와는 다름 — JPA가 결과 리스트에서 같은 id를 가진 객체를 제거한다).

Hibernate 6부터는 `DISTINCT`가 없어도 자동으로 중복을 제거하는 동작이 기본값으로 바뀌었다. 하지만 명시적으로 써두는 것이 의도를 명확히 한다.

### 다중 컬렉션 fetch join 금지

```java
// 잘못된 예 — MultipleBagFetchException 발생
@Query("SELECT o FROM Order o JOIN FETCH o.orderItems JOIN FETCH o.coupons")
List<Order> findAll(); // 컬렉션 2개를 동시에 fetch join → 예외
```

JPA는 컬렉션 두 개를 동시에 fetch join하는 것을 허용하지 않는다 (Bag 타입일 경우). 해결 방법은 두 가지다.

1. 하나는 fetch join, 나머지는 `@BatchSize`
2. `List` 대신 `Set` 사용 (중복 허용 여부가 다르므로 도메인 의미 확인 필요)

---

## 해결책 2: @BatchSize (배치 크기 설정)

### 원리

`@BatchSize`는 프록시를 초기화할 때 개별 쿼리 대신 `IN` 절로 묶어서 한 번에 가져온다.

```java
@Entity
public class Order {

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    @BatchSize(size = 100)
    private List<OrderItem> orderItems = new ArrayList<>();
}
```

주문 100건을 조회하면 기존에는 100번의 쿼리가 나갔지만, `@BatchSize(size = 100)` 설정 후에는 다음과 같이 1번으로 줄어든다.

```sql
SELECT * FROM order_item
WHERE order_id IN (1, 2, 3, ..., 100);
```

### 글로벌 배치 크기 설정

엔티티마다 `@BatchSize`를 붙이는 것이 번거롭다면 글로벌로 설정할 수 있다.

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 100
```

이 값은 보통 **100~1000** 사이로 설정한다. MySQL의 경우 `IN` 절이 너무 커지면 옵티마이저가 인덱스를 타지 않고 풀 스캔으로 전환할 수 있으므로 무작정 크게 잡는 것은 좋지 않다.

### fetch join vs @BatchSize 선택 기준

| 상황 | 권장 방법 |
|------|-----------|
| 특정 API에서 항상 연관 데이터가 필요한 경우 | fetch join |
| 연관 데이터가 조건부로 필요한 경우 | @BatchSize |
| 컬렉션 두 개 이상을 동시에 로딩 | fetch join 1개 + @BatchSize 나머지 |
| 페이지네이션이 필요한 경우 | @BatchSize (fetch join 사용 금지) |

---

## 페이지네이션과 fetch join의 위험한 조합

이 부분은 면접에서 자주 틀리는 포인트다.

### 문제: HibernateJpaDialect의 경고

```java
@Query("SELECT DISTINCT o FROM Order o JOIN FETCH o.orderItems")
Page<Order> findAllWithItems(Pageable pageable); // 위험!
```

이 코드를 실행하면 Hibernate가 다음 경고를 출력한다.

```
HHH90003004: firstResult/maxResults specified with collection fetch; applying in memory
```

페이지네이션을 데이터베이스 레벨이 아닌 **메모리에서** 처리한다는 뜻이다. 즉, 전체 데이터를 모두 읽어 메모리에 올린 후 페이지를 자른다. 데이터가 수십만 건이면 OutOfMemoryError로 이어진다.

### 올바른 해결책: CountQuery 분리 + @BatchSize

```java
// Step 1: 페이지네이션은 Order만 가져온다
@Query(
    value = "SELECT o FROM Order o WHERE o.status = :status",
    countQuery = "SELECT COUNT(o) FROM Order o WHERE o.status = :status"
)
Page<Order> findByStatus(@Param("status") OrderStatus status, Pageable pageable);

// Step 2: Service에서 ID만 먼저 뽑고 fetch join으로 상세 로딩
@Service
@Transactional(readOnly = true)
public class OrderService {

    public Page<OrderResponse> getOrders(OrderStatus status, Pageable pageable) {
        Page<Order> page = orderRepository.findByStatus(status, pageable);

        // @BatchSize 또는 별도 fetch join 쿼리로 컬렉션 로딩
        // page.getContent()를 순회하며 orderItems에 접근하면
        // default_batch_fetch_size 설정에 의해 IN 절로 배치 조회됨
        return page.map(OrderResponse::from);
    }
}
```

또 다른 패턴은 **Slice**를 사용하는 것이다. 전체 카운트가 필요 없는 무한 스크롤 UI라면 `Slice<Order>`를 반환해 COUNT 쿼리를 아낀다.

---

## 발생 SQL과 EXPLAIN 연결

### 실행 계획 확인

fetch join으로 바꾼 쿼리가 인덱스를 제대로 타는지 확인해야 한다.

```sql
-- fetch join 쿼리 예시
EXPLAIN SELECT DISTINCT o.*, oi.*
FROM orders o
INNER JOIN order_item oi ON oi.order_id = o.id
WHERE o.status = 'COMPLETED'
  AND o.created_at >= '2026-01-01';
```

EXPLAIN 결과에서 주목할 컬럼:

| 컬럼 | 좋은 값 | 나쁜 값 |
|------|---------|---------|
| type | ref, eq_ref, range | ALL (풀 스캔) |
| key | 인덱스 이름 | NULL |
| rows | 작을수록 좋음 | 전체 행 수 |
| Extra | Using index | Using filesort, Using temporary |

### 인덱스 설계와 연결

```sql
-- order_item.order_id에 인덱스가 없으면 fetch join도 느리다
ALTER TABLE order_item ADD INDEX idx_order_id (order_id);

-- 복합 인덱스: status + created_at으로 자주 조회한다면
ALTER TABLE orders ADD INDEX idx_status_created (status, created_at);
```

JPA가 생성하는 SQL이 어떤 인덱스를 타는지 확인하려면:

1. 로그에서 실제 SQL 추출
2. MySQL 클라이언트에서 `EXPLAIN` 실행
3. `key` 컬럼이 NULL이면 인덱스 추가 검토

---

## 로컬 실습 환경 구성

### Docker로 MySQL 8 실행

```bash
docker run -d \
  --name careeros-mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=careeros \
  -p 3306:3306 \
  mysql:8.0
```

### 프로젝트 구조

```
src/
└── main/
    └── java/com/example/careeros/
        ├── domain/
        │   ├── Order.java
        │   ├── OrderItem.java
        │   └── Member.java
        ├── repository/
        │   ├── OrderRepository.java
        │   └── OrderRepositoryCustom.java
        └── service/
            └── OrderService.java
```

### 엔티티 정의

```java
@Entity
@Table(name = "orders")
@Getter
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id")
    private Member member;

    @Enumerated(EnumType.STRING)
    private OrderStatus status;

    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    @BatchSize(size = 100)
    private List<OrderItem> orderItems = new ArrayList<>();
}

@Entity
@Table(name = "order_item")
@Getter
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id")
    private Order order;

    private String productName;
    private int quantity;
    private int price;
}
```

### Repository 구현

```java
public interface OrderRepository extends JpaRepository<Order, Long>, OrderRepositoryCustom {

    // 페이지네이션용 — @BatchSize가 IN 절로 아이템 로딩
    @Query(
        value = "SELECT o FROM Order o WHERE o.status = :status ORDER BY o.createdAt DESC",
        countQuery = "SELECT COUNT(o) FROM Order o WHERE o.status = :status"
    )
    Page<Order> findByStatus(@Param("status") OrderStatus status, Pageable pageable);

    // 소량 조회용 fetch join
    @Query("SELECT DISTINCT o FROM Order o JOIN FETCH o.orderItems WHERE o.member.id = :memberId")
    List<Order> findWithItemsByMemberId(@Param("memberId") Long memberId);
}
```

### 테스트 데이터 삽입 및 N+1 재현

```java
@SpringBootTest
@Transactional
class OrderN1ReproductionTest {

    @Autowired OrderRepository orderRepository;
    @Autowired MemberRepository memberRepository;
    @PersistenceContext EntityManager em;

    @BeforeEach
    void setUp() {
        Member member = new Member("tester");
        memberRepository.save(member);

        for (int i = 0; i < 10; i++) {
            Order order = new Order(member, OrderStatus.COMPLETED);
            for (int j = 0; j < 3; j++) {
                order.addItem(new OrderItem("상품" + j, 1, 10000));
            }
            orderRepository.save(order);
        }
        em.flush();
        em.clear(); // 1차 캐시 제거 — 실제 DB 쿼리를 유도
    }

    @Test
    void n_plus_1_발생() {
        List<Order> orders = orderRepository.findAll();
        // 다음 라인에서 LAZY 프록시 초기화 → N번 쿼리 발생
        orders.forEach(o -> System.out.println(o.getOrderItems().size()));
        // 로그에서 SELECT * FROM order_item WHERE order_id = ? 가 10번 출력됨
    }

    @Test
    void fetch_join으로_해결() {
        List<Order> orders = orderRepository.findWithItemsByMemberId(1L);
        orders.forEach(o -> System.out.println(o.getOrderItems().size()));
        // 쿼리 1번만 실행됨
    }
}
```

---

## DTO 프로젝션으로 완전히 회피하기

연관 엔티티 전체가 필요 없고 특정 필드만 필요할 때는 엔티티를 로딩하지 않고 DTO로 바로 받는 것이 가장 효율적이다.

```java
public record OrderSummary(
    Long orderId,
    String memberName,
    long totalAmount
) {}

// Repository
@Query("""
    SELECT new com.example.careeros.dto.OrderSummary(
        o.id,
        m.name,
        SUM(oi.price * oi.quantity)
    )
    FROM Order o
    JOIN o.member m
    JOIN o.orderItems oi
    WHERE o.status = :status
    GROUP BY o.id, m.name
    """)
List<OrderSummary> findOrderSummaries(@Param("status") OrderStatus status);
```

이 방식은 영속성 컨텍스트에 엔티티를 올리지 않으므로:
- N+1 문제 자체가 없음
- 메모리 사용량 최소화
- 읽기 전용 API에 적합

단점은 엔티티 변경 감지(dirty checking)를 사용할 수 없고, 연관 관계 탐색이 불가능하다는 점이다.

---

## 잘못된 패턴 vs 개선된 패턴

### 패턴 1: Service 레이어에서 반복 접근

```java
// 나쁜 예
@Transactional(readOnly = true)
public List<OrderResponse> getCompletedOrders() {
    List<Order> orders = orderRepository.findByStatus(OrderStatus.COMPLETED);
    return orders.stream()
        .map(order -> {
            int totalQty = order.getOrderItems().stream()  // N번 쿼리
                .mapToInt(OrderItem::getQuantity)
                .sum();
            return new OrderResponse(order.getId(), totalQty);
        })
        .toList();
}

// 좋은 예
@Transactional(readOnly = true)
public List<OrderResponse> getCompletedOrders() {
    // @BatchSize 글로벌 설정 + 트랜잭션 내에서 접근
    // 또는 fetch join으로 한 번에 가져옴
    List<Order> orders = orderRepository.findWithItemsByStatus(OrderStatus.COMPLETED);
    return orders.stream()
        .map(order -> {
            int totalQty = order.getOrderItems().stream()
                .mapToInt(OrderItem::getQuantity)
                .sum();
            return new OrderResponse(order.getId(), totalQty);
        })
        .toList();
}
```

### 패턴 2: @Transactional 없이 LAZY 접근

```java
// 나쁜 예 — LazyInitializationException 발생
@GetMapping("/orders/{id}")
public OrderResponse getOrder(@PathVariable Long id) {
    Order order = orderService.findById(id); // 트랜잭션 종료
    order.getOrderItems().size(); // 여기서 예외 — 세션이 이미 닫혔음
    return OrderResponse.from(order);
}

// 좋은 예 — 트랜잭션 안에서 필요한 것을 모두 로딩 후 DTO로 반환
@Transactional(readOnly = true)
public OrderDetailResponse getOrderWithItems(Long id) {
    Order order = orderRepository.findWithItemsById(id)
        .orElseThrow(() -> new OrderNotFoundException(id));
    return OrderDetailResponse.from(order); // 변환은 트랜잭션 내에서
}
```

### 패턴 3: Open Session In View (OSIV) 의존

Spring Boot의 기본 설정인 `spring.jpa.open-in-view=true`는 HTTP 요청 전체에 걸쳐 영속성 컨텍스트를 열어둔다. 이 덕분에 컨트롤러나 뷰 레이어에서도 LAZY 로딩이 가능하지만, DB 커넥션을 요청이 끝날 때까지 붙잡고 있어 커넥션 풀 고갈로 이어질 수 있다.

```yaml
# 운영 환경 권장
spring:
  jpa:
    open-in-view: false
```

OSIV를 끄면 트랜잭션 밖에서 LAZY 접근 시 `LazyInitializationException`이 발생한다. 이를 강제적인 아키텍처 규율로 삼아 서비스 레이어 안에서 필요한 모든 로딩을 완료하는 구조를 만든다.

---

## 면접 답변 프레임 (시니어 레벨)

### 질문: "JPA N+1 문제가 무엇이고 어떻게 해결하셨나요?"

> N+1 문제는 컬렉션 연관관계를 가진 엔티티 목록을 조회할 때 JPA 프록시의 지연 로딩으로 인해 첫 번째 쿼리(1번) 이후 각 엔티티의 연관 데이터를 가져오기 위해 N번의 추가 쿼리가 발생하는 현상입니다.
>
> 저는 세 가지 방식으로 상황에 맞게 해결했습니다. 첫째, 항상 연관 데이터가 필요한 단건 조회나 소량 목록 API에는 JPQL의 `JOIN FETCH`를 사용해 한 번의 쿼리로 해결합니다. 둘째, 페이지네이션이 있는 목록 API에서는 fetch join을 사용하면 Hibernate가 메모리에서 페이지를 처리해 전체 데이터를 올리는 문제가 생기므로, `default_batch_fetch_size`를 글로벌로 설정해 IN 절 배치 로딩으로 처리합니다. 셋째, 읽기 전용 API에서 특정 필드만 필요한 경우에는 DTO 프로젝션으로 엔티티 로딩 자체를 회피합니다.
>
> 추가로 OSIV를 끄고 서비스 레이어에서 트랜잭션 안에 필요한 로딩을 모두 완료하는 구조를 강제해, N+1이 컨트롤러나 뷰 레이어에서 발생하는 패턴을 차단했습니다.

### 예상 심화 질문

**Q. fetch join과 @BatchSize를 동시에 쓸 수 있나요?**
> 가능합니다. 컬렉션 A는 fetch join으로, 컬렉션 B는 @BatchSize로 처리하는 조합이 일반적입니다. `MultipleBagFetchException`을 피하면서 두 컬렉션 모두 효율적으로 로딩할 수 있습니다.

**Q. 페이지네이션에서 fetch join을 쓰면 안 된다는 걸 어떻게 알았나요?**
> Hibernate가 `HHH90003004` 경고를 로그에 출력하고, 이후 `LIMIT` 절을 SQL에 추가하지 않고 전체 결과를 메모리에 올린 다음 자르는 방식으로 동작합니다. 이를 직접 로그에서 확인하고 EXPLAIN으로 실행 계획을 분석해 문제를 인지했습니다.

**Q. default_batch_fetch_size 값은 어떻게 결정하나요?**
> 한 페이지에 노출되는 행 수와 MySQL IN 절 한계를 고려합니다. 일반적으로 페이지 크기의 2~5배 정도(보통 100~500)로 설정하고, 실제로는 EXPLAIN으로 인덱스가 제대로 타는지 확인합니다. MySQL 옵티마이저는 IN 절 크기가 너무 커지면 full scan으로 전환할 수 있어서 무작정 크게 잡는 건 피합니다.

---

## 체크리스트

- [ ] `show-sql: true`와 `format_sql: true`로 쿼리 로그를 켜고 N+1 발생 여부를 직접 확인했는가
- [ ] 목록 API에서 컬렉션 연관관계 접근 시 쿼리 수를 세어 봤는가
- [ ] fetch join 사용 시 `DISTINCT` 또는 Hibernate 6 기본 동작을 이해하고 있는가
- [ ] 컬렉션 두 개를 동시에 fetch join하면 `MultipleBagFetchException`이 발생함을 알고 있는가
- [ ] 페이지네이션 + fetch join 조합의 위험성(메모리 페이징)을 알고 있는가
- [ ] `default_batch_fetch_size` 글로벌 설정을 통해 모든 LAZY 컬렉션에 배치 로딩을 적용하는 방법을 알고 있는가
- [ ] DTO 프로젝션으로 N+1을 아예 회피하는 패턴을 사용할 수 있는가
- [ ] OSIV의 장단점과 운영 환경에서 끄는 이유를 설명할 수 있는가
- [ ] fetch join으로 생성된 SQL을 EXPLAIN으로 분석해 인덱스를 확인하는 흐름을 알고 있는가
- [ ] `LazyInitializationException`이 발생하는 상황과 원인을 설명할 수 있는가
