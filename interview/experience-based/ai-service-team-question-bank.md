# [초안] AI 서비스팀 경험 기반 면접 질문 은행 — RAG 배치, Graceful Shutdown, 전략 패턴, 하네스 파이프라인

---

## 이 트랙의 경험 요약

- NHN AI 서비스 개발팀 4년차, Spring Batch 기반 Confluence → OpenSearch RAG 벡터 색인 파이프라인을 11개 Step으로 분리해 설계·구현하고 운영
- gRPC OCR 서버 배포·스케일인 시 503 에러를 K8s terminationGracePeriodSeconds 30초 제약 하에서 Envoy + supervisord + SIGTERM 핸들러 예산 재배분으로 제거
- 임베딩 메타데이터 구성을 Blocklist(remove)에서 Allowlist(provider) 전략 패턴으로 전환해 OCP를 회복하고 신규 DocumentType 추가 시 EmbeddingService 무수정 확장 구조 확보
- 12일 동안 단독으로 Next.js 16 + Prisma 7 + Gemini 6단계 풀스택 AI 웹툰 MVP를 199 plan / 760 커밋 규모로 완성, Claude Code 하네스 기반 4인 에이전트 팀(planner/critic/executor/docs-verifier)으로 조율
- Gemini pro→flash→lite fallback과 전역 Rate Limit Tracking, Project 단위 Context Cache, Continuation Grounding 재주입까지 AI 호출 구조의 신뢰성을 직접 설계한 경험

## 1분 자기소개 준비

- 안녕하세요. NHN에서 4년간 게임 백엔드와 AI 서비스 개발을 담당해 온 김병태입니다.
- 최근 2년은 Spring Boot 기반 MSA에서 동시성·이벤트 드리븐·대용량 데이터 처리를 직접 설계하고 운영하는 데 집중해 왔습니다. 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout과 StampedLock으로 해결했고, Kafka @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store 기반 신뢰성 있는 비동기 흐름을 설계했습니다.
- 이후 AI 서비스 개발팀으로 옮겨 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 11개 Step으로 분리해 처음부터 구현했습니다. AsyncItemProcessor로 I/O 병렬화를 잡고, 전략 패턴으로 스페이스별 메타데이터 차이를 흡수했으며, 배포 시 발생한 gRPC 503을 graceful shutdown 예산 재배분으로 제거하기도 했습니다.
- 최근에는 12일 동안 단독으로 Next.js + Gemini 기반 AI 웹툰 제작 도구 MVP를 풀스택으로 구현하면서, Claude Code 하네스 위에서 planner/critic/executor/docs-verifier 4인 에이전트 팀을 직접 조율해 199 plan을 완수했습니다. 이 경험을 통해 단순 코드 작성자가 아니라 파이프라인·하네스 설계자의 시야를 갖게 되었다고 생각합니다.
- 지금까지 쌓아 온 동시성·이벤트·대용량 처리 경험과, AI를 도구가 아니라 아키텍처로 다루는 능력을 1,600만 고객이 쓰는 커머스 플랫폼에 직접 기여하는 데 쓰고 싶어 지원했습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영 커머스플랫폼이 1,600만 고객을 대상으로 빠르고 안정적인 경험을 제공하는 미션을 갖고 있다는 점이, 제가 지난 2년간 집중해 온 '동시성과 대용량 흐름의 신뢰성 설계' 경험과 직접 맞닿아 있다고 생각합니다.
- 기술 블로그에서 본 Cache-Aside + Kafka 하이브리드 데이터 연동, Feature Flag와 Shadow Mode 기반 무중단 OAuth2 전환, Resilience4j 3단계 보호 같은 설계 패턴은 제가 슬롯 게임 서버에서 다중 서버 캐시 정합성을 다뤘던 맥락과 거의 동일한 문제 영역입니다.
- Kafka 비동기 처리에서 @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + traceId 추적까지 직접 설계해 본 경험은 도메인 간 이벤트 연동이 핵심인 커머스 환경에 바로 적용 가능하다고 생각합니다.
- OpenSearch 대규모 벡터 색인을 Step 단위 격리, AsyncItemProcessor, 증분/삭제 동기화까지 운영해 본 경험은, 상품·전시처럼 변경이 잦고 검색 품질이 곧 매출인 도메인의 색인 파이프라인 설계에도 그대로 활용할 수 있다고 봅니다.
- 기능 구현에 그치지 않고 팀이 함께 빠르게 움직일 수 있는 구조 — 추상 템플릿, 전략 패턴, Cursor Rules 20+개, 하네스 파이프라인 — 를 만들어 온 점이 '안정성과 속도를 동시에 추구하는' 올리브영 조직 문화와 잘 맞을 것이라 확신합니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- NHN에서 4년간 사내·B2B 트래픽 중심의 백엔드를 다뤘기 때문에, 이제 1,600만 일반 사용자가 쓰는 대규모 커머스 트래픽 환경에서 제가 설계해 온 패턴이 어떻게 작동하는지 직접 검증하고 싶습니다.
- 동시성·이벤트·대용량 처리 같은 제 강점이 게임/내부 서비스보다 더 도메인이 복잡하고 비즈니스 영향도가 큰 커머스 환경에서 더 큰 난이도로 다뤄지는 것이 다음 성장 포인트라고 판단했습니다.
- AI 서비스팀에서 RAG·하네스·에이전트 협업까지 경험하면서, 단순 '신기술 도입'이 아니라 제품 경쟁력으로 연결되는 환경에 합류하고 싶다는 방향이 또렷해졌습니다.

