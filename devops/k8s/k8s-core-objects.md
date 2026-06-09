# 쿠버네티스 핵심 객체 4종 — Pod, Service, Ingress, Namespace의 관계

쿠버네티스에서 외부 노출 작업을 하다가, Pod니 Service니 Ingress니 하는 단어들이 머릿속에서 자꾸 섞였다. 각각 뉘앙스는 알겠는데 "그래서 이것들이 서로 어떤 관계냐"가 안 잡혔다. 그래서 이 네 가지를 한 번에 정리하기로 했다. 이 네 개의 관계만 잡으면 쿠버네티스의 절반은 이해한 거라고 봐도 된다.

Service와 Ingress의 기본 정의는 [Service와 Ingress](./service-ingress.md)에 따로 정리했으니, 이 글은 네 객체를 **관계 중심**으로 묶어서 본다.

## 한 장으로 보는 관계

먼저 그림부터. 어떤 앱(`api`)을 외부에 노출하는 상황을 예로 들면 이렇게 생겼다.

```
Namespace: app  ← 이 모든 게 담긴 구획
┌────────────────────────────────────────────────────┐
│ Ingress: api-ingress                                │
│    규칙: "/api 로 온 요청 → api-service 로 보내라"      │
│            │                                         │
│            ▼                                         │
│ Service: api-service (ClusterIP, 고정)               │
│    selector: app=api  ← 이 label 가진 Pod 를 고름      │
│            │                                         │
│            ▼ (Endpoints = 살아있는 Pod IP 목록 자동관리) │
│            ▼                                         │
│ Pod: api-xxxx (label app=api)                       │
│ Pod: api-yyyy (label app=api)                       │
│    실제 앱이 도는 곳                                   │
└────────────────────────────────────────────────────┘
```

핵심은 두 가지다. 하나, **위로 갈수록 안정적이고 추상적이며, 아래로 갈수록 불안정하고 구체적**이다. 둘, **Service가 label로 Pod를 골라서 둘을 잇는다.** 이 두 가지만 기억하면 나머지는 따라온다.

## Pod — 실제 앱이 도는 가장 작은 단위

Pod는 컨테이너 한 개 이상을 묶은, 쿠버네티스가 배포하고 실행하는 가장 작은 단위다. 보통 컨테이너 하나(내 앱)지만, 사이드카 패턴이면 여러 개가 한 Pod에 들어가기도 한다. 같은 Pod 안 컨테이너끼리는 `localhost`와 스토리지를 공유한다.

Pod의 가장 중요한 성질은 **일회용**이라는 점이다. 배포할 때마다, 재시작할 때마다, 노드를 옮길 때마다 죽고 새로 태어난다. 그리고 새로 태어날 때마다 **IP가 바뀐다.** 이름도 끝에 붙은 해시가 매번 달라진다.

그래서 Pod는 보통 직접 만들지 않는다. **Deployment**가 "이 앱을 항상 2개 띄워둬라" 같은 식으로 관리하고, Pod가 죽으면 알아서 새로 띄운다. 내가 직접 챙기는 게 아니라, 원하는 상태를 선언하면 쿠버네티스가 맞춰주는 식이다.

IP가 계속 바뀌니까, **누구도 Pod IP를 직접 부를 수 없다.** 프론트엔드나 다른 서비스가 매번 바뀌는 IP를 쫓아다닐 수는 없으니까. 여기서 Service가 등장한다.

## Service — 변하지 않는 진입점

Service는 Pod 묶음 앞에 세우는 **고정된 IP와 고정된 DNS 이름**이다. Pod가 아무리 죽고 새로 떠도 이 IP는 변하지 않는다. 비유하면 Pod는 자주 자리를 옮기는 직원이고, Service는 바뀌지 않는 부서 대표번호다.

Service가 Pod를 어떻게 찾을까? **label selector**다.

```yaml
spec:
  type: ClusterIP
  selector:
    app: api   # 이 label 을 가진 Pod 들에게 트래픽을 보낸다
```

`selector: app=api`는 "이 label을 가진 Pod들에게 트래픽을 보내라"는 뜻이다. Pod에 `app=api` label이 붙어 있으면 이 Service에 자동으로 묶인다. 내가 Pod IP를 일일이 등록하는 게 아니라, label이 맞는 Pod를 쿠버네티스가 알아서 모아준다.

그 "모아준 결과"가 **Endpoints**다. Service는 selector에 맞는 **살아있는 Pod IP 목록**을 실시간으로 관리한다. Pod가 죽으면 목록에서 빼고, 새로 뜨면 추가한다. 그래서 Service로 보낸 요청은 항상 살아있는 Pod로만 간다. 들어온 요청은 여러 Pod에 로드밸런싱으로 분배된다.

