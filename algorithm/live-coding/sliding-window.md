# [초안] 슬라이딩 윈도우 완전 정복 — Java 백엔드 라이브 코딩 인터뷰 대비

---

## 왜 슬라이딩 윈도우를 따로 공부해야 하는가

알고리즘 인터뷰에서 배열이나 문자열을 다루는 문제의 상당수는 "연속된 구간"을 탐색하는 패턴에 속한다. 이런 문제를 처음 보면 이중 반복문(O(n²))으로 모든 구간을 검사하고 싶어진다. 슬라이딩 윈도우는 그 이중 반복문을 단일 패스(O(n))로 바꾸는 기법이다.

HackerRank, LeetCode, 그리고 국내 대기업 코딩 테스트에서 슬라이딩 윈도우 문제는 빈번하게 출제된다. 특히 라이브 코딩 인터뷰에서는 "생각하면서 말해달라"는 요청을 받기 때문에, 패턴을 몸에 익혀 자동으로 나오도록 해야 한다. 개념을 알고 있어도 손이 움직이지 않으면 시간 압박에 무너진다.

이 문서는 개념 설명 → 패턴 분류 → 자주 하는 실수 → 인터뷰 발화 흐름 → 실습 문제 순서로 구성되어 있어, 이 문서 하나로 라이브 코딩 준비를 완결할 수 있도록 작성했다.

---

## 핵심 개념: 슬라이딩 윈도우란

슬라이딩 윈도우는 배열 또는 문자열에서 **두 포인터(left, right)** 가 구간의 경계를 나타내고, 이 구간을 조건에 따라 확장하거나 수축하면서 최적해를 구하는 기법이다.

```
인덱스:  0   1   2   3   4   5   6
배열:  [ 1,  3,  2,  4,  1,  2,  3 ]
             └──────────┘
             left=1     right=3   윈도우 = [3, 2, 4], 합 = 9
```

포인터 `right`는 거의 항상 앞으로만 이동한다. `left`도 앞으로만 이동한다. 따라서 두 포인터를 합산하면 최대 2n번만 이동하므로 전체 시간복잡도는 O(n)이 된다. 이 "두 포인터가 뒤로 가지 않는다"는 불변성이 슬라이딩 윈도우의 효율성을 만든다.

---

## 패턴 분류: 고정 크기 vs 가변 크기

슬라이딩 윈도우 문제는 크게 두 가지 유형으로 나뉜다.

### 1. 고정 크기 윈도우 (Fixed-Size Window)

윈도우의 크기 `k`가 주어진다. `right`가 `k-1`에 도달하면 윈도우가 완성되고, 이후 매 스텝마다 `left`와 `right`를 동시에 한 칸씩 이동한다.

**문제 형태 식별 키워드**: "크기 k인 연속 부분 배열", "정확히 k개의 원소", "k개 슬라이딩"

**Java 뼈대 코드**:

```java
int windowSum = 0;
int maxSum = Integer.MIN_VALUE;

for (int right = 0; right < nums.length; right++) {
    windowSum += nums[right]; // 윈도우에 원소 추가

    if (right >= k - 1) {    // 윈도우 크기가 k가 되는 시점부터
        maxSum = Math.max(maxSum, windowSum);
        windowSum -= nums[right - (k - 1)]; // 가장 왼쪽 원소 제거
    }
}
```

핵심은 `right - (k - 1)`이 `left`의 역할을 한다는 점이다. 별도의 `left` 변수 없이 `right`만으로 관리하는 방식이다. 명시적 `left` 변수를 써도 동일하다:

```java
int left = 0;
for (int right = 0; right < nums.length; right++) {
    windowSum += nums[right];
    if (right - left + 1 == k) {
        maxSum = Math.max(maxSum, windowSum);
        windowSum -= nums[left];
        left++;
    }
}
```

### 2. 가변 크기 윈도우 (Variable-Size Window)

윈도우 크기가 조건에 따라 달라진다. "가장 긴 구간", "가장 짧은 구간"처럼 최적 크기를 스스로 찾아야 하는 문제다.

**문제 형태 식별 키워드**: "합이 S 이상인 가장 짧은 연속 부분 배열", "중복 없는 가장 긴 부분 문자열", "최대 k번 교체했을 때..."

**패턴 A: 조건 위반 시 left 전진 (최장 구간)**

```java
int left = 0;
int maxLen = 0;
// 상태를 추적하는 자료구조 (Map, Set, int 등)

for (int right = 0; right < s.length(); right++) {
    // right 추가 → 상태 업데이트

    while (조건 위반) {
        // left 제거 → 상태 업데이트
        left++;
    }

    maxLen = Math.max(maxLen, right - left + 1);
}
```

