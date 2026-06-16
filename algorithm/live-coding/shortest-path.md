# [초안] 라이브 코딩에서 풀어내는 최단 경로: BFS와 Dijkstra 완전 정리

## 왜 이 주제가 라이브 코딩에서 자주 나오는가

HackerRank·코딜리티·온사이트 화이트보드 라이브 코딩에서 그래프 탐색은 거의 빠지지 않는다. 그중에서도 "최단 경로"는 면접관 입장에서 채점하기 좋은 문제다. 입력 그래프의 형태(가중치 유무, 음수 간선 유무, 노드 수)만 살짝 비틀어도 후보자가 어떤 알고리즘을 선택하고, 왜 그 선택이 옳은지 설명할 수 있는지를 단 30분 안에 측정할 수 있다.

라이브 코딩에서 우리가 자주 실수하는 지점은 알고리즘 자체가 어려워서가 아니다. **언제 BFS면 충분하고, 언제 Dijkstra가 필요한지를 즉답하지 못해서** 시간을 잡아먹는다. 또는 PriorityQueue를 일단 꺼내놓고 visited 배열을 BFS처럼 다루다가 답이 틀어진다. 시니어 백엔드 면접관은 이 둘을 정확히 구분하는 후보자를 선호한다. 시스템 설계에서도 동일한 사고가 등장하기 때문이다 — "균등 비용이면 큐 하나로 충분하다, 비용이 다르면 우선순위 기반이어야 한다."

이 글은 라이브 코딩에서 바로 꺼내 쓸 수 있는 수준으로 BFS 최단 경로와 Dijkstra를 정리하고, 두 알고리즘이 갈라지는 지점, 흔한 버그, 면접에서의 설명 흐름, 그리고 직접 풀어볼 연습 문제 두 개(쉬움 1, 중간 1)까지 다룬다.

## 핵심 개념: BFS 최단 경로 vs Dijkstra

### BFS가 최단 경로를 내는 조건

BFS는 시작 노드에서 가까운 노드부터 한 겹씩 펼쳐나가는 탐색이다. 큐에 들어간 순서대로 꺼내 처리하기 때문에, **모든 간선의 비용이 동일할 때**(보통 1) 가장 먼저 도달한 깊이가 곧 최단 거리가 된다.

- 그리드에서 상하좌우 한 칸씩 움직이는 문제
- 미로에서 벽이 아닌 칸을 한 번씩 밟고 나아가는 문제
- 단어 변환에서 한 글자만 바꾸는 비용을 모두 1로 보는 문제
- 친구의 친구 같은 무가중 소셜 그래프

이 경우 비용은 "이동 횟수"이고, 모든 이동은 1로 동등하다. BFS만으로 충분하다. 시간 복잡도는 `O(V + E)`이고 자료구조는 `ArrayDeque`나 `LinkedList` 같은 일반 큐다.

### Dijkstra가 필요한 조건

간선 비용이 서로 다르면 BFS는 더 이상 최단을 보장하지 않는다. 비용 1짜리 두 번 밟는 경로가 비용 5짜리 한 번 밟는 경로보다 짧을 수 있는데, BFS는 깊이가 1인 경로를 먼저 확정해버린다. 이때 Dijkstra가 등장한다.

Dijkstra의 핵심은 **현재까지 알려진 거리 중 가장 작은 노드부터 확정한다**는 그리디 원칙이다. 이 그리디가 옳으려면 **음수 간선이 없어야** 한다. 음수가 있으면 한 번 확정한 노드가 나중에 더 짧은 경로로 갱신될 수 있고, Dijkstra는 그걸 잡지 못한다(그때는 Bellman-Ford나 SPFA로 간다).

자료구조는 우선순위 큐(`PriorityQueue`)다. 시간 복잡도는 일반적으로 `O((V + E) log V)`다.

### 한 문장 결정 트리

라이브 코딩에서 면접관에게 입으로 말할 수 있어야 하는 결정 흐름은 다음과 같다.

> "간선이 모두 같은 비용이면 BFS, 비용이 다르면 Dijkstra, 음수면 Bellman-Ford. 가중치가 0/1만 있으면 0-1 BFS도 있다."

이 한 줄을 시작 멘트로 깔고 나서 코드를 짜기 시작하면 면접관은 이미 절반은 안심한다.

### 0-1 BFS라는 중간 지대

