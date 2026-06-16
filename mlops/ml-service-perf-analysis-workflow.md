# ML 서비스 성능 분석 워크플로 — 자바 백엔드 트러블슈팅과 다른 점

이 시리즈의 마무리 글이다. 앞선 글들에서 다음 주제를 자바 백엔드 비교 관점으로 정리했다.

- Python 문법
- 의존성 관리
- FastAPI
- async/await
- GPU·CUDA·MPS
- PyTorch
- multi-process worker pool
- OCR 파이프라인

마지막은 이 모든 개념을 적용해 실제 ML 서비스의 성능을 분석하는 워크플로를 정리한다.

내가 직접 ML 문서 파싱 서비스를 분석하며 17개의 개선 이슈를 GitHub 에 등록한 경험을 일반화해서 단계별 절차로 옮긴다. 자바 백엔드의 트러블슈팅과 다른 결정적 차이도 함께 짚는다.

## 자바 vs ML — 무엇이 다른가

자바 백엔드 트러블슈팅의 표준 도구는 거의 정해져 있다.

- `jstack` — 스레드 덤프
- `jmap` / `jcmd` — heap 덤프
- GC log + GCeasy 분석
- APM (NewRelic, Datadog, Pinpoint) 의 transaction trace
- JFR / async-profiler

JVM 안에서 일어나는 일은 거의 다 보인다. 한 프로세스, 한 heap, 한 thread pool. 자바 개발자는 이 안에서 코드를 읽고, 락 분석하고, GC 튜닝하면 된다.

ML 서비스는 그림이 다층이다.

| 계층 | 자바 백엔드 | ML 서비스 |
|---|---|---|
| HTTP | Tomcat thread pool | FastAPI + Uvicorn |
| 비동기 | Reactor / CompletableFuture | asyncio event loop |
| 동시성 | Thread (JVM 안) | Process (OS 단위 격리) |
| 컴퓨팅 자원 | CPU + JVM heap | CPU + 시스템 RAM + GPU + VRAM |
| 모니터링 | JMX, jstack, APM | nvidia-smi, ps, profile timings |
| 외부 호출 | DB, REST API | DB, REST API, **외부 OCR/ML API** |

자바 트러블슈팅의 80% 가 한 JVM 안에서 끝나는 반면, ML 서비스는 **OS 프로세스 단위 분석 + GPU 분석 + 외부 API 분석** 까지 동시에 봐야 한다.

## 분석 워크플로 — 6단계

내가 따른 절차를 일반화하면 다음과 같다.

### 운영 환경 파악

코드를 열기 전에 운영 인스턴스의 실제 상태를 본다. 자바라면 `jps` + GC log 위치 확인 같은 단계.

- 컨테이너 / 프로세스 목록 (`docker ps`)
- 환경 변수 (`docker exec ... printenv`)
- GPU 상태 (`nvidia-smi`)
- 시스템 리소스 (`free -h`, `nproc`)
- 서비스 자체 status 엔드포인트 (`/status/*`)

이 단계에서 운영자의 의도가 코드 기본값과 다른 부분을 찾는 게 핵심. 내가 분석한 서비스도 `MAX_TASKS_PER_WORKER` 가 코드 기본값 50 인데 운영 env 가 3 으로 override 되어 있어서 즉시 의심 지점이 됐다.

### 정적 코드 분석 — 영역별 분리

자바 백엔드에서 IntelliJ + 코드 리뷰만으로 부분 분석하는 단계. ML 서비스는 영역이 넓어서 한꺼번에 보면 산만하다. 다음 4개 축으로 분리해 병렬 분석한다.

- **요청 진입·스케줄링** — 엔드포인트, GPU 라우팅, RequestTracker
- **워커 풀·라이프사이클** — spawn/init/recycle, MAX_TASKS, worker death monitor
- **변환·추론 파이프라인** — PDF 백엔드, OCR, layout 모델
- **I/O 전후처리** — 외부 OCR API, 파일 변환, 후처리 (markdown 생성)

