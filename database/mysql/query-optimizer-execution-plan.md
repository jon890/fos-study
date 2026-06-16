# [초안] MySQL 옵티마이저와 실행 계획 생성 — 비용 모델·통계·optimizer_trace 실전 가이드

## 왜 알아야 하는가

대부분의 백엔드 개발자는 EXPLAIN 출력을 읽는 법은 알지만, 그 출력을 **만들어내는 옵티마이저가 어떻게 동작하는지**는 모른다.
면접에서 "왜 인덱스가 있는데 안 타죠?", "조인 순서는 누가 결정하나요?", "옵티마이저가 잘못된 선택을 할 때 어떻게 강제하나요?" 같은 질문을 받으면 막힌다.

옵티마이저는 SQL 한 문장을 **수십\~수백 개의 후보 실행 계획**으로 펼쳐 놓고, 각 계획의 비용을 추정한 뒤 최저 비용을 선택한다.
이 결정 과정에 다음 같은 수많은 변수가 개입한다.

- 통계 정보
- 카디널리티
- 인덱스 선택도
- 조인 알고리즘
- 서브쿼리 변환
- semi-join 전략
- ICP (Index Condition Pushdown)
- MRR (Multi-Range Read)

EXPLAIN은 그 결정의 **결과**일 뿐이고, optimizer_trace는 그 결정의 **과정**을 보여준다.

이 문서는 실행 계획을 *읽는* 단계에서 *만들어지는 원리*를 이해하는 단계로 넘어가기 위한 학습 가이드다.
EXPLAIN 출력 컬럼 해석은 [EXPLAIN / EXPLAIN ANALYZE](./explain-plan.md), 복합 인덱스 설계는 [복합 인덱스 완전 정복](./composite-index.md), B-Tree 인덱스 구조는 [B-Tree 인덱스](./b-tree-index.md)에서 다룬다. 본 문서는 그 위에 올라가는 옵티마이저 레이어를 집중적으로 본다.

---

## 쿼리 한 줄이 실행되기까지의 6단계

MySQL 서버는 SQL을 받으면 다음 단계를 거친다.

| 단계 | 책임 |
|------|------|
| 1. Parser | 토큰화·문법 검사. parse tree 생성 |
| 2. Resolver | 테이블·컬럼·권한 확인. 식별자 바인딩 |
| 3. Logical transformation | 서브쿼리 평탄화, 뷰 머지, 조건 정규화, 상수 폴딩 |
| 4. Optimizer (Cost-based) | 조인 순서·접근 방법·인덱스 선택. 후보 계획 생성 → 비용 추정 → 최적 계획 선택 |
| 5. Plan refinement | ICP/MRR/BKA 적용, range optimizer가 sargable 조건 정리 |
| 6. Executor | 선택된 계획으로 storage engine handler API 호출 |

EXPLAIN은 4\~5단계 결과를 보여주는 스냅샷이고, optimizer_trace는 3\~5단계 내부 의사결정 로그다.
인터뷰에서 "EXPLAIN을 어떻게 진단하나요?"보다 더 깊은 질문은 "옵티마이저가 그 계획을 *왜* 선택했나요?"인데, 이 질문에 답하려면 비용 모델을 알아야 한다.

---

## 비용 기반 옵티마이저(CBO) — 무엇을 비교하나

### 비용의 정의

MySQL 옵티마이저는 각 후보 계획의 비용을 **추정값**으로 계산한다. 비용 단위는 추상화된 cost unit이며, 두 가지 축으로 합산된다.

- **IO 비용** — 디스크 페이지 읽기·랜덤 I/O·시퀀셜 I/O
- **CPU 비용** — 행 평가·정렬·조인·집계

8.0 이후로 `mysql.engine_cost`, `mysql.server_cost` 테이블에서 단가를 조회·튜닝할 수 있다.

```sql
SELECT * FROM mysql.engine_cost;
SELECT * FROM mysql.server_cost;
```

