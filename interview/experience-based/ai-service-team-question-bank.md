# [초안] AI 서비스 팀 경험 기반 질문 은행 — Spring Batch RAG 파이프라인 · 배치 재시작 · Graceful Shutdown · AI 도구 도입

---

## 이 트랙의 경험 요약

- Spring Batch 기반 RAG 색인 파이프라인을 처음부터 설계한 경험 — 11개 Step 분리, 실패 격리, 재시작 가능성을 중심으로 설계 의사결정을 설명할 수 있어야 한다
- AsyncItemProcessor + CompositeItemProcessor 체이닝을 통한 I/O 병렬화 설계 — 임베딩 API 호출 병목을 어떻게 진단하고 해결했는지 메커니즘 수준으로 설명할 수 있어야 한다
- 운영 장애(503 ECONNREFUSED) 원인을 Envoy sidecar 종료 시퀀스 수준까지 추적한 경험 — 제약 조건(terminationGracePeriodSeconds 30초)을 고려한 예산 설계까지 설명할 수 있어야 한다
- Claude Code 하네스 기반 4인 에이전트 팀으로 10일 풀스택 MVP를 완성한 경험 — Rate Limit 전략, 부분 성공 처리, 토큰 절감 판단을 트레이드오프 관점에서 설명할 수 있어야 한다

## 메인 질문 1. Spring Batch를 선택해 11개 Step으로 분리한 이유와 Step 실패 격리가 실제 운영에서 어떻게 동작하는지 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 단순 스케줄러 대비 Spring Batch를 선택한 기술적 근거를 묻는다 — 재시작 가능성·청크 처리·실행 이력 관리를 실제 요구사항과 연결할 수 있는지 확인한다
- Step 분리가 운영 내구성을 어떻게 높였는지 검증한다 — 댓글 Step 실패 시 페이지 Step 결과가 보존되고 실패 지점부터 재시작된다는 메커니즘을 설명할 수 있어야 한다
- 11개라는 숫자 자체가 아니라 단일 책임 분리 원칙에 따라 설계했음을 보여줘야 한다

### 실제 경험 기반 답변 포인트

- 재시작 가능성: 임베딩 API 장애로 페이지 색인 Step이 중단돼도 이미 완료된 스페이스 수집·초기화 Step 결과가 보존되고 실패 지점부터 재시작 가능하다
- 청크 처리로 OOM 방지: 수천 개 문서를 한 번에 메모리에 올리지 않고 설정된 사이즈씩 커밋하므로 힙 사용량이 예측 가능하다
- Step 단위 실패 격리: BATCH_STEP_EXECUTION 상태가 각 Step을 독립적으로 추적하므로 댓글 Step 실패가 페이지 Step 성공에 영향을 주지 않는다
- 실행 이력 자동 관리: Job 실행 이력이 BATCH_JOB_EXECUTION 테이블에 자동으로 쌓여 언제 돌았고 성공·실패했는지 운영 추적이 가능하다
- Step 간 컨텍스트 공유 설계: 대용량 페이지 ID 목록은 JobExecutionContext 직렬화 부하를 피해 @JobScope 인메모리 홀더로 분리했다

### 1분 답변 구조

- 결정 배경: RAG 색인 파이프라인은 수집·변환·임베딩·색인·삭제 동기화라는 성격이 다른 책임이 공존해 단일 프로세스로 구현하면 중간 실패 시 전체 재실행이 필요했고, 임베딩 API처럼 외부 의존이 많은 환경에서는 신뢰성이 핵심 요구였습니다
- 핵심 설계: 11개 Step으로 분리해 각 Step이 단일 책임만 가지도록 했고, 앞 Step이 실패해도 뒤 Step의 상태가 오염되지 않도록 격리했습니다. BATCH_STEP_EXECUTION 상태가 Step별로 독립적으로 관리되어 재시작 시 COMPLETED Step은 스킵되고 실패 Step부터 이어서 실행됩니다
- 실제 효과: 임베딩 API 장애로 페이지 색인 Step이 중단돼도 이미 완료된 스페이스 수집·초기화 Step은 보존되고 페이지 Step부터 재시작할 수 있었습니다. 하나의 거대한 Step이었다면 처음부터 다시 돌려야 했을 것입니다

