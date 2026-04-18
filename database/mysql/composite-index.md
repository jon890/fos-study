# [초안] MySQL 복합 인덱스 완전 정복: 좌측 접두사 규칙부터 커버링 인덱스까지

## 왜 복합 인덱스를 깊게 알아야 하는가

단일 컬럼 인덱스는 직관적이다. `user_id`에 인덱스를 걸면 `WHERE user_id = 42`가 빠르다. 그런데 실제 서비스 쿼리는 대부분 조건이 2개 이상이다. `WHERE user_id = 42 AND status = 'ACTIVE'`, `WHERE category_id = 5 AND created_at >= '2025-01-01' ORDER BY created_at DESC` 같은 형태다.

이때 단일 인덱스를 두 개 만들어도 MySQL 옵티마이저는 둘 중 하나만 사용한다(Index Merge가 발생하기도 하지만 그것도 비용이 크다). 복합 인덱스 하나를 올바르게 설계하면 두 조건을 동시에 인덱스 레인지 스캔으로 처리하거나, 심지어 테이블 접근 자체를 없애는 커버링 인덱스로 만들 수 있다.

시니어 백엔드 면접에서 "인덱스 최적화 경험"을 물어볼 때 단일 인덱스 이야기만 한다면 감점 요인이 된다. 복합 인덱스의 좌측 접두사 규칙, 선택도 기반 컬럼 순서 결정, EXPLAIN 해석, 커버링 인덱스 설계까지 설명할 수 있어야 실전 경험이 있다는 인상을 준다.

---

## 복합 인덱스의 내부 구조

복합 인덱스는 B+Tree 구조에서 **여러 컬럼을 하나의 키로 결합**하여 저장한다. 예를 들어 `INDEX idx_user_status (user_id, status)`를 생성하면 인덱스 리프 노드에는 `(user_id, status)` 쌍이 **user_id 오름차순 → 동일 user_id 내에서 status 오름차순** 으로 정렬되어 저장된다.

```
leaf node 예시:
(1, 'ACTIVE')   → row pointer
(1, 'INACTIVE') → row pointer
(2, 'ACTIVE')   → row pointer
(2, 'ACTIVE')   → row pointer
(3, 'DELETED')  → row pointer
```

이 구조에서 핵심은 정렬 순서다. 인덱스는 첫 번째 컬럼을 기준으로 먼저 정렬되고, 그 안에서 두 번째 컬럼이 정렬된다. 세 번째 컬럼이 있다면 두 번째 컬럼 안에서 정렬된다.

이 물리적 구조가 **좌측 접두사 규칙(Leftmost Prefix Rule)** 의 근거다.

---

## 좌측 접두사 규칙 (Leftmost Prefix Rule)

`INDEX idx (a, b, c)`가 있다고 하자. 이 인덱스가 사용 가능한 조건은 항상 **왼쪽 컬럼부터 순서대로** 포함해야 한다.

| 쿼리 조건 | 인덱스 사용 여부 | 설명 |
|---|---|---|
| `WHERE a = 1` | 사용 (a만) | a로 범위 스캔 가능 |
| `WHERE a = 1 AND b = 2` | 사용 (a, b) | a로 좁히고 b로 추가 필터 |
| `WHERE a = 1 AND b = 2 AND c = 3` | 사용 (a, b, c) | 세 컬럼 모두 활용 |
| `WHERE b = 2` | 미사용 | a가 없으면 정렬 순서가 의미 없음 |
| `WHERE b = 2 AND c = 3` | 미사용 | a가 누락 |
| `WHERE a = 1 AND c = 3` | 부분 사용 (a만) | b를 건너뜀, c는 인덱스 활용 안 됨 |

마지막 케이스가 가장 흔한 실수다. `a`와 `c`로 조건을 걸었을 때 `a`까지만 인덱스를 타고 `c`는 테이블에서 필터링한다. `b`를 인덱스에서 건너뛸 수 없기 때문이다.

### 범위 조건이 오면 그 뒤는 인덱스를 타지 않는다

이것이 복합 인덱스 설계에서 가장 중요한 실용 규칙이다.

```sql
INDEX idx (a, b, c)

-- a = 동등, b = 범위 → c는 인덱스 미사용
WHERE a = 1 AND b > 10 AND c = 5
```

