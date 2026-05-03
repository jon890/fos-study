# [초안] Trie 라이브 코딩 완전 정복 - prefix 검색 자료구조를 손으로 짜는 법

## 왜 Trie를 라이브 코딩 단골로 만나게 되는가

라이브 코딩 면접에서 Trie가 자주 등장하는 이유는 단순하다. 한 자료구조를 직접 손으로 만들면서, 시간/공간 trade-off, 자료구조 선택 근거, 엣지 케이스 처리, 코드 가독성을 한 화면 안에 모두 보여줄 수 있기 때문이다. HackerRank나 코드시그널 같은 라이브 코딩 환경, 그리고 사내 시스템의 화이트보드 인터뷰에서 Trie 변형 문제는 "자동완성", "사전 탐색", "IP 라우팅 prefix 매칭", "T9 입력기"라는 실무 맥락과 함께 출제된다.

면접관 입장에서 Trie는 한 가지 더 매력이 있다. HashMap이나 정렬+이분탐색으로도 비슷한 일을 할 수 있는데, "왜 Trie를 골랐는가"를 묻는 순간 지원자의 자료구조 감각이 드러난다. prefix 검색이 뜨거운 경로(hot path)인지, 사전이 정적인지 동적인지, 문자 집합 크기가 얼마인지 — 이 질문에 답하지 못하면 외운 코드를 쓰는 사람으로 보이고, 답할 수 있으면 트리 구조 위에서 trade-off를 사고하는 백엔드 엔지니어로 보인다.

이 문서는 시니어 백엔드 관점에서 Trie를 다음 흐름으로 다룬다. 핵심 개념과 메모리 모델 → Java로 자주 쓰는 두 가지 구현 패턴 → 면접에서 자주 무너지는 구현 버그 → 라이브 코딩에서 사고를 푸는 말하기 순서 → 실제로 직접 풀어보는 문제 두 개. 마지막 두 문제는 풀이와 전체 코드를 details/summary 블록으로 가려두었으므로, 코드를 보기 전에 반드시 직접 손으로 짜본 뒤 펼치기를 권한다.

## Trie의 본질 - 트리에 문자를 분산 저장한 prefix 인덱스

Trie(트라이, prefix tree, digital tree)는 문자열 집합을 트리에 분산 저장하는 자료구조다. 노드 자체는 문자를 담지 않고, **부모에서 자식으로 가는 간선이 한 글자를 의미**한다. 루트에서 어떤 노드까지 내려온 경로의 글자들을 이어 붙이면 그 노드가 표현하는 prefix가 된다. 그 노드에 "여기서 단어가 끝났다"는 플래그(`isEnd`, `isWord`, `terminal`)를 두면 단어 종결을 표시할 수 있다.

핵심은 **prefix가 같으면 노드를 공유**한다는 점이다. `car`, `card`, `care`, `cargo`를 넣으면 `c → a → r`까지는 같은 노드 세 개를 공유하고, 그 다음에서 `d`, `e`, `g` 가지가 갈라진다. 이 공유 덕분에 prefix 기반 질의가 압도적으로 빨라진다.

복잡도는 단어 길이를 L, 사전에 들어 있는 단어 수를 N, 알파벳 크기를 σ라고 할 때 다음과 같다.

- `insert(word)`: O(L)
- `search(word)`: O(L)
- `startsWith(prefix)`: O(L) — prefix 길이만큼만 내려가면 끝
- 공간: 최악 O(N · L · σ) (배열형), 보통은 HashMap 사용 시 실제 사용한 간선 수만큼

여기서 중요한 통찰은 비교 대상이다. HashSet도 단어 단위 검색은 O(L) 해시 계산 + O(L) 비교라서 점근적으로 비슷하다. 하지만 HashSet으로는 **prefix로 시작하는 모든 단어 나열**, **공통 최장 prefix**, **사전순 정렬된 자동완성 후보**, **streaming 입력에 대한 점진적 매칭**을 효율적으로 못 한다. Trie의 진짜 가치는 단일 검색이 아니라 prefix 위에 얹은 부가 연산이라는 점을 면접에서 반드시 말해야 한다.

