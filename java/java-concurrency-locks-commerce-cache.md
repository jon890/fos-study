# [초안] Java 동시성 락 정리 — 커머스 메뉴/프로모션 정책 캐시 갱신 관점

## 왜 지금 이 주제인가

커머스 백엔드에서 메뉴, 프로모션, 매장 운영 정책 같은 "거의 안 바뀌지만 모든 요청이 읽는" 데이터는 거의 예외 없이 메모리 캐시로 들어간다. 트래픽이 큰 시간대에 이 캐시를 어떻게 갱신할지가 곧 시스템의 안정성을 결정한다. 갱신 순간에 락을 잘못 잡으면 모든 조회 스레드가 멈추고, 락을 너무 느슨하게 풀면 절반은 옛 데이터, 절반은 새 데이터를 보는 일관성 사고가 난다.

CJ푸드빌 같은 외식 커머스 환경에서는 점심 직전과 저녁 직전 트래픽 피크 직전에 운영자가 메뉴 가격, 품절 여부, 할인율을 바꾸는 패턴이 흔하다. "변경은 분당 수 건, 조회는 초당 수천 건"이라는 비대칭이 핵심이다. 이때 단순 `synchronized`로 막아 버리면 운영자 1명의 메뉴 갱신이 점심 피크의 모든 조회를 줄 세우는 사고가 난다. 시니어 백엔드 면접에서 동시성 락 질문이 들어오면 대부분의 답이 `synchronized` vs `ReentrantLock`까지로 끝나는데, 실제 차별점은 "왜 read-heavy 캐시에서는 RWLock이 모자라고 StampedLock의 optimistic read가 필요한가"를 설명할 수 있느냐다.

## 핵심 개념 정리

### thread safety의 두 축

가장 먼저 분리해야 할 두 가지 축이 있다.

- **가시성(visibility)**: 한 스레드가 쓴 값이 다른 스레드에게 보이는가. `volatile`, 동기화 블록, `final` 필드 초기화 후 publish 같은 수단이 해결한다.
- **원자성(atomicity)**: "읽고 비교하고 쓰는" 일련의 연산이 다른 스레드의 개입 없이 한 덩어리로 끝나는가. `synchronized`, 명시적 Lock, `Atomic*` CAS 연산이 해결한다.

`volatile`은 단일 변수의 가시성만 보장하고 복합 연산의 원자성은 보장하지 않는다. 캐시 객체 전체를 통째로 갈아 끼우는 패턴에서는 `volatile` 하나로 충분할 수 있지만, "맵 안의 한 항목만 수정"에는 절대 부족하다. 이 구분이 면접에서 가장 자주 헷갈리는 지점이다.

### synchronized

JVM 내장 모니터 락. 진입/이탈이 자동이고 구현이 간단하지만, 다음 한계가 있다.

- 읽기/쓰기를 구분하지 않는다. 100개의 스레드가 동시에 같은 캐시를 읽기만 해도 줄을 선다.
- 인터럽트가 어렵고, tryLock 같은 비차단 시도가 없다.
- 락 획득 대기 시간이 길어지면 throughput이 급격히 떨어진다.

상태가 거의 안 바뀌고 호출 빈도가 낮은 영역(예: 초기화 가드, 카운터 증가)에 한정해서 쓴다.

### ReentrantLock

`synchronized`의 기능 확장판. tryLock, 인터럽트 가능 lockInterruptibly, 공정성 옵션, 다중 Condition을 지원한다. 그러나 read와 write를 여전히 구분하지 않으므로 read-heavy 캐시 갱신용으로는 여전히 부적합하다.

### ReentrantReadWriteLock

읽기 락과 쓰기 락을 분리한다.

- 읽기 락은 여러 스레드가 동시에 보유 가능하다.
- 쓰기 락은 단독 보유, 진입 시 모든 활성 read와 write가 끝나기를 기다린다.
- write 보유 중이면 read도 막힌다.

`HashMap` 같은 공유 자료구조를 캐시로 두고 갱신할 때 가장 직관적인 도구다. 다만 읽기 락도 락이다. 매 read마다 락 객체의 내부 카운터를 CAS로 증가시키고 메모리 배리어가 발생한다. 초당 수만 read 환경에서는 이 비용이 무시 못 할 수준이 된다. 그리고 writer starvation 문제도 있다 — 끊임없이 읽기가 들어오면 쓰기가 영영 잡히지 않을 수 있어, 공정성 옵션을 켜면 throughput이 또 떨어진다.

