# [초안] Redis Streams 소비자 그룹 신뢰성 — PEL, 재할당, 멱등성까지

> 이 문서는 Redis Streams의 소비자 그룹(Consumer Group)이 *어떻게 메시지 유실 없이 분산 처리를 보장하는가*를 운영·장애 관점에서 정리한다. Stream의 기본 명령어와 Pub/Sub과의 비교는 [pub-sub.md](./pub-sub.md)에 이미 있으므로, 본 문서는 그 위에서 한 단계 더 들어간다 — *소비자가 죽었을 때 메시지는 어디에 남고, 누가 다시 처리하며, 중복을 어떻게 막는가*. 결론부터 말하면 Streams는 "메시지를 영속한다"가 아니라 **at-least-once + PEL(Pending Entries List) + 명시적 ACK**라는 세 부품의 조합으로 신뢰성을 만든다. 이 세 가지를 분리해서 설명할 수 있어야 한다.

학습 목표는 다음 세 가지다.

- `XREADGROUP`이 메시지를 PEL에 등록하는 순간과 `XACK`로 비우는 순간의 의미를 구분한다.
- 소비자가 죽은 뒤 남은 메시지를 `XPENDING` → `XCLAIM` / `XAUTOCLAIM`으로 회수하는 흐름을 설계한다.
- at-least-once 전달 위에서 멱등 소비(idempotent consumer)와 독약 메시지(poison message) 처리를 어떻게 얹는지 판단한다.

---

## 왜 소비자 그룹이 신뢰성의 핵심인가

단일 소비자가 `XREAD`로 스트림을 읽는 것만으로는 신뢰성이 없다. 읽고 나서 처리 중에 프로세스가 죽으면 그 메시지가 처리됐는지 아무도 모른다. 다시 읽으려면 마지막으로 읽은 ID를 소비자가 직접 어딘가에 저장해야 하는데, 그 저장 자체가 또 하나의 장애 지점이 된다.

소비자 그룹은 이 "어디까지 읽었나"와 "무엇을 아직 처리 못 했나"를 **서버 측 상태로** 들고 있다. 그래서 소비자가 재시작해도 자기가 받았지만 ACK하지 않은 메시지를 그대로 다시 받을 수 있다. Kafka의 컨슈머 그룹 + 오프셋 커밋과 같은 역할이지만, Redis는 오프셋 하나가 아니라 **개별 메시지 단위의 미처리 목록(PEL)**을 들고 있다는 점이 결정적으로 다르다.

---

## 핵심 작동 원리: PEL과 두 개의 시점

소비자 그룹의 신뢰성은 단 두 개의 시점으로 요약된다.

```bash
# 시점 1: XREADGROUP — 메시지를 받는 순간, PEL에 등록된다
XREADGROUP GROUP workers consumer-1 COUNT 10 STREAMS orders >

# 시점 2: XACK — 처리 완료를 알리는 순간, PEL에서 제거된다
XACK orders workers 1711500000000-0
```

`>` 는 "이 그룹의 누구에게도 아직 전달되지 않은 새 메시지"를 뜻한다. 이 호출이 성공하면 해당 메시지는 **그 소비자 이름으로 PEL에 기록**된다. PEL은 그룹별로 유지되는 "전달은 됐지만 아직 ACK 안 된 메시지" 목록이다.

여기서 가장 자주 틀리는 부분 — `XACK`를 호출하기 전까지 메시지는 PEL에 영원히 남는다. 소비자가 처리 도중 죽어도 메시지는 사라지지 않는다. 다시 살아난 소비자는 `>` 대신 자기 ID 범위를 지정해 자기 PEL을 다시 읽을 수 있다.

```bash
# 0 부터 읽으면 = 내가 받았지만 아직 ACK 안 한 메시지를 다시 가져온다 (재처리)
XREADGROUP GROUP workers consumer-1 COUNT 10 STREAMS orders 0
```

`>`는 새 메시지, `0`(또는 특정 ID)은 자기 PEL 재조회. 이 둘을 섞으면 안 된다.

### ACK를 처리 전에 할 것인가, 후에 할 것인가

이게 전달 시멘틱을 결정한다.

- **처리 후 ACK** (권장 기본값): 처리 성공이 확인된 다음 `XACK`. 처리 중 죽으면 PEL에 남아 재처리된다 → **at-least-once**. 중복이 발생할 수 있으므로 멱등성이 필수다.
- **처리 전 ACK**: 받자마자 `XACK` 후 처리. 처리 중 죽으면 메시지는 영영 사라진다 → **at-most-once**. 유실을 감수하는 게 맞는 비핵심 이벤트에만.

Redis Streams는 구조적으로 exactly-once를 보장하지 않는다. "정확히 한 번"은 at-least-once 전달 + 멱등 소비로 *결과적으로* 만드는 것이지, 브로커가 주는 게 아니다.

---

## 죽은 소비자의 메시지 회수: XPENDING과 XCLAIM

