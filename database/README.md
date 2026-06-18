# Database

데이터 스토어 관련 학습 기록. 관계형·검색엔진·캐시를 모두 포함한다.

## 스토어별

- [MySQL](./mysql/README.md) — InnoDB, 인덱스, 트랜잭션, 락
- [Redis](./redis/README.md) — 캐시, 분산 락, Pub/Sub, 세션, 랭킹
- [OpenSearch](./opensearch/README.md) — 매핑, 샤딩, RAG 검색
- [Milvus](./milvus/README.md) — 벡터 DB 아키텍처·동작·실무 규모 성능

## 공통 주제

- [인덱스 개론](./index.md) — DB 성능 최적화의 핵심
- [커넥션 풀 크기](./connection-pool.md) — 풀 사이즈 결정 기준
- [커넥션 풀 포화와 스레드 풀 격리](./connection-pool-saturation-thread-pool-isolation.md) — Saturation·Exhaustion·Starvation 구분과 격리 패턴
- [정규화](./정규화.md) / [역정규화](./역정규화.md)
- [벡터 DB 비교 — OpenSearch·Milvus·Qdrant·Vespa](./vectordb-comparison.md) — 데이터 규모·차원·하이브리드별 선택 가이드
- [HNSW 깊이 보기](./hnsw.md) — 벡터 검색이 빠른 원리(그래프 인덱스)

## 도서

- [김영한의 실전 데이터베이스 설계](./김영한의-실전-데이터베이스-설계/README.md)

## 면접 대비 — 커머스 응용 (초안)

- [JPA N+1과 커머스 조회 모델](./jpa-n-plus-one-commerce-read-model.md) — 주문/메뉴/쿠폰 도메인
- [MyBatis와 JPA/Hibernate 트레이드오프](./mybatis-jpa-tradeoffs.md) — 레거시 백엔드를 다루는 시니어 관점
- [MyBatis 동적 SQL과 ResultMap 기본기](./mybatis-dynamic-sql-resultmap-basics.md) — 안전한 동적 쿼리·결과 매핑

## 관련

- [캐시 설계 전략](../architecture/cache-strategies.md) — 캐시 패턴 총정리
