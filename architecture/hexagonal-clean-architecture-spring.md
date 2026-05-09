# [초안] Hexagonal / Clean Architecture를 Spring 백엔드에 적용하기

## 왜 지금 이 주제인가

Spring 기반 백엔드 경력 중후반에서 가장 자주 마주치는 질문이 두 가지 있다. "왜 우리 서비스는 비즈니스 로직이 Controller, Service, Entity, Repository 사이에 흩어져 있어서 매번 바꾸기가 무서운가?" 그리고 "그렇다고 Hexagonal Architecture니 Clean Architecture니 하는 걸 그대로 도입하면 클래스 수만 두 배가 되고 정작 변경 비용은 줄지 않는데, 어디까지 가야 하는가?"

면접에서도 똑같은 형태로 물어본다. "도메인 로직과 인프라 코드를 분리한 경험이 있는가", "JPA 엔티티를 그대로 도메인 모델로 쓰는 것의 문제는 무엇인가", "이 코드에 트랜잭션 경계를 어디에 두어야 하는가". 이 질문들에 답하려면 Hexagonal/Clean이라는 단어를 외워서 되는 게 아니라, **경계를 어디에 긋고 무엇을 그 경계 안에 둘지**를 자기 언어로 설명할 수 있어야 한다. 이 글은 그 경계를 Spring 코드 위에 직접 그려 보는 것을 목표로 한다.

도메인 모델 자체에 대한 더 일반적인 설명은 [DDD와 도메인 모델링](./ddd-domain-modeling.md) 문서가 어울리고, 이 문서는 그중에서도 **Hexagonal/Clean이라는 경계 모델을 Spring 컴포넌트(Controller, Service, JPA, Kafka 등) 위에 올리는 실전 기술**에 집중한다.

## 핵심 개념: 한 문장으로 정리부터

Hexagonal Architecture(Alistair Cockburn)와 Clean Architecture(Robert C. Martin)는 이름과 비유가 다르지만, 실질적으로는 같은 한 가지 규칙을 말한다.

> **의존성은 항상 바깥(인프라/프레임워크) → 안쪽(도메인) 방향으로만 향해야 한다. 안쪽은 바깥을 모른다.**

Hexagonal은 이 규칙을 "포트(Port)와 어댑터(Adapter)"라는 입출력 비유로 표현한다.
- **Inbound Port**: 도메인이 "나를 이렇게 호출해 달라"고 외부에 노출하는 인터페이스 (UseCase)
- **Inbound Adapter**: HTTP Controller, Kafka Listener, 스케줄러처럼 그 UseCase를 호출해 주는 쪽
- **Outbound Port**: 도메인이 "이런 능력이 필요하다"고 외부에 요구하는 인터페이스 (Repository, MessagePublisher, ExternalApiClient)
- **Outbound Adapter**: JPA 구현체, Redis 구현체, FeignClient 구현체

Clean Architecture는 같은 구조를 동심원으로 그린다. 가장 안쪽에 Entities(엔터프라이즈 비즈니스 룰), 그 바깥에 Use Cases(애플리케이션 비즈니스 룰), 더 바깥에 Interface Adapters(Controller, Presenter, Gateway), 가장 바깥에 Frameworks & Drivers(Spring, JPA, Kafka, DB). 안쪽 원이 바깥 원을 import하지 않는다는 점만 지키면, 사실상 Hexagonal과 같은 그림이다.

실무에서 어느 용어를 쓰든 합의해야 하는 본질은 셋이다.
1. **도메인은 Spring/JPA를 import하지 않는다.** `@Entity`, `@Service`, `@Transactional`, `@Autowired`가 도메인 클래스에 등장하면 이미 경계가 무너져 있는 것이다. (현실에선 점진 도입 단계에서 타협하는 경우가 많고, 이 문서 후반에서 그 타협의 기준을 다룬다.)
2. **포트는 도메인이 정의한다.** Repository 인터페이스가 `org.springframework.data` 아래의 타입을 노출하면 그건 포트가 아니라 그냥 Spring Data 인터페이스다.
3. **유스케이스는 한 번의 비즈니스 의도 단위로 잘린다.** "사용자 가입", "쿠폰 발급", "슬롯 회차 정산" — Controller 메서드 1:1로 잘리는 게 아니라 비즈니스 의도 1:1로 잘린다.

