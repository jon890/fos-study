# [초안] 이진 탐색 완전 정복 — Java 라이브 코딩 인터뷰 준비 가이드

---

## 왜 이진 탐색인가

이진 탐색은 알고리즘 인터뷰에서 가장 자주 나오는 주제 중 하나다. 단순히 "정렬된 배열에서 값을 찾는다"는 개념을 넘어서, 실무 백엔드에서도 의미 있게 쓰인다. DB 인덱스의 B+Tree 탐색, 로그 파일에서 특정 시간대 로그 범위 조회, 배포 바이너리의 특정 버전 탐색 등이 모두 이진 탐색의 응용이다.

인터뷰에서 이진 탐색이 위험한 이유는 **"알고 있는데 코드를 틀리는"** 패턴 때문이다. off-by-one 버그, 무한 루프, lower bound와 upper bound의 혼동 — 이 세 가지가 현장에서 망하는 원인 80%를 차지한다. 이 문서는 개념 정리보다 **버그 없이 짜는 법**에 집중한다.

---

## 핵심 개념: 이진 탐색이 성립하는 조건

이진 탐색이 가능하려면 **단조성(monotonicity)** 이 있어야 한다. 정렬된 배열은 단조 증가하는 가장 기본적인 예시다. 그러나 이 단조성은 배열이 아니어도 성립할 수 있다.

```
조건 f(x)가 어떤 경계점 k를 기준으로
x < k 이면 false, x >= k 이면 true (또는 그 반대)
```

이 패턴이 성립하는 문제라면 이진 탐색 적용이 가능하다. 숫자 배열, 정수 범위, 날짜 범위, 심지어 파라미터 조합까지 탐색 공간이 될 수 있다.

**이진 탐색을 쓸 시그널:**

- 문제에서 "정렬된"이라는 단어가 나온다.
- "최솟값 중 최대", "최댓값 중 최소" 같은 최적화 표현이 나온다.
- 탐색 범위가 정수 구간이고 조건을 O(n) 이하로 검증할 수 있다.
- 배열에서 특정 범위의 첫 번째 또는 마지막 위치를 찾아야 한다.

---

## 기본 이진 탐색: 정렬된 배열에서 값 찾기

가장 기본적인 형태부터 버그 없이 구현하는 방법을 익힌다.

### 구현 템플릿

```java
public int binarySearch(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;

    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2; // overflow 방지: (lo + hi) / 2 하면 안 된다

        if (nums[mid] == target) {
            return mid;
        } else if (nums[mid] < target) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }

    return -1; // not found
}
```

**왜 `(lo + hi) / 2`가 위험한가?**

Java에서 `int`는 32비트다. `lo = 1_500_000_000`, `hi = 2_000_000_000`이면 합이 `Integer.MAX_VALUE`(약 21억)를 넘어 오버플로가 발생한다. `lo + (hi - lo) / 2`는 이 문제를 회피한다. 라이브 코딩에서 면접관이 반드시 체크하는 포인트다.

---

## Lower Bound와 Upper Bound

실무에서 더 자주 쓰이는 패턴이다. 단순히 "있냐 없냐"가 아니라 **처음 등장 위치**나 **마지막 등장 위치**를 찾는 쿼리가 훨씬 많다. 예를 들어 날짜 범위로 로그를 슬라이싱할 때 정확히 이 패턴을 쓴다.

### Lower Bound: target 이상인 첫 번째 인덱스

```java
// nums에서 target 이상인 값이 처음 등장하는 인덱스 반환
// 모든 값이 target보다 작으면 nums.length 반환
public int lowerBound(int[] nums, int target) {
    int lo = 0, hi = nums.length; // hi = length (not length - 1)

    while (lo < hi) { // not lo <= hi
        int mid = lo + (hi - lo) / 2;

        if (nums[mid] < target) {
            lo = mid + 1;
        } else {
            hi = mid; // mid 자체가 후보일 수 있으므로 hi = mid - 1 하면 안 된다
        }
    }

    return lo;
}
```

### Upper Bound: target 초과인 첫 번째 인덱스

