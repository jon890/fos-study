# Confluence 문서를 OpenSearch에 벡터 색인하기 — Spring Batch 파이프라인 설계기

**진행 기간**: 2026.01 ~ 2026.03

사내 AI 서비스에 RAG 기능을 붙이기 위해 Confluence 문서를 벡터 DB에 색인하는 배치 파이프라인을 처음부터 설계하고 구현했다. 단순히 텍스트를 긁어 넣는 것부터 시작해서, 댓글·첨부파일 처리, 삭제 동기화, 다중 스페이스 지원까지 점진적으로 확장한 과정을 정리했다.

---

## 어떤 서비스인가

**AI Playground**는 사내 직원이 사내 지식 베이스를 AI로 검색할 수 있는 서비스다. 질문을 던지면 관련 문서를 찾아서 LLM이 답변을 생성한다. 이게 요즘 많이 쓰는 **RAG(Retrieval-Augmented Generation)** 패턴이다.

RAG가 동작하려면 검색 단계에서 "질문과 의미적으로 유사한 문서"를 빠르게 찾아야 한다. 단순 키워드 검색이 아니라 **벡터 유사도 검색**을 써야 하기 때문에, 원본 문서를 임베딩 모델로 변환한 **벡터**를 미리 계산해서 저장해 두어야 한다. 그 역할을 이 배치가 한다.

```
[Confluence 문서]
       ↓ 수집 (REST API)
[배치 파이프라인]
       ↓ 임베딩 API 호출
[벡터 + 메타데이터]
       ↓ 색인
[OpenSearch]
       ↓ 유사도 검색
[AI Playground 서비스]
```

---

## 왜 Spring Batch인가

단순한 스케줄러로 구현할 수도 있었지만, Spring Batch를 선택한 이유가 있다.

- **재시작 가능**: 배치가 중간에 실패해도 어디서 멈췄는지 기록하고 이어서 실행할 수 있다. 임베딩 API 장애로 페이지 처리가 중단됐을 때 처음부터 다시 돌릴 필요가 없다.
- **청크 처리**: 페이지를 10개씩 묶어서 처리하고 커밋한다. 전체를 메모리에 올리지 않아서 OOM 위험이 없다.
- **Step 단위 책임 분리**: 페이지 색인 → 댓글 색인 → 삭제 동기화를 각각 독립적인 Step으로 만들면, 한 Step이 실패해도 다른 Step에 영향이 없다.
- **실행 이력 관리**: Job 실행 이력이 DB에 자동으로 쌓여서 언제 돌았고 성공/실패했는지 추적할 수 있다.

---

## 배치 잡 전체 구조

Confluence 색인 잡은 다음 순서로 실행된다.

```
startIndexingJobStep          ← 색인 작업 시작 기록
    ↓
initConfluenceSourceStep      ← Confluence 연결 정보 초기화 (baseUrl, 토큰)
    ↓
confluenceSpaceCollectStep    ← 대상 스페이스 정보 수집, Job 컨텍스트에 저장
    ↓
confluencePageIndexingStep    ← 페이지 수집 → 임베딩 → OpenSearch 색인
    ↓
confluencePageIdCollectStep   ← 댓글 조회에 쓸 페이지 ID 목록 수집
    ↓
confluenceCommentIndexingStep ← 댓글 수집 → 임베딩 → OpenSearch 색인
    ↓
confluenceDeletedPageRemoveStep      ← 삭제된 페이지 제거
    ↓
confluenceDeletedCommentRemoveStep   ← 삭제된 댓글 제거
    ↓
confluenceDeletedAttachmentRemoveStep ← 삭제된 첨부파일 제거
    ↓
confluenceIndexRefreshStep    ← 색인 갱신
    ↓
completeIndexingJobStep       ← 색인 작업 완료 기록
```

11개 Step이 순서대로 실행된다. 각 Step은 단일 책임만 가지고, 앞 Step이 컨텍스트에 저장한 데이터를 뒤 Step이 읽어 가는 방식으로 데이터를 공유한다.

---

## Step 간 데이터 공유: `@JobScope` 인메모리 홀더 ([Spring Batch @StepScope / @JobScope 정리](../../java/spring-batch/step-scope.md))

앞 Step이 수집한 데이터를 뒤 Step에서 사용해야 하는 경우가 있다. 스페이스 정보(`confluenceSpaceCollectStep`)와 페이지 ID 목록(`confluencePageIdCollectStep`)이 대표적이다.