## Spring 컴포넌트 위에 경계 그리기

레이어 이름을 어떻게 붙이든 결국 Spring 백엔드는 다음 다섯 부류의 코드를 갖는다. 어느 패키지에 두든, 어느 부류가 어느 부류를 호출해도 되는지가 경계다.

| 부류 | 책임 | 의존 가능 방향 |
|------|------|----------------|
| Controller (Web Adapter) | HTTP ↔ UseCase 호출, DTO ↔ Command 변환 | UseCase Port만 의존 |
| Application Service (UseCase 구현) | 트랜잭션 경계, 도메인 객체 협력 조율 | Domain, Outbound Port |
| Domain Model | 비즈니스 규칙, 불변식, 상태 전이 | 자기 자신만 |
| Outbound Port | 도메인이 외부에 요구하는 능력의 인터페이스 | Domain |
| Outbound Adapter (JPA/Redis/Feign 등) | 포트 구현, 외부 시스템 통신 | Outbound Port |

이 표만 지켜도 Hexagonal/Clean 상당 부분이 충족된다. 다음 질문들에 어떻게 답하느냐가 실제 설계의 디테일이다.

### JPA 엔티티 = 도메인 모델? 분리해야 하나?

가장 자주 나오는 질문이고 답이 둘로 갈린다.

- **합치는 쪽**: `@Entity` 클래스에 비즈니스 메서드를 두고, 그게 곧 도메인이다. 매핑 클래스를 두 벌 만들지 않아 코드량이 적고, 단순한 CRUD 도메인엔 충분하다.
- **분리하는 쪽**: 순수 POJO `Order` 도메인과 JPA 매핑용 `OrderJpaEntity`를 따로 두고, Repository 어댑터가 둘 사이를 매핑한다. 도메인 모델이 영속성 라이프사이클(`detached`, lazy loading proxy 등)에서 자유로워지고, 단위 테스트가 압도적으로 쉬워진다. 대신 매핑 코드와 클래스 수가 늘어난다.

실전 기준은 단순하다. **도메인 모델이 JPA 라이프사이클 때문에 표현력이 망가지기 시작하면 분리한다.** 예를 들어 `Order` 안에 `cancel()` 메서드를 넣었는데, `cancel()`이 lazy 컬렉션을 건드리거나 영속성 컨텍스트가 닫힌 뒤에 호출되면 깨지는 식이라면 이미 신호다. 또, 같은 도메인 개념을 여러 영속 저장소(MySQL + Elasticsearch + 외부 API)에 분산 저장해야 하면 도메인 모델은 어느 한쪽 매핑에 종속될 수 없으므로 분리해야 한다.

CJ푸드빌처럼 디지털 채널(웹/앱/POS/배달 플랫폼) 다채널을 다루는 백엔드는 같은 "주문" 개념이 채널마다 약간씩 다르게 영속화되거나, 외부 채널 API 응답에 끌려다니기 쉽다. 이때 JPA 엔티티 = 도메인 전략을 끝까지 끌면 채널마다 엔티티를 복제하거나 한 엔티티에 채널 분기가 누적되는 흔한 안티패턴이 생긴다. 도메인 `Order`와 채널별 `OrderProjection` / `OrderJpaEntity`를 분리하는 편이 결국 변경 비용이 싸다.

### 트랜잭션 경계는 어디?

원칙: **트랜잭션은 유스케이스 = Application Service에서 시작하고 끝난다.** Controller에 `@Transactional`을 붙이지 않는다 (HTTP 라이프사이클과 트랜잭션 라이프사이클이 섞이면 예외 처리, 비동기, 재시도 설계가 다 꼬인다). Repository 메서드 단위로 트랜잭션을 거는 것도 피한다 (한 유스케이스 안에서 여러 Repository 호출이 한 트랜잭션이 되어야 하기 때문).

