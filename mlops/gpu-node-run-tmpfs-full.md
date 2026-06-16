# Kubernetes GPU 노드에서 /run tmpfs가 꽉 차서 Pod가 안 뜰 때

NHN Cloud OCR 리얼 배포 중 ArgoCD sync가 Degraded로 떨어졌다.
pod sandbox 생성 단계에서 `no space left on device` 에러가 반복 발생했고, 원인은 GPU 노드의 `/run` tmpfs 포화였다.

루트 디스크는 16%밖에 안 쓰고 있는데 pod가 안 뜨는 상황이라 처음엔 혼란스러웠다.
이 글에서는 `/run` tmpfs가 뭔지, containerd가 왜 거기에 데이터를 저장하는지, GPU 노드에서 왜 특히 문제가 되는지를 정리한다.

## 증상

ArgoCD에서 ocr-api와 ocr-console이 Degraded 상태로 전환됐다.
kubectl로 이벤트를 조회하니 **pod sandbox** 생성 단계에서 에러가 반복되고 있었다.

pod sandbox란 pod 안의 모든 컨테이너가 공유하는 격리 환경(network namespace, IPC namespace 등)을 만드는 첫 단계다.
Kubernetes는 pod를 생성할 때 먼저 **pause 컨테이너**(인프라 컨테이너)를 실행해서 namespace를 확보하고, 그 위에 실제 앱 컨테이너를 올린다.
sandbox 생성이 실패하면 그 pod 안의 어떤 컨테이너도 시작할 수 없어서 `ContainerCreating` 상태로 멈추게 된다.

이 sandbox 생성 과정에서 containerd가 `/run/containerd/.../config.json`을 쓰려고 했는데, `/run` tmpfs가 꽉 차서 파일을 못 쓴 것이 에러의 직접적인 원인이었다.

```
Failed to create pod sandbox: rpc error: code = Unknown desc =
failed to create containerd task: failed to start shim:
write /run/containerd/io.containerd.runtime.v2.task/k8s.io/.../config.json:
no space left on device: unknown
```

동시에 nvidia-container-runtime 관련 에러도 섞여 있었다.

```
OCI runtime exec failed: /usr/bin/nvidia-container-runtime
did not terminate successfully: exit status 255: unknown
```

## 어떤 노드에서 발생했나

클러스터에는 6대의 노드가 있었다.

| 노드 그룹 | 노드 수 | 용도 |
|---|---|---|
| application | 2대 | OCR API, Console, Admin, Metering |
| default-worker | 2대 | 시스템 워크로드 |
| gpu-llm | 2대 | LLM 모델 서버 (GPU) |

`kubectl describe pod`로 확인하니 문제가 발생한 pod는 전부 **gpu-llm 노드**에 스케줄된 것이었다.
application 노드에 스케줄된 pod는 정상이었다.

## 디스크는 충분한데 왜?

GPU 노드에 ssh로 접속해서 `df -h`를 확인했다.

```bash
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
tmpfs           8.9G  8.9G     0 100% /run        # ← 여기가 100%
/dev/vda1       485G   78G  408G  16% /            # ← 루트는 여유
tmpfs            45G  1.2M   45G   1% /dev/shm
```

루트 디스크는 485G 중 78G만 사용(16%)하고 있었다.
문제는 `/run`이라는 tmpfs가 8.9G 중 8.9G를 전부 쓰고 있었다는 것이다.

## tmpfs와 /run이란

여기서 tmpfs와 `/run`에 대해 짚고 넘어가자.

### tmpfs — RAM 위의 파일시스템

**tmpfs**(temporary filesystem)는 디스크가 아니라 **RAM 위에 존재하는 파일시스템**이다.
일반 파일시스템처럼 파일을 읽고 쓸 수 있지만, 모든 데이터가 메모리에 저장되기 때문에 디스크 I/O가 없어 매우 빠르다.
대신 재부팅하면 전부 사라진다.