처음에는 `JobExecutionContext`에 저장했다.

```java
// ❌ JobExecutionContext에 도메인 데이터 저장
jobExecution.getExecutionContext().put("pageIds", pageIds);
```

`JobExecutionContext`는 청크 커밋마다 `BATCH_JOB_EXECUTION_CONTEXT` 테이블에 직렬화된다. 수천 개의 페이지 ID를 매 커밋마다 DB에 읽고 쓰는 건 불필요한 부하다. `JobExecutionContext`는 재시작을 위한 커서 위치 같은 **경량 상태** 전용이다.

`@JobScope` 빈 `ConfluenceJobDataHolder`로 옮겼다.

```java
@Getter
@Component
@JobScope
public class ConfluenceJobDataHolder {
    private ConfluenceSpaceInfo space;
    private List<String> pageIds = new ArrayList<>();

    public @Nonnull ConfluenceSpaceInfo getSpace() {
        if (space == null) {
            throw new IllegalStateException("ConfluenceGetSpaceInfoStep이 실행되었는지 확인하세요");
        }
        return space;
    }
}
```

`@JobScope`는 내부적으로 `proxyMode = ScopedProxyMode.TARGET_CLASS`를 포함해서 싱글톤 빈에 안전하게 주입할 수 있다. 주입되는 것은 CGLIB 프록시이고, 실제 호출 시 현재 Job 스코프의 인스턴스로 위임된다.

**재시작 시 주의**: Job이 실패해서 재시작하면 새로운 `JobExecution`이 생성되고 `@JobScope` 빈도 새 인스턴스로 초기화된다. 상태를 채우는 Step들이 `COMPLETED` 처리된 채로 스킵되면 빈이 빈 상태로 남아서 NPE가 발생한다. `allowStartIfComplete(true)`를 설정해서 재시작 시에도 상태 로더 Step이 반드시 재실행되게 했다.

---

## 핵심 Step: 페이지/댓글 색인 파이프라인

색인 Step의 내부 구조가 가장 복잡하다. Spring Batch의 청크 지향 처리를 쓴다.

```
Reader → Processor → Writer
```

**Reader**: Confluence REST API를 페이지네이션하면서 페이지 목록을 가져온다. 한 번에 전부 가져오지 않고 설정된 페이지 사이즈만큼 씩 API를 호출한다.

**Processor**: 텍스트 변환 → 임베딩을 담당한다. 여기서 조금 복잡한 구성을 썼다.

**Writer**: 임베딩된 문서를 OpenSearch에 벌크로 색인한다.

### AsyncItemProcessor를 쓴 이유 ([Spring Batch AsyncItemProcessor 정리](../../java/spring-batch/async-item-processor.md))

임베딩 API 호출은 네트워크 I/O다. 페이지 하나를 처리할 때 임베딩 API 응답을 기다리는 시간이 대부분이다. 동기 방식이면 이 구조가 된다.

```
페이지1 처리 → [API 대기 200ms] → 페이지2 처리 → [API 대기 200ms] → ...
```

청크 사이즈가 10이면 하나의 청크를 처리하는 데 최소 2초가 걸린다. 스페이스에 페이지가 수천 개면 심각하게 느려진다.

`AsyncItemProcessor`로 감싸면 각 아이템을 스레드풀에서 병렬로 처리한다.

```
페이지1 → [스레드1: API 호출 중]
페이지2 → [스레드2: API 호출 중]  ← 동시에
페이지3 → [스레드3: API 호출 중]
...
```

실제 코드에서는 이렇게 설정했다.

```java
@Bean
public AsyncItemProcessor<ConfluencePageItem, EmbeddedConfluenceDocuments> confluenceAsyncProcessor(
    @Qualifier("parallelChunkExecutor") TaskExecutor taskExecutor,
    @Qualifier("confluenceCompositeProcessor") ItemProcessor<ConfluencePageItem, EmbeddedConfluenceDocuments> compositeProcessor
) {
    AsyncItemProcessor<ConfluencePageItem, EmbeddedConfluenceDocuments> asyncProcessor = new AsyncItemProcessor<>();
    asyncProcessor.setDelegate(compositeProcessor);    // 실제 처리를 위임
    asyncProcessor.setTaskExecutor(taskExecutor);      // 스레드풀 설정
    return asyncProcessor;
}
```

`AsyncItemProcessor`가 반환하는 값은 `Future<EmbeddedConfluenceDocuments>`다. Writer 단계에서 `AsyncItemWriter`가 `Future.get()`을 호출해서 결과를 모아 벌크 색인한다.

