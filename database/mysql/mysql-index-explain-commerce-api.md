# [초안] 커머스 API를 위한 MySQL 인덱스와 EXPLAIN 실전 가이드

## 왜 이 주제가 중요한가

커머스 백엔드에서 가장 자주 마주치는 성능 문제는 거의 항상 인덱스와 실행 계획에서 출발한다. 주문 목록, 회원 쿠폰, 매장 메뉴처럼 조회 패턴이 정해져 있는 화면일수록 트래픽이 누적되고, 단일 쿼리의 비효율이 그대로 슬로우 쿼리 로그와 P99 응답 시간에 누적된다. CJ푸드빌처럼 매장/회원/메뉴/주문이 얽힌 도메인에서는 한 화면에서 수십만 row를 스캔하는 비효율이 손쉽게 만들어지고, 새벽 배치/이벤트 트래픽에서 한꺼번에 터진다.

시니어 백엔드 면접에서 인덱스를 묻는 이유는 단순한 암기 검증이 아니다. 면접관은 보통 이런 흐름으로 문제를 본다.

- 어떤 쿼리가 느린지 어떻게 알아냈는가 (slow query log, APM, RDS Performance Insights)
- `EXPLAIN`을 어떻게 읽는가 (type, key, rows, Extra의 의미)
- 왜 그 인덱스가 안 탔는가 (leftmost prefix 위반, 함수 적용, 형 변환, 낮은 cardinality)
- 어떤 인덱스를 새로 추가할 것인가 (복합 인덱스, 커버링 인덱스, 정렬/페이지네이션 고려)
- 인덱스를 추가하면 어떤 부작용이 있는가 (쓰기 비용, 디스크, 락, 옵티마이저 오판)

이 문서는 이 다섯 가지를 커머스 API 시나리오 위에서 실제 SQL과 함께 풀어낸다. 인덱스 자체의 자료구조와 컬럼 순서 결정 트리, EXPLAIN 컬럼 해석은 같은 디렉터리의 [b-tree-index.md](./b-tree-index.md), [composite-index.md](./composite-index.md), [explain-plan.md](./explain-plan.md)에 두고, 여기서는 "현장에서 어떻게 진단하고 어떻게 고치는가"에 집중한다. 면접 직전 1페이지 리뷰는 [review-index-design.md](./review-index-design.md)를 펼친다.

## 핵심 개념을 다시 정리

### B+Tree 인덱스의 핵심 성질

InnoDB의 일반 인덱스는 모두 B+Tree 위에 올라간다. 실무 의사결정을 위해 잊지 말아야 할 성질은 세 가지다.

- 정렬된 키 순서로 조회/range 스캔이 효율적이다.
- 복합 인덱스 `(a, b, c)`는 사실상 `a` → `(a, b)` → `(a, b, c)` 순서로만 prefix 검색이 가능하다 (leftmost prefix).
- 리프 노드에는 클러스터드 인덱스(보통 PK)에 대한 포인터가 들어 있고, 세컨더리 인덱스에서 PK가 아닌 컬럼이 필요하면 다시 클러스터드 인덱스로 점프한다 (lookup, random I/O).

여기서 "커버링 인덱스"라는 개념이 나온다. 쿼리가 필요한 모든 컬럼이 인덱스 안에 이미 들어 있어서 클러스터드 인덱스로 추가 lookup 없이 답을 만들 수 있는 경우다. `EXPLAIN`에서 `Extra: Using index`로 표시된다.

### Cardinality와 선택도

cardinality는 인덱스 컬럼의 distinct 값 개수에 대한 추정치다. 옵티마이저는 통계를 보고 "이 인덱스를 타면 몇 row를 읽을지" 추정한다. cardinality가 낮은 컬럼(예: `is_deleted`, `status`)을 인덱스 맨 앞에 두면 오히려 비효율이다. 반대로 cardinality가 매우 높은 컬럼(예: `member_id`, `order_id`)이 prefix로 들어가야 효과가 크다.

### EXPLAIN의 핵심 필드

