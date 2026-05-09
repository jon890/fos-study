# [초안] 라이브 코딩 대비 — Deque 기반 Sliding Window 완전 정복

## 왜 이 주제가 중요한가

라이브 코딩 인터뷰에서 "배열을 한 번 훑으면서 길이 K짜리 윈도우의 최댓값/최솟값을 구하라" 같은 문제는 단골이다. 단순 이중 루프로 풀면 O(N·K)지만, 면접관은 화이트보드 앞에서 "여기 더 빠르게 갈 방법 없을까요?"라고 한 번은 반드시 묻는다. 이때 자연스럽게 꺼내야 할 카드가 바로 **Deque 기반 단조 큐(Monotonic Deque) Sliding Window**다. 시간 복잡도를 O(N)으로 낮추고, 메모리는 O(K)로 유지된다는 명확한 trade-off 설명이 가능하다.

백엔드 시니어 후보에게 이 패턴은 단순 알고리즘 문제 그 이상이다. 실제로 모니터링 시스템에서 최근 N초 윈도우의 peak latency 추적, 스트리밍 데이터에서 최근 이벤트 윈도우의 임계치 추적, rate limiter의 슬라이딩 카운터 등에서 같은 골격이 반복된다. "이 자료구조를 왜 쓰는지" 한 줄로 설명할 수 있어야 라이브 코딩에서 흔들리지 않는다.

## 핵심 개념 — 왜 Deque인가

### 윈도우 max/min 문제의 본질

길이 N의 배열 `nums`와 윈도우 크기 K가 주어졌을 때, 각 윈도우의 최댓값을 구한다고 하자. 윈도우는 한 칸씩 오른쪽으로 이동하므로 N-K+1개의 결과가 나온다.

순진한 접근:

```
for each window:
    max = -inf
    for j in window:
        max = max(max, nums[j])
```

O(N·K). K=10^5, N=10^6이면 10^11 연산. 라이브 코딩에서 면접관이 "데이터 크기가 100만 정도면요?"라고 말하는 순간 이 풀이는 죽은 풀이다.

### Heap은 왜 부족한가

PriorityQueue를 떠올릴 수 있다. 윈도우에 들어오는 원소를 push, 나가는 원소를 remove. 하지만 `PriorityQueue.remove(Object)`는 **O**(K) 다. 결과적으로 O(N·K)에서 O(N·log K + N·K)로 오히려 더 나빠질 수 있다. "Lazy deletion으로 보완하면?"이 가능한데 — 이건 면접에서 중간 단계로 언급할 가치는 있지만 최종 풀이로는 약하다. 면접관은 "그것보다 더 단순하면서 O(N) 보장되는 거 없어요?"라고 밀어붙인다.

### Deque의 핵심 아이디어 두 가지

**아이디어 1: 단조성**(Monotonicity)

윈도우 안에 있는 인덱스들 중에서, 어떤 인덱스 `i`보다 뒤에 있고 값이 같거나 더 큰 인덱스 `j`가 있다면, `i`는 **앞으로 절대 답이 될 수 없다**. 윈도우가 어디로 움직이든 `j`가 윈도우 안에 살아 있는 한 답은 `j`(또는 더 큰 누군가)이지 `i`가 아니다. 그러니 `i`는 그냥 버리면 된다.

이 통찰을 자료구조에 박아넣은 것이 **단조 감소 deque**다. deque 안의 인덱스들이 가리키는 값들이 항상 단조 감소하도록 유지한다. 새 원소 `nums[r]`을 넣을 때, deque 뒤쪽에서 `nums[r]`보다 작거나 같은 원소들을 모두 pop해버린다. 그 후 `r`을 push한다. 결과적으로 deque의 front는 현재 윈도우의 최댓값 인덱스가 된다.

**아이디어 2: 인덱스 만료**

