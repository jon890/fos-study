# PyTorch 기초 — 텐서, 디바이스, 그리고 모델 로딩이 무거운 이유

자바 백엔드에서 Spring Boot 가 부팅하는 시간이 5-30초 걸리는 게 일반적이다. 클래스 로딩, 컴포넌트 스캔, 의존성 주입, EntityManagerFactory 초기화 등이 누적된다. 한 번 부팅하면 그 뒤로는 요청 처리에 거의 영향이 없다.

PyTorch 기반 ML 서비스는 비슷하지만 한 단계 더 무겁다. 우리 프로젝트의 KR Worker 가 실측으로 **워커 한 번 spawn 마다 5.74초** (1,565회 측정, p95 5.94s) 의 워밍업 비용을 지불한다. 자바 시각으로는 "Spring Boot 가 매번 부팅하는 비용을 요청 몇 건마다 다시 내는 셈". 이 글은 PyTorch 의 모델 로딩이 왜 그렇게 무거운지, 자바 백엔드 비교로 정리한다.

## 텐서 — numpy array + GPU + autograd

PyTorch 의 모든 데이터는 `torch.Tensor` 다. 겉모습은 numpy `ndarray` 와 비슷하지만 세 가지가 더 있다.

1. **GPU 에서 동작 가능** — `.to("cuda")` 로 VRAM 으로 이동, 같은 연산을 GPU 가 수행
2. **자동 미분** — `requires_grad=True` 시 모든 연산이 계산 그래프로 기록, 학습 가능
3. **dtype 가 정수·소수·복소수·bool 까지 폭넓음** — float32, float16, bfloat16, int8 등 (양자화 시 중요)

```python
import torch

x = torch.tensor([[1.0, 2.0], [3.0, 4.0]])      # CPU 텐서, float32 기본
print(x.shape, x.dtype, x.device)
# torch.Size([2, 2]) torch.float32 cpu

y = x.to("cuda")                                  # GPU 로 복사
z = y @ y.T                                       # GPU 에서 행렬 곱
print(z.device)
# cuda:0
```

자바로 비유하면 `Tensor` 는 `double[]` + `Stream API` + GPU 위에서 도는 SIMD 까지 묶은 객체. Spring 의 `Mono<T>` 처럼 lazy 한 것은 아니지만, autograd 모드에서는 계산 그래프가 차곡차곡 쌓인다는 점에서 비슷한 결.

추론 (학습 아님) 서비스에서는 보통 autograd 를 끈다. `torch.no_grad()` 또는 `torch.inference_mode()` 컨텍스트 매니저 안에서 연산. 자바의 `final` 처럼 "수정 안 함" 을 컴파일러가 아니라 런타임에 PyTorch 에 알려주는 셈.

```python
with torch.inference_mode():
    output = model(input_tensor)
```

## device — 자바의 Executor 자리

자바에서 `ExecutorService` 가 작업을 어디서 실행할지 결정하듯, PyTorch 에서는 텐서·모델의 `device` 가 어디서 연산이 일어날지 결정한다.

```python
device = "cuda" if torch.cuda.is_available() else \
         "mps"  if torch.backends.mps.is_available() else \
         "cpu"

model = model.to(device)
input = input.to(device)
output = model(input)        # 같은 device 에서만 연산 가능
```

같은 device 끼리만 연산이 된다. CPU 텐서와 GPU 텐서를 곱하려 하면 `RuntimeError: Expected all tensors to be on the same device` 가 난다. 자바 멀티스레드에서 ThreadLocal 자원을 다른 스레드가 만지면 NPE 가 나는 것과 비슷한 위치.

device 가 여러 개 (multi-GPU) 인 환경에서는 `cuda:0`, `cuda:1` 처럼 인덱스를 지정한다. 우리 운영 환경은 T4 한 장이라 항상 `cuda:0`.

## nn.Module — Spring `@Service` 같은 비유

PyTorch 모델의 단위는 `torch.nn.Module` 서브클래스다. 자바에서 `@Service` 클래스가 비즈니스 로직을 담듯, `nn.Module` 은 forward 연산을 담는다.

