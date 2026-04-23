# [초안] NHN AI 서비스 팀 경험 기반 시니어 백엔드 면접 질문 은행 — CJ 올리브영 커머스플랫폼유닛

---

## 이 트랙의 경험 요약

- AI 서비스 팀 4개 대표 경험 축: (1) Spring Batch 11 Step RAG 색인 파이프라인, (2) gRPC OCR Graceful Shutdown 503 해결, (3) 임베딩 메타데이터 전략 패턴 전환, (4) 12일 단독 풀스택 AI 웹툰 MVP
- 질문은 시니어 Java 백엔드 면접 기준 — 설계 의사결정, 트레이드오프, 장애 격리, 재시작성, OCP/확장성, 운영 복구 경로가 중심이다
- AI/에이전트 협업 경험은 '툴 사용자'가 아니라 '파이프라인·아키텍처 설계자' 관점으로 녹여내 — 하네스, 에이전트 팀 역할 분리, Gemini fallback·Context Cache 등을 설계 결정으로 기술한다
- 전 질문은 커머스 도메인(상품·전시·주문, Cache-Aside, Event-Driven, 대용량 검색 색인) 연결 포인트를 마지막 포석으로 둔다 — 경험이 올영의 1,600만 고객 트래픽 환경에 바로 이식 가능함을 증명한다

## 1분 자기소개 준비

- NHN에서 4년간 게임 백엔드와 AI 서비스 개발을 맡아온 김병태입니다. Spring Boot 기반 멀티모듈 MSA에서 슬롯 서비스를 담당해 신규 게임 개발·성능 개선·아키텍처 재설계를 수행했고, 이후 AI 서비스 팀으로 이동해 사내 RAG 플랫폼의 색인 파이프라인을 처음부터 설계·구현했습니다.
- 대표 경험 네 가지를 1분 안에 정리하면, 첫째는 다중 서버 인메모리 캐시 정합성 문제를 Hibernate PostCommit + RabbitMQ Fanout + StampedLock 조합으로 해결한 경험, 둘째는 @TransactionalEventListener AFTER_COMMIT과 Dead Letter Store + 스케줄러 재시도로 비동기 신뢰성을 확보한 Kafka 이벤트 드리븐 설계입니다.
- 셋째는 Confluence 문서를 OpenSearch에 벡터 색인하는 11 Step Spring Batch 파이프라인을 설계해 AsyncItemProcessor 병렬화, 커서 기반 재시작, 전략 패턴 기반 메타데이터 확장까지 구현한 경험이고, 넷째는 12일 동안 혼자 풀스택으로 AI 웹툰 제작 도구 MVP를 만든 경험입니다 — Claude Code 하네스 위에 planner/critic/executor/docs-verifier 4인 에이전트 팀을 태워 199 plan / 760 커밋을 처리했습니다.
- 기능만 만들기보다 팀 전체가 빠르게 기여할 수 있는 구조를 만드는 걸 중요하게 여깁니다. 파편화된 로직은 추상 템플릿과 인터페이스로 정리하고, 트레이드오프는 ADR로 남기며, 실패 복구 경로와 재시작성을 설계 단계부터 박는 개발자입니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영의 1,600만 고객 트래픽 환경에서 가장 직접적으로 쓰일 경험은 Kafka 이벤트 드리븐 설계와 다중 서버 캐시 정합성 설계입니다 — AFTER_COMMIT 발행, Dead Letter Store + 재시도, traceId 기반 실패 추적까지 갖춘 구조는 상품·주문·전시 도메인 간 이벤트 연동에 바로 이식할 수 있습니다.
- 대용량 색인 파이프라인 경험도 커머스 상품 검색에 그대로 적용됩니다 — Step 실패 격리, AsyncItemProcessor 병렬화, 증분 처리와 삭제 동기화, OpenSearch 벌크 색인은 문서 도메인이든 상품 도메인이든 패턴이 동일합니다.
- 올영 기술 블로그에서 본 Cache-Aside + Kafka 하이브리드, Feature Flag + Shadow Mode + Resilience4j 3단계 보호, SQS 데드락 분석 같은 주제들은 제가 경험한 패턴과 결이 같습니다 — 설계 이유와 운영 시 실패 경로를 함께 이야기할 수 있습니다.
- AI 개발 도구 도입에서도 팀 내 선도 역할을 맡아 왔습니다. Cursor Rules 20개 이상 구축과 에이전트 단독 신규 게임 3종 구현, 12일 하네스 기반 MVP 같은 경험을 올영 백엔드 팀의 개발 속도와 안정성 동시 확보에 기여하는 방향으로 가져가고 싶습니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 게임과 사내 AI 서비스에서 설계한 패턴들 — 캐시 정합성, Kafka 신뢰성, 대용량 색인 — 이 '진짜 대규모 커머스 트래픽' 환경에서 어떻게 작동하고 어디서 깨지는지 직접 부딪혀 보고 싶습니다. 지금까지의 경험이 문서와 블로그의 패턴으로만 머무르지 않고 실제 1,600만 고객 규모에서 검증되는 단계로 넘어가고자 지원했습니다.
- 제가 쌓아 온 기술 스택(Spring Boot 멀티모듈 MSA, Kafka AFTER_COMMIT + DLS, JPA 이벤트 리스너 기반 캐시 동기화, OpenSearch 색인, Docker/K8s 운영)이 올리브영 커머스플랫폼이 쓰는 스택과 거의 완전히 겹칩니다 — 온보딩 비용이 낮고 조기 기여가 가능하다고 판단했습니다.
- AI 서비스 팀에서 단독 풀스택으로 MVP를 만들어 보며, 제가 가장 즐기고 가장 잘하는 일이 '복잡한 도메인을 구조적으로 정리해 팀이 빠르게 움직일 수 있게 만드는 것'이라는 걸 명확히 했습니다. 이 경험을 상품·전시·주문 같은 복잡한 커머스 도메인에서 이어 가고 싶습니다.

