# [초안] Java 라이브 코딩 - Intervals 완전 정복: 정렬·병합·sweep line 면접 대비

## 왜 이 주제가 중요한가

Intervals 문제는 HackerRank, LeetCode, 그리고 실제 시니어 백엔드 면접 라이브 코딩에서 가장 자주 등장하는 패턴 중 하나다. 이유는 단순하다. 실제 백엔드 시스템은 "시간 구간"을 다루는 일이 너무 많다. 캘린더 예약 충돌 판정, 광고 노출 기간 겹침 제거, 쿠폰/프로모션 유효기간 병합, 로그 시간대 집계, rate limiting window, TTL 기반 캐시 만료 구간 계산, 배포 가능 시간 슬롯 조회 — 전부 intervals 문제다.

면접관 입장에서도 intervals는 이상적인 문제다. 코드 30줄 이내에 풀리지만, 후보자가 정렬의 필요성을 인지하는지, 겹침 조건을 edge case 포함해서 정확히 쓸 수 있는지, O(n log n) 복잡도를 설명할 수 있는지, 입력이 거대할 때 스트리밍/오프라인 전략 차이를 아는지까지 모두 검증할 수 있다. 40분짜리 세션이라면 보통 "merge intervals → meeting rooms II" 두 문제로 흐름이 이어진다.

라이브 코딩 관점에서 intervals의 핵심은 **구현 자체보다 접근 방식을 말로 설명하는 능력**이다. 아래에서는 그 말하기 시나리오까지 같이 정리한다.

## 핵심 개념 1: interval 표현과 "겹침"의 정확한 정의

interval은 보통 `[start, end]` 쌍으로 표현한다. 그런데 면접에서 가장 먼저 확인해야 할 것은 경계가 **닫힌 구간(inclusive)인지 반열린 구간(half-open, `[start, end)`)인지**다. 이걸 가정하지 않고 코딩을 시작하면 겹침 판정에서 1칸 차이로 계속 틀린다.

두 구간 `A = [a1, a2]`, `B = [b1, b2]`가 겹치는지 판정하는 조건:

- 닫힌 구간: `a1 <= b2 && b1 <= a2`
- 반열린 구간 `[start, end)`: `a1 < b2 && b1 < a2`

면접관이 "회의실 예약 9:00~10:00과 10:00~11:00이 겹치냐"고 물으면 정답은 "반열린 구간으로 모델링하면 안 겹친다"이다. 이런 질문을 먼저 던지는 것 자체가 점수를 얻는다.

겹침의 **부정**으로 판정하는 방식도 자주 쓴다. "겹치지 않는다 = 한쪽이 다른 쪽보다 완전히 앞이거나 완전히 뒤"

```
!overlap  ⇔  a2 < b1 || b2 < a1   (닫힌 구간)
```

이 변형은 "겹치지 않는 쌍을 세라" 문제에서 바로 쓸 수 있다.

## 핵심 개념 2: 정렬 후 병합 패턴 (merge intervals)

intervals 문제의 90%는 **start 기준 정렬 후 한 번 훑기**로 풀린다. 템플릿은 다음과 같다.

```
1. start 오름차순 정렬
2. 결과 리스트에 첫 구간 push
3. 이후 구간마다:
   - 마지막 결과 구간과 겹치면 end를 max로 확장
   - 겹치지 않으면 새 구간 push
```

시간 복잡도는 정렬이 지배해 O(n log n), 공간은 결과 저장 O(n)이다. "왜 start로 정렬하나요?"라는 질문이 반드시 따라온다. 답: start로 정렬해야 "현재 들어오는 구간이 이전 구간의 연장선인지 여부"만 검사하면 되고, 이미 확정된 앞 구간들을 다시 볼 필요가 없어 한 번의 선형 스캔으로 끝난다. end로 정렬하면 이 단조성이 깨진다.

**흔한 실수**: 병합 조건을 `current.start < last.end`로만 쓰는 경우. `[1,3]`과 `[3,5]`를 닫힌 구간으로 병합하려면 `<=`가 맞다. 이걸 반열린 구간인지 명확히 정하지 않고 코딩하면 테스트 절반이 날아간다.

