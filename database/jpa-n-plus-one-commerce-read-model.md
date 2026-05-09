# [초안] JPA N+1과 커머스 조회 모델: 주문/메뉴/쿠폰 도메인에서 살아남기

## 왜 이 주제가 중요한가

커머스 백엔드에서 가장 많이 깨지는 지점은 의외로 결제도, 동시성도 아닌 **조회 쿼리**다. 주문 한 건을 화면에 띄우려면 주문 헤더, 주문 라인, 메뉴, 메뉴 옵션, 쿠폰, 매장, 회원 등 5\~7개 테이블이 엮인다. JPA를 쓰는 팀이라면 이 시점에서 거의 반드시 N+1 쿼리 문제를 만난다. 더 나쁜 점은 N+1이 단위 테스트에서는 안 보인다는 것이다. 통합 테스트조차 데이터가 적으면 통과한다. 운영에 올라가서 매장이 100개 늘고 메뉴 옵션이 평균 4개씩 붙는 순간 쿼리 수가 기하급수로 폭발하고, 응답 지연과 커넥션 풀 고갈이 동시에 터진다.

CJ푸드빌 같은 외식 프랜차이즈 도메인은 N+1이 더 잘 터지는 구조다. 매장(브랜드/지점) × 메뉴(베이스 상품) × 옵션(사이즈, 토핑, 사이드) × 쿠폰(적용 가능 여부) 조합이 항상 묶여서 다닌다. "주문 상세 조회 한 번에 200쿼리"가 농담이 아니라 실측치로 잡힌다.

이 문서는 N+1을 단순히 "fetch join 쓰면 된다"로 끝내지 않고, **언제 fetch join을 쓰면 안 되는지**, **언제 read model을 분리해야 하는지**, **언제 JPA를 버리고 MyBatis로 가는지** 까지 시니어 백엔드 관점으로 정리한다. 면접에서 "JPA N+1 어떻게 해결하셨어요?"라는 질문은 실은 "당신이 ORM의 한계를 알고 있느냐"를 묻는 질문이다.

관련 문서가 있다면 다음과 가볍게 연결해서 읽는다.
- 인덱스/실행계획 측면은 별도의 MySQL EXPLAIN/커버링 인덱스 문서 참조
- 트랜잭션 전파/OSIV 관련은 Spring 트랜잭션 문서 참조

## 핵심 개념: N+1은 "지연 로딩 × 컬렉션"의 함수다

### N+1이 생기는 정확한 조건

N+1 쿼리는 다음 세 조건이 동시에 만족될 때 발생한다.

1. 부모 엔티티를 N건 조회한다.
2. 각 부모가 자식 엔티티에 대해 `LAZY` 연관관계를 갖는다.
3. 부모 N건을 순회하면서 자식에 접근한다(서비스 코드, JSON 직렬화, 화면 렌더링 등).

이때 부모 1쿼리 + 자식 N쿼리가 발생해서 총 N+1쿼리가 된다. EAGER로 바꿔도 단지 같은 N+1을 INSERT 시점에 미리 던질 뿐이다. 즉 EAGER는 해결책이 아니다.

### "조회 모델"이라는 별도 사고

JPA를 쓰는 팀이 자주 빠지는 함정은 **쓰기용 도메인 모델 = 조회용 응답 모델**이라고 가정하는 것이다. 도메인 모델은 비즈니스 규칙(주문 상태 전이, 결제 가능 여부, 환불 가능 여부)을 표현하기 위해 풍부한 객체 그래프를 가진다. 그러나 화면용 응답은 평탄한 DTO 한 덩어리만 필요하다. 이 둘을 같은 엔티티로 처리하려고 하면 결국 LAZY를 강제로 깨거나, fetch join을 남발하거나, OSIV로 트랜잭션을 끌고 다니게 된다.

시니어 레벨 답변의 핵심은 이것이다.
> "쓰기 모델은 JPA 엔티티로 두고, 조회 모델은 별도 DTO 또는 별도 쿼리(MyBatis/JdbcTemplate/JPQL DTO projection)로 분리한다."

