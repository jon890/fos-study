# [초안] InnoDB MVCC 완전 분석 — Undo Log, Read View, 잠금, 그리고 Crash Recovery까지

---

## 1. 왜 MVCC를 깊이 알아야 하는가

InnoDB의 동시성 제어는 단순한 "락을 잡느냐 안 잡느냐"의 문제가 아니다. MySQL이 높은 읽기 처리량을 유지하면서도 트랜잭션 격리를 보장하는 핵심 메커니즘이 MVCC(Multi-Version Concurrency Control)다. 실무에서 발생하는 N+1 문제, 데드락, 팬텀 읽기, 갑작스러운 Undo Log 비대화, 슬로우 쿼리가 모두 MVCC의 동작 방식을 모르면 제대로 진단할 수 없다.

e-커머스 플랫폼에서는 재고 차감, 주문 상태 변경, 포인트 적립이 동시에 수천 건씩 발생한다. 이 환경에서 **읽기가 쓰기를 막지 않아야** 하고, 동시에 **일관된 데이터 뷰를 제공해야** 한다. MVCC는 그 두 요구를 동시에 충족하는 설계다.

면접에서 "InnoDB의 동시성 전략이 무엇인가요?"라는 질문에 "락 기반입니다"라고 답하면 절반밖에 맞지 않는다. 정답은 "읽기는 MVCC(스냅샷 기반 일관 읽기)로, 쓰기는 락으로 처리합니다"다.

---

## 2. 숨겨진 컬럼과 버전 체인

### 2-1. 레코드에 숨겨진 세 컬럼

InnoDB는 사용자가 정의한 컬럼 외에 모든 레코드 행에 숨겨진 컬럼을 추가한다.

| 숨겨진 컬럼 | 크기 | 역할 |
|---|---|---|
| `DB_TRX_ID` | 6 bytes | 이 버전을 만든(또는 마지막으로 갱신한) 트랜잭션 ID |
| `DB_ROLL_PTR` | 7 bytes | 이전 버전의 Undo Log 레코드를 가리키는 롤 포인터 |
| `DB_ROW_ID` | 6 bytes | PK가 없을 때만 생성되는 내부 행 ID |

`DB_TRX_ID`와 `DB_ROLL_PTR`가 MVCC의 핵심이다. 이 두 컬럼이 버전 체인을 구성한다.

### 2-2. 버전 체인(Version Chain)

InnoDB는 레코드를 갱신할 때 기존 레코드를 지우지 않는다. 대신 Undo Log에 이전 버전을 기록하고, 레코드 헤더의 `DB_ROLL_PTR`가 그 이전 버전을 가리키게 한다.

```
[현재 레코드]          [Undo v1]              [Undo v2]
DB_TRX_ID = 100  <--  DB_TRX_ID = 80   <--  DB_TRX_ID = 50
DB_ROLL_PTR ------→   DB_ROLL_PTR ------→    DB_ROLL_PTR = NULL
price = 20000          price = 15000          price = 10000
```

읽기 트랜잭션은 자신의 Read View가 허용하는 버전을 이 체인을 거슬러 올라가며 찾는다. 체인의 끝까지 갔는데도 가시성이 확인되지 않으면 그 레코드는 "보이지 않음"으로 처리된다.

---

## 3. Undo Log — 버전 체인의 저장소

### 3-1. Insert Undo Log

`INSERT` 시 생성된다. 트랜잭션이 커밋되면 즉시 삭제해도 된다.

- 롤백 시 레코드를 통째로 삭제하면 그만이다.
- 다른 트랜잭션이 이 버전을 읽을 이유가 없다. 삽입 전에는 존재하지 않던 레코드이므로, 이 트랜잭션이 시작하기 전의 스냅샷에서는 애초에 이 행이 없다.

### 3-2. Update Undo Log

`UPDATE` 또는 `DELETE` 시 생성된다. 커밋 후에도 즉시 삭제할 수 없다.

- 이 버전을 참조하는 Read View가 하나라도 살아있으면 삭제 불가다.
- Purge Thread가 더 이상 참조하는 Read View가 없음을 확인한 후에야 정리한다.
- **이것이 Undo Log 비대화(Undo Log Bloat)의 근본 원인이다.**

