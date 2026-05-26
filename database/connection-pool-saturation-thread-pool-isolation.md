# [초안] DB Connection Pool Saturation과 Thread Pool 격리

## 왜 이 주제가 면접에서 중요한가

시니어 백엔드 면접에서 "장애 경험"을 물었을 때 가장 자주 등장하는 시나리오 중 하나가 **DB Connection Pool Saturation으로 시작되는 전체 서비스 다운**이다. 평소엔 평균 응답 50ms로 잘 돌던 주문 API가 어느 순간 P99 30s로 늘어지고, 헬스체크는 통과하는데 사용자 트래픽은 503으로 죽어나가는 상황. 표면 증상만 보면 "DB가 느려졌다"로 끝나지만, 시니어가 대답해야 하는 건 그 뒤다.

- 왜 HikariCP 풀이 빈 게 아니라 *꽉 찬 채로* 멈춰 있는가
- WAS의 Tomcat worker thread는 왜 같이 죽어나가는가
- 한 다운스트림(쿠폰 API, PG, 추천 서비스)의 지연이 어떻게 전체 인스턴스를 마비시키는가
- 다음에 같은 일이 또 안 나려면 어디에 *격벽(bulkhead)*을 세우는가

본 문서는 이 네 개 질문에 답할 수 있는 구조로 정리한다. 단순 풀 사이즈 튜닝은 [커넥션 풀 크기는 얼마나 조정해야 할까?](./connection-pool.md), Aurora Serverless 특수성은 [Aurora Serverless 환경의 커넥션 풀과 트랜잭션 예산 설계](./mysql/aurora-serverless-connection-pool-transaction-budget.md), 트랜잭션 경계 이슈는 [Spring 트랜잭션 전파·격리수준·AFTER_COMMIT 실전 정리](../java/spring/transaction-propagation-isolation-after-commit.md)로 분리되어 있다. 여기서는 그 위의 *운영 레이어*에 집중한다.

## 핵심 개념 — Saturation은 풀이 비는 게 아니라 꽉 차는 것

용어부터 정리한다.

- **Saturation**(포화): 풀의 *사용 중* 커넥션 수가 maximum-pool-size에 도달하고, 신규 요청은 `connection-timeout`을 기다리다가 `SQLTransientConnectionException`으로 떨어지는 상태
- **Exhaustion**(고갈): Saturation이 지속되어 풀이 영구적으로 빈 슬롯을 못 만드는 상태. 보통 *트랜잭션이 끝나지 않는다*는 신호
- **Starvation**(기아): 풀은 살아있지만 특정 요청군이 다른 요청군에 밀려 계속 대기하는 상태. 우선순위/공정성 이슈

Google SRE 책의 **USE Method**(Utilization, Saturation, Errors)와 **RED Method**(Rate, Errors, Duration)를 풀에 그대로 매핑하면 진단이 빨라진다.

- Utilization: `hikaricp.connections.active / max` — 사용률
- Saturation: `hikaricp.connections.pending` — 대기 큐 길이
- Errors: `SQLTransientConnectionException` count
- Rate: 트랜잭션 시작 RPS
- Duration: 트랜잭션당 점유 시간(P50/P95/P99)

면접에서 "어떤 지표를 봤느냐"를 물으면 위 5개를 한 호흡에 답하는 게 시니어 답변이다.

## Tomcat Worker Thread와 HikariCP의 직렬 연결

오해 1순위는 "Tomcat thread랑 DB 풀은 별개"라는 인식이다. 실제로는 *직렬*로 묶여 있다.

```text
[클라이언트] → [Tomcat NIO acceptor]
            → [Tomcat worker thread (max=200)]
              → [Spring DispatcherServlet]
                → [@Transactional 진입 → HikariCP 풀에서 커넥션 획득]
                  → [JDBC 호출 → MySQL]
```

worker thread는 *DB 커넥션을 잡고 있는 동안* 다른 요청을 받지 못한다. 즉:

- worker thread 200개 × 풀 10개 시스템에서, DB가 느려져 트랜잭션이 평균 10s를 잡으면 worker thread 200개가 전부 *풀 대기*로 묶인다
- 그 결과 헬스체크는 별도 풀을 안 쓰면 통과하지만(=`/actuator/health` Spring Boot에서 DB indicator off라면), 사용자 요청은 acceptor 큐에 쌓여 timeout
- 이 상태가 **worker thread saturation**이고, 출발점은 DB pool saturation이었다

답변 프레임으로 정리하면 "HikariCP가 막히면 그 위의 Tomcat worker가 직렬로 같이 막힌다. 풀 사이즈만 키우면 worker thread를 못 풀고, worker만 키우면 풀이 더 빨리 마른다. 둘은 묶어서 봐야 한다."

## Slow Query → Pool Exhaustion 연쇄

가장 흔한 실전 원인은 *느린 쿼리 하나*다. 다음 시나리오를 머릿속에 박아 두자.

1. 주문 목록 API에 `WHERE user_id = ? ORDER BY created_at DESC LIMIT 20` 쿼리가 있다
2. 인덱스가 `(user_id, status)`만 있고 `created_at`이 없어 filesort 발생
3. 평소엔 한 사용자 평균 50건이라 50ms로 끝나지만, 어드민이 *과거 데이터 백필* 배치를 돌려 일부 헤비 유저가 5만 건이 됐다
4. 그 유저의 요청이 들어오면 한 트랜잭션이 5s를 잡는다
5. 그 사이 같은 유저의 다른 요청, 다른 헤비 유저의 요청이 누적되며 풀 10개가 5s × N으로 점유된다
6. `hikaricp.connections.pending`이 쌓이기 시작하고, 30s `connection-timeout` 임박
7. 다운스트림으로 호출하는 *쿠폰 조회* 트랜잭션조차 풀을 못 얻어 실패한다
8. 사용자 입장에서는 "주문 페이지 전체가 멈춤"

여기서 시니어가 짚어야 할 포인트는 *원인은 한 쿼리지만 영향은 전체 트래픽*이라는 비대칭성이다. 풀 사이즈를 늘리는 응급 처치는 *원인의 영향 범위를 한 단계 더 키우는* 처방이 될 수 있다.

```sql
-- 진단용 — 현재 실행 중 long-running query 찾기
SELECT id, time, state, info
FROM information_schema.processlist
WHERE command != 'Sleep' AND time > 5
ORDER BY time DESC;

-- 트랜잭션이 안 끝나고 있는 세션 (InnoDB)
SELECT trx_id, trx_state, trx_started, trx_query
FROM information_schema.innodb_trx
ORDER BY trx_started ASC;
```

운영에서 saturation 알람이 떴을 때 위 두 쿼리를 1분 안에 던지는 것이 1차 대응이다. *풀 사이즈를 만지는 건 그다음*이다.

## Bulkhead 패턴 — Thread Pool 격리로 폭주 차단

배의 격벽(bulkhead)에서 따온 패턴이다. **한 다운스트림의 장애가 전체 인스턴스를 마비시키지 않도록 자원을 분리한다.**

격리 단위로 가장 흔한 세 가지:

- **DataSource 분리** — 주문 쓰기 / 주문 조회 / 백오피스 / 통계 배치를 각각 다른 HikariCP 풀로
- **Executor 분리** — 외부 PG 호출, 알림 호출, 추천 API 호출을 각각 다른 `ThreadPoolTaskExecutor`로
- **Resilience4j Bulkhead** — 라이브러리 레벨 격리. SemaphoreBulkhead / ThreadPoolBulkhead

Spring Boot에서 DataSource 분리는 다음과 같다.

```java
@Configuration
public class DataSourceConfig {

    @Bean
    @Primary
    @ConfigurationProperties("spring.datasource.write")
    public HikariDataSource writeDataSource() {
        // 주문/결제 쓰기 — pool 20, timeout 3s
        return new HikariDataSource();
    }

    @Bean
    @ConfigurationProperties("spring.datasource.read")
    public HikariDataSource readDataSource() {
        // 목록 조회 — pool 30, timeout 1s
        return new HikariDataSource();
    }

    @Bean
    @ConfigurationProperties("spring.datasource.batch")
    public HikariDataSource batchDataSource() {
        // 정산/백필 — pool 5, timeout 60s, replica
        return new HikariDataSource();
    }
}
```

