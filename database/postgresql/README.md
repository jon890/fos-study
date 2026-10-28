# PostgreSQL

PostgreSQL 운영과 실행 구조 학습 기록.

## 글

- [PostgreSQL 실행 계획 기초: 쿼리가 실행되는 순서부터 스캔, 조인, 통계까지](./execution-plan-basics.md) — 페이지와 heap, 스캔과 조인 방법, 계획의 숫자, 통계, 청크, CTE와 창 함수. 실행 계획 시리즈의 첫 편
- [PostgreSQL 실행 계획 읽기: Index Cond와 Filter, heap 접근, generic plan과 TimescaleDB 청크 제외](./explain-index-cond-generic-plan-chunks.md) — `EXPLAIN (ANALYZE, BUFFERS)`, 커버링 인덱스와 visibility map, `plan_cache_mode`와 pgjdbc `prepareThreshold`, 청크 제외
- [PostgreSQL 쿼리 패턴과 실행 계획: LATERAL 최신 한 건, unnest와 Inner Unique, gaps and islands](./lateral-unnest-window-query-plans.md) — 그룹마다 최신 한 건, 배열을 표로 펼치기, `lag()`로 연속 구간 찾기
- [Docker의 PostgreSQL 병렬 쿼리가 디스크가 남아도 No space left on device로 실패하는 이유](./docker-parallel-query-dev-shm.md) — 병렬 쿼리의 동적 공유 메모리, Docker `/dev/shm` 64MB, 확인 명령과 대안 비교

## 관련

- [MySQL](../mysql/README.md) — InnoDB, 인덱스, 트랜잭션, 락