### 왜 올리브영인가
- 올영 기술 블로그의 'MSA 도메인 데이터 연동 전략(Cache-Aside + Kafka 하이브리드)', '무중단 OAuth2 전환기(Feature Flag + Shadow + Resilience4j)', 'SQS 알림톡 데드락 분석'을 읽으며, 이 팀이 장애 경로·부분 실패·트레이드오프를 ADR 수준으로 깊이 다루는 조직이라고 느꼈습니다. 제가 지금까지 유지해 온 'ADR·docs-first' 작업 방식과 결이 같아 협업 생산성이 높을 것이라 확신합니다.
- 1,600만 고객, 올영세일 10배 트래픽, P95 50ms/100% 성공률 같은 수치는 '정합성과 속도를 동시에'를 요구하는 환경입니다. 제가 StampedLock 타임아웃으로 갱신 중 조회 병목을 풀고, Jitter·재시도·DLS를 설계 단계에서 박는 방식으로 일해 왔기 때문에 이 환경에 잘 맞습니다.
- MSA·Event-Driven·대용량 캐시·무중단 배포·Kafka·OpenSearch — 이 조합을 모두 실무에서 설계·운영해 온 팀은 국내에서 흔치 않습니다. 앞으로 5~10년 경력의 중심축을 이 스택 위에 세우고자 하는 저에게 최적의 자리라고 판단했습니다.

### 왜 이 역할에 맞는가
- 커머스플랫폼유닛은 상품 관리, 전시 로직, 검색 엔진 연동이 핵심 업무입니다. OpenSearch 색인 운영, Cache-Aside 정합성, Kafka 기반 도메인 간 연동, JPA 도메인 모델링 — 이 네 축이 모두 제가 설계·운영까지 해 본 영역입니다. 바로 기여 가능한 범위가 명확합니다.
- MSA 환경에서의 비동기 신뢰성 설계가 제 가장 깊은 강점 중 하나입니다. AFTER_COMMIT 커밋 이후 발행, REQUIRES_NEW 별도 트랜잭션으로 실패 메시지 저장, traceId 기반 실패 추적 — 이 패턴은 주문·알림·상품 이벤트 연동에 그대로 이식됩니다.
- 도메인 모델링 역량도 이 자리와 잘 맞습니다. 파편화된 비즈니스 로직을 AbstractPlayService + SpinOperationHandler 조합으로 정리하고, Decorator 패턴으로 계산 로직을 도메인 레이어에 응집시킨 경험은 상품·전시·주문처럼 타입·변형이 많은 커머스 도메인에 특히 유효합니다.

## 메인 질문 1. Confluence → OpenSearch RAG 벡터 색인 파이프라인을 Spring Batch 11 Step으로 설계하셨습니다. 왜 '단일 Job + 11 Step'으로 쪼개셨고, Step 경계를 어떤 기준으로 그으셨나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 후보자가 Spring Batch 선택을 단순 '재시작 가능'이 아니라 실패 격리·청크 커밋·이력 관리 관점에서 설계했는지 확인
- Step 분리의 판단 기준(단일 책임, 의존 방향, 재시작 단위)을 자기 언어로 설명할 수 있는지 검증
- 스케줄러 직접 구현이나 단일 Step 초거대 Tasklet 대비 왜 Batch + Step 분리가 우월한지 트레이드오프를 말할 수 있는지 확인

### 실제 경험 기반 답변 포인트

- 기준 1 — 실패 격리 단위: 페이지 색인 / 댓글 색인 / 삭제 동기화(페이지·댓글·첨부파일) / 인덱스 refresh를 각각 독립 Step으로 분리해, 댓글 Step이 터져도 페이지 Step 결과는 DB에 유지되고 실패 지점부터 재시작 가능하게 설계
- 기준 2 — 데이터 의존 방향: 앞 Step이 수집한 컨텍스트(스페이스 정보, 페이지 ID 목록)를 뒤 Step이 읽어 쓰는 DAG 형태로 구성하되, 컨텍스트는 무거운 JobExecutionContext 대신 @JobScope 빈(ConfluenceJobDataHolder)에 담아 청크 커밋마다 DB 직렬화되지 않게 설계
- 기준 3 — 재시작성: Reader에 ItemStream을 구현해 커서 기반 페이지네이션 위치를 ExecutionContext에 저장, 상태 로더 Step에는 allowStartIfComplete(true)를 박아 재시작 시 @JobScope 빈이 빈 상태로 남아 NPE 나는 문제를 방지
- 기준 4 — 운영 관측성: 색인 시작/완료 마커 Step(startIndexingJobStep / completeIndexingJobStep)을 양끝에 두어 Job 실행 이력과 외부 모니터링을 연결
- Batch 선택 이유: 단순 스케줄러라면 OOM 리스크·실패 재시작·이력 관리를 직접 만들어야 하지만, Spring Batch는 청크 커밋·BATCH_JOB_EXECUTION 이력 테이블·Step별 COMPLETED/FAILED 상태 관리를 기본 제공해 운영 복구 경로를 설계 시간에 이미 확보

### 1분 답변 구조

