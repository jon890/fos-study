# [초안] 시니어 Java 백엔드 면접 마스터 플레이북 — 김병태

> 대상 직무: 시니어 Java 백엔드 (재사용 가능한 공통 자료)
> 가장 가까운 면접: CJ 올리브영 커머스플랫폼유닛 Back-End (경력) — 2026-04-21
> 근거: [`resume/2603_김병태_이력서_v4.md`](../../resume/2603_김병태_이력서_v4.md), `task/nsc-slot/**`, `task/ai-service-team/**`, [`interview/cj-oliveyoung-wellness-backend.md`](../cj-oliveyoung-wellness-backend.md)

---

## 1. 1분 자기소개 (60초, 약 280자)

> NHN에서 4년간 Java 백엔드 개발을 해온 김병태입니다. 소셜 카지노 슬롯팀에서는 Spring Boot 멀티모듈 MSA 환경에서 신규 슬롯 게임 5종 이상과 RTP 캐시 시스템(RCC)을 만들었고, 다중 서버 인메모리 캐시 정합성 문제를 RabbitMQ Fanout과 StampedLock으로 직접 풀었습니다. 이후 AI 서비스팀으로 이동해 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 11개 Step과 AsyncItemProcessor로 처음부터 설계·구현했고, 최근에는 12일 동안 혼자 AI 웹툰 제작 도구 MVP를 Next.js와 Gemini, Claude Code 하네스 기반 에이전트 팀으로 199 plan·760 커밋까지 밀어냈습니다. 설계부터 운영, AI 도구 도입·확산까지 전 과정을 주도한 경험을 살려 기여하고 싶습니다.

---

## 2. 90초 자기소개 (강약 포인트 한두 개 추가)

> NHN에서 4년간 Java 백엔드 개발을 해온 김병태입니다. 슬롯팀에서는 Spring Boot 멀티모듈 MSA 환경에서 신규 슬롯 게임 5종 이상을 개발했고, 성능·동시성 이슈를 직접 풀었습니다. 다중 서버 인메모리 캐시 정합성 문제에서는 Hibernate `PostCommitUpdateEventListener`로 커밋 후에만 RabbitMQ Fanout Exchange로 변경 ID를 발행하고, 갱신 중 조회 충돌은 StampedLock + 2.5초 tryReadLock 타임아웃으로 해결했습니다. Kafka 쪽에서는 즉시 응답이 필요한 흐름과 후처리 흐름을 분리하고, `@TransactionalEventListener(AFTER_COMMIT)`으로 커밋 이후에만 발행 + `Propagation.REQUIRES_NEW` 기반 Dead Letter Store + 스케줄러 재시도 구조로 비동기 흐름의 신뢰성을 확보했습니다.
>
> AI 서비스팀으로 옮긴 뒤에는 Confluence → OpenSearch RAG 파이프라인을 11개 Step으로 분리해 처음부터 설계·구현했습니다. I/O 바운드인 임베딩 호출은 `AsyncItemProcessor`로 병렬화하고, 메타데이터 차이는 전략 패턴(`EmbeddingMetadataProvider`)으로 흡수해 OCP를 지켰습니다. 최근에는 12일 동안 혼자 Next.js 16 · React 19 · Prisma 7 · Gemini 기반 AI 웹툰 제작 도구 MVP를 만들었는데, Claude Code 하네스 위에서 planner·critic·executor·docs-verifier 4인 에이전트 팀을 조율해 199 plan / 760 커밋을 소화했습니다. Gemini Pro 우선 + 429 fallback 전략, 전역 Rate Limit Tracking, Project 단위 Context Cache, Promise.allSettled 기반 60컷 부분 성공 생성, 글콘티 Grounding 재주입으로 환각을 구조적으로 차단한 게 핵심이었습니다.
>
> 강점은 두 가지입니다. 하나는 기능 구현에 그치지 않고 추상 템플릿·전략 패턴·테스트 인프라까지 구조를 다져 팀 속도를 높이는 것이고, 다른 하나는 AI 도구를 단순히 쓰는 게 아니라 파이프라인으로 설계·운영하는 관점입니다. 대규모 커머스 트래픽 환경에서 그동안의 캐시·이벤트·대용량 배치 경험을 빠르게 적용하고 싶습니다.

---

## 3. 핵심 커리어 요약 (최근 → 과거)

