# [초안] AI 서비스 개발팀 경험 기반 시니어 백엔드 인터뷰 질문 뱅크 — RAG 배치·Graceful Shutdown·전략 패턴·하네스 파이프라인

---

## 이 트랙의 경험 요약

- NHN AI 서비스 개발팀에서 수행한 4가지 대표 경험(Spring Batch 11-Step RAG 파이프라인, gRPC OCR 503 Graceful Shutdown, EmbeddingMetadataProvider 전략 패턴, 12일 단독 AI 웹툰 MVP)을 시니어 Java 백엔드 면접 관점에서 재구성한 질문 뱅크입니다.
- 각 질문은 단순 기능 설명이 아니라 설계 의도·트레이드오프·실패 격리·운영 신뢰성·확장성 관점의 답변을 요구합니다. CJ 올리브영 커머스플랫폼유닛이 강조하는 MSA·Kafka·Redis 캐시·JPA·대용량 트래픽 키워드와 의도적으로 매핑됩니다.
- 특히 AI/에이전트 경험은 '툴 사용자'가 아닌 '파이프라인 아키텍트' 수준임을 드러내도록 설계했습니다. Gemini pro→flash→lite fallback, 전역 Rate Limit Tracking, Project 단위 Context Caching, planner/critic/executor/docs-verifier 4인 에이전트 팀 조율 등 운영 수준의 설계 결정을 면접에서 풀어낼 수 있는 구조입니다.
- 면접 압박 상황에서의 방어 라인과 약한 답변 회피 가이드, 5단계 꼬리 질문까지 포함해 한 질문당 약 8~10분 분량의 심층 대화를 시뮬레이션할 수 있습니다.

## 1분 자기소개 준비

- 안녕하세요. NHN에서 4년째 Spring Boot 기반 멀티모듈 MSA 환경에서 백엔드를 개발하고 있는 김병태입니다.
- 처음 3년은 소셜 카지노 슬롯 게임 팀에서 신규 게임 개발과 성능·아키텍처 재설계를 담당했고, 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout + StampedLock으로 해결하고 핵심 API를 동기/비동기로 분리해 Kafka @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + 스케줄러 재시도 구조로 신뢰성을 확보한 경험이 있습니다.
- 이후 AI 서비스 개발팀으로 이동해 사내 RAG를 위한 Confluence → OpenSearch 벡터 색인 Spring Batch 파이프라인을 11개 Step으로 처음부터 설계·운영했고, AsyncItemProcessor를 활용한 I/O 병렬화와 @JobScope 인메모리 홀더 설계로 처리 속도와 재시작 안정성을 함께 확보했습니다.
- 최근에는 12일 동안 Next.js 16 + Prisma 7 + Gemini 기반 AI 웹툰 제작 도구 MVP를 단독으로 풀스택 구현하며 Claude Code 하네스 위에서 planner/critic/executor/docs-verifier 4인 에이전트 팀을 조율해 199 plan, 760 커밋을 처리한 경험이 있습니다. 백엔드 신뢰성 설계와 AI 시대 협업 구조 설계 양쪽에 자신 있는 개발자입니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영 커머스플랫폼유닛의 핵심 키워드인 MSA·Kafka·Redis Cache-Aside·JPA·대용량 트래픽이 제가 NHN에서 4년간 실제로 다뤄온 스택과 정확히 일치합니다.
- 특히 다중 서버 환경의 인메모리 캐시 정합성을 RabbitMQ Fanout으로 풀고, Cache-Aside의 한계를 갱신 중 동시성·확장 가능 구조 관점에서 직접 경험한 점이 1,600만 고객 트래픽 환경의 상품·전시 도메인 캐싱 전략에 그대로 활용 가능하다고 생각합니다.
- Kafka 이벤트 드리븐 설계에서 @TransactionalEventListener(AFTER_COMMIT) 기반 발행, 트랜잭션 경계와 Dead Letter Store + 스케줄러 재시도, traceId 기반 실패 추적까지 직접 구현했기 때문에, 올리브영의 도메인 간 데이터 연동 전략(Cache-Aside + Kafka 하이브리드)에 빠르게 합류할 수 있습니다.
- Spring Batch 기반 대용량 색인 파이프라인 설계 경험은 커머스 상품 검색·전시 색인 도메인의 증분 처리·삭제 동기화·재시작성 요구에도 그대로 적용되며, 동시에 AI 도구를 팀 생산성에 정착시키는 협업 구조 설계 경험까지 더해 안정성과 개발 속도를 함께 끌어올리는 데 기여하고 싶습니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- NHN에서 4년간 쌓아온 MSA·Kafka·캐시·JPA·대용량 배치 역량이 실제 대규모 커머스 트래픽 환경에서 어떻게 작동하는지 직접 검증하고 싶다는 것이 가장 큰 이유입니다.
- 게임/AI 도메인은 트래픽 패턴은 강했지만 비즈니스 도메인의 깊이(상품·전시·주문·결제)는 커머스가 비교 불가하게 풍부합니다. 도메인 모델링과 확장 구조 설계에 꾸준히 투자해온 만큼, 더 복잡한 도메인에서 한 단계 성장하고 싶습니다.
- AI 시대에 '기능을 만드는 속도'와 '대규모 환경에서의 안정성'을 동시에 끌어올리는 조직 문화를 경험하고 싶습니다. 올리브영이 무중단 OAuth2 전환·Feature Flag·Shadow Mode를 운영 사례로 공개한 수준의 엔지니어링 디테일이 제가 일하고 싶은 환경과 맞습니다.

