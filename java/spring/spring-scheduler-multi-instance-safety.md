# [초안] Spring 스케줄러 다중 인스턴스 안전성 — @Scheduled가 N번 도는 문제와 해결

> 학습 목표: 단일 서버에서 잘 돌던 `@Scheduled` 작업이 인스턴스를 2대 이상으로 늘리는 순간 왜 중복 실행되는지 이해하고, ShedLock·분산 락·리더 선출·외부 스케줄러 같은 선택지를 trade-off와 함께 고를 수 있게 한다.
>
> 한 줄 결론: `@Scheduled`는 JVM 하나 안에서만 동작하므로 인스턴스 간 조율 장치가 전혀 없다. 같은 잡을 한 번만 돌리려면 외부 저장소 기반의 잠금(또는 단 하나의 실행 주체)을 별도로 붙여야 한다.
>
> 관련 문서: [Redis 분산 락](../../database/redis/distributed-lock.md), [Spring Batch vs Event-Driven](../../architecture/spring-batch-vs-event-driven.md)

---

## 왜 중요한가

처음 서비스를 띄울 때는 인스턴스가 한 대다. 매일 새벽 정산을 돌리는 `@Scheduled`, 만료 쿠폰을 정리하는 배치, 외부 API로 상태를 동기화하는 폴링 작업이 모두 그 한 대에서 한 번씩 돈다. 문제가 없다.

트래픽이 늘어 인스턴스를 3대로 스케일 아웃하는 순간 조용히 망가진다. 같은 코드가 3대에 똑같이 배포되므로, 새벽 정산이 3번 실행되고, 결제 알림 메일이 3통 나가고, 외부 API 호출이 3배가 된다. 컴파일 에러도, 런타임 예외도 없이 "그냥 결과가 이상한" 형태로 드러나기 때문에 운영에서 가장 늦게 발견되는 부류의 버그다.

핵심은 `@Scheduled`가 분산 환경을 전혀 모른다는 사실이다. 이 문서는 그 한계를 이해하고, 중복 실행을 막는 표준 패턴들을 정리한다.

---

## @Scheduled는 어떻게 동작하는가

Spring의 `@Scheduled`는 `ScheduledAnnotationBeanPostProcessor`가 빈을 스캔해서, cron/fixedDelay/fixedRate 메타데이터를 읽고 `TaskScheduler`(기본 구현은 `ThreadPoolTaskScheduler`)에 등록하는 구조다.

```java
@Component
public class SettlementJob {

    @Scheduled(cron = "0 0 3 * * *") // 매일 새벽 3시
    public void runDailySettlement() {
        // 정산 로직
    }
}
```

여기서 중요한 사실 두 가지:

- **스케줄러는 그 JVM 프로세스 내부에만 존재한다.** `ThreadPoolTaskScheduler`는 로컬 스레드 풀일 뿐, 다른 인스턴스의 스케줄러와 통신하지 않는다.
- **각 인스턴스는 자기 시계로 cron 시각을 판단한다.** 인스턴스 A도 새벽 3시에 깨고, 인스턴스 B도 새벽 3시에 깬다. 둘은 서로의 존재를 모른다.

즉 N개 인스턴스 = N개의 독립된 스케줄러 = 같은 잡이 N번 실행. 이것은 버그가 아니라 `@Scheduled`의 설계 그대로의 동작이다.

---

## 흔한 오해

### 오해 1: "fixedRate면 한 군데서만 돌겠지"

fixedRate/fixedDelay/cron 모두 **로컬 트리거 방식**이다. 트리거 방식만 다를 뿐, 어느 것도 인스턴스 간 조율을 하지 않는다. 셋 다 똑같이 중복 실행된다.

### 오해 2: "DB 트랜잭션이 막아주지 않나"

트랜잭션은 같은 행을 동시에 수정할 때의 격리를 보장할 뿐, "이 잡을 한 번만 실행"을 보장하지 않는다. 3개 인스턴스가 각자 트랜잭션을 열고 각자 정산 행을 INSERT하면, 트랜잭션은 모두 정상 커밋되고 중복 데이터가 3건 남는다.

### 오해 3: "락만 걸면 멱등성은 신경 안 써도 된다"

락은 동시 실행을 줄여줄 뿐 완벽한 단일 실행을 보장하지 못한다. 락 만료(TTL)가 잡 실행 시간보다 짧거나, 시계 차이(clock skew)가 있거나, GC 멈춤으로 락을 늦게 해제하면 두 인스턴스가 겹칠 수 있다. 락은 1차 방어선이고, **잡 로직 자체의 멱등성**이 최종 안전망이다.

---

## 해결 패턴

### 패턴 1: ShedLock — 가장 표준적인 선택

ShedLock은 "스케줄 잡 한정 분산 락" 라이브러리다. 범용 분산 락이 아니라 **스케줄 중복 실행 방지**라는 단일 목적에 최적화돼 있다.