| 기간 | 소속 | 역할 | 대표 기술 결정 |
|------|------|------|----------------|
| 2026.04 (12일) | NHN AI 서비스팀 | 단독 풀스택 MVP 리드 | Next.js 16 + Gemini + Claude Code 하네스 기반 4인 에이전트 팀(planner/critic/executor/docs-verifier)으로 199 plan/760 커밋. Gemini Pro 기본 + 429 fallback, 전역 Rate Limit Tracking, Project Context Cache, Grounding 재주입, Container/Presenter + 파일 소유권 매트릭스 |
| 2026.01 ~ 2026.03 | NHN AI 서비스팀 | RAG 배치 파이프라인 설계·구현 | Spring Batch 11 Step + `AsyncItemProcessor` 병렬 임베딩, `@JobScope` 인메모리 홀더, ADF → Markdown 변환, 전략 패턴 기반 `EmbeddingMetadataProvider`, 삭제 동기화 (`status=DELETED,TRASHED` 재사용) |
| 2025.12 ~ | NHN AI 서비스팀 | 백엔드 | OCR 서버 Graceful Shutdown 503 수정, 임베딩 메타데이터 blocklist → allowlist 전환 |
| 2025.07 ~ 2025.10 | NHN NSC 슬롯팀 | RCC·엔진 추상화 리드 | RTP Cache Control 6종 대응, `SlotTemplate`/`BaseSlotService`/`ExtraConfig` 분리, `StampedLock` 도입으로 refresh 중 NPE 제거, Alias 테이블 `IN`절 일괄 조회 |
| 2025.02 ~ 2025.08 | NHN NSC 슬롯팀 | 신규 슬롯 5종 | Slot 36/38/41/44/47, Cursor Rules 20+로 AI 에이전트 단독 구현 3종, 스핀 최적화(AliasMethod O(1), `SecureRandom` → `ThreadLocalRandom`), 시뮬레이터 OOM 해결(Welford's Online Algorithm) |
| 2024.06 ~ 2024.12 | NHN NSC 슬롯팀 | 합류 첫 해 | Slot 21/33 신규 게임, Admin Alpha↔Real 비교/복사, BuyFeature 티켓·시나리오 스핀 플랫폼 기능, 다중 서버 캐시 정합성 (RabbitMQ Fanout + StampedLock), Kafka 비동기 발행 (AFTER_COMMIT + Dead Letter Store 재시도) |

---

## 4. 강점 (구체 증거 포함)

### 4-1. 동시성·정합성 문제를 구조로 해결한다

- **문제**: 다중 서버가 각자 정적 설정 데이터를 인메모리 캐시로 가지는 상황에서, 어드민 변경 시 갱신 중 조회 요청이 일시적 정합성 오류를 냄.
- **해결**: `PostCommitUpdateEventListener`로 커밋 후에만 RabbitMQ Fanout Exchange로 변경 ID 발행 → 각 인스턴스가 자신의 큐에서 수신 후 해당 항목만 선택 갱신. 갱신/조회 경합은 `StampedLock` writeLock + `tryReadLock(2500ms)` 타임아웃으로 흡수. `StaticDataManager` 인터페이스로 init/refresh/clear 책임 분리 → 새 캐시 타입 추가해도 기존 코드 무변경.
- **커머스 전이 관점**: 상품 캐시로 확장할 때는 Caffeine(L1) + Redis(L2) **2-tier 구조**로 피크 TPS를 흡수하고, 인스턴스 수가 수십~백 대 규모로 늘어나면 RabbitMQ Fanout 대신 Kafka 토픽(인스턴스마다 독립 consumer group)이나 Redis Pub/Sub이 더 적합하다는 점을 인지하고 있습니다. Cache Stampede는 핫키에 대한 probabilistic early expiration + single-flight로 대응.
- **증거**: [`resume/2603_김병태_이력서_v4.md`](../../resume/2603_김병태_이력서_v4.md) 문항 1, [`task/nsc-slot/slot-engine-abstraction.md`](../../task/nsc-slot/slot-engine-abstraction.md) "StaticDataLoader 개선", [`architecture/cache-strategies.md`](../../architecture/cache-strategies.md) 개인 학습 기록.

### 4-2. Kafka 비동기 흐름의 신뢰성을 구조로 확보했다

- 금액/레벨처럼 즉시 응답이 필요한 로직은 DB 트랜잭션 내, 미션·통계·알림 후처리는 Kafka로 분리.
- `@TransactionalEventListener(AFTER_COMMIT)`으로 커밋 이후에만 발행해 롤백된 트랜잭션 이벤트의 외부 유출을 차단. 전송 실패 시 `Propagation.REQUIRES_NEW` 별도 트랜잭션으로 실패 메시지를 DB에 저장하고 스케줄러가 재전송하는 **Dead Letter Store + 재시도 구조**. traceId 동반 저장으로 실패 원인 추적.
- **정식 Transactional Outbox와의 차이 인지**: AFTER_COMMIT과 Kafka 발행 사이의 짧은 구간(JVM 크래시·SIGKILL)에 대한 유실 가능성이 남음. 해당 도메인(통계·알림)의 특성상 수용 가능한 수준으로 판단한 설계 선택이며, 커머스처럼 정합성이 더 엄격한 도메인에서는 이벤트를 비즈니스 데이터와 같은 트랜잭션에 저장 후 relay하는 **정식 Outbox 구조**로 강화할 계획입니다.
- 증거: [`resume/2603_김병태_이력서_v4.md`](../../resume/2603_김병태_이력서_v4.md) 문항 1, [`architecture/distributed-transaction-outbox-pattern.md`](../../architecture/distributed-transaction-outbox-pattern.md) 개인 학습 기록.

### 4-3. 대용량 배치 파이프라인을 처음부터 설계했다

- 11개 Step 분리로 실패 격리: 댓글 Step이 실패해도 페이지 Step 결과는 살아있고, 재시작 시 실패 지점부터 이어감.
- I/O 바운드 임베딩 호출은 `AsyncItemProcessor` + `AsyncItemWriter`로 병렬화. 청크 내 문서를 스레드풀에서 동시 처리.
- Reader에 `ItemStream` 구현으로 커서 위치를 `ExecutionContext`에 저장 → 중간 실패 후에도 마지막 처리 지점에서 재시작.
- `@JobScope` 홀더(`ConfluenceJobDataHolder`) 도입으로 `JobExecutionContext` 직렬화 부하 회피 (경량 커서 상태 vs 도메인 데이터 분리 판단).
- 증거: [`task/ai-service-team/rag-vector-search-batch.md`](../../task/ai-service-team/rag-vector-search-batch.md).

### 4-4. 성능 의사결정을 수치 기반으로 한다

- 스핀 성능: `AliasMethod`로 가중치 샘플링을 O(n)→O(1)로, `SecureRandom` → `ThreadLocalRandom` 전환.
- 시뮬레이터 OOM: `List<Long> winmoneyList` 누적 구조를 Welford's Online Algorithm 기반 1-pass 통계로 교체해 메모리 상수화.
- Context Cache: 원작 소설(수십만 토큰)을 Gemini Project 단위 cachedContent로 묶어 Analysis/Content-review/Treatment/Conti/Continuation 5단계 공유 → 재결제 비용 제거.
- 통합 분석: Step1 소설 분석 5개 영역을 단일 Structured Output 호출로 합쳐 토큰 75% 절감, 26.8s → 13.1s.
- 증거: [`task/nsc-slot/slot-spin-performance.md`](../../task/nsc-slot/slot-spin-performance.md), [`task/nsc-slot/slot-simulator-oom.md`](../../task/nsc-slot/slot-simulator-oom.md), [`task/ai-service-team/webtoon-maker-ai-pipeline.md`](../../task/ai-service-team/webtoon-maker-ai-pipeline.md) (ADR-059, ADR-069).

### 4-5. 에이전트 파이프라인을 설계·운영하는 엔지니어

- "Cursor Rules를 쓴다"가 아니라 20개 이상 직접 구축해 슬롯 도메인 컨텍스트를 문서화하고, 이 규칙 위에서 신규 게임 3종을 에이전트 단독으로 구현.
- AI 웹툰 MVP에서는 Claude Code 하네스 위에 **planner → critic → executor → docs-verifier** 4역할 에이전트 팀을 조립. `/planning` → `/plan-and-build` → `/build-with-teams` → `/integrate-ux`로 vibe 코딩을 spec 기반 코딩으로 단계적 전환.
- 개인 성과에 그치지 않고 팀에 활용 방법을 전파해 반복 개발 사이클 단축.
- 증거: [`task/nsc-slot/ai-tool-adoption.md`](../../task/nsc-slot/ai-tool-adoption.md)(목차), [`task/ai-service-team/webtoon-maker-ai-pipeline.md`](../../task/ai-service-team/webtoon-maker-ai-pipeline.md) "하네스 진화".

### 4-6. 테스트 인프라를 안전망으로 만든다

- 슬롯 도메인: 제네릭 추상 테스트 클래스 `AbstractSlotTest`로 게임 타입별 초기화 자동화, 총 447개 테스트 파일에서 핵심 비즈니스 로직 / AOP 검증 / Kafka 이벤트 발행 / Redis 통합 테스트까지 커버.
- 배치 도메인: `@BatchComponentTest` 커스텀 애노테이션으로 외부 API만 모킹하고 Spring 컨텍스트에서 실제 빈을 엮어 테스트해 `@Qualifier` 충돌·`@StepScope` 빈 중복 같은 실수를 빌드 타임에 차단.
- 증거: [`resume/2603_김병태_이력서_v4.md`](../../resume/2603_김병태_이력서_v4.md) 문항 1, [`task/ai-service-team/rag-vector-search-batch.md`](../../task/ai-service-team/rag-vector-search-batch.md) "테스트 전략".

---

## 5. 약점 (거짓 약점 금지 — 실제 개선 중인 것)

### 5-1. 초대형 트래픽 환경의 "운영" 경험 폭

- 슬롯/AI 서비스 모두 사내·B2C 환경이긴 하지만, **초 단위 수만 TPS 수준의 커머스 피크 트래픽**을 내가 직접 튜닝하며 살려낸 경험은 아직 부족합니다.
- 보완: 최근 올리브영 기술 블로그의 MSA 데이터 연동 전략, 무중단 OAuth2 전환(Feature Flag + Shadow Mode + Resilience4j 3단 보호 + ±30s Jitter로 Peak TPS 40% 감소) 글을 정독하며, 슬롯에서 푼 캐시 정합성 문제가 커머스 상품·전시 도메인에 어떻게 매핑되는지 역산 중입니다. 관련 개념을 개인 블로그에 사전 학습으로 정리해뒀습니다:
  - [`architecture/cache-strategies.md`](../../architecture/cache-strategies.md) — 캐시 패턴 전체 + Cache Stampede 대응
  - [`architecture/resilience-patterns.md`](../../architecture/resilience-patterns.md) — Timeout/Retry/CB/Bulkhead/Backpressure
  - [`architecture/high-traffic-commerce-patterns.md`](../../architecture/high-traffic-commerce-patterns.md) — 1,600만 고객 + 올영세일 대비 설계
- 입사 후에는 관찰 기간을 짧게 가져가되 Datadog APM과 기존 장애 리포트를 먼저 읽고 병목·핫 쿼리 가설을 수립한 뒤 말하는 방식으로 접근하겠습니다.

### 5-2. Kotlin

- Java 4년 / Spring Boot 3.x가 주력이고 업무 코드는 Java로 써왔습니다. Kotlin은 개인 학습과 AI 웹툰 MVP 외곽(스크립트)에서 간헐적으로만 사용했습니다.
- 보완: 공고의 Java/Kotlin 병용 요건에 맞춰, 최근 Kotlin + Spring Boot의 `data class`·`null safety`·`coroutine` 관련 패턴을 집중 학습 중입니다. 기존 Java 설계 원칙(불변성, 단일 책임, 도메인 모델링)이 동일하게 적용되기 때문에, 초기 1~2주 안에 실무 생산성 수준으로 붙일 수 있다고 봅니다.

### 5-3. 성급한 추상화를 경계하는 성향 자체의 그림자

- 반복이 충분히 쌓일 때까지 추상화를 미루는 성향이 있어, **조기에 공통 계층을 세팅했어야 했다**는 반성이 남은 경우가 있었습니다 (예: `SlotTemplate`/`BaseSlotService`는 신규 슬롯 5종을 만든 후에야 정돈).
- 보완: 팀 합류 시에는 "현재 반복의 단계(1~2회 / 3회 이상)"를 명시적으로 체크리스트화해, 3회 이상 반복이 보일 때 즉시 ADR 후보로 올리는 리듬을 갖추려 합니다.

### 5-4. 무중단 배포·점진 전환 경험 부재

- 게임 도메인은 **월 단위 배포 주기**로 움직였기에, 라이브 서비스 리팩토링을 **완전 대체 마이그레이션**으로 수행한 경험만 있습니다. Feature Flag 기반 런타임 전환, Shadow Mode로 신·구 양쪽 결과 비교, Canary 배포로 트래픽 일부만 전환하는 실전 경험은 아직 없습니다.
- 대신 이 공백은 **테스트 안전망**으로 메워왔습니다. Spring Test Execution Listener 기반 게임 데이터 프리로딩 + 게임 플레이 시뮬레이션 테스트 + QA 협업 시나리오(일반·튜토리얼·치트)로 배포 전 회귀를 차단했습니다.
- 보완: 커머스의 실시간 배포 + 무중단 요구가 다른 차원의 문제임을 인지하고, CJ 올리브영 **무중단 OAuth2 전환기**(Feature Flag + Shadow Mode + Resilience4j 3단 + Jitter) 사례를 정독하며 [`architecture/zero-downtime-migration.md`](../../architecture/zero-downtime-migration.md)에 스터디 기록을 남겼습니다. 입사 후 1개월 내 실 사례에 체득하는 것이 목표입니다.

---

## 6. 기술 의사결정 스타일

> 기본 원칙: **"싼 단가가 아니라 총비용"**, **"추상화는 반복을 충분히 경험한 뒤"**, **"API/모델 경계와 논리 경계를 분리해서 본다"**.

### 사례 1 — Gemini 모델 전략: Flash 기본 → Pro 기본으로 뒤집은 결정

- 초기: 단가가 낮은 Flash를 기본으로 사용 → 운영자가 결과를 보고 재생성하는 빈도가 높아 **총 호출 횟수·시간 비용 증가**.
- 재결정 (ADR-072): Pro 기본, 429 발생 시 Flash → Lite로 fallback. 전역 `Rate Limit Tracking`(429 맞은 모델을 일정 시간 skip 대상으로 마킹)으로 다른 요청이 같은 모델을 또 두드리지 않게.
- 30초 재시도 로직 제거: TPM은 분 단위로 풀리는데 30초는 또 실패만 불러와 즉시 다음 fallback이 더 빠르고 안정.
- Trade-off: 단가는 오르지만 **"한 번에 만족하는 결과"가 총비용을 낮춘다**는 관점으로 뒤집은 의사결정. 증거: [`task/ai-service-team/webtoon-maker-ai-pipeline.md`](../../task/ai-service-team/webtoon-maker-ai-pipeline.md).

### 사례 2 — 60컷 일괄 생성: SSE → `Promise.allSettled` 구조 전환

- 초기: 서버 SSE로 60개 순회 + 진행률 스트리밍. 부분 실패 시 재시도 상태 기계가 복잡.
- 재결정 (ADR-073): 클라이언트에서 60개 독립 fetch를 `Promise.allSettled`로 병렬 실행.
  - 실패는 per-Promise로 자연스럽게 추적.
  - 브라우저 호스트당 6 동시 연결 제한이 자연 throttling으로 동작 → 별도 rate limiter 불필요.
  - `AbortController`로 전체 취소, 실패 컷만 같은 엔드포인트 재호출.
- **논리 경계 분리 판단**: "1개의 긴 생성"은 SSE, "N개의 독립 생성"은 Promise.allSettled. 글콘티(단일 LLM 호출)는 SSE 유지.

### 사례 3 — 타입 소스 레이어별 분리 (ADR-131)

- 초기: Zod 단일 소스를 Repository까지 확장(`Partial<XxxFields>`) → Prisma의 `DbNull`·`connect/create/disconnect` semantic을 외부 타입으로 흉내 내며 추상화 누수.
- 재결정: Action = Zod + TS 유틸, Repository = `Prisma.XxxCreate/UpdateInput`, 경계는 `actions/mappers/`의 작은 변환 함수. "단일 소스" 도그마를 포기하고 **레이어 본질에 맞는 타입 소스**를 각자 사용.

### 사례 4 — `JobExecutionContext` vs `@JobScope` 홀더

- 초기: 수천 개 페이지 ID를 `JobExecutionContext`에 저장. 청크 커밋마다 `BATCH_JOB_EXECUTION_CONTEXT` 테이블에 직렬화되는 부하.
- 재결정: `JobExecutionContext`는 **재시작용 경량 커서 상태** 전용으로 제한하고, 도메인 데이터는 `@JobScope` 빈 `ConfluenceJobDataHolder`로 분리. `allowStartIfComplete(true)` 세팅으로 재시작 시에도 상태 로더가 반드시 재실행되게 해서 NPE 방지.

### 사례 5 — 메타데이터 구성: Blocklist → Allowlist 전환

- 초기: 임베딩 메타데이터를 "필드 제거" 방식(blocklist)으로 관리. 신규 필드가 추가되면 자동으로 흘러 들어가 의도치 않은 노출.
- 재결정: `EmbeddingMetadataProvider` 인터페이스 기반 allowlist 방식으로 뒤집어 **명시적으로 허용한 필드만** 포함. OCP 준수(새 스페이스 포맷은 새 Provider 추가).

---

## 7. 협업 / 리더십 / 코드 리뷰 강점

### 7-1. "팀이 쓸 수 있는 형태"로 만드는 리팩터링 리드

- 파편화된 스핀 흐름(일반 · 바이피처 · 바이피처 티켓)을 `AbstractPlayService` 단일 템플릿으로 통합하고, 타입별 가변 동작은 `SpinOperationHandler` 인터페이스로 위임. 여러 타입에 흩어진 계산 로직은 Decorator 패턴으로 도메인 레이어에 응집, static 의존을 DI로 전환해 테스트 가능성 확보.
- 결과: 신규 스핀 타입이 늘어도 기존 코드를 건드리지 않고 확장 가능한 구조.

### 7-2. AI 도구 도입의 허리 역할

- Cursor Rules 20개 이상을 직접 구축해 **슬롯 도메인 컨텍스트 자체를 문서화**. 이 규칙 위에서 신규 게임 3종을 에이전트 단독으로 구현.
- 팀 전파 방식: "도구 사용법"이 아니라 "우리 도메인에서 에이전트가 지켜야 할 제약"을 공유. 반복 개발 사이클 단축.

### 7-3. 디자이너와의 협업: ADR이 아니라 파일 소유권 매트릭스로

- AI 웹툰 MVP 후반부 UX 디자이너 합류. 동일 파일(예: 503줄 `StepConti.tsx`) 동시 수정으로 conflict가 빈발.
- 해결: Semantic CSS 토큰 + 공통 컴포넌트 분리(ADR-129), Container/Presenter + Layout Primitives(ADR-130), `docs/collaboration.md`에 **파일 소유권 매트릭스** 명시(디자이너: `globals.css`, `components/common/layout/`, `components/**/components/` / 백엔드: `actions/`, `lib/`, `components/**/hooks/`, `components/**/containers/`).
- `/integrate-ux` 스킬화 — 디자이너의 vibe 코드를 로컬 state → Server Action, 인라인 카드 → 공통 컴포넌트, 인라인 색상 → semantic 토큰으로 **정해진 변환 룰**에 따라 흡수.
- 결과: git conflict가 거의 0에 수렴. 추상적 "관심사 분리" 원칙보다 구체적 소유권 룰이 협업을 굴린다.

### 7-4. 코드 리뷰 관점: 트레이드오프 근거를 ADR/문서로 남긴다

- AI 웹툰 MVP에서 12일간 134개 ADR(001~134)을 생성. 한 ADR이 1,581줄로 비대해지자 docs-verifier 지적을 받아 700줄대로 축약 — **"ADR도 AI 에이전트 컨텍스트"**라는 관점.
- 슬롯 엔진 추상화(`SlotTemplate`/`BaseSlotService`) 도입 시에도 "**반복을 충분히 경험한 뒤 공통점을 뽑았다**"는 근거를 문서화. 후임이 맥락 없이도 의도 파악 가능.

---

## 8. 주요 프로젝트별 요약

### 8-1. Confluence → OpenSearch RAG 배치 파이프라인 (2026.01 ~ 2026.03)

- **문제 정의**: 사내 AI Playground가 RAG 검색 품질을 올리려면 Confluence 문서를 벡터로 사전 색인해야 하는데, 포맷(ADF), 첨부파일, 다중 스페이스, 삭제 동기화, 재시작 요구가 얽힘.
- **해결 접근**: Spring Batch 기반 11 Step 분리 파이프라인. `CompositeItemProcessor`로 `ChangeFilter → Enrichment → BodyConvert → Embedding` 단계를 체이닝, I/O 바운드 임베딩은 `AsyncItemProcessor` + `AsyncItemWriter`로 병렬화. `@JobScope` 홀더로 Step 간 경량 공유, `JobExecutionContext`는 재시작 커서로만 사용. 전략 패턴(`ConfluenceDocumentMetadataProvider`)으로 스페이스별 메타데이터 포맷 차이 흡수. 삭제 동기화는 `status=DELETED,TRASHED` 재사용으로 별도 ID 집합 비교 없이 처리.
- **측정 가능한 결과**: Step 단위 실패 격리 + 커서 기반 재시작으로 장애 복구 시 처음부터 재실행 불필요. 변경 감지(`version` 비교)로 불필요한 임베딩 API 호출 제거.
- **기술적 핵심**: Spring Batch, `AsyncItemProcessor`, `@JobScope` 프록시, OpenSearch bulk, 전략 패턴, `@StepScope` 빈 충돌 해결(`@Qualifier` 정리).

### 8-2. AI 웹툰 제작 도구 MVP (2026.04, 12일 / 단독)

- **문제 정의**: 웹소설 → 세계관/캐릭터/각색/글콘티/60컷 이미지까지 6단계 풀 파이프라인을 12일에, 혼자.
- **해결 접근**: Next.js 16 / React 19 / Prisma 7 / Zod 4 / Tailwind v4 / `@google/genai`로 단일 코드베이스 + 타입 안전성 극대화. Claude Code 하네스 위에 planner / critic / executor / docs-verifier **4인 에이전트 팀**을 조립하고, `/planning` → `/plan-and-build` → `/build-with-teams` → `/integrate-ux`로 vibe 코딩 → spec 기반 코딩 전환.
- **측정 가능한 결과**: 11일 실작업 / 199 plan / 760 커밋. 하루 최대 120 커밋. Step1 통합 분석으로 **토큰 75% 절감, 26.8s → 13.1s**.
- **기술적 핵심**:
  - Gemini 모델 전략: Pro 기본 + 429 fallback + 전역 Rate Limit Tracking (ADR-069, ADR-072).
  - Project 단위 Context Cache로 원작 소설을 5단계 공유 → 재결제 비용 제거.
  - `Promise.allSettled` 기반 60컷 병렬 생성 (`AbortController` 전체 취소, 실패 컷별 재호출) (ADR-073).
  - 글콘티 환각 차단: Grounding 블록 + Continuation 재주입 + conti 프롬프트 3-layer(`types/`, `templates/`, `blocks/`) (ADR-132).
  - 캐릭터 외형 고정: 텍스트 anti-drift 한계 인정 → `CharacterSheet.isDefault` + 기본 시트 이미지 자동 prepend + mode 분기(`default`/`outfit`) (ADR-133/134).
  - 타입 시스템: Zod 단일 소스(ADR-109) + 레이어별 분리(ADR-131, Action=Zod / Repository=Prisma / mapper).
  - 디자이너 협업: Semantic 토큰 + Container/Presenter + Layout Primitives + 파일 소유권 매트릭스 (ADR-129/130).

### 8-3. 다중 서버 인메모리 캐시 정합성 (2024~2025)

- **문제 정의**: 정적 설정 데이터를 여러 인스턴스가 메모리에 캐싱하는데, 어드민에서 한 곳이 바뀌면 나머지 서버도 갱신돼야 하고, 갱신 중 조회 요청에서 일시적 정합성 오류 발생.
- **해결 접근**: Hibernate `PostCommitUpdateEventListener` → RabbitMQ Fanout Exchange 발행 → 각 인스턴스가 자신의 큐에서 수신해 **해당 슬롯만 선택 갱신**. 갱신/조회 경합은 `StampedLock` writeLock + `tryReadLock(2500ms)`. `StaticDataManager` 인터페이스로 init/refresh/clear 책임 분리.
- **측정 가능한 결과**: 갱신 중 NPE/정합성 오류 제거, 읽기 성능 유지, 신규 캐시 타입 추가 시 기존 코드 무변경.
- **기술적 핵심**: JPA 이벤트 리스너, RabbitMQ Fanout, StampedLock, Alias 테이블 `IN`절 일괄 조회로 init/refresh 쿼리 수 감소.

### 8-4. Kafka 비동기 발행 + Dead Letter Store (슬롯팀)

- **문제 정의**: 금액·레벨 등 즉시 응답 로직과 미션·통계·알림 후처리가 한 트랜잭션 안에 얽혀 지연·실패 전파.
- **해결 접근**: 동기/비동기 분리. `@TransactionalEventListener(AFTER_COMMIT)`으로 커밋 이후에만 발행해 롤백된 이벤트의 외부 유출 차단. 전송 실패 시 `Propagation.REQUIRES_NEW` 별도 트랜잭션으로 실패 메시지 + traceId를 DB에 저장하는 **Dead Letter Store** → 스케줄러 재전송.
- **측정 가능한 결과**: 전송 실패 복구 가능, 실패 원인 추적 가능, 핵심 API 응답 시간 단축.
- **기술적 핵심**: Spring AOP 기반 이벤트 리스너, Dead Letter 테이블, 스케줄러 재시도, traceId 전파.
- **한계 인지**: AFTER_COMMIT과 Kafka 발행 사이의 JVM 크래시·SIGKILL 구간은 유실 가능성이 남음. 해당 도메인(통계·알림)에선 수용 가능한 수준으로 판단했고, 정합성이 더 엄격한 도메인에서는 이벤트를 비즈니스 데이터와 같은 트랜잭션에 저장하는 **정식 Transactional Outbox** 구조로 강화가 필요합니다.

### 8-5. 스핀 성능 최적화 & 시뮬레이터 OOM (2025 상반기)

- **문제 정의**: 스핀 TPS 한계, 시뮬레이터 장기 실행 시 OOM.
- **해결 접근**: `AliasMethod`로 가중치 샘플링 O(n)→O(1), `SecureRandom` → `ThreadLocalRandom`. 시뮬레이터는 `List<Long> winmoneyList` 누적 → Welford's Online Algorithm 기반 1-pass 평균/분산으로 상수 메모리.
- **측정 가능한 결과**: 스핀 경로 핫스팟 제거, 시뮬레이터 OOM 해소.
- **기술적 핵심**: 자료구조 선택의 체감 효과, `SecureRandom` 경합 병목 이해, 수치 안정성(Welford).

### 8-6. RCC (RTP Cache Control, 2025.07 ~ 2025.10)

- **문제 정의**: 스핀 결과를 사전 캐시해 응답 지연을 낮추면서도 다중 서버 환경에서 RTP 정합성을 깨지 않아야 함.
- **해결 접근**: 슬롯 6종에 대해 사전 계산 + 캐시 + 동시성 제어. 슬롯 엔진 추상화(`SlotTemplate`, `BaseSlotService`, `ExtraConfig` 분리)와 함께 진행해 확장 비용 최소화.
- **기술적 핵심**: Spring Boot 3.x, Redis, Project Reactor, 템플릿/전략 패턴.

---

## 9. 지원동기 — 왜 이 회사, 왜 이 역할, 왜 지금

### 9-1. 한 문단 통합 서사 (면접 "왜 우리 회사?" 답변용, 약 90초)

> 지난 4년간 NHN에서 **동시성·이벤트 드리븐·대용량 배치** 문제를 깊게 풀어오면서, 같은 패턴이 커머스 도메인에서 더 큰 스케일로 어떻게 다시 나타나는지에 대한 호기심이 계속 쌓였습니다. 슬롯 도메인에서 다중 서버 캐시 정합성을 RabbitMQ + StampedLock으로 풀고, 메시지 신뢰성을 `AFTER_COMMIT` + Dead Letter Store로 구조화한 경험이, **1,600만 고객 트래픽의 상품·전시·주문 도메인**에서 어떤 형태로 다시 등장하는지 직접 보고 싶습니다. 특히 CJ 올리브영 기술 블로그의 MSA 데이터 연동 전략과 무중단 OAuth2 전환기를 읽으면서 **판단의 결이 저와 같다**는 확신이 들었습니다. 여기에 AI 도구를 단순히 쓰는 게 아니라 파이프라인으로 설계·운영한 경험을 더해, 팀의 개발 사이클을 한 단계 당기는 데 기여하고 싶습니다.

### 9-2. 왜 지금 이직하는가 (타이밍 설명)

- **충분한 축적**: 슬롯·AI 서비스에서 4년간 캐시 정합성, Kafka 이벤트, Spring Batch 대용량 처리, 도메인 추상화, AI 파이프라인까지 풀스펙트럼으로 경험을 쌓았습니다.
- **스펙트럼 확장**: AI 웹툰 MVP를 12일간 단독 리드하면서 설계부터 운영까지의 의사결정 속도가 한 단계 올라갔습니다. 이제 그 속도를 더 큰 규모의 시스템에 적용해볼 단계입니다.
- **검증 필요성**: 슬롯은 사내·B2C 도메인, AI 서비스는 사내 도구 중심이었습니다. 지금까지의 패턴이 **초 단위 수만 TPS 실서비스 트래픽**에서 얼마나 버티는지는 다음 단계에서 검증해야 합니다. 그 검증 환경으로 CJ 올리브영 커머스플랫폼이 가장 적합하다고 판단했습니다.

### 9-3. 왜 이 회사 — 기술 블로그에서 본 결

- **MSA 데이터 연동 전략** (2026-03-18) — 데이터의 사용처·변경 빈도·라이프사이클로 Cache-Aside vs Kafka 이벤트 + Redis Key 캐싱을 선택하는 접근은, 제가 슬롯에서 "정적 데이터는 인메모리 + Fanout, 후처리는 Kafka 비동기"로 나눈 판단과 같은 결입니다.
- **무중단 OAuth2 전환기** (2025-10-28) — Feature Flag(Strategy) + Shadow Mode + Resilience4j 3단(Timeout → Retry → CB) + ±30s Jitter로 Peak TPS 40% 감소, P95 50ms / 성공률 100%. **"안전하게 뒤집는 방법"을 코드 배포 없이도 확보하는 감각**이 제 "Pro 기본 + 429 fallback + 전역 Rate Limit Tracking" 설계와 같은 방향입니다.
- **SQS 알림톡 데드락 분석** (2025-12-30), **Spring 트랜잭션 동기화 레거시 개선** (2026-02-23) — 레거시를 **트랜잭션 경계·이벤트 경계로 재설계**하는 접근은 슬롯의 동기/비동기 흐름을 `AFTER_COMMIT` + Dead Letter Store로 정리한 것과 같습니다.

### 9-4. 왜 이 역할 — JD × 경험 매핑

- **상품·전시·검색·ORM**: JPA 도메인 모델링 + 이벤트 리스너 + 다중 서버 캐시 정합성 4년 경험이 상품·전시의 실시간 변경·다중 서버 동기화 문제에 직접 매핑됩니다.
- **MSA·Kafka·캐싱**: `AFTER_COMMIT` 발행 + Dead Letter Store 재시도, RabbitMQ Fanout, Spring Batch 11 Step + AsyncItemProcessor까지 운영 경험이 검색·알림·주문 도메인 간 이벤트 연동에 바로 적용 가능합니다.
- **AI 도구 도입**: Cursor Rules 20+로 슬롯 도메인 컨텍스트 문서화 → 신규 게임 3종 에이전트 단독 구현, AI 웹툰 MVP 4인 에이전트 팀 운영 경험을 팀에 들여와 반복 개발 사이클을 단축하는 데 쓰고 싶습니다.
- **Kotlin**: 초기 학습 필요. 공고의 Java/Kotlin 병용 요건에 맞춰 1~2주 안에 실무 생산성 수준까지 끌어올리겠습니다.

### 9-5. 기여 포지셔닝 — 한 줄 클로징

> "저는 기능을 빨리 만드는 사람이기보다, **팀이 같은 기능을 더 빠르고 안전하게 다시 만들 수 있는 구조를 남기는 사람**으로 일해왔습니다. 오늘 이야기한 경험들을 이 팀의 상품·전시·주문 도메인에 다시 적용해 보고 싶습니다."

---

## 10. 시니어 백엔드 공통 질문 + 답변 프레이밍 가이드

> 공통 프레이밍: **맥락(왜 문제였는지) → 트레이드오프 → 결정 → 측정 결과 → 회고**. 한 답변 60~90초 기준.

### Q1. "설계 결정을 되돌려야 했던 경험이 있나요?"

- **AI 웹툰 모델 전략**: Flash 기본 → Pro 기본으로 반대 방향 전환. "단가가 싸다 ≠ 총비용이 싸다"는 걸 운영자 재생성 빈도로 체감. 되돌린 후 전역 Rate Limit Tracking까지 얹어 중복 429를 구조적으로 제거. (ADR-072)
- **60컷 SSE → `Promise.allSettled`**: 부분 실패 상태 기계가 복잡해진 지점에서 "N개 독립 생성"의 본질에 맞게 클라이언트 병렬로 뒤집음. 브라우저 connection 제한을 의도적으로 throttler로 활용. (ADR-073)
- **회고**: 되돌리는 비용 ≠ 실패. 초기 가정이 현실에 맞는지 **짧은 주기로 계측**하면 되돌림 비용이 작다.

### Q2. "DB 마이그레이션/데이터 이행 중 실패가 난다면 어떻게 하시겠어요?"

- 기본 전제 세 가지: **(a) 멱등성**, **(b) 재시작 가능성**, **(c) 실패 격리**. Spring Batch 파이프라인에서 실제로 적용한 원칙입니다.
- 접근:
  1. 이행을 논리적 Step 단위로 분리 (수집 → 변환 → 검증 → 쓰기 → 정합성 확인).
  2. Reader는 커서 기반, 커서 위치는 `ExecutionContext`에 저장 → 실패 지점부터 재시작.
  3. 쓰기는 청크 단위 트랜잭션 + 멱등 키로 중복 실행 방어.
  4. **Shadow 이행** (구 → 신 병기 기록) 단계로 운영 데이터와 이행 데이터를 비교한 뒤, Feature Flag로 읽기 경로만 점진 전환(올리브영 OAuth2 전환 사례와 같은 결).
  5. 실패 메시지는 `REQUIRES_NEW` 별도 트랜잭션 + traceId로 저장, 재처리 큐로 흘려보냄.
- 실제 근거: `AsyncItemProcessor` + 커서 재시작([`task/ai-service-team/rag-vector-search-batch.md`](../../task/ai-service-team/rag-vector-search-batch.md)), `REQUIRES_NEW` 기반 Dead Letter Store 재시도(`resume 문항 1`).

### Q3. "주니어가 합류하면 리뷰 정책은 어떻게 세팅하시겠어요?"

- 1주차: **도메인 맥락 먼저**. 코딩 컨벤션보다 "이 모듈은 왜 이렇게 생겼는지"의 ADR/README 읽기를 우선. 저는 슬롯팀에서 Cursor Rules 20+로 도메인 컨텍스트를 문서화해 이 온보딩 비용을 낮춰왔습니다.
- 리뷰 태그 3단계: `must` (병합 차단) / `should` (논의 후 결정) / `nit` (취향). 이유 없는 `must`는 금지.
- PR 크기 상한 + 테스트 동반을 원칙으로. `AbstractSlotTest` 같은 추상 테스트 클래스로 **테스트를 쓰는 게 쉬운 구조**를 먼저 만드는 것이 리뷰보다 앞섭니다.
- 리뷰 자체가 아니라 "왜 이 결정인지"를 남기는 문화가 장기 품질에 더 기여합니다 (슬롯 엔진 추상화·AI 웹툰 ADR 134개 운용 경험).

### Q4. "다중 서버에서 캐시 일관성을 어떻게 보장하세요?"

- 3축으로 분리: **전파 채널 / 갱신 타이밍 / 경합 제어**.
  - 전파: Hibernate `PostCommitUpdateEventListener` → RabbitMQ Fanout (커밋 이후만 발행, ID만 전달해 각 서버가 선택 갱신).
  - 타이밍: 풀 invalidate 대신 변경 ID 기반 선택 갱신.
  - 경합: `StampedLock` writeLock + `tryReadLock(2500ms)`. 짧고 예측 가능한 대기.
- 대안 비교: Redis Pub/Sub는 구독 보장·순서에서 약하고, 캐시 서버 중앙화(Redis만 사용)는 인메모리 대비 읽기 지연 증가. 이 시스템은 읽기 극단적 우세·갱신 저빈도라 인메모리 + Fanout이 맞았습니다.

### Q5. "Kafka에서 메시지 유실을 막는 구조를 어떻게 설계하시나요?"

- **정식 Transactional Outbox**: 비즈니스 트랜잭션 안에서 outbox 테이블에 이벤트를 함께 기록하고, relay(스케줄러 또는 CDC)가 outbox를 읽어 Kafka로 발행. 커밋 자체에 메시지 저장이 포함되므로 JVM 크래시 상황에서도 유실이 구조적으로 차단됩니다.
- **슬롯팀에서 한 구현과의 차이**: 저는 `@TransactionalEventListener(AFTER_COMMIT)`으로 커밋 이후 발행 + 전송 실패 시 `Propagation.REQUIRES_NEW`로 Dead Letter Store + 스케줄러 재시도 구조로 구현했습니다. AFTER_COMMIT과 Kafka 발행 사이의 크래시 구간은 유실 가능성이 남는 한계가 있고, 통계·알림 도메인에선 수용 가능한 수준으로 판단한 선택이었습니다. 정합성이 엄격한 도메인이면 정식 Outbox로 강화해야 합니다.
- 컨슈머 쪽: 멱등 키 + 수동 커밋 + DLQ. "한 번 이상 도착" 모델을 전제로 설계.
- 회고: producer는 유실 방지, consumer는 중복 방어가 분업. 이 경계를 흐리면 retry 폭주/순환이 생깁니다.

### Q6. "N+1 같은 JPA 성능 문제 어떻게 진단하세요?"

- 1) 로그·APM에서 쿼리 N회 반복 여부 탐지 → 2) `EXPLAIN` + 인덱스 구조 확인 → 3) `@EntityGraph` 또는 fetch join으로 평탄화 vs 프로젝션(DTO)로 우회 → 4) 컬렉션 여러 개를 동시 fetch join하는 MultipleBagFetchException은 batch size + fetch join 혼합으로 우회 → 5) 벌크 연산 후 영속성 컨텍스트 clear 누락 주의.
- AI 서비스 배치에서는 init/refresh 시 게임별 Alias 쿼리를 `IN`절 일괄 조회로 묶어 쿼리 수를 크게 줄인 사례가 있습니다.

