Here is the final markdown draft:

---

```markdown
# [초안] MySQL EXPLAIN / EXPLAIN ANALYZE 완전 정복 — 실행 계획 읽기부터 Aurora 인터뷰 대비까지

## 1. 왜 알아야 하는가

백엔드 인터뷰에서 "N+1 문제를 어떻게 해결했나요?"에 "JOIN FETCH를 썼습니다"라고 답하면 반타작입니다.
면접관이 바로 묻습니다. "EXPLAIN으로 확인해봤나요? 실행 계획이 어떻게 달라졌나요?"

EXPLAIN은 MySQL 옵티마이저가 쿼리를 실제로 어떻게 처리할지 보여주는 실행 계획(Execution Plan)입니다.
인덱스를 타는지, 풀스캔인지, 몇 행을 읽는지 — 이것을 읽을 줄 알아야 슬로우 쿼리의 원인을 진단하고 인덱스를 올바르게 설계할 수 있습니다.

CJ 올리브영 웰니스 플랫폼처럼 상품·주문·사용자 데이터가 대규모로 쌓이는 커머스 백엔드에서는, EXPLAIN을 읽지 못하면 성능 문제가 배포 후에야 드러납니다.

---

## 2. 핵심 개념

### 2-1. EXPLAIN vs EXPLAIN ANALYZE

| 구분 | 실행 여부 | 출력 |
|------|-----------|------|
| `EXPLAIN` | 실행 안 함 | 옵티마이저의 예측 계획만 출력 |
| `EXPLAIN ANALYZE` | 실제로 실행 | 예측값 + 실제 실행 결과(actual) 함께 출력 (MySQL 8.0.18+) |

> `EXPLAIN ANALYZE`는 쿼리를 실제로 실행하므로 대용량 테이블에서는 주의하세요.
> `SELECT`에만 사용하고, `UPDATE`/`DELETE`에는 `EXPLAIN`만 사용합니다.

---

### 2-2. EXPLAIN 출력 컬럼 해석

```
+----+-------------+-------+------+---------------+-----+---------+------+------+----------+----------------+
| id | select_type | table | type | possible_keys | key | key_len | ref  | rows | filtered | Extra          |
+----+-------------+-------+------+---------------+-----+---------+------+------+----------+----------------+
```

---

#### `type` — 가장 중요한 컬럼

성능이 좋은 순서대로 나열합니다.

| type | 의미 | 신호 |
|------|------|------|
| `system` | 테이블 행이 0~1개 | 최적 |
| `const` | PK 또는 Unique 인덱스로 정확히 1행 조회 | 최적 |
| `eq_ref` | 조인에서 PK/Unique로 1행씩 매칭 | 매우 좋음 |
| `ref` | Non-unique 인덱스로 여러 행 매칭 | 좋음 |
| `range` | 인덱스 범위 스캔 (`BETWEEN`, `>`, `<`, `IN`) | 보통 |
| `index` | 인덱스 풀스캔 (테이블 풀스캔보다 낫지만 느림) | 나쁨 |
| `ALL` | 테이블 풀스캔 | 매우 나쁨 |

> **인터뷰 포인트**: `ALL`이나 `index`가 보이면 인덱스 설계를 즉시 검토해야 합니다.

---

#### `rows` — 예상 읽기 행 수

옵티마이저가 조건 만족을 위해 읽어야 한다고 추정하는 행 수입니다.
통계 기반 추정값이며 실제 반환 행 수가 아닙니다.
이 값이 전체 테이블 행 수에 가까우면 인덱스가 동작하지 않는다는 신호입니다.

---

#### `filtered` — 조건 필터링 비율 (%)

`rows × (filtered ÷ 100)` = 다음 단계로 전달되는 예상 행 수입니다.
`filtered`가 낮을수록 WHERE 조건이 인덱스 밖에서 처리되고 있다는 의미입니다.

---

#### `Extra` — 추가 실행 정보

| Extra 값 | 의미 | 조치 |
|----------|------|------|
| `Using index` | 커버링 인덱스 — 테이블 접근 없음 | 최적 |
| `Using where` | 인덱스 후 WHERE 필터 추가 적용 | 대체로 정상 |
| `Using filesort` | 메모리/디스크 정렬 수행 | 인덱스 개선 검토 |
| `Using temporary` | 임시 테이블 사용 (GROUP BY, DISTINCT 등) | 쿼리 재설계 검토 |
| `Using join buffer` | 조인 컬럼에 인덱스 없음 | 인덱스 추가 |
| `Using index condition` | ICP(Index Condition Pushdown) 적용 | 긍정적 신호 |

---

## 3. 로컬 실습 환경 구성 (MySQL 8 Docker)

```bash
docker run --name mysql8-explain \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=shopdb \
  -p 3306:3306 \
  -d mysql:8.0

