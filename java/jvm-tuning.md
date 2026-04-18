# [초안] JVM 튜닝: 시니어 Java 백엔드를 위한 GC·메모리·동시성 실전 가이드

## 왜 이 주제가 중요한가

실무 백엔드 서비스에서 "느려졌다"는 신고가 들어올 때, 신입은 코드를 본다. 시니어는 GC 로그를 본다. JVM 튜닝은 단순히 플래그 몇 개를 외우는 것이 아니라, **애플리케이션이 CPU/메모리/스레드 자원을 어떻게 쓰는지를 JVM 관점에서 역산하는 능력**이다. 이 능력은 크게 세 가지 상황에서 실전 가치가 폭발한다.

첫째, 레이턴시 SLO가 무너질 때다. p99 응답이 100ms에서 갑자기 1.5s로 튀면, 코드 변경이 없었다면 거의 대부분 GC pause 혹은 Safepoint 지연이 원인이다. 둘째, OOM이 난 뒤 재발 방지 회의에 불려갈 때다. "Heap을 늘렸다"는 답은 중간급 엔지니어의 답이고, "Heap이 아니라 Metaspace였고 클래스로더 누수가 원인이었다"는 답이 시니어의 답이다. 셋째, Java 21 이후 Virtual Threads가 들어오면서 기존 튜닝 상식 중 일부가 무효화되고 있다. 스레드 풀 크기 산정, 블로킹 I/O 재평가, backpressure 전략이 다시 설계 테이블 위에 올라왔다.

이 문서는 이 세 가지를 한 번에 훑을 수 있는 시니어용 체크포인트다. 개념 → 실습 → 안티패턴 → 면접 답변 순으로 구성했다.

---

## JVM 메모리 구조 다시 보기

JVM의 프로세스 메모리는 `-Xmx`에 잡히지 않는 영역이 훨씬 많다. 컨테이너 환경에서 OOMKilled가 나는 대부분의 원인이 여기에 있다.

**Heap (`-Xms`, `-Xmx`)**
- `new`로 만든 객체, 배열이 올라가는 공간.
- Young Generation(Eden + Survivor S0, S1)과 Old Generation으로 분리된다(G1은 논리적으로만).
- GC 대상이 되는 거의 유일한 영역.

**Metaspace (`-XX:MaxMetaspaceSize`)**
- 클래스 메타데이터, 메서드 바이트코드, 상수 풀.
- Java 8에 PermGen을 대체했고 **기본은 unbounded**다. 누수 시 컨테이너가 통째로 죽는다.
- 동적 프록시, CGLIB, Groovy, 핫스왑 도구가 많을수록 위험하다.

**Thread Stack (`-Xss`)**
- 스레드당 고정(기본 1MB 근처). 스레드가 5,000개면 약 5GB가 힙 바깥에서 사라진다.
- Virtual Threads는 이 제약을 정면으로 깬다(뒤에서 다룸).

**Direct Memory / Native Buffer (`-XX:MaxDirectMemorySize`)**
- `ByteBuffer.allocateDirect()`, Netty, gRPC, Kafka 클라이언트가 사용.
- Heap dump에 안 보인다. `jcmd <pid> VM.native_memory` 또는 NMT로 본다.

**Code Cache (`-XX:ReservedCodeCacheSize`)**
- JIT 컴파일된 네이티브 코드. 부족하면 JIT가 멈추고 성능이 조용히 절벽을 탄다.

실무 체크리스트: 컨테이너 memory limit을 `L`이라 할 때, `-Xmx`는 대략 `L * 0.5 ~ 0.7`로 잡는다. 나머지를 Metaspace, Direct, Stack, Code Cache, JVM 자체 오버헤드에 남겨야 한다. `-Xmx = L`로 잡는 설정은 거의 항상 사고를 부른다.

---

## GC 기본: Young / Old, 승격, Stop-the-world

**Weak Generational Hypothesis**: 대부분의 객체는 금방 죽는다. 이 가정 위에서 GC는 Young 영역을 자주, 빠르게 훑고, 살아남은 객체만 Old로 승격시킨다.

