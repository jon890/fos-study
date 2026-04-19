# InnoDB 트랜잭션과 잠금

Real MySQL 8.0 5장 내용을 정리한 문서. 개발자 입장에서 중요한 MVCC와 Lock 동작 방식에 집중했다.

---

## 격리 수준 (간략)

MySQL InnoDB 기본값은 **REPEATABLE READ**다. 나머지 수준은 설정을 바꾸지 않는 이상 실무에서 마주칠 일이 거의 없으니 표로만 정리한다.

| 격리 수준 | Dirty Read | Non-Repeatable Read | Phantom Read |
|---|---|---|---|
| READ UNCOMMITTED | 발생 | 발생 | 발생 |
| READ COMMITTED | 없음 | 발생 | 발생 |
| **REPEATABLE READ (기본값)** | 없음 | 없음 | InnoDB에서 없음* |
| SERIALIZABLE | 없음 | 없음 | 없음 |

\* 표준 SQL 스펙상 REPEATABLE READ는 Phantom Read를 허용하지만, InnoDB는 **Next-Key Lock**으로 Gap을 잠가서 Phantom Read를 막는다.

---

## MVCC (Multi-Version Concurrency Control)

### 핵심 아이디어

InnoDB가 높은 동시성을 달성하는 핵심 메커니즘이다.

> **읽기는 잠금 없이, 쓰기는 잠금으로** — 덕분에 읽기와 쓰기가 서로를 막지 않는다.

일반 SELECT는 잠금을 전혀 걸지 않는다. 대신 데이터의 "과거 버전 스냅샷"을 읽는다. 이 스냅샷을 어떻게 만드는가가 MVCC의 핵심이다.

---

### Undo Log — 과거 버전의 저장소

UPDATE나 DELETE가 발생하면 InnoDB는 변경 전 데이터를 **Undo Log**에 기록한다.

```
현재 레코드 (id=1, name="B")
    ↓ roll_pointer
Undo Log v1 (id=1, name="A")  ← UPDATE 전 버전
    ↓ roll_pointer
Undo Log v0 (id=1, name="초기값")  ← 그 전 버전
```

각 레코드는 `roll_pointer`로 이전 버전 체인을 유지한다. 트랜잭션이 롤백하거나 예전 스냅샷을 읽어야 할 때 이 체인을 따라간다.

---

### Read View — "어느 버전까지 볼 수 있는가"

SELECT를 실행할 때 InnoDB는 **Read View**를 생성한다. Read View는 "이 SELECT가 볼 수 있는 최신 커밋 시점"을 기록한 스냅샷이다.

Read View 생성 시점이 격리 수준에 따라 다르다.

| 격리 수준 | Read View 생성 시점 |
|---|---|
| **REPEATABLE READ** | 트랜잭션 시작 후 **첫 번째 SELECT**에서 1회 생성, 이후 재사용 |
| READ COMMITTED | **SELECT마다** 새로 생성 |

#### REPEATABLE READ 동작 예시

```
T1: BEGIN
T1: SELECT * FROM orders WHERE id=1  ← Read View 생성 (시점 A)
                                         결과: status="pending"

T2: UPDATE orders SET status="done" WHERE id=1
T2: COMMIT

T1: SELECT * FROM orders WHERE id=1  ← 동일한 Read View 재사용
                                         결과: status="pending"  (T2 커밋 안 보임)
T1: COMMIT
```

T1이 같은 조건으로 두 번 조회해도 결과가 바뀌지 않는다. T2가 커밋했어도 T1의 Read View 기준으론 아직 "보이지 않는" 버전이라 Undo Log를 읽는다.

#### READ COMMITTED 동작 예시

```
T1: BEGIN
T1: SELECT * FROM orders WHERE id=1  ← Read View 생성 (시점 A)
                                         결과: status="pending"

T2: UPDATE orders SET status="done" WHERE id=1
T2: COMMIT

T1: SELECT * FROM orders WHERE id=1  ← 새 Read View 생성 (시점 B)
                                         결과: status="done"  (T2 커밋 보임)
T1: COMMIT
```

Non-Repeatable Read가 발생한다. 같은 쿼리인데 결과가 달라진다.

---

### Consistent Non-Locking Read vs Locking Read

MVCC의 일반 SELECT는 **Consistent Non-Locking Read**다. 잠금 없이 스냅샷 버전을 읽는다.

반면 `SELECT FOR UPDATE`, `SELECT FOR SHARE`는 **Locking Read**다.

