# [초안] Java 라이브 코딩을 위한 Linked List 핵심 패턴 정리

## 왜 지금 Linked List인가

라이브 코딩에서 Linked List가 자주 출제되는 이유는 단순하다. 자료구조의 본질을 화이트보드 한 장 분량으로 검증할 수 있고, 후보자가 포인터/참조를 어떻게 다루는지 그대로 드러나기 때문이다. 배열 문제는 인덱스 산수 실수로 죽지만, Linked List 문제는 "노드를 잘못 잃어버리는" 실수로 죽는다. 면접관 입장에서는 후보자가 (1) 참조의 끊김/이음 순서를 머릿속에서 그리는지, (2) edge case를 자기 입으로 먼저 꺼내는지, (3) 추가 메모리를 쓰지 않고 in-place로 변형할 수 있는지를 단번에 본다.

특히 시니어 백엔드 트랙에서는 알고리즘 풀이 자체보다 **사고 흐름을 말로 풀어내는 능력**이 큰 비중을 차지한다. HackerRank 라이브 환경에서는 코드를 짜는 30분 동안 거의 계속 말을 해야 하는데, Linked List는 그 진행이 자연스럽다. "지금 prev를 잡았고, current.next를 임시 저장한 다음, current.next를 prev로 돌리고…" 같은 narration이 그대로 코드 흐름과 일치한다.

이 문서는 라이브 코딩 직전에 한 번 훑고 들어갈 수 있는 분량으로, 핵심 패턴 4가지(dummy node, slow-fast pointer, reverse, merge)와 실수 패턴, 면접 진행 스크립트, 그리고 실제로 풀어보는 연습 문제 2개로 구성한다.

## 사전 약속: 이 문서가 다루는 노드 정의

이 문서의 모든 코드는 다음 노드 정의를 전제로 한다. LeetCode/HackerRank의 표준 정의와 거의 동일하다.

```java
class ListNode {
    int val;
    ListNode next;
    ListNode() {}
    ListNode(int val) { this.val = val; }
    ListNode(int val, ListNode next) { this.val = val; this.next = next; }
}
```

라이브 코딩에서는 보통 이 클래스가 이미 주어져 있으므로 직접 정의하지 말고, **내가 새 노드를 만들 일이 있는지 / 기존 노드를 재배치만 할 것인지**를 먼저 면접관에게 명시하는 것이 좋다.

## Dummy Node를 쓰는 진짜 이유

Dummy(또는 sentinel) head는 "결과 리스트의 head가 무엇이 될지 모를 때, head 자리를 비워두는 가짜 노드"다. 거의 모든 Linked List 문제에서 가장 큰 골칫거리는 **head가 바뀌는 경우와 안 바뀌는 경우를 분기 처리**해야 한다는 점이다. dummy를 쓰면 이 분기를 통째로 없앨 수 있다.

다음과 같은 상황에서 dummy가 빛난다.

- **새 리스트를 한 노드씩 이어 붙일 때** (merge two sorted lists, 결과 리스트 build-up)
- **head 자체가 삭제될 수 있을 때** (특정 값 삭제, N번째 노드 삭제)
- **앞쪽에 노드를 삽입할 가능성이 있을 때**

규칙은 단순하다. 결과 리스트를 만들거나 head 변경이 가능한 모든 문제에서 일단 dummy를 잡고 시작한다. 그리고 마지막에 `return dummy.next;`로 반환한다. 라이브 코딩에서는 "head가 바뀔 가능성이 있어서 dummy를 두고 시작하겠습니다"라고 한 줄 말하면 그 자체로 점수가 된다.

```java
ListNode dummy = new ListNode(0);
ListNode tail = dummy;
// ... tail.next = newNode; tail = tail.next;
return dummy.next;
```

dummy를 남용해서 안 되는 경우는 **단일 노드 in-place 수정**(예: 값만 바꾸는 작업)이다. 이때는 dummy가 오히려 잡음이 된다.

## Slow-Fast Pointer (Floyd의 토끼와 거북이)

두 포인터를 **같은 시작점에서 출발**시키되 한쪽은 한 칸씩, 다른 쪽은 두 칸씩 이동시킨다. 이 단순한 트릭으로 다음 문제들이 한 번에 해결된다.

