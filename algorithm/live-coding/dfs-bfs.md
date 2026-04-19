# [초안] Java 라이브 코딩을 위한 DFS / BFS 실전 가이드

## 왜 이 주제가 중요한가

HackerRank 스타일의 라이브 코딩 면접에서 가장 자주 나오는 카테고리는 배열 다음으로 그래프/트리 탐색이다. 경력 백엔드 개발자를 뽑는 자리에서도 "복잡한 알고리즘"은 잘 나오지 않는다. 대신 **`DFS 혹은 BFS 중 어느 쪽을 선택하는가, 왜 그렇게 선택했는가, visited 처리를 어느 시점에 하는가**와 같은 **판단의 질**을 본다. 코드를 외워 쓴 티가 나면 오히려 감점이다.

라이브 코딩에서는 30~45분 안에 다음을 모두 해내야 한다.

- 문제를 듣고 그래프/트리 구조를 모델링
- DFS와 BFS 중 하나를 골라 그 이유를 설명
- 재귀 스택과 큐 기반 반복 중 어떤 구현을 쓸지 결정
- visited / 방문 처리를 올바른 시점에 삽입
- 엣지 케이스(빈 그래프, 사이클, 분리된 컴포넌트)를 말로 먼저 짚어 주기
- 시간·공간 복잡도를 간단히 설명

백엔드 실무와도 직접 연결된다. 권한 트리 순회, 조직도 DFS, 카테고리 BFS 전개, 외부 API DAG 의존 스케줄링, 그래프 기반 추천 확장, 의존성 순회 등은 모두 DFS/BFS를 요구한다. 면접관 입장에서 "이 사람이 실무에서 재귀 깊이 한도를 의식하는가", "쓸데없이 BFS로 모든 간선을 탐색하지 않는가"를 보는 것도 그래서다.

## 핵심 개념 정리

### 그래프와 트리 탐색의 선택 기준

| 관점 | DFS | BFS |
|------|-----|-----|
| 자료 구조 | 스택(재귀 콜스택 또는 `Deque`) | 큐(`ArrayDeque`) |
| 용도 | 경로 존재 여부, 연결 컴포넌트, 사이클 탐지, 위상 정렬, 백트래킹 | 최단 거리(가중치 없음), 레벨 순회, 상태 공간에서의 최소 단계 |
| 메모리 사용 | 경로 깊이에 비례 | 레벨 크기에 비례(보통 더 큼) |
| 직관 | "일단 끝까지 가 본다" | "가까운 것부터 본다" |

기준은 단순하다. **"가장 짧은 무언가"가 질문에 들어가 있으면 BFS를 먼저 의심한다.** 최단 이동 수, 최소 변환 단계, 감염 시간, 거리 등이 모두 여기에 해당한다. 반대로 "모든 경우를 탐색", "조합을 만든다", "경로를 구성한다"가 보이면 DFS(특히 백트래킹)다.

라이브 코딩에서는 기준을 **한 줄로 먼저 말한다**: "최단 이동 수를 묻기 때문에 가중치 없는 그래프에서는 BFS로 풀겠습니다. 레벨이 곧 거리이기 때문입니다." 이런 한 문장이 면접관의 평가를 크게 좌우한다.

### 재귀 DFS와 반복 DFS

재귀 DFS는 작성 속도가 빠르지만 콜스택 깊이가 문제다. Java의 기본 스레드 스택은 512KB ~ 1MB 수준이고, 한 프레임이 몇십~몇백 바이트이므로 깊이 1만 ~ 2만 정도에서 `StackOverflowError`가 난다. 그래프가 긴 체인을 만들 수 있는 문제(가령 n=10^5의 직선 연결)에서는 반복 DFS를 선택한다.

- **재귀 DFS**: 트리, 깊이 제한이 명확한 경우, 백트래킹.
- **반복 DFS**: 일반 그래프, 스택 오버플로 위험이 있는 경우, 경로 재구성이 단순한 경우.

반복 DFS의 기본 꼴은 BFS와 거의 같고 **큐 대신 `ArrayDeque`를 스택처럼** 쓴다. 다만 방문 순서가 재귀 DFS와 완전히 같지는 않다(인접 리스트를 역순으로 push하면 비슷해진다). 이 점은 면접에서 질문받을 수 있다.

### 큐 기반 BFS와 최단 거리 직관

BFS의 핵심 불변식은 "큐에서 꺼낼 때의 거리가 단조 증가한다"이다. 가중치가 모두 1이기 때문에, 처음 방문하는 순간이 곧 **시작점으로부터의 최단 거리**가 된다.

자주 쓰는 두 가지 패턴이 있다.

1. 노드마다 `dist[v]`를 기록한다. 방문하지 않은 이웃에 대해 `dist[nx] = dist[cur] + 1`로 큐에 넣는다.
2. 레벨 단위로 while 안에 `for (int s = queue.size(); s > 0; s--)` 루프를 두고 한 바퀴마다 `level++`.

둘 다 동일한 결과를 주지만, **방문 수를 기록해야 한다거나 레벨별로 상태를 다르게 처리해야 하는 문제**(예: "각 단계에서 썩는 오렌지 수")라면 레벨 루프 방식이 유리하다.

### visited 처리 타이밍 — 면접 단골 함정

가장 흔히 실수가 나는 부분이다. 원칙은 이렇다.

- **BFS**: **큐에 넣는 순간** visited 처리한다. 꺼낼 때 visited 처리를 하면, 같은 노드가 큐에 여러 번 들어가서 메모리·시간이 터진다.
- **재귀 DFS (일반 그래프)**: **함수 진입 시** visited 처리한다.
- **백트래킹 DFS**: 진입 시 visited에 추가하고, **함수 리턴 직전에 제거**한다(경로 기반 순열·조합·n-Queens 등).

실제로 백트래킹이 아닌 단순 연결 탐색에서 리턴 직전에 visited를 제거해 무한 루프에 빠지는 경우가 많다. 두 목적이 다른 것을 의식해야 한다.

## 실무 백엔드에서의 사용

DFS/BFS는 경력 개발자의 일상과도 맞닿아 있다.

- **권한 트리 전개**: 부모 권한이 자식에 상속될 때, 특정 사용자의 유효 권한 집합을 DFS로 flatten.
- **조직도 순회**: 관리자 라인 타고 올라가며 결재권자 찾기 — 부모 포인터로 올라가는 DFS.
- **카테고리 BFS 전개**: 상품 카테고리의 직접·간접 하위 카테고리 전체를 레벨 순으로 수집.
- **의존성 그래프 순서**: 배치 작업/마이그레이션 DAG의 실행 순서를 DFS 기반 위상 정렬로 결정.
- **그래프 캐시 확장**: 특정 상품에서 2-hop 이내 연관 상품을 BFS로 수집해 추천 풀 구성.

실무에서는 재귀 깊이와 메모리 폭주가 훨씬 중요한 문제다. DB에서 가져온 수만 건의 트리를 그대로 재귀로 돌다가 스택 오버플로가 나는 일은 의외로 자주 있다. 면접에서 "왜 반복 DFS를 고려했습니까"라는 답으로 이 경험을 직접 연결하면 설득력이 커진다.

## Bad vs Improved 예제

### Bad — visited를 꺼낼 때 체크하는 BFS

```java
// 중복 enqueue로 시간·메모리가 폭발하는 전형적인 실수
Queue<Integer> q = new ArrayDeque<>();
boolean[] visited = new boolean[n];
q.offer(start);

