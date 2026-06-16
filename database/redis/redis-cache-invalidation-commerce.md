# [초안] Redis 캐시 무효화 - 커머스 메뉴/프로모션/회원 정합성 실전

## 왜 이 주제가 중요한가

커머스 백엔드에서 Redis는 거의 모든 읽기 경로의 핵심이다. 메뉴 트리, 프로모션 배너, 회원 등급/포인트, 매장 영업 정보, 추천 상품처럼 한 번 조회되면 수백\~수천 명에게 동일하게 응답되는 데이터는 DB가 아니라 Redis가 받아낸다. 캐시가 막아주지 못하면 메뉴 한 번 클릭에 수십 개의 쿼리가 동시에 RDB에 떨어지고, 트래픽이 몰리는 점심·저녁 피크에 곧장 장애로 이어진다.

문제는 캐시를 "어떻게 채우느냐"보다 "언제, 어떻게 비우느냐"에서 더 자주 터진다. 메뉴 가격은 바뀌었는데 화면에는 어제 가격이 노출되고, 프로모션은 종료됐는데 결제 단계에서 할인 코드가 여전히 통과하고, 회원 등급은 올라갔는데 일부 서버에서만 옛 등급으로 응답하는 식이다. 이 문서는 cache-aside·write-through·TTL·pub/sub·fanout invalidation 같은 기본기를 정리하고, RabbitMQ Fanout으로 분산 캐시를 무효화해 본 실무 경험을 면접 답변으로 어떻게 풀어낼지까지 이어 본다.

## 핵심 개념 정리

### [Cache-Aside](cache-aside.md) (Lazy Loading)

가장 흔한 패턴이다. 애플리케이션이 캐시를 먼저 조회하고, miss면 DB에서 읽어 캐시에 채운 뒤 응답한다.

```
1) GET cache:menu:123          → miss
2) SELECT * FROM menu WHERE id=123
3) SETEX cache:menu:123 600 {json}
4) return menu
```

장점은 단순함과 캐시 장애 시 fallback이 자연스럽다는 점. 단점은 첫 요청에 항상 DB 부하가 가고, 무효화는 별도로 해야 한다는 점이다. 보통 쓰기 경로에서 `DEL` 또는 `EXPIRE 0`을 같이 호출한다.

### Write-Through / Write-Behind

쓰기 시점에 캐시와 DB를 같이 갱신하는 방식이다. write-through는 동기적으로 둘 다 쓰고, write-behind는 캐시에 먼저 쓰고 DB는 비동기로 따라간다.

커머스 메뉴/프로모션처럼 **조회 100 : 갱신 1** 비율의 데이터는 write-through까지 갈 필요가 거의 없다. 단순한 cache-aside + 명시적 무효화가 정답인 경우가 많다. write-behind는 데이터 유실 위험을 감수해야 하므로 회원 포인트, 결제 잔액 같은 데이터에 함부로 쓰면 안 된다.

### TTL 기반 만료

`SETEX` 또는 `EXPIRE`로 키에 만료 시간을 건다. TTL은 "최악의 경우라도 이 시간 안에는 정합성이 회복된다"는 안전망이다.

- 메뉴 트리: 10\~30분
- 프로모션 메타: 1\~5분 (시작/종료 경계 때문에 짧게)
- 회원 기본 정보: 5\~10분
- 베스트셀러 랭킹: 1\~3분
- 정적인 매장 정보: 30분\~2시간

TTL만 믿으면 갱신이 반영되기까지 항상 그 시간만큼 stale을 노출한다. TTL은 "보조"이고, 명시적 invalidation이 "주"가 되어야 한다.

### Pub/Sub 기반 분산 무효화

서버 인스턴스가 여러 대일 때, 한 인스턴스에서 캐시를 갱신해도 다른 인스턴스의 **로컬 캐시**(L1)는 여전히 옛 데이터를 들고 있을 수 있다. 이때 Redis Pub/Sub이나 메시지 브로커로 invalidation 이벤트를 모든 노드에 fanout 한다.

