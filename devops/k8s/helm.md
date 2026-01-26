# Helm

- k8s의 **Gradle**
- Gradle이 `.jar` 파일을 관리한다면, Helm은 **k8s yaml 파일 뭉치(Chart)**를 관리한다.
- 개발자 입장에서 Helm이 해결해 주는 핵심 문제는 바로 **하드코딩 제거**와 **재사용성**이다.

## 1. 왜 Helm이 필요한가요?

Helm 없이 k8s를 운영하면 "복붙의 지옥"에 빠진다.

- 상황 : `api` 서비스를 Alpha, Beta, Real 환경에 배포해야 한다고 하자.
- 문제 : 3개 환경은 구조 (Deployment, Service)는 똑같은데, **설정값(변수)**만 다르다.
  - 예시 :
    - Alpha: Replicas=1, CPU=0.5
    - Real : Replicas=10, CPU=4.0
- Helm이 없을 떄 : `deployment-alpha.yaml`, `deployment-beta.yaml`, `deployment-real.yaml` 파일을 3개 복사해서 관리해야 한다.

## 2. Helm의 해결책 : 템플릿 엔진

Helm은 이 문제를 **템플릿(Template)**과 **설정값(Values)**의 분리로 해결한다.

- 백엔드에서 **JSP**나 **Thymeleaf**를 생각하면 된다.
- **Chart(템플릿)**
  - 변수 처리된 yaml 파일이다. Go Template 문법을 사용한다.
  ```yaml
  # deployment.yaml (Helm Template)
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: { { .Values.appName } }
  spec:
    replicas: { { .Values.replicaCount } }
  ```
- **Values(설정값)**
  - 환경별로 달라지는 값만 따로 모아둔 파일
  ```yaml
  # values-real.yaml
  appNAme: api-real
  replicaCount: 10
  ```
- **Release(결과물)**
  - Helm 명령어를 실행하면 템플릿에 값을 채워 최종 yaml을 생성하고 k8s에 배포한다
  ```sh
  helm install -f values-real.yaml
  ```

## 3. Package Manager로서의 기능

Maven Repository에서 라이브러리를 가져오듯, 남들이 잘 만들어둔 k8s 설정(Redis, MySQL, Jenkins, Promethus 등)을 명령어 한 줄로 설치할 수 있다

- Linux : `apt-get install nginx`
- Helm : `helm install my-nginx bitnami/nginx`

내가 처음부터 Nginx용 Service, Deployment, ConfigMap YAML을 짤 필요 없이, 검증된 패키지를 다운받아 설치만 하면 끝이다.