### 왜 올리브영인가
- 올리브영 기술 블로그의 'MSA 환경 데이터 연동 전략' 글에서 Cache-Aside + Kafka 하이브리드 + Redis Key 기반 선택적 API 호출 설계를 봤을 때, 제가 슬롯 팀에서 RabbitMQ Fanout + StampedLock으로 풀었던 문제와 동일한 결의 고민을 더 큰 트래픽 단위로 풀고 있다고 느꼈습니다. 같은 언어로 대화할 수 있는 팀이라고 판단했습니다.
- 올영세일 평소 대비 10배 트래픽 중 OAuth2를 무중단 전환하면서 Feature Flag·Shadow Mode·Resilience4j 3단계 보호·Jitter 설계까지 운영한 사례는 '시니어가 트레이드오프를 어디까지 책임지는지'에 대한 팀 기준을 보여줍니다. 이 기준 위에서 일하고 싶습니다.
- 1,600만 고객의 쇼핑 경험을 책임지는 커머스 코어를 다룬다는 점이 매력적입니다. 게임에서는 트래픽 폭증과 정합성, AI 서비스에서는 대용량 색인과 외부 API 신뢰성을 다뤘는데, 이 둘을 합친 형태가 결국 대규모 커머스 백엔드라고 생각합니다.

### 왜 이 역할에 맞는가
- 공고의 우대 사항(Spring Boot, MSA, Kafka, 캐싱 전략, 대용량 데이터/트래픽, JPA·도메인 모델링)이 제가 4년 동안 실제로 사용한 핵심 스택과 거의 1:1로 일치합니다. 합류 즉시 도메인 학습에만 집중하면 되는 포지션이라고 판단했습니다.
- 수습 3개월 + 1차 라이브 코딩 + 2차 화이트보드 같은 전형 구조는 단순 경력 매칭이 아니라 '실제로 코드를 짜고 설계를 그릴 수 있는가'를 보겠다는 신호로 읽었고, 그 평가 기준이 제가 일하는 방식과 맞습니다.
- AI 도구를 팀에 정착시킨 경험(Cursor Rules 20+, 신규 게임 3종 에이전트 단독 구현, Claude Code 하네스 기반 4인 에이전트 팀 운영)이 있기 때문에, 커머스 도메인의 안정성을 지키면서도 팀 전체 개발 속도를 끌어올리는 형태로 기여할 수 있다고 생각합니다.

## 메인 질문 1. 사내 AI Playground RAG를 위해 Confluence 문서를 OpenSearch에 색인하는 Spring Batch 파이프라인을 처음부터 설계하셨다고 들었습니다. 11개 Step으로 분리한 이유, AsyncItemProcessor를 도입한 배경, 그리고 재시작 가능성을 어떻게 구조적으로 보장했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 후보자가 '왜 Spring Batch인가'에 대한 의도적 선택 근거를 가지고 있는지, 단순 스케줄러로 끝내지 않은 이유를 설계 언어로 설명할 수 있는지 본다.
- Step 분리 = 실패 격리라는 운영 신뢰성 사고가 실제로 코드 구조에 박혀 있는지, 그리고 그 사고가 커머스 색인·증분 처리에도 전이 가능한지 확인한다.
- 비동기 I/O 처리를 단순 '병렬화하면 빠르다' 수준이 아니라 청크/Future/Writer 위임의 동작 원리까지 이해한 시니어 수준인지 검증한다.

### 실제 경험 기반 답변 포인트

- Step 11개로 분리한 핵심 이유는 '실패 격리 + 재시작 단위 분리'다. 페이지 색인 Step이 실패해도 댓글 Step·삭제 동기화 Step의 결과가 보존되고, 실패 지점부터 이어서 재시작 가능하다.
- AsyncItemProcessor를 도입한 이유는 임베딩 API와 문서 파싱 API 모두 I/O 바운드라 동기 처리 시 청크당 수 분이 걸렸기 때문이다. AsyncItemProcessor는 Future를 반환하고 AsyncItemWriter가 Future.get()으로 모아서 OpenSearch에 벌크 색인하는 위임 구조다.
- 재시작성은 두 축으로 보장했다. ① Reader에 ItemStream을 구현해 커서 기반 페이지네이션 위치를 ExecutionContext에 저장 → 마지막으로 처리한 지점부터 재시작. ② 스페이스 정보·페이지 ID 같은 도메인 데이터는 JobExecutionContext가 아니라 @JobScope 인메모리 홀더(ConfluenceJobDataHolder)로 분리 → JobExecutionContext는 재시작용 경량 상태(커서 위치)에만 쓴다.
- @JobScope 빈은 재시작 시 새 JobExecution이 만들어지면 새 인스턴스로 초기화되기 때문에, 상태 로더 Step에 allowStartIfComplete(true)를 걸어 재시작 시에도 반드시 재실행되게 했다. 이 부분은 디버깅하면서 NPE로 직접 확인한 함정이다.
- 처리 단계는 CompositeItemProcessor로 ChangeFilter(version 비교) → Enrichment(첨부·작성자·멘션) → BodyConvert(ADF→Markdown) → Embedding으로 체이닝해 단일 책임을 유지했고, 이 위에 AsyncItemProcessor가 한 번 더 감싸서 스레드풀 병렬화를 담당하는 이중 구조다.

### 1분 답변 구조

- Spring Batch를 선택한 이유는 재시작 가능성·청크 단위 트랜잭션·Step 단위 책임 분리·실행 이력 추적 네 가지가 운영상 필수였기 때문입니다.
- Step을 11개로 쪼갠 이유는 실패 격리입니다. 페이지·댓글·삭제 동기화 Step이 독립적이라 한 Step이 실패해도 나머지 결과가 살아있고 실패 지점부터 재실행됩니다.
- AsyncItemProcessor를 도입한 이유는 임베딩 API가 I/O 바운드여서 동기 처리 시 청크당 수 분이 걸렸기 때문입니다. AsyncItemProcessor가 Future를 반환하고 AsyncItemWriter가 Future.get으로 결과를 모아 OpenSearch에 벌크 색인하는 위임 구조로 만들어 처리 시간을 크게 단축했습니다.
- 재시작성은 Reader의 커서를 ExecutionContext에 저장하는 한편, 스페이스 정보·페이지 ID 같은 도메인 데이터는 @JobScope 인메모리 홀더로 분리해 JobExecutionContext가 매 청크마다 직렬화되는 부담을 없앴습니다. 이 분리가 청크 커밋마다 DB I/O를 줄이는 의도적 설계입니다.

