# [초안] Aurora Serverless 환경의 커넥션 풀과 트랜잭션 예산 설계

## 왜 이 주제가 중요한가

Aurora Serverless는 "필요할 때만 늘어나고 줄어드는 MySQL"이라는 매력적인 약속을 한다. 하지만 그 약속은 애플리케이션 측 커넥션 풀 설계와 트랜잭션 점유 패턴이 받쳐줄 때만 성립한다. 풀을 잘못 잡으면 ACU가 천천히 따라오는 동안 커넥션 고갈로 503이 먼저 터지고, 트랜잭션을 길게 잡으면 scale-down이 막히면서 비용은 비용대로 나간다. 올리브영처럼 정시 행사·라이브 방송 직후 짧은 시간 안에 트래픽이 5~10배로 튀는 커머스 환경에서는 이 두 축을 분리해서 사고하는 것이 실력 차이를 가른다.

면접관이 "Aurora Serverless를 쓰는 서비스에서 커넥션 풀은 어떻게 잡으셨어요?"라고 물어볼 때, 단순히 "HikariCP에 maximumPoolSize 10 정도 줬어요"로 끝내면 그 위에 어떤 후속 질문도 쌓을 수 없다. 풀 사이즈, max_connections, RDS Proxy, 트랜잭션 길이, 외부 IO 분리, 재시도 정책이 한 묶음으로 움직인다는 사실을 보여줘야 한다.

이 글은 그 묶음을 "트랜잭션 예산(transaction budget)"이라는 운영 감각으로 풀어낸다. 인덱스나 쿼리 튜닝 같은 한 단계 안쪽 주제는 [데이터베이스 풀 동시성 모델](./mysql-connection-pool-concurrency.md) 류의 기존 문서가 있다면 그쪽을 가볍게 참조하고, 여기서는 "서버리스 + 풀 + 예산"의 결합 지점에 집중한다.

## 핵심 개념: Aurora Serverless의 동작 모델부터 다시

### v1 vs v2 — 같은 이름, 다른 짐승

Aurora Serverless v1은 capacity unit을 **단계적으로** 점프시킨다. 2 ACU → 4 ACU → 8 ACU 같은 식으로 이동하고, 그 이동 자체가 수십 초~수 분 걸린다. 트래픽이 갑자기 들어오면 일정 시간 동안은 작은 ACU로 버텨야 하고, 활성 트랜잭션이 있으면 scale을 못 한다. 그래서 v1은 "트래픽이 평탄하지만 idle 비중이 큰 워크로드"에 맞는다.

v2는 0.5 ACU 단위로 **연속적**으로 스케일된다. 점프가 아니라 슬라이더가 움직이듯이 capacity가 변한다. cold start도 v1보다 훨씬 짧다. 다만 0 ACU까지 내려가는 auto-pause는 v2 초기에는 없었고, 이후 일부 모드에서 추가됐다. 면접에서는 "우리는 v2를 쓰는데, scale 자체는 빠르지만 max_connections는 ACU에 비례해서 결정되기 때문에 갑자기 큰 풀을 요구하면 거절당한다"는 식으로 답하는 게 좋다.

핵심 포인트는 이거다. **ACU가 늘어나는 속도와 트래픽이 늘어나는 속도가 다르다.** 둘의 미스매치가 커넥션 풀 설계의 출발점이다.

### max_connections는 ACU에 묶여 있다

Aurora MySQL의 max_connections 기본값은 인스턴스 메모리에 비례한 공식으로 계산된다. Serverless v2에서는 ACU(메모리)에 따라 동적으로 바뀌는데, 0.5 ACU에서는 수십 개, 4 ACU 정도에서야 수백 개가 된다. 즉 scale-down 상태에서 애플리케이션이 큰 풀을 가지고 있으면 단순히 커넥션을 여는 행위만으로 DB 한도를 넘긴다.

