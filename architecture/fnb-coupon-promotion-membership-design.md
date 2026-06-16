# [초안] F&B 쿠폰·프로모션·멤버십·포인트 설계

## 왜 중요한가

F&B 이커머스에서 쿠폰·프로모션·멤버십·포인트는 매출 직결 도메인이면서 동시에 가장 컴플레인이 많이 나오는 영역이다. 한 번의 결제에 "신규가입 쿠폰", "브랜드 쿠폰", "매장 쿠폰", "메뉴 쿠폰", "통신사 제휴 할인", "멤버십 등급 할인", "포인트 사용"이 동시에 얹히고, 발급·사용·취소·환불이 비동기로 흐른다. 정책이 잘못 설계되면 같은 쿠폰이 두 번 차감되거나, 환불 후 쿠폰이 살아나지 않거나, 선착순 이벤트가 정원을 초과 발급한다. 이 도메인은 "어떻게 만들겠다"가 아니라 "어떤 실패를 어떻게 막겠다"가 핵심이다.

F&B·헬스앤뷰티 같은 멀티브랜드 도메인은 여러 브랜드 × 멀티채널(앱, 웹, 매장 POS, 키오스크) × 멀티 결제수단이 결합된다. 같은 쿠폰이 매장에서는 인쇄 바코드로, 앱에서는 푸시 카드로, 키오스크에서는 QR로 들어오는데 백엔드는 한 정책으로 검증해야 한다. 즉 "쿠폰 = 단순 할인 코드"가 아니라 "조건·우선순위·재고·발급정책·복구정책을 가진 정책 객체"로 다뤄야 한다.

## 도메인 모델 — 4개 축을 분리한다

쿠폰을 한 테이블로 만들면 6개월 안에 망가진다. 기능적으로 다음 4개 축을 분리한다.

1. **쿠폰 정의**(Coupon Definition) — 어떤 할인인가. 할인 종류(정액/정률/N+1/무료배송), 적용 대상(브랜드/매장/카테고리/메뉴), 사용 조건(최소 금액, 시간대, 요일, 채널), 중복 가능 정책.
2. **쿠폰 발급**(Coupon Issue) — 누구에게 몇 장, 언제까지. 1인 1매, 계정당 N매, 선착순 N명, 다운로드형, 자동 발급(생일/등급업).
3. **쿠폰 사용**(Coupon Redemption) — 한 결제에서 어느 쿠폰을 어떻게 적용했는가. 멱등성 보장이 핵심.
4. **쿠폰 회수**(Coupon Restore) — 결제 취소·환불·CS 복구 시 사용 이력을 되돌리는 흐름.

`coupon_template` (정의) → `coupon_issue` (사용자별 보유 쿠폰 인스턴스) → `coupon_use_log` (사용 이력) 3계층이 가장 확장이 잘 된다. `coupon_issue`는 `(template_id, user_id, status, expire_at)`로 인덱스를 잡고, `status`는 `ISSUED / RESERVED / USED / EXPIRED / RESTORED` 5상태 머신으로 둔다. `RESERVED`는 결제 진입 시점에 잠그는 중간 상태로, 이걸 빼면 결제 동시 진행 시 같은 쿠폰이 두 번 적용된다.

## 핵심 정합성 원칙 — 멱등키와 상태 전이

쿠폰 도메인은 분산 트랜잭션을 피하면서도 정합성을 보장해야 한다. 가장 안전한 패턴은 다음 두 가지다.

- **멱등키**(Idempotency Key): 결제 요청별로 `order_id`를 멱등키로 사용하고, `coupon_use_log(order_id, coupon_issue_id) UNIQUE` 제약을 건다. 같은 주문에 대한 재시도가 와도 두 번 차감되지 않는다.
- **CAS 기반 상태 전이**: 쿠폰 사용은 `UPDATE coupon_issue SET status='USED', used_at=NOW() WHERE id=? AND status='ISSUED'` 형태의 조건부 업데이트로 한다. `affected rows = 0`이면 이미 누가 썼다는 뜻이고 즉시 실패시킨다.

