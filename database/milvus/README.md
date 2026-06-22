# Milvus

전용 벡터 데이터베이스 Milvus 학습 기록.

## 글

- [Milvus 아키텍처와 동작, 실무 규모 성능](./milvus-architecture-and-performance.md) — storage-compute 분리, segment/WAL, 인덱스 종류(DiskANN·GPU CAGRA), sparse(BM25·SPLADE)·multi-vector 하이브리드, 한국어 하이브리드(lindera ko-dic)
- [OpenSearch vs Milvus 심층 비교](./opensearch-vs-milvus.md) — 아키텍처·노드 역할·메모리 담당·검색 품질·한국어를 1:1 로 대조
- [Milvus 3.0 은 무엇을 바꾸나](./milvus-3-0-whats-new.md) — 3.0-beta 의 운영 단순화·데이터 레이크 통합(External Collection)·스키마 표현력

## 관련

- [벡터 DB 선택 가이드](../vectordb-comparison.md) — 4제품 비교와 조건별 선택
- [OpenSearch — RAG 검색](../opensearch/README.md) — 범용 검색엔진의 벡터 검색
- [RAG / 임베딩](../../AI/RAG/README.md)
