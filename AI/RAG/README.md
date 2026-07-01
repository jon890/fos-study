# RAG (Retrieval-Augmented Generation)

RAG 파이프라인 구성 요소 학습 기록. 임베딩·벡터 검색·알고리즘·실제 사례.

## 개념

- [Embedding](./embedding.md) — 임베딩의 의미, 학습 방식(contrastive), Matryoshka, 모델 선택
- [벡터 검색 알고리즘 — kNN에서 HNSW까지](./vector-search-algorithms.md) — 거리 계산, brute force 한계, ANN, HNSW 구조·파라미터·약점
- [HNSW 심화 — 파라미터 튜닝과 구현체별 성능 차이](./hnsw-deep-dive.md) — M·ef_construction·ef_search 상호작용, 코사인=정규화 내적, 구현체별 차이, 필터 충돌·한계

## 벡터 스토어

- [OpenSearch를 VectorStore로 활용하기](./opensearch-vector.md) — 벡터 필드, kNN 쿼리

## 실무 사례

- [엔터프라이즈 RAG 구축 사례 (Kubeflow + Milvus + LLaMA3)](./enterprise-rag-with-kubeflow.md)
- [STORM Parse](./storm-parse.md) — 구조화 추출/파싱 방법
- [토스: 100번 실패하고 살려낸 문서 시스템](./toss-parkssi.md) — 외부 사례 정리

## 신뢰·운영

- [RAG 환각 제어](./hallucination-control.md) — grounding 재주입, sourceQuote 검증, 배치 정합성, bulk 색인

## 관련

- [OpenSearch RAG 검색 품질 높이기](../../database/opensearch/rag-search-quality.md) — Hybrid Search, Reranking, Sentence Window
- [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md) — RAG 파이프라인 실제 구현
