# [초안] Redis Cache-Aside 완전 정복 — 흐름, 정합성, 스탬피드, 장애 대응까지

> Cache-Aside는 단순해 보이지만, 실무에서 제대로 구현하려면 TTL 전략, 스탬피드 방어, 정합성 트레이드오프, 장애 시나리오를 모두 고려해야 한다. 이 문서는 Java 백엔드 관점에서 Cache-Aside의 전 과정을 하나씩 짚는다.

---

## 왜 Cache-Aside인가

캐시 전략은 크게 네 가지로 나뉜다. Read-Through, Write-Through, Write-Behind, 그리고 Cache-Aside다. 이 중 Cache-Aside가 가장 많이 쓰이는 이유는 단순하다 — **애플리케이션이 캐시를 직접 제어**하기 때문이다.

Read-Through와 Write-Through는 캐시 레이어 자체가 DB 접근 로직을 포함해야 한다. Redis 기본 기능만으로는 지원되지 않으며, 별도 캐시 미들웨어(예: NCache, Coherence)나 커스텀 플러그인이 필요하다. 반면 Cache-Aside는 애플리케이션 코드 안에서 캐시 조회 → 미스 시 DB 조회 → 캐시 저장 순서로 동작하기 때문에 Redis 단독으로도 쉽게 구현할 수 있다.

Spring 기반 Java 백엔드에서 `@Cacheable`이 기본적으로 Cache-Aside 패턴으로 동작한다. 이 어노테이션이 내부에서 무엇을 하는지, 어디서 문제가 생길 수 있는지를 이해하지 못하면 실무 장애로 이어진다.

---

## 핵심 개념: Cache-Aside 동작 흐름

Cache-Aside는 **Lazy Loading**이라고도 부른다. 데이터를 미리 캐시에 채워두는 게 아니라, 처음 요청이 왔을 때 DB에서 읽어 캐시에 올리는 방식이기 때문이다.

### 읽기 흐름 (Read Path)

```
1. 클라이언트가 데이터 요청
2. 애플리케이션이 Redis에서 키 조회
   ├─ HIT: Redis에서 바로 반환 → 종료
   └─ MISS: Redis에 데이터 없음
       3. DB에서 데이터 조회
       4. 조회한 데이터를 Redis에 저장 (TTL 포함)
       5. 클라이언트에 반환
```

### 쓰기 흐름 (Write Path)

Cache-Aside의 쓰기는 두 가지 방식이 있다.

**방식 1 — 캐시 무효화**(Invalidation, 권장):
```
1. DB에 데이터 업데이트
2. Redis에서 해당 키 삭제 (DEL)
3. 다음 읽기 요청이 올 때 DB에서 다시 읽어 캐시 갱신
```

**방식 2 — 캐시 갱신**(Update):
```
1. DB에 데이터 업데이트
2. Redis에 새 데이터를 즉시 SET
```

실무에서는 방식 1(무효화)이 훨씬 안전하다. 방식 2는 DB 업데이트와 캐시 갱신 사이에 레이스 컨디션이 발생할 수 있기 때문이다(뒤에서 상세히 다룬다).

---

## 정합성 트레이드오프

Cache-Aside의 가장 큰 약점은 **캐시와 DB 사이에 짧은 불일치 구간이 존재**한다는 점이다. 이 구간이 어디서 발생하는지, 어떻게 줄일 수 있는지를 이해해야 한다.

### 시나리오 1 — 동시 쓰기 레이스 (Write Race)

```
시간 →
T1: Thread A가 DB에서 user:1 읽음 (잔액: 10,000)
T2: Thread B가 user:1 잔액을 20,000으로 DB 업데이트, 캐시 DEL
T3: Thread A가 캐시에 구버전(10,000)을 SET — 캐시 오염!
T4: 이후 조회는 캐시에서 10,000을 반환 (DB는 20,000)
```

