# [초안] CJ 올리브영 시니어 Java 백엔드 면접 — AI 서비스 팀 경험 기반 질문 뱅크

---

## 이 트랙의 경험 요약

- AI 서비스 팀 4대 경험(Spring Batch RAG 색인 / OCR 503 Graceful Shutdown / 임베딩 메타데이터 전략 패턴 / 12일 단독 AI 웹툰 풀스택)을 시니어 백엔드 면접 관점으로 압축한 질문 뱅크입니다
- 각 질문은 인터뷰어 의도·답변 핵심 포인트·1분 답변·압박 방어·약한 답변 회피·후속 5문항으로 구성해 실전 시뮬레이션이 가능하도록 설계했습니다
- AI/에이전트 협업 경험은 '툴 사용자'가 아니라 '파이프라인·검증 게이트·역할 분리를 직접 설계한 시스템 설계자' 수준임을 드러내는 데 초점을 맞췄습니다
- 1분 자기소개와 지원 동기/회사 적합성은 AI 서비스 팀 경험을 올리브영 커머스플랫폼유닛 기술 스택(MSA 데이터 연동, 무중단 OAuth2, Cache-Aside + Kafka)과 직접 연결시키는 메시지로 작성했습니다

## 1분 자기소개 준비

- NHN에서 4년차 백엔드 개발자로 일하면서 처음 2년은 소셜 카지노 게임 팀에서 Spring Boot 기반 멀티모듈 MSA의 슬롯 서비스를 담당했고, 이후 AI 서비스 팀으로 옮겨 사내 RAG 파이프라인과 12일 단독 풀스택 MVP를 만들었습니다
- 게임 팀에서는 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout + StampedLock으로, Kafka 후처리 신뢰성을 @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + 스케줄러 재시도로 풀어내며 동시성·이벤트 드리븐 설계를 직접 부딪혀 봤습니다
- AI 서비스 팀에서는 Confluence → OpenSearch 벡터 색인 배치를 11 Step Spring Batch + AsyncItemProcessor로 설계해 I/O 바운드 작업을 병렬화하고 재시작 가능성을 확보했고, 임베딩 메타데이터를 Blocklist→Allowlist 전략 패턴으로 전환해 OCP를 코드 레벨에서 강제했습니다
- 최근에는 Claude Code 기반 4인 에이전트 팀 하네스를 직접 설계해 12일 동안 199 plan / 760 커밋 규모의 AI 웹툰 도구를 혼자 풀스택으로 완성했습니다 — 기능 구현뿐 아니라 팀의 반복 개발 사이클을 단축하는 구조 만들기에 집중하는 개발자입니다

## 올리브영/포지션 맞춤 연결 포인트

- 올리브영 커머스플랫폼유닛이 다루는 Cache-Aside + Kafka 하이브리드, Resilience4j 기반 무중단 배포는 본인이 게임 팀에서 캐시 정합성과 Kafka AFTER_COMMIT 신뢰성으로 풀어온 문제와 결이 같아, 합류 직후 기여 지점이 분명합니다
- JPA·Spring 트랜잭션·이벤트 드리븐·캐싱·대용량 색인까지 우대 사항 항목을 실제 프로덕션에서 설계·운영한 경험이 있고, 특히 OpenSearch 벌크 색인 + 증분/삭제 동기화 경험은 커머스 상품 검색 도메인에 그대로 응용 가능한 자산입니다
- 도메인 추상화·Decorator·전략 패턴으로 파편화된 로직을 정리하고 static 의존을 DI로 전환해 테스트 가능성을 높여온 경험은 상품·전시·주문처럼 복잡한 커머스 도메인 모델링에 그대로 이어집니다
- AI 개발 도구를 단순 사용자가 아니라 4인 에이전트 팀 하네스 설계자로서 다뤄본 경험은 1,600만 고객 서비스의 안정성과 개발 속도를 동시에 끌어올려야 하는 조직에서 차별화된 기여 포인트가 됩니다

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- NHN 4년간 게임 백엔드와 AI 서비스 개발을 통해 MSA·이벤트 드리븐·대용량 색인을 직접 설계·운영했지만, 트래픽 변동 폭이 더 크고 도메인이 더 깊은 커머스 환경에서 같은 기술 스택이 어떻게 동작하는지 직접 검증하고 싶다
- AI 서비스 팀에서 RAG 파이프라인과 12일 단독 풀스택 MVP를 만들면서, 한 사람이 책임지는 범위를 키우는 경험이 가장 큰 성장을 만든다는 걸 체감했다. 1,600만 고객 트래픽에서 같은 책임 범위로 일하고 싶다
- 사내 서비스가 아닌 실제 매출이 일어나는 도메인에서, 캐싱·이벤트·트랜잭션 설계가 비즈니스 지표와 어떻게 연결되는지를 학습하는 것이 다음 4~5년의 중요한 커리어 축이라 판단했다