Linux 커널 문서에 따르면 tmpfs의 기본 크기는 **물리 RAM의 50%**다.
다만 `/run`은 systemd가 부팅 시 별도로 마운트하며, 배포판마다 기본 크기가 다르다.
이 GPU 노드에서는 약 90G RAM의 10%인 8.9G로 설정되어 있었다.

### /run — 런타임 임시 데이터의 표준 경로

`/run`은 Linux FHS(Filesystem Hierarchy Standard)에서 정의한 **런타임 데이터 전용 디렉터리**다.
부팅 후 프로세스들이 실행 중에 필요한 임시 파일을 저장하는 곳이다.

| 저장되는 것 | 예시 | 설명 |
|---|---|---|
| PID 파일 | `/run/sshd.pid` | 프로세스 ID 기록 |
| Unix 소켓 | `/run/containerd/containerd.sock` | 프로세스 간 통신(IPC) |
| Lock 파일 | `/run/lock/*` | 동시 접근 방지 |
| FIFO/파이프 | containerd shim의 `log` | 데이터 스트리밍 |
| 마운트 포인트 | 컨테이너 rootfs | overlay 마운트 포인트 |

이전에는 `/var/run`이 이 역할을 했지만, 현대 Linux에서는 `/var/run`이 `/run`의 심볼릭 링크다.

핵심은 `/run`이 tmpfs라는 점이다.
디스크가 아니라 RAM에서 할당된 제한된 공간이므로, 여기에 저장되는 데이터가 많아지면 루트 디스크와 무관하게 공간 부족이 발생한다.

## containerd 아키텍처 — 컨테이너가 실행되기까지

containerd가 `/run`을 왜 쓰는지 이해하려면 컨테이너가 실행되는 전체 흐름을 알아야 한다.

### Kubelet에서 컨테이너까지의 호출 체인

Kubernetes에서 컨테이너가 실행되는 과정은 여러 컴포넌트를 거친다.

```
Kubelet
  ↓  CRI (Container Runtime Interface)
containerd
  ↓  fork/exec
containerd-shim (shim v2)
  ↓  fork/exec
runc (OCI Runtime)
  ↓  clone/exec
컨테이너 프로세스
```

각 컴포넌트의 역할:

- **Kubelet**: Kubernetes 노드 에이전트. pod spec을 받아 컨테이너 생성을 요청한다
- **containerd**: 고수준 컨테이너 런타임. 이미지 pull, 스냅샷 관리, 컨테이너 라이프사이클 조율을 담당한다. 직접 컨테이너를 실행하지는 않는다
- **containerd-shim**: containerd와 실제 런타임 사이의 중간 프로세스. containerd가 재시작되어도 컨테이너가 죽지 않도록 분리하는 역할이다
- **runc**: OCI(Open Container Initiative) 표준을 구현한 저수준 런타임. 실제로 Linux namespace, cgroup을 설정하고 컨테이너 프로세스를 실행한다

GPU 노드에서는 runc 대신 **nvidia-container-runtime**이 사용된다.
이 런타임이 GPU 디바이스를 컨테이너에 매핑하는 역할을 한다.

### containerd가 /run에 저장하는 것

containerd는 컨테이너를 실행할 때 `/run/containerd/io.containerd.runtime.v2.task/k8s.io/<컨테이너ID>/` 디렉터리를 만든다.
여기에 저장되는 파일:

| 파일 | 용도 |
|---|---|
| `config.json` | OCI 컨테이너 스펙 (namespace, mount, env 등) |
| `log` | shim 프로세스의 로그 FIFO 파이프 |
| `address` | shim의 ttrpc 소켓 주소 |
| `rootfs/` | 컨테이너 파일시스템의 overlay 마운트 포인트 |

이 데이터가 `/run`(tmpfs)에 저장되는 이유:

- **속도**: 컨테이너 생성/삭제가 빈번하므로 RAM 기반이 유리하다
- **임시성**: 컨테이너가 죽으면 의미 없는 데이터라 디스크 영속이 불필요하다
- **Linux 표준**: `/run`은 런타임 상태 데이터의 표준 경로다

한편 **영구 데이터**(이미지 레이어, 스냅샷)는 `/var/lib/containerd/`에 저장된다.
이쪽은 루트 디스크를 사용하므로 tmpfs 제한과 무관하다.

### shim v2의 1:1 프로세스 모델

containerd shim v2는 **컨테이너당 하나의 shim 프로세스**를 fork한다.
각 shim은 자신만의 task 디렉터리를 `/run/containerd/io.containerd.runtime.v2.task/k8s.io/` 아래에 갖는다.

이 설계 덕분에 containerd 데몬이 재시작되어도 shim이 살아있어 컨테이너가 죽지 않는다.
하지만 동시에, 컨테이너 수가 많아지면 `/run`에 저장되는 task 디렉터리와 관련 커널 메타데이터도 비례해서 늘어난다.

## Overlay 파일시스템과 마운트 포인트

컨테이너의 rootfs는 overlay 파일시스템으로 구성된다.
이 부분이 `/run` tmpfs 사용량에 영향을 주는 핵심이다.

### Overlay 마운트 구조

overlay 파일시스템은 여러 디렉터리를 겹쳐서 하나의 통합된 뷰를 만든다.

```
[컨테이너가 보는 파일시스템]
         ↑
    overlay mount
    ┌─────────────────────────────┐
    │ upperdir (쓰기 가능 레이어)   │ → /var/lib/containerd/.../snapshots/N/fs
    │ lowerdir (읽기 전용 레이어들) │ → /var/lib/containerd/.../snapshots/{1,2,3,...}/fs
    │ workdir  (overlay 내부 작업) │ → /var/lib/containerd/.../snapshots/N/work
    └─────────────────────────────┘
         ↓
    mount point: /run/containerd/io.containerd.runtime.v2.task/k8s.io/<ID>/rootfs
```

실제 이미지 데이터(lowerdir, upperdir)는 `/var/lib/containerd/`(루트 디스크)에 있다.
하지만 **마운트 포인트 자체**는 `/run` tmpfs에 위치한다.

### 커널 메타데이터가 tmpfs를 먹는다

overlay 마운트가 설정되면 커널은 마운트 포인트 아래의 파일/디렉터리에 대해 **dentry**(디렉터리 엔트리)와 **inode** 구조체를 생성한다.
Linux 커널 문서에 따르면 overlay 파일시스템은 하위 파일시스템의 dentry 트리를 복제하여 빠른 캐시 조회를 가능하게 한다.

이 메타데이터는 마운트 포인트가 속한 파일시스템, 즉 `/run` tmpfs의 공간을 소비한다.
`find -xdev -type f`로 찾으면 일반 파일이 거의 안 나오는데, `df`에서는 100%로 표시되는 이유가 이것이다.

## GPU 노드에서 특히 문제가 되는 이유

일반 application 노드의 `/run`은 794M tmpfs에 1%만 사용하고 있었다.
GPU 노드만 8.9G tmpfs가 꽉 찬 이유는 두 가지다.

### LLM 이미지의 레이어 수

`mount` 명령으로 overlay 마운트 정보를 확인했다.

일반 컨테이너(calico, neuvector 등):
```
overlay on .../rootfs type overlay (
  lowerdir=snapshots/35/fs,
  upperdir=snapshots/84/fs, ...
)
```
lowerdir가 1개다.

ocr-llm 컨테이너:
```
overlay on .../rootfs type overlay (
  lowerdir=1645/fs:1644/fs:1643/fs:...:403/fs,
  upperdir=snapshots/1646/fs, ...
)
```
**lowerdir가 약 50개**였다.

