# [초안] AI 서비스 팀 경험 기반 시니어 백엔드 면접 질문 뱅크 — Spring Batch RAG / gRPC graceful shutdown / 전략 패턴 / 12일 AI 웹툰 MVP

---

## 이 트랙의 경험 요약

- AI 서비스 개발팀에서 직접 설계·운영한 4대 경험을 시니어 Java 백엔드 면접 관점에서 구술 가능한 형태로 정리한다 — (1) Spring Batch 11 Step 기반 Confluence → OpenSearch RAG 색인 파이프라인, (2) gRPC OCR 서버 배포·스케일인 503의 graceful shutdown 예산 재설계, (3) 임베딩 메타데이터 구성 방식의 blocklist → allowlist 전환과 전략 패턴, (4) 12일 단독 풀스택 AI 웹툰 MVP의 4인 에이전트 팀 하네스·Gemini 모델 전략·환각 차단.
- 각 경험은 단순 사용 경험이 아니라 트레이드오프 기반의 설계 의사결정으로 풀어 답할 수 있도록 구성한다 — 왜 JobExecutionContext가 아니라 @JobScope, 왜 30초 안에서 'sleep 15 + grace 12'였는지, 왜 blocklist가 아니라 allowlist인지, 왜 SSE가 아니라 Promise.allSettled로 바꿨는지를 1분 답변과 압박 방어 답변에 모두 녹인다.
- 추가로 1분 자기소개와 지원 동기(왜 변화 / 왜 올리브영 / 왜 이 직무)를 별도 섹션으로 두어, 본 질문 뱅크가 'AI/에이전트 협업 경험을 단순 툴 사용자가 아니라 파이프라인·아키텍처 설계자 수준으로 드러내는 시니어 면접 자료'로 사용 가능하도록 한다.

## 1분 자기소개 준비

- NHN에서 4년째 Spring Boot 기반 MSA 환경에서 백엔드를 개발해온 김병태입니다. 처음 3년은 소셜 카지노 게임 슬롯 서비스에서 신규 게임 개발과 성능 개선·아키텍처 재설계를 담당했고, 이후 AI 서비스 팀으로 이동해 사내 RAG를 위한 Spring Batch 색인 파이프라인을 설계·운영했습니다.
- 기술적으로는 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout + Hibernate PostCommitUpdateEventListener + StampedLock으로 직접 해결했고, Kafka 이벤트 드리븐을 AFTER_COMMIT + Dead Letter Store + traceId 추적까지 결합해 신뢰성 있는 비동기 처리를 구조적으로 만들었습니다.
- AI 서비스 팀에서는 Confluence → OpenSearch RAG 파이프라인을 11개 Step으로 분리하고 AsyncItemProcessor로 I/O 병렬화, 임베딩 메타데이터 구성을 blocklist에서 EmbeddingMetadataProvider 기반 allowlist로 전환해 OCP를 지키는 식으로 운영 가능한 형태로 정리했습니다. 직전에는 12일 동안 혼자 AI 웹툰 제작 도구 MVP를 풀스택으로 구현하며 199 plan / 760 커밋을 4인 에이전트 팀 하네스로 처리했고, 이 과정에서 'AI 도구를 쓰는 사람'이 아니라 'AI 호출 구조와 비용 모델을 설계하는 사람'으로 한 단계 더 나갔다고 생각합니다.
- 이 모든 경험을 1,600만 고객이 사용하는 커머스 트래픽 환경에서 검증하고 싶어 올리브영 커머스플랫폼유닛에 지원하게 되었고, 안정성과 개발 속도를 동시에 끌어올리는 데 빠르게 기여하고 싶습니다.

## 올리브영/포지션 맞춤 연결 포인트

- 다중 서버 인메모리 캐시 정합성을 RabbitMQ Fanout + Hibernate PostCommitUpdateEventListener + StampedLock으로 직접 해결한 경험은, 올리브영 기술 블로그의 '변경 빈도/라이프사이클 기반 Cache-Aside + Kafka 하이브리드' 의사결정과 같은 결이라 합류 직후 같은 패턴을 1,600만 트래픽 규모에서 검증할 수 있다.
- Kafka 이벤트 드리븐을 @TransactionalEventListener(AFTER_COMMIT) + Dead Letter Store + 스케줄러 재시도 + traceId 추적까지 결합해 비동기 신뢰성을 구조적으로 확보한 경험은, 올리브영의 '무중단 OAuth2 전환'에서 본 Resilience4j 3단계 보호 + Feature Flag + Shadow Mode 같은 운영 안정성 설계와 같은 결의 사고방식이다.
- Spring Batch 11 Step 기반 Confluence → OpenSearch 색인 파이프라인을 처음부터 설계하면서 AsyncItemProcessor / @JobScope / 커서 기반 재시작 / 삭제 동기화까지 운영했고, 이 패턴은 커머스 상품 검색 색인이나 전시 데이터 동기화에 그대로 옮겨진다.
- AI 도구를 단순 사용자가 아니라 호출 구조와 비용 모델을 직접 설계하는 수준에서 다뤄왔다 — 4인 에이전트 팀 하네스로 12일에 199 plan / 760 커밋을 처리한 경험은 '대규모 인원 없이도 빠른 반복이 가능한 팀 구조'를 만드는 역량으로 연결된다.

## 지원 동기 / 회사 핏

