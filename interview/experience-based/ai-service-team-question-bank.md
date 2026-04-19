# [초안] CJ 올리브영 커머스플랫폼 Back-End 면접 Q&A — NHN AI 서비스팀 경험 기반 (Spring Batch RAG / gRPC Graceful Shutdown / 임베딩 메타데이터 전략 / AI 웹툰 MVP)

---

## 이 트랙의 경험 요약

- Java 백엔드 시니어 포지션(5년 이상) 관점에서 NHN AI 서비스팀 4건의 대표 경험을 심층 질문으로 구조화했다.
- Spring Batch 11-Step RAG 파이프라인, gRPC OCR Graceful Shutdown 503 해결, 임베딩 메타데이터 전략 패턴 전환, 12일 단독 풀스택 AI 웹툰 MVP를 축으로 구성했다.
- AI/에이전트 협업 경험은 '툴 사용자'가 아니라 '파이프라인·아키텍처 설계자' 수준으로 드러나도록 기술 의사결정 근거·트레이드오프·운영 지표를 전면에 배치했다.
- 올리브영 기술 블로그(MSA 데이터 연동, Cache-Aside+Kafka, 무중단 OAuth2 전환)와 후보자 경험(PostCommitUpdateEventListener+Fanout, AFTER_COMMIT+DLS+재시도, OpenSearch 벡터 색인)의 접점을 질문마다 명시적으로 연결했다.
- 각 질문은 인터뷰어 의도 / 답변 포인트 / 1분 답변 뼈대 / 압박 질문 방어 / 피해야 할 약한 답변 / 후속 꼬리질문 5개 구조로 통일해 실전 리허설이 가능하도록 설계했다.

## 1분 자기소개 준비

- 안녕하세요, NHN에서 4년간 Spring Boot 기반 MSA 환경의 백엔드 개발을 담당해 온 김병태입니다.
- 소셜 카지노 게임 팀에서는 멀티서버 인메모리 캐시 정합성 문제를 RabbitMQ Fanout과 StampedLock으로 해결하고, 핵심 API 응답 흐름을 @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + 스케줄러 재시도 구조로 재설계하며 동시성·신뢰성 설계를 주도했습니다.
- 이후 AI 서비스 개발팀으로 이동해 사내 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 11-Step RAG 파이프라인을 처음부터 설계·구현했고, AsyncItemProcessor로 I/O 병렬화와 Step 단위 실패 격리를 동시에 확보했습니다.
- 최근에는 Claude Code 하네스 기반 4인 에이전트 팀을 조율해 12일 만에 AI 웹툰 제작 도구 MVP를 단독 풀스택으로 완성하며, 설계부터 운영까지 책임지는 시니어 백엔드의 역할을 넓혀가고 있습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영이 1,600만 고객을 상대하는 대규모 커머스 환경에서 제가 실무로 쌓아온 기술 축(Event-Driven, Cache-Aside, 대용량 데이터, 도메인 모델링)이 그대로 맞닿아 있다고 생각해 지원했습니다.
- 올리브영 기술 블로그의 'Redis Cache-Aside + Kafka 이벤트 하이브리드' 전략은, 제가 게임 팀에서 PostCommitUpdateEventListener + RabbitMQ Fanout으로 다중 서버 캐시 정합성을 유지한 경험과 문제 해결 방식이 직접 닿아 있어 빠르게 기여할 수 있다고 판단했습니다.
- 무중단 OAuth2 전환기에서 보이는 Feature Flag · Shadow Mode · Resilience4j 기반 점진 전환 설계는, 제가 AFTER_COMMIT 이벤트 발행 · Dead Letter Store · traceId 기반 실패 추적으로 구축한 비동기 신뢰성 설계와 동일한 '구조로 안정성을 확보한다'는 철학을 공유합니다.
- Spring Batch 기반 OpenSearch 벡터 색인 운영 경험(증분 처리·삭제 동기화·다중 스페이스)은 커머스 상품 검색 도메인의 색인 파이프라인에 그대로 이식 가능하다고 확신합니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 게임 도메인에서 동시성·이벤트 기반 신뢰성 설계를 깊이 경험했지만, 대규모 커머스 트래픽 환경에서 같은 기술이 어떻게 작동하고 어디서 한계가 생기는지 직접 검증해 보고 싶어 이직을 결정했습니다.
- AI 서비스팀에서 Spring Batch·OpenSearch·Gemini 기반 파이프라인을 주도하며 '설계자 레벨'로 한 단계 성장했고, 이 역량을 더 복잡한 도메인(상품·전시·주문)에 투입해 폭을 넓히고 싶습니다.
- 개인 성과보다 팀 전체의 개발 속도·유지보수성을 높이는 구조 개선에 관심이 많은데, 1,600만 고객을 상대하는 플랫폼에서는 이런 구조적 기여가 실제 사용자 영향력으로 바로 이어진다고 판단했습니다.

### 왜 올리브영인가
- 올리브영 기술 블로그의 'MSA 도메인 데이터 연동 전략', '무중단 OAuth2 전환기', 'SQS 데드락 분석기', 'Spring 트랜잭션 동기화' 네 편을 모두 정독했고, 제가 실무에서 고민한 주제(이벤트 드리븐 신뢰성, 캐시 정합성, 데드락, 트랜잭션 동기화)와 정확히 겹쳐 '문화 핏'이 있다고 느꼈습니다.
- 올영세일처럼 평소 대비 10배 트래픽이 몰리는 환경에서 Feature Flag · Jitter · Circuit Breaker로 P95 50ms·성공률 100%를 유지한 사례는, 제가 지향하는 '구조로 안정성을 만든다'는 엔지니어링 철학과 일치합니다.
- 커머스플랫폼유닛은 상품·전시·검색·주문처럼 복잡한 이커머스 도메인을 다루는 팀인데, 제가 꾸준히 투자해 온 도메인 추상화(AbstractPlayService + SpinOperationHandler, EmbeddingMetadataProvider)와 인터페이스 기반 확장 구조가 그대로 적용될 수 있는 조직이라고 판단했습니다.

