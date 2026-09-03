---
tags: ["모델 서빙", "추론 프레임워크", "입문", study]
series: "추론 서빙 프레임워크 비교"
seriesOrder: 1
---

# Triton Inference Server — GPU 추론을 짜내는 모델 실행 런타임

> 이 글은 추론 프레임워크 비교 시리즈의 첫 편이다.
> 배칭이 왜 GPU 처리량을 올리는지 원리가 궁금하면 [배칭과 GPU 활용률](../llm-serving/continuous-batching-gpu-utilization.md)을 먼저 읽으면 좋다. 여기서는 그 원리를 Triton이 어떤 설정으로 실현하는지에 집중한다.

추론 프레임워크를 비교하기 전에 한 가지를 먼저 못박아야 한다. Triton, BentoML, Ray는 흔히 "vs"로 묶이지만 **같은 층이 아니다.** Triton은 그중 가장 아래, 모델을 GPU에서 실제로 실행하는 런타임에 있다. 이 글은 Triton이 그 층에서 무엇을 해주는지, 그리고 우리가 직접 gRPC 서버를 짜서 하던 일을 Triton이 어떻게 설정 한 줄로 대체하는지를 정리한다.

한 문장 결론: **Triton은 "GPU를 최대한 안 놀리기"에 특화된 서버다.** dynamic batching과 concurrent execution 두 장치가 그 목적을 위해 존재한다. 대신 전후처리를 Python으로 편하게 붙이는 개발 경험은 포기해야 한다.

## Triton이 정확히 무엇인가 — 서빙 런타임 층

Triton은 **이미 만들어진 모델을 로드해 요청을 받고 추론을 실행·응답하는 서버**다. 모델을 학습하거나 최적화하는 도구가 아니다. TensorRT 엔진, ONNX, PyTorch(TorchScript), TensorFlow 같은 산출물을 받아 프로덕션에서 굴리는 실행 계층에 있다.

이름에 얽힌 사연이 하나 있다. 처음엔 **TensorRT Inference Server**였는데, TensorRT 외 다른 프레임워크까지 지원하게 되면서 2020년 Triton으로 개명됐다. 최근 NVIDIA 마케팅 자료에서 "Dynamo Triton"이라는 상위 브랜드로 묶어 부르기도 하지만, 공식 GitHub 저장소와 문서는 여전히 "Triton Inference Server"라는 이름과 2.x 버전 체계를 그대로 쓴다(2026년 7월 기준 최신 2.70.0, 컨테이너 태그 26.06).

레이어를 이렇게 잡아두면 뒤 편들이 쉬워진다.

- **Triton**: 모델을 GPU에서 빠르게 실행하는 런타임 (이 글)
- **BentoML**: 모델을 Python으로 포장해 API로 내보내는 프레임워크
- **Ray Serve**: 여러 모델·노드에 분산·오케스트레이션하는 층

Triton은 제일 아래고, 뒤 두 프레임워크가 Triton을 감싸 쓰는 조합도 실제로 존재한다.

## Dynamic batching — 요청을 묶어 GPU를 채운다

Triton의 핵심 기능 첫 번째. 개별 요청을 큐에서 잠깐 대기시켰다가 여러 건을 묶어 백엔드에 한 번에 넘긴다. 배칭이 왜 처리량을 올리는지는 [별도 글](../llm-serving/continuous-batching-gpu-utilization.md)에서 다뤘으니 여기서는 **Triton이 그걸 어떤 손잡이로 조절하는지**만 본다.

모델 설정 파일 `config.pbtxt`에 이렇게 적는다.

```
# config.pbtxt
max_batch_size: 32

dynamic_batching {
  preferred_batch_size: [ 8, 16 ]
  max_queue_delay_microseconds: 100
}
```

- `preferred_batch_size`: 가능하면 이 크기로 배치를 묶으려 시도한다.
- `max_queue_delay_microseconds`: 선호 배치를 못 채웠을 때 요청을 큐에서 **얼마나 더 기다릴지**의 상한. 기본값 0.
  - 대기 중 새 요청이 들어와 배치가 차면 그 즉시 보낸다.
  - 이 값을 키우면 배치가 잘 차서 처리량↑, 대신 개별 요청 지연↑. 앞서 스캐폴딩에서 짚은 처리량 대 지연 맞교환이 바로 이 한 줄에 있다.