### 왜 이직하려는가
- NHN에서 4년 동안 게임 백엔드 → AI 서비스 백엔드로 도메인을 한 번 바꾸면서 같은 Spring 스택이 도메인 변화에 따라 어떻게 다르게 깨지고 다르게 버티는지 체감했고, 다음 단계는 '실사용자 트래픽이 매일 흐르는 대규모 커머스'에서 같은 기술을 검증하는 것이라고 판단했다.
- AI 서비스 팀에서 Spring Batch RAG 파이프라인과 gRPC OCR graceful shutdown을 직접 설계·운영하면서, 안정성과 정합성 문제는 트래픽 규모와 도메인 복잡도가 같이 커질 때 가장 선명하게 드러난다는 것을 체득했다 — 그 환경이 1,600만 고객 커머스다.
- 지금까지 쌓은 캐시 정합성 · 이벤트 드리븐 · 대용량 색인 경험이 커머스 백엔드의 전형적 문제(상품·전시·주문 정합성, 실시간 이벤트 연동, 검색 색인)와 직접 맞닿아 있어 합류 직후부터 기여 가능한 시점이라고 봤다.

### 왜 올리브영인가
- 올리브영 기술 블로그의 'MSA 데이터 연동 전략' 글에서 데이터의 변경 빈도·라이프사이클을 기준으로 Cache-Aside와 Kafka 이벤트 드리븐을 하이브리드로 묶은 부분이, 내가 슬롯 서비스에서 RabbitMQ Fanout + StampedLock으로 풀었던 다중 서버 캐시 정합성 문제와 같은 결의 의사결정이라 강하게 공감됐고, 같은 의사결정 패턴을 1,600만 트래픽 규모에서 검증하고 싶다.
- '무중단 OAuth2 전환' 글에서 Feature Flag · Shadow Mode · Resilience4j 3단계 보호 · Jitter 분산까지 운영 안정성을 '코드'와 '배포 전략'을 함께 설계해서 푸는 방식이, 내가 Kafka AFTER_COMMIT + Dead Letter Store + traceId 추적으로 비동기 신뢰성을 구조적으로 확보했던 접근과 결이 같아 빠르게 합류 가능하다고 판단했다.
- 팀이 '빠르고 안정적인 고객 경험'을 미션으로 명시하고, 그것을 단순 슬로건이 아니라 ADR/포스트모템 수준의 글로 공개하는 문화 자체가 내가 일해온 방식(ADR로 결정 근거 남기기 · docs-first)과 정합도가 높다.

### 왜 이 역할에 맞는가
- 담당 업무가 상품·전시·검색 엔진 연동·MSA·ORM 도메인 모델링·새 기술 검토로 명시되어 있고, 이는 내가 NHN에서 슬롯 도메인을 AbstractPlayService + SpinOperationHandler로 통합하고 정적 의존을 DI로 전환했던 도메인 모델링 경험과 RAG 색인 파이프라인을 OpenSearch에 붙여 운영했던 색인 운영 경험을 동시에 활용할 수 있는 자리다.
- 우대 사항 8개 중 Spring Boot · Docker/K8s · MSA · Kafka · 캐싱 전략 · 대용량 데이터/트래픽 6개에서 직접 '설계·운영' 경험이 있고, 부족한 부분(Kotlin, 커머스 도메인 자체)은 이미 학습 중이라 합류 후 첫 분기에 추가로 가져갈 영역으로 명확히 잡힌다.
- 1차 라이브 코딩 + 2차 화이트보드까지 두 단계로 평가하는 절차가 '구술로 잘 말하는 사람'이 아니라 '실제로 설계와 코드 양쪽을 같이 보는 사람'을 뽑는다는 시그널이고, 본인이 가장 자신 있는 평가 방식이라 그 자리에서 실력을 정확히 보여줄 수 있다고 본다.

## 메인 질문 1. Confluence → OpenSearch RAG 파이프라인을 11개 Step으로 분리한 이유와, Step 간 데이터 공유 / 재시작 / 병렬화를 어떻게 설계했는지 설명해주세요.

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 대용량 색인 같은 장기 실행 워크로드에서 '실패 격리 / 재시작 / 멱등성'을 원리적으로 이해하고 직접 설계해본 경험이 있는지를 본다.
- Spring Batch의 도구(@JobScope, ExecutionContext, AsyncItemProcessor, allowStartIfComplete)를 단순 사용 수준이 아니라 '왜 이 도구를 이 위치에 썼는가'로 설명할 수 있는지를 검증한다.

### 실제 경험 기반 답변 포인트

- 전체 잡은 11개 Step으로 분리했고, 각 Step은 단일 책임만 가지며 앞 Step이 컨텍스트에 저장한 데이터를 뒤 Step이 읽어가는 구조로 데이터를 공유한다 — 색인 시작/소스 초기화 / 스페이스 수집 / 페이지 색인 / 페이지ID 수집 / 댓글 색인 / 삭제 페이지·댓글·첨부 제거 / 색인 갱신 / 완료 기록.
- Step 분리의 본질은 '실패 격리'다 — 댓글 Step이 실패해도 페이지 Step 결과는 살아있고 재시작하면 댓글 Step부터 이어 돌릴 수 있다. 거대한 단일 Step이면 중간 실패 시 처음부터 다시 해야 한다.
- Step 간 데이터 공유는 처음에 JobExecutionContext에 넣었다가 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT에 직렬화되는 비용이 커서 @JobScope 빈인 ConfluenceJobDataHolder로 옮겼다. JobExecutionContext는 재시작용 커서 같은 경량 상태 전용이라는 원칙을 지켰다.
- 재시작 시 새 JobExecution이 생기면 @JobScope 빈도 새 인스턴스로 초기화되는데 상태 로더 Step이 COMPLETED로 스킵되면 빈이 빈 상태로 남아 NPE가 나기 때문에 allowStartIfComplete(true)로 상태 로더는 반드시 재실행되도록 잡았다.
- I/O 바운드인 임베딩/문서 파싱 호출은 AsyncItemProcessor + AsyncItemWriter로 청크 내 병렬화했고, Reader는 ItemStream 구현으로 커서 기반 페이지네이션 위치를 ExecutionContext에 저장해 정확히 마지막 처리 지점부터 재시작 가능하도록 설계했다.