### 왜 이 역할에 맞는가
- JPA·Hibernate·Spring Transaction을 실무에서 깊게 써 왔고, PostCommitUpdateEventListener를 활용한 커밋 시점 캐시 갱신, @TransactionalEventListener(AFTER_COMMIT) 기반 이벤트 발행처럼 ORM과 트랜잭션 경계를 설계 레벨에서 다룬 경험이 커머스 도메인 모델링 요구에 직접 연결됩니다.
- Kafka 기반 Event-Driven 설계를 'Dead Letter Store + 스케줄러 재시도 + traceId 기반 추적'까지 운영 레벨에서 완결해 본 경험이 있어, 도메인 간 이벤트 연동·장애 격리·재처리 전략에 즉시 기여할 수 있습니다.
- OpenSearch 벡터 색인·증분 처리·삭제 동기화를 Spring Batch로 구현·운영해 본 경험은, 커머스 상품 검색 색인 파이프라인의 재시작성·실패 격리·대용량 처리 요구에 그대로 이식 가능합니다.
- AI 개발 도구 도입·하네스 파이프라인 설계 경험을 살려 팀의 반복 개발 사이클과 코드 품질 게이트를 끌어올리는 역할까지 확장하고 싶습니다.

## 메인 질문 1. Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 '처음부터' 설계했다고 하셨는데, 왜 Spring Batch여야 했고 11개 Step으로 쪼갠 기준은 무엇이었나요? 그리고 설계 과정에서 가장 비쌌던 트레이드오프는 무엇이었습니까?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 단순 구현자가 아니라 '왜 이 기술을, 이 구조로 선택했는가'를 설명할 수 있는 시니어 설계자인지 검증하려는 의도.
- 재시작성·청크 처리·Step 단위 실패 격리 같은 Spring Batch의 본질을 요구 사항(대용량·I/O 바운드·외부 API 연동)에 맞게 매핑했는지 확인.
- 선택하지 않은 대안(스케줄러·Kafka Connect·사내 파서 호출 직접 구현)을 근거 있게 기각할 수 있는지도 간접적으로 검증.

### 실제 경험 기반 답변 포인트

- 요구 사항을 먼저 정의: (1) 수천~수만 건 문서의 증분 색인, (2) 임베딩 API·문서 파싱 API·Confluence API 3단계 외부 호출이 전부 I/O 바운드, (3) 실패 시 '처음부터 다시'가 아니라 '실패한 지점부터 재시작' 가능해야 함, (4) 다중 스페이스(baseUrl·토큰 상이)·삭제 동기화·첨부파일 ZIP 분해까지 운영 기능이 따라붙음.
- Spring Batch 선택 근거 4가지: 청크 커밋으로 OOM 방지, JobRepository 기반 재시작(ExecutionContext에 커서 위치 저장), Step 단위 실패 격리로 댓글 Step 실패가 페이지 Step 결과를 무효화하지 않음, 실행 이력의 영속화로 언제 어느 Job이 성공/실패했는지 추적 가능.
- 11 Step 분할 기준: 단일 책임(시작 기록 → 연결 초기화 → 스페이스 수집 → 페이지 색인 → 페이지 ID 수집 → 댓글 색인 → 삭제 3종 → Index refresh → 완료 기록), 즉 '외부 호출 대상'과 '책임'을 축으로 쪼갬. 앞 Step의 산출물을 뒤 Step이 읽는 의존성은 @JobScope 홀더(ConfluenceJobDataHolder)로 전달하고, JobExecutionContext는 재시작용 경량 커서 전용으로 제한.
- 가장 비쌌던 트레이드오프: 초기 구현에서 JobExecutionContext에 페이지 ID 수천 개를 저장했다가, 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블 직렬화 비용이 누적되는 걸 확인하고 @JobScope 인메모리 홀더로 이전. 단, 재시작 시 상태 로더 Step이 COMPLETED로 스킵되면 NPE가 나기 때문에 allowStartIfComplete(true)를 명시해 '재시작 안전성'과 '경량 상태 관리'를 동시에 확보.
- 대안 기각 근거: 단순 스케줄러는 재시작성·이력 관리를 직접 만들어야 하고, Kafka Connect는 임베딩·ADF→Markdown 변환 같은 도메인 로직을 얹기 어려움. 사내 AI 팀이 운영 주체라는 점을 고려하면 Spring Batch가 Java/Spring 스택과의 정합성도 가장 높았음.

### 1분 답변 구조

- 첫 줄: 'Spring Batch를 선택한 이유는 재시작성·청크 처리·Step 단위 실패 격리 3가지가 요구 사항과 정확히 맞아떨어졌기 때문입니다.'
- 중간: 11 Step은 외부 호출 대상과 책임을 축으로 쪼갰고, 앞 Step 산출물은 @JobScope 홀더(ConfluenceJobDataHolder), 재시작용 경량 커서는 JobExecutionContext로 역할을 분리했다고 설명.
- 마무리: 가장 비쌌던 트레이드오프는 JobExecutionContext 남용이었고, 청크 커밋마다 DB 직렬화 비용이 쌓이는 걸 발견해 @JobScope로 이전하고 allowStartIfComplete(true)로 재시작 안전성을 함께 확보했다고 마감.

### 압박 질문 방어 포인트

- 'Kafka Streams나 Airflow로 풀지 않은 이유는?' → Kafka Streams는 변경 감지·증분 색인·삭제 동기화를 직접 쌓아야 하고, Airflow는 사내 스택·운영 주체·Java 생태계 정합성이 맞지 않았음. Spring Batch는 JPA·Spring Boot와 동일 컨텍스트에서 운영 인력 부담 없이 굴릴 수 있는 유일한 선택지였다고 답.
- 'Step 11개면 너무 잘게 쪼갠 것 아닌가?' → 각 Step의 책임이 '외부 호출 대상 1개 + 단일 side effect'로 수렴하는지로 검증했고, 실제로 문서 파싱 API 장애 때 댓글 Step과 삭제 Step은 영향받지 않고 페이지 Step만 재시작해 전체 색인을 살린 사례가 있다고 구체 사례로 방어.
- '@JobScope 남용이 Spring Context 비용을 키우지 않나?' → holder 1개 빈에 국한했고, proxyMode=TARGET_CLASS로 싱글톤 주입도 안전하며, 페이지 ID·스페이스 정보처럼 '한 Job 수명 동안만 유효한 도메인 상태'에만 적용했다고 한정.

