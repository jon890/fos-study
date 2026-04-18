# [초안] AI 서비스 개발팀 경험 기반 면접 질문 뱅크 — CJ 올리브영 커머스플랫폼 Back-End

---

## 이 트랙의 경험 요약

- AI 서비스 개발팀에서 설계·구현한 네 가지 축을 커버: (1) Spring Batch 11 Step RAG 벡터 색인 파이프라인, (2) gRPC OCR graceful shutdown 503 장애, (3) 임베딩 메타데이터 전략 패턴 전환, (4) 12일 단독 풀스택 AI 웹툰 MVP와 하네스 설계.
- 올리브영 커머스플랫폼 공고의 핵심 요구(MSA/Kafka/Cache-Aside/대용량 데이터·트래픽·ORM 도메인 모델링)와 경험을 직접 연결해, 상품 검색·전시·주문 도메인에 이식 가능성을 구체 근거로 제시한다.
- 시니어 백엔드 관점에서 설계 의도·트레이드오프·실패 사례·대안 검토를 중심에 두고, AI/에이전트 협업은 '툴 사용자'가 아닌 '파이프라인·아키텍처 설계자' 레벨로 드러낸다.
- 각 질문은 1분 답변 구조와 압박 질문 방어, 피해야 할 약한 답변, 5개 후속 질문을 함께 제공해 실전 라이브 면접에서 즉시 쓸 수 있도록 구성했다.
- 자기소개·지원동기·회사 적합성 영역을 추가해, 게임→AI→커머스 트랙 전환의 서사와 1,600만 트래픽 도메인 적합성을 함께 정리했다.

## 1분 자기소개 준비

- NHN에서 4년차로 Spring Boot 기반 MSA 백엔드를 개발하고 있는 김병태입니다. 처음 2년은 소셜 카지노 슬롯 팀에서 멀티 서버 인메모리 캐시 동기화(RabbitMQ Fanout + StampedLock)와 Kafka Transactional Outbox를 설계했고, 최근 1년은 AI 서비스팀에서 사내 RAG용 Confluence → OpenSearch 벡터 색인 배치를 11 Step 파이프라인으로 처음부터 구축했습니다.
- 주력 기술은 Java 21 / Spring Boot 3 / JPA-Hibernate / Kafka / Redis / Spring Batch / OpenSearch이고, 도메인 모델링과 확장 가능한 구조 설계에 강점이 있습니다. 흩어진 스핀 로직을 AbstractPlayService 템플릿으로 통합하고 SpinOperationHandler 인터페이스로 위임한 리팩터링, 임베딩 메타데이터를 blocklist에서 EmbeddingMetadataProvider 기반 allowlist로 전환한 OCP 리팩터링이 대표적입니다.
- 최근 12일 동안은 AI 웹툰 제작 도구 MVP를 단독으로 풀스택 구현했습니다. Next.js 16 + Prisma 7 + Gemini 기반 6단계 파이프라인으로, 199 plan / 760 커밋 규모를 Claude Code 하네스 기반 4인 에이전트 팀(planner/critic/executor/docs-verifier)으로 조율하면서 '툴 사용자'가 아닌 파이프라인 설계자 경험을 쌓았습니다.
- 설계·구현·운영·장애 대응(gRPC 503 graceful shutdown 예산 설계 포함)까지 전 과정을 직접 경험했고, 팀의 개발 속도와 안전망을 높이는 구조 개선(테스트 447개, ADR 134개 유지)에 꾸준히 투자해 왔습니다.
- 앞으로는 이 경험을 1,600만 고객이 사용하는 커머스 도메인의 대규모 트래픽·복잡 도메인 환경에서 검증하고 기여하고 싶어 올리브영 커머스플랫폼 백엔드에 지원했습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영 기술 블로그의 MSA 데이터 연동 전략(Cache-Aside + Kafka Event-Driven 하이브리드)은 제가 NHN에서 풀었던 다중 서버 캐시 정합성 문제와 정확히 같은 축입니다. RabbitMQ Fanout 기반 이벤트 발행 + StampedLock 기반 읽기/쓰기 보호로 갱신 중 정합성 오류를 2.5초 타임아웃으로 해결한 경험을, 실시간성이 중요한 상품/전시 캐시 무효화에 바로 적용할 수 있습니다.
- Kafka Transactional Outbox(@TransactionalEventListener(AFTER_COMMIT) + REQUIRES_NEW + traceId 저장 + 스케줄러 재전송)를 설계·운영한 경험이, 주문·결제·알림·전시처럼 메시지 유실이 곧 장애인 커머스 도메인 이벤트 연동에 그대로 재사용될 수 있습니다.
- Spring Batch 11 Step으로 RAG 벡터 색인 파이프라인(증분 변경 감지, 첨부파일/삭제 동기화, AsyncItemProcessor I/O 병렬화, OpenSearch 벌크 색인)을 설계한 경험은, 상품 검색 색인·증분 동기화·삭제 반영 같은 커머스 검색 인프라 설계와 동일한 문제 공간입니다.
- gRPC OCR 서버 배포 시 발생한 503을 NCS의 terminationGracePeriodSeconds 30초 제약 안에서 preStop 15s + gRPC grace 12s + 여유 3s로 예산 설계해 해결한 경험은, 트래픽 10배 피크에서 무중단 전환을 다뤄야 하는 커머스 배포 환경에 직접 이식 가능합니다.
- JPA Hibernate PostCommitUpdateEventListener로 커밋 시점 기준 캐시 무효화를 구현하고, Decorator 패턴으로 흩어진 도메인 로직을 응집시키며 static → DI 전환으로 테스트 가능성을 높인 ORM/도메인 모델링 경험이 상품·전시·주문 도메인 모델링 요구사항과 직결됩니다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- 지난 4년간 쌓은 캐싱·이벤트·배치·도메인 설계 역량이 게임/사내 AI 서비스를 넘어 대규모 커머스 트래픽 환경에서 어떻게 작동하는지 직접 검증하고 싶습니다. 1,600만 고객 규모는 제가 경험한 문제의 크기를 한 단계 확장시키는 무대라고 생각합니다.
- 지금까지는 사내 또는 B2C 게임 사용자 대상이었지만, 실제 매출·재고·프로모션처럼 비즈니스 임팩트가 즉시 드러나는 도메인에서 설계 결정의 책임을 지고 싶습니다. 기술 결정이 숫자로 환산되는 환경에서 의사결정 근육을 키우고 싶습니다.
- AI 도구가 일상화되면서 '무엇을 만들지'가 더 중요한 시대라는 걸 12일간 단독 MVP에서 체감했고, 복잡한 도메인과 대규모 제약이 있는 곳에서 이 흐름을 제품 아키텍트 수준으로 확장하고 싶습니다.

