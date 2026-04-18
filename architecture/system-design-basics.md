# [초안] 시니어 백엔드를 위한 시스템 설계 입문 스터디 팩

## 왜 시스템 설계가 면접의 승부처인가

시니어 백엔드 포지션의 기술 면접에서 코딩 테스트는 "탈락시킬 사람을 거르는" 필터에 가깝고, 실제로 합격과 불합격을 가르는 단계는 시스템 설계 라운드다. 이유는 단순하다. 주니어는 주어진 API 스펙을 구현하면 되지만, 시니어는 "요구사항이 명확하지 않은 상태에서 제약 조건을 스스로 도출하고, 여러 선택지 중 트레이드오프를 명시하며 의사결정할 수 있는가"를 증명해야 한다. 면접관은 정답 아키텍처를 찾으러 온 것이 아니라, 당신이 장애 상황에서 조직을 대표해 판단할 수 있는 사람인지 관찰하러 온 것이다.

이 문서는 "URL shortener를 그려 보세요"라는 고전적 질문에 45분 안에 요구사항 명확화부터 장애 대응까지 매끄럽게 talk-through할 수 있도록 구성된 실전 스터디 팩이다. CJ 올리브영 웰니스 플랫폼처럼 트래픽 스파이크가 분명하고, 커머스/회원/추천이 동시에 돌아가는 환경에서 시니어로서 설득력 있게 말할 수 있어야 한다.

## 핵심 개념 1: 요구사항 명확화는 "문제를 좁히는 행위"다

면접관이 "URL shortener를 설계해 달라"고 하면 바로 박스와 화살표를 그리기 시작하는 후보는 거의 대부분 감점된다. 시니어는 먼저 문제의 경계를 재정의해야 한다. 다음 세 축으로 질문을 던진다.

**Functional requirements (기능 요구사항)**
- 핵심 사용자 시나리오는 무엇인가? 단축 URL 생성, 리다이렉트, 통계 조회, 만료 관리, 커스텀 alias?
- 쓰기(write) vs 읽기(read) 비율 추정은? URL shortener는 보통 1:100 ~ 1:1000의 read-heavy 시스템이다.
- 사용자 인증이 필요한가? 익명 생성을 허용하는가?
- 통계(클릭 수, 지역별 분포)는 실시간인가 배치로 충분한가?

**Non-functional requirements (비기능 요구사항)**
- 가용성 목표: 99.9% (연 8.76시간 다운) vs 99.99% (연 52분)?
- 지연시간 목표: 리다이렉트 p99 < 100ms?
- 데이터 보존 기간: 5년? 무기한?
- 보안: 단축 URL을 통한 피싱 방지, abuse detection?

**일관성 / 실시간성 / 확장성 축**
- 방금 만든 단축 URL을 즉시 리다이렉트할 수 있어야 하는가? (read-your-writes)
- 통계 카운터는 eventual consistency로 충분한가?
- 트래픽 성장 예측: 1년 후 10배, 5년 후 100배를 감당해야 하는가?

이 질문을 15개쯤 준비해서 면접 초반 5~7분을 "질문-확인-정리"로 사용하는 것이 프로다. 좁혀진 요구사항은 이후 모든 의사결정의 정당화 근거로 사용된다. 예를 들어 "실시간 통계는 eventual로 가능"이라는 합의를 얻어내면, 나중에 Kafka + 배치 집계 구조를 자연스럽게 정당화할 수 있다.

## 핵심 개념 2: Capacity estimation — back-of-the-envelope 계산

용량 추정을 못 하는 시니어는 없다. 하지만 면접장에서 당황하지 않고 빠르게 계산하려면 "숫자 블록"을 외워 둬야 한다.

기본 숫자 블록:
- 1일 = 86,400초 ≈ 10^5초
- 1년 = 약 3 × 10^7초
- UTF-8 영문자 1자 = 1 byte, 한글 1자 = 약 3 bytes
- HDD seek = 10ms, SSD seek = 0.1ms, 메모리 read = 100ns, 네트워크 RTT(같은 리전) = 0.5ms

