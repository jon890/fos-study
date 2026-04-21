# [초안] AI 서비스 개발팀 경험 기반 시니어 백엔드 면접 질문은행

---

## 이 트랙의 경험 요약

- 대상 경험: NHN AI 서비스 개발팀 2025.12~ 재직 중 수행한 4개 핵심 과업 — (1) Confluence → OpenSearch RAG 벡터 색인 Spring Batch 11-Step 파이프라인 신규 설계/구현, (2) gRPC OCR 서버 배포·스케일인 503 해결(Graceful Shutdown·K8s grace 예산 재배분), (3) 임베딩 메타데이터 Blocklist → Allowlist(EmbeddingMetadataProvider) OCP 리팩터링, (4) 12일 단독 풀스택 AI 웹툰 제작 도구 MVP(Next.js 16 + Prisma 7 + Gemini, 하네스 기반 4인 에이전트 팀, 199 plan / 760 커밋).
- 면접 포지션: CJ 올리브영 커머스플랫폼유닛 Back-End 개발(경력 5년+), 웰니스개발팀. 연결 포인트: MSA·Event-Driven·Cache-Aside 하이브리드 연동 전략, 대용량 트래픽 무중단 배포(Feature Flag/Shadow Mode), JPA/Hibernate 도메인 모델링, Kafka 기반 비동기 연동, 대용량 데이터 색인 운영 경험을 AI 서비스 팀·게임 팀 실무 사례로 구체화.
- 방향성: AI/에이전트 협업 경험을 '툴 사용자' 수준이 아닌 '파이프라인·아키텍처 설계자' 수준으로 각인. Spring Batch 내부 동작(@JobScope·@StepScope·ItemStream·allowStartIfComplete), I/O 바운드 병렬화 설계(AsyncItemProcessor/Writer·Future), 분산 시스템 종료 시퀀스(SIGTERM·preStop·supervisord·Envoy drain), OCP/전략 패턴 기반 리팩터링, 하네스 파이프라인의 '역할 분리 에이전트 팀'(planner/critic/executor/docs-verifier)과 '스펙 기반 코딩' 전환 논거를 시니어 백엔드 설계 역량으로 매핑.
- 준비 기한: 면접 2026-04-21. 이번 draft는 핵심 5문항 + 25개 꼬리질문, 자기소개(1분·올리브영 Fit), 지원동기/커리어 이동 논거, 최종 체크리스트까지 커버. 이후 반복 run에서 숫자·ADR 번호·올리브영 블로그 인용 및 역질문 보강 예정.

## 1분 자기소개 준비

- NHN에서 4년간 Spring Boot 기반 MSA 백엔드를 담당해왔습니다. 소셜 카지노 슬롯 팀에서 신규 게임 개발·성능 개선·아키텍처 재설계를 거쳐, 2025년 12월부터는 AI 서비스 개발팀에서 사내 RAG 플랫폼의 색인 파이프라인을 설계·운영하고 있습니다.
- 대표적인 기술 경험 네 가지는 첫째, Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 11-Step 파이프라인을 처음부터 설계해 AsyncItemProcessor로 임베딩 API 호출을 병렬화하고 Step 단위 실패 격리·재시작 가능성을 확보한 것, 둘째, gRPC OCR 서버의 배포·스케일인 503을 Envoy drain·SIGTERM 핸들러·supervisord stopwaitsecs·preStop 예산을 재배분해 K8s 30초 grace 제약 안에서 해결한 것입니다.
- 셋째, 임베딩 메타데이터 구성을 14개 remove가 분기되던 Blocklist 방식에서 EmbeddingMetadataProvider 기반 Allowlist 전략 패턴으로 바꿔 DocumentType이 늘어도 EmbeddingService를 수정하지 않게 만들어 OCP를 회복시킨 리팩터링, 넷째, 2026년 4월 12일 동안 단독으로 Next.js 16 + Prisma 7 + Gemini 기반 AI 웹툰 제작 도구 MVP를 만들면서 Claude Code 하네스로 planner/critic/executor/docs-verifier 4인 에이전트 팀을 조율해 199 plan·760 커밋을 처리한 경험입니다.
- 앞선 게임 팀 시절에는 Kafka @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + 스케줄러 재시도로 비동기 흐름의 신뢰성을 구조화했고, RabbitMQ Fanout Exchange + Hibernate PostCommitUpdateEventListener + StampedLock으로 다중 서버 인메모리 캐시 정합성을 설계한 경험이 있습니다. 이 실무 스택이 1,600만 고객을 대상으로 하는 올리브영 커머스플랫폼의 MSA·Event-Driven·Cache-Aside 요구와 그대로 맞닿아 있다고 보고 지원했습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영 기술 블로그의 'MSA 환경 도메인 데이터 연동 전략'에서 제시한 Cache-Aside + Kafka 이벤트 하이브리드 구조는, 제가 게임 팀에서 RabbitMQ Fanout + PostCommitUpdateEventListener + StampedLock으로 다중 서버 인메모리 캐시 정합성을 구현한 경험과 설계 지점이 매우 유사합니다. '어떤 데이터는 캐시로, 어떤 데이터는 이벤트로, 어떤 데이터는 Redis Key만 캐싱하고 API로 가져오는가' 하는 판단을 실무에서 체감한 상태라, 상품·전시 데이터 연동 의사결정에 바로 기여할 수 있습니다.
- Kafka 기반 Event-Driven 설계 경험이 단순 메시지 발행에 머무르지 않습니다. @TransactionalEventListener(AFTER_COMMIT)로 커밋 후 발행을 보장하고, 전송 실패 시 Propagation.REQUIRES_NEW로 분리된 트랜잭션에서 Dead Letter Store에 저장한 뒤 스케줄러 재전송 + traceId 기반 실패 추적까지 설계한 경험은 '무중단 OAuth2 전환기'에서 드러난 Resilience4j 3단계 보호 + Shadow Mode 배포 문화에 자연스럽게 이어질 것입니다.
- 대용량 데이터 색인·증분 처리·삭제 동기화 운영 경험은 커머스의 상품 검색·전시 인덱싱 도메인에 거의 그대로 이식 가능합니다. 11-Step 파이프라인에서 다룬 AsyncItemProcessor 병렬화, @JobScope 기반 Step 간 데이터 공유, allowStartIfComplete(true)로 재시작 안전성 확보, 커서 기반 ItemStream 재시작은 대규모 배치·벌크 API 운영에서 반복적으로 재사용되는 패턴입니다.
- JPA/Hibernate 기반 도메인 모델링과 테스트 인프라 체계화 경험도 강점입니다. 스핀 타입별 파편화된 비즈니스 로직을 AbstractPlayService + SpinOperationHandler 템플릿 + 전략 인터페이스로 통합하고 static 의존을 DI로 전환해 447개 테스트 파일로 덮은 경험은, 상품·전시·주문처럼 도메인 타입이 다층적인 이커머스 모델링 요구에 동일한 방식으로 적용 가능합니다.
- AI 개발 도구 도입을 팀 생산성으로 확장한 경험은 올리브영이 중시하는 '학습과 성장' 가치와 직결됩니다. Cursor Rules 20+개 구축으로 신규 슬롯 게임 3종을 에이전트 단독 구현에 성공시키고 팀에 전파한 경험, 12일 만에 하네스 기반 웹툰 MVP를 혼자 풀스택으로 완성한 경험은 '툴 사용자'가 아니라 '조직의 개발 속도를 구조적으로 끌어올리는 설계자' 역할을 보여줍니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 게임 도메인에서 쌓은 동시성·이벤트 드리븐·캐시 정합성 설계 역량이 대규모 커머스 트래픽 환경에서 어떻게 작동하고 어디서 깨지는지를 직접 경험하고 싶습니다. 게임 서비스도 실시간성이 높지만, 커머스는 재고·전시·가격·주문처럼 도메인이 본질적으로 더 다층적이고 트랜잭션 요구가 복잡해 설계자로서 다음 단계의 난이도를 맞이하게 됩니다.
- AI 서비스 팀에서 Spring Batch·OpenSearch·전략 패턴 기반 확장 구조를 처음부터 설계해본 경험은, 향후 '대용량 데이터·대량 트래픽·복잡한 도메인'을 동시에 다루는 커머스 현장에 그대로 적용 가능한 범용 역량입니다. 사내 제품 개발을 넘어 B2C 고객이 직접 체감하는 서비스의 품질과 속도에 기여하고 싶은 단계에 있습니다.
- 게임/AI 서비스 모두 사내·내부 사용자가 주 사용자였지만, 1,600만 고객이 실시간으로 부딪히는 서비스에서 설계 결정의 블라스트 반경을 감당해본 경험으로 커리어의 폭을 넓히고자 합니다. 올영세일 같은 피크 트래픽 이벤트에서 무중단 배포·트래픽 제어·장애 격리를 실제로 다뤄보는 것이 다음 4~5년을 결정짓는 기회라고 판단했습니다.

