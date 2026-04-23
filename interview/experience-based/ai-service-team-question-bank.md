# [초안] AI 서비스 개발팀 경험 기반 인터뷰 질문 은행 — CJ 올리브영 커머스플랫폼 시니어 백엔드

---

## 이 트랙의 경험 요약

- NHN AI 서비스 개발팀에서의 Spring Batch 기반 대용량 RAG 벡터 색인 파이프라인 설계/운영 경험을 중심으로, 시니어 백엔드 수준의 설계 판단·트레이드오프·장애 대응 역량을 검증하는 질문 은행.
- 단순 기능 구현이 아닌 아키텍처 레벨 의사결정(@JobScope vs JobExecutionContext, AsyncItemProcessor I/O 병렬화, 전략 패턴 기반 확장 구조)을 드러내는 질문에 무게중심을 둔다.
- Graceful Shutdown 503 트러블슈팅을 통해 인프라/런타임(K8s terminationGracePeriodSeconds, Envoy drain, supervisord stopwaitsecs, SIGTERM 전파)에 대한 실전 이해 깊이를 확인한다.
- AI 웹툰 MVP 12일 단독 풀스택(199 plan / 760 커밋) 경험으로 AI 에이전트 협업 역량이 '툴 사용자'가 아닌 '파이프라인·아키텍처 설계자' 수준임을 드러내고, CJ 올리브영의 대규모 커머스 MSA·Kafka·Redis·JPA 환경과의 접합면을 강조한다.
- 자기소개와 지원 동기를 커머스 도메인(1,600만 고객·대규모 트래픽)과 후보자 경험(MSA, 이벤트 드리븐, 캐시 정합성, 색인 파이프라인) 사이의 구체적 매핑으로 구성한다.

## 1분 자기소개 준비

- NHN에서 4년째 Spring Boot 기반 MSA 환경에서 백엔드 개발을 담당하고 있는 김병태입니다. 소셜 카지노 게임 팀에서 슬롯 서비스 백엔드를 담당하며 다중 서버 인메모리 캐시 정합성, Kafka 기반 AFTER_COMMIT 비동기 처리, 도메인 리팩터링을 주도했습니다.
- 최근 약 1년 4개월간은 AI 서비스 개발팀에서 사내 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch RAG 파이프라인을 11개 Step 구조로 처음부터 설계·운영했고, 여기서 AsyncItemProcessor 기반 I/O 병렬화와 재시작 가능한 청크 구조를 직접 구축했습니다.
- 동시에 gRPC OCR 서버의 배포 중 503 이슈를 Kubernetes terminationGracePeriodSeconds 30초 제약 하에서 Envoy drain · SIGTERM 핸들러 · supervisord stopwaitsecs를 조율해 Graceful Shutdown 예산 설계로 해결한 경험도 있습니다.
- 최근에는 AI 웹툰 제작 도구 MVP를 12일 동안 혼자 풀스택으로 구현하면서, Claude Code 하네스 기반 4인 에이전트 팀을 직접 설계해 199개 plan / 760 커밋을 돌리는 spec 기반 코딩 체계를 만들었습니다. 기능을 만드는 것에 그치지 않고, 팀이 쓸 수 있는 구조와 확장 가능한 파이프라인을 만드는 것을 중요하게 여기는 개발자입니다.

## 올리브영/포지션 맞춤 연결 포인트

- 커머스플랫폼유닛이 쓰는 핵심 스택(Spring Boot MSA · Kafka 이벤트 드리븐 · Redis Cache-Aside · JPA/Hibernate · MSA 간 도메인 데이터 연동)을 실무에서 설계·운영까지 직접 해봤습니다. 단순 사용이 아니라 한계 상황에서 어떤 트레이드오프가 생기는지 체감한 경험이 있습니다.
- 캐시 정합성은 RabbitMQ Fanout + Hibernate PostCommitUpdateEventListener + StampedLock 조합으로 다중 서버 동기화를 구현했고, 올리브영 기술 블로그의 Redis Cache-Aside + Kafka 이벤트 기반 데이터 연동 설계와 문제의식이 같습니다.
- 대용량 데이터 처리 측면에서 OpenSearch에 문서 수만 건을 벡터 색인하고 증분/삭제 동기화를 운영한 경험은, 커머스의 상품 색인·전시 데이터 연동 파이프라인에 즉시 전용될 수 있다고 봅니다.
- Kafka AFTER_COMMIT 발행 + Dead Letter Store + 스케줄러 재시도 + traceId 기반 실패 추적까지 비동기 흐름의 신뢰성을 구조적으로 확보한 경험이 있어, 커머스에서 주문·알림·검색 색인 등 도메인 간 이벤트 연동의 안정성 확보 업무에 바로 기여할 수 있습니다.
- AI 에이전트 협업에서는 팀 내 도입을 선도했고(Cursor Rules 20+ 구축, 신규 게임 3종 에이전트 단독 구현, 팀 전파), 1,600만 고객 환경에서 개발 속도와 안정성을 동시에 높이는 구조 개선에 기여할 수 있습니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 지금까지 쌓아온 기술 — MSA, Kafka 이벤트 드리븐, 캐시 정합성, 대용량 색인 파이프라인 — 이 대규모 커머스 트래픽 환경에서 어떻게 작동하는지 직접 경험해 보고 싶습니다. 게임/AI 서비스 도메인에서 검증한 설계 원칙이 1,600만 고객 규모의 복잡한 커머스 도메인에서 어디까지 유효한지 확인하고 싶은 지적 동기가 큽니다.
- NHN에서는 주로 게임 도메인에서 '동시성과 즉시성'이 최우선이었다면, 커머스는 '복잡한 도메인 모델과 장기 운영되는 비즈니스 로직'이 중심입니다. 후자 환경에서의 도메인 모델링·확장 구조 설계 경험으로 백엔드 개발자로서의 폭을 넓히는 것이 현 시점의 성장 방향과 맞다고 판단했습니다.
- 개인적으로는 '내가 만든 시스템을 실제로 많은 사용자가 매일 쓰는 경험'이 다음 단계의 동기부여입니다. B2C 커머스 플랫폼의 백엔드 엔지니어로서 눈에 보이는 제품 임팩트와 함께 일하고 싶습니다.

