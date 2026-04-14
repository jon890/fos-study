# [초안] MySQL EXPLAIN 실행 계획 읽기

> 이 문서는 career-os에서 생성한 학습용 초안입니다. 이후 보강될 수 있습니다.

## 왜 중요한가

쿼리가 느리다는 것을 안다고 해서 어디가 느린지 알 수는 없다. `EXPLAIN`은 MySQL 옵티마이저가 실제로 어떤 경로로 쿼리를 실행하기로 결정했는지 보여주는 유일한 창구다.

실무에서 EXPLAIN을 꺼내는 상황:
- 슬로우 쿼리 로그에 찍힌 SQL 분석
- JPA가 생성한 SQL이 기대와 다른 실행 계획을 탈 때
- 배포 전 인덱스 효과 사전 검증
- 대용량 조회 API 응답 지연 원인 추적
- 신규 인덱스 추가 또는 변경 후 적용 확인

인덱스가 있어도 옵티마이저가 선택하지 않을 수 있고, 타더라도 효율이 나쁜 방식일 수 있다. EXPLAIN을 읽는 능력이 없으면 인덱스를 추가해도 결과가 바뀐 이유를 설명할 수 없다.

---

## EXPLAIN 빠르게 읽는 법

```sql
EXPLAIN SELECT o.id, o.status, m.name
FROM orders o
JOIN member m ON o.member_id = m.id
WHERE o.status = 'PENDING'
  AND o.created_at >= '2026-01-01';
```

결과는 행 단위로 출력된다. **아래 행이 먼저 실행된 것이 아니다.** `id` 값이 같으면 위에서 아래 순서로 읽고, `id` 값이 크면 먼저 실행된 서브쿼리다. 조인은 보통 동일한 `id`로 두 행이 나온다.

읽는 순서:
1. `type` — 풀스캔인지 인덱스를 타는지 가장 먼저 확인
2. `key` — 실제로 선택된 인덱스 이름 확인 (`NULL`이면 즉시 경보)
3. `rows` — 예상 처리 행 수가 비정상적으로 크면 인덱스 문제
4. `Extra` — `Using filesort`, `Using temporary`가 있으면 검토 신호
5. `filtered` — `rows × filtered%`로 실제 다음 단계 행 수 추정

---

## 핵심 해석표

### type — 접근 방식 (가장 중요)

| type | 의미 | 판단 | 언제 나타나는가 |
|------|------|------|-----------------|
| `system` | 테이블에 1건만 존재 | 최상 | 상수 서브쿼리 |
| `const` | PK/Unique로 1건 조회 | 최상 | `WHERE id = 1` |
| `eq_ref` | 조인 시 PK/Unique로 정확히 1건 | 매우 좋음 | `JOIN ON pk_col` |
| `ref` | 비유니크 인덱스로 동등 비교 | 좋음 | `WHERE status = 'PENDING'` |
| `range` | 인덱스 범위 스캔 | 보통 | `BETWEEN`, `>`, `<`, `IN` |
| `index` | 인덱스 전체 풀스캔 | 아쉬움 | 커버링 인덱스만 가능한 경우 |
| `ALL` | 테이블 풀스캔 | 위험 신호 | 인덱스 없음 또는 옵티마이저 포기 |

실무 기준: `ref` 이상이면 허용, `range`는 `rows`가 크면 검토 필요, `ALL`은 즉시 조치.

### rows — 예상 처리 행 수

옵티마이저가 통계 정보를 기반으로 추정한 값이다. **실제 처리 건수가 아니다.** 통계가 오래됐거나 데이터 분포가 불균등하면 실제와 크게 다를 수 있다. `rows × (filtered / 100)`이 실제로 다음 단계로 넘어가는 행 수 추정값이다.

### filtered — 인덱스 이후 필터링 비율

`rows = 10000`, `filtered = 10`이면 인덱스로 10000건을 읽고 1000건만 통과한다는 뜻이다. filtered가 낮을수록 인덱스 선택이 비효율적이거나 WHERE 조건이 인덱스를 못 타고 있다는 신호다.

### Extra — 추가 실행 정보

