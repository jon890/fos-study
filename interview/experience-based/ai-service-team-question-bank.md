# [초안] AI 서비스 팀 경험 기반 질문 뱅크 — Spring Batch RAG 파이프라인 & Graceful Shutdown

---

## 이 트랙의 경험 요약

- Spring Batch 11개 Step 기반 Confluence 벡터 색인 파이프라인을 직접 설계·구현했다. 실패 격리, 재시작 가능 구조, AsyncItemProcessor 비동기 I/O 병렬 처리, OpenSearch 벌크 색인까지 설명 가능한 상태다
- OCR 서버 배포·스케일인 시 503 에러를 Envoy 종료 시퀀스 레벨에서 진단하고 gRPC Graceful Shutdown을 NCS terminationGracePeriodSeconds 30초 제약 안에 설계해 해결했다
- 최신 이력서 기준으로 AI 웹툰 제작 도구 MVP를 10일 동안 단독 풀스택으로 리드했고, Claude Code 하네스 기반 4인 에이전트 팀 운영, 167개 plan, 555개 커밋, Gemini fallback 전략과 부분 성공 생성 구조까지 실무적으로 설명할 수 있다

## 메인 질문 1. Confluence 벡터 색인 배치를 설계할 때 Step을 11개로 분리한 이유와, 재시작 가능 구조를 실제로 어떻게 구현했는지 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 단순히 기능을 구현했는지가 아니라 Step 분리의 설계 원칙(단일 책임, 실패 격리)을 이해하고 실제 문제 상황에 적용했는지 확인한다
- 재시작 가능 구조(ItemStream 커서 저장, allowStartIfComplete 설정, @JobScope 빈 재초기화 문제 해결)를 직접 구현한 경험이 있는지 검증한다

### 실제 경험 기반 답변 포인트

- Step 분리의 핵심 목적은 실패 격리다. 댓글 색인 Step이 실패해도 페이지 색인 Step 결과가 보존되고, 실패 지점부터 재시작이 가능하다. 하나의 거대한 Step에 다 넣으면 중간 실패 시 앞서 완료된 처리 결과까지 날아간다
- Reader에 ItemStream을 구현해 커서 기반 페이지네이션 위치를 ExecutionContext에 저장함으로써 중간 실패 시에도 마지막으로 처리한 지점부터 재시작이 가능하도록 했다
- @JobScope 빈(ConfluenceJobDataHolder)을 사용해 Step 간 데이터를 인메모리로 공유하되, 재시작 시 상태 로더 Step이 반드시 재실행되도록 allowStartIfComplete(true)를 설정했다. 설정하지 않으면 새 JobExecution에서 @JobScope 빈이 빈 상태로 남아 NPE가 발생한다
- JobExecutionContext는 경량 상태(커서 위치) 전용으로만 사용하고 수천 개 페이지 ID 같은 도메인 데이터는 @JobScope 인메모리 홀더에 두어, 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블에 직렬화되는 불필요한 DB 부하를 막았다

### 1분 답변 구조

- RAG 파이프라인 Step을 11개로 분리한 핵심 이유는 실패 격리입니다. 하나의 거대한 Step에 전체 로직을 넣으면 임베딩 API 장애 상황에서 앞서 완료된 페이지 색인 결과까지 날아가고 처음부터 재실행해야 합니다.
- 재시작 가능 구조는 두 축으로 구현했습니다. Reader에 ItemStream을 구현해 커서 기반 페이지네이션 위치를 ExecutionContext에 저장하고, @JobScope 빈을 채우는 상태 로더 Step에 allowStartIfComplete(true)를 설정해 재시작 시에도 반드시 재실행되도록 했습니다. 설정하지 않으면 새 JobExecution에서 빈이 빈 상태로 남아 NPE가 터집니다.
- JobExecutionContext와 @JobScope 빈의 역할도 명확히 구분했습니다. 커서 위치 같은 경량 상태는 ExecutionContext에, 수천 개 페이지 ID 같은 도메인 데이터는 @JobScope 인메모리 홀더에 두어 청크 커밋마다 DB에 직렬화되는 불필요한 부하를 막았습니다.