deque에 값이 아니라 **인덱스**를 저장하는 게 핵심이다. 윈도우가 오른쪽으로 이동하면 left 경계가 따라온다. deque의 front 인덱스가 left 경계 밖으로 나갔으면 (즉 `front < r - K + 1`) front를 pop한다. 인덱스를 저장해야만 "이 원소가 윈도우 안에 살아 있는지"를 비교할 수 있다.

### 왜 O(N)인가 — 분할 상환 분석

각 인덱스는 deque에 **정확히 한 번 push**되고 **최대 한 번 pop** 된다 (뒤에서 단조성으로 밀려나거나, 앞에서 윈도우 밖으로 나가거나). 따라서 전체 push/pop 횟수의 합은 2N 이하다. 이중 for문처럼 보이지만 안쪽 while은 분할 상환 O(1)로 보면 된다. 면접관이 "왜 O(N)인지 설명해보세요"라고 물어볼 때 이 한 단락을 그대로 말로 풀 수 있어야 한다.

## 백엔드 실무에서의 같은 패턴

이 패턴이 단순 알고리즘 문제로 끝나지 않는 이유.

- **모니터링/SRE**: 최근 60초 동안의 max latency를 매 초 갱신하는 슬라이딩 윈도우. 단조 deque로 구현하면 초당 도착 이벤트 수에 무관하게 최댓값 갱신이 분할 상환 O(1).
- **레이트 리미터**: 정확히 같은 자료구조는 아니지만, "최근 윈도우 안의 토큰 수" 추적은 같은 사고방식이다. 만료된 인덱스를 앞에서 버리고, 새 이벤트는 뒤로 push.
- **시계열 알림**: "최근 N개 샘플의 최댓값이 임계치 초과 시 알림" 같은 조건. 데이터가 고빈도로 들어올 때 PriorityQueue로 짜면 GC 압력과 remove 비용이 부담된다. 단조 deque는 그냥 ArrayDeque 하나로 끝난다.

라이브 코딩 면접에서 이 연결을 한두 문장 던져주면 "단순 LeetCode 풀이 외운 게 아니구나"라는 신호가 된다.

## Bad vs Improved — 같은 문제, 두 가지 풀이

### Bad: 이중 루프

```java
public int[] maxSlidingWindowNaive(int[] nums, int k) {
    int n = nums.length;
    int[] ans = new int[n - k + 1];
    for (int i = 0; i <= n - k; i++) {
        int max = Integer.MIN_VALUE;
        for (int j = i; j < i + k; j++) {
            max = Math.max(max, nums[j]);
        }
        ans[i] = max;
    }
    return ans;
}
```

문제점:
- O(N·K). N=10^5, K=10^4이면 10^9 연산. TLE 직행.
- 동일 원소를 K번 다시 본다. 윈도우가 한 칸 움직였을 뿐인데 K-1개 원소를 또 비교한다.

### Improved: 단조 감소 Deque

```java
public int[] maxSlidingWindow(int[] nums, int k) {
    int n = nums.length;
    int[] ans = new int[n - k + 1];
    Deque<Integer> dq = new ArrayDeque<>(); // store indices, values monotonically decreasing

    for (int r = 0; r < n; r++) {
        // 1) expire: drop indices that fell out of window
        while (!dq.isEmpty() && dq.peekFirst() <= r - k) {
            dq.pollFirst();
        }
        // 2) maintain monotonicity: drop smaller-or-equal tails
        while (!dq.isEmpty() && nums[dq.peekLast()] <= nums[r]) {
            dq.pollLast();
        }
        // 3) push current index
        dq.offerLast(r);
        // 4) record answer once we have a full window
        if (r >= k - 1) {
            ans[r - k + 1] = nums[dq.peekFirst()];
        }
    }
    return ans;
}
```

