---
series: "자바 백엔드 개발자를 위한 Python 입문"
seriesOrder: 4
---

# FastAPI 기초 — Spring Boot 사용자가 빠르게 익히는 법

Python ML 서비스를 분석하면서 가장 빨리 익숙해진 것이 FastAPI 였다. Spring Boot 를 써 본 사람이라면 손에 익기까지 한두 시간이면 충분하다. "어노테이션으로 라우팅 매핑하고, 클래스로 DTO 정의하고, 의존성 주입 받는다" 라는 큰 틀이 거의 그대로 옮겨온다.

다만 세부에서 사고방식이 다르다. Pydantic 이 자바 Bean Validation 자리에 들어가는데 강제 수준이 훨씬 세고, 의존성 주입은 Spring 컨테이너가 아니라 함수 시그니처에서 일어난다. 자동으로 생성되는 OpenAPI 문서는 SpringDoc 보다 손이 덜 간다.

이 글은 FastAPI 의 핵심 개념을 Spring Boot 와 1:1 로 비교하며 정리한다. [데코레이터 동작 원리](./java-to-python-oop-decorator.md) 와 [Python 문법 핵심](./java-to-python-syntax.md) 을 전제로 한다.

## 한 줄로 본 위치

FastAPI 는 Python 의 비동기 ASGI 웹 프레임워크다. Starlette (HTTP 처리) + Pydantic (데이터 검증) + 자동 OpenAPI 문서가 합쳐졌다.

Spring 진영과 짝지어 보면 이렇다.

| Spring Boot | FastAPI |
|---|---|
| Spring Boot (Tomcat/Undertow) | FastAPI + Uvicorn |
| `@RestController`, `@GetMapping` | `@app.get("/...")` |
| Jackson + Bean Validation | Pydantic |
| `@RequestBody`, `@PathVariable`, `@RequestParam` | 함수 인자 자체 (타입 힌트로 구분) |
| Spring DI (`@Autowired`, `@Bean`) | `Depends(...)` |
| `@RestControllerAdvice` (예외 처리) | `@app.exception_handler(...)` |
| SpringDoc / Springfox | 내장 — `/docs`, `/redoc` 자동 |
| `application.yml` | 보통 `.env` + `pydantic-settings` |
| Spring Security | FastAPI Security utils (OAuth2, API key) |

큰 차이는 두 가지: **클래스가 아니라 함수**가 핸들러의 단위라는 점, 그리고 **타입 힌트가 단순 메타데이터가 아니라 실제 검증 기준**이 된다는 점.

## Hello World — 라우팅·핸들러

자바 Spring 의 컨트롤러:

```java
@RestController
public class HelloController {
    @GetMapping("/hello/{name}")
    public Greeting hello(@PathVariable String name,
                          @RequestParam(defaultValue = "1") int times) {
        return new Greeting(name, times);
    }
}
```

같은 엔드포인트의 FastAPI:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Greeting(BaseModel):
    name: str
    times: int

@app.get("/hello/{name}")
def hello(name: str, times: int = 1) -> Greeting:
    return Greeting(name=name, times=times)
```

`@app.get("/hello/{name}")` 가 `@GetMapping` 자리. 차이는 **인자의 정체를 별도 어노테이션 없이 시그니처로 추론**한다는 점이다. URL path 의 `{name}` 과 매칭되는 인자는 `@PathVariable` 없이 그냥 같은 이름으로 받고, path 와 매칭 안 되는 인자는 자동으로 query parameter (`?times=3`) 로 잡힌다.

자바라면 `@PathVariable`, `@RequestParam` 을 일일이 붙여야 했던 일이 사라진다. 이는 다음에 볼 Pydantic 과 합쳐져 큰 위력을 발휘한다.

## Pydantic — Bean Validation 의 강화판

자바 Bean Validation 은 `@NotNull`, `@Size(min=1, max=100)` 같은 어노테이션을 필드에 박고, 컨트롤러에서 `@Valid` 로 활성화한다.

Pydantic 은 **타입 힌트 자체가 검증 규칙**이다.

```python
from pydantic import BaseModel, Field, HttpUrl