### 왜 올리브영인가
- 커머스플랫폼유닛 기술 블로그(MSA 데이터 연동 전략, 무중단 OAuth2 전환)에서 Cache-Aside + Kafka 하이브리드, Feature Flag + Shadow Mode + Resilience4j 같은 패턴을 다루는 깊이가 본인이 게임 팀에서 했던 캐시 동기화·Kafka AFTER_COMMIT 설계와 결이 같아, 합류 직후 기여 가능 영역이 분명히 보인다
- 올영세일 같은 평소 대비 10배 트래픽을 무중단으로 처리하는 운영 경험을 가진 조직에서, 본인이 다중 서버 캐시 정합성·Dead Letter Store + 스케줄러 재시도로 다뤘던 신뢰성 설계가 더 큰 트래픽 환경에서 어떻게 변형되는지 직접 부딪혀 보고 싶다
- 1,600만 고객을 대상으로 한 상품·전시·주문 도메인의 모델링 난이도가 본인이 도메인 추상화·Decorator·전략 패턴으로 풀어온 문제와 직접 맞닿아 있어, 단순 구현이 아닌 구조 개선까지 기여할 수 있다고 본다

### 왜 이 역할에 맞는가
- JPA·Spring 트랜잭션·이벤트 드리븐·캐싱 전략·대용량 색인까지 우대 사항 6개 항목 모두 실제 프로덕션에서 설계한 경험이 있고, 특히 AsyncItemProcessor + OpenSearch 벌크 색인 + 증분/삭제 동기화는 커머스 상품 검색 도메인에 그대로 응용 가능한 자산이다
- MSA 환경에서 도메인 데이터를 어떤 데이터는 캐시로, 어떤 데이터는 이벤트로 분리하는 의사결정을 직접 내려본 경험이 있고, 트레이드오프를 ADR로 문서화하는 습관이 있어 팀 의사결정 자산을 늘리는 데 기여할 수 있다
- AI 개발 도구를 단순 사용자가 아니라 4인 에이전트 팀 하네스를 직접 설계해 12일 199 plan을 처리한 경험이 있어, 팀의 반복 개발 사이클을 단축하는 도구 도입까지 함께 끌어올 수 있다

## 메인 질문 1. Confluence → OpenSearch RAG 벡터 색인 배치를 처음부터 설계했다고 하셨는데, 11개 Step으로 쪼갠 이유와 그중 가장 어려웠던 설계 결정을 트레이드오프와 함께 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- Spring Batch를 단순히 '쓸 줄 안다' 수준이 아니라 Job/Step 책임 분리, 재시작성, 청크 처리 같은 핵심 메커니즘을 의식하고 설계했는지를 본다
- 수많은 설계 옵션 중 무엇을 왜 선택했는지를 트레이드오프 언어로 설명할 수 있는 시니어 사고가 있는지 평가한다

### 실제 경험 기반 답변 포인트

- 11 Step 분리 기준은 두 축이다 — (a) 실패 격리: 댓글 색인이 깨져도 페이지 색인 결과가 살아남고 그 Step부터 재시작 가능, (b) 책임 단일화: 수집·변환·임베딩·색인·삭제 동기화가 각각 독립적으로 책임짐
- 가장 어려웠던 결정은 Step 간 데이터 공유 방식이었다. 처음엔 JobExecutionContext에 페이지 ID 수천 개를 넣었는데 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블에 직렬화되는 부하가 컸다. @JobScope 빈(ConfluenceJobDataHolder)으로 옮겨 인메모리 홀더로 분리했다. JobExecutionContext는 재시작용 경량 커서 상태 전용으로 정리
- 재시작 함정도 같이 풀어야 했다. 상태를 채우는 Step이 COMPLETED로 스킵되면 @JobScope 빈이 비어 NPE가 난다. allowStartIfComplete(true)로 재시작 시에도 로더 Step이 반드시 재실행되게 했다
- 임베딩 호출이 I/O 바운드라 청크 하나에 수 분이 걸릴 수 있어, AsyncItemProcessor + AsyncItemWriter로 청크 내 병렬화를 했고, Reader는 ItemStream을 구현해 커서 위치를 ExecutionContext에 저장해 실패 지점부터 이어 받게 했다

### 1분 답변 구조

