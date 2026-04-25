# [초안] Union-Find로 라이브 코딩 뚫기 — Java 백엔드 시니어용 실전 가이드

## 왜 Union-Find인가

라이브 코딩에서 그래프 문제는 거의 빠지지 않는다. BFS/DFS만큼 자주 등장하지는 않지만, "두 원소가 같은 그룹인지", "지금까지 연결된 컴포넌트가 몇 개인지", "이 간선을 추가해도 사이클이 생기지 않는지"를 묻는 문제가 나오면 다른 자료구조로는 깔끔하게 풀리지 않는다. 이때 Union-Find(Disjoint Set Union, DSU)가 정답이다.

라이브 코딩 환경에서 Union-Find가 매력적인 이유는 세 가지다.

첫째, 코드량이 짧다. 면접 시간이 45분이라 가정할 때, 사고 시간을 충분히 확보하면서도 실수 없이 칠 수 있는 분량이다. 둘째, 거의 외워도 되는 골격이 있다. `parent[]`, `find()`, `union()` 세 가지가 전부고, path compression과 union by rank/size를 합치면 거의 상수에 가까운 시간 복잡도가 나온다. 셋째, 응용 폭이 넓다. Kruskal MST, 사이클 탐지, 동적 연결성, 오프라인 쿼리 처리, 그리드 컴포넌트 카운팅 같은 문제를 같은 골격으로 푼다.

시니어 백엔드 관점에서도 의미가 있다. 분산 환경에서 "어떤 두 리소스가 같은 샤드에 속하는가", "장애 도메인 단위로 묶일 때 그룹이 어떻게 형성되는가" 같은 질문은 결국 disjoint set 문제다. 알고리즘 자체보다 "이 문제는 disjoint set으로 모델링되는구나"라고 빠르게 인지하는 능력이 평가된다.

## 핵심 개념 — parent 배열로 숲(forest)을 표현한다

Union-Find의 본질은 각 원소가 자신이 속한 집합의 대표자(root)를 향해 부모 포인터를 따라 올라가는 트리 구조다. 모든 원소가 별도 트리로 시작했다가, `union` 연산을 거치면서 트리들이 합쳐진다.

가장 단순한 표현은 다음 두 가지다.

```
parent[i] = i 자신       → i는 자기 자신이 root
parent[i] = j (j ≠ i)   → i의 부모는 j
```

`find(x)`는 `parent[x]`를 따라 올라가다가 `parent[r] == r`인 r을 만나면 그 r이 x가 속한 집합의 대표자다.

`union(x, y)`는 `find(x)`와 `find(y)`를 구한 뒤, 한쪽 root의 부모를 다른 쪽 root로 설정해 두 트리를 합친다.

여기까지가 골격이다. 그런데 그냥 이대로 두면 한쪽으로 길게 늘어진 트리가 만들어져서 `find`가 O(n)까지 갈 수 있다. 그래서 두 가지 최적화를 거의 항상 같이 적용한다.

### Path compression

`find(x)`를 수행하면서 거쳐 간 모든 노드의 `parent`를 곧장 root로 갱신한다. 두 번째 호출부터는 거의 한 번에 root에 도달한다.

```java
int find(int x) {
    if (parent[x] == x) return x;
    parent[x] = find(parent[x]); // 재귀하면서 root로 평탄화
    return parent[x];
}
```

스택이 깊어지는 게 걱정이면 반복문 + 두 번째 패스로 압축할 수 있지만, 라이브 코딩에서는 위 재귀형이 가독성이 가장 좋다. 입력 규모가 N=10^5 정도면 재귀 깊이도 충분히 견딘다.

### Union by rank / Union by size

두 트리를 합칠 때, 키(또는 크기)가 작은 트리를 큰 트리에 붙여야 트리가 더 깊어지지 않는다.

- **union by rank**: rank는 트리의 추정 깊이. 같은 rank끼리 합칠 때만 +1.
- **union by size**: 각 root가 보유한 원소 개수. 큰 쪽이 부모, 작은 쪽이 자식.

라이브 코딩에서는 size가 더 자주 유용하다. 컴포넌트 크기를 직접 묻는 문제(예: "현재 가장 큰 그룹의 크기는?")가 자주 나오는데, size를 들고 있으면 별도 계산이 필요 없다.

path compression + union by rank/size를 함께 쓰면 m개의 연산에 대해 O(m · α(n))이 된다. α는 inverse Ackermann이라 사실상 4 이하의 상수로 봐도 된다.

