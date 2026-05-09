# [초안] 라이브 코딩에서 백트래킹: 선택-재귀-복구 패턴으로 풀어내는 Java 면접 가이드

## 왜 백트래킹이 라이브 코딩의 단골 주제인가

HackerRank, 코딜리티, 구글 docs 화면 공유 같은 라이브 코딩 환경에서 백트래킹 문제가 자주 등장하는 이유는 단순하다. 면접관 입장에서 한 문제로 여러 신호를 동시에 관찰할 수 있기 때문이다.

- 재귀 호출과 호출 스택을 정확히 다루는가
- 상태 변경과 복구를 빠뜨리지 않는가 (전형적인 mutation 버그)
- 가지치기를 어떤 기준으로 거는가 (시간 복잡도 추정 능력)
- 답이 없을 때 어떻게 종료하는가 (`return false` vs 계속 탐색)
- 문제 도메인을 그래프/트리/조합 중 어느 것으로 모델링하는가

특히 시니어 백엔드 면접에서 백트래킹은 단순 알고리즘 트릭으로 끝나지 않는다. 권한 정책 트리 탐색, 일정 후보 매칭, 로깅 규칙 매칭, 룰 엔진의 결정 트리, 워크플로 가능 경로 열거 같은 실제 시스템 문제도 본질이 백트래킹이다. 라이브 코딩에서 백트래킹을 깔끔하게 풀면 “단순 코더”가 아닌 “구조를 짚는 시니어”라는 인상을 빠르게 심을 수 있다.

이 문서는 1) 백트래킹의 코어 패턴을 한 번에 정리하고, 2) 라이브 코딩에서 면접관에게 사고 흐름을 설명하는 방식을 보여주고, 3) Java 정규 코드로 실제 문제 두 개(쉬움 1, 중간 1)를 풀어보며 점검하는 것을 목표로 한다.

## 핵심 개념: 선택-재귀-복구의 3박자

백트래킹은 “모든 경우를 다 만들어 보되, 만들면서 안 되는 가지는 버린다”는 전략이다. 코드 모양은 거의 매번 같은 골격을 따른다.

```java
void backtrack(상태 state) {
    if (정답 조건) {
        결과 기록(state);
        return;
    }
    if (가지치기 조건) {
        return;
    }

    for (선택 choice : 가능한_선택들(state)) {
        if (!유효(choice, state)) continue;

        선택_적용(state, choice);   // (1) 선택
        backtrack(state);          // (2) 재귀
        선택_복구(state, choice);   // (3) 복구
    }
}
```

이 골격에서 중요한 포인트는 다음 네 가지다.

**1. 상태(state)는 인자로 그대로 들고 다닌다.** 깊은 복사를 매번 하면 시간/메모리 모두 폭발한다. `List<Integer> path` 하나를 공유하고, 들어갈 때 add, 나올 때 removeLast로 복구하는 형태가 정석이다.

**2. 결과 리스트에 담을 때만 새 사본을 만든다.** `result.add(new ArrayList<>(path))` 처럼. 같은 path 참조를 그대로 add하면 모든 결과가 마지막 상태로 덮인다. 라이브 코딩에서 가장 흔한 첫 번째 버그.

**3. 종료 조건과 가지치기 조건을 분리해서 쓴다.** “정답을 만났을 때 기록하고 더 진행할지 결정”과 “더 가도 의미 없을 때 끊기”는 다른 사고다. 한 줄에 섞으면 디버깅이 안 된다.

**4. 선택 순서를 명확히 한다.** 인덱스 기반(`start` 변수)인지, “쓰지 않은 원소”를 boolean visited로 추적하는지, 사전순 정렬 후 같은 값 스킵으로 중복 제거하는지 — 문제 유형에 따라 정해진다.

## 부분집합 / 순열 / 조합의 변형 한 번에 정리

라이브 코딩에서 마주치는 백트래킹 문제 90%는 아래 셋의 변형이다. 각각 골격만 외우면 변형은 조건 한두 줄로 흡수된다.

### 부분집합 (Subsets)

```java
void subsets(int[] nums, int start, List<Integer> path, List<List<Integer>> result) {
    result.add(new ArrayList<>(path));      // 매 단계마다 결과
    for (int i = start; i < nums.length; i++) {
        path.add(nums[i]);
        subsets(nums, i + 1, path, result); // i+1: 한 번 고른 건 다시 고려 X
        path.remove(path.size() - 1);
    }
}
```

