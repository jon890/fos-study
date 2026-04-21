# [초안] AI 서비스 개발팀 경험 기반 질문 은행 (CJ 올리브영 커머스플랫폼유닛 Back-End)

---

## 이 트랙의 경험 요약

- AI 서비스팀 4개 대표 경험(Spring Batch RAG 파이프라인, gRPC OCR 503 Graceful Shutdown, EmbeddingMetadataProvider Allowlist 전환, 12일 단독 AI 웹툰 MVP)을 시니어 Java 백엔드 관점으로 구조화합니다.
- 대용량 I/O 바운드 병렬화, 쿠버네티스 종료 예산 설계, OCP 기반 도메인 리팩터링, Claude Code 하네스 기반 4인 에이전트 팀 오케스트레이션을 모두 포함합니다.
- 각 경험을 올리브영 커머스 도메인(상품/전시/검색/주문, 1,600만 고객, 올영세일 10배 피크)으로 이식 가능함을 bridge 문장으로 연결합니다.
- AI 협업을 '툴 사용자'가 아니라 '파이프라인·아키텍처 설계자' 수준으로 드러내는 증거(199 plan, 760 커밋, ADR 134개, 스킬화된 4개 워크플로우)를 질문과 답변에 배치합니다.

## 1분 자기소개 준비

- NHN에서 4년째 Spring Boot 기반 MSA 백엔드를 담당해왔고, 게임 소셜 카지노 슬롯과 AI 서비스 RAG 파이프라인 양쪽에서 설계·구현·운영까지 전 과정을 경험했습니다.
- 게임 팀에서는 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout Exchange + StampedLock + PostCommitUpdateEventListener로 해결했고, Kafka AFTER_COMMIT + Dead Letter Store 재시도 구조로 비동기 흐름의 신뢰성을 구조적으로 확보했습니다.
- AI 서비스 팀에서는 Confluence → OpenSearch 벡터 색인을 11 Step Spring Batch + AsyncItemProcessor로 설계했고, 임베딩 메타데이터 구성을 전략 패턴으로 Allowlist 방식으로 전환해 OCP를 준수하는 구조로 정리했습니다.
- 최근에는 12일 단독으로 Next.js 16 + Prisma 7 + Gemini 기반 AI 웹툰 MVP 풀스택을 Claude Code 하네스 4인 에이전트 팀 구조로 완주하며 199 plan / 760 커밋을 처리해 AI 협업을 '파이프라인 설계자' 수준으로 경험했습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 캐싱 전략을 단순 Redis 사용을 넘어 다중 서버 정합성·갱신 중 동시성·확장 구조 설계까지 고민해본 경험이 올리브영의 Cache-Aside + Kafka 하이브리드 연동에 바로 맞닿습니다.
- Kafka AFTER_COMMIT + Dead Letter Store + traceId 기반 실패 추적 설계는 올리브영 도메인 간 이벤트 연동 구조에 그대로 이식 가능합니다.
- OpenSearch 대용량 색인·증분 처리·삭제 동기화 운영 경험은 상품 검색·전시 도메인의 색인 파이프라인 설계와 동일 패턴입니다.
- gRPC OCR 503을 Envoy/supervisord/SIGTERM/NCS 30s 예산으로 재설계한 경험이 올영세일 10배 피크 트래픽의 무중단 배포·장애 격리 요구와 결이 같습니다.
- Cursor Rules 20개 구축 및 Claude Code 하네스 4인 에이전트 팀 설계 경험을 팀 생산성 레버로 전파할 수 있어 기능 구현뿐 아니라 팀 역량 강화에 기여 가능합니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 사내 서비스에서 다룬 캐싱·이벤트·대용량 색인 기술이 1,600만 고객 규모 커머스 트래픽에서 어떻게 동작하는지 직접 검증하고 싶어 지원했습니다.
- 게임/AI 도메인에서 쌓은 설계 경험을 더 큰 트래픽과 더 복잡한 비즈니스(상품/전시/주문) 도메인에서 증명하고 확장하고 싶습니다.
- 장기적으로 대규모 커머스 아키텍처에서 시니어 기여자로 성장하는 커리어 방향과 직무가 정합합니다.

