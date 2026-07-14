---
tags: ["모델 서빙", "추론 프레임워크", "비교"]
series: "추론 서빙 프레임워크 비교"
seriesOrder: 4
---

# Triton vs BentoML vs Ray Serve — 층이 다른 셋을 어떻게 고르나

> 추론 프레임워크 비교 시리즈의 마지막 편이다.
> 각 프레임워크 입문편([Triton](./triton-inference-server.md) · [BentoML](./bentoml.md) · [Ray Serve](./ray-serve.md))을 먼저 읽으면 이 글의 비교가 훨씬 잘 붙는다.

세 프레임워크를 공부하며 얻은 가장 중요한 결론을 먼저 박아둔다. **Triton vs BentoML vs Ray 는 사실 틀린 질문이다.** 셋은 경쟁 제품이 아니라 서로 다른 층에 있고, 실전에서는 오히려 조합된다. 이 글은 그 층위를 표로 정리하고, 조합 패턴을 보고, 마지막으로 사내 OCR 서빙 맥락에서 어떻게 판단할지로 이어간다.

## 층위부터 — 셋은 한 줄로 세울 수 없다

앞선 세 편에서 반복한 그림을 한 자리에 모으면 이렇다.

- **Triton** = 모델 실행 런타임 (제일 아래). GPU에서 모델을 빠르게 돌린다.
- **BentoML** = 패키징 + 서빙 프레임워크 (가운데). Python 코드를 API로 포장·배포한다.
- **Ray Serve** = 분산 오케스트레이션 (제일 위). 여러 모델·노드에 분산·오토스케일한다.

아래로 갈수록 "성능", 위로 갈수록 "개발·운영 편의와 규모"에 관심이 있다. 그래서 "어느 게 제일 좋냐"가 아니라 **지금 내 병목이 어느 층에 있냐**가 올바른 질문이다.

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

핵심만 다시 말하면 — Triton은 성능을 주고 편의를 뺏고, BentoML은 편의를 주고 성능·규모를 위임하고, Ray Serve는 규모를 주고 운영 부담을 지운다.

## 경쟁이 아니라 조합 — 실전 패턴

이 시리즈에서 제일 강조하고 싶은 부분이다. 세 개는 서로를 감싼다.

- **BentoML + Triton**: BentoML로 API·전후처리를 Python으로 짜고, 무거운 GPU 추론만 Triton 러너에 위임하는 하이브리드. (단 이 통합은 BentoML 1.1 시절 기능으로, 최신 문서에서 빠졌다 — [BentoML 편](./bentoml.md) 참고. 지금 이 조합을 전제로 설계하는 건 위험하다.)
- **Ray Serve + Triton**: Ray Serve가 오토스케일·모델 조합으로 오케스트레이션하고, 각 replica 안에서 Triton을 Python API로 감싸 저수준 추론을 맡기는 패턴. Ray·NVIDIA 양쪽 공식 문서에 튜토리얼이 있다.
- **Ray Serve + BentoML**: 각 Bento를 Ray Serve deployment로 감싸 분산·스케일하는 조합.

정리하면 위 두 층(BentoML·Ray Serve)이 개발·운영을 책임지고, 성능이 급하면 그 안쪽에 Triton을 넣는 구조다. "하나를 고른다"기보다 "어느 층까지 직접 짜고 어디부터 위임하냐"의 문제다.

## 사내 OCR 서빙 맥락에서의 판단

이 공부를 시작한 실제 이유로 돌아온다. 현재 우리 OCR 추론 서빙은 **프레임워크 없이 gRPC 기반 Python 모델 서버를 직접 구현해 컨테이너로 운영**하는 형태다. 위 세 프레임워크는 아직 쓰지 않는다. 그 관점에서 각 층이 무엇을 더해줄지 정리하면 이렇다.

- **직접 구현한 gRPC 서버의 정체**: 사실 지금 손으로 짠 것 상당 부분이 Triton이 표준으로 제공하는 것이다 — gRPC 프로토콜, 요청 배칭, 인스턴스 관리. Triton으로 옮기면 이 코드를 설정으로 대체하고 dynamic batching·concurrent execution을 공짜로 얻는다. 대신 전후처리를 백엔드 규약에 맞춰 재구성해야 하고, config 러닝커브를 진다.
- **BentoML이 더할 것**: 모델·코드·환경을 하나의 아티팩트로 봉인하고 컨테이너까지 뽑는 패키징 워크플로. 다만 성능 문제를 풀어주진 않는다. 지금 GPU 활용도가 병목이면 BentoML은 답이 아니다.
- **Ray Serve가 더할 것**: 트래픽이 크게 출렁이고 여러 모델을 단계별로 다르게 스케일해야 할 때. 단 Ray cluster 운영 부담이 크므로, 그 규모의 문제가 실제로 있는지가 도입 조건이다.

판단 프레임 — 다음 순서로 자문하면 층이 갈린다.

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

세 프레임워크를 공부하고 남은 한 문장은 이것이다. **추론 프레임워크 선택은 성능 경쟁에서 이긴 하나를 고르는 게 아니라, 내 병목이 어느 층에 있는지 진단하고 그 층의 도구를 고르는 일이다.** Triton은 실행, BentoML은 패키징, Ray Serve는 오케스트레이션 — 층을 알면 "vs"가 아니라 "어디까지 직접 짜고 어디부터 위임하나"로 질문이 바뀐다.

## 참고 링크

- [BentoML vs Ray Serve vs Triton 비교 (index.dev)](https://www.index.dev/skill-vs-skill/ai-bentoml-vs-ray-serve-vs-triton)
- [Ray Serve + Triton 통합 튜토리얼](https://docs.ray.io/en/latest/serve/tutorials/triton-server-integration.html)
- [BentoML or Triton, Choose Both (BentoML 블로그, 2023)](https://www.bentoml.com/blog/bentoml-or-triton-inference-server-choose-both)
- [Low-latency generative AI serving with Ray + NVIDIA (Anyscale)](https://www.anyscale.com/blog/low-latency-generative-ai-model-serving-with-ray-nvidia)