```sql
-- Undo Log를 폭발시키는 패턴
-- [세션 A]
START TRANSACTION;
SELECT COUNT(*) FROM orders;  -- 이 시점에 Read View가 고정된다

-- 이 상태로 아무것도 하지 않고 수 분 대기하는 사이
-- [다른 세션들]에서 orders 테이블에 수천 건의 UPDATE가 발생

-- 세션 A의 Read View가 살아있는 한,
-- 그 UPDATE들의 이전 버전 Undo Log는 하나도 삭제되지 않는다

-- [세션 A]
COMMIT;  -- 여기서야 Read View가 해제되고 Purge가 진행된다
```

### 3-3. Purge Thread와 History List Length

Purge Thread는 백그라운드에서 더 이상 필요 없는 Update Undo Log를 정리한다. `SHOW ENGINE INNODB STATUS`의 `History list length` 값이 이 잔여 Undo Log의 양을 나타낸다. 이 값이 수만 이상으로 지속적으로 증가하면 오래된 Read View가 Purge를 막고 있다는 신호다.

```sql
SHOW ENGINE INNODB STATUS\G
-- 출력 중 아래 부분 확인:
-- TRANSACTIONS
-- ...
-- History list length 42
-- 숫자가 크고 계속 증가하면 장기 트랜잭션을 찾아야 한다

-- 오래 실행 중인 트랜잭션 확인 (MySQL 8)
SELECT trx_id, trx_started, trx_isolation_level, trx_query
FROM information_schema.INNODB_TRX
ORDER BY trx_started ASC;
```

---

## 4. Read View — 스냅샷의 실체

### 4-1. Read View 구조

MVCC에서 "스냅샷"의 실체는 메모리에 존재하는 Read View 구조체다. 다음 네 가지 필드로 구성된다.

| 필드 | 의미 |
|---|---|
| `m_low_limit_id` | Read View 생성 시점에 아직 시작되지 않은 가장 낮은 트랜잭션 ID. 이 값 이상의 트랜잭션이 만든 변경은 절대 보이지 않는다. |
| `m_up_limit_id` | 활성 트랜잭션 목록 중 가장 낮은 ID. 이 값보다 작으면 이미 커밋된 것이므로 무조건 보인다. |
| `m_ids` | Read View 생성 시점의 활성(미커밋) 트랜잭션 ID 목록. 이 목록에 있으면 아직 커밋 전이므로 보이지 않는다. |
| `m_creator_trx_id` | 이 Read View를 만든 트랜잭션 자신의 ID. |

### 4-2. 가시성 판단 알고리즘

레코드의 `DB_TRX_ID`를 Read View와 비교하는 의사코드다.

```
function is_visible(record_trx_id, read_view):

  # 내가 직접 변경한 버전
  if record_trx_id == read_view.m_creator_trx_id:
    return TRUE

  # Read View 생성 전에 이미 커밋 완료된 트랜잭션
  if record_trx_id < read_view.m_up_limit_id:
    return TRUE

  # Read View 생성 이후에 시작된 트랜잭션
  if record_trx_id >= read_view.m_low_limit_id:
    return FALSE

  # Read View 생성 당시 아직 커밋하지 않은 트랜잭션
  if record_trx_id in read_view.m_ids:
    return FALSE

  # 위 조건에 해당하지 않으면 커밋 완료된 것
  return TRUE
```

`is_visible`이 `FALSE`를 반환하면 `DB_ROLL_PTR`를 따라 이전 버전으로 이동하고 다시 판단한다. 체인 끝까지 `FALSE`면 이 레코드는 현재 트랜잭션에게 보이지 않는다.

---

## 5. 일관 읽기 vs 현재 읽기

이 구분은 면접에서 반드시 나온다. 잘못 알고 있는 엔지니어가 많다.

### 5-1. 일관 읽기(Consistent Read = Snapshot Read)

```sql
SELECT * FROM orders WHERE user_id = 1;
```

- MVCC Read View를 사용하여 스냅샷 시점의 데이터를 반환한다.
- **락을 걸지 않는다.** 다른 트랜잭션이 같은 레코드를 수정 중이어도 블로킹되지 않는다.
- `REPEATABLE READ`에서는 트랜잭션 내 첫 번째 SELECT 시점에 Read View가 고정되고 커밋 전까지 재사용된다.
- `READ COMMITTED`에서는 SELECT마다 새 Read View를 생성한다.

