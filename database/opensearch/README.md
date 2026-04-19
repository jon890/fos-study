# OpenSearch

OpenSearch(ElasticSearch 포크) 학습 기록. 매핑·샤딩·쿼리·RAG 검색 적용 주제.

## 기본

- [Mapping](./mapping.md) — 필드 타입, 분석기
- [Sharding](./sharding.md) — 프라이머리/레플리카 샤드 전략
- [Refresh Interval](./refresh-interval.md) — 실시간성 vs 처리량 트레이드오프

## 쿼리와 성능

- [DFS Query Then Fetch](./dfs_query_then_fetch.md) — 검색 단계와 스코어링
- [RAG 검색 품질 높이기](./rag-search-quality.md) — Hybrid Search, Reranking, Sentence Window

## 관련 문서

- [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md) — OpenSearch를 RAG용 벡터 스토어로 쓴 실제 사례