### 압박 질문 방어 포인트

- "Step이 11개면 관리 복잡도가 너무 높지 않나요?"라는 압박에는: Step마다 단일 책임만 가지고 앞 Step이 컨텍스트에 저장한 데이터를 뒤 Step이 읽는 구조이기 때문에 각 Step은 독립적으로 테스트하고 재시작할 수 있습니다. 복잡도가 올라가는 것이 아니라 각 단위가 명확해집니다.
- "ExecutionContext 대신 @JobScope를 쓴 이유가 정확히 무엇인가요?"라는 심화 질문에는: ExecutionContext는 청크 커밋마다 BATCH_JOB_EXECUTION_CONTEXT 테이블에 직렬화됩니다. 수천 개 페이지 ID를 매 커밋마다 DB에 읽고 쓰는 것은 불필요한 부하이고, 이 데이터는 재시작 시 다시 채우면 되기 때문에 영속화 대상이 아닙니다.

### 피해야 할 약한 답변

- "Step을 많이 나눠서 구조가 더 깔끔해졌습니다"처럼 추상적인 이점만 말하고 실패 격리, 재시작 지점 보존 같은 구체적인 설계 근거를 빠뜨리는 답변은 설계 의도를 이해하지 못한 것처럼 들립니다
- "Spring Batch가 자동으로 재시작해 준다"는 식으로 프레임워크 기능에만 의존하는 듯한 답변은 @JobScope 빈의 NPE 문제나 allowStartIfComplete 설정 같은 실제 구현 세부사항을 경험하지 못한 것처럼 보입니다

### 꼬리 질문 5개

**F1-1.** Step 간 데이터를 @JobScope 빈과 ExecutionContext 중 어떤 기준으로 나누어 저장했나요?

**F1-2.** allowStartIfComplete(true)를 설정하지 않았을 때 실제로 어떤 오류가 발생했고, 어떻게 원인을 파악했나요?

**F1-3.** 청크 사이즈는 어떻게 결정했고, 임베딩 API 속도 제한(Rate Limit)과 어떻게 균형을 맞췄나요?

**F1-4.** Step 실패 격리 덕분에 재시작이 실제로 효과적이었던 사례가 있었나요?

**F1-5.** 11개 Step의 전체 실행 시간을 모니터링하거나 줄이기 위해 시도한 것이 있었나요?

---

## 메인 질문 2. 임베딩 처리 파이프라인에서 AsyncItemProcessor를 선택한 판단 기준과, AsyncItemWriter와의 연동 방식을 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 성능 문제를 I/O 바운드 vs CPU 바운드 관점에서 분석하고 AsyncItemProcessor라는 해결책을 근거 있는 의사결정으로 선택했는지 보고 싶어 한다
- Future 기반 비동기 처리 흐름과 AsyncItemWriter가 없으면 AsyncItemProcessor 단독으로 동작하지 않는다는 점을 실제로 이해하고 있는지 확인한다

### 실제 경험 기반 답변 포인트

- 임베딩 API 호출은 네트워크 I/O 바운드 작업으로, 동기 처리 시 페이지 하나당 200ms 대기가 청크 사이즈 10 기준 2초, 수천 페이지 처리 시 수십 분으로 이어질 수 있었다
- AsyncItemProcessor는 각 아이템을 스레드풀(parallelChunkExecutor)에서 병렬로 제출하고 Future를 반환한다. AsyncItemWriter가 Writer 단계에서 Future.get()을 호출해 결과를 모아 벌크 색인하는 구조로, AsyncItemWriter 없이는 Writer가 Future 타입을 처리할 수 없다
- CompositeItemProcessor 4단계 체인(변경 감지 → 데이터 보강 → ADF 변환 → 임베딩) 전체를 AsyncItemProcessor 하나로 감쌌기 때문에 각 처리 단계의 순서와 단일 책임은 그대로 유지된다
- 스레드풀 크기는 임베딩 API의 동시 요청 수 제한과 서버 인스턴스 수를 고려해 설정했고, API 응답 지연이 늘어나는 임계점을 부하 테스트로 확인해 조정했다

### 1분 답변 구조