여기서 흔한 오해 하나. "풀 사이즈를 크게 잡아두면 트래픽이 튀어도 안전하지 않나?" 정반대다. 풀이 크면 작은 ACU 상태에서 커넥션 자체로 DB를 압박하고, 그 압박이 scale 트리거를 더 늦춘다.

### scale-down을 막는 가장 흔한 범인: 긴 트랜잭션

Aurora Serverless가 scale-down을 결정하려면 "지금 줄여도 안전한가"를 봐야 한다. 활성 트랜잭션, 임시 테이블, 락이 있으면 줄이지 않는다. 운영에서 보면 야간 배치가 트랜잭션을 1시간씩 잡고 있다든지, 외부 결제 콜백을 트랜잭션 안에서 기다린다든지 하는 패턴이 scale-down을 통째로 막아 비용을 두 배로 만드는 사례가 흔하다.

## 트랜잭션 예산이라는 사고 틀

"트랜잭션 예산"은 공식 용어가 아니라 운영 감각을 코드화한 표현이다. 한 트랜잭션이 쓸 수 있는 자원을 미리 정해두고, 그 한도를 넘으면 트랜잭션을 쪼개거나 트랜잭션 밖으로 빼낸다는 발상이다.

예산의 축은 보통 네 가지다.

1. **시간 예산**: 한 트랜잭션은 몇 ms 안에 끝나야 하는가 (예: P99 200ms)
2. **락 예산**: 어떤 행/테이블 락을 얼마나 오래 쥘 수 있는가
3. **커넥션 예산**: 동시에 몇 개의 트랜잭션을 열 수 있는가 (= 풀 사이즈와 직결)
4. **IO 예산**: 트랜잭션 안에서 외부 호출, 파일 IO, 네트워크 호출을 몇 번 하는가 (이상적으로는 0)

이 네 가지가 서로 곱해진다. 시간이 2배 길어지면 같은 풀로 처리할 수 있는 RPS는 절반이 되고, 락 시간이 길어지면 hot row 위에서는 사실상 직렬화된다. 외부 IO를 트랜잭션 안에 넣으면 그 외부 시스템의 P99가 우리 DB의 점유 시간이 된다.

### Little's Law로 풀 사이즈 잡기

면접에서 풀 사이즈 정한 근거를 물어보면 Little's Law를 꺼내는 게 깔끔하다.

```
필요한 커넥션 수 ≈ 평균 RPS × 트랜잭션당 평균 점유 시간(초)
```

예를 들어 한 인스턴스가 200 RPS를 받고, 한 트랜잭션이 평균 50ms DB를 점유한다면 평균적으로는 `200 × 0.05 = 10`개 커넥션이 필요하다. 거기에 P99 여유분으로 2~3배를 잡아 25~30개 정도를 시작값으로 둔다. **트래픽이 아니라 점유 시간이 풀 사이즈를 결정한다**는 점을 강조해야 한다.

여기서 Aurora Serverless 제약이 들어온다. 인스턴스가 5대고 각각 30개 풀을 잡으면 총 150커넥션이다. 이게 0.5 ACU 시점의 max_connections를 넘으면 cold start 직후 인스턴스가 동시에 풀을 채우려는 순간 일제히 거절당한다.

## 실전 백엔드 적용 패턴

### HikariCP + RDS Proxy 조합 이유

Aurora Serverless 앞에 RDS Proxy를 두는 가장 큰 이유는 **fan-out 흡수**다. 애플리케이션 인스턴스 수가 늘어날 때마다 DB 커넥션이 곱해지지 않게, 실제 DB 커넥션은 Proxy 측에서 공유 풀로 관리한다. 그 결과 애플리케이션 풀은 "응답성을 위한 로컬 캐시", DB 커넥션은 "공유 자원"으로 역할이 분리된다.

이 분리가 있으면 HikariCP의 maximumPoolSize는 비교적 넉넉하게 잡아도 된다. 어차피 Proxy가 실제 DB 커넥션을 재사용하기 때문이다. 다만 트랜잭션 모드(pinning)에 들어가면 Proxy의 커넥션 멀티플렉싱 효과가 사라진다는 점은 주의해야 한다. `SET` 같은 세션 상태 변경, 임시 테이블, prepared statement 사용 패턴에 따라 pin이 걸린다.

