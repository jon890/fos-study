# GPU·CUDA·MPS 기초 — 자바 백엔드 개발자가 처음 만나는 그림

자바로 백엔드만 짤 때는 컴퓨팅 자원이 단순했다. CPU 코어 수, JVM heap (`-Xmx`), 시스템 RAM. 워크로드가 커지면 인스턴스를 늘리거나 스레드를 늘리는 게 답이었다.

ML 서비스를 다루기 시작하면 그림이 한 층 더 생긴다. **GPU** 라는 별도 컴퓨팅 장치, 그 안의 **VRAM** 이라는 별도 메모리, 그리고 그것들을 다루는 **CUDA·cuDNN·MPS** 같은 용어들. 자바 입장에서는 갑자기 "JVM 옆에 별도의 가상 머신이 하나 더 붙는 것 같다" 는 인상을 받는다.

이 글은 자바 백엔드 개발자가 ML 서비스를 운영·분석할 때 알아둬야 할 GPU 관련 기초 개념을 정리한다. 우리 프로젝트의 운영 환경 (Tesla T4 1장, MPS=OFF, Mac 로컬은 Apple MPS) 를 예시로 쓴다.

## GPU 는 CPU 와 어떻게 다른가

CPU 는 소수의 강력한 코어로 복잡한 분기·예측·캐싱을 한다. 자바 백엔드 코드는 대부분 분기와 객체 조작이라 CPU 모델에 잘 맞는다.

GPU 는 수천 개의 단순한 코어로 같은 연산을 데이터 다발에 일괄 수행한다. **행렬 곱·합성곱** 같은 단순 반복 연산에서 CPU 대비 100배 이상의 처리량을 낸다. ML 모델 추론·학습이 사실상 거대한 행렬 곱이라 GPU 의 강점과 정확히 일치한다.

자바로 비유하면 CPU 는 "복잡한 비즈니스 로직 한 트랜잭션", GPU 는 "Hadoop/Spark 가 데이터를 일괄 처리하듯 SIMD (Single Instruction Multiple Data) 방식의 병렬 처리" 라고 보면 가깝다.

## CUDA — NVIDIA GPU 의 프로그래밍 인터페이스

CUDA 는 NVIDIA 가 만든 GPU 컴퓨팅 플랫폼 + API 다. 자바의 JVM 자리에 NVIDIA 의 CUDA 런타임이 들어가고, PyTorch·TensorFlow 같은 라이브러리가 그 위에서 동작한다.

| 자바 | CUDA |
|---|---|
| JDK / OpenJDK | NVIDIA driver |
| JVM | CUDA Runtime |
| 자바 라이브러리 (예: Netty) | cuDNN, cuBLAS, cuFFT |
| 애플리케이션 (Spring Boot) | PyTorch, TensorFlow |

세 가지 버전이 모두 호환되어야 동작한다. 우리 프로젝트의 Dockerfile 첫 줄 `FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04` 가 그 의미다.

- `cuda:11.8.0` — CUDA Runtime 버전. PyTorch 빌드가 요구하는 버전과 맞아야 한다.
- `cudnn8` — cuDNN 버전. 딥러닝 연산 (특히 합성곱) 가속 라이브러리.
- `ubuntu22.04` — OS 베이스.

호스트의 NVIDIA driver 가 컨테이너 안의 CUDA Runtime 보다 같거나 높아야 하고, PyTorch 가 빌드된 CUDA 버전과도 맞아야 한다. 자바에서 JDK 호환성 매트릭스를 신경 쓰는 것과 비슷하지만 한 단계 더 깐깐하다.

## VRAM — GPU 전용 메모리

VRAM 은 GPU 카드 위에 붙은 메모리다. **시스템 RAM 과 물리적으로 분리**된다. 우리 운영 환경의 Tesla T4 는 VRAM 16GB (실측 가용 15GB). 호스트의 시스템 RAM 32GB 와는 별도.

