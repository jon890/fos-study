---
series: "AI 서비스 실전 구축·운영"
seriesOrder: 9
---

# OCR 오토스케일 전환마다 나던 connection 에러 — 모델 서버와 호출자 양쪽에서 막기

**진행 기간**: 2026.06 ~ 2026.07

> 1차 대응은 [OCR 서버 배포·스케일인 시 503 에러 수정](./graceful-shutdown-503-fix.md) 참고

---

## 배경 — 같은 증상이 두 번 왔다

앞서 배포·스케일인 때 나던 503 을 graceful shutdown 으로 한 번 잡았다.
그런데 주간 에러 리포트에 연결 실패가 계속 올라왔다.

이번엔 증상이 두 갈래였고, **원인도 방향도 서로 달랐다.**

| 전환 | 에러 | 무슨 일인가 |
| --- | --- | --- |
| scale-**out** | 503 (errno 111) | 새 pod 의 envoy(5000)가 gRPC(50051) 모델 로딩이 끝나기 전에 트래픽을 받음 |
| scale-**in** | `PrematureClose` | 종료되는 pod 가 진행 중이던 추론을 끊음 |

scale-out 은 **아직 준비 안 된 곳으로 보낸 것**이고, scale-in 은 **하던 일을 끊은 것**이다.
한쪽만 고쳐서는 리포트가 안 줄어드는 이유였다.

그리고 문제는 모델 서버에만 있지 않았다. 호출자인 OCR.API 쪽에도 있었다.

---

## 모델 서버 쪽 — 기동과 종료에 순서를 만든다

### 1. grace 12초는 서비스타임보다 짧았다

1차 대응에서 gRPC `server.stop(grace=12)` 를 넣었는데, 밀집 문서의 서비스타임이 약 19초다.
**진행 중이던 추론을 유예 시간이 먼저 끊고 있었다.**

- gRPC `grace` 12초 → **30초**
- supervisord `stopwaitsecs` 17초 → **35초** (grace 이상이어야 SIGKILL 이 먼저 날아가지 않는다)

### 2. SIGTERM 이 python 에 닿지 않고 있었다

`stopwaitsecs` 를 늘려도 핸들러가 안 돌면 소용이 없다.
supervisord 가 보낸 SIGTERM 이 중간 bash 프로세스에서 멈춰, `handle_sigterm` 이 **아예 실행되지 않는** 상태였다.

```ini
# 중간 프로세스 없이 python 이 PID 를 그대로 받도록
command=... exec python server_grpc_general_OCR.py
```

`exec` 한 단어가 빠져서 앞의 grace 설정이 전부 무의미했던 셈이다.

### 3. envoy 를 wrapper 로 감싸 기동과 종료 순서를 확정

supervisord 는 envoy 와 gRPC 를 거의 동시에 띄우고, 종료 순서도 보장하지 않는다.
그래서 envoy 를 wrapper 스크립트가 소유하게 했다.

- **기동 보류** — gRPC ready 신호(`/tmp/start_success`) 전까지 5000 bind 를 미룬다
- **종료 순서** — SIGTERM 을 trap 해 `drain_listeners` → gRPC 종료 대기 → envoy 종료

기동 보류가 scale-out 의 503 을, 종료 순서가 scale-in 의 `PrematureClose` 를 각각 막는다.

`supervisord` 의 `priority` 조정만으로 끝낼 수도 있었지만 그렇게 하지 않았다.
**supervisord 가 종료를 직렬로 기다린다는 보장이 문서상 분명하지 않아**, envoy 가 gRPC drain 전에 죽을 위험이 남는다.
wrapper 가 gRPC 종료를 직접 확인하면 그 보장이 supervisord 내부 동작에 의존하지 않는다.

gRPC health service 와 envoy active health check 도 검토했다.
gRPC 는 죽으면 in-place 재시작 없이 pod 가 교체되므로 파일 신호로 충분했고, proto 와 envoy 설정을 늘릴 만한 이득이 없었다.

### 4. 기동 보류를 풀었는데 여전히 붙지 않던 구간

wrapper 를 넣고도 scale-out 직후 짧은 실패가 남았다.
envoy 바이너리를 **런타임에 받고 있었다.** 기동 보류가 풀린 뒤 다운로드가 끝나야 5000 을 bind 하니, 그 사이가 그대로 구멍이었다.