```java
@Bean
public AsyncItemWriter<EmbeddedConfluenceDocuments> confluenceAsyncWriter(...) {
    AsyncItemWriter<EmbeddedConfluenceDocuments> asyncWriter = new AsyncItemWriter<>();
    asyncWriter.setDelegate(confluenceDocumentWriter);  // 실제 OpenSearch 쓰기 위임
    return asyncWriter;
}
```

### CompositeItemProcessor로 처리 단계 체이닝

Processor는 `CompositeItemProcessor`로 체이닝한 4단계로 구성된다.

```java
compositeProcessor.setDelegates(List.of(
    changeFilter,        // 변경 감지
    enrichmentProcessor, // 데이터 보강
    bodyConvertProcessor,// ADF → Markdown
    embeddingProcessor   // Markdown → 임베딩
));
```

**ChangeFilterProcessor**: 매번 전체 문서를 임베딩하면 비용이 크다. OpenSearch에 색인된 문서의 `version` 필드와 Confluence API가 반환한 `version`을 비교해서, 변경이 없으면 `null`을 반환한다. Spring Batch는 Processor가 `null`을 반환하면 해당 아이템을 스킵한다. 덕분에 실제로 수정된 문서만 임베딩 API를 호출한다. 추가로, 이전 실행에서 반복적으로 실패한 문서는 실패 횟수 임계치를 초과하면 자동으로 건너뛴다.

**EnrichmentProcessor**: ChangeFilter를 통과한 문서에 필요한 데이터를 보강한다. 세 가지를 채운다.
- **첨부파일 목록**: 페이지 ID로 첨부파일 API를 커서 기반 페이지네이션하면서 전체 조회
- **작성자 이름**: `authorId`(계정 ID)를 Confluence 사용자 API로 `displayName`으로 변환
- **멘션된 사용자 이름**: ADF body에서 `mention` 노드의 `accountId`를 추출하고 `displayName`으로 변환해서 `referrerNames`로 저장

**BodyConvertProcessor**: ADF → Markdown 변환 (앞서 설명)

**EmbeddingProcessor**: Markdown 텍스트 + 첨부파일 내용을 임베딩 API에 넘겨 벡터 생성

체이닝하면 각 Processor가 단일 책임을 가진다. 나중에 처리 단계를 추가하거나 교체할 때 다른 코드를 건드리지 않아도 된다.

전체 Processor 구성을 그림으로 보면 이렇다.

```
Reader
  ↓ ConfluencePageItem
CompositeItemProcessor
  ├─ ChangeFilterProcessor    (version 비교 → 미변경 스킵)
  ├─ EnrichmentProcessor      (첨부파일·작성자·멘션 보강)
  ├─ BodyConvertProcessor     (ADF → Markdown)
  └─ EmbeddingProcessor       (Markdown + 첨부파일 → 임베딩)
  ↓ EmbeddedConfluenceDocuments (Future로 감싸짐)
AsyncItemProcessor (parallelChunkExecutor 스레드풀)
  ↓ Future<EmbeddedConfluenceDocuments>
AsyncItemWriter
  ↓ (Future.get() 호출 후)
ConfluenceDocumentWriter      (OpenSearch 벌크 색인)
```

---

## 스페이스마다 연결 정보가 다르다

Confluence를 여러 조직이 각자 다른 인스턴스로 쓰는 경우가 있다. baseUrl, 계정, API 토큰이 스페이스마다 다르다.

초기에는 클라이언트를 빈으로 등록해서 쓰다 보니 "하나의 빈에 하나의 연결 정보"밖에 못 담는 문제가 있었다. `ConfluenceApiService` 인터페이스와 `ConfluenceApiServiceFactory`를 도입해서 해결했다.

```java
// 잡 파라미터로 들어온 연결 정보를 Step 실행 컨텍스트에 저장
// → 각 Step 컴포넌트가 beforeStep()에서 읽어서 서비스 인스턴스 생성

public class ConfluencePageItemReader implements ItemReader<ConfluencePageItem>, StepExecutionListener {

    @Override
    public void beforeStep(StepExecution stepExecution) {
        ConfluenceConnectionInfo connectionInfo = SharedContextUtils.getConnectionInfo(stepExecution);
        this.confluenceApiService = confluenceApiServiceFactory.create(connectionInfo);
    }
}
```

