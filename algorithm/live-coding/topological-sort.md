# [초안] 라이브 코딩 - 위상 정렬(Topological Sort) 한 번에 정리

## 왜 면접에서 위상 정렬이 자주 나오는가

라이브 코딩에서 위상 정렬은 "그래프 + 큐 + 의존성 추론"이라는 세 가지 백엔드 감각을 동시에 검증할 수 있는 깔끔한 주제다. 출제자가 직접적으로 "위상 정렬을 구현하세요"라고 묻는 경우는 드물고, 대부분은 다음과 같은 옷을 입고 등장한다.

- "강의 N개가 있고, 일부 강의는 선수 강의가 있다. 모든 강의를 들을 수 있는 순서가 존재하는가?"
- "빌드 태스크들의 의존 관계가 주어졌을 때 실행 가능한 순서를 출력하라."
- "패키지 매니저에서 설치 순서를 결정하라."
- "마이크로서비스 N개가 부팅 순서 의존성을 가질 때 부팅 순서를 출력하라."

이 모든 문제의 공통점은 `A는 B가 끝나야 시작할 수 있다`라는 **선후관계(precedence)**다. 면접관이 보고 싶은 것은 다음 세 가지다.

1. 문제 설명을 듣고 "이건 DAG 위에서의 위상 정렬 문제다"라고 30초 안에 매핑할 수 있는가.
2. Kahn's algorithm(진입차수 기반 BFS)을 큐와 진입차수 배열로 깔끔하게 구현할 수 있는가.
3. 사이클을 어떻게 감지하고, 입력이 DAG가 아닐 때 어떤 결과를 반환할지 명확히 설명할 수 있는가.

시니어 백엔드 면접에서는 여기에 한 가지가 더 붙는다. **"실서비스에서 이 알고리즘을 적용한다면 어디에 쓰일 것 같습니까?"** Spring 빈 초기화 순서, Gradle 태스크 그래프, 데이터 파이프라인 DAG(Airflow), DB 마이그레이션 의존성, 빌드 캐시 무효화 등 자연스럽게 언급할 수 있어야 한다.

## 핵심 개념: DAG와 위상 정렬

위상 정렬(topological sort)은 **방향 비순환 그래프(Directed Acyclic Graph, DAG)**의 정점들을 일렬로 나열했을 때, 모든 간선 `(u → v)`에 대해 `u`가 `v`보다 앞에 오는 순서를 만드는 것이다.

여기서 두 가지를 분명히 해야 한다.

- **방향(Directed)**: "A가 B의 선수다"는 단방향이다. A → B와 B → A는 다르다.
- **비순환(Acyclic)**: 사이클이 있으면 위상 정렬은 **존재하지 않는다**. A가 B의 선수이고 B가 A의 선수라면 무엇을 먼저 시작할 수 없다.

위상 정렬의 결과는 **유일하지 않다**. 같은 DAG에서도 여러 개의 valid한 순서가 존재할 수 있다. 면접에서 "정답이 하나가 아닌 것 같은데요"라고 묻는다면 "valid한 순서 중 하나만 출력하면 됩니다. 다만 사전순으로 정렬해야 한다는 추가 조건이 붙으면 PriorityQueue를 쓸 수 있습니다"라고 답하면 된다.

### 진입차수(in-degree)란

정점 `v`로 들어오는 간선의 개수를 `v`의 진입차수라고 한다. 진입차수가 0이라는 것은 "이 정점은 더 이상 기다려야 할 선행 작업이 없다"는 뜻이다. 위상 정렬의 직관은 단순하다.

> 진입차수가 0인 정점부터 차례차례 꺼내고, 그 정점이 가리키는 다른 정점들의 진입차수를 1씩 줄인다. 그러다 새로 0이 되는 정점이 있으면 큐에 넣는다. 모든 정점을 다 꺼내면 그 순서가 위상 정렬이다.

이게 바로 **Kahn's algorithm**이다.

### 왜 BFS인가, DFS도 되지 않는가

DFS 기반 위상 정렬도 존재한다(후위 순회 후 역순). 하지만 라이브 코딩에서는 Kahn's algorithm을 **첫 번째 선택**으로 가져가는 것이 안전하다. 이유는 세 가지다.

