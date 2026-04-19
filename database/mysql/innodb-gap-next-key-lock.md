# [초안] InnoDB Gap Lock & Next-Key Lock 심층 분석 — 구간 의미론부터 실무 디버깅까지

> 이 문서는 **락의 '의미론'** 에 집중한다. MVCC 일반론은 `database/mysql/innodb-mvcc.md`, 데드락 해결/재시도/컨슈머 운영은 `database/mysql/deadlock-analysis.md`를 참고한다. 여기서는 "왜 이 범위가 잠기는가", "어떤 락이 어떤 락과 충돌하는가", "로그의 어떤 표현이 어떤 상태인가"를 끝까지 파고든다.

---

## 1. 왜 Gap / Next-Key Lock을 따로 공부해야 하는가

 InnoDB에서 "락 때문에 발생한 장애"의 대부분은 **Record Lock 자체가 아니라 Gap Lock과 Next-Key Lock의 구간 의미론을 오해한 결과**다. 대표적으로:

- "분명 WHERE로 한 건만 잡았는데 옆 레코드 INSERT가 막힌다."
- "존재하지 않는 키를 `FOR UPDATE`로 조회했는데 다른 세션 INSERT가 멈춘다."
- "같은 쿼리인데 PK 조회는 괜찮고 보조 인덱스 조회는 데드락이 난다."
- "RR에서는 터지는데 RC로 바꾸면 사라진다."
- "`SELECT ... FOR UPDATE` 두 세션이 서로 대기만 하다 한 쪽이 Deadlock으로 롤백된다."

이 모든 현상은 "InnoDB가 인덱스의 어느 구간을 어떤 모드로 잠갔는가"를 정확히 읽을 수 있으면 설명 가능하다. 반대로, 이걸 대충 이해한 상태에서 "격리 수준을 낮추자", "재시도 늘리자"로만 대응하면 같은 증상이 다른 쿼리에서 또 터진다.

면접에서 시니어 백엔드에게 기대하는 답은 "InnoDB는 RR에서 Next-Key Lock을 씁니다" 같은 외운 문장이 아니라, **"이 쿼리가 이 인덱스에서 이 범위에 이 모드의 락을 걸고, 그래서 다른 트랜잭션의 INSERT/SELECT FOR UPDATE가 이렇게 차단된다"** 를 설명하는 능력이다.

---

## 2. 선수 지식 요약 — 락의 최소 어휘

세부는 각 장에서 다루고, 여기서는 단어만 맞추고 간다.

| 용어 | 한 줄 정의 |
|---|---|
| Record Lock | 인덱스 레코드 **한 건** 자체에 걸리는 락 |
| Gap Lock | 인덱스 레코드들 **사이의 빈 공간**(gap)에 걸리는 락. 해당 gap에 새 키 삽입을 막음 |
| Next-Key Lock | Record Lock + 그 레코드 **바로 앞 gap**. 반열린 구간 `(prev, cur]` |
| Insert Intention Lock | INSERT가 특정 gap에 들어가겠다는 '의도' 락. gap lock과 충돌하지만 서로끼리는 호환 |
| Supremum (가상 레코드) | 인덱스의 '무한대' 끝을 가리키는 가상 레코드. `(last, +∞)` 구간을 표현 |
| Intention Lock (IS/IX) | 테이블 레벨 의도 락. 레코드 락과 DDL/`LOCK TABLES` 사이의 조율용 |

기억할 대전제:

- **InnoDB의 행 락은 항상 인덱스 레코드에 걸린다.** 적절한 인덱스가 없으면 클러스터드 인덱스(PK) 전 구간을 스캔하며 Next-Key Lock을 넓게 건다. "인덱스 부재 = 락 폭발"의 뿌리.
- **락은 '데이터'가 아니라 '인덱스의 위치'를 잠근다.** 같은 행이라도 PK로 접근했는지, 보조 인덱스로 접근했는지에 따라 잡히는 락 집합이 다르다.

---

## 3. 구간 표기법 — 먼저 표기부터 고정한다

InnoDB 락 로그를 읽으려면 반열린 구간 표기가 몸에 붙어야 한다. 이 문서는 아래 표기만 쓴다.

- `(a, b)` : a < x < b. 순수 Gap.
- `(a, b]` : a < x ≤ b. Next-Key Lock의 전형.
- `[a, a]` : 레코드 a 한 건. Record Lock.
- `(last, +∞)` : supremum pseudo-record까지의 마지막 gap.

예시 인덱스: `idx_amount`에 값 `10, 30, 50, 80`이 존재한다. 이 인덱스가 만드는 gap은 다음과 같다.

```
(-∞, 10)   (10, 30)   (30, 50)   (50, 80)   (80, +∞)
       [10]       [30]       [50]       [80]
```

어떤 쿼리가 "50을 Next-Key Lock" 걸었다 = `(30, 50]`을 잠갔다. 이 표기가 자동으로 떠올라야 다음 장부터 편하다.

---

## 4. Gap Lock의 본질

### 4-1. 존재 이유

