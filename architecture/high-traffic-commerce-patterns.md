# [초안] 대규모 커머스 트래픽 처리 패턴 — 1,600만 고객과 올영세일을 버티는 설계

## 1. 이 주제가 왜 중요한가

대규모 커머스 백엔드는 평상시와 이벤트 시점의 트래픽 프로파일이 극단적으로 다르다. CJ 올리브영의 경우 멤버십 회원 규모가 1,600만 명을 넘고, 한 해에 수 차례 진행되는 **올영세일**과 같은 메가 프로모션에서는 상시 TPS의 5~10배가 수십 분 안에 몰린다. 이 조건에서 단순히 서버를 늘리는 것으로는 해결되지 않는다. 트래픽이 집중되는 자원(인기 상품 상세, 재고 차감 로직, 쿠폰 발급 API, 결제 초입)이 반드시 존재하고, 이 **hot path**가 시스템 전체를 끌고 들어간다.

시니어 백엔드 엔지니어에게 요구되는 역량은 명확하다. "장애가 났다"가 아니라 "이 구간은 이래서 쏠리고, 이래서 버티거나 버티지 못했으며, 이 설계로 바꾸면 이렇게 완화된다"를 설명할 수 있어야 한다. 이 문서는 커머스 도메인에 한정해 재고·쿠폰·타임세일·읽기·쓰기·핫키·장애 격리를 하나의 흐름으로 엮는 실전 플레이북을 만든다.

본인이 과거 슬롯팀에서 RCC(Real-time Campaign Cache) 사전 캐시와 JMH 기반 성능 의사결정, Kafka Outbox 패턴을 실무에서 다뤘던 경험은 이 토픽과 정확히 연결된다. 면접에서 "블랙프라이데이에 주문이 10배 들어옵니다. 어디부터 보시겠어요?"라는 질문을 받으면, 아래 구조대로 답해 나가면 된다.

## 2. 커머스 트래픽 프로파일의 세 가지 축

커머스 트래픽은 하나의 커브가 아니다. 세 가지 성질이 겹쳐 있다.

**① 상시 read-heavy.** 일반 시간대에도 상품 상세·목록·검색 조회 트래픽이 쓰기 대비 50~200배다. 전시 상품 ID 기준으로 캐시 적중률이 성패를 가른다.

**② 프로모션 spike.** 올영세일이 열리는 순간 +5~10배 증가가 수 초 내에 일어난다. 이 스파이크는 등속이 아니라 **시작 시각 ±30초**에 날카로운 에지가 생긴다. 예열이 되어 있지 않으면 JVM JIT도, DB 커넥션 풀도, 캐시도 동시에 미준비 상태에서 맞는다.

**③ Hot key.** 세일 기간의 TOP 20 상품이 전체 상품 상세 조회의 30~50%를 먹는다. 이 20개 키가 캐시 노드, DB 파티션, Redis 샤드에 고르게 분산되지 않으면 **특정 노드 한 장**이 병목이 된다. 커머스에서 "평균 레이턴시는 괜찮은데 p99가 튄다"의 90%는 핫키다.

세 가지는 각각 다른 대응이 필요하다. 상시 read-heavy는 캐시 계층 설계, spike는 대기열·자동 스케일·사전 워밍, hot key는 2-tier cache와 키 분할로 푼다. 한 가지 기술로 다 풀려 들면 반드시 구멍이 난다.

## 3. 재고 차감 동시성 — 같은 상품을 100명이 동시에 집는다

재고 차감은 커머스에서 가장 자주 면접 질문으로 나오는 동시성 문제다. 네 가지 전형적 해법을 비교한다.

### 3-1. DB row lock (비관적 락)

```sql
START TRANSACTION;
SELECT stock FROM product_stock WHERE product_id = 9001 FOR UPDATE;
-- 애플리케이션에서 재고 > 요청수량 검증
UPDATE product_stock SET stock = stock - 1 WHERE product_id = 9001;
COMMIT;
```

가장 단순하고 정확하다. 하지만 `FOR UPDATE`가 같은 행에 직렬화되므로 TPS가 **단일 행의 락 대기 시간**으로 캡된다. 평균 락 보유 시간이 5ms라면 이론 최대 TPS는 200이다. 인기 상품 하나에 1만 명이 몰리면 대기열이 DB 커넥션을 다 잠그고 다른 요청까지 연쇄 지연된다.

### 3-2. 조건부 UPDATE (낙관적)