### 압박 질문 방어 포인트

- 11개 Step이 너무 많은 것 아닌가요? → Step 수보다 책임 분리의 명확성이 유지보수성을 결정합니다. 각 Step이 단일 책임을 가지므로 어느 단계에서 실패했는지 즉시 특정되고, 재시작 지점도 명확합니다. 대안인 단일 Step은 실패 격리 이점을 포기하는 트레이드오프입니다
- Spring Batch 학습 비용이 높지 않나요? → 재시작 가능성과 실행 이력 관리를 직접 구현하면 그 비용이 더 높습니다. 특히 임베딩 API처럼 외부 의존이 많은 파이프라인은 신뢰성이 핵심이라 선택이 합리적이었습니다. 실제로 API 장애 후 재시작이 자연스럽게 동작해 운영 부담이 줄었습니다

### 피해야 할 약한 답변

- Spring Batch는 대용량 처리에 좋아서 썼습니다처럼 일반론만 말하고 Step 분리가 실제 운영에서 어떤 내구성을 제공했는지 설명 못하는 답변 — 올리브영 면접관은 대규모 커머스 운영 경험을 기대하므로 구체적 장애 시나리오와 연결해야 한다
- Step 실패 격리가 어떻게 동작하는지 BATCH_STEP_EXECUTION 상태나 재시작 시 COMPLETED Step 스킵 메커니즘 없이 격리된다고만 말하는 답변 — 메커니즘을 모르면 실제로 경험했다는 신뢰를 주지 못한다

### 꼬리 질문 5개

**F1-1.** JobExecutionContext 대신 @JobScope 빈으로 Step 간 데이터를 공유한 이유와 JobExecutionContext를 썼을 때 발생하는 구체적 문제는 무엇인가요?

**F1-2.** 재시작 시 @JobScope 빈이 빈 상태로 초기화되어 NPE가 발생하는 문제를 allowStartIfComplete(true)로 해결했다면, 해당 Step을 멱등하게 설계하지 않으면 어떤 부작용이 생기나요?

**F1-3.** Step 단위 청크 크기는 어떻게 결정했고, 너무 작거나 너무 크면 각각 어떤 문제가 생기나요?

**F1-4.** BATCH_JOB_EXECUTION 테이블에 이력이 계속 쌓이면 관리 전략이 필요한데 어떻게 접근했나요?

**F1-5.** 비슷한 구조의 배치를 올리브영 상품 색인 파이프라인에 적용한다면 Step 구성을 어떻게 설계하겠나요?

---

## 메인 질문 2. AsyncItemProcessor를 도입해 임베딩 API 호출 병목을 해결한 과정과 CompositeItemProcessor 4단계 체이닝 설계를 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- I/O 바운드 작업에서 동기 처리의 병목을 스스로 진단하고 해결한 경험을 평가한다 — 단순히 AsyncItemProcessor를 써서 빠르다가 아니라 왜 I/O 바운드에서 비동기가 효과적인지 설명할 수 있어야 한다
- Future 기반 비동기 처리가 Writer 단계에서 AsyncItemWriter.get()으로 어떻게 합산되는지 메커니즘 이해 깊이를 확인한다
- CompositeItemProcessor 체이닝에서 ChangeFilterProcessor null 반환으로 비용을 절감한 설계 판단을 평가한다

### 실제 경험 기반 답변 포인트

- 임베딩 API는 네트워크 I/O로 페이지 하나당 대기 시간이 200ms, 동기로 처리하면 청크 10개에 2초 이상 소요되어 수천 페이지 처리 시 수 시간이 걸렸다
- AsyncItemProcessor로 청크 내 아이템을 parallelChunkExecutor 스레드풀에서 병렬 처리해 처리 시간을 단축했다
- AsyncItemProcessor 반환 타입은 Future<T>이므로 AsyncItemWriter가 Future.get()을 호출해 결과를 수집한 후 벌크 색인한다
- CompositeItemProcessor 4단계: ChangeFilterProcessor(version 비교 후 미변경 null 반환) → EnrichmentProcessor(첨부파일·작성자·멘션 보강) → BodyConvertProcessor(ADF→Markdown) → EmbeddingProcessor(임베딩 API 호출)
- ChangeFilterProcessor가 null을 반환하면 Spring Batch가 해당 아이템을 자동 스킵해 미변경 문서에 대한 임베딩 API 호출 비용을 제거했다