### Q7. "실패 원인 추적(Observability)을 어떻게 설계하세요?"

- MDC/traceId 전파를 트랜잭션 경계·메시징 경계 모두에서 유지. Dead Letter 레코드에도 traceId를 함께 박아 사후 재현성 확보.
- 비즈니스 실패(예: safety filter 차단, AI 환각)는 **기술 예외와 다른 채널**로 기록. AI 웹툰에서는 컷별로 `lastGenerationStatus`, `lastGenerationError`, `lastGeneratedAt`을 DB에 박아 UI에 구체적 사유를 노출했습니다.
- Circuit Breaker·Timeout·Retry는 이벤트를 남기지 않으면 "왜 성공했는지/왜 실패했는지"가 사라짐. Resilience4j 사용 시 이벤트 리스너로 상태 전이 로깅 필수.

### Q8. "팀에 기술적 반대 의견을 낸다면 어떻게 하시나요?"

- 반대 자체보다 **트레이드오프 표**를 먼저 올립니다. "이걸 택하면 무엇을 잃는가"를 숫자/시나리오로.
- 단기 의사결정이라면 ADR 초안 1페이지, 장기라면 스파이크/벤치마크로 증거를 모은 뒤 논의. 슬롯 엔진 추상화도 반복 5회 이상을 채운 뒤에야 ADR로 제안했습니다.
- "내가 틀릴 수 있음"을 명시적으로 남겨두면 논의 비용이 훨씬 내려갑니다.