이 문제는 캐시 **갱신**(방식 2)을 쓸 때 발생한다. 캐시 **무효화**(방식 1)를 쓰면 T3에서 캐시를 SET하는 대신 아무것도 하지 않으므로 다음 읽기가 DB를 직접 조회해 최신값을 가져온다.

정합성이 극도로 중요한 데이터(계좌 잔액, 재고 수량 등)라면 Cache-Aside 자체를 피하거나, 캐시를 짧은 TTL의 읽기 전용 버퍼로만 사용하는 것이 안전하다.

### 시나리오 2 — DB 업데이트 후 캐시 DEL 실패

```
T1: DB 업데이트 성공
T2: Redis DEL 실패 (네트워크 순단, Redis 재시작 등)
결과: 캐시에 구버전 데이터가 TTL 만료 때까지 잔류
```

**대응 방법:**
- TTL을 짧게 설정해 불일치 구간을 최소화
- Redis 연산에 재시도 로직 추가 (짧은 지수 백오프)
- 중요 데이터는 쓰기 후 캐시 DEL을 트랜잭션 이벤트로 처리 (DB 커밋 이후 이벤트 발행)

### 시나리오 3 — 캐시 미스 후 DB에서 null 읽기 (Cache Penetration)

존재하지 않는 키로 반복 요청이 오면 매번 캐시 미스 → DB 쿼리가 발생한다. 악의적인 요청이라면 DB에 심각한 부하를 줄 수 있다.

**대응 방법:**
```java
// null 결과도 캐시에 저장 (짧은 TTL로)
String value = redis.get(key);
if (value == null) {
    Product product = db.findById(id); // null일 수도 있음
    if (product == null) {
        redis.setex(key, 30, "NULL_SENTINEL"); // 30초짜리 빈 마커
    } else {
        redis.setex(key, 3600, serialize(product));
    }
}
```

Bloom Filter를 앞에 배치해 존재하지 않는 키를 필터링하는 방법도 있다. Redis에는 RedisBloom 모듈이 있고, Spring Data Redis 3.x부터 일부 지원한다.

---

## TTL 전략

TTL은 Cache-Aside의 핵심 파라미터다. 너무 길면 정합성 문제, 너무 짧으면 캐시 효과가 없다.

### TTL 설계 기준

| 데이터 특성 | 권장 TTL | 이유 |
|------------|---------|------|
| 실시간 재고/가격 | 10~30초 | 불일치가 비즈니스 손실로 이어짐 |
| 사용자 프로필 | 5~30분 | 자주 바뀌지 않음, 미미한 불일치 허용 |
| 상품 상세 페이지 | 1~24시간 | 카탈로그성 데이터, 변경 드묾 |
| 공지사항, 배너 | 1~6시간 | 관리자가 직접 캐시 무효화 가능 |
| 정적 코드/코드표 | 24시간 이상 | 배포 시에만 변경 |

### TTL 분산: 동시 만료 방지

같은 TTL 값을 모든 키에 적용하면, 해당 시각에 대량의 키가 동시에 만료되어 DB에 순간적으로 폭발적인 부하가 발생한다. 이를 **Thundering Herd** 또는 **Cache Avalanche**라고 부른다.

```java
// 나쁜 예: 모든 상품에 3600초 고정
redis.setex("product:" + id, 3600, data);

// 좋은 예: 기준 TTL에 ±10% 랜덤 지터 추가
int baseTtl = 3600;
int jitter = ThreadLocalRandom.current().nextInt(-360, 361); // ±360초
redis.setex("product:" + id, baseTtl + jitter, data);
```

---

## Cache Stampede (캐시 스탬피드)

스탬피드는 Cache-Aside에서 가장 자주 언급되는 문제다. 인기 키의 TTL이 만료되는 순간, 수백~수천 개의 동시 요청이 모두 캐시 미스를 확인하고 동시에 DB를 조회하는 현상이다.