### 왜 올리브영인가
- 기술 블로그의 MSA 데이터 연동 전략(Cache-Aside + Kafka 하이브리드), 대규모 트래픽 중 무중단 OAuth2 전환(Feature Flag + Shadow Mode + Resilience4j 3단계 방어), SQS 데드락 분석기에서 팀이 실제 운영 문제를 정면으로 다루고 글로 남기는 문화를 확인했습니다. 이 레벨의 엔지니어링 문화가 제가 더 성장할 수 있는 환경입니다.
- 올리브영은 오프라인과 온라인이 얽힌 리테일 커머스라, 재고·전시·상품·주문·검색 도메인이 단순 웹 커머스보다 훨씬 복잡합니다. 복잡 도메인 모델링에 투자해 온 제 이력과 문제 궁합이 좋습니다.
- 커머스플랫폼유닛이 '빠르고 안정적인 고객 경험'을 팀 미션으로 명시한 점이, 제가 꾸준히 중요하게 여겨온 '속도와 안정성 동시 추구'와 같은 방향이어서 합류 후 가치관 충돌 없이 곧바로 기여할 수 있다고 판단했습니다.

### 왜 이 역할에 맞는가
- 공고의 우대 사항(Spring Boot / MSA / Kafka / 다양한 캐싱 전략 / 대용량 데이터·트래픽 / Docker·K8s)이 제가 NHN에서 실제로 설계·운영한 축과 거의 1:1 매핑됩니다. 러닝 커브 없이 초기 3개월 안에 핵심 파이프라인 한 축에서 자기 몫을 하는 목표가 현실적입니다.
- 상품·전시·검색은 제가 RAG 벡터 색인 파이프라인에서 다뤄온 '대규모 문서 증분 색인·삭제 동기화·메타데이터 전략' 문제와 구조적으로 같습니다. OpenSearch 기반 색인 운영 경험을 커머스 검색 인프라에 바로 이식할 수 있습니다.
- JPA/Hibernate 기반 도메인 모델링, Kafka Transactional Outbox, Cache-Aside 정합성, Circuit Breaker/Timeout/Retry 3단계 방어 같은 주제에서 원리 수준의 대화가 가능합니다. 시니어 백엔드로서 설계 회의에 즉시 기여할 수 있는 포지션입니다.

## 메인 질문 1. Spring Batch 기반 Confluence → OpenSearch 벡터 색인 파이프라인을 11개 Step으로 쪼갠 이유와, 특히 @JobScope 데이터 홀더와 AsyncItemProcessor를 도입한 설계 결정의 근거를 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- Spring Batch의 Step 분리·청크 처리·재시작성에 대한 원리 이해 깊이를 본다. 단순히 '돌아가는 배치'를 넘어 설계 의도와 트레이드오프를 언어화할 수 있는지 확인한다.
- 대용량 I/O 바운드 작업(임베딩/파싱 API)을 병렬화할 때 AsyncItemProcessor/Writer 조합을 고르게 된 이유, 그리고 @JobScope와 JobExecutionContext 중 왜 전자를 선택했는지로 Spring 생명주기·스코프 이해도를 평가한다.
- 커머스 상품 검색 색인 같은 비슷한 도메인에 경험을 어떻게 이식할지도 엿본다.

### 실제 경험 기반 답변 포인트

