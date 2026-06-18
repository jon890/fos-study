---
series: "자바 백엔드 개발자를 위한 Python 입문"
seriesOrder: 3
---

# Java 개발자를 위한 Python 심화 — OOP·데코레이터·컨텍스트 매니저

[Post 1 (Python 문법 핵심)](./java-to-python-syntax.md) 에서 클래스·데코레이터·`with`·`yield` 는 다음 글로 미뤘다. 이 글에서 마저 정리한다. 코드를 "쓰는" 단계로 넘어가려면 이 다섯을 알아야 한다.

자바 record·Lombok·annotation·`AutoCloseable`·`Iterator` 와 1:1 로 비교해 가며 차이만 짚는다.

## dunder method — 자바의 `equals/hashCode/toString` 자리

Post 1 에서 양 옆에 언더스코어 두 개가 박힌 메서드를 dunder 라 부른다고 짚었다. 자바의 `Object` 가 가지고 있는 핵심 메서드 자리에 Python 은 dunder 가 들어간다.

| 자바 | Python | 호출되는 시점 |
|---|---|---|
| 생성자 | `__init__` | `Worker("x")` |
| `toString()` | `__repr__` / `__str__` | `print(obj)`, `repr(obj)` |
| `equals(Object)` | `__eq__` | `a == b` |
| `hashCode()` | `__hash__` | `set` 또는 `dict` 키로 사용 시 |
| `Comparable.compareTo` | `__lt__` 등 | `<`, `sorted()` |
| `Iterable.iterator()` | `__iter__` | `for x in obj` |
| `AutoCloseable.close()` | `__exit__` | `with obj:` 블록 종료 |
| `length` (가상) | `__len__` | `len(obj)` |

자바는 연산자 오버로딩이 거의 없지만 Python 은 dunder 로 사실상 모든 연산자를 가로챈다. `a == b` 의 동작이 클래스마다 다른 이유다.

```python
class Money:
    def __init__(self, amount: int):
        self.amount = amount
    def __repr__(self) -> str:
        return f"Money({self.amount})"
    def __eq__(self, other) -> bool:
        return isinstance(other, Money) and self.amount == other.amount
    def __hash__(self) -> int:
        return hash(self.amount)
```

`__eq__` 만 구현하고 `__hash__` 빠뜨리면 `set` 에 넣을 때 자바와 비슷한 사고가 난다. 자바에서 `equals` 만 오버라이드하고 `hashCode` 안 만지면 `HashSet` 동작이 깨지는 것과 같다.

## `@property` — getter/setter 자리

자바는 `getName() / setName(name)` 패턴이 관용구다. Lombok 의 `@Getter/@Setter` 도 결국 같은 메서드를 만든다.

Python 은 **필드 접근처럼 보이는데 메서드가 실행되는** `@property` 를 쓴다.

```python
class Worker:
    def __init__(self, max_tasks: int):
        self._max_tasks = max_tasks      # 관용적으로 앞에 _ 붙이면 "내부용" 표시

    @property
    def max_tasks(self) -> int:
        return self._max_tasks

    @max_tasks.setter
    def max_tasks(self, value: int) -> None:
        if value < 1:
            raise ValueError("must be >= 1")
        self._max_tasks = value

w = Worker(50)
print(w.max_tasks)   # getter 호출. 괄호 없음.
w.max_tasks = 100    # setter 호출. 검증 들어감.
```

`obj.field = value` 한 줄이 사실은 메서드 호출이라는 점만 익히면 된다. 자바 사고로 `w.max_tasks()` 처럼 괄호 붙이면 `int` 객체를 호출하려 들어서 `TypeError` 가 난다.

Python 에는 자바의 `private/protected/public` 같은 접근 제어자가 **없다**. 관행적으로 `_name` (한 개) 은 내부용, `__name` (두 개) 은 강한 내부용으로 본다. 강제는 아니다.

## dataclass — Java record/Lombok 자리

자바 14+ 의 `record` 또는 Lombok `@Data` 가 하는 일을 Python 은 표준 라이브러리 `dataclasses` 가 한다.

```python
from dataclasses import dataclass

@dataclass
class OcrResult:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]
    page: int = 0
```

이거 한 번 쓰면 자동으로 `__init__`, `__repr__`, `__eq__` 가 만들어진다. `frozen=True` 옵션을 주면 자바 record 처럼 불변이 된다. 우리가 분석한 OCR 플러그인 코드는 옵션 객체를 dataclass 로 받았다.