영역마다 "Top 3 의심 지점" 을 file:line 정확도로 뽑아 통합하면 자바의 architecture review 와 같은 효과를 낸다.

### 추정값 → 실측 교체

자바 트러블슈팅에서 "왜 느릴까" 추측은 거의 항상 틀린다. 실측을 먼저 보는 게 원칙. ML 서비스도 같다.

- 운영 로그 grep — 단계별 시간, 503 비율, worker 라이프사이클
- `nvidia-smi` + Grafana — GPU 메모리 추세, 사용률
- 워커 PID 별 RSS 추적 (10분 ~ 1시간 간격으로 시계열)
- DOCLING_PROFILE_TIMINGS 같은 라이브러리 자체 프로파일 활용

내가 한 번 분석에서 추정한 "워커 재시작 30-90초" 가 실측에서 5.74초로 나왔다. 추정과 실측이 5-15배 어긋날 수 있다. 자바 GC 튜닝에서 "stop-the-world 가 길 것 같다" 가 실제로는 안 일어나는 케이스와 같다.

### 우선순위표 + GitHub 이슈

영역별 발견을 (영향도 × 변경 비용) 으로 정렬한 표로 합친다. 자바 진영의 backlog grooming 과 같은 절차.

이슈 본문에는 다음 6 섹션을 포함한다.

```
1. 배경 / 현재 문제 (실측 수치 + 근거)
2. 제안 조치
3. 변경 위치 (file:line)
4. 구현 계획 (체크리스트)
5. 측정·회귀 검증 방법
6. 완료 조건 (acceptance criteria)
```

자바 트러블슈팅 티켓과 같은 구조지만 측정·회귀 검증이 더 명시적이어야 한다. ML 서비스는 markdown 출력 같은 비-결정적 산출물의 회귀를 byte-level 로 확인해야 변경의 안전성을 보장할 수 있다.

### 보안 + 코드 품질 추가 점검

성능 분석이 본격이지만 사이드 패스로 다음도 같이 본다.

- **보안** — SSRF (`/parse/url`), 운영 엔드포인트 무인증 (`/restart`), 파일 다운로드 크기 검증, 시크릿 로깅 (OWASP Top 10 매핑)
- **silent failure** — bare `except:` 패턴, 에러 삼키기, fallback 의 잘못된 결과 반환
- **race condition** — multi-process / multi-thread 공유 상태의 lock 누락 (이번 분석에선 OCR 플러그인의 lock TOCTOU race 가 발견됨)

자바 백엔드와 다른 점: ML 라이브러리는 OSS 인 경우가 많아 외부 코드도 같이 봐야 할 때가 있다. native 바인딩의 락 처리 같은 부분.

### 로컬 테스트 환경 + 카나리 배포

Mac M-series 에서 CPU 모드로 환경을 세팅해 정확성 (correctness) 회귀 테스트. GPU 성능 검증은 운영 클러스터의 한 인스턴스를 LB 에서 빼서 처리. 자바 진영의 Kubernetes rolling deployment 와 같은 그림인데, GPU 워커가 비싸서 한 인스턴스 빼는 것의 trade-off 가 크다.

| 검증 항목 | Mac 가능? |
|---|---|
| markdown 출력 동일성 | ✓ CPU 모드 |
| 보안·인증·async 동작 | ✓ |
| race condition | ✓ |
| GPU 성능 수치 | ✗ |
| VRAM 추세 | ✗ |
| 503 폭풍 검증 | ✗ |

GPU 검증은 운영 카나리로 미루는 게 자연스럽다. 자바라면 staging 환경에서 부하 테스트로 처리하는 단계.

## 자바와 결정적으로 다른 두 가지

위 워크플로 안에서 자바 백엔드 경험만으로는 안 보이는 두 가지 함정.

### 모델 로딩 비용이 누적 비용이라는 점

자바 Spring Boot 부팅은 한 번이고 그 뒤로는 무관하다. ML 서비스의 모델 로딩은 **워커가 죽고 다시 spawn 될 때마다 반복**된다. `MAX_TASKS_PER_WORKER` 가 작으면 누적 부담이 폭증한다.