```
T0: product:hot-item 캐시 만료
T1: 요청 1,000건이 동시에 Redis GET → 모두 MISS
T2: 1,000건 모두 MySQL SELECT 실행 → DB CPU 100%
T3: 1,000건 모두 Redis SET → 대부분 중복 쓰기
```

### 해결책 1 — 분산 락 (Mutex Lock)

캐시 미스 시 하나의 요청만 DB를 조회하고, 나머지는 대기하거나 구버전 데이터를 반환한다.

```java
public Product getProduct(long id) {
    String cacheKey = "product:" + id;
    String lockKey = "lock:product:" + id;

    // 1. 캐시 조회
    String cached = redis.get(cacheKey);
    if (cached != null) {
        return deserialize(cached, Product.class);
    }

    // 2. 캐시 미스 — 락 시도 (SET NX EX)
    boolean acquired = redis.set(lockKey, "1", SetParams.setParams().nx().ex(5)) != null;

    if (acquired) {
        try {
            // 3. 락 획득 → DB 조회 후 캐시 갱신
            Product product = productRepository.findById(id).orElseThrow();
            redis.setex(cacheKey, 3600, serialize(product));
            return product;
        } finally {
            redis.del(lockKey);
        }
    } else {
        // 4. 락 획득 실패 → 잠시 대기 후 캐시 재조회
        Thread.sleep(50);
        cached = redis.get(cacheKey);
        return cached != null ? deserialize(cached, Product.class) : getFromDb(id);
    }
}
```

**단점:** 대기 중인 요청이 증가하면 레이턴시 스파이크 발생. 락 획득 실패 시 DB 직접 조회 폴백이 필요하다.

### 해결책 2 — 확률적 조기 갱신 (Probabilistic Early Expiration)

TTL이 만료되기 전에 확률적으로 미리 갱신해, 만료 시점의 폭발적 재조회를 방지한다. Facebook이 제안한 XFetch 알고리즘이 이 방식이다.

```java
public Product getProductWithPER(long id) {
    String key = "product:" + id;
    CachedValue<Product> cached = redis.getWithTtl(key); // 값 + 남은 TTL 함께 조회

    if (cached != null) {
        long remainingTtl = cached.getTtl(); // 남은 TTL (초)
        double beta = 1.0; // 공격성 조절 파라미터 (1.0 권장)
        double recomputeTime = 0.1; // 예상 DB 조회 시간 (초)

        // XFetch: -beta * recomputeTime * log(random()) > remainingTtl 이면 조기 갱신
        double threshold = -beta * recomputeTime * Math.log(Math.random());
        if (threshold > remainingTtl) {
            // 조기 갱신 트리거
            Product fresh = productRepository.findById(id).orElseThrow();
            redis.setex(key, 3600, serialize(fresh));
            return fresh;
        }
        return cached.getValue();
    }

    // 캐시 없음 — 일반 경로
    Product product = productRepository.findById(id).orElseThrow();
    redis.setex(key, 3600, serialize(product));
    return product;
}
```

**장점:** 락 없이 동작하므로 레이턴시 스파이크가 없다. 단, 여러 인스턴스가 동시에 조기 갱신을 트리거할 수 있어 DB 부하가 소폭 증가할 수 있다.

### 해결책 3 — 사전 워밍 (Pre-warming)

캐시가 만료되기 전에 스케줄러가 미리 갱신한다. 가장 확실하지만, 갱신 주기와 TTL을 맞추는 운영 부담이 생긴다.

```java
@Scheduled(fixedDelay = 3000000) // 50분마다
public void warmPopularProducts() {
    List<Long> hotIds = analyticsService.getTopProductIds(100);
    for (Long id : hotIds) {
        Product product = productRepository.findById(id).orElseThrow();
        redis.setex("product:" + id, 3600, serialize(product));
    }
}
```

---

## 장애 시나리오와 대응

### 장애 1 — Redis 완전 다운

Redis가 재시작되거나 연결 불가 상태가 되면 모든 요청이 DB로 직행한다. DB가 이 트래픽을 감당하지 못하면 연쇄 장애(Cascading Failure)로 이어진다.