### 왜 올리브영인가
- 기술 블로그의 Cache-Aside + Kafka 하이브리드 연동, Feature Flag + Shadow Mode 무중단 OAuth2 전환 같은 주제가 제가 실무에서 고민해온 설계 영역과 1:1로 겹칩니다.
- 1,600만 고객과 올영세일 평상시 대비 10배 트래픽 피크는 국내에서 실제로 대규모 트래픽 설계를 검증해볼 수 있는 몇 안 되는 환경입니다.
- 기술 블로그의 구조·완성도 자체가 '기술 결정을 문서화하고 공유하는 문화'를 증명해, docs-first를 습관으로 유지해온 제 작업 방식과 잘 맞을 것으로 판단했습니다.

### 왜 이 역할에 맞는가
- 담당 업무(상품/전시/검색/MSA/ORM/도메인 모델링)가 제 강점(JPA Hibernate 이벤트 리스너, 대용량 OpenSearch 색인, 이벤트 드리븐 신뢰성 설계)과 직접 매핑됩니다.
- 캐싱·이벤트·검색·MSA 설계·운영 경험이 온보딩 기간을 단축시키고 조기에 기여할 수 있는 조건이라고 판단합니다.
- AI 협업 역량(Cursor Rules·하네스 설계)을 팀 생산성 레버로 전파할 수 있는 포지션에서 일하고 싶습니다.

## 메인 질문 1. RAG 벡터 색인 파이프라인을 왜 11개 Step으로 분리했고, AsyncItemProcessor를 선택한 기준은 무엇이었는지, 어떤 대안을 어떻게 비교해 결정했는지 설명해주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- Spring Batch의 Step/Chunk/Scope 개념을 실제로 이해하고 있는지 확인
- I/O 바운드 작업에서 비동기·병렬 설계를 측정 기반으로 선택했는지 검증
- 재시작성·실패 격리 같은 운영 관점을 설계 단계에서 고려했는지 확인

### 실제 경험 기반 답변 포인트

- 11 Step 분리의 근거: 수집·변환·임베딩·색인·삭제 동기화가 I/O 특성·실패 비용·재시도 단위가 모두 달라 Step 단위 책임 분리와 allowStartIfComplete 전략으로 재시작 지점을 정교하게 제어했습니다.
- AsyncItemProcessor 선택 근거: 임베딩 API는 페이지당 수백 ms 네트워크 대기로 명확한 I/O 바운드였고, 동기 처리 시 청크 10개에 수 초가 고정 낭비되어 parallelChunkExecutor 스레드풀 기반 병렬화로 처리 시간을 수 분에서 수십 초대로 낮췄습니다.
- CompositeItemProcessor 체이닝: ChangeFilter → Enrichment → BodyConvert(ADF→Markdown) → Embedding 4단계를 단일 책임으로 쪼개 테스트·교체 비용을 낮추고 Processor 단계별로 스킵/보강/변환 책임을 분리했습니다.
- @JobScope 인메모리 홀더(ConfluenceJobDataHolder)로 Step 간 도메인 데이터를 공유하고, JobExecutionContext는 재시작 커서 같은 경량 상태 전용으로 한정해 BATCH_JOB_EXECUTION_CONTEXT 테이블의 불필요한 직렬화 부하를 제거했습니다.
- 대안 검토: 단일 거대 Step은 실패 격리 상실, Processor 내부 WebClient 비동기는 청크·트랜잭션 경계와 어긋나 재시작 모델 수동 구현 부담, Kafka 기반 파이프라인은 운영 복잡도가 MVP 단계에 과했습니다.

### 1분 답변 구조

- 수집/변환/임베딩/색인/삭제 동기화가 서로 실패 비용과 재시도 단위가 달라 11개 Step으로 분리해 Step 단위 실패 격리와 재시작성을 확보했습니다.
- 임베딩 API가 명확한 I/O 바운드였기 때문에 AsyncItemProcessor + AsyncItemWriter 조합으로 청크 내부를 스레드풀 병렬화해 청크 처리 시간을 수 분에서 수십 초 단위로 줄였습니다.
- 변환 로직은 CompositeItemProcessor로 ChangeFilter → Enrichment → BodyConvert → Embedding 4단계로 체이닝해 단일 책임을 유지했고, Step 간 도메인 데이터는 @JobScope 홀더로, 재시작 커서는 JobExecutionContext로 역할을 분리했습니다.