핵심은 `start` 인덱스. “지금까지 고른 것 뒤에서만 고른다”로 중복을 자연스럽게 제거한다. 시간 복잡도는 `O(2^n)`개 부분집합 × 각 부분집합 복사 `O(n)` = `O(n · 2^n)`. 라이브 코딩에서 이 분석을 묻는 경우가 많다.

### 순열 (Permutations)

```java
void permute(int[] nums, boolean[] used, List<Integer> path, List<List<Integer>> result) {
    if (path.size() == nums.length) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = 0; i < nums.length; i++) {
        if (used[i]) continue;
        used[i] = true;
        path.add(nums[i]);
        permute(nums, used, path, result);
        path.remove(path.size() - 1);
        used[i] = false;
    }
}
```

순열은 `start` 인덱스가 없고 `used[]`로 “이미 쓴 원소”를 추적한다. 복구할 때 `path.remove`와 `used[i] = false` 두 줄을 동시에 되돌려야 한다. 한쪽만 빠뜨리면 결과가 통째로 망가진다 — 면접에서 자주 나오는 두 번째 버그 패턴.

### 조합 (Combinations)

```java
void combine(int n, int k, int start, List<Integer> path, List<List<Integer>> result) {
    if (path.size() == k) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = start; i <= n; i++) {
        path.add(i);
        combine(n, k, i + 1, path, result);
        path.remove(path.size() - 1);
    }
}
```

조합은 부분집합과 거의 같지만 “고정 길이 k”라는 종료 조건이 추가된다.

### 중복 입력에서 결과 중복 제거

`nums = [1, 1, 2]`처럼 중복 원소가 있을 때 결과의 중복을 막으려면 정렬 + 같은 깊이에서의 같은 값 스킵을 사용한다.

```java
Arrays.sort(nums);
for (int i = start; i < nums.length; i++) {
    if (i > start && nums[i] == nums[i - 1]) continue; // 같은 깊이에서 같은 값 스킵
    ...
}
```

이 한 줄을 라이브 코딩에서 자연스럽게 끼워 넣을 수 있으면 “중복 처리도 알고 있다”는 신호로 작동한다.

## 가지치기(Pruning) 기준 잡기

순수 완전 탐색은 입력이 조금만 커져도 시간 안에 끝나지 않는다. 가지치기 없이 백트래킹을 풀면 라이브에서 “시간 초과 시 어떻게 줄일 것이냐”는 질문이 반드시 따라온다. 자주 쓰이는 가지치기 기준은 다음과 같다.

- **남은 길이가 부족하면 즉시 종료**: 길이 k 조합인데 남은 원소가 부족하면 바로 return.
- **현재 누적값이 이미 한계를 초과**: 합이 target을 넘었으면 더 큰 후보는 보지 않는다(정렬 전제).
- **사전순/오름차순 강제**: 동일 결과가 여러 순서로 만들어지는 걸 차단.
- **유망성 판단**(promising): 현재 부분 해 + 가능한 최댓값으로도 정답에 못 미치면 컷.
- **메모이제이션**: 동일 (상태)에 대한 호출이 반복되면 캐시. 사실상 DP로 전환.

라이브 코딩에서 면접관이 “시간 줄여 달라”고 했을 때, 어떤 가지치기 후보가 있는지 “네 개 정도 있다”고 먼저 분류하고 그 중 한두 개를 적용하는 흐름이 좋다. 무작정 코드를 손대기 시작하면 인상이 약해진다.

## 흔한 버그 패턴 다섯 가지

라이브에서 시간을 가장 많이 잡아먹는 곳은 알고리즘 자체보다 백트래킹의 디테일이다. 미리 패턴화해 두면 같은 실수를 반복하지 않는다.

**버그 1. path 참조를 그대로 결과에 add**

```java
result.add(path);            // 잘못됨 — 모든 결과가 마지막 상태가 됨
result.add(new ArrayList<>(path)); // 올바름
```

**버그 2. 복구 누락**

`used[i] = true`만 쓰고 `false`로 되돌리지 않거나, `path.add`만 하고 `remove`를 빠뜨리는 경우. for 루프 끝마다 “들어갈 때 한 일 = 나올 때 되돌릴 일” 짝을 짠다는 규칙을 코드로 강제하면 줄어든다.

**버그 3. start 인덱스 잘못 잡기**

