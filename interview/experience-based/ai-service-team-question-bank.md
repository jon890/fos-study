# [초안] AI 서비스 개발팀 경험 기반 시니어 백엔드 면접 질문 은행

---

## 이 트랙의 경험 요약

- Spring Batch 11 Step 기반 Confluence → OpenSearch RAG 벡터 색인 파이프라인 (AsyncItemProcessor / CompositeItemProcessor / @JobScope / 재시작성) — 설계·운영 전 과정을 본인이 주도했고, 대용량 I/O 바운드 배치에서 청크 병렬화와 Step 단위 실패 격리를 실제로 돌려본 경험.
- gRPC OCR 서버 배포·스케일인 시 503 에러를 Envoy drain / supervisord stopwaitsecs / SIGTERM 핸들러 / preStop hook 예산을 NHN Cloud의 고정된 terminationGracePeriodSeconds 30초 제약 안에서 재배분하여 해결한 종료 시퀀스 설계 경험.
- 임베딩 메타데이터를 Blocklist(remove) → Allowlist(EmbeddingMetadataProvider)로 전환하며 OCP를 지키고, 전략 패턴을 DocumentType → Provider 맵 + Spring DI로 정착시켜 신규 소스 추가 시 EmbeddingService를 건드리지 않는 구조를 만든 리팩터링.
- Next.js 16 + Prisma 7 + Gemini @google/genai 기반 AI 웹툰 제작 도구 MVP를 12일 단독으로 6단계 파이프라인(소설→세계관→캐릭터→각색→글콘티→이미지)으로 구현하며 199 plan / 760 커밋을 달성, Claude Code 하네스 4인 에이전트 팀(planner/critic/executor/docs-verifier)을 설계·운영한 경험.
- Gemini pro→flash→lite fallback + 전역 Rate Limit Tracking(Map<string, number>) + Project 단위 Context Caching + Continuation 재주입으로 환각 차단을 '프롬프트 카피라이팅'이 아니라 '호출 구조 설계'로 풀어낸 AI 파이프라인 아키텍처 경험.
- 이력서/지원 문항 기준 지원 동기는 '대규모 커머스 트래픽 환경에서 캐시 정합성·이벤트 드리븐·대용량 색인·도메인 모델링 기술이 어떻게 작동하는지 직접 검증하고 싶다'이며, 1,600만 고객 규모의 올리브영 커머스플랫폼유닛이 본인 기술 스택과 직접 맞닿아 있음을 강조.

## 1분 자기소개 준비

- NHN에서 4년째 Java/Spring Boot 기반 백엔드 개발을 해 온 김병태입니다. 소셜 카지노 게임 팀에서 멀티모듈 MSA 슬롯 서비스 신규 게임 개발·성능 개선·아키텍처 재설계를 맡았고, 이후 AI 서비스 개발팀으로 이동해 Confluence → OpenSearch 벡터 색인 RAG 파이프라인을 Spring Batch로 처음부터 설계·구현했습니다.
- 대표 경험 세 가지를 꼽으면 — 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout + Hibernate PostCommitUpdateEventListener + StampedLock으로 해결한 동시성 설계, @TransactionalEventListener(AFTER_COMMIT) 기반 Kafka 비동기 + Dead Letter Store 재시도 + traceId 추적의 신뢰성 설계, 그리고 11 Step 분리 + AsyncItemProcessor 병렬 처리 + 커서 기반 재시작 가능 구조의 대용량 색인 파이프라인 설계입니다.
- 설계뿐 아니라 구조 개선에도 꾸준히 투자해왔습니다. 파편화된 스핀 비즈니스 로직을 AbstractPlayService + SpinOperationHandler 인터페이스 위임 구조로 통합했고, 447개 테스트 파일로 핵심 로직·AOP·Kafka·Redis 통합 테스트를 커버하는 안전망을 만들었습니다. Cursor Rules 20개 이상을 구축해 에이전트 단독으로 신규 게임 3종을 구현한 AI 도구 도입 경험도 있습니다.
- 최근에는 12일 단독으로 Next.js 16 + Prisma 7 + Gemini 기반 AI 웹툰 제작 도구 MVP를 6단계 파이프라인으로 구현하며 Claude Code 하네스 4인 에이전트 팀을 설계·운영해 199 plan / 760 커밋을 쳐냈습니다. 기능을 만드는 것에 그치지 않고 팀 전체의 개발 속도와 안정성을 동시에 끌어올리는 구조를 만드는 것을 지향합니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영 커머스플랫폼유닛이 1,600만 고객에게 '빠르고 안정적인 고객 경험'을 제공한다는 미션에 깊이 공감합니다. 제가 4년간 쌓아온 Spring Boot MSA / Kafka / Redis / JPA / 대용량 색인 스택이 상품·전시·주문 도메인에 직접 맞닿아 있어, 수습 3개월 안에 의미 있는 기여를 낼 수 있다고 판단해 지원했습니다.
- 기술 블로그의 'Cache-Aside + Kafka 하이브리드 도메인 연동' 글과 제가 구현한 'RabbitMQ Fanout + PostCommit 이벤트 리스너 기반 다중 서버 캐시 정합성' 설계는 문제 유형이 거의 동일합니다. '데이터 변경 빈도·라이프사이클 기준으로 Cache-Aside vs 이벤트 드리븐을 구분한다'는 팀 기조를 실무에서 이미 적용해본 경험이 있다고 말씀드릴 수 있습니다.
- '올영세일 중 무중단 OAuth2 전환' 글에 나오는 Feature Flag + Shadow Mode + Resilience4j + Jitter 패턴은 제가 해결한 '@TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + traceId 추적' 및 'gRPC OCR 503 Graceful Shutdown 예산 설계'와 같은 '신뢰성을 구조로 담보한다'는 동일한 철학을 공유합니다.
- Spring Batch 11 Step + AsyncItemProcessor + OpenSearch 벌크 색인으로 대용량 문서 증분 처리와 삭제 동기화를 직접 운영한 경험은, 커머스 상품 검색 인덱싱 도메인에도 그대로 적용 가능합니다. AI 도구를 '쓰는 수준'이 아니라 하네스 파이프라인과 스킬을 설계해 팀 개발 사이클을 단축한 경험은, 1,600만 고객 규모의 빠른 개발·높은 안정성을 동시에 추구해야 하는 환경에 바로 기여할 수 있는 자산이라고 생각합니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 지금까지 쌓은 기술이 '대규모 커머스 트래픽'이라는 실제 환경에서 어떻게 작동하는지 직접 검증하고 싶습니다. 게임·AI 서비스에서 다룬 캐시 정합성·이벤트 드리븐·대용량 색인 경험이 커머스의 상품·전시·주문 도메인에서 어떻게 구부러지는지 몸으로 부딪혀보고 싶다는 동기가 가장 큽니다.
- AI 서비스 팀에서 RAG 파이프라인을 처음부터 설계·운영하면서, 정작 그 AI가 결국 어떤 비즈니스 가치를 만드는지는 B2B 내부 도구라 체감하기 어려웠습니다. 올리브영처럼 고객 트래픽과 매출에 직접 연결되는 도메인에서 기술적 결정의 영향을 end-to-end로 보고 싶습니다.
- 4년간 동일 조직에서 슬롯 → AI 서비스로 도메인 전환을 해봤기 때문에, '조직 이동 후 빠르게 도메인을 흡수하는 방법'에 대한 감각이 있습니다. 지금이 커머스라는 새로운 도메인에서 한 단계 더 성장할 수 있는 적절한 시점이라고 판단했습니다.
- 팀 내 AI 도구 도입과 하네스 파이프라인 설계를 주도하며 '개인 생산성'을 넘어 '팀 생산성'을 설계하는 일에 가장 큰 재미를 느꼈습니다. 같은 고민을 더 큰 규모와 더 큰 도메인 복잡도에서 하고 싶어 이직을 결심했습니다.

