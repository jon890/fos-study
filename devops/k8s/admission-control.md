---
series: "백엔드 개발자를 위한 쿠버네티스 기본기"
seriesOrder: 5
thumbnail: ./images/admission-control-thumbnail.jpg
tags: [study]
---

# 쿠버네티스 Admission 단계 — 리소스가 etcd에 저장되기 직전에 무슨 일이 일어나는가

`kubectl apply`를 하면 리소스가 클러스터에 "생긴다". 그런데 그 사이에 뭐가 있는지는 오래 몰랐다. 공인 LoadBalancer를 붙이면서 ingress controller를 내부용·외부용으로 나눴는데, "새 Ingress를 만들면 admission webhook이 검증한다"는 문장이 계속 나왔다. admission이 정확히 어느 단계고, 왜 하필 "저장 직전"인지 짚고 넘어가지 않으면 self-lock 같은 사고를 이해할 수 없었다.

한 줄로 먼저 말하면 — **admission은 kube-apiserver가 요청받은 객체를 etcd에 저장하기 직전에 검문·변형하는 단계**다. 여기서 거부되면 객체는 etcd에 저장조차 안 되고, 그래서 controller도 그 객체를 영영 보지 못한다. 이 "저장 직전"이라는 위치가 핵심이라, 이 글은 apiserver 요청 파이프라인에서 admission이 어디 앉아 있는지부터 정리한다.

## kube-apiserver 요청 파이프라인

`kubectl`이든 ArgoCD든, 클러스터에 뭔가를 바꾸는 요청은 전부 kube-apiserver 하나를 거친다. 그 요청이 처리되는 순서는 이렇다.

요청(kubectl · ArgoCD · controller)이 kube-apiserver에 들어오면 순서대로 처리된다.

1. **Authentication** — 너 누구냐. 인증서·토큰·서비스어카운트로 신원 확인
2. **Authorization** — 이거 할 권한 있냐. RBAC 검사
3. **Admission Control** — 이 글의 주제. 안에서 또 세 단계로 나뉜다
    1. Mutating admission — 객체를 변형한다 (기본값 주입, sidecar 삽입)
    2. Object schema 검증 — OpenAPI 스키마에 맞는지 본다
    3. Validating admission — 객체를 검증하고, 통과 못 하면 거부한다
4. **etcd 저장** — 이제서야 클러스터에 존재하게 된다
5. **controller가 감지** — 실제 반영. nginx reload, Pod 생성 등

인증(누구냐)과 권한(되냐)을 통과한 다음, **저장되기 직전**에 admission이 낀다. 그리고 실제로 뭔가가 동작하는 건(nginx가 설정을 다시 읽거나, Pod가 뜨거나) 그보다도 뒤인 5번, controller가 etcd에 저장된 객체를 보고 나서다.

이 순서를 눈에 넣어두면 두 가지가 분명해진다.

- admission에서 거부되면 객체는 **4번(etcd)에 못 간다.** 클러스터에 존재한 적이 없으니 5번 controller도 못 본다. `kubectl`은 그 자리에서 에러를 받는다.
- 반대로 이미 5번까지 가서 돌고 있는 기존 객체(예: 지금 트래픽을 받고 있는 Ingress)는 admission과 **무관하다.** admission은 "새로 들어오는 요청"만 검문하는 문지기지, 이미 안에 있는 것들을 건드리지 않는다.

두 번째가 실무에서 특히 중요했다. 운영 중인 서비스에 새 Ingress를 하나 추가할 때 "기존 트래픽이 끊기나?"를 걱정했는데, admission은 신규 객체의 등록 여부만 판정할 뿐 돌고 있는 것에 손대지 않는다. 그래서 순수하게 추가만 하는 변경은 기존 경로에 영향이 없다.

## Mutating vs Validating — 변형이냐 검증이냐

admission은 두 종류로 갈린다. 순서대로 mutating이 먼저, validating이 나중이다.

- **Mutating** — 저장 전에 객체를 변형한다. 비어 있는 필드에 기본값을 넣거나, Pod에 sidecar 컨테이너를 자동으로 끼워 넣는 식이다(Istio가 이렇게 한다). 요청을 바꿔서 통과시킨다.
- **Validating** — 객체를 바꾸지 않고 규칙에 맞는지만 본다. 통과하면 그대로, 아니면 거부한다.

둘을 나눠 놓은 이유는 순서 때문이다. 변형이 다 끝난 **최종 형태**를 놓고 검증해야 하니, mutating을 먼저 돌리고 그 결과를 validating이 본다. 중간에 mutating이 넣은 기본값까지 포함해서 검증하는 것이다.

쿠버네티스에는 이 admission을 수행하는 내장 플러그인이 여럿 있다(예: `NamespaceLifecycle`, `ResourceQuota`). 그리고 여기에 **직접 만든 검문 로직을 꽂는 확장 지점**이 admission webhook이다.

## admission webhook — apiserver가 외부에 물어보는 확장점

내장 플러그인만으로는 "우리 팀 규칙"을 강제할 수 없다. 그래서 apiserver는 admission 단계에서 **외부 HTTP 엔드포인트에 물어보는** 기능을 연다. 이게 admission webhook이다.

- `MutatingWebhookConfiguration` — apiserver가 "이 객체 이렇게 바꿔도 돼?"를 외부에 물어 변형 결과를 받는다.
- `ValidatingWebhookConfiguration` — apiserver가 "이 객체 받아도 돼?"를 외부에 물어 admit/deny를 받는다.