URL shortener 실전 추정 예시:
- 가정: 월 500M 단축 URL 생성, read:write = 100:1
- 쓰기 QPS: 500M / (30 × 86,400) ≈ 500M / 2.6M ≈ 193 QPS (평균), 피크 × 3 = 약 600 QPS
- 읽기 QPS: 193 × 100 ≈ 19,300 QPS (평균), 피크 약 60,000 QPS
- 5년 저장 URL: 500M × 12 × 5 = 30B (300억 개)
- 레코드 크기: short_key(7) + long_url(평균 100) + user_id(8) + created_at(8) + meta(77) ≈ 200 bytes
- 총 저장소: 30B × 200 bytes = 6TB (인덱스 제외, 인덱스 포함 약 9~10TB)
- 대역폭(읽기): 60,000 × 500 bytes(응답) = 30MB/s = 240Mbps 피크

이 숫자를 말하면서 "캐시 hit rate 90%를 가정하면 DB가 받는 읽기는 6,000 QPS로 떨어져서 read replica 3~5대로 감당 가능하다"까지 이어지면, 면접관은 이미 당신을 믿기 시작한다.

## 핵심 개념 3: 기본 빌딩 블록 카탈로그

시니어는 각 컴포넌트의 "언제 쓰면 안 되는지"까지 말할 수 있어야 한다.

**Load Balancer (L4/L7)**
- L4(TCP): HAProxy, NLB — 낮은 지연, 프로토콜 무관
- L7(HTTP): ALB, Nginx — 경로 기반 라우팅, TLS termination, sticky session
- 안티패턴: 모든 트래픽에 sticky session을 거는 것 — 스케일 아웃 시 캐시 국소성이 깨지면서 오히려 불균형 발생

**API Gateway**
- 인증, rate limiting, 요청 변환, API versioning, observability 일원화
- 주의: gateway가 비즈니스 로직을 품으면 "분산 모놀리스"가 된다. gateway는 얇게 유지한다.

**서비스 분리 (Microservice)**
- 분리 기준은 "팀 경계 + 데이터 오너십 + 배포 주기"이다. 기술적 호기심으로 쪼개면 분산 트랜잭션 지옥에 빠진다.
- Saga 패턴, outbox 패턴을 이해하고 있어야 한다.

**Database**
- OLTP: MySQL/PostgreSQL — 강한 일관성, 트랜잭션, 외래키
- OLAP: BigQuery, Redshift — 컬럼 지향, 배치 분석
- NoSQL: DynamoDB(key-value), MongoDB(document), Cassandra(wide column) — 특정 접근 패턴에 최적
- 시니어 포인트: "왜 NoSQL인가"에 "scalable하니까"라고 답하면 탈락. "접근 패턴이 key 기반 point lookup으로 고정되어 있고 join이 없기 때문"이라고 답해야 한다.

**Cache**
- In-memory: Redis, Memcached
- 패턴: Cache-aside (lazy), Write-through, Write-behind, Refresh-ahead
- 실패 패턴: Thundering herd(캐시 만료 시 DB 폭격), Cache stampede — 해결책은 랜덤 TTL jitter, probabilistic early expiration, request coalescing(singleflight)

**Message Queue**
- Kafka: 고처리량 로그/이벤트 스트림, 순서 보장은 파티션 단위
- RabbitMQ, SQS: task queue, at-least-once 전달
- 핵심: "왜 동기 호출이 아니라 큐인가?" — 결합도 분리, 스파이크 흡수, 재시도 격리, 도메인 이벤트 broadcast

**CDN**
- Static asset뿐 아니라 edge caching으로 API 응답 자체를 캐싱 가능(Cloudflare Workers, CloudFront Functions)
- URL shortener의 리다이렉트는 CDN edge에서 처리하면 원본 서버 QPS를 획기적으로 줄일 수 있다.