자바 사고로 가장 헷갈리는 부분이 이거다. JVM heap 은 시스템 RAM 의 한 조각이지만, GPU 의 VRAM 은 완전히 별도의 메모리 풀. 데이터를 GPU 에서 처리하려면 **시스템 RAM → VRAM 으로 명시적 복사**해야 한다.

```python
import torch

x = torch.randn(1000, 1000)        # 시스템 RAM 에 있음 (CPU 텐서)
x_gpu = x.to("cuda")                # VRAM 으로 복사 (GPU 텐서)
y = x_gpu @ x_gpu                   # GPU 에서 행렬 곱
result = y.to("cpu")                # 결과를 시스템 RAM 으로 가져옴
```

이 `to(...)` 호출이 PCIe 버스를 통한 메모리 전송이다. 비용이 있어서 잦은 transfer 는 성능 손해. 모델을 한 번 GPU 에 올리고 그 안에서 가능한 한 끝까지 계산하는 패턴이 표준.

## OOM 의 두 가지 의미

자바에서 `OutOfMemoryError` 는 JVM heap 이 꽉 찼다는 뜻이다. ML 서비스에서는 두 가지가 따로 있다.

- **시스템 RAM OOM** — 자바 OOM 과 동일. 프로세스가 죽거나 OS 가 OOM killer 로 죽인다.
- **GPU OOM** — VRAM 부족. PyTorch 가 `RuntimeError: CUDA out of memory` 를 던진다. JVM GC 같은 자동 회수가 없어서 손으로 정리해야 한다.

JVM 에서는 GC 가 알아서 회수해주지만 PyTorch 는 더 명시적이다. `del tensor` 또는 `torch.cuda.empty_cache()` 같은 호출이 필요할 수 있다. 우리 프로젝트 코드의 `clear_cuda_memory()` 함수가 그 역할.

```python
def clear_cuda_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
```

자바의 `System.gc()` 와 비슷한 위치인데, ML 워크로드에서는 호출 빈도가 훨씬 잦다.

## nvidia-smi — GPU 의 jstat·jmap

자바에서 JVM 상태를 보려고 `jstat`, `jmap`, `jstack`, JConsole 을 쓴다. GPU 는 `nvidia-smi` 한 명령으로 거의 모든 게 보인다.

```bash
$ nvidia-smi
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 470.57.02   Driver Version: 470.57.02   CUDA Version: 11.4       |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  Tesla T4            Off  | 00000000:00:1B.0 Off |                    0 |
| N/A   48C    P0    27W /  70W |   4580MiB / 15360MiB |     64%      Default |
+-------------------------------+----------------------+----------------------+
```

핵심 지표:
- **Memory-Usage** — VRAM 사용량 / 총 VRAM. 자바 heap 사용량과 같은 위치.
- **GPU-Util** — GPU 코어 가동률. 자바 CPU 사용률과 같은 의미.
- **Temp / Pwr** — 온도·전력. 자바 백엔드에서는 신경 안 쓰던 부분.
- **Compute M.** — Default / Exclusive_Process / Exclusive_Thread 등 동작 모드.

스크립트로 뽑을 때는 `--query-gpu` 옵션이 편하다.

```bash
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv
# memory.used [MiB], memory.total [MiB], utilization.gpu [%]
# 4580, 15360, 64
```

운영 중인 어느 PID 가 VRAM 을 점유하는지 보려면:

```bash
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
# pid, used_gpu_memory [MiB]
# 626719, 998 MiB
# 703689, 690 MiB
```

자바에서 `jps` 로 프로세스 확인하는 것과 같은 자리.

## MPS — 같은 약어, 다른 두 가지 의미

`MPS` 라는 약어가 두 가지 다른 것을 가리킬 수 있다. 처음에 헷갈렸던 부분.

### NVIDIA MPS (Multi-Process Service)

여러 프로세스가 같은 GPU 를 효율적으로 공유하기 위한 NVIDIA 의 서비스. 기본 모드에서는 각 프로세스가 GPU 에 접근할 때 자체 CUDA context 를 만든다 (~300-600MB VRAM 소비 + 컨텍스트 전환 비용). MPS 를 켜면 여러 프로세스가 같은 컨텍스트를 공유해 효율이 올라간다.