기본값을 그대로 쓰는 게 거의 대부분이고, 단가를 바꿀 일은 매우 드물지만, **존재한다는 것만 알아도** 면접 답변의 깊이가 달라진다.

### 비용 = f(통계, 카디널리티, 인덱스 선택도, 접근 방법)

옵티마이저는 통계 정보가 부정확하면 잘못된 계획을 고른다.
이게 운영에서 가장 자주 보는 "EXPLAIN은 정상인데 본번에서 느린" 증상의 원인이다.

```sql
-- 통계 갱신 강제
ANALYZE TABLE product;
ANALYZE TABLE orders;

-- 컬럼 수준 히스토그램(8.0+) — non-indexed 컬럼의 분포 추정
ANALYZE TABLE product UPDATE HISTOGRAM ON status, price WITH 16 BUCKETS;

-- 적용된 히스토그램 확인
SELECT * FROM information_schema.column_statistics
WHERE schema_name = 'shopdb';
```

히스토그램은 인덱스가 없는 컬럼의 선택도 추정을 보강한다.
인덱스를 추가하기 곤란한 분석성·임시성 컬럼에 카디널리티 정보를 옵티마이저에 주입할 수 있다는 점이 핵심이다.

---

## optimizer_trace — 옵티마이저의 결정을 그대로 들여다보기

`EXPLAIN`은 "어떤 계획을 선택했나"만 보여준다. `optimizer_trace`는 **왜 다른 계획을 버렸는가**까지 보여준다.

### 켜고 출력 뽑기

```sql
SET optimizer_trace = "enabled=on";
SET optimizer_trace_max_mem_size = 1048576;

-- 분석하고 싶은 쿼리 한 번 실행
SELECT p.id, p.name
FROM product p
JOIN orders o ON o.product_id = p.id
WHERE p.category_id = 3 AND o.ordered_at > '2026-01-01';

SELECT trace
FROM information_schema.optimizer_trace\G

SET optimizer_trace = "enabled=off";
```

### trace에서 봐야 할 5가지 섹션

| 섹션 | 의미 |
|------|------|
| `condition_processing` | WHERE 조건의 상수 폴딩·equality propagation 결과 |
| `rows_estimation` | 각 테이블에서 옵티마이저가 추정한 읽기 행 수 |
| `considered_execution_plans` | 후보 조인 순서·접근 방법별 비용 |
| `chosen_plan` | 최종 선택 |
| `attaching_conditions_to_tables` | ICP(인덱스 컨디션 푸시다운) 적용 여부 |

운영에서 "왜 이 인덱스를 안 탔지?"가 막힐 때, trace의 `considered_execution_plans`를 보면 옵티마이저가 그 인덱스도 평가는 했지만 비용 추정이 높아서 버렸음을 직접 확인할 수 있다.

---

## 조인 순서 결정 — 옵티마이저의 가장 중요한 작업

### 왜 조인 순서가 핵심인가

3개 테이블을 조인할 때 가능한 순서는 3! = 6가지다.
실제 OLTP에서는 5\~6개 테이블 조인이 흔하고, 5개 테이블이면 5! = 120가지 순서가 있다.
이걸 다 비교하면 시간이 폭발하므로 MySQL은 `optimizer_search_depth`로 검색 깊이를 제한한다.

```sql
SHOW VARIABLES LIKE 'optimizer_search_depth';
-- 기본 62. 0이면 자동 선택.
```

8개 이상 테이블 조인부터는 옵티마이저가 휴리스틱으로 자르며, 이 지점에서 사람이 잘못된 순서를 선택하기 쉬워진다.

### STRAIGHT_JOIN과 JOIN_ORDER 힌트

옵티마이저가 명백히 틀린 순서를 고를 때만 강제한다. 정상 쿼리에 힌트를 박으면 통계 변화에 따라가지 못해 장기적으로 손해다.