```python
@dataclass(frozen=True)
class OcrOptions:
    do_ocr: bool = True
    do_table: bool = True
    confidence_threshold: float = 0.5
```

자바 Lombok 의 `@Builder` 패턴이 필요하면 `dataclass` 와 `field(default_factory=...)` 조합으로 충분한 경우가 많다. Builder 까지 갖고 싶다면 `attrs` 또는 `pydantic.BaseModel` 로 넘어가는 편.

## 상속과 다중상속 — MRO 한 줄

자바는 클래스 다중상속이 없고 인터페이스 다중구현만 허용한다. Python 은 **클래스 자체를 여러 개 상속할 수 있다**.

```python
class A:
    def hello(self): print("A")

class B:
    def hello(self): print("B")

class C(A, B):
    pass

C().hello()   # A — 먼저 적힌 부모 우선 (MRO)
```

같은 메서드가 부모 양쪽에 있으면 **MRO**(Method Resolution Order) 라는 규칙으로 결정된다. `C.__mro__` 으로 순서 확인 가능. 실무에서 다중상속은 mixin (보조 기능 한정) 형태 외에는 거의 안 쓴다. Spring 의 `@Aspect` 나 자바 default method 가 채워주던 자리에 mixin 이 들어간다고 보면 비슷.

`super().method()` 호출은 자바와 거의 같다. 다만 `super()` 한 번에 MRO 가 알아서 다음 클래스를 찾아준다.

## 추상 클래스·Protocol — 자바 interface 자리

자바 interface 와 가장 가까운 건 `abc.ABC` 또는 `typing.Protocol`.

```python
from abc import ABC, abstractmethod

class OcrEngine(ABC):
    @abstractmethod
    def recognize(self, image) -> list[str]: ...

class CloudOcr(OcrEngine):
    def recognize(self, image):
        return ["..."]
```

ABC 는 자바 추상 클래스에 가깝다 (구현 못 한 메서드를 가진 채 인스턴스화하면 에러). `Protocol` 은 자바 interface 와 더 비슷하되 **명시적 상속 없이도 메서드 시그니처만 맞으면 통과**한다 (duck typing 의 타입 힌트 버전).

```python
from typing import Protocol

class Closeable(Protocol):
    def close(self) -> None: ...

def cleanup(resource: Closeable) -> None:   # Closeable 을 상속하지 않아도 OK
    resource.close()
```

자바 21 의 sealed interface 와는 결이 좀 다르다. Python 은 강제 계약이 아니라 "이 형태면 된다" 에 가깝다.

## 데코레이터 — 자바 어노테이션과 다른 동작

이 부분이 자바 개발자가 가장 헷갈리는 곳이다. **자바 어노테이션은 정적 메타데이터**고, 누군가 (런타임 프레임워크) 가 리플렉션으로 읽어야 동작한다.

```java
@RestController
@RequestMapping("/api")
public class UserController { ... }
```

Spring 이 부팅 시점에 어노테이션을 스캔해서 핸들러로 등록한다. 어노테이션 자체는 객체를 바꾸지 않는다.

**Python 데코레이터는 함수다.** 위에서 아래로 함수를 한 번 더 감싸는 함수.

```python
def log_call(func):
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"returned {result}")
        return result
    return wrapper

@log_call
def add(a, b):
    return a + b

# 위 @log_call 은 정확히 다음과 동치
# add = log_call(add)
```

`@log_call` 이라는 문법 설탕이 `add = log_call(add)` 를 의미한다. 즉 데코레이터는 함수를 인자로 받아 새 함수를 반환하는 **고차 함수**다. 자바 어노테이션처럼 스캐너가 따로 필요하지 않다. import 되는 순간 적용된다.

FastAPI 의 `@app.get("/users")` 도 같은 원리다. `app.get("/users")` 가 데코레이터(=함수)를 반환하고, 그 데코레이터가 핸들러 함수를 받아서 라우터에 등록한다.

```python
@app.get("/users")
def list_users():
    ...

# 풀어 쓰면
# decorator = app.get("/users")
# list_users = decorator(list_users)
```

자주 보는 표준 데코레이터 몇 개:

- `@classmethod` / `@staticmethod` — 자바의 static 메서드 자리. `cls` 또는 `self` 가 들어오는지가 차이
- `@functools.lru_cache(maxsize=128)` — 자바의 `@Cacheable` 비슷. 결과 메모이제이션
- `@property` — 위에서 본 getter
- `@dataclass` — 위에서 본 record

