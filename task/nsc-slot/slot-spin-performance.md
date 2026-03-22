# 슬롯 스핀 성능 최적화 — AliasMethod와 Random 선택기

**진행 기간**: 2025.01 ~ 2025.02

---

## 배경

시뮬레이터로 100만 스핀을 돌리다 보면 속도 차이가 꽤 크게 느껴진다. 슬롯 한 종류에 1~2분이면 끝나야 할 시뮬레이션이 10분 넘게 걸리는 경우도 있었다. 직접 기여한 비중이 크지는 않지만, 병목을 파악하면서 두 가지를 정리해두고 싶어서 기록으로 남긴다.

---

## 1. 가중치 랜덤 선택 — Alias Method

### 기존 방식

슬롯 릴은 심볼마다 등장 가중치가 다르다. "7" 심볼은 가중치 1, "체리"는 가중치 100 같은 식이다.

가중치 기반으로 하나를 선택하는 가장 직관적인 방법은 이렇다.

```java
// 누적 합 방식 (O(n))
int totalWeight = 0;
for (int w : weights) totalWeight += w;

int pivot = random.nextInt(totalWeight);
int sum = 0;
for (int i = 0; i < weights.length; i++) {
    sum += weights[i];
    if (sum > pivot) return i;
}
```

가중치 배열 길이가 n이면 최악의 경우 n번 탐색해야 한다. 릴 하나에 심볼이 수십 개, 스핀 한 번에 릴이 5개, 시뮬레이터는 100만 스핀이라면 이 반복이 꽤 쌓인다.

### Alias Method

Alias Method는 사전에 테이블을 만들어두고, 선택 시점에는 딱 2번의 랜덤으로 O(1) 선택을 한다.

아이디어는 이렇다. 가중치를 정규화해서 각 항목이 "평균"보다 많거나 적은 구역을 가지도록 쌍을 맞춘다.

```
가중치: [1, 3, 2]  →  총합 6, 평균 2

정규화:
  인덱스 0: 비율 1/2 → 부족 (Small)
  인덱스 1: 비율 3/2 → 초과 (Large)
  인덱스 2: 비율 2/2 → 정확

Small과 Large를 쌍으로 맞춰 alias 배열 구성:
  prob[0] = 1/2,  alias[0] = 1  ← 0을 선택했는데 확률 미달이면 1로 대체
  prob[1] = 1,    alias[1] = 1
  prob[2] = 1,    alias[2] = 2
```

선택 시:

```java
// 항상 O(1)
int i = random.nextInt(n);           // 구역 선택
int r = random.nextInt(avg);         // 구역 내 위치
return r < prob[i] ? i : alias[i];  // 확률에 따라 원본 또는 대체 반환
```

실제 코드는 `SlotAliasMethodMaker.of(int[] weights)`에서 테이블을 생성하고, `AliasTable.pick()`에서 위 로직으로 선택한다.

```java
// 테이블 생성 (한 번만)
SlotAliasMethod aliasMethod = SlotAliasMethodMaker.of(weights);

// 선택 (O(1), 매번)
public String pick() {
    final int i = ThreadLocalRandom.current().nextInt(alias.getIndices().length);
    final int r = ThreadLocalRandom.current().nextInt(avg);
    return r < probability.getFigures()[i]
        ? representative.getRepresentatives()[i]
        : representative.getRepresentatives()[alias.getIndices()[i]];
}
```

테이블 생성은 슬롯 초기화 시점에 한 번만 한다. 이후 스핀마다 호출되는 `pick()`은 항상 O(1)이다.

---

## 2. 게임에서 Random은 무엇을 써야 하는가

### SecureRandom이 슬롯에 있었다

코드 안에 `SecureRandom`을 쓰는 부분이 있었다.

```java
private static final SecureRandom RANDOM = new SecureRandom();
final int random = RANDOM.nextInt(maxRandom);
```

