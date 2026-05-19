# [초안] Redis Pub/Sub 패턴 심화 — 실전 활용과 메시지 큐와의 경계

> 이 문서는 Redis Pub/Sub의 동작 원리와 실전 패턴(캐시 무효화, 실시간 이벤트 전파, 세션 클러스터링)을 백엔드 면접 관점에서 정리한다. Pub/Sub과 Stream의 비교는 [pub-sub.md](./pub-sub.md)에 이미 있으므로 본 문서는 *Pub/Sub 단일 채널을 패턴 수준에서 어떻게 쓰는가*에 집중하고, Kafka·RabbitMQ와의 선택 기준까지 다룬다. 코드 예시는 Spring Data Redis 6.x 기준이다.

---

## 왜 이 주제인가

Pub/Sub은 Redis가 처음 추가한 메시지 전달 메커니즘이라 다들 한 번씩 써봤다. 그러나 면접에서 "캐시 무효화를 어떻게 했어요?" 또는 "다중 서버에서 로컬 캐시를 어떻게 동기화했어요?"를 받으면 대부분 "Redis Pub/Sub을 썼습니다" 한 줄로 끝낸다. 그러면 면접관은 곧바로 따라온다 — *"왜 Kafka가 아니고 Pub/Sub이었어요?"*, *"메시지가 유실되면 어떻게 되나요?"*, *"구독자가 1초 끊겼다 다시 붙으면요?"*

이 질문군에 1분 안에 답하려면 다음 세 가지가 머릿속에 동시에 있어야 한다.

- Pub/Sub의 전달 시멘틱(at-most-once, fire-and-forget)이 *왜* 그렇게 설계됐는지
- 실전에서 Pub/Sub이 *맞는* 패턴 3가지와 *틀린* 패턴
- Kafka·RabbitMQ를 골라야 할 신호와 그 신호를 어떻게 감지하는지

Pub/Sub은 "가벼운 메시지 큐"가 아니라 *영속성을 포기하고 레이턴시와 운영 단순성을 산* 도구다. 이 trade-off의 이름을 분명히 부를 수 있어야 한다.

---

## Pub/Sub 핵심 동작 원리

### 채널, 구독자, 브로커

Redis는 단일 스레드 이벤트 루프 위에서 채널별 구독자 리스트를 메모리로 들고 있다. `PUBLISH ch msg` 호출은 다음을 *동기적으로* 처리한다.

1. 채널 이름으로 구독자 소켓 리스트를 찾는다.
2. 각 구독자 소켓의 write buffer에 메시지를 push 한다.
3. 등록된 구독자 수를 반환한다.

여기서 두 가지 함의가 나온다.

- **구독자가 0명이면 메시지는 그 자리에서 사라진다.** 큐에 쌓이지 않는다.
- **publish는 구독자 처리를 기다리지 않는다.** 클라이언트가 socket buffer를 비우지 못하면 결국 `client-output-buffer-limit`에 걸려 강제 연결 끊김(disconnect) 후 메시지 손실.

이게 *at-most-once*의 실제 의미다. "최대 한 번"이라는 말은 우호적이고, 정확히는 "0번 또는 1번"이다.

### 패턴 구독(PSUBSCRIBE)

`PSUBSCRIBE order.*` 같은 glob 패턴은 채널 *이름*에 매칭한다. consumer 그룹 같은 분배 동작이 아니다. 패턴 구독자 N명이 있으면 같은 메시지를 N번 받는다.

### 명령어 표면

```bash
# 단일 채널 구독 (블로킹)
SUBSCRIBE cache.invalidate

# 패턴 구독
PSUBSCRIBE cache.invalidate.*

# 발행 — 반환값은 그 시점 활성 구독자 수
PUBLISH cache.invalidate "product:9901"

# 메타 정보
PUBSUB CHANNELS *                    # 활성 채널 목록
PUBSUB NUMSUB cache.invalidate       # 채널별 구독자 수
PUBSUB NUMPAT                        # 패턴 구독자 수
```

상세 명령어 표와 Stream과의 비교는 [pub-sub.md](./pub-sub.md)에 정리되어 있다.

---

## 실전 패턴 1 — 다중 서버 로컬 캐시 무효화

### 문제 상황

