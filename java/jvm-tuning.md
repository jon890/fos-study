# [초안] JVM 튜닝 실전: 메모리 구조부터 Virtual Threads, GC 튜닝, 프로파일링까지

## 왜 지금 JVM 튜닝을 다시 공부해야 하는가

시니어 Java 백엔드 엔지니어라면 "서비스가 느려졌다"는 장애 리포트를 한 번쯤 받아봤을 것이다. 이때 "GC가 원인인가?"를 10분 안에 판단할 수 있는가, 아니면 로그만 뒤적이다가 한 시간을 보내는가. 이 차이가 시니어와 미드 레벨의 결정적 차이다.

JVM 튜닝은 "옵션 플래그를 외우는 것"이 아니다. 힙이 어떻게 구성되는지, GC가 어떤 규칙으로 객체를 죽이는지, 어떤 지표를 봐야 튜닝 방향이 잡히는지를 이해해야 한다. 특히 Java 17, 21 LTS로 넘어오면서 G1GC가 기본값이 되고, ZGC가 프로덕션 레벨로 올라왔고, Virtual Threads가 등장하면서 "Thread Pool 사이즈를 어떻게 잡는가"라는 오랜 질문 자체가 다시 쓰이고 있다. CJ OliveYoung 규모의 커머스 플랫폼이라면 결제/검색/추천 등 다양한 워크로드가 한 JVM 안에 혼재하고, 초당 수천 건의 요청에서 pause time 100ms가 사용자 경험을 직접 깎아먹는다.

이 문서는 JVM 메모리 구조 → GC → 튜닝 플래그 → 로그 해석 → OOM 대응 → 실전 사례 매핑 → 프로파일링 → Virtual Threads → 동시성 유틸리티 → JMH 벤치마킹 → 면접 답변 framing까지, 시니어 관점의 JVM 지식을 한 번에 정리한다.

## JVM 메모리 구조 복습

JVM이 프로세스로 올라왔을 때 차지하는 메모리는 크게 네 영역이다.

**Heap**. 애플리케이션 객체가 사는 곳. `-Xms`(초기값), `-Xmx`(최대값)로 크기를 지정한다. G1GC는 이 Heap을 Region(기본 1MB~32MB 사이 2의 거듭제곱) 단위로 쪼개서 관리한다.

**Metaspace**. 클래스 메타데이터(클래스 구조, 메서드 바이트코드, 상수 풀 등)가 들어간다. Java 8에서 PermGen을 대체해서 나왔다. 네이티브 메모리에 잡히고, `-XX:MaxMetaspaceSize`로 상한을 안 걸면 시스템 메모리를 무제한 먹을 수 있다. 동적 클래스 로딩이 많은 애플리케이션(JSP, Groovy, JPA Entity 프록시 대량 생성)은 여기서 터진다.

**Thread stack**. 각 스레드마다 `-Xss`(기본 1MB 전후)만큼 잡힌다. 스레드 1만 개면 순수 스택으로만 10GB가 날아간다. 이게 바로 Virtual Threads가 풀어야 했던 문제의 본질이다.

**Direct memory / Native memory**. `ByteBuffer.allocateDirect()`, Netty, DirectBuffer 기반 I/O, JNI 라이브러리 등이 여기에 잡힌다. `-XX:MaxDirectMemorySize`로 상한을 건다. Heap 모니터링만 하고 있으면 이쪽이 터져도 원인을 못 찾는다.

컨테이너 환경에서 특히 주의할 점: 컨테이너 메모리 한도가 4GB인데 `-Xmx3g`를 잡았다고 해서 나머지 1GB가 Metaspace + Thread stack + Direct + JVM 자체 오버헤드로 다 쓸 수 있는 건 아니다. 보통 Heap은 컨테이너 메모리의 50~70% 정도로 시작해서 실측으로 조정한다.

```
[컨테이너 4GB]
├── Heap (Xmx=2.5g)
├── Metaspace (~256MB)
├── Thread stack (스레드 200개 × 1MB = 200MB)
├── Direct memory (~256MB)
├── Code cache (~240MB)
├── GC overhead, JIT, symbol table (~수백 MB)
└── OS / 여유
```

## GC 기본: Young/Old, 승격, Stop-the-world

대부분의 객체는 "금방 죽는다"는 **Weak Generational Hypothesis**가 현대 GC의 출발점이다.

**Young 영역**은 Eden + Survivor 0/1로 구성된다. 새 객체는 Eden에 잡힌다. Eden이 꽉 차면 **Minor GC(Young GC)**가 발동해, 살아남은 객체를 Survivor로 옮긴다. 여러 번 살아남으면(age threshold, 기본 15회) **Old 영역**으로 **승격(promotion)**된다.

**Old 영역**에 객체가 쌓이다가 임계치를 넘으면 **Major GC / Mixed GC / Full GC**가 일어난다. G1GC는 Old까지 포함하는 Mixed GC로 최대한 Full GC를 회피한다.

**Stop-the-world(STW)**란 GC가 힙을 안전하게 스캔하고 객체를 옮기는 동안 애플리케이션 스레드를 전부 멈추는 구간이다. 파라렐 GC는 STW가 길고, G1은 대부분의 작업을 병렬로 하지만 핵심 단계는 여전히 STW이다. ZGC, Shenandoah는 STW를 수 ms 이하로 끌어내린 **concurrent GC**다.

면접에서 "왜 Young/Old로 나누는가"를 물으면: 새 객체의 대부분은 금방 죽으므로 Young만 자주 청소하면 비용이 낮다. Old로 승격된 객체는 이미 오래 살아남은 객체들이고, 그들끼리는 생존률이 높으니 덜 자주 청소한다. 세대 구분은 **"GC 대상 범위를 줄이는 최적화"**의 결과물이다.