### 왜 올리브영인가
- 1,600만 고객이라는 규모는 지금 제 기술 스택(Spring Boot MSA / Kafka / Redis / JPA / 대용량 색인)이 가장 의미 있게 작동할 수 있는 규모라고 봅니다. 기술 블로그의 'Cache-Aside + Kafka 하이브리드', '무중단 OAuth2 전환', 'SQS 데드락 분석' 등의 글을 보면 제가 실무에서 풀어온 문제 유형과 교집합이 매우 큽니다.
- 올영세일처럼 평시 대비 10배 트래픽이 정기적으로 발생하는 환경은 '안정성을 구조로 담보한다'는 제 일하는 방식과 잘 맞습니다. Feature Flag + Shadow Mode + Resilience4j 3단 보호 같은 패턴을 팀 차원에서 제도화해 왔다는 점이 특히 매력적입니다.
- 기술 블로그를 통해 의사결정의 '왜'를 외부에 공개·공유하는 문화가 있다는 것이 드러납니다. 저 역시 기술 결정의 배경과 트레이드오프를 ADR·문서로 남기는 습관이 있어, 올리브영의 문서 문화와 작업 방식이 잘 맞을 것이라고 생각합니다.
- 웰니스 카테고리는 상품 속성·전시 규칙·개인화 요구가 복잡해 도메인 모델링 난이도가 높다고 이해하고 있습니다. 제가 게임 슬롯에서 AbstractPlayService + SpinOperationHandler로 파편화된 로직을 통합한 경험이, 복잡한 커머스 도메인에도 그대로 적용 가능하다고 판단했습니다.

### 왜 이 역할에 맞는가
- 백엔드 개발자로서 '도메인 모델링 + ORM + 이벤트 드리븐 + 캐싱 + 대용량 검색'이라는 5개 축이 한 포지션에 모두 들어있는 기회는 드뭅니다. 커머스플랫폼유닛 웰니스개발팀의 담당 업무 목록이 제 4년간의 경험과 가장 높은 overlap을 보여, 가장 빠르게 기여할 수 있는 자리라고 판단했습니다.
- 상품 관리·전시 로직·검색 엔진 연동이라는 핵심 비즈니스 로직은 바로 제가 RAG 파이프라인에서 다룬 '증분 색인 + 삭제 동기화 + 메타데이터 Allowlist 전략'과 맞닿아 있습니다. 기술 도메인은 다르지만 패턴이 동일해 투입 후 러닝 커브가 짧을 것으로 보입니다.
- MSA 환경에서 서비스 간 동기/비동기 통신 경계를 직접 설계·운영해 본 경험이 있어, '도메인 데이터 연동 전략'이 주요 의제인 이 팀에서 제 경험을 바로 꺼내 쓸 수 있습니다. @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store 패턴은 팀이 이미 쓰고 있는 SQS 기반 알림톡 개선 주제와도 연결됩니다.
- Spring Boot 프로젝트 수행, Kafka 비동기 처리, 다양한 캐싱 전략, 대용량 트래픽 운영이라는 4개 우대 조건에 모두 해당합니다. 특히 '캐싱 전략을 단순 Redis 사용을 넘어 다중 서버 정합성까지 고민해본 경험'은 이 포지션이 기대하는 시니어급 역할과 직접 연결된다고 생각합니다.

