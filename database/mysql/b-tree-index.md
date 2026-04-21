# [초안] MySQL / InnoDB 인덱스 종합 정리: 구조부터 "인덱스를 안 타는 쿼리"까지

## 왜 하나로 모아야 하는가

MySQL 인덱스는 면접에서 늘 두 축으로 물어본다. "어떻게 동작하는가"(구조)와 "왜 내 쿼리는 느린가"(운영). 전자는 B+Tree, 클러스터드/세컨더리, 커버링, 복합 인덱스 같은 정적 지식이다. 후자는 EXPLAIN으로 실제 실행 계획을 읽고, 인덱스를 **안 타는** 상황을 진단해 개선하는 동적 역량이다.

이 문서는 둘을 하나로 묶는다. 개별 심화 문서(`composite-index.md`, `explain-plan.md`)는 별도로 있지만, 실제 면접에서는 "인덱스 왜 안 타요?" 같은 질문 하나에 구조·복합·EXPLAIN·운영이 동시에 튀어나온다. 이 문서를 먼저 읽고 필요한 축에서 심화 문서로 내려가는 구조다.

---

## 1. InnoDB 인덱스의 기본 구조

### 1-1. B+Tree를 쓰는 이유

InnoDB 인덱스는 모두 **B+Tree**다. B-Tree와 달리 내부 노드에는 키만, 실제 값은 리프 노드에만 있고 리프 노드끼리 양방향 링크드 리스트로 연결된다.

- **범위 검색에 유리**: 리프가 정렬+링크 구조라서 `BETWEEN`, `>`, `<`, `LIKE 'prefix%'` 같은 범위 조건을 링크를 타고 순차 스캔한다.
- **디스크 I/O 최소화**: 노드 하나가 InnoDB 페이지(기본 16KB)에 다수 키를 담고, 트리 높이가 낮다(보통 3~4단계). 한 번의 페이지 읽기로 많은 키를 가져온다.

```
                    [ 루트 ]
                   /        \
             [ 내부 ]        [ 내부 ]
             /    \          /    \
         [리프]  [리프] ↔ [리프]  [리프]
              (리프는 양방향 연결 리스트)
```

### 1-2. 트리 높이와 읽기 비용

100만 행 테이블의 B+Tree 높이는 보통 3~4다. PK 조회 1건에 디스크 I/O 3~4회. 루트와 상위 내부 노드는 버퍼 풀에 거의 상주하므로 실질 디스크 I/O는 1~2회에 가깝다. "인덱스가 있으면 빠르다"의 정량적 근거다.

---

## 2. 클러스터드 인덱스 (Primary Key)

InnoDB의 가장 중요한 사실 하나: **PK 자체가 테이블이다.**

```
PK 인덱스 리프 노드 = 실제 행 데이터 전체

리프: [PK=1 | name="kim" | age=30 | ...]
       [PK=2 | name="lee" | age=25 | ...]
       [PK=3 | name="park"| age=40 | ...]
```

- PK 순서로 물리적으로 정렬 저장 → PK 범위 조회는 순차 I/O
- 별도의 "테이블 파일 + 인덱스 파일" 구조가 아니다 (MyISAM과 다름)
- PK가 없으면 MySQL이 내부적으로 6바이트짜리 hidden `DB_ROW_ID`를 만든다

### 2-1. Auto Increment PK를 선호하는 이유

단조 증가 PK는 항상 트리의 오른쪽 끝에 추가되어 페이지 분할이 거의 없다. 반면 UUIDv4 같은 랜덤 PK는 중간 삽입이 잦아 페이지 분할과 단편화가 심해진다. UUID가 꼭 필요하면 시간순 정렬이 보장되는 **UUIDv7** 또는 ULID를 고려한다.

### 2-2. PK 선택의 실무 기준

