# 시뮬레이터 OOM — Welford's Online Algorithm으로 교체

**진행 기간**: 2025.02

---

## 배경

시뮬레이터는 슬롯 게임의 RTP(Return To Player)와 변동성 지수를 검증하는 도구다. 1억 스핀을 돌려서 기댓값과 분산이 수학적으로 맞게 나오는지 확인한다.

변동성 지수(Volatility Index)를 구하려면 분산이 필요하다. 분산을 구하는 가장 직관적인 방법은 모든 스핀의 당첨금을 다 모아두고 나중에 한꺼번에 계산하는 것이다. 이게 문제의 시작이었다.

---

## 발견

여러 명이 동시에 시뮬레이터를 돌리면 OOM(OutOfMemoryError)이 발생했다. 확인해보니 JVM 힙 사이즈 설정이 빠져 있어서 기본값으로 실행되고 있었다. 구조적인 원인은 파악했지만, 당장의 해결책으로 힙을 12GB로 늘리는 임시방편을 먼저 적용했다.

```bash
export JAVA_OPTS="-Xmx12g -Xms12g"
```

이후 온라인 알고리즘이라는 방법을 찾게 되어 구조적인 원인을 근본적으로 해결했다.

---

## 원인 분석

코드를 보면 `AccumulateData` 클래스에 이런 필드가 있었다.

```java
// 변동성 지수 계산시 사용하던 변수
private final List<Long> winmoneyList;
```

시뮬레이션이 돌아가는 동안 스핀 한 번이 실행될 때마다 당첨금을 이 리스트에 쌓는다. 문제는 규모다.

```
1억 스핀 × Long 1개(8 bytes) = 800MB (시뮬레이션 1회)
4명 동시 수행 = 800MB × 4 = 3.2GB
```

힙 12GB 중 winmoneyList만 3.2GB를 차지하고, 그 위에 시뮬레이터의 다른 누적 데이터, Spring 컨텍스트, GC 오버헤드까지 더해지면 OOM이 터질 조건이 충분히 만들어진다.

시뮬레이터는 성능을 위해 멀티스레드로 스핀을 처리하고, 스레드마다 각자의 `AccumulateData`를 들고 있다가 나중에 합산한다. 합산할 때도 리스트 두 개를 이어 붙이므로(`concatList`) 순간적으로 메모리 사용량이 더 튀어오른다.

결론: **힙 사이즈 미설정은 트리거였고, 근본 원인은 분산 계산을 위해 모든 당첨금을 메모리에 올려놓는 구조**였다.

---

## 해결 — Welford's Online Algorithm

분산을 구하기 위해 모든 데이터를 저장할 필요가 없다. Welford's Online Algorithm은 데이터를 하나씩 받을 때마다 평균과 분산을 즉시 갱신한다. 저장하는 값은 세 개뿐이다.

```
count  — 지금까지 처리한 스핀 수 (int,    4 bytes)
mean   — 현재 평균                 (double, 8 bytes)
m2     — 분산 계산을 위한 누적 변수 (double, 8 bytes)
```

1억 스핀을 처리해도 메모리에 남는 건 20바이트다.

`WelfordOnlineCalculator`를 새로 만들어서 이 로직을 구현했다.

```java
public void addWinMoney(long winMoney, long totalBetAmount) {
    count++;
    final double multiplier = (double) winMoney / totalBetAmount;

    // 새 값이 평균에서 얼마나 벗어났는지
    final double delta = multiplier - mean;

    // 평균 업데이트
    mean += delta / count;

    // 업데이트된 평균 기준으로 다시 계산
    final double delta2 = multiplier - mean;

    // 편차의 제곱합 누적
    m2 += delta * delta2;
}

double getVariance() {
    return count > 1 ? m2 / (count - 1) : 0.0;
}
```

스핀 한 번 처리할 때 리스트에 값을 추가하는 대신 `addWinMoney()`를 한 번 호출하면 된다.

### 병렬 처리에서의 병합

멀티스레드로 처리할 때 각 스레드의 계산기를 합산하는 것도 수학적으로 처리할 수 있다.

```java
public static WelfordOnlineCalculator merge(WelfordOnlineCalculator o1, WelfordOnlineCalculator o2) {
    final WelfordOnlineCalculator merged = new WelfordOnlineCalculator();
    merged.count = o1.count + o2.count;

    if (merged.count == 0) {
        return merged;
    }

    final double delta = o2.mean - o1.mean;
    merged.mean = ((o1.mean * o1.count) + (o2.mean * o2.count)) / merged.count;
    merged.m2 = o1.m2 + o2.m2 + delta * delta * o1.count * o2.count / merged.count;

    return merged;
}
```

기존 방식은 리스트 merge 시 1억 개짜리 리스트 두 개를 이어 붙이는 비용이 들었다. 이제는 숫자 몇 개의 연산으로 끝난다.

---

## 적용

`AccumulateData.init()`을 `@Deprecated` 처리하고, 새로운 팩토리 메서드 `initWithWelfordOnlineCalculator()`를 추가했다.

```java
// 기존 방식 — 더 이상 사용하지 않는다
@Deprecated
public static AccumulateData init() { ... }

// 새 방식
public static AccumulateData initWithWelfordOnlineCalculator() {
    final AccumulateData accumulateData = new AccumulateData(..., null); // winmoneyList는 null
    accumulateData.welfordOnlineCalculator = WelfordOnlineCalculator.init();
    return accumulateData;
}
```

슬롯 5종(21, 29, 31, 32, 33)의 시뮬레이터를 새 방식으로 전환했다.

---

## 결과

스핀마다 리스트에 당첨금을 쌓던 방식이 사라졌다. 1억 스핀을 처리하는 동안 메모리에는 스칼라 값 3개(20바이트)만 유지된다. 4명이 동시에 시뮬레이션을 실행해도 winmoneyList로 인한 메모리 증가가 없다.

한 가지 검토한 부분이 있었다. Welford's Online Algorithm은 부동소수점 연산을 누적하기 때문에, 전체 데이터를 모아 한꺼번에 계산하는 방식과 결과가 완전히 일치하지 않는다. 실제로 측정했을 때 오차율은 0.xx% 수준이었다. 변동성 지수 계산의 특성상 이 정도 오차는 무시할 수 있는 범위였고, 메모리 안정성을 얻는 편이 훨씬 중요했다.

---

## 배운 것

**분산을 구하기 위해 모든 데이터를 저장해야 한다는 선입관을 버리자.** Welford's Online Algorithm처럼 수학적으로 증명된 온라인 알고리즘을 활용하면 단일 패스로 평균과 분산을 동시에 구할 수 있다.

**힙 크기 조절은 임시방편이다.** 메모리가 부족해 보일 때 `-Xmx`를 늘리는 것은 원인을 가리는 것에 가깝다. 무엇이 메모리를 점유하고 있는지 파악하고 구조를 바꾸는 게 맞다.

**멀티스레드 환경에서 스레드별 상태 크기가 선형으로 증가하면 위험하다.** 스레드 하나의 부담이 작아 보여도 스레드 수 × 사용자 수로 곱해지면 이야기가 달라진다.

**정확도와 실용성 사이의 트레이드오프는 직접 측정해서 판단하자.** 알고리즘을 바꾸면 오차가 생긴다는 걸 알고 있었다. 어림짐작이 아니라 실제로 측정해보니 0.xx% 수준이었고, 변동성 지수 용도로는 충분히 허용 가능한 범위였다. 수치로 판단했기 때문에 확신을 갖고 적용할 수 있었다.

---

## 사용 기술

- Java 17
- Welford's Online Algorithm
