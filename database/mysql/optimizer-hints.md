# [초안] MySQL 옵티마이저 힌트 — 인덱스 힌트와 optimizer hint로 실행 계획을 다루는 법

## 1. 이 문서의 목표

이 문서는 MySQL이 고른 실행 계획이 마음에 들지 않을 때, **무엇을 어떻게 강제할 수 있는지**를 정리한 학습 가이드다.
결론부터 말하면 힌트는 두 계열로 나뉜다.

- 인덱스 힌트(`USE / FORCE / IGNORE INDEX`) — 오래된 문법, 인덱스 후보 집합만 손댄다.
- 옵티마이저 힌트(`/*+ ... */`) — MySQL 5.7+ 문법, 조인 방식·접근 전략·실행 제어까지 세밀하게 손댄다.

그리고 가장 중요한 운영 원칙: **힌트는 통계로 풀리지 않는 문제에만 쓰는 최후 수단**이다.
힌트를 박는 순간 그 쿼리는 데이터 분포 변화를 따라가지 못하게 굳는다.

옵티마이저가 *왜* 그런 계획을 골랐는지는 [쿼리 옵티마이저와 실행 계획 생성](./query-optimizer-execution-plan.md)에서, 실행 계획을 *읽는* 법은 [EXPLAIN / EXPLAIN ANALYZE](./explain-plan.md)에서 다룬다.
본 문서는 그 위에서 "고른 결과를 사람이 어떻게 덮어쓰는가"에 집중한다.

---

## 2. 힌트가 두 종류인 이유

MySQL의 힌트는 역사적으로 두 번 진화했다.

| 계열 | 도입 | 위치 | 손대는 대상 |
|------|------|------|-------------|
| 인덱스 힌트 | 오래전부터 | 테이블 참조 바로 뒤 | 인덱스 후보 집합 |
| 옵티마이저 힌트 | 5.7 / 8.0에서 확장 | `SELECT` 직후 주석 블록 | 조인·접근·서브쿼리·실행 제어 |

인덱스 힌트는 "이 테이블에서 이 인덱스만 봐라" 수준의 거친 도구다.
옵티마이저 힌트는 주석처럼 생겼지만 MySQL이 파싱하는 정식 문법이고, 적용 범위(scope)를 글로벌·쿼리블록·테이블·인덱스 단위로 지정할 수 있어 훨씬 외과적이다.

새 코드라면 옵티마이저 힌트를 우선 검토한다.
인덱스 힌트는 레거시 쿼리 유지보수나 아주 단순한 인덱스 강제에만 남겨둔다.

---

## 3. 인덱스 힌트 — USE / FORCE / IGNORE INDEX

### 3-1. 세 가지 동작 차이

```sql
-- 후보로 "고려만" 하라고 제안 (옵티마이저가 무시할 수도 있음)
SELECT * FROM orders USE INDEX (idx_user_created) WHERE user_id = 100;

-- 풀스캔보다 비싸 보여도 이 인덱스를 "쓰게" 강하게 밀어붙임
SELECT * FROM orders FORCE INDEX (idx_user_created) WHERE user_id = 100;

-- 이 인덱스는 후보에서 "제외"
SELECT * FROM orders IGNORE INDEX (idx_status) WHERE user_id = 100;
```

핵심 오해 하나: `USE INDEX`는 강제가 아니다.
옵티마이저가 그 인덱스보다 풀스캔이 싸다고 판단하면 여전히 풀스캔을 고를 수 있다.
정말 인덱스를 강제하려면 `FORCE INDEX`를 쓴다.

### 3-2. 용도 한정 — FOR JOIN / ORDER BY / GROUP BY

인덱스 힌트는 어느 처리 단계에 적용할지 좁힐 수 있다.

```sql
-- 정렬에만 이 인덱스를 쓰도록 한정
SELECT * FROM orders
FORCE INDEX FOR ORDER BY (idx_created_at)
WHERE status = 'PAID'
ORDER BY created_at DESC
LIMIT 20;
```

