---
thumbnail: ./images/welford-online-algorithm-thumbnail.jpg
tags: [study, insights]
---

# Welford's Online Algorithm: 값을 저장하지 않고 평균과 분산 계산하기

Welford's Online Algorithm은 입력을 한 번만 읽으면서 평균과 분산을 갱신한다.
입력 개수와 관계없이 `count`, `mean`, `m2`만 유지하므로 추가 메모리는 `O(1)`이다.

이 글은 다음 질문에 답한다.

- 왜 모든 값을 모아서 계산할 필요가 없는가
- 새 값 하나가 들어올 때 평균과 분산을 어떻게 갱신하는가
- 여러 스레드에서 나눠 계산한 결과를 어떻게 합치는가

## 모든 값을 저장하는 방식의 문제

평균을 먼저 구하고 각 값과 평균의 차이를 다시 더하는 방식은 이해하기 쉽다.

```text
평균 = sum(x) / n
분산 = sum((x - 평균)^2) / n
```

입력을 다시 읽을 수 있다면 두 번 순회해서 계산할 수 있다.
하지만 스트림을 한 번만 읽을 수 있거나 값을 목록에 쌓는 구조라면 입력 수만큼 메모리가 늘어난다.

1억 개 값을 `List<Long>`에 보관하면 원시 `long` 배열보다 훨씬 많은 메모리가 필요하다.
정확한 크기는 JVM의 객체 정렬, compressed oops와 컬렉션 구현에 따라 달라지므로 바이트 수를 고정해 말할 수 없다.
중요한 점은 입력이 두 배가 되면 저장 공간도 두 배가 되는 `O(n)` 구조라는 사실이다.

Welford 방식은 지금까지 본 값의 요약 상태만 남긴다.

| 상태 | 의미 |
| --- | --- |
| `count` | 처리한 값의 개수 |
| `mean` | 현재까지의 평균 |
| `m2` | 현재 평균을 기준으로 한 편차 제곱합 |

## 새 값 하나를 반영하는 갱신식

현재 상태가 `count`, `mean`, `m2`이고 새 값 `x`가 들어왔다고 하자.
상태는 다음 순서로 갱신한다.

```text
count' = count + 1
delta  = x - mean
mean'  = mean + delta / count'
delta2 = x - mean'
m2'    = m2 + delta * delta2
```

`delta`는 갱신 전 평균과 새 값의 차이다.
`delta2`는 갱신 후 평균과 새 값의 차이다.
두 차이의 곱을 `m2`에 더하면 모든 값을 다시 읽지 않고도 편차 제곱합을 유지할 수 있다.

전체 입력을 처리하는 시간은 `O(n)`이고, 값 하나를 추가하는 연산은 `O(1)`이다.
추가 메모리는 입력 수와 관계없이 `O(1)`이다.

### 1, 2, 3을 차례로 넣는 예

초기 상태는 `count = 0`, `mean = 0`, `m2 = 0`이다.

| 입력 | count | mean | m2 |
| ---: | ---: | ---: | ---: |
| 1 | 1 | 1 | 0 |
| 2 | 2 | 1.5 | 0.5 |
| 3 | 3 | 2 | 2 |

세 값을 모두 처리하면 모집단분산은 `m2 / count = 2 / 3`이다.
표본분산은 자유도 보정을 적용해 `m2 / (count - 1) = 1`이다.
분모가 다르므로 계산기가 어느 분산을 반환하는지 메서드 이름으로 드러내야 한다.

## Java 구현

```java
public final class OnlineVariance {
    private long count;
    private double mean;
    private double m2;

    public void add(double value) {
        count++;
        double delta = value - mean;
        mean += delta / count;
        double delta2 = value - mean;
        m2 += delta * delta2;
    }

    public long count() {
        return count;
    }

    public double mean() {
        return mean;
    }

    public double populationVariance() {
        return count == 0 ? Double.NaN : m2 / count;
    }

    public double sampleVariance() {
        return count < 2 ? Double.NaN : m2 / (count - 1);
    }
}
```