class ParseRequest(BaseModel):
    url: HttpUrl                                  # URL 형식 자동 검증
    do_ocr: bool = True                            # 기본값
    timeout: int = Field(default=30, ge=1, le=300) # 1 이상 300 이하
    languages: list[str] = ["ko", "en"]
    metadata: dict[str, str] | None = None         # Optional
```

핸들러에서 받는 방법:

```python
@app.post("/parse/url")
def parse_url(request: ParseRequest):
    ...
```

`request` 인자가 BaseModel 서브클래스라는 사실 하나로 FastAPI 가 알아서 다음을 처리한다.

- HTTP body 를 JSON 으로 파싱
- `ParseRequest` 에 캐스팅 + 검증
- 검증 실패 시 자동으로 422 응답 + 어느 필드가 어떤 이유로 틀렸는지 JSON 메시지

자바 `@RestControllerAdvice` 에서 직접 짜야 했던 검증 실패 응답 포맷이 기본으로 제공된다.

우리가 분석한 코드의 `URLRequest` (`app.py`) 도 거의 같은 형태였다. URL 다운로드 핸들러가 `request: URLRequest` 한 줄만 받고, 나머지 옵션 (`do_ocr`, `ja_doc`, `prior` 등) 은 다 Pydantic 이 검증.

## 의존성 주입 — Spring DI 와 결이 다르다

Spring DI 는 컨테이너가 빈을 관리하고 어노테이션으로 주입한다. FastAPI 는 컨테이너가 없고, **`Depends(...)` 함수**가 의존성을 표현한다.

```python
from fastapi import Depends, Header, HTTPException

def verify_admin_key(x_admin_key: str = Header(...)):
    if x_admin_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(403, "Forbidden")

@app.post("/restart", dependencies=[Depends(verify_admin_key)])
def restart_servers():
    ...
```

`Depends(verify_admin_key)` 는 핸들러 실행 전에 `verify_admin_key` 를 호출하고, 거기서 예외가 나면 핸들러는 실행되지 않는다. 일종의 Spring `HandlerInterceptor` 또는 메서드 시큐리티 어노테이션 역할.

리턴 값을 받아 핸들러 인자로 주입할 수도 있다.

```python
def get_db():
    db = SessionLocal()
    try:
        yield db                # 컨텍스트 매니저처럼 동작
    finally:
        db.close()

@app.get("/items")
def list_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

`yield` 를 쓰는 의존성은 자바의 `try-with-resources` 자리. 핸들러 종료 후 자동으로 `finally` 가 호출된다. 우리가 [Post 2 에서 본 컨텍스트 매니저](./java-to-python-oop-decorator.md) 의 응용.

Spring 의 `@Autowired` 는 클래스 필드/생성자에 박지만, FastAPI 는 핸들러 시그니처에 박는다. 클래스 단위가 아니라 **요청 단위**로 의존성이 새로 만들어지는 게 기본 (`Depends(use_cache=True)` 로 요청 안에서 캐시 가능).

## 동기·비동기 핸들러

핸들러를 `def` 로 정의하면 동기, `async def` 로 정의하면 비동기다.

```python
@app.get("/sync")
def sync_handler():
    time.sleep(1)               # 다른 요청 block
    return {"ok": True}

@app.get("/async")
async def async_handler():
    await asyncio.sleep(1)      # 다른 요청 처리 가능
    return {"ok": True}
```

FastAPI 는 `def` 핸들러를 스레드 풀에서 실행해 이벤트 루프 block 을 피하지만, `async def` 안에서 `requests.get(...)` 같은 동기 호출을 하면 그대로 루프가 멈춘다. 우리 프로젝트의 `/parse/url` 가 `async def` 인데 내부에서 동기 `requests.get` 을 호출해 동시성을 깎는 문제가 분석에서 잡혔다. 이 함정은 별도 글에서 자세히 본다.

