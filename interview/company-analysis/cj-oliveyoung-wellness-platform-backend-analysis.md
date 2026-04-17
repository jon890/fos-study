# [초안] CJ 올리브영 웰니스개발팀 백엔드 실무 분석 — 면접 준비용 팀 이해 가이드

> 작성일: 2026-04-17 | 면접일: 2026-04-21
> 목적: 팀이 실제로 어떤 문제를 풀고 있는지 추론하고, 후보자 경험과의 연결점을 정리한다.

---

## 이 문서를 읽는 법

채용 공고와 기술 블로그 글 4편, 그리고 올리브영 기술 스택 시그널을 분석해 웰니스개발팀이 실제 운영 중인 시스템의 구조와 책임 범위를 역방향으로 추론했다. 단순한 공고 요약이 아니라 "이 팀이 지금 어떤 백엔드 엔지니어링 문제를 안고 있는가"를 이해하는 것이 목표다. 면접관은 팀의 실제 업무를 알고 있다. 후보자가 그 맥락을 이해하고 있다는 신호를 주는 것과 그렇지 않은 것은 차이가 크다.

---

## 1. 팀의 비즈니스·도메인 범위

커머스플랫폼유닛 웰니스개발팀은 온라인몰의 핵심 구매 경험을 담당한다. 1,600만 명 이상 고객이 사용하는 플랫폼이고, 올영세일 같은 이벤트 기간에는 평소 대비 10배 트래픽이 발생한다는 점이 기술 블로그에서 구체적으로 언급됐다. 이 수치는 시스템 설계 방향을 결정짓는다.

**도메인 범위 추론**:
- **상품 관리**: 상품 정보, 가격, 재고, 카테고리 계층 구조 관리. 상품 수가 많고 업데이트 빈도가 높다면 DB 쓰기 부하와 캐시 무효화가 핵심 문제다.
- **전시 로직**: 상품 큐레이션, 기획전, 배너, 추천 목록. 어떤 상품을 어느 위치에 보여줄지 결정하는 비즈니스 규칙이 복잡하다.
- **검색 엔진 연동**: 공고에 "검색 엔진 연동"이 명시돼 있다. 별도 검색 인프라(Elasticsearch 계열)와 상품 색인 동기화 파이프라인이 존재할 가능성이 높다.
- **인증/세션 관리**: Spring Authorization Server와 Spring Session이 스택에 포함된다. OAuth2 기반 인증 서버를 자체 운영 중이고, 기술 블로그에서 대규모 트래픽 중 무중단 OAuth2 전환 경험을 공개했다.
- **알림 시스템**: SQS 기반 알림톡 파이프라인이 별도 서비스로 운영되고 있다. 이벤트 드리븐 아키텍처로 구성돼 있으며, 데드락 분석 사례까지 블로그에 공개할 정도면 실제 운영 문제를 겪은 영역이다.
- **도메인 간 데이터 연동**: MSA 구조에서 상품 정보, 재고, 가격 같은 도메인 데이터를 여러 서비스가 공유해야 한다. Kafka 이벤트 + Redis 캐시 하이브리드 설계를 실제로 사용 중이라는 것이 기술 블로그에서 확인됐다.

---

## 2. 팀이 실제로 하는 백엔드 업무

공고의 "담당 업무" 항목은 형식적인 나열이다. 기술 블로그와 스택을 교차 분석하면 실제 업무가 훨씬 구체적으로 보인다.

### 2-1. 서비스 간 데이터 동기화 설계

MSA 환경에서 상품 도메인 데이터가 바뀔 때 downstream 서비스들이 최신 상태를 빠르게 반영해야 한다. 올리브영 기술 블로그에서 공개한 설계 원칙은 다음과 같다:

- 변경 빈도가 낮은 데이터 → **Cache-Aside 패턴** (Redis TTL 기반)
- 실시간 변경이 필요한 이벤트 데이터 → **Kafka 이벤트** 수신 후 Redis Key만 캐싱 → 실제 데이터는 선택적 API 호출

이 설계의 핵심은 "모든 데이터를 복제하지 않는다"는 것이다. Kafka 이벤트로 변경 사실만 전달하고 Redis에 해당 Key를 캐시해 불필요한 API 호출을 줄이는 방식이다. 이 패턴은 실시간성과 정확성을 동시에 확보하면서 서비스 간 결합도를 낮춘다.

