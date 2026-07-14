---
tags: ["모델 서빙", "추론 프레임워크", "입문"]
series: "추론 서빙 프레임워크 비교"
seriesOrder: 2
---

# BentoML — Python 코드를 프로덕션 API로 포장하는 프레임워크

> 추론 프레임워크 비교 시리즈의 두 번째 편이다.
> 첫 편 [Triton Inference Server](./triton-inference-server.md)를 먼저 읽으면 "런타임 층"과 "프레임워크 층"의 차이가 잡힌다. 이 글은 Triton 바로 위 층에 있는 BentoML을 다룬다.

Triton이 "GPU에서 모델을 어떻게 빠르게 돌리나"였다면, BentoML의 질문은 다르다. **내 Python 추론 코드를 어떻게 빠르게 프로덕션 API로 만들고 배포하나.** 공식 정의도 "Python 타입 힌트만으로 모델 추론 코드를 REST API 서버로 전환한다"에 방점이 있다.

한 문장 결론: **BentoML은 개발·패키징·배포의 편의를 파는 프레임워크다.** 저수준 GPU 최적화는 Triton 같은 엔진에 위임하고, 자신은 그 위에서 "빠르게 만들고 컨테이너로 찍어 배포하는" 경험을 책임진다.

## BentoML이 정확히 무엇인가 — 패키징 + 서빙 층

BentoML은 Python 라이브러리다. 추론 로직을 담은 클래스에 데코레이터를 붙이면 REST API 서버가 되고, 그걸 의존성·모델 파일과 함께 하나의 배포 단위로 묶어 컨테이너 이미지까지 뽑는다. 관심사가 "GPU 성능"이 아니라 "개발자 워크플로"에 있다.

버전 얘기를 먼저 정리해야 헷갈리지 않는다. BentoML은 1.2에서 API를 크게 갈아엎었다(2026년 7월 기준 최신 1.4.x).

- **1.1 이전**: `bentoml.Service` + `Runner` 조합 구조. 지금은 "legacy"로 명시됨.
- **1.2 이후**: 클래스 기반 `@bentoml.service` 데코레이터 방식으로 전면 개편.

웹에서 옛 예제(Runner 중심)를 보고 따라 하면 최신 버전과 어긋난다. 아래는 현행 클래스 기반 API 기준이다.

## 핵심 개념 1 — @bentoml.service로 클래스를 API로

추론 클래스에 데코레이터를 붙여 서비스로 만든다. 리소스·타임아웃 같은 설정을 데코레이터 인자로 준다.

```python
import bentoml

@bentoml.service(
    resources={"gpu": 1},
    traffic={"timeout": 10},
)
class OcrService:
    def __init__(self):
        # 모델 로딩 등 초기화
        self.model = load_model()

    @bentoml.api
    def recognize(self, image: bytes) -> dict:
        # 전처리 → 추론 → 후처리를 그냥 Python으로
        return self.model.infer(image)
```

- `@bentoml.service`: 클래스를 서비스로 표시. `resources`로 GPU 개수, `traffic`으로 타임아웃 등 지정.
- `@bentoml.api`: 메서드를 HTTP 엔드포인트로 노출(기본 POST).

주목할 점은 전후처리가 **그냥 평범한 Python 메서드**라는 것이다. Triton에서 Python backend나 BLS 규약에 맞춰야 했던 부분을, 여기서는 아무 제약 없이 파이썬으로 쓴다. 이게 BentoML이 파는 편의의 핵심이다.

## 핵심 개념 2 — Bento와 bentofile.yaml (패키징)

**Bento**는 소스 코드·의존성·모델 파일과 자동 생성된 Dockerfile을 묶은 배포 단위다. `bentofile.yaml`에 빌드 설정을 적고 `bentoml build`로 찍는다.

```yaml
# bentofile.yaml
service: "service:OcrService"
python:
  packages:
    - torch
    - pillow
docker:
  python_version: "3.11"
```

1.4부터는 YAML 없이 `service.py` 안에서 순수 Python으로 빌드 스펙을 정의하는 방식도 생겼다. 어느 쪽이든 목적은 같다 — **모델·코드·환경을 재현 가능한 하나의 아티팩트로 봉인**하는 것이다. 여기서 컨테이너 이미지까지 한 흐름으로 이어진다.

## 핵심 개념 3 — Adaptive batching

BentoML도 배칭을 한다. 서버 쪽 dispatcher가 요청을 모아 배치가 차거나 타임아웃에 닿으면 모델로 넘긴다.

- `max_batch_size`, `max_latency_ms`로 상한을 준다.
- "adaptive"인 이유: 과거 요청 패턴을 회귀 모델로 학습해 실제 배치 크기·대기 시간을 트래픽에 맞춰 스스로 조절한다.

Triton의 dynamic batching과 목적은 같다(처리량 향상). 차이는 BentoML은 이걸 Python 프레임워크 층에서, 트래픽 적응형으로 한다는 점이다. 다만 뒤에 나오는 Triton 통합을 쓰면 이 로직은 우회된다.

## GPU 지원과 Triton 통합 — 유보를 달아야 하는 부분

