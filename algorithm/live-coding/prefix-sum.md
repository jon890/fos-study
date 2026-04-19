# [초안] Prefix Sum 완전 정복 - Java 라이브 코딩 대비 스터디 팩

## 왜 Prefix Sum을 깊이 파야 하는가

라이브 코딩 면접, 특히 HackerRank나 코드 공유 화면에서 진행되는 45~60분짜리 세션에서 Prefix Sum은 "면접관이 좋아하는 주제" 중 하나다. 이유는 명확하다.

첫째, **문제를 겉으로만 보면 O(N·Q) 완전 탐색으로 쉽게 풀리지만, 제약을 살짝만 키우면 반드시 O(1) 쿼리로 바꿔야 한다.** 이 전환이 지원자의 "시간 복잡도 감각"을 가장 깔끔하게 드러낸다. 면접관 입장에서는 지원자가 단순 반복문 이상의 자료구조 전처리 사고를 할 수 있는지 20분 안에 판별할 수 있다.

둘째, **백엔드 실무에서도 이 사고는 그대로 쓰인다.** 일·월 단위 KPI 집계, 광고 과금 윈도우 합산, Redis Sorted Set에 점수 누적, MySQL 통계 테이블의 delta 기반 스냅샷, Kafka 파티션별 offset 구간 합 같은 문제 대부분은 "구간 합을 빠르게 꺼내기 위한 전처리"라는 같은 뿌리를 공유한다. 실제 인터뷰에서 "이전 프로젝트에서 비슷한 성능 문제를 어떻게 풀었냐"는 꼬리질문이 따라붙기 때문에, Prefix Sum을 백엔드 시스템적 언어로 설명할 수 있어야 한다.

셋째, **구현 자체에는 함정이 많다.** 인덱스 off-by-one, prefix 배열을 N+1 크기로 잡느냐 N 크기로 잡느냐, 초기값 처리, 2D에서 포함-배제 공식, hash map 결합 시 `map.put(0, 1)` 누락 같은 실수가 모두 "흔하지만 떨어지는 이유"가 된다. 라이브 코딩에서는 이런 디테일이 최종 합격을 가른다.

이 문서는 Prefix Sum을 "개념 → 패턴 → 라이브 코딩 실전 2문제"까지 45분 분량 스터디로 압축한 가이드다.

## 구간 합 직관 - "차이로 환원한다"

Prefix Sum의 본질은 다음 한 줄이다.

> 구간 `[l, r]`의 합은 "0부터 r까지의 합"에서 "0부터 l-1까지의 합"을 뺀 것이다.

수식으로는 이렇게 된다.

```
prefix[i] = a[0] + a[1] + ... + a[i-1]   (길이 N+1, prefix[0] = 0)
sum(l, r) = prefix[r+1] - prefix[l]
```

여기서 중요한 감각은 "나는 구간 합을 구하는 게 아니라 **두 지점의 누적값 차이**를 구한다"라고 사고의 프레임을 바꾸는 것이다. 이 프레임이 잡히는 순간 다음과 같은 확장이 모두 자연스럽게 이어진다.

- 합이 아닌 XOR, 개수, 모듈러 합도 동일한 차이 연산으로 환원된다 (역원이 존재하는 연산이면 모두 가능).
- "합이 K인 부분배열 개수" 같은 해시 결합 문제도 "두 prefix 값의 차이가 K"로 환원된다.
- 2차원 누적합도 결국 네 지점의 차이(포함-배제)로 환원된다.

라이브 코딩 중 면접관에게 접근법을 설명할 때, 이 문장을 먼저 뱉는 것이 좋다. "구간 합 질의는 두 누적값의 차이로 환원해서 쿼리당 O(1)로 내리는 게 기본 전략입니다." 이 한 문장이 곧 전체 풀이 시그널이다.

## 1차원 prefix sum의 정석 구현

크기를 `N+1`로 잡고 `prefix[0] = 0`으로 두는 스타일을 **항상 쓰는 걸 권장한다.** 이유는 경계 조건이 통째로 사라지기 때문이다.

```java
int n = a.length;
long[] prefix = new long[n + 1];
for (int i = 0; i < n; i++) {
    prefix[i + 1] = prefix[i] + a[i];
}
// 구간 [l, r] (양쪽 포함) 합
long sumLR = prefix[r + 1] - prefix[l];
```