Gap Lock은 **팬텀 레코드의 출현을 방지**하기 위해 존재한다. REPEATABLE READ 격리 수준에서 현재 읽기(`SELECT ... FOR UPDATE`, `UPDATE`, `DELETE`)가 같은 조건을 두 번 실행해도 새 행이 끼어들지 못하게 만드는 장치다.

MVCC만으로는 스냅샷 읽기의 팬텀만 막는다. 잠금 읽기에는 MVCC가 개입하지 않으므로 별도 방어가 필요하고, 그게 Gap Lock이다.

### 4-2. Gap Lock의 '이상한' 성질

Gap Lock은 일반 락과 직관이 다르다.

1. **Gap Lock끼리는 서로 호환된다.** 두 트랜잭션이 같은 gap에 동시에 Gap Lock을 잡을 수 있다. '서로를 배제'하는 락이 아니기 때문이다. 이 gap에 **INSERT를 못 하게 만드는 것**이 유일한 목적.
2. **Gap Lock은 'mode S/X' 구분이 거의 의미 없다.** 목적이 삽입 방지 하나뿐이라 S/X 사이 호환성도 사실상 대등하다.
3. **Gap Lock은 빼앗기지 않는다.** 트랜잭션이 커밋/롤백될 때까지 유지된다.
4. **Gap Lock은 wait-for 그래프에서 길게 꼬리를 만든다.** "누가 어떤 gap을 들고 있는지"가 겉으로 잘 안 보여서 원인 분석이 까다롭다.

### 4-3. Gap Lock vs Insert Intention Lock

이 쌍의 호환성이 실무 데드락의 중심이다.

| 상대 →<br>보유 ↓ | Gap Lock | Insert Intention |
|---|---|---|
| Gap Lock | **호환** (같은 gap 공유 가능) | **충돌** (INSERT가 대기) |
| Insert Intention | **호환** (서로 방해 안 함) | **호환** (gap 내 동시 insert 허용) |

핵심:

- 평범한 `INSERT`는 내부적으로 "이 gap에 들어갈게"라는 **Insert Intention Lock**을 먼저 요청한다.
- 누군가 이미 이 gap에 **일반 Gap Lock**을 들고 있으면 Insert Intention은 그 트랜잭션이 커밋할 때까지 대기한다.
- 그래서 "존재하지 않는 키를 `FOR UPDATE`로 조회한 세션 A" 때문에 "그 키를 INSERT하려는 세션 B"가 멈추는 현상이 발생한다.

### 4-4. Gap Lock이 잡히는 전형적 조건

RR 격리 수준에서 **보조 인덱스 범위 스캔 + 잠금 읽기** 조합이면 거의 항상 Gap Lock이 관여한다.

```sql
-- 모두 Gap Lock을 생성할 수 있는 패턴
SELECT * FROM t WHERE col BETWEEN 10 AND 20 FOR UPDATE;
SELECT * FROM t WHERE col >= 100 FOR UPDATE;
SELECT * FROM t WHERE col = 999 FOR UPDATE;  -- 보조 인덱스거나 존재하지 않는 키면 gap 발생
UPDATE t SET ... WHERE col BETWEEN 10 AND 20;
DELETE FROM t WHERE col >= 100;
```

반대로 **PK 또는 UNIQUE 인덱스로 존재하는 단일 키를 정확히 지정**하면 Gap Lock이 생략된다(9장에서 자세히). "얼핏 동일해 보이는 쿼리가 락 범위가 다른 이유"가 이 지점에 있다.

---

## 5. Next-Key Lock = Record Lock + 그 앞의 Gap

### 5-1. 구간 의미

InnoDB RR의 기본 잠금 단위는 Next-Key Lock이다. 인덱스에서 '잡은 레코드'와 그 **바로 앞 gap**을 함께 잠근다.

예시: `idx_amount`에 `10, 30, 50, 80`이 있고, 세션 A가 다음 쿼리를 실행한다.

```sql
SELECT * FROM orders WHERE amount > 40 FOR UPDATE;
```

스캔 경로상 `50`과 `80`이 걸리고, 추가로 '마지막 다음'인 supremum까지 잠긴다. 잠기는 구간은:

```
(30, 50]   -- 50 레코드의 Next-Key Lock: (이전 키 30, 50]
(50, 80]   -- 80 레코드의 Next-Key Lock
(80, +∞)   -- supremum gap: 마지막 레코드 이후 무한대까지
```

- 다른 세션이 `amount = 60`을 INSERT하려 하면 `(50, 80]`에 걸려 대기.
- `amount = 90`을 INSERT해도 supremum gap에 걸려 대기.
- `amount = 25`는 어디에도 안 걸리고 통과(잠긴 구간이 아님).

### 5-2. "왜 앞 gap을 같이 잡는가"

팬텀 방지의 방향이 '그 값이 들어올 수 있는 틈'을 함께 막는 것이기 때문이다. `amount > 40` 조건이 두 번째 스캔에서도 같은 결과를 내게 하려면, `(40, 50)` 사이 어디에도 새 행이 끼면 안 된다. 그래서 `(30, 50]`을 통째로 잡는다.