- 임베딩 API 호출은 전형적인 I/O 바운드 작업입니다. 페이지 하나당 응답 대기가 200ms라면 청크 사이즈 10에서 직렬 처리 시 한 청크에 2초, 수천 페이지면 수십 분이 걸립니다.
- AsyncItemProcessor를 선택한 이유는 Spring Batch의 청크 지향 처리 구조를 바꾸지 않으면서 I/O 대기 시간을 겹칠 수 있기 때문입니다. 각 아이템을 스레드풀에 제출하고 Future를 반환하면 AsyncItemWriter가 Writer 단계에서 Future.get()으로 결과를 모아 한 번에 벌크 색인합니다. AsyncItemWriter 없이는 Writer가 Future 타입을 받을 수 없어 반드시 쌍으로 사용해야 합니다.
- CompositeItemProcessor(변경 감지 → 데이터 보강 → ADF 변환 → 임베딩) 4단계 체인 전체를 AsyncItemProcessor 하나로 감쌌기 때문에 각 처리 단계의 순서와 단일 책임은 그대로 유지됩니다.

### 압박 질문 방어 포인트

- "스레드풀 크기를 얼마로 설정했고 그 근거는 무엇인가요?"라는 압박에는: 임베딩 API의 동시 요청 수 제한과 서버 인스턴스 수를 기준으로 초기값을 설정한 뒤 실제 부하 테스트를 통해 API 응답 지연이 늘어나는 임계점을 확인하고 조정했습니다. 제한 없이 스레드를 늘리면 API 측 429 오류가 발생합니다.
- "Future.get() 호출 시 타임아웃 처리는 어떻게 했나요?"라는 심화 질문에는: 임베딩 API 클라이언트 레벨에서 커넥션/읽기 타임아웃을 설정했고, 반복 실패한 아이템은 실패 횟수 임계치 초과 시 ChangeFilterProcessor 단계에서 자동 스킵하도록 설계했습니다.

### 피해야 할 약한 답변

- "비동기로 처리하면 빠르니까 AsyncItemProcessor를 썼습니다"처럼 I/O 바운드 분석 없이 단순히 속도만 이유로 드는 답변은 설계 근거가 없습니다
- AsyncItemWriter와의 연동 없이 "AsyncItemProcessor만 쓰면 된다"고 답하는 경우 실제 구현에서 Writer가 Future 타입을 받을 수 없다는 핵심을 모르는 것입니다

### 꼬리 질문 5개

**F2-1.** AsyncItemProcessor 도입 전후로 실제 처리 시간이 얼마나 단축됐나요?

**F2-2.** 스레드풀 크기 결정에 임베딩 API Rate Limit이 구체적으로 어떻게 영향을 줬나요?

**F2-3.** 병렬 처리 중 일부 아이템에서 임베딩 API가 실패하면 해당 청크 전체를 어떻게 처리했나요?

**F2-4.** CompositeItemProcessor 4단계 중 실제 병목이 어느 단계였고 어떻게 확인했나요?

**F2-5.** 배치가 여러 인스턴스에서 동시에 실행될 경우 임베딩 API Rate Limit 충돌을 어떻게 고려했나요?

---

## 메인 질문 3. 스페이스마다 다른 메타데이터 포맷 문제를 전략 패턴으로 해결한 과정을 설명해 주세요. 처음에 어떤 설계를 시도했고 어떤 트레이드오프를 인식해 전환했나요?

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- OCP(개방-폐쇄 원칙)를 실제 문제 상황에서 어떻게 적용했는지, if-else 분기를 전략 패턴으로 전환하는 판단 기준을 스스로 설명할 수 있는지 확인한다
- Provider 인터페이스를 정의하고 @Qualifier로 주입하는 Spring DI 활용 방식과 @StepScope 빈 충돌(NoUniqueBeanDefinitionException) 해결 경험을 검증한다

### 실제 경험 기반 답변 포인트