### 피해야 할 약한 답변

- 'Spring Batch가 표준이라 썼습니다' 같은 관성적 답변 — 요구 사항과의 매핑을 설명하지 못하면 시니어 신호가 깨짐.
- 'Step을 잘게 나누면 관리가 편해서요' 같은 주관적 기준 — '실패 격리'·'외부 호출 경계'·'재시작 지점'이라는 설계 축을 언급하지 않으면 설득력이 약함.
- 대안(Kafka Connect·Airflow·커스텀 스케줄러)을 한 번도 평가해 보지 않은 듯한 답변 — '왜 선택하지 않았는가'를 근거 있게 말하지 못하면 의사결정자로서의 깊이가 드러나지 않음.
- JobExecutionContext 남용 경험 같은 '실제로 부딪힌 비용'을 생략하고 이상적 설계만 설명하는 답변 — 운영 경험의 증거가 약해 보임.

### 꼬리 질문 5개

**F1-1.** 페이지 ID 수집 Step과 삭제 Step 사이에서 '재시작 시 상태 손실'을 구체적으로 어떻게 재현했고 allowStartIfComplete(true)로 어디까지 복구되는지 설명해 주세요.

**F1-2.** 청크 사이즈는 어떻게 튜닝했고, 임베딩 API의 Rate Limit·응답 지연·실패율을 고려해 어떤 지표(처리 시간, 429 발생률, 메모리)를 기준으로 최종 값을 결정했습니까?

**F1-3.** Confluence Cloud의 302 리다이렉트·MIME 타입 위조 같은 외부 API '거짓말' 문제를 어떻게 방어했고, 운영 로그에서 어떤 신호를 모니터링하십니까?

**F1-4.** 만약 동일 파이프라인을 Kafka 기반 스트림 처리로 재설계한다면 어떤 Step이 '배치로 남아야 하고' 어떤 Step이 '스트림으로 옮겨야 한다'고 판단하시겠습니까?

**F1-5.** 커머스 상품 검색 색인 파이프라인에 이 구조를 이식한다면 가장 먼저 바꿀 3가지 설계 포인트는 무엇이고 그 근거는 무엇입니까?

---

## 메인 질문 2. 색인 Step의 Processor를 AsyncItemProcessor + CompositeItemProcessor 4단계로 체이닝하셨는데, 왜 이 조합이 필요했고 각 단계의 책임 경계는 어떻게 그었습니까? 그리고 '비동기 + 체이닝'에서 가장 자주 부딪히는 함정은 무엇이었나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- I/O 바운드 작업을 '스레드풀에 넘기면 끝'이 아니라 Spring Batch의 트랜잭션·재시작·에러 전파 맥락 안에서 설계할 수 있는지 확인.
- CompositeItemProcessor를 '관심사 분리 도구'로 쓸 줄 아는지, 그리고 '변경 감지 → 보강 → 변환 → 임베딩' 순서의 의미(비용·의존성·실패 영향)를 설명할 수 있는지 검증.
- Future<T>·AsyncItemWriter·트랜잭션 경계의 조합에서 발생하는 실제 함정(예외 전파 시점, 순서 뒤집힘, 재시작 시 컨텍스트 손실)을 경험적으로 알고 있는지 확인.

### 실제 경험 기반 답변 포인트

- 비동기가 필요했던 이유: 임베딩 API 한 호출이 수백 ms 단위의 네트워크 I/O이고, 청크 사이즈 10이면 동기 처리 시 청크당 최소 2초. 스페이스에 수천 페이지면 전체 색인이 수 시간 단위로 밀림. AsyncItemProcessor로 청크 내 아이템을 parallelChunkExecutor 스레드풀에서 병렬 처리하고, AsyncItemWriter가 Future.get()으로 결과를 모아 OpenSearch 벌크 색인으로 위임.
- Composite 체이닝 순서와 근거: ChangeFilterProcessor(version 비교로 미변경 스킵 · null 반환이 곧 Spring Batch의 skip 신호) → EnrichmentProcessor(첨부파일·작성자·멘션 displayName 보강) → BodyConvertProcessor(ADF→Markdown) → EmbeddingProcessor(임베딩 호출). 비용이 가장 큰 단계를 가장 뒤에 배치해 '불필요한 임베딩 호출을 앞 단계에서 걸러내는' 비용 구조.
- 단일 책임과 교체 가능성: 각 Processor가 단일 관심사만 갖도록 인터페이스를 분리했고(예: BodyConverter), 포맷이 바뀌면 BodyConverterProvider가 atlas_doc_format 같은 파라미터로 구현체만 교체. 덕분에 임베딩 모델·메타데이터 포맷·본문 포맷이 각각 독립적으로 진화 가능.
- 자주 부딪힌 함정 3가지: (1) AsyncItemProcessor의 예외가 Future.get() 시점에 터져서 '에러 메시지 위치'와 '실제 실패 아이템' 매핑이 어긋남 → traceId·page id를 Future 결과에 동봉해 Writer에서 로깅. (2) @StepScope 빈이 두 Job에서 같은 타입으로 등록되며 NoUniqueBeanDefinitionException 발생 → 공용 빈은 @Component @StepScope로 전역화, 잡 전용 빈은 @Qualifier로 명시. (3) 실패 누적 문서를 매 실행마다 재시도하면 임베딩 API 비용이 커짐 → ChangeFilterProcessor에 실패 횟수 임계치를 두고 자동 스킵.
- 재시작 시 데이터 정합성: ItemStream 구현으로 커서 위치를 ExecutionContext에 저장, 실패 지점부터 재개. 단 앞서 설명한 @JobScope 홀더는 상태 로더 Step의 allowStartIfComplete(true)가 없으면 재시작 시 비어버리므로 반드시 세트로 관리.