## 메인 질문 1. Confluence → OpenSearch RAG 벡터 색인 배치를 Spring Batch 11 Step으로 설계했는데, 왜 하나의 거대한 Step이나 별도 스케줄러 배치가 아니라 굳이 11 Step으로 쪼갠 건가요? 설계 의도와 실제 운영에서 이 분리가 어떤 가치를 만들어냈는지 구체적으로 설명해주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 대용량 배치에서 '왜 Spring Batch인가 / 왜 Step 분리인가'를 의사결정 수준에서 이해하고 있는지 확인.
- 단순 기능 구현이 아니라 재시작성·실패 격리·Step 간 데이터 공유(@JobScope)의 트레이드오프를 인식하고 있는지 검증.
- 커머스 상품 색인 파이프라인 설계 경험으로 이어질 수 있는 시니어급 설계 사고인지 평가.

### 실제 경험 기반 답변 포인트

- 배치 잡은 크게 3단계 — 초기화/컬렉트 / 페이지·댓글 색인 / 삭제 동기화 / 인덱스 리프레시 — 각 단계가 '실패 시 영향 범위'가 완전히 다르기 때문에 한 Step에 묶으면 재시작 비용이 폭발합니다.
- 핵심 색인 Step(Reader → CompositeItemProcessor → AsyncItemProcessor → AsyncItemWriter)은 I/O 바운드라 병렬화가 필수이지만, 앞쪽 스페이스 정보 수집은 한 번만 돌면 되므로 Tasklet으로 처리해 리소스를 낭비하지 않습니다.
- Step 간 데이터 공유는 JobExecutionContext 대신 @JobScope 빈 ConfluenceJobDataHolder로 분리 — JobExecutionContext는 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT에 직렬화되기 때문에 수천 개 페이지 ID를 넣기에는 부적절. @JobScope는 재시작 시 새 JobExecution과 함께 초기화되므로 allowStartIfComplete(true)로 상태 로더 Step을 반드시 재실행시켜 NPE 방지.
- 실제 운영에서의 가치 — 댓글 Step이 실패해도 페이지 색인 결과는 살아있고, 재시작 시 실패한 Step부터 이어서 돌면 됨. 임베딩 API 장애가 났을 때 이 구조가 없었다면 전체 재실행 비용이 수 배로 증가했을 것.

### 1분 답변 구조

- 한 마디로는 '실패 격리'와 '재시작 비용 최소화'입니다. 수집/색인/삭제/리프레시는 각각 외부 의존성이 달라 실패 확률과 재실행 비용이 다릅니다.
- 예: 임베딩 API 장애로 페이지 색인 Step이 실패해도, 앞서 돌린 스페이스 정보 초기화나 페이지 ID 수집은 이미 끝나 있고 뒤의 삭제 동기화도 별개 경로라 건드리지 않아도 됩니다. 실패 지점부터 이어서 돌 수 있습니다.
- 또한 Step 간 도메인 데이터는 JobExecutionContext에 넣지 않고 @JobScope 빈(ConfluenceJobDataHolder)으로 옮겨, 청크 커밋마다 DB에 직렬화되는 부하를 피했습니다. 재시작 시 새 JobExecution에서 빈이 비는 문제는 allowStartIfComplete(true)로 상태 로더 Step을 반드시 재실행시켜 해결했습니다.
- 결론적으로 '기능 단위'가 아니라 '실패 시 영향 경계'를 기준으로 Step을 나눈 게 제 설계의 핵심입니다.

### 압박 질문 방어 포인트

- '그럼 Step이 너무 많아 관리 비용이 늘지 않나요?' → 각 Step이 단일 책임을 가져 변경 파급이 좁고, Job 실행 이력이 DB에 쌓여 오히려 관찰 가능성이 높아짐. 11 Step은 도메인 요구(수집·보강·색인·삭제 동기화)의 자연스러운 분할이라 과도한 분해가 아닙니다.
- '@JobScope는 재시작 시 NPE가 발생한다면서 굳이 쓸 이유가 있나?' → allowStartIfComplete(true)로 NPE를 예방할 수 있고, JobExecutionContext의 직렬화 비용을 피할 수 있음. 도메인 데이터 vs 재시작 커서 상태를 저장소 관점에서 분리하는 게 원칙.

### 피해야 할 약한 답변

- 'Step Batch는 원래 그렇게 쓰는 거라서요' 같은 프레임워크 기본값 복창.
- 'Step을 나누면 코드가 깔끔해져서요' 같이 실패 격리/재시작성 같은 운영 가치를 언급하지 못하는 답.

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor + AsyncItemWriter 조합에서 병렬 처리 중 특정 아이템이 실패하면 청크 전체가 롤백되나요, 아니면 해당 Future만 실패하나요? 스킵/재시도 정책은 어떻게 설계했나요?

**F1-2.** CompositeItemProcessor 체이닝(ChangeFilter → Enrichment → BodyConvert → Embedding)에서 ChangeFilter가 null을 반환해 스킵된 아이템은 이후 Processor를 건너뛰는데, 이 동작이 AsyncItemProcessor로 감쌀 때도 동일하게 동작하나요?

**F1-3.** JobExecutionContext vs @JobScope 빈의 트레이드오프를 다시 설명해 주시고, 만약 수천이 아니라 수십만 단위 페이지 ID를 다뤄야 한다면 @JobScope 빈도 메모리 압박이 클 텐데 어떻게 풀 수 있을까요?

**F1-4.** 재시작 시 allowStartIfComplete(true)를 켠 Step이 side-effect가 있는 Step(예: 외부 API 호출, DB insert)이면 중복 실행이 문제가 되지 않나요? 멱등성은 어떻게 보장했나요?