## 커머스 도메인의 N+1 시나리오

### 시나리오 1: 주문 상세 조회

요구사항: 한 화면에 다음을 모두 보여준다.

- 주문 1건
- 주문 라인 N개
- 라인별 옵션 M개
- 매장 정보
- 적용 쿠폰

엔티티 구조 가정:

```java
@Entity
public class Order {
    @Id Long id;
    @ManyToOne(fetch = LAZY) Store store;
    @ManyToOne(fetch = LAZY) Member member;
    @OneToMany(mappedBy = "order", fetch = LAZY) List<OrderLine> lines;
    @OneToMany(mappedBy = "order", fetch = LAZY) List<AppliedCoupon> coupons;
}

@Entity
public class OrderLine {
    @Id Long id;
    @ManyToOne(fetch = LAZY) Order order;
    @ManyToOne(fetch = LAZY) Menu menu;
    @OneToMany(mappedBy = "line", fetch = LAZY) List<OrderLineOption> options;
}
```

나쁜 코드:

```java
public OrderDetailResponse getOrder(Long orderId) {
    Order order = orderRepository.findById(orderId).orElseThrow();
    return OrderDetailResponse.from(order); // 여기서 모든 LAZY 다 깨짐
}
```

이 코드는 다음과 같이 쿼리가 폭발한다.

- 주문 1쿼리
- store 1쿼리
- member 1쿼리
- lines 1쿼리
- 라인별 menu N쿼리
- 라인별 options N쿼리
- coupons 1쿼리

라인이 5개면 13쿼리, 20개면 43쿼리.

### 시나리오 2: 주문 목록(페이지네이션)

요구사항: 회원의 최근 주문 20건을 카드 리스트로 보여준다. 카드 한 장에는 첫 번째 라인의 메뉴 이미지, 라인 개수, 총 금액, 적용 쿠폰명이 들어간다.

```java
public Page<OrderCardResponse> listOrders(Long memberId, Pageable pageable) {
    Page<Order> orders = orderRepository.findByMemberId(memberId, pageable);
    return orders.map(OrderCardResponse::from); // 카드마다 LAZY 깨짐
}
```

20건을 띄우는데 쿼리가 20 × (lines + menu + coupons) = 60\~80쿼리. 이게 운영에서 가장 흔한 N+1 패턴이다.

### 시나리오 3: 메뉴 옵션 카탈로그

요구사항: 매장별 메뉴 카탈로그 화면. 메뉴 50개, 메뉴별 옵션 그룹 3\~5개, 그룹별 옵션 3\~10개.

이건 N+1+M 구조로 폭이 더 넓다. 부모 50건 조회 후 자식 컬렉션 두 단계가 LAZY로 풀린다.

### 시나리오 4: 쿠폰 적용 가능 여부 일괄 조회

요구사항: 메뉴 카드 100개에 대해 "이 쿠폰을 지금 적용 가능한가"를 함께 표시.

이건 단순 N+1을 넘어, **카르테시안 폭발**까지 같이 검토해야 한다. 쿠폰 정책이 join 대상이 되면 fetch join은 오히려 위험하다.

## 해결 도구별 정확한 사용 시점

### 1) fetch join (JPQL `JOIN FETCH`)

가장 직관적인 해결책. 한 번의 SQL로 부모와 자식을 한꺼번에 가져온다.

```java
@Query("""
    select o from Order o
    join fetch o.store
    join fetch o.lines l
    join fetch l.menu
    where o.id = :id
""")
Optional<Order> findDetailById(@Param("id") Long id);
```

**언제 쓰나**: 단건 상세 조회, 컬렉션 1개까지.