- 11 Step 분리 기준은 '실패 격리'와 '단일 책임'이고, 한 Step이 깨져도 그 지점부터 재시작 가능한 게 가장 큰 이득이다
- 가장 어려웠던 설계 결정은 Step 간 데이터 공유였다 — JobExecutionContext에 도메인 데이터를 넣었던 초기 구현이 청크 커밋마다 DB 직렬화 부하를 만들어, @JobScope 빈으로 옮기고 JobExecutionContext는 재시작 커서용으로 한정했다
- 재시작 시 상태 로더 Step이 COMPLETED로 스킵되면 빈이 비어 NPE가 나는 함정이 있어 allowStartIfComplete(true)로 보정했다
- I/O 바운드인 임베딩 처리는 AsyncItemProcessor + AsyncItemWriter로 청크 내 병렬화해 처리 시간을 크게 단축했다

### 압박 질문 방어 포인트

- '그냥 한 Step에 다 넣지 그랬냐'고 물으면 — 한 Step이 거대해지면 중간 실패 시 처음부터 재실행해야 하고, 임베딩 API 호출 비용이 다시 발생한다. 11 Step의 운영 비용은 재시작 비용 절감으로 충분히 회수된다고 답한다
- '@JobScope 인메모리 홀더는 분산 환경에서 위험하지 않냐'고 물으면 — 이 배치는 단일 인스턴스에서만 실행되도록 잡 락으로 보장하고, 분산 실행이 필요한 단계가 아니어서 의도적으로 단순화했다고 설명한다
- 'AsyncItemProcessor 스레드풀 크기 산정은 어떻게 했냐'고 물으면 — 임베딩 API의 동시 호출 한도, 청크 사이즈, 한 호출당 평균 응답 시간을 곱해 추정했고, 운영하면서 429 발생률을 보고 조정했다고 솔직히 답한다

### 피해야 할 약한 답변

- 'Spring Batch 좋아서 썼다' 같은 주관적 선호로 답하면 안 된다 — 재시작성·실패 격리·이력 관리 같은 구체 기능과 요구사항이 어떻게 매칭됐는지로 답해야 한다
- 'AsyncItemProcessor 쓰면 빨라진다'로 끝내면 안 된다 — Future 반환, AsyncItemWriter의 Future.get() 호출, 스레드풀 위임이라는 메커니즘과, 동기 처리 시 청크가 직렬 대기로 묶이는 한계를 같이 설명해야 한다

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor의 Future가 AsyncItemWriter에서 어떻게 처리되며, 트랜잭션 경계는 어디에 있는가?

**F1-2.** @JobScope와 @StepScope의 차이, 그리고 ScopedProxyMode.TARGET_CLASS가 싱글톤 빈 주입에서 어떤 역할을 하는가?

**F1-3.** ChangeFilterProcessor가 OpenSearch version과 Confluence version을 비교해 null을 반환하는 설계인데, 이때 임베딩 비용 절감과 데이터 정합성 사이의 트레이드오프는 무엇인가?

**F1-4.** 다중 스페이스 지원을 위해 ConfluenceApiServiceFactory를 도입했는데, 잡 파라미터로 인증 정보를 받는 구조의 보안·운영상 위험은 어떻게 통제했는가?

**F1-5.** 이 배치를 커머스 상품 검색 색인으로 옮긴다면 무엇을 그대로 쓰고 무엇을 바꿔야 한다고 보는가?

---

## 메인 질문 2. OCR 서버 배포 중 503 에러를 Graceful Shutdown 미적용으로 잡았다고 하셨는데, K8s terminationGracePeriodSeconds 30초 제약 안에서 Envoy·supervisord·gRPC 서버까지 어떻게 예산을 분배했고 무엇이 가장 위험했는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 트러블슈팅을 단발성 패치가 아니라 인프라 제약 안에서 시간 예산을 설계하는 시스템 사고로 풀 수 있는지를 본다
- Envoy drain, SIGTERM 핸들러, supervisord stopwaitsecs 같은 종료 시퀀스의 각 레이어를 정확히 이해하고 있는지를 검증한다

### 실제 경험 기반 답변 포인트

- 원인은 두 가지였다 — (a) gRPC 서버에 SIGTERM 핸들러가 없어 즉시 죽었고, (b) supervisord stopwaitsecs 기본 10초가 적용돼 핸들러를 추가해도 SIGKILL 위험이 남아 있었다. 그 결과 Envoy는 살아있는데 upstream 50051이 닫혀 ECONNREFUSED가 503으로 노출됐다
- NCS는 terminationGracePeriodSeconds를 30초로 고정한다. 모든 종료 작업이 30초 안에 끝나야 했다. preStop sleep 15s + gRPC grace 12s + 여유 3s = 30s 예산으로 재설계했다
- 코드/설정 3 곳을 함께 바꿨다 — server_grpc_general_OCR.py에 signal.SIGTERM 핸들러 등록 후 server.stop(grace=12), supervisord.conf의 stopwaitsecs=17(grace 12s + 여유 5s), Jenkinsfile_deploy_real의 preStop sleep을 20→15로 단축
- 수정 후 종료 시퀀스는 T+15s preStop 완료 → SIGTERM → drain 시작 → T+27s 종료로 정렬돼 Envoy가 upstream에 연결 거부를 받지 않게 됐다