### 1분 답변 구조

- 문제 인식: 임베딩 API 호출이 I/O 바운드여서 페이지 하나당 API 대기 시간이 처리 시간의 대부분이었습니다. 동기 처리 시 청크 10개에 2초 이상, 스페이스 전체로는 수 시간이 걸리는 계산이 나왔습니다
- 해결 구조: AsyncItemProcessor로 청크 내 아이템을 parallelChunkExecutor 스레드풀에서 병렬 처리했고, 반환된 Future<T>를 AsyncItemWriter가 get()으로 수집해 OpenSearch에 벌크 색인했습니다
- 추가 최적화: CompositeItemProcessor 4단계 중 맨 앞 ChangeFilterProcessor가 OpenSearch에 색인된 version과 Confluence API version을 비교해 미변경 문서에 null을 반환하면 Spring Batch가 자동 스킵합니다. 덕분에 실제 변경된 문서만 임베딩 API를 호출해 비용을 절감했습니다

### 압박 질문 방어 포인트

- 스레드풀 사이즈를 어떻게 결정했나요? → 임베딩 API의 Rate Limit과 서버 스펙을 기준으로 설정했습니다. 너무 크면 Rate Limit 초과, 너무 작으면 병렬화 효과가 줄어 실측 후 조정했습니다. Rate Limit이 제약이 되는 경우라면 청크 사이즈와 스레드풀 사이즈를 함께 튜닝해야 합니다
- AsyncItemProcessor 사용 시 예외 처리는 어떻게 했나요? → Future.get() 단계에서 예외가 발생하면 Spring Batch 청크 롤백이 트리거됩니다. 임베딩 API 타임아웃처럼 재시도 가능한 예외는 RetryTemplate으로 감쌌습니다

### 피해야 할 약한 답변

- 비동기라서 빠릅니다처럼 왜 I/O 바운드 작업에서 비동기가 효과적인지 CPU 바운드와의 차이 설명 없이 결과만 말하는 답변 — 올리브영처럼 대규모 트래픽 환경에서는 병목 진단 능력이 중요하다
- AsyncItemProcessor와 AsyncItemWriter의 Future 계약 관계를 모르거나 Writer가 get()을 호출한다는 메커니즘 없이 그냥 비동기로 쓴다고만 설명하는 답변 — 직접 구현했다는 신뢰를 주지 못한다

### 꼬리 질문 5개

**F2-1.** ChangeFilterProcessor에서 null 반환으로 스킵 처리하는 방식의 단점과 대안은 무엇인가요?

**F2-2.** CompositeItemProcessor 체이닝에서 한 단계가 예외를 던지면 나머지 단계와 청크 커밋은 어떻게 되나요?

**F2-3.** parallelChunkExecutor 스레드풀 사이즈와 청크 사이즈 사이의 관계를 어떻게 조율했나요?

**F2-4.** 임베딩 API가 Rate Limit를 초과했을 때 재시도 전략은 어떻게 설계했고 backoff 설정은 어떻게 했나요?

**F2-5.** AsyncItemProcessor 없이 CompletableFuture를 직접 써서 병렬화하는 방식과 비교하면 Spring Batch 통합 측면에서 어떤 차이가 있나요?

---

## 메인 질문 3. 배치 중간 실패 후 재시작 가능성을 확보하기 위해 ItemStream과 ExecutionContext, @JobScope 빈을 어떻게 조합했나요?

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 대용량 배치에서 중간 실패 복구 메커니즘을 직접 설계한 경험을 검증한다 — ItemStream의 open·update·close 계약과 ExecutionContext 영속화 타이밍을 설명할 수 있어야 한다
- @JobScope 빈 재시작 시 초기화 문제와 allowStartIfComplete(true) 대응처럼 엣지 케이스 인식 수준을 평가한다
- JobExecutionContext와 @JobScope 인메모리 홀더 선택 기준을 설명할 수 있는지 확인한다