### 왜 올리브영인가
- 올리브영 커머스플랫폼이 공유한 MSA 데이터 연동 전략(Cache-Aside + Kafka), 무중단 OAuth2 전환, SQS 데드락 분석 같은 글에서 '이론이 아니라 트래픽으로 검증된 설계'를 외부에 진정성 있게 공개하는 조직 문화를 보고 깊은 신뢰가 생겼습니다.
- Resilience4j 3단계 보호, Feature Flag + Shadow Mode, Jitter로 Peak TPS 40% 감소 같은 디테일은 제가 평소 비동기 신뢰성 설계에서 신경 쓰던 지점과 정확히 일치해, 합류 즉시 같은 언어로 논의할 수 있을 것이라 봤습니다.
- 올영세일 같은 평소 대비 10배 트래픽 이벤트가 정기적으로 존재하는 환경은 제가 동시성·캐시 정합성 경험을 가장 빠르게 확장할 수 있는 무대라고 판단했습니다.

### 왜 이 역할에 맞는가
- 커머스플랫폼 백엔드는 상품·전시·주문처럼 도메인이 복잡하고 변경 압력이 강한 영역이라, 제가 슬롯 도메인에서 AbstractPlayService + SpinOperationHandler 인터페이스로 파편화된 로직을 통합한 경험과 직접 매핑됩니다.
- JPA Hibernate 이벤트 리스너, Kafka AFTER_COMMIT, Dead Letter Store, Spring Batch + OpenSearch 증분 색인까지 모두 공고의 우대사항(JPA·Kafka·캐싱·대용량·MSA)에 자연스럽게 들어맞습니다.
- 기능 구현뿐 아니라 테스트 인프라 447개, Cursor Rules 20+개, 하네스 파이프라인까지 '팀 전체의 개발 속도'를 끌어올리는 일을 자발적으로 해 온 점이, 빠른 실험과 안정 운영을 동시에 요구하는 이 포지션에 잘 맞을 것이라 생각합니다.

## 메인 질문 1. Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 11개 Step으로 분리해 설계하셨다고 했는데, 왜 그렇게 잘게 쪼갰는지와 그 결정이 운영에서 어떤 효과를 주었는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 단순히 'Spring Batch 써봤다'가 아니라 Step 분리·재시작·실패 격리에 대한 설계 사고를 가지고 있는지 검증하려는 의도
- 대용량/외부 API 의존 워크로드에서 신뢰성과 운영 비용을 같이 고려하는 시니어 백엔드 개발자인지 가늠하려는 의도

### 실제 경험 기반 답변 포인트

- 워크로드 특성: Confluence REST · 임베딩 API · 문서 파싱 서비스 등 외부 의존이 많고, 각 단계가 다른 종류의 실패(429, 타임아웃, 파싱 실패)를 갖는다는 점에서 단일 Step으로 묶으면 한 종류의 실패가 전체를 무너뜨림
- Step 분리 기준: 시작/종료 마커, 연결 정보 초기화, 스페이스/페이지ID 수집, 페이지·댓글 색인, 페이지·댓글·첨부파일 삭제 동기화, 인덱스 refresh — 각 Step은 단일 책임이며 다음 Step에 필요한 데이터만 컨텍스트로 넘김
- 운영 효과: 댓글 Step이 실패해도 페이지 색인 결과는 보존되고 그 Step부터 재시작 가능, BATCH_JOB_EXECUTION 이력으로 어떤 단계에서 멈췄는지 추적, 재시도 비용이 항상 '실패한 단계 + 그 뒤'로 한정되어 토큰/임베딩 비용도 통제됨
- @JobScope ConfluenceJobDataHolder로 Step 간 도메인 데이터를 인메모리 공유하면서 JobExecutionContext 직렬화 부담을 피했고, 재시작 시 NPE를 피하기 위해 상태 로더 Step에 allowStartIfComplete(true)를 명시