```sql
UPDATE coupon_issue
   SET status = 'USED',
       used_at = NOW(6),
       order_id = :orderId
 WHERE id = :couponIssueId
   AND user_id = :userId
   AND status = 'ISSUED'
   AND expire_at > NOW(6);
```

이 한 줄이면 분산락 없이도 단일 쿠폰의 이중 사용을 막는다. 비관적 락(`SELECT ... FOR UPDATE`)을 거는 코드도 자주 보이지만, 결제 트랜잭션이 길어지면 락 대기로 결제 큐가 막히기 때문에 단건 CAS가 더 낫다.

## 선착순 이벤트 — Redis가 정답인 이유

"오전 10시 쿠폰 1만장 선착순 발급" 같은 이벤트는 RDBMS만으로는 풀리지 않는다. RDBMS에 `INSERT INTO coupon_issue ... WHERE (SELECT COUNT(*) FROM coupon_issue WHERE template_id=?) < 10000` 같은 쿼리를 박으면 락 경합으로 DB가 죽는다. 패턴은 다음과 같다.

1. 이벤트 시작 전, Redis에 `event:{id}:stock = 10000`을 세팅한다.
2. 요청이 들어오면 `DECR event:{id}:stock`을 먼저 호출한다.
3. 반환값이 0 이상이면 RabbitMQ/Kafka에 발급 메시지를 넣는다. 음수가 되면 즉시 "마감" 응답.
4. 컨슈머가 `coupon_issue` INSERT를 비동기로 처리한다.
5. 1인 1매 제약은 Redis `SET NX`(`SET event:{id}:user:{userId} 1 NX EX 86400`)으로 본다.

이 구조에서 핵심은 **"재고 차감"과 "DB 발급"을 분리**하는 것이다. 재고 차감은 Redis 단일 명령으로 원자성을 보장하고, DB 발급은 메시지 큐 컨슈머가 자기 페이스로 처리한다. 발급 메시지가 유실되면 안 되니 큐는 publisher confirm + persistent + at-least-once로 둔다. 멱등키는 `(event_id, user_id)`이면 충분하다.

"왜 Redis를 캐시가 아닌 진실의 원천처럼 쓰는가"에 대한 답은 다음과 같다. 선착순 카운터는 일시적 진실이고, 영구 진실은 컨슈머가 RDBMS에 쓰는 `coupon_issue` 행이다. Redis는 게이트키퍼 역할이고, 실패 시 발급 메시지를 다시 흘려서 RDBMS 기준으로 정합성을 맞춘다.

## 정책 엔진 — 우선순위와 중복 가능 규칙

브랜드·매장·메뉴별 적용 조건은 정책 엔진으로 분리한다. 각 쿠폰은 다음 정보를 가진다.

- `scope`: `BRAND` / `STORE` / `CATEGORY` / `MENU` / `ORDER_TOTAL`
- `target_ids`: 적용 대상 식별자 리스트
- `discount_type`: `FIXED` / `PERCENT` / `BOGO` / `FREE_DELIVERY`
- `priority`: 적용 우선순위 (낮을수록 먼저)
- `stackable_with`: 같이 쓸 수 있는 쿠폰 그룹 ID

결제 시 정책 엔진은 `장바구니 → 적용 가능한 쿠폰 후보 추출 → 우선순위 정렬 → 중복 가능 규칙으로 필터링 → 최적 조합 선택`의 파이프라인을 돈다. 일반적인 적용 순서는 **메뉴 단위 할인 → 카테고리 할인 → 주문 총액 할인 → 멤버십 등급 할인 → 포인트 사용 → 결제 수단 할인**이다. 이 순서가 바뀌면 같은 쿠폰이 다른 금액으로 찍힌다.

"최적 조합 선택"은 욕심껏 하면 NP 문제가 된다. 실무에서는 그리디(최대 할인 1장)와 정책상 허용된 조합만 시뮬레이션하는 형태로 컷한다. 멀티브랜드면 "브랜드 쿠폰 1장 + 매장 쿠폰 1장 + 멤버십 할인 1개 + 포인트"로 슬롯을 정해두는 게 현실적이다.

## 포인트 — 가용/적립예정/만료 분리