잡 파라미터로 `baseUrl`, `username`, `apiToken`을 받아서 Step 컨텍스트에 넣고, 각 Step 컴포넌트가 `beforeStep()`에서 꺼내 쓰는 방식이다. 스페이스가 추가돼도 잡 파라미터만 바꾸면 된다.

---

## Atlas Doc Format → Markdown 변환

Confluence Cloud는 페이지 본문을 기본적으로 **Atlas Doc Format(ADF)** 으로 반환한다. JSON 기반의 트리 구조 포맷인데, 그냥 저장하면 RAG 검색에 쓸 수 없다. 임베딩 모델에는 구조화된 텍스트가 들어가야 하는데, Markdown으로 변환하면 문서의 계층 구조와 의미론적 정보를 보존할 수 있어서 검색 품질에 유리하다.

```json
// ADF 예시
{
  "type": "doc",
  "content": [
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "안녕하세요" }]
    }
  ]
}
```

`ConfluenceAtlasDocFormatConverter` 클래스가 ADF JSON을 Markdown으로 변환한다. 지원하는 변환 목록은 다음과 같다.

- **헤딩**: `# heading` (level 1~6)
- **텍스트 스타일**: 볼드(`**text**`), 이탤릭(`*text*`), 취소선(`~~text~~`), 인라인 코드(`` `code` ``)
- **링크**: `[text](url)`
- **리스트**: 불릿 리스트(`- item`, 중첩 지원 들여쓰기 2칸), 순서 리스트(`1. item`, 중첩 지원)
- **블록 요소**: 블록쿼트(`> text`), 코드 블록(` ```language\ncode\n``` ` 언어 명시)
- **패널**: blockquote 형식으로 변환되며, `> **INFO/NOTE/WARNING/TIP/ERROR**` 형태의 레이블 포함
- **테이블**: Markdown 표 형식 (`| col | col |`, `|---|---|`)
- **미디어/이미지**: `![alt](url)`
- **Expand/NestedExpand**: 제목을 `**bold**`로 표현하고 내용 펼쳐서 출력
- **인라인 카드**: `[url](url)`
- **멘션**: 표시 텍스트 유지
- **날짜**: `yyyy-MM-dd` 형식 (Asia/Seoul 기준)
- **Status**: `[STATUS_TEXT]`
- **이모지**: 텍스트/shortName
- **Extension 매크로**: 제목+URL 있으면 `[title](url)`, 없으면 스킵
- **수평선**: `---`

`BodyConverter` 인터페이스(`ConfluenceBodyConverter`)로 추상화되어 있어서 포맷별로 교체할 수 있다. `ConfluenceBodyConverterProvider`가 `ConfluenceBodyFormat` 파라미터 값(예: `atlas_doc_format`)을 기준으로 적절한 구현체를 선택한다. API 요청 시 `bodyFormat` 파라미터로 `atlas_doc_format`을 명시해야 ADF로 응답이 온다.

변환 후에는 `normalizeMarkdown()`으로 연속 3개 이상 줄바꿈을 2개로 정규화해서 과도한 공백을 제거한다.

---

## 첨부파일 처리

페이지에 첨부된 PDF, Word, PPT 같은 파일도 내용을 뽑아서 색인해야 한다. 파일을 직접 파싱하지 않고 사내 문서 파싱 서비스에 위임한다.

처음에는 파일을 전부 바이트 배열로 받아서 파싱 API에 넘겼는데, 큰 파일에서 OOM이 날 수 있다. 스트림으로 받아서 바로 넘기도록 바꿨다.

```java
InputStream inputStream = confluenceApiService.downloadAttachment(attachment);
DocumentParseResponse response = documentParseClient.parse(inputStream, fileName, fileSize);
```

한 가지 주의할 점: Confluence Cloud의 첨부파일 다운로드 URL이 S3 같은 외부 스토리지로 302 리다이렉트되는 경우가 있다. RestClient의 기본 설정은 리다이렉트를 자동 처리하지 않아서 수동으로 처리해야 했다.

**ZIP 파일**은 내부 엔트리를 순회하면서 각각 파싱·색인한다. ZIP 하나를 단일 문서로 색인하면 내용이 섞여서 검색 품질이 떨어진다.

**포맷 검증**은 MIME 타입만 보다가 확장자 + MIME 타입 이중 검증으로 강화했다. MIME 타입을 `application/octet-stream`으로 올리는 경우가 있어서 확장자 없이는 걸러내지 못했다.

---

## 삭제 동기화