## 핵심 개념 4: 스케일링 전략

**Vertical scaling (scale-up)**
- 장점: 복잡도 없음, 즉효성. 초기 스타트업은 이게 정답인 경우가 많다.
- 한계: 단일 머신 상한, SPOF, 다운타임 동반 업그레이드

**Horizontal scaling (scale-out)**
- 상태 없는(stateless) 서비스에 적용이 쉽다. 상태가 있으면 sticky session이나 외부 상태 저장소(Redis, DB)가 필요하다.
- 시니어 포인트: "scale-out을 위해 상태를 어디로 빼낼 것인가"가 진짜 설계 질문이다.

**Read replica**
- Master-slave 구조. 쓰기는 마스터, 읽기는 복제본. Replication lag는 현실이다(수 ms ~ 수 초).
- Read-your-writes가 필요한 API는 마스터로 강제 라우팅하거나, "방금 쓴 사용자"는 일정 시간 마스터로 읽도록 힌트를 건다.

**Partitioning (수직/수평)**
- 수직 파티셔닝: 테이블 컬럼을 쪼개 핫 컬럼과 콜드 컬럼 분리
- 수평 파티셔닝(sharding): 행을 샤드 키 기준으로 분산

**Sharding 전략**
- Range: 시간/ID 범위. 핫샤드 위험(최신 데이터가 한 샤드에 몰림).
- Hash: 균등 분산. 범위 쿼리 불가.
- Directory(lookup table): 유연하지만 디렉터리가 SPOF.
- Consistent hashing: 노드 추가/제거 시 재분배 최소화. URL shortener의 샤드 키로 `short_key`의 consistent hash를 쓴다면 노드 3→4 확장 시 1/4만 이동한다.

## 핵심 개념 5: 일관성 모델

- **Strong consistency**: 쓰기 직후 모든 읽기가 최신값. 비용 큼(쿼럼 읽기/쓰기, 합의 프로토콜).
- **Eventual consistency**: 시간이 지나면 수렴. 댓글 좋아요 카운터, 조회수 등에 적합.
- **Read-your-writes**: 사용자 본인이 쓴 것은 본인이 바로 읽을 수 있다. 세션 기반 스티키 라우팅 또는 "최근 쓰기 타임스탬프" 기반 라우팅.
- **Monotonic read**: 한 번 본 데이터보다 과거 버전을 다시 보지 않는다. 사용자 세션이 동일 복제본에 붙도록 하거나, 버전 토큰을 들고 다니게 한다.

## 핵심 개념 6: Trade-off 프레임 — CAP와 PACELC

CAP는 "네트워크 파티션(P)이 발생했을 때 C(일관성)와 A(가용성) 중 하나를 포기해야 한다"는 정리지만, 이 프레임만으로는 부족하다. 현실은 네트워크 파티션이 없는 시간이 훨씬 길기 때문이다.

**PACELC**가 더 실전적이다.
- **P**artition 시: **A**vailability vs **C**onsistency
- **E**lse(정상 시): **L**atency vs **C**onsistency

예시:
- DynamoDB: PA/EL — 파티션 시 가용성, 평소엔 지연시간 우선 (eventual consistency default)
- 전통 RDBMS: PC/EC — 파티션 시 일관성, 평소에도 일관성 우선
- Cassandra: PA/EL, 튜닝 가능

면접에서 "왜 이 DB를 골랐는가"를 물으면 PACELC 프레임으로 답하면 설득력이 압도적이다.

## 딥다이브: URL Shortener 전체 설계

### 1) 요구사항 확정
- 단축 URL 생성 / 리다이렉트 / 기본 통계
- 인증된 사용자만 custom alias 허용
- 단축 URL 7자리 base62 (62^7 ≈ 3.5조) → 30B 저장량 충분
- 가용성 99.95%, 리다이렉트 p99 < 80ms
- 통계는 1분 지연 허용(eventual)