조합/부분집합에서 `i + 1` 대신 `start + 1`을 넘기거나, 순열에 `start`를 끌고 다니는 실수. 어떤 자료구조를 쓸지 결정하기 전에 “재방문 허용? 순서 의미 있음?”을 명시적으로 답하면 막을 수 있다.

**버그 4. 정렬 안 하고 중복 스킵 시도**

중복 제거 if 문은 “정렬되어 있다”가 전제다. 정렬 없이 같은 if 문을 쓰면 결과가 일부 누락된다. 코드 위에 `Arrays.sort(nums);`를 먼저 적는 습관이 안전하다.

**버그 5. 종료 조건이 너무 늦거나 너무 이르다**

`path.size() == k`를 체크하기 전에 for 루프에 들어가서 한 단계 더 깊이 가버리는 경우, 혹은 `path.size() > k`로 잡아서 정상 결과까지 잘리는 경우. 종료 조건은 함수 진입 직후 첫 번째 줄에 두는 것을 기본으로 한다.

## 라이브 면접에서 접근을 설명하는 방법

면접관은 코드보다 사고 흐름을 본다. 백트래킹 문제를 받았을 때 다음 5단계로 말로 풀어내는 것을 권장한다.

1. **문제 분류**: “이거 부분집합 / 순열 / 조합 / 분기 탐색 중 어디에 가까운가”를 먼저 입 밖으로 정한다. “일단 백트래킹 같은데 부분집합 변형으로 보입니다”처럼 기준을 명시.
2. **상태 정의**: 어떤 변수를 들고 다닐 것인가. `path`, `start`, `used`, `currentSum` 같은 후보를 적는다. 화면에 노션이나 텍스트 패드를 띄울 수 있다면 한 줄씩 적는 것이 좋다.
3. **종료 조건 + 결과 기록 시점**: “언제 답이 완성되는가”와 “언제 더 가지 않는가”를 분리해서 말한다.
4. **시간 복잡도 추정**: 최악의 경우 `O(2^n)`인지, `O(n!)`인지 미리 말한다. 입력 크기 제약과 비교해 “n=20이면 2^20 = 약 백만이라 충분히 돌아갑니다” 식으로 안정감을 준다.
5. **가지치기 기회**: 위에서 언급한 가지치기 후보를 한 줄씩 살펴보고, 적용할지 말지 판단한다. 시간이 빠듯해 보일 때만 구현에 넣는다.

이 흐름을 코드 작성 전 1~2분에 끝내고 코딩을 시작하면 된다. 코딩 도중에 막혀도 “지금 어디 단계에서 막혔는지” 면접관에게 명시할 수 있다.

## 로컬 연습 환경

실제 라이브 코딩은 IDE 자동완성이 약하거나 아예 없는 환경에서 진행되는 경우가 많다. 손으로 골격을 칠 수 있는 수준까지 끌어올리는 게 이 문서의 두 번째 목표다. 권장 환경은 다음과 같다.

```bash
mkdir -p ~/playground/backtracking-java
cd ~/playground/backtracking-java
# 단일 파일 실행 (Java 11+)
java Subsets.java
```

JDK 11 이상이면 `java SingleFile.java`로 컴파일 없이 단일 파일을 실행할 수 있다. IntelliJ에 의존하지 않고 단일 파일을 만들어 `main`에서 직접 호출/출력하는 흐름을 몸에 익히면 코딜리티/HackerRank 스타일에서도 흔들리지 않는다.

권장 연습 루틴:

- 매일 1문제, 30분 타이머 + 시계 앞에서 “말로 5단계 설명 → 코드” 순서로 풀이.
- 풀이 후 골격(선택-재귀-복구)이 분리되어 있는지 자기 코드 리뷰.
- 자주 틀리는 줄을 “mistake.md” 같은 한 파일에 한 줄씩 누적.

LeetCode 78(Subsets), 46(Permutations), 39(Combination Sum), 51(N-Queens), 79(Word Search), 131(Palindrome Partitioning)을 한 사이클 도는 것을 추천한다.

## 연습 문제

아래 두 문제는 본 문서 안에서 학습/검증을 끝낼 수 있도록 풀이와 Java 전체 코드를 details 블록 안에 숨겨 두었다. 먼저 자기 손으로 풀고, 막힌 뒤에만 펼쳐서 비교하는 방식이 가장 효과가 크다.

### 문제 1 (쉬움) — 부분집합 모두 출력하기