### 1분 답변 구조

- 첫 줄: '임베딩·문서 파싱·Confluence API가 모두 I/O 바운드여서, 동기 처리 시 처리 시간이 API 대기 시간에 선형으로 묶였습니다.'
- 중간: AsyncItemProcessor로 청크 내 병렬 처리, CompositeItemProcessor로 변경 감지→보강→변환→임베딩 4단계를 체이닝하되, 가장 비싼 임베딩 호출을 뒤에 둬 앞 단계에서 최대한 걸러내는 비용 구조를 짰다고 설명.
- 마무리: 가장 자주 부딪힌 함정은 Future 예외의 위치 불일치·@StepScope 빈 중복 등록·실패 누적 재시도 비용 세 가지였고, traceId 동봉·@Qualifier 분리·실패 임계치 스킵으로 대응했다고 마감.

### 압박 질문 방어 포인트

- 'Reactive(WebClient + Mono)로 풀면 더 깔끔하지 않나?' → Spring Batch의 청크 커밋·재시작·실행 이력 모델은 명시적 블로킹 경계를 전제로 설계돼 있어, Reactive 스택과 섞으면 트랜잭션 경계·JobRepository 기록 시점이 어긋남. '배치 모델과 정합성'이라는 축에서 AsyncItemProcessor가 가장 비용이 낮았다고 답.
- '체이닝이 너무 깊어서 디버깅 어렵지 않나?' → 각 Processor가 Stateless·단일 책임·인터페이스 기반이라 단위 테스트로 개별 검증 가능했고, 실제로 ADF→Markdown 변환 버그는 BodyConvertProcessor 단독 테스트로 격리 재현했다고 구체 사례로 방어.
- '스레드풀 크기 튜닝 기준은?' → CPU가 아니라 외부 API의 허용 동시성·Rate Limit·평균 응답 시간의 곱을 상한으로 잡았고, 임베딩 API 429 빈도가 임계치를 넘으면 스레드풀을 좁히는 방향으로 보수적으로 튜닝했다고 답.

### 피해야 할 약한 답변

- '병렬로 돌리면 빨라져서 썼다'처럼 수치·비용 구조 없이 설명하는 답변 — I/O 바운드라는 본질을 짚지 못하면 기술 깊이가 드러나지 않음.
- CompositeItemProcessor를 단순히 'Processor를 여러 개 붙이는 문법'으로만 설명 — 순서의 비용 근거(비싼 호출을 뒤로)를 설명하지 못하면 설계자 관점이 약함.
- Future 예외 전파 함정·@StepScope 빈 충돌 같은 실제 운영 이슈를 언급하지 않는 '이상적 설명' — 운영 증거가 부족해 보임.
- 'Spring Batch가 알아서 해 줍니다' 식의 프레임워크 의존 발언 — 시니어는 프레임워크의 기본 동작과 한계를 모두 설명할 수 있어야 함.

### 꼬리 질문 5개

**F2-1.** AsyncItemProcessor 환경에서 트랜잭션 경계는 어디에 그어지고, Writer에서 OpenSearch 벌크 색인이 부분 실패했을 때 재시도·롤백 전략을 어떻게 설계하셨습니까?

**F2-2.** ChangeFilterProcessor의 'version 비교 스킵' 로직에서 false positive/negative(실제로는 바뀌었는데 스킵·안 바뀌었는데 임베딩)를 어떻게 모니터링하고 있습니까?

**F2-3.** @Component @StepScope와 @Bean @StepScope의 역할을 어느 시점에 어떤 기준으로 구분했고, 테스트 코드에서 @Qualifier 누락으로 실패한 사례를 어떻게 재현·예방하십니까?

**F2-4.** parallelChunkExecutor의 스레드풀 설정(코어·맥스·큐)을 결정하기 위해 관찰한 지표와, 스레드풀을 전역 공유로 가져갈지 Job별로 분리할지에 대한 의사결정 기준을 설명해 주세요.

**F2-5.** 동일한 Processor 체이닝 패턴을 커머스 상품 색인 파이프라인에 적용한다면, '변경 감지 → 보강 → 변환 → 임베딩' 중 어떤 단계가 가장 먼저 병목이 될 것이라 예상하시고 그 근거는 무엇입니까?

---

## 메인 질문 3. gRPC OCR 서버 배포·스케일인 시 503이 일정 주기로 발생한 문제를, terminationGracePeriodSeconds 30초 고정 제약 하에서 Envoy·supervisord·SIGTERM·preStop hook을 어떻게 재설계해서 해결하셨는지 시퀀스 단위로 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- '로그 에러 111'이라는 단일 신호를 TCP·L7(Envoy)·컨테이너 라이프사이클(preStop/SIGTERM)·프로세스 감독자(supervisord) 계층으로 분해해서 root cause를 잡을 수 있는 시니어인지 검증.
- 클라우드 제약(30초 고정)을 '바꾸려 하지 않고' 주어진 예산 안에서 각 단계 타임라인을 재설계할 수 있는 엔지니어링 감각을 확인.
- 대규모 커머스의 무중단 배포 맥락(올리브영 무중단 OAuth2 전환, Feature Flag, Shadow Mode)으로 확장 가능한 일반 원칙을 후보자가 이해하고 있는지 간접 검증.

### 실제 경험 기반 답변 포인트