| 용도 | 종료 조건 | 결과 |
|------|-----------|------|
| 중간 노드 찾기 | `fast == null \|\| fast.next == null` | slow가 중간 또는 중간 직전 |
| 사이클 탐지 | `fast == slow` 만나면 사이클 존재 | 사이클 시작점은 다시 head에서 출발해 만남 |
| 끝에서 N번째 노드 | fast를 먼저 N칸 전진 후 같이 이동 | slow가 끝에서 N번째 직전 |

중간 노드 찾기는 짝수 길이일 때 "두 중간 중 어느 쪽을 원하는가"가 항상 함정이다. 면접관에게 "리스트 길이가 짝수면 두 중간 중 뒤쪽을 반환하는 게 맞나요?"를 반드시 묻고 들어간다.

```java
ListNode slow = head, fast = head;
while (fast != null && fast.next != null) {
    slow = slow.next;
    fast = fast.next.next;
}
// slow는 짝수 길이일 때 뒤쪽 중간을 가리킨다.
// 앞쪽 중간을 원하면: while (fast.next != null && fast.next.next != null)
```

사이클 탐지에서 자주 나오는 추가 질문은 "사이클이 시작되는 노드를 반환하라"이다. 이건 수학적으로, slow와 fast가 만난 지점에서 한 포인터를 head로 옮기고 둘 다 한 칸씩 이동하면 다시 만나는 지점이 사이클 시작이라는 사실을 외워두는 게 빠르다.

## Reverse Linked List 정석

Reverse는 모든 Linked List 문제의 도장 같은 패턴이다. iterative로 외우고, recursive는 추가로 보여줄 수 있으면 좋다.

```java
ListNode reverse(ListNode head) {
    ListNode prev = null;
    ListNode curr = head;
    while (curr != null) {
        ListNode next = curr.next;  // 1. 다음 노드 백업
        curr.next = prev;            // 2. 방향 반전
        prev = curr;                 // 3. prev 한 칸 전진
        curr = next;                 // 4. curr 한 칸 전진
    }
    return prev;
}
```

이 4줄의 순서가 살짝만 어긋나도 리스트가 끊어진다. 라이브 코딩에서는 4줄을 적은 뒤에 입으로 다시 한 번 "next 저장 → 방향 뒤집기 → prev 이동 → curr 이동"이라고 짚어주는 것이 안전하다.

부분 reverse(예: m번째 ~ n번째만 뒤집기) 문제도 같은 골격에 dummy + "before" 포인터가 추가된다고 생각하면 된다.

## Merge Two Sorted Lists 정석

```java
ListNode merge(ListNode a, ListNode b) {
    ListNode dummy = new ListNode(0);
    ListNode tail = dummy;
    while (a != null && b != null) {
        if (a.val <= b.val) {
            tail.next = a; a = a.next;
        } else {
            tail.next = b; b = b.next;
        }
        tail = tail.next;
    }
    tail.next = (a != null) ? a : b;  // 남은 꼬리 통째로 연결
    return dummy.next;
}
```

두 가지 포인트를 면접관에게 설명한다. 첫째, 마지막 줄에서 남은 한쪽을 통째로 이어 붙이는 게 핵심이라는 점. 둘째, `<=`를 써서 동률일 때 안정적(stable)으로 처리한다는 점. K개 리스트 병합으로 확장되면 PriorityQueue 또는 분할 정복으로 가는데, 그 확장 가능성도 한 마디 언급해두면 시니어다움이 묻어난다.

## 흔한 버그 패턴

면접관이 가장 자주 잡아내는 실수들이다.

1. **`while (curr.next != null)`로 시작했는데 head가 null인 경우를 잊는 것.** 입력이 빈 리스트면 곧바로 NPE.
2. **next를 임시 저장하지 않고 끊어버리기.** `curr.next = prev;` 직후 `curr = curr.next;`를 그대로 쓰면 prev로 거슬러 올라가게 된다.
3. **dummy를 만들었는데 return을 head로 하는 것.** `return dummy.next`가 맞다.
4. **slow-fast에서 fast의 null 체크를 한쪽만 하는 것.** `fast.next.next`를 평가하는 순간 `fast.next`가 null이면 NPE.
5. **삭제 시 prev를 잃어버리는 것.** 단방향 리스트에서 노드를 삭제하려면 항상 "지울 노드의 직전 노드"를 들고 있어야 한다. dummy가 이걸 자연스럽게 해결해준다.
6. **사이클이 있는 입력을 무한 루프로 도는 것.** 사이클 가능성이 명시된 문제에서는 슬로우-패스트로 사전에 차단하거나 visited 처리를 한다.
7. **재귀 reverse에서 base case를 `head == null`만 두고 `head.next == null`을 빠뜨리는 것.** 둘 다 검사해야 한다.