백엔드 엔지니어로서 이 팀에서 해야 하는 일은 단순히 Kafka Consumer를 붙이는 것이 아니다. 어떤 데이터를 어떤 방식으로 동기화할지 설계 판단을 내리고, 캐시 무효화 시점과 데이터 정합성 보장 수준을 결정하는 것이다.

### 2-2. 대규모 트래픽 대응 및 안정성 확보

올영세일 기간 10배 트래픽은 평소 시스템으로는 버티지 못한다. 기술 블로그에서 공개된 대응 전략:

- **Feature Flag (전략 패턴)**: 런타임 DB 설정 변경만으로 코드 배포 없이 기능 전환. 코드 변경 없이 동작을 바꿀 수 있어야 하기 때문에 전략 패턴을 인터페이스 수준에서 설계해야 한다.
- **Shadow Mode**: 새 시스템을 실제 트래픽 병행 실행 후 점진적 전환. 기존 응답과 새 응답을 비교해 검증하는 구조다.
- **Resilience4j 3단계 보호**: Timeout → Retry → Circuit Breaker 순서로 장애 격리. 단순히 Circuit Breaker를 "달면 된다"가 아니라 Timeout 임계값, Retry 횟수, Circuit 열리는 실패율 임계값을 각 서비스 특성에 맞게 튜닝하는 작업이 따른다.
- **Jitter(±30초 랜덤)**: 캐시 TTL 만료가 동시에 발생하는 Thunder Herd 문제를 랜덤 오프셋으로 분산. P95 레이턴시 50ms, 성공률 100% 달성 사례가 있다.

이 팀에서의 업무는 "기능이 동작하게 만든다"가 아니라 "이벤트 기간에도 SLA를 지킨다"가 목표다.

### 2-3. 레거시 시스템 현대화

두 편의 기술 블로그 글이 레거시 개선을 다룬다.

- **SQS 알림톡 데드락 분석**: 이벤트 드리븐 아키텍처로 전환했지만 트랜잭션 경합으로 데드락이 발생했다는 뜻이다. 기존 동기 방식 코드가 비동기 큐 방식으로 전환되면서 트랜잭션 경계가 바뀌고, 예상치 못한 락 경합이 생기는 전형적인 레거시 현대화 문제다.
- **Spring 트랜잭션 동기화**: `TransactionSynchronizationManager`를 활용해 레거시 알림 발송 시스템을 개선했다. 트랜잭션 커밋 이후 알림 발송이 보장되도록 하는 패턴이다. `afterCommit()` 훅을 사용하지 않으면 롤백된 트랜잭션에서 알림이 발송되거나, 커밋 전 발송된 알림이 누락되는 문제가 생긴다.

이 팀에는 단기 피처 개발뿐 아니라 실제 운영 중인 레거시 시스템을 안전하게 개선하는 역할도 있다는 뜻이다.

---

## 3. 예상 아키텍처 패턴

기술 스택과 블로그 글을 종합하면 팀의 아키텍처 구조가 윤곽을 드러낸다.

```
[Client]
    │
    ▼
[API Gateway / BFF Layer]
    │
    ├──▶ [상품 서비스]    ─── Aurora Serverless (MySQL)
    │         │                    │
    │         └──▶ Kafka ──────▶ [도메인 데이터 Consumer]
    │                                    │
    ├──▶ [전시/큐레이션 서비스]     Redis Cache-Aside
    │
    ├──▶ [인증 서비스]    Spring Authorization Server
    │         └──▶ Spring Session (Redis 저장)
    │
    ├──▶ [알림 서비스]    AWS SQS
    │         └──▶ 알림톡 발송 (외부 API)
    │
    └──▶ [검색 연동]     검색 엔진 색인 동기화
```

각 서비스는 독립 배포 가능하고, Kafka를 통해 도메인 이벤트를 교환한다. Aurora Serverless는 MySQL 호환이므로 JPA + Hibernate 기반 ORM이 그대로 동작한다. Redis는 Cache-Aside 패턴의 중앙 캐시로 동작하며, SQS는 알림 같은 eventually consistent 처리에 사용한다.