- Step 경계는 세 기준으로 그었습니다 — 실패 격리 단위, 데이터 의존 방향, 재시작 단위. 페이지·댓글·삭제 동기화를 각각 독립 Step으로 분리해 한 Step이 터져도 다른 Step 결과는 보존되고 해당 지점부터 재시작되게 했습니다.
- Step 간 데이터 공유는 @JobScope 빈 ConfluenceJobDataHolder로 했습니다. JobExecutionContext에 수천 개 페이지 ID를 담으면 청크 커밋마다 DB에 직렬화되는 불필요한 부하가 있어, ExecutionContext는 재시작 커서 같은 경량 상태 전용으로 제한했습니다.
- Batch를 택한 이유는 OOM 방지를 위한 청크 커밋, Job 실행 이력 관리, Step COMPLETED/FAILED 상태 기반 재시작이 모두 기본 제공되기 때문입니다. 단순 스케줄러로 같은 신뢰성을 만들면 복구 경로를 직접 작성해야 하고 운영 중 놓치는 엣지 케이스가 늘어납니다.

### 압박 질문 방어 포인트

- 'Step이 너무 많은 것 아니냐'라는 압박에는 — Step 하나당 단일 책임이고 11개 중 7개는 삭제 동기화·상태 로더처럼 Tasklet 수준으로 짧아 오버헤드가 크지 않다, 오히려 통합하면 부분 실패 시 전체 재실행 비용이 훨씬 크다고 답한다
- '단일 Tasklet으로 만들면 더 단순하지 않냐'에는 — 색인 API 장애·임베딩 API 429·OpenSearch 쓰기 실패가 각기 다른 실패 도메인을 형성하고, 한 Tasklet에 몰면 한 실패가 전체 Job을 되돌려 비용이 증가한다로 반박
- 'allowStartIfComplete(true)가 의도치 않은 재실행을 유발하지 않냐'에는 — 상태 로더 Step에만 한정 적용했고, 멱등한 조회형 Step에만 쓰기 때문에 부작용이 없도록 경계선을 그었다고 설명

### 피해야 할 약한 답변

- 'Spring Batch가 좋아서 Batch로 했다'는 식의 기술 선택 이유를 단순화하는 답변 — 면접관이 원하는 건 단순 스케줄러/ETL 프레임워크 대비 실패 격리·청크 커밋·이력 관리의 구체적 이점 비교다
- JobExecutionContext와 @JobScope 빈을 혼용해 설명하는 답변 — 둘의 저장 위치(DB 직렬화 vs 인메모리 Job 스코프)와 재시작 시 동작 차이를 구분하지 못하면 Batch 경험이 얕다는 인상을 준다
- Step 분리 기준을 '관심사 분리' 같은 추상어로만 대답하는 경우 — 실제로 왜 이 지점에 경계를 그었는지, 경계를 옮기면 어떤 비용이 생기는지 구체화해야 한다

### 꼬리 질문 5개

**F1-1.** Step 간 데이터 공유를 JobExecutionContext 대신 @JobScope 빈으로 바꾼 의사결정을 좀 더 구체적으로 말해 달라 — 어느 순간 부담을 느꼈고 무엇을 측정해 바꿨나?

**F1-2.** 재시작 시 '상태 로더 Step이 COMPLETED여서 스킵되고 @JobScope 빈이 빈 상태로 남는' 시나리오를 직접 겪으셨나? allowStartIfComplete(true) 외에 고려한 대안은?

**F1-3.** 삭제 동기화를 별도 Step 3개(페이지·댓글·첨부파일)로 쪼갠 이유는? 하나로 통합하면 어떤 비용이 생기는지 설명해 달라

**F1-4.** 임베딩 API 장애로 특정 페이지가 반복 실패할 때 ChangeFilterProcessor에서 임계치로 스킵한다고 하셨는데, 이 임계치를 어떻게 결정했고 false positive(정상 문서가 영구 스킵) 방지 장치는 무엇인가?

**F1-5.** 이 Batch 구조를 커머스 상품 색인(가격 변경·전시 상태 변경·재고 이벤트)에 이식한다면 Step을 어떻게 재설계하시겠나?

---

## 메인 질문 2. 색인 Processor를 AsyncItemProcessor + CompositeItemProcessor 조합으로 짜셨습니다. 왜 '비동기'이면서 동시에 '체이닝'이어야 했고, 두 장치의 책임 경계를 어떻게 그으셨나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- I/O 바운드 병목(임베딩 API, 문서 파싱)을 식별하고 실제 개선 전후를 수치화해 설명할 수 있는지
- AsyncItemProcessor의 Future 반환 + AsyncItemWriter.get() 조합을 정확히 이해하고 있는지 (단순히 '병렬 처리한다'가 아님)
- Composite 체이닝의 설계 원칙(단일 책임·교체 가능성) 관점에서 Change/Enrich/Convert/Embed 4단계를 왜 이렇게 나눴는지

### 실제 경험 기반 답변 포인트

- 비동기가 필요한 이유 — 임베딩 API와 문서 파싱 서비스 호출이 모두 네트워크 I/O. 동기면 '페이지1 처리 → API 대기 200ms → 페이지2 처리 → API 대기 200ms'가 직렬이라 청크 10 처리에 최소 2초. 스페이스 수천 페이지면 치명적
- AsyncItemProcessor가 Future<T>를 반환하고, AsyncItemWriter가 Future.get()으로 결과를 수거해 OpenSearch 벌크로 위임. 이로써 Reader는 순차 읽기를 유지하면서 Processor 단계만 parallelChunkExecutor에서 병렬
- Composite 체이닝 4단계: ChangeFilterProcessor(version 비교 → 미변경 null 반환으로 스킵, 반복 실패 문서도 임계치로 스킵) → EnrichmentProcessor(첨부파일·작성자·멘션 accountId→displayName) → BodyConvertProcessor(ADF→Markdown) → EmbeddingProcessor(Markdown+첨부파일 → 벡터)
- 체이닝 설계 원칙 — 각 Processor가 단일 책임. 새 처리 단계(예: PII 마스킹)를 추가할 때 기존 코드 무수정. ChangeFilter가 null을 반환하면 Batch가 자동으로 해당 아이템을 스킵하는 관례를 이용해 '임베딩 API 호출 회피'를 비즈니스 로직 없이 구현
- 스레드 풀 튜닝 포인트 — parallelChunkExecutor의 core/max/queue를 임베딩 API의 허용 동시성과 청크 사이즈를 맞춰 설정. 지나치게 크면 임베딩 API 429 유발, 작으면 병렬화 효과가 없음