while (!q.isEmpty()) {
    int cur = q.poll();
    if (visited[cur]) continue;   // ← 여기서 처리
    visited[cur] = true;

    for (int nx : graph[cur]) {
        q.offer(nx);              // visited 여부와 무관하게 push
    }
}
```

한 노드가 이웃 수만큼 큐에 중복으로 들어간다. 간선이 많으면 O(V+E)가 아닌 O(V·E)에 가깝게 된다.

### Improved — 큐에 넣는 순간 visited 처리

```java
Queue<Integer> q = new ArrayDeque<>();
boolean[] visited = new boolean[n];
q.offer(start);
visited[start] = true;

while (!q.isEmpty()) {
    int cur = q.poll();
    for (int nx : graph[cur]) {
        if (visited[nx]) continue;
        visited[nx] = true;   // ← enqueue와 동시에 체크
        q.offer(nx);
    }
}
```

### Bad — 깊은 체인에서 재귀 DFS 고집

```java
// n=100000 선형 체인에서 StackOverflowError 발생
void dfs(int u) {
    visited[u] = true;
    for (int v : graph[u]) if (!visited[v]) dfs(v);
}
```

### Improved — 반복 DFS 전환

```java
Deque<Integer> stack = new ArrayDeque<>();
stack.push(start);
visited[start] = true;
while (!stack.isEmpty()) {
    int cur = stack.pop();
    for (int nx : graph[cur]) {
        if (visited[nx]) continue;
        visited[nx] = true;
        stack.push(nx);
    }
}
```

## 구현 시 흔한 버그 목록

라이브 코딩에서는 코드를 쓰기 전 아래 체크를 말로 먼저 한다. 버그 거리를 좁히는 가장 빠른 방법이다.

- 인접 리스트를 `new ArrayList<>()`로 노드마다 초기화했는가(NPE 단골).
- 방향 그래프인데 양방향으로 간선을 넣었는가.
- `visited`를 enqueue/함수 진입 시점에 처리했는가.
- BFS에서 레벨 단위 처리가 필요한 문제에 무지성 단순 BFS를 쓰지 않았는가.
- 격자 문제에서 `dx/dy` 배열과 경계 체크(`0 <= nr < R && 0 <= nc < C`)가 맞는가.
- 백트래킹에서 상태 복원(visited 해제, 경로 pop)을 빠뜨리지 않았는가.
- `int` 오버플로가 날 조건(거리 합, 경우의 수)이 있는가.
- 연결되지 않은 그래프에서 모든 컴포넌트를 도는 외부 루프가 필요한가.

## 로컬 연습 환경

IDE 없이도 문제를 풀 수 있어야 한다. 다음 세팅이면 충분하다.

```bash
mkdir -p ~/algo/dfsbfs && cd ~/algo/dfsbfs
cat > Main.java <<'EOF'
import java.util.*;
public class Main {
    public static void main(String[] args) {
        // 여기서 임시 입력을 만들어 검증한다
    }
}
EOF
javac Main.java && java Main
```

테스트는 별도 프레임워크 없이 `assert`로 충분하다. 실행 시 `java -ea Main`으로 assertion을 켠다. 문제 풀이는 **입력 파서 → 그래프 빌드 → 탐색 → 결과 출력** 네 블록으로 나눠 쓰면 실수와 디버깅이 줄어든다.

## 라이브 면접에서 접근 방식을 설명하는 법

면접관은 코드보다 사고 과정을 본다. 다음 순서로 입을 먼저 연다.

1. **문제 재진술**: "입력은 n개의 노드와 m개의 간선, 시작 s, 목표 t입니다. 최소 이동 수를 구합니다."
2. **모델링 선언**: "방향 없는 그래프, 가중치 없음. 인접 리스트로 구성하겠습니다."
3. **알고리즘 선택 + 이유**: "가중치가 없으므로 BFS를 쓰면 큐에서 꺼낸 순간이 최단 거리입니다."
4. **복잡도**: "O(V+E) 시간, O(V) 공간."
5. **엣지 케이스**: "s == t, 도달 불가, 자기 루프, 중복 간선."
6. **구현**: 주석 없이도 읽히는 변수명과 일관된 반복 구조.
7. **손 디버깅**: 작성 후 작은 예제로 큐의 변화를 말로 추적해 준다.

이 7단계를 의식적으로 순서대로 수행하면, 중간에 코드가 막혀도 전체 인상은 나쁘게 남지 않는다.

## 인터뷰 답변 프레이밍

- *"DFS와 BFS 중 어떻게 고르나요?"*
  > 문제가 "최단 무엇"을 묻고 간선 가중치가 동일하면 BFS. 모든 경로·조합 탐색이나 연결 컴포넌트, 사이클 탐지라면 DFS. 실무에서는 깊이가 커질 수 있는 상황에서는 스택 오버플로 때문에 반복 DFS를 기본으로 씁니다.

- *"재귀 DFS의 한계는?"*
  > Java 스레드 기본 스택이 작아 수만 깊이에서 터집니다. 트리 체인, 그리드 스네이크 모양 입력이 대표 케이스고, 이런 문제는 반복 DFS 또는 BFS로 우회합니다.

- *"BFS에서 visited 처리를 큐에 넣을 때 해야 하는 이유는?"*
  > 같은 노드가 여러 이웃에서 동시에 발견되기 때문입니다. pop 시점에 처리하면 중복 enqueue로 시간·메모리가 이웃 수 배로 커집니다.

- *"백트래킹과 일반 DFS의 차이는?"*
  > 상태를 공유해 모든 경로를 재사용하면 일반 DFS. 특정 경로·선택의 조합을 enumerate해야 하면 백트래킹이고, 리턴 직전에 선택을 취소하는 점이 다릅니다.

## 연습 문제 (Java · 쉬움 1 / 중간 1)

### 문제 1 (쉬움) — 무가중치 그래프 최단 거리

- 정점 수 `n (1 ≤ n ≤ 10^5)`, 양방향 간선 목록 `edges`, 출발 `s`, 도착 `t`.
- `s`에서 `t`까지의 최소 간선 수를 반환한다. 도달 불가 시 `-1`.
- 제약: 자기 루프, 중복 간선, 분리된 컴포넌트 존재 가능.

면접에서 먼저 말해야 할 것: "가중치가 없으므로 BFS. enqueue 시점에 visited 처리. 도달 불가는 루프 종료 후 `dist[t]`가 갱신되지 않은 것으로 판정."

<details>
<summary>풀이 보기 (접근 설명 + Java 전체 코드)</summary>

**접근**: 인접 리스트를 만들고 `dist[]`를 `-1`로 초기화. 시작점만 `0`으로 둔다. BFS 큐에서 꺼낸 노드의 이웃 중 아직 `-1`인 것만 `dist[cur]+1`로 갱신하며 enqueue. 한 번이라도 `t`가 갱신되면 조기 종료할 수도 있지만, 평균 복잡도는 동일하므로 구현 단순성을 위해 끝까지 돌린다.

**복잡도**: 시간 O(V+E), 공간 O(V+E).

```java
import java.util.*;

