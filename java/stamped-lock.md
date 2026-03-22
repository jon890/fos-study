# Java StampedLock — 읽기 폭주에도 쓰기가 밀리지 않는 락

---

## 왜 StampedLock인가

`ReentrantReadWriteLock`(RRWL)은 읽기 많고 쓰기 드문 상황에 흔히 쓰는 도구다. 읽기 락은 동시에 여러 스레드가 잡을 수 있고, 쓰기 락은 모든 읽기가 끝날 때까지 기다린다.

문제는 **읽기가 계속 들어오면 쓰기가 영원히 기다릴 수 있다**는 점이다.

```
RRWL write lock 대기 타임라인:

[읽기1 실행 중........]
         [읽기2 실행 중........]
                  [읽기3 실행 중........]
    [쓰기 대기...............................? 언제 들어갈 수 있지?]
```

트래픽이 많은 서비스에서 로컬 캐시를 주기적으로 갱신해야 하는데, 그 사이에 읽기 요청이 끊이지 않으면 쓰기(갱신)가 계속 밀리는 현상이 생긴다.

`StampedLock`은 이 문제를 **낙관적 읽기(Optimistic Read)** 로 해결한다.

---

## 세 가지 모드

| 모드        | 메서드                | 특징                               |
| ----------- | --------------------- | ---------------------------------- |
| 쓰기 락     | `writeLock()`         | 배타적. 읽기/쓰기 모두 블로킹      |
| 읽기 락     | `readLock()`          | 공유적. 쓰기는 블로킹              |
| 낙관적 읽기 | `tryOptimisticRead()` | 락을 잡지 않음. 버전 스탬프만 확인 |

핵심은 낙관적 읽기다. **락을 잡지 않으므로 쓰기 락이 들어올 때 기다릴 필요가 없다.**

---

## 낙관적 읽기(Optimistic Read) 동작 원리

StampedLock 내부에는 버전 카운터가 있다. 쓰기가 일어날 때마다 이 카운터가 바뀐다.

```
초기 상태:   stamp = 256 (버전 카운터)

쓰기 발생:   stamp = 384 (카운터 변경)
```

낙관적 읽기는 다음 흐름으로 동작한다.

```
1. tryOptimisticRead()  → 현재 stamp 값을 읽어온다 (e.g. 256)
2. 데이터를 읽는다
3. validate(stamp)      → 현재 stamp가 여전히 256이면 성공, 바뀌었으면 실패
4. 실패 시 → 읽기 락을 잡고 다시 읽는다 (폴백)
```

```java
private final StampedLock lock = new StampedLock();
private Map<String, Object> cache = new HashMap<>();

public Object getFromCache(String key) {
    // 1. 낙관적 읽기 시도 — 락을 잡지 않음
    long stamp = lock.tryOptimisticRead();
    Object value = cache.get(key);

    // 2. 읽는 사이에 쓰기가 일어났는지 검증
    if (!lock.validate(stamp)) {
        // 3. 쓰기가 있었다면 읽기 락으로 폴백
        stamp = lock.readLock();
        try {
            value = cache.get(key);
        } finally {
            lock.unlockRead(stamp);
        }
    }

    return value;
}
```

---

## 캐시 갱신에 적용 — 실제 사용 사례

> 캐시 갱신 시 유저 요청을 막고, 로컬 캐시를 갱신한다.
> 이후 유저의 읽기 요청이 몰려들어도, 다음 갱신 요청은 막히지 않아야 한다.

이 요구사항이 StampedLock의 낙관적 읽기와 정확히 맞는 이유가 있다.

```
RRWL 상황 (문제):

[읽기 요청 폭주.................................]
[읽기 요청 폭주.................................]
  [갱신 대기............. 읽기가 안 끝나서 못 들어감 ...]

StampedLock + 낙관적 읽기 상황 (해결):

[낙관적 읽기 ──> validate 실패 ──> 폴백 읽기 락으로 재시도]
[낙관적 읽기 ──> validate 실패 ──> 폴백 읽기 락으로 재시도]
  [갱신 write lock 즉시 획득 ──> 캐시 교체 ──> 해제]
```

낙관적 읽기 중인 스레드는 **락을 잡고 있지 않다.** 쓰기 락 입장에서는 경쟁자가 없는 것과 같다. 갱신이 끝나면 낙관적 읽기 스레드들은 `validate()` 실패를 감지하고 폴백 경로로 재시도한다.

```java
@Component
public class LocalCacheManager {

    private final StampedLock lock = new StampedLock();
    private volatile Map<String, GameConfig> cache = Collections.emptyMap();

    // 유저 요청 — 낙관적 읽기
    public GameConfig get(String gameId) {
        long stamp = lock.tryOptimisticRead();
        Map<String, GameConfig> snapshot = cache;
        GameConfig value = snapshot.get(gameId);

        if (!lock.validate(stamp)) {
            // 갱신이 일어났다면 일반 읽기 락으로 재시도
            stamp = lock.readLock();
            try {
                value = cache.get(gameId);
            } finally {
                lock.unlockRead(stamp);
            }
        }

        return value;
    }

    // 백그라운드 갱신 — 쓰기 락
    public void refresh(Map<String, GameConfig> newCache) {
        long stamp = lock.writeLock();
        try {
            this.cache = newCache;
        } finally {
            lock.unlockWrite(stamp);
        }
    }
}
```

### 이게 맞는 용도인가?

