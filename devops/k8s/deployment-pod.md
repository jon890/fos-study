# Deployment와 Pod

- 계속해서, ArgoCD를 하향식으로 학습해 나가본다.
- 다음으로는 **Deployment(전략) -> ReplicaSet(관리) -> Pod(실체)** 순서로 내려가게 된다.

<br />

- 백엔드 개발자에게 익숙한 개념으로 비유해보자.
  - **Deployment** : 배포 전략서 (Blue/Green을 할지, Rolling을 할지, 버전은 뭔지)
  - **ReplicaSet** : "인스턴스 개수 유지 장치" (Scale-out 담당)
  - **Pod** : 실제 실행중인 Spring Boot 프로세스

## 1. Pod (파드): K8s의 가장 작은 원자 단위

많은 사람이 "K8s는 컨테이너를 관리한다"고 생각하지만, 사실은 K8s는 **Pod**를 관리한다.

- 개념 : 컨테이너를 감싸고 있는 껍데기이다.
- 특징
  - **1 Pod = 1 IP** : Pod 하나마다 고유한 내부 IP를 할당받는다.
  - **일회용(Ephemeral)** : Pod는 영원하지 않다. 죽으면 **되살리는 게 아니라, 폐기하고 새로운 Pod를 만든다**
  - **다중 컨테이너** : 보통은 `Spring Boot` 컨테이너 1개만 들어가지만, 로그 수집기나 프록시 같은 보조 컨테이너(Sidecar)를 옆에 끼워서 같이 띄울 수도 있다.
    - 이들은 **localhost**로 통신한다.

## 2. ReplicaSet (레플리카셋): 개수를 보장하는 중간 관리자

ArgoCD 화면에서 `api-deployment-xxxxx` 같은 이름으로 여러 개 보였던 녀석들이다.

- **역할**: 무조건 N개를 유지해
- **동작**: 사용자가 "Replicas: 3"이라고 설정하면, 현재 파드가 2개면 1개를 더 만들고, 4개면 1개를 죽인다.
  - 단순 무식하게 숫자를 맞춘다.
- **중요한 점**: 우리는 이 ReplicaSet을 직접 만들지 않는다. **Deployment가 알아서 만든다**

## 3. Deployment: 진정한 관리자 (배포의 핵심)

우리가 작성하는 YAML 파일의 90%는 바로 이 **Deployment**이다.

- **역할**: 앱의 버전 관리와 배포 전략을 담당한다.
- **핵심 기능**:
  - 배포 이력 관리 : ArgoCD에서 본 회색 박스(과거 ReplicaSet)을 보관하고 있어, 언제든 롤백이 가능하다.
  - 무중단 배포 : 기존 Pod를 하나씩 죽이면서, 새 버전 Pod를 하나씩 띄우는 과정을 쥐휘한다.

## 4. 실제 YAML 뜯어보기

이제 "Deployment"가 어떻게 생겼는지 코드로 보자. <br />
주석을 통해 각 설정이 Spring Boot 앱에 어떤 영향을 주는지 설명해 두었다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api # 앱 이름
spec:
  replicas: 2 # 서버 2대 띄워줘 (Scale-out)
  selector:
    matchLabels:
      app: api # 이 라벨이 붙은 Pod를 관리할게
  template:
    metadata:
      labels:
        app: api
  spec:
    containers:
      - name: api-container
        image: my-repo/api:v2.0.0 # 배포할 버전
        ports:
          - containerPort: 8080

        # 중요! 헬스 체크 (이게 없으면 배포 중 에러 나도 보름)
        readinessProbe: # 요청 받은 준비 됐는지 확인
          httpGet:
            path: /actuator/health
            port: 8080
          initialDelaySeconds: 30 # 앱 뜨는데 30초 기다려줘
        livenssProbe:
          httpGet:
            path: /actuator/health
            port: 8080
```

## 5. 배포의 마법: Rolling Update 과정

개발자가 이미지 태그를 `v1`에서 `v2`로 바꾸고 `kubectl apply`를 하면 무슨 일이 벌어질까?

1. **Deployment**가 "어? 버전이 바뀌었네?"라고 감지한다.
2. **Deployment**는 **새로운 ReplicaSet (v2용)**을 만든다. (아직 Pod 개수는 0)
3. **Deployment**가 새 RS에게 "Pod 1개 만들어봐"라고 시킨다. -> v2 Pod 1개 생성
4. 새 Pod가 `ReadinessProbe` (헬스 체크)를 통과해서 "준비 완료" 상태가 되면,
5. **Deployment**는 **기존 RS (v1용)**에게 "Pod를 1개 줄여"라고 시킨다. -> v1 Pod 1개 삭제
6. 이 과정을 목표 개수 (Replicas: 2)가 될 떄까지 반복한다.
7. **결과**: 사용자는 다운타임 없이 v1에서 v2로 자연스럽게 넘어간다.