docker exec -it mysql8-explain mysql -uroot -proot shopdb
```

### 샘플 DDL

```sql
CREATE TABLE category (
  id   BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL
);

CREATE TABLE product (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  name        VARCHAR(200) NOT NULL,
  category_id BIGINT NOT NULL,
  price       INT NOT NULL,
  status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_product_category FOREIGN KEY (category_id) REFERENCES category(id)
);

CREATE TABLE orders (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id    BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  quantity   INT NOT NULL,
  ordered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES product(id)
);
```

### 샘플 데이터 (카테고리 10개 / 상품 10만 / 주문 50만)

```sql
-- 카테고리 10개
INSERT INTO category (name)
SELECT CONCAT('category_', n)
FROM (SELECT 1 n UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
      UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9 UNION SELECT 10) t;

-- 상품 10만 건
INSERT INTO product (name, category_id, price, status, created_at)
WITH RECURSIVE gen(n) AS (
  SELECT 1 UNION ALL SELECT n + 1 FROM gen WHERE n < 100000
)
SELECT
  CONCAT('product_', n),
  (n % 10) + 1,
  (n % 100) * 1000 + 1000,
  IF(n % 20 = 0, 'INACTIVE', 'ACTIVE'),
  DATE_SUB(NOW(), INTERVAL n SECOND)
FROM gen;

-- 주문 50만 건
INSERT INTO orders (user_id, product_id, quantity, ordered_at)
WITH RECURSIVE gen(n) AS (
  SELECT 1 UNION ALL SELECT n + 1 FROM gen WHERE n < 500000
)
SELECT
  (n % 1000) + 1,
  (n % 100000) + 1,
  (n % 5) + 1,
  DATE_SUB(NOW(), INTERVAL n SECOND)
FROM gen;
```

---

## 4. 실행 계획 실습

### 4-1. 풀스캔 → 인덱스 스캔

```sql
-- 인덱스 없음: 풀스캔
EXPLAIN SELECT * FROM product WHERE status = 'ACTIVE';
-- type: ALL, rows: ~100000, Extra: Using where

-- 인덱스 추가
CREATE INDEX idx_product_status ON product(status);

EXPLAIN SELECT * FROM product WHERE status = 'ACTIVE';
-- type: ref, rows: ~95000
```

> `status` 컬럼은 카디널리티가 낮아 옵티마이저가 인덱스를 무시하고 풀스캔을 선택할 수 있습니다.
> 이럴 때는 `(status, created_at)` 복합 인덱스로 선택도를 높입니다.

---

### 4-2. 커버링 인덱스

```sql
-- 커버링 인덱스 없음
EXPLAIN SELECT id, name FROM product WHERE category_id = 3;
-- Extra: (없음 — 테이블 랜덤 I/O 발생)

-- 복합 커버링 인덱스 추가
CREATE INDEX idx_product_cat_name ON product(category_id, name);

EXPLAIN SELECT id, name FROM product WHERE category_id = 3;
-- Extra: Using index  ← 테이블 접근 없음
```

---

### 4-3. filesort 발생과 제거

```sql
-- filesort 발생
EXPLAIN SELECT * FROM product WHERE category_id = 3 ORDER BY created_at DESC;
-- Extra: Using filesort

-- 정렬 컬럼을 인덱스에 포함
CREATE INDEX idx_product_cat_created ON product(category_id, created_at);

EXPLAIN SELECT * FROM product WHERE category_id = 3 ORDER BY created_at DESC;
-- Extra: (없음) ← 인덱스로 정렬 처리
```

---

## 5. EXPLAIN ANALYZE 실습

```sql
EXPLAIN ANALYZE
SELECT p.name, COUNT(o.id) AS order_count
FROM product p
JOIN orders o ON o.product_id = p.id
WHERE p.category_id = 1
GROUP BY p.id, p.name
ORDER BY order_count DESC
LIMIT 10;
```

출력 예시 (트리 형식, 안쪽부터 실행):

```
-> Limit: 10 row(s)  (actual time=52.3..52.3 rows=10 loops=1)
    -> Sort: order_count DESC  (actual time=52.2..52.2 rows=10 loops=1)
        -> Table scan on <temporary>  (actual time=52.0..52.1 rows=9890 loops=1)
            -> Aggregate using temporary table  (actual time=... rows=9890 loops=1)
                -> Nested loop inner join  (actual time=... rows=49450 loops=1)
                    -> Index lookup on p using fk_product_category
                       (category_id=1)  (actual time=0.1..1.2 rows=9890 loops=1)
                    -> Index lookup on o using fk_orders_product
                       (product_id=p.id)  (actual time=0.0..0.0 rows=5 loops=9890)