`b > 10`은 범위 조건이다. 인덱스에서 `a = 1`로 좁히고 `b > 10`으로 레인지 스캔은 하지만, 그 안에서 `c`는 다시 정렬 보장이 없다. `b`가 달라질 때마다 `c`의 순서가 다를 수 있기 때문이다.

실용적 결론: **동등 조건(`=`) 컬럼을 앞에, 범위 조건 컬럼을 뒤에** 배치해야 인덱스를 최대한 활용한다.

```sql
-- 좋은 설계: status(동등) 먼저, created_at(범위) 나중
INDEX idx (user_id, status, created_at)
WHERE user_id = 42 AND status = 'ACTIVE' AND created_at >= '2025-01-01'
-- → user_id, status, created_at 세 컬럼 모두 인덱스 활용

-- 나쁜 설계: created_at(범위)이 중간에 끼면
INDEX idx (user_id, created_at, status)
WHERE user_id = 42 AND status = 'ACTIVE' AND created_at >= '2025-01-01'
-- → user_id, created_at까지만 인덱스 활용, status는 필터링
```

---

## 선택도(Selectivity)와 컬럼 순서 결정

선택도는 `유니크한 값의 수 / 전체 행 수`다. 1에 가까울수록 선택도가 높다(성별은 낮고, UUID는 높다).

복합 인덱스에서 컬럼 순서를 결정할 때 선택도 외에도 쿼리 패턴을 반드시 고려해야 한다. 흔히 "선택도가 높은 컬럼을 앞에"라고 말하지만, 이것만 따르면 잘못된 설계가 된다.

### 잘못된 단순 법칙: "선택도 높은 것을 앞에"

```sql
-- users 테이블: user_id(매우 높은 선택도), status(낮은 선택도)
-- 쿼리: WHERE status = 'ACTIVE' ORDER BY created_at

-- 단순 선택도 기준이면 user_id를 앞에 놓고 싶지만
-- 이 쿼리에 user_id 조건이 없다면 user_id를 앞에 놓으면 인덱스를 못 탄다
```

### 올바른 기준: 쿼리 패턴이 우선

실제 설계 순서는 다음과 같다.

1. **항상 동등 조건(`=`)으로 사용되는 컬럼**을 맨 앞에 배치
2. 동등 조건 컬럼이 여럿이면 그 안에서 선택도가 높은 것을 앞으로
3. **범위 조건 컬럼**을 그 뒤에
4. **ORDER BY 컬럼**을 범위 조건 뒤에 (또는 범위 조건 없으면 동등 조건 뒤에)

예시: 상품 목록 API, `category_id = 5 AND status = 'ON_SALE' ORDER BY created_at DESC`

```sql
-- 나쁜 순서 (선택도만 고려):
INDEX idx (created_at, status, category_id)

-- 좋은 순서 (동등 조건 먼저, ORDER BY 마지막):
INDEX idx (category_id, status, created_at)
```

`category_id = 5 AND status = 'ON_SALE'`로 정확히 범위를 좁힌 뒤 `created_at` 정렬을 인덱스 순서로 처리할 수 있어서 **filesort가 없어진다**.

---

## 커버링 인덱스 (Covering Index)

커버링 인덱스는 **쿼리가 필요로 하는 모든 컬럼이 인덱스에 포함**되어 있어서 실제 테이블 행을 읽을 필요가 없는 인덱스다.

InnoDB에서 테이블 데이터는 클러스터드 인덱스(PK 기준)에 저장된다. 세컨더리 인덱스의 리프 노드에는 인덱스 컬럼 값과 함께 **PK 값**이 저장된다. 커버링 인덱스가 아닐 때는 세컨더리 인덱스로 PK를 얻은 뒤 클러스터드 인덱스를 다시 조회한다(이중 조회, 랜덤 I/O).

커버링 인덱스가 되면 세컨더리 인덱스만 읽고 끝나므로 I/O가 절반 이하로 줄어든다.

### EXPLAIN에서 커버링 인덱스 확인

```sql
EXPLAIN SELECT user_id, status, created_at
FROM orders
WHERE user_id = 42 AND status = 'ACTIVE';
```

