---
tags: [study]
---

# Graceful Shutdown

서버를 그냥 끄면 안 되는 이유는 단순하다. 처리 중인 요청이 있다. DB 트랜잭션이 열려 있다. 커넥션 풀이 열려 있다. 이것들을 제대로 정리하지 않고 죽으면 클라이언트는 에러를 받고, 데이터는 일관성을 잃을 수 있다.

Graceful shutdown은 "받은 요청은 다 처리하고 나서 죽겠다"는 약속이다.

---

## Linux Signal 기초

프로세스 종료는 OS가 시그널을 보내는 것으로 시작된다. 핵심은 SIGTERM과 SIGKILL의 차이다.

| 시그널 | 번호 | 의미 | 핸들러 등록 |
|--------|------|------|-------------|
| SIGTERM | 15 | 정상 종료 요청 | 가능 |
| SIGKILL | 9 | 강제 종료 | 불가 (커널이 직접 처리) |
| SIGINT | 2 | 인터럽트 (Ctrl+C) | 가능 |

SIGTERM은 "이제 종료해도 된다"는 신호다. 프로세스가 핸들러를 등록해두면 받고 나서 정리 작업을 할 수 있다. SIGKILL은 다르다. 핸들러 자체가 불가능하고 커널이 즉시 프로세스를 죽인다. 그래서 graceful shutdown의 핵심은 SIGTERM을 받았을 때 무엇을 할지 정의하는 것이다.

```mermaid
sequenceDiagram
    participant OS as OS / Kubernetes
    participant P as 프로세스
    participant H as Signal Handler

    Note over OS,P: SIGTERM — 정상 종료 요청
    OS->>P: SIGTERM 전달
    alt 핸들러 등록됨
        P->>H: 핸들러 실행
        H->>P: in-flight 요청 처리 완료 대기
        H->>P: 리소스 정리 (DB 커넥션, 파일 등)
        P-->>OS: 정상 종료 (exit 0)
    else 핸들러 없음 (기본 동작)
        P-->>OS: 즉시 종료 — in-flight 요청 드랍
    end

    Note over OS,P: SIGKILL — 강제 종료 (핸들러 불가)
    OS->>P: SIGKILL 전달
    Note over P: 커널이 직접 처리, 프로세스 개입 불가
    P-->>OS: 강제 종료
```

---

## 일반 API 서버에서 신경 써야 할 것

### 로드밸런서 / 서비스 디스커버리에서 먼저 빠지기

새 요청이 들어오지 않도록 먼저 제거되어야 한다. Kubernetes라면 Pod가 Terminating 상태가 되면 Endpoints에서 제거되기 시작하지만, 이 전파에 시간이 걸린다. preStop hook에서 sleep을 주는 이유가 이것이다.

### in-flight 요청 처리 완료 대기

이미 들어온 요청은 끝까지 처리해야 한다. 타임아웃을 설정해서 무한정 기다리지는 않도록 한다.

### 커넥션 드레인

HTTP Keep-Alive 커넥션, DB 커넥션 풀, gRPC 채널 등 열려 있는 커넥션을 닫아야 한다.

### 리소스 정리

파일 핸들, 캐시 플러시, 메시지 큐 커밋 등 데이터 일관성에 영향을 주는 것들.

---

## Spring Boot Graceful Shutdown

Spring Boot 2.3부터 내장 웹서버 수준의 graceful shutdown이 지원된다.

```yaml
# application.yml
server:
  shutdown: graceful

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # 기본값 30s
```

`server.shutdown=graceful`을 설정하면 SIGTERM 수신 시 Tomcat(또는 Netty, Undertow)이 신규 요청 수락을 중단하고 처리 중인 요청이 완료될 때까지 대기한다. `timeout-per-shutdown-phase`는 최대 대기 시간이다.

```mermaid
sequenceDiagram
    participant OS as OS
    participant SB as Spring Boot
    participant TS as Tomcat
    participant HC as HealthCheck (/actuator/health)

    OS->>SB: SIGTERM
    SB->>HC: 상태 → OUT_OF_SERVICE
    Note over HC: 로드밸런서가 헬스체크 실패 감지 → 제외
    SB->>TS: 신규 요청 수락 중단
    Note over TS: in-flight 요청 처리 중...
    Note over TS: timeout-per-shutdown-phase 내 완료 대기
    TS-->>SB: 처리 완료
    SB->>SB: Bean 소멸 (DB 커넥션 풀 등)
    SB-->>OS: 정상 종료
```

`/actuator/health`가 `OUT_OF_SERVICE`로 바뀌는 걸 이용해 로드밸런서에서 먼저 제외되도록 하는 흐름도 중요하다. 헬스체크 간격이 있으니 preStop hook으로 sleep을 주는 것과 조합하면 더 안전하다.

### Spring Boot + Kubernetes 조합 시 시간 예산

```
preStop sleep (10~15s)          → Endpoints 전파 완료 대기
+ timeout-per-shutdown-phase    → in-flight 요청 처리
= terminationGracePeriodSeconds 이내여야 함
```

---

## Python 모델 서버 (gRPC)

일반 REST API 서버와 달리 모델 서버는 몇 가지 추가 고려사항이 있다.

- 추론(inference) 시간이 길다 — 수백 ms ~ 수 초
- GPU 메모리를 점유하고 있다 — 갑자기 죽으면 GPU 메모리 누수 가능
- 프로세스 매니저(supervisord 등)가 중간에 있는 경우가 많다

### Python signal 핸들러 등록