```python
import torch.nn as nn

class Classifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer1 = nn.Linear(768, 256)
        self.layer2 = nn.Linear(256, 10)

    def forward(self, x):
        x = torch.relu(self.layer1(x))
        return self.layer2(x)

model = Classifier().to("cuda")
output = model(input_tensor)         # 사실은 model.forward(input_tensor)
```

자바 차이점:

- 모델의 **상태 = parameter 들 (텐서)** 이 객체 안에 보유된다. `model.parameters()` 로 순회 가능.
- 모델 호출 시 `forward` 가 아니라 객체 자체를 함수처럼 부른다 (`model(x)`). [Python 데코레이터 글](./java-to-python-oop-decorator.md) 의 `__call__` dunder 가 동작.
- `.to("cuda")` 한 번 부르면 **모든 parameter 텐서가 GPU 로 일괄 이동**. 자바의 `@Transactional` 처럼 모듈 전체에 적용되는 동작.

## 모델 로딩이 무거운 이유 — 다섯 단계 누적

자바 Spring 부팅이 한 번 끝나면 그 뒤로는 코드 로딩이 끝나지만, PyTorch 모델 로딩은 다음 다섯 단계가 모두 끝나야 첫 추론이 가능하다.

### 1단계: heavy import (3-8s)

`import torch`, `import paddle`, `import docling`, `import transformers` 자체가 비싸다. 각 라이브러리가 수십 MB 짜리 native 바이너리 (CUDA kernels, BLAS 라이브러리) 를 로딩하고 ABI 호환성 체크를 한다.

자바 `Class.forName(...)` 의 lazy 클래스 로딩과 달리 Python 은 import 즉시 모듈 본문이 전부 실행된다. ML 라이브러리들은 import 시점에 GPU device 스캔, CUDA 버전 확인 등을 한다.

### 2단계: 모델 파일 디스크 읽기 (수 100MB)

`torch.load("model.pt")` 또는 HuggingFace `from_pretrained(...)` 는 사실상 큰 binary file 을 디스크에서 읽어 파이썬 객체로 deserialize 한다. 모델 크기가 BERT-base 라면 ~440MB, 더 큰 모델은 수 GB.

자바의 `ObjectInputStream` deserialization 과 같은 결인데 데이터 크기 자체가 큼.

### 3단계: weights 를 GPU 로 복사 (PCIe 전송)

파일에서 읽은 weight 텐서를 시스템 RAM 에서 VRAM 으로 옮긴다. `model.to("cuda")`. PCIe 버스를 통한 단방향 전송. 약 10GB/s 대역폭 기준 400MB 모델은 약 40ms 지만 실제로는 작은 청크 여러 개라 시간이 좀 더 든다.

### 4단계: CUDA context 초기화 (300-600MB VRAM + 1-2s)

각 프로세스가 GPU 에 처음 접근할 때 CUDA Runtime 이 컨텍스트를 만든다. 자바의 첫 `Thread.start()` 가 OS 스레드를 만드는 비용과 비슷한 위치인데 훨씬 무겁다. 300-600MB 의 VRAM 도 소비. NVIDIA MPS 가 이 비용을 공유로 줄이려는 시도.

### 5단계: JIT warmup — 첫 추론 캐싱 (3-10s)

PyTorch / cuDNN 은 첫 번째 추론 시점에 최적 알고리즘을 선택하고 GPU kernel 을 컴파일해 캐싱한다. 같은 입력 shape 라면 두 번째 호출부터 매우 빠르다.

자바의 JIT (HotSpot) 가 자주 호출되는 메서드를 컴파일하는 것과 같은 개념인데, ML 라이브러리는 **첫 호출 자체에 더 큰 비용**을 모은다. 그래서 서비스 부팅 시 "warmup" 단계를 의도적으로 수행한다.

```python
# warmup — 서비스가 받을 입력과 같은 shape 로 한 번 돌려준다
dummy = torch.randn(1, 3, 224, 224, device="cuda")
with torch.inference_mode():
    _ = model(dummy)
torch.cuda.synchronize()
```

우리 프로젝트의 `warm_up_all_converters` 함수가 정확히 이 일을 한다. Docling converter 를 만들고 `sample/warmup.pdf` 를 한 번 변환해 JIT 캐시를 채운다. 운영 로그에서 `Finished converting document warmup.pdf in 4.67 sec` 로 보이는 게 이 단계.