`Extra` 컬럼에 **`Using index`** 가 나오면 커버링 인덱스다. `Using index condition`은 다르다 — 인덱스를 활용하지만 테이블 접근이 있다는 의미다.

### 커버링 인덱스 설계 예시

```sql
-- orders 테이블의 자주 사용하는 목록 쿼리
SELECT order_id, user_id, status, total_amount, created_at
FROM orders
WHERE user_id = 42
ORDER BY created_at DESC
LIMIT 20;

-- 이 쿼리를 커버링 인덱스로 처리하려면:
CREATE INDEX idx_orders_covering
ON orders (user_id, created_at, status, total_amount);
-- order_id는 PK이므로 세컨더리 인덱스에 자동 포함
```

주의: SELECT에 컬럼이 많아질수록 인덱스 크기가 커지고 INSERT/UPDATE 비용도 증가한다. 커버링 인덱스는 **읽기가 압도적으로 많고** 자주 실행되는 쿼리에 적용해야 효과적이다.

---

## EXPLAIN으로 복합 인덱스 검증하기

이론을 알아도 실제로 쿼리 플랜을 보지 않으면 추측에 불과하다. EXPLAIN 출력에서 복합 인덱스와 관련된 핵심 컬럼은 다음과 같다.

| 컬럼 | 의미 |
|---|---|
| `type` | 접근 방식. `ref`, `range`는 인덱스 사용. `ALL`은 풀스캔 |
| `key` | 실제 선택된 인덱스 이름 |
| `key_len` | 사용된 인덱스 바이트 수. 몇 개 컬럼이 사용됐는지 역산 가능 |
| `ref` | 인덱스와 비교되는 값의 출처 |
| `rows` | 옵티마이저가 읽을 것으로 예상하는 행 수 |
| `Extra` | `Using index`(커버링), `Using filesort`(정렬 인덱스 미사용), `Using where`(테이블 필터) |

### key_len으로 컬럼 몇 개가 사용됐는지 확인

```sql
CREATE TABLE orders (
    order_id    BIGINT       NOT NULL,
    user_id     BIGINT       NOT NULL,   -- 8 bytes
    status      VARCHAR(20)  NOT NULL,   -- 20 * 4 + 2 = 82 bytes (utf8mb4, nullable아니면 +0)
    created_at  DATETIME     NOT NULL,   -- 8 bytes
    PRIMARY KEY (order_id),
    INDEX idx (user_id, status, created_at)
);

EXPLAIN SELECT * FROM orders WHERE user_id = 42 AND status = 'ACTIVE';
-- key_len = 8 + 82 = 90 → user_id + status 두 컬럼 사용

EXPLAIN SELECT * FROM orders WHERE user_id = 42;
-- key_len = 8 → user_id 하나만 사용
```

VARCHAR에서 NULL 허용이면 +1 바이트, 문자셋 utf8mb4이면 최대 4배이므로 `VARCHAR(20) NOT NULL utf8mb4` 는 `20*4 + 2(length prefix) = 82`다.

### EXPLAIN ANALYZE (MySQL 8.0.18+)

실행 계획뿐 아니라 실제 실행 통계까지 보여준다.

```sql
EXPLAIN ANALYZE
SELECT order_id, user_id, status
FROM orders
WHERE user_id = 42 AND status = 'ACTIVE'
ORDER BY created_at DESC
LIMIT 10;
```

출력 예:
```
-> Limit: 10 row(s)  (actual time=0.123..0.130 rows=10 loops=1)
    -> Index scan on orders using idx (reverse)  (cost=2.51 rows=10)
       (actual time=0.120..0.126 rows=10 loops=1)
```

`actual time`과 `rows`가 옵티마이저 예측과 크게 다르면 통계가 오래됐거나 인덱스 설계가 잘못된 것이다.

---

## 나쁜 예 vs 개선된 예

### 사례 1: 범위 조건 위치 실수