운영형 백엔드에서 어드민 사용자가 "메뉴 정책"이나 "프로모션 설정"을 변경한다. 인스턴스 N대가 각자 인메모리 캐시(Caffeine, Ehcache, `ConcurrentHashMap`)를 들고 있다면 변경 직후 *변경 인스턴스만* 신선한 값을 보고 나머지는 stale 값을 본다.

Redis 자체 캐시(`SET`)만 쓴다면 문제없다. 그러나 hot key 부하 분산을 위해 L1(local) + L2(Redis) 계층을 둔 순간 L1을 깨워야 한다. 이때 Pub/Sub이 첫 번째 자연스러운 선택지다.

### 패턴 흐름

```text
[Admin API]
    │ ① 정책 변경 (DB write)
    ▼
[DB] ──── ② AFTER_COMMIT 이벤트
              │
              ▼
       PUBLISH cache.invalidate "policy:menu:1001"
              │
       ┌──────┼──────────────────┐
       ▼      ▼                  ▼
   [App-1]  [App-2]  ...  [App-N]
   L1 evict L1 evict       L1 evict
```

### Spring Data Redis 구현 골격

```java
@Configuration
public class CacheInvalidationConfig {

    @Bean
    public RedisMessageListenerContainer container(
            RedisConnectionFactory cf,
            CacheInvalidationListener listener) {
        var container = new RedisMessageListenerContainer();
        container.setConnectionFactory(cf);
        container.addMessageListener(listener, new PatternTopic("cache.invalidate.*"));
        return container;
    }
}

@Component
@RequiredArgsConstructor
public class CacheInvalidationListener implements MessageListener {

    private final CacheManager cacheManager;

    @Override
    public void onMessage(Message message, byte[] pattern) {
        String channel = new String(message.getChannel());      // cache.invalidate.policy
        String key = new String(message.getBody());             // menu:1001

        String cacheName = channel.substring("cache.invalidate.".length());
        Cache cache = cacheManager.getCache(cacheName);
        if (cache != null) cache.evict(key);
    }
}

@Service
@RequiredArgsConstructor
public class PolicyWriteService {

    private final StringRedisTemplate redis;
    private final PolicyRepository repository;

    @Transactional
    public void updateMenuPolicy(Long id, MenuPolicyUpdate update) {
        repository.update(id, update);
        // 커밋 이후 발행되도록 ApplicationEventPublisher + @TransactionalEventListener 분리 권장
    }
}

@Component
@RequiredArgsConstructor
public class PolicyEventPublisher {

    private final StringRedisTemplate redis;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onPolicyChanged(PolicyChangedEvent event) {
        redis.convertAndSend("cache.invalidate.policy", "menu:" + event.id());
    }
}
```

### 왜 AFTER\_COMMIT인가

커밋 이전에 발행하면 *다른 인스턴스가 stale DB를 한 번 더 읽고 다시 캐싱*하는 사이드 이펙트가 생긴다. 발행은 commit 이후, 수신은 그 다음. 트랜잭션 경계와 이벤트 경계의 분리는 [redis-advanced-patterns.md](./redis-advanced-patterns.md)와 Outbox 패턴이 다루는 핵심 주제다.

### 한계와 보정

Pub/Sub은 *해당 인스턴스가 끊겨 있는 동안의 메시지를 받지 못한다*. 운영 중인 인스턴스가 GC stall, 네트워크 단절, 배포 재기동 사이에 발행된 invalidate 메시지를 놓치면 그 인스턴스만 영구히 stale 값을 들고 있게 된다.

현실 보정 3가지.

- **짧은 TTL을 L1에 강제로 건다.** 60초 \~ 5분 정도면 "최악의 stale 윈도우"가 한정된다.
- **버전 키를 같이 본다.** 정책 ID마다 Redis에 `policy:menu:1001:version` 카운터를 두고 L1 hit 시점에 비교한다. version 불일치면 L1 invalidate.
- **재기동 시 cold start.** 인스턴스 부팅 후 첫 요청은 L1 miss → L2 또는 DB에서 새로 적재. Pub/Sub은 "정상 운영 중 빠른 전파" 용도로만 보고, 정합성은 TTL과 version key가 마지막 안전망이다.

### 실제 경험 매핑

