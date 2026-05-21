# [초안] MySQL 복제와 페일오버 심화: 운영 관점 deep-dive

> 이 문서는 [`replication-sharding.md`](./replication-sharding.md)의 후속 deep-dive다. binlog 포맷, GTID 개요, replica lag 원인 같은 기본 개념은 그 hub 문서에서 다루고, 여기서는 **장애 시 어떻게 primary가 바뀌고 트래픽이 끊김 없이 이어지는가**라는 한 가지 축만 깊게 본다.

## 왜 이 주제가 시니어 면접에서 갈리는가

읽기 부하 분산은 인덱스 + read replica + `@Transactional(readOnly=true)` 조합으로 대부분 해결된다. 진짜 시험대는 **primary가 죽었을 때 무슨 일이 일어나는가**다. 이 질문이 깊은 이유는 단순히 "다른 노드로 트래픽이 넘어간다"가 아니라, 그 사이에 발생할 수 있는 데이터 유실(RPO), 서비스 가용성 단절(RTO), 잘못 살아남은 트랜잭션(errant transaction), 클라이언트 커넥션 stuck, 두 노드가 동시에 쓰기를 받는 split-brain까지 전부 트레이드오프 관계로 묶여 있기 때문이다.

면접관이 "Aurora의 페일오버는 보통 몇 초가 걸리고 그동안 클라이언트가 무엇을 하나요"라고 묻는 이유는 단편적인 숫자를 듣고 싶어서가 아니라, 그 30~60초가 **DNS TTL + 클러스터 컨센서스 + 클라이언트 reconnect + 인플라이트 트랜잭션 처리**의 합성이라는 것을 후보자가 분해해서 말할 수 있는지를 본다.

## RPO와 RTO를 복제 모델로 환산하기

페일오버 설계는 항상 두 숫자에서 출발한다.

- **RPO**(Recovery Point Objective): "최대 얼마만큼의 최근 데이터까지 잃어도 되는가." 0초면 무손실, 5초면 마지막 5초 트랜잭션 유실 허용.
- **RTO**(Recovery Time Objective): "장애 발생부터 정상 서비스 복귀까지 얼마나 걸려도 되는가." 30초인지 5분인지 30분인지.

복제 모델별 현실:

| 모델 | 이론적 RPO | 실제 RTO | 비고 |
|---|---|---|---|
| 비동기 binlog 복제 | replica lag만큼 (0초가 아님) | promotion 수동 시 분 단위 | 가장 흔하지만 무손실 아님 |
| 반동기 복제(semi-sync) | 0초에 근접 (ACK 받은 트랜잭션은 보존) | 보통 30~60초 | primary 응답 지연 trade |
| Aurora 6-way quorum | 사실상 0초 (스토리지 레이어 합의) | 30~60초 (DNS + reconnect) | 단일 region 가정 |
| Aurora Global Database | 보조 region까지 < 1초 | 1~2분 (region promotion) | 멀티 region DR |

면접에서 자주 받는 함정 질문: "비동기 복제로도 데이터 유실 0이 보장되나요?" 답은 No. binlog이 replica에 도착하기 전에 primary 스토리지가 날아가면 그 트랜잭션은 사라진다. semi-sync 도 "binlog이 replica의 relay log에 디스크 fsync 되었음을 ACK" 받는 것이지 "replica가 실제로 SQL을 재실행했음을 보장"하는 것이 아니다. 그래서 lossless semi-sync(`AFTER_SYNC`)와 일반 semi-sync(`AFTER_COMMIT`)의 차이를 구분해야 한다.

## 페일오버는 단일 동작이 아니라 4단계 상태 머신이다

면접 답변의 핵심 골격은 다음 네 단계다.

1. **Detect**: primary가 죽었다는 사실을 누가, 어떻게 판정하는가
2. **Fence**: 죽은 primary가 좀비로 살아나서 쓰기를 다시 받지 못하게 차단
3. **Promote**: 어느 replica를 새 primary로 올릴지 선택하고 read-write로 전환
4. **Reroute**: 클라이언트 트래픽을 새 primary로 이동

각 단계가 독립적으로 실패할 수 있다는 점이 중요하다. detect는 잘 됐는데 fence가 안 되어 split-brain이 발생하거나, promote는 끝났는데 클라이언트 DNS 캐시 때문에 reroute가 안 되는 경우가 실제 운영에서 가장 자주 발생한다.

### Detect: 다수결과 false positive 방지