LLM 모델 서버 이미지는 Ubuntu 기반에 CUDA 툴킷, cuDNN, Python, 모델 관련 의존성이 겹겹이 쌓여 레이어 수가 많다.
레이어가 많을수록 overlay 마운트 시 커널이 생성하는 dentry/inode 메타데이터도 비례해서 늘어난다.

### 컨테이너 수

GPU 노드에서 실행 중인 active task는 29개였다.
ocr-llm 외에도 calico, csi-cinder, neuvector, argo-redis, nvidia-device-plugin, metrics-server 등 시스템 pod가 여럿 올라가 있었다.
각각이 shim task 디렉터리와 overlay 마운트 포인트를 `/run`에 만든다.

application 노드는 이미지 레이어가 적고(Java JAR 기반으로 3\~7개), tmpfs 크기 대비 여유가 충분했다.
GPU 노드는 50레이어짜리 LLM 이미지 + 29개 task 조합이 8.9G를 전부 소진한 것이다.

## 진단 과정

### 어떤 노드인지 특정

```bash
kubectl describe pod ocr-api-deployment-xxx -n ocr
# Node: ocr-real-gpu-llm-f2038b41-node-0
```

### 노드 디스크 vs tmpfs 분리 확인

```bash
$ df -h /run
tmpfs  8.9G  8.9G  0  100%  /run

$ df -h /
/dev/vda1  485G  78G  408G  16%  /
```

### /run 안에서 뭐가 큰지 확인

```bash
# 같은 파일시스템만 집계 (-x 옵션)
$ sudo du -sx /run/containerd/
9266636  /run/containerd/

# overlay 마운트를 따라가면 50G로 뻥튀기됨 (실제 tmpfs 사용량 아님)
$ sudo du -sh /run/containerd/
50G  /run/containerd/
```

`du -sx`의 `-x` 옵션이 중요하다.
이 옵션 없이 `du -sh`를 하면 overlay 마운트 포인트를 따라가면서 `/var/lib/containerd/`의 이미지 데이터까지 합산해 50G로 나온다.
실제 tmpfs 사용량은 9.27G다.

### orphan task 식별

```bash
# 실행 중인 task 목록
$ sudo ctr -n k8s.io tasks ls | wc -l
29

# task 디렉터리 수
$ sudo ls /run/containerd/io.containerd.runtime.v2.task/k8s.io/ | wc -l
39
```

29개는 active, 10개는 종료된 컨테이너의 shim이 정리되지 않고 남은 orphan이었다.
다만 orphan은 각 4KB로 공간 영향은 미미했다.

## 해결

### 즉시 조치 — tmpfs 크기 확장

```bash
sudo mount -o remount,size=16G /run
```

이 한 줄로 `/run` tmpfs가 8.9G에서 16G로 확장되었다.
기존 데이터는 그대로 유지되면서 7.2G 여유 공간이 생겼다.

```bash
$ df -h /run
tmpfs  16G  8.9G  7.2G  56%  /run
```

확장 후 ContainerCreating으로 멈춰있던 pod들(metrics-server, argo-redis-ha-haproxy)이 자동으로 정상 기동됐고, ocr-api pod도 GPU 노드에서 정상 생성되었다.

GPU 노드 2대 모두 동일한 증상이었고, 양쪽 다 같은 조치로 해결했다.

### 영구 적용 — /etc/fstab

`mount -o remount`는 런타임 변경이라 **재부팅하면 원래 크기로 돌아간다**.
영구 적용하려면 `/etc/fstab`에 한 줄을 추가한다.

```bash
echo 'tmpfs /run tmpfs defaults,size=16G 0 0' | sudo tee -a /etc/fstab
```

tmpfs는 "최대 허용량"이지 "즉시 할당"이 아니다.
16G로 설정해도 실제 RAM 사용은 현재 사용량(9G)에 비례하므로, 90G RAM 노드에서 16G tmpfs는 메모리 압박 없이 안전하다.

### nodeAffinity 이슈