| Extra 값 | 의미 | 대응 방향 |
|----------|------|-----------|
| `Using index` | 커버링 인덱스 — 테이블 액세스 없음 | 좋음, 유지 |
| `Using where` | 인덱스 이후 WHERE 필터 추가 적용 | 무조건 나쁜 건 아님, filtered 같이 확인 |
| `Using filesort` | 정렬을 인덱스 없이 메모리/디스크에서 수행 | 정렬 컬럼 인덱스 포함 검토 |
| `Using temporary` | 임시 테이블 생성 (GROUP BY, DISTINCT 등) | 인덱스 설계 재검토 |
| `Using index condition` | ICP(Index Condition Pushdown) 적용 | 일반적으로 좋음 |
| `Using join buffer` | 인덱스 없는 조인에서 버퍼 사용 | 조인 컬럼 인덱스 추가 |
| `Impossible WHERE` | 항상 거짓인 조건 | 쿼리 로직 오류 |

`Using filesort`와 `Using temporary`가 동시에 나오면 GROUP BY + ORDER BY 구조에서 인덱스를 전혀 활용하지 못하는 상태다. 대용량 테이블에서 이 조합은 즉각 조치가 필요하다.

### possible_keys vs key

`possible_keys`는 후보 인덱스 목록, `key`는 옵티마이저가 최종 선택한 인덱스다. `key`가 NULL이면 인덱스가 있어도 풀스캔을 선택한 것이다. 이 경우 통계 갱신(`ANALYZE TABLE`) 또는 데이터 분포 확인이 먼저다.

### key_len — 인덱스 사용 길이

복합 인덱스에서 실제로 몇 바이트까지 사용했는지 알 수 있다. `(status, created_at)` 복합 인덱스에서 `status`만 사용하면 `key_len`이 status 컬럼 크기에 해당하는 값만 나온다. 복합 인덱스가 예상보다 짧게 사용되고 있다면 쿼리 조건과 인덱스 컬럼 순서를 다시 맞춰야 한다.

---

## EXPLAIN ANALYZE 보는 법

`EXPLAIN ANALYZE`는 MySQL 8.0.18+에서 사용 가능하다. 일반 EXPLAIN이 옵티마이저의 추정이라면, EXPLAIN ANALYZE는 실제 쿼리를 실행하고 예상값 대비 실제 실행 결과를 트리 형태로 보여준다.

```sql
EXPLAIN ANALYZE
SELECT o.id, o.status, oi.product_id, oi.quantity
FROM orders o
JOIN order_item oi ON o.id = oi.order_id
WHERE o.member_id = 10001
  AND o.status = 'PENDING';
```

출력 예시:
```
-> Nested loop inner join  (cost=42.5 rows=18) (actual time=0.312..5.821 rows=24 loops=1)
    -> Index lookup on o using idx_orders_member_status (member_id=10001, status='PENDING')
         (cost=5.1 rows=6) (actual time=0.201..0.318 rows=6 loops=1)
    -> Index lookup on oi using idx_order_item_order (order_id=o.id)
         (cost=3.8 rows=3) (actual time=0.089..0.652 rows=4 loops=6)
```

**읽는 포인트:**

| 항목 | 의미 |
|------|------|
| `cost=N rows=M` | 옵티마이저 예측값 |
| `actual time=A..B rows=R loops=L` | 실제 실행값. A=첫 행까지(ms), B=전체 완료까지(ms) |
| rows 예측 vs 실제 편차 | 크면 통계 오래됨 → `ANALYZE TABLE` 고려 |
| `loops` | 해당 단계가 몇 번 실행됐는지 (중첩 루프 깊이 파악) |

**병목 찾는 법:**
- `actual time`이 가장 높은 노드를 찾는다. 그 노드가 병목이다.
- rows 예측과 실제가 10배 이상 차이 나면 통계 문제다. `ANALYZE TABLE orders;`로 갱신 후 재확인한다.
- `loops`가 큰데 안쪽 노드의 `actual time`이 크면 N+1과 동일한 구조가 SQL 레벨에서 일어나고 있는 것이다.

> **주의**: `EXPLAIN ANALYZE`는 실제 쿼리를 실행한다. 무거운 쿼리를 프로덕션 DB에서 직접 실행하지 않도록 주의한다. 재현 환경에서 테스트하는 것이 원칙이다.

---

## 실무/면접 연결

### 슬로우 쿼리 → EXPLAIN 워크플로우

```
슬로우 쿼리 로그 / Performance Insights / APM에서 문제 SQL 추출
    ↓
EXPLAIN으로 옵티마이저 선택 확인
    ↓
type=ALL 또는 Using filesort/temporary 발견
    ↓
인덱스 설계 수정 또는 쿼리 재작성
    ↓
EXPLAIN ANALYZE로 실제 실행 시간 전후 비교
    ↓
배포 후 슬로우 쿼리 재확인
```