primary가 죽었다는 판정은 단일 모니터의 한 번 ping 실패로 내리면 안 된다. 네트워크 일시 단절, GC long pause, 디스크 IO 멈춤 같은 일시적 현상도 ping 실패로 보이기 때문이다. 운영에서 쓰는 방법:

- **다중 모니터 합의**: Orchestrator는 여러 zone의 raft 노드들이 각각 primary 상태를 관측하고, 다수가 "unreachable + not replicating from anywhere reasonable"로 합의해야 페일오버 트리거.
- **Replication topology check**: primary가 죽었는지, replica의 IO thread만 끊긴 건지, 네트워크 파티션 한쪽인지를 구분. 단순 TCP ping이 아니라 "다른 replica가 이 primary에서 binlog을 받고 있는가"도 같이 본다.
- **Aurora 내부**: writer 인스턴스의 health check가 연속 3회 실패 + storage layer의 quorum 응답이 정상이면 페일오버 트리거. 클러스터 자체가 6-way quorum 위에 있어서 detect는 빠른 편.

### Fence: 좀비 primary 차단

가장 위험한 시나리오. primary가 죽은 줄 알았는데 사실 네트워크 파티션이었고, 페일오버 후에 원래 primary가 돌아와서 자기는 여전히 read-write라고 믿는 상태. 두 노드가 동시에 쓰기를 받으면 데이터가 갈라진다(split-brain). Fence 방법:

- **STONITH**(Shoot The Other Node In The Head): 페일오버 직전에 옛 primary의 인스턴스를 강제 종료 또는 네트워크 차단. AWS 환경에서는 security group을 갈아치우거나 ENI를 분리.
- **Application-level fencing token**: 모든 쓰기에 epoch 번호를 붙이고, 새 primary는 더 큰 epoch만 받음. 옛 primary가 살아 돌아와도 클라이언트가 작은 epoch 토큰을 보내면 거부.
- **Quorum 기반**: Aurora처럼 스토리지 레이어가 quorum이면 옛 writer가 살아 돌아와도 쓰기를 commit 할 수 없음(과반 ACK를 받지 못함).

### Promote: 어느 replica를 새 primary로

여러 replica가 있을 때 선택 기준:

- **가장 최신 GTID를 가진 replica**: 데이터 유실을 최소화. Orchestrator의 기본 정책.
- **사전 지정된 우선순위**: Aurora의 `failover priority tier`(0~15). 일부 인스턴스를 reporting 전용으로 만들고 페일오버 후보에서 제외하고 싶을 때.
- **AZ 동일성**: 같은 AZ의 replica를 우선해 네트워크 지연 최소화.

Promote 자체는 빠르다(수 초). 다만 promote 직전에 **나머지 replica들 사이의 GTID 차이를 메우는 단계**가 있다. 예를 들어 primary가 GTID 100까지 발행했지만 replica A는 98, replica B는 100까지 받았다면, A를 promote하기 전에 B에서 99, 100 트랜잭션을 가져와야 한다. 이 catch-up이 lag이 컸던 만큼 시간을 잡아먹는다.

### Reroute: DNS, proxy, 클라이언트 캐시

새 primary로 트래픽을 보내는 방법:

- **DNS CNAME 갱신**: Aurora cluster endpoint가 새 writer로 CNAME 변경. 단, JVM의 `networkaddress.cache.ttl`이 기본값(infinity)이면 새 IP를 영영 안 본다.
- **Proxy 갱신**: RDS Proxy / ProxySQL이 새 writer를 자동 감지. 클라이언트는 단일 endpoint 유지.
- **Aurora JDBC Wrapper**(aws-mysql-jdbc / aws-advanced-jdbc-wrapper): 클러스터 토폴로지를 클라이언트가 알고 있어서 DNS 의존 없이 새 writer를 찾아간다. failover 평균 시간이 30초 → 7~10초로 단축.

## GTID continuity와 errant transaction

GTID 기반 복제에서 가장 함정인 운영 이슈가 **errant transaction**이다.

상황 시나리오:
1. primary는 A, replica는 B, C.
2. 누군가가 운영 사고로 replica B에 직접 `INSERT`를 실행. B에서만 존재하는 GTID `<B의 UUID>:5`가 생긴다.
3. primary A가 죽고 B가 새 primary로 promote된다.
4. C가 B에 붙으려는 순간, C에게는 없고 B에게만 있는 GTID `<B>:5`를 적용해야 한다. 일반 복제 트랜잭션이 아니므로 C는 충돌 가능성을 보고 replication을 멈춘다.

