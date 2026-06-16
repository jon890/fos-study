# [초안] MySQL 인덱스 설계 1페이지 복습: B+Tree·복합 인덱스·커버링 인덱스

## 이 문서의 역할

면접 직전 또는 운영 중 인덱스 리뷰가 필요할 때 5분 안에 훑을 수 있는 **압축 복습용 카드**다. 구조나 사례별 깊은 설명은 아래 상세 문서로 내려보내고, 여기서는 "어떤 원칙을 어떤 순서로 적용하는가"만 추린다.

- 구조와 인덱스 종류 전반: [b-tree-index.md](./b-tree-index.md)
- 좌측 접두사·범위 조건·정렬 최적화 심화: [composite-index.md](./composite-index.md)
- 실행 계획 진단: [explain-plan.md](./explain-plan.md)

같은 설명을 반복하지 않고, 본 문서는 **결정 트리 + 체크리스트 + 흔한 실수**에 집중한다.

---

## B+Tree 구조에서 잊지 말아야 할 3가지

1. **InnoDB의 모든 인덱스는 B+Tree고, 리프는 양방향 링크드 리스트로 연결된다.** 그래서 등호 검색뿐 아니라 `BETWEEN`, `>=`, `ORDER BY`가 같은 인덱스로 처리될 수 있다.
2. **PK = 클러스터드 인덱스 = 테이블 본문.** 세컨더리 인덱스 리프에는 PK 값이 들어 있고, 본문 접근은 PK 트리를 한 번 더 타는 **북마크 룩업**이 된다.
3. **트리 높이는 보통 3~4단계.** 즉 인덱스를 "탔는가/안 탔는가"가 보통 수십 배 차이를 만들고, "북마크 룩업이 사라졌는가(커버링)"가 그다음 큰 차이를 만든다.

이 세 사실에서 인덱스 설계의 우선순위가 결정된다 → **(1) 인덱스를 타게 만든다 → (2) 가능하면 커버링으로 만든다 → (3) 그래도 비용이 크면 PK 설계와 분포를 손본다.**

---

## 복합 인덱스 컬럼 순서 — 결정 트리

`INDEX idx (a, b, c)`의 리프는 `a` → 같은 `a` 내 `b` → 같은 `(a, b)` 내 `c` 순서로 정렬된다. 이 물리 순서가 모든 규칙의 근거다.

순서를 정할 때는 다음 트리를 따른다.

1. **등호(=) 조건 컬럼을 가장 앞에 둔다.**
   - 항상 `=`로 들어오는 컬럼은 인덱스의 첫 번째에 둘 때 가장 강하다(필터 + 이후 컬럼 정렬 모두 활용).
2. **그다음 `ORDER BY` 또는 `GROUP BY` 컬럼을 둔다.**
   - 정렬 방향이 인덱스와 일치하면 `Using filesort`가 사라진다.
3. **범위(`>`, `<`, `BETWEEN`, `LIKE 'abc%'`) 조건은 마지막에 둔다.**
   - 범위 조건이 등장한 컬럼 **이후의 컬럼**은 인덱스 정렬을 못 쓴다.
4. **선택도가 비슷하면 자주 쓰는 쿼리 패턴이 좌측 접두사로 정확히 떨어지게 둔다.**
   - 선택도(distinct 비율)는 결정타가 아니라 동률일 때의 타이브레이커다. "선택도 높은 컬럼을 무조건 앞에"라는 통념은 잘못이다.

### 작은 사례

```sql
-- 쿼리: 특정 사용자의 최근 주문을 상태별로 조회
SELECT id, total_amount
FROM orders
WHERE user_id = 42
  AND status = 'PAID'
  AND created_at >= '2026-04-01'
ORDER BY created_at DESC
LIMIT 20;
```

올바른 순서:

```sql
CREATE INDEX idx_orders_user_status_created
  ON orders (user_id, status, created_at);
```

- `user_id`(=) → `status`(=) → `created_at`(범위 + 정렬) 순으로 좌측 접두사가 정확히 맞는다.
- `created_at`이 마지막이라 범위 + `ORDER BY ... DESC LIMIT`이 인덱스만으로 처리된다.

---

## 커버링 인덱스 — "본문에 안 가도 되게" 만든다

`SELECT`에 필요한 모든 컬럼이 인덱스에 포함되면 **북마크 룩업이 사라진다.** EXPLAIN의 `Extra: Using index`가 나오면 커버링이다.

만드는 두 가지 방법:

1. 인덱스에 컬럼을 더 포함시킨다.
2. MySQL 8의 `INVISIBLE`/`INCLUDE` 대신 일반 인덱스 컬럼 끝에 추가한다(MySQL은 PostgreSQL처럼 `INCLUDE` 절이 없으므로, **정렬에 영향 주지 않는 위치(=인덱스 뒷부분)에 컬럼을 매단다**).