### 실제 경험 기반 답변 포인트

- Reader에 ItemStream을 구현해 read() 호출 시마다 페이지네이션 오프셋을 ExecutionContext에 저장하고, 청크 커밋마다 BATCH_STEP_EXECUTION_CONTEXT 테이블에 영속화해 중단 지점부터 재시작 가능하게 했다
- @JobScope ConfluenceJobDataHolder를 도입해 스페이스 정보·페이지 ID 목록 같은 도메인 데이터를 인메모리로 공유했다 — JobExecutionContext에 넣으면 매 청크 커밋마다 수천 개 ID가 직렬화되어 DB 부하가 컸다
- Job 재시작 시 @JobScope 빈이 새 인스턴스로 초기화되므로 상태를 채우는 Step에 allowStartIfComplete(true) 설정이 없으면 COMPLETED로 스킵되어 빈이 빈 상태로 남고 NPE가 발생한다
- JobExecutionContext는 재시작을 위한 경량 커서 위치 전용, 도메인 대용량 데이터는 @JobScope 인메모리 홀더로 분리하는 원칙을 적용했다
- @JobScope는 내부적으로 CGLIB 프록시를 생성해 싱글톤 빈에 안전하게 주입할 수 있고, 실제 호출 시 현재 Job 스코프 인스턴스로 위임된다

### 1분 답변 구조

- 커서 위치 보존: Reader가 ItemStream을 구현해 페이지네이션 오프셋을 update()에서 ExecutionContext에 저장하고 청크 커밋마다 DB에 영속화했습니다. 임베딩 API 장애로 중단되면 마지막 처리한 오프셋부터 재시작합니다
- @JobScope 빈 도입 이유: 페이지 ID 목록 같은 대용량 데이터를 JobExecutionContext에 넣으면 매 청크 커밋마다 직렬화 비용이 발생합니다. @JobScope 인메모리 홀더로 분리해 JobExecutionContext는 경량 커서 위치 전용으로만 쓰는 원칙을 세웠습니다
- 재시작 엣지 케이스: Job 재시작 시 @JobScope 빈이 새 인스턴스로 초기화되는데, 상태를 채우는 Step이 COMPLETED로 스킵되면 빈이 빈 상태로 남아 NPE가 발생합니다. allowStartIfComplete(true)로 해당 Step이 재시작 시에도 항상 재실행되게 했습니다

### 압박 질문 방어 포인트

- @JobScope 빈을 쓰면 재시작 시 빈이 초기화되어 데이터 일관성이 깨지지 않나요? → allowStartIfComplete(true)로 상태 로더 Step이 항상 재실행되게 했습니다. Confluence API를 다시 호출해 상태를 채우는 방식이 멱등하게 설계되어 있어 재실행해도 부작용이 없습니다
- ExecutionContext에 저장하는 커서 데이터 크기에 제한이 없나요? → ExecutionContext는 오프셋이나 마지막 처리 ID처럼 경량 상태만 넣는 원칙을 지켰습니다. 도메인 데이터를 넣으면 BATCH_STEP_EXECUTION_CONTEXT 컬럼 크기 제한에도 걸릴 수 있어 @JobScope 빈으로 분리했습니다

### 피해야 할 약한 답변

- Spring Batch가 자동으로 재시작해준다고만 알고 ItemStream의 open·update·close 계약이나 ExecutionContext 영속화 타이밍을 설명 못하는 답변 — 구현을 직접 했다는 신뢰를 주지 못한다
- @JobScope와 @StepScope의 차이를 구분 못하거나 재시작 시 @JobScope 빈 초기화 문제와 allowStartIfComplete(true) 연결을 경험한 적 없다는 답변 — 실제 운영 경험이 있다면 이 엣지 케이스는 반드시 마주쳤을 것이다

### 꼬리 질문 5개

**F3-1.** ItemStream의 open·update·close가 각각 호출되는 시점은 언제이고, 청크 처리 중 예외가 발생하면 update는 어떻게 동작하나요?

**F3-2.** 청크 처리 중 예외가 발생했을 때 ExecutionContext 롤백은 어떻게 동작하고 커서 위치가 안전하게 보존되나요?