## 노드 메모리 - 배열 vs HashMap, 어떤 trade-off를 골라야 하는가

Trie 노드의 자식 표현 방식은 라이브 코딩에서 가장 먼저 결정해야 할 설계 포인트다. 크게 두 갈래다.

**고정 배열 방식 (`TrieNode[] children = new TrieNode[26]`)**
- 문자 집합이 작고 고정일 때(`a`–`z` 26개, ASCII 소문자) 가장 빠르다.
- 인덱스 계산이 `c - 'a'` 한 번이라 분기 예측에 유리하고 캐시 친화적이다.
- 단점은 명확하다. 한 노드마다 26개의 참조 슬롯을 잡으므로, 단어가 적고 트리 깊이가 깊으면 상당량의 메모리를 빈 슬롯으로 낭비한다. 영어 단어 100만 개 정도까지는 서버 메모리에서 충분히 받아들일 수 있다.

**HashMap 방식 (`Map<Character, TrieNode> children = new HashMap<>()`)**
- 유니코드, 한글, 다국어, 임의 문자, 큰 σ를 다룰 때 사실상 강제된다.
- 노드당 메모리는 실제 자식 수에만 비례하므로 sparse한 사전에 유리하다.
- 단점은 상수 factor다. HashMap의 박싱(`Character`), 해시 계산, 캐시 미스 때문에 배열보다 보통 2~5배 느리다.

라이브 코딩에서는 문제 제약을 먼저 읽고 결정한다. "소문자 영어"가 명시되면 거의 무조건 배열형으로 간다. 코드량이 적고 버그 가능성이 낮으며 면접관이 보기에 명료하다. 반대로 "임의의 문자열", "유니코드", "한글 자모"가 등장하면 HashMap 기반으로 가야 한다. 어떤 선택을 하든 면접관에게 한 줄로 근거를 말하는 게 핵심이다. "문자 집합이 소문자 26개로 고정이니 캐시 친화적인 배열형으로 갑니다", "유니코드 가능성이 있어 HashMap을 쓰겠습니다, 대신 단일 문자 검색에 상수 factor가 더 듭니다"처럼.

여기서 한 단계 더 들어간 변형은 **압축 Trie(Radix tree, Patricia trie)**다. 자식이 하나뿐인 직선 경로를 한 노드로 압축해 메모리를 더 줄인다. Linux 라우팅 테이블, Redis Streams 내부 인덱스에서 쓰인다. 라이브 코딩에서 직접 짤 일은 거의 없지만, "왜 그냥 Trie를 안 쓰고 압축 Trie를 쓸까요"라는 follow-up이 들어왔을 때 메모리 압력 때문이라고 답할 수 있어야 한다.

## insert / search / startsWith 구현 패턴

라이브 코딩에서 안전하게 통용되는 표준 형태가 있다. 처음 보면 어색해도, 한 번 손에 익으면 5분 안에 막힘없이 짤 수 있어야 한다. 아래는 영문 소문자 가정의 배열형 구현이다.

```java
class Trie {
    private static class Node {
        Node[] next = new Node[26];
        boolean end;
    }

    private final Node root = new Node();

    public void insert(String word) {
        Node cur = root;
        for (int i = 0; i < word.length(); i++) {
            int idx = word.charAt(i) - 'a';
            if (cur.next[idx] == null) {
                cur.next[idx] = new Node();
            }
            cur = cur.next[idx];
        }
        cur.end = true;
    }

    public boolean search(String word) {
        Node node = walk(word);
        return node != null && node.end;
    }

    public boolean startsWith(String prefix) {
        return walk(prefix) != null;
    }

    private Node walk(String s) {
        Node cur = root;
        for (int i = 0; i < s.length(); i++) {
            int idx = s.charAt(i) - 'a';
            if (cur.next[idx] == null) return null;
            cur = cur.next[idx];
        }
        return cur;
    }
}
```

이 구조에서 면접관이 보고 싶어 하는 디테일은 다음 네 가지다.