## 핵심 개념 3: meeting rooms 류 사고방식

meeting rooms II는 "회의 목록이 주어졌을 때 필요한 회의실의 최소 개수"를 묻는다. 이 문제는 merge intervals와 **근본적으로 다른 문제**다. 병합이 아니라 **동시에 열려 있는 구간의 최댓값**을 구해야 한다.

대표적 풀이 두 가지:

**풀이 A — 분리 정렬 (two-pointer)**
- starts 배열과 ends 배열을 각각 정렬
- start 포인터로 진행하며 `start[i] < end[j]`면 방 +1, 아니면 j++ (방이 하나 비워짐)
- 진행 중 최대 동시 사용 수를 추적

**풀이 B — min-heap**
- start 기준 정렬
- heap에 end를 저장 (현재 사용 중인 방들의 종료 시각)
- 새 구간 start가 heap.peek() (가장 빨리 끝나는 방의 end) 이상이면 poll (재사용)
- 새 구간의 end를 push
- 마지막 heap.size()가 답

heap 풀이가 더 직관적이고 설명하기 쉽다. 라이브 코딩에서는 heap 풀이를 먼저 말하고 "공간을 더 줄이려면 분리 정렬도 있다"고 언급하면 좋다.

## 핵심 개념 4: sweep line 기초

sweep line은 intervals 문제를 **이벤트 시퀀스**로 재해석하는 기법이다. 각 구간 `[s, e]`를 두 이벤트로 쪼갠다.

- `(s, +1)` — 구간 시작
- `(e, -1)` — 구간 종료

이벤트를 시간순으로 정렬해 훑으면서 누적합을 유지하면, 그 누적합이 바로 **현재 그 시각에 활성인 구간 수**가 된다. meeting rooms II도 sweep line으로 풀 수 있다: 누적합의 최댓값이 답이다.

sweep line이 빛나는 순간은 이런 문제다.
- "어떤 시각에 가장 많은 사용자가 로그인해 있었는가"
- "모든 광고 노출 구간의 합집합의 길이는?"
- "특정 시간대마다 동시 접속 수가 K 이상이던 총 시간은?"

이벤트 정렬 시 **동률 타이브레이킹**이 함정이다. 시각이 같을 때 `-1`(종료)을 먼저 처리할지 `+1`(시작)을 먼저 처리할지에 따라 답이 달라진다.
- "같은 시각에 끝나고 시작하면 이어진 것으로 본다" → 종료(-1)를 뒤로 보내거나, 시작(+1)을 먼저 처리
- "같은 시각이면 독립된 두 구간" → 종료(-1)를 먼저

면접에서 이걸 먼저 확인하면 "edge case를 잡는다"는 강한 시그널이 된다.

## 실전 백엔드 활용 예시

- **캘린더 API의 freeBusy 조회**: 여러 캘린더의 busy 구간을 합쳐 반환할 때 merge intervals.
- **쿠폰 유효기간 충돌 판정**: 한 사용자에게 중복 적용 불가한 쿠폰을 발급할 때 기존 쿠폰 구간과 overlap 체크.
- **광고 노출 중복 제거**: 여러 캠페인이 겹치는 구간을 제거한 실질 노출 시간 계산 — sweep line.
- **트래픽 피크 분석**: 세션 시작/종료 로그에서 동시 접속자 최댓값 — meeting rooms II와 동형.
- **배포 타임 슬롯 예약**: 요청된 배포 시간이 비어 있는 슬롯인지 확인 — sorted interval tree 또는 TreeMap 기반 floor/ceiling.
- **Redis/DB TTL 구간 병합**: 캐시 무효화 구간들을 병합해 한 번에 invalidate.

## Bad vs Improved 예제

### Bad 1: 정렬 없이 이중 루프로 겹침 검사
```java
// O(n^2), 30만 건이면 9*10^10 연산 → 타임아웃
for (int i = 0; i < intervals.length; i++) {
  for (int j = i + 1; j < intervals.length; j++) {
    if (overlap(intervals[i], intervals[j])) { ... }
  }
}
```
문제점: 선형 스캔으로 해결 가능한 문제를 제곱으로 만들었다. 백엔드에서 "쿠폰 목록이 수십만 건"이면 바로 장애.