### Spring Boot 설정의 출발점

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 2000      # 2초 내 못 받으면 빠르게 실패
      validation-timeout: 1000
      max-lifetime: 300000          # 5분 — Proxy idle timeout보다 짧게
      idle-timeout: 60000
      keepalive-time: 30000
      leak-detection-threshold: 5000
```

`connection-timeout`을 짧게 잡는 게 핵심이다. 트래픽 폭주 시 풀에서 영원히 기다리게 두면 thread가 쌓이고 컨테이너가 OOM으로 죽는다. 차라리 빨리 실패해서 회로 차단기에 신호를 보내는 게 낫다.

`max-lifetime`은 RDS Proxy 또는 Aurora 측의 idle/wait_timeout보다 짧게 잡는다. 안 그러면 DB가 끊은 커넥션을 풀이 살아 있다고 믿고 꺼내 쓰다 첫 쿼리에서 실패한다.

## Bad vs Improved 예제

### 예제 1: 외부 결제 호출을 트랜잭션 안에 둔 경우

```java
// BAD
@Transactional
public Order placeOrder(OrderRequest req) {
    Order order = orderRepository.save(req.toEntity());
    PaymentResult pr = paymentClient.charge(order);   // 외부 HTTP 2~5초
    order.markPaid(pr);
    return order;
}
```

이 트랜잭션은 결제사 응답 시간만큼 DB 커넥션을 잡고 행 락을 유지한다. 결제사 P99가 3초면 우리 DB 점유도 3초가 된다. RPS 100에서 점유 3초면 Little's Law로 300 커넥션이 필요해진다. Aurora Serverless가 ACU를 올릴 시간을 벌기도 전에 풀이 마른다.

```java
// IMPROVED
public Order placeOrder(OrderRequest req) {
    Order order = txTemplate.execute(s ->
        orderRepository.save(req.toEntityPending()));   // 짧은 INSERT만

    PaymentResult pr = paymentClient.charge(order);     // 트랜잭션 밖

    return txTemplate.execute(s -> {                    // 다시 짧은 UPDATE
        Order o = orderRepository.findByIdForUpdate(order.getId());
        o.markPaid(pr);
        return o;
    });
}
```

트랜잭션을 두 번 짧게 끊어 외부 IO를 밖으로 꺼냈다. 점유 시간이 50ms 수준으로 떨어지면서 같은 풀로 처리할 수 있는 RPS가 수십 배 늘어난다. 외부 호출 실패 시 보상 트랜잭션·재시도·결제 상태 reconciliation 배치는 별도로 설계해야 한다.

### 예제 2: 풀 사이즈를 무작정 키운 경우

```yaml
# BAD
hikari:
  maximum-pool-size: 200
```

ECS 태스크 30개가 모두 200을 잡으면 6000개 커넥션을 시도한다. 0.5 ACU 인스턴스가 cold start하는 순간 max_connections 거부로 헬스체크부터 떨어진다.

```yaml
# IMPROVED
hikari:
  maximum-pool-size: 20
  connection-timeout: 2000
```

대신 RDS Proxy를 두고, 애플리케이션 측은 "한 인스턴스가 동시에 처리할 수 있는 in-flight 트랜잭션 수"에 맞춘다. 30 × 20 = 600도 여전히 작은 ACU에서는 부담이지만, Proxy의 공유 풀을 거치면 실제 DB 측 커넥션은 그보다 훨씬 적게 유지된다.

### 예제 3: 락을 길게 잡는 배치

```sql
-- BAD: 한 트랜잭션 안에서 100만 행을 한 번에 업데이트
START TRANSACTION;
UPDATE order_item SET status='ARCHIVED'
 WHERE created_at < '2025-01-01';
