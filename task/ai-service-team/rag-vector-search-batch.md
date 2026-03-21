# RAG 서비스를 위한 Confluence 색인 배치 파이프라인 개발

> Spring Batch 기반으로 사내 Wiki 시스템(Confluence Cloud)의 페이지, 댓글, 첨부파일을 OpenSearch에 벡터 임베딩하여 색인하는 배치 파이프라인을 처음부터 설계하고 구현했다.

## 배경

사내 AI Playground 서비스에 RAG 기능을 붙이기 위해 Confluence 문서를 벡터 DB에 색인해야 했다. 기존 배치 애플리케이션(Spring Boot 3 + Spring Batch)에 Confluence 소스를 새로 연동하는 작업으로, 파이프라인 설계부터 운영까지 전담했다.

초기엔 단순히 페이지 본문만 색인하는 것부터 시작했지만, 이후 댓글·첨부파일 처리, 삭제 동기화, 다중 스페이스 지원까지 점진적으로 확장했다.

---

## 주요 기여

### 1. Confluence 색인 파이프라인 설계 및 구현

#### ConfluenceApiService 추상화

처음에는 Confluence REST 클라이언트를 직접 주입해서 사용했는데, 스페이스마다 연결 정보(baseUrl, API 토큰)가 달라서 단일 빈으로 관리할 수가 없었다. `ConfluenceApiService` 인터페이스를 도입하고 `ConfluenceApiServiceFactory`에서 Step 실행 컨텍스트의 연결 정보를 읽어 인스턴스를 생성하는 방식으로 바꿨다.

```java
// Step 실행 컨텍스트에서 연결 정보를 읽어 서비스 인스턴스 생성
ConfluenceApiService service = confluenceApiServiceFactory.create(connectionInfo);
```

#### 댓글 색인을 별도 Step으로 분리

초기에는 페이지 처리 Step에서 댓글까지 같이 처리하고 있었다. 페이지와 댓글의 변경 감지 주기가 달라서 페이지 Step이 실패하면 댓글 색인도 함께 중단되는 문제가 있었다. pageId 기반 댓글 조회 전략으로 변경하고, 댓글 색인을 독립적인 Step으로 분리해서 실패가 전파되지 않도록 했다.

#### 첨부파일 처리 (ZIP 포함)

페이지/댓글에 첨부된 파일도 파싱해서 색인해야 했다.

- MIME 타입만 검사하던 포맷 검증을 **확장자 + MIME 타입 이중 검증**으로 강화
- 설정 가능한 파일 크기 상한(`maxFileSizeMb`)을 두고 초과 시 스킵 처리
- ZIP 파일은 내부 엔트리를 순회하며 각각 파싱·색인
- 첨부파일 다운로드를 바이트 배열 방식에서 **스트림 기반**으로 변경, 302 리다이렉트 수동 처리 추가

#### Atlas Doc Format 컨버터 추가

Confluence Cloud는 페이지 본문을 Atlas Doc Format(ADF)으로 반환하는데, 기존 코드는 storage format만 처리했다. ADF를 파싱해서 텍스트를 추출하는 컨버터를 추가하고, `BodyConverter` 인터페이스를 도입해 포맷별로 교체 가능한 구조로 만들었다.

#### SharedContext 래퍼 도입

Step 실행 컨텍스트에서 연결 정보, 스페이스 키 등을 꺼낼 때마다 타입 캐스팅과 null 체크가 반복됐다. `SharedContextUtils` 래퍼 클래스를 도입해서 캐스팅/null 체크를 한 곳에서 처리하고, 이후 모든 Step 컴포넌트가 이를 통해 컨텍스트를 읽도록 통일했다.

#### beforeStep 공통 추상화

각 Step 컴포넌트(Reader, Processor)마다 `beforeStep()`에서 `MetaIndexContext`를 추출하는 코드가 중복돼 있었다. 추상 클래스 `AbstractConfluenceStepComponent`를 만들어 공통 로직을 올리고, 각 컴포넌트는 필요한 부분만 오버라이드하도록 정리했다.

#### 임베딩 실패 로그 기록

임베딩 API에서 문자 수 초과 오류가 발생할 때 어떤 문서가 실패했는지 알 수가 없었다. 실패 시 `IndexingFailLog` 엔티티에 메타데이터(문서 ID, 타입, 스페이스 키 등)를 포함해 기록하고, 해당 문서는 스킵 처리하도록 했다. 페이지와 댓글 모두 동일하게 적용했다.

---

### 2. 삭제 동기화 Step 구현

Confluence에서 삭제된 페이지·댓글·첨부파일이 OpenSearch에 그대로 남아 있는 문제가 있었다.

배치 실행 시점의 Confluence 전체 문서 ID 목록을 수집하고, OpenSearch 색인의 ID와 비교해서 차집합을 삭제하는 Step을 추가했다.

- **페이지·댓글 삭제**: Reader에서 삭제 대상 ID 목록을 읽고, Writer에서 OpenSearch 벌크 삭제
- **첨부파일 삭제**: 페이지/댓글 삭제 시 연관 첨부파일도 연쇄 삭제
- 삭제 대상 문서의 원본 컨텐츠를 정리하는 로직도 함께 구현

---

### 3. 스페이스별 별도 배치 잡 추가 및 MetadataProvider 전략 패턴 도입

#### 배경

특정 스페이스는 메타데이터 포맷이 달랐다. 기존은 `metadata.title`을 쓰지만 이 스페이스는 `metadata.subject`를 써야 했고, `creator_id`나 `extra_data` 필드는 불필요했다. EmbeddingProcessor에 분기를 추가하는 방향은 지저분해질 게 뻔해서 전략 패턴을 적용했다.