### Improved 1: 정렬 + 선형 병합
```java
Arrays.sort(intervals, Comparator.comparingInt(a -> a[0]));
List<int[]> merged = new ArrayList<>();
for (int[] cur : intervals) {
  if (!merged.isEmpty() && merged.get(merged.size()-1)[1] >= cur[0]) {
    merged.get(merged.size()-1)[1] = Math.max(merged.get(merged.size()-1)[1], cur[1]);
  } else {
    merged.add(cur);
  }
}
```

### Bad 2: meeting rooms에서 "시작 시각이 겹치는 개수"만 세기
```java
// 틀린 접근: 시작만 보고 "동시에 시작한 건 1개면 방 1개"라고 판단
```
문제점: 현재 활성인 구간 수를 추적하지 않으면 "11시에 하나 시작, 11:30에 또 시작, 12시에 둘 다 진행 중" 같은 상황을 잡지 못한다.

### Improved 2: min-heap 풀이
```java
Arrays.sort(intervals, Comparator.comparingInt(a -> a[0]));
PriorityQueue<Integer> endHeap = new PriorityQueue<>();
for (int[] cur : intervals) {
  if (!endHeap.isEmpty() && endHeap.peek() <= cur[0]) {
    endHeap.poll();
  }
  endHeap.offer(cur[1]);
}
int rooms = endHeap.size();
```
`<=`인지 `<`인지는 반열린/닫힌 구간 컨벤션에 따라 결정. 반열린이면 `<=`, 닫힌이면 `<`.

### Bad 3: 경계값 처리 누락
```java
// 빈 배열, 한 개 구간, 완전히 포함된 구간, 동일 구간 등 edge case 누락
return intervals[0];
```
문제점: 라이브 코딩에서 가장 감점 요소. `intervals.length == 0` 처리 먼저 쓰고 시작한다.

## 구현 시 흔한 버그

1. **정렬 키 오류** — end로 정렬하고 병합 로직 적용.
2. **경계 부등호 혼동** — `[1,2], [2,3]` 병합 여부를 확정하지 않음.
3. **in-place 수정 중 새 리스트에 담지 않음** — 원본 배열을 수정하면 debug가 어려워진다. 새 List 생성 권장.
4. **오버플로 가능성** — `mid = (lo + hi) / 2` 대신 `lo + (hi - lo) / 2`. intervals 문제 자체는 overflow가 드물지만 이분 탐색 변형에서 자주 등장.
5. **sweep line 타이브레이킹 미정의** — 같은 시각의 +1/-1 순서 미지정.
6. **Comparator에서 뺄셈 사용** — `a[0] - b[0]`은 int overflow 위험. `Integer.compare(a[0], b[0])` 또는 `Comparator.comparingInt` 사용.
7. **병합 결과를 다시 배열로 변환할 때 `toArray(new int[0][])` 누락** — 라이브 코딩에서 컴파일 에러로 당황.
8. **Heap에 Integer가 아니라 int[]를 넣으면서 Comparator 미지정** — `PriorityQueue<int[]>`를 그냥 만들면 런타임 ClassCastException.

## 라이브 면접에서 접근 방식을 설명하는 방법

라이브 코딩에서 면접관이 실제로 평가하는 것은 **말하는 순서**다. 다음 템플릿을 외워두면 30초 안에 reasonable한 접근을 꺼낼 수 있다.

1. **입력/출력 재확인** — "구간은 닫힌 구간인가요, 반열린인가요? 정렬된 상태로 들어오나요? 빈 입력 가능합니까?"
2. **brute force 먼저 언급** — "모든 쌍을 비교하면 O(n^2)입니다. 개선 여지가 있을 것 같습니다."
3. **정렬 아이디어 제안** — "start 기준으로 정렬하면 이전 구간과의 관계만 보면 되어 O(n log n)으로 줄어듭니다."
4. **예시 1~2개를 손으로 따라가기** — "`[[1,3],[2,6],[8,10]]`이면 `[1,3]`과 `[2,6]`이 겹쳐서 `[1,6]`, 그다음 `[8,10]`은 분리."
5. **edge case 나열** — 빈 배열, 단일 구간, 완전 포함, 경계 인접(`[1,2][2,3]`).
6. **코드 작성** — Comparator를 먼저 선언하고, 결과 컨테이너를 준비한 뒤 루프.
7. **돌려보기** — 샘플 입력을 손으로 trace.
8. **복잡도 요약** — "시간 O(n log n), 공간 O(n)."
9. **확장 질문 선제** — "만약 구간이 스트리밍으로 들어오면 TreeMap으로 floor/ceiling을 써서 amortized O(log n)에 처리 가능합니다."