조건의 하한(40)은 인덱스에 없으므로, InnoDB는 '40을 포함할 수 있는 가장 작은 인덱스 레코드'인 50을 기준점으로 쓰고 그 앞 gap(`30~50`)까지 포함해 잠근다. 이게 Next-Key Lock의 기본 동작이다.

### 5-3. Next-Key Lock의 호환성

| 상대 →<br>보유 ↓ | S Next-Key | X Next-Key | Insert Intention |
|---|---|---|---|
| S Next-Key | 호환 | 충돌 | **충돌** |
| X Next-Key | 충돌 | 충돌 | **충돌** |
| Insert Intention | 호환 | 호환 | 호환 |

Record 부분은 일반 락 호환성을 따르고, Gap 부분은 4-3 표대로 동작한다. 둘 중 하나라도 충돌하면 전체가 대기한다.

### 5-4. 로그에서 구분하기

`SHOW ENGINE INNODB STATUS`의 `LATEST DETECTED DEADLOCK` 또는 `performance_schema.data_locks`를 볼 때:

- `lock_mode X` → Next-Key Lock (기본값, Record + Gap)
- `lock_mode X locks rec but not gap` → 순수 Record Lock (gap 제외)
- `lock_mode X locks gap before rec` → 순수 Gap Lock (그 레코드 앞의 gap만)
- `lock_mode X insert intention waiting` → Insert Intention Lock 대기 중
- `lock_mode X locks gap before rec insert intention` → Insert Intention이 gap lock과 경합 중인 상태

이 네다섯 개 표현만 정확히 구분하면 대부분의 RR 관련 잠금 로그는 읽힌다.

---

## 6. Insert Intention Lock 집중 분해

### 6-1. 역할

Insert Intention Lock은 **여러 트랜잭션이 같은 gap에 서로 다른 키로 동시 INSERT할 수 있게 하는 최적화**다. 만약 INSERT가 gap 전체를 X로 잠가버리면 병렬 INSERT 성능이 무너진다. 그래서 "나는 이 gap의 이 지점에 들어가겠다"는 약한 형태의 선언만 하고, 서로끼리는 호환시키는 구조를 택했다.

### 6-2. 충돌 규칙 (다시)

- **Gap Lock 보유 → Insert Intention 요청: 대기.** 이것이 "`FOR UPDATE`로 잡고 있으면 다른 INSERT가 멈추는" 이유.
- **Insert Intention 보유 → Gap Lock 요청: 대기하지 않음.** gap lock은 '삽입 방지'가 목적이라 이미 진행 중인 insert를 굳이 뒤에서 막지 않는다. 단, 새 insert와는 경합 구도가 만들어진다.
- **Insert Intention ↔ Insert Intention: 호환.** 같은 gap에 다른 키라면 둘 다 진행.

### 6-3. 전형 데드락: "Gap Lock 두 개 + Insert Intention 두 개"

```sql
-- idx_user에 user_id 값이 10, 20만 존재한다고 가정

-- 세션 A
BEGIN;
SELECT * FROM coupon WHERE user_id = 15 FOR UPDATE;
-- user_id=15 없음 → Gap Lock on (10, 20)

-- 세션 B
BEGIN;
SELECT * FROM coupon WHERE user_id = 15 FOR UPDATE;
-- 동일 gap에 Gap Lock → 4-2(1)에 따라 호환, 둘 다 보유

-- 세션 B
INSERT INTO coupon(user_id, ...) VALUES (15, ...);
-- Insert Intention on (10, 20) → A가 Gap Lock 보유 중이라 대기

-- 세션 A
INSERT INTO coupon(user_id, ...) VALUES (15, ...);
-- Insert Intention on (10, 20) → B도 Gap Lock 보유 중이라 대기
-- → 사이클 성립. InnoDB가 한 쪽을 데드락 희생자로 롤백
```

RR + "없는 키를 `FOR UPDATE`로 확인 후 INSERT" 패턴이 만드는 가장 흔한 데드락. 해법은 `deadlock-analysis.md` 5장 참고(`ON DUPLICATE KEY UPDATE` 원자화, RC 전환, unique index + 예외 처리 중 선택).

### 6-4. 로그 판별

```
RECORD LOCKS space id ... index idx_user of table ...
    trx id XXX lock_mode X locks gap before rec insert intention waiting
```

`insert intention waiting`이 보이면 "누군가의 Gap Lock 때문에 내 INSERT가 막힌 상태"다. 이 경우 반드시 **누가 gap lock을 들고 있는지** 를 `data_lock_waits`로 역추적해야 한다.

---

## 7. Supremum Pseudo-Record와 무한대 gap

InnoDB는 각 인덱스 페이지의 논리 끝에 **supremum**이라는 가상 레코드를 둔다. "이 인덱스의 +∞" 위치다. 범위 스캔이 인덱스의 마지막 실제 값을 지나 끝까지 가면 supremum에도 Next-Key Lock이 걸린다.

```
인덱스 값: ..., 80
Gap 구조: ..., [80], (80, +∞)   ← supremum gap
```

