---
tags: ["모델 서빙", "추론 프레임워크", "입문"]
series: "추론 서빙 프레임워크 비교"
seriesOrder: 3
---

# Ray Serve — 여러 모델을 분산·오토스케일하는 오케스트레이션 층

> 추론 프레임워크 비교 시리즈의 세 번째 편이다.
> 앞의 [Triton](./triton-inference-server.md)(런타임 층)과 [BentoML](./bentoml.md)(패키징 층)을 먼저 읽으면 Ray Serve가 어느 층에 있는지 대비가 선명하다.

Triton이 "한 GPU에서 모델을 빠르게", BentoML이 "한 모델을 API로 편하게"였다면, Ray Serve의 질문은 규모 쪽이다. **여러 모델을, 여러 노드에 걸쳐, 부하에 맞춰 자동으로 늘렸다 줄였다 하며 어떻게 서빙하나.**

한 문장 결론: **Ray Serve는 분산 컴퓨팅 위에 얹힌 서빙 오케스트레이션 층이다.** 단일 GPU를 저수준으로 짜내는 일은 Triton에 맡기고, 자신은 스케일아웃·오토스케일·모델 조합을 책임진다.

## Ray와 Ray Serve의 관계 — 엔진과 그 위의 라이브러리

먼저 이름부터 정리한다. **Ray**는 분산 컴퓨팅 런타임(AI compute engine)이고, **Ray Serve**는 그 위에 얹힌 서빙 전용 라이브러리다. 공식 정의도 "Ray Serve is built on top of Ray, so it easily scales to many machines and offers flexible scheduling such as fractional GPUs"라고 이 관계를 못박는다.

Ray 생태계에는 Serve 말고도 Train(분산 학습), Data, Tune 등이 있다. 이미 Ray로 분산 학습을 하는 조직이면 같은 런타임 위에서 서빙까지 이어갈 수 있다는 게 Ray Serve의 큰 유인이다(2026년 기준 Ray 2.55~2.56대).

## 핵심 개념 1 — deployment와 replica

Ray Serve의 기본 단위는 **deployment**다. 비즈니스 로직이나 ML 모델을 담은 클래스에 `@serve.deployment`를 붙인다. 런타임에 이 deployment는 여러 **replica**(복제본)로 뜨는데, 각 replica는 별도 프로세스(Ray Actor)로 실행된다.

```python
from ray import serve

@serve.deployment(num_replicas=2, ray_actor_options={"num_gpus": 1})
class OcrModel:
    def __init__(self):
        self.model = load_model()

    async def __call__(self, image: bytes) -> dict:
        return self.model.infer(image)

app = OcrModel.bind()
```

- deployment: 스케일 가능한 서빙 단위.
- replica: 그 deployment의 개별 프로세스 복사본. 부하에 맞춰 개수가 조절된다.
- ingress deployment: `serve.run`에 넘기는 최상위 진입점.

여기서 Triton·BentoML과의 차이가 드러난다. Ray Serve는 처음부터 "여러 프로세스에 복제해 분산한다"를 기본 모델로 깐다.

## 핵심 개념 2 — Autoscaling

Ray Serve의 대표 기능. `num_replicas="auto"`로 켜고 범위를 준다.

```python
@serve.deployment(
    num_replicas="auto",
    autoscaling_config={"min_replicas": 0, "max_replicas": 10},
)
class OcrModel:
    ...
```

- `min_replicas=0`: 트래픽 없는 시간대엔 replica를 0까지 줄여 GPU 비용을 아낀다(scale to zero).
- Serve Controller가 각 replica의 큐 크기·처리 중 요청 수를 주기적으로 수집해 replica 수를 조정한다.

GPU가 비싸고 트래픽이 출렁이는 서빙에서 이 오토스케일이 핵심 가치다. 다만 replica를 0에서 다시 띄울 때 모델 로딩 콜드 스타트가 붙는 맞교환이 있다.

## 핵심 개념 3 — Model composition

OCR처럼 전처리 → 검출 → 인식 → 후처리로 이어지는 파이프라인을, Ray Serve는 여러 deployment를 `.bind()`로 묶어 DAG로 구성한다. 각 단계를 독립 deployment로 나누면 단계별로 따로 스케일·설정할 수 있다.

```python
@serve.deployment
class Pipeline:
    def __init__(self, detector, recognizer):
        self.detector = detector      # DeploymentHandle로 치환됨
        self.recognizer = recognizer

    async def __call__(self, image):
        boxes = await self.detector.remote(image)
        return await self.recognizer.remote(boxes)

app = Pipeline.bind(Detector.bind(), Recognizer.bind())
```

다른 deployment 호출이 평범한 함수 호출처럼 보인다("calls to different models look just like function calls"). 검출 모델은 무거워 replica 4개, 후처리는 가벼워 1개 — 이런 단계별 차등 스케일이 model composition의 강점이다. (과거 "Deployment Graph"라는 실험적 이름이었고 지금은 "Model Composition"이 정식 명칭이다.)

## 핵심 개념 4 — 배칭과 fractional GPU