핵심은 *batch가 폭주해도 write 풀은 멀쩡하다*는 보장이다. 같은 DB 인스턴스를 쓰더라도 풀 레벨에서 격리해 두면, 백오피스 한 명이 던진 무거운 쿼리가 결제 트랜잭션을 못 죽인다.

Executor 격리 예시:

```java
@Bean("pgExecutor")
public ThreadPoolTaskExecutor pgExecutor() {
    var ex = new ThreadPoolTaskExecutor();
    ex.setCorePoolSize(10);
    ex.setMaxPoolSize(10);
    ex.setQueueCapacity(20);  // 큐가 차면 reject — 절대 무한 큐 금지
    ex.setRejectedExecutionHandler(new ThreadPoolExecutor.AbortPolicy());
    ex.setThreadNamePrefix("pg-");
    return ex;
}

@Bean("notifyExecutor")
public ThreadPoolTaskExecutor notifyExecutor() {
    var ex = new ThreadPoolTaskExecutor();
    ex.setCorePoolSize(20);
    ex.setMaxPoolSize(20);
    ex.setQueueCapacity(100);
    ex.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy()); // 알림은 우아하게 떨어뜨림
    return ex;
}
```

큐 용량을 *항상 유한하게* 잡고 reject policy를 명시하는 것이 핵심. `LinkedBlockingQueue` 기본값(Integer.MAX_VALUE)을 쓰면 격벽이 무의미하다 — 메모리만 부풀고 결국 GC pause로 다 같이 죽는다.

## Timeout 계층 — 가장 깊은 곳이 가장 짧게

Saturation을 방지하는 두 번째 축은 timeout이다. 흔한 실수는 *위로 갈수록 짧게* 잡는 것. 정답은 반대다. **가장 깊은 호출(DB)이 가장 짧고, 위로 갈수록 점점 길게.**

| 레이어 | 권장값 (커머스 OLTP) | 이유 |
|---|---|---|
| MySQL 쿼리 timeout (`MAX_EXECUTION_TIME`) | 1\~3s | 슬로우 쿼리가 풀을 못 잡게 |
| JDBC `queryTimeout` (Statement) | 5s | 쿼리 timeout보다 살짝 길게 |
| HikariCP `connection-timeout` | 3s | 풀 대기는 짧게 — 빨리 실패 |
| `@Transactional(timeout=N)` | 10s | 한 트랜잭션 전체 예산 |
| Tomcat `connectionTimeout` | 20s | accept 후 첫 바이트까지 |
| L7 LB (ALB/Nginx) | 30s | 사용자에게 보이는 한계 |
| 클라이언트 (앱/브라우저) | 60s | 가장 너그럽게 |

부등호 한 줄: `DB <= JDBC <= HikariCP wait <= 트랜잭션 <= WAS <= LB <= client`. 이 부등호가 무너지면 *위쪽이 먼저 끊겨서 아래쪽 trx가 고아 상태로 풀을 점유*하는 사고가 난다. 면접 답변으로 거의 그대로 쓸 수 있다.

```yaml
spring:
  datasource:
    hikari:
      connection-timeout: 3000        # 풀 대기 3s
      validation-timeout: 2000
      max-lifetime: 1800000
      maximum-pool-size: 20
  jpa:
    properties:
      hibernate:
        jdbc:
          time_zone: UTC
        javax.persistence.query.timeout: 5000   # 5s — Statement timeout
server:
  tomcat:
    connection-timeout: 20000
    threads:
      max: 200
      min-spare: 25
```

## Backpressure — 받지 않을 권리

격리·timeout만으로는 부족한 경우가 있다. 들어오는 트래픽이 처리 능력을 초과할 때 *받는 양을 줄이는* 메커니즘이 backpressure다.

- **Tomcat acceptCount** — 큐 길이. 짧게 잡아 즉시 503을 내는 게 *천천히 무너지는 것*보다 낫다
- **Rate limiter** — Resilience4j RateLimiter / Bucket4j로 인스턴스당 RPS 상한
- **Circuit breaker** — 다운스트림이 일정 실패율 넘으면 short-circuit, 풀 잠식 차단
- **Load shedding** — `/health`와 `/critical` 경로는 살리고 나머지는 일찍 떨어뜨리기

