---
series: "AI 서비스 실전 구축·운영"
seriesOrder: 3
---

# 문서 파싱 서비스 관측성 체계 구축 — 초기화 순서 함정과 지표 단일화

**진행 기간**: 2026.05 ~ 2026.07

문서 파싱 서비스(Playground의 OCR 기반 문서→markdown 변환 API)를 운영하면서 관측성(observability) 체계를 처음부터 만들었다.
다음 다섯 가지를 다뤘다.

- `/metrics` 엔드포인트 신규 도입
- 운영 배포 직후 터진 메트릭 누락 사고 대응
- 무중단 컨테이너 교체를 위한 drain 모드
- 대시보드 31패널까지의 점진적 확장
- 지표·로그·조회 API로 흩어져 있던 관측 경로의 단일화

전체 흐름을 시간순으로 정리한다.

## 처리량·지연 실시간 관측 체계 구축

운영 중인 서비스의 `Throughput`(처리량)·`Latency`(지연)·워커 상태를 볼 수단이 처음엔 아예 없었다.
성능 문제가 생기면 로그를 뒤져 사후에 추정하는 게 전부였다.

그래서 메트릭 노출부터 붙였다.
`prometheus-fastapi-instrumentator`로 HTTP 기본 메트릭을, `prometheus_client`로 도메인 메트릭(워커 워밍업·OCR 호출·거부 등)을 직접 정의해 같은 registry에 등록했다.
이 서비스는 uvicorn을 다중 워커로 띄우고, 문서 변환 자체도 `ProcessPoolExecutor`로 별도 OS 프로세스에서 처리한다.
프로세스가 여러 개라 메트릭도 프로세스마다 따로 쌓이는데, `PROMETHEUS_MULTIPROC_DIR` 환경변수 기반의 `MultiProcessCollector`가 각 프로세스의 `.db` 파일을 모아 메인 프로세스의 `/metrics` 응답 하나로 합쳐준다.

- Pushgateway 방식(워커가 직접 push)이나 메인 프로세스만 계측하는 방식은 기각했다 — 워밍업 시간·OCR 호출 지연 같은 핵심 신호가 워커 프로세스 안에서만 발생하기 때문이다.
- 사내 메트릭 수집 시스템과 연동된 Prometheus·Grafana 대시보드를 13패널로 처음 만들었다.
- `scripts/swap-container.sh`로 컨테이너를 새 이미지로 교체하는 과정을 스크립트화했다.
    기존 컨테이너의 환경변수(OCR 키·워커 설정 등)를 자동 보존하고, 교체 후 `/health` 200 응답을 최대 5분 폴링해 확인한다.

이렇게 처리량·지연·OCR 호출·워커 라이프사이클을 실시간으로 볼 수 있게 됐고, 이후 이어진 모든 성능·메모리 개선 작업의 효과 측정 기준이 됐다.

## 운영 배포 직후 메트릭 4종 누락 사고

체계를 배포한 직후 운영에서 핵심 메트릭 4종(`parse_requests_total`, `parse_processing_seconds`, `worker_restart_total`, `requests_rejected_total`)이 `/metrics` 응답에서 통째로 빠지는 걸 발견했다.
워커 프로세스가 기록하는 메트릭(`worker_alive`, OCR 호출 관련)은 정상 노출됐는데, 메인 프로세스가 직접 기록하는 메트릭만 누락됐다.

### 묻혀버린 실패부터 걷어냈다

원인을 찾으려 해도 단서가 없었다.
메트릭 기록 코드 8곳이 전부 `try/except`로 감싸져 있었고, 실패해도 `logging.debug` 또는 `except: pass`로 조용히 삼켜지고 있었다.
실패 이유를 보려면 먼저 로그부터 드러내야 했다 — `debug`를 `warning` + `exc_info=True`로 바꿔 다음 요청에서 실제 예외 traceback이 로그에 남게 했다.

### 근본 원인 — multiproc 모드는 import 시점에 딱 한 번 결정된다

