# [초안] Redis Cache-Aside 패턴: 실전 백엔드 관점의 설계와 함정

## 왜 이 주제가 중요한가

Cache-Aside(Lazy Loading)는 Redis를 도입할 때 가장 먼저 마주치는 기본 패턴이다. 이론상 "캐시에 먼저 물어보고 없으면 DB에서 읽어 캐시에 넣는다"는 단순한 흐름이지만, 실제 백엔드 시스템에서는 이 단순함이 다음과 같은 복합적 이슈로 이어진다.

- **캐시 일관성**: DB가 업데이트된 후 캐시가 여전히 과거 값을 반환하는 상황
- **동시성**: 캐시 미스가 다수의 요청에 동시에 발생할 때 DB에 과부하가 걸리는 Thundering Herd / Cache Stampede
- **장애 전파**: Redis가 느려지거나 다운될 때 애플리케이션 레이턴시가 같이 무너지는 현상
- **데이터 신선도**: TTL 설계와 무효화 전략의 trade-off
- **메모리 운용**: 캐시 미싱이 많은 키를 올리면 Redis 메모리가 포화되고 eviction 폭풍이 일어나는 문제

시니어 백엔드 면접에서 "Redis를 어떻게 쓰고 있나요?"라는 질문은 대부분 이 Cache-Aside의 실전 이해도를 묻는 것이다. 즉 개념 자체보다 "실패 경험과 trade-off 판단"이 합격 포인트다.

기존의 일반 Redis 개념 문서(`../redis-basics.md` 등)가 커맨드와 자료구조 중심이라면, 이 문서는 **패턴 적용과 실패 사례**에 초점을 맞춘 deep-dive 역할을 맡는다.

## 핵심 개념

Cache-Aside 패턴의 기본 흐름은 다음과 같다.

**Read path**

1. 애플리케이션이 캐시에 key로 조회한다.
2. Hit이면 그 값을 반환한다.
3. Miss면 DB에서 읽어 캐시에 쓰고, 값을 반환한다.

**Write path**

1. 애플리케이션이 DB를 먼저 업데이트한다.
2. 해당 키의 캐시를 무효화(삭제)한다.

여기서 두 가지 중요한 설계 판단이 숨어 있다.

### 1) DB → Cache 방향은 단방향이다

애플리케이션이 캐시와 DB를 모두 직접 관리한다. Redis는 "DB의 replica"가 아니라 **애플리케이션이 의식적으로 유지하는 보조 저장소**다. 그래서 캐시가 비어 있어도 시스템은 정상 동작해야 한다. Redis가 dump되어도 서비스가 느려질 뿐 죽어서는 안 된다는 전제가 깔려 있다.

### 2) Write 시 "업데이트"가 아니라 "삭제"가 기본이다

`DB 업데이트 → 캐시 삭제`가 `DB 업데이트 → 캐시 업데이트`보다 안전한 이유는 동시성이다. 두 트랜잭션이 거의 동시에 같은 키를 업데이트할 때, 네트워크/스케줄링에 따라 캐시에 "오래된 값이 나중에 쓰여" 영구적으로 stale해질 수 있다. 삭제 방식이면 다음 read에서 최신 값을 다시 로드하므로 드리프트가 자체 복구된다.

## 백엔드에서의 실전 적용

### 대상 선택 기준

모든 데이터를 캐시에 올리지 않는다. 다음 조건에서 효과가 크다.

- 읽기 비율이 쓰기보다 압도적으로 높다 (10:1 이상이 실전 기준)
- 한 번 읽힌 데이터가 여러 번 반복 조회된다
- 약간의 지연된 일관성(수 초~수 분)이 허용된다
- DB 쿼리 비용이 높다 (복잡한 JOIN, 집계, EXPLAIN상 index range + filesort 등)

반대로 트랜잭션성이 강한 데이터(결제, 재고 차감, 포인트 잔액)는 Cache-Aside만으로는 부족하며 분산락 또는 write-through, CDC 기반 패턴을 병행해야 한다.

### TTL 설계

TTL은 "일관성 예산"이다. 짧으면 DB 부하가 커지고, 길면 stale 데이터가 오래 남는다. 실무 감각은 다음과 같이 잡는다.

