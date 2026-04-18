# [초안] MySQL 데드락 실전 분석 — SQS 컨슈머 환경에서 InnoDB 락을 읽고 풀어내는 법

## 왜 이 주제가 중요한가

백엔드에서 데드락은 "가끔 나는 현상"이 아니다. 트래픽이 올라가고, 동일 로직이 컨슈머 워커 N대에서 병렬로 돌고, 트랜잭션이 살짝 길어지기 시작하면 숨어 있던 락 충돌이 한꺼번에 터진다. 그리고 그 시점은 대부분 프로모션, 쿠폰 발급, 알림 발송 같은 "돈과 고객 경험이 걸린 순간"이다.

CJ OliveYoung 같은 이커머스 백엔드에서 실제로 터지는 장애의 패턴을 보면 이렇다. 주문 완료 → 알림톡 발송 이벤트를 SQS에 넣는다 → 컨슈머 여러 대가 같은 테이블(`notification_dispatch`, `order_notification_log`)을 업데이트한다 → 데드락이 수십 개씩 발생한다 → 컨슈머가 재시도를 퍼붓는다 → HikariCP 커넥션 풀이 말라버린다 → 본 서비스 API까지 5xx가 터진다. 이 연쇄 반응을 겪어본 사람은 "데드락은 격리된 DB 이슈"라는 말을 못 한다.

시니어 백엔드 면접에서 "주문 처리 중 데드락이 발생하고 있어요. 어떻게 접근하시겠습니까"라는 질문은 거의 항상 나온다. 이때 기대하는 답은 "재시도하면 됩니다"가 아니다. **락 레벨을 읽어내고, `SHOW ENGINE INNODB STATUS` 로그를 해독하고, 원인을 설계 단계까지 되짚어가는 능력**이다. 이 문서는 그 능력을 재현 가능한 수준으로 정리한다.

## InnoDB 락 모델 복습 — 데드락 로그를 읽기 위한 최소 지식

### Shared / Exclusive Lock

- **S lock (Shared)**: `SELECT ... LOCK IN SHARE MODE` 또는 외래키 참조 확인 시 획득. 다른 트랜잭션의 S는 허용, X는 차단.
- **X lock (Exclusive)**: `UPDATE`, `DELETE`, `SELECT ... FOR UPDATE`에서 획득. S/X 모두 차단.

단순해 보이지만, 이 조합에서 "FK 제약이 걸린 INSERT는 부모 테이블에 S 락을 건다"는 사실을 놓치면 데드락 로그를 절대 못 읽는다.

### Record / Gap / Next-Key Lock

REPEATABLE READ(RR) 격리 수준에서 InnoDB가 쓰는 핵심 락 단위다.

- **Record Lock**: 인덱스 레코드 자체에 걸리는 락.
- **Gap Lock**: 인덱스 레코드 사이의 "빈 공간"에 걸리는 락. 팬텀 리드를 막기 위해 존재.
- **Next-Key Lock**: Record + 그 앞의 Gap을 묶은 것. RR 기본 락 단위.

예를 들어 인덱스에 `user_id = 10, 20, 30` 레코드가 있을 때 `SELECT ... WHERE user_id BETWEEN 15 AND 25 FOR UPDATE`를 실행하면 InnoDB는 `20` 레코드뿐 아니라 `(10, 20]`과 `(20, 30]` Gap까지 락을 건다. 이 때문에 **다른 트랜잭션이 `user_id = 22`를 INSERT하려 하면 Gap Lock에 걸려 대기**한다.

### Intention Lock (IS, IX)

테이블 레벨의 "선언용" 락이다. "나는 이 테이블의 어딘가에 S/X 락을 걸 계획이다"를 알리는 용도. 실제 레코드 락과는 충돌하지 않지만, `LOCK TABLES`나 DDL과 충돌한다. 로그에 `IX`, `IS`가 보이면 "아 테이블 레벨 의도 락이구나" 정도로 읽고 넘어간다.

### Insert Intention Lock과 AUTO-INC

- **Insert Intention Lock**: Gap Lock의 특수 형태. 여러 트랜잭션이 같은 Gap에 INSERT하려 할 때 서로 충돌하지 않게 하는 최적화. 단, 누군가 이미 **일반 Gap Lock**을 들고 있으면 Insert Intention Lock은 대기한다. **이게 데드락의 단골 원인 중 하나**다.
- **AUTO-INC Lock**: `innodb_autoinc_lock_mode`에 따라 동작이 바뀐다. 기본값(`2`, consecutive)은 대부분 가볍지만, `INSERT ... SELECT`나 벌크 INSERT에서 긴 락이 생길 수 있다.

