# [초안] 라이브 코딩 대비 — Binary Tree (Java)

## 왜 이 주제가 중요한가

라이브 코딩 면접에서 트리 문제는 거의 빠지지 않는다. HackerRank나 코드페어 같은 환경에서 30~45분짜리 세션에 등장하는 문제 중, 단순 배열/문자열 다음으로 자주 출제되는 자료구조가 이진 트리다. 시니어 백엔드 면접에서도 트리 문제가 나오는 이유는 명확하다.

- **재귀 사고력 검증**: 종료 조건과 분할 정복을 자연스럽게 사용할 수 있는지 본다.
- **자료구조 기반 사고**: 인덱스 접근만 가능한 배열과 달리, 참조 기반 자료구조에서 null 처리, 순회 순서, 메모리 모델을 어떻게 다루는지 본다.
- **시간/공간 복잡도 트레이드오프**: BFS는 큐 기반 너비 우선이라 메모리 폭이 넓고, DFS는 스택 기반(또는 재귀)이라 깊이에 비례한 호출 스택을 쓴다. 어느 쪽을 왜 선택했는지 말로 설명할 수 있어야 한다.
- **백엔드 도메인 연결**: 실제 업무에서도 카테고리 트리, 조직도, 부모-자식 댓글, S3 prefix 트리, B+Tree 인덱스 같은 트리 구조를 다룬다. 라이브 코딩에서 보여준 사고 패턴은 그대로 실무 코드 리뷰 톤으로 이어진다.

면접관이 보는 포인트는 "정답을 빨리 맞추는가"가 아니라 "사고 과정이 일관적이고 디버깅 가능한가"이다. 그래서 이 문서는 단순 알고리즘 풀이집이 아니라, 라이브 환경에서 **소리 내어 설명하면서 푸는 법**까지 같이 다룬다.

## 1. 이진 트리 핵심 개념 정리

이진 트리(Binary Tree)는 각 노드가 최대 두 개의 자식(left, right)을 갖는 트리다. 면접에서는 보통 다음 변형이 등장한다.

- **이진 트리**(Binary Tree): 자식이 0~2개. 정렬 보장 없음.
- **이진 탐색 트리**(BST): `left.value < node.value < right.value` 조건을 만족.
- **완전 이진 트리**(Complete Binary Tree): 마지막 레벨을 제외하고 모두 채워져 있고, 마지막 레벨은 왼쪽부터 채움. 힙 구현의 기반.
- **균형 트리**(Balanced Tree): 모든 노드에서 왼쪽/오른쪽 서브트리 높이 차가 1 이하. AVL, Red-Black 트리가 대표적이다.

높이의 정의는 면접관마다 다르게 쓰니 시작 전 합의해야 한다.

- "노드 1개짜리 트리의 높이는 0이다"라고 하는 정의 (간선 수 기준)
- "노드 1개짜리 트리의 높이는 1이다"라고 하는 정의 (노드 수 기준)

라이브 코딩에서는 **"높이는 루트에서 가장 먼 리프까지의 간선 수, 빈 트리는 -1"** 같은 식으로 한 줄로 합의해 두는 게 안전하다.

### Java 노드 정의

면접용 표준 클래스는 LeetCode/HackerRank가 제공하는 것과 동일하게 맞추는 게 좋다.

```java
public class TreeNode {
    int val;
    TreeNode left;
    TreeNode right;

    TreeNode() {}
    TreeNode(int val) { this.val = val; }
    TreeNode(int val, TreeNode left, TreeNode right) {
        this.val = val;
        this.left = left;
        this.right = right;
    }
}
```

라이브 코딩 환경에서는 이미 정의되어 있는 경우가 대부분이다. 직접 정의해야 한다면 시간 낭비를 줄이기 위해 위 형태를 외워 두는 게 낫다.

## 2. 순회 — 전위 / 중위 / 후위

순회는 "현재 노드를 언제 처리할 것인가"를 결정하는 문제다. 세 가지 모두 DFS의 변형이다.