### 1분 답변 구조

- 도입: 외부 API 의존이 많고 단계마다 실패 종류가 다른 워크로드라, 거대한 단일 Step은 한 종류의 실패가 전체를 무너뜨린다는 판단에서 시작했습니다.
- 설계: 시작/종료 마커, 연결 초기화, 스페이스·페이지ID 수집, 페이지/댓글 색인, 삭제 동기화, refresh 까지 11개 Step으로 단일 책임 분리하고, Step 간 데이터는 @JobScope 인메모리 홀더로 넘겨 JobExecutionContext 직렬화 비용을 피했습니다.
- 효과: 댓글 Step이 실패해도 페이지 색인 결과가 살아있고 그 지점부터 재시작이 가능해 임베딩 비용 재발생을 막았으며, 어느 단계에서 어떤 실패가 났는지 BATCH_JOB_EXECUTION 이력만 봐도 추적이 됩니다.
- 마무리: '실패 격리 = 운영 비용 통제'라는 관점에서 Step 분리를 의도적으로 잘게 가져갔고, 재시작 시 상태 로더가 스킵되어 NPE가 나지 않도록 allowStartIfComplete(true)까지 함께 설계했습니다.

### 압박 질문 방어 포인트

- “Step이 너무 많아 오버엔지니어링 아니냐” → 외부 의존 종류와 실패 모드가 그만큼 다르고, 합치는 순간 실패 격리·재시작·이력 추적 이점이 모두 사라집니다. 11개라는 숫자보다 '단일 책임 단위'라는 기준이 본질입니다.
- “그냥 큰 잡 하나에 try/catch면 되지 않냐” → 트랜잭션과 임베딩 API 비용 측면에서 try/catch는 실패 지점부터 재시작을 보장하지 못합니다. Spring Batch가 제공하는 Step 단위 재시작·skip·이력 테이블이 곧 그 보장입니다.

### 피해야 할 약한 답변

- Step을 나눈 이유를 'Spring Batch 권장'이라고만 답하고 외부 API 실패 모드와 비용 관점을 연결하지 못하는 답변
- @JobScope와 JobExecutionContext의 차이를 모르고 '컨텍스트에 다 담았다'고 뭉뚱그려 답하는 답변

### 꼬리 질문 5개

**F1-1.** JobExecutionContext와 @JobScope 빈을 어떤 기준으로 구분해서 쓰셨고, 둘이 잘못 섞이면 어떤 사고가 나나요?

**F1-2.** 재시작 시 상태 로더 Step이 COMPLETED라 스킵되면서 NPE가 발생할 수 있다는 점은 어떻게 발견했고 어떻게 해결하셨나요?

**F1-3.** 삭제 동기화에서 Confluence API의 status=DELETED,TRASHED를 활용하셨는데, 만약 그 파라미터가 없었다면 어떤 대안 설계를 고려하셨을까요?

**F1-4.** 한 Step이 실패한 채로 며칠 누적되면 OpenSearch와 원본 사이에 어떤 종류의 정합성 깨짐이 생길 수 있고, 운영에서는 어떻게 감지하셨나요?

**F1-5.** 이 11 Step 구조를 커머스 상품 검색 색인 파이프라인에 옮긴다면 어떤 Step을 추가/제거하시겠어요?

---

## 메인 질문 2. 임베딩 API 호출이 I/O 바운드라 청크 처리에 AsyncItemProcessor를 쓰셨다고 했는데, CompositeItemProcessor 체이닝과 결합했을 때의 동작 흐름과 트레이드오프를 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- Spring Batch의 비동기 처리 모델을 단순 사용 수준이 아니라 내부 동작과 한계까지 이해하고 있는지 검증하려는 의도
- Future·TaskExecutor·청크 커밋 사이의 트랜잭션/순서 의미를 정확히 다루는 시니어 수준인지 확인하려는 의도

### 실제 경험 기반 답변 포인트

