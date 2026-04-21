# [초안] Java 라이브 코딩: HashMap과 문자열 패턴 집중 훈련

## 왜 이 조합이 라이브 코딩의 핵심인가

HackerRank, 프로그래머스, LeetCode 어느 플랫폼이든 시니어 백엔드 엔지니어 대상 라이브 코딩에서 가장 높은 빈도로 출제되는 카테고리가 **HashMap + String**이다. 이유는 단순하다.

첫째, 면접관 입장에서 평가 포인트가 풍부하다. 자료구조 선택, 시간/공간 복잡도 분석, 에지 케이스 처리, 변수 네이밍, 디버깅 과정, 트레이드오프 설명까지 한 문제 안에서 관찰할 수 있다. 둘째, 백엔드 실무와 연결된다. 요청 로그에서 패턴을 추출하거나, 중복 키를 탐지하거나, 특정 상태를 카운팅하는 작업은 실제 서비스 운영에서 매일 마주친다. 셋째, 30~45분이라는 제한된 시간 안에 "생각 → 코드 → 검증"을 모두 보여줄 수 있을 만큼 범위가 적절하다.

그런데 많은 지원자가 이 유형에서 실수를 한다. 표면적으로는 쉬워 보여서 준비를 덜 하기 때문이다. `HashMap<Character, Integer>`를 쓰는 관용적 코드는 머리로 알지만, 실제 타이핑에서 `getOrDefault`와 `merge`의 차이, `containsKey` → `get` → `put` 3단 콤보의 race 가능성, `String.toCharArray()`로 인한 불필요한 메모리 할당 같은 것들을 면접관 앞에서 설명하지 못한다.

이 문서는 그런 약점을 없애는 것을 목표로 한다. HashMap과 문자열을 엮어 푸는 문제를 **실전 라이브 코딩 시나리오**에 맞춰 분해하고, 말로 설명하는 방식까지 함께 정리한다.

## 핵심 개념: 빈도 카운팅을 넘어서

### 1) 빈도 카운팅의 세 가지 패턴

문자열 문제에서 HashMap이 등장하는 맥락은 거의 다음 셋 중 하나다.

**(a) 단순 카운트** — 각 문자(또는 단어)가 몇 번 나왔는가
```java
Map<Character, Integer> freq = new HashMap<>();
for (char c : s.toCharArray()) {
    freq.merge(c, 1, Integer::sum);
}
```

**(b) 위치/인덱스 기억** — 특정 문자가 마지막으로 등장한 인덱스가 필요할 때 (슬라이딩 윈도우의 "longest substring without repeating characters"류)
```java
Map<Character, Integer> lastIndex = new HashMap<>();
for (int i = 0; i < s.length(); i++) {
    lastIndex.put(s.charAt(i), i);
}
```

**(c) 그룹 버킷** — 어떤 키로 묶으면 같은 그룹인지 판정할 때 (아나그램 그룹핑이 대표적)
```java
Map<String, List<String>> groups = new HashMap<>();
for (String word : words) {
    String key = normalize(word); // 정렬하거나 카운트 시그니처 생성
    groups.computeIfAbsent(key, k -> new ArrayList<>()).add(word);
}
```

실전에서는 (a)와 (b)를 **같이** 써야 하는 문제가 자주 나온다. 빈도도 세고 위치도 추적해야 하는 경우, `Map<Character, int[]>` 또는 별도의 두 맵으로 관리한다. 이 분기점에서 머뭇거리면 시간이 샌다.

### 2) 아나그램과 패턴 매칭

아나그램 판정은 세 가지 접근이 있다.

- **정렬 비교**: `Arrays.sort(arr)` 후 equals. O(n log n)이지만 코드가 짧다.
- **카운트 배열**: `int[26]` 으로 두 문자열을 동시에 카운트하며 +1/-1 하고 마지막에 전부 0인지 확인. O(n).
- **HashMap 카운트**: 유니코드 전체를 다룰 때. ASCII 26자 이내라면 배열이 훨씬 빠르다.

라이브 코딩에서 **알파벳 소문자만** 나온다는 제약이 있으면 반드시 `int[26]`을 꺼내라. HashMap보다 20~50배 빠르고 면접관이 "왜 HashMap 대신 배열을?"이라고 물었을 때 "해시 오버헤드 제거, 캐시 지역성, 키 범위가 고정"이라는 답을 바로 할 수 있어야 한다.

