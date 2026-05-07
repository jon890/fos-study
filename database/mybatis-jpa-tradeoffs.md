# [초안] MyBatis와 JPA/Hibernate 트레이드오프 — 레거시 백엔드를 다루는 시니어 관점

## 왜 이 주제가 중요한가

한국 SI/엔터프라이즈 도메인, 특히 외식·유통·리테일 도메인의 백엔드는 여전히 **MyBatis 기반 레거시**가 다수다. 신규 프로젝트는 JPA/Hibernate로 출발하더라도, 실제 운영에서 마주치는 코드의 절반 이상은 XML Mapper, 동적 SQL, 수십 줄짜리 `JOIN` 쿼리로 구성된 MyBatis 코드일 가능성이 높다. CJ푸드빌처럼 디지털 채널(주문, 결제, 멤버십, 매장 운영) 백엔드를 다루는 조직은 운영 안정성과 SQL 가시성이 핵심 가치이고, 이런 환경에서는 ORM의 추상화보다 **명시적 SQL 통제**를 선호하는 경우가 많다.

JPA에 익숙한 지원자가 면접에서 "MyBatis 경험이 부족합니다"로 끝내면 곤란하다. 두 도구의 본질적 트레이드오프, 각자가 잘 해결하는 문제, 그리고 **레거시에서 MyBatis를 만났을 때 어떻게 빠르게 적응할지**까지 답할 수 있어야 한다. 이 문서는 그 답변을 만들기 위한 학습 노트다.

관련 개념 문서가 이미 있는 항목(예: JPA N+1, 트랜잭션 전파, 인덱스 설계 등)은 본문에서 짧게만 다루고 추후 같은 폴더 내 deep-dive 문서로 연결하는 방향으로 구성한다.

## 핵심 개념: 두 도구는 무엇을 자동화하는가

JPA(Hibernate 구현)와 MyBatis는 둘 다 **자바 코드와 RDBMS 사이의 매핑**을 다루지만, 추상화 위치가 다르다.

| 구분 | JPA/Hibernate | MyBatis |
|------|---------------|---------|
| 추상화 대상 | 객체 ↔ 테이블 매핑, SQL 생성, 영속성 컨텍스트 | SQL 결과 ↔ 자바 객체 매핑 |
| SQL 작성 주체 | 프레임워크 (JPQL/Criteria/Spec → SQL) | 개발자 (XML Mapper / @Select) |
| 1차 캐시 | 영속성 컨텍스트로 자동 제공 | 기본적으로 없음 (SqlSession 범위만, 비활성 권장) |
| 변경 감지 | dirty checking 자동 | 직접 UPDATE 작성 |
| 학습 곡선 | 가파름 (영속성 컨텍스트, 프록시, 플러시 타이밍) | 완만함 (SQL을 알면 됨) |
| SQL 가시성 | 낮음 (생성된 SQL을 로그로 확인) | 높음 (작성한 SQL이 그대로 실행) |

핵심은 **JPA는 SQL을 생성해주는 도구**고, **MyBatis는 SQL을 매핑해주는 도구**라는 점이다. JPA는 객체 모델을 1차 시민으로 두고, MyBatis는 SQL을 1차 시민으로 둔다.

### MyBatis가 잘 풀어주는 문제

1. **복잡한 통계/리포팅 쿼리**: 윈도우 함수, 다중 `JOIN`, 서브쿼리, `GROUP BY ROLLUP` 같은 쿼리는 JPQL/Criteria로 짜면 가독성이 급락한다. MyBatis는 그냥 SQL을 그대로 쓰면 된다.
2. **레거시 스키마**: 정규화가 덜 되었거나 자연키, 복합키, 비표준 명명이 섞인 스키마. JPA 매핑이 부담스러운 경우.
3. **DBA가 SQL을 검수하는 조직**: SQL이 XML에 그대로 보이므로 리뷰·튜닝이 직관적이다.
4. **벤더 종속 SQL 활용**: MySQL의 `ON DUPLICATE KEY UPDATE`, Oracle의 `MERGE INTO`, 힌트 등을 자유롭게 쓴다.

