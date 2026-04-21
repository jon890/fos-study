# [초안] Heap과 PriorityQueue로 뚫는 라이브 코딩 Top-K 패턴 (Java)

라이브 코딩에서 "정렬하면 되지 않나요?"라고 먼저 답하는 순간, 면접관의 다음 질문은 거의 정해져 있다. "배열이 엄청 크고 k가 작으면요?" 이 한 마디에 무너지지 않으려면 Heap과 `PriorityQueue`를 손에 익혀둬야 한다. 이 문서는 HackerRank 스타일의 라이브 면접에서 Heap 계열 문제를 만났을 때, 접근 방식을 말로 설명하고 Java 코드로 구현하고 엣지 케이스까지 커버하는 전 과정을 한 번에 훈련하기 위한 스터디 팩이다.

## 왜 이 주제가 중요한가

시니어 백엔드 라이브 코딩에서 Heap/PriorityQueue는 정렬·이분탐색·해시맵 다음으로 가장 자주 나오는 자료구조다. 특히 다음 세 가지 상황에서 반드시 손이 먼저 나가야 한다.

- **Top-K / Bottom-K**: "가장 큰 k개", "가장 자주 등장한 k개 단어", "가장 가까운 k개 좌표"
- **스트리밍 / 온라인 처리**: 전체를 다 볼 수 없거나 다 볼 필요가 없는 경우의 실시간 중앙값, 실시간 Top-K
- **k-way merge**: 여러 정렬된 스트림을 합치는 경우. Kafka 파티션별 정렬 로그 병합, 여러 DB 샤드에서 가져온 정렬된 결과 머지 등 실무에서 백엔드가 자주 마주친다.

실무 관점에서도 의미가 크다. Top-K는 "전체를 `ORDER BY` 해서 `LIMIT k` 할 것인가, 아니면 스트리밍 집계에서 k 크기 힙으로 유지할 것인가"라는 설계 선택으로 그대로 이어진다. 면접관은 알고리즘 문제를 풀면서도 이런 설계 감각을 가진 지원자를 찾는다.

## 핵심 개념 정리

### Heap이란 무엇인가

Heap은 **부모-자식 관계에 대한 순서 조건만 만족시키는 완전 이진 트리**다. 전체 정렬이 아니라 "루트가 항상 최솟값(또는 최댓값)"이라는 약한 조건만 보장한다. 그래서 정렬보다 저렴하다.

- 삽입: O(log n)
- 루트 조회(peek): O(1)
- 루트 제거(poll): O(log n)
- 임의 원소 탐색: O(n) — 이 점을 잊어서 `contains` 남발하면 코드가 느려진다.

### 왜 정렬 대신 Heap을 쓰는가

라이브 코딩에서 "정렬 O(n log n) vs 힙 O(n log k)"를 바로 꺼낼 수 있어야 한다.

- n = 1,000,000, k = 10 → 정렬 ~2천만 연산, 힙 ~330만 연산. 메모리도 n이 아니라 k만 쓰면 된다.
- 데이터가 스트리밍이면 정렬 자체가 불가능하다. 힙은 한 원소씩 흘려 넣으며 유지할 수 있다.
- "최댓값 하나만 필요하다"면 힙도 과하다. 그냥 선형 스캔 O(n)이 더 빠르고 단순하다. 즉 **k가 1이면 힙을 쓰지 말라**는 것도 기억해두면 면접에서 신중함을 보여줄 수 있다.

기준 정리:

| 상황 | 선택 |
|------|------|
| k = 1, 전체 1회 스캔 | 선형 스캔 |
| k ≪ n, 한 번만 | 크기 k 힙 |
| 전체 정렬 결과가 필요 | 정렬 |
| 스트리밍, 계속 갱신 | 힙 (또는 두 개 힙) |
| k-way merge | 각 스트림의 head를 담는 힙 |

### min heap과 max heap 구분

Java `PriorityQueue`는 **기본이 min heap**이다. 즉 `peek()`은 최솟값이다. 이 점이 Top-K 문제에서 가장 흔한 혼동 포인트다.