조금 깊이 들어가면 0-1 BFS가 있다. 비용이 0 또는 1만 있는 경우, 우선순위 큐 대신 `Deque`를 쓰고 비용 0 간선은 앞에, 비용 1 간선은 뒤에 넣는다. `O(V + E)`로 Dijkstra 효과를 낸다. 라이브 코딩에서 자주 안 나오지만, "벽 부수기 0개/1개" 같은 변형 문제에서 이 패턴을 알면 우아하게 끝낼 수 있다.

## 우선순위 큐 갱신 패턴: lazy deletion이 표준이다

Dijkstra를 자바로 구현할 때 가장 자주 망가지는 부분은 우선순위 큐의 항목을 어떻게 "갱신"하느냐다. 자바 `PriorityQueue`는 임의 위치의 키를 효율적으로 갱신하는 API를 제공하지 않는다. `remove(o)`는 `O(n)`이라 사용하면 안 된다.

표준 패턴은 **lazy deletion**(또는 lazy 갱신)이다.

1. 노드 `u`까지의 거리 `dist[u]`를 더 짧게 갱신할 때마다 그냥 `(새 거리, u)` 튜플을 큐에 새로 push한다.
2. 큐에서 꺼낼 때, 꺼낸 거리 값이 현재 `dist[u]`보다 크면 **이건 옛날 정보**이므로 그냥 버린다(`continue`).
3. 작거나 같으면 진짜 처리한다.

이 패턴 덕분에 `PriorityQueue`만으로 Dijkstra가 깔끔하게 구현된다. 큐 안에 한 노드가 여러 번 들어가지만, 옛날 항목은 꺼내자마자 버려지므로 정확성에 영향이 없다. 이게 자바 라이브 코딩의 정답 패턴이다.

```java
PriorityQueue<long[]> pq = new PriorityQueue<>(Comparator.comparingLong(a -> a[0]));
long[] dist = new long[n];
Arrays.fill(dist, Long.MAX_VALUE);
dist[start] = 0L;
pq.offer(new long[]{0L, start});

while (!pq.isEmpty()) {
    long[] cur = pq.poll();
    long d = cur[0];
    int u = (int) cur[1];
    if (d > dist[u]) continue;          // 옛날 정보 → lazy 버림
    for (int[] e : graph.get(u)) {
        int v = e[0];
        long w = e[1];
        long nd = d + w;
        if (nd < dist[v]) {
            dist[v] = nd;
            pq.offer(new long[]{nd, v});
        }
    }
}
```

기억할 포인트는 두 가지다.

- **`if (d > dist[u]) continue;`**: 이 한 줄이 Dijkstra의 정확성과 성능을 동시에 지킨다. 라이브 코딩에서 빠뜨리면 시간 초과로 직결된다.
- **거리 자료형**: 가중치 합이 `int` 범위를 넘을 수 있으면 `long`을 쓴다. `Integer.MAX_VALUE` 더하기로 오버플로우 나는 사고는 라이브 코딩 단골이다. 안전하게 `Long.MAX_VALUE`로 시작하자.

## visited와 distance 배열의 역할

BFS 최단 경로와 Dijkstra의 결정적 차이가 여기서 나온다.

### BFS에서

- `visited[v] = true`는 "이 노드는 이미 처리됐다"는 표식이고, **처음 도달한 깊이가 곧 최단 거리**다.
- 따라서 큐에 넣는 순간 `visited`를 켠다. 같은 노드를 두 번 큐에 넣지 않는다.
- 별도의 `dist[]` 배열을 둘 수도 있고, BFS의 레벨 단위로 카운트해도 된다.

```java
int[] dist = new int[n];
Arrays.fill(dist, -1);
Deque<Integer> q = new ArrayDeque<>();
dist[start] = 0;
q.offer(start);
while (!q.isEmpty()) {
    int u = q.poll();
    for (int v : graph.get(u)) {
        if (dist[v] != -1) continue;     // 이미 방문/큐 진입
        dist[v] = dist[u] + 1;
        q.offer(v);
    }
}
```

여기서 `dist[v] != -1`이 곧 BFS의 visited 역할이다. 값이 들어간 순간 더 짧아질 일이 없다.

### Dijkstra에서

- `dist[]`는 **지금까지 알려진 최단 거리**다. 갱신될 수 있다.
- visited는 **꺼내서 확정한 순간**에만 의미가 있다. 큐에 넣을 때가 아니라.
- lazy deletion 패턴을 쓴다면 `visited` 배열 자체를 안 두기도 한다. `if (d > dist[u]) continue;`가 그 역할을 대신한다.