**언제 쓰면 안 되나**:
- 컬렉션을 둘 이상 fetch join 하면 `MultipleBagFetchException`이 터지거나, 카르테시안 곱이 발생한다.
- 페이징과 함께 컬렉션 fetch join 하면 Hibernate가 메모리에서 페이징해버린다(`firstResult/maxResults specified with collection fetch; applying in memory` 경고). 데이터가 많으면 OOM.
- 즉 **목록 + 컬렉션 fetch join은 금지**라고 외워야 한다.

### 2) `@EntityGraph`

JPQL 안 건드리고 fetch 전략만 선언적으로 바꿀 때.

```java
@EntityGraph(attributePaths = {"store", "lines", "lines.menu"})
Optional<Order> findById(Long id);
```

내부 동작은 fetch join과 사실상 같다. 한계도 같다(컬렉션 둘+페이징 금지). 다만 **Spring Data 메서드 시그니처를 그대로 두면서** fetch만 강화할 수 있어서 코드 가독성이 좋아진다.

### 3) `default_batch_fetch_size` (Hibernate batch fetching)

`application.yml`:

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 100
```

부모 N건을 조회한 뒤, LAZY 컬렉션을 처음 접근할 때 Hibernate가 자식 N개를 한 번의 `where parent_id in (?, ?, …)` 쿼리로 묶어서 가져온다. **N+1이 N+1이 아니라 1+1 또는 1+(N/100)** 으로 줄어든다.

**언제 쓰나**:
- 목록 + 컬렉션 둘 이상이 LAZY로 엮여 있을 때
- 페이징을 살려야 할 때

**주의점**:
- batch size를 너무 크게 잡으면 IN 절 파라미터가 비대해져 옵티마이저가 계획을 잘못 세울 수 있다. 대부분의 케이스에서 100\~500 정도가 무난하다.
- batch fetching은 "쿼리 수 감소"이지 "쿼리 비용 감소"는 아니다. 인덱스가 없으면 IN 쿼리 자체가 풀스캔이 된다.

### 4) DTO projection (`new` 연산자, JPQL/QueryDSL projection)

엔티티 그래프가 아니라 **응답 모델 자체를 SQL로 직조**한다.

```java
@Query("""
    select new com.cj.order.dto.OrderCardDto(
        o.id, o.totalPrice, o.createdAt, m.name, m.imageUrl, c.name
    )
    from Order o
    join o.lines l
    join l.menu m
    left join o.coupons ac
    left join ac.coupon c
    where o.member.id = :memberId
""")
Page<OrderCardDto> findCards(@Param("memberId") Long memberId, Pageable pageable);
```

**언제 쓰나**: 목록 화면, 검색 화면, 통계 화면. 즉 "엔티티의 행동이 필요 없는" 모든 조회.

**장점**:
- LAZY/fetch join 고민이 사라진다.
- 페이징과 자유롭게 결합된다.
- 응답에 필요한 컬럼만 select 하므로 I/O가 줄어든다.

**단점**:
- 컬렉션을 그대로 표현하기 어렵다. "주문 1건당 라인 N개"를 DTO 한 줄로 표현 못 하므로, group_concat 같은 트릭을 쓰거나, 헤더 DTO를 먼저 가져온 뒤 라인만 별도 IN 쿼리로 채우는 2단계 전략을 쓴다.

### 5) read model 분리(쓰기 모델과 분리된 조회 전용 쿼리)

규모가 더 커지면 단순 DTO projection을 넘어 **조회 전용 SQL 레이어**를 별도로 두는 게 옳다. JPA를 버리는 게 아니라, 쓰기용 Repository(`OrderRepository extends JpaRepository`)와 조회용 Reader(`OrderQueryDao` — JdbcTemplate, MyBatis, QueryDSL projection 등)를 분리한다.

```java
public interface OrderRepository extends JpaRepository<Order, Long> { /* 쓰기 */ }