### 압박 질문 방어 포인트

- '그냥 스케줄러 + ExecutorService로도 되지 않냐'는 질문에는, 재시작 시 어디서 멈췄는지 자동 추적·청크 단위 트랜잭션 커밋·Job 실행 이력 자동 적재 세 가지를 직접 구현하면 결국 Spring Batch를 다시 만드는 셈이라고 답한다. 운영 비용 관점의 결정이지 기술적 호기심이 아니다.
- 'AsyncItemProcessor는 Spring 공식 문서에서도 권장 안 한다는데?'는 충분히 들어올 수 있다. 답: 권장 안 하는 맥락은 '주문 트랜잭션처럼 처리 순서·정합성이 중요한 케이스'다. 우리는 임베딩 결과가 idempotent하고 OpenSearch에 벌크로 모아 색인하므로 순서 보장이 필요 없는 워크로드라 적합했다.
- 'JobExecutionContext에 그냥 저장하면 안 되나'는 명확한 함정 질문이다. 답: 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블에 직렬화되기 때문에 수천 개 페이지 ID를 매번 쓰는 건 불필요한 부하다. JobExecutionContext는 재시작용 경량 상태 전용이고, 도메인 데이터는 @JobScope에 둬야 한다는 게 의도적 분리다.

### 피해야 할 약한 답변

- '성능이 좋아서 AsyncItemProcessor를 썼다' 수준의 답변. 왜 동기가 느렸는지(I/O 바운드 vs CPU 바운드)와 비동기 적용 후 어떤 메커니즘으로 빨라졌는지 메커니즘 언어로 설명하지 못하면 시니어 답변이 아니다.
- 'Step을 잘게 쪼개는 게 좋아 보였다' 수준의 답변. Step 분리 = 실패 격리 = 재시작 단위 분리라는 운영상 의도를 못 풀면 단순 모범 답안 암기로 보인다.
- 재시작성 질문에 '@JobScope를 썼다'까지만 답하고 'allowStartIfComplete(true)' 같은 함정을 말하지 못하면 실제로 운영해본 사람이 아니라는 인상을 준다.

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor가 Future를 반환하는데, 청크 내 일부 아이템이 실패하면 트랜잭션 롤백 범위는 어떻게 됩니까? Skip 정책과 어떻게 결합했나요?

**F1-2.** ChangeFilterProcessor가 null을 반환하면 Spring Batch가 해당 아이템을 스킵하는데, 청크 사이즈가 10이고 9개가 스킵되면 통계·로깅 측면에서 어떤 문제가 생길 수 있고 어떻게 대응했나요?

**F1-3.** @JobScope 빈은 CGLIB 프록시로 싱글톤 빈에 주입되는데, 재시작 시 새 JobExecution이 만들어지면 빈이 어떻게 다시 초기화되는지 그 라이프사이클을 설명해 주세요.

**F1-4.** 11개 Step 중 'completeIndexingJobStep'이 마지막에 실행 중 실패하면, 그 사이에 OpenSearch에 색인된 문서들의 정합성을 어떻게 보장하나요? 보상 트랜잭션이나 후처리 전략이 있었나요?

**F1-5.** 이 파이프라인을 커머스 상품 검색 색인에 그대로 옮긴다면 어떤 부분이 동일하고, 어떤 부분이 달라져야 한다고 보십니까? (특히 변경 빈도·삭제 동기화·실시간성 요구 차이 관점)

---

## 메인 질문 2. OCR 서버 배포·스케일인 시 발생하던 503 에러를 추적해 Graceful Shutdown 누락이 원인임을 찾아내고 해결하셨습니다. NHN Cloud의 terminationGracePeriodSeconds 30초 고정 제약 안에서 시간 예산을 어떻게 분배했는지, SIGTERM 핸들러와 supervisord stopwaitsecs를 함께 손본 이유를 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- '에러 로그 → 진짜 원인'까지의 추적 경로를 가설 수립·검증 형태로 풀 수 있는지, 즉 공고의 '문제 해결을 위한 가설 수립 및 수행 경험'에 직접 대응하는지 본다.
- K8s/컨테이너/프로세스 매니저/리버스 프록시(Envoy)의 종료 시퀀스를 한 흐름으로 이해하고 있는지, 단일 레이어 지식이 아니라 분산 시스템 종료 라이프사이클을 시니어 수준으로 다룰 수 있는지 검증한다.
- 고정된 외부 제약(terminationGracePeriodSeconds 30초) 안에서 시간 예산을 분배하는 설계 사고를 갖췄는지 확인한다.

### 실제 경험 기반 답변 포인트

- 에러 표면은 'upstream connect error / reset reason: connection failure / delayed connect error: 111'이었다. error 111 = ECONNREFUSED라 TCP 레벨에서 연결이 거부되는 상황이고, 응답 헤더의 'server: envoy'로 Envoy는 살아있고 upstream(:50051) 쪽 문제임을 좁혔다.
- 원인 추적 결과 두 층의 문제였다. ① gRPC 서버에 SIGTERM 핸들러가 없어 server.wait_for_termination()이 SIGTERM 수신 시 즉시 죽어 50051 포트가 먼저 닫힘. ② preStop hook은 Envoy drain_listeners + sleep 20s를 수행 중이라 그 시간 동안 Envoy가 이미 죽은 upstream으로 트래픽을 라우팅 → ECONNREFUSED.
- supervisord stopwaitsecs도 함께 손봐야 했다. 기본값 10초라 SIGTERM 핸들러를 추가해도 supervisord가 10초 안에 종료 안 되면 SIGKILL을 날린다. 핸들러 grace=12s를 살리려면 stopwaitsecs를 17s(grace 12 + 여유 5)로 늘려야 SIGKILL이 안 끼어든다.
- NCS의 terminationGracePeriodSeconds 30s 고정 제약 때문에 'preStop sleep 15 + gRPC grace 12 + 여유 3 = 30s'로 예산을 재분배했다. 기존 sleep 20을 그대로 두면 grace를 추가하는 순간 30s를 넘어 SIGKILL이 발생한다.
- 수정 후 시퀀스: T+0 preStop 시작 → T+15 SIGTERM → T+15~27 in-flight RPC drain + 신규 거부 → T+27 컨테이너 종료. Envoy가 더 이상 죽은 포트로 라우팅하지 않는다.