### 1분 답변 구조

- RAG를 위해 Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인을 처음부터 설계했고, 잡 시작 기록부터 색인 갱신·완료 기록까지 11개 Step으로 분리했다.
- 분리 기준은 '실패 격리 단위'였다 — 페이지 색인이 실패해도 댓글 Step이 살아있어 별도 재시도 경로가 가능하고, 재시작하면 실패한 Step부터 정확히 이어진다.
- Step 간 데이터 공유는 처음에 JobExecutionContext를 썼지만 청크 커밋마다 DB 직렬화 비용이 커서 @JobScope 빈으로 옮겼고, JobExecutionContext는 재시작용 커서 위치 같은 경량 상태로만 한정했다.
- I/O 바운드인 임베딩 호출은 AsyncItemProcessor + AsyncItemWriter로 청크 내 병렬화했고, Reader는 ItemStream을 구현해 커서 위치를 ExecutionContext에 저장해 정확한 지점에서 재시작이 가능하도록 했다.

### 압박 질문 방어 포인트

- '그냥 하나의 큰 Step에 다 넣지 그랬냐'는 질문이 들어오면, 단일 Step이면 중간 실패 시 전체 재실행이라 임베딩 API 비용·시간이 그대로 다시 발생하고 부분 실패한 데이터의 재시도 추적이 불가능했다는 점을 사례 기반으로 설명한다.
- @JobScope 선택을 '과한 추상화 아니냐'로 압박받으면, JobExecutionContext가 청크 커밋마다 직렬화되는 구조 자체를 근거로 제시하고, '재시작용 커서 = ExecutionContext, 잡 단위 도메인 데이터 = @JobScope 빈'이라는 역할 분리 원칙으로 방어한다.

### 피해야 할 약한 답변

- 'Step을 잘게 나눴더니 깔끔했다' 수준의 미적 관점만 답하고, 실패 격리·재시작·DB 직렬화 비용 같은 운영적 이유를 못 대는 답변.
- AsyncItemProcessor를 '비동기 처리해서 빨라졌어요'로만 끝내고 Future, AsyncItemWriter, 스레드풀 분리, 청크 트랜잭션 경계와의 관계를 설명하지 못하는 답변.

### 꼬리 질문 5개

**F1-1.** AsyncItemProcessor를 쓰면서 청크 단위 트랜잭션 경계와 예외 전파, 부분 실패 시 어떤 아이템이 어디서 실패했는지 추적하는 부분은 어떻게 다뤘나요?

**F1-2.** 재시작 시 allowStartIfComplete(true)를 어디까지 적용했고, 반대로 절대 재실행하면 안 되는 Step(예: 색인 시작 기록)은 어떻게 구분했나요?

**F1-3.** 11개 Step으로 쪼갠 기준이 무엇인가요 — 더 잘게 쪼갤 수 있는 부분과 합쳐도 됐던 부분이 후행적으로 보였나요?

**F1-4.** Step 사이를 JobExecutionContext가 아닌 @JobScope 빈으로 공유하면 다중 잡 동시 실행이나 다른 인스턴스에서의 재시작 같은 시나리오에서는 어떤 한계가 있었나요?

**F1-5.** 이 11 Step 구조를 만약 처음부터 다시 설계한다면 어디를 가장 먼저 바꾸고 싶나요?

---

## 메인 질문 2. OCR 서버 배포·스케일인 시 클러스터 단위 503이 발생했던 사건의 원인 분석과 해결 과정을 설명해주세요. terminationGracePeriodSeconds가 고정 30초였다는 제약은 설계에 어떻게 반영했나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 배포·스케일링 같은 '경계 시점'의 503을 단순 재시작으로 덮지 않고 종료 시퀀스 전체(K8s lifecycle / preStop / SIGTERM / supervisord / 애플리케이션 코드)를 추적해서 푸는 디버깅 깊이를 본다.
- 외부 제약(terminationGracePeriodSeconds 30s 고정)을 받아들인 상태에서 시간 예산을 재분배하는 시스템적 사고가 가능한지를 검증한다.

### 실제 경험 기반 답변 포인트

