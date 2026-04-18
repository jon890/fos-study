# [초안] MySQL 복제와 샤딩: 시니어 백엔드 엔지니어를 위한 운영 실전 스터디

## 왜 이 주제가 중요한가

트래픽이 커지는 서비스에서 DB는 가장 먼저 무너지는 레이어다. 애플리케이션 서버는 수평 확장으로 대부분 해결되지만, 상태를 가진 DB는 단순히 인스턴스를 늘린다고 성능이 선형으로 증가하지 않는다. 복제(Replication)와 샤딩(Sharding)은 이 한계를 돌파하는 두 가지 축이다. 복제는 읽기 부하를 여러 노드로 분산시키고 장애 시 복구를 빠르게 만든다. 샤딩은 쓰기 부하와 저장 용량을 물리적으로 분산시킨다.

시니어 백엔드 엔지니어에게 이 주제는 개념 이해만으로 충분하지 않다. "Aurora reader 두 대 붙였는데 왜 1초짜리 lag이 나오고 그게 사용자 불만으로 이어지는가", "샤딩 키를 user_id로 잡았다가 VIP 사용자 한 명 때문에 특정 샤드가 80% 부하를 받는 상황을 어떻게 풀어야 하는가" 같은 실전 문제를 다뤄야 한다. 면접에서도 "트래픽이 늘어나는데 DB가 병목이면 어떻게 접근하시나요"는 거의 고정 질문이며, 여기서 지원자의 운영 경험 깊이가 바로 드러난다.

## MySQL / Aurora 복제 모델 깊이 있게 보기

### Binlog 포맷: statement / row / mixed

MySQL의 복제는 primary가 binlog에 변경 이벤트를 기록하고, replica가 그것을 읽어 재실행하는 구조다. binlog 포맷이 세 가지 있는데 각각 트레이드오프가 명확하다.

- **statement-based (SBR)**: 실행된 SQL 문장 자체를 기록한다. 로그 크기는 작지만 `NOW()`, `UUID()`, `LAST_INSERT_ID()` 같은 비결정적 함수에서 primary와 replica 결과가 달라질 수 있다. `INSERT ... SELECT` 같은 넓은 쿼리도 락 양상이 달라 위험하다.
- **row-based (RBR)**: 변경된 각 row의 before/after 이미지를 기록한다. 정확성은 가장 높지만 대량 UPDATE 시 로그가 폭증한다. 예를 들어 `UPDATE orders SET status='X' WHERE created_at < '2025-01-01'` 이 수천만 row에 걸리면 binlog이 수 GB가 된다.
- **mixed**: 기본적으로 statement, 위험한 경우만 row로 자동 전환. MySQL 8의 기본값에 가깝지만, 운영 표준은 거의 항상 **ROW** 로 고정하는 것이 맞다. Aurora도 `binlog_format=ROW`를 요구하는 기능이 많다.

### GTID: 페일오버의 핵심

GTID(Global Transaction ID)는 각 트랜잭션에 `server_uuid:transaction_id` 형식의 전역 식별자를 붙인다. 기존의 `MASTER_LOG_FILE`/`MASTER_LOG_POS` 기반 복제는 페일오버 시 새 primary의 binlog 좌표를 사람이 계산해야 했는데, GTID가 있으면 replica가 "내가 어디까지 적용했는지"를 UUID:ID 집합으로 알기 때문에 `CHANGE REPLICATION SOURCE TO SOURCE_AUTO_POSITION=1`만으로 정확한 지점부터 이어받는다. 운영 클러스터에서 GTID 없이 MHA나 Orchestrator 기반 자동 페일오버를 돌리는 것은 사실상 불가능하다.

### 반동기 복제 (semi-sync)

일반 비동기 복제는 primary가 커밋을 완료한 뒤 binlog을 전송하므로, primary가 죽으면 아직 전송되지 못한 트랜잭션이 유실된다. 반동기 복제는 "적어도 하나의 replica가 binlog을 디스크의 relay log까지 받았다"는 ACK를 받은 후에 primary가 클라이언트에 성공을 응답한다. 강한 내구성을 주지만 primary 응답 지연은 replica 네트워크 지연만큼 늘어난다. Aurora는 이 모델 대신 스토리지 레이어에서 6-way quorum(4/6 write, 3/6 read)으로 내구성을 처리하므로 semi-sync를 쓰지 않는다.