public class ShortestPathBFS {
    public static int shortest(int n, int[][] edges, int s, int t) {
        List<List<Integer>> g = new ArrayList<>();
        for (int i = 0; i < n; i++) g.add(new ArrayList<>());
        for (int[] e : edges) {
            if (e[0] == e[1]) continue;     // 자기 루프 무시
            g.get(e[0]).add(e[1]);
            g.get(e[1]).add(e[0]);
        }

        int[] dist = new int[n];
        Arrays.fill(dist, -1);
        dist[s] = 0;

        Deque<Integer> q = new ArrayDeque<>();
        q.offer(s);

        while (!q.isEmpty()) {
            int cur = q.poll();
            if (cur == t) return dist[t];   // 조기 종료
            for (int nx : g.get(cur)) {
                if (dist[nx] != -1) continue;
                dist[nx] = dist[cur] + 1;
                q.offer(nx);
            }
        }
        return dist[t];
    }

    public static void main(String[] args) {
        int[][] edges = {{0,1},{1,2},{2,3},{1,3},{4,5}};
        System.out.println(shortest(6, edges, 0, 3)); // 2
        System.out.println(shortest(6, edges, 0, 5)); // -1
        System.out.println(shortest(6, edges, 2, 2)); // 0
    }
}
```

**이런 실수를 피한다**
- `dist[nx] != -1` 대신 별도 `visited[]`를 두면 멀쩡히 동작하지만 변수 두 개를 동기화해야 한다. 하나로 합친다.
- 자기 루프를 그대로 인접 리스트에 넣으면 동작엔 문제없지만 디버깅이 헷갈린다. 미리 버린다.

</details>

### 문제 2 (중간) — 2D 격자에서 동시 BFS (썩는 오렌지)

- 격자 `grid[R][C]`, 값은 `0`(빈 칸), `1`(신선한 오렌지), `2`(썩은 오렌지).
- 매 분마다 썩은 오렌지의 상하좌우 인접한 신선한 오렌지가 썩는다.
- 모든 신선한 오렌지가 썩는 최소 분을 반환하고, 영영 썩지 않는 오렌지가 있으면 `-1`.
- 제약: `1 ≤ R, C ≤ 300`. 한 칸에 여러 출처에서 동시에 썩음이 전파될 수 있음.

면접에서 먼저 말해야 할 것: "여러 시작점에서 동시에 퍼지는 BFS(멀티 소스 BFS). 초기 큐에 모든 썩은 칸을 한꺼번에 넣고 레벨 루프로 분 단위로 처리. 남은 신선 오렌지 수로 `-1` 판정."

<details>
<summary>풀이 보기 (접근 설명 + Java 전체 코드)</summary>

**접근**: 첫 스캔에서 (1) 모든 `2` 위치를 큐에 넣고, (2) `fresh` 카운트를 센다. 큐가 비어도 `fresh == 0`이면 시간은 `0`이다. 그 외에는 레벨 단위로 BFS를 돌리면서 매 레벨마다 `minutes++`, 이웃 중 `1`을 `2`로 바꾸고 `fresh--`. 마지막에 `fresh > 0`이면 `-1`. 이 문제의 핵심은 **여러 출발점을 동시에 큐에 넣는 것**과 **레벨 루프로 "분"을 세는 것**이다.

**복잡도**: 시간 O(R·C), 공간 O(R·C).

```java
import java.util.*;