public interface OrderQueryDao {
    OrderDetailView findDetail(long orderId);
    Page<OrderCardView> findCards(long memberId, Pageable pageable);
}
```

이 구조의 장점은 분명하다.
- 쓰기 모델은 도메인 규칙에 충실하게 풍부한 객체 그래프를 유지한다.
- 조회 모델은 화면 요구사항이 바뀔 때마다 SQL만 갈아 끼우면 된다.
- 인덱스 튜닝 대상이 명확해진다(조회용 SQL은 죄다 Reader 안에 있음).

CQRS의 가벼운 버전이다. 굳이 명령/조회를 별도 DB로 분리하지 않아도, **레이어를 나누는 것만으로** 면접에서 충분히 강한 답이 나온다.

## 나쁜 코드 vs 개선된 코드

### 나쁜 예: 주문 목록 + 컬렉션 fetch join + 페이징

```java
@Query("""
    select distinct o from Order o
    join fetch o.lines l
    join fetch l.menu
    where o.member.id = :memberId
""")
Page<Order> findAllWithLines(@Param("memberId") Long id, Pageable pageable);
```

문제:
- 컬렉션 fetch join + 페이징 → Hibernate가 메모리 페이징 경고 후 전체 결과 로드
- `distinct`가 SQL distinct이지 의미가 다름. 카르테시안 곱 그대로 받아 Java에서 중복 제거
- 라인이 평균 5개면 행이 5배로 늘어남. 회원이 주문 1만 건이면 5만 행 메모리 적재

### 개선된 예 1: DTO projection + 라인 IN 쿼리 2단계

```java
public Page<OrderCardView> findCards(Long memberId, Pageable pageable) {
    Page<OrderHeaderView> headers = orderQueryDao.findHeaders(memberId, pageable);
    List<Long> orderIds = headers.stream().map(OrderHeaderView::orderId).toList();
    Map<Long, List<OrderLineView>> lineMap =
        orderQueryDao.findLinesByOrderIds(orderIds).stream()
            .collect(groupingBy(OrderLineView::orderId));
    return headers.map(h -> OrderCardView.of(h, lineMap.getOrDefault(h.orderId(), List.of())));
}
```

쿼리 수: 헤더 1쿼리 + 라인 1쿼리 = 2쿼리. 페이징 정확히 동작. 카르테시안 곱 없음.

### 개선된 예 2: 단건 상세는 EntityGraph 그대로

```java
@EntityGraph(attributePaths = {"store", "member", "lines", "lines.menu", "lines.options"})
Optional<Order> findById(Long id);
```

단건이면 컬렉션 fetch join이 안전하다(페이징 없음). 단, 컬렉션 둘 이상이면 한쪽은 batch fetching에 맡긴다.

### 개선된 예 3: 메뉴 카탈로그는 batch size

```yaml
hibernate:
  default_batch_fetch_size: 200
```

```java
List<Menu> menus = menuRepository.findByStoreId(storeId);
menus.forEach(m -> m.getOptionGroups().forEach(g -> g.getOptions().size()));
// 쿼리: 메뉴 1 + 옵션 그룹 1 + 옵션 1 = 3쿼리
```

## OSIV 함정과 처리 원칙

Spring Boot의 기본값은 `spring.jpa.open-in-view=true`다. 이 값은 **요청이 끝날 때까지 영속성 컨텍스트를 살려둔다**. 컨트롤러나 뷰에서 LAZY 접근이 가능해서 편하지만, 다음 부작용이 있다.

- 트랜잭션 경계 밖에서 쿼리가 나간다. DB 커넥션을 요청 전체 시간 동안 점유한다.
- 외부 API 호출 중에도 커넥션을 잡고 있어 커넥션 풀이 빠르게 고갈된다.
- "어디서 쿼리가 나가는지" 추적이 어려워져 N+1을 잡기 더 힘들어진다.

운영 권장 설정:

```yaml
spring:
  jpa:
    open-in-view: false