- 현상 요약: 배포·스케일인 시 `upstream connect error ... reset reason: connection failure ... error 111(ECONNREFUSED)` 503이 30~60초 주기로 묶음 발생. 응답 헤더 `server: envoy`에서 Envoy는 살아있고 upstream(:50051)이 거부한 상황으로 특정.
- root cause 2가지: (1) gRPC 서버(`server_grpc_general_OCR.py`)에 SIGTERM 핸들러가 없어 preStop의 `sleep 20` 종료 후 SIGTERM 수신 순간 즉시 포트 50051이 닫힘. Envoy는 아직 drain 중이라 신규 요청을 upstream으로 라우팅하다 ECONNREFUSED를 받음. (2) supervisord `[program:grpc-server]`에 `stopwaitsecs` 미설정 → 기본 10초 → 핸들러를 넣어도 10초 후 SIGKILL로 강제 종료되는 구조.
- NCS 제약 인식: NHN Cloud Container Service는 `terminationGracePeriodSeconds`를 30초로 고정하고 API 스펙에 해당 필드가 없어 변경 불가. 제약을 '바꾼다'가 아니라 '30초 예산을 어떻게 배분할 것인가'의 문제로 재정의.
- 예산 배분 설계: `preStop sleep 15s + gRPC grace 12s + 여유 3s = 30s`. preStop에서 Envoy `drain_listeners` 호출로 L7에서 신규 라우팅 차단 후 15초 대기 → SIGTERM → `server.stop(grace=12)`로 in-flight RPC 처리 후 정상 종료. supervisord `stopwaitsecs=17`(grace 12 + 여유 5)로 프로세스 감독자가 중간에 SIGKILL로 죽이지 않도록 정렬.
- 수정 후 시퀀스: T+0(preStop 시작, Envoy drain, sleep 15s) → T+15s(preStop 완료, SIGTERM, `server.stop(grace=12)` 시작) → T+15~27s(in-flight 처리·신규 거부) → T+27s(gRPC 종료, 컨테이너 종료). 이후 503은 재현되지 않음.
- 일반 원칙: '누가 먼저 죽느냐'가 아니라 '누가 언제까지 받고, 언제 거부하고, 언제 종료되는가'를 단계별 타이밍으로 설계해야 하며, Envoy/Proxy·앱 프로세스·프로세스 감독자·오케스트레이터 4계층 모두가 같은 예산표를 공유해야 함.

### 1분 답변 구조

- 첫 줄: '503의 본질은 Envoy는 drain 중인데 gRPC 서버가 SIGTERM에 즉시 죽어 upstream이 먼저 사라지는 타이밍 어긋남이었고, 30초 grace 고정 제약 안에서 단계별 예산을 다시 배분해 해결했습니다.'
- 중간: gRPC 서버에 SIGTERM 핸들러 + `server.stop(grace=12)`, supervisord `stopwaitsecs=17`, preStop `sleep 15`로 `15+12+3=30` 예산을 명시적으로 맞췄다고 설명.
- 마무리: 핵심은 Envoy·앱·supervisord·오케스트레이터가 동일 예산표를 공유해야 한다는 것이고, 이 원칙은 커머스 무중단 배포·롤링 업데이트에도 그대로 적용된다고 마감.

### 압박 질문 방어 포인트

- 'grace 30초를 늘려달라고 인프라에 요청했어야 하는 것 아닌가?' → NCS API 스펙에 해당 필드가 없어 플랫폼 팀 요청 자체가 비현실적이었고, 주어진 제약 안에서 예산을 재배분하는 게 더 낮은 리스크·빠른 ETA였다고 답.
- 'gRPC `server.stop(grace)`만 붙이면 되는 것 아닌가, supervisord를 왜 건드렸나?' → 감독자가 프로세스를 10초 후 SIGKILL로 죽이는 한 앱 레벨 grace가 무력화되기 때문에, supervisord·앱·preStop·오케스트레이터 4계층이 같은 예산을 공유해야 한다고 답하며 해당 수치의 산정 근거(grace 12 + 여유 5 = 17)를 설명.
- 'Envoy drain_listeners를 안 쓰고 해결할 수 있지 않았나?' → drain 없이 앱 grace만 늘리면 신규 요청이 계속 upstream으로 들어와 in-flight가 줄지 않음. L7 차단(drain)과 앱 grace는 역할이 다르며 둘이 순차로 동작해야 503이 0으로 수렴한다고 원칙 단위로 방어.

### 피해야 할 약한 답변

- 'preStop에 sleep을 추가해서 해결했다'만 말하고 각 계층의 책임을 분리하지 못하는 답변 — 문제의 본질(타이밍 어긋남)을 짚지 못함.
- SIGTERM 핸들러만 언급하고 supervisord `stopwaitsecs`·preStop·Envoy drain의 역할을 설명하지 못하는 답변 — 운영 컨텍스트 이해가 얕아 보임.
- `terminationGracePeriodSeconds`를 30초에서 늘리는 쪽으로 먼저 접근하는 답변 — '제약 고정·예산 배분'이라는 엔지니어링적 사고가 드러나지 않음.
- '에러 111이 뭔지 정확히 모르겠다'거나 L4/L7 구분 없이 '503이라서 HTTP 문제다'로 뭉개는 답변 — 계층적 디버깅 능력이 없어 보임.

### 꼬리 질문 5개

**F3-1.** Envoy `drain_listeners`가 처리 중인 요청과 신규 연결·기존 Keep-Alive 커넥션을 각각 어떻게 다르게 처리하는지, 그리고 gRPC long-lived stream에서는 어떤 추가 고려가 필요한지 설명해 주세요.

**F3-2.** 수정 후에도 503이 극소수 발생한다면 가장 먼저 확인하실 지표·로그 필드는 무엇이고, 그 근거는 무엇입니까?

**F3-3.** 오토스케일러가 매우 공격적으로 축소하는 상황에서 `preStop + grace` 예산을 초과하는 in-flight 요청이 있다면, 어떤 백프레셔·큐잉 전략으로 유실을 더 줄일 수 있을까요?

**F3-4.** 동일한 원칙을 Spring Boot + Tomcat 기반 커머스 API 서버의 롤링 배포에 적용한다면, '무엇이 Envoy·supervisord·SIGTERM에 해당하는지' 매핑해서 설계를 제시해 보세요.

**F3-5.** K8s readiness probe·liveness probe와 preStop의 역할 중복·책임 경계는 어떻게 나눠야 503을 최소화할 수 있다고 보십니까?

---