### Aurora 복제의 특이점

Aurora의 replica는 "binlog 재실행"이 아니라 **공유 스토리지**를 읽는다. writer와 reader가 동일한 스토리지 볼륨을 보며, writer가 페이지를 업데이트하면 reader는 redo log stream을 통해 자기 버퍼풀만 갱신하면 된다. 그래서 Aurora replica lag은 보통 수 ms~수십 ms 수준이고, 장거리 복제나 느린 replica가 writer를 블로킹하지 않는다. 하지만 lag이 0이 아니라는 사실은 반드시 기억해야 한다.

## Read Replica Lag: 실제 원인과 탐지

replica lag이 튀는 이유는 거의 항상 아래 네 가지 중 하나다.

1. **Long running transaction**: primary에서 10분짜리 트랜잭션이 걸리면, binlog 이벤트가 커밋 이후 한꺼번에 쏟아지거나, replica의 SQL thread가 해당 트랜잭션을 재실행하는 동안 뒤의 이벤트들이 밀린다. 특히 단일 스레드 복제(Aurora 이전 MySQL 기본)에서는 치명적이다.
2. **DDL**: `ALTER TABLE` 이 10GB 테이블에 걸리면 replica에서도 같은 시간만큼 SQL thread가 점유된다. MySQL 5.7+ 의 parallel replication을 켜도 같은 스키마의 DDL은 직렬화된다.
3. **Hot row 경합**: 특정 row에 초당 수천 건의 UPDATE가 몰리면, replica는 이것을 단일 스레드로 순차 적용해야 하므로 primary보다 느리게 소화한다.
4. **Purge / Undo 지연**: long tx가 살아있으면 MVCC undo가 purge되지 못하고 쌓여 replica의 쿼리 성능까지 떨어뜨린다.

탐지는 다음을 조합한다.

```sql
-- 전통적인 lag 지표
SHOW REPLICA STATUS\G
-- Seconds_Behind_Source, Replica_SQL_Running_State 확인

-- Aurora의 경우
SELECT AURORA_REPLICA_STATUS();
-- Replica Lag in Milliseconds 값이 실제 체감 lag

-- performance_schema로 heartbeat 기반 추정
SELECT * FROM performance_schema.replication_applier_status_by_worker;
```

CloudWatch의 `AuroraReplicaLag` 지표를 알람으로 걸되, 임계값은 서비스 특성에 맞춰야 한다. 결제 도메인이면 50ms, 일반 커뮤니티 타임라인이면 500ms~1s까지 허용 가능하다.

## Read-After-Write 일관성: Sticky 라우팅 전략

사용자가 게시글을 작성하고 즉시 목록으로 돌아왔는데 자기 글이 안 보이는 상황. replica로 읽기가 가면 lag 때문에 쓰기가 아직 반영되지 않은 것이다. 해결 전략은 실전에서 네 가지가 쓰인다.

1. **Write 직후 일정 시간 sticky**: "방금 쓴 사용자는 5초간 writer로 읽기 라우팅" 하는 방식. 구현이 단순하고 효과가 크다. 보통 `ThreadLocal` 이나 세션 쿠키 + Redis 플래그로 구현한다.
2. **트랜잭션 범위 내 강제 writer 라우팅**: Spring의 `@Transactional(readOnly=false)` 블록은 무조건 writer를 쓴다. 같은 비즈니스 흐름 안에서는 lag 문제가 사라진다.
3. **GTID 기반 일관성 읽기**: 쓰기 후 반환된 GTID를 클라이언트가 들고 있다가 replica에서 `WAIT_FOR_EXECUTED_GTID_SET(gtid, timeout)`을 호출. 정확하지만 레이턴시가 lag 만큼 늘어나 좋은 UX는 아니다.
4. **Aurora Global Database의 managed read replica 엔드포인트**: 리전 내부 lag은 통상 매우 낮으므로 도메인이 허용하면 그대로 쓴다.

실무에서 가장 자주 쓰는 조합은 **(1) + (2)** 다. 간단하면서도 대부분의 read-after-write 사용자 불만을 제거한다.

## 트래픽 라우팅: Proxy / DNS / 앱 레벨 분기

라우팅 방식은 세 레이어에서 선택지가 있다.