1. 객체는 Eden에 생성된다.
2. Eden이 차면 Minor GC(Young GC)가 돈다. 살아남은 객체는 Survivor로 복사.
3. Survivor를 여러 번 살아남으면(`-XX:MaxTenuringThreshold`, 기본 15) Old로 승격(promotion).
4. Old가 차면 Major GC / Mixed GC / Full GC가 돈다.

**Stop-the-world(STW)**: GC가 애플리케이션 스레드를 전부 멈추는 구간. Minor GC도 STW가 있지만 보통 수 ms. 문제는 Full GC의 STW로, 초 단위가 나올 수 있다. 시니어가 "GC 튜닝"이라고 할 때 실제로 말하는 것은 **STW의 빈도와 길이를 SLO 이내로 눌러 두는 작업**이다.

**Allocation rate**: 초당 얼마나 많은 바이트가 Eden에 할당되는가. GC 로그의 핵심 지표. 200MB/s를 넘어가면 Young GC가 너무 자주 돌고 p99가 흔들린다. 이때 답은 "힙을 늘린다"가 아니라 "불필요한 객체 할당을 찾아서 줄인다"인 경우가 더 많다.

---

## 현대 GC 비교: G1 vs ZGC vs Shenandoah

Java 17/21 기준 실무 선택지는 세 가지다.

### G1GC (기본값, Java 9+)
- 힙을 고정 크기 Region(`-XX:G1HeapRegionSize`, 기본 1~32MB 자동)으로 쪼개고 "가비지가 많은 Region부터" 수거.
- `-XX:MaxGCPauseMillis=200`(기본) 같은 **pause 목표**를 주면 G1이 Young 크기를 자동 조정.
- **언제 쓰나**: 힙 4~32GB, p99 요구가 100~300ms 수준, 워크로드 변동이 큰 일반 API 서버. 사실상 기본값.

### ZGC (Java 15 GA, Java 21 Generational ZGC)
- 대부분 구간이 동시(concurrent)로 동작. **STW는 거의 항상 1ms 미만**.
- Colored pointers + Load barrier로 동시 압축(compaction)까지 한다.
- **언제 쓰나**: 힙 16GB~수 TB, p99.9가 10ms를 요구, 금융·광고 입찰·실시간 피드. 2023년 이후 Generational ZGC가 들어오며 throughput 손실도 많이 줄었다.

### Shenandoah (RedHat, OpenJDK)
- ZGC와 유사하게 동시 압축. STW pause를 힙 크기와 거의 무관하게 낮게 유지.
- **언제 쓰나**: 힙이 크면서 저지연이 필요한데 Oracle JDK가 아닌 RedHat/Temurin 라인을 쓰는 경우.

### 실무 선택 트리
1. 힙 < 4GB, 레이턴시 덜 민감 → G1 기본값으로 충분.
2. 힙 8~32GB, 일반 API → G1 + `MaxGCPauseMillis` 튜닝.
3. p99.9 < 10ms가 비즈니스 요건 → ZGC(Generational) 1순위 검토.
4. throughput이 최우선 → Parallel GC도 여전히 후보(배치 잡).

---

## GC 튜닝 기본 플래그와 힙 크기 결정 원리

```
-Xms4g -Xmx4g                      # Xms == Xmx 로 고정 (리사이즈 비용 제거)
-XX:+UseG1GC                        # G1 명시
-XX:MaxGCPauseMillis=200            # pause 목표 (soft goal)
-XX:G1HeapRegionSize=8m             # 큰 객체(>Region/2)가 Humongous로 빠지는 것 방지
-XX:InitiatingHeapOccupancyPercent=45  # Old 점유율 이 값에서 Concurrent Marking 시작
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/app/
-Xlog:gc*,gc+age=trace,safepoint:file=/var/log/app/gc.log:time,level,tags:filecount=10,filesize=50m
```