라이브 코딩에서 이 7가지 중 2-3개를 **자기 입으로 먼저 언급하고 방어**하면 코드를 안 쓴 시점에서 이미 합격선에 가깝다.

## 라이브 면접 진행 스크립트

HackerRank처럼 화면 공유 + 음성 채널 환경에서는 다음 5단계를 지킨다.

1. **문제 이해 재진술**: "입력은 단방향 Linked List이고, 빈 리스트 가능, 노드 값 범위는 …, 정답은 새 리스트를 만들지 않고 in-place로 가능한가요?"
2. **edge case 선제 나열**: 빈 리스트, 노드 1개, head 변경 가능성, 중복값, 사이클 가능성. 이걸 면접관이 묻기 전에 내가 먼저 꺼낸다.
3. **접근 방식을 한 문장으로**: "two pointer로 한 번 순회하며 dummy를 두고 결과 리스트를 만들겠습니다. 시간 O(n), 공간 O(1)입니다."
4. **코드 작성 중 narration**: 변수 의미 한 번, 루프 종료 조건 한 번, 가장 까다로운 라인은 두 번 짚는다.
5. **dry-run**: 작성 직후 입력 예시 1개를 직접 손으로 따라가며 출력이 맞는지 확인한다. 이 단계를 빠뜨리면 사소한 off-by-one이 그대로 제출된다.

면접관이 "왜 dummy를 썼나요?"라고 물으면 "head 변경 분기를 없애기 위해서입니다"라고 한 줄로 답한다. 길게 설명하지 않는다.

## 로컬 연습 환경

라이브 면접 직전에는 IDE 자동완성을 끄고 빈 화면에서 코드를 쓰는 연습을 한다. 다음 셋업이면 충분하다.

```bash
mkdir -p ~/scratch/linked-list && cd ~/scratch/linked-list
# Solution.java 한 파일에 ListNode + main + 헬퍼 두기
javac Solution.java && java Solution
```

헬퍼는 두 개만 둔다. 배열을 받아 리스트로 만드는 `build(int[])`, 리스트를 출력하는 `print(ListNode)`. 이 두 개로 모든 문제의 입출력을 검증할 수 있다.

```java
static ListNode build(int[] a) {
    ListNode dummy = new ListNode(0);
    ListNode tail = dummy;
    for (int v : a) { tail.next = new ListNode(v); tail = tail.next; }
    return dummy.next;
}
static void print(ListNode head) {
    StringBuilder sb = new StringBuilder("[");
    while (head != null) {
        sb.append(head.val);
        if (head.next != null) sb.append(", ");
        head = head.next;
    }
    System.out.println(sb.append("]"));
}
```

연습할 때는 항상 입력 케이스를 4개 준비한다: 빈 리스트, 노드 1개, 짝수 길이, 홀수 길이. 이 4개가 통과하지 못하는 코드는 면접에서도 깨진다.

## 연습 문제 1 (Easy) — Reverse Linked List

**문제**: 단방향 Linked List의 head가 주어진다. 리스트를 뒤집어 새 head를 반환하라. 추가 자료구조를 쓰지 말고 in-place로 풀어라.

**입력 예**
- `[1, 2, 3, 4, 5]` → `[5, 4, 3, 2, 1]`
- `[1]` → `[1]`
- `[]` → `[]`

먼저 시간을 재고 종이/에디터에서 직접 풀어본 뒤 아래 풀이를 본다.

<details>
<summary>풀이 보기</summary>

**접근**: 세 포인터(prev, curr, next)로 한 번 순회한다. 각 단계에서 curr.next 방향만 prev로 뒤집는다. 시간 O(n), 공간 O(1).

**핵심 narration**: "next를 먼저 백업해야 한다. 안 그러면 curr.next = prev로 덮어쓰는 순간 다음 노드로 못 간다."

