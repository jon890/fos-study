# Redis Hash와 Lua 스크립트로 잭팟 누적 구현하기

슬롯 게임의 잭팟 시스템을 들여다볼 기회가 생겼다. 구조를 파악하면서 "왜 여기서 Lua를 쓰지?"라는 질문이 생겼고, 그 이유를 이해하고 나서 기록으로 남긴다.

---

## 잭팟 시스템의 특성

프로그레시브 잭팟은 두 가지 사건이 교차하는 구조다.

- **누적**: 슬롯이 돌아갈 때마다 베팅 금액의 일부가 잭팟 풀에 쌓인다. 초당 수십~수백 건의 업데이트가 발생한다.
- **당첨**: 잭팟 조건이 충족되면, 누적된 금액 전체를 당첨자에게 지급하고 풀을 0으로 초기화한다.

이 두 사건이 동시에 일어날 수 있다는 점이 핵심이다. 누군가 당첨되는 순간에도 다른 사용자의 스핀이 계속 누적을 시도한다.

---

## Redis Hash 구조

잭팟 풀은 Redis Hash로 관리한다.

```
Key: jackpotPoolKey (슬롯 게임별 풀 식별자)
Field: TBI:{totalBetIndex}_JL:{jackpotLevel}
Value: 누적 금액 (String)
```

하나의 슬롯 게임에 잭팟 레벨이 여러 개(Mini, Major, Grand 등)이고, 베팅 금액 단계별로도 독립 관리되기 때문에 Hash의 field로 구분하는 구조다.

초기화 시 `HSETNX`로 필드를 생성한다. 이미 있으면 건드리지 않는다.

```java
hashOps.putIfAbsent(jackpotPoolKey, getJackpotHashKey(totalBetIndex, jackpotLevel), "0");
```

---

## 누적: HINCRBYFLOAT

스핀이 발생할 때마다 누적 금액을 더한다.

```java
hashOps.increment(jackpotPoolKey, getJackpotHashKey(totalBetIndex, jackpotLevel), accumulateAmount);
```

Spring Data Redis의 `increment`는 내부적으로 `HINCRBYFLOAT`를 사용한다. Redis는 싱글 스레드로 명령어를 처리하므로, 여러 사용자가 동시에 누적을 시도해도 race condition 없이 안전하게 더해진다.

---

## 당첨: Lua 스크립트가 필요한 이유

문제는 당첨 처리다. "누적된 금액을 읽고, 0으로 초기화하고, 읽은 금액을 반환"하는 세 단계를 한 번에 해야 한다.

Hash 필드에는 `GETDEL`이 없다. String 타입에는 있지만 Hash에는 없다. 그래서 단순하게 구현하면 두 명령어가 된다.

```
HGET jackpotPoolKey field    ← 금액 읽기
HSET jackpotPoolKey field 0  ← 0으로 초기화
```

이 두 명령어 사이에 다른 스핀의 누적이 끼어들면, 초기화 직전에 쌓인 금액이 유실된다. 읽었을 때와 0으로 쓸 때 사이의 틈이 문제다.

Lua 스크립트는 이 두 명령어를 하나의 원자적 단위로 만든다. Redis는 Lua 스크립트 실행 중에 다른 명령어를 끼워 넣지 않는다.

```lua
-- findAndDecrementJackpot.lua
local amount = redis.call('HGET', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[1], ARGV[1], 0)

if(amount == nil or amount == '') then
    return 0;
else
    return tonumber(amount);
end
```

Java 코드에서는 `RedisScript`로 등록해서 사용한다.

```java
@Bean(name = "findAndDecrementJackpot")
public RedisScript<Long> findAndDecrementJackpot() {
    final Resource script = new ClassPathResource("redis-scripts/findAndDecrementJackpot.lua");
    return RedisScript.of(script, Long.class);
}
```

실행은 `execute`로 호출한다.

```java
final Long accumulateAmount = getRedisTemplate().execute(
    findAndDecrementScript,
    Collections.singletonList(jackpotPoolKey),
    getJackpotHashKey(totalBetIndex, jackpotLevel)
);
```

`KEYS[1]`이 Hash의 key, `ARGV[1]`이 field가 된다.

---

## 시뮬레이터는 다르게 구현된다

시뮬레이터는 1억 스핀을 돌리는 용도라 Redis 연결 없이 인메모리에서 처리해야 한다. 동일한 `ProgressiveJackpotRepository` 인터페이스를 `AtomicReference<Double>` 기반으로 구현한 별도 클래스가 있다.

```java
// 누적
atomic.updateAndGet(current -> current + accumulateAmount);

// 당첨
final Double accumulateAmount = atomic.getAndSet(0.0);
```

Redis의 `HINCRBYFLOAT`와 Lua 스크립트가 하는 역할을 JVM 수준에서 `AtomicReference`의 CAS 연산으로 대체한다.

인터페이스가 같으니 서비스 레이어는 어떤 구현체가 들어오는지 모른다. `GameMode`로 구현체를 선택한다.

---

## Lua 스크립트의 원자성 한계

한 가지 주의할 점이 있다. Lua 스크립트의 원자성은 "다른 명령어가 끼어들지 못한다"는 격리성이지, RDBMS 트랜잭션처럼 all-or-nothing을 보장하지는 않는다.

스크립트 실행 도중 Redis 프로세스가 죽으면:

- `HGET`만 된 상태에서 죽었다면 데이터는 변경되지 않았다.
- `HSET`까지 됐는데 죽었다면, Redis 메모리에는 0으로 반영됐지만 AOF나 Replica에는 스크립트 전체가 기록되지 않을 수 있다.

롤백이 없다. 이 점을 인지하고 설계해야 한다. 잭팟 당첨 처리는 어떻게든 DB에도 기록되는 구조가 되어야 한다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- Spring Data Redis (`RedisTemplate`, `RedisScript`, `HashOperations`)
- Redis Hash (`HSETNX`, `HINCRBYFLOAT`, `HGET`, `HSET`)
- Lua Script (Redis 서버 사이드 원자적 실행)