### 압박 질문 방어 포인트

- '단일 Step으로 만들면 더 단순하지 않나'라는 질문에는 실패 시 전체 재실행 비용과 Step별 allowStartIfComplete 같은 정교한 재시작 제어 불가로 답합니다.
- 'AsyncItemProcessor 대신 Processor 내부 비동기로 충분하지 않나'라는 지적에는 청크·트랜잭션 경계와 어긋나 Spring Batch의 재시작·실패 처리 모델을 수동 구현해야 한다는 점을 근거로 제시합니다.
- '스레드풀 병렬화가 임베딩 서비스에 과부하를 주지 않나'라는 우려에는 스레드풀 크기와 청크 크기를 묶어 동시성 상한을 제어하고 임베딩 서비스 TPS에 맞춰 튜닝했음을 설명합니다.

### 피해야 할 약한 답변

- 'Spring Batch가 공식적으로 권장해서 그대로 썼다'처럼 설계 근거 없는 채택 이유는 시니어 수준 답변이 아닙니다.
- '비동기가 빨라서 도입했다'처럼 bottleneck 분석 없이 성능만 강조하면 I/O 바운드 여부를 이해하지 못한 것으로 보입니다.
- 실패 격리·재시작성 같은 운영 관점을 전혀 언급하지 않고 성능 수치만 강조하는 답변은 운영 감각 부재로 읽힙니다.

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor 도입 이후 스레드풀 크기·청크 크기·임베딩 서비스 TPS를 어떻게 상호 튜닝하셨나요?

**F1-2.** @JobScope 빈을 재시작 시 allowStartIfComplete(true)로 강제 재실행한 이유와 그때 데이터 정합성은 어떻게 보장했나요?

**F1-3.** ChangeFilter 단계의 version 기반 스킵과 반복 실패 문서 임계치 스킵 정책 사이에는 어떤 트레이드오프가 있나요?

**F1-4.** 만약 임베딩 API가 TPS 제한을 더 엄격하게 건다면 현재 11 Step 구조 중 어디를 가장 먼저 손보시겠습니까?

**F1-5.** @StepScope 빈 중복 등록으로 NoUniqueBeanDefinitionException이 발생한 사례를 어떻게 진단했고 어떤 설계 원칙으로 재정리하셨나요?

---

## 메인 질문 2. NCS가 terminationGracePeriodSeconds를 30초로 고정한 상태에서 gRPC OCR 서버 배포·스케일인 시 503이 발생한 문제를 어떻게 분석하고 preStop/gRPC grace/supervisord 예산을 재설계했는지 설명해주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 로그·에러 코드에서 원인을 단계적으로 좁혀가는 디버깅 역량 확인
- 쿠버네티스 종료 시퀀스와 외부 인프라(Envoy, supervisord) 상호작용 이해도 검증
- 변경 불가능한 제약 하에서 예산 설계로 안정성을 확보하는 시니어 판단 확인

### 실제 경험 기반 답변 포인트

- 로그 패턴 분석: `upstream connect error ... error 111 (ECONNREFUSED)`와 `server: envoy` 헤더에서 'Envoy는 살아있고 upstream(포트 50051)이 빠르게 닫히는' 시나리오로 범위를 축소했습니다.
- 실제 종료 시퀀스 재구성: preStop(Envoy drain + sleep 20) → SIGTERM → gRPC 서버 즉시 종료 → Envoy가 20초간 upstream으로 라우팅 → ECONNREFUSED 발생이라는 흐름을 복원했습니다.
- 원인 분해: (1) gRPC 서버에 SIGTERM 핸들러 부재로 즉시 종료, (2) supervisord stopwaitsecs 기본 10초가 핸들러가 있어도 SIGKILL을 강제, (3) NCS가 terminationGracePeriodSeconds를 30초로 고정해 전체 예산 상한이 묶여 있었습니다.
- 예산 재설계: preStop sleep 15s + gRPC server.stop(grace=12) + supervisord stopwaitsecs=17(grace 12 + 여유 5) 조합으로 27초 수렴, NCS 30초 한도 안에서 drain → 신규 요청 차단 → in-flight RPC 마감 순서를 보장했습니다.
- 검증: 수정 후 타임라인을 T+0→T+15(drain 완료)→T+27(gRPC 정상 종료)로 재작성하고 클러스터 단위 503 재발 여부를 모니터링해 해결을 확인했습니다.