배치가 문서를 색인만 하면 Confluence에서 삭제된 페이지가 OpenSearch에 계속 남아서 검색 결과에 노이즈가 생긴다.

다행히 Confluence API는 삭제 상태(`DELETED`, `TRASHED`)의 문서를 직접 조회하는 `status` 파라미터를 제공한다. 별도로 ID 집합을 비교할 필요 없이, API에서 삭제된 문서만 바로 가져올 수 있다.

```
Confluence API → status=DELETED,TRASHED 조회 → 삭제 대상 목록 반환
→ OpenSearch에서 해당 문서 제거
```

삭제 Step도 Reader → Writer 패턴으로 구현했다. 페이지·댓글은 색인 시에 쓰던 `ConfluencePageReader`, `ConfluenceCommentItemReader`를 `status=DELETED,TRASHED`로 재사용한다. 따로 Reader를 만들지 않고 status 파라미터만 바꿔서 주입하면 됐다.

```java
// 삭제된 페이지 조회: 기존 Reader에 DELETED, TRASHED status만 전달
new ConfluencePageReader(..., List.of(ConfluencePageStatus.DELETED, ConfluencePageStatus.TRASHED), ...)
```

첨부파일은 페이지 단위로 조회해야 하는 API 구조 때문에 별도 `ConfluenceDeletedAttachmentItemReader`를 만들었다. 앞서 `confluencePageIdCollectStep`에서 수집한 페이지 ID 목록을 순회하면서, 각 페이지의 `TRASHED` 상태 첨부파일을 커서 기반으로 페이지네이션해서 읽는다.

Writer는 Reader에서 받은 삭제 대상 문서 ID로 OpenSearch 벌크 삭제를 수행하고, 원본 컨텐츠(FullContent)도 함께 정리한다. 페이지·댓글·첨부파일 각각 별도 Step으로 분리했다.

---

## 스페이스별 다른 메타데이터 포맷: 전략 패턴

특정 스페이스는 색인 메타데이터 스키마가 달랐다. 기존 색인은 `metadata.title`을 쓰는데, 이 스페이스는 `metadata.subject`를 써야 했다. `creator_id`, `extra_data` 같은 필드도 불필요했다.

처음에는 EmbeddingProcessor 안에 if-else 분기를 넣으려 했는데, 스페이스가 늘어날수록 분기도 늘어날 게 뻔해 보였다. **전략 패턴**으로 메타데이터 빌드 로직을 인터페이스로 추상화했다.

```java
public interface ConfluenceDocumentMetadataProvider {
    DocumentMetadata buildPageMetadata(ConfluencePageItem page);
    DocumentMetadata buildCommentMetadata(ConfluenceCommentItem comment, String pageTitle, ConfluenceSpaceInfo space);
    DocumentMetadata buildPageAttachmentMetadata(ConfluencePageItem page, ConfluenceAttachment attachment, String fileName, long fileSize, @Nullable String zipEntryPath);
    DocumentMetadata buildCommentAttachmentMetadata(ConfluenceCommentItem comment, String pageTitle, ConfluenceSpaceInfo space, ConfluenceAttachment attachment, String fileName, Long fileSize, @Nullable String zipEntryPath);
}
```

- `DefaultConfluenceDocumentMetadataProvider`: 기존 포맷 (`title`, `creator_id`, `extra_data` 포함)
- `NewSpaceConfluenceDocumentMetadataProvider`: 신규 포맷 (`subject` 사용, `extra_data` 없음)

EmbeddingProcessor는 인터페이스에만 의존한다.

```java
public class ConfluencePageItemEmbeddingProcessor implements ItemProcessor<ConfluencePageItem, EmbeddedConfluenceDocuments> {

    private final ConfluenceDocumentMetadataProvider metadataProvider;  // 주입

    @Override
    public EmbeddedConfluenceDocuments process(ConfluencePageItem item) {
        DocumentMetadata metadata = metadataProvider.buildPageMetadata(item);  // 구현체에 위임
        // ...
    }
}
```

각 배치 잡 설정 클래스에서 `@Qualifier`로 원하는 구현체를 주입하면 된다. EmbeddingProcessor 코드를 건드릴 필요가 없다.

---

## @StepScope 빈 충돌 문제 ([Spring Batch @StepScope 정리](../../java/spring-batch/step-scope.md))

두 배치 잡이 같은 타입의 `@StepScope` 빈을 각자 등록하면서 Spring이 어느 것을 주입해야 할지 몰라 `NoUniqueBeanDefinitionException`이 발생했다.