### StampedLock과 optimistic read

Java 8에서 도입된 StampedLock의 장점은 **optimistic read**다.

- `tryOptimisticRead()`는 락을 잡지 않고 stamp(버전 번호)만 받는다. 비용이 거의 0에 가깝다.
- 읽고 난 뒤 `validate(stamp)`로 그 사이에 쓰기가 있었는지 검증한다.
- 검증 실패 시에만 정식 read lock을 잡고 다시 읽는다.

이 패턴은 "쓰기는 드물고 읽기는 빈번하다"라는 캐시 갱신 시나리오와 정확히 맞는다. write가 안 들어오는 99.9%의 경우, read는 락 없이 끝난다. write가 끼어들었을 때만 fall back한다.

단, StampedLock은 **재진입을 지원하지 않고**, **Condition도 없으며**, optimistic read 구간에서는 **읽는 데이터가 일관된 상태가 아닐 수 있으므로** 읽은 값을 일단 지역 변수로 복사한 뒤 validate로 검증해야 한다. 이 사용 규칙을 모르고 쓰면 오히려 위험하다.

### volatile + AtomicReference: 통째 교체 패턴

캐시가 정적이고 일관된 스냅샷 단위로 갱신된다면, 락을 안 쓰고 끝낼 수도 있다.

- 캐시 객체 자체를 `volatile` 또는 `AtomicReference`로 들고 있다가, 갱신 시 새로운 불변 캐시 객체를 통째로 만들어서 참조만 바꿔치기(swap)한다.
- 조회 스레드는 락 없이 참조를 한 번 읽고, 그 시점의 스냅샷을 끝까지 사용한다.

이 패턴은 메뉴 캐시, 프로모션 정책 캐시처럼 "1\~5분에 한 번 전체를 다시 빌드해도 되는" 경우에 가장 깔끔하다. 단점은 부분 갱신이 안 된다는 것 — 메뉴 한 줄을 바꾸려고 전체 캐시를 다시 만든다. 그러나 외식 커머스의 마스터 데이터는 보통 수백\~수천 건 수준이라 전체 재빌드 비용이 크지 않다.

## 백엔드 실전 사용 — 메뉴/프로모션 캐시 갱신

후보자가 이전에 다뤘던 "슬롯 머신용 정적 데이터 캐시"는 사실상 같은 구조의 문제다. 게임 슬롯의 심볼 테이블/배당률은 운영자가 가끔 바꾸고, 게임 스레드는 매 스핀마다 읽는다. 외식 커머스로 옮기면 다음으로 매핑된다.

| 게임 도메인 | 커머스 도메인 |
| --- | --- |
| 슬롯 심볼 테이블 | 매장별 메뉴 마스터 |
| 배당률 테이블 | 프로모션/할인율 정책 |
| 운영자 콘솔의 정적 데이터 변경 | 점주/본사의 메뉴/가격/품절 변경 |
| 매 스핀의 배당 계산 | 매 주문의 가격 계산 |

공통 패턴은 "운영 변경은 분 단위, 조회는 초 단위, 일관된 스냅샷이 필요" 라는 것이다. 따라서 채택할 수 있는 갱신 모델은 보통 다음 셋 중 하나다.

1. **불변 객체 + AtomicReference swap** — 점심/저녁 피크 직전 일괄 적용 가능, 부분 변경은 전체 재빌드.
2. **StampedLock optimistic read** — 부분 변경이 잦고, 캐시 자료구조가 큰 경우.
3. **ReentrantReadWriteLock** — 단순함을 우선시하고 read 빈도가 그렇게 극단적이지 않을 때.

## bad vs improved 예제

### 예제 1 — synchronized로 메뉴 캐시를 막은 안티패턴

```java
public class BadMenuCache {
    private final Map<Long, Menu> menus = new HashMap<>();

    public synchronized Menu get(long id) {
        return menus.get(id);
    }

    public synchronized void reload(List<Menu> latest) {
        menus.clear();
        for (Menu m : latest) menus.put(m.getId(), m);
    }
}
```

문제점:

- 읽기끼리도 직렬화된다. 점심 피크에 초당 수천 건이 한 줄로 줄을 선다.
- reload 중에는 `clear()` 직후의 빈 맵을 다른 스레드가 보지 못하긴 하지만, 어쨌든 모든 read가 멈춘다.
- 메뉴 1건 변경에도 전체 reload를 호출하면 전체 트래픽이 일시 정지한다.