## 현대 GC 비교: G1GC / ZGC / Shenandoah

**G1GC**(Java 9+ 기본, Java 11 LTS 이후 완전 기본값). 힙을 Region으로 쪼개고, garbage가 많은 Region부터 우선 청소한다. 목표 pause time을 `-XX:MaxGCPauseMillis`로 지정하면 그 목표를 최대한 지키려고 Region 수를 조절한다. 힙 4GB~수십 GB, pause 100~200ms 목표에서 가장 무난하다.

**ZGC**(Java 15 GA, Java 17부터 프로덕션 권장). pause time이 힙 크기와 거의 무관하게 1ms 이하다. Colored pointer와 load barrier를 써서 mark/relocate를 전부 concurrent하게 돌린다. 수백 GB 힙에서도 pause가 안 늘어난다. 대신 CPU와 메모리 오버헤드가 약간 있고, throughput은 G1보다 살짝 낮다. **지연에 민감한 API 게이트웨이, 결제, 검색**에 적합.

**Shenandoah**(Red Hat, OpenJDK 포함). ZGC와 유사한 목표를 가진 low-pause GC. Brooks pointer 또는 load reference barrier를 사용해 concurrent compaction을 구현한다. Red Hat 기반 배포판에서 자주 쓰인다.

선택 가이드라인:

| 워크로드 | 추천 GC |
|---|---|
| 일반 웹/API, Heap 4~32GB, pause 100~200ms OK | G1GC |
| 결제/검색/실시간, pause 10ms 이하 요구 | ZGC |
| Heap 100GB 이상 | ZGC |
| Batch, throughput 최우선 | Parallel GC |
| 메모리 100MB 이하 초소형 | Serial GC |

커머스 플랫폼에서 결제 API는 ZGC, 어드민 배치는 Parallel, 일반 API는 G1로 다르게 튜닝하는 것이 합리적이다.

## GC 튜닝 기본 플래그

**힙 크기**.
```bash
-Xms4g -Xmx4g
```
`Xms`와 `Xmx`를 같은 값으로 두는 게 정석이다. 다르게 두면 힙을 늘리고 줄이는 과정 자체가 STW를 유발한다. 서버 JVM에서 힙 크기 변동은 비용만 크고 이득이 거의 없다.

**힙 크기 결정 원리**. 피크 부하 시점의 **Old 영역 실사용량 × 2~3배**가 전체 Heap의 합리적 시작점이다. 피크 때 Old가 1GB를 쓰고 있다면 Heap 3~4GB를 주고, 거기서 GC 로그를 보며 조정한다. 무작정 크게 잡으면 GC 한 번이 더 오래 걸리고, 너무 작게 잡으면 Full GC가 뜬다.

**G1GC 주요 플래그**.
```bash
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
-XX:G1HeapRegionSize=16m
-XX:InitiatingHeapOccupancyPercent=45
-XX:+ParallelRefProcEnabled
```

`MaxGCPauseMillis`는 "목표"지 보장이 아니다. 너무 공격적으로(예: 50ms) 잡으면 Young 영역이 과도하게 작아져 오히려 GC 빈도가 올라간다. `G1HeapRegionSize`는 대개 자동 계산에 맡기지만, 큰 객체(humongous object, region 50% 이상)를 자주 만드는 애플리케이션이면 명시적으로 늘리는 게 좋다.

**ZGC 주요 플래그**.
```bash
-XX:+UseZGC
-XX:+ZGenerational   # Java 21+, Generational ZGC
-Xmx16g
```

**Metaspace**.
```bash
-XX:MetaspaceSize=256m
-XX:MaxMetaspaceSize=512m
```

**OOM 덤프 자동 생성**. 프로덕션 필수.
```bash
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/heapdump/
-XX:+ExitOnOutOfMemoryError
```

## GC 로그 해석

Java 9+부터는 `-Xlog:gc*`로 통합되었다.
```bash
-Xlog:gc*,gc+heap=debug,gc+age=trace:file=/var/log/app/gc.log:time,uptime,level,tags:filecount=10,filesize=64m
```

G1 로그 예시 한 줄:
```
[2026-04-19T14:22:11.345+0900][14.345s][info][gc] GC(42) Pause Young (Normal) (G1 Evacuation Pause) 2048M->512M(4096M) 35.4ms
```
해석:
- `GC(42)`: 42번째 GC 이벤트
- `Pause Young (Normal)`: Young GC(Minor)
- `2048M->512M(4096M)`: GC 전 힙 사용량 2048M → GC 후 512M, 전체 힙 4096M
- `35.4ms`: STW 시간

세 가지 핵심 지표를 본다.

**Pause time**. 개별 GC의 STW. p99 pause가 SLA 이내인가.

**Throughput**. `1 - (GC 시간 / 전체 시간)`. 95% 이상이 정상, 90% 이하면 GC 압박이 심하다.

**Allocation rate**. `(GC 전 힙 사용량 - 직전 GC 후 힙 사용량) / 경과 시간`. 초당 몇 MB의 객체가 새로 할당되는가. 갑자기 올라가면 메모리 누수 or 불필요한 객체 생성이 의심된다.