- 에러 패턴 자체가 단서였다 — 'upstream connect error / reset reason: connection failure / error 111'은 Envoy는 살아있는데 upstream 50051이 거부됐다는 TCP 레벨 시그널이고, 30~60초 주기 묶음 발생이 배포·스케일인 이벤트와 정확히 일치했다.
- 구조적으로는 Envoy(:5000) → gRPC(:50051) 사이에서 preStop이 'Envoy drain_listeners + sleep 20'만 했고, sleep이 끝나 SIGTERM이 전달되면 gRPC 서버가 즉시 종료되며 그 사이에 들어오는 요청이 ECONNREFUSED로 떨어졌다 — 진짜 원인은 gRPC 서버에 SIGTERM 핸들러가 없었던 것이다.
- 두 번째 원인은 supervisord의 stopwaitsecs 미지정으로 기본 10초가 적용되어, SIGTERM 핸들러를 붙여도 supervisord가 10초 내에 SIGKILL로 강제 종료할 수 있는 구조였다는 점이었다.
- NHN Cloud Container Service가 terminationGracePeriodSeconds=30s로 고정되어 있어 모든 종료 작업이 30초 안에 끝나야 한다는 외부 제약을 만났고, 이 30초 안에서 'preStop sleep 15s + gRPC server.stop(grace=12s) + 여유 3s'로 예산을 재배분했다.
- 최종 변경은 세 군데였다 — gRPC 서버에 signal.signal(SIGTERM, server.stop(grace=12)) 추가, supervisord에 stopwaitsecs=17 (grace 12 + 여유 5) 명시, Jenkinsfile preStop sleep을 20→15s로 단축. 결과적으로 preStop 끝나는 시점에 gRPC가 정상 drain 후 종료된다.

### 1분 답변 구조

- 배포·스케일인마다 30~60초 묶음으로 503이 났고, error 111 / server: envoy 헤더에서 'Envoy는 살아있는데 upstream gRPC 50051이 거부됐다'는 신호를 잡았다.
- 원인은 두 가지였다 — gRPC 서버에 SIGTERM 핸들러가 없어 SIGTERM이 오면 즉시 죽었고, supervisord stopwaitsecs가 기본 10초여서 핸들러를 붙여도 강제 종료될 수 있었다. preStop은 Envoy drain + sleep 20만 하고 정작 upstream 종료는 신경 쓰지 않는 구조였다.
- NCS가 terminationGracePeriodSeconds=30s로 고정이라 30초 예산 안에서 'preStop sleep 15 + gRPC grace 12 + 여유 3'으로 재분배했다.
- 최종 수정은 세 곳이다 — gRPC 서버에 SIGTERM 핸들러로 server.stop(grace=12), supervisord에 stopwaitsecs=17, preStop sleep을 20→15초로 단축. 이후 preStop 종료 시점에 gRPC가 정상 drain 후 종료된다.

### 압박 질문 방어 포인트

- '재시작 시 503은 어쩔 수 없는 거 아니냐'로 들어오면, Envoy drain과 upstream graceful shutdown이 시간 축에서 정렬되면 503이 0에 수렴한다는 점을 종료 시퀀스 표로 설명하고, 수정 후 실측 변화를 근거로 든다.
- 'terminationGracePeriodSeconds를 늘리면 되지'로 압박받으면, NCS가 해당 필드를 API 스펙에서 제공하지 않아 30초 고정이라는 외부 제약을 먼저 명확히 하고, 그 제약 안에서 예산 재분배가 유일한 해법이었음을 설명한다.

### 피해야 할 약한 답변

- 'graceful shutdown을 추가했더니 해결됐다' 식으로 종료 시퀀스의 시간축(preStop / SIGTERM / supervisord stopwaitsecs / gRPC stop grace) 분리 없이 결론만 말하는 답변.
- 원인을 'Envoy 문제'나 'K8s 문제'로 한 레이어에 몰아붙이고 supervisord나 애플리케이션 SIGTERM 핸들러까지 내려가 보지 않은 답변.

### 꼬리 질문 5개

**F2-1.** Envoy drain과 gRPC graceful shutdown 사이의 시간 예산을 30초 안에 배분할 때 '왜 sleep 15 + grace 12'였나요 — 다른 분배는 검토해봤나요?

**F2-2.** in-flight gRPC 스트림이 grace 12초 안에 못 끝나는 long-running 요청이 있었다면 어떻게 다뤘을 건가요?

**F2-3.** 이 문제를 모니터링/관측만으로 사전에 잡을 수 있었을 거라 본다면, 어떤 메트릭이나 로그를 봤어야 한다고 생각하시나요?

**F2-4.** supervisord 대신 PID 1을 init이나 tini로 두는 옵션은 검토했나요? 왜 supervisord를 유지했나요?

**F2-5.** 동일 패턴의 503이 다른 서비스에서도 재발하지 않게, 팀 차원의 표준 종료 절차로는 어떻게 정착시켰나요?

---

## 메인 질문 3. 임베딩 메타데이터 구성을 blocklist에서 allowlist(EmbeddingMetadataProvider)로 전환한 배경과 설계 의사결정을 설명해주세요. 왜 전략 패턴이었고, OCP는 어떻게 지켰나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- '전략 패턴'을 책 지식이 아니라 실제 운영 코드에서 구체적 문제(blocklist의 OCP 위반, 분기 폭발, 가독성 저하)에 매핑해 적용한 경험이 있는지를 본다.
- Spring DI(List<T> 주입 + Map 빌드 + @Qualifier)를 통해 추상화를 실제 런타임 라우팅으로 어떻게 잇는지에 대한 감각이 있는지를 검증한다.

### 실제 경험 기반 답변 포인트