- `SELECT * FROM t WHERE amount > 100 FOR UPDATE` 상황에서, `amount`의 최대값이 80이면 **실제 잠기는 것은 `(80, +∞)` gap 전체**가 된다. "결과 0건인데도 락이 잡힌다"는 오해는 여기서 자주 나온다.
- 이 gap이 잡혀 있는 동안 `amount = 9999` INSERT도 대기한다. "미래에 들어올 수 있는 모든 값"을 잠그는 효과.

로그에서는 `lock_mode X` + `supremum pseudo-record` 표기로 나온다. 범위 상한이 열린(`>=`, `>`, `BETWEEN ... AND 매우 큰 값`) 쿼리는 항상 supremum 잠금을 의심해야 한다.

---

## 8. 어떤 SQL이 어떤 락을 만드는가 — 패턴 지도

RR 격리 수준, 인덱스 `idx_amount` 기준. 값이 `10, 30, 50, 80`이라 가정.

### 8-1. 범위 스캔

```sql
SELECT * FROM orders WHERE amount BETWEEN 20 AND 60 FOR UPDATE;
```

잠기는 구간:
- `(10, 30]` — 30 포함
- `(30, 50]` — 50 포함
- `(50, 80]` — 상한 60을 감싸는 다음 레코드 80까지 같이 잡힘. 이유: 60 이후 '다음 키'가 80이므로 팬텀 방지를 위해 그 앞 gap까지 필요.

실무 교훈: "BETWEEN으로 60까지"라고 썼지만, **실제로는 80까지 관여**한다. 상한 경계의 '한 칸 더' 현상.

### 8-2. 등치 검색, 값 존재

```sql
SELECT * FROM orders WHERE amount = 50 FOR UPDATE;  -- 보조 인덱스, 값 존재
```

보조 인덱스라 InnoDB는 50과 그 앞 gap `(30, 50]`을 Next-Key Lock으로 잡고, 추가로 50의 '다음 키'에서 gap `(50, 80)` 부분만 잡는다(50 다음 레코드 80은 조건 불일치이므로 레코드 락까지 가진 않음). 즉 실제 잠김:
- `(30, 50]` Next-Key
- `(50, 80)` Gap only

값이 **유일하게 하나라도** 보조 인덱스로 접근하는 한 gap이 살아남는다. 이유는 9-1.

### 8-3. 등치 검색, 값 부재

```sql
SELECT * FROM orders WHERE amount = 60 FOR UPDATE;
```

60은 없음. '60이 들어갈 자리'인 `(50, 80)` gap에만 Gap Lock. 결과 0건이지만 이 구간에 INSERT 불가. 6-3 데드락 패턴의 출발점.

### 8-4. PK 등치 검색, 값 존재

```sql
SELECT * FROM orders WHERE id = 100 FOR UPDATE;  -- PK, 존재
```

Record Lock만. `locks rec but not gap` 표기. 9-1 참고.

### 8-5. PK 등치 검색, 값 부재

```sql
SELECT * FROM orders WHERE id = 100 FOR UPDATE;  -- PK, 부재
```

그 자리의 Gap Lock만. "없는 PK를 FOR UPDATE하면 INSERT가 막힌다"의 출처.

### 8-6. 인덱스 없는 컬럼

```sql
SELECT * FROM orders WHERE memo = 'abc' FOR UPDATE;  -- memo에 인덱스 없음
```

스캔 경로가 클러스터드 인덱스(PK) 전 구간 → **테이블의 모든 PK 레코드에 Next-Key Lock**. 사실상 테이블 락과 비슷. 이게 "인덱스 없으면 락 폭발"의 정체. 옵티마이저가 커버 범위를 줄일 수 있는 경우가 예외적으로 있으나, 기본은 전 범위 잠금으로 가정한다.

### 8-7. UPDATE / DELETE

내부적으로 Current Read를 수행하며 WHERE에 해당하는 인덱스 경로에 위와 동일한 락을 건다. "읽고 쓰기" 한 번에 처리되는 것으로 보이지만 락 관점에선 Current Read + X lock이다. `UPDATE`에 WHERE 절이 없거나 인덱스를 못 타면 그대로 8-6 상황이 된다.

---

## 9. 인덱스 종류가 바꾸는 잠금 범위

### 9-1. Unique 인덱스 & 존재하는 단일 키 → Gap Lock 생략

InnoDB는 **PK 또는 UNIQUE 인덱스로 '한 건'이 확정**되는 등치 조회에서 Gap Lock을 건너뛴다. 이유는:

- Unique 인덱스는 이미 "이 키로는 하나만 있을 수 있다"는 제약을 제공한다.
- 따라서 그 한 건에 Record Lock만 걸면 팬텀이 생길 수 없다(같은 키로 또 들어올 수 없기 때문).

이 최적화 덕에 PK 기반 접근은 RR에서도 경합이 훨씬 적다. "가능하면 PK로 찍어라"의 락 관점 근거가 이것.