### 1분 답변 구조

- 병목이 명확했습니다 — 임베딩 API + 문서 파싱 호출 모두 I/O 바운드라 동기면 청크 하나에 수 분까지 걸렸습니다. AsyncItemProcessor로 Processor 단계만 스레드풀에서 병렬화하고, AsyncItemWriter가 Future.get()으로 결과를 모아 OpenSearch에 벌크 색인하는 구조로 풀었습니다.
- 체이닝은 단일 책임과 교체 가능성 때문입니다. ChangeFilter는 version 비교로 미변경 문서를 스킵해 임베딩 비용 자체를 없애고, Enrichment는 첨부파일·작성자·멘션 표시명을 보강하고, BodyConvert는 ADF→Markdown, Embedding은 벡터 생성 — 각 단계가 null 반환/통과라는 Batch 관례만 지키면 기존 코드를 건드리지 않고 확장할 수 있습니다.
- 튜닝 관점에서는 스레드풀 크기를 임베딩 API 허용 동시성과 청크 사이즈에 맞춰 조정했습니다. 과하게 키우면 429를 유발하고, 작으면 병렬화 효과가 사라집니다.

### 압박 질문 방어 포인트

- '그냥 CompletableFuture로 수동 병렬해도 되지 않냐'에는 — Batch의 청크 커밋·실패 재시작과 Future 수거를 수동으로 엮으면 트랜잭션 경계에서 일관성이 깨지기 쉽고, AsyncItemProcessor가 이미 Batch 트랜잭션 모델에 맞춰 설계돼 있어 직접 구현은 재발명이라고 답한다
- 'ChangeFilter null 반환으로 스킵하는 게 암묵적이지 않냐'에는 — Spring Batch의 공식 관례이며 로깅으로 스킵 카운터를 별도 집계해 가시성을 확보했다고 반박
- '병렬 처리하면 순서가 깨지지 않냐'에는 — 색인 대상 문서는 서로 독립이고 OpenSearch 벌크 색인은 per-doc 단위라 순서 보장이 요구사항이 아니라고 설명

### 피해야 할 약한 답변

- '비동기 처리로 빨라졌다'는 식의 결과만 말하고 Future/AsyncItemWriter 조합의 동작 원리를 설명 못 하는 경우
- Composite의 각 단계가 왜 그 순서인지(Change → Enrich → Convert → Embed) 대답하지 못하면 체이닝 설계 경험이 얕다는 인상
- '스레드풀 크기는 적당히 잡았다'로 끝내는 답변 — 임베딩 API rate limit / 청크 사이즈 / 메모리 관점을 연결해 근거 있는 값이어야 한다

### 꼬리 질문 5개

**F2-1.** 동기 버전 대비 실측 개선 수치가 있나? 어느 구간에서 얼마만큼 개선됐는지 말해 달라

**F2-2.** ChangeFilterProcessor에서 '이전 실행에서 반복 실패한 문서'를 임계치로 자동 스킵한다고 하셨는데, 이 임계치 설계의 근거는? 임베딩 API가 일시 장애인 경우와 영구 결함 문서를 어떻게 구분하나?

**F2-3.** AsyncItemProcessor를 쓰면 청크 단위 트랜잭션과 예외 전파가 복잡해지는데, 하나의 Future가 실패했을 때 해당 청크의 롤백 범위가 어떻게 되나?

**F2-4.** EnrichmentProcessor에서 외부 API(사용자 API)를 또 부르는데, 여기서의 N+1성 호출은 어떻게 완화했나? 캐싱·배치 조회·메모이제이션 중 어떤 선택을 했는지

**F2-5.** 이 구조를 커머스 상품 색인에 이식한다면, 가격/재고/전시 상태 중 어떤 필드가 ChangeFilter 대상이어야 하고, Enrichment 대상은 무엇이 되어야 할까?

---

## 메인 질문 3. OCR gRPC 서버 배포·스케일인 시 503이 묶음 발생했는데, K8s terminationGracePeriodSeconds가 30초로 고정된 제약 하에서 어떻게 예산을 재설계해 해결하셨나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 503의 실제 원인을 Envoy·upstream·SIGTERM·supervisord 레이어 중 어디에서 찾았는지 — 진단 능력 확인
- 플랫폼 제약(NCS가 grace period 30초 고정, 변경 불가)을 받아들이고 예산 재분배로 푸는 실무 판단력
- 'SIGTERM 핸들러 한 줄 추가'가 아니라 preStop hook / supervisord stopwaitsecs / server.stop(grace) 세 레이어를 일관되게 맞추는 시스템 사고

### 실제 경험 기반 답변 포인트