- 메타/코드성 데이터(카테고리, 브랜드 매핑): 수십 분 ~ 수 시간
- 사용자 프로필, 권한: 수 분
- 상품 상세/가격: 1~5분, 변경 이벤트 연동 시 즉시 무효화
- 검색 결과 / 목록: 수십 초 ~ 수 분, 정렬/필터 키 설계 중요

모든 키에 **지터(jitter)** 를 붙여 동시에 만료되지 않도록 한다. `ttl = base + random(0, base * 0.2)` 정도의 분산이면 만료 폭주를 크게 완화한다.

### 키 네이밍 규칙

키 네임스페이스는 배포 전에 확정해두는 게 좋다.

```
{service}:{entity}:{id}:{version}
# 예시
catalog:product:12345:v2
user:profile:7788:v1
order:summary:2026-04-21:user:7788:v1
```

`version` 필드를 미리 넣어두면 스키마 변경 시 기존 캐시를 일괄 폐기할 수 있다. 키 변경만으로 eviction을 자연스럽게 유도한다.

## Bad vs Improved 예제

아래 예제는 Spring Boot + Spring Data Redis + JPA 전제다. 설명을 위해 필요한 부분만 남겼다.

### Bad: 트랜잭션 안과 밖이 뒤섞인 캐시 무효화

```java
@Transactional
public Product updatePrice(Long productId, BigDecimal newPrice) {
    Product product = productRepository.findById(productId)
        .orElseThrow();
    product.changePrice(newPrice);

    redisTemplate.delete("catalog:product:" + productId + ":v2");

    return product;
}
```

문제점이 세 가지다.

1. **트랜잭션 커밋 전 캐시를 지운다.** 지운 직후 다른 요청이 캐시 미스로 DB를 읽으면, 아직 커밋되지 않은 옛날 값을 다시 캐시에 올린다. 결과적으로 "지웠는데도 stale"이 된다.
2. **Redis 장애 시 DB 트랜잭션도 실패한다.** `redisTemplate.delete`가 예외를 던지면 `@Transactional`이 롤백된다. 캐시는 보조 저장소인데 주 경로를 망가뜨리는 구조다.
3. **dirty read를 캐시로 전파할 수 있다.** 동일 트랜잭션 내 재조회가 캐시로 다시 떨어지면 격리 수준이 흐려진다.

### Improved: 커밋 이후에 무효화, 그리고 "지연 삭제 한 번 더"

```java
@Transactional
public Product updatePrice(Long productId, BigDecimal newPrice) {
    Product product = productRepository.findById(productId)
        .orElseThrow();
    product.changePrice(newPrice);

    String cacheKey = "catalog:product:" + productId + ":v2";

    TransactionSynchronizationManager.registerSynchronization(
        new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                safeDelete(cacheKey);
                scheduler.schedule(() -> safeDelete(cacheKey),
                                   Duration.ofMillis(500));
            }
        }
    );
    return product;
}

private void safeDelete(String key) {
    try {
        redisTemplate.delete(key);
    } catch (Exception e) {
        log.warn("cache delete failed key={}", key, e);
    }
}
```

핵심 개선점

- **`afterCommit`** 로 옮겨 DB 커밋 이후에만 캐시를 삭제한다.
- **두 번 삭제(Delayed Double Delete)** 로 커밋과 read 사이에 살짝 뒤늦게 도착한 stale write를 한 번 더 닦아낸다. 지연 시간은 보통 수백 ms ~ 2초 내에서 정한다.
- **예외를 삼킨다.** Redis 장애가 주 경로를 끌고 내려가지 않게 한다. 실패 로그/지표는 별도로 남긴다.
- **트랜잭션 분리.** DB는 주, 캐시는 보조라는 원칙이 코드에 드러난다.

### Bad: 단순 Cache Stampede

```java
public Product findById(Long id) {
    String key = "catalog:product:" + id + ":v2";
    Product cached = (Product) redisTemplate.opsForValue().get(key);
    if (cached != null) return cached;

    Product fromDb = productRepository.findById(id).orElseThrow();
    redisTemplate.opsForValue().set(key, fromDb, Duration.ofMinutes(5));
    return fromDb;
}
```

단일 요청 기준으로는 정상이지만, **인기 상품 키의 TTL이 만료되는 순간** 수천 개의 요청이 동시에 miss 처리되어 DB로 쏟아진다. 복구 직후 RT가 급등하고 DB CPU가 튄다.

