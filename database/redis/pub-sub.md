# Redis Pub/Sub & Stream

Redis는 두 가지 메시지 전달 메커니즘을 제공한다. **Pub/Sub**은 실시간 브로드캐스트에, **Stream**은 신뢰성 있는 메시지 큐에 적합하다. 용도가 다르므로 혼동하지 말아야 한다.

---

## Pub/Sub

발행자(Publisher)가 채널에 메시지를 보내면, 해당 채널을 구독 중인 모든 구독자(Subscriber)에게 즉시 전달하는 **Fire-and-Forget** 방식이다.

### 핵심 명령어

```bash
# 구독 (SUBSCRIBE 이후 블로킹 상태)
SUBSCRIBE channel:notifications
SUBSCRIBE channel:chat:room1 channel:chat:room2  # 다중 채널

# 패턴 구독
PSUBSCRIBE channel:chat:*        # chat: 으로 시작하는 모든 채널
PSUBSCRIBE notification:user:*

# 발행 (반환값: 해당 채널 현재 구독자 수)
PUBLISH channel:notifications "새 주문이 들어왔습니다"
PUBLISH channel:chat:room1 "안녕하세요"

# 구독 해제
UNSUBSCRIBE channel:notifications
PUNSUBSCRIBE channel:chat:*

# 채널 정보 조회
PUBSUB CHANNELS *                # 활성 채널 목록
PUBSUB NUMSUB channel:notifications  # 채널별 구독자 수
```

### 동작 흐름

```
Publisher                Redis              Subscriber A    Subscriber B
    │                      │                     │               │
    │  PUBLISH ch "msg"    │                     │               │
    │─────────────────────>│                     │               │
    │                      │   push "msg"        │               │
    │                      │────────────────────>│               │
    │                      │   push "msg"        │               │
    │                      │─────────────────────────────────────>│
    │                      │                     │               │
```

### 한계 (중요)

- **메시지 영속성 없음**: 구독자가 오프라인이면 메시지 유실
- **확인(ACK) 없음**: 전달 성공 여부를 알 수 없음
- **재처리 불가**: 실패한 메시지를 다시 받을 방법 없음
- **구독자 0명이어도 발행 가능**: 아무도 받지 않아도 에러 없음

> Pub/Sub은 "최대한 전달하지만 보장은 안 한다(at-most-once)"는 구조다. 중요한 이벤트라면 Stream을 써야 한다.

### 적합한 사용 사례

- **실시간 채팅**: 메시지 손실을 어느 정도 허용하는 경우
- **캐시 무효화 브로드캐스트**: 여러 서버의 로컬 캐시를 동시에 삭제
- **실시간 알림**: 접속 중인 사용자에게만 전달하면 충분한 알림
- **이벤트 버스**: 서비스 내부 간단한 이벤트 전파

```bash
# 캐시 무효화 예시
# 상품 정보 변경 시 모든 서버의 캐시 삭제 신호 전송
PUBLISH cache:invalidate "product:9901"

# 각 서버는 해당 채널 구독 중
# SUBSCRIBE cache:invalidate
# → 수신 시 로컬 캐시에서 해당 키 삭제
```

---

## Redis Stream

Redis 5.0에 추가된 **로그 구조 자료구조**. Kafka처럼 메시지를 영속하고, 소비자 그룹(Consumer Group)으로 분산 처리하며, ACK 기반으로 재처리를 보장한다.

### 핵심 명령어

```bash
# 메시지 추가 (ID는 자동 생성: milliseconds-sequence)
XADD orders * userId 1001 amount 50000 itemId 9901
# 반환: "1711500000000-0" 형태의 ID

# 길이 제한하며 추가 (오래된 것 자동 삭제)
XADD orders MAXLEN ~ 10000 * userId 1001 amount 50000

# 메시지 읽기 (0 = 처음부터)
XREAD COUNT 10 STREAMS orders 0

# 특정 ID 이후부터 읽기
XREAD COUNT 10 STREAMS orders 1711500000000-0

# 블로킹 읽기 (새 메시지 올 때까지 대기)
XREAD COUNT 10 BLOCK 5000 STREAMS orders $

# 스트림 길이
XLEN orders

# 범위 조회
XRANGE orders - +              # 전체
XRANGE orders 1711500000000-0 + # 특정 ID 이후
```