### 1분 답변 구조

- 원인은 gRPC 서버에 SIGTERM 핸들러가 없어 즉시 죽으면서 Envoy가 살아있는 채로 upstream 50051에 연결을 못 한 것이고, supervisord stopwaitsecs 기본 10초도 함께 위험했다
- NCS의 terminationGracePeriodSeconds 30초 고정 제약 안에서 preStop 15초 + gRPC grace 12초 + 여유 3초로 예산을 분배했다
- 코드 한 곳이 아니라 server_grpc / supervisord / Jenkinsfile 세 곳을 같이 고쳐야 종료 시퀀스가 정렬됐다
- 가장 위험했던 건 한 레이어만 고치면 다른 레이어의 디폴트가 SIGKILL을 트리거할 수 있다는 점이었고, 시퀀스 도식을 그려 모든 타임라인을 검증한 뒤 적용했다

### 압박 질문 방어 포인트

- 'preStop sleep 자체가 안티패턴 아니냐'고 물으면 — Envoy drain은 비동기로 진행되고 새 요청 차단이 활성화되기까지 시간이 필요해, drain 호출 후 sleep으로 그 윈도우를 보장하는 게 NCS 환경에서는 가장 단순하고 신뢰할 수 있는 방법이라 답한다
- 'Pod readiness probe로 푸는 게 더 정석 아니냐'고 물으면 — terminating 상태에서는 이미 endpoints에서 빠지지만 Envoy의 connection pool에는 잠시 남아 있을 수 있고, 본질적으로 upstream 종료 순서를 맞춰야 했다고 설명한다
- 'gRPC keepalive나 health check로 풀 수도 있지 않냐'고 물으면 — 그것도 보완책이지만 실제 종료 순간의 SIGTERM 비핸들링이 직접 원인이라 일차적으로는 핸들러 + grace 설계가 맞았다고 답한다

### 피해야 할 약한 답변

- 'sleep 늘려서 해결했다'로 끝내면 절대 안 된다 — terminationGracePeriodSeconds 제약 안에서 예산을 어떻게 분배했는지를 반드시 같이 말해야 한다
- 'gRPC에 SIGTERM 핸들러 추가했다'만 말하고 supervisord stopwaitsecs와 preStop 단축을 빼먹으면 안 된다 — 한 레이어만 고치면 또 다른 레이어가 SIGKILL을 만든다는 점이 핵심

### 꼬리 질문 5개

**F2-1.** Envoy drain_listeners API 호출 후 실제로 어떤 동작이 일어나며, 새 요청 차단과 in-flight 처리 완료가 어떤 순서로 보장되는가?

**F2-2.** supervisord stopwaitsecs와 stopsignal의 관계, 그리고 SIGTERM 후 SIGKILL이 발사되는 시점은 어떻게 결정되는가?

**F2-3.** K8s terminationGracePeriodSeconds 안에서 preStop hook과 SIGTERM 핸들러의 실행 순서, 그리고 preStop이 길어지면 컨테이너가 어떻게 강제 종료되는가?

**F2-4.** gRPC의 server.stop(grace) 호출 시 in-flight 스트리밍 RPC와 단방향 RPC가 다르게 처리되는가?

**F2-5.** 이 사례를 일반화해서, 새 마이크로서비스를 NCS에 배포할 때 종료 시퀀스 검증 체크리스트를 만든다면 어떤 항목을 넣겠는가?

---

## 메인 질문 3. 임베딩 메타데이터 구성을 Blocklist(remove) → Allowlist(EmbeddingMetadataProvider)로 전환했다고 하셨는데, 전략 패턴 도입 전후의 코드 구조 차이와 OCP 관점에서 무엇이 본질적으로 바뀌었는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 디자인 패턴을 책의 정의로 외우는 게 아니라 실제 통증에서 출발해 인터페이스 추상화로 푸는 사고의 흐름을 보여줄 수 있는지 본다
- OCP·DI·Spring 자동 등록 같은 기본기를 일관된 설계 결정으로 엮어낼 수 있는 시니어인지 검증한다