```java
@Bean
public CircuitBreaker pgCircuitBreaker() {
    return CircuitBreaker.of("pg",
        CircuitBreakerConfig.custom()
            .failureRateThreshold(50)
            .waitDurationInOpenState(Duration.ofSeconds(10))
            .slidingWindowSize(20)
            .minimumNumberOfCalls(10)
            .build());
}
```

PG 같은 외부 의존이 죽었을 때 `failureRateThreshold` 50%를 넘으면 open 상태로 전환해 *즉시 실패*시킨다. 호출 자체를 안 하니 풀 점유가 없다. open 동안에는 Fallback(예: "결제 잠시 후 다시" 응답)으로 사용자 경험을 보존한다.

## 관측성 — Prometheus / Micrometer 지표

HikariCP는 Micrometer를 통해 다음 메트릭을 노출한다.

```text
hikaricp_connections                # 전체 (active + idle)
hikaricp_connections_active         # 사용 중
hikaricp_connections_idle           # 유휴
hikaricp_connections_pending        # 풀 대기 중인 스레드 수 ★
hikaricp_connections_max            # maximum-pool-size
hikaricp_connections_min            # minimum-idle
hikaricp_connections_usage_seconds  # 커넥션 사용 시간 분포
hikaricp_connections_acquire_seconds # 풀에서 받는 데 걸린 시간
hikaricp_connections_creation_seconds # 신규 생성 시간
hikaricp_connections_timeout_total  # connection-timeout으로 실패한 횟수
```

★ 표시한 `pending`이 0보다 의미 있게 크면 saturation 임박이다. Tomcat thread pool도 같이 본다.

```text
tomcat_threads_busy_threads
tomcat_threads_current_threads
tomcat_threads_config_max_threads
```

PromQL 쿼리 예시:

```text
# 풀 사용률
hikaricp_connections_active{application="order-api"} / hikaricp_connections_max{application="order-api"}

# 풀 대기 — saturation 직전 신호
hikaricp_connections_pending{application="order-api"}

# 트랜잭션 점유 시간 P99 — slow query 추적
histogram_quantile(0.99, sum(rate(hikaricp_connections_usage_seconds_bucket[5m])) by (le, application))

# worker thread 사용률
tomcat_threads_busy_threads / tomcat_threads_config_max_threads
```

알람 임계값 가이드 (커머스 OLTP 출발점):

- Utilization > 70% 3분 지속 → warn
- Pending > 0 1분 지속 → page
- `hikaricp_connections_timeout_total` 증가율 > 0 → page
- P99 usage > 트랜잭션 예산의 80% → warn

## 커머스 주문/결제 장애 시나리오 2개

### 시나리오 A — 라이브 방송 직후 풀 폭주

라이브 커머스 송출이 끝난 직후 3분간 평소 5배 트래픽 유입. 주문 API 풀 20, worker 200. PG 호출은 트랜잭션 내부에서 동기 호출. 평소 PG 응답 300ms.

- 트래픽 5배 + PG 응답 800ms로 상승 → 트랜잭션 점유 시간 약 1.2s
- Little's Law: 필요 풀 = 평균 RPS × 점유 시간. 평소 100rps × 0.5s = 50… 어? 풀 20인데 평소엔 어떻게 됐지?
- 평소엔 RPS도 작아 가능했지만, 피크에서 500rps × 1.2s = 600 → 풀 20으로는 절대 불가능
- worker 200 전부 풀 대기, ALB 30s timeout에 503 폭주

**개선**: PG 호출을 트랜잭션 밖으로 분리(주문 생성 trx 커밋 후 별도 executor에서 PG 호출), PG 호출에 circuit breaker, PG executor 풀 분리(20), 주문 trx timeout 3s, MAX_EXECUTION_TIME 1s.

이때 trx 경계와 PG 호출의 분리는 [Outbox Pattern](../architecture/distributed-transaction-outbox-pattern.md)으로 자연스럽게 연결된다.

### 시나리오 B — 백오피스 통계 쿼리가 운영 풀을 잡아먹음