```sql
UPDATE product_stock
SET stock = stock - 1
WHERE product_id = 9001 AND stock >= 1;
```

`affected rows = 0`이면 재고 없음이다. 락 없이 원자적 차감이 가능하고, MySQL InnoDB가 row-level 락을 짧게 잡았다 놓는다. 그래도 인기 상품은 여전히 해당 행에 직렬화된다. 차이는 "락을 애플리케이션이 오래 쥐지 않는다"는 점이다. 실무에서는 이 방식이 비관적 락보다 거의 항상 더 빠르다.

### 3-3. Redis DECR 기반 차감

```lua
-- KEYS[1] = stock:product:9001, ARGV[1] = 차감수량
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current < tonumber(ARGV[1]) then
  return -1
end
return redis.call('DECRBY', KEYS[1], ARGV[1])
```

Redis는 싱글 스레드라 Lua 스크립트 단위로 원자적이다. 단일 키 기준 수만 TPS가 나온다. DB는 "최종 일관성" 경로로 빠진다(이벤트 큐로 반영). 주의할 점은 **Redis가 소스 오브 트루스가 되는 순간 장애 시 데이터 손실 위험**이 생긴다는 것이다. AOF fsync everysec + Sentinel/Cluster 구성과, DB로의 비동기 체크포인트(정합성 복구용)는 반드시 필요하다.

### 3-4. 큐잉 (선착순 기반)

```
Client → API Gateway → Kafka(order-request) → Consumer(순차 처리) → DB/Redis
```

요청을 받자마자 큐로 넘기고 즉시 "대기 중" 응답을 돌려준다. Consumer는 파티션 단위로 순차 처리하므로 동시성이 자연스럽게 조절된다. 트레이드오프는 **실시간성 포기**다. 사용자는 "주문 접수 완료"가 아니라 "대기번호 N번"을 본다. 플래시 세일·한정판·드롭에 적합하다.

### 비교 요약

| 방식 | 정합성 | 최대 TPS(단일 키) | 구현 복잡도 | 언제 쓰나 |
|------|--------|-------------------|-------------|-----------|
| FOR UPDATE | 강함 | 낮음 | 낮음 | 평상시 낮은 동시성 |
| 조건부 UPDATE | 강함 | 중간 | 낮음 | 중간 트래픽 기본값 |
| Redis DECR | 중간 | 매우 높음 | 중간 | 프로모션·이벤트 |
| 큐잉 | 강함(지연된) | 매우 높음 | 높음 | 플래시 세일·한정판 |

면접에서 "재고 동시성 어떻게 할까요"는 답이 하나가 아니라 **상품 성격에 따른 선택**이라고 말해야 정답에 가깝다.

## 4. 타임세일·플래시 세일 — 시작 시각 ±초 구간 전투

19시 정각 시작 세일은 18:59:58~19:00:03 구간에 트래픽이 완전히 수렴한다. 이 구간은 오토스케일링이 따라오지 못한다. 따라서 **사전 예열**과 **입장 대기열**이 정답이다.

### 4-1. 사전 예열 (warming)

이벤트 시작 T-10분에:
- 세일 대상 상품 ID를 캐시에 미리 로드한다(`products:sale:20260418_19`).
- Redis 재고 키를 DB에서 복사해 둔다.
- JVM에 대한 synthetic 요청을 넣어 JIT을 활성화하고 커넥션 풀을 덥힌다.
- CDN에 상세 페이지 정적 리소스를 푸시한다.

슬롯팀 RCC 사전 캐시 경험을 그대로 가져올 수 있다. 캠페인 시작 전 핵심 키를 미리 채워두면, 시작 직후 cache miss → DB 몰림이 사라진다.

### 4-2. 가상 대기열 (virtual queue)

```
Client ──(GET /waiting-room)──> Edge
         <─ {token: "xyz", position: 14820, polling_interval: 3s} ─

Edge(Redis ZSET, score=enter_time)
  └─ 매초 N명씩 score를 "passed"로 이동
      └─ Passed 클라이언트만 실제 API 호출 가능
```

`ZADD waiting:saleA <ts> <userId>` 로 입장 시각 순서를 기록하고, 초당 N명씩 `ZPOPMIN` 해 통과시킨다. 통과 토큰(JWT나 Redis key)이 있는 요청만 실제 주문 API로 라우팅한다. 나머지는 Edge에서 끊어낸다. **실제 오리진 TPS는 N으로 고정**되므로 뒤쪽 시스템이 숨을 쉰다.