```java
// nums에서 target보다 큰 값이 처음 등장하는 인덱스 반환
public int upperBound(int[] nums, int target) {
    int lo = 0, hi = nums.length;

    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;

        if (nums[mid] <= target) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }

    return lo;
}
```

### 두 경계를 이용해 개수 세기

```java
// nums에서 target의 등장 횟수
public int countOccurrences(int[] nums, int target) {
    return upperBound(nums, target) - lowerBound(nums, target);
}
```

배열 `[1, 2, 2, 2, 3, 4]`에서 `target = 2`라면:
- `lowerBound` → 1 (인덱스)
- `upperBound` → 4 (인덱스)
- count → 3

이 패턴을 이해하면 면접관이 "중복이 있어도 되냐?"고 물어볼 때 자신 있게 답할 수 있다.

---

## Lower/Upper Bound의 직관: 문을 닫는 방향

두 구현의 차이는 **`mid`를 발견했을 때 문을 어느 방향으로 닫느냐**에 있다.

| 패턴 | 발견 시 동작 | 의미 |
|---|---|---|
| 기본 탐색 | `return mid` | 정확히 일치하는 값 반환 |
| lower bound | `hi = mid` | 더 왼쪽에 있을 수 있으므로 오른쪽을 좁힘 |
| upper bound | `lo = mid + 1` | `mid`는 아직 target 이하이므로 왼쪽을 좁힘 |

이 직관이 잡히면 변형 문제에서도 헷갈리지 않는다.

---

## 정답 이진 탐색 (Answer Binary Search)

"가능한 정답의 범위"를 탐색 공간으로 삼아, 조건 함수로 실현 가능 여부를 검증하는 패턴이다. 코딩 테스트에서 "파라미터 최솟값을 구하라" 또는 "최대 몇 명까지 수용 가능하냐"류 문제가 여기 해당한다.

### 템플릿

```java
public int answerBinarySearch(int lo, int hi) {
    // lo: 가능한 최솟값, hi: 가능한 최댓값

    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;

        if (isPossible(mid)) {
            hi = mid;       // mid가 가능하면 더 작은 값도 가능할 수 있다 (최솟값 탐색)
        } else {
            lo = mid + 1;   // mid가 불가능하면 더 큰 값으로
        }
    }

    return lo;
}

private boolean isPossible(int candidate) {
    // O(n) 또는 O(n log n) 검증 로직
    // ...
    return true;
}
```

최댓값을 탐색할 때는 `isPossible`이 true일 때 `lo = mid`로 반전시키면 된다. 단, 이 경우 `mid = lo + (hi - lo + 1) / 2`로 올림 계산을 써야 무한 루프를 피할 수 있다.

---

## 흔한 버그 패턴 5가지

### 1. `(lo + hi) / 2` 오버플로

앞서 설명했다. 항상 `lo + (hi - lo) / 2`를 쓴다.

### 2. `lo <= hi` vs `lo < hi` 혼동

기본 탐색(정확한 값 찾기)은 `lo <= hi`, lower/upper bound는 `lo < hi`를 쓴다. 이유: lower bound에서 `hi = nums.length`로 초기화하므로 `nums[hi]` 접근이 범위 밖이다. `lo < hi`일 때 루프가 끝나면 `lo == hi`이고 이것이 답이다.

### 3. `hi = mid` vs `hi = mid - 1` 혼동

lower bound에서 `nums[mid] >= target`이면 `hi = mid`다. `mid - 1`로 줄이면 답 자체가 버려진다.

### 4. 무한 루프

answer binary search에서 최댓값을 탐색할 때 `lo = mid`로 업데이트하고 `mid = lo + (hi - lo) / 2`를 쓰면 `lo == hi - 1`일 때 `mid = lo`로 계속 반복된다. 이 경우 `mid = lo + (hi - lo + 1) / 2`로 올림을 써야 탈출한다.

### 5. 빈 배열 처리 누락

`nums.length == 0`일 때 `lo = 0`, `hi = -1`이면 기본 탐색에서는 즉시 루프를 빠져나오므로 괜찮다. 그러나 lower/upper bound에서 `hi = nums.length = 0`이면 루프 자체가 실행되지 않고 0을 반환한다. 호출 측에서 0과 "빈 배열"을 구분할 수 있도록 반환값 의미를 명확히 정의해야 한다.