| 필드 | 무엇을 보는가 |
|------|---------------|
| `type` | `const`, `eq_ref`, `ref`, `range`, `index`, `ALL` 순으로 좋다 → 나쁘다 |
| `key` | 실제로 선택된 인덱스 |
| `key_len` | 인덱스에서 실제 사용된 prefix 바이트 수 (복합 인덱스 어디까지 탔는지 추정 가능) |
| `rows` | 옵티마이저 추정 row 수, 정확한 값 아님 |
| `filtered` | WHERE 추가 조건으로 남는 비율(%) |
| `Extra` | `Using index`(커버링), `Using where`, `Using filesort`, `Using temporary`, `Using index condition`(ICP) 등 |

이 중 면접에서는 `type`, `key`, `Extra` 세 가지를 엮어서 읽는 능력이 가장 자주 검증된다.

## 커머스 API에서 자주 보는 쿼리 패턴

여기서부터는 MySQL 8.0 기준으로 실행 가능한 예제를 깐다. 도메인은 일반화된 커머스/F&B 시나리오로 둔다.

### 스키마

```sql
CREATE TABLE members (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  email        VARCHAR(120) NOT NULL,
  status       VARCHAR(20)  NOT NULL,
  created_at   DATETIME(6)  NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_members_email (email)
) ENGINE=InnoDB;

CREATE TABLE stores (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  brand_code   VARCHAR(20)  NOT NULL,
  name         VARCHAR(120) NOT NULL,
  region_code  VARCHAR(20)  NOT NULL,
  is_active    TINYINT(1)   NOT NULL,
  PRIMARY KEY (id),
  KEY idx_stores_brand (brand_code, region_code)
) ENGINE=InnoDB;

CREATE TABLE menus (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  store_id     BIGINT       NOT NULL,
  category     VARCHAR(40)  NOT NULL,
  name         VARCHAR(120) NOT NULL,
  price        INT          NOT NULL,
  is_sold_out  TINYINT(1)   NOT NULL,
  display_order INT         NOT NULL,
  PRIMARY KEY (id),
  KEY idx_menus_store (store_id)
) ENGINE=InnoDB;

CREATE TABLE orders (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  member_id    BIGINT       NOT NULL,
  store_id     BIGINT       NOT NULL,
  status       VARCHAR(20)  NOT NULL,
  total_price  INT          NOT NULL,
  created_at   DATETIME(6)  NOT NULL,
  PRIMARY KEY (id),
  KEY idx_orders_member_created (member_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE member_coupons (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  member_id    BIGINT       NOT NULL,
  coupon_code  VARCHAR(40)  NOT NULL,
  status       VARCHAR(20)  NOT NULL,
  expires_at   DATETIME(6)  NOT NULL,
  PRIMARY KEY (id),
  KEY idx_mc_member_status (member_id, status, expires_at)
) ENGINE=InnoDB;
```

데모용 더미 데이터는 약 100만 건 단위 `orders`, 50만 건의 `member_coupons`를 가정한다. 실제 학습 시에는 아래 "로컬 실습 환경" 섹션에서 데이터를 채우는 방법을 다룬다.

### 사례 1. 회원의 주문 목록 페이지네이션

API 요구사항: "내 주문 목록을 최신순으로 20건씩 페이지로 본다."

처음 자주 쓰는 SQL.

```sql
SELECT id, store_id, status, total_price, created_at
FROM orders
WHERE member_id = ?
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;
```

`idx_orders_member_created (member_id, created_at)`이 있으면 어떤 일이 일어나는가. `EXPLAIN`을 보자.

```text
type: ref
key: idx_orders_member_created
key_len: 8
rows: 약 1500
Extra: Backward index scan
```

`member_id`로 ref 검색을 하고 `created_at`이 인덱스에 이미 정렬돼 있으므로 정렬 없이 끝난다. MySQL 8.0부터 descending index와 backward index scan을 잘 활용하므로 `ORDER BY created_at DESC`도 인덱스로 처리된다.

#### 페이지가 깊어질 때의 함정

문제는 OFFSET이 커질 때다.

```sql
SELECT id, store_id, status, total_price, created_at
FROM orders
WHERE member_id = ?
ORDER BY created_at DESC
LIMIT 20 OFFSET 10000;
```