1. `walk` 같은 보조 메서드로 `search`와 `startsWith`의 공통 경로를 통합했다. 중복 제거를 자연스럽게 보여준다.
2. `end` 플래그와 "노드가 존재함"을 구분한다. `search("car")`가 사전에 `card`만 있을 때 false여야 하는 핵심.
3. `final Node root`로 루트를 보호하고, 외부에서 노드 클래스가 새지 않게 `private static class`로 캡슐화했다.
4. `int idx = c - 'a'`를 한 번만 계산해서 가독성을 높였다.

HashMap 변형이 필요하면 다음과 같이 바꾼다. 대규모 면접에서는 `getOrDefault`보다 `computeIfAbsent`를 쓰는 편이 코드가 더 명료하다.

```java
Map<Character, Node> children = new HashMap<>();
// insert
cur = cur.children.computeIfAbsent(c, k -> new Node());
// search
Node nxt = cur.children.get(c);
if (nxt == null) return null;
cur = nxt;
```

`delete`까지 요구되는 경우는 드물지만, 묻는다면 재귀로 풀면서 "이 노드가 다른 단어의 prefix가 아니고, 자식도 없을 때만 부모에서 끊는다"고 설명한다. 라이브에서는 시간 압박이 크므로, 묻기 전에는 굳이 짜지 않는다.

## 문자 집합 가정 - 면접에서 가장 먼저 확인해야 할 한 가지

Trie 라이브 코딩에서 가장 비싼 실수는 코드 버그가 아니라 **가정 누락**이다. 다음 질문을 면접관에게 30초 안에 던져야 한다.

- 입력 문자 집합은 무엇인가? 소문자 영어만? 대소문자 섞여 있는가? 숫자/공백/유니코드도 들어오는가?
- 빈 문자열 입력을 받아야 하는가? 받아야 한다면 `insert("")`는 루트의 `end`를 true로 만든다.
- 같은 단어가 여러 번 들어오면? 멱등하게 처리할 것인가, count를 들 것인가? 자동완성 랭킹이 필요하면 노드에 `int frequency`를 들어야 한다.
- 단어 최대 길이와 사전 크기 상한은? 메모리 추정 근거.
- 대소문자 통일 정책은? 입력 단계에서 `toLowerCase()`로 정규화할지, Trie가 모르게 둘지.

이 질문 다섯 개를 던지는 것만으로도 다른 지원자와 구분된다. 특히 한국 IT 회사 면접에서 한글이 등장할 가능성을 묻는 게 좋다. 한글 자모로 분해해서 넣을지, 음절(가, 나, 다 …) 단위로 넣을지에 따라 σ가 19~67(자모)에서 11,172(완성형 음절)까지 차이가 난다. 음절 단위면 배열 26은 절대 안 되고 HashMap이 강제된다.

## 구현하면서 흔히 무너지는 버그들

라이브 코딩에서 같은 패턴의 버그가 반복적으로 나타난다.

**버그 1. `end` 플래그를 빠뜨려서 prefix와 단어를 구분하지 못한다.**
`insert("apple")`만 한 뒤 `search("app")`가 true로 나오면 망한 것이다. `search`는 마지막 노드의 `end`를 검사해야 하고, `startsWith`는 그렇지 않다. 두 메서드의 마지막 줄이 달라야 한다.

**버그 2. 같은 prefix를 가진 단어를 덮어쓴다.**
재귀 구현에서 가끔 보이는 실수다. 부모에서 자식을 새로 만들 때 `cur.next[idx] = new Node()`를 무조건 실행해버리면 기존 단어의 가지가 통째로 날아간다. 항상 `if (cur.next[idx] == null)` 체크가 선행되어야 한다.

**버그 3. 인덱스 계산에서 음수 또는 범위 초과.**
`c - 'a'`는 입력이 소문자 영문이라는 가정 위에서만 안전하다. 대문자나 숫자가 섞이면 음수 인덱스 또는 26 이상 값이 나와 `ArrayIndexOutOfBoundsException`이 터진다. 입력 검증을 어디서 할지 한 번은 명시해야 한다.