```java
@Scheduled(cron = "0 0 3 * * *")
@SchedulerLock(
    name = "dailySettlement",
    lockAtMostFor = "10m",  // 잡이 죽어도 최대 10분 뒤 락 강제 해제
    lockAtLeastFor = "1m"   // 최소 1분은 락 유지 (빠른 재획득/시계차 방어)
)
public void runDailySettlement() {
    LockAssert.assertLocked(); // 락 없이 호출되면 예외
    // 정산 로직
}
```

동작 원리:

- 잡이 트리거되면 ShedLock이 먼저 공유 저장소(JDBC/Redis/Mongo/ZooKeeper 등)에 락 행을 `INSERT` 또는 조건부 `UPDATE`로 잡으려 한다.
- 성공한 인스턴스만 잡을 실행한다. 나머지는 락 획득 실패로 조용히 스킵한다.
- 저장소가 **단일 진실의 원천**이 되어 인스턴스 간 조율을 대신한다.

JDBC 락 저장소 예시 스키마:

```sql
CREATE TABLE shedlock (
    name       VARCHAR(64)  NOT NULL,
    lock_until TIMESTAMP(3) NOT NULL,
    locked_at  TIMESTAMP(3) NOT NULL,
    locked_by  VARCHAR(255) NOT NULL,
    PRIMARY KEY (name)
);
```

`name`이 PK라는 점이 핵심이다. 같은 잡 이름으로 두 인스턴스가 동시에 INSERT를 시도하면 PK 제약으로 하나만 성공한다. 데이터베이스의 원자성에 조율을 위임하는 셈이다.

#### lockAtMostFor vs lockAtLeastFor

이 둘을 헷갈리면 운영 사고가 난다.

- **lockAtMostFor**(상한): 잡을 실행한 인스턴스가 락을 해제하지 못하고 죽었을 때를 대비한 안전장치. 이 시간이 지나면 락이 자동 해제돼 다음 실행이 가능해진다. **반드시 잡의 정상 최대 실행 시간보다 넉넉하게** 잡는다. 너무 짧으면 긴 잡이 끝나기 전에 락이 풀려 다른 인스턴스가 끼어든다.
- **lockAtLeastFor**(하한): 잡이 매우 빨리 끝나도 최소 이 시간만큼은 락을 유지한다. 잡이 0.1초 만에 끝나는데 인스턴스 간 시계가 약간 다르면, 락이 즉시 풀리면서 다른 인스턴스가 같은 cron 시각에 또 잡을 수 있다. 이를 막는다.

### 패턴 2: 범용 분산 락 직접 사용 (Redis)

이미 Redis 분산 락 인프라가 있다면 ShedLock 없이 직접 잠글 수도 있다. 상세 구현은 [Redis 분산 락 문서](../../database/redis/distributed-lock.md)를 참고한다.

```java
@Scheduled(cron = "0 0 3 * * *")
public void runDailySettlement() {
    String lockKey = "lock:job:dailySettlement";
    // SET key value NX EX 600 — 원자적 획득 + TTL
    boolean acquired = redis.opsForValue()
        .setIfAbsent(lockKey, instanceId, Duration.ofMinutes(10));
    if (!Boolean.TRUE.equals(acquired)) {
        return; // 다른 인스턴스가 이미 실행 중
    }
    try {
        // 정산 로직
    } finally {
        // 본인이 건 락만 해제 (Lua로 owner 확인 후 DEL)
        releaseIfOwner(lockKey, instanceId);
    }
}
```

ShedLock 대비 차이: 직접 구현은 유연하지만 락 만료·소유권 확인·fencing token 같은 디테일을 스스로 책임져야 한다. 스케줄 중복 방지만이 목적이라면 ShedLock이 보일러플레이트를 줄여준다.

### 패턴 3: 리더 선출 (Leader Election)

"모든 인스턴스가 잡을 경합"하는 대신, **클러스터에서 리더 하나만 스케줄 잡을 돌린다**는 접근이다.

- Kubernetes `Lease` 오브젝트 기반 리더 선출
- Spring Integration `LeaderInitiator` (ZooKeeper/Hazelcast/etcd 등)
- 리더만 `@Scheduled` 잡을 활성화하고, 리더가 죽으면 다른 인스턴스가 리더를 이어받는다.

락 방식과의 차이: 락은 "매 실행마다 경합"이고, 리더 선출은 "한 번 리더를 정해두고 그 인스턴스가 계속 실행"이다. 잡이 많고 자주 도는 환경에서는 매번 락을 잡는 비용을 줄일 수 있다.

### 패턴 4: 외부 스케줄러 / 전용 인스턴스

조율 자체를 애플리케이션 밖으로 빼는 방법.