이 쿼리는 인덱스를 타더라도 옵티마이저가 10,020 row를 거꾸로 따라가서 10,000개를 버려야 한다. `EXPLAIN`은 그대로 좋아 보이지만 실제 실행 시간은 page가 깊어질수록 선형으로 늘어난다. 흔히 "OFFSET pagination 안티패턴"이라고 부른다.

개선 패턴은 cursor 방식이다.

```sql
SELECT id, store_id, status, total_price, created_at
FROM orders
WHERE member_id = ?
  AND (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

`(created_at, id)` 튜플을 cursor로 두고 매 페이지마다 마지막 row의 값으로 다음 페이지를 끊는다. 인덱스가 `(member_id, created_at)`이라면 같은 `member_id` 안에서 `created_at` 정렬이 이미 보장돼 있으므로 cursor 비교만으로 page가 깊어져도 매번 20건만 본다.

면접에서 한 번에 답할 흐름은 이렇다. "OFFSET이 커지면 인덱스 자체는 타도 OFFSET만큼의 row를 거쳐야 해서 P99가 무너집니다. cursor 기반 keyset pagination으로 바꿔서 OFFSET을 제거합니다."

### 사례 2. 회원 쿠폰 조회 — leftmost prefix와 cardinality

요구사항: "사용 가능한 쿠폰만 만료 임박순으로 가져온다."

```sql
SELECT id, coupon_code, expires_at
FROM member_coupons
WHERE member_id = ?
  AND status = 'AVAILABLE'
  AND expires_at >= NOW()
ORDER BY expires_at ASC
LIMIT 50;
```

`idx_mc_member_status (member_id, status, expires_at)`이 있다. 이 인덱스가 잘 동작하는 이유는 다음과 같다.

- `member_id`로 좁히면 회원 한 명의 쿠폰만 남는다 (cardinality 매우 높음).
- 그 안에서 `status = 'AVAILABLE'`로 한 번 더 좁힌다.
- 같은 `(member_id, status)` 안에서 `expires_at`이 정렬돼 있으므로 `expires_at >= NOW()`는 range 스캔으로 끊고, `ORDER BY expires_at`은 정렬 비용 없이 끝난다.

만약 인덱스를 `(status, member_id, expires_at)`로 잘못 잡으면 어떻게 되는가. `status`는 cardinality가 매우 낮다(보통 3\~4종류). 회원 한 명의 쿠폰만 보고 싶은데 인덱스의 첫 키가 `status`이므로 그 status에 해당하는 모든 회원의 모든 쿠폰을 큰 범위로 스캔하게 된다. cardinality가 낮은 컬럼을 prefix로 두지 말 것이라는 일반론은 이 시나리오를 통해 실감할 수 있다.

#### `expires_at`에 함수를 씌우는 안티패턴

```sql
WHERE DATE(expires_at) >= CURDATE()
```

이 식은 `expires_at` 값에 함수를 씌우기 때문에 인덱스가 무력화된다 (MySQL 8.0의 functional index를 별도로 추가하지 않는 한). 개선은 단순하다.

```sql
WHERE expires_at >= CURDATE()
```

비슷한 함정으로 `WHERE LEFT(member_id, ...)`, `WHERE CAST(member_id AS CHAR) = ?` 같은 함수/형 변환이 있다. 컬럼은 가능하면 raw 그대로 두고 비교 우측만 가공하는 것이 원칙이다.

### 사례 3. 매장 메뉴 목록 — 커버링 인덱스로 lookup 제거

요구사항: "매장 화면에서 카테고리별 메뉴를 표시 순서대로 가져온다."

```sql
SELECT id, name, price, is_sold_out
FROM menus
WHERE store_id = ?
  AND category = ?