```

`false`로 두면 트랜잭션 안에서 필요한 데이터를 모두 끌어와야 한다. 이게 강제되면 자연스럽게 fetch 전략과 DTO projection이 들어오게 된다. 즉 OSIV를 끄는 것 자체가 **N+1 예방 장치**다.

면접 답변 포인트:
> "OSIV는 개발 편의를 위한 기본값이지, 운영 권장 값이 아닙니다. 저는 OSIV를 false로 두고, 서비스 계층에서 필요한 LAZY를 명시적으로 초기화하거나 DTO projection으로 처리합니다."

## MyBatis vs JPA 선택 기준

JPA를 쓴다고 모든 쿼리를 JPA로 풀어야 한다는 법은 없다. CJ푸드빌 같은 외식 도메인 관점에서 정리하면 다음과 같다.

| 상황 | 권장 |
|------|------|
| 도메인 규칙이 풍부한 쓰기 (주문 생성, 결제 처리, 상태 전이) | JPA |
| 단건 상세 조회 | JPA + EntityGraph |
| 목록 / 검색 / 카드 리스트 | JPA DTO projection 또는 MyBatis |
| 보고서, 통계, 정산, 외부 추출 | MyBatis 또는 JdbcTemplate |
| 동적 검색 조건이 많고 SQL 가독성이 중요한 경우 | MyBatis |
| 다중 테이블 join + group by + 윈도우 함수 | MyBatis |

핵심은 "조회는 SQL 친화 도구, 쓰기는 객체지향 도구"라는 분업이다. JPA만 고집하다 fetch join을 누더기로 깁는 것보다, 조회 한두 개를 MyBatis로 빼는 게 운영 친화적이다.

## 로컬 실습 환경

### docker compose

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: shopdb
    ports: ["3306:3306"]
    command: --default-authentication-plugin=mysql_native_password
```

### 스키마

```sql
create table store (
  id bigint primary key auto_increment,
  name varchar(100) not null
);

create table menu (
  id bigint primary key auto_increment,
  store_id bigint not null,
  name varchar(100) not null,
  price int not null,
  index idx_menu_store (store_id)
);

create table orders (
  id bigint primary key auto_increment,
  member_id bigint not null,
  store_id bigint not null,
  total_price int not null,
  created_at datetime not null,
  index idx_orders_member_created (member_id, created_at desc)
);

create table order_line (
  id bigint primary key auto_increment,
  order_id bigint not null,
  menu_id bigint not null,
  qty int not null,
  index idx_line_order (order_id)
);

create table order_line_option (
  id bigint primary key auto_increment,
  line_id bigint not null,
  name varchar(100) not null,
  extra_price int not null,
  index idx_option_line (line_id)
);
```

### 시드 데이터

```sql
insert into store(name) values ('역삼점'),('잠실점');
insert into menu(store_id,name,price)
  select 1, concat('메뉴',n), 8000 + n*100 from
  (select 1 as n union all select 2 union all select 3 union all select 4 union all select 5) t;

insert into orders(member_id,store_id,total_price,created_at)
  select 7, 1, 20000, now() - interval n day from
  (select 1 as n union all select 2 union all select 3 union all select 4 union all select 5
   union all select 6 union all select 7 union all select 8 union all select 9 union all select 10) t;
```

### 쿼리 로깅

```yaml
spring:
  jpa:
    properties:
      hibernate:
        format_sql: true
logging:
  level:
    org.hibernate.SQL: debug
    org.hibernate.orm.jdbc.bind: trace
```

`p6spy`를 쓰면 바인딩 값까지 한 줄로 잡힌다. N+1 추적에는 p6spy + `decorator.datasource.p6spy.enable-logging=true` 조합이 가장 강력하다.

## 실행 가능한 예제 모음

### 1) N+1 재현 후 측정

```java
@SpringBootTest
@Transactional
class OrderNPlusOneTest {
    @Autowired OrderRepository orderRepository;

    @Test
    void detect_n_plus_one() {
        Statistics stats = sessionFactory.getStatistics();
        stats.clear();
        List<Order> orders = orderRepository.findByMemberId(7L);
        orders.forEach(o -> o.getLines().forEach(l -> l.getMenu().getName()));
        long count = stats.getPrepareStatementCount();
        System.out.println("queries = " + count);
    }
}
```