- Step을 11개(초기화 → 스페이스 수집 → 페이지 색인 → 페이지ID 수집 → 댓글 색인 → 삭제 동기화 3종 → 인덱스 리프레시 → 완료 기록)로 분리한 핵심 이유는 '실패 격리'와 '재시작성'. 댓글 Step이 실패해도 페이지 Step 결과는 살아 있고, 실패 지점부터 재시작 가능하다.
- 데이터 공유에 JobExecutionContext를 쓰지 않고 @JobScope 빈(ConfluenceJobDataHolder)으로 옮긴 이유: JobExecutionContext는 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블에 직렬화되어 수천 개 페이지 ID를 매 커밋마다 읽고 쓰는 게 낭비다. JobExecutionContext는 재시작용 커서 위치 같은 경량 상태 전용으로 쓰는 게 맞다.
- @JobScope는 내부적으로 ScopedProxyMode.TARGET_CLASS 프록시여서 싱글톤에 안전하게 주입되지만, 재시작 시 새 JobExecution이 생기고 빈도 초기화된다. 상태 로더 Step이 COMPLETED로 스킵되면 NPE가 나므로 allowStartIfComplete(true)로 재실행 보장.
- 임베딩/문서 파싱 API가 전부 I/O 바운드. 동기면 청크(10) 처리에만 ~2초가 깔린다. AsyncItemProcessor로 Future<Item>을 반환하고 AsyncItemWriter가 Future.get()으로 모아 OpenSearch 벌크 색인. CompositeItemProcessor로 ChangeFilter(version 비교 스킵) → Enrichment → ADF→Markdown → Embedding 4단계 체이닝해 각 단계 단일 책임 유지.
- 이 구조가 커머스 상품/검색 색인·증분 동기화·삭제 반영과 동일한 문제 공간이라 이식 가능성이 높다.

### 1분 답변 구조

- 11 Step 분리의 본질 이유는 실패 격리와 재시작성이다. 하나의 거대 Step이면 중간 실패 시 처음부터 다시 돌려야 하지만, Step 단위면 성공한 앞 Step 결과가 보존되고 실패 지점부터 이어서 돈다.
- Step 간 대용량 데이터(수천 건의 페이지 ID) 공유는 JobExecutionContext가 아니라 @JobScope 빈으로 했다. 청크마다 DB에 직렬화되는 비용을 피하기 위해서다. 재시작 시 NPE를 막으려 상태 로더 Step엔 allowStartIfComplete(true)를 걸었다.
- 임베딩과 문서 파싱은 I/O 바운드라 동기 처리는 치명적으로 느리다. AsyncItemProcessor + AsyncItemWriter로 청크 내 병렬화했고, 전처리는 CompositeItemProcessor로 4단계 체이닝해 단일 책임을 유지했다. ChangeFilter는 version 비교로 미변경 문서를 스킵해 임베딩 비용을 크게 줄였다.
- 이 설계는 커머스 상품/검색 색인 증분 파이프라인에 바로 매핑된다.

### 압박 질문 방어 포인트

- Q: AsyncItemProcessor 쓰면 청크 트랜잭션/실패 복구가 헷갈리지 않나? — A: Writer 시점에 Future.get()으로 모으므로 예외는 청크 Writer에서 터진다. 실패 청크는 skip/retry 정책으로 처리하고, 영속 실패는 ChangeFilter 쪽 실패 횟수 임계치로 자동 스킵해 무한 재시도로 빠지지 않게 했다.
- Q: @JobScope 대신 외부 저장소(Redis/DB)에 두는 게 더 안전하지 않나? — A: 데이터 수명은 단일 Job 실행 범위여서 외부 저장소는 과잉이다. 여러 인스턴스가 동일 Job을 나눠 실행하는 파티셔닝 구조가 된다면 그때 외부 저장소로 승격할 계획.

### 피해야 할 약한 답변

- 'Spring Batch가 좋아서 썼다' 식으로 선택 근거를 일반론으로 말하는 답변. 스케줄러 대비 Spring Batch의 구체 이점(재시작성, 청크, 실행 이력)과 실제 장애 시나리오를 연결해야 한다.
- AsyncItemProcessor의 반환이 Future라는 점과 AsyncItemWriter가 Future.get()을 호출한다는 구조를 설명 못 하면 '써봤다' 수준으로만 보인다.
- @JobScope와 @StepScope, JobExecutionContext의 차이를 뭉뚱그려 말하는 답.

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor의 Future는 어느 시점에 resolve되고, 예외는 어떤 경로로 전파되나요?

**F1-2.** 재시작 시 ChangeFilter가 version 비교로 스킵하는 문서와 Spring Batch의 ExecutionContext 기반 커서 재시작은 어떻게 상호작용하나요?

**F1-3.** @JobScope와 @StepScope의 스코프 생명주기 차이, 그리고 싱글톤 빈에 주입될 때 프록시 동작을 설명해 주세요.

**F1-4.** CompositeItemProcessor에서 단계별 실패율이 다를 때, 재시도/스킵 정책을 어떻게 설계하셨나요?

**F1-5.** 이 파이프라인을 커머스 상품 색인에 이식한다면 어떤 Step을 추가/제거하고, 어떤 메트릭을 가장 먼저 꽂겠습니까?

---

## 메인 질문 2. OCR gRPC 서버 배포 시 503이 묶음으로 발생하던 문제를 어떻게 원인 분석하고, NHN Cloud Container Service의 terminationGracePeriodSeconds 30초 고정 제약 안에서 어떻게 예산을 설계해 해결했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 분산 시스템 장애를 에러 로그(envoy 111 ECONNREFUSED)에서 구체 원인(SIGTERM 즉시 종료)으로 좁혀 가는 추론력.
- K8s 파드 종료 시퀀스(preStop → SIGTERM → grace → SIGKILL)와 envoy/supervisord/gRPC 서버의 상호작용을 이해하는지, 그리고 플랫폼 제약(grace 30초 고정) 안에서 설계 예산을 짤 수 있는지 본다. 커머스의 무중단 배포 요구와 직결된다.

