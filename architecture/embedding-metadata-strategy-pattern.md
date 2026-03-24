# 임베딩 메타데이터 전략 패턴: Blocklist에서 Allowlist로

RAG 파이프라인에서 여러 소스의 문서를 벡터 색인할 때, 임베딩 API에 전달할 메타데이터를 구성하는 방식이 코드 복잡도에 직접 영향을 미친다는 것을 깨달았다. blocklist 방식에서 allowlist 방식으로 전환하면서 전략 패턴을 실제로 적용한 경험을 공유한다.

## 문제 상황: Blocklist의 한계

### 초기 구조

우리의 RAG 파이프라인은 Confluence, Dooray Task/Wiki/Drive 등 다양한 소스에서 문서를 수집해 OpenSearch에 벡터 색인한다. 임베딩 API에 전달할 때는 문서의 내용(content) 외에 문맥을 보완하는 메타데이터를 함께 보낸다.

초기 구현은 매우 간단했다. `EmbeddingService`에서 문서의 전체 메타데이터를 복사한 뒤, 불필요한 필드들을 하나씩 제거(blocklist)하는 방식이었다.

```java
// ❌ before: 하나의 메서드에 14개의 remove 호출
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

처음에는 이 방식이 충분했다. 하지만 시간이 지나면서 몇 가지 문제가 드러났다.

**1. 새로운 DocumentType이 추가될 때마다 분기가 늘어난다**

```java
if (document.getType() == DocumentType.DOORAY_TASK) {
    // 14개의 remove + 추가 로직
} else if (document.getType() == DocumentType.DOORAY_WIKI) {
    // 다른 필드들의 remove + 다른 추가 로직
} else if (document.getType() == DocumentType.CONFLUENCE_PAGE) {
    // 또 다른 remove 조합
}
```

코드는 점점 길어지고 복잡해졌다.

**2. 어떤 필드가 포함되는지 파악하기 어렵다**

"임베딩에 실제로 어떤 필드들이 포함되나?"라는 질문에 답하려면 remove 목록을 역산해야 했다. 이는 매우 비효율적이었다.

**3. 불필요한 메서드가 생겨난다**

이 패턴을 위해서만 존재하는 메서드들이 누적되었다:

- `Document.cloneMetadata()` — 메타데이터 전체 복사
- `getMetadataValue(String)` — 단순 조회
- `putMetadata(String)` — 단순 삽입

이들은 실제로 메타데이터 구성 로직과 강하게 결합되어 있었다.

**4. OCP 원칙 위반**

새로운 DocumentType이 추가될 때마다 `EmbeddingService`를 수정해야 했다. 이는 확장에는 열려있지만 수정에는 닫혀있어야 한다는 OCP 원칙에 위배되었다.

## 해결: 전략 패턴으로 Allowlist 방식 전환

### 설계 철학

핵심 아이디어는 간단했다: **"제거할 필드들을 관리하지 말고, 포함할 필드들을 명시적으로 관리하자"**

이를 위해 각 DocumentType별로 "어떤 필드를 임베딩에 포함할 것인가"를 선언하는 책임을 분리했다. 이것이 바로 전략 패턴이다.

### 인터페이스 정의

```java
public interface EmbeddingMetadataProvider {
    // 이 구현체가 담당하는 DocumentType 목록
    Set<DocumentType> getSupportedDocumentTypes();

    // 임베딩 요청에 포함할 메타데이터 맵을 구성하여 반환
    Map<String, Object> provide(Document document);
}
```

각 구현체는:

1. `getSupportedDocumentTypes()`로 자신이 담당하는 DocumentType들을 선언한다.
2. `provide()`에서 필요한 필드만 명시적으로(allowlist) 담는다.

이 설계로 "어떤 필드가 임베딩에 포함되나?"라는 질문에 바로 답할 수 있게 되었다.

### 클래스 계층 구조

공통 유틸리티는 `AbstractEmbeddingMetadataProvider`에 모았다. 이곳에서 null 체크, 날짜 포맷팅 같은 반복되는 로직을 처리한다.

그 위에 소스 시스템별로 두 개의 추상 클래스를 뒀다:

```
EmbeddingMetadataProvider (interface)
  └─ AbstractEmbeddingMetadataProvider
       ├─ AbstractDoorayEmbeddingMetadataProvider
       │    ├─ DoorayTaskEmbeddingMetadataProvider
       │    ├─ DoorayWikiEmbeddingMetadataProvider
       │    └─ DoorayDriveFileEmbeddingMetadataProvider
       └─ AbstractConfluenceEmbeddingMetadataProvider
            └─ ConfluenceEmbeddingMetadataProvider
```

**AbstractDoorayEmbeddingMetadataProvider** 는 Dooray 시스템의 공통 필드들을 처리한다:

```java
public abstract class AbstractDoorayEmbeddingMetadataProvider extends AbstractEmbeddingMetadataProvider {