**버그 4. null 체크 누락으로 NPE.**
`startsWith`나 `search`에서 중간 노드가 null인데 다음 줄에서 `cur.next[idx]`를 또 따라가면 NPE다. early return 패턴이 가장 안전하다.

**버그 5. 빈 문자열 처리.**
`insert("")`나 `search("")`가 들어왔을 때 의도된 동작을 정의하지 않으면 결과가 환경마다 다르게 보인다. 사전적 정의로는 빈 문자열도 prefix이므로 `startsWith("")`는 true가 자연스럽다.

**버그 6. delete에서 공유 prefix를 끊어버린다.**
`apple`, `app`이 모두 들어 있는 상태에서 `apple`을 지운다고 `app` 노드까지 잘라내면 `app` 검색이 깨진다. delete는 반드시 "자식이 모두 비고, 이 노드 자체가 단어가 아닐 때"만 부모에서 끊는다.

**버그 7. 문자 집합을 바꿨는데 노드 배열 크기를 안 바꾼다.**
σ를 26으로 두고 알파벳 + 숫자를 받으면 배열이 작아 깨진다. 반대로 σ를 256으로 키워두고 영문 소문자만 받으면 메모리만 낭비된다.

이 일곱 가지를 머리에 새긴 채로 짜면 라이브 코딩에서 디버깅으로 시간을 쓰는 일이 거의 사라진다.

## 라이브에서 사고 흐름을 말로 푸는 순서

HackerRank 화면 공유 면접은 코드 정확성만큼 사고 흐름의 명료함이 평가된다. 다음 순서로 말하면 안전하다.

1. **문제 재진술과 입출력 가정 확인**: "검색 함수가 prefix 검색까지 요구하는지, 단어 종결만 보는지부터 확인하겠습니다."
2. **자료구조 선택 근거**: "문자 집합이 소문자 영어로 고정되어 있고 prefix 질의가 핵심이라 Trie가 적합합니다. HashSet으로는 prefix 질의 시 전체 집합 스캔이 필요합니다."
3. **메모리 모델 선택**: "노드 자식은 26 크기 배열로 갑니다. σ가 작고 캐시 친화적입니다."
4. **API 설계**: "`insert(String)`, `search(String)`, `startsWith(String)`을 두고, 후자 둘은 walk 헬퍼를 공유합니다."
5. **엣지 케이스 선제 언급**: "빈 문자열은 루트의 end로 처리하고, 입력은 소문자 영문 가정이므로 검증은 호출자에 맡기겠습니다."
6. **구현**: 위 표준 패턴 그대로.
7. **테스트 케이스 직접 호출**: 빈 문자열, 같은 prefix를 공유하는 단어, 단어가 아닌 prefix 검색, 사전에 없는 단어. 면접관이 시키기 전에 먼저 돌린다.
8. **복잡도 정리**: 시간 O(L), 공간 O(N·L·σ) 최악, 실측은 사전이 sparse하면 훨씬 적음.
9. **확장 토의**: 압축 Trie, 자동완성에 빈도수, Aho-Corasick으로 다중 패턴 매칭까지 자연스럽게 연결한다.

이 흐름의 핵심은 **트레이드오프를 입 밖으로 내는 것**이다. "왜 HashMap 안 썼나요"라는 질문이 나오기 전에 내가 먼저 "이 가정에서는 배열이 더 낫다, 가정이 바뀌면 HashMap이 낫다"고 말한다.

## 로컬 연습 환경 - 5분 만에 세팅

라이브 코딩 환경을 흉내 내려면 외부 라이브러리 없이 JDK만으로 충분하다. JDK 21 이상을 권하지만 17부터 무리 없이 동작한다.

```
mkdir -p ~/work/trie-live && cd ~/work/trie-live
javac --version   # 17 이상이면 OK
```