### Aurora endpoint + DNS

Aurora는 cluster endpoint(writer), reader endpoint(라운드로빈 읽기), instance endpoint(특정 인스턴스)를 DNS로 제공한다. reader endpoint는 TTL 5초 DNS 기반이라 새 replica가 붙거나 빠져도 빠르게 반영되지만, **DNS 캐싱** 이슈가 있다. JVM의 기본 InetAddress 캐시는 무한이므로 `networkaddress.cache.ttl=30` 같은 설정을 반드시 건드려야 한다.

### Proxy (ProxySQL, RDS Proxy)

애플리케이션은 단일 proxy에 연결하고, proxy가 쿼리 패턴을 보고 writer/reader로 분기한다. `SELECT` 는 reader, `INSERT/UPDATE` 는 writer. 트랜잭션이 열린 동안은 같은 커넥션에 고정된다. RDS Proxy는 연결 풀링까지 묶어주므로 Lambda처럼 커넥션이 폭발하는 워크로드에 유용하다.

### 애플리케이션 레벨 ThreadLocal 분기

Spring의 `AbstractRoutingDataSource`가 대표적이다. `@Transactional(readOnly=true)` 면 reader DataSource를, 그 외에는 writer를 선택한다.

```java
public class ReplicationRoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
            ? "reader" : "writer";
    }
}
```

주의: `readOnly=true` 트랜잭션 안에서 쓰기를 수행하면 hibernate가 flush 하지 않을 뿐 DB는 막지 않는다. 라우팅도 reader로 가버려 실행 자체가 실패한다. 아키텍처 결정이지 버그가 아니므로 코드 리뷰에서 readOnly 플래그를 꼭 본다.

## 파티셔닝 vs 샤딩

| 구분 | 파티셔닝 | 샤딩 |
|---|---|---|
| 레벨 | 단일 DB 인스턴스 내부 | 여러 DB 인스턴스 |
| 목적 | 쿼리 성능, 관리 편의 | 쓰기/용량 수평 확장 |
| 트랜잭션 | 일반 트랜잭션 가능 | 분산 트랜잭션 필요, 보통 포기 |
| 조인 | 자유롭게 가능 | 샤드 간 조인 극도로 비쌈 |

**수직 분할**은 "하나의 큰 테이블이나 DB를 도메인 단위로 쪼갠다". `users`, `orders`, `payments` 를 각각 별도 DB로 분리. 마이크로서비스 분리와 쌍을 이루는 결정이다. **수평 분할(=샤딩)**은 "동일한 스키마를 가진 데이터를 키 기준으로 여러 DB에 나눠 담는다". `user_id % 16` 으로 16개 샤드에 분산.

의사결정은 보통 순서가 있다. 먼저 인덱스/쿼리 튜닝 → 읽기는 replica 분산 → 수직 분할(도메인 분리) → 그래도 단일 DB 쓰기가 버티지 못하면 수평 샤딩. 샤딩은 마지막 옵션이다. 한 번 샤딩하면 롤백 비용이 엄청나고, 조인·트랜잭션·유니크 제약·글로벌 시퀀스·리포팅 쿼리 전부가 복잡해진다.

## 샤딩 키 선택

### 카디널리티

`country_code` 같은 낮은 카디널리티 컬럼을 샤딩 키로 쓰면 안 된다. 샤드 수만큼 분산되지 않고 몇 개 샤드에 뭉친다. `user_id`, `tenant_id`, `order_id` 처럼 값의 종류가 충분히 많은 컬럼을 택한다.

### 핫스팟

B2B SaaS에서 `tenant_id` 로 샤딩하면, 특정 대형 고객 하나가 단일 샤드를 독점할 수 있다. 탐지 방법: 주기적으로 각 샤드의 QPS/row count/bytes를 대시보드화한다. 대응: (a) 핫 샤드 분리 이관 (b) 해당 tenant를 composite key `(tenant_id, user_id)` 기반 sub-shard로 다시 쪼개기.

### 재샤딩 비용

modulo 방식(`key % N`)은 N이 바뀌는 순간 거의 모든 데이터가 이동한다. **consistent hashing** 을 쓰면 샤드 추가/제거 시 평균 1/N 만큼만 이동한다. 구현 복잡도는 약간 올라가지만 운영 유연성이 크게 오른다. Vitess, Cassandra가 이 방식이다.