이 9단계를 **말하면서** 코딩하면 "코딩만 하는 후보"와 차별화된다.

## 로컬 연습 환경

JDK 17+ 기준, 단일 파일로 빠르게 돌려볼 수 있는 세팅을 권장한다.

```
mkdir -p ~/playground/intervals
cd ~/playground/intervals
# Solution.java 파일 작성 후
javac Solution.java && java Solution
```

또는 JBang을 쓰면 더 간편하다.
```
jbang init --template=cli Solution.java
jbang Solution.java
```

라이브 코딩 대비에는 **타이머와 화이트보드**를 같이 두고 연습한다. 20분 안에 merge intervals를 edge case까지 포함해 한 번에 통과시키는 것을 목표로 삼는다. IDE 자동완성을 끄고 `System.out` 정도만 자동완성을 남겨두는 것이 실전과 가깝다.

테스트 케이스 세트 (문제 풀 때 공통으로 적용):
- 빈 입력
- 한 개 구간
- 전부 겹치는 구간
- 전부 분리된 구간
- 경계 인접 (`[1,2],[2,3]`)
- 완전 포함 (`[1,10],[3,5]`)
- 역순 입력 (정렬 안 된 상태)
- 중복 구간

## 연습 문제 1 (쉬움) — Merge Intervals

**문제**
정수 배열로 표현된 구간 목록 `int[][] intervals`가 주어진다. 각 구간은 `[start, end]` (닫힌 구간)이다. 겹치는 모든 구간을 병합해 서로 겹치지 않는 구간 목록을 반환하라. `[1,2]`와 `[2,3]`은 겹친 것으로 본다.

입력 예: `[[1,3],[2,6],[8,10],[15,18]]`
출력 예: `[[1,6],[8,10],[15,18]]`

제약: 1 ≤ intervals.length ≤ 10^4, 0 ≤ start ≤ end ≤ 10^4.

먼저 10분간 스스로 풀어본 뒤 아래를 연다.

<details>
<summary>풀이 아이디어와 전체 코드 보기</summary>

**접근**
1. start 오름차순으로 정렬.
2. 결과 리스트의 마지막 구간 `last`와 현재 구간 `cur`을 비교.
3. `last[1] >= cur[0]`이면 겹치거나 인접 → `last[1] = max(last[1], cur[1])`로 확장.
4. 아니면 새 구간 push.

시간 O(n log n), 공간 O(n). 닫힌 구간이므로 병합 조건은 `>=`를 사용한다.

**Java 전체 코드**
```java
import java.util.*;

public class MergeIntervals {
    public static int[][] merge(int[][] intervals) {
        if (intervals == null || intervals.length == 0) {
            return new int[0][0];
        }
        Arrays.sort(intervals, Comparator.comparingInt(a -> a[0]));

        List<int[]> merged = new ArrayList<>();
        merged.add(intervals[0].clone());

        for (int i = 1; i < intervals.length; i++) {
            int[] last = merged.get(merged.size() - 1);
            int[] cur = intervals[i];
            if (last[1] >= cur[0]) {
                last[1] = Math.max(last[1], cur[1]);
            } else {
                merged.add(cur.clone());
            }
        }
        return merged.toArray(new int[0][]);
    }

    public static void main(String[] args) {
        int[][] in = {{1,3},{2,6},{8,10},{15,18}};
        int[][] out = merge(in);
        for (int[] r : out) {
            System.out.println(Arrays.toString(r));
        }
        // [1, 6]
        // [8, 10]
        // [15, 18]

        System.out.println(Arrays.deepToString(merge(new int[][]{{1,4},{4,5}})));
        // [[1, 5]]

        System.out.println(Arrays.deepToString(merge(new int[][]{})));
        // []

        System.out.println(Arrays.deepToString(merge(new int[][]{{1,10},{2,3},{4,5}})));
        // [[1, 10]]
    }
}
```