### Q9. "RabbitMQ Fanout 구조를 Kafka로 전환한다면 consumer group을 어떻게 잡으시겠어요?"

- 핵심은 **"모든 인스턴스가 모든 메시지를 받아야 한다"**는 Fanout 의미론을 Kafka에서 재현하는 것입니다.
- **같은 consumer group으로 묶으면 안 됨**: Kafka는 같은 group 안에서 파티션을 컨슈머들에게 **분할 할당**합니다. 100대 인스턴스 + 하나의 group이면 각 메시지는 하나의 인스턴스만 받는 **Work Distribution**이 됩니다. 캐시 갱신 브로드캐스트로는 실패.
- **인스턴스마다 독립 consumer group**: 각 인스턴스가 자기 group을 가지면 각자 모든 파티션을 읽습니다. `group.id`는 `cache-sync-${hostname}` 같은 결정론적 ID로 잡아야 재배포 시 offset이 이어집니다. 랜덤 UUID면 매 배포마다 earliest/latest로 초기화돼 폭주 위험.
- **파티션 수**: Fanout 구조에선 각 group 내 컨슈머가 1개뿐이므로 **파티션 1개도 충분**. 파티션 수는 "각 group 내 병렬 소비가 필요한가"에 따라 결정. Work Distribution 시나리오와 헷갈리면 안 됩니다.
- **100대 규모의 운영 이슈**: 100개 group이면 `__consumer_offsets` 토픽 부하 100배. offset commit 주기 튜닝 필요. 대안으로 Redis Streams + consumer group, 혹은 짧은 L1 TTL 기반 이벤트 없는 캐시도 검토 가치가 있습니다.