`Trie.java` 한 파일에 `Trie` 클래스와 `main`을 함께 넣고 `javac Trie.java && java Trie`로 돌리는 게 라이브 코딩 환경과 가장 유사하다. JUnit이나 Maven을 끌어오지 않고 `assert`나 `if (!ok) throw new AssertionError()`만으로 테스트하면 된다. `java -ea Trie`로 assertion을 켜는 것을 잊지 말자.

면접 직전에는 다음 사이클을 5번 반복한다. (1) 빈 파일에서 시작, (2) 표준 Trie를 6분 안에 짜기, (3) 빈 입력/공유 prefix/존재하지 않는 단어로 직접 검증, (4) 메모리 추정을 입으로 말하기, (5) 손으로 그린 트리 그림과 코드 일치 확인. 이 5번을 마치면 어떤 변형 문제가 나와도 출발선에서 흔들리지 않는다.

## 실전 연습 문제 두 개

아래 두 문제는 실제 라이브 코딩에서 출제되는 형태에 가깝게 다듬었다. **반드시 details를 펼치기 전에 직접 짜보라.** 라이브 코딩 실력은 코드를 읽는 시간이 아니라 자기 손으로 막히는 지점을 통과하는 시간으로 늘어난다. 시간 제한은 쉬움 12분, 중간 25분을 권한다.

### 문제 1 (쉬움) — 기본 Trie 구현

`Trie` 클래스를 구현한다. 입력 단어는 모두 영문 소문자(`a`–`z`)로만 이루어져 있고 길이는 1 이상 1000 이하, 단어 수는 최대 3·10^4개다. 다음 세 메서드를 지원해야 한다.

- `void insert(String word)` — 단어를 사전에 추가한다. 같은 단어가 여러 번 들어와도 결과는 동일해야 한다.
- `boolean search(String word)` — 정확히 그 단어가 사전에 있으면 true.
- `boolean startsWith(String prefix)` — 사전의 어떤 단어든 이 prefix로 시작하면 true. 빈 문자열 prefix는 true로 처리한다.

테스트 시나리오로는 다음을 직접 호출해 본다. `insert("apple")` → `search("apple")` true, `search("app")` false, `startsWith("app")` true, `insert("app")` → `search("app")` true, `startsWith("")` true.

<details>
<summary>문제 1 풀이 보기 (직접 짜본 뒤에 펼쳐주세요)</summary>

접근 방식. 문자 집합이 소문자 영어 26개로 고정이라 캐시 친화적인 26 크기 배열형 노드를 선택한다. `search`와 `startsWith`는 마지막 줄만 다르므로 `walk(String)` 헬퍼로 공통 경로를 분리해 가독성과 중복 제거를 동시에 잡는다. `end` 플래그로 단어 종결 여부를 표현하고, 노드 존재만으로 단어를 판정하지 않도록 분리한다. 빈 문자열의 경우 `walk("")`는 루트를 그대로 반환하고, 루트의 `end`는 기본 false이므로 `search("")`는 false가 자연스럽다. `startsWith("")`는 walk 결과가 null이 아니므로 자동으로 true가 된다. 시간 복잡도는 모든 연산 O(L), 공간 복잡도는 사전에 들어간 모든 단어의 고유 prefix 노드 수에 비례하며 최악은 O(N·L) 노드, 노드당 26 슬롯이다.

```java
public class Trie {

    private static final int SIGMA = 26;

    private static final class Node {
        final Node[] next = new Node[SIGMA];
        boolean end;
    }

    private final Node root = new Node();

    public void insert(String word) {
        Node cur = root;
        for (int i = 0; i < word.length(); i++) {
            int idx = word.charAt(i) - 'a';
            if (cur.next[idx] == null) {
                cur.next[idx] = new Node();
            }
            cur = cur.next[idx];
        }
        cur.end = true;
    }

    public boolean search(String word) {
        Node node = walk(word);
        return node != null && node.end;
    }

    public boolean startsWith(String prefix) {
        return walk(prefix) != null;
    }

    private Node walk(String s) {
        Node cur = root;
        for (int i = 0; i < s.length(); i++) {
            int idx = s.charAt(i) - 'a';
            Node nxt = cur.next[idx];
            if (nxt == null) return null;
            cur = nxt;
        }
        return cur;
    }

    public static void main(String[] args) {
        Trie t = new Trie();
        t.insert("apple");
        require(t.search("apple"), "apple should exist");
        require(!t.search("app"), "app not yet inserted");
        require(t.startsWith("app"), "app is a prefix of apple");
        require(!t.search("apples"), "apples not inserted");
        t.insert("app");
        require(t.search("app"), "app inserted");
        require(t.startsWith(""), "empty prefix is always true");
        require(!t.search(""), "empty string was never inserted");
        t.insert("app");
        require(t.search("app"), "duplicate insert is idempotent");
        System.out.println("ok");
    }

    private static void require(boolean cond, String msg) {
        if (!cond) throw new AssertionError(msg);
    }
}
```