- **전위**(Preorder): 자기 자신 → 왼쪽 → 오른쪽. 트리 복제, 직렬화에 적합.
- **중위**(Inorder): 왼쪽 → 자기 자신 → 오른쪽. **BST의 중위 순회는 정렬된 순서**를 만든다는 사실은 단골 면접 트릭.
- **후위**(Postorder): 왼쪽 → 오른쪽 → 자기 자신. 자식이 모두 처리되어야 부모가 처리되는 문제(트리 삭제, 디렉터리 용량 합산, 표현식 트리 평가)에 적합.

### 재귀 구현

```java
void preorder(TreeNode node, List<Integer> out) {
    if (node == null) return;
    out.add(node.val);
    preorder(node.left, out);
    preorder(node.right, out);
}

void inorder(TreeNode node, List<Integer> out) {
    if (node == null) return;
    inorder(node.left, out);
    out.add(node.val);
    inorder(node.right, out);
}

void postorder(TreeNode node, List<Integer> out) {
    if (node == null) return;
    postorder(node.left, out);
    postorder(node.right, out);
    out.add(node.val);
}
```

세 함수의 차이는 단 한 줄, `out.add(node.val)`의 위치다. 라이브 코딩에서 면접관에게 "여기서 add 위치만 바꾸면 다른 순회가 됩니다"라고 짚어 주면 자료구조 이해도가 그대로 드러난다.

### 반복 구현 — 스택 기반

재귀는 스택 오버플로 위험이 있어서 **트리 깊이가 클 수 있다고 하면 반복 구현으로 가는 게 안전**하다. 자바에서는 `Deque<TreeNode>`를 스택처럼 쓴다(`Stack` 클래스는 `Vector` 기반이라 동기화 오버헤드가 있다).

```java
List<Integer> inorderIterative(TreeNode root) {
    List<Integer> out = new ArrayList<>();
    Deque<TreeNode> stack = new ArrayDeque<>();
    TreeNode curr = root;
    while (curr != null || !stack.isEmpty()) {
        while (curr != null) {
            stack.push(curr);
            curr = curr.left;
        }
        curr = stack.pop();
        out.add(curr.val);
        curr = curr.right;
    }
    return out;
}
```

## 3. 재귀 종료 조건은 항상 "null 노드"

면접에서 가장 흔한 버그가 재귀 종료 조건이다. 빈 트리(`root == null`), 한쪽 자식만 있는 노드, 리프 노드를 모두 처리할 수 있어야 한다.

좋은 재귀 함수의 시그니처는 다음과 같은 성질을 만족한다.

1. `null`이 들어오면 즉시 의미 있는 base case로 끝난다 (예: 높이는 -1, 합은 0, 존재 여부는 false).
2. 자식 결과로부터 부모 결과를 합성하는 한 줄이 명확하다.
3. 재귀 호출은 `node.left`와 `node.right`에 대해 정확히 한 번씩만 한다 — 같은 노드를 두 번 방문하지 않는다.

높이 계산을 예로 들면:

```java
int height(TreeNode node) {
    if (node == null) return -1;
    return 1 + Math.max(height(node.left), height(node.right));
}
```

- base case: 빈 트리 높이 -1.
- 합성: 좌우 자식 높이 중 큰 값에 자기 자신(간선 1) 더하기.
- 한쪽이 null이어도 `Math.max(-1, h)` 형태로 자연스럽게 처리됨.

만약 base case를 `if (node.left == null && node.right == null) return 0;`처럼 리프 기준으로 두면, 자식 한쪽이 null인 경우를 따로 처리해야 해서 코드가 복잡해진다. **null을 base case로 두는 패턴**을 외워 두는 게 거의 항상 깔끔하다.

## 4. BFS vs DFS — 어느 쪽을 언제 쓰는가

| 기준 | DFS (재귀/스택) | BFS (큐) |
|------|----------------|----------|
| 메모리 | O(h), h는 트리 높이 | O(w), w는 트리 최대 너비 |
| 자연스러운 문제 | 경로 합, 서브트리 합산, 직렬화, 검증 | 레벨 단위, 최단 거리, 최소 깊이, 좌→우 순서대로 보기 |
| 구현 난이도 | 재귀로 짧게 가능 | 큐 + 레벨 사이즈 추적 필요 |
| 위험 | 깊은 트리에서 스택 오버플로 | 마지막 레벨이 매우 넓으면 메모리 폭주 |