- Composite 체이닝: ChangeFilter(version 비교 → 미변경 시 null로 스킵) → Enrichment(첨부·작성자·멘션 보강) → BodyConvert(ADF→Markdown) → Embedding 순으로 단일 책임을 가진 Processor를 직렬 체이닝
- AsyncItemProcessor 래핑: 위 Composite 전체를 하나의 delegate로 감싸 청크 내 N개 아이템을 parallelChunkExecutor 스레드풀에서 병렬 실행, 결과는 Future<EmbeddedConfluenceDocuments>로 반환
- AsyncItemWriter: Future.get()을 호출해 결과를 모은 뒤 OpenSearch 벌크 색인에 위임하므로, 청크 커밋 단위는 그대로 유지되고 한 청크의 모든 Future가 완료되어야 커밋
- 트레이드오프: I/O 대기를 병렬화해 청크 처리 시간이 크게 줄지만, 한 아이템이 매우 느리면 그 청크 전체가 그 아이템을 기다리게 되며, 스레드풀 사이즈와 임베딩 API rate limit이 충돌하지 않도록 동시성 한도를 같이 튜닝해야 함

### 1분 답변 구조

- 구조: Processor를 ChangeFilter → Enrichment → BodyConvert → Embedding 4단계로 Composite 체이닝하고, 그 전체를 AsyncItemProcessor로 감쌌습니다. Reader가 보낸 아이템이 스레드풀에 풀려 임베딩 API 응답을 동시에 기다리는 구조입니다.
- 결과 처리: AsyncItemProcessor가 반환하는 Future를 AsyncItemWriter가 .get()으로 모아 OpenSearch에 벌크 색인합니다. 청크 커밋은 한 청크의 모든 Future가 완료된 뒤에만 일어나기 때문에 부분 커밋으로 인한 정합성 문제는 생기지 않습니다.
- 효과: 동기 처리 시 청크 하나에 수 분 걸리던 임베딩 단계가 임베딩 API 한 호출 분량 정도로 수렴했고, ChangeFilter가 version 비교로 미변경 문서를 스킵해 임베딩 비용 자체가 크게 줄었습니다.
- 트레이드오프: 청크 내 가장 느린 한 건이 청크 전체를 잡아두므로 스레드풀 사이즈와 임베딩 API의 분당 rate limit을 함께 튜닝해야 하고, 이 부분이 운영에서 가장 신경 쓴 지점이었습니다.

### 압박 질문 방어 포인트

- “그냥 청크 사이즈를 1로 두고 reader 페치를 늘리면 되지 않냐” → 청크 사이즈 1은 커밋 비용·OpenSearch bulk write 효율·재시작 단위가 모두 나빠집니다. 청크 단위는 유지하고 그 안의 I/O만 비동기화하는 게 비용·정합성 측면에서 더 좋습니다.
- “AsyncItemProcessor 쓰면 트랜잭션 컨텍스트가 깨지지 않냐” → 임베딩/외부 API 호출은 트랜잭션 자원이 아니고, 트랜잭션 경계는 청크 커밋(Writer 시점)에 그대로 유지됩니다. 외부 호출 결과만 비동기로 만든 셈입니다.

### 피해야 할 약한 답변

- AsyncItemProcessor를 쓰면 무조건 빠르다고 답하면서 청크 내 가장 느린 아이템이 전체를 막는 한계를 언급하지 않는 답변
- ChangeFilter로 미변경 문서를 스킵하는 비용 절감 효과를 빼고 단순히 '병렬화로 속도 N배'만 강조하는 답변

### 꼬리 질문 5개

**F2-1.** 임베딩 API rate limit과 스레드풀 사이즈는 어떤 관계로 같이 잡으셨나요? 어떤 신호를 보고 조정하셨어요?

**F2-2.** Composite 체이닝 중 ChangeFilter가 null을 반환했을 때 뒤 Processor가 호출되지 않는 이유와, 이걸 잘못 이해하면 어떤 버그가 나는지 설명해 주실 수 있을까요?

**F2-3.** AsyncItemProcessor를 썼을 때 예외가 한 건 발생하면 청크 커밋이 어떻게 되고, Skip/Retry 정책과는 어떻게 상호작용하나요?

**F2-4.** OpenSearch 벌크 색인이 부분 실패하는 경우(일부 도큐먼트만 reject) 운영에서 어떻게 감지하고 재처리하셨나요?

**F2-5.** 이 비동기 구조를 커머스의 상품 인덱싱 같은 도메인에 적용한다면 어떤 부분에서 가장 다른 설계가 필요할 것 같나요?

---

