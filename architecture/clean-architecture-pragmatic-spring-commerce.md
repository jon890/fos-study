# [초안] 커머스 Spring 서비스에 Clean/Hexagonal Architecture를 실용적으로 적용하기

## 왜 중요한가

외식·커머스 도메인은 표면적으로는 "메뉴 CRUD에 결제 붙이기"처럼 보이지만, 실제로는 매장 운영, 재고, 프로모션, 결제, 주문 상태 머신이 얽힌다. 이때 모든 로직을 `@Service` 한 클래스에 몰면 처음 6개월은 빠르지만, 1년 차부터는 결제 PG 교체, 재고 정책 변경, 주문 상태 추가가 수십 개의 if-else 가지를 수정해야 끝나는 상태로 변한다. Clean Architecture와 Hexagonal Architecture(포트/어댑터)는 이런 도메인을 **외부 기술이 바뀌어도 핵심 정책이 흔들리지 않게** 분리하는 도구다.

다만 모든 화면을 헥사고날로 짜면 1주일 작업이 1달이 된다. 실전에서 중요한 것도 "다 짤 줄 아느냐"가 아니라 "어디까지 적용하고 어디서 멈추느냐"다. 이 글은 그 경계선을 잡는 실전 문서다.

## 핵심 개념: 의존성 방향만 기억하면 된다

Clean Architecture의 다이어그램은 네 겹이지만 본질은 한 줄이다.

> **외부(웹, DB, 메시징, PG)는 도메인을 안다. 도메인은 외부를 모른다.**

Spring 표준 레이어드 아키텍처에서는 보통 다음과 같이 의존성이 흐른다.

```
Controller → Service → Repository(JPA) → Entity(@Entity)
```

여기서 `Service`가 `JpaRepository`와 `@Entity`에 직접 의존하는 순간, "DB가 MySQL이라는 사실"이 비즈니스 정책 안으로 새어 들어온다. 헥사고날에서는 다음과 같이 바꾼다.

```
[adapter-in]  HTTP Controller, Kafka Listener
       │
       ▼
[application] UseCase 인터페이스 ← 구현 ApplicationService
       │  ↓ 사용         ↑ 호출
       ▼
[domain]      Order, OrderLine, OrderPolicy (POJO)
       ▲
       │ 구현
[adapter-out] OrderJpaRepository, KafkaPublisher, TossPaymentClient
       │ implements
[application] OrderRepository(port), PaymentPort
```

즉 `application` 모듈은 자기보다 안쪽(domain)만 알고, 바깥쪽(adapter)은 인터페이스(port)로만 안다. Spring DI가 런타임에 어댑터를 꽂아준다.

## 커머스에서 어디까지 적용할지: CRUD vs 복잡 도메인

실용적으로 모든 Bounded Context에 같은 깊이로 적용하지 않는다. 보통 다음 기준으로 나눈다.

| 유형 | 예시(외식 커머스) | 권장 스타일 |
|------|--------------------|------------|
| 단순 CRUD | 매장 영업시간 조회, 카테고리 마스터 | Transaction Script + JPA Repository 직결 |
| 흐름 위주 | 메뉴 검색, 매장 목록 | Application Service + 얇은 도메인 객체 |
| 상태 머신/정책 | 주문, 결제, 환불, 프로모션 적용 | 헥사고날 + 도메인 모델 + 포트 분리 |
| 외부 통합 다수 | 결제, 배달 라이더 호출, 매장 POS 연동 | 포트/어댑터 강제, 어댑터 단위 통합 테스트 분리 |

"주문/결제/매장 운영"이 핵심인 외식 커머스라면 그 영역만 헥사고날로 가져가고 사이드 도메인(공지사항, 운영자 화면 일부)은 굳이 깊이 적용하지 않는다. 이 판단을 **Pragmatic Clean Architecture**라고 부르며, 특히 중요한 부분이다.

DDD 전술 패턴 자체에 대한 더 깊은 정리는 별도 문서로 갈 가능성이 높으므로, 이 문서는 "Spring 코드 위에서 어떻게 모듈/패키지를 자르고 트랜잭션을 묶을지"에 집중한다.

## 패키지·모듈 구조 한 가지 안

