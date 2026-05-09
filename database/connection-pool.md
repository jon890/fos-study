# 커넥션 풀 크기는 얼마나 조정해야 할까?

## 결론부터 — "작게"

직관과 반대다. 동시 사용자가 많아지면 풀을 키워야 할 것 같지만, 실제로는 **작게 유지하는 쪽이 더 빠르다**. 커넥션은 결국 DB 측 자원(워커 프로세스/스레드, 디스크 I/O)을 점유하는데, 그 자원의 수가 한정되어 있기 때문이다.

> 다른 변경 없이 커넥션 풀 크기만 줄였더니 애플리케이션 응답 시간이 약 100ms에서 약 2ms로, 50배 이상 단축됐다 — HikariCP 공식 글 사례.

## 왜 작아야 하나

CPU 코어가 하나뿐인 컴퓨터도 수십·수백 개 스레드를 "동시에" 돌리는 것처럼 보인다. 하지만 실제로는 OS가 **타임 슬라이싱**으로 만들어낸 환상이고, 한 코어는 한 번에 하나의 스레드만 실행한다. 스레드를 늘릴수록 컨텍스트 스위칭 비용이 커지고, 코어 수를 넘어가면 추가하는 만큼 오히려 느려진다.

DB 쪽도 똑같다. 풀 크기를 1만으로 잡으면 1만 개의 커넥션이 DB 워커를 분점하는 셈이고, DB는 컨텍스트 스위칭에 시간을 쓰느라 실제 작업 시간이 줄어든다. 단일 CPU에서 A·B를 순차 실행하는 것이 타임 슬라이싱으로 "동시에" 실행하는 것보다 항상 빠르다는 건 컴퓨팅의 기본 법칙이다.

## PostgreSQL 공식 — 출발점

```text
Connection Pool Size = (코어 수 × 2) + I/O를 동시에 처리할 수 있는 디스크 수
```

- 4코어 + HDD 1대 → `(4 × 2) + 1 = 9`
- 8코어 + SSD 1대 → `(8 × 2) + 1 = 17`

PostgreSQL 발 공식이지만 MySQL을 비롯한 대부분 DB에 출발점으로 통한다. SSD/NVMe·Aurora·RDS Proxy 같은 환경에서는 그대로 따르지 말고 **부하 테스트로 sweet spot을 찾는 것이 정석**이다.

> 사용자가 1만 명이라고 풀을 1만 개로 잡는 건 말이 안 된다. 1,000개도 과하고 100개 조차 과하다. 풀은 수십 개 수준으로 두고, 나머지 애플리케이션 스레드는 풀에서 연결을 기다리도록 둔다.

## HikariCP 권장 설정

Spring Boot에서 가장 흔히 쓰이는 풀이 HikariCP다. 핵심 설정은 다섯 개로 보면 된다.

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 10           # 풀 상한 — 위 공식 기준 출발
      minimum-idle: 10                # 보통 maximum과 같게 (HikariCP 공식 권고)
      connection-timeout: 3000        # 풀에서 커넥션 못 받을 때 기다리는 시간 (ms)
      idle-timeout: 600000            # 유휴 커넥션 정리까지 (10분, ms)
      max-lifetime: 1800000           # 커넥션 최대 수명 (30분, ms)
      validation-timeout: 5000        # 헬스체크 타임아웃 (ms)
      keepalive-time: 60000           # 유휴 중 keepalive 주기 (1분, ms)
