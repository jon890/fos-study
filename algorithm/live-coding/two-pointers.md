# [초안] Two Pointers — 라이브 코딩 완전 정복 가이드 (Java)

## 왜 Two Pointers인가

알고리즘 라이브 코딩 면접에서 배열이나 문자열 관련 문제가 나왔을 때, 가장 먼저 고려해야 하는 패턴 중 하나가 Two Pointers다. 이유는 간단하다. O(n²) 브루트 포스 접근을 O(n)으로 줄여주는 가장 직관적인 기법이면서, 코드 자체가 짧고 구조가 명확해서 라이브 코딩 환경에서 빠르게 작성하고 설명하기 쉽다.

면접관 입장에서 Two Pointers를 묻는 이유는 크게 두 가지다.

첫째, 후보자가 "배열을 처음부터 끝까지 훑는다"는 단순한 발상에서 벗어나, 자료의 특성(정렬 여부, 단조성 등)을 활용해 탐색 공간을 줄이는 사고를 할 수 있는지 확인하기 위해서다. 둘째, 포인터 이동 조건과 경계 조건을 실수 없이 구현하는 구현력을 보기 위해서다. 실무에서도 대용량 정렬된 로그 데이터나 슬라이딩 윈도우 기반 지표 계산에 같은 개념이 직접 쓰인다.

---

## 핵심 개념 — 두 가지 패턴

Two Pointers는 쓰임새에 따라 두 방향으로 나뉜다.

### 패턴 1: 반대 방향 (Opposite Direction)

배열의 양 끝에 포인터를 두고 조건에 따라 안쪽으로 좁혀 오는 방식이다. **정렬된 배열**에서 합 조건을 만족하는 쌍을 찾을 때 전형적으로 사용된다.

```
배열: [1, 3, 5, 7, 9]
      ^               ^
      left           right

left + right > target  →  right--
left + right < target  →  left++
left + right == target →  정답 기록, 두 포인터 모두 이동
```

**언제 쓰는가:**
- 정렬된 배열에서 합이 target인 두 수 찾기 (Two Sum on sorted array)
- 정렬된 배열에서 세 수의 합이 0인 경우 (3Sum)
- 팰린드롬 판별
- 컨테이너 물 담기 (Container With Most Water)

### 패턴 2: 같은 방향 (Same Direction / Sliding Window 유사)

두 포인터가 같은 방향으로 이동하되, 속도나 조건이 다른 방식이다. 주로 **중복 제거**, **부분 배열 탐색**, **fast-slow 포인터** 문제에 사용된다.

```
배열: [0, 0, 1, 1, 2, 3]
       ^  ^
       slow fast

fast가 새로운 값을 만나면 slow를 전진시키고 값을 덮어쓴다.
```