### 실제 경험 기반 답변 포인트

- 통증은 명확했다 — EmbeddingService 한 곳에 14개 remove 호출이 모여 있었고, 새 DocumentType이 추가될 때마다 여기에 if-else 분기를 늘려야 했다. '임베딩에 어떤 필드가 들어가나'를 알려면 remove 목록을 역산해야 했다
- 해결의 핵심 한 줄은 '제거할 필드를 관리하지 말고 포함할 필드를 명시하자'였다. EmbeddingMetadataProvider 인터페이스에 getSupportedDocumentTypes()와 provide(Document)만 두고, 각 구현체가 자신이 담당하는 DocumentType을 선언하게 했다
- 공통 필드 중복을 막으려고 AbstractEmbeddingMetadataProvider → AbstractCollabToolEmbeddingMetadataProvider / AbstractConfluenceEmbeddingMetadataProvider 두 단계 추상 클래스로 정리했다. Confluence는 title이 없으면 subject로 폴백하는 도메인 특수성이 있어 별도 추상 클래스로 분리했다
- Spring DI로 List<EmbeddingMetadataProvider>를 자동 주입받아 DocumentType → Provider Map을 빌드한다. EmbeddingService는 Map에서 조회해 위임만 한다. 새 DocumentType은 @Component 구현체 하나만 추가하면 끝나, OCP가 코드 레벨에서 강제된다
- 부산물로 Document.cloneMetadata(), getMetadataValue(String), putMetadata(String) 같은 'remove 패턴 전용' 메서드들이 사라져 도메인 모델이 깨끗해졌다

### 1분 답변 구조

- EmbeddingService 한 곳에 14개 remove 호출이 모여 있고 DocumentType이 늘어날수록 if-else가 누적되는 구조가 문제였다. '제거할 필드를 관리하지 말고 포함할 필드를 명시하자'로 발상을 뒤집었다
- EmbeddingMetadataProvider 인터페이스에 getSupportedDocumentTypes/provide만 두고, AbstractEmbeddingMetadataProvider → 협업도구 / Confluence 두 단계로 추상 클래스를 정리해 공통 필드 중복을 흡수했다
- Spring이 List<EmbeddingMetadataProvider>를 자동 주입하면 DocumentType→Provider Map으로 빌드하고, EmbeddingService는 위임만 한다. 새 DocumentType 추가 시 @Component 한 개만 늘리면 돼 OCP가 코드 레벨에서 강제된다
- 부산물로 cloneMetadata/getMetadataValue/putMetadata 같은 우회 메서드가 삭제돼 도메인 모델이 깨끗해진 것도 큰 이득이었다

### 압박 질문 방어 포인트

- '그냥 if-else 잘 정리하면 되는 거 아니냐'고 물으면 — 분기는 시간이 지나면 반드시 누적되고, 가장 큰 비용은 '어떤 필드가 포함되는지'를 빠르게 답할 수 없는 가독성 손실이라고 답한다. 패턴은 가독성과 변경 영향 범위를 줄이는 도구다
- '전략 패턴을 너무 일찍 도입한 건 아니냐'고 물으면 — DocumentType이 이미 6종을 넘었고 신규 스페이스 요청이 반복적으로 들어오는 시점이라, 지연 도입 비용이 분기 비용을 추월했다고 설명한다
- '추상 클래스 두 단계는 과도한 깊이 아니냐'고 물으면 — Confluence의 title/subject 폴백이 협업도구와 명백히 다른 책임이라 한 추상 클래스로 묶기 어려웠고, 두 계열의 공통 유틸은 최상위에서 흡수했다고 답한다

### 피해야 할 약한 답변

- '전략 패턴이 좋아서 적용했다' 같은 패턴 카탈로그식 답은 안 된다 — 패턴 이전의 통증과 패턴 이후의 OCP·가독성 이득을 구체 코드 변화로 말해야 한다
- 'OCP를 지켰다'만 말하고 Spring DI로 List 주입 + Map 빌드라는 자동 등록 메커니즘을 빼면 시니어 답변이 아니다 — 어떻게 '코드를 안 건드려도 되는 구조'가 강제되는지가 핵심

### 꼬리 질문 5개

**F3-1.** DocumentType 추가가 '오직 @Component 1개'로 끝난다고 했는데, EmbeddingService의 단위 테스트는 어떻게 회귀를 막는가?

**F3-2.** AbstractCollabToolEmbeddingMetadataProvider와 AbstractConfluenceEmbeddingMetadataProvider를 한 추상 클래스로 합치지 않은 결정적 이유는 무엇이며, 합쳤다면 어떤 결합이 생겼겠는가?