## 데드락 정의와 탐지 방법

데드락은 **두 개 이상의 트랜잭션이 서로가 들고 있는 락을 기다려서 영원히 풀리지 않는 상태**다. InnoDB는 대기 그래프(wait-for graph)를 주기적으로 검사해 사이클을 발견하면 **한 트랜잭션을 희생자로 골라 롤백**시킨다.

### 탐지에 쓰는 세 가지 관측 도구

```sql
-- 1. 최근 발생한 데드락 로그 (가장 중요)
SHOW ENGINE INNODB STATUS;
-- 출력 중 "LATEST DETECTED DEADLOCK" 섹션이 핵심

-- 2. 현재 실행 중인 트랜잭션
SELECT trx_id, trx_state, trx_started, trx_mysql_thread_id,
       trx_query, trx_rows_locked, trx_rows_modified,
       trx_isolation_level
FROM information_schema.innodb_trx
ORDER BY trx_started;

-- 3. 지금 이 순간 걸려 있는 락 (MySQL 8 기준)
SELECT ENGINE_TRANSACTION_ID AS trx_id,
       OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME,
       LOCK_TYPE, LOCK_MODE, LOCK_STATUS, LOCK_DATA
FROM performance_schema.data_locks;

-- 4. 락 대기 관계
SELECT REQUESTING_ENGINE_TRANSACTION_ID AS waiting_trx,
       BLOCKING_ENGINE_TRANSACTION_ID  AS blocking_trx
FROM performance_schema.data_lock_waits;
```

운영 환경에서는 `innodb_print_all_deadlocks = ON`으로 해두면 발생 즉시 에러 로그로 떨어져 추적이 쉬워진다.

## 데드락 로그 읽는 법

아래는 실전에서 자주 보는 로그 형태다. 이걸 한 줄씩 해독할 줄 알아야 한다.

```
LATEST DETECTED DEADLOCK
------------------------
2026-04-17 03:14:21 0x7f9a

*** (1) TRANSACTION:
TRANSACTION 4821993, ACTIVE 0 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 3 lock struct(s), heap size 1128, 2 row lock(s)
MySQL thread id 88123, OS thread handle ...
UPDATE notification_dispatch
   SET status = 'SENT'
 WHERE dispatch_id = 120451;

*** (1) HOLDS THE LOCK(S):
RECORD LOCKS space id 512 page no 41 n bits 144 index PRIMARY
of table `oy`.`notification_dispatch` trx id 4821993 lock_mode X locks rec but not gap

*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 512 page no 41 n bits 144 index idx_order_id
of table `oy`.`notification_dispatch` trx id 4821993 lock_mode X waiting

*** (2) TRANSACTION:
TRANSACTION 4821994, ACTIVE 0 sec starting index read
UPDATE notification_dispatch
   SET retry_count = retry_count + 1
 WHERE order_id = 998877;

*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 512 page no 41 n bits 144 index idx_order_id
of table `oy`.`notification_dispatch` trx id 4821994 lock_mode X

*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 512 page no 41 n bits 144 index PRIMARY
of table `oy`.`notification_dispatch` trx id 4821994 lock_mode X waiting

*** WE ROLL BACK TRANSACTION (2)
```

해독 포인트:

1. **TRX 블록 수**: 두 개가 전형적이다. 세 개 이상이면 대기 그래프가 꼬였다는 뜻.
2. **HOLDS / WAITING FOR**: 각 트랜잭션이 무엇을 들고 있고 무엇을 기다리는지 명확히 나와 있다.
3. **인덱스 이름**: `PRIMARY`, `idx_order_id` 같은 값. "어느 인덱스에서 락 충돌이 일어나는지"가 로그의 핵심.
4. **`lock_mode X locks rec but not gap`**: Record Lock만 (RC 격리 수준이거나 unique index 조회). `lock_mode X`만 있으면 Next-Key Lock.
5. **희생자 선택**: InnoDB는 `undo log` 크기, 즉 **롤백 비용이 더 작은 트랜잭션**을 희생자로 고른다. 큰 벌크 UPDATE는 살아남고, 짧은 UPDATE가 죽는 경향이 있다.
6. 위 예제의 본질: 트랜잭션 1은 PK → 보조 인덱스 순서로 락을, 트랜잭션 2는 보조 인덱스 → PK 순서로 락을 잡는다. **락 획득 순서가 역순**이다. 전형적인 데드락.

