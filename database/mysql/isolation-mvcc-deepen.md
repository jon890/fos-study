# [초안] MySQL 격리수준과 MVCC 심화 — 표준을 벗어난 경계 케이스와 운영 선택의 기준

> 이 문서는 "Dirty Read / Non-Repeatable Read / Phantom Read" 3원소 매트릭스를 외운 다음 단계를 다룬다. MVCC 일반론은 [InnoDB MVCC](./innodb-mvcc.md), 락 의미론은 [Gap Lock & Next-Key Lock](./innodb-gap-next-key-lock.md), 데드락 분석은 [Deadlock Analysis](./deadlock-analysis.md)를 함께 본다. 여기서는 **MVCC와 락이 충돌하는 경계**, **표준 SQL과 InnoDB가 일치하지 않는 지점**, **격리수준 변경이 실제로 무엇을 바꾸는가**를 끝까지 파고든다.

---

## 1. 왜 한 번 더 깊이 들어가야 하는가

격리수준 표를 외운 백엔드 개발자는 많다. 그러나 다음 질문에 즉답할 수 있는 사람은 드물다.

- 동일한 트랜잭션 안에서 `SELECT`와 `UPDATE`의 결과가 어긋날 수 있는 이유는 무엇인가.
- `REPEATABLE READ`에서 Lost Update가 여전히 발생할 수 있는 시나리오는 무엇인가.
- Write Skew는 MySQL InnoDB에서 어떤 격리수준까지 살아남는가.
- READ COMMITTED가 UPDATE의 매칭 동작을 변화시키는 "Semi-Consistent Read"는 정확히 무엇인가.
- 격리수준을 낮추면 동시성이 좋아진다는데, 무엇이 좋아지고 무엇이 위험해지는가.

이 다섯 질문은 모두 "MVCC 스냅샷이 만드는 가시성"과 "락이 만드는 직렬화"의 경계에서 발생한다. 표준 SQL 정의로는 설명되지 않고, InnoDB의 실제 구현 동작까지 알아야 답이 나온다. 그리고 면접에서 시니어 백엔드에게 기대하는 깊이가 정확히 여기에 있다.

운영에서 격리수준은 단순히 "기본값을 쓴다"가 아니라 **도메인별 트레이드오프 선택**이다. 결제 멱등성, 쿠폰 선착순, 재고 차감, 회계성 배치, 큐 컨슈머는 모두 다른 격리수준 정책이 적합하다. 이 문서는 그 선택의 근거를 제공한다.

---

## 2. 표준 SQL vs InnoDB의 실제 매트릭스

### 2-1. 표준 SQL의 4가지 격리수준

표준이 정의하는 것은 "허용되는 이상 현상"이지 구현 방식이 아니다.

| 격리수준 | Dirty Read | Non-Repeatable Read | Phantom Read | Lost Update | Write Skew | Read Skew |
|---|---|---|---|---|---|---|
| READ UNCOMMITTED | 허용 | 허용 | 허용 | 허용 | 허용 | 허용 |
| READ COMMITTED | 금지 | 허용 | 허용 | 허용 | 허용 | 허용 |
| REPEATABLE READ | 금지 | 금지 | **허용** | 금지(*) | 허용 | 금지 |
| SERIALIZABLE | 금지 | 금지 | 금지 | 금지 | 금지 | 금지 |

(\*) "표준은 RR에서 Lost Update를 금지하지 않는다"는 해석도 있으나, ANSI SQL-92 정의를 엄격히 보면 RR은 직렬 스케줄과 등가여야 하므로 Lost Update도 막혀야 한다. 구현이 실제로 그러한지는 별개.

### 2-2. InnoDB의 실제 동작

InnoDB가 표준에서 벗어나는 핵심 두 지점:

1. **REPEATABLE READ에서 Phantom Read를 막는다.** 표준은 RR에서 팬텀을 허용하지만, InnoDB는 Next-Key Lock으로 잠금 읽기의 팬텀까지 제거한다. 일관 읽기는 MVCC가 막고, 잠금 읽기는 Gap Lock이 막는다. 결과적으로 InnoDB의 RR은 표준 RR보다 강하다.
2. **REPEATABLE READ에서 Write Skew는 여전히 살아 있다.** 같은 트랜잭션에서 서로 다른 행을 읽고-쓰는 패턴은 MVCC만으로는 막을 수 없다. "내가 본 시점의 동료들 휴가 상태"가 "내가 휴가를 신청하는 시점"의 사실과 다를 수 있다.

표를 다시 그리면:

| 격리수준 | Dirty | Non-Repeatable | Phantom (Snapshot) | Phantom (Current) | Lost Update | Write Skew |
|---|---|---|---|---|---|---|
| READ UNCOMMITTED | 허용 | 허용 | 허용 | 허용 | 허용 | 허용 |
| READ COMMITTED | 금지 | 허용 | 허용 | 허용 | 허용 | 허용 |
| **InnoDB REPEATABLE READ** | 금지 | 금지 | 금지 | **금지**(Next-Key Lock) | 조건부 발생 | **허용** |
| SERIALIZABLE | 금지 | 금지 | 금지 | 금지 | 금지 | 금지 |

"조건부 발생"의 의미는 5장에서 다룬다.

---

## 3. Read View 재생성 타이밍의 세부 동작

### 3-1. 두 격리수준의 결정적 차이

`REPEATABLE READ`와 `READ COMMITTED`의 차이를 한 문장으로 압축하면 **"Read View를 언제 새로 만드는가"** 다.

- RR: 트랜잭션 안에서 첫 번째 일관 읽기(`SELECT`) 시점에 Read View가 만들어지고 트랜잭션이 끝날 때까지 재사용된다.
- RC: 일관 읽기 문장마다 새 Read View가 만들어진다.

이 한 줄 차이가 만드는 결과:

