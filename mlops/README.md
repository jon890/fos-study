# MLOps

## GPU 로 LLM 서빙하기

Java 백엔드 개발자가 GPU와 CUDA에서 출발해 LLM 서버 한 대의 동작을 익힌 뒤, 여러 모델로 요청을 보내고 운영 병목을 분석하는 순서다.

### GPU와 CUDA 기초

1. [GPU·CUDA·MPS 기초](./java-to-python-gpu-cuda-mps.md) · CPU와 GPU는 어떤 일을 나눠 맡고, VRAM은 어떻게 확인하는가?
2. [Python CUDA 버전 생태계](./cuda-version-ecosystem.md) · 왜 드라이버, 툴킷, PyTorch가 서로 다른 CUDA 버전을 표시하는가?
3. [GPU 컨테이너의 CUDA 버전 호환성](./gpu-container-cuda-driver-compatibility.md) · 호스트 드라이버와 컨테이너 속 CUDA 런타임은 어떤 조건에서 함께 동작하는가?
4. [한 GPU를 여러 프로세스가 나눠 쓰기](./multi-process-gpu-mps.md) · Time-Slicing과 MPS로 GPU를 나눠 쓰면 무엇이 달라지는가?
5. [Multi-process GPU 워크로드](./java-to-python-multiprocess-gpu-worker-pool.md) · Java의 ThreadPool과 GPU 프로세스 풀은 모델을 올리고 워커를 다시 띄우는 방식이 어떻게 다른가?

### LLM 서버 한 대에서 요청이 도는 방식

6. [GPU로 LLM을 서빙한다는 것](./llm-serving/gpu-llm-serving-basics.md) · 입력을 읽는 단계와 출력을 만드는 단계는 각각 어디에서 느려지는가?
7. [배칭과 GPU 활용률](./llm-serving/continuous-batching-gpu-utilization.md) · 완료된 자리를 다음 요청으로 채우면 GPU 처리량이 왜 늘어나는가?
8. [vLLM 서버 옵션 지도](./llm-serving/vllm-serving-options.md) · 요청이 들어와 토큰이 나갈 때까지 각 옵션은 어디에 개입하는가?
9. [vLLM의 스케줄러 루프가 CPU에 묶이면 왜 GPU가 쉬는가](./llm-serving/vllm-cpu-bound-scheduler.md) · 같은 배치의 다른 응답도 토큰이 늦어질 때 무엇을 확인하는가?
10. [vLLM prefix cache를 살리는 프롬프트 배치](./llm-serving/vllm-prefix-cache-prompt-layout.md) · 에이전트가 탐색과 작성을 나눠 호출할 때 공통 입력을 어디까지 재사용할 수 있는가?
11. [추측 디코딩과 vLLM 적응형 검증](./llm-serving/speculative-decoding-adaptive-verification.md) · 초안 토큰을 한 번에 여러 개 검증하는 방식은 어떤 부하에서 이득인가?

### 여러 모델과 인스턴스에 요청 보내기

12. [Model Router 란 무엇인가](./model-router/what-is-model-router.md) · 모델을 고르는 것과 같은 모델의 인스턴스를 고르는 일은 어떻게 다른가?
13. [어느 모델로 보낼지 무엇으로 정하는가](./model-router/routing-criteria-and-cost.md) · 요청에 맞는 모델을 고르는 판단 자체에는 얼마만큼의 비용이 드는가?
14. [모델을 골라주는 계층이 대신 가져오는 제약](./model-router/router-constraints.md) · 라우터를 넣으면 문맥 길이, 모델 목록과 응답 추적에 어떤 제약이 생기는가?
15. [캐시를 보고 인스턴스를 고른다](./model-router/cache-aware-routing.md) · 비슷한 요청을 같은 서버로 보내는 방식과 실제 캐시 상태를 보고 고르는 방식은 어떻게 다른가?
16. [첫 토큰이 나간 뒤에는 재시도할 수 없다](./model-router/streaming-retry-boundary.md) · 스트리밍 중 장애가 나면 어느 시점까지 다시 호출할 수 있는가?
17. [LiteLLM 로 라우팅 정책을 설정하는 방법](./model-router/litellm-routing-strategies.md) · 분산, 실패 시 우회, 일시 제외와 예산을 실제 설정으로 어떻게 옮기는가?
18. [vLLM 지표를 라우팅 판단에 쓰는 방법](./model-router/vllm-metrics-for-routing.md) · 요청을 보낼 때 쓸 지표와 느려진 뒤 원인을 찾는 지표를 어떻게 구분하는가?
19. [같은 문제를 회사마다 다른 층에서 푼다](./model-router/industry-cases.md) · 공개 사례에서 모델 선택과 인스턴스 선택은 각각 어느 계층이 맡는가?

### 운영과 성능 분석

20. [Kubernetes GPU 노드에서 /run tmpfs가 꽉 차서 Pod가 안 뜰 때](./gpu-node-run-tmpfs-full.md) · GPU 메모리가 남아 있는데도 Pod가 뜨지 않으면 노드의 어디를 살피는가?
21. [ML 서비스 성능 분석 워크플로](./ml-service-perf-analysis-workflow.md) · Python 워커, GPU와 외부 호출을 오가는 요청의 병목을 어떻게 검증하는가?
