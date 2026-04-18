# [초안] DDD와 도메인 모델링: 시니어 백엔드 관점의 전술/전략 패턴 실전 가이드

## 왜 DDD인가

DDD**(Domain-Driven Design)**는 "소프트웨어의 복잡성은 도메인 그 자체의 복잡성에서 나온다"는 전제에서 출발한다. 기술 스택을 아무리 정교하게 고르고 아키텍처 계층을 얼마나 깔끔하게 나누든, 비즈니스 규칙이 엉뚱한 곳에 흩뿌려져 있으면 결국 유지보수 비용이 폭증한다. DDD는 **복잡한 도메인을 코드로 직접 표현**해 변경 비용을 낮추는 데 목적이 있다.

### Anemic Domain vs Rich Domain

Anemic domain 모델은 엔티티가 getter/setter와 필드만 가진 **데이터 구조체**에 불과하고, 실제 비즈니스 로직은 `OrderService`, `OrderValidator`, `OrderHelper` 같은 서비스 레이어에 흩어진다. 이 패턴의 문제는 다음과 같다.

- 비즈니스 규칙이 어디 있는지 찾을 수 없다. `order.cancel()`이 있어야 할 자리에 `OrderService.cancelOrder(order)`가 있고, 동일한 취소 로직이 반환/환불/관리자-강제취소 세 군데에 중복된다.
- 객체 자신이 **불변식(invariant)**을 지키지 못한다. `order.setStatus(CANCELLED)`를 누구든 호출할 수 있으니, 배송 완료 상태에서 취소되는 사고가 발생한다.
- 테스트가 서비스 레이어에 몰리고, 순수 도메인 단위 테스트가 불가능해진다.

Rich domain 모델은 엔티티가 자기 책임을 스스로 진다.

```java
// Anemic
public class Order {
    private OrderStatus status;
    public void setStatus(OrderStatus s) { this.status = s; }
}
public class OrderService {
    public void cancel(Order order) {
        if (order.getStatus() == DELIVERED) throw ...;
        order.setStatus(CANCELLED);
    }
}

// Rich
public class Order {
    private OrderStatus status;
    public void cancel() {
        if (status == DELIVERED)
            throw new OrderAlreadyDeliveredException(id);
        if (status == CANCELLED) return; // 멱등
        this.status = CANCELLED;
        registerEvent(new OrderCancelledEvent(id));
    }
}
```

변경 비용 관점에서 보면 Rich 모델은 "취소 규칙이 바뀌었다"는 요구에 **한 메서드만 수정**하면 된다. Anemic 모델은 규칙이 흩어져 있어 회귀가 난다.

## 전략 패턴 **(Strategic DDD)**

### Bounded Context

Bounded Context는 **특정 도메인 모델이 유효한 경계**다. 같은 "상품"이라는 단어라도 주문 컨텍스트의 `Product`(가격, 할인 가능 여부)와 재고 컨텍스트의 `Product`(SKU, 창고별 수량)는 다른 모델이다. 하나로 합치면 `Product` 클래스에 필드 50개와 메서드 30개가 붙어 "신 객체"가 탄생한다.