도메인 모델은 `@Transactional`을 모른다. "한 트랜잭션 안에서 일관성을 지킬 책임"은 유스케이스 레벨의 약속이고, 도메인은 그저 자기 불변식만 책임진다.

외부 시스템 호출(결제, 채널사 API, Kafka 발행)은 트랜잭션 경계 안에서 직접 호출하지 않는 게 원칙이다. DB 트랜잭션이 롤백되어도 외부 호출은 되돌릴 수 없기 때문이다. Outbound Port를 두되, 발행 실제 시점은 `TransactionalEventListener(phase = AFTER_COMMIT)` 또는 outbox 패턴으로 미루는 편이 실무적으로 안전하다.

### DTO와 도메인 모델, 그리고 Command/Result

경계마다 다른 자료형을 쓰는 게 정석이다.

- **Web ↔ Controller**: `OrderCreateRequest`, `OrderResponse` (Jackson 직렬화 친화적, validation 포함)
- **Controller ↔ UseCase**: `CreateOrderCommand`, `OrderView` (Spring 의존성 없음, 의도 표현)
- **UseCase ↔ Domain**: `Order`, `OrderLine`, `Money` 같은 도메인 객체
- **Adapter ↔ DB**: `OrderJpaEntity`

매핑이 늘어 보이지만 각 경계의 변경 이유가 다르다는 게 핵심이다. API 스펙 변경(Web DTO), 유스케이스 인자 변경(Command), 도메인 규칙 변경(Domain), 스키마 변경(JpaEntity) 중 어느 하나가 다른 셋을 끌어다니지 않게 하는 것이 분리의 가치다.

## Bad vs Improved 예제

### Bad: 트랜잭셔널 스크립트 + 만능 Service

```java
@RestController
@RequiredArgsConstructor
public class OrderController {
    private final OrderService orderService;

    @PostMapping("/orders")
    @Transactional
    public OrderResponse create(@RequestBody OrderCreateRequest req) {
        return orderService.create(req);
    }
}

@Service
@RequiredArgsConstructor
public class OrderService {
    private final OrderRepository orderRepository; // JpaRepository<OrderEntity, Long>
    private final CouponRepository couponRepository;
    private final PaymentClient paymentClient;     // FeignClient
    private final KafkaTemplate<String, String> kafka;

    public OrderResponse create(OrderCreateRequest req) {
        OrderEntity order = new OrderEntity();
        order.setUserId(req.getUserId());
        order.setItems(req.getItems().stream().map(i -> {
            OrderItemEntity e = new OrderItemEntity();
            e.setSku(i.getSku());
            e.setQty(i.getQty());
            e.setPrice(i.getPrice());
            return e;
        }).collect(Collectors.toList()));

        if (req.getCouponCode() != null) {
            CouponEntity coupon = couponRepository.findByCode(req.getCouponCode())
                .orElseThrow(() -> new RuntimeException("쿠폰 없음"));
            if (coupon.isUsed()) throw new RuntimeException("이미 사용됨");
            int discount = coupon.getAmount();
            int total = order.getItems().stream().mapToInt(i -> i.getPrice() * i.getQty()).sum() - discount;
            if (total < 0) total = 0;
            order.setTotal(total);
            coupon.setUsed(true);
        } else {
            order.setTotal(order.getItems().stream().mapToInt(i -> i.getPrice() * i.getQty()).sum());
        }

        orderRepository.save(order);
        paymentClient.charge(order.getId(), order.getTotal());      // 외부 호출
        kafka.send("order-created", String.valueOf(order.getId())); // 외부 호출

        OrderResponse res = new OrderResponse();
        res.setOrderId(order.getId());
        res.setTotal(order.getTotal());
        return res;
    }
}
```

여기서 곪는 지점들.
- Controller에 `@Transactional`이 붙어 HTTP/트랜잭션 라이프사이클이 섞임.
- 비즈니스 규칙(쿠폰 사용 가능 여부, 음수 총액 보정, 합계 계산)이 Service 절차 코드 안에 흩어져 있어 단위 테스트하려면 JPA 엔티티와 Repository를 모두 mock해야 함.
- `paymentClient.charge()`와 `kafka.send()`가 DB 트랜잭션 안에서 일어나, 트랜잭션 롤백 시 외부 부수효과를 되돌릴 수 없음.
- `OrderEntity`가 JPA 매핑이자 비즈니스 규칙이 들어있는 자리. 후에 검색용 Elasticsearch 모델, 채널별 응답 모델을 도입할 때 갈라치기 어려움.