**힙 크기 결정 원리 (시니어 관점)**:
1. **Live set size**를 먼저 측정한다. Full GC 직후 Old 점유량 = 진짜 장기 생존 객체. 이게 `L`이면 힙은 `L * 2.5 ~ 3` 정도가 출발점.
2. Allocation rate가 크면 Young 영역이 커야 Minor GC 빈도가 내려간다. G1에서는 `MaxGCPauseMillis`를 낮추면 Young이 작아지고, 높이면 커진다. 트레이드오프.
3. 컨테이너 메모리에서 JVM 자체 오버헤드(~512MB 이상) + Metaspace + Direct + Stack 총합을 뺀 나머지가 Heap.
4. "더 큰 힙 = 항상 좋음"은 거짓. 힙이 커질수록 Concurrent Marking 비용도, Full GC가 한 번 터질 때의 STW도 커진다.

---

## GC 로그 해석

Java 9+에서는 `-Xlog:gc*` 통합 로깅을 쓴다. 예시 로그:

```
[2.341s][info][gc] GC(12) Pause Young (Normal) (G1 Evacuation Pause) 512M->128M(2048M) 18.234ms
[2.890s][info][gc] GC(13) Pause Young (Concurrent Start) (G1 Humongous Allocation) 540M->150M(2048M) 22.100ms
[3.450s][info][gc] GC(14) Concurrent Mark Cycle
[5.120s][info][gc] GC(15) Pause Mixed (G1 Evacuation Pause) 800M->200M(2048M) 45.600ms
```

읽는 법:
- `Pause Young (Normal)` → 일반 Minor GC. 512M에서 128M로 줄었고 18ms 걸렸다. 좋은 상태.
- `G1 Humongous Allocation` → Region 절반 이상 크기 객체가 할당됨. 큰 배열/버퍼 풀을 의심.
- `Concurrent Mark Cycle` → Old 마킹 시작. STW 아님.
- `Pause Mixed` → Young + 일부 Old 동시 수거. G1 후반 단계.

**계산해야 할 3가지 지표**:
- **Pause time**: 각 GC 이벤트의 ms. p99, max를 본다.
- **Throughput**: `1 - (GC 총 시간 / 전체 시간)`. 95% 미만이면 의심.
- **Allocation rate**: `(Young 크기 변화) / 간격`. GCViewer, GCeasy.io에 로그를 올리면 자동 계산.

면접에서 "GC 로그 어떻게 보냐"는 질문이 나오면 반드시 이 세 숫자를 언급하라. 단순히 "pause를 본다"는 답은 주니어 답이다.

---

## OOM 4가지 유형과 대응

### 1. `java.lang.OutOfMemoryError: Java heap space`
- **원인**: Heap 부족. 진짜 로드가 많거나, 객체 누수(정적 컬렉션, 캐시 미방출, 리스너 등록 후 미해제).
- **대응**: `-XX:+HeapDumpOnOutOfMemoryError`로 덤프를 받고 **MAT(Eclipse Memory Analyzer)**의 Leak Suspects 리포트를 연다. Dominator Tree로 가장 많이 점유한 루트를 찾는다.

### 2. `java.lang.OutOfMemoryError: Metaspace`
- **원인**: 클래스로더 누수. 보통 동적 클래스 생성(CGLIB, Groovy, reflection 프록시) + 클래스로더가 GC되지 않는 상황.
- **대응**: `-XX:MaxMetaspaceSize`를 반드시 **명시**한다(무한 성장 방지). `jcmd <pid> VM.classloader_stats`로 누가 클래스를 찍어내는지 본다.

### 3. `java.lang.OutOfMemoryError: Direct buffer memory`
- **원인**: Netty 등이 DirectByteBuffer를 해제하지 않음. `-XX:MaxDirectMemorySize` 미설정 시 기본값이 Heap과 비슷해 탐지 지연.
- **대응**: `-Dio.netty.leakDetection.level=paranoid`, NMT(`-XX:NativeMemoryTracking=detail` + `jcmd VM.native_memory`).