GPU는 `@bentoml.service(resources={"gpu": 1})`로 붙인다. 멀티 GPU는 개수를 늘리고 코드에서 `cuda:0`, `cuda:1`로 배치한다. 저수준 분산은 PyTorch의 `DistributedDataParallel` 같은 프레임워크 기본 기능에 위임한다 — BentoML 자체의 저수준 분산 추론 엔진은 없다.

Triton 통합은 조심해서 말해야 한다. BentoML 1.0.16부터 Triton을 Runner로 감싸 "Python 편의 + Triton의 C++ 런타임 효율"을 함께 얻는 하이브리드 구조가 있었다. 그런데:

- 이 통합 문서는 아카이브된 1.1 문서 경로에만 있다.
- Runner 개념 자체가 1.2부터 legacy다.
- 최신(1.4) 문서와 발표 블로그에는 Triton 언급이 없다.

공식적으로 "제거했다"는 공지는 못 찾았지만, **최신 문서에서 완전히 빠졌다는 사실 자체가 근거다.** "1.1 시절 기능이며 현행 문서에서는 다뤄지지 않는다"로 이해하는 게 정확하다. 지금 BentoML로 Triton을 감싸는 조합을 전제로 설계하는 건 위험하다.

## 배포 — BentoCloud가 1차, 자체 K8s는 답보

`bentoml containerize <bento>`로 OCI 이미지를 뽑는다. 그다음 배포 대상이 갈린다.

- **BentoCloud**: BentoML의 공식 관리형 배포 대상. 원클릭 배포, GPU 타입 지정 등. 문서가 사실상 이쪽을 1차 경로로 민다.
- **자체 호스팅 K8s**(Yatai): 마지막 태그 릴리스가 2023년 10월이고 1.2용은 "under construction". 관련 도구 `bentoctl`도 deprecated. 여전히 동작은 하지만 활발히 진화하지 않는다.

이 대목이 도입 판단에 중요하다. 사내 K8s에 자체 배포하려는 조직이면, BentoML의 자체 호스팅 경로가 답보 상태라는 점을 감안해야 한다. 관리형(BentoCloud)에 올릴 수 없는 환경이라면 이 부분을 별도로 검증해야 한다.

## 성능 — "BentoML이 빠르다"는 근거는 없다

솔직하게 짚을 부분이다. BentoML 프레임워크 자체의 처리량·지연 공식 벤치마크(오버헤드가 얼마다)는 찾지 못했다.

BentoML이 공개하는 벤치마크는 성격이 다르다. `llm-optimizer`나 LLM Performance Explorer는 **BentoML 위에서 돌린 여러 추론 백엔드(vLLM·TensorRT-LLM 등) 간 비교**다. 즉 "BentoML이 빠르다"가 아니라 "BentoML이 벤치마킹 인프라를 제공한다"는 근거다. 성능을 이유로 BentoML을 고르는 건 층위 오해다 — 성능은 아래 엔진의 몫이고, BentoML은 그 위 편의를 판다.

## 언제 쓰나 / 언제 피하나

**강점**:

- Python 타입 힌트만으로 프로덕션급 REST API를 빠르게. 전후처리에 프레임워크 제약이 없다.
- 모델 패키징(Bento) → 컨테이너화 → 배포까지 하나의 워크플로.
- `bentoml.depends()`로 여러 서비스를 묶어 멀티 모델 파이프라인 구성.

**약점 / 피할 상황**:

- 저수준 GPU 최적화가 목적 → 그건 Triton/TensorRT의 몫. BentoML 자체 기능으로는 부족.
- 자체 인프라에 대규모 분산 서빙 → Ray 수준의 클러스터 스케줄링은 없다.
- 자체 호스팅 K8s가 필수 → Yatai 답보 상태를 감안해야.

한 줄 요약: **모델을 빠르게 API로 만들고 컨테이너로 배포하는 개발 속도가 중요하면 BentoML, GPU를 짜내는 성능이나 대규모 분산이 중심이면 다른 층을 봐야 한다.**

## 다음 편

다음 글은 Ray Serve다. BentoML이 "한 모델을 편하게 API로"라면, Ray Serve는 "여러 모델·여러 노드에 걸쳐 분산·오토스케일"이 주제다. 세 프레임워크의 층위가 모두 나오면, 비교편에서 이들을 조합하는 실전 패턴과 OCR 맥락 판단으로 넘어간다.

## 참고 링크

- [What is BentoML?](https://docs.bentoml.com/en/latest/overview/what-is-bentoml.html)
- [Create online API Services (@bentoml.service)](https://docs.bentoml.com/en/latest/build-with-bentoml/services.html)
- [Introducing BentoML 1.2](https://www.bentoml.com/blog/introducing-bentoml-1-2)
- [Adaptive batching](https://docs.bentoml.com/en/latest/get-started/adaptive-batching.html)
- [GPU inference](https://docs.bentoml.com/en/latest/build-with-bentoml/gpu-inference.html)
- [Packaging for deployment (containerize)](https://docs.bentoml.com/en/latest/get-started/packaging-for-deployment.html)
- [Triton 통합 (1.1 아카이브 문서)](https://docs.bentoml.com/en/1.1/integrations/triton.html)