### 실제 경험 기반 답변 포인트

- 1차 증상 파악: 503 묶음 발생이 배포/스케일인 이벤트와 정확히 시간 일치. 응답 헤더 server: envoy, reset reason 111(ECONNREFUSED)로 envoy는 살아 있고 upstream(50051) 연결이 거부되는 구조임을 확인.
- 원인 두 가지: (a) gRPC 서버가 SIGTERM 핸들러를 구현하지 않아 즉시 종료, (b) supervisord의 stopwaitsecs 미지정(기본 10s)으로 핸들러를 붙여도 SIGKILL 위험. 결과적으로 preStop의 envoy drain_listeners + sleep 20 동안 upstream이 먼저 죽는 역전이 발생.
- NCS가 terminationGracePeriodSeconds를 30초로 고정해 API 스펙으로 변경 불가. 모든 종료 작업을 30초 안에 끝내야 하므로 예산을 preStop sleep 15s + gRPC grace 12s + 여유 3s = 30s로 재설계.
- 수정: (a) server_grpc_general_OCR.py에 signal.SIGTERM 핸들러로 server.stop(grace=12) 호출, (b) supervisord.conf에 stopwaitsecs=17(grace 12 + 여유 5), (c) Jenkinsfile의 preStop을 sleep 20 → 15로 단축. 결과적으로 envoy drain 완료 후 SIGTERM이 들어와도 in-flight RPC가 정상 처리된 뒤 종료되도록 순서 보장.
- 교훈: graceful shutdown은 단일 컴포넌트가 아니라 envoy ↔ supervisord ↔ app의 '종료 순서 체인'으로 봐야 한다. 플랫폼 제약이 상수로 주어지면 제약 안에서 예산을 나누는 게 설계자의 역할.

### 1분 답변 구조

- 증상은 배포/스케일인과 시간이 정확히 겹치는 503 묶음이었고, envoy의 111 ECONNREFUSED 헤더로 upstream 조기 사망을 확인했다.
- 원인은 두 가지였다. gRPC 서버에 SIGTERM 핸들러가 없어 즉시 죽었고, supervisord의 stopwaitsecs 기본값 10초 때문에 핸들러를 붙여도 SIGKILL 위험이 있었다.
- NCS는 terminationGracePeriodSeconds를 30초로 고정해 바꿀 수 없으므로, preStop 15s + grace 12s + 여유 3s로 예산을 나눴다. gRPC 서버에 signal.SIGTERM 핸들러를 붙여 server.stop(grace=12)를 호출하게 하고, supervisord stopwaitsecs=17, preStop sleep을 20→15로 단축했다.
- 수정 후에는 envoy drain 완료 이후 SIGTERM이 gRPC에 도착해 in-flight RPC가 정상 종료되는 순서가 보장됐다. 503은 사라졌다.

### 압박 질문 방어 포인트

- Q: 그냥 terminationGracePeriodSeconds를 늘리면 되지 않나? — A: NCS는 이 값을 고정해 API 스펙으로도 변경할 수 없어서 선택지가 아니었다. 플랫폼 제약이 상수면 그 상수 안에서 예산을 나눠야 한다.
- Q: SIGKILL이 와도 envoy가 걸러주지 않나? — A: envoy는 upstream 연결 거부를 503으로 변환해 클라이언트로 돌려준다. 조기 사망이 곧 503이라 envoy가 방패가 되지 못한다. 예산으로 순서를 강제하는 것이 유일한 해법이었다.

### 피해야 할 약한 답변

- 'graceful shutdown을 붙였습니다'로 끝나고 예산 배분·순서 보장의 원리를 언어화하지 못하는 답.
- 원인을 '아마 envoy 설정 문제'로 추정만 하고 111 ECONNREFUSED → upstream 조기 사망이라는 직접 증거를 들지 못하는 답변.
- supervisord의 stopwaitsecs가 기본 10초라는 점을 놓쳐 SIGKILL 가능성을 무시하는 설명.

### 꼬리 질문 5개

**F2-1.** preStop hook과 SIGTERM이 같은 시간축에서 어떻게 겹치고, 왜 envoy drain을 preStop에 두어야 했는지 설명해 주세요.

**F2-2.** 만약 terminationGracePeriodSeconds가 15초로 줄어든다면 예산을 어떻게 재분배하시겠습니까? 어떤 부분을 희생하나요?

**F2-3.** gRPC의 server.stop(grace)가 내부적으로 어떤 일을 하며, in-flight RPC와 신규 RPC를 어떻게 구분하나요?

**F2-4.** 쿠버네티스 Service가 파드를 endpoints에서 제외하는 시점과 SIGTERM이 들어오는 시점 사이의 경쟁 조건은 어떻게 방어하셨나요?

**F2-5.** 커머스 무중단 배포 관점에서 이 패턴을 WAS/Spring Boot 기반 서비스에 이식한다면, Spring Boot의 어떤 설정과 actuator 엔드포인트를 함께 써야 할까요?

---

