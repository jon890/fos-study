# Python

자바 백엔드 개발자가 Python 기반 ML 서비스를 분석하며 정리한 학습 기록. 문법부터 PyTorch·OCR 기초까지 시리즈로 묶었다.
GPU·CUDA·모델 서빙 운영은 [mlops](../mlops/README.md) 카테고리로 옮겼다.

## Java 개발자를 위한 Python 시리즈

1. [Python 문법 핵심](./java-to-python-syntax.md) — 자바 개발자가 Python 코드를 빨리 읽기 위한 차이점
2. [OOP·데코레이터·컨텍스트 매니저](./java-to-python-oop-decorator.md) — record·Lombok·annotation·`AutoCloseable`·`Iterator` 비교
3. [의존성 관리](./java-to-python-dependency-management.md) — Maven/Gradle 사용자가 만나는 첫 충격, uv 중심
4. [FastAPI 기초](./java-to-python-fastapi-basics.md) — Spring Boot 사용자가 빠르게 익히는 법
5. [async/await 와 blocking I/O 함정](./java-to-python-async-blocking-io.md) — CompletableFuture·Reactor 와 다른 점
6. [PyTorch 기초 — 텐서·모델 로딩 비용](./java-to-python-pytorch-tensor-model-loading.md) — 모델 로딩이 무거운 이유
7. [OCR 동작 원리](./ocr-pipeline-basics.md) — Layout · Text · Post-process 3단계

## 성능 트러블슈팅

- [Python 서버의 RSS 가 안 줄어드는 이유](./python-rss-leak-glibc-malloc-trim.md) — gc.collect 의 한계와 malloc_trim