- **dynamic request batching**: `@serve.batch` 데코레이터로 요청을 모아 배치로 처리한다.
  - `batch_wait_timeout_s`(기본 0.01초)로 대기 상한, `max_concurrent_batches`(기본 1)로 동시 배치 수를 조절.
  - Triton·BentoML의 배칭과 목적은 같다. Ray Serve는 이걸 Python 데코레이터로 준다.
- **fractional GPU**: `ray_actor_options={"num_gpus": 0.5}`처럼 소수점 GPU 할당. 가벼운 모델 여럿이 GPU 하나를 0.25씩 나눠 쓸 수 있다.
  - **중요한 함정**: Ray는 `CUDA_VISIBLE_DEVICES`로 가시성만 격리할 뿐 **실제 GPU 메모리 사용량을 강제하지 않는다.** 각 task가 자기 몫을 넘지 않게 하는 건 사용자 책임이다. fractional GPU는 스케줄링 상의 숫자 배분이지 하드웨어 격리가 아니다. PyTorch·TensorFlow 자체 메모리 제한으로 보완해야 한다.

## 클러스터 구조와 LLM 서빙

Ray cluster는 head node 1개 + worker node 여러 개다. head는 오토스케일러·GCS(전역 제어 저장소)·드라이버 같은 관리 프로세스를 얹어 돌리고, worker는 실제 task·actor 실행을 맡는다. 이 클러스터 자체를 설치·모니터링·장애 대응 하는 운영 부담이 Ray Serve 도입의 진짜 비용이다.

LLM 쪽은 Ray Serve LLM이라는 전용 확장이 있다. OpenAI 호환 API를 주고, vLLM·SGLang 등 특정 엔진에 종속되지 않는 구조다. 파이프라인·텐서·전문가 병렬성, prefill-decode 분리, Multi-LoRA 등을 분산 배포와 함께 쓴다. OCR·CV가 주 관심이면 이 부분은 당장 필요하진 않지만, 같은 프레임워크로 LLM까지 확장 가능하다는 점은 기억해둘 만하다.

## 성능 — 조건부 수치로 읽자

Anyscale(Ray 상용화 회사)이 공개한 최적화 수치가 있다. "워크로드 전반 최대 11.1배 처리량, P99 지연 75~88% 감소" 같은 헤드라인이 대표적이다. 그런데 이건 **특정 워크로드·하드웨어에서, 대개 최적화 전 Ray Serve 버전 대비**의 수치다. 범용 벤치마크로 일반화하면 과장이 된다. 인용하려면 원문의 테스트 조건을 반드시 함께 봐야 한다. 우리 OCR 워크로드의 실제 수치는 직접 재는 게 후속 과제다.

## Anyscale과의 관계

Ray는 Apache 2.0 완전 오픈소스다. Anyscale은 Ray 창시자들이 세운 회사로, 오픈소스 Ray 위에 관리형 엔터프라이즈 플랫폼을 판다. 여기엔 RayTurbo라는 상용 전용 최적화 런타임이 포함돼, 오픈소스 Ray만으로는 못 얻는 성능 개선을 낸다고 명시한다. 즉 위 벤치마크 일부는 상용 레이어가 낀 수치일 수 있으니, 오픈소스만 쓸 계획이면 그만큼 할인해 읽어야 한다.

## 언제 쓰나 / 언제 피하나

**강점**:

- 여러 모델을 조합한 복합 파이프라인, 단계별 차등 스케일.
- 정교한 오토스케일(scale to zero 포함)이 필요한, 트래픽이 출렁이는 서빙.
- 이미 Ray로 분산 학습을 쓰는 조직 — 생태계 통합이 학습 부담을 상쇄.

**약점 / 피할 상황**:

- 단일 GPU 저수준 최적화가 목적 → 그건 Triton의 몫.
- 모델 하나를 그냥 빠르게 API로 → Ray cluster 운영 부담이 과하다. BentoML이 가볍다.
- 클러스터 운영 인력·경험이 없다 → 러닝커브와 운영 복잡도가 부담. 여러 비교 자료가 공통으로 "steeper learning curve"를 지적한다.

한 줄 요약: **여러 모델·노드·오토스케일이 필요한 규모의 문제면 Ray Serve, 그 규모가 아니면 대개 과하다.**

## 다음 편

이제 세 층이 다 나왔다 — Triton(런타임), BentoML(패키징), Ray Serve(오케스트레이션). 마지막 비교편에서 이들을 하나의 표로 정리하고, 서로 조합하는 실전 패턴, 그리고 사내 OCR 서빙 맥락에서 무엇을 고를지 판단 기준을 세운다.

## 참고 링크

- [Ray Serve 개요](https://docs.ray.io/en/latest/serve/index.html)
- [Key Concepts (deployment, replica)](https://docs.ray.io/en/latest/serve/key-concepts.html)
- [Autoscaling guide](https://docs.ray.io/en/latest/serve/autoscaling-guide.html)
- [Model Composition](https://docs.ray.io/en/latest/serve/model_composition.html)
- [Dynamic request batching (@serve.batch)](https://docs.ray.io/en/latest/serve/advanced-guides/dyn-req-batch.html)
- [Resource allocation (fractional GPU)](https://docs.ray.io/en/latest/serve/resource-allocation.html)
- [Ray Serve + Triton 통합 튜토리얼](https://docs.ray.io/en/latest/serve/tutorials/triton-server-integration.html)