방어 방법:

- 모든 replica에 `super_read_only=ON` 설정. root조차 쓰기 불가.
- 페일오버 전에 `pt-slave-find` 또는 Orchestrator UI로 errant GTID 존재 여부 확인.
- 발견 시 inject empty transaction으로 supersede 또는 dump/reload로 강제 정합.

```sql
-- 클러스터 전체에서 각 노드의 GTID 집합 확인
SELECT @@global.gtid_executed;

-- errant transaction이 있다면 다른 노드에 empty transaction 주입
SET GTID_NEXT='<B-UUID>:5';
BEGIN; COMMIT;
SET GTID_NEXT='AUTOMATIC';
```

면접에서 "GTID는 페일오버를 어떻게 쉽게 만드나요"에 답할 때는 자동 좌표 추적 + errant transaction 위험 둘을 같이 말해야 깊이가 드러난다.

## Aurora 클러스터 페일오버: 30~60초의 내부 분해

Aurora가 광고하는 "60초 이하 페일오버"가 실제 어떻게 구성되는지:

| 구간 | 소요 시간 | 무슨 일이 일어나는가 |
|---|---|---|
| Failure detection | 5~15초 | health check 연속 실패 누적, quorum confirmation |
| Cluster decision | 1~3초 | RDS control plane이 어느 replica를 promote할지 선정 |
| Promotion | 1~2초 | 선택된 replica가 writer 역할로 전환 (스토리지 공유라 catch-up 불필요) |
| DNS update | 5~30초 | cluster endpoint의 CNAME 갱신, TTL 5초지만 클라이언트 캐시는 별개 |
| Client reconnect | 1~10초 | 기존 커넥션 끊김, 풀이 새 endpoint 해석 후 재연결 |

이 분해를 알고 있으면 "왜 우리 서비스는 페일오버가 2분 걸리나요"라는 질문에 정확히 답할 수 있다. 대부분의 경우 promotion 자체가 아니라 **클라이언트 DNS 캐시 + HikariCP 풀의 idle 커넥션 cleanup 지연**이 범인이다.

`-Dnetworkaddress.cache.ttl=10` 같은 JVM 옵션 또는 `aws-advanced-jdbc-wrapper` 도입으로 이 시간이 크게 줄어든다.

## 클라이언트 reconnect: 인플라이트 트랜잭션은 어떻게 되는가

페일오버 순간 중간에 떠 있던 트랜잭션은 어떻게 되는가? 짧게 답하면 **롤백된다**. 옛 primary의 InnoDB는 죽었거나 강등됐고, undo log의 일부만 replica로 넘어왔을 가능성이 있다. 새 primary는 마지막 커밋된 상태만 보장한다.

애플리케이션 코드 관점에서 처리해야 할 패턴:

```java
@Retryable(
    value = { SQLTransientConnectionException.class, CommunicationsException.class },
    maxAttempts = 3,
    backoff = @Backoff(delay = 500, multiplier = 2)
)
@Transactional
public void chargePoint(Long userId, BigDecimal amount) {
    Account acc = accountRepository.findByUserIdForUpdate(userId);
    acc.charge(amount);
    pointLedgerRepository.save(PointLedger.charged(userId, amount));
}
```

주의: **자동 재시도가 멱등하지 않은 작업에 걸리면 중복 결제가 난다**. retry 가능한 예외는 connection 단계 실패(아예 DB에 도달 못함)만으로 좁히고, "commit을 보냈는데 응답이 안 옴" 상태는 별도의 멱등 키 + 결과 조회로 처리해야 한다. 결제 도메인에서는 idempotency key를 트랜잭션 entry로 박는 패턴이 표준.

JDBC 드라이버 관점:

- **mysql-connector-j**: `failoverReadOnly=false`, `secondsBeforeRetryMaster`, `autoReconnect=true` 같은 옵션이 있지만 silent reconnect는 인플라이트 트랜잭션 손실을 숨기므로 비권장.
- **aws-advanced-jdbc-wrapper**: cluster topology를 알고 있어서 페일오버를 감지하면 명시적 예외를 던지고 새 writer로 재연결. 트랜잭션 손실은 애플리케이션이 명시적으로 핸들.

## Split-brain 실제 사례 패턴

운영에서 split-brain이 발생하는 전형적 경로:

1. AZ-a의 primary가 AZ-b의 네트워크와 일시 단절. 모니터가 "primary unreachable"로 판정.
2. AZ-b의 replica가 promote되어 새 writer가 됨.
3. 그 사이 AZ-a의 옛 primary는 자기 zone 내부에서는 여전히 reachable이라 클라이언트 일부가 옛 primary에 계속 쓰기를 보냄.
4. 네트워크 복구 후 두 노드의 binlog이 갈라진 상태로 발견.

방어 체크리스트:

- 페일오버 시 옛 primary를 즉시 `super_read_only=ON` 또는 네트워크 차단.
- 클라이언트 endpoint를 cluster endpoint(DNS 기반)로 통일하고 instance endpoint 하드코딩 금지.
- Aurora 같은 quorum 스토리지를 쓰면 자연스럽게 차단(과반 ACK 불가).

## Planned switchover: graceful drain 절차

장애 페일오버는 어쩔 수 없는 손실을 동반하지만, 계획된 switchover(버전 업그레이드, 인스턴스 타입 변경)는 무손실로 처리할 수 있다. 표준 절차:

1. 새 primary 후보 replica의 lag을 0으로 수렴시킴 (트래픽 일부 차단 또는 일시 정지).
2. 옛 primary를 `read_only=ON`으로 전환. 신규 쓰기 차단, 인플라이트 트랜잭션만 마무리.
3. 옛 primary의 binlog이 replica에 100% 전달되었는지 GTID로 확인.
4. 새 primary 후보를 `read_only=OFF`로 전환.
5. Endpoint를 새 primary로 갱신.
6. 클라이언트 커넥션 풀이 새 primary로 reconnect.

Aurora에서는 콘솔 또는 CLI의 `failover-db-cluster` 명령으로 이 흐름이 한 번에 처리된다. 다만 운영팀은 어느 시점에 클라이언트가 일시적으로 `ER_OPTION_PREVENTS_STATEMENT`를 받을 수 있는지 알고 있어야 한다. 그 짧은 윈도우에서 재시도가 안 되는 API는 5xx로 노출된다.

## 나쁜 예 vs 개선된 예

### 나쁜 예: 페일오버 후 좀비 커넥션이 영영 남음

```java
@Configuration
public class DataSourceConfig {
    @Bean
    public DataSource dataSource() {
        HikariConfig cfg = new HikariConfig();
        cfg.setJdbcUrl("jdbc:mysql://my-cluster.cluster-xxx.rds.amazonaws.com:3306/app");
        cfg.setMaximumPoolSize(50);
        return new HikariDataSource(cfg);
    }
}
```

JVM 기본 DNS 캐시가 무한이라 옛 primary 인스턴스 IP를 풀이 영영 들고 있는다. 페일오버 후에도 풀은 죽은 인스턴스로 쿼리를 시도한다.

### 개선된 예

```java
// JVM 시작 옵션 또는 main에서
java.security.Security.setProperty("networkaddress.cache.ttl", "10");
java.security.Security.setProperty("networkaddress.cache.negative.ttl", "5");

// HikariCP 설정
cfg.setMaxLifetime(Duration.ofMinutes(30).toMillis());
cfg.setKeepaliveTime(Duration.ofMinutes(2).toMillis());
cfg.setValidationTimeout(Duration.ofSeconds(2).toMillis());
cfg.setConnectionTestQuery("SELECT 1");
```

추가로 가능하면 `aws-advanced-jdbc-wrapper`로 교체:

```text
jdbc:aws-wrapper:mysql://my-cluster.cluster-xxx.rds.amazonaws.com:3306/app
```

이 wrapper는 클러스터 토폴로지를 알고 있어서 DNS에 의존하지 않고 새 writer로 즉시 reconnect한다.

### 나쁜 예: 페일오버 자동 재시도가 결제를 중복 처리

```java
@Retryable(maxAttempts = 5)
@Transactional
public void chargeCard(Long userId, BigDecimal amount) {
    paymentGateway.charge(userId, amount); // 외부 PG 호출
    pointRepository.deduct(userId, amount);
}
```

페일오버 순간 PG 호출은 성공했는데 DB commit 응답이 안 와서 retry가 돌면, PG에 두 번 결제가 찍힌다.

### 개선된 예

