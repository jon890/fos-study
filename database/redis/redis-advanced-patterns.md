# [초안] Redis Advanced Patterns — 백엔드 실무에서 자주 마주치는 고급 패턴 정리

## 왜 이 주제가 중요한가

Redis를 "그냥 빠른 key-value 캐시"로만 쓰다 보면, 트래픽이 늘었을 때 오히려 Redis가 장애의 진원지가 된다. 실무에서 흔히 겪는 상황은 이런 식이다.

- 캐시를 걷어냈더니 DB가 죽는다 (cache stampede).
- 캐시 TTL이 모두 동시에 만료돼 순간 QPS가 튄다 (thundering herd).
- 분산락을 Redis로 걸었는데 타임아웃 상황에서 두 프로세스가 동시에 임계 구역에 들어간다.
- `KEYS *` 한 번으로 Redis 전체가 멈춘다.
- Redis Cluster로 옮겼더니 기존 `MULTI/EXEC` 파이프라인이 `CROSSSLOT` 에러로 깨진다.

시니어 백엔드 면접에서 Redis 질문은 단순 자료구조(String/Hash/List/Set/ZSet)를 묻는 수준을 넘어선다. "트래픽이 10배로 튀었을 때 이 캐시 전략으로 버틸 수 있는가", "이 분산락 구현은 정확히 어디서 깨지는가" 같은 실패 시나리오 중심 질문이 나온다. 이 문서는 그 수준에 맞춘 실전 패턴을 정리한다.

Redis의 기본 자료구조와 영속화(RDB/AOF), 복제/클러스터 개요는 별도의 기초 문서에서 다룬 것으로 간주하고, 여기서는 **캐시 전략**, **분산락**, **atomic 연산과 Lua**, **Pub/Sub vs Streams**, **Cluster 제약**, **실무에서의 hot key / big key 문제**에 집중한다.

## 캐시 읽기/쓰기 패턴 — 선택의 기준

### 1. Cache-Aside (Lazy Loading)

가장 흔하게 쓰는 패턴이다.

```
read:
  v = redis.get(key)
  if v is None:
      v = db.select(...)
      redis.setex(key, ttl, v)
  return v

write:
  db.update(...)
  redis.delete(key)   // not set
```

쓰기 경로에서 **set이 아니라 delete**를 하는 이유는 두 가지다.

1. 쓰기 직후의 stale write race: `T1: db.update(old->new)` → `T2: db.update(new->final)` → `T2: redis.set(final)` → `T1: redis.set(new)` 이면 캐시에 오래된 값이 남는다. delete는 이 race를 줄인다.
2. write-through 비용 회피: 읽히지 않을 데이터도 매 쓰기마다 캐시에 올리면 메모리 낭비가 크다.

### 2. Read-Through / Write-Through

애플리케이션이 아니라 캐시 레이어(또는 라이브러리)가 DB를 직접 읽고 쓴다. 스펙이 단순해지는 대신 캐시 장애가 곧 읽기/쓰기 장애가 된다. JPA 2차 캐시나 Spring `@Cacheable`이 이쪽에 가깝다.

### 3. Write-Behind (Write-Back)

쓰기는 캐시에만 하고, 배치로 DB에 flush한다. Throughput은 최고지만 Redis가 죽으면 데이터 유실이다. 카운터/집계처럼 "정확한 값은 중요하지 않지만 빠른 증가가 중요한" 경우 외에는 일반 도메인 데이터에 쓰지 않는다.

### 4. Refresh-Ahead

TTL이 끝나기 전에 미리 비동기로 갱신한다. Hot key가 만료되는 순간 DB로 쏠리는 걸 막는다. 아래 stampede 대응에서 다시 다룬다.

선택 기준은 단순하다. **정합성이 중요한가, 속도가 중요한가, 트래픽이 튀는가**. 일반적인 상품 조회, 유저 프로필 같은 도메인은 Cache-Aside + delete on write가 기본이다.

## Cache Stampede (Thundering Herd) 대응

인기 있는 키 하나의 TTL이 끝나는 순간, 동시에 수백 개 요청이 캐시 miss → 같은 DB 쿼리를 치는 현상이다. 대응 방법은 크게 세 가지다.