### 5-2. 현재 읽기(Current Read = Locking Read)

```sql
SELECT * FROM orders WHERE user_id = 1 FOR UPDATE;    -- Exclusive Lock
SELECT * FROM orders WHERE user_id = 1 FOR SHARE;     -- Shared Lock
UPDATE orders SET status = 'PAID' WHERE id = 100;     -- 내부적으로 Current Read
DELETE FROM orders WHERE id = 100;                    -- 내부적으로 Current Read
```

- Undo Log 체인을 거치지 않고 **가장 최근에 커밋된 실제 데이터를 읽는다.**
- 읽으면서 동시에 해당 레코드에 락을 건다. 다른 트랜잭션이 같은 레코드를 변경하려 하면 대기한다.
- `UPDATE`와 `DELETE`는 WHERE 조건으로 레코드를 찾을 때 내부적으로 Current Read를 사용한다. 이 점이 중요하다.

### 5-3. 재고 차감에서 발생하는 실수

```sql
-- 잘못된 패턴: Snapshot Read로 재고 확인
START TRANSACTION;
SELECT stock FROM products WHERE id = 1;
-- stock = 10 반환. 그러나 이 사이에 다른 세션이 stock을 0으로 바꾸고 커밋했을 수 있다.
-- 이 SELECT는 스냅샷을 읽으므로 여전히 10을 반환한다.
UPDATE products SET stock = stock - 1 WHERE id = 1;
-- 음수 재고 발생 가능
COMMIT;

-- 올바른 패턴: Current Read로 최신값 확인 및 잠금
START TRANSACTION;
SELECT stock FROM products WHERE id = 1 FOR UPDATE;
-- 실제 최신 커밋값을 읽고, 동시에 이 레코드를 잠근다.
-- 다른 세션의 동시 차감을 막는다.
-- 애플리케이션에서 stock > 0 검증

UPDATE products SET stock = stock - 1 WHERE id = 1 AND stock > 0;
-- ROW_COUNT()로 실제 차감 여부 확인
SELECT ROW_COUNT();  -- 0이면 재고 부족
COMMIT;
```

---

## 6. 트랜잭션 격리 수준과 MVCC

### 6-1. READ UNCOMMITTED

MVCC를 사용하지 않는다. 커밋되지 않은 변경사항을 그대로 읽는다(Dirty Read 허용). 실무에서 거의 사용하지 않는다.

### 6-2. READ COMMITTED

```sql
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- [세션 A]
START TRANSACTION;
SELECT price FROM products WHERE id = 1;
-- Read View #1 생성 → price = 15000

-- [세션 B] (별도 터미널)
UPDATE products SET price = 20000 WHERE id = 1;
COMMIT;

-- [세션 A] 계속
SELECT price FROM products WHERE id = 1;
-- Read View #2 새로 생성 → price = 20000  (Non-Repeatable Read 발생)
COMMIT;
```

SELECT마다 새 Read View를 생성하기 때문에 같은 트랜잭션 안에서도 결과가 달라진다. Non-Repeatable Read가 허용된다.

### 6-3. REPEATABLE READ (InnoDB 기본값)

```sql
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- [세션 A]
START TRANSACTION;
SELECT price FROM products WHERE id = 1;
-- Read View 고정 → price = 15000

-- [세션 B]
UPDATE products SET price = 20000 WHERE id = 1;
COMMIT;

-- [세션 A] 계속
SELECT price FROM products WHERE id = 1;
-- 동일한 Read View 재사용 → 여전히 price = 15000 (Repeatable Read 보장)

SELECT price FROM products WHERE id = 1 FOR UPDATE;
-- Current Read → price = 20000 (최신 커밋값)
COMMIT;
```

트랜잭션 내 첫 번째 SELECT에서 Read View가 고정되고, 그 이후 SELECT는 같은 Read View를 재사용한다.

### 6-4. SERIALIZABLE

모든 SELECT가 암묵적으로 `FOR SHARE`처럼 동작한다. 완전한 직렬성을 보장하지만 동시성이 크게 떨어진다. 금융 배치 처리처럼 정합성이 최우선인 특수 케이스에만 사용한다.

---

## 7. 팬텀 읽기와 Next-Key Lock

