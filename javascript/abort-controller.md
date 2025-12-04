# AbortController

> JS에서 비동기 작업을 취소할 수 있도록 만든 공식 표준 API
> -> fetch, stream, timer, custom async 함수 모두 취소 가능

핵심 구성 요소는 두 가지

- AbortController : 취소 명령을 만드는 컨트롤러
- AbortSignal : 취소 여부 및 이벤트를 전달하는 신호 객체

```ts
const controller = new AbortController();
const signal = controller.signal;
controller.abort(); // 취소 신호 발생
```

## 1. HTTP 요청을 "중간에 취소" 할 수 있다 (fetch 기반 클라이언트에서 모두 지원)

예를 들어, fetch 요청을 취소할 수 있음

```ts
const controller = new AbortController();
const signal = controller.signal;

fetch('/api/data', { signal })
  .then((res) => res.json())
  .catch((err) => {
    if (err.name === 'AbortError') {
      console.log('요청이 취소됨');
    }
  });

// 200ms 후 강제 취소
setTimeout(() => controller.abort(), 200);
```

-> 응답이 오기 전에 네트워크 연결을 끊고,
-> fetch는 즉시 Reject 되며,
-> 소켓도 clean-up 됨

## 2. abort 시 단순히 "requestㄹ르 취소하는 것"이 아니다

AbortSignal은 비동기 함수들이 취소 상태를 관찰하는 통일된 구조다

- async stream 읽기 중 취소
- 오래 걸리는 연산 취소
- 반복적인 조회(polling) 취소
- 타임아웃 구현
- 외부 API retry 작업 중간 중단
- 예시
  ```js
  async function longTask(signal) {
    for (let i = 0; i < 10000; i++) {
      if (signal.aborted) throw new Error('Aborted');
      await doSomething(i);
    }
  }
  ```

## 3. abort 시 어떤 일이 일어나는가?

### fetch 라면

- underlying TCP 소켓이 닫히거나 read/write가 중단됨
- Promise가 reject됨 (AbortError)
- 메모리가 해제됨
- timeout처럼 대기하지 않고 즉시 중단됨

### stream 이라면

- reader.cancel() 발생
- 읽기/쓰기 중단
- 리소스 해제

### event listener나 timer라면?

- 개발자가 수동으로 체크해야 함 (AbortSignal에 event listener 등록 가능)

## 4. AbortController는 HTTP 용도뿐 아니라 "타임아웃 구현"에도 자주 쓰인다

```js
function withTimeout(promise, ms) {
  const controller = new AbortController();

  const timeout = setTimeout(() => controller.abort(), ms);

  return fetch(promise, { signal: controller.signal }).finally(() =>
    clearTimeout(timeout),
  );
}
```