소비자 하나가 영영 돌아오지 않으면, 그 소비자의 PEL에 갇힌 메시지를 다른 소비자가 가져와야 한다. 이걸 자동으로 해주는 장치는 없다 — **직접 구현해야 하는 운영 책임**이다.

```bash
# 1. 그룹 전체의 미처리 현황 요약 (총 개수, 최소/최대 ID, 소비자별 분포)
XPENDING orders workers

# 2. 상세 — idle 시간이 60초(60000ms) 넘은 미처리 메시지 최대 10건
XPENDING orders workers IDLE 60000 - + 10

# 3. 특정 메시지를 consumer-2 소유로 강제 이전 (3600000ms 이상 idle인 것만)
XCLAIM orders workers consumer-2 3600000 1711500000000-0
```

`XCLAIM`의 idle 임계값이 안전장치다. "최소 N밀리초 동안 아무도 ACK 안 한 메시지만 뺏는다"는 조건이라, 아직 살아서 처리 중인 소비자의 메시지를 성급하게 빼앗지 않는다. 임계값을 너무 짧게 잡으면 느린 소비자의 메시지를 중복 처리하게 되고, 너무 길게 잡으면 장애 복구가 느려진다.

### XAUTOCLAIM — 스캔과 클레임을 한 번에

Redis 6.2부터는 `XPENDING`으로 스캔하고 `XCLAIM`으로 옮기는 두 단계를 `XAUTOCLAIM` 하나로 합칠 수 있다.

```bash
# idle 60초 넘은 미처리 메시지를 0번 커서부터 스캔해 consumer-2가 회수
XAUTOCLAIM orders workers consumer-2 60000 0 COUNT 10
```

반환값에 다음 커서가 포함되므로 커서를 이어가며 전체 PEL을 순회할 수 있다. 운영에서는 별도의 "회수 워커"가 주기적으로 `XAUTOCLAIM`을 돌려 고아 메시지를 흡수하게 만드는 패턴이 흔하다.

---

## 독약 메시지(poison message)와 데드레터

at-least-once의 그림자는 *영원히 실패하는 메시지*다. 처리할 때마다 예외가 터지는 메시지는 ACK되지 않으니 PEL에 남고, 회수 워커가 계속 다시 집어 처리를 시도한다 → 무한 재처리 루프.

`XPENDING ... IDLE` 상세 응답에는 각 메시지의 **전달 횟수(delivery count)**가 들어 있다. 이 값을 임계값으로 쓴다.

```text
1) 1) "1711500000000-0"
   2) "consumer-1"
   3) (integer) 920000     # idle time (ms)
   4) (integer) 5          # delivery count — 5번째 전달
```

전달 횟수가 임계값(예: 5)을 넘으면 다음 중 하나를 선택한다.

- 별도의 데드레터 스트림으로 `XADD` 후 원본은 `XACK`로 PEL에서 제거.
- 알림을 띄우고 사람이 수동 개입할 때까지 격리.

Redis는 데드레터를 기본 제공하지 않으므로, "전달 횟수 임계값 + 데드레터 스트림 + 원본 ACK"를 직접 구성해야 한다. 이걸 빼먹으면 독약 메시지 하나가 회수 워커의 처리량을 통째로 갉아먹는다.

---

## 흔한 오해

- **Stream에 넣으면 메시지가 안전하게 보관된다.** → MAXLEN/MINID 트리밍이나 메모리 압박에 의한 제거는 **ACK 여부를 보지 않는다.** 아직 PEL에 남은 미처리 메시지도 트리밍으로 잘려나갈 수 있다. 보존 기간은 처리 SLA보다 넉넉해야 한다.
- **소비자 그룹이 자동으로 재할당해 준다.** → 아니다. 죽은 소비자의 PEL을 옮기는 것은 `XCLAIM`/`XAUTOCLAIM`을 호출하는 *내 코드*다. Kafka의 리밸런스 같은 자동 재분배는 없다.
- **ACK는 처리 성공의 증거다.** → `XACK`는 그저 PEL에서 빼는 명령일 뿐, 처리 결과를 검증하지 않는다. 처리 전에 ACK하면 그 메시지는 성공 여부와 무관하게 사라진다.
- **consumer 이름이 많을수록 빨라진다.** → PEL은 consumer 이름 단위로 쌓인다. 매번 랜덤 이름으로 접속하면 죽은 이름마다 고아 PEL이 남아 `XINFO`가 지저분해지고 회수 대상이 폭증한다. consumer 이름은 안정적으로 재사용한다.
- **XLEN이 0이면 다 처리된 것이다.** → `XLEN`은 스트림에 남은 엔트리 수일 뿐 PEL과 무관하다. 미처리 현황은 `XPENDING`과 `XINFO GROUPS`의 `pending` / `lag`로 본다.

---

## 설계·운영 체크포인트