- 기존 EmbeddingService는 문서의 전체 메타데이터를 cloneMetadata()로 복사한 뒤 14개의 remove() 호출로 불필요한 필드를 제거하고, 그 위에 if-else로 DocumentType별 추가 로직을 붙이는 'blocklist' 방식이었다 — 새 DocumentType이 추가될 때마다 EmbeddingService 자체를 수정해야 해서 OCP가 깨지고, '실제로 어떤 필드가 임베딩에 들어가는지'를 코드로 답하기 어려웠다.
- 핵심 전환은 '제거할 필드를 관리하지 말고 포함할 필드를 명시적으로 관리하자'였다. EmbeddingMetadataProvider 인터페이스에 getSupportedDocumentTypes()와 provide(Document) 두 메서드만 두고, 각 구현체가 자신이 담당하는 DocumentType을 선언하도록 했다.
- 공통 필드는 AbstractEmbeddingMetadataProvider → AbstractCollabToolEmbeddingMetadataProvider / AbstractConfluenceEmbeddingMetadataProvider로 추상 계층을 한 단 더 두고, 그 아래에 Task/Wiki/DriveFile/Confluence 구현체를 둬서 공통 createResultWithCommonFields()를 재사용했다 — 특히 Confluence 측은 title이 없으면 subject로 폴백하는 케이스를 추상 클래스 안에 가뒀다.
- Spring DI를 활용해 List<EmbeddingMetadataProvider>를 자동 주입받고, Config에서 flatMap으로 DocumentType → Provider 맵을 빌드하도록 했다. EmbeddingService는 DocumentType으로 provider를 조회해 위임만 하면 끝이라 이전의 14개 remove + if-else 분기가 모두 사라졌다.
- 결과적으로 새 DocumentType이 추가돼도 EmbeddingService 코드는 닫혀 있고 @Component 구현체만 추가하면 확장된다(OCP). 부산물로 cloneMetadata / getMetadataValue / putMetadata 같이 이 패턴 때문에만 존재하던 메서드들도 삭제됐고, 단위 테스트 단위가 구현체별로 깨끗하게 떨어졌다.

### 1분 답변 구조

- 기존 EmbeddingService는 cloneMetadata 후 14개 remove로 필드를 빼고 DocumentType별 if-else로 추가 로직을 얹는 blocklist 방식이라, 새 DocumentType마다 EmbeddingService를 직접 고쳐야 했다 — OCP가 깨지고 어떤 필드가 들어가는지 한눈에 안 보였다.
- EmbeddingMetadataProvider 인터페이스를 두고 'getSupportedDocumentTypes / provide(Document)'로 각 구현체가 담당 DocumentType과 포함할 필드를 명시적으로 선언하게 바꿨고, 협업 도구·Confluence처럼 패밀리별 공통 필드는 추상 클래스 두 단으로 모았다.
- Spring이 List<EmbeddingMetadataProvider>를 자동 주입하면 Config에서 flatMap으로 DocumentType → Provider 맵을 빌드하고, EmbeddingService는 그 맵에서 조회해 위임만 한다.
- 결과: EmbeddingService에서 14개 remove + if-else가 사라졌고, 새 DocumentType은 @Component 구현체만 추가하면 된다(OCP). 더 이상 쓰이지 않게 된 cloneMetadata / getMetadataValue / putMetadata 같은 부산물 메서드도 같이 정리됐다.

### 압박 질문 방어 포인트

- '그냥 if-else가 더 직관적 아니냐'로 들어오면, 14개 remove + 분기가 누적된 실제 코드 스냅샷을 근거로 '어떤 필드가 임베딩에 들어가는지를 답하기 위해 필드 제거 목록을 역산해야 했다'는 점을 강조한다.
- '전략 패턴 남발'로 압박받으면, '동일 구조 3곳 이상 반복'을 추출 기준으로 보수적으로 잡았다는 점과, OCP 위반이 실제 PR 히스토리에서 EmbeddingService 잦은 수정으로 드러났다는 점을 들어 정당화한다.

### 피해야 할 약한 답변

- '전략 패턴을 적용해서 깔끔해졌다'는 식으로 구체적 비포(14개 remove + if-else 분기)와 애프터의 차이를 코드 수준에서 못 보여주는 답변.
- Spring DI로 List<T> 주입 + Map 빌드 부분을 빼먹고 인터페이스만 만들면 끝난 것처럼 설명해, 런타임 라우팅과 확장성의 연결을 보여주지 못하는 답변.

### 꼬리 질문 5개

**F3-1.** 하나의 DocumentType이 두 Provider 후보를 갖는 케이스(예: 같은 Task인데 일부 스페이스만 다른 메타데이터)는 어떻게 라우팅했나요? 우선순위나 명시적 Qualifier가 필요했나요?

**F3-2.** 전략 패턴으로 풀지 않고 'metadata 내부에 시리얼라이저를 두는' 방식으로도 풀 수 있을 텐데, 왜 외부 Provider 인터페이스가 더 적합하다고 판단했나요?

**F3-3.** Confluence Provider에서 title → subject 폴백을 추상 클래스에 넣은 이유는 무엇인가요? 만약 다른 스페이스에서 또 다른 폴백 룰이 필요하다면 구조를 어떻게 확장할 건가요?

**F3-4.** EmbeddingMetadataProvider의 getSupportedDocumentTypes()를 Set으로 둔 이유와, 이 정보가 컴파일 시간이 아니라 런타임 맵 구축으로만 검증된다는 점은 어떻게 보완했나요?

