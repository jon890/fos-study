# MySQL

MySQL과 InnoDB 스토리지 엔진 학습 기록. 아키텍처, 인덱스, 트랜잭션/락, EXPLAIN, 운영 주제로 묶었다.

이 폴더는 **짧은 탐색용 허브**다. 각 문서는 역할을 나눠 유지한다.
- 빠르게 전체 지형을 보고 싶으면 이 README에서 출발
- 인덱스 전체 그림은 [B-Tree 인덱스 허브](./b-tree-index.md)
- 엔진 내부 구조를 공부 중이면 [InnoDB 스토리지 아키텍처](./innodb-storage-architecture.md)
- 실행 계획 실전 진단은 [EXPLAIN / EXPLAIN ANALYZE](./explain-plan.md)

## 아키텍처

- [MySQL 서버 아키텍처](./mysql-architecture.md) — 커넥션/SQL 레이어/스토리지 엔진 구조 개관
- [InnoDB 스토리지 아키텍처](./innodb-storage-architecture.md) — 버퍼 풀, 체크포인트
- [Redo Log](./redo-log.md) — WAL, fsync, 그룹 커밋

## 인덱스

- [B-Tree 인덱스](./b-tree-index.md) — 인덱스 전체 그림을 잡는 허브 문서
- [복합 인덱스 완전 정복](./composite-index.md) — 좌측 접두사 규칙, 커버링 인덱스, 컬럼 순서 심화
- [EXPLAIN / EXPLAIN ANALYZE](./explain-plan.md) — 실행 계획 읽기와 실제 진단

## 트랜잭션과 락

- [InnoDB 트랜잭션과 잠금](./transaction-lock.md) — MVCC/Lock 개관
- [InnoDB MVCC](./innodb-mvcc.md) — Read View, 버전 체인
- [Gap Lock & Next-Key Lock 심층 분석](./innodb-gap-next-key-lock.md) — 구간 락 의미론, RR에서의 함정
- [Deadlock Analysis](./deadlock-analysis.md) — 데드락 로그 해석, 재시도 전략

## 운영

- [복제와 샤딩](./replication-sharding.md) — Source/Replica, 샤딩 전략
- [PublicKeyRetrieval is not allowed](./publickey-retrieval-is-not-allowed.md) — MySQL 8 드라이버 연결 이슈