### JPA가 잘 풀어주는 문제

1. **도메인 모델 중심 설계**: 애그리거트, 연관관계, 값 객체를 코드로 표현.
2. **CRUD 반복 작성 제거**: 단순 조회/저장/수정 코드의 90%를 줄여준다.
3. **변경 감지와 트랜잭션 일관성**: dirty checking과 영속성 컨텍스트가 하나의 트랜잭션 안에서 객체-DB 일관성을 보장.
4. **벤더 독립성**: Dialect 교체로 DB 이식 가능(현실에서는 거의 안 일어나지만).

## XML Mapper와 resultMap — 실전 패턴

MyBatis 코드의 중심은 `*Mapper.xml`이다. 인터페이스 메서드와 XML의 `id`가 매핑되고, 결과는 `resultType` 또는 `resultMap`으로 객체에 매핑된다.

```xml
<!-- OrderMapper.xml -->
<mapper namespace="com.example.order.OrderMapper">

  <resultMap id="OrderWithItems" type="com.example.order.Order">
    <id     property="orderId"     column="order_id"/>
    <result property="orderNo"     column="order_no"/>
    <result property="orderedAt"   column="ordered_at"/>
    <result property="totalAmount" column="total_amount"/>
    <association property="customer" javaType="com.example.order.Customer">
      <id     property="customerId" column="customer_id"/>
      <result property="name"       column="customer_name"/>
    </association>
    <collection property="items" ofType="com.example.order.OrderItem">
      <id     property="itemId"   column="item_id"/>
      <result property="menuName" column="menu_name"/>
      <result property="quantity" column="quantity"/>
      <result property="price"    column="price"/>
    </collection>
  </resultMap>

  <select id="findOrderWithItems" resultMap="OrderWithItems">
    SELECT
      o.order_id, o.order_no, o.ordered_at, o.total_amount,
      c.customer_id, c.name AS customer_name,
      i.item_id, i.menu_name, i.quantity, i.price
    FROM orders o
    JOIN customers c   ON c.customer_id = o.customer_id
    LEFT JOIN order_items i ON i.order_id  = o.order_id
    WHERE o.order_id = #{orderId}
  </select>
</mapper>
```

여기서 봐야 할 포인트:
- `resultMap`은 **하나의 SQL 결과 행을 객체 그래프로 조립**한다. JPA의 `@OneToMany fetch=JOIN`과 비슷한 결과를 얻지만, **자동화가 없다**. 매핑이 곧 명세다.
- `<collection>`이 들어가면 N개의 행이 1개의 부모 객체로 접히면서 자식 컬렉션으로 펼쳐진다. 즉 `ROW → OBJECT GRAPH` 변환을 개발자가 통제한다.
- `#{...}`는 **PreparedStatement 바인딩**, `${...}`는 **문자열 치환**이다. `${}`는 SQL Injection 위험이 있어 ORDER BY 컬럼 같은 식별자에 한정적으로만 사용한다.

### 동적 SQL — 검색 조건 빌더의 본체

MyBatis의 진짜 무기는 동적 SQL이다.

```xml
<select id="searchOrders" resultMap="OrderWithItems">
  SELECT o.*, c.name AS customer_name
  FROM orders o
  JOIN customers c ON c.customer_id = o.customer_id
  <where>
    <if test="storeId != null">
      AND o.store_id = #{storeId}
    </if>
    <if test="status != null and status != ''">
      AND o.status = #{status}
    </if>
    <if test="startDate != null and endDate != null">
      AND o.ordered_at BETWEEN #{startDate} AND #{endDate}
    </if>
    <if test="keyword != null and keyword != ''">
      AND (o.order_no LIKE CONCAT('%', #{keyword}, '%')
           OR c.name LIKE CONCAT('%', #{keyword}, '%'))
    </if>
  </where>
  ORDER BY o.ordered_at DESC
  LIMIT #{offset}, #{size}
</select>
```