### 1분 답변 구조

- Envoy 헤더와 error 111에서 'Envoy는 살아있지만 upstream이 빨리 죽는 구조'로 범위를 좁힌 뒤, Envoy drain sleep 20s 동안 gRPC 서버가 이미 종료되는 시퀀스를 복원했습니다.
- 원인은 SIGTERM 핸들러 부재, supervisord stopwaitsecs 기본 10초, 그리고 NCS가 변경 불가능한 terminationGracePeriodSeconds 30초 제약이 겹쳐 생긴 구조적 문제였습니다.
- 30초 예산을 preStop sleep 15s + gRPC grace 12s + supervisord stopwaitsecs 17s로 재배분해 Envoy drain이 끝난 뒤에만 gRPC가 graceful하게 in-flight RPC를 마감하도록 시퀀스를 맞췄고, 수정 후 503 로그가 사라졌습니다.

### 압박 질문 방어 포인트

- 'terminationGracePeriodSeconds를 늘리면 되지 않나'라는 질문에는 NCS API 스펙상 해당 필드가 노출되지 않아 인프라 제약이 협상 대상이 아니라 설계 입력이라는 점을 설명합니다.
- 'preStop sleep을 줄이면 Envoy drain이 부족하지 않나'라는 우려에는 drain_listeners 호출로 Envoy가 즉시 신규 트래픽을 차단하므로 15초면 안전 마진이 충분함을 근거로 답합니다.
- '왜 preStop을 더 짧게 잡지 않았나'에는 장시간 in-flight RPC 고려와 30초 전체 예산에서 grace/stopwaitsecs 여유를 빼고 남은 값을 역산한 결과라고 설명합니다.

### 피해야 할 약한 답변

- '대충 sleep 값을 키웠다'처럼 원인 분해 없이 숫자만 튜닝했다는 답변은 근본 원인을 모르는 것으로 보입니다.
- Envoy만 탓하고 SIGTERM 핸들러 부재·supervisord stopwaitsecs 기본값 같은 애플리케이션 레이어 원인을 놓치는 답변은 풀스택 디버깅 역량 부족으로 읽힙니다.

### 꼬리 질문 5개

**F2-1.** grace=12초가 부족해 in-flight RPC가 마감되지 않는 상황을 어떻게 감지하고 후속 대응하시겠습니까?

**F2-2.** supervisord stopsignal을 TERM 대신 QUIT이나 INT로 바꿨을 때의 실효 차이를 설명해주세요.

**F2-3.** Envoy drain_listeners 호출이 실패하거나 지연될 때 preStop 스크립트를 어떻게 방어적으로 설계해야 하나요?

**F2-4.** 동일한 종료 예산 설계를 Spring Boot HTTP 서버로 옮긴다면 어떤 속성(server.shutdown, lifecycle.timeout-per-shutdown-phase 등)이 grace와 stopwaitsecs에 대응되나요?

**F2-5.** 503 재발 여부를 CI/CD나 카나리 배포 단계에서 자동으로 감지할 SLI/SLO는 무엇으로 잡으시겠습니까?

---

## 메인 질문 3. RAG 임베딩 메타데이터 구성을 Blocklist에서 Allowlist(EmbeddingMetadataProvider)로 전환하면서 전략 패턴을 도입했는데, 어떤 경계로 인터페이스를 설계했고 왜 그 계층 구조를 택했는지 설명해주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 리팩터링 동기를 OCP·SRP 같은 구조적 용어로 설명할 수 있는지 확인
- 전략 패턴의 추상화 수준을 실제 도메인 요구에 맞게 설계할 수 있는지 검증
- Spring DI를 활용해 확장 가능한 구조를 만드는 실전 감각 확인

### 실제 경험 기반 답변 포인트