### 7-1. 팬텀 읽기란

같은 조건의 SELECT를 두 번 실행했을 때, 사이에 다른 트랜잭션이 새 행을 삽입하여 첫 번째와 두 번째 결과의 **행 수**가 달라지는 현상이다.

```sql
-- 세션 A (REPEATABLE READ)
START TRANSACTION;
SELECT COUNT(*) FROM orders WHERE amount > 50000;  -- 결과: 5건

-- 세션 B
INSERT INTO orders (product_id, user_id, amount, status)
VALUES (1, 999, 60000, 'PENDING');
COMMIT;

-- 세션 A
SELECT COUNT(*) FROM orders WHERE amount > 50000;           -- 5건 (스냅샷 읽기)
SELECT COUNT(*) FROM orders WHERE amount > 50000 FOR UPDATE; -- 6건 (현재 읽기)
COMMIT;
```

일관 읽기에서는 MVCC가 Read View를 고정하므로 팬텀이 발생하지 않는다. 문제는 현재 읽기(FOR UPDATE, UPDATE 내부)에서 팬텀이 발생할 수 있다는 점이다. InnoDB는 이를 Next-Key Lock으로 방지한다.

### 7-2. Next-Key Lock = Record Lock + Gap Lock

**Record Lock**: 인덱스 레코드 자체에 거는 락

**Gap Lock**: 인덱스 레코드 사이의 간격에 거는 락. 해당 범위에 새 행 삽입을 막는다.

**Next-Key Lock**: 특정 레코드와 그 레코드 바로 앞의 Gap까지 함께 잠그는 락. `(이전 값, 현재 값]` 형태의 반열린 구간이다.

```sql
-- 예시 데이터: amount 인덱스에 10000, 30000, 50000, 80000 존재

-- 세션 A
START TRANSACTION;
SELECT * FROM orders WHERE amount > 40000 FOR UPDATE;

-- 잠기는 범위 (Next-Key Lock):
-- (-∞, 10000]: 없음 (40000 이하이므로 조건 미해당)
-- (30000, 50000]: Record Lock on 50000 + Gap Lock (30000, 50000)
-- (50000, 80000]: Record Lock on 80000 + Gap Lock (50000, 80000)
-- (80000, +∞):   Gap Lock (supremum pseudo-record까지)
```

이 상태에서 세션 B가 `amount = 60000`인 행을 삽입하려 하면 `(50000, 80000)` Gap Lock에 걸려 세션 A가 커밋하기 전까지 대기한다.

### 7-3. 유니크 인덱스에서 Gap Lock 생략

PK 또는 유니크 인덱스로 정확히 하나의 레코드를 지정하면 Gap Lock 없이 Record Lock만 걸린다.

```sql
-- PK 조회이고 id=100이 존재하면: Record Lock만 (Gap Lock 없음)
SELECT * FROM orders WHERE id = 100 FOR UPDATE;

-- id=100이 존재하지 않으면: Gap Lock (해당 위치에 삽입 방지)
SELECT * FROM orders WHERE id = 100 FOR UPDATE;
```

존재하지 않는 키에 대해 Gap Lock이 걸리는 것은 팬텀 방지를 위한 중요한 동작이다. 이를 모르면 "왜 없는 레코드를 조회했는데 INSERT가 블로킹되지?"라는 상황을 이해하지 못한다.

### 7-4. Gap Lock이 만드는 데드락

Gap Lock은 삽입 방향에 대해서만 동작하고, 두 트랜잭션이 각각 Gap Lock을 잡고 있는 상태에서 서로의 Gap 범위에 삽입을 시도하면 데드락이 발생한다.

```sql
-- orders 테이블에 id = 10, 20이 있다고 가정

-- 세션 A
START TRANSACTION;
SELECT * FROM orders WHERE id = 15 FOR UPDATE;  -- Gap Lock (10, 20)

-- 세션 B
START TRANSACTION;
SELECT * FROM orders WHERE id = 15 FOR UPDATE;  -- Gap Lock (10, 20) 동시 획득 가능
                                                -- (Gap Lock끼리는 호환됨)
INSERT INTO orders (id, ...) VALUES (15, ...);  -- 세션 A의 Gap Lock에 의해 대기

-- 세션 A
INSERT INTO orders (id, ...) VALUES (15, ...);  -- 세션 B의 Gap Lock에 의해 대기
-- → 데드락 발생
```