## 전형적인 데드락 패턴

### 패턴 1. 역순 락 획득

```sql
-- 트랜잭션 A
BEGIN;
UPDATE account SET balance = balance - 1000 WHERE id = 1;
UPDATE account SET balance = balance + 1000 WHERE id = 2;

-- 트랜잭션 B
BEGIN;
UPDATE account SET balance = balance - 500 WHERE id = 2;
UPDATE account SET balance = balance + 500 WHERE id = 1;
```

A는 1→2, B는 2→1. 둘이 동시에 돌면 데드락. **해결**: 항상 `MIN(id), MAX(id)` 순서로 정렬해서 락을 건다.

### 패턴 2. INSERT + FK 확인 경합

부모 테이블을 참조하는 FK가 있는 자식 테이블에 INSERT할 때 InnoDB는 부모 레코드에 **S 락**을 건다. 부모를 같은 순간에 UPDATE(X 락)하려는 다른 트랜잭션이 있으면 데드락.

### 패턴 3. UPDATE + SELECT FOR UPDATE 경합

```sql
-- 컨슈머 A
SELECT * FROM outbox WHERE status = 'PENDING' LIMIT 10 FOR UPDATE SKIP LOCKED;
-- 컨슈머 B
UPDATE outbox SET status = 'DONE' WHERE id IN (...);
```

`SKIP LOCKED`가 없으면 Gap Lock이 넓게 잡히고, B의 UPDATE가 Gap Lock과 충돌한다. MySQL 8에서 **`FOR UPDATE SKIP LOCKED`는 컨슈머 패턴의 기본기**다.

### 패턴 4. AUTO-INC 경합

`innodb_autoinc_lock_mode = 1` (consecutive)에서 벌크 INSERT 두 개가 동시에 돌면 AUTO-INC 락 대기가 길어진다. 8.0 기본은 `2`(interleaved)라 대부분 문제없지만, statement-based replication 쓰는 환경은 여전히 조심해야 한다.

### 패턴 5. Gap Lock과 RR 특유의 데드락

```sql
-- 세션 A (RR)
SELECT * FROM coupon WHERE user_id = 100 FOR UPDATE;
-- 이 시점 user_id = 100인 행이 없으면 Gap Lock이 걸림

-- 세션 B
INSERT INTO coupon(user_id, code) VALUES (100, 'X');
-- Insert Intention Lock이 세션 A의 Gap Lock에 막혀 대기

-- 세션 A
INSERT INTO coupon(user_id, code) VALUES (100, 'Y');
-- 세션 B의 Insert Intention Lock이 Gap을 점유 → 데드락
```

이 패턴은 **RR 격리 + unique index 중복 체크 후 INSERT** 코드에서 끔찍하게 자주 터진다. 해결은 (1) 격리 수준을 READ COMMITTED로 낮추거나 (2) `INSERT ... ON DUPLICATE KEY UPDATE`로 원자화하거나 (3) unique 인덱스만 믿고 예외를 잡아 처리하는 것.

## SQS / Kafka 컨슈머 병렬 실행에서의 락 충돌

컨슈머 환경의 본질은 "같은 로직이 N대에서 동시에 돈다"는 것이다. 테스트 환경에서 멀쩡하던 코드가 운영에서 죽는 이유의 90%가 이것.

### 시나리오: 알림톡 발송 중복 방지

```java
@Transactional
public void dispatch(Long orderId) {
    NotificationLog log = repo.findByOrderId(orderId).orElse(null);
    if (log != null && log.isSent()) return;

    if (log == null) {
        log = new NotificationLog(orderId);
        repo.save(log);                          // INSERT
    }
    sender.send(orderId);                        // 외부 API
    log.markSent();                              // UPDATE
}
```