- Blocklist의 한계: 새 DocumentType이 추가될 때마다 EmbeddingService에 remove 분기가 누적되고, '실제 어떤 필드가 임베딩에 포함되는가'를 역산해야 하는 가독성 문제, 그리고 Document.cloneMetadata/getMetadataValue/putMetadata 같은 이 패턴 전용 유틸이 유지보수 부담으로 남았습니다.
- 핵심 전환: '제거할 필드'가 아니라 '포함할 필드'를 명시하는 EmbeddingMetadataProvider 인터페이스(getSupportedDocumentTypes + provide(Document))로 의미를 뒤집었습니다.
- 계층 설계: AbstractEmbeddingMetadataProvider(putIfNotNull·putFormattedDatetime 공통 유틸) → 소스 시스템별 추상(AbstractCollabToolEmbeddingMetadataProvider, AbstractConfluenceEmbeddingMetadataProvider) → 구현체(Task/Wiki/Drive/Confluence)로 2단 추상을 유지해 오버엔지니어링을 피했습니다.
- Spring DI: List<EmbeddingMetadataProvider>를 주입받아 flatMap으로 DocumentType → Provider 맵을 빌드해 EmbeddingService는 위임만 담당하도록 단순화했고, 새 DocumentType은 @Component 구현체만 추가하면 OCP를 준수합니다.
- 효과: EmbeddingService의 14개 remove 블록과 if-else 분기 제거, 필드 가시성 확보, 구현체별 독립 단위 테스트 가능, 스페이스별 Confluence 메타데이터(title/subject 폴백) 같은 예외도 계층 내부에서 흡수했습니다.

### 1분 답변 구조

- Blocklist 방식은 DocumentType이 늘 때마다 EmbeddingService에 remove 분기가 쌓였고, 임베딩에 실제 어떤 필드가 포함되는지를 역산해야 했습니다.
- EmbeddingMetadataProvider 인터페이스에 getSupportedDocumentTypes와 provide만 두고, Spring이 모든 @Component 구현체를 List로 주입해 DocumentType → Provider 맵을 빌드하게 바꿔 EmbeddingService는 위임만 남겼습니다.
- 공통 유틸(AbstractEmbeddingMetadataProvider)과 소스별 공통 필드(CollabTool/Confluence)를 2단 추상으로 두어 구현체 중복을 줄이면서도 추상 계층이 과하지 않게 유지했고, 새 DocumentType은 구현체 하나만 추가하면 되는 OCP 구조로 정리됐습니다.

### 압박 질문 방어 포인트

- '단순 if-else가 더 빠르지 않나'라는 지적에는 DocumentType이 3개일 때는 맞지만 Task/Wiki/Drive/Confluence + 스페이스별 분기까지 고려하면 유지보수 비용이 훨씬 크다고 근거를 제시합니다.
- '추상화가 과한 건 아닌가'라는 우려에는 인터페이스 메서드 2개, 계층 2단계로 최소한의 추상만 유지했음을 설명합니다.
- '구현체가 자기 DocumentType을 선언하는 방식이 위험하지 않나'에는 빌드 시 동일 DocumentType 중복을 차단하는 맵 빌드 단계의 실패-빠르게 전략과 단위 테스트로 방어함을 설명합니다.

### 피해야 할 약한 답변

- '코드가 더러워서 리팩터링했다'처럼 OCP·SRP 같은 구조적 근거가 빠진 답변은 리팩터링 의도 없이 취향으로만 움직인 것으로 보입니다.
- 전략 패턴을 단지 'if-else 제거'로만 설명하고 공통 추상 계층의 역할이나 Spring DI 자동 등록의 효과를 언급하지 않으면 설계 깊이가 얕다고 읽힙니다.

### 꼬리 질문 5개

**F3-1.** AbstractCollabToolEmbeddingMetadataProvider와 AbstractConfluenceEmbeddingMetadataProvider를 별도 추상 계층으로 둔 기준은 무엇이었나요?

**F3-2.** Confluence title/subject 폴백 같은 '스페이스별 예외'가 또 생긴다면 계층을 더 쪼개시겠습니까, 구현체 내부 분기로 두시겠습니까?

**F3-3.** 구현체가 자기 자신이 담당할 DocumentType을 선언하는 방식의 위험(중복·미등록)을 어떻게 방어하셨나요?

