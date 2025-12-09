# Async Iterator와 제너레이터

## Async Iterator

- 예시

```ts
for await (const transaction of streamTransactions()) {
}
```

- 비동기적으로 하나씩 값이 흘러오는 컬렉션을, 순서대로 기다리면서 소비하는 문법
- 이게 재대로 동작하려면 `streamTransactions()`는 async iterable이어야 하고, 그 안에서 보통 `yield`, `yield` + `await`을 사용하는 (async) generator로 구현되어 있다.

### `for...of` vs `for await...of`

- **일반 for...of**
  - ```ts
    for (const x of iterable) {
      // iterable[Symbol.iterator]() 사용
    }
    ```
  - `iterable[Symbol.iterator()]`를 호출해서 동기 iterator를 얻고,
  - 그 iterator의 `next()`를 계속 호출하면서 `{ value, done }`를 받아서 루프를 돎
  - 모든 `next()` 호출은 즉시 값을 반환해야 함 (Promise 말고 그냥 값)
- **`for await...of`**