라이브 코딩에서 절대 하지 말아야 할 실수는 **Dijkstra에서 BFS처럼 큐에 넣을 때 visited를 켜는 것**이다. 그러면 처음 큐에 들어간 거리(꼭 최단이 아닐 수 있는)로 노드가 잠겨버려서 답이 틀린다. 이건 "Dijkstra처럼 보이는데 답이 틀리는" 가장 흔한 함정이다.

## 가중치 조건에 따른 알고리즘 선택

라이브 코딩 화이트보드에서 정리해서 한 번에 결정하기 위한 표.

| 조건 | 선택 | 시간 복잡도 |
| --- | --- | --- |
| 모든 간선 비용 동일 | BFS | `O(V + E)` |
| 비용 0 또는 1만 존재 | 0-1 BFS (Deque) | `O(V + E)` |
| 비용 양수, 음수 없음 | Dijkstra (PQ + lazy) | `O((V+E) log V)` |
| 음수 간선 존재, 음수 사이클 없음 | Bellman-Ford | `O(V·E)` |
| 모든 쌍 최단 경로, V 작음 | Floyd-Warshall | `O(V^3)` |
| DAG | 위상정렬 + DP | `O(V + E)` |

면접관이 그래프 모양만 던지면 후보자가 이 표를 머릿속에서 펼쳐서 고른다는 인상을 줘야 한다. 굳이 외운 것처럼 말하지 말고, "음수가 없네요. 그럼 Dijkstra로 갑니다" 정도로 자연스럽게.

## 흔한 구현 버그 모음

라이브 코딩에서 시간을 까먹는 지점들.

1. **PriorityQueue의 비교 함수 방향 실수.** `a[0] - b[0]`을 쓸 때 `int` 오버플로우, 또는 long 거리에서 `(int)(a[0] - b[0])` 같은 캐스팅 사고. `Comparator.comparingLong(a -> a[0])`이 안전하다.
2. **`dist`를 `Integer.MAX_VALUE`로 초기화하고 더하기.** `MAX_VALUE + w` → 음수로 흘러가서 갱신이 잘못 트리거된다. `Long.MAX_VALUE`를 쓰거나 더하기 전에 `dist[u] == Long.MAX_VALUE`인지 가드.
3. **양방향 그래프인데 단방향만 추가.** 무방향 입력은 양쪽 다 push 해야 한다.
4. **visited를 BFS 스타일로 Dijkstra에 적용.** 위에서 본 함정.
5. **lazy deletion 가드 누락.** `if (d > dist[u]) continue;`를 빼면, 같은 노드를 중복 처리하면서 큐가 폭발한다. TLE.
6. **자기 자신 시작점 처리.** `dist[start] = 0`을 빼먹고 무한대로 두면 모든 답이 무한대가 된다.
7. **0이 답인 케이스.** 시작이 곧 도착인 경우 0을 반환해야 하는데, 큐에서 도착을 만나기 전에 종료하는 로직이 있으면 답이 틀린다.
8. **방문하지 못한 노드 출력.** 도달 불가 노드는 보통 `-1`로 답해야 한다. `Long.MAX_VALUE`를 그대로 출력하지 않도록 마지막에 변환.
9. **그래프 입력에서 인덱스 0/1 오프셋 혼동.** 문제에서 1-based로 주는데 배열은 0-based로 잡는 흔한 실수.
10. **이웃 리스트 자료구조 선택.** `ArrayList<int[]>`이 정석. `Map<Integer, List<int[]>>`은 불필요한 박싱이 많다.

## 면접에서 접근 방식을 설명하는 방법

라이브 코딩의 절반은 코딩이고, 나머지 절반은 **말하는 흐름**이다. 침묵하면 면접관은 "이 사람이 막혔는지 생각 중인지" 모른다. 다음 5단계를 입으로 말하면서 풀자.

1. **문제 재정의.** "노드 N개, 간선 M개, 시작점 s에서 도착점 t까지의 최소 비용을 구하는 문제로 이해했습니다."
2. **그래프 성질 확인.** "간선 가중치가 양수만 있고 음수는 없네요. 무방향 그래프입니다."
3. **알고리즘 선택과 근거.** "비용이 동일하지 않으니 BFS는 안 됩니다. 음수 간선이 없으니 Dijkstra가 적합합니다. 시간 복잡도는 `(V+E) log V`로, N, M 제약을 보면 충분합니다."
4. **자료구조 선언.** "인접 리스트는 `List<int[]>[]`로, 거리 배열은 `long[]`, 우선순위 큐는 거리 기준 min-heap을 씁니다. 갱신은 lazy deletion 패턴으로 처리합니다."
5. **엣지 케이스 미리 언급.** "시작과 도착이 같은 경우 0, 도달 불가는 -1, 정수 오버플로우 방지 위해 `long`을 사용합니다."