- 처음에는 EmbeddingProcessor 안에 스페이스별 if-else 분기를 넣으려 했으나, 스페이스가 늘어날수록 Processor 코드가 오염되고 기존 동작에 영향을 주는 변경이 불가피해진다는 OCP 위반을 인식해 전략 패턴으로 전환했다
- ConfluenceDocumentMetadataProvider 인터페이스를 정의하고 DefaultConfluenceDocumentMetadataProvider와 NewSpaceConfluenceDocumentMetadataProvider 두 구현체로 분리했다. EmbeddingProcessor는 인터페이스에만 의존하고 @Qualifier로 구현체를 주입한다
- 신규 스페이스 추가 시 EmbeddingProcessor 코드를 건드리지 않고 Provider 구현체만 추가하면 된다. 각 잡 Config 클래스에서 @Qualifier로 원하는 구현체를 주입하면 스페이스가 늘어도 기존 코드가 불변이다
- 두 잡에서 동일 타입 @StepScope 빈이 충돌해 NoUniqueBeanDefinitionException이 발생했다. 잡 전용 빈은 Config 클래스에서만 @Bean @StepScope로 정의하고, 공용 빈은 @Component @StepScope로 전역 등록하는 방식으로 해결했다. 테스트 코드에서도 @Qualifier를 명시해야 했다

### 1분 답변 구조

- 스페이스마다 메타데이터 포맷이 달랐을 때 처음에는 EmbeddingProcessor 안에 if-else 분기를 넣으려 했습니다. 스페이스가 늘어날수록 Processor 코드가 오염되고 기존 스페이스 동작에도 영향을 주는 변경이 불가피하다는 OCP 위반을 인식해 전략 패턴으로 전환했습니다.
- ConfluenceDocumentMetadataProvider 인터페이스를 정의하고 DefaultProvider와 NewSpaceProvider 두 구현체를 만들었습니다. EmbeddingProcessor는 인터페이스에만 의존하고 각 잡 Config 클래스에서 @Qualifier로 원하는 구현체를 주입합니다.
- 덕분에 신규 스페이스가 추가되어도 EmbeddingProcessor를 건드릴 필요가 없습니다. 실제로 두 잡에서 동일 타입 @StepScope 빈이 충돌하는 NoUniqueBeanDefinitionException을 겪었고, 잡 전용 빈은 Config에서만 정의하고 공용 빈은 @Component로 전역 등록하는 방식으로 해결했습니다.

### 압박 질문 방어 포인트

- "그냥 처음부터 인터페이스로 설계했어야 하는 거 아닌가요?"라는 압박에는: 처음 시점에는 스페이스가 하나였고 메타데이터 차이를 미리 예측하기 어려웠습니다. YAGNI 원칙상 필요해지는 시점에 리팩터링하는 것이 맞고, 두 번째 스페이스가 생기는 시점에 빠르게 전환할 수 있었습니다.
- "인터페이스에 메서드가 4개면 ISP를 위반하지 않나요?"라는 심화 질문에는: 페이지·댓글·첨부파일 각각의 메타데이터 빌드 책임이 하나의 스페이스 컨텍스트 안에 묶여 있기 때문에 같은 인터페이스로 관리하는 것이 적절하다고 판단했습니다. 구현체가 모든 메서드를 실질적으로 다르게 구현합니다.

### 피해야 할 약한 답변

- "전략 패턴을 쓰면 유지보수가 좋아진다"는 교과서적인 답변은 실제로 어떤 문제 상황에서 어떤 트레이드오프를 판단해 적용했는지 드러나지 않습니다
- if-else를 전략 패턴으로 바꾼 기계적 설명만 하고 EmbeddingProcessor가 왜 인터페이스에만 의존해야 하는지와 @StepScope 빈 충돌 해결 경험을 언급하지 않는 답변은 실제 구현 깊이가 드러나지 않습니다

### 꼬리 질문 5개

**F3-1.** DefaultProvider와 NewSpaceProvider에서 실제로 다르게 구현된 메서드는 어떤 것들이었나요?

**F3-2.** @StepScope 빈 충돌(NoUniqueBeanDefinitionException)을 처음 접했을 때 원인 파악에 어떻게 접근했나요?

**F3-3.** BodyConverterProvider도 같은 전략 패턴인데 MetadataProvider와 BodyConverterProvider의 책임 범위를 어떻게 구분했나요?