### 4. `java.lang.OutOfMemoryError: GC overhead limit exceeded`
- **원인**: 힙이 거의 꽉 찬 상태에서 GC가 98% 시간을 쓰는데 2%도 못 회수. 사실상 heap space OOM의 전조.
- **대응**: 힙 자체 누수 수사 + 캐시 크기 제한(Caffeine의 `maximumSize`/`maximumWeight`).

---

## 프로파일링 도구

**jcmd** — 가장 먼저 쓸 스위스 나이프.
```bash
jcmd <pid> VM.flags                   # 실제 적용된 GC 플래그 확인
jcmd <pid> GC.heap_info               # 힙 현재 상태
jcmd <pid> GC.class_histogram          # 클래스별 인스턴스/바이트
jcmd <pid> VM.native_memory summary    # NMT (미리 -XX:NativeMemoryTracking 필요)
jcmd <pid> Thread.print                # 스레드 덤프
jcmd <pid> GC.heap_dump /tmp/heap.hprof
```

**jstat** — GC 1초 단위 모니터링.
```bash
jstat -gcutil <pid> 1000
#  S0     S1     E      O      M     CCS    YGC    YGCT    FGC    FGCT     GCT
#  0.00  45.32  67.12  72.45  98.21  95.43   125    2.345    3     0.892    3.237
```
- YGC 횟수/시간, FGC 횟수/시간을 1초 단위로 본다. 급증하는 구간이 장애 구간.

**async-profiler** — 샘플링 기반, 거의 오버헤드 없음.
```bash
./profiler.sh -d 30 -f /tmp/cpu.html <pid>          # CPU Flamegraph
./profiler.sh -d 30 -e alloc -f /tmp/alloc.html <pid>  # Allocation hotspot
./profiler.sh -d 30 -e lock -f /tmp/lock.html <pid>    # Lock contention
```
실무에서 "allocation rate가 높다"를 진단한 뒤 바로 `-e alloc`으로 어디서 만드는지 찾는 흐름이 표준.

**JFR (Java Flight Recorder)** — Java 11+ 무료, 상시 가동 가능.
```bash
jcmd <pid> JFR.start duration=120s filename=/tmp/app.jfr
# JDK Mission Control(JMC)로 열어서 분석
```

**MAT (heap dump 분석)**
- Leak Suspects 자동 리포트가 90% 사건을 해결.
- **Retained heap** vs **Shallow heap**을 구분: 해당 객체를 지우면 얼마가 해제되는가가 Retained.

---

## Virtual Threads (Java 21+)

플랫폼 스레드는 OS 스레드에 1:1로 매핑된다. 각 1MB 스택 + 컨텍스트 스위칭 비용 때문에 수만 개를 만들 수 없다. 그래서 우리는 늘 `ExecutorService` + 스레드 풀로 재사용했다.

Virtual Thread는 **JVM이 관리하는 경량 스레드**로, 블로킹 시 플랫폼 스레드(캐리어)에서 **unmount** 되어 캐리어를 해방시킨다. 결과적으로 블로킹 I/O를 하는 코드도 수십만 개 동시 요청을 "스레드 하나당 하나의 요청(thread-per-request)" 스타일로 짤 수 있다.

```java
// 기존
var pool = Executors.newFixedThreadPool(200);

// Java 21
var executor = Executors.newVirtualThreadPerTaskExecutor();
executor.submit(() -> {
    var user = userRepository.findById(id);      // JDBC 블로킹도 OK
    var profile = profileClient.fetch(user.id()); // HTTP 블로킹도 OK
    return render(user, profile);
});
```

**효과가 큰 경우**:
- I/O 바운드 서비스(외부 API 체인 호출, DB 여러 번 조회).
- 기존 WebFlux/Reactor로 가기엔 학습 비용이 큰 팀.

**효과가 작거나 오히려 해로운 경우**:
- CPU 바운드 작업(암호화, 이미지 처리) — 스레드를 아무리 늘려도 코어 수 이상은 못 쓴다.
- `synchronized` 블록 안에서 블로킹 — 캐리어를 **pin**시켜 unmount가 안 된다. Java 21에서 여전히 주의점, Java 24에서 개선 예정. `java.util.concurrent.locks`(ReentrantLock)로 대체.
- 스레드-로컬 기반 캐시(스레드 수가 폭증하면 캐시가 의미 없어짐).