로그를 받은 뒤 원인을 확인했다.
`prometheus_client`는 모듈이 처음 import되는 시점에 `PROMETHEUS_MULTIPROC_DIR` 환경변수 존재 여부를 딱 한 번 검사해서, 이후 모든 메트릭 객체가 단일 프로세스 모드로 갈지 멀티 프로세스 모드로 갈지를 그 자리에서 고정해버린다.
나중에 환경변수를 설정해도 이미 결정된 모드는 바뀌지 않는다.

기존 코드는 FastAPI의 `lifespan` startup 블록 안에서 `PROMETHEUS_MULTIPROC_DIR`을 `setdefault`하고 있었는데, 이 코드가 실행되는 시점은 `prometheus_client`를 최상단에서 import한 한참 뒤였다.
그래서 메인 프로세스의 Counter·Histogram은 이미 단일 프로세스 모드로 굳어진 채 생성됐고, `inc()`를 호출해도 메모리에만 반영될 뿐 `MultiProcessCollector`가 읽는 `.db` 파일이 생성되지 않았다.
반대로 워커 프로세스는 매번 새 인터프리터로 spawn되면서, 워커 초기화 코드 안의 `setdefault` 이후에 메트릭 모듈을 처음 import했기 때문에 우연히 멀티 프로세스 모드로 정상 동작했다.

```python
# 모듈 최상단 — prometheus_client/instrumentator import 보다 반드시 먼저
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/prom_multiproc")
Path(os.environ["PROMETHEUS_MULTIPROC_DIR"]).mkdir(parents=True, exist_ok=True)

from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
```

이 한 줄을 최상단으로 옮기고 나니 두 번째 함정이 나왔다.
`prometheus-fastapi-instrumentator`의 `Instrumentator(...)`도 모듈 로드 시점에 `PROMETHEUS_MULTIPROC_DIR` 디렉터리가 실제로 존재하는지 검증한다.
`setdefault`만 하고 디렉터리를 안 만들면 부팅 자체가 `ValueError: not a directory`로 죽는다.
`mkdir`을 `setdefault` 바로 옆에 붙여야 했다.

### 세 번째 함정 — main 프로세스의 multiproc Histogram이 lazy create 안 된다

앞선 두 수정 뒤에도 `parse_processing_seconds` 하나만 계속 비어 있었다.
운영 8대 인스턴스에서 직접 확인해보니, 같은 프로세스가 만드는 `counter_<pid>.db`·`summary_<pid>.db`는 정상 생성되는데 `histogram_<pid>.db`만 메인 프로세스에서 생성되지 않았다.
`observe()` 자체는 예외 없이 정상 실행되는데도 파일만 안 만들어지는 라이브러리 차원의 동작으로 보였고, 정확한 메커니즘은 더 파고들지 않고 우회로 대응했다.

회피책은 `lifespan` startup에서 가능한 라벨 조합(`endpoint` × `ja_doc`, 4개 조합)을 `observe(0)`으로 한 번씩 미리 호출해 `.db` 파일을 강제로 만들어두는 것이었다.
이후 실제 요청의 `observe()`는 정상 동작했다.
노이즈로 `count=1, sum=0`이 한 번 더 잡히지만 대시보드에는 영향이 없다.

세 함정을 다 걷어내고 나서야 전 메트릭이 정상 노출되고 대시보드가 복구됐다.
이 사고로 원칙 하나를 얻었다 — multiproc 환경변수·디렉터리 준비는 항상 해당 라이브러리의 최초 import보다 앞서야 하고, `lifespan` 안에서의 설정은 "이미 늦은" 시점일 수 있다.

## drain 모드 도입

컨테이너를 교체하거나 인스턴스 하나를 점검하려면 처리 중인 요청이 끊기거나, 로드밸런서(LB)에서 그 인스턴스를 수동으로 빼야 했다.
서버 프로세스 종료 자체를 다루는 [Graceful Shutdown](../../devops/graceful-shutdown.md)과는 다른 층위다 — drain은 종료 전에 LB 라우팅에서 미리 빠지는 단계이고, graceful shutdown은 종료 신호를 받은 뒤 처리 중인 요청을 마저 끝내는 단계다.

