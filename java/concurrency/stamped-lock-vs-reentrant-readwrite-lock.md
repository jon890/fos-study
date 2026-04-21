# [초안] StampedLock vs ReentrantReadWriteLock: 백엔드 동시성 제어의 실전 선택

## 왜 이 주제가 중요한가

백엔드 서비스에서 동시성 제어는 성능과 정확성을 동시에 결정하는 핵심 축이다. 읽기와 쓰기가 섞이는 상황 — 예를 들어 인메모리 캐시, 설정 스냅샷, 메타데이터 테이블, 통계 집계 버퍼 — 에서 적절한 락 선택은 처리량을 수 배에서 수십 배까지 바꿀 수 있다. `synchronized`와 `ReentrantLock`은 직관적이지만 읽기 비중이 압도적인 워크로드에서는 낭비가 크다. 그래서 JDK 5부터 `ReentrantReadWriteLock`이, JDK 8부터 `StampedLock`이 도입되었다.

시니어 백엔드 면접에서 "읽기가 많은 캐시를 어떻게 보호하겠는가"라는 질문은 단골이다. 여기서 `ReentrantReadWriteLock`을 답하면 1차 통과, `StampedLock`의 낙관적 읽기(optimistic read)를 언급하면 한 단계 더 올라간다. 그리고 "그런데 StampedLock의 함정은 무엇이냐"까지 답할 수 있으면 실전 경험이 있는 사람으로 읽힌다. 이 문서는 그 세 레벨을 모두 채우는 것을 목표로 한다.

핵심 질문은 단순하다. 두 락의 내부 동작은 어떻게 다른가, 각각 언제 써야 하는가, 그리고 어떻게 하면 틀리지 않게 쓸 수 있는가.

## 핵심 개념 정리

### ReentrantReadWriteLock

`ReentrantReadWriteLock`은 읽기 락과 쓰기 락을 분리한 AQS(AbstractQueuedSynchronizer) 기반 락이다. 주요 성질은 다음과 같다.

- **읽기 락은 공유(shared)**, 쓰기 락은 배타(exclusive)다. 읽기 락은 여러 스레드가 동시에 점유할 수 있고, 쓰기 락은 한 번에 하나만 가능하다.
- **재진입(reentrant)** 가능하다. 같은 스레드가 이미 읽기/쓰기 락을 가진 상태에서 다시 획득해도 deadlock이 발생하지 않는다.
- **공정성(fair/unfair)** 모드를 지원한다. 기본값은 비공정 모드로, 처리량이 더 높지만 starvation 가능성이 존재한다.
- **쓰기 락 다운그레이드** 지원: 쓰기 락을 보유한 상태에서 읽기 락을 획득한 뒤 쓰기 락을 해제하면, 원자적으로 읽기 락으로 전환된다. 반대 방향(업그레이드)은 **지원하지 않는다**. 읽기 락을 잡은 채로 쓰기 락을 획득하려 하면 deadlock이 된다.

내부적으로 AQS의 32비트 상태 값을 상위 16비트(읽기 카운트)와 하위 16비트(쓰기 카운트)로 나눠 쓴다. 그래서 읽기 스레드 수는 이론적으로 65535개까지 제한된다.

### StampedLock

`StampedLock`은 JDK 8에 도입된 락이다. `ReentrantReadWriteLock`과 결정적으로 다른 점은 세 가지다.

- **재진입 불가**: 같은 스레드가 중첩해서 획득하면 deadlock이 될 수 있다.
- **Condition 지원 불가**: `newCondition()`이 없다.
- **낙관적 읽기(optimistic read) 지원**: 락 획득 없이 스탬프만 받아서 읽은 뒤, 그 사이에 쓰기가 발생했는지 검증(`validate`)한다. 쓰기가 끼어들지 않았다면 그 값은 유효하고, 끼어들었다면 비관적 읽기 락으로 재시도한다.

모든 `lock`/`unlock` API는 `long` 타입 **스탬프**를 주고받는다. 이 스탬프는 "어떤 모드로 어느 버전에 획득했는가"를 담은 값이다. 해제 시 반드시 획득 시 받은 스탬프를 `unlockRead(stamp)` / `unlockWrite(stamp)` 형태로 넘겨야 한다.