- 불변이어야 한다 (변경되면 세컨더리 인덱스 전체가 바뀐다)
- 가능한 한 짧게 (세컨더리 인덱스 리프에 PK 값이 복제되므로 PK가 길면 세컨더리가 비대해진다)
- 단조 증가가 유리

---

## 3. 세컨더리 인덱스와 북마크 룩업

PK 외 컬럼에 만든 인덱스. 리프에는 **인덱스 키 + PK 값**이 들어간다.

```
name 인덱스 리프:
  ["kim"  | PK=1]
  ["lee"  | PK=2]
  ["park" | PK=3]
```

세컨더리 인덱스로 조회하면 기본적으로 두 번 탐색한다.

1. 세컨더리 인덱스 탐색 → PK 획득
2. 클러스터드 인덱스(PK 트리) 탐색 → 실제 행 획득

이 2단계를 **북마크 룩업(bookmark lookup)**, 또는 **테이블 액세스**라고 한다. 공짜가 아니라는 사실이 커버링 인덱스가 중요한 이유다.

---

## 4. 커버링 인덱스 (Covering Index)

쿼리가 필요로 하는 **모든 컬럼이 인덱스 안에** 있어서 북마크 룩업이 생략되는 경우.

```sql
-- (name, age) 복합 인덱스가 있을 때
SELECT age FROM users WHERE name = 'kim';
-- 세컨더리 인덱스 리프에 name과 age가 다 있음 → 테이블 접근 없음
```

EXPLAIN `Extra: Using index`가 커버링 인덱스 시그널이다. `Using index condition`과 혼동하지 말 것 — 후자는 ICP(Index Condition Pushdown)가 적용됐다는 뜻이지 커버링은 아니다.

### 4-1. 언제 커버링으로 만들 가치가 있나

- **읽기 빈도가 매우 높은** 핫 쿼리(상품 목록, 홈 피드 등)
- SELECT 컬럼이 고정적
- 테이블이 커서 북마크 룩업의 랜덤 I/O 비용이 무시 못 할 때

### 4-2. 트레이드오프

- 인덱스 크기 증가 → 버퍼 풀 점유 증가
- INSERT/UPDATE/DELETE 시 모든 관련 인덱스를 갱신 → 쓰기 비용 증가
- `SELECT *`를 남발하면 커버링 설계가 거의 불가능

---

## 5. 복합 인덱스와 좌측 접두사 규칙

`INDEX idx (a, b, c)`의 리프는 **a 오름차순 → 같은 a 내 b 오름차순 → 같은 (a,b) 내 c 오름차순**으로 정렬된다. 이 물리 구조가 **좌측 접두사 규칙(Leftmost Prefix Rule)**의 근거다.

| 쿼리 조건 | 사용 | 이유 |
|---|---|---|
| `a = 1` | a | 선두 컬럼 |
| `a = 1 AND b = 2` | a, b | 좌측부터 연속 |
| `a = 1 AND b = 2 AND c = 3` | a, b, c | 모두 사용 |
| `b = 2` | 미사용 | 선두 컬럼 없음 |
| `b = 2 AND c = 3` | 미사용 | 선두 컬럼 없음 |
| `a = 1 AND c = 3` | a만 | b를 건너뜀, c는 인덱스 활용 X |
| `a = 1 AND b > 10 AND c = 5` | a, b까지 | 범위 이후 컬럼은 인덱스 활용 X |

### 5-1. 컬럼 순서 결정 순서 (선택도가 아니라 쿼리 패턴)

흔한 오답: "선택도 높은 컬럼을 앞에." 쿼리 패턴을 먼저 봐야 한다.

1. **항상 동등 조건(`=`)으로 쓰이는 컬럼**을 맨 앞에
2. 동등 조건 컬럼이 여럿이면 그 중 선택도 높은 것을 앞에
3. **범위 조건(`>`, `<`, `BETWEEN`)** 컬럼을 뒤에
4. **ORDER BY / GROUP BY** 컬럼을 그 뒤에

