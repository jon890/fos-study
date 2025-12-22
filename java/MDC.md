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