**F3-5.** 동일한 패턴을 ConfluenceDocumentMetadataProvider(스페이스별 schema 차이)와 EmbeddingMetadataProvider(DocumentType별 schema 차이) 두 군데에 적용했는데, 두 패턴을 합쳐 한 인터페이스로 통일하지 않은 이유는 무엇이었나요?

---

## 메인 질문 4. 다중 서버 환경에서 인메모리 캐시 정합성을 RabbitMQ Fanout + Hibernate 이벤트 + StampedLock으로 푼 설계를 설명해주세요. 왜 Redis가 아니라 인메모리였고, 갱신 중 동시성은 어떻게 보장했나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 다중 서버 환경에서의 캐시 정합성과 갱신 중 동시성을 직접 풀어본 경험이 있는지, 또 그 해법이 패턴 암기인지 트레이드오프 기반의 설계인지 본다.
- Hibernate 이벤트 리스너 + 메시징 + 동시성 제어 + 확장 가능한 도메인 추상화를 한 번에 엮어본 사람인지를 검증한다 — 즉 구현 한 군데가 아닌 시스템 단위 사고.

### 실제 경험 기반 답변 포인트

- 슬롯 서비스에서 정적 설정 데이터를 애플리케이션 메모리에 캐싱하면서 어드민 변경을 다중 서버에 반영해야 했고, Hibernate PostCommitUpdateEventListener가 발동하면 RabbitMQ Fanout Exchange로 변경된 게임 ID만 발행하는 구조로 정합성을 유지했다 — 각 서버 인스턴스는 자기 큐에서 메시지를 받아 해당 슬롯만 선택적으로 갱신한다.
- 갱신 중 조회 요청이 들어올 때 일시적 정합성 오류가 났는데, StampedLock을 도입해 갱신 시 writeLock으로 읽기를 차단하고 tryReadLock에 2.5초 타임아웃을 걸어 무한 대기를 차단했다.
- 동시성 1차 대응 후, 새로운 캐시 타입을 추가할 때마다 동일 문제가 반복되지 않도록 StaticDataManager 인터페이스로 init/refresh/clear 책임을 분리하고 데이터 타입별 구현체로 확장 구조를 만들었다 — 신규 캐시 타입을 추가할 때 기존 코드를 건드릴 일이 없다.
- 왜 Redis가 아니라 인메모리였는가에 대한 트레이드오프도 명확하다 — 정적 설정 데이터는 변경 빈도가 매우 낮고 핫 패스에서 매 요청 조회되기 때문에 네트워크 왕복을 없애는 인메모리 + 변경 시 invalidate가 비용 대비 효과가 가장 컸다. 단점인 다중 서버 정합성은 Fanout 메시징으로 해결했다.
- 이 경험은 올리브영의 'MSA 데이터 연동 전략'에서 변경 빈도/라이프사이클 기준으로 Cache-Aside와 Kafka 이벤트 드리븐을 하이브리드로 묶은 의사결정과 같은 결이다 — 같은 의사결정 패턴을 1,600만 트래픽 규모에서 적용·검증할 수 있다.

### 1분 답변 구조

- 슬롯 서비스에서 정적 설정 데이터를 인메모리 캐시로 두고 어드민 변경 시 Hibernate PostCommitUpdateEventListener에서 RabbitMQ Fanout Exchange로 변경된 게임 ID를 발행, 각 서버가 자기 큐에서 받아 해당 항목만 선택적으로 refresh하는 구조로 다중 서버 정합성을 유지했다.
- 갱신 중 조회 시 일시 정합성 오류가 나서 StampedLock으로 갱신 시 writeLock, 조회 시 tryReadLock + 2.5초 타임아웃을 걸어 무한 대기와 정합성 오류를 동시에 차단했다.
- 타입이 늘어날 때 같은 문제가 반복되지 않게 StaticDataManager 인터페이스로 init/refresh/clear 책임을 분리하고 데이터 타입별 구현체로 확장 구조를 잡아, 신규 캐시 추가 시 기존 코드를 건드리지 않는다.
- Redis가 아닌 인메모리를 택한 건 변경 빈도와 핫 패스 특성 때문이었고, 이는 올리브영 기술 블로그의 '데이터 라이프사이클 기반 하이브리드 연동' 의사결정과 같은 결로, 같은 패턴을 커머스 트래픽 규모에서 검증하고 싶다.

### 압박 질문 방어 포인트

- '그냥 Redis 쓰면 되지'로 들어오면, 정적 설정 데이터의 핫 패스 특성과 네트워크 왕복 비용 / 변경 빈도 / 운영 복잡도를 기준으로 인메모리가 본 도메인에 맞았다는 트레이드오프를 명확히 제시한다.
- 'StampedLock은 까다로운데 왜?'로 압박받으면, ReentrantReadWriteLock 대비 reader 비차단 우선의 성격과 tryReadLock 타임아웃을 갖춘 점이 갱신 중 조회의 대기 시간 상한을 명시적으로 만들 수 있다는 이유를 든다.

### 피해야 할 약한 답변

- RabbitMQ를 쓴 사실만 말하고 PostCommitUpdateEventListener와의 연결, '왜 Fanout인지', '변경 ID 단위 메시지인지'를 풀어내지 못하는 답변.
- StampedLock을 'lock 걸었다' 수준으로만 답하고 tryReadLock + 타임아웃 / writeLock 점유 / 무한 대기 방지 같은 설계 의도를 설명하지 못하는 답변.