### 옵티마이저가 인덱스를 포기하는 경우

옵티마이저는 테이블 전체 행 대비 추출 비율(선택도)이 높으면 풀스캔을 선택한다. 예를 들어 `status` 컬럼이 `PENDING`, `COMPLETED` 두 값뿐이고 99%가 `COMPLETED`인 상태에서 `WHERE status = 'COMPLETED'`를 쿼리하면 인덱스를 타도 이득이 없어 풀스캔을 선택할 수 있다.

이 경우 `FORCE INDEX`로 억지로 인덱스를 강제하는 것보다 PK 범위 조건과 조합하거나 더 선택도 높은 복합 인덱스로 설계를 바꾸는 것이 올바른 접근이다. 인덱스를 강제해도 랜덤 I/O가 순차 풀스캔보다 느릴 수 있기 때문이다.

---

## JPA N+1 예제와 실행 계획 비교

### 문제 상황

```java
// OrderRepository.java
List<Order> findByMemberId(Long memberId);

// OrderService.java
@Transactional(readOnly = true)
public List<OrderDto> getOrders(Long memberId) {
    List<Order> orders = orderRepository.findByMemberId(memberId);
    return orders.stream()
        .map(o -> new OrderDto(o, o.getItems()))  // LAZY 로딩 — 각 반복에서 SELECT 발생
        .toList();
}
```

이 코드가 만들어내는 SQL:
```sql
-- 1번: 주문 목록 조회
SELECT * FROM orders WHERE member_id = 10001;
-- 결과: 20건

-- 20번: 각 주문의 order_item 개별 조회
SELECT * FROM order_item WHERE order_id = ?;  -- 20번 반복
```

N+1이란 이름은 "1번의 메인 조회 + N번의 추가 조회"에서 왔다. 주문이 1000건이면 1001번의 쿼리가 발생한다.

### EXPLAIN만 보면 문제가 안 보인다

```sql
-- N+1이 발생하는 단건 조회의 실행 계획
EXPLAIN SELECT * FROM order_item WHERE order_id = 1;
```

```
id  select_type  table       type  key                    rows  Extra
1   SIMPLE       order_item  ref   idx_order_item_order   4     NULL
```

단건으로 보면 `ref`로 인덱스를 잘 타고 있다. 문제는 이것이 루프로 반복된다는 것이다. **EXPLAIN 한 번으로는 N+1을 잡을 수 없다.** Hibernate SQL 로그 또는 p6spy 같은 도구로 전체 쿼리 횟수를 먼저 파악해야 한다.

```yaml
# application.yml — 개발 환경에서 쿼리 수 파악
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
logging:
  level:
    org.hibernate.stat: DEBUG
```

### 해결: JOIN FETCH

```java
@Query("SELECT DISTINCT o FROM Order o JOIN FETCH o.items WHERE o.memberId = :memberId")
List<Order> findWithItemsByMemberId(@Param("memberId") Long memberId);
```

생성되는 SQL:
```sql
SELECT DISTINCT o.*, oi.*
FROM orders o
INNER JOIN order_item oi ON o.id = oi.order_id
WHERE o.member_id = 10001;
```

```sql
EXPLAIN SELECT DISTINCT o.id, o.status, oi.id, oi.product_id
FROM orders o
INNER JOIN order_item oi ON o.id = oi.order_id
WHERE o.member_id = 10001;
```

```
id  select_type  table  type   key                       rows  Extra
1   SIMPLE       o      ref    idx_orders_member_id      20    Using temporary
1   SIMPLE       oi     ref    idx_order_item_order      4     NULL
```

`Using temporary`가 보인다. `DISTINCT` 때문에 임시 테이블을 쓴다. 대용량에서는 부담이 된다. `DISTINCT` 없이 Set으로 결과를 받거나 DTO 프로젝션으로 바꾸는 방식이 더 낫다.

### 더 나은 방법: DTO 프로젝션

```java
@Query("""
    SELECT new com.example.dto.OrderItemSummary(
        o.id, o.status, oi.productId, oi.quantity
    )
    FROM Order o JOIN o.items oi
    WHERE o.memberId = :memberId
""")
List<OrderItemSummary> findSummaryByMemberId(@Param("memberId") Long memberId);
```

생성 SQL에서 `SELECT *` 대신 필요한 컬럼만 가져오므로 커버링 인덱스를 활용할 가능성이 높아지고, 영속성 컨텍스트에 엔티티를 올리지 않아 메모리도 절약된다.