빌드 시점에 미리 받아두는 것으로 해결했다.

### 레포 밖에서 맞춰야 하는 것

컨테이너 안만 고쳐서는 완결되지 않는다.

- `terminationGracePeriodSeconds` ≥ 60초 — preStop drain 15초, gRPC grace 30초, envoy 종료 여유를 더한 값이다. 이보다 짧으면 SIGKILL 이 graceful 을 잘라버린다
- readiness probe 는 **envoy 5000 응답 기준**으로 둔다. gRPC ready 파일만 보면 envoy 가 5000 을 bind 하기 전에 Ready 로 떠서 scale-out 실패가 그대로 남는다

---

## 호출자 쪽 — 커넥션을 언제 버리고 언제 다시 보낼 것인가

모델 서버가 아무리 곱게 내려가도, 호출자가 사라진 pod 를 계속 가리키면 실패는 계속된다.

### 1. `maxIdleTime` 만으로는 회수되지 않는다

커넥션 풀에 `maxIdleTime(3초)` 은 있었다. 그런데 **바쁘게 재사용되는 커넥션은 idle 상태가 되질 않는다.**
scale-in 으로 종료된 pod 를 가리키는 커넥션이 stale 인 채 계속 돌면서 `PrematureClose` 를 만들었다.

생성 후 60초 상한(`maxLifeTime`)을 둬서, 종료된 pod 의 커넥션이 강제로 재수립되게 했다.

### 2. connect timeout 이 없어 netty 기본값 30초가 걸려 있었다

도달 불가한 다운스트림이 하나 생기면 요청 하나가 **30초 동안 커넥션을 점유**한다.
모든 다운스트림이 단일 커넥션 풀을 공유하므로, 무관한 API 까지 같이 느려진다.

2초로 정한 근거는 셋이다.

- 실측 connect 시간이 다운스트림 전부 **6~118ms** 라 여유가 충분하다
- Linux SYN 재전송이 `t=0, 1s, 3s` 시점이라 **2초와 3초의 재전송 내성이 2회로 같다.** 3초는 자원만 더 붙잡고 얻는 게 없다
- `connect 2s + responseTimeout 58s = 60s` 로 `spring.mvc.async.request-timeout(60s)` 예산과 맞는다

적용 후 도달 불가 주소 호출이 30초가 아니라 **2.1초**에 실패한다.

### 3. 503 은 재시도해도 안전하다 — `ReadTimeout` 은 아니다

재시도 판단에서 갈리는 지점이 여기다.

| 실패 | 요청이 모델에 닿았나 | 재시도 |
| --- | --- | --- |
| envoy 503 upstream connect error | **닿지 못함** | 안전 |
| `PrematureClose` | 연결이 끊김 | 안전 |
| `ReadTimeout` | **닿은 뒤 실패** | 위험 — 중복 처리 |

기존엔 `PrematureClose` 만 재시도하고 있어서, scale-out 전환 중의 503 이 그대로 사용자에게 나갔다.
503 을 재시도 대상에 넣고, 대기도 `fixedDelay(3, 100ms)` 에서 `backoff(3, 200ms, maxBackoff 2초)` 로 늘렸다.
pod 재기동은 초 단위라 100ms 고정으로는 전환 창을 못 덮는다.

여기서 **잠재 결함이 하나 같이 드러났다.** `fixedDelay` 는 재시도가 소진되면 원본 예외를 `RetryExhaustedException` 으로 감싼다. 그 바람에 `INTERNAL_API_FAIL(5000001)` 로 가야 할 에러가 일반 `FAIL` 로 잘못 매핑되고 있었다. `onRetryExhaustedThrow` 로 원본 예외를 그대로 전파하게 하면서 함께 해소됐다.

---

## 그런데 어느 요청이 실패한 건지 찾을 수가 없었다

여기까지가 연결 실패 자체에 대한 대응이다. 별개로 오래 걸린 문제가 하나 더 있었다.

에러를 분석할 때 **게이트웨이 로그, OCR.API 로그, 모델 서버 로그를 묶을 공통 키가 없었다.**
`requestId` 는 있었지만 OCR.API 가 자체 생성한 UUID라, 게이트웨이 요청이나 모델 로그와 이어지지 않았다.
한 요청이 어디서 끊겼는지 추적하다 매번 멈췄다.

### 게이트웨이가 이미 주고 있던 값을 쓰기로 했다