패턴 매칭의 확장형은 "두 문자열 사이 일대일 대응"이다. `isIsomorphic("egg", "add")` 같은 문제에서는 **양방향 매핑**이 필요하다.

```java
boolean isIsomorphic(String s, String t) {
    if (s.length() != t.length()) return false;
    Map<Character, Character> sToT = new HashMap<>();
    Map<Character, Character> tToS = new HashMap<>();
    for (int i = 0; i < s.length(); i++) {
        char a = s.charAt(i), b = t.charAt(i);
        if (sToT.containsKey(a) && sToT.get(a) != b) return false;
        if (tToS.containsKey(b) && tToS.get(b) != a) return false;
        sToT.put(a, b);
        tToS.put(b, a);
    }
    return true;
}
```

양방향을 빠뜨려서 `"ab"`, `"aa"` 같은 케이스를 잘못 통과시키는 것이 가장 흔한 버그다.

### 3) 문자열 상태 추적: 슬라이딩 윈도우

HashMap이 빛을 발하는 영역이 슬라이딩 윈도우다. 창 안의 문자 빈도를 유지하면서 왼쪽 포인터를 당기고 오른쪽을 늘린다.

**템플릿 (Java)**
```java
int longestUniqueWindow(String s) {
    Map<Character, Integer> count = new HashMap<>();
    int left = 0, best = 0;
    for (int right = 0; right < s.length(); right++) {
        char c = s.charAt(right);
        count.merge(c, 1, Integer::sum);
        while (count.get(c) > 1) {
            char l = s.charAt(left++);
            if (count.merge(l, -1, Integer::sum) == 0) {
                count.remove(l);
            }
        }
        best = Math.max(best, right - left + 1);
    }
    return best;
}
```

여기서 `count.remove(l)`을 깜빡하면 "창 안에 없는 문자가 맵에 남아" 중복 판정이 어긋난다. `merge`가 0을 반환했을 때 제거하는 습관이 중요하다.

### 4) StringBuilder와 불변 문자열

Java의 `String`은 불변이다. 루프 안에서 `result += c` 하면 매 순회마다 새 `String`이 만들어져 O(n²)가 된다. 라이브 코딩 중 이 실수를 보이면 시니어 평가는 바로 깎인다.

- 문자열 조립은 **항상 `StringBuilder`**.
- 단일 비교/반환은 그대로 `String` 사용.
- 부분 문자열이 필요하면 `s.substring(i, j)` — 다만 Java 7u6 이후 내부 char[]를 공유하지 않고 복사하므로 O(k)라는 점을 알고 있어야 한다.
- 대용량 문자열에서 문자 접근은 `charAt(i)`가 `toCharArray()`보다 메모리 효율적이다. `toCharArray()`는 전체 복사본을 만든다.

```java
StringBuilder sb = new StringBuilder();
for (int i = 0; i < n; i++) sb.append(arr[i]);
String result = sb.toString();
```

`StringBuilder`는 thread-safe가 아니다. 라이브 코딩에서는 문제없지만, 면접관이 "`StringBuffer`와 차이는?"이라고 따라오면 "`StringBuffer`는 synchronized, 단일 스레드에서는 StringBuilder가 기본"이라고 즉답할 수 있어야 한다.

## 실무에서는 어떻게 쓰이는가

- **로그 파서**: 엑세스 로그에서 IP별 요청 수 집계, 특정 User-Agent 패턴 카운팅.
- **중복 요청 탐지**: 최근 N초 동안 같은 키의 요청이 몇 번 들어왔는지 LRU 성격의 맵으로 유지.
- **feature flag 라우팅**: 사용자 ID 문자열을 해시해 A/B 버킷 키로 변환.
- **입력 정규화**: 상품명이나 검색어의 공백/대소문자/특수문자를 제거한 정규화 키를 HashMap에 넣고 중복 집계.

이 중 로그 파서와 중복 요청 탐지는 라이브 코딩에서 **응용 문제**로 그대로 나온다. "최근 10초 내 같은 IP가 5회 이상이면 block list에 넣어라" 같은 변형은 `Map<String, Deque<Long>>` 구조로 풀린다. HashMap만으로는 안 되고 큐가 함께 필요하다는 판단을 빨리 해야 한다.

## Bad vs Improved 예제

### Bad: 빈도 카운트
```java
Map<Character, Integer> freq = new HashMap<>();
for (int i = 0; i < s.length(); i++) {
    char c = s.charAt(i);
    if (freq.containsKey(c)) {
        freq.put(c, freq.get(c) + 1);
    } else {
        freq.put(c, 1);
    }
}
```
문제점: `containsKey` → `get` → `put`으로 해시 연산 3회. 관용적이지도 않다.