`FOR JOIN`은 행을 찾는 접근(조인·WHERE 매칭), `FOR ORDER BY`는 정렬, `FOR GROUP BY`는 그룹핑에만 적용된다.
용도를 명시하지 않으면 모든 단계에 적용된다.

---

## 4. 옵티마이저 힌트 — /*+ ... */ 구조

### 4-1. 기본 문법과 적용 범위

옵티마이저 힌트는 `SELECT`(또는 `INSERT`/`UPDATE`/`DELETE`) 키워드 **바로 다음**에 `/*+ ... */` 블록으로 넣는다.

```sql
SELECT /*+ MAX_EXECUTION_TIME(1000) BNL(o) */
       o.id, o.amount
FROM orders o
WHERE o.user_id = 100;
```

적용 범위는 4단계로 나뉜다.

- 글로벌 — 쿼리 전체 (`MAX_EXECUTION_TIME` 등)
- 쿼리 블록 — 특정 `SELECT` 블록 (`SEMIJOIN`, `SUBQUERY` 등)
- 테이블 — 특정 테이블 (`BNL(o)`, `NO_BKA(o)` 등)
- 인덱스 — 특정 인덱스 (`INDEX(o idx_user)`, `NO_INDEX_MERGE(o idx_a, idx_b)` 등)

### 4-2. 서브쿼리를 가리키는 QB_NAME

중첩 쿼리에서 "어느 블록"인지 지정하려면 쿼리 블록에 이름을 붙인다.

```sql
SELECT /*+ JOIN_ORDER(o, u) */
       u.name, o.amount
FROM users u
JOIN (
  SELECT /*+ QB_NAME(sub) */ user_id, amount
  FROM orders
  WHERE status = 'PAID'
) o ON o.user_id = u.id;
```

`QB_NAME`으로 블록에 라벨을 달면, 바깥에서 `@블록이름` 형태로 그 블록 안의 테이블을 가리킬 수 있다.
중첩이 깊은 쿼리에서 힌트가 "어디에 걸리는지" 모호할 때 필수다.

---

## 5. 자주 쓰는 옵티마이저 힌트 카탈로그

대부분 `XXX` / `NO_XXX` 쌍으로 존재한다 — 켜기와 끄기.

| 분류 | 힌트 | 의미 |
|------|------|------|
| 조인 순서 | `JOIN_ORDER`, `JOIN_PREFIX`, `JOIN_SUFFIX` | 조인 순서를 고정·부분 고정 |
| 조인 알고리즘 | `BNL` / `NO_BNL`, `BKA` / `NO_BKA`, `HASH_JOIN` / `NO_HASH_JOIN` | Block Nested Loop·Batched Key Access·해시 조인 제어 |
| 인덱스 접근 | `INDEX`, `NO_INDEX`, `GROUP_INDEX`, `JOIN_INDEX`, `ORDER_INDEX` | 인덱스 후보 지정 (8.0.20+ 세분화) |
| 인덱스 전략 | `INDEX_MERGE` / `NO_INDEX_MERGE`, `MRR` / `NO_MRR`, `NO_ICP` | 인덱스 머지·Multi-Range Read·Index Condition Pushdown 제어 |
| 서브쿼리 | `SEMIJOIN` / `NO_SEMIJOIN`, `SUBQUERY` | semi-join 전략, 머티리얼라이즈 vs exists 변환 |
| 실행 제어 | `MAX_EXECUTION_TIME`, `SET_VAR`, `RESOURCE_GROUP` | 타임아웃·세션 변수 임시 변경·리소스 그룹 |
| 파생 테이블 | `MERGE` / `NO_MERGE` | 뷰·서브쿼리를 머지할지 머티리얼라이즈할지 |

자주 실전에서 닿는 두 가지를 짚는다.