- 증상 확인 — 'upstream connect error... delayed connect error: 111' (ECONNREFUSED). 응답 헤더 server: envoy로 Envoy는 살아있는데 upstream 50051에 연결 거부. 배포/스케일인 시점과 정확히 일치, 30~60초 묶음 발생 후 자연 소멸
- 원인 1 — gRPC 서버 serve() 함수에 SIGTERM 핸들러가 없어 server.wait_for_termination()만 존재. SIGTERM 수신 즉시 종료되어 50051 포트가 닫힘. 반면 preStop sleep 20s 동안 Envoy는 여전히 살아 upstream으로 라우팅 시도 → 거부 → 503
- 원인 2 — supervisord의 [program:grpc-server]에 stopwaitsecs 미설정. 기본값 10초라 SIGTERM 핸들러를 추가해도 graceful drain이 10초를 넘기면 SIGKILL
- 제약 — NHN Cloud NCS는 terminationGracePeriodSeconds를 30초로 고정, API 스펙에 필드 자체가 없어 변경 불가. 모든 종료 작업이 30초 내에 끝나야 함
- 해결 — 예산 재분배: preStop drain + sleep 15s → SIGTERM → server.stop(grace=12s) → 여유 3s = 30s. supervisord stopwaitsecs=17(grace 12 + 여유 5). 세 레이어가 일관된 예산으로 맞춰져야 함

### 1분 답변 구조

- 증상은 Envoy가 살아있는데 upstream 50051에 연결 거부(ECONNREFUSED)였고, 타이밍이 배포/스케일인과 정확히 겹쳤습니다. 원인은 두 겹이었습니다 — gRPC 서버에 SIGTERM 핸들러가 없어 즉시 죽었고, supervisord stopwaitsecs 미설정으로 기본 10초 내 종료 안 되면 SIGKILL이었습니다.
- 제약은 플랫폼(NCS)이 grace period를 30초로 고정하는 것이었습니다. 늘릴 수 없으니 예산을 재분배했습니다 — preStop drain+sleep 15초, SIGTERM 후 server.stop(grace=12초), 여유 3초로 딱 30초에 맞추고, supervisord stopwaitsecs=17로 grace보다 5초 여유를 둬 supervisord가 먼저 SIGKILL 하지 않게 했습니다.
- 핵심은 'SIGTERM 핸들러 한 줄'이 아니라 preStop → SIGTERM → server.stop(grace) → supervisord 네 레이어의 시간 예산이 일관되게 맞아야 한다는 점이었습니다.

### 압박 질문 방어 포인트

- '왜 grace period 자체를 늘려달라고 요청하지 않았냐'에는 — NCS API 스펙에 필드가 없어 요청할 창구가 없었고, 있었어도 플랫폼 공통 변경이라 시간·협의 비용이 큼. 제약을 받아들이고 30초 내에서 푸는 게 실용적이라고 답한다
- 'preStop sleep 20 → 15로 줄이면 Envoy drain이 덜 되지 않냐'에는 — 실제로 drain_listeners 호출은 즉시 완료되고 sleep은 in-flight 처리를 위한 여유이며, gRPC 쪽 grace=12를 확보한 게 더 본질이라 실측으로 503이 사라졌다고 설명
- 'Python asyncio 레벨의 Graceful Shutdown은 왜 고려 안 했냐'에는 — grpcio 동기 서버를 쓰고 있어 server.stop(grace)가 공식 권장이고, 이 값이 in-flight RPC 완료 대기 + 신규 요청 거부를 정확히 수행한다로 반박

### 피해야 할 약한 답변

- 'SIGTERM 핸들러를 추가해서 해결했다'만 말하는 답변 — supervisord stopwaitsecs 레이어를 놓치면 핸들러가 있어도 SIGKILL로 죽는다
- 원인을 '503이라 Envoy 문제'로 오진하는 답변 — Envoy는 살아있고 upstream 연결이 거부된 것이라는 구분이 핵심
- 'terminationGracePeriodSeconds를 늘려달라고 인프라 팀에 요청했다'로 푸는 접근 — 플랫폼 제약을 받아들이고 안에서 푸는 판단이 시니어 신호

### 꼬리 질문 5개

**F3-1.** Envoy drain_listeners가 신규 연결을 끊고 in-flight만 받게 한다고 아는데, 이 호출 자체의 완료 시점은 어떻게 확인했나? curl이 응답하면 drain이 끝난 것으로 간주해도 되나?

**F3-2.** server.stop(grace=12)의 grace는 'in-flight RPC 완료 대기 + 신규 거부' 의미인데, 긴 스트리밍 RPC가 12초 넘어가면 어떻게 되고 그런 케이스를 식별했나?

**F3-3.** supervisord가 grace 내에 종료 안 되면 SIGKILL을 날린다. stopwaitsecs=17을 선택한 근거(grace 12 + 여유 5)가 충분하다고 본 이유는?

**F3-4.** 이 경험을 JVM 기반 Spring Boot 서비스에 이식한다면, Tomcat/Netty graceful shutdown 시간과 preStop 예산을 어떻게 맞추겠나?

**F3-5.** 배포 파이프라인에서 503 재발을 회귀로 감지하려면 어떤 지표/알람을 두시겠나? P95 latency만으로는 묶음 발생을 놓칠 수 있는데

---

## 메인 질문 4. 임베딩 메타데이터 구성을 blocklist(remove) 방식에서 allowlist(EmbeddingMetadataProvider) 방식으로 전환하셨습니다. 왜 기존 방식을 유지하지 않고 리팩터링했고, 전략 패턴 + Spring DI 조합으로 어떤 효과를 얻었나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 후보자가 '확장성'을 추상어로 말하는지, 실제 OCP 위반 사례와 수정 비용을 수치·코드 레벨로 증명하는지
- 전략 패턴을 '이론' 수준이 아니라 Spring DI·@Qualifier·List<Interface> 자동 주입과 연결해 설계해 본 경험이 있는지
- 리팩터링 시 안전장치(테스트 용이성, 삭제 가능한 메서드 식별) 같은 부가 효과를 설계 의도로 챙겼는지