## connected components 사고방식

Union-Find로 풀어야 한다는 신호는 보통 이렇다.

- "두 노드가 같은 그룹에 속하는가?"가 자주 질의된다.
- 간선이 시간 순서로 들어오고, 그때그때 연결 여부를 알아야 한다.
- 그래프에서 사이클을 만드는 첫 간선이 무엇인지 묻는다.
- 여러 그리드 셀을 묶어 컴포넌트 단위로 카운트해야 한다.
- 오프라인 쿼리: 모든 간선을 한꺼번에 받아 가중치 순으로 처리해도 되는 경우(MST).

반대로 "두 노드 사이의 최단 경로", "특정 경로의 가중치 합" 같은 질문이 들어오면 Union-Find만으로는 부족하고 BFS/DFS/Dijkstra가 필요하다. Union-Find는 정확히 *연결성(connectivity)* 만을 다루는 자료구조라는 점을 잊으면 안 된다.

또 하나, **간선 삭제(disconnect)는 Union-Find가 직접 다루기 어렵다.** 간선이 빠지는 시나리오를 보면 "역으로 시간을 되감아 union으로 재해석"하는 트릭(오프라인 처리)을 떠올려야 한다. 라이브 코딩에서 이 패턴이 나오면 면접관이 시니어급 사고를 보고 싶어 한다는 신호다.

## 그래프 문제에서 언제 쓰는지 판단하는 체크리스트

라이브 코딩 첫 5분 안에 결정해야 한다.

1. 그래프 정점 수 N과 간선 수 M이 주어졌는가?
2. 쿼리가 "연결 여부", "그룹 크기", "그룹 개수", "사이클 여부"인가?
3. 간선이 한 번 추가되면 빠지지 않는가?
4. 가중치를 정렬해서 작은 것부터 합치라는 신호가 보이는가? (MST 후보)
5. 2D 그리드인데 인접 셀을 같은 그룹으로 묶어야 하는가? (셀 인덱스를 `r * cols + c`로 평탄화)

세 개 이상이 들어맞으면 Union-Find로 시작하고, 풀리지 않을 때 BFS/DFS로 후퇴하는 전략을 쓴다.

## 자주 나오는 응용 패턴

- **Kruskal MST**: 간선을 가중치 오름차순 정렬 → 사이클을 만들지 않는 간선만 union.
- **사이클 탐지(무방향)**: union 시도 시 두 끝점의 root가 같으면 사이클이 생기는 간선.
- **동적 연결성**: 온라인으로 간선이 추가되며 "지금 연결돼 있나?"를 빠르게 답해야 할 때.
- **친구 관계 / 계정 병합**: LeetCode "Accounts Merge" 류. 이메일 → id 매핑 후 union.
- **그리드 섬 카운트**: "Number of Islands II"처럼 셀이 동적으로 활성화되는 경우 BFS/DFS보다 압도적으로 빠르다.
- **오프라인 쿼리 역방향 처리**: 간선 삭제 시나리오에서 모든 삭제를 마친 최종 상태에서 시작해 시간을 거꾸로 되돌리며 union.

## 표준 Java 템플릿 — 외워둘 것

라이브 코딩에서 외워둬야 할 핵심 골격이다. 약 25줄.

```java
class DSU {
    int[] parent;
    int[] size;
    int components;

    DSU(int n) {
        parent = new int[n];
        size = new int[n];
        components = n;
        for (int i = 0; i < n; i++) {
            parent[i] = i;
            size[i] = 1;
        }
    }

    int find(int x) {
        if (parent[x] == x) return x;
        parent[x] = find(parent[x]);
        return parent[x];
    }

    boolean union(int a, int b) {
        int ra = find(a);
        int rb = find(b);
        if (ra == rb) return false; // 이미 같은 그룹
        if (size[ra] < size[rb]) { int t = ra; ra = rb; rb = t; }
        parent[rb] = ra;
        size[ra] += size[rb];
        components--;
        return true;
    }

    int componentSize(int x) { return size[find(x)]; }
    boolean connected(int a, int b) { return find(a) == find(b); }
}
```

이 템플릿은 거의 모든 라이브 코딩에서 그대로 쓸 수 있다. `union`이 boolean을 반환하게 한 게 핵심 트릭이다. "사이클을 만드는 간선" 문제, "MST에 들어간 간선 수" 문제 모두 반환값만 보면 된다.

## 구현 시 흔한 버그