**언제 쓰는가:**
- 정렬된 배열에서 중복 제거 (Remove Duplicates)
- 연결 리스트 사이클 감지 (Floyd's Cycle Detection)
- 특정 조건을 만족하는 가장 짧은/긴 부분 배열

---

## 정렬된 배열 페어 문제 — 반대 방향 패턴 상세 설명

Two Sum 문제를 예로 들어 반대 방향 패턴의 작동 원리를 단계별로 살펴본다.

**문제:** 정렬된 배열에서 합이 target인 두 수의 인덱스를 반환하라.

**왜 정렬이 전제 조건인가?** 정렬이 되어 있어야 "합이 너무 크면 오른쪽 포인터를 줄이고, 너무 작으면 왼쪽 포인터를 늘린다"는 단조성이 성립한다. 정렬되지 않은 배열이라면 이 논리가 깨진다.

```java
public int[] twoSumSorted(int[] nums, int target) {
    int left = 0;
    int right = nums.length - 1;

    while (left < right) {
        int sum = nums[left] + nums[right];

        if (sum == target) {
            return new int[]{left, right};
        } else if (sum < target) {
            left++;   // 합이 작으면 더 큰 수가 필요 → 왼쪽 포인터 전진
        } else {
            right--;  // 합이 크면 더 작은 수가 필요 → 오른쪽 포인터 후퇴
        }
    }

    return new int[]{-1, -1}; // 없는 경우
}
```

**시간복잡도:** O(n) — 각 포인터는 최대 n번 이동하고, 두 포인터가 만나면 종료된다.
**공간복잡도:** O(1) — 추가 자료구조 없음.

---

## 중복 제거 — 같은 방향 패턴 상세 설명

같은 방향 패턴의 핵심은 "slow 포인터는 유효한 결과의 끝을 가리키고, fast 포인터는 탐색 선두에 있다"는 역할 분리다.

**문제:** 정렬된 배열에서 in-place로 중복을 제거하고, 유니크한 원소의 수를 반환하라.

```java
public int removeDuplicates(int[] nums) {
    if (nums.length == 0) return 0;

    int slow = 0; // 유효한 배열의 마지막 위치

    for (int fast = 1; fast < nums.length; fast++) {
        if (nums[fast] != nums[slow]) {
            slow++;
            nums[slow] = nums[fast]; // 새로운 유니크 값을 slow 다음 위치에 기록
        }
        // nums[fast] == nums[slow]이면 fast만 전진, slow는 제자리
    }

    return slow + 1; // 유니크한 원소 수 (0-indexed이므로 +1)
}
```

**직관:** slow는 완성된 배열을 쌓아가는 스택의 top 포인터라고 생각하면 된다. fast가 새 값을 발견할 때만 slow를 올리고 값을 복사한다.

---

## 실무와의 연결 — 백엔드에서 같은 개념이 쓰이는 곳

Two Pointers는 순수 알고리즘 문제에만 국한되지 않는다. 백엔드 실무에서도 같은 사고방식이 반복된다.

**예시 1 — 정렬된 두 결과 셋 병합 (Merge Two Sorted Results)**

두 개의 정렬된 DB 결과 목록을 메모리에서 병합할 때, 각 리스트에 포인터를 두고 비교하면서 합친다. 이것이 Merge Sort의 핵심이자 Two Pointers의 변형이다.

```java
public List<Integer> mergeSorted(List<Integer> a, List<Integer> b) {
    List<Integer> result = new ArrayList<>();
    int i = 0, j = 0;

    while (i < a.size() && j < b.size()) {
        if (a.get(i) <= b.get(j)) {
            result.add(a.get(i++));
        } else {
            result.add(b.get(j++));
        }
    }

    while (i < a.size()) result.add(a.get(i++));
    while (j < b.size()) result.add(b.get(j++));

    return result;
}
```

**예시 2 — 슬라이딩 윈도우 지표 계산**

API 요청 로그가 타임스탬프 순으로 정렬되어 있을 때, 최근 N초 내 요청 수를 추적하는 Rate Limiter 로직이 전형적인 같은 방향 Two Pointers다.

```java
// 타임스탬프 배열에서 현재 시각 기준 window 내 요청 수 계산
public int countRequestsInWindow(long[] timestamps, long currentTime, long windowMs) {
    int left = 0;
    int right = timestamps.length - 1;

    // 오른쪽부터 탐색해 window 내 가장 왼쪽 인덱스 찾기
    while (left <= right) {
        if (timestamps[left] < currentTime - windowMs) {
            left++;
        } else {
            break;
        }
    }

    return timestamps.length - left;
}
```

---

## 흔한 구현 실수 패턴

Two Pointers 구현에서 반복적으로 나타나는 실수들이 있다. 라이브 코딩에서 이 실수를 범하면 디버깅에 시간을 낭비하게 된다.

### 실수 1: `left < right` vs `left <= right` 혼동

**잘못된 코드:**
```java
while (left <= right) {  // 같은 위치일 때도 진입
    int sum = nums[left] + nums[right];
    if (sum == target) return new int[]{left, right}; // left == right면 같은 원소를 두 번 사용
    // ...
}
```

**올바른 코드:**
```java
while (left < right) {  // 두 포인터가 교차하기 직전에 종료
    // ...
}
```

**규칙:** 두 포인터가 서로 다른 원소를 가리켜야 하는 경우 `left < right`. 같은 위치도 유효한 경우는 드물다.

### 실수 2: 3Sum에서 중복 건너뛰기 누락

3Sum처럼 반복하여 unique한 triplet을 찾을 때, 포인터 이동 후 같은 값 연속 건너뛰기를 빠뜨리면 중복 결과가 나온다.

**잘못된 코드:**
```java
if (sum == 0) {
    result.add(Arrays.asList(nums[i], nums[left], nums[right]));
    left++;
    right--;
    // 중복 건너뛰기 없음 → 같은 triplet이 다시 추가될 수 있다
}
```

**올바른 코드:**
```java
if (sum == 0) {
    result.add(Arrays.asList(nums[i], nums[left], nums[right]));
    left++;
    right--;
    while (left < right && nums[left] == nums[left - 1]) left++;   // 중복 건너뜀
    while (left < right && nums[right] == nums[right + 1]) right--; // 중복 건너뜀
}
```

### 실수 3: 정렬 전제 확인 누락

Two Pointers의 반대 방향 패턴은 **정렬된 배열을 전제**로 한다. 입력이 정렬되어 있지 않다면 먼저 정렬해야 한다. 이를 빠뜨리면 논리가 완전히 깨진다.

```java
// 입력 정렬이 보장되지 않는 경우
Arrays.sort(nums); // 반드시 먼저 정렬
int left = 0, right = nums.length - 1;
```

### 실수 4: 포인터를 양쪽 다 이동하지 않기

정답을 찾은 후 포인터를 하나만 이동하면 무한 루프에 빠질 수 있다.

```java
if (sum == target) {
    result.add(...);
    left++; // right도 이동해야 함
    right--; // 반드시 둘 다
}
```

---

## 로컬 실습 환경 구성

라이브 코딩 연습은 실제 제한 환경과 유사하게 구성하는 것이 중요하다. 아래는 IntelliJ IDEA 없이 터미널에서 빠르게 실행할 수 있는 방법이다.

### 방법 1: 단일 파일 Java 실행 (Java 11+)

```bash
# 파일 생성
cat > TwoPointers.java << 'EOF'
public class TwoPointers {
    public static int[] twoSumSorted(int[] nums, int target) {
        int left = 0, right = nums.length - 1;
        while (left < right) {
            int sum = nums[left] + nums[right];
            if (sum == target) return new int[]{left, right};
            else if (sum < target) left++;
            else right--;
        }
        return new int[]{-1, -1};
    }

    public static void main(String[] args) {
        int[] result = twoSumSorted(new int[]{1, 3, 5, 7, 9}, 8);
        System.out.println(result[0] + ", " + result[1]); // 기대: 1, 3 (3+5=8)
    }
}
EOF

# 컴파일 없이 바로 실행 (Java 11+)
java TwoPointers.java
```

### 방법 2: JShell로 빠른 스니펫 검증

```bash
jshell
```

```java
// JShell 내에서 직접 실행
int[] nums = {1, 3, 5, 7, 9};
int target = 8;
int left = 0, right = nums.length - 1;
while (left < right) {
    int sum = nums[left] + nums[right];
    if (sum == target) { System.out.println(left + ", " + right); break; }
    else if (sum < target) left++;
    else right--;
}
```

JShell은 클래스 정의 없이 코드를 즉시 실행할 수 있어 알고리즘 로직 검증에 유용하다.

---

## 면접에서 Two Pointers를 설명하는 방법

라이브 코딩 면접에서 풀이를 설명할 때 **Think Out Loud** 방식으로 접근하는 것이 중요하다. 조용히 코드만 작성하는 것은 좋은 인상을 남기지 못한다.

**추천 설명 흐름:**

1. **문제 특성 파악을 먼저 말한다**
   > "배열이 정렬되어 있고, 두 수의 합 조건을 만족하는 쌍을 찾는 문제입니다. 정렬된 배열의 단조성을 활용하면 O(n)에 해결 가능합니다."

2. **브루트 포스를 먼저 언급한다**
   > "나이브하게는 이중 루프로 O(n²)에 풀 수 있는데, 정렬 특성을 이용하면 더 효율적으로 할 수 있습니다."

3. **포인터 이동 조건의 '왜'를 설명한다**
   > "왼쪽 포인터를 올리면 합이 커지고, 오른쪽 포인터를 내리면 합이 작아집니다. 그래서 현재 합과 target을 비교해 포인터를 조정합니다."

4. **경계 조건을 명시적으로 언급한다**
   > "while 조건을 `left < right`로 두는 이유는 같은 원소를 두 번 사용하면 안 되기 때문입니다."

5. **복잡도를 정리하며 마무리한다**
   > "각 포인터가 최대 n번 이동하므로 시간복잡도는 O(n), 추가 공간은 사용하지 않으므로 공간복잡도는 O(1)입니다."

---

## 연습 문제

### 문제 1 (Easy) — Valid Palindrome

**문제:**
주어진 문자열에서 영문자와 숫자만 고려했을 때 팰린드롬인지 판별하라. 대소문자는 구별하지 않는다.

**입출력 예:**
```
입력: "A man, a plan, a canal: Panama"
출력: true

입력: "race a car"
출력: false
```

**힌트:**
- 반대 방향 Two Pointers를 사용한다.
- 유효하지 않은 문자(영문자, 숫자가 아닌 문자)는 건너뛴다.
- `Character.isLetterOrDigit()`과 `Character.toLowerCase()`를 활용한다.

<details>
<summary>풀이 보기 (클릭하여 펼치기)</summary>

**접근법:**

양 끝에 포인터를 두고, 유효하지 않은 문자는 건너뛴다. 유효한 문자끼리 비교해 다르면 false, 두 포인터가 교차할 때까지 같으면 true를 반환한다.

```java
public class ValidPalindrome {

    public boolean isPalindrome(String s) {
        int left = 0;
        int right = s.length() - 1;

        while (left < right) {
            // 왼쪽에서 유효하지 않은 문자 건너뜀
            while (left < right && !Character.isLetterOrDigit(s.charAt(left))) {
                left++;
            }
            // 오른쪽에서 유효하지 않은 문자 건너뜀
            while (left < right && !Character.isLetterOrDigit(s.charAt(right))) {
                right--;
            }

            // 대소문자 무시하고 비교
            if (Character.toLowerCase(s.charAt(left)) != Character.toLowerCase(s.charAt(right))) {
                return false;
            }

            left++;
            right--;
        }

        return true;
    }

    public static void main(String[] args) {
        ValidPalindrome vp = new ValidPalindrome();
        System.out.println(vp.isPalindrome("A man, a plan, a canal: Panama")); // true
        System.out.println(vp.isPalindrome("race a car")); // false
        System.out.println(vp.isPalindrome(" ")); // true (공백만 있는 경우 빈 문자열 취급)
    }
}
```

**복잡도 분석:**
- 시간: O(n) — 각 문자는 최대 한 번 방문
- 공간: O(1) — 추가 자료구조 없음 (`toLowerCase()`로 새 문자열 생성하지 않음)

**흔한 실수:**
- `s.toLowerCase().replaceAll("[^a-z0-9]", "")` 방식으로 새 문자열을 만들어 비교하는 방법도 가능하지만, 공간복잡도가 O(n)으로 올라간다. 면접에서 O(1) 공간을 물으면 위 방식을 써야 한다.
- `left < right` 조건을 inner while 문에도 반드시 포함해야 한다. 빠뜨리면 인덱스가 배열 범위를 벗어난다.

**면접 설명 포인트:**
> "팰린드롬 판별은 반대 방향 Two Pointers의 교과서적 사례입니다. 영문자와 숫자만 보는 조건이 있어서 유효하지 않은 문자를 건너뛰는 inner while을 추가했습니다. 중요한 것은 inner while에도 `left < right` 경계 조건이 있어야 한다는 점입니다."

</details>

---

### 문제 2 (Medium) — 3Sum

**문제:**
정수 배열 `nums`에서 합이 0이 되는 모든 유니크한 세 수의 조합을 반환하라. 중복 triplet은 포함하지 않는다.

**입출력 예:**
```
입력: [-1, 0, 1, 2, -1, -4]
출력: [[-1, -1, 2], [-1, 0, 1]]

입력: [0, 0, 0]
출력: [[0, 0, 0]]

입력: [0, 1, 1]
출력: []
```

**힌트:**
- 먼저 배열을 정렬한다.
- 바깥 루프로 첫 번째 원소를 고정하고, 나머지 두 수는 Two Pointers로 찾는다.
- 중복 건너뛰기가 핵심이다 — 바깥 루프와 포인터 이동 후 모두 처리해야 한다.
- `nums[i] > 0`이면 합이 0이 될 수 없으므로 조기 종료한다.

<details>
<summary>풀이 보기 (클릭하여 펼치기)</summary>

**접근법:**

정렬 후 바깥 루프에서 첫 번째 원소 `nums[i]`를 고정하고, `i+1`부터 끝까지의 범위에서 Two Pointers로 `nums[left] + nums[right] == -nums[i]`를 찾는다. 중복 triplet을 피하기 위해 두 곳에서 건너뛰기가 필요하다.

```java
import java.util.*;

public class ThreeSum {

    public List<List<Integer>> threeSum(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums); // 정렬이 전제 조건

        for (int i = 0; i < nums.length - 2; i++) {
            // 첫 번째 원소 중복 건너뜀
            if (i > 0 && nums[i] == nums[i - 1]) continue;

            // 최솟값이 양수면 합이 0이 될 수 없음 → 조기 종료
            if (nums[i] > 0) break;

            int left = i + 1;
            int right = nums.length - 1;
            int target = -nums[i]; // nums[left] + nums[right]가 이 값이어야 함

            while (left < right) {
                int sum = nums[left] + nums[right];

                if (sum == target) {
                    result.add(Arrays.asList(nums[i], nums[left], nums[right]));
                    left++;
                    right--;
                    // 두 번째, 세 번째 원소 중복 건너뜀
                    while (left < right && nums[left] == nums[left - 1]) left++;
                    while (left < right && nums[right] == nums[right + 1]) right--;
                } else if (sum < target) {
                    left++;
                } else {
                    right--;
                }
            }
        }

        return result;
    }

    public static void main(String[] args) {
        ThreeSum ts = new ThreeSum();

        System.out.println(ts.threeSum(new int[]{-1, 0, 1, 2, -1, -4}));
        // 기대: [[-1, -1, 2], [-1, 0, 1]]

        System.out.println(ts.threeSum(new int[]{0, 0, 0}));
        // 기대: [[0, 0, 0]]

        System.out.println(ts.threeSum(new int[]{0, 1, 1}));
        // 기대: []

        System.out.println(ts.threeSum(new int[]{-2, 0, 0, 2, 2}));
        // 기대: [[-2, 0, 2]]
    }
}
```

**복잡도 분석:**
- 시간: O(n²) — 정렬 O(n log n) + 바깥 루프 × Two Pointers O(n) = O(n²)
- 공간: O(1) ~ O(n) — 결과 저장 외 추가 공간 없음 (정렬이 in-place인 경우)

**중복 처리 로직 상세 설명:**

세 곳에서 중복 건너뛰기가 필요하다.

1. **바깥 루프 (i):** `if (i > 0 && nums[i] == nums[i-1]) continue;`
   - i=0에서 -1로 triplet을 찾았고, i=1도 -1이면 동일한 탐색을 반복하므로 건너뛴다.
   - `i > 0` 조건이 없으면 첫 번째 원소에서도 건너뛰어 버린다.

2. **left 포인터 이동 후:** `while (left < right && nums[left] == nums[left-1]) left++;`
   - triplet을 찾은 직후 left를 한 칸 올렸는데, 그 자리도 같은 값이면 또 같은 triplet이 추가된다.

3. **right 포인터 이동 후:** `while (left < right && nums[right] == nums[right+1]) right--;`
   - 같은 이유로 right를 한 칸 내린 뒤 같은 값 건너뛰기.

**흔한 실수:**

```java
// 잘못된 예: i > 0 조건 없음
if (nums[i] == nums[i - 1]) continue; // i=0이면 nums[-1] → ArrayIndexOutOfBoundsException

// 잘못된 예: 중복 건너뛰기 방향 혼동
while (left < right && nums[left] == nums[left + 1]) left++; // left-1이 아닌 left+1과 비교 → 건너뛰는 타이밍 어긋남
```

**면접 설명 포인트:**
> "3Sum은 Two Pointers의 대표 중급 문제입니다. 정렬 후 바깥 루프로 첫 수를 고정하고 Two Pointers로 나머지를 찾는 구조인데, 여기서 가장 중요한 것은 세 곳의 중복 건너뛰기입니다. 각각 어느 시점에 어떤 값과 비교해야 하는지 헷갈리기 쉬운데, 이미 방문한 위치의 값과 비교해야 한다는 점이 핵심입니다."

</details>

---

## 패턴 선택 결정 트리

면접 중 문제를 보고 어떤 Two Pointers 패턴을 쓸지 빠르게 결정하는 흐름이다.

```
배열/문자열 문제인가?
│
├── 합/차 조건을 만족하는 쌍/삼중쌍 찾기?
│   └── 정렬 가능한가?
│       ├── 예 → 반대 방향 Two Pointers
│       └── 아니오 → HashMap 사용 (Two Sum unsorted)
│
├── 중복 제거 / in-place 수정?
│   └── 같은 방향 (slow-fast) Two Pointers
│
├── 팰린드롬 판별?
│   └── 반대 방향 Two Pointers
│
└── 부분 배열/연속 구간 문제?
    └── 슬라이딩 윈도우 (같은 방향 변형)
```

---

## 체크리스트

면접 직전 확인용 체크리스트다.

- [ ] **정렬 전제 확인**: 반대 방향 패턴을 쓰기 전, 배열이 정렬되어 있는지, 정렬이 필요한지 확인한다.
- [ ] **while 조건**: `left < right`인지 `left <= right`인지 문제 조건에 맞게 선택했는가?
- [ ] **포인터 양쪽 이동**: 정답을 찾은 후 `left++`, `right--` 둘 다 이동했는가?
- [ ] **중복 건너뛰기**: 유니크한 결과가 필요한 경우, 바깥 루프와 포인터 이동 후 중복 건너뛰기를 모두 처리했는가?
- [ ] **경계 조건**: inner while 루프에도 `left < right` 조건이 포함되어 있는가?
- [ ] **조기 종료**: 더 이상 결과가 나올 수 없는 조건(최솟값이 양수 등)에서 `break`로 종료하는가?
- [ ] **복잡도 설명 준비**: O(n) vs O(n²)의 이유를 한 문장으로 설명할 수 있는가?
- [ ] **Think Out Loud**: 코드 작성 전, 포인터 이동 조건의 '왜'를 먼저 말했는가?