**F3-4.** 같은 전환을 커머스 상품 전시의 '표시 필드 allowlist'에 적용한다면 구현 포인트가 어떻게 달라질 수 있을까요?

**F3-5.** provide()가 Map<String, Object>를 반환하는데 타입 안전성 관점에서 개선할 여지가 있다면 어떤 방향이 될까요?

---

## 메인 질문 4. 12일 단독으로 AI 웹툰 MVP 풀스택을 끝냈는데 199 plan / 760 커밋이라는 볼륨을 어떻게 만들어냈고, 스스로를 '툴 사용자'가 아니라 '파이프라인 설계자'라고 말할 수 있는 근거는 무엇인가요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI 도구 사용 수준이 '툴 소비자'를 넘어 '설계자'임을 구체적 증거로 보일 수 있는지 확인
- 속도와 품질의 동시 달성을 어떤 구조로 가능하게 했는지 검증
- 이 방법론을 커머스팀 온보딩·리팩터링에 이식할 수 있는지 판단

### 실제 경험 기반 답변 포인트

- 입력 정확도 업그레이드: /planning(Opus 기반 8단계 논의)으로 기술 가능성·사용자 흐름·데이터 모델·API 설계·엣지 케이스를 task 파일로 확정해 에이전트 입력의 80%를 설계 단계에서 고정했습니다.
- 재시작 가능 실행: /plan-and-build로 tasks/planNNN-*/index.json + phase 파일 단위 자기완결 실행 구조를 만들어 세션 끊김·실패와 무관하게 pending phase부터 이어받게 했습니다.
- 역할 분리 검증 게이트: /build-with-teams로 planner/critic/executor/docs-verifier 4인 에이전트 팀을 도입해 critic이 계획과 실제 코드를 대조하고 docs-verifier가 ADR/data-schema 드리프트를 차단하게 했습니다.
- 협업 흡수 자동화: /integrate-ux 스킬로 UX 디자이너의 vibe PR을 Container/Presenter + semantic 토큰 + 공통 컴포넌트로 변환하는 반복 가능한 변환 파이프라인을 만들어 협업 마찰을 제거했습니다.
- docs-first 원칙: ADR 134개를 docs-verifier로 관리하고 1,581줄까지 비대해진 ADR을 컨텍스트 효율을 위해 700줄로 축약하는 등 '문서가 에이전트 컨텍스트'라는 관점을 끝까지 유지했습니다.

### 1분 답변 구조

- 12일에 199 plan을 처리한 건 vibe 코딩을 '입력 정확도 설계(/planning), 재시작 가능 실행(/plan-and-build), 역할 분리 검증(/build-with-teams), 협업 흡수(/integrate-ux)' 4단계 하네스로 공정화했기 때문입니다.
- planner가 Opus로 설계 정확도를 올리고, critic이 코드와 계획을 대조해 REVISE를 돌리고, executor가 구현하며, docs-verifier가 ADR/데이터 스키마 드리프트를 잡는 역할 분리를 제가 직접 설계했습니다.
- 스킬화 이후 같은 종류 작업은 한 줄 명령으로 끝나 plan 처리량이 선형이 아니라 워크플로우 단위로 누적됐고, 이것이 'AI가 다 한 것'이 아니라 '파이프라인을 제가 설계했다'는 핵심 근거입니다.

### 압박 질문 방어 포인트

- 'AI가 다 한 것 아니냐'라는 도전에는 task 파일·ADR·스킬·에이전트 역할 프롬프트 모두 제가 설계한 산출물이고 에이전트는 구현 실행자 역할임을 분리해 설명합니다.
- '커밋 수는 품질 지표가 아니다'라는 지적에는 동의하며, plan 단위 검증 게이트(critic + docs-verifier)로 품질이 관리된 커밋임을 ADR·테스트 구조로 증명 가능함을 근거로 제시합니다.
- '혼자 쓰는 MVP라 가능한 것 아니냐'에는 파일 소유권 매트릭스와 /integrate-ux 스킬화가 실제로 디자이너 합류 후 git conflict를 거의 0으로 만든 협업 사례임을 들어 확장 가능성을 보입니다.

### 피해야 할 약한 답변