```

**읽는 법**:
- 들여쓰기가 깊을수록 먼저 실행됩니다.
- `actual time=X..Y`: X는 첫 행 반환 시간(ms), Y는 마지막 행 반환 시간(ms)
- `rows`: 실제 처리 행 수
- `loops`: 이 노드가 반복 실행된 횟수

---

## 6. JPA N+1 vs JOIN FETCH — EXPLAIN 비교

### N+1 발생 패턴

```java
// 카테고리별 상품 조회 후 루프에서 주문 접근
List<Product> products = productRepository.findByCategoryId(1L);
for (Product p : products) {
    int count = p.getOrders().size(); // 지연 로딩 → 쿼리 N번 추가 발생
}
```

실제 발생 SQL:
```sql
-- 1번
SELECT * FROM product WHERE category_id = 1;

-- N번 (product 수만큼)
SELECT * FROM orders WHERE product_id = 1;
SELECT * FROM orders WHERE product_id = 2;
-- ...
```

각 추가 쿼리 EXPLAIN:
```sql
EXPLAIN SELECT * FROM orders WHERE product_id = ?;
-- type: ref (FK 인덱스 존재 시), rows: ~5
-- 쿼리 자체는 빠르지만 9,890번 반복 → 네트워크 왕복 비용 누적
```

---

### JOIN FETCH로 해결

```java
@Query("SELECT DISTINCT p FROM Product p JOIN FETCH p.orders WHERE p.categoryId = :cid")
List<Product> findWithOrders(@Param("cid") Long categoryId);
```

발생 SQL:
```sql
SELECT DISTINCT p.*, o.*
FROM product p
INNER JOIN orders o ON o.product_id = p.id
WHERE p.category_id = 1;
```

EXPLAIN:
```sql
EXPLAIN SELECT DISTINCT p.id, p.name, o.id, o.quantity
FROM product p
INNER JOIN orders o ON o.product_id = p.id
WHERE p.category_id = 1;
```

```
+----+-------------+-------+------+---------------------+---------------------+----------+
| id | select_type | table | type | key                 | ref                 | rows     |
+----+-------------+-------+------+---------------------+---------------------+----------+
|  1 | SIMPLE      | p     | ref  | fk_product_category | const               | 9890     |
|  1 | SIMPLE      | o     | ref  | fk_orders_product   | shopdb.p.id         | 5        |
+----+-------------+-------+------+---------------------+---------------------+----------+
```

**비교 정리**:

| 방식 | 쿼리 수 | 특이사항 |
|------|---------|----------|
| N+1 | N+1번 | 쿼리 자체는 빠르지만 커넥션/왕복 비용 N배 |
| JOIN FETCH | 1번 | 카테시안 곱으로 데이터 양 증가 가능 |
| @BatchSize / IN | 2번 내외 | 중간 타협안, 메모리 사용 예측 가능 |

---

## 7. 나쁜 예 vs 개선 예

### 7-1. 인덱스 컬럼에 함수 적용 → 인덱스 무효화

```sql
-- Bad: 함수로 인덱스 컬럼 변환 → 풀스캔
EXPLAIN SELECT * FROM product WHERE YEAR(created_at) = 2025;
-- type: ALL

-- Good: 범위 조건으로 변환
EXPLAIN SELECT * FROM product
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01';
-- type: range
```

---

### 7-2. OR 조건으로 인덱스 분산

```sql
-- Bad: OR로 인덱스 분리 → index_merge 또는 풀스캔
EXPLAIN SELECT * FROM product WHERE category_id = 1 OR status = 'ACTIVE';

-- Good: UNION ALL로 각각 인덱스 활용
EXPLAIN
  SELECT * FROM product WHERE category_id = 1
  UNION ALL
  SELECT * FROM product WHERE status = 'ACTIVE' AND category_id != 1;
```

---

### 7-3. SELECT * 와 커버링 인덱스

```sql
-- Bad: 불필요한 컬럼 포함 → 테이블 랜덤 I/O 발생
SELECT * FROM product WHERE category_id = 3 LIMIT 20;

-- Good: 필요한 컬럼만 선택
-- idx_product_cat_name(category_id, name) 존재 시 Extra: Using index
SELECT id, name FROM product WHERE category_id = 3 LIMIT 20;
```

---

### 7-4. 복합 인덱스 선두 컬럼 원칙 위반

```sql
-- 인덱스: (category_id, status, created_at)

-- Bad: 중간 컬럼(status) 건너뜀 → created_at 범위에 인덱스 미사용
EXPLAIN SELECT * FROM product
WHERE category_id = 1 AND created_at > '2025-01-01';

