# Async Iterator와 제너레이터

비동기로 하나씩 값이 흘러오는 컬렉션을 순서대로 기다리며 소비하는 문법. Node.js 스트림, fetch의 ReadableStream, AI 모델 토큰 스트리밍, 페이지네이션이 있는 외부 API 등 "한꺼번에 메모리에 올리면 부담스러운 데이터"를 다룰 때 쓴다.

## 핵심 예시

```ts
for await (const transaction of streamTransactions()) {
  // transaction이 하나 도착할 때마다 처리
}
```

이게 동작하려면 `streamTransactions()`가 **async iterable**이어야 하고, 보통 `async function*`(async generator) 안에서 `yield`로 값을 흘려보낸다.

## `for...of` vs `for await...of`

두 문법은 모양이 비슷하지만 `next()`가 무엇을 반환하느냐가 다르다.

### 일반 `for...of`

```ts
for (const x of iterable) {
  // iterable[Symbol.iterator]() 사용
}
```

- `iterable[Symbol.iterator]()`를 호출해 **동기 iterator**를 얻음
- iterator의 `next()`를 호출하면 즉시 `{ value, done }`을 반환
- `next()`는 Promise가 아니라 **값 자체**를 반환해야 함

### `for await...of`

```ts
for await (const x of asyncIterable) {
  // asyncIterable[Symbol.asyncIterator]() 사용
}
```

- `asyncIterable[Symbol.asyncIterator]()`를 호출해 **비동기 iterator**를 얻음
- iterator의 `next()`는 `Promise<{ value, done }>`을 반환
- 루프는 매 단계마다 그 Promise를 `await`한 뒤 다음으로 넘어감

즉 `for await...of`는 **각 반복마다 비동기 작업을 기다린다**. 일반 배열에도 쓸 수 있지만(이 경우엔 `for...of`와 동일) 본격적인 사용처는 비동기 이터러블이다.

## Async Generator로 만드는 가장 단순한 형태

```ts
async function* streamTransactions() {
  let cursor: string | undefined = undefined;
  while (true) {
    const page = await fetchPage(cursor);
    for (const tx of page.items) {
      yield tx;
    }
    if (!page.nextCursor) break;
    cursor = page.nextCursor;
  }
}
```

- `async function*`은 결과 자체가 async iterable
- `yield`마다 한 값을 소비자에게 넘기고, 소비자가 `await`을 끝낼 때까지 generator는 일시정지
- `await`은 generator 안에서 그대로 쓰면 된다 (페이지 fetch, DB 쿼리 등)

페이지네이션·스트림 응답·이벤트 큐 같이 **언제 끝날지 모르는 데이터를 한 줄씩 흘리는** 패턴에 잘 맞는다.

## 종료와 에러 처리

`for await...of` 루프에서 `break`이나 `return`이 일어나면 generator의 `return()`이 호출되어 정리 단계가 실행된다. 이 정리를 안전하게 하려면 generator 안에 `try / finally`를 둔다.

```ts
async function* streamTransactions() {
  const conn = await openConnection();
  try {
    for await (const tx of conn.stream()) {
      yield tx;
    }
  } finally {
    await conn.close();   // break/return/예외 어느 경로로 빠져나가도 호출됨
  }
}
```

소비자 쪽에서 발생한 예외도 동일하다. `for await...of` 안에서 던진 에러는 generator의 `throw()`로 전달되어 `try/catch`로 잡을 수 있다. 외부 자원(파일 핸들, 커넥션, 워커 등)을 잡고 있는 generator를 만들 땐 `try/finally`를 거의 강제로 박아야 한다.

## 어떤 상황에 쓰면 좋은가

- **페이지네이션이 있는 외부 API 순회** — 한 번에 받지 말고 페이지를 yield로 흘려보내면 호출자가 필요한 만큼만 소비하고 멈출 수 있다
- **Node.js 스트림 / fetch ReadableStream** — 둘 다 async iterable을 노출하므로 `for await...of`로 받을 수 있다
- **LLM 토큰 스트리밍** — Anthropic·OpenAI SDK가 stream chunk를 async iterable로 노출. UI에 즉시 흘려주거나 어딘가로 forward할 때 자연스럽다
- **메시지 큐 컨슈머** — 메시지가 도착할 때마다 yield. 백프레셔(소비자가 느리면 generator도 자동으로 멈춤)가 자연스럽게 동작

반대로 **이미 한 번에 받아온 컬렉션**(예: DB에서 select 결과 100개)을 비동기 작업과 함께 처리하는 거라면 굳이 async generator를 쓸 필요는 없다. `Promise.all`이나 일반 `for...of` + `await`이 더 간결하다.

## 참고

- [for await...of (MDN)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for-await...of)
- [async function* (MDN)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/async_function*)