읽을 때 주의할 부분:
- `dq.peekFirst() <= r - k` — 등호 위치가 자주 틀린다. 윈도우는 `[r-k+1 .. r]`이므로 `r-k`는 이미 밖이다. `<` 가 아니라 `<=`.
- `nums[dq.peekLast()] <= nums[r]` — 등호를 넣지 않으면 같은 값이 deque에 누적된다. 답은 맞지만 메모리/시간이 늘어나고, 최솟값 변형에서는 다른 값에 묻혀 답이 틀릴 수 있다. 안전하게 등호 포함.
- 답 기록 조건 `r >= k - 1` — 첫 윈도우가 완성되는 시점부터 기록.

## 구현 시 흔한 버그 5선

라이브 코딩 중 화이트보드에서 가장 자주 미끄러지는 지점들. 면접 직전 한 번 더 훑어둔다.

1. **deque에 값을 저장**한다. 인덱스를 저장해야 윈도우 만료 비교가 가능하다. 값만 저장하면 만료 시점에 같은 값이 윈도우 안에도 있는지 구분 못 한다.
2. **만료 조건의 등호** 실수. 윈도우 `[r-k+1, r]`. `dq.peekFirst() < r-k+1`도 맞고 `dq.peekFirst() <= r-k`도 맞다. 두 표현 섞이면 한쪽이 off-by-one.
3. **단조성 비교의 등호 누락**. 같은 값이 누적되어 메모리가 커지거나, min 변형에서 미세하게 답이 어긋난다.
4. **답 기록 시점**. 윈도우가 K개 채워지기 전(`r < k-1`)에는 기록하지 않는다. 빈 deque 상태에서 peek하다 NPE 또는 잘못된 인덱스 접근.
5. **min과 max 혼동**. 단조 감소 deque → 윈도우 max. 단조 증가 deque → 윈도우 min. 비교 부등호 방향만 뒤집으면 된다. 평소에 양쪽 다 손에 익혀두기.

추가로 자주 나오는 미세 함정:
- `LinkedList` vs `ArrayDeque`. `ArrayDeque`가 캐시 친화적이고 빠르다. Java에서 deque의 표준 선택은 `ArrayDeque`다. `LinkedList`는 면접에서 "왜 그걸 썼나요?" 한 번 들어올 수 있다.
- `Stack`을 deque 대용으로 쓰지 말 것. `Stack`은 동기화 비용이 있고 deprecated 취급이다.

## 면접에서 접근 방식을 설명하는 방법

라이브 코딩에서 코드를 치기 **전에** 1~2분 동안 접근 방식을 말로 푸는 단계가 가장 중요하다. 면접관이 평가하는 건 "이 사람이 문제를 어떻게 해체하는가"다. 다음 5단계 스크립트를 외워두면 흔들리지 않는다.

1. **문제 재진술**: "윈도우 길이 K, 배열을 한 번 훑으며 각 윈도우의 최댓값을 출력. 결과는 N-K+1개."
2. **순진한 풀이 언급**: "이중 루프로 O(N·K). N, K가 커지면 TLE. 더 줄여보겠습니다."
3. **핵심 통찰**: "윈도우 안에서 어떤 원소보다 뒤에 더 큰(같거나 큰) 원소가 들어오면, 앞 원소는 다시는 답이 될 수 없습니다. 이걸 자료구조에 반영하겠습니다."
4. **자료구조 선택**: "Deque에 인덱스를 저장하고, 값이 단조 감소하도록 유지합니다. 새 원소가 들어오면 뒤에서 작은 값들을 pop, 앞에서 윈도우 밖 인덱스를 pop. front가 항상 현재 윈도우의 최댓값."
5. **복잡도**: "각 인덱스가 deque에 한 번 push되고 한 번 pop되므로 분할 상환 O(N), 메모리 O(K)."

이 5단계를 1분 30초 안에 말한 뒤 코딩에 들어가면, 코드가 조금 어색해도 면접관은 이미 통과 신호를 받은 상태다.

질문이 들어올 만한 follow-up도 미리 답을 준비해두자.