- **Kubernetes CronJob**: cron 시각에 단발성 Pod를 하나만 띄워 잡을 실행. 인스턴스 수와 무관하게 항상 1회.
- **전용 스케줄러 인스턴스**: 배포 프로파일로 한 대만 `scheduler` 역할을 켜고 나머지는 끈다 (`@Profile("scheduler")`). 단순하지만 그 한 대가 죽으면 잡이 멈추는 단일 장애점이 된다.
- **Quartz 클러스터 모드**: JDBC JobStore를 공유해 Quartz가 자체적으로 클러스터 잡 분배를 처리. 트리거/잡 상태를 DB에 저장한다.

---

## 설계·운영 체크포인트

- **멱등성을 포기하지 않는다.** 락은 중복 실행 확률을 크게 낮추지만 0으로 만들지는 못한다. 잡 결과가 "여러 번 실행돼도 안전"하도록 설계한다. 예: INSERT 대신 UPSERT, 처리 여부 플래그 확인 후 진행.
- **lockAtMostFor는 잡의 최악 실행 시간보다 길게.** 잡이 평소 2분이라도 외부 API 지연으로 8분 걸릴 수 있으면 상한을 10분 이상으로 둔다.
- **시계 동기화(NTP)를 확인한다.** 분산 락의 TTL과 cron 트리거 모두 각 노드의 시계에 의존한다. 노드 간 시계가 수 초씩 벌어지면 lockAtLeastFor로 방어하더라도 경계 사례가 생긴다.
- **graceful shutdown과 잡 중단.** 배포·스케일 인으로 인스턴스가 내려갈 때 실행 중이던 잡이 중간에 끊기면 락은 lockAtMostFor 이후에야 풀린다. 그동안 잡이 재실행되지 못할 수 있으니 상한 시간과 배포 주기를 함께 고려한다.
- **관측 가능성.** 어느 인스턴스가 잡을 실제로 실행했는지, 락 획득에 실패한 인스턴스가 몇이었는지 로그·메트릭으로 남긴다. 중복 실행 사고는 "한 번만 돌았는지"를 사후에 증명할 수 있어야 빨리 잡힌다.
- **락 저장소의 가용성이 새 의존성이 된다.** ShedLock JDBC를 쓰면 그 DB가, Redis 락을 쓰면 Redis가 스케줄 실행의 단일 의존점이 된다. 저장소 장애 시 잡이 아예 안 도는 것과 중복 실행 중 무엇이 더 위험한지 잡별로 판단한다.

---

## 패턴 선택 가이드

| 상황 | 권장 패턴 |
|---|---|
| 일반적인 Spring `@Scheduled` 중복 방지 | ShedLock (JDBC 또는 Redis 락 저장소) |
| 이미 Redis 분산 락 인프라 보유 | 직접 락 또는 ShedLock Redis provider |
| 잡이 많고 자주 돌아 매번 락 경합이 부담 | 리더 선출 |
| 애플리케이션과 무관하게 1회 실행 보장 | Kubernetes CronJob 등 외부 스케줄러 |
| 복잡한 잡 스케줄·재시도·이력 관리 필요 | Quartz 클러스터 모드 |

대부분의 백엔드 서비스에서 첫 선택은 ShedLock이다. 추가 인프라 없이 기존 DB만으로 시작할 수 있고, 목적이 "스케줄 중복 방지" 하나로 명확하기 때문이다.

---

## 점검 질문

1. 인스턴스 3대 환경에서 `@Scheduled(cron=...)` 잡은 몇 번 실행되는가? 왜 그런가?
2. ShedLock의 `lockAtMostFor`와 `lockAtLeastFor`는 각각 어떤 장애 시나리오를 막기 위한 값인가?
3. 분산 락을 걸었는데도 잡이 두 번 실행될 수 있는 경우를 두 가지 이상 설명해 보라. (락 TTL, 시계 차이, GC 멈춤 등)
4. 락을 걸었으니 멱등성은 신경 쓰지 않아도 된다 — 이 주장의 문제점은?
5. 리더 선출 방식과 매 실행 락 경합 방식의 trade-off는 무엇인가?
6. Kubernetes CronJob으로 잡을 빼면 애플리케이션 내부 `@Scheduled` 대비 무엇을 얻고 무엇을 잃는가?

---

## 실습 아이디어

- 로컬에서 같은 Spring Boot 앱을 포트만 바꿔 2개 띄우고, `@Scheduled(fixedRate=5000)` 잡에 인스턴스 ID와 실행 시각을 로그로 찍어 중복 실행을 눈으로 확인한다.
- 같은 앱에 ShedLock JDBC를 붙이고 `shedlock` 테이블의 `locked_by`를 관찰하며, 매 실행마다 어느 인스턴스가 락을 잡는지 추적한다.
- `lockAtMostFor`를 잡 실행 시간보다 짧게 일부러 설정해 두 인스턴스가 겹쳐 실행되는 상황을 재현하고, 값을 늘려 해소되는지 확인한다.