COMMIT;
```

이 트랜잭션이 도는 동안 scale-down은 막히고, 해당 테이블의 다른 쓰기가 줄을 선다.

```sql
-- IMPROVED: 청크 단위 분할
SET @last_id := 0;
REPEAT
  START TRANSACTION;
  UPDATE order_item SET status='ARCHIVED'
   WHERE id > @last_id
     AND created_at < '2025-01-01'
   ORDER BY id
   LIMIT 1000;
  SELECT MAX(id) INTO @last_id FROM ...;
  COMMIT;
UNTIL done END REPEAT;
```

청크 1,000행 단위로 끊으면 락 시간이 수백 ms로 떨어지고, 사이사이 다른 트랜잭션이 진입할 수 있다. 작업 도중 scale-down도 가능해진다.

## 로컬 실습 환경 구성

Aurora Serverless를 그대로 띄우는 비용을 매번 부담할 필요는 없다. 트랜잭션 예산 감각은 로컬 MySQL 8로도 충분히 훈련된다.

### docker-compose.yml

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: shop
    command:
      - --max_connections=50          # 일부러 작게
      - --innodb_lock_wait_timeout=3
      - --wait_timeout=60
    ports: ["3306:3306"]
```

`max_connections=50`으로 일부러 좁혀두면 풀을 잘못 잡았을 때 즉시 재현된다.

### 부하 생성 스크립트

```bash
# k6 또는 hey로 RPS 200 트래픽
hey -z 60s -c 50 http://localhost:8080/orders
```

이때 슬로우 쿼리 로그와 `SHOW PROCESSLIST`를 모니터링하며 트랜잭션 점유 시간을 측정한다.

## 실행 가능한 예제: 점유 시간 측정

```sql
-- 현재 활성 트랜잭션과 시작 시각
SELECT trx_id, trx_started,
       TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS held_sec,
       trx_state, trx_query
  FROM information_schema.innodb_trx
 ORDER BY trx_started;

-- 락 대기 체인
SELECT * FROM performance_schema.data_lock_waits;
```

운영에서는 이 두 쿼리를 1분 주기 알람으로 걸어두는 것만으로도 "10초 넘게 사는 트랜잭션"을 90% 잡아낼 수 있다. 면접에서 "트랜잭션이 얼마나 도는지 어떻게 보세요?"에 답할 때 이 두 쿼리를 들 수 있다.

## 커머스 트래픽 시나리오: 라이브 방송 직후

올리브영 같은 환경을 가정하자. 21시 라이브 방송 종료 직후 30초 안에 평소 RPS의 8배가 들어온다. Aurora Serverless v2는 0.5초 단위로 ACU를 올리지만, 8배 캐파에 도달하려면 그래도 수십 초 걸린다. 그 갭을 어떻게 메우는가가 설계 포인트다.

- **풀은 작게, 응답은 빠르게**: 풀이 크면 작은 ACU에 커넥션 부담이 집중된다. 풀을 작게 잡고 connection-timeout을 짧게 설정해 빨리 실패시킨다.
- **읽기 부하는 리더로**: 상품 상세, 재고 표시 같은 읽기는 reader endpoint로 분산. Aurora의 read replica scale은 별도라 writer만 묶이는 상황을 피할 수 있다.
- **결제·재고 차감은 짧은 트랜잭션 + 외부 IO 분리**: 결제 게이트웨이, 쿠폰 외부 시스템, 알림은 모두 트랜잭션 밖. 트랜잭션 안에는 우리 DB 한정.
- **짧은 idempotency window 캐시**: 동일 주문 중복 클릭은 Redis로 흡수해 DB까지 안 보낸다.
- **Burst를 흡수하는 큐**: 즉시 응답이 필요 없는 후속 작업(메일, 적립, 추천 학습)은 Kafka/SQS로 빼낸다.
- **회로 차단기**: 외부 결제·배송 시스템 P99가 튀면 빠르게 실패시켜 우리 DB 커넥션이 그 시스템의 지연에 묶이지 않게 한다.