### 꼬리 질문 5개

**F4-1.** StampedLock 대신 ReentrantReadWriteLock이나 Versioned Atomic Reference도 후보였을 텐데, 왜 StampedLock이었고 tryReadLock 타임아웃을 2.5초로 잡은 근거는 무엇이었나요?

**F4-2.** Fanout Exchange로 broadcast하면 N대 인스턴스가 동시에 같은 데이터를 갱신 요청하게 되는데, 외부 소스(DB/원본)에 발생하는 부하는 어떻게 평가하고 제어했나요?

**F4-3.** PostCommitUpdateEventListener는 트랜잭션 커밋 이후라도 메시지 발행이 실패하면 데이터-메시지 정합성이 깨질 수 있는데, 이 경계는 어떻게 다뤘나요?

**F4-4.** 정적이지만 '거의 안 변하는' 데이터와 '꽤 자주 변하는' 데이터의 경계를 어디에 두었나요? 그 기준이 잘못 잡혔던 사례가 있었나요?

**F4-5.** 이 구조를 커머스 도메인(예: 전시 룰, 상품 진열 정책)에 옮긴다면 어디를 그대로 가져가고 어디를 바꿔야 한다고 보시나요?

---

## 메인 질문 5. 12일 단독 풀스택으로 AI 웹툰 MVP를 만들면서 4인 에이전트 팀(planner/critic/executor/docs-verifier)을 어떻게 조율했고, Gemini 모델 fallback과 환각 차단을 어떻게 설계했는지 설명해주세요. 이 경험이 커머스 백엔드 업무에 어떻게 옮겨질 수 있다고 보시나요?

> 추가: 2026-04-18 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- AI/에이전트를 '툴 사용자' 수준으로 답할지, '파이프라인·아키텍처 설계자' 수준으로 답할지를 본다 — 시니어 백엔드 채용에서 결정적 차별화 포인트.
- 12일이라는 짧은 기간에 199 plan / 760 커밋이 가능했던 이유를 단순 'AI 잘 썼어요'가 아니라 '입력 정확도 / 역할 분리 / 호출 구조 설계 / 비용 모델'이라는 엔지니어링 언어로 풀어낼 수 있는지 검증한다.

### 실제 경험 기반 답변 포인트

- 12일 동안 혼자 풀스택을 돌릴 수 있었던 본질은 '하네스'였다 — 4인 에이전트 팀(planner / critic / executor / docs-verifier)이 한 plan을 함께 처리하고, 나는 'planning 단계에서 무엇을 할지 결정하는 일'에 집중했다. 결과는 199개 plan / 760 커밋(11일).
- vibe 코딩 → spec 기반 코딩으로 단계적으로 진화시켰다 — /planning(스펙 합의), /plan-and-build(phase 분할 + 재시작 가능), /build-with-teams(critic + docs-verifier 게이트), /integrate-ux(디자이너 vibe 결과물 흡수). 새 스킬을 만든 시점부터 같은 종류의 작업이 한 줄 명령으로 끝났다.
- AI 인프라 자체도 직접 설계했다 — Gemini 모델 전략을 'pro 기본 + 429 시 flash → lite fallback'으로 뒤집고, 전역 Rate Limit Tracking을 메모리 Map으로 두어 어떤 모델이 429를 받으면 일정 시간 skip 대상으로 마킹해 다른 요청이 같은 모델을 또 두드리지 않게 했다. '비용 = 단가 × 호출 수'가 아니라 '단가 × (호출 + 재생성)'으로 봐야 한다는 인사이트가 핵심이었다.
- 환각 차단은 프롬프트 카피라이팅이 아니라 '호출 구조 설계' 문제였다 — 글콘티 continuation이 tail 5컷만 보고 다음 컷을 만들면서 grounding이 사라지고 있었다. Grounding 블록을 프롬프트 최우선에 두고 continuation에도 매번 재주입했고, 토큰 비용은 Project 단위 Gemini Context Cache로 원작 소설을 cachedContent로 묶어 만회했다.
- 60컷 일괄 생성은 처음에 SSE 한 줄기였다가 부분 실패 처리가 복잡해져 클라이언트 Promise.allSettled로 바꿨다 — 60개 독립 요청이라 per-Promise 추적이 자연스럽고, 브라우저 호스트당 6 동시 연결이 throttling 역할을 해 별도 rate limiting 코드가 필요 없어졌다. '1개의 긴 생성=SSE / N개의 독립 생성=allSettled'를 분리한 게 후속 유지보수의 핵심이었다.

### 1분 답변 구조

