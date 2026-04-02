# OCR 서버 배포·스케일인 시 503 에러 수정 — Graceful Shutdown 미적용

**진행 기간**: 2026.04

> Graceful shutdown 개념은 [devops/graceful-shutdown.md](../../devops/graceful-shutdown.md) 참고

---

## 배경

General OCR 서비스를 배포(롤링 업데이트)하거나 오토스케일러가 스케일인할 때마다 짧은 시간 동안 503 에러가 클러스터 단위로 발생했다. 에러 로그를 보면 패턴이 일정했다.

```
upstream connect error or disconnect/reset before headers.
reset reason: connection failure,
transport failure reason: delayed connect error: 111
```

error 111은 ECONNREFUSED, TCP 레벨에서 연결이 거부됐다는 뜻이다. 응답 헤더에 `server: envoy`가 있었고, 이건 Envoy 자체는 살아있는데 upstream(포트 50051)에 연결을 못 했다는 의미다.

에러가 30~60초 주기로 묶음 발생하고 자연히 사라지는 패턴 — 배포/스케일인 이벤트와 정확히 일치했다.

---

## 원인 분석

서비스 구조는 이렇다.

```
클라이언트 → Envoy(:5000) → gRPC 서버(:50051)
```

컨테이너가 종료될 때 실제로 일어나는 일을 추적해봤다.

**종료 시퀀스 (수정 전)**

1. preStop hook 실행: Envoy `drain_listeners` 호출 → `sleep 20`
2. preStop 완료 → SIGTERM 전달 → gRPC 서버 **즉시 종료** → 포트 50051 닫힘
3. sleep 20s 동안 Envoy가 아직 살아있어 요청을 upstream으로 라우팅 시도
4. 50051 연결 거부(ECONNREFUSED) → 503 반환

핵심은 gRPC 서버에 SIGTERM 핸들러가 없었다는 것이다. `server_grpc_general_OCR.py`의 `serve()` 함수는 `server.wait_for_termination()`만 있었고, SIGTERM을 받으면 그냥 죽었다.

```python
# 수정 전
server.start()
server.wait_for_termination()  # SIGTERM 수신 시 즉시 종료
```

두 번째 문제는 supervisord 설정이었다. `[program:grpc-server]`에 `stopwaitsecs`가 없어 기본값 10초가 적용됐다. SIGTERM 핸들러를 추가해도 supervisord가 10초 안에 종료 안 되면 SIGKILL을 날리는 구조였다.

---

## NCS 제약

NHN Cloud Container Service는 `terminationGracePeriodSeconds`를 30초로 고정한다. API 스펙에도 해당 필드가 없어 변경할 방법이 없다. 따라서 모든 종료 작업은 30초 이내에 끝나야 한다.

기존 preStop `sleep 20`을 유지하면서 grace period를 늘릴 경우, `20 + grace`가 30초를 넘기 때문에 preStop sleep을 15초로 줄이고 grace를 12초로 설정하는 방식으로 예산을 맞췄다.

```
preStop sleep 15s + gRPC grace 12s + 여유 3s = 30s
```

---

## 수정 내용

**`server_grpc_general_OCR.py`** — SIGTERM 핸들러 추가

```python
import signal  # 추가

def serve():
    server = grpc.server(...)
    server.start()

    def handle_sigterm(signum, frame):
        print("SIGTERM received, starting graceful shutdown (grace=12s)...")
        server.stop(grace=12)

    signal.signal(signal.SIGTERM, handle_sigterm)
    server.wait_for_termination()
```

**`supervisord.conf`** — stopwaitsecs 추가

```ini
[program:grpc-server]
stopwaitsecs=17    # grace(12s) + 여유(5s)
stopsignal=TERM
```

**`Jenkinsfile_deploy_real`** — preStop sleep 단축

```
"preStop": ["/bin/sh", "-c", "curl -sf ... drain_listeners || true; sleep 15"]
```

---

## 수정 후 종료 시퀀스

| 시간 | 이벤트 |
|------|--------|
| T+0s | preStop 실행: Envoy drain_listeners, sleep 15s 시작 |
| T+15s | preStop 완료 → SIGTERM → `server.stop(grace=12)` 시작 |
| T+15~27s | in-flight RPC 처리 완료 대기, 신규 요청 거부 |
| T+27s | gRPC 서버 종료, 컨테이너 종료 |

수정 전에는 T+15s(또는 T+20s)에 gRPC 서버가 즉시 죽고 Envoy가 50051에 연결을 못 해서 503이 났다. 수정 후에는 preStop 완료 시점에 gRPC 서버가 정상적으로 drain을 수행하고 종료된다.
