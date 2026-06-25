# OpenSearch

OpenSearch(ElasticSearch 포크) 학습 기록. 매핑·샤딩·쿼리·RAG 검색 적용 주제.

## 입문

- [OpenSearch 기초](./opensearch-basics.md) — 검색 엔진을 백엔드 관점에서 다루는 입문 가이드

## 색인 / 매핑

- [Mapping](./mapping.md) — 필드 타입, 분석기
- [Sharding](./sharding.md) — 프라이머리/레플리카 샤드 전략
- [Refresh Interval](./refresh-interval.md) — 실시간성 vs 처리량 트레이드오프

## 분석기 / 플러그인

- [Analyzer 구조 (nori, ngram, tokenizer, token filter)](./opensearch-plugins-nori-ngram-analyzer-tokenizer-token-filter.md) — 한국어 형태소·자동완성·오타 보정의 빌딩 블록

## 쿼리와 성능

- [DFS Query Then Fetch](./dfs_query_then_fetch.md) — 검색 단계와 스코어링
- [OpenSearch를 벡터 DB로 굴리며 알게 된 것](./running-opensearch-as-vector-db.md) — k-NN graph memory와 circuit breaker 운영 포인트
- [RAG 검색 품질 높이기](./rag-search-quality.md) — Hybrid Search, Reranking, Sentence Window

## 관련 문서

- [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md) — OpenSearch를 RAG용 벡터 스토어로 쓴 실제 사례