면접에서 자주 나오는 결정 기준은 다음과 같다.

- **"가장 짧은 경로 / 최소 깊이"** — BFS. 첫 번째로 만나는 리프가 답.
- **"각 레벨의 평균"** 또는 **"오른쪽에서 본 모습(Right Side View)"** — BFS. 레벨 사이즈를 알아야 한다.
- **"경로 상의 합", "검증(BST/대칭)"** — DFS. 재귀가 자연스럽다.
- **"서브트리 단위 결과를 부모로 합산"** — DFS 후위 순회.

BFS 골격은 다음과 같이 외운다.

```java
List<List<Integer>> levelOrder(TreeNode root) {
    List<List<Integer>> result = new ArrayList<>();
    if (root == null) return result;
    Queue<TreeNode> queue = new ArrayDeque<>();
    queue.offer(root);
    while (!queue.isEmpty()) {
        int size = queue.size();
        List<Integer> level = new ArrayList<>(size);
        for (int i = 0; i < size; i++) {
            TreeNode node = queue.poll();
            level.add(node.val);
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
        result.add(level);
    }
    return result;
}
```

핵심은 `int size = queue.size()` 를 루프 시작점에 한 번 캡처해서 **현재 레벨의 노드만 처리**하는 것이다. 이걸 안 하면 레벨 경계가 흐트러진다.

## 5. 높이와 균형 — 자주 묶이는 단골 질문

"이 트리가 균형인지 판별하시오"는 라이브 코딩 단골이다. 단순 구현은 모든 노드에서 좌우 높이를 다시 계산하느라 O(n²)가 된다. 후위 순회 한 번으로 O(n)에 끝내는 패턴을 알아야 한다.

```java
boolean isBalanced(TreeNode root) {
    return check(root) != -1;
}

// 균형이 깨지면 -1, 아니면 높이 반환
int check(TreeNode node) {
    if (node == null) return 0;
    int l = check(node.left);
    if (l == -1) return -1;
    int r = check(node.right);
    if (r == -1) return -1;
    if (Math.abs(l - r) > 1) return -1;
    return 1 + Math.max(l, r);
}
```

이 패턴은 "단일 재귀 함수가 두 가지 정보(높이 + 균형 여부)를 동시에 들고 올라온다"는 점이 핵심이다. 면접관이 "왜 sentinel로 -1을 썼나요?"라고 물으면 "Boolean과 높이를 따로 들고 다니는 페어 객체를 새로 만들지 않기 위해, 높이가 음수가 될 수 없다는 도메인 제약을 활용했다"고 답하면 깔끔하다.

## 6. 구현 시 흔한 버그 패턴

라이브 코딩에서 시간을 깎아먹는 실수는 거의 정해져 있다.

1. **null 체크 위치 실수** — `node.left.val`처럼 자식의 값에 바로 접근하기 전에 null 가드를 안 두는 경우. base case를 `node == null`로 두면 거의 해결된다.
2. **BFS에서 level 경계 누락** — 레벨 평균/오른쪽 뷰 문제에서 `queue.size()`를 루프 안에서 매번 부르면 자식까지 같이 세서 경계가 깨진다.
3. **재귀로 높이 다시 계산하는 O**(n²) — `isBalanced`를 단순 구현하면 시간 초과. 위의 sentinel 패턴을 알아야 한다.
4. **BST 검증을 인접 노드 비교로만 함** — `node.left.val < node.val && node.right.val > node.val`만 보면 틀린다. 왼쪽 서브트리의 **모든** 노드가 작아야 하므로 (min, max) 범위를 재귀 인자로 넘겨야 한다.
5. **`int` 오버플로** — `Integer.MIN_VALUE`나 `MAX_VALUE` 노드가 들어올 수 있으면 비교 시 `long` 또는 `Integer` 박싱으로 처리해야 한다. BST 검증 문제에서 자주 잡힌다.
6. **`Stack` vs `ArrayDeque`** — `Stack`은 동기화 비용 + 레거시. `Deque<TreeNode> stack = new ArrayDeque<>();`로 가는 게 자바 관용구다.
7. **재귀 깊이** — 트리가 한쪽으로 치우쳐 있으면 N=10^5만 돼도 스택 오버플로. 면접관이 입력 크기를 명시하면 반복 구현으로 갈지 사전에 합의한다.
8. **순회 결과 리스트를 매 호출마다 새로 만들기** — 합치는 비용이 추가됨. 외부에 누적 리스트를 두고 `void` 반환 재귀로 짜는 게 보통 더 빠르다.