문제:
1. `findByOrderId` → `save`는 원자적이지 않다. 두 컨슈머가 동시에 들어오면 둘 다 `null`을 보고 둘 다 INSERT한다.
2. unique 제약이 있다면 한 쪽은 `DuplicateKeyException`을 먹는다. 없으면 중복 발송.
3. INSERT 사이에 Gap Lock이 끼어 데드락이 발생한다.
4. 외부 API 호출이 트랜잭션 안에 있어 트랜잭션이 길어진다. 커넥션 풀 고갈의 지름길.

### 해법 1. Idempotency + Unique Key

`order_id`에 unique 인덱스를 걸고, `INSERT ... ON DUPLICATE KEY UPDATE`나 "먼저 insert 시도 → duplicate면 update"로 원자화한다.

```sql
INSERT INTO notification_log (order_id, status, created_at)
VALUES (?, 'PENDING', NOW())
ON DUPLICATE KEY UPDATE created_at = created_at;
```

### 해법 2. SELECT ... FOR UPDATE SKIP LOCKED

큐 테이블 패턴에서는 이게 거의 정답이다.

```sql
SELECT id FROM outbox
 WHERE status = 'PENDING'
 ORDER BY id
 LIMIT 50
 FOR UPDATE SKIP LOCKED;
```

### 해법 3. 분산락 (Redis / DB Named Lock)

컨슈머 단위로 `orderId`를 키로 분산락을 걸어 동일 주문은 한 번에 한 컨슈머만 처리하게 만든다. 단, 이건 "락 순서 뒤집힘"을 해결하지 못하므로 DB 설계와 함께 간다.

### 해법 4. 외부 API는 트랜잭션 밖으로

트랜잭션 안에서 외부 HTTP 호출을 하지 않는다. DB 상태 변경만 트랜잭션 안에 두고, 발송은 트랜잭션 커밋 후 이벤트 리스너/아웃박스 패턴으로 분리한다.

## 데드락을 줄이는 설계 원칙 (순서 중요)

1. **락 획득 순서를 전역적으로 정렬한다.** ID 오름차순, 계좌 번호 오름차순 등. 코드 리뷰에서 "정말 같은 순서인가"를 본다.
2. **트랜잭션을 짧게 유지한다.** 특히 외부 I/O(HTTP, Kafka produce, S3)는 트랜잭션 밖으로.
3. **인덱스로 락 범위를 좁힌다.** 풀 스캔은 테이블 전체에 Next-Key Lock을 걸 수 있다. 후보자가 slot팀에서 "복합 인덱스로 전환해 락 경합을 줄였다"고 했던 그 경험이 정확히 이 원칙.
4. **비즈니스 키에 unique 인덱스를 건다.** 중복 체크를 애플리케이션에서 하지 말고 DB에 위임.
5. **낙관적 락(OCC)을 검토한다.** 경합이 낮을 것으로 예상되는 도메인(상품 상세, 설정값)은 `@Version`으로 충분하다.
6. **upsert / merge를 활용한다.** "select → 없으면 insert → 있으면 update" 세 단계는 동시성의 적이다.
7. **격리 수준을 다시 본다.** 이커머스 주문 도메인에서 RC가 적합한 경우가 많다. RR의 Gap Lock은 비싼 장치다.

## 커넥션 풀 고갈과 데드락의 연쇄

HikariCP `maximumPoolSize = 20`인 서비스에서 긴 트랜잭션 + 데드락 재시도가 결합되면 이런 일이 일어난다.

```
t=0s  : 컨슈머 10대 각자 트랜잭션 시작 (커넥션 10개 점유)
t=1s  : 데드락 발생, 한 쪽 롤백, 재시도
t=2s  : 재시도 트랜잭션이 같은 락을 또 기다림
t=3s  : 컨슈머 추가 10대 가세 (커넥션 20개 점유, 풀 고갈)
t=5s  : 본 서비스 API 요청이 커넥션을 못 받아 타임아웃
t=8s  : 헬스체크 실패로 인스턴스 순환 재시작
```

방어책:
- **풀 사이즈는 "CPU 코어 × 2 + 디스크 수"가 출발점** (HikariCP 공식 가이드). 무조건 늘린다고 좋은 게 아니다.
- `connectionTimeout`을 짧게(예: 3s) 잡아 빠르게 실패.
- 트랜잭션 타임아웃(`@Transactional(timeout = 3)`)과 `innodb_lock_wait_timeout`(기본 50s → 5~10s로 낮춤)을 정렬.
- 컨슈머 프리페치 크기를 제한해 DB로 쏟아지는 동시성을 조절.

