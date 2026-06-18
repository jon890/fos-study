---
series: "자바 백엔드 개발자를 위한 Python 입문"
seriesOrder: 5
---

# Python async/await — CompletableFuture·Reactor 와 다른 점, 그리고 blocking I/O 함정

자바에서 비동기를 다루는 방법은 시대마다 달랐다. `Future.get()` 의 블로킹 시절, `CompletableFuture` 의 콜백 체인, Reactor·RxJava 의 스트림. 모두 **별도 스레드**에서 작업을 돌리고 결과를 받아오는 모델이다.

Python 의 `async/await` 는 다르다. **단일 스레드 안에서 이벤트 루프가 코루틴을 번갈아 실행**한다. 처음 보면 자바 모델과 비슷해 보이지만, 한 번 잘못 쓰면 동시성이 통째로 무너진다. 우리가 분석한 FastAPI 코드에서도 `async def` 안에서 `requests.get(...)` 을 호출하는 부분이 이벤트 루프 전체를 block 시켜 동시성을 깎고 있었다.

이 글은 async/await 의 개념을 자바 비동기 모델과 비교하면서, blocking I/O 함정과 회피법까지 정리한다.

## 단일 스레드 이벤트 루프라는 모델

자바 `CompletableFuture` 는 보통 `ForkJoinPool.commonPool()` 의 워커 스레드에서 작업을 돌린다. 콜백을 등록하면 어떤 스레드에서 실행될지는 라이브러리가 결정한다. 멀티스레드 + 콜백 조합.

Python `async/await` 는 단일 스레드 안에서 이벤트 루프가 코루틴들을 협력적으로 스케줄한다. **하나의 코루틴이 `await` 로 양보해야 다른 코루틴이 돌아간다**. 자바의 협력적 스레드 yield 와 비슷하지만, Python 은 OS 스레드를 더 만들지 않는 점이 결정적이다.

```python
import asyncio

async def fetch(url: str) -> str:
    print(f"start {url}")
    await asyncio.sleep(1)        # 양보 — 다른 코루틴 실행 기회
    print(f"done {url}")
    return f"{url} body"

async def main():
    results = await asyncio.gather(
        fetch("/a"),
        fetch("/b"),
        fetch("/c"),
    )

asyncio.run(main())
```

세 `fetch` 가 거의 동시에 시작하고 1초 뒤 거의 동시에 끝난다. 스레드 3개를 만든 게 아니라 같은 스레드 안에서 `await` 시점마다 다른 코루틴으로 점프하는 것뿐이다.

자바 `CompletableFuture.allOf(...)` 와 결과는 비슷하지만 내부 메커니즘이 다르다. 자바는 풀의 여러 스레드가 동시에 돈다. Python 은 한 스레드가 빠르게 왔다 갔다 한다.

## 왜 Python 은 단일 스레드를 골랐나 — GIL

이 모델을 이해하려면 **GIL** (Global Interpreter Lock) 을 짚어야 한다. CPython 은 한 번에 하나의 스레드만 바이트코드를 실행하도록 인터프리터에 락을 박았다. 멀티스레드를 만들어도 CPU 작업은 직렬화된다.

자바라면 `synchronized` 로 일부 임계 구역만 직렬화하는데, Python 은 인터프리터 자체가 큰 모니터 락 하나로 묶여 있는 셈. 결과적으로 **Python 멀티스레드는 CPU bound 작업에서 자바 멀티스레드만큼 빨라지지 않는다**.

I/O 작업은 다르다. 시스템 콜을 기다리는 동안 GIL 을 놓는다. 그래서 자바 multithreaded I/O 와 비슷한 동시성이 나온다. 다만 비동기 모델이 더 가볍다 — OS 스레드 1만 개는 메모리만 수 GB 인데, 코루틴 1만 개는 메가바이트 수준.