멀티모듈로 가는 것이 이상적이지만, 단일 모듈에서도 패키지로 동일한 효과를 낼 수 있다. 모놀리식 커머스에서 무난한 출발점은 다음 구조다.

```
com.example.order
├── domain                  // POJO, 프레임워크 의존 0
│   ├── Order.java
│   ├── OrderLine.java
│   ├── OrderStatus.java
│   └── OrderPricingPolicy.java
├── application
│   ├── port.in
│   │   └── PlaceOrderUseCase.java
│   ├── port.out
│   │   ├── OrderRepository.java
│   │   ├── PaymentPort.java
│   │   └── StoreInventoryPort.java
│   └── service
│       └── PlaceOrderService.java   // @Service, @Transactional
└── adapter
    ├── in.web
    │   └── OrderController.java
    └── out
        ├── persistence
        │   ├── OrderJpaEntity.java
        │   ├── OrderJpaRepository.java
        │   └── OrderPersistenceAdapter.java   // implements OrderRepository
        ├── payment
        │   └── TossPaymentAdapter.java        // implements PaymentPort
        └── inventory
            └── StoreInventoryHttpAdapter.java
```

`domain` 패키지에는 Spring/JPA 어노테이션을 넣지 않는다. 이 규칙 하나만 ArchUnit으로 강제해도 효과가 크다.

```java
@Test
void domainShouldNotDependOnSpringOrJpa() {
    noClasses().that().resideInAPackage("..order.domain..")
        .should().dependOnClassesThat()
        .resideInAnyPackage("org.springframework..", "jakarta.persistence..", "..adapter..")
        .check(importedClasses);
}
```

## 나쁜 예: 트랜잭션 스크립트로 뒤엉킨 주문 서비스

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderJpaRepository orderRepo;
    private final MenuJpaRepository menuRepo;
    private final RestTemplate paymentClient;
    private final KafkaTemplate<String, String> kafka;

    @Transactional
    public Long placeOrder(PlaceOrderRequest req) {
        var menus = menuRepo.findAllById(req.menuIds());
        long total = 0;
        for (var m : menus) {
            if (m.getStoreId() != req.storeId()) {
                throw new IllegalArgumentException("매장 불일치");
            }
            if (req.couponCode() != null && m.isCouponApplicable()) {
                total += m.getPrice() * 9 / 10;
            } else {
                total += m.getPrice();
            }
        }

        var pgRes = paymentClient.postForObject(
            "https://pg.example.com/pay",
            Map.of("amount", total, "card", req.cardToken()),
            Map.class);

        if (!"OK".equals(pgRes.get("result"))) {
            throw new IllegalStateException("결제 실패");
        }

        var entity = new OrderJpaEntity(req.storeId(), total, "PAID", LocalDateTime.now());
        orderRepo.save(entity);

        kafka.send("order.created", String.valueOf(entity.getId()));
        return entity.getId();
    }
}
```

이 코드의 문제는 다음과 같다.

- 가격 정책(쿠폰 10% 할인)과 PG 호출, 카프카 발행이 한 메서드 안에 섞여 있다.
- `RestTemplate` 응답 형식이 바뀌면 비즈니스 로직 클래스가 흔들린다.
- 단위 테스트하려면 카프카, PG, JPA를 모두 모킹해야 한다.
- "결제 후 주문 저장 실패" 같은 정합성 시나리오를 검증할 자리가 없다.
- PG가 토스에서 NICE로 바뀌면 같은 클래스를 다시 연다.

## 개선 예: 포트/어댑터 + 도메인 모델

도메인은 정책만 안다.

```java
// domain/Order.java
public class Order {
    private final Long id;
    private final Long storeId;
    private final List<OrderLine> lines;
    private OrderStatus status;
    private Money totalAmount;

    public static Order place(Long storeId, List<OrderLine> lines, CouponPolicy coupon) {
        if (lines.isEmpty()) throw new DomainException("빈 주문");
        Money total = lines.stream()
            .map(line -> coupon.applyTo(line))
            .reduce(Money.ZERO, Money::plus);
        return new Order(null, storeId, lines, OrderStatus.PENDING, total);
    }