### 왜 올리브영인가
- 올리브영 기술 블로그를 통해 공개된 설계 수준이 지원 동기의 중심입니다. 'MSA 환경 도메인 데이터 연동 전략'의 Cache-Aside + Kafka 하이브리드, '무중단 OAuth2 전환기'의 Feature Flag·Shadow Mode·Resilience4j 3단계 보호·Jitter ±30초로 Peak TPS 40% 감소 같은 의사결정은, 단순 구현이 아니라 '운영 제약 아래 설계 예산을 어떻게 배분하는가'를 고민한 팀이라는 신호로 읽힙니다. 제가 gRPC OCR 503 해결에서 K8s 30초 grace 안에 preStop·SIGTERM·supervisord·in-flight drain을 재배분했던 접근과 사고방식이 같습니다.
- 1,600만 고객 규모와 올영세일 같은 10배 트래픽 이벤트는 제가 지금까지 다뤄본 규모를 넘어서는 실전 환경이고, 동시에 팀이 이미 Cache-Aside·Event-Driven·Circuit Breaker·Feature Flag·Shadow Mode 같은 '검증된 도구 세트'를 운영 중이기 때문에 새로 학습해야 할 추상 개념과 이미 체득한 패턴의 비율이 이상적으로 맞습니다. 기여 속도가 빠르고, 그만큼 스스로 성장 가속이 큰 환경이라고 판단했습니다.
- 웰니스 도메인은 건강·식품 등 소비자 관여도가 높은 카테고리라 '정확성'과 '빠름'이 동시에 요구되는 분야입니다. 제가 게임 팀에서 '실시간 응답 + 트랜잭션 정합성', AI 서비스 팀에서 '검색 품질 + 증분 처리'의 트레이드오프를 실제로 해결해본 경험이, 웰니스 상품의 상세 정보·리뷰·재고·추천을 다루는 커머스 백엔드 문제와 직접 맞닿는다고 봅니다.

### 왜 이 역할에 맞는가
- 커머스플랫폼유닛은 상품·전시 로직·검색 엔진 연동·RESTful API·JPA 도메인 모델링·MSA 운영을 한 팀에서 모두 다룹니다. 제가 게임 팀에서 Decorator 패턴으로 파편화된 계산 로직을 도메인 레이어로 응집시키고 static 의존을 DI로 전환한 경험, AI 서비스 팀에서 전략 패턴으로 스페이스별 메타데이터 포맷 차이를 흡수한 경험은, 상품·전시·주문처럼 '타입별로 조금씩 다른 규칙'이 끊임없이 추가되는 커머스 도메인에서 가장 자주 쓰이는 설계 도구입니다.
- Kafka·Redis·JPA·Spring Boot·MSA·Docker/Kubernetes 우대 스택이 제 실무 스택과 그대로 겹칩니다. Kafka 실패 복구용 Dead Letter Store + traceId 추적, Spring Batch + OpenSearch 벌크 색인, Hibernate 이벤트 리스너 기반 자동 캐시 갱신, RabbitMQ Fanout + StampedLock 동시성 제어를 실제 프로덕션에서 설계·운영해본 경험이, '5년 이상 백엔드, JPA/Hibernate 도메인 모델링, MSA, 비동기 처리' 자격 요건에 꼭 맞춰져 있습니다.
- 1차 Live Coding + 구술, 2차 Whiteboard Test 같은 전형 구조는 '코드를 짤 줄 아는가'가 아니라 '의사결정의 근거를 말로 설명할 수 있는가'를 보는 절차라고 이해합니다. 저는 기술 결정의 배경과 트레이드오프를 ADR/문서로 남기는 습관을 꾸준히 유지해왔고, AI 웹툰 MVP에서도 134개 ADR을 축적한 경험이 있어 화이트보드 앞에서 설계 의도를 풀어내는 대화에 강점이 있다고 판단합니다.

## 메인 질문 1. Confluence 문서를 OpenSearch에 색인하는 RAG 파이프라인을 왜 11개의 Spring Batch Step으로 쪼갰고, 색인 Step 내부에서는 어떤 구조를 선택했나요? 특히 AsyncItemProcessor를 도입한 판단 근거와 트레이드오프를 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 대용량 배치 파이프라인을 처음부터 설계해본 적이 있는지, 단일 책임·실패 격리·재시작 가능성이라는 Spring Batch의 본래 가치를 체득한 상태로 쓰고 있는지 확인하려는 의도.
- I/O 바운드 작업 병렬화에 대한 이해가 '스레드풀을 쓴다' 수준을 넘어 AsyncItemProcessor/AsyncItemWriter·Future 수렴·순서 보장 포기·예외 전파 같은 실무 트레이드오프까지 가고 있는지 검증.

### 실제 경험 기반 답변 포인트