## Spring Retry + 트랜잭션 + 데드락 재시도 전략

Spring은 데드락을 `DeadlockLoserDataAccessException`(DataAccessException 계열)으로 감싼다. 재시도는 **트랜잭션 밖**에서 해야 한다. 트랜잭션 내부에서 재시도하면 같은 트랜잭션이 이미 롤백 표시된 상태라 의미가 없다.

```java
@Service
public class NotificationService {

    @Retryable(
        retryFor = { DeadlockLoserDataAccessException.class,
                     CannotAcquireLockException.class },
        maxAttempts = 3,
        backoff = @Backoff(delay = 50, multiplier = 2.0, random = true)
    )
    public void dispatch(Long orderId) {
        txTemplate.execute(status -> {
            doDispatch(orderId);
            return null;
        });
    }

    @Recover
    public void recover(DeadlockLoserDataAccessException e, Long orderId) {
        deadLetterQueue.send(orderId, e.getMessage());
    }
}
```

포인트:
- `@Retryable`은 `@Transactional`을 감싸는 바깥 레이어에 둔다.
- 백오프에 `random = true`를 준다. 동시에 재시도하는 컨슈머가 또 부딪힐 수 있다.
- 재시도 한계 도달 시 DLQ로 옮기고 알림을 띄운다. 무한 재시도는 장애를 키운다.

## 로컬 재현 환경

Docker로 MySQL 8 띄우고 두 세션으로 재현한다.

```bash
docker run --name mysql8 -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=labs -p 3306:3306 -d mysql:8.0 \
  --innodb_print_all_deadlocks=ON \
  --transaction_isolation=REPEATABLE-READ
```

```sql
CREATE TABLE account (
  id BIGINT PRIMARY KEY,
  balance BIGINT NOT NULL
) ENGINE=InnoDB;

INSERT INTO account VALUES (1, 10000), (2, 10000);
```

## 실행 가능한 예제 1 — 역순 락 데드락 재현

두 개의 `mysql` 클라이언트 세션을 연다.

세션 A:
```sql
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;  -- X lock on id=1
-- 여기서 멈춤
```

세션 B:
```sql
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 2;  -- X lock on id=2
UPDATE account SET balance = balance + 100 WHERE id = 1;  -- 대기 (A가 id=1 락 소유)
```

세션 A로 돌아와서:
```sql
UPDATE account SET balance = balance + 100 WHERE id = 2;
-- ERROR 1213 (40001): Deadlock found when trying to get lock;
-- try restarting transaction
```

곧바로:
```sql
SHOW ENGINE INNODB STATUS\G
```

`LATEST DETECTED DEADLOCK` 블록을 읽어 둘의 HOLDS / WAITING FOR 패턴이 정확히 엇갈리는 것을 확인한다.

## 실행 가능한 예제 2 — Gap Lock 데드락

```sql
CREATE TABLE coupon (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  code VARCHAR(32) NOT NULL,
  UNIQUE KEY uk_user (user_id, code)
) ENGINE=InnoDB;
```

세션 A:
```sql
BEGIN;
SELECT * FROM coupon WHERE user_id = 500 FOR UPDATE; -- 결과 0건, Gap Lock 획득
```

세션 B:
```sql
BEGIN;
SELECT * FROM coupon WHERE user_id = 501 FOR UPDATE; -- 결과 0건, 다른 Gap Lock
INSERT INTO coupon(user_id, code) VALUES (500, 'B');  -- A의 Gap에 막혀 대기
```

세션 A:
```sql
INSERT INTO coupon(user_id, code) VALUES (501, 'A');  -- B의 Gap에 막혀 데드락
```

해결안을 비교해본다.
- RC로 격리 수준을 낮추면: 대부분의 Gap Lock이 사라진다. `INSERT` 둘 다 성공하거나 unique 제약 위반만 난다.
- unique 인덱스 믿고 `INSERT ... ON DUPLICATE KEY UPDATE`를 쓰면: `SELECT FOR UPDATE`가 필요 없어지고 Gap Lock 자체를 피한다.

## 나쁜 설계 vs 개선된 설계

**나쁜 버전**