```sql
-- 8.0 권장 방식: 옵티마이저 힌트
SELECT /*+ JOIN_ORDER(p, o) */ p.id, COUNT(o.id)
FROM product p JOIN orders o ON o.product_id = p.id
WHERE p.category_id = 3
GROUP BY p.id;

-- 5.7 호환 방식: STRAIGHT_JOIN
SELECT STRAIGHT_JOIN p.id, COUNT(o.id)
FROM product p JOIN orders o ON o.product_id = p.id
WHERE p.category_id = 3
GROUP BY p.id;
```

힌트는 "옵티마이저가 틀렸다는 증거(trace + EXPLAIN ANALYZE 비교)를 본 뒤"에만 박는다. 추측으로 박지 않는다.

---

## 조인 알고리즘 — Nested Loop, BNL, Hash Join

### Nested Loop Join (NLJ)

가장 흔한 형태. 외부 테이블 한 행마다 내부 테이블 인덱스 lookup. 내부 테이블에 적절한 인덱스가 있어야 효율적이다.

### Block Nested Loop (BNL)

내부 테이블에 인덱스가 없을 때 외부 행을 join buffer에 쌓아 내부 테이블 풀스캔 횟수를 줄이는 방법.
`Extra: Using join buffer (Block Nested Loop)`로 표시된다. **인덱스 부재 신호**다.

### Hash Join (8.0.18+)

equi-join이고 양쪽이 인덱스가 없을 때 옵티마이저가 BNL 대신 hash join을 자동 선택할 수 있다.
대용량 분석성 쿼리에서 BNL 대비 큰 폭으로 빨라진다.

```sql
EXPLAIN FORMAT=TREE
SELECT p.name, c.name
FROM product p JOIN category c ON p.category_id = c.id
WHERE p.status = 'ACTIVE';
-- -> Hash Join ... 형태가 보이면 hash join 적용
```

### BKA (Batched Key Access)

외부 행을 모아서 내부 테이블 인덱스 lookup을 정렬된 키로 한 번에 처리. MRR(Multi-Range Read)과 같이 동작하며 랜덤 I/O를 시퀀셜에 가깝게 변환한다.
8.0 기본값으로 끄여 있어 다음처럼 켤 수 있다.

```sql
SET optimizer_switch = 'batched_key_access=on,mrr=on,mrr_cost_based=off';
```

운영 전체에 켜기 전 워크로드별 검증을 거치는 게 안전하다.

---

## 서브쿼리와 Semi-Join 전략

### semi-join이 무엇인가

`WHERE col IN (SELECT ...)` 처럼 "존재만 확인하는" 서브쿼리는 옵티마이저가 semi-join으로 변환한다.
중복 매칭 행을 한 번만 반환하면 되므로 일반 조인과 처리 전략이 다르다.

MySQL은 5가지 semi-join 전략을 후보로 두고 비교한다.

| 전략 | 의미 | 좋은 경우 |
|------|------|-----------|
| FirstMatch | 내부 매칭 1건 만나면 즉시 중단 | 외부 행이 작고 매칭 빨리 끝남 |
| LooseScan | 인덱스 정렬을 이용해 중복 제거 | 내부 테이블에 정렬 인덱스 있음 |
| Materialization | 서브쿼리 결과를 임시 테이블화 후 조인 | 서브쿼리 결과 작고 재사용 |
| DuplicateWeedout | 일반 조인 후 마지막에 중복 제거 | 조건이 복잡한 경우 |
| Table Pull-out | 1:1 관계로 입증되면 일반 조인으로 평탄화 | unique 제약이 있는 경우 |

`SET optimizer_switch = 'semijoin=on,firstmatch=on,materialization=on,loosescan=on,duplicateweedout=on';` 로 켤 수 있다. 운영 환경은 보통 모두 ON.

### IN vs EXISTS 신화 깨기

옛날 통념인 "EXISTS가 항상 빠르다"는 5.6 이전 한정이다.
5.7\~8.0의 옵티마이저는 IN/EXISTS를 동일한 semi-join으로 변환할 수 있다.
중요한 건 다음이다.