라이브 코딩에서 면접관이 가장 자주 잡아내는 실수들이다. 적어도 한 번씩 직접 겪어봐야 한다.

1. **`parent[i] = i` 초기화 누락.** 0으로 가만히 두면 모든 원소의 root가 0이 되어 처음부터 사이클이 보인다.
2. **`find` 안에서 path compression을 빼먹음.** 작동은 하지만 Worst-case에서 TLE.
3. **`union`에서 root끼리 비교하지 않고 원본 인덱스끼리 비교.** `parent[a] = b`처럼 짜면 트리가 끊긴다. 항상 `find(a)`, `find(b)`를 먼저 구한다.
4. **`size`를 root가 아닌 원소에 갱신.** 합칠 때 반드시 `size[ra] += size[rb]`처럼 root 인덱스에만 누적해야 한다.
5. **컴포넌트 카운트를 별도로 갱신하지 않음.** `components--`를 union 성공 시에만 해야 하며, root가 같을 때 빼면 음수로 간다.
6. **그리드에서 좌표 평탄화 실수.** `idx = r * cols + c`인데 `r * rows + c`로 잘못 적는 패턴이 흔하다. 화이트보드에 한 번 작성해두는 습관이 도움이 된다.
7. **재귀 깊이.** path compression의 재귀형이 N이 매우 클 때 스택을 터뜨릴 수 있다. 면접관이 "더 큰 입력에서는?"이라고 물으면 반복문 버전을 칠 수 있어야 한다.
8. **간선 삭제를 직접 구현하려는 시도.** Union-Find는 분리(disjoin)를 지원하지 않는다. 이걸 시도하는 순간 시간을 잃는다. 오프라인 트릭으로 우회한다.

## 라이브 면접에서 접근 방식을 설명하는 방법

HackerRank 스타일 라이브 코딩에서는 *코드를 치기 전에 어떻게 사고했는지*를 말로 풀어내는 게 거의 절반의 점수다. 다음 5단계로 말하면 안전하다.

1. **문제를 1문장으로 다시 말하기.** "결국 N개의 노드와 M개의 간선이 주어지고, 추가될 때마다 두 노드가 같은 그룹인지 답해야 하는 문제로 이해했습니다."
2. **자료구조 선정 근거.** "연결 여부와 그룹 크기를 빠르게 묻고 간선이 빠지지 않으니 Union-Find가 적합합니다. BFS/DFS는 매번 O(N+M)이라 쿼리당 비효율입니다."
3. **시간 복잡도 선언.** "path compression + union by size로 m개의 연산에 대해 O(m · α(n)) ≈ O(m). N=10^5, M=10^5에서 충분합니다."
4. **엣지 케이스 언급.** "self-loop 간선, 이미 같은 그룹인 간선, 1-indexed 입력 처리, 컴포넌트가 여러 개인 초기 상태."
5. **코딩 진행.** 위 템플릿을 그대로 친 뒤, 문제 고유 로직만 main에서 추가한다.

면접관이 "더 최적화할 수 있나요?"라고 물으면, "이미 Union-Find는 거의 상수 시간이고, I/O 비용이 더 큰 구간일 가능성이 큽니다. `BufferedReader`로 입력을 받겠습니다." 정도로 정리하면 된다. 시니어급 답변이다.

## 로컬 연습 환경 세팅

JDK 17 이상이면 충분하다. 한 파일에 클래스 하나 두고 바로 컴파일하면 된다.

```bash
mkdir -p ~/practice/dsu
cd ~/practice/dsu
# Solution.java 작성 후
javac Solution.java
echo "테스트 입력" | java Solution
```

라이브 코딩 환경(HackerRank, CoderPad 등)은 stdin/stdout 기반이 많다. 평소 연습할 때부터 `BufferedReader`/`StringTokenizer` 패턴을 손에 익혀두면 좋다.

```java
import java.io.*;
import java.util.*;

public class Solution {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(br.readLine());
        // ...
        StringBuilder sb = new StringBuilder();
        // 출력은 sb에 모아 마지막에 한 번에
        System.out.print(sb);
    }
}
```

`Scanner`는 편하지만 큰 입력에서 느려서 면접 중 TLE의 흔한 원인이다.

## 연습 문제 1 (쉬움) — 친구 네트워크의 컴포넌트 개수