```java
public void chargeCard(Long userId, BigDecimal amount, String idempotencyKey) {
    // 1. 멱등 키로 결과 조회 - 이미 처리됐다면 그대로 반환
    if (paymentIdempotencyRepository.exists(idempotencyKey)) {
        return; // 또는 기존 결과 반환
    }
    // 2. 멱등 키 선저장 - unique 제약으로 중복 차단
    paymentIdempotencyRepository.reserve(idempotencyKey, userId, amount);
    // 3. 외부 호출 + DB 처리
    paymentGateway.charge(userId, amount, idempotencyKey);
    pointRepository.deduct(userId, amount);
    // 4. 멱등 키 confirm
    paymentIdempotencyRepository.confirm(idempotencyKey);
}
```

PG 자체도 같은 idempotency key를 받으면 동일 결과를 반환하도록 약속.

## 로컬 실습: semi-sync + 수동 promotion

[`replication-sharding.md`](replication-sharding.md)의 docker-compose 위에 semi-sync를 얹고 수동 페일오버를 흉내내 본다.

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
      --rpl-semi-sync-master-enabled=1
      --rpl-semi-sync-master-timeout=1000
    ports: ["3306:3306"]

  mysql-replica:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
    command: >
      --server-id=2
      --log-bin=mysql-bin
      --binlog-format=ROW
      --gtid-mode=ON
      --enforce-gtid-consistency=ON
      --rpl-semi-sync-slave-enabled=1
      --super-read-only=ON
    ports: ["3307:3306"]
```

semi-sync 플러그인 로드:

```sql
-- primary
INSTALL PLUGIN rpl_semi_sync_source SONAME 'semisync_source.so';
SET GLOBAL rpl_semi_sync_source_enabled = 1;

-- replica
INSTALL PLUGIN rpl_semi_sync_replica SONAME 'semisync_replica.so';
SET GLOBAL rpl_semi_sync_replica_enabled = 1;
STOP REPLICA IO_THREAD;
START REPLICA IO_THREAD;
```

페일오버 실습:

```bash
# 1. primary에 트래픽 발생
docker exec -it mysql-primary mysql -uroot -proot -e \
  "USE test; INSERT INTO logs(msg) VALUES('before failover');"

# 2. primary를 강제 종료
docker stop mysql-primary

# 3. replica를 promote
docker exec -it mysql-replica mysql -uroot -proot -e \
  "STOP REPLICA; RESET REPLICA ALL; SET GLOBAL super_read_only=OFF; SET GLOBAL read_only=OFF;"

# 4. 새 primary에 쓰기 확인
docker exec -it mysql-replica mysql -uroot -proot -e \
  "USE test; INSERT INTO logs(msg) VALUES('after failover');"

# 5. 옛 primary 부활 시 errant transaction 점검
docker start mysql-primary
docker exec -it mysql-primary mysql -uroot -proot -e \
  "SELECT @@global.gtid_executed;"