```sql
-- 격리수준 = REPEATABLE READ
START TRANSACTION;

SELECT balance FROM account WHERE id = 1;
-- 첫 SELECT. 여기서 Read View 생성. balance = 1000

-- 다른 세션이 balance를 500으로 갱신하고 커밋

SELECT balance FROM account WHERE id = 1;
-- 같은 Read View 재사용. 여전히 1000

SELECT balance FROM account WHERE id = 1 FOR UPDATE;
-- 현재 읽기(Current Read). Read View 무시. 500
COMMIT;
```

```sql
-- 격리수준 = READ COMMITTED
START TRANSACTION;

SELECT balance FROM account WHERE id = 1;
-- 새 Read View. balance = 1000

-- 다른 세션이 balance를 500으로 갱신하고 커밋

SELECT balance FROM account WHERE id = 1;
-- 또 새 Read View. balance = 500 (Non-Repeatable Read 발생)
COMMIT;
```

### 3-2. "START TRANSACTION 시점에는 Read View가 만들어지지 않는다"

흔한 오해. `START TRANSACTION` 자체는 트랜잭션 ID만 할당하거나(또는 그것도 안 하고) 비워둔다. Read View는 **첫 번째 일관 읽기**가 발생할 때 만들어진다.

이 시점 차이가 만드는 결과:

```sql
START TRANSACTION;
-- 이 시점: Read View 없음

-- 다른 세션 X가 트랜잭션을 시작하고 데이터를 변경하고 커밋
-- 그 사이 또 다른 세션 Y도 같은 데이터를 변경하고 커밋

SELECT * FROM t WHERE ...;
-- 이 시점에서 Read View 최초 생성
-- 그 결과: X, Y의 커밋이 모두 보인다
```

만약 `START TRANSACTION READ ONLY` 또는 `START TRANSACTION WITH CONSISTENT SNAPSHOT`을 쓰면 트랜잭션 시작 시점에 Read View가 즉시 만들어진다. 배치/리포트 트랜잭션에서 "정확히 이 순간의 스냅샷이 필요하다"고 명시할 때 사용한다.

```sql
-- 시작 즉시 스냅샷 고정
START TRANSACTION WITH CONSISTENT SNAPSHOT;
SELECT ...;
SELECT ...;
COMMIT;
```

### 3-3. 한 트랜잭션 안의 SELECT와 UPDATE가 어긋나는 메커니즘

```sql
-- RR
START TRANSACTION;

SELECT balance FROM account WHERE id = 1;
-- Read View 시점의 스냅샷. balance = 1000

-- 다른 세션이 balance = 500으로 갱신하고 커밋

UPDATE account SET balance = balance - 200 WHERE id = 1;
-- UPDATE는 Current Read. 현재 커밋된 500을 읽고, 거기서 200을 뺀다.
-- 결과: balance = 300 (1000 - 200 = 800이 아님)

SELECT balance FROM account WHERE id = 1;
-- 같은 Read View 재사용 → 1000. 그러나 UPDATE 이후이므로 자신이 만든 버전(300)이 보인다.
-- 결과: 300

COMMIT;
```

같은 트랜잭션의 `SELECT`(1000)와 `UPDATE`의 계산 기준(500)이 어긋난 채로 진행됐다. 이 어긋남이 Lost Update의 근본 원인이다.

---

## 4. Lost Update — RR에서도 발생한다

### 4-1. Lost Update의 정의

두 트랜잭션이 같은 행을 동시에 갱신할 때, 한쪽의 변경이 다른 쪽의 변경에 의해 덮어쓰여 사라지는 현상.

### 4-2. RR에서의 시나리오 1: "읽고 계산해서 다시 쓰기"

```sql
-- 잘못된 패턴: 일관 읽기로 현재값을 읽고 애플리케이션에서 계산
-- 격리수준 RR

-- 세션 A
START TRANSACTION;
SELECT balance FROM account WHERE id = 1;
-- 1000

-- 세션 B
START TRANSACTION;
SELECT balance FROM account WHERE id = 1;
-- 1000 (서로 다른 Read View, 동일한 커밋값 봄)

-- 세션 A: 애플리케이션에서 1000 - 100 = 900 계산
UPDATE account SET balance = 900 WHERE id = 1;
COMMIT;

-- 세션 B: 애플리케이션에서 1000 - 200 = 800 계산
UPDATE account SET balance = 800 WHERE id = 1;
-- 세션 A의 X락이 풀린 후 진행. 800으로 덮어쓴다.
COMMIT;

-- 최종 balance = 800. 세션 A의 차감 100이 사라짐 (Lost Update)
```

InnoDB의 RR은 Lost Update를 직접적으로 막지 않는다. UPDATE는 행 락을 잡지만, 그 사이에 다른 트랜잭션의 SELECT가 먼저 끝나고 자신만의 계산 결과로 쓰기를 한다면 두 갱신이 순차적으로 적용되며 한쪽이 묻힌다.

### 4-3. RR에서의 시나리오 2: SQL 안에서 계산하면 안전

```sql
-- 올바른 패턴: 표현식으로 원자 갱신

-- 세션 A
START TRANSACTION;
UPDATE account SET balance = balance - 100 WHERE id = 1;
-- Current Read: 최신값 1000을 잠그고 읽음 → 900으로 쓰기
COMMIT;

-- 세션 B
START TRANSACTION;
UPDATE account SET balance = balance - 200 WHERE id = 1;
-- 세션 A 커밋 후: 최신값 900을 잠그고 읽음 → 700으로 쓰기
COMMIT;

-- 최종 balance = 700. 정확.
```

`balance = balance - 100` 표현식이 UPDATE 안에 있으면 Current Read로 최신값을 잠그고 그 값을 기준으로 계산하므로 Lost Update가 없다. **"읽고 → 애플리케이션 계산 → 쓰기"가 위험하고, "SQL 표현식으로 원자 갱신"이 안전하다.**