```sql
-- 이 쿼리만 500ms 넘으면 죽여라 (전역 설정을 건드리지 않고 쿼리 단위 타임아웃)
SELECT /*+ MAX_EXECUTION_TIME(500) */ COUNT(*) FROM big_table WHERE flag = 1;

-- 이 쿼리에서만 세션 변수를 잠깐 바꿔라 (SET 후 복구하는 패턴을 한 줄로)
SELECT /*+ SET_VAR(optimizer_switch='index_merge=off') */ *
FROM orders WHERE user_id = 100 OR status = 'PAID';
```

`SET_VAR`는 `SET` 한 줄로 세션 변수를 바꾸고 되돌리는 번거로운 패턴을 쿼리 안에 가둬, 영향 범위를 그 한 문장으로 한정한다.

---

## 6. 우선순위와 충돌 규칙

힌트를 섞어 쓰면 어느 쪽이 이기는지 헷갈린다.
규칙은 이렇다.

- 같은 대상에 인덱스 힌트와 옵티마이저 힌트가 둘 다 걸리면 **옵티마이저 힌트가 우선**한다.
- 같은 옵티마이저 힌트가 같은 대상에 중복되면 **처음 것만 적용**되고 나머지는 무시된다 (경고 발생).
- 서로 모순되는 힌트는 뒤따라온 힌트가 무시된다.
- `FORCE INDEX`로 지정한 인덱스가 쿼리에 실제로 쓸 수 없는 인덱스면, 힌트가 조용히 무시되고 풀스캔으로 떨어질 수 있다.

힌트가 듣지 않을 때 디버깅 순서는 단순하다.

```sql
-- 1) 힌트를 넣은 그대로 EXPLAIN
EXPLAIN SELECT /*+ INDEX(o idx_user_created) */ * FROM orders o WHERE o.user_id = 100;

-- 2) 무시됐다면 경고를 본다
SHOW WARNINGS;
```

`SHOW WARNINGS`는 "힌트 이름이 틀렸다", "그 인덱스는 쓸 수 없다", "중복 힌트라 무시했다" 같은 사유를 직접 알려준다.
힌트가 안 먹으면 추측하지 말고 경고를 먼저 읽는다.

---

## 7. 작동 원리 — 힌트는 어느 단계에서 적용되나

힌트는 마법이 아니라 옵티마이저의 특정 단계에 개입하는 입력이다.

쿼리 한 줄이 실행되는 단계는 [쿼리 옵티마이저와 실행 계획 생성](./query-optimizer-execution-plan.md)에서 자세히 다루지만, 힌트 관점에서 핵심만 보면 이렇다.

- 인덱스 힌트·`INDEX` 류 힌트 → 옵티마이저가 **접근 방법 후보를 만드는 단계**에서 후보 집합을 좁히거나 강제한다.
- `JOIN_ORDER` 류 → **조인 순서 탐색 단계**에서 탐색 공간을 고정한다.
- `BNL` / `BKA` / `HASH_JOIN` 류 → **조인 알고리즘 선택 단계**를 덮어쓴다.
- `SEMIJOIN` / `SUBQUERY` → **서브쿼리 변환 단계**의 전략을 지정한다.
- `MAX_EXECUTION_TIME` → 옵티마이저가 아니라 **실행기(executor) 단계**에서 타이머로 작동한다.

그래서 "비용 모델상 불가능한 계획"은 힌트로도 못 만든다.
힌트는 옵티마이저가 *고려할 수 있는 후보 안에서* 선택을 강제하는 것이지, 없는 실행 경로를 만들어내는 게 아니다.
`FORCE INDEX`가 무시되는 가장 흔한 이유도 이것 — 그 인덱스로는 해당 WHERE 조건을 만족할 수 없어서 애초에 후보가 아니기 때문이다.

---

## 8. 흔한 오해