## 메인 질문 3. OCR 서버 배포·스케일인 시 503이 발생하던 문제를 graceful shutdown 미적용 이슈로 진단하고 수정하셨는데, K8s terminationGracePeriodSeconds가 30초로 고정된 환경에서 어떻게 예산을 분배해 해결하셨는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 에러 메시지(ECONNREFUSED, envoy 헤더)에서 트래픽 경로의 어느 계층이 죽었는지 정확히 짚어내는 디버깅 능력 검증
- K8s/리버스 프록시/프로세스 매니저/애플리케이션 시그널 핸들링이 결합된 시스템에서 시간 예산을 직접 설계할 수 있는지 확인

### 실제 경험 기반 답변 포인트

- 증상 진단: 'upstream connect error… delayed connect error: 111' + server: envoy 헤더에서 Envoy는 살아있고 upstream(:50051)이 ECONNREFUSED라는 사실을 분리, 30~60초 주기로 묶음 발생 → 배포/스케일인 이벤트와 일치
- 근본 원인: gRPC 서버 serve()에 SIGTERM 핸들러가 없어서 server.wait_for_termination()이 받자마자 즉시 종료, supervisord stopwaitsecs 미설정으로 기본 10초 후 SIGKILL이 날아가는 이중 문제, preStop sleep 동안 Envoy가 살아 있어 죽은 upstream으로 라우팅
- 예산 설계: NCS의 terminationGracePeriodSeconds=30s 고정 제약 하에서 preStop sleep 20s → 15s로 단축, gRPC server.stop(grace=12s), supervisord stopwaitsecs=17s(=12+5)로 잡아 '15s drain + 12s graceful + 3s 여유 = 30s' 안에 모든 종료가 끝나도록 재배분
- 수정 후 흐름: T+0 preStop drain_listeners → T+15 SIGTERM → T+15~27 in-flight RPC 처리 + 신규 거부 → T+27 정상 종료, 컨테이너 삭제 시점에 upstream이 미리 비워져 있어 503 사라짐

### 1분 답변 구조

- 에러 메시지에서 server: envoy 헤더와 ECONNREFUSED를 보고 'Envoy는 살아있고 :50051이 죽었다'는 사실을 먼저 분리했고, 발생 패턴이 배포/스케일인 시점과 정확히 일치하는 걸 확인했습니다.
- 원인은 gRPC 서버에 SIGTERM 핸들러가 없어 즉시 죽고, supervisord stopwaitsecs도 미설정이라 기본 10초 안에 SIGKILL이 떨어지는 이중 문제였고, 그 사이 Envoy는 죽은 upstream으로 라우팅을 유지하고 있었습니다.
- NCS의 terminationGracePeriodSeconds가 30초로 고정이라 그 안에 모두 끝나야 했고, preStop sleep 20→15초, server.stop(grace=12s), supervisord stopwaitsecs=17s로 예산을 재분배해 'drain 15 + graceful 12 + 여유 3 = 30'으로 맞췄습니다.
- 결과적으로 배포 시 in-flight RPC가 정상 처리되고 신규 요청은 미리 거부되며 컨테이너가 깨끗하게 종료되어 503이 사라졌습니다.

### 압박 질문 방어 포인트

- “그냥 grace를 넉넉히 30초 이상 잡으면 되지 않냐” → NCS는 terminationGracePeriodSeconds가 30초로 고정이고 API에도 노출되어 있지 않아 변경할 수 없었습니다. 주어진 한도 안에서 각 계층 예산을 설계하는 게 유일한 해결책이었습니다.
- “supervisord stopwaitsecs 기본 10초인 줄 몰랐다고 했는데 운영자가 놓친 것 아닌가” → 기본값에 의존한다는 사실 자체가 위험 신호였고, 이번 수정 이후 종료 관련 설정은 항상 명시값으로 강제하고 코드 리뷰 체크리스트에 넣었습니다.

### 피해야 할 약한 답변

- 503의 원인을 단순히 '배포할 때 잠깐 끊긴다'로 설명하고 envoy/upstream/SIGTERM 계층 분석을 빼는 답변
- preStop sleep만 늘리면 된다고 답하고 terminationGracePeriodSeconds 30초 제약 안에서 예산을 어떻게 나눴는지 설명하지 않는 답변

### 꼬리 질문 5개

**F3-1.** preStop sleep 15초 동안 Envoy가 drain되는데, 만약 그 사이에 매우 오래 걸리는 RPC가 들어와 있었다면 어떻게 처리되나요?

**F3-2.** Java/Spring Boot 환경이었다면 같은 문제를 어떻게 다르게 해결하셨을 것 같으세요? (GracefulShutdownPhase, server.shutdown.grace-period 등)