포인트는 쿠폰보다 골치 아프다. 조회 시점의 잔액과 사용 가능 잔액이 다르고, 환불 시 적립 취소까지 따라온다. 모델은 다음과 같이 잡는다.

- `point_balance(user_id, available, pending, locked)`: 합산 캐시.
- `point_transaction(id, user_id, type, amount, source_order_id, expire_at, status)`: 모든 변동의 단일 진실원.

`type`은 `EARN / USE / EXPIRE / CANCEL_EARN / CANCEL_USE`. 잔액은 `point_transaction`의 합으로 계산되고, `point_balance`는 그 캐시일 뿐이다. 캐시 정합성이 깨지면 정기 배치로 재계산한다. 이 구조에서 **읽기 빈도가 매우 높다**는 점이 중요하다 — 결제 화면, 마이페이지, 주문 내역 모두 잔액을 부른다. 읽기 전용 잔액 조회는 Redis 캐시 + StampedLock의 `tryOptimisticRead`로 받쳐주면 락 경합 없이 처리량을 끌어올릴 수 있다. 잔액이 갱신될 때만 `writeLock`으로 캐시를 무효화한다.

차감은 항상 멱등키 기반이다. `INSERT INTO point_transaction(order_id, type, ...) VALUES(...)`에 `UNIQUE(order_id, type)`을 걸면 결제 재시도에도 이중 차감이 안 일어난다. 만료는 별도 스케줄러가 `expire_at < NOW() AND status='ACTIVE'`인 적립건을 `EXPIRE`로 마킹하고 잔액 캐시를 갱신한다.

## 나쁜 예 vs 개선 예

### 나쁜 예 — 쿠폰 사용을 SELECT 후 UPDATE로 처리

```java
// 두 번 사용될 수 있다
Coupon coupon = couponRepo.findById(id);
if (coupon.getStatus() == ISSUED) {
    coupon.setStatus(USED);
    couponRepo.save(coupon);
}
```

동일 쿠폰을 두 탭에서 동시에 결제 시도하면 둘 다 `ISSUED`를 보고 둘 다 `USED`로 바꾼다. 두 주문 모두 할인이 들어간다.

### 개선 예 — 조건부 UPDATE + 멱등 로그

```java
int updated = couponMapper.markUsedIfIssued(couponIssueId, userId, orderId);
if (updated == 0) {
    throw new CouponAlreadyUsedException(couponIssueId);
}
couponUseLogMapper.insertIgnore(orderId, couponIssueId, appliedAmount);
```

`updated == 0`이면 이미 누군가 썼거나 만료되었다는 뜻이고 즉시 실패다. `INSERT IGNORE`로 로그가 멱등하게 들어가서 재시도해도 같은 결과다.

### 나쁜 예 — 환불 시 쿠폰 단순 복구

```java
coupon.setStatus(ISSUED); // 만료된 쿠폰도 살아난다
```

### 개선 예 — 정책에 따른 복구

```java
if (coupon.getExpireAt().isBefore(now)) {
    couponMapper.markRestoredButExpired(couponIssueId);
    // CS 정책에 따라 별도 보상 쿠폰 발급 또는 포인트 환급
} else {
    couponMapper.markRestoredAndReusable(couponIssueId);
}
auditLog.record(RESTORE, couponIssueId, orderId, reason);
```

복구는 단순 상태 토글이 아니라 **만료 여부, 환불 사유, CS 정책**을 모두 본다. 그리고 모든 복구는 감사 로그에 남긴다 — 누가, 언제, 왜.

## 동시성 — 어디서 어떤 도구를 쓰는가

- **단일 쿠폰의 이중 사용 방지**: DB CAS UPDATE. 락 불필요.
- **선착순 재고 차감**: Redis `DECR`. 단일 명령 원자성.
- **사용자당 1매 제약**: Redis `SET NX` 또는 DB `UNIQUE(template_id, user_id)`.
- **포인트 잔액 조회 핫패스**: StampedLock `tryOptimisticRead` + Redis 캐시. 쓰기 시 무효화.
- **포인트 차감/적립**: DB 트랜잭션 + 멱등키 UNIQUE.
- **결제 후 비동기 적립/차감 메시지**: RabbitMQ/Kafka, publisher confirm + at-least-once + 컨슈머 멱등성.