## 우리 환경의 5.74초 분해

운영 측정 결과 KR Worker 워밍업 시간 mean 5.74s, p50 5.48s. 위 다섯 단계로 분해하면 다음과 같다.

| 단계 | 추정 시간 | 비고 |
|---|---|---|
| heavy import | ~1-2s | 두 번째 worker spawn 부터는 OS 페이지 캐시 덕에 빠름 |
| PaddleOCR 모델 로드 | ~1s | det+rec+cls 세 모델 |
| Docling converter 생성 | ~0.5-1s | layout, table, OCR pipeline 옵션 결합 |
| GPU 로 transfer + CUDA context | ~0.5-1s | 모델이 GPU 모드일 때 |
| warmup convert + MarkItDown sample | ~2-3s | `warmup.pdf` 4.67s + `warmup.docx` 0.55s 합산 |

부팅 시점에는 모델 파일 다운로드 (HuggingFace) 까지 포함되어 16.5s 가 걸린다. 그 이후 respawn 은 디스크 캐시 덕에 5.7s 수준. 우리 분석에서 "모델 다시 로딩하는 비용이 워밍업 시간 차이를 만든다" 가 핵심 결론.

## HuggingFace 캐시 — 자바 Maven local repo 자리

`transformers`, `docling-ibm-models` 같은 라이브러리는 모델을 처음 요청할 때 HuggingFace Hub 에서 자동 다운로드한 뒤 `~/.cache/huggingface/` 에 저장한다. 자바의 `~/.m2/repository` 와 같은 자리.

Docker 환경에서는 이 캐시가 컨테이너 안에 있으면 컨테이너 재시작 시 사라진다. 그래서 우리 Dockerfile 은 빌드 시점에 `huggingface-cli download` 로 모델을 미리 받아 이미지에 박는다. 자바에서 `mvn dependency:go-offline` 으로 의존성을 박는 것과 같은 패턴.

## 모델 캐시 — 자바 싱글톤 빈

PyTorch 모델 자체는 한 번 로드하면 메모리에 떠 있다. 매 요청마다 다시 로드하면 위 다섯 단계를 매번 반복해 처리가 안 된다.

우리 프로젝트는 worker 안에 `_converter_cache` (`document_parser.py:161`) 라는 dict 로 옵션 조합별 Docling converter 를 캐싱한다. 자바 Spring 의 싱글톤 빈과 같은 패턴.

```python
_converter_cache = {}

def get_converter(do_ocr, do_table, ja_doc):
    cache_key = f"ocr_{do_ocr}_table_{do_table}_ja_{ja_doc}"
    if cache_key not in _converter_cache:
        _converter_cache[cache_key] = build_converter(do_ocr, do_table, ja_doc)
    return _converter_cache[cache_key]
```

cache key 가 빠뜨려진 인자 (예: `ocr_model`) 가 있으면 stale cache 버그가 생긴다. 우리 분석에서 이슈로 잡힌 부분.

## 정리

자바 백엔드에서 ML 서비스로 넘어올 때 두 줄로 외우면 좋다.

> PyTorch 모델 로딩은 import + 디스크 읽기 + GPU 전송 + CUDA context + JIT warmup 다섯 단계의 합이다. 한 번 끝나면 캐시 객체로 재사용한다.

> Worker 가 죽고 다시 spawn 될 때마다 이 다섯 단계가 반복된다. `MAX_TASKS_PER_WORKER` 가 작으면 누적 비용이 폭증한다.

다음 글은 이 워밍업 비용을 multi-process worker pool 패턴으로 다루는 방법, 자바 ThreadPool 과의 결정적 차이를 정리한다.

## 참고

- [PyTorch — Tensors](https://pytorch.org/docs/stable/tensors.html)
- [PyTorch — nn.Module](https://pytorch.org/docs/stable/generated/torch.nn.Module.html)
- [PyTorch — Inference Mode](https://pytorch.org/docs/stable/generated/torch.inference_mode.html)
- [HuggingFace — Caching](https://huggingface.co/docs/huggingface_hub/guides/manage-cache)
- [PyTorch CUDA Semantics — Caching allocator](https://pytorch.org/docs/stable/notes/cuda.html#memory-management)
