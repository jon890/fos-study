# 제너레이터(Generator)

- 제너레이터는 중단 가능한 함수(pausable function)이다
- 일반 함수는 다음과 같이 동작
  - 호출하면 -> 시작
  - return 만나면 -> 끝
  - 중간에 멈추지 못함
- 하지만 제너레이터는
  - 실행중 `yield`에서 멈춘 뒤
  - 나중에 다시 그 지점부터 이어서 실행(resume) 가능
- > "실행을 원하는 타이밍에 조금씩 나눠서 실행할 수 있는 함수"
- 자바스크립트에서는 `function*`으로 정의

## 제너레이터를 어디에 쓰는가? (이게 제일 중요)

- **1. 데이터를 하나씩(lazy evaluation) 스트리밍할 때**

  ```ts
  function* range(start, end) {
    for (let i = start; i < end; i++) {
      yield i;
    }
  }

  for (const n of range(1, 5)) {
    console.log(n); // 1,2,3,4
  }
  ```

  - 배열을 한 번에 만들지 않고 필요한 순간에 1개씩 생성 -> 메모리 절약

- **2. 무한한 시퀀스를 다룰 때**

  - 배열은 무한을 만들 수 없지만, generator는 가능

  ```ts
    function* infinite() {
      let n = 0;
      while (true) yield++;
    }
  ```

  - 필요할 때만 하나씩 꺼내 스면 됨

- **3. 이터러블 프로토콜 구현**

  - `for...of` 루프, 전개 연산자([...]), destructuring 등이 동작하려면 iterable이 필요함
  - generator는 자동으로 iterable + iterator를 구현함

  ```ts
  const g = function* () {
    yield 1;
    yield 2;
  };
  console.log([...g]); // [1, 2]
  ```

- **4. 비동기 흐름 제어(예전 패턴)**

  - 예전에는 async/await 나오기 전에
  - 제너레이터 + Promise + runner 패턴으로 비동기 코드를 동기 느낌으로 작성함
  - 대표적으로 Koa v1, co 라이브러리, Redux-saga

  ```ts
  function* saga() {
    const data = yield callApi('/user');
    yield put(action(data));
  }
  ```

- **5. 복잡한 상태 머신(state machine)을 단순화**

  - 아래 두 코드를 비교해보면 차이가 명확하다

  ```ts
  // 일반 구현
  function step(state, input) {
    if (state === 0) [
        if (input === 'A') return 1;
        if (input === 'B') return 2;
    ]
    // ... 코드 장황해짐
  }

  // 제너레이터로 상태 구현
  function* machine() {
    const x = yield "state A";
    const y = yield "state B";
    return "done"
  }
  ```

  - 제너레이터는 사실상 "코드를 자연스럽게 상태 머신으로 만들어주는 문법 설탕"

- **6. 직접 구현하는 Iterator/AsyncIterator의 편리한 구현체**

  ```ts
  // 수동 구현
  const iterable = {
    current: 0,
    next() {
      return { value: this.current++, done: false };
    },
    [Symbol.iterator]() {
      return this;
    },
  };

  // generator 사용
  function* numbers() {
    let n = 0;
    while (true) yield n++;
  }
  ```

- **7. 스트림 처리 (특히 async generator)**

  - 웹소켓, SSE, 풀링 기반 데이터 스트림 -> async generator와 `for await...of` 조합이 좋음

  ```ts
  async function* events() {
    while (true) yield await getNextEvent();
  }
  ```

## 제너레이터는 내부적으로 어떻게 동작하는가?

> 제너레이터 함수는 호출되는 순간 실행되지 않고, </br>
> 내부 실행 컨텍스트를 가지고 있는 iterator 객체를 반환한다

```ts
function* gen() { ...}
const it = gen(); // 실행 X!
it.next(); // 이때 실행 시작됨
```

- 이 `iterator` 안에는 다음이 담기게 됨
  - 제너레이터 함수의 실행 스택 일부
  - 현재 실행 위치 (PC: Program Counter)
  - 지역 변수 (state)
  - 마지막 yield 위치
  - done 여부
- 즉, 제너레이터는 자체 스택 프레임을 들고 있는 객체로 이해하면 맞음

- **1. 제너레이터는 컴파일 시 "상태 머신"으로 변환된다**

  ```ts
  // 제너레이터
  function* g() {
    console.log('A');
    yield 1;
    console.log('B');
    yield 2;
    console.log('C');
  }

  // 엔진 내부적으로 대략 아래와 같이 변환됨
  switch (state) {
    case 0:
      console.log('A');
      state = 1;
      return { value: 1, done: false };
    case 1:
      console.log('B');
      state = 2;
      return { value: 2, done: false };
    case 2:
      console.log('C');
      state = 3;
      return { value: undefined, done: true };
  }
  ```

  - 그래서, `yield` = 현재 상태를 저장하고 외부로 값 반환
  - 다음 `next()` 호출 = 해당 상태로 점프해서 이어서 실행
  - 이 구조이기 때문에
    - 함수가 중단(pause)된다
    - 지역변수도 유지된다
    - 재개(resume) 시 정확한 위치에서 시작한다

- **2. `next(value)`의 의미**

  ```ts
  function* g() {
    const x = yield 1;
  }

  const it = g();
  it.next(); // yield 1 출력
  it.next(42); // 42가 'yield 1' 표현식의 값이 됨
  ```

  - `yield`로 내보낸 값은 `next()` return값에 들어감
