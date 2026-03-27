# Redis

> "Remote Dictionary Server" — 원격에 위치한 프로세스로 동작하는 인메모리 키-값 데이터 구조 서버

Redis는 단순한 캐시가 아니라 **데이터베이스, 캐시, 메시지 브로커, 스트리밍 엔진**으로 모두 쓰인다. RAM에서 직접 처리하므로 디스크 기반 DB 대비 수백 배 빠르지만, 용량이 제한적이고 기본적으로 영속성을 보장하지 않는다는 트레이드오프가 있다.

---

## 왜 빠른가?

### 1. 인메모리 기반

디스크 I/O 병목이 없다. 10,000건 기준으로 디스크는 약 30초, RAM은 약 0.0002초가 소요된다.

### 2. 최적화된 자료구조

단순 String이 아니라 연산 특성에 맞게 자체 구현된 자료구조를 사용한다.

- **Hash Table**: 평균 O(1) 접근
- **Skip List** (Sorted Set): O(log N)으로 정렬 데이터 유지
- **IntSet / ZipList → ListPack**: 데이터 양이 적을 때는 메모리 절약형 선형 구조를 쓰다가, 임계값을 초과하면 자동으로 더 빠른 구조로 전환

### 3. 싱글 스레드 이벤트 루프

Redis 핵심 엔진은 싱글 스레드로 동작한다.

- **Context Switching 비용 없음**: 멀티 스레드 오버헤드 제거
- **Lock-free**: Race condition 걱정 없이 코드가 단순하고 빠름
- **I/O Multiplexing**: `epoll`/`kqueue` 같은 비차단 I/O로 수만 개의 클라이언트 연결을 동시에 처리

> 싱글 스레드이기 때문에 `KEYS *`, `SMEMBERS`, `HGETALL` 같은 **O(N) 명령어 하나가 전체 서버를 블로킹**할 수 있다. 운영 환경에서 주의해야 한다.

---

## 자료구조 (Data Types)

### String

Redis의 가장 기본 타입. 텍스트, 숫자, 바이너리 모두 저장 가능하며 최대 512MB.

```
SET user:1:name "Alice"
GET user:1:name

INCR page:view:count      # 원자적 카운터
INCRBY page:view:count 5
```

**주요 사용 사례:**
- 캐시 (HTML 조각, API 응답 JSON)
- 원자적 카운터 (조회수, 좋아요 수)
- 분산 락 (`SET key value NX EX seconds`)
- 세션 토큰 저장

---

### Hash

필드-값 쌍의 집합. 객체 하나를 키 하나로 표현하기에 적합하다.

```
HSET user:1 name "Alice" age 30 email "alice@example.com"
HGET user:1 name
HGETALL user:1
HINCRBY user:1 age 1
```

**주요 사용 사례:**
- 사용자 프로필, 상품 정보 저장
- 여러 필드를 각각 조회/갱신할 때 (String으로 JSON 직렬화보다 효율적)
- 잭팟 풀처럼 다수의 카운터를 하나의 키로 관리 → [Lua 스크립트 활용 사례](./lua-script.md)

> `HGETALL`은 O(N)이므로 필드가 많을 때는 특정 필드만 `HGET`으로 가져오는 것이 안전하다.

---

### List

삽입 순서가 유지되는 이중 연결 리스트. 양쪽 끝에서 O(1)로 삽입/삭제가 가능하다.

```
LPUSH queue:email "job1"    # 왼쪽 삽입 (최신)
RPUSH queue:email "job2"    # 오른쪽 삽입
LPOP queue:email            # 왼쪽 제거 (스택)
RPOP queue:email            # 오른쪽 제거 (큐)
LRANGE queue:email 0 -1     # 전체 조회 (O(N))
BLPOP queue:email 30        # 블로킹 팝 (최대 30초 대기)
```

**주요 사용 사례:**
- 작업 큐 (Producer-Consumer 패턴)
- 최근 활동 내역 (최근 본 상품, 알림 목록)
- 타임라인 (SNS 피드)
- Twitter는 초당 30만 건의 타임라인 요청을 Redis List로 캐싱

---

### Set

중복 없는 고유 값의 집합. 순서 보장 없음. 합집합/교집합/차집합 연산 지원.