이 5단계를 다 말하는 데 90초 정도 든다. 그러고 코드를 친다. 코딩 끝나면 자기 입으로 손가락 짚으면서 dry run을 작은 입력으로 보여준다. 시니어 라이브 코딩의 평가 포인트는 "정답을 맞췄나"보다 "사고 과정을 통제 가능하게 보여줬나"에 가깝다.

면접관이 "왜 BFS는 안 되나요?" 같은 follow-up을 던지면 작은 반례를 즉석에서 그린다. 노드 3개, A→B 비용 5, A→C 비용 1, C→B 비용 1짜리 그래프. BFS는 A→B를 1홉으로 확정해서 5라고 답하지만, 실제 최단은 A→C→B 2홉으로 2다. 이런 반례를 5초 안에 그릴 수 있어야 한다.

## 로컬 연습 환경

라이브 코딩 대비는 IDE를 너무 잘 갖추면 오히려 손해다. HackerRank·CoderPad는 자동완성도 약하고 디버거도 없다. 다음 환경을 권장한다.

- JDK 17 이상 (`java --version`으로 확인)
- 단일 파일 컴파일·실행: `javac Main.java && java Main`
- 입력은 `Scanner` 또는 `BufferedReader`. 라이브 코딩에서는 `Scanner`가 빠르다.
- IntelliJ를 쓰되 자동 import만 사용하고, 그 외 자동 보정은 일부러 끄고 연습한다.
- 표준 입력으로 그래프를 받는 템플릿을 손에 익혀둔다.

```java
import java.util.*;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        int m = sc.nextInt();
        List<int[]>[] g = new List[n + 1];
        for (int i = 0; i <= n; i++) g[i] = new ArrayList<>();
        for (int i = 0; i < m; i++) {
            int u = sc.nextInt();
            int v = sc.nextInt();
            int w = sc.nextInt();
            g[u].add(new int[]{v, w});
            g[v].add(new int[]{u, w}); // 무방향이라면
        }
        int s = sc.nextInt();
        int t = sc.nextInt();
        // ... solve ...
    }
}
```

이 템플릿을 30초 안에 손으로 칠 수 있어야 한다. 라이브 코딩에서 입력 파싱에 5분을 쓰는 후보자는 이미 진 것이다.

## 연습 문제 두 개

### 문제 1 (쉬움) — 균등 비용 격자 최단 경로

`R x C` 격자가 주어진다. `'.'`은 빈 칸, `'#'`은 벽. 시작점 `(sr, sc)`에서 도착점 `(er, ec)`까지 상하좌우 한 칸씩 이동할 때 최소 이동 횟수를 구하라. 도달 불가능하면 `-1`을 반환.

입력 예시:
```
5 5
.....
.###.
.#...
.#.#.
...#.
0 0
4 4
```

출력: `8`

힌트: 모든 이동의 비용이 1이다. BFS로 충분하다. `dist[r][c] = -1`로 초기화하고, 큐에 넣을 때 `dist`를 채운다. 도착에 도달한 시점에 그 값이 답이다.

<details>
<summary>풀이 보기 (Java 전체 코드)</summary>

접근:
- 큐 기반 표준 BFS.
- `dist[][]`를 `-1`로 초기화하여 방문 여부 겸 거리 표식으로 사용.
- 방향 배열 `dr/dc`로 4방향 이웃 순회.
- 도달 시점에서 즉시 반환하면 더 빠르지만, 일반화를 위해 끝까지 채워둔다.

```java
import java.util.*;

public class Grid4DirShortest {
    public static int solve(char[][] grid, int sr, int sc, int er, int ec) {
        int R = grid.length;
        int C = grid[0].length;
        if (grid[sr][sc] == '#' || grid[er][ec] == '#') return -1;
        int[][] dist = new int[R][C];
        for (int[] row : dist) Arrays.fill(row, -1);
        int[] dr = {-1, 1, 0, 0};
        int[] dc = {0, 0, -1, 1};
        Deque<int[]> q = new ArrayDeque<>();
        dist[sr][sc] = 0;
        q.offer(new int[]{sr, sc});
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            int r = cur[0], c = cur[1];
            if (r == er && c == ec) return dist[r][c];
            for (int k = 0; k < 4; k++) {
                int nr = r + dr[k];
                int nc = c + dc[k];
                if (nr < 0 || nr >= R || nc < 0 || nc >= C) continue;
                if (grid[nr][nc] == '#') continue;
                if (dist[nr][nc] != -1) continue;
                dist[nr][nc] = dist[r][c] + 1;
                q.offer(new int[]{nr, nc});
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int R = sc.nextInt();
        int C = sc.nextInt();
        char[][] g = new char[R][];
        for (int i = 0; i < R; i++) g[i] = sc.next().toCharArray();
        int sr = sc.nextInt(), scc = sc.nextInt();
        int er = sc.nextInt(), ec = sc.nextInt();
        System.out.println(solve(g, sr, scc, er, ec));
    }
}
```