경계를 정하는 힌트:
- 팀 경계와 일치하는가 (Conway's Law)
- 트랜잭션 경계가 자연스럽게 분리되는가
- 동일 용어가 다른 의미로 쓰이는가

### Ubiquitous Language

Bounded Context 내부에서는 기획자, 개발자, DBA가 **같은 용어**를 쓴다. 기획 문서에 "주문 취소"라고 쓰여 있으면 코드의 메서드명도 `cancel()`이어야지 `updateStatus(4)`가 되어서는 안 된다. 언어가 흔들리면 모델이 흔들린다.

### Context Map

컨텍스트 간 관계를 매핑한다.

- **Upstream / Downstream**: 데이터와 의미를 주는 쪽이 upstream, 받는 쪽이 downstream. 주문이 결제 upstream인지, 결제가 주문 upstream인지는 도메인 흐름에 달려 있다.
- **ACL**(Anticorruption Layer): downstream이 upstream의 모델을 그대로 흡수하면 외부 모델 오염으로 내부 도메인이 망가진다. 변환 레이어를 두어 "우리 용어"로 번역한다. 레거시 연동에서 필수다.
- **OHS**(Open Host Service): upstream이 다수 downstream에게 표준 API를 공개한다. REST/이벤트 스키마가 여기에 해당한다.
- **Conformist**: downstream이 upstream 모델을 그대로 따라 쓴다. 보통 힘의 차이가 클 때(외부 벤더 API 등) 선택한다.

## 전술 패턴 **(Tactical DDD)**

### Entity

식별자(ID)로 동일성을 판별하는 객체. `Order`, `Member`가 전형이다. 동일 ID면 필드가 달라도 같은 엔티티다.

### Value Object **(VO)**

값 자체로 동일성이 결정되고 **불변**이다. `Money`, `Address`, `DateRange`.

```java
@Embeddable
public class Money {
    @Column(name = "amount", precision = 19, scale = 4)
    private BigDecimal amount;

    @Column(name = "currency", length = 3)
    private String currency;

    protected Money() {}

    public Money(BigDecimal amount, String currency) {
        if (amount == null || amount.signum() < 0)
            throw new IllegalArgumentException("amount must be >= 0");
        this.amount = amount;
        this.currency = currency;
    }

    public Money add(Money other) {
        requireSameCurrency(other);
        return new Money(this.amount.add(other.amount), currency);
    }

    private void requireSameCurrency(Money other) {
        if (!this.currency.equals(other.currency))
            throw new IllegalArgumentException("currency mismatch");
    }
}
```

VO로 감싸는 이점은 **무결성을 타입으로 보장**한다는 점이다. 메서드 시그니처가 `cancel(BigDecimal refund, String currency)`가 아니라 `cancel(Money refund)`가 되면 파라미터 순서 실수가 원천 차단된다.

### Aggregate / Aggregate Root

Aggregate는 **한 트랜잭션에서 일관성을 함께 지켜야 할 엔티티 묶음**이다. Aggregate Root를 통해서만 내부 엔티티에 접근한다. `Order`가 루트이고 `OrderLine`은 내부 엔티티다. 외부에서 `OrderLine`을 직접 저장/수정하면 Order의 총액 같은 불변식이 깨진다.

**핵심 설계 원칙**:

1. **일관성 경계 == 트랜잭션 경계**. Aggregate 하나가 한 트랜잭션에서 커밋된다. 여러 Aggregate를 한 트랜잭션에 묶으면 동시성 충돌이 급증한다.
2. **작게 유지**. Order가 수천 개의 OrderLine을 가지면 로딩만으로 DB가 죽는다. 배치 처리 전용 Aggregate를 따로 설계하거나 경계를 재고한다.
3. **다른 Aggregate는 ID로 참조**. `Order`가 `Member` 객체를 필드로 가지지 않고 `MemberId`만 가진다. 객체 그래프가 폭주하는 것을 막는다.

```java
@Entity
@Table(name = "orders")
public class Order {
    @Id
    private Long id;

    @Embedded
    private MemberId memberId; // 다른 Aggregate는 ID 참조

    @OneToMany(
        mappedBy = "order",
        cascade = CascadeType.ALL,
        orphanRemoval = true,
        fetch = FetchType.LAZY
    )
    private List<OrderLine> lines = new ArrayList<>();

    @Embedded
    private Money totalAmount;

    private OrderStatus status;

    public static Order place(MemberId memberId, List<OrderLineCommand> commands) {
        Order order = new Order();
        order.memberId = memberId;
        order.status = OrderStatus.PLACED;
        commands.forEach(order::addLine);
        order.recalculateTotal();
        return order;
    }

    private void addLine(OrderLineCommand cmd) {
        this.lines.add(new OrderLine(this, cmd.productId(), cmd.quantity(), cmd.unitPrice()));
    }

    public void cancel() {
        if (status == OrderStatus.DELIVERED)
            throw new OrderAlreadyDeliveredException(id);
        this.status = OrderStatus.CANCELLED;
    }

    private void recalculateTotal() {
        this.totalAmount = lines.stream()
            .map(OrderLine::subtotal)
            .reduce(Money.ZERO_KRW, Money::add);
    }
}
```

### Repository

Aggregate Root 단위로만 존재한다. `OrderRepository`는 있지만 `OrderLineRepository`는 없다. OrderLine은 Order를 통해서만 접근한다. 이 원칙 하나만 지켜도 아래의 "Repository에서 직접 필드 수정하기" 같은 안티패턴이 줄어든다.

### Domain Service

엔티티 하나에 자연스럽게 속할 수 없는 **도메인 로직**은 Domain Service로 뺀다. 예: 환율 변환, 여러 Aggregate를 조회해 가격을 계산하는 규칙. 주의할 점은 Domain Service는 **인프라(DB, 외부 API)가 아니다**. 단지 "어느 엔티티에 붙이기 어색한 도메인 규칙"이다.

### Domain Event

"무언가가 일어났다"를 표현하는 불변 객체. `OrderPlacedEvent`, `PaymentCompletedEvent`. 사이드 이펙트(메일 발송, 재고 차감, 적립금 부여)를 도메인에서 분리해내는 핵심 장치다.

## JPA로 Aggregate 구현하기

JPA는 DDD를 강제하지 않지만, Aggregate 패턴과 **궁합이 좋다**.

### cascade / orphanRemoval 선택 기준

Aggregate 내부 엔티티는 Root의 **생명주기에 종속**된다. 따라서:

- `cascade = CascadeType.ALL`로 Root 저장 시 함께 저장
- `orphanRemoval = true`로 컬렉션에서 제거된 자식은 DB에서도 삭제

```java
@OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
private List<OrderLine> lines = new ArrayList<>();
```

반대로 **다른 Aggregate**와의 관계에서는 cascade를 절대 걸지 않는다. `Order`가 `Member`에 cascade를 걸면 주문 삭제가 회원 삭제로 전파된다.

### @OneToMany 선택 기준

단방향/양방향, EAGER/LAZY, `@JoinColumn`/`@JoinTable` 선택은 Aggregate 경계 안에서 이루어진다.

- Aggregate 내부: **양방향 + LAZY**가 기본. Root에서 자식을 조작하고 불변식을 검증하기 편하다.
- 컬렉션이 크거나 페이징이 필요하면 Aggregate 경계를 다시 의심. 진짜 한 트랜잭션에서 전체를 로딩할 필요가 있는가.

### @Embeddable로 VO 표현

테이블에 필드가 늘어나는 것을 두려워하지 말고, **도메인의 말**을 타입으로 옮긴다.

```java
@Embeddable
public class DateRange {
    private LocalDateTime start;
    private LocalDateTime end;

    public boolean contains(LocalDateTime t) {
        return !t.isBefore(start) && !t.isAfter(end);
    }
}

@Entity
public class Coupon {
    @Id private Long id;
    @Embedded private DateRange validPeriod;

    public boolean isUsableAt(LocalDateTime t) {
        return validPeriod.contains(t);
    }
}
```

## Repository 인터페이스의 위치 — 의존성 역전

전형적인 3-layer 아키텍처에서는 Service → Repository → DB로 흐른다. DDD/헥사고날에서는 **Repository 인터페이스를 도메인 레이어에 두고 구현체를 인프라 레이어에 둔다**.

```
domain/
  order/
    Order.java
    OrderRepository.java         // 인터페이스 (순수 도메인)
infrastructure/
  persistence/
    JpaOrderRepository.java      // Spring Data JPA 구현
    OrderRepositoryImpl.java     // 혹은 QueryDSL 조합
```

이유:
- 도메인 레이어가 JPA, MyBatis 같은 **구현 세부사항에 의존하지 않는다**. 단위 테스트에서 인메모리 구현으로 대체 가능.
- 저장소 기술 교체가 쉬워진다. MySQL에서 MongoDB로 옮기거나, 읽기 전용 캐시를 추가할 때 도메인 코드는 그대로다.
- Spring Data JPA를 쓰면서도 도메인 레이어에 `OrderRepository` 인터페이스만 두고, 인프라 레이어에 `interface JpaOrderRepository extends JpaRepository<...>, OrderRepository`를 선언해 합치는 방식이 실무적이다.

## Application Service vs Domain Service

| 구분 | Application Service | Domain Service |
|------|---------------------|----------------|
| 역할 | 유스케이스 조립 | 순수 도메인 규칙 |
| 트랜잭션 | 여기서 시작·종료 | 없음 |
| 외부 의존 | DB, 이메일, 외부 API | 원칙적으로 없음 |
| 예 | `OrderCancelService.cancel(orderId)` | `DiscountPolicy.apply(order, coupon)` |

**트랜잭션 경계는 Application Service**에 둔다. `@Transactional`을 도메인 엔티티나 Domain Service에 붙이면 "이 도메인 규칙은 DB에 붙어 있다"는 선언이 되어 응집이 깨진다.

```java
@Service
@RequiredArgsConstructor
public class CancelOrderApplicationService {
    private final OrderRepository orderRepository;
    private final RefundGateway refundGateway;
    private final ApplicationEventPublisher publisher;

    @Transactional
    public void cancel(OrderId id, String reason) {
        Order order = orderRepository.findById(id)
            .orElseThrow(() -> new OrderNotFoundException(id));
        order.cancel(); // 도메인 규칙
        // 외부 결제 취소는 트랜잭션 커밋 후에
        publisher.publishEvent(new OrderCancelledEvent(id, reason));
    }
}
```

## Domain Event 발행

### 방법 1 — Spring Data의 @DomainEvents

```java
public class Order extends AbstractAggregateRoot<Order> {
    public void cancel() {
        // ...
        registerEvent(new OrderCancelledEvent(this.id));
    }
}
```

`AbstractAggregateRoot`를 상속하면 `save()` 시점에 등록된 이벤트가 자동 발행된다. 편하지만 Spring Data JPA에 종속된다.

### 방법 2 — ApplicationEventPublisher + @TransactionalEventListener

```java
@Component
public class OrderCancelledHandler {
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(OrderCancelledEvent event) {
        // 커밋 이후에만 실행 — 보상 처리가 더 단순해진다
    }
}
```

`AFTER_COMMIT` 페이즈가 중요하다. 주문 취소 트랜잭션이 롤백됐는데 환불 메일이 나가는 사고를 막는다. 반대로 이벤트 처리 실패가 본 트랜잭션에 영향을 주지 않음을 이해하고, 유실 대비 아웃박스 패턴을 병행한다.

## 커머스 예시로 Bounded Context 나누기

OliveYoung 류 커머스 도메인을 다음과 같이 자른다.

- **Order Context**: `Order`, `OrderLine`, `OrderStatus`. 주문 수명주기 관리.
- **Payment Context**: `Payment`, `PaymentMethod`. PG 연동, 승인/취소.
- **Coupon Context**: `Coupon`, `CouponPolicy`, `IssuedCoupon`. 발급, 소진, 검증.
- **Inventory Context**: `Stock`, `Reservation`. 재고 차감/복구.

이들 사이의 관계:

- Order → Payment: Order가 upstream. `OrderId`가 Payment 쪽 식별자에 참조된다. Payment는 Order 취소 이벤트를 구독해 환불을 트리거.
- Order → Coupon: 주문 생성 시 Coupon Context에 "이 쿠폰 사용 가능?"을 질의하고, `appliedCouponId`만 Order에 저장. Coupon 객체 전체를 들고 오지 않는다.
- Order ↔ Inventory: 주문 확정 시 재고 예약 이벤트 발행 → Inventory가 처리. 실패 시 보상 트랜잭션.

```java
// Order Aggregate는 Coupon 객체를 모른다. ID만 안다.
@Entity
public class Order {
    @Embedded private CouponId appliedCouponId; // nullable
    @Embedded private Money discountAmount;     // 적용 시점에 계산된 금액만 저장
}
```

이 설계의 이점: 쿠폰 정책이 바뀌어도 과거 주문의 할인 금액은 변하지 않는다. **"과거의 사실"을 불변으로 보존**하는 것이 Aggregate 설계의 중요한 감각이다.

## 가벼운 CQRS 도입

조회 요구가 복잡해지면 명령(Command) 모델과 조회(Query) 모델을 분리한다. Event Sourcing까지 가지 않아도, **Read 전용 DTO와 전용 쿼리**만 분리해도 효과가 크다.

```java
// 명령 측 — 도메인 엔티티
@Service
public class PlaceOrderService {
    @Transactional
    public OrderId place(PlaceOrderCommand cmd) { ... }
}

// 조회 측 — 도메인 엔티티를 거치지 않는 플랫한 DTO
public interface OrderQueryDao {
    List<OrderListItemDto> findRecentByMember(MemberId memberId, Pageable p);
    OrderDetailDto findDetail(OrderId id);
}
```

`OrderDetailDto`는 주문, 결제, 쿠폰, 배송 상태를 한 번의 조인 쿼리나 애플리케이션 조합으로 채운다. Aggregate를 억지로 로딩해 DTO로 변환하는 방식보다 훨씬 단순하고 빠르다. **쓰기 모델은 일관성을 위해, 읽기 모델은 성능을 위해** 최적화한다는 관점의 분리다.

## 레거시에서 DDD로 점진 도입하기

"풀 리라이트는 실패한다." 현실적 전략은 다음과 같다.

1. **Seam 식별**: 가장 변경 요구가 많고 복잡한 모듈(예: 주문 취소 플로우)을 먼저 고른다.
2. **ACL 설치**: 해당 모듈 앞에 Anticorruption Layer를 둔다. 레거시의 `OrderEntity`를 새 도메인의 `Order`로 변환하는 번역 계층.
3. **새 로직은 새 모델로**: 새 기능은 신 도메인에서 구현. 기존 호출은 ACL을 통해 기존 모델과 호환 유지.
4. **Strangler Fig**: 기능 단위로 신 모델이 레거시를 잠식하도록 점진 이동. 한꺼번에 자르지 않는다.
5. **이벤트 도입**: 느슨한 결합이 필요해진 지점부터 Domain Event를 도입. 동기 호출 사슬을 이벤트로 끊어 Bounded Context 간 독립성을 확보.

## 안티패턴 목록

1. **Service 레이어 비만**: `OrderService` 2,000줄, 엔티티는 setter만. → Rich 모델로 로직 이동.
2. **Repository에서 비즈니스 검증**: `orderRepository.cancelOrderIfNotDelivered(id)` 같은 메서드. Repository는 저장소 추상화이지 정책 판단자가 아니다.
3. **Setter 난사**: `public` setter는 불변식을 깨는 최단 경로다. 상태 변경은 `cancel()`, `approve()` 같은 의도가 드러나는 메서드로.
4. **Aggregate 간 객체 참조**: `Order`가 `Member` 엔티티를 직접 들고 있음 → 트랜잭션 경계 혼란, 대규모 객체 그래프 로딩. **ID 참조**로 바꾼다.
5. **EAGER 기본**: `@OneToMany(fetch = EAGER)`는 Aggregate 경계를 의심하게 만든다. 기본은 LAZY, 필요한 유스케이스에서만 fetch join.
6. **도메인에 Spring/JPA 어노테이션 범람**: 도메인 엔티티에 `@Transactional`, `@CachePut` 등이 붙으면 응집이 깨진다. 이런 관심사는 Application 레이어로.

## 후보 경험의 DDD 재해석

후보자가 가진 다음 경험은 DDD 용어로 자연스럽게 번역된다.

- **slot 엔진 추상화 / 전략 패턴 도입**: 할인 정책·슬롯 선정 알고리즘을 `DiscountPolicy`, `SlotSelectionStrategy` 같은 **Domain Service**로 분리한 사례. OCP를 지키면서 정책 교체 비용을 낮춘 것은 전형적인 DDD식 리팩터링이다.
- **내부 모듈 경계 분리**: 서로 다른 팀/기능이 공유하던 단일 모듈을 기능 단위로 쪼갠 경험 → **Bounded Context 분리**. 공유되던 DTO를 각 컨텍스트 안에서 자체 모델로 재정의한 경험이 있다면 강력한 어필 포인트.
- **공통 유틸에서 벗어나 도메인 중심으로 이동**: `CommonUtil.calculate(...)`를 엔티티의 `calculate()` 메서드로 옮긴 경험 → Anemic에서 Rich로의 이동.

면접에서는 "전략 패턴을 적용했습니다"보다 "**정책 객체를 Domain Service로 분리해 할인 규칙이 엔티티 상태와 분리되도록 설계했습니다**"가 훨씬 강하게 들린다.

## 로컬 실습 환경

```
project/
├── build.gradle
├── docker-compose.yml
└── src/main/java/com/example/shop/
    ├── order/
    │   ├── domain/
    │   │   ├── Order.java
    │   │   ├── OrderLine.java
    │   │   ├── OrderRepository.java
    │   │   └── event/OrderCancelledEvent.java
    │   ├── application/
    │   │   ├── PlaceOrderService.java
    │   │   └── CancelOrderService.java
    │   └── infrastructure/
    │       └── JpaOrderRepository.java
    └── coupon/
        └── ...
```

docker-compose로 MySQL 8을 띄운다.

```yaml
version: "3.8"
services:
  mysql:
    image: mysql:8.0
    ports: ["3306:3306"]
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: shop
```

`application.yml`에서 `hibernate.jdbc.batch_size=50`, `order_inserts=true`, `order_updates=true`를 켠다. Aggregate 저장 시 자식 insert가 배치로 묶여 나가는지 `show_sql` 로그로 확인한다.

## 실행 가능한 실습 시나리오

1. `Order.place(...)` 정적 팩토리로 주문을 생성하고, OrderLine 3개 중 1개를 컬렉션에서 제거해 `orphanRemoval` 동작을 확인한다.
2. `Order.cancel()` 안에서 `AbstractAggregateRoot.registerEvent`를 호출하고, `@TransactionalEventListener(AFTER_COMMIT)`가 실제로 커밋 후에만 실행되는지 로그로 검증한다. 의도적으로 예외를 던져 롤백 시 이벤트가 발행되지 않는지 확인.
3. `OrderRepository` 인터페이스를 도메인 패키지에 두고, 인프라 패키지의 `JpaOrderRepository`가 이를 `extends`하도록 구성. 도메인 코드에서 `jakarta.persistence.*` import가 하나도 없는 상태를 만든다.
4. 같은 `Money` VO를 두 번 생성해 `equals` 결과를 검증. JPA 로딩 후에도 값이 같으면 동일 객체로 취급되는지 확인.
5. `Order`가 `Member` 객체 대신 `MemberId`만 가지도록 리팩터링하고, N+1 문제가 사라지는 것을 SQL 로그로 확인.
6. 조회 전용 `OrderQueryDao`를 별도로 만들어 주문 목록 화면 전용 쿼리를 작성. 명령 모델을 거치지 않는 것을 확인.

## 면접 답변 프레이밍

**Q. 도메인 모델링은 어떻게 하시나요?**

> 저는 도메인을 Bounded Context 단위로 먼저 나눕니다. 같은 "상품"이라도 주문과 재고에서 다른 책임을 지니기 때문에 하나의 모델로 합치지 않습니다. 컨텍스트 안에서는 Entity와 Value Object를 구분해, 식별자로 추적해야 할 것은 Entity, 값 자체가 의미인 것은 VO로 표현합니다. 비즈니스 규칙은 서비스가 아니라 엔티티 자신의 메서드로 두어 불변식이 깨지지 않도록 합니다. 예전에 쿠폰 정책 모듈을 리팩터링할 때 `CouponService.validate(coupon, order)`에 흩어진 규칙을 `Coupon.isUsableFor(order)`로 옮긴 적이 있는데, 이후 새 정책 추가 비용이 반으로 줄었습니다.

**Q. Aggregate 경계는 어떻게 정하시나요?**

> 핵심 질문은 "어떤 것들이 한 트랜잭션에서 함께 일관성을 지켜야 하는가"입니다. 주문과 주문 라인은 금액 합계 불변식이 있으니 한 Aggregate, 주문과 결제는 트랜잭션을 분리할 수 있고 실제로 분리해야 동시성이 확보되니 별도 Aggregate로 둡니다. Aggregate는 작게 유지하고, 다른 Aggregate는 객체가 아닌 ID로 참조합니다. 과거에 Order가 Member 엔티티를 직접 참조해 발생한 N+1과 캐스케이드 사고를 겪고 나서 이 원칙을 철저하게 지킵니다.

**Q. 레거시 코드에 DDD를 어떻게 도입하시겠습니까?**

> 풀 리라이트는 거의 실패하니, Strangler Fig 방식으로 접근합니다. 변경 빈도가 높은 모듈부터 식별해 ACL로 둘러싸고, 새 기능은 신 도메인 모델에서 구현합니다. 기존 호출부는 ACL을 통해 호환을 유지합니다. 이 과정에서 Bounded Context 경계를 처음에는 느슨하게 긋고, Ubiquitous Language가 안정된 다음에 점점 단단하게 굳혀갑니다.

## 체크리스트

- [ ] 엔티티에 public setter가 없는가 (상태 변경은 의도가 드러나는 메서드로)
- [ ] Aggregate Root만 Repository를 갖는가
- [ ] 다른 Aggregate는 ID로만 참조하는가
- [ ] 도메인 레이어에 JPA/Spring 어노테이션이 최소한으로만 사용되는가
- [ ] 트랜잭션 경계가 Application Service에 있는가, 엔티티나 Domain Service에 분산되지 않았는가
- [ ] VO는 불변이고 equals/hashCode가 값 기반인가
- [ ] cascade와 orphanRemoval이 Aggregate 경계 안에서만 사용되는가
- [ ] Domain Event가 `AFTER_COMMIT` 페이즈에서 발행되는가
- [ ] 읽기 복잡도가 큰 화면은 별도 Query 모델을 갖는가
- [ ] Ubiquitous Language가 코드, DB 컬럼명, API 스펙에 일관되게 반영되어 있는가
- [ ] 레거시와 새 모델 사이에 ACL이 존재하는가
- [ ] 면접에서 "Aggregate 경계를 어떻게 정하냐"에 30초 안에 구체 사례로 답할 수 있는가