**F3-4.** 새 스페이스가 추가될 때 기존 스페이스 색인에 영향이 없음을 어떻게 검증했나요?

**F3-5.** 메타데이터 포맷이 런타임 DB 설정으로 바뀌어야 한다면 현재 @Qualifier 정적 주입 설계에서 무엇을 바꿔야 하나요?

---

## 메인 질문 4. OCR 서버 배포·스케일인 시 503 에러의 원인을 어떻게 진단했고, Graceful Shutdown을 적용해 해결한 과정을 설명해 주세요.

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 운영 중인 시스템의 간헐적 503 에러를 컨테이너 종료 시퀀스 레벨까지 추적해 근본 원인을 특정한 디버깅 사고 과정을 확인한다
- Envoy·gRPC·supervisord 계층별 종료 흐름을 이해하고 플랫폼 제약(NCS 30초 고정) 안에서 현실적인 해결책을 설계한 엔지니어링 판단력을 검증한다

### 실제 경험 기반 답변 포인트

- 에러 패턴(배포/스케일인 이벤트 직후 30~60초간 묶음 503)과 응답 헤더의 server: envoy, ECONNREFUSED(error 111)를 단서로 gRPC 서버(50051)가 Envoy보다 먼저 종료된다는 가설을 세우고 종료 시퀀스를 직접 추적했다
- preStop sleep 20초 동안 Envoy는 살아 upstream으로 라우팅하는데, SIGTERM 핸들러가 없는 gRPC 서버는 즉시 종료되어 50051 포트가 닫히고 ECONNREFUSED가 발생했다. supervisord의 기본 stopwaitsecs 10초도 grace 없이 SIGKILL을 날리는 원인이었다
- NCS의 terminationGracePeriodSeconds 30초 고정 제약(API 스펙에 필드 자체가 없음) 안에서 preStop sleep(15s) + gRPC grace(12s) + 여유(3s) = 30초로 예산을 맞췄다
- 세 파일을 조율해 수정했다: Python 서버에 signal.SIGTERM 핸들러와 server.stop(grace=12) 추가, supervisord.conf에 stopwaitsecs=17 설정(grace 12s + 여유 5s), Jenkinsfile preStop sleep을 20초에서 15초로 단축

### 1분 답변 구조

- 에러 로그 패턴(배포/스케일인 이벤트 직후 30~60초간 묶음 503)과 응답 헤더의 server: envoy, Envoy ECONNREFUSED(error 111)를 단서로 gRPC 서버가 Envoy보다 먼저 종료된다는 가설을 세웠습니다.
- 종료 시퀀스를 직접 추적해 확인했습니다. preStop sleep 20초 동안 Envoy는 살아 upstream으로 라우팅하는데, SIGTERM 핸들러가 없는 gRPC 서버는 즉시 종료되어 50051 포트가 닫히고 ECONNREFUSED가 발생했습니다. supervisord의 기본 stopwaitsecs 10초도 grace 없이 SIGKILL을 날리는 원인이었습니다.
- NCS terminationGracePeriodSeconds 30초 고정 제약 안에 세 변경을 조율했습니다. Python 서버에 signal.SIGTERM 핸들러와 server.stop(grace=12)를 추가하고, supervisord stopwaitsecs=17로 SIGKILL 차단 시간을 확보하고, preStop sleep을 20초에서 15초로 줄여 전체 합산을 30초 이내로 맞췄습니다.

### 압박 질문 방어 포인트

- "terminationGracePeriodSeconds를 늘리면 안 됐나요?"라는 압박에는: NCS는 이 값을 30초로 고정하고 API 스펙에 해당 필드 자체가 없어 변경 방법이 없었습니다. 제약 조건 안에서 preStop + gRPC grace + 여유의 합산을 30초에 맞춰 설계했습니다.
- "supervisord stopwaitsecs를 왜 grace보다 5초 더 길게 설정했나요?"라는 심화 질문에는: server.stop(grace=12)가 12초 안에 완료되면 프로세스가 정상 종료되지만, in-flight 요청이 많아 12초를 약간 초과하는 경우를 대비해 5초 여유를 줬습니다. supervisord가 SIGKILL을 날리기 전에 자연 종료할 시간을 확보한 것입니다.