여기서 중요한 구분 하나. Triton의 dynamic batching은 **요청 단위 배칭**(request batching)이다. CV·OCR 모델처럼 한 번의 forward pass로 결과가 나오는 모델에 맞다. LLM에서 쓰는 continuous batching(토큰 스텝 단위로 슬롯을 재활용하는 방식)과는 다른 개념이다 — LLM 쪽은 [배칭 글](../llm-serving/continuous-batching-gpu-utilization.md)에서 다룬다. OCR 추론 서빙을 고민한다면 우리에게 필요한 건 continuous가 아니라 이 dynamic batching이다.

## Concurrent model execution — 한 GPU에 인스턴스 여러 개

두 번째 장치. 기본 상태의 Triton은 모델 인스턴스를 1개만 띄운다. 동시에 요청이 몰리면 GPU에서 순차 실행된다. `instance_group`으로 인스턴스를 늘리면 여러 요청을 겹쳐 처리한다.

```
# config.pbtxt
instance_group [
  {
    count: 2
    kind: KIND_GPU
  }
]
```

인스턴스를 2개로 늘리면 한 인스턴스가 CPU↔GPU 메모리 전송을 하는 동안 다른 인스턴스가 연산을 돌려, 놀던 시간을 겹쳐 없앤다. dynamic batching이 "요청을 가로로 묶기"라면 concurrent execution은 "실행을 세로로 겹치기"다. 둘을 함께 써서 GPU 활용도를 짜낸다.

## 지원 백엔드 — 하나의 서버로 여러 프레임워크

Triton은 프레임워크마다 "백엔드" 플러그인으로 대응한다. 한 서버 프로세스가 서로 다른 프레임워크 모델을 동시에 굴릴 수 있다.

- TensorRT, ONNX Runtime, PyTorch(LibTorch), TensorFlow, OpenVINO
- Python backend — 전후처리나 커스텀 로직을 Python으로 직접 구현
- vLLM backend, TensorRT-LLM backend — LLM 서빙용

OCR 파이프라인이 검출 모델은 ONNX, 인식 모델은 PyTorch처럼 섞여 있어도 한 Triton으로 묶을 수 있다는 뜻이다.

## Ensemble과 BLS — 여러 모델을 서버 안에서 이어 붙이기

OCR은 보통 단일 모델이 아니라 전처리 → 검출 → 인식 → 후처리로 이어지는 파이프라인이다. 이걸 잇는 방법은 두 가지다.

먼저 **안 쓰는** 쪽부터 보면 왜 필요한지 와닿는다. 클라이언트가 직접 오케스트레이션하는 방식이다.

1. 클라이언트 → Triton: 전처리 모델 호출, 결과 받음
2. 클라이언트 → Triton: 검출 모델 호출, 박스 받음
3. 클라이언트 → Triton: 인식 모델 호출, 텍스트 받음

문제는 단계마다 **네트워크 왕복**이 생기고, 중간 텐서(전처리된 이미지·박스)가 GPU에서 클라이언트로 나왔다 다시 들어간다는 것이다. 이미지 데이터가 크면 이 왕복이 지연을 지배한다.

Ensemble과 BLS는 이 오케스트레이션을 **서버 안으로** 옮긴다. 클라이언트는 원본 이미지 한 번만 보내고 최종 텍스트만 받는다. 중간 텐서는 GPU 메모리에 머문 채 모델 사이를 흐른다. 왕복이 사라진다.

### Ensemble — 설정으로 그리는 정적 DAG

Ensemble은 코드 없이 `config.pbtxt` 설정만으로 모델들을 DAG(방향 있는 비순환 그래프)로 잇는다. 핵심은 **어느 모델의 출력이 어느 모델의 입력으로 들어가는지**를 텐서 이름으로 배선하는 것이다.