```python
import signal

def serve():
    server = grpc.server(...)
    server.start()

    def handle_sigterm(signum, frame):
        print("SIGTERM received, graceful shutdown (grace=24s)...")
        server.stop(grace=24)  # 24초 내 in-flight RPC 완료 대기, 신규 요청 거부

    signal.signal(signal.SIGTERM, handle_sigterm)
    server.wait_for_termination()
```

`server.stop(grace=N)`은 두 가지를 한다:
- 신규 RPC 요청 거부
- 이미 처리 중인 RPC는 N초까지 완료 대기

핸들러는 `server.start()` 이후에 등록한다. 클로저로 `server`를 캡처하기 때문에 `server`가 이미 초기화된 이후여야 하고, Python 클로저는 호출 시점에 변수를 조회하므로 문제없다.

### supervisord가 있는 경우

supervisord가 PID 1이면 SIGTERM이 supervisord에게 먼저 간다. supervisord는 `stopwaitsecs` 이내에 자식 프로세스가 종료되지 않으면 SIGKILL을 보낸다. 기본값이 10초라 grace period보다 짧으면 graceful stop이 완료되기 전에 강제 종료된다.

```ini
[program:grpc-server]
stopsignal=TERM
stopwaitsecs=27    # grace 24s 에 여유 3s
```

### Kubernetes 와 NCS 환경에서의 시간 예산

NHN Cloud Container Service(NCS)는 `terminationGracePeriodSeconds`를 30초로 고정한다. API 스펙에 해당 필드가 없어 변경할 방법이 없다.

그래서 각 단계의 시간을 늘리는 문제가 아니라 30초를 단계별로 나누는 문제가 된다.
종료가 시작된 시각을 `t=0` 으로 두면 예산이 이렇게 나뉜다.

| 구간 | 최대 소요 | 끝나는 시각 |
| --- | ---: | ---: |
| preStop 에서 Envoy admin 호출 | 2초 | `t=2` |
| listener 전환 대기 | 1초 | `t=3` |
| gRPC 처리 중 요청 대기 | 24초 | `t=27` |
| Envoy 종료 | 약 1초 | `t=28` |
| 남는 여유 | 2초 | `t=30` |

남는 2초에는 인터프리터 종료와 GPU 문맥 정리가 들어가야 하므로 0으로 잡지 않는다.
그리고 24초를 넘는 추론은 여전히 잘릴 수 있다는 한계가 남는다.

preStop 을 3초까지 줄인 것이 핵심이다.
Endpoints 전파를 기다리는 긴 sleep 대신 Envoy 에게 신규 연결을 직접 끊게 하면, 남은 예산을 처리 중인 요청 쪽으로 몰아줄 수 있다.

```mermaid
sequenceDiagram
    participant K8s as Kubernetes / NCS
    participant EP as Endpoints
    participant PS as preStop Hook
    participant ENV as Envoy
    participant APP as gRPC Server

    K8s->>EP: Pod를 Endpoints에서 제거 시작
    K8s->>PS: preStop hook 실행
    PS->>ENV: drain_listeners (신규 요청 차단)
    Note over PS: 총 3s (admin 호출 2s, listener 전환 1s)
    PS-->>K8s: hook 완료

    K8s->>APP: SIGTERM 전달
    APP->>APP: server.stop(grace=24) 시작
    Note over APP: 처리 중인 RPC 완료 대기 (최대 24s)
    APP-->>K8s: 정상 종료

    Note over K8s: 총 30s 초과 시 SIGKILL
```

---

## 정리

| 환경 | 핵심 설정 |
|------|-----------|
| Spring Boot | `server.shutdown=graceful` + `timeout-per-shutdown-phase` |
| Python gRPC | `signal.signal(SIGTERM, handler)` + `server.stop(grace=N)` |
| supervisord | `stopwaitsecs` > grace 값 |
| Kubernetes | preStop sleep + grace ≤ terminationGracePeriodSeconds |

결국 같은 원칙이다. SIGTERM을 받으면 신규 요청을 막고, 하던 것은 끝내고, 그리고 죽는다. 어떤 스택이든 이 흐름을 명시적으로 구현해야 한다.

---

## 실제 적용 사례

### NHN Cloud Container 30초 고정 예산 하 OCR gRPC 서버 503 해결

이 글의 "Kubernetes 와 NCS 환경에서의 시간 예산" 단락이 정확히 그 환경이다.
같은 30초를 두 번에 걸쳐 나눴고, 나눈 값이 달라졌다.

| 항목 | 1차 대응 (2026.04, 운영 반영) | 재배분 (2026.09, 검증 환경) |
| --- | ---: | ---: |
| preStop | 15초 | 3초 |
| gRPC `grace` | 12초 | 24초 |
| supervisord `stopwaitsecs` | 17초 | 27초 |

1차 대응은 Endpoints 전파를 sleep 으로 기다리는 구성이라 preStop 이 예산의 절반을 썼다.
그 결과 유예가 12초뿐이었는데 밀집 문서의 서비스타임이 약 19초여서, 처리 중이던 추론을 유예가 먼저 끊고 있었다.

재배분은 Envoy 에게 신규 연결을 직접 끊게 해서 preStop 을 3초로 줄이고, 그만큼을 처리 중인 요청 쪽으로 옮기는 것이다.
오른쪽 열은 검증 환경까지 올라간 값이고 운영에는 아직 반영하지 않았다.
실제 종료 시간을 재서 표의 예산과 맞는지 확인하는 단계가 남아 있다.

- 초기 503의 증상, 1차 대응의 한계와 종료 예산 재배분은 [OCR 오토스케일 전환의 connection 에러를 양쪽에서 막기](../task/ai-service-team/ocr-scale-connection-resilience.md)에 정리했다.