## 7. 라이브 면접에서 접근 방식을 설명하는 법

화면 공유 환경에서 면접관이 가장 답답해하는 것은 **침묵**이다. HackerRank 라이브 코딩은 IDE 화면이 공유되기 때문에 사고 흐름을 말로 풀어 줘야 한다. 다음 6단계 스크립트를 외워 두면 머리가 멈춰도 입은 움직인다.

1. **문제 재진술**(30초): "입력은 이진 트리 루트, 출력은 정수. 빈 트리일 때는 0을 반환한다는 가정이 맞나요?" — 가정/엣지 케이스를 같이 못 박는다.
2. **예시 한두 개 손으로 트레이스**(1\~2분): 화이트보드 노트나 IDE 주석에 트리 그림 그리고, 기대 출력을 직접 계산. 단순 케이스 + 비대칭 케이스 + 빈 트리 정도.
3. **접근 후보 비교**(1\~2분): "DFS 재귀로 풀면 O(n) 시간 / O(h) 공간이고, BFS 레벨 순회로 풀면 코드는 길지만 깊이 큰 트리에서도 안전합니다. 입력 깊이가 10^5까지면 BFS 또는 명시적 스택으로 가는 게 안전한데, 어떻게 가정하면 될까요?"
4. **시간/공간 복잡도 합의**: 코드 짜기 전에 미리 말한다. 면접관이 "더 빠르게는?"이라고 물으면 그때 가서 개선한다.
5. **구현**(10\~15분): base case → 재귀 합성 → 메인 호출 순서로 위에서 아래로 채운다. 변수명은 `node`, `left`, `right`, `result` 같은 평범한 이름.
6. **자체 테스트**(3\~5분): 빈 트리, 한쪽으로 치우친 트리, 일반적 케이스, 음수 값 등 직접 트레이스. **테스트 직접 돌리기 전에 입으로 한 번 트레이스**하는 모습을 보여주는 것이 좋다.

면접관 질문에 막히면 "잠시 5초만 생각해 볼게요" 같은 표현을 써서 무음 구간을 명시적으로 만들어 두면 인상이 좋다.

## 8. 로컬 연습 환경

라이브 코딩 환경(HackerRank)을 흉내 내려면, 외부 라이브러리 없이 표준 자바만으로 컴파일/실행이 되어야 한다.

```bash
# JDK 17 권장 (JDK 21도 무방)
java --version

mkdir -p ~/livecoding/tree
cd ~/livecoding/tree

# Solution.java 한 파일로 시작
javac Solution.java
java Solution
```

`Solution.java` 골격:

```java
import java.util.*;

public class Solution {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int val) { this.val = val; }
    }

    public static void main(String[] args) {
        // 작은 트리 직접 만들기
        //        1
        //       / \
        //      2   3
        //     / \
        //    4   5
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2);
        root.right = new TreeNode(3);
        root.left.left = new TreeNode(4);
        root.left.right = new TreeNode(5);

        System.out.println(maxDepth(root));        // 3
        System.out.println(levelOrder(root));      // [[1],[2,3],[4,5]]
    }

    static int maxDepth(TreeNode node) {
        if (node == null) return 0;
        return 1 + Math.max(maxDepth(node.left), maxDepth(node.right));
    }

    static List<List<Integer>> levelOrder(TreeNode root) {
        List<List<Integer>> result = new ArrayList<>();
        if (root == null) return result;
        Queue<TreeNode> queue = new ArrayDeque<>();
        queue.offer(root);
        while (!queue.isEmpty()) {
            int size = queue.size();
            List<Integer> level = new ArrayList<>(size);
            for (int i = 0; i < size; i++) {
                TreeNode n = queue.poll();
                level.add(n.val);
                if (n.left != null) queue.offer(n.left);
                if (n.right != null) queue.offer(n.right);
            }
            result.add(level);
        }
        return result;
    }
}
```