**F1-5.** 커머스 상품 색인처럼 문서 수가 Confluence보다 훨씬 많고 변경 빈도가 훨씬 높은 환경이라면, 지금 구조를 어디부터 바꿔야 한다고 보시나요?

---

## 메인 질문 2. gRPC OCR 서버 배포·스케일인 시 503이 클러스터 단위로 발생하는 문제를 해결하셨다고 했는데, 원인 분석부터 수정 범위 결정까지의 사고 과정을 시간 순서대로 설명해주세요. 특히 NHN Cloud의 terminationGracePeriodSeconds 30초 고정 제약을 어떻게 예산화했는지가 궁금합니다.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 장애 증상 → 근본 원인 역추적 능력(Envoy drain, SIGTERM, supervisord stopwaitsecs 등)을 검증.
- '고정된 인프라 제약' 안에서 트레이드오프를 예산 단위로 쪼개 배분하는 시니어급 설계 감각 확인.
- 커머스의 배포/스케일인 상황에서 유사한 장애를 만났을 때 디버깅·설계 품질을 가늠.

### 실제 경험 기반 답변 포인트

- 증상: 배포·스케일인 시 30~60초 단위로 503 'upstream connect error, reset reason: connection failure, transport failure reason: delayed connect error: 111(ECONNREFUSED)', server: envoy 헤더가 붙어 Envoy는 살아있는데 upstream:50051에 연결이 거부되는 패턴이었음.
- 구조: 클라이언트 → Envoy(:5000) → gRPC 서버(:50051). preStop이 Envoy drain_listeners + sleep 20을 돌렸지만, sleep이 끝나고 SIGTERM이 전달되면 gRPC 서버가 SIGTERM 핸들러 없이 즉시 죽고, 그 사이 sleep 중 Envoy가 50051로 라우팅을 시도해 ECONNREFUSED가 발생.
- 근본 원인 두 가지 — (1) server_grpc_general_OCR.py의 serve()가 wait_for_termination()만 있고 SIGTERM 핸들러가 없어 graceful shutdown 미구현, (2) supervisord [program:grpc-server]에 stopwaitsecs가 없어 기본값 10초만에 SIGKILL을 날림.
- NCS가 terminationGracePeriodSeconds를 30초로 고정 → 전체 종료는 30초 안에 끝나야 함. preStop sleep 20 + grace 12 = 32초로 초과. preStop sleep을 15로 줄이고, gRPC server.stop(grace=12)로 in-flight 처리 대기, supervisord stopwaitsecs=17(12+여유 5)로 설정해 15+12+3=30초 예산 안에 맞춤. 핵심은 '시퀀스 내 각 단계가 소모할 수 있는 시간'을 예산 단위로 쪼갠 것.

### 1분 답변 구조

- 먼저 에러 응답의 server:envoy 헤더와 111 ECONNREFUSED로 'Envoy 자체가 아니라 upstream 포트 50051이 먼저 닫힌다'는 걸 확정했습니다. 이 시점에 '왜 Envoy drain 중에 gRPC가 먼저 죽나'가 핵심 질문이 됐습니다.
- 코드를 보니 gRPC 서버에 SIGTERM 핸들러 자체가 없어서 SIGTERM이 오면 즉시 프로세스가 종료됐고, supervisord도 stopwaitsecs 기본값 10초 때문에 핸들러를 추가해도 SIGKILL로 끊길 구조였습니다.
- NCS는 terminationGracePeriodSeconds가 30초 고정이라 전체 시퀀스를 30초 예산 안에 넣어야 했습니다. preStop sleep을 20→15로 줄이고, gRPC server.stop(grace=12)로 in-flight RPC 처리 대기, supervisord stopwaitsecs=17로 맞춰 15+12+여유3=30초 안에 정확히 수렴하게 설계했습니다.
- 결과는 배포·스케일인 503이 사라졌고, 배운 건 '고정된 인프라 제약 앞에서는 각 단계를 예산 단위로 쪼개 배분해야 한다'는 것이었습니다.

### 압박 질문 방어 포인트

- 'preStop sleep을 15로 줄이면 Envoy drain이 부족하지 않나?' → 실제 클러스터의 connection 라이프사이클과 Envoy 설정을 보고 판단한 값. drain_listeners는 신규 연결만 막고 in-flight는 유지하므로, in-flight는 하류 gRPC grace에서 흡수됨. 관찰 결과 503 없음으로 수렴.
- '왜 terminationGracePeriodSeconds를 늘리지 않았나?' → NCS가 30초 고정이라 API 스펙에서 아예 바꿀 수 없는 환경 제약. 주어진 제약 안에서 예산 재분배가 유일한 해결책이었음.

### 피해야 할 약한 답변

- 'SIGTERM 핸들러를 추가해서 해결했습니다' 수준의 1-step 답 — preStop, supervisord, 인프라 제약까지 함께 보지 않은 답.
- 'K8s graceful shutdown을 적용했습니다' 같이 '책에서 본 용어'로 떠넘기고 실제 예산 계산·환경 제약을 설명하지 못하는 답.

### 꼬리 질문 5개

**F2-1.** server.stop(grace=12)의 grace는 정확히 어떤 의미인가요? 새 RPC는 거부되고 기존 RPC는 유지되는 동작이 gRPC Python SDK 내부적으로 어떻게 구현되어 있나요?

**F2-2.** supervisord stopwaitsecs를 12가 아니라 17로 잡은 이유와, 만약 grace 대기 중 SIGKILL이 들어오면 in-flight RPC는 어떻게 되나요? 클라이언트는 어떤 에러를 보게 되나요?

**F2-3.** preStop sleep 15초가 Envoy drain이 충분한지 어떻게 검증했나요? drain_listeners는 실제로 어떤 커넥션을 종료하고 어떤 커넥션을 유지하나요?