### 왜 올리브영인가
- 올리브영 기술 블로그의 MSA 데이터 연동 전략 글에서 Redis Cache-Aside + Kafka 이벤트 하이브리드 설계를 보고, 제가 NHN에서 풀어낸 다중 서버 인메모리 캐시 정합성 문제(RabbitMQ Fanout + Hibernate 이벤트 + StampedLock)와 같은 계열의 문제의식을 이미 조직 차원에서 다루고 있다는 점에 매력을 느꼈습니다.
- 올영세일 평소 대비 10배 트래픽 중 Feature Flag + Shadow Mode + Resilience4j Circuit Breaker + Jitter로 P95 50ms / 성공률 100%를 달성한 무중단 OAuth2 전환 사례는, '대규모 트래픽을 실제로 감당하는 운영 역량'이 조직에 축적되어 있다는 신호로 읽었습니다.
- 수십 명 규모 팀에서 깊이 있는 기술 블로그를 꾸준히 쓰는 문화는 '결정의 맥락을 문서로 남기는 습관'이 조직에 자리잡았다는 뜻이고, 제가 중요하게 여기는 '기술 결정과 트레이드오프를 문서로 남겨 동료와 공유하는' 방식과 잘 맞습니다.

### 왜 이 역할에 맞는가
- 커머스플랫폼유닛의 담당 업무 — 상품 관리·전시 로직·검색 엔진 연동 — 중에서 '검색 엔진 연동'은 제가 OpenSearch 기반 RAG 벡터 색인 파이프라인을 처음부터 설계·운영한 경험과 가장 직접적으로 맞닿아 있습니다. AI 문서 검색과 커머스 상품 검색은 목적이 다르지만, 대규모 데이터를 증분 색인하고 삭제 동기화를 안정적으로 운영하는 패턴은 동일합니다.
- MSA 환경에서 도메인 간 이벤트 연동, 캐시 전략, ORM 활용, 장애 격리(Circuit Breaker·Graceful Shutdown) 같은 공고 우대 항목이 제가 실무에서 직접 풀어본 문제들과 거의 그대로 일치합니다. '학습 후 투입'이 아니라 '첫 달부터 PR 리뷰에 기여'가 가능하다고 판단합니다.
- 수습 3개월의 구조가 '빠른 온보딩 후 바로 기여'를 전제로 한다는 점도 제가 선호하는 방식입니다. 단기간에 제품과 조직의 맥락을 흡수해 확장 가능한 구조 개선에 자발적으로 나서는 일을 지난 회사에서 계속 해왔습니다.

## 메인 질문 1. Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 11개 Step으로 분리했다고 하셨는데, 왜 그렇게 쪼갰는지, 그리고 각 Step 사이의 데이터 공유 방식은 어떻게 설계했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- Spring Batch를 '잡 = 거대한 스크립트'가 아니라 '실패 격리·재시작성·단일 책임' 관점에서 의식적으로 설계했는지 확인한다.
- @JobScope / @StepScope / JobExecutionContext 같은 프레임워크 개념을 경험에 기반해 정확히 구분해 쓰는지, 단순 사용이 아니라 트레이드오프를 이해하는지를 검증한다.
- 시니어 수준의 '왜 쪼갰는가 / 안 쪼갰을 때의 실제 부작용은 무엇이었는가'를 설명할 수 있는지를 본다.

### 실제 경험 기반 답변 포인트

- Step 분리의 본질적 이유는 '실패 격리'였다. 수집·변환·임베딩·색인·삭제 동기화를 한 Step에 묶으면 중간 실패 시 이미 처리된 결과가 사라지고 처음부터 재시작해야 한다. 댓글 Step이 실패해도 페이지 Step 결과는 살아있어야 했다.
- 11개 Step은 단일 책임 단위로 정리: startIndexingJob / initSource / spaceCollect / pageIndexing / pageIdCollect / commentIndexing / deletedPage/Comment/Attachment Remove / indexRefresh / completeIndexingJob. Step 간 데이터는 앞 Step이 컨텍스트에 쓰고 뒤 Step이 읽는 pull 방식.
- Step 간 데이터 공유는 처음에 JobExecutionContext에 넣었지만, 이는 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT에 직렬화되는 '경량 커서' 전용이다. 수천 건 페이지 ID 같은 도메인 데이터를 여기에 두면 매 커밋마다 DB에 읽고 쓰는 불필요한 부하가 된다.
- 그래서 @JobScope 빈 ConfluenceJobDataHolder로 옮겼다. @JobScope는 ScopedProxyMode.TARGET_CLASS로 싱글톤 빈에 안전하게 주입 가능하고, 잡 실행이 끝나면 자동으로 폐기된다.
- 재시작 시 함정이 있었다: 실패 재시작 시 새 JobExecution이 생성되고 @JobScope 빈도 새로 초기화되는데, 상태 로더 Step이 COMPLETED로 스킵되면 빈이 빈 상태로 남아 NPE가 난다. 이를 allowStartIfComplete(true)로 해결했다.
- 이 설계 덕에 색인 중 특정 Step 실패 시 해당 Step부터 재시작 가능했고, 댓글 Step 장애가 페이지 색인 결과를 날려먹지 않았다. 운영 관점에서 '실패의 비용'을 크게 낮췄다.

### 1분 답변 구조