### 실제 경험 기반 답변 포인트

- Blocklist의 본질적 한계 — 14개 remove 호출 블록이 DocumentType마다 달라 if-else 분기가 늘어날 수밖에 없음. 'Task면 이 필드들 제거, Wiki면 저 필드들 제거'가 EmbeddingService 내부에 쌓여 OCP 위반
- 가독성 문제 — '임베딩에 실제로 어떤 필드가 포함되는가?'에 답하려면 remove 목록을 역산해야 함. Allowlist는 '포함할 필드'를 명시적으로 넣기 때문에 구현체만 보면 바로 알 수 있음
- 전략 패턴 적용 — EmbeddingMetadataProvider 인터페이스(getSupportedDocumentTypes + provide). 구현 계층을 AbstractCollabTool / AbstractConfluence로 나눠 공통 필드 로직을 재사용하고, Task는 due_date·closed 추가, Wiki는 공통 필드만, Confluence는 title→subject 폴백 처리
- Spring DI 자동 등록 — Config에서 List<EmbeddingMetadataProvider>로 모든 @Component 구현체를 자동 주입받고, 각 구현체의 getSupportedDocumentTypes()를 순회해 DocumentType→Provider 맵을 빌드. 새 DocumentType 추가 시 @Component 클래스 하나만 만들면 끝
- 부가 효과 — cloneMetadata() / getMetadataValue(String) / putMetadata(String) 같은 '이 패턴 때문에만 존재하던' 메서드가 삭제 가능해짐. 테스트도 구현체별 독립 단위 테스트로 단순화

### 1분 답변 구조

- 기존 방식은 '전체 메타데이터 복사 후 불필요한 14개 필드를 remove'였는데, DocumentType이 늘 때마다 EmbeddingService 내부 if-else 분기와 remove 조합이 같이 늘어나 OCP를 정면으로 위반했습니다. 또 '임베딩에 실제 어떤 필드가 포함되는지'를 알려면 remove 목록을 역산해야 해 가독성도 나빴습니다.
- EmbeddingMetadataProvider 인터페이스를 도입해 '포함할 필드'를 구현체가 명시하게 했고, Abstract 계층으로 공통 필드 로직(CollabTool/Confluence)을 재사용했습니다. Spring이 List<EmbeddingMetadataProvider>를 자동 주입하고 getSupportedDocumentTypes()로 DocumentType→Provider 맵을 만들기 때문에, 새 타입 추가는 @Component 클래스 하나로 끝입니다.
- 결과적으로 EmbeddingService의 14 remove 블록과 if-else 분기가 전부 사라졌고, cloneMetadata() 같이 이 패턴 때문에만 존재하던 메서드들도 함께 제거되어 전반적인 도메인 모델이 가벼워졌습니다.

### 압박 질문 방어 포인트

- '전략 패턴이 오버엔지니어링 아니냐'에는 — 이미 DocumentType이 Task·Wiki·Drive·Confluence 4개였고 공통 스페이스 요구로 5번째 Provider가 추가 예정이었다. 분기가 '3개 이상'이라는 본인 기준을 넘는 시점에 리팩터링한 것이라고 답한다
- 'Spring DI로 자동 주입하면 어느 구현체가 주입됐는지 런타임에만 알 수 있어 디버깅이 어렵지 않냐'에는 — Config에서 맵을 빌드할 때 중복 DocumentType 등록을 예외로 터뜨리는 가드를 두고, 주입된 Provider 목록을 애플리케이션 기동 시 로그로 남겨 가시성을 확보했다로 반박
- 'Abstract 계층이 너무 많지 않냐'에는 — CollabTool과 Confluence가 공통 필드 셋이 다르고(title vs title→subject 폴백) 실제 반복 코드가 있어 Abstract 2개로 최소화한 것. 더 얕게 하면 반복이 되살아난다고 설명

### 피해야 할 약한 답변

- '가독성이 좋아졌다'만 말하고 OCP 위반 사례를 구체 코드로 못 그리는 답변
- 전략 패턴을 설명하면서 '인터페이스 뒀다'에서 멈추는 경우 — Spring DI의 List 자동 주입, @Qualifier, @Component @StepScope 전역 등록까지 연결돼야 실무 경험으로 인정된다
- 'blocklist가 편해서 썼는데 바꿨다' 식의 판단 기준이 약한 답변 — 언제 blocklist가 맞고 언제 allowlist가 맞는지 결정 기준을 제시해야 한다

### 꼬리 질문 5개

**F4-1.** blocklist 방식이 오히려 더 적합한 경우도 있을 텐데, 어떤 조건에서 blocklist를 유지하는 게 낫다고 보나?

**F4-2.** 새 DocumentType 추가 시 @Component 하나로 끝난다고 했는데, DocumentType enum 자체는 변경이 필요하다. enum 변경 없이 런타임 확장하는 설계도 고려해 봤나?

**F4-3.** AbstractCollabTool / AbstractConfluence 2개 Abstract를 둔 기준은? 하나로 합치거나 Provider별로 완전 독립시키는 안과 비교해 트레이드오프를 말해 달라

**F4-4.** 테스트 전략은? 구현체별 단위 테스트 외에 'DocumentType 전수 커버리지'를 회귀 보장하는 장치가 있나?

**F4-5.** 이 구조를 커머스 상품 검색 메타데이터 구성에 이식한다면, 카테고리·브랜드·프로모션 축에서 Provider를 어떻게 쪼개시겠나?

---