서로 다른 정수 배열 `nums`가 주어진다. 가능한 모든 부분집합을 반환하라. 결과 순서는 자유. 입력 길이는 최대 10.

예) `nums = [1, 2, 3]` → `[[], [1], [1,2], [1,2,3], [1,3], [2], [2,3], [3]]`

면접관이 요구할 만한 follow-up 두 가지를 미리 머릿속에 두자. (1) “중복 원소가 있다면?” → 정렬 + 같은 깊이에서 같은 값 스킵. (2) “부분집합이 아니라 합이 target인 부분집합만?” → 가지치기 추가.

<details>
<summary>풀이 보기</summary>

이 문제는 부분집합 골격 그대로다. `start` 인덱스를 들고 다니며 “지금까지 고른 것 뒤에서만 고른다”로 중복을 막는다. 매 호출마다 현재 path를 결과에 사본으로 추가한다. 종료 조건이 따로 없고 for 루프가 자연스럽게 끝나는 것이 부분집합의 특징이다.

말로 설명할 때는 “부분집합은 각 원소를 넣거나 안 넣거나 두 가지이므로 2^n 개. n이 10이면 1024라 가지치기 없이도 충분합니다”까지 짚어주는 게 좋다.

```java
import java.util.ArrayList;
import java.util.List;

public class Subsets {

    public static List<List<Integer>> subsets(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(nums, 0, new ArrayList<>(), result);
        return result;
    }

    private static void backtrack(int[] nums, int start,
                                  List<Integer> path,
                                  List<List<Integer>> result) {
        result.add(new ArrayList<>(path));
        for (int i = start; i < nums.length; i++) {
            path.add(nums[i]);
            backtrack(nums, i + 1, path, result);
            path.remove(path.size() - 1);
        }
    }

    public static void main(String[] args) {
        int[] nums = {1, 2, 3};
        List<List<Integer>> all = subsets(nums);
        for (List<Integer> s : all) {
            System.out.println(s);
        }
    }
}
```

자기 점검 포인트:

- `result.add(new ArrayList<>(path))` 가 들어 있는가? path 자체를 add 하지 않았는가?
- 재귀 호출에 `i + 1`을 넘기는가? `start + 1`이 아닌가?
- `path.remove(path.size() - 1)`이 for 루프 안 마지막에 있는가?

</details>

### 문제 2 (중간) — Combination Sum (중복 원소 사용 가능)

서로 다른 양의 정수 배열 `candidates`와 정수 `target`이 주어진다. 합이 target이 되는 모든 조합을 반환하라. 같은 원소는 여러 번 사용할 수 있다. 같은 조합이 여러 순서로 나오는 걸 피하라.

예) `candidates = [2, 3, 6, 7]`, `target = 7` → `[[2,2,3], [7]]`

이 문제는 LeetCode 39 원본에 가깝다. 라이브 면접에서 자주 나오는 이유는 (1) 중복 사용 허용 + 결과 중복 방지를 동시에 다뤄야 하고, (2) 가지치기를 안 걸면 입력이 커질 때 시간 초과가 자연스럽게 등장하기 때문이다.

핵심 트릭은 두 가지다.

- 같은 조합이 여러 순서로 나오는 걸 막기 위해 “고른 인덱스 이상부터만 다음 원소를 본다” → 다음 호출에 `i`를 넘긴다(중복 사용 허용이므로 `i + 1`이 아닌 `i`).
- 정렬 후 `target - candidates[i] < 0`이면 break. 이후 인덱스는 더 큰 값이라 어차피 모두 컷.

<details>
<summary>풀이 보기</summary>

상태로 들고 다닐 것: `path`(현재까지 고른 숫자들), `remaining`(target에서 합을 뺀 잔액). 잔액이 0이면 정답으로 기록하고 return. 잔액이 음수가 되기 전에 break으로 자른다.

라이브에서 면접관에게 시간 복잡도를 물으면 “target이 작고 candidates가 작아서 실질적으로 트리 깊이는 target / min(candidates), 가지 수는 candidates.length 정도라 작은 입력에선 충분합니다”까지 짚는다.