```

각 설정의 의도:

- **`maximum-pool-size`**: 풀 상한. **DB 측 `max_connections`보다 충분히 작아야 한다**가 기본 원칙. 여러 인스턴스(WAS 4대 × 풀 10 = 동시 40 커넥션)를 함께 계산해야 한다.
- **`minimum-idle = maximum-pool-size`**: HikariCP 공식 위키는 두 값을 같게 두라고 권한다. 풀이 줄었다가 다시 커지는 사이클이 응답 지연을 만들기 때문이다. 즉 **고정 크기 풀**로 운영.
- **`connection-timeout`**: 풀이 비어 있을 때 호출자가 기다리는 한계. 보통 3초. 이 시간을 넘으면 `SQLTransientConnectionException`이 난다. 길게 잡으면 장애가 호출자에게 잘 안 보이고, 짧으면 일시적 부하에서 실패가 늘어난다.
- **`max-lifetime`**: 커넥션을 강제로 잘라내는 주기. **MySQL 서버의 `wait_timeout`보다 짧게** 잡아야 한다. 그렇지 않으면 서버가 끊은 커넥션을 풀이 가지고 있다가 "Communications link failure"를 만든다. 보통 30분.
- **`idle-timeout`**: 유휴 커넥션 정리. `minimum-idle = maximum`이면 사실상 비활성. 풀 크기를 변동시키고 싶을 때만 의미가 있다.

## MySQL 측 설정

풀만 잘 잡아도 DB 측 설정이 안 맞으면 깨진다. 자주 보는 두 축.

```sql
SHOW VARIABLES LIKE 'max_connections';        -- 동시 커넥션 상한 (기본 151)
SHOW VARIABLES LIKE 'wait_timeout';           -- 유휴 커넥션 자르는 시간 (기본 28800 = 8시간)
SHOW VARIABLES LIKE 'interactive_timeout';    -- 인터랙티브 세션 유휴 자르기
```

권장값 (B2B 백엔드 기준):

| 설정 | 권장값 | 이유 |
|---|---|---|
| `max_connections` | (각 WAS 풀 × 인스턴스 수) + 여유분 + 운영 도구 몫 | 풀 합보다 작으면 풀이 못 채워짐 |
| `wait_timeout` | 600~3600 (10분에서 1시간) | 기본 8시간은 너무 길다. HikariCP `max-lifetime`보다 충분히 길게 |
| `interactive_timeout` | 동일 | 일관성 유지 |

`max-lifetime` < `wait_timeout`이 되도록 잡는 게 핵심이다. 풀이 먼저 자르고 서버가 그 다음에 자르도록 순서를 맞춰야 위에서 말한 "끊긴 커넥션을 풀이 들고 있는" 문제가 안 난다.

## 운영에서 봐야 할 메트릭

풀 크기를 정한 뒤 실제로 적정한지는 메트릭으로 본다. HikariCP는 Micrometer로 다음 메트릭을 노출한다.

- `hikaricp.connections.active` — 사용 중 커넥션 수
- `hikaricp.connections.idle` — 유휴 커넥션 수
- `hikaricp.connections.pending` — **풀 대기 중인 스레드 수. 이게 0보다 크면 풀이 부족하다는 신호**
- `hikaricp.connections.usage` — 커넥션 사용 시간 분포
- `hikaricp.connections.acquire` — 풀에서 커넥션 받는 데 걸린 시간

가장 중요한 건 `pending`. 평소엔 0이고 트래픽 피크에서 잠깐 1~2 찍는 정도면 풀 크기는 적정. 지속적으로 `pending`이 쌓이면 풀이 부족하거나 **트랜잭션이 길어진 신호**(SELECT가 오래 걸리거나, 트랜잭션 안에서 외부 IO를 하는 안티패턴 등)다. 이 경우 풀을 늘리기 전에 **트랜잭션 길이부터 점검**하는 게 정석이다.

## 핵심 요약

- 풀은 **작게**. 직관과 반대지만 컨텍스트 스위칭 비용 때문이다.
- PostgreSQL 공식 `(코어 × 2) + 디스크`를 출발점으로, **부하 테스트로 sweet spot 확인**.
- HikariCP는 `maximum = minimum`(고정 크기), `max-lifetime < wait_timeout` 순서를 지킬 것.
- MySQL `max_connections`는 (풀 × 인스턴스) + 여유분 이상으로 충분히 잡을 것.
- `hikaricp.connections.pending`을 모니터링 — 의미 있게 쌓이면 풀이 아니라 **트랜잭션 길이**부터 점검.

## 관련 / 참고

- [Aurora Serverless 커넥션 풀과 트랜잭션 예산](./mysql/aurora-serverless-connection-pool-transaction-budget.md) — 서버리스 환경에서의 풀·재시도·외부 IO 분리
- [HTTP Connection Pool](../http/connection-pool.md) — 다른 레이어의 같은 풀 패턴 (TCP/TLS 재사용)
- [HikariCP — About Pool Sizing](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
- [HikariCP — MySQL Configuration](https://github.com/brettwooldridge/HikariCP/wiki/MySQL-Configuration)
- [PostgreSQL Wiki — Number Of Database Connections](https://wiki.postgresql.org/wiki/Number_Of_Database_Connections)