- 12일 동안 혼자 Next.js 16 + Prisma 7 + Gemini로 6단계 풀스택 파이프라인 MVP를 만들었고, 199 plan / 760 커밋이 나왔다 — 본질은 4인 에이전트 팀(planner/critic/executor/docs-verifier) 하네스였고, 나는 '무엇을 할지'에 집중했다.
- 스킬을 vibe → spec으로 단계적으로 진화시켰다 — /planning(스펙 합의), /plan-and-build(phase 분할 + 재시작 가능), /build-with-teams(critic + docs-verifier 게이트), /integrate-ux(디자이너 vibe 결과물 흡수). 새 스킬마다 같은 작업이 한 줄로 끝났다.
- AI 인프라도 직접 설계했다 — Gemini를 pro 기본 + 429 시 flash→lite로 뒤집고, 메모리 Map 기반 전역 Rate Limit Tracking으로 다른 요청이 같은 모델을 또 두드리지 않게 했다. '비용은 단가가 아니라 단가 × (호출 + 재생성)'이라는 모델이 의사결정의 기준이었다.
- 환각 차단은 프롬프트 글이 아니라 '호출 구조 설계'로 풀었다 — Grounding 블록 + Continuation 재주입 + Project 단위 Context Cache. 60컷 생성은 SSE에서 Promise.allSettled로 바꿔 '1개 긴 생성 vs N개 독립 생성'의 패턴을 분리했다.
- 이 경험이 시사하는 건 'AI를 쓰는 사람'이 아니라 'AI 호출 구조와 비용 모델을 설계하는 사람'이라는 자리이고, 이 시각이 커머스 백엔드의 일상 업무(ADR 정리, 장애 분석, 코드 리뷰 자동화)에도 그대로 옮겨진다고 본다.

### 압박 질문 방어 포인트

- 'AI가 다 짠 코드 아니냐'로 들어오면 — planning 단계의 8단계 합의(기술 가능성 / 사용자 흐름 / 데이터 모델 / API / 화면 동작 / 엣지 / 마이그레이션 / 검증)가 모두 사람의 결정이고, executor는 그 결정의 80%가 박힌 task 파일에서만 실행된다는 점을 강조한다 — 실제 결정 권한은 사람이 갖고 있다.
- '12일 760 커밋이 과장 아니냐'로 압박받으면, 4인 에이전트 팀과 phase 단위 커밋 단위(planner의 task 분리 → executor 단위 작업)를 근거로 '내가 손으로 친 커밋'과 '에이전트가 만든 커밋'의 비율을 솔직하게 분리해 답한다.

### 피해야 할 약한 답변

- 'AI 도구로 빨리 만들었다'는 식으로 끝나서 본인이 어디에 결정 권한을 갖고 있었는지(planning 단계, 호출 구조, 비용 모델)가 드러나지 않는 답변.
- 환각 차단을 '프롬프트에 DO NOT을 추가했다' 수준으로만 답하고 continuation 재주입 / Context Cache / 채널 mismatch(텍스트 vs 이미지 레퍼런스) 같은 구조적 인사이트를 말하지 못하는 답변.

### 꼬리 질문 5개

**F5-1.** 4인 에이전트 팀에서 'critic'을 별도 역할로 둔 이유는 무엇이었고, 같은 모델임에도 시야 차이가 실제로 발견된 사례를 하나만 들어주세요.

**F5-2.** 전역 Rate Limit Tracking을 단일 인스턴스 메모리 Map으로 둔 한계가 분명한데, 다중 인스턴스로 확장한다면 어떤 저장소·구조를 택할 건가요?

**F5-3.** Gemini Context Caching의 5분 만료를 운영 동선과 어떻게 맞췄나요? cache miss가 발생하는 패턴이 보였나요?

**F5-4.** 이 12일 경험을 '백엔드 면접관 입장'에서 가장 의심해볼 부분은 어디라고 생각하시나요? 어떻게 답할 준비가 되어 있나요?

**F5-5.** 이 하네스를 커머스 백엔드 일상 업무에 옮긴다면 (예: 쿼리 튜닝 / 장애 대응 / ADR 정리) 어디를 가장 먼저 적용할 수 있을 것 같나요?

---

## 최종 준비 체크리스트

- 면접 직전 30분 동안 4대 핵심 경험(RAG 배치 11 Step / gRPC 503 graceful shutdown / EmbeddingMetadataProvider 전략 패턴 / 12일 AI 웹툰 MVP) 각 1분 요약을 입으로 한 번씩 리허설했는가 — 키워드는 외우지 말고 흐름만 잡는다.
- 각 경험에서 '왜 그 결정을 했는가(트레이드오프)'를 답할 수 있는가 — 예: 왜 JobExecutionContext가 아니라 @JobScope, 왜 30초 재시도가 아니라 즉시 fallback, 왜 blocklist가 아니라 allowlist, 왜 SSE가 아니라 Promise.allSettled.
- 올리브영 기술 블로그 4편(MSA 데이터 연동 / OAuth2 무중단 / SQS 데드락 / Spring 트랜잭션 동기화) 핵심 용어를 본인 경험과 매핑할 수 있는가 — 특히 Cache-Aside·Kafka 이벤트 드리븐·Resilience4j·Feature Flag.
- AI/에이전트 협업 경험을 '툴 사용자'가 아니라 '파이프라인 설계자'로 풀어낼 수 있는가 — 199 plan / 760 커밋 / 4인 에이전트 팀(planner·critic·executor·docs-verifier) / vibe → spec 전환을 한 호흡으로 설명할 수 있어야 한다.
- 약점(웰니스/커머스 도메인 미경험, Kotlin·DB 심화 미흡)에 대해 회피하지 않고 '현재 어떻게 학습 중인지' 구체적 행동으로 답할 수 있는가 — 모호한 다짐이 아니라 베이스라인 학습 트랙 + ADR 정리 습관을 근거로 든다.
- 역질문 3개 이상 준비했는가 — 팀 온보딩, MSA 도메인 경계, AI 도구 도입 여지처럼 1,600만 트래픽·실제 팀 운영 정보를 끌어낼 수 있는 질문으로.