```java
@Transactional
public void processOrder(Long orderId, Long userId, List<Long> itemIds) {
    Order order = orderRepo.findById(orderId).orElseThrow();
    for (Long itemId : itemIds) {
        Stock stock = stockRepo.findByIdForUpdate(itemId);
        stock.decrease(1);
    }
    emailClient.sendConfirmation(userId);       // 외부 I/O
    order.markPaid();
}
```

문제:
- `itemIds`가 호출마다 순서가 다르면 락 순서가 달라져 데드락.
- 외부 메일 호출이 트랜잭션 안에 있어 트랜잭션이 수백 ms ~ 수 초까지 길어짐.
- `findByIdForUpdate`가 보조 인덱스를 타면 Next-Key Lock이 불필요하게 넓게 걸림.

**개선된 버전**

```java
public void processOrder(Long orderId, Long userId, List<Long> itemIds) {
    List<Long> sorted = itemIds.stream().sorted().toList(); // 락 순서 고정

    txTemplate.execute(status -> {
        Order order = orderRepo.findById(orderId).orElseThrow();
        for (Long itemId : sorted) {
            int updated = stockRepo.decreaseIfAvailable(itemId, 1); // 단일 UPDATE
            if (updated == 0) throw new OutOfStockException(itemId);
        }
        order.markPaid();
        eventPublisher.publishAfterCommit(new OrderPaidEvent(orderId, userId));
        return null;
    });
}
```

`stockRepo.decreaseIfAvailable`:
```sql
UPDATE stock SET qty = qty - :n
 WHERE item_id = :itemId AND qty >= :n;
```

개선 포인트:
- 락 획득 순서를 `itemId` 오름차순으로 고정.
- `SELECT FOR UPDATE` 대신 조건부 UPDATE로 락 구간 단축.
- 외부 I/O는 `@TransactionalEventListener(AFTER_COMMIT)`로 분리.
- 트랜잭션 타임아웃과 `innodb_lock_wait_timeout`을 짧게 세팅해 커넥션 고갈 방지.

## 실전 분석 워크플로

1. **증상 재확인**: 어느 API/컨슈머/작업에서 몇 시부터 데드락이 찍혔는가. 로그에서 `Deadlock found` 카운트.
2. **로그 캡처**: `SHOW ENGINE INNODB STATUS`의 `LATEST DETECTED DEADLOCK`, `innodb_print_all_deadlocks=ON`으로 남는 에러 로그. 가능하면 5분치 이상.
3. **트랜잭션 / 쿼리 정체 확인**: `innodb_trx`, `data_locks`, `data_lock_waits`로 그 순간 어떤 락이 걸려 있었는지 확인.
4. **원인 가설 3가지 이상**: 역순 락? Gap Lock? FK 경합? 인덱스 없음? 하나로 단정하지 말고 후보를 나열.
5. **재현**: 로컬 MySQL 8로 같은 스키마/격리 수준에서 재현한다. 재현 안 되면 가설이 틀렸다는 증거.
6. **수정**: 락 순서 정렬, 트랜잭션 분리, 인덱스 추가, 격리 수준 조정, upsert 전환 중 최소 침습 선택.
7. **회귀 테스트**: 동일 시나리오를 부하 테스트(`k6`, `jmeter`)로 돌려 데드락 수가 0에 수렴하는지 확인. 수정 전/후 에러 카운트를 그래프로 붙인다.
8. **런북 업데이트**: 팀 위키에 "이런 로그가 또 보이면 이렇게 읽어라"를 남긴다.

## 후보자 경험과의 연결

slot팀에서 "DB 유니크 키 기반 동시성 제어"와 "복합 인덱스 튜닝으로 락 범위 축소"를 해본 경험은 이 주제와 정확히 맞물린다. 면접에서 이렇게 연결한다.

- 중복 발급 방지: "애플리케이션에서 select-then-insert로 막던 것을 `UNIQUE(user_id, event_id)`에 올리고 `INSERT ... ON DUPLICATE KEY UPDATE`로 원자화했습니다. Gap Lock으로 발생하던 데드락이 사라졌습니다."
- 복합 인덱스 튜닝: "`(status, updated_at)` 인덱스를 만들어 컨슈머 조회가 풀 스캔 대신 인덱스 레인지를 타도록 바꿨습니다. Next-Key Lock 범위가 좁아져 경합이 줄었습니다."

이런 구체 수치(예: "데드락 분당 20건 → 0건", "p99 레이턴시 800ms → 120ms")까지 준비하면 시니어 톤이 완성된다.

