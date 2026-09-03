---
thumbnail: ./images/alias-method-weighted-random-thumbnail.jpg
tags: [study, insights]
---

# Alias Method: 가중치 랜덤 선택을 전처리 O(n), 추출 O(1)로 바꾸기

Alias Method는 자주 바뀌지 않는 가중치 분포에서 항목을 반복해서 뽑을 때 사용한다.
분포를 한 번 전처리한 뒤에는 배열 두 개를 조회해 `O(1)`에 항목 하나를 선택할 수 있다.

이 글은 다음 질문에 답한다.

- 누적합과 이진 탐색 대신 Alias Method를 선택할 조건은 무엇인가
- 확률 배열과 alias 배열은 어떻게 만들어지는가
- 구현이 원래 가중치 분포를 따르는지 어떻게 검증하는가

## 반복 선택에서 전처리가 필요한 이유

가중치가 `[1, 3, 2]`라면 두 번째 항목은 첫 번째 항목보다 세 배 자주 선택되어야 한다.
가장 단순한 방법은 가중치 누적합을 순회하며 난수가 들어갈 구간을 찾는 것이다.

| 방식 | 전처리 | 선택 1회 | 추가 메모리 | 적합한 상황 |
| --- | ---: | ---: | ---: | --- |
| 선형 누적합 순회 | `O(n)` | `O(n)` | `O(n)` | 항목 수와 호출 수가 적음 |
| 누적합과 이진 탐색 | `O(n)` | `O(log n)` | `O(n)` | 가중치가 자주 바뀜 |
| Alias Method | `O(n)` | `O(1)` | `O(n)` | 같은 분포에서 매우 자주 선택 |

Alias Method는 전처리 비용을 없애는 알고리즘이 아니다.
가중치가 바뀔 때마다 표를 다시 만들어야 하므로 분포가 자주 바뀌면 장점이 줄어든다.

## 하나의 열에 두 후보만 남기는 구조

항목이 `n`개라면 전체 확률을 너비가 같은 `n`개 열로 나눈다.
각 열은 원래 항목 하나와 부족한 확률을 채워 주는 alias 항목 하나만 가진다.

전처리가 끝나면 두 배열을 유지한다.

| 배열 | 의미 |
| --- | --- |
| `probability[i]` | 열 `i`에서 원래 항목을 선택할 확률 |
| `alias[i]` | 원래 항목이 선택되지 않았을 때 대신 선택할 항목 |

선택할 때는 열 하나를 균등하게 고르고, 열 안에서 다시 균등 난수를 만든다.
난수가 `probability[i]`보다 작으면 `i`를 반환하고, 아니면 `alias[i]`를 반환한다.

```text
column = uniformInteger(0, n)
coin   = uniformDouble(0, 1)

if coin < probability[column]
    return column
else
    return alias[column]
```

배열 접근 횟수는 항목 수와 관계없이 일정하므로 선택 연산은 `O(1)`이다.

## 가중치 1, 3, 2로 표 만들기

가중치 합은 `6`이고 항목 수는 `3`이다.
각 확률에 항목 수를 곱하면 열 하나의 기준 크기가 `1`이 된다.

```text
scaled[0] = 1 / 6 * 3 = 0.5
scaled[1] = 3 / 6 * 3 = 1.5
scaled[2] = 2 / 6 * 3 = 1.0
```

기준보다 작은 항목은 `small`, 큰 항목은 `large`에 넣는다.

```text
small = [0]
large = [1]
완성   = [2]
```

작은 항목 `0`의 열에는 원래 확률 `0.5`를 둔다.
남은 `0.5`는 큰 항목 `1`이 대신 차지하므로 `alias[0] = 1`이 된다.
큰 항목 `1`의 남은 크기는 `1.0`이 되어 그 열도 완성된다.

| 열 | probability | alias |
| ---: | ---: | ---: |
| 0 | 0.5 | 1 |
| 1 | 1.0 | 1 |
| 2 | 1.0 | 2 |

열은 각각 `1 / 3` 확률로 선택된다.
항목 `0`은 첫 열의 절반인 `1 / 6`, 항목 `1`은 첫 열의 나머지와 두 번째 열을 합친 `3 / 6`, 항목 `2`는 세 번째 열인 `2 / 6` 확률을 갖는다.

## 전처리 알고리즘

Vose의 구성 방식은 `small`과 `large` 작업 목록을 사용해 선형 시간에 표를 만든다.