OPA/Gatekeeper, Kyverno, Pod Security 같은 정책 도구가 전부 이 위에서 돈다. 그리고 우리가 쓰는 ingress-nginx도 여기 하나 얹혀 있었다.

## 실제로 마주친 예 — ingress-nginx의 ValidatingWebhook

ingress-nginx를 설치하면 `ValidatingWebhookConfiguration`이 같이 깔린다. 하는 일은 이렇다.

- 누군가 Ingress를 CREATE/UPDATE 한다.
- apiserver가 저장 직전에 ingress-nginx controller의 webhook을 호출한다.
- controller는 그 Ingress를 반영한 nginx 설정을 **렌더해서 `nginx -t`(문법 검사)를 돌린다.**
- 문법이 깨지면(잘못된 annotation, 망가진 정규식 등) admission 단계에서 **거부**한다.

효과는 명확하다. 잘못된 Ingress 하나가 실제 nginx config로 반영돼서 controller 전체를 망가뜨리는 사고를, "저장되기 전에" 막는다. 깨진 설정은 etcd에 들어가지도 못하니 controller가 그걸 로드할 일이 없다.

실제 클러스터에서 확인한 webhook은 이런 모양이었다.

```
ValidatingWebhookConfiguration: ingress-nginx-admission
  webhook: validate.nginx.ingress.kubernetes.io
  failurePolicy: Fail
  rules: ingresses (CREATE, UPDATE)   # class 구분 없이 전부
```

여기서 두 가지를 눈여겨봐야 했다. `failurePolicy: Fail`과, rules에 class 필터가 없다는 것.

## 함정 — webhook은 controller와 달리 격리되지 않는다

controller는 IngressClass로 자기 것만 처리한다. `nginx` class controller는 `nginx` Ingress만, `nginx-external` class controller는 `nginx-external` Ingress만 본다.

그런데 **webhook은 그렇지 않다.** `ValidatingWebhookConfiguration`은 cluster-scoped 리소스라, class로도 namespace로도 안 갈라지고 **클러스터 전체의 Ingress 요청을 전부 가로챈다.** 위 rules에 class 필터가 없는 게 그 증거다.

여기에 `failurePolicy: Fail`이 겹치면 사고 시나리오가 나온다. controller를 내부용·외부용 둘로 나누면서 외부 controller의 webhook을 그냥 켜두면 —

1. 외부 controller의 webhook Pod가 죽는다.
2. 그런데 그 webhook은 (class 무관) 모든 Ingress 요청을 검문하도록 등록돼 있다.
3. 검문에 응답 못 하면 `failurePolicy: Fail`이라 요청을 거부한다.
4. 결과적으로 **내부 Ingress를 수정하려 해도** "webhook 응답 없음"으로 막힌다.
5. 배포가 줄줄이 실패한다 — self-lock이다.

그래서 우리는 외부 controller에는 `admissionWebhooks.enabled: false`로 webhook 자체를 안 만들었다. 검증 한 겹을 포기하는 대신(전역 검증은 기존 내부 controller의 webhook이 어차피 해준다) 새 단일 장애점을 안 만든 것이다. 이 self-lock을 실제로 어떻게 피했는지, whitelist·affinity 같은 다른 운영 디테일과 함께 다룬 글은 따로 있다 — **[ingress-nginx 운영에서 부딪힌 디테일들](./ingress-nginx-operations.md)**.

## 가져갈 것

admission을 이해하고 나서 남은 판단 기준은 이렇다.

- **기존 트래픽이 끊기나 물을 때** — admission은 신규 객체 등록만 게이트한다. 이미 돌고 있는 객체엔 손대지 않는다. 순수 추가(새 Ingress·새 Secret) 변경이면 admission 검증만 통과하면 되고, 기존 경로는 무관하다.
- **admission webhook을 늘릴 때** — controller는 class로 격리되지만 webhook은 안 된다. `failurePolicy: Fail` + 전역 rules 조합이면, 그 webhook Pod의 장애가 클러스터 전체 Ingress 변경을 막을 수 있다. controller를 여러 개 둘 거면 webhook을 하나로 유지하거나, 추가되는 쪽 webhook을 끄는 걸 먼저 검토한다.
- **거부와 런타임을 분리해서 보기** — admission 거부는 "저장 실패"지 "서비스 장애"가 아니다. `kubectl`이 에러를 받을 뿐, 돌고 있는 워크로드는 그대로다. 반대로 잘못된 게 admission을 통과해 버리면 그때부터가 진짜 위험이다.

## 관련 글

- [ingress-nginx 운영에서 부딪힌 디테일들 — webhook, whitelist, affinity, 리소스 사양](./ingress-nginx-operations.md) — 이 글의 self-lock을 실제로 어떻게 피했는지
- [쿠버네티스 핵심 객체 4종 — Pod, Service, Ingress, Namespace의 관계](./k8s-core-objects.md)
- [API Gateway를 제거한 자리 채우기 — path rewrite, 요청 크기 병목 4개, 그리고 HTTPS](./api-gateway-removal-rewrite-and-https.md)

## 참고 링크

- [Kubernetes — Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [Kubernetes — Admission Controllers Reference](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Kubernetes — Controlling Access to the Kubernetes API](https://kubernetes.io/docs/concepts/security/controlling-access/)