- Step 분리의 핵심 목적은 실패 격리와 재시작 가능성입니다. 수집·변환·임베딩·색인·삭제 동기화를 한 Step에 묶으면 중간 실패 시 이미 처리한 수천 건이 전부 사라집니다. 그래서 11개 Step으로 쪼개 각 Step이 단일 책임만 지게 했습니다.
- Step 사이 데이터 공유는 처음에 JobExecutionContext를 썼는데, 매 청크 커밋마다 DB에 직렬화되는 구조라서 수천 건 페이지 ID 공유에는 부적합했습니다. 그래서 @JobScope 빈 ConfluenceJobDataHolder로 옮겨 메모리에서만 공유하고, JobExecutionContext는 재시작용 커서 같은 경량 상태 전용으로 남겼습니다.
- 재시작 시 상태 로더 Step이 COMPLETED로 스킵되면 @JobScope 빈이 비어 NPE가 나는 문제를 allowStartIfComplete(true)로 잡았습니다. 이 설계 덕에 댓글 Step이 실패해도 페이지 색인 결과는 보존되고, 실패 지점부터 재시작이 가능해졌습니다.

### 압박 질문 방어 포인트

- '왜 11개씩이나? 더 합칠 수 있지 않나요?' → 각 Step이 외부 호출(Confluence / 임베딩 / OpenSearch) 중 하나를 담당하므로 실패 지점이 본질적으로 다르다. 묶으면 실패 원인 분석과 재시작 비용이 선형적으로 증가한다.
- '@JobScope 프록시가 스레드 세이프한가요? AsyncItemProcessor와 함께 쓰면?' → @JobScope 빈에서 제공하는 컬렉션에 쓰기는 로더 Step에서 끝내고, 이후 Step은 읽기 전용으로만 접근하게 분리했다. 동시 쓰기가 없으므로 멀티스레드 Reader에서도 안전하다.
- 'JobExecutionContext도 재시작을 지원하는데 왜 굳이 @JobScope로?' → 용도 분리의 문제다. 커서 같은 경량 상태는 ExecutionContext에 두어 재시작에 활용하고, 수천 건 도메인 데이터는 메모리 빈에 둔다. 둘이 섞이면 DB 부하와 재시작 복잡도가 동시에 늘어난다.

### 피해야 할 약한 답변

- 'Spring Batch 예제에서 본 대로 만들었습니다' — 설계 판단 부재를 드러낸다. 왜 11개인지, 왜 @JobScope인지 설명이 빠지면 '따라 쓴' 수준으로 읽힌다.
- '재시작은 Spring Batch가 알아서 해 줍니다' — allowStartIfComplete나 @JobScope 재초기화 같은 실제로 부딪힌 함정을 말하지 못하면 '실제 운영 경험이 얕다'는 인상을 준다.
- '11개 Step 전부 설명하겠습니다'로 나열만 하는 답변 — 질문의 본질(왜 쪼갰는가 / 어떻게 공유하는가)을 놓친다. Step 이름 나열보다 원칙과 트레이드오프를 먼저 말해야 한다.

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor를 썼다고 하셨는데, Future<T>가 Reader → Processor → Writer 체인에서 정확히 어떻게 흐르는지, 그리고 청크 커밋과의 관계를 설명해 주세요.

**F1-2.** CompositeItemProcessor로 ChangeFilter → Enrichment → BodyConvert → Embedding 4단계를 체이닝했는데, ChangeFilter에서 null을 반환하면 뒤 단계가 스킵된다는 Spring Batch의 동작이 설계에 어떤 영향을 주었나요?

**F1-3.** 색인 Step에서 청크 중간에 일부 아이템의 임베딩 API가 실패하면 청크 전체가 롤백되나요, 아니면 skip 정책을 썼나요? 그 선택 근거는 무엇인가요?

**F1-4.** 다중 Confluence 인스턴스(스페이스별 baseUrl/토큰)를 동일 잡에서 처리하기 위해 ConfluenceApiServiceFactory를 도입하고 Step 실행 컨텍스트에서 연결 정보를 꺼내 쓰셨는데, 왜 잡 파라미터 기반이었고 스프링 프로필 분리는 고려 대상에서 제외했나요?

**F1-5.** 같은 구조를 커머스의 상품 색인 파이프라인에 적용한다면 가장 먼저 바뀌어야 할 Step과 유지될 Step은 각각 무엇이라고 보시나요?

---

## 메인 질문 2. gRPC OCR 서버 배포·스케일인 시 503이 발생한 이슈를, 원인 분석부터 Kubernetes terminationGracePeriodSeconds 30초 제약 하에서의 예산 설계까지 설명해 주세요. 무엇을 보고 무엇을 결정했나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 단순 '로그 보고 고쳤다'가 아니라 '현상 → 스택별 원인 가설 → 제약 조건 → 예산 설계 → 검증'의 엔지니어링 사이클을 수행할 수 있는지를 본다.
- 애플리케이션 레벨(SIGTERM 핸들러)뿐 아니라 프로세스 매니저(supervisord), 사이드카 프록시(Envoy), 오케스트레이터(K8s)까지 수직 전층에 대한 이해도를 검증한다.
- 'NHN Cloud 특수성(terminationGracePeriodSeconds 고정 30초)' 같은 현실 제약을 받아들이고 그 안에서 해를 찾는 실무 감각을 본다.

### 실제 경험 기반 답변 포인트

