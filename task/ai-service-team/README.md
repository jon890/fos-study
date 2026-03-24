# NHN AI 서비스 개발 업무 기록

**회사**: NHN | **팀**: AI 서비스 개발팀

AI 서비스 플랫폼에서 진행한 주요 업무를 정리한 문서 모음. (2025.12 ~)

---

## 문서 목록

### 신규 구현

| 기간              | 업무                                                                 | 문서                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 2026.01 ~ 2026.03 | Confluence 벡터 색인 배치 — RAG 파이프라인, Spring Batch, OpenSearch | [rag-vector-search-batch.md](rag-vector-search-batch.md) |

### 리팩터링

| 기간    | 업무                                                                          | 문서                                                                   |
| ------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 2026.03 | 임베딩 메타데이터 구성 개선 — Blocklist → Allowlist, EmbeddingMetadataProvider | [embedding-metadata-provider.md](embedding-metadata-provider.md) |

---

## 기간별 주요 업무

### 2025 하반기 ~ 2026 상반기 (2025.12 ~)

- **Confluence 벡터 색인 배치**: Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인 설계 및 구현
  - ADF → Markdown 변환, 임베딩 비동기 처리(`AsyncItemProcessor`), 삭제 동기화, 다중 스페이스 지원
  - 변경 감지(version 비교), 데이터 보강(첨부파일·작성자·멘션), 전략 패턴 기반 메타데이터 확장
- **임베딩 메타데이터 구성 개선**: blocklist(remove) → allowlist(provider) 방식 전환, `EmbeddingMetadataProvider` 인터페이스 도입으로 OCP 준수

---

## 기술 키워드

`Spring Boot 3.x` `Java 21` `Spring Batch` `OpenSearch` `RAG` `Vector Search`