- "가장 큰 k개를 구하라" → **min heap**을 쓴다. 힙 크기를 k로 유지하면서, 들어오는 값이 힙 루트(현재 k개 중 최소)보다 크면 루트를 제거하고 새 값을 넣는다. 끝나면 힙에 남은 k개가 답이다.
- "가장 작은 k개를 구하라" → **max heap**을 쓴다. 반대로 동작한다.
- 실수 포인트: "가장 큰 k개니까 max heap이 당연하지" 하고 전부 집어넣으면 공간이 O(n)이 된다. Top-K의 핵심은 **반대 방향 힙을 크기 k로 유지**하는 것이다.

### Comparator의 구조

Java에서 힙을 제어하는 건 99% comparator다. 시그니처는 `int compare(a, b)`이고 규칙은 단순하다.

- 음수를 반환하면 `a`가 먼저(=우선순위 높음=루트에 가까움)
- 양수를 반환하면 `b`가 먼저
- 0이면 동등

즉 **"먼저 나와야 하는 걸 '작게' 만들면 된다"**. min heap으로 동작하기 때문이다.

```java
// 값이 큰 것부터 나오게(=max heap)
PriorityQueue<Integer> maxHeap = new PriorityQueue<>((a, b) -> Integer.compare(b, a));

// 빈도 높은 단어 먼저, 동률이면 사전순 먼저
PriorityQueue<Map.Entry<String, Integer>> pq = new PriorityQueue<>((a, b) -> {
    if (!a.getValue().equals(b.getValue())) {
        return Integer.compare(b.getValue(), a.getValue()); // freq desc
    }
    return a.getKey().compareTo(b.getKey()); // lex asc
});
```

## 실무 백엔드 관점에서의 PriorityQueue

알고리즘 문제 너머의 쓰임도 같이 떠올릴 수 있어야 면접에서 깊이가 생긴다.

- **스케줄러 / 작업 큐**: 실행 시각이 가장 빠른 작업을 먼저 꺼내는 타이머 큐. `DelayQueue`, `ScheduledThreadPoolExecutor` 내부가 전부 힙 기반이다.
- **Dijkstra / A\***: 가중 그래프 최단 경로에서 현재까지의 최소 거리 노드를 꺼내는 데 힙을 쓴다. 라우팅, 물류, 게임 네비게이션에서 그대로 쓰이는 구조다.
- **외부 정렬 (External Sort)**: 메모리에 다 못 올리는 큰 파일을 정렬할 때 k-way merge 단계에서 힙을 쓴다. 실무에서 로그/이벤트 배치 처리할 때 본 경험을 묶어서 이야기하면 좋다.
- **Rate limiter / 만료 처리**: "가장 먼저 만료될 토큰"을 O(log n)으로 꺼내야 할 때.

이런 사례를 미리 하나씩 붙여두면 "왜 힙을 썼나요?" 질문이 왔을 때 "Top-K 유지 + O(log n) 갱신 비용 + 루트만 보면 되는 구조" 같은 답을 자연스럽게 내놓을 수 있다.

## 흔한 버그 패턴

라이브에서 떨어뜨리는 실수들은 거의 이 목록 안에서 나온다.

1. **기본이 min heap이라는 걸 잊는다.** "가장 큰 값부터"를 원했는데 `peek()`이 최솟값이라 로직이 완전히 뒤집힌다.
2. **정수 뺄셈 comparator.** `(a, b) -> a - b`는 `a`나 `b`가 음수일 때 오버플로로 부호가 뒤집힐 수 있다. 항상 `Integer.compare(a, b)`를 쓴다.
3. **k번째와 k개를 혼동한다.** "k번째로 큰 값"은 힙 크기 k짜리 min heap의 `peek()`이고, "가장 큰 k개"는 그 힙 전체다.
4. **size 체크 순서.** `offer` → `if (pq.size() > k) pq.poll();` 흐름은 명확하지만, "힙이 비었으면 무조건 넣고, 아니면 루트와 비교"로 쓰면 경계 케이스를 놓치기 쉽다.
5. **tie-breaker 정의 누락.** 빈도가 같으면 어떻게 정렬할지 명시하지 않으면 테스트가 흔들린다. 문제 조건을 다시 읽고 tie-breaker를 반드시 comparator에 넣는다.
6. **불변 값을 바꾼다.** 힙에 들어간 객체의 비교 기준 필드를 외부에서 바꾸면 힙 불변식이 깨진다. `PriorityQueue`는 내부 재정렬을 해주지 않는다.
7. **`remove(Object)` 남용.** O(n) 탐색이다. "임의 원소 제거"가 자주 필요하면 힙이 아니라 `TreeSet` 또는 "lazy deletion + 두 번째 힙" 패턴을 고려해야 한다.
8. **`Iterator` 순서를 정렬 순서로 착각.** `for (X x : pq)`는 순서 보장이 없다. 정렬 순서로 보려면 `poll()`을 반복해야 한다.