- 내부 테이블에 조인 키 인덱스가 있는가
- semi-join 변환이 켜져 있는가
- 옵티마이저가 두 가지 모두를 같은 형태로 평탄화하는가

trace에서 `transformations_to_nested_joins`를 보면 변환 결과를 확인할 수 있다.

---

## ICP / MRR — 인덱스를 더 똑똑하게 쓰는 보조 기법

### ICP (Index Condition Pushdown)

복합 인덱스 `(a, b)`가 있을 때 `WHERE a = ? AND b LIKE 'X%'` 같은 쿼리에서 `b` 조건을 **인덱스 레벨에서 미리 거른다**.
테이블 본문으로 가는 랜덤 I/O를 줄인다.

EXPLAIN의 `Extra: Using index condition`이 그 표시다.

### MRR (Multi-Range Read)

range 스캔 결과를 PK 순서로 정렬한 뒤 테이블 본문을 읽어 랜덤 I/O를 시퀀셜에 가깝게 변환한다.
대용량 range 조회에서 IO 시간을 큰 폭으로 줄일 수 있지만, 8.0 기본값은 cost-based(`mrr_cost_based=on`)라 옵티마이저가 비용상 유리하다고 판단할 때만 적용된다.

### 두 기능 모두 인덱스 설계의 상호작용

설계 시 ICP/MRR을 의식한 컬럼 순서를 잡으면 같은 인덱스로도 옵티마이저가 더 좋은 계획을 만든다.
인덱스 컬럼 순서 선택 자체는 [복합 인덱스 완전 정복](./composite-index.md)에서 다룬다.

---

## 나쁜 예 vs 개선 예 — 옵티마이저가 잘 못 푸는 패턴

### 함수로 sargability 깨기

```sql
-- Bad: 인덱스 컬럼에 함수 적용 → 옵티마이저가 range 변환 못 함
EXPLAIN SELECT * FROM orders WHERE DATE(ordered_at) = '2026-05-17';

-- Good: 범위 조건으로 표현하면 옵티마이저가 range 스캔 선택
EXPLAIN SELECT * FROM orders
WHERE ordered_at >= '2026-05-17 00:00:00'
  AND ordered_at <  '2026-05-18 00:00:00';
```

8.0의 functional index(`CREATE INDEX ... ON orders ((DATE(ordered_at)))`)로 우회는 가능하지만 인덱스 설계가 복잡해지는 대가가 있다.

### 잘못된 SARGable 조건 순서

```sql
-- 인덱스: (category_id, status, ordered_at)
-- Bad: 옵티마이저가 ordered_at의 range를 선두 prefix로 못 씀
WHERE ordered_at > '2026-05-01' AND status = 'PAID';

-- Good: 선두 컬럼부터 같다 비교가 있어야 인덱스 활용 폭이 넓어진다
WHERE category_id = 3 AND status = 'PAID' AND ordered_at > '2026-05-01';
```

leftmost prefix 원칙은 옵티마이저가 어기는 게 아니라 *어길 수 없다*는 점을 면접에서 분명히 말해야 한다.

### OR로 인덱스 분산

```sql
-- Bad: 옵티마이저가 index_merge_union을 시도하지만 비용상 풀스캔 선택할 가능성
WHERE status = 'PAID' OR user_id = 1234;

-- Good: UNION ALL로 각 인덱스 독립 활용
SELECT * FROM orders WHERE status = 'PAID'
UNION ALL
SELECT * FROM orders WHERE user_id = 1234 AND status <> 'PAID';
```

`optimizer_switch=index_merge=on` 여부와 `index_merge_union/intersection/sort_union` 세부 플래그가 결과를 좌우한다.

### LIMIT + ORDER BY 페이지네이션 함정