---

## 8. MVCC + Redo Log + Crash Recovery

### 8-1. Undo Log와 Redo Log의 역할 분담

두 로그를 혼동하는 경우가 많다. 목적이 완전히 다르다.

| 구분 | Undo Log | Redo Log |
|---|---|---|
| **목적** | 롤백, 이전 버전 제공(MVCC) | 커밋된 변경사항 크래시 복구 |
| **저장 위치** | Undo Tablespace (`undo_001`, `undo_002`) | `#ib_redo*` (MySQL 8.0.30+) 또는 `ib_logfile*` |
| **생성 시점** | 데이터 변경 **직전** | 데이터 변경 **직후** (버퍼 풀 수정 시) |
| **삭제 시점** | 참조 Read View가 사라진 후 Purge | Checkpoint 완료 후 |
| **Write 방식** | 변경 이전 값 기록 | 변경 이후 값 기록 (WAL) |

### 8-2. 트랜잭션 커밋까지의 전체 흐름

```
1. 트랜잭션 시작: 새 DB_TRX_ID 할당

2. 변경 직전: Undo Log에 이전 버전 기록
   └─ Undo Log 자체도 Redo Log에 기록된다
      (크래시 복구 시 Undo Log 복원이 필요하기 때문)

3. 버퍼 풀의 페이지 수정 (메모리)
   └─ DB_TRX_ID, DB_ROLL_PTR 업데이트

4. Redo Log Buffer에 변경사항 기록 (메모리)

5. 커밋 요청:
   └─ Redo Log Buffer를 디스크에 fsync (innodb_flush_log_at_trx_commit=1)
   └─ 이 fsync가 완료되면 커밋 완료 응답

6. 변경된 버퍼 풀 페이지는 나중에 Checkpoint 때 디스크에 반영
```

### 8-3. Crash Recovery 순서

MySQL이 비정상 종료 후 재시작하면 다음 순서로 복구한다.

```
재시작
  │
  ▼
Redo Log 스캔 (Roll-Forward)
  └─ 커밋 마커가 있는 트랜잭션 → Redo 적용 (디스크에 누락된 변경사항 복원)
  └─ 커밋 마커가 없는 트랜잭션 → 미완료 트랜잭션으로 표시
  │
  ▼
Undo Log로 미완료 트랜잭션 롤백 (Roll-Back)
  └─ 커밋 전 크래시된 트랜잭션의 변경사항을 이전 버전으로 복원
  │
  ▼
서비스 재개
```

Undo Log가 Redo Log에 의해 먼저 복원되는 이유가 여기에 있다. 크래시 직전에 Undo Log를 기록하던 중이었다면 Redo Log로 Undo Log를 먼저 살려야 롤백이 가능하다.

### 8-4. `innodb_flush_log_at_trx_commit` 옵션

이 값은 Durability와 성능의 트레이드오프를 결정한다.

| 값 | 동작 | Durability |
|---|---|---|
| `1` (기본, 권장) | 커밋마다 fsync | 완전 보장 (ACID) |
| `2` | 커밋마다 OS 버퍼에 write, 1초마다 fsync | OS 크래시 시 최대 1초 손실 |
| `0` | 1초마다 write + fsync | MySQL 크래시 시 최대 1초 손실 |

프로덕션 환경에서는 `1`을 사용해야 한다.

---

## 9. 흔한 오해 5가지

### 오해 1: "REPEATABLE READ에서는 팬텀 읽기가 무조건 발생하지 않는다"

절반만 맞다. 일관 읽기(SELECT)에서는 MVCC가 팬텀을 방지한다. 그러나 현재 읽기(FOR UPDATE, UPDATE)에서는 Gap Lock이 없으면 팬텀이 발생할 수 있다. Gap Lock은 인덱스 범위 스캔에서만 정확히 동작하며, 풀 테이블 스캔에서는 테이블 전체에 락이 걸리는 방식으로 처리된다.

### 오해 2: "FOR UPDATE를 걸면 데드락이 방지된다"

오히려 반대다. `FOR UPDATE`를 남용할수록 데드락 확률이 높아진다. 두 세션이 서로 다른 순서로 `FOR UPDATE`를 획득하려 하면 데드락이 발생한다. 데드락 방지를 위해서는 항상 동일한 순서로 락을 획득해야 한다.