**튜닝 포인트**:
- 더 이상 "스레드 풀 크기"를 고민하지 말고, **downstream에 대한 동시성 제한**(세마포어, Rate Limiter)을 상위에서 건다.
- DB 커넥션 풀 크기는 여전히 제한된다. Virtual Thread 10만 개가 동시에 `getConnection()`을 부르면 그대로 블로킹 큐에 줄 선다.

---

## CompletableFuture와 구조화된 동시성

Virtual Thread 이전/이후에도, 복수 API를 합성해야 할 때 CompletableFuture는 여전히 유용하다.

```java
CompletableFuture<User> u = supplyAsync(() -> userRepo.find(id), ex);
CompletableFuture<List<Order>> o = supplyAsync(() -> orderRepo.findByUser(id), ex);
CompletableFuture<Profile> p = supplyAsync(() -> profileClient.fetch(id), ex);

return CompletableFuture.allOf(u, o, p)
    .thenApply(v -> new Dashboard(u.join(), o.join(), p.join()))
    .orTimeout(500, TimeUnit.MILLISECONDS)
    .exceptionally(ex -> Dashboard.fallback());
```

**안티패턴**: `join()`을 체인 중간에 부르는 것. 그 순간 비동기가 끝난다.

**Java 21 Structured Concurrency (preview)**:
```java
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    var fUser = scope.fork(() -> userRepo.find(id));
    var fOrders = scope.fork(() -> orderRepo.findByUser(id));
    scope.join().throwIfFailed();
    return new Dashboard(fUser.get(), fOrders.get());
}
```
하나 실패하면 나머지도 자동 cancel. 에러 전파/타임아웃/취소가 try-with-resources 범위로 묶인다. CompletableFuture의 "orphan task" 문제를 근본적으로 푼다.

---

## StampedLock vs ReentrantReadWriteLock

공유 상태에 "읽기 훨씬 많고, 쓰기 드물다"는 조건이 있을 때 선택한다.

**ReentrantReadWriteLock**:
- 읽기 락끼리는 공유, 쓰기 락은 배타.
- 재진입 가능, 공정 모드 지원.
- 단점: 읽기가 몰리면 쓰기 기아(starvation) 가능, 읽기 락 획득/해제에도 CAS 비용.

**StampedLock (Java 8+)**:
- **Optimistic read**를 지원. 락 없이 stamp만 받고 읽은 뒤 `validate(stamp)`로 쓰기가 끼어들었는지만 확인.
- 재진입 불가, Condition 없음.

```java
private final StampedLock sl = new StampedLock();
private double x, y;

public double distanceFromOrigin() {
    long stamp = sl.tryOptimisticRead();
    double cx = x, cy = y;
    if (!sl.validate(stamp)) {              // 쓰기가 끼어들었다면 재시도
        stamp = sl.readLock();
        try { cx = x; cy = y; }
        finally { sl.unlockRead(stamp); }
    }
    return Math.sqrt(cx * cx + cy * cy);
}
```

실측상 읽기 비율이 95% 이상인 핫패스에서 RWLock 대비 수 배 처리량이 나온다. 다만 재진입, Condition, 업그레이드 시 코드가 까다로우니 **정말 병목일 때만** 쓴다. 일반 서비스 코드에서는 RWLock이 기본.

---

## JMH 마이크로벤치마크의 함정

`System.currentTimeMillis()` 기반 자체 측정은 거의 항상 거짓말이다. JIT가 충분히 데워지지 않았거나, 결과를 안 쓰는 계산을 dead code로 제거해 버린다. JMH는 이 문제를 해결한다.

```java
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 5, time = 1)
@Measurement(iterations = 10, time = 1)
@Fork(2)
public class HashBench {
    private String data;

    @Setup public void setup() { data = "x".repeat(1024); }

    @Benchmark
    public int baseline() {
        return data.hashCode();
    }

    @Benchmark
    public void sinkToBlackhole(Blackhole bh) {
        bh.consume(data.hashCode());     // dead code elimination 방지
    }
}
```