직접 돌려 보면서 다음 세 가지를 손에 익혀 둔다.

- 트리 손으로 만드는 코드 5초 안에 작성
- DFS 재귀 / BFS 레벨 순회 골격을 보지 않고 작성
- `null` 가드 한 줄을 본능적으로 먼저 쓰는 습관

배열에서 트리를 복원하는 헬퍼도 하나 외워 두면 시간 낭비가 줄어든다(LeetCode 입력 형식과 비슷).

```java
static TreeNode build(Integer... arr) {
    if (arr.length == 0 || arr[0] == null) return null;
    TreeNode root = new TreeNode(arr[0]);
    Queue<TreeNode> q = new ArrayDeque<>();
    q.offer(root);
    int i = 1;
    while (!q.isEmpty() && i < arr.length) {
        TreeNode parent = q.poll();
        if (i < arr.length && arr[i] != null) {
            parent.left = new TreeNode(arr[i]);
            q.offer(parent.left);
        }
        i++;
        if (i < arr.length && arr[i] != null) {
            parent.right = new TreeNode(arr[i]);
            q.offer(parent.right);
        }
        i++;
    }
    return root;
}
```

## 9. 연습 문제

라이브 면접에서 자주 출제되는 두 문제를 직접 풀어 본다. 풀이를 보기 전에 **30분 안에 직접 작성 → 손 트레이스 → 코드 실행** 순서로 진행하는 게 좋다.

### 문제 1 (쉬움) — Maximum Depth of Binary Tree

이진 트리의 루트가 주어졌을 때, 최대 깊이를 반환하라. 깊이는 루트에서 가장 먼 리프까지 경로상의 노드 수다. 빈 트리의 깊이는 0이다.

입력 예: `[3, 9, 20, null, null, 15, 7]` → 출력 `3`

먼저 종이에 그려 보고, base case와 합성 규칙을 머릿속으로 한 줄로 정리한 다음 코드를 작성한다.

<details>
<summary>풀이 보기</summary>

**접근**: 재귀 DFS. 빈 노드 깊이를 0으로 두고, 자식 깊이의 최댓값에 1을 더한다.

**복잡도**: 시간 O(n) — 모든 노드 1회 방문. 공간 O(h) — 호출 스택. 균형 트리면 O(log n), 한쪽으로 치우치면 O(n).

**대안**: BFS 레벨 순회로 레벨 카운트를 세도 동일한 결과. 깊이가 매우 큰 입력이라면 스택 오버플로를 피하기 위해 BFS가 유리.

```java
import java.util.*;

public class Solution {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int val) { this.val = val; }
    }

    public static int maxDepth(TreeNode root) {
        if (root == null) return 0;
        int left = maxDepth(root.left);
        int right = maxDepth(root.right);
        return 1 + Math.max(left, right);
    }

    // 깊이가 큰 입력 대비 BFS 버전
    public static int maxDepthBfs(TreeNode root) {
        if (root == null) return 0;
        Queue<TreeNode> queue = new ArrayDeque<>();
        queue.offer(root);
        int depth = 0;
        while (!queue.isEmpty()) {
            int size = queue.size();
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                if (node.left != null) queue.offer(node.left);
                if (node.right != null) queue.offer(node.right);
            }
            depth++;
        }
        return depth;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3);
        root.left = new TreeNode(9);
        root.right = new TreeNode(20);
        root.right.left = new TreeNode(15);
        root.right.right = new TreeNode(7);

        System.out.println(maxDepth(root));     // 3
        System.out.println(maxDepthBfs(root));  // 3
        System.out.println(maxDepth(null));     // 0
    }
}
```

**라이브에서 짚을 포인트**:
- "빈 트리 깊이를 0으로 둔 이유: 깊이=노드 수 정의를 따랐기 때문. 면접관이 다른 정의를 쓴다면 base case만 바꾸면 된다."
- "재귀 호출 결과를 변수에 받은 이유: 디버깅 시 IDE에서 중간값을 보기 위함. 한 줄로도 가능하지만 라이브 환경에서는 가독성이 우선."

</details>

### 문제 2 (중간) — Validate Binary Search Tree

이진 트리가 주어졌을 때, 그것이 유효한 BST인지 판단하라. BST 조건은 다음과 같다.

