---
tags: ["모델 서빙", "추론 프레임워크", "비교", study]
series: "추론 서빙 프레임워크 비교"
seriesOrder: 4
---

# Triton vs BentoML vs Ray Serve: 층이 다른 셋을 어떻게 고르나

> 추론 프레임워크 비교 시리즈의 마지막 편이다.
> 각 프레임워크 입문편([Triton](./triton-inference-server.md) · [BentoML](./bentoml.md) · [Ray Serve](./ray-serve.md))을 먼저 읽으면 이 글의 비교가 훨씬 잘 붙는다.

세 프레임워크를 공부하며 얻은 가장 중요한 결론을 먼저 박아둔다. **Triton vs BentoML vs Ray 는 사실 틀린 질문이다.** 셋은 경쟁 제품이 아니라 서로 다른 층에 있고, 실전에서는 오히려 조합된다. 이 글은 그 계층을 표로 정리하고, 조합 패턴을 보고, Triton 이 NVIDIA Dynamo 로 개편된 뒤의 이름과 LLM 서빙 선택지를 확인한 다음, 마지막으로 사내 OCR 서빙 맥락에서 어떻게 판단할지로 이어간다.

## 층위부터: 넷은 한 줄로 세울 수 없다

앞선 세 편에서 반복한 그림에 LLM 서빙 도구까지 올리면 계층이 넷으로 갈린다.

| 계층 | 하는 일 | 예 |
| --- | --- | --- |
| 라우팅 | 어느 모델과 어느 제공자로 보낼지 정한다 | LiteLLM, Azure Foundry model router |
| 배포와 오케스트레이션 | 모델 서버를 띄우고 스케일한다 | KServe, Ray Serve, BentoML |
| 서빙 서버 | 요청을 받아 배치로 묶고 엔진에 넘긴다. 프로토콜과 지표를 제공한다 | Triton, vLLM 자체 서버 |
| 추론 엔진 | GPU 에서 실제로 토큰을 만든다 | vLLM, TensorRT-LLM |

이 글이 비교하는 셋은 이 표에서 자리가 다르다.
BentoML 은 Python 코드를 API 로 포장해 배포하니 배포와 오케스트레이션 계층에 있고, Ray Serve 는 여러 모델과 노드에 분산해 오토스케일하니 같은 계층의 더 위쪽에 있다.
Triton 은 요청을 받아 배치로 묶고 GPU 인스턴스를 관리하는 서빙 서버 계층에 있다.

**vLLM 은 아래 두 계층에 걸쳐 있어서 이 표에 두 번 나온다.**
`vllm serve` 로 띄우면 그 자체가 OpenAI 호환 API 서버라 서빙 서버 계층에 선다.
반대로 Triton 안에 vLLM backend 로 넣으면 Triton 이 서빙 서버를 맡고 vLLM 은 추론 엔진만 맡는다.
[Triton 편](./triton-inference-server.md)에서 본 backend 목록에 vLLM 과 TensorRT-LLM 이 나란히 있는 것이 이 자리다.

아래로 갈수록 성능, 위로 갈수록 개발과 운영 편의와 규모에 관심이 있다.
그래서 어느 게 제일 좋냐가 아니라 **지금 내 병목이 어느 계층에 있냐**가 올바른 질문이다.

## 공통 비교축

층은 다르지만, 실무자가 고를 때 보는 축은 겹친다. 그 축으로 나란히 놓으면 이렇다.

| 축 | Triton | BentoML | Ray Serve |
|---|---|---|---|
| 주 관심사 | GPU 실행 성능 | 개발·배포 편의 | 분산·오케스트레이션 |
| 개발 언어 경험 | config.pbtxt + 백엔드별 규약 | 순수 Python, 제약 적음 | 순수 Python, 분산 개념 필요 |
| 배칭 | dynamic (요청 단위) | adaptive (트래픽 적응) | `@serve.batch` (요청 단위) |
| GPU 최적화 | 최고<br>concurrent execution, TensorRT | 아래 엔진에 위임 | fractional GPU<br>단 메모리 격리는 미보장 |
| 확장 모델 | 단일 서버 인스턴스 | 컨테이너 복제 | 클러스터 분산<br>오토스케일, scale to zero |
| 전후처리 | Python backend / BLS로 별도 구현 | 평범한 Python 메서드 | 평범한 Python + composition |
| 배포 1차 경로 | 컨테이너 (직접) | BentoCloud<br>자체 K8s는 답보 | Ray cluster (직접 운영) |
| 러닝커브 | config·백엔드 학습 부담 | 낮음 | 클러스터 운영까지 높음 |

핵심만 다시 말하면 이렇다. Triton은 성능을 주고 편의를 뺏고, BentoML은 편의를 주고 성능·규모를 위임하고, Ray Serve는 규모를 주고 운영 부담을 지운다.

## 실전에서는 경쟁이 아니라 조합이다

이 시리즈에서 제일 강조하고 싶은 부분이다. 세 개는 서로를 감싼다.

