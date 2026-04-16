# [초안] AI 서비스 팀 경험 기반 질문 뱅크 — Spring Batch RAG 파이프라인 & Graceful Shutdown

---

## 이 트랙의 경험 요약

- Spring Batch 11개 Step 기반 Confluence 벡터 색인 파이프라인 설계 경험 — 실패 격리, 재시작 가능 구조, AsyncItemProcessor 비동기 I/O 병렬 처리까지 전 과정을 직접 설계·구현했다
- OCR 서버 배포·스케일인 시 503 에러를 Envoy 종료 시퀀스 레벨에서 진단하고 gRPC Graceful Shutdown을 NCS terminationGracePeriodSeconds 30초 제약 안에 설계해 해결했다
- Cursor Rules 20개 이상 구축과 Claude Code 하네스 기반 4인 에이전트 팀 운영으로 신규 게임 3종 및 AI 웹툰 MVP 10일 풀스택 개발을 달성하고 팀에 전파했다

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

## 메인 질문 5. Cursor Rules를 20개 이상 구축하고 Claude Code 하네스 기반 에이전트 팀을 운영한 경험을 설명해 주세요. 어떤 문제를 풀기 위해 시작했고, 팀에는 어떻게 전파했나요?

> 추가: 2026-04-16 | 업데이트: 2026-04-16

### 면접관이 실제로 보는 것

- 단순 AI 도구 사용자가 아니라 도구의 한계를 분석하고 도메인 컨텍스트 문서화 체계를 직접 설계해 팀 생산성 구조를 만든 경험인지 확인한다
- 에이전트 단독 구현(신규 게임 3종)과 에이전트 팀 오케스트레이션(웹툰 MVP)이라는 두 수준의 실제 성과를 구체적으로 설명할 수 있는지 검증한다

### 실제 경험 기반 답변 포인트

- AI 에이전트가 복잡한 슬롯 도메인에서 잘못된 설계 결정을 내리는 문제를 경험하고, 에이전트가 이해할 수 있는 언어로 도메인 컨텍스트를 문서화하는 것이 핵심임을 인식했다. Cursor Rules 20개 이상을 직접 작성해 게임 타입별 규칙, 코드 패턴, 확장 제약을 명시했다
- 이 규칙 체계 위에서 신규 게임 3종을 에이전트 단독으로 구현했다. Rules 적용 이전에는 에이전트가 도메인 특수 규칙(베팅 금액 계산, 후처리 흐름)을 잘못 구현하는 사례가 반복됐고, 적용 이후 수정 사이클이 대폭 줄었다
- AI 웹툰 도구 MVP에서는 Claude Code 하네스 기반 4인 에이전트 팀을 직접 구성해 10일 만에 Next.js + Gemini 풀스택 결과물을 냈다. 6단계 파이프라인(세계관·캐릭터·각색·글콘티 → 60컷 이미지)을 에이전트 간 역할 분담으로 처리했고 167개 plan, 555개 커밋을 달성했다
- 개인 성과에 머물지 않고 팀에 Cursor Rules 구조와 작성 방법을 공유해 반복 개발 사이클을 단축했다. 447개 테스트 파일 기반 테스트 인프라가 에이전트 생성 코드의 회귀를 검출하는 안전망 역할을 했다

### 1분 답변 구조

- AI 에이전트가 복잡한 슬롯 도메인에서 도메인 특수 규칙을 잘못 구현하는 문제를 먼저 경험했습니다. 에이전트가 제대로 동작하려면 이해할 수 있는 언어로 도메인을 문서화하는 사전 작업이 핵심이라는 것을 인식하고, Cursor Rules를 20개 이상 직접 작성해 게임 타입별 규칙, 코드 패턴, 확장 제약을 명시했습니다.
- 이 체계 위에서 신규 게임 3종을 에이전트 단독으로 구현했습니다. AI 웹툰 도구 MVP에서는 Claude Code 하네스 기반으로 4인 에이전트 팀을 직접 구성해 10일 만에 Next.js + Gemini 풀스택 결과물을 냈습니다. 6단계 파이프라인을 에이전트 간 역할 분담으로 처리했고 167개 plan, 555개 커밋을 달성했습니다.
- 개인 성과에 머물지 않고 팀에 Cursor Rules 구조와 작성 방법을 공유했습니다. 규칙 없이 에이전트를 쓰면 도메인 컨텍스트 부재로 설계 결정이 잘못된다는 점을 팀이 인식하도록 하고, 447개 테스트 파일 기반 안전망이 에이전트 생성 코드의 회귀를 검출할 수 있도록 했습니다.