- 왼쪽 서브트리의 **모든** 노드 값이 현재 노드 값보다 작다.
- 오른쪽 서브트리의 **모든** 노드 값이 현재 노드 값보다 크다.
- 양쪽 서브트리도 BST다.
- 같은 값(중복)은 허용하지 않는다.

입력 예 1: `[2, 1, 3]` → `true`
입력 예 2: `[5, 1, 4, null, null, 3, 6]` → `false` (4가 5보다 작음)

이 문제는 "직관적인 풀이가 틀린다"는 점에서 시니어 후보를 변별하는 단골 문제다. 먼저 직관적으로 짠 다음 반례를 직접 만들어 보고, 정답 풀이로 넘어가는 흐름을 권한다.

<details>
<summary>풀이 보기</summary>

**잘못된 직관**: "각 노드에서 `node.left.val < node.val < node.right.val`만 보면 된다."
→ 반례: `[5, 1, 6, null, null, 4, 7]`. 노드 6의 왼쪽 자식 4는 6보다 작아서 통과되지만, 4는 루트 5보다도 작으면 안 된다(오른쪽 서브트리에 있으므로). 즉 **인접 비교만으로는 부족**하고, 각 노드는 **상속받은 (min, max) 범위** 안에 있어야 한다.

**접근 1 — 범위 전달 DFS**: 재귀 인자로 (low, high)를 넘기며, 현재 노드 값이 그 범위에 속하는지 본다. 자식으로 내려갈 때 범위를 좁힌다.

**접근 2 — 중위 순회 단조 증가**: BST의 중위 순회는 정렬된 시퀀스다. 직전에 본 값보다 현재 값이 항상 커야 한다.

두 접근 모두 시간 O(n), 공간 O(h). 면접관이 둘 다 알고 있는지 떠보는 경우가 많아서, 둘 다 외워 두는 게 좋다.

**오버플로 주의**: 노드 값에 `Integer.MIN_VALUE` 또는 `Integer.MAX_VALUE`가 들어올 수 있으면 `int` 범위로 비교하면 경계에서 틀린다. `Integer` 박싱 또는 `long`을 쓴다.

```java
import java.util.*;

public class Solution {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int val) { this.val = val; }
    }

    // 접근 1: 범위 전달 DFS
    public static boolean isValidBST(TreeNode root) {
        return validate(root, null, null);
    }

    private static boolean validate(TreeNode node, Integer low, Integer high) {
        if (node == null) return true;
        if (low != null && node.val <= low) return false;
        if (high != null && node.val >= high) return false;
        return validate(node.left, low, node.val)
            && validate(node.right, node.val, high);
    }

    // 접근 2: 중위 순회 + 직전값 비교
    private static Integer prev = null;

    public static boolean isValidBSTInorder(TreeNode root) {
        prev = null;
        return inorder(root);
    }

    private static boolean inorder(TreeNode node) {
        if (node == null) return true;
        if (!inorder(node.left)) return false;
        if (prev != null && node.val <= prev) return false;
        prev = node.val;
        return inorder(node.right);
    }

    public static void main(String[] args) {
        // [2, 1, 3]
        TreeNode t1 = new TreeNode(2);
        t1.left = new TreeNode(1);
        t1.right = new TreeNode(3);
        System.out.println(isValidBST(t1));        // true
        System.out.println(isValidBSTInorder(t1)); // true

        // [5, 1, 4, null, null, 3, 6]
        TreeNode t2 = new TreeNode(5);
        t2.left = new TreeNode(1);
        t2.right = new TreeNode(4);
        t2.right.left = new TreeNode(3);
        t2.right.right = new TreeNode(6);
        System.out.println(isValidBST(t2));        // false
        System.out.println(isValidBSTInorder(t2)); // false

        // 인접 비교만 했을 때 잡히지 않는 반례
        // [5, 1, 6, null, null, 4, 7]
        TreeNode t3 = new TreeNode(5);
        t3.left = new TreeNode(1);
        t3.right = new TreeNode(6);
        t3.right.left = new TreeNode(4);
        t3.right.right = new TreeNode(7);
        System.out.println(isValidBST(t3));        // false
        System.out.println(isValidBSTInorder(t3)); // false
    }
}
```

