# [초안] Redis 고급 패턴 허브 — 여러 문서를 꿰어 읽는 법

> 이 문서는 redis 폴더 안의 개별 심화 문서들을 **하나의 맥락으로 묶어주는 허브**다. 개념 설명이나 명령어 레퍼런스를 반복하지 않고, '어느 패턴을 언제 쓰는가', '어떤 장애 시나리오에서 어느 문서를 꺼내 드는가', '여러 기법을 어떻게 조합하는가'에 집중한다. 상세 구현과 예제는 각 링크 문서에서 이어서 읽는다.

---

## 이 허브가 존재하는 이유

Redis를 실무에서 쓰다 보면, 하나의 장애가 **여러 패턴에 걸쳐** 발생한다.

- 인기 상품 페이지의 TTL이 만료되는 순간 → 캐시 스탬피드 + hot key + DB 커넥션 폭주가 동시에 일어난다.
- 분산 락으로 보호한다고 믿었던 재고 차감 → GC stall + 락 만료 + oversell이 연쇄로 발생한다.
- Redis 단독 구성을 Cluster로 옮긴 뒤 → 기존 Lua/MULTI가 `CROSSSLOT` 에러로 한 번에 깨진다.

이런 문제들은 한 문서로는 설명되지 않는다. `cache-aside`, `distributed-lock`, `lua-script`, `operations`가 **함께** 읽혀야 판단이 선다. 이 허브는 그 연결 지점을 정리한다.

---

## 학습 경로 — 어떤 순서로 읽을 것인가

```
[입문]           basic.md          ← 아키텍처, 자료구조, 싱글 스레드 전제
    │
    ├─ [캐시]   cache-aside.md    ← 읽기/쓰기 경로, 스탬피드, 정합성
    │
    ├─ [동시성] distributed-lock.md  ← SET NX, Redisson, Redlock 한계
    │           lua-script.md         ← 복합 연산 원자화 사례
    │           rate-limiting.md      ← 고정/슬라이딩 윈도우, 토큰 버킷
    │
    ├─ [메시징] pub-sub.md        ← Pub/Sub vs Stream 선택
    │
    ├─ [상태]   session.md        ← Spring Session, JWT 비교
    │           leaderboard.md    ← Sorted Set 랭킹
    │
    └─ [운영]   operations.md     ← 성능, 메모리, 모니터링, 장애 대응
                backup.md         ← RDB/AOF, Sentinel/Cluster
```

허브 문서인 여기서는 **위 개별 문서가 서로 만나는 지점**만 다룬다.

---

## 1. 캐시 + 분산 락 + Lua — 임계 경로 이중 방어

재고 차감, 쿠폰 발급, 잭팟 지급처럼 **중복 실행이 곧 돈 손실**인 경로는 하나의 기법으로는 부족하다. 세 가지 문서의 패턴을 합쳐야 한다.

### 조합 설계

```
요청 → [1] 로컬 캐시(L1)          ← cache-aside의 L1/L2 계층화
       [2] Redis 예약(DECR/Lua)   ← lua-script의 원자적 차감
       [3] 분산 락 (보조)          ← distributed-lock의 best-effort 보호
       [4] DB 트랜잭션 + 유니크제약 ← 최종 정합성 보증
       [5] 실패 시 보상 INCR       ← Redis 예약 되돌림
```