-- Good: 선두 컬럼부터 순서대로
EXPLAIN SELECT * FROM product
WHERE category_id = 1 AND status = 'ACTIVE' AND created_at > '2025-01-01';
```

---

## 8. Aurora MySQL 특이사항

Aurora MySQL은 MySQL 8 호환이지만 실행 계획 해석 시 알아야 할 차이점이 있습니다.

### 읽기/쓰기 분리 — readOnly 라우팅

```java
@Transactional(readOnly = true)
public List<ProductDto> findByCategory(Long categoryId) {
    return productRepository.findByCategoryId(categoryId);
}
```

`readOnly = true`이면 Spring은 Reader 인스턴스로 라우팅합니다.
EXPLAIN도 Reader에서 실행되므로, 대용량 조회 성능 분석 시 Reader 인스턴스에서 직접 확인하는 것이 정확합니다.

### 병렬 쿼리 (Parallel Query)

Aurora MySQL 일부 버전에서 `Extra: Using parallel query`가 나타날 수 있습니다.
풀스캔 자체를 없애지 못하는 분석성 쿼리에서 스토리지 레이어 병렬 처리로 속도를 보완합니다.

### 통계 정보 갱신

대량 데이터 적재 후 EXPLAIN 계획이 부정확해 보이면 수동으로 통계를 갱신합니다:

```sql
ANALYZE TABLE product;
ANALYZE TABLE orders;
```

---

## 9. 인터뷰 답변 프레이밍

### Q. 쿼리 성능 문제를 어떻게 찾고 해결하나요?

> "슬로우 쿼리 로그나 APM에서 임계치 초과 쿼리를 먼저 식별합니다. 해당 쿼리를 `EXPLAIN`으로 분석해 `type`이 `ALL`이거나 `Extra`에 `Using filesort`, `Using temporary`가 있는지 확인합니다. 원인 파악 후 `EXPLAIN ANALYZE`로 예측값과 실제값 차이를 비교해 옵티마이저 통계 오차까지 확인합니다. 인덱스를 추가하거나 쿼리를 수정한 뒤 반드시 다시 EXPLAIN으로 계획이 바뀌었는지 검증합니다."

---

### Q. JPA N+1 문제를 어떻게 해결하나요?

> "N+1은 연관 엔티티를 지연 로딩할 때 루프에서 추가 쿼리가 N번 발생하는 문제입니다. 항상 함께 조회하는 경우 JOIN FETCH를, 데이터 양이 커서 카테시안 곱이 우려되면 `@BatchSize`나 `IN` 쿼리를 씁니다. 어떤 방법을 선택하든 EXPLAIN으로 실제 쿼리가 몇 번 발생하는지, 조인이 인덱스를 타는지 검증합니다."

---

### Q. 커버링 인덱스란 무엇이고 언제 유효한가요?

> "쿼리가 필요로 하는 모든 컬럼이 인덱스에 포함되어 테이블 본문에 랜덤 I/O 없이 인덱스만으로 결과를 반환하는 상태입니다. `EXPLAIN`의 `Extra: Using index`로 확인합니다. `SELECT *` 대신 필요한 컬럼만 선택하고, 복합 인덱스에 SELECT 컬럼을 포함시키면 적용됩니다. 고빈도 조회 경로에서 디스크 I/O를 크게 줄일 수 있어 상품 목록 같은 핫 쿼리에 효과적입니다."

---

## 10. 시니어 레벨 체크리스트

```
[ ] EXPLAIN type 컬럼에서 ALL, index를 즉시 알아보고 위험 신호로 인식한다
[ ] rows * (filtered / 100) 으로 실제 처리 행 수를 추정할 수 있다
[ ] Using filesort, Using temporary가 왜 발생하는지 원인과 해결책을 설명할 수 있다
[ ] Using index (커버링)과 Using index condition (ICP)의 차이를 안다
[ ] EXPLAIN ANALYZE의 actual time, rows, loops를 읽고 병목 노드를 찾을 수 있다
[ ] 복합 인덱스의 Leftmost Prefix 원칙을 EXPLAIN으로 검증할 수 있다
[ ] JPA N+1 쿼리와 JOIN FETCH 쿼리의 EXPLAIN 결과를 비교 설명할 수 있다
[ ] 인덱스 컬럼에 함수를 쓰면 왜 인덱스가 무효화되는지 예시로 보여줄 수 있다
[ ] 카디널리티가 낮은 컬럼의 인덱스 한계와 복합 인덱스로의 대안을 설명할 수 있다
[ ] Aurora readOnly 트랜잭션이 Reader 인스턴스로 라우팅됨을 알고 성능 분석 시 활용한다
[ ] ANALYZE TABLE을 언제 실행해야 하는지 설명할 수 있다
```
```