- **그룹 생성 시작점**: `XGROUP CREATE orders workers $`는 "지금 이후 새 메시지부터", `0`은 "맨 처음부터"다. 이미 쌓인 메시지를 처리할지 결정해 시작 ID를 고른다. 스트림이 없을 수 있으면 `MKSTREAM` 옵션을 붙인다.
- **멱등 소비**: at-least-once이므로 같은 메시지가 두 번 올 수 있다. 메시지 ID나 비즈니스 키를 처리 완료 집합(예: Redis Set, DB unique 제약)에 기록해 중복 처리를 무력화한다.
- **회수 워커 분리**: 정상 소비 경로(`>`)와 고아 회수 경로(`XAUTOCLAIM`)를 분리하면, 회수 로직 장애가 정상 처리량에 영향을 덜 준다.
- **PEL 모니터링**: `XINFO GROUPS orders`의 `pending`(미처리 수)과 `lag`(아직 전달 안 된 수)를 지표로 수집한다. pending이 단조 증가하면 소비자가 처리를 못 따라가거나 ACK를 빠뜨리고 있다는 신호다.
- **트리밍 안전 마진**: `XADD orders MAXLEN ~ 100000 * ...`처럼 근사 트리밍(`~`)으로 성능을 확보하되, 보존량은 최대 처리 지연 + 회수 지연을 견딜 만큼 잡는다.
- **단일 인스턴스 한계**: Redis Streams는 한 키가 한 노드에 산다. 클러스터에서 처리량을 늘리려면 스트림 키 자체를 샤딩해야 하고, Kafka 수준의 파티션 재분배·복제 보장이 필요하면 Stream이 맞는 도구인지 다시 본다.

---

## Spring Data Redis에서의 ACK 제어

Spring의 `StreamMessageListenerContainer`는 기본이 자동 ACK다. 신뢰성 있는 소비를 하려면 자동 ACK를 끄고 처리 성공 뒤 직접 `acknowledge`해야 한다.

```java
StreamMessageListenerContainerOptions<String, MapRecord<String, String, String>> options =
    StreamMessageListenerContainerOptions.builder()
        .pollTimeout(Duration.ofSeconds(1))
        .build();

StreamMessageListenerContainer<String, MapRecord<String, String, String>> container =
    StreamMessageListenerContainer.create(connectionFactory, options);

// autoAck = false 로 구독 → 처리 성공 후에만 명시적 ACK
container.receive(
    Consumer.from("workers", "consumer-1"),
    StreamOffset.create("orders", ReadOffset.lastConsumed()),
    message -> {
        try {
            handle(message.getValue());                       // 비즈니스 처리
            redisTemplate.opsForStream()
                .acknowledge("orders", "workers", message.getId());  // 성공 후 ACK
        } catch (Exception e) {
            // ACK하지 않음 → PEL에 남아 회수 대상이 된다
            log.warn("처리 실패, 재처리 대기: {}", message.getId(), e);
        }
    });

container.start();
```

`receiveAutoAck(...)`을 쓰면 받는 즉시 ACK되어 at-most-once가 된다. 핵심 이벤트라면 위처럼 `receive(...)` + 명시 ACK를 쓴다.

---

## 직접 해보기

로컬 Redis로 장애 시나리오를 재현해 본다.

```bash
# 1. 스트림에 메시지 적재 + 그룹 생성
redis-cli XADD orders '*' userId 1001 amount 50000
redis-cli XGROUP CREATE orders workers 0

# 2. consumer-1이 읽기만 하고 ACK 안 함 (장애 흉내)
redis-cli XREADGROUP GROUP workers consumer-1 COUNT 1 STREAMS orders '>'

# 3. PEL에 갇힌 것을 확인
redis-cli XPENDING orders workers

# 4. idle 0ms 기준으로 consumer-2가 회수
redis-cli XAUTOCLAIM orders workers consumer-2 0 0

# 5. 처리 완료 가정 후 ACK → PEL 비워짐 확인
redis-cli XACK orders workers <message-id>
redis-cli XPENDING orders workers
```

---

## 점검 질문

스스로 1분 안에 답할 수 있는지 확인한다.

1. `XREADGROUP`에서 `>`와 `0`의 차이는 무엇이고, 각각 언제 쓰는가?
2. 소비자가 처리 도중 죽으면 그 메시지는 어디에 남고, 누가 어떻게 다시 처리하는가?
3. Redis Streams가 exactly-once를 보장하지 못하는 이유와, 그럼에도 중복 없는 결과를 만드는 방법은?
4. 영원히 실패하는 메시지를 어떻게 감지하고 격리하는가?
5. PEL에 미처리 메시지가 남아 있어도 트리밍으로 유실될 수 있는 이유는?

---

## 함께 보면 좋은 문서

- [pub-sub.md](./pub-sub.md) — Pub/Sub와 Stream 기본 명령어, 전달 시멘틱 비교
- [pub-sub-patterns.md](./pub-sub-patterns.md) — Pub/Sub 실전 패턴과 메시지 큐 경계
- [../../kafka/message-delivery-semantics.md](../../kafka/message-delivery-semantics.md) — at-least-once / exactly-once를 Kafka 관점에서 비교