심화 근거/예시는 [composite-index.md](./composite-index.md) 참고.

---

## 6. EXPLAIN으로 인덱스 검증하기

인덱스를 "만들었다"로 끝내면 안 된다. **EXPLAIN으로 실제 타는지 확인**하는 습관이 실력이다.

### 6-1. 핵심 컬럼

| 컬럼 | 본다는 의미 |
|---|---|
| `type` | 접근 방식. `const`/`eq_ref`/`ref`/`range` 좋음, `index` 나쁨, `ALL` 풀스캔 |
| `key` | 실제 선택된 인덱스 |
| `key_len` | 인덱스 바이트 수 → 몇 개 컬럼까지 사용했는지 역산 가능 |
| `rows` | 옵티마이저 추정 읽기 행 수 |
| `filtered` | WHERE 후 남을 비율(%). `rows × filtered/100`이 다음 단계로 넘어갈 예상 행 수 |
| `Extra` | `Using index`(커버링), `Using filesort`, `Using temporary`, `Using where`, `Using index condition`(ICP) |

### 6-2. key_len으로 사용 컬럼 수 역산

```sql
-- INDEX idx (user_id BIGINT, status VARCHAR(20) NOT NULL utf8mb4, created_at DATETIME NOT NULL)
-- BIGINT=8, VARCHAR(20) NOT NULL utf8mb4 = 20*4+2 = 82, DATETIME NOT NULL = 5

EXPLAIN ... WHERE user_id = 42;
-- key_len = 8       → user_id 하나만

EXPLAIN ... WHERE user_id = 42 AND status = 'ACTIVE';
-- key_len = 8 + 82 = 90   → 두 컬럼

EXPLAIN ... WHERE user_id = 42 AND status = 'ACTIVE' AND created_at >= '2025-01-01';
-- key_len = 90 + 5 = 95   → 세 컬럼
```

의도한 컬럼 수와 `key_len`이 다르면 어딘가에서 인덱스가 끊긴 것이다. 더 깊이는 [explain-plan.md](./explain-plan.md) 참고.

### 6-3. EXPLAIN ANALYZE (MySQL 8.0.18+)

실제 실행 후 `actual time`, `rows`, `loops`까지 보여준다. 옵티마이저 추정과 실제가 크게 다르면 통계가 낡았거나 인덱스 설계가 어긋난 것이다. `ANALYZE TABLE`로 통계부터 갱신한다.

---

## 7. 인덱스를 타지 않는 케이스 (이 문서의 핵심)

면접에서 가장 자주 묻는 영역. 실무 슬로우 쿼리의 절반 이상이 여기에 해당한다. 각 케이스마다 **왜 안 타는지 → 어떻게 고치는지 → 어떻게 진단하는지**를 묶어서 본다.

### 7-1. 인덱스 컬럼에 함수 / 연산 적용

```sql
-- BAD: 함수로 감싸면 인덱스 무력화
WHERE YEAR(created_at) = 2025
WHERE DATE(created_at) = '2025-04-21'
WHERE created_at + INTERVAL 1 DAY = NOW()
WHERE LOWER(email) = 'test@example.com'
WHERE SUBSTRING(phone, 1, 3) = '010'
```

**왜**: B+Tree는 컬럼 원본 값으로 정렬되어 있다. `YEAR(created_at)`의 결과는 정렬 보장이 없으므로 옵티마이저는 전체를 훑어 계산할 수밖에 없다.

**고치는 법**:

```sql
-- 범위 조건으로 변환
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01'
WHERE created_at >= '2025-04-21 00:00:00' AND created_at < '2025-04-22 00:00:00'

-- 애플리케이션에서 정규화 후 저장 (email 소문자 등)
WHERE email = 'test@example.com'

-- MySQL 8: 꼭 함수 기반 조회가 필요하면 함수형 인덱스
CREATE INDEX idx_email_lower ON users ((LOWER(email)));
CREATE INDEX idx_created_year ON orders ((YEAR(created_at)));
```