### (1) 분산락으로 단일 재계산 보장

```
v = redis.get(key)
if v is not None:
    return v

lock_key = "lock:" + key
if redis.set(lock_key, token, nx=True, ex=5):
    try:
        v = db.select(...)
        redis.setex(key, ttl, v)
    finally:
        // 반드시 Lua로 token 일치 검증 후 DEL
        release_lock(lock_key, token)
    return v
else:
    sleep(50ms)
    return redis.get(key) or db.select(...)
```

대기 측은 짧게 sleep 후 캐시를 재조회한다. "락을 못 잡은 쪽이 그냥 DB를 치게" 두면 정작 보호하려던 DB가 또 맞는다.

### (2) Probabilistic Early Expiration (XFetch)

TTL이 끝나기 전에 확률적으로 **한 요청만** 재계산하게 만든다. Redis에 값과 함께 `computed_at`, `delta`(재계산 소요시간)를 저장하고, 다음 조건에서 재계산한다.

```
now - delta * beta * ln(rand()) >= expiry
```

`beta`는 보통 1.0. 수학적으로 TTL 끝 직전에 재계산될 확률이 급격히 높아지고, 그 사이의 나머지 요청은 아직 살아있는 캐시를 그대로 본다. DB가 감당 가능한 수준으로 stampede가 분산된다.

### (3) TTL 지터(jitter)

비슷한 시점에 생성된 키가 정확히 같은 시각에 만료되면 동시에 튄다. `ttl = base + rand(0, jitter)`로 분산시킨다. 배치로 warm-up 한 캐시일수록 지터가 필수다.

## 분산락 — Redis로 정말 mutual exclusion이 되는가

기본 구현은 `SET key token NX PX 30000`. 문제는 해제 시점이다. 반드시 **Lua 스크립트로 token을 검증한 뒤 DEL** 해야 한다.

```lua
-- release.lua
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

아래는 흔한 실패 시나리오다.

1. T1이 락을 잡고 GC로 멈춘다 (또는 네트워크가 끊긴다).
2. 락 TTL이 만료되고 T2가 새 락을 잡는다.
3. T1이 깨어나서 `DEL lock_key` 를 하면 **T2의 락을 지운다**.
4. T3가 또 락을 잡는다 → 임계 구역 중복 진입.

token 검증 Lua는 이 중 3단계를 막아준다. 하지만 **2단계 자체**(T1과 T2가 잠깐 동시에 락을 소유한다고 "믿는" 상태)는 Redis만으로는 원천 차단할 수 없다. Redlock 알고리즘도 Martin Kleppmann이 지적한 대로, GC stall이나 clock drift 상황에서 완전한 mutual exclusion을 보장하지는 못한다.

실무에서의 현실적인 결론은 이렇다.

- **돈이 걸린 연산에는 Redis 락을 최종 방어선으로 쓰지 않는다**. DB 유니크 제약, `SELECT ... FOR UPDATE`, fencing token 같은 추가 방어를 둔다.
- Redis 락은 **중복 실행을 줄이기 위한 최선 노력(best-effort)** 수단으로 쓴다. 캐시 재계산 dedupe, 스케줄러 leader election, 외부 API 호출 dedupe 정도가 적합하다.
- 락 TTL은 **작업 예상 시간보다 충분히 길게** 두되, 장시간 락은 watchdog로 주기적 갱신한다 (Redisson `RLock`이 이 방식).

## Atomic 연산과 Lua 스크립트

Redis 명령 하나하나는 atomic이지만, 여러 명령의 조합은 그렇지 않다. `GET` → 값 보고 판단 → `SET`은 race가 생긴다. 해결책은 세 가지 중 하나다.

### (1) 단일 명령으로 끝내기

- 재고 차감: `DECR stock:1001` 후 음수면 롤백. 원자적.
- 중복 체크 후 추가: `SADD visited:user:42 post:1001` — 1 반환하면 첫 방문.
- TTL 같이 설정하는 SET: `SET key v NX EX 60` — 없을 때만 생성.

### (2) Lua 스크립트

스크립트 실행 중에는 다른 명령이 끼어들지 않는다. 복수 키 조작을 atomic하게 묶는 가장 강력한 수단이다.

```lua
-- 재고 차감 with 최소값 검증
local stock = tonumber(redis.call("GET", KEYS[1]) or "0")
local qty = tonumber(ARGV[1])
if stock < qty then
    return -1