여기서 의식적으로 고정해야 하는 규칙 3가지:

1. **`prefix` 길이는 항상 `N+1`.** 길이를 `N`으로 잡으면 `l == 0`일 때 `prefix[l - 1]` 접근이 생겨 if 분기가 들어간다. 분기는 버그의 온상이다.
2. **합 타입은 `long`.** int 배열이라도 N이 10^5만 넘어가면 누적값이 int overflow 난다. 라이브 코딩에서 int로 썼다가 큰 테스트케이스에서 -값이 나오는 게 전형적 탈락 장면이다.
3. **`sum(l, r) = prefix[r + 1] - prefix[l]`을 "한 줄짜리 공식"으로 외운다.** 라이브 코딩 중에 유도하지 말고, "양 포함 구간이면 오른쪽 +1, 왼쪽 그대로"로 입에서 바로 나와야 한다.

## 2차원 누적합 - 포함-배제 공식

2D Prefix Sum은 동일한 사고를 좌표 평면으로 확장한 것이다.

```
prefix[i][j] = matrix[0..i-1][0..j-1] 영역의 합
prefix[i][j] = prefix[i-1][j] + prefix[i][j-1] - prefix[i-1][j-1] + matrix[i-1][j-1]
```

영역 합 쿼리는 포함-배제로 푼다. 좌상단 `(r1, c1)`, 우하단 `(r2, c2)`의 직사각형 합은:

```
sum = prefix[r2 + 1][c2 + 1]
    - prefix[r1][c2 + 1]
    - prefix[r2 + 1][c1]
    + prefix[r1][c1]
```

1D와 2D의 가장 큰 차이는 **전처리 시점의 중복 영역 제거**다. 1D는 단순 누적, 2D는 위·왼쪽을 더한 뒤 겹친 좌상단을 한 번 빼줘야 한다. 이 공식이 손에 익지 않으면 라이브 코딩에서 종이에 2x2 예시를 그려놓고 시작하는 게 빠르다.

```
matrix =
1 2 3
4 5 6
7 8 9

prefix =
0  0  0  0
0  1  3  6
0  5 12 21
0 12 27 45
```

`(1,1)~(2,2)` 영역 합은 `5+6+8+9 = 28`이고, 공식으로는 `prefix[3][3] - prefix[1][3] - prefix[3][1] + prefix[1][1] = 45 - 6 - 12 + 1 = 28`로 일치한다. 라이브 면접에서는 이 검산을 소리 내어 하는 게 좋은 인상을 준다.

## 누적합 + HashMap 결합 패턴

Prefix Sum의 진짜 고점은 해시맵과의 결합에서 나온다. 대표 문제: **"합이 K인 부분배열의 개수"**.

핵심 변환은 이것이다.

> `sum(l, r) = K`  ⇔  `prefix[r+1] - prefix[l] = K`  ⇔  `prefix[l] = prefix[r+1] - K`

즉, "현재까지 누적합 `cur`을 보면서, 과거에 `cur - K`가 몇 번 등장했는지 센다." 이 한 줄이 이 패턴의 전부다.

```java
public int subarraySum(int[] nums, int k) {
    Map<Long, Integer> freq = new HashMap<>();
    freq.put(0L, 1);          // 핵심: "아무것도 안 더한 상태" = 0 은 1번 존재한다
    long cur = 0;
    int count = 0;
    for (int x : nums) {
        cur += x;
        count += freq.getOrDefault(cur - k, 0);
        freq.merge(cur, 1, Integer::sum);
    }
    return count;
}
```

이 패턴에서 가장 많이 틀리는 지점:

- **`freq.put(0L, 1)`을 깜빡한다.** "배열의 처음부터 r까지 합이 정확히 K인 경우"를 놓친다.
- **카운트를 먼저 올리고 빈도를 증가시켜야 한다.** 순서가 바뀌면 같은 위치 자기 자신을 센다 (K=0일 때 특히 버그).
- **`cur`을 long으로 두지 않는다.** 음수와 양수가 섞인 배열에서 int overflow는 자주 터진다.

이 패턴은 확장이 다양하다. "합이 K의 배수인 부분배열 개수"는 `cur % k`를 키로 쓰고, "XOR이 K인 부분배열 개수"는 `+` 대신 `^`를 쓰면 그대로 동작한다. 연산이 역원을 가지면 전부 같은 구조다.