- Step 분리 근거는 두 축입니다. (1) 단일 책임으로 각 Step이 실패해도 다른 Step의 결과가 살아 있음(페이지·댓글·첨부파일·삭제 동기화가 독립), (2) 재시작 지점 세분화로 임베딩 API 장애 시 해당 Step만 재개.
- 전체 11-Step: startIndexingJob → initConfluenceSource → spaceCollect → pageIndexing → pageIdCollect → commentIndexing → deletedPage/Comment/AttachmentRemove → indexRefresh → completeIndexingJob. 앞 Step이 @JobScope 홀더에 저장한 데이터를 뒤 Step이 읽는 방식으로 데이터 공유.
- 색인 Step 내부는 Reader → CompositeItemProcessor(ChangeFilter → Enrichment → BodyConvert → Embedding) → Writer 구조. ChangeFilter가 OpenSearch version과 비교해 미변경 문서는 null 반환 → Spring Batch가 스킵 → 임베딩 API 호출 자체를 차단.
- AsyncItemProcessor 선택 근거: 임베딩 API와 문서 파싱 API가 모두 I/O 바운드. 동기 처리 시 청크(10건) 하나를 처리하는데 API 대기시간 × 10이 그대로 쌓여 청크당 수 분 수준까지 늘어남. AsyncItemProcessor로 감싸면 TaskExecutor 스레드풀에서 청크 내 문서가 병렬 처리되고 Future를 반환, AsyncItemWriter가 Future.get() 후 OpenSearch 벌크 색인으로 수렴.
- 트레이드오프: 청크 내 순서 보장 포기(색인 도메인은 문서 단위라 무관), 스레드풀 튜닝 이슈, Future.get()에서의 예외 전파 복잡도, 외부 API TPS 한도 초과 시 Rate Limit 관리 필요. 그래서 ChangeFilter로 호출 자체를 최소화하고, 임계치 초과 실패 문서는 자동 스킵 로직을 추가.

### 1분 답변 구조

- 11개 Step 분리는 두 가지 목표입니다. 실패 격리로 댓글 Step이 터져도 페이지 Step 결과는 살아있고, 재시작 지점을 세분화해 임베딩 API 장애 시에도 해당 Step부터만 재개됩니다.
- 색인 Step 내부는 Reader → CompositeItemProcessor(변경 감지 → 데이터 보강 → ADF→Markdown → 임베딩) → Writer입니다. 처음에 ChangeFilter가 OpenSearch의 version과 비교해 미변경 문서를 스킵시켜, 비싼 임베딩 API 호출 자체를 차단합니다.
- AsyncItemProcessor는 임베딩/파싱이 모두 I/O 바운드였기 때문입니다. 동기면 청크 10건이 API 응답 대기시간만큼 직렬화되는데, 스레드풀로 병렬 처리하면 청크당 처리시간이 가장 느린 한 건 수준으로 수렴합니다. Writer 쪽은 AsyncItemWriter가 Future.get()으로 모은 뒤 OpenSearch에 벌크로 넘깁니다.
- 트레이드오프로 청크 내 순서 보장을 포기하고(문서 단위라 무관), 스레드풀 크기·외부 API TPS 한도·예외 전파 복잡도를 추가로 관리해야 했습니다. 이 비용은 ChangeFilter로 호출을 줄이고 임계치 초과 문서 자동 스킵으로 흡수했습니다.

### 압박 질문 방어 포인트

- '그냥 병렬 스트림 써도 되지 않냐'는 질문에는: 병렬 스트림은 재시작·커밋 경계·실패 롤백·진행 이력 저장을 스스로 책임져야 합니다. Spring Batch는 ExecutionContext·JobRepository·청크 커밋·allowStartIfComplete 제어를 이미 제공하므로, 대용량 I/O 바운드 작업을 '안전하게 중단하고 이어서 돌 수 있는' 수준으로 끌어올리는 비용이 훨씬 낮습니다.
- 'Step이 너무 많은 것 아니냐, 오버엔지니어링이다'라는 지적에는: 색인/댓글/첨부파일/삭제 동기화의 실패 모드가 다릅니다. 댓글은 Confluence API rate limit, 첨부파일은 외부 파싱 서비스 리다이렉트, 삭제는 status 파라미터 변경이 실패 원인이 되는데, 하나의 거대한 Step으로 묶으면 실패 시 처음부터 다시 돌아야 해서 전체 SLA가 오히려 악화됩니다. Step 수는 늘었지만 각각이 30~200줄 수준으로 단순하고 테스트 가능성이 높습니다.

### 피해야 할 약한 답변

- 'Spring Batch 공식 예제를 따라 했습니다' 수준의 답변 — 설계 의도·실패 격리 근거·AsyncItemProcessor 트레이드오프가 빠지면 '라이브러리 사용자'로 평가됩니다.
- 'AsyncItemProcessor를 쓰면 빨라서 썼습니다'처럼 I/O 바운드 여부·스레드풀 크기·Future.get() 예외 전파·순서 보장 포기 같은 대가를 언급하지 않는 답변.
- 11 Step을 그냥 나열만 하고 Step 간 데이터 공유 방식(@JobScope 홀더), 재시작 시 안전성(allowStartIfComplete) 같은 Spring Batch 내부 이해를 보여주지 못하는 답변.

### 꼬리 질문 5개

**F1-1.** 청크 사이즈와 스레드풀 크기를 결정할 때 어떤 지표(임베딩 API 응답 p95, TPS 한도, 메모리, JVM GC)를 기준으로 삼았나요, 그리고 튜닝 과정에서 어떤 실패를 겪었나요?

**F1-2.** AsyncItemProcessor 사용 시 청크 내 순서 보장이 깨지는데, 재시작 시 중복 색인이나 삭제-색인 순서 역전 같은 문제는 어떻게 방지했나요?

**F1-3.** ChangeFilterProcessor에서 Confluence API의 version 비교를 선택한 이유는 무엇이고, ETag·lastModifiedTime·해시 비교 같은 대안 대비 어떤 장단점이 있었나요?

**F1-4.** CompositeItemProcessor 체인의 특정 단계(예: 임베딩 API)에서 예외가 났을 때, 전체 청크 롤백 대신 부분 실패를 허용하는 재시도 전략이나 Dead Letter 처리는 어떻게 설계했나요?

**F1-5.** Step 단위 재시작 가능성을 실제로 검증해본 적이 있나요? 어떤 장애 시나리오(JVM 강제 종료, OpenSearch 단절, 임베딩 API 장애)에서 커서가 살아있음을 확인했는지 구체적으로 설명해 주세요.

---

## 메인 질문 2. Spring Batch Step 간 데이터 공유를 처음에는 JobExecutionContext에 넣었다가 @JobScope 빈(ConfluenceJobDataHolder)으로 옮겼다고 하셨는데, 그 판단 근거와 재시작 안전성을 어떻게 확보했는지, 그리고 @StepScope 빈 충돌(NoUniqueBeanDefinitionException)은 어떻게 풀었는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- Spring Batch 프레임워크 내부 동작(JobExecutionContext 직렬화, BATCH_JOB_EXECUTION_CONTEXT 테이블, @JobScope/@StepScope 프록시, allowStartIfComplete)을 표면적으로 외운 수준이 아닌 실제 운영상의 선택지로 이해하고 있는지 확인.
- '단순히 쓴다'가 아니라 'Spring의 스코프·DI·프록시 모델을 직접 활용해 설계 문제를 풀 줄 아는가'를 시니어 수준에서 검증.

### 실제 경험 기반 답변 포인트

