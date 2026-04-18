# [초안] AI 서비스 개발팀 경험 기반 Java 백엔드 면접 질문 은행

---

## 이 트랙의 경험 요약

- AI 서비스 팀에서 수행한 Confluence → OpenSearch RAG 벡터 색인 Spring Batch 11-Step 파이프라인(AsyncItemProcessor/CompositeItemProcessor/@JobScope/재시작성), 임베딩 메타데이터 전략 패턴 전환(Blocklist→Allowlist, OCP 준수), OCR 서버 Graceful Shutdown 503 수정(K8s terminationGracePeriodSeconds 제약 하 Envoy·supervisord·SIGTERM 예산 설계), AI 웹툰 제작 도구 MVP(Next.js 16 + Prisma 7 + Gemini, 12일 단독 풀스택, Claude Code 하네스 기반 4인 에이전트 팀)를 중심 소재로 삼는다.
- 질문 톤은 시니어 Java 백엔드 면접 기준을 유지하되, AI 협업 경험이 '툴 사용자' 수준을 넘어 '파이프라인 설계자' 수준임을 드러내는 질문과 답변 포인트를 섞는다. 올리브영 커머스플랫폼유닛(1,600만 고객, MSA, Kafka Event-Driven, Redis Cache-Aside, JPA, 대용량 처리)이라는 타깃 컨텍스트와 연결되는 브릿지를 매 질문에서 유지한다.
- 5개 메인 질문은 각각 (1) Spring Batch RAG 파이프라인 설계 (2) Graceful Shutdown 503 원인 분석 및 예산 설계 (3) 임베딩 메타데이터 전략 패턴 리팩터링 (4) AI 웹툰 MVP 하네스·에이전트 팀 설계 (5) Kafka Transactional Outbox Pattern 구현을 다룬다. 각 질문에 5개 팔로업을 붙여 설계 트레이드오프와 운영 관점까지 내려가도록 구성했다.

## 1분 자기소개 준비

- NHN에서 4년째 게임 백엔드와 AI 서비스 개발을 맡고 있는 김병태입니다.
- 소셜 카지노 게임 팀에서 Spring Boot 멀티모듈 MSA 환경의 슬롯 서비스를 담당하며, 다중 서버 인메모리 캐시 동기화를 RabbitMQ Fanout과 StampedLock으로 해결했고, Kafka 비동기 처리에는 @TransactionalEventListener AFTER_COMMIT과 REQUIRES_NEW 기반 Outbox Pattern을 직접 설계했습니다.
- 이후 AI 서비스 팀으로 옮겨 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 11-Step RAG 파이프라인을 설계·구현했고, 임베딩 메타데이터 구성을 Blocklist에서 Allowlist 기반 전략 패턴으로 리팩터링해 OCP를 확보했습니다.
- 최근 12일간은 혼자 AI 웹툰 제작 도구 MVP를 Claude Code 하네스 기반 4인 에이전트 팀으로 199 plan, 760 커밋 규모로 개발하면서, AI 협업을 '도구 사용'에서 '파이프라인 설계'로 한 단계 끌어올렸습니다.
- 지금까지 쌓은 Kafka Event-Driven, Redis 캐싱, Spring Batch 대용량 처리, JPA 도메인 모델링 경험을 1,600만 고객이 사용하는 커머스 환경에서 검증하고 기여하고 싶어 올리브영 커머스플랫폼유닛에 지원했습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 제가 슬롯 서비스에서 해결한 '다중 서버 캐시 정합성 + 이벤트 기반 선택적 갱신' 설계는 올리브영 기술 블로그의 'MSA 도메인 데이터 연동 전략'에서 다룬 Cache-Aside + Kafka 하이브리드와 문제의식이 같아, 합류 후 설계 토론에 바로 기여할 수 있다고 판단합니다.
- OCR 서비스 배포 503을 NCS terminationGracePeriodSeconds 30초 제약 하에서 preStop hook 15s + gRPC grace 12s로 예산 재설계한 경험은, 올영세일 10배 트래픽 중 무중단 OAuth2 전환을 달성한 팀의 문제 영역과 동일합니다.
- Spring Batch로 RAG 벡터 색인 파이프라인을 처음부터 설계한 경험은, 커머스의 상품·전시 색인 파이프라인에서 '증분 처리, 실패 격리, 재시작 가능성'이라는 동일한 원칙으로 이식 가능합니다.
- Cursor Rules 20+개 구축과 Claude Code 하네스 기반 에이전트 팀 구축으로 팀 내 AI 도구 도입을 선도한 경험이 있어, 빠른 개발 속도와 안정성을 함께 요구하는 팀 문화에 바로 녹아들 수 있다고 생각합니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 현재 팀에서 MSA 캐시 정합성, Kafka Outbox, Spring Batch RAG 파이프라인, 12일 단독 풀스택 MVP까지 설계-구현-운영 전 주기를 직접 다뤄봤고, 다음 단계는 이 설계 역량이 '1,600만 고객 트래픽'이라는 물리적 규모에서 실제로 어떻게 작동하는지 검증하는 환경이라고 판단했다.
- 게임·AI 서비스 도메인에서는 트래픽 피크가 이벤트성으로 오는 반면, 커머스는 상시적인 대규모 트래픽 + 세일 피크가 공존한다. 내가 설계한 Outbox·StampedLock 기반 캐시 동기화·AsyncItemProcessor 병렬화가 상시 트래픽 환경에서 어떻게 통할지 직접 부딪혀 보고 싶어 이직을 결심했다.
- 혼자 또는 소수로 핵심 설계를 주도하는 경험을 4년간 쌓았는데, 이제는 시니어 엔지니어들과 함께 더 큰 규모의 도메인(상품·전시·주문·검색)에서 설계 토론을 하며 한 단계 더 성장하는 환경이 필요하다고 느꼈다.
- AI 개발 도구 도입을 팀 내 선도적으로 맡아 Cursor Rules 20+개 구축, Claude Code 하네스 기반 4인 에이전트 팀 구축까지 해봤는데, 이 경험을 '게임 도메인 내 개인 생산성 도구' 수준이 아니라 커머스처럼 복잡한 도메인에서 팀 전체의 개발 속도를 끌어올리는 자산으로 확장하고 싶다.