**F3-3.** BATCH_STEP_EXECUTION_CONTEXT 테이블에 직렬화되는 데이터 크기가 너무 커지면 어떤 문제가 생기고 어떻게 관리했나요?

**F3-4.** @StepScope와 @JobScope 중 어떤 상황에서 각각을 선택해야 하고, 잘못 선택하면 어떤 문제가 생기나요?

**F3-5.** 재시작 시 이미 COMPLETED된 Step의 결과가 유효하지 않을 수 있는 시나리오(예: 외부 데이터 변경)는 어떻게 처리했나요?

---

## 메인 질문 4. OCR 서버 배포·스케일인 시 발생한 503 에러를 어떻게 원인을 추적하고 수정했는지 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 운영 장애 원인을 네트워크·프로세스 레벨까지 추적하는 디버깅 역량을 평가한다 — error 111(ECONNREFUSED)에서 SIGTERM 핸들러 누락까지 연결하는 추론 과정을 설명할 수 있어야 한다
- Graceful Shutdown 설계에서 NCS terminationGracePeriodSeconds 30초 제약을 고려해 시간 예산을 배분한 경험을 확인한다
- Envoy sidecar 환경에서 컨테이너 종료 순서와 preStop hook 역할을 이해하고 있는지 검증한다

### 실제 경험 기반 답변 포인트

- 에러 패턴 분석: error 111(ECONNREFUSED) + response header server: envoy 조합으로 Envoy는 살아있고 upstream(포트 50051) 연결이 거부됐음을 확인했다
- 종료 시퀀스 추적: preStop sleep 20s 동안 gRPC 서버가 SIGTERM 수신 즉시 종료되어 50051이 닫히고, 아직 살아있는 Envoy가 50051에 연결 시도하다 503 반환했다
- 근본 원인: Python gRPC 서버에 SIGTERM 핸들러가 없어 신호 수신 시 즉시 프로세스 종료, server.wait_for_termination()만으로는 graceful drain이 불가능했다
- NCS 제약: terminationGracePeriodSeconds가 30초로 고정되어 preStop(15s) + gRPC grace(12s) + 여유(3s) 예산을 설계했다
- 수정 내용: signal.signal(SIGTERM, handler)로 server.stop(grace=12) 호출, supervisord stopwaitsecs=17 추가, Jenkinsfile preStop sleep을 20에서 15로 단축했다

### 1분 답변 구조

- 가설 수립: 503 에러가 배포·스케일인 이벤트와 정확히 일치하고 error 111(ECONNREFUSED)이 반복되어 gRPC 서버가 Envoy보다 먼저 종료된다는 가설을 세웠습니다
- 원인 확인: 종료 시퀀스를 추적하니 preStop이 Envoy drain 후 sleep 20s 동안 gRPC 서버가 SIGTERM을 받아 즉시 죽었고, Envoy가 남은 시간 동안 50051에 연결을 시도하다 503을 반환했습니다. Python 서버에 SIGTERM 핸들러가 없었던 것이 근본 원인이었습니다
- 제약 고려 후 수정: NCS가 terminationGracePeriodSeconds를 30초로 고정해서 preStop 15초·gRPC grace 12초·여유 3초로 예산을 맞췄습니다. signal.signal(SIGTERM, handler)로 server.stop(grace=12)를 호출하고, supervisord stopwaitsecs=17로 SIGKILL 타임아웃을 늘렸습니다

### 압박 질문 방어 포인트

- terminationGracePeriodSeconds를 늘리면 더 간단하지 않나요? → NCS 인프라가 30초로 고정하고 API 스펙에도 해당 필드가 없어 변경 방법이 없었습니다. 제약 안에서 예산을 배분하는 것이 유일한 선택이었고, 이런 인프라 제약 파악이 원인 분석보다 선행되어야 했습니다
- preStop sleep을 없애면 더 간단하지 않나요? → preStop sleep은 Envoy가 새 연결을 받지 않도록 drain 시간을 확보하는 역할입니다. sleep 없이 gRPC 서버만 graceful shutdown하면 Envoy가 종료되기 전에 새 요청을 upstream으로 라우팅하다가 503이 날 수 있습니다