**맞다.** 구체적으로 다음 세 조건이 모두 충족되기 때문이다.

1. **읽기 >> 쓰기** — 캐시 갱신은 드물고, 읽기는 매 요청마다 일어난다.
2. **쓰기 기아(writer starvation) 방지가 필요** — 읽기 폭주 중에도 갱신이 제때 들어가야 한다.
3. **읽기가 재시도를 감당할 수 있다** — 낙관적 읽기 실패 시 폴백 경로가 있고, 비용이 크지 않다.

RRWL로 같은 요구사항을 구현하면 읽기 트래픽이 많을수록 갱신이 지연된다. StampedLock의 낙관적 읽기는 이 구조적 문제를 해결하는 올바른 선택이다.

---

## ReentrantReadWriteLock과 비교

| 항목                 | ReentrantReadWriteLock      | StampedLock                    |
| -------------------- | --------------------------- | ------------------------------ |
| 읽기 중 쓰기 대기    | 현재 읽기 락 모두 해제 대기 | 낙관적 읽기면 즉시 획득 가능   |
| writer starvation    | fair=false 시 발생 가능     | 낙관적 읽기 구조상 없음        |
| 재진입(reentrant)    | 가능                        | **불가능**                     |
| Condition 사용       | 가능 (`newCondition()`)     | **불가능**                     |
| 읽기→쓰기 업그레이드 | 불가능                      | `tryConvertToWriteLock()` 가능 |
| 구현 복잡도          | 낮음                        | 높음 (validate 패턴 필수)      |

---

## tryConvertToWriteLock — 락 업그레이드

읽다가 쓰기가 필요해지는 경우, 읽기 락을 해제하고 다시 쓰기 락을 잡지 않아도 된다.

```java
public void updateIfExpired(String key) {
    long stamp = lock.readLock();
    try {
        if (!isExpired(cache.get(key))) return; // 갱신 불필요

        // 읽기 락을 쓰기 락으로 업그레이드 시도
        long writeStamp = lock.tryConvertToWriteLock(stamp);
        if (writeStamp != 0) {
            // 업그레이드 성공
            stamp = writeStamp;
            cache.put(key, loadFresh(key));
        } else {
            // 업그레이드 실패 → 읽기 락 해제 후 쓰기 락 획득
            lock.unlockRead(stamp);
            stamp = lock.writeLock();
            cache.put(key, loadFresh(key));
        }
    } finally {
        lock.unlock(stamp);
    }
}
```

---

## 주의사항

### 재진입 불가

같은 스레드에서 락을 중첩해서 잡으면 **데드락**이 발생한다.

```java
// 위험: 재진입 시 데드락
long s1 = lock.writeLock();
long s2 = lock.writeLock(); // 영원히 대기
```

### validate() 없이 읽으면 무의미

낙관적 읽기는 반드시 `validate()`로 검증해야 한다. 검증 없이 쓰면 일반 unsynchronized 읽기와 다를 바 없다.

```java
// 잘못된 패턴: validate 누락
long stamp = lock.tryOptimisticRead();
Object value = cache.get(key);
return value; // 쓰기와 동시에 읽힌 불완전한 데이터일 수 있음
```

### 낙관적 읽기 중 필드는 volatile 또는 직접 복사

낙관적 읽기는 메모리 베리어를 보장하지 않는다. 여러 필드를 읽는다면 지역 변수에 복사해서 사용하거나 `volatile`을 써야 한다.

```java
// 위험: x와 y가 서로 다른 버전에서 읽힐 수 있음
long stamp = lock.tryOptimisticRead();
int x = point.x;
int y = point.y; // x와 y 사이에 쓰기가 끼면 불일치
if (!lock.validate(stamp)) { ... }

// 안전: 복사 후 validate
long stamp = lock.tryOptimisticRead();
int x = point.x;
int y = point.y;
if (!lock.validate(stamp)) {
    stamp = lock.readLock();
    try { x = point.x; y = point.y; }
    finally { lock.unlockRead(stamp); }
}
// 이후 x, y 사용
```

### Condition 사용 불가

`await()`/`signal()` 패턴이 필요하면 RRWL을 써야 한다.

---

## 배운 것

**낙관적 읽기의 핵심은 "락을 잡지 않는다"는 것이다.** 락을 잡지 않기 때문에 쓰기가 기다릴 필요가 없다. 읽기 폭주 중에도 쓰기가 즉시 들어갈 수 있는 이유가 여기에 있다.

**validate() 패턴을 반드시 따라야 한다.** 낙관적 읽기는 데이터의 정합성을 보장하지 않는다. 읽은 후 `validate()`로 버전이 바뀌지 않았는지 확인하고, 바뀌었으면 폴백 경로에서 다시 읽어야 한다.

**재진입이 필요하면 RRWL을 써야 한다.** StampedLock은 재진입을 지원하지 않는다. 같은 스레드에서 중첩해서 락을 잡는 코드가 있으면 RRWL이 적합하다.

**읽기 >> 쓰기 구조에서만 이점이 있다.** 쓰기가 빈번하면 낙관적 읽기 실패율이 높아져 폴백 오버헤드가 커진다. 그 경우 RRWL이나 다른 동시성 구조가 낫다.

---

## 사용 기술

- Java 8+ (`java.util.concurrent.locks.StampedLock`, JDK 8 도입)
- 낙관적 읽기(Optimistic Read) / 읽기 락 / 쓰기 락
- `tryConvertToWriteLock()` — 락 업그레이드