### Improved: UseCase + Port + Domain

도메인:

```java
// domain/order/Order.java  — Spring/JPA 의존 없음
public class Order {
    private final OrderId id;
    private final UserId userId;
    private final List<OrderLine> lines;
    private Money total;
    private OrderStatus status;

    public static Order create(UserId userId, List<OrderLine> lines, Optional<Coupon> coupon) {
        Money subtotal = lines.stream().map(OrderLine::amount).reduce(Money.ZERO, Money::add);
        Money discounted = coupon.map(c -> c.applyTo(subtotal)).orElse(subtotal);
        if (discounted.isNegative()) discounted = Money.ZERO;
        return new Order(OrderId.next(), userId, lines, discounted, OrderStatus.PLACED);
    }

    public Money total() { return total; }
    public OrderId id()  { return id; }
    // ... 상태 전이 메서드
}

public class Coupon {
    private final CouponCode code;
    private final Money amount;
    private boolean used;

    public Money applyTo(Money subtotal) {
        if (used) throw new CouponAlreadyUsedException(code);
        return subtotal.minus(amount);
    }
    public void markUsed() { this.used = true; }
}
```

Inbound Port (UseCase):

```java
// application/port/in/PlaceOrderUseCase.java
public interface PlaceOrderUseCase {
    OrderPlacedResult place(PlaceOrderCommand command);
}

public record PlaceOrderCommand(String userId, List<Line> lines, String couponCode) {
    public record Line(String sku, int qty, long unitPrice) {}
}
```

Outbound Port:

```java
// application/port/out/OrderRepositoryPort.java
public interface OrderRepositoryPort {
    void save(Order order);
    Optional<Order> findById(OrderId id);
}

// application/port/out/CouponRepositoryPort.java
public interface CouponRepositoryPort {
    Optional<Coupon> findByCode(CouponCode code);
    void save(Coupon coupon);
}

// application/port/out/PaymentPort.java
public interface PaymentPort {
    void charge(OrderId id, Money amount);
}

// application/port/out/OrderEventPublisher.java
public interface OrderEventPublisher {
    void publishPlaced(OrderId id);
}
```

UseCase 구현 (Application Service):

```java
@Service
@RequiredArgsConstructor
public class PlaceOrderService implements PlaceOrderUseCase {
    private final OrderRepositoryPort orderRepo;
    private final CouponRepositoryPort couponRepo;
    private final PaymentPort payment;
    private final OrderEventPublisher events;

    @Transactional
    @Override
    public OrderPlacedResult place(PlaceOrderCommand cmd) {
        Optional<Coupon> coupon = Optional.ofNullable(cmd.couponCode())
            .map(CouponCode::of).flatMap(couponRepo::findByCode);

        Order order = Order.create(UserId.of(cmd.userId()), toLines(cmd.lines()), coupon);
        coupon.ifPresent(c -> { c.markUsed(); couponRepo.save(c); });
        orderRepo.save(order);

        // 결제와 이벤트 발행은 도메인 트랜잭션 밖에서 일어나도록 후처리에 위임
        payment.charge(order.id(), order.total());
        events.publishPlaced(order.id());

        return new OrderPlacedResult(order.id().value(), order.total().value());
    }
}
```

Outbound Adapter (JPA):

```java
@Repository
@RequiredArgsConstructor
class OrderRepositoryAdapter implements OrderRepositoryPort {
    private final OrderJpaRepository jpa;
    private final OrderJpaMapper mapper;

    @Override public void save(Order order) { jpa.save(mapper.toJpa(order)); }
    @Override public Optional<Order> findById(OrderId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }
}
```