목록 10건이면 30+쿼리가 찍힌다. 그다음 `default_batch_fetch_size: 100`을 켜고 재실행해 3쿼리로 떨어지는 것을 확인한다.

### 2) 페이징과 컬렉션 fetch join 동시 사용 시 경고 확인

```java
@Query("select o from Order o join fetch o.lines where o.member.id = :id")
Page<Order> badQuery(@Param("id") Long id, Pageable pageable);
```

실행하면 `HHH000104: firstResult/maxResults specified with collection fetch; applying in memory!` 경고가 뜬다. 이 경고를 무시하지 않는 게 시니어다.

### 3) 2단계 조회로 변환

```java
public Page<OrderCardView> findCards(Long memberId, Pageable pageable) {
    Page<OrderHeaderView> headers = headerDao.find(memberId, pageable);
    if (headers.isEmpty()) return headers.map(h -> OrderCardView.empty(h));

    List<Long> ids = headers.getContent().stream().map(OrderHeaderView::orderId).toList();
    Map<Long, List<OrderLineView>> lines = lineDao.findInOrderIds(ids).stream()
        .collect(groupingBy(OrderLineView::orderId));

    return headers.map(h -> OrderCardView.of(h, lines.getOrDefault(h.orderId(), List.of())));
}
```

### 4) MyBatis로 빼는 예

```xml
<select id="findCards" resultType="OrderCardView">
  select
    o.id            as orderId,
    o.total_price   as totalPrice,
    o.created_at    as createdAt,
    (select group_concat(m.name separator ',')
       from order_line ol join menu m on m.id = ol.menu_id
      where ol.order_id = o.id) as menuNames
  from orders o
  where o.member_id = #{memberId}
  order by o.created_at desc
  limit #{size} offset #{offset}
</select>
```

JPA로 같은 결과를 만들려면 native query에 의존하게 되므로, 이 정도 화면은 MyBatis가 더 정직하다.

## 면접 답변 프레이밍

### Q1. "JPA에서 N+1을 어떻게 해결하셨나요?"

> N+1은 단일 해결책이 아니라 케이스별 도구 선택 문제로 봅니다.
> - 단건 상세는 fetch join이나 EntityGraph로 한 번에 끌어옵니다. 단 컬렉션 둘 이상이면 한쪽은 batch fetching에 맡깁니다.
> - 목록 + 컬렉션은 fetch join을 쓰면 안 됩니다. 페이징이 메모리에서 일어나기 때문입니다. 이 경우 `default_batch_fetch_size`를 설정해 IN 쿼리로 묶거나, DTO projection으로 응답 모델을 직접 만들고 부족한 컬렉션은 별도 IN 쿼리로 한 번 더 가져오는 2단계 전략을 씁니다.
> - 화면이 복잡한 카드 리스트나 통계는 아예 조회 전용 Reader를 두고 MyBatis로 처리합니다. 쓰기 모델과 조회 모델을 분리하는 것이 핵심입니다.

### Q2. "fetch join과 EntityGraph 차이는요?"

> 동작 원리는 같습니다. 둘 다 한 SQL로 join 해서 가져옵니다. 차이는 선언 위치입니다. fetch join은 JPQL에 명시적으로 들어가고, EntityGraph는 메서드 시그니처 위 어노테이션으로 선언합니다. 같은 Repository 메서드에 다양한 fetch 전략을 두고 싶을 때는 EntityGraph가 깔끔하고, 동적 join이 필요하면 QueryDSL fetch join을 씁니다.

### Q3. "OSIV는 어떤 입장인가요?"

> 운영 환경에서는 false가 기본이라고 봅니다. true는 LAZY 접근을 어디서든 허용해서 편하지만, 트랜잭션 밖에서 커넥션을 잡고, 외부 API 호출 중에도 커넥션이 묶여서 풀이 빠르게 고갈됩니다. false로 두면 서비스 계층에서 필요한 데이터를 명시적으로 가져와야 하기 때문에, 자연스럽게 N+1 예방이 됩니다.