**패턴 B: 조건 만족 시 left 전진 (최단 구간)**

```java
int left = 0;
int minLen = Integer.MAX_VALUE;
int windowSum = 0;

for (int right = 0; right < nums.length; right++) {
    windowSum += nums[right];

    while (windowSum >= target) {
        minLen = Math.min(minLen, right - left + 1);
        windowSum -= nums[left];
        left++;
    }
}
```

패턴 A와 B의 차이는 `while` 조건의 방향이다. **A는 "위반이면 수축"**, **B는 "만족이면 수축하면서 최소 기록"**이다. 이 방향을 헷갈리는 것이 가장 흔한 실수다.

---

## 빈도수 카운팅 패턴 (Frequency Counting)

문자열 문제에서는 문자 빈도를 추적하기 위해 `HashMap<Character, Integer>` 또는 `int[26]` 배열을 쓴다. 이 조합이 슬라이딩 윈도우에서 가장 자주 나오는 자료구조 패턴이다.

예: 중복 없는 가장 긴 부분 문자열 (Longest Substring Without Repeating Characters)

```java
public int lengthOfLongestSubstring(String s) {
    Map<Character, Integer> freq = new HashMap<>();
    int left = 0, maxLen = 0;

    for (int right = 0; right < s.length(); right++) {
        char c = s.charAt(right);
        freq.merge(c, 1, Integer::sum); // freq.put(c, freq.getOrDefault(c, 0) + 1)

        while (freq.get(c) > 1) {      // 중복 발생
            char leftChar = s.charAt(left);
            freq.merge(leftChar, -1, Integer::sum);
            if (freq.get(leftChar) == 0) freq.remove(leftChar);
            left++;
        }

        maxLen = Math.max(maxLen, right - left + 1);
    }
    return maxLen;
}
```

`freq.merge(key, delta, Integer::sum)`는 Java 8+ 관용구다. 인터뷰에서 이걸 쓰면 "Java에 익숙하다"는 인상을 준다. `getOrDefault`보다 간결하다.

---

## 최장/최단 직관 정리

| 구하는 것 | `while` 조건 | 결과 갱신 위치 |
|---------|------------|-------------|
| 최장 구간 | 조건 위반 시 수축 | `while` 밖 (매 right마다) |
| 최단 구간 | 조건 만족 시 수축 | `while` 안 (수축 직전) |

이 표를 외우면 문제 유형을 보자마자 뼈대를 채울 수 있다.

---

## 자주 하는 구현 실수 7가지

### 실수 1: off-by-one — 윈도우 크기 계산

```java
// 잘못된 코드
if (right - left == k) { ... }

// 올바른 코드
if (right - left + 1 == k) { ... }
```

`right - left`는 포인터 간 거리이고, 원소 개수는 `right - left + 1`이다. 이 실수는 고정 크기 윈도우에서 99% 확률로 나온다.

### 실수 2: left가 right를 넘어가는 경우를 처리 안 함

```java
// 실수: left가 right를 초과할 수 있음
while (freq.get(c) > 1) {
    left++;  // c를 지우기 전에 left 증가
}

// 올바른 순서
while (freq.get(c) > 1) {
    freq.merge(s.charAt(left), -1, Integer::sum);
    left++;  // 제거 후 left 이동
}
```

항상 "left의 원소를 상태에서 제거하고 난 뒤 left++를 한다"는 순서를 지켜야 한다.

### 실수 3: 빈도맵에서 0 처리 누락

`HashMap`을 쓸 때 값이 0이 되어도 키가 남아있으면 `size()` 기반 조건이 틀어진다.

```java
// 올바른 제거 패턴
freq.merge(leftChar, -1, Integer::sum);
if (freq.get(leftChar) == 0) freq.remove(leftChar);
```

### 실수 4: 정수 오버플로우

배열 원소가 int이고 합을 구할 때 k가 크면 int 오버플로우가 발생한다.

```java
// 위험
int windowSum = 0;

// 안전
long windowSum = 0;
```

### 실수 5: right 루프 전에 left를 초기화 안 함

```java
// 흔한 실수: left 선언을 for 안에서 함
for (int right = 0, left = 0; right < n; right++) { ... }
// left를 while 안에서 참조할 때 범위 문제 없지만
// 다른 메서드와 혼용할 때 혼란 유발

// 명확한 패턴
int left = 0;
for (int right = 0; right < n; right++) { ... }
```