**이 구조에서 백엔드 엔지니어가 실제로 부딪히는 문제들**:
- Kafka Consumer 그룹이 메시지를 처리하다 실패할 때 재처리 전략 (Dead Letter Queue, Retry Topic)
- Redis 캐시가 만료되거나 Eviction이 발생할 때 Cache Stampede 대응
- JPA를 통해 MySQL에 접근하는데 N+1 쿼리가 발생하거나 인덱스를 타지 않는 쿼리가 배포됐을 때 진단
- Aurora Serverless의 Auto Scaling 특성 (콜드 스타트 레이턴시, 최소 ACU 설정) 이해
- 서비스 간 분산 트랜잭션이 필요한 상황에서 Saga 패턴 또는 이벤트 소싱 적용 판단

---

## 4. Kafka / Redis / JPA / DB가 실제로 중요한 지점

### Kafka

단순한 "비동기 메시지 큐" 수준이 아니다. 올리브영에서 Kafka의 역할은 MSA 도메인 간 데이터 일관성 유지다. 상품이 업데이트됐을 때 전시 서비스, 검색 색인, 추천 시스템이 동시에 최신 상태를 알아야 한다면 Kafka 이벤트로 브로드캐스트하는 것이 가장 자연스러운 설계다.

**면접에서 확인하려는 것**: Kafka Producer/Consumer 사용 경험이 있는가보다, **이벤트 스키마 설계, at-least-once 처리의 멱등성 보장, Consumer Lag 모니터링** 같은 운영 실무 경험이 있는가다.

### Redis

Cache-Aside 패턴의 구체적인 구현을 이해하는 것이 중요하다. 단순히 `@Cacheable`을 붙이는 것과, Redis에 직접 접근하며 캐시 무효화 시점·TTL·Jitter를 세밀하게 제어하는 것은 다른 수준이다. 올리브영은 도메인 데이터의 변경 빈도와 라이프사이클을 분석해 캐싱 전략을 결정하는 접근을 사용한다.

**주의해야 할 패턴**:
- Cache miss 시 DB 조회 결과를 Redis에 쓰는 과정의 원자성 (SET NX 활용)
- 대규모 트래픽에서 TTL 만료가 동시 발생하는 Cache Stampede (Jitter, Lock-based refresh)
- Redis를 Spring Session 저장소로 사용할 때 세션 직렬화 형식과 데이터 크기 관리

### JPA / Hibernate

공고에 ORM과 도메인 모델링 경험이 필수 자격 요건으로 명시돼 있다. 웰니스 커머스 도메인은 상품-카테고리-옵션-재고-가격 관계가 복잡하다. 이 구조를 JPA 엔티티로 모델링하면 즉시 N+1 문제, LAZY/EAGER 로딩 전략, 복잡한 조인 쿼리 최적화 이슈가 따라온다.

**면접에서 자주 나오는 JPA 이슈**:
- `@OneToMany` 컬렉션 LAZY 로딩에서 N+1 발생 → `JOIN FETCH` 또는 `EntityGraph` 적용
- 대량 업데이트/삭제 시 `@Modifying` + JPQL 벌크 연산 vs 엔티티 단건 처리 성능 차이
- 영속성 컨텍스트 범위와 Dirty Checking이 예상치 못한 UPDATE를 발생시키는 케이스
- QueryDSL vs Criteria API vs 네이티브 쿼리 선택 기준

### DB (Aurora Serverless / MySQL)

자기 평가에서 DB가 약점 영역으로 분류돼 있다. 이 팀에서 Aurora Serverless는 MySQL 8 호환 RDS다. 따라서 MySQL 인덱스 설계, 실행 계획 분석, 트랜잭션 격리 수준 이해가 직결된다.

**올리브영 규모에서 DB가 실제 문제가 되는 시나리오**:

상품 검색 또는 카테고리 조회 쿼리에서 인덱스를 타지 않으면 수백만 행 풀스캔이 발생한다. 실행 계획을 보는 것이 기본이 돼야 한다.

```sql
-- 문제 상황: 카테고리 + 가격 범위 + 정렬 복합 조건
SELECT p.id, p.name, p.price
FROM product p
WHERE p.category_id = 100
  AND p.price BETWEEN 10000 AND 50000
  AND p.status = 'ACTIVE'
ORDER BY p.created_at DESC
LIMIT 20;

-- EXPLAIN으로 확인해야 할 것:
-- 1. type이 ref/range인가, 아니면 ALL(풀스캔)인가
-- 2. rows 추정치가 실제 결과 수보다 과도하게 크지 않은가
-- 3. Extra에 Using filesort가 있으면 ORDER BY를 인덱스로 처리 못한 것

-- 커버링 인덱스 설계:
-- (category_id, status, price, created_at)으로 복합 인덱스 설계 시
-- WHERE 조건 컬럼 + ORDER BY 컬럼까지 인덱스에 포함해 filesort 제거
CREATE INDEX idx_product_category_status_price_created
ON product(category_id, status, price, created_at);
```