```
SADD user:1:tags "backend" "redis" "java"
SISMEMBER user:1:tags "redis"    # 멤버 여부 O(1)
SMEMBERS user:1:tags             # 전체 조회 (O(N) 주의)
SUNION user:1:tags user:2:tags   # 합집합
SINTER user:1:tags user:2:tags   # 교집합 (공통 팔로워 등)
SCARD user:1:tags                # 크기
```

**주요 사용 사례:**
- 팔로워/팔로잉 목록
- 태그, 카테고리 분류
- 중복 방문자 제거
- "A를 구매한 사람이 또 구매한 상품" 같은 교집합 추천

---

### Sorted Set (ZSet)

각 멤버에 **score(실수)**를 부여해 정렬 상태를 유지하는 집합. score 기준 범위 조회가 O(log N).

```
ZADD leaderboard 1500 "user:alice"
ZADD leaderboard 2300 "user:bob"
ZRANK leaderboard "user:alice"        # 순위 (낮은 score = 낮은 순위)
ZREVRANK leaderboard "user:bob"       # 역순 순위
ZRANGE leaderboard 0 9 WITHSCORES    # 하위 10명
ZREVRANGE leaderboard 0 9 WITHSCORES # 상위 10명
ZINCRBY leaderboard 100 "user:alice"  # score 증가
```

**주요 사용 사례:**
- 리더보드 / 랭킹 시스템
- 위시리스트 (담은 시간을 score로 → 최신순 정렬 자동)
- 우선순위 큐
- 지연 실행 큐 (실행 시각을 score로 설정)
- Rate Limiting (타임스탬프를 score로 사용)

---

### Bitmap

String을 비트 배열로 취급. 512MB String = 약 42억 비트. 공간 효율이 매우 높다.

```
SETBIT user:login:20260327 1001 1   # 유저 1001 오늘 로그인
GETBIT user:login:20260327 1001
BITCOUNT user:login:20260327        # 오늘 로그인한 유저 수
BITOP AND result key1 key2          # 7일 연속 로그인 유저
```

**주요 사용 사례:**
- 일별 활성 사용자(DAU) 집계
- 기능 플래그 (사용자별 A/B 테스트)
- 출석 체크 (365비트 = 1년치 출석을 45바이트로 저장)

---

### HyperLogLog

집합의 원소 개수(카디널리티)를 **근사치**로 계산하는 자료구조. 오차율 약 0.81%이지만 메모리를 최대 12KB만 사용한다.

```
PFADD uv:20260327 "user:1" "user:2" "user:1"   # 중복 자동 제거
PFCOUNT uv:20260327                              # 약 2 반환
PFMERGE uv:week uv:day1 uv:day2 uv:day3        # 주간 UV 합산
```

**주요 사용 사례:**
- 페이지별 UV(순 방문자 수) 집계
- 정확성보다 규모가 중요한 대용량 통계

---

### Stream

Redis 5.0에 추가된 로그 구조 자료구조. Kafka와 유사하게 소비자 그룹 기반으로 메시지를 처리한다.

```
XADD orders * userId 1001 amount 50000    # 메시지 추가
XLEN orders                               # 메시지 수
XREAD COUNT 10 STREAMS orders 0          # 읽기
XREADGROUP GROUP workers consumer1 COUNT 10 STREAMS orders >  # 소비자 그룹 읽기
XACK orders workers <message-id>         # 처리 완료 ACK
```

**주요 사용 사례:**
- Kafka보다 가벼운 이벤트 스트리밍
- 주문 생성 후 알림톡, 정산, 분석 데이터 생성 등 부수 작업 처리
- ACK 기반으로 처리 실패 시 재처리 보장

---

## 주요 사용 사례

### 캐시 (Cache)

가장 일반적인 Redis 활용 사례. 캐싱 전략은 **Look-Aside, Read-Through, Write-Through, Write-Behind** 등 다양하다.

→ 캐싱 전략 상세: [캐시 설계 전략 총정리](../../architecture/cache-strategies.md)

**실전 포인트:**
- TTL을 반드시 설정해 메모리 낭비 방지
- 캐시 미스 시 DB 폴백 로직 필수 (장애 내결함성)
- Cache Stampede 방지: Lock 또는 Probabilistic Early Expiration