**대응 패턴 — Circuit Breaker:**

```java
@Service
public class ProductService {
    private final CircuitBreaker redisCircuitBreaker;
    private final StringRedisTemplate redis;
    private final ProductRepository db;

    public Product getProduct(long id) {
        String key = "product:" + id;

        try {
            // Redis 조회를 Circuit Breaker로 감쌈
            String cached = redisCircuitBreaker.executeSupplier(() -> redis.opsForValue().get(key));
            if (cached != null) {
                return deserialize(cached, Product.class);
            }
        } catch (Exception e) {
            // Redis 장애 — DB 폴백 진행 (Circuit Breaker가 OPEN 상태)
            log.warn("Redis unavailable, falling back to DB for key={}", key);
        }

        // DB 조회
        Product product = db.findById(id).orElseThrow();

        // Redis 복구 후 다시 저장 시도 (실패해도 계속 진행)
        try {
            redisCircuitBreaker.executeRunnable(() ->
                redis.opsForValue().set(key, serialize(product), Duration.ofHours(1))
            );
        } catch (Exception ignored) {}

        return product;
    }
}
```

Resilience4j의 `CircuitBreaker`를 사용하면 Redis 연속 실패 N회 시 자동으로 OPEN 상태로 전환하고, 이후 요청은 Redis를 거치지 않고 즉시 DB로 간다. 복구 후 자동으로 HALF-OPEN → CLOSED로 복귀한다.

### 장애 2 — Hot Key 집중 (Hot Spot)

특정 키에 트래픽이 집중되면 Redis 단일 노드의 CPU나 네트워크 대역폭이 병목이 된다.

```bash
# Redis Cluster 환경에서도 같은 슬롯의 키는 한 노드에 몰림
# 예: 인기 상품 ID가 1인 경우
# product:1 → CRC16("product:1") % 16384 = 항상 같은 슬롯
```

**대응 패턴 — 로컬 캐시 레이어 (L1 + L2):**

```java
// Caffeine을 L1(JVM 내 로컬), Redis를 L2(분산)로 사용
@Bean
public Cache<String, Product> localCache() {
    return Caffeine.newBuilder()
        .maximumSize(1_000)
        .expireAfterWrite(30, TimeUnit.SECONDS) // 매우 짧은 TTL
        .build();
}

public Product getProduct(long id) {
    String key = "product:" + id;

    // L1: 로컬 캐시 조회 (네트워크 없음, 나노초)
    Product local = localCache.getIfPresent(key);
    if (local != null) return local;

    // L2: Redis 조회 (밀리초)
    String cached = redis.get(key);
    if (cached != null) {
        Product product = deserialize(cached, Product.class);
        localCache.put(key, product);
        return product;
    }

    // DB 조회
    Product product = productRepository.findById(id).orElseThrow();
    redis.setex(key, 3600, serialize(product));
    localCache.put(key, product);
    return product;
}
```

L1 TTL은 매우 짧게(10~30초) 잡아야 정합성 문제를 줄일 수 있다. 인스턴스가 여러 대라면 각각 독립적인 L1을 갖기 때문에, 쓰기 후 Redis DEL만 해서는 L1이 갱신되지 않는다. Pub/Sub으로 무효화 신호를 브로드캐스트하거나, 짧은 TTL로 자연 만료를 기다리는 방식을 선택해야 한다.

### 장애 3 — 직렬화 버전 불일치

애플리케이션을 새 버전으로 배포할 때, 캐시에 이전 버전의 직렬화된 데이터가 남아 있으면 역직렬화 오류가 발생한다.

```java
// 나쁜 예: Java 기본 직렬화 (SerialVersionUID 변경 시 오류)
redis.setex(key, 3600, SerializationUtils.serialize(product));

// 좋은 예: JSON 직렬화 (필드 추가/제거에 유연)
redis.setex(key, 3600, objectMapper.writeValueAsString(product));
```