### Q10. "슬롯 인메모리 캐시를 커머스 상품 캐시로 옮기면 어떻게 설계하시겠어요?"

- **데이터 성격별 저장소 분리가 출발점**:
  - 재고·가격(실시간 정합성 요구) → Redis single source of truth
  - 상품 상세·노출 순위(느린 변경) → 인메모리 + 이벤트 무효화
- **2-tier 구조로 확장**: Caffeine(L1, 프로세스 내, 수 초 TTL) + Redis(L2, 공유, 장기 TTL). L1이 L2를 방어하고, L2가 DB를 방어. 이벤트로 L1 무효화 전파.
- **Cache Stampede 대응**: 핫키 만료 순간 DB 폭주 방지를 위한 3중 방어 — probabilistic early expiration(만료 전 확률적 갱신), single-flight(request coalescing으로 한 번만 DB 조회), Redis 분산 락.
- **TTL에 Jitter**: 같은 시각 대량 만료로 cliff가 생기는 걸 막기 위해 TTL에 ±10% 난수 가감.
- **전파 채널 선택**: 인스턴스 수가 적으면 RabbitMQ Fanout, 많아지면 Kafka 토픽(인스턴스마다 독립 group) 또는 Redis Pub/Sub. 메시지 보장이 필요한지가 선택 기준.
- 근거: [`architecture/cache-strategies.md`](../../architecture/cache-strategies.md), [`architecture/high-traffic-commerce-patterns.md`](../../architecture/high-traffic-commerce-patterns.md).