- 초기에는 스페이스 정보와 페이지 ID 목록을 JobExecutionContext.put()으로 저장. 문제: JobExecutionContext는 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블에 직렬화 저장되는 구조라, 수천 건의 페이지 ID를 커밋마다 DB에 쓰고 읽는 불필요한 I/O가 누적.
- 원칙을 재정리: JobExecutionContext는 '재시작을 위한 경량 커서 상태'(예: 마지막 처리 offset)만 담는 용도. 도메인 데이터는 메모리 수명 관리가 명시적인 별도 홀더에 둬야 함.
- 해결: ConfluenceJobDataHolder를 @JobScope + @Component로 선언. @JobScope는 내부적으로 proxyMode=TARGET_CLASS를 포함해 CGLIB 프록시가 만들어지므로 싱글톤 빈에 안전하게 주입 가능. 실제 호출 시점에 현재 Job 스코프 인스턴스로 위임.
- 재시작 함정: Job이 실패해 재시작하면 새 JobExecution이 생성되고 @JobScope 빈도 초기화됨. 상태 수집 Step이 이미 COMPLETED면 Spring Batch가 기본적으로 스킵하는데, 그러면 홀더가 빈 상태로 남아 NPE. allowStartIfComplete(true)를 상태 로더 Step(spaceCollect, pageIdCollect)에 명시적으로 설정해 재시작 시 반드시 재실행되게 보장. get*() 메서드에 IllegalStateException 가드를 둬 호출 순서 오류를 빌드·테스트에서 즉시 드러냄.
- @StepScope 빈 충돌: 두 잡이 같은 타입의 @StepScope 빈을 각자 Config에서 @Bean으로 정의하면서 NoUniqueBeanDefinitionException 발생. 공용 컴포넌트는 @Component @StepScope로 전역 1개만 등록, 잡별로 다른 의존을 주입해야 할 때만 Config에서 @Bean으로 분기하고 @Qualifier로 명시. 테스트 코드에서도 @Autowired에 @Qualifier를 반드시 맞춰야 빈 주입 실패를 피할 수 있음.

### 1분 답변 구조

- JobExecutionContext는 청크 커밋마다 DB 테이블에 직렬화되는 구조라, 수천 건짜리 페이지 ID 리스트를 넣으면 커밋 횟수만큼 쓸데없는 I/O가 발생합니다. 그래서 '재시작 커서 같은 경량 상태'만 JobExecutionContext에 두고, 도메인 데이터는 @JobScope 빈으로 분리하는 원칙을 세웠습니다.
- ConfluenceJobDataHolder를 @JobScope + @Component로 선언하면 CGLIB 프록시가 싱글톤 빈에 주입되고, 호출 시점에 현재 Job 스코프 인스턴스로 위임됩니다. 싱글톤에서 안전하게 참조 가능합니다.
- 재시작 시 함정이 하나 있습니다. 상태 수집 Step이 이미 COMPLETED면 스킵되면서 홀더가 비어 NPE가 나는데, allowStartIfComplete(true)를 상태 로더 Step에만 명시해 재시작 시 반드시 재실행되게 하고, get*() 메서드에 IllegalStateException 가드를 넣어 호출 순서 오류를 빠르게 드러내도록 했습니다.
- @StepScope 충돌은 두 잡이 같은 타입의 빈을 각자 Config에 @Bean으로 등록하면서 발생했습니다. 공용 컴포넌트는 @Component @StepScope로 전역 1개만 두고, 잡별로 다른 의존이 필요할 때만 @Bean + @Qualifier로 분기하는 방식으로 정리했습니다.

### 압박 질문 방어 포인트

- '그냥 싱글톤 빈에 데이터 담고 쓰면 안 되냐'는 질문에는: 싱글톤은 JVM 생명주기에 묶여 있어 이전 Job의 잔여 상태가 다음 Job 실행에 누출될 위험이 있고, 테스트 간 상태 격리도 깨집니다. @JobScope는 Job 경계에서 라이프사이클이 끝나므로 안전합니다.
- 'allowStartIfComplete(true)를 남발하면 재시작 의미가 무너지지 않냐'는 지적에는: 모든 Step에 주는 게 아니라 '상태 로더 Step'에만 명시합니다. 실제 색인·삭제 Step은 기본 정책을 유지해 중간 완료된 Step의 결과를 재사용하고, 상태 로더만 '재시작 시 반드시 메모리를 다시 채워야 한다'는 의미론을 갖게 분리했습니다. 즉 의도된 비대칭입니다.

### 피해야 할 약한 답변

- '@JobScope는 Job 범위니까 그냥 썼다' 수준의 답변 — 직렬화 비용·프록시 모드·재시작 시 빈 초기화 문제를 설명하지 못하면 프레임워크 표면만 쓴 인상을 줍니다.
- @StepScope 빈 충돌을 '@Qualifier로 풀었다'로만 답하고, 공용 컴포넌트(@Component @StepScope)와 잡별 전용 빈(@Bean @StepScope)의 경계를 구분하지 못하는 답변.

### 꼬리 질문 5개

**F2-1.** @JobScope 내부의 CGLIB 프록시가 정확히 어느 시점에 만들어지고, 싱글톤 빈에서 프록시를 호출했을 때 실제 인스턴스 해석이 어떻게 일어나는지 설명해 주세요.

**F2-2.** allowStartIfComplete(true)가 적용된 Step과 그렇지 않은 Step을 어떤 기준으로 분류했나요? 기준을 잘못 적용하면 어떤 장애가 발생할 수 있나요?

**F2-3.** @JobScope 인메모리 홀더 방식은 멀티 인스턴스 스케줄링(Job을 여러 인스턴스가 분산 실행)에서는 어떻게 한계가 드러날까요? 한계가 드러났을 때 어떻게 우회할 생각인가요?

**F2-4.** JobExecutionContext에 저장해야 마땅한 데이터와 @JobScope 홀더에 저장해야 할 데이터의 구분 기준을, 팀원이 규칙으로 이해하도록 한 줄로 정의한다면 뭐라고 쓰시겠어요?

**F2-5.** @StepScope 공용 컴포넌트로 묶을 때(@Component) vs 잡별 Config로 분리할 때(@Bean)를 판단하는 당신의 경험적 체크리스트는 무엇인가요?

---

## 메인 질문 3. gRPC OCR 서버가 배포·스케일인 중 503 에러를 내던 문제를, NHN Cloud의 terminationGracePeriodSeconds가 30초로 고정된 제약 안에서 어떻게 진단하고 해결했는지 설명해 주세요. 특히 왜 그 시간 예산을 preStop 15초 + grace 12초 + 여유 3초로 나누었는지 결정 근거가 궁금합니다.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 장애 로그에서 시작해 Envoy·gRPC·supervisord·K8s preStop·SIGTERM의 종료 시퀀스를 끝까지 추적해 진짜 원인을 짚는 능력을 보려는 의도. 올리브영이 운영하는 MSA + 무중단 배포 환경에서 핵심 역량이기 때문.
- 바꿀 수 없는 인프라 제약(플랫폼 grace 고정 30s) 하에서 예산을 재배분해 문제를 푸는 설계 사고를 검증. 'Feature Flag + Shadow Mode + Resilience4j 3단계'로 피크 TPS 40% 줄인 올리브영 문화와 정확히 겹치는 사고방식.