    protected Map<String, Object> createResultWithCommonFields(Document document) {
        DocumentMetadata metadata = document.getMetadata();
        Map<String, Object> result = new HashMap<>();

        // Dooray 공통 필드: type, title, 생성 시간, 프로젝트, 멤버
        putIfNotNull(result, "type", metadata.get(DocumentMetadataType.TYPE, String.class));
        putIfNotNull(result, "title", metadata.get(DocumentMetadataType.TITLE, String.class));
        putFormattedDatetime(result, "created_at", metadata.get(DocumentMetadataType.CREATED_TIME, Long.class));
        putIfNotNull(result, "project_id", metadata.getExtraData("project_id", String.class));
        putIfNotNull(result, "member_id", metadata.getExtraData("member_id", String.class));

        return result;
    }
}
```

**AbstractConfluenceEmbeddingMetadataProvider** 는 Confluence 고유의 로직을 처리한다:

```java
public abstract class AbstractConfluenceEmbeddingMetadataProvider extends AbstractEmbeddingMetadataProvider {

    protected Map<String, Object> createResultWithCommonFields(Document document) {
        DocumentMetadata metadata = document.getMetadata();
        Map<String, Object> result = new HashMap<>();

        // Confluence 공통 필드
        putIfNotNull(result, "type", metadata.get(DocumentMetadataType.TYPE, String.class));

        // title이 없으면 subject로 대체
        String title = metadata.get(DocumentMetadataType.TITLE, String.class);
        if (title == null) {
            title = metadata.get(DocumentMetadataType.SUBJECT, String.class);
        }
        putIfNotNull(result, "title", title);

        putFormattedDatetime(result, "created_at", metadata.get(DocumentMetadataType.CREATED_TIME, Long.class));
        putIfNotNull(result, "space_key", metadata.getExtraData("space_key", String.class));

        return result;
    }
}
```

### 구체적 구현체: Dooray Task

```java
@Component
public class DoorayTaskEmbeddingMetadataProvider extends AbstractDoorayEmbeddingMetadataProvider {

    @Override
    public Set<DocumentType> getSupportedDocumentTypes() {
        return Set.of(
            DocumentType.DOORAY_TASK,
            DocumentType.DOORAY_TASK_COMMENT,
            DocumentType.DOORAY_TASK_FILE
        );
    }

    @Override
    public Map<String, Object> provide(Document document) {
        DocumentMetadata metadata = document.getMetadata();

        // 공통 필드부터 시작
        Map<String, Object> result = createResultWithCommonFields(document);

        // Task 전용 필드 추가
        putFormattedDatetime(result, "due_date", metadata.getExtraData("due_date", Long.class));
        putIfNotNull(result, "closed", metadata.getExtraData("closed", Boolean.class));

        return result;
    }
}
```

### 구체적 구현체: Dooray Wiki

흥미롭게도, Wiki는 공통 필드만 필요해서 구현체가 매우 간단하다:

```java
@Component
public class DoorayWikiEmbeddingMetadataProvider extends AbstractDoorayEmbeddingMetadataProvider {

    @Override
    public Set<DocumentType> getSupportedDocumentTypes() {
        return Set.of(
            DocumentType.DOORAY_WIKI,
            DocumentType.DOORAY_WIKI_COMMENT,
            DocumentType.DOORAY_WIKI_FILE
        );
    }

    @Override
    public Map<String, Object> provide(Document document) {
        return createResultWithCommonFields(document);
    }
}
```

한 줄짜리 구현체가 가능해진 것이 이 패턴의 아름다움이다. 복잡한 로직은 추상 클래스에 숨겨져 있고, 구현체는 "내가 무엇을 포함하는가"만 명확하게 표현한다.

## Spring DI: 구현체의 자동 등록과 조회

Spring이 우리의 친구다. `List<EmbeddingMetadataProvider>`로 모든 구현체를 자동으로 주입받을 수 있다.

`EmbeddingClientConfig`에서 이들을 수집해 `DocumentType → Provider` 맵으로 빌드한다:

```java
@Configuration
public class EmbeddingClientConfig {

    private final List<EmbeddingMetadataProvider> embeddingMetadataProviders;
    private final Map<DocumentType, EmbeddingMetadataProvider> metadataProviders;

    public EmbeddingClientConfig(List<EmbeddingMetadataProvider> embeddingMetadataProviders) {
        this.embeddingMetadataProviders = embeddingMetadataProviders;
        this.metadataProviders = buildMetadataProviderMap();
    }

    private Map<DocumentType, EmbeddingMetadataProvider> buildMetadataProviderMap() {
        return embeddingMetadataProviders.stream()
            .flatMap(provider -> provider.getSupportedDocumentTypes().stream()
                                         .map(type -> Map.entry(type, provider)))
            .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
    }

