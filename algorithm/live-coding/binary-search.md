# [초안] 라이브 코딩 완전 정복: Binary Search — Java 백엔드 인터뷰 실전 가이드

---

## 1. 왜 Binary Search인가

알고리즘 인터뷰에서 이진 탐색은 단순히 "정렬된 배열에서 값 찾기"가 아니다. 실제 인터뷰에서 이진 탐색이 등장하는 맥락은 훨씬 넓다.

- **정렬된 자료구조에서 탐색**: `O(N)` 선형 탐색이 가능한 상황인데도 면접관이 "더 빠르게 할 수 있나요?"라고 묻는다면, 이진 탐색이 정답일 확률이 높다.
- **범위 압축 (Answer Binary Search)**: "최솟값을 최대화하라", "최소 비용으로 조건을 만족하라"는 유형의 최적화 문제에서 **정답 범위 자체를 이진 탐색**한다.
- **Lower Bound / Upper Bound**: 중복이 있는 배열에서 특정 값이 처음 등장하는 위치, 마지막 등장하는 위치를 구할 때 사용한다. Java의 `Collections.binarySearch`는 이 경계를 보장하지 않기 때문에 직접 구현해야 하는 경우가 많다.

HackerRank, 코딩 인터뷰 환경에서 이진 탐색 문제를 받았을 때 30분 안에 깔끔하게 구현하고 설명할 수 있어야 한다. 이 문서는 그 목적에 집중한다.

---

## 2. 핵심 개념: 이진 탐색이란

이진 탐색의 전제는 **탐색 공간에 단조성(monotonicity)이 존재한다**는 것이다. 즉, 어떤 조건 `f(x)`가 있을 때 `x`가 증가하면 `f(x)`도 단조 증가(또는 단조 감소)한다면, 이진 탐색으로 경계를 찾을 수 있다.

정렬된 배열 `[1, 3, 5, 7, 9]`에서 `5`를 찾는 과정을 단계별로 따라가 보자.

```
배열: [1, 3, 5, 7, 9]
       0  1  2  3  4

lo = 0, hi = 4

step 1: mid = (0 + 4) / 2 = 2 → arr[2] = 5 → 목표값과 일치 → 반환
```

만약 `6`을 찾는다면:

```
step 1: mid = 2 → arr[2] = 5 < 6 → lo = mid + 1 = 3
step 2: mid = (3 + 4) / 2 = 3 → arr[3] = 7 > 6 → hi = mid - 1 = 2
step 3: lo(3) > hi(2) → 루프 종료 → 없음
```

매 단계마다 탐색 범위가 절반으로 줄어든다. `N`개 원소에서 최대 `log₂(N)` 번만 비교하면 된다.

---

## 3. 기본 구현 — 정렬된 배열에서 값 찾기

```java
public int binarySearch(int[] arr, int target) {
    int lo = 0, hi = arr.length - 1;

    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2; // overflow 방지: (lo + hi) / 2 대신

        if (arr[mid] == target) {
            return mid;
        } else if (arr[mid] < target) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }

    return -1; // 없음
}
```

**핵심 포인트 3가지:**

1. `mid = lo + (hi - lo) / 2` — `lo + hi`가 `Integer.MAX_VALUE`를 넘을 수 있으므로 overflow를 방지하는 이 방식을 항상 사용한다.
2. `while (lo <= hi)` — `lo == hi`일 때도 원소 하나가 남아 있으므로 검사해야 한다.
3. `lo = mid + 1`, `hi = mid - 1` — mid는 이미 확인했으므로 제외한다. `lo = mid`나 `hi = mid`로 쓰면 무한 루프에 빠질 수 있다.

---

## 4. Lower Bound와 Upper Bound

중복 원소가 있는 배열 `[1, 2, 2, 2, 3, 5]`에서 `2`의 첫 번째 위치와 마지막 위치를 각각 구해야 하는 경우가 있다.

- **Lower Bound**: `target` 이상인 값이 처음 등장하는 인덱스
- **Upper Bound**: `target` 초과인 값이 처음 등장하는 인덱스

### Lower Bound 구현

"target보다 작은 원소"는 왼쪽에 버리고, "target 이상인 원소"는 오른쪽 후보로 유지하면서 범위를 좁힌다.