    public void markPaid() {
        if (status != OrderStatus.PENDING) throw new DomainException("이미 처리됨");
        this.status = OrderStatus.PAID;
    }
}
```

application 계층은 유스케이스 흐름과 트랜잭션 경계만 책임진다.

```java
// application/service/PlaceOrderService.java
@Service
@RequiredArgsConstructor
public class PlaceOrderService implements PlaceOrderUseCase {

    private final OrderRepository orderRepository;     // port.out
    private final PaymentPort paymentPort;             // port.out
    private final StoreInventoryPort inventoryPort;    // port.out
    private final OrderEventPublisher eventPublisher;  // port.out
    private final CouponPolicyFactory couponFactory;

    @Override
    @Transactional
    public OrderId place(PlaceOrderCommand cmd) {
        inventoryPort.reserve(cmd.storeId(), cmd.lineItems());

        var coupon = couponFactory.of(cmd.couponCode());
        var order  = Order.place(cmd.storeId(), cmd.toLines(), coupon);
        var saved  = orderRepository.save(order);

        var paid = paymentPort.pay(saved.id(), saved.totalAmount(), cmd.cardToken());
        if (!paid.isSuccess()) {
            throw new PaymentFailedException(paid.reason());
        }
        saved.markPaid();
        orderRepository.save(saved);

        eventPublisher.publishCreated(saved);
        return saved.id();
    }
}
```

어댑터는 외부 기술과만 대화한다.

```java
// adapter.out.payment/TossPaymentAdapter.java
@Component
@RequiredArgsConstructor
class TossPaymentAdapter implements PaymentPort {
    private final TossClient tossClient;

    @Override
    public PaymentResult pay(OrderId orderId, Money amount, String cardToken) {
        var res = tossClient.charge(orderId.value(), amount.toLong(), cardToken);
        return res.isApproved()
            ? PaymentResult.success(res.transactionId())
            : PaymentResult.fail(res.reasonCode());
    }
}
```

이 구조의 효과는 다음과 같다.

- 가격 계산은 `Order.place`만 단위 테스트하면 된다. Spring 컨텍스트가 필요 없다.
- PG가 토스에서 NICE로 바뀌어도 `NicePaymentAdapter` 추가, 빈 등록만 바꾼다.
- "결제 후 주문 갱신 실패" 시나리오는 `PlaceOrderService` 통합 테스트에서 어댑터를 가짜 구현으로 바꿔 검증한다.
- 트랜잭션 경계가 application service에 명확히 한 점만 있다.

## 트랜잭션 스크립트 vs 도메인 모델: 언제 무엇을 쓰는가

마틴 파울러의 분류대로, 단순 매장 영업시간 같은 영역에 도메인 모델을 강제하면 오히려 코드가 늘어난다. 다음 신호가 보이면 도메인 모델로 옮긴다.

- 같은 if-else가 3개 이상 서비스 메서드에 반복된다.
- 상태 전이가 4개 이상이고, 잘못된 전이를 막아야 한다(주문, 정산, 환불).
- 가격/할인/적립 등 정책이 자주 바뀐다.
- 동일 데이터에 대해 "검증"과 "변경"이 같이 일어난다.

반대로 다음이면 그대로 둔다.

- 화면 한 개에서만 쓰는 단순 조회/저장.
- 외부 시스템 응답을 그대로 저장만 하는 ETL성 코드.
- 운영자 화면처럼 트래픽이 낮고 정책이 거의 없는 영역.

## 테스트 경계 잡는 법

헥사고날의 가장 큰 보상은 테스트 피라미드를 짤 자리가 생기는 것이다.

| 테스트 종류 | 대상 | 도구 | 비고 |
|-------------|------|------|------|
| 단위 | `Order`, `Money`, `CouponPolicy` | JUnit만 | Spring 없음, 가장 많이 짠다 |
| application | `PlaceOrderService` | JUnit + Fake/Stub 어댑터 | 포트의 fake 구현으로 빠르게 |
| 어댑터 | `OrderPersistenceAdapter`, `TossPaymentAdapter` | `@DataJpaTest`, WireMock | 외부 기술별로 분리 |
| 인수 | HTTP → DB | `@SpringBootTest` + Testcontainers | 핵심 시나리오 소수 |

여기서 자주 빠지는 함정은 application service 테스트에 `@SpringBootTest`를 쓰는 것이다. 그러면 빌드가 느려지고, 테스트가 어댑터의 실수까지 같이 잡으려다 의도가 흐려진다. application 테스트에서는 포트 인터페이스의 in-memory 가짜 구현을 직접 만든다.

```java
class FakeOrderRepository implements OrderRepository {
    private final Map<Long, Order> store = new HashMap<>();
    private final AtomicLong seq = new AtomicLong();
    public Order save(Order order) { /* id 발급 후 저장 */ }
    public Optional<Order> findById(OrderId id) { /* */ }
}
```

## 자주 나오는 잘못된 적용

- **포트가 JPA Repository와 1:1 메서드 매핑**: `findByStoreIdAndStatus` 같은 JPA 시그니처가 그대로 port에 노출되면 도메인이 SQL 모양을 알게 된다. 포트는 도메인 언어로(`findActiveOrdersOf(StoreId)`) 정의한다.
- **도메인이 `@Entity`와 같은 클래스**: 처음에는 편하지만 곧 `@OneToMany` lazy 로딩, dirty checking이 도메인 메서드에 영향을 준다. 도메인 POJO와 JPA 엔티티는 분리하고, 어댑터에서 매핑 책임을 진다(MapStruct 또는 손코딩).
- **모든 곳에 UseCase 인터페이스**: 단일 구현뿐인 인터페이스를 무조건 만들면 오히려 노이즈다. 외부에서 "정책 교체 가능성"이 실제로 있는 포트만 인터페이스로 둔다(in-port는 자주 단일 구현이라 생략 가능).
- **DTO를 도메인 객체 대신 곳곳에 흘림**: Controller가 받은 `Request`가 그대로 application, domain까지 흘러들어가면 외부 표현이 도메인을 오염시킨다. application 입구에서 `Command`로 변환한다.
- **트랜잭션을 어댑터에 거는 경우**: `@Transactional`은 application service에만 둔다. 어댑터에 걸면 여러 어댑터가 호출될 때 트랜잭션 경계가 흐려진다.

## 로컬 실습 환경

다음 조건을 그대로 따라 하면 1\~2시간 안에 헥사고날 미니 커머스를 띄울 수 있다.

- Java 17, Spring Boot 3.x
- MySQL 8 (Docker)
- WireMock(가짜 PG)
- Testcontainers(통합 테스트)

```bash
docker run --name commerce-mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=commerce \
  -p 3306:3306 -d mysql:8.0