- 현상: 롤링 배포와 스케일인 직후 수십 초 동안 503이 클러스터 단위로 발생. 에러 메시지는 'upstream connect error ... delayed connect error: 111'. error 111은 ECONNREFUSED, 응답 헤더의 server: envoy는 Envoy는 살아있는데 upstream(50051)에 연결 실패라는 뜻.
- 구조: 클라이언트 → Envoy(:5000) → gRPC 서버(:50051). 컨테이너 종료 시 실제 시퀀스를 재구성해 원인 두 개를 찾았다.
- 원인 1: gRPC 서버에 SIGTERM 핸들러가 없었다. server.wait_for_termination()만 있어 SIGTERM 수신 시 즉시 종료 → 포트 50051 닫힘. 반면 preStop hook은 Envoy drain_listeners 호출 후 sleep 20을 걸어 '20초간 gRPC 서버가 죽은 채 Envoy는 살아서 50051로 라우팅'하는 구간이 생겼다.
- 원인 2: supervisord [program:grpc-server]에 stopwaitsecs가 없어 기본 10초 적용. SIGTERM 핸들러를 추가해도 supervisord가 10초 안에 종료되지 않으면 SIGKILL을 날리는 구조였다.
- 제약: NHN Cloud는 terminationGracePeriodSeconds를 30초로 고정. API 스펙에도 해당 필드가 없어 변경 불가. 모든 종료 동작이 30초 안에 끝나야 한다.
- 예산 설계: preStop sleep 15s + gRPC grace 12s + 여유 3s = 30s. (1) gRPC 서버에 signal.SIGTERM 핸들러 추가 → server.stop(grace=12) (2) supervisord stopwaitsecs=17로 grace(12) + 여유(5) (3) preStop sleep 20→15로 단축.
- 결과: preStop 완료 시점에 gRPC 서버가 정상 drain 후 종료되어 Envoy가 50051에 접속 거부당하는 구간이 사라졌다. 배포 중 503이 0으로 수렴.

### 1분 답변 구조

- 현상은 롤링 배포와 스케일인 직후 503이 묶음으로 발생하는 패턴이었고, 에러 111은 ECONNREFUSED, server: envoy 헤더는 Envoy는 살아있는데 upstream(50051)에 연결 실패라는 뜻이었습니다. 종료 시퀀스를 재구성해 보니 preStop이 Envoy drain 후 sleep 20을 하는 동안 gRPC 서버는 SIGTERM 핸들러가 없어 즉시 죽어 있었습니다. 두 번째 원인은 supervisord stopwaitsecs 기본값 10초로 인한 SIGKILL 강제 종료였습니다.
- NHN Cloud는 terminationGracePeriodSeconds를 30초로 고정하고 변경 API도 제공하지 않아, 모든 종료 동작을 30초 안에 끝내야 했습니다. preStop sleep 15 + gRPC grace 12 + 여유 3 = 30초 예산으로 설계하고, gRPC 서버에 SIGTERM 핸들러를 추가해 server.stop(grace=12)로 in-flight RPC를 drain시키고, supervisord stopwaitsecs=17을 설정해 SIGKILL을 막았습니다.
- 수정 후 preStop 완료 시점에 gRPC 서버가 정상 drain 후 종료되어 Envoy가 upstream에 접속 거부당하는 구간이 사라지고 배포 중 503이 0으로 수렴했습니다.

### 압박 질문 방어 포인트

- '왜 30초 제약을 바꿀 협상을 인프라팀과 하지 않았나요?' → API 스펙 자체에 필드가 없어 플랫폼 레벨에서 막힌 제약이었다. 협상 비용 대비 '있는 예산 안에서 푼다'가 더 빠르고, 구조적 개선이 인프라 측 변경 없이 우리 팀 범위에서 닫혔다.
- 'Envoy preStop drain 대신 gRPC 서버의 readiness probe를 먼저 꺼서 트래픽을 빼는 방법은?' → 그 방식도 유효하지만 이 구조는 Envoy가 트래픽 진입점을 쥐고 있어 drain_listeners를 직접 호출하는 게 더 결정적이었다. readiness 기반은 kube-proxy 전파 지연이 추가 변수로 들어온다.
- 'sleep 15초는 너무 매직넘버 아닌가요?' → 당시 평균 in-flight RPC 지속 시간과 Envoy drain 전파 시간을 측정해 Envoy drain + connection drain window를 합친 안전 하한으로 15를 택했고, 나머지 12초 grace는 tail 요청 처리에 할당했다. 예산을 엔드투엔드로 쓴 구조이지 숫자 자체가 매직이 아니다.

### 피해야 할 약한 답변

- 'SIGTERM 핸들러 추가해서 해결했습니다'만 말하기 — preStop / supervisord / terminationGracePeriodSeconds 같은 수직 전층 원인을 놓쳤다는 인상을 준다.
- '30초 제약이 너무 짧다'는 불평으로 시작 — 주어진 제약 안에서 해를 찾는 시니어 감각이 아니라 환경 탓하는 태도로 읽힌다.
- Envoy 에러 메시지를 그대로 옮기기만 하고 ECONNREFUSED와 upstream 라우팅 구조를 설명하지 못함 — 로그를 해석할 뿐 원인 추론을 못 한 것으로 보인다.

### 꼬리 질문 5개

**F2-1.** server.stop(grace=12)가 내부적으로 정확히 어떻게 동작하는지(신규 요청 거부 시점, in-flight 요청 처리 보장, 타임아웃 시 강제 종료 여부)를 설명해 주세요.

**F2-2.** supervisord stopwaitsecs와 stopsignal의 관계, 그리고 SIGKILL이 내려오는 경로를 구체적으로 설명해 주세요.

**F2-3.** preStop hook은 blocking 실행이라 그 안의 sleep 동안 SIGTERM이 전파되지 않습니다. 이 사실이 왜 중요했고 설계에 어떻게 반영됐나요?

**F2-4.** Envoy 대신 istio 사이드카를 쓰는 환경이었다면 drain 메커니즘이 어떻게 달라지고, 30초 예산 배분이 어떻게 바뀌었을까요?

**F2-5.** 커머스처럼 수백 개 파드가 동시에 롤링 업데이트되는 환경에서는 이 패턴이 더 어려워집니다. 동일 원칙을 TPS·커넥션 풀 상태와 함께 어떻게 확장 적용하시겠어요?