### 7-2. 암묵적 타입 변환 (Implicit Type Conversion)

```sql
-- user_id가 BIGINT인데 문자열로 비교 (버전/케이스에 따라 컬럼 쪽 캐스팅이 걸릴 수 있음)
WHERE user_id = '42'
-- VARCHAR 컬럼을 숫자와 비교 → 컬럼이 숫자로 캐스팅 → 거의 확실히 풀스캔
WHERE phone_number = 01012345678
```

**왜**: MySQL은 비교 대상 한쪽을 캐스팅해서 타입을 맞추는데, **컬럼 쪽으로 캐스팅이 걸리면 "컬럼에 함수 적용"과 같은 상태**가 되어 인덱스가 죽는다. 특히 `VARCHAR` 컬럼을 숫자 리터럴과 비교하면(반대 방향 캐스팅) 거의 확실히 풀스캔이다.

**진단**: `EXPLAIN` 직후 `SHOW WARNINGS`에 cast 관련 경고가 있는지 확인.

**고치는 법**: Java/JPA에서 **파라미터 타입을 DB 컬럼 타입과 정확히 일치**시킨다. `Long` PK에 `String`을 바인딩하지 말 것.

### 7-3. LIKE의 선두 와일드카드

```sql
WHERE name LIKE '%kim'    -- ❌ 인덱스 불가
WHERE name LIKE '%kim%'   -- ❌ 인덱스 불가
WHERE name LIKE 'kim%'    -- ✅ 범위 스캔 가능
```

**왜**: B+Tree는 앞에서부터 정렬되어 있다. 접두가 없으면 어디서부터 탐색을 시작할지 결정할 수 없다.

**고치는 법**:

- 접미/중간 검색이 꼭 필요하면 FULLTEXT 인덱스(`MATCH ... AGAINST`) 또는 Elasticsearch 같은 외부 검색 엔진
- 역방향 접미 검색만 필요하면 `REVERSE(col)`에 함수형 인덱스 + 쿼리도 `LIKE REVERSE('kim') || '%'` 형태로
- 단순 포함 검색은 n-gram FULLTEXT 파서 고려

### 7-4. OR 조건

```sql
WHERE user_id = 42 OR email = 'test@example.com'
```

**왜**: 각각 다른 인덱스라도 OR은 둘을 결합 판단해야 해 옵티마이저가 풀스캔을 고르는 경우가 많다. 둘 다 인덱스가 있으면 `index_merge union`이 적용될 수도 있지만 비용과 예측성이 낮다.

**고치는 법**: `UNION ALL`로 분해해 각각 인덱스를 타게 한다.

```sql
SELECT * FROM users WHERE user_id = 42
UNION ALL
SELECT * FROM users WHERE email = 'test@example.com' AND user_id <> 42;
```

`UNION`(중복 제거)은 정렬 비용이 크므로 가능한 `UNION ALL`에 중복 제외 조건을 두 번째 쿼리에 명시.

### 7-5. 낮은 카디널리티 + 넓은 매칭

```sql
-- status 값이 5개뿐, 데이터의 90%가 'ACTIVE'
WHERE status = 'ACTIVE'
```

**왜**: 옵티마이저는 "인덱스 탐색 후 북마크 룩업 × N회"가 "풀스캔 한 번"보다 비싸다고 판단하면 풀스캔을 고른다. 통상 **테이블의 20~30% 이상을 읽을 것으로 추정**되면 풀스캔을 택한다(데이터 분포·버퍼 상태 의존).

**고치는 법**:

- 낮은 카디널리티 컬럼을 **단독 인덱스로 만들지 말 것**
- 복합 인덱스의 뒷부분에 포함해 다른 조건과 결합 선택도를 높임
- 또는 `(status, created_at)`처럼 자주 같이 쓰는 컬럼과 묶어 **커버링 인덱스**로 만들어 풀스캔보다 싸게