```sql
EXPLAIN SELECT o.id, o.status, oi.product_id, oi.quantity
FROM orders o
JOIN order_item oi ON o.id = oi.order_id
WHERE o.member_id = 10001;
```

```
id  select_type  table  type   key                       rows  Extra
1   SIMPLE       o      ref    idx_orders_member_id      20    NULL
1   SIMPLE       oi     ref    idx_order_item_order      4     NULL
```

`Using temporary` 사라짐. 조인 조건과 WHERE가 모두 인덱스를 탄다.

> **중요**: ToMany 컬렉션을 `JOIN FETCH`하면 row 수가 곱으로 증가한다. 주문 20건 × 아이템 평균 5개 = 100 rows가 결과로 올라오고, 페이징(`LIMIT`)이 의도대로 동작하지 않는다. ToMany에서는 `@BatchSize` 또는 별도 쿼리 분리를 먼저 검토해야 한다.

---

## 로컬 실습 환경

### Docker Compose

```yaml
# docker-compose.yml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: wellness
    ports:
      - "3306:3306"
    command: >
      --innodb-buffer-pool-size=256M
      --slow-query-log=ON
      --slow-query-log-file=/var/log/mysql/slow.log
      --long-query-time=0.1
```

```bash
docker compose up -d
docker exec -it <container_name> mysql -uroot -proot wellness
```

### 슬로우 쿼리 실시간 확인

```sql
SHOW VARIABLES LIKE 'slow_query_log%';
SHOW VARIABLES LIKE 'long_query_time';

-- 세션에서 임시로 모든 쿼리를 슬로우 로그에 남기기
SET SESSION long_query_time = 0;
```

### 통계 갱신

```sql
ANALYZE TABLE orders;
ANALYZE TABLE order_item;
ANALYZE TABLE member;
ANALYZE TABLE product;
```

---

## 샘플 스키마와 데이터

### DDL

```sql
CREATE TABLE member (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    email      VARCHAR(100) NOT NULL,
    name       VARCHAR(50)  NOT NULL,
    grade      VARCHAR(20)  NOT NULL DEFAULT 'BASIC',  -- BASIC, VIP, VVIP
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_member_email (email),
    KEY idx_member_grade (grade)
) ENGINE=InnoDB;

CREATE TABLE product (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    name       VARCHAR(200) NOT NULL,
    category   VARCHAR(50)  NOT NULL,
    price      INT          NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'ON_SALE',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_product_category_status (category, status)
) ENGINE=InnoDB;

CREATE TABLE inventory (
    id         BIGINT   NOT NULL AUTO_INCREMENT,
    product_id BIGINT   NOT NULL,
    stock      INT      NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_inventory_product (product_id)
) ENGINE=InnoDB;

CREATE TABLE orders (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    member_id  BIGINT      NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, PAID, SHIPPED, COMPLETED, CANCELLED
    total      INT         NOT NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_orders_member_id       (member_id),
    KEY idx_orders_status_created  (status, created_at)
) ENGINE=InnoDB;

CREATE TABLE order_item (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    order_id   BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity   INT    NOT NULL,
    unit_price INT    NOT NULL,
    PRIMARY KEY (id),
    KEY idx_order_item_order   (order_id),
    KEY idx_order_item_product (product_id)
) ENGINE=InnoDB;
```

### 샘플 데이터 대량 삽입