### 오해 3: "MVCC는 읽기만을 위한 것이다"

MVCC는 읽기의 스냅샷뿐 아니라 롤백의 기반이기도 하다. `ROLLBACK` 시 Undo Log의 이전 버전으로 데이터를 복원한다. 또한 크래시 복구의 Roll-Back 단계에서도 Undo Log를 사용한다.

### 오해 4: "트랜잭션을 짧게 유지하면 락만 빨리 풀린다"

락뿐 아니라 Read View도 해제된다. 긴 트랜잭션 = 오래 살아있는 Read View = Purge 불가 = Undo Log 비대화 = 디스크 증가 + 버전 체인 길어짐 + 읽기 성능 저하. 트랜잭션을 짧게 유지해야 하는 이유는 락 해제와 Undo 정리, 두 가지 모두에 있다.

### 오해 5: "Undo Log와 Redo Log는 같은 것이다"

완전히 다른 목적이다. Undo는 "변경 이전으로 되돌리기(롤백, 이전 버전 제공)", Redo는 "변경 이후를 다시 적용하기(크래시 복구)". 트랜잭션 처리 시 둘 다 기록된다. 그리고 Undo Log 자체가 Redo Log로 보호받는다.

---

## 10. 실습 환경 구성

### 10-1. Docker로 MySQL 8 시작

```bash
docker run --name mvcc-lab \
  -e MYSQL_ROOT_PASSWORD=password \
  -e MYSQL_DATABASE=mvcctest \
  -p 3306:3306 \
  -d mysql:8.0

# 접속
mysql -h 127.0.0.1 -P 3306 -u root -ppassword mvcctest
```

### 10-2. 실습용 스키마

```sql
CREATE TABLE products (
    id   INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    price INT NOT NULL,
    INDEX idx_price (price)
) ENGINE=InnoDB;

INSERT INTO products (name, stock, price) VALUES
('비타민C', 100, 15000),
('콜라겐',   50, 35000),
('홍삼정',   30, 80000);

CREATE TABLE orders (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    user_id    INT NOT NULL,
    amount     INT NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at DATETIME DEFAULT NOW(),
    INDEX idx_amount (amount)
) ENGINE=InnoDB;

INSERT INTO orders (product_id, user_id, amount, status) VALUES
(1, 1, 15000, 'PAID'),
(2, 2, 35000, 'PAID'),
(1, 3, 45000, 'PAID'),
(3, 4, 80000, 'PAID'),
(2, 5, 70000, 'PENDING');
```

---

## 11. 실행 가능한 시나리오

### 시나리오 1: REPEATABLE READ 스냅샷 고정 확인

터미널 두 개를 열어 각각 세션 A, B로 사용한다.

```sql
-- [세션 A]
START TRANSACTION;
SELECT price FROM products WHERE id = 1;
-- 결과: 15000

-- [세션 B] (별도 터미널)
UPDATE products SET price = 20000 WHERE id = 1;
COMMIT;

-- [세션 A]
SELECT price FROM products WHERE id = 1;
-- 결과: 15000 (Read View 고정, 세션 B의 변경 안 보임)

SELECT price FROM products WHERE id = 1 FOR UPDATE;
-- 결과: 20000 (Current Read, 최신 커밋값)

COMMIT;
```

### 시나리오 2: Gap Lock으로 팬텀 삽입 차단

```sql
-- [세션 A]
START TRANSACTION;
SELECT * FROM orders WHERE amount > 50000 FOR UPDATE;
-- amount = 70000, 80000인 행에 Record Lock + Gap Lock 획득

-- [세션 B] (별도 터미널)
START TRANSACTION;
INSERT INTO orders (product_id, user_id, amount, status)
VALUES (1, 99, 60000, 'PENDING');
-- → 세션 A의 Gap Lock (50000, 70000)에 의해 여기서 대기

-- [세션 A]
COMMIT;
-- → 세션 B의 INSERT 즉시 완료

-- [세션 B]
COMMIT;
```

### 시나리오 3: Undo Log 비대화 재현과 진단