- **"K가 동적으로 변하면?"** → 단조 deque는 K가 고정일 때 가장 깔끔. K가 바뀌면 윈도우 정의가 흔들리므로 BIT/Segment Tree 같은 다른 도구를 검토.
- **"중복 원소가 많으면?"** → 단조성 비교에서 `<=`로 등호 포함하면 deque가 깨끗하게 유지. 답은 동일.
- **"최댓값과 최솟값을 동시에?"** → deque 두 개를 병렬 유지. 메모리 2배, 시간은 여전히 O(N).
- **"스트리밍이라 N을 모를 때?"** → 같은 패턴. 단지 결과 배열 대신 콜백/이벤트 발행으로 바꾼다.

## 로컬 연습 환경

라이브 코딩은 익숙한 손에서 나온다. 다음 환경을 준비해두면 반복 연습이 빨라진다.

- JDK 17 이상. `sdkman`으로 설치: `sdk install java 17.0.10-tem`.
- 단일 파일 실행: `java Solution.java` (JEP 330, JDK 11+). main이 있는 파일을 그대로 실행 가능.
- 입출력은 표준 입출력으로 받는 연습. HackerRank/CodeSignal 라이브 코딩은 stdin/stdout 기반이 많다.

연습 템플릿:

```java
import java.util.*;
import java.io.*;

public class Solution {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        // parse input
        // call solver
        // print output
    }
}
```

`BufferedReader`/`StringTokenizer` 조합은 `Scanner`보다 한 자릿수 빠르다. 라이브 코딩에서 N=10^6 입력을 받는데 Scanner 쓰면 입력 단계에서 TLE 난다.

## 연습 문제 — 정확히 2개

면접 직전에 한 번 풀어보고 손에 익혀두기 좋은 두 문제. 풀이는 details 안에 숨겨두었으니, 먼저 코드를 안 보고 화이트보드에 적어본 뒤 펼친다.

### 문제 1 (쉬움) — 윈도우 최댓값 출력

길이 N의 정수 배열과 윈도우 크기 K가 주어진다. 모든 길이-K 윈도우의 최댓값을 공백으로 구분해 한 줄에 출력하시오.

- 입력: 첫 줄 `N K`, 둘째 줄 정수 N개
- 제약: 1 ≤ K ≤ N ≤ 10^6, |값| ≤ 10^9
- 시간 제한: 1초

예시:

```
입력
8 3
1 3 -1 -3 5 3 6 7

출력
3 3 5 5 6 7
```

<details>
<summary>풀이 보기</summary>

핵심: 단조 감소 deque에 인덱스를 저장. front가 현재 윈도우의 최댓값.

값 범위가 int를 벗어날 수 있으니 `long`으로 받는 게 안전하지만, 위 제약(|값| ≤ 10^9)이면 int로 충분. 입력이 N=10^6이므로 `BufferedReader`+`StreamTokenizer` 조합으로 입력 속도 확보.

```java
import java.util.*;
import java.io.*;

public class Solution {
    public static void main(String[] args) throws IOException {
        StreamTokenizer in = new StreamTokenizer(new BufferedReader(new InputStreamReader(System.in)));
        in.nextToken(); int n = (int) in.nval;
        in.nextToken(); int k = (int) in.nval;
        int[] nums = new int[n];
        for (int i = 0; i < n; i++) {
            in.nextToken();
            nums[i] = (int) in.nval;
        }

        StringBuilder sb = new StringBuilder();
        Deque<Integer> dq = new ArrayDeque<>();
        for (int r = 0; r < n; r++) {
            while (!dq.isEmpty() && dq.peekFirst() <= r - k) {
                dq.pollFirst();
            }
            while (!dq.isEmpty() && nums[dq.peekLast()] <= nums[r]) {
                dq.pollLast();
            }
            dq.offerLast(r);
            if (r >= k - 1) {
                sb.append(nums[dq.peekFirst()]);
                if (r != n - 1) sb.append(' ');
            }
        }
        System.out.println(sb);
    }
}
```