이 패턴을 처음 보는 자바 개발자는 "그냥 worker 더 띄우면 되지 않나" 라고 생각하기 쉽다. 실제로는 VRAM·CUDA context 비용이 따라 붙어 worker 수에 자연스러운 상한이 있다. [Multi-process GPU 글](./java-to-python-multiprocess-gpu-worker-pool.md) 에서 다룬 트레이드오프.

### async / blocking 의 경계가 동시성 전체를 결정

자바 `@Async` 또는 Reactor 의 blocking 호출 함정은 알려진 패턴이지만, FastAPI 에서 `async def` 핸들러 안의 동기 호출이 이벤트 루프를 통째로 막는다는 사실은 더 가혹하다. worker 가 3개뿐인 환경에서 한 요청이 30초 동안 이벤트 루프를 점유하면 그 동안 들어온 모든 요청이 503 으로 거부된다.

내가 분석한 서비스의 12시간 데이터에서 거부율 96.7% 가 정확히 이 패턴의 누적이었다. 자바라면 thread pool 의 thread starvation 으로 표현되는 문제가 Python async 모델에서는 더 결정적 영향으로 나온다.

## 측정 → 변경 → 검증의 자바와 다른 점

자바 트러블슈팅의 단위는 보통 하나의 메서드, 하나의 쿼리, 하나의 GC pause. ML 서비스 변경은 단위가 더 굵다.

- **모델 옵션 한 줄 변경** (예: `images_scale=3.0 → 2.0`) 이 처리량과 품질을 동시에 흔든다. byte-level diff + 인식률 A/B 가 필요.
- **env 한 줄 변경** (`MAX_TASKS=3 → 50`) 이 워커 라이프사이클 전반을 바꾼다. 24시간 RAM 추세 + 503 비율 비교 필요.
- **외부 API 호출 패턴** (직렬 → 병렬) 변경이 rate limit 위반 위험까지 동반.

자바 단위 테스트보다 한 단계 위의 **A/B 테스트** + **카나리 운영 측정** 이 거의 항상 필요하다. 자바 진영에서도 큰 변경은 같은 절차를 따르지만 ML 은 더 자주, 더 명시적으로 필요하다.

## 시리즈 마무리

자바 백엔드 시각에서 Python ML 서비스를 처음 본 사람의 학습 경로를 10개 글로 정리했다.

- Python 문법 핵심 (Post 1) + OOP·데코레이터 심화 (Post 2) — 코드를 읽기 위한 전제
- 의존성 관리 (Post 3) — venv, uv, pyproject.toml
- FastAPI 기초 (Post 4) — Spring Boot 사용자가 빠르게 익히는 법
- async/await + blocking I/O (Post 5) — CompletableFuture·Reactor 와 다른 점
- GPU·CUDA·MPS (Post 6) — 새로운 컴퓨팅 평면
- PyTorch 텐서·모델 로딩 (Post 7) — 워커 spawn 이 무거운 이유
- Multi-process worker pool (Post 8) — ThreadPool 모델과 다른 점
- OCR 동작 원리 (Post 9) — Layout · Text · Post-process 파이프라인
- ML 서비스 성능 분석 워크플로 (이 글)

자바 백엔드 개발자가 ML 서비스를 두려워하지 않고 분석·개선할 수 있는 도구는 충분히 갖춰져 있다. 핵심은 **JVM 안에서만 보던 그림을 멀티 프로세스 + GPU + 외부 API 까지 확장하는 시각**. 그 위에 자바에서 익힌 트러블슈팅 감각을 그대로 옮기면 된다.

## 참고

- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [PyTorch Performance Tuning Guide](https://pytorch.org/tutorials/recipes/recipes/tuning_guide.html)
- [FastAPI Concurrency](https://fastapi.tiangolo.com/async/)
- [NVIDIA Performance Analysis Tools](https://developer.nvidia.com/performance-analysis-tools)
- [Real Python — Optimizing Python Performance](https://realpython.com/python-performance-optimization/)