## 메인 질문 5. 12일 동안 혼자 AI 웹툰 제작 도구 MVP를 풀스택으로 만드셨습니다. 199 plan / 760 커밋 규모를 감당한 Claude Code 하네스 + 4인 에이전트 팀 구조를 시니어 백엔드 관점에서 어떻게 설계하셨나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI/에이전트 협업 경험이 '툴 사용자' 수준인지 '파이프라인·아키텍처 설계자' 수준인지 판별
- Gemini 모델 전략·Context Cache·Rate Limit Tracking 같은 LLM 운영 이슈를 엔지니어링 문제로 풀어본 경험
- 환각 차단·재시작성·docs-first 같은 결정이 단순 기능이 아니라 '시스템 설계 결정'임을 후보자 본인이 인식하고 있는지

### 실제 경험 기반 답변 포인트

- 입력 정확도 문제 — 초기엔 vibe 코딩이었으나 긴 작업에서 컨텍스트 한도·잘못된 가정으로 실패율이 높았음. /planning 단계를 분리해 Opus로 8단계(기술 가능성·사용자 흐름·데이터 모델·API·화면·엣지 케이스·마이그레이션·검증)를 합의 후 task 파일로 동결
- 재시작성 — /plan-and-build는 tasks/planNNN-*/index.json + phase 파일로 떨어뜨리고, run-phases.py가 pending phase부터 순차 실행. 세션이 끊겨도 git에 task가 있으니 어디서든 이어받음. 휘발 세션이 아니라 task가 영속 상태
- 검증 게이트 — /build-with-teams에 critic(계획 vs 코드 정합성 APPROVE/REVISE)과 docs-verifier(ADR·data-schema 드리프트 방지)를 붙임. 자기 계획을 자기가 검증하면 못 봄 → 역할 분리된 에이전트 팀이 단일 에이전트보다 안정적
- LLM 운영 — Gemini pro 기본 + 429 시 flash → lite fallback(ADR-072). 전역 Rate Limit Tracking Map<modelName, skipUntil>로 분산된 요청들이 같은 모델을 또 두드리지 않음. 30초 재시도 제거(TPM 1분 주기라 무의미)
- 토큰 최적화 — Step1 소설 분석 5개 영역을 1회 Structured Output으로 통합(ADR-059, 토큰 75% 절감 26.8s→13.1s). 원작 소설은 Project 단위 Gemini Context Cache로 묶어 analysis/content-review/treatment/conti/continuation 5단계 공유
- 환각 차단 — continuation이 tail 5컷만 봐서 환각 발생. Grounding 블록을 continuation에 재주입(ADR-132). '허용되는 창의 = 연출, 금지 = 서사 창작'으로 경계 명시. 모델에게 도망갈 자리 부여
- 캐릭터 외형 고정 — 텍스트 anti-drift가 실패. CharacterSheet.isDefault 스키마 + 자동 레퍼런스 prepend + mode(default/outfit) 분기(ADR-133/134). 이미지 일관성은 이미지 채널로 전달
- 레이어별 타입 소스 — Action=Zod / Repository=Prisma / 경계에 mapper(ADR-131). Zod 단일 소스 통일 시도가 Prisma.DbNull·connect/create semantic에서 부딪혀 레이어별 분리로 재정리
- 디자이너 협업 — Container/Presenter + Layout Primitives + 파일 소유권 매트릭스(ADR-129/130). 디자인 변경=globals.css+시각 컴포넌트, 로직 변경=상태·데이터 파일. git conflict가 거의 0
- docs-first — ADR 134개 작성. AI 에이전트 컨텍스트 효율 관점에서 비대한 ADR을 docs-verifier가 지적해 700줄 수준으로 정리. 'ADR은 사람뿐 아니라 에이전트 컨텍스트'라는 관점

### 1분 답변 구조

- 핵심은 에이전트에게 줄 '입력 정확도'를 시스템으로 올리는 거였습니다. vibe 코딩에서 spec 기반으로 전환해, /planning 단계를 Opus로 분리하고 8단계 합의 후 task 파일에 결정 80%를 박은 뒤에야 executor를 돌립니다. task는 git에 영속되기 때문에 세션이 끊겨도 재시작 가능합니다.
- 검증 게이트로 critic(계획 vs 코드 정합성)과 docs-verifier(ADR 드리프트 방지)를 붙였습니다. 자기 계획을 자기가 검증하면 못 봅니다 — 역할 분리된 에이전트 팀이 단일 에이전트보다 안정적이라는 게 12일의 가장 큰 교훈 중 하나입니다.
- LLM 운영 측면에서는 Gemini pro 기본 + 429 시 flash→lite fallback을 쓰되 전역 Rate Limit Tracking Map으로 분산 요청이 같은 모델을 또 두드리지 않게 했고, 원작 소설은 Project 단위 Context Cache로 묶어 5단계 호출이 공유하게 했습니다. Step1은 5개 영역을 1회 Structured Output으로 통합해 토큰 75% 절감했습니다.
- 환각 차단은 프롬프트 카피라이팅이 아니라 호출 구조 설계였습니다. continuation이 tail 5컷만 봐서 환각이 났고, grounding 블록을 재주입하는 것으로 해결했습니다 — 채널 mismatch를 제거한 거고, 같은 원리로 캐릭터 외형 고정은 텍스트 anti-drift가 아니라 이미지 레퍼런스 자동 prepend로 풀었습니다.

### 압박 질문 방어 포인트

