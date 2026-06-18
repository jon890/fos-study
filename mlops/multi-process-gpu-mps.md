# 한 GPU 를 여러 프로세스가 나눠 쓰기 — Time-Slicing 과 MPS

[GPU·CUDA·MPS 기초](./java-to-python-gpu-cuda-mps.md) 에서 MPS 라는 약어가 NVIDIA 와 Apple 두 가지를 가리킨다는 것까지 정리했다. 그 글 끝에 "multi-process GPU 패턴은 다음 글에서" 라고 미뤄둔 부분을 이어 쓴다.

질문은 단순하다. **GPU 는 한 장인데, 그 위에서 추론하는 프로세스가 여러 개면 GPU 를 어떻게 나눠 쓰는가.**

여러 워커 프로세스가 각자 추론을 하는 서버를 떠올리면 된다. 메인 프로세스가 요청을 받고, 실제 모델 추론은 자식 워커 프로세스 풀에 넘긴다. 워커가 3개면 GPU 하나에 추론 프로세스가 3개 붙는다. 이때 GPU 를 나눠 쓰는 방식이 곧 성능과 안정성을 가른다.

## 기본 동작 — Time-Slicing

아무 설정도 안 하면 GPU 는 **time-slicing** 으로 동작한다. 여러 프로세스가 보낸 커널(GPU 연산 단위)을 **순서대로 돌아가며** 실행한다. 한 순간엔 한 프로세스의 커널만 GPU 전체를 쓰고, 시간이 지나면 다음 프로세스로 넘어간다. 시분할 방식의 OS 스케줄러가 CPU 를 프로세스에 번갈아 주는 것과 같은 그림이다.

이걸 **temporal multiplexing**(시간 다중화)이라 부른다. GPU 한 장에 여러 프로세스를 올릴 수 있다는 점에서 밀도는 올라간다. 하지만 두 가지 비용이 따라온다.

- **컨텍스트 전환 오버헤드** — 프로세스를 바꿀 때마다 GPU 가 한 프로세스의 CUDA 컨텍스트를 내리고 다음 것을 올린다. 이 전환이 공짜가 아니다.
- **GPU 유휴** — 한 프로세스의 커널이 GPU 의 일부 연산 유닛만 써도, 그 시간 슬롯 동안 나머지 유닛은 논다. 다른 프로세스가 옆에서 같이 돌 수 없기 때문이다.

특히 짧고 자잘한 커널이 많은 워크로드일수록 전환 비용과 유휴가 누적돼 GPU 활용도가 떨어진다. 추론 서비스는 요청마다 작은 커널이 쏟아지는 패턴이라 이 약점에 정확히 걸린다.

## MPS — 공간으로 나눠 쓰기

**MPS**(Multi-Process Service)는 같은 문제를 시간이 아니라 **공간**으로 푼다.

GPU 안에는 **SM**(Streaming Multiprocessor)이라는 연산 유닛이 수십 개 들어 있다. time-slicing 이 "한 순간엔 한 프로세스가 SM 전부를 쓴다" 면, MPS 는 **여러 프로세스의 커널이 SM 을 나눠서 동시에 실행**되게 한다. 한 프로세스가 GPU 의 절반만 쓰면, 나머지 절반에서 다른 프로세스 커널이 같이 돈다. 이걸 **spatial multiplexing**(공간 다중화)이라 부른다.

핵심은 **여러 프로세스의 커널을 하나의 CUDA 컨텍스트로 합쳐** GPU 에 제출한다는 데 있다. 컨텍스트 전환 없이 커널들이 동시에 인터리빙되므로, time-slicing 의 전환 오버헤드와 유휴가 줄어든다. 프로세스를 늘려도 GPU 가 놀지 않고 채워진다.

### MPS control 데몬의 역할

MPS 를 켜면 **MPS control 데몬**(`nvidia-cuda-mps-control`)이 뜬다. 이 데몬이 MPS 서버를 관리하고, 각 클라이언트 프로세스가 보낸 커널을 GPU 에 스케줄링하는 중개자 역할을 한다. 클라이언트(워커 프로세스)들은 GPU 에 직접 컨텍스트를 만들지 않고, 이 MPS 서버를 통해 공유 컨텍스트로 커널을 흘려보낸다.

그래서 MPS 를 쓰는 컨테이너는 보통 앱을 띄우기 전에 이 데몬을 먼저 기동하고, 종료 시 정리하는 절차를 둔다. 앱 프로세스 하나만 띄우면 끝이 아니라, GPU 공유를 중개하는 데몬이 함께 살아야 한다.

### 활용도를 조절하는 손잡이