또는 캐시 키에 버전을 포함해 배포 시 자동으로 새 키를 사용하는 방식도 있다.

```java
private static final String CACHE_VERSION = "v2";
String key = "product:" + CACHE_VERSION + ":" + id;
```

---

## 로컬 Redis 실습 환경

### Docker로 Redis 띄우기

```bash
# Redis 단일 인스턴스 실행
docker run -d \
  --name redis-dev \
  -p 6379:6379 \
  redis:7.2-alpine \
  redis-server --loglevel verbose

# 접속 확인
docker exec -it redis-dev redis-cli ping
# PONG

# 로그 확인
docker logs -f redis-dev
```

### Cache-Aside 동작 직접 확인

```bash
docker exec -it redis-dev redis-cli

# 1. 캐시 없는 상태에서 조회
EXISTS product:1
# (integer) 0  → MISS

# 2. DB 조회 후 캐시 저장 시뮬레이션
SET product:1 '{"id":1,"name":"비타민C","price":12000}' EX 3600
# OK

# 3. 캐시 히트
GET product:1
# '{"id":1,"name":"비타민C","price":12000}'

# 4. TTL 확인
TTL product:1
# (integer) 3598

# 5. 업데이트 후 캐시 무효화
DEL product:1
# (integer) 1

# 6. 다음 요청은 다시 MISS → DB 조회
EXISTS product:1
# (integer) 0

# 7. null sentinel 패턴 테스트
SET product:9999 "NULL_SENTINEL" EX 30
GET product:9999
# "NULL_SENTINEL"
TTL product:9999
# (integer) 28
```

### 스탬피드 시뮬레이션

```bash
# 짧은 TTL 키 만들기
SET hot:product:1 '{"id":1}' EX 5

# 5초 후 만료 확인
sleep 5 && redis-cli TTL hot:product:1
# (integer) -2  → 만료됨 (-2: 키 없음, -1: TTL 없음)

# 만료 이벤트 구독 (별도 터미널)
redis-cli CONFIG SET notify-keyspace-events Ex
redis-cli SUBSCRIBE __keyevent@0__:expired
# 다른 터미널에서 키 만료 시 이벤트 수신됨
```

---

## Java 백엔드 구현 — Spring + Redis

### 의존성 (build.gradle)

```gradle
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-data-redis'
    implementation 'org.springframework.boot:spring-boot-starter-cache'
    implementation 'com.fasterxml.jackson.core:jackson-databind'
    implementation 'io.github.resilience4j:resilience4j-spring-boot3'
}
```

### Redis 설정

```java
@Configuration
@EnableCaching
public class RedisConfig {

    @Bean
    public RedisConnectionFactory redisConnectionFactory() {
        LettuceClientConfiguration clientConfig = LettuceClientConfiguration.builder()
            .commandTimeout(Duration.ofMillis(500)) // 타임아웃 설정 필수
            .build();

        RedisStandaloneConfiguration serverConfig =
            new RedisStandaloneConfiguration("localhost", 6379);

        return new LettuceConnectionFactory(serverConfig, clientConfig);
    }

    @Bean
    public RedisTemplate<String, Object> redisTemplate(
            RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // 키: String 직렬화
        template.setKeySerializer(new StringRedisSerializer());
        template.setHashKeySerializer(new StringRedisSerializer());

        // 값: JSON 직렬화 (역직렬화 시 타입 정보 포함)
        Jackson2JsonRedisSerializer<Object> jsonSerializer =
            new Jackson2JsonRedisSerializer<>(Object.class);
        template.setValueSerializer(jsonSerializer);
        template.setHashValueSerializer(jsonSerializer);

        template.afterPropertiesSet();
        return template;
    }

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofHours(1))
            .serializeKeysWith(
                RedisSerializationContext.SerializationPair.fromSerializer(
                    new StringRedisSerializer()))
            .serializeValuesWith(
                RedisSerializationContext.SerializationPair.fromSerializer(
                    new GenericJackson2JsonRedisSerializer()))
            .disableCachingNullValues(); // null은 캐시하지 않음 (별도 처리 필요 시 제거)

        Map<String, RedisCacheConfiguration> cacheConfigs = new HashMap<>();
        // 상품 캐시: 1시간 + 지터
        cacheConfigs.put("products", defaultConfig
            .entryTtl(Duration.ofSeconds(3600 + ThreadLocalRandom.current().nextInt(-360, 361))));
        // 사용자 프로필: 30분
        cacheConfigs.put("users", defaultConfig.entryTtl(Duration.ofMinutes(30)));

        return RedisCacheManager.builder(connectionFactory)
            .cacheDefaults(defaultConfig)
            .withInitialCacheConfigurations(cacheConfigs)
            .build();
    }
}
```