주의: **보조 유니크 인덱스 + 일부 케이스** 에서는 gap lock이 남을 수 있다. 클러스터드 인덱스 레코드에 접근할 때 발생하는 추가 잠금 때문인데, 단순화하여 기억하자: **PK 또는 단일 컬럼 UNIQUE로 정확히 한 건을 지정하면 대체로 안전, 나머지는 Gap Lock 있다고 가정**.

### 9-2. 존재하지 않는 키

Unique이든 아니든 **값이 없으면 Gap Lock은 반드시 생긴다**. 이유 4-1과 동일. "없는 것을 다시 조회해도 없게" 보장해야 하므로 삽입 방지가 필요.

### 9-3. 비유일 보조 인덱스

"이 값은 여러 번 올 수 있다"는 전제 → 팬텀 방지를 위해 항상 Next-Key Lock. 실무에서 락 경합 대부분이 이 경로에서 발생.

### 9-4. 인덱스 미사용 쿼리

옵티마이저가 인덱스를 안 태우면 클러스터드 인덱스 전 구간에 걸쳐 잠금 → 8-6. `EXPLAIN`에서 `type=ALL`이 보이면 즉시 경계한다.

### 9-5. 커버링 인덱스와 락

커버링 인덱스는 **읽기 IO**를 줄이지만 **락 범위를 줄이지는 않는다**. 락은 인덱스 구조상의 위치에 걸리기 때문이다. "커버링 인덱스라서 안전하다"는 오해 금지.

---

## 10. 격리 수준별 동작 차이

### 10-1. REPEATABLE READ (InnoDB 기본)

- 기본 잠금 단위 = **Next-Key Lock**.
- Gap Lock 활발. 팬텀 완전 방지 목적.
- "정합성 > 동시성" 성향. 컨슈머 패턴, 대량 insert 경합 많은 시스템에서 불리.

### 10-2. READ COMMITTED

- **Gap Lock을 원칙적으로 사용하지 않는다**(예외: 외래키 검사, `UPDATE`/`DELETE`의 semi-consistent read 중 매칭 판단 후 실패 레코드 등 일부 내부 동작).
- 잠금 단위가 사실상 Record Lock.
- 팬텀 허용. 다만 이커머스 주문 처리같이 "한 건씩 원자적으로 처리"하는 도메인에서는 대개 문제 없음.
- 성능과 인식상 단순함(락 로그 해석이 훨씬 쉬움) 측면에서 많은 서비스가 RC를 선택.

RC로 내리는 것은 만병통치약이 아니다. 팬텀을 정말 막아야 하는 배치/회계 작업에서는 RR 또는 `SERIALIZABLE` 필요. "문제 도메인별 격리 수준" 선택이 시니어의 판단 영역.

### 10-3. SERIALIZABLE

모든 `SELECT`가 암묵적으로 `LOCK IN SHARE MODE` 성격을 띠어, 모든 구간에 S Next-Key Lock. 동시성 크게 하락. 금융 정산 같은 특수 케이스에서만.

### 10-4. 바이너리 로그 / 복제와의 관계

- `binlog_format=ROW`가 기본인 현대 MySQL에서는 과거에 존재하던 '복제 안전성' 때문에 Gap Lock을 강제하던 제약이 완화됐다.
- 그러나 트리거, 외래키 검사 같은 내부 경로는 여전히 Gap Lock을 요구할 수 있다.
- STATEMENT 기반 복제를 쓰는 레거시 환경이면 Gap Lock 제거가 더 위험하므로 격리 수준 변경 전에 복제 설정을 함께 검토한다.

---

## 11. 관측 도구 — 락을 '보는' 방법

### 11-1. `performance_schema.data_locks` (MySQL 8)

```sql
SELECT ENGINE_TRANSACTION_ID AS trx_id,
       OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME,
       LOCK_TYPE,   -- RECORD / TABLE
       LOCK_MODE,   -- X, X,GAP, X,REC_NOT_GAP, X,INSERT_INTENTION, ...
       LOCK_STATUS, -- GRANTED / WAITING
       LOCK_DATA    -- 어떤 키 값인지 (supremum pseudo-record 표기도 여기)
FROM performance_schema.data_locks;
```

각 `LOCK_MODE`가 이 문서의 개념과 1:1 대응한다. 특히 `X,GAP`, `X,REC_NOT_GAP`, `X,INSERT_INTENTION` 세 표기를 빠르게 읽는 훈련을 해두면 로그 독해 속도가 두 배가 된다.

### 11-2. `performance_schema.data_lock_waits`

```sql
SELECT REQUESTING_ENGINE_TRANSACTION_ID AS waiter,
       BLOCKING_ENGINE_TRANSACTION_ID   AS holder
FROM performance_schema.data_lock_waits;
```

누가 누구의 락을 기다리는지 직접. `data_locks`와 조인해 "무엇을 기다리는지"까지 뽑아낼 수 있다.

### 11-3. `SHOW ENGINE INNODB STATUS`

`LATEST DETECTED DEADLOCK` 섹션의 의미는 `deadlock-analysis.md` 4장 참조. 이 문서 관점에서는 **각 트랜잭션이 보유/대기 중인 락의 인덱스명, 구간 표기, 모드**를 확인하는 데 집중한다.