### 소비자 그룹 (Consumer Group)

여러 소비자가 메시지를 **분산 처리**하는 구조다. 같은 그룹 내에서 하나의 메시지는 하나의 소비자만 받는다.

```bash
# 그룹 생성 ($ = 이후 새 메시지만, 0 = 처음부터)
XGROUP CREATE orders workers $ MKSTREAM

# 소비자 그룹으로 읽기 (> = 아직 전달 안 된 메시지)
XREADGROUP GROUP workers consumer1 COUNT 10 STREAMS orders >

# 처리 완료 ACK
XACK orders workers 1711500000000-0

# 처리 실패/미완료 메시지 확인 (PEL: Pending Entry List)
XPENDING orders workers - + 10

# 오래된 미처리 메시지 강제 재할당
XCLAIM orders workers consumer2 3600000 1711500000000-0
```

### 동작 흐름

```
Producer
    │
    │ XADD orders * ...
    ↓
[Stream: orders]
 ─────────────────────────
 msg-1 | msg-2 | msg-3 | ...
 ─────────────────────────
    │               │
    │ XREADGROUP    │ XREADGROUP
    ↓               ↓
Consumer 1      Consumer 2
 (msg-1)         (msg-2)
    │               │
    │ XACK          │ XACK
    ↓               ↓
  완료 ✅          완료 ✅

Consumer 3 (장애)
 (msg-3) → ACK 없음
    ↓
XPENDING으로 감지
    ↓
XCLAIM으로 Consumer 1에 재할당
    ↓
재처리 ♻️
```

### Spring Boot 연동 예시

```java
// 메시지 발행
StreamOperations<String, String, String> ops =
    redisTemplate.opsForStream();

Map<String, String> message = Map.of(
    "userId", "1001",
    "amount", "50000"
);
ops.add("orders", message);

// 소비자 그룹 설정 (한 번만)
ops.createGroup("orders", ReadOffset.latest(), "workers");

// 메시지 소비
List<MapRecord<String, String, String>> messages =
    ops.read(Consumer.from("workers", "consumer1"),
             StreamReadOptions.empty().count(10),
             StreamOffset.create("orders", ReadOffset.lastConsumed()));

for (var record : messages) {
    try {
        processOrder(record.getValue());
        ops.acknowledge("orders", "workers", record.getId());  // ACK
    } catch (Exception e) {
        // ACK 안 함 → PEL에 남아서 나중에 재처리
        log.error("처리 실패: {}", record.getId(), e);
    }
}
```

---

## Pub/Sub vs Stream 선택 기준

| 항목 | Pub/Sub | Stream |
|------|---------|--------|
| 메시지 영속성 | ❌ 없음 | ✅ 있음 |
| 전달 보장 | ❌ at-most-once | ✅ at-least-once |
| ACK / 재처리 | ❌ 없음 | ✅ 있음 |
| 소비자 그룹 | ❌ 없음 | ✅ 있음 |
| 오프라인 구독자 | ❌ 메시지 유실 | ✅ 나중에 수신 가능 |
| 사용 복잡도 | 낮음 | 높음 |
| 적합 용도 | 실시간 브로드캐스트 | 신뢰성 이벤트 큐 |

**판단 기준:**
- 메시지 유실이 허용된다 → **Pub/Sub**
- 모든 메시지가 정확히 처리되어야 한다 → **Stream**
- Kafka가 과하다 싶은 경량 이벤트 큐 → **Stream**

---

## Stream vs Kafka 선택 기준

| 항목 | Redis Stream | Kafka |
|------|-------------|-------|
| 설치/운영 복잡도 | 낮음 | 높음 |
| 처리량 | 수만 TPS | 수십만~수백만 TPS |
| 보존 기간 | 메모리/설정에 따라 | 무제한 (디스크) |
| 메시지 재생(replay) | 제한적 | 강력 |
| 운영 도구 | 기본적 | Kafka UI, Schema Registry 등 |

같은 Redis 인프라를 이미 쓰고 있고, 처리량이 크지 않다면 Stream이 경제적이다.

---

## 관련 문서

- [Redis 기본](./basic.md) — Stream, Pub/Sub 자료구조 개요
- [분산 락](./distributed-lock.md) — Redisson Pub/Sub 기반 락 대기 메커니즘