- 사이클 감지가 자연스럽다. 큐가 비었는데 처리한 정점 수가 N보다 적으면 사이클이 있다.
- 진입차수 배열만 있으면 되고 재귀가 없다. 스택 오버플로우 걱정이 없다.
- 면접관에게 설명할 때 "선행 조건이 없는 노드부터 처리"라는 비즈니스 직관과 1:1 대응된다.

DFS 풀이는 "백엣지로 사이클 감지를 같이 해야 하고 방문 상태를 3가지(미방문/방문중/완료)로 관리해야 한다"는 부담이 있다. 면접에서 시간을 빨리 까먹는다.

## 사이클이 있으면 왜 실패하는가

사이클이 있는 부분 그래프에서는 **모든 정점의 진입차수가 1 이상**이다. 사이클을 이루는 정점들은 서로가 서로를 가리키기 때문에, 어느 한쪽을 0으로 만들 외부 자극이 없다. 결과적으로 큐에 들어갈 수 없고 영원히 처리되지 않는다.

라이브 코딩에서 이 점을 말로 풀 때는 이렇게 표현한다.

> "사이클이 있으면 그 사이클 안의 노드들은 서로를 기다리는 데드락 상태가 됩니다. Kahn's에서는 큐가 자연스럽게 비게 되고, 처리한 노드 수가 N보다 작아지므로 그 차이로 사이클의 존재를 감지합니다."

데드락이라는 단어를 백엔드 컨텍스트로 가져오는 게 핵심이다. 트랜잭션 데드락, 분산 락에서의 순환 대기와 같은 구조라는 점을 한 줄 덧붙이면 시니어 톤이 살아난다.

## 선후관계 문제로 변환하는 감각

라이브 코딩에서는 위상 정렬을 직접 풀라고 안 한다. 옷을 벗겨야 한다. 다음 키워드가 등장하면 즉시 위상 정렬을 의심한다.

- "~를 하기 전에 반드시 ~를 끝내야 한다"
- "선수 과목", "의존성", "prerequisite", "depends on"
- "유효한 순서가 존재하는가"
- "빌드 순서", "초기화 순서", "실행 순서"
- "사이클이 있는지 판단"

옷을 벗긴 뒤에는 항상 다음 4가지를 그래프 모델로 옮긴다.

1. **노드는 무엇인가**: 강의 / 태스크 / 패키지 / 서비스
2. **간선의 방향은 어디인가**: `prereq → course` 인지 `course → prereq` 인지 명확히 정한다. 일반적으로는 "선행이 끝나야 후행이 시작 가능"이므로 `선행 → 후행` 방향을 권장한다. 이렇게 하면 진입차수가 "남은 선행 개수"라는 직관과 일치한다.
3. **노드 식별자**: `int 0..N-1`로 강제할 것인가, `String`으로 받을 것인가. `String`이면 `Map<String, Integer>`로 인덱싱한다.
4. **출력 형식**: 순서 하나? 가능 여부 boolean? 사전순?

이 네 가지를 30초 안에 면접관에게 정리해 말로 확인받는 것이 라이브 코딩의 가장 중요한 첫 단계다.

## 구현 시 흔한 버그

라이브 코딩에서 떨어지는 90%는 알고리즘 무지가 아니라 **잔실수**다. 위상 정렬에서 자주 보이는 버그를 카탈로그화해두면 면접장에서 시간을 아낄 수 있다.

### 1. 간선 방향을 거꾸로 잡기

`[1, 0]`이 "1을 들으려면 0이 선수다"라는 의미라면 `0 → 1` 간선을 추가해야 한다. 이걸 `1 → 0`으로 추가하면 진입차수 의미가 뒤집혀서 결과가 비논리적으로 나온다. 항상 입력 형식의 의미를 한 번 더 읽고 시작한다.

### 2. 진입차수 배열 초기화 누락

`int[] inDegree = new int[n]` 만 선언하고 `inDegree[v]++`를 빠뜨리거나, 양방향으로 ++하는 실수가 많다. 진입차수는 **들어오는 간선만** 카운트한다.

### 3. 큐에 처음 0인 노드들을 넣는 것을 잊음