```
# ocr_pipeline/config.pbtxt
name: "ocr_pipeline"
platform: "ensemble"
input  [ { name: "RAW_IMAGE" data_type: TYPE_UINT8 dims: [ -1 ] } ]
output [ { name: "TEXT"      data_type: TYPE_STRING dims: [ -1 ] } ]

ensemble_scheduling {
  step [
    {
      model_name: "preprocess"
      input_map  { key: "IMAGE_IN"  value: "RAW_IMAGE" }    # 파이프라인 입력을 받음
      output_map { key: "IMAGE_OUT" value: "preprocessed" } # "preprocessed"라는 이름표를 붙여 내보냄
    },
    {
      model_name: "detector"
      input_map  { key: "IMAGE" value: "preprocessed" }     # 위 단계 출력을 이름으로 받음
      output_map { key: "BOXES" value: "boxes" }
    },
    {
      model_name: "recognizer"
      input_map  { key: "BOXES"    value: "boxes" }
      output_map { key: "TEXT_OUT" value: "TEXT" }           # 파이프라인 최종 출력으로 연결
    }
  ]
}
```

읽는 법: `output_map`의 `value`가 이름표를 붙여 내보내면, 다음 단계의 `input_map`이 그 `value` 이름으로 받아 간다. `value`들이 서버 내부의 "텐서 버스"고, `key`는 각 모델이 자기 입출력에 붙인 이름이다. 이렇게 `RAW_IMAGE → preprocessed → boxes → TEXT`로 텐서가 흐른다.

한계가 여기서 드러난다. **배선이 고정**이다. `if 한글이면 A엔진, 영어면 B엔진` 같은 조건 분기나, `검출된 박스 개수만큼 인식 반복` 같은 루프를 config로는 못 그린다. DAG는 갈래가 정해진 정적 그래프라서다.

### BLS — Python으로 짜는 동적 오케스트레이션

**BLS**(Business Logic Scripting)는 그 한계를 푼다. Python backend 모델의 `execute` 함수 안에서 다른 모델에 추론 요청을 **코드로** 직접 보낸다. 그래서 반복문·조건문이 된다.

OCR의 전형적 상황 — 검출된 박스 개수가 이미지마다 다르다. ensemble로는 "박스 수만큼 인식 반복"을 못 그리지만 BLS로는 그냥 `for`다.

```python
import triton_python_backend_utils as pb_utils

class TritonPythonModel:
    def execute(self, requests):
        responses = []
        for request in requests:
            image = pb_utils.get_input_tensor_by_name(request, "RAW_IMAGE")

            # 1. 검출 모델을 코드로 호출
            det_req = pb_utils.InferenceRequest(
                model_name="detector",
                requested_output_names=["BOXES"],
                inputs=[image],
            )
            boxes = pb_utils.get_output_tensor_by_name(det_req.exec(), "BOXES")

            # 2. 검출된 박스 "개수만큼" 인식 모델 반복 호출 — ensemble로는 불가능한 부분
            texts = []
            for box in split_boxes(boxes):
                rec_req = pb_utils.InferenceRequest(
                    model_name="recognizer",
                    requested_output_names=["TEXT"],
                    inputs=[box],
                )
                text = pb_utils.get_output_tensor_by_name(rec_req.exec(), "TEXT")
                texts.append(text)

            responses.append(pb_utils.InferenceResponse(output_tensors=[join(texts)]))
        return responses
```

`InferenceRequest(...).exec()`가 다른 모델을 호출하는 부분이다. 동기(`exec()`)·비동기(`async_exec()`) 둘 다 있다. 박스 개수가 데이터에 따라 변해도 `for`가 알아서 돈다 — 이게 ensemble과 결정적으로 다른 점이다.

### 언제 무엇을

- 파이프라인이 **정해진 일직선/고정 갈래** → Ensemble. 코드 없이 config로 끝, 가장 가볍다.
- **데이터에 따라 횟수·경로가 달라짐**(가변 박스 수, 언어별 분기) → BLS. Python이라 자유롭지만 손이 더 간다.

이 대목이 Triton의 트레이드오프를 잘 보여준다. 우리가 Python으로 자유롭게 짜던 파이프라인을, ensemble 설정 문법이나 BLS 규약에 맞춰 다시 구성해야 한다. 대신 얻는 것이 서버 내 오케스트레이션(왕복 제거)과 GPU 상주 텐서다.

## 프로토콜 — KServe v2 기반 gRPC와 HTTP