빈 입력과 값 하나뿐인 표본에는 분산을 계산할 수 없다는 사실을 반환값이나 예외 정책으로 명확히 해야 한다.
위 예시는 계산 불가 상태에 `Double.NaN`을 사용했다.

## 병렬 계산 결과 병합

입력을 여러 작업으로 나눴다면 각 작업이 `count`, `mean`, `m2`를 계산한 뒤 세 값만 합칠 수 있다.
두 부분 집합을 `a`, `b`라고 하면 병합식은 다음과 같다.

```text
count = countA + countB
delta = meanB - meanA
mean  = meanA + delta * countB / count
m2    = m2A + m2B + delta^2 * countA * countB / count
```

```java
public OnlineVariance merge(OnlineVariance other) {
    if (other.count == 0) {
        return this;
    }
    if (count == 0) {
        count = other.count;
        mean = other.mean;
        m2 = other.m2;
        return this;
    }

    long mergedCount = count + other.count;
    double delta = other.mean - mean;

    m2 += other.m2
        + delta * delta * count * other.count / mergedCount;
    mean += delta * other.count / mergedCount;
    count = mergedCount;
    return this;
}
```

스레드마다 계산기 하나를 두고 작업이 끝난 뒤 병합하면 공유 목록과 잠금이 필요 없다.
병렬 스트림이나 배치 파티션에서도 입력 원본 대신 작은 누적 상태만 전달할 수 있다.

## 수치 안정성과 한계

분산을 `E[x²] - E[x]²`로 계산하면 두 큰 값이 거의 같을 때 유효 숫자가 사라질 수 있다.
Welford 갱신식은 이 방식보다 수치적으로 안정적이다.

그렇다고 부동소수점 오차가 없어지는 것은 아니다.

- `double`의 표현 범위를 넘는 값에는 사용할 수 없다.
- 입력 순서와 병합 순서에 따라 마지막 몇 비트가 달라질 수 있다.
- 금융 정산처럼 십진수의 정확한 일치가 필요하면 `BigDecimal`이나 별도의 정밀도 정책이 필요하다.
- 중앙값, 백분위수와 히스토그램은 세 상태만으로 복원할 수 없다.

정확한 원본 값이 다시 필요하거나 슬라이딩 윈도우에서 오래된 값을 제거해야 한다면 기본 Welford 방식만으로는 부족하다.

## 검증 방법

구현 검증은 작은 정답과 큰 무작위 입력을 나눠서 진행한다.

### 손으로 계산할 수 있는 값

`[1, 2, 3]`의 평균은 `2`, 모집단분산은 `2 / 3`, 표본분산은 `1`이다.
빈 입력과 값 하나인 입력의 반환 정책도 함께 검증한다.

### 두 번 순회한 결과와 비교

테스트 데이터는 배열에 보관해 평균과 편차 제곱합을 두 번 순회해서 계산한다.
같은 데이터를 Welford 계산기에 넣은 뒤 절대 오차와 상대 오차가 정한 허용 범위 안인지 확인한다.

```java
assertThat(actual)
    .isCloseTo(expected, within(1e-12));
```

### 분할 병합 검증

같은 입력을 한 번에 처리한 결과와 여러 조각으로 나눠 처리한 뒤 병합한 결과를 비교한다.
병렬 적용에서는 이 검증이 순차 갱신 테스트만큼 중요하다.

## 실제 적용 사례

슬롯 시뮬레이터는 1억 회 실행 결과를 `List<Long>`에 쌓아 분산을 계산했다.
Welford 방식으로 바꾸면서 입력 수에 비례하던 상태를 세 개의 스칼라 값으로 줄였다.

[슬롯 시뮬레이터 OOM 해결](../task/nsc-slot/slot-simulator-oom.md)

## 참고 자료

- [B. P. Welford, Note on a Method for Calculating Corrected Sums of Squares and Products](https://doi.org/10.1080/00401706.1962.10490022)
- [T. F. Chan, G. H. Golub, R. J. LeVeque, Algorithms for Computing the Sample Variance](https://doi.org/10.1080/00031305.1983.10483115)