**함정 5가지**:
1. **Dead code elimination** — 반환값을 받지 않거나 Blackhole로 소비하지 않으면 JIT가 통째로 날린다.
2. **Constant folding** — 벤치마크 입력이 상수면 JIT가 컴파일 타임에 계산해 버린다. `@State`로 주입.
3. **Warm-up 부족** — 처음 몇 초는 인터프리터/C1 단계. `@Warmup`으로 최소 5회.
4. **Fork 수 1** — JVM 하나에서 모든 벤치를 돌리면 이전 벤치가 JIT 상태를 오염시킨다. `@Fork(2+)`.
5. **단일 스레드 가정** — 락/동시 구조를 볼 땐 `@Threads`로 명시.

실제 사례: 과거 `StampedLock` 기반 좌표 접근 구조를 만들면서 동일 연산을 `synchronized` → `ReentrantReadWriteLock` → `StampedLock optimistic read`로 바꾸며 JMH로 측정했더니, 읽기 95% 워크로드에서 처리량이 약 58배 차이가 났다. 이 숫자는 JMH가 아니었으면 **훨씬 작게 보였을 가능성**이 높다. Dead code elimination과 warm-up 차이가 결과를 20~100배씩 흔들기 때문이다. 시니어가 "58배 빨라졌다"라고 말할 때는 반드시 JMH 리포트와 함께 말해야 신뢰를 산다.

---

## 로컬 실습 환경

```bash
# JDK 21 (Temurin)
sdk install java 21.0.5-tem
sdk use java 21.0.5-tem

# async-profiler
curl -LO https://github.com/async-profiler/async-profiler/releases/latest/download/async-profiler-linux-x64.tar.gz
tar xzf async-profiler-linux-x64.tar.gz

# JMH skeleton
mvn archetype:generate \
  -DinteractiveMode=false \
  -DarchetypeGroupId=org.openjdk.jmh \
  -DarchetypeArtifactId=jmh-java-benchmark-archetype \
  -DgroupId=com.example -DartifactId=jmh-lab -Dversion=0.1
```

JVM 실습용 최소 실행 스크립트:

```bash
#!/usr/bin/env bash
java \
  -Xms512m -Xmx512m \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=100 \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/tmp/heap.hprof \
  -Xlog:gc*,safepoint:file=/tmp/gc.log:time,level,tags:filecount=5,filesize=10m \
  -XX:+FlightRecorder \
  -jar app.jar
```

부하는 `wrk`나 `k6`로 주면서 별도 터미널에서:
```bash
watch -n1 "jstat -gcutil $(pgrep -f app.jar) | tail -n +2"
```

---

## 안티패턴 vs 개선

**Bad 1: 힙만 키우면 된다**
```
-Xmx16g   # 커지면 해결되겠지
```
→ Full GC 한 번에 STW가 수 초. Allocation rate 자체가 문제라면 힙은 증상 완화일 뿐.

**Improved 1**: async-profiler `-e alloc`으로 할당 핫스팟 찾기 → 불필요한 `new byte[]`, 로그 포매팅, `String.format` 제거 → 그 다음에도 필요하면 힙 조정.

**Bad 2: 스레드 풀 크기를 무한대로**
```java
Executors.newCachedThreadPool()
```
→ downstream이 느려지면 스레드가 무제한 생성, 결국 OOM.

**Improved 2**: `ThreadPoolExecutor`로 coreSize/maxSize/queue를 명시하거나, Java 21 이상이면 Virtual Thread + 상위 세마포어.

**Bad 3: 모든 GC 문제는 G1으로 해결된다**
→ 힙 64GB + p99.9 5ms 요구 서비스라면 G1은 부족. ZGC Generational로 간다.

**Bad 4: JMH 없이 `System.nanoTime()`으로 "빨라졌다"고 주장**
→ JIT 상태에 따라 100배까지 튄다. JMH로 다시 측정.

---