---

## 메인 질문 3. 임베딩 메타데이터 구성을 Blocklist(remove 14번)에서 Allowlist(EmbeddingMetadataProvider) 방식으로 전환했다고 하셨습니다. 왜 이 리팩터링이 OCP 관점에서 중요했고, 설계 전후의 변경 비용을 어떻게 비교할 수 있는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- '전략 패턴 썼습니다'가 아니라 '왜 전략 패턴이 이 문제에 적합했는가'를 설명할 수 있는지를 본다.
- OCP(Open-Closed Principle)를 교과서가 아니라 실제 변경 비용으로 설명하는지, '새 DocumentType 추가 시 수정되는 파일 수'로 체감적으로 드러내는지를 확인한다.
- 리팩터링 결정의 인과관계(문제 현상 → 설계 한계 → 대안 → 전환 비용)를 이해하고 있는지, 그리고 그 과정에서 발생한 부차적 비용(@Component + @Qualifier, 테스트 수정)을 정직하게 드러내는지를 본다.

### 실제 경험 기반 답변 포인트

- 전환 전 구조: EmbeddingService가 document.cloneMetadata() 후 id/url/employee_id/project_id/... 14개 필드를 remove 방식으로 제거하고, DocumentType별로 if-else 분기로 추가 로직을 태웠다.
- Blocklist의 문제 4가지: (1) 새 DocumentType마다 분기 추가 → EmbeddingService 수정 (2) 어떤 필드가 '포함'되는지 파악하려면 remove 목록을 역산해야 함 (3) cloneMetadata/getMetadataValue/putMetadata 같은 전용 메서드가 늘어남 (4) OCP 위반 — 새 도메인 추가가 기존 서비스 수정으로 번짐.
- 전환 후 구조: EmbeddingMetadataProvider 인터페이스(getSupportedDocumentTypes, provide). 각 구현체(Task/Wiki/DriveFile/Confluence)가 자신이 담당하는 타입을 선언하고 포함할 필드를 명시적으로 조립. AbstractCollabToolEmbeddingMetadataProvider / AbstractConfluenceEmbeddingMetadataProvider로 공통 필드 추출.
- Spring DI로 List<EmbeddingMetadataProvider>를 주입받아 DocumentType → Provider 맵을 빌드. EmbeddingService는 맵에서 Provider를 꺼내 위임만 한다. 14개 remove 블록과 if-else가 전부 사라짐.
- 변경 비용 비교: 새 DocumentType 추가 시 전환 전에는 EmbeddingService를 열어 분기 추가 + remove 목록 수정 + 테스트 수정. 전환 후에는 @Component 구현체 하나를 새로 만들고 getSupportedDocumentTypes에 타입 선언만 하면 끝. EmbeddingService 코드는 건드리지 않는다.
- 부차 비용도 정직하게 인정: 구현체 수가 늘어나며 @Component + @Qualifier 주입 설정이 세밀해졌고, @StepScope 빈 충돌(NoUniqueBeanDefinitionException)로 테스트 @Autowired에 @Qualifier를 맞춰야 하는 작업이 추가됐다.

### 1분 답변 구조

- Blocklist 방식은 '제거할 필드'를 관리하는 구조라 새 DocumentType이 추가될 때마다 EmbeddingService에 분기와 remove 목록이 늘었고, 어떤 필드가 실제로 포함되는지를 역산해야 했습니다. 전형적인 OCP 위반이었습니다.
- EmbeddingMetadataProvider 인터페이스를 도입하고 각 구현체가 getSupportedDocumentTypes로 담당 타입을 선언하도록 뒤집었습니다. Spring이 List<Provider>를 주입해 DocumentType→Provider 맵을 만들고, EmbeddingService는 위임만 합니다. 공통 필드는 AbstractCollabTool / AbstractConfluence 추상 클래스로 응집했습니다.
- 전환 후 새 도메인 추가 비용은 '@Component 구현체 하나 작성'으로 끝나고 EmbeddingService는 수정하지 않습니다. 부차 비용으로 @StepScope 빈 충돌 해결을 위한 @Qualifier 주입과 테스트 코드 Autowired 정리가 있었지만, 장기 변경 비용의 감소에 비해 일회성이었습니다.

### 압박 질문 방어 포인트

- '이 정도는 전략 패턴 과설계 아닌가?' → Provider 구현체가 이미 5종(Task/Wiki/DriveFile/Confluence 기본/Confluence 신규 스페이스)이고 계속 늘어나는 궤적이었다. 과설계 여부는 '분기 개수 × 변화 주기'로 판단한다. 여기는 이미 임계를 넘었다.
- '@Qualifier를 명시해야 하는 비용은 전체 코드를 더 복잡하게 만들지 않나?' → 명시적 주입은 '설정 파일이 곧 조합의 증명'이라는 장점이 있어, 추적 가능성 측면에서는 오히려 유리하다. 리팩터링 과정에서 발견된 @StepScope 빈 충돌도 이 명시성 덕에 빌드 타임에 잡혔다.
- '왜 처음부터 이 구조로 만들지 않았나?' → 초기에는 DocumentType이 Task 하나였고, YAGNI 원칙상 추상화를 미리 꽂지 않았다. 3번째 타입이 추가되는 시점이 전환의 자연스러운 신호였고, 실제로 그때 리팩터링했다.

### 피해야 할 약한 답변

- '코드가 더 깨끗해졌습니다'로만 설명 — OCP·변경 비용·추상화 결정 시점 같은 시니어 레벨 언어가 빠진다.
- '전략 패턴 썼습니다'로 끝내기 — 문제의 본질이 Blocklist vs Allowlist의 정보 흐름 방향임을 짚지 못하면 표면적 지식으로 보인다.
- '전부 좋아졌습니다'로 부차 비용을 숨기기 — @StepScope 빈 충돌 같은 실제 트러블을 인정하지 않으면 '경험담이 아니라 정답 재생'으로 읽힌다.