```sql
-- member 10,000건
INSERT INTO member (email, name, grade, created_at)
SELECT
    CONCAT('user', seq, '@example.com'),
    CONCAT('회원', seq),
    ELT(1 + FLOOR(RAND() * 3), 'BASIC', 'VIP', 'VVIP'),
    DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 730) DAY)
FROM (
    SELECT a.n + b.n * 100 + 1 AS seq
    FROM (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
          UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a
    CROSS JOIN
         (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
          UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b
    LIMIT 10000
) g;

-- product 1,000건
INSERT INTO product (name, category, price, status, created_at)
SELECT
    CONCAT('상품-', seq),
    ELT(1 + FLOOR(RAND() * 5), 'SKINCARE', 'HAIRCARE', 'BODY', 'WELLNESS', 'MAKEUP'),
    (1 + FLOOR(RAND() * 100)) * 1000,
    IF(RAND() > 0.05, 'ON_SALE', 'SOLD_OUT'),
    DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 365) DAY)
FROM (
    SELECT a.n + b.n * 100 + 1 AS seq
    FROM (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
          UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a
    CROSS JOIN
         (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
          UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b
    LIMIT 1000
) g;

-- inventory
INSERT INTO inventory (product_id, stock)
SELECT id, FLOOR(RAND() * 1000) FROM product;

-- orders 100,000건 (information_schema.columns 활용)
INSERT INTO orders (member_id, status, total, created_at)
SELECT
    1 + FLOOR(RAND() * 10000),
    ELT(1 + FLOOR(RAND() * 5), 'PENDING', 'PAID', 'SHIPPED', 'COMPLETED', 'CANCELLED'),
    (1 + FLOOR(RAND() * 50)) * 5000,
    DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 365) DAY)
FROM information_schema.columns
LIMIT 100000;

-- order_item (주문당 평균 3개)
INSERT INTO order_item (order_id, product_id, quantity, unit_price)
SELECT
    o.id,
    1 + FLOOR(RAND() * 1000),
    1 + FLOOR(RAND() * 5),
    (1 + FLOOR(RAND() * 100)) * 1000
FROM orders o
CROSS JOIN (SELECT 1 UNION SELECT 2 UNION SELECT 3) multiplier
WHERE RAND() < 0.7;
```

### 테스트 쿼리

```sql
-- 1. 특정 회원의 최근 주문 조회
EXPLAIN SELECT id, status, total, created_at
FROM orders
WHERE member_id = 100
ORDER BY created_at DESC
LIMIT 10;

-- 2. 상태별 주문 집계 (기간 필터 포함)
EXPLAIN SELECT status, COUNT(*) AS cnt, SUM(total) AS revenue
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY status;

-- 3. 회원 + 주문 조인
EXPLAIN SELECT m.name, m.grade, o.status, o.total
FROM orders o
JOIN member m ON o.member_id = m.id
WHERE o.status = 'PENDING'
  AND o.created_at >= '2026-04-01';

-- 4. 상품 카테고리별 재고 현황
EXPLAIN SELECT p.category, p.name, i.stock
FROM product p
JOIN inventory i ON p.id = i.product_id
WHERE p.category = 'SKINCARE'
  AND p.status = 'ON_SALE'
ORDER BY i.stock ASC;
```

---

## 인덱스를 못 타는 경우 / 타게 바꾸는 경우

### 1. 컬럼에 함수 적용

```sql
-- ❌ YEAR() 함수가 created_at에 적용 → 인덱스 미사용
SELECT * FROM orders WHERE YEAR(created_at) = 2026;

-- ✅ 범위 조건으로 변경
SELECT * FROM orders
WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01';
```

이유: 인덱스는 `created_at` 컬럼 값 자체를 정렬해 저장한다. `YEAR(created_at)`은 옵티마이저 입장에서 "변환된 새 값"이라 인덱스 키와 비교가 불가능하다. 범위로 풀면 B+Tree 리프 노드를 그대로 순회할 수 있다.

### 2. 묵시적 형변환

```sql
-- ❌ member_id가 BIGINT인데 문자열로 비교
SELECT * FROM orders WHERE member_id = '10001';

-- ✅ 타입 일치
SELECT * FROM orders WHERE member_id = 10001;
```

이유: MySQL이 내부적으로 `CAST(member_id AS CHAR)`를 수행해 인덱스를 사용할 수 없게 된다. JPA에서 파라미터 타입이 잘못 바인딩되면 이 문제가 조용히 발생하므로 생성 SQL의 파라미터 타입을 확인해야 한다.

### 3. LIKE 앞 와일드카드

```sql
-- ❌ 앞 와일드카드 — B+Tree는 앞에서부터 정렬되므로 스캔 불가
SELECT * FROM member WHERE name LIKE '%영희';

-- ✅ 접두사 검색은 인덱스 가능
SELECT * FROM member WHERE name LIKE '김%';
```

이유: B+Tree 인덱스는 값을 앞에서부터 정렬해 저장한다. 접미사(`%영희`)를 찾으려면 정렬 순서를 이용할 수 없어 전체를 스캔해야 한다. 접미사/부분 문자열 검색이 핵심 요구사항이면 별도 전문 검색 엔진(Elasticsearch 등)을 쓰는 것이 맞다.

### 4. OR 조건으로 인덱스 분산

```sql
-- ❌ 두 인덱스를 OR로 묶으면 index_merge가 발생하거나 하나만 탄다
SELECT * FROM orders WHERE member_id = 100 OR status = 'PENDING';

-- ✅ UNION ALL로 분리
SELECT * FROM orders WHERE member_id = 100
UNION ALL
SELECT * FROM orders WHERE status = 'PENDING' AND member_id != 100;
```

