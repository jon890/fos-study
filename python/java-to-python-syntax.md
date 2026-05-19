# Java 개발자를 위한 Python 문법 핵심

자바 백엔드만 다뤄오다가 Python 기반 ML 서비스를 분석해야 할 일이 생겼다. 코드를 읽기 시작하자마자 한 줄짜리 함수가 데코레이터로 둘러싸여 있고, 타입은 어디 갔는지 모르겠고, `self` 가 왜 첫 인자에 박혀 있는지 헷갈렸다. 이 글은 그때 내가 정리한 노트다. Python 을 처음부터 끝까지 훑는 게 아니라, **자바 개발자가 Python 코드를 빨리 읽기 위해 알아야 할 차이점**만 추렸다.

이 시리즈의 다른 글들에 등장하는 Python 코드를 이해하는 전제로 두기 위한 글이라 OOP·데코레이터·async 같은 심화 주제는 다음 글로 분리했다.

## 들여쓰기가 문법이다

자바는 `{}` 로 블록을 묶고, 들여쓰기는 사람을 위한 장식이다. Python 은 들여쓰기 자체가 블록의 경계다.

```python
def greet(name):
    if name:
        print(f"hi, {name}")
    else:
        print("hi, stranger")
```

스페이스 4개가 표준. 탭과 스페이스를 섞으면 `IndentationError` 가 난다. 자바에서는 `if` 한 줄 뒤 `{}` 빠뜨려도 컴파일은 되지만 Python 에서는 들여쓰기 어긋나면 그대로 에러다.

## 변수와 타입 — 동적 타이핑

자바는 정적 타이핑이다. `int n = 42;` 하면 `n` 은 영원히 `int`.

```java
int n = 42;
String s = "hello";
List<String> list = new ArrayList<>();
```

Python 은 동적 타이핑이다. 변수는 그냥 상자고, 어떤 객체든 담을 수 있다.

```python
n = 42          # int
n = "hello"     # 이제 str. 자바라면 컴파일 에러.
s = "hello"
items = []      # list, 제네릭 없음
```

여기까지 보면 "자유롭다" 가 아니라 "위험하다" 로 보인다. 그래서 Python 3.5 부터 **타입 힌트**(type hint)가 들어왔다.

```python
def parse(text: str, retries: int = 3) -> dict:
    ...
```

자바의 메서드 시그니처와 비슷한 정보를 담는다. 단 **런타임에 강제되지 않는다**. `parse(123, "abc")` 호출해도 인터프리터는 그대로 실행한다. 타입 힌트는 IDE 자동완성과 `mypy` 같은 정적 분석 도구를 위한 힌트일 뿐 자바의 컴파일 타임 체크와는 다르다.

요즘 Python 프로젝트는 타입 힌트를 거의 다 붙인다. 우리가 분석한 FastAPI 코드도 모든 핸들러 시그니처에 타입 힌트가 있다.

## None, null, 그리고 `is` vs `==`

자바의 `null` 은 Python 에서 `None` 이다. 단 비교 방식이 다르다.

```python
if x is None:        # 자바의 x == null 에 해당. 권장.
    ...
if x == None:        # 동작하긴 하지만 비권장. PEP 8 위반.
    ...
```

- `==` 는 자바의 `equals()` 와 비슷하다. 값 비교.
- `is` 는 자바의 `==` (참조 비교) 와 비슷하다. 같은 객체인가.

`None` 은 싱글톤이라 `is None` 이 안전하고 빠르다. 자바 개발자가 흔히 `x == null` 식으로 쓰면 동작은 하지만 코드 리뷰에서 지적받는다.

## 컬렉션 — list, dict, set, tuple

자바 컬렉션과 1:1로 짝지어 보면 빠르다.

| 자바 | Python | 비고 |
|---|---|---|
| `ArrayList<T>` | `list` | `[1, 2, 3]` |
| `HashMap<K,V>` | `dict` | `{"a": 1, "b": 2}` |
| `HashSet<T>` | `set` | `{1, 2, 3}` |
| 없음 (`Tuple` 외부 라이브러리) | `tuple` | `(1, "a", True)`, 불변 |

자바는 제네릭을 클래스에 박지만 Python list 는 어떤 타입이든 담는다. 타입 힌트로는 `list[int]` `dict[str, int]` 형태로 표기한다 (Python 3.9+).