### 피해야 할 약한 답변

- "503이 나서 서버를 재시작했더니 해결됐습니다"처럼 근본 원인을 특정하지 않고 임시 조치만 설명하는 답변은 운영 문제 해결 역량을 보여주지 못합니다
- "Graceful Shutdown을 추가했습니다"라고만 말하고 preStop sleep 조정, supervisord stopwaitsecs, NCS 30초 제약 같은 계층별 시퀀스 조율을 언급하지 않으면 실제 구현 깊이가 드러나지 않습니다

### 꼬리 질문 5개

**F4-1.** 종료 시퀀스를 실제로 어떻게 추적했나요? 에러 로그 외에 다른 단서나 도구를 활용했나요?

**F4-2.** 수정 후 503 에러가 완전히 사라진 것을 어떻게 검증했나요?

**F4-3.** in-flight RPC가 grace period(12초) 안에 완료되지 않는 경우를 어떻게 처리했나요?

**F4-4.** 이 문제가 OCR 서버 외에 다른 gRPC 서비스에도 잠재할 수 있다고 판단했나요? 팀에 공유했나요?

**F4-5.** NCS terminationGracePeriodSeconds 30초 고정 제약을 처음 인식한 과정은 어떠했나요?

---

## 메인 질문 5. Claude Code 하네스 기반 에이전트 팀으로 AI 웹툰 제작 도구 MVP를 10일 안에 완성한 경험을 설명해 주세요. 어떤 구조로 일을 쪼갰고, 왜 그 방식이 먹혔나요?

> 추가: 2026-04-16 | 업데이트: 2026-04-18

### 면접관이 실제로 보는 것

- 단순히 AI 코딩 툴을 써봤는지가 아니라, 짧은 기간에 큰 범위를 끝내기 위해 작업 분해, 검증 루프, 실패 복구 구조까지 설계했는지 확인한다
- 최신 이력서의 대표 경험인 웹툰 MVP를 통해 생산성뿐 아니라 모델 선택, rate limit 대응, 부분 성공 처리 같은 실전 엔지니어링 판단을 설명할 수 있는지 검증한다

### 실제 경험 기반 답변 포인트

- 배경은 사내 TF에서 웹소설 입력부터 60컷 이미지 생성까지 이어지는 6단계 AI 웹툰 MVP를 10일 안에 혼자 만들어야 했던 상황이다. 프론트, 백엔드, DB, AI 파이프라인을 모두 붙여야 해서 사람이 직접 타이핑하는 방식으로는 범위를 감당하기 어렵다고 판단했다
- 그래서 main 세션에서 계획을 정리하고, phase 파일 단위로 자기완결적인 작업을 만든 뒤, Claude Code 하네스 기반 executor, critic, docs-verifier가 순차 검증하는 구조를 만들었다. 이 구조 덕분에 167개 plan과 555개 커밋을 소화할 수 있었다
- 단순 생산성만이 아니라 기술 판단도 직접 했다. Gemini는 flash 기본 전략에서 pro 우선 + 429 fallback 구조로 바꿨고, 60컷 이미지 생성은 SSE 일괄 처리 대신 Promise.allSettled 기반 부분 성공 보존 구조로 전환해 실패 컷만 재시도 가능하게 만들었다
- 팀 전파 포인트는 '에이전트를 잘 쓰는 법'이 아니라 '에이전트가 제대로 일할 수 있는 구조를 먼저 만드는 법'이었다. Cursor Rules, docs-first, ADR 축적, 테스트 안전망을 같이 갖춰야 반복 개발 사이클이 실제로 단축된다는 점을 공유했다

### 1분 답변 구조

