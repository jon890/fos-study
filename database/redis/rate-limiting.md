# Redis Rate Limiting (요청 제한)

특정 사용자/IP/API가 일정 시간 안에 너무 많은 요청을 보내는 것을 막는 기법이다. Redis는 원자적 명령어와 빠른 응답 속도 덕분에 Rate Limiting 구현에 적합하다.

---

## 1. 고정 윈도우 (Fixed Window)

가장 단순한 방식. 분 단위나 시간 단위 키를 만들고 `INCR`로 카운트한다.

```bash
# 키 형식: rate:{user_id}:{window}
# 현재 분(window)을 기준으로 카운트

INCR rate:user:1001:202603271430      # 현재 분 카운트 증가
EXPIRE rate:user:1001:202603271430 60 # 60초 후 자동 삭제

# 현재 카운트 확인
GET rate:user:1001:202603271430
```

```java
String key = "rate:user:" + userId + ":" + getCurrentMinute();
Long count = redisTemplate.opsForValue().increment(key);
if (count == 1) {
    redisTemplate.expire(key, Duration.ofSeconds(60));
}
if (count > 100) {  // 분당 100회 초과
    throw new RateLimitException("요청 한도 초과");
}
```

**한계: 경계 문제 (Boundary Problem)**

```
1:59분에 100회 요청 → 허용
2:00분에 100회 요청 → 허용
→ 실제로는 2초 안에 200회 요청이 통과
```

윈도우 경계 직전/직후에 두 배 요청이 허용되는 취약점이 있다.

---

## 2. 슬라이딩 윈도우 (Sliding Window) — Sorted Set

현재 시각 기준으로 과거 N초 이내의 요청만 카운트한다. 경계 문제가 없다.

```bash
# 요청마다 현재 타임스탬프를 score로 추가
ZADD rate:user:1001 {now_ms} {now_ms}

# 윈도우 밖(60초 이전) 데이터 제거
ZREMRANGEBYSCORE rate:user:1001 0 {now_ms - 60000}

# 현재 윈도우 내 요청 수
ZCARD rate:user:1001

# TTL 갱신 (키 자동 정리)
EXPIRE rate:user:1001 60
```

원자성을 보장하려면 위 명령어들을 **Lua 스크립트**로 묶는다.

```lua
-- sliding_window_rate_limit.lua
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])  -- 윈도우 크기 (ms)
local limit = tonumber(ARGV[3])   -- 허용 횟수

local window_start = now - window

-- 오래된 요청 제거
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

-- 현재 요청 수
local count = redis.call('ZCARD', key)

if count < limit then
    -- 요청 추가
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, math.ceil(window / 1000))
    return 1  -- 허용
else
    return 0  -- 거부
end
```

```java
String key = "rate:user:" + userId;
long now = System.currentTimeMillis();
long window = 60_000L;  // 60초
int limit = 100;

Long result = redisTemplate.execute(
    slidingWindowScript,
    Collections.singletonList(key),
    String.valueOf(now),
    String.valueOf(window),
    String.valueOf(limit)
);

if (result == 0L) {
    throw new RateLimitException("요청 한도 초과");
}
```

**고정 윈도우 vs 슬라이딩 윈도우:**

| 항목 | 고정 윈도우 | 슬라이딩 윈도우 |
|------|-----------|--------------|
| 구현 복잡도 | 낮음 | 중간 |
| 메모리 사용 | 낮음 (키 1개) | 높음 (요청마다 엔트리) |
| 경계 문제 | 있음 | 없음 |
| 정확도 | 낮음 | 높음 |

---

## 3. 토큰 버킷 (Token Bucket)

버킷에 일정 속도로 토큰이 채워지고, 요청마다 토큰을 소모한다. 순간적인 버스트를 허용하면서도 평균 처리량을 제한할 수 있다.

```
버킷 용량: 10 토큰
토큰 보충: 초당 2개

요청 1: 토큰 1 소모 → 버킷 9
요청 2: 토큰 1 소모 → 버킷 8
...
요청 10: 토큰 1 소모 → 버킷 0
요청 11: 토큰 없음 → 거부
5초 후: 토큰 10 보충 → 버킷 10
```

Redis로 구현할 때는 마지막 요청 시각과 남은 토큰 수를 Hash에 저장한다.