낙관적 읽기의 의미는 중요하다. 일반적인 읽기 락은 공유라고 해도 **CAS로 AQS 상태를 증가시킨다**. 즉 읽기 스레드끼리 캐시 라인 경합이 발생한다. 반면 `tryOptimisticRead`는 현재 버전 스탬프만 읽어서 반환하고, 아무 상태도 변경하지 않는다. 읽기 스레드들 사이에 경합이 0에 수렴한다. 대신 쓰기가 발생하면 그 읽기는 무효화된다.

### 본질적 차이의 한 줄 요약

`ReentrantReadWriteLock`은 **독자끼리는 공유하지만 상태는 건드린다**. `StampedLock`의 낙관적 읽기는 **상태를 아예 건드리지 않고, 나중에 충돌이 없었는지 검증한다**. 전자는 정확성이 단순하지만 읽기 스레드가 많아질수록 확장성에 한계가 온다. 후자는 낮은 충돌 시 극도로 빠르지만 프로그래밍 모델이 까다롭다.

## 실무 백엔드에서 어디에 쓰이는가

### 캐시, 설정 스냅샷, 메타데이터

Spring Boot 애플리케이션이 기동 시 로드하는 기능 플래그 맵, 환율 테이블, 상품 카테고리 트리 같은 데이터는 읽기 비율이 99%에 달한다. 10분에 한 번 리프레시되고, 서비스 내 수천 건의 요청이 매초 읽는다. 이런 자료에는 `StampedLock`의 낙관적 읽기가 거의 이상적이다.

### 주기적 통계 집계

1초마다 갱신되는 슬라이딩 윈도우 카운터, 최근 N건의 응답 시간 평균, 서킷 브레이커 상태 등은 쓰기 주기는 일정하지만 읽기가 자주 일어난다. 여기서도 낙관적 읽기 + 비관적 읽기 fallback 조합이 유효하다.

### 복잡한 자료 구조 (트리, 그래프)

읽기 경로가 길어서 일관된 스냅샷 시점이 필요한 자료 구조에는 `StampedLock`이 오히려 불리할 수 있다. 낙관적 읽기 도중 쓰기가 들어오면 전체를 처음부터 다시 읽어야 하는데, 경로가 길면 재시도 비용이 크다. 이 경우 `ReentrantReadWriteLock` 또는 copy-on-write 자료 구조를 검토한다.

### 재진입이 필요한 경로

서비스 레이어에서 동일 락을 재귀적으로 잡아야 하는 설계라면 `StampedLock`은 선택지에서 제외된다. 가장 흔한 실수가 이 지점에서 나온다.

## 나쁜 예와 개선된 예

### 예제 1 — 단순 읽기 많음, ReentrantReadWriteLock도 비효율인 경우

**Bad: synchronized로 읽기까지 직렬화**

```java
public class RateCache {
    private final Map<String, BigDecimal> rates = new HashMap<>();

    public synchronized BigDecimal get(String code) {
        return rates.get(code);
    }

    public synchronized void put(String code, BigDecimal value) {
        rates.put(code, value);
    }
}
```

읽기 요청이 초당 수만 건 들어오면 이 메서드가 핫스팟이 된다. 모든 스레드가 동일 모니터에 직렬화된다.

**Better: ReentrantReadWriteLock**

```java
public class RateCache {
    private final Map<String, BigDecimal> rates = new HashMap<>();
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

    public BigDecimal get(String code) {
        lock.readLock().lock();
        try {
            return rates.get(code);
        } finally {
            lock.readLock().unlock();
        }
    }

    public void put(String code, BigDecimal value) {
        lock.writeLock().lock();
        try {
            rates.put(code, value);
        } finally {
            lock.writeLock().unlock();
        }
    }
}
```

읽기끼리는 공유된다. 그러나 읽기 락 획득 시 내부적으로 CAS가 일어나므로, 초당 수십만 건의 읽기에서는 여전히 캐시 라인 경합이 관측된다.

**Best (적합한 워크로드에서): StampedLock with Optimistic Read**