end
redis.call("DECRBY", KEYS[1], qty)
return stock - qty
```

주의: Lua 스크립트가 길어지면 **Redis 싱글 스레드 전체가 그 시간만큼 블로킹된다**. 수 ms가 넘어가는 스크립트는 지양하고, `SCRIPT LOAD` + `EVALSHA`로 네트워크 payload를 줄인다.

### (3) MULTI/EXEC (트랜잭션)

`WATCH`와 함께 optimistic lock처럼 쓸 수 있지만, 실무에서는 Lua가 대부분 더 깔끔하다. Cluster 환경에서는 모든 키가 같은 hash slot에 있어야 한다는 제약이 붙는다.

## Pub/Sub vs Streams — 메시징 패턴 선택

### Pub/Sub

- fire-and-forget.
- 구독자가 없으면 메시지는 사라진다.
- 재연결 시 놓친 메시지 복구 불가.
- 실시간 캐시 무효화 브로드캐스트, 라이브 알림 정도에만 쓴다.

### Streams (XADD / XREAD / XGROUP)

- Kafka와 유사한 append-only 로그.
- Consumer group, offset 관리, 재시도(pending entries list), DLQ 패턴 구현 가능.
- 주문 이벤트, 감사 로그, 백그라운드 작업 큐 등 **유실되면 안 되는 이벤트**에 적합.

```
XADD orders:stream * orderId 1001 status paid
XGROUP CREATE orders:stream billing $ MKSTREAM
XREADGROUP GROUP billing worker-1 COUNT 10 BLOCK 2000 STREAMS orders:stream >
XACK orders:stream billing <message-id>
```

Kafka가 이미 있는 조직이라면 이벤트 소싱의 본류는 Kafka에 두고, Redis Streams는 **짧은 생명 주기의 작업 큐**(이미지 썸네일 생성, 메일 큐)에만 쓰는 것이 일반적인 분리다.

## Cluster 환경의 제약 — CROSSSLOT 문제

Redis Cluster는 키를 16384개 hash slot으로 나눠 샤드에 분배한다. Lua 스크립트나 MULTI/EXEC는 **하나의 slot 안에서만** 동작한다.

```
MSET user:1:name Alice user:2:name Bob
→ (error) CROSSSLOT Keys in request don't hash to the same slot
```

해시 태그 `{}`로 같은 slot에 묶을 수 있다.

```
MSET {user:1}:name Alice {user:1}:email alice@x.com
```

설계 원칙은 명확하다. **함께 atomic하게 조작해야 하는 키들은 같은 해시 태그를 공유**한다. 주문과 주문 아이템, 유저와 유저 프로필 같은 것들이다. 반대로 전혀 관련 없는 키에 같은 태그를 붙이면 특정 slot만 비대해지는 **hot slot** 문제가 생긴다.

## Hot Key와 Big Key — 운영의 두 가지 지뢰

### Hot Key

특정 키 하나에 트래픽이 쏠려 해당 샤드의 CPU가 포화되는 현상이다. 대응 방법:

- **로컬 캐시 계층 추가**: Caffeine 같은 in-process 캐시를 Redis 앞에 두고, 짧은 TTL(1~5초)로 동일 키 조회를 앱 서버 레벨에서 흡수한다.
- **키 샤딩**: `counter:page:123` 하나 대신 `counter:page:123:{0..9}` 10개에 분산 INCR하고, 읽을 때 합산한다. 정확도를 약간 포기하는 대신 쓰기가 분산된다.
- **Read replica 활용**: 읽기만 하는 트래픽이면 replica로 분산.

### Big Key

하나의 키에 수십~수백 MB가 들어있는 경우다. `DEL`만 해도 Redis 스레드가 수초 멈춘다. 대응:

- 리스트/해시를 논리적으로 쪼갠다 (`chat:room:1:msgs:2026-04` 처럼 날짜/범위 파티셔닝).
- 삭제는 `UNLINK`로 비동기화한다 (Redis 4.0+).
- `redis-cli --bigkeys`, `MEMORY USAGE key`로 주기적으로 감시한다.

### 금지해야 할 명령

- `KEYS *` — O(N), 전체 블로킹. 반드시 `SCAN`으로 대체.
- `FLUSHALL` / `FLUSHDB` — 프로덕션에서는 rename-command로 막아두는 것이 안전.
- `SMEMBERS huge_set` — 큰 집합 전체 조회. `SSCAN`으로 대체.

## Bad vs Improved 예제 — 재고 차감

### Bad: 애플리케이션 레벨 GET/SET

```java
Integer stock = redis.get("stock:1001");
if (stock >= qty) {
    redis.set("stock:1001", stock - qty);
    orderService.createOrder(...);
}
```

문제점:
- GET과 SET 사이에 다른 요청이 끼어든다 → oversell.
- 애플리케이션 예외 시 차감만 되고 주문은 실패 → 재고 유실.

### Improved: Lua로 원자화 + DB 이중 방어

```java
String LUA = """
    local stock = tonumber(redis.call('GET', KEYS[1]) or '0')
    local qty = tonumber(ARGV[1])
    if stock < qty then return -1 end
    redis.call('DECRBY', KEYS[1], qty)
    return stock - qty
""";