### 실제 경험 기반 답변 포인트

- 증상: 배포·스케일인 시 30~60초 구간에 503이 묶음으로 발생하다 자연히 사라짐. 에러 바디에 'upstream connect error ... reset reason: connection failure, transport failure reason: delayed connect error: 111'과 헤더에 'server: envoy'. 111은 ECONNREFUSED. 즉 Envoy는 살아있는데 upstream(:50051)에 TCP 연결이 거부됨.
- 구조: 클라 → Envoy(:5000) → gRPC 서버(:50051). 종료 시 preStop hook에서 curl로 Envoy drain_listeners 호출 후 sleep 20. 문제는 preStop 완료 후 SIGTERM이 오자마자 gRPC 서버가 즉시 죽어 50051이 닫힘. Envoy는 아직 살아있어 들어온 요청을 upstream으로 보내려다 ECONNREFUSED를 맞음.
- 원인1: gRPC 서버 파이썬 코드 `server.wait_for_termination()`만 있고 SIGTERM 핸들러 부재. 원인2: supervisord [program:grpc-server]에 stopwaitsecs 미설정 → 기본 10초 → 핸들러를 추가해도 supervisord가 먼저 SIGKILL 날릴 가능성.
- NHN Cloud Container Service는 API 스펙에 terminationGracePeriodSeconds 필드 자체가 없어 30초 고정 불가변. 따라서 preStop + SIGTERM 후 drain + 컨테이너 종료가 전부 30초 안에 끝나야 함. 예산 재배분: preStop sleep 15s + server.stop(grace=12s) + 여유 3s = 30s.
- 수정 3곳: (a) 파이썬 server_grpc_general_OCR.py에 signal.signal(SIGTERM, handle_sigterm) 등록하고 server.stop(grace=12)로 in-flight 대기, (b) supervisord.conf [program:grpc-server]에 stopwaitsecs=17(=grace 12 + 여유 5), stopsignal=TERM 명시, (c) Jenkinsfile_deploy_real의 preStop sleep을 20 → 15로 단축. 결과 시퀀스는 T+0 drain_listeners → T+15 SIGTERM → T+15~27 in-flight 처리·신규 거부 → T+27 정상 종료.
- 핵심 설계 원리: Envoy drain 시간과 gRPC in-flight 처리 시간 사이에 순서가 생기도록 예산을 나눔. preStop이 충분히 길면 Envoy가 먼저 신규 연결을 끊어 이후 SIGTERM 시점엔 in-flight만 남음. grace는 p99 응답시간 + 여유로 설정해 in-flight가 정상적으로 수렴.

### 1분 답변 구조

- 503 에러 바디의 error 111(ECONNREFUSED)과 'server: envoy' 헤더가 Envoy는 살아있고 upstream gRPC만 먼저 죽었다는 신호였습니다. 종료 시퀀스를 추적해보니 preStop이 drain 후 sleep 20을 돌리는데, 이후 SIGTERM을 받자 gRPC 서버가 SIGTERM 핸들러가 없어 즉시 죽고, sleep 구간 동안 Envoy가 요청을 포트 50051로 계속 라우팅한 게 원인이었습니다.
- supervisord stopwaitsecs가 기본 10초라 핸들러를 추가해도 SIGKILL이 먼저 날아올 수 있는 2차 문제도 있었습니다.
- 플랫폼 grace가 30초로 고정되어 있어 예산을 preStop sleep 15s + server.stop(grace=12s) + 여유 3s로 재배분했습니다. Envoy가 먼저 신규 연결을 drain한 뒤 SIGTERM이 도착하고, 그 시점엔 in-flight만 남아 grace 안에 정상 수렴하도록 시간 순서를 설계한 것입니다.
- 수정은 세 곳입니다. 파이썬에 SIGTERM 핸들러와 server.stop(grace=12) 등록, supervisord에 stopwaitsecs=17, Jenkins preStop sleep을 20→15로 단축. 수정 후 503 재발이 사라졌습니다.

### 압박 질문 방어 포인트

- '왜 사이드카 readiness probe나 EndpointSlice 변경으로 풀지 않았냐'는 질문에는: readiness 해제에는 컨트롤러·kube-proxy 동기화 지연이 수 초~십 수 초 들어갑니다. 플랫폼 grace가 30초로 고정된 제약 안에서는 애플리케이션 레벨 drain(Envoy drain + SIGTERM 핸들러)이 가장 결정적이고 빠른 경로였습니다. readiness를 보조 수단으로 조합하는 것은 이후 개선 아이디어로 남겨뒀습니다.
- 'grace 12초를 어떻게 정했느냐'에는: in-flight OCR 요청의 p99 처리시간과 드레인 버퍼를 측정해 예산 30초에서 preStop drain 15초를 뺀 15초 내에 안전하게 들어가는 값으로 12초를 정했습니다. 여유 3초는 컨테이너 런타임·supervisord 자체 종료 지연을 위한 안전 마진입니다. 그래서 stopwaitsecs는 grace+5=17초로 한 단계 더 크게 잡아 SIGKILL을 방지했습니다.

### 피해야 할 약한 답변

- 'SIGTERM 핸들러를 추가했더니 해결됐다'로 끝내는 답변 — Envoy drain·supervisord stopwaitsecs·preStop sleep·플랫폼 grace 30초라는 네 가지 타이밍이 동시에 맞아야 한다는 설계 관점이 빠지면 단편적 fix로 보입니다.
- 'terminationGracePeriodSeconds를 30초 이상으로 늘렸다'고 말하는 답변 — NHN Cloud Container Service는 API 스펙상 해당 필드 자체가 없어 불가능합니다. 제약을 제약으로 받아들이지 않고 설계를 바꾸지 않는 태도는 마이너스입니다.
- '503 로그만 보고 Envoy 설정을 고쳤다'처럼 원인 후보를 좁히는 추적 로직 없이 결론만 말하는 답변.

### 꼬리 질문 5개

**F3-1.** Envoy의 drain_listeners가 내부적으로 어떤 동작을 수행하는지, 그리고 왜 preStop 안에서 curl로 직접 호출해야 하는지 설명해 주세요(Admin API 구조, drain timeout).

**F3-2.** supervisord 종료 시 SIGTERM → SIGKILL 전파 경로와 stopwaitsecs·stopsignal 설정이 하위 프로세스(gRPC 서버)에 어떻게 도달하는지 구체적으로 알려주세요.

**F3-3.** 플랫폼 grace 30초 제약이 사라진다면(또는 더 큰 값을 쓸 수 있다면) 같은 문제를 어떻게 다르게 설계하시겠어요? 올리브영처럼 피크 시즌에 스케일 이벤트가 잦은 환경에서는 어떤 보강이 필요한가요?

**F3-4.** p99 응답시간이 갑자기 늘어나 grace=12s 안에 in-flight가 수렴하지 못하는 상황이 발생하면 어떻게 대응하시겠어요? 동적 조정이 가능한가요?