## 메인 질문 4. 임베딩 요청의 메타데이터 구성을 blocklist(remove) 방식에서 `EmbeddingMetadataProvider` 기반 allowlist로 전환하셨습니다. '기능은 동일한데 구조만 바꾼 리팩터링'이 왜 가치 있었고, OCP·전략 패턴이 실제로 어떤 운영 이익을 만들었는지 증거 기반으로 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 시니어가 '동일 기능 리팩터링'에 정당성을 부여할 수 있는지 — 단순 취향·미적 이유가 아니라 가독성·변경 비용·OCP 같은 구체 축으로 설명할 수 있는지 확인.
- 전략 패턴을 '책에서 본 패턴'이 아니라 실제 요구(스페이스마다 다른 메타데이터 포맷, 새 DocumentType 추가) 맥락에서 구조적 문제로 풀어낸 경험인지 검증.
- Spring DI + @Component 자동 수집 + `Set<DocumentType>` 자기 선언 구조 같은 프레임워크 수준의 실무 설계 감각을 확인.

### 실제 경험 기반 답변 포인트

- before의 구조적 문제 4가지: (1) EmbeddingService 단일 메서드에 14개 `remove(...)` 호출 + 타입별 if-else 분기가 누적되며 '실제로 포함되는 필드'를 역산해야 파악 가능, (2) 새 DocumentType 추가마다 EmbeddingService를 고쳐야 해 OCP 위반, (3) 패턴 유지를 위해서만 존재하는 메서드(`cloneMetadata`, `getMetadataValue`, `putMetadata`)가 도메인 모델을 오염, (4) 스페이스별 특수 포맷(title vs subject, extra_data 포함 여부)이 새로 들어오면 분기가 기하급수로 늘어남.
- 해결 아이디어 한 줄: '제거할 필드를 관리하지 말고, 포함할 필드를 명시적으로 관리한다.' `EmbeddingMetadataProvider` 인터페이스에 `getSupportedDocumentTypes()`와 `provide(Document)` 두 메서드만 두고, 각 구현체가 자기 담당 DocumentType을 자기 선언.
- 계층 설계: `AbstractEmbeddingMetadataProvider`(putIfNotNull·putFormattedDatetime 공통 유틸) → `AbstractCollabToolEmbeddingMetadataProvider`(협업 도구 공통 필드) → Task/Wiki/DriveFile 구현체, 별도 계보로 `AbstractConfluenceEmbeddingMetadataProvider`(title/subject 폴백) → Confluence 구현체. '공통 필드는 위로, 도메인 특수 규칙은 아래로' 원칙.
- Spring DI 조립: 모든 구현체를 `List<EmbeddingMetadataProvider>`로 자동 주입받고, Config에서 `flatMap`으로 `DocumentType → Provider` 맵을 빌드. EmbeddingService는 맵 조회 + `provide()` 위임만 수행. 새 DocumentType은 `@Component` 구현체 추가만으로 끝나며 EmbeddingService 코드를 건드리지 않음.
- 증거 기반 운영 이익: (a) 신규 스페이스의 `subject` 폴백 같은 특수 포맷을 `AbstractConfluenceEmbeddingMetadataProvider`에 단 한 곳만 정의, (b) 구현체별 독립 단위 테스트로 '어떤 필드가 임베딩에 들어가는가'를 코드 레벨에서 증명, (c) Document 도메인에서 임시 메서드 3종을 제거해 모델 표면적이 축소, (d) 이후 DriveFile처럼 version·revision이 추가되는 도메인이 붙을 때도 EmbeddingService를 건드리지 않음.

### 1분 답변 구조

- 첫 줄: '기능은 동일해도 blocklist 방식은 OCP를 위반해 도메인이 늘수록 EmbeddingService와 Document 모델 모두가 계속 부풀고 가독성이 역산 방식에 의존했습니다.'
- 중간: `EmbeddingMetadataProvider` 인터페이스로 각 구현체가 자기 DocumentType을 자기 선언하고, Spring이 `List`로 자동 수집해 Config에서 `DocumentType → Provider` 맵으로 빌드, EmbeddingService는 위임만 하는 구조로 바꿨다고 설명.
- 마무리: 신규 스페이스 특수 포맷은 한 구현체에 국한되고, 구현체별 단위 테스트로 '포함 필드'를 코드 레벨에서 증명하며, Document 도메인에서 3개 임시 메서드를 제거해 표면적을 줄였다고 증거 기반으로 마감.

### 압박 질문 방어 포인트

- '같은 결과인데 리팩터링 비용이 정당화되나?' → 신규 DocumentType 추가가 월 1회 이상 예상되는 상황에서 blocklist는 매번 EmbeddingService를 건드리게 만들어 회귀 위험이 누적됨. 리팩터링 1회의 비용보다 '매 추가마다의 위험 비용'이 더 크다는 TCO 관점에서 정당화했다고 답.
- '인터페이스·추상 클래스 계층이 3단이면 오버엔지니어링 아닌가?' → 실제로 협업 도구 공통 필드와 Confluence 특수 폴백(title↔subject)이 다른 경로를 요구했기 때문에 공통을 억지로 하나로 묶으면 더 나쁜 추상화(이중 if)를 만들게 됨. '진짜 다른 두 공통'을 두 개의 추상 클래스로 인정한 게 낫다고 답.
- 'Spring이 Provider를 못 찾으면 어떻게 되나?' → 맵에 없으면 명시적으로 기존 기본 경로로 떨어지도록 fallback을 뒀고, DocumentType enum이 늘어나면 컴파일 시점에 누락을 잡을 수 있도록 테스트에서 모든 enum 값을 순회 검증하는 가드 테스트를 추가했다고 답.

### 피해야 할 약한 답변

- '코드가 깔끔해져서 바꿨다'처럼 심미적 이유만 드는 답변 — 시니어 신호 부족.
- blocklist의 구체적 문제(14개 remove·if-else·cloneMetadata 의존 등)를 언급하지 않는 답변 — before 인식이 얕아 보임.
- 전략 패턴을 설명하면서 Spring DI·@Component 자동 수집·맵 빌딩 조립 방식을 언급하지 않는 답변 — 실무 조립 감각이 약해 보임.
- '테스트가 쉬워졌다'만 말하고 어떤 테스트가 왜 쉬워졌는지(구현체별 독립 단위 테스트, enum 가드 테스트 등) 구체화하지 못하는 답변.

### 꼬리 질문 5개