```
expected single matching bean but found 2:
confluencePageItemEmbeddingProcessor,
newSpacePageItemEmbeddingProcessor
```

해결 방법: 공용으로 쓰는 빈은 `@Component @StepScope`로 전역 등록하고, 잡 전용 빈은 각 Config 클래스에서만 정의한다. 주입할 때는 `@Qualifier`로 명시한다.

```java
// Config 클래스에서
@Bean
@StepScope
public ConfluencePageItemEmbeddingProcessor confluencePageItemEmbeddingProcessor(
    @Qualifier("defaultMetadataProvider") ConfluenceDocumentMetadataProvider metadataProvider,
    ...
) {
    return new ConfluencePageItemEmbeddingProcessor(..., metadataProvider);
}
```

테스트 코드에서도 `@Autowired`에 `@Qualifier`를 맞춰줘야 한다는 걸 처음엔 몰랐다.

```java
@Autowired
@Qualifier("confluencePageItemEmbeddingProcessor")  // 이걸 빠뜨리면 테스트 실패
private ConfluencePageItemEmbeddingProcessor processor;
```

반대로, **두 잡에서 완전히 동일하게 쓰는 컴포넌트**라면 각 Config에서 `@Bean @StepScope`로 따로 정의하는 대신 `@Component @StepScope`로 전역 등록하면 중복이 없어진다. `ConfluencePageIdCollectTasklet`, `ConfluencePageItemWriter`가 이 패턴으로 통합됐다.

```java
// 잡 Config에서 @Bean으로 각각 정의하던 것을
@Component
@StepScope
public class ConfluencePageItemWriter extends AbstractConfluenceStepComponent implements ItemWriter<EmbeddedConfluenceDocuments> {
    // 어느 잡에서든 동일한 빈을 주입받아 쓴다
}
```

---

## 테스트 전략

Confluence 파이프라인 코드와 함께 테스트 기반도 만들었다.

**`@BatchComponentTest`**: 외부 API(Confluence, 문서 파싱, 임베딩)만 모킹하고 Spring 컴포넌트는 실제 빈을 주입받는 컴포넌트 테스트 애노테이션이다.

```java
@SpringBootTest
@SpringBatchTest
@ActiveProfiles("test")
@Import({TestOpenSearchConfig.class, TestExternalApiConfig.class, FakeConfluenceClientConfig.class})
public @interface BatchComponentTest {}
```

순수 단위 테스트로 모든 걸 테스트하면 외부 시스템과의 실제 통합 지점을 놓치기 쉽다. Spring 컨텍스트에서 실제 빈을 엮어서 테스트하면 빈 설정 오류, Qualifier 충돌 같은 문제를 빌드 타임에 잡을 수 있다. 외부 HTTP 호출만 `MockRestServiceServer`로 가로채서 제어한다.

---

## 마무리

이 배치를 만들면서 배운 게 꽤 많다.

**임베딩처럼 I/O 바운드 작업은 무조건 비동기로**. 동기 처리는 API 대기 시간이 그대로 처리 시간이 된다. `AsyncItemProcessor` + `AsyncItemWriter` 조합이 Spring Batch에서 이걸 깔끔하게 해결한다.

**Step 분리는 실패 격리다**. 댓글 Step이 실패해도 페이지 Step 결과는 살아있다. 재시작하면 댓글 Step부터 이어서 돌 수 있다. 하나의 거대한 Step 안에 다 넣으면 중간 실패 시 처음부터 다시 해야 한다.

**전략 패턴은 기존 코드를 건드리지 않고 동작을 교체한다**. 스페이스마다 메타데이터 포맷이 달라질 때, EmbeddingProcessor를 건드리지 않고 Provider 구현체만 갈아끼웠다. 처음부터 인터페이스로 설계했다면 더 빨랐을 것 같다.

**Confluence Cloud는 On-Premise와 다르다**. API 응답 포맷, URL 구조, 인증 방식이 다르다. 문서를 너무 믿지 말고 실제 응답을 직접 찍어보는 게 빠르다.

---

## 사용 기술

- **언어/프레임워크**: Java 21, Spring Boot 3, Spring Batch
- **검색엔진**: OpenSearch (벡터 색인)
- **외부 API**: Confluence Cloud REST API, 문서 파싱 서비스, 임베딩 서비스
- **테스트**: JUnit 5, MockRestServiceServer, spring-batch-test, Testcontainers
- **CI/CD**: GitHub Actions
- **빌드**: Gradle
