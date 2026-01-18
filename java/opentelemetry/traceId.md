# OpenTelemetry에서 traceId는 누가 만들까?

- OpenTelemetry SDK / Instrumentattion이 자동 생성한다.

```text
HTTP 요청 수신
 └─ OTel Instrumentation
     ├─ Trace 생성
     ├─ traceId / spanId 생성
     ├─ Context에 저장
     └─ 다음 처리로 전달
```

- 우리가 해야할 일
  - 의존성 추가
  - Instrumentation 활성화
  - Exporter 설정
- 우리가 안해도 되는 일
  - UUID 생성
  - MDC.put("traceId", ...)
  - 헤더 수동 파싱 / 전파

## OTel의 기본 추적 모델

- Trace / Span 구조

```text
Trace (하나의 요청)
 ├─ Span: HTTP Server
 │   ├─ Span: DB Query
 │   └─ Span: Redis
 └─ Span: HTTP Client (다른 서비스)
```

- traceId : 전체 요청을 묶는 ID
- spanId: 각 작업 단위
- MDC는 traceId 1개
- OTel은 정밀한 호출 트리

## 서비스 간 traceId 전파는 어떻게 하는가?

- OTel은 **표준 헤더**를 사용ㄹ함
- W3C Trace Context
  - > traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
  - 자동 생성
  - 자동 파싱
  - 자동 전파
- 우리가 직접 `X-Trace-Id`를 만들 필요가 없음

## 그럼 MDC는 이제 필요 없나?

- 그렇지 않음. 둘은 역할이 다르다
- OTel + MDC 관계

| 역할          | 담당            |
| ------------- | --------------- |
| 분산 트레이싱 | OpenTelemetry   |
| 로그 상관관계 | MDC             |
| 시각화        | Tempo / Jaeger  |
| 로그 검색     | NHN Log & Crash |

## OTel에서 MDC로 traceId를 넣어주는 구조

- 보통 이런 흐름이다

```text
OTel Context
   ↓
Logback MDC Bridge
   ↓
로그에 traceId 출력
```

- 자동 브릿지
  - Spring Boot + OTel Instrumentattion 사용 시:
    - `traceId`, `spanId` 자동으로 MDC에 주입됨
    - 로그에 `%X{trace_id}` 가능
  - > 즉, traceId를 OTel이 만들고, MDC는 로그 출력을 위해 자동으로 받아쓴다