이유: `index_merge`는 두 인덱스 결과를 메모리에서 병합하는 비용이 크다. 대용량에서는 UNION ALL이 각 인덱스를 독립적으로 타서 훨씬 안정적이다.

### 5. 복합 인덱스 선두 컬럼 누락

```sql
-- 인덱스: idx_orders_status_created (status, created_at)

-- ❌ 선두 컬럼 status 없이 created_at만으로 조회
SELECT * FROM orders WHERE created_at >= '2026-01-01';
-- → type: ALL (풀스캔)

-- ✅ 선두 컬럼 포함
SELECT * FROM orders
WHERE status = 'PENDING' AND created_at >= '2026-01-01';
-- → type: range, key: idx_orders_status_created
```

이유: B+Tree 복합 인덱스는 `(status, created_at)` 순으로 정렬되어 있다. `status` 없이 `created_at`만으로는 트리의 시작점을 찾을 방법이 없다. 좌측 접두사 규칙은 인덱스 설계의 가장 기본이다.

### 6. 데이터 분포 편중 — 옵티마이저가 풀스캔 선택

```sql
-- orders.status 분포: COMPLETED 97%, 나머지 3%
-- ❌ 옵티마이저가 인덱스보다 풀스캔이 낫다고 판단
EXPLAIN SELECT * FROM orders WHERE status = 'COMPLETED';
-- → type: ALL

-- ✅ 더 선택도 높은 컬럼과 조합하거나 범위 조건 추가
SELECT * FROM orders
WHERE status = 'COMPLETED' AND created_at >= '2026-04-01';
```

이유: 전체의 97%를 인덱스 랜덤 I/O로 읽으면 풀스캔의 순차 I/O보다 느리다. 옵티마이저가 맞게 판단한 것이다. 억지로 인덱스를 강제하면 오히려 느려진다. 쿼리 설계 자체를 바꾸거나 히스토그램을 추가해 더 정확한 통계를 제공하는 게 올바른 방향이다.

### 7. 인덱스 컬럼에 연산 적용

```sql
-- ❌ 컬럼에 산술 연산 → 인덱스 불가
SELECT * FROM orders WHERE total / 100 > 500;

-- ✅ 상수 쪽을 이동
SELECT * FROM orders WHERE total > 50000;
```

### 8. NULL 비교 주의

```sql
-- IS NULL은 인덱스 사용 가능
SELECT * FROM orders WHERE updated_at IS NULL;

-- IS NOT NULL도 인덱스 사용 가능 (데이터 분포에 따라 다름)
SELECT * FROM orders WHERE updated_at IS NOT NULL;

-- 잘못된 패턴 — 항상 공집합
SELECT * FROM orders WHERE updated_at != NULL;  -- NULL 비교는 = 또는 != 대신 IS NULL / IS NOT NULL 사용
```

---

## Aurora MySQL 관점 정리

CJ 올리브영은 **Aurora Serverless(MySQL 호환)**를 사용한다. 실행 계획 문법과 해석 방식은 일반 MySQL과 동일하지만, 운영 환경에서 알아야 할 차이점이 있다.

### Reader/Writer 통계 불일치

Aurora는 Writer 인스턴스와 Reader 인스턴스를 분리한다. `@Transactional(readOnly = true)` 설정과 드라이버 레벨 라우팅으로 조회 쿼리를 Reader로 분산할 수 있다.

**주의**: Writer와 Reader는 통계를 독립적으로 유지할 수 있다. 동일한 쿼리가 Writer에서 `ref`로 실행되고 Reader에서 `ALL`로 실행되는 경우가 발생할 수 있다. 통계 불일치가 의심되면 Reader 인스턴스에 직접 접속해 `ANALYZE TABLE`을 실행한다.

### 슬로우 쿼리 진단 워크플로우

```
Performance Insights → Top SQL에서 평균 대기 시간 높은 쿼리 확인
    ↓
문제 쿼리 digest 추출
    ↓
개발/스테이징 환경에서 EXPLAIN / EXPLAIN ANALYZE 실행
    ↓
인덱스 설계 또는 쿼리 수정
    ↓
배포 후 Performance Insights 재확인
```

CloudWatch Logs Insights와 슬로우 쿼리 로그를 조합해 특정 시간대 문제 쿼리를 추출하는 방법도 익혀두면 유용하다.

