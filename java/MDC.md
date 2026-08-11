# MDC (Mapped Diagnostic Context)

- 현재 실행 흐름(Thread)에 key-value 형태의 컨텍스트를 붙여두는 공간

```java
MDC.put("traceId", "abc-123");
log.info("주문 생성");
// [traceId=abc-123] 주문 생성
```

- 로그를 찍을 때마다 매번 traceId를 파라미터로 넘기지 않아도 됨
- Logback / Log4j / SLF4J에서 공통 지원

## MDC의 핵심 원리

- MDC는 ThreadLocal 기반
  - MDC 값은 **현재 스레드에만 저장**
  - 같은 요청 처리 흐름에서는 자동으로 유지됨
  - 다른 요청/스레드에는 전파 X

```text
HTTP 요청
 └─ Thread-1
     ├─ MDC.put(traceId)
     ├─ log()
     ├─ log()
     └─ 요청 종료 → MDC 제거
```

### ThreadLocal이라서 생기는 두 가지 사고

"현재 스레드에만 저장"은 편의가 아니라 제약이다.
스레드가 바뀌는 순간 두 방향으로 깨진다.

**1. 비동기로 넘기면 traceId가 사라진다**

`@Async`, `CompletableFuture`, `ExecutorService` 어디든 마찬가지다.
작업이 다른 스레드에서 돌기 때문에 MDC가 따라가지 않는다.

```java
MDC.put("traceId", "abc-123");
log.info("제출 전");                       // [traceId=abc-123] 제출 전

executor.submit(() -> log.info("작업 안")); // [traceId=] 작업 안  ← 비어 있다
```

넘기려면 **제출하는 쪽에서 복사해 작업 스레드에서 다시 심어야** 한다.

```java
Map<String, String> context = MDC.getCopyOfContextMap();

executor.submit(() -> {
    Map<String, String> previous = MDC.getCopyOfContextMap();
    if (context != null) MDC.setContextMap(context);
    try {
        log.info("작업 안");               // [traceId=abc-123] 작업 안
    } finally {
        // 풀 스레드는 재사용되므로 원래 상태로 되돌린다
        if (previous != null) MDC.setContextMap(previous);
        else MDC.clear();
    }
});
```

Spring이라면 매번 이렇게 감싸는 대신 `TaskDecorator`로 한 번만 심어두는 편이 낫다.

**2. 정리하지 않으면 남의 traceId가 찍힌다**

이쪽이 더 잘 안 보이는 사고다.
스레드 풀은 스레드를 재사용하므로, 요청이 끝날 때 `MDC.clear()`를 빼먹으면
그 값이 다음 요청에 그대로 남는다.

```text
Thread-8 ── 요청 A: MDC.put(traceId=A) ... 응답 (clear 누락)
Thread-8 ── 요청 B: MDC.put 안 함      ... 로그에 [traceId=A] 가 찍힘
```

- 로그가 비는 게 아니라 **틀린 값이 찍히므로** 장애 추적에서 엉뚱한 요청을 쫓게 된다
- 그래서 Filter나 Interceptor에서 `finally { MDC.clear(); }`가 필수다

## MDC로 어떻게 "분산 추적"이 되는가?

- 핵심은 **traceId를 서비스 간에 전달**하는 것
- 예시:

```text
Client -> Service A -> Service B -> Service C
```

### 최초 진입 지점 (Service A)

- traceId 생성
- MDC에 저장
- 응답/요청 헤더에 포함

```java
String traceId = UUID.randomUUID().toString();
MDC.put("traceId", traceId);
```

```http
X-Trace-Id: abc-123
```

### Service A -> Service B 호출

- HTTP Header에 traceId 전달

```http
GET /api
X-Trace-Id: abc-123
```

### Service B 수신

- Header에서 traceId 추출
- MDC에 다시 세팅

```java
String traceId = request.getHeader("X-Trace-Id");
MDC.put("traceId", traceId);
```

### 결과

- 모든 서비스 로그에 **같은 traceId**

```text
[traceId=abc-123] Service A 요청 수신
[traceId=abc-123] Service B 주문 조회
[traceId=abc-123] Service C 결제 처리
```

- 로그 수집 시스템에서 `traceId=abc-123` 검색
- -> 전체 호출 경로 복원 가능

### 이게 왜 "분산" 추적인가?

- MDC 자체는 **로컬(Thread) 개념**
- **traceId를 네트워크로 전달**하면서
- 분산 시스템 전체를 하나의 "논리적 트랜잭션"으로 묶음

> MDC = 로컬 컨텍스트 <br />
> traceId 전파 = 분산 연결고리