로그 분석 도구: **GCViewer**, **GCEasy**(https://gceasy.io — 사내망 제약이 있으면 GCViewer 로컬 실행).

## OOM 유형과 대응

**`java.lang.OutOfMemoryError: Java heap space`**. Heap이 꽉 찼다. 원인: 메모리 누수(정적 Map에 계속 쌓음), 대용량 데이터 한 번에 로딩(페이징 없이 `findAll()`), 캐시 상한 미설정. 대응: 힙 덤프 받아서 MAT으로 Dominator Tree → Retained Heap 큰 객체 추적.

**`java.lang.OutOfMemoryError: Metaspace`**. 클래스 로딩 과다. 원인: 동적 프록시 과생성, 클래스로더 누수(Tomcat redeploy시 고전적 문제), 라이브러리가 런타임 바이트코드 생성 남용. 대응: `jcmd <pid> VM.classloader_stats`, `-XX:MaxMetaspaceSize`로 상한 설정 후 누수 탐지.

**`java.lang.OutOfMemoryError: Direct buffer memory`**. Netty, NIO 채널, 이미지/PDF 처리 라이브러리가 의심. 대응: `-XX:MaxDirectMemorySize` 명시, `-Dio.netty.maxDirectMemory=0`으로 Netty가 JVM 한도 따르게 강제.

**`java.lang.OutOfMemoryError: GC overhead limit exceeded`**. 전체 시간의 98% 이상을 GC에 쓰는데 회수량이 2% 미만. 실질적으로는 Heap 부족의 전조. 힙을 늘리거나 누수를 찾는다.

**`java.lang.OutOfMemoryError: unable to create new native thread`**. Heap 문제가 아니라 OS limit(ulimit -u) 또는 Thread stack 합계가 시스템 메모리를 초과. 스레드 수를 줄이거나 `-Xss`를 줄인다(단, StackOverflowError 위험).

## 실전 사례: 슬롯 시뮬레이터 OOM — 임시 대응 vs 근본 해결

앞 섹션의 `Java heap space` 카테고리에 정확히 들어맞는 실제 사례를 앞서 다룬 개념들로 매핑해본다. 이 케이스는 **"힙을 늘려서 끄기"와 "구조를 바꾸기"의 경계가 어디인지**를 분명하게 보여주는 교과서적 예시다. 참고: [슬롯 시뮬레이터 OOM](../task/nsc-slot/slot-simulator-oom.md).

### 상황 요약

슬롯 게임의 RTP(Return To Player)와 변동성 지수를 검증하는 시뮬레이터였다. 1억 스핀을 돌려 기댓값과 분산이 수학적으로 맞게 나오는지 확인한다. 변동성 지수 = 분산이 필요하고, 분산을 구하는 직관적인 방법은 **모든 당첨금을 리스트에 쌓아두고 끝에 한 번에 계산**하는 것이다.

```java
public class AccumulateData {
    // 변동성 지수 계산시 사용하던 변수
    private final List<Long> winmoneyList;
}
```

여러 명이 동시에 시뮬레이터를 돌리자 `java.lang.OutOfMemoryError: Java heap space`가 떨어졌다. 조사 과정에서 먼저 드러난 것은 **JVM 힙 사이즈 옵션 자체가 지정돼 있지 않아 기본값으로 실행**되고 있었다는 것이다.

### 메모리 계산

```
1회 시뮬레이션: 1억 스핀 × Long(8 bytes) = 약 800MB
                (실제로는 Long 박싱 + ArrayList 내부 오버헤드로 더 큼)
4명 동시 실행  : 800MB × 4 = 3.2GB
+ 스레드별 AccumulateData 중간 상태
+ merge 시점의 concatList 순간 피크
```

이는 앞서 본 Heap OOM 원인 중 "대용량 데이터 한 번에 로딩 / 무제한 누적" 패턴과 정확히 같은 계열이다. `findAll()`로 수백만 건을 올리는 예시와 구조적으로 동일하다.

### 1단계 — 임시 대응: 힙 확장

당장 서비스가 돌아야 하니 다음과 같이 대응했다.

```bash
export JAVA_OPTS="-Xmx12g -Xms12g"
```

이 대응의 성격을 정확히 이해해야 한다.

- ✅ **OOM이 당장 뜨지 않게 한다** — 사용자가 시뮬레이터를 못 쓰는 상황을 막는다.
- ❌ **원인은 그대로다** — 동시 사용자가 더 늘거나 스핀 수가 늘면 다시 터진다.
- ❌ **GC 비용이 선형으로 증가한다** — 힙이 커질수록 Full GC 한 번의 STW가 길어진다. 대용량 `List<Long>`이 Old로 승격되면 Mixed GC도 무거워진다.
- ❌ **allocation rate가 여전히 비정상적으로 높다** — 스핀마다 Long 박싱이 일어나 Young GC 빈도가 폭발적으로 올라간다. 본 문서의 GC 로그 섹션에서 말한 "throughput 90% 미만"에 금방 도달한다.
- ❌ **humongous object 위험** — List가 특정 크기를 넘으면 G1 region의 50%를 넘어 humongous 할당이 일어날 수 있고, 이는 G1의 최적화 경로에서 벗어난다.

즉, 힙 확장은 **"원인 조사 시간을 버는 행위"**이지 해결이 아니다. 앞선 OOM 섹션의 루틴을 실제로 적용했다면:

1. `-XX:+HeapDumpOnOutOfMemoryError`로 생성된 `.hprof`를 MAT에 로딩
2. Leak Suspects Report — `ArrayList` 내부 `Object[]`가 상위에 뜬다
3. Dominator Tree에서 Retained Heap 상위 — `AccumulateData.winmoneyList`가 확실히 최상위
4. GC Roots 추적 — 시뮬레이션 스레드에서 참조를 쥐고 있음

여기까지 오면 "이 리스트가 왜 존재해야 하는가"로 자연스럽게 질문이 올라간다. 시니어의 진단은 여기서 멈추지 않고 **"이 객체가 원래 필요했는가"**를 묻는 단계로 간다.

### 2단계 — 근본 해결: 공간 복잡도 O(N) → O(1)

분산을 구하기 위해 **모든 값을 저장할 필요가 없다**는 것이 핵심이다. Welford's Online Algorithm은 `count`, `mean`, `m2` 세 개의 스칼라만 유지하면서 단일 패스로 평균과 분산을 갱신한다.

```
저장: int count(4) + double mean(8) + double m2(8) = 20 bytes
1억 스핀이든 100억 스핀이든 메모리 사용량은 그대로 20바이트
```

```java
public void addWinMoney(long winMoney, long totalBetAmount) {
    count++;
    double multiplier = (double) winMoney / totalBetAmount;
    double delta  = multiplier - mean;
    mean += delta / count;
    double delta2 = multiplier - mean;
    m2 += delta * delta2;
}

double getVariance() {
    return count > 1 ? m2 / (count - 1) : 0.0;
}
```

구조 변경의 효과를 JVM 관점으로 풀면 다음과 같다.

| 지표 | 변경 전 | 변경 후 |
|---|---|---|
| 스핀 1회당 allocation | `Long` 박싱 + ArrayList 확장 | 0 (스칼라 변수 갱신만) |
| 1억 스핀 누적 메모리 | ~800MB/스레드 | 20 bytes/스레드 |
| 4명 동시 실행 피크 | ~3.2GB + merge concat 피크 | ~80 bytes |
| Young GC 빈도 | 매우 높음 (allocation rate 급증) | 급감 |
| Old 승격 | 장수 객체 winmoneyList → Old 이동 | 없음 |
| Full GC / GC overhead limit | 발생 가능 | 사실상 사라짐 |
| humongous object 위험 | 리스트가 커질수록 존재 | 없음 |

### 병렬 처리에서의 병합

시뮬레이터는 멀티스레드로 스핀을 돌리고 스레드마다 `AccumulateData`를 들고 있다가 끝에 합친다. 기존 방식에서는 merge 순간에 **1억 개짜리 리스트 두 개를 concat**해야 했다. 이 순간이 allocation rate와 Old promotion의 피크였고, G1에서는 young evacuation이 급증해 pause time도 튀었을 시점이다.

온라인 알고리즘에서는 merge도 수학적으로 상수 공간/상수 시간이다.

```java
public static WelfordOnlineCalculator merge(WelfordOnlineCalculator a, WelfordOnlineCalculator b) {
    var merged = new WelfordOnlineCalculator();
    merged.count = a.count + b.count;
    if (merged.count == 0) return merged;
    double delta = b.mean - a.mean;
    merged.mean = (a.mean * a.count + b.mean * b.count) / merged.count;
    merged.m2 = a.m2 + b.m2 + delta * delta * a.count * b.count / merged.count;
    return merged;
}
```

즉 "멀티스레드 환경에서 스레드당 상태 크기가 입력 크기에 선형으로 증가하는 설계" 자체를 제거한 것이다.

### 트레이드오프: 부동소수점 누적 오차

Welford's는 `double` 누적에 기반하므로 전체 데이터를 모은 뒤 한 번에 계산하는 방식과 수치적으로 완전히 일치하지 않는다. 실측 오차율은 0.xx% 수준이었고, **변동성 지수 용도에는 충분히 허용 가능한 범위**였다.

시니어 관점에서 중요한 건 "알고리즘 교체로 발생한 오차를 감으로 처리하지 않고 측정했다"는 점이다. 이는 본 문서 JMH 섹션의 "58배 개선 사례" framing과 같은 맥락이다 — **"얼마나 빨라졌는가"보다 "어디까지 적용했는가, 어떤 수치로 판단했는가"**를 같이 말할 수 있어야 시니어다.

### 적용 방식: 기존 경로 무력화하지 않기

기존 팩토리 메서드는 `@Deprecated`로 두고 새 팩토리를 추가했다. 슬롯 5종(21, 29, 31, 32, 33)에 점진적으로 전환했다.

```java
@Deprecated
public static AccumulateData init() { ... }

public static AccumulateData initWithWelfordOnlineCalculator() {
    var accumulateData = new AccumulateData(..., null); // winmoneyList는 null
    accumulateData.welfordOnlineCalculator = WelfordOnlineCalculator.init();
    return accumulateData;
}
```

같이 배우는 것: **구조 변경은 한 번에 뒤집지 않는다**. `@Deprecated`로 기존 경로를 유지하고 신규 경로를 병행해서 슬롯 단위로 롤백 가능한 단위를 만든다.

### 이 사례에서 뽑아낼 JVM/GC 교훈

1. **힙 확장은 임시 대응이다.** `-Xmx`를 늘리는 것은 원인을 가리는 행위다. 필요하면 해야 하지만, 동시에 힙 덤프를 떠서 근본 원인을 추적하는 작업을 시작해야 한다.
2. **Heap OOM은 대부분 allocation rate 또는 retained heap의 문제다.** 전자는 "많이 만들어서", 후자는 "붙잡고 안 놓아서". 이 케이스는 둘 다 해당한다 — 스핀마다 Long을 박싱해 allocation rate가 높고, 리스트가 시뮬레이션 끝까지 참조를 유지해 retained heap이 크다.
3. **멀티스레드에서 "스레드당 상태 크기"가 입력 크기에 선형으로 증가하면 위험하다.** 스레드 수 × 동시 사용자 수로 곱해지면 작은 상수도 폭발한다. JVM 튜닝 전에 **알고리즘의 공간 복잡도**를 먼저 본다.
4. **힙 사이즈 옵션은 항상 명시적으로 지정한다.** 컨테이너 환경에서 기본값을 쓰면 컨테이너 한도와 맞지 않아 예측 불가능한 동작을 한다. 본 문서 앞부분의 "컨테이너 50~70%" 가이드라인을 그대로 적용한다.
5. **"느려졌다/터졌다"의 진단 순서는 동일하다.** GC 로그 → jstat으로 Old/Full GC 확인 → 힙 덤프 → MAT로 retained heap top 객체 → 그 객체의 설계 자체를 의심. 이 사례는 5번째 단계, 즉 **"왜 이 객체가 원래 필요했는가"**까지 올라가 구조를 바꾼 예다.
6. **JVM 튜닝과 알고리즘 설계는 연속된 스펙트럼이다.** `-Xmx` 플래그 조정, GC 선택, 데이터 구조 교체, 알고리즘 교체는 같은 문제에 대한 서로 다른 강도의 개입이다. 상위로 올라갈수록 근본적이고 효과가 크지만 리스크도 크다.

### 인터뷰 활용 framing

> "시뮬레이터에서 Heap OOM이 나서 `-Xmx`를 12GB로 늘린 것이 임시 대응이었습니다. 이 대응이 원인을 해결하는 게 아니라 'GC 로그와 힙 덤프를 뜰 시간을 버는 행위'라는 걸 전제로 했습니다. 진짜 원인은 1억 건의 당첨금을 분산 계산을 위해 `List<Long>`으로 쌓고 있다는 것이었고, retained heap 상위에 `winmoneyList`가 올라오는 걸로 확인했습니다. 분산은 모든 값을 저장하지 않아도 Welford's Online Algorithm으로 단일 패스 계산이 가능했기 때문에, 공간 복잡도를 O(N)에서 O(1)로 바꿔 스레드당 메모리를 20바이트로 줄였습니다. 부동소수점 누적 오차가 생긴다는 걸 알고 있었기 때문에 실제 오차율을 측정했고, 0.xx% 수준으로 변동성 지수 용도에는 허용 가능했습니다. 이 경험에서 얻은 건 세 가지입니다 — `-Xmx`는 원인을 가리는 수단이지 해결이 아니라는 것, 멀티스레드에서 스레드당 상태 크기가 입력에 선형으로 커지는 설계는 위험하다는 것, 그리고 알고리즘 교체로 인한 트레이드오프는 감이 아니라 측정으로 정당화해야 한다는 것입니다."

이 답변은 본 문서의 OOM 섹션, 프로파일링 루틴, JMH framing을 한 번에 끌어와 사용한다. 면접관은 "이 사람은 JVM을 플래그가 아니라 **인과 구조**로 이해하고 있다"고 받아들인다.

## 프로파일링 도구

**jcmd**. JDK 내장, 가장 먼저 손이 가는 도구.
```bash
jcmd <pid> VM.flags             # 현재 실행 중인 JVM 플래그
jcmd <pid> GC.heap_info         # 힙 요약
jcmd <pid> GC.class_histogram   # 클래스별 객체 수/크기
jcmd <pid> GC.heap_dump /tmp/heap.hprof
jcmd <pid> Thread.print         # 스레드 덤프
jcmd <pid> JFR.start duration=60s filename=/tmp/profile.jfr
```

**jstat**. GC 통계 실시간 스트리밍.
```bash
jstat -gcutil <pid> 1000
#  S0     S1     E      O      M     CCS    YGC    YGCT    FGC    FGCT    GCT
#  0.00  50.00  80.12  65.30  95.20  92.10   1234   12.34     3    1.50   13.84
```
`E`(Eden), `O`(Old) 사용률, `YGC`(Young GC 횟수), `FGC`(Full GC 횟수), `GCT`(누적 GC 시간).

**async-profiler**. CPU, allocation, lock 프로파일링을 JFR 없이 저렴하게. flame graph 출력이 강력하다.
```bash
./profiler.sh -d 60 -f flame.html <pid>
./profiler.sh -e alloc -d 60 -f alloc.html <pid>   # allocation hotspot
./profiler.sh -e lock  -d 60 -f lock.html <pid>    # contention
```

슬롯 시뮬레이터 케이스에서 `-e alloc`으로 떴다면 `AccumulateData.addWinMoney` → `ArrayList.add` 경로에서 allocation hotspot이 명확히 잡혔을 것이다.

**JFR(Java Flight Recorder)**. 오버헤드 1% 미만, 프로덕션 상시 on도 가능. `jcmd <pid> JFR.start`로 시작 → `.jfr` 파일을 **JDK Mission Control(JMC)**에서 분석.

**MAT(Eclipse Memory Analyzer)**. heap dump 분석 표준. **Leak Suspects**, **Dominator Tree**, **GC Roots까지의 경로** 이 세 기능만 쓸 줄 알면 대부분의 누수를 잡는다.

분석 루틴 예시 — "OOM이 떴다"면:
1. `-HeapDumpOnOutOfMemoryError`로 생성된 `.hprof`를 MAT에 로딩
2. Leak Suspects Report 먼저 열기
3. Dominator Tree에서 Retained Heap 큰 순서대로 상위 20개
4. 의심 객체의 GC Roots 경로 추적 → 어떤 정적 참조가 붙잡고 있는지 식별
5. **"이 객체가 원래 필요한가"**까지 질문을 올린다 (슬롯 시뮬레이터 사례 참고)

## Virtual Threads (Java 21+)

**기존 Platform Thread 모델의 한계**. 1 Java Thread = 1 OS Thread. 스택 1MB × 수만 스레드 = 메모리 폭발. 그래서 Tomcat, Netty, Spring MVC는 "스레드 풀 200개로 수천 RPS를 받기 위해" async, NIO, CompletableFuture, Reactor 등 비동기 프로그래밍을 동원해왔다.

**Virtual Thread**는 JVM이 관리하는 경량 스레드다. `Thread.startVirtualThread()` 또는 `Executors.newVirtualThreadPerTaskExecutor()`로 만든다. OS 스레드(= Carrier thread, ForkJoinPool 기반)에 올라탔다가, **블로킹 I/O를 만나면 언마운트해서 다른 가상 스레드에게 carrier를 양보**한다. 수만~수백만 개의 가상 스레드를 띄워도 OS 스레드는 CPU 코어 수만큼만 쓴다.

```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    IntStream.range(0, 10_000).forEach(i ->
        executor.submit(() -> {
            var response = httpClient.send(request, BodyHandlers.ofString());
            return response.body();
        })
    );
}
```

**언제 효과가 큰가**: 외부 HTTP 호출, DB 쿼리 대기 등 **블로킹 I/O가 많은 워크로드**. 기존에는 어쩔 수 없이 WebFlux로 갔던 코드를 "그냥 동기 스타일로 쓰고 Virtual Thread 위에 올리기"가 가능해진다.

**언제 효과가 없거나 주의해야 하는가**:
- CPU bound 작업(이미지 처리, 복잡한 계산, 대규모 시뮬레이션 루프) — 가상 스레드가 unmount되지 않으므로 이득 없음. Platform thread pool이 더 적합. 슬롯 시뮬레이터처럼 CPU에 얹혀 도는 루프는 Virtual Thread를 써도 메리트가 없다.
- `synchronized` 블록 안에서 블로킹 I/O — 기존 JVM은 pinning이 일어나 carrier를 점유. Java 21은 개선, Java 24+에서 대부분 해소. `ReentrantLock`으로 교체하면 안전하다.
- ThreadLocal 대량 사용 — 가상 스레드가 수만 개 생기면 ThreadLocal 복제 비용이 커진다. `ScopedValue`(Preview) 고려.

**Spring Boot 3.2+**는 `spring.threads.virtual.enabled=true` 한 줄로 Tomcat/Jetty 요청 처리를 가상 스레드 위에 올린다.

## CompletableFuture 합성 패턴과 구조화된 동시성

**CompletableFuture**는 비동기 합성의 표준.
```java
CompletableFuture<User> userFuture = async(() -> userService.find(id));
CompletableFuture<List<Order>> ordersFuture = async(() -> orderService.findByUser(id));

CompletableFuture<UserDetail> result = userFuture
    .thenCombine(ordersFuture, UserDetail::of)
    .orTimeout(2, TimeUnit.SECONDS)
    .exceptionally(ex -> UserDetail.fallback(id));
```

하지만 CompletableFuture는 **에러 전파와 취소 처리가 복잡**하다. 한 분기가 실패해도 다른 분기가 계속 돌아서 자원을 낭비한다.

**Structured Concurrency (Java 21 Preview, Java 25 GA 예정)**가 이를 풀려고 나왔다.
```java
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    Supplier<User>        user   = scope.fork(() -> userService.find(id));
    Supplier<List<Order>> orders = scope.fork(() -> orderService.findByUser(id));

    scope.join().throwIfFailed();
    return UserDetail.of(user.get(), orders.get());
}
```
하나가 실패하면 scope 전체가 취소된다. 부모-자식 관계가 명확해서 스택 트레이스가 의미 있게 연결된다. Virtual Thread와 짝을 이뤘을 때 진가가 나온다.

## StampedLock vs ReentrantReadWriteLock

후보자의 이전 학습 노트([StampedLock](./stamped-lock.md))에서 다룬 주제의 심화 정리.

**ReentrantReadWriteLock**. Read가 많고 Write가 적은 워크로드에서 여러 Read가 동시에 진행 가능. 재진입 지원. 하지만 Write가 끼어들면 Read가 블로킹되고, Read 락 자체도 비용이 있다.

**StampedLock**(Java 8+). 세 가지 모드:
- `writeLock()`: 배타 락, stamp 반환
- `readLock()`: 공유 락
- `tryOptimisticRead()`: **락을 실제로 잡지 않고** stamp만 받고 읽기 시도 → 끝나고 `validate(stamp)`로 "그사이 write가 없었는지" 검증. 없었으면 그대로 성공, 있었으면 read lock으로 fallback.

```java
double distanceFromOrigin() {
    long stamp = sl.tryOptimisticRead();
    double cx = x, cy = y;
    if (!sl.validate(stamp)) {
        stamp = sl.readLock();
        try { cx = x; cy = y; } finally { sl.unlockRead(stamp); }
    }
    return Math.sqrt(cx*cx + cy*cy);
}
```

**선택 기준**:
- 재진입 필요하면 `ReentrantReadWriteLock` (StampedLock은 재진입 미지원)
- 읽기 빈도 압도적으로 높고 짧은 critical section이면 `StampedLock`의 optimistic read
- `Condition`이 필요하면 `ReentrantReadWriteLock`

**함정**: StampedLock은 interrupt에 약하고, stamp를 잘못 관리하면 deadlock 위험이 높다. 인터뷰에서 "왜 StampedLock을 선택했는가"를 물으면 "read가 write의 20배 이상이었고, validate 실패율이 1% 미만임을 JMH로 확인했기 때문"처럼 **측정 기반 근거**를 댈 수 있어야 한다.

## JMH: 함정과 58배 개선 사례 framing

**마이크로벤치마크의 3대 함정**:
1. **Dead Code Elimination**: JIT이 결과를 쓰지 않는 코드를 제거. `Blackhole.consume(result)`로 방지.
2. **Warm-up 부족**: JIT 컴파일이 되기 전 해석 모드 측정치를 결과로 씀. `@Warmup(iterations = 5)`.
3. **Constant Folding**: 입력이 상수면 JIT이 계산을 컴파일 타임에 처리. `@State` + 런타임 입력 생성.

```java
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 5, time = 1)
@Measurement(iterations = 10, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class LockBenchmark {

    private final StampedLock stamped = new StampedLock();
    private final ReentrantReadWriteLock rw = new ReentrantReadWriteLock();
    private volatile int value = 42;

    @Benchmark
    public int stampedOptimistic() {
        long s = stamped.tryOptimisticRead();
        int v = value;
        if (!stamped.validate(s)) {
            s = stamped.readLock();
            try { v = value; } finally { stamped.unlockRead(s); }
        }
        return v;
    }

    @Benchmark
    public int rwRead() {
        rw.readLock().lock();
        try { return value; } finally { rw.readLock().unlock(); }
    }
}
```

**"58배 개선 사례" framing** (인터뷰에서 쓸 때):
"읽기 비율이 95% 이상인 캐시 조회 경로에서 ReentrantReadWriteLock이 CAS 경합으로 인해 스레드 64개일 때 성능이 역전되는 걸 JMH로 측정했습니다. StampedLock optimistic read로 교체하니 같은 조건에서 평균 응답 시간이 약 58배 개선되었습니다. 다만 이 수치는 critical section이 수 ns 수준인 경우에만 의미가 있고, 실제 비즈니스 로직이 섞인 경로에서는 이득이 2~3배 수준으로 떨어졌습니다. 그래서 **끝단 캐시**에만 적용하고 나머지는 유지했습니다."

마지막 문장이 핵심이다. 시니어는 "얼마나 빨라졌는가"가 아니라 "어디까지 적용하지 않았는가"를 같이 말한다. 슬롯 시뮬레이터 OOM 사례에서 "오차율 0.xx%까지 측정 후 적용 범위를 한정"한 것과 같은 감각이다.

## 로컬 실습 환경

```bash
# JDK 21 설치 (SDKMAN)
sdk install java 21.0.2-tem

# GC 로그 관찰용 Spring Boot 샘플
git clone https://github.com/spring-guides/gs-rest-service demo && cd demo/complete

./mvnw package

java -Xms512m -Xmx512m -XX:+UseG1GC \
     -XX:+HeapDumpOnOutOfMemoryError \
     -Xlog:gc*:file=gc.log:time,uptime,level,tags \
     -jar target/*.jar &

# 부하
ab -n 10000 -c 50 http://localhost:8080/greeting

# GC 실시간
jstat -gcutil $(pgrep -f spring-boot) 1000

# 스레드/힙
jcmd $(pgrep -f spring-boot) Thread.print | head -50
jcmd $(pgrep -f spring-boot) GC.heap_info

# JFR 60초
jcmd $(pgrep -f spring-boot) JFR.start duration=60s filename=prof.jfr
```

async-profiler로 Flame graph 생성:
```bash
./profiler.sh -d 30 -f cpu.html $(pgrep -f spring-boot)

# 슬롯 시뮬레이터 같은 allocation hotspot 재현/분석
./profiler.sh -e alloc -d 30 -f alloc.html $(pgrep -f spring-boot)
```

## 나쁜 패턴 vs 개선 패턴

**나쁨**: 페이징 없이 전체 로딩 → Heap OOM
```java
List<Order> all = orderRepository.findAll(); // 수백만 건
```
**개선**: Streaming + batch
```java
try (Stream<Order> s = orderRepository.streamAll()) {
    s.forEach(o -> process(o));
}
```

**나쁨**: 분산/평균 계산을 위해 전체 값 수집 → Heap OOM (슬롯 시뮬레이터 케이스)
```java
private final List<Long> winmoneyList = new ArrayList<>(); // 1억 건 누적
for (long i = 0; i < 100_000_000; i++) winmoneyList.add(spin());
double variance = computeVariance(winmoneyList); // O(N) 메모리
```
**개선**: Welford's Online Algorithm — O(1) 메모리
```java
var calc = WelfordOnlineCalculator.init();
for (long i = 0; i < 100_000_000; i++) calc.addWinMoney(spin(), bet);
double variance = calc.getVariance();
```

**나쁨**: 무제한 캐시
```java
Map<String, User> cache = new HashMap<>(); // 영원히 증가
```
**개선**: Caffeine으로 TTL + max size
```java
Cache<String, User> cache = Caffeine.newBuilder()
    .maximumSize(10_000)
    .expireAfterWrite(Duration.ofMinutes(10))
    .build();
```

**나쁨**: Virtual Thread 위에서 `synchronized` 안에 DB 호출
```java
synchronized (this) {
    repository.save(entity); // carrier pinning
}
```
**개선**: `ReentrantLock`
```java
lock.lock();
try { repository.save(entity); } finally { lock.unlock(); }
```

**나쁨**: ExecutorService 누수
```java
public Response handle() {
    var exec = Executors.newFixedThreadPool(10); // 매 요청마다 생성
    ...
}
```
**개선**: 빈으로 재사용 + 종료 hook.

**나쁨**: `-Xmx` 미지정으로 JVM 기본값에 의존 (슬롯 시뮬레이터 케이스의 트리거)
```bash
java -jar app.jar  # Xmx가 컨테이너 한도와 무관하게 설정됨
```
**개선**: 컨테이너 메모리의 50~70%로 명시
```bash
java -Xms4g -Xmx4g -XX:+HeapDumpOnOutOfMemoryError -Xlog:gc* -jar app.jar
```

## 인터뷰 framing: "서비스가 느려졌는데 GC 문제인지 어떻게 확인하나요"

STAR 구조로 정리한 모범 답변 뼈대:

**Situation**. "결제 API의 p99 응답 시간이 200ms에서 갑자기 1.2s로 튀었다는 알람이 왔다고 가정하겠습니다."

**Task / Approach**. "먼저 원인 후보를 세 가지로 좁힙니다. (1) 외부 의존성 지연, (2) DB 슬로우 쿼리, (3) JVM 자체 문제(GC/메모리/스레드). 첫 2분 안에 세 가설을 병렬 확인합니다."

**Action**.
"1단계 — GC 지표 확인. `jstat -gcutil <pid> 1000`으로 YGC/FGC 빈도와 Old 사용률을 봅니다. Full GC가 분당 수 회로 튀었는지, Old가 90%를 넘어서 안 내려오는지 확인합니다. 동시에 `-Xlog:gc*` 로그를 GCViewer로 열어서 pause time 분포와 throughput을 봅니다. Throughput이 90% 아래로 떨어졌으면 GC가 범인일 가능성이 큽니다.

2단계 — GC가 원인이면, Young이 작아서 Minor가 너무 잦은지 vs Old가 꽉 차서 Mixed/Full이 자주 도는지 구분합니다. 전자는 힙/Young 비율 조정으로 해결되고, 후자는 **메모리 누수**거나 **승격률**이 비정상적으로 높은 경우입니다.

3단계 — 누수가 의심되면 `jcmd <pid> GC.heap_dump`로 덤프 받아 MAT의 Leak Suspects로 돌립니다. 우리가 실제로 겪었던 사례 중 하나는 `ThreadLocal`에 요청 스코프 객체를 넣고 제거를 안 해서 Tomcat 스레드 풀이 계속 참조를 쥐고 있던 케이스였습니다.

4단계 — 누수가 아니라 **설계상의 대용량 누적**이면, retained heap 상위 객체의 **존재 이유 자체를 의심**합니다. 슬롯 시뮬레이터 OOM 케이스에서는 분산 계산을 위해 1억 개 당첨금을 리스트로 들고 있던 구조가 retained heap top이었고, 온라인 알고리즘으로 바꿔 O(N) → O(1)로 제거했습니다. 이 단계가 'JVM 튜닝'과 '설계 변경'의 경계입니다.

5단계 — GC가 아니면 async-profiler로 CPU flame graph를 뜹니다. 블로킹 호출이 특정 메서드에 집중되는지, lock contention(`-e lock`)이 있는지 확인합니다."

**Result framing**. "최종적으로 원인이 GC인지 아닌지 **두 개 이하의 지표**로 판단할 수 있어야 한다고 생각합니다. 저는 보통 `jstat`의 GCT 증가율과 GC 로그의 throughput, 이 두 개로 결정합니다. GC가 아니라는 걸 2~3분 안에 배제할 수 있으면 나머지 시간을 실제 원인에 쓸 수 있습니다. 그리고 GC가 맞다고 판단되면, 플래그 튜닝이 먼저인지 구조 변경이 먼저인지를 **임시 대응인지 근본 해결인지** 축으로 판단합니다."

이 답변의 핵심은 "도구 이름을 많이 나열하는 것"이 아니라, **판단 기준과 배제 로직이 명확한 것**, 그리고 **임시 대응과 근본 해결을 구분하는 사고 프레임**이 있다는 점이다.

## 체크리스트

- [ ] Heap, Metaspace, Thread stack, Direct memory 각각의 역할과 측정 방법을 설명할 수 있다
- [ ] Young/Old, 승격, STW를 Weak Generational Hypothesis와 엮어서 설명할 수 있다
- [ ] G1GC, ZGC, Shenandoah를 선택하는 기준을 워크로드로 설명할 수 있다
- [ ] `-Xms`, `-Xmx`, `MaxGCPauseMillis`, `G1HeapRegionSize`의 의미와 결정 원리를 안다
- [ ] `-Xlog:gc*` 로그에서 pause time, throughput, allocation rate를 뽑아낼 수 있다
- [ ] 4가지 OOM(Heap/Metaspace/Direct/GC overhead)을 구분하고 각각의 1차 대응을 안다
- [ ] `jcmd`, `jstat`, `async-profiler`, JFR, MAT을 실제로 실행해봤다
- [ ] Virtual Thread가 효과적인 워크로드와 그렇지 않은 워크로드를 구분할 수 있다
- [ ] CompletableFuture의 `thenCombine`, `orTimeout`, `exceptionally`를 합성할 수 있다
- [ ] StampedLock의 optimistic read와 ReentrantReadWriteLock을 **측정 근거로** 선택할 수 있다
- [ ] JMH의 3대 함정을 설명하고 `@Warmup`, `Blackhole` 사용법을 안다
- [ ] "서비스가 느려졌다"는 질문에 GC 여부를 배제하는 순서를 2분 안에 말할 수 있다
- [ ] 프로덕션 JVM 플래그에 `-XX:+HeapDumpOnOutOfMemoryError`와 GC 로그 설정이 반드시 들어가 있다
- [ ] **임시 대응(`-Xmx` 확장)과 근본 해결(알고리즘/구조 변경)을 구분해 설명할 수 있다** (슬롯 시뮬레이터 OOM 케이스)

---

## 관련 문서

- [Virtual Thread와 Project Loom](./virtual-thread.md) — 경량 스레드의 튜닝 고려사항
- [Java StampedLock](./stamped-lock.md) — 동시성 프리미티브 측정 선택
- [슬롯 시뮬레이터 OOM 해결](../task/nsc-slot/slot-simulator-oom.md) — 실전 OOM 케이스
- [ ] **멀티스레드 환경에서 스레드당 상태 크기가 입력에 선형으로 증가하는 설계**를 식별하고 위험성을 설명할 수 있다
- [ ] Heap OOM 진단 루틴의 마지막 단계로 **"이 객체가 원래 필요한가"**까지 질문을 올릴 수 있다
- [ ] 알고리즘 교체로 인한 오차/트레이드오프를 **수치로 측정해 정당화**한 경험이 있다 (Welford's 오차율 0.xx% 측정 사례)