> N명의 사람이 있고(0 ~ N-1), 친구 관계 M개가 주어진다. 친구 관계는 양방향이며, 친구의 친구도 같은 그룹으로 본다. 전체 그룹이 몇 개인지 출력하라.
>
> 입력 1행: `N M`
> 다음 M행: `a b` (a와 b가 친구)
> 출력: 컴포넌트 개수
>
> 제약: 1 ≤ N ≤ 10^5, 0 ≤ M ≤ 2·10^5

먼저 직접 풀어 보고, 막히면 아래 풀이를 본다.

<details>
<summary>풀이 보기 — 컴포넌트 개수</summary>

핵심 아이디어는 단순하다. DSU를 만들고 모든 친구 관계에 대해 union한 뒤, `components`만 출력하면 된다. 별도의 set 카운팅도 필요 없다.

주의할 점은 자기 자신과의 친구 관계나 이미 같은 그룹인 관계가 들어와도 `union`이 false를 반환하면서 components를 줄이지 않는다는 점이다. 우리 템플릿이 이미 안전하게 처리한다.

복잡도는 O((N + M) · α(N))이고, N=10^5, M=2·10^5에서 즉시 통과한다.

```java
import java.io.*;
import java.util.*;

public class Solution {
    static int[] parent, size;
    static int components;

    static int find(int x) {
        if (parent[x] == x) return x;
        parent[x] = find(parent[x]);
        return parent[x];
    }

    static boolean union(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra == rb) return false;
        if (size[ra] < size[rb]) { int t = ra; ra = rb; rb = t; }
        parent[rb] = ra;
        size[ra] += size[rb];
        components--;
        return true;
    }

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(br.readLine());
        int n = Integer.parseInt(st.nextToken());
        int m = Integer.parseInt(st.nextToken());

        parent = new int[n];
        size = new int[n];
        components = n;
        for (int i = 0; i < n; i++) {
            parent[i] = i;
            size[i] = 1;
        }

        for (int i = 0; i < m; i++) {
            st = new StringTokenizer(br.readLine());
            int a = Integer.parseInt(st.nextToken());
            int b = Integer.parseInt(st.nextToken());
            union(a, b);
        }

        System.out.println(components);
    }
}
```

면접 중에 이 코드를 칠 때는 `find`/`union`을 먼저 작성한 뒤 main을 채우는 순서가 자연스럽다. main을 먼저 쓰면 자료구조가 흔들릴 때 코드가 꼬인다.

</details>

## 연습 문제 2 (중간) — 가장 큰 그룹의 크기를 추적하는 동적 연결성

> N개의 노드가 있다(1 ~ N). Q개의 쿼리가 주어진다.
>
> - `1 a b`: 노드 a와 b를 연결한다.
> - `2 a`: 현재 a가 속한 그룹의 크기를 출력한다.
> - `3`: 현재 가장 큰 그룹의 크기를 출력한다.
>
> 제약: 1 ≤ N ≤ 2·10^5, 1 ≤ Q ≤ 5·10^5
>
> 1-indexed 입력에 주의.

라이브 코딩에서 자주 나오는 변형이다. "전역 최대값"을 union마다 갱신해야 한다는 작은 트릭이 추가된다.

<details>
<summary>풀이 보기 — 동적 연결성 + 전역 최대 그룹</summary>

DSU에 `maxSize` 변수를 추가한다. `union`이 성공할 때만 `maxSize = max(maxSize, size[ra])`를 갱신하면 된다. 쿼리 3은 O(1).

쿼리 2는 `componentSize(a)`를 그대로 쓰면 된다.

1-indexed 입력은 두 가지로 처리할 수 있다. (a) 0-indexed로 내부 변환, (b) 배열을 N+1 크기로 잡기. 라이브에서 실수가 적은 쪽은 (b)다. 단, `parent[0]`은 사용하지 않는다는 점만 명확히 한다.

또 한 가지, 출력이 많은 문제이므로 `StringBuilder`에 모아 마지막에 한 번 출력하는 게 안전하다. `System.out.println`을 쿼리마다 호출하면 I/O 때문에 시간 초과가 날 수 있다.