**F3-5.** 이 사건 이후 팀의 배포 체크리스트·대시보드·알럿에 무엇을 추가했고, 비슷한 종료 시퀀스 문제를 예방하기 위해 어떤 일반화된 규칙을 남겼나요?

---

## 메인 질문 4. 임베딩 메타데이터 구성을 14개 remove가 나열된 Blocklist 방식에서 EmbeddingMetadataProvider 기반 Allowlist로 바꾼 리팩터링을 설명해 주세요. OCP·전략 패턴·Spring DI 관점에서 왜 그 구조가 더 나은지, 그리고 실무적으로 경계해야 할 점은 무엇이었는지 궁금합니다.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 설계 원칙(OCP)과 패턴(전략)을 실제 리팩터링으로 구현할 수 있는 수준인지, 그리고 Spring DI(List 주입, Map 빌드)를 자연스럽게 활용하는지 확인. 올리브영 커머스의 상품·전시 도메인처럼 '타입별로 조금씩 다른 규칙'이 계속 추가되는 환경에서 핵심 역량.
- 리팩터링을 '패턴을 적용했다'는 형식적 이유로 하는 게 아니라, 구체적으로 어떤 증상이 발현되었고 어떤 비용을 줄였는지를 말할 수 있는 시니어인지 검증.

### 실제 경험 기반 답변 포인트

- Before 증상: EmbeddingService.buildContent()가 Document에서 cloneMetadata 후 14개 필드를 remove, 날짜 포맷 변환 직접 수행, DocumentType별 if-else 분기. 새 DocumentType(TASK/WIKI/DRIVE/CONFLUENCE_PAGE 등)이 추가될 때마다 EmbeddingService 수정 → OCP 위반. 임베딩에 실제 무엇이 들어가는지 파악하려면 remove 목록을 역산해야 함. cloneMetadata·getMetadataValue·putMetadata 같은 보조 메서드가 이 용도로만 존재.
- After 인터페이스: EmbeddingMetadataProvider { Set<DocumentType> getSupportedDocumentTypes(); Map<String,Object> provide(Document document); }. 각 구현체가 자신이 담당할 타입을 선언하고, provide()에서 포함할 필드만 명시적으로 채움.
- 계층 설계: AbstractEmbeddingMetadataProvider(putIfNotNull·putFormattedDatetime 유틸) → AbstractCollabToolEmbeddingMetadataProvider(협업도구 공통 필드 create/modified/project/member) → Task/Wiki/DriveFile 구현체. 병렬로 AbstractConfluenceEmbeddingMetadataProvider(title/subject 폴백) → ConfluenceEmbeddingMetadataProvider. Template Method + Strategy 결합.
- Spring DI: 구현체를 @Component로 등록하면 Spring이 List<EmbeddingMetadataProvider>로 자동 주입. 설정 시점에 stream().flatMap으로 (DocumentType, Provider) 엔트리를 만들어 Map<DocumentType, EmbeddingMetadataProvider> 빌드. EmbeddingService는 documentType으로 provider를 조회해 위임만 수행.
- 결과: OCP 복구(새 타입 = @Component 구현체 추가), 가독성(구현체만 보면 포함 필드가 한눈에), 보조 메서드(cloneMetadata 등) 제거, 단위 테스트 용이(Provider 독립 테스트). Confluence 내부에서도 같은 원리로 ConfluenceDocumentMetadataProvider(Default vs NewSpace)로 스페이스별 메타데이터 포맷 차이를 흡수해 EmbeddingProcessor 코드를 건드리지 않고 갈아끼울 수 있게 함.
- 경계해야 할 점: (1) DocumentType에 매핑된 Provider가 없을 때의 기본 동작을 명시(fail-fast로 IllegalStateException 또는 noop+경고 로그 중 선택). (2) 두 Provider가 같은 타입을 지원한다고 주장하면 Map 빌드 시 충돌 — 이때 어떤 정책으로 우선순위를 둘지 명시. (3) Strategy가 너무 잘게 쪼개져 공통 필드 변경 시 여러 구현체를 동시에 수정해야 하면 Template Method 계층을 더 두껍게 가져가야 함 — Abstract 두 계층 설계가 이 균형을 맞춘 것.

### 1분 답변 구조

- Before는 EmbeddingService에서 14개 remove와 DocumentType 분기가 섞여 있어, 새 타입이 추가될 때마다 EmbeddingService를 수정해야 하는 OCP 위반이었고, 임베딩에 실제 어떤 필드가 포함되는지 알려면 remove 목록을 역산해야 했습니다.
- After는 EmbeddingMetadataProvider 인터페이스를 두고 '포함할 필드만 명시'하도록 뒤집었습니다. Abstract 계층을 두 단계(공통 유틸 → 협업도구/Confluence 공통 필드 → 구현체)로 두어 Template Method + Strategy를 결합했습니다.
- Spring이 List<Provider>로 @Component 구현체를 자동 주입하면 flatMap으로 Map<DocumentType, Provider>를 빌드하고, EmbeddingService는 위임만 합니다. 새 타입 추가 = @Component 한 클래스 추가로 끝납니다.
- 경계해야 할 점은 (1) 매핑 누락 시 정책(fail-fast vs noop 로그), (2) 두 Provider가 같은 타입을 주장할 때 충돌 탐지, (3) 공통 필드 변경이 여러 구현체에 흩어지지 않도록 Abstract 계층을 적절히 두껍게 설계하는 것이었습니다. 결과적으로 가독성·테스트 용이성·OCP를 모두 회복했습니다.

### 압박 질문 방어 포인트

- '전략 패턴이 오버엔지니어링 아니냐, switch 하나면 되지 않냐'는 질문에는: DocumentType이 이미 Task/Wiki/Drive/Confluence 4종 이상이고 각 타입마다 포함 필드·날짜 포맷·폴백 규칙이 달랐습니다. switch 안에 14개 remove와 if-else가 섞여 있으니 팀원이 '무엇이 임베딩에 들어가는지'를 5분 안에 파악하지 못했습니다. Provider 구현체는 각 30~50줄이라 오히려 인지 부하가 줄었습니다.
- 'Allowlist로 바꾸면 필드 하나 누락될 위험이 있지 않냐'는 지적에는: 맞습니다. 그 위험을 수용한 게 핵심입니다. Blocklist는 '신규 필드가 자동 포함'되는데 임베딩 품질·비용에 영향이 있어 오히려 예상치 못한 회귀가 생깁니다. Allowlist는 '신규 필드가 기본 제외'되므로 명시적 의사결정이 강제됩니다. 임베딩처럼 출력 품질이 비용과 직결되는 영역에서는 Allowlist 비대칭이 안전합니다.

### 피해야 할 약한 답변

- '전략 패턴을 적용했다'만 말하고 Before의 구체적 증상(14개 remove·보조 메서드·OCP 위반)을 수치·코드 수준으로 설명 못 하는 답변.
- Spring DI의 List 자동 주입과 Map 빌드 과정을 생략하고 '인터페이스 주입했다' 수준으로 넘어가는 답변.
- 경계 사항(매핑 누락 정책, 동일 타입 지원 충돌, Template Method와의 균형)을 언급하지 못해 '장점만 있다'고 주장하는 순진한 답변.