가장 큰 함정: **mutable default argument**.

```python
def add_item(item, items=[]):   # ⚠️ 자바 사고로 보면 함정
    items.append(item)
    return items

add_item("a")  # ["a"]
add_item("b")  # ["a", "b"]  — 같은 list 가 재사용됨!
```

자바라면 메서드 호출마다 새 list 가 만들어질 것 같지만, Python 은 함수 정의 시점에 default 객체를 한 번만 만든다. 관용구는 `items=None` 으로 받고 함수 안에서 `items or []`.

```python
def add_item(item, items=None):
    items = items if items is not None else []
    items.append(item)
    return items
```

## 함수 — 일급 객체, 가변 인자, 키워드 인자

함수가 일급 객체라 변수에 담고 전달할 수 있다. 자바 8 람다/메서드 레퍼런스와 비슷한 감각.

```python
def double(x):
    return x * 2

f = double          # 함수를 변수에 담음
print(f(3))         # 6

list(map(double, [1, 2, 3]))   # [2, 4, 6]
```

자바와 가장 다른 부분은 **가변 인자**와 **키워드 인자**다.

```python
def call_api(url, *args, timeout=30, **kwargs):
    print(url, args, timeout, kwargs)

call_api("http://x", "a", "b", timeout=10, retry=True, auth=("u","p"))
# url="http://x", args=("a","b"), timeout=10, kwargs={"retry":True,"auth":("u","p")}
```

- `*args` 는 위치 인자 가변 (자바의 `String... args` 와 유사하지만 더 자유로움)
- `**kwargs` 는 키워드 인자 가변 (자바에 직접 대응 없음 — 굳이 비유하면 `Map<String, Object>` 를 마지막 인자에 받는 것)
- 호출 시 `timeout=10` 처럼 이름으로 인자를 지정 가능 (named argument)

FastAPI, requests, paddleocr 같은 라이브러리는 옵션을 모두 키워드 인자로 받는 게 일반적이다.

## 문자열 — f-string

자바는 `String.format("hi %s", name)` 또는 `"hi " + name` 이다. Python 3.6+ 에서는 **f-string** 이 사실상 표준.

```python
name = "world"
n = 3
msg = f"hi {name}, count={n}, double={n * 2}"
# "hi world, count=3, double=6"
```

`f"..."` 안에 `{}` 로 표현식을 넣는다. 표현식이라 함수 호출·연산 모두 OK. 자바 14+ 의 text block (`"""..."""`) 같은 멀티라인 문자열도 Python 은 `"""..."""` 트리플 쿼트로 같다.

## for 문 — iterator 가 표준

자바의 enhanced for 와 사실상 같지만 더 폭넓다.

```python
items = [10, 20, 30]
for x in items:
    print(x)

# 인덱스가 필요하면 enumerate
for i, x in enumerate(items):
    print(i, x)

# dict 순회
config = {"host": "localhost", "port": 8000}
for key, value in config.items():
    print(key, value)
```

`range(n)` 은 자바의 `IntStream.range(0, n)` 같은 감각.

## List comprehension — 자바 Stream 의 압축형

자바 8 Stream 의 `filter().map().collect()` 패턴이 Python 에서는 한 줄 표현식이다.

```python
nums = [1, 2, 3, 4, 5]

# 자바 stream
# nums.stream().filter(n -> n % 2 == 0).map(n -> n * n).collect(toList())

# Python comprehension
squares = [n * n for n in nums if n % 2 == 0]
# [4, 16]
```

dict 도 같은 패턴.

```python
config = {"HOST": "localhost", "PORT": "8000"}
lower = {k.lower(): v for k, v in config.items()}
```

자바보다 짧다는 게 장점이자 단점. 한 줄에 욱여넣으면 가독성이 무너지므로, 조건이 둘 이상 끼면 보통 `for` 루프로 푼다.

## 클래스 — 가볍게만 짚고 다음 글에서 심화

자바 클래스와 비슷하지만 몇 가지 큰 차이.

```python
class Worker:
    pool_size = 4   # 클래스 변수 (자바의 static)

    def __init__(self, name: str):   # 생성자
        self.name = name              # 인스턴스 변수

    def start(self):                 # 메서드. self 는 명시적
        print(f"start {self.name}")

w = Worker("kr-worker-1")            # new 키워드 없음
w.start()
```