**F3-3.** supervisord 대신 컨테이너 PID 1이 gRPC 서버였다면 SIGTERM 핸들링이 어떻게 달라졌을까요?

**F3-4.** 503 발생 패턴이 30~60초 주기로 묶여 있었던 단서를 어떻게 활용해 문제 영역을 좁히셨나요?

**F3-5.** 이 graceful shutdown 설계를 커머스 트래픽처럼 평소의 10배가 되는 이벤트(올영세일) 환경으로 옮긴다면 어떤 부분을 추가로 보강하시겠어요?

---

## 메인 질문 4. 임베딩 메타데이터 구성을 Blocklist에서 Allowlist 전략 패턴(EmbeddingMetadataProvider)으로 뒤집은 결정의 배경과, 그 구조가 OCP를 어떻게 회복시켰는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 기존 코드의 냄새를 단순히 '복잡해서'가 아니라 OCP·가독성·테스트 용이성 같은 원칙으로 진단하는 시야가 있는지 검증
- 전략 패턴 같은 디자인 패턴을 교과서가 아니라 실제 설계 의도와 함께 적용한 경험인지 확인

### 실제 경험 기반 답변 포인트

- Before의 냄새: EmbeddingService가 cloneMetadata 후 14개 remove를 호출하고 DocumentType 별 if-else를 중첩, 새 타입 추가 시 EmbeddingService를 수정해야 해 OCP 위반, '실제 무엇이 들어가는지' 역산해야 해 가독성도 저하
- 전환 원칙: 제거할 필드 관리(blocklist) → 포함할 필드 명시(allowlist)로 뒤집고, EmbeddingMetadataProvider 인터페이스에 getSupportedDocumentTypes / provide(Document) 두 메서드를 둬서 각 구현체가 자기가 담당할 타입을 스스로 선언
- 계층화: AbstractEmbeddingMetadataProvider(공통 putIfNotNull/putFormattedDatetime) → AbstractCollabToolEmbeddingMetadataProvider(협업도구 공통 필드) / AbstractConfluenceEmbeddingMetadataProvider(title/subject 폴백) → 각 도메인 구현체로 트리 구성
- DI 자동 등록: Spring이 List<EmbeddingMetadataProvider>를 주입 → flatMap으로 DocumentType→Provider 맵 빌드 → EmbeddingService는 위임만 수행, 결과적으로 EmbeddingService의 14개 remove와 if-else가 모두 사라지고 신규 타입은 @Component 추가만으로 확장 가능

### 1분 답변 구조

- Before는 EmbeddingService가 cloneMetadata 후 14개 remove를 부르고 DocumentType 분기까지 중첩되어 있어, 새 타입이 추가될 때마다 같은 파일을 수정해야 했고 '실제 무엇이 임베딩에 들어가는지'도 remove를 역산해야 알 수 있었습니다.
- 그래서 '제거할 필드 관리'가 아니라 '포함할 필드를 명시한다'로 관점을 뒤집어 EmbeddingMetadataProvider 인터페이스를 만들고, 각 구현체가 자기가 담당하는 DocumentType을 스스로 선언하게 했습니다.
- 공통 부분은 Abstract 계층으로 끌어올렸고(협업도구 공통 / Confluence 공통 / Confluence는 title→subject 폴백 등), Spring이 List<Provider>를 자동 주입하면 Config에서 DocumentType→Provider 맵으로 빌드해 EmbeddingService는 lookup 후 위임만 하면 되도록 정리했습니다.
- 결과적으로 EmbeddingService에서 14개 remove와 if-else가 사라지고, 새 DocumentType은 @Component 구현체 추가만으로 확장돼 OCP가 회복됐습니다.

### 압박 질문 방어 포인트

- “그냥 if-else 정리만 해도 되지 않냐” → if-else를 정리해도 책임이 EmbeddingService에 그대로 남아 새 타입마다 같은 파일을 수정해야 합니다. 책임을 '담당 타입을 아는 객체'로 옮기지 않으면 OCP는 회복되지 않습니다.
- “전략 패턴이 오버엔지니어링이라는 의견은 어떻게 생각하냐” → 적용 전 14개 remove의 가독성·신규 타입 추가 비용·테스트 단위 분리 곤란을 직접 겪은 뒤 도입한 결정이었고, 도입 후에 코드 라인이 줄고 테스트가 구현체별로 깨끗하게 분리됐다는 점이 그 판단의 근거입니다.

### 피해야 할 약한 답변