`<where>`는 첫 `AND`/`OR`을 자동으로 떼주고, 모든 조건이 falsy면 `WHERE` 자체를 생략한다. `<foreach>`는 `IN (...)` 절에 자주 쓴다.

```xml
<select id="findByMenuIds" resultMap="MenuMap">
  SELECT * FROM menus
  WHERE menu_id IN
  <foreach collection="ids" item="id" open="(" close=")" separator=",">
    #{id}
  </foreach>
</select>
```

JPA 진영에서 동일한 동적 검색을 하려면 Querydsl이나 Spring Data JPA Specification이 필요한데, 가독성은 사람마다 호불호가 갈린다. MyBatis의 동적 SQL은 결국 **출력되는 SQL 모양이 그대로 보인다**는 게 강점이다.

## 페이징 — `LIMIT/OFFSET`을 직접 다루는 책임

MyBatis는 페이징을 자동으로 해주지 않는다. 일반적으로 두 가지 패턴 중 하나다.

1. `LIMIT`/`OFFSET` 직접 작성 + `COUNT(*)` 별도 쿼리
2. PageHelper, MyBatis-PageHelper 같은 인터셉터 라이브러리 사용

```xml
<select id="countSearchOrders" resultType="long">
  SELECT COUNT(*) FROM orders o
  <where>
    <!-- 검색 조건과 동일하게 유지 -->
  </where>
</select>
```

조심할 부분:
- 검색 쿼리와 카운트 쿼리의 `WHERE` 조건이 어긋나면 페이지 수와 결과가 불일치한다. 동적 SQL을 `<sql>` + `<include>`로 추출해 공유하는 게 안전하다.
- 깊은 페이징(`OFFSET 100000`)은 MySQL에서 성능이 급락한다. **Keyset 페이징**(`WHERE id < :lastId ORDER BY id DESC LIMIT 20`)으로 전환할 수 있는지 확인한다. JPA에서도 동일한 함정이 있고, 이건 MyBatis/JPA 문제가 아니라 SQL 설계 문제다.

## N+1 — MyBatis에서도 똑같이 일어난다

JPA의 N+1만 유명하지, MyBatis도 부주의하면 같은 문제를 만든다.

```xml
<!-- 부모 조회 -->
<select id="findOrders" resultType="Order">
  SELECT * FROM orders WHERE store_id = #{storeId}
</select>

<!-- 각 주문의 아이템을 별도 조회 -->
<select id="findItemsByOrderId" resultType="OrderItem">
  SELECT * FROM order_items WHERE order_id = #{orderId}
</select>
```

서비스 레이어에서 주문 100건을 받고 각 주문마다 `findItemsByOrderId`를 호출하면 101번 쿼리가 나간다. 해결 방법:

1. **JOIN으로 한 번에 조회** + `<collection>` 매핑 (앞의 `OrderWithItems` 예시 참고).
2. **2-쿼리 in-clause 패턴**: 주문 ID 리스트를 모아 한 번의 `IN (...)`으로 자식 조회 후, 자바에서 그룹핑.
3. MyBatis의 `<collection select="...">` 지연 로딩 — 가능하지만 SQL 가시성이 떨어져 운영 환경에선 호불호가 갈린다.

JPA 경험자라면 "fetch join, @EntityGraph, BatchSize"의 사고방식을 그대로 들고 와서 MyBatis에서도 적용하면 된다. 도구만 다르지 문제와 해법의 본질은 같다.

## 복잡한 조회 — MyBatis가 빛나는 영역

매장별 일일 매출 요약, 멤버십 등급별 객단가, 메뉴별 시간대 판매량 같은 리포팅 쿼리는 JPA/Querydsl보다 MyBatis가 훨씬 유리하다.