체크 포인트:
- 만료 조건 `dq.peekFirst() <= r - k`. 등호 위치 다시 확인.
- 단조 비교 `<=`. 같은 값 누적 방지.
- 출력은 `StringBuilder`로 모은 뒤 한 번에 println. N=10^6에서 println 반복은 출력 자체가 병목.

복잡도: 시간 O(N), 공간 O(K).
</details>

### 문제 2 (중간) — 윈도우 max - min ≤ T 인 가장 긴 부분 배열

길이 N의 정수 배열과 정수 T가 주어진다. 부분 배열의 길이를 가능한 한 길게 잡되, 그 부분 배열의 (최댓값 − 최솟값) ≤ T가 성립해야 한다. 가능한 가장 긴 길이를 출력하시오.

- 입력: 첫 줄 `N T`, 둘째 줄 정수 N개
- 제약: 1 ≤ N ≤ 10^5, 0 ≤ T ≤ 10^9, |값| ≤ 10^9
- 출력: 조건을 만족하는 가장 긴 부분 배열의 길이

예시:

```
입력
7 3
1 5 4 7 3 9 2

출력
3
```

(부분 배열 `[5, 4, 7]`은 max−min = 3, `[4, 7, 3]`은 max−min = 4. `[5,4,7]`이 길이 3이며 max−min=3으로 조건 만족. 길이 4 이상의 부분 배열은 모두 max−min > 3이라 답은 3.)

<details>
<summary>풀이 보기</summary>

핵심: **두 개의 단조 deque**로 슬라이딩 윈도우 max와 min을 동시에 유지하면서, **two pointer**로 윈도우 길이를 늘렸다 줄였다 한다. 윈도우 길이 K가 고정이 아니라 가변이라는 점이 문제 1과 다르다.

알고리즘:
1. 오른쪽 포인터 `r`을 한 칸씩 늘리며 새 원소를 두 deque에 반영.
2. 현재 윈도우의 max(maxDq.front)와 min(minDq.front) 차이를 본다.
3. 차이가 T보다 크면, 왼쪽 포인터 `l`을 오른쪽으로 한 칸 이동시키고 두 deque의 front를 만료 시킨다.
4. 매 단계에서 `r - l + 1`로 답 갱신.

각 인덱스는 두 deque 각각에 한 번 push, 한 번 pop. 전체 O(N).

```java
import java.util.*;
import java.io.*;

public class Solution {
    public static void main(String[] args) throws IOException {
        StreamTokenizer in = new StreamTokenizer(new BufferedReader(new InputStreamReader(System.in)));
        in.nextToken(); int n = (int) in.nval;
        in.nextToken(); long t = (long) in.nval;
        int[] nums = new int[n];
        for (int i = 0; i < n; i++) {
            in.nextToken();
            nums[i] = (int) in.nval;
        }

        Deque<Integer> maxDq = new ArrayDeque<>(); // monotonically decreasing values
        Deque<Integer> minDq = new ArrayDeque<>(); // monotonically increasing values

        int l = 0;
        int best = 0;
        for (int r = 0; r < n; r++) {
            while (!maxDq.isEmpty() && nums[maxDq.peekLast()] <= nums[r]) {
                maxDq.pollLast();
            }
            maxDq.offerLast(r);
            while (!minDq.isEmpty() && nums[minDq.peekLast()] >= nums[r]) {
                minDq.pollLast();
            }
            minDq.offerLast(r);

            while ((long) nums[maxDq.peekFirst()] - (long) nums[minDq.peekFirst()] > t) {
                l++;
                if (maxDq.peekFirst() < l) maxDq.pollFirst();
                if (minDq.peekFirst() < l) minDq.pollFirst();
            }
            best = Math.max(best, r - l + 1);
        }
        System.out.println(best);
    }
}
```