### Q4. "JPA만 쓰지 왜 MyBatis도 쓰셨어요?"

> 도메인 규칙이 들어가는 쓰기는 JPA가 강합니다. 상태 전이, 무결성 제약, 도메인 이벤트가 깔끔합니다. 반면 보고서, 통계, 동적 검색, 카드 리스트처럼 SQL 가독성과 join 자유도가 중요한 조회는 MyBatis가 단순합니다. 한 도구로 모든 걸 풀려고 fetch join을 누더기로 깁기보다, 조회 일부를 MyBatis로 분리해 쓰기 모델의 일관성을 지키는 쪽이 운영에 더 좋다고 판단합니다.

### Q5. "주문 목록을 페이징하면서 라인까지 보여줘야 하는데 fetch join을 쓰면 안 된다면 어떻게 하시겠어요?"

> 컬렉션 fetch join + 페이징은 메모리 페이징이 일어나서 위험합니다. 저라면 두 가지 중 하나를 씁니다. 첫째, `default_batch_fetch_size`를 설정해 페이지 안에서 라인을 IN 쿼리로 묶어서 가져오게 합니다. 둘째, 헤더 DTO를 먼저 페이징으로 가져오고 헤더 ID 목록을 모아서 라인을 별도 IN 쿼리로 한 번 더 가져온 뒤, 메모리에서 group by로 합칩니다. 응답 모델이 복잡하면 후자를 선호합니다. 페이징 정확성과 인덱스 활용 모두 명시적으로 보장됩니다.

## 자주 틀리는 패턴

- `@OneToMany`에 `fetch = EAGER`를 박아 두고 N+1을 피했다고 착각하는 경우. 실제로는 모든 조회 시점에 N+1이 강제로 일어난다.
- `distinct`를 SQL distinct로 오해해 카르테시안 곱을 메모리에 그대로 받는 경우.
- `findAll()` 후 `stream().map(toDto)` 안에서 LAZY를 깨는 경우. 트랜잭션 밖이면 `LazyInitializationException`, OSIV 켜져 있으면 N+1.
- 통합 테스트에서 데이터를 적게 넣어 N+1이 안 보이는 경우. 적어도 30\~100건 시드를 쓰고 쿼리 카운트를 assert 한다.
- batch size를 너무 크게 잡아 IN 절이 비대해지고 옵티마이저가 잘못된 plan을 잡는 경우.
- 메뉴/옵션같이 변동이 적은 데이터에 cache를 안 쓰는 경우. N+1을 줄이는 가장 빠른 길이 종종 캐시다.

## 체크리스트

- [ ] 신규 조회 API를 만들 때, 응답 그래프를 먼저 그려보고 fetch 전략을 쿼리 단위로 결정했는가
- [ ] 컬렉션 fetch join은 단건 상세에만 쓰고, 목록에는 쓰지 않았는가
- [ ] 컬렉션이 둘 이상이면 한쪽을 batch fetching에 맡겼는가
- [ ] 목록 화면에서 DTO projection 또는 2단계 조회로 페이징 정확성을 보장했는가
- [ ] `spring.jpa.open-in-view`를 false로 두고 서비스 계층에서 LAZY를 명시적으로 처리했는가
- [ ] 보고서/통계/카드 리스트 등 화면 친화 쿼리를 MyBatis로 분리할 만한 후보를 검토했는가
- [ ] p6spy 또는 Hibernate statistics로 실측 쿼리 수를 측정했는가
- [ ] 통합 테스트에 N+1 회귀 방지를 위해 쿼리 카운트 assertion을 넣었는가
- [ ] 인덱스가 IN 쿼리에 맞게 설계되었는가(`order_id`, `(member_id, created_at desc)` 등)
- [ ] OSIV를 끈 상태에서 외부 API 호출 구간이 트랜잭션 밖에 있는지 확인했는가