```java
public class RateCache {
    private final Map<String, BigDecimal> rates = new HashMap<>();
    private final StampedLock lock = new StampedLock();

    public BigDecimal get(String code) {
        long stamp = lock.tryOptimisticRead();
        BigDecimal value = rates.get(code);
        if (!lock.validate(stamp)) {
            stamp = lock.readLock();
            try {
                value = rates.get(code);
            } finally {
                lock.unlockRead(stamp);
            }
        }
        return value;
    }

    public void put(String code, BigDecimal value) {
        long stamp = lock.writeLock();
        try {
            rates.put(code, value);
        } finally {
            lock.unlockWrite(stamp);
        }
    }
}
```

여기서 반드시 주의해야 할 점: 낙관적 읽기 구간에서 읽는 자료 구조가 **쓰는 도중에도 JVM 관점에서 안전해야** 한다. 위 예제는 실제로는 **위험하다**. `HashMap.get`은 재해시(rehash) 도중에 무한 루프에 빠지거나 `NullPointerException`이 터질 수 있다. 낙관적 읽기는 "충돌이 있었는지 사후 검증"할 뿐이므로, 읽는 동안 자료 구조가 일관되지 않아도 검증 전에는 절대 `throw`가 일어나지 않도록 방어해야 한다.

### 예제 2 — 낙관적 읽기의 올바른 패턴

```java
public class Point {
    private double x, y;
    private final StampedLock lock = new StampedLock();

    public void move(double dx, double dy) {
        long stamp = lock.writeLock();
        try {
            x += dx;
            y += dy;
        } finally {
            lock.unlockWrite(stamp);
        }
    }

    public double distanceFromOrigin() {
        long stamp = lock.tryOptimisticRead();
        double currentX = x;
        double currentY = y;
        if (!lock.validate(stamp)) {
            stamp = lock.readLock();
            try {
                currentX = x;
                currentY = y;
            } finally {
                lock.unlockRead(stamp);
            }
        }
        return Math.sqrt(currentX * currentX + currentY * currentY);
    }
}
```

로컬 변수로 값을 **복사한 뒤**, validate에 성공하면 그 로컬 값으로 계산한다. 이 패턴은 JDK `StampedLock` 공식 javadoc에 나오는 권장 패턴이다. 포인트는 두 가지다.

1. `validate` 전에는 읽은 값이 **불일치(inconsistent)** 할 수 있다고 가정한다.
2. `validate` 이후에야 계산에 사용한다. 실패 시 비관적 읽기 락으로 fallback한다.

### 예제 3 — 재진입 함정

```java
public class Counter {
    private long value;
    private final StampedLock lock = new StampedLock();

    public void incrementTwice() {
        long outer = lock.writeLock();
        try {
            value++;
            incrementOnce();
        } finally {
            lock.unlockWrite(outer);
        }
    }

    public void incrementOnce() {
        long inner = lock.writeLock();
        try {
            value++;
        } finally {
            lock.unlockWrite(inner);
        }
    }
}
```

`incrementTwice()` 안에서 `incrementOnce()`를 호출하는 순간 **deadlock**이다. `StampedLock`은 재진입을 지원하지 않는다. 같은 스레드라도 내부 락을 다시 요구하면 자기 자신을 기다린다.

`ReentrantReadWriteLock`에서는 동일한 코드가 정상 동작한다. 재진입이 필요한 설계 전에 이 제약을 의식적으로 확인해야 한다.

### 예제 4 — 업그레이드 실패 사례

```java
// ReentrantReadWriteLock 에서 흔히 하는 실수
public void maybeRefresh(String key) {
    rw.readLock().lock();
    try {
        if (!cache.containsKey(key)) {
            // 여기서 writeLock을 잡으면 deadlock
            rw.writeLock().lock(); // 절대 호출되지 않음
            // ...
        }
    } finally {
        rw.readLock().unlock();
    }
}
```

읽기 락을 가진 상태에서 쓰기 락을 획득할 수 없다. 다른 모든 읽기 락이 풀려야 쓰기 락을 획득할 수 있는데, 자기 자신이 읽기 락을 잡고 있으므로 영원히 풀리지 않는다.