## 인덱스 경계 처리 - 라이브 코딩의 진짜 난관

라이브 코딩에서 대부분의 실수는 **"구간 정의가 모호한 상태에서 코딩을 시작"**한 것이다. 손이 먼저 움직이기 전에 다음 3가지를 소리 내어 확정하라.

1. 입력 인덱스는 0-based인가, 1-based인가?
2. 구간 `[l, r]`은 양쪽 포함인가, 오른쪽 배타인가?
3. `prefix` 배열 크기는 N+1인가 N인가?

이 셋을 고정하면 공식도 고정된다. 예를 들어 "입력은 1-based, 양 포함, prefix는 N+1" 조합이면 `sum(l, r) = prefix[r] - prefix[l-1]`이 되고, "입력은 0-based, 양 포함, prefix는 N+1"이면 `sum(l, r) = prefix[r+1] - prefix[l]`이다. **헷갈리면 면접관에게 묻는다. 묻는 건 감점이 아니다.**

## 흔한 버그 체크리스트

- `int` 오버플로 - 누적합은 `long`으로.
- prefix를 N 크기로 잡고 `l=0` 분기를 따로 쓰다가 오타.
- 2D 포함-배제에서 `prefix[r1][c1]`을 빼는 실수 (실제로는 더해야 함).
- 해시맵 초기값 `{0:1}` 누락.
- 쿼리 인덱스 변환 실수 (1-based 입력인데 0-based로 조회).
- 음수 원소가 있는데 "합이 K 이상인 최소 길이 구간"에 prefix + 투 포인터를 쓴다 - 이건 단조성이 깨지므로 해시/덱으로 가야 한다. **이건 면접에서 꼭 언급**하면 좋은 꼬리 질문 방어가 된다.

## 로컬 연습 환경

Java 라이브 코딩은 HackerRank/CoderPad 환경이 기본이지만, 자기 검증은 로컬에서 빠르게 돌리는 게 낫다. 권장 세팅:

```bash
# 폴더 구조
prefix-sum-practice/
  src/
    main/java/algo/PrefixSum.java
    test/java/algo/PrefixSumTest.java
  build.gradle

# build.gradle 최소 설정
plugins { id 'java' }
repositories { mavenCentral() }
dependencies {
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
}
test { useJUnitPlatform() }
```

실행:

```bash
./gradlew test --tests algo.PrefixSumTest
```

IDE 없이 빠르게 돌리려면 단일 파일로 `public static void main`에 시나리오 3~5개를 넣고 `javac PrefixSum.java && java PrefixSum`으로 10초 안에 피드백 루프를 만든다. 라이브 코딩도 결국 "작은 케이스로 직접 검산"이 핵심이다.

## 라이브 면접에서 접근 방식을 설명하는 방법

면접관 앞에서 문제를 받으면 다음 6단계를 소리 내어 진행한다. 이 흐름이 곧 "시니어스러운" 신호다.

1. **입력·출력·제약을 복창**한다. "배열 길이 N ≤ 10^5, 쿼리 Q ≤ 10^5, 값 범위 -10^9 ~ 10^9이죠?"
2. **브루트포스부터 정의**한다. "쿼리마다 구간 합을 O(N)에 구하면 O(N·Q)=10^10이라 TLE입니다."
3. **환원 문장을 뱉는다.** "구간 합은 prefix의 차이로 O(1) 환원 가능합니다."
4. **경계와 자료형을 미리 못 박는다.** "prefix는 N+1 길이, long 타입, sum(l, r) = prefix[r+1] - prefix[l]."
5. **엣지 케이스 시나리오**를 언급한다. N=0, 구간이 전체, 값이 모두 음수, 1개 원소 구간.
6. **코딩 후 작은 예제로 검산**한다. 실행 없이 머리로 trace한다.

이 6단계 중 하나라도 빼먹으면 "그냥 외운 풀이"로 보인다. 특히 3번과 6번이 시니어 지표다.

## 연습 문제 1 (쉬움) - Running Sum Query

**문제.** 길이 N의 정수 배열 `a`와 Q개의 쿼리가 주어진다. 각 쿼리는 `(l, r)` (0-based, 양쪽 포함)이다. 각 쿼리의 구간 합을 출력하라.

