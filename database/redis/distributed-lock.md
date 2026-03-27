# Redis 분산 락 (Distributed Lock)

여러 서버/프로세스가 동일한 자원에 동시에 접근하는 것을 막아야 할 때 Redis를 분산 락 저장소로 사용한다. JVM 내부의 `synchronized`나 `ReentrantLock`은 단일 프로세스 안에서만 동작하므로, 다중 서버 환경에서는 외부 저장소 기반의 락이 필요하다.

---

## 왜 Redis인가?

- **원자적 SET NX EX**: 락 획득과 만료 시간 설정을 하나의 명령어로 처리
- **싱글 스레드**: Race condition 없이 락 획득 여부를 판단
- **자동 만료 (TTL)**: 락을 획득한 서버가 죽어도 락이 영원히 남지 않음

---

## 기본 구현: SET NX EX

```bash
# 락 획득 시도 (원자적)
# NX: 키가 없을 때만 SET (없으면 실패)
# EX 30: 30초 후 자동 만료
SET lock:order:1001 {owner_id} NX EX 30

# 반환값
# "OK"   → 락 획득 성공
# (nil)  → 이미 다른 프로세스가 락 보유 중

# 락 해제
DEL lock:order:1001
```

### 락 해제 시 소유자 검증 (필수)

단순 `DEL`은 위험하다. 락이 만료된 후 다른 서버가 락을 획득했는데, 원래 서버가 뒤늦게 `DEL`을 실행하면 다른 서버의 락을 해제해버린다.

```lua
-- Lua 스크립트로 소유자 확인 + 삭제를 원자적으로 처리
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

```java
// Spring Data Redis 적용
String lockKey = "lock:order:" + orderId;
String owner = UUID.randomUUID().toString();

// 락 획득
Boolean acquired = redisTemplate.opsForValue()
    .setIfAbsent(lockKey, owner, Duration.ofSeconds(30));

if (!Boolean.TRUE.equals(acquired)) {
    throw new LockAcquisitionException("락 획득 실패");
}

try {
    // 임계 영역 로직
    processOrder(orderId);
} finally {
    // 소유자 확인 후 해제 (Lua 스크립트)
    redisTemplate.execute(unlockScript,
        Collections.singletonList(lockKey), owner);
}
```

---

## Redisson: Pub/Sub 기반 락

직접 구현보다 **Redisson 라이브러리**를 쓰는 것이 실무에서 일반적이다. 스핀 락 대신 Pub/Sub으로 락 해제 신호를 대기하므로 Redis 부하가 적다.

```java
RLock lock = redissonClient.getLock("lock:order:" + orderId);

// 락 획득 시도 (최대 3초 대기, 락 유지 시간 30초)
boolean acquired = lock.tryLock(3, 30, TimeUnit.SECONDS);
if (!acquired) {
    throw new LockAcquisitionException("락 획득 실패");
}

try {
    processOrder(orderId);
} finally {
    lock.unlock();
}
```

### Redisson 내부 동작

```
서버 A: 락 획득 성공 → 임계 영역 실행
서버 B: 락 시도 → 실패 → "lock:order:1001" 채널 구독 후 대기
서버 A: 락 해제 → "lock:order:1001" 채널에 해제 신호 발행
서버 B: 신호 수신 → 즉시 재시도 → 락 획득
```

폴링(스핀 락)과 달리 Redis에 반복 요청을 보내지 않으므로 부하가 낮다.

### Watchdog (락 자동 갱신)

락 유지 시간을 명시하지 않으면 Redisson의 **Watchdog**이 10초마다 TTL을 갱신한다. 서버가 죽으면 Watchdog도 멈추므로 TTL이 만료되어 락이 자동 해제된다.

```java
// Watchdog 활성화: leaseTime 생략
lock.lock();  // 기본 30초, Watchdog이 자동 갱신

// Watchdog 비활성화: leaseTime 명시
lock.lock(10, TimeUnit.SECONDS);  // 정확히 10초 후 만료
```

---

## Redlock: 클러스터 환경의 분산 락

단일 Redis 인스턴스 기반 락은 Redis 서버가 죽으면 락이 사라진다. **Redlock 알고리즘**은 독립적인 Redis 노드 과반수에 락을 획득해야 유효로 처리한다.

```
Redis 노드 5개 (독립적, 클러스터 아님)

락 획득 시도:
  노드 1: SET 성공 ✅
  노드 2: SET 성공 ✅
  노드 3: SET 성공 ✅  ← 과반수(3/5) 달성
  노드 4: SET 실패 ❌
  노드 5: SET 성공 ✅

결과: 락 유효 (과반수 획득)
유효 시간: TTL - 락 획득 소요 시간
```

Redlock은 **Martin Kleppmann** 등의 분산 시스템 전문가들로부터 엣지 케이스에 대한 비판을 받기도 했다 (GC pause, 클락 드리프트 등). 결제/재고 등 **정확성이 생명인 시스템**에서는 Redlock 대신 ZooKeeper나 etcd 기반 락을 권장하는 의견도 있다.

---

## 사용 패턴별 선택 기준

| 상황 | 권장 방식 |
|------|---------|
| 단일 Redis, 간단한 락 | `SET NX EX` + Lua 해제 |
| 단일 Redis, 편의성 우선 | Redisson `RLock` |
| 멀티 Redis, 고가용성 필요 | Redlock (Redisson 지원) |
| 재고 차감처럼 단순 원자적 감소 | `DECR` / `DECRBY` (락 불필요) |

---

## 주의사항

### 락 만료 시간 설계

- **너무 짧음**: 임계 영역 작업이 끝나기 전에 락 만료 → 두 프로세스가 동시 진입
- **너무 긺**: 서버 장애 시 락이 오래 남아 서비스 지연

실제 작업 시간을 측정한 뒤 **2~3배 여유**를 두거나, Redisson Watchdog을 활용해 자동 갱신하는 것이 안전하다.

### 재진입(Reentrant) 락

같은 스레드가 락을 중첩 획득해야 하는 경우 단순 `SET NX`로는 불가능하다. Redisson의 `RLock`은 재진입 락을 지원한다.

```java
lock.lock();   // 1회 획득
lock.lock();   // 재진입 (같은 스레드) → 성공
lock.unlock(); // 1회 해제
lock.unlock(); // 완전 해제
```

### 락이 필요 없는 경우

락보다 **원자적 명령어**로 해결할 수 있는 경우가 많다.

```bash
DECR  inventory:product:9901   # 재고 1 차감 (원자적)
INCR  view:count:article:1     # 조회수 증가 (원자적)
SETNX unique:key value         # 중복 방지 (원자적)
```

---

## 관련 문서

- [Redis 기본](./basic.md) — Redis 싱글 스레드와 원자성 설명
- [Redis Lua 스크립트](./lua-script.md) — 원자적 복합 연산 구현 사례