### 4-4. 명시적 잠금 패턴

표현식 갱신이 불가능한 경우(조건 분기, 외부 호출 결과 사용)는 `FOR UPDATE`로 명시적 잠금.

```sql
-- 세션 A, B 모두
START TRANSACTION;
SELECT balance FROM account WHERE id = 1 FOR UPDATE;
-- 한쪽이 X락을 잡으면 다른 쪽은 대기

-- 애플리케이션 검증 (잔액 부족 체크 등)

UPDATE account SET balance = balance - X WHERE id = 1;
COMMIT;
```

`FOR UPDATE`는 Current Read이므로 최신 커밋값을 읽으면서 동시에 X락을 잡는다. 다른 세션의 동일 행 잠금 시도는 대기한다.

### 4-5. 낙관적 잠금 패턴

분산 환경, 락 보유 시간을 짧게 가져가야 하는 경우는 버전 컬럼 + WHERE 조건으로 충돌 검출.

```sql
-- account 테이블에 version 컬럼 추가
-- 세션 A
SELECT balance, version FROM account WHERE id = 1;
-- balance = 1000, version = 5

-- 애플리케이션 계산: 900

UPDATE account SET balance = 900, version = 6
WHERE id = 1 AND version = 5;
-- 영향받은 행이 1이면 성공. 0이면 다른 세션이 먼저 갱신함 → 재시도 또는 사용자에게 통지
```

낙관적 잠금은 충돌이 드물 때 유리하고, 충돌이 잦으면 재시도 비용이 비관적 잠금보다 커진다. 도메인의 충돌 빈도로 선택한다.

---

## 5. Write Skew — MVCC의 진짜 한계

### 5-1. 정의

두 트랜잭션이 **서로 다른 행**을 읽고 갱신하는데, 각각이 본 스냅샷에서는 정합성 규칙(불변 조건)이 만족되지만 두 트랜잭션이 모두 커밋된 후의 결과에서는 불변 조건이 깨지는 현상.

### 5-2. 의사 예제 — 당직 인원수 보장

규칙: "당직 중인 의사가 최소 1명은 있어야 한다."

```sql
CREATE TABLE doctor (
  id INT PRIMARY KEY,
  name VARCHAR(50),
  on_call BOOLEAN
);
INSERT INTO doctor VALUES (1, 'Alice', TRUE), (2, 'Bob', TRUE);
```

```sql
-- 격리수준 RR
-- 세션 A (Alice가 당직 빠지려 함)
START TRANSACTION;
SELECT COUNT(*) FROM doctor WHERE on_call = TRUE;
-- Read View 시점의 스냅샷: 2. 1명이 빠져도 1명이 남으니 OK.

-- 세션 B (Bob도 동시에 당직 빠지려 함)
START TRANSACTION;
SELECT COUNT(*) FROM doctor WHERE on_call = TRUE;
-- Read View 시점의 스냅샷: 2. 1명이 빠져도 1명이 남으니 OK.

-- 세션 A
UPDATE doctor SET on_call = FALSE WHERE id = 1;
COMMIT;

-- 세션 B
UPDATE doctor SET on_call = FALSE WHERE id = 2;
COMMIT;

-- 최종: 당직 0명. 불변 조건 위반.
```

두 트랜잭션이 갱신한 행은 서로 다르다(`id=1` vs `id=2`). 행 락은 충돌하지 않는다. 그러나 "전체 당직 수"라는 집합 수준의 불변 조건이 깨졌다. 이게 Write Skew다.

### 5-3. InnoDB RR에서 Write Skew가 살아남는 이유

Write Skew를 막으려면 "내가 읽은 데이터가 그 시점의 사실이 아직도 사실인가"를 검증할 메커니즘이 필요하다. MVCC는 이를 제공하지 않는다. Read View는 시점만 고정하고, 다른 트랜잭션의 행 변경에 대한 검증을 트리거하지 않는다.

SERIALIZABLE은 모든 SELECT를 `LOCK IN SHARE MODE`로 만들어 Write Skew를 막는다. 그러나 동시성이 크게 떨어진다.

### 5-4. RR + 명시적 잠금으로 해결

Write Skew는 "이 SELECT가 본 데이터가 다른 트랜잭션에 의해 변하지 않는다"를 보장하면 막을 수 있다.

```sql
-- 격리수준 RR
-- 세션 A, B 둘 다
START TRANSACTION;
SELECT COUNT(*) FROM doctor WHERE on_call = TRUE FOR UPDATE;
-- 모든 on_call=TRUE 행에 X락. Gap Lock 포함.

-- 둘 중 먼저 들어온 쪽이 진행
UPDATE doctor SET on_call = FALSE WHERE id = ...;
COMMIT;
-- 나머지 쪽은 SELECT FOR UPDATE에서 대기 → 깨어난 후 COUNT = 1을 보고 거부
```

이 패턴은 잠금 범위가 넓어서 동시성이 낮아진다. 도메인의 핫스팟이면 차라리 단일 마스터 락(전용 락 행) 패턴으로 직렬화하는 것이 유지보수에 유리하다.

### 5-5. "물질화 충돌(Materializing Conflicts)" 패턴

Write Skew를 행 락만으로 막기 어려운 케이스는 충돌점을 별도 행으로 물질화한다.

```sql
-- 위 의사 당직 예제에서 'on_call_shift' 행을 만들고 모든 변경 전에 잠금
SELECT * FROM on_call_shift WHERE shift_id = 'today' FOR UPDATE;
-- 이 행 X락 → 두 트랜잭션이 직렬화됨
-- 이후 COUNT 검증 및 UPDATE 진행
```

도메인 모델에 "이 정책 결정의 단일 잠금 포인트"를 명시적으로 두는 방식이다. 코드 복잡도 비용이지만 동시성과 정합성을 둘 다 잡는 정형 패턴.