**F2-4.** 같은 문제를 커머스 상품 API처럼 HTTP 기반 서비스에서 겪는다면 접근이 어떻게 달라져야 할까요? Spring Boot의 server.shutdown=graceful 설정과 비교해서 설명해 주세요.

**F2-5.** NCS 고정 제약이 없어 terminationGracePeriodSeconds를 자유롭게 쓸 수 있다면, 같은 문제를 어떤 예산으로 재설계하시겠어요? 그 결정에 영향을 미치는 가장 큰 변수는 무엇인가요?

---

## 메인 질문 3. 임베딩 메타데이터를 Blocklist(remove) → Allowlist(EmbeddingMetadataProvider) 방식으로 전환하며 전략 패턴을 적용하셨는데, '그냥 if-else 분기로도 충분하지 않나?'라는 반론에 어떻게 답하시겠어요? 그리고 이 설계가 OCP를 정말 지켰다고 어떻게 입증할 수 있나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 전략 패턴·OCP 같은 교과서 용어를 실무 리팩터링에서 '왜 여기서 써야 했는가' 관점에서 풀어낼 수 있는지 검증.
- 단순 코드 품질이 아니라 '확장 포인트 설계' 수준의 시니어 판단을 하는지 확인.
- 커머스의 복잡한 상품·전시 도메인에서 신규 요구 수용 전략을 같은 원칙으로 풀 수 있는지 평가.

### 실제 경험 기반 답변 포인트

- Before 문제 — EmbeddingService 한 메서드에 14개 remove() + if (documentType == TASK) 분기가 누적되어, 새 DocumentType이 생길 때마다 EmbeddingService를 직접 수정해야 함. 게다가 '어떤 필드가 임베딩에 포함되나?'를 blocklist로 역산해야 하는 가독성 문제까지 발생.
- Allowlist 전환의 본질은 '관리 단위'를 바꾼 것 — 제거할 필드가 아니라 포함할 필드를 명시. EmbeddingMetadataProvider.getSupportedDocumentTypes() + provide(Document)로 구현체가 자기 책임 범위를 스스로 선언.
- OCP 입증 — Spring DI가 List<EmbeddingMetadataProvider>로 @Component 구현체를 자동 수집해 DocumentType → Provider 맵을 빌드. 신규 소스(예: Jira)를 추가할 때 EmbeddingService·Config·다른 Provider 중 어느 것도 건드리지 않고 JiraEmbeddingMetadataProvider 클래스 하나만 추가하면 맵에 자동 등록 — 이게 OCP의 운영적 증거.
- 계층 구조(AbstractEmbeddingMetadataProvider → AbstractCollabToolEmbeddingMetadataProvider / AbstractConfluenceEmbeddingMetadataProvider → 구체 구현)로 공통 필드(putIfNotNull, putFormattedDatetime)는 한 번만 정의. Confluence 스페이스별 title/subject 폴백처럼 '소스 계열 내 미세한 차이'는 계열 추상 클래스에서 흡수해, 구현체는 자기 고유 필드만 책임.

### 1분 답변 구조

- if-else로도 동작은 하지만 '관리 단위'가 틀립니다. blocklist는 '빼야 할 것'을 관리해서 새 필드가 생길 때마다 모든 분기에 remove를 추가해야 하고, '지금 임베딩에 어떤 필드가 들어가나?'를 역산해야 합니다.
- Allowlist로 뒤집으면 '포함할 것'을 구현체가 선언합니다. EmbeddingMetadataProvider의 getSupportedDocumentTypes + provide만 구현하면 되고, Spring이 List<Provider>로 자동 주입돼 EmbeddingService는 맵 조회 → 위임만 합니다.
- OCP 입증은 '신규 소스 추가 시 수정해야 하는 파일 수'로 본다면 명확합니다. Jira가 생긴다면 JiraEmbeddingMetadataProvider 하나 추가로 끝이고, EmbeddingService·Config·다른 Provider를 건드릴 필요가 없습니다. 이게 운영에서의 OCP 증거입니다.
- 추가로 공통 필드는 계열 추상 클래스(AbstractCollabTool·AbstractConfluence)에서 흡수해, 구현체 중복도 제거했습니다.

### 압박 질문 방어 포인트

- '확장 포인트가 없으면 전략 패턴은 과잉 설계 아닌가?' → 지금 소스가 Task/Wiki/Drive/Confluence로 이미 4종이고, 신규 스페이스별 메타데이터 차이까지 고려하면 확장 포인트가 이미 실재. 미래가 아니라 현재 도메인에 근거한 추상화.
- 'Allowlist도 결국 필드가 늘면 각 구현체를 고쳐야 하지 않나?' → 맞음. 그러나 수정 범위가 자기 소스 구현체로 국한되어 blast radius가 작고, 공통 필드는 계열 추상 클래스에서 한 번만 관리하므로 변경 비용이 일정함.

### 피해야 할 약한 답변

- '전략 패턴이 더 깔끔해서요' 같은 감각적 답. OCP 증명·구체 변경 비용 비교 없이 용어만 반복하는 답.
- 'cloneMetadata(), getMetadataValue() 같은 지저분한 메서드가 사라져서요' 같이 표면적 개선만 언급하는 답.

### 꼬리 질문 5개

**F3-1.** @StepScope 빈 충돌로 NoUniqueBeanDefinitionException이 났다고 하셨는데, 정확히 어떤 상황에서 발생했고 @Qualifier + @Component @StepScope 전역 등록 조합으로 어떻게 해결했는지 설명해 주세요.