### Q11. "라이브 운영 중인 시스템을 리팩토링하실 때 어떤 전환 방식을 쓰시나요?"

- **정직한 전제**: 슬롯 도메인은 월 단위 배포 주기여서 **완전 대체 마이그레이션** + 테스트 안전망(게임 플레이 시뮬레이션 + QA 시나리오 검증) + 팀 QA 협업으로 풀어왔습니다. Feature Flag/Shadow Mode/Canary 같은 실시간 무중단 전환 경험은 아직 없습니다.
- **커머스 환경의 필요성 인지**: 1,600만 고객 + 실시간 배포 환경에선 다른 차원의 전환 전략이 필요하다는 걸 알고 있고, CJ 올리브영 무중단 OAuth2 전환기(Feature Flag + Shadow Mode + Resilience4j 3단 + Jitter)를 정독하며 [`architecture/zero-downtime-migration.md`](../../architecture/zero-downtime-migration.md)에 스터디 기록을 남겼습니다.
- **커머스에서 쓸 접근 순서** (도입 시):
  1. **Feature Flag**로 신·구 로직을 런타임 전환 가능하게 (배포 없이 30초 내 반영)
  2. **Shadow Mode**로 신 로직을 read-only로 병행 실행 → 결과 비교 대시보드(diff rate 알람)
  3. **Canary 배포**로 hash(userId) 기반 결정론적 10% → 30% → 100% 점진 확대
  4. **Resilience4j 3단**(Timeout → Retry → CircuitBreaker) 체인으로 외부 의존 실패 격리
  5. 플래그 cleanup 티켓 + 롤백 drill 문서화