```java
// target 이상인 값이 처음 나오는 인덱스 반환
// 모든 원소가 target 미만이면 arr.length 반환
public int lowerBound(int[] arr, int target) {
    int lo = 0, hi = arr.length; // hi = length (인덱스 밖까지 포함)

    while (lo < hi) { // lo < hi: lo == hi 되면 답이 확정
        int mid = lo + (hi - lo) / 2;

        if (arr[mid] < target) {
            lo = mid + 1; // mid는 너무 작으므로 제외
        } else {
            hi = mid; // mid가 후보가 될 수 있으므로 유지
        }
    }

    return lo; // lo == hi 인 시점이 답
}
```

```
배열: [1, 2, 2, 2, 3, 5], target = 2
       0  1  2  3  4  5

lo=0, hi=6
mid=3 → arr[3]=2 >= 2 → hi=3
mid=1 → arr[1]=2 >= 2 → hi=1
mid=0 → arr[0]=1 < 2 → lo=1
lo==hi==1 → 반환 1
```

### Upper Bound 구현

"target 이하인 원소"는 왼쪽에 버리고, "target 초과인 원소"는 오른쪽 후보로 유지한다.

```java
// target 초과인 값이 처음 나오는 인덱스 반환
public int upperBound(int[] arr, int target) {
    int lo = 0, hi = arr.length;

    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;

        if (arr[mid] <= target) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }

    return lo;
}
```

두 함수를 이용하면 `target`이 배열에 등장하는 횟수를 `O(log N)`에 구할 수 있다:

```java
int count = upperBound(arr, target) - lowerBound(arr, target);
```

---

## 5. Answer Binary Search (정답 이진 탐색)

이 패턴은 라이브 코딩 인터뷰에서 고득점을 받는 핵심 기술이다. 문제 형태는 주로 이렇다:

> "조건을 만족하는 최솟값(또는 최댓값)을 구하라."

아이디어는 **정답이 될 수 있는 값의 범위**를 탐색 공간으로 삼고, "이 값이 조건을 만족하는가"를 판별 함수 `check(x)`로 분리하는 것이다.

일반적인 골격:

```java
int lo = 최솟값_가능한_범위, hi = 최댓값_가능한_범위;

while (lo < hi) {
    int mid = lo + (hi - lo) / 2;

    if (check(mid)) {
        hi = mid;        // mid가 조건 만족 → 더 작은 값도 가능한지 탐색
    } else {
        lo = mid + 1;    // mid가 조건 미만 → 더 큰 값 필요
    }
}

// lo == hi: 조건을 만족하는 최솟값
return lo;
```

`check(x)` 함수의 반환값이 단조적이어야 이 패턴이 유효하다. 즉, `check(k) == true`이면 `check(k+1) == true`도 보장되어야 한다.

---

## 6. 자주 나오는 구현 버그

### 버그 1: `mid = (lo + hi) / 2` — Integer Overflow

```java
// 잘못된 예
int mid = (lo + hi) / 2; // lo=1_500_000_000, hi=1_500_000_000 → overflow

// 올바른 예
int mid = lo + (hi - lo) / 2;
```

### 버그 2: `while (lo < hi)` vs `while (lo <= hi)` 혼용

- 기본 탐색(정확한 값 찾기): `lo <= hi`, `hi = mid - 1`
- Lower/Upper Bound 및 Answer Binary Search: `lo < hi`, `hi = mid`

두 패턴을 구분하지 않고 혼용하면 루프가 하나 적게 돌거나 무한 루프에 빠진다.

### 버그 3: `hi = mid` 써야 할 곳에 `hi = mid - 1` 쓰기

Lower Bound에서 `arr[mid] >= target`일 때 `mid`가 정답 후보다. `hi = mid - 1`로 쓰면 정답을 버리게 된다.

```java
// 잘못된 예 — mid가 정답인 경우를 버림
if (arr[mid] >= target) hi = mid - 1;

// 올바른 예
if (arr[mid] >= target) hi = mid;
```

### 버그 4: `hi` 초기값을 `arr.length - 1`로 제한

Lower/Upper Bound 탐색에서 모든 원소가 target보다 작은 경우, 정답 인덱스는 `arr.length`가 된다. 초기 `hi = arr.length - 1`로 설정하면 이 케이스를 놓친다.

```java
// 잘못된 예
int hi = arr.length - 1; // 모든 원소가 target 미만인 경우 정답 반환 불가

// 올바른 예
int hi = arr.length;
```

---

## 7. 나쁜 예 vs 개선된 예

### 나쁜 예: 재귀로 짠 이진 탐색