**F3-2.** EmbeddingMetadataProvider는 인터페이스인데, provide(Document)의 반환 타입이 Map<String, Object>입니다. 타입 안전성을 포기한 이유와, 만약 DocumentMetadata 같은 별도 VO로 강타입화한다면 어떤 장단점이 생길까요?

**F3-3.** Confluence의 title/subject 폴백처럼 '같은 계열인데 스페이스별로만 다른 규칙'이 앞으로 더 많아지면 AbstractConfluenceEmbeddingMetadataProvider가 비대해질 위험이 있습니다. 어떻게 막으시겠어요?

**F3-4.** 커머스 상품·전시처럼 메타데이터 필드가 수십 개 이상이고 카테고리별 규칙이 복잡한 도메인이라면, 지금 구조를 그대로 쓰시겠어요, 아니면 어떻게 바꾸시겠어요?

**F3-5.** Allowlist 전환으로 과거에 blocklist였던 필드가 누락될 수 있습니다. 리팩터링 당시 회귀를 어떻게 방지했나요? 테스트 전략이 궁금합니다.

---

## 메인 질문 4. 12일 단독으로 Next.js 16 + Prisma 7 + Gemini 기반 AI 웹툰 제작 도구 MVP를 199 plan / 760 커밋 규모로 만들면서 Claude Code 하네스 4인 에이전트 팀을 설계·운영하셨는데, 이 파이프라인을 '툴 사용'이 아니라 '아키텍처'라고 부를 수 있는 이유를 설명해 주세요. 그리고 이 경험이 커머스 백엔드 개발자 역할에 어떻게 이어집니까?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI 도구를 단순 코드 자동 완성이 아니라 파이프라인/에이전트 팀 수준으로 설계한 역량을 검증.
- 대규모 커밋·plan 수에 휘둘리지 않고 '구조적 설계 원칙'을 끌어낼 수 있는지 확인.
- 시니어 백엔드 관점에서 AI 협업 경험을 도메인 업무로 연결 짓는 언어 능력 평가.

### 실제 경험 기반 답변 포인트

- 하네스 진화 5단계 — (1) vibe 코딩 단일 세션, (2) /planning으로 스펙 우선(Opus 기반 8단계 논의 → tasks/planNNN-*/index.json + phase 파일), (3) /plan-and-build로 phase 자기완결 + run-phases.py로 재시작 가능, (4) /build-with-teams로 critic(계획-코드 대조 APPROVE/REVISE) + docs-verifier(ADR/data-schema 정합성) 게이트 추가, (5) /integrate-ux로 디자이너 vibe PR을 컨벤션으로 흡수.
- '아키텍처'라 부를 수 있는 이유 — 역할 분리(planner/critic/executor/docs-verifier)로 자기 계획을 자기가 검증하지 않는 구조, task 파일이 git에 영속되어 세션이 끊겨도 재시작 가능, docs-first로 코드 변경 전에 ADR/data-schema 업데이트 → 다음 세션의 컨텍스트 부패 방지. 모두 분산 시스템 설계 원칙(역할 분리·상태 영속화·eventual consistency·idempotency)의 재적용.
- 기술 결정의 깊이 — Gemini pro→flash→lite fallback + 전역 Rate Limit Tracking Map으로 429 모델을 일정 시간 스킵, 원작 소설은 Project 단위 Context Cache로 5단계 호출이 공유, Continuation에 Grounding 블록 재주입으로 환각 차단(환각은 프롬프트 카피라이팅이 아니라 호출 구조 설계 문제). Zod 4 z.toJSONSchema()로 Gemini Structured Output과 런타임 검증을 단일 소스로 통합.
- 커머스 연결 — 도메인은 다르지만 '재시작 가능성·실패 격리·전역 상태(Rate Limit)·역할 분리·문서로서의 컨텍스트'는 Spring Batch 색인 파이프라인, 주문-배송 이벤트 오케스트레이션, 팀 개발 프로세스 설계에 그대로 이식 가능. 게다가 하네스 자체를 팀에 도입해 개발 사이클을 단축한 경험은 1,600만 고객 규모에서 기능 안정성과 개발 속도를 동시에 끌어올리는 데 직결됨.

### 1분 답변 구조

- 핵심은 '역할이 분리된 에이전트 팀을 태스크 파일 + 재시작 가능한 하네스 위에 올렸다'는 점입니다. planner가 tasks/planNNN-*/index.json + phase 파일로 스펙을 고정하고, critic이 계획-코드 대조로 APPROVE/REVISE, executor가 실행, docs-verifier가 ADR·data-schema 정합성을 지킵니다.
- 이 구조는 분산 시스템 원칙의 재적용입니다. task 파일은 git에 영속된 상태, phase는 자기완결적 단위, critic/docs-verifier는 게이트, Rate Limit Tracking은 전역 상태 — 어느 한 세션이 죽어도 다른 세션이 이어받을 수 있습니다.
- Gemini pro→flash→lite fallback + Context Cache + Continuation grounding 재주입처럼 모델·캐시·호출 구조 수준의 결정도 직접 설계했고, 덕분에 환각과 비용 폭증을 동시에 눌렀습니다.
- 커머스 백엔드로 이어지면 Spring Batch 색인, 이벤트 오케스트레이션, 팀 개발 프로세스 설계 어디서든 같은 원칙이 적용됩니다. AI를 쓰는 수준이 아니라 AI 팀 파이프라인을 설계·운영하는 수준의 생산성으로 기여할 수 있습니다.

### 압박 질문 방어 포인트