```sql
-- [세션 A] 오래 사는 트랜잭션
START TRANSACTION;
SELECT * FROM products LIMIT 1;
-- Read View 고정. 이 상태로 유지

-- [터미널 3] (반복 실행하여 Undo 누적)
UPDATE products SET price = price + 1 WHERE id = 1;
-- 커밋: UPDATE products SET price = price + 1 WHERE id = 1;
-- (별도로 커밋)

-- [터미널 4] 진단
SHOW ENGINE INNODB STATUS\G
-- "History list length" 확인

SELECT trx_id, trx_started, trx_query
FROM information_schema.INNODB_TRX
ORDER BY trx_started;
-- 세션 A의 트랜잭션이 오래된 시작 시각으로 나타난다

-- [세션 A] 해제
COMMIT;
-- 이후 History list length가 줄어드는 것을 INNODB STATUS로 재확인
```

### 시나리오 4: 락 경합과 대기 확인

```sql
-- [세션 A]
START TRANSACTION;
SELECT * FROM products WHERE id = 1 FOR UPDATE;

-- [세션 B]
START TRANSACTION;
SELECT * FROM products WHERE id = 1 FOR UPDATE;
-- 세션 A 커밋 전까지 여기서 대기

-- 대기 중인 락 확인
SELECT
    r.trx_id waiting_trx_id,
    r.trx_query waiting_query,
    b.trx_id blocking_trx_id,
    b.trx_query blocking_query
FROM information_schema.INNODB_LOCK_WAITS w
JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id
JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id;

-- [세션 A]
COMMIT;
-- [세션 B] 즉시 진행
```

---

## 12. 시니어 면접 답변 프레이밍

### Q1. InnoDB에서 읽기가 쓰기를 막지 않는 이유를 설명해주세요.

> InnoDB는 읽기와 쓰기를 분리하기 위해 MVCC를 사용합니다. 데이터를 변경할 때 기존 값을 Undo Log에 보관하고, `DB_ROLL_PTR`로 이전 버전들을 체인으로 연결합니다. 읽기 트랜잭션은 자신의 Read View가 허용하는 버전을 이 체인에서 찾아 읽으므로 락 없이 동작합니다. 따라서 SELECT는 쓰기 트랜잭션을 블로킹하지 않고, 쓰기 트랜잭션도 읽기를 블로킹하지 않습니다. 고동시성 환경에서 읽기 처리량을 높게 유지할 수 있는 핵심 이유입니다.

### Q2. REPEATABLE READ에서도 팬텀 읽기가 발생할 수 있나요?

> 일반 SELECT에서는 MVCC가 Read View를 고정하기 때문에 발생하지 않습니다. 그러나 FOR UPDATE나 UPDATE 같은 현재 읽기에서는 Undo Log를 거치지 않고 최신 커밋 데이터를 읽기 때문에 팬텀이 발생할 수 있습니다. InnoDB는 이를 Next-Key Lock으로 방지합니다. 인덱스 범위에 Record Lock과 Gap Lock을 함께 걸어 다른 트랜잭션이 그 범위에 새 행을 삽입하지 못하게 막는 방식입니다.

### Q3. 장기 실행 트랜잭션이 시스템에 미치는 영향을 설명해주세요.

> 두 가지 문제가 동시에 발생합니다. 첫째, 락을 오래 붙잡아 다른 트랜잭션의 대기 시간이 길어지고 데드락 가능성이 높아집니다. 둘째, Read View를 오래 유지하기 때문에 Purge Thread가 Undo Log를 정리하지 못합니다. Undo Tablespace가 비대해지고 버전 체인이 길어지면 읽기 성능까지 저하됩니다. `information_schema.INNODB_TRX`와 `SHOW ENGINE INNODB STATUS`의 History list length를 모니터링하고, 애플리케이션 레벨에서 트랜잭션 타임아웃과 배치 처리 경계를 명확히 설정하는 것이 중요합니다.

### Q4. Undo Log와 Redo Log의 역할을 각각 설명해주세요.

