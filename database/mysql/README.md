# MySQL

MySQL과 InnoDB 스토리지 엔진 학습 기록. 아키텍처·인덱스·트랜잭션/락·EXPLAIN·운영 주제로 묶었다.

## 아키텍처

- [MySQL 서버 아키텍처](./mysql-architecture.md) — 커넥션/SQL 레이어/스토리지 엔진 구조 개관
- [InnoDB 스토리지 아키텍처](./innodb-storage-architecture.md) — 버퍼 풀, 체크포인트
- [Redo Log](./redo-log.md) — WAL, fsync, 그룹 커밋

## 인덱스

- [B-Tree 인덱스](./b-tree-index.md) — 구조와 탐색, InnoDB 클러스터드 인덱스
- [복합 인덱스 완전 정복](./composite-index.md) — 좌측 접두사 규칙, 커버링 인덱스
- [EXPLAIN / EXPLAIN ANALYZE](./explain-plan.md) — 실행 계획 읽기

## 트랜잭션과 락

- [InnoDB 트랜잭션과 잠금](./transaction-lock.md) — MVCC/Lock 개관
- [InnoDB MVCC](./innodb-mvcc.md) — Read View, 버전 체인
- [Gap Lock & Next-Key Lock 심층 분석](./innodb-gap-next-key-lock.md) — 구간 락 의미론, RR에서의 함정
- [Deadlock Analysis](./deadlock-analysis.md) — 데드락 로그 해석, 재시도 전략

## 운영

- [복제와 샤딩](./replication-sharding.md) — Source/Replica, 샤딩 전략
- [PublicKeyRetrieval is not allowed](./publickey-retrieval-is-not-allowed.md) — MySQL 8 드라이버 연결 이슈