Long remaining = redis.eval(LUA, List.of("stock:1001"), List.of("2"));
if (remaining < 0) throw new OutOfStockException();

try {
    orderService.createOrder(...);   // DB 트랜잭션, 유니크 제약 포함
} catch (Exception e) {
    redis.incrBy("stock:1001", 2);   // 보상 차감 복원
    throw e;
}
```

핵심은 Redis 차감을 **예약(reservation)** 으로 다루고, DB 주문 생성을 최종 commit으로 본다는 점이다. DB 쪽에도 유니크 제약이나 재고 컬럼의 CHECK 제약을 걸어 "Redis가 거짓말을 해도" 이중 판매가 나지 않도록 한다.

## 로컬 실습 환경

Docker 하나로 충분하다.

```bash
docker run -d --name redis-study \
    -p 6379:6379 \
    redis:7.2 redis-server --appendonly yes

docker exec -it redis-study redis-cli
```

Cluster 실험이 필요하면 `redis:7.2` 이미지 + `redis-cli --cluster create`로 6노드(3 master / 3 replica)를 띄우는 bitnami의 compose 예제를 쓰는 것이 빠르다. MySQL과 같이 띄워야 하는 경우는 아래처럼 최소 구성으로 충분하다.

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7.2
    ports: ["6379:6379"]
    command: ["redis-server", "--appendonly", "yes"]
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: study
    ports: ["3306:3306"]
```

## 실제로 돌려볼 실습 과제

### 실습 1 — Cache-Aside + TTL 지터

1. MySQL에 `product(id, name, price)` 테이블을 만들고 10만 row를 INSERT.
2. Spring Boot에서 `GET /products/{id}` 엔드포인트를 Cache-Aside로 구현.
3. `ttl = 300 + rand(0, 60)` 지터를 적용.
4. wrk로 동일 상품 1000 concurrent 부하 → DB 쿼리 수가 1회 근방인지 슬로우 쿼리 로그로 확인.

### 실습 2 — Lua 재고 차감

1. `stock:{productId}` 키에 초기 재고 100 SET.
2. 위의 차감 Lua를 적용.
3. 200 concurrent로 qty=1 차감 요청 200개 → 정확히 100개만 성공하는지 검증.
4. Lua 없이 GET/DECR로 바꿔 같은 테스트 → 초과 판매 재현.

### 실습 3 — 분산락 타임아웃 재현

1. Jedis/Lettuce로 `SET lock NX EX 2`.
2. 임계 구역에서 `Thread.sleep(3000)` — TTL보다 오래 걸리게.
3. 다른 프로세스가 같은 락을 잡는지 확인.
4. release를 **Lua token 검증 없이** DEL만 하게 만들어 "남의 락 지우기" 시나리오 재현.
5. Lua 기반 release로 수정해 재현되지 않는 것 확인.