### 왜 올리브영인가
- 올리브영 기술 블로그의 'MSA 도메인 데이터 연동 전략(2026-03-18)'에서 다룬 'Redis Cache-Aside + Kafka 이벤트 수신 후 선택적 API 호출' 하이브리드 설계는, 내가 슬롯 서비스에서 구현했던 'RabbitMQ Fanout + StampedLock + 인메모리 캐시' 패턴과 문제의식이 거의 동일하다. 같은 문제를 더 큰 규모에서 다르게 푼 팀이라 설계 토론에 바로 기여할 수 있다고 판단했다.
- 올영세일 트래픽 10배 상황에서 Feature Flag + Shadow Mode + Resilience4j 3단계 보호 + Jitter로 100% 성공률 OAuth2 무중단 전환을 이룬 사례는, 내가 배포 중 503을 일으킨 OCR 서비스에서 preStop hook 예산을 재설계한 경험과 동일한 '런타임 트래픽을 끊지 않으면서 구조를 바꾸는' 문제 영역이다. 이 영역에서 일하고 싶어 지원했다.
- 1,600만 고객이 사용하는 서비스에서 안정성과 개발 속도를 동시에 높이는 것이 팀의 미션이라 명시돼 있는데, 나는 지금까지 '파편화된 로직을 단일 템플릿으로 통합 + 타입별 위임 + 447개 테스트로 안전망 확보'처럼 개발 속도와 안정성을 트레이드오프 없이 함께 끌어올리는 방식을 반복해왔다. 동일한 가치관을 가진 팀에서 더 큰 영향을 내고 싶다.
- Kafka 기반 Event-Driven, JPA 도메인 모델링, Redis 캐싱, MSA, 대용량 처리 — 올리브영 커머스플랫폼이 요구하는 스택이 내가 실무에서 설계 수준으로 다룬 스택과 1:1로 겹친다. 학습 곡선에 시간을 쓰는 대신 도메인 이해와 기여에 집중할 수 있는 환경이라 판단했다.

### 왜 이 역할에 맞는가
- 공고에서 말한 '상품 관리, 전시 로직, 검색 엔진 연동'은 내가 Confluence → OpenSearch RAG 파이프라인에서 다룬 '대규모 문서 증분 색인 + 삭제 동기화 + 벡터 검색 + 메타데이터 전략 패턴' 문제와 구조적으로 동일하다. 검색 품질을 높이는 색인 전략(allowlist 메타데이터, 변경 감지, 재시작성)을 상품 검색 도메인에 그대로 적용할 수 있다.
- 'JPA/Hibernate ORM 및 도메인 모델링'이 필수 자격인데, 나는 PostCommitUpdateEventListener로 커밋 이후에만 캐시 갱신 메시지를 발행하는 설계, @TransactionalEventListener(AFTER_COMMIT) + Propagation.REQUIRES_NEW 기반 Outbox 등 JPA 트랜잭션 경계 위에서 도메인 이벤트를 안전하게 뽑아내는 설계를 실제 서비스에서 운영한 경험이 있다.
- MSA + Kafka + Redis + Spring Batch + 대용량 데이터 — 우대사항에 나열된 항목들이 단순 사용 경험이 아니라 '내가 설계했거나 재설계한 영역'이다. 특히 Spring Batch 11 Step으로 RAG 벡터 색인 파이프라인을 처음부터 만든 경험은 커머스의 상품/재고/전시 색인·배치 파이프라인에 직접 이식 가능하다.
- 팀의 미션인 '빠르고 안정적인 고객 경험'을 내 관점에서 해석하면 '도메인 로직을 확장 가능한 구조로 유지하면서 실패 격리 + 재시작 + 관측 가능성을 확보하는 것'이다. 이 관점이 지금까지 내 작업(AbstractPlayService 통합, Outbox traceId 저장, Step 단위 실패 격리)의 공통 주제였고, 동일한 관점을 커머스 도메인에서 이어가고 싶다.

## 메인 질문 1. AI 서비스 팀에서 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 처음부터 설계하셨다고 했는데, 왜 Spring Batch를 택했고 전체 Step 구조를 어떻게 잡았는지, 그 중 가장 어려웠던 설계 결정은 무엇이었는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 대용량 데이터 처리 설계 경험이 실제로 '프레임워크를 썼다'가 아니라 '왜 이 프레임워크/구조를 택했는가'까지 내려가는지 확인하고 싶다.
- 커머스 상품·재고·전시 색인 파이프라인에 바로 연결 가능한 문제의식(증분 처리, 실패 격리, 재시작성)을 가지고 있는지 평가하고자 한다.
- Step 분리 · 청크 처리 · 리스타트 같은 Spring Batch 핵심 개념을 실전 맥락에서 설명할 수 있는지 보고자 한다.

### 실제 경험 기반 답변 포인트

