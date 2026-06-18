---
series: "AI 서빙 인프라: GPU부터 문서 파싱까지"
seriesOrder: 5
---

# Multi-process GPU 워크로드 — 자바 ThreadPool 사용자가 만나는 모델 차이

자바 백엔드에서 `ThreadPoolExecutor` 는 거의 만능이었다. CPU bound 든 I/O bound 든 스레드 풀 크기만 잘 잡으면 동시성을 챙길 수 있었다. JVM 안에서 메모리를 공유하니 작업 간 데이터 전달도 가볍다.

Python ML 서비스는 그림이 다르다. `ThreadPoolExecutor` 가 있지만 CPU/GPU 작업에서는 거의 안 쓰고, 대신 `ProcessPoolExecutor` (실제 OS 프로세스 풀) 를 쓴다. 우리 프로젝트도 KR 워커 2개 + JA 워커 1개를 모두 별도 프로세스로 띄운다. 자바 시각에서는 "왜 굳이 무거운 프로세스를?" 라는 의문이 자연스럽게 생긴다.

이 글은 그 의문에 답하고, multi-process GPU 워크로드의 핵심 패턴 4개를 자바 ThreadPool 과 비교해 정리한다.

- worker 라이프사이클
- `MAX_TASKS_PER_WORKER`
- NVIDIA MPS
- worker death monitor

## 왜 thread 가 아니라 process 인가 — GIL 의 결정

이전 [async/await 글](../python/java-to-python-async-blocking-io.md) 에서 짚었듯 CPython 은 GIL (Global Interpreter Lock) 로 인터프리터에 큰 락을 박았다. 한 프로세스 안에서는 한 번에 하나의 스레드만 Python 바이트코드를 실행한다.

자바에서 `Runtime.getRuntime().availableProcessors()` 만큼 스레드를 띄워 CPU 작업을 병렬화하는 패턴은 Python 에서는 **거의 동작하지 않는다**. CPU 시간이 단일 스레드로 직렬화되기 때문.

GPU 작업도 비슷한 영향을 받는다. PyTorch 가 CUDA kernel 을 호출하는 잠깐 동안 GIL 을 놓지만, 그 외 파이썬 코드 (전처리·후처리·dispatch) 가 직렬화된다. 모델 추론 자체가 빠르더라도 주변 코드가 병목이 되면 throughput 이 올라가지 않는다.

해결책은 **프로세스 단위 격리**. 프로세스마다 독립 인터프리터·독립 GIL 을 가지므로 진짜 병렬 실행이 된다.

| 비교 | 자바 ThreadPool | Python ProcessPool |
|---|---|---|
| 단위 | OS 스레드 | OS 프로세스 |
| 메모리 | JVM 안에서 공유 | 격리 (IPC 필요) |
| 생성 비용 | 가벼움 (수십 μs) | 무거움 (Python 인터프리터 + 모델 로드, 수 초) |
| 데이터 전달 | 객체 참조 직접 | pickle 직렬화 + IPC |
| GIL 영향 | 없음 | 없음 (프로세스 분리) |
| OOM 영향 범위 | JVM 전체 | 해당 프로세스만 |
| 모니터링 단위 | `jstack` | `ps`, `nvidia-smi` |

가장 큰 차이는 **메모리 격리와 생성 비용**. 자바라면 1ms 만에 새 스레드를 만들지만, Python ProcessPool 의 worker spawn 은 우리 실측으로 5.74초 (`MAX_TASKS_PER_WORKER` 도달 시 매번). [PyTorch 모델 로딩 글](../python/java-to-python-pytorch-tensor-model-loading.md) 에서 분해한 다섯 단계가 매 spawn 마다 반복된다.

## ProcessPoolExecutor 의 동작

자바의 `ExecutorService` 자리에 `concurrent.futures.ProcessPoolExecutor` 가 들어간다.

```python
from concurrent.futures import ProcessPoolExecutor

def init_worker():
    # 워커 프로세스가 시작될 때 한 번만 실행
    global converter
    converter = build_converter()

def process_document(path: str) -> str:
    return converter.convert(path)

executor = ProcessPoolExecutor(
    max_workers=2,
    initializer=init_worker,
    max_tasks_per_child=50,
)

future = executor.submit(process_document, "/tmp/file.pdf")
result = future.result(timeout=1200)
```