### 4-3. Token bucket

가상 대기열이 없어도 되는 규모라면 초당 rate를 제한하는 token bucket을 Edge에 둔다. Redis 단일 키로 구현하는 가장 단순한 형태:

```lua
local key = KEYS[1]
local now, rate, capacity = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1]) or capacity
local ts = tonumber(data[2]) or now
local delta = math.max(0, now - ts) * rate
tokens = math.min(capacity, tokens + delta)
if tokens < 1 then return 0 end
redis.call('HMSET', key, 'tokens', tokens - 1, 'ts', now)
redis.call('EXPIRE', key, 60)
return 1
```

유저별·상품별·IP별 조합으로 버킷을 분리할 수 있다.

## 5. 쿠폰 동시 발급·사용 — 1인 1매 + 수량 제한

쿠폰은 재고와 비슷하지만 **유저별 제약**이 추가된다. 두 가지 원자 연산이 필요하다. "총 발급량 차감"과 "해당 유저의 중복 수령 방지".

### 5-1. 분산 락 + 멱등성 키

```java
String lockKey = "coupon:lock:" + couponId + ":" + userId;
String idempotencyKey = request.getHeader("Idempotency-Key");

// SET NX PX 로 락 획득
Boolean ok = redis.setIfAbsent(lockKey, idempotencyKey, Duration.ofSeconds(3));
if (!Boolean.TRUE.equals(ok)) {
    throw new DuplicateRequestException();
}
try {
    // 1) 이미 발급받았는가 (SETNX + 멤버십)
    Boolean firstIssue = redis.opsForSet().add("coupon:issued:" + couponId, String.valueOf(userId)) == 1L;
    if (!firstIssue) return AlreadyIssued();

    // 2) 총 수량 원자 차감
    Long remain = redis.opsForValue().decrement("coupon:remaining:" + couponId);
    if (remain == null || remain < 0) {
        redis.opsForSet().remove("coupon:issued:" + couponId, String.valueOf(userId));
        return SoldOut();
    }

    // 3) 비동기 영속화 (Outbox → Kafka → DB)
    outbox.enqueueCouponIssued(couponId, userId, idempotencyKey);
    return Ok();
} finally {
    // 내가 건 락만 해제 (값 비교)
    releaseLock(lockKey, idempotencyKey);
}
```

포인트 세 가지다.
- **멱등성 키**를 락 값으로 사용해 같은 요청의 재시도를 구분한다.
- **SET 멤버십**(`SADD`)으로 "이 유저가 받은 적 있는가"를 O(1)에 검증한다.
- 실제 DB insert는 Kafka Outbox로 위임해 응답 시간을 짧게 유지한다.

Outbox 패턴은 트랜잭션 내에서 이벤트 row를 만들고 별도 프로세스가 Kafka로 publish하는 방식이다. 본인이 Kafka Outbox를 쓴 경험에서 얻는 가장 큰 이득은 **분산 트랜잭션 없이 at-least-once 보장**이 된다는 점이다. Consumer는 `idempotency_key` UNIQUE 제약으로 중복을 흡수한다.

## 6. Read storm 방지 — 캐시의 세 가지 심화 패턴

### 6-1. Cache-Aside + Negative caching

조회 트래픽은 기본적으로 cache-aside(lazy loading)를 쓴다.

```java
public Product find(long id) {
    String key = "product:" + id;
    Product cached = redis.get(key, Product.class);
    if (cached != null) return cached == NULL_MARKER ? null : cached;

    Product db = productRepository.findById(id).orElse(null);
    redis.set(key, db == null ? NULL_MARKER : db, ttlWithJitter(Duration.ofMinutes(10)));
    return db;
}
```

**Negative caching**이 중요하다. 존재하지 않는 상품 ID로 스캔형 공격이 오면, null 응답도 짧게라도 캐시해야 DB가 보호된다. TTL은 짧게(30~60초) 둔다.

### 6-2. Request coalescing (single-flight)

같은 키에 대해 동시 cache miss가 100개 발생하면 DB로 100번 가선 안 된다. 하나의 요청만 DB에 가고 나머지는 그 결과를 공유한다.

