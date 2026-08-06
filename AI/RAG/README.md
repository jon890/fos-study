# RAG (Retrieval-Augmented Generation)

RAG 파이프라인 구성 요소 학습 기록. 임베딩·벡터 검색·알고리즘·실제 사례.

## 개념

- [Embedding](./embedding.md) — 임베딩의 의미, 학습 방식(contrastive), Matryoshka, 모델 선택
- [벡터 검색 알고리즘 — kNN에서 HNSW까지](./vector-search-algorithms.md) — 거리 계산, brute force 한계, ANN, HNSW 구조·파라미터·약점
- [HNSW 심화 — 파라미터 튜닝과 구현체별 성능 차이](./hnsw-deep-dive.md) — M·ef_construction·ef_search 상호작용, 코사인=정규화 내적, 구현체별 차이, 필터 충돌·한계

## 평가·설계

- [RAG를 평가에서 역설계하기](./evaluation-driven-context-provider.md) — 컨텍스트 제공자의 목표, 컴포넌트별 평가, 평가 기준에서 검색 구성을 선택하는 방법
- [Neo4j GraphRAG로 에이전트 컨텍스트 제공자 만들기](./neo4j-graphrag/README.md) — 온톨로지 모델링부터 관계 탐색, 원문 근거, 평가, 운영까지 이어지는 학습 시리즈

## 실무 사례

- [엔터프라이즈 RAG 구축 사례 (Kubeflow + Milvus + LLaMA3)](./enterprise-rag-with-kubeflow.md)
- [STORM Parse](./storm-parse.md) — 구조화 추출/파싱 방법
- [토스: 100번 실패하고 살려낸 문서 시스템](./toss-parkssi.md) — 외부 사례 정리

## 관련

- [OpenSearch RAG 검색 품질 높이기](../../database/opensearch/rag-search-quality.md) — Hybrid Search, Reranking, Sentence Window
- [OpenSearch를 벡터 DB로 굴리며 알게 된 것](../../database/opensearch/running-opensearch-as-vector-db.md) — native 메모리, circuit breaker, 샤드 운영
- [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md) — RAG 파이프라인 실제 구현