```
Admin → Redis Pub/Sub channel:menu-invalidate → 모든 API 서버 SUBSCRIBE
```

각 서버는 메시지를 받으면 자신의 로컬 Caffeine/Guava 캐시 엔트리를 지운다. Redis 자체 캐시는 한 번만 지우면 되지만, JVM 안의 L1까지 동기화하려면 이런 fanout이 필수다.

### Fanout Invalidation

"하나의 변경이 여러 키를 무효화"하는 케이스다. 예를 들어 카테고리 A 가격 정책이 바뀌면:

- `cache:menu:category:A`
- `cache:menu:list:popular`
- `cache:menu:detail:{각 상품 id}`
- 추천 페이지의 `cache:reco:home:v1`

이 중 어디까지 지울지가 설계 포인트다. 너무 좁게 지우면 stale 노출, 너무 넓게 지우면 cache stampede. 보통은 "버전 키"를 두고, 카테고리 단위로 `cache:ver:menu:cat:A`를 증가시켜 키 prefix에 버전을 포함시키는 식으로 우회한다.

## 커머스에서 자주 만나는 정합성 문제

### 메뉴 가격/노출 변경

운영자가 어드민에서 메뉴 가격을 조정한다. cache-aside만 쓰고 invalidation을 안 하면 TTL 만료 전까지 옛 가격이 유지된다. 가격은 결제까지 이어지므로 stale은 곧 컴플레인이다.

대응:
- 어드민 저장 트랜잭션 커밋 후 `DEL cache:menu:detail:123` 호출
- 같은 카테고리 리스트 캐시도 같이 무효화
- 다중 인스턴스 L1 캐시는 Pub/Sub fanout으로 정리

### 프로모션 시작/종료 경계

프로모션은 "12:00:00 시작"처럼 분 단위 경계가 중요하다. TTL 10분짜리 캐시에 11:55에 조회된 프로모션 응답이 들어가면, 12:00\~12:05 사이에는 시작된 프로모션이 보이지 않을 수 있다.

대응:
- 프로모션 메타는 TTL 짧게 (60\~120초)
- 시작/종료 시각 가까운 키는 별도로 짧은 TTL
- 시작·종료 스케줄러가 명시적으로 `DEL` 호출

### 회원 등급/포인트 변경

회원 등급이 VIP로 올라갔는데 일부 서버는 GENERAL을 들고 있어서 등급 할인 미적용. 이런 류는 사용자에게 직접 보이고 CS로 직행한다.

대응:
- 등급 변경 이벤트를 큐에 넣고 모든 인스턴스가 SUBSCRIBE
- 회원별 캐시는 `cache:member:{id}` 한 키로 통합해 무효화 단위를 단순화
- 결제 같은 critical path에서는 캐시를 신뢰하지 말고 DB 한 번 더 조회

### Cache Stampede (캐시 쇄도)

인기 상품의 캐시 키가 동시에 만료되면 수백 개의 요청이 동시에 DB로 몰린다. 캐시 무효화 패턴 자체가 stampede를 만들 수도 있다 — `DEL` 직후 첫 요청 수백 개가 한꺼번에 miss를 본다.

대응:
- **Mutex/distributed lock**: 첫 요청만 DB로 보내고 나머지는 잠깐 대기
- **Probabilistic early expiration**: TTL이 가까워지면 일부 요청이 미리 갱신
- **Stale-While-Revalidate**: 만료 직후에도 옛 값을 잠깐 더 응답하고, 백그라운드로 갱신

### 분산 락의 무효화 보장

여러 서버가 동시에 같은 키를 갱신하려 할 때 Redlock이나 `SET NX EX`로 락을 잡는다. 락을 잡은 서버만 DB 조회 → 캐시 갱신. 락을 못 잡은 서버는 짧게 sleep 후 캐시 재조회.

```
SET cache:lock:menu:123 {token} NX EX 5
```