운영자가 백오피스에서 "지난 1년 매출" 리포트를 받는다. 같은 DataSource를 쓰는 단일 풀 30. 통계 쿼리 하나가 풀 25개를 60s 동안 점유.

- 운영 트래픽이 풀 5로 처리되다가 saturation
- 결제 트랜잭션이 풀 대기로 밀려 PG 측에서는 정상 승인됐는데 우리 DB에는 *주문 상태 업데이트가 안 됨*
- 결과: 환불 처리, CS 대응

**개선**: DataSource 격리(write/read/batch/backoffice 4풀), backoffice는 read replica로, 통계는 별도 워커 인스턴스. 운영 풀과 백오피스 풀이 격리됐다면 사용자 영향 0.

## Bad vs Improved 코드

### Bad — 트랜잭션 안에서 외부 호출 + 무한 큐

```java
@Transactional
public OrderResult placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.from(cmd));
    PgResponse pg = pgClient.charge(cmd.payment()); // 외부 호출! P99 = 풀 점유 시간
    notifyExecutor.submit(() -> emailService.send(order)); // notifyExecutor가 LinkedBlockingQueue 기본
    return OrderResult.success(order, pg);
}
```

문제: PG 응답이 느려지면 트랜잭션 전체가 늘어지고 풀이 점유된다. 알림 큐는 무한이라 메모리 폭증. 트랜잭션 내부 `submit`은 *커밋 전*에 큐잉되므로 롤백 시 *고스트 알림*까지 발생.

### Improved — Outbox + executor 격리 + commit 이후 발행

```java
@Transactional
public OrderResult placeOrder(OrderCommand cmd) {
    Order order = orderRepository.save(Order.from(cmd));
    outboxRepository.save(OutboxEvent.pgCharge(order, cmd.payment()));
    return OrderResult.accepted(order); // 결제는 비동기 — 사용자에게 "처리 중" 응답
}

// 별도 executor + circuit breaker
@Scheduled(fixedDelay = 500)
public void publishOutbox() {
    outboxRepository.findUnpublished(100).forEach(evt ->
        pgExecutor.submit(() -> withCircuitBreaker(() -> pgClient.charge(evt))));
}
```

trx는 DB 쓰기만 잡고 즉시 풀 반환. PG 호출은 격리된 풀에서, 실패 시 circuit breaker가 전체 잠식 차단.

## 로컬 실습 환경

부하 상황 재현은 의외로 간단하다.

```bash
docker run -d --name mysql8 -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 mysql:8
docker run -d --name app -e SPRING_DATASOURCE_URL=jdbc:mysql://host.docker.internal:3306/test \
  -e SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=5 my-spring-boot:latest

# slow query 강제
mysql -uroot -proot -e "SELECT SLEEP(10);" &
mysql -uroot -proot -e "SELECT SLEEP(10);" &
# ... 풀 5에 맞춰 SLEEP 5개 띄움

# k6로 동시 부하
k6 run --vus 50 --duration 30s load.js
```

`/actuator/prometheus`에서 `hikaricp_connections_pending`이 즉시 5, 10, 20…으로 쌓이는 것을 관측 가능. 그 상태에서 timeout 부등호를 깨뜨려보고 어떻게 503 패턴이 바뀌는지 직접 보면 답변이 단단해진다.

## 면접 답변 프레임 — 1분 / 3분

### 1분 답변 — "DB Connection Pool Saturation 경험"

> 라이브 트래픽 피크 직후 풀 saturation이 발생한 적이 있습니다. 원인은 단일 풀에서 결제 쓰기 트랜잭션과 PG 외부 호출이 묶여 있었던 것이고, PG 응답이 길어지면서 풀 20이 1.2초씩 점유돼 500 RPS를 못 받았습니다. 해결은 세 축으로 했습니다. 첫째 PG 호출을 Outbox로 트랜잭션 밖으로 빼서 trx 점유 시간을 1.2초에서 80ms로 줄였고, 둘째 PG executor를 별도 풀로 격리하고 circuit breaker를 걸어 폭주를 차단했고, 셋째 timeout 계층을 DB 1초 / 풀 대기 3초 / WAS 20초 / LB 30초로 정렬해 부등호를 맞췄습니다. 사후 회고는 `hikaricp_connections_pending`과 worker thread busy 비율을 같이 본다는 알람을 추가하는 걸로 마무리했습니다.

