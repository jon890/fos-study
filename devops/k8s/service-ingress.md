# Service와 Ingress

- Deployment가 서버를 띄우고 관리하는 것이라면, **Service와 Ingress**는 "그 서버로 가는 길을 뚫어주는 것(Networking)"이다.
- 딱 한 문장으로 정의하고 시작하면 이해가 빠를 것이다.

> Pod는 변수(Variable)고, Service는 상수(Constants)이다.

## 1. Service (서비스): 변하지 않는 연락처 (L4)

### 왜 필요한가?

Pod는 일회용이다. 배포할 떄마다 죽고 새로 태어나며, 그때마다 **IP 주소가 바뀐다.** <br />
프론트엔드나 다른 MSA 서비스가 자꾸 바뀌는 IP를 추적해서 호출할 수는 없다.

### 해결책: Service

Pod 앞단에 **고정된 IP(Cluster IP)**와 **고정된 도메인 이름(DNS)**을 부여하는 **내부 로드밸런서**이다.

- **동작 방식**: 내 뒤에 있는 Pod들(Selector)에게 트래픽을 `Round Robin`으로 뿌려줘
- **개발자 비유**:
  - **Pod IP**: 개발자 개인 내선 번호
  - **Service**: 개발팀 대표 번호
- **특징**:
  - **Service Discovery**: K8s 내부에서는 IP 대신 `http://api` 처럼 서비스 이름만으로 통신할 수 있다.
    - 내부 DNS가 `api` -> `10.96.0.1`로 해석해준다.

### YAML로 확인하기

가장 중요한 건 **selector** 이다. 이게 Deployment의 라벨과 일치해야 연결된다.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service # 내부에서 부를 이름 (DNS)
spec:
  type: ClusterIP # 내부 전용
  selector:
    app: api # (중요) 이 라벨을 가진 Pod들로 트래픽을 보냄
  ports:
    - protocol: TCP
      port: 80 # 서비스의 포트
      targetPort: 8080 # Pod의 포트
```

## 2. Ingress(인그레스): 외부로 통하는 대문 (L7)

### 왜 필요한가?

**Service**는 기본적으로 **K8s 클러스터 내부**에서만 접근 가능하다. (보안상 안전) <br />
하지만 외부 사용자는 우리 API를 호출해야 한다. 게다가 도메인도 연결해야 하고, HTTPS 인증서도 붙여야 한다.

### 해결책: Ingress

외부에서 들어오는 HTTP(S) 트래픽을 규칙에 따라 적절한 **Service**로 라우팅해주는 **L7 리버스 프록시 설정**이다.

- **구성 요소**:
  - **Ingress (주문서)**: `my-service.com/api`는 api 서비스로 보내줘라고 적힌 YAML.
  - **Ingress Controller (실행자)**: 실제 Nginx 서버(Pod). 주문서(Ingress YAML)를 읽어서 `nginx.conf₩를 동적으로 고치고 트래픽을 처리한다.
- **개발자 비유**:
  - **Service**: 각 부서의 안내 데스크
  - **Ingress**: 건물 1층의 통합 로비 & 보안 게이트
- **기능**:
  - 도메인 기반 라우팅
  - 경로(Path) 기반 라우팅 (`/api`, `/admin`)
  - SSL/TLS 종료

### YAML로 확인하기

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: `api-ingress`
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: / # Ngnix 세부 설정
spec:
  rules:
  - host: my-service.com # 1. 이 도메인으로 들어오면
    http:
      paths:
        - path: /api # 2. 그리고 /api 경로로 들어오면
          pathType: Prefix
          backend:
            service:
              name: api-service # 3. 이 서비스로 보내라
              port:
                number: 80

```

## 3. 전체 흐름도: 트래픽은 어떻게 흐르는가?

이제 Deployment, Service, Ingress가 합쳐졌을 떄, 사용자의 요청이 Spring Boot까지 도달하는 여정이다.

- **1. User Request**: 사용자가 브라우저에;서 `https://my-service.com/api/v1/hello` 호출
- **2. Ingress (Nginx):**
  - 도메인과 경로를 확인한다.
  - 설정된 규칙에 따라 `api-service`를 찾는다.
- **3. Service:**
  - `api-service`는 자신의 목록(Endpoints)에 살아있는 **Pod IP 중 하나**를 선택한다.
- **4. Pod(Spring Boot):**
  - 최종적으로 요청을 받아 처리하고 응답한다.