```java
import java.io.*;
import java.util.*;

public class Solution {
    static int[] parent, size;
    static int maxSize;

    static int find(int x) {
        if (parent[x] == x) return x;
        parent[x] = find(parent[x]);
        return parent[x];
    }

    static void union(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra == rb) return;
        if (size[ra] < size[rb]) { int t = ra; ra = rb; rb = t; }
        parent[rb] = ra;
        size[ra] += size[rb];
        if (size[ra] > maxSize) maxSize = size[ra];
    }

    static int componentSize(int x) { return size[find(x)]; }

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(br.readLine());
        int n = Integer.parseInt(st.nextToken());
        int q = Integer.parseInt(st.nextToken());

        parent = new int[n + 1];
        size = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            parent[i] = i;
            size[i] = 1;
        }
        maxSize = 1;

        StringBuilder sb = new StringBuilder();

        for (int i = 0; i < q; i++) {
            st = new StringTokenizer(br.readLine());
            int op = Integer.parseInt(st.nextToken());
            if (op == 1) {
                int a = Integer.parseInt(st.nextToken());
                int b = Integer.parseInt(st.nextToken());
                union(a, b);
            } else if (op == 2) {
                int a = Integer.parseInt(st.nextToken());
                sb.append(componentSize(a)).append('\n');
            } else {
                sb.append(maxSize).append('\n');
            }
        }

        System.out.print(sb);
    }
}
```

이 문제에서 면접관이 던질 만한 추가 질문은 두 가지다.

첫째, "간선이 빠지는 4번 쿼리도 추가되면?" — 이 순간 Union-Find로는 직접 못 푼다고 솔직히 말하고, 오프라인 처리(쿼리를 모두 받아 역순으로 union) 또는 Link-Cut Tree 같은 고급 자료구조를 언급한다. 시니어급 답변이다.

둘째, "쿼리 3을 O(1) 말고 진짜로 매번 정확히 계산하라면?" — heap을 같이 들고 있어야 하지만, lazy deletion 패턴이 필요하다고 설명한다. 시간이 남으면 구현, 부족하면 설명만으로도 충분하다.

</details>

## 면접 답변 프레이밍 — 시니어 백엔드 관점

알고리즘 면접이라도 결국 "이 사람이 시스템을 만들 수 있는가"를 본다. Union-Find 답변에서 시니어 색을 입히는 포인트는 다음과 같다.

- **자료구조 선택의 근거를 시간복잡도로 정량화한다.** "α(n) ≈ 4 이하의 상수입니다"라고 못 박는다.
- **확장성 가정을 명시한다.** "N이 백만 이상으로 커지면 재귀 path compression을 반복문으로 바꾸겠습니다."
- **운영 관점을 살짝 얹는다.** "이 패턴을 실제 서비스에서 본 적이 있는데, 사용자 계정 병합 시 동일한 사람으로 식별되는 식별자들을 union으로 묶는 배치 작업이 있었습니다." 식의 사례 한 줄.
- **테스트 가능성.** "면접 시간이 더 있다면 `connected`, `componentSize`, `union`이 boolean을 반환하는 부분을 단위 테스트하겠습니다."
- **에러 핸들링과 유효성.** 노드 인덱스 범위 검증을 어디서 할지 (DSU 내부 vs 호출부) 잠깐 언급한다.

면접에서 가장 듣고 싶지 않은 답변은 "외운 코드 그대로 쳤습니다"다. 반대로 가장 좋은 답변은 "이 문제를 모델링하면 disjoint set이고, 다음 트레이드오프를 검토했습니다"다.

## 사고 흐름 체크리스트 (라이브 코딩 직전 1분)

면접 시작 직전이나 문제를 받자마자 머릿속으로 돌리면 좋은 항목이다.

- [ ] 이 문제는 연결성/그룹 크기/사이클 중 무엇을 묻는가?
- [ ] 간선이 빠지는가? 빠지면 Union-Find가 부적합하거나 오프라인 트릭이 필요하다.
- [ ] N과 M의 상한은? α(n) 가정이 통하는 규모인가?
- [ ] 입력이 0-indexed인가 1-indexed인가? 배열 크기 N인가 N+1인가?
- [ ] 컴포넌트 개수, 컴포넌트 크기, 가장 큰 그룹 중 어떤 정보를 들고 있어야 하는가?
- [ ] 출력이 많은가? `StringBuilder` + `BufferedReader`를 쓸 것인가?
- [ ] path compression과 union by size를 둘 다 적용했는가?
- [ ] `union`의 반환값(이미 같은 그룹이면 false)을 활용해야 하는 문제인가?
- [ ] self-loop, 중복 간선, 동일 노드 union 같은 엣지 케이스를 처리했는가?
- [ ] 마지막 1분: 입력 파싱 인덱스 오프바이원, root vs 원본 인덱스 혼동, components 카운트 갱신을 다시 확인했는가?

이 체크리스트를 한 번 돌리는 데 1~2분이면 충분하고, 라이브 코딩 결과물의 안정성이 눈에 띄게 올라간다.