docker run --name fake-pg \
  -p 8089:8080 -d wiremock/wiremock:3.5.4
```

`build.gradle.kts` 핵심 의존성.

```kotlin
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    runtimeOnly("com.mysql:mysql-connector-j")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("com.tngtech.archunit:archunit-junit5:1.3.0")
    testImplementation("org.testcontainers:mysql:1.20.1")
    testImplementation("org.wiremock:wiremock-standalone:3.5.4")
}
```

## 실습 과제: 한 시간짜리 미니 주문 서비스

1. `domain.Order`, `OrderLine`, `Money`, `OrderStatus`를 POJO로 작성. `Money`는 BigDecimal + Currency.
2. `PlaceOrderUseCase`(in-port), `OrderRepository`/`PaymentPort`(out-port) 정의.
3. `PlaceOrderService` 구현. `@Transactional` 한 메서드만.
4. JPA 어댑터: `OrderJpaEntity`, `OrderJpaRepository`, `OrderPersistenceAdapter`. 도메인 ↔ 엔티티 매핑은 어댑터 안에서.
5. WireMock으로 PG 모킹: 200 OK + `{"result":"OK"}`. `TossPaymentAdapter`가 이걸 호출.
6. 인수 테스트: 1) 정상 결제, 2) PG 실패 시 주문 PENDING 유지, 3) 빈 주문 시 400.
7. ArchUnit 테스트로 `domain → spring/jpa/adapter` 의존 금지 강제.
8. 가격 정책에 "쿠폰 10%"를 넣고, 그 정책만 단위 테스트로 분리해 본다. Spring을 띄우지 않는다.

이 과제를 끝까지 마쳤다면, 기존 본인 프로젝트(`task/` 기록이 있는 영역) 중 한 군데를 골라 같은 구조로 1주일 안에 리팩터링해 본다. 변경 전후 테스트 수행 시간, 변경된 파일 수를 기록해 두면 구조 개선의 효과를 정량적으로 보여주는 강력한 근거가 된다.

## 설계 의사결정 정리

**Q. 모든 프로젝트에 클린 아키텍처를 적용하는가?**

A. 아니다. 도메인의 복잡도와 외부 통합 수에 따라 다르게 적용한다. CRUD에 가까운 운영자 화면은 트랜잭션 스크립트와 JPA Repository 직결로 충분하고, 주문·결제·정산처럼 상태 머신과 외부 통합이 많은 영역에만 포트/어댑터를 강제한다. 같은 코드베이스 안에서 두 스타일이 공존하는 것이 현실적이다.

**Q. 그렇게 하면 신규 합류자가 헷갈리지 않는가?**

A. 두 가지 장치로 막는다. 첫째, 도메인 패키지 안에서 Spring/JPA 의존성을 ArchUnit으로 막아 어디까지가 "정책"인지 컴파일 타임에 보이게 한다. 둘째, 포트/어댑터를 적용하는 영역의 기준을 README에 적어 둔다. 외부 시스템과 직접 대화하는 영역, 상태 전이가 4개 이상인 영역, 정책이 자주 바뀌는 영역, 이 세 가지 중 두 가지가 겹치면 헥사고날로 간다.

**Q. 도메인 객체와 JPA 엔티티를 분리하면 매핑 코드가 많이 늘지 않는가?**

A. 늘어난다. 다만 매핑 코드가 늘어나는 비용보다, JPA의 lazy 로딩이나 dirty checking이 도메인 메서드 동작을 바꾸는 사고가 더 크다. 매핑은 MapStruct로 거의 자동화 가능하고, 매핑 한 군데가 바뀐다고 해서 다른 도메인 메서드가 깨지지 않는다는 점이 장기적으로 더 큰 가치다. 단순 CRUD 영역에서는 굳이 분리하지 않는다.

**Q. 트랜잭션 경계는 어떻게 잡는가?**

A. application service의 유스케이스 메서드 한 점에만 `@Transactional`을 둔다. 어댑터에는 걸지 않는다. 외부 호출(PG, 메시지 발행)이 트랜잭션 안에 들어가면 commit 시점과 외부 효과 시점이 어긋나 정합성이 깨질 수 있어, 가능하면 외부 호출은 트랜잭션 밖이나 outbox 패턴으로 분리한다.

**Q. 헥사고날을 도입하면서 가장 크게 얻는 것은?**

A. 단위 테스트의 비중이 늘어난다는 점이다. 도메인 단위 테스트가 전체 테스트의 70%를 차지하면 빌드 시간이 줄고, 정책 변경 PR에서 깨지는 테스트가 곧바로 정책 회귀를 가리킨다. 반대로 가장 신경 써야 할 부분은 "어디까지 적용할지"이고, 이걸 팀 합의로 문서화하지 않으면 같은 코드베이스가 두 스타일로 깨져서 더 나빠질 수 있다.

## 체크리스트

- [ ] 도메인 패키지에 Spring/JPA 의존이 없는가 (ArchUnit으로 강제)
- [ ] `@Transactional`은 application service에만 있는가
- [ ] 포트 메서드가 도메인 언어로 정의되었는가 (JPA 시그니처 노출 금지)
- [ ] 도메인 객체와 JPA 엔티티가 핵심 도메인에서 분리되어 있는가
- [ ] application service 테스트가 `@SpringBootTest` 없이 fake 어댑터로 돌아가는가
- [ ] 외부 호출(PG, 메시지)은 트랜잭션 밖이거나 outbox로 분리되어 있는가
- [ ] CRUD 영역에까지 헥사고날을 강제하고 있지 않은가
- [ ] 어댑터별 통합 테스트가 분리되어 있는가 (`@DataJpaTest`, WireMock 등)
- [ ] Controller가 받은 Request를 application 입구에서 Command로 변환하는가
- [ ] 도메인 메서드에 상태 전이 검증이 있고, 잘못된 전이가 예외로 막히는가
