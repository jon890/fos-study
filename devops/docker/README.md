# Docker

Docker 기본기와 운영 주제 학습 기록.

- [Docker 기본기](./docker.md) — 컨테이너 개념, 이미지, 레이어
- [Dockerfile의 HealthCheck](./health-check.md) — 컨테이너 상태 확인 지시어
- [리눅스에서 프로세스를 격리시키는 방법](./linux-process-isolation.md) — Namespace, Cgroup 기반 격리 원리
- [Docker에서 좀비 프로세스가 쌓이는 이유](./pid1-zombie-tini.md) — PID 1 문제와 tini

## 관련

- [Docker의 PostgreSQL 병렬 쿼리가 디스크가 남아도 No space left on device로 실패하는 이유](../../database/postgresql/docker-parallel-query-dev-shm.md) — 컨테이너 `/dev/shm` 기본 64MB와 PostgreSQL 병렬 쿼리
- [Alpine 이미지의 Java 에서 링크 바꿔치기(TOCTOU)를 막지 못하는 이유](../../java/alpine-securedirectorystream-toctou.md) — Alpine(musl) 베이스 이미지에서 `SecureDirectoryStream` 이 꺼지는 이유