- 제약: N, Q ≤ 10^5, |a[i]| ≤ 10^9
- 예시 입력: `a = [3, -1, 4, 1, 5, 9, 2, 6]`, 쿼리 `(0, 2), (1, 4), (3, 7)`
- 기대 출력: `6, 9, 23`

힌트 없이 먼저 풀어보고, 5분 안에 손이 안 움직이면 풀이를 본다.

<details>
<summary>풀이 및 Java 전체 코드 보기</summary>

**풀이 전략.**

- prefix 배열을 N+1 길이 long으로 잡고 `prefix[0] = 0`.
- `prefix[i+1] = prefix[i] + a[i]`로 전처리 O(N).
- 각 쿼리는 `prefix[r+1] - prefix[l]`로 O(1).
- 총 복잡도 O(N + Q).

**검산 (a = [3, -1, 4, 1, 5, 9, 2, 6]).**

- prefix = `[0, 3, 2, 6, 7, 12, 21, 23, 29]`
- `(0,2)` → prefix[3] - prefix[0] = 6 - 0 = 6 ✓
- `(1,4)` → prefix[5] - prefix[1] = 12 - 3 = 9 ✓
- `(3,7)` → prefix[8] - prefix[3] = 29 - 6 = 23 ✓

```java
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.StringTokenizer;

public class RunningSumQuery {

    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(br.readLine());
        int n = Integer.parseInt(st.nextToken());
        int q = Integer.parseInt(st.nextToken());

        long[] prefix = new long[n + 1];
        st = new StringTokenizer(br.readLine());
        for (int i = 0; i < n; i++) {
            int v = Integer.parseInt(st.nextToken());
            prefix[i + 1] = prefix[i] + v;
        }

        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < q; i++) {
            st = new StringTokenizer(br.readLine());
            int l = Integer.parseInt(st.nextToken());
            int r = Integer.parseInt(st.nextToken());
            long sum = prefix[r + 1] - prefix[l];
            sb.append(sum).append('\n');
        }
        System.out.print(sb);
    }
}
```

**라이브 면접용 한 줄 요약.** "쿼리당 O(1) 응답을 위해 N+1 길이 long prefix를 미리 만들고, 차이로 답합니다. int 오버플로 방지를 위해 long을 씁니다."

</details>

## 연습 문제 2 (중간) - Subarray Sum Equals K (음수 포함)

**문제.** 정수 배열 `nums` (음수 포함)와 정수 K가 주어진다. 합이 정확히 K인 연속 부분배열의 **개수**를 반환하라.

- 제약: N ≤ 2·10^4, |nums[i]| ≤ 10^3, |K| ≤ 10^7
- 예시: `nums = [1, 2, 3]`, K = 3 → 출력 `2` (`[1,2]`, `[3]`)
- 예시: `nums = [1, -1, 0]`, K = 0 → 출력 `3` (`[1,-1]`, `[0]`, `[1,-1,0]`)

**함정.** 음수가 섞이면 슬라이딩 윈도우 / 투 포인터로 풀 수 없다. 단조성이 깨지기 때문이다. 이 지점을 면접관에게 먼저 짚어주는 것이 중요하다.

<details>
<summary>풀이 및 Java 전체 코드 보기</summary>

**풀이 전략.**

- `sum(l, r) = K` ⇔ `prefix[r+1] - prefix[l] = K` ⇔ `prefix[l] = prefix[r+1] - K`.
- HashMap에 "지금까지 등장한 prefix 값의 빈도"를 유지한다.
- 초기값 `{0: 1}` 반드시 포함 (배열 시작부터 합이 K가 되는 경우 처리).
- 순서 엄수: 현재 prefix로 `cur - K` 빈도를 먼저 더한 뒤, 현재 prefix를 맵에 넣는다. 순서를 바꾸면 K=0일 때 자기 자신을 센다.
- 복잡도 O(N) 시간, O(N) 공간.

**검산 (nums = [1, -1, 0], K = 0).**

| i | x  | cur | 먼저 더할 freq(cur - K) | count | 그 뒤 freq 상태 |
|---|----|-----|-------------------------|-------|------------------|
| - | -  | 0   | -                       | 0     | {0:1}           |
| 0 | 1  | 1   | freq(1)=0               | 0     | {0:1, 1:1}      |
| 1 | -1 | 0   | freq(0)=1 → count=1     | 1     | {0:2, 1:1}      |
| 2 | 0  | 0   | freq(0)=2 → count=3     | 3     | {0:3, 1:1}      |