---

### 세션 저장소 (Session Store)

다중 서버 환경에서 서버 간 세션 불일치 문제를 해결한다. 인메모리라 조회가 빠르고, TTL로 세션 만료를 자동 처리한다.

```
SET session:{token} {user_json} EX 1800   # 30분 세션
GET session:{token}
DEL session:{token}                        # 로그아웃
```

**Redis vs Memcached (세션 저장소 비교):**

| 항목 | Redis | Memcached |
|------|-------|-----------|
| 자료구조 | String, Hash, List 등 다양 | String만 |
| 영속성 | RDB/AOF 지원 | 없음 |
| Replication | Master-Replica 지원 | 없음 |
| 클러스터 | 공식 Cluster 지원 | 별도 구성 필요 |
| 성능 | 읽기 우수 | 단순 쓰기 빠름 |

세션 저장소라면 대부분의 경우 Redis가 더 적합하다.

---

### 분산 락 (Distributed Lock)

여러 서버가 동일한 자원에 동시 접근하는 것을 막는다. `SET NX EX` 조합으로 원자적으로 락을 획득한다.

```
SET lock:resource:1 {owner} NX EX 30   # 락 획득 (이미 있으면 실패)
DEL lock:resource:1                     # 락 해제
```

- **Redisson 라이브러리**: Pub/Sub 기반으로 Lock 해제 신호를 대기하므로 스핀 락보다 Redis 부하가 낮다
- **Redlock 알고리즘**: 클러스터 환경에서 과반수 노드에 락을 획득해야 유효로 처리 (단일 노드 장애 대응)
- **DECR / INCRBY**: 원자적 재고 차감. 음수 체크로 초과 예약 방지

---

### Pub/Sub

채널을 통해 발행자(Publisher)와 구독자(Subscriber) 간 실시간 메시지를 전달한다.

```
SUBSCRIBE channel:notifications          # 구독
PUBLISH channel:notifications "새 알림"  # 발행
PSUBSCRIBE channel:*                     # 패턴 구독
```

**주의:** Pub/Sub은 메시지를 **영속하지 않는다**. 구독자가 없거나 오프라인이면 메시지가 유실된다. 신뢰성이 필요하다면 **Redis Stream**을 사용해야 한다.

**주요 사용 사례:**
- 실시간 채팅, 알림 브로드캐스트
- 캐시 무효화 이벤트 (다른 서버에 캐시 삭제 신호)
- 간단한 이벤트 버스

---

### Rate Limiting (요청 제한)

```
# 슬라이딩 윈도우: Sorted Set 방식
ZADD rate:user:1 {now_ms} {now_ms}    # 현재 요청 추가
ZREMRANGEBYSCORE rate:user:1 0 {window_start}  # 윈도우 밖 제거
ZCARD rate:user:1                       # 현재 윈도우 요청 수

# 고정 윈도우: INCR 방식
INCR rate:user:1:{minute}
EXPIRE rate:user:1:{minute} 60
```

**주요 사용 사례:**
- API 호출 횟수 제한 (분당 N회)
- 로그인 시도 횟수 제한
- DDoS 방어

---

### 리더보드 (Leaderboard)

Sorted Set의 score를 점수로 사용해 실시간 순위를 O(log N)으로 유지한다.

```
ZINCRBY leaderboard 100 "user:1"          # 점수 추가
ZREVRANK leaderboard "user:1"             # 현재 순위
ZREVRANGE leaderboard 0 9 WITHSCORES     # 상위 10명
ZRANGEBYSCORE leaderboard 1000 +inf      # 특정 점수 이상
```

**주요 사용 사례:**
- 게임 점수 순위
- 판매량 TOP N
- 실시간 인기 상품/검색어

---

### CQRS Read Model (Materialized View)

복잡한 JOIN이 필요한 읽기 조회를 Redis에 미리 조합해 저장한다.

- **Write-Behind 전략**: DB에 쓰고 동시에 Redis에 "주문 요약" 형태의 Hash 또는 JSON 저장
- **RediSearch 모듈**: Redis 내에서 인덱싱과 전문 검색(Full-text search)이 가능해 RDBMS 대비 훨씬 빠른 필터링 응답