```java
// 재귀 구현 — 불필요한 복잡도, overflow 버그 포함
public int binarySearchRecursive(int[] arr, int lo, int hi, int target) {
    if (lo > hi) return -1;
    int mid = (lo + hi) / 2; // overflow 버그
    if (arr[mid] == target) return mid;
    if (arr[mid] < target) return binarySearchRecursive(arr, mid + 1, hi, target);
    return binarySearchRecursive(arr, lo, mid - 1, target);
}
```

문제점:
- `(lo + hi) / 2` overflow 위험
- 라이브 코딩에서 반복문이 더 명확하고 빠르게 작성된다
- 면접관이 "반복문으로 바꿔보세요"라고 요청하는 경우가 있다

### 개선된 예: 반복문 기반, 명시적 경계 처리

```java
public int binarySearch(int[] arr, int target) {
    int lo = 0, hi = arr.length - 1;

    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;

        if (arr[mid] == target) return mid;
        else if (arr[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }

    return -1;
}
```

---

## 8. 로컬 연습 환경 구성

Java 11 이상 환경에서 단일 파일로 바로 실행할 수 있다.

```bash
# JDK 확인
java -version

# 단일 파일 실행 (Java 11+)
java BinarySearchPractice.java
```

`BinarySearchPractice.java`

```java
public class BinarySearchPractice {

    static int binarySearch(int[] arr, int target) {
        int lo = 0, hi = arr.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (arr[mid] == target) return mid;
            else if (arr[mid] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }

    static int lowerBound(int[] arr, int target) {
        int lo = 0, hi = arr.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (arr[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    static int upperBound(int[] arr, int target) {
        int lo = 0, hi = arr.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (arr[mid] <= target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        int[] arr = {1, 2, 2, 2, 3, 5};

        System.out.println(binarySearch(arr, 2));      // 1 또는 2 또는 3 (구현에 따라)
        System.out.println(lowerBound(arr, 2));         // 1
        System.out.println(upperBound(arr, 2));         // 4
        System.out.println(upperBound(arr, 2) - lowerBound(arr, 2)); // 3 (등장 횟수)
    }
}
```

---

## 9. 라이브 인터뷰에서 말하는 법

라이브 코딩 인터뷰에서는 코드를 치는 것만큼이나 **생각을 소리로 표현하는 것**이 중요하다. 면접관은 당신이 어떻게 사고하는지를 평가한다.

### 문제를 받았을 때 (처음 1~2분)

```
"이 배열은 정렬되어 있으니 이진 탐색이 적합할 것 같습니다.
시간 복잡도는 O(log N)이고, 공간 복잡도는 O(1)입니다.
엣지 케이스로는 빈 배열, target이 범위 밖에 있는 경우를 고려하겠습니다."
```

### 구현 중

```
"lo와 hi로 탐색 범위를 유지합니다.
mid는 lo + (hi - lo) / 2로 계산해서 overflow를 방지합니다.
arr[mid]가 target보다 작으면 lo를 올려서 오른쪽을 탐색하고,
크면 hi를 내려서 왼쪽을 탐색합니다."
```

### 구현 후 검증

```
"예시 배열로 직접 따라가 보겠습니다.
[1, 3, 5, 7], target = 5
lo=0, hi=3, mid=1 → arr[1]=3 < 5 → lo=2
lo=2, hi=3, mid=2 → arr[2]=5 == 5 → 반환 2. 맞습니다."
```

### 면접관이 "더 개선할 수 있나요?" 물을 때

```
"이 문제에서는 O(log N)이 이미 최적입니다.
만약 중복 원소가 있고 첫 번째 위치를 찾아야 한다면,
Lower Bound 변형으로 바꿀 수 있습니다.
그 경우 while 조건과 hi 갱신 방식을 조금 바꾸면 됩니다."
```

### 막히는 순간 대처 패턴

| 막히는 상황 | 즉각 말할 내용 |
|------------|---------------|
| lower bound vs upper bound 헷갈림 | "잠깐 lo < hi 패턴으로 작성하겠습니다. arr[mid] < target이면 lo를 올리고, 아니면 hi를 mid로 설정합니다." |
| 무한 루프 발생 | "lo = mid + 1이 되어야 하는데 제가 mid로 썼네요. 수정하겠습니다." |
| 경계값 결과가 이상함 | "lo = 0, hi = 3 트레이싱을 다시 해보겠습니다." (실제로 트레이싱) |
| 문제 자체가 이해 안 됨 | "이 조건을 예시와 함께 확인할게요. 입력이 X이면 출력이 Y여야 한다는 의미인가요?" (질문) |

---

## 10. 연습 문제 1 (Easy): 정렬된 배열에서 타겟의 위치 찾기