`initializer` 는 자바 `ThreadFactory` 에서 `beforeExecute` 자리. **각 워커 프로세스가 시작될 때 한 번 호출**되어 무거운 모델을 미리 로드한다. 우리 코드의 `init_worker_process` 함수가 이 자리에서 PaddleOCR + Docling converter 를 워커마다 캐싱한다.

`max_tasks_per_child` 는 자바에 없는 옵션. 워커 한 명이 N 개 task 를 처리하면 자동으로 죽고 새 워커가 spawn 된다. 메모리 누수 방어용으로 도입된 패턴인데, 우리 분석에서는 이 값이 너무 작게 (`3`) 설정되어 throughput 손해가 큰 것으로 드러났다.

## 워커 라이프사이클

자바 ThreadPool 의 스레드는 보통 영원히 살아 있다. 작업 큐에서 작업을 꺼내 실행하고 다음 작업을 기다리는 것을 반복.

Python ProcessPool 의 워커는 라이프사이클이 더 명시적이다.

1. **Spawn** — `os.fork()` 또는 `spawn` 방식으로 새 프로세스 생성 (Linux 기본 `fork`, macOS·Windows 기본 `spawn`)
2. **Initialize** — `initializer` 호출, 모델 로딩, GPU 컨텍스트 생성. 5-30초 소요.
3. **Process tasks** — 작업 큐에서 task pickle 을 받아 실행, 결과 pickle 로 반환
4. **Recycle**(선택) — `max_tasks_per_child` 도달 시 종료, 새 워커가 자리에 spawn
5. **Death** — 예외·OOM·외부 시그널로 비정상 종료

자바와 결정적으로 다른 점은 **3번에서 4번 사이의 비용**. 자바 스레드는 그냥 다음 작업을 받지만, Python 프로세스는 종료 후 새 프로세스가 모델을 다시 로드한다. 워밍업 비용 5.74초가 이 사이클의 핵심 부담이 된다.

## MAX_TASKS_PER_WORKER 의 트레이드오프

자바 ThreadPool 에는 거의 없는 개념이지만 Python 에서는 표준 패턴이 됐다. 이유는 두 가지.

**메모리 누수 방어**: PyTorch / PaddleOCR 같은 native 라이브러리가 가끔 메모리를 명확히 회수하지 않는 케이스가 있다. JVM GC 처럼 자동 회수가 잘 되는 환경이 아니라서, 일정 작업마다 프로세스를 죽이고 다시 만들어 메모리를 초기화하는 게 안전.

**predictable shutdown**: 자바 GC tuning 처럼 메모리 추세를 예측하기 어려운 워크로드에서 "N 건마다 무조건 reset" 이라는 단순 규칙이 운영 안정성을 준다.

비용은 명확하다. 매번의 워밍업 시간이 누적된다. 우리 운영의 `MAX_TASKS=3` 은 12시간 동안 1,565회 워밍업 = 약 150분의 누적 다운타임을 만든다. 적정값을 찾으려면 메모리 추세를 실측한 뒤 점진적 상향을 권한다 (우리 케이스는 50 수준이 안전한 것으로 판단).

자바의 `Tomcat` 가 worker 스레드를 자동 재활용하지 않는 것과 대비된다. 자바는 그 자리에 heap dump + GC tuning 으로 대응. Python ML 서비스는 더 국소적인 "주기적 reset" 방식.

## NVIDIA MPS — multi-process GPU 효율화

[GPU·CUDA 글](./java-to-python-gpu-cuda-mps.md) 에서 NVIDIA MPS 를 짚었다. multi-process GPU 워크로드의 핵심 최적화.

기본 모드에서는 각 프로세스가 GPU 에 접근할 때 자체 CUDA context 를 만든다. 우리 워커 3개라면 CUDA context 3개 × 300-600MB = ~1.5GB VRAM 이 그냥 컨텍스트로 소비. T4 15GB 중에 큰 비중.

NVIDIA MPS daemon 을 띄우면 여러 프로세스가 같은 컨텍스트를 공유한다. VRAM 절약 + 컨텍스트 전환 비용 감소. 우리 운영은 현재 `MPS=OFF` 인데, multi-process 워커 수를 늘릴 때 MPS 를 켜는 게 ROI 있는 방향.