SB 개발팀 시절 Ehcache(`@Cacheable`) + 인메모리 Map 캐시 이중 구조를 두고 다중 서버 정합성을 RabbitMQ Fanout으로 풀었다. RabbitMQ를 골랐던 이유는 *발행자 인스턴스가 죽었다 살아나도 다른 인스턴스의 invalidate가 큐에 남아있게 하고 싶었기* 때문이다. 즉, *영속성을 사야 했던* 케이스. 만약 정책 변경 빈도가 낮고 TTL이 짧으면 Redis Pub/Sub만으로 충분했을 것이다.

---

## 실전 패턴 2 — 실시간 이벤트 전파 (WebSocket fanout)

### 문제 상황

채팅, 알림, 라이브 가격 갱신처럼 *접속 중인 사용자에게만* 보내면 되는 이벤트가 있다. WebSocket 세션은 인스턴스마다 고립되어 있어서 사용자 A가 App-1, 친구 B가 App-2에 붙어 있다면 A가 보낸 메시지를 B에게 전달할 다리가 필요하다.

### 패턴 흐름

```text
User A ── ws ──> [App-1] ── PUBLISH chat.room.42 ──> Redis ──> PSUBSCRIBE chat.room.* ──> [App-2] ── ws ──> User B
```

각 인스턴스는 자기에게 붙은 WebSocket 세션 목록을 들고 있고, Redis Pub/Sub 메시지를 받을 때 해당 룸 ID에 속한 세션에만 forward 한다.

### Spring 코드 골격

```java
@Component
@RequiredArgsConstructor
public class ChatRelay implements MessageListener {

    private final WebSocketSessionRegistry sessions;
    private final ObjectMapper mapper;

    @Override
    public void onMessage(Message message, byte[] pattern) {
        try {
            ChatPayload payload = mapper.readValue(message.getBody(), ChatPayload.class);
            String channel = new String(message.getChannel());        // chat.room.42
            String roomId = channel.substring("chat.room.".length());

            sessions.findByRoom(roomId).forEach(s -> sendSafely(s, payload));
        } catch (IOException e) {
            log.warn("chat relay deserialize fail", e);
        }
    }
}
```

### 왜 Kafka가 아닌가

Kafka는 *모든 partition replica에 디스크 fsync 후 commit* 한다. 1ms도 아낄 수 있다면 굳이 Kafka의 P99 latency를 받을 이유가 없다. 채팅 메시지 한 건이 유실되면 사용자가 다시 입력하거나 화면 새로고침으로 복구되는 게 일반적이다. 즉 *유실 비용 < 레이턴시 비용*이면 Pub/Sub가 맞다.

반대로 *주문 이벤트가 외부 정산 시스템으로 가야 한다* 같은 도메인은 유실 비용이 결제 금액이라 Kafka 또는 RabbitMQ ack가 필수다.

### 함정 — 슬로우 컨슈머

WebSocket 송신이 느려진 인스턴스는 Redis로부터 받은 메시지를 다 처리하지 못해 client buffer가 부풀어 오른다. Redis는 `client-output-buffer-limit pubsub 32mb 8mb 60` 같은 정책으로 임계치를 넘으면 *해당 구독자 연결을 끊는다*. 다시 붙는 사이 메시지는 영구 유실. 단일 인스턴스가 다른 인스턴스의 메시지까지 끊어버리는 일은 없지만, 해당 인스턴스의 사용자만 메시지를 잃는다.

대응은 *비동기 dispatch* — 리스너 스레드가 메시지를 받으면 큐에 던지고 즉시 리턴, WebSocket 송신은 별도 워커 풀에서. 구독자 처리 속도가 publish 속도를 따라가지 못하는 패턴이 보이면 *그 시점이 Stream 또는 Kafka로 이전할 시그널*이다.

---

## 실전 패턴 3 — 세션·토큰 무효화 브로드캐스트

### 문제 상황

사용자가 로그아웃하거나 비밀번호를 변경하면 *모든 활성 인스턴스*에서 해당 사용자의 세션을 즉시 끊어야 한다. JWT를 쓰면 더 까다롭다 — 토큰 자체는 stateless이므로 강제 폐기 목록(blacklist)을 인스턴스가 알아야 한다.

### 패턴 흐름

```text
Logout API ──> Redis SADD revoked:tokens <jti> EX 3600
            └─> PUBLISH session.revoke <jti>
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
   [App-1] L1            [App-2] L1         [App-N] L1
   blacklist update      blacklist update    blacklist update
```

### 핵심 설계 포인트