---

## 6. Semi-Consistent Read — RC만의 UPDATE 매칭 동작

### 6-1. 정의

`READ COMMITTED` 격리수준에서 `UPDATE`가 WHERE 조건의 행을 잠그려 할 때, 잠긴 행이 이미 다른 트랜잭션에 의해 변경되어 자신의 WHERE 조건과 일치하지 않을 가능성이 있으면, InnoDB는 그 행을 잠그지 않고 건너뛴다. "Semi-Consistent"라는 이름은 "엄밀한 Current Read는 아니지만, MVCC 스냅샷보다는 최신"이라는 의미다.

RR에서는 활성화되지 않는다. RR에서 `UPDATE`는 WHERE 매칭 행을 모두 X락으로 잠그고, 자신의 작업이 완전히 끝날 때까지 다른 트랜잭션의 갱신을 막는다.

### 6-2. 시나리오

```sql
-- 격리수준 RC
-- 데이터: status가 'PENDING'인 주문이 100건

-- 세션 A
START TRANSACTION;
UPDATE orders SET worker_id = 'A' WHERE status = 'PENDING' LIMIT 10;
-- 10건을 잠그고 worker_id = 'A'로 갱신, 아직 커밋 안 함

-- 세션 B
START TRANSACTION;
UPDATE orders SET worker_id = 'B' WHERE status = 'PENDING' LIMIT 10;
-- 세션 A가 잠근 10건은 status가 곧 'PROCESSING'으로 바뀔 수도 있다.
-- RC의 Semi-Consistent Read: 잠긴 행을 일시적으로 스킵하고 다음 매칭 행을 찾는다.
-- 세션 A가 잠근 10건은 건너뛰고, 그다음 10건(11~20번째)을 잠근다.
-- → 데드락이나 긴 대기 없이 동시 진행 가능
```

같은 시나리오를 RR에서 실행하면 세션 B는 세션 A가 잠근 행을 만나는 순간 대기한다. 세션 A가 커밋해야 풀린다. 큐 컨슈머가 다수 동시에 PENDING을 처리해야 하는 환경에서는 RC + Semi-Consistent Read 조합이 처리량을 크게 올린다.

### 6-3. 운영 함의

큐 워커, 멀티 컨슈머 배치, 알림 발송같이 "조건에 맞는 행 N개를 가져와 처리"하는 패턴은 RC가 자연스럽다. RR로 같은 패턴을 구현하면 잠금 대기로 직렬화되거나 데드락이 빈발한다.

더 명시적인 선택지는 `FOR UPDATE SKIP LOCKED`다.

```sql
SELECT id FROM orders WHERE status = 'PENDING'
ORDER BY id LIMIT 10
FOR UPDATE SKIP LOCKED;
```

이는 격리수준과 무관하게 "잠긴 행은 건너뛰고 다음 행을 잠근다"는 의미를 명확히 한다. MySQL 8.0+에서 사용 가능. 큐 워커 패턴의 표준이다.

---

## 7. UPDATE의 WHERE 조건은 어느 시점의 데이터에 적용되는가

### 7-1. RR에서의 동작

```sql
-- 격리수준 RR
START TRANSACTION;
SELECT * FROM orders WHERE amount > 10000;
-- Read View 시점의 스냅샷에서 5건 반환

-- 다른 세션이 새 주문 (amount = 20000) 1건 INSERT + COMMIT

UPDATE orders SET status = 'BIG' WHERE amount > 10000;
-- 영향받은 행: 6건
-- "내가 본 5건"이 아니라 "현재 최신 커밋의 6건"이 갱신된다.
```

RR의 일관 읽기는 스냅샷이지만, `UPDATE`의 매칭은 Current Read다. 같은 트랜잭션 안에서 SELECT가 본 결과집합과 UPDATE가 갱신하는 결과집합이 다를 수 있다.

### 7-2. 면접 빈출 질문

> "RR 트랜잭션 안에서 SELECT는 5건인데 UPDATE는 6건을 갱신했다. 왜?"

답:

> SELECT는 MVCC 일관 읽기이므로 트랜잭션 첫 SELECT 시점의 Read View로 스냅샷을 봅니다. 그 사이에 다른 트랜잭션이 새 행을 INSERT하고 커밋했더라도 SELECT 결과에는 보이지 않습니다. 반면 UPDATE는 Current Read로 동작합니다. 최신 커밋 상태의 인덱스를 스캔하면서 매칭 행을 잠그고 갱신합니다. 따라서 새로 들어온 행도 UPDATE 대상에 포함됩니다. 이게 RR에서 SELECT와 UPDATE의 결과 행 수가 어긋날 수 있는 메커니즘입니다. 정합성을 보장하려면 처음부터 `SELECT ... FOR UPDATE`로 잠금 읽기를 하거나, Next-Key Lock이 작동하도록 인덱스가 잡힌 범위 조건으로 잠가야 합니다.

### 7-3. 인덱스가 없으면 어떻게 되는가

WHERE 조건이 인덱스를 타지 못하면 클러스터드 인덱스 전 범위를 스캔하면서 매칭을 검사한다. RR이면 모든 행에 Next-Key Lock이 걸린다. 사실상 테이블 락이다. 자세히는 [Gap Lock 문서 8-6](./innodb-gap-next-key-lock.md) 참고.

---

## 8. 격리수준 선택 의사결정 트리

### 8-1. 도메인별 추천 매트릭스