타입 `ClusterIP`는 **클러스터 내부 전용**이다. 외부에서는 못 닿는다. 외부 노출은 LoadBalancer 타입이나 Ingress가 필요한데, 그 얘기는 [외부 트래픽이 Pod까지 닿는 경로](./external-traffic-path.md)에 정리해뒀다.

## Ingress — 외부에서 Service로 가는 라우팅 규칙

Ingress는 **"어느 도메인의 어느 경로를 어느 Service로 보낼지"**를 적은 HTTP 라우팅 규칙이다. `/api`로 온 요청은 `api-service`로, `/admin`으로 온 요청은 `admin-service`로 보내는 식이다.

여기서 헷갈리기 쉬운 게 하나 있다. **Ingress는 규칙(YAML)일 뿐, 그 규칙을 실제로 실행하는 건 Ingress Controller**다. Ingress 리소스만 만들어두고 Controller가 없으면 아무 일도 안 일어난다. 안내판(Ingress)을 붙여놨는데 안내데스크 직원(Controller)이 없는 셈이다.

그리고 Ingress는 백엔드로 **Pod가 아니라 Service를 이름으로** 가리킨다. Pod는 불안정하니 당연히 안정적인 Service를 가리키는 거다. 여기서도 "불안정한 건 안정적인 것 뒤에 숨긴다"는 패턴이 반복된다.

## Namespace — 리소스를 담는 논리적 구획

Namespace는 클러스터를 논리적으로 나누는 **가상 구획**이다. 일종의 폴더라고 보면 된다. 한 클러스터 안에서 용도별로 리소스를 나눠 담는다 — 앱은 `app` 네임스페이스, 모니터링은 `monitoring`, ingress controller는 `ingress-nginx` 같은 식이다.

Namespace가 주는 것:

- **이름 충돌 방지** — 리소스 이름은 같은 namespace 안에서만 유일하면 된다. 다른 namespace엔 같은 이름이 있어도 괜찮다.
- **권한 경계(RBAC)** — "이 팀은 이 namespace에만 접근" 같은 권한을 namespace 단위로 건다.
- **자원 할당 경계(ResourceQuota)** — "이 namespace는 CPU 몇 개까지" 같은 제한을 건다.

## namespaced vs cluster-scoped — 모든 리소스가 namespace에 속하진 않는다

여기서 중요한 구분이 하나 있다. 쿠버네티스 리소스는 두 종류로 나뉜다.

| 구분 | 예시 | 의미 |
|---|---|---|
| **namespaced** | Pod, Service, Ingress, Deployment | namespace에 **속한다**. `app` ns의 Pod와 다른 ns의 Pod는 별개 |
| **cluster-scoped** | Node, IngressClass, ValidatingWebhookConfiguration | namespace 없이 **클러스터 전역**. 모두가 공유 |

이 구분이 왜 중요하냐면, 실제 운영에서 직접 부딪히기 때문이다. 예를 들어 **IngressClass**(어떤 Controller가 어떤 Ingress를 처리할지 정하는 것)는 cluster-scoped라, 어느 namespace의 Ingress든 같은 class를 가리킬 수 있다.

더 중요한 건 **admission webhook**(`ValidatingWebhookConfiguration`)이다. 이것도 cluster-scoped라서, namespace로도 class로도 격리가 안 되고 **클러스터 전체의 리소스 요청을 가로챈다.** 이 성질 때문에 ingress controller를 둘로 나눌 때 예상 못 한 함정이 생기는데, 그건 [ingress-nginx 운영에서 부딪힌 디테일들](./ingress-nginx-operations.md)에서 자세히 다뤘다.

## 관계 요약

네 객체를 한 문장으로 묶으면 이렇게 된다.

**"Namespace라는 구획 안에서, 불안정한 Pod를 Service가 안정적으로 감싸고, Ingress가 외부 트래픽을 그 Service로 흘려보낸다."**

각 관계를 따로 떼면:

- **포함**: Namespace ⊃ {Pod, Service, Ingress} — 구획 안에 담긴다
- **트래픽 흐름**: Ingress → Service → Pod — 외부에서 안으로
- **선택**: Service가 label selector로 Pod를 고른다
- **추상화 사다리**: Pod(불안정한 실체) → Service(안정 진입점) → Ingress(외부 라우팅)

처음엔 객체가 많아서 복잡해 보였는데, "불안정한 걸 안정적인 것 뒤에 숨긴다"는 한 가지 패턴이 계속 반복된다는 걸 알고 나니 한결 단순해졌다. Pod를 Service 뒤에 숨기고, Service를 Ingress 뒤에 숨기는 식이다.

## 관련 글

- [Service와 Ingress](./service-ingress.md) — 두 객체의 기본 정의
- [외부 트래픽이 Pod까지 닿는 경로](./external-traffic-path.md) — LoadBalancer부터 Pod까지 전체 경로
- [ingress-nginx 운영에서 부딪힌 디테일들](./ingress-nginx-operations.md) — cluster-scoped webhook이 만드는 함정
