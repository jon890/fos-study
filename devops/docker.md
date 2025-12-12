# Docker 기본기 학습

## 1. Docker가 무엇인가?

> 리눅스의 Namespace + Cgroups 기반으로 컨테이너를 쉽게 만들고 실행하고 배포하도록 도와주는 플랫폼

우리가 직접 컨테이너를 만드려면

- Namespace 생성
- Cgroup 설정
- 파일시스템 구성
- 프로세스 실행

등을 직접 해야 하는데, 도커가 이 모든 과정을 지능적으로 자동화해주는 도구

## 2. Docker의 핵심 구성 요소들

K8s를 하기 위해 반드시 알아야 할 개념은 아래 6개다

1. Docker Image
2. Docker Container
3. Dockerfile
4. Docker Daemon & Engine
5. Docker Registry
6. Storage (Layer / OverlayFS)

이걸 순서대로 자세히 풀어보자

### 2.1 Docker Image - 실행 환경을 묶어놓은 "불변 템플릿"

이미지는 **컨테이너를 실행하기 위한 모든 것이 담긴 스냅샷**

- OS 최소 구성 (알파인, 우분투 등)
- 라이브러리, 런타임 (JDK, Node)
- 애플리케이션 코드
- 의존성 파일

> 즉, Image = 실행을 위한 전체 Runtime + App이 포함된 읽기 전용 파일 시스템

#### 특징

- Immutable (불변) -> 변경할 수 없음
- 여러 "Layer"로 구성됨
- 동일 이미지로 컨테이너를 여러 개 생성 가능

### 2.2 Docker Container - Image를 실행한 "프로세스"

컨테이너는 이미지 기반으로 실행되는 **격리된 프로세스**

- 자체 네트워크 인터페이스
- 자체 PID
- 자체 filesystem (image + writable layer)
- 자체 환경변수/env 파일

컨테이너는 VM이 아님, OS 커널을 공유하지만 **각각 독립된 환경을 가진 프로세스처럼 동작**

### 2.3 Dockerfile - 이미지 생성 레시피

이미지를 만드는 설정 파일
예시 : Spring Boot 이미지 예제

```dockerfile
FROM eclipse-tmurin:21-jre
WORKDIR /app
COPY build/libs/app.jar app.jar
ENTRYPOINT ["java", "-jar", "app.jar"]
```

#### Dockerfile에서 중요한 개념들

- FROM : base image (계층의 시작)
- COPY / ADD
- RUN : 이미지 빌드 시 실행되는 명령
- CMD / ENTRYPOINT : 컨테이너 실행 시 실행되는 프로세스
- WORKDIR : 작업 디렉토리
- ENV : 환경변수 설정
- EXPOSE : 문서적인 포트 표기 (실제 매핑 아님)

K8s에 올릴 때는 ENTRYPOINT / CMD가 필수적 역할을 하니까 꼭 알아둬야 함

### 2.4 Docker Daemon & Docker Engine

도커의 내부 구조는 이렇다

| Component                 | 역할                                                              |
| ------------------------- | ----------------------------------------------------------------- |
| Docker Daemon (`dockerd`) | 컨테이너 생성, 삭제, 네트워크 관리, 이미지 빌드 등 모든 기능 담당 |
| Docker CLI                | 우리가 쓰는 `docker run`, `docker build` 명령                     |
| Docker Engine API         | CLI가 dockerd와 통신하는 API 레이어                               |

즉 CLI는 그냥 요청을 보내는 클라이언트고 **dockerd가 모든 일을 처리하는 백엔드 프로세스**
이 구조는 K8s의 kubelet과도 연결됨

### 2.5 Docker Registry - 이미지 저장소

컨테이너 이미지를 저장해두는 공간
종류:

- Docker Hub (공개)
- GitHub Container Registry
- AWS ECR / GCP GCR / Azure ACR (클라우드)
- 사내 Private Registry

K8s에서 `Deployment`의 `image: xxx`는 레지스트리에서 이미지를 끌어오는 것

### 2.6 Docker Storage - Layer 기반 구조

도커 이미지의 핵심은 **레이어(layer)** 구조

#### 이미지 레이어 구조

```bash
FROM openjdk:21    (layer 1)
COPY app.jar /app  (layer 2)
RUN chmod +x /app  (layer 3)
```

각 명령이 하나의 레이어로 저장됨. 따라서 변경된 레이어만 다시 빌드되므로 **캐싱이 매우 빠르다**

#### OverlayFS (도커 파일 시스탬)

컨테이너 실행 시

- 기반 이미지는 읽기 전용
- 컨테이너는 별도의 writable 레이어 생성

> 즉, 이미지는 불변, 컨테이너는 변경 가능 레이어만 따로 유지

이 구조가 도커를 매우 가볍고 빠르게 만듬

## 3. Docker 네트워크 구성도 빠르게 짚기

쿠버네티스를 이해하려면 Docker 네트워크 모델도 기본적으로 알아야 함

도커 네트워크 종류

- **1. bridge (기본)**
  - `docker0` 브리지 네트워크
  - 컨테이너끼리 내부 IP로 통신 가능
- **2. host**
  - 호스트와 같은 네트워크 스택 사용
- **3. none**
  - 네트워크 없음

쿠버네티스는 자체 CNI(Container Network Interface)를 사용하여, 도커의 네트워크 구조를 완전히 대체함