루프 시작 전에 `for (int i = 0; i < n; i++) if (inDegree[i] == 0) queue.offer(i);`를 빠뜨리면 큐는 영원히 비어있고 결과는 빈 리스트가 된다.

### 4. 사이클 감지 실패

처리한 노드 수가 N보다 작은데도 그냥 정렬 결과를 반환하면, 부분 결과를 정답인 양 내보내게 된다. 항상 `if (result.size() != n) return /* 사이클 표시 */;`를 마지막에 둔다.

### 5. 자기 자신으로의 간선

`u → u`가 입력에 있으면 그 자체가 사이클이다. Kahn's에서 자연스럽게 걸러지지만, 인접 리스트에 중복 간선이 들어오면 진입차수가 과도하게 커져서 영원히 처리되지 않을 수 있다. 입력 검증이 필요한 문제라면 명시한다.

### 6. List 인접 리스트 인덱스 미초기화

`List<List<Integer>> graph = new ArrayList<>();` 만 만들고 `for (int i = 0; i < n; i++) graph.add(new ArrayList<>());`를 빠뜨리면 NPE가 난다. Java 라이브 코딩에서 가장 흔한 NPE 중 하나다.

### 7. PriorityQueue 사용 시 비교 기준 누락

"사전순으로 출력"이 추가되면 `Queue` 대신 `PriorityQueue<Integer>`를 쓰는데, 객체를 노드로 쓸 때는 `Comparator`를 명시해야 한다. `int`라면 자연 순서로 충분하다.

## 라이브 면접에서 접근 방식을 설명하는 법

HackerRank 스타일 라이브 코딩에서는 **코드를 치기 전에 먼저 말로 풀어야** 한다. 다음 흐름이 안전하다.

1. **문제 재진술 (15초)**: "정리하면 N개의 노드가 있고, 'A를 하려면 B가 끝나야 한다'라는 의존성이 M개 주어집니다. 모든 노드를 처리하는 유효한 순서를 출력하면 되는 문제로 이해했습니다. 맞나요?"
2. **모델링 선언 (15초)**: "이건 DAG 위의 위상 정렬 문제로 보입니다. 간선 방향은 `선행 → 후행`으로 잡고, 진입차수가 0인 노드부터 BFS로 꺼내겠습니다."
3. **사이클 처리 정책 확인 (15초)**: "사이클이 있을 경우 어떻게 처리할까요? 빈 배열을 반환할까요, 예외를 던질까요?"
4. **시간/공간 복잡도 (15초)**: "노드 V개, 간선 E개일 때 `O(V+E)`로 풀립니다. 인접 리스트 메모리도 `O(V+E)`입니다."
5. **간단한 예제 트레이스 (30초)**: 화이트보드처럼 작은 예제 하나를 머리로 돌려본다. "노드 3개, 간선 `0→1, 1→2`라면 진입차수는 `[0, 1, 1]`. 큐에 0이 들어가고, 0을 빼며 1의 진입차수를 0으로 만들고…"
6. **이제 코드를 친다**.

이 6단계를 빠뜨리고 바로 코드부터 치는 후보는 십중팔구 중간에 멈춘다. 시니어일수록 1~5번을 천천히 가져가는 게 점수가 더 높다.

## 로컬 연습 환경 세팅

연습은 IDE 없이도 가능해야 한다. HackerRank나 코딩 화상 면접은 보통 자동완성이 약하기 때문이다.

```bash
mkdir -p ~/coding-prep/topo && cd ~/coding-prep/topo
cat > Main.java <<'EOF'
public class Main {
    public static void main(String[] args) {
        int n = 6;
        int[][] prereq = {{1,0},{2,0},{3,1},{3,2},{4,3},{5,4}};
        int[] order = topoSort(n, prereq);
        for (int v : order) System.out.print(v + " ");
        System.out.println();
    }
    // 본문 풀이를 여기에 옮겨 직접 컴파일
    static int[] topoSort(int n, int[][] prereq) { return new int[0]; }
}
EOF
javac Main.java && java Main
```

추가로 연습 강도를 높이려면 다음 사이트의 위상 정렬 태그 문제를 5~7개 정도 시간을 재며 푼다.