- **"힌트를 박으면 항상 빨라진다"** — 아니다. 당장은 빨라져도 데이터 분포가 바뀌면 옛 판단에 굳어 더 느려진다. 힌트는 통계 변화에 약하다.
- **"USE INDEX면 그 인덱스를 무조건 쓴다"** — 아니다. `USE`는 제안, `FORCE`가 강제다.
- **"옵티마이저 힌트는 주석이라 무시돼도 된다"** — 문법은 주석 모양이지만 MySQL이 정식 파싱한다. 오타가 나면 `SHOW WARNINGS`에 경고가 뜨고 그 힌트만 무시된다.
- **"힌트 한 번 넣으면 끝"** — 버전 업그레이드 시 옵티마이저가 똑똑해져 힌트가 오히려 방해가 되는 경우가 잦다. 힌트는 업그레이드 회귀 검증 대상이다.
- **"FORCE INDEX는 인덱스를 새로 만들어준다"** — 아니다. 이미 존재하는 인덱스 중에서 고를 뿐이다. 인덱스 설계 자체는 [복합 인덱스 완전 정복](./composite-index.md)을 따른다.

---

## 9. 설계·운영 체크포인트

힌트를 쓰기 전에 다음 순서로 자문한다.

1. **통계가 최신인가** — `ANALYZE TABLE`로 통계를 갱신하면 힌트 없이 풀리는 경우가 많다. 힌트보다 통계가 먼저다.
2. **인덱스 설계 문제가 아닌가** — 옵티마이저가 나쁜 인덱스를 고르는 건 종종 더 나은 인덱스가 없다는 신호다.
3. **쿼리를 다시 쓸 수 있나** — sargable하지 않은 조건, 불필요한 함수 래핑을 고치면 힌트가 필요 없어진다.
4. **그래도 옵티마이저가 명백히 틀렸나** — `optimizer_trace`로 잘못된 비용 추정을 *증거로* 확인한 뒤에만 힌트를 박는다.

힌트를 박기로 했다면 운영 규칙을 함께 남긴다.

- 힌트를 넣은 쿼리에는 **왜 박았는지 주석**을 단다 (어떤 통계·trace 근거로, 어떤 버전에서).
- 힌트가 걸린 쿼리는 **MySQL 버전 업그레이드 회귀 목록**에 올린다.
- 가능하면 힌트 대신 **인덱스 추가·통계 갱신·쿼리 재작성**으로 해결한 뒤 힌트를 제거한다.

---

## 10. 점검 질문

스스로 답해보며 이해를 확인한다.

- 인덱스 힌트와 옵티마이저 힌트의 문법 위치와 적용 범위 차이를 설명할 수 있는가.
- `USE INDEX`와 `FORCE INDEX`의 차이는 무엇이고, 왜 `USE`가 무시될 수 있는가.
- 옵티마이저 힌트의 4가지 적용 범위(글로벌·쿼리블록·테이블·인덱스)를 예로 들 수 있는가.
- 중첩 서브쿼리에서 특정 블록을 가리키려면 무엇을 쓰는가.
- 인덱스 힌트와 옵티마이저 힌트가 충돌하면 어느 쪽이 이기는가.
- `FORCE INDEX`가 조용히 무시되는 대표적 원인은 무엇인가.
- `MAX_EXECUTION_TIME`이 옵티마이저가 아니라 실행기 단계에서 작동한다는 게 무슨 뜻인가.
- 힌트를 박기 전에 먼저 확인해야 할 것 네 가지(통계·인덱스 설계·쿼리 재작성·trace 증거)를 말할 수 있는가.

---

## 관련 문서

- [쿼리 옵티마이저와 실행 계획 생성](./query-optimizer-execution-plan.md) — 비용 모델·통계·optimizer_trace
- [EXPLAIN / EXPLAIN ANALYZE 완전 정복](./explain-plan.md) — 실행 계획 출력 읽기
- [복합 인덱스 완전 정복](./composite-index.md) — 힌트 이전에 점검할 인덱스 설계
- [B-Tree 인덱스](./b-tree-index.md) — 인덱스 구조 기초
