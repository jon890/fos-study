# Virtual Thread와 Project Loom

## 히스토리

### 2017 - Proejct Loom 공식 제안

- OpenJDK에서 자바의 동시성 모델을 근본적으로 바꾸자는 목표로 시작
- 기존 OS 스레드 기반 모델의 한계
  - 스레드 생성 비용 큼 (1MB stack)
  - context switching 무거움
  - 수십만 단위 concurrency 불가
- 목표
  - Lightweight user-mode thread (Fiber / Virtual Thread)
  - Continuation API
  - Structured Concurrency
- 이 때는 주로 실험적 개념 정의 단계, 실제 구현 없음

### 2018 ~ 2019년 - 초기 Fiber 구현 (실험용)

- Fibers 라는 이름으로 가장 처음 구현되기 시작
- Go의 goroutine, Kotlin coroutine처럼 user-mode 스케쥴링 실험
- 이 시기 아키텍쳐 핵심
  - Continuation 기반 fiber scheduler 구현
  - blocking call을 non-blocking으로 바꾸지 않고도 높은 동시성 구현

### 2020년 - Virtual Thread 정식 방향 결정

- Fiber -> Virtual Thread 개념으로 정리됨
- 이유
  - Java는 기존 Thread API를 그대로 사용하고 싶어함 (thread 개념 유지)
  - 개발자 입장에서 새로운 API 학습 비용을 최소화하려는 목적
- 핵심 철학
  - 기존 자바 코드를 변경하지 않고 곧바로 10만/100만 concurrency를 가능하게 하자
- 이 때 부터 실제 스펙이 빠르게 안정화되기 시작

### 2021년 - Structured Concurrency 소개

- Virtual Thread만 도입하면 코드는 concurrency가 오히려 복잡해짐 -> 해결책 도입
- Structured Concurrency의 핵심
  - Task의 lifecycle이 부모-자식 구조로 정리됨
  - 예외/취소 전파가 명확해짐
  - scoped concurrency로 안정적 제어 가능

```java
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    var r1 = scope.fork(() => task1());
    var r2 = scope.fork(() => task2());
    scope.join();
    scope.throwIfFailed();
}
```

### 2022년 - JDK 19에서 Preview 기능 출시

- Virtual Thread (Preview)
- Structured Concurrency (Incubator)
- Scoped Values (Incubator)

실무에서 테스트할 수 있는 수준이 됨

### 2023년 - JDK 21에서 Virtual Thread 정식 출시

- JDK 21 (LTS)에 Virtual Thread가 정식 기능(Stable)로 들어감
- JDK 21의 핵심 변화
  - Virtual Thread가 기본 Java API에 완전히 통합됨
  - ThreadBuiler API 추가
  - 대부분의 blocking I/O가 virtual thread friendly 방식으로 동작
  - Executors.newVirtualThreadPerTAskExecutor() 정식 포함
- 실무적 의미
  - 자바도 이제 Go, Kotlin, Erlang 처럼 `1 스레드 = 1 작업` 모델을 기본으로 채택 가능

### 2024 ~ 2025 - Structured Concurrency 안정화 및 성능 최적화

- Structured Concurrency가 preview 단계를 넘어서 안정화 중
- Virtual Threaad 스케줄링 성능 지속 개선
- 향후 목표
  - IO 속도 & native call 대응 강화
  - 애플리케이션 서버들의 Virtual Thread adoption 확대

## 위 내용을 바탕으로 궁금점

### 왜 OS 스레드를 만들 때의 비용은 큰가? (1MB 메모리를 차지한다고 하는데)

- OS 스레드는 커널이 직접 관리하는 커널 리소스이기 때문에, 스레드를 하나 만들거나 스케줄링할 떄 다음과 같은 비용이 발생
- 스택 메모리를 (1MB ~ 8MB)를 미리 할당해야 함
  - OS 스레드는 고정 크기 스택을 미리 확보해야 함 (JVM 기본 스택 : OS에 따라 보통 1~2MB)
  - 즉, 스레드 10만 개를 만들면 100GB 메모리가 필요 -> 불가능
- 많은 동시 커넥션을 처리하는 게임 서버에서 OS 스레드가 적합하지 않은 이유가 됨

### 컨텍스트 스위칭 관점에서는 결국, 스레드를 스케줄링하고 컨텍스트를 스위칭해야하는데 왜 가상 스레드 모델이 더 빠른가?

- 커널 수준의 Context Switching 비용

  - CPU 레지스터 저장
  - 커널 스택 교체
  - TLB FLush
  - CPU 캐시 miss 증가
  - 커널 모드 <-> 유저모드 전환
  - 이는 수백 ns ~ 수 us 단위의 비용을 소모

- 커널이 동시성 제한

  - OS가 스레드를 관리하므로 너무 많은 스레드를 만들면 run queue가 길어져 스케줄러 부담 증가
  - 문맥 전환 비용이 더 커짐
  - 실제로 JVM에서 스레드가 4~5000개를 넘으면 서버가 불안정 해짐

- 왜 Virtual Thread는 훨씬 빠르고 가벼운가?

  - JVM 내부에서 관리되는 user-mode thread다.

- 스택을 필요할 때만 사용하며, 크기도 매우 작고 가변적

  - 초기 스택이 매우 작음 (수 KB 정도)
  - 스레드가 블로킹되면 스택을 힙으로 스냅샷 떠서 옮겨두고, 다시 필요하면 복원함
  - 따라서 수십만 ~ 수백만 개도 만들 수 있다.

