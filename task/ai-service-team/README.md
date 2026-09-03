# NHN AI 서비스 개발 업무 기록

**회사**: NHN | **팀**: AI 서비스 개발팀 | **기간**: 2025.12–현재

AI 서비스 플랫폼에서 진행한 업무 기록을 모았다.

---

## 문서 목록

### 신규 구현

| 기간              | 업무                                                                 | 문서                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 2026.01–2026.03 | Confluence 벡터 색인 배치: RAG 파이프라인, Spring Batch, OpenSearch | [Confluence 문서를 OpenSearch에 벡터 색인하기: Spring Batch 파이프라인 설계기](rag-vector-search-batch.md) |
| 2026.04           | AI 웹툰 제작 도구 MVP: 웹소설 분석부터 60컷 이미지 생성까지의 6단계 파이프라인 | [AI 웹툰 제작 도구 MVP: 6단계 생성 파이프라인](webtoon-maker-ai-pipeline.md) |
| 2026.04–현재 | OCR 비즈니스 오류 관측: HTTP 200 응답 안의 오류 코드 지표와 주간 원인 분류 | [HTTP 200 응답 안의 OCR 오류를 운영 지표로 만들기](ocr-business-error-monitoring.md) |
| 2026.05–현재 | Document Parser 기여 개요: 문서→markdown 파싱 서비스(docling·OCR) 운영·개선 총괄 | [Playground 문서 파싱 파이프라인 기여 개요](playground-document-parser.md) |
| 2026.05–2026.07 | Document Parser 관측성 체계: Prometheus·Grafana, 초기화 순서 함정, 지표 단일화 | [문서 파싱 서비스 관측성 체계 구축: 초기화 순서 함정과 지표 단일화](docparser-observability.md) |
| 2026.05–현재 | 운영 관측과 주간 에러 분류 루프: 지표·로그·요청 ID 를 붙여 AI 와 함께 분석하고 개선 순서를 정하는 구조 | [지표와 로그를 붙이자 AI 와 같이 볼 화면이 생겼다](observability-to-error-triage-loop.md) |
| 2026.06–2026.07 | OCR 공인 진입점 전환: API Gateway 제거, 공인 LB·Ingress 직접 노출, 경로 변환·HTTPS·IP 접근 제어 | [API Gateway를 제거하고 공인 LoadBalancer로 직접 노출하기](ocr-api-gateway-removal.md) |

### 성능 개선

| 기간              | 업무                                                                 | 문서                                                     |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 2026.05–2026.07 | Document Parser 처리 성능 최적화: OCR 병렬화, PPTX 구조 개선, GPU 직렬 추론 실측 | [문서 파싱 서비스 성능 최적화: OCR 병렬화부터 GPU 직렬 추론 실측까지](docparser-performance.md) |

### 트러블슈팅

| 기간    | 업무                                                                          | 문서                                                                   |
| ------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 2026.04 | OCR 서버 배포·스케일인 시 503 에러 수정: [Graceful Shutdown](../../devops/graceful-shutdown.md) 미적용 | [OCR 서버 배포·스케일인 시 503 에러 수정: Graceful Shutdown 미적용](graceful-shutdown-503-fix.md) |
| 2026.05 | Python 서버 RSS 누수: gc.collect 한계, malloc_trim 적용 | [Python 서버 RSS가 줄지 않을 때 malloc_trim을 적용한 과정](glibc-malloc-trim-python-leak.md) |
| 2026.05–2026.07 | Document Parser 메모리·리소스 안정화: 워커 강제 종료·좀비 프로세스·CUDA 중복 누수 방어 | [문서 파싱 서비스, 리소스가 새는 자리를 하나씩 틀어막은 기록](docparser-memory-stability.md) |
| 2026.06–현재 | OCR pod 증감·노드 교체 안정화: 30초 종료 예산, 커넥션 회복, PDB, 클러스터 업그레이드 | [OCR 오토스케일 전환의 connection 에러를 양쪽에서 막기](ocr-scale-connection-resilience.md) |

### 리팩터링

| 기간    | 업무                                                                          | 문서                                                                   |
| ------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 2026.05–현재 | Document Parser 구조 분해와 품질 운영 루프: 회귀·정답지·오류 응답·지원 형식 검증 | [문서 파싱 서비스의 코드 구조 정리와 파싱 품질 운영 루프](docparser-quality-regression.md) |

---

## 기술 키워드

`Spring Boot 3.x` `Java 21` `Spring Batch` `OpenSearch` `RAG` `Vector Search` `Next.js 16` `React 19` `Prisma 7` `Zod 4` `Gemini 3` `@google/genai` `SSE` `Claude Code 하네스` `Python` `FastAPI` `docling` `OCR` `Prometheus` `Grafana` `Docker`