### 꼬리 질문 5개

**F3-1.** AbstractCollabToolEmbeddingMetadataProvider와 AbstractConfluenceEmbeddingMetadataProvider를 왜 별도 추상 클래스로 나눴나요? 인터페이스 기본 메서드로 처리하지 않은 이유는?

**F3-2.** @StepScope 빈 충돌로 NoUniqueBeanDefinitionException이 발생했을 때, @Component @StepScope 전역 등록과 @Bean @StepScope 잡 전용 등록을 어떤 기준으로 나눴나요?

**F3-3.** Confluence의 title/subject 폴백 처리는 구현체 안에 두셨는데, 이를 인터페이스 계약으로 올리는 대안(예: fieldNameResolver)은 왜 택하지 않았나요?

**F3-4.** 전략 패턴이 적합하지 않은 경우를 경험한 적이 있다면 말씀해 주세요. 어떤 신호를 보고 전략 패턴을 포기하셨나요?

**F3-5.** 커머스의 상품 도메인에 같은 패턴을 적용한다면, DocumentType 대신 어떤 기준(카테고리 / 채널 / 브랜드)으로 Provider를 분기시키는 게 적절하다고 보시나요?

---

## 메인 질문 4. AI 웹툰 제작 도구 MVP를 12일 동안 혼자 풀스택으로 구현하면서 199 plan / 760 커밋을 돌렸다고 하셨습니다. Claude Code 하네스 기반 4인 에이전트 팀을 어떻게 설계했고, 단순 'AI 툴 사용'과 '하네스 설계자' 사이의 차이는 무엇이었나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI 에이전트 협업 경험이 '코드 자동완성 수준'인지 '파이프라인·아키텍처 설계 수준'인지 구분한다.
- spec 기반 코딩·역할 분리 에이전트·재시작 가능성 같은 '검증된 방법론적 사고'를 실제로 가지고 있는지 확인한다.
- 커머스 팀에 합류했을 때 조직 단위의 생산성 개선 기여가 가능한 사람인지(Cursor Rules 20+ 전파 경험 포함)를 본다.

### 실제 경험 기반 답변 포인트

- 하네스는 '사람이 많이 치는 도구'가 아니라 '에이전트에게 줄 입력의 정확도를 올리는 구조'다. 12일 / 199 plan / 760 커밋은 개인 타이핑 볼륨이 아니라 에이전트 팀의 처리량이다.
- 4인 역할 분리: planner(설계) / critic(계획 검증) / executor(구현) / docs-verifier(ADR·스키마 정합성 점검). 같은 모델이라도 역할 프롬프트가 다르면 다른 시야로 본다. 자기가 짠 계획을 자기가 검증하면 잘 못 본다는 것이 반복 경험의 결론이었다.
- 진화 단계: vibe 코딩 → /planning(스펙을 먼저 잡음, Opus로 설계 정확도 확보) → /plan-and-build(phase 분할 + 재시작 가능) → /build-with-teams(critic + docs-verifier 검증 게이트) → /integrate-ux(디자이너 vibe 결과물 흡수 워크플로우 스킬화).
- 핵심 설계 원칙 3가지: (1) task 파일이 영속 상태 — 세션이 끊겨도 이어받기 가능 (2) 결정의 80%는 task 파일에 박혀 있어야 한다 — 모호한 입력은 모호한 출력을 낳는다 (3) docs-first — ADR·스키마를 먼저 업데이트해야 다음 세션 에이전트가 올바른 전제로 시작한다.
- 단순 사용자와의 차이: 사용자는 '프롬프트 엔지니어링'에 머물고, 설계자는 '호출 구조 · 검증 게이트 · 역할 분리 · 영속 상태'를 설계한다. 환각 차단을 anti-pattern 문구로 풀지 않고 Continuation에 Grounding 재주입 + Project 단위 Context Cache로 구조적으로 푸는 것이 그 차이의 예다.
- 팀 전파 경험: 사내 슬롯팀에서도 Cursor Rules 20+ 구축 → 신규 게임 3종 에이전트 단독 구현 → 팀 전파로 반복 개발 사이클 단축. 개인 성과가 아니라 팀 생산성 구조 개선에 가까운 일이었다.

### 1분 답변 구조

- 하네스는 사람이 많이 치는 도구가 아니라 에이전트에게 주는 입력의 정확도를 올리는 구조입니다. 199 plan / 760 커밋은 저 혼자 친 게 아니라 4인 에이전트 팀의 처리량이었습니다.
- 팀 구성은 planner / critic / executor / docs-verifier 네 역할이었습니다. 같은 모델이라도 역할 프롬프트가 다르면 다른 시야로 보기 때문에, 자기가 짠 계획을 자기가 검증하게 두지 않고 critic을 분리한 게 핵심이었습니다.
- 진화는 vibe 코딩 → /planning → /plan-and-build → /build-with-teams → /integrate-ux로 쌓였습니다. task 파일이 영속 상태가 되어 세션이 끊겨도 이어받을 수 있고, 결정의 80%를 task 파일에 미리 박아 실행 중 임의 결정을 줄였습니다.
- 단순 사용자와 설계자의 차이는 환각 같은 문제를 프롬프트 문구로 푸는지 호출 구조로 푸는지의 차이입니다. 저는 Continuation에 Grounding 재주입 + Project Context Cache로 구조적으로 풀었습니다. 이 관점은 이전 회사에서도 Cursor Rules 20+ 전파로 팀 생산성 개선에 이미 적용했던 일입니다.

### 압박 질문 방어 포인트

