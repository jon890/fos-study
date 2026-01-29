# AsyncItemProcessor

## 1. 아키텍처 및 Executor 구성

이 구조의 핵심은 **읽기는 동기, 처리는 비동기, 쓰기는 동기(Future Unwrapping)**이다.

- **1. ItemReader (Main Thread)**:
  - 단일 스레드에서 Chunk Size만큼 데이터를 순차적으로 읽는다.
  - 따라서 **Reader에는 Executor가 필요 없다.**
- **2. AsyncItemProcessor (Main Thread -> Worker Threads)**:
  - Main 스레드가 읽은 데이터를 받아 `TaskExecutor`에 작업을 제출(Submit)한다.
  - 즉시 `Future<T>`를 리턴하고 다음 데이터를 받는다.
  - **여기에만 `ExecutorService(TaskExecutor)`가 필요하다.**
- **3. AsyncItemWriter (Main Thread)**:
  - `ASyncItemWriter`는 `List<Future<T>>`를 받는다.
  - 내부적으로 루프를 돌며 `Future.get()`을 호출해 결과가 나올 때까지 기다린다.
  - **따라서 Writer는 별도의 Executor를 가지지 않으며, Main 스레드에서 동작한다**

> 핵심: Writer가 `Future.get()`으로 대기하는 동안, Processor의 스레드 풀에서는 병렬로 로직이 수행된다. <br>
> Writer는 단지 "결과 수집기" 역할을 할 뿐이다.

## 2. Chunk Size vs Thread Pool Size는 어떻게 조정해야할까?

`AsyncItemProcessor`를 사용할 떄 성능 병목은 **Chunk Size와 Thread Pool Size의 불일치**에서 발생한다.

- **A. 이상적인 비율 (1:1)**:
  - 권장 설정: `Thread Pool Size` >= `Chunk Size`
  - 이유: Reader가 Chunk(100개)를 다 읽어서 Processor에 넘기면, Processor는 순식간에 100개의 Task를 스레드 풀에 던진다.
    - 만약 `Chunk=100`, `Pool=10`이라면?
    - 10개만 돌고 90개는 큐에서 대기한다.
    - Writer는 100개가 다 끝날 때까지 기다려야 하므로, 전체적인 처리 시간은 **가장 늦게 끝나는 작업**에 맞춰진다.
    - 따라서 한 청크 내의 아이템들이 **최대한 동시**에 실행되도록 맞추는 것이 베스트이다.
- **B. 현실적인 제약 (DB Connection Pool)**
  - 하지만 무작정 스레드 풀을 늘릴 수 없는 결정적인 이유가 **DB 커넥션**이다.
  - **Processor 내부에서 DB 조회/저장이 일어난다면?**
    - `Thread Pool Size`가 100이어도 `HikariCP Maximum Pool Size`가 10이라면, 나머지 90개 스레드는 DB 커넥션을 얻기 위해 블락 상태가 된다. 컨텍스트 스위칭 비용만 낭비하게 된다.
- **C. 실무 튜닝 가이드**
  - 1. I/O Bound 작업 (API 호출 등)인 경우:
    - Chunk Size: 100 ~ 200
    - Thread Pool: Chunk Size와 **1:1**로 맞춘다. (CPU를 안 쓰므로 스레드를 많이 늘려도 됨)
    - DB 연결: 필요 없다면 스레드 풀을 더 늘려도 무방하다.
  - 2. DB Bound 작업 (JPA 조회 등)인 경우:
    - DB Connection Pool: 먼저 DB가 버틸 수 있는 최대 커넥션 수를 확보한다.
    - Thread Pool: 커넥션 풀 개수에 맞춘다.
    - Chunk Size: Thread Pool 사이즈와 같거나 배수로 맞춘다.

## 우리 현재 구조에서 개선해볼점 -> 모든 I/O 처리는 Processor에서 담당하고, 가벼운 순수 Write 작업만 Writer로 ㄴ마긴다

- **현재 구조의 문제점**:
  - AsyncItemWriter는 비동기 결과가 완료될 떄 까지 메인 스레드에서 기다린 후, 결과를 꺼내서 **동기적으로** `delegate writer`를 실행한다.
  - 만약 Writer 단계에 'Docling 파싱'이나 '임베딩 요청'같은 무거운 I/O가 남아있다면, **Processor에서 아무리 병렬로 처리해도 Writer(메인 스레드)가 하나씩(혹은 청크 단위로) 순차 처리하느라 전체 속도가 떨어진다**
- **해결책**:
  - **무거운 I/O를 모두 Processor로 옮기자.**
  - Writer는 오직 가공된 데이터를 OpenSearch에 저장(Bulk Insert)하는 역할만 남겨야 한다.

## 추가팁

### A. Java 21 Virtual Threads (강력 추천)

만약 프로젝트가 **Java 21 + Spring Boot 3.2 이상**이라면, 복잡한 스레드 풀 튜닝 없이 **가상 스레드(Virtual Threads)**를 쓰자. <br>
I/O Bound 작업에서 압도적인 효율을 보여준다.

```kotlin
@Bean
fun taskExecutor(): TaskExecutor {
    return SimpleAsyncTaskExecutor().apply {
        setVirtualThreads(true)
    }
}
```

이 경우 Chunk Size만 API 허용량에 맞춰 조절하면 된다.

### B. API Rate Limiting (429 Error) 대비

병렬 처리를 극대화하면 Confluence API나 임베딩 서버에서 `429 Too Many Requests`를 뱉을 수 있다.

- **Resilience4j**의 `RateLimiter`나 `Retry`를 Processor 내부 로직에 적용하여, 요청 실 패 시 잠깐 대기했다가 재시도하도록 안전장치를 마련하자.