### 실수 6: while 대신 if 사용 — 최장 구간에서

```java
// 잘못됨: 한 번만 수축하면 여러 위반 원소를 처리 못 함
if (조건 위반) {
    // left 제거, left++
}

// 올바름
while (조건 위반) {
    // left 제거, left++
}
```

### 실수 7: 결과 변수 초기값 설정 실수

```java
// 최장 구간: 0으로 초기화 OK (길이는 0 이상)
int maxLen = 0;

// 최단 구간: Integer.MAX_VALUE로 초기화
int minLen = Integer.MAX_VALUE;
// 반환 시 결과가 없으면 0 또는 -1 반환 처리 필요
return minLen == Integer.MAX_VALUE ? 0 : minLen;
```

---

## 슬라이딩 윈도우 문제 풀이 흐름 (라이브 인터뷰용 발화 스크립트)

라이브 코딩 인터뷰에서는 "지금 무슨 생각을 하는지" 말하면서 코딩해야 한다. 다음 흐름을 몸에 익혀두면 패닉 없이 진행할 수 있다.

**Step 1 — 문제 재확인 (30초)**

> "연속된 구간을 탐색하는 문제네요. 입력이 배열/문자열이고, 최적 구간을 찾아야 하니까 슬라이딩 윈도우를 먼저 고려해볼게요."

**Step 2 — 유형 판단 (15초)**

> "윈도우 크기가 고정인가요, 조건에 따라 달라지나요? (고정이면) k가 주어졌으니 고정 크기 윈도우를 쓸게요. (가변이면) 최장/최단 중 어느 쪽인지 확인하겠습니다."

**Step 3 — 상태 자료구조 결정 (15초)**

> "윈도우 내 상태를 무엇으로 추적해야 하나요? 합이면 int 하나, 문자 빈도면 HashMap이나 int[26], 고유 원소 수면 Set을 쓰겠습니다."

**Step 4 — 뼈대 작성 → 채우기**

> "left=0, right를 반복문으로 이동시키고, 조건 체크 후 상태 업데이트, 결과 갱신 순서로 작성하겠습니다."

**Step 5 — 엣지 케이스 언급**

> "빈 배열, k가 배열 길이보다 큰 경우, 모든 원소가 동일한 경우를 확인하겠습니다."

---

## 로컬 실습 환경 설정

인텔리J나 VS Code가 있다면 다음 구조로 바로 실습 가능하다.

```
sliding-window-practice/
├── src/
│   └── main/java/
│       └── practice/
│           ├── FixedWindow.java
│           ├── LongestSubstring.java
│           ├── MinSubarrayLen.java
│           └── MaxVowels.java
└── pom.xml  (또는 build.gradle)
```

**빠른 시작 — pom.xml 없이 단일 파일 실행 (Java 11+)**

```bash
cat > SlidingTest.java << 'EOF'
public class SlidingTest {
    public static void main(String[] args) {
        // 여기에 코드 붙여넣기
    }
}
EOF
javac SlidingTest.java && java SlidingTest
```

---

## 연습 문제 1 (Easy): 크기 k인 부분 배열의 최대 합

### 문제 설명

정수 배열 `nums`와 정수 `k`가 주어진다. 크기가 정확히 `k`인 연속 부분 배열 중 합이 최대인 값을 반환하라.

**입력/출력 예시**:
```
nums = [2, 1, 5, 1, 3, 2], k = 3
출력: 9  (부분 배열 [5, 1, 3])

nums = [2, 3, 4, 1, 5], k = 2
출력: 7  (부분 배열 [3, 4])
```

**제약 조건**:
- `1 <= k <= nums.length <= 10^5`
- `-10^4 <= nums[i] <= 10^4`

**풀이 전 스스로 생각해볼 것**:
1. 이중 반복문 O(n·k) 먼저 떠올리기
2. 이전 윈도우 합에서 왼쪽 원소를 빼고 오른쪽 원소를 더하면 O(1)로 전환되는 이유 생각하기
3. 윈도우가 완성되는 시점(right가 k-1에 도달하는 시점)을 인덱스로 표현하기

<details>
<summary>풀이 및 Java 코드 보기</summary>

**접근법**: 고정 크기 윈도우. `right`가 `k-1`이 되는 순간부터 윈도우가 완성된다. 그 이후부터 매 스텝마다 왼쪽 끝 원소를 빼고 오른쪽 원소를 더하면서 최댓값을 갱신한다.

