# 시뮬레이터 잭팟 풀 — ThreadLocal 격리 버그

**진행 기간**: 2025.09

---

## 배경

슬롯 시뮬레이터는 1억 스핀을 멀티스레드로 나눠 돌린다. 잭팟이 있는 슬롯을 시뮬레이션하면 누적 금액이 맞지 않는 문제가 있었다. 각 스레드가 잭팟을 따로 쌓고 있었다.

---

## 원인: ThreadLocal로 스레드마다 독립된 잭팟 풀

기존 `SimulatorProgressiveJackpotRepositoryImpl`은 잭팟 풀을 `ThreadLocal`로 관리했다.

```java
private final ThreadLocal<Map<String, List<Jackpot>>> jackpotPools = new ThreadLocal<>();
```

`ThreadLocal`은 스레드마다 독립된 변수를 제공한다. 스레드 A에서 만든 잭팟 풀은 스레드 B에서 보이지 않는다.

시뮬레이터는 여러 스레드가 동시에 스핀을 나눠 처리한다. 각 스레드가 `createJackpotPool`을 호출해도 자신만의 풀을 만들고, 자신만의 풀에 누적했다. 스레드 간에 잭팟이 전혀 공유되지 않은 것이다.

게다가 초기화와 삭제가 각 스레드 실행 단위에서 이뤄졌다.

```java
// 기존: 각 스레드 태스크 내부에서 초기화/삭제
initializeJackpotPool(slotGame);      // 각 스레드마다 자기 풀 생성
// ... 스핀 처리 ...
deleteAllJackpotPool(simulationSpinInfo.slotGame());  // 각 스레드마다 자기 풀 삭제
```

스레드 태스크가 끝날 때 `deleteAllJackpotPool()`을 호출하는데 이게 모든 풀을 삭제(`ThreadLocal.remove()`)했다. 다른 시뮬레이션이 돌고 있는 상황에서 풀이 통째로 날아갈 수도 있는 구조였다.

---

## 해결: AtomicReference 기반 공유 풀 + 생명주기 분리

### 1. ThreadLocal 제거 → AtomicReference 공유 맵

`SimulatorProgressiveJackpotRepositoryImpl`을 삭제하고, 전체 스레드가 하나의 맵을 공유하는 `AtomicProgressiveJackpotRepositoryImpl`로 교체했다.

```java
private final Map<String, Map<String, AtomicReference<Double>>> jackpotPools = new HashMap<>();
```

누적은 `AtomicReference.updateAndGet()`으로 처리한다.

```java
// 누적 — CAS로 race condition 없이 더함
atomic.updateAndGet(current -> current + accumulateAmount);

// 당첨 — 원자적으로 읽고 0으로 초기화
final Double accumulateAmount = atomic.getAndSet(0.0);
```

Redis의 `HINCRBYFLOAT`과 Lua 스크립트가 하는 역할을 JVM 수준에서 `AtomicReference`로 대체한 구조다.

### 2. 잭팟 풀 생명주기를 시뮬레이션 단위로 올림

풀 생성과 삭제를 각 스레드 태스크 내부에서 꺼내 시뮬레이션 전체를 감싸는 바깥 계층으로 올렸다.

```java
// 수정 후: 시뮬레이션 시작 전 풀 생성, 끝나면 해당 풀만 삭제
try {
    initializeJackpotPool(simulationSpin.slotGame());
    return getSimulationResults(simulator, simulationSpin);
} finally {
    deleteAllJackpotPool(simulationSpin.slotGame());
}
```

`deleteAllJackpotPool()`도 `deleteProgressiveJackpotPool(casinoUuid, gameId)`로 바꿨다. 전체를 날리는 대신 해당 시뮬레이션의 풀만 제거한다.

---

## 배운 것

**ThreadLocal은 "스레드마다 독립된 상태"가 필요할 때 쓰는 도구다.** 잭팟 풀처럼 여러 스레드가 함께 쌓아야 하는 공유 상태에 ThreadLocal을 쓰면 격리가 목적이 아니라 버그가 된다.

**생명주기의 위치가 맞지 않으면 데이터가 사라진다.** 풀을 만드는 곳과 쓰는 곳, 삭제하는 곳의 범위가 일치해야 한다. "각 태스크가 자신의 상태를 관리한다"는 패턴은 단일 스레드에서는 깔끔하지만, 병렬 실행에서는 공유 상태와 개별 상태를 명확히 구분해야 한다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- `AtomicReference` (CAS 기반 lock-free 누적)
- Project Reactor (`ReactiveSimulatorService`)