- 선택 이유를 네 축으로: 재시작 가능성(BATCH_JOB_EXECUTION 이력), 청크 기반 메모리 안전(OOM 방지), Step 단위 책임 분리로 실패 격리, 실행 이력 자동 기록. 단순 스케줄러 대비 '임베딩 API 장애로 중간에 실패해도 처음부터 다시 돌리지 않는다'는 운영 요구가 핵심이었다.
- 전체 11개 Step 구조를 흐름으로 설명: 색인 시작 기록 → 연결 정보 초기화 → 스페이스 수집 → 페이지 색인 → 페이지 ID 수집 → 댓글 색인 → 삭제된 페이지/댓글/첨부파일 제거 → 인덱스 refresh → 완료 기록. 각 Step이 단일 책임을 갖고 앞 Step이 채운 상태를 뒤 Step이 읽는다.
- 가장 어려웠던 결정은 Step 간 데이터 공유 방식이었다. 처음엔 JobExecutionContext에 수천 개 페이지 ID를 넣었지만 청크 커밋마다 DB에 직렬화되는 부하가 컸다. @JobScope 빈 ConfluenceJobDataHolder로 옮기면서 CGLIB 프록시 기반 주입, 재시작 시 @JobScope가 초기화되는 문제에 대비해 상태 로더 Step에 allowStartIfComplete(true) 지정까지 필요했다.
- 청크 내 병렬화는 AsyncItemProcessor로 해결했다. 임베딩 API가 I/O 바운드라 청크 사이즈 10일 때 동기 처리로는 청크당 수 분이 걸렸다. AsyncItemProcessor + AsyncItemWriter가 Future를 흘려보내고 Writer에서 Future.get()을 모아 OpenSearch 벌크 색인하는 구조였다.
- Processor는 CompositeItemProcessor로 ChangeFilter(version 비교로 미변경 스킵) → Enrichment(첨부·작성자·멘션 보강) → BodyConvert(ADF→Markdown) → Embedding을 체이닝했다. 덕분에 '변경된 문서만 임베딩 호출'이라는 비용 최적화가 자연스럽게 들어갔다.
- 설계 기준은 '실패 격리 + 재시작 + 증분 처리'. 이는 커머스의 상품·전시·검색 색인 파이프라인에 그대로 이식 가능한 패턴이다.

### 1분 답변 구조

- Spring Batch를 택한 건 임베딩 API 장애로 중간에 실패해도 재시작 가능해야 했기 때문이다. 단순 스케줄러로는 청크 실패 시 처음부터 다시 돌려야 했다.
- Step은 11개로 잘랐다. 스페이스 수집, 페이지 색인, 댓글 색인, 삭제된 페이지/댓글/첨부 제거까지 단일 책임으로 분리했고, 각 Step이 @JobScope 홀더를 통해 상태를 공유한다.
- 핵심 Step인 페이지 색인은 CompositeItemProcessor로 ChangeFilter·Enrichment·BodyConvert·Embedding을 체이닝했고, 임베딩 API가 I/O 바운드라 AsyncItemProcessor로 청크 내 병렬화했다.
- 가장 어려운 결정은 Step 간 데이터 공유였다. JobExecutionContext는 청크 커밋마다 DB 직렬화 부하가 커서 @JobScope 빈으로 바꿨고, 재시작 시 상태 로더가 반드시 재실행되도록 allowStartIfComplete(true)로 잡았다.

### 압박 질문 방어 포인트

- 'AsyncItemProcessor 쓰면 스레드 안전은 어떻게 보장했냐'고 파고들면: 각 Processor 단계는 stateless하게 설계했고, 상태를 가지는 컴포넌트(연결 정보)는 @StepScope로 Step별 인스턴스를 분리했다. Writer는 Future를 순서대로 get()하는 AsyncItemWriter라 벌크 순서성도 유지된다고 답한다.
- '그냥 Kafka + Consumer로 실시간 색인하면 안 되냐'고 물으면: Confluence가 변경 이벤트를 안정적으로 push하지 않고 polling 방식이 현실적이며, 삭제 동기화(TRASHED 상태 조회)는 배치 스타일이 더 명확하다고 방어한다. 다만 페이지 생성 실시간성이 중요해지면 하이브리드(Kafka로 변경 감지 + Batch로 보정)를 검토할 여지가 있다고 열어둔다.

### 피해야 할 약한 답변

- 'Spring Batch가 기본이라 골랐습니다' 식의 피상적 답변 — 설계 트레이드오프가 드러나지 않으면 감점
- Step 개수만 나열하고 Step 간 데이터 공유(@JobScope vs JobExecutionContext) 선택 이유를 못 대는 답변 — 실전 경험이 얕다고 판단될 수 있음
- AsyncItemProcessor를 '병렬 처리 때문에 썼다'로만 설명 — Future/AsyncItemWriter 흐름까지 설명해야 설계 수준으로 보인다

### 꼬리 질문 5개

**F1-1.** allowStartIfComplete(true)가 없으면 재시작 시 구체적으로 어떤 NPE가 어디서 납니까? 상태 로더 Step이 이미 COMPLETED면 어떤 일이 벌어지나요?

**F1-2.** AsyncItemProcessor의 스레드풀 크기를 어떻게 정했나요? 임베딩 API의 Rate Limit과 충돌하지 않도록 어떤 실험·지표를 봤습니까?

**F1-3.** 청크 사이즈를 10으로 정한 근거는 무엇인가요? OpenSearch 벌크 색인 단위와 임베딩 API 타임아웃 중 어느 쪽 제약이 더 강했습니까?

**F1-4.** ChangeFilter가 OpenSearch의 version 필드를 기준으로 변경 감지를 한다고 했는데, Confluence 쪽에서 version이 올라갔지만 본문은 동일한 경우에도 전부 재임베딩되지 않나요? 그 비용은 허용 가능했습니까?

**F1-5.** Confluence Cloud가 첨부파일 다운로드 URL을 S3로 302 리다이렉트한다고 했는데, RestClient에서 리다이렉트를 수동 처리하기로 한 이유는 뭔가요? 자동 follow로 두면 어떤 위험이 있나요?

---