- 컨텍스트 스위치가 JVM 내부에서 이루어짐

  - JVM이 자체 스케줄러(ForkJoinPool 기반)을 사용
  - 유저 모드에서 스위칭
  - OS 컨텍스트 전환 없음
  - 비용이 ns ~ 수십 ns 수준으로 매우 작음

- 시스템 콜을 거의 발생시키지 않음

  - 가상스레드는 블로킹 IO를 만나면
    - 해당 virtual thread를 unmount (OS thread에서 분리)
    - 다른 virtual thread를 mount
    - IO 완료 후 다시 mount
  - 이 과정은 전부 JVM이 수행하므로 시스템 호출로 인한 비용이 거의 없음
  - 기존의 비동기 IO(CompletableFuture, NIO)를 코드 수정 없이 "동기 코드 그대로" 사용할 수 있게 해줌

- 스케줄링 방식 자체가 경량
  - OS 스레드는 preemptive shheduling(선점형), 가상스레드는 cooperative scheduling(협력형) 성격이 강함
  - IO에서 자연스럽게 yield가 발생하기 때문에 스케줄러 부담이 적다.

### Platform Thread와 Virtual Thread는 무엇인가?

- Platform Thread
  - 우리가 자바에서 알던 기존 쓰레드 = `java.lang.Thread`
  - 내부적으로 OS 스레드 1:1 매핑
  - 스레드를 많이 만들수록 커널 스레드가 늘어나서 문맥 전환비용, 메모리 비용이 커짐
- Virtual Thread

  - Java 21에서 정식으로 들어온 경량 스레드
  - JMV이 관리하는 유저 레벨 스레드
  - 내부적으로는 여러 Virtual Thread가 소수의 Platform Thread 위에서 multiplexing 됨
  - 구조적으로는 Go의 goroutine, Kotlin coroutine과 비슷한 개념

### Virtual Thread는 어떻게 스케줄링 되는가?

- Virtual Thread = 작업단위 / 사용자 코드 스택을 잡고 있다가

  - 실행해야 할 때 Platform Thread위에 붙었다가 = run
  - I/O 블로킹, `park()`같은 지점에서 떨어져 나왔다가 = unmount
  - 다시 실행 가능할 떄 다른 Platform Thread에 다시 붙는다 = remount

- 예를 들어, Virtual Thread에서 JDBC 호출 같은 블로킹 I/O를 호출하면, JVM은 해당 Virtual Thread의 스택과 상태를 저장해두고 Platform Thread를 다른 작업에 재사용합니다.
- I/O가 완료되면 Virtual Thread는 다시 어떤 Platform Thread 위에서 재개됩니다.
- 이렇게 해서 OS 스레드 수를 최소화하면서도 수많은 동시 요청을 처리할 수 있는 구조가 됩니다.

### 그렇다면 Platform Thread를 Blocking 시키면 어떻게 되는가?

- 라이브러리가 내부에서 OS-level blocking call을 호출하면, 가볍게 동작할 수 없다
- virtual thread는 사용하는 라이브러리가 논블로킹 친화적일 때만 고성능이다.
- Platform thread를 블락하는 호출은 어떤 것이 있는가?
  - Socket I/O (read, write, accept)
    - InputStream.read(), SocketChannel.read(), ServerSocket.accept() 등이 해당
    - Virtual Thread는 이 호출을 만나면 Carrier Thread를 점유하게 됨
  - File I/O
    - POSIX file I/O syscall은 기본적으로 블로킹
    - Java의 Files.readAllBytes() 등이 해당
  - Lock 경합
    - synchronized 블록 안에서 오래 기다리면
    - Virtual thread가 Park -> Unpark 흐름으로 전환되지만 경합이 심한 경우 carrier thread 점유 시간이 늘어남
- 그렇다면 Virtual Thread는 블로킹 I/O에서 어떻게 최적화하는가?
  - 블로킹을 만나면 그 지점을 스케줄러가 파악하고 carrier thread에서 떼어냄 (PARK)
  - 다른 Virtual Thread가 carrier thread를 사용함
  - 이 기능을 제공하는게 continuation 이다.
- 단 조건이 있는데..
  - JVM이 파킹 지점을 알아야 한다
  - 라이브러리가 native blocking syscall을 감추고 있을 경우 JVM은 파킹 지점을 잡지 못함
  - 대표적으로 문제 되는 라이브러리 : DB Driver
  - 기본적으로 블로킹 소켓 I/O 기반
  - MySQL Driver는 Loom 대응이 되었을까?
    - 아직 완전한 대응을 하지 않음
    - 내부 I/O가 기본적으로 blocking socket
    - JVM이 continuation을 삽입할 수 없는 native 호출 흐름이 있음
- 핵심 요약
  - Virtual Thread는 블로킹처럼 보이지만 실제는 논블로킹을 만들기 위한 기술
  - 하지만 라이브러리가 블로킹 syscall을 숨기고 있으면 Carrier Thread 블로킹이 발생해 성능이 저하된다

### 자바 소켓 라이브러리가 NIO로 동작하도록 개선되지 않았는가?

- Java 8
  - 전통적 object 소켓
- Java 11
  – 일부 NIO 기반 내부 변경
- Java 14
  - 내부 리팩토링 / 최적화
- Java 21

  - 블라킹 되나, Virtual Thread가 park됨

- 내부적으로 NIO 채널 구현을 일부 재사용하는 수준
