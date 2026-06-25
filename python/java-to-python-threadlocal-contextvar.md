---
series: "자바 백엔드 개발자를 위한 Python 입문"
seriesOrder: 6
---

# ThreadLocal 에서 contextvars 로 — Python 의 요청 컨텍스트 전파

자바에서 요청 단위로 값을 들고 다니는 일은 `ThreadLocal`, 더 정확히는 그 위에 얹은 SLF4J `MDC` 의 몫이었다.
요청이 들어오면 인터셉터에서 `requestId` 를 `MDC` 에 넣고, 로그 패턴에 `%X{requestId}` 만 박아두면 그 요청에서 찍히는 모든 로그 줄에 같은 id 가 자동으로 붙는다.
함수 인자로 `requestId` 를 일일이 넘기지 않아도 된다는 게 핵심이다.

Python 으로 같은 일을 하려다 `threading.local` 을 먼저 떠올렸는데, async 코드에서 깨진다는 걸 알게 됐다.
정답은 `contextvars` 였다.
이 글은 자바의 `ThreadLocal`/`MDC` 감각을 Python 으로 옮기면서 정리한 노트다 — **둘이 거의 1:1 로 대응되지만, async 를 만나는 순간 갈라진다**는 점이 요지다.

## 문제 — 요청마다 다른 값을 인자 없이 꺼내고 싶다

서버에서 한 요청을 처리하는 동안에는 그 요청에만 해당하는 값이 있다.
`requestId`, 호출자 IP, 인증 주체 같은 것들이다.
이 값을 로깅·감사·추적에 쓰려면 호출 스택 깊은 곳까지 전달해야 하는데, 모든 함수 시그니처에 `request_id` 파라미터를 추가하는 건 끔찍하다.

그래서 "현재 실행 흐름에 묶인 저장소"가 필요하다.
요청 A 를 처리하는 흐름에서 꺼내면 A 의 값이, B 의 흐름에서 꺼내면 B 의 값이 나오는 저장소.
자바는 이걸 스레드 단위로 풀었고, Python 도 같은 출발점을 가진다.

## 자바에서는 ThreadLocal, 그리고 MDC

`ThreadLocal` 은 값을 **스레드마다 따로** 저장한다.
서블릿 컨테이너가 요청 하나를 스레드 하나에 묶어 처리하므로, 스레드별 저장소가 곧 요청별 저장소가 된다.

로깅에서는 이걸 직접 만지지 않고 `MDC`(Mapped Diagnostic Context)를 쓴다.
`MDC` 내부가 `ThreadLocal<Map>` 이다.

```java
// 진입점(인터셉터)에서 한 번
MDC.put("requestId", requestId);
// 이후 이 스레드에서 찍는 모든 로그에 requestId 가 붙는다 (패턴에 %X{requestId})
// 요청 끝나면 정리
MDC.clear();
```

전제는 "한 요청 = 한 스레드, 그리고 그 스레드가 요청 내내 유지된다"는 것이다.
이 전제가 깨지는 순간(비동기로 다른 스레드에 넘기면) `MDC` 도 따라가지 못해서, Reactor 의 context 전파나 `ThreadLocalAccessor` 같은 장치를 따로 붙여야 한다.

## Python 의 답 — contextvars

Python 3.7 부터 표준 라이브러리에 `contextvars` 가 들어왔다.
`ContextVar` 하나가 자바의 `ThreadLocal` 한 칸에 대응한다.

```python
import contextvars

# 모듈 레벨에서 생성한다 (closure 안에서 만들면 GC 가 제대로 안 됨 — 공식 문서 경고)
request_id_var = contextvars.ContextVar("request_id", default=None)

# 진입점에서 set
token = request_id_var.set("abc-123")

# 어디서든 get
request_id_var.get()   # "abc-123", 없으면 default(None)

# 복원 (set 이 돌려준 token 으로)
request_id_var.reset(token)
```

`set()` 이 `Token` 을 돌려주고 `reset(token)` 으로 이전 값으로 되돌린다는 점이 `ThreadLocal` 의 `set/remove` 보다 한 단계 정교하다.
중첩 호출에서 바깥 값을 안전하게 복원할 수 있다(같은 토큰은 두 번 못 쓴다).

## ThreadLocal 과 무엇이 같고 다른가

공식 문서가 직접 말한다 — "각 스레드는 자신의 context stack 을 가지므로, 서로 다른 스레드에서 값을 할당하면 `ContextVar` 는 `threading.local()` 과 비슷하게 동작한다."
즉 스레드 격리는 똑같다.
차이는 async 에서 드러난다.