분산락(Redisson `RLock`)은 마지막 수단이다. 위 도구로 안 풀릴 때만 쓰는데, 쿠폰·포인트 도메인은 거의 모두 위 도구로 풀린다.

## 감사 로그와 CS 운영

쿠폰·포인트는 돈과 같다. 모든 상태 변경은 append-only 로그에 남긴다.

- `coupon_audit_log(coupon_issue_id, action, before_status, after_status, actor, reason, created_at)`
- `point_audit_log(transaction_id, action, amount, before_balance, after_balance, actor, reason, created_at)`

`actor`는 `USER` / `SYSTEM` / `CS_AGENT_ID`. CS가 직접 복구한 건은 반드시 사람의 ID가 남아야 한다. 이 로그는 별도 OLAP 또는 Elasticsearch로 흘려서 정산팀과 CS팀이 자유 검색할 수 있게 한다.

CS 복구 시나리오는 미리 메뉴화한다. "결제 취소 후 쿠폰 자동복구 실패", "포인트 차감되었는데 주문 누락", "선착순 이벤트 정원 초과 발급" 같은 빈발 케이스는 CS 어드민에 전용 버튼을 만들어서 사람이 SQL 치지 않게 한다. 어드민 행동 하나하나가 감사 로그에 들어가야 한다.

## 로컬 실습 환경

```yaml
# docker-compose.yml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: promo
    ports: ["3306:3306"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  rabbitmq:
    image: rabbitmq:3-management
    ports: ["5672:5672", "15672:15672"]
```

테이블 스키마 일부.

```sql
CREATE TABLE coupon_template (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  name          VARCHAR(100) NOT NULL,
  scope         VARCHAR(20)  NOT NULL,
  discount_type VARCHAR(20)  NOT NULL,
  discount_value INT         NOT NULL,
  min_order_amount INT       NOT NULL DEFAULT 0,
  total_stock   INT          NULL,
  per_user_limit INT         NOT NULL DEFAULT 1,
  starts_at     DATETIME(6)  NOT NULL,
  ends_at       DATETIME(6)  NOT NULL
) ENGINE=InnoDB;

CREATE TABLE coupon_issue (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  template_id BIGINT NOT NULL,
  user_id     BIGINT NOT NULL,
  status      VARCHAR(20) NOT NULL,
  order_id    BIGINT NULL,
  issued_at   DATETIME(6) NOT NULL,
  used_at     DATETIME(6) NULL,
  expire_at   DATETIME(6) NOT NULL,
  UNIQUE KEY uq_template_user (template_id, user_id),
  KEY idx_user_status (user_id, status, expire_at)
) ENGINE=InnoDB;

CREATE TABLE coupon_use_log (
  order_id        BIGINT NOT NULL,
  coupon_issue_id BIGINT NOT NULL,
  applied_amount  INT NOT NULL,
  created_at      DATETIME(6) NOT NULL,
  PRIMARY KEY (order_id, coupon_issue_id)
) ENGINE=InnoDB;
```

## 실행 가능한 예제 — 선착순 발급 컨트롤러

```java
@PostMapping("/events/{eventId}/coupons")
public CouponIssueResponse claim(@PathVariable Long eventId,
                                 @AuthenticationPrincipal User user) {
    String stockKey = "event:" + eventId + ":stock";
    String userKey  = "event:" + eventId + ":user:" + user.getId();

    Boolean firstClaim = redis.opsForValue()
        .setIfAbsent(userKey, "1", Duration.ofDays(1));
    if (Boolean.FALSE.equals(firstClaim)) {
        throw new AlreadyClaimedException();
    }

    Long remaining = redis.opsForValue().decrement(stockKey);
    if (remaining == null || remaining < 0) {
        redis.delete(userKey);
        throw new SoldOutException();
    }

    rabbit.convertAndSend("coupon.issue",
        new IssueMessage(eventId, user.getId(), UUID.randomUUID()));
    return CouponIssueResponse.queued();
}
```