트랜잭션 격리 수준은 알림톡 데드락 사례에서 직접 언급됐다. 데드락은 두 트랜잭션이 서로 상대방이 가진 락을 기다릴 때 발생한다. InnoDB의 기본 격리 수준인 REPEATABLE READ에서는 gap lock이 함께 동작해 INSERT 경합 시 예상치 못한 데드락이 생기기도 한다.

---

## 5. 팀의 실제 업무에서 나오는 예상 면접 질문

### 아키텍처·설계 계열

**Q. MSA 환경에서 서비스 간 데이터 정합성을 어떻게 보장하나요? Kafka를 사용할 때 at-least-once 처리에서 멱등성은 어떻게 확보했나요?**

이 질문은 Kafka 사용 여부가 아니라 이벤트 중복 수신 시 어떻게 동일한 결과를 보장하는지를 묻는다. DB 유니크 키 기반 중복 체크, 이벤트 ID 기반 처리 이력 테이블, 또는 비즈니스 규칙상 자연스럽게 멱등한 연산인지를 설명할 수 있어야 한다.

**Q. Cache-Aside 패턴에서 캐시 무효화 시점을 어떻게 결정했고, Cache Stampede는 어떻게 방어했나요?**

올영세일 기간에 대규모 캐시 만료가 동시 발생하면 DB에 폭발적인 쿼리가 몰린다. Jitter 적용, Redis SETNX 기반 refresh lock, 또는 Soft TTL + 백그라운드 갱신 같은 전략을 알고 있어야 한다.

**Q. Feature Flag를 전략 패턴으로 구현할 때 런타임 DB 설정 변경만으로 동작을 바꾸는 구조를 설명해 주세요.**

기술 블로그에서 직접 공개한 설계다. `Strategy` 인터페이스를 정의하고, DB에서 설정 값을 읽어 적절한 구현체를 선택하는 구조를 코드 수준에서 설명할 수 있어야 한다. 스프링의 `ApplicationContext`에서 빈을 동적으로 선택하는 방법까지 연결하면 더 좋다.

### 성능·DB 계열

**Q. JPA를 사용하면서 N+1 문제를 발견한 경험과 해결 방법을 설명해 주세요.**

핵심은 단순히 "JOIN FETCH를 썼다"가 아니라, N+1이 어떤 상황에서 발생하는지 이해하고 있는가다. `@OneToMany` 컬렉션을 JOIN FETCH로 가져올 때 페이지네이션과 충돌하는 문제(HibernateJpaDialect 경고), 이를 해결하기 위한 batch size 설정 또는 별도 쿼리 분리 전략까지 설명하면 깊이를 보여줄 수 있다.

**Q. EXPLAIN 실행 계획에서 무엇을 주로 확인하고, 어떤 지표가 개선 신호인가요?**

`type`, `key`, `rows`, `Extra` 컬럼의 의미를 실무 맥락으로 설명해야 한다. `type=ALL`이 풀스캔, `Using filesort`가 정렬 인덱스 미사용, `Using index`가 커버링 인덱스 활용이라는 것을 알고, 어떤 인덱스를 추가하면 개선되는지 판단하는 과정을 설명할 수 있어야 한다.

**Q. 트랜잭션 경합으로 인한 데드락을 경험한 적이 있나요? 원인을 어떻게 진단했나요?**

MySQL의 `SHOW ENGINE INNODB STATUS` 또는 `information_schema.INNODB_LOCKS`로 데드락 로그를 확인하는 방법, 트랜잭션이 락을 획득하는 순서를 역추적하는 접근법, 해결책(트랜잭션 순서 통일, 락 범위 축소, 격리 수준 조정)을 연결해야 한다.

### 운영·장애 대응 계열

**Q. Resilience4j Circuit Breaker를 적용할 때 임계값(실패율, Slow Call 기준)을 어떻게 결정했나요?**

Circuit Breaker를 "달았다"가 아니라 어떤 기준으로 열고 닫을지 서비스 특성에 맞게 결정하는 판단 과정을 묻는다. Slow Call 임계값이 너무 낮으면 일시적 지연에도 Circuit이 열려 오히려 가용성을 해친다.