**라이브에서 짚을 포인트**:
- "처음에 인접 비교만 하는 풀이를 짤 뻔했지만, 반례를 손으로 만들어 보니 깨졌습니다. 그래서 부모로부터 받은 (min, max) 범위를 같이 들고 내려가는 방식으로 바꿨습니다."
- "static 필드 `prev`는 라이브 환경에서 빠르게 짜기 위함이고, 실제 production이라면 호출 사이의 상태 누수를 막기 위해 외부 클래스 인스턴스 변수나 캡슐화된 컨텍스트로 분리하는 편이 안전합니다." — 시니어다운 자기 비판.
- "`Integer`로 받은 이유: `Integer.MIN_VALUE` 노드를 다룰 때 `Long.MIN_VALUE`를 sentinel로 쓰는 트릭 대신, null로 '경계 없음'을 표현하기 위함입니다."

</details>

## 10. 면접 답변 프레이밍

라이브 코딩이 끝난 직후 회고 질문(behavioral)이 따라오는 경우가 많다. 시니어 백엔드 후보로서 답할 때 좋은 프레이밍 예시.

- **"실무에서 트리 구조를 다룬 경험이 있나요?"**
  > "댓글의 부모-자식 관계를 단일 테이블 + parent_id로 다뤘습니다. depth가 깊어지면 N+1이 심하게 터져서, 댓글 1depth만 즉시 로드하고 그 이상은 lazy 로딩으로 분리했습니다. 그 과정에서 BFS 레벨 단위로 prefetch하는 패턴이, 라이브 코딩에서 짠 levelOrder 골격과 같은 사고였습니다."

- **"왜 재귀 대신 반복 구현을 고를 때가 있나요?"**
  > "재귀는 짧고 직관적이지만 트리 깊이에 비례한 호출 스택을 잡습니다. 입력이 사용자 입력에서 오는 경우, 즉 깊이를 신뢰할 수 없는 경우에는 명시적 스택을 써서 OOM 대신 통제 가능한 큐 사이즈로 바꿉니다. 운영 환경에서 안정성이 우선일 때의 트레이드오프입니다."

- **"BFS와 DFS 중 무엇을 먼저 시도하나요?"**
  > "문제 진술에 '레벨', '최단', '가장 가까운' 같은 키워드가 있으면 BFS, '경로 합', '모든 ~를 만족', '서브트리 단위 결과'면 DFS로 갑니다. 키워드만 보고 결정한 뒤, 메모리 폭이 위험해 보이면 그때 다시 검토합니다."

## 11. 라이브 코딩 직전 체크리스트

면접 시작 5분 전 마지막으로 확인할 것.

- [ ] `TreeNode` 클래스 정의를 5초 안에 쓸 수 있다.
- [ ] DFS 재귀의 base case를 항상 `node == null`로 두는 습관이 있다.
- [ ] BFS 레벨 순회 골격(`int size = queue.size()`)을 보지 않고 짤 수 있다.
- [ ] 전위/중위/후위 차이를 한 줄(`add 위치`)로 설명할 수 있다.
- [ ] BST 검증에서 인접 비교 함정을 알고, 범위 전달 또는 중위 순회로 대응할 수 있다.
- [ ] `isBalanced`에서 sentinel 패턴(-1)을 떠올릴 수 있다.
- [ ] `Stack` 대신 `ArrayDeque`를 쓰는 이유를 한 마디로 답할 수 있다.
- [ ] 재귀 깊이 한계와 그 대안(명시적 스택, BFS)을 안다.
- [ ] 입력 가정(빈 트리, 음수, 중복, 노드 수 상한)을 코드 작성 전에 묻는 습관이 있다.
- [ ] 코드 작성 직전에 시간/공간 복잡도를 입으로 말한다.
- [ ] 막혔을 때 "5초만 생각해 볼게요"라고 침묵을 명시화할 수 있다.
- [ ] 자체 테스트 케이스를 빈 트리 / 한쪽 치우친 트리 / 일반 케이스로 항상 3개 이상 만든다.

위 항목 중 무의식적으로 안 되는 게 하나라도 있으면 그 부분을 30분 더 손에 익히고 면접에 들어가는 게 좋다.
