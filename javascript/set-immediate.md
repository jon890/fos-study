# `setImmediate()`

- `setTimeout(fn, delay)`
  - 최소 delay(ms)가 지난 뒤, fn을 실행하도록 Timers 큐에 등록
- `setInterval(fn, interval)`
  - interval(ms)마다 반복 실행되도록 Timers 큐에 등록
- `setImmediate(fn)`
  - 현재 이벤트 루프 사이클이 끝난 직후, Check 큐에서 실행

핵심:

- `setTimout` / `setInterval` -> 시간 기준
- `setImmediate` -> 이벤트 루프 단계 기준

## Node.js 이벤트 루프 구조

```text
┌─────────────┐
│   timers    │ ← setTimeout, setInterval
├─────────────┤
│ pending cb  │
├─────────────┤
│ idle/prepare│
├─────────────┤
│    poll     │ ← I/O 대기 & 콜백 실행
├─────────────┤
│    check    │ ← setImmediate
├─────────────┤
│ close cb    │
└─────────────┘
```

## setTimeout / setInterval의 동작 원리

- **setTimeout**
  - ```js
    setTimeout(fn, 0);
    ```
  - "즉시 실행" 아님
  - 의미:
    - **oms 이상 지난 후**
    - timers 단계에서 실행 가능 상태가 되면 실행
  - poll 단계가 길어지면 **더 늦게 실행될 수 있음**
- **setInterval**
  - ```js
    setInterval(fn, 1000);
    ```
  - timers 단계에서
  - 이전 실행이 끝난 시점 기준이 아니라
  - **interval이 지났는지 여부**로 실행 여부 판단
  - 주의:
    - 콜백 실행 시간이 길면
    - 호출 간격은 **밀릴 수 있음**
    - **겹쳐서 실행되지는 않음** (싱글 스레드)

## setImmediate의 동작 원리

```js
setImmediate(fn);
```

- poll 단계가 끝난 뒤
- check 단ㄱPdptj tlfgod
- 시간 개념 X

### 왜 존재하나?

> "I/O 콜백 이후에, 다음 timers 전에 실행하고 싶다"

즉

- `setTimeout(0)`보다, **I/O 콜백 이후 실행이 더 보장됨**

## 예시

### I/O 콜백 내부

```js
require('fs').readFile(__filename, () => {
  setTimeout(() => console.log('timeout'), 0);
  setImmediate(() => console.log('immediate'));
});
```

결과는 **항상**

```text
immediate
timeout
```

이유:

- readFile 콜백 -> poll 단계
- poll 끝 -> check -> setImmediate
- 다음 루프 -> timers -> setTimeout

## setInterval과 이벤트 루프 관계

- 매 이벤트 루프의 **timers 단계**에서 검사
- interval이 지났으면 실행
- 실행이 밀리면 다음 실행도 밀림
- 누적 실행 X

- 그래서 정확한 주기 작업에는
  - setTimeout 재귀 패턴이 더 안전한 경우도 많음

## 언제 무엇을 쓰는가? (실무 기준)

### setTimeout

- 재시도
- debounce
- 일정 시간 지연

### setInterval

- polling
- heartbeat
- 단순 주기 작업

### setImmediate

- I/O 이후 후처리
- 이벤트 루프 양보
- CPU-heavy 작업을 쪼갤 떄

## setImmediate vs Promise 실행 순서

핵심 규칙

> Promise (`then`, `finally`)는 setImmediate보다 항상 먼저 실행된다

이유:

- Promise -> Microtask Queue
- setImmediate -> Check phase (Macrotask)

실행 우선순위 요약

```text
현재 콜스택
↓
Microtask Queue
  - Promise.then
  - Promise.finally
  - queueMicrotask
↓
(Event loop phase 이동)
↓
Check phase
  - setImmediate
```

> Microtask는 이벤트 루프 phase를 건너뛰고 즉시 실행