### 피해야 할 약한 답변

- 503이 나서 서버를 재배포하거나 재시작했다는 식으로 근본 원인 분석 없이 증상만 설명하는 답변 — 올리브영은 대규모 트래픽 운영 환경이므로 장애 원인 추적 역량을 중요하게 본다
- error 111의 의미(ECONNREFUSED)나 Envoy sidecar 구조를 이해하지 못한 채 gRPC 서버 문제라고만 설명하는 답변 — 왜 Envoy 헤더가 있는데 upstream 연결이 실패했는지 설명하지 못하면 실제 분석을 했다는 신뢰를 주지 못한다

### 꼬리 질문 5개

**F4-1.** Graceful Shutdown에서 Readiness Probe를 먼저 fail시키는 것이 왜 중요하고, 이 OCR 서버 케이스에서는 Readiness Probe와 preStop의 순서가 어떻게 됐나요?

**F4-2.** gRPC의 server.stop(grace=N)에서 grace 시간 동안 실제로 어떤 일이 일어나고, grace 시간이 만료되면 어떻게 처리되나요?

**F4-3.** Envoy sidecar가 있는 환경에서 앱 컨테이너와 사이드카 컨테이너의 종료 순서를 어떻게 제어하고, 이 케이스에서는 어떤 순서가 목표였나요?

**F4-4.** supervisord stopwaitsecs가 만료되면 어떤 신호가 전송되고 gRPC 서버에 어떤 영향을 주나요?

**F4-5.** 비슷한 구조의 Java Spring Boot 서버에서 Graceful Shutdown을 설정한다면 Python gRPC 서버 케이스와 어떤 점이 다른가요?

---

## 메인 질문 5. Claude Code 하네스 기반 4인 에이전트 팀으로 AI 웹툰 제작 도구 MVP를 10일 만에 완성한 과정과 핵심 기술 판단을 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- AI 개발 도구를 개인 생산성이 아닌 팀 생산성 확대로 연결한 경험을 평가한다 — 슬롯 팀 Cursor Rules 20개 구축에서 웹툰 도구 에이전트 팀 운영까지 일관된 도구 설계 철학이 있는지 확인한다
- 복잡한 멀티모달 파이프라인(Gemini Rate Limit, 60컷 부분 성공)에서 엔지니어링 판단과 트레이드오프를 설명할 수 있는지 검증한다
- 10일 단독 풀스택이라는 제약 조건에서 어떤 것을 의도적으로 포기했는지 트레이드오프 인식을 평가한다

### 실제 경험 기반 답변 포인트

- 10일 단독 풀스택: Next.js + Gemini 기반 6단계 파이프라인(세계관·캐릭터·각색·글콘티·이미지 60컷) 전체 구현
- Claude Code 하네스로 4인 에이전트 팀을 구성해 167 plan·555 커밋 달성 — 에이전트에 도메인 컨텍스트와 설계 원칙을 규칙으로 주입해 반복 작업을 위임했다
- Gemini 모델 전략: 퀄리티 우선 모델 + 429 fallback + 전역 Rate Limit Tracking으로 API 한도 초과 없이 안정적 처리
- 통합 분석으로 토큰 75% 절감: 개별 호출 대신 배치 분석으로 동일 컨텍스트를 재사용했다
- Promise.allSettled 기반 60컷 부분 성공: 일부 컷 실패 시에도 성공한 컷은 반환해 전체 실패를 방지했다
- Zod 단일 소스: 스키마 정의와 타입 추론을 Zod로 통합해 프론트-백 타입 불일치를 구조적으로 제거했다

### 1분 답변 구조