### 문제

정수 배열 `nums`와 정수 `target`이 주어진다.  
`nums`는 오름차순으로 정렬되어 있으며 중복 원소가 없다.  
`target`이 배열에 존재하면 그 인덱스를, 존재하지 않으면 `-1`을 반환하라.  
**시간 복잡도 O(log N)을 만족해야 한다.**

```
입력: nums = [-1, 0, 3, 5, 9, 12], target = 9
출력: 4

입력: nums = [-1, 0, 3, 5, 9, 12], target = 2
출력: -1
```

**제약:**
- `1 <= nums.length <= 10^4`
- `-10^4 < nums[i], target < 10^4`
- `nums`의 모든 원소는 유일하다.

**힌트:** 기본 이진 탐색 그대로다. `lo <= hi` 루프, `mid` 계산, 세 가지 분기를 구현한다.

<details>
<summary>풀이 및 Java 코드 보기</summary>

### 접근 방식

정렬된 배열에서 정확한 값을 찾는 가장 기본적인 이진 탐색이다. 세 가지 분기:
1. `arr[mid] == target` → 찾음
2. `arr[mid] < target` → 오른쪽 탐색
3. `arr[mid] > target` → 왼쪽 탐색

루프가 끝날 때까지 못 찾으면 `-1` 반환.

### Java 코드

```java
public class Solution {
    public int search(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;

        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;

            if (nums[mid] == target) {
                return mid;
            } else if (nums[mid] < target) {
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }

        return -1;
    }

    // 테스트
    public static void main(String[] args) {
        Solution sol = new Solution();
        int[] nums1 = {-1, 0, 3, 5, 9, 12};
        System.out.println(sol.search(nums1, 9));   // 4
        System.out.println(sol.search(nums1, 2));   // -1

        int[] nums2 = {5};
        System.out.println(sol.search(nums2, 5));   // 0
        System.out.println(sol.search(nums2, 3));   // -1
    }
}
```

### 복잡도

- 시간: `O(log N)` — 매 반복마다 탐색 범위가 절반으로 줄어든다
- 공간: `O(1)` — 추가 메모리 없음

### 흔한 실수

- `mid = (lo + hi) / 2` — overflow 가능
- `while (lo < hi)` — `lo == hi`일 때 원소 하나가 남는 케이스를 놓침
- `lo = mid`, `hi = mid` — 무한 루프 발생

</details>

---

## 11. 연습 문제 2 (Medium): 정렬된 배열에서 타겟 범위 찾기

### 문제

정수 배열 `nums`와 정수 `target`이 주어진다.  
`nums`는 오름차순으로 정렬되어 있으며 중복 원소가 있을 수 있다.  
`target`이 배열에서 나타나는 **시작 인덱스와 끝 인덱스**를 `[start, end]` 형식으로 반환하라.  
`target`이 없으면 `[-1, -1]`을 반환하라.  
**시간 복잡도 O(log N)을 만족해야 한다.**

```
입력: nums = [5, 7, 7, 8, 8, 10], target = 8
출력: [3, 4]

입력: nums = [5, 7, 7, 8, 8, 10], target = 6
출력: [-1, -1]

입력: nums = [], target = 0
출력: [-1, -1]
```

**제약:**
- `0 <= nums.length <= 10^5`
- `-10^9 <= nums[i] <= 10^9`
- `nums`는 오름차순 정렬

**힌트:** Lower Bound와 Upper Bound를 각각 한 번씩 호출하면 된다. 단, target이 존재하지 않는 경우를 별도로 처리해야 한다.

<details>
<summary>풀이 및 Java 코드 보기</summary>

### 접근 방식

두 가지 이진 탐색을 조합한다:

1. `lowerBound(nums, target)` → target 이상인 첫 인덱스 `L`
2. `upperBound(nums, target)` → target 초과인 첫 인덱스 `R`

target의 등장 범위는 `[L, R-1]`이 된다.  
단, `L >= nums.length` 이거나 `nums[L] != target`이면 target이 없는 것이므로 `[-1, -1]`을 반환한다.

### Java 코드