ORDER BY display_order ASC;
```

현재 인덱스가 `idx_menus_store (store_id)`만 있다면 `EXPLAIN`은 보통 이렇게 나온다.

```text
type: ref
key: idx_menus_store
rows: 매장당 메뉴 수 전체
Extra: Using where; Using filesort
```

`store_id`만으로 ref 검색은 되지만 카테고리 필터는 row를 다 읽고 나서 `Using where`로 거른다. 게다가 `display_order` 정렬은 인덱스에 없으므로 `Using filesort`가 붙는다. 메뉴 수가 매장당 200\~500개로 늘어나면 화면 응답이 들쑥날쑥해진다.

개선 인덱스는 다음과 같다.

```sql
ALTER TABLE menus
  ADD KEY idx_menus_store_cat_order (store_id, category, display_order);
```

이 상태에서 EXPLAIN.

```text
type: ref
key: idx_menus_store_cat_order
Extra: Using index condition
```

`(store_id, category)`로 ref하고, 같은 prefix 안에서 `display_order`가 이미 정렬돼 있으므로 filesort가 사라진다. 필요하다면 `name`, `price`, `is_sold_out`까지 인덱스에 포함시키는 진짜 covering index도 검토할 수 있다. 다만 모든 컬럼을 인덱스에 박는 것은 쓰기 비용을 키우고 디스크를 키운다. "조회 빈도가 정말 높은 화면에 한해 covering"이 실무 기준이다.

### 사례 4. 다중 조건 검색 — range 조건과 인덱스 사용 한계

```sql
SELECT id, member_id, store_id, status, total_price, created_at
FROM orders
WHERE store_id = ?
  AND created_at BETWEEN ? AND ?
  AND status = 'PAID'
ORDER BY created_at DESC
LIMIT 100;
```

여기서 자주 헷갈리는 규칙이 있다. **B+Tree 인덱스에서 첫 range 조건이 나온 컬럼 이후로는 같은 인덱스의 뒤쪽 컬럼이 equality여도 동등 비교 효과를 다 내지 못한다.**

가령 `(store_id, created_at, status)` 인덱스가 있다고 하자. `store_id = ?` (eq) → `created_at BETWEEN`이 range로 잡히는 순간, 인덱스의 다음 컬럼인 `status`는 인덱스 트리 자체로는 더 좁히지 못한다. 옵티마이저는 보통 ICP(Index Condition Pushdown)로 `status` 비교를 인덱스 레벨에서 푸시다운해 row 가져오기 비용은 줄이지만, 인덱스 트리에서 직접 좁힌 효과만큼은 아니다.

이 시나리오에서는 둘 중 하나를 고른다.

- `(store_id, status, created_at)` 인덱스를 쓴다. 그러면 eq, eq, range 순으로 가장 효율적이다. status별 성격이 비슷한 매장 분석 쿼리에 잘 맞는다.
- 화면이 status를 거의 항상 PAID로만 본다면 `(store_id, created_at)` 그대로 두고 status는 `Using where`로 후처리해도 충분하다. 인덱스 추가 비용 대비 이득이 미미할 수 있다.

면접에서 강조해야 할 포인트: **"왜 인덱스를 추가하지 않았는가"도 설계 결정의 일부다.** 인덱스를 늘리면 INSERT/UPDATE/DELETE 비용이 늘고, 쓰기 트래픽이 큰 테이블에서는 락과 페이지 분할 비용도 누적된다.

### 사례 5. 주문 + 매장 JOIN — driving 테이블과 인덱스 매칭

요구사항: "특정 브랜드의 매장에서 어제 들어온 결제 완료 주문을 보여준다."

```sql
SELECT o.id, o.member_id, o.total_price, s.name AS store_name
FROM orders o
JOIN stores s ON s.id = o.store_id
WHERE s.brand_code = ?
  AND o.status = 'PAID'
  AND o.created_at >= ?
  AND o.created_at <  ?
ORDER BY o.created_at DESC
LIMIT 200;
```

JOIN 쿼리에서 가장 먼저 봐야 할 것은 **driving 테이블이 누구인가**다. 옵티마이저는 보통 결과 row 수가 작을 것 같은 쪽을 driving으로 잡는다. 브랜드별 매장 수가 보통 수십\~수백 개라면 `stores`가 driving이 되어 brand_code로 좁히고, 각 매장당 주문을 lookup 하는 nested loop join이 만들어진다.

이 모양에서 필요한 인덱스 두 개를 분리해서 본다.

- `stores`: `KEY (brand_code, region_code)` — 이미 있다. driving 측 필터로 잘 작동한다.
- `orders`: 매장당 lookup이므로 `(store_id, status, created_at)`이 가장 효율적이다. `store_id`로 좁히고 같은 prefix에서 `status` eq, `created_at` range가 그대로 떨어진다.

```sql
ALTER TABLE orders
  ADD KEY idx_orders_store_status_created (store_id, status, created_at);