- LeetCode: Course Schedule (207), Course Schedule II (210), Alien Dictionary (269), Minimum Height Trees (310)
- 백준: 2252(줄 세우기), 1766(문제집), 2056(작업)

LeetCode는 영문 문제 해석 연습도 같이 된다. 한국어 면접이라도 외국계 회사면 영문 문제가 나올 수 있어서 시간을 들일 가치가 있다.

## 라이브 코딩 템플릿 (Java)

면접에서 손에 익혀둘 Kahn's 표준 골격이다. 외워서 30초 안에 칠 수 있어야 한다.

```java
import java.util.*;

public class TopoSort {
    static int[] kahn(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        int[] inDeg = new int[n];
        for (int[] e : edges) {
            int from = e[0], to = e[1];
            graph.get(from).add(to);
            inDeg[to]++;
        }
        Deque<Integer> queue = new ArrayDeque<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) queue.offer(i);
        int[] order = new int[n];
        int idx = 0;
        while (!queue.isEmpty()) {
            int u = queue.poll();
            order[idx++] = u;
            for (int v : graph.get(u)) {
                if (--inDeg[v] == 0) queue.offer(v);
            }
        }
        if (idx != n) return new int[0]; // 사이클 존재
        return order;
    }
}
```

이 골격을 바탕으로 입력 포맷이 prerequisite 쌍 `[a, b]`로 들어올 때(`a를 들으려면 b가 선수`)는 `e[0]`과 `e[1]`을 뒤집어서 `b → a` 방향으로 넣어야 한다는 점만 매번 다시 결정하면 된다.

## 인터뷰 답변 프레이밍

면접관이 "위상 정렬에 대해 설명해주세요"라고 직설적으로 묻는다면 다음과 같이 1분 답을 준비해둔다.

> "위상 정렬은 DAG 위에서 모든 의존성을 만족하는 정점 순서를 결정하는 알고리즘입니다. 저는 진입차수 기반의 Kahn's algorithm을 선호하는데, 사이클 감지가 자연스럽고 BFS로 큐만 쓰면 되어서 라이브 코딩에서 실수가 적기 때문입니다. 시간복잡도는 O(V+E)이고, 실무에서는 Spring 빈 초기화 순서, Gradle 태스크 의존성, 데이터 파이프라인 DAG, DB 마이그레이션 순서 같은 곳에서 동일한 구조가 반복적으로 등장합니다. 사이클이 있으면 위상 정렬은 정의되지 않으며, 이는 분산 시스템의 순환 대기 데드락과 같은 구조입니다."

이 답안의 전략은 세 가지다. 첫째, 알고리즘 선택의 **이유**를 말한다. 둘째, **복잡도**를 빼먹지 않는다. 셋째, 실무 도메인 사례를 **세 가지 이상** 든다. 시니어 후보는 알고리즘을 안다는 것을 넘어서 그것이 어디에 쓰이는지를 알아야 한다.

## 연습 문제 1 (쉬움) — 빌드 순서 결정

태스크 N개가 있다. 일부 태스크는 다른 태스크가 끝나야 시작할 수 있다. 모든 태스크를 수행할 수 있는 순서를 한 가지 출력하라. 만약 사이클이 있어 불가능하면 빈 배열을 반환하라.

입력은 `int n`과 `int[][] dependencies` 형태이며 `dependencies[i] = [a, b]`는 "a를 시작하려면 b가 먼저 끝나야 한다"는 뜻이다.

예: `n = 4`, `dependencies = [[1,0],[2,1],[3,2]]` → `[0,1,2,3]`

면접에서 이 문제를 받으면 가장 먼저 확인할 것은 **간선 방향**이다. `[a, b]`가 "a는 b를 필요로 한다"이면 `b → a`로 간선을 만들어야 진입차수 = 남은 선행 개수가 된다.

<details>
<summary>풀이 보기</summary>

핵심 결정 사항.

- 노드: 태스크 ID `0..n-1`
- 간선 방향: `b → a` (b가 끝나야 a 가능)
- 진입차수가 0인 태스크부터 큐에 넣고 BFS
- 처리한 태스크 수가 n보다 작으면 사이클 → 빈 배열 반환

복잡도는 `O(V+E)`. n과 의존성 수에 비례한다.