```java
ConcurrentMap<String, CompletableFuture<Product>> inflight = new ConcurrentHashMap<>();

public Product find(long id) {
    String key = "product:" + id;
    Product cached = redis.get(key, Product.class);
    if (cached != null) return cached;

    CompletableFuture<Product> future = inflight.computeIfAbsent(key, k ->
        CompletableFuture.supplyAsync(() -> loadFromDbAndCache(id))
                         .whenComplete((v, e) -> inflight.remove(k))
    );
    return future.join();
}
```

프로세스 내 single-flight는 JVM 단위에서 한 번, Redis 분산 락을 얹으면 클러스터 전역에서 한 번만 DB를 친다. 비용과 단순성의 균형을 보고 결정한다.

### 6-3. Stale-while-revalidate

캐시 만료 직전 또는 직후에 "낡은 값 반환 + 백그라운드 재계산"을 한다.

```java
CacheEntry e = redis.getEntry(key);
if (e != null && e.isFresh()) return e.value;
if (e != null && e.isStaleButUsable()) {
    refreshAsync(key);     // 백그라운드로 갱신
    return e.value;        // 낡았지만 반환
}
return loadAndCache(key);
```

상품 상세처럼 1~2분 낡아도 치명적이지 않은 데이터에 적합하다. 재고·가격은 예외다.

## 7. Thundering herd / Cache stampede 방지

핫키의 TTL이 동시에 만료되면 다음 1초에 DB로 수천 요청이 몰린다.

**① TTL jitter.** 모든 키에 같은 10분이 아니라 `10분 ± 30초` 분포를 준다. 올리브영 테크 블로그에서도 jitter 적용 시 40% 수준의 피크 리소스 감소 사례가 공유됐다. 원리는 단순하다. 만료 시각을 흩뿌리면 미스 이벤트가 시간축에서 평탄화된다.

**② Probabilistic early expiration (XFetch).** 만료 시각이 가까울수록 확률적으로 "내가 지금 갱신할게"를 결정한다.

```java
double xfetch = Math.log(ThreadLocalRandom.current().nextDouble()) * beta * computeTimeMs;
if (System.currentTimeMillis() - xfetch >= expireAt) {
    refreshAsync(key);
}
```

`beta`가 클수록 더 일찍 갱신된다. 한 프로세스만 확률적으로 먼저 뽑히므로 동시 갱신을 줄인다.

**③ Lock + single-flight.** 앞서 다룬 request coalescing을 Redis 분산 락으로 올리면 클러스터 전역 stampede까지 막는다.

## 8. Hot key 완화 — 핵심은 "한 노드에 몰리지 않게"

### 8-1. 2-tier cache (Caffeine + Redis)

```
App JVM (Caffeine, TTL 10s) → Redis (TTL 10m) → DB
```

상위 계층에 로컬 캐시를 두면 hot key에 대한 Redis 요청도 줄어든다. JVM 인스턴스 수만큼 fan-out이 자연 분산된다. 주의할 점은 **정합성**이다. 가격·재고처럼 최신성이 중요한 데이터는 짧은 TTL(수 초)과 이벤트 기반 invalidation(Kafka)으로 보완한다.

### 8-2. Key 분할 (suffix sharding)

카운터·랭킹처럼 단일 키로 쏠리는 경우 `"viewcount:9001:{0..15}"` 처럼 16개로 쪼갠다. 쓰기는 `hash(userId) % 16`, 읽기는 16개 합산. 단일 샤드 핫스팟을 16분의 1로 낮춘다.

### 8-3. Read replica 분산

Redis Cluster에서 `READONLY` 모드로 replica에서 읽는다. MySQL도 조회 전용 replica를 두고, 핫 상품 읽기는 replica로 라우팅한다. **일관성 이슈**(lag)가 허용되는 경로에서만 쓴다.

## 9. Write storm 완화 — 쓰기를 직접 맞지 말기

주문·장바구니·조회수 같은 쓰기는 **batching + async**로 완화한다.

**Write-behind.** 조회수는 실시간 DB 반영이 필요없다. Redis에 INCR → 30초마다 배치로 DB flush.

**비동기 위임.** 주문 성사 이후 파생 작업(쿠폰 차감, 포인트 적립, 알림톡 발송, 추천 갱신)은 Kafka 토픽으로 넘긴다. 주문 API는 DB에 한 번만 쓰고 이벤트 하나만 publish한다.

```
POST /orders → INSERT order + outbox(ORDER_CREATED) → 200 OK
              └─ outbox relay → Kafka(order.created)
                                   ├── coupon-consumer
                                   ├── point-consumer
                                   ├── alimtalk-consumer
                                   └── recommender-consumer
```