**설명할 포인트**
- `Comparator.comparingInt`를 쓴 이유: `a[0]-b[0]` 방식의 overflow를 피하기 위함.
- `intervals[0].clone()`을 한 이유: 입력 배열을 직접 수정하지 않기 위해 방어적 복사.
- `>=`를 쓴 이유: 닫힌 구간이고 `[1,2],[2,3]`을 인접으로 간주해 병합해야 하기 때문.
- 반열린 구간이라면 `>`로 바꾸는 한 줄 수정으로 대응 가능.

</details>

## 연습 문제 2 (중간) — Meeting Rooms II

**문제**
`int[][] intervals`로 회의 일정이 주어진다. 각 `[start, end]`는 한 회의의 시작/종료 시각이다(반열린 구간 `[start, end)`). 동시에 진행 가능한 회의를 모두 수용하려면 최소 몇 개의 회의실이 필요한가?

입력 예: `[[0,30],[5,10],[15,20]]`
출력 예: `2`

제약: 0 ≤ intervals.length ≤ 10^4, 0 ≤ start < end ≤ 10^6.

min-heap 풀이와 sweep line 풀이 둘 다 떠올려보자. 어느 쪽이 면접에서 설명하기 쉬울지도 같이 고민한다.

<details>
<summary>풀이 아이디어와 전체 코드 보기</summary>

**접근 A — min-heap (가장 흔한 답)**
1. start 기준 정렬.
2. 현재 열려 있는 회의들의 `end`를 min-heap에 보관.
3. 새 회의 시작 시각이 가장 빨리 끝나는 회의의 end 이상이면 그 방을 반납(poll).
4. 새 회의의 end를 push.
5. 최종 heap 크기가 필요한 방 수.

반열린 구간이므로 `end <= start` (9:00 종료, 9:00 시작은 재사용 가능)일 때 반납한다.

**접근 B — sweep line**
1. 각 구간을 `(start, +1)`, `(end, -1)` 이벤트로 변환.
2. 시각 오름차순 정렬. 동률이면 `-1`(종료)을 먼저 처리 — 반열린 구간 가정.
3. 누적합을 유지하며 최댓값을 기록.

**Java 전체 코드 (두 풀이 모두 포함)**
```java
import java.util.*;

public class MeetingRoomsII {

    // 풀이 A: min-heap
    public static int minRoomsHeap(int[][] intervals) {
        if (intervals == null || intervals.length == 0) return 0;
        Arrays.sort(intervals, Comparator.comparingInt(a -> a[0]));

        PriorityQueue<Integer> endHeap = new PriorityQueue<>();
        for (int[] cur : intervals) {
            if (!endHeap.isEmpty() && endHeap.peek() <= cur[0]) {
                endHeap.poll();
            }
            endHeap.offer(cur[1]);
        }
        return endHeap.size();
    }

    // 풀이 B: sweep line
    public static int minRoomsSweep(int[][] intervals) {
        if (intervals == null || intervals.length == 0) return 0;
        int n = intervals.length;
        int[][] events = new int[n * 2][2];
        for (int i = 0; i < n; i++) {
            events[2 * i]     = new int[]{intervals[i][0], +1};
            events[2 * i + 1] = new int[]{intervals[i][1], -1};
        }
        // 시각 오름차순, 같은 시각이면 -1 먼저 (반열린 구간)
        Arrays.sort(events, (a, b) -> {
            if (a[0] != b[0]) return Integer.compare(a[0], b[0]);
            return Integer.compare(a[1], b[1]);
        });

        int cur = 0, max = 0;
        for (int[] e : events) {
            cur += e[1];
            max = Math.max(max, cur);
        }
        return max;
    }

    public static void main(String[] args) {
        int[][] t1 = {{0,30},{5,10},{15,20}};
        System.out.println(minRoomsHeap(t1));  // 2
        System.out.println(minRoomsSweep(t1)); // 2

        int[][] t2 = {{7,10},{2,4}};
        System.out.println(minRoomsHeap(t2));  // 1
        System.out.println(minRoomsSweep(t2)); // 1

        int[][] t3 = {{9,10},{10,11},{11,12}};
        System.out.println(minRoomsHeap(t3));  // 1 (반열린 → 연쇄 재사용)
        System.out.println(minRoomsSweep(t3)); // 1

        int[][] t4 = {};
        System.out.println(minRoomsHeap(t4));  // 0
        System.out.println(minRoomsSweep(t4)); // 0
    }
}
```