### 꼬리 질문 5개

**F4-1.** 두 Provider가 같은 DocumentType을 지원한다고 선언할 경우 현재 코드는 어떤 정책으로 충돌을 처리하나요? 팀에서 합의한 원칙은 무엇이었나요?

**F4-2.** DocumentType이 매핑에 없을 때(신규 타입 등록 누락) fail-fast vs noop+로그 중 어떤 정책을 기본으로 두셨나요, 그리고 그 선택의 근거는 무엇인가요?

**F4-3.** Template Method 계층(Abstract 두 단계)과 Strategy(구현체)의 경계를 어떤 기준으로 그었나요? 공통 필드 변경이 여러 구현체에 흩어지기 시작하면 계층을 어떻게 조정할 건가요?

**F4-4.** 임베딩 품질에 메타데이터 필드 선정이 실제로 어떤 영향을 주는지 측정해보셨나요? Allowlist로 바꾼 뒤 검색 품질 회귀가 없었는지 어떻게 검증했는지 궁금합니다.

**F4-5.** Confluence 스페이스별 메타데이터 포맷 차이를 ConfluenceDocumentMetadataProvider(Default vs NewSpace)로 흡수했는데, 스페이스 수가 수십 개로 늘어난다면 같은 전략을 유지할까요, 아니면 구성 주도(configuration-driven) 방식으로 바꿀까요?

---

## 메인 질문 5. 2026년 4월 6일부터 18일까지 단독으로 AI 웹툰 제작 도구 MVP를 만들어 199개 plan, 760 커밋을 처리했다고 하셨습니다. Claude Code 하네스 기반의 planner/critic/executor/docs-verifier 4인 에이전트 팀을 어떻게 조율했고, Gemini pro→flash→lite fallback과 전역 Rate Limit Tracking, Context Cache 같은 설계 선택이 왜 필요했는지 시니어 백엔드 관점에서 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI/에이전트 활용 경험이 '툴 사용자'가 아니라 '파이프라인·아키텍처 설계자' 수준인지를 검증. 올리브영이 중시하는 '새로운 기술 도입 및 검토' 역량과 맞닿는 핵심 질문.
- 외부 API 한도·비용·환각 같은 운영 리스크를 전역 상태·fallback·캐시·grounding 재주입 같은 정통 백엔드 설계 도구로 풀어낼 수 있는지, 그리고 그 결정 근거를 정량·정성적으로 말할 수 있는지 확인.

### 실제 경험 기반 답변 포인트

- 범위·규모: 웹소설 .txt → 60컷 웹툰 이미지 6단계 파이프라인(기획/캐릭터/각색/글콘티/이미지/동영상). 스택은 Next.js 16 + React 19 + Prisma 7 + Zod 4 + Tailwind v4 + @google/genai. 12일 단독, 199 plan, 760 커밋. 단독 처리 가능한 이유는 하네스 파이프라인이 생성·평가·문서 정합성을 분담했기 때문.
- 하네스 진화: vibe(단일 세션) → /planning(8단계 논의로 task 확정, Opus) → /plan-and-build(index.json + phase 파일 독립 실행, 재시작 가능) → /build-with-teams(critic + docs-verifier 검증 게이트) → /integrate-ux(디자이너 vibe 결과물을 컨벤션으로 흡수). 역할 분리가 핵심: 같은 모델도 critic 역할 시스템 프롬프트를 받으면 자기가 짠 계획을 객관적으로 뒤집을 수 있음.
- Gemini 전략(ADR-072): 초기 flash 기본 → 재생성 반복으로 총 비용 상승을 확인 → pro 기본 + 429 fallback(flash → lite)으로 뒤집음. '단가'가 아니라 '총 호출 횟수(재생성 포함)'로 비용을 봐야 한다는 원리.
- 전역 Rate Limit Tracking(ADR-069): Map<ModelName, SkipUntilEpochMs> 인메모리로 429를 맞은 모델을 일정 시간 skip 대상으로 마킹 → 다른 요청들이 같은 모델을 재차 두드리지 않음. 30초 재시도 로직은 제거(TPM이 1분 단위라 30초는 또 실패), 즉시 다음 fallback으로 전환.
- 토큰 최적화: Step1 소설 분석에서 5개 영역(프로필/구조/관계/세계관/장소)을 별도 호출 → Structured Output 하나로 통합(ADR-059) → 토큰 75% 절감, 속도 26.8s → 13.1s. 'API 경계 ≠ 논리 경계'가 핵심. Project 단위 Gemini Context Cache로 novelText를 Analysis·Content-review·Treatment·Conti·Continuation 5단계에서 공유, 5분 만료 내 호출은 입력 토큰 비용 거의 0.
- 환각 차단(ADR-132): Continuation이 tail 5컷만 보고 다음 컷을 만들어 grounding이 사라진 게 진짜 원인. 해결은 프롬프트 카피라이팅이 아니라 '호출 구조 설계'. Continuation에 Grounding/Treatment 블록 재주입, '연출 자유 · 서사 grounding'이라는 경계 명시(금지만 나열하면 클리셰로 도망감). 캐릭터 외형 고정은 텍스트 anti-drift 한계를 인정하고 기본 시트 이미지를 레퍼런스 첫 번째에 자동 prepend(ADR-133/134) — 이미지 모델에는 이미지 채널로 신호를 줘야 한다는 원리.
- 60컷 생성 패턴(ADR-073): 초기 SSE 순차 생성 → 부분 실패 상태 기계가 복잡. Promise.allSettled 클라이언트 병렬로 전환, 브라우저 호스트당 6 커넥션이 자연 throttle, AbortController로 전체 취소, 컷별 lastGenerationStatus/Error 저장. 'N개의 독립 생성'과 '1개의 긴 생성'의 설계 패턴이 다르다는 결론.
- 아키텍처 경계(ADR-068): actions(검증·repository 호출·revalidatePath) / lib/db(Prisma만) / lib/ai(Gemini만) / api(SSE·오케스트레이션)로 레이어를 분리해 AI 리팩터링이 DB를 건드릴 일이 없고 역도 동일. 타입 소스는 레이어별로 분리(ADR-131): Action=Zod, Repository=Prisma, 경계에 mapper. '단일 소스 통일'이 항상 옳은 건 아니라는 경험.

### 1분 답변 구조