**F4-1.** blocklist → allowlist 전환 과정에서 임베딩 결과의 동일성(회귀 없음)을 어떻게 검증했습니까? 스냅샷 테스트·diff 도구·샘플링 중 어떤 방식을 선택하셨고 그 근거는 무엇인가요?

**F4-2.** 만약 새 DocumentType이 `provide()` 구현을 깜빡했을 때 런타임이 아니라 빌드·기동 시점에 실패하게 만들려면 어떤 가드를 추가하시겠습니까?

**F4-3.** `Set<DocumentType>` 자기 선언 방식 대신 `@Handles(DocumentType.TASK)` 같은 애너테이션 기반 라우팅으로 바꾼다면 얻는 것·잃는 것은 무엇입니까?

**F4-4.** 동일한 전략 패턴 구조를 커머스 도메인(상품 카테고리별 진열 규칙, 프로모션 타입별 할인 계산)에 적용한다면, 어느 지점이 '공통 추상 계층'이 되고 어디가 '구현체의 자유'로 남아야 할까요?

**F4-5.** allowlist로 바꾸면서 도메인 모델(Document)에서 제거한 `cloneMetadata/getMetadataValue/putMetadata`처럼, '패턴 유지를 위해서만 존재하는 메서드'의 발견·제거 기준을 팀에 어떻게 정착시키셨습니까?

---

## 메인 질문 5. 12일 동안 혼자서 Next.js 16 + Prisma 7 + Gemini 기반 6단계 AI 웹툰 제작 MVP를 199 plan · 760 커밋 규모로 완성하셨는데, 이게 가능했던 '하네스 파이프라인'의 구조와 진화를 설명해 주시고, 그 경험에서 백엔드 시니어로서 일반화할 수 있는 원칙 3가지를 뽑아 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI/에이전트 협업 경험이 '툴 사용자' 수준을 넘어 '파이프라인 설계자'로 성장했는지, 즉 Gemini 모델 전략·Rate Limit·Context Cache·역할 분리된 에이전트 팀 조율 같은 구조적 의사결정을 했는지 검증.
- 백엔드 시니어 관점에서 일반화 가능한 원칙(docs-first, 호출 구조 설계, 관심사 분리 등)으로 승화할 수 있는지 — 즉 '다른 도메인으로 이식 가능한 학습'을 뽑는 능력이 있는지 확인.
- 커머스 플랫폼 관점에서 '대규모 요청의 fallback·rate limit·cache'가 곧바로 연결될 수 있는지를 간접 검증.

### 실제 경험 기반 답변 포인트

- 하네스 진화 5단계: (1) vibe 코딩 — 한 세션에서 논의·구현·빌드·테스트를 모두 처리하다 컨텍스트 한도·결정 누락으로 한계, (2) `/planning`으로 스펙을 먼저 확정(기술 가능성·데이터 모델·API·엣지·마이그레이션·검증 8축, Opus로 수행), (3) `/plan-and-build`로 plan을 `index.json` + phase 파일로 분해해 재시작 가능·자기완결적 실행 단위화, (4) `/build-with-teams`로 critic(계획↔코드 정합성 검증)과 docs-verifier(ADR·스키마 드리프트 검증) 게이트 추가해 4인 에이전트 팀(planner·critic·executor·docs-verifier) 구성, (5) `/integrate-ux`로 디자이너의 vibe 결과물을 Container/Presenter·semantic 토큰·공통 컴포넌트 규칙으로 흡수하는 변환 워크플로우까지 스킬화.
- Gemini 운영 전략 3축: (A) 모델 전략 — flash 기본이 '재생성 비용'을 키워 총 비용이 오히려 증가하므로 pro를 기본으로 두고 429 시 flash→lite fallback, (B) 전역 Rate Limit Tracking — `Map<string, number>` 기반 메모리 맵으로 429 맞은 모델을 일정 시간 skip 대상으로 마킹해 다른 요청이 같은 모델을 두드리지 않게 함, (C) Gemini Context Cache — 63만 자 원작 소설을 Project 단위 `cachedContent`로 묶어 Analysis·Content-review·Treatment·Conti·Continuation 다섯 단계가 공유, 만료(5분) 내 입력 토큰 비용을 사실상 0으로.
- 환각 차단의 본질: anti-pattern 문구 추가가 아니라 '호출 구조 설계' 문제. Continuation이 tail 5컷만 보고 다음 컷을 만들어 grounding이 사라진 게 진짜 원인. 1차·continuation 양쪽에서 동일한 `buildGroundingBlock()`을 호출하고, '허용되는 창의는 연출(카메라·구도·조명·페이싱)만, 서사는 grounding'이라는 경계를 명시. 이미지 일관성도 텍스트 anti-drift가 아니라 기본 시트 이미지 레퍼런스 자동 prepend로 해결(채널 정합성).
- 통합 분석 결정: Step1의 5개 영역을 별도 호출로 처리하면 TPM 한도에 닿아 429 빈발. Zod 스키마의 필드로 '논리적 경계'를 유지하면서 하나의 Structured Output으로 합쳐 토큰 75% 절감·13.1s로 단축. 'API 경계 ≠ 논리 경계'라는 원칙을 도출.
- 백엔드 시니어로 일반화 가능한 원칙 3가지: (1) 비용 최적화는 '단가'가 아니라 '총 호출 횟수(재시도 포함)' 기준이며, 분산 재시도 정책은 전역 상태(global rate limit tracking)가 있어야 비효율이 누적되지 않는다, (2) '1개의 긴 작업'은 SSE·스트리밍, 'N개의 독립 작업'은 클라이언트 `Promise.allSettled` 등 병렬 실행 — 두 성격을 한 구조로 묶지 말 것, (3) docs-first는 매너가 아니라 생산성 도구. 에이전트·신규 팀원의 컨텍스트가 되는 ADR·스키마가 부패하면 다음 세션의 전제가 깨진다.

### 1분 답변 구조