### 11-4. `EXPLAIN`과 연계

`EXPLAIN FORMAT=JSON`의 `used_key`, `key_length`, `range_checked_for_each_record`, `Using index condition` 정보는 "어느 인덱스의 어느 범위를 스캔할지"를 말해준다. 즉 **락이 어디에 걸릴지의 예측**이 바로 이 정보다.

---

## 12. 재현 실습

### 12-1. 준비

```bash
docker run --name lock-lab -e MYSQL_ROOT_PASSWORD=pw \
  -e MYSQL_DATABASE=labs -p 3306:3306 -d mysql:8.0 \
  --transaction_isolation=REPEATABLE-READ \
  --innodb_print_all_deadlocks=ON
```

```sql
CREATE TABLE orders (
  id INT PRIMARY KEY AUTO_INCREMENT,
  amount INT NOT NULL,
  KEY idx_amount (amount)
) ENGINE=InnoDB;

INSERT INTO orders (amount) VALUES (10), (30), (50), (80);
```

### 12-2. 실습 1 — Next-Key Lock의 '한 칸 더'

세션 A:
```sql
BEGIN;
SELECT * FROM orders WHERE amount BETWEEN 20 AND 60 FOR UPDATE;
```

세션 B:
```sql
INSERT INTO orders (amount) VALUES (70);  -- (50, 80]에 걸려 대기
```

관측:
```sql
SELECT INDEX_NAME, LOCK_MODE, LOCK_DATA, LOCK_STATUS
FROM performance_schema.data_locks
WHERE OBJECT_NAME='orders';
```
세션 A의 GRANTED 락으로 `idx_amount` 상에 `30`, `50`, `80`이 각기 `X` (Next-Key) 로 찍혀 있고, 세션 B는 `X,INSERT_INTENTION` WAITING. 상한을 60으로 썼지만 80까지 관여한 점을 확인한다.

### 12-3. 실습 2 — 존재하지 않는 키의 Gap Lock

세션 A:
```sql
BEGIN;
SELECT * FROM orders WHERE amount = 60 FOR UPDATE;  -- 0건
```

세션 B:
```sql
INSERT INTO orders (amount) VALUES (55);  -- (50, 80) gap에 걸려 대기
INSERT INTO orders (amount) VALUES (85);  -- 이건 통과
```

관측: A의 락은 `X,GAP` on `80`으로 표기됨("80 레코드의 앞 gap"). A가 커밋할 때까지 `(50, 80)` gap에 INSERT 불가.

### 12-4. 실습 3 — supremum gap

세션 A:
```sql
BEGIN;
SELECT * FROM orders WHERE amount > 200 FOR UPDATE;  -- 0건
```

세션 B:
```sql
INSERT INTO orders (amount) VALUES (999);  -- 대기
```

관측: A의 `data_locks`에 `LOCK_DATA = 'supremum pseudo-record'` 표기. 결과 0건이지만 "앞으로 들어올 수 있는 모든 큰 값"이 잠겨 있음을 확인.

### 12-5. 실습 4 — PK 등치의 gap 생략

세션 A:
```sql
BEGIN;
SELECT * FROM orders WHERE id = 2 FOR UPDATE;  -- 존재
```

세션 B:
```sql
INSERT INTO orders (amount) VALUES (25);  -- 어디에도 안 걸림, 바로 성공
```

관측: A의 락이 `X,REC_NOT_GAP`. Gap 없음. PK + 존재 조건이 만드는 '평화로운 락'의 전형.

### 12-6. 실습 5 — 격리 수준 RC에서 Gap Lock 소멸

```sql
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
BEGIN;
SELECT * FROM orders WHERE amount BETWEEN 20 AND 60 FOR UPDATE;
```

관측: `data_locks`에서 Gap Lock이 대부분 사라지고 `X,REC_NOT_GAP`만 잡힘. 세션 B의 임의 INSERT가 거의 다 통과. 동시성 증가 효과를 눈으로 확인한다.

### 12-7. 실습 6 — Insert Intention 데드락 재현

6-3 시나리오를 그대로 실행해보고 `SHOW ENGINE INNODB STATUS`의 데드락 로그에서 `lock_mode X locks gap before rec insert intention waiting`이 양쪽에 찍히는 것을 확인한다. 이후 `ON DUPLICATE KEY UPDATE`로 바꾸면 사라지는 것까지 실습.

---

## 13. 실무 안티패턴과 교정

### 13-1. "있는지 보고, 없으면 INSERT"

```java
var row = repo.findByKey(key);
if (row == null) repo.insert(key, ...);
else             repo.update(row, ...);
```

문제: 두 세션이 동시에 `null`을 보고 INSERT 충돌 → Gap Lock + Insert Intention 데드락 또는 중복.

교정:
- `INSERT ... ON DUPLICATE KEY UPDATE` 또는 `INSERT IGNORE` + 후속 UPDATE.
- 업무 키에 UNIQUE 인덱스.
- RC로 낮추는 선택지는 "정말 팬텀이 문제 안 되는가" 검증 후에.