## 메인 질문 3. 임베딩 메타데이터 구성을 14개 remove 호출 방식(blocklist)에서 EmbeddingMetadataProvider 기반 allowlist로 바꾸신 배경과, 전략 패턴·OCP를 실제 코드 레벨에서 어떻게 강제했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- '디자인 패턴을 책으로 안다'가 아니라 실제 리팩터링에서 OCP 위반 증상을 식별하고, 해소 구조를 설계·검증할 수 있는지 본다.
- Spring DI와 @StepScope 충돌 같은 실전 함정(NoUniqueBeanDefinitionException)을 만나 본 사람인지, 그리고 추상화 수준을 정할 때 유지보수 비용과 가독성을 어떻게 저울질하는지 확인한다.

### 실제 경험 기반 답변 포인트

- 문제: EmbeddingService가 메타데이터를 '전체 복사 후 불필요한 필드 remove(14개)' 하는 blocklist 방식. DocumentType이 늘면 분기가 늘고, 실제 포함 필드가 역산해야 보이고, cloneMetadata/putMetadata 같은 보조 메서드가 부풀어 OCP 위반이 누적.
- 해결 아이디어: '제거할 필드'가 아니라 '포함할 필드'를 구현체가 명시. EmbeddingMetadataProvider 인터페이스(getSupportedDocumentTypes + provide(Document) → Map)로 추상화.
- 계층화: AbstractEmbeddingMetadataProvider(공통 유틸 putIfNotNull/putFormattedDatetime) → AbstractCollabToolEmbeddingMetadataProvider / AbstractConfluenceEmbeddingMetadataProvider로 소스별 공통 필드 응집 → 구현체(Task/Wiki/DriveFile/Confluence)가 자기 도메인 특화 필드만 추가.
- Spring DI로 List<EmbeddingMetadataProvider>를 주입받아 DocumentType → Provider Map으로 빌드. EmbeddingService는 Map에서 lookup 후 위임만 한다. 새 DocumentType 추가 시 EmbeddingService 수정 불필요.
- 실전 함정 해소: 두 배치 잡이 같은 타입의 @StepScope 빈을 각자 등록해 NoUniqueBeanDefinitionException이 났던 문제. 공용 빈은 @Component @StepScope로 전역 등록, 잡 특화 빈은 Config에서만 @Qualifier로 명시 주입. 테스트에서도 @Qualifier를 맞춰야 한다는 점이 초기 함정.
- 부수 효과: cloneMetadata/getMetadataValue/putMetadata 3종의 보조 메서드가 자연스럽게 삭제됐고, 구현체별 단위 테스트가 독립됐다.

### 1분 답변 구조

- 문제는 blocklist 방식의 구조적 누수였다. DocumentType이 늘 때마다 remove 분기가 늘고, 어떤 필드가 실제 전달되는지 역산해야 보여 가독성과 OCP 모두 무너지고 있었다.
- 해결은 '제거'가 아닌 '포함'을 선언하는 전략 패턴이다. EmbeddingMetadataProvider 인터페이스에 getSupportedDocumentTypes와 provide를 두고, Abstract 계층으로 공통 필드를 응집시킨 뒤 구현체마다 자기 도메인 필드만 추가한다.
- Spring DI로 List 주입을 받아 DocumentType → Provider Map으로 빌드하면 EmbeddingService는 lookup + 위임만 한다. 새 타입 추가에 EmbeddingService를 수정하지 않는 OCP가 코드 구조로 강제된다.
- @StepScope 중복 등록 충돌은 공용 빈을 @Component @StepScope로 전역화하고 잡 특화 빈만 Config에서 @Qualifier로 명시 주입해 풀었다. 결과적으로 cloneMetadata 등 보조 메서드가 삭제됐고, 구현체별 단위 테스트가 가능해졌다.

### 압박 질문 방어 포인트

- Q: 단순 if-else 분기가 한 곳에 모여 있으면 오히려 디버깅은 쉬운 거 아닌가? — A: 도메인 타입이 3~4개까지는 맞는 말. 여기서는 이미 DocumentType이 10개를 넘었고 신규 스페이스마다 포맷(title vs subject)이 달라지는 압력이 커서 한계에 닿았다. 분기 증가 속도가 유지보수 속도를 앞지를거라는 신호를 보고 전환한 것.
- Q: 전략 패턴이 과한 추상화가 될 수도 있지 않나? — A: 추상화 수준을 올린 게 아니라 기존에 흩어져 있던 분기를 옮긴 것뿐이다. 구현체 개수만큼만 클래스가 늘었고, 각 클래스가 1~2개 메서드뿐이라 과잉은 아니라고 판단했다.

### 피해야 할 약한 답변

- 전략 패턴을 '인터페이스 + 구현체' 정도로만 설명하고 OCP/Spring DI/실제 버그(NoUniqueBeanDefinitionException)와 엮어 말하지 못하는 답.
- cloneMetadata/getMetadataValue 같은 보조 메서드가 왜 함께 사라졌는지 설명 못 하는 답. 증상이 해소됐다는 증거를 보여 주지 못한다.
- Provider들이 어떻게 Spring DI로 연결되는지(List 주입 → Map 빌드) 구조를 말하지 못하는 답.

### 꼬리 질문 5개

**F3-1.** getSupportedDocumentTypes를 Provider가 직접 반환하게 한 이유는? 대안으로 애노테이션 기반 매핑도 있을 텐데 트레이드오프는 무엇인가요?

**F3-2.** AbstractCollabTool과 AbstractConfluence를 같은 추상 클래스로 합치지 않고 따로 둔 기준은 무엇이었나요?

**F3-3.** @Component @StepScope 전역 빈과 Config의 @Bean @StepScope 빈이 공존할 때 우선순위와 충돌 규칙은 어떻게 되나요?

