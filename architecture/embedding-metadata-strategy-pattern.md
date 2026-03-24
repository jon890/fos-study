# 임베딩 메타데이터 전략 패턴: Blocklist에서 Allowlist로

RAG 파이프라인에서 여러 소스의 문서를 벡터 색인할 때, 임베딩 API에 전달할 메타데이터를 구성하는 방식이 코드 복잡도에 직접 영향을 미친다는 걸 깨달았다. blocklist 방식에서 allowlist 방식으로 전환하면서 전략 패턴을 실제로 적용한 경험을 정리했다.

## 문제 상황: Blocklist의 한계

### 초기 구조

RAG 파이프라인은 Confluence, 사내 협업 도구의 Task/Wiki/Drive 등 다양한 소스에서 문서를 수집해 OpenSearch에 벡터 색인한다. 임베딩 API에 전달할 때는 content 외에 문맥을 보완하는 메타데이터를 함께 보낸다.

초기 구현은 `EmbeddingService`에서 문서의 전체 메타데이터를 복사한 뒤, 불필요한 필드를 하나씩 제거(blocklist)하는 방식이었다.

```java
// ❌ before: 하나의 메서드에 14개 remove 호출
DocumentMetadata metadata = document.cloneMetadata();
metadata.remove("id");
metadata.remove("url");
metadata.remove("employee_id");
metadata.removeExtraData("project_id");
metadata.removeExtraData("task_id");
metadata.removeExtraData("wiki_id");
metadata.removeExtraData("wiki_page_id");
metadata.removeExtraData("drive_id");
metadata.removeExtraData("member_id");
metadata.removeExtraData("hash");
metadata.removeExtraData("file_name");
metadata.removeExtraData("file_size");
metadata.removeExtraData("zip_entry_path");
metadata.removeExtraData("assignees");
metadata.removeExtraData("referrers");

// 날짜 포맷 변환도 여기서 직접 처리
Long createdTime = document.getCreatedTime();
if (createdTime != null) {
    metadata.put("created_time", FormatUtils.formatKoreanDateTime(createdTime));
}
// ... 이하 생략
```

### 왜 문제였나?

처음에는 이 방식이 충분했다. 하지만 시간이 지나면서 문제가 드러났다.

**1. 새로운 DocumentType이 추가될 때마다 분기가 늘어난다**

```java
if (documentType == DocumentType.TASK) {
    // 14개 remove + 추가 로직
} else if (documentType == DocumentType.WIKI) {
    // 다른 필드들의 remove + 다른 추가 로직
} else if (documentType == DocumentType.CONFLUENCE_PAGE) {
    // 또 다른 remove 조합
}
```

코드는 점점 길어지고 복잡해진다.

**2. 어떤 필드가 포함되는지 파악하기 어렵다**

"임베딩에 실제로 어떤 필드들이 포함되나?"에 답하려면 remove 목록을 역산해야 했다.

**3. 불필요한 메서드가 생겨난다**

이 패턴을 위해서만 존재하는 메서드들이 누적됐다.

- `Document.cloneMetadata()` — 메타데이터 전체 복사
- `getMetadataValue(String)` — 단순 조회
- `putMetadata(String)` — 단순 삽입

**4. OCP 원칙 위반**

새로운 DocumentType이 추가될 때마다 `EmbeddingService`를 수정해야 했다.

---

## 해결: 전략 패턴으로 Allowlist 방식 전환

### 인터페이스 정의

핵심 아이디어는 단순했다. **"제거할 필드를 관리하지 말고, 포함할 필드를 명시적으로 관리하자"**

```java
public interface EmbeddingMetadataProvider {
    // 이 구현체가 담당하는 DocumentType 목록
    Set<DocumentType> getSupportedDocumentTypes();

    // 임베딩 요청에 포함할 메타데이터 맵을 구성하여 반환
    Map<String, Object> provide(Document document);
}
```

각 구현체가 자신이 담당하는 DocumentType을 선언하고, 필요한 필드만 명시적으로 담는다.