### 13-2. 인덱스 없는 `UPDATE`/`DELETE`

```sql
UPDATE user SET last_seen = NOW() WHERE ext_id = 'abc';  -- ext_id 인덱스 없음
```

클러스터드 인덱스 전 범위 Next-Key Lock. 사실상 테이블 락. 배치 중이면 서비스 전체가 느려진다. 교정: `ext_id`에 적절한 인덱스, 가능하면 UNIQUE.

### 13-3. 큐 테이블에 평범한 `FOR UPDATE`

```sql
SELECT id FROM outbox WHERE status='PENDING' ORDER BY id LIMIT 50 FOR UPDATE;
```

여러 컨슈머가 같은 구간을 두고 Gap Lock 경합. 교정: `FOR UPDATE SKIP LOCKED` 도입, 가능하면 상태 전이에 유니크 조건("claim" 컬럼)으로 원자적 점유.

### 13-4. 범위 UPDATE를 루프 밖으로 뺐다고 안심

```sql
UPDATE point SET amount = amount + 100 WHERE user_id BETWEEN 1000 AND 2000;
```

범위 내 모든 인덱스 레코드와 그 앞 gap들이 잡힘. 다른 세션의 해당 범위 insert/update 전부 대기. 배치 트랜잭션은 **짧게 쪼개고 범위를 작게**.

### 13-5. "`FOR UPDATE` 두 번"이 만드는 교차 경로

한 트랜잭션 안에서 서로 다른 순서로 두 테이블/두 인덱스에 `FOR UPDATE`를 걸면 역순 락 데드락의 완벽한 조건. 데드락 분석 문서 6장과 짝으로 볼 것.

---

## 14. 면접 답변 프레이밍

### Q1. RR에서 팬텀 리드를 어떻게 막나요? Snapshot Read와 Current Read가 왜 다르게 동작하나요?

> Snapshot Read는 MVCC Read View로 "이 트랜잭션 관점의 스냅샷"을 고정하므로 팬텀이 보이지 않습니다. Current Read(`SELECT ... FOR UPDATE`, `UPDATE`, `DELETE`)는 최신 커밋값을 읽으므로 MVCC만으로는 팬텀을 못 막습니다. 그래서 InnoDB는 Current Read에 Next-Key Lock을 걸어 **스캔 경로에 해당하는 인덱스 구간의 gap**에 새 행이 끼지 못하게 합니다. 정확히는 `(이전 키, 현재 키]` 형태의 반열린 구간을 잡는 방식입니다.

### Q2. Gap Lock끼리 호환인데 왜 Insert Intention과 충돌해서 데드락이 나나요?

> Gap Lock의 목적이 '새 행 삽입 방지'이기 때문에, 같은 목적을 가진 Gap Lock끼리는 서로를 막지 않습니다. 반면 실제 INSERT가 들어가는 Insert Intention Lock은 "gap에 값을 꽂겠다"는 의도라, gap lock과는 근본적으로 배타적입니다. 두 트랜잭션이 같은 gap에 각자 Gap Lock을 걸어둔 상태에서 서로 그 gap에 INSERT하려 하면 양쪽 Insert Intention이 상대 Gap Lock을 기다리게 되어 사이클이 생기고, 이게 RR에서 가장 자주 보는 데드락 패턴입니다.

### Q3. 존재하지 않는 키를 `FOR UPDATE`로 조회한 세션이 다른 INSERT를 막는 이유는요?

> 없는 키를 조회하더라도, "이 조건이 두 번째에도 여전히 없다"를 보장해야 팬텀이 없기 때문에 InnoDB는 그 값이 들어갈 자리에 Gap Lock을 겁니다. 예를 들어 인덱스에 50과 80만 있는데 60을 `FOR UPDATE`하면 `(50, 80)` gap이 잠깁니다. 이 상태에서 다른 세션이 55나 70을 INSERT하려 하면 Insert Intention이 Gap Lock과 충돌해 대기하게 됩니다.

### Q4. PK 조회와 보조 인덱스 조회의 락 범위가 다른 이유는 뭔가요?

> InnoDB는 PK 또는 UNIQUE 인덱스로 **단일 레코드가 확정**되는 등치 조회에서 Gap Lock을 생략합니다. 유일성 제약이 이미 팬텀 가능성을 없애주기 때문입니다. 반면 비유일 보조 인덱스는 같은 값이 또 들어올 수 있으니 팬텀 방지를 위해 앞뒤 gap까지 잠급니다. 그래서 같은 의미의 쿼리라도 PK로 찍으면 경합이 훨씬 적고, 보조 인덱스 경로는 데드락 위험이 큽니다. 단, PK 조회라도 키가 **존재하지 않으면** Gap Lock은 유지됩니다.

### Q5. 격리 수준을 RC로 내리면 어떤 락이 사라지고 어떤 위험이 새로 생기나요?