이를 위해 `app.state.drain_mode`라는 메모리 플래그와 `POST /admin/drain` / `POST /admin/undrain` API를 추가했다.
인증은 `X-Admin-Key` 헤더를 `hmac.compare_digest`로 비교하는 방식이고, 키 미설정 시엔 503으로 막아 실수로 열리는 걸 방지한다.
drain이 켜지면 L4 LB가 헬스체크로 쓰는 `GET /health`가 503을 반환해 그 인스턴스로 신규 트래픽이 안 들어오게 되고, `/health/detailed`·`/status/*`는 200 + `drain: true` 필드로 상태를 노출한다.
`/parse/*` 같은 실제 처리 엔드포인트는 drain 중에도 정상 동작한다.

파일 마커나 호스트 볼륨 마운트 같은 대안은 원격 토글이 번거롭거나 배포 절차 변경이 필요해 기각했다.
메모리 플래그를 쓴 이유는 컨테이너가 재기동되면 자동으로 drain이 풀리는 것도 의도한 fail-safe이기 때문이다.

결과적으로 처리 중이던 요청은 그대로 마저 처리되면서 LB가 자동으로 신규 트래픽만 차단하는 흐름을 확보했다.
컨테이너 교체·점검을 사람이 LB를 직접 조작하지 않고 처리할 수 있게 됐다.

## 문서 처리 실패 가시화

이 무렵 대시보드도 함께 다듬었다.
패널 종류가 늘어날수록 heatmap은 한눈에 추세를 보기 어려워져서, 시계열이 늘어난 heatmap 패널 일부를 timeseries로 바꿨다.
처리 시간 히스토그램(`parse_processing_seconds`)의 bucket 상한도 실제 운영 분포에 맞춰 늘렸다 — 최대 10분(600초)까지만 있던 걸 900·1200초까지 추가했다.

정작 큰 구멍은 실패가 안 보인다는 것이었다.
문서 처리 중 예외가 나도 클라이언트는 HTTP 200과 빈 markdown을 받아서, 정상적인 빈 문서와 처리 실패를 구분할 수 없었다.
실패가 얼마나·어떤 원인으로 일어나는지 볼 운영 지표도 없었다.

처음에는 응답 계약을 건드리지 않는 선에서 시작했다.
`document_parse_failures_total{format, reason}` 카운터와 실패 로그만 추가해 운영 가시성을 먼저 확보하고, 응답 구조 변경은 클라이언트 영향 조사가 끝난 뒤로 미뤘다.
`reason` 라벨에 예외 메시지를 그대로 넣으면 라벨 조합이 무한히 늘어나므로, 예외 타입을 고정된 `reason` 집합으로 매핑했다.
이후 클라이언트 영향을 확인한 다음 단계에서 `DocumentResponse`에 `reason` 필드(status="error" 시)를 추가해 응답에서도 실패 사유를 확인할 수 있게 확장했다.

대시보드에는 처리 에러율 KPI, 실패 사유별 패널을 추가했다.
워커 재시작 패널도 하나로 뭉쳐 보던 걸 "정상 재활용(`reason=unknown`, max_tasks 도달 등)"과 "강제 종료(`reason=timeout_kill`, 처리 시간 초과로 인한 CPU 과점유 방어)"로 나눴다.
둘을 섞어 보면 정상적인 워커 순환과 장애성 강제 종료 추세가 서로 가려지기 때문이다.

이제 실패가 지표·로그 양쪽에서 드러나고, 워커 재시작이 "정상"인지 "장애 신호"인지 대시보드에서 바로 구분된다.

## 관측 경로 단일화

요청 하나가 처리되는 동안 같은 수치가 메트릭·로그·조회 API(`/status/requests`, `/status/gpu`) 세 곳에 동시에 기록되고 있었다.
요청마다 로그가 여러 줄 쌓였고, 운영자는 같은 값을 세 창구에서 확인해야 했다.
`/status/gpu`는 메인 프로세스의 GPU 컨텍스트만 측정해 별도 프로세스인 워커의 실제 VRAM 점유를 반영하지도 못했다.

요청 현황의 단일 기준을 Prometheus 메트릭(Grafana)으로 정하고, 중복되던 요청 추적 객체와 `/status/requests`·`/status/gpu` 조회 API 2종을 제거했다.
캐시 조합·GPU별 워커 배치처럼 메트릭 라벨로는 표현할 수 없는 디버깅 정보만 `/status/converters`에 남겼다.