최종 3 ✓.

```java
import java.util.HashMap;
import java.util.Map;

public class SubarraySumEqualsK {

    public static int subarraySum(int[] nums, int k) {
        Map<Long, Integer> freq = new HashMap<>();
        freq.put(0L, 1);

        long cur = 0;
        int count = 0;

        for (int x : nums) {
            cur += x;
            Integer hit = freq.get(cur - k);
            if (hit != null) {
                count += hit;
            }
            freq.merge(cur, 1, Integer::sum);
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(subarraySum(new int[]{1, 2, 3}, 3));       // 2
        System.out.println(subarraySum(new int[]{1, -1, 0}, 0));      // 3
        System.out.println(subarraySum(new int[]{3, 4, 7, 2, -3, 1, 4, 2}, 7)); // 4
    }
}
```

**라이브 면접용 한 줄 요약.** "음수가 섞여 윈도우 단조성이 깨지므로 prefix sum + HashMap으로 환원했습니다. 과거 prefix 중 `cur - K`가 몇 번 있었는지 세는 구조이고, 초기값 `{0:1}`과 '먼저 세고 나중에 빈도 증가' 순서가 포인트입니다."

**꼬리 질문 대비.**

- "합이 K의 배수인 부분배열 개수는?" → 키를 `cur % k`로 바꾸되, 음수 mod 처리에 주의 (`((cur % k) + k) % k`).
- "XOR이 K인 부분배열 개수는?" → `+`를 `^`로 바꾸고 동일 구조.
- "N이 10^7이고 값이 int 범위 상한이면?" → Long 박싱 비용 때문에 `HashMap<Long,Integer>` 대신 primitive map (Eclipse Collections `LongIntHashMap` 등)을 고려.

</details>

## 백엔드 실무 연결 포인트

라이브 코딩에서 문제를 푼 뒤, 면접관이 "이거 실무에서 쓴 적 있어요?"라고 물으면 다음 중 하나로 연결하라.

- **광고/결제 KPI 배치.** 일별 매출을 매번 SUM으로 재계산하지 않고, 월초 누적 스냅샷 + 일 delta로 구간 매출을 O(1) 쿼리로 내린 경험.
- **MySQL 집계 테이블.** 원본 트랜잭션 테이블 위에 `daily_snapshot(date, cum_amount)` 같은 누적 컬럼을 두고, 리포트 쿼리는 차이 연산으로 처리. 이건 DB 버전의 prefix sum이다.
- **Redis Sorted Set + score 누적.** 사용자별 누적 점수를 유지하고 구간 랭킹을 빠르게 뽑는 구조.
- **Kafka 오프셋 lag 모니터링.** 파티션별 committed offset을 prefix처럼 기록하고 구간별 consumer 처리량을 차이로 측정.

이 연결을 한두 문장만 붙여도 "알고리즘을 시스템 언어로 번역할 수 있는 사람"으로 보인다.

## 최종 체크리스트

- [ ] prefix 배열은 N+1, 타입은 long으로 고정했는가?
- [ ] `sum(l, r) = prefix[r+1] - prefix[l]` 공식이 입에서 바로 나오는가?
- [ ] 2D 포함-배제 공식을 2x2 예시로 30초 안에 검산할 수 있는가?
- [ ] 해시 결합 패턴에서 `freq.put(0L, 1)`을 절대 빠뜨리지 않는가?
- [ ] 해시 결합 패턴에서 "세고 나서 빈도 증가" 순서를 지키는가?
- [ ] 음수 포함 시 투 포인터가 안 된다는 걸 설명할 수 있는가?
- [ ] 구간 정의(0/1-based, 포함/배타)를 면접 초반에 먼저 묻는 습관이 있는가?
- [ ] 2개 연습 문제를 코드 없이 whiteboard로 10분 안에 구현할 수 있는가?
- [ ] 백엔드 실무 사례(MySQL 집계/Redis/Kafka)와 한 문장으로 연결할 수 있는가?

이 체크리스트 전부에 "예"가 붙으면 Prefix Sum 주제로 라이브 코딩 45분 세션은 방어된다. 남은 시간은 모노토닉 스택, 슬라이딩 윈도우, 이진탐색 같은 인접 패턴에 투자하라.