### 개선 1 — AtomicReference로 통째 교체

```java
public final class MenuSnapshot {
    private final Map<Long, Menu> byId;
    public MenuSnapshot(Map<Long, Menu> byId) {
        this.byId = Map.copyOf(byId);
    }
    public Menu get(long id) { return byId.get(id); }
}

public class MenuCache {
    private final AtomicReference<MenuSnapshot> ref =
        new AtomicReference<>(new MenuSnapshot(Map.of()));

    public Menu get(long id) {
        return ref.get().get(id);
    }

    public void reload(List<Menu> latest) {
        Map<Long, Menu> next = new HashMap<>();
        for (Menu m : latest) next.put(m.getId(), m);
        ref.set(new MenuSnapshot(next));
    }
}
```

- read는 사실상 락이 없다. 참조 한 번만 읽는다.
- reload 중에도 read는 직전 스냅샷을 본다. tearing이 일어나지 않는다.
- 부분 수정은 reload 한 번을 다시 호출해서 처리한다.

### 예제 2 — RWLock으로 조회 중 갱신 처리

부분 변경이 실제로 잦아서 매번 전체 reload가 부담스러울 때.

```java
public class RwLockMenuCache {
    private final Map<Long, Menu> map = new HashMap<>();
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

    public Menu get(long id) {
        lock.readLock().lock();
        try { return map.get(id); }
        finally { lock.readLock().unlock(); }
    }

    public void update(Menu m) {
        lock.writeLock().lock();
        try { map.put(m.getId(), m); }
        finally { lock.writeLock().unlock(); }
    }
}
```

read 동시성은 확보되지만 매 read마다 락 카운터를 만진다는 비용은 남는다.

### 개선 2 — StampedLock optimistic read

```java
public class StampedMenuCache {
    private Map<Long, Menu> map = new HashMap<>();
    private final StampedLock sl = new StampedLock();

    public Menu get(long id) {
        long stamp = sl.tryOptimisticRead();
        Map<Long, Menu> snapshot = map;
        Menu found = snapshot.get(id);
        if (!sl.validate(stamp)) {
            stamp = sl.readLock();
            try {
                found = map.get(id);
            } finally {
                sl.unlockRead(stamp);
            }
        }
        return found;
    }

    public void update(Menu m) {
        long stamp = sl.writeLock();
        try {
            Map<Long, Menu> next = new HashMap<>(map);
            next.put(m.getId(), m);
            map = next;
        } finally {
            sl.unlockWrite(stamp);
        }
    }
}
```

- 99% 이상의 read는 락 없이 끝난다.
- write가 동시에 일어났을 때만 read 락으로 fall back.
- write 시 새 Map을 통째로 만들어 swap하는 점이 핵심이다 — 기존 Map을 직접 put 하면 optimistic read 구간이 깨진 자료구조를 보게 되어 위험하다.

### 자주 만드는 실수 패턴

- `volatile Map` 하나만 두고 그 Map에 `put`을 직접 한다 — Map 내부 상태가 깨진 채로 read 스레드에 보일 수 있다. swap 패턴이 아니면 안 된다.
- StampedLock optimistic read 구간에서 객체의 두 필드를 따로 읽고 그대로 사용한다 — 두 필드가 서로 다른 시점일 수 있다. 지역 변수로 복사한 뒤 validate, 실패 시 read lock 재시도가 정석이다.
- write lock 안에서 외부 호출(DB 조회, RPC)을 한다 — write 구간이 길어져 read 전체가 블록된다. write lock 진입 전에 새 데이터를 먼저 빌드해야 한다.
- ReadWriteLock으로 starvation을 제어하지 않고 fair=false 그대로 운영 — write가 영영 안 잡히는 사고를 본다.

## 로컬 실습 환경

JDK 17+, Maven 또는 Gradle 단일 모듈로 충분하다. 외부 의존성 없이 JMH 또는 직접 짠 스레드 풀 벤치만으로 의미 있는 비교가 가능하다.

```
src/main/java/cache/MenuCache.java        # AtomicReference 버전
src/main/java/cache/RwLockMenuCache.java
src/main/java/cache/StampedMenuCache.java
src/test/java/cache/CacheBench.java       # ExecutorService 기반 부하기
```