## 응답 모델 — 직렬화 + 문서화

리턴 타입 힌트에 BaseModel 을 적으면 자동으로 직렬화 + OpenAPI 스키마에 반영된다.

```python
class ParseResponse(BaseModel):
    content: str
    page_count: int
    status: str

@app.post("/parse/url", response_model=ParseResponse)
def parse_url(request: ParseRequest) -> ParseResponse:
    ...
```

`response_model=ParseResponse` 옵션은 응답을 한 번 더 필터링한다. 의도하지 않은 필드가 노출되는 것을 막는다. 자바 Jackson 의 `@JsonView` 자리.

## 미들웨어와 lifespan

전역 처리 (CORS, gzip, 인증 일괄 등) 는 미들웨어로 처리한다. Spring 의 `Filter` 또는 `HandlerInterceptor` 자리.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

부팅·종료 훅은 `lifespan` 컨텍스트 매니저. Spring 의 `ApplicationListener` 또는 `@PostConstruct` / `@PreDestroy` 자리.

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await warmup_models()
    yield
    # shutdown
    await shutdown_workers()

app = FastAPI(lifespan=lifespan)
```

우리 프로젝트의 워커 풀 초기화·해체가 같은 패턴으로 들어가 있다. PaddleOCR·Docling converter 워밍업이 startup 단계에서 일어나고, shutdown 단계에서 워커 풀이 정리된다.

## OpenAPI 자동 문서 — SpringDoc 없이도

FastAPI 는 서버를 띄우자마자 두 개의 문서 페이지를 자동 제공한다.

- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/redoc` — ReDoc

Pydantic 모델, 타입 힌트, docstring 이 모두 스키마로 반영된다. Spring 진영에서 SpringDoc 또는 Springfox 를 설정·튜닝해야 했던 일이 거의 없다.

```python
@app.post("/parse/url",
          response_model=ParseResponse,
          summary="Parse document from URL",
          tags=["parse"])
def parse_url(request: ParseRequest):
    """
    URL 에서 문서를 다운로드해 markdown 으로 변환.

    - **url**: 다운로드 대상 URL
    - **do_ocr**: OCR 적용 여부
    """
    ...
```

docstring 의 마크다운이 그대로 `/docs` 에 렌더링된다. 자바에서 어노테이션으로 일일이 박았던 메타데이터가 docstring 한 곳에 모인다.

## 한계와 함정

FastAPI 가 만능은 아니다. Spring 진영에서 넘어올 때 부딪히는 부분들.

- **컨테이너가 없다** — `@Autowired` 처럼 어디서든 빈을 꺼내 쓰는 패턴이 없다. 의존성은 핸들러 시그니처를 통해서만 들어온다. 비-요청 컨텍스트 (예: 백그라운드 작업) 에서 DB 세션을 꺼내고 싶다면 직접 객체를 만들어 넘겨야 한다.
- **트랜잭션 자동 관리가 없다** — Spring 의 `@Transactional` 자리. SQLAlchemy 의 `Session` 을 `Depends` 로 받아 `try/commit/rollback` 을 핸들러나 서비스 함수에서 직접 짜야 한다.
- **AOP 가 없다** — Spring `@Aspect` 자리는 데코레이터 또는 미들웨어가 일부 대신하지만 1:1 대응은 아니다.
- **async 와 sync 가 섞이면 위험** — 핸들러를 `async def` 로 쓰면서 안에서 동기 I/O 를 호출하면 동시성이 무너진다. Spring 의 `@Async` 와는 다른 함정.

이 마지막 함정이 다음 글의 주제다. async/await 와 blocking I/O 함정, 그리고 자바 `CompletableFuture` / Reactor 와의 비교.

## 참고

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
- [Starlette docs](https://www.starlette.io/)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [PEP 484 — Type Hints](https://peps.python.org/pep-0484/)
