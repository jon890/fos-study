# RAG (Retrieval-Augmented Generation)

RAG 파이프라인 구성 요소 학습 기록. 임베딩·벡터 검색·알고리즘·실제 사례.

## 개념

- [Embedding](./embedding.md) — 임베딩의 의미, 학습 방식(contrastive), Matryoshka, 모델 선택
- [벡터 검색 알고리즘 — kNN에서 HNSW까지](./vector-search-algorithms.md) — 거리 계산, brute force 한계, ANN, HNSW 구조·파라미터·약점
- [HNSW 심화 — 파라미터 튜닝과 구현체별 성능 차이](./hnsw-deep-dive.md) — M·ef_construction·ef_search 상호작용, 코사인=정규화 내적, 구현체별 차이, 필터 충돌·한계
- [임베딩 모델을 바꾸면 벡터 색인 운영도 함께 바뀐다](./embedding-version-and-vector-index-lifecycle.md) — 벡터 버전 추적, 모델과 색인의 동시 전환, 대량 조회 부하 검증

## 검색 구조

- [RAG 검색을 제품별로 만들지 않고 공통 파이프라인으로 둔다](./rag-retrieval-platform-pipeline.md) — 질문 구조화, 하이브리드 검색, 리랭킹, 모듈을 점진적으로 더하는 방식
- [배치 추천에서 실시간 루프로 옮기는 조건과 구성](./recommendation-batch-to-realtime-loop.md) — 배치 추천이 충분한 구간, 전환 조건, 루프 구성과 운영 부담

## 평가·설계

- [RAG를 평가에서 역설계하기](./evaluation-driven-context-provider.md) — 컨텍스트 제공자의 목표, 컴포넌트별 평가, 평가 기준에서 검색 구성을 선택하는 방법
- [문서 파싱 품질을 재는 방법의 스펙트럼](./document-parsing-quality-evaluation.md) — 회귀, golden, NED, TEDS, LLM 판정의 역할과 조합
- [Neo4j GraphRAG로 에이전트 컨텍스트 제공자 만들기](./neo4j-graphrag/README.md) — 온톨로지 모델링부터 관계 탐색, 원문 근거, 평가, 운영까지 이어지는 학습 시리즈

## 실무 사례

- [엔터프라이즈 RAG 구축 사례](./enterprise-rag-with-kubeflow.md) — Kubeflow, Milvus, LLaMA3 조합
- [STORM Parse](./storm-parse.md) — 구조화 추출/파싱 방법
- [Docling](./docling.md) — IBM Research 의 문서 파싱 toolkit. 표·스캔본·다단 레이아웃 처리와 OCR 플러그인
- [토스: 100번 실패하고 살려낸 문서 시스템](./toss-parkssi.md) — 외부 사례 정리

## 관련

- [OpenSearch RAG 검색 품질 높이기](../../database/opensearch/rag-search-quality.md) — Hybrid Search, Reranking, Sentence Window
- [OpenSearch를 벡터 DB로 굴리며 알게 된 것](../../database/opensearch/running-opensearch-as-vector-db.md) — native 메모리, circuit breaker, 샤드 운영
- [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md) — RAG 파이프라인 실제 구현