**Q. Spring `TransactionSynchronizationManager`의 `afterCommit()` 훅을 사용한 경험이 있나요?**

올리브영 기술 블로그에서 직접 언급한 패턴이다. 트랜잭션 커밋 이후 알림 발송이 보장되어야 하는 시나리오에서 `afterCommit()` 훅이 왜 필요한지, 트랜잭션 내부에서 직접 외부 시스템 호출을 하면 어떤 문제가 생기는지 설명할 수 있어야 한다.

---

## 6. 후보자 경험과 역할 매핑

### 슬롯팀 경험 → 올리브영 맥락

| 슬롯팀 경험 | 올리브영 맥락 연결 |
|---|---|
| RCC 캐시 시스템 (DB 캐시 + 비동기 생성) | Redis Cache-Aside + 비동기 캐시 워밍업 패턴 |
| DB 유니크 키 기반 동시성 처리 | 이벤트 멱등 처리, 중복 방지 설계 |
| StampedLock으로 정적 캐시 갱신 보호 | 캐시 Refresh 중 읽기 일관성 보장 |
| RabbitMQ 이벤트 기반 캐시 동기화 | Kafka Consumer 이벤트 처리 패턴 동일 구조 |
| SlotTemplate/BaseSlotService 추상화 | Feature Flag 전략 패턴, MSA 서비스 인터페이스 설계 |
| AliasMethod + JMH 기반 성능 측정 | DB 쿼리 최적화, 실행 계획 기반 성능 분석 접근법 |

**연결 방식**: "슬롯팀에서 캐시 시스템을 직접 설계했습니다"로 끝내지 말고, "당시 겪은 Cache Stampede 유사 문제를 DB 유니크 키와 비동기 사전 생성으로 해결한 패턴이 올리브영의 Cache-Aside + 이벤트 기반 갱신 전략과 같은 설계 원리를 공유한다고 생각합니다"처럼 연결해야 한다.

### AI 서비스팀 경험 → 올리브영 맥락

| AI 서비스팀 경험 | 올리브영 맥락 연결 |
|---|---|
| Spring Batch 11-Step 실패 격리 설계 | 대용량 처리 파이프라인 (상품 색인, 가격 배치 등) |
| AsyncItemProcessor (I/O 바운드 병렬화) | 외부 API 병렬 호출, Kafka 이벤트 병렬 Consumer |
| TransactionSynchronizationManager 이해 | 올리브영 기술 블로그에서 직접 언급한 패턴 |
| OCR 서버 Graceful Shutdown (Envoy + gRPC) | MSA 배포 중 무중단 서비스 유지 |

**Spring 트랜잭션 동기화 연결**: `TransactionSynchronizationManager` 경험은 올리브영 기술 블로그에서 직접 언급된 패턴과 정확히 일치한다. 면접에서 먼저 꺼낼 수 있는 가장 직접적인 공통점이다.

---

## 7. 면접에서 경험을 꺼내는 방식

경험 기반 질문에서 흔한 실수는 경험 자체를 설명하는 데 그치는 것이다. 면접관은 "이 사람이 우리 팀에서 비슷한 문제를 만났을 때 어떻게 행동할지"를 보고 싶어한다.

**나쁜 패턴**: "슬롯 결과 캐시 시스템을 설계했고 DB 유니크 키로 동시성을 처리했습니다."

**좋은 패턴**: "분산 환경에서 캐시 생성이 중복 발생하는 동시성 문제를 해결해야 했는데, 낙관적 락 대신 DB 유니크 키 + 예외 처리 조합을 선택했습니다. 이 시스템에서 중요한 건 정확히 하나의 레코드가 아니라 충분한 양의 캐시가 존재하는 것이었고, 중복 생성 예외는 다른 인스턴스가 이미 처리했다는 신호이므로 재시도 없이 넘어가는 것이 맞았습니다. 분산 락은 단순성 대비 운영 비용이 높고 이 케이스에는 과잉이었습니다. 올리브영에서 Cache-Aside를 구현할 때도 Redis SETNX 기반 접근과 이 방식을 상황에 따라 선택하는 판단 기준이 같다고 생각합니다."

이 차이는 "내가 무엇을 했다"가 아니라 "왜 그 결정을 했고, 다른 상황에서도 같은 판단 기준을 적용할 수 있다"를 보여주는 데 있다.

---

## 8. 학습 우선순위 리스트