| 도메인 | 추천 격리수준 | 이유 |
|---|---|---|
| 결제 멱등성 / 잔액 차감 | RC + FOR UPDATE 또는 RR + 표현식 갱신 | 단일 행 정합성. 표현식 갱신이면 RC도 안전. |
| 큐 컨슈머 / 배치 워커 | RC (+ SKIP LOCKED) | Semi-Consistent Read 활용, 잠금 대기 최소화. |
| 회계 일/월마감 배치 | RR + WITH CONSISTENT SNAPSHOT | 시점 고정된 정합 스냅샷 필요. |
| 쿠폰 선착순 발급 | RC + UNIQUE 키 + 멱등 INSERT | RR의 Gap Lock 데드락 회피. |
| 재고 차감 | RR/RC 모두 가능, SQL 표현식 + 조건 차감 | `stock = stock - 1 WHERE stock > 0`. |
| 통계/리포트 | RR + WITH CONSISTENT SNAPSHOT | 긴 SELECT 동안 일관 시점 유지. |
| 사용자 프로필 단순 CRUD | 기본값(RR) | 별도 고려 불필요. |

### 8-2. 결정 트리

```text
1. 트랜잭션이 같은 조건을 두 번 이상 SELECT 하는가?
   YES → 결과 일관성이 필요한가?
     YES → RR (또는 WITH CONSISTENT SNAPSHOT)
     NO  → RC
   NO  → 2번으로

2. 트랜잭션이 "있는지 확인하고 없으면 INSERT" 패턴을 쓰는가?
   YES → RC + UNIQUE 키 + INSERT ... ON DUPLICATE KEY UPDATE 추천
        (RR의 Gap+Insert Intention 데드락 회피)
   NO  → 3번으로

3. 트랜잭션이 큐 컨슈머(조건에 맞는 N건 처리) 패턴인가?
   YES → RC (+ SKIP LOCKED)
   NO  → 4번으로

4. 트랜잭션이 집합 수준 불변 조건(여러 행의 합/개수 등)에 의존하는가?
   YES → SERIALIZABLE 또는 명시적 잠금 + 물질화 충돌 패턴
   NO  → 기본 RR
```

### 8-3. 격리수준을 낮출 때 점검할 것

- 같은 트랜잭션 안에서 SELECT 두 번 + 그 결과로 분기하는 코드가 있는가? Non-Repeatable Read의 직접 영향권.
- UPDATE의 매칭 동작이 다른 워커와 충돌해도 되는가? Semi-Consistent Read는 "다른 워커가 잠근 행을 무시"하는데, 그게 비즈니스적으로 의도된 동작인가.
- 외래키 / 트리거 / 복제 설정이 격리수준 변경에 영향을 주는가? `binlog_format=ROW`라면 영향 적음. `STATEMENT`라면 검토 필요.

격리수준 변경은 격리수준 변경만으로 끝나지 않는다. **잠금 패턴이 함께 바뀐다.** 코드 리뷰에서 `@Transactional(isolation = ...)`을 변경하는 PR이 보이면 잠금 측면까지 검토해야 한다.

---

## 9. Spring 트랜잭션과의 연결

### 9-1. `@Transactional(isolation = ...)` 명시

```java
@Transactional(isolation = Isolation.READ_COMMITTED)
public void claimNextPendingOrders() {
    // RC + Semi-Consistent Read 의도적 활용
    List<Order> orders = orderRepo.findTopByStatusOrderByIdSkipLocked(
        OrderStatus.PENDING, 10);
    // ...
}
```

JPA / Hibernate 환경에서 격리수준은 트랜잭션 매니저가 JDBC `Connection.setTransactionIsolation()`으로 설정한다. 트랜잭션 시작 시 1회. 트랜잭션 중간에 바꿀 수 없다.

### 9-2. `Propagation.REQUIRES_NEW`와 격리수준

```java
@Transactional(propagation = Propagation.REQUIRES_NEW,
               isolation = Isolation.READ_COMMITTED)
public void recordFailureLog(...) {
    // 외부 호출 실패 로그를 별도 트랜잭션으로 격리
    // 부모 트랜잭션이 RR이어도 이 메서드는 RC로 동작
}
```

REQUIRES_NEW로 분리된 트랜잭션은 부모와 독립적으로 격리수준을 가질 수 있다. Outbox 실패 메시지 저장 같은 패턴에서 유용하다. 관련 흐름은 [Spring 트랜잭션 전파 문서](../../java/spring/transaction-propagation-isolation-after-commit.md) 참고.

### 9-3. 긴 일관 읽기 트랜잭션의 함정

```java
@Transactional(readOnly = true)
public Report generateMonthlyReport() {
    // 30분 걸리는 집계 트랜잭션
    // RR이면: 트랜잭션 시작 시점 Read View 고정 → Undo Log 비대화 위험
}
```

`readOnly = true`는 트랜잭션의 일관성을 보장하기 위해 RR + WITH CONSISTENT SNAPSHOT처럼 동작할 수 있다. 긴 readOnly 트랜잭션은 Undo Log Purge를 막아 디스크 증가와 쓰기 성능 저하를 부른다.

대안:

- 보고서 생성을 별도 데이터 마트로 분리.
- 청크 단위로 트랜잭션을 쪼개고 각 청크 사이에 잠시 트랜잭션을 끊는다.
- 읽기 전용 리플리카로 라우팅.

---

## 10. 실습 환경과 시나리오

### 10-1. Docker로 MySQL 8 띄우기

```bash
docker run --name iso-lab \
  -e MYSQL_ROOT_PASSWORD=password \
  -e MYSQL_DATABASE=isotest \
  -p 3306:3306 -d mysql:8.0 \
  --transaction_isolation=REPEATABLE-READ \
  --innodb_print_all_deadlocks=ON

mysql -h 127.0.0.1 -P 3306 -u root -ppassword isotest
```

### 10-2. 실습용 스키마