- 'AI가 짜준 코드를 믿을 수 있나요?' → 믿음은 구조에서 나온다. critic 에이전트가 계획을 코드와 대조해 APPROVE/REVISE를 판정하고, docs-verifier가 문서 정합성을 체크하는 이중 게이트가 있어 실행 중 터지는 일이 거의 없었다.
- '커머스 조직 규모에서도 같은 방식이 통할까요?' → 규모가 커질수록 '결정의 맥락을 문서로 남기는' 도구가 오히려 더 필요하다. ADR docs-first 원칙과 파일 소유권 매트릭스는 사람 팀에서도 정확히 같은 목적으로 쓰인다.
- '760 커밋은 품질이 낮은 것 아닌가요?' → 커밋 단위를 작고 명확하게 유지하는 것이 에이전트 팀의 동작 원리다. 큰 커밋은 critic이 검증하기 어렵고, 작은 커밋은 실패 격리 단위가 된다. Spring Batch의 Step 분리와 같은 원칙이다.

### 피해야 할 약한 답변

- 'Claude Code 썼습니다 / 생산성 N배 됐습니다'로 끝내기 — 구조 설계 언어가 빠져 있다.
- '에이전트한테 시키면 다 됩니다'라고 답하기 — 환각 / 세션 단절 / 역할 혼재 같은 실제 부딪힌 문제와 해법이 빠지면 설계자가 아니라 관찰자로 보인다.
- '개인 프로젝트라 가능했습니다'로 축소 — 팀 전파 경험(Cursor Rules 20+, 신규 게임 3종)을 연결하지 못하면 조직 기여 가능성을 의심받는다.

### 꼬리 질문 5개

**F4-1.** critic 에이전트의 APPROVE/REVISE 판정 기준을 어떻게 설계했나요? 같은 계획에 대해 critic이 반복해서 REVISE를 내면 어떻게 벗어나나요?

**F4-2.** docs-verifier가 ADR이 1,581줄까지 비대해진 것을 지적해 700줄로 줄였다고 하셨는데, '에이전트 컨텍스트 효율'과 '사람 가독성'이 충돌할 때 어느 쪽을 우선하시나요?

**F4-3.** 4인 역할 분리가 단일 에이전트보다 안정적인 이유를 '같은 모델이라도 역할 프롬프트가 다르면 다른 시야로 본다'고 하셨는데, 이 주장을 재현 가능한 방법으로 검증한 경험이 있으신가요?

**F4-4.** 커머스 팀에 합류한다면 이 방법론의 어떤 조각(예: docs-first ADR, critic 게이트, 파일 소유권 매트릭스)을 가장 먼저 도입해야 한다고 보시나요? 도입 순서의 근거는?

**F4-5.** 디자이너 vibe 결과물을 /integrate-ux 스킬로 흡수했다고 하셨는데, 사람 개발자의 PR에도 같은 '자동 정합성 변환' 아이디어를 적용할 수 있을까요?

---

## 메인 질문 5. Gemini 모델 전략을 pro 기본 → 429 시 flash → lite fallback으로 설계하시고, 여기에 전역 Rate Limit Tracking과 Project 단위 Context Cache를 결합하셨습니다. 왜 '싼 모델이 결과적으로 비싸다'고 판단했는지, 그리고 429 재시도를 30초 대기 대신 즉시 fallback으로 바꾼 이유를 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 비용 최적화를 '단가'가 아니라 '총 호출 횟수(재생성 포함)'로 보는지, 즉 품질-비용 트레이드오프를 시스템 레벨로 사고하는지를 확인한다.
- Rate Limit이 분산 시스템의 상태 문제임을 이해하고, 메모리 Map 기반 전역 트래킹 같은 구체적 설계를 스스로 내놓을 수 있는지를 본다.
- Context Cache 같은 프레임워크별 최적화 API를 '어디에 왜 쓰는지' 용도 기반으로 설명할 수 있는지를 검증한다.

### 실제 경험 기반 답변 포인트

- 처음에는 flash가 기본이었다. pro 대비 1/4 비용에 빠르니 자연스러운 선택이었다. 며칠 써 보니 운영자가 결과물을 보고 '다시 해야겠다'고 느끼면 총 비용이 오히려 증가한다는 패턴이 보였다.
- 판단 기준을 뒤집었다: '단가가 싼 모델'이 아니라 '한 번에 만족하는 확률이 높은 모델'이 결과적으로 더 싸다. pro를 기본으로 쓰고 429가 뜨면 flash → lite로 품질·비용을 순서대로 포기하는 fallback 체인으로 바꿨다.
- 재시도 정책: 처음에는 429 후 30초 대기 → 재시도를 했는데, Gemini TPM은 1분 단위로 풀리므로 30초 대기는 대부분 또 실패했다. '대기는 비싸고 실패율도 낮추지 못한다.' 대신 429 즉시 다음 fallback 모델로 넘어가는 구조가 더 빠르고 안정적이었다.
- 전역 Rate Limit Tracking: 429를 받은 모델을 Map<modelName, skipUntilTimestamp>로 마킹. 다른 요청들은 그 시간 동안 해당 모델을 건너뛰고 바로 fallback으로 간다. 분산된 재시도 로직이 아니라 전역 공유 상태가 필요한 이유 — 독립적으로 재시도하면 같은 429를 여러 번 반복해 비효율이 쌓인다.
- Project 단위 Context Cache: 63만자 원작 소설은 Analysis/Treatment/Conti/Continuation 등 5단계가 모두 참조한다. 매번 보내면 단계마다 수십만 토큰을 재결제. cachedContent로 묶으면 만료(5분) 안의 호출은 입력 토큰 비용이 거의 0.
- 통합 분석(Step1)도 같은 사고의 결과다. 5개 영역 별도 호출 → 분당 160만 토큰으로 TPM 한도에 거의 닿음. Structured Output 기반 1회 호출로 합쳐 토큰 75% 절감, 26.8s → 13.1s. API 호출 경계와 논리적 경계가 꼭 같아야 하지는 않다.