    @Bean
    public Map<DocumentType, EmbeddingMetadataProvider> metadataProviders() {
        return metadataProviders;
    }
}
```

핵심은:

1. 모든 `@Component` 구현체들이 자동으로 `List<EmbeddingMetadataProvider>`에 들어온다.
2. `flatMap`으로 각 구현체가 담당하는 DocumentType들을 펼친다.
3. 최종적으로 DocumentType별로 provider를 빠르게 조회할 수 있는 맵이 만들어진다.

이제 `EmbeddingService`는 위임만 하면 된다:

```java
@Service
public class EmbeddingService {

    private final Map<DocumentType, EmbeddingMetadataProvider> metadataProviders;
    // ... 다른 의존성들

    public String getEmbeddingText(Document document) throws JsonProcessingException {
        DocumentType documentType = DocumentType.from(
            document.getMetadata().get(DocumentMetadataType.TYPE, String.class)
        );

        EmbeddingMetadataProvider metadataProvider = metadataProviders.get(documentType);

        if (metadataProvider != null) {
            Map<String, Object> contentMap = new HashMap<>();
            contentMap.put("metadata", metadataProvider.provide(document));
            contentMap.put("content", document.getContent());
            return objectMapper.writeValueAsString(contentMap);
        }

        // provider가 없으면 기본 처리
        return document.getContent();
    }
}
```

✅ **before의 14개 remove 블록과 if-else 분기가 모두 사라졌다.**

## 적용 후 달라진 것

### 1. 가독성 향상

"임베딩에 어떤 필드가 포함되나?"라는 질문에 더 이상 remove 목록을 역산할 필요가 없다. 각 구현체를 보면 명확하게 알 수 있다.

```java
// DoorayTaskEmbeddingMetadataProvider를 열어보면
// type, title, created_at, project_id, member_id, due_date, closed 이 포함됨을 바로 알 수 있다.
```

### 2. OCP 원칙 준수

새로운 DocumentType을 추가할 때 `EmbeddingService`를 수정할 필요가 없다. `@Component` 구현체 하나만 추가하면 자동으로 반영된다.

예를 들어, "NAVER_CAFE_POST"가 새로 추가된다면:

```java
@Component
public class NaverCafePostEmbeddingMetadataProvider extends AbstractEmbeddingMetadataProvider {
    @Override
    public Set<DocumentType> getSupportedDocumentTypes() {
        return Set.of(DocumentType.NAVER_CAFE_POST);
    }

    @Override
    public Map<String, Object> provide(Document document) {
        // Naver 카페 전용 메타데이터 구성
    }
}
```

이 클래스 하나만 추가하면 끝이다. Spring이 자동으로 주입하고, 빌더가 맵에 추가한다.

### 3. 불필요한 코드 제거

패턴을 위해서만 존재하던 메서드들이 모두 삭제되었다:

- `Document.cloneMetadata()` ✗
- `getMetadataValue(String)` ✗
- `putMetadata(String)` ✗

Document 클래스가 간결해지고, 관심사 분리가 명확해졌다.

### 4. 테스트 용이성

구현체별로 독립적으로 테스트할 수 있다:

```java
@Test
public void doorayTaskProvider_shouldIncludeDueDate() {
    // arrange
    Document task = createDoorayTaskDocument();
    provider = new DoorayTaskEmbeddingMetadataProvider();

    // act
    Map<String, Object> metadata = provider.provide(task);

    // assert
    assertThat(metadata).containsKey("due_date");
    assertThat(metadata).containsKey("closed");
}
```

각 provider의 책임이 명확하므로, 단위 테스트도 간결해진다.

### 5. 유지보수 비용 감소

기존에는 메타데이터 구성 로직이 `EmbeddingService` 한 곳에 모여 있었다. 지금은:

- 공통 유틸 → `AbstractEmbeddingMetadataProvider`
- 시스템별 공통 로직 → `AbstractDooray...`, `AbstractConfluence...`
- 타입별 로직 → 각 구현체

이렇게 계층화되어 있으므로, 특정 타입의 로직을 수정하려면 해당 구현체만 열면 된다. 다른 타입에 영향을 주지 않는다.

## 마무리

이 리팩터링은 "좋은 설계"가 얼마나 중요한지 보여주는 사례다.

**Blocklist 방식의 근본 문제는**, 마음속 모델(mental model)과 코드가 맞지 않았다는 것이다. 우리가 생각하는 것은 "임베딩에 포함할 필드를 결정한다"인데, 코드는 "제거할 필드를 나열한다"고 표현했다.

**전략 패턴으로 전환하면서**, 코드가 우리의 의도를 정확하게 표현하게 되었다. 각 구현체가 "나는 이런 필드들을 포함한다"고 명시적으로 선언한다. 이것이 좋은 코드다.

더 나아가 Spring의 자동 등록 메커니즘과 함께 사용하면, **확장성도 함께 얻을 수 있다**. 새로운 source가 추가되어도, 기존 코드는 건드리지 않는다.

실무에서는 이런 작은 설계 개선들이 모여서 유지보수하기 좋은 시스템을 만든다. 꼭 대규모 아키텍처 변경만이 아니어도, 한 부분의 책임을 명확히 하는 것만으로도 코드는 훨씬 나아진다.