```

EXPLAIN을 찍으면 보통 이런 모양이 나온다.

```text
1 SIMPLE s  type=ref  key=idx_stores_brand        rows=120
1 SIMPLE o  type=ref  key=idx_orders_store_status_created
            Extra=Using index condition
```

흔한 함정 두 가지를 짚는다.

- driving이 뒤집히는 경우 — `WHERE` 조건이 `orders` 쪽으로 강하게 좁히면(예: 특정 매장 1개) `orders`가 driving이 되고 `stores`는 PK lookup이 된다. `EXPLAIN`의 `id`/`select_type` 순서가 매번 같다고 가정하지 말고 새로 본다.
- JOIN 컬럼 타입 불일치 — `orders.store_id BIGINT` vs `stores.id BIGINT UNSIGNED`처럼 signed/unsigned가 어긋나면 암시적 형 변환으로 인덱스 효율이 떨어진다. JOIN 키는 데이터 타입과 collation까지 맞춘다.

면접에서 답할 때는 "driving 테이블을 먼저 식별하고, driven 쪽 인덱스를 lookup 패턴에 맞게 설계합니다. JOIN 컬럼 타입과 collation 불일치는 EXPLAIN의 `ref` 컬럼 값이나 `Using join buffer`로 잡힙니다." 정도가 무난하다.

## EXPLAIN을 읽는 순서 (면접용)

낯선 슬로우 쿼리를 받았을 때 항상 같은 순서로 본다.

1. `type` — `ALL`이나 `index`면 풀스캔/풀 인덱스 스캔이다. 가장 먼저 잡아야 한다.
2. `key`와 `key_len` — 의도한 인덱스가 실제로 선택됐는가. 복합 인덱스 어디까지 탔는가.
3. `rows` × `filtered` — 옵티마이저가 추정한 실제 처리량. 한 자릿수\~수백이면 보통 OK, 수십만이면 의심.
4. `Extra` — `Using filesort`, `Using temporary`는 보통 정렬/그룹 처리 비효율, `Using index`는 좋은 신호, `Using index condition`은 ICP가 적용됐다는 뜻.
5. JOIN이 있으면 driving 테이블이 무엇인지, 각 테이블의 `type`이 무엇인지 본다.
6. 의심이 가면 `EXPLAIN ANALYZE`로 실제 실행 시간을 본다 (MySQL 8.0.18+).

이 흐름을 답할 때, "느리면 무조건 인덱스를 추가한다"는 식으로 말하지 않는다. "현재 인덱스를 왜 안 탔는지부터 설명하고, leftmost prefix 위반인지, 함수/형 변환인지, cardinality가 낮은 prefix인지 진단합니다"가 시니어 톤이다.

## Bad vs Improved 예제 모음

### (Bad) status 먼저 거는 인덱스

```sql
KEY idx_bad (status, member_id)
```

`status`는 cardinality가 매우 낮아 회원 단위 조회에서 큰 범위를 읽게 된다. 회원 중심 화면이면 `member_id`가 prefix.

### (Bad) 컬럼에 함수

```sql
WHERE DATE(created_at) = ?
```

→ Improved.

```sql
WHERE created_at >= ? AND created_at < ? + INTERVAL 1 DAY
```

### (Bad) 큰 OFFSET 페이지네이션

```sql
ORDER BY created_at DESC LIMIT 20 OFFSET 100000
```

→ Improved (keyset).

```sql
WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC LIMIT 20
```

### (Bad) IN 절에 NULL 섞임

```sql
WHERE status IN ('PAID', NULL)
```

`NULL`은 IN으로 매칭되지 않는다. NULL 처리는 `IS NULL`로 분리한다.

### (Bad) ORDER BY와 인덱스 정렬 방향 불일치

`(member_id, created_at ASC)` 인덱스인데 `ORDER BY member_id ASC, created_at DESC`처럼 섞으면 MySQL 8.0의 descending 인덱스를 명시적으로 만들지 않는 한 filesort가 발생할 수 있다. 정렬 키 방향이 자주 섞이면 `(member_id ASC, created_at DESC)`처럼 descending 인덱스를 만들어 둔다.

## 로컬 실습 환경

다음 환경에서 그대로 따라할 수 있다.

```bash
docker run --name mysql8-study \
  -e MYSQL_ROOT_PASSWORD=secret \
  -p 3306:3306 \
  -d mysql:8.0