**개선**

```java
public void maybeRefresh(String key) {
    rw.readLock().lock();
    boolean needsWrite = !cache.containsKey(key);
    rw.readLock().unlock();

    if (needsWrite) {
        rw.writeLock().lock();
        try {
            cache.computeIfAbsent(key, this::loadFromDb);
        } finally {
            rw.writeLock().unlock();
        }
    }
}
```

`StampedLock`에서는 `tryConvertToWriteLock(stamp)` API가 있어서 조금 더 유연하지만, 성공/실패를 반드시 확인해야 하므로 작성 난이도는 여전히 높다.

## 로컬 실습 환경

### 준비

JDK 17 이상, Gradle 또는 Maven. JMH(Java Microbenchmark Harness)까지 있으면 이상적이지만, 처음에는 `System.nanoTime`과 `ExecutorService`로 충분하다.

```
mkdir -p lock-lab/src/main/java/locklab
cd lock-lab
```

`build.gradle.kts` 최소 구성:

```kotlin
plugins {
    java
    application
}

repositories { mavenCentral() }

java {
    toolchain { languageVersion.set(JavaLanguageVersion.of(17)) }
}

application {
    mainClass.set("locklab.Main")
}
```

### 실행 가능한 벤치 예제

```java
package locklab;

import java.util.concurrent.*;
import java.util.concurrent.locks.*;

public class Main {
    static final int READERS = 16;
    static final int WRITERS = 1;
    static final long DURATION_MS = 3_000;

    public static void main(String[] args) throws Exception {
        System.out.println("ReentrantReadWriteLock: " + bench(new RwCounter()) + " ops");
        System.out.println("StampedLock(optimistic): " + bench(new StampedCounter()) + " ops");
    }

    static long bench(Counter counter) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(READERS + WRITERS);
        long end = System.currentTimeMillis() + DURATION_MS;
        CountDownLatch start = new CountDownLatch(1);
        long[] readOps = new long[READERS];

        for (int i = 0; i < READERS; i++) {
            final int idx = i;
            pool.submit(() -> {
                start.await();
                long count = 0;
                while (System.currentTimeMillis() < end) {
                    counter.read();
                    count++;
                }
                readOps[idx] = count;
                return null;
            });
        }
        for (int i = 0; i < WRITERS; i++) {
            pool.submit(() -> {
                start.await();
                while (System.currentTimeMillis() < end) {
                    counter.write();
                    Thread.sleep(1);
                }
                return null;
            });
        }

        start.countDown();
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);

        long total = 0;
        for (long v : readOps) total += v;
        return total;
    }

    interface Counter { long read(); void write(); }

    static class RwCounter implements Counter {
        private long v;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
        public long read() {
            lock.readLock().lock();
            try { return v; } finally { lock.readLock().unlock(); }
        }
        public void write() {
            lock.writeLock().lock();
            try { v++; } finally { lock.writeLock().unlock(); }
        }
    }

    static class StampedCounter implements Counter {
        private long v;
        private final StampedLock lock = new StampedLock();
        public long read() {
            long stamp = lock.tryOptimisticRead();
            long local = v;
            if (!lock.validate(stamp)) {
                stamp = lock.readLock();
                try { local = v; } finally { lock.unlockRead(stamp); }
            }
            return local;
        }
        public void write() {
            long stamp = lock.writeLock();
            try { v++; } finally { lock.unlockWrite(stamp); }
        }
    }
}
```

실행해 보면 읽기 스레드 수가 늘어날수록 `StampedLock` 쪽 처리량이 훨씬 빠르게 벌어지는 것을 확인할 수 있다. CPU 코어 수와 경합 정도에 따라 다르지만, 16코어 환경에서 `StampedLock`이 3~8배 처리량을 보이는 경우가 흔하다.

### 측정 포인트

- 읽기 스레드 수: 2, 4, 8, 16, 32
- 쓰기 비율: 0%, 1%, 10%, 50%
- 쓰기 비율이 10%를 넘으면 낙관적 읽기의 이점이 급격히 줄어든다는 것을 직접 눈으로 확인하는 것이 중요하다.