MPS 서버는 한 클라이언트가 쓸 수 있는 자원에 상한을 걸 수 있다. 대표적으로 **active thread percentage** 로 "각 클라이언트는 GPU 스레드의 최대 N% 까지" 를 지정한다. 예를 들어 50% 로 두면 한 프로세스가 GPU 를 독식하지 못하고 절반 안에서만 돈다. 최신 아키텍처에서는 SM 을 **chunk** 단위(Hopper 기준 8 SM)로 떼어 정적으로 나누는 모드도 있다. 워커 수와 워크로드에 맞춰 분할 정책을 조절하는 셈이다.

## 공짜는 아니다 — 격리가 약해진다

MPS 가 좋아 보이지만 트레이드오프가 분명하다. 가장 중요한 건 **에러 격리(fault isolation)가 약하다**는 점이다.

MPS 는 여러 클라이언트를 **하나의 공유 CUDA 컨텍스트** 안에서 다중화한다. 그래서 한 클라이언트가 치명적 GPU 폴트를 내면, 그 공유 컨텍스트가 무너지면서 **같이 돌던 다른 클라이언트들도 함께 죽을 수 있다.** 누가 사고를 냈는지조차 다른 클라이언트엔 알려지지 않는다. Volta 이후 아키텍처가 클라이언트별 GPU 주소 공간을 분리해 **메모리 침범**은 막아주지만, 이건 메모리 보호일 뿐 **하드웨어 수준의 폴트 격리는 아니다.**

정리하면 이렇다.

| 항목 | Time-Slicing | MPS |
|---|---|---|
| 다중화 방식 | 시간 (순차 실행) | 공간 (동시 실행) |
| GPU 활용도 | 전환 오버헤드·유휴로 낮음 | SM 공유로 높음 |
| 컨텍스트 | 프로세스마다 별도 | 공유 컨텍스트 |
| 에러 격리 | 프로세스 독립 | 약함 (한 폴트가 전부 전파 가능) |
| 추가 구성 | 없음 | MPS control 데몬 필요 |

## 그래서 언제 켜는가

MPS 는 **추론 워크로드의 GPU 활용을 끌어올리고 싶을 때** 잘 맞는다. 여러 프로세스가 GPU 를 잘게 나눠 쓰는데 각자는 GPU 를 다 못 채우는 상황 — 동시성을 높여 처리량을 올리는 게 목적이라면 후보다.

반대로 **강한 격리가 중요한 서비스에는 신중해야 한다.** 한 워커의 GPU 폴트가 다른 워커까지 끌고 내려갈 수 있으므로, 워커 하나가 죽어도 나머지는 살아야 하는 안정성 요구가 크다면 MPS 의 약한 격리가 부담이 된다. 게다가 데몬 기동·종료라는 운영 절차가 하나 더 늘고, 간섭·메모리·폴트 거동을 워크로드별로 직접 검증해야 한다.

실제로 한 GPU 에 추론 워커 몇 개를 띄우는 서비스에서 MPS 를 **환경변수 스위치로만 열어두고 기본은 끈 채 운영**하는 선택을 본 적이 있다. 워커 수가 많지 않고 단일 GPU 메모리도 빠듯하면, MPS 가 주는 활용도 이득보다 약한 격리와 운영 복잡도가 더 크게 느껴지기 때문이다. 옵션은 코드에 남겨두되 기본값은 보수적으로 가는, 합리적인 절충이다.

GPU 공유에는 이 둘 말고 **MIG**(Multi-Instance GPU)라는 세 번째 길도 있다. 하드웨어 수준으로 GPU 를 물리적으로 쪼개 완전히 격리하는 방식인데, 이건 지원 아키텍처(A100 등)가 따로 있어 다음 기회에 따로 다룬다.

## 한 줄 정리

> Time-slicing 은 GPU 를 시간으로 돌려 쓰고(전환 비용·유휴), MPS 는 SM 을 공간으로 나눠 동시에 쓴다(활용도↑, 격리↓). 활용도를 살 것인가 격리를 지킬 것인가의 문제다.

## 참고

- [When to Use MPS — NVIDIA 공식 문서](https://docs.nvidia.com/deploy/mps/when-to-use-mps.html)
- [CUDA Multi-Process Service Overview (NVIDIA PDF)](https://docs.nvidia.com/deploy/pdf/CUDA_Multi_Process_Service_Overview.pdf)
- [Improving GPU Utilization in Kubernetes — NVIDIA Technical Blog](https://developer.nvidia.com/blog/improving-gpu-utilization-in-kubernetes/)
- [Kubernetes GPU Sharing: Time-Slicing, MPS, and MIG](https://scaleops.com/blog/kubernetes-gpu-sharing/)
- [Demystifying NVIDIA MPS (Medium)](https://sagar-parmar.medium.com/demystifying-nvidia-mps-how-multi-process-service-improves-gpu-sharing-and-performance-9f633878318a)