### Improved
```java
Map<Character, Integer> freq = new HashMap<>();
for (int i = 0; i < s.length(); i++) {
    freq.merge(s.charAt(i), 1, Integer::sum);
}
```
해시 연산 1회. `merge`는 Java 8 표준이며 면접관이 가장 좋아하는 패턴이다.

### Bad: 아나그램 판정
```java
boolean isAnagram(String a, String b) {
    char[] x = a.toCharArray();
    char[] y = b.toCharArray();
    Arrays.sort(x);
    Arrays.sort(y);
    return Arrays.equals(x, y);
}
```
동작은 한다. O(n log n). 작은 입력에선 충분하지만 "더 빠른 방법?"이 오면 멈춘다.

### Improved
```java
boolean isAnagram(String a, String b) {
    if (a.length() != b.length()) return false;
    int[] cnt = new int[26];
    for (int i = 0; i < a.length(); i++) {
        cnt[a.charAt(i) - 'a']++;
        cnt[b.charAt(i) - 'a']--;
    }
    for (int v : cnt) if (v != 0) return false;
    return true;
}
```
O(n), 공간 O(1). 길이 선체크로 조기 종료까지 붙였다.

## 구현 시 흔한 버그

1. **빈도가 0이 된 엔트리를 맵에서 지우지 않아** 슬라이딩 윈도우 조건이 틀어진다.
2. **양방향 매핑 누락** — isomorphic, word pattern 문제에서 단방향만 검사.
3. **`char - 'a'` 인덱싱을 대문자나 숫자에 그대로 적용** — 입력 범위 확인을 안 함.
4. **`String.equals` 대신 `==`** — 상수 풀 밖의 문자열에서 false가 되어 디버깅 30분 낭비.
5. **`toCharArray()` 남발** — 메모리 복사. `charAt(i)`로 충분한 자리.
6. **`getOrDefault(k, 0) + 1`을 put하면서 `merge`와 혼용** — 일관성 없는 코드는 버그를 부른다. 한 파일에선 한 방식으로.
7. **유니코드 이모지** — `char`는 16비트라 surrogate pair가 있는 이모지는 두 개의 char로 쪼개진다. 대부분 면접에선 ASCII 가정이지만 "유니코드면?" 질문이 오면 `codePoints()`를 언급하라.
8. **`Integer` 박싱 오버헤드** — `Map<Character, Integer>`는 박싱된다. 성능이 결정적이면 `int[]` 또는 `Map<Character, int[]>`에 `cnt[0]++` 트릭.

## 라이브 면접에서 말하는 순서

면접관 앞에서는 바로 코드를 치지 마라. 다음 4단계를 말로 먼저 훑는다.

1. **입력 제약 확인**: "길이 범위는? 문자 범위는 알파벳 소문자만인가요, 아스키 전체인가요? 빈 문자열이 들어오나요?"
2. **접근 선언**: "저는 한 번 순회하면서 HashMap에 빈도를 저장하는 O(n) 방식으로 가겠습니다. 문자 범위가 소문자 26자면 `int[26]`으로 바꿀 수 있고 그게 더 빠릅니다."
3. **에지 케이스 열거**: "빈 문자열은 true/false 중 무엇인가요? 길이가 다르면 즉시 false로 처리하겠습니다."
4. **구현 후 복잡도 재진술**: "시간 O(n), 공간 O(k). k는 유일 문자 수입니다."

이 네 단계를 빠뜨리고 코드만 치는 지원자와, 천천히 말하면서 함께 생각하는 지원자의 평가는 크게 갈린다.

## 로컬 연습 환경

JDK 17 이상 권장. 빠른 반복을 위해서는 IDE보다 단일 파일 실행이 편하다.

```bash
# JDK 설치 확인
java -version

# 단일 파일 작성 및 실행 (Java 11+)
cat > Solution.java <<'EOF'
public class Solution {
    public static void main(String[] args) {
        System.out.println(isAnagram("listen", "silent"));
    }
    static boolean isAnagram(String a, String b) {
        if (a.length() != b.length()) return false;
        int[] cnt = new int[26];
        for (int i = 0; i < a.length(); i++) {
            cnt[a.charAt(i) - 'a']++;
            cnt[b.charAt(i) - 'a']--;
        }
        for (int v : cnt) if (v != 0) return false;
        return true;
    }
}
EOF
java Solution.java
```