```

접속.

```bash
docker exec -it mysql8-study mysql -uroot -psecret
```

스키마 생성 후 더미 데이터를 채운다. 빠르게 100만 건을 만들고 싶다면 재귀 CTE를 쓴다.

```sql
SET cte_max_recursion_depth = 2000000;

INSERT INTO members (email, status, created_at)
SELECT CONCAT('m', n, '@ex.com'),
       'ACTIVE',
       NOW() - INTERVAL FLOOR(RAND() * 365) DAY
FROM (
  WITH RECURSIVE seq(n) AS (
    SELECT 1 UNION ALL SELECT n+1 FROM seq WHERE n < 100000
  )
  SELECT n FROM seq
) t;

INSERT INTO orders (member_id, store_id, status, total_price, created_at)
SELECT FLOOR(1 + RAND() * 100000),
       FLOOR(1 + RAND() * 500),
       ELT(FLOOR(1 + RAND() * 4), 'PAID', 'CANCELED', 'REFUNDED', 'PENDING'),
       FLOOR(5000 + RAND() * 50000),
       NOW() - INTERVAL FLOOR(RAND() * 180) DAY
FROM (
  WITH RECURSIVE seq(n) AS (
    SELECT 1 UNION ALL SELECT n+1 FROM seq WHERE n < 1000000
  )
  SELECT n FROM seq
) t;
```

이후 통계 갱신.

```sql
ANALYZE TABLE orders, members, member_coupons, menus, stores;
```

## 직접 돌려볼 예제

각 EXPLAIN을 직접 찍어 비교한다.

```sql
EXPLAIN
SELECT id FROM orders
WHERE member_id = 12345
ORDER BY created_at DESC LIMIT 20;

EXPLAIN
SELECT id FROM orders
WHERE member_id = 12345
ORDER BY created_at DESC LIMIT 20 OFFSET 100000;

EXPLAIN
SELECT id FROM orders
WHERE member_id = 12345
  AND (created_at, id) < ('2026-04-01 00:00:00', 9999999)
ORDER BY created_at DESC, id DESC LIMIT 20;

EXPLAIN
SELECT id, name, price FROM menus
WHERE store_id = 42 AND category = 'COFFEE'
ORDER BY display_order;

ALTER TABLE menus
  ADD KEY idx_menus_store_cat_order (store_id, category, display_order);

EXPLAIN
SELECT id, name, price FROM menus
WHERE store_id = 42 AND category = 'COFFEE'
ORDER BY display_order;
```

같은 쿼리에 대해 인덱스 추가 전후의 `type`, `key`, `Extra`가 어떻게 변하는지 직접 비교한다. 가능하면 `EXPLAIN ANALYZE`까지 같이 본다.

```sql
EXPLAIN ANALYZE
SELECT id FROM member_coupons
WHERE member_id = 88
  AND status = 'AVAILABLE'
  AND expires_at >= NOW()