### 1분 답변 구조

- 에러 헤더의 'server: envoy'와 error 111(ECONNREFUSED)을 보고 'Envoy는 살아있는데 upstream gRPC가 먼저 죽는다'로 가설을 좁혔습니다.
- 원인은 두 층이었습니다. gRPC 서버에 SIGTERM 핸들러가 없어 SIGTERM에 즉시 죽고, supervisord stopwaitsecs 기본값 10초가 핸들러 grace보다 짧아 SIGKILL이 끼어들 수 있었습니다.
- NCS가 terminationGracePeriodSeconds 30초로 고정이라 'preStop sleep 15 + gRPC grace 12 + 여유 3 = 30'으로 예산을 다시 짰습니다. 기존 sleep 20을 그대로 두면 grace를 추가하는 순간 30초를 넘어 SIGKILL이 발생합니다.
- 수정 후에는 preStop이 끝난 시점에 gRPC 서버가 SIGTERM을 받아 grace=12s 동안 in-flight RPC를 처리하고 신규 요청을 거부하는 구조라, Envoy가 죽은 포트로 라우팅하지 않게 됐고 503이 사라졌습니다.

### 압박 질문 방어 포인트

- 'preStop sleep을 그냥 더 늘리면 안 되냐'는 압박: terminationGracePeriodSeconds가 30초로 고정이라 sleep을 늘리면 SIGTERM 이후 drain 시간이 사라진다. 결국 어느 지점에서 죽이느냐의 문제고, drain은 애플리케이션 레이어가 책임져야 한다.
- 'SIGKILL은 어차피 OS 강제 종료 아니냐, supervisord 굳이 신경써야 하냐'는 압박: supervisord가 SIGKILL을 날리면 K8s grace period가 다 안 갔는데 프로세스가 먼저 죽는다. K8s는 grace 안에서 SIGTERM을 기대하지만 supervisord가 그 안에서 자체 SIGKILL을 날리면 의도가 깨진다. K8s + 프로세스 매니저 두 레이어의 정책이 일관되어야 한다.
- '왜 처음부터 SIGTERM 핸들러를 안 넣었나'에는 정직하게 답한다. gRPC 서버 템플릿에 그게 들어있지 않았고, 트래픽이 적을 땐 묻혀 있다가 배포·스케일인 빈도가 늘면서 표면화됐다. 단순 코드 추가가 아니라 '예산 분배·SIGKILL 끼어듦 방지'까지 같이 가야 진짜 해결이라는 점이 핵심이다.

### 피해야 할 약한 답변

- 'preStop sleep을 늘려서 해결했다' 수준의 답변. terminationGracePeriodSeconds 제약과 SIGKILL 끼어듦 문제를 못 풀면 근본 원인을 못 본 것이다.
- SIGTERM 핸들러만 추가했다고 답하고 supervisord stopwaitsecs 함정을 말하지 못하면 '한 레이어만 보는 사람'으로 보인다.
- 'Envoy가 문제였다'고 답하면 오답에 가깝다. Envoy는 정상 동작했고 upstream이 먼저 죽은 게 문제다. 책임 레이어를 잘못 가리키는 건 시니어로서 큰 감점.

### 꼬리 질문 5개

**F2-1.** in-flight RPC 처리 중에 신규 RPC가 들어오면 server.stop(grace=12)는 신규 요청을 어떻게 처리합니까? gRPC 라이브러리 레벨의 동작을 설명해 주세요.

**F2-2.** preStop hook의 sleep 동안 K8s는 어떤 상태로 컨테이너를 보고 있고, Service의 endpoint에서 이 Pod이 언제 제거됩니까? 이 타이밍이 바로 503에 어떻게 영향을 주나요?

**F2-3.** gRPC 대신 HTTP 기반 서비스라면 동일한 패턴(preStop drain + SIGTERM grace)을 어떻게 구현하시겠습니까? Spring Boot의 graceful shutdown 옵션과 비교해 설명해 주세요.

**F2-4.** 이 문제를 사후 검증하기 위해 어떤 메트릭을 봤거나 어떤 부하 테스트로 회귀를 막을 수 있을까요? (예: 배포 중 5xx rate, in-flight 요청 수)

**F2-5.** 동일한 종료 시퀀스 문제를 Kafka Consumer 애플리케이션에 적용한다면 in-flight 메시지·offset commit 관점에서 어떤 추가 설계가 필요할까요?

---

## 메인 질문 3. RAG 임베딩 메타데이터 구성을 Blocklist(remove) 방식에서 Allowlist(EmbeddingMetadataProvider 인터페이스) 방식으로 전환하셨습니다. 이 리팩터링이 OCP 관점에서 어떤 문제를 해결했고, Spring DI(`List<EmbeddingMetadataProvider>` 자동 주입)와 결합해 어떤 확장 구조를 만들었는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 전략 패턴·OCP·DI 같은 키워드를 단순 용어 암기가 아니라 실제 코드 변경으로 풀 수 있는지 본다.
- 리팩터링 전후 코드의 가독성·테스트 용이성·확장성 차이를 구체 사례로 비교 설명할 수 있는지 확인한다.
- 도메인 모델링과 ORM 활용을 강조하는 포지션이라, 단순 분기 코드를 인터페이스로 추상화한 설계 사고가 커머스 도메인에 어떻게 전이될지 그릴 수 있는지 검증한다.

### 실제 경험 기반 답변 포인트