### Aurora Serverless 스케일링과 실행 계획

Aurora Serverless v2는 ACU(Aurora Capacity Unit) 단위로 자동 스케일링된다. 쿼리 하나가 풀스캔으로 CPU를 급격히 올리면 스케일 업 이전에 레이턴시 스파이크가 발생한다. 인스턴스를 올리기 전에 실행 계획을 먼저 점검하면 스케일 업 없이 해결 가능한 케이스가 상당히 많다.

### 통계 hygiene

InnoDB 통계는 영구 저장(`innodb_stats_persistent=ON`)된다. 대량 INSERT/DELETE/배치 작업 이후 통계가 자동 갱신되지 않으면 옵티마이저가 잘못된 계획을 세울 수 있다.

```sql
-- 통계 갱신
ANALYZE TABLE orders;

-- 히스토그램 생성 (MySQL 8.0+, 분포 편중 컬럼에 유효)
ANALYZE TABLE orders UPDATE HISTOGRAM ON status WITH 10 BUCKETS;

-- 현재 통계 확인
SELECT * FROM information_schema.INNODB_TABLE_STATS
WHERE table_name = 'orders';
```

배치 작업이나 마이그레이션 후 대상 테이블의 `ANALYZE TABLE`을 루틴으로 포함하는 것이 좋다.

---

## 예상 면접 질문과 7년차 수준의 답변 포인트

### Q1. EXPLAIN에서 가장 먼저 확인하는 것이 무엇인가요?

**답변 포인트**: `type` 컬럼을 가장 먼저 본다. `ALL`이 있으면 즉시 경보다. 그 다음 `key`가 NULL인지 확인하고, `rows`와 `filtered`를 조합해 실제 처리 행 수를 추정한다. 마지막으로 `Extra`에서 `Using filesort`나 `Using temporary`가 있는지 확인한다. 컬럼 하나만 보는 게 아니라 이 세트를 함께 읽어야 전체 그림이 보인다.

### Q2. 인덱스가 있는데 옵티마이저가 사용하지 않았습니다. 왜 그런가요?

**답변 포인트**: 크게 세 가지다. 첫째, 데이터 분포가 편중되어 인덱스 랜덤 I/O가 풀스캔 순차 I/O보다 비용이 크다고 판단한 경우 — 옵티마이저가 맞게 판단한 것이다. 둘째, 통계 정보가 오래됐거나 잘못된 경우 — `ANALYZE TABLE`로 갱신하고 재확인한다. 셋째, 컬럼에 함수나 연산이 적용되어 인덱스 키와 비교할 수 없는 경우 — 쿼리 형태를 바꿔야 한다.

### Q3. JPA N+1 문제를 어떻게 발견하고 해결하나요?

**답변 포인트**: 발견은 Hibernate 통계 로그나 p6spy로 쿼리 수를 측정한다. EXPLAIN 한 번만 보면 단건 plan이 좋아 보여 N+1을 놓친다. 해결은 연관관계 타입에 따라 다르다 — ToOne은 `JOIN FETCH`가 비교적 안전하지만, ToMany는 row 폭증과 페이징 문제가 생긴다. ToMany에서는 `@BatchSize`로 IN 절 묶음 조회를 하거나 별도 쿼리로 분리한다. 최종적으로 생성된 SQL의 EXPLAIN으로 반드시 검증한다.

### Q4. EXPLAIN ANALYZE 결과에서 예상 rows와 실제 rows가 크게 다릅니다. 어떻게 처리하나요?

**답변 포인트**: 통계 오차다. `ANALYZE TABLE`로 통계를 갱신하고 재실행한다. 갱신 후에도 편차가 크면 데이터 분포가 매우 치우쳐 있는 것이다. MySQL 8.0이라면 히스토그램을 생성해 옵티마이저가 더 정확한 선택도를 추정하도록 한다. 그래도 해결이 안 되면 쿼리 형태나 인덱스 설계 자체를 재검토한다.

### Q5. 복합 인덱스 설계 원칙을 설명해 주세요.

**답변 포인트**: 세 가지다. 첫째, `=` 조건 컬럼을 앞에, 범위 조건 컬럼을 뒤에 배치한다 — 범위 조건 이후 컬럼은 인덱스를 사용할 수 없기 때문이다. 둘째, 선택도가 높은 컬럼을 앞에 두는 것이 일반 원칙이지만 실제 쿼리 패턴이 우선이다. 셋째, SELECT 컬럼을 인덱스에 포함해 커버링 인덱스로 만들면 테이블 액세스 없이 처리할 수 있다 — `Extra: Using index`로 확인할 수 있다.