**edge case**: head가 null이면 즉시 null 반환. 노드 1개면 prev=null, curr=head로 시작해 한 번 루프 돌고 prev(=원래 head) 반환. 둘 다 같은 코드로 자연스럽게 처리된다.

```java
public class Solution {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode reverse(ListNode head) {
        ListNode prev = null;
        ListNode curr = head;
        while (curr != null) {
            ListNode next = curr.next;
            curr.next = prev;
            prev = curr;
            curr = next;
        }
        return prev;
    }

    public static void main(String[] args) {
        int[][] cases = { {1,2,3,4,5}, {1}, {} };
        for (int[] c : cases) {
            ListNode head = build(c);
            ListNode r = reverse(head);
            print(r);
        }
    }

    static ListNode build(int[] a) {
        ListNode dummy = new ListNode(0);
        ListNode tail = dummy;
        for (int v : a) { tail.next = new ListNode(v); tail = tail.next; }
        return dummy.next;
    }

    static void print(ListNode head) {
        StringBuilder sb = new StringBuilder("[");
        while (head != null) {
            sb.append(head.val);
            if (head.next != null) sb.append(", ");
            head = head.next;
        }
        System.out.println(sb.append("]"));
    }
}
```

**확장 질문 대비**: "재귀로 풀어보라"고 하면 base case는 `head == null || head.next == null`, 재귀 호출 결과를 newHead로 받은 뒤 `head.next.next = head; head.next = null;` 한 뒤 newHead 반환. 이 두 줄의 의미를 입으로 말할 수 있어야 한다.

</details>

## 연습 문제 2 (Medium) — Remove Nth Node From End

**문제**: 단방향 Linked List와 정수 n이 주어진다. 끝에서 n번째 노드를 한 번의 순회로 제거하고 head를 반환하라. n은 항상 유효(1 ≤ n ≤ 리스트 길이)하다고 가정한다.

**입력 예**
- `head = [1,2,3,4,5], n = 2` → `[1,2,3,5]`
- `head = [1], n = 1` → `[]`
- `head = [1,2], n = 1` → `[1]`
- `head = [1,2], n = 2` → `[2]`

이 문제는 dummy의 가치를 가장 잘 보여주는 클래식이다. n이 리스트 길이와 같으면 head 자체가 삭제 대상이다.

<details>
<summary>풀이 보기</summary>

**접근**: dummy를 만든 뒤 fast를 dummy에서 n+1칸 전진시킨다. 그 다음 slow=dummy로 두고 fast가 null이 될 때까지 둘이 같이 한 칸씩 이동한다. 이러면 slow는 "삭제할 노드의 직전"에 위치한다. 그 자리에서 `slow.next = slow.next.next`로 단번에 끊는다. 시간 O(L), 공간 O(1), 한 번의 순회만으로 끝난다.

**왜 dummy인가**: head가 삭제 대상일 수 있다. dummy를 두지 않으면 "head 삭제 vs 중간 삭제" 분기를 따로 짜야 한다. dummy가 있으면 두 경우가 동일한 코드 경로로 처리된다.

**왜 fast를 n+1칸 전진시키는가**: slow가 "삭제 대상의 직전"에 도달해야 하기 때문이다. fast가 n칸이면 slow는 삭제 대상에 도달한다 — 그러면 끊을 수 없다. n+1칸이어야 직전에 멈춘다.

**dry-run** (`[1,2,3,4,5], n=2`)
- dummy → 1 → 2 → 3 → 4 → 5
- fast를 dummy에서 3칸 전진: fast = 노드(2)? 아니다, dummy → 1 → 2 → 3 이므로 fast = 노드(3).
- slow = dummy.
- 함께 이동: (slow=1, fast=4) → (slow=2, fast=5) → (slow=3, fast=null) 멈춤.
- slow.next = slow.next.next → 노드(3).next = 노드(5). 결과 `[1,2,3,5]`.