- 전략 패턴을 'GoF 책에 나오는 패턴이라 적용했다'고 답하고 Blocklist 한계와 OCP 위반 같은 구체적 동기를 못 짚는 답변
- Provider가 자기 DocumentType을 어떻게 선언하고 Spring이 어떻게 맵으로 묶이는지 흐름을 설명하지 못하는 답변

### 꼬리 질문 5개

**F4-1.** 한 DocumentType을 두 Provider가 동시에 선언하면 어떤 일이 벌어지고, 이를 어떻게 방지하셨나요?

**F4-2.** Confluence Provider가 title 대신 subject로 폴백하는 케이스처럼 도메인 차이가 늘어나면 인터페이스 자체를 바꿔야 하는 압력이 생깁니다. 어디까지를 인터페이스로 흡수하고 어디부터를 구현체로 분기시키는 기준이 있으세요?

**F4-3.** Allowlist 방식이 오히려 위험한 케이스(예: 누락 필드가 검색 품질에 직결)는 어떻게 감지하고 보강하셨나요?

**F4-4.** 이 구조를 커머스의 상품/리뷰/검색 쿼리 같은 다양한 인덱스 타입에 적용한다면 어떤 추가 추상화가 필요할 것 같나요?

**F4-5.** 전략 패턴 도입 전후 테스트 코드는 어떻게 달라졌고, 어떤 종류의 회귀 버그가 줄었나요?

---

## 메인 질문 5. 12일 동안 단독으로 199개 plan과 760 커밋을 처리하며 AI 웹툰 제작 도구 MVP를 풀스택으로 만드셨다고 했는데, Claude Code 하네스와 4인 에이전트 팀을 어떻게 설계했고, 그것이 결과물의 안정성에 어떤 차이를 만들었는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI/에이전트 협업을 단순한 '도구 사용'이 아니라 파이프라인·아키텍처 설계 영역으로 이해하고 직접 만든 경험인지 검증
- Gemini fallback, Rate Limit Tracking, Context Cache, Continuation Grounding 같은 신뢰성 설계를 시니어 백엔드 시야로 다룰 수 있는지 확인

### 실제 경험 기반 답변 포인트

- 출발점: 처음에는 단일 세션 vibe 코딩이었으나, 길어지면 컨텍스트 한도·잘못된 가정·반복 결정 비용 문제가 누적되어 'spec 기반 코딩'으로 전환 — /planning(Opus)으로 8단계 합의 → tasks/planNNN/index.json + phase 파일 생성
- 재시작 가능 실행: /plan-and-build의 run-phases.py가 index.json의 pending phase부터 순차 실행, phase 파일이 자기완결적이라 세션이 끊겨도 같은 git 상태에서 이어받기 가능
- 4인 에이전트 팀: planner(설계) / critic(계획↔코드 정합성 APPROVE/REVISE 게이트) / executor(구현) / docs-verifier(ADR·data-schema 정합성) — 자기가 짠 계획을 자기가 검증하지 못한다는 한계를 별도 역할 분리로 해결
- AI 호출 신뢰성 설계: Gemini pro→flash→lite fallback + 전역 Rate Limit Tracking Map(429 모델 일정 시간 skip) + Project 단위 Context Cache로 원작 소설 토큰 재결제 방지 + Continuation 호출에 Grounding 블록 매번 재주입(ADR-132)으로 환각 차단 + 캐릭터 외형 고정은 텍스트 anti-drift가 아닌 기본 시트 이미지 자동 prepend로 해결(ADR-133/134)

### 1분 답변 구조

- 초기 vibe 코딩은 길어질수록 컨텍스트 한도와 잘못된 가정 비용이 누적돼서, /planning을 Opus로 8단계 합의해 task 파일을 만들고 그 task를 실제 실행하는 /plan-and-build 하네스로 'spec 기반 코딩'으로 전환했습니다.
- phase 파일을 자기완결적으로 만들어 세션이 끊겨도 git 상태만 있으면 이어받을 수 있게 했고, planner/critic/executor/docs-verifier 4인 에이전트 팀으로 역할을 분리해 자기가 짠 계획을 자기가 검증하는 맹점을 제거했습니다.
- AI 호출 신뢰성도 별도로 설계했습니다. Gemini pro→flash→lite fallback에 전역 Rate Limit Tracking Map을 둬서 429를 받은 모델은 일정 시간 skip하고, 원작 소설은 Project 단위 Context Cache로 묶어 단계마다 재결제되지 않게 했습니다.
- 환각 문제는 'continuation이 tail 5컷만 보고 있던' 호출 구조 결함을 잡는 게 본질이었고, Grounding 블록을 continuation에 매번 재주입하고 캐릭터 외형은 텍스트가 아니라 기본 시트 이미지를 자동 prepend해서 해결했습니다. 이 분업 구조가 없었다면 12일 / 199 plan 볼륨은 불가능했다고 봅니다.