```xml
<select id="dailyStoreSalesSummary" resultType="DailySales">
  SELECT
    o.store_id,
    DATE(o.ordered_at)                          AS sales_date,
    COUNT(*)                                    AS order_count,
    SUM(o.total_amount)                         AS total_sales,
    AVG(o.total_amount)                         AS avg_ticket,
    SUM(CASE WHEN o.channel = 'APP'   THEN o.total_amount ELSE 0 END) AS app_sales,
    SUM(CASE WHEN o.channel = 'KIOSK' THEN o.total_amount ELSE 0 END) AS kiosk_sales
  FROM orders o
  WHERE o.ordered_at &gt;= #{startDate}
    AND o.ordered_at &lt;  #{endDate}
    AND o.status = 'COMPLETED'
  GROUP BY o.store_id, DATE(o.ordered_at)
  ORDER BY sales_date DESC, total_sales DESC
</select>
```

이런 쿼리를 JPQL로 옮기는 데 시간 쓰지 않고, **DBA에게 그대로 보여주고 튜닝 받을 수 있다**는 게 MyBatis의 강점이다. 인덱스 추가, 파티셔닝 검토, 실행계획 분석이 SQL 텍스트 위에서 곧바로 이뤄진다.

## 트랜잭션 — 둘 다 Spring `@Transactional`을 쓴다

MyBatis는 자체 트랜잭션 매니저를 갖고 있지만, Spring 환경에서는 `DataSourceTransactionManager`(JPA가 함께면 `JpaTransactionManager`)가 동일한 커넥션 위에서 MyBatis SqlSession도 관리한다. 즉 **트랜잭션 전파, 격리 수준, 롤백 규칙은 JPA에서 쓰던 그대로**다.

다만 차이점:
- **dirty checking 없음**: 객체를 수정해도 자동으로 UPDATE가 안 나간다. 직접 `update` 호출이 필요하다. 이걸 잊으면 "테스트는 통과하는데 운영에선 변경이 안 됨" 류의 버그가 난다.
- **flush 타이밍 문제 없음**: JPA는 `flush()` 시점에 따라 같은 트랜잭션 내 select가 변경 결과를 못 볼 수 있는데, MyBatis는 즉시 SQL이 나가므로 이 혼란이 적다.
- **JPA + MyBatis 혼용** 프로젝트에서는 JPA 영속성 컨텍스트가 알지 못하는 변경을 MyBatis가 만들어내므로, 같은 트랜잭션 안에서 JPA 조회 결과가 stale일 수 있다. 필요한 경우 `EntityManager.clear()` / `refresh()`로 동기화한다.

## 캐시 — 신중하게 끈다

MyBatis는 1차 캐시(SqlSession scope)와 2차 캐시(`<cache>`)를 제공하지만, 운영에서 2차 캐시를 그대로 켜는 경우는 드물다. 이유는 단순하다.

- 다중 인스턴스 환경에서 인스턴스별 로컬 캐시는 일관성 깨짐의 주범이다.
- DB 직접 변경(다른 배치, 다른 시스템)을 인지하지 못한다.
- TTL/무효화 규칙을 매퍼 단위로 관리하면 추적이 어렵다.

현실에서는 **MyBatis 캐시를 끄고**, 캐시가 필요한 영역은 **Redis 등 외부 캐시 + 명시적 무효화 정책**으로 관리한다. JPA의 2차 캐시도 같은 이유로 운영에서 거의 쓰지 않는다. 이 판단은 도구가 아니라 운영 모델의 문제다.

## Bad vs Improved

### Bad: SQL Injection과 동적 ORDER BY 혼용

```xml
<select id="searchBad" resultType="Menu">
  SELECT * FROM menus
  WHERE name LIKE '%${keyword}%'
  ORDER BY ${sortColumn} ${sortDir}
</select>
```

`${keyword}`는 그대로 SQL 텍스트에 박혀 들어가 인젝션이 가능하다. `${sortColumn}`은 식별자라 바인딩이 불가능한 영역이지만, 화이트리스트 검증 없이 넘기는 건 위험하다.

### Improved

```xml
<select id="searchGood" resultType="Menu">
  SELECT * FROM menus
  WHERE name LIKE CONCAT('%', #{keyword}, '%')
  ORDER BY
  <choose>
    <when test="sortColumn == 'PRICE'">price</when>
    <when test="sortColumn == 'NAME'">name</when>
    <otherwise>menu_id</otherwise>
  </choose>
  <if test="sortDir == 'DESC'">DESC</if>
</select>
```