### 7-6. 좌측 접두사 규칙 위반

```sql
-- INDEX idx (a, b, c)
WHERE b = 2 AND c = 3          -- ❌ 선두 a 없음 → 인덱스 미사용
WHERE a = 1 AND c = 3          -- ⚠️ a만 사용, c는 테이블 필터링
```

**진단**: EXPLAIN `key_len`이 선두 컬럼 바이트만 반영되는지 확인.

**고치는 법**: 쿼리 패턴에 맞는 새 인덱스를 만들거나 기존 인덱스 컬럼 순서를 재설계(기존 쿼리 영향 반드시 확인).

### 7-7. 범위 조건 이후 컬럼

```sql
-- INDEX idx (a, b, c)
WHERE a = 1 AND b > 10 AND c = 5
-- a, b까지만 인덱스 활용, c는 테이블에서 필터링
```

**왜**: `b > 10`은 여러 b 값을 훑는다. 각 b 값 내에서 c는 정렬되어 있지만 b가 달라지면 c의 정렬 연속성이 깨진다. c로는 인덱스 점프가 불가능.

**고치는 법**: 동등 조건을 앞으로 모은다.

```sql
-- 재설계: c(동등)를 b(범위) 앞으로
INDEX idx (a, c, b)
```

MySQL 5.6+의 **ICP(Index Condition Pushdown)**이 켜져 있으면 c 조건을 스토리지 엔진 레벨에서 필터해 북마크 룩업 자체를 줄여준다 (`Extra: Using index condition`).

### 7-8. ORDER BY / GROUP BY 미스매치 → filesort

```sql
-- INDEX idx (category_id, created_at)

-- BAD: 정렬 컬럼이 인덱스 뒷부분에 없음
SELECT * FROM products WHERE category_id = 5 ORDER BY price DESC;
-- Extra: Using filesort

-- GOOD: 정렬 컬럼을 인덱스에 포함
CREATE INDEX idx ON products (category_id, price);
SELECT * FROM products WHERE category_id = 5 ORDER BY price DESC;
-- Extra: (없음)
```

**ASC/DESC 혼합 주의**: 인덱스가 모든 컬럼에서 같은 방향이어야 filesort 없이 처리된다. MySQL 8은 `CREATE INDEX idx (a ASC, b DESC)` 같은 **내림차순 인덱스**를 지원한다.

### 7-9. 옵티마이저가 풀스캔을 선택하는 경우

인덱스가 있는데도 `type: ALL`이 나오면 옵티마이저가 의도적으로 풀스캔을 고른 것이다. 주요 원인:

1. **통계 오래됨** → `ANALYZE TABLE`로 갱신
2. **매칭 비율이 너무 높음** (7-5)
3. **테이블이 작아서** 풀스캔이 더 쌈
4. **조인 순서/힌트 문제**: `STRAIGHT_JOIN`, 조인 순서가 바뀌면 계획 달라짐

**최후 수단 `FORCE INDEX` / `USE INDEX`**: 옵티마이저 선택을 강제할 수 있지만, 통계/데이터 분포가 변하면 오히려 더 느려질 수 있다. **원인(통계·설계)부터 고치는 게 원칙**, 힌트는 확신이 있을 때만.

### 7-10. `NOT IN`, `!=`, `<>`

이런 조건은 인덱스 범위 스캔으로 표현하기 어려워 풀스캔이 되는 경우가 많다. 데이터 분포 의존.

**고치는 법**: 가능하면 긍정 조건으로 재작성. 상태가 5개인데 `status != 'DELETED'`라면 `status IN ('ACTIVE', 'PENDING', 'PAUSED', 'HOLD')`로 바꿔 IN 리스트 범위 스캔으로 유도.

### 7-11. NULL 비교