컨슈머는 `IssueMessage`를 받아 `coupon_issue`에 `INSERT IGNORE`(또는 `ON DUPLICATE KEY UPDATE`)로 멱등 발급한다.

## 핵심 설계 질문과 정리

> Q. 선착순 1만장 쿠폰 이벤트는 어떻게 설계하는가

재고 차감과 영구 발급을 분리한다. 재고는 Redis `DECR`로 원자 차감해서 1만 장이라는 게이트만 통과시키고, 실제 발급은 RabbitMQ로 비동기로 흘려서 RDBMS에 `coupon_issue`로 저장한다. 1인 1매 제약은 Redis `SET NX`와 DB UNIQUE 키 두 군데에 둬서, Redis가 휘발되어도 DB가 막아주게 한다. 캐시와 DB 정합성 문제는 Redis는 게이트키퍼고 진실의 원천은 DB라는 원칙으로 푼다.

> Q. 결제 취소 시 쿠폰 복구는 어떻게 처리하는가

단순 상태 토글이 아니라 정책 분기다. 만료된 쿠폰은 그대로 살리지 않고 별도 보상 정책을 태우고, 만료 전이라면 `RESTORED`가 아닌 `ISSUED`로 되돌린다. 모든 복구는 `coupon_audit_log`에 actor와 reason과 함께 남겨서 CS와 정산이 추적할 수 있게 한다. 결제 시스템과 쿠폰 시스템 사이는 분산 트랜잭션 대신 결제 이벤트를 Kafka로 흘리고, 컨슈머에서 멱등키 기반으로 복구를 적용한다.

> Q. 포인트 잔액 조회가 매우 잦은데 어떻게 받쳐주는가

잔액은 `point_transaction`의 합이 진실이지만, 매 조회마다 합산하면 비싸다. `point_balance` 캐시 테이블 + Redis 캐시 두 단을 두고, 읽기는 StampedLock의 `tryOptimisticRead`로 락 없이 받는다. 쓰기 시점에만 `writeLock`으로 캐시를 무효화하고 Redis도 expire한다. 캐시가 어긋나면 야간 배치가 트랜잭션 합계로 재계산해서 보정한다.

> Q. 쿠폰 적용 우선순위는 어떻게 정하는가

메뉴 단위 → 카테고리 → 주문 총액 → 멤버십 등급 → 포인트 → 결제수단 순으로 고정한다. 같은 레벨에서 여러 장이 있으면 `priority` 필드로 결정하고, 중복 가능 여부는 `stackable_with` 그룹으로 제어한다. 결제 화면에서 미리보는 할인 금액과 결제 시점 최종 할인 금액이 달라지면 사고로 이어지니, 견적 계산기와 적용 계산기는 같은 정책 엔진을 호출하도록 일원화한다.

## 체크리스트

- [ ] `coupon_issue.status`는 `RESERVED`를 포함한 5상태 머신인가
- [ ] 쿠폰 사용은 조건부 UPDATE(CAS)인가, SELECT-then-UPDATE가 아닌가
- [ ] `coupon_use_log`에 `(order_id, coupon_issue_id)` UNIQUE가 있는가
- [ ] 선착순 재고 차감은 Redis 원자 명령으로 분리되어 있는가
- [ ] 발급 메시지 큐는 publisher confirm + at-least-once인가, 컨슈머는 멱등인가
- [ ] 1인 1매 제약이 Redis와 DB 양쪽에 모두 걸려 있는가
- [ ] 환불·복구가 만료 여부와 CS 정책에 따라 분기되는가
- [ ] 모든 상태 변경이 감사 로그에 actor와 reason까지 남는가
- [ ] 포인트는 `point_transaction` 단일 진실원 + 잔액 캐시 구조인가
- [ ] 포인트 차감에 `(order_id, type)` UNIQUE 멱등키가 걸려 있는가
- [ ] 견적 계산기와 적용 계산기가 같은 정책 엔진을 호출하는가
- [ ] CS 어드민이 직접 SQL을 치지 않도록 정형 복구 메뉴가 있는가
- [ ] 정합성 보정 배치가 야간에 잔액·쿠폰 상태를 재계산하는가