```java
public class Solution {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode removeNthFromEnd(ListNode head, int n) {
        ListNode dummy = new ListNode(0);
        dummy.next = head;
        ListNode fast = dummy;
        ListNode slow = dummy;

        for (int i = 0; i < n + 1; i++) {
            fast = fast.next;
        }
        while (fast != null) {
            fast = fast.next;
            slow = slow.next;
        }
        slow.next = slow.next.next;
        return dummy.next;
    }

    public static void main(String[] args) {
        int[][] inputs = { {1,2,3,4,5}, {1}, {1,2}, {1,2} };
        int[] ns =        {       2,       1,     1,     2 };
        for (int i = 0; i < inputs.length; i++) {
            ListNode head = build(inputs[i]);
            ListNode r = removeNthFromEnd(head, ns[i]);
            print(r);
        }
    }

    static ListNode build(int[] a) {
        ListNode dummy = new ListNode(0);
        ListNode tail = dummy;
        for (int v : a) { tail.next = new ListNode(v); tail = tail.next; }
        return dummy.next;
    }

    static void print(ListNode head) {
        StringBuilder sb = new StringBuilder("[");
        while (head != null) {
            sb.append(head.val);
            if (head.next != null) sb.append(", ");
            head = head.next;
        }
        System.out.println(sb.append("]"));
    }
}
```

**자주 깨지는 버그**
- `for (int i = 0; i < n; i++)`로 잘못 써서 fast를 n칸만 전진시키는 경우 → slow가 삭제 대상 자리에 멈춰 끊을 수 없다.
- dummy 없이 head부터 시작해서 head 삭제 케이스에서 NPE.
- 두 번 순회(길이 측정 후 다시 이동)하는 풀이를 제출하면 정답은 맞지만 "한 번의 순회로"라는 follow-up에서 다시 짜야 한다. 처음부터 two-pointer로 가는 게 안전하다.

</details>

## 면접 답변 프레이밍

면접관이 "Linked List 잘 다루세요?"처럼 열린 질문을 던지면 다음 골격으로 답한다.

> "단방향 Linked List를 다룰 때 저는 항상 두 가지 도구를 먼저 떠올립니다. 첫째, head가 변할 가능성이 있는 모든 문제에서는 dummy node를 두고 시작합니다. 분기를 줄이기 위해서입니다. 둘째, 길이를 모르거나 끝에서부터 세야 할 때는 slow-fast pointer로 한 번의 순회로 해결합니다. Reverse는 prev/curr/next 세 포인터 패턴을 외워두고, Merge는 dummy + tail 누적으로 풉니다. 라이브 코딩에서는 코드를 짜기 전에 빈 리스트, 노드 1개, head 삭제 가능성, 사이클 가능성을 먼저 면접관과 합의하고 들어가는 편입니다."

이 답변은 30초 안에 끝나고, 후속 질문(예: "사이클은 어떻게 검출하시나요?")으로 자연스럽게 이어진다. 시니어 트랙에서는 "왜 이 자료구조를 굳이 골랐는가"가 따라오는데, 실무에서는 보통 ArrayList/Deque로 대체된다는 점을 솔직히 말하고, Linked List 자체의 활용은 LRU 캐시(LinkedHashMap), 메시지 큐의 in-memory buffer, GC-friendly한 객체 풀 정도로 좁게 답변한다.

## 마지막 체크리스트

라이브 코딩 들어가기 직전 60초 동안 읽는 점검표.

- [ ] 입력이 null/빈 리스트일 때 코드가 NPE 없이 끝나는가
- [ ] 노드 1개일 때 정상 동작하는가
- [ ] head가 바뀔 가능성이 있다면 dummy를 두었는가
- [ ] reverse 4줄 순서(next 백업 → 뒤집기 → prev 이동 → curr 이동)를 외우고 있는가
- [ ] slow-fast의 종료 조건 `fast != null && fast.next != null`을 손가락이 자동으로 치는가
- [ ] 삭제 작업에서 "직전 노드"를 잃지 않게 잡고 있는가
- [ ] 코드 작성 후 dry-run을 입력 1개로 직접 따라갔는가
- [ ] 시간 복잡도 / 공간 복잡도를 한 줄로 말할 준비가 되었는가
- [ ] follow-up("재귀로 다시", "한 번의 순회로", "사이클 있을 때") 중 적어도 하나에 즉답할 수 있는가

이 9개 중 7개 이상에 자신 있게 체크할 수 있다면, Linked List 라이브 코딩에서 떨어지지 않는다. 떨어지는 경우는 거의 항상 dummy를 안 두거나 next를 백업하지 않은 데서 온다.