| 항목 | 자바 `ThreadLocal`/`MDC` | Python `threading.local` | Python `contextvars` |
|---|---|---|---|
| 스레드별 격리 | O | O | O |
| 새 스레드가 부모 값 상속 | X | X | X (스레드는 빈 context 로 시작) |
| async/코루틴 단위 격리 | 해당 없음 | **X** — 깨짐 | **O** — Task 가 context 복사 |
| `await` 가로질러 값 유지 | 해당 없음 | **X** | **O** |
| 표준 위치 | `java.lang` / SLF4J | `threading` | `contextvars` (PEP 567) |

## 왜 threading.local 이 아니라 contextvar 인가 — async 에서 갈린다

`threading.local` 도 있는데 왜 굳이 `contextvars` 인가.
동기 스레드 모델만 쓴다면 둘은 사실상 같다.
갈리는 지점은 asyncio 다.

asyncio 는 보통 **한 스레드 안에서** 여러 코루틴을 번갈아 실행한다.
`await` 에서 실행권이 다른 코루틴으로 넘어갔다가 돌아온다.
`threading.local` 은 "같은 스레드면 같은 값"이라, 한 스레드에서 코루틴 A·B 가 번갈아 돌면 서로의 값을 덮어쓴다 — 격리가 깨진다.

`contextvars` 는 이걸 푼다.
asyncio 의 각 `Task` 는 생성될 때 현재 context 를 **복사**해서 들고 시작한다.
그래서 코루틴이 `await` 를 건너뛰어도 자기 context 의 값이 그대로 유지된다.
(자바 진영에서 Reactor 가 `Hooks.enableAutomaticContextPropagation()` 으로 풀려던 문제와 같은 문제를, Python 은 표준 라이브러리 차원에서 푼 셈이다.)

async 와 blocking 의 경계 감각은 [async/await 와 blocking I/O 함정](./java-to-python-async-blocking-io.md) 에서 더 다뤘다.

한 가지 비대칭에 주의한다.
**Task(asyncio)는 부모 context 를 상속하지만, 스레드(threading)는 상속하지 않는다.**
설계 의도가 다르기 때문이다 — Task 는 보통 자신을 띄운 코드와 논리적으로 묶인 짧은 작업이고, 스레드는 독립적인 장기 실행 단위로 본다.
그래서 `ThreadPoolExecutor` 로 작업을 넘기면 워커 스레드는 부모의 context 값을 못 받는다.
이게 뒤에서 다룰 함정의 핵심이다.

## 실전 패턴 — 로그에 자동 주입

`MDC` + `%X{requestId}` 의 Python 대응은 `contextvars` + `logging.Filter` 다.
`Filter` 가 모든 로그 레코드를 지나가므로, 거기서 contextvar 값을 레코드에 꽂으면 모든 로그 줄에 자동으로 붙는다.

```python
import logging
from mypkg.trace_context import request_id_var

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        # 이미 명시적으로 박힌 값이 있으면 보존, 없을 때만 contextvar 값 주입
        if getattr(record, "requestId", None) is None:
            record.requestId = request_id_var.get()
        return True

# 핸들러에 Filter 를 붙여두면 끝. 로그 호출부는 requestId 를 신경 쓸 필요가 없다.
handler.addFilter(RequestIdFilter())
```

이렇게 하면 로그를 찍는 쪽 코드는 `logger.info("done")` 만 호출하면 된다.
`requestId` 를 매번 `extra=` 로 넘기던 걸 진입점 1곳의 `set` + `Filter` 자동 주입으로 옮기는 것이다.
"새 로그를 추가할 때 requestId 전달을 잊는" 누락이 구조적으로 사라진다.

요청 단위 값을 "어느 계층에서 주입할 것인가"라는 고민은 자바의 [Filter · Interceptor · AOP 관심사 분리](../java/spring/filter-interceptor-aop.md) 와 같은 질문이다.
진입점에 한 번 꽂고 아래로는 전파에 맡긴다는 원칙은 언어와 무관하게 같다.

## 적용 사례 — gRPC 모델 추론 서버의 분산 추적

최근 내가 다루는 gRPC OCR 모델 추론 서버에 분산 추적을 붙이는 설계를 했다.
상위 API 서버가 자기 `requestId` 를 `X-Request-Id` 헤더로 실어 모델 서버를 호출하면, 모델 서버는 그 값을 자기 로그의 `requestId` 로 채워 양쪽 로그를 한 id 로 묶는 그림이다.

전파 방식으로 두 안을 놓고 고민했다.