- "경험 없음을 숨기지 않고, 학습한 범위를 구체적으로 제시하는" 프레이밍으로 답변합니다.

---

## 11. 역질문 리스트 (기술 / 팀 / 성장 / 회사 방향)

### 기술

1. 상품·전시·주문 도메인 간 데이터 연동에서 Kafka 이벤트와 Cache-Aside가 공존한다고 알고 있는데, **현재 가장 병목이 되는 지점**은 어느 도메인 경계입니까?
2. MSA 경계에서 스키마 변경(특히 이벤트 payload) 관리는 어떤 도구·컨벤션으로 하고 계신가요? (예: Schema Registry, Consumer Driven Contract)
3. 대형 세일 트래픽에서 **캐시 stampede**가 발생했을 때 팀에서 검증된 완화 패턴(request coalescing, jitter, early refresh 등)은 무엇인가요?
4. Datadog APM에서 오탐/무시해도 되는 알람과 실제 액션이 필요한 알람을 구분하는 팀 내 기준이 있습니까?

### 팀

1. 코드 리뷰에서 `must`/`should`/`nit` 같은 태그 문화가 있는지, 없다면 리뷰 갈등은 어떻게 중재되나요?
2. 주니어/신규 입사자 온보딩에 평균 어느 정도 기간이 소요되고, 처음 맡기는 태스크는 주로 어떤 성격인가요?
3. 사고/장애 발생 시 **blameless postmortem** 문화가 어느 수준으로 자리잡혀 있나요?