- Blocklist 방식은 EmbeddingService에서 전체 메타데이터를 복사한 뒤 14개 remove를 직접 호출하는 구조였다. DocumentType이 늘어날 때마다 if-else 분기가 늘었고, '임베딩에 결국 어떤 필드가 들어가나'를 알려면 remove 목록을 역산해야 했다.
- EmbeddingMetadataProvider 인터페이스를 도입해 각 구현체가 'getSupportedDocumentTypes'로 자신이 담당하는 타입을 선언하고 'provide(Document)'로 명시적으로 포함할 필드만 채우는 Allowlist 구조로 바꿨다. 인터페이스 한 곳을 보면 어떤 필드가 들어가는지 즉시 보인다.
- 공통 필드 처리는 AbstractCollabToolEmbeddingMetadataProvider, AbstractConfluenceEmbeddingMetadataProvider 두 추상 클래스로 묶고, 그 위에 Task·Wiki·DriveFile·Confluence 구현체를 뒀다. Confluence는 title이 없을 때 subject로 폴백하는 특수 로직을 추상 클래스 레벨에 통합했다.
- Spring이 List<EmbeddingMetadataProvider>로 모든 @Component를 자동 주입하고, Config에서 flatMap으로 'DocumentType → Provider' 맵을 빌드한다. EmbeddingService는 DocumentType으로 provider를 조회해 위임만 하면 끝이라 14개 remove + if-else 분기가 사라졌다.
- 결과: ① 새 DocumentType 추가 시 EmbeddingService를 건드리지 않음(OCP 준수) ② cloneMetadata, getMetadataValue, putMetadata 같은 Blocklist 전용 보일러플레이트 메서드 삭제 ③ 구현체별 단위 테스트가 독립적으로 가능.

### 1분 답변 구조

- 기존 Blocklist 방식은 EmbeddingService에서 14개 remove를 호출하고 DocumentType별 if-else가 누적되는 구조였습니다. 어떤 필드가 임베딩에 들어가는지 알려면 remove 목록을 역산해야 했습니다.
- EmbeddingMetadataProvider 인터페이스로 'getSupportedDocumentTypes + provide(Document)' 두 메서드만 두고, 각 구현체가 자신이 담당하는 타입을 선언하면서 포함할 필드만 명시적으로 채우는 Allowlist 구조로 바꿨습니다.
- Spring이 List<EmbeddingMetadataProvider>로 모든 @Component를 자동 주입하고, Config에서 'DocumentType → Provider' 맵을 빌드합니다. EmbeddingService는 DocumentType으로 조회해 위임만 합니다.
- 결과적으로 새 DocumentType 추가 시 EmbeddingService 수정이 필요 없고(OCP), 보일러플레이트 메서드 3개를 삭제했고, 구현체별 단위 테스트가 깔끔해졌습니다.

### 압박 질문 방어 포인트

- '결국 if-else가 인터페이스 + 다형성으로 옮겨간 것 아니냐, 분기 자체는 사라지지 않았다'는 압박: 맞다, 분기가 사라진 게 아니라 책임이 이동한 것이다. 핵심은 '누가 변경에 책임지는가'다. 새 DocumentType이 추가될 때 EmbeddingService(공용 코드)를 건드리지 않고 새 @Component만 추가하면 끝인 게 OCP의 본질이다.
- '추상 클래스 두 단계로 나눈 건 over-engineering 아니냐'는 압박: AbstractCollabTool과 AbstractConfluence 둘 다 'createResultWithCommonFields'에 공통 필드 + 타입별 차이(Confluence는 title→subject 폴백)를 흡수해야 했다. 하나로 합치면 폴백 로직이 협업 도구 쪽까지 누수된다. 두 계층은 실제 도메인 차이의 반영이다.
- '그냥 Map<DocumentType, Function> 으로도 됐을 텐데'에는, 인터페이스를 쓰면 ① Spring DI로 자동 등록 ② getSupportedDocumentTypes로 한 구현체가 여러 타입을 담당하는 다대일 관계 표현 ③ 구현체별 단위 테스트가 독립이라는 세 가지 이점이 있어 인터페이스가 더 적합했다고 답한다.

### 피해야 할 약한 답변

- '전략 패턴을 적용했다'까지만 말하고 Blocklist의 구체적 문제(역산 어려움, 14 remove, OCP 위반)를 못 풀면 패턴 명칭만 외운 사람으로 보인다.
- Spring DI 자동 주입(List<>)과 flatMap 맵 빌드 부분을 빼면 '구조는 좋은데 실제 어떻게 묶었나'에 답을 못 한 것이다.
- '리팩터링하니 깨끗해졌다' 수준의 정성적 답변. 삭제된 메서드 3개·테스트 독립성·OCP 준수 같은 구체적 결과를 말하지 못하면 약하다.

### 꼬리 질문 5개

**F3-1.** 한 구현체가 여러 DocumentType(예: TASK / TASK_COMMENT / TASK_FILE)을 담당하는 다대일 관계인데, 만약 미래에 같은 DocumentType을 두 Provider가 담당하려 하면 Config의 toMap이 충돌합니다. 어떻게 방어하시겠어요?

**F3-2.** Provider가 늘어나면 컨텍스트 부팅 시 List<>에 자동 주입되는 빈이 많아지는데, 특정 환경(테스트·스페이스별)에서 일부 Provider만 활성화하고 싶다면 어떻게 설계하시겠습니까?

**F3-3.** 이 패턴을 커머스의 '상품 → 검색 색인 메타데이터' 구성에 옮긴다면 카테고리·브랜드·전시·프로모션 도메인별로 어떻게 Provider를 쪼개시겠어요? 경계 기준은 무엇인가요?

**F3-4.** Provider 인터페이스의 'provide' 메서드가 Map<String, Object>를 반환하는데, 타입 안정성 관점에서 더 나은 시그니처가 있다면 어떻게 바꾸시겠어요?

**F3-5.** 리팩터링 전 Blocklist 코드를 그대로 두고 새 Provider 시스템을 추가했다면 어떤 운영상 위험이 있었을까요? 빅뱅이 아닌 점진적 전환은 어떻게 설계하시겠어요?