- '12일에 760 커밋이면 품질 검증이 되나요?' → critic과 docs-verifier가 매 phase마다 게이트를 치고, ADR 134개가 결정의 근거로 남아 있음. 실제로 ADR이 1,581줄로 비대해졌을 때 docs-verifier가 '에이전트 컨텍스트 효율 관점에서 길다'고 지적해 700줄로 줄인 사례처럼 검증 루프가 작동함.
- '결국 vibe 코딩 아닌가?' → 초기엔 그랬지만 /planning 이후부터 '결정의 80%는 task 파일에 박혀 있어야 한다'는 원칙으로 전환. 결정이 안 된 부분이 실행 중에 터진다는 걸 반복적으로 경험하며 설계가 공고해짐.

### 피해야 할 약한 답변

- 'Claude Code를 잘 써서 많이 만들었어요' — 숫자만 자랑하고 구조를 설명하지 못하는 답.
- 'AI가 대신 코드를 짜 줬어요'처럼 본인의 의사결정·아키텍처 역할을 덜어내는 답.

### 꼬리 질문 5개

**F4-1.** critic이 REVISE 판정을 내리는 구체적 사례 하나를 들어주실 수 있나요? 그 결정이 코드 품질에 어떻게 기여했나요?

**F4-2.** Gemini pro→flash→lite fallback 시 grounding 준수력이 약해진다고 하셨는데, 지금은 어떻게 대응하고 있고, 만약 더 시간이 있었다면 어떤 구조로 풀었을까요?

**F4-3.** Continuation에 Grounding 블록을 재주입하는 방식은 토큰 비용을 늘립니다. Context Cache와의 비용 트레이드오프를 어떻게 계산했나요? 손익분기점은 어디에 있었나요?

**F4-4.** Zod 4 z.toJSONSchema()로 단일 소스를 만들었지만, Repository 레이어에서는 Prisma 고유 타입(Partial·DbNull·connect/create/disconnect)을 쓰는 게 더 깔끔했다고 하셨습니다. '단일 소스' 원칙을 언제 깨고 언제 유지해야 한다고 보시나요?

**F4-5.** 이 하네스 경험을 올리브영의 기존 팀에 도입한다면, 가장 먼저 어떤 작업부터 하시겠어요? 기존 팀이 쓰는 툴·문서·프로세스와 충돌할 수 있는 지점은 어디라고 예상하시나요?

---

## 메인 질문 5. 본인 이력서의 'RabbitMQ Fanout + PostCommitUpdateEventListener + StampedLock 기반 다중 서버 캐시 정합성' 설계와, 올리브영 기술 블로그의 'Cache-Aside + Kafka Event-Driven 하이브리드 도메인 데이터 연동' 글을 비교해서, 두 설계의 공통점과 본질적인 차이를 설명해 주세요. 올리브영 팀에 합류했을 때 본인 경험을 어디에 어떻게 접목하시겠습니까?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 지원사가 공개한 아키텍처를 이해하고, 본인 경험을 '구조 수준'에서 대응시킬 수 있는지 검증.
- 단순히 '저도 비슷한 걸 해봤습니다'가 아니라, 공통 원리와 차이를 언어화할 수 있는 시니어급 분석력을 확인.
- 합류 후 즉시 기여할 수 있는 구체적 영역을 본인 스스로 정의할 수 있는지 평가.

### 실제 경험 기반 답변 포인트

- 공통점 — 둘 다 '변경 빈도·라이프사이클 기준으로 연동 방식을 차별화'하는 접근. 올리브영은 변경이 적은 데이터는 Cache-Aside, 실시간 이벤트 데이터는 Kafka 이벤트 + Redis Key만 캐싱 + 선택적 API 호출. 제 설계도 정적 설정 데이터는 인메모리 캐시, 변경은 RabbitMQ Fanout으로 다중 서버에 브로드캐스트해 선택적 갱신 — 데이터 분류 원칙이 동일.
- 본질적 차이 — (1) 캐시 저장 위치: 올리브영은 Redis(외부), 제 설계는 애플리케이션 인메모리(로컬). 인메모리는 DB 부하를 더 줄이지만 다중 서버 정합성 문제가 커져 Fanout 브로드캐스트 + StampedLock writeLock/tryReadLock 2.5초 타임아웃으로 갱신 중 읽기 경합을 제어. (2) 이벤트 트리거: 올리브영은 Kafka producer를 애플리케이션이 명시적 발행, 제 설계는 Hibernate PostCommitUpdateEventListener로 엔티티 커밋 훅에서 자동 발행 — 비즈니스 코드 침투가 없음. (3) 실패 복구: Kafka 비동기 경로는 @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store(REQUIRES_NEW 별도 트랜잭션 DB 저장) + 스케줄러 재시도 + traceId 추적까지 결합.
- 합류 후 접목 포인트 — (1) 현재 블로그 구조에서 Cache-Aside 대상 데이터 중 '변경은 드물지만 동시 접근이 많은 데이터'가 있으면 인메모리 캐시 + 이벤트 기반 선택 갱신 옵션을 제시할 수 있음. (2) Kafka consumer에서 이벤트 처리 실패가 현재 어떻게 복구되는지 확인 후, Dead Letter Store + traceId 추적 패턴을 도입 제안 가능. (3) Resilience4j 3단 보호와 제 Dead Letter Store는 철학이 같으므로, 비동기 쓰기 경로에도 같은 수준의 신뢰성을 확장 가능.
- 유의할 점 — 1,600만 고객 / 올영세일 10배 트래픽 환경이라 인메모리 캐시는 정합성보다 메모리/인스턴스 수 제약에서 더 신중해야 함. 따라서 '내 경험을 그대로 이식'하는 게 아니라 '원리를 공유하는 구조'로 접목하는 게 옳음.

### 1분 답변 구조