체크 포인트:
- 차이 계산은 반드시 `long`. `int` 두 개의 차이가 int 범위를 넘을 수 있다(|값| ≤ 10^9이면 차이가 2·10^9까지 가능, int overflow).
- max 유지에는 `<=`로 단조 감소, min 유지에는 `>=`로 단조 증가.
- 만료 조건은 인덱스가 `l` 미만일 때. K가 가변이라 `r-k`가 아니라 `l`을 기준으로 비교한다. 문제 1과 다른 부분이니 헷갈리면 손이 굳는다.
- `l`을 한 칸씩 옮기지만, 한 단계에서 여러 칸 이동할 수 있다. while로 묶는다.

복잡도: 시간 O(N), 공간 O(N).

면접에서 follow-up: "T=0이면?" → 같은 값으로만 이루어진 가장 긴 연속 구간 길이. 같은 코드가 그대로 돌아가는지 머릿속에서 한 번 시뮬레이션.
</details>

## 면접 답변 프레이밍 (시니어 백엔드 관점)

라이브 코딩이 끝난 직후 또는 행동 면접 단계에서 "이걸 실제 시스템에 어떻게 응용해본 적 있어요?"라는 질문이 종종 따라붙는다. 외운 LeetCode 답변이 아니라 본인 경험과 엮어 답하는 후보가 점수를 받는다.

답변 골격:

> "단조 deque의 핵심은 '뒤에 더 강한 원소가 들어오면 앞 원소는 더 이상 답에 기여하지 않는다'는 통찰입니다. 저는 이걸 모니터링 파이프라인의 슬라이딩 max latency 추적에서 응용해본 적이 있습니다. 매 초 들어오는 latency 샘플을 단조 deque로 관리하면, 최근 60초 윈도우 max를 push/pop 분할 상환 O(1)로 유지할 수 있습니다. PriorityQueue 기반은 remove 비용 때문에 고빈도 이벤트에서 GC 압력이 컸는데, ArrayDeque 기반으로 바꾸니 평균 처리 latency가 한 자릿수 ms 수준으로 안정화됐습니다."

핵심 포인트:
- **자료구조의 본질적 통찰**을 한 줄로 말한다.
- **다른 대안과의 비교**를 항상 곁들인다(여기서는 PriorityQueue).
- **측정 가능한 결과**로 마무리한다(latency 수치, GC 횟수, 처리량).

이 골격은 이 토픽 외에도 거의 모든 자료구조 follow-up에서 재사용 가능하다. "이 패턴을 실제로 어디 써봤어요?" 질문이 나오면 30초 안에 위 형식으로 답할 수 있도록 미리 입에 붙여둔다.

## 마지막 점검 체크리스트

라이브 코딩 직전, 화면 켜기 전 30초 안에 한 번 머릿속으로 훑는다.

- [ ] deque에 **인덱스**를 저장한다 (값 아님).
- [ ] **만료**: front 인덱스가 윈도우 밖이면 pollFirst.
- [ ] **단조성**: 새 원소 ≥ tail이면 pollLast (max용 단조 감소).
- [ ] **min 변형**은 부등호 방향만 뒤집는다.
- [ ] **답 기록**은 `r >= k - 1`부터.
- [ ] `ArrayDeque` 사용. `LinkedList`/`Stack` 회피.
- [ ] 입력 파서는 `BufferedReader` 또는 `StreamTokenizer`. `Scanner` 회피.
- [ ] 출력은 `StringBuilder`로 모아 한 번에 flush.
- [ ] 시간 복잡도 설명: 분할 상환 O(N).
- [ ] 공간 복잡도 설명: O(K).
- [ ] 차이 계산이 들어가는 변형은 `long`으로 캐스팅.
- [ ] 가변 윈도우는 `r-k`가 아니라 `l`을 기준으로 만료.
- [ ] 코딩 전에 5단계 설명 스크립트 1분 30초 안에 말하기.
- [ ] follow-up 후보: K 동적/스트리밍/min+max 동시/실무 응용.