ORDER BY expires_at ASC LIMIT 50;
```

`actual time=...`에 첫 row까지 걸린 시간과 마지막 row까지 걸린 시간이 찍힌다. 옵티마이저 추정 `rows`와 실제 `actual rows`가 크게 차이 나면 통계 갱신(`ANALYZE TABLE`)이나 히스토그램(`ANALYZE TABLE ... UPDATE HISTOGRAM`)을 검토한다.

## 슬로우 쿼리 운영 측면

학습용 EXPLAIN과 별개로, 실제 운영에서는 다음 흐름으로 인덱스 후보를 잡는다.

- `slow_query_log = ON`, `long_query_time = 0.3` 정도로 임계 낮춰 표본 수집.
- `mysqldumpslow -s t -t 20 slow.log` 또는 `pt-query-digest`로 합산 시간 기준 상위 쿼리 추출.
- 상위 쿼리 각각에 대해 `EXPLAIN`/`EXPLAIN ANALYZE`.
- 새 인덱스 후보를 검토할 때는 운영 트래픽 시간대를 피해 staging에서 추가하고, 추가 후 INSERT/UPDATE 지표가 바뀌는지 확인.
- 사용되지 않는 인덱스는 `sys.schema_unused_indexes` 뷰로 점검.
- 옵티마이저 추정 `rows`가 실제와 크게 어긋나면 `ANALYZE TABLE ... UPDATE HISTOGRAM ON column WITH N BUCKETS`로 히스토그램을 추가/갱신해 분포 정보를 보강.

이 운영 흐름을 면접에서 같이 이야기하면, "인덱스 이론은 아는데 실제로 적용해본 사람"이라는 신호가 강하게 전달된다.

## 면접 답변 프레이밍

EXPLAIN/인덱스 질문이 들어오면 다음 4스텝으로 답한다.

1. 문제 정의 — 어떤 화면/API가 느렸고, 어떤 지표(P95/P99, slow query log)에서 잡았는지.
2. 진단 — `EXPLAIN`을 보고 `type`, `key`, `Extra` 중 어떤 신호가 문제였는지. cardinality, leftmost prefix, 함수 적용, OFFSET 깊이 같은 구체 원인을 말한다.
3. 처리 — 인덱스 추가/변경, 쿼리 리라이팅, keyset pagination, covering index 중 무엇을 적용했고 왜 그것을 골랐는지.
4. trade-off — 추가한 인덱스의 쓰기 비용, 통계 영향, 인덱스 개수 관리. "안 만든 인덱스"에 대한 판단도 같이 말한다.

이 4스텝은 거의 모든 DB 성능 질문의 답을 만들어낸다. 추상적인 "인덱스를 잘 써야 합니다" 톤을 피하고, 위 시나리오 중 하나를 자기 경험처럼 구체적으로 끌어올 수 있도록 준비한다.

자기 경험으로 연결할 때는 "주문 목록 OFFSET pagination을 cursor 방식으로 바꿔 P99를 N% 개선했다", "쿠폰 조회 인덱스 prefix를 status에서 member\_id로 바꿔 평균 응답 시간을 줄였다"처럼 정량 표현 한 줄을 꼭 포함시킨다. 숫자가 없으면 면접관은 단순 학습으로 받아들인다.

## 체크리스트

- 슬로우 쿼리는 `slow_query_log` + `pt-query-digest`로 합산 시간 기준 상위부터 본다.
- `EXPLAIN`은 `type → key → key_len → rows × filtered → Extra` 순으로 읽는다.
- 복합 인덱스는 cardinality 높은 컬럼을 prefix에 둔다.
- range 조건이 들어가는 순간 그 뒤 컬럼은 인덱스 트리로 더 좁히지 못한다.
- 컬럼에 함수/형 변환을 걸지 않는다. 가공은 우측 값에 한다.
- 큰 OFFSET pagination은 keyset(cursor) 방식으로 바꾼다.
- 정렬/그룹 컬럼이 인덱스 끝에 들어가도록 설계해 `Using filesort`를 제거한다.
- 정말 자주 호출되는 화면에 한해 covering index를 검토한다.
- 인덱스를 추가할 때마다 쓰기 비용·디스크·옵티마이저 영향까지 같이 평가한다.
- JOIN 쿼리는 driving 테이블 식별 → driven 쪽 lookup 인덱스 설계 순으로 본다. JOIN 키의 타입·collation 일치를 확인한다.
- 추가 후 `ANALYZE TABLE`로 통계를 갱신하고, `sys.schema_unused_indexes`로 죽은 인덱스를 정기 점검한다.
- 면접에서는 "왜 인덱스를 안 만들었는가"도 답할 수 있어야 한다.