**F3-3.** 동일 DocumentType을 두 Provider가 동시에 선언하면 어떻게 감지·실패시키는가? 빌드 타임에 잡을 방법이 있는가?

**F3-4.** 이 패턴을 EmbeddingService 외에 ConfluenceDocumentMetadataProvider로 확장한 사례가 있는데, 두 곳에 동일 패턴이 있다는 건 더 상위 추상화 신호인가 아니면 의도적 분리인가?

**F3-5.** Allowlist 방식의 단점은 '필드 누락' 가능성인데, 운영에서 이를 어떻게 검증하고 모니터링했는가?

---

## 메인 질문 4. 12일 단독으로 AI 웹툰 제작 도구 MVP를 199 plan / 760 커밋 규모로 만들었다고 하셨는데, Claude Code 기반 4인 에이전트 팀(main/executor/critic/docs-verifier) 하네스를 어떻게 설계했고 단일 에이전트 대비 무엇이 본질적으로 좋아졌는지 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI 도구를 '잘 쓰는 사람' 수준이 아니라 파이프라인·역할 분리·검증 게이트를 직접 설계한 시스템 설계자 수준인지 본다
- 혼자 12일에 풀스택 MVP를 끝냈다는 결과가 '운'이 아니라 재현 가능한 워크플로우 설계의 결과임을 입증할 수 있는지 평가한다

### 실제 경험 기반 답변 포인트

- 출발은 vibe 코딩이었다. 한 세션에서 논의·구현·테스트를 다 하니 컨텍스트 한도, 잘못된 가정으로 시작한 작업 폐기, 비슷한 결정 반복이 누적됐다. 본질 통증은 '입력의 정확도가 낮다'는 것이었다
- 1단계 /planning으로 설계와 실행을 분리했다. 8단계 논의(기술 가능성·사용자 흐름·데이터 모델·API 설계·화면 동작·엣지 케이스·마이그레이션·검증)가 합의돼야 task 파일을 만들고, 이 단계만 비싼 Opus를 썼다. 결정의 80%가 task 파일에 박혀 있어야 한다는 원칙
- 2단계 /plan-and-build로 plan을 phase 파일로 쪼개 자기완결적으로 만들고, run-phases.py가 index.json을 읽어 pending phase부터 순차 실행한다. 세션이 끊겨도 어디서든 재시작 가능한 영속 상태가 됐다
- 3단계 /build-with-teams가 핵심이었다. critic이 phase 파일과 실제 코드를 대조해 APPROVE/REVISE를 내리고, docs-verifier가 ADR/data-schema 정합성을 확인한다. '자기 계획을 자기가 검증하면 못 본다 — 별도 에이전트한테 critic 역할을 주면 본다'가 가장 큰 깨달음
- 4단계 /integrate-ux는 디자이너가 vibe 코딩으로 올린 PR을 컨벤션(공통 컴포넌트·semantic 토큰·Container/Presenter)으로 변환하는 워크플로우를 스킬화한 것이다. 협업의 마찰을 변환 룰로 흡수했다

### 1분 답변 구조

- 통증은 '에이전트에게 줄 입력의 정확도가 낮다'는 것이었고, 해결은 vibe 코딩에서 spec 기반 코딩으로의 전환이었다
- /planning으로 결정의 80%를 task 파일에 박고, /plan-and-build로 phase 파일을 자기완결적으로 만들어 세션이 끊겨도 재시작 가능한 영속 상태로 바꿨다
- /build-with-teams의 critic + docs-verifier 게이트가 결정적이었다 — 같은 모델이라도 critic 역할을 받으면 다른 시야로 보고, 자기 계획을 자기가 검증하지 않는 분리가 안정성을 만들었다
- 디자이너 협업도 /integrate-ux로 변환 워크플로우를 스킬화해 마찰을 흡수했다. 199 plan을 처리한 건 이 4단계 진화의 결과지 단일 에이전트 능력의 결과가 아니다

### 압박 질문 방어 포인트

- 'AI가 짠 코드 품질을 어떻게 보장하냐'고 물으면 — critic이 코드와 plan을 대조하고 docs-verifier가 ADR 정합성을 검증하는 두 게이트가 있고, 빌드/테스트 통과까지 phase 종료 조건에 포함된다고 답한다
- '단순히 도구 잘 쓴 거 아니냐'고 물으면 — 4인 에이전트 역할 정의·phase 분할·index.json 진행 상태 관리·재시작성 같은 설계 결정을 내가 만든 것이고, 단순 도구 사용자였다면 12일 만에 134개 ADR과 199 plan이 나오지 않았다고 설명한다
- 'critic도 같은 모델이라 같이 헛걸 잡는 거 아니냐'고 물으면 — 같은 모델이라도 시스템 프롬프트와 입력 컨텍스트가 다르면 다른 시야가 만들어지고, 실제 critic이 'plan의 가정이 현재 코드와 다르다'를 잡는 비율이 의미 있게 높았다고 답한다