```java
public class MaxSumFixedWindow {

    public static int maxSum(int[] nums, int k) {
        if (nums == null || nums.length < k) return -1;

        long windowSum = 0;
        long maxSum = Long.MIN_VALUE;

        for (int right = 0; right < nums.length; right++) {
            windowSum += nums[right];

            if (right >= k - 1) {
                maxSum = Math.max(maxSum, windowSum);
                windowSum -= nums[right - (k - 1)]; // left = right - k + 1
            }
        }

        return (int) maxSum;
    }

    public static void main(String[] args) {
        System.out.println(maxSum(new int[]{2, 1, 5, 1, 3, 2}, 3)); // 9
        System.out.println(maxSum(new int[]{2, 3, 4, 1, 5}, 2));    // 7
        System.out.println(maxSum(new int[]{-1, -2, -3, -4}, 2));   // -3
    }
}
```

**시간복잡도**: O(n) — 각 원소는 정확히 한 번씩 추가되고 한 번씩 제거된다.  
**공간복잡도**: O(1) — 추가 자료구조 없음.

**인터뷰 포인트**:
- `long`을 쓴 이유를 묻는다면: "원소가 최대 10^4이고 k가 최대 10^5이면 합이 10^9를 넘을 수 있어서 int 오버플로우를 방지했습니다."
- `right - (k - 1)`이 `left`라는 것을 명시적으로 설명할 수 있어야 한다: "이 인덱스는 현재 윈도우의 왼쪽 끝입니다."

</details>

---

## 연습 문제 2 (Medium): 중복 없는 가장 긴 부분 문자열

### 문제 설명

문자열 `s`가 주어진다. 중복 문자가 없는 가장 긴 연속 부분 문자열의 길이를 반환하라.

**입력/출력 예시**:
```
s = "abcabcbb"
출력: 3  ("abc")

s = "bbbbb"
출력: 1  ("b")

s = "pwwkew"
출력: 3  ("wke")

s = ""
출력: 0
```

**제약 조건**:
- `0 <= s.length() <= 5 * 10^4`
- `s`는 영어 소문자, 숫자, 기호, 공백으로 구성됨

**풀이 전 스스로 생각해볼 것**:
1. 브루트포스(O(n²) 또는 O(n³)) 접근을 먼저 떠올리고 왜 느린지 설명하기
2. "중복이 없다"는 조건을 자료구조로 어떻게 추적할지 (Set? Map? int[]?)
3. 중복이 발생했을 때 left를 얼마나 이동시켜야 하는가? 한 칸? 아니면?
4. `int[128]` ASCII 배열과 `HashMap<Character, Integer>` 중 어느 게 더 빠른가?

<details>
<summary>풀이 및 Java 코드 보기 (두 가지 구현)</summary>

**접근법**: 가변 크기 윈도우 — 최장 구간 탐색. `right`를 전진시키면서 문자 빈도를 추적하고, 중복이 발생하면 `left`를 전진시켜 중복을 제거한다.

---

**구현 A: HashMap 방식 — 가장 범용적**

```java
import java.util.HashMap;
import java.util.Map;

public class LongestSubstringNoRepeat {

    public static int lengthOfLongestSubstring(String s) {
        Map<Character, Integer> freq = new HashMap<>();
        int left = 0;
        int maxLen = 0;

        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            freq.merge(c, 1, Integer::sum);

            // 중복 발생 시 left를 전진시켜 중복 제거
            while (freq.get(c) > 1) {
                char leftChar = s.charAt(left);
                freq.merge(leftChar, -1, Integer::sum);
                if (freq.get(leftChar) == 0) freq.remove(leftChar);
                left++;
            }

            maxLen = Math.max(maxLen, right - left + 1);
        }

        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(lengthOfLongestSubstring("abcabcbb")); // 3
        System.out.println(lengthOfLongestSubstring("bbbbb"));    // 1
        System.out.println(lengthOfLongestSubstring("pwwkew"));   // 3
        System.out.println(lengthOfLongestSubstring(""));         // 0
        System.out.println(lengthOfLongestSubstring(" "));        // 1 (공백도 문자)
    }
}
```

---

**구현 B: int[128] ASCII 배열 방식 — 성능 최적화**

영어 소문자/숫자/기호만 나온다면 `int[128]` 배열이 HashMap보다 ~3배 빠르다. 인터뷰에서 "최적화할 수 있나요?"라는 질문에 대답할 수 있는 카드다.

```java
public class LongestSubstringNoRepeatOptimized {

    public static int lengthOfLongestSubstring(String s) {
        int[] freq = new int[128]; // ASCII 범위
        int left = 0;
        int maxLen = 0;

        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            freq[c]++;

            while (freq[c] > 1) {
                freq[s.charAt(left)]--;
                left++;
            }

            maxLen = Math.max(maxLen, right - left + 1);
        }

        return maxLen;
    }
}
```