```sql
CREATE TABLE account (
  id INT PRIMARY KEY,
  owner VARCHAR(50),
  balance INT NOT NULL,
  version INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT INTO account VALUES (1, 'Alice', 1000, 0), (2, 'Bob', 1000, 0);

CREATE TABLE doctor (
  id INT PRIMARY KEY,
  name VARCHAR(50),
  on_call BOOLEAN NOT NULL
) ENGINE=InnoDB;
INSERT INTO doctor VALUES (1, 'Alice', TRUE), (2, 'Bob', TRUE);

CREATE TABLE outbox (
  id INT PRIMARY KEY AUTO_INCREMENT,
  payload VARCHAR(200),
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  worker_id VARCHAR(50)
) ENGINE=InnoDB;
INSERT INTO outbox (payload) VALUES ('a'),('b'),('c'),('d'),('e'),('f');
```

### 10-3. 실습 1 — Lost Update 재현

세션 A, B를 별도 터미널로 연다.

```sql
-- 세션 A
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION;
SELECT balance FROM account WHERE id = 1;
-- 1000
```

```sql
-- 세션 B
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION;
SELECT balance FROM account WHERE id = 1;
-- 1000
```

```sql
-- 세션 A
UPDATE account SET balance = 900 WHERE id = 1;  -- 애플리케이션 계산값
COMMIT;
```

```sql
-- 세션 B
UPDATE account SET balance = 800 WHERE id = 1;  -- 자기 계산값
COMMIT;
SELECT balance FROM account WHERE id = 1;
-- 800. 세션 A의 -100 차감이 사라짐.
```

해결판 실습:

```sql
-- 두 세션 모두
SELECT balance FROM account WHERE id = 1 FOR UPDATE;
UPDATE account SET balance = balance - 100 WHERE id = 1;
```

`FOR UPDATE` 또는 SQL 표현식 갱신으로 같은 시나리오를 재현하고 최종 balance가 정확히 800(1000-100-100)이 되는지 확인한다.

### 10-4. 실습 2 — Write Skew 재현

```sql
-- 세션 A
START TRANSACTION;
SELECT COUNT(*) FROM doctor WHERE on_call = TRUE;
-- 2

-- 세션 B
START TRANSACTION;
SELECT COUNT(*) FROM doctor WHERE on_call = TRUE;
-- 2

-- 세션 A
UPDATE doctor SET on_call = FALSE WHERE id = 1;
COMMIT;

-- 세션 B
UPDATE doctor SET on_call = FALSE WHERE id = 2;
COMMIT;

SELECT COUNT(*) FROM doctor WHERE on_call = TRUE;
-- 0. 불변 조건 깨짐.
```

해결판:

```sql
-- 두 세션 모두
START TRANSACTION;
SELECT * FROM doctor WHERE on_call = TRUE FOR UPDATE;
-- 행 잠금 + Gap Lock
-- 비즈니스 검증: COUNT - 1 >= 1 인지 확인
UPDATE doctor SET on_call = FALSE WHERE id = ?;
COMMIT;
```

### 10-5. 실습 3 — Semi-Consistent Read 효과 비교

```sql
-- 세션 A (RR 모드)
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION;
UPDATE outbox SET worker_id = 'A', status = 'PROCESSING'
WHERE status = 'PENDING' LIMIT 3;

-- 세션 B (RR 모드)
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION;
UPDATE outbox SET worker_id = 'B', status = 'PROCESSING'
WHERE status = 'PENDING' LIMIT 3;
-- 세션 A의 X락 때문에 대기.
```

```sql
-- 세션 A 롤백 후 RC 모드로 재시도
ROLLBACK;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
UPDATE outbox SET worker_id = 'A', status = 'PROCESSING'
WHERE status = 'PENDING' LIMIT 3;

-- 세션 B도 RC로
ROLLBACK;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
UPDATE outbox SET worker_id = 'B', status = 'PROCESSING'
WHERE status = 'PENDING' LIMIT 3;
-- 즉시 진행. Semi-Consistent Read가 세션 A의 잠긴 행을 건너뛰고 다음 행을 잠근다.
```

각 세션이 잠근 행을 확인:

```sql
SELECT id, worker_id, status FROM outbox ORDER BY id;
```

### 10-6. 실습 4 — WITH CONSISTENT SNAPSHOT

```sql
-- 터미널 1
START TRANSACTION WITH CONSISTENT SNAPSHOT;
-- 즉시 Read View 생성. 아직 SELECT를 하지 않았어도.
SELECT NOW();
-- 천천히 다른 작업 진행

-- 터미널 2 (이 사이)
INSERT INTO outbox (payload) VALUES ('z');
COMMIT;

-- 터미널 1
SELECT * FROM outbox WHERE payload = 'z';
-- 0건. 트랜잭션 시작 시점에 없었으므로 보이지 않음.
COMMIT;
```

`START TRANSACTION` 단독이었으면 첫 SELECT 시점에 Read View가 만들어져 'z'가 보였을 것이다. 시점 고정 차이를 직접 관찰한다.

---

## 11. 흔한 오해 8가지

### 오해 1: "InnoDB의 RR은 표준 SQL의 RR과 같다"

다르다. 표준은 RR에서 Phantom Read를 허용하지만, InnoDB는 Next-Key Lock으로 잠금 읽기의 팬텀까지 막는다. 강한 RR이다.

### 오해 2: "RR이면 Lost Update가 발생하지 않는다"

발생한다. "읽고 → 애플리케이션 계산 → 쓰기" 패턴은 RR에서도 Lost Update가 가능하다. 표현식 갱신이나 `FOR UPDATE`, 낙관적 잠금 중 하나로 막아야 한다.

### 오해 3: "격리수준을 SERIALIZABLE로 올리면 모든 동시성 문제가 해결된다"

해결은 되지만 동시성이 거의 사라진다. 모든 SELECT가 S락을 잡고, 다른 트랜잭션의 X락 시도가 모두 대기한다. 실용성이 낮다. 대신 핫스팟에 명시적 잠금이나 단일 마스터 락을 두는 것이 현실적.

### 오해 4: "Read View는 START TRANSACTION 시점에 만들어진다"