### 피해야 할 약한 답변

- 'Claude Code 잘 써서 빨리 만들었다'로 끝나면 가장 안 된다 — 역할 분리·재시작성·검증 게이트라는 설계 결정이 있어야 시니어 답변
- 'AI가 다 해줬다'는 톤은 절대 금물이다 — 결정의 80%는 task 파일에서 사람이 박았고, 구조 설계와 트레이드오프 판단은 여전히 사람의 영역이라는 점을 분명히 말해야 한다

### 꼬리 질문 5개

**F4-1.** critic 에이전트가 REVISE 판정을 내리는 구체 기준은 무엇이며, 무한 루프를 방지하는 메커니즘은 어떻게 두었는가?

**F4-2.** docs-verifier가 ADR과 코드 드리프트를 잡는 구체 사례를 하나 들고, 잡지 못했던 케이스도 있다면 무엇이었는가?

**F4-3.** phase 파일을 '자기완결적'으로 만든다는 것의 정의는 무엇이고, 이전 phase 결과에 의존하는 부분은 어떻게 표현했는가?

**F4-4.** 이 하네스를 팀 단위 개발에 적용한다면, 사람-에이전트 간 역할 분담을 어떻게 다시 설계하겠는가?

**F4-5.** 올리브영 커머스 도메인에 같은 하네스를 도입한다면 어디서부터 시작하겠는가? 가장 큰 위험과 첫 번째 성공 지표는 무엇인가?

---

## 메인 질문 5. AI 웹툰 도구에서 Gemini 모델을 pro→flash→lite로 fallback하면서 전역 Rate Limit Tracking과 Project 단위 Context Cache를 같이 설계했다고 하셨는데, '싼 모델이 결과적으로 비싸다'는 의사결정 배경과 환각 차단을 위한 호출 구조 설계를 함께 설명해 주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- LLM 비용·성능·신뢰성을 단가가 아니라 총 호출 횟수와 운영 비용 관점에서 사고할 수 있는지 본다
- 환각 같은 모델 한계를 프롬프트 카피라이팅이 아니라 호출 구조·캐시·grounding 재주입 같은 시스템 설계로 푸는 사고의 깊이를 검증한다

### 실제 경험 기반 답변 포인트

- 초기엔 flash가 기본이었다. 며칠 운영하면서 '운영자가 결과를 보고 다시 돌리면 총 비용이 올라간다'는 사실이 명확해졌다 — 단가 1/4의 모델이 재생성 2~3회를 만들면 결과적으로 더 비싸다. ADR-072에서 pro 기본 + 429 시 flash → lite fallback으로 뒤집었다
- 분산된 재시도가 비효율을 쌓지 않게 전역 Rate Limit Tracking(Map<string, number>)을 두어 어떤 모델이 429를 받으면 일정 시간 skip 마킹을 했고, 30초 재시도는 TPM이 1분 단위로 풀리는 특성과 안 맞아 제거했다
- 토큰 비용은 Project 단위 Gemini Context Cache로 메웠다 — 원작 소설(63만자)을 Analysis/Content-review/Treatment/Conti/Continuation 다섯 단계에서 공유하는 cachedContent로 묶어 만료 5분 안에 들어오는 호출의 입력 비용을 0에 가깝게 줄였다
- 환각 차단의 진짜 원인은 프롬프트 문구가 아니라 호출 구조였다. Continuation이 tail 5컷만 보고 다음 컷을 만들면서 grounding이 사라져 있었다. ADR-132에서 (a) Grounding 블록을 프롬프트 최우선에 박고 '연출은 자유, 서사는 grounding'이라는 허용 범위를 명시, (b) Continuation에도 Grounding/Treatment 블록을 매번 재주입했다. 토큰 비용은 Context Cache로 흡수했다
- 한계도 솔직히 말한다 — Pro가 429로 Flash/Lite로 fallback하면 같은 프롬프트라도 grounding 준수력이 약해져 환각이 다시 등장한다. 서비스 연속성을 우선해 fallback은 유지했고, 별도 대응이 다음 과제로 남아 있다

### 1분 답변 구조

