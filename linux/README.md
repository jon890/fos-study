# Linux

리눅스 시스템 콜·도구 학습 기록.

- [fsync](./fsync.md) — 파일 동기화 시스템 콜. MySQL `innodb_flush_log_at_trx_commit` 동작의 토대
- [SSH forced command 로 배포 키가 실행할 수 있는 명령 제한하기](./ssh-forced-command.md) — `authorized_keys` 의 `restrict,command=` 와 허용 목록 wrapper 로 CI 배포 키가 할 수 있는 일을 제한하는 방법

## 관련

- [Alpine 이미지의 Java 에서 링크 바꿔치기(TOCTOU)를 막지 못하는 이유](../java/alpine-securedirectorystream-toctou.md) — `openat` 과 `O_NOFOLLOW`, musl 에서 꺼지는 JDK 판정