HackerRank 실전 환경은 `main`과 `Scanner`로 입력을 받는 형태다. 아래 템플릿을 외워두면 입력 파싱에서 시간을 허비하지 않는다.

```java
import java.util.*;
public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = Integer.parseInt(sc.nextLine().trim());
        for (int i = 0; i < n; i++) {
            String line = sc.nextLine();
            System.out.println(solve(line));
        }
    }
    static String solve(String s) {
        // TODO
        return "";
    }
}
```

## 연습 문제

두 문제 모두 **먼저 스스로 풀고**, 막히면 details 블록을 연다. 최소 20분은 고민해라. 라이브 코딩에서 답을 외우는 것은 의미가 없다. 과정을 체화해야 한다.

### 문제 1 (쉬움) — 첫 번째 유일 문자의 인덱스

문자열 `s`가 주어졌을 때, 문자열 안에서 **단 한 번만 등장하는 문자** 중 **가장 앞에 나타난 문자의 인덱스**를 반환하라. 모든 문자가 2회 이상 등장하면 `-1`을 반환한다.

- 입력: `"leetcode"` → 출력: `0` (`l`)
- 입력: `"loveleetcode"` → 출력: `2` (`v`)
- 입력: `"aabb"` → 출력: `-1`

제약: 입력은 ASCII 소문자만. 길이는 1 이상 100,000 이하.

힌트만: 두 번 순회해도 된다. 한 번 순회 + 카운트 맵, 두 번째 순회에서 카운트 1인 첫 문자를 찾는다.

<details>
<summary>풀이 보기</summary>

**접근**
- 첫 순회: 각 문자의 빈도를 `int[26]`에 기록. 유니코드까지 확장할 여지가 있다면 `HashMap`도 가능하지만, 제약이 소문자라면 배열이 맞다.
- 두 번째 순회: 원본 문자열을 처음부터 훑으며 `cnt[c - 'a'] == 1`을 만족하는 첫 인덱스를 반환.

**왜 두 번 도는가?** HashMap에 insertion order를 신뢰하고 싶지 않고(`HashMap`은 순서 보장 X), `LinkedHashMap`으로 한 번에 끝낼 수도 있지만 **두 번 순회 + int[26]**이 가장 빠르고 말하기 쉽다. 면접관에게 "LinkedHashMap으로 한 번에 풀 수도 있지만 해시/박싱 오버헤드가 있어 소문자 제약에선 배열 두 번 순회가 더 빠릅니다"라고 설명하면 된다.

**복잡도**: 시간 O(n), 공간 O(1) (26 고정).

**실수 포인트**
- 두 번째 순회에서 `cnt` 배열을 다시 훑으면 안 된다. 반드시 **원본 문자열**을 훑어야 "가장 앞" 조건이 지켜진다.
- 대문자/공백이 입력에 섞여 오면 `c - 'a'`가 음수 인덱스를 만들어 `ArrayIndexOutOfBoundsException`. 제약 확인이 생명.

**전체 코드**
```java
import java.util.*;

public class FirstUniqueChar {
    public static int firstUniqChar(String s) {
        int[] cnt = new int[26];
        for (int i = 0; i < s.length(); i++) {
            cnt[s.charAt(i) - 'a']++;
        }
        for (int i = 0; i < s.length(); i++) {
            if (cnt[s.charAt(i) - 'a'] == 1) return i;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(firstUniqChar("leetcode"));      // 0
        System.out.println(firstUniqChar("loveleetcode"));  // 2
        System.out.println(firstUniqChar("aabb"));          // -1
        System.out.println(firstUniqChar(""));              // -1
    }
}
```

**HashMap 버전 (면접관이 "맵으로도 해보라"고 할 때)**
```java
public static int firstUniqCharMap(String s) {
    Map<Character, Integer> freq = new HashMap<>();
    for (int i = 0; i < s.length(); i++) {
        freq.merge(s.charAt(i), 1, Integer::sum);
    }
    for (int i = 0; i < s.length(); i++) {
        if (freq.get(s.charAt(i)) == 1) return i;
    }
    return -1;
}
```
두 버전을 모두 보여주고 "제약에 따라 선택"이라고 말하면 시니어 인상이 남는다.

</details>

### 문제 2 (중간) — 아나그램 그룹핑 + 가장 큰 그룹의 대표 단어