데코레이터는 **클래스에도 붙일 수 있고**, **체이닝도 가능**하다. 여러 개 쌓으면 아래에서 위로 적용된다.

```python
@app.get("/items/{id}")
@require_auth
@cache(ttl=60)
def get_item(id: int):
    ...
```

이 코드는 `get_item = app.get("/items/{id}")(require_auth(cache(ttl=60)(get_item)))` 와 같다. 자바 Spring 의 어노테이션 여러 개 쌓은 것과 외관은 비슷한데 **순서 의미가 명확**하다는 게 다르다.

## 컨텍스트 매니저 — try-with-resources 의 일반화

자바의 try-with-resources 는 `AutoCloseable` 인터페이스를 구현한 객체에만 동작한다. Python 의 `with` 는 `__enter__` / `__exit__` 두 dunder 가 있으면 무엇에든 적용된다.

```python
class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    def __exit__(self, exc_type, exc_val, tb):
        self.elapsed = time.perf_counter() - self.start
        print(f"elapsed={self.elapsed:.3f}s")
        return False   # True 면 예외를 삼킴. 보통 False.

with Timer() as t:
    do_work()
# 블록을 벗어나면 __exit__ 가 호출됨
```

자바 `AutoCloseable` 은 `close()` 만 호출하지만, `__exit__` 은 예외 정보 3개 (type, value, traceback) 를 받아 예외를 **삼킬지 다시 던질지** 선택할 수 있다. `with` 블록을 트랜잭션·락·일시 디렉터리·DB 세션 모두에 쓸 수 있는 이유다.

`contextlib.contextmanager` 데코레이터로 더 짧게 쓸 수도 있다.

```python
from contextlib import contextmanager

@contextmanager
def timer():
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f"elapsed={time.perf_counter() - start:.3f}s")

with timer():
    do_work()
```

여기서 등장하는 `yield` 가 다음 절의 주제다.

## 제너레이터·yield — Iterator 의 자연스러운 버전

자바 `Iterator<T>` 를 직접 구현하려면 `hasNext`/`next` 메서드를 짜야 한다. Python 의 `yield` 는 함수에 한 줄 추가하는 것만으로 같은 일을 한다.

```python
def page_numbers(total_pages: int, chunk_size: int):
    for start in range(0, total_pages, chunk_size):
        end = min(start + chunk_size, total_pages)
        yield (start, end)

for s, e in page_numbers(75, 30):
    print(s, e)
# (0, 30), (30, 60), (60, 75)
```

`yield` 가 있는 함수는 호출 시 즉시 실행되지 않고 **제너레이터 객체**를 반환한다. `for` 가 한 번 도는 순간 다음 `yield` 까지 실행되고 멈춘다. 자바 18 의 `Stream.generate(...)` 와 비슷한 lazy evaluation.

큰 데이터·페이지 단위 처리·무한 수열에 잘 맞는다. 우리가 분석한 PDF 청크 처리 코드도 30 페이지씩 끊어 yield 했다면 더 깔끔했을 것이다 (실제로는 list 를 통째로 채워 직렬 처리하고 있어서 별도 이슈로 잡힌 부분).

## 다음 글로 넘기는 것

- **async/await** — 자바 `CompletableFuture` 와 Reactor 와 모두 다르다. blocking I/O 함정과 함께 별도 글에서.
- **GIL**(Global Interpreter Lock) — 왜 Python 멀티스레드가 자바 멀티스레드와 다른가. 워커를 thread 가 아닌 process 로 띄우는 이유.
- **typing 심화** — `TypeVar`, `Generic`, `Protocol`, `TypedDict`, `Annotated` (FastAPI 가 적극 활용)

지금까지 두 글이면 우리가 다음 글들에서 다룰 코드를 줄 단위로 읽고, 적당히 수정할 수 있는 정도는 된다.

## 참고

- [Python Data Model — dunder methods](https://docs.python.org/3/reference/datamodel.html)
- [PEP 318 — Decorators for Functions and Methods](https://peps.python.org/pep-0318/)
- [dataclasses — Python docs](https://docs.python.org/3/library/dataclasses.html)
- [contextlib — Python docs](https://docs.python.org/3/library/contextlib.html)
- [Real Python — Primer on Python Decorators](https://realpython.com/primer-on-python-decorators/)