## 면접 답변 프레이밍

**질문**: "주문 처리에서 데드락이 계속 나고 있어요. 어떻게 분석하고 해결하시겠어요?"

**답변 구조 (STAR + 기술 디테일)**

1. **상황 정의**: "먼저 범위를 좁힙니다. 어느 트랜잭션 쌍에서, 어느 인덱스에서, 어떤 격리 수준에서 나는지를 확인합니다."
2. **관측**: "`innodb_print_all_deadlocks`을 켜고, `SHOW ENGINE INNODB STATUS`의 `LATEST DETECTED DEADLOCK` 블록을 수집합니다. `performance_schema.data_locks`로 실시간 락 상태도 봅니다."
3. **가설**: "가장 흔한 패턴 세 가지, 역순 락, Gap Lock + Insert Intention, FK 경합을 먼저 의심합니다. 로그에서 HOLDS / WAITING FOR의 인덱스 이름을 보면 구분됩니다."
4. **재현**: "로컬 MySQL 8에서 동일 스키마로 두 세션 시나리오를 재현합니다. 재현 안 되면 가설을 바꿉니다."
5. **수정 원칙**: "락 순서 정렬, 트랜잭션 단축, 인덱스로 락 범위 축소, 필요하면 격리 수준을 RC로 내립니다. 비즈니스 키는 unique 인덱스에 맡기고 upsert로 원자화합니다."
6. **컨슈머 관점**: "같은 로직을 병렬 워커로 돌리는 환경이면 `FOR UPDATE SKIP LOCKED`나 분산락으로 경합을 줄이고, 외부 I/O는 트랜잭션 밖으로 뺍니다."
7. **재시도**: "Spring Retry로 `DeadlockLoserDataAccessException`에 대해 지수 백오프 + 지터로 최대 3회 재시도, 실패 시 DLQ. 재시도는 반드시 트랜잭션 외부에서 합니다."
8. **운영 보호**: "커넥션 풀 사이즈, 커넥션 타임아웃, `innodb_lock_wait_timeout`, 트랜잭션 타임아웃을 같이 조정합니다. 한 가지만 만지면 다른 곳이 터집니다."
9. **검증**: "부하 테스트로 데드락 카운트와 p99가 목표치에 수렴하는지 확인하고 런북을 업데이트합니다."

여기에 본인 경험("slot팀에서 유니크 키로 중복 발급 데드락을 없앴다", "복합 인덱스로 Next-Key Lock 범위를 좁혀 경합을 70% 줄였다")을 한 문장 얹으면 바로 시니어 톤이다.

## 자가 체크리스트

- [ ] `LATEST DETECTED DEADLOCK` 블록을 보고 TRX1/TRX2의 HOLDS / WAITING FOR 인덱스를 짚어낼 수 있다.
- [ ] Record / Gap / Next-Key / Insert Intention Lock의 차이를 한 문장씩 설명할 수 있다.
- [ ] RR과 RC에서 Gap Lock 동작이 어떻게 달라지는지 예제로 보일 수 있다.
- [ ] `performance_schema.data_locks`와 `data_lock_waits`를 조인해 현재 대기 관계를 뽑는 쿼리를 쓸 수 있다.
- [ ] 역순 락 데드락을 로컬 MySQL 8에서 10분 안에 재현할 수 있다.
- [ ] Gap Lock 기반 데드락을 재현하고, 격리 수준 변경과 upsert로 각각 해결해보았다.
- [ ] `SELECT FOR UPDATE SKIP LOCKED`를 언제 쓰는지, 왜 쓰는지 말할 수 있다.
- [ ] Spring Retry + `@Transactional` 배치 순서를 실수 없이 그릴 수 있다.
- [ ] HikariCP 풀 사이즈, `innodb_lock_wait_timeout`, `@Transactional(timeout)`을 함께 설계할 수 있다.
- [ ] 외부 I/O를 트랜잭션 밖으로 빼는 세 가지 방법(비동기 이벤트, 아웃박스, AFTER_COMMIT 리스너)을 설명할 수 있다.
- [ ] 데드락 수정 후 회귀 테스트로 수치 개선을 증명하는 루프를 갖고 있다.
- [ ] 본인의 slot팀 유니크 키 / 복합 인덱스 경험을 2분 이내로 데드락 해결 스토리로 엮어 말할 수 있다.