문자열 배열 `words`가 주어졌을 때, **아나그램끼리 묶은 뒤**, **원소 수가 가장 많은 그룹의 단어들을 사전순(lexicographic)으로 정렬**해 반환하라. 동률 그룹이 여러 개면, 그룹을 구성하는 단어들을 사전순으로 정렬했을 때 **첫 단어가 사전순으로 가장 빠른 그룹**을 선택한다.

- 입력: `["eat", "tea", "tan", "ate", "nat", "bat"]`
- 아나그램 그룹: `[eat, tea, ate]`, `[tan, nat]`, `[bat]`
- 가장 큰 그룹은 `[eat, tea, ate]`, 사전순 정렬 후 `[ate, eat, tea]`
- 출력: `["ate", "eat", "tea"]`

제약: `words.length` ≤ 10,000, 각 단어 길이 ≤ 100, 소문자만.

이 문제는 실제로 HackerRank/LeetCode의 "Group Anagrams" + 추가 조건을 합친 형태다. 라이브 코딩에서 **요구사항을 재진술**하는 훈련까지 포함된다.

<details>
<summary>풀이 보기</summary>

**접근**
1. 각 단어를 **정규화 키**로 변환. 두 가지 방법:
   - (a) 단어를 정렬한 문자열: `"eat"` → `"aet"`
   - (b) 26칸 카운트 시그니처: `"eat"` → `"1,0,0,0,1,...,1"` 형태
   라이브 코딩에선 (a)가 코드가 짧고 설명이 쉽다. 길이가 매우 길고 단어 수가 많으면 (b)가 유리하다 (정렬 O(L log L) → 카운트 O(L)).
2. `Map<String, List<String>>`에 키별로 묶는다. `computeIfAbsent` 사용.
3. 가장 큰 그룹을 찾는다. 동률 타이브레이커를 위해 "그룹 단어들을 사전순 정렬했을 때 첫 단어"를 보조 키로 사용.
4. 최종 그룹을 사전순 정렬 후 반환.

**요구사항 재진술** (면접관에게 말할 문장):
"그룹별 크기를 먼저 비교하고, 동률이면 그룹을 정렬했을 때의 첫 단어를 비교한다는 거죠? 그리고 최종 출력은 그 그룹을 사전순으로 정렬한 결과고요."

**복잡도**
- 정규화: O(N · L log L) (정렬 키 방식)
- 그룹핑: O(N)
- 최대 그룹 탐색: O(G) (G = 그룹 수)
- 최종 정렬: O(M log M) (M = 최대 그룹 크기)

**실수 포인트**
- `Arrays.sort(char[])`는 primitive라 `Arrays.sort(Integer[])`와 달리 매우 빠르다. 하지만 `String.toCharArray()`는 복사본이라는 점을 기억.
- 동률 판정에서 "그룹 크기만 비교"하고 타이브레이커를 빠뜨리면 테스트 케이스에서 실패.
- `HashMap` 순회 순서는 보장되지 않으므로, 동률 그룹 중 "먼저 나온 걸 쓰면 된다"는 식의 가정은 위험하다. **명시적 타이브레이커**를 두어라.
- `computeIfAbsent`의 람다에서 `new ArrayList<>()`를 제대로 리턴하지 않고 `put`하는 중복 코드를 쓰면 면접관이 지적한다.

**전체 코드**
```java
import java.util.*;

public class TopAnagramGroup {

    public static List<String> topAnagramGroup(String[] words) {
        Map<String, List<String>> groups = new HashMap<>();
        for (String w : words) {
            String key = normalize(w);
            groups.computeIfAbsent(key, k -> new ArrayList<>()).add(w);
        }

        List<String> best = null;
        String bestFirst = null;
        for (List<String> group : groups.values()) {
            List<String> sorted = new ArrayList<>(group);
            Collections.sort(sorted);
            String first = sorted.get(0);

            if (best == null
                    || sorted.size() > best.size()
                    || (sorted.size() == best.size() && first.compareTo(bestFirst) < 0)) {
                best = sorted;
                bestFirst = first;
            }
        }

        return best == null ? Collections.emptyList() : best;
    }

    private static String normalize(String w) {
        char[] arr = w.toCharArray();
        Arrays.sort(arr);
        return new String(arr);
    }

    public static void main(String[] args) {
        String[] input = {"eat", "tea", "tan", "ate", "nat", "bat"};
        System.out.println(topAnagramGroup(input));
        // [ate, eat, tea]

        String[] tie = {"abc", "bca", "xyz", "zyx"};
        System.out.println(topAnagramGroup(tie));
        // [abc, bca] — 크기 동률, 첫 단어 "abc" < "xyz"
    }
}
```