### @Cacheable 기반 Cache-Aside 구현

```java
@Service
@RequiredArgsConstructor
public class ProductService {

    private final ProductRepository productRepository;
    private final StringRedisTemplate redis;

    // @Cacheable이 자동으로 Cache-Aside를 구현
    // 키: "products::1" (캐시 이름 + "::" + SpEL 결과)
    @Cacheable(value = "products", key = "#id")
    public ProductDto getProduct(Long id) {
        // 캐시 미스 시에만 실행됨
        return productRepository.findById(id)
            .map(ProductDto::from)
            .orElseThrow(() -> new ProductNotFoundException(id));
    }

    // 업데이트: DB 갱신 후 캐시 무효화
    @CacheEvict(value = "products", key = "#id")
    @Transactional
    public ProductDto updateProduct(Long id, UpdateProductRequest request) {
        Product product = productRepository.findById(id)
            .orElseThrow(() -> new ProductNotFoundException(id));
        product.update(request.getName(), request.getPrice());
        return ProductDto.from(product);
        // @CacheEvict가 메서드 반환 후 캐시에서 해당 키 삭제
    }

    // 여러 키 동시 무효화
    @CacheEvict(value = "products", allEntries = true)
    public void clearAllProductCache() {
        // 관리자가 상품 일괄 업데이트 후 전체 캐시 초기화
    }
}
```

### @Cacheable의 한계와 수동 구현

`@Cacheable`은 편리하지만 다음 상황에서는 직접 구현해야 한다.

- 스탬피드 방어 (락, PER 알고리즘)
- null 결과 캐싱 (null sentinel)
- 복잡한 키 구성 (다중 파라미터 조합)
- 조건부 TTL

```java
@Service
@RequiredArgsConstructor
public class ProductCacheService {

    private static final String KEY_PREFIX = "product:v2:";
    private static final int BASE_TTL = 3600;
    private static final String NULL_SENTINEL = "__NULL__";

    private final StringRedisTemplate redis;
    private final ProductRepository productRepository;
    private final ObjectMapper objectMapper;

    public Optional<ProductDto> getProduct(Long id) {
        String key = KEY_PREFIX + id;
        String cached = redis.opsForValue().get(key);

        // 캐시 히트
        if (cached != null) {
            if (NULL_SENTINEL.equals(cached)) {
                return Optional.empty(); // 존재하지 않는 데이터 → null sentinel
            }
            try {
                return Optional.of(objectMapper.readValue(cached, ProductDto.class));
            } catch (JsonProcessingException e) {
                log.warn("Cache deserialization failed for key={}, evicting", key);
                redis.delete(key); // 역직렬화 실패 → 삭제 후 DB 조회
            }
        }

        // 캐시 미스 → DB 조회
        Optional<ProductDto> result = productRepository.findById(id).map(ProductDto::from);

        // TTL 지터 추가 후 캐시 저장
        int ttl = BASE_TTL + ThreadLocalRandom.current().nextInt(-360, 361);
        try {
            String value = result.map(dto -> {
                try { return objectMapper.writeValueAsString(dto); }
                catch (JsonProcessingException e) { throw new RuntimeException(e); }
            }).orElse(NULL_SENTINEL);

            redis.opsForValue().set(key, value, Duration.ofSeconds(
                result.isPresent() ? ttl : 30 // null은 30초만 캐시
            ));
        } catch (Exception e) {
            log.warn("Failed to cache product id={}", id, e);
            // 캐시 저장 실패는 무시 — DB 결과 반환
        }

        return result;
    }

    public void evict(Long id) {
        redis.delete(KEY_PREFIX + id);
    }
}
```