- '에이전트가 다 한 건데 본인 기여가 뭐냐'에는 — 199 plan의 설계, 134 ADR의 트레이드오프 판단, 하네스 5단계(vibe→planning→plan-and-build→build-with-teams→integrate-ux) 진화 자체가 내 작업. 에이전트는 실행자, 방향·검증·구조는 사람의 영역이라고 답한다
- '최신 스택(Next.js 16 / Prisma 7 / Zod 4)은 리스크 아니냐'에는 — 개인 MVP는 N-1 보수주의가 안 맞음. @source inline·z.toJSONSchema() 같은 신기능이 없었으면 우회 코드가 더 많아져 결과적으로 리스크가 증가한다로 반박
- 'Gemini pro 기본이 비싸지 않냐'에는 — 저가 모델로 생성 후 재생성이 반복되면 총 비용이 오히려 증가. '단가'가 아니라 '재생성 포함 총 호출 횟수'로 비용을 봐야 한다는 관점(ADR-072)을 설명
- '커머스 백엔드 면접과 무슨 관련이냐'에는 — LLM fallback·Rate Limit Tracking·Context Cache는 Resilience4j Circuit Breaker·캐시 정합성·비용 예산 같은 백엔드 근본 문제와 같은 모양. 도구만 바뀐 것이라고 연결

### 피해야 할 약한 답변

- 'Claude Code 써서 빠르게 만들었다'로 끝나는 답변 — 하네스 설계·에이전트 역할 분리·검증 게이트가 안 들어가면 '툴 사용자' 인상
- 환각 차단을 'DO NOT invent 같은 문구를 추가했다'로 설명 — 실제 해결은 호출 구조 설계였다는 본질이 빠진다
- ADR 134개 숫자만 자랑하는 답변 — 왜 docs-first가 AI 시대의 컨텍스트 도구가 되는지 관점이 필요하다
- '혼자 12일에 풀스택 다 했다'로 압축 — 인프라·DB·AI 파이프라인·디자이너 통합·디자인 시스템 중 어떤 결정이 가장 어려웠는지 말하지 못하면 깊이가 드러나지 않는다

### 꼬리 질문 5개

**F5-1.** critic과 docs-verifier를 같은 모델 기반으로 돌렸나, 다른 모델로 돌렸나? 역할별로 시스템 프롬프트만 바꿨다면 동일 모델의 자기 검증 한계는 어떻게 완화했나?

**F5-2.** Gemini Context Cache의 만료(5분)는 장시간 파이프라인에서 적중률을 떨어뜨릴 수 있다. 만료 갱신 전략은? cache 실패 시 fallback은?

**F5-3.** 60컷 일괄 생성에서 SSE 대신 Promise.allSettled 클라이언트 병렬로 바꿨는데, 브라우저 6 connection 제한이 자연스러운 throttling이 된다고 하셨다. 서버 측에서 추가로 두어야 할 보호 장치(토큰 버킷 등)는 없었나?

**F5-4.** 레이어별 타입 소스(Action=Zod / Repository=Prisma)에서 mapper 레이어가 중복 작성의 비용을 낳진 않았나? 자동화 여지는?

**F5-5.** 이 하네스 경험을 올리브영 커머스 백엔드 팀의 개발 속도·안정성 향상에 이식한다면, 어느 지점(배포·장애 대응·대규모 리팩터링·ADR 운영)에 먼저 적용하시겠나?

---

## 최종 준비 체크리스트

- 자기소개(1분): AI 서비스 팀 이동 후 11 Step RAG 파이프라인·OCR 503·메타데이터 리팩터·12일 MVP 네 꼭지를 순서대로 언급하되 각 꼭지당 15초 이내로 분량을 맞춘다 — 길어지면 follow-up의 여지를 빼앗긴다
- Spring Batch 답변에서 @JobScope vs JobExecutionContext 구분, allowStartIfComplete(true) 필요 이유, AsyncItemProcessor의 Future 반환 → AsyncItemWriter.get() 수거 플로우를 반드시 한 호흡으로 설명할 수 있게 연습한다
- OCR 503 답변에서는 'SIGTERM 핸들러 한 줄'이 아니라 preStop(15s) + server.stop(grace=12) + supervisord stopwaitsecs=17의 세 레이어 예산이 30초 안에서 일관되게 맞아야 한다는 포인트를 강조한다 — 플랫폼 제약을 받아들이고 안에서 푸는 태도를 드러낸다
- 메타데이터 전략 패턴에서는 Spring DI 자동 주입(List<EmbeddingMetadataProvider> + getSupportedDocumentTypes → Map 빌드) 부분을 특히 디테일하게 준비한다 — '인터페이스 뒀다'에서 멈추지 않고 DI 레이어까지 이어가야 실무 경험으로 인정된다
- AI 웹툰 MVP는 '툴 사용자'가 아니라 '파이프라인 설계자'로 포지셔닝한다 — 하네스 5단계 진화, 에이전트 역할 분리, Gemini 전역 Rate Limit Tracking + Context Cache + fallback 전략을 Resilience4j·캐시 정합성·비용 예산 같은 백엔드 원리와 같은 모양이라고 연결한다
- 모든 답변 말미에 '이걸 커머스 도메인(상품·전시·주문)에 이식한다면'으로 한 문장 붙여 올리브영 업무와의 직접 연결을 드러낸다 — 경험의 이식 가능성을 면접관에게 계산해 주는 효과
- 수치는 단 1개라도 반드시 들고 간다 — 11 Step, 447 테스트 파일, 199 plan / 760 커밋 / 134 ADR / 12일, 토큰 75% 절감·26.8s→13.1s, preStop 15s + grace 12s + 여유 3s = 30s. 수치가 없으면 '경험'이 '일화'로 전락한다
- 약점 방어: 'Kotlin 미사용'은 Java 21 + Spring Boot 3 + Gradle + 멀티모듈 MSA로 상쇄하고, 'DB 자가 평가 약점'은 MVCC/B+Tree/InnoDB 락 같은 강점으로 선제 방어한다 — 질문 받기 전에 스스로 프레이밍을 잡는다
