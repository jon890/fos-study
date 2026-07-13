# NHN AI 서비스 개발 업무 기록

**회사**: NHN | **팀**: AI 서비스 개발팀

AI 서비스 플랫폼에서 진행한 주요 업무를 정리한 문서 모음. (2025.12 ~)

---

## 문서 목록

### 신규 구현

| 기간              | 업무                                                                 | 문서                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 2026.01 ~ 2026.03 | Confluence 벡터 색인 배치 — RAG 파이프라인, Spring Batch, OpenSearch | [rag-vector-search-batch.md](rag-vector-search-batch.md) |
| 2026.04           | AI 웹툰 제작 도구 MVP — Next.js + Gemini + 하네스 기반 12일 풀스택    | [webtoon-maker-ai-pipeline.md](webtoon-maker-ai-pipeline.md) |
| 2026.05 ~ 2026.07 | Document Parser 관측성 체계 — Prometheus·Grafana, 초기화 순서 함정, 지표 단일화 | [docparser-observability.md](docparser-observability.md) |

### 성능 개선

| 기간              | 업무                                                                 | 문서                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 2026.05 ~ 2026.07 | Document Parser 처리 성능 최적화 — OCR 병렬화, PPTX 구조 개선, GPU 직렬 추론 실측 | [docparser-performance.md](docparser-performance.md) |

### 트러블슈팅

| 기간    | 업무                                                                          | 문서                                                                   |
| ------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 2026.04 | OCR 서버 배포·스케일인 시 503 에러 수정 — [Graceful Shutdown](../../devops/graceful-shutdown.md) 미적용 | [graceful-shutdown-503-fix.md](graceful-shutdown-503-fix.md) |
| 2026.05 | Python 서버 RSS 누수 — gc.collect 한계, malloc_trim 적용 | [glibc-malloc-trim-python-leak.md](glibc-malloc-trim-python-leak.md) |
| 2026.05 ~ 2026.07 | Document Parser 메모리·리소스 안정화 — 워커 강제 종료·좀비 프로세스·CUDA 중복 누수 방어 | [docparser-memory-stability.md](docparser-memory-stability.md) |

### 리팩터링

| 기간    | 업무                                                                          | 문서                                                                   |
| ------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 2026.03 | 임베딩 메타데이터 구성 개선 — Blocklist → Allowlist, EmbeddingMetadataProvider | [embedding-metadata-provider.md](embedding-metadata-provider.md) |
| 2026.05 ~ 2026.07 | Document Parser 코드 구조 분해 + 파싱 품질 회귀 검증 — 회귀 vs 품질 축 분리 | [docparser-quality-regression.md](docparser-quality-regression.md) |

---

## 기간별 주요 업무

### 2025 하반기 \~ 2026 상반기 (2025.12 \~)

- **Confluence 벡터 색인 배치**: Confluence 문서를 OpenSearch에 벡터 색인하는 Spring Batch 파이프라인 설계 및 구현
  - ADF → Markdown 변환, 임베딩 비동기 처리(`AsyncItemProcessor`), 삭제 동기화, 다중 스페이스 지원
  - 변경 감지(version 비교), 데이터 보강(첨부파일·작성자·멘션), 전략 패턴 기반 메타데이터 확장
- **임베딩 메타데이터 구성 개선**: blocklist(remove) → allowlist(provider) 방식 전환, `EmbeddingMetadataProvider` 인터페이스 도입으로 OCP 준수
- **OCR 서버 배포·스케일인 503 에러 수정**: Envoy `drain_listeners` 후 SIGTERM 즉시 종료로 발생한 30~60초 503 묶음 — gRPC 서버에 graceful shutdown 적용해 preStop sleep 동안 in-flight 요청을 마저 처리하도록 종료 시퀀스 재정렬
- **AI 웹툰 제작 도구 MVP**: 12일 단독 풀스택 — 웹소설 → 세계관/캐릭터/각색/글콘티 → 60컷 이미지 6단계 파이프라인
  - Claude Code 하네스 기반 4인 에이전트 팀(planner/critic/executor/docs-verifier)으로 12일/199 plan/760 커밋
  - vibe 코딩 → spec 기반 코딩 진화: `/planning` → `/plan-and-build` → `/build-with-teams`, 디자이너 통합용 `/integrate-ux` 스킬화
  - Gemini 모델 전략(퀄리티 우선 + 429 fallback + 전역 Rate Limit Tracking), 통합 분석으로 토큰 75% 절감
  - 글콘티 환각 차단: Grounding 블록 + Continuation 재주입 + Project 단위 Context Cache (ADR-132)
  - 캐릭터 외형 고정: 텍스트 anti-drift 한계 → mode 분기 + 기본 시트 이미지 자동 레퍼런스 prepend (ADR-133/134)
  - 디자이너 협업: Container/Presenter + Layout Primitives + 파일 소유권 매트릭스로 git conflict 해소 (ADR-129/130)
  - 타입 시스템: Zod ↔ Prisma 레이어별 분리(Action=Zod / Repository=Prisma) + mapper로 경계 정리 (ADR-131)
- **Document Parser 운영·성능·안정화**: PDF·이미지·오피스 문서를 markdown으로 변환하는 FastAPI 서비스(docling + OCR)를 사실상 단독으로 운영하며 관측성·성능·리소스·품질 네 축을 개선
  - 관측성: uvicorn 다중 프로세스 메트릭을 `/metrics` 하나로 통합, Prometheus·Grafana 대시보드 구축, 배포 직후 메트릭 누락 사고(초기화 순서 함정) 대응
  - 성능: OCR 페이지·영역 통합 병렬화로 idle pool 84% 해소, PPTX base64 왕복 제거로 대용량 문서 본문 604배 부풀림 해소, docling threaded pipeline은 로컬 30% 단축이 운영 GPU에서 오차 수준임을 실측(GPU 단일 직렬 추론)
  - 리소스: signal.alarm 미동작 워커를 감시 프로세스 SIGKILL로 회수, 대용량 xlsx 행 단위 streaming(27GiB→RSS 92MB), LibreOffice 좀비 tini 회수, CUDA 3중 중복 제거로 이미지 9.89GB→6.82GB
  - 품질: 1939줄 단일 파일 도메인별 분해 + 단위 테스트 135건, "회귀(전후 동일)"와 "품질(golden 대비 정확도)"을 다른 축으로 분리 검증

---

## 기술 키워드

`Spring Boot 3.x` `Java 21` `Spring Batch` `OpenSearch` `RAG` `Vector Search` `Next.js 16` `React 19` `Prisma 7` `Zod 4` `Gemini 3` `@google/genai` `SSE` `Claude Code 하네스` `Python` `FastAPI` `docling` `OCR` `Prometheus` `Grafana` `Docker`
