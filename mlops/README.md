# MLOps

GPU 기반 ML 서비스를 운영하며 정리한 학습 기록.
CUDA 버전 생태계, GPU 컨테이너 최적화, 모델 서빙 워커 풀, 추론 성능 분석을 묶었다.

## GPU·CUDA 기초

- [Python CUDA 버전 생태계](./cuda-version-ecosystem.md) — nvidia-smi·nvcc·pip·conda가 다 다른 버전을 말하는 이유
- [GPU·CUDA·MPS 기초](./java-to-python-gpu-cuda-mps.md) — 자바 백엔드 개발자가 처음 만나는 그림

## GPU 컨테이너·이미지

- [GPU 컨테이너의 CUDA 버전 호환성](./gpu-container-cuda-driver-compatibility.md) — nvidia-smi부터 이미지 다이어트까지
- [GPU 노드 /run tmpfs 포화](./gpu-node-run-tmpfs-full.md) — 컨테이너 GPU 운영 트러블슈팅

## 모델 서빙·성능

- [Multi-process GPU 워커 풀](./java-to-python-multiprocess-gpu-worker-pool.md) — ThreadPool 사용자가 만나는 프로세스 모델 차이
- [ML 서비스 성능 분석 워크플로](./ml-service-perf-analysis-workflow.md) — 자바 백엔드 트러블슈팅과 다른 점