체크리스트:
- 시작/도착이 벽인 케이스를 가드했다.
- `dist != -1`을 visited 대용으로 썼다.
- 4방향 모두 검사하기 전에 경계와 벽을 우선 거른다.
- 도달 못 했을 때 `-1`을 반환한다.

</details>

### 문제 2 (중간) — 가중치 그래프 최단 경로 with 환승 비용

도시가 `N`개, 도로가 `M`개 있다. 각 도로는 양방향이고 `(u, v, w)` 형태로 비용 `w`를 가진다. 또한 도로마다 "유형"이 있어서, 서로 다른 유형의 도로로 환승할 때마다 추가 비용 `K`가 든다. 같은 유형의 도로끼리는 환승 비용이 없다. 시작 도시 `S`에서 도착 도시 `T`까지의 최소 비용을 구하라. 도달 불가능하면 `-1`.

입력 형식: 첫 줄 `N M K`, 그 다음 `M`줄 `u v w t`(`t`는 도로 유형, 0 이상의 정수), 마지막 줄 `S T`.

이 문제는 Dijkstra이지만 상태가 `(노드, 마지막 도로 유형)`이다. 같은 노드라도 어떤 유형으로 도착했는지에 따라 다음 환승 비용이 달라지기 때문이다. 시작점은 "유형 없음" 상태로 시작하고, 첫 간선 사용 시 환승 비용은 부과하지 않는다.

힌트:
- 상태를 `(node, lastType)`으로 확장한 그래프 위에서 Dijkstra.
- `dist`는 `Map<Long, Long>` 또는 `HashMap<Long, Long>`(키 인코딩) 또는 `long[][]` (유형 수가 작을 때).
- 시작 상태는 `(S, -1)`로 두고, 첫 간선에서는 환승 비용을 부과하지 않도록 분기.

<details>
<summary>풀이 보기 (Java 전체 코드)</summary>

접근:
- 노드 상태를 `(node, lastType)`로 확장.
- 우선순위 큐에는 `(누적비용, 노드, 마지막유형)` 튜플을 넣는다.
- `lastType == -1`이면 환승 비용 0, 그 외에 다음 간선 유형이 다르면 `+K`.
- lazy deletion 가드를 적용한다. `dist`는 `HashMap<Long, Long>`로 (`node * (T+2) + lastType+1`) 키를 만든다. 유형 가짓수가 작다고 가정되면 2D 배열이 더 빠르다.
- 거리 합 오버플로우 가능성 → `long` 사용.

```java
import java.util.*;

public class TransferCostDijkstra {
    public static long solve(int n, int k, List<int[]>[] g, int s, int t) {
        // g[u]는 {v, w, type} 리스트
        PriorityQueue<long[]> pq = new PriorityQueue<>(Comparator.comparingLong(a -> a[0]));
        // dist key: node * (numTypes+2) + (lastType+1)
        // 단순화를 위해 HashMap 사용
        HashMap<Long, Long> dist = new HashMap<>();
        long startKey = encode(s, -1, n);
        dist.put(startKey, 0L);
        pq.offer(new long[]{0L, s, -1});

        while (!pq.isEmpty()) {
            long[] cur = pq.poll();
            long d = cur[0];
            int u = (int) cur[1];
            int lastType = (int) cur[2];
            long key = encode(u, lastType, n);
            Long known = dist.get(key);
            if (known == null || d > known) continue;
            if (u == t) return d;
            for (int[] e : g[u]) {
                int v = e[0];
                long w = e[1];
                int type = e[2];
                long add = (lastType == -1 || lastType == type) ? 0L : (long) k;
                long nd = d + w + add;
                long nKey = encode(v, type, n);
                Long prev = dist.get(nKey);
                if (prev == null || nd < prev) {
                    dist.put(nKey, nd);
                    pq.offer(new long[]{nd, v, type});
                }
            }
        }
        return -1L;
    }

    private static long encode(int node, int lastType, int n) {
        // lastType은 -1 이상의 정수. 적당한 base로 인코딩.
        long base = 1_000_003L;
        return (long) node * base + (lastType + 1);
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        int m = sc.nextInt();
        int k = sc.nextInt();
        List<int[]>[] g = new List[n + 1];
        for (int i = 0; i <= n; i++) g[i] = new ArrayList<>();
        for (int i = 0; i < m; i++) {
            int u = sc.nextInt();
            int v = sc.nextInt();
            int w = sc.nextInt();
            int t = sc.nextInt();
            g[u].add(new int[]{v, w, t});
            g[v].add(new int[]{u, w, t});
        }
        int s = sc.nextInt();
        int dst = sc.nextInt();
        System.out.println(solve(n, k, g, s, dst));
    }
}
```