### 2) 용량 추정 (앞 절 참고)
쓰기 600 QPS 피크, 읽기 60,000 QPS 피크, 5년 30B rows, 약 10TB.

### 3) 스키마 (MySQL 8)

```sql
CREATE TABLE urls (
  short_key   CHAR(7)       NOT NULL,
  long_url    VARCHAR(2048) NOT NULL,
  user_id     BIGINT        NULL,
  created_at  DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  expires_at  DATETIME(3)   NULL,
  PRIMARY KEY (short_key)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  ROW_FORMAT=DYNAMIC;

CREATE INDEX idx_urls_user_created
  ON urls (user_id, created_at);

CREATE TABLE url_click_events (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  short_key   CHAR(7)     NOT NULL,
  clicked_at  DATETIME(3) NOT NULL,
  country     CHAR(2)     NULL,
  referer     VARCHAR(512) NULL,
  INDEX idx_click_key_time (short_key, clicked_at)
) ENGINE=InnoDB
  PARTITION BY RANGE (TO_DAYS(clicked_at)) (
    PARTITION p202604 VALUES LESS THAN (TO_DAYS('2026-05-01')),
    PARTITION p202605 VALUES LESS THAN (TO_DAYS('2026-06-01')),
    PARTITION pmax    VALUES LESS THAN MAXVALUE
  );
```

`short_key`를 PK로 두면 리다이렉트는 점 조회(point lookup)로 끝난다. `url_click_events`는 월별 파티션으로 retention 관리와 낡은 파티션 drop을 쉽게 한다.

### 4) 단축 키 생성 전략
- **해시 기반**(MD5/SHA256 → base62 앞 7자리): 충돌 가능 → 충돌 시 rehash 또는 seed 추가. 단순하지만 분산 환경에서 충돌 검사 race condition이 까다롭다.
- **ID generator + base62 인코딩**(권장): Snowflake 또는 DB auto-increment → base62. 충돌 없음, 단조 증가로 핫샤드 위험은 consistent hash 샤딩으로 완화.
- **Pre-allocated key pool**: Key generation service가 미리 100만 개씩 키를 만들어 Zookeeper/Redis에 적재, 웹서버는 POP만 한다. 고QPS 환경에서 안정적.

### 5) 하이레벨 아키텍처

```
[Client]
   │
   ▼
[CDN / Edge cache]  ── 핫 단축 URL은 edge에서 리다이렉트
   │
   ▼
[L7 LB / API Gateway] ── TLS, rate limit, auth
   │
   ├──► [Write Service] ──► [Key Gen Service] ──► [MySQL Primary]
   │                                                     │
   │                                              replication
   │                                                     ▼
   └──► [Read Service] ──► [Redis cache] ──► [MySQL Read Replicas]
                                │
                                └── miss ──► DB
   
   [Click events] ──► [Kafka] ──► [Flink/Spark] ──► [Analytics DB]
```

### 6) 병목 & 확장
- **읽기 병목**: Redis hit rate 90%+ 유지. short_key → long_url을 7일 TTL + jitter로 캐싱. Miss stampede는 singleflight로 방지.
- **쓰기 병목**: Key gen pool로 DB insert 부하 분산. Sharding은 short_key consistent hash 기준.
- **통계 병목**: 모든 클릭을 DB에 쓰면 60k QPS 쓰기가 된다. 리다이렉트 경로에서는 Kafka로 이벤트만 던지고, 집계는 스트림 처리 또는 5분 배치.

### 7) 캐시 전략 상세
- Cache-aside + TTL jitter(6~8일 랜덤)
- 생성 직후 write-through로 Redis에 선기록 → read-your-writes 충족
- Negative cache: 존재하지 않는 short_key는 60초간 "not found" 캐싱해서 악성 스캔 방어