## 면접 답변 프레이밍

**질문: 읽기가 압도적으로 많은 캐시를 보호해야 합니다. 어떻게 설계하시겠습니까?**

> 먼저 읽기/쓰기 비율, 재진입 필요성, 데이터 구조의 복잡도를 확인합니다. 읽기 비율이 90% 이상이고 쓰기가 짧고 드물며, 내부 자료 구조가 단순하다면 `StampedLock`의 낙관적 읽기를 1순위로 고려합니다. `tryOptimisticRead` → 로컬 복사 → `validate` → 실패 시 `readLock` fallback 패턴을 씁니다. 다만 `StampedLock`은 재진입이 불가능하고 `Condition`이 없으므로, 서비스 레이어에서 락이 재진입 경로에 놓이는지, 조건 변수가 필요한지를 먼저 확인합니다. 그 제약을 받아들일 수 없으면 `ReentrantReadWriteLock`으로 내려가고, 쓰기 빈도가 꽤 높아지면 `ConcurrentHashMap`이나 copy-on-write 스냅샷 전략으로 아예 락을 제거하는 방향을 검토합니다.

**질문: StampedLock의 함정은 무엇인가요?**

> 세 가지가 있습니다. 첫째, 재진입 불가입니다. 같은 스레드가 중첩해 획득하면 deadlock이 됩니다. 둘째, 낙관적 읽기 구간에서 읽는 자료 구조가 쓰기 도중에도 런타임 예외를 던지지 않아야 합니다. `HashMap`처럼 재해시 중 NPE가 터질 수 있는 구조는 위험합니다. 셋째, 스탬프를 잘못 넘기면 `IllegalMonitorStateException`이 납니다. 낙관적 스탬프를 `unlockRead`에 넘기는 실수가 전형적입니다.

**질문: ReentrantReadWriteLock의 다운그레이드는 어떻게 쓰나요?**

> 쓰기 락을 보유한 상태에서 먼저 읽기 락을 획득하고, 그 다음 쓰기 락을 해제합니다. 이 순서로 하면 쓰기 작업이 끝난 직후 자신이 수정한 값을 일관되게 읽을 수 있고, 다른 쓰기 스레드가 끼어들기 전에 읽기 권한으로 전환됩니다. 반대로 업그레이드(읽기 → 쓰기)는 지원되지 않아 항상 deadlock이므로, 설계 단계에서 분기를 명확히 해야 합니다.

**꼬리 질문 대비 포인트**

- `ReentrantReadWriteLock` 공정 모드는 언제 쓰는가 → writer starvation 방지.
- `StampedLock` 대신 `AtomicReference` + copy-on-write는 언제가 나은가 → 자료 구조 전체 교체 비용이 낮고 쓰기가 흔치 않은 경우.
- 분산 환경이라면 → 이런 JVM 내부 락은 의미 없음. Redis Redlock, DB row lock, 낙관적 버전 컬럼 등으로 이동.

## 체크리스트

- [ ] 재진입이 필요한 호출 경로인가? 그렇다면 `StampedLock`은 제외한다.
- [ ] `Condition`(대기/통지)이 필요한가? 그렇다면 `StampedLock`은 제외한다.
- [ ] 쓰기 비율이 10% 이상인가? 그렇다면 낙관적 읽기의 이점이 줄어든다. 측정 후 결정한다.
- [ ] 낙관적 읽기 구간에서 읽는 자료 구조가 중간 상태에서도 예외를 던지지 않는가?
- [ ] 스탬프를 확실히 finally 블록에서 해제하고 있는가?
- [ ] 업그레이드(읽기 → 쓰기)를 시도하는 코드 경로가 없는가?
- [ ] 쓰기 락 다운그레이드가 필요한가? `ReentrantReadWriteLock`에서 권장 순서를 지켰는가?
- [ ] JMH 또는 자체 벤치로 실제 워크로드에서 개선을 확인했는가? 추정만으로 채택하지 않는다.
- [ ] 단일 JVM 범위를 벗어나는 동시성 요구사항이 생겼을 때, 분산 락/DB 락으로 이전할 설계 여지가 있는가?