### 실습 4 — Streams consumer group

1. `XADD orders * ...`로 100건 produce.
2. `XREADGROUP` 워커 2개 기동.
3. 한 워커 중간에 죽이고 `XPENDING`으로 미처리 메시지 확인.
4. `XCLAIM`으로 다른 워커에 재할당.

## 면접 답변 프레이밍

면접관이 "캐시 전략 설명해 보세요"라고 물을 때, 교과서 정의부터 시작하면 깊이 없는 답변이 된다. 다음 골격이 더 잘 먹힌다.

> "저는 Cache-Aside를 기본으로 쓰고, 쓰기 경로에서는 set이 아니라 delete를 씁니다. 이유는 동시 쓰기 시 stale 캐시가 남는 race를 줄이기 위해서입니다. TTL에는 항상 랜덤 지터를 넣어 동시 만료를 피하고, 인기 키의 경우 probabilistic early expiration이나 분산락으로 stampede를 제어합니다. 분산락은 Redlock이라도 GC stall 상황에서 상호 배제를 절대 보장하지는 못하기 때문에, 돈이 걸린 경로에는 DB 유니크 제약이나 SELECT FOR UPDATE를 이중 방어로 둡니다."

이 답에 면접관이 이어 물을 확률이 높은 질문과 답 방향을 미리 준비해 둔다.

- **"그럼 delete 후 바로 다른 요청이 miss로 DB 치면요?"** → hot key는 재계산 구간에 분산락을 걸어 단일 워커만 DB를 치게 한다, 나머지는 짧게 재시도.
- **"Redis Cluster에서 Lua 못 쓸 때는?"** → 같은 slot으로 묶는 hash tag를 설계에 반영한다. 불가능한 경우 애플리케이션 레벨에서 보상 트랜잭션을 설계한다.
- **"Redis 장애 나면?"** → 캐시는 장애 내성(graceful degradation) 전제로 설계한다. 캐시 호출을 타임아웃 짧게(예: 50ms) 걸고 실패 시 DB 직접 조회 + circuit breaker로 보호.

경력자 톤으로 말할 때는 "OO 상황에서 이런 장애를 본 적이 있다 → 원인은 X였다 → 이후에는 Y 패턴으로 바꿨다" 흐름이 가장 설득력이 있다. 추상적인 best practice 나열은 주니어 답변처럼 들린다.

## 체크리스트

- [ ] Cache-Aside + delete-on-write를 기본값으로 이해하고, 언제 write-through/write-behind로 넘어가는지 설명할 수 있다.
- [ ] TTL 지터의 목적과 미적용 시의 thundering herd를 예시로 설명할 수 있다.
- [ ] Cache stampede 대응 세 가지(분산락, probabilistic early expiration, refresh-ahead)의 trade-off를 말할 수 있다.
- [ ] `SET NX PX` + Lua 기반 release를 직접 구현할 수 있다.
- [ ] Redis 분산락이 mutual exclusion을 절대적으로 보장하지 않는 이유(GC, clock drift, network partition)를 설명할 수 있다.
- [ ] Lua 스크립트가 싱글 스레드를 블로킹한다는 점과, 긴 스크립트 사용 시의 영향을 이해하고 있다.
- [ ] Cluster 환경의 CROSSSLOT 제약과 hash tag 설계 원칙을 적용할 수 있다.
- [ ] Pub/Sub과 Streams의 차이, 각각 적합한 유스케이스를 구분할 수 있다.
- [ ] Hot key / big key 탐지 방법(`--bigkeys`, `MEMORY USAGE`, 모니터링)과 대응책을 알고 있다.
- [ ] `KEYS *`, `FLUSHALL`, 큰 컬렉션 전수 조회 같은 금지 명령과 대체 명령(`SCAN`, `UNLINK` 등)을 구분한다.
- [ ] 재고 차감 같은 critical path에서 Redis 차감 + DB 제약 이중 방어 구조를 설계할 수 있다.
- [ ] 캐시 장애 시 graceful degradation(타임아웃, circuit breaker, DB 직접 조회) 경로가 준비되어 있다.