- 상황은 10일 안에 웹소설부터 60컷 웹툰 이미지까지 이어지는 AI 웹툰 MVP를 혼자 완성해야 했던 것이었습니다. 프론트, 백엔드, DB, AI 파이프라인 범위가 넓어서 사람 손코딩만으로는 일정이 안 나온다고 판단했습니다.
- 그래서 main 세션에서 계획을 만들고, phase 파일 단위로 executor, critic, docs-verifier가 이어받는 Claude Code 하네스 구조를 만들었습니다. 그 결과 167개 plan과 555개 커밋을 처리하며 6단계 파이프라인을 완성했습니다.
- 중요한 건 AI를 썼다는 사실보다 구조였습니다. Gemini는 pro 우선 + fallback으로 품질을 확보했고, 60컷 생성은 Promise.allSettled로 부분 성공을 보존해 실패 컷만 재시도 가능하게 했습니다. 이런 구조를 팀에 공유해 반복 개발 사이클 단축으로 이어지게 했습니다.

### 압박 질문 방어 포인트

- "에이전트가 만든 코드 품질을 어떻게 믿었나요?"라는 압박에는: executor가 생성한 코드를 critic이 계획과 대조해 APPROVE/REVISE로 검증하고, docs-verifier가 문서 정합성까지 확인하는 다단계 루프를 뒀다고 답하면 됩니다. 여기에 테스트와 직접 리뷰를 붙여 맹신이 아니라 검증 가능한 워크플로로 운영했다고 설명하면 됩니다.
- "555개 커밋이면 그냥 잔커밋 많은 것 아닌가요?"라는 심화 질문에는: 핵심은 커밋 수 자체가 아니라 167개 plan을 phase 단위로 독립 실행하고 실패 시 해당 지점부터 재시작 가능하게 만든 점입니다. 짧은 피드백 루프와 실패 복구 가능성이 일정 준수에 실질적으로 기여했다고 설명하면 됩니다.

### 피해야 할 약한 답변

- "AI 도구를 써서 빨리 만들었습니다"처럼 생산성만 강조하고 작업 분해 구조, 검증 루프, rate limit 대응, 부분 성공 처리 같은 엔지니어링 판단을 말하지 않으면 깊이가 부족해 보입니다
- Claude Code를 단순 자동완성 도구처럼 설명하면 하네스 기반 오케스트레이션 경험과 docs-first 운영 경험이 전혀 드러나지 않습니다

### 꼬리 질문 5개

**F5-1.** executor, critic, docs-verifier 각 역할을 왜 분리했나요? 한 에이전트로 다 하면 안 됐나요?

**F5-2.** 60컷 이미지 생성에서 SSE 일괄 처리 대신 Promise.allSettled로 바꾼 이유와 트레이드오프는 무엇이었나요?

**F5-3.** Gemini 모델 전략을 flash 기본에서 pro 우선 + fallback으로 바꾼 의사결정 근거는 무엇이었나요?

**F5-4.** docs-first와 ADR 축적이 실제로 에이전트 생산성에 어떤 영향을 줬나요?

**F5-5.** 이 경험이 올리브영 웰니스 백엔드 역할과 어떻게 연결된다고 보나요?

---

## 최종 준비 체크리스트

- Spring Batch 11개 Step 설계 의도(실패 격리, 재시작 지점 보존)를 ItemStream 커서 저장, allowStartIfComplete 설정, @JobScope 빈 재초기화 문제까지 코드 근거와 함께 설명할 수 있다
- AsyncItemProcessor 도입 결정의 근거(I/O 바운드 분석, 직렬 대기 시간 계산)와 AsyncItemWriter와의 쌍 사용 이유, 스레드풀 크기 결정 기준을 설명할 수 있다
- 전략 패턴 전환의 OCP 근거와 if-else 분기에서 ConfluenceDocumentMetadataProvider 인터페이스로의 전환 과정, @StepScope 빈 충돌 해결 방식을 설명할 수 있다
- OCR 서버 503 진단 과정(Envoy error 111 → 종료 시퀀스 추적 → gRPC 즉시 종료 특정)과 NCS 30초 제약 안에서 preStop·grace·stopwaitsecs를 조율한 해결 설계를 설명할 수 있다
- AI 웹툰 MVP 경험에서 하네스 기반 작업 분해 구조, Gemini 모델 선택 전략, 부분 성공 처리, docs-first 운영 방식을 올리브영 백엔드 면접 맥락과 연결해 설명할 수 있다
