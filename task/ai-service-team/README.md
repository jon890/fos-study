# NHN AI 서비스 개발 업무 기록

**회사**: NHN | **팀**: AI 서비스 개발팀

AI 서비스 플랫폼에서 진행한 주요 업무를 정리한 문서 모음. (2025.12 ~)

---

## 문서 목록

### 신규 구현

| 기간              | 업무                                                                 | 문서                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 2026.01 ~ 2026.03 | Confluence 벡터 색인 배치 — RAG 파이프라인, Spring Batch, OpenSearch | [rag-vector-search-batch.md](rag-vector-search-batch.md) |
| 2026.04           | AI 웹툰 제작 도구 MVP — Next.js + Gemini + 하네스 기반 10일 풀스택    | [webtoon-maker-ai-pipeline.md](webtoon-maker-ai-pipeline.md) |

### 트러블슈팅

| 기간    | 업무                                                                          | 문서                                                                   |
| ------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 2026.04 | OCR 서버 배포·스케일인 시 503 에러 수정 — Graceful Shutdown 미적용 | [graceful-shutdown-503-fix.md](graceful-shutdown-503-fix.md) |

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
- **AI 웹툰 제작 도구 MVP**: 사내 TF 차출, 10일 단독 풀스택 — 웹소설 → 세계관/캐릭터/각색/글콘티 → 60컷 이미지 6단계 파이프라인
  - Claude Code 하네스 기반 4인 에이전트 팀으로 10일/167 plan/555 커밋
  - Gemini 모델 전략(퀄리티 우선 + 429 fallback + 전역 Rate Limit Tracking)
  - 통합 분석으로 토큰 75% 절감, Promise.allSettled 기반 60컷 부분성공 생성, Zod 단일 소스 전환

---

## 기술 키워드

`Spring Boot 3.x` `Java 21` `Spring Batch` `OpenSearch` `RAG` `Vector Search` `Next.js 16` `React 19` `Prisma 7` `Zod 4` `Gemini 3` `@google/genai` `SSE` `Claude Code 하네스`
