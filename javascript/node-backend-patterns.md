# Node 백엔드 운영 패턴 — Streams 백프레셔, pipe/pipeline, 멱등성 vs 분산 락

기존 javascript/ 문서들이 다루지 않는 Node 백엔드 실전 패턴 두 가지를 묶어 정리한다.

- HTTP 클라이언트 / fetch / Ky / undici 비교 → [http-client.md](./http-client.md)
- AbortController / fetch 취소 / timeout 구현 → [abort-controller.md](./abort-controller.md)
- V8·이벤트 루프·메모리·CPU 운영 가이드 → [nodejs.md](./nodejs.md)

---

## 대용량 파일은 `readFileSync` 대신 Streams

### 문제 — `fs.readFileSync`

`fs.readFileSync`는 파일 전체를 한 번에 읽어 Node 프로세스 힙에 Buffer / String 으로 올린다. 파일이 커지면 메모리 사용량과 GC 부담이 비례해서 늘고, 처리 완료 전까지 메모리 해제가 불가능하다. CSV 한 건이 수백 MB 단위로 커질 가능성이 있는 운영 환경이라면 그대로 OOM 으로 이어진다.

### 해결 — `fs.createReadStream`

파일을 작은 chunk 단위로 읽고, 읽자마자 처리하고, 처리가 끝나면 버린다. 메모리에는 chunkSize 수준만 올라가 GC 부담이 적고, CSV 처럼 줄 단위로 처리 가능한 포맷에 잘 맞는다.

```ts
import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';

const rl = createInterface({
  input: createReadStream('big.csv', { encoding: 'utf8' }),
  crlfDelay: Infinity,
});

for await (const line of rl) {
  await processLine(line);
}
```

---

## Streams Backpressure — 생산 속도 > 소비 속도일 때 무엇이 일어나는가

### 정의

생산자(파일 읽기 등)가 소비자(DB Insert, 외부 API 호출 등)보다 빠를 때 데이터가 메모리에 누적되어 OOM 으로 이어지는 상황을 막기 위해, **소비자의 처리 속도에 맞춰 생산자의 속도를 늦추는 메커니즘**.

### Node Streams 가 처리하는 방식

- 모든 Readable / Writable 스트림은 내부 버퍼를 가지고 있고, 버퍼의 상한이 정해져 있다 (`highWaterMark` 옵션, 기본값 **64KB**).
- 소비자가 버퍼를 빠르게 소비하지 못하고 버퍼가 상한에 도달하면 **읽기를 일시 정지**해서 생산-소비 페이스를 맞춘다.
- 소비자가 다시 따라잡으면 자동으로 읽기가 재개된다.
- 즉 **64KB 라는 상한은 소비자 보호 장치**다. 운영 환경에서 큰 chunk 가 필요한 경우만 의식적으로 올려야 한다.

### 흔한 실수

- `for (const chunk of readable)` 처럼 동기 루프로 받으면서 안에서 `await db.insert(chunk)` 만 호출 — 이러면 백프레셔가 흐르지 않고 메모리에 누적될 수 있다. `pipeline()` 으로 잇거나 async iterator (`for await`) 를 쓰는 게 맞다.
- `data` 이벤트로 직접 받은 chunk 를 비동기로 흘려보내면서 `pause()` / `resume()` 을 직접 안 부르는 경우 — 라이브러리 추상화에 맡기는 게 안전하다.

---

## `pipe()` vs `pipeline()`

### `pipe()`

가장 단순한 연결. 한쪽 스트림의 출력을 다른쪽 입력으로 흘려보낸다. 작동은 하지만:

- **에러 전파가 자동이 아니다** — 중간 스트림에서 에러가 나도 뒤쪽 스트림은 계속 살아있을 수 있다.
- **리소스 자동 정리가 없다** — 파일 디스크립터, 소켓이 누수될 수 있다.

### `pipeline()` (Node 10+)

여러 스트림을 한 번에 잇고, 에러가 나면 모든 스트림을 정리하고 콜백 / Promise 로 에러를 전달한다. 운영 환경에서는 사실상 `pipeline()` 만 써야 한다.

```ts
import { pipeline } from 'node:stream/promises';

await pipeline(
  createReadStream('big.csv'),
  csvParser,
  validator,
  dbWriter,
);
```

> 단순 동작 확인은 `pipe()` 로 충분하지만, **운영 환경에서 안정성을 보장해야 하는 배치는 `pipeline()` 이 의도를 더 잘 드러내고 실패를 안전하게 다룰 수 있다**.

---

## 멱등성 키(Idempotency Key) vs 분산 락 — 역할 분리

POS / 결제처럼 네트워크 지연이나 timeout 이 흔한 환경에서는 **두 메커니즘을 혼동하지 말고 역할을 분리해야** 한다.

### 멱등성 키

- **목적**: "같은 요청을 다시 처리하지 않기 위한 장치".
- **상황**: 서버에서는 이미 처리됐지만 클라이언트가 응답을 받지 못해 같은 요청을 재시도하는 경우.
- **발급 주체**: 클라이언트 — 요청 성공 / 실패 여부를 인지할 수 있는 쪽이 발급해야 의미가 있다.
- **저장소**: TTL 기반 휘발성 — Redis 가 적합. TTL 은 재시도 윈도우(예: ~1시간) 정도.
- **서버의 역할**: 전달받은 키로 이미 처리된 요청인지 판단해 결과를 재사용하거나 중복 처리를 차단.

### 분산 락

- **목적**: "동시에 여러 요청이 들어와 상태가 꼬이는 상황을 방지하는 보조 수단".
- **상황**: 같은 유저 계정 / 같은 자원에 대해 동시에 여러 원자적 요청이 들어올 때.
- **저장소**: Redis 기반 SET NX, Redisson, Redlock 등.

### 결합 — 둘 다 필요한 경우

- 멱등성 키만 있고 분산 락이 없으면: 같은 키의 동시 요청 두 건이 모두 "신규" 로 판정되어 중복 처리될 수 있다.
- 분산 락만 있고 멱등성 키가 없으면: 클라이언트가 응답 누락으로 재시도했을 때 락은 풀려 있고, 결과 캐시도 없어 서버는 다시 처리해버린다.

> 멱등성 키는 **시간을 가로질러** 동일 요청을 연결하고, 분산 락은 **순간에 동시 요청**을 직렬화한다. 두 축이 다르므로 보통 같이 쓴다.

---

## 관련 문서

- [AbortController](./abort-controller.md) — fetch 취소 / timeout 구현
- [Async Iterator](./async-iterator.md) — async generator 와 백프레셔의 자연스러운 결합
- [HTTP Client](./http-client.md) — fetch / undici / Ky / axios 비교
- [Node.js 운영 주의 포인트](./nodejs.md) — V8, 이벤트 루프, 메모리, GC
- [결제 도메인 멱등성과 트랜잭션 재시도 기본기](../architecture/payment-idempotency-transaction-basics.md) — 결제 도메인 관점의 멱등성
- [Redis 분산 락](../database/redis/distributed-lock.md) — SET NX, Redisson, Redlock