---

## 메인 질문 4. 12일 동안 단독으로 AI 웹툰 제작 도구 MVP(199 plan / 760 커밋)를 만드셨습니다. 이 정도 볼륨이 가능했던 핵심 요인인 Claude Code 하네스 기반 4인 에이전트 팀(planner/critic/executor/docs-verifier) 구조를 설계 관점에서 설명하시고, vibe 코딩에서 spec 기반 코딩으로 어떻게 진화시켰는지 말씀해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 후보자가 AI 도구를 단순 사용자가 아니라 파이프라인·아키텍처 설계자 수준으로 다루는지, 즉 협업 구조 자체를 설계할 수 있는지 본다.
- 혼자 12일에 199 plan / 760 커밋 같은 비현실적 숫자를 만들어낸 메커니즘을 메타 인지 관점에서 풀 수 있는지, 즉 '내 머리로 한 일'과 '에이전트 팀이 한 일'의 경계를 명확히 그릴 수 있는지 검증한다.
- '팀에 정착시키는 능력'이 강점인 후보자라, 이 경험이 커머스 팀 생산성 향상으로 어떻게 전이될지 그림이 그려지는지 확인한다.

### 실제 경험 기반 답변 포인트

- 처음 vibe 코딩 단계에서는 한 세션에서 논의→구현→빌드→테스트를 다 했지만, 작업이 길어지면 컨텍스트 한도·잘못된 가정 시작·반복 결정 같은 문제가 누적됐다. 가장 큰 문제는 '무엇을 할지'를 충분히 잡지 못한 채 코드부터 친 것이었다.
- spec 기반 코딩으로 전환하면서 /planning 단계를 분리했다. 기능 구현 전 8단계(기술 가능성·사용자 흐름·데이터 모델·API·화면·엣지 케이스·마이그레이션·검증)로 논의하고 합의된 결과만 task 파일로 만든다. Opus 모델을 쓴 이유는 잘못된 task로 executor를 돌리면 그 시간/토큰이 더 비싸기 때문이다.
- /plan-and-build 단계에서는 planning 결과물을 tasks/planNNN-*/index.json + phase 파일들로 떨어뜨려 자기완결적으로 만들었다. 세션이 끊겨도 git에 task가 영속 상태로 남아있어 어디서든 이어받을 수 있다.
- /build-with-teams에서 critic + docs-verifier 게이트를 추가했다. critic은 계획을 실제 코드와 대조해 APPROVE/REVISE를 판정하고, docs-verifier는 코드 변경 후 ADR·data-schema 정합성을 확인한다. '자기 계획을 자기가 검증하면 잘 못 본다'는 관찰을 구조화한 결과다.
- /integrate-ux는 합류한 디자이너의 vibe 코드(로컬 state 목업·인라인 색상·god component)를 정해진 변환 룰로 흡수하는 스킬이다. '디자이너 vibe 결과물을 다시 짜야 할 것이 아니라 흡수할 변환 대상으로 보는 관점' 자체가 협업 마찰을 없앴다.

### 1분 답변 구조

- 혼자 12일에 199 plan을 처리할 수 있었던 핵심은 4인 에이전트 팀(planner/critic/executor/docs-verifier)의 역할 분리였습니다.
- 처음 vibe 코딩에서는 모호한 입력이 모호한 출력을 만들어 결과를 통째로 버리는 일이 잦았습니다. /planning 단계를 분리해 8단계 합의가 끝난 task 파일만 executor에게 넘기는 spec 기반 코딩으로 전환하면서 입력 정확도가 결과 품질을 결정한다는 걸 체득했습니다.
- critic 에이전트가 계획을 코드와 대조해 APPROVE/REVISE를 판정하고, docs-verifier가 ADR/data-schema 정합성을 확인합니다. 자기 계획을 자기가 검증하면 잘 못 본다는 관찰을 별도 에이전트로 구조화한 결과입니다.
- task가 git에 영속 상태로 남아 세션이 끊겨도 어디서든 재시작할 수 있다는 점이 12일 단기간에 199 plan을 처리할 수 있었던 결정적 메커니즘이었습니다. 결국 사람의 역할은 '구조 설계와 트레이드오프 판단'으로 이동했습니다.

### 압박 질문 방어 포인트

- '그 760 커밋이 진짜 의미 있는 코드냐, 자동 생성 노이즈 아니냐'는 압박이 들어올 수 있다. 답: docs-first 원칙으로 코드 전 ADR·data-schema부터 갱신하고, critic이 phase 파일과 코드를 대조해 REVISE하는 게이트가 있으며, 12일 동안 134개 ADR이 쌓였다는 점이 결정 밀도를 보여준다. 단순 자동 커밋이 아니라 결정 단위 커밋이다.
- '에이전트가 다 했는데 뭐가 본인 역량이냐'는 질문에는, '무엇을 만들지'에 대한 spec 합의·아키텍처 레이어 경계 설계(Action/Repository/AI/Routes)·Pro→Flash→Lite fallback 구조·환각 차단을 위한 Continuation grounding 재주입 같은 결정은 모두 내가 했고, 에이전트는 그 결정의 실행자였다고 답한다. 분업의 경계가 명확하다.
- '그래서 이 방식이 커머스 팀에 어떻게 적용되냐'에는, 슬롯 팀에서 Cursor Rules 20+로 신규 게임 3종을 에이전트 단독 구현한 경험을 합쳐 '도메인 컨텍스트 문서화 → 팀 전체가 활용할 수 있는 형태로 정착'까지 이미 검증된 흐름이라고 답한다. 1,600만 트래픽 도메인의 안정성을 지키면서도 개발 속도를 올리는 게 가능하다.

### 피해야 할 약한 답변