### 예시: 주문 테이블

- 나쁜 선택: `created_at` (시간 기반 → 최신 샤드만 핫)
- 나쁜 선택: `status` (카디널리티 극히 낮음)
- 합리적 선택: `user_id` (조회 패턴이 "내 주문 보기" 위주일 때)
- 더 나은 선택: `(user_id, created_at)` composite + consistent hashing

## HikariCP 튜닝

커넥션 풀 설정이 잘못되면 DB가 멀쩡해도 앱이 죽는다.

### maximumPoolSize 계산

공식: `pool_size = Tn * (Cm - 1) + 1` (T=스레드 수, Cm=스레드당 동시 커넥션) 은 참고용일 뿐이고, 실무에선 **DB의 max_connections 한도를 인스턴스 수로 나눈 값** 에서 역산한다.

예: RDS의 `max_connections=1000`, 앱 서버 20대 → 서버당 최대 50, 안전 마진 포함해 **30~40** 을 상한. 이보다 크게 잡으면 피크 시 DB가 커넥션을 거부한다.

많이들 오해하는 부분: pool size를 키우면 성능이 좋아질 것 같지만 실제로는 **작게** 잡는 쪽이 대부분 더 빠르다. DB CPU가 유한하므로 동시 active 쿼리를 줄이면 각각의 응답 시간이 줄고 throughput 이 오른다. HikariCP 공식 권고도 "작게 시작해서 지표 보고 늘려라" 다.

### 타임아웃 조합

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 30
      minimum-idle: 10
      connection-timeout: 3000      # 풀에서 대기 최대 3초
      idle-timeout: 600000          # 10분 유휴 시 반납
      max-lifetime: 1800000         # 30분 후 강제 재생성 (DB wait_timeout보다 작게)
      leak-detection-threshold: 60000  # 1분 이상 빌려간 커넥션은 로그 경고
      validation-timeout: 2000
      keepalive-time: 120000
```

- `max-lifetime` 은 반드시 DB의 `wait_timeout` 보다 짧아야 한다. 그렇지 않으면 DB가 먼저 끊은 좀비 커넥션을 앱이 잡아 "Communications link failure" 가 난다.
- `leak-detection-threshold` 는 운영에서 필수. 트랜잭션 누수(커넥션 반납 안 됨)를 조기에 잡는다.

### 커넥션 누수 탐지 실전

- HikariCP의 `leakDetectionThreshold` 로그 → 스택 트레이스에서 누수 코드 추적.
- `SHOW PROCESSLIST` 로 "Sleep 상태가 수 시간인 커넥션" 식별.
- APM(Scouter, DataDog, Pinpoint)에서 "connection hold time" 지표 상위 API 조사.

## Slow Query 실전 분석 파이프라인

1단계: slow log 켜기.

```sql
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
SET GLOBAL log_queries_not_using_indexes = 'ON';
```

2단계: `pt-query-digest` 로 주기적 집계.

```bash
pt-query-digest /var/log/mysql/slow.log > digest-$(date +%F).txt
```

결과에서 "총 실행 시간 상위 쿼리", "평균 응답 시간 상위 쿼리" 두 랭킹을 본다. 둘이 다르다.

3단계: `EXPLAIN` 또는 `EXPLAIN ANALYZE`.

```sql
EXPLAIN ANALYZE
SELECT * FROM orders
WHERE user_id = 1234 AND status = 'PAID'
ORDER BY created_at DESC LIMIT 20;
```

`type=ALL`, `rows=수백만`, `Using filesort` 가 보이면 인덱스 설계 잘못이다.

4단계: 인덱스 보강.

```sql
ALTER TABLE orders ADD INDEX idx_user_status_created (user_id, status, created_at DESC);
```

복합 인덱스 순서는 카디널리티가 아니라 **WHERE 등가 조건 → range 조건 → ORDER BY** 순서로 설계한다.

## DDL 변경의 운영 위험

MySQL 8의 online DDL은 대부분의 `ADD COLUMN`, `ADD INDEX`를 online 으로 처리하지만 한계가 있다.

- 테이블 rebuild 가 필요한 DDL (`ALTER COLUMN ... MODIFY`, PK 변경)은 내부적으로 카피가 일어나 디스크 2배 필요.
- metadata lock 이 long tx와 부딪히면 DDL 전체가 대기.
- Aurora는 일부 DDL이 binlog replication 없이 스토리지 레이어에서 처리되지만 여전히 write 블로킹 구간이 존재.

대형 테이블은 **pt-online-schema-change** 또는 **gh-ost** 를 쓴다.
- pt-osc: 트리거 기반. 새 테이블을 만들고 트리거로 변경을 복제, 백필 후 rename. 트리거 overhead 가 있음.
- gh-ost: binlog 기반. 트리거를 쓰지 않아 primary 부담이 적고, 이동 속도를 동적 제어 가능(throttle). GitHub가 밀어붙인 이유가 있다.

둘 다 **작업 전 반드시 foreign key 유무와 replica lag 기준 throttle 조건**을 점검한다.

## 백업 / PITR / Binlog 보존

- Aurora: 자동 연속 백업이 기본. PITR 윈도우는 1~35일. snapshot은 별도 보존.
- MySQL on EC2/RDS: 물리 백업은 Percona XtraBackup, 논리 백업은 `mysqldump`/`mysqlpump`. 복구 시간은 물리 백업이 훨씬 빠르다.
- Binlog 보존 기간(`binlog_expire_logs_seconds`): 최소 PITR 목표 시간 + 여유. 너무 짧으면 복구 불가, 너무 길면 디스크 폭발.
- 복구 리허설을 분기별로 1회라도 해야 한다. "백업은 있는데 복구는 한 번도 안 해봤다" 는 실제로 사고 난다.

## 로컬 실습 환경

Docker compose 로 1 primary + 2 replica를 세운다.

```yaml
version: '3.8'
services:
  mysql-primary:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
    command: >
      --server-id=1
      --log-bin=mysql-bin
      --binlog-format=ROW
      --gtid-mode=ON
      --enforce-gtid-consistency=ON
    ports: ["3306:3306"]

  mysql-replica-1:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
    command: >
      --server-id=2
      --log-bin=mysql-bin
      --binlog-format=ROW
      --gtid-mode=ON
      --enforce-gtid-consistency=ON
      --read-only=ON
    ports: ["3307:3306"]