- **Pub/Sub은 *빠른 전파*용**이고, ***권위 있는 진실*은 Redis의 Set/Hash**다. 모든 인스턴스는 첫 요청 시 Redis blacklist를 read-through 하고, Pub/Sub은 단지 L1 invalidate 트리거.
- TTL을 토큰 만료 시간과 동일하게 둬서 자동 청소.
- 인스턴스가 Pub/Sub 메시지를 놓쳐도 *최악의 stale 윈도우는 L1 TTL*이다. 토큰 보안에서 1분 stale를 허용할 수 있는지는 비즈니스 요구에 따른다. 허용 불가면 *L1 캐시를 두지 않고* 매 요청 Redis 조회로 가야 한다 (네트워크 비용 ↑, 정합성 ↑).

### 면접에서 자주 따라오는 질문

*"Pub/Sub 메시지를 못 받은 인스턴스가 있으면요?"* — 답: "Pub/Sub은 보조 전파입니다. 권위 출처는 Redis Set이고 L1 TTL을 짧게 잡아 최악 stale window를 닫습니다. stale 허용 불가 도메인은 L1 자체를 안 둡니다."

---

## Kafka · RabbitMQ vs Redis Pub/Sub — 선택 기준

| 항목 | Redis Pub/Sub | RabbitMQ | Kafka |
|---|---|---|---|
| 전달 시멘틱 | at-most-once | at-least-once (ack) | at-least-once (consumer offset) |
| 메시지 영속성 | 없음 | queue durable + persistent message | 디스크 로그 (보존 기간 설정) |
| 오프라인 구독자 | 유실 | queue에 적재 | replay 가능 |
| 처리량 | 수만 TPS | 수만 \~ 수십만 TPS | 수십만 \~ 수백만 TPS |
| 레이턴시 | 매우 낮음 (sub-ms) | 낮음 (수 ms) | 수 ms (replica fsync) |
| 운영 복잡도 | 매우 낮음 (Redis 인프라 재사용) | 중간 (broker, exchange, queue 관리) | 높음 (broker, ZK/KRaft, topic, partition) |
| 재처리 / replay | 불가 | DLQ + manual requeue | offset 재설정 |
| 순서 보장 | 채널 내 발행 순서 (단일 인스턴스) | queue 내 순서 | partition 내 순서 |

### 결정 트리

1. **유실 허용?** No → RabbitMQ / Kafka. Yes → 2.
2. **재처리·replay 필요?** Yes → Kafka. No → 3.
3. **이미 Redis 인프라 운영 중이고 새 broker 추가가 부담?** Yes → Pub/Sub. No → RabbitMQ로도 OK.
4. **레이턴시가 수 ms도 비쌈 (실시간 게임, 호가창, 채팅)?** Yes → Pub/Sub.
5. **구독자 ack / 재시도 / DLQ 운영이 필요?** Yes → RabbitMQ.

거꾸로 *Pub/Sub 절대 금지* 시그널.

- 결제, 정산, 회계 이벤트
- 외부 시스템으로 나가는 통합 메시지
- 발행자와 소비자가 서로 다른 팀이 운영해서 *유실이 SLA 위반*인 경우
- 메시지가 큐에 쌓이는 backpressure 동작이 필요한 경우 (Pub/Sub은 backpressure 없이 그냥 drop)

---

## 커머스 환경에서의 Pub/Sub 판단 기준

운영형 자사 백엔드(주문, 매장, 메뉴, 쿠폰, 멤버십)에서 메시징 후보가 등장하는 지점은 대략 다음과 같다.

| 시나리오 | 권장 도구 | 이유 |
|---|---|---|
| 어드민이 메뉴/프로모션 정책 변경 → 다중 서버 L1 캐시 무효화 | **Pub/Sub** | 유실해도 L1 TTL이 안전망, 새 broker 도입 부담 |
| 매장 영업 상태 변경 (open/close) 즉시 전파 | **Pub/Sub + Redis Hash** | Hash가 권위 출처, Pub/Sub은 L1 즉시 갱신 트리거 |
| 주문 생성 → 결제 모듈로 비동기 알림 | **Kafka (Outbox)** | 유실 = 결제 누락. AFTER\_COMMIT + Outbox + 재전송 |
| 결제 승인 → 매장 POS로 주문 전달 | **RabbitMQ ack** 또는 **Kafka** | 매장 POS가 잠시 끊겨도 큐에 적재 + 재시도 |
| 쿠폰 발급 이벤트 (선착순) | **Redis Lua + 분산 락** | 메시징이 아니라 원자적 차감. 별도 채널 |
| 사용자 로그아웃 / 토큰 폐기 브로드캐스트 | **Pub/Sub + Redis Set** | Set이 권위 출처, Pub/Sub은 빠른 전파 |
| 실시간 매장 주문 현황 대시보드 (운영자 화면) | **Pub/Sub** | 유실 허용, WebSocket fanout |
| 주문 상태 변경 (접수 → 제조 → 완료) 사용자 알림 | **Kafka + 푸시 worker** | 유실 = CS, 재시도 필요 |