```sql
-- 나쁜 예
CREATE INDEX idx_bad ON orders (user_id, created_at, status);

SELECT * FROM orders
WHERE user_id = 42
  AND created_at >= '2025-01-01'
  AND status = 'ACTIVE';
-- created_at 범위 이후 status는 인덱스 활용 안 됨
-- Extra: Using index condition, Using where

-- 개선된 예
CREATE INDEX idx_good ON orders (user_id, status, created_at);
-- status가 동등 조건이므로 앞에, created_at 범위 조건은 뒤에
-- user_id + status로 범위를 좁힌 뒤 created_at으로 레인지 스캔
```

### 사례 2: ORDER BY를 고려하지 않은 설계

```sql
-- 나쁜 예: filesort 발생
CREATE INDEX idx_bad ON products (category_id, status);

SELECT product_id, name, price
FROM products
WHERE category_id = 10 AND status = 'ON_SALE'
ORDER BY price ASC;
-- Extra: Using index condition; Using filesort

-- 개선된 예: price를 인덱스에 포함
CREATE INDEX idx_good ON products (category_id, status, price);
-- Extra: Using index condition (filesort 없음)
```

### 사례 3: 커버링 인덱스 미활용

```sql
-- 나쁜 예: SELECT에 필요한 컬럼이 인덱스에 없어서 테이블 접근
CREATE INDEX idx_bad ON users (status);

SELECT user_id, email, status FROM users WHERE status = 'ACTIVE';
-- type: ref, Extra: Using where
-- user_id(PK)는 자동 포함되지만 email이 없어서 테이블 접근 필요

-- 개선된 예: email을 인덱스에 추가
CREATE INDEX idx_good ON users (status, email);
-- SELECT user_id, email, status → 모두 인덱스에 있음
-- Extra: Using index (커버링 인덱스!)
```

---

## MySQL 8 로컬 실습 환경

### Docker로 MySQL 8 실행

```bash
docker run --name mysql8-practice \
  -e MYSQL_ROOT_PASSWORD=practice \
  -e MYSQL_DATABASE=testdb \
  -p 3306:3306 \
  -d mysql:8.0
```

### 실습용 테이블 및 데이터 생성

```sql
USE testdb;

CREATE TABLE orders (
    order_id   BIGINT       NOT NULL AUTO_INCREMENT,
    user_id    BIGINT       NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
    total_amt  DECIMAL(12,2) NOT NULL DEFAULT 0,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id)
) ENGINE=InnoDB;

-- 100만 건 데이터 생성 (프로시저 이용)
DELIMITER $$
CREATE PROCEDURE gen_orders(IN n INT)
BEGIN
    DECLARE i INT DEFAULT 0;
    DECLARE statuses VARCHAR(100) DEFAULT 'PENDING,ACTIVE,COMPLETED,CANCELLED,REFUNDED';
    WHILE i < n DO
        INSERT INTO orders (user_id, status, total_amt, created_at)
        VALUES (
            FLOOR(RAND() * 10000) + 1,
            ELT(FLOOR(RAND() * 5) + 1, 'PENDING', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'REFUNDED'),
            ROUND(RAND() * 500000, 2),
            DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 365) DAY)
        );
        SET i = i + 1;
    END WHILE;
END$$
DELIMITER ;

CALL gen_orders(1000000);
ANALYZE TABLE orders;
```

### 인덱스 없이 기준선 측정

```sql
-- 기준선: 인덱스 없는 상태에서 실행 계획
EXPLAIN SELECT order_id, user_id, status, total_amt, created_at
FROM orders
WHERE user_id = 42 AND status = 'ACTIVE'
ORDER BY created_at DESC
LIMIT 20;
-- type: ALL, rows: ~1000000, Extra: Using where; Using filesort

-- 실제 시간 측정
SET profiling = 1;
SELECT order_id, user_id, status, total_amt, created_at
FROM orders
WHERE user_id = 42 AND status = 'ACTIVE'
ORDER BY created_at DESC LIMIT 20;
SHOW PROFILES;
```

### 복합 인덱스 추가 및 비교