**F3-4.** 메타데이터 규격이 JSON 스키마로 외부에 공개되어야 한다면, Provider 기반 구조를 어떻게 확장하시겠습니까?

**F3-5.** 이 패턴을 커머스의 상품 검색 색인 메타데이터(카테고리/프로모션/브랜드 속성)에 이식한다면 어떤 경계에서 구현체를 나누시겠습니까?

---

## 메인 질문 4. 12일 동안 단독으로 AI 웹툰 제작 도구 MVP를 199 plan / 760 커밋 규모로 쌓으면서 Claude Code 하네스 기반 에이전트 팀을 어떻게 설계·운영하셨는지, 그리고 그 과정에서 얻은 '툴 사용자'가 아닌 '파이프라인 설계자' 관점의 교훈은 무엇인지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI 협업을 생산성 도구 차원이 아니라 '역할 분리된 에이전트 팀을 설계·조율하는 아키텍처'로 인식하고 운영했는지 확인한다.
- spec 기반 코딩으로 이행하면서 무엇을 명시하고 무엇을 위임했는지, 그리고 이를 팀 협업(디자이너 합류)으로 확장했을 때의 파일 소유권·Container/Presenter 구조 같은 설계 언어를 갖고 있는지 본다.

### 실제 경험 기반 답변 포인트

- 파이프라인 구조: 6단계(작품 기획 → 캐릭터/배경 → 스토리 각색 → 글콘티 → 이미지 컷 → [Phase2]동영상). 각 단계가 자기완결 산출물을 가지며 앞 단계 수정 시 이후 확정이 연쇄 해제되는 상태 머신을 갖는다.
- 하네스 진화 5단계: (1) vibe 코딩 → (2) /planning으로 8단계 스펙 합의 후 task 생성 → (3) /plan-and-build로 phase 분할 + 재시작 가능 실행(index.json + phase 파일) → (4) /build-with-teams로 critic·docs-verifier 게이트 추가 → (5) /integrate-ux로 디자이너 vibe 결과물 흡수.
- 4인 에이전트 팀: planner(설계)·executor(구현)·critic(계획-코드 정합성 APPROVE/REVISE 판정)·docs-verifier(ADR/data-schema 드리프트 감지). 자기 계획을 자기가 검증하지 않는 '역할 분리' 원칙이 핵심.
- 모델 전략(ADR-072): pro 기본 + 429 시 flash → lite fallback + 전역 Rate Limit Tracking(Map<string, number>)으로 429 모델을 일정 시간 skip 처리. 재시도 30초 대기는 TPM 윈도우(1분)와 맞지 않아 제거하고 fallback 즉시 전환.
- 토큰 비용 설계: 원작 소설은 Project 단위 Gemini Context Cache로 5단계(Analysis/Content-review/Treatment/Conti/Continuation)가 공유. 통합 분석(ADR-059)으로 5개 영역을 하나의 Structured Output으로 묶어 토큰 75% 절감, 26.8s→13.1s.
- 환각 차단 본질(ADR-132): continuation 호출이 tail 5컷만 보고 있어 grounding이 사라진 상태에서 생성하고 있었음. 프롬프트 최상단에 grounding 블록 박고 continuation마다 재주입. '허용되는 창의는 연출, 서사는 grounding'처럼 도망갈 자리를 주는 것이 핵심.
- 캐릭터 외형 고정(ADR-133/134): 텍스트 anti-drift의 채널 mismatch를 인지하고, 기본 시트 개념(isDefault=true 1개 보장) + 자동 레퍼런스 prepend + outfit 모드로 이미지 채널에 이미지 신호를 줬다.
- 타입 경계(ADR-131): Action=Zod(외부 도메인), Repository=Prisma Input(ORM semantic), 경계에 mapper. 단일 소스 강박을 버린 판단.
- 디자이너 협업(ADR-129/130): semantic 토큰(@theme inline) + Container/Presenter + Layout Primitives + 파일 소유권 매트릭스로 git conflict 거의 0으로 줄임.

### 1분 답변 구조

- 12일 760 커밋은 제가 타이핑한 결과가 아니라, 역할 분리된 4인 에이전트 팀(planner/executor/critic/docs-verifier)을 하네스로 조율한 결과입니다.
- 가장 큰 전환은 vibe 코딩에서 spec 기반 코딩으로의 이동이었습니다. /planning으로 8단계 스펙을 먼저 합의해 task 파일에 결정의 80%를 박아 두고, /plan-and-build로 phase를 쪼개 재시작 가능하게 실행하고, critic이 '계획이 현재 코드에서 실행 가능한지'를 APPROVE/REVISE로 판정하게 했습니다.
- 모델 전략은 퀄리티가 결국 총비용을 줄인다는 관찰에 따라 pro 기본 + 429 시 flash→lite fallback으로 바꾸고, 전역 Rate Limit Tracking Map으로 skip 대상을 공유했습니다. 원작 소설은 Project Context Cache로 5단계가 공유하고, 5개 분석 영역을 하나의 Structured Output으로 묶어 토큰 75%를 아꼈습니다.
- 환각 차단은 프롬프트 카피라이팅이 아니라 호출 구조 설계였습니다. continuation이 tail만 보던 구조를 바꿔 grounding을 매번 재주입한 게 본질적 해법이었습니다. 디자이너 협업은 파일 소유권 매트릭스 + Container/Presenter로 git conflict를 거의 없앴습니다.
- 정리하면 AI 협업은 '사람이 툴을 쓰는 것'이 아니라 '어떤 에이전트에게 어떤 역할과 컨텍스트를 주는가'라는 아키텍처 설계 문제였습니다.