> RC에서는 원칙적으로 Gap Lock이 사라집니다. Next-Key Lock도 사실상 Record Lock으로 축소돼 동시성이 크게 올라가고 데드락 빈도도 내려갑니다. 대신 같은 조건의 조회가 트랜잭션 중 두 번 실행되면 결과 행 수가 달라질 수 있는 팬텀과 Non-Repeatable Read가 허용됩니다. 주문 한 건을 원자적으로 처리하는 이커머스 도메인은 대체로 RC로도 충분하지만, "이 조건으로 몇 건 있는지"를 트랜잭션 내에서 여러 번 참조해 판단 로직에 쓰는 경우, 배치 집계, 회계성 작업에서는 RR이 필요합니다.

### Q6. Next-Key Lock으로 인한 데드락을 어떻게 분석하시나요?

> `SHOW ENGINE INNODB STATUS`의 `LATEST DETECTED DEADLOCK`에서 두 트랜잭션 각각의 HOLDS/WAITING의 **인덱스 이름과 LOCK_MODE 표기**를 봅니다. `X`면 Next-Key, `X locks rec but not gap`이면 순수 Record, `gap before rec`이면 Gap, `insert intention waiting`이면 삽입 의도 대기입니다. 여기에 `performance_schema.data_locks`로 실제 잠긴 `LOCK_DATA`(키 값 또는 supremum)를 매핑하면 "어느 구간에서 충돌했는지"가 특정됩니다. 이후 원인을 락 순서 역전, Gap+Insert Intention, 인덱스 부재, 범위 상한의 '한 칸 더' 등 중 하나로 분류하고, 수정안은 인덱스 추가, 업무 키 UNIQUE + upsert 원자화, 격리 수준 RC 전환, 범위 축소, 트랜잭션 단축, `SKIP LOCKED` 중에서 최소 침습으로 선택합니다.

---

## 15. 자가 체크리스트

### 구간 의미론

- [ ] Record / Gap / Next-Key / Insert Intention Lock을 한 문장씩 구분해 설명할 수 있다.
- [ ] 반열린 구간 표기로 Next-Key Lock의 범위를 그릴 수 있다.
- [ ] supremum pseudo-record의 의미와 `amount > 200 FOR UPDATE`류 쿼리의 실제 잠금 범위를 설명할 수 있다.
- [ ] Gap Lock끼리 호환이지만 Insert Intention과는 충돌하는 이유를 목적 관점에서 설명할 수 있다.

### 인덱스와 락

- [ ] PK/UNIQUE의 등치 조회에서 Gap Lock이 생략되는 조건과 생략되지 않는 예외를 설명할 수 있다.
- [ ] 보조 인덱스 범위 스캔에서 상한이 '한 칸 더' 확장되는 현상을 예시로 보일 수 있다.
- [ ] 인덱스 부재 `UPDATE`/`DELETE`가 테이블 락처럼 동작하는 메커니즘을 설명할 수 있다.
- [ ] 커버링 인덱스는 읽기 IO만 줄이고 락 범위는 줄이지 않는다는 점을 말할 수 있다.

### 격리 수준

- [ ] RR vs RC에서 Gap Lock 동작 차이를 한 쿼리로 보여주는 실습을 할 수 있다.
- [ ] 도메인 관점에서 RR을 유지해야 할 때 vs RC로 낮춰도 되는 때의 기준을 제시할 수 있다.

### 관측과 로그 독해

- [ ] `performance_schema.data_locks`의 `LOCK_MODE` 표기 5가지 이상을 구분해 읽을 수 있다.
- [ ] `data_lock_waits`로 대기 관계를 추출해 `data_locks`와 조인하는 쿼리를 쓸 수 있다.
- [ ] `LATEST DETECTED DEADLOCK` 블록만 보고 HOLDS / WAITING의 인덱스·모드·키값을 짚을 수 있다.

### 실습 재현

- [ ] 12-1 실습을 처음부터 끝까지 10분 안에 재현할 수 있다.
- [ ] 12-5(RC 전환) 전후 `data_locks` 변화를 비교해 Gap Lock 소멸을 시연할 수 있다.
- [ ] 12-7의 Insert Intention 데드락을 재현하고 `ON DUPLICATE KEY UPDATE`로 제거할 수 있다.

### 실무 판단

- [ ] 큐 테이블 컨슈머 경합에 `SKIP LOCKED`를 도입해야 하는 이유를 Gap Lock 관점에서 말할 수 있다.
- [ ] "select-then-insert" 안티패턴을 Gap+Insert Intention 데드락과 연결해 설명할 수 있다.
- [ ] 범위 상한의 '한 칸 더' 현상을 고려해 BETWEEN 경계값과 배치 크기를 설계할 수 있다.
- [ ] 본인 경험(예: 복합 인덱스 튜닝으로 Next-Key Lock 범위 축소, UNIQUE 키로 중복 발급 데드락 제거)을 이 문서의 개념 용어로 설명할 수 있다.

---

*작성 기준: MySQL 8.0, InnoDB 스토리지 엔진, 기본 격리 수준 REPEATABLE READ. 연계 문서: `database/mysql/innodb-mvcc.md`(MVCC/Read View), `database/mysql/deadlock-analysis.md`(데드락 분석·재시도·컨슈머 운영).*