여기서 `NX`는 키가 없을 때만 설정, `EX 5`는 5초 TTL. 작업이 5초보다 오래 걸리면 다른 서버가 동시에 갱신할 수 있으므로 작업 시간 추정과 락 TTL 설정이 핵심이다. 해제 시에는 본인이 잡은 토큰인지 Lua 스크립트로 확인하고 `DEL` 한다.

## Bad vs Improved 예제

### Bad — 무효화 없이 TTL만 의존

```java
public Menu getMenu(Long id) {
    String key = "menu:" + id;
    String cached = redis.get(key);
    if (cached != null) return parse(cached);
    Menu menu = menuRepository.findById(id);
    redis.setex(key, 600, toJson(menu));
    return menu;
}

@Transactional
public void updateMenuPrice(Long id, int price) {
    menuRepository.updatePrice(id, price);
    // 캐시는 그대로. 최대 10분간 옛 가격 노출.
}
```

문제:
- 가격 변경 후 최대 10분 stale
- 다중 인스턴스 L1 캐시는 갱신 후에도 옛 값 보유
- 무효화 정책이 코드로 표현되어 있지 않아 운영자가 추적 불가

### Improved — 명시적 무효화 + Pub/Sub fanout + 분산 락

```java
private static final String LOCK_PREFIX = "lock:menu:";
private static final String CACHE_PREFIX = "menu:";
private static final String INVALIDATE_CHANNEL = "menu-invalidate";

public Menu getMenu(Long id) {
    String key = CACHE_PREFIX + id;
    String cached = redis.get(key);
    if (cached != null) return parse(cached);

    String lockKey = LOCK_PREFIX + id;
    String token = UUID.randomUUID().toString();
    boolean locked = redis.set(lockKey, token, "NX", "EX", 3);

    if (!locked) {
        sleep(50);
        cached = redis.get(key);
        if (cached != null) return parse(cached);
        return menuRepository.findById(id);
    }

    try {
        Menu menu = menuRepository.findById(id);
        redis.setex(key, 600, toJson(menu));
        return menu;
    } finally {
        releaseLockSafely(lockKey, token);
    }
}

@Transactional
public void updateMenuPrice(Long id, int price) {
    menuRepository.updatePrice(id, price);
    TransactionSynchronizationManager.registerSynchronization(
        new TransactionSynchronization() {
            @Override public void afterCommit() {
                redis.del(CACHE_PREFIX + id);
                redis.publish(INVALIDATE_CHANNEL, String.valueOf(id));
            }
        }
    );
}
```

핵심 변화:
- 무효화는 트랜잭션 **커밋 후**에 실행 (롤백 시 캐시만 비우는 사고 방지)
- Pub/Sub로 모든 인스턴스의 L1 캐시도 정리
- miss 폭주는 분산 락으로 단일 갱신자만 통과
- 락 해제는 본인 토큰 검증 후 (다른 서버 락을 잘못 풀지 않도록 Lua로 atomic 처리하면 더 안전)

### 더 안전한 락 해제 (Lua)

```lua
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

## 로컬 실습 환경

도커로 Redis 7 띄우고 바로 시험해 본다.

```bash
docker run -d --name redis-lab -p 6379:6379 redis:7-alpine
docker exec -it redis-lab redis-cli
```

기본 명령:

```
SET menu:123 '{"price":12000}' EX 600
GET menu:123
TTL menu:123
DEL menu:123

SUBSCRIBE menu-invalidate
PUBLISH menu-invalidate 123
```

분산 락 흉내:

```
SET lock:menu:123 token-A NX EX 3
SET lock:menu:123 token-B NX EX 3   -> nil (이미 있음)
GET lock:menu:123
```

Stampede 시뮬레이션은 `redis-benchmark` 또는 간단한 Java 스레드 풀로 동시 요청 100개를 같은 키에 던져보면 된다. 락 없이/있을 때 DB 쿼리 카운트 차이를 직접 보면 감이 잡힌다.

## 실행 가능한 예제 — Spring Boot + Lettuce

```java
@Service
@RequiredArgsConstructor
public class MenuCacheService {
    private final StringRedisTemplate redis;
    private final MenuRepository repo;