**카운트 시그니처 버전 (단어가 길 때)**
```java
private static String normalizeByCount(String w) {
    int[] cnt = new int[26];
    for (int i = 0; i < w.length(); i++) cnt[w.charAt(i) - 'a']++;
    StringBuilder sb = new StringBuilder(52);
    for (int i = 0; i < 26; i++) {
        sb.append(cnt[i]).append('#');
    }
    return sb.toString();
}
```
구분자 `#`이 없으면 `"1,11"`과 `"11,1"`이 충돌한다. 구분자 누락이 가장 흔한 버그다.

**면접관이 물어볼 후속 질문 준비**
- "단어가 매우 길면?" → 카운트 시그니처로 O(L) 정규화.
- "메모리가 부족하면?" → 스트리밍으로 그룹 크기만 카운트하는 1차 패스 후, 최대 그룹만 2차 패스에서 모은다. 단, 타이브레이커 처리가 복잡해짐.
- "대소문자 혼용이면?" → 정규화 단계에서 `toLowerCase(Locale.ROOT)` 추가. Locale 명시가 포인트 — 터키어 로케일에서 `I`가 소문자로 바뀌는 이슈.

</details>

## 면접 답변 프레이밍

"HashMap 쓰실 줄 아세요?"가 아니라 "왜 HashMap이고, 왜 지금 이 크기인가요?"가 시니어 면접의 질문이다. 다음 문장 패턴을 연습해두면 말이 막히지 않는다.

- **선택 근거**: "이 문제는 키로 그룹핑이 필요하고 키 범위가 유계가 아니라 HashMap을 택했습니다. 만약 문자 범위가 ASCII 26자로 제한되면 `int[26]`이 해시/박싱 오버헤드가 없어 더 빠릅니다."
- **복잡도 방어**: "평균 O(1) 조회지만 충돌이 많으면 Java 8 이후 트리 전환으로 O(log n). 키 해시가 고르게 분포하는지가 관건입니다."
- **메모리 언급**: "`HashMap<Character, Integer>`는 박싱된 Integer가 매 엔트리마다 16바이트 이상 오버헤드. 고성능이 필요하면 primitive 배열이나 Eclipse Collections의 `CharIntHashMap`."
- **동시성**: "스레드 안전이 필요하면 `ConcurrentHashMap`, 하지만 이 문제는 단일 스레드라 `HashMap` 충분."
- **확장**: "실무에선 같은 패턴을 Redis의 HASH 타입으로 옮겨 요청 카운팅에 씁니다. TTL이 붙는다는 게 차이고요."

경험 연결 질문이 오면 본인 프로젝트에서 "요청/로그 빈도 집계" 또는 "중복 키 탐지" 에피소드를 30초 이내로 말할 수 있게 미리 준비한다. 라이브 코딩의 알고리즘 문제가 백엔드 실무와 어떻게 닿아 있는지를 연결하는 지원자는 드물고, 그만큼 인상이 남는다.

## 체크리스트

- [ ] `merge(k, 1, Integer::sum)` 관용구를 망설임 없이 친다
- [ ] `int[26]`과 `HashMap` 중 언제 어느 쪽을 쓸지 30초 안에 판단한다
- [ ] 슬라이딩 윈도우 템플릿을 외워서 쓰되, 0이 된 엔트리를 제거하는 습관이 있다
- [ ] 아나그램을 정렬/카운트/배열 세 가지 방식으로 설명할 수 있다
- [ ] isomorphic/word pattern류 문제에서 **양방향 매핑**을 놓치지 않는다
- [ ] 루프 안 문자열 결합은 반드시 `StringBuilder`
- [ ] `toCharArray()`의 메모리 비용과 `charAt()`의 대안을 안다
- [ ] 면접 시작 4단계(제약 확인 → 접근 선언 → 에지 케이스 → 복잡도)를 말로 실행한다
- [ ] HackerRank `Scanner` 입력 템플릿을 1분 안에 타이핑한다
- [ ] `computeIfAbsent` 한 줄로 그룹 버킷을 만든다
- [ ] 동률 판정 시 명시적 타이브레이커를 둔다
- [ ] Locale 관련 대소문자 함정(터키어)을 언급할 수 있다
- [ ] 이 문서의 연습 문제 두 개를 details를 열지 않고 15분 내에 푼다