## 라이브 면접에서 접근 방식을 설명하는 법

HackerRank 스타일은 **말하면서 코딩**이 기본이다. 다음 6단계 템플릿을 외워두면, 문제를 받자마자 흐름을 선점할 수 있다.

1. **문제 재진술**: "정리하면 … 이 조건이 핵심이고, 입력 크기는 … 범위군요."
2. **브루트포스부터 선언**: "가장 단순한 방법은 전부 정렬 후 앞에서 k개 가져오는 O(n log n)입니다."
3. **제약을 건드려 업그레이드**: "n은 크고 k는 작다고 하셨으니 O(n log k)로 줄일 수 있는 힙 접근이 맞아 보입니다."
4. **자료구조 결정을 말로 확정**: "가장 큰 k개니까 크기 k의 **min heap**을 유지하겠습니다. 루트가 현재 k개 중 최솟값이라, 새로 들어오는 값이 루트보다 크면 교체합니다."
5. **엣지 케이스 먼저 수집**: "k가 0이거나 배열 길이보다 크면? 중복 값이 있으면? 음수는? null 입력 가능성은?"
6. **구현 후 직접 드라이런**: 작은 입력 2~3개로 루프를 말로 돌린다. 시간·공간 복잡도를 다시 한 번 말한다.

이 흐름은 "코드를 얼마나 빨리 쳤는가"보다 "어떤 근거로 자료구조를 선택했는가"를 보여주기 때문에 시니어 포지션에서 특히 유리하다.

## 로컬 연습 환경

- JDK 17 이상 (`PriorityQueue` 자체는 오래된 API지만, `record`·`switch` 패턴을 섞어 쓰면 편하다.)
- 빌드 도구 없이 `javac`, `java` 한 파일로 돌리는 게 가장 빠르다. 라이브 환경을 가정하고 **IDE 자동완성 없이** 풀어보는 훈련도 최소 일주일에 두 번 한다.

실행 루틴 예시:

```bash
mkdir -p ~/coding-live/heap && cd ~/coding-live/heap
# 문제 1개당 파일 하나. main에 테스트 케이스를 직접 박아서 실행.
javac TopKFrequent.java && java TopKFrequent
```

연습 규칙:

- 타이머 25분을 맞춘다. 라이브 면접 한 문제 분량을 가정.
- 풀이 중 웹 검색 금지. `PriorityQueue` API가 기억나지 않으면 기억나는 만큼만 쓰고 나중에 확인.
- 끝난 뒤엔 "내 설명이 그대로 녹음돼도 면접관이 납득했을까?"를 기준으로 회고.

## 연습 문제 2개

두 문제 모두 풀이와 Java 전체 코드는 `<details>` 블록에 숨겨두었다. 먼저 25분 타이머로 직접 풀고, 그다음 펼쳐서 비교한다.

### 문제 1 (쉬움) — Kth Largest Element

정수 배열 `nums`와 정수 `k`가 주어질 때, **k번째로 큰 값**을 반환하라.

- 제약: `1 <= k <= nums.length <= 10^5`, `-10^4 <= nums[i] <= 10^4`.
- 예시
  - `nums = [3,2,1,5,6,4]`, `k = 2` → `5`
  - `nums = [3,2,3,1,2,4,5,5,6]`, `k = 4` → `4`
- 면접관이 이어서 물어볼 수 있는 것: "n이 10^9이고 k가 10이면 어떻게 바꿀 건가요?" → 크기 k min heap 전략을 그대로 유지할 수 있다고 답한다.

<details>
<summary>풀이와 Java 전체 코드 보기</summary>

**접근**: 전체 정렬은 O(n log n). 대신 **크기 k짜리 min heap**을 유지한다. 배열을 훑으면서 힙에 값을 넣고, 크기가 k를 넘으면 루트(=현재 k+1개 중 최솟값)를 버린다. 마지막에 힙의 루트가 k번째로 큰 값이다. 복잡도 O(n log k), 공간 O(k).

**드라이런** (`nums = [3,2,1,5,6,4]`, `k = 2`):