- 공통점은 '변경 빈도·라이프사이클에 따라 연동 방식을 나눈다'는 원칙입니다. 올리브영은 Cache-Aside와 Kafka + Redis Key + 선택적 API 호출, 제 설계는 정적 데이터 인메모리 캐시와 RabbitMQ Fanout 브로드캐스트 + 선택적 갱신 — 원리가 같습니다.
- 본질적 차이는 세 가지입니다. 캐시 위치가 Redis vs 인메모리, 이벤트 트리거가 명시적 producer vs Hibernate PostCommit 훅(비즈니스 코드 비침투), 실패 복구가 @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + traceId까지 결합되어 있다는 점입니다.
- 합류 후 접목은 원리 공유 → 구조 제안 순서로 하겠습니다. 인메모리 캐시를 그대로 이식하진 않되, '변경 드물고 동시 접근 많은 데이터'에서 옵션으로 제시하고, Kafka 쓰기 경로에 Dead Letter Store + traceId 추적을 넣어 현재 Resilience4j 3단 보호와 동일한 수준의 신뢰성을 비동기 경로에도 확장할 수 있습니다.
- 1,600만 고객·10배 피크 환경이라 '인메모리'는 메모리·인스턴스 수 제약에서 신중해야 한다는 점을 인지하고, 원리를 공유하는 구조로 접근하겠습니다.

### 압박 질문 방어 포인트

- '다중 서버 인메모리 캐시는 Redis만큼 검증되지 않은 패턴 아닌가?' → 정합성 리스크가 크다는 건 사실. 그래서 Fanout 브로드캐스트 + StampedLock writeLock으로 갱신 중 읽기 차단, tryReadLock 2.5초 타임아웃으로 데드락 방지까지 설계. 다만 모든 데이터에 쓰는 게 아니라 '정적 설정 데이터'에 국한한 선택.
- '결국 올리브영 블로그 글을 읽고 맞추는 것 아닌가?' → 블로그를 읽기 전부터 제가 풀었던 문제 유형이 동일. 블로그를 보고 '용어가 다를 뿐 같은 고민을 팀이 한다'는 걸 확인했고, 그래서 이 팀에 기여할 수 있다고 판단해 지원했음.

### 피해야 할 약한 답변

- '올리브영 블로그에서 본 Cache-Aside + Kafka와 제 RabbitMQ 경험이 비슷합니다' 수준의 표면적 매칭.
- '저도 캐싱 해봤고 Kafka도 해봤습니다'처럼 공통점·차이를 구분하지 않는 답.

### 꼬리 질문 5개

**F5-1.** StampedLock의 writeLock/tryReadLock을 선택한 이유를 ReentrantReadWriteLock이나 ReadWriteLock과 비교해 설명해 주세요. 2.5초 타임아웃은 어떻게 산정했나요?

**F5-2.** Hibernate PostCommitUpdateEventListener를 쓰면 비즈니스 코드 침투가 없는 반면, '엔티티 변경'이라는 저수준 이벤트를 '도메인 이벤트'로 끌어올리는 데 한계가 있습니다. 커머스 도메인에서 이 한계가 문제가 되는 시나리오를 예로 들어주세요.

**F5-3.** @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store 패턴에서, Kafka 발행이 AFTER_COMMIT 시점에 실패하면 원 트랜잭션은 이미 커밋된 상태입니다. 이 불일치는 어떻게 허용 가능한 설계로 만드시나요?

**F5-4.** 올영세일처럼 10배 피크 트래픽에서 Cache-Aside + 선택적 API 호출 구조가 오히려 '선택적 호출이 집중되는 순간'에 취약할 수 있습니다. 이런 thundering herd 시나리오는 어떻게 방어하시겠어요?

**F5-5.** 본인이 설계한 RabbitMQ Fanout 구조와 Kafka 기반 구조가 혼재한 환경에서 팀이 '하나로 통일하자'고 한다면, 어느 쪽을 권하시겠어요? 결정 기준은 무엇인가요?

---

## 최종 준비 체크리스트

- 자기소개 1분 버전과 올리브영 fit 버전을 각각 한 번씩 소리 내어 리허설하고, 두 버전 모두 60~90초 안에 들어오는지 녹음 체크.
- 5개 메인 질문에 대해 'oneMinuteAnswer' 4~5줄 구조를 그대로 말로 재현할 수 있는지 확인하고, 막혔다면 answerPoints의 구체 수치(11 Step / 30초 예산 / 199 plan·760 커밋 / 14개 remove 등)를 다시 암기.
- 올리브영 기술 블로그 4개 글(MSA 데이터 연동 / 무중단 OAuth2 전환 / SQS 데드락 / Spring 트랜잭션 동기화)의 핵심 결론 한 줄씩 정리하고, 각 글과 내 경험의 접점을 1문장씩 연결해 말하기 연습.
- followUps 총 25개를 '답할 수 있음 / 보강 필요 / 모름' 3단계로 셀프 체크하고, 보강 필요 항목은 근거 코드·ADR·지표를 하루 1~2개씩 복습 계획으로 배분.
- pressureDefense 항목을 기준으로 '반론이 들어왔을 때 흔들리지 않는 문장'을 미리 말로 준비하고, 특히 '과잉 설계 아닌가 / 다른 기술로도 되지 않나' 계열 압박에 2문장 이내로 되받아치는 대응 스크립트를 확정.
- 이력서 2번·3번·4번 문항의 수치(4년, 447개 테스트, Cursor Rules 20개+, 신규 게임 3종, 199 plan, 760 커밋, 12일, terminationGracePeriodSeconds 30초 등)를 수치만 따로 뽑아 플래시카드로 만들고 면접 전날 최종 점검.