### 3분 답변 — "Thread Pool 격리 설계"

bulkhead 패턴 정의 → DataSource 격리 / Executor 격리 / 라이브러리 bulkhead 3축 → 큐 용량 유한화 + reject policy 명시 이유 → backpressure(rate limiter / circuit breaker) → 관측 지표(`hikaricp_connections_pending`, `tomcat_threads_busy`, executor queue depth) → 운영 사례(시나리오 B) → trade-off(격리 풀 수가 늘수록 max_connections 총합도 늘어 DB 측 제약 검토 필요).

### 자주 나오는 꼬리 질문

- "풀 사이즈를 늘리는 게 답이 아닌 이유?" → DB 측 max_connections / 컨텍스트 스위칭 / 원인이 점유 시간일 수 있어
- "왜 timeout이 깊은 쪽이 짧아야 하는가?" → 위에서 먼저 끊기면 아래 trx가 고아로 풀을 점유
- "Bulkhead와 Circuit breaker 차이?" → bulkhead는 자원 격리(공간), circuit breaker는 실패 누적 시 호출 차단(시간)
- "Little's Law로 풀 사이즈를 어떻게 잡나?" → `필요 풀 ≈ RPS × 평균 점유 시간`, P99 여유분 2~3배
- "한 DB 인스턴스에 풀을 여러 개 만들면 max_connections 부족 아닌가?" → 그래서 RDS Proxy / PgBouncer 같은 외부 풀러와 함께 설계

## 운영 체크리스트

- [ ] HikariCP `maximum-pool-size`가 Little's Law 기반 근거를 갖는가
- [ ] `(인스턴스 수 × 풀 사이즈 합) <= DB max_connections - 운영 여유분`인가
- [ ] `max-lifetime < MySQL wait_timeout` 부등호가 성립하는가
- [ ] DataSource를 write/read/batch/backoffice로 격리했는가 (또는 의식적으로 단일을 선택했는가)
- [ ] 외부 호출(PG, 알림, 추천)이 트랜잭션 *밖에* 있는가
- [ ] 외부 호출용 ThreadPoolTaskExecutor의 queueCapacity가 유한이고 reject policy가 명시됐는가
- [ ] timeout 부등호 `DB <= JDBC <= 풀 <= trx <= WAS <= LB <= client`가 일관되는가
- [ ] `hikaricp_connections_pending` / `_timeout_total` / `tomcat_threads_busy` 알람이 있는가
- [ ] circuit breaker가 핵심 다운스트림(PG, 외부 검색, 결제 사후 정산)에 걸려 있는가
- [ ] saturation 발생 시 1분 안에 던질 진단 쿼리(`processlist`, `innodb_trx`)가 런북에 있는가
- [ ] 풀 사이즈를 키우기 *전에* "트랜잭션 점유 시간이 길어진 게 아닌가"부터 점검하는 절차가 있는가

## 관련 / 참고

- [커넥션 풀 크기는 얼마나 조정해야 할까?](./connection-pool.md) — 풀 사이즈 기본 공식과 HikariCP 권장 설정
- [Aurora Serverless 환경의 커넥션 풀과 트랜잭션 예산 설계](./mysql/aurora-serverless-connection-pool-transaction-budget.md) — Aurora Serverless 환경의 ACU/풀/트랜잭션 예산
- [분산 트랜잭션과 Outbox 패턴](../architecture/distributed-transaction-outbox-pattern.md) — 트랜잭션 밖으로 외부 호출 빼기 패턴
- [Spring 트랜잭션 전파·격리수준·AFTER_COMMIT 실전 정리](../java/spring/transaction-propagation-isolation-after-commit.md) — `AFTER_COMMIT` / `REQUIRES_NEW` 활용
- [HikariCP — About Pool Sizing](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
- [Resilience4j Bulkhead](https://resilience4j.readme.io/docs/bulkhead)
- [Google SRE — USE Method](https://www.brendangregg.com/usemethod.html)