- 첫 줄: '12일에 760커밋이 나온 건 제가 키보드로 친 결과가 아니라 5단계로 진화한 하네스 파이프라인과 4인 에이전트 팀(planner·critic·executor·docs-verifier)이 돌린 결과입니다.'
- 중간: Gemini는 pro 기본 + 429 시 flash→lite fallback, 전역 Rate Limit Tracking, Project 단위 Context Cache 3축으로 운영했고, 환각은 continuation에 grounding 재주입이라는 '호출 구조 설계'로 잡았으며, Step1의 통합 분석으로 API 경계와 논리 경계를 분리해 토큰 75%를 절감했다고 설명.
- 마무리: 여기서 뽑은 백엔드 원칙은 (1) 총 호출 수 기준 비용 관점과 전역 rate limit 상태, (2) 단일 스트림 vs 독립 N개 요청의 구조 분리, (3) docs-first — 커머스의 API·캐시·이벤트 설계에도 그대로 이식된다고 마감.

### 압박 질문 방어 포인트

- 'AI가 짠 코드라 품질 보장되냐?' → critic이 계획↔코드 정합성을, docs-verifier가 ADR·스키마 드리프트를, 그리고 Container/Presenter 분리·파일 소유권 매트릭스·semantic 토큰으로 구조적 가드레일을 뒀다고 답. 134개 ADR이 설계 결정의 근거로 남아 있다고 증거 제시.
- '백엔드 포지션에 이 경험이 왜 관련 있나?' → 모델 fallback·rate limit·cache·재시도 전략은 대규모 커머스 API의 외부 의존성 관리(결제·배송·재고 API)와 동일한 설계 문제. 특히 '재생성 비용이 단가보다 비싸다'는 원칙은 커머스의 캐시 전략·SLA 설계에 직접 연결된다고 답.
- '혼자 760커밋은 과포장 아닌가?' → 커밋의 주체는 에이전트이고 제 역할은 plan 설계·critic 판정 검토·ADR 승인에 있었음을 명확히 분리. 반대로 199개 plan 중 APPROVE/REVISE 판정과 phase 분할은 모두 제가 책임졌고, 이 조율이 곧 시니어의 일이라고 재정의.

### 피해야 할 약한 답변

- 'Claude/Gemini에게 시키니까 빨랐다'처럼 에이전트의 성과를 자기 성과로 뭉개는 답변 — 역할 분리를 설명하지 못하면 오히려 신뢰도가 떨어짐.
- Gemini 모델 선택을 '비싼 게 좋다'로만 말하고 '재생성 비용을 포함한 총 비용' 논거를 제시하지 못하는 답변.
- 환각 문제를 '프롬프트를 잘 쓰면 된다'로 답하는 경우 — '호출 구조 설계' 관점이 누락되면 얕아 보임.
- backend 포지션과의 연결점(rate limit·fallback·cache·재시도·docs-first)을 명시적으로 연결하지 못하면 '흥미로운 사이드 프로젝트' 수준으로만 보임.

### 꼬리 질문 5개

**F5-1.** Gemini 전역 Rate Limit Tracking의 Map 키·TTL·공유 범위를 어떻게 설계하셨고, 프로세스 다중화(여러 인스턴스) 시 이걸 Redis·분산 상태로 옮긴다면 어떤 정합성 문제가 생길 수 있다고 보십니까?

**F5-2.** Project 단위 Gemini Context Cache의 만료·무효화 전략은 어떻게 짰고, 커머스에서 '상품 설명·카탈로그'를 유사한 방식으로 캐시한다면 가장 먼저 설계해야 할 정합성 규칙은 무엇일까요?

**F5-3.** `Promise.allSettled`로 60컷을 병렬 생성하신 구조에서, 브라우저 호스트당 6 동시 연결 제한을 의도적 백프레셔로 쓰셨는데 서버 측에서 추가로 보호해야 할 경계(큐·세마포어·Rate Limit)는 어디라고 보십니까?

**F5-4.** critic·docs-verifier 에이전트가 실제로 잡아낸 '사람이 놓쳤을 법한 오류'의 구체 사례를 1개만 들어 주시고, 커머스의 코드 리뷰·배포 게이트에 어떻게 이식할 수 있을지 제안해 주세요.

**F5-5.** 하네스 진화를 '기술 블로그 글로 정리한다'면 독자에게 전달하고 싶은 핵심 한 문장은 무엇이고, 그 문장에 가장 반대할 만한 시니어 백엔드 개발자의 반론은 무엇이라고 예상하십니까?

---

## 최종 준비 체크리스트

- 자기소개 1분 — NHN 4년·게임→AI 서비스팀 이동·하네스 기반 풀스택 MVP라는 3막 구조로 30초마다 명확한 전환점이 있는지 최종 점검.
- 질문별 '1분 답변'을 3회 이상 타이머로 실측해 58~62초 범위에 들어오는지 리허설하고, 초과 시 중간 섹션부터 축약한다.
- 각 질문의 '피해야 할 약한 답변'을 실제로 말해 보며 스스로 차단 연습 — 특히 Q5에서 'AI가 대신 해 줬다'로 뭉개지 않도록 역할 분리 문장을 암기한다.
- 올리브영 기술 블로그 4편(MSA 데이터 연동, 무중단 OAuth2, SQS 데드락, Spring 트랜잭션 동기화)과 본인 경험의 접점을 질문별로 1개씩 매핑해 즉석 언급 가능하게 준비한다.
- 압박 질문(Reactive로 풀지 않은 이유·grace 30초 제약을 인프라에 요청하지 않은 이유·blocklist 리팩터링의 TCO·백엔드와 AI 웹툰 경험의 관련성)에 대한 방어 문장을 구두로 2회 이상 리허설한다.
- 수치·고유명사(11 Step, 447 테스트, 30초 grace, 15+12+3 예산, 199 plan·760 커밋, 토큰 75% 절감, 26.8s→13.1s)를 카드로 정리해 면접 직전 5분간 복기한다.
- 면접 말미 역질문 3~5개 준비 — 팀 온보딩·코드 리뷰/배포 게이트·커머스 도메인 이벤트 연동 현황·AI/에이전트 활용 여지·수습 3개월 기대치를 축으로 구성한다.