### Q6. 인덱스를 추가했는데 오히려 쓰기 성능이 떨어졌습니다. 왜인가요?

**답변 포인트**: 인덱스는 읽기를 올리는 대신 쓰기 비용을 높인다. `INSERT`/`UPDATE`/`DELETE` 시 테이블뿐 아니라 모든 인덱스도 함께 변경해야 하고, B+Tree 페이지 분할이 발생하면 추가 I/O와 잠금이 생긴다. 불필요한 인덱스가 많으면 쓰기 처리량이 크게 줄어든다. 실제 쿼리 패턴을 분석해 꼭 필요한 인덱스만 유지해야 한다.

### Q7. Aurora MySQL에서 EXPLAIN을 사용할 때 주의할 점이 있나요?

**답변 포인트**: 문법과 실행 계획 형식은 일반 MySQL과 동일하다. 다만 Reader 인스턴스의 통계가 Writer와 달라져 동일 쿼리의 실행 계획이 달라질 수 있다. 슬로우 쿼리 진단은 Performance Insights에서 시작해 개발 환경에서 EXPLAIN으로 검증하는 워크플로우가 중요하다. 또 Aurora Serverless는 스케일 업 이전에 레이턴시 스파이크가 있어, 이를 인스턴스 용량 문제로 오해하지 않고 실행 계획을 먼저 확인하는 습관이 필요하다.

---

## 실전 연습 체크리스트

### EXPLAIN 기본

- [ ] `type` 컬럼에서 `ALL`, `index`를 식별하고 원인을 설명할 수 있다
- [ ] `possible_keys`와 `key`가 다를 때 이유를 설명할 수 있다
- [ ] `key_len`으로 복합 인덱스에서 몇 번째 컬럼까지 사용됐는지 판단할 수 있다
- [ ] `rows × (filtered / 100)`으로 실제 처리 행 수를 추정할 수 있다
- [ ] `Extra: Using filesort / Using temporary / Using index`를 구분하고 대응 방향을 말할 수 있다

### EXPLAIN ANALYZE

- [ ] `actual time`과 `cost`의 차이를 설명할 수 있다
- [ ] rows 예측 vs 실제 편차가 클 때 `ANALYZE TABLE`을 실행하고 이유를 설명할 수 있다
- [ ] 트리에서 가장 느린 노드를 찾아 병목을 설명할 수 있다
- [ ] `loops` 값으로 N+1과 유사한 구조를 SQL 레벨에서 식별할 수 있다

### 인덱스 설계

- [ ] 함수/연산/형변환이 인덱스를 막는 이유를 설명할 수 있다
- [ ] 복합 인덱스에서 선두 컬럼 누락 시 동작을 설명할 수 있다
- [ ] 커버링 인덱스가 적용됐는지 `Extra`로 확인할 수 있다
- [ ] 샘플 스키마에서 쿼리를 보고 인덱스 설계 방향을 제안할 수 있다
- [ ] 데이터 분포 편중 시 옵티마이저의 판단을 설명할 수 있다

### JPA 연동

- [ ] N+1이 발생하는 코드를 보고 EXPLAIN과 연결해 설명할 수 있다
- [ ] `JOIN FETCH`와 DTO 프로젝션의 실행 계획 차이를 설명할 수 있다
- [ ] ToMany `JOIN FETCH`의 row 폭증과 페이징 문제를 설명할 수 있다
- [ ] Hibernate 통계 로그로 N+1 여부를 진단하는 방법을 알고 있다

### Aurora MySQL

- [ ] Reader/Writer 통계 불일치 가능성을 인식하고 대응 방법을 말할 수 있다
- [ ] Performance Insights에서 슬로우 쿼리를 찾는 워크플로우를 설명할 수 있다
- [ ] 대량 데이터 변경 후 `ANALYZE TABLE`을 루틴에 포함해야 하는 이유를 말할 수 있다
- [ ] Serverless 스케일 업 전에 실행 계획을 먼저 확인해야 하는 이유를 설명할 수 있다

---

## 관련 문서

- [B-Tree 인덱스](./b-tree-index.md)
- [InnoDB 트랜잭션과 잠금](./transaction-lock.md)
- [Spring Data JPA 트랜잭션 실수](../../java/spring/jpa-transaction.md)