우리 프로젝트는 단일 T4 에 워커 3개 (KR=2, JA=1) 를 띄우는데, 이런 multi-process GPU 워크로드의 전형. `ENABLE_CUDA_MPS=true` 옵션으로 켤 수 있지만 현재 운영은 `MPS=OFF`. 다음 글에서 multi-process GPU 패턴을 자세히 다룬다.

### Apple MPS (Metal Performance Shaders)

Apple Silicon (M1/M2/M3) 에서 GPU 가속을 제공하는 Apple 의 프레임워크. NVIDIA CUDA 와 완전히 별개의 스택.

```python
import torch
print(torch.backends.mps.is_available())   # True on Apple Silicon
x = torch.randn(1000, 1000).to("mps")      # Apple GPU 사용
```

Mac M-series 에서 PyTorch 가 자동으로 Apple GPU 를 활용한다. 우리가 로컬 개발 환경을 Mac 에 세팅했을 때 `torch.backends.mps.is_available()` 가 True 로 나온 게 이 의미. 운영 환경의 NVIDIA T4 와는 다른 GPU 지만 PyTorch 코드는 거의 그대로 돌아간다 (성능 차이는 큼).

같은 약어가 같은 PyTorch 코드 안에 등장할 수 있다는 점 — `torch.cuda.*` 호출이 안 통할 때 `torch.backends.mps.*` 로 분기하는 패턴을 자주 본다.

## JVM heap 과의 비교 — 명시적 자원 관리

자바 백엔드를 운영할 때 가장 신경 쓰는 게 JVM heap 튜닝 (`-Xmx`, `-Xms`, GC 알고리즘 선택) 이었다. GPU 워크로드는 그와 비슷하지만 차이가 있다.

| 항목 | 자바 (JVM heap) | Python (VRAM) |
|---|---|---|
| 자동 회수 | GC | 없음 (수동 `del`, `empty_cache`) |
| 최대 크기 지정 | `-Xmx2g` | 거의 없음 (PyTorch 가 자유 할당) |
| 모니터링 | jstat, JMX | nvidia-smi |
| OOM 동작 | OutOfMemoryError → 보통 프로세스 죽음 | RuntimeError → catch 가능, 다음 작업 계속 |
| 멀티 프로세스 공유 | OS 가 관리 | 명시적 (CUDA context 또는 NVIDIA MPS) |

큰 차이 한 가지: 자바는 JVM 안에서 모든 게 일어나서 OOM 이 나면 프로세스가 끝나지만, GPU OOM 은 try/except 로 잡고 텐서를 정리한 뒤 다음 요청을 처리할 수 있다. 우리가 분석한 코드의 `clear_cuda_memory(force=True)` 와 RAM threshold 기반 worker 재시작 패턴이 이 모델 위에 서 있다.

## 정리

자바 백엔드에서 ML 서비스로 넘어올 때 알아둘 한 줄.

> CPU + 시스템 RAM 만 있던 그림에 GPU + VRAM 이라는 별도 컴퓨팅 평면이 추가된다. nvidia-smi 가 jstat 자리, `.to("cuda")` 가 데이터 전송, `clear_cuda_memory()` 가 수동 GC.

이걸 머릿속에 두면 다음 글들 — PyTorch 모델 로딩 비용, multi-process GPU 워커 패턴 — 이 자연스럽게 이어진다.

## 참고

- [NVIDIA CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [PyTorch CUDA Semantics](https://pytorch.org/docs/stable/notes/cuda.html)
- [PyTorch MPS Backend (Apple Silicon)](https://pytorch.org/docs/stable/notes/mps.html)
- [NVIDIA Multi-Process Service](https://docs.nvidia.com/deploy/mps/index.html)
- [nvidia-smi documentation](https://developer.nvidia.com/nvidia-system-management-interface)