> Undo Log는 변경 이전 데이터를 보관합니다. 롤백 시 이전 버전으로 복원하고, MVCC에서 오래된 스냅샷이 필요한 트랜잭션에게 이전 버전을 제공합니다. Redo Log는 변경 이후 데이터를 WAL 방식으로 기록합니다. 크래시 발생 시 재시작 과정에서 먼저 Redo Log를 재생해 커밋된 변경사항을 복구(Roll-Forward)하고, 이어서 Undo Log로 미완료 트랜잭션을 롤백(Roll-Back)합니다. Undo Log 자체도 Redo Log에 의해 보호받습니다. 크래시 직전 Undo Log 기록 중이었다면 Redo로 먼저 Undo Log를 복원해야 Roll-Back이 가능하기 때문입니다.

### Q5. FOR UPDATE와 일반 SELECT의 차이를 실무 사례로 설명해주세요.

> 재고 차감이 대표적입니다. 일반 SELECT는 스냅샷을 읽기 때문에 다른 세션이 이미 재고를 0으로 만들었어도 이전 값을 볼 수 있습니다. 이 값을 기준으로 차감하면 음수 재고가 발생합니다. FOR UPDATE는 최신 커밋값을 읽고 동시에 해당 레코드에 X Lock을 걸어 다른 세션의 동시 수정을 막습니다. 따라서 정확성이 중요한 "읽은 후 조건 판단하여 쓰기" 패턴에서는 반드시 FOR UPDATE를 사용해야 합니다. 단, FOR UPDATE 남용은 락 경합과 데드락을 유발하므로, 꼭 필요한 범위에만 사용하고 트랜잭션을 짧게 유지해야 합니다.

---

## 13. 핵심 체크리스트

### 개념

- [ ] `DB_TRX_ID`, `DB_ROLL_PTR`의 역할과 버전 체인 형성 원리를 설명할 수 있다.
- [ ] Insert Undo Log와 Update Undo Log의 생명주기 차이를 설명할 수 있다.
- [ ] Read View의 네 필드와 가시성 판단 알고리즘을 순서대로 설명할 수 있다.
- [ ] Undo Log와 Redo Log의 목적 차이를 한 문장으로 구분할 수 있다.

### 격리 수준

- [ ] `READ COMMITTED`와 `REPEATABLE READ`에서 Read View 생성 시점의 차이를 설명할 수 있다.
- [ ] 일관 읽기(Snapshot Read)와 현재 읽기(Current Read)의 차이와 각각의 사용 케이스를 설명할 수 있다.
- [ ] `UPDATE` 내부에서 Current Read가 발생하는 이유를 설명할 수 있다.

### 잠금

- [ ] Next-Key Lock이 Record Lock과 Gap Lock의 조합임을 설명할 수 있다.
- [ ] 유니크 인덱스 조건에서 Gap Lock이 생략(또는 변경)되는 이유를 설명할 수 있다.
- [ ] Gap Lock끼리 호환되지만 삽입 의도 락(Insert Intention Lock)과는 충돌하는 이유를 설명할 수 있다.

### Crash Recovery

- [ ] Roll-Forward → Roll-Back 순서와 각각에서 어떤 로그가 사용되는지 설명할 수 있다.
- [ ] Undo Log가 Redo Log로 보호받아야 하는 이유를 설명할 수 있다.
- [ ] `innodb_flush_log_at_trx_commit` 값에 따른 Durability 차이를 설명할 수 있다.

### 실무

- [ ] 재고 차감에서 FOR UPDATE가 필요한 이유를 스냅샷 읽기의 한계와 연결하여 설명할 수 있다.
- [ ] `SHOW ENGINE INNODB STATUS`에서 History list length의 의미와 증가 원인을 설명할 수 있다.
- [ ] 장기 트랜잭션이 Undo Log 비대화로 이어지는 경로를 단계별로 설명할 수 있다.

---

## 관련 문서

- [Gap Lock & Next-Key Lock 심층 분석](./innodb-gap-next-key-lock.md) — 구간 락 의미론, RR에서의 함정
- [InnoDB 트랜잭션과 잠금](./transaction-lock.md) — Lock 전체 개관
- [Deadlock Analysis](./deadlock-analysis.md) — 데드락 로그 해석
- [Redo Log](./redo-log.md) — WAL과 Undo Log의 관계
- [Spring 트랜잭션 전파·격리수준·AFTER_COMMIT](../../java/spring/transaction-propagation-isolation-after-commit.md) — 애플리케이션 경계에서의 격리 수준

---

*작성 기준: MySQL 8.0, InnoDB 스토리지 엔진, 기본 격리 수준 REPEATABLE READ*