자바에는 비유할 게 없는 영역. JVM 자체가 프로세스 격리를 받지 않고 OS 의 GPU 직접 접근도 거의 없기 때문.

## Round-Robin GPU 스케줄링

multi-GPU 환경에서는 작업을 어느 GPU 에 보낼지 결정해야 한다. 우리 프로젝트 코드는 KR / JA / Priority 풀별로 Round-Robin index 를 락으로 보호하면서 GPU 를 순회한다.

```python
_kr_gpu_round_robin_idx = 0
_kr_gpu_round_robin_lock = threading.Lock()

def get_kr_executor() -> ProcessPoolExecutor:
    global _kr_gpu_round_robin_idx
    with _kr_gpu_round_robin_lock:
        idx = _kr_gpu_round_robin_idx % len(available_gpus)
        _kr_gpu_round_robin_idx += 1
    return _kr_executors[idx]
```

자바 `AtomicInteger` 의 `incrementAndGet()` 자리. 단 single GPU 환경에서는 `idx % 1 = 0` 으로 항상 같은 결과라 락만 잡고 효과가 없다. 우리 분석에서 이슈로 잡힌 부분. multi-GPU 클러스터로 확장될 가능성이 있는 코드라 일반화는 합리적이지만, 단일 GPU 케이스의 단락 처리를 추가하는 게 좋다.

## Worker death monitor — 자바엔 없는 패턴

자바 ThreadPool 의 스레드가 예외로 죽으면 풀이 새 스레드를 spawn 한다. Python ProcessPool 도 비슷하지만, **모니터링이 더 명시적**이다.

우리 코드의 `worker_death_monitor` 는 별도 thread 가 1초 간격으로 `executor` 의 워커 상태를 확인한다. 죽은 워커가 발견되면 즉시 새 worker 를 spawn 한다.

```python
def worker_death_monitor():
    while True:
        for executor in [_kr_executor, _ja_executor]:
            if has_dead_worker(executor):
                respawn(executor)
        time.sleep(1)
```

자바라면 `Thread.setUncaughtExceptionHandler` + 풀 내장 동작으로 해결되는 일을, Python 에서는 별도 watchdog 스레드로 풀어야 한다. 프로세스 간 통신·죽음 감지가 일반적으로 더 깨지기 쉬워서다.

## restart-all-at-once 패턴의 함정

우리 분석에서 가장 큰 운영 이슈로 잡힌 것이 `restart_all_executors_if_needed` 패턴. RAM threshold 도달 또는 수동 `/restart` 호출 시 KR/JA/Priority 풀을 **동시에** teardown 한 뒤 `_is_restarting=True` 동안 모든 incoming 요청을 503 으로 거부한다.

실측 결과 12시간 동안 503 응답이 225,803회. 거부율 96.7%. 같은 시점에 다른 풀이 살아 있도록 staggered restart 패턴이 필요하다는 결론.

자바 진영의 rolling restart (Kubernetes Deployment 의 `maxUnavailable`) 와 같은 개념인데, 단일 프로세스 안의 worker pool 단위에서 같은 패턴을 적용해야 한다. JVM 내부에서는 거의 마주치지 않던 문제.

## 정리

자바 ThreadPool 사용자가 Python multi-process worker pool 로 옮길 때 외워둘 한 줄.

> Python ML 워크로드는 GIL 때문에 thread 가 아닌 process 단위로 격리한다. process 는 비싸므로 worker 라이프사이클 (spawn, initialize, recycle) 이 핵심 비용이고, 모든 운영 문제 (503 폭풍, 메모리 누수, 워밍업 누적) 가 그 라이프사이클의 변형으로 환원된다.

다음 글은 이 위에서 OCR 파이프라인이 어떻게 동작하는지 (layout detection → text recognition → post-processing) 정리한다. ML 모델 추론의 실제 흐름을 보여주는 단계.

## 참고

- [concurrent.futures — ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor)
- [Python multiprocessing — Contexts and start methods](https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods)
- [NVIDIA Multi-Process Service (MPS)](https://docs.nvidia.com/deploy/mps/index.html)
- [PyTorch — Distributed and parallel training](https://pytorch.org/docs/stable/distributed.html)
- [Real Python — Speed Up Your Python Program with Concurrency](https://realpython.com/python-concurrency/)