ML 워크로드처럼 CPU/GPU 가 무거운 작업은 **multiprocessing** (각 프로세스마다 독립 인터프리터·독립 GIL) 으로 풀어야 한다. 우리 프로젝트가 워커를 `ProcessPoolExecutor` 로 띄우는 이유가 정확히 이것. 자바라면 그냥 ThreadPool 로 충분했을 일이다. 이 주제는 다음 글에서 깊게 본다.

## 코루틴이 자바 Reactor 와 가까운 점, 다른 점

Reactor 와 async/await 의 공통점:

- 둘 다 callback hell 을 피하기 위해 선언적 체인을 제공
- 둘 다 단일 스레드 모델 (`Reactor` 의 `Scheduler.single()`, asyncio 의 기본 루프) 위에서 효율적
- 둘 다 backpressure 비슷한 개념이 있음 (asyncio 는 큐 사이즈, Reactor 는 onBackpressureBuffer)

차이점:

- Reactor 는 **Stream-of-N** 추상 (`Flux`). async/await 는 **단일 값** 비동기 (`Future` 비슷). 스트림은 `async for + 제너레이터` 로 풀어야 한다.
- Reactor 는 명시적으로 `subscribe()` 해야 실행. asyncio 는 `await` 또는 `gather/create_task` 가 실행 트리거.
- Reactor 의 `Mono.fromCallable(...).subscribeOn(Schedulers.boundedElastic())` 패턴이 asyncio 의 `run_in_executor(...)` 와 의도는 같다 (블로킹 작업을 별도 스레드로).

자바에서 `CompletableFuture` 든 Reactor 든 **이 작업이 어떤 스레드에서 도는가** 가 항상 명시적 또는 암묵적으로 추적된다. Python async 는 "**이 작업이 이벤트 루프를 양보하는가**" 가 중심 질문이 된다.

## 결정적 함정 — async 안의 blocking I/O

이 글의 핵심이다. `async def` 함수 안에서 동기 I/O 호출 (네트워크·파일) 을 직접 부르면 **이벤트 루프 전체가 멈춘다**. 동시에 들어온 다른 요청도 같이 멈춘다.

```python
@app.get("/parse/url")
async def parse_url(req: ParseRequest):
    response = requests.get(req.url, timeout=30)   # ⚠️ 30초 동안 모든 요청 block
    return process(response.content)
```

우리가 분석한 코드에 정확히 이 패턴이 있었다. FastAPI 가 `async def` 핸들러는 이벤트 루프에서 직접 돌리는데, 그 안에서 `requests.get(...)` 같은 동기 호출은 시스템 콜에서 GIL 만 놓을 뿐 이벤트 루프에는 양보하지 않는다. 결과적으로 동시에 들어온 다른 비동기 핸들러도 처리 못 한다.

worker 가 3개뿐인 환경에서 한 요청이 30초 동안 이벤트 루프를 점유하면, 그 동안 큐에 쌓인 요청은 503 으로 거부되거나 timeout 까지 대기한다. 단일 요청 latency 가 아니라 **전체 동시성**이 무너진다.

자바 비교: Spring WebFlux 에서 `Mono<String>` 안에 `restTemplate.getForObject(...)` (동기) 를 쓰는 것과 같다. Reactor 스레드가 막혀서 다른 요청을 못 받는다. 그래서 WebFlux 진영은 `WebClient` (논블로킹) 를 강제한다. Python 도 같은 원칙이다.

### 회피 방법 1: 진짜 비동기 라이브러리 사용

`requests` (동기) 대신 `httpx.AsyncClient` (비동기) 또는 `aiohttp`:

```python
import httpx

@app.get("/parse/url")
async def parse_url(req: ParseRequest):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(str(req.url))
    return process(response.content)
```

`await client.get(...)` 의 `await` 가 이벤트 루프에 양보 신호. 다른 코루틴이 그 사이 실행 가능.

파일 I/O 도 `open()` 대신 `aiofiles`:

```python
import aiofiles

async def save_upload(file, path):
    async with aiofiles.open(path, "wb") as f:
        while chunk := await file.read(8192):
            await f.write(chunk)
```

### 회피 방법 2: run_in_executor 로 별도 스레드 위임

이미 동기 라이브러리를 쓰고 있고 즉시 교체가 어렵다면, blocking 호출만 별도 스레드 풀에 위임한다.

```python
import asyncio

@app.get("/parse/url")
async def parse_url(req: ParseRequest):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,                       # 기본 ThreadPoolExecutor
        lambda: requests.get(str(req.url), timeout=30)
    )
    return process(response.content)
```

`run_in_executor` 는 자바 Reactor 의 `subscribeOn(Schedulers.boundedElastic())` 패턴과 정확히 같은 의도다. 동기 작업을 별도 스레드에서 돌리고 결과만 이벤트 루프로 반환.

장점은 코드 변경이 작다. 단점은 스레드 풀이 별도로 돌고, GIL 때문에 CPU bound 작업이면 큰 이득이 없다 (I/O bound 에는 유효).

### 회피 방법 3: 핸들러를 동기로

FastAPI 의 트릭. 핸들러를 `def` (동기) 로 정의하면 **FastAPI 가 알아서 별도 스레드에서 실행**한다. 이벤트 루프는 막히지 않는다.

```python
@app.get("/parse/url")
def parse_url(req: ParseRequest):       # async 가 아니라 그냥 def
    response = requests.get(str(req.url), timeout=30)
    return process(response.content)
```

핸들러가 `async def` 일 필요가 없는 경우 (예: 안에 비동기 호출이 없거나, 즉시 동기 라이브러리로 충분한 경우) 가장 간단한 회피책. 다만 스레드 풀 크기에 따라 동시성이 제한된다는 점은 알아둬야 한다.

## 우리 프로젝트의 실측 영향

분석 과정에서 `app.py` 의 다음 위치들이 blocking I/O 함정에 걸려 있었다.

- `app.py:2153` — `parse_document_from_url` (`async def`) 안에서 `download_file_from_url` → `requests.get` 동기 호출, 최대 30초 block
- `app.py:1907` — `get_file_extension_from_url` 의 fallback `requests.head` 동기 호출, 최대 10초 block
- `app.py:2261` — `parse_document_from_file` (`async def`) 안에서 `shutil.copyfileobj` 동기 파일 복사

worker 3개 환경에서 이 패턴들이 누적되어 동시성이 거의 의미를 잃은 상태였다. 단일 요청 응답시간은 같더라도 5요청 동시 처리 시 p95 가 폭증한다. GitHub 이슈로 따로 등록해 둔 부분.

## 정리 — 자바 개발자가 기억할 한 가지

자바 비동기는 "어느 스레드에서 도는가" 를 묻는다. Python 비동기는 "이벤트 루프를 양보하는가" 를 묻는다. `await` 키워드가 양보 신호다.

이걸 한 줄로 외워두면 다음 두 규칙이 자연스럽다.

> `async def` 안에서는 모든 I/O 가 `await` 와 함께 호출되어야 한다. `await` 없는 동기 호출은 이벤트 루프를 인질로 잡는다.

> 동기 라이브러리를 어쩔 수 없이 써야 하면 `run_in_executor` 또는 핸들러를 `def` (동기) 로.

다음 글은 이 모델이 ML 워크로드를 만났을 때의 한계 — GIL 과 multiprocessing, worker pool 패턴 — 을 자바 ThreadPool 과 비교해 정리한다.

## 참고

- [PEP 492 — Coroutines with async and await syntax](https://peps.python.org/pep-0492/)
- [asyncio — Python docs](https://docs.python.org/3/library/asyncio.html)
- [FastAPI — Concurrency and async / await](https://fastapi.tiangolo.com/async/)
- [httpx — Async usage](https://www.python-httpx.org/async/)
- [Real Python — Async IO in Python: A Complete Walkthrough](https://realpython.com/async-io-python/)