## 면접 답변 프레임

면접관: "Aurora Serverless 환경에서 커넥션 풀은 어떻게 잡으셨어요?"

```
저는 풀 사이즈 자체보다 트랜잭션 점유 시간을 먼저 봅니다.
Little's Law로 평균 RPS × 평균 점유 시간을 계산해서 필요 커넥션 수를 잡고,
거기에 P99 여유분 2~3배를 더해 풀 사이즈를 정합니다.

Aurora Serverless v2는 ACU에 비례해 max_connections가 변하기 때문에,
작은 ACU에서 cold start 시 풀을 한꺼번에 채우려다 거절당하지 않도록
풀은 일부러 작게 잡고 connection-timeout을 2초 이내로 짧게 둡니다.

대신 애플리케이션 인스턴스가 늘어날 때 fan-out을 흡수하기 위해
RDS Proxy를 앞에 둬서 실제 DB 커넥션은 공유 풀로 관리합니다.

가장 신경 쓰는 건 트랜잭션 안에 외부 IO가 들어가지 않는 것입니다.
결제, 알림, 외부 API 호출은 모두 트랜잭션 밖으로 빼고,
DB 트랜잭션은 한 자리수 ms~수십 ms 안에 끝나게 합니다.
이게 곧 scale-down을 막지 않는 운영 조건이기도 합니다.
```

면접관: "트랜잭션 예산이라는 게 뭔가요?"

```
한 트랜잭션이 쓸 수 있는 시간, 락, 커넥션, 외부 IO를 미리 정해두는 사고 틀입니다.
예를 들어 한 트랜잭션은 P99 200ms, 외부 IO 0회, 한 행에 대한 락 50ms 이하로 잡습니다.
이 한도를 넘으면 트랜잭션을 쪼개거나, 외부 IO를 트랜잭션 밖으로 빼거나,
배치를 청크 단위로 나눕니다. 이렇게 하면 트래픽이 튀어도 풀 사이즈가 선형으로 줄지 않고,
Aurora Serverless가 scale-down을 결정하는 데도 방해가 안 됩니다.
```

면접관: "RDS Proxy를 꼭 써야 하나요?"

```
필수는 아니지만 두 가지 상황에서 강하게 권장합니다.
첫째, 애플리케이션 인스턴스가 자주 변하는 환경(서버리스 컴퓨트, ECS auto scaling).
둘째, Aurora Serverless처럼 max_connections가 동적으로 변하는 환경.
다만 트랜잭션 모드에서 pinning이 걸리면 Proxy의 멀티플렉싱 이점이 줄어들기 때문에
세션 변수나 임시 테이블 사용 패턴은 미리 점검해야 합니다.
```

## 운영 체크리스트

- 풀 사이즈는 RPS가 아니라 평균 트랜잭션 점유 시간 기준으로 산정했는가
- connection-timeout이 2초 이하로 짧게 잡혀 있는가
- max-lifetime이 RDS Proxy / Aurora의 wait_timeout보다 짧은가
- 결제·외부 API·알림이 모두 트랜잭션 밖으로 분리되어 있는가
- 1분 이상 사는 트랜잭션을 잡는 알람이 있는가 (`information_schema.innodb_trx`)
- scale-down이 막히는 시간대에 어떤 트랜잭션/락이 있는지 추적할 수 있는가
- 배치 작업은 청크 단위로 끊어 락 시간을 수백 ms 이하로 유지하는가
- 회로 차단기와 짧은 retry policy가 외부 의존성에 걸려 있는가
- 읽기 부하가 reader endpoint로 분산되어 있는가
- cold start 직후 일제히 풀을 채우는 패턴(thundering herd)을 방지하는 워밍업/지연 진입이 있는가
- 동일 요청 중복 클릭을 흡수하는 짧은 idempotency 캐시가 있는가
- 풀 고갈 시 fail-fast → 회로 차단기 → 캐시 fallback 순서로 응답 경로가 정의되어 있는가
