# GPU 컨테이너의 CUDA 버전 호환성 — nvidia-smi부터 이미지 다이어트까지

GPU로 모델을 추론하는 문서 파싱 서비스의 컨테이너 이미지가 압축 기준 10GB, 디스크에 풀면 30GB까지 부푼 걸 마주했다.
줄여보려고 들여다보다가, 정작 내가 GPU 컨테이너의 버전 체계를 제대로 모른다는 걸 알았다.
`nvidia-smi`가 찍어주는 두 개의 버전 숫자가 무슨 뜻인지, 왜 컨테이너 안 CUDA를 마음대로 못 올리는지부터 막혔다.

이 글은 그때 정리한 내용이다.
드라이버와 CUDA 런타임과 cuDNN이 어떻게 층을 이루는지, 컨테이너가 그 사이에서 어떻게 끼는지, 그리고 그 이해가 이미지 다이어트로 어떻게 이어졌는지를 적는다.

## nvidia-smi가 찍는 두 개의 버전

GPU가 붙은 호스트에서 `nvidia-smi`를 치면 맨 윗줄에 이런 게 나온다.

```
NVIDIA-SMI 535.154.05   Driver Version: 535.154.05   CUDA Version: 12.2
...
  0  Tesla T4   On  | 00000000:00:05.0 Off |  3944MiB / 15360MiB | 0% Default
```

처음엔 `Driver Version`과 `CUDA Version`이 둘 다 떠서 헷갈렸다.
"드라이버는 535인데 CUDA는 12.2를 설치했다는 건가?" 싶었는데, 아니었다.

여기서 `CUDA Version: 12.2`는 설치된 CUDA Toolkit 버전이 아니다.
이 드라이버가 지원하는 가장 높은 CUDA 버전이다.
정확히는 드라이버에 같이 들어 있는 CUDA Driver API의 호환 상한이다.
실제로 시스템에 어떤 CUDA Toolkit이 깔렸는지는 이 줄이 말해주지 않는다.

그래서 같은 머신에서 `nvcc --version`을 치면 다른 숫자가 나올 수 있다.
`nvcc`는 실제로 설치된 Toolkit 버전, 즉 Runtime API 쪽을 보고한다.
정리하면 이렇다.

- `nvidia-smi`의 CUDA 버전 = 드라이버가 받아줄 수 있는 최대 CUDA (호환성 상한)
- `nvcc`의 CUDA 버전 = 실제로 깔린 Toolkit (컴파일에 쓰이는 버전)

나머지 줄도 읽어두면 운영에서 유용하다.

- `Tesla T4` — GPU 모델. Turing 세대, Compute Capability 7.5
- `3944MiB / 15360MiB` — 메모리 사용량. T4는 16GB 카드라 약 15GB가 가용
- 아래 Processes 표 — 지금 GPU 메모리를 잡고 있는 프로세스들. 워커가 몇 개 떠 있는지, 각자 얼마를 쓰는지가 보인다

위 출력에서 python 프로세스 다섯 개가 GPU를 나눠 쓰고 있었는데, 이게 나중에 중요한 단서가 된다.

## 드라이버, CUDA 런타임, cuDNN — 누가 어디에 사는가

버전 호환성을 이해하려면 세 가지가 각각 어디에 사는지를 먼저 그려야 한다.

- NVIDIA 드라이버는 호스트에 산다. 커널 모듈과 `libcuda.so`로, GPU 하드웨어를 직접 제어한다.
- CUDA 런타임(`cudart`, `cublas`, `cufft` 등)은 애플리케이션이나 컨테이너 안에 산다. 드라이버 위에서 돈다.
- cuDNN은 딥러닝 가속 라이브러리로, 역시 앱/컨테이너 쪽에 산다. PyTorch 같은 프레임워크가 자기 버전을 끼고 다닌다.

핵심 규칙은 하나다.
드라이버 쪽 CUDA 버전이 런타임 쪽 CUDA 버전보다 같거나 높아야 한다.
즉 호스트 드라이버가 535(CUDA 12.2 상한)면, 그 위에서 도는 CUDA 런타임은 12.2 이하여야 안전하다는 게 기본 원칙이다.

컨테이너를 쓰면 이 그림이 한 겹 더 접힌다.
컨테이너 안에는 CUDA 런타임만 들어 있고 드라이버는 없다.
대신 `nvidia-container-toolkit`이 호스트 드라이버를 컨테이너 안으로 연결해준다.
그러니까 컨테이너가 GPU를 쓴다는 건, 컨테이너 자기 런타임 + 호스트가 빌려준 드라이버의 조합으로 도는 것이다.

이 구조 때문에 컨테이너 안 CUDA를 무작정 최신으로 올릴 수가 없다.
호스트 드라이버가 그만큼 못 받아주면 GPU 초기화 단계에서 깨진다.

## minor version compatibility — 규칙에 난 구멍

