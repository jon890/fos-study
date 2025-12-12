# 리눅의에서 프로세스를 격리시키는 방법

> Namespaces + Cgroups = 컨테이너 격리의 기반

이 두 개를 이해하면 "컨테이너가 어떻게 격리되는지"와 "Docker / K8s가 왜 가능한지"를 완전히 이해하게 됨

## 1. Linux Namespace - 리소스를 분리하여 "겉보기 환경"을 따로 만드는 기술

- Namespace는 프로세스마다 **보이는 세계를 다르게 만드는 기술**
- 예를 들어 A 프로세스는 PID 1로 보이는데, B 프로세스는 A를 PID 500으로 봄
- 파일 시스템, 네트워크까지 완전히 다르게 보이게 할 수 있음

### 주요 Namespace 종류

| Namespace   | 역할                                                             | 예시                                        |
| ----------- | ---------------------------------------------------------------- | ------------------------------------------- |
| PID         | 프로세스 번호(PID) 분리                                          | 컨테이너 내부에서는 자신이 PID 1            |
| Mount (mnt) | 파일 시스템 격리                                                 | 다른 루트 파일시스템 (/) 사용 가능          |
| UTS         | 호스트 이름 분리                                                 | 컨테이너마다 hostname 다름                  |
| IPC         | IPC 자원 (Message Queue, Shared Memory) 분리                     | 메시지큐 충돌 없음                          |
| Network     | 네트워크 스택(인터페이스, 라우팅) 분리                           | 각 컨테이너 eth0 따로                       |
| User        | UID/GID 격리                                                     | root처럼 보여도 실제 호스트에선 일반 사용자 |
| Cgroup      | 자원 제한과 관리 (Namespaces와 함께 동작하지만 분류상 별도 가능) | CPU 20%만 사용                              |

> 즉, "동일한 Linux kernel 위에서 가짜 환경을 여러 개 만들어주는 기술"

### 간단 실습 : Namespace로 직접 격리된 환경 만들기

리눅스에서는 `unshare`로 직접 namespace를 만들어 볼 수 있다

```bash
sudo unshare --pid --fork --mount-proc bash
ps -ef # bash pid가 1로 보임, 즉 프로세스 트리가 신규 환경처럼 보임
```

## 2. Cgroups - "CPU, 메모리 등 자원 제한"

Namespace가 "보이는 세게"를 분리하는 것이라면, **Cgroups은 실제 리소스를 제한하고 관리하는 기술**이다

### Cgroups로 할 수 있는 것

- CPU 사용률 제한
- 메모리 최대 사용량 제한
- I/O 제한
- 프로세스 그룹 단위로 리소스 모니터링

예 : 메모리를 100MB로 제한

```bash
mkdir /sys/fs/cgroup/mygroup
echo 10000000 > /sys/fs/cgroup/mygroup/memory.max
echo <pid> > /sys/fs/cgroup/mygroup/cgorup.procs
```

-> pid 프로세스는 100MB 이상 메모리를 사용하면 OOM 발생

## 3. Namespaces + Cgroups 조합하면 컨테이너가 됨

도커가 하는 일은 사실 **리눅스 커널의 기능을 "편하게 쓰도록" 래핑한 것**이다

### 도커가 실행될 때 하는 일

- **1. 새로운 Namespace 생성**
  - PID, Network, Mount, UTS 등
- **2. Cgroup에 프로세스 등록**
  - CPU/메모리 제한 적용
- **3. Chroot 또는 OverlayFS로 파일 시스템 격리**
  - 각 컨테이너만의 root 파일시스템
- **4. Entrypoint 실행**
  - 즉, 컨테이너 안의 메인 프로세스 실행

그래서 결론적으로

> 컨테이너 = Namespace (격리) + Cgroup (자원제한) + Filesystem Overlay (루트FS)
> Docker는 이걸 자동으로 만들어주는 도구

## 4. 프로세스 격리가 어떻게 보안과 직결되는가?

Namespace가 없으면:

- 컨테이너 내부에서 호스트의 `/proc` 접근 가능
- 프로세스 트리 전체가 보임
- 네트워크 인터페이스 접근 가능

Namespace를 사용하면:

- 다른 컨테이너 프로세스가 보이지 않음
- root처럼 보여도 user namespace 덕분에 실제 root 권한 없음
- 네트워크가 각각 독립됨

즉, **컨테이너는 가상머신처럼 보안적으로 분리되지만 훨씬 가볍다**