```sql
-- Bad: 깊은 오프셋에서 옵티마이저가 정렬을 일찍 끊지 못 함
SELECT * FROM orders ORDER BY ordered_at DESC LIMIT 100 OFFSET 100000;

-- Good: 키셋 페이지네이션(cursor)
SELECT * FROM orders
WHERE ordered_at < :last_seen_ordered_at
ORDER BY ordered_at DESC
LIMIT 100;
```

옵티마이저는 OFFSET을 100,000행 만큼 *물리적으로* 건너뛰는 비용을 줄여주지 못한다. 운영 페이지네이션은 키셋이 표준이다.

---

## 로컬 실습 환경

```bash
docker run --name mysql8-optimizer \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=shopdb \
  -p 3306:3306 \
  -d mysql:8.0

docker exec -it mysql8-optimizer mysql -uroot -proot shopdb
```

```sql
-- 작은 테이블 1개로 옵티마이저 거동 실습
CREATE TABLE orders (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id     BIGINT NOT NULL,
  product_id  BIGINT NOT NULL,
  status      VARCHAR(16) NOT NULL,
  amount      INT NOT NULL,
  ordered_at  DATETIME NOT NULL
);

CREATE INDEX idx_orders_user_ordered ON orders(user_id, ordered_at);
CREATE INDEX idx_orders_status_ordered ON orders(status, ordered_at);
```

```sql
-- 1만 행 시드
INSERT INTO orders (user_id, product_id, status, amount, ordered_at)
WITH RECURSIVE g(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM g WHERE n < 10000)
SELECT (n % 200) + 1,
       (n % 500) + 1,
       ELT((n % 3) + 1, 'PAID','CANCELED','REFUNDED'),
       (n % 100) * 1000,
       DATE_SUB(NOW(), INTERVAL n MINUTE)
FROM g;

ANALYZE TABLE orders;
```

```sql
-- 같은 쿼리를 두 인덱스 중 하나로 강제해 비용 비교
EXPLAIN FORMAT=JSON
  SELECT * FROM orders
  WHERE user_id = 7 AND status = 'PAID'
  ORDER BY ordered_at DESC LIMIT 50;

EXPLAIN FORMAT=JSON
  SELECT * FROM orders FORCE INDEX (idx_orders_user_ordered)
  WHERE user_id = 7 AND status = 'PAID'
  ORDER BY ordered_at DESC LIMIT 50;

EXPLAIN FORMAT=JSON
  SELECT * FROM orders FORCE INDEX (idx_orders_status_ordered)
  WHERE user_id = 7 AND status = 'PAID'
  ORDER BY ordered_at DESC LIMIT 50;
```

`EXPLAIN FORMAT=JSON`의 `cost_info`를 비교하면 옵티마이저가 각 인덱스에 어떤 비용을 매겼는지 직접 볼 수 있다. 이 실습 한 번이 비용 모델을 이론으로 외우는 것보다 훨씬 빨리 감을 잡게 한다.

---

## 인터뷰 답변 프레이밍

### Q. EXPLAIN과 EXPLAIN ANALYZE, optimizer_trace의 차이를 설명해 주세요.

> "EXPLAIN은 옵티마이저가 선택한 *최종 계획*의 추정값을 보여줍니다. EXPLAIN ANALYZE는 실제로 쿼리를 실행해 추정값과 실측값을 함께 보여주므로, 통계 오차로 인한 잘못된 추정을 잡아낼 때 씁니다. optimizer_trace는 더 깊은 단계로, 옵티마이저가 *어떤 후보 계획들을 비교했고 왜 그것을 버렸는지*까지 보여줍니다. 운영에서 '인덱스가 있는데 안 타요' 같은 상황은 보통 EXPLAIN으로 안 보이고, trace의 considered_execution_plans에서야 비용 추정이 왜 그렇게 되었는지가 드러납니다."

### Q. MySQL 옵티마이저가 조인 순서를 어떻게 결정하나요?