`IS NULL` / `IS NOT NULL`은 인덱스를 **탈 수 있다** (MySQL은 인덱스에 NULL을 포함). `column = NULL`(항상 거짓, 틀린 문법)은 별개의 실수. 선택도가 극단적이면(대부분이 NULL이거나 NOT NULL) 풀스캔이 나올 수 있다.

---

## 8. 실무 진단 플레이북

슬로우 쿼리 제보가 들어왔을 때 어떤 순서로 접근하는가 — 면접 답변에 그대로 쓸 수 있는 흐름.

1. **슬로우 쿼리 로그 / APM**에서 대상 쿼리 식별
2. `EXPLAIN` 실행
   - `type`이 `ALL`/`index`면 1차 위험 신호
   - `Extra`에 `Using filesort` / `Using temporary`가 있는지
   - `key`가 기대한 인덱스인지
   - `key_len`이 기대한 컬럼 수만큼인지
3. `EXPLAIN ANALYZE`로 예측값 vs 실제값 비교 → 차이 크면 `ANALYZE TABLE`로 통계 갱신 후 재측정
4. 원인을 7장 케이스 중 하나로 분류
5. 수정안 적용 — **쿼리 재작성 → 인덱스 추가 → 인덱스 재설계** 순으로 가벼운 것부터
6. 수정 후 **다시 EXPLAIN**으로 실제로 바뀌었는지 검증
7. 운영 반영 시 온라인 DDL 지원 여부 확인 (`ALTER TABLE ... ALGORITHM=INPLACE, LOCK=NONE`)
8. 반영 후 **슬로우 쿼리 로그 / p99 지표 재측정**

---

## 9. 운영 관점 주의 사항

### 9-1. 페이지 분할과 단편화

```
[1][2][3][4]  ← 꽉 참
    ↓ 중간에 5 삽입
[1][2] [3][4][5]
```

- 쓰기 성능 저하 (분할 + 부모 노드 갱신)
- 범위 스캔 시 물리적 비연속 → 순차 I/O가 랜덤 I/O에 가까워짐
- `OPTIMIZE TABLE`로 재구축 가능하지만 락/복제 지연 주의

### 9-2. 인덱스 추가/삭제는 운영 이벤트

- 대형 테이블에서 인덱스 생성은 수십 분~수 시간
- **온라인 DDL** 가능 여부 미리 확인: `ALGORITHM=INPLACE, LOCK=NONE`
- Aurora에서는 Reader 복제 지연을 함께 모니터링
- pt-online-schema-change / gh-ost 같은 도구 고려

### 9-3. 인덱스 개수의 균형

인덱스는 공짜가 아니다. INSERT/UPDATE/DELETE 때마다 모든 인덱스를 갱신한다. 버퍼 풀도 점유한다. "일단 만들어두자"가 아니라 **쿼리 패턴을 근거로 최소한만**.

### 9-4. 주기적 통계 갱신

대량 적재/삭제 후 통계가 낡으면 옵티마이저가 잘못된 플랜을 고른다. 배치 적재 후 `ANALYZE TABLE`을 의식적으로 호출한다.

---

## 10. 면접 답변 프레임

### Q1. "MySQL 인덱스는 어떤 구조고, 왜 빠른가요?"

> "InnoDB는 B+Tree를 사용합니다. 리프 노드에만 실제 값이 있고 리프끼리 양방향 링크로 연결돼 있어 범위 검색이 효율적이고, 노드 하나가 16KB 페이지에 많은 키를 담아 트리 높이가 3~4단계로 낮습니다. 그래서 100만 행에서도 PK 조회는 디스크 I/O 몇 번으로 끝납니다. InnoDB는 PK 자체가 테이블 데이터 구조(클러스터드 인덱스)이고, 세컨더리 인덱스는 리프에 PK 값을 담아 두 번 탐색을 거쳐 행을 읽습니다."