- 'Claude가 알아서 해준다'처럼 설계 기여를 구체적으로 기술하지 못하면 '툴 사용자'에 머문다는 인상을 줍니다.
- 스킬화·검증 게이트 구조 없이 커밋 수와 plan 수만 강조하면 볼륨이 품질로 이어진 근거가 약해 보입니다.

### 꼬리 질문 5개

**F4-1.** planner/critic/executor/docs-verifier의 시스템 프롬프트 경계를 어떻게 설계해 '자기 계획 자기 검증' 문제를 피하셨나요?

**F4-2.** plan 실행 중 critic이 REVISE를 반복해 진행이 막혔을 때 어떤 기준으로 사람이 개입 결정을 했나요?

**F4-3.** ADR이 1,581줄까지 비대해진 후 700줄로 축약한 과정에서 컨텍스트 효율과 정보 손실 트레이드오프를 어떻게 판단하셨나요?

**F4-4.** /integrate-ux 스킬이 디자이너 PR을 변환하는 규칙 중 자동화하지 않고 수동으로 남긴 부분은 무엇이고 그 이유는 무엇인가요?

**F4-5.** 이 하네스 방법론을 커머스팀 온보딩이나 레거시 리팩터링에 적용한다면 가장 먼저 공정화할 워크플로우는 무엇으로 고르시겠습니까?

---

## 메인 질문 5. AI 웹툰 MVP에서 Gemini pro→flash→lite fallback, 전역 Rate Limit Tracking, Project 단위 Context Cache를 도입했는데 이 세 가지가 어떻게 맞물려 총 비용과 환각을 동시에 낮췄는지 설명하고, 커머스 도메인 이식 가능성도 언급해주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 비용 최적화를 단가가 아닌 '재생성 포함 총 호출 비용' 관점으로 사고하는지 확인
- 전역 상태·캐싱·폴백 정책을 하나의 시스템으로 통합 설계할 수 있는지 검증
- 이 설계를 커머스(상품 요약·리뷰 요약·검색 보강) 도메인에 이식할 일반화 역량 확인

### 실제 경험 기반 답변 포인트

- Fallback 뒤집기(ADR-072): 처음엔 비용이 싼 flash를 기본으로 썼으나 결과 불만족 → 재생성이 누적돼 싼 모델이 결과적으로 더 비싸다는 측정에 근거해 pro → flash → lite 순으로 전략을 뒤집었습니다.
- 전역 Rate Limit Tracking(ADR-069): 어떤 모델이 429를 받으면 Map<모델, skip-until>로 해당 모델을 일정 시간 회피하도록 전역 상태를 공유해 분산된 재시도가 같은 모델을 재차 두드리는 파상공격을 방지했습니다.
- 30초 재시도 제거: TPM이 1분 단위로 풀리는 특성상 30초 대기는 실패 확률이 높아 대기 대신 즉시 다음 fallback 모델로 넘기는 구조로 바꿨습니다.
- Project 단위 Context Cache(ADR-132): 63만자 원작 소설을 Analysis/Content-review/Treatment/Conti/Continuation 5단계가 공유하도록 cachedContent로 묶어 입력 토큰 비용을 근접 0으로 떨어뜨리고 TPM 한도 압박을 해소했습니다.
- 통합 분석(ADR-059): Step1 소설 분석의 5개 영역을 1회 Structured Output 호출로 합치고 Zod 스키마 필드로 관심사를 분리해 토큰 75% 절감, 속도 26.8s → 13.1s를 동시에 달성했습니다.
- 커머스 이식: 동일 패턴이 상품 상세 LLM 요약, 리뷰 요약, 검색 보강 같은 시나리오에 그대로 이식 가능하며, 특히 원본 상품·리뷰 데이터를 Context Cache로 묶고 fallback + rate limit tracking을 결합하면 peak 시 안정성과 비용을 동시에 잡을 수 있습니다.

### 1분 답변 구조