- '비용 최적화는 단가가 아니라 총 호출 횟수로 본다'가 핵심 관점이다. Pro 기본 + 429 시 flash→lite fallback으로 뒤집고, 전역 Rate Limit Tracking으로 분산 재시도가 비효율을 쌓지 않게 했다
- 토큰 비용은 Project 단위 Context Cache로 다섯 단계가 같은 원작 소설을 공유하게 해 흡수했다
- 환각 차단은 프롬프트 카피라이팅이 아니라 호출 구조 설계였다. Continuation이 tail 5컷만 보고 grounding을 잃은 게 원인이었고, Grounding 블록 최우선 배치 + Continuation 재주입으로 해결했다
- '연출은 자유, 서사는 grounding'이라는 허용 범위 명시가 단순 금지보다 훨씬 잘 먹었다 — 도망갈 자리를 줘야 grounding을 지킨다

### 압박 질문 방어 포인트

- 'Pro만 쓰면 비용이 폭증하지 않냐'고 물으면 — 단가는 비싸도 재생성 비율과 운영자 시간이 줄어 총 비용이 낮아진다는 데이터로 답하고, Context Cache로 입력 토큰의 큰 부분을 흡수했다고 설명한다
- '환각을 자동 판정기로 잡지 그랬냐'고 물으면 — 환각의 경계가 fuzzy해서 자동 판정 자체가 또 다른 환각 소스가 된다고 답하고, 사람 판정 + 체크리스트 + 호출 구조 설계가 MVP에서 가장 신뢰도 높았다고 솔직히 말한다
- 'fallback 시 grounding 약화는 어떻게 받아들였냐'고 물으면 — 트레이드오프를 인정하고 서비스 연속성을 우선했으며, 후속 과제로 fallback 모델 전용 프롬프트 강화 같은 안을 가지고 있다고 답한다

### 피해야 할 약한 답변

- 'Pro가 더 좋아서 썼다'로 끝나면 안 된다 — 단가 vs 재생성 비율의 의사결정 프레임을 반드시 같이 말해야 한다
- 환각 해결을 'DO NOT invent를 추가했다' 같은 프롬프트 카피라이팅 수준으로 답하면 시니어 답변이 아니다 — '문구 수정으로는 안 됐고 호출 구조에 grounding 재주입이 필요했다'는 본질을 짚어야 한다

### 꼬리 질문 5개

**F5-1.** 전역 Rate Limit Tracking을 Map으로 단일 인스턴스에 두었는데, 멀티 인스턴스 환경에서는 어떤 자료구조·저장소로 옮기겠는가?

**F5-2.** Project 단위 Context Cache의 만료(5분)가 다섯 단계 호출 시퀀스와 어긋나는 케이스는 어떻게 감지하고 처리했는가?

**F5-3.** '연출은 자유, 서사는 grounding'이라는 허용 범위 명시가 효과적이었다고 했는데, 이 원칙을 다른 도메인(예: 커머스 상품 설명 생성)에 옮기면 어떻게 일반화하겠는가?

**F5-4.** Continuation에 매번 grounding을 재주입하면 토큰이 늘어나는데, Context Cache가 없는 환경이라면 이 트레이드오프를 어떻게 풀겠는가?

**F5-5.** Pro fallback 시 grounding 준수력 약화가 미해결 과제라고 했는데, 가장 가능성 있어 보이는 해결안 두 가지와 각각의 위험을 무엇으로 보는가?

---

## 최종 준비 체크리스트

- Spring Batch 11 Step 분리 근거(실패 격리 + 재시작)와 @JobScope vs JobExecutionContext 트레이드오프를 한 문장으로 요약 가능
- AsyncItemProcessor/AsyncItemWriter Future 흐름, parallelChunkExecutor 스레드풀 크기 산정 근거, 청크 사이즈와의 관계 설명 준비
- OCR 503 사례에서 K8s terminationGracePeriodSeconds 30s 제약과 preStop sleep 15s + grace 12s + 여유 3s 예산 설계 도식 외우기
- 전략 패턴(ConfluenceDocumentMetadataProvider, EmbeddingMetadataProvider) 도입 전후 코드 차이와 OCP 위반 비용을 1분 이내로 설명
- AI 웹툰 12일 199 plan/760 커밋 — main/executor/critic/docs-verifier 4인 에이전트 역할 분리, Gemini pro→flash→lite fallback + 전역 Rate Limit Tracking + Context Cache 흐름도 손그림으로 그릴 수 있을 것
- Pro→Flash fallback 시 grounding 준수력 약화 같은 미해결 과제를 솔직히 말하고 후속 대응안 제시
- 올리브영 MSA 데이터 연동 전략(Cache-Aside + Kafka 하이브리드), 무중단 OAuth2 전환(Feature Flag + Shadow Mode + Resilience4j) 글 핵심 메시지 숙지