```sql
-- 위 쿼리를 커버링으로 만들고 싶다면 SELECT의 total_amount까지 인덱스에 포함
CREATE INDEX idx_orders_cover
  ON orders (user_id, status, created_at, total_amount);
```

이때 주의:

- **PK는 자동으로 들어 있다.** 세컨더리 인덱스 리프에는 PK가 항상 포함되므로 `id`만 필요한 경우라면 추가 컬럼 없이도 커버링이 된다.
- **쓰기 비용 트레이드오프가 따라온다.** 인덱스가 커지고, 인덱스 컬럼이 갱신될 때마다 인덱스 페이지가 분할된다. 고빈도 갱신 컬럼(예: `updated_at`, 카운터)을 커버링용으로 매다는 것은 위험하다.
- **`SELECT *`는 커버링이 거의 불가능하다.** 컬럼이 늘면 늘수록 커버링 인덱스의 의미가 약해진다.

---

## Bad vs Improved 짧은 사례 3개

### 사례 A — 좌측 접두사 무시

```sql
-- BAD: 자주 쓰는 쿼리는 WHERE status = ? AND user_id = ? 인데
CREATE INDEX idx_bad ON orders (status, user_id);
-- 쿼리: WHERE user_id = 42  → 인덱스 못 탐 (좌측 접두사 위반)
```

```sql
-- IMPROVED: 단일 user_id 쿼리도 자주 있다면 user_id를 앞에
CREATE INDEX idx_good ON orders (user_id, status);
```

### 사례 B — 범위 조건이 중간에 끼어 있는 경우

```sql
-- BAD: created_at이 가운데
CREATE INDEX idx_bad ON logs (service, created_at, level);
-- WHERE service = 'api' AND created_at >= ? AND level = 'ERROR'
-- → level은 인덱스로 못 거른다 (created_at 범위 이후라서)
```

```sql
-- IMPROVED: 범위는 가장 뒤로
CREATE INDEX idx_good ON logs (service, level, created_at);
```

### 사례 C — 북마크 룩업이 병목

```sql
-- BAD: 핫한 페이지네이션 쿼리에서 본문 접근이 많아 IO 폭주
SELECT id, title, summary
FROM articles
WHERE category_id = 5
ORDER BY published_at DESC
LIMIT 20;
-- INDEX (category_id, published_at) 만 있을 때
```

```sql
-- IMPROVED: 자주 보는 컬럼을 인덱스 끝에 매달아 커버링
CREATE INDEX idx_articles_cover
  ON articles (category_id, published_at, title, summary);
-- EXPLAIN Extra: Using index 확인
```

---

## 로컬 실습 환경 (MySQL 8)

```bash
docker run --name mysql8-idx \
  -e MYSQL_ROOT_PASSWORD=test \
  -e MYSQL_DATABASE=idx_lab \
  -p 3306:3306 -d mysql:8.0
```

```sql
USE idx_lab;

CREATE TABLE orders (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  status VARCHAR(16) NOT NULL,
  total_amount DECIMAL(12,2) NOT NULL,
  created_at DATETIME NOT NULL
) ENGINE=InnoDB;

-- 100만 건 더미 (간단판)
INSERT INTO orders (user_id, status, total_amount, created_at)
SELECT
  FLOOR(RAND()*10000),
  ELT(FLOOR(RAND()*3)+1, 'PAID', 'CANCELED', 'PENDING'),
  ROUND(RAND()*100000, 2),
  NOW() - INTERVAL FLOOR(RAND()*365) DAY
FROM information_schema.columns a, information_schema.columns b
LIMIT 1000000;
```

진단 흐름은 항상 같다.

```sql
EXPLAIN ANALYZE
SELECT id, total_amount
FROM orders
WHERE user_id = 42 AND status = 'PAID'
  AND created_at >= '2026-01-01'
ORDER BY created_at DESC
LIMIT 20;
```

확인할 것:

- `type` → `ref`/`range` 인지(아니면 `ALL`은 풀스캔)
- `key` → 의도한 인덱스를 탔는지
- `Extra` → `Using index`(커버링), `Using where`(필터 잔여), `Using filesort`(정렬 못 탐), `Using temporary`(그룹/조인 임시 테이블)

---

## 인덱스 설계 체크리스트