핵심 차이 셋:
1. **`self` 가 명시적**: 자바의 암묵적 `this` 와 달리 메서드 첫 인자로 받는다. 호출할 때는 자동으로 채워진다.
2. **필드 선언이 없다**: 자바처럼 클래스 본문에 `private String name;` 같은 줄을 쓰지 않는다. `__init__` 에서 `self.name = ...` 으로 처음 대입할 때 필드가 생긴다.
3. **`new` 가 없다**: `Worker("x")` 자체가 생성.

`__init__` 처럼 양쪽 언더스코어 두 개로 둘러싼 메서드는 **dunder method** (double underscore) 라 부르며 자바의 `equals/hashCode/toString` 같은 특수 메서드에 해당한다.

## 예외 처리 — finally 는 거의 `with`

자바의 `try/catch/finally` 는 Python 의 `try/except/finally` 다. 자바와 다른 키워드 두 개:

```python
try:
    do_something()
except ValueError as e:        # catch 가 except
    print(f"bad: {e}")
except (KeyError, TypeError):  # multi-catch 는 튜플
    print("missing or wrong type")
finally:
    cleanup()
```

자바의 try-with-resources 에 해당하는 `with` 구문은 매우 자주 본다.

```python
with open("file.txt") as f:
    data = f.read()
# 블록을 벗어나면 f 가 자동 close 됨
```

`AutoCloseable` 이 구현된 자원이라면 `with` 로 묶는 게 관용구다. 우리가 분석 중인 코드에서 임시 파일 처리 시 `with` 누락이 문제로 자주 발견됐다.

## import 와 패키지 — 클래스가 아니라 모듈이 단위

자바는 파일 하나에 (보통) 클래스 하나, 패키지가 디렉터리. Python 도 디렉터리=패키지지만 **import 단위는 모듈(=`.py` 파일) 자체**다.

```python
# requests 패키지의 get 함수만 가져옴
from requests import get
get("http://example.com")

# 모듈 전체를 별칭으로
import numpy as np
np.array([1, 2, 3])

# 상대 import (같은 패키지 내)
from .util import helper
```

자바의 `import com.foo.Bar;` 한 줄에 클래스 하나 가져오는 것과 달리, Python 은 모듈 단위로 가져온 뒤 점 표기로 함수·클래스에 접근하는 게 일반적. `import numpy as np` 가 그 예.

## Truthy / Falsy — 자바보다 헐겁다

자바에서 `if (list)` 는 컴파일 에러다. `if (list != null && !list.isEmpty())` 처럼 풀어 써야 한다. Python 은 그냥 `if list:` 가 동작한다.

```python
if items:           # 빈 list 면 False
    process(items)

if name:            # None, "", 0 모두 False
    greet(name)
```

자바 코드를 옮길 때 `if not None and not empty` 검사를 Pythonic 하게 `if x:` 한 줄로 쓰는 경우가 흔하다. 다만 **0 과 빈 문자열도 False** 라는 점은 주의. 진짜로 `None` 만 거르고 싶다면 `if x is not None:` 으로 명시한다.

## 마무리 — 다음 글로 넘기는 것들

이 글은 코드를 "읽기" 위한 최소한이다. 본격적으로 **쓰려면** 다음을 추가로 알아야 한다.

- 데코레이터 (`@app.get(...)`, `@property`) — 자바 어노테이션과 비슷해 보이지만 동작 원리가 완전히 다르다. FastAPI 가 이걸 적극 활용한다.
- 컨텍스트 매니저 (`with` 의 내부 동작 — `__enter__/__exit__`)
- 제너레이터·yield — Java `Iterator` 와 비슷하지만 더 부드러움
- async/await — `CompletableFuture` 와 다르고 Reactor 와도 다르다 (별도 글 예정)
- GIL (Global Interpreter Lock) — 자바 스레드 모델과의 결정적 차이

각각은 시리즈 후속 글에서 다룬다. 일단은 여기까지만 알면 우리가 분석할 FastAPI + Docling + PaddleOCR 코드를 줄 단위로 읽을 수 있다.

## 참고

- [Python 공식 튜토리얼 — Classes](https://docs.python.org/3/tutorial/classes.html)
- [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 484 — Type Hints](https://peps.python.org/pep-0484/)
- [Real Python — Common Python Pitfalls (mutable default)](https://docs.python-guide.org/writing/gotchas/)