### 압박 질문 방어 포인트

- "에이전트가 구현한 코드의 품질을 어떻게 보장했나요?"라는 압박에는: Cursor Rules가 코드 패턴과 제약을 명시하기 때문에 에이전트가 기존 구조를 벗어나는 코드를 생성하면 Rules 위반으로 감지됩니다. 또한 447개 테스트 파일 기반 테스트 인프라가 회귀를 검출하는 안전망 역할을 했습니다.
- "Cursor Rules 20개가 실제로 효과가 있었다는 것을 어떻게 증명하나요?"라는 심화 질문에는: Rules 없이 시도했을 때 에이전트가 도메인 특수 규칙을 잘못 구현하는 사례를 먼저 경험했고, Rules 적용 이후 수정 사이클이 줄었으며 신규 게임 3종을 에이전트 단독으로 구현 완료한 것이 직접 증거입니다.

### 피해야 할 약한 답변

- "AI 도구를 적극적으로 활용했습니다"라는 선언적 답변만 하고 어떤 문제를 풀기 위해 Rules를 체계화했는지, 팀에 어떻게 전파했는지 구체적인 내용이 없으면 차별성이 없습니다
- Claude Code나 Cursor를 단순히 코드 자동완성 도구로만 설명하는 경우 에이전트 팀 구성이나 하네스 기반 파이프라인 설계처럼 더 깊은 활용 경험을 보여주지 못합니다

### 꼬리 질문 5개

**F5-1.** Cursor Rules 20개 중 슬롯 도메인에서 가장 효과적이었던 규칙 유형은 어떤 것이었나요?

**F5-2.** 에이전트가 구현한 코드에서 사람이 직접 수정해야 했던 유형의 오류 패턴이 있었나요?

**F5-3.** Claude Code 하네스 기반 4인 에이전트 팀에서 에이전트 간 역할을 어떻게 분담했나요?

**F5-4.** 팀에 AI 도구 활용법을 전파할 때 가장 큰 저항이나 어려움은 무엇이었나요?

**F5-5.** AI 도구 도입으로 개발 사이클이 단축된 것을 구체적인 수치나 사례로 설명할 수 있나요?

---

## 최종 준비 체크리스트

- Spring Batch 11개 Step 설계 의도(실패 격리, 재시작 지점 보존)를 ItemStream 커서 저장, allowStartIfComplete 설정, @JobScope 빈 재초기화 문제까지 코드 근거와 함께 설명할 수 있다
- AsyncItemProcessor 도입 결정의 근거(I/O 바운드 분석, 직렬 대기 시간 계산)와 AsyncItemWriter와의 쌍 사용 이유, 스레드풀 크기 결정 기준을 설명할 수 있다
- 전략 패턴 전환의 OCP 근거와 if-else 분기에서 ConfluenceDocumentMetadataProvider 인터페이스로의 전환 과정, @StepScope 빈 충돌 해결 방식을 설명할 수 있다
- OCR 서버 503 진단 과정(Envoy error 111 → 종료 시퀀스 추적 → gRPC 즉시 종료 특정)과 NCS 30초 제약 안에서 preStop·grace·stopwaitsecs를 조율한 해결 설계를 설명할 수 있다
- AI 도구 도입 경험(Cursor Rules 체계화 목적과 효과, Claude Code 하네스 에이전트 팀 구성 방식)의 구체적 결과와 팀 전파 방법을 설명할 수 있다