기본 원칙이 "드라이버 ≥ 런타임"이라면, 드라이버 535(12.2 상한)에서 CUDA 12.6으로 빌드한 라이브러리는 못 도는 게 맞아야 한다.
그런데 현실은 더 너그럽다.

CUDA 11부터 도입된 minor version compatibility 덕분이다.
같은 메이저 버전(12.x) 안에서 컴파일한 애플리케이션은, 그 메이저의 최소 드라이버만 있으면 돈다.
NVIDIA가 공식적으로 정한 메이저별 최소 드라이버는 이렇다.

- CUDA 11.x — 드라이버 450 이상
- CUDA 12.x — 드라이버 525 이상
- CUDA 13.x — 드라이버 580 이상

그러니까 CUDA 12.6으로 빌드한 라이브러리도, 호스트 드라이버가 525 이상이면 minor compat로 돈다.
535는 525보다 높으니 12.6 런타임이 돌 수 있다는 뜻이다.
단 NVIDIA 문서가 못박는 단서가 있다. 일부 기능은 toolkit과 드라이버 양쪽에 걸쳐 있어서, 호환 모드에서는 제한된 기능으로만 동작할 수 있다.

여기서 한 가지를 꼭 구분해야 한다. 나도 이걸 섞어서 한참 헤맸다.

- minor compat가 보장하는 최소 드라이버: CUDA 12.x는 525면 동작 (제한 기능)
- 어떤 CUDA를 네이티브로 완전 지원하는 드라이버: CUDA 12.6은 560.28 이상

이 둘이 다르다.
12.6을 525에서 돌리는 건 "호환 모드로 됨"이고, 12.6을 온전히 받는 건 560이다.
이 구분이 다음 함정으로 이어진다.

## 컨테이너가 시작도 못 하고 거부당하는 이유

CUDA 12.6 베이스 이미지(`nvidia/cuda:12.6.0-runtime` 류)를 535 드라이버 호스트에서 띄우면, minor compat 이론상 될 것 같은데 컨테이너가 아예 시작을 거부한다.

```
nvidia-container-cli: requirement error: unsatisfied condition:
cuda>=12.6, please update your driver to a newer version,
or use an earlier cuda container
```

이건 CUDA 런타임이 실제로 못 돌아서 나는 에러가 아니다.
컨테이너가 뜨기도 전에 `nvidia-container-toolkit`이 막은 것이다.

NVIDIA가 배포하는 CUDA 베이스 이미지에는 `NVIDIA_REQUIRE_CUDA`라는 환경 라벨이 박혀 있다.
`nvidia/cuda:12.6` 이미지면 `cuda>=12.6` 같은 조건이 들어 있다.
컨테이너 런타임이 이걸 호스트 드라이버 능력(여기선 12.2)과 비교해서, 조건을 못 채우면 GPU 연결 자체를 거부한다.

그래서 minor compat가 "런타임 라이브러리는 돌 수 있다"고 해도, 베이스 이미지의 REQUIRE 체크는 별개의 관문이다.
이 관문은 드라이버가 12.6을 네이티브로 받을 때(560+)만 통과한다.

정리하면 같은 "CUDA 12.6"이라도 경로에 따라 운명이 갈린다.

- 베이스 이미지의 시스템 CUDA를 12.6으로 = REQUIRE 체크에 걸림 = 드라이버 560 필요
- pip 휠이 끼고 들어온 CUDA 12.6 = REQUIRE 라벨 없음 = minor compat로 525+에서 동작

이게 실측에서 그대로 드러났다.
앞의 `nvidia-smi`에서 python 프로세스 다섯 개가 GPU를 잘 쓰고 있었는데, 그 컨테이너의 베이스는 CUDA 11.8이었고 그 위에 깔린 PyTorch는 CUDA 12.6 빌드였다.
베이스가 11.8이라 REQUIRE 라벨이 `cuda>=11.8`이고, PyTorch 휠에는 그런 라벨이 없으니, 12.6 런타임이 535 드라이버에서 minor compat로 멀쩡히 돌고 있던 것이다.

이 한 가지 관찰이 다이어트 방향을 정해줬다.
베이스 이미지의 CUDA를 올리는 건 드라이버를 묶지만(운영 모든 호스트의 드라이버 업그레이드라는 인프라 작업이 선행되어야 한다), 프레임워크가 끼고 오는 CUDA는 그 제약에서 비교적 자유롭다는 것.

GPU를 여러 프로세스로 나눠 쓰는 워커 풀 구성은 [Java 개발자가 본 Python 멀티프로세스 GPU 워커 풀](./java-to-python-multiprocess-gpu-worker-pool.md)에 따로 정리해두었다.

## 30GB는 어디서 왔나 — pull 없이 레이어를 뜯어보기

방향을 잡았으니 실제로 이미지를 뜯어봐야 했다.
그런데 문제의 이미지가 30GB다. 받아서 `docker history`로 보기엔 너무 무겁다.