진단 과정에서 하나 더 발견한 것이 있다.
ocr-api deployment의 `nodeAffinity`에 `application`과 `gpu-llm` 모두 포함되어 있었다.

```yaml
nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
    - matchExpressions:
      - key: magnum.openstack.org/nodegroup
        operator: In
        values:
        - application
        - gpu-llm    # GPU 노드에도 스케줄 가능
```

여기에 `podAntiAffinity`(같은 hostname에 같은 app 중복 불가)가 걸려있어서, application 노드 2대가 점유되면 나머지 pod는 GPU 노드로 밀렸다.
이건 의도된 설정이었지만, GPU 노드의 tmpfs가 부족한 상태에서는 문제가 됐다.

## 추가 발견: nvidia-container-runtime 과도한 로깅

조사 과정에서 NVIDIA Container Toolkit의 알려진 버그([Issue #511](https://github.com/NVIDIA/nvidia-container-toolkit/issues/511))를 발견했다.
exec liveness/readiness probe를 실행할 때 nvidia-container-runtime이 과도한 로그를 `/run/containerd/.../log.json`에 기록하여 tmpfs를 채우는 문제가 보고되어 있다.

이 클러스터에서 관찰된 `nvidia-container-runtime did not terminate successfully: exit status 255` 에러와 정확히 일치하는 증상이다.
[PR #560](https://github.com/NVIDIA/nvidia-container-toolkit/pull/560)에서 로깅 verbosity를 줄이는 수정이 반영되었으므로, 후속으로 toolkit 버전 업그레이드 또는 로그 출력 경로를 디스크(`/var/log/`)로 변경하는 방안을 검토할 예정이다.

## 정리

| 항목 | 값 |
|---|---|
| 근본 원인 | GPU 노드의 `/run` tmpfs(8.9G)가 containerd runtime 메타데이터로 포화 |
| 왜 GPU만 | LLM 이미지의 overlay 레이어 약 50개 + 29개 active task → 커널 메타데이터 누적 |
| 해결 | `mount -o remount,size=16G /run` |
| 영구 적용 | `/etc/fstab` 또는 NKS 노드 설정 변경 필요 |

이번 이슈에서 배운 건 `df -h`로 루트 디스크만 보면 안 된다는 것이다.
`/run` 같은 tmpfs는 별도 파일시스템이라 루트와 독립적으로 꽉 찰 수 있고, `du`도 `-x` 옵션 없이 쓰면 overlay 마운트를 따라가면서 엉뚱한 숫자를 보여준다.

containerd의 shim v2 아키텍처가 `/run`에 task 디렉터리와 overlay 마운트 포인트를 저장하는 구조를 알고 나니, GPU 노드처럼 이미지 레이어가 많은 환경에서 왜 tmpfs 기본 크기가 부족해지는지 이해할 수 있었다.

## 참고 자료

- [Tmpfs — Linux Kernel documentation](https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html)
- [containerd Runtime V2 문서](https://containerd.io/docs/main/runtime-v2/)
- [Runtime v2 and Shim Architecture — DeepWiki](https://deepwiki.com/containerd/containerd/5.1-runtime-v2-and-shim-architecture)
- [Overlay Filesystem — Linux Kernel documentation](https://docs.kernel.org/filesystems/overlayfs.html)
- [Understanding OCI Runtimes: containerd, Shims, and the Container Lifecycle](https://dev.to/jimjunior/understanding-oci-runtimes-containerd-shims-and-the-container-lifecycle-2632)
- [CRI & containerd Explained — Medium](https://medium.com/@kikuchidaisuke.zr/cri-containerd-explained-29ad5c598f8b)
- [NVIDIA Container Toolkit Issue #511 — Excessive runtime logging](https://github.com/NVIDIA/nvidia-container-toolkit/issues/511)
- [NVIDIA Container Toolkit PR #560 — Reduce logging verbosity](https://github.com/NVIDIA/nvidia-container-toolkit/pull/560)