```

5단계에서 두 노드의 GTID 집합을 비교하면 errant transaction이 어떻게 보이는지 직접 관찰 가능하다.

## 실수 패턴 정리

- `autoReconnect=true`만 믿고 인플라이트 트랜잭션 처리 코드를 빼먹음 → 페일오버 시 silent partial commit.
- JVM `networkaddress.cache.ttl`을 만지지 않아 페일오버 후 5분+ 옛 IP 사용.
- replica에서 root로 직접 INSERT한 데이터 → errant transaction → 다음 페일오버에서 복제 중단.
- semi-sync timeout이 너무 짧아 replica 일시 지연 시 자동으로 비동기로 떨어지는 것을 인지하지 못함.
- 페일오버 후 새 primary의 binlog 보존 정책을 옛 primary와 다르게 설정해 PITR 윈도우가 어긋남.
- planned switchover에서 옛 primary를 `read_only=ON`으로 바꾸기 전에 endpoint를 옮겨 트래픽 손실 발생.
- Aurora `failover priority tier`를 설정하지 않아 reporting 전용 인스턴스가 writer로 승격.
- 결제/포인트 같은 비멱등 API에 `@Retryable`을 묻지마 부착 → 중복 처리.

## 면접 답변 프레이밍

### "MySQL primary가 죽었을 때 페일오버는 내부적으로 어떻게 진행되나요"

페일오버는 단일 동작이 아니라 detect, fence, promote, reroute 네 단계로 분해해서 이해합니다. detect는 단일 ping 실패가 아니라 다중 모니터의 합의로 판정해야 false positive를 피할 수 있습니다. fence는 옛 primary가 좀비로 살아 돌아와 split-brain을 만들지 못하게 차단하는 단계로, STONITH나 quorum 스토리지가 대표적입니다. promote는 가장 최신 GTID를 가진 replica를 선택하고 read-write로 전환하며, 이 직전에 다른 replica들과의 GTID 격차를 메우는 catch-up이 가장 시간을 잡아먹습니다. reroute는 DNS, proxy, JDBC wrapper 중 어느 레이어에서 트래픽을 옮기는지 결정합니다. 운영에서는 promote 자체보다 클라이언트의 DNS 캐시와 커넥션 풀의 cleanup이 RTO를 결정짓는 경우가 더 많아서 JVM `networkaddress.cache.ttl` 같은 설정이나 aws-advanced-jdbc-wrapper 도입이 표준 대응입니다.

### "비동기 복제로 무손실 페일오버가 가능한가요"

원칙적으로 불가능합니다. binlog이 replica에 도달하기 전에 primary 스토리지가 손상되면 그 트랜잭션은 사라집니다. 무손실에 가까우려면 semi-sync, 그것도 `AFTER_SYNC` 모드를 써서 적어도 한 replica가 relay log에 fsync한 후에만 클라이언트에 success를 반환하도록 해야 합니다. 그래도 SQL thread가 실제로 재실행한 것을 보장하지는 않습니다. 진짜 무손실에 가까운 것은 Aurora의 6-way quorum이나 Spanner류 합의 기반 스토리지입니다. 면접에서는 도메인의 RPO 허용치를 먼저 정하고, 그 숫자가 0초에 가까울수록 비용과 응답 지연 trade-off를 받아들여야 한다는 흐름으로 답하면 됩니다.

### "페일오버 직후 결제 API에서 가끔 중복 결제가 발생합니다. 원인과 대응은요"

페일오버 순간 클라이언트는 commit을 보냈는데 응답을 못 받은 상태가 됩니다. 이 때 `@Retryable`이나 드라이버의 `autoReconnect=true`가 묻지마 재시도하면, 외부 PG가 이미 결제를 받은 상태에서 한 번 더 호출되어 중복 결제가 발생합니다. 해결은 두 레벨입니다. 첫째, 재시도 대상 예외를 connection establishment 실패로만 좁히고 "commit 보냈는데 응답 없음" 상태는 별도로 처리합니다. 둘째, 결제 같은 비멱등 API에는 idempotency key를 표준으로 박고, 같은 키로 두 번째 호출이 오면 기존 결과를 반환하도록 PG와 자사 양쪽에 강제합니다. 자사 DB에는 unique 제약으로 키를 선저장한 뒤 외부 호출, 마지막에 confirm 컬럼 업데이트하는 3단계 패턴을 씁니다.

## 체크리스트

- [ ] 도메인별 RPO/RTO 목표가 명문화되어 있는가
- [ ] 복제 모델(비동기/semi-sync/Aurora quorum)이 RPO 목표에 맞게 선택되었는가
- [ ] detect 단계에서 다중 모니터 합의가 사용되는가, 단일 ping 실패만으로 페일오버하지 않는가
- [ ] 옛 primary를 fence하는 메커니즘(STONITH / `super_read_only` / quorum)이 있는가
- [ ] 모든 replica에 `super_read_only=ON`이 적용되어 errant transaction을 사전 차단하는가
- [ ] GTID 집합 비교를 통해 errant transaction을 주기적으로 점검하는가
- [ ] 클라이언트 JVM의 `networkaddress.cache.ttl`이 DNS TTL 수준으로 짧은가
- [ ] HikariCP의 `keepaliveTime`, `validationTimeout`이 죽은 커넥션을 빠르게 솎아내는가
- [ ] aws-advanced-jdbc-wrapper 같은 토폴로지 인식 드라이버 사용을 검토했는가
- [ ] 비멱등 API에 무조건 `@Retryable`이 붙어있지 않은가
- [ ] 결제/포인트 같은 핵심 API에 idempotency key + unique 제약 + confirm 단계가 있는가
- [ ] planned switchover SOP가 문서화되어 있고 분기별로 리허설하는가
- [ ] Aurora `failover priority tier`가 의도대로 설정되어 있는가
- [ ] 페일오버 후 binlog 보존 정책이 PITR 윈도우를 깨지 않는가
- [ ] semi-sync timeout이 너무 짧아 비동기로 silent fallback되지 않는지 모니터링되는가