## 면접 답변 framing: "서비스가 느려졌는데 GC 문제인지 어떻게 확인하나요"

시니어 답변 구조는 **관측 → 가설 → 검증 → 대응** 4단으로 짠다.

1. **관측**: 먼저 p99 레이턴시 악화 시점을 APM(Datadog/Pinpoint)에서 특정한다. 같은 시점에 GC time(%), heap used, Metaspace, 스레드 수 메트릭을 본다. p99 스파이크와 Young/Full GC pause가 겹치면 1차 용의자.
2. **가설**: 원인은 세 축으로 나눈다. (a) Allocation rate 급증(트래픽/페이로드 증가, 캐시 리빌드), (b) 누수성 증가(Old gen이 계속 우상향), (c) 설정 문제(컨테이너 메모리 대비 Xmx 과다, Metaspace 무제한).
3. **검증**:
   - `jstat -gcutil 1s`로 YGC/FGC 빈도·시간.
   - `-Xlog:gc*` 로그에서 allocation rate, pause time 분포.
   - 의심 시점에 `jcmd GC.heap_dump` + MAT로 Dominator Tree.
   - async-profiler `-e alloc`로 할당 핫스팟.
4. **대응**:
   - Allocation rate 문제 → 코드 레벨에서 할당 제거.
   - 누수 → 원인 클래스로더/캐시 수정 후 배포.
   - pause 자체 문제 → G1 → ZGC 전환 또는 `MaxGCPauseMillis` 재조정.
   - 진짜 로드 증가 → scale-out과 힙 재산정(Full GC 직후 live set × 2.5).

**피해야 할 답변**: "힙 덤프 떠서 봅니다" 단독 답변. 이건 도구 이름일 뿐, 방법론이 아니다. 반드시 "먼저 메트릭으로 GC 구간을 특정하고, 그 시점의 힙 덤프와 프로파일을 교차 확인"이라고 말해야 한다.

---

## 체크리스트

**메모리 / 설정**
- [ ] `-Xms == -Xmx` 고정 (리사이즈 비용 제거, 컨테이너 OOMKill 방지)
- [ ] 컨테이너 limit 대비 `-Xmx`는 50~70%
- [ ] `-XX:MaxMetaspaceSize` 명시
- [ ] `-XX:MaxDirectMemorySize` 명시 (Netty/Kafka 쓰면 필수)
- [ ] `-XX:+HeapDumpOnOutOfMemoryError` + HeapDumpPath
- [ ] `-Xlog:gc*` 롤링 파일로 상시 기록

**GC 선택**
- [ ] 힙 32GB 이하 일반 API → G1
- [ ] p99.9 10ms 미만 요구 → ZGC (Generational)
- [ ] `MaxGCPauseMillis` 기본 200에서 SLO에 맞춰 조정

**관측**
- [ ] APM에서 GC time(%) 메트릭 대시보드 상주
- [ ] 배포마다 `jcmd VM.flags`로 실제 적용 플래그 기록
- [ ] JFR 상시 수집(오버헤드 ~1%)

**코드**
- [ ] Virtual Thread 쓴다면 `synchronized` 블록에서 블로킹 금지 → `ReentrantLock`
- [ ] DB 커넥션 풀 크기는 Virtual Thread와 무관하게 별도 산정
- [ ] 핫패스 벤치마크는 JMH로, `@Fork(2+) @Warmup(5) @Measurement(10)` 최소 기준
- [ ] StampedLock은 읽기 95%+ 핫패스에서만, 그 외는 ReentrantReadWriteLock

**면접**
- [ ] "GC 문제인가요?" 질문에 관측→가설→검증→대응 4단으로 답할 수 있는가
- [ ] OOM 4가지 유형과 각 진단 명령어를 구분해 말할 수 있는가
- [ ] G1 vs ZGC 선택 기준을 힙 크기와 p99 SLO로 설명할 수 있는가
- [ ] Virtual Thread가 "스레드 풀 크기 고민을 끝냈다"는 말의 정확한 의미와 예외 상황(pin, CPU 바운드)을 설명할 수 있는가