> "비용 기반으로 후보 순서를 비교합니다. n개 테이블 조인이면 이론상 n! 후보가 있지만, optimizer_search_depth로 검색 폭을 제한하고 휴리스틱으로 가지치기합니다. 각 후보 순서마다 통계 정보로 추정한 row 수와 인덱스 접근 비용을 곱해 누적 비용을 계산하고, 최저 비용 순서를 고릅니다. 옵티마이저가 명백히 틀렸다는 증거가 trace로 확인되면 JOIN_ORDER 힌트나 STRAIGHT_JOIN으로 강제하지만, 통계 변화에 약해지므로 추측으로는 박지 않습니다."

### Q. 통계 정보와 히스토그램은 어떻게 옵티마이저에 영향을 주나요?

> "옵티마이저는 인덱스 카디널리티와 컬럼 분포로 행 수를 추정합니다. ANALYZE TABLE이 통계를 갱신하지 못한 상태면 추정이 어긋나 잘못된 계획을 고릅니다. MySQL 8.0의 히스토그램은 인덱스가 없는 컬럼에도 분포 정보를 제공해, status 같은 비-인덱스 컬럼이 카디널리티 낮은 값에 몰려 있을 때 옵티마이저가 그 사실을 알고 인덱스를 더 선호하게 만듭니다. 운영에서는 대량 적재·삭제 후 ANALYZE TABLE을 잊으면 EXPLAIN 결과가 일관성을 잃습니다."

### Q. Hash Join이 들어왔는데 언제 NLJ보다 유리한가요?

> "양쪽 테이블에 조인 키 인덱스가 없는 equi-join에서 BNL을 대체하는 용도입니다. NLJ는 외부 1행마다 내부 인덱스 lookup이 일어나므로 외부 카디널리티가 크면 비용이 폭발합니다. Hash Join은 내부 테이블 전체를 해시 테이블로 만들고 외부를 한 번 스캔하므로 두 테이블이 모두 크고 인덱스가 없을 때 유리합니다. 다만 메모리 예산과 hash 충돌을 옵티마이저가 추정하므로, 인덱스를 추가해 NLJ로 갈 수 있다면 OLTP에서는 NLJ가 보통 더 좋습니다."

---

## 시니어 레벨 체크리스트

```text
[ ] EXPLAIN / EXPLAIN ANALYZE / optimizer_trace의 역할 차이를 한 문장으로 말한다
[ ] mysql.engine_cost, mysql.server_cost 단가 테이블의 존재와 의미를 안다
[ ] ANALYZE TABLE이 안 도는 상황이 어떤 증상으로 운영에 드러나는지 설명한다
[ ] 8.0 히스토그램이 어떤 컬럼에 유효한지 말한다
[ ] optimizer_search_depth가 너무 큰 조인에서 어떻게 동작하는지 안다
[ ] JOIN_ORDER 힌트와 STRAIGHT_JOIN의 차이와 권장 시점을 설명한다
[ ] NLJ / BNL / Hash Join이 각각 어느 상황에서 선택되는지 비교한다
[ ] BKA와 MRR이 랜덤 I/O를 시퀀셜로 변환한다는 원리를 안다
[ ] 5가지 semi-join 전략(FirstMatch / LooseScan / Materialization / DuplicateWeedout / Table Pull-out)을 구분한다
[ ] IN vs EXISTS가 8.0에서 같은 계획으로 평탄화될 수 있다는 사실을 안다
[ ] ICP가 적용된 EXPLAIN 표식(Using index condition)을 즉시 인식한다
[ ] 인덱스 컬럼에 함수가 들어가면 sargability가 깨진다는 원리를 설명한다
[ ] 깊은 OFFSET 페이지네이션 대신 키셋 페이지네이션이 옵티마이저 비용 측면에서 왜 우월한지 말한다
[ ] FORCE INDEX는 통계 변화에 약하므로 trace 증거 없이 박지 않는다는 원칙을 안다
[ ] EXPLAIN FORMAT=JSON의 cost_info를 읽어 두 후보 계획의 비용을 비교할 수 있다
```