- 3 넣고 heap=[3]
- 2 넣고 heap=[2,3]
- 1 넣고 size>2 → 1 버림, heap=[2,3]
- 5 넣고 size>2 → 2 버림, heap=[3,5]
- 6 넣고 size>2 → 3 버림, heap=[5,6]
- 4 넣고 size>2 → 4 버림, heap=[5,6]
- 루트 = 5 ✅

**자주 하는 실수**: max heap에 전부 넣고 k번 `poll()`하는 것. 답은 맞지만 O(n log n)이라 "정렬이랑 뭐가 다르죠?" 질문에 흔들린다.

```java
import java.util.PriorityQueue;

public class KthLargest {

    public static int findKthLargest(int[] nums, int k) {
        if (nums == null || k <= 0 || k > nums.length) {
            throw new IllegalArgumentException("invalid input");
        }
        PriorityQueue<Integer> minHeap = new PriorityQueue<>(k);
        for (int num : nums) {
            if (minHeap.size() < k) {
                minHeap.offer(num);
            } else if (num > minHeap.peek()) {
                minHeap.poll();
                minHeap.offer(num);
            }
        }
        return minHeap.peek();
    }

    public static void main(String[] args) {
        System.out.println(findKthLargest(new int[]{3, 2, 1, 5, 6, 4}, 2)); // 5
        System.out.println(findKthLargest(new int[]{3, 2, 3, 1, 2, 4, 5, 5, 6}, 4)); // 4
        System.out.println(findKthLargest(new int[]{-1, -2, -3, -4}, 2)); // -2
    }
}
```

</details>

### 문제 2 (중간) — Top K Frequent Words

문자열 배열 `words`와 정수 `k`가 주어질 때, **가장 자주 등장한 단어 k개**를 빈도 내림차순으로 반환하라. 빈도가 같으면 **사전순 오름차순**으로 정렬한다.

- 제약: `1 <= words.length <= 5 * 10^4`, `1 <= k <= 고유 단어 수`.
- 예시
  - `words = ["i","love","leetcode","i","love","coding"]`, `k = 2` → `["i","love"]`
  - `words = ["the","day","is","sunny","the","the","the","sunny","is","is"]`, `k = 4` → `["the","is","sunny","day"]`
- 이 문제에서 면접관이 보고 싶은 것: **tie-breaker comparator**, **크기 k 유지 전략**, **결과를 어떻게 원하는 순서로 뽑는지**.

<details>
<summary>풀이와 Java 전체 코드 보기</summary>

**접근**:

1. `HashMap`으로 빈도를 센다. O(n).
2. 크기 k짜리 **"반대 방향" 힙**을 만든다. 최종 정렬 기준은 "빈도 desc, 단어 asc"지만, 힙에서는 `peek()`이 **가장 약한 후보**(=빈도 작고, 빈도 같으면 단어 큰 쪽)가 되어야 넘치는 순간 루트만 버리면 된다. 즉 comparator가 뒤집힌다.
3. 힙에 전부 넣고 넘칠 때마다 루트를 버린다. 마지막엔 k개가 남는다.
4. 결과는 `poll()`을 반복해 거꾸로 쌓는다. 그래야 빈도 desc / 단어 asc 순서가 된다.

복잡도 O(n log k), 공간 O(n + k).

**자주 하는 실수**:

- 힙 comparator를 "빈도 desc, 단어 asc"로 그대로 넣는 것. 그러면 넘쳤을 때 버려야 할 것은 가장 **뒤에** 있는데, `poll()`은 **앞**을 버린다. 답이 완전히 반대가 된다.
- tie-breaker를 `Integer.compare`로만 쓰고 문자열 비교를 빼먹는 것.
- 최종 결과를 `poll` 순서대로 넣어서 정렬이 거꾸로 나오는 것. `Collections.reverse` 또는 `add(0, x)`로 맞춘다.