---

## 라이브 인터뷰에서 말하는 법

라이브 코딩에서 침묵은 최악이다. 면접관은 코드 결과보다 **사고 과정**을 본다. 다음은 이진 탐색 문제에서 쓸 수 있는 실전 멘트 흐름이다.

**1단계 — 조건 확인:**
> "배열이 정렬되어 있다고 하셨으니 이진 탐색 적용이 가능해 보입니다. 중복 값이 있나요? 있다면 첫 번째 위치를 반환해야 하나요, 아무 위치나 괜찮은가요?"

**2단계 — 경계 설정 소리 내어 하기:**
> "`lo = 0`, `hi = nums.length - 1`로 잡겠습니다. `mid`는 오버플로 방지를 위해 `lo + (hi - lo) / 2`로 계산합니다."

**3단계 — 루프 종료 조건 설명:**
> "정확한 값을 찾는 거라서 `lo <= hi`로 합니다. 같을 때도 한 번 더 확인이 필요하니까요."

**4단계 — 엣지 케이스 먼저 말하기:**
> "빈 배열, 원소가 하나인 배열, target이 최솟값보다 작거나 최댓값보다 큰 경우를 체크하겠습니다."

**5단계 — 작성 후 테스트 케이스 한 줄로 트레이싱:**
> "배열 `[1,3,5,7,9]`, target `5`로 돌려볼게요. lo=0, hi=4 → mid=2, nums[2]=5, 맞습니다."

침묵보다는 틀린 말이 낫고, 틀린 말보다는 스스로 틀렸다고 인지하고 수정하는 것이 훨씬 낫다. 자신의 사고 과정을 계속 말하라.

---

## 로컬 연습 환경

JDK 17 이상이면 충분하다. IDE 없이 터미널에서 빠르게 돌릴 수 있는 단일 파일 구조를 쓴다.

```bash
# 단일 파일로 컴파일 + 실행
javac BinarySearchPractice.java && java BinarySearchPractice
```

```java
// BinarySearchPractice.java
public class BinarySearchPractice {
    public static void main(String[] args) {
        int[] nums = {1, 2, 2, 2, 3, 4, 5};
        System.out.println(lowerBound(nums, 2)); // 기대: 1
        System.out.println(upperBound(nums, 2)); // 기대: 4
        System.out.println(upperBound(nums, 2) - lowerBound(nums, 2)); // 기대: 3
    }

    static int lowerBound(int[] nums, int target) {
        int lo = 0, hi = nums.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    static int upperBound(int[] nums, int target) {
        int lo = 0, hi = nums.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] <= target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
}
```

HackerRank나 LeetCode 환경은 클래스 선언이 고정되어 있으므로 메서드만 붙여 넣으면 된다.

---

## 실전 연습 문제

---

### 문제 1 (Easy): 정렬된 배열에서 타겟 범위 찾기

**문제 설명**

정렬된 정수 배열 `nums`와 정수 `target`이 주어진다. `target`이 배열에서 등장하는 첫 번째와 마지막 인덱스를 `[first, last]` 형태로 반환하라. 존재하지 않으면 `[-1, -1]`을 반환하라.

```
입력: nums = [5,7,7,8,8,10], target = 8
출력: [3, 4]

입력: nums = [5,7,7,8,8,10], target = 6
출력: [-1, -1]

입력: nums = [], target = 0
출력: [-1, -1]
```

**제약:**
- `0 <= nums.length <= 10^5`
- `nums`는 오름차순 정렬
- 시간 복잡도 O(log n)

**힌트:** lower bound와 upper bound를 각각 한 번씩 호출하면 된다. 반환 전에 실제로 `target`이 존재하는지 검증하는 코드를 잊지 마라.

<details>
<summary>풀이 및 Java 코드 보기</summary>

**접근 방법**

`lowerBound(nums, target)`은 target 이상인 첫 인덱스를 반환한다. 이 위치의 값이 실제로 target과 같으면 등장 범위의 시작이다. `upperBound(nums, target) - 1`이 마지막 인덱스다.