차이가 어디서 오는가.
- `PlaceOrderService`를 테스트할 때 4개 포트를 fake로 주입하면 끝난다. JPA, Spring 컨텍스트, Kafka 모두 필요 없다.
- `Order.create()`만으로 "쿠폰 적용 후 음수 총액이면 0으로 보정"이라는 규칙을 단위 테스트할 수 있다. 이게 도메인 단위 테스트의 가치다.
- 결제/이벤트 발행은 포트로 추상화돼 있어서, 추후 outbox 패턴이나 `@TransactionalEventListener(AFTER_COMMIT)`로 전환할 때 UseCase 코드를 거의 바꾸지 않는다.

## 로컬 실습 환경

학습용으로 가볍게 돌릴 환경 한 벌:

```bash
# JDK 17, Gradle 8.x, Docker 가정
mkdir hex-spring-lab && cd hex-spring-lab
gradle init --type java-application --dsl groovy --test-framework junit-jupiter --package com.example.hex --project-name hex
```

`build.gradle` 의존성 최소 셋:

```groovy
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web:3.3.0'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa:3.3.0'
    runtimeOnly    'com.mysql:mysql-connector-j:8.4.0'
    compileOnly    'org.projectlombok:lombok:1.18.32'
    annotationProcessor 'org.projectlombok:lombok:1.18.32'
    testImplementation 'org.springframework.boot:spring-boot-starter-test:3.3.0'
    testImplementation 'org.testcontainers:junit-jupiter:1.19.8'
    testImplementation 'org.testcontainers:mysql:1.19.8'
}
```

MySQL 8 컨테이너:

```bash
docker run -d --name hex-mysql -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=hexlab -p 3306:3306 mysql:8.0
```

권장 패키지 구조:

```
com.example.hex
├── adapter
│   ├── in.web        (Controller, Web DTO)
│   └── out
│       ├── persistence (JpaEntity, JpaRepository, RepositoryAdapter)
│       └── payment    (FeignClient, PaymentAdapter)
├── application
│   ├── port.in       (UseCase 인터페이스, Command/Result)
│   ├── port.out      (Repository/Payment/Event 포트)
│   └── service       (UseCase 구현)
└── domain
    └── order         (Order, OrderLine, Money, Coupon ...)
```

이 패키지 구조를 ArchUnit으로 강제하면 PR마다 경계 위반을 잡을 수 있다.

```java
@Test
void domain_must_not_depend_on_spring_or_jpa() {
    JavaClasses classes = new ClassFileImporter().importPackages("com.example.hex");
    noClasses().that().resideInAPackage("..domain..")
        .should().dependOnClassesThat().resideInAnyPackage(
            "org.springframework..", "jakarta.persistence..", "org.hibernate.."
        ).check(classes);
}
```

## 실행 가능한 미니 예제: 쿠폰 적용 단위 테스트

도메인만 가지고 돌아가는 테스트가 이 아키텍처의 진짜 효용이다.

```java
class OrderTest {
    @Test
    void 쿠폰_적용_후_음수면_0으로_보정된다() {
        var lines = List.of(new OrderLine(Sku.of("A"), 1, Money.of(1000)));
        var coupon = new Coupon(CouponCode.of("C1"), Money.of(5000));

        Order order = Order.create(UserId.of("u1"), lines, Optional.of(coupon));

        assertThat(order.total()).isEqualTo(Money.ZERO);
    }

    @Test
    void 이미_사용된_쿠폰은_적용시_예외() {
        var coupon = new Coupon(CouponCode.of("C1"), Money.of(500));
        coupon.markUsed();
        assertThatThrownBy(() ->
            Order.create(UserId.of("u1"),
                List.of(new OrderLine(Sku.of("A"), 1, Money.of(1000))),
                Optional.of(coupon)))
            .isInstanceOf(CouponAlreadyUsedException.class);
    }
}
```

UseCase 테스트는 포트 in-memory 구현으로:

```java
class PlaceOrderServiceTest {
    @Test
    void 주문_저장과_쿠폰_사용처리가_함께_일어난다() {
        var orderRepo  = new InMemoryOrderRepo();
        var couponRepo = new InMemoryCouponRepo();
        couponRepo.save(new Coupon(CouponCode.of("C1"), Money.of(2000)));
        var payment = mock(PaymentPort.class);
        var events  = mock(OrderEventPublisher.class);

        var sut = new PlaceOrderService(orderRepo, couponRepo, payment, events);
        var result = sut.place(new PlaceOrderCommand("u1",
            List.of(new PlaceOrderCommand.Line("A", 1, 5000)), "C1"));

        assertThat(result.total()).isEqualTo(3000L);
        assertThat(couponRepo.findByCode(CouponCode.of("C1")).orElseThrow().isUsed()).isTrue();
        verify(payment).charge(any(), eq(Money.of(3000)));
    }
}
```

Spring 컨텍스트 없이 돌아간다는 사실이 핵심이다. 실행 시간이 ms 단위이고, JPA 영속성 컨텍스트와 무관하게 비즈니스 규칙만 검증한다.

## 흔한 실수 / 안티패턴

- **포트인 척하는 Spring Data 인터페이스**: `OrderRepositoryPort extends JpaRepository<...>` 같은 형태. 도메인이 Spring을 import하기 시작하면서 경계가 무너진다.
- **UseCase가 Web DTO를 받는다**: Controller가 `OrderCreateRequest`를 그대로 Service에 넘기면 API 변경이 곧 유스케이스 변경이 된다. Command 객체 한 단계를 빼먹지 말 것.
- **도메인에 `@Transactional`**: 도메인 메서드는 트랜잭션 인지 못 한다. 트랜잭션은 유스케이스의 약속이다.
- **모든 클래스를 두 벌씩**: CRUD가 90%인 어드민 페이지에 `Order` 도메인과 `OrderJpaEntity`를 분리하면 비용만 증가한다. 비즈니스 규칙이 거의 없는 경계에서는 JPA 엔티티 = 모델로 두고, 규칙이 자라기 시작하면 그때 분리한다.
- **외부 호출이 트랜잭션 안**: 결제, 채널 API, Kafka 발행을 트랜잭션 안에서 직접 호출. 롤백 시점에 부수효과가 남는다. AFTER_COMMIT 또는 outbox로.

## 어디까지 적용해야 하는가 (과설계 기준)

도입 강도를 세 단계로 본다.

1. **단계 0 — 그냥 Layered**: Controller / Service / Repository / Entity. 비즈니스 규칙이 적은 CRUD 어드민, 짧은 수명의 PoC.
2. **단계 1 — UseCase + Port (도메인은 Entity 재사용)**: Application Service를 명시적으로 분리하고, Outbound Port를 Repository 위에 인터페이스로 둔다. JPA 엔티티는 그대로 도메인 역할도 겸한다. 대부분의 백엔드는 여기서 충분하다.
3. **단계 2 — Pure Domain 분리**: 도메인 모델과 JPA 엔티티 분리, 매퍼, ArchUnit, 멀티 어댑터. 도메인 규칙이 풍부하거나(주문/정산/회원 등급/쿠폰), 멀티 채널/멀티 영속성/멀티 외부 시스템이거나, 팀이 충분히 크고 변경 빈도가 높을 때.

레거시 커머스 코드에 한 번에 단계 2를 적용하려고 하면 거의 항상 실패한다. 효과적인 패턴은 다음과 같다.
- 새로 추가하는 유스케이스부터 `application/port` 패키지를 신설해서 시작
- 가장 자주 바뀌는 도메인(보통 가격/할인/정산) 한 덩어리만 골라 도메인 클래스를 추출
- ArchUnit으로 새 패키지의 의존 규칙을 강제. 기존 패키지는 예외 처리하다가 점진적으로 줄여 나감
- 한 PR에 "구조 이동 + 동작 변경"을 동시에 넣지 않음. 이동만 하는 PR과 동작 변경 PR을 분리

## 면접 답변 프레이밍 (시니어 백엔드)

지원자 본인의 SlotTemplate / RccSpinResultAnalyzer / Provider 전략 패턴 경험을 포트-어댑터 언어로 다시 풀면 다음과 같은 답이 가능하다.