```java
import java.util.*;

public class TopKFrequentWords {

    public static List<String> topKFrequent(String[] words, int k) {
        Map<String, Integer> freq = new HashMap<>();
        for (String w : words) {
            freq.merge(w, 1, Integer::sum);
        }

        // 힙 기준: "약한 것이 위로". 빈도 오름차, 빈도 같으면 단어 내림차.
        PriorityQueue<Map.Entry<String, Integer>> heap = new PriorityQueue<>((a, b) -> {
            int freqCmp = Integer.compare(a.getValue(), b.getValue());
            if (freqCmp != 0) {
                return freqCmp;
            }
            return b.getKey().compareTo(a.getKey());
        });

        for (Map.Entry<String, Integer> e : freq.entrySet()) {
            heap.offer(e);
            if (heap.size() > k) {
                heap.poll();
            }
        }

        List<String> result = new ArrayList<>(k);
        while (!heap.isEmpty()) {
            result.add(heap.poll().getKey());
        }
        Collections.reverse(result); // 빈도 desc, 단어 asc 순으로 정렬
        return result;
    }

    public static void main(String[] args) {
        System.out.println(topKFrequent(
                new String[]{"i", "love", "leetcode", "i", "love", "coding"}, 2));
        // [i, love]

        System.out.println(topKFrequent(
                new String[]{"the", "day", "is", "sunny", "the", "the", "the",
                        "sunny", "is", "is"}, 4));
        // [the, is, sunny, day]
    }
}
```

**드라이런 포인트** (`k = 2`, 입력 첫 예시):

- 빈도: `{i:2, love:2, leetcode:1, coding:1}`
- 힙에 넣는 동안 루트(가장 약한 후보)가 바뀌면서, 최종적으로 `i`, `love`만 남는다.
- `poll()` 순서는 `love → i` (약한 순), `reverse` 후 `[i, love]`.

</details>

## 면접 답변 프레이밍

"Heap을 써본 경험이 있나요?"라는 질문은 자료구조 지식을 확인하려는 게 아니라, **언제 쓸지를 판단할 수 있는가**를 보려는 것이다. 답변 구조는 다음을 따른다.

1. **정의**: "Heap은 부모-자식 간 순서만 보장하는 완전 이진 트리이고, Java에선 `PriorityQueue`로 씁니다. 기본이 min heap이라 Top-K 문제에선 반대 방향 힙을 쓰는 게 포인트입니다."
2. **언제 쓰는가**: "전체 정렬이 아니라 **상위 몇 개**만 필요한 경우, 또는 **스트리밍**처럼 전체를 한 번에 볼 수 없는 경우에 씁니다."
3. **실무 예시 묶기**: "최근에 … 요청에서 상위 N개 사용자만 뽑아야 했는데, 전체 정렬 대신 크기 N 힙으로 유지해서 메모리와 시간을 모두 줄였습니다." (실제 경험이 없다면 "스케줄러에서 가장 빠른 실행 시각의 작업을 꺼내는 구조도 힙 기반이라 개념이 동일합니다"처럼 구조적으로 설명한다.)
4. **한계**: "임의 원소 제거나 검색은 O(n)이라, 그 기능이 필요하면 `TreeSet` 또는 해시맵 + 힙 조합을 검토합니다."
5. **확장**: "실시간 중앙값 같은 문제는 min heap과 max heap 두 개를 균형 맞춰 운영하는 패턴이 있습니다."

## 체크리스트

- [ ] `PriorityQueue` 기본이 min heap이라는 것을 1초 안에 답할 수 있다.
- [ ] Top-K "가장 큰 k개"를 묻는 순간 반사적으로 "크기 k의 min heap"이라고 말한다.
- [ ] comparator에서 `a - b` 대신 `Integer.compare`를 쓴다.
- [ ] tie-breaker를 comparator 한 블록 안에서 분기 처리할 수 있다.
- [ ] 힙 크기 유지 로직(`offer` 후 `if size > k poll`)을 외워서 쓴다.
- [ ] 정렬 O(n log n) vs 힙 O(n log k)을 숫자로 설명할 수 있다.
- [ ] `PriorityQueue`의 순회 순서가 정렬 순서가 아니라는 것을 안다.
- [ ] 힙에 들어간 원소의 비교 키를 외부에서 변경하면 안 된다는 걸 안다.
- [ ] `remove(Object)`가 O(n)이라는 것을 알고, 잦은 임의 삭제면 다른 자료구조를 고려한다.
- [ ] 실시간 중앙값, Dijkstra, k-way merge 세 가지 실무 패턴을 한 문장으로 설명할 수 있다.
- [ ] 라이브 코딩에서 문제 재진술 → 브루트포스 → 힙 업그레이드 → 엣지 케이스 → 드라이런 순서로 말하며 푼다.