- [ ] PK는 **단조 증가 + 짧고 + 불변**인가? (AUTO_INCREMENT 또는 ULID/UUIDv7)
- [ ] 자주 쓰이는 핵심 쿼리 5~10개를 적어두고, 그 쿼리가 어떤 인덱스를 탈지 의도적으로 매핑했는가?
- [ ] 복합 인덱스 컬럼 순서는 **등호 → 정렬/그룹 → 범위** 순인가?
- [ ] 좌측 접두사 규칙을 위반하는 쿼리가 남아 있지 않은가?
- [ ] 핫한 조회 쿼리가 **커버링 인덱스**로 만들어질 여지가 있는가? (`Using index` 노렸는가)
- [ ] 인덱스 추가 시 **쓰기 비용**(INSERT/UPDATE 인덱스 갱신)을 감내할 만한가?
- [ ] 인덱스 컬럼에 함수/형변환을 씌우는 쿼리는 없는가? (`WHERE DATE(created_at) = ?` 같은 패턴)
- [ ] `IN (...)` 리스트 크기, `OR` 조건, `LIKE '%abc%'` 같은 인덱스 무력화 패턴이 있는가?
- [ ] EXPLAIN ANALYZE로 `type`, `key`, `rows`, `Extra`를 실제로 확인했는가?
- [ ] 사용되지 않는 인덱스(`sys.schema_unused_indexes`)를 주기적으로 정리하는가?

---

## 흔한 실수 패턴

- 단일 컬럼 인덱스를 여러 개 만들어 두고 옵티마이저가 알아서 합쳐줄 거라 기대한다. (Index Merge는 비용이 큰 마지막 카드다.)
- "선택도 높은 컬럼을 무조건 앞에" 규칙을 맹신한다. 실제로는 **쿼리 형태 + 등호/범위 구분**이 더 중요하다.
- `created_at` 같은 범위/정렬 컬럼을 인덱스 가운데 끼워 넣는다.
- 모든 검색 쿼리에 같은 컬럼들이 등장한다고 해서 그 컬럼들을 전부 한 인덱스에 욱여넣는다 (오버스펙 + 쓰기 비용 폭증).
- 인덱스 컬럼에 함수를 씌운 채로 조회한다: `WHERE DATE(created_at) = '2026-04-30'` → MySQL 8의 함수 인덱스가 없으면 인덱스를 못 탄다.
- `LIKE '%foo'` 또는 `LIKE '%foo%'` 처럼 좌측 와일드카드를 쓴다 (좌측 접두사가 깨져 인덱스 무력화).
- `OR` 로 다른 컬럼 조건을 묶는다: `WHERE a = 1 OR b = 2` → 보통 풀스캔. `UNION ALL`로 분리하는 편이 빠르다.
- `SELECT *`로 커버링 인덱스를 무력화한다. 필요한 컬럼만 명시.
- `ORDER BY` 방향과 인덱스 방향이 달라 `Using filesort`가 발생한다(특히 컬럼별 ASC/DESC가 섞일 때 — MySQL 8의 Descending Index 검토).
- PK를 UUIDv4로 잡아 페이지 분할이 잦아진다. 단조 증가 PK 또는 ULID/UUIDv7로 교체.
- 운영 중 `ALTER TABLE ADD INDEX`를 락 고려 없이 친다. 큰 테이블은 `ALGORITHM=INPLACE, LOCK=NONE` 가능 여부와 온라인 DDL 비용을 사전 확인해야 한다.

---

## 면접 답변 프레이밍

질문이 "MySQL 인덱스 설계는 어떻게 접근하십니까?"라면 다음 4단으로 정리한다.

1. **구조부터 잡는다.** "InnoDB 인덱스는 B+Tree이고 PK가 클러스터드라, 세컨더리 인덱스는 기본적으로 PK를 한 번 더 타는 비용이 있습니다. 그래서 저는 핫한 쿼리에 한해 커버링 인덱스를 우선 검토합니다."
2. **컬럼 순서 원칙을 말한다.** "복합 인덱스는 등호 조건 → 정렬/그룹 → 범위 조건 순으로 둡니다. 선택도는 쿼리 형태가 같을 때의 타이브레이커일 뿐, 그 자체가 1순위 기준은 아닙니다."
3. **트레이드오프를 짚는다.** "인덱스를 추가할 때마다 쓰기 비용과 디스크/버퍼 풀 비용이 늘어납니다. 그래서 저는 EXPLAIN ANALYZE로 실제 효과를 확인하고, `sys.schema_unused_indexes` 같은 진단으로 사용되지 않는 인덱스는 주기적으로 정리합니다."
4. **실제 사례로 닫는다.** "예를 들어 페이지네이션 쿼리에서 북마크 룩업이 병목인 걸 EXPLAIN의 `Extra` 컬럼으로 확인하고, 정렬 컬럼 뒤에 표시용 컬럼을 매달아 커버링 인덱스로 만들어 응답 시간을 줄인 경험이 있습니다."

이 4단 구조면 follow-up이 어떤 방향으로 와도(범위 조건, 함수 인덱스, 페이지 분할, Index Merge 등) 자연스럽게 이어붙일 수 있다.