### Q2. "인덱스를 걸었는데도 느린 쿼리, 어떻게 진단하시나요?"

> "EXPLAIN부터 봅니다. `type`이 `ALL`/`index`인지, `key`가 의도한 인덱스인지, `key_len`이 기대한 컬럼 수만큼인지, `Extra`에 `Using filesort`/`Using temporary`가 있는지를 확인합니다. 원인은 보통 몇 가지 패턴으로 모입니다 — 인덱스 컬럼에 함수/연산을 씌운 경우, VARCHAR 컬럼을 숫자와 비교해 암묵적 캐스팅이 생긴 경우, LIKE의 선두 와일드카드, OR 분기, 복합 인덱스의 좌측 접두사 위반, 범위 조건 뒤에 동등 조건을 둔 경우 등입니다. 원인을 분류한 뒤 쿼리 재작성 → 인덱스 추가 → 인덱스 재설계 순으로 가벼운 조치부터 시도하고, 수정 후 반드시 EXPLAIN으로 다시 검증합니다."

### Q3. "복합 인덱스 컬럼 순서는 어떻게 정하나요?"

> "선택도만 보는 게 아니라 쿼리 패턴이 우선입니다. 동등 조건으로 항상 쓰이는 컬럼을 앞에, 동등 컬럼 사이에서는 선택도가 높은 것을 앞으로, 범위 조건 컬럼을 그 뒤에, ORDER BY 컬럼을 마지막에 둡니다. 범위 조건 이후 컬럼은 인덱스로 정렬 연속성이 깨져 활용이 안 되기 때문입니다. 설계 후에는 EXPLAIN `key_len`으로 의도한 컬럼 수만큼 인덱스가 잡히는지 확인합니다."

### Q4. "커버링 인덱스는 언제 쓰나요?"

> "읽기 빈도가 매우 높고 SELECT 컬럼이 고정적인 핫 쿼리에 적용합니다. 세컨더리 인덱스 리프에는 PK가 있으므로 SELECT 대상이 모두 인덱스 안에 있으면 클러스터드 인덱스 재조회(랜덤 I/O)가 사라집니다. EXPLAIN `Extra: Using index`로 확인합니다. 다만 인덱스가 비대해지고 쓰기 비용이 늘어나므로 트래픽이 높은 조회에만 선별적으로 적용합니다."

---

## 11. 체크리스트

- [ ] `type`이 `ALL`/`index`가 아닌가
- [ ] `key`가 의도한 인덱스인가
- [ ] `key_len`이 기대한 컬럼 수만큼인가
- [ ] `Extra`에 `Using filesort` / `Using temporary`가 없는가 (또는 있어야만 하는 이유가 있는가)
- [ ] 인덱스 컬럼에 함수/연산을 씌운 곳이 없는가
- [ ] 파라미터 타입이 컬럼 타입과 정확히 일치하는가 (JPA 바인딩 포함)
- [ ] LIKE에 선두 와일드카드가 없는가
- [ ] OR을 UNION ALL로 쪼갤 수 있는가
- [ ] 복합 인덱스 좌측 접두사를 지키는가
- [ ] 범위 조건 뒤에 또 다른 동등 조건을 두지 않았는가
- [ ] ORDER BY 컬럼이 인덱스 뒷부분에 포함되는가
- [ ] `ANALYZE TABLE`로 통계가 최신인가
- [ ] 인덱스가 쓰기 부하에 비례해 과하지 않은가
- [ ] 운영 반영 시 온라인 DDL 가능한가

---

## 관련 문서

- [복합 인덱스 심화 — 좌측 접두사, 선택도, 커버링 설계](./composite-index.md)
- [EXPLAIN / EXPLAIN ANALYZE 심화 — 실행 계획 읽기](./explain-plan.md)
- [InnoDB 트랜잭션과 잠금 (MVCC, Lock)](./transaction-lock.md)
- [Redo Log](./redo-log.md)