```java
public class SearchRange {
    public int[] searchRange(int[] nums, int target) {
        int first = lowerBound(nums, target);

        // target이 배열에 없는 경우
        if (first == nums.length || nums[first] != target) {
            return new int[]{-1, -1};
        }

        int last = upperBound(nums, target) - 1;
        return new int[]{first, last};
    }

    private int lowerBound(int[] nums, int target) {
        int lo = 0, hi = nums.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    private int upperBound(int[] nums, int target) {
        int lo = 0, hi = nums.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] <= target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    // 테스트
    public static void main(String[] args) {
        SearchRange sr = new SearchRange();
        int[] result1 = sr.searchRange(new int[]{5,7,7,8,8,10}, 8);
        System.out.println(result1[0] + ", " + result1[1]); // 3, 4

        int[] result2 = sr.searchRange(new int[]{5,7,7,8,8,10}, 6);
        System.out.println(result2[0] + ", " + result2[1]); // -1, -1

        int[] result3 = sr.searchRange(new int[]{}, 0);
        System.out.println(result3[0] + ", " + result3[1]); // -1, -1
    }
}
```

**시간 복잡도:** O(log n) — lowerBound와 upperBound 각각 O(log n)  
**공간 복잡도:** O(1)

**면접에서 말할 내용:**
> "lower bound와 upper bound를 별도 메서드로 분리했습니다. `first == nums.length`는 target이 전체 배열보다 크다는 뜻이고, `nums[first] != target`은 target이 배열에 없다는 뜻입니다. 두 조건을 AND로 단락 평가해서 배열 범위 밖 접근을 막았습니다."

</details>

---

### 문제 2 (Medium): 나무 자르기 — 정답 이진 탐색

**문제 설명**

나무꾼이 `n`개의 나무를 자르려 한다. 각 나무의 높이는 배열 `heights`로 주어진다. 나무꾼은 절단기 높이 `H`를 설정하면, `H`보다 높은 나무는 `(나무 높이 - H)` 만큼 잘려 나간다. `H` 이하인 나무는 잘리지 않는다. 나무꾼이 최소 `m` 미터의 목재를 가져가야 할 때, 설정 가능한 절단기 높이의 최댓값을 구하라.

```
입력: heights = [20, 15, 10, 17], m = 7
출력: 15
설명: H=15로 설정하면 [5, 0, 0, 2] → 합계 7. 정확히 m을 만족하는 최댓값.

입력: heights = [4, 42, 40, 26, 46], m = 20
출력: 36
```

**제약:**
- `1 <= heights.length <= 10^6`
- `1 <= heights[i] <= 10^9`
- `1 <= m <= sum(heights)`

**힌트:** H가 커질수록 수확량이 줄어든다 — 단조 감소 함수다. "H를 최대로 높이되 수확량이 m 이상"을 만족하는 최댓값을 찾는다. 탐색 범위는 `[0, max(heights)]`.

<details>
<summary>풀이 및 Java 코드 보기</summary>

**접근 방법**

절단기 높이 H가 증가할수록 수확량은 감소한다. 이 단조성을 이용해 "수확량 >= m을 만족하는 H 중 최댓값"을 이진 탐색한다.

탐색 공간: `[0, max(heights)]`  
검증 함수: `canHarvest(H) → sum(max(0, h - H) for each h) >= m`

최댓값을 탐색하므로 `isPossible`이 true일 때 `lo = mid`, false일 때 `hi = mid - 1`. 이때 무한 루프를 피하기 위해 `mid = lo + (hi - lo + 1) / 2`를 쓴다.