면접에서 강조할 포인트. (1) `walk` 헬퍼로 중복 제거. (2) `end` 분리로 prefix와 단어 구분. (3) 빈 문자열 동작을 명시적으로 정의. (4) 같은 단어 중복 삽입이 멱등하다. (5) σ=26 가정과 그 근거를 코드 상수로 추출.

</details>

### 문제 2 (중간) — 자동완성 후보 사전순 상위 K개

대화형 검색창의 백엔드를 시뮬레이션한다. 단어 사전과 빈도수가 주어지고, 사용자가 prefix를 입력할 때마다 그 prefix로 시작하는 사전 단어들 중에서 **빈도 내림차순, 빈도가 같으면 사전순 오름차순**으로 상위 K개를 반환한다.

API는 다음과 같다.

- `void add(String word, int freq)` — 단어와 빈도를 더한다. 같은 단어가 다시 들어오면 빈도를 누적한다.
- `List<String> suggest(String prefix, int k)` — prefix로 시작하는 단어 중 위 정렬 기준 상위 k개. prefix로 시작하는 단어가 k 미만이면 있는 만큼만 반환한다. prefix가 사전에 없으면 빈 리스트를 반환한다.

제약: 단어는 소문자 영어, 길이 1~50, 사전 크기 최대 5·10^4, `suggest` 호출은 최대 10^4번, k는 최대 10. 단어가 같은 prefix를 공유하는 비율이 높다. 이런 워크로드에서 단순 선형 스캔은 prefix마다 O(N)이라 답이 안 나온다.

테스트 케이스. `add("car", 5)`, `add("card", 3)`, `add("care", 7)`, `add("cargo", 1)`, `add("apple", 2)`. `suggest("car", 3)` → `["care", "car", "card"]` (빈도 7, 5, 3). `suggest("car", 10)` → `["care", "car", "card", "cargo"]`. `suggest("z", 3)` → `[]`. `add("car", 4)` 후 `suggest("car", 2)` → `["car", "care"]` (빈도 9, 7).

<details>
<summary>문제 2 풀이 보기 (직접 짜본 뒤에 펼쳐주세요)</summary>

설계 결정 과정. 자동완성은 prefix 질의가 hot path라서 Trie가 자연스럽다. 핵심은 prefix 노드를 찾은 뒤 그 서브트리에서 단어를 모두 모으고, 빈도/사전순으로 정렬해 상위 k개를 자르는 것이다. 단순 구현으로 충분히 빠른지 먼저 추산한다. prefix 노드 아래 서브트리 단어가 보통 100개 이내라면 매 호출마다 DFS + 정렬 O(M log M)이 10^4 호출 × 100 단어 ≈ 10^6 정렬 작업이라 여유롭다. M이 매우 클 가능성이 있으면 각 노드에 "이 서브트리의 top-k"를 캐싱하는 정교한 변형이 가능하지만, 라이브 코딩 25분 안에서는 단순 DFS 버전이 안전하다. 면접에서는 단순 버전을 먼저 짜고 "트래픽이 더 크면 노드별 top-k 캐시로 진화시키겠다"고 추가 설명하는 편이 평가에 유리하다.