### 압박 질문 방어 포인트

- “AI가 다 짜준 거 아니냐” → 모델은 실행을 분담했지만, planning에서의 트레이드오프 결정·역할 분리 구조 설계·Continuation Grounding 같은 호출 구조 설계는 모두 사람이 한 판단입니다. 에이전트는 그 결정의 80%가 task 파일에 박혀 있을 때만 안정적으로 동작합니다.
- “그냥 하나의 강한 모델로 돌리면 되지 않냐” → 같은 모델이라도 critic 역할을 받으면 시야가 달라집니다. 자기 계획을 자기가 검증하면 잘 못 본다는 게 12일간 가장 또렷이 본 패턴이라 역할 분리가 핵심이었습니다.

### 피해야 할 약한 답변

- Claude Code를 '코드 자동완성 도구'로만 설명하고 planning/critic/executor/docs-verifier 분업 구조와 docs-first 원칙을 빼는 답변
- Gemini fallback을 단순히 '쌌다/빨랐다'로만 설명하고 전역 Rate Limit Tracking·Context Cache·Continuation Grounding의 호출 구조 설계 의도를 못 짚는 답변

### 꼬리 질문 5개

**F5-1.** critic이 APPROVE/REVISE를 내릴 때 어떤 신호를 기준으로 판단하도록 프롬프트를 설계하셨나요? 잘못된 APPROVE를 줄이기 위해 어떤 가드레일을 두셨어요?

**F5-2.** 전역 Rate Limit Tracking을 단일 프로세스 메모리 Map으로 두셨다고 했는데, 이걸 멀티 인스턴스 환경(예: 커머스 백엔드)으로 옮기면 어떻게 다시 설계하시겠어요?

**F5-3.** Continuation에 Grounding을 매번 재주입하면 토큰이 늘어나는 비용이 생기는데, Project 단위 Context Cache와 결합해 비용을 어떻게 회수하셨나요?

**F5-4.** 캐릭터 외형 고정 문제를 텍스트 anti-drift가 아니라 이미지 레퍼런스 prepend로 해결한 결정의 일반화 가능한 원칙은 무엇이라고 보시나요?

**F5-5.** 이 하네스/에이전트 팀 구조에서 얻은 교훈 중, 1,600만 사용자 커머스 백엔드 팀에 가져와도 가치가 있는 것이 있다면 어떤 부분일까요?

---

## 최종 준비 체크리스트

- 1분 자기소개에서 '게임 백엔드 4년 → AI 서비스팀 RAG/하네스 설계 → 12일 풀스택 MVP'의 흐름이 자연스럽게 이어지는지, 면접 직전에 한 번 소리 내어 점검할 것
- 지원동기에서 올리브영 기술 블로그(MSA 데이터 연동, 무중단 OAuth2, SQS 데드락, Spring 트랜잭션 동기화) 4편을 인용 가능한 수준으로 다시 한 번 정리해 둘 것
- Spring Batch 11 Step / AsyncItemProcessor / @JobScope vs JobExecutionContext / allowStartIfComplete 같은 디테일은 화이트보드에서 그릴 수 있게 손으로 한 번 그려보고 갈 것
- OCR 503 사례에서 '15s drain + 12s graceful + 3s 여유 = 30s' 예산 분배를 숫자 그대로 말할 수 있게 외우고, Java/Spring Boot에서 동일 문제를 어떻게 풀지 미리 답안 한 줄을 준비해 둘 것
- 전략 패턴 사례는 'Blocklist→Allowlist + OCP + Spring DI 자동 맵 빌드'를 30초 안에 설명할 수 있도록 프레이즈를 다듬어 둘 것
- AI 웹툰 MVP 답변에서 '도구 사용자가 아니라 파이프라인 설계자' 톤을 유지하기 위해 critic·docs-verifier 역할 분리와 Continuation Grounding 재주입 사례를 한 문장씩 외워 둘 것
- 압박 질문(‘오버엔지니어링 아니냐’, ‘AI가 다 짜준 거 아니냐’)에 대한 한 줄 방어 답변을 카드처럼 정리해 면접 직전 훑어볼 것
- 각 사례마다 '커머스 도메인으로 옮긴다면 어떻게 다르게 설계하겠는가'에 대한 한 문단 답을 미리 준비해 follow-up에 즉시 응답 가능하도록 할 것