```java
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class CombinationSum {

    public static List<List<Integer>> combinationSum(int[] candidates, int target) {
        Arrays.sort(candidates);
        List<List<Integer>> result = new ArrayList<>();
        backtrack(candidates, 0, target, new ArrayList<>(), result);
        return result;
    }

    private static void backtrack(int[] candidates, int start, int remaining,
                                  List<Integer> path,
                                  List<List<Integer>> result) {
        if (remaining == 0) {
            result.add(new ArrayList<>(path));
            return;
        }
        for (int i = start; i < candidates.length; i++) {
            int c = candidates[i];
            if (c > remaining) break;        // 정렬되어 있어 이후는 모두 컷
            path.add(c);
            backtrack(candidates, i, remaining - c, path, result); // i 그대로 → 중복 사용 허용
            path.remove(path.size() - 1);
        }
    }

    public static void main(String[] args) {
        int[] candidates = {2, 3, 6, 7};
        int target = 7;
        List<List<Integer>> all = combinationSum(candidates, target);
        for (List<Integer> s : all) {
            System.out.println(s);
        }
    }
}
```

흔한 실수 점검:

- 다음 호출에 `i + 1`을 넘기면 같은 원소를 여러 번 못 쓴다. 문제의 “중복 사용 가능”과 충돌.
- 정렬을 빼먹으면 `if (c > remaining) break`가 깨진다. continue로 바꾸면 동작은 하지만 가지치기가 사라진다.
- `remaining < 0`까지 들어간 뒤 비교하면 path에 이미 음수 잔액 상태가 남는다. for 루프 안에서 즉시 break/continue로 끊는 게 정석.

면접관 follow-up 대비:

- “같은 원소를 한 번씩만 써야 한다면?” → 다음 호출에 `i + 1`. 추가로 입력에 중복이 있을 수 있다면 같은 깊이 같은 값 스킵.
- “조합 개수만 세면 된다면?” → 결과 리스트 대신 카운터, 그러면 메모이제이션으로 DP 전환 가능. 사실상 동전 교환 문제.
- “target이 매우 크면?” → 백트래킹 대신 DP 테이블(coin change)이 더 적절하다는 점을 짚는다.

</details>

## 면접 답변 프레이밍

같은 코드라도 어떻게 설명하느냐에 따라 인상이 달라진다. 시니어 백엔드 후보로서 백트래킹 문제 끝에 면접관이 “이 접근에 대해 더 말해 줄 수 있나요?”라고 물어볼 때 쓸 수 있는 답변 프레이밍 예시.

> “이 문제는 후보 집합에서 부분 해를 점진적으로 만들고, 더 진행할 가치가 없는 분기에서 되돌아가는 백트래킹 패턴입니다. 코드 골격은 선택-재귀-복구 세 단계로 고정되어 있고, 변형은 상태 표현(`start` 인덱스 vs `used` 배열)과 가지치기 조건에서만 일어납니다. 실제 시스템에서도 권한 정책 검사, 룰 매칭, 워크플로 가능 경로 탐색 같은 곳에서 같은 패턴을 씁니다. 입력이 커지면 메모이제이션으로 DP 전환 또는 분기한정으로 한계 가지를 컷하는 식으로 확장합니다.”

이 한 단락을 외워 두면 어떤 백트래킹 문제 뒤에도 자연스럽게 붙일 수 있다.

## 체크리스트

라이브 코딩에서 백트래킹 문제를 만났을 때 코드를 적기 전 30초 동안 머리로 훑을 항목.

- [ ] 부분집합 / 순열 / 조합 / 분기 탐색 중 어디에 해당하는지 분류했는가
- [ ] 상태 변수 후보를 적었는가 (`path`, `start`, `used`, `remaining` 등)
- [ ] 종료 조건과 가지치기 조건을 분리했는가
- [ ] 결과 기록 시 `new ArrayList<>(path)` 사본으로 넣는가
- [ ] for 루프에서 들어갈 때 한 일을 나올 때 모두 되돌리는가 (path, used 등 짝)
- [ ] 중복 입력 처리가 필요하면 정렬 + 같은 깊이 같은 값 스킵을 넣었는가
- [ ] 같은 원소 재사용 허용 여부에 맞게 다음 호출 인덱스를 골랐는가 (`i` vs `i + 1`)
- [ ] 가지치기 기준을 한 가지 이상 적용 가능한지 확인했는가
- [ ] 시간 복잡도를 입력 크기와 함께 입 밖으로 추정했는가
- [ ] 코드 작성 후 작은 입력으로 직접 손추적 한 사이클 돌렸는가

이 체크리스트를 면접 직전 1분 안에 한 번 훑는 습관을 들이면, 손이 먼저 나가고 머리가 따라가는 사고를 막을 수 있다.