```

복제 설정:

```sql
-- primary에서
CREATE USER 'repl'@'%' IDENTIFIED BY 'replpass';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';

-- replica에서
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='mysql-primary',
  SOURCE_USER='repl',
  SOURCE_PASSWORD='replpass',
  SOURCE_AUTO_POSITION=1;
START REPLICA;
SHOW REPLICA STATUS\G
```

이후 primary에 INSERT 후 replica에서 SELECT로 확인하고, primary에서 `SELECT SLEEP(10), ...` 같은 long tx를 걸어 `Seconds_Behind_Source` 가 올라가는 것을 관찰한다.

## 나쁜 예 vs 개선된 예

### 나쁜 예: 라우팅 없이 모든 쿼리 writer로

```java
@Service
public class FeedService {
    public List<Post> timeline(Long userId) {
        return postRepository.findRecent(userId, 50);
    }
}
```

설정 파일에 writer DataSource 하나만 등록되어 있다. 트래픽이 늘면 writer CPU가 100% 로 박힌다.

### 개선된 예

```java
@Service
@Transactional(readOnly = true)
public class FeedService {
    public List<Post> timeline(Long userId) {
        return postRepository.findRecent(userId, 50);
    }

    @Transactional
    public void writePost(Long userId, String content) {
        postRepository.save(new Post(userId, content));
        stickyRouter.markWriterSticky(userId, Duration.ofSeconds(5));
    }
}
```

`@Transactional(readOnly=true)` 로 읽기는 reader DataSource, 쓰기 직후 5초간 해당 사용자는 writer로 고정.

### 나쁜 예: 샤딩 키로 created_at

```sql
-- shard 번호 = DATE_FORMAT(created_at, '%Y%m') % 8
```

최신 달이 들어있는 샤드 한 개가 모든 쓰기를 받는다.

### 개선된 예

```sql
-- shard 번호 = consistent_hash(user_id) over ring of 64 virtual nodes
```

## 실수 패턴 정리

- replica에 쓰기 쿼리가 흘러가 `ER_OPTION_PREVENTS_STATEMENT` 로 장애 경보.
- `@Transactional` 누락으로 읽기가 writer로 가서 writer 부하 집중.
- modulo 샤딩 후 "샤드 하나 추가"가 불가능해 전체 재이관 프로젝트 발생.
- HikariCP max-lifetime > DB wait_timeout → 주기적 "Communications link failure".
- Aurora reader endpoint를 JVM 기본 DNS 캐시로 물고 있다가 replica 교체 후 한참 동안 죽은 엔드포인트 호출.

## 면접 답변 프레이밍

### "트래픽이 늘어나는데 DB가 병목이면 어떻게 접근하시나요"

먼저 어떤 병목인지 분리합니다. CPU, IOPS, 커넥션, 락 중 무엇인지 RDS Performance Insights와 slow log로 측정합니다. 읽기 부하면 인덱스/쿼리 튜닝이 우선입니다. `pt-query-digest` 로 상위 쿼리를 잡아 `EXPLAIN` 하고 복합 인덱스를 설계합니다. 그래도 부족하면 read replica를 추가해 `@Transactional(readOnly=true)` 기반 라우팅을 적용합니다. 쓰기가 병목이면 접근이 달라집니다. 먼저 도메인 단위 수직 분할로 DB를 쪼갭니다. 이것으로도 버티지 못할 때 수평 샤딩을 검토합니다. 샤딩은 되돌리기 어려우므로 consistent hashing 과 샤딩 키 카디널리티/핫스팟 분석을 선행하고, 애플리케이션의 트랜잭션 경계가 샤드 내부에 한정되도록 도메인을 재설계합니다. 이 모든 단계에서 커넥션 풀(HikariCP max-lifetime 과 DB wait_timeout 의 정합), DDL 위험(gh-ost), 백업/PITR 같은 운영 안전장치는 함께 점검합니다.

### "replica lag 이 1초 이상 튀는 원인을 어떻게 조사하시나요"

primary에서 long transaction 과 DDL을 먼저 확인합니다. `information_schema.innodb_trx` 와 `SHOW FULL PROCESSLIST` 로 오래 열린 트랜잭션을 찾습니다. replica 쪽에서는 `SHOW REPLICA STATUS` 의 `Replica_SQL_Running_State`, Aurora라면 `AURORA_REPLICA_STATUS()` 의 lag ms 값과 `performance_schema.replication_applier_status_by_worker` 를 봅니다. hot row 경합이 의심되면 같은 PK에 몰리는 UPDATE 빈도를 APM으로 확인합니다. 그 다음 조치는 원인별로 다릅니다. long tx는 타임아웃 정책과 코드 레벨 트랜잭션 범위 축소, DDL은 gh-ost 로 교체, hot row는 캐시 레이어로 쓰기 빈도 낮추기, purge 지연은 undo log 크기와 history list length 를 함께 모니터링합니다.

## 체크리스트

- [ ] `binlog_format=ROW`, `gtid_mode=ON`, `enforce_gtid_consistency=ON` 인가
- [ ] 반동기 복제 필요성/허용 지연을 도메인별로 합의했는가
- [ ] replica lag 알람이 도메인별 허용치로 분리되어 있는가
- [ ] read-after-write 경로에 sticky 전략이 있는가
- [ ] `@Transactional(readOnly=true)` 가 읽기 서비스 메서드에 일관되게 붙어 있는가
- [ ] JVM `networkaddress.cache.ttl` 이 DNS TTL 수준으로 설정되어 있는가
- [ ] HikariCP `max-lifetime` < DB `wait_timeout` 인가
- [ ] `leak-detection-threshold` 가 운영 환경에서 활성화되어 있는가
- [ ] slow log + pt-query-digest 리포트가 주간으로 생성되는가
- [ ] 대형 테이블 DDL 시 gh-ost/pt-osc 표준 절차가 문서화되어 있는가
- [ ] binlog 보존 기간이 PITR 목표 시간을 덮는가
- [ ] 복구 리허설을 분기 1회 이상 수행했는가
- [ ] 샤딩 도입 전 수직 분할 옵션을 검토했는가
- [ ] 샤딩 키의 카디널리티와 핫스팟 시나리오를 데이터로 검증했는가
- [ ] consistent hashing 기반 샤드 추가/제거 플랜이 있는가