- 준비 단계(pending, 워커 제출 전) 가시성은 메트릭에 없는 채로 사라졌다 — 짧은 구간이고 구조화 로그로 추적 가능해 수용했다.
- status 도메인을 통째로 없애는 안은 기각했다.
    캐시 조합·GPU 배치는 메트릭에 없는 유일한 디버깅 창구였다.

이렇게 운영 확인 기준이 Grafana 하나로 통일됐다.

## metrics·로그 관측성 개선 — 고아 db 스윕과 로그 정리

multiproc Gauge는 `livesum` 모드로 각 프로세스의 `.db` 파일 값을 합산한다.
워커가 정상 종료되면 `mark_process_dead(pid)`가 그 파일을 지워 합산에서 빠지지만, SIGKILL이나 OOM으로 강제 종료되면 이 정리 경로를 안 타서 죽은 워커의 값이 합산에 영구히 남는다.
운영 Grafana에서 `worker_alive`·glibc 지표가 계속 우상향하는 현상으로 확인했다.

- **고아 db 스윕**: `worker_death_monitor` 루프가 매 주기 `PROMETHEUS_MULTIPROC_DIR` 안의 `*_<pid>.db` 파일에서 PID를 뽑아 `psutil.pid_exists(pid)`로 생존 여부를 확인하고, 죽은 PID면 `mark_process_dead`로 정리한다.
    종료 경로(정상/SIGKILL/OOM)와 무관하게 청소되는 게 핵심이다.
    같은 감시 루프가 시간 초과 워커를 강제 종료하는 역할도 겸한다 — 그 쪽 이야기는 [문서 파싱 서비스, 리소스가 새는 자리를 하나씩 틀어막은 기록](./docparser-memory-stability.md)에서 다룬다.
- **호스트 RAM 지표 3종** (`system_memory_usage_percent`/`used_bytes`/`total_bytes`) 을 추가했다 — `malloc_trim`이 OS에 메모리를 실제로 반환하는지 확인할 관측 창구가 없었기 때문이다.
- 변환 로그를 이모지·영어 위주에서 한국어 자연어 + 파일 정보 중심으로 정리하고, 메트릭과 중복되던 로그(예: `malloc_trim` 호출당 INFO 로그)를 제거했다.
    같은 정보가 glibc Gauge·STW 시간 Histogram으로 이미 노출되고 있어서, 로그는 호출 빈도가 높을수록 운영 로그 노이즈만 키웠다.
- 대시보드는 31패널 전체에 설명(description)을 보강해 처음 보는 사람도 각 패널이 뭘 보여주는지 알 수 있게 했다.

## 회고

관측성 체계는 그 자체가 목적이 아니라, 이후 이어진 워커 메모리 누수 대응([Python 서버 RSS malloc_trim 적용기](glibc-malloc-trim-python-leak.md))을 포함한 모든 성능·메모리 개선 작업의 "효과를 측정하는 기준"이 됐다.
개선 전후를 숫자로 비교할 수 없으면 그 개선이 실제로 효과가 있었는지 주장할 근거가 없다.

가장 크게 배운 건 멀티 프로세스 메트릭 통합의 함정이다.
`PROMETHEUS_MULTIPROC_DIR`은 "설정만 해두면 되는" 값이 아니라 "해당 라이브러리를 import하기 전에" 설정돼야 하는 값이었고, `lifespan` 같은 애플리케이션 생명주기 훅 안의 코드는 생각보다 늦은 시점일 수 있다는 걸 사고를 겪고서야 체감했다.

지표·로그·조회 API로 흩어졌던 관측 경로를 하나로 줄여나가는 과정도 반복된 주제였다.
같은 정보를 여러 곳에 중복해서 남기면 그 정보들이 서로 어긋나기 시작하는 순간 어느 쪽을 믿어야 할지 알 수 없어진다.
메트릭이 답할 수 있는 질문은 메트릭에 맡기고, 로그·조회 API는 메트릭이 답하지 못하는 것만 남기는 원칙으로 정리했다.