**Outbox**를 끼우면 DB 트랜잭션과 이벤트 publish가 같은 트랜잭션에서 원자적으로 묶인다. publish 실패 시 재시도는 relay가 담당한다.

## 10. 알림톡·푸시 폭주

쿠폰 발급 완료·주문 완료 알림은 수십만 건이 한 번에 쏠린다. 동기 호출로 외부 알림톡 API를 찌르면 그 API가 throttle을 걸고, 우리 스레드 풀이 전부 blocked 된다.

- Kafka 토픽으로 분리, 소비자가 초당 N건으로 rate limit.
- Circuit breaker(Resilience4j)로 외부 API 실패율이 임계치를 넘으면 열고 fallback(일단 DB에만 기록, 나중에 재시도).
- Bulkhead로 알림 전송 스레드 풀을 주문 스레드 풀과 분리. 알림이 막혀도 주문은 산다.

## 11. 장애 격리 — bulkhead · feature flag · degraded mode

### Bulkhead

서비스별 스레드 풀/커넥션 풀을 분리한다. 추천 API가 느려지면 추천용 풀만 고갈되고, 상품 상세는 영향을 받지 않는다. Hystrix는 deprecated이고 Resilience4j의 `Bulkhead` 모듈을 쓴다.

### Feature flag

신규 기능을 배포는 해두되 플래그로 꺼둔다. 트래픽 피크 직전에 켰다가, 문제가 보이면 즉시 끈다. 배포 롤백보다 훨씬 빠르다. 내부 `configuration service` 또는 Unleash·LaunchDarkly 같은 도구.

### Degraded mode

전체 다 죽이지 않는 부분 실패 설계. 예:
- 추천 영역 장애 시 "오늘의 MD 추천" 정적 목록 노출.
- 리뷰 서비스 장애 시 리뷰 탭 "잠시 후 다시 시도" 배너.
- 가격 계산 장애 시 정가만 노출하고 장바구니 진입 차단.

완전 장애보다 **부분 기능만 죽이는** 것이 매출 손실을 최소화한다.

## 12. 로컬 실습 환경

docker-compose.yml 예시:

```yaml
version: "3.8"
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: commerce
    ports: ["3306:3306"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  kafka:
    image: bitnami/kafka:3.6
    environment:
      - KAFKA_ENABLE_KRAFT=yes
      - KAFKA_CFG_NODE_ID=1
      - KAFKA_CFG_PROCESS_ROLES=broker,controller
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@localhost:9093
    ports: ["9092:9092"]
```

재고 테이블(MySQL 8):

```sql
CREATE TABLE product_stock (
  product_id BIGINT PRIMARY KEY,
  stock      INT NOT NULL,
  version    INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

INSERT INTO product_stock(product_id, stock) VALUES (9001, 100);
```

## 13. 실행 가능한 부하 테스트

k6로 재고 차감에 500 VU로 10초간 찌른다.

```javascript
import http from 'k6/http';
import { check } from 'k6';
export const options = { vus: 500, duration: '10s' };
export default function () {
  const res = http.post('http://localhost:8080/orders',
    JSON.stringify({ productId: 9001, qty: 1 }),
    { headers: { 'Content-Type': 'application/json',
                 'Idempotency-Key': `${__VU}-${__ITER}` } });
  check(res, { '200 or sold_out': r => [200, 409].includes(r.status) });
}
```

DB 조건부 UPDATE 방식, Redis DECR 방식, 큐잉 방식 세 가지를 동일 스크립트로 비교한다. p50·p95·p99 레이턴시와 성공률을 기록하면 **왜 이 방식을 골랐는가**가 데이터로 남는다. JMH는 메서드 수준 마이크로벤치용이고, 종단 처리량은 k6·Gatling 쪽이 맞다. 슬롯팀에서 JMH로 의사결정한 경험은 **단위 병목 확인에 유효**하고, 시스템 처리량은 따로 잡아야 한다는 경계 감각과 연결된다.

## 14. 면접 답변 프레이밍 — "블프에 10배 들어옵니다, 어디부터 보시겠어요?"

대답 템플릿:

1) **트래픽 프로파일 먼저 나눈다.** "저는 먼저 그 10배가 읽기인지 쓰기인지, 스파이크인지 분산된 증가인지 확인하겠습니다. 커머스는 보통 read가 5~10배, write가 2~3배, hot key 한두 개가 30% 이상을 먹는 구조라서 대응이 다릅니다."

