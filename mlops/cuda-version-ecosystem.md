# Python CUDA 버전 생태계 — nvidia-smi, nvcc, pip, conda가 다 다른 버전을 말하는 이유

PyTorch를 `pip install`로 깔았는데 시스템에 CUDA Toolkit을 따로 안 깔아도 GPU가 돌았다.
그러다 `nvidia-smi`는 CUDA 12.2라고 하고, `nvcc --version`은 아예 명령이 없다고 하고, `python -c "import torch; print(torch.version.cuda)"`는 12.6이라고 한다.
같은 머신에서 CUDA 버전이 세 가지로 갈렸다.

처음엔 환경이 꼬인 줄 알았는데, 알고 보니 셋 다 정상이고 각자 다른 걸 말하고 있었다.
이 글은 그 생태계를 정리한 것이다.
GPU 컨테이너에서의 드라이버 호환성은 [GPU 컨테이너의 CUDA 버전 호환성](./gpu-container-cuda-driver-compatibility.md)에 따로 적었고, 이 글은 로컬 Python 환경에서 CUDA가 어떻게 여러 층으로 쪼개지는지를 다룬다.

## CUDA에는 API가 두 개다

혼란의 뿌리는 CUDA가 하나가 아니라는 데 있다.
CUDA는 두 개의 API 층으로 나뉜다.

- Driver API — 드라이버에 들어 있는 저수준 API다. `libcuda.so`로 제공되고, NVIDIA 드라이버를 깔면 같이 들어온다. GPU에 직접 명령을 내리는 가장 아래층이다.
- Runtime API — 그 위에 얹히는 고수준 API다. `libcudart.so`로 제공되고, CUDA Toolkit이나 PyTorch 같은 라이브러리에 묶여 들어온다. 우리가 코드에서 쓰는 대부분의 CUDA 함수가 여기에 있다.

이 두 층이 별도로 버전을 가진다.
드라이버 쪽 CUDA 버전(Driver API)과 런타임 쪽 CUDA 버전(Runtime API)이 서로 다를 수 있고, 그게 정상이다.

기본 규칙은 하나다.
Driver API 버전이 Runtime API 버전보다 같거나 높아야 한다.
드라이버가 더 낮은 CUDA를 보면 못 돌린다.
반대로 드라이버가 더 높은 CUDA를 보는 건 괜찮다. 이게 forward compatibility다.

## nvidia-smi와 nvcc는 서로 다른 층을 본다

이제 두 명령이 왜 다른 숫자를 말하는지가 풀린다.

`nvidia-smi`는 드라이버와 함께 설치되고, Driver API 쪽 버전을 보고한다.
정확히는 이 드라이버가 받아줄 수 있는 가장 높은 CUDA 버전, 즉 호환 상한이다.
실제로 무엇이 설치됐는지가 아니라 무엇까지 받아줄 수 있는지를 말한다.

`nvcc`는 CUDA Toolkit과 함께 설치되고, Runtime API 쪽 버전을 보고한다.
실제로 시스템에 깔린 Toolkit 버전이다.
컴파일에 쓰이는 버전이라 이게 정확해야 빌드가 맞물린다.

그래서 둘이 다르면 이렇게 읽으면 된다.

- `nvidia-smi`가 12.2 = 이 드라이버는 CUDA 12.2까지 받아줄 수 있다
- `nvcc`가 11.8 = 시스템에 깔린 Toolkit은 11.8이다
- 11.8 ≤ 12.2 이므로 정상이다

`nvcc`가 아예 없다고 나오는 경우도 흔하다.
CUDA Toolkit을 시스템에 설치하지 않았다는 뜻인데, 뒤에서 보겠지만 PyTorch만 쓸 거라면 이게 오히려 정상이다.

## Python에서는 CUDA가 패키지로 따라온다

여기가 Python 생태계의 핵심이다.

`pip install torch`를 하면, PyTorch 휠은 자기가 쓸 CUDA 런타임 라이브러리를 의존성으로 같이 끌어온다.
요즘 PyTorch는 `nvidia-cuda-runtime-cu12`, `nvidia-cudnn-cu12`, `nvidia-cublas-cu12` 같은 패키지들을 딸려 설치한다.
이것들이 바로 Runtime API 쪽 라이브러리다.

중요한 건 이 패키지들이 런타임 라이브러리만 담고 있다는 점이다.
`libcudart.so`, `libcublas.so` 같은 실행용 `.so`는 들어 있지만, `nvcc` 같은 개발 도구는 없다.
그래서 시스템에 CUDA Toolkit을 안 깔아도 PyTorch가 GPU에서 도는 것이다.
PyTorch가 자기 런타임을 통째로 들고 다니고, 호스트에서는 드라이버(`libcuda.so`)만 빌려 쓴다.

이게 세 번째 버전의 정체다.

```python
import torch
print(torch.version.cuda)   # 예: 12.6 — PyTorch 휠이 번들한 CUDA 런타임 버전
```

`torch.version.cuda`는 시스템 Toolkit도 드라이버도 아니다.
PyTorch 휠 안에 묶여 들어온 CUDA 런타임 버전이다.
그래서 `nvidia-smi`(드라이버 상한)와도, `nvcc`(시스템 Toolkit)와도 다를 수 있다.

## conda와 pip, 그리고 full toolkit의 차이

설치 경로가 여러 갈래라 더 헷갈린다. 정리하면 이렇다.