API Gateway 가 발급하는 `X-Request-Id` 를 요청 전 구간의 추적 키로 채택했다.

```
API Gateway ──X-Request-Id──> OCR.API ──X-Request-Id──> 모델 서버
                                 │                         │
                              MDC 저장                  contextvar 저장
                                 └──────── 같은 값으로 로그 적재 ────────┘
```

- OCR.API — 인터셉터가 헤더를 MDC `requestId` 로 저장(sanitize, 없으면 UUID fallback)하고 로그 패턴·모델 호출 헤더로 전파
- 모델 서버 — gRPC 진입점에서 `contextvar` 에 저장하고 `logging.Filter` 가 모든 로그 레코드에 자동 주입

모델 서버 쪽에서 **로그마다 `extra={'requestId': ...}` 를 명시 전달하던 방식을 걷어낸 것**이 컸다.
새 로그를 추가할 때 전달을 잊으면 그 줄만 추적에서 빠지는데, 진입점에서 한 번 저장하고 자동 주입하면 그 누락이 원천 차단된다.

### OpenTelemetry 를 쓰지 않은 이유

표준을 따르자면 W3C Trace Context(`traceparent`)가 맞다. 검토했지만 채택하지 않았다.

- 게이트웨이가 `traceparent` 를 보내지 않아 별도 propagator 를 붙여야 한다
- trace 백엔드가 없다. 목적이 **로그 상관관계**이지 시각적 span 추적이 아니다

목적에 비해 도입 비용이 컸다. 나중에 span 단위 추적이 필요해지면 그때 다시 볼 문제로 남겼다.

### MDC 가 ThreadLocal 이라 겪은 것들

`requestId` 를 MDC 에 얹고 나서 세 번 밟았다. 셋 다 원인이 같다 — **MDC 는 스레드에 묶여 있다.**

- **서블릿 async 재디스패치** — 비동기 처리 후 다시 디스패치될 때 MDC 가 비어 있어 `requestId` 를 재사용하도록 고쳤다
- **감사 로그 뒤 복원 누락** — 중간에 MDC 를 바꿔 쓰고 되돌리지 않아 이후 로그에서 `requestId` 가 사라졌다
- **헬퍼에서 `MDC.clear()`** — 중간 헬퍼가 전체를 지워 뒤따르는 로그가 통째로 추적에서 빠졌다

세 번째가 가장 찾기 어려웠다. 로그가 **비는 게 아니라 그냥 값이 없는 채로 정상 출력**되기 때문이다.
회귀 테스트로 채택·전파·sanitize·누수 방지를 묶어 고정했다.

> MDC 자체에 대한 정리는 [로그에 traceId 남기기](../../java/MDC.md) 참고

---

## 배운 것

**증상이 같아도 원인이 같지 않다.** 배포·스케일인의 503 을 한 번 잡았다고 연결 실패가 끝나지 않았다. scale-out 은 "준비 전에 받았다", scale-in 은 "하던 걸 끊었다" 로 방향이 반대였다.

**서버만 고치면 절반이다.** 모델 서버가 곱게 내려가도 호출자 풀에 남은 커넥션이 사라진 pod 를 가리키면 실패는 계속된다. 종료 쪽과 호출 쪽을 같이 봐야 리포트가 줄었다.

**타임아웃 값은 감이 아니라 예산으로 정한다.** connect 2초는 실측 분포(6~118ms), 커널 재전송 시점(0·1·3초), 상위 타임아웃 예산(60초)을 맞춰 나온 값이다. 3초로 잡아도 동작은 하지만 재전송 내성은 같고 자원만 더 붙잡는다.

**재시도의 안전 여부는 "요청이 상대에 닿았는가" 로 갈린다.** 503 은 닿지 못한 실패라 재시도해도 되고, `ReadTimeout` 은 닿은 뒤 실패라 재시도하면 중복 처리가 된다. 같은 실패로 보여도 이 질문 하나로 나뉜다.

**추적 키는 이미 있는 것을 쓰는 게 낫다.** 게이트웨이가 발급하던 값을 그대로 채택하니 표준 도입 없이 게이트웨이부터 모델까지 한 줄로 묶였다.

---

## 사용 기술

- Java 21, Spring Boot 3.x, WebClient (Reactor Netty)
- Python, gRPC, Envoy, supervisord
- NHN Cloud Container Service (NCS)