자바 코드에서도 `sortColumn`과 `sortDir`을 enum으로 받아 검증하면 더 안전하다.

### Bad: N+1을 유발하는 서비스 코드

```java
List<Order> orders = orderMapper.findOrdersByStore(storeId);
for (Order o : orders) {
    o.setItems(orderMapper.findItemsByOrderId(o.getOrderId())); // N+1
}
```

### Improved

```java
List<Order> orders = orderMapper.findOrdersWithItemsByStore(storeId); // resultMap collection으로 한 번에
```

또는 ID 리스트를 모아 `IN (...)`으로 한 번에 조회 후, 자바에서 `Collectors.groupingBy(OrderItem::getOrderId)`로 묶는다.

## 로컬 실습 환경 (MySQL 8 + Spring Boot + MyBatis)

```yaml
# docker-compose.yml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: shopdb
    ports: ["3306:3306"]
    command: --default-authentication-plugin=mysql_native_password
```

```sql
-- schema.sql (MySQL 8)
CREATE TABLE customers (
  customer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name        VARCHAR(64) NOT NULL
);

CREATE TABLE orders (
  order_id     BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no     VARCHAR(32) NOT NULL UNIQUE,
  customer_id  BIGINT NOT NULL,
  store_id     BIGINT NOT NULL,
  status       VARCHAR(16) NOT NULL,
  channel      VARCHAR(16) NOT NULL,
  total_amount DECIMAL(12,2) NOT NULL,
  ordered_at   DATETIME NOT NULL,
  KEY idx_orders_store_ordered (store_id, ordered_at),
  KEY idx_orders_customer (customer_id)
);

CREATE TABLE order_items (
  item_id   BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_id  BIGINT NOT NULL,
  menu_name VARCHAR(64) NOT NULL,
  quantity  INT NOT NULL,
  price     DECIMAL(10,2) NOT NULL,
  KEY idx_items_order (order_id)
);
```

```gradle
dependencies {
  implementation 'org.springframework.boot:spring-boot-starter-jdbc'
  implementation 'org.mybatis.spring.boot:mybatis-spring-boot-starter:3.0.3'
  runtimeOnly    'com.mysql:mysql-connector-j'
}
```

```yaml
# application.yml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/shopdb?useSSL=false&serverTimezone=Asia/Seoul
    username: root
    password: root

mybatis:
  mapper-locations: classpath:mapper/**/*.xml
  configuration:
    map-underscore-to-camel-case: true
    default-statement-timeout: 5
```

`map-underscore-to-camel-case: true`는 `customer_id` → `customerId` 자동 매핑을 해줘 `resultMap` 작성량을 줄여준다.

## 실행 가능한 예제 시나리오

1. 위 스키마로 컨테이너 띄우고 테이블 생성.
2. 더미 데이터 1만 건 삽입(`INSERT ... SELECT` 자기복제로 빠르게 늘릴 수 있다).
3. `searchOrders` 동적 검색 호출 — 조건 조합별로 출력되는 SQL을 `logging.level.org.mybatis: DEBUG`로 확인.
4. `findItemsByOrderId`를 N번 호출하는 코드와 `findOrderWithItems` 한 번 호출하는 코드를 비교하고, MySQL의 `EXPLAIN`으로 실행계획 차이를 본다. 인덱스 사용/스캔 행 수가 어떻게 변하는지 기록.
5. `dailyStoreSalesSummary`를 30일 범위로 돌려보고, `idx_orders_store_ordered` 유무에 따른 응답시간 차이 측정. 인덱스 설계 deep-dive 문서가 있다면 그쪽으로 링크.
6. `@Transactional` 메서드 안에서 `update` 호출 후 예외 발생시켜 롤백 확인.
7. 같은 트랜잭션에서 MyBatis `update`로 변경한 행을 JPA `EntityManager`로 조회했을 때 stale 데이터가 보이는지 검증(혼용 시 함정).