JMH를 도입할 수 있으면 `@Benchmark` 메서드 3종(read-only, read-heavy with 1% write, balanced)을 두고 비교한다. 도입하지 않더라도 `Executors.newFixedThreadPool(64)`에 read 스레드 32, write 스레드 1\~2개를 섞어 30초 돌린 뒤 read 횟수를 비교하면 패턴별 throughput 차이가 명확히 보인다.

## 실행 가능한 미니 부하 테스트

```java
public class CacheBench {
    public static void main(String[] args) throws Exception {
        StampedMenuCache cache = new StampedMenuCache();
        for (long i = 0; i < 1000; i++) cache.update(new Menu(i, "m" + i));

        AtomicLong reads = new AtomicLong();
        ExecutorService es = Executors.newFixedThreadPool(33);
        long end = System.currentTimeMillis() + 5000;

        for (int i = 0; i < 32; i++) {
            es.submit(() -> {
                ThreadLocalRandom r = ThreadLocalRandom.current();
                while (System.currentTimeMillis() < end) {
                    cache.get(r.nextLong(1000));
                    reads.incrementAndGet();
                }
            });
        }
        es.submit(() -> {
            while (System.currentTimeMillis() < end) {
                cache.update(new Menu(0, "updated"));
                Thread.sleep(50);
            }
            return null;
        });

        es.shutdown();
        es.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("reads=" + reads.get());
    }
}
```

`StampedMenuCache`, `RwLockMenuCache`, `MenuCache(AtomicReference)`를 차례로 끼워 넣고 reads 수치를 비교하면 read-heavy 시나리오에서 optimistic read와 swap 패턴의 우위가 가시화된다.

## 면접 답변 프레이밍

질문이 "동시성 어떻게 다루셨어요?" 또는 "캐시 갱신 중 조회 일관성은 어떻게 보장합니까?"로 들어오면, 다음 흐름이 안전하다.

1. **상황 정의로 시작한다.** "조회는 초당 수천, 변경은 분당 수 건 수준의 비대칭이라 read-heavy 정책 캐시 패턴으로 분류했습니다."
2. **선택지 비교를 짧게 깐다.** synchronized → 직렬화 비용, RWLock → read도 락 비용, StampedLock optimistic read → read 사실상 무비용, swap 패턴 → 부분 갱신 불가.
3. **선택과 근거를 댄다.** "데이터 양이 수천 건 수준이고 일관된 스냅샷 단위로 운영자가 적용하는 패턴이라 AtomicReference swap을 1차로 채택했습니다. 이후 부분 갱신 요건이 추가되어 StampedLock 기반으로 옮겼습니다."
4. **이전 경험과 잇는다.** "이전 직무의 게임 정적 데이터 캐시도 같은 구조였고, 운영자 콘솔 변경 시 새 스냅샷을 빌드해 통째 swap하는 방식으로 조회 latency 영향을 거의 없앴습니다. 외식 커머스 메뉴/프로모션 캐시도 같은 모델로 풀 수 있다고 봅니다."
5. **trade-off를 먼저 인정한다.** "StampedLock은 재진입이 안 되고 사용 규칙이 까다로워서 팀 코드 리뷰 시 패턴을 가이드 문서로 고정해야 합니다."

이 흐름은 후보자가 단순히 키워드를 외운 것이 아니라 read/write 비대칭을 보고 도구를 고른다는 인상을 준다.

## 체크리스트

- 캐시 read와 write의 빈도 비율을 숫자로 말할 수 있는가.
- 부분 갱신이 진짜 필요한가, 전체 swap으로 충분한가를 판별했는가.
- write 락 구간에 외부 호출(DB, 네트워크)이 들어가 있지 않은가.
- StampedLock optimistic read 구간에서 읽은 값을 지역 변수로 복사했는가.
- `volatile Map` 단독 사용으로 자료구조 내부를 직접 수정하는 코드가 없는가.
- ReadWriteLock 사용 시 writer starvation 가능성을 검토했는가.
- 갱신 중 조회 스레드가 보는 일관성 단위(스냅샷 vs 부분 갱신)를 문서로 합의했는가.
- 운영 피크 직전 reload를 트리거하는 운영 절차/모니터링이 준비되어 있는가.
- 면접 답변에서 도구 이름만이 아니라 read/write 비율과 trade-off로 설명할 수 있는가.