**핵심 원칙:**
- Redis 차감은 **예약(reservation)**, DB commit이 **최종 결정**이다.
- Redis 락은 Martin Kleppmann이 지적한 GC stall / clock drift 조건에서 mutual exclusion을 **절대 보장하지 않는다**. → [분산 락](./distributed-lock.md#redlock-클러스터-환경의-분산-락)
- DB에 유니크 제약 / CHECK 제약을 반드시 이중으로 건다. Redis가 "거짓말"해도 이중 판매가 막힌다.

관련 상세:
- [Redis Lua 스크립트](./lua-script.md) — Hash + Lua로 잭팟 누적/당첨을 atomic하게 처리한 실제 사례
- [분산 락](./distributed-lock.md) — SET NX EX, Redisson Watchdog, Redlock의 한계
- [Cache-Aside](./cache-aside.md#장애-2--hot-key-집중-hot-spot) — L1(Caffeine) + L2(Redis) 계층화

---

## 2. 캐시 스탬피드 — 세 가지 해법의 분기

캐시 스탬피드는 `cache-aside.md`에 상세 설명이 있다. 여기서는 **어느 상황에 어느 해법을 고르는지**만 정리한다.

| 상황 | 해법 | 참조 |
|------|------|------|
| 인기 키 1~2개, 트래픽 예측 가능 | 사전 워밍 (스케줄러) | [Cache-Aside § 사전 워밍](./cache-aside.md#해결책-3--사전-워밍-pre-warming) |
| 인기 키 N개, 순간 폭주 | 분산 락 기반 단일 재계산 | [Cache-Aside § 분산 락](./cache-aside.md#해결책-1--분산-락-mutex-lock), [분산 락](./distributed-lock.md) |
| 레이턴시 스파이크 허용 불가 | Probabilistic Early Expiration (XFetch) | [Cache-Aside § PER](./cache-aside.md#해결책-2--확률적-조기-갱신-probabilistic-early-expiration) |
| 동시 만료 자체를 분산 | TTL 지터 (모든 경우 기본 적용) | [Cache-Aside § TTL 분산](./cache-aside.md#ttl-분산-동시-만료-방지) |
| Hot key 자체 부하 | L1 로컬 캐시로 Redis 조회 흡수 | [Cache-Aside § Hot Key](./cache-aside.md#장애-2--hot-key-집중-hot-spot) |

**판단 기준:** 지터는 '무조건 적용'. 나머지는 인기 키 수와 비즈니스 레이턴시 허용치로 고른다. 실무에서는 보통 **지터 + L1 + 분산 락** 3종 세트로 시작하고, 부족하면 PER를 얹는다.

---

## 3. Pub/Sub vs Stream vs Kafka — 메시징 경로 선택

[`pub-sub.md`](./pub-sub.md)에 상세 비교표가 있다. 허브 관점에서는 **조직의 기존 인프라**까지 포함해 본다.

```
메시지 유실 허용 O  →  Redis Pub/Sub
                      · 캐시 무효화 브로드캐스트
                      · 실시간 채팅/알림 (접속자만)
                      · Redisson 락 해제 신호

메시지 유실 허용 X, Kafka 없음  →  Redis Stream
                                    · 짧은 생명주기 작업 큐
                                    · 이미지 처리, 메일 발송, 썸네일 생성

메시지 유실 허용 X, Kafka 있음  →  Kafka (본류) + Redis Stream (보조)
                                    · 주문/결제 이벤트 → Kafka
                                    · 백그라운드 dedupe/빠른 큐 → Streams
```

같은 Redis 인프라에 이미 있는 Streams를 굳이 Kafka로 옮기지는 않는다. 반대로 Kafka가 이미 있는데 Streams로 중요한 이벤트를 옮기면 **운영 도구(Schema Registry, Kafka UI, exactly-once)가 없어 후회**한다.

---

## 4. Redis Cluster의 제약 — CROSSSLOT

단일 인스턴스에서 Cluster로 넘어갈 때 **가장 자주 터지는 함정**이지만 개별 문서에서는 깊이 다루지 않는다. 여기서 정리한다.

```
# 단일 인스턴스에서는 잘 돌던 코드
MSET user:1:name Alice user:2:name Bob
→ Cluster: (error) CROSSSLOT Keys in request don't hash to the same slot
```

Redis Cluster는 키를 CRC16 기반 16,384개 hash slot으로 분배한다. **Lua 스크립트, MULTI/EXEC, MSET/MGET, 트랜잭션**은 모두 같은 slot의 키에만 동작한다.

### 해시 태그로 같은 slot에 묶기

```
MSET {user:1}:name Alice {user:1}:email alice@x.com
       ^^^^^^^                ^^^^^^^
   해시 태그 → user:1 기준으로 같은 slot에 저장
```

### 설계 원칙

- **같이 atomic하게 다룰 키들은 같은 해시 태그**를 공유한다 (user-profile, order-items 등).
- **관련 없는 키에 같은 태그를 남발하면 hot slot**이 생긴다 (특정 샤드 CPU 100%).
- 해시 태그는 **데이터 모델 설계 단계**에서 정해야 한다. 운영 중에 바꾸면 키 이동 = 캐시 폭풍이다.

영향 받는 기능과 대체안:

| 기능 | Cluster에서 | 대체 |
|------|------------|------|
| Lua 다중 키 조작 | 같은 slot만 가능 | 해시 태그 설계 또는 애플리케이션 레벨 보상 트랜잭션 |
| MULTI/EXEC | 같은 slot만 가능 | Lua 스크립트로 통합 |
| MSET/MGET | 같은 slot만 가능 | 개별 SET/GET + 파이프라인 |
| Pub/Sub | Cluster-wide 동작 | 영향 없음 |

관련: [Redis 기본 § Redis Cluster](./basic.md#redis-cluster), [Redis Lua 스크립트](./lua-script.md), [Redis 영속성과 클러스터](./backup.md)

---

## 5. Hot Key와 Big Key — 운영의 두 지뢰

`operations.md`에 진단 명령어가 있지만, **개념 정의와 대응 설계**는 여러 문서에 분산되어 있어 허브에서 통합한다.

### Hot Key (단일 키 트래픽 집중)

**증상:** 해당 슬롯의 CPU 100%, P99 지연 스파이크. 전체 서버는 한가한데 특정 노드만 과부하.

**대응 계층:**

```
[L0 앱 내 캐시]   Caffeine 1~5초 TTL → Redis 호출 자체를 흡수
[L1 로컬 로컬]    JVM 여러 대라면 Pub/Sub 무효화 신호
[L2 Redis]        Read replica에 읽기 분산 (쓰기는 master)
[L3 샤딩]         counter:page:123 → counter:page:123:{0..9} 10개로 분산
                   읽을 때 SUM, 정확도 소폭 희생
```

→ [Cache-Aside § Hot Key](./cache-aside.md#장애-2--hot-key-집중-hot-spot) 에 코드 예시가 있다.

### Big Key (단일 키 용량 비대)

**증상:** `DEL`만 해도 수 초 블로킹. `HGETALL` 타임아웃. 메모리 파편화 악화.

**탐지/대응:**

```bash
redis-cli --bigkeys                    # 큰 키 스캔
redis-cli MEMORY USAGE chat:room:1     # 개별 키 크기
UNLINK chat:room:1                     # 비동기 삭제 (Redis 4.0+)
```

**설계 원칙:**
- 리스트/해시를 **파티셔닝**한다: `chat:room:1:msgs:2026-04`, `chat:room:1:msgs:2026-05`.
- 오래된 데이터는 `ZREMRANGEBYRANK`, `LTRIM`으로 주기적 삭제.
- 삭제는 `DEL` 대신 **`UNLINK`** (Redis 4.0+).

→ [Redis 기본 § 주의사항](./basic.md#주의사항), [운영 가이드 § 운영 금지 명령어](./operations.md#운영-금지-명령어)

---

## 6. Graceful Degradation — Redis 장애 시 서비스가 죽지 않게

**원칙:** Redis는 캐시 계층이다. Redis 장애가 서비스 전체 장애로 번지면 설계가 잘못된 것이다.

### 3단 방어

```
[1] 짧은 타임아웃       → Lettuce commandTimeout = 50~500ms
[2] Circuit Breaker    → 연속 실패 시 Redis 우회, DB 직접 조회
[3] DB 폴백 + 부하 보호 → 커넥션 풀 한계, 쿼리 타임아웃, 비상 rate limit
```

```java
try {
    return redisCircuitBreaker.executeSupplier(() -> redis.get(key));
} catch (Exception e) {
    log.warn("Redis unavailable, falling back to DB");
    return db.findById(id);  // 단, DB 커넥션 풀이 살아있는지 확인
}
```

**주의:** Redis 다운 → DB로 트래픽 전부 쏠림 → DB도 다운 (연쇄 장애)이 실제로 가장 자주 발생한다. DB 쪽 보호(커넥션 풀 상한, 쿼리 타임아웃, 비상 rate limit)가 준비되지 않으면 Redis 다운보다 더 큰 장애가 난다.

→ [Cache-Aside § 장애 1 Redis 완전 다운](./cache-aside.md#장애-1--redis-완전-다운), [Resilience 패턴](../../architecture/resilience-patterns.md)

---

## 7. 장애 유형 → 펼칠 문서 매핑

실무에서 장애가 발생했을 때 **어느 문서를 먼저 꺼내는가**를 정리한다.

| 증상 | 1차 문서 | 2차 문서 |
|------|---------|---------|
| DB CPU 폭주 + Redis 히트율 급락 | [Cache-Aside § 스탬피드](./cache-aside.md#cache-stampede-캐시-스탬피드) | [operations § 장애 5](./operations.md#5-cache-stampede-캐시-폭풍) |
| 특정 슬롯 CPU 100% | 본 문서 § Hot Key | [basic § Redis Cluster](./basic.md#redis-cluster) |
| DEL 한 번에 서버 블로킹 | 본 문서 § Big Key | [operations § 운영 금지 명령어](./operations.md#운영-금지-명령어) |
| 분산 락에도 oversell 발생 | [distributed-lock § Redlock](./distributed-lock.md#redlock-클러스터-환경의-분산-락) | [lua-script § Lua 원자성 한계](./lua-script.md#lua-스크립트의-원자성-한계) |
| Cluster 이전 후 CROSSSLOT 에러 | 본 문서 § Cluster 제약 | [lua-script](./lua-script.md) |
| 메모리 파편화 / evicted_keys 증가 | [operations § 메모리](./operations.md#메모리--얼마가-적절하고-몇--이상이면-위험한가) | [basic § 메모리 파편화](./basic.md#메모리-파편화) |
| 세션이 간헐적으로 사라짐 | [session](./session.md) | [operations § 장애 2 서버 재시작](./operations.md#2-서버-다운--재시작) |
| Redis 다운 → 서비스 전체 다운 | 본 문서 § Graceful Degradation | [cache-aside § 장애 1](./cache-aside.md#장애-1--redis-완전-다운) |
| 메시지가 조용히 사라짐 | [pub-sub § Pub/Sub 한계](./pub-sub.md#한계-중요) | [pub-sub § Stream](./pub-sub.md#redis-stream) |

---

## 인터뷰 답변 프레임 — 문서를 넘나드는 답

시니어 백엔드 면접에서 Redis 질문은 단일 문서 수준에서 답변하면 얕게 들린다. **여러 패턴을 연결하는 답**이 경력자처럼 들린다.

### Q. "캐시 전략을 어떻게 잡으시나요?"

> Cache-Aside를 기본으로 하고, 쓰기 경로에서는 set이 아니라 delete를 씁니다. 동시 쓰기 race에서 stale 캐시가 남는 걸 줄이기 위해서입니다. TTL에는 항상 랜덤 지터를 넣고, 인기 키가 있다면 L1으로 Caffeine을 30초 TTL로 두거나, 필요하면 분산 락으로 단일 재계산을 보장합니다. 정합성이 극도로 중요한 데이터는 캐시를 안 쓰거나, 짧은 TTL + 이벤트 기반 무효화를 조합합니다.

(링크: [cache-aside](./cache-aside.md), [distributed-lock](./distributed-lock.md))

### Q. "Redis 분산 락으로 재고 차감 막을 수 있나요?"

> Redis 락은 best-effort입니다. Redlock이라 해도 GC stall이나 clock drift 상황에서 완전한 mutual exclusion은 불가능합니다. 그래서 돈이 걸린 경로는 Redis 락을 최종 방어선으로 쓰지 않습니다. Redis 차감은 Lua로 원자화해 **예약**으로 다루고, 최종 결정은 DB 트랜잭션 + 유니크 제약 + CHECK 제약으로 이중 방어합니다. 실패하면 Redis에 보상 INCR로 되돌립니다.

(링크: [distributed-lock](./distributed-lock.md), [lua-script](./lua-script.md))

### Q. "단일 Redis를 Cluster로 옮길 때 무엇을 조심하나요?"

> 가장 자주 터지는 건 CROSSSLOT입니다. Lua, MULTI/EXEC, MSET이 같은 슬롯의 키만 지원하기 때문에, 같이 atomic하게 다뤄야 하는 키들은 해시 태그로 묶어야 합니다. 단, 태그를 남발하면 특정 슬롯에 트래픽이 집중되는 hot slot이 생기기 때문에, 해시 태그 설계는 데이터 모델 설계 단계에서 결정해야 합니다.

(링크: [basic § Cluster](./basic.md#redis-cluster))

### Q. "Redis가 다운되면 서비스는요?"

> 캐시 계층 장애를 서비스 전체 장애로 번지지 않게 하는 것이 원칙입니다. 모든 Redis 호출은 50~500ms 타임아웃으로 감싸고 Circuit Breaker로 감지합니다. 단 DB 폴백을 준비하는 것으로 끝이 아니고, Redis 트래픽이 DB로 쏠릴 때 DB가 죽지 않도록 커넥션 풀 상한과 비상 rate limit이 같이 설계돼 있어야 합니다.

(링크: [cache-aside § 장애 1](./cache-aside.md#장애-1--redis-완전-다운), [resilience-patterns](../../architecture/resilience-patterns.md))

---

## 허브 체크리스트 — 설계 단계에서 확인할 것

- [ ] 캐시 전략이 Cache-Aside + delete-on-write + TTL 지터로 시작하는가
- [ ] 인기 키에 대해 스탬피드 방어(지터/락/L1/PER) 중 최소 한 가지가 걸려 있는가
- [ ] 임계 경로(돈/재고)에 Redis Lua + DB 제약의 이중 방어가 걸려 있는가
- [ ] Redis 락의 한계(GC, clock drift)를 이해하고 DB 방어를 생략하지 않았는가
- [ ] Cluster 사용 시 해시 태그 설계가 데이터 모델 단계에서 반영되어 있는가
- [ ] 해시 태그 남발로 hot slot이 생기지 않는지 검토했는가
- [ ] Hot key에 대해 L1 로컬 캐시 또는 키 샤딩이 준비되어 있는가
- [ ] Big key(100KB+)가 주기적으로 탐지/파티셔닝되는가 (`--bigkeys`, `MEMORY USAGE`)
- [ ] 삭제는 `DEL` 대신 `UNLINK`를 우선 쓰는가 (Redis 4.0+)
- [ ] 모든 Redis 호출이 짧은 타임아웃으로 감싸져 있는가 (50~500ms)
- [ ] Circuit Breaker가 Redis 장애를 감지하고 DB 폴백으로 전환하는가
- [ ] DB 폴백 시 커넥션 풀/비상 rate limit으로 DB가 연쇄 장애를 피하는가
- [ ] 메시지 유실 허용 여부로 Pub/Sub vs Stream vs Kafka가 구분돼 있는가
- [ ] `KEYS *`, `FLUSHALL`, 대형 컬렉션 전수 조회 같은 금지 명령이 운영에서 차단되는가
- [ ] 장애 유형별 런북이 있어 "어느 문서를 볼지"를 즉시 안다 (§ 7 매핑 참조)

---

## 관련 문서

**기초:**
- [Redis 기본](./basic.md) — 아키텍처, 자료구조, 싱글 스레드 전제
- [Redis 영속성과 클러스터](./backup.md) — RDB/AOF, Sentinel/Cluster

**패턴별 심화:**
- [Cache-Aside 완전 정복](./cache-aside.md) — 정합성, 스탬피드, L1/L2, 장애 대응
- [분산 락](./distributed-lock.md) — SET NX, Redisson, Redlock 한계
- [Rate Limiting](./rate-limiting.md) — 고정/슬라이딩 윈도우, 토큰 버킷
- [Pub/Sub & Stream](./pub-sub.md) — 실시간 브로드캐스트 vs 신뢰성 큐
- [세션 저장소](./session.md) — Spring Session, JWT 비교
- [실시간 랭킹](./leaderboard.md) — Sorted Set 기반 랭킹 설계
- [Lua 스크립트](./lua-script.md) — Hash + Lua 잭팟 누적/당첨 사례

**운영:**
- [Redis 운영 가이드](./operations.md) — 성능, 메모리, 모니터링, 장애 대응, 설정

**교차 주제:**
- [캐시 설계 전략](../../architecture/cache-strategies.md) — Look-Aside, Read/Write-Through 전반
- [Resilience 패턴](../../architecture/resilience-patterns.md) — Circuit Breaker, 타임아웃, 폴백