## 메인 질문 2. OCR 서버 배포·스케일인 때마다 503이 발생하던 문제를 Graceful Shutdown으로 해결하셨다고 했는데, 원인을 어떻게 추적했고 NCS의 terminationGracePeriodSeconds 30초 제약 하에서 어떻게 시간 예산을 설계했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 운영 중 장애를 추적·해결하는 체계적 사고방식을 보고자 한다. 에러 로그 → 프로토콜 레벨 원인 → 구성 요소 각각의 종료 동작까지 내려갈 수 있는지 평가.
- 현실 제약(플랫폼이 강제하는 30초) 아래에서 설계 트레이드오프를 숫자로 맞춰본 경험이 있는지 확인.
- 대규모 트래픽 환경에서 무중단 배포를 중요하게 여기는 팀이라(올영세일 OAuth2 전환 사례) 같은 문제의식을 공유하는지 판단.

### 실제 경험 기반 답변 포인트

- 증상: 배포/스케일인 시 30~60초 단위로 503이 묶음 발생. 응답 헤더 'server: envoy' + 'delayed connect error: 111' → Envoy는 살아있지만 upstream(50051) 연결이 ECONNREFUSED라는 TCP 레벨 사실 확인.
- 구조 파악: 클라이언트 → Envoy(:5000) → gRPC 서버(:50051). 종료 순서를 추적하니 preStop이 Envoy drain_listeners 후 sleep 20s를 걸어두고 있었는데, preStop 완료 후 SIGTERM이 전달되면 gRPC 서버에 SIGTERM 핸들러가 없어서 '즉시' 종료돼버렸다.
- 두 번째 원인: supervisord [program:grpc-server]에 stopwaitsecs가 없어 기본값 10초가 적용됐다. 그 결과 SIGTERM 핸들러를 추가해도 supervisord가 10초 후 SIGKILL을 날리는 구조였다.
- NCS 제약: terminationGracePeriodSeconds가 30초로 고정돼 API 스펙에도 없어서 변경할 수 없다. 모든 종료 작업을 30초 예산 안에 맞춰야 했다.
- 해결: preStop sleep 20s → 15s로 단축, gRPC 서버에 SIGTERM 핸들러 추가해서 server.stop(grace=12) 호출, supervisord stopwaitsecs=17로 설정. 예산은 15 + 12 + 여유 3 = 30초.
- 수정 후 종료 시퀀스: T+0 preStop 시작(Envoy drain) → T+15 SIGTERM → T+15~27 in-flight RPC 완료 대기·신규 요청 거부 → T+27 gRPC 종료. Envoy가 살아있는 동안 upstream이 먼저 죽는 race가 사라졌다.

### 1분 답변 구조

- 증상은 배포마다 묶음 503이었고, 로그의 'delayed connect error: 111'로 Envoy는 살아있는데 upstream(50051)이 먼저 죽은 race라는 걸 특정했다.
- 원인은 두 개였다. gRPC 서버에 SIGTERM 핸들러가 없어서 preStop 끝나자마자 즉시 죽었고, supervisord의 stopwaitsecs 기본값 10초가 겹쳐 SIGKILL이 날아갔다.
- NCS가 terminationGracePeriodSeconds를 30초로 고정해 변경이 불가능해서, preStop sleep 15s + gRPC grace 12s + 여유 3s로 숫자 예산을 다시 짰다.
- 수정 결과 T+15에 SIGTERM이 가고 T+27까지 in-flight RPC를 정상 종료해 503이 사라졌다. 이 경험은 커머스에서 '롤링 배포 중 무중단'이 플랫폼 제약 숫자와 정확히 맞닿아 있다는 걸 몸으로 익힌 사례다.

### 압박 질문 방어 포인트

- '왜 30초 예산 안에 15+12를 나눴냐, 20+5는 왜 안 되냐'고 파고들면: Envoy drain 시간은 in-flight 요청 완료 여유라 너무 짧으면 읽기 직전 요청이 남고, gRPC grace는 실제 응답 시간 p99 + OCR 추론 시간 분포를 보고 12s로 잡았다고 근거 제시. 20+5는 추론 p99를 넘기는 grace가 없어 SIGKILL 위험이 남는다.
- 'SIGTERM 핸들러 대신 trap 셸로 처리하면 되지 않냐'고 물으면: supervisord가 [program]을 관리하고 있어 셸 trap이 프로세스 트리에서 신호를 받지 못하는 구조였다. stopsignal=TERM + stopwaitsecs로 supervisord가 직접 SIGTERM을 전달하도록 체인을 맞춰야 일관성 있게 동작한다고 방어.

### 피해야 할 약한 답변

- 'SIGTERM 핸들러를 추가했습니다'로만 끝내고 supervisord stopwaitsecs나 terminationGracePeriodSeconds 제약을 놓친 답변 — 부분 해결만 한 셈
- 시간 숫자(15/12/17)를 추상적으로만 말하고 '왜 이 숫자인가'의 근거(in-flight 분포, drain 시간, 여유 마진)가 없는 답변
- Envoy·gRPC·supervisord·k8s 중 한 레이어만 얘기해서 '전체 종료 시퀀스'가 머리에 없다는 인상을 주는 답변

### 꼬리 질문 5개

**F2-1.** server.stop(grace=12)가 12초 안에 끝나지 않으면 실제로 어떻게 되나요? Python grpc.server.stop의 내부 동작을 설명해 주세요.

**F2-2.** Envoy drain_listeners를 호출하면 기존 연결과 신규 연결이 각각 어떻게 처리됩니까? connection draining과 listener draining의 차이는?

**F2-3.** K8s에서 preStop hook과 SIGTERM은 어떤 순서로 실행되고, terminationGracePeriodSeconds가 어디서부터 카운트되는지 정확히 설명해 주세요.