### 한 줄 가이드

*Pub/Sub은 "잃어도 되는 빠른 신호"*. 잃으면 *돈이 새는* 신호는 모두 Outbox + Kafka/RabbitMQ로.

---

## 자주 빠지는 함정

### 1. Pub/Sub과 Redis Cluster

Redis Cluster의 일반 Pub/Sub은 *전 노드 broadcast*다. 채널이 어느 슬롯에 속한다는 개념 자체가 없다 (Redis 7 미만). 노드 수가 많아지면 노드 간 트래픽이 증폭된다. Redis 7+의 *Sharded Pub/Sub*(`SSUBSCRIBE`)이 슬롯 기반으로 노드 안에만 전달하지만 클라이언트 라이브러리 지원이 균일하지 않다. 운영 중 Cluster 전환을 고려한다면 Pub/Sub 사용 패턴을 미리 정리해 두자.

### 2. 발행 시점의 트랜잭션 경계

DB 커밋 이전에 발행하면 다른 인스턴스가 *commit 직전 상태*를 보고 캐시를 만든다. `@TransactionalEventListener(phase = AFTER_COMMIT)`로 분리하는 게 표준. 분리 안 하면 정합성 버그가 production에서만 산발적으로 재현된다.

### 3. 메시지 페이로드를 크게 만들지 않기

Pub/Sub은 인메모리 fanout이라 페이로드 크기가 곧 인스턴스 수 만큼 곱해진다. *키만 보내고 본문은 Redis 또는 DB에서 다시 읽는다*가 기본 패턴. 본문을 직접 실으면 hot key fanout 시 네트워크 폭주가 된다.

### 4. 메시지를 동기 처리하지 않기

`MessageListener#onMessage`는 Redis 리스너 스레드 풀(기본 1개)에서 호출된다. 여기서 무거운 I/O(DB 조회, 외부 API)를 하면 다음 메시지 처리가 막힌다. 받자마자 자체 워커 풀로 dispatch.

### 5. 패턴 구독 남발

`PSUBSCRIBE *` 같은 와일드카드는 모든 발행에 매칭된다. 채널이 늘어날수록 매 발행에서 패턴 매칭 비용 + 라우팅 오버헤드가 커진다. 패턴은 *명확한 prefix 안에서만* 쓴다.

---

## 면접 답변 프레임 — 1분 답변 템플릿

### 질문 1 — "다중 서버 캐시 무효화를 어떻게 했어요?"

> "두 단계로 갔습니다. 권위 있는 진실은 Redis L2에 두고, hot key 부하 분산을 위해 인스턴스 로컬에 L1을 짧은 TTL로 둡니다. 정책 변경 시 DB 커밋 이후 `@TransactionalEventListener(AFTER_COMMIT)`에서 Redis `PUBLISH cache.invalidate.<cache> <key>`를 발행하고, 각 인스턴스가 패턴 구독으로 받아 L1에서 해당 키만 evict 합니다. Pub/Sub은 *유실 가능*이라 L1 TTL을 안전망으로 두고, 더 강한 정합성이 필요했던 SB 개발팀 시절에는 같은 패턴을 RabbitMQ Fanout으로 옮긴 경험도 있습니다."

### 질문 2 — "왜 Kafka가 아니고 Redis Pub/Sub이었어요?"

> "두 가지 trade-off였습니다. 첫째, 캐시 무효화 메시지는 유실되면 L1 TTL이 닫아주는 자기 회복 구조라 영속성이 비용 대비 의미가 약했습니다. 둘째, 이미 Redis가 인프라에 있었고 broker를 추가하면 운영 surface가 늘어납니다. 만약 같은 메시지가 *결제 정산 알림*이었다면 유실이 곧 돈 손실이라 Outbox + Kafka로 갔을 겁니다."