```java
public class Solution {

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

    public int[] searchRange(int[] nums, int target) {
        if (nums.length == 0) return new int[]{-1, -1};

        int L = lowerBound(nums, target);

        // L이 배열 밖이거나 target과 다른 값이면 없음
        if (L == nums.length || nums[L] != target) {
            return new int[]{-1, -1};
        }

        int R = upperBound(nums, target) - 1;
        return new int[]{L, R};
    }

    // 테스트
    public static void main(String[] args) {
        Solution sol = new Solution();

        int[] nums1 = {5, 7, 7, 8, 8, 10};
        System.out.println(java.util.Arrays.toString(sol.searchRange(nums1, 8)));   // [3, 4]
        System.out.println(java.util.Arrays.toString(sol.searchRange(nums1, 7)));   // [1, 2]
        System.out.println(java.util.Arrays.toString(sol.searchRange(nums1, 6)));   // [-1, -1]

        int[] nums2 = {};
        System.out.println(java.util.Arrays.toString(sol.searchRange(nums2, 0)));   // [-1, -1]

        int[] nums3 = {2, 2};
        System.out.println(java.util.Arrays.toString(sol.searchRange(nums3, 2)));   // [0, 1]
    }
}
```

### 복잡도

- 시간: `O(log N)` — 이진 탐색 두 번 = `2 * O(log N)`
- 공간: `O(1)`

### 라이브 인터뷰에서 말하는 방식

```
"중복이 있으니 단순 이진 탐색으로는 경계를 보장할 수 없습니다.
Lower Bound로 target 이상이 처음 나오는 위치를 구하고,
Upper Bound로 target 초과가 처음 나오는 위치를 구합니다.
그 사이 범위 [L, R-1]이 target의 등장 구간이 됩니다.
존재 여부는 L이 배열 범위 내에 있고 nums[L] == target인지로 판별합니다."
```

### 흔한 실수

- `lowerBound`에서 `hi = arr.length - 1`로 초기화 → 모든 원소가 target 미만인 경우 누락
- target 존재 여부 확인을 빠트림 → `nums[L] != target`인 경우에도 L을 반환
- `upperBound - 1`을 빠트리고 `[L, R]` 반환 → off-by-one

</details>

---

## 12. 인터뷰 답변 프레임

### "이진 탐색은 언제 쓰나요?"

> "탐색 공간에 단조성이 있을 때 씁니다. 가장 전형적인 경우는 정렬된 배열에서 값을 찾는 것이고, 더 넓게는 '조건을 만족하는 최소값을 구하라'는 최적화 문제에서도 정답 범위를 이진 탐색 공간으로 삼을 수 있습니다. 핵심은 check(x) 함수가 단조적이어야 한다는 것입니다."

### "Lower Bound와 Upper Bound의 차이는요?"

> "둘 다 이진 탐색이지만 경계 조건이 다릅니다. Lower Bound는 target 이상인 값이 처음 나오는 인덱스, Upper Bound는 target 초과인 값이 처음 나오는 인덱스입니다. 차이는 비교 연산자 하나입니다. `arr[mid] < target`이면 lo를 올리고, `arr[mid] <= target`이면 lo를 올립니다. Java 표준 라이브러리의 `binarySearch`는 중복이 있을 때 어느 인덱스를 반환할지 보장하지 않기 때문에, 경계가 중요한 경우에는 직접 구현합니다."

### "시간 복잡도 O(log N)을 어떻게 설명하나요?"

> "매 반복마다 탐색 범위가 절반으로 줄어듭니다. N개 원소를 절반씩 줄이면 최대 log₂(N)번 만에 범위가 1로 줄어들기 때문에 O(log N)입니다. 실용적으로는 배열 크기가 10억이어도 약 30번의 비교로 탐색이 끝납니다."

---

## 13. 체크리스트

라이브 코딩 인터뷰 직전에 이 항목들을 빠르게 점검한다.

- [ ] `mid = lo + (hi - lo) / 2` — overflow 방지 공식 암기
- [ ] 기본 탐색: `while (lo <= hi)`, `hi = mid - 1`
- [ ] Lower/Upper Bound: `while (lo < hi)`, `hi = mid` 또는 `lo = mid + 1`
- [ ] Lower Bound 초기 `hi = arr.length` (length - 1이 아님)
- [ ] target 존재 여부 확인: `L < arr.length && arr[L] == target`
- [ ] Answer Binary Search: `check(mid)` 함수를 먼저 분리해서 정의
- [ ] 엣지 케이스: 빈 배열, 원소 하나짜리 배열, target이 범위 밖
- [ ] 간단한 예시로 손 추적(hand trace) 후 제출
- [ ] 말하면서 짜기: lo/hi 갱신 이유를 설명하며 작성

---

*이 문서는 CJ OliveYoung 백엔드 인터뷰 준비를 위한 알고리즘 라이브 코딩 시리즈 중 Binary Search 편이다.*