### 8) 인증 & rate limit
- 익명: IP당 분당 30 생성, 일 300 생성
- 인증: user_id당 분당 300, 일 30,000
- Token bucket을 Redis Lua로 원자적으로 구현 → API gateway에서 처리
- Abuse: 생성된 long_url을 Google Safe Browsing으로 비동기 검증, 악성이면 단축 URL을 tombstone 처리

## 실습 환경: 로컬에서 돌려보기

MySQL 8 + Redis + Node/Spring/FastAPI 중 취향대로 한다. 아래는 Docker Compose 한 벌.

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpw
      MYSQL_DATABASE: shortener
    ports: ["3306:3306"]
    command: --default-authentication-plugin=mysql_native_password
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  app:
    build: ./app
    depends_on: [mysql, redis]
    environment:
      DB_URL: "mysql://root:rootpw@mysql:3306/shortener"
      REDIS_URL: "redis://redis:6379"
    ports: ["8080:8080"]
```

실습 과제 3개:
1. `/shorten` POST, `/:key` GET 구현 후 `wrk -t4 -c200 -d30s http://localhost:8080/abc1234`로 부하 테스트. Redis 끄고/켜고 비교.
2. `expires_at` 지난 URL을 배치로 soft-delete하는 스케줄러 추가.
3. 클릭 이벤트를 Kafka(로컬 Redpanda)로 흘려 보내고, 1분 윈도우 집계 잡을 Flink로 돌려본다.

## 나쁜 예 vs 개선된 예

**나쁜 예 1**: 리다이렉트 경로에서 동기적으로 `UPDATE urls SET click_count = click_count + 1 WHERE short_key = ?` 호출.
→ row lock contention, 핫 로우에서 락 대기로 p99 폭등.

**개선**: 클릭 이벤트를 Kafka로 fire-and-forget, 집계 잡이 주기적으로 카운트 업데이트. 리다이렉트 p99 유지.

**나쁜 예 2**: "처음부터 10개 MSA로 쪼개요."
→ 초기 트래픽에 비해 운영 복잡도 폭증. 분산 트랜잭션, 분산 추적, CI/CD, 인증 전파 전부 비용.

**개선**: 모듈러 모놀리스로 시작, 데이터 오너십 경계를 명확히 유지, 병목이 드러날 때 해당 경계만 분리(strangler fig pattern).

**나쁜 예 3**: 캐시 TTL을 모든 키에 정확히 1시간으로 설정.
→ 정각마다 대량 만료 → 동시 DB 폭격(thundering herd).

**개선**: TTL에 ±10% 랜덤 jitter, hot key는 probabilistic early refresh.

## 후보자 경험 연결 포인트

Slot 엔진 추상화 경험: "게임 슬롯의 다양한 수학 모델을 engine abstraction 뒤에 숨겨, 클라이언트 계약을 깨지 않고 엔진을 추가/교체했다"는 서술은 **결합도 분리 / plug-in 아키텍처 / contract-first** 경험으로 연결된다. 시스템 설계 라운드에서 "서비스 분리 기준"이나 "stable interface와 내부 진화를 어떻게 양립시켰는가"를 물을 때 강력한 답변이 된다.

RAG 배치 경험: "대량 문서 임베딩 배치를 안정적으로 운영했다"는 서술은 **배치 vs 스트림, 재시도, idempotency, backpressure, partial failure 복구** 경험이다. Kafka + 집계 잡 이야기를 할 때 자연스럽게 "실제로 이런 구조에서 poison message와 DLQ를 어떻게 처리했다"로 이어갈 수 있다.

면접에서는 "제가 맡았던 X에서 비슷한 트레이드오프를 겪었는데, 그때 Y를 선택한 이유는 Z였습니다"라는 템플릿을 2~3번 꽂으면 즉시 신뢰가 쌓인다.

## 면접 talk-through 구조 (45분용)