public class RottingOranges {
    static final int[] DR = {-1, 1, 0, 0};
    static final int[] DC = {0, 0, -1, 1};

    public static int orangesRotting(int[][] grid) {
        int R = grid.length, C = grid[0].length;
        Deque<int[]> q = new ArrayDeque<>();
        int fresh = 0;
        for (int r = 0; r < R; r++) {
            for (int c = 0; c < C; c++) {
                if (grid[r][c] == 2) q.offer(new int[]{r, c});
                else if (grid[r][c] == 1) fresh++;
            }
        }
        if (fresh == 0) return 0;

        int minutes = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            boolean spread = false;
            for (int i = 0; i < size; i++) {
                int[] p = q.poll();
                for (int d = 0; d < 4; d++) {
                    int nr = p[0] + DR[d];
                    int nc = p[1] + DC[d];
                    if (nr < 0 || nr >= R || nc < 0 || nc >= C) continue;
                    if (grid[nr][nc] != 1) continue;
                    grid[nr][nc] = 2;        // enqueue 시점에 상태 전환
                    fresh--;
                    q.offer(new int[]{nr, nc});
                    spread = true;
                }
            }
            if (spread) minutes++;
        }
        return fresh == 0 ? minutes : -1;
    }

    public static void main(String[] args) {
        int[][] g1 = {{2,1,1},{1,1,0},{0,1,1}};
        System.out.println(orangesRotting(g1)); // 4

        int[][] g2 = {{2,1,1},{0,1,1},{1,0,1}};
        System.out.println(orangesRotting(g2)); // -1

        int[][] g3 = {{0,2}};
        System.out.println(orangesRotting(g3)); // 0
    }
}
```

**이런 실수를 피한다**
- 큐가 비어 있지 않으면 무조건 `minutes++`를 하면, 퍼짐이 없는 마지막 레벨에서도 +1이 되어 답이 1 커진다. `spread` 플래그로 방어한다.
- `visited` 배열을 별도로 두기보다 `grid[nr][nc] = 2`로 직접 상태를 바꾸면 메모리도 절약되고 버그 표면이 줄어든다.
- 멀티 소스라는 걸 놓치고 `2` 한 곳에서만 BFS를 시작하면 일부 케이스에서 답이 과대 추정된다.

</details>

## 라이브 코딩 체크리스트

- [ ] 문제를 내 언어로 재진술했다.
- [ ] 그래프/트리 모델링을 선언했다(노드·간선·방향성·가중치 유무).
- [ ] DFS/BFS 선택 이유를 **한 문장**으로 말했다.
- [ ] 재귀 vs 반복 여부를 깊이 한도 기준으로 결정했다.
- [ ] visited 처리 시점을 enqueue/함수 진입에 맞췄다.
- [ ] 엣지 케이스(빈 입력, 자기 루프, 분리 컴포넌트, 시작==도착)를 나열했다.
- [ ] 시간/공간 복잡도를 계산했다.
- [ ] 작은 입력으로 손 추적 디버깅을 시연했다.
- [ ] 마무리에 "실무였다면 이렇게 바꿉니다"(예: 반복 DFS 사용, 큐 사이즈 제한)를 한 줄 덧붙였다.

이 체크리스트를 면접 10분 전에 한 번 훑고 들어가면, 같은 문제를 만났을 때 사고 흐름이 흐트러지지 않는다.