### 압박 질문 방어 포인트

- Q: 결국 AI가 다 한 거라 본인의 기여가 뭔가? — A: 제 기여는 '무엇을 할지' 쪽에 집중됐습니다. task 파일의 결정, 하네스 파이프라인 구조, 에이전트 역할 분리, 모델 전략, 환각 차단 구조, 파일 소유권 룰 같은 상위 판단이 산출물의 품질을 좌우했습니다. vibe 코딩으로는 이 볼륨이 절대 나오지 않습니다.
- Q: critic·docs-verifier 역할 분리가 정말 의미가 있나? 같은 모델인데? — A: 같은 모델이라도 역할에 맞는 시스템 프롬프트를 받으면 다른 시야로 봅니다. 자기 계획을 자기가 검증하는 건 구조적으로 잘 안 됩니다. 별도 컨텍스트로 critic을 돌렸더니 잘못된 가정을 실행 전에 잡는 빈도가 눈에 띄게 올라갔습니다.

### 피해야 할 약한 답변

- AI 도구 사용 경험을 'Claude를 잘 썼다'는 수준으로 서술하는 답. 역할 분리·spec 기반 이행·재시작성 같은 설계 언어가 없으면 시니어 평가에서 힘이 빠진다.
- 모델 전략을 '저가 모델로 비용 최적화'로 요약하는 답. 재생성 비용까지 포함한 총비용 관점(퀄리티 기본 + 선택적 fallback)이 빠지면 설계자의 판단 근육이 안 보인다.
- 환각 차단을 '프롬프트를 잘 쓰면 된다'로 요약하는 답. continuation 구조에 grounding을 재주입한다는 호출 구조 수준 해법을 설명해야 한다.

### 꼬리 질문 5개

**F4-1.** plan-and-build에서 phase 파일을 '자기완결적'으로 만든다는 원칙을 어떻게 코드 레벨·템플릿 레벨에서 강제했나요?

**F4-2.** critic이 REVISE를 반복해서 낼 때 무한 루프를 막기 위한 장치는 무엇인가요?

**F4-3.** Gemini Context Cache의 만료(5분)와 Project 단위 공유를 어떻게 오케스트레이션해 캐시 미스를 최소화했나요?

**F4-4.** 60컷 일괄 생성을 SSE에서 클라이언트 Promise.allSettled로 바꾼 결정의 트레이드오프는 무엇이었나요?

**F4-5.** 이 하네스 파이프라인을 커머스 백엔드의 반복 개발 사이클(API 스펙 → 구현 → 테스트 → 문서)로 이식한다면 어떤 에이전트 역할을 먼저 만들고, 어떤 보장을 설계하시겠습니까?

---

## 메인 질문 5. Gemini 모델 사용에서 pro→flash→lite fallback, 전역 Rate Limit Tracking, Project 단위 Context Caching을 함께 설계하신 이유와, 이 세 요소가 상호 보완하는 구조를 상세히 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 외부 API를 단순 호출하는 수준이 아니라 Rate Limit·비용·지연·품질의 4차원 트레이드오프를 동시에 관리하는 아키텍트적 사고를 하는지 본다.
- 커머스 환경의 외부 의존(결제/검색/추천/광고 API) 안정화 설계(Resilience4j 3단계, Circuit Breaker, Timeout, Retry)와 직접 연결되는 사고 틀인지 확인한다.

### 실제 경험 기반 답변 포인트

- 출발점 관찰: 저가 모델(flash)은 단가가 싸도 운영자가 '다시 해야겠다'고 느끼면 재생성 비용이 누적돼 총비용이 오히려 증가한다. 단가가 아니라 '성공까지 걸린 호출 수' 기준으로 비용을 재정의.
- 전략(ADR-072): pro 기본, 429 발생 시 flash → lite fallback. 퀄리티를 기본값으로 하고 연속성만 열화 허용.
- 전역 Rate Limit Tracking(ADR-069): 429를 받은 모델을 Map<modelKey, skipUntilTimestamp>에 마킹해 일정 시간 skip. 다른 요청 스레드/에이전트가 같은 모델을 다시 두드려 429를 유발하는 비효율을 차단. 프로세스 내 공유 상태로 동시성 제어.
- 재시도 30초 대기 제거: TPM은 1분 윈도우로 회복되는데 30초 대기는 너무 짧아 또 실패한다. fallback으로 즉시 넘기는 게 총 지연/비용 모두에서 유리.
- Project 단위 Context Cache: 원작 소설(수십만 토큰)을 5단계(Analysis/Content-review/Treatment/Conti/Continuation)가 공유. 만료 5분 안에 들어오는 호출은 입력 토큰 비용이 0에 수렴.
- 통합 분석(ADR-059): 5개 영역을 개별 호출→하나의 Structured Output으로 통합. 토큰 75% 절감, 26.8s→13.1s. API 경계와 논리 경계를 분리해 Structured Output 스키마 필드로 논리 분리를 유지.
- 상호 보완: Rate Limit Tracking은 '어느 모델이 지금 막혀 있는가', Fallback은 '막혔을 때 어디로 갈 것인가', Context Cache는 '그래도 호출은 줄인다'를 담당. 세 축이 동시에 작동해야 비용/지연/품질이 같이 잡힌다.
- 한계 인식: Pro fallback 후 grounding 준수력이 약해져 환각이 다시 등장하는 미해결 과제를 투명하게 관리. 서비스 연속성 우선.