#### MetadataProvider 전략 패턴

```java
public interface ConfluenceDocumentMetadataProvider {
    DocumentMetadata buildPageMetadata(ConfluencePageItem page);
    DocumentMetadata buildCommentMetadata(ConfluenceCommentItem comment, ...);
    DocumentMetadata buildPageAttachmentMetadata(...);
    DocumentMetadata buildCommentAttachmentMetadata(...);
}
```

- `DefaultConfluenceDocumentMetadataProvider`: 기존 포맷 (title, creator_id, extra_data 포함)
- `PlanGymConfluenceDocumentMetadataProvider`: 신규 포맷 (subject 사용, extra_data 없음)

EmbeddingProcessor는 수정 없이 `@Qualifier`로 적절한 Provider만 주입받아 동작한다.

#### @StepScope 빈 충돌 해결

두 배치 잡이 같은 타입의 `@StepScope` 빈을 각자 등록하다 보니 `NoUniqueBeanDefinitionException`이 발생했다. 신규 잡 전용 빈들을 별도 Config 클래스로 분리하고, 공용 빈은 `@Component @StepScope`로 전역 등록 후 `@Qualifier`로 명시 주입하는 방식으로 해결했다.

#### Confluence Cloud URL 버그 수정

`_links.webui` 응답이 `/spaces/...` 형태로 오는데 실제 접근 URL은 `/wiki/spaces/...`이다. 조건 분기와 fallback이 섞여 있던 코드를 단순화했다.

```java
// before: null 체크 + startsWith("/wiki") 분기 + fallback
// after
private static String buildPageUrl(ConfluencePage page, String baseUrl) {
    String cleanBaseUrl = baseUrl.replace("/api", "");
    return cleanBaseUrl + "/wiki" + page.getWebuiLink();
}
```

#### 색인 작업 상태 연동

신규 잡을 `AbstractIndexingJobTasklet`의 잡 이름 → `subjectId` 매핑에 추가했다. 이를 위해 JobConfig의 `JOB_NAME` 상수를 `public static final`로 변경했다.

---

### 4. 테스트 인프라 구축

Confluence 파이프라인 코드 작성과 함께 테스트 기반을 만들었다.

- **`@BatchComponentTest`**: 외부 API만 모킹하고 Spring 컴포넌트는 실제 빈을 주입받는 컴포넌트 테스트용 애노테이션 정의. `MockRestServiceServer` 기반의 `FakeConfluenceClientConfig`, OpenSearch 모킹 설정 포함
- 페이지 리더, 댓글 리더, EmbeddingProcessor, 첨부파일 검증 유틸 단위 테스트 추가
- `ConfluenceSpaceCollectTasklet` 단위 테스트 추가

---

### 5. CI/CD 개선

- **Dependabot / Renovate 설정**: 의존성 자동 업데이트 워크플로 추가
- **테스트 결과 업로드**: CI에서 테스트 실패 시 결과 파일을 아티팩트로 업로드해 원인 추적 용이하게 개선
- **GHES 호환 수정**: `upload-artifact` v4 → v3 다운그레이드 (사내 GitHub Enterprise 호환)

---

### 6. 기타 버그 수정

- **배치 잡 완료 후 앱 미종료**: 배치 실행 후 프로세스가 종료되지 않는 문제 수정
- **연결 정보 blank 체크**: `baseUrl`, `username`, `apiToken`을 null 체크에서 blank 체크로 변경 (빈 문자열이 유효한 연결로 처리되던 문제)

---

## 기술적으로 배운 것들

**@StepScope 빈 중복 문제**

같은 타입의 `@StepScope` 빈이 여러 개 등록되면 `NoUniqueBeanDefinitionException`이 난다. 처음엔 빈 이름만 바꾸면 되는 줄 알았는데, 테스트 코드의 `@Autowired`에도 `@Qualifier`를 맞춰줘야 했다. 공용 빈은 전역 등록, 잡 전용 빈은 Config별로 명시 분리하는 게 정석이다.

**Confluence Cloud API webui 경로**

문서에는 webui 링크가 완전한 URL처럼 나오는데 실제 응답은 `/wiki` prefix가 없다. 조건 분기를 넣으면 나중에 헷갈리니 항상 붙이는 방향으로 단순화하는 게 낫다.

**스트림 기반 파일 다운로드**

첨부파일을 한 번에 바이트 배열로 받으면 큰 파일에서 OOM 위험이 있다. 스트림으로 받아서 바로 파싱 API에 넘기는 방식으로 변경했고, Confluence가 302 리다이렉트를 쓰는 경우가 있어 수동 처리가 필요했다.

**전략 패턴으로 메타데이터 포맷 분리**

EmbeddingProcessor 안에 if-else 분기를 넣으려다 MetadataProvider 인터페이스로 뺐다. 새 스페이스 포맷이 생겨도 구현체만 추가하면 되고 Processor는 건드리지 않아도 된다.

---

## 사용 기술

- **언어/프레임워크**: Java 21, Spring Boot 3, Spring Batch
- **검색엔진**: OpenSearch (벡터 색인)
- **외부 API**: Confluence Cloud REST API, 사내 문서 파싱 API, 임베딩 서비스
- **테스트**: JUnit 5, MockRestServiceServer, spring-batch-test, Testcontainers
- **CI/CD**: GitHub Actions, Dependabot, Renovate
- **빌드**: Gradle