```lua
-- token_bucket.lua
local key = KEYS[1]
local capacity = tonumber(ARGV[1])    -- 버킷 최대 용량
local rate = tonumber(ARGV[2])        -- 초당 토큰 보충량
local now = tonumber(ARGV[3])         -- 현재 시각 (초)
local requested = tonumber(ARGV[4])   -- 요청 토큰 수 (보통 1)

local last_time = tonumber(redis.call('HGET', key, 'last_time') or now)
local tokens = tonumber(redis.call('HGET', key, 'tokens') or capacity)

-- 경과 시간만큼 토큰 보충
local elapsed = now - last_time
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_time', now)
    redis.call('EXPIRE', key, math.ceil(capacity / rate) + 1)
    return 1  -- 허용
else
    redis.call('HSET', key, 'last_time', now)
    return 0  -- 거부
end
```

---

## 4. 계층별 Rate Limiting

사용자 등급, API 엔드포인트, IP 등 여러 기준을 조합한다.

```bash
# 사용자별
rate:user:{userId}:{window}

# IP별 (미인증 요청)
rate:ip:{ip_address}:{window}

# API 엔드포인트별
rate:api:{endpoint}:{window}

# 복합: 특정 엔드포인트에 대한 사용자별 제한
rate:api:payment:user:{userId}:{window}
```

```java
// 여러 레이어를 순서대로 체크
checkRateLimit("rate:ip:" + ipAddress, 1000, 60);       // IP당 분 1000회
checkRateLimit("rate:user:" + userId, 100, 60);          // 사용자당 분 100회
checkRateLimit("rate:api:order:" + userId, 10, 60);      // 주문 API 분 10회
```

---

## Spring에서 AOP로 Rate Limiting 적용

```java
@Aspect
@Component
public class RateLimitAspect {

    @Around("@annotation(rateLimit)")
    public Object checkRateLimit(ProceedingJoinPoint pjp,
                                  RateLimit rateLimit) throws Throwable {
        String userId = SecurityContext.getCurrentUserId();
        String key = "rate:" + rateLimit.key() + ":" + userId + ":"
                     + getCurrentWindow(rateLimit.windowSeconds());

        Long count = redisTemplate.opsForValue().increment(key);
        if (count == 1) {
            redisTemplate.expire(key, Duration.ofSeconds(rateLimit.windowSeconds()));
        }
        if (count > rateLimit.limit()) {
            throw new RateLimitException("요청 한도 초과: " + count + "/" + rateLimit.limit());
        }
        return pjp.proceed();
    }
}

// 사용
@RateLimit(key = "order", limit = 10, windowSeconds = 60)
public Order createOrder(OrderRequest request) { ... }
```

---

## 주의사항

### 분산 환경에서의 원자성

`INCR`과 `EXPIRE`는 별개 명령어라 그 사이에 서버 장애가 나면 TTL 없는 키가 남는다. 안전하게 처리하려면:

```bash
# INCR 반환값이 1일 때만 EXPIRE 설정 (첫 요청에만)
# 이미 TTL이 있으면 EXPIRE를 다시 설정하지 않음
SET rate:user:1001:window 0 EX 60 NX  # 먼저 키+TTL 생성
INCR rate:user:1001:window            # 카운트 증가
```

또는 Lua 스크립트로 두 명령어를 원자적으로 묶는다.

### 메모리 사용량 관리

슬라이딩 윈도우 방식은 요청마다 Sorted Set 엔트리를 추가한다. 요청이 매우 많으면 메모리 사용량이 커질 수 있다. `ZREMRANGEBYSCORE`로 오래된 데이터를 즉시 제거하고, `EXPIRE`로 키 전체를 자동 삭제하도록 설정해야 한다.

### Rate Limit 응답 헤더

클라이언트에게 현재 한도 상태를 알려주는 것이 좋다.

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 43
X-RateLimit-Reset: 1711500060
Retry-After: 30   # 한도 초과 시
```

---

## 관련 문서

- [Redis 기본](./basic.md) — Sorted Set, String 자료구조
- [Redis Lua 스크립트](./lua-script.md) — 원자적 복합 연산 구현
- [분산 락](./distributed-lock.md) — 원자적 락 획득 패턴