### Improved: 싱글 플라이트 + 약간의 조기 갱신

```java
public Product findById(Long id) {
    String key = "catalog:product:" + id + ":v2";
    String lockKey = key + ":lock";

    Product cached = (Product) redisTemplate.opsForValue().get(key);
    if (cached != null) {
        maybeRefreshInBackground(id, key, cached);
        return cached;
    }

    Boolean locked = redisTemplate.opsForValue()
        .setIfAbsent(lockKey, "1", Duration.ofSeconds(3));

    if (Boolean.TRUE.equals(locked)) {
        try {
            Product fromDb = productRepository.findById(id).orElseThrow();
            long ttlMs = 5 * 60_000L + ThreadLocalRandom.current().nextLong(30_000);
            redisTemplate.opsForValue()
                .set(key, fromDb, Duration.ofMillis(ttlMs));
            return fromDb;
        } finally {
            redisTemplate.delete(lockKey);
        }
    }

    for (int i = 0; i < 10; i++) {
        sleep(50);
        Product again = (Product) redisTemplate.opsForValue().get(key);
        if (again != null) return again;
    }

    return productRepository.findById(id).orElseThrow();
}
```

이 코드는 다음을 해결한다.

- **단일 DB 조회 보장**: `SET NX`로 한 스레드만 DB를 읽고 나머지는 폴링으로 캐시를 기다린다.
- **지터 TTL**: 동시 만료를 분산한다.
- **백그라운드 재조회**: `maybeRefreshInBackground`는 TTL이 30% 이하 남았을 때 비동기로 미리 갱신하여 사용자 요청 경로에서의 만료를 줄인다(probabilistic early expiration의 단순 버전).
- **폴링 실패 시 폴백**: 락 대기가 너무 길면 그냥 DB로 떨어진다. "Redis 없어도 동작"의 원칙을 지킨다.

## 로컬 실습 환경

### Docker로 Redis + MySQL 띄우기

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7.2
    ports: ["6379:6379"]
    command: ["redis-server", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: shop
    ports: ["3306:3306"]
```

```bash
docker compose up -d
```

MySQL 8 스키마 예시:

```sql
CREATE TABLE product (
  id BIGINT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  price DECIMAL(12,2) NOT NULL,
  updated_at DATETIME(3) NOT NULL
);

INSERT INTO product (id, name, price, updated_at)
SELECT n, CONCAT('prod-', n), 1000 + n, NOW(3)
FROM (WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t WHERE n < 10000)
      SELECT n FROM t) x;
```

## 실행 가능한 실습

### 1) 기본 Cache-Aside 측정

`redis-cli` 로 수동 체험해본다.

```bash
redis-cli SET catalog:product:1:v2 '{"id":1,"price":1001}' EX 300
redis-cli GET catalog:product:1:v2
redis-cli TTL catalog:product:1:v2
redis-cli DEL catalog:product:1:v2
```

Spring Boot 앱에서 `findById(1L)`을 처음 호출하면 미스 + DB 쿼리 1회, 두 번째 호출부터 hit만 발생해야 한다. `p6spy`나 Hibernate SQL 로그로 쿼리 횟수를 확인한다.

### 2) Stampede 재현

```bash
redis-cli DEL catalog:product:1:v2
ab -n 500 -c 50 http://localhost:8080/products/1
# 또는
hey -n 500 -c 50 http://localhost:8080/products/1
```

락 없는 구현에서는 MySQL `SHOW PROCESSLIST`에 동일 쿼리가 동시에 수십 개 찍힌다. 개선 구현에서는 1회만 찍혀야 한다.

### 3) 일관성 깨짐 재현

```bash
# 터미널 A
while true; do curl -s http://localhost:8080/products/1; echo; done