- 'AI를 잘 써서 빠르게 만들었다' 수준의 답변. 에이전트 팀의 역할 분리·게이트 구조·docs-first 원칙을 못 풀면 단순 툴 사용자로 보인다.
- vibe 코딩과 spec 기반 코딩의 차이를 추상적으로만 답하면 약하다. /planning 8단계, task 파일 영속화, critic의 APPROVE/REVISE 같은 구체 메커니즘이 답변에 들어가야 한다.
- 에이전트 의존도가 너무 높아 '본인이 한 결정'이 무엇인지 답하지 못하면 시니어 면접에서 큰 감점이다. 결정의 80%는 task 파일에 박혀 있어야 한다는 인사이트를 함께 풀어야 한다.

### 꼬리 질문 5개

**F4-1.** critic이 REVISE를 반복적으로 내려서 phase 파일이 수렴하지 않는 경우 어떻게 끊으셨습니까? 무한 루프 방어 메커니즘이 있나요?

**F4-2.** docs-first에서 ADR이 1,581줄까지 비대해졌다가 700줄로 줄였다고 하셨는데, AI 에이전트 컨텍스트 효율 관점에서 ADR을 어떻게 설계해야 한다고 보십니까?

**F4-3.** 이 4인 에이전트 팀 구조를 그대로 커머스 팀의 5명 시니어 개발자 환경에 적용한다면 어떤 부분이 그대로 가고 어떤 부분이 달라져야 한다고 생각하십니까?

**F4-4.** Pro fallback 시 Flash/Lite 모델은 grounding 준수력이 약해 환각이 다시 등장한다고 하셨는데, 만약 다음 이터레이션에서 이 문제를 풀어야 한다면 어떤 접근부터 시도하시겠어요?

**F4-5.** /integrate-ux 스킬의 변환 룰(로컬 state→Server Action, 인라인 색상→semantic 토큰, god component→Container/Presenter)을 어떻게 코드 레벨에서 자동화 가능 여부를 판단하셨나요? 자동화 한계는 어디입니까?

---

## 메인 질문 5. Gemini 모델 전략을 처음에는 flash 우선으로 갔다가 'pro 기본 + 429 fallback flash → lite' 구조로 뒤집으셨습니다. 이 결정의 트레이드오프와, 분산된 재시도 비효율을 막기 위해 도입한 전역 Rate Limit Tracking, 그리고 Project 단위 Gemini Context Caching까지 결합한 비용·신뢰성 설계를 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 비용 vs 신뢰성 트레이드오프를 단가가 아니라 총 호출 횟수(재생성 포함)로 보는 시니어 사고를 갖췄는지 본다.
- 분산 환경의 재시도 정책이 전역 상태 없이 비효율을 누적시키는 패턴(여러 요청이 같은 죽은 모델을 또 두드림)을 인지하고, 이를 메모리 Map 같은 가벼운 전역 상태로 푸는 실무적 감각이 있는지 검증한다.
- 외부 API 비용 최적화를 단순 단가 비교가 아니라 캐시·재시도 통합 설계 수준으로 끌어올릴 수 있는지, 즉 커머스 외부 연동 신뢰성 설계에 전이 가능한지 확인한다.

### 실제 경험 기반 답변 포인트

- 초기 flash 우선 전략은 단가 1/4·속도 빠름이라는 표면적 이득에 끌렸지만, 운영자가 결과 퀄리티에 불만족해 재생성을 트리거하면 총 호출 횟수가 증가해 결과적으로 더 비싸졌다. '비용 최적화는 단가가 아니라 재생성 포함 총 호출'로 관점을 바꿨다.
- ADR-072에서 'pro 기본 + 429 fallback flash → lite'로 뒤집었다. 속도/비용을 우선 희생하고 한 번에 만족하는 결과 확률을 높이는 선택이다.
- 분산 재시도가 같은 모델을 또 두드리는 비효율을 막기 위해 전역 Rate Limit Tracking(메모리 Map<modelId, skipUntilTimestamp>)을 두고, 어떤 요청이 429를 받으면 그 모델을 일정 시간 skip 대상으로 마킹해 다른 요청들이 같은 죽은 모델을 또 호출하지 않도록 했다.
- 30초 재시도 로직을 제거한 이유는 TPM이 1분 단위로 풀리기 때문에 30초 대기는 너무 짧아 또 실패한다는 관찰이다. 429가 오면 즉시 다음 fallback으로 넘기는 게 빠르고 안정적이었다.
- Project 단위 Gemini Context Caching은 비용 절감의 다른 축이다. 원작 소설 전문(novelText)을 cachedContent로 묶어 Analysis·Content-review·Treatment·Conti·Continuation 다섯 단계가 같은 캐시를 공유하게 했다. 만료 5분 안에 들어오는 호출은 입력 토큰 비용이 0에 가깝고, 이 절감액이 pro 사용에 따른 단가 상승을 상쇄한다.

### 1분 답변 구조

- 처음 flash 우선은 단가가 싸 보였지만, 결과 퀄리티에 운영자가 불만족해 재생성하면 총 호출이 늘어 결국 더 비쌌습니다. 그래서 'pro 기본 + 429 fallback flash → lite'로 뒤집었습니다.
- 분산된 재시도가 같은 죽은 모델을 또 두드리는 비효율을 막기 위해 전역 Rate Limit Tracking을 메모리 Map<modelId, skipUntilTimestamp>로 두고, 한 요청이 429를 받으면 그 모델을 일정 시간 skip 대상으로 마킹했습니다.
- 30초 재시도는 TPM이 1분 단위라 또 실패하기 쉬워 즉시 다음 fallback으로 넘기는 게 빠르고 안정적이었습니다.
- 비용은 Project 단위 Context Caching으로 메웠습니다. 원작 소설 전문을 cachedContent로 묶어 5개 단계가 공유하면 5분 만료 안 호출은 입력 토큰 비용이 거의 0이라, pro 단가 상승을 상쇄합니다. 비용·신뢰성·재시도 정책을 따로 보지 않고 하나의 설계로 묶었습니다.

### 압박 질문 방어 포인트