**F2-4.** 같은 문제를 HTTP 서비스에서 만났다면 gRPC와 다르게 어떤 설계를 했을 것 같나요? Keep-Alive나 HTTP/2 GOAWAY를 어떻게 다뤄야 하나요?

**F2-5.** 올리브영처럼 세일 피크 트래픽 환경에서 스케일인이 동시에 여러 파드에서 일어나면 이 설계로 충분할까요? 추가로 어떤 보호 장치를 두시겠습니까?

---

## 메인 질문 3. 임베딩 메타데이터 구성을 Blocklist(remove)에서 Allowlist(EmbeddingMetadataProvider) 방식으로 바꾸셨다고 했는데, 기존 구조의 어떤 한계가 이 리팩터링을 촉발했고 구체적으로 어떻게 OCP를 확보했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 단순 '전략 패턴 썼다'가 아니라 기존 코드의 문제를 구조적으로 진단하고, 확장성을 '코드 레벨'에서 증명할 수 있는지 본다.
- 커머스 도메인(상품/전시/주문)처럼 타입이 계속 늘어나는 영역에서 동일한 사고방식을 적용할 수 있는지 평가.
- SOLID·디자인 패턴을 교과서가 아니라 실제 유지보수 문제로 다룬 경험을 확인.

### 실제 경험 기반 답변 포인트

- 기존 Blocklist 한계 네 가지: (1) DocumentType이 늘어날 때마다 if-else 분기와 remove 조합이 폭발적으로 증가 (2) '실제 임베딩에 포함되는 필드'를 알려면 remove 목록을 역산해야 해서 가독성이 떨어짐 (3) cloneMetadata(), getMetadataValue(String), putMetadata(String) 같은 이 패턴 전용 메서드가 Document에 쌓임 (4) 새 DocumentType마다 EmbeddingService를 수정해야 해서 OCP 위반.
- 핵심 아이디어: '제거할 필드 관리'가 아니라 '포함할 필드 명시'로 의미를 뒤집었다. EmbeddingMetadataProvider 인터페이스는 getSupportedDocumentTypes()와 provide(Document)만 가진다.
- 계층 구조로 중복 제거: AbstractEmbeddingMetadataProvider(공통 유틸 putIfNotNull/putFormattedDatetime) → AbstractCollabToolEmbeddingMetadataProvider(협업 도구 공통 필드) → Task/Wiki/DriveFile 구체 Provider. 반대편에 AbstractConfluenceEmbeddingMetadataProvider(title/subject 폴백 처리) → ConfluenceEmbeddingMetadataProvider.
- Spring DI로 자동 확장: @Component로 등록된 모든 Provider를 List로 주입받아 DocumentType → Provider 맵을 Config에서 빌드. EmbeddingService는 DocumentType으로 lookup 후 위임만 한다. 새 DocumentType 추가 시 @Component 클래스 하나만 만들면 끝, EmbeddingService는 건드리지 않는다. 이것이 OCP 준수의 실제 형태다.
- 부수 효과: 구현체별 독립 단위 테스트가 쉬워졌고, before의 14줄 remove + 추가 로직 블록과 if-else 분기가 모두 사라졌으며, Document에 달렸던 cloneMetadata() 등 불필요 메서드도 제거됐다.

### 1분 답변 구조

- 기존 구조는 EmbeddingService에서 문서 메타데이터를 복사한 뒤 14개 필드를 remove하는 Blocklist였다. DocumentType이 늘어날수록 remove 조합과 if-else 분기가 기하급수로 커졌다.
- 핵심 전환은 의미를 뒤집은 것이다. '제거할 필드 관리'에서 '포함할 필드 명시'로 바꿨다. EmbeddingMetadataProvider 인터페이스가 supportedDocumentTypes와 provide를 선언한다.
- 계층은 AbstractEmbeddingMetadataProvider 아래 CollabTool/Confluence 추상 클래스를 두고 Task/Wiki/DriveFile/Confluence 구체 클래스로 분기했다. 공통 필드는 추상 클래스에서 한 번만 정의된다.
- Spring이 @Component 구현체들을 List로 주입해 DocumentType→Provider 맵을 빌드하므로 새 타입 추가 시 @Component 하나만 만들면 끝난다. EmbeddingService를 수정하지 않으므로 OCP가 코드 레벨에서 증명된다.

### 압박 질문 방어 포인트

- 'Provider가 너무 많아지면 관리가 어렵지 않냐'고 하면: 오히려 한 파일당 한 책임이라 리뷰·테스트 단위가 작아진다. DocumentType이 10개가 되면 이전 구조는 EmbeddingService가 폭발하지만, 새 구조는 파일이 10개로 분산될 뿐 각 파일은 짧다고 답한다.
- '왜 어노테이션 기반 자동 dispatch 대신 Map을 Config에서 빌드했냐'고 물으면: 런타임 lookup이 O(1)이고, 시작 시점에 중복 매핑(Provider 둘이 같은 DocumentType을 지원)을 빌드 오류로 바로 잡을 수 있어 디버깅이 쉽다. 어노테이션 스캔은 테스트 환경에서 예기치 않게 Provider가 빠지거나 추가되는 리스크가 있다.

### 피해야 할 약한 답변

- '전략 패턴으로 바꿨습니다'만 말하고 Blocklist의 구체적 문제(4가지 한계)를 나열하지 못하는 답변
- Spring DI 자동 주입 메커니즘을 '알아서 된다' 식으로만 설명하는 답변 — List<T> 주입과 Config 맵 빌드의 흐름을 설명해야 설계자 인상을 준다
- OCP를 '개방-폐쇄 원칙'으로 추상적으로만 말하고, '어떤 코드가 수정되지 않는가'를 구체적으로 짚지 못하는 답변

### 꼬리 질문 5개