---

## 잘못된 구현 vs 올바른 구현

### 나쁜 예 1 — TTL 없이 캐시

```java
// 나쁜 예: TTL 미설정 → 메모리 무한 증가, 구버전 데이터 영구 잔류
redis.opsForValue().set("product:" + id, data);

// 올바른 예: 항상 TTL 포함
redis.opsForValue().set("product:" + id, data, Duration.ofHours(1));
```

### 나쁜 예 2 — 캐시 갱신(update) 방식으로 쓰기

```java
// 나쁜 예: DB 업데이트 + 캐시 갱신 → 레이스 컨디션 발생 가능
product.update(request);
productRepository.save(product);
redis.opsForValue().set("product:" + id, serialize(product)); // 위험

// 올바른 예: DB 업데이트 + 캐시 무효화
product.update(request);
productRepository.save(product);
redis.delete("product:" + id); // 다음 읽기에서 최신 DB 데이터 로드
```

### 나쁜 예 3 — 캐시 타임아웃 미처리

```java
// 나쁜 예: Redis 장애 시 전체 서비스 중단
public Product getProduct(Long id) {
    String cached = redis.opsForValue().get("product:" + id); // 예외 미처리
    // ...
}

// 올바른 예: 캐시 장애는 경고만 하고 DB로 폴백
public Product getProduct(Long id) {
    try {
        String cached = redis.opsForValue().get("product:" + id);
        if (cached != null) return deserialize(cached);
    } catch (RedisException e) {
        log.warn("Redis unavailable, falling back to DB. id={}", id);
    }
    return productRepository.findById(id).orElseThrow();
}
```

### 나쁜 예 4 — 쓰기 전에 캐시 삭제 (Delete Before Write)

```java
// 나쁜 예: 삭제 후 DB 업데이트 사이에 구버전이 다시 캐시될 수 있음
redis.delete("product:" + id);  // 삭제
// ← 여기서 다른 스레드가 DB 읽고 구버전 SET할 수 있음
productRepository.save(product); // DB 업데이트

// 올바른 예: DB 업데이트 먼저, 캐시 삭제 나중
productRepository.save(product); // DB 업데이트 먼저
redis.delete("product:" + id);  // 그 다음 캐시 삭제 (Write-Delete 순서)
```

---

## 인터뷰 답변 프레임

### Q. Cache-Aside 패턴을 설명해주세요.

> Cache-Aside는 애플리케이션이 캐시를 직접 관리하는 패턴입니다. 읽기 요청이 오면 먼저 Redis를 조회하고, 캐시 미스라면 DB에서 읽어 Redis에 저장한 뒤 반환합니다. 쓰기 시에는 DB를 먼저 업데이트하고 캐시를 삭제합니다. Spring에서는 `@Cacheable`과 `@CacheEvict`가 이 흐름을 자동으로 처리해줍니다.

### Q. 캐시 정합성 문제를 어떻게 다루나요?

> Cache-Aside에서 정합성 위험이 가장 높은 구간은 DB 업데이트 직후 캐시 삭제 전 사이입니다. 이를 줄이는 방법은 세 가지입니다. 첫째, 캐시 갱신(SET) 대신 캐시 무효화(DEL)를 사용합니다. 갱신 방식은 쓰기 레이스가 발생할 수 있습니다. 둘째, TTL을 짧게 설정해 최악의 경우에도 불일치 구간을 제한합니다. 셋째, 정합성이 절대적으로 중요한 데이터는 캐시 자체를 쓰지 않거나, DB 커밋 이후 이벤트로 캐시를 삭제합니다.