- flash를 기본으로 쓰다가 퀄리티 불만족 → 재생성 누적으로 싼 모델이 결과적으로 더 비싸다는 걸 측정으로 확인하고 pro → flash → lite 순으로 fallback을 뒤집었습니다.
- 분산된 호출이 같은 모델에 재차 부딪히지 않도록 전역 Map으로 skip-until 상태를 공유했고, TPM 윈도우와 어긋나는 30초 대기 대신 즉시 다음 fallback으로 넘어가도록 했습니다.
- 63만자 원작은 Project 단위 Context Cache로 5단계가 공유하게 묶고 통합 분석으로 5개 관심사를 한 번의 Structured Output 호출로 합쳐 토큰 75%를 절감했으며, 동일 패턴은 커머스 상품 요약·리뷰 요약에 그대로 이식 가능합니다.

### 압박 질문 방어 포인트

- 'pro가 비싸면 비용이 더 나오지 않나'라는 지적에는 단가가 아니라 재생성 포함 총 호출 비용으로 봐야 한다고 답하고 실측 데이터로 전략을 뒤집은 근거를 제시합니다.
- '전역 상태는 멀티 인스턴스 환경에서 위험하다'라는 우려에는 현재 단일 인스턴스 전제이며 확장 시 Redis 등 공유 스토리지로 이관 가능한 설계임을 설명합니다.
- 'fallback 시 환각 준수력이 약해진다'라는 미해결 과제에는 서비스 연속성을 우선한 현재 선택임을 인정하고, 개선 방향(grounding 블록 강화·continuation 재주입 정책 모델별 분기)을 함께 제시합니다.

### 피해야 할 약한 답변

- '싼 모델을 우선 쓰면 비용이 절감된다'처럼 재생성 비용을 놓치는 답변은 AI 비용 설계 감각 부재로 읽힙니다.
- Context Cache를 단지 '속도 최적화'로만 설명하고 TPM 한도·환각 차단(Continuation grounding 재주입)과의 연결을 보지 못하는 답변은 시스템 시야가 좁다고 보입니다.

### 꼬리 질문 5개

**F5-1.** 단일 인스턴스 전제의 Map<string, number> 전역 상태를 멀티 인스턴스로 확장하면 어떤 동기화 설계(Redis/pub-sub/TTL)가 필요할까요?

**F5-2.** Project 단위 Context Cache의 5분 만료 내에 파이프라인 5단계가 끝나지 않는 케이스는 어떻게 방어했나요?

**F5-3.** pro fallback 시 환각 준수력이 약해지는 미해결 과제를 해결하려면 어떤 구조적 접근을 시도해보고 싶나요?

**F5-4.** 커머스 상품 상세 LLM 요약에 이 설계를 그대로 이식할 때 비용·지연·정확도 트레이드오프는 어떻게 잡으시겠습니까?

**F5-5.** Structured Output 통합 분석이 항상 최적인가요? 오히려 분리가 유리한 상황이 있다면 어떤 경우일까요?

---

## 최종 준비 체크리스트

- 네 가지 대표 경험(Spring Batch 11 Step RAG, gRPC 503 Graceful Shutdown, Allowlist 리팩터링, AI 웹툰 MVP)을 각각 60초 버전과 3-5분 풀 버전으로 말할 수 있을 때까지 리허설한다.
- 각 경험 끝에 올리브영 도메인(상품/전시/검색/주문, 1,600만 고객, 올영세일 10배 피크)으로 연결하는 1-2줄 bridge 문장을 미리 준비해 '이식성'을 반드시 명시한다.
- 전략 패턴·OCP·전역 상태·재시작성 같은 구조적 용어를 '실제 문제 → 해결 → 효과 → 남은 한계'로 역추적 가능하게 정리하고, 시니어 압박 질문에도 근거 기반으로 답할 수 있게 한다.
- Gemini fallback·Rate Limit Tracking·Context Cache를 이야기할 때는 '단가가 아니라 재생성 포함 총 호출 비용'이라는 관점을 반드시 먼저 꺼내 AI 비용 설계 감각을 드러낸다.
- Claude Code 하네스 4인 에이전트 팀(planner/critic/executor/docs-verifier)과 스킬화된 4개 워크플로우(/planning, /plan-and-build, /build-with-teams, /integrate-ux)의 역할과 설계 의도를 1분 이내로 설명 가능한 상태로 유지한다.
- 'AI가 다 한 것 아니냐'는 압박에 대비해 task 파일·ADR 134개·스킬 프롬프트 같은 '내가 설계한 산출물' 리스트를 사전에 확보해 즉시 인용할 수 있게 한다.