# 터미널 B
curl -X PUT -d '{"price":9999}' http://localhost:8080/products/1/price
```

`afterCommit` 삭제가 없으면 B 직후에도 A에서 과거 가격이 수 초~TTL 길이만큼 관찰된다. Delayed Double Delete 적용 후 그 창이 거의 사라지는지 확인한다.

## 흔한 실수 패턴

- **캐시 장애 전파**: Redis 타임아웃이 API 타임아웃과 같게 설정되어 Redis 장애 시 전체 서비스가 느려진다. 클라이언트 타임아웃은 Redis가 훨씬 짧아야 한다 (예: 50~100ms).
- **큰 객체를 한 키에 통째로**: 상품 상세 + 리뷰 + 재고를 한 JSON으로 말아 넣으면 한 필드만 바뀌어도 전체가 stale 된다. 도메인 경계에 맞춰 키를 쪼갠다.
- **Negative cache 미구현**: 존재하지 않는 id에 대해 매번 DB를 친다. `NOT_FOUND` 표식을 짧은 TTL로 캐시해두면 Cache Penetration 공격을 완화한다.
- **TTL 0 또는 무제한**: 영구 키는 운영 중 디버깅이 어렵다. 기본적으로 TTL을 붙이고, 영속 키는 별도 네임스페이스로 분리한다.
- **캐시 워밍 없음**: 배포 직후 전 키 미스가 발생한다. 핵심 인기 키는 배포 후 배치로 미리 채운다.
- **버전 필드 부재**: 스키마 변경 시 기존 캐시를 지울 수 없어 강제 FLUSH를 하게 된다. 운영에서 금기 동작.

## 면접 답변 프레이밍

시니어 백엔드 관점에서 답할 때는 "패턴 설명"이 아니라 **"내가 겪은 실패 → 어떻게 풀었는지 → 다음엔 어떻게 하겠는지"** 흐름을 쓴다.

예시 답변 틀.

> "Cache-Aside를 쓰면서 가장 고생한 건 캐시와 DB의 일관성이었습니다. 초반엔 `@Transactional` 안에서 캐시를 삭제했는데, 커밋 전 삭제가 다른 요청의 miss 경로와 겹쳐 과거 값이 다시 캐시에 올라가는 현상이 있었습니다. `afterCommit`으로 옮기고, 지연 이중 삭제를 붙여서 드리프트를 크게 줄였습니다. 그 다음 문제는 만료 순간의 stampede였는데, `SET NX` 기반 싱글 플라이트와 TTL 지터, 만료 임박 시 비동기 재조회로 해결했습니다. Redis 장애 시 주 경로가 같이 죽지 않도록 클라이언트 타임아웃을 짧게 두고 예외를 삼키도록 했습니다. 지금 돌이켜보면 Cache-Aside는 '캐시를 지운다'가 아니라 '일관성 예산을 설계한다'에 가깝다고 봅니다."

이 답변에는 개념, 실패, 해결, 재설계 관점이 모두 들어간다. 여기에 면접관이 꼬리 질문으로 들어오는 포인트는 대체로 다음과 같다.

- "왜 write-through가 아니라 Cache-Aside였나?" → 장애 격리, 초기 구현 단순성, 일관성 요구 수준 설명
- "TTL 기준은 어떻게 잡았나?" → 읽기/쓰기 비율, 허용 지연, 캐시 메모리 크기와의 trade-off
- "캐시 서버가 완전히 죽으면?" → 장애 격리 설계, 서킷 브레이커, DB 직접 경로의 용량 검토
- "Redis 클러스터에서 키 분포가 치우치면?" → 해시 슬롯, hot key, 샤드 단위 부하 확인 방법

## 체크리스트

- [ ] 캐시 삭제는 DB 커밋 이후에만 수행되는가
- [ ] 지연 이중 삭제가 필요한 도메인에 적용되어 있는가
- [ ] 모든 키에 TTL이 설정되어 있는가, 그리고 지터가 있는가
- [ ] 키 네이밍에 version 필드가 포함되어 있는가
- [ ] 인기 키에 싱글 플라이트/분산락이 적용되어 있는가
- [ ] 존재하지 않는 리소스에 대한 negative cache가 있는가
- [ ] Redis 클라이언트 타임아웃이 API 타임아웃보다 충분히 짧은가
- [ ] Redis 장애 시 주 경로가 살아남는가(예외 격리, 회로차단기)
- [ ] 배포 직후 전면 miss를 막기 위한 워밍 절차가 있는가
- [ ] 큰 객체 대신 도메인 경계에 맞게 키가 분리되어 있는가
- [ ] 캐시 hit/miss/latency/error rate를 지표로 관측하고 있는가
- [ ] 캐시 무효화 실패 시 재시도/보정 로그가 남는가