`SecureRandom`은 암호학적으로 안전한 난수 생성기다. 암호화 키 생성, 세션 토큰 생성처럼 "결과를 예측할 수 없어야" 하는 곳에 쓴다. OS의 엔트로피 풀을 사용하기 때문에 생성 비용이 높고, 멀티스레드 환경에서 내부적으로 `synchronized` 처리가 들어간다.

### 슬롯에서 암호학적 난수가 필요한가

슬롯은 **서버가 결과를 결정하고 클라이언트에 전달**하는 구조다. 유저는 서버의 난수 생성 과정에 접근할 수 없다. 클라이언트가 다음 스핀 결과를 예측할 방법이 없다.

암호학적 난수가 필요한 경우는 **공격자가 내부 상태를 알아내서 다음 값을 예측하는 시나리오**를 막아야 할 때다. 슬롯에서 랜덤 생성 내부 상태가 외부에 노출될 방법이 없으므로, `SecureRandom`의 보안 강도는 여기서는 과잉이다.

`ThreadLocalRandom`으로 충분하다.

### JMH 벤치마크

실제로 얼마나 차이가 나는지 JMH로 측정했다. 1000만 번 랜덤을 뽑는 기준이다.

```
ThreadLocalRandom: 70.241 ops/s
SecureRandom:       1.197 ops/s
```

약 58배 차이다. 시뮬레이터에서 스핀 하나당 수십 번 랜덤을 뽑는 걸 감안하면 이 차이가 누적된다.

### 왜 ThreadLocalRandom이 빠른가

`ThreadLocalRandom`은 이름 그대로 스레드별 독립 인스턴스다. 각 스레드가 자신만의 상태를 가지기 때문에 스레드 간 경쟁이 없다.

`SecureRandom`은 내부적으로 `synchronized` 블록을 사용한다. 멀티스레드 환경에서 락 경합이 발생한다. 시뮬레이터는 멀티스레드로 스핀을 처리하기 때문에 이 비용이 더 크다.

---

## 3. ThreadLocalRandom 올바른 사용법

`ThreadLocalRandom`으로 바꾸면 끝이 아니다. 잘못 쓰면 의도한 대로 동작하지 않는다.

### 필드로 저장하면 안 된다

```java
// 잘못된 방식
@Component
public class ThreadLocalRandomProvider {
    private final ThreadLocalRandom random = ThreadLocalRandom.current(); // ← 문제
    ...
}
```

`ThreadLocalRandom.current()`는 **현재 스레드에 귀속된 인스턴스**를 반환한다. 필드로 저장하면 저장 시점의 스레드(Spring 초기화 스레드)에 귀속된 인스턴스가 고정된다. 다른 스레드에서 이 필드를 쓰면 같은 인스턴스를 공유하게 되어 스레드 안전하지 않다.

실제로 이 패턴으로 작성된 코드에서 버그가 났다.

```java
// 올바른 방식: 매번 current() 호출
private ThreadLocalRandom getRandom() {
    return ThreadLocalRandom.current(); // 호출 시점의 스레드 인스턴스 반환
}
```

`ThreadLocalRandom.current()`는 매번 호출해도 비용이 크지 않다. 스레드 로컬에서 조회하는 것뿐이다.

---

## 배운 것

**암호학 도구는 암호학에만 쓰자.** `SecureRandom`이 더 안전해 보여서 기본 Random 대신 쓰는 경우가 있다. 암호학적 보장이 필요하지 않은 곳에 쓰면 성능 비용만 지불하게 된다. "안전하다 = 더 좋다"는 아니다. 목적에 맞는 도구를 쓰는 게 맞다.

**ThreadLocal 객체는 필드에 저장하면 안 된다.** `ThreadLocal`의 핵심은 "호출 시점의 스레드"에 귀속된 값을 가져오는 것이다. 필드로 저장하면 이 특성이 깨진다. `ThreadLocalRandom`뿐 아니라 모든 `ThreadLocal` 계열 객체에 적용된다.

---

## 사용 기술

- Java 17
- JMH (Java Microbenchmark Harness)