### 질문 3 — "Pub/Sub 메시지를 못 받은 인스턴스가 있으면요?"

> "Pub/Sub은 보조 전파, 권위 출처는 Redis Set 또는 Hash로 따로 둡니다. 인스턴스가 메시지를 놓쳐도 다음 요청에서 L1 TTL이 만료되면 L2 또는 DB에서 새 값을 읽어옵니다. 즉, 최악의 stale window는 L1 TTL입니다. 토큰 폐기처럼 stale 허용 불가 도메인은 L1을 안 두거나 매 요청 Redis 조회로 갑니다."

### 질문 4 — "Pub/Sub과 Stream을 어떻게 구분해서 써요?"

> "두 가지가 답이 다른 도구입니다. Pub/Sub은 *fire-and-forget*, Stream은 *log + consumer group + ACK*입니다. 채팅, 실시간 알림, 캐시 무효화 같은 *유실 허용 + 낮은 레이턴시* 요구면 Pub/Sub. 신뢰성 있는 작업 큐가 필요하면 Stream인데, Kafka가 과해 보일 때만 Stream을 쓰고 보존 기간이 길거나 replay가 필요하면 Kafka로 갑니다."

---

## 로컬 실습 환경

### docker-compose

```yaml
services:
  redis:
    image: redis:7.4
    ports:
      - "6379:6379"
    command: ["redis-server", "--appendonly", "no"]
```

### 두 터미널로 직접 확인

```bash
# 터미널 1 — 구독
redis-cli SUBSCRIBE cache.invalidate

# 터미널 2 — 발행
redis-cli PUBLISH cache.invalidate "product:9901"
# 반환값: (integer) 1   <- 구독자 1명에게 전달됨

# 터미널 2 — 구독자 없는 채널로 발행
redis-cli PUBLISH cache.no-one-listens "x"
# 반환값: (integer) 0   <- 메시지는 즉시 사라짐
```

### 슬로우 컨슈머 재현

```bash
# 터미널 1 — Python으로 의도적으로 느린 구독자
python -c "
import redis, time
r = redis.Redis()
p = r.pubsub()
p.subscribe('flood')
for m in p.listen():
    time.sleep(0.5)
    print(m)
"

# 터미널 2 — 빠른 발행
for i in $(seq 1 10000); do redis-cli PUBLISH flood "msg-$i" > /dev/null; done
```

`client-output-buffer-limit`를 작게 설정해두면 구독자 연결이 강제 종료되는 동작을 직접 관측할 수 있다. *이게 운영에서 Pub/Sub이 유실되는 가장 흔한 경로*다.

---

## 체크리스트

- [ ] Pub/Sub은 *at-most-once*고 구독자가 없으면 그 자리에서 drop 된다는 사실을 명확히 말할 수 있다
- [ ] 발행은 `@TransactionalEventListener(AFTER_COMMIT)` 안에서 한다
- [ ] 메시지 페이로드에 본문 전체를 싣지 않고 *키만* 보낸다
- [ ] 리스너 안에서 직접 무거운 I/O를 하지 않고 별도 워커로 dispatch 한다
- [ ] 권위 있는 진실은 Redis Set/Hash 또는 DB이고 Pub/Sub은 *빠른 전파* 역할이다
- [ ] L1 TTL을 최악의 stale window로 잡았고 그 값이 비즈니스 허용치 안에 있다
- [ ] Redis Cluster 환경에서는 Sharded Pub/Sub 또는 별도 redis 인스턴스 사용을 검토했다
- [ ] 결제, 정산, 외부 시스템 통합 같은 *유실 = 손실* 도메인은 Pub/Sub 후보에서 제외한다
- [ ] 슬로우 컨슈머 시그널(`client-output-buffer-limit` 끊김, lag 증가)을 모니터링한다
- [ ] 패턴 구독은 명확한 prefix 안에서만 쓴다

---

## 관련 문서

- [Redis Pub/Sub & Stream 기본](./pub-sub.md) — 명령어 표면과 Stream 비교
- [Cache-Aside](./cache-aside.md) — 캐시 무효화 흐름 전체
- [분산 락](./distributed-lock.md) — Redisson Pub/Sub 기반 락 대기 메커니즘
- [Redis 고급 패턴 허브](./redis-advanced-patterns.md) — 여러 패턴을 묶어 읽는 지도