### 성장

1. 기술 블로그에 올라온 글은 누가 어떤 리듬으로 쓰는지, 사내 공유·외부 공유가 어떻게 연결되나요?
2. 시니어 개발자에게 기대되는 **기술 리드와 피플 요소의 비율**은 대략 어떻게 그려집니까?
3. AI/에이전트 기반 개발 도구 도입에 대해 팀·유닛 차원에서 지금 어떤 실험이 진행되고 있나요?

### 회사 방향

1. 커머스플랫폼유닛이 향후 1~2년 안에 **가장 투자하려는 기술 영역**(예: 검색 고도화, 추천, 결제, 물류 연계 등)은 무엇인가요?
2. B2C 트래픽 외에 **B2B 파트너·입점사 API** 쪽의 아키텍처 방향은 따로 있나요?
3. Kotlin 도입 비중은 현재 어느 정도이고, Java/Kotlin 혼용에서 팀 컨벤션은 어떻게 정리되어 있나요?

---

## 12. 면접 당일 최종 체크리스트

### 지참물 / 세팅

- [ ] 이력서·상세경력기술서 출력본 2부 (면접관 수 × 1 + 본인 참고용).
- [ ] 노트북(라이브 코딩 대비) — 충전기·어댑터·멀티탭·이어폰·유선 랜(백업).
- [ ] 사원증 시절 사진·신분증.
- [ ] 필기구 + A4 2장(화이트보드 대비 핵심 다이어그램 연습용).
- [ ] 참고 원페이저 1장(이 문서의 §3 커리어 요약 + §8 프로젝트 요약 + §11 역질문).

### 라이브 코딩 / 화면 공유 준비

- [ ] IDE: IntelliJ(JDK 17 / 21 모두 준비), 즐겨쓰는 단축키 워밍업.
- [ ] 화면 공유 테스트: Zoom/Google Meet 모두 "전체 화면 vs 앱 단위" 공유 확인. 알림·메신저 off.
- [ ] 글꼴 크기 14pt 이상으로 고정 (면접관이 잘 보여야 함).
- [ ] 빈 프로젝트 1개 + `gradle init` 상태 준비 (필요 시 빠른 시작).
- [ ] 화이트보드 테스트 대비: 시스템 다이어그램 그리는 **4단계 순서** 워밍업
      1) Context(외부 → 내부), 2) Component(주요 모듈), 3) Data flow(읽기/쓰기), 4) Failure mode(어디서 깨지는가).

### 시간 배분 (60분 기준)

- 자기소개 60초 (§1 그대로).
- 이력·경험 설명 10~15분: 슬롯 캐시 정합성 / Kafka 비동기 발행 / RAG 배치 / AI 웹툰 MVP 중 **면접관이 관심 보이는 축을 빠르게 감지**해 거기에 무게.
- 기술 심화 QnA 20~25분: §10의 프레이밍 그대로 사용.
- 라이브 코딩/화이트보드 10~15분.
- 역질문 5분: §11에서 **기술 1 + 팀 1 + 회사 방향 1** 세 개 우선.
- 마지막 1분: "오늘 이야기에서 제가 더 설명드리면 좋을 부분이 있는지" 역질문으로 닫기.

### 말하기 지침

- 속도: 평소보다 **20% 느리게**. 숫자·고유명사(StampedLock, `AsyncItemProcessor`, `@TransactionalEventListener(AFTER_COMMIT)`)는 또박또박.
- 한 답변 60~90초 원칙. 길어지면 "핵심 먼저 → 이후 더 깊게 가실지 여쭤봐도 될까요?"로 끊기.
- "잘 모르겠다"는 세 단계로: (1) 현재 아는 범위, (2) 비슷한 경험에서의 가설, (3) 입사 후 어떻게 검증할지. **모른다는 걸 숨기지 않는다**.
- 재사용 가능한 클로징 문장 한 줄 준비:
  > "저는 기능을 만드는 것보다 팀이 같은 기능을 더 빠르고 안전하게 다시 만들 수 있는 구조를 남기는 데 동기부여되는 사람입니다. 오늘 이야기한 경험들을 이 팀에서 상품·전시·주문 도메인에 다시 적용해 보고 싶습니다."

### 당일 아침

- [ ] 이 문서 §1, §3, §8, §11만 재독 (전체 아님).
- [ ] 최근 3개월 사내 수정 사항(임베딩 메타데이터 allowlist 전환, OCR Graceful Shutdown, AI 웹툰 MVP 12일 회고) 키워드 복기.
- [ ] 물 500ml, 사탕 1~2개. 긴장 완화용.
- [ ] 이동 시간 + 30분 여유. 근무지: 서울.