**설명할 포인트**
- heap 풀이는 "현재 활성 회의의 종료 시각들 중 가장 빠른 것만 관심 있다"는 통찰이 핵심.
- `endHeap.peek() <= cur[0]`에서 `<=`인 이유는 반열린 구간이기 때문. 닫힌 구간으로 바뀌면 `<`.
- sweep line에서 `-1` 먼저 처리하는 타이브레이킹을 면접관에게 명시적으로 언급한다. 닫힌 구간 가정이라면 `+1` 먼저로 뒤집어야 한다고 덧붙이면 가산점.
- 두 풀이 모두 O(n log n). heap은 공간 O(n), sweep는 이벤트 배열 O(n).
- 확장: "회의실마다 이름/장비 제약이 있다면?" → 자원별로 heap을 분리하거나, 이분 매칭으로 격상.

</details>

## 인터뷰 답변 프레이밍

면접관이 "실무에서 intervals를 다룬 경험이 있나요?"라고 물을 때 쓸 답변 템플릿:

> "광고/쿠폰/캘린더처럼 기간이 있는 리소스를 다룰 때 자주 썼습니다. 특히 배포 슬롯 예약 API를 만들 때, 기존 예약 구간과 신규 요청이 겹치는지 판정해야 했는데 TreeMap의 floor/ceiling으로 인접 구간만 조회해 O(log n)에 충돌 판정을 했습니다. 대량 병합이 필요한 배치는 정렬 후 선형 병합 O(n log n)으로 처리했고, 동시 활성 수를 구할 땐 sweep line으로 바꾸는 게 더 간결했습니다. 경계 규칙은 팀 내 컨벤션으로 반열린 구간 `[start, end)`을 명시적으로 문서화했는데, 이걸 초기에 합의하지 않으면 `10:00 종료/10:00 시작` 같은 edge case에서 버그가 반복됩니다."

시니어 티어에서 중요한 건 **알고리즘 자체보다 데이터 모델링 선택과 운영 경험**이다. 구간 컨벤션, 타임존, DST, 대규모 입력에서의 스트리밍 처리까지 언급하면 깊이가 드러난다.

## 체크리스트

라이브 코딩 직전에 5분간 훑을 수 있는 압축 체크리스트.

- [ ] 닫힌 구간인지 반열린 구간인지 면접관에게 확인했다
- [ ] start로 정렬하는 이유를 1문장으로 말할 수 있다
- [ ] 병합 조건 부등호(`>=` vs `>`)를 구간 타입에 맞춰 쓴다
- [ ] `Integer.compare` 또는 `Comparator.comparingInt`를 쓰고 뺄셈 Comparator는 피한다
- [ ] 빈 입력, 단일 구간, 완전 포함, 경계 인접 네 가지 edge case를 테스트한다
- [ ] meeting rooms II에서 heap과 sweep line 두 가지 풀이를 모두 설명할 수 있다
- [ ] sweep line에서 동시각 `+1`/`-1` 타이브레이킹 규칙을 명시한다
- [ ] 시간 복잡도 O(n log n), 공간 O(n)을 자연스럽게 언급한다
- [ ] 스트리밍 입력이면 TreeMap floor/ceiling으로 넘어가는 대안을 안다
- [ ] 백엔드 실무 예시(캘린더, 쿠폰, 광고, 배포 슬롯)를 최소 하나 꺼낼 수 있다
- [ ] 입력 배열을 직접 수정하지 않고 방어적 복사를 한다
- [ ] 코드 작성 전 "접근 → 예시 trace → edge case → 구현 → 복잡도" 순서로 말한다