- 12일 단독 풀스택이 가능했던 이유는 Claude Code 하네스가 생성(executor)·평가(critic)·문서 정합성(docs-verifier)을 분담했기 때문입니다. 저는 planning에 집중해 무엇을 할지 결정에 투자했습니다.
- Gemini 전략은 초기 flash 기본에서 pro 기본 + 429 fallback(flash→lite)으로 뒤집었습니다. 저가 모델로 재생성이 반복되면 총 비용이 더 커진다는 걸 며칠 만에 확인했기 때문입니다. 429는 전역 Map으로 skip 대상을 마킹해 다른 요청이 같은 모델을 다시 두드리지 않게 했고, 30초 재시도는 TPM이 1분 단위라 즉시 fallback으로 전환이 더 빨랐습니다.
- 토큰 절감은 두 가지입니다. Step1 분석의 5개 영역을 Structured Output 하나로 통합해 75% 절감, 속도 13초대로 단축. novelText는 Project 단위 Context Cache로 5단계 공유해 5분 만료 내 호출 비용을 거의 0으로 줄였습니다.
- 환각은 프롬프트 카피라이팅이 아니라 호출 구조의 문제였습니다. Continuation에 trailing 5컷만 있고 Grounding이 빠진 게 원인이라 Grounding을 매번 재주입하고 '연출 자유·서사 grounding' 경계를 명시했습니다. 캐릭터 외형은 텍스트로 강제하지 않고 기본 시트 이미지를 자동 prepend해 이미지 채널로 신호를 줬습니다. 60컷 생성은 SSE 대신 Promise.allSettled로 N개 독립 생성 패턴을 쓰고 브라우저 6 커넥션이 자연 throttle이 되게 설계했습니다.

### 압박 질문 방어 포인트

- '면접 지원자가 AI에 일을 맡긴 거 아니냐'는 질문에는: 하네스가 실행을 수행한 건 맞지만 '무엇을 만들지·어떤 경계로 자를지·어떤 트레이드오프를 받아들일지'는 전부 제가 결정했습니다. 134개 ADR에 그 결정이 코드보다 먼저 기록되어 있고, 잘못된 입력이 들어가면 에이전트가 잘못된 출력을 낸다는 걸 planning 단계 강화로 해결했습니다. '입력의 정확도'를 올리는 게 시니어 백엔드의 일이라고 봅니다.
- 'Pro fallback 시 환각이 약해진다는 문제는 해결했냐'는 지적에는: 아직 미해결로 남겨뒀습니다. 서비스 연속성을 우선해 Flash/Lite fallback은 유지했고, grounding 준수력 차이를 프롬프트 레벨에서 메우는 건 모델 capability 한계라 완전한 해결이 어렵다고 판단했습니다. 대신 Pro 사용률과 Flash/Lite fallback률을 대시보드로 분리해 운영자 개입 지점을 만들었습니다. 이건 실무에서 '모든 문제를 기술로 풀지 않고 운영 프로세스로 분담하는' 선택을 해본 경험입니다.

### 피해야 할 약한 답변

- 'Claude Code로 빨리 만들었다' 수준의 답변 — 숫자·ADR·설계 의도가 빠지면 '툴 사용자'로 평가됩니다.
- Gemini 전략을 단가 관점으로만 설명하고 '재생성 반복으로 총 비용 증가'라는 관점 전환을 말하지 않는 답변.
- 환각을 '프롬프트에 DO NOT 문구를 추가해 해결했다'는 식으로 표면적으로 설명하는 답변 — Continuation 호출 구조가 진짜 원인이라는 관점이 빠지면 설계자가 아닌 사용자로 보입니다.
- 전역 Rate Limit Tracking·Context Cache·Promise.allSettled 같은 정통 백엔드 설계 도구를 'AI 개발이라 특별하다'는 식으로 포장하는 답변.

### 꼬리 질문 5개

**F5-1.** critic 에이전트의 시스템 프롬프트에서 가장 중요하게 설정한 원칙 두세 가지는 무엇인가요? 자기 계획을 자기가 검증하지 못하는 구조적 이유도 함께 설명해 주세요.

**F5-2.** Gemini Context Cache는 5분 만료라는 제약이 있는데, 파이프라인의 단계별 호출 순서·병렬 여부를 이 만료 시간을 기준으로 어떻게 조정했나요? 만료 전 마지막 호출이 늦어질 경우의 예외 설계는?

**F5-3.** Pro fallback 시 환각이 약해진다고 하셨는데, 운영 중 실제로 환각이 튀어나온 경우를 어떻게 탐지하고 롤백했나요? 자동 판정기를 만들지 않은 이유도 궁금합니다.

**F5-4.** Promise.allSettled + 브라우저 6 커넥션이 자연 throttle로 작동했다고 하셨는데, 서버 측 Rate Limit Tracking과 클라이언트 측 병렬 제한이 상호작용해 발생할 수 있는 문제(예: 일시적 burst, 재시도 폭주)는 어떻게 예방했나요?

**F5-5.** 하네스 기반 스펙 기반 코딩으로 전환한 뒤 생산성·품질을 어떤 지표로 측정했나요? 그 지표를 올리브영 같은 대규모 커머스 팀에서 채택한다면 어떤 변형이 필요할까요?

---

## 최종 준비 체크리스트

- 핵심 수치 암기: 11 Step, 청크 10, preStop 15s + grace 12s + 여유 3s = 30s, supervisord stopwaitsecs=17, 5영역→75% 토큰 절감·26.8s→13.1s, 12일·199 plan·760 커밋·134 ADR, 447 테스트 파일, 게임 팀 신규 3종 에이전트 구현.
- 핵심 용어 재정의 리허설: @JobScope vs JobExecutionContext, allowStartIfComplete, CGLIB 프록시, AsyncItemProcessor/Writer·Future.get(), CompositeItemProcessor 4단계, ChangeFilter·Enrichment·BodyConvert·Embedding, Envoy drain_listeners, supervisord stopsignal/stopwaitsecs, @TransactionalEventListener(AFTER_COMMIT), Dead Letter Store, PostCommitUpdateEventListener, StampedLock tryReadLock 타임아웃 2.5s.
- 올리브영 기술 블로그 4편의 인사이트를 내 경험과 1:1 매핑: (MSA 연동 전략 ↔ RabbitMQ Fanout + PostCommit + StampedLock), (무중단 OAuth2 ↔ preStop·SIGTERM·supervisord 예산 재배분·gRPC 503 해결), (SQS 데드락 ↔ Propagation.REQUIRES_NEW로 DLStore 분리), (트랜잭션 동기화 ↔ @TransactionalEventListener AFTER_COMMIT).
- 설계 사고 프레임 한 줄 요약 준비: 'API 경계 ≠ 논리 경계', '비용은 단가가 아니라 총 호출 횟수', '환각은 프롬프트가 아니라 호출 구조', '이미지 일관성은 이미지 채널로', '단일 소스 통일이 항상 옳지 않다', 'Allowlist 비대칭으로 회귀를 막는다'.
- 약점 영역(DB) 보강 답변 준비: EXPLAIN 읽기·복합 인덱스·커버링 인덱스·InnoDB MVCC·Next-Key Lock·격리 수준 4종·N+1 해결(@EntityGraph/fetch join/BatchSize)·트랜잭션 전파·Lost Update 방어. 게임 팀 슬롯 예시로 구체화.
- 역질문 3개 준비: (1) 웰니스개발팀 내 Backend 인원 구성과 온보딩 기간, (2) Kafka·Redis·Aurora 운영에서 가장 최근에 겪은 장애·의사결정, (3) 팀의 ADR·설계 문서 문화와 코드 리뷰 관행. Live Coding / Whiteboard 전형에서 말로 설계를 풀어내는 리허설을 최소 3회 진행.