### 1분 답변 구조

- 저가 모델로 최적화하려다 퀄리티 불만족 → 재생성 루프를 보고 비용 정의를 단가에서 '성공까지의 호출 수'로 바꿨습니다. 그래서 pro를 기본으로 두고 429 시에만 flash → lite로 fallback하도록 전략을 뒤집었습니다.
- 전역 Rate Limit Tracking은 429 받은 모델을 일정 시간 skip 대상으로 공유 Map에 올려 다른 호출이 같은 모델을 반복해 때리지 않게 합니다. 30초 재시도 대기는 TPM 1분 윈도우와 맞지 않아 제거했습니다.
- Context Cache는 원작 소설을 Project 단위로 묶어 5단계 호출이 공유하게 해 입력 토큰 비용을 0에 수렴시켰고, 통합 분석으로 5개 영역을 하나의 Structured Output에 묶어 토큰 75%를 추가로 줄였습니다.
- 세 축은 역할이 겹치지 않습니다. Rate Limit Tracking은 '지금 어디가 막혔나', Fallback은 '그럼 어디로 갈까', Cache는 '어차피 호출은 줄이자'를 각각 담당해 비용·지연·품질을 동시에 관리합니다.

### 압박 질문 방어 포인트

- Q: Rate Limit Tracking을 메모리 Map으로 했는데 다중 인스턴스에선 안 깨지나? — A: MVP 스케일에서는 단일 프로세스 스코프로 충분했고, 확장 시 Redis 같은 공유 저장소로 올릴 계획입니다. 실제로 429가 스파이크성이라 프로세스 간 동기화 비용이 이득보다 커질 수 있다는 점도 고려했습니다.
- Q: fallback이 퀄리티를 떨어뜨려 환각이 돌아오는데 그래도 쓴 이유는? — A: 서비스 연속성이 더 큰 손실이라 판단했습니다. 대신 fallback 시 환각 약화라는 한계를 문서에 투명하게 기록해, 해당 구간의 운영자 리뷰 강도를 높이는 식으로 운영 절차로 보완했습니다.

### 피해야 할 약한 답변

- '429 나면 retry 하면 된다'로 요약되는 답. retry 간격·TPM 윈도우·fallback 순서를 구분해 말하지 못한다.
- Context Cache를 단순 응답 캐시와 구분하지 못하는 답. '입력 토큰 비용을 줄이는 prefix 공유' 개념을 설명해야 한다.
- 단가 기반 비용 최적화만 이야기하고 '재생성 포함 총비용' 관점이 없는 답.

### 꼬리 질문 5개

**F5-1.** 모델 fallback 순서(pro→flash→lite)를 결정할 때 어떤 기준(품질/지연/가격)을 어떤 가중치로 두셨나요?

**F5-2.** Rate Limit Tracking Map에 어떤 키 설계를 쓰고, skipUntil의 초기값은 어떤 근거로 정했나요?

**F5-3.** Context Cache 만료(5분)와 호출 스케줄을 어떻게 맞춰 cache hit 비율을 높였나요?

**F5-4.** 통합 Structured Output 분석(ADR-059)의 단점(장애 반경 확대, 부분 실패 재시도 난이도)은 어떻게 관리하셨나요?

**F5-5.** 이 세 축(Fallback/Tracking/Cache) 개념을 커머스의 외부 의존(결제 PG, 검색, 광고 API)에 이식한다면 Resilience4j/Redis/Circuit Breaker와 어떻게 결합하시겠습니까?

---

## 최종 준비 체크리스트

- 네 가지 대표 경험(RAG 벡터 색인 파이프라인 / gRPC 503 graceful shutdown / 임베딩 메타데이터 전략 패턴 / AI 웹툰 MVP + 하네스)을 각각 1분 답변 버전과 상세 버전으로 구두 연습했는지 확인.
- 커머스 도메인으로의 이식 가능성(상품/전시/주문/검색/무중단 배포/외부 API 복원력)을 각 질문마다 최소 한 문장으로 연결할 수 있는지 리허설.
- Spring Batch(@JobScope vs @StepScope vs JobExecutionContext, AsyncItemProcessor의 Future 흐름), JPA/Hibernate 이벤트 리스너, Kafka Transactional Outbox(AFTER_COMMIT + REQUIRES_NEW), Cache-Aside + StampedLock 같은 원리 질문에 2단 깊이로 답할 수 있도록 점검.
- ADR 번호(072/069/059/132/133/134/131/129/130) 중 압박 질문에서 인용할 2~3개를 선별해 배경·결정·대안·결과 구조로 말할 수 있도록 준비.
- 자기소개(1분)·지원동기·회사 적합성(올리브영 기술 블로그 4편 요약 반영)을 각각 독립적으로 암송 가능하도록 연습하고, 라이브 코딩·화이트보드에서 꺼낼 수 있는 대표 설계 다이어그램(11 Step RAG, graceful shutdown 타임라인, Provider 계층도) 핸드 스케치 연습.