빈도 누적은 단어 종결 노드의 `freq`에 더하는 방식이다. `freq > 0`이면 그 노드는 단어 종결로 간주한다. 빈 문자열 prefix는 루트에서 시작해 전체를 훑으니 자연스럽게 동작한다.

정렬 비교자. `freq` 내림차순, `word` 오름차순. `Comparator.comparingInt((String[] e) -> -Integer.parseInt(e[1])).thenComparing(e -> e[0])`보다 가독성을 위해 전용 record/클래스를 쓴다.

```java
import java.util.*;

public class AutoComplete {

    private static final int SIGMA = 26;

    private static final class Node {
        final Node[] next = new Node[SIGMA];
        int freq;
    }

    private final Node root = new Node();

    public void add(String word, int freq) {
        if (freq <= 0) return;
        Node cur = root;
        for (int i = 0; i < word.length(); i++) {
            int idx = word.charAt(i) - 'a';
            if (cur.next[idx] == null) {
                cur.next[idx] = new Node();
            }
            cur = cur.next[idx];
        }
        cur.freq += freq;
    }

    public List<String> suggest(String prefix, int k) {
        if (k <= 0) return List.of();
        Node start = walk(prefix);
        if (start == null) return List.of();

        List<Entry> bucket = new ArrayList<>();
        StringBuilder buf = new StringBuilder(prefix);
        collect(start, buf, bucket);

        bucket.sort((a, b) -> {
            if (a.freq != b.freq) return Integer.compare(b.freq, a.freq);
            return a.word.compareTo(b.word);
        });

        int n = Math.min(k, bucket.size());
        List<String> out = new ArrayList<>(n);
        for (int i = 0; i < n; i++) out.add(bucket.get(i).word);
        return out;
    }

    private Node walk(String s) {
        Node cur = root;
        for (int i = 0; i < s.length(); i++) {
            int idx = s.charAt(i) - 'a';
            Node nxt = cur.next[idx];
            if (nxt == null) return null;
            cur = nxt;
        }
        return cur;
    }

    private void collect(Node node, StringBuilder buf, List<Entry> out) {
        if (node.freq > 0) {
            out.add(new Entry(buf.toString(), node.freq));
        }
        for (int i = 0; i < SIGMA; i++) {
            Node nxt = node.next[i];
            if (nxt == null) continue;
            buf.append((char) ('a' + i));
            collect(nxt, buf, out);
            buf.deleteCharAt(buf.length() - 1);
        }
    }

    private record Entry(String word, int freq) {}

    public static void main(String[] args) {
        AutoComplete ac = new AutoComplete();
        ac.add("car", 5);
        ac.add("card", 3);
        ac.add("care", 7);
        ac.add("cargo", 1);
        ac.add("apple", 2);

        require(ac.suggest("car", 3).equals(List.of("care", "car", "card")), "car top3");
        require(ac.suggest("car", 10).equals(List.of("care", "car", "card", "cargo")), "car all");
        require(ac.suggest("z", 3).equals(List.of()), "no match");

        ac.add("car", 4); // accumulate
        require(ac.suggest("car", 2).equals(List.of("car", "care")), "car after bump");

        require(ac.suggest("", 3).equals(List.of("care", "car", "card")), "empty prefix top3 by global freq");
        System.out.println("ok");
    }

    private static void require(boolean cond, String msg) {
        if (!cond) throw new AssertionError(msg);
    }
}
```

면접에서 짚을 follow-up과 답변 가이드.

- "사전이 매우 커서 prefix 아래 단어가 수만 개면 매번 DFS는 비싸다." 답: 각 노드에 size-k min-heap이나 정렬된 top-k 캐시를 유지해 add 시 갱신하면 suggest를 O(L + k log k)로 만들 수 있다. trade-off는 add 비용이 prefix 길이만큼의 노드에 대해 갱신되니 O(L · log k)로 늘어난다는 점이다.
- "동시성은?" 답: read 쪽이 압도적으로 많고 add는 batch라면 Copy-on-write 또는 RW lock으로 충분하다. add가 잦다면 노드별 lock 또는 lock-free 갱신을 검토해야 하지만 보통은 사전을 정적 build하고 swap한다.
- "빈도 누적이 음수가 들어오면?" 답: 사양 외라고 잘라내거나, 단어 삭제 시맨틱이라면 noop 단어 노드를 회수하는 cleanup 패스를 별도 정의해야 한다.
- "메모리 추산은?" 답: σ=26 배열 노드는 64-bit JVM 기준 헤더 16B + 배열 참조 8B + 배열 자체 16B + 26·8B ≈ 240B. 사전 5·10^4 단어 평균 길이 8이면 노드 ≈ 4·10^5 → 약 100MB. 적절한지 면접관과 합의한다.