- **BentoML 과 Triton**: BentoML로 API·전후처리를 Python으로 짜고, 무거운 GPU 추론만 Triton 러너에 위임하는 하이브리드. (단 이 통합은 BentoML 1.1 시절 기능으로, 최신 문서에서 빠졌다 — [BentoML 편](./bentoml.md) 참고. 지금 이 조합을 전제로 설계하는 건 위험하다.)
- **Ray Serve 와 Triton**: Ray Serve가 오토스케일·모델 조합으로 오케스트레이션하고, 각 replica 안에서 Triton을 Python API로 감싸 저수준 추론을 맡기는 패턴. Ray·NVIDIA 양쪽 공식 문서에 튜토리얼이 있다.
- **Ray Serve 와 BentoML**: 각 Bento를 Ray Serve deployment로 감싸 분산·스케일하는 조합.

정리하면 위 두 층(BentoML·Ray Serve)이 개발·운영을 책임지고, 성능이 급하면 그 안쪽에 Triton을 넣는 구조다. "하나를 고른다"기보다 "어느 층까지 직접 짜고 어디부터 위임하냐"의 문제다.

## Triton 은 이제 Dynamo 플랫폼의 일부다

2025년 3월에 NVIDIA 가 Triton 을 Dynamo 플랫폼 안으로 접었다.
공식 표기가 `NVIDIA Dynamo-Triton` 이다.
Triton 이 사라지고 다른 제품으로 대체된 것이 아니라, 담당이 둘로 갈렸다.

| 제품 | 담당 |
| --- | --- |
| Dynamo-Triton | 범용 다중 모델 서빙. 기존 Triton 의 자리를 그대로 잇는다 |
| NVIDIA Dynamo | LLM 전용 추론 서빙. disaggregated serving, prefix caching, KV cache 를 스토리지로 내리는 기능을 담았다 |

[Triton 편](./triton-inference-server.md)에 적었듯 공식 GitHub 저장소와 문서는 여전히 Triton Inference Server 라는 이름과 2.x 버전 체계를 쓴다.
그래서 지금 Triton 을 도입할 때 설정이나 코드에서 바꿔야 하는 것은 없고, 문서와 발표 자료에서 두 이름을 같은 것으로 읽으면 된다.

NVIDIA Dynamo 쪽이 담은 기능은 계층 경계가 움직인다는 신호다.
prefix caching 과 KV cache 를 어디에 두느냐는 원래 라우팅 계층이 어느 인스턴스로 보낼지 정할 때 보던 상태인데, 그것을 서빙 계층이 직접 관리하기 시작했다.
이 경계는 [Model Router 란 무엇인가](../model-router/what-is-model-router.md)에서 다룬다.

## LLM 을 서빙한다면 선택지가 하나 더 있다

이 시리즈를 쓸 때는 LLM 전용 서빙 도구를 비교 대상에 넣지 않았다.
계층을 넷으로 세우면 그 자리가 보인다.

| 상황 | 일반적인 선택 |
| --- | --- |
| LLM 하나만 서빙한다 | vLLM 단독 또는 SGLang |
| LLM 과 임베딩과 비전 모델을 같은 GPU 에서 함께 서빙한다 | Triton 에 backend 로 vLLM 을 꽂는다 |
| Kubernetes 위에서 LLM 만 다루고 캐시 인식 라우팅까지 원한다 | vLLM production stack 또는 llm-d |

근거는 이렇다.

- 단일 모델 LLM 서빙에서는 vLLM 단독이 더 일반적이다. LLM 전용 서빙에서 개발이 가장 활발한 경로가 vLLM 과 SGLang 두 갈래다.
- Triton 의 vLLM backend 는 요청당 오버헤드를 더한다. HTTP 서버와 vLLM 엔진 사이에 계층이 하나 더 생기고, QPS 가 높아질수록 응답을 포장하는 처리에서 시간이 더 걸린다는 실측이 있다. 서빙 서버와 엔진을 한 번에 얻는 대가다.
- 반대로 같은 GPU 에서 LLM 과 임베딩 모델과 비전 인코더를 함께 서빙해야 하면 Triton 쪽이 프로덕션 표준이다. 모델마다 서버를 따로 띄우면 GPU 메모리가 그만큼 나뉜다.

배칭과 GPU 활용률이 왜 이 선택을 가르는지는 [GPU로 LLM을 서빙한다는 것](../llm-serving/gpu-llm-serving-basics.md)과 [배칭과 GPU 활용률](../llm-serving/continuous-batching-gpu-utilization.md)에 정리해뒀다.

## 사내 OCR 서빙 맥락에서의 판단

이 공부를 시작한 실제 이유로 돌아온다. 현재 우리 OCR 추론 서빙은 **프레임워크 없이 gRPC 기반 Python 모델 서버를 직접 구현해 컨테이너로 운영**하는 형태다. 위 세 프레임워크는 아직 쓰지 않는다. 그 관점에서 각 층이 무엇을 더해줄지 정리하면 이렇다.