**F3-1.** 공통 필드를 AbstractCollabToolEmbeddingMetadataProvider에 모았다고 했는데, 만약 Task만 특정 공통 필드를 제외해야 한다면 그 계층을 어떻게 수정하시겠습니까?

**F3-2.** DocumentType → Provider 맵 빌드 시 같은 DocumentType을 두 Provider가 주장하면 어떻게 감지하고 있나요? Fail-fast 전략이 걸려 있나요?

**F3-3.** Provider 단위 단위 테스트는 어떻게 설계했나요? Document와 DocumentMetadata를 fixture로 어떻게 구성합니까?

**F3-4.** Confluence에서 title 없으면 subject로 폴백한다고 하셨는데, 이런 '도메인 특수 규칙'이 Provider 안에 들어가는 게 맞는지 아니면 상위 레이어에서 normalize해야 하는지 트레이드오프를 설명해 주세요.

**F3-5.** 이 패턴을 커머스의 '상품 카드 응답 메타데이터 구성'(상품 타입별 다른 필드 노출)에 적용한다면 어떤 경계를 만들어야 할까요?

---

## 메인 질문 4. 12일 동안 혼자 AI 웹툰 제작 도구 MVP를 Claude Code 하네스로 199 plan, 760 커밋 규모로 만드셨다는데, 단순 '툴 사용자'를 넘어 에이전트 파이프라인 자체를 설계한 경험이라면 그 구조와 핵심 의사결정이 무엇이었는지 시니어 백엔드 관점에서 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI/에이전트 협업이 '코드 완성 툴 사용' 수준인지, 아니면 시스템 설계 수준인지 가늠한다.
- 커머스 플랫폼에서도 팀 생산성 향상에 기여할 수 있는 사람인지 판단. 특히 팀 내 도입 경험과 설계 관점이 있는지 평가.
- 12일/199/760이라는 숫자 뒤에 실제 구조와 트레이드오프가 있는지, 아니면 마케팅성 수치인지 검증.

### 실제 경험 기반 답변 포인트

- 문제 정의: 혼자 12일에 Next.js + Prisma + Gemini 기반 6단계 풀스택 MVP를 내야 하는 상황. 타이핑 속도로는 불가능한 볼륨(최대 하루 120 커밋)이었기에, 하네스 자체를 제품처럼 설계해야 했다.
- 하네스 진화를 5단계로: (1) vibe 코딩 (2) /planning으로 스펙 선정 (3) /plan-and-build로 phase 분할 + 재시작 가능한 실행 (4) /build-with-teams로 critic + docs-verifier 게이트 추가 (5) /integrate-ux로 디자이너 vibe 코드 통합 스킬화.
- 4인 에이전트 팀: planner(Opus), critic, executor(Sonnet), docs-verifier. 단일 에이전트가 자기 계획을 자기 검증하면 잘 못 본다는 관찰을 근거로 역할 분리. critic은 phase 파일을 실제 코드와 대조해 APPROVE/REVISE 판정, docs-verifier는 ADR/data-schema 드리프트를 차단.
- Gemini 모델 전략: pro→flash→lite fallback + 전역 Rate Limit Tracking Map(429 받은 모델을 일정 시간 skip 마킹) + Project 단위 Context Caching(원작 소설을 5단계가 공유). 인사이트는 '비용 최적화는 단가가 아니라 총 호출 횟수(재생성 포함)'.
- 환각 차단 사례로 설계 수준 증명: 글콘티 continuation 호출이 tail 5컷만 보고 다음 컷을 만들어 환각이 폭증했다. 원인은 프롬프트 문구가 아니라 '호출 구조'였다는 게 핵심 인사이트. Grounding 블록을 continuation에도 매번 재주입하고, '연출은 자유, 서사는 grounding'이라는 경계를 명시해 모델에게 도망갈 자리를 줬다.
- docs-first: 12일간 ADR 134개가 쌓였고, 1,581줄까지 커진 ADR은 docs-verifier가 '에이전트 컨텍스트 효율' 기준으로 700줄로 리팩터링하도록 판정했다. 문서 부패가 곧 에이전트 컨텍스트 부패라는 관점.
- 커머스 연결: 동일한 하네스 설계 원칙(역할 분리 + 재시작 가능 실행 + docs-first + 파일 소유권 매트릭스)이 팀 단위 개발 속도를 끌어올리는 데 그대로 적용 가능하다.

### 1분 답변 구조

- 혼자 12일에 풀스택 MVP를 내야 해서 하네스 자체를 제품처럼 설계했다. 결과적으로 199 plan, 760 커밋이 쌓였다.
- 4인 에이전트 팀(planner/critic/executor/docs-verifier)을 두고, vibe 코딩에서 /planning, /plan-and-build, /build-with-teams, /integrate-ux까지 5단계로 파이프라인을 진화시켰다. 핵심 가치는 입력 정확도와 재시작 가능성이었다.
- Gemini 호출은 pro→flash→lite fallback, 전역 Rate Limit Tracking Map, Project 단위 Context Caching으로 설계했다. 단가가 아니라 총 호출 횟수 기준으로 비용을 봤기 때문이다.
- 환각 차단은 프롬프트 카피라이팅이 아니라 호출 구조 문제였다. Continuation에 Grounding 블록을 매번 재주입하고, '연출은 자유, 서사는 grounding' 경계를 명시해 해결했다. 이 경험은 팀 단위 하네스 도입 설계에 이식 가능하다.

### 압박 질문 방어 포인트