### Q. Cache Stampede를 경험하거나 방어해본 적 있나요?

> 인기 상품 상세 페이지에서 캐시 TTL이 만료되는 순간 DB 쿼리가 폭발하는 현상을 경험했습니다. 당시에는 두 가지를 적용했습니다. 하나는 TTL에 랜덤 지터를 추가해 동시 만료를 분산했고, 다른 하나는 L1으로 Caffeine 로컬 캐시를 30초 TTL로 앞에 배치해 Redis 조회 자체를 줄였습니다. 이후 트래픽이 더 커지면 분산 락 기반 갱신이나 XFetch 알고리즘을 검토할 것입니다.

### Q. Redis가 다운되면 어떻게 되나요?

> Redis 장애를 캐시 계층의 실패로 처리해야지, 서비스 전체 장애로 이어지면 안 됩니다. 모든 Redis 접근을 try-catch로 감싸고, 실패 시 DB 폴백 경로를 보장합니다. 나아가 Resilience4j의 Circuit Breaker를 적용해 Redis 연속 실패가 감지되면 즉시 우회 경로로 전환하고, 복구 후 자동으로 Redis를 다시 사용합니다. 단, DB 폴백 시 트래픽이 DB로 집중되므로 DB 커넥션 풀과 쿼리 성능 모니터링을 같이 준비해야 합니다.

### Q. Cache-Aside의 단점은 무엇인가요?

> 세 가지입니다. 첫째, **콜드 스타트 문제** — 서비스 재시작이나 신규 배포 직후에는 캐시가 비어 있어 모든 요청이 DB로 향합니다. 사전 워밍이나 Lazy Loading 허용 여부를 운영 계획에 포함해야 합니다. 둘째, **일시적 정합성 불일치** — DB와 캐시가 항상 동일하지 않을 수 있어, 강한 일관성이 필요한 데이터에는 부적합합니다. 셋째, **캐시 스탬피드** — 대량의 키가 동시에 만료되면 DB 부하가 급증합니다. TTL 지터와 락 전략으로 방어해야 합니다.

---

## 체크리스트

실무 배포 전 확인 항목:

- [ ] 모든 캐시 저장에 TTL이 설정되어 있는가
- [ ] TTL에 랜덤 지터를 추가해 동시 만료를 분산했는가
- [ ] 쓰기 순서가 DB 업데이트 → 캐시 삭제(DEL) 순서인가 (역순 아님)
- [ ] 캐시 미스 시 null sentinel을 저장해 Cache Penetration을 방어하는가
- [ ] Redis 타임아웃과 장애 시 DB 폴백 경로가 구현되어 있는가
- [ ] Circuit Breaker 또는 최소한 try-catch로 Redis 장애를 격리했는가
- [ ] 직렬화 형식이 JSON 등 버전 간 호환되는 방식인가
- [ ] 캐시 키에 버전 또는 네임스페이스가 포함되어 배포 시 충돌을 피하는가
- [ ] 인기 키에 대해 스탬피드 방어 전략(지터, 락, L1 캐시)을 적용했는가
- [ ] 로컬 캐시(L1) 사용 시 무효화 전략(Pub/Sub 또는 짧은 TTL)이 있는가
- [ ] 캐시 히트율을 `keyspace_hits / (keyspace_hits + keyspace_misses)`로 모니터링하는가
- [ ] evicted_keys가 0인지 주기적으로 확인하는가

---

## 관련 문서

- [Redis 기본](./basic.md) — 아키텍처, 자료구조, 사용 사례 전반
- [Redis 운영 가이드](./operations.md) — 메모리 관리, 모니터링 지표, 장애 대응
- [분산 락](./distributed-lock.md) — 스탬피드 방어에 활용되는 SET NX EX 패턴
