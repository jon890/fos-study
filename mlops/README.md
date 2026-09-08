# MLOps

GPU 기반 ML 서비스를 운영하며 정리한 학습 기록.
CUDA 버전 생태계, GPU 컨테이너 최적화, 모델 서빙 워커 풀, 추론 성능 분석을 묶었다.

## GPU·CUDA 기초

- [Python CUDA 버전 생태계](./cuda-version-ecosystem.md) — nvidia-smi·nvcc·pip·conda가 다 다른 버전을 말하는 이유
- [GPU·CUDA·MPS 기초](./java-to-python-gpu-cuda-mps.md) — 자바 백엔드 개발자가 처음 만나는 그림
- [한 GPU 를 여러 프로세스가 나눠 쓰기 — Time-Slicing 과 MPS](./multi-process-gpu-mps.md) — 한 GPU 를 여러 프로세스가 공유하는 두 방식과 트레이드오프

## GPU 컨테이너·이미지

- [GPU 컨테이너의 CUDA 버전 호환성](./gpu-container-cuda-driver-compatibility.md) — nvidia-smi부터 이미지 다이어트까지
- [GPU 노드 /run tmpfs 포화](./gpu-node-run-tmpfs-full.md) — 컨테이너 GPU 운영 트러블슈팅

## 모델 서빙·성능

- [Multi-process GPU 워커 풀](./java-to-python-multiprocess-gpu-worker-pool.md) — ThreadPool 사용자가 만나는 프로세스 모델 차이
- [ML 서비스 성능 분석 워크플로](./ml-service-perf-analysis-workflow.md) — 자바 백엔드 트러블슈팅과 다른 점

## 추론 서빙 프레임워크 비교 (시리즈)

Triton, BentoML, Ray Serve를 층위별로 비교한 스터디 시리즈. OCR 추론 서빙에 어느 프레임워크가 적절한지 판단하기 위한 기록이다.

- [Triton Inference Server](./serving-frameworks/triton-inference-server.md) — GPU 추론을 짜내는 모델 실행 런타임
- [BentoML](./serving-frameworks/bentoml.md) — Python 코드를 프로덕션 API로 포장하는 프레임워크
- [Ray Serve](./serving-frameworks/ray-serve.md) — 여러 모델을 분산·오토스케일하는 오케스트레이션 층
- [Triton vs BentoML vs Ray Serve](./serving-frameworks/triton-vs-bentoml-vs-ray.md) — 층이 다른 셋을 어떻게 고르나

## Model Router (시리즈)

모델 호출이 지나는 한 지점에서 어느 모델과 어느 인스턴스로 보낼지 정하는 계층을 정리한 스터디 시리즈. 관리형 라우터로 충분한 구간과 자체 구축으로 넘어가는 조건을 가르기 위한 기록이다.

- [Model Router 란 무엇인가](./model-router/what-is-model-router.md) — 모델을 고르는 계층과 인스턴스를 고르는 계층
- [어느 모델로 보낼지 무엇으로 정하는가](./model-router/routing-criteria-and-cost.md) — 판단 방식 넷과 그 판단에 드는 시간
- [모델을 골라주는 계층이 대신 가져오는 제약](./model-router/router-constraints.md) — 컨텍스트 한도, 대상 목록 고정, 결정 추적, 캐시와의 충돌
- [캐시를 보고 인스턴스를 고른다](./model-router/cache-aware-routing.md) — prefix aware 와 KV cache aware 의 차이
- [첫 토큰이 나간 뒤에는 재시도할 수 없다](./model-router/streaming-retry-boundary.md) — streaming 중 장애의 재시도 경계
- [LiteLLM 로 라우팅 정책을 설정하는 방법](./model-router/litellm-routing-strategies.md) — 라우팅 전략, fallback, cooldown, 예산
- [vLLM 지표를 라우팅 판단에 쓰는 방법](./model-router/vllm-metrics-for-routing.md) — 요청 경로에서 볼 값과 사후 진단에 쓸 값
- [같은 문제를 회사마다 다른 층에서 푼다](./model-router/industry-cases.md) — 토스증권, Netflix, Uber, KT 의 계층 경계