체크리스트:
- 상태 확장이 필요한 이유를 면접관에게 설명할 수 있다 ("같은 노드라도 어떤 유형으로 들어왔느냐가 다음 비용을 바꾸기 때문").
- lazy deletion 가드(`d > known`) 사용.
- 유형 수가 매우 크면 인코딩 충돌이 없도록 base를 충분히 크게 잡는다.
- `long`으로 누적 비용을 다룬다.
- 시작 상태에서 환승 비용을 부과하지 않는다.

이 문제를 라이브 코딩에서 받으면 처음부터 코드를 치지 말고, "상태가 노드 하나로는 부족하니 `(노드, 직전 유형)`으로 확장하겠습니다"라고 명시적으로 말하고 시작한다. 이게 시니어 시그널이다.

</details>

## 시니어 백엔드 관점의 면접 답변 프레임

라이브 코딩에서 끝났다고 끝이 아니다. "이걸 실제 시스템에서 어떻게 응용해봤느냐"는 follow-up이 자주 따라온다. 시니어 백엔드 관점에서는 다음 같이 연결한다.

- **메시지 라우팅 / 워크플로 엔진**: 단계 간 전이 비용이 다른 워크플로의 최소 비용 경로 산출에 Dijkstra 응용.
- **추천 그래프 / 친구 추천**: 무가중 BFS로 N차 이웃 거리 산출. 캐시·페이징 전략과 결합.
- **CDN / 라우팅 비용 최적화**: 노드 간 RTT를 가중치로 보고 Dijkstra.
- **재시도/회복 경로**: 실패 비용이 다른 fallback 체인을 가중 그래프로 모델링.
- **멱등성과 버전 관리**: 그래프 갱신이 잦은 환경에서, 매번 풀지 않고 영향받은 노드 부분만 재계산하는 incremental 접근.

이런 응용을 한두 개 머릿속에 두고 있으면 "Dijkstra를 외운 후보자"가 아니라 "현업 시스템에 적용해본 후보자"로 평가가 바뀐다.

## 셀프 체크리스트

라이브 코딩 시작 직전에 머릿속으로 빠르게 점검할 항목.

- [ ] 그래프 가중치를 보고 BFS / Dijkstra / Bellman-Ford / 0-1 BFS / Floyd 중에서 즉답으로 고를 수 있다
- [ ] 무방향 입력일 때 양방향 추가를 잊지 않는다
- [ ] 거리 자료형을 `long`으로 잡고, 초기값은 `Long.MAX_VALUE`로 둔다
- [ ] PriorityQueue 비교자는 `Comparator.comparingLong`으로 명시한다
- [ ] Dijkstra에 lazy deletion 가드(`if (d > dist[u]) continue;`)를 둔다
- [ ] BFS는 큐에 넣는 순간 visited를 켠다, Dijkstra는 꺼낼 때 확정한다는 차이를 설명할 수 있다
- [ ] 도달 불가 시 `-1` 반환을 처리한다
- [ ] 시작과 끝이 같은 경우 0을 반환한다
- [ ] 입력 파싱 템플릿을 30초 안에 친다
- [ ] 풀고 나서 작은 입력으로 dry run을 입으로 짚어준다
- [ ] 알고리즘 선택 근거와 시간 복잡도를 면접관에게 한 문장으로 설명한다
- [ ] 시스템 응용 사례 한두 개를 머릿속에 갖고 있다

이 체크리스트를 통과하면, 라이브 코딩에서 최단 경로가 출제되어도 침착하게 30분을 운영할 수 있다.