- '결국 pro 단가가 비싸지지 않냐'는 압박: 단가 비교는 의미가 없다. 운영자가 만족 못 해 재생성하면 호출 횟수가 두 배가 되는 게 진짜 비용이다. Context Caching으로 입력 토큰 비용을 거의 0으로 만들면 pro 단가의 상당 부분이 상쇄된다.
- '그 메모리 Map은 멀티 인스턴스 환경에선 일관성이 깨지지 않냐'는 정확한 지적: MVP 단계에서는 단일 인스턴스라 충분했고, 멀티 인스턴스로 확장하면 Redis 같은 공유 저장소로 옮겨야 한다는 걸 인지하고 있다. 이 부분은 의도적으로 미룬 결정이다.
- '30초 재시도를 없앤 건 너무 공격적 아니냐'는 압박: TPM이 1분 단위로 풀린다는 게 실측 데이터고, 30초는 또 실패할 확률이 높았다. 즉시 fallback으로 넘기는 게 사용자 응답 시간 측면에서도 더 좋았다.

### 피해야 할 약한 답변

- '비용을 줄이려고 모델 전략을 바꿨다' 수준의 답변. 단가 vs 총 호출 횟수의 관점 전환을 못 풀면 표면적 이해로 보인다.
- 전역 Rate Limit Tracking 부분에서 '왜 전역 상태가 필요한가'(분산 재시도가 같은 죽은 모델을 또 호출하는 비효율)를 풀지 못하면 단순 retry 로직 수준으로 보인다.
- Context Caching을 단순 '비용 절감'으로만 답하고 'pro 단가 상승을 상쇄하는 다른 축'으로 묶어 설명하지 못하면 통합 설계 사고가 약해 보인다.

### 꼬리 질문 5개

**F5-1.** 전역 Rate Limit Tracking을 멀티 인스턴스 환경(K8s 여러 Pod)으로 확장한다면 Redis나 Hazelcast 중 어떤 걸 선택하시겠어요? 일관성 모델·TTL·atomic 연산 관점에서 설명해 주세요.

**F5-2.** Context Caching의 5분 만료 윈도 안에 모든 단계를 끝내야 비용 이득이 나오는데, 사용자가 중간에 중단하거나 재생성하면 캐시가 만료되어 비용이 다시 올라갑니다. 어떤 운영 메트릭으로 캐시 효율을 추적하시겠어요?

**F5-3.** 올리브영의 무중단 OAuth2 전환에서 본 Resilience4j Circuit Breaker 3단계 보호와 비교하면, 이 fallback 구조는 어떤 면에서 닮아있고 어떤 면에서 다릅니까?

**F5-4.** 이 모델 전략을 커머스의 외부 결제·배송·재고 API 호출 신뢰성 설계에 옮긴다면 어떤 부분이 그대로 가고 어떤 부분이 달라져야 한다고 보십니까?

**F5-5.** fallback 시 Flash/Lite로 떨어지면 grounding 준수력이 약해져 환각이 다시 등장한다고 하셨습니다. SLA(품질) vs 가용성 트레이드오프에서 어떤 신호로 fallback을 멈추고 사용자에게 실패를 알려야 한다고 설계하시겠어요?

---

## 최종 준비 체크리스트

- 면접 직전 체크 1: '왜 Spring Batch인가 = 재시작·청크 트랜잭션·Step 실패 격리·실행 이력' 4-튜플을 한 호흡에 말할 수 있는지, 그리고 AsyncItemProcessor가 Future를 반환하고 AsyncItemWriter가 Future.get으로 모은다는 위임 구조를 손으로 그릴 수 있는지 확인한다.
- 면접 직전 체크 2: gRPC OCR 503 사례에서 'preStop sleep 15 + gRPC grace 12 + 여유 3 = 30s' 예산 분배를 외워 두고, supervisord stopwaitsecs(기본 10s) 함정과 SIGKILL 끼어듦을 설명할 수 있는지 점검한다. error 111 = ECONNREFUSED, server: envoy 헤더로 책임 레이어를 좁혀가는 사고 흐름이 핵심이다.
- 면접 직전 체크 3: EmbeddingMetadataProvider 리팩터링은 '14 remove → Allowlist provide()'와 'EmbeddingService는 위임만'이라는 두 문장을 코어로 답한다. List<EmbeddingMetadataProvider> 자동 주입과 flatMap으로 DocumentType 맵을 만든다는 Spring DI 부분을 빼먹지 말 것.
- 면접 직전 체크 4: AI 웹툰 12일 사례는 '199 plan / 760 커밋 / 134 ADR' 숫자를 기억하고, 4인 에이전트 팀(planner/critic/executor/docs-verifier) + /planning 8단계 + docs-first 원칙을 한 흐름으로 풀 수 있게 준비한다. '에이전트가 다 한 것 아니냐' 압박에 대한 분업 경계 답변(spec 합의·레이어 경계·fallback·환각 차단은 사람이 결정)을 외워둔다.
- 면접 직전 체크 5: Gemini 모델 전략에서는 '단가 비교가 아니라 재생성 포함 총 호출' 관점 전환과, 메모리 Map<modelId, skipUntilTimestamp> 기반 전역 Rate Limit Tracking, Project 단위 Context Caching 5분 윈도 세 가지를 묶어 답할 수 있어야 한다. 멀티 인스턴스 확장 시 Redis로 옮긴다는 한계 인식까지 함께 말한다.
- 면접 직전 체크 6: 모든 답변 끝에 '커머스 도메인에 어떻게 전이되는가'를 한 문장 붙인다. 1,600만 고객·MSA·Cache-Aside + Kafka 하이브리드·무중단 OAuth2 전환 같은 올리브영 키워드와 자연스럽게 연결한다.
- 면접 직전 체크 7: 약한 답변 회피 — '잘 됐다·깨끗해졌다·빠르다' 같은 정성적 표현을 피하고, 항상 메커니즘(왜)·숫자(얼마나)·트레이드오프(무엇을 포기했나)·전이 가능성(다른 도메인 적용)을 한 답변 안에 묶는다.