- **직접 구현한 gRPC 서버의 정체**: 사실 지금 손으로 짠 것 상당 부분이 Triton이 표준으로 제공하는 것이다 — gRPC 프로토콜, 요청 배칭, 인스턴스 관리. Triton으로 옮기면 이 코드를 설정으로 대체하고 dynamic batching·concurrent execution을 공짜로 얻는다. 대신 전후처리를 백엔드 규약에 맞춰 재구성해야 하고, config 러닝커브를 진다.
- **BentoML이 더할 것**: 모델·코드·환경을 하나의 아티팩트로 봉인하고 컨테이너까지 뽑는 패키징 워크플로. 다만 성능 문제를 풀어주진 않는다. 지금 GPU 활용도가 병목이면 BentoML은 답이 아니다.
- **Ray Serve가 더할 것**: 트래픽이 크게 출렁이고 여러 모델을 단계별로 다르게 스케일해야 할 때. 단 Ray cluster 운영 부담이 크므로, 그 규모의 문제가 실제로 있는지가 도입 조건이다.

판단 프레임을 적는다. 다음 순서로 자문하면 층이 갈린다.

1. **GPU 활용도·처리량이 지금 병목인가?** → 그렇다면 Triton(또는 그 조합)을 먼저 본다.
2. **개발·배포 반복 속도가 병목인가?** → BentoML.
3. **트래픽 변동·다중 모델 스케일이 병목인가?** → Ray Serve.
4. **아직 병목이 뚜렷하지 않은가?** → 프레임워크 도입을 서두르지 말고, 먼저 현재 서버의 처리량·지연을 측정해 병목 층부터 찾는다.

가장 중요한 건 4번이다. 프레임워크는 병목을 아는 다음에 고르는 것이지, 좋아 보여서 얹는 게 아니다.

## 실측은 후속 과제

이 시리즈는 공식 문서와 벤치마크를 교차검증해 정리한 개념·구조 비교다. **세 스택을 우리 OCR 모델로 직접 벤치마크한 실측은 아직 없다.** 절대 성능 순위를 단정하지 않은 이유다.

후속 과제로 남긴다.

- 현재 gRPC 서버의 처리량·p99 지연을 기준값으로 측정한다.
- Triton으로 같은 모델을 서빙해 dynamic batching·instance group 설정을 바꿔가며 `perf_analyzer`로 비교한다.
- 그 결과로 "직접 구현 대비 Triton이 실제로 얼마나 이득인가"를 수치로 확인한 뒤, 별도 실측 글로 정리한다.

## 시리즈를 마치며

세 프레임워크를 공부하고 남은 한 문장은 이것이다. **추론 프레임워크 선택은 성능 경쟁에서 이긴 하나를 고르는 게 아니라, 내 병목이 어느 층에 있는지 진단하고 그 층의 도구를 고르는 일이다.** Triton은 서빙 서버, BentoML은 패키징, Ray Serve는 오케스트레이션이고, vLLM 은 서빙 서버와 추론 엔진 양쪽에 걸쳐 있다. 계층을 알면 "vs"가 아니라 "어디까지 직접 짜고 어디부터 위임하나"로 질문이 바뀐다.

## 참고 링크

- [BentoML vs Ray Serve vs Triton 비교 (index.dev)](https://www.index.dev/skill-vs-skill/ai-bentoml-vs-ray-serve-vs-triton)
- [Ray Serve 와 Triton 통합 튜토리얼](https://docs.ray.io/en/latest/serve/tutorials/triton-server-integration.html)
- [BentoML or Triton, Choose Both (BentoML 블로그, 2023)](https://www.bentoml.com/blog/bentoml-or-triton-inference-server-choose-both)
- [Ray 와 NVIDIA 로 만드는 저지연 생성 AI 서빙 (Anyscale)](https://www.anyscale.com/blog/low-latency-generative-ai-model-serving-with-ray-nvidia)
- [추론 서버 비교. vLLM, TGI, SGLang, Triton (Prem AI)](https://www.premai.io/blog/llm-inference-servers-compared-vllm-vs-tgi-vs-sglang-vs-triton-2026/)
- [Triton 과 vLLM 의 GPU 추론 플랫폼 비교 (Alongside)](https://www.alongside.team/blog/triton-vs-vllm-gpu-inference-platforms)
- [NVIDIA Dynamo-Triton 제품 페이지](https://developer.nvidia.com/dynamo-triton)
- [NVIDIA Dynamo 공개 발표 (NVIDIA 뉴스룸, 2025)](https://nvidianews.nvidia.com/news/nvidia-dynamo-open-source-library-accelerates-and-scales-ai-reasoning-models)
- [NVIDIA Dynamo 가 무엇이고 왜 중요한가 (Network World)](https://www.networkworld.com/article/3849341/what-is-nvidia-dynamo-and-why-it-matters-to-enterprises.html)