기본 `START TRANSACTION`에서는 첫 일관 읽기 시점에 만들어진다. `WITH CONSISTENT SNAPSHOT`이 붙으면 그 즉시 만들어진다.

### 오해 5: "같은 트랜잭션의 SELECT와 UPDATE는 같은 데이터를 본다"

다르다. SELECT(일관 읽기)는 스냅샷을 보고, UPDATE는 Current Read로 최신 커밋을 본다. 같은 트랜잭션 안에서 결과가 어긋날 수 있다.

### 오해 6: "RC로 내리면 무조건 성능이 좋아진다"

대체로 잠금 경합과 데드락이 줄어 처리량이 오르지만, 같은 조건의 SELECT를 두 번 하는 코드, 집합 불변 조건을 가정한 코드는 새 종류의 정합성 버그를 만들 수 있다. 코드 패턴과 함께 변경 영향을 평가해야 한다.

### 오해 7: "Write Skew는 RR에서는 발생하지 않는다"

발생한다. MVCC는 행 단위 가시성만 다루고, 집합 수준 불변 조건은 보호하지 않는다. SERIALIZABLE 또는 명시적 잠금 / 물질화 충돌 패턴이 필요하다.

### 오해 8: "FOR UPDATE는 RR에서만 의미 있다"

RC에서도 FOR UPDATE는 X락을 잡는다. 다만 RC에서는 Gap Lock이 거의 사라지므로 잠금 범위가 좁고, Semi-Consistent Read와 SKIP LOCKED 같은 변형 패턴이 자연스럽게 동작한다.

---

## 12. 시니어 면접 답변 프레이밍

### Q1. InnoDB의 REPEATABLE READ는 표준 SQL의 RR과 어떻게 다른가요?

> 표준 SQL의 RR은 Phantom Read를 허용합니다. InnoDB는 Next-Key Lock을 통해 잠금 읽기에서도 팬텀이 발생하지 않게 막습니다. 일관 읽기는 MVCC Read View로 스냅샷 시점을 고정하므로 팬텀이 보이지 않고, 잠금 읽기는 인덱스 범위에 Record Lock과 Gap Lock을 함께 걸어 새 행 삽입을 차단합니다. 결과적으로 InnoDB RR은 표준 RR보다 강한 격리 보장을 합니다. 다만 Write Skew는 여전히 막지 못합니다.

### Q2. RR에서도 Lost Update가 발생할 수 있다고 들었습니다. 어떤 시나리오인가요?

> "현재값을 SELECT로 읽고, 애플리케이션에서 계산해서, 다시 UPDATE로 쓰는" 패턴에서 발생합니다. 두 트랜잭션이 같은 행을 동시에 이렇게 처리하면 각자 SELECT는 같은 값을 보고, 각자의 계산 결과로 UPDATE합니다. 행 락은 순차적으로 잡히지만 한쪽의 결과가 다른 쪽 결과를 덮어쓰면서 변경이 사라집니다. 막는 방법은 세 가지입니다. 첫째, `UPDATE balance = balance - 100`처럼 SQL 표현식으로 원자 갱신. 둘째, `SELECT ... FOR UPDATE`로 명시적 비관 잠금. 셋째, 버전 컬럼을 이용한 낙관적 잠금과 충돌 시 재시도. 도메인의 충돌 빈도와 락 보유 가능 시간에 따라 선택합니다.

### Q3. Write Skew를 예시로 설명해주세요. InnoDB RR에서 어떻게 막을 수 있나요?

> Write Skew는 두 트랜잭션이 서로 다른 행을 갱신하지만, 그 갱신이 합쳐졌을 때 집합 수준의 불변 조건이 깨지는 현상입니다. 예를 들어 "당직 의사 최소 1명"이라는 규칙이 있을 때, 두 의사가 동시에 빠지려 하면 각자 스냅샷에서는 "1명이 빠져도 1명이 남는다"는 검증을 통과합니다. 그러나 둘 다 커밋되면 0명이 됩니다. 행 락은 서로 다른 행에 걸리므로 충돌하지 않습니다. InnoDB RR은 이를 직접 막지 못합니다. 해결책은 두 가지입니다. 첫째, 검증 대상 집합에 `FOR UPDATE`로 잠금 읽기를 걸어 다른 트랜잭션의 동시 진행을 막습니다. 둘째, "이 정책 결정의 잠금 포인트"를 별도 행으로 물질화해 그 행에 X락을 잡는 패턴으로 두 트랜잭션을 직렬화합니다. SERIALIZABLE로 올리는 것은 가능하지만 동시성 비용이 큽니다.

### Q4. RC와 RR의 격리수준 차이가 실제 운영에서 어떤 영향을 주나요?

> 두 가지 큰 차이가 있습니다. 첫째, Read View 재생성 타이밍이 다릅니다. RR은 트랜잭션 첫 일관 읽기에 한 번 만들고 재사용, RC는 일관 읽기마다 새로 만듭니다. 같은 트랜잭션에서 동일 SELECT를 두 번 했을 때 결과가 달라질 수 있는지가 갈립니다. 둘째, 잠금 범위가 다릅니다. RR은 Gap Lock으로 인덱스 범위 전체를 잠그지만 RC는 Record Lock 중심이라 잠금 범위가 좁습니다. 거기에 RC에서만 동작하는 Semi-Consistent Read가 UPDATE의 매칭 동작에서 잠긴 행을 건너뛰게 만들어 큐 워커 같은 패턴의 처리량을 크게 올립니다. 운영적으로는 동시성이 중요한 시스템(컨슈머, 멀티 워커 배치)은 RC가 자연스럽고, 회계성 집계나 시점 일관성이 필요한 보고서는 RR에 `WITH CONSISTENT SNAPSHOT`이 자연스럽습니다.

### Q5. 격리수준 변경 PR 리뷰에서 무엇을 확인하시나요?