```java
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Deque;
import java.util.random.RandomGenerator;

public final class AliasTable {
    private final double[] probability;
    private final int[] alias;

    public AliasTable(double[] weights) {
        validate(weights);

        int size = weights.length;
        probability = new double[size];
        alias = new int[size];

        double sum = Arrays.stream(weights).sum();
        double[] scaled = Arrays.stream(weights)
            .map(weight -> weight / sum * size)
            .toArray();

        Deque<Integer> small = new ArrayDeque<>();
        Deque<Integer> large = new ArrayDeque<>();

        for (int i = 0; i < size; i++) {
            if (scaled[i] < 1.0) {
                small.add(i);
            } else {
                large.add(i);
            }
        }

        while (!small.isEmpty() && !large.isEmpty()) {
            int less = small.removeLast();
            int more = large.removeLast();

            probability[less] = scaled[less];
            alias[less] = more;
            scaled[more] = scaled[more] + scaled[less] - 1.0;

            if (scaled[more] < 1.0) {
                small.add(more);
            } else {
                large.add(more);
            }
        }

        while (!small.isEmpty()) {
            probability[small.removeLast()] = 1.0;
        }
        while (!large.isEmpty()) {
            probability[large.removeLast()] = 1.0;
        }
    }

    private static void validate(double[] weights) {
        if (weights == null || weights.length == 0) {
            throw new IllegalArgumentException("weights must not be empty");
        }

        double sum = 0.0;
        for (double weight : weights) {
            if (!Double.isFinite(weight) || weight < 0.0) {
                throw new IllegalArgumentException("weights must be finite and non-negative");
            }
            sum += weight;
        }
        if (!Double.isFinite(sum) || sum <= 0.0) {
            throw new IllegalArgumentException("weight sum must be finite and positive");
        }
    }

    public int sample(RandomGenerator random) {
        int column = random.nextInt(probability.length);
        return random.nextDouble() < probability[column]
            ? column
            : alias[column];
    }
}
```

마지막 반복문은 부동소수점 반올림 때문에 작업 목록에 값이 남는 경우를 처리한다.
수학적으로는 정확히 `1.0`이어야 하므로 완성된 열로 취급한다.

## 입력 검증에서 자주 놓치는 조건

전처리 전에 다음 조건을 확인해야 한다.

- 가중치 배열이 비어 있지 않아야 한다.
- 각 가중치는 `0` 이상이고 유한한 값이어야 한다.
- 전체 합은 `0`보다 커야 한다.
- 정수 가중치를 먼저 합한다면 오버플로가 나지 않는 자료형을 사용해야 한다.

가중치가 `0`인 항목은 표에 둘 수 있지만 선택 결과로 나와서는 안 된다.
음수, `NaN`과 무한대는 확률 분포를 만들 수 없으므로 즉시 거부한다.

## 난수 생성기와 Alias Method의 책임

Alias Method는 균등 난수를 주어진 분포로 변환한다.
난수의 예측 가능성이나 보안성을 높이지는 않는다.

따라서 난수 생성기는 사용 목적에 따라 별도로 선택해야 한다.

- 시뮬레이션 재현이 중요하면 seed를 주입할 수 있는 생성기를 사용한다.
- 병렬 성능이 중요하면 스레드 간 공유 상태와 경합 여부를 확인한다.
- 보안이나 규제 요구가 있으면 해당 요구를 충족하는 생성기를 사용한다.

분포 선택 알고리즘이 빠르다는 이유만으로 난수 생성기의 안전 요구를 낮추면 안 된다.

## 검증 방법

Alias 표는 배열 값만 보고 정확성을 확신하기 어렵다.
구조 검증과 분포 검증을 나눠서 진행한다.

### 구조 검증

- 모든 `probability` 값이 `0`부터 `1` 사이인지 확인한다.
- 모든 `alias`가 유효한 배열 인덱스인지 확인한다.
- 가중치가 하나뿐이면 항상 그 인덱스를 반환하는지 확인한다.
- 가중치가 `0`인 항목이 선택되지 않는지 확인한다.
- 잘못된 입력이 즉시 거부되는지 확인한다.

### 분포 검증

가중치 `[1, 3, 2]`로 충분히 많이 추출한 뒤 관측 비율을 기대 비율과 비교한다.

| 항목 | 기대 비율 |
| ---: | ---: |
| 0 | 약 16.67% |
| 1 | 50% |
| 2 | 약 33.33% |

표본 수가 적으면 정상 구현도 기대 비율에서 벗어난다.
테스트에서는 고정 seed로 회귀를 잡고, 별도의 통계 테스트에서는 표본 수와 허용 오차를 함께 기록한다.

## 사용하지 않는 편이 나은 경우

- 가중치가 선택할 때마다 바뀌어 표를 계속 다시 만들어야 하는 경우
- 항목 수가 작고 선택 횟수도 적어 선형 탐색이 더 단순한 경우
- 항목 삽입과 삭제가 빈번해 동적 자료구조가 필요한 경우
- 정확한 재현보다 암호학적 난수 요구가 먼저인 경우

알고리즘 선택은 `O(1)`이라는 표기만으로 끝나지 않는다.
전처리 횟수, 분포 변경 빈도와 전체 추출 횟수를 함께 봐야 한다.

## 실제 적용 사례

슬롯 시뮬레이터는 같은 가중치 표에서 선택을 매우 많이 반복했다.
초기화할 때 Alias 표를 만들고 반복 경로에서는 상수 시간 선택만 수행하도록 분리했다.

[슬롯 스핀 성능 최적화](../task/nsc-slot/slot-spin-performance.md)

## 참고 자료

- [A. J. Walker, New fast method for generating discrete random numbers with arbitrary frequency distributions](https://doi.org/10.1049/el:19740097)
- [M. D. Vose, A linear algorithm for generating random numbers with a given distribution](https://doi.org/10.1109/32.92917)