```sql
-- 인덱스 추가
CREATE INDEX idx_user_status_created
ON orders (user_id, status, created_at);

-- 동일 쿼리 다시 실행
EXPLAIN SELECT order_id, user_id, status, total_amt, created_at
FROM orders
WHERE user_id = 42 AND status = 'ACTIVE'
ORDER BY created_at DESC
LIMIT 20;
-- type: ref, key: idx_user_status_created, Extra: Using index condition
-- (total_amt가 인덱스에 없어서 커버링 인덱스 아님)

-- 커버링 인덱스 시도
CREATE INDEX idx_covering
ON orders (user_id, status, created_at, total_amt);

EXPLAIN SELECT order_id, user_id, status, total_amt, created_at
FROM orders
WHERE user_id = 42 AND status = 'ACTIVE'
ORDER BY created_at DESC
LIMIT 20;
-- Extra: Using index (커버링 인덱스 성공)
```

### key_len으로 컬럼 사용 수 확인

```sql
-- user_id만 사용
EXPLAIN SELECT * FROM orders WHERE user_id = 42;
-- key_len: 8 (BIGINT 8바이트)

-- user_id + status 사용
EXPLAIN SELECT * FROM orders WHERE user_id = 42 AND status = 'ACTIVE';
-- key_len: 8 + (20*4 + 2) = 90
-- VARCHAR(20) NOT NULL utf8mb4: 20*4 + 2바이트(length prefix) = 82
-- 8 + 82 = 90

-- user_id + status + created_at 사용
EXPLAIN SELECT * FROM orders
WHERE user_id = 42 AND status = 'ACTIVE' AND created_at >= '2025-01-01';
-- key_len: 90 + 5 = 95  (DATETIME NOT NULL: 5바이트)
```

### 범위 조건 위치에 따른 차이 확인

```sql
-- 두 개의 인덱스를 만들어 비교
CREATE INDEX idx_range_middle
ON orders (user_id, created_at, status);  -- created_at 중간에

CREATE INDEX idx_range_last
ON orders (user_id, status, created_at);  -- created_at 마지막에

-- 동일 쿼리
EXPLAIN SELECT * FROM orders
WHERE user_id = 42
  AND status = 'ACTIVE'
  AND created_at >= '2025-01-01';

-- 옵티마이저가 idx_range_last를 선택하고 key_len이 더 크면 세 컬럼 활용
-- idx_range_middle 강제 사용시:
EXPLAIN SELECT * FROM orders USE INDEX (idx_range_middle)
WHERE user_id = 42
  AND status = 'ACTIVE'
  AND created_at >= '2025-01-01';
-- key_len이 작으면 status가 인덱스에서 사용 안 됨을 확인 가능
```

---

## 자주 저지르는 실수

**실수 1: GROUP BY나 ORDER BY 컬럼을 인덱스 설계에서 빠뜨린다**

쿼리에 `ORDER BY`가 있으면 마지막 컬럼이 ORDER BY 컬럼과 일치해야 filesort를 피할 수 있다. 특히 DESC 정렬이 필요하면 MySQL 8에서 `CREATE INDEX idx (a, b DESC)`처럼 내림차순 인덱스를 명시할 수 있다.

**실수 2: 인덱스 컬럼에 함수를 적용한다**

```sql
-- 인덱스 무력화
WHERE YEAR(created_at) = 2025
WHERE LOWER(email) = 'test@example.com'

-- 인덱스 활용
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01'
WHERE email = 'test@example.com'  -- 애플리케이션에서 소문자 변환 후 저장
```

**실수 3: 암묵적 타입 변환**

```sql
-- user_id가 BIGINT인데 문자열로 비교하면 인덱스를 못 탄다
WHERE user_id = '42'   -- 문자열 '42'를 BIGINT로 캐스팅 → 인덱스 무력화 가능

-- 반드시 타입을 맞춰서
WHERE user_id = 42
```

Java/Spring에서 `String`을 `Long` 타입 PK 컬럼에 바인딩할 때 이런 문제가 생길 수 있다. JPA에서 파라미터 타입을 정확히 지정해야 한다.

**실수 4: 인덱스를 많이 만들면 항상 좋다고 생각한다**

인덱스가 많을수록 INSERT/UPDATE/DELETE 시 모든 인덱스를 갱신해야 하므로 쓰기 비용이 증가한다. 또한 OPTIMIZE TABLE 시간과 버퍼 풀 사용량도 늘어난다. 인덱스는 읽기 패턴과 쓰기 빈도를 균형 있게 고려해서 꼭 필요한 것만 만들어야 한다.

**실수 5: FORCE INDEX를 남용한다**