면접까지 4일 남았다. 전체를 다 볼 수 없으므로 팀의 실제 문제와 후보자 약점 교차점에 집중한다.

### 최우선 (1-2일 내 반드시)

1. **MySQL 실행 계획 읽기**: `EXPLAIN` 결과의 `type`, `key`, `rows`, `Extra` 컬럼 해석. 특히 `Using filesort`, `Using temporary`, `Using index`의 의미와 인덱스 추가로 어떻게 바뀌는지 실습.

2. **JPA N+1 진단과 해결 패턴**: LAZY 컬렉션에서 N+1이 왜 발생하는지, `JOIN FETCH`와 `@BatchSize` 각각 어떤 상황에 적합한지. 페이지네이션 + JOIN FETCH 충돌 케이스 이해.

3. **Redis Cache-Aside 구현**: Spring에서 `RedisTemplate` 또는 `@Cacheable`을 사용하는 것의 차이. TTL 설정, Jitter 적용, 캐시 Miss 시 DB 조회와 캐시 저장의 순서와 원자성.

4. **Spring 트랜잭션 동기화**: `TransactionSynchronizationManager.registerSynchronization()` 패턴. `afterCommit()`과 `afterCompletion()`의 차이. 트랜잭션 내부에서 외부 시스템 호출을 하면 안 되는 이유.

### 중간 우선순위 (시간이 되면)

5. **Kafka 기본 운영 개념**: Consumer Group, Offset Commit 방식 (auto vs manual), Retry Topic / DLQ 구조. 슬롯팀의 RabbitMQ 경험을 Kafka 개념에 매핑.

6. **Resilience4j Circuit Breaker 설정**: Sliding Window 방식 (count-based vs time-based), Open/Half-Open 전환 조건, Bulkhead 패턴.

7. **복합 인덱스 설계 원칙**: 선두 컬럼 선택 기준, 커버링 인덱스 설계, 인덱스 선택도(Cardinality) 고려. 슬롯팀의 복합 인덱스 설계 경험 연결.

### 여유 시간에

8. **MSA 분산 트랜잭션 패턴**: Saga (Choreography vs Orchestration), Two-Phase Commit의 한계, Outbox 패턴.

9. **Aurora Serverless 특성**: Auto Scaling, 최소/최대 ACU 설정, 콜드 스타트 레이턴시, MySQL 8 호환 범위.

---

## 체크리스트

- [ ] `EXPLAIN` 결과를 보고 인덱스 추가 방향을 즉시 판단할 수 있다
- [ ] JPA N+1 문제가 발생하는 코드를 보면 원인을 설명하고 3가지 해결 방법을 제시할 수 있다
- [ ] Redis Cache-Aside 패턴을 직접 구현한다고 했을 때 코드 수준으로 설명할 수 있다
- [ ] Cache Stampede가 무엇이고 Jitter로 어떻게 방어하는지 설명할 수 있다
- [ ] `TransactionSynchronizationManager`의 `afterCommit()` 훅을 언제 쓰는지, 쓰지 않으면 어떤 문제가 생기는지 설명할 수 있다
- [ ] Kafka Consumer에서 at-least-once 처리 시 멱등성을 보장하는 방법 2가지 이상을 설명할 수 있다
- [ ] Resilience4j Circuit Breaker의 상태 전이 (Closed → Open → Half-Open)와 각 상태의 동작을 설명할 수 있다
- [ ] 슬롯팀 RCC 캐시 경험을 올리브영 Cache-Aside 설계 맥락으로 재프레이밍해서 1분 안에 말할 수 있다
- [ ] AI 서비스팀 Spring Batch 경험을 대용량 배치 처리 맥락으로 연결할 수 있다
- [ ] 올리브영 기술 블로그 4편을 읽고 각각의 핵심 설계 결정을 한 문장으로 요약할 수 있다

---

저장 위치: `sources/fos-study/interview/company-analysis/cj-oliveyoung-wellness-platform-backend-analysis.md`

**우선순위 요약**: 남은 4일 기준으로 DB EXPLAIN 읽기 + JPA N+1 + Redis Cache-Aside + Spring 트랜잭션 동기화가 가장 확실한 투자다. `TransactionSynchronizationManager` 경험은 올리브영 기술 블로그와 직접 겹치는 유일한 지점이므로 면접에서 먼저 꺼낼 카드로 준비해 두는 것이 좋다.