---

## 주의사항

### O(N) 명령어 위험

Redis는 싱글 스레드이므로 O(N) 명령어 하나가 전체 서버를 블로킹한다.

| 위험 명령어 | 대안 |
|------------|------|
| `KEYS *` | `SCAN` (커서 기반 반복) |
| `SMEMBERS` | `SSCAN` |
| `HGETALL` (필드 많을 때) | `HSCAN` 또는 필요한 필드만 `HGET` |
| `LRANGE 0 -1` (긴 리스트) | 페이지네이션 |
| `FLUSHALL`, `FLUSHDB` | 운영 환경 사용 금지 |

### 메모리 파편화

Redis가 메모리를 할당/해제를 반복하면 파편화가 발생해 실제 사용량보다 많은 물리 메모리를 점유할 수 있다. 심하면 OOM으로 프로세스가 종료될 수 있다.

- `INFO memory`에서 `mem_fragmentation_ratio`를 모니터링 (1.5 이상이면 주의)
- Redis 4.0+의 `MEMORY PURGE`로 파편화 메모리 회수 가능
- `jemalloc` 사용으로 파편화 최소화 (기본값)

### 데이터 유실

기본 설정에서 Redis는 프로세스 재시작 시 데이터가 사라진다. 영속성이 필요하면 RDB 스냅샷이나 AOF를 설정해야 한다.

→ 영속성 및 클러스터 상세: [Redis 영속성과 클러스터](./backup.md)

### 싱글 스레드 한계

CPU 코어가 많아도 단일 코어만 사용한다. CPU-bound 작업(복잡한 Lua 스크립트 등)이 많으면 처리량이 제한된다. Redis 6.0+부터는 I/O 처리는 멀티 스레드화되었지만 명령 실행은 여전히 싱글 스레드다.

---

## 고가용성 구성

### Redis Sentinel

마스터 장애 시 자동으로 레플리카를 마스터로 승격(Failover)하는 모니터링 시스템이다. Sentinel 자체도 홀수 개(최소 3개)로 구성해 과반수 합의로 장애를 판단한다.

```
Master ──→ Replica 1
       └─→ Replica 2

Sentinel 1 │
Sentinel 2 ├─ Master 감시 → 장애 감지 → Replica 승격
Sentinel 3 │
```

### Redis Cluster

16,384개의 해시 슬롯으로 데이터를 분산해 수평 확장을 지원한다.

```
노드 A (Master): 슬롯 0 ~ 5460
노드 B (Master): 슬롯 5461 ~ 10922
노드 C (Master): 슬롯 10923 ~ 16383

각 Master마다 Replica 보유 → 자동 Failover
```

- 키 라우팅: `CRC16(key) % 16384`
- 해시 태그 `{}`: `{user:1}:orders`와 `{user:1}:profile`은 같은 노드에 저장 (트랜잭션 지원 위해)
- `MGET`, `MULTI/EXEC`는 같은 슬롯의 키에만 사용 가능

→ 클러스터/영속성 상세: [Redis 영속성과 클러스터](./backup.md)

---

## 관련 문서

- [캐시 설계 전략 총정리](../../architecture/cache-strategies.md) — Look-Aside, Read-Through, Write-Through, Write-Behind 등 캐시 패턴 상세
- [Redis 영속성과 클러스터](./backup.md) — RDB/AOF 설정, Cluster 구성 상세
- [Redis Lua 스크립트](./lua-script.md) — Hash + Lua로 원자적 잭팟 누적/당첨 처리 구현 사례

---

## 참고

- [REDIS 📚 개념 소개 사용처 캐시 세션 한눈에 쏙 정리](https://inpa.tistory.com/entry/REDIS-%F0%9F%93%9A-%EA%B0%9C%EB%85%90-%EC%86%8C%EA%B0%9C-%EC%82%AC%EC%9A%A9%EC%B2%98-%EC%BA%90%EC%8B%9C-%EC%84%B8%EC%85%98-%ED%95%9C%EB%88%88%EC%97%90-%EC%8F%99-%EC%A0%95%EB%A6%AC)
- [Redis 공식 문서](https://redis.io/docs/latest/)