- '760 커밋이 정말 의미 있는 숫자냐'고 하면: 각 커밋은 executor의 phase 단위 체크포인트로, 재시작 경계이자 critic 검증 단위다. 하루 120 커밋은 사람 타이핑이 아니라 에이전트가 체크포인트를 쌓은 결과이며, 큰 단위 커밋이 실패하면 롤백 비용이 커지므로 오히려 작게 쌓은 것이라고 설명.
- 'Claude Code 하네스 없이 Cursor/Copilot으로는 불가능했냐'고 물으면: Cursor도 병행 사용했지만, /plan-and-build처럼 phase 파일을 git에 영속시켜 재시작 가능한 실행을 만드는 건 IDE 내 인라인 완성 모델로는 커버가 안 됐다. Cursor는 로컬 변경 제안, Claude Code는 장기 실행 파이프라인으로 역할을 나눴다고 답한다.
- '커머스에 AI 하네스가 정말 필요하냐'고 회의적으로 가면: 커머스 자체 기능 개발에 AI 파이프라인을 바로 넣자는 주장이 아니라, 팀의 반복 작업(테스트 생성·마이그레이션 리뷰·대규모 리팩터링)에 한정해 생산성을 올리는 도구로서의 경험을 공유하겠다고 스코프를 좁혀 방어한다.

### 피해야 할 약한 답변

- 'Claude를 잘 썼습니다' 수준으로 끝나고 에이전트 역할 분리, Rate Limit Tracking, Context Caching 등 구체적 설계 결정이 안 나오는 답변
- 숫자(199/760)만 강조하고 실제 구조적 의사결정을 설명하지 않는 답변 — 과장으로 들린다
- AI 이야기가 길어지면서 원래 지원한 Java 백엔드 관점에서 벗어나는 답변 — 2분 안에 끝내고 '커머스 팀 생산성에 어떻게 쓸 수 있는지'로 브릿지해야 한다

### 꼬리 질문 5개

**F4-1.** critic 에이전트가 APPROVE/REVISE 판정을 내릴 때 기준이 코드와 phase 파일의 어떤 대조였습니까? 평가 프롬프트의 핵심 규칙 두 가지만 말씀해 주세요.

**F4-2.** 전역 Rate Limit Tracking Map의 TTL은 어떻게 정했나요? 429가 풀리는 시점과 skip 해제 시점을 어떻게 맞췄습니까?

**F4-3.** Gemini Context Caching에서 cachedContent 만료(5분)를 넘는 장시간 파이프라인은 어떻게 처리하셨나요? 캐시 리프레시 전략이 있었습니까?

**F4-4.** docs-verifier가 ADR 드리프트를 잡았을 때 자동으로 ADR을 갱신했나요, 아니면 사람에게 경고만 했나요? 자동화 범위를 어디서 끊었습니까?

**F4-5.** 올리브영 팀에 이런 하네스를 도입한다면 첫 90일에 무엇부터 증명하시겠습니까? 도메인 코드를 에이전트가 만지게 하는 게 아니라면 어떤 범위에서 시작할까요?

---

## 메인 질문 5. 슬롯 서비스의 Kafka 비동기 처리에서 Transactional Outbox Pattern을 직접 설계·구현하셨다고 했는데, 왜 Outbox가 필요했고 @TransactionalEventListener(AFTER_COMMIT), Propagation.REQUIRES_NEW, 재전송 스케줄러, traceId가 각각 어떤 실패 시나리오를 막기 위한 장치인지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 커머스 공고에서 필수로 본 Kafka 기반 Event-Driven Architecture와 Spring 트랜잭션 경계에 대한 '설계 수준' 이해도를 측정.
- Outbox를 '아는 용어' 수준이 아니라 '왜 각 장치가 필요한가'의 근거를 들며 설명할 수 있는지 확인.
- 분산 시스템에서 메시지 유실/중복/재처리 문제를 실제로 겪고 해결한 사람인지 판단.

### 실제 경험 기반 답변 포인트

- 문제 정의: 핵심 API에서 금액 처리·레벨 변화 같은 즉시 응답 로직은 DB 트랜잭션 안에 있어야 하고, 미션 진행·통계·알림 같은 후처리는 Kafka로 분리해야 응답 지연을 막을 수 있다. 하지만 DB 커밋과 Kafka 발행을 함께 처리하면 2PC가 필요해지거나, 커밋 전 발행하면 롤백 시 유령 이벤트가 생긴다.
- @TransactionalEventListener(AFTER_COMMIT): DB 트랜잭션이 '성공적으로 커밋된 이후'에만 이벤트 리스너를 트리거한다. 롤백된 트랜잭션의 이벤트가 Kafka에 나가는 '유령 이벤트' 문제를 원천 차단.
- Kafka 전송 실패 대응: Propagation.REQUIRES_NEW로 별도 트랜잭션을 열어 실패 메시지를 DB(Outbox 테이블)에 저장한다. 이 트랜잭션을 분리한 이유는, 기존 요청 트랜잭션은 이미 커밋된 뒤이므로 여기에 추가 쓰기를 얹을 수 없고, REQUIRES_NEW로 독립된 단위를 열어야 '본 트랜잭션 커밋 + Outbox 기록 실패'가 본 로직까지 롤백시키지 않는다.
- 재전송 스케줄러: Outbox에 쌓인 실패 메시지를 주기적으로 읽어 재전송. at-least-once 전달을 보장하면서 애플리케이션 레이어에서 중복 처리(idempotency)는 소비자가 책임진다.
- traceId 저장: 실패 이벤트에 traceId를 함께 저장해, Kafka가 복구됐는데도 특정 이벤트만 계속 실패하는 경우를 추적 가능하게 했다. 운영 장애 대응 시간을 크게 줄인다.
- 커머스 도메인 연결: 올리브영 블로그의 'Spring 트랜잭션 동기화로 레거시 알림톡 발송 시스템 개선' 사례와 동일한 문제 영역(커밋 이후 이벤트 발행)이며, SQS 기반 알림톡 데드락 분석 글의 문제의식과도 맞닿아 있다.

### 1분 답변 구조