---

**구현 C: Map + last-seen index 방식 — left를 한 번에 점프**

중복 문자가 마지막으로 등장한 위치를 기억해두면 `while` 루프 없이 `left`를 한 번에 이동시킬 수 있다.

```java
import java.util.HashMap;
import java.util.Map;

public class LongestSubstringLastSeen {

    public static int lengthOfLongestSubstring(String s) {
        Map<Character, Integer> lastSeen = new HashMap<>();
        int left = 0;
        int maxLen = 0;

        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);

            if (lastSeen.containsKey(c) && lastSeen.get(c) >= left) {
                // left를 중복 문자 바로 다음으로 점프
                left = lastSeen.get(c) + 1;
            }

            lastSeen.put(c, right);
            maxLen = Math.max(maxLen, right - left + 1);
        }

        return maxLen;
    }
}
```

> 주의: 이 방식에서 `lastSeen.get(c) >= left` 조건이 중요하다. `lastSeen`에 기록된 위치가 현재 윈도우 왼쪽 바깥이면(이미 제거된 문자이면) 무시해야 한다.

---

**세 구현의 비교**:

| 구현 | 시간복잡도 | 공간복잡도 | 특징 |
|-----|----------|----------|------|
| HashMap + while | O(n) | O(min(m,n)) | 가장 직관적, 모든 문자 처리 가능 |
| int[128] + while | O(n) | O(1) | ASCII 한정, 실제로 빠름 |
| HashMap + last-seen | O(n) | O(min(m,n)) | while 없음, 면접관에게 인상적 |

m = 문자 집합 크기

**인터뷰 포인트**:
- "처음에는 HashMap으로 구현하겠습니다. 만약 입력이 ASCII 문자로 한정된다면 int[128] 배열로 바꿔서 공간을 O(1)로, 속도를 더 높일 수 있습니다."
- last-seen 방식을 설명할 때: "left를 하나씩 이동시키는 대신 중복 문자가 마지막에 있던 위치의 다음으로 바로 점프합니다. 단, 그 위치가 현재 윈도우 안에 있을 때만 점프해야 합니다."

</details>

---

## 인터뷰 대답 프레이밍 (시니어 백엔드 관점)

라이브 코딩 인터뷰에서 슬라이딩 윈도우를 선택한 이유를 묻는다면:

> "배열/문자열에서 연속 구간을 탐색할 때 이중 반복문은 O(n²)입니다. 슬라이딩 윈도우는 두 포인터가 각각 한 방향으로만 이동한다는 불변성을 이용해 O(n)으로 줄입니다. left와 right를 합산해도 최대 2n번만 이동하므로 시간복잡도가 선형이 됩니다."

복잡도 분석을 물었을 때:

> "각 원소는 최대 한 번 윈도우에 추가되고 한 번 제거됩니다. 따라서 총 연산 횟수는 2n이고, O(n)입니다. 공간복잡도는 윈도우 내 상태를 추적하는 자료구조 크기에 따라 다르며, 이 문제에서는 문자 집합 크기에 비례하므로 O(1) 또는 O(m)입니다 (m = 문자 종류 수)."

---

## 최종 체크리스트

라이브 코딩 인터뷰 직전, 이 체크리스트를 빠르게 읽고 들어가라.

- [ ] 문제를 읽고 "연속 구간 탐색"이면 슬라이딩 윈도우를 먼저 고려한다
- [ ] 고정 크기 vs 가변 크기를 30초 안에 판단한다
- [ ] 가변 크기 → 최장(while 위반 시 수축) vs 최단(while 만족 시 수축)을 구분한다
- [ ] 상태 자료구조를 즉시 결정한다: int(합), int[](고정 문자셋), HashMap(범용)
- [ ] `right - left + 1`로 현재 윈도우 크기를 계산한다 (off-by-one 방지)
- [ ] `left` 제거 시 "상태에서 제거 → left++" 순서를 지킨다
- [ ] 최단 구간 결과 변수는 `Integer.MAX_VALUE`로 초기화하고 반환 전 처리한다
- [ ] 빈 배열/문자열, k > n, 모든 원소 동일 케이스를 언급한다
- [ ] 코드 작성 후 예시 입력으로 손으로 한 번 트레이싱한다
- [ ] "최적화 가능한가?"라는 질문에 int[] vs HashMap 트레이드오프로 답한다