</details>

## 면접 답변용 핵심 한 줄 묶음

라이브 코딩이 끝나고 면접관이 "그럼 Trie를 한 줄로 정리해주세요"라고 묻는 상황을 위해, 시니어 백엔드 답변용 카드 몇 장을 외워둔다.

- "Trie는 prefix가 같은 단어들을 노드 공유로 표현해 prefix 질의를 단어 길이에 선형으로 만들어주는 자료구조입니다. HashSet과 점근 복잡도는 비슷하지만 prefix 위에 얹는 자동완성, 사전 탐색, 다중 패턴 매칭 같은 부가 연산에서 본질적 우위를 가집니다."
- "구현에서 가장 큰 결정은 노드 자식 표현입니다. σ가 작고 고정이면 배열, 크거나 sparse하면 HashMap을 씁니다. 압축이 필요한 IP 라우팅 같은 도메인은 Radix tree로 갑니다."
- "단어 종결 플래그를 노드 존재와 분리하지 않으면 search와 startsWith가 같은 답을 내는 흔한 버그가 생깁니다."
- "라이브에서는 코드 짜기 전에 문자 집합, 빈 문자열, 중복 삽입 정책을 면접관과 30초 안에 합의합니다. 합의가 끝나면 walk 헬퍼로 search/startsWith 공통 경로를 묶어 코드를 줄이고, 직접 호출 테스트로 검증합니다."
- "확장 방향은 자동완성 시 노드별 top-k 캐시, 다중 패턴 매칭 시 Aho-Corasick으로의 진화, 정적 사전이면 압축 Trie 또는 DAFSA로의 메모리 최적화입니다."

## 면접 직전 셀프 체크리스트

- [ ] 표준 Trie를 빈 파일에서 6분 안에 짜고 빈 문자열, 공유 prefix, 미존재 단어 케이스를 직접 검증할 수 있는가
- [ ] 노드 자식을 배열로 둘지 HashMap으로 둘지 30초 안에 근거와 함께 결정할 수 있는가
- [ ] `search`와 `startsWith`의 마지막 줄 차이를 말로 설명할 수 있는가
- [ ] σ를 코드 상수로 분리하고, 문자 집합 가정을 면접관에게 먼저 묻는 습관이 있는가
- [ ] 빈 문자열 prefix와 빈 문자열 단어 처리 방침을 정해두었는가
- [ ] delete 요구 시 "자식 없고 단어 종결도 아닐 때만 부모에서 끊는다" 규칙을 말할 수 있는가
- [ ] 자동완성 변형에서 단순 DFS 정렬 → 노드별 top-k 캐시로의 진화 경로를 설명할 수 있는가
- [ ] 시간 복잡도뿐 아니라 노드 단위 메모리 추산을 숫자로 댈 수 있는가
- [ ] HashSet과 비교했을 때 Trie의 본질적 우위(prefix 위 부가 연산)를 한 문장으로 말할 수 있는가
- [ ] 라이브 환경에서 외부 라이브러리 없이 `javac && java -ea`만으로 검증을 돌리는 손에 익은 워크플로가 있는가

이 체크리스트의 항목 하나하나가 라이브 코딩에서 1~2분의 자신감을 만들고, 그 자신감이 누적되면 화이트보드 인터뷰 전체의 결을 바꾼다. 코드는 외우는 것이 아니라, 가정을 듣고 그 가정에서 자라나도록 손이 기억하게 만드는 것이다.