1. **요구사항 명확화 (5~7분)**: functional, non-functional, 일관성/실시간성/확장성 축. 합의한 내용은 화면 한 귀퉁이에 적어 두고 계속 참조.
2. **용량 추정 (3~5분)**: QPS, 저장소, 대역폭. 숫자를 끝까지 말한다.
3. **하이레벨 설계 (8~10분)**: 박스와 화살표. 컴포넌트별 책임 한 줄 설명.
4. **딥다이브 (10~15분)**: 면접관이 고르는 한 컴포넌트 또는 본인이 가장 자신 있는 곳. DB 스키마, 캐시 전략, 샤딩 키 결정.
5. **병목 & 확장 (5~7분)**: "트래픽 10배가 되면 무엇이 먼저 부러지는가"를 스스로 말한다.
6. **장애 대응 & 트레이드오프 (3~5분)**: 캐시 장애, DB primary 장애, 리전 장애. PACELC로 의사결정 요약.

시간 배분을 지키는 연습을 타이머 두고 3회 이상 해본다. 실전에서 가장 흔한 실패는 "하이레벨 설계에서 시간 다 쓰고 딥다이브를 못 하는 것"이다.

## 시니어가 자주 지적받는 공통 실수와 방어

- **"Scalable하게 설계했습니다"로 뭉뚱그림** → 방어: 숫자로 말한다. "피크 6만 QPS를 감당하도록 Redis 샤드 6개, replica 2개로 구성"처럼.
- **트레이드오프 없이 단정** → 방어: 모든 선택에 "대안 A/B를 고려했고, X 제약 때문에 A를 골랐다"를 덧붙인다.
- **분산 트랜잭션 남용** → 방어: Saga/outbox/idempotency key로 이벤트 기반 일관성을 설명.
- **장애 시나리오 미언급** → 방어: 항상 "이 컴포넌트가 죽으면 시스템은 어떻게 degrade되는가"를 먼저 말한다.
- **기술 유행어 나열** → 방어: Kafka, Kubernetes, GraphQL을 이유 없이 넣지 않는다. "이 요구사항 때문에 선택했다"가 없으면 감점 요인.
- **일관성 모델 혼동** → 방어: strong / eventual / read-your-writes를 사례별로 매칭. URL shortener의 리다이렉트 카운터 = eventual, 방금 만든 URL = read-your-writes.
- **캐시 무효화 미설계** → "computer science의 2대 난제 중 하나"를 설계에서 회피하지 말고 TTL + versioned key + invalidation event로 명시.
- **Rate limit / abuse 누락** → 공개 엔드포인트는 반드시 bucket 기반 제한과 abuse detection이 있어야 한다.

## 최종 체크리스트

- [ ] 요구사항 명확화 질문을 functional/non-functional/일관성 3축으로 15개 이상 준비했다.
- [ ] QPS, 저장량, 대역폭을 암산할 수 있는 숫자 블록(10^5초/일, 10^7초/년 등)을 외웠다.
- [ ] Load balancer, API gateway, DB, cache, queue, CDN의 "안 써야 할 때"를 각각 말할 수 있다.
- [ ] Sharding 4가지 전략과 각각의 한계를 설명할 수 있다.
- [ ] Strong / eventual / read-your-writes / monotonic read를 사례와 함께 설명할 수 있다.
- [ ] CAP가 아니라 PACELC로 DB 선택을 정당화할 수 있다.
- [ ] URL shortener를 요구사항→추정→스키마→아키텍처→병목→캐시→rate limit→장애까지 45분 안에 talk-through할 수 있다.
- [ ] Slot 엔진 / RAG 배치 경험을 "결합도 분리", "배치 vs 스트림", "idempotency" 키워드와 각각 연결할 수 있다.
- [ ] 시니어 공통 실수 8가지 각각에 대해 "나는 이렇게 방어한다"는 문장을 만들어 뒀다.
- [ ] 로컬에서 MySQL 8 + Redis + 애플리케이션을 Docker로 띄워 리다이렉트 부하 테스트를 직접 돌려 봤다.
