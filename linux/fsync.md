# fsync — 리눅스 파일 동기화 시스템 콜

데이터베이스가 "디스크에 썼다"고 보장하는 메커니즘을 이해하려면 fsync를 알아야 한다. MySQL `innodb_flush_log_at_trx_commit=1`의 동작도 결국 fsync 호출이다.

---

## 파일 쓰기의 계층 구조

애플리케이션에서 `write()`를 호출했다고 데이터가 바로 디스크에 가지 않는다.

```
애플리케이션
    │ write() 시스템 콜
    ↓
OS 페이지 캐시 (커널 버퍼)  ← 여기까지만 쓰여도 write() 반환
    │ 커널이 알아서 나중에 flush (pdflush/writeback)
    ↓
디스크 컨트롤러 캐시
    │
    ↓
물리 디스크 (플래터 / NAND)
```

`write()` 호출이 성공해도 데이터는 OS 페이지 캐시에 있을 뿐이다. 프로세스가 죽어도 OS가 살아있으면 데이터는 보존된다. 하지만 **OS가 크래시하거나 전원이 나가면 페이지 캐시의 데이터는 사라진다.**

---

## fsync

```c
#include <unistd.h>
int fsync(int fd);
```

**OS 페이지 캐시의 내용을 물리 디스크까지 flush하고, 완전히 기록될 때까지 블로킹한다.**

```
fsync(fd) 호출
    ↓
OS 페이지 캐시 → 디스크 컨트롤러 캐시 → 물리 디스크
    ↓
모두 기록 완료 후 반환
```

fsync가 반환되면 그 시점까지 write한 데이터는 디스크 장애가 아닌 이상 살아있다고 보장된다.

---

## 관련 시스템 콜 비교

| 시스템 콜 | 동작 | 보장 수준 |
|---|---|---|
| `write()` | OS 페이지 캐시에 기록 | 프로세스 크래시 후 생존 |
| `fdatasync()` | 데이터만 디스크까지 flush (메타데이터 제외) | OS 크래시 후 생존 |
| `fsync()` | 데이터 + 파일 메타데이터(크기, 수정 시간 등)까지 flush | OS 크래시 후 생존 |
| `sync()` | 시스템 전체 dirty buffer flush (완료 보장 없음) | 약한 보장 |

`fdatasync()`는 파일 크기 등 복구에 필요한 메타데이터만 제외하고 동기화해서 `fsync()`보다 I/O 횟수가 적다. 데이터베이스처럼 파일 크기가 미리 할당된 경우 `fdatasync()`로 충분하고 더 빠르다.

---

## O_DIRECT와의 관계

```c
int fd = open("file", O_WRONLY | O_DIRECT);
```

`O_DIRECT` 플래그로 열면 OS 페이지 캐시를 **완전히 우회**해서 직접 디스크로 쓴다.

```
O_DIRECT write():
    애플리케이션 버퍼 → 디스크 컨트롤러 캐시 → 물리 디스크
    (OS 페이지 캐시 없음)
```

`O_DIRECT`를 쓰면 write() 자체가 디스크까지 내려가므로 매번 fsync가 필요 없다. 하지만 OS 캐시의 읽기 이점도 사라진다. 데이터베이스는 자체 버퍼(Buffer Pool)를 갖추고 있어서 OS 페이지 캐시가 이중으로 필요 없다. 그래서 InnoDB는 `O_DIRECT`를 사용한다 (`innodb_flush_method=O_DIRECT`).

---

## MySQL과 fsync의 관계

`innodb_flush_log_at_trx_commit` 설정이 결국 fsync 호출 시점을 결정한다.

```
값=1 (기본값):
    트랜잭션 커밋
        → Redo Log Buffer → write() → OS 페이지 캐시
        → fsync() 호출 → 디스크까지 보장
        → 커밋 완료 반환

값=2:
    트랜잭션 커밋
        → Redo Log Buffer → write() → OS 페이지 캐시
        → 커밋 완료 반환  (fsync 없음)
    백그라운드 스레드 (초당 1회):
        → fsync() 호출

값=0:
    트랜잭션 커밋
        → Redo Log Buffer에만 기록
        → 커밋 완료 반환  (write도 없음)
    백그라운드 스레드 (초당 1회):
        → write() + fsync()
```

값=1이 느린 이유는 커밋마다 fsync를 호출하기 때문이다. SSD에서도 fsync는 수백 마이크로초의 레이턴시가 있다. 초당 수천 건 커밋이 필요한 워크로드에서 병목이 된다.

**Group Commit**: MySQL은 여러 트랜잭션의 커밋을 모아서 fsync를 한 번에 호출하는 최적화를 한다. 동시 커밋이 많을수록 효과가 크다.

---

## Java에서 fsync

Java의 `FileOutputStream.flush()`는 Java 버퍼를 OS로 내보낼 뿐, OS 페이지 캐시까지만 쓴다. 디스크까지 보장하지 않는다.

```java
// OS 페이지 캐시까지만 (fsync 없음)
fileOutputStream.flush();

// 디스크까지 보장
FileChannel channel = fileOutputStream.getChannel();
channel.force(true);   // fsync와 동일, true = 메타데이터 포함
channel.force(false);  // fdatasync와 유사, 데이터만
```

`FileChannel.force(true)`가 내부적으로 `fsync()` 시스템 콜을 호출한다.

로컬 파일에 중요한 데이터를 영속화해야 할 때 (`flush()`만 하면 OS 크래시 시 손실될 수 있다.

---

## 디스크 캐시 문제

fsync를 호출해도 **디스크 컨트롤러의 쓰기 캐시(Write Cache)** 가 활성화되어 있으면 완전한 보장이 되지 않는다. 디스크가 "썼다"고 응답했지만 실제로는 컨트롤러 캐시에 있을 수 있기 때문이다.

- 서버용 NVMe/SSD는 전원 손실 보호(Power Loss Protection) 기능이 있어서 이 문제를 해결한다
- 일반 SATA HDD는 쓰기 캐시 비활성화(`hdparm -W 0`)를 고려하기도 한다
- 클라우드 환경의 EBS, Persistent Disk 등은 내부적으로 이를 처리한다

데이터베이스 서버를 직접 운영한다면 디스크의 쓰기 캐시 설정을 확인할 필요가 있다.

---

## 관련 문서

- [Redo Log — MySQL에서 fsync 활용](../database/mysql/redo-log.md)