## 면접 답변 프레이밍

면접관이 묻는 질문은 대체로 세 갈래다.

### Q1. "MyBatis 경험이 있나요?"

JPA 중심으로 일해온 지원자라면 정직하게 답하되, **트레이드오프 이해**와 **레거시 적응 능력**을 보여주는 답변이 좋다.

> "주력은 JPA/Hibernate였지만, MyBatis 코드를 읽고 수정한 경험은 있습니다. 두 도구는 추상화 위치가 달라서, MyBatis는 SQL을 1차 시민으로 두고 결과 매핑을 도와주고 JPA는 객체 모델을 1차 시민으로 두고 SQL을 생성합니다. 그래서 복잡한 통계 쿼리, 레거시 스키마, DBA 검수 프로세스가 강한 환경에서는 MyBatis가 명확히 유리하다고 생각합니다. 입사 후 MyBatis 비중이 높은 모듈을 맡게 되면, XML Mapper 구조와 동적 SQL, resultMap 매핑부터 빠르게 익히고, JPA에서 다뤘던 N+1·페이징·트랜잭션 같은 문제는 도구가 다를 뿐 본질이 같으니 그대로 적용할 수 있을 것 같습니다."

### Q2. "MyBatis와 JPA 중 어떤 걸 선호하나요?"

선호를 묻는 게 아니라 **판단 기준**을 묻는 질문이다.

> "도메인 모델이 풍부하고 CRUD 비중이 높은 서비스에는 JPA가 생산성 측면에서 유리하고, 통계·리포팅·복잡한 조회가 많은 시스템이나 SQL 가시성이 운영상 중요한 환경에서는 MyBatis가 더 맞다고 봅니다. 한 시스템 안에서도 핵심 도메인은 JPA, 통계/배치는 MyBatis로 혼용하는 패턴이 현실적이라고 생각합니다."

### Q3. "MyBatis에서 N+1을 어떻게 해결하나요?"

> "MyBatis도 부모-자식 조회를 분리해서 호출하면 N+1이 그대로 발생합니다. 보통 세 가지 중 하나로 해결합니다. 첫째, JOIN 한 번에 조회한 뒤 resultMap의 collection 매핑으로 객체 그래프를 조립하는 방식. 둘째, 부모 ID 리스트를 모아 자식을 IN 절로 한 번에 조회한 뒤 자바에서 그룹핑하는 방식. 셋째, 지연 로딩을 켜는 방식인데 운영 SQL 가시성이 떨어져서 저는 앞의 두 가지를 선호합니다."

## 체크리스트

- [ ] resultMap의 `<association>`/`<collection>` 매핑 의미를 SQL 결과 행 흐름으로 설명할 수 있다.
- [ ] `#{}`와 `${}`의 차이, SQL Injection 위험 영역을 안다.
- [ ] `<where>`, `<if>`, `<choose>`, `<foreach>`의 출력 SQL을 머릿속으로 그릴 수 있다.
- [ ] 페이징 시 검색 쿼리와 카운트 쿼리의 조건 동기화 문제를 안다.
- [ ] 깊은 페이징의 성능 문제와 keyset 페이징을 설명할 수 있다.
- [ ] MyBatis에서 N+1을 만드는 패턴과 세 가지 해결법을 안다.
- [ ] MyBatis 2차 캐시를 운영에서 끄는 이유를 설명할 수 있다.
- [ ] Spring `@Transactional` 하에서 MyBatis와 JPA가 같은 트랜잭션 매니저를 공유하는 경우의 동작을 안다.
- [ ] JPA + MyBatis 혼용 시 영속성 컨텍스트 stale 문제를 안다.
- [ ] 통계/리포팅 쿼리는 MyBatis가 유리한 이유를 SQL 가시성·DBA 협업 관점에서 설명할 수 있다.
- [ ] 면접에서 "MyBatis 경험 부족"을 트레이드오프 이해와 적응 전략으로 보완해 답변할 수 있다.