- pip의 `nvidia-cuda-runtime-cu12` 류 — 런타임 라이브러리만. PyTorch가 의존성으로 끌어온다.
- conda의 `cudatoolkit` — 마찬가지로 런타임 라이브러리 중심. conda 환경 안에 CUDA 런타임을 넣어준다. `pytorch-cuda` 메타패키지는 conda solver가 맞는 PyTorch 빌드를 고르도록 돕는 역할이다.
- NVIDIA가 배포하는 full CUDA Toolkit — 런타임 + 개발 도구 전부. `nvcc`, `cuda-gdb`, `cuda-memcheck`까지 들어 있다.

여기서 갈린다.
PyTorch나 PaddlePaddle로 추론/학습만 한다면 full toolkit이 필요 없다.
런타임 라이브러리만 있으면 되고, 그건 pip/conda가 프레임워크와 함께 넣어준다.
full toolkit이 필요한 건 직접 CUDA 커널(`.cu` 파일)을 작성해서 `nvcc`로 컴파일할 때다.
커스텀 연산을 빌드하거나, 일부 라이브러리를 소스에서 빌드할 때가 그렇다.

그래서 "GPU 코드를 돌린다"와 "GPU 코드를 컴파일한다"를 구분해야 한다.
돌리기만 하면 런타임으로 충분하고, 컴파일하려면 full toolkit이 필요하다.

## PyTorch는 CUDA 버전을 골라서 깐다

PyTorch 휠은 CUDA 버전별로 따로 빌드되어 배포된다.
pip 기본 인덱스에서 받으면 PyTorch가 그 시점에 기본으로 정한 CUDA 빌드가 깔리는데, 특정 버전을 원하면 인덱스를 직접 지정한다.

```bash
# CUDA 11.8 빌드
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.4 빌드
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

어떤 cu 버전을 고를지는 GPU와 드라이버에 달렸다.

- cu118 — 가장 안전하고 호환 범위가 넓다. 오래된 카드도 잘 받는다.
- cu121, cu124, cu126 — 최신 카드에 맞고, 최신 PyTorch가 기본으로 따라가는 쪽이다.

PyTorch 버전마다 제공하는 cu 빌드가 다르다는 점도 주의한다.
예를 들어 어떤 PyTorch 버전은 cu118과 cu124만 주고, 다른 버전은 cu118과 cu126을 준다.
원하는 조합이 실제로 배포되는지를 인덱스에서 먼저 확인하는 게 안전하다.

그리고 앞에서 본 호환성 규칙이 여기서도 작동한다.
PyTorch 휠이 cu126으로 빌드됐어도, 호스트 드라이버가 CUDA 12.x를 받을 수 있으면(같은 메이저의 최소 드라이버 이상) 돈다.
드라이버가 그 메이저를 아예 못 받으면 그때 막힌다.

## 내 환경의 CUDA를 진단하는 법

버전이 꼬였다고 느낄 때 한 번에 훑는 명령들이다.

```bash
# 1. 드라이버가 받아줄 수 있는 CUDA 상한 (Driver API)
nvidia-smi

# 2. 시스템에 설치된 CUDA Toolkit (Runtime API, 없을 수 있음)
nvcc --version

# 3. PyTorch가 번들한 CUDA 런타임 버전
python -c "import torch; print(torch.version.cuda, torch.cuda.is_available())"

# 4. pip가 끌어온 CUDA 런타임 패키지들
pip list | grep -i nvidia
```

이 넷이 다 다른 숫자를 말해도 보통 정상이다.

- nvidia-smi 숫자 ≥ torch.version.cuda 의 메이저 호환이면 GPU가 돈다
- nvcc가 없거나 다른 버전이어도 PyTorch 추론에는 영향이 없다
- `torch.cuda.is_available()`이 True면 실제로 GPU를 잡은 것이다

마지막 줄이 핵심 판정이다.
버전 숫자가 제각각이어도 `is_available()`이 True면 일단 동작하는 환경이다.

## 정리

같은 머신에서 CUDA 버전이 여러 개로 보이는 건 고장이 아니라 구조다.

- CUDA는 Driver API와 Runtime API 두 층으로 나뉜다.
- nvidia-smi는 드라이버 상한(Driver API), nvcc는 설치된 Toolkit(Runtime API)을 본다.
- Python에서는 PyTorch 휠이 자기 CUDA 런타임을 번들로 끌어온다. 그래서 시스템 Toolkit 없이도 GPU가 돈다.
- pip/conda가 주는 건 런타임 라이브러리고, nvcc가 든 full toolkit은 CUDA 코드를 직접 컴파일할 때만 필요하다.
- 버전이 다 달라도 드라이버가 런타임의 메이저를 받아주면 동작한다.

결국 외워야 할 한 줄은 이거다.
호스트에는 드라이버만 맞추고, 런타임 CUDA는 프레임워크가 들고 다닌다.
이 구조를 알고 나니 버전 숫자가 제각각인 게 더 이상 불안하지 않았다.

## 참고 링크

- [CUDA Compatibility — NVIDIA 공식 문서](https://docs.nvidia.com/deploy/cuda-compatibility/)
- [nvcc vs nvidia-smi: Why Different CUDA Versions Are Shown](https://www.codegenes.net/blog/different-cuda-versions-shown-by-nvcc-and-nvidia-smi/)
- [PyTorch Previous Versions — 설치 인덱스](https://pytorch.org/get-started/previous-versions/)
- [CUDA Toolkit: Full vs Conda-installed version](https://medium.com/@yulin_li/cuda-toolkit-full-vs-conda-installed-version-fe2153fc4263)