다행히 Docker Registry HTTP API v2로 이미지를 받지 않고도 레이어 구성을 볼 수 있다.

- `GET /v2/<repo>/manifests/<tag>` — 레이어별 압축 크기 목록과 config blob 다이제스트
- `GET /v2/<repo>/blobs/<config-digest>` — 각 레이어를 만든 빌드 명령(history)

manifest의 레이어 크기와 config의 history를 순서대로 맞물리면, "어느 빌드 명령이 만든 레이어가 몇 MB인지"가 나온다.
받은 건 JSON 수십 KB뿐인데 30GB 이미지의 구조가 손에 잡혔다.

뜯어보니 거대화의 정체는 CUDA 라이브러리의 삼중 중복이었다.

- 베이스 이미지의 시스템 CUDA 11.8 + cudnn8
- PyTorch가 끌어온 CUDA 12.6 라이브러리 묶음 (nvidia-cudnn-cu12 등 십수 개)
- PaddlePaddle이 끌어온 CUDA 11.8 라이브러리

세 벌의 CUDA가 한 이미지에 쌓여 있었다.
게다가 PyTorch는 자기 CUDA 12.6 번들을 쓰니, 베이스 이미지가 품고 있는 cudnn8은 PyTorch 입장에서 죽은 무게였다.

## 다이어트 레버 — MLOps 관점에서 무엇을 먼저 자르나

레이어 분석이 끝나니 자를 곳의 우선순위가 정리됐다.
GPU 추론 이미지를 줄일 때 일반적으로 적용되는 레버들이다.

- 베이스 이미지를 최소화한다. `devel`이 아니라 `runtime` 계열을 쓰고, 프레임워크가 cudnn을 자기 번들로 들고 오면 베이스의 cudnn은 뺄 수 있는지 검증한다.
- 빌드 도구를 런타임에서 분리한다. 멀티스테이지 빌드로 컴파일러, 헤더, 빌드 캐시를 builder 스테이지에 가두고, 최종 이미지에는 실행에 필요한 것만 복사한다.
- 안 쓰는 의존성을 들어낸다. import가 한 번도 안 되는데 따라 들어온 패키지(특히 전이 의존성으로 무거운 것을 끌고 오는 패키지)를 찾아 제거한다.
- CUDA 버전을 통일한다. 같은 메이저 안에서 프레임워크들의 CUDA 버전을 맞추면 라이브러리 정합성이 올라간다. 다만 이미지 크기 절감 효과 자체는 생각보다 작을 수 있어서, 줄이는 효과와 정합성 효과를 분리해서 기대해야 한다.

여기서 MLOps 관점의 교훈이 하나 나온다.
"CUDA를 최신으로 올리면 더 좋아지겠지"라는 직관이 운영에서는 자주 빗나간다.
최신 CUDA로 통일하려면 호스트 드라이버를 그만큼 올려야 하고, 그건 GPU 노드 전체를 건드리는 인프라 작업이다.
모델 추론 컨테이너만 새로 빌드한다고 끝나지 않는다.
그래서 이미지 최적화는 "라이브러리를 어디까지 올릴 수 있나"가 아니라 "호스트 드라이버가 받쳐주는 선이 어디까지인가"에서 거꾸로 출발하는 게 맞다.

## 정리

GPU 컨테이너의 버전 문제는 결국 세 층의 관계로 환원된다.
호스트 드라이버, 컨테이너 안 CUDA 런타임, 그리고 그 둘을 잇는 nvidia-container-toolkit.

- `nvidia-smi`의 CUDA 버전은 설치된 Toolkit이 아니라 드라이버가 받아줄 수 있는 상한이다.
- 드라이버는 호스트에 있고 컨테이너가 빌려 쓴다. 그래서 컨테이너 CUDA는 드라이버 능력에 묶인다.
- minor version compatibility로 같은 메이저 안에서는 더 새 런타임도 돌지만, 베이스 이미지의 `NVIDIA_REQUIRE_CUDA` 관문은 별개라 네이티브 드라이버를 요구한다.
- 그래서 베이스 이미지 CUDA를 올리는 것과 프레임워크가 끼고 오는 CUDA는 제약의 무게가 다르다.

이미지를 줄이겠다고 시작했는데, 정작 가장 크게 배운 건 버전 호환성의 층위였다.
30GB를 어떻게 자를지보다, 왜 그렇게 쌓였고 무엇은 못 건드리는지를 아는 게 먼저였다.

## 참고 링크

- [CUDA Compatibility — NVIDIA 공식 문서](https://docs.nvidia.com/deploy/cuda-compatibility/)
- [Minor Version Compatibility — NVIDIA](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)
- [NVIDIA Container Toolkit Troubleshooting](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html)
- [CUDA Compatibility — Lei Mao's Log Book](https://leimao.github.io/blog/CUDA-Compatibility/)
- [Docker Registry HTTP API V2](https://distribution.github.io/distribution/spec/api/)