Triton은 KServe 커뮤니티 표준 추론 프로토콜(v2, Open Inference Protocol)을 기반으로 HTTP/REST와 gRPC를 노출한다. gRPC는 양방향 스트리밍 추론도 지원한다.

이 지점이 실무에서 의미가 크다. 많은 사내 모델 서버가 이미 gRPC로 짜여 있는데, 그건 Triton이 표준으로 제공하는 것을 손으로 구현한 셈이다. Triton으로 옮기면 프로토콜·배칭·인스턴스 관리를 직접 짜는 대신 설정으로 얻는다 — 이 맞바꿈이 도입 판단의 핵심이고, 비교편에서 다시 다룬다.

## Model repository와 warmup

- **Model repository**: 파일시스템 기반 모델 저장소. 로컬 경로뿐 아니라 S3·GCS도 된다.
  - 모델 디렉터리 아래에 숫자 이름의 버전 폴더(`1/`, `2/`)를 두고 그 안에 모델 파일을 넣는다. 버전 관리가 디렉터리 구조로 강제된다.
- **Model warmup**: 첫 실제 요청 전에 더미 추론을 미리 돌려 모델을 완전히 초기화한다. warmup이 끝나기 전엔 모델을 "ready"로 표시하지 않아 첫 요청의 콜드 스타트 지연을 없앤다. 대신 모델 리로드 응답성이 떨어지는 맞교환이 있다.

## 성능 — 공식 수치는 조건을 보고 읽자

Triton 자료에는 "single-digit millisecond latency" 같은 정성 표현이 자주 나오지만, 조건(모델·하드웨어·배치 크기)이 명시된 재현 가능한 벤치마크 표는 공식 소개 페이지에 없다. NVIDIA가 MLPerf Inference 4.1에서 TensorRT-LLM + Triton으로 Llama-2-70B 서빙 결과를 공개했지만, 이 글에서 절대 수치를 단정하진 않겠다.

대신 Triton 철학은 "고정 벤치마크를 믿지 말고 네 워크로드로 직접 재라"에 가깝다. 그래서 `perf_analyzer`와 `Model Analyzer`라는 측정 도구를 제공한다. 동시성·배치 설정을 바꿔가며 최적 구성을 스스로 찾는 방식이다. 우리 OCR 모델의 실제 처리량·지연은 이 도구로 측정하는 것이 후속 과제다.

## 언제 쓰나 / 언제 피하나

**강점**:

- GPU 활용도가 비용에 직결되는 고처리량 서빙. dynamic batching + concurrent execution + TensorRT 결합.
- 여러 프레임워크 모델을 한 서버로 통합 관리.
- 표준 gRPC/HTTP 프로토콜과 버전 관리를 서버가 제공.

**약점 / 피할 상황**:

- Python 전후처리를 편하게 붙이고 싶다 → Python backend나 BLS로 별도 구현해야 해 번거롭다.
- `config.pbtxt` 옵션이 많아 러닝커브가 있다. 빠른 프로토타이핑에는 무겁다.
- CPU-only 환경 → Triton의 핵심 이점(GPU 활용 극대화)이 상대적으로 줄어든다.

한 줄로 요약하면, **모델이 GPU에 얹혀 있고 처리량 한 톨이 아까운 단계에서 Triton이 빛나고, 아직 API 형태와 전후처리를 빠르게 실험하는 단계에서는 무겁다.**

## 다음 편

다음 글에서는 Triton과 정반대 지점에 있는 BentoML을 본다. "GPU를 짜내는 서버"가 아니라 "Python 코드를 API로 빠르게 포장하는 프레임워크"다. 두 글을 읽으면 층위 차이가 선명해지고, 마지막 비교편에서 둘을 조합하는 패턴까지 이어진다.

## 참고 링크

- [Triton Inference Server GitHub](https://github.com/triton-inference-server/server)
- [Model Configuration (dynamic_batching, instance_group)](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html)
- [Batcher 문서](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/batcher.html)
- [Concurrent Model Execution](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_execution.html)
- [Business Logic Scripting (BLS)](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/bls.html)
- [Inference Protocols and APIs (KServe v2)](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/customization_guide/inference_protocols.html)