- 호출마다 `requestId` 를 함수 인자/`extra` 로 명시 전달
- 진입점에서 contextvar 에 한 번 넣고 `Filter` 가 자동 주입

명시 전달은 새 로그가 생길 때마다 빠뜨릴 위험이 있어서, contextvar 방식을 택했다.
구조는 이렇다.

```python
# gRPC 진입점(인터셉터)에서 헤더 → contextvar
def set_request_id_from_metadata(metadata):
    rid = _find_header(metadata, "x-request-id")  # gRPC metadata 는 소문자 키
    if not rid:
        rid = uuid.uuid4().hex                      # 헤더 없으면 자체 생성 fallback
    request_id_var.set(rid)
    return rid
```

여기서 자바 경험이 그대로 도움이 됐다.
상위 API 서버(자바)는 인입 `X-Request-Id` 를 인터셉터에서 `MDC` 에 넣고, async 경계를 넘기 위해 Reactor context 전파를 따로 걸었다.
모델 서버(Python)는 같은 일을 진입점 contextvar + `Filter` 로 한다.
**양쪽이 같은 문제(요청 단위 값의 흐름 전파)를 각 언어의 표준 도구로 푼 것**이고, 개념이 1:1 로 겹쳐서 설계가 빨랐다.

> 이 서버는 gRPC 동기 서버라 요청이 워커 스레드에서 실행된다. 그래서 contextvar 의 async 이점을 당장 쓰는 건 아니지만, 표준이고 향후 async 전환에도 안전해서 `threading.local` 대신 골랐다.

OCR 파이프라인 자체의 구조는 [OCR 동작 원리](./ocr-pipeline-basics.md) 에 따로 정리했다.

## 어디서 깨지나

직접 정리하면서 확인한 함정들이다.

- **스레드 풀에 넘기면 값이 안 따라간다.** `ThreadPoolExecutor` 로 작업을 던지면 워커 스레드는 빈 context 로 시작한다(부모 미상속). 그 스레드 진입점에서 다시 `set` 하거나, `contextvars.copy_context()` 로 부모 context 를 복사해 `ctx.run(...)` 으로 실행해야 한다.
- **모듈 레벨에서 만들어야 한다.** `ContextVar` 를 함수/클로저 안에서 생성하면 GC 가 제대로 안 된다(공식 문서 경고). 모듈 전역에 한 번 선언한다.
- **reset 을 안 하면 값이 남는다.** 한 스레드를 재사용하는 풀에서 `set` 만 하고 `reset` 을 안 하면 다음 작업에 이전 값이 새어든다. 단, 요청마다 진입점에서 항상 `set` 하는 구조라면 매번 덮어쓰므로 안전하다. 애매하면 `token` 으로 `reset` 하거나 finally 에서 정리한다.
- **`threading.local` 을 async 에 쓰면 조용히 틀린다.** 에러가 안 나고 값만 뒤섞여서 디버깅이 어렵다. async 코드면 처음부터 `contextvars` 를 쓴다.

## 가져갈 기준

- async 코드(asyncio)면 고민 없이 `contextvars`. `threading.local` 은 `await` 에서 격리가 깨진다.
- 동기 스레드 모델만이면 둘 다 동작하지만, 표준이고 미래에 안전한 `contextvars` 를 기본으로 둔다.
- 요청 단위 값은 **진입점 한 곳에서 set**, 아래로는 `Filter`(또는 자바라면 `MDC` 패턴)로 자동 주입한다. 함수 인자로 끌고 다니지 않는다.
- 스레드 풀·executor 경계를 넘기면 context 가 자동으로 안 따라간다는 걸 기억한다 — 그 경계에서 명시적으로 복사하거나 다시 set 한다.

## 회고

자바에서 `MDC` 를 당연하게 쓰다가 Python 으로 넘어오니 "이건 뭘로 하지" 싶었는데, `contextvars` 가 거의 같은 모델이라 옮겨오는 비용이 거의 없었다.
오히려 `contextvars` 쪽이 async 까지 표준으로 커버해서 더 깔끔했다.
양쪽 언어가 같은 문제를 각자의 표준으로 푼 걸 나란히 놓고 보니, "요청 컨텍스트는 진입점에 한 번 꽂고 전파에 맡긴다"는 원칙 자체는 언어와 무관하다는 게 분명해졌다.

## 참고 링크

- [contextvars — Context Variables (Python 공식 문서)](https://docs.python.org/3/library/contextvars.html)
- [PEP 567 – Context Variables](https://peps.python.org/pep-0567/)
- [PEP 550 – Execution Context](https://peps.python.org/pep-0550/)