```java
public class WoodCutting {

    public int maxHeight(int[] heights, long m) {
        int lo = 0;
        int hi = 0;
        for (int h : heights) hi = Math.max(hi, h);

        while (lo < hi) {
            // 최댓값 탐색: 올림 mid로 무한 루프 방지
            int mid = lo + (hi - lo + 1) / 2;

            if (canHarvest(heights, mid, m)) {
                lo = mid; // mid가 가능하면 더 높은 H를 시도
            } else {
                hi = mid - 1; // mid가 불가능하면 낮춰야 함
            }
        }

        return lo;
    }

    private boolean canHarvest(int[] heights, int H, long m) {
        long total = 0;
        for (int h : heights) {
            if (h > H) total += (h - H);
        }
        return total >= m;
    }

    // 테스트
    public static void main(String[] args) {
        WoodCutting wc = new WoodCutting();
        System.out.println(wc.maxHeight(new int[]{20, 15, 10, 17}, 7)); // 15
        System.out.println(wc.maxHeight(new int[]{4, 42, 40, 26, 46}, 20)); // 36
    }
}
```

**주의할 버그 포인트:**

1. `total`을 `long`으로 선언해야 한다. `heights[i]`가 최대 10^9이고 배열 길이가 10^6이면 합계가 `long` 범위를 필요로 한다.
2. `canHarvest` 내에서 `h - H`가 음수가 되면 수확량이 없으므로 `if (h > H)` 조건이 필요하다. 음수를 더하면 목표를 잘못 계산한다.
3. `mid = lo + (hi - lo + 1) / 2` — 올림 mid. `lo = 0, hi = 1`이면 내림 mid는 0이 되어 `lo = mid = 0`으로 무한 루프에 빠진다. 올림은 `mid = 1`이 되어 루프를 탈출한다.

**시간 복잡도:** O(n log(max_height))  
**공간 복잡도:** O(1)

**면접에서 말할 내용:**
> "H가 커지면 수확량이 줄어드는 단조 감소 관계라서 이진 탐색이 적용됩니다. 최댓값 탐색 패턴이라서 `mid`를 올림으로 계산했습니다. 내림으로 하면 `lo = mid`일 때 lo가 변하지 않아 무한 루프가 발생합니다. 수확량 합산에 `long`을 쓴 이유는 입력 범위가 int 최댓값을 넘을 수 있어서입니다."

</details>

---

## 인터뷰 답변 프레이밍 (시니어 백엔드 관점)

면접관이 "이진 탐색을 언제 쓰나요?"라고 물으면 단순히 "정렬된 배열에서 값을 찾을 때"라고 답하면 주니어 수준이다. 시니어답게 확장하려면:

> "이진 탐색은 탐색 공간에 단조성이 있을 때 O(log n)으로 줄여주는 기법입니다. 실무에서는 직접 배열을 탐색하는 것 외에도, 예를 들어 '특정 응답 시간을 유지하면서 최대 몇 개의 동시 요청을 처리할 수 있냐'는 파라미터 탐색에도 쓸 수 있습니다. 검증 함수 하나만 만들 수 있으면 탐색 공간이 정수 범위라도 적용됩니다. DB에서 커버링 인덱스를 탐색할 때 내부적으로 B+Tree에서 이진 탐색이 일어나는 것과 같은 원리입니다."

이 답변은 알고리즘 지식과 실무 연결, DB 이해까지 한 번에 보여준다.

---

## 체크리스트

인터뷰 전 스스로 점검:

- [ ] `(lo + hi) / 2` 대신 `lo + (hi - lo) / 2`를 무조건 쓴다
- [ ] 기본 탐색과 lower/upper bound의 루프 조건(`<=` vs `<`)을 구분할 수 있다
- [ ] lower bound에서 발견 시 `hi = mid`이고 `hi = mid - 1`이 아님을 설명할 수 있다
- [ ] answer binary search에서 최솟값과 최댓값 탐색 패턴을 구분할 수 있다
- [ ] 최댓값 탐색에서 올림 mid가 필요한 이유를 말로 설명할 수 있다
- [ ] 빈 배열, 단일 원소 배열, 타겟이 범위 밖인 경우를 처리할 수 있다
- [ ] 수확량 합산 등 누적 계산에서 `int` 오버플로를 `long`으로 방지할 수 있다
- [ ] 문제를 받으면 먼저 "정렬/단조성이 있는가?"를 체크하는 습관이 있다
- [ ] 트레이싱을 소리 내어 진행하면서 버그를 현장에서 잡을 수 있다