### 1분 답변 구조

- 비용을 '단가'가 아니라 '총 호출 횟수(재생성 포함)'로 봤습니다. flash는 싸지만 품질이 부족해 재생성이 일어나면 결과적으로 더 비쌌고, pro는 한 번에 만족하는 확률이 훨씬 높았습니다. 그래서 pro 기본 + 429 시 flash → lite fallback으로 전략을 뒤집었습니다.
- 429 후 30초 대기는 Gemini TPM이 1분 단위로 풀리는 구조 때문에 대부분 또 실패했습니다. 대기는 비싸고 실패율도 낮추지 못했기에, 즉시 다음 fallback 모델로 넘기는 쪽이 빠르고 안정적이었습니다.
- 분산 요청이 독립적으로 재시도하면 같은 429를 여러 번 반복해 비효율이 쌓이므로, Map<modelName, skipUntilTimestamp> 전역 상태로 '지금 막힌 모델'을 공유해 모두가 함께 fallback하도록 했습니다.
- Project 단위 Context Cache로 63만자 소설을 다섯 단계가 공유 참조하게 해 매 호출마다 수십만 토큰을 재결제하는 낭비를 없앴습니다. 같은 맥락에서 Step1 소설 분석의 5개 영역도 Structured Output 1회 호출로 합쳐 토큰 75% 절감과 26.8s→13.1s를 얻었습니다.

### 압박 질문 방어 포인트

- '처음부터 pro를 썼으면 fallback이 필요 없지 않나?' → pro도 TPM 한도가 있고 429가 난다. fallback은 '품질 하락을 감수하더라도 서비스 연속성을 지킨다'는 의사결정이지, pro 선택 실수의 보완이 아니다.
- '전역 상태는 서버 여러 대로 확장되면 Redis 같은 걸로 바꿔야 하는데?' → 맞다. 이 구조는 MVP 단계 단일 인스턴스 기준 설계였고, 확장되면 Redis로 승격하는 것이 자연스러운 다음 단계다. Fallback 우선순위 정책은 그대로 유지된다.
- 'Context Cache 5분 만료는 너무 짧지 않나?' → Gemini 플랫폼 제약이다. 대안은 Project 생성 시점에 cache를 지연 생성하지 않고 단계 진입 시마다 refresh하거나, 5분 내 연속 호출이 보장된 순차 실행 흐름을 설계하는 것이다. 후자를 택했다.

### 피해야 할 약한 답변

- 'pro가 성능이 좋아서 썼습니다' — 비용 관점 없이 품질만 얘기하면 시니어 수준의 설계 판단이 아니다.
- '429는 어쩔 수 없이 대기합니다' — 재시도 정책의 근거(1분 TPM 리셋)를 모른 채 표준 지연 전략만 언급하는 답.
- 'Context Cache 썼습니다'로 끝내기 — 왜 Project 단위인지, 만료와 refresh 흐름을 어떻게 맞췄는지 설명하지 못하면 API 사용자 수준의 이해로 보인다.

### 꼬리 질문 5개

**F5-1.** Map<modelName, skipUntilTimestamp>의 skipUntil 값은 무엇을 기준으로 결정했나요? 429 응답 헤더의 Retry-After와 실제 관측치의 차이는 어떻게 맞추셨나요?

**F5-2.** Pro → Flash fallback 시 프롬프트 Grounding 준수력이 약해져 환각이 다시 등장한다고 하셨는데, 이 문제를 모니터링하거나 자동 감지하는 구조를 설계한다면 어떻게 하시겠어요?

**F5-3.** Gemini Context Cache의 cachedContent 만료(5분) 안에 호출이 끝나지 않으면 다음 단계가 비용 이득을 못 봅니다. 단계 순서와 타이밍을 어떻게 짰나요?

**F5-4.** Step1 통합 분석이 토큰 75% 절감과 속도 2배를 얻었는데, 반대로 '논리적 경계를 쪼개 두는 게 유리한 경우'는 어떤 시그널로 판단하시나요?

**F5-5.** 커머스의 상품 검색 쿼리 LLM Rewriting 같은 흐름에 같은 전략을 쓴다면, 캐시 단위와 fallback 체인을 어떻게 설계하시겠어요?

---

## 최종 준비 체크리스트

- 각 답변에서 'NHN 경험 → CJ 올리브영 커머스 접합면(Kafka/Redis/MSA/대용량 색인)'으로 연결되는 브릿지 문장을 한 번 이상 넣었는지 점검.
- 숫자(199 plan / 760 커밋 / 12일, 447 테스트 파일, 11 Step, 30초 예산 = 15 + 12 + 3, Step1 토큰 75% 절감, 26.8s → 13.1s)를 외우고 있는지 리허설에서 검증.
- 모든 질문에 '왜 그렇게 했는가'에 대한 트레이드오프 답변을 준비했는지 확인 — '그냥 했다'로 끝나는 답이 없어야 한다.
- 압박 질문(pressureDefense)에 대해 방어 논리 + 반박 수용 지점(한계 인정)을 함께 준비해 '완벽 주장'처럼 들리지 않도록 연습.
- 자기소개 1분 버전을 실제로 녹음해 타임박싱(60±5초) 확인 — 경력/AI 서비스/OCR/웹툰 MVP 네 축이 빠지지 않고 흘러가는지 점검.
- Why 올리브영 파트에서 기술 블로그 4개 글(MSA 데이터 연동 / OAuth2 무중단 / SQS 데드락 / Spring 트랜잭션 동기화) 중 2개 이상을 자연스럽게 인용할 수 있는지 리허설.
- 하네스·AI 경험이 '툴 사용자 자랑'으로 보이지 않고 '파이프라인·아키텍처 설계 경험'으로 정확히 프레이밍되는지 동료 리뷰로 검증.