    public Menu get(Long id) {
        String key = "menu:" + id;
        String hit = redis.opsForValue().get(key);
        if (hit != null) return JsonUtil.parse(hit, Menu.class);

        Menu loaded = repo.findById(id).orElseThrow();
        redis.opsForValue().set(key, JsonUtil.toJson(loaded), Duration.ofMinutes(10));
        return loaded;
    }

    public void invalidate(Long id) {
        redis.delete("menu:" + id);
        redis.convertAndSend("menu-invalidate", String.valueOf(id));
    }
}

@Configuration
public class RedisSubscriberConfig {
    @Bean
    public RedisMessageListenerContainer container(
            RedisConnectionFactory cf, LocalCacheEvictor evictor) {
        var c = new RedisMessageListenerContainer();
        c.setConnectionFactory(cf);
        c.addMessageListener(
            (msg, pattern) -> evictor.evictMenu(new String(msg.getBody())),
            new ChannelTopic("menu-invalidate")
        );
        return c;
    }
}
```

`LocalCacheEvictor`는 Caffeine 같은 JVM 로컬 캐시를 들고 있다가 메시지를 받으면 해당 엔트리를 지운다. Redis는 공유 캐시(L2), Caffeine은 인스턴스별 L1 역할이다.

## 자주 만나는 실수 패턴

- **트랜잭션 안에서 캐시 삭제**: 트랜잭션이 롤백되어도 캐시는 이미 비워져 있음. `afterCommit`으로 미루는 것이 원칙.
- **DEL 후 즉시 SET**: 분산 환경에서 다른 서버가 그 사이에 옛 값을 다시 채울 수 있음. DEL → 다음 요청이 lazy load 하도록 두는 편이 안전.
- **TTL 무한대**: 무효화 누락 시 영원히 stale. 어떤 캐시도 TTL 없이 두지 않는 것을 기본으로.
- **Hot key 한 곳 집중**: 인기 상품 한 키에 트래픽 집중. 키 분할(`menu:123:shard:{n}`)이나 로컬 캐시 병행으로 분산.
- **Pub/Sub 메시지 유실 무시**: Redis Pub/Sub은 at-most-once. 구독자가 잠깐 끊기면 메시지 놓침. 중요한 무효화는 Stream/Kafka/RabbitMQ로 보강하거나, TTL을 짧게 가져가 fallback.
- **회원별 캐시에 PII 저장**: 주민번호, 카드번호 같은 데이터는 캐시에 두지 않거나 마스킹. 운영 디버깅 중 노출되는 사고가 잦다.

## RabbitMQ Fanout 경험을 면접 답변으로 연결

지원자 프로필상 RabbitMQ Fanout exchange로 다중 인스턴스에 이벤트를 뿌려본 경험이 있다. 이 경험은 캐시 무효화 질문에 그대로 매핑된다.

답변 골격:

> "이전 시스템에서 N대의 API 서버가 각자 로컬 캐시를 들고 있었습니다. 마스터 데이터가 어드민에서 변경되면 RabbitMQ Fanout exchange에 invalidation 이벤트를 발행하고, 모든 인스턴스가 자기 로컬 큐로 받아서 해당 캐시 엔트리만 지우는 구조였습니다. Redis만 있는 환경이라면 같은 패턴을 Redis Pub/Sub로 구현할 수 있는데, Pub/Sub은 at-most-once라 구독자가 잠깐 끊기면 메시지를 놓치는 약점이 있어서, 중요한 도메인은 메시지 큐 + 짧은 TTL을 같이 두는 식으로 안전망을 만들어야 한다고 봅니다."

여기에 더해 trade-off까지 한 줄 붙이면 좋다:

> "Fanout은 구독자별 필터링이 약해서 모든 인스턴스가 모든 invalidation을 받습니다. 캐시 종류가 늘면 토픽을 분리하거나 메시지에 도메인 태그를 넣어서 인스턴스가 자기 관심사만 처리하도록 했습니다."

## 시니어 백엔드 면접 답변 프레이밍

자주 나오는 질문과 답변 방향:

**Q. 캐시 무효화 전략을 어떻게 설계하나요?**
A. 데이터를 "조회 빈도, 갱신 빈도, stale 허용도"로 나눈다. 거의 안 바뀌는 정적 메타는 긴 TTL + 명시적 invalidation. 자주 바뀌는 회원 데이터는 짧은 TTL + 이벤트 기반 무효화. 결제·정산처럼 stale 허용 0인 데이터는 캐시를 쓰지 않거나 캐시를 신뢰하지 않는 fallback 경로를 둔다.

**Q. 캐시 stampede는 어떻게 막나요?**
A. 분산 락으로 단일 갱신자만 DB에 가게 하는 방식이 가장 직관적. 트래픽이 더 큰 경우 probabilistic early expiration이나 stale-while-revalidate를 같이 쓴다. 핵심은 "TTL이 동시에 만료되지 않도록 분산"시키는 것.

**Q. 다중 서버 환경에서 캐시 정합성을 어떻게 맞추나요?**
A. Redis 같은 공유 캐시(L2)는 한 번 갱신하면 끝이지만, 인스턴스 로컬 캐시(L1)는 별도 무효화가 필요. Pub/Sub이나 메시지 큐로 fanout 한다. Pub/Sub은 유실 가능성이 있어 critical 경로는 메시지 큐(RabbitMQ, Kafka)로 보강.

**Q. 캐시 갱신을 트랜잭션 안에서 하면 안 되나요?**
A. 트랜잭션이 롤백되면 DB는 옛 값으로 돌아가는데 캐시는 이미 비워져 있다. 다음 요청이 lazy load 하면서 옛 값을 다시 채우니까 결과적으로는 잘 굴러가긴 하는데, 그 사이에 캐시 miss 폭주가 발생할 수 있다. 그래서 트랜잭션 커밋 이후에 무효화를 호출하는 패턴이 표준.

**Q. Redis가 죽으면 어떻게 되나요?**
A. cache-aside라면 자연스럽게 DB로 fallback 된다. 단, DB가 그 트래픽을 못 받으면 곧장 장애. 그래서 Redis 장애 시나리오에는 (1) 회로 차단기로 DB 보호, (2) 로컬 캐시로 일부 요청 흡수, (3) 핫 데이터 일부는 인메모리에 미리 워밍 같은 조합을 둔다.

## 학습 체크리스트

- [ ] cache-aside, write-through, write-behind 차이를 30초 안에 설명할 수 있다
- [ ] TTL이 "보조"인 이유를 설명할 수 있다
- [ ] 트랜잭션 커밋 전·후 무효화 차이를 설명할 수 있다
- [ ] cache stampede의 원인과 3가지 대응책을 말할 수 있다
- [ ] 분산 락을 `SET NX EX`로 구현하고 Lua로 안전하게 해제할 수 있다
- [ ] Redis Pub/Sub과 메시지 큐(RabbitMQ Fanout)의 신뢰성 차이를 설명할 수 있다
- [ ] 다중 인스턴스 L1 캐시 동기화 시나리오를 그릴 수 있다
- [ ] 메뉴/프로모션/회원 도메인별로 적절한 TTL과 무효화 정책을 제안할 수 있다
- [ ] hot key 문제와 키 샤딩 전략을 설명할 수 있다
- [ ] RabbitMQ Fanout 경험을 캐시 무효화 답변으로 자연스럽게 연결할 수 있다
- [ ] 결제 같은 critical path에서 캐시를 어떻게 다룰지 결정 기준을 갖고 있다
- [ ] Redis 장애 시 fallback 시나리오를 최소 2개 갖고 있다