2) **읽기부터 막는다.** "Edge의 CDN·API Gateway 캐시 설정을 확인하고, 상품 상세는 Redis + 로컬 Caffeine 2-tier로 방어합니다. 핫키는 TTL jitter와 stale-while-revalidate로 DB stampede를 차단합니다."

3) **쓰기는 비동기 위임.** "주문 자체만 DB에 찍고, 쿠폰·포인트·알림은 Kafka outbox로 분리합니다. 알림톡 API 같은 외부 의존은 circuit breaker와 bulkhead로 격리합니다."

4) **재고는 상품 성격으로 결정.** "일반 상품은 조건부 UPDATE, 한정판·드롭은 Redis DECR 또는 큐잉을 씁니다. 둘 다 idempotency key로 재시도를 흡수합니다."

5) **관측과 킬 스위치.** "TPS·p99·에러율·cache hit rate·DB active connections을 대시보드에 띄우고, feature flag로 부하가 큰 기능(실시간 추천, 리뷰 집계)을 즉시 끌 수 있게 합니다."

6) **degraded mode 언급.** "완전히 죽이지 않는 부분 실패를 미리 설계합니다. 추천이 죽으면 정적 MD pick으로 대체하는 식이에요."

이렇게 1~6을 흐름으로 말하면, 면접관이 **깊이 찌를 수 있는 고리**를 준다. "그럼 Redis DECR 쓰면 소스 오브 트루스가 Redis가 되는데요?", "jitter로 40% 감소 사례는 왜 그런 수치인가요?" 같은 질문이 들어온다. 답은 이 문서 본문이다.

## 15. 흔한 실수 패턴

- **전역 TTL 고정.** 같은 TTL이 동시에 만료 → stampede. 반드시 jitter.
- **로컬 캐시 invalidation 누락.** Caffeine 갱신이 Kafka 이벤트에 연결되지 않아 10초간 낡은 가격을 보여준다.
- **Idempotency key 없이 재시도.** 쿠폰이 두 번 발급된다.
- **분산 락을 TTL 없이 건다.** 프로세스 크래시 시 영원히 락이 남는다.
- **Outbox relay 단일 장애.** relay가 죽으면 이벤트가 쌓이기만 한다. HA 구성 필수.
- **서킷 브레이커 없는 동기 호출.** 외부 알림 API 지연이 주문 API까지 삼킨다.
- **읽기 replica 지연 무시.** 주문 직후 "주문 내역" 조회에서 빈 응답이 나온다. 쓰기 직후 조회는 primary로.
- **hot key를 모니터링하지 않음.** Redis `--hotkeys`, `CLIENT LIST`, slowlog, 그리고 애플리케이션 레벨 top-N 카운터 모두 필요.

## 16. 체크리스트

- [ ] 상시/프로모션/핫키 세 가지 트래픽 프로파일로 구간별 대응을 분리했는가
- [ ] 재고 차감은 상품 성격(일반/한정판/드롭)에 따라 다른 전략을 매핑했는가
- [ ] 타임세일 시작 T-10분 워밍 스크립트가 준비돼 있는가
- [ ] 가상 대기열 또는 token bucket으로 Edge에서 오리진을 보호하는가
- [ ] 쿠폰 발급에 idempotency key + 분산 락 + SADD 멤버십 체크가 있는가
- [ ] 모든 캐시 TTL에 jitter가 적용돼 있는가
- [ ] request coalescing 또는 single-flight가 핫 키 경로에 들어가 있는가
- [ ] Caffeine + Redis 2-tier 구조와 이벤트 기반 invalidation이 연결돼 있는가
- [ ] Write path에 Outbox + Kafka가 있고 consumer는 idempotent한가
- [ ] 외부 의존(알림톡·PG)에 circuit breaker와 bulkhead가 있는가
- [ ] Feature flag로 실시간 기능을 끌 수 있는가
- [ ] Degraded mode UI가 각 서비스 장애 시 정의돼 있는가
- [ ] p50·p95·p99, cache hit rate, DB conn, queue lag 대시보드가 준비됐는가
- [ ] k6 부하 테스트로 세 가지 재고 전략을 실측 비교한 데이터가 있는가
- [ ] "블프 10배" 질문에 6단계 프레이밍으로 4분 안에 설명할 수 있는가