### 클래스 계층 구조

공통 유틸(`putIfNotNull`, `putFormattedDatetime`)을 `AbstractEmbeddingMetadataProvider`에 모았다. 그 위에 소스 시스템별로 추상 클래스를 뒀다.

```
EmbeddingMetadataProvider (interface)
  └─ AbstractEmbeddingMetadataProvider
       ├─ AbstractCollabToolEmbeddingMetadataProvider  ← 협업 도구 공통 필드
       │    ├─ TaskEmbeddingMetadataProvider           ← Task/Comment/File (+ due_date, closed)
       │    ├─ WikiEmbeddingMetadataProvider           ← Wiki/Comment/File
       │    └─ DriveFileEmbeddingMetadataProvider      ← Drive File (+ version, revision)
       └─ AbstractConfluenceEmbeddingMetadataProvider ← Confluence 공통 필드
            └─ ConfluenceEmbeddingMetadataProvider    ← Page/Comment/Attachment
```

**AbstractCollabToolEmbeddingMetadataProvider** — 협업 도구 공통 필드:

```java
protected Map<String, Object> createResultWithCommonFields(Document document) {
    DocumentMetadata metadata = document.getMetadata();
    Map<String, Object> result = new LinkedHashMap<>();
    putIfNotNull(result, DocumentMetadataType.TYPE.getValue(),         metadata.get(DocumentMetadataType.TYPE, String.class));
    putIfNotNull(result, DocumentMetadataType.TITLE.getValue(),        metadata.get(DocumentMetadataType.TITLE, String.class));
    putFormattedDatetime(result, DocumentMetadataType.CREATE_TIME.getValue(),   document.getCreatedTime());
    putFormattedDatetime(result, DocumentMetadataType.MODIFIED_TIME.getValue(), document.getModifiedTime());
    putIfNotNull(result, DocumentMetadataType.PROJECT_NAME.getValue(), metadata.get(DocumentMetadataType.PROJECT_NAME, String.class));
    putIfNotNull(result, DocumentMetadataType.MEMBER_NAME.getValue(),  metadata.get(DocumentMetadataType.MEMBER_NAME, String.class));
    return result;
}
```

**AbstractConfluenceEmbeddingMetadataProvider** — Confluence 특유의 title/subject 폴백 처리:

```java
protected Map<String, Object> createResultWithCommonFields(Document document) {
    DocumentMetadata metadata = document.getMetadata();
    Map<String, Object> result = new LinkedHashMap<>();
    putIfNotNull(result, DocumentMetadataType.TYPE.getValue(), metadata.get(DocumentMetadataType.TYPE, String.class));
    // 특정 스페이스는 title 대신 subject를 사용하므로 폴백 처리
    String title = metadata.get(DocumentMetadataType.TITLE, String.class);
    if (title == null) {
        title = metadata.get(DocumentMetadataType.SUBJECT, String.class);
    }
    putIfNotNull(result, DocumentMetadataType.TITLE.getValue(), title);
    putFormattedDatetime(result, DocumentMetadataType.CREATE_TIME.getValue(),   document.getCreatedTime());
    putFormattedDatetime(result, DocumentMetadataType.MODIFIED_TIME.getValue(), document.getModifiedTime());
    putIfNotNull(result, DocumentMetadataType.PROJECT_NAME.getValue(), metadata.get(DocumentMetadataType.PROJECT_NAME, String.class));
    putIfNotNull(result, DocumentMetadataType.MEMBER_NAME.getValue(),  metadata.get(DocumentMetadataType.MEMBER_NAME, String.class));
    return result;
}
```

### 구체적 구현체: Task

Task는 공통 필드 외에 마감일(`due_date`)과 완료 여부(`closed`)가 추가된다.