- 배경과 목표: 사내 TF에 10일 단독 차출로 웹소설 텍스트에서 60컷 이미지까지 생성하는 AI 웹툰 제작 도구 MVP를 완성해야 했습니다. 6단계 파이프라인 전체를 Next.js + Gemini로 구현하는 범위였습니다
- 에이전트 팀 운영: Claude Code 하네스로 4인 에이전트 팀을 구성해 단계별 생성 작업을 병렬화했고 10일간 167 plan·555 커밋을 달성했습니다. Gemini 호출은 전역 Rate Limit Tracker로 429 에러를 사전 차단하고 fallback 모델을 자동 전환했습니다
- 핵심 트레이드오프: 60컷 이미지 생성은 일부 실패가 불가피하다고 판단해 Promise.allSettled로 부분 성공을 허용했고, 통합 분석으로 동일 컨텍스트를 재사용해 토큰을 75% 절감했습니다. Zod 단일 소스로 타입 안정성을 확보해 프론트-백 불일치를 구조적으로 차단했습니다

### 압박 질문 방어 포인트

- 에이전트가 코드를 생성한다면 코드 품질을 어떻게 보장했나요? → Cursor Rules와 동일하게 에이전트에 도메인 컨텍스트와 설계 원칙을 규칙으로 주입했습니다. 핵심 로직과 아키텍처 결정은 직접 검토하고 에이전트는 반복 구현에 집중시켰습니다. Zod 단일 소스처럼 구조가 강제하는 품질 보장책도 함께 사용했습니다
- 10일이라는 일정에서 품질을 희생한 것 아닌가요? → Zod 단일 소스로 타입 안정성을 확보하고, 부분 성공 처리로 UX 안정성을 지켰습니다. MVP이므로 완성도보다 핵심 파이프라인 검증을 우선했고, 이는 범위와 일정을 함께 고려한 의도적 트레이드오프였습니다

### 피해야 할 약한 답변

- AI 도구를 잘 써서 빨리 만들었습니다처럼 Rate Limit 전략·부분 성공 설계·토큰 절감 판단 같은 구체적 엔지니어링 결정을 설명 못하는 답변 — 도구를 쓴 것이 아니라 도구를 설계했다는 것을 보여줘야 한다
- 에이전트 도구 도입을 개인 생산성 향상으로만 설명하고 팀 전파나 도구 설계 경험(Cursor Rules 구축·팀 확산)을 언급하지 않는 답변 — 올리브영은 팀 전체가 빠르게 기여할 수 있는 구조를 만드는 역량을 기대한다

### 꼬리 질문 5개

**F5-1.** Gemini 전역 Rate Limit Tracker를 직접 구현한 이유와 구체적인 설계 방식은 무엇인가요?

**F5-2.** Promise.allSettled로 부분 성공을 허용했을 때 클라이언트에게 결과와 실패 정보를 어떻게 표현했나요?

**F5-3.** Claude Code 하네스에서 에이전트 4인에게 작업을 분배하는 기준은 무엇이었고, 에이전트 간 결과물 통합은 어떻게 처리했나요?

**F5-4.** Zod 단일 소스로 전환하기 전에 실제로 어떤 타입 불일치 버그가 발생했고 전환 후 어떻게 해소됐나요?

**F5-5.** 슬롯 게임 팀에서 Cursor Rules 20개를 구축해 팀에 전파한 경험이 이번 AI 웹툰 도구 에이전트 운영 방식에 어떻게 연결됐나요?

---

## 최종 준비 체크리스트

- Spring Batch Step 실패 격리 메커니즘(BATCH_STEP_EXECUTION 상태, 재시작 시 COMPLETED Step 스킵)을 구체적인 시나리오와 함께 30초 안에 설명할 수 있다
- AsyncItemProcessor + AsyncItemWriter의 Future 계약(Writer가 get()을 호출해 수집 후 벌크 색인)과 CompositeItemProcessor 4단계 역할을 각각 설명할 수 있다
- ItemStream open·update·close 타이밍, ExecutionContext 영속화 시점, @JobScope 빈 재시작 시 allowStartIfComplete(true) 필요성을 연결해 설명할 수 있다
- error 111(ECONNREFUSED)에서 출발해 SIGTERM 핸들러 누락까지 원인 추적 과정을 설명하고, preStop + gRPC grace + terminationGracePeriodSeconds 예산 배분 숫자를 암기하고 있다
- Claude Code 하네스 에이전트 팀 운영에서 Rate Limit 전략, 부분 성공 처리(Promise.allSettled), 토큰 75% 절감 판단을 트레이드오프 관점에서 설명할 수 있다