> "슬롯 회차 결과 분석은 SlotTemplate이라는 도메인 개념이 중심이었고, RccSpinResultAnalyzer는 그 템플릿이 정한 규칙을 적용해 한 회차의 결과를 산출하는 책임이었습니다. 외부에서 보면 '회차 결과 분석'이라는 하나의 유스케이스이고, 안에서는 템플릿 조회와 결과 산출이라는 도메인 협력입니다. 이걸 포트-어댑터로 다시 보면, Inbound Port는 `AnalyzeSpinResultUseCase` 같은 형태가 되고, Outbound Port는 SlotTemplate 조회를 위한 `SlotTemplateRepositoryPort`와 외부 게임 Provider별 결과 조회를 위한 `SpinResultProviderPort`로 분리됩니다. 실제로 Provider별로 응답 포맷이 달랐기 때문에 전략 패턴으로 구현했는데, 그게 곧 한 Outbound Port에 대한 다중 어댑터(ProviderA Adapter / ProviderB Adapter)였다고 정리할 수 있습니다. 도메인은 어느 Provider를 쓰는지 모르고, 어댑터 선택은 Application Service나 팩토리가 책임집니다. 그래서 새 Provider가 붙어도 도메인과 UseCase는 변경 없이 어댑터만 추가하면 됐습니다."

이 답변에는 면접관이 듣고 싶어 하는 키워드가 자연스럽게 들어간다 — 책임 분리, Port/Adapter, 전략 패턴의 역할, OCP, 변경 영향 범위.

후속 질문 대비 포인트:
- "JPA 엔티티와 도메인을 분리하셨나요?" → 단계 1/2 기준을 그대로 답한다. "규칙이 자라는 도메인은 분리했고, CRUD에 가까운 부분은 엔티티 재사용으로 두었습니다. 분리 기준은 영속성 라이프사이클이 도메인 표현력을 망치기 시작하는 시점이었습니다."
- "트랜잭션 경계는요?" → "Application Service에 두고, 외부 호출은 AFTER_COMMIT 또는 outbox로 미뤘습니다. Controller에는 트랜잭션을 두지 않았습니다."
- "그게 과설계 아닌가요?" → "도입 강도를 세 단계로 보고, 새 유스케이스부터 상위 단계로 시작해 ArchUnit으로 침범을 막는 방식으로 점진 도입했습니다. 한 번에 전체 리팩터링은 비용 대비 효과가 낮다고 판단했습니다."
- "Clean Architecture와 Hexagonal Architecture 차이는?" → "본질은 같습니다. 의존성 방향이 항상 안쪽으로 향한다는 규칙. Clean은 동심원으로 표현하고 Use Cases / Entities를 명시적으로 구분하는 반면, Hexagonal은 Port/Adapter 입출력 비유로 표현합니다. Spring 위에서는 둘 다 결국 Controller-UseCase-Domain-Port-Adapter라는 같은 다섯 부류로 구현됩니다."

## 체크리스트

- [ ] 도메인 패키지가 `org.springframework`, `jakarta.persistence`, `org.hibernate`를 import하지 않는다
- [ ] Outbound Port 인터페이스를 도메인/애플리케이션 쪽이 정의하고, JPA Repository는 그 어댑터다
- [ ] Controller에 `@Transactional`이 없다
- [ ] UseCase 구현에 `@Transactional`이 있고, 외부 시스템 호출은 트랜잭션 밖 또는 AFTER_COMMIT/outbox로 미뤄져 있다
- [ ] Web DTO와 Command 객체가 분리되어 있다
- [ ] 도메인 단위 테스트가 Spring 컨텍스트 없이 ms 단위로 돈다
- [ ] 같은 외부 자원에 대해 다중 구현(예: 다중 Provider)이 필요할 때, 그 자리는 하나의 포트 + 다중 어댑터로 풀린다
- [ ] ArchUnit 또는 모듈 시스템으로 의존 방향이 강제된다
- [ ] 새 유스케이스부터 점진 도입할 진입점이 정해져 있다 (모든 레거시를 한 번에 바꾸려 하지 않는다)
- [ ] 면접에서 "이건 왜 이렇게 했나"를 단계 0/1/2 기준으로 trade-off까지 설명할 수 있다
