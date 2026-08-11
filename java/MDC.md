# 로그에 traceId 남기기 — MDC 부터 OpenTelemetry 까지

로그를 보다가 "이 로그와 저 로그가 같은 요청인가"를 알 수 없으면 장애 추적이 멈춘다.
그 연결고리를 만드는 것이 `traceId`이고, 로그에 그 값을 붙이는 도구가 MDC다.

이 글은 MDC로 직접 붙이는 방식에서 시작해,
OpenTelemetry가 그 일을 어디까지 대신해 주는지까지 이어서 본다.

## MDC (Mapped Diagnostic Context)

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

여기까지가 **손으로 하는 방식**이다.
`UUID`를 만들고, 헤더에 싣고, 받는 쪽에서 꺼내 다시 `MDC.put` 한다.
서비스가 셋을 넘어가면 이 코드가 서비스마다 반복된다.

## OpenTelemetry는 이 일을 어디까지 대신하는가?

`traceId`를 만드는 주체가 우리에서 SDK로 넘어간다.

```text
HTTP 요청 수신
 └─ OTel Instrumentation
     ├─ Trace 생성
     ├─ traceId / spanId 생성
     ├─ Context에 저장
     └─ 다음 처리로 전달
```

| 우리가 하는 일 | OTel이 대신하는 일 |
| --- | --- |
| 의존성 추가 | `UUID` 생성 |
| Instrumentation 활성화 | `MDC.put("traceId", ...)` |
| Exporter 설정 | 헤더 수동 파싱과 전파 |

### 추적 모델이 더 정밀해진다

MDC로 하면 요청 하나에 `traceId` 하나다.
OTel은 그 안을 다시 나눠 호출 트리를 만든다.

```text
Trace (하나의 요청)
 ├─ Span: HTTP Server
 │   ├─ Span: DB Query
 │   └─ Span: Redis
 └─ Span: HTTP Client (다른 서비스)
```

- `traceId` — 전체 요청을 묶는 ID
- `spanId` — 각 작업 단위

"이 요청이 느렸다"에서 멈추지 않고 "그중 DB 조회가 느렸다"까지 좁혀진다.

### 전파는 표준 헤더로

앞에서 직접 만든 `X-Trace-Id` 대신 W3C Trace Context 표준을 쓴다.

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

- 생성, 파싱, 전파가 모두 자동이다
- 표준이라 다른 언어·프레임워크로 만든 서비스와도 그대로 이어진다

## 그럼 MDC는 이제 필요 없나?

아니다. 둘은 역할이 다르다.

| 역할 | 담당 |
| --- | --- |
| 분산 트레이싱 | OpenTelemetry |
| 로그 상관관계 | MDC |
| 시각화 | Tempo / Jaeger |
| 로그 검색 | NHN Log & Crash |

OTel이 만든 `traceId`를 **로그에 찍으려면 결국 MDC를 거쳐야** 한다.
그 연결은 자동 브릿지가 해준다.

```text
OTel Context
   ↓
Logback MDC Bridge
   ↓
로그에 traceId 출력
```

- Spring Boot에 OTel Instrumentation을 붙이면 `traceId`와 `spanId`가 MDC에 자동 주입된다
- 로그 패턴에 `%X{trace_id}`를 쓸 수 있다

즉 **traceId는 OTel이 만들고, MDC는 로그 출력을 위해 자동으로 받아쓴다.**

앞의 "ThreadLocal이라서 생기는 두 가지 사고"는 이 구조에서도 그대로 유효하다.
브릿지가 값을 넣어줄 뿐, 저장 위치는 여전히 ThreadLocal이기 때문이다.

## OTel이 항상 답은 아니다

여기까지 읽으면 "그럼 OTel을 넣으면 되겠네"로 끝나기 쉽다.
실제로 도입을 검토했다가 **넣지 않기로 한 적이 있다.**

게이트웨이 뒤에 API 서버와 모델 서버가 있는 구조에서
"한 요청의 로그를 처음부터 끝까지 묶어 보고 싶다"가 목적이었다.
OTel과 W3C Trace Context가 정석이지만 두 가지가 걸렸다.

- **게이트웨이가 `traceparent`를 보내지 않았다.** 표준을 쓰려면 앞단에 propagator를 따로 붙여야 했다
- **trace 백엔드가 없었다.** span을 모아 시각화할 곳이 없으니 OTel의 강점인 호출 트리를 쓸 데가 없다

반면 게이트웨이는 이미 `X-Request-Id`를 발급하고 있었다.
그 값을 그대로 받아 MDC에 넣고 다음 서비스로 넘기는 것만으로 목적이 달성됐다.

여기서 갈린 기준은 **"span 단위 추적이 필요한가, 로그 상관관계면 되는가"** 였다.

| 필요한 것 | 맞는 도구 |
| --- | --- |
| 이 요청의 로그를 한데 모아 보기 | 헤더 하나와 MDC |
| 이 요청 안에서 어디가 느렸는지 보기 | OpenTelemetry, 그리고 trace 백엔드 |

뒤쪽이 필요해지면 그때 OTel로 가면 된다.
앞쪽만 필요한데 OTel을 넣으면 propagator와 백엔드까지 딸려온다.

> 실제 적용 기록은 [OCR 오토스케일 전환마다 나던 connection 에러](../task/ai-service-team/ocr-scale-connection-resilience.md) 참고

## 참고

- [OpenTelemetry 공식 docs](https://opentelemetry.io/docs/what-is-opentelemetry/) — 관측 프레임워크 개념 정의
- [W3C Trace Context](https://www.w3.org/TR/trace-context/) — `traceparent` 헤더 표준