- 즉시 응답이 필요한 로직은 DB 트랜잭션 안에, 후처리는 Kafka로 분리하고 싶었다. 그러나 커밋과 발행을 함께 묶으면 2PC가 필요하고, 커밋 전 발행은 롤백 시 유령 이벤트가 생긴다.
- 첫 번째 방어선은 @TransactionalEventListener(AFTER_COMMIT)였다. 커밋 성공 이후에만 리스너가 트리거되므로 롤백된 트랜잭션의 이벤트는 절대 Kafka에 나가지 않는다.
- 두 번째 방어선은 Kafka 전송 실패 시 Propagation.REQUIRES_NEW로 별도 트랜잭션을 열어 Outbox 테이블에 기록하고 스케줄러가 재전송하는 구조다. 기존 요청 트랜잭션은 이미 커밋됐기 때문에 분리가 필수였다.
- 실패 이벤트에 traceId를 함께 저장해 장기 실패 이벤트를 추적 가능하게 만든 게 운영 관점의 핵심 장치다. 동일한 문제 영역을 올리브영 블로그에서도 다루고 있어 바로 기여 가능하다.

### 압박 질문 방어 포인트

- '@TransactionalEventListener 대신 커밋 후 메서드 마지막에 Kafka send()를 호출해도 같지 않냐'고 하면: 비즈니스 코드에 infrastructure 호출이 섞여 응집도가 떨어지고, 여러 커밋 지점이 있는 긴 트랜잭션에서 AFTER_COMMIT 정확한 시점 보장이 어렵다. 리스너 방식이 Spring 트랜잭션 라이프사이클에 정확히 훅 걸리므로 안전하다고 답한다.
- 'Debezium 같은 CDC 기반 Outbox가 더 표준 아니냐'고 물으면: 정답 중 하나다. 다만 당시 인프라에 CDC 도입 비용이 컸고, 트랜잭션 리스너 + Outbox 테이블 조합으로도 at-least-once + traceId 추적 요구는 충족됐다. 팀 규모와 트래픽이 커지면 CDC 도입이 타당하다는 점까지 열어둔다.

### 피해야 할 약한 답변

- 'Outbox 패턴 썼습니다'만 말하고 네 가지 장치(@TransactionalEventListener, REQUIRES_NEW, 스케줄러, traceId)의 역할을 각각 설명 못하는 답변
- '2PC를 대체하기 위해 썼다'로만 답하고 실제 실패 시나리오(유령 이벤트, 커밋 후 Kafka 장애)를 구체화 못하는 답변
- at-least-once / idempotency / 소비자 책임 분담을 놓치는 답변 — Kafka 설계 이해가 부족해 보인다

### 꼬리 질문 5개

**F5-1.** @TransactionalEventListener(AFTER_COMMIT)이 실제로 어떤 Spring 내부 메커니즘으로 동작하나요? TransactionSynchronizationManager와의 관계를 설명해 주세요.

**F5-2.** Outbox 테이블의 스키마를 어떻게 잡았나요? 메시지 상태, 재시도 횟수, traceId, 파티셔닝 키 같은 필드를 어떻게 구성했습니까?

**F5-3.** 재전송 스케줄러가 여러 인스턴스에서 동시에 돌면 중복 발행이 발생할 텐데, 락 방식(낙관적/비관적)이나 클러스터 잠금을 어떻게 처리했나요?

**F5-4.** 소비자 측 idempotency는 어떻게 확보했나요? 이벤트 ID 기반 dedup인가요, 비즈니스 상태 기반 멱등성인가요?

**F5-5.** 올리브영처럼 상품·전시·주문이 이벤트로 느슨하게 연동되는 MSA에서 Outbox 대신 쓸 수 있는 다른 패턴은 어떤 게 있고, 언제 어떤 걸 택해야 한다고 보십니까?

---

## 최종 준비 체크리스트

- Spring Batch 11 Step 파이프라인의 각 Step 책임과 데이터 공유 방식(@JobScope vs JobExecutionContext) 구분해 설명 가능한지 확인
- AsyncItemProcessor + AsyncItemWriter 구조에서 Future 흐름과 parallelChunkExecutor 스레드풀 설정 근거 답변 가능한지 리허설
- gRPC OCR 503 사건에서 NCS terminationGracePeriodSeconds 30초 제약, preStop sleep 15s, grace 12s, stopwaitsecs 17s 숫자 예산을 그대로 말할 수 있는지 점검
- 임베딩 메타데이터 전략 패턴 전환 시 OCP, 레이어 추상화(Abstract → CollabTool/Confluence → 구체) 계층 설명과 before/after 코드 대비 준비
- AI 웹툰 MVP에서 199 plan / 760 커밋 / 12일 / 134 ADR 숫자와 4인 에이전트 팀 역할(main/executor/critic/docs-verifier) 확정 암기
- Gemini pro→flash→lite fallback + 전역 Rate Limit Tracking Map + Context Caching이 '비용 최적화는 단가가 아니라 총 호출 횟수'라는 인사이트와 연결되도록 스토리 구성
- 글콘티 환각 차단 사례에서 Continuation 호출에 tail 5컷만 줬던 문제와 Grounding 재주입 + '연출은 자유, 서사는 grounding' 경계 설계를 한 문장으로 요약
- 커머스 도메인 적용 가능성(상품/전시/주문, 1,600만 고객, Cache-Aside + Kafka 하이브리드)으로 답변을 연결하는 브릿지 문장 미리 준비
- Java 백엔드 질문 흐름에서 Claude Code 하네스 이야기가 너무 길어지지 않도록 '파이프라인 설계자' 관점 2문장 버전과 5분 버전 분리 연습
- 자기소개 1분 버전과 지원 동기(OliveYoung/직무/이직) 버전을 타이머 켜고 소리 내어 각 3회 이상 리허설