`FORCE INDEX`는 옵티마이저를 무시하므로 통계가 갱신되거나 데이터 분포가 변하면 오히려 더 느려질 수 있다. 옵티마이저 선택이 잘못됐다면 `ANALYZE TABLE`로 통계를 갱신하거나 인덱스 자체를 재설계해야 한다.

---

## 시니어 백엔드 면접 답변 프레임

### 예상 질문: "복합 인덱스 설계 시 컬럼 순서를 어떻게 결정하나요?"

잘못된 답변: "선택도가 높은 컬럼을 앞에 놓습니다."

좋은 답변 구조:

> "컬럼 순서는 쿼리 패턴을 기준으로 결정합니다. 첫째로 동등 조건(`=`)으로 사용되는 컬럼을 앞에 배치합니다. 동등 조건 컬럼이 여럿이면 그 안에서 선택도가 높은 것을 앞으로 당깁니다. 둘째로 범위 조건 컬럼을 그 뒤에 배치합니다. 범위 조건 이후 컬럼은 인덱스 레인지 스캔에서 활용되지 않기 때문입니다. 마지막으로 ORDER BY 컬럼을 범위 조건 뒤에 배치하면 filesort를 피할 수 있습니다. 실무에서는 이 이론적 순서를 정한 뒤 EXPLAIN으로 key_len과 Extra 컬럼을 확인해서 실제로 의도한 대로 인덱스가 사용되는지 반드시 검증합니다."

### 예상 질문: "커버링 인덱스는 언제 사용하나요?"

> "커버링 인덱스는 읽기 빈도가 매우 높고 SELECT 컬럼이 고정적인 쿼리에 적용합니다. InnoDB에서 세컨더리 인덱스는 리프 노드에 PK를 포함하므로 SELECT 대상 컬럼이 모두 인덱스에 있으면 클러스터드 인덱스 재조회(랜덤 I/O)가 없어집니다. EXPLAIN의 Extra에 `Using index`가 나오면 커버링 인덱스가 적용된 것입니다. 다만 인덱스에 컬럼이 많아질수록 쓰기 비용과 인덱스 크기가 증가하므로, 트래픽이 높은 조회 API에 한정해 적용하고 쓰기 비용 증가를 모니터링해야 합니다."

### 예상 질문: "N+1 문제와 인덱스는 어떤 관계인가요?"

> "N+1 자체는 애플리케이션 레벨 문제이지만, 인덱스 설계가 N+1 임팩트를 크게 다르게 만듭니다. N+1로 N번의 쿼리가 발생할 때 각 쿼리가 인덱스를 타지 않으면 풀스캔이 N번 일어납니다. 반대로 FK 컬럼에 복합 인덱스가 있고 커버링 인덱스로 설계되면 N번의 쿼리가 모두 빠르게 처리됩니다. 따라서 페치 조인이나 배치 로딩으로 N+1을 해결하는 것이 우선이지만, 해결하기 어려운 케이스라면 인덱스 설계로 피해를 최소화할 수 있습니다."

---

## 체크리스트

- [ ] 쿼리의 WHERE 조건에서 동등 조건 컬럼을 인덱스 앞부분에 배치했는가
- [ ] 범위 조건 컬럼이 동등 조건 컬럼보다 뒤에 있는가
- [ ] ORDER BY 컬럼이 인덱스 마지막에 포함되어 filesort를 피하는가
- [ ] EXPLAIN의 `type`이 `ALL`이 아닌지 확인했는가
- [ ] `key_len`을 계산해서 의도한 컬럼 수만큼 인덱스가 사용되는지 확인했는가
- [ ] 커버링 인덱스가 필요한 쿼리에서 EXPLAIN Extra에 `Using index`가 나오는가
- [ ] 인덱스 컬럼에 함수 적용이나 암묵적 타입 변환이 없는가
- [ ] 인덱스 수가 테이블의 쓰기 빈도와 균형을 이루는가
- [ ] `ANALYZE TABLE`을 실행해서 통계가 최신 상태인가
- [ ] 운영 환경에 인덱스 추가 시 `ALTER TABLE ... ALGORITHM=INPLACE, LOCK=NONE`으로 온라인 DDL 사용 여부를 확인했는가