> 격리수준은 잠금 패턴까지 바꾸기 때문에 단순 설정 변경이 아닙니다. 첫째, 트랜잭션 안에서 같은 조건 SELECT를 두 번 이상 하면서 그 결과로 비즈니스 분기를 하는지 봅니다. RC로 내리면 두 SELECT의 결과 행 수가 달라질 수 있어서 새 종류의 버그가 생깁니다. 둘째, 집합 수준 불변 조건에 의존하는 코드인지 확인합니다. Write Skew 위험이 있으면 격리수준만으로는 해결되지 않고 명시적 잠금이 필요합니다. 셋째, 큐 컨슈머나 배치 워커처럼 다수 트랜잭션이 같은 행 집합을 동시에 다루는 경우에는 Semi-Consistent Read의 동작이 비즈니스적으로 의도된 것인지 확인합니다. 넷째, 외래키나 트리거, 복제 설정에 영향이 있는지 봅니다. `binlog_format=ROW`라면 영향이 작지만 STATEMENT 환경에서는 추가 검토가 필요합니다. 마지막으로 ORM의 트랜잭션 매니저가 의도대로 격리수준을 설정하는지 실제 로그로 확인합니다.

### Q6. 본인 경험에서 격리수준 관련 의사결정을 한 사례가 있나요?

> 다중 서버 인메모리 캐시 정합성 작업에서 정적 데이터 갱신을 트랜잭션 커밋 이후 이벤트로 발행해야 했습니다. RR 기본값에서 `@TransactionalEventListener(AFTER_COMMIT)`을 쓰면 발행 시점에 커밋이 끝났음이 보장되어 Read View 만료를 신경 쓰지 않아도 됐고, 트랜잭션 안에서 같은 데이터를 여러 번 SELECT하는 어드민 로직과의 정합성도 유지됐습니다. 반대로 메시지 발행 실패 기록은 `Propagation.REQUIRES_NEW`로 분리해 부모 트랜잭션과 독립적으로 짧게 종료시켰습니다. 두 트랜잭션이 다른 생명주기를 갖되 각자의 격리 보장은 유지되도록 설계한 사례입니다.

---

## 13. 핵심 체크리스트

### 격리수준 의미론

- [ ] InnoDB RR이 표준 SQL RR과 다른 두 지점을 설명할 수 있다.
- [ ] Read View 생성 시점이 RR과 RC에서 어떻게 다른지 설명할 수 있다.
- [ ] `WITH CONSISTENT SNAPSHOT`이 기본 `START TRANSACTION`과 어떻게 다른지 설명할 수 있다.
- [ ] 같은 트랜잭션 안에서 SELECT와 UPDATE의 결과가 어긋날 수 있는 이유를 일관 읽기/현재 읽기 관점에서 설명할 수 있다.

### 이상 현상

- [ ] Dirty / Non-Repeatable / Phantom 이외의 Lost Update와 Write Skew를 정의할 수 있다.
- [ ] InnoDB RR에서 Lost Update가 발생하는 패턴과 막는 세 가지 방법을 설명할 수 있다.
- [ ] Write Skew의 의사 당직 예제 같은 사례를 들어 설명하고 InnoDB RR에서의 해결책을 제시할 수 있다.
- [ ] Snapshot Phantom과 Current Phantom의 차이를 구분해 설명할 수 있다.

### Semi-Consistent Read

- [ ] Semi-Consistent Read의 정의와 활성화 조건(RC)을 설명할 수 있다.
- [ ] 큐 워커 패턴에서 RC + Semi-Consistent Read가 RR보다 처리량이 높은 이유를 설명할 수 있다.
- [ ] `FOR UPDATE SKIP LOCKED`와 Semi-Consistent Read의 의미 차이를 설명할 수 있다.

### 운영 의사결정

- [ ] 결제 멱등성 / 큐 컨슈머 / 회계 마감 / 선착순 쿠폰 도메인 각각에 적합한 격리수준과 잠금 패턴을 매핑할 수 있다.
- [ ] 격리수준을 낮출 때 점검할 코드 패턴 세 가지(반복 SELECT, 집합 불변 조건, UPDATE 매칭 동작)를 식별할 수 있다.
- [ ] `@Transactional(isolation = ...)` 변경 PR을 잠금 측면까지 검토할 수 있다.

### 실습 재현

- [ ] Lost Update를 RR에서 재현하고 표현식 갱신 / FOR UPDATE / 낙관적 잠금 세 방식으로 해결할 수 있다.
- [ ] Write Skew를 의사 당직 예제로 재현하고 명시적 잠금으로 해결할 수 있다.
- [ ] RR과 RC에서 동일한 UPDATE 쿼리가 다르게 잠금을 잡는 모습을 `performance_schema.data_locks`로 비교할 수 있다.
- [ ] `WITH CONSISTENT SNAPSHOT`을 사용해 다른 세션의 INSERT를 보이지 않게 만드는 시나리오를 재현할 수 있다.

---

## 관련 문서

- [InnoDB MVCC 완전 분석](./innodb-mvcc.md) — Read View 구조, 버전 체인, Undo / Redo, Crash Recovery
- [InnoDB Gap Lock & Next-Key Lock 심층 분석](./innodb-gap-next-key-lock.md) — 구간 락 의미론, Insert Intention, supremum
- [InnoDB 트랜잭션과 잠금](./transaction-lock.md) — 격리수준과 잠금 종류 개관
- [Deadlock Analysis](./deadlock-analysis.md) — 데드락 로그 해석과 재시도 전략
- [Redo Log](./redo-log.md) — WAL과 Undo Log 관계
- [Spring 트랜잭션 전파·격리수준·AFTER_COMMIT](../../java/spring/transaction-propagation-isolation-after-commit.md) — 애플리케이션 경계에서의 격리수준

---

*작성 기준: MySQL 8.0, InnoDB 스토리지 엔진, 기본 격리수준 REPEATABLE READ.*