```java
import java.util.*;

public class BuildOrder {
    public int[] findBuildOrder(int n, int[][] dependencies) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        int[] inDeg = new int[n];
        for (int[] dep : dependencies) {
            int a = dep[0], b = dep[1]; // a needs b
            graph.get(b).add(a);
            inDeg[a]++;
        }

        Deque<Integer> queue = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            if (inDeg[i] == 0) queue.offer(i);
        }

        int[] order = new int[n];
        int idx = 0;
        while (!queue.isEmpty()) {
            int u = queue.poll();
            order[idx++] = u;
            for (int v : graph.get(u)) {
                if (--inDeg[v] == 0) queue.offer(v);
            }
        }

        if (idx != n) return new int[0];
        return order;
    }

    public static void main(String[] args) {
        BuildOrder bo = new BuildOrder();
        int[] r1 = bo.findBuildOrder(4, new int[][]{{1,0},{2,1},{3,2}});
        System.out.println(Arrays.toString(r1)); // [0, 1, 2, 3]

        int[] r2 = bo.findBuildOrder(2, new int[][]{{0,1},{1,0}});
        System.out.println(Arrays.toString(r2)); // []

        int[] r3 = bo.findBuildOrder(6, new int[][]{{1,0},{2,0},{3,1},{3,2},{4,3},{5,4}});
        System.out.println(Arrays.toString(r3)); // 0,1,2,3,4,5 또는 0,2,1,3,4,5
    }
}
```

면접 시 함정 지점.

- `dependencies = []`일 때 `0..n-1`을 그냥 출력해야 함. 큐 초기화 루프가 그 역할을 한다.
- `n = 0`이면 빈 배열 반환. `inDeg`도 0크기로 정상 동작한다.
- 자기 루프 `[0,0]` 입력은 사이클이므로 빈 배열을 반환한다.

</details>

## 연습 문제 2 (중간) — 외계어 사전(Alien Dictionary)

외계인이 사용하는 사전이 있다. 단어들이 그 외계어의 사전순으로 정렬되어 주어진다. 이 사전에서 사용된 알파벳들 사이의 사전순(앞 글자가 뒤 글자보다 먼저 나옴)을 추론하여 valid한 순서 한 가지를 문자열로 반환하라. 모순이 있으면 빈 문자열을 반환하라.

예: `["wrt", "wrf", "er", "ett", "rftt"]` → `"wertf"`

이 문제는 위상 정렬을 바로 보여주지 않는다. **두 단어를 비교해서 한 쌍의 문자 선후관계를 추출**한 뒤, 그 관계들을 위상 정렬해야 한다는 두 단계 추론이 필요하다. 라이브 코딩 면접에서 떨어지는 흔한 지점은 다음 세 가지다.

- 인접한 두 단어만 비교하면 된다는 점을 놓침 (전부 비교하려고 함)
- `["abc", "ab"]`처럼 prefix가 더 긴 단어가 앞에 오면 모순(불가능 케이스)임을 감지하지 못함
- 첫 다른 글자 한 쌍만 정보로 쓰고 그 뒤 글자들에서는 추가 정보를 얻을 수 없다는 점을 놓침

<details>
<summary>풀이 보기</summary>

핵심 결정 사항.

1. 등장하는 모든 알파벳을 노드로 만든다. 이 단계를 빠뜨리면 어떤 글자는 인접 리스트에 등장하지 않아 출력에서 누락된다.
2. 인접한 두 단어 `w1, w2`를 비교하며 첫 다른 글자 `(c1, c2)`를 찾으면 `c1 → c2` 간선을 추가한다. 첫 다른 글자가 없는데 `len(w1) > len(w2)`이면 모순이다.
3. Kahn's algorithm으로 위상 정렬한다. 결과 길이가 등장 글자 수와 다르면 사이클이 있다는 뜻이므로 빈 문자열을 반환한다.
4. 동일 간선이 여러 번 추가되면 진입차수가 부풀어 사이클 오판이 날 수 있다. `Set<Character>`로 중복을 막는다.

복잡도. 단어 총 길이를 L이라 하면 간선 추출은 `O(L)`, 위상 정렬은 `O(노드+간선) = O(26 + 26*26)`이므로 사실상 `O(L)`.