```sql
-- Non-Locking Read: MVCC 스냅샷, 잠금 없음
SELECT * FROM orders WHERE id = 1;

-- Locking Read: 최신 커밋 데이터 읽기 + 잠금 획득
SELECT * FROM orders WHERE id = 1 FOR UPDATE;   -- X-Lock
SELECT * FROM orders WHERE id = 1 FOR SHARE;    -- S-Lock
```

Locking Read는 **항상 최신 커밋 버전**을 읽는다. Read View를 무시하고 현재 레코드를 직접 읽으면서 잠금을 건다.

실무에서 자주 실수하는 케이스:

```
T1 (REPEATABLE READ): BEGIN
T1: SELECT stock FROM inventory WHERE id=1        -- 결과: 10 (스냅샷)
T2: UPDATE inventory SET stock=0 WHERE id=1
T2: COMMIT
T1: UPDATE inventory SET stock=stock-1 WHERE id=1 -- 내부적으로 최신값 읽고 UPDATE
                                                    -- stock이 -1이 됨
```

일반 SELECT는 스냅샷으로 10을 봤지만, UPDATE의 WHERE 조건은 최신 레코드(0)에 적용된다. "재고 확인 후 차감" 로직에서 이 차이를 모르면 데이터 정합성이 깨진다. `SELECT FOR UPDATE`로 읽어야 한다.

---

### 긴 트랜잭션과 Undo Log 비대화

Read View가 살아있는 동안 그 시점 이후의 Undo Log를 **Purge Thread**가 삭제할 수 없다.

```
T1: BEGIN (Read View 시점 = 100)
...오래 걸리는 작업...
T1: COMMIT (한참 뒤)

-- 이 사이에 쌓인 Undo Log: 시점 101 ~ N 전부 삭제 불가
```

배치 처리나 긴 보고서 쿼리를 트랜잭션 안에 묶어두면 Undo Log가 계속 쌓인다. Undo Tablespace가 커지고 Purge 지연이 쌓이면서 전체 쓰기 성능에 영향을 준다.

---

## InnoDB 잠금 종류

### Shared Lock (S) / Exclusive Lock (X)

- **S-Lock**: 읽기 잠금. 여러 트랜잭션이 동시에 획득 가능
- **X-Lock**: 쓰기 잠금. 하나만 획득 가능. S-Lock과도 충돌

| | S-Lock 요청 | X-Lock 요청 |
|---|---|---|
| S-Lock 보유 중 | 호환 | 대기 |
| X-Lock 보유 중 | 대기 | 대기 |

---

### Row-Level Lock 3종류

InnoDB의 행 잠금은 테이블의 실제 행이 아닌 **인덱스 레코드**를 기준으로 작동한다.

#### 1. Record Lock
인덱스 레코드 자체를 잠근다.

```
인덱스: [1] [2] [3] [5] [7]

id=3 Record Lock: [3]만 잠금
```

#### 2. Gap Lock
인덱스 레코드 사이의 빈 공간(Gap)을 잠근다. 그 범위에 새 레코드가 삽입되는 것을 막는다.

```
인덱스: [1] [2] [3] [5] [7]

id=3 Gap Lock: (2, 3) 범위의 삽입 차단
```

Phantom Read 방지가 목적이다. REPEATABLE READ에서 범위 조건 쿼리에 자동으로 걸린다.

#### 3. Next-Key Lock
Record Lock + Gap Lock의 조합. InnoDB의 기본 잠금 방식이다.

```
인덱스: [1] [2] [3] [5] [7]

id=3 Next-Key Lock: [3]을 잠금 + (2, 3) Gap 잠금
```

---

### 인덱스 없으면 테이블 전체가 잠긴다

InnoDB 행 잠금이 인덱스 기준이기 때문에, 인덱스를 사용하지 못하는 WHERE 조건이면 모든 레코드에 잠금이 걸린다. 테이블 수준 잠금과 다를 바 없어진다.

```sql
-- name 컬럼에 인덱스 없는 경우
SELECT * FROM users WHERE name = 'kim' FOR UPDATE;
-- → 테이블 전체 레코드에 X-Lock 발생
```

Lock 관련 성능 문제가 생기면 실행 계획(EXPLAIN)에서 인덱스를 타는지 먼저 확인한다.

---

## 관련 문서

- [InnoDB MVCC 완전 분석](./innodb-mvcc.md) — Read View, 버전 체인, 격리 수준
- [Gap Lock & Next-Key Lock 심층 분석](./innodb-gap-next-key-lock.md) — 구간 락 의미론, RR에서의 함정
- [Deadlock Analysis](./deadlock-analysis.md) — 데드락 로그 해석, 재시도 전략
- [Spring Data JPA 트랜잭션 실수 모음](../../java/spring/jpa-transaction.md)