```java
@Component
public class TaskEmbeddingMetadataProvider extends AbstractCollabToolEmbeddingMetadataProvider {

    @Override
    public Set<DocumentType> getSupportedDocumentTypes() {
        return Set.of(DocumentType.TASK, DocumentType.TASK_COMMENT, DocumentType.TASK_FILE);
    }

    @Override
    public Map<String, Object> provide(Document document) {
        DocumentMetadata metadata = document.getMetadata();
        Map<String, Object> result = createResultWithCommonFields(document);
        putFormattedDatetime(result, "due_date", metadata.getExtraData("due_date", Long.class));
        putIfNotNull(result, "closed", metadata.getExtraData("closed", Boolean.class));
        return result;
    }
}
```

### 구체적 구현체: Wiki

Wiki는 공통 필드만 필요해서 구현이 한 줄이다.

```java
@Component
public class WikiEmbeddingMetadataProvider extends AbstractCollabToolEmbeddingMetadataProvider {

    @Override
    public Set<DocumentType> getSupportedDocumentTypes() {
        return Set.of(DocumentType.WIKI, DocumentType.WIKI_COMMENT, DocumentType.WIKI_FILE);
    }

    @Override
    public Map<String, Object> provide(Document document) {
        return createResultWithCommonFields(document);
    }
}
```

한 줄짜리 구현체가 가능해진 게 이 패턴의 장점이다. 복잡한 로직은 추상 클래스에 숨겨지고, 구현체는 "내가 무엇을 포함하는가"만 표현한다.

---

## Spring DI: 구현체 자동 등록

Spring이 `List<EmbeddingMetadataProvider>`로 모든 `@Component` 구현체를 자동 주입한다. Config에서 `DocumentType → Provider` 맵으로 빌드한다.

```java
private Map<DocumentType, EmbeddingMetadataProvider> buildMetadataProviderMap() {
    return embeddingMetadataProviders.stream()
        .flatMap(provider -> provider.getSupportedDocumentTypes().stream()
                                     .map(type -> Map.entry(type, provider)))
        .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
}
```

`EmbeddingService`는 DocumentType으로 provider를 조회해서 위임만 하면 된다.

```java
// ✅ after: EmbeddingService는 위임만
DocumentType documentType = DocumentType.from(
    document.getMetadata().get(DocumentMetadataType.TYPE, String.class));
EmbeddingMetadataProvider metadataProvider = metadataProviders.get(documentType);

if (metadataProvider != null) {
    contentMap.put("metadata", metadataProvider.provide(document));
    contentMap.put("content", document.getContent());
    text = objectMapper.writeValueAsString(contentMap);
}
```

before의 14개 remove 블록과 if-else 분기가 모두 사라졌다.

---

## 적용 후 달라진 것

**가독성**: "어떤 필드가 임베딩에 포함되나?"를 구현체를 보면 바로 알 수 있다. remove 목록을 역산할 필요 없음.

**OCP 준수**: 새 DocumentType을 추가할 때 `EmbeddingService` 코드를 건드리지 않는다. `@Component` 구현체 하나만 추가하면 자동으로 반영된다.

**불필요한 코드 제거**: `Document.cloneMetadata()`, `getMetadataValue(String)`, `putMetadata(String)` — 이 패턴을 위해서만 존재하던 메서드들이 모두 삭제됐다.

**테스트 용이성**: 구현체별로 독립적으로 테스트할 수 있다. 각 provider의 책임이 명확하므로 단위 테스트도 간결해진다.

---

## 마무리

blocklist 방식의 근본 문제는 마음속 모델(mental model)과 코드가 맞지 않았다는 것이다. 생각하는 건 "포함할 필드를 결정한다"인데, 코드는 "제거할 필드를 나열한다"고 표현했다.

전략 패턴으로 바꾸면서 코드가 의도를 정확하게 표현하게 됐다. 각 구현체가 "나는 이런 필드들을 포함한다"고 명시적으로 선언한다. Spring의 자동 등록과 결합하면 확장성도 덤으로 얻는다. 새 소스가 추가되더라도 기존 코드는 건드리지 않는다.