```java
import java.util.*;

public class AlienDictionary {
    public String alienOrder(List<String> words) {
        Map<Character, Set<Character>> graph = new HashMap<>();
        Map<Character, Integer> inDeg = new HashMap<>();

        // 1) 등장 글자 모두 노드로 등록
        for (String w : words) {
            for (char c : w.toCharArray()) {
                graph.putIfAbsent(c, new HashSet<>());
                inDeg.putIfAbsent(c, 0);
            }
        }

        // 2) 인접한 두 단어에서 간선 추출
        for (int i = 0; i + 1 < words.size(); i++) {
            String w1 = words.get(i), w2 = words.get(i + 1);
            int minLen = Math.min(w1.length(), w2.length());
            boolean foundDiff = false;
            for (int j = 0; j < minLen; j++) {
                char c1 = w1.charAt(j), c2 = w2.charAt(j);
                if (c1 != c2) {
                    if (!graph.get(c1).contains(c2)) {
                        graph.get(c1).add(c2);
                        inDeg.merge(c2, 1, Integer::sum);
                    }
                    foundDiff = true;
                    break;
                }
            }
            // prefix가 더 긴 단어가 앞에 오면 모순
            if (!foundDiff && w1.length() > w2.length()) return "";
        }

        // 3) Kahn's algorithm
        Deque<Character> queue = new ArrayDeque<>();
        for (var e : inDeg.entrySet()) {
            if (e.getValue() == 0) queue.offer(e.getKey());
        }

        StringBuilder sb = new StringBuilder();
        while (!queue.isEmpty()) {
            char u = queue.poll();
            sb.append(u);
            for (char v : graph.get(u)) {
                inDeg.merge(v, -1, Integer::sum);
                if (inDeg.get(v) == 0) queue.offer(v);
            }
        }

        if (sb.length() != inDeg.size()) return ""; // 사이클
        return sb.toString();
    }

    public static void main(String[] args) {
        AlienDictionary ad = new AlienDictionary();
        System.out.println(ad.alienOrder(List.of("wrt","wrf","er","ett","rftt")));
        // 예: "wertf"

        System.out.println(ad.alienOrder(List.of("z","x")));
        // "zx"

        System.out.println(ad.alienOrder(List.of("z","x","z")));
        // "" (사이클)

        System.out.println(ad.alienOrder(List.of("abc","ab")));
        // "" (prefix 모순)
    }
}
```

면접관이 묻기 전에 먼저 짚을 함정.

- "왜 모든 단어 쌍을 비교하지 않고 인접한 쌍만 비교합니까?" → 사전순 정의상 인접한 쌍의 첫 다른 글자만 직접 정보를 준다. 떨어진 단어 쌍은 인접 쌍들을 통해 transitively 도출되므로 중복 정보다.
- "단어 길이가 같지 않은데 첫 다른 글자가 없으면 어떻게 됩니까?" → 짧은 단어가 앞에 와야 한다. `["abc","ab"]`는 모순.
- "결과가 여러 개일 수 있나요?" → 위상 정렬 결과는 일반적으로 유일하지 않다. 그 중 하나만 반환하면 된다.

</details>

## 라이브 코딩 직전 체크리스트

- [ ] 입력 형식의 간선 방향을 한 번 더 읽었는가
- [ ] 노드 수 N, 간선 수 M의 범위를 확인했는가 (인접 리스트 vs 인접 행렬 결정에 영향)
- [ ] 진입차수 배열을 0으로 초기화했는가
- [ ] 진입차수 0인 노드들을 처음에 큐에 넣었는가
- [ ] 처리한 노드 수가 N과 같은지 마지막에 검사했는가
- [ ] 사이클일 때 반환값을 면접관과 합의했는가 (빈 배열, 예외, boolean 등)
- [ ] 작은 예제 하나로 머릿속 트레이스를 마쳤는가
- [ ] 시간/공간 복잡도를 말로 설명할 수 있는가
- [ ] 실무 도메인 적용 사례를 2~3개 댈 수 있는가
- [ ] 사전순 변형이 나오면 PriorityQueue로 바꿀 수 있는가

이 체크리스트를 라이브 코딩 직전 1분 안에 머리로 한 번 훑는 습관만으로도 잔실수의 절반은 사라진다.
