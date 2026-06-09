# ingress-nginx 운영에서 부딪힌 디테일들 — webhook, whitelist, affinity, 리소스 사양

ingress controller를 하나 추가하는 작업은 "차트 만들고 배포하면 끝"일 줄 알았다. 그런데 실제로는 그 과정에서 처음 보는 개념들에 계속 걸렸다. annotation으로 설정을 관리하는 방식, admission webhook이 만드는 self-lock 위험, whitelist, Pod 분산 배치, 그리고 리소스 사양까지. 하나하나는 작지만, 모르고 지나가면 운영에서 사고가 나는 것들이라 정리해둔다.

내부용과 외부용 controller를 분리한 배경은 [외부 트래픽이 Pod까지 닿는 경로](./external-traffic-path.md)에 있고, 이 글은 그 후속으로 controller를 다루며 부딪힌 운영 디테일을 모았다.

## annotation으로 설정을 관리하는 이유

Ingress YAML을 보면 `metadata.annotations`에 별별 설정이 다 들어간다.

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: 10m
    nginx.ingress.kubernetes.io/whitelist-source-range: 10.0.0.0/8
```

처음엔 "왜 설정을 spec이 아니라 annotation(메모)으로 넣지?"가 이상했다. 이유를 알고 나니 쿠버네티스의 설계 의도가 보였다.

쿠버네티스의 **Ingress 표준 spec은 최소한만 정의한다.** "어느 호스트의 어느 경로를 어느 Service로" 정도뿐이다. body size 제한, IP whitelist, 경로 rewrite, rate limit 같은 세부 동작은 **표준 spec에 칸 자체가 없다.**

그런데 실제 Ingress Controller는 제품마다(nginx, traefik, haproxy) 고유 기능이 천차만별이다. 이걸 전부 표준 spec에 넣을 수가 없다. 한 제품 기능을 표준에 박으면 다른 제품엔 안 맞으니까. 그래서 **controller별 확장 설정을 annotation이라는 통로로 전달한다.** nginx ingress controller는 `nginx.ingress.kubernetes.io/`로 시작하는 annotation을 읽어서 자기 내부 `nginx.conf`에 반영한다.

> `spec`은 정해진 칸만 채우는 정식 신청서 양식이고, `annotation`은 거기 붙이는 포스트잇 메모다. 양식엔 칸이 없지만 담당자(controller)가 메모를 읽고 처리해준다.

이렇게 한 이유는 쿠버네티스가 **벤더 중립**을 지키려고 그런 거다. "Ingress"라는 표준 개념은 공통으로 두되, 각 controller의 고유 기능은 표준을 건드리지 않고 annotation으로 확장하게 했다. 다만 이 방식이 깔끔하지 않다는 불만이 쌓여서, 요즘은 **Gateway API**라는 차세대 표준이 이런 설정을 정식 필드로 흡수하려는 흐름도 있다. 아직은 ingress-nginx와 annotation 조합이 현업 주류지만.

## admission webhook — 격리가 안 되는 검문소

이게 이번 작업에서 가장 직관에 어긋났던 부분이다.

**admission webhook**은 쿠버네티스에 리소스를 만들거나 바꾸려고 요청하면, API 서버가 **저장하기 직전에 거치는 검문소**다. ingress-nginx를 설치하면 이 검문소(`ValidatingWebhookConfiguration`)가 같이 깔린다. 역할은 검증이다. 잘못된 Ingress(nginx 설정으로 바꿨을 때 문법 오류가 나는 것)를 미리 거부해서, 깨진 설정 하나가 nginx 전체를 망가뜨리는 걸 막는다.

문제는 controller를 둘로 나눌 때 드러난다. **controller는 IngressClass로 자기 것만 처리하지만, webhook은 그렇지 않다.**

- controller는 `--ingress-class`로 자기 class(`nginx` 또는 `nginx-external`)만 본다. 깔끔하게 격리된다.
- 그런데 webhook은 cluster-scoped 리소스라서, **class로도 namespace로도 격리되지 않고 클러스터 전체의 Ingress 요청을 가로챈다.**

(이 "cluster-scoped"라는 성질은 [쿠버네티스 핵심 객체 4종](./k8s-core-objects.md#namespaced-vs-cluster-scoped--모든-리소스가-namespace에-속하진-않는다)에서 다룬, namespace에 속하지 않는 전역 리소스 얘기와 같은 맥락이다.)

그래서 외부용 controller를 추가하면 webhook도 하나 더 생기는데, 이 새 webhook은 "외부 class만"이 아니라 **모든 Ingress(내부 것 포함)**를 검문한다. 여기서 사고 시나리오가 나온다.

1. 외부 controller의 webhook Pod가 죽는다.
2. 그런데 이 webhook은 모든 Ingress 요청을 검문하도록 등록돼 있다.
3. 검문에 응답할 수 없으면, 정책에 따라 요청을 **거부**한다(`failurePolicy: Fail`).
4. 결과적으로 **내부 Ingress를 수정하려 해도** "webhook 응답 없음"으로 거부된다.
5. 배포 도구가 Ingress를 반영하려다 줄줄이 실패한다 — self-lock의 변종이다.

그래서 외부 controller에는 `admissionWebhooks.enabled: false`로 **webhook 자체를 안 만들었다.** 검증을 한 겹 포기하는 셈이지만, 사전 검증은 기존 controller의 webhook이 어차피 클러스터 전체로 해주고 있으니(전역이라), 새 장애점만 안 생기고 내부 경로가 안전해진다. 검증 한 겹과 self-lock 위험을 맞바꾼 거고, 후자가 훨씬 무거웠다.

> controller는 자기 구역만 배달하는 우편배달부고, webhook은 우체국 전체의 검열대다. 검열대를 하나 더 만들면, 그게 고장 났을 때 다른 구역 편지까지 전부 막힌다.

## whitelist-source-range — 공인인데 평문일 때의 보호막

외부용 Ingress에는 출발지 IP를 제한하는 annotation을 걸었다.

```yaml
nginx.ingress.kubernetes.io/whitelist-source-range: 10.0.0.0/8,203.0.113.5
```

이걸 건 이유는 단계 때문이다. 공인 LB로 열면 이론상 인터넷의 누구나 그 IP로 접근할 수 있다. 그런데 이 시점엔 아직 TLS를 안 붙여서 통신이 평문 HTTP다. 평문인 채로 인터넷 전체에 열면 요청·응답 내용이 그대로 노출되니 위험하다. (TLS가 왜 필요한지는 [HTTPS는 어떻게 안전한가](../../http/https-tls-basics.md)에 정리해뒀다.)

그래서 공인 진입은 켜되, 실제로 닿을 수 있는 범위를 사내 IP로 제한했다. nginx가 요청의 출발지 IP를 보고, 목록에 없으면 403으로 거부한다. 지금 검증할 건 "공인 IP로 들어온 요청이 경로를 타고 앱까지 닿는가"뿐이라, 사내에서 호출해 확인하면 충분하다. 정식으로 외부에 공개할 때(TLS와 도메인이 준비되면) 이 제한을 조정하면 된다.

## podAntiAffinity — replica를 다른 노드에 흩뿌리기

controller values에 이런 블록이 있었다.

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/instance
                operator: In
                values: [ingress-nginx-external]
          topologyKey: kubernetes.io/hostname
        weight: 1
```

길어 보이지만 뜻은 한 줄이다. **이 controller의 Pod들끼리는 가능하면 서로 다른 노드에 배치해라.**

- `podAntiAffinity` — anti(반대), 즉 "이런 Pod들끼리는 떨어뜨려 놔라".
- `preferredDuringScheduling...` — `preferred`는 **선호**(강제 아님). 가능하면 지키되 안 되면 그냥 배치한다. (반대인 `required`로 하면 못 지킬 때 Pod가 아예 안 뜬다.)
- `topologyKey: kubernetes.io/hostname` — **노드 단위**로 떨어뜨린다.

controller를 2개 띄우는데 둘이 **같은 노드**에 몰려 있으면, 그 노드 하나가 죽을 때 둘 다 같이 죽어서 진입점 전체가 멈춘다. 다른 노드에 흩어두면 노드 하나가 죽어도 나머지가 살아남는다. `preferred`로 둔 건, 노드가 부족할 때 같은 노드에라도 뜨게 허용하려는 거다. `required`였으면 노드가 모자랄 때 Pod가 안 떠버린다.

> 당직 두 명을 가능하면 다른 건물에 배치하는 것과 같다. 한 건물에 불나도 한 명은 살아있게. 단 건물이 하나뿐이면 같은 건물이라도 배치한다(필수는 아니니까).

## 리소스 사양 — 추측 말고 측정

controller에 잡아둔 리소스가 충분한지 궁금했는데, 답은 추측이 아니라 측정에서 나왔다. `kubectl top`으로 실제 사용량을 보면 된다.

직접 보고 알게 된 것:

- **ingress-nginx controller는 의외로 메모리를 적게 쓴다.** 여러 Ingress를 처리하는데도 30~50Mi 수준이었다. nginx가 가벼운 reverse proxy라 그렇다.
- **`memory request == limit`이면 Guaranteed QoS다.** "딱 그만큼 보장, 넘으면 즉시 OOMKill"이라는 뜻이다. 안정적이지만 **여유 폭이 좁다.** 갑작스런 스파이크에 죽지 않으려면 limit을 request보다 넉넉히 두는 게 안전하다.
- **환경마다 사양이 다르다.** 테스트 환경은 작게 잡고 replica를 고정해도 되지만, 운영 환경은 더 크게 잡고 autoscaling을 걸어 부하에 따라 Pod 수가 늘게 한다. 그래서 새 controller를 운영으로 확장할 땐 운영 쪽 사양·autoscaling 정책에 맞춰줘야 한다.

특히 주의할 케이스가 있다. **큰 파일을 업로드받는 서비스**는 nginx가 요청 본문을 버퍼링하므로, 동시 업로드가 몰리면 메모리 압박이 생길 수 있다. (큰 본문은 디스크 임시파일로도 버퍼링돼서 폭증하진 않지만, 모니터링 대상이다.) 그래서 운영 적용 전에는 `kubectl top`으로 실제 부하를 한 번 측정하고 사양을 정하는 게 맞다. "충분하겠지"라는 추측보다 30초짜리 측정이 훨씬 믿을 만하다.

## 정리

ingress controller 하나 추가하는 일이, 알고 보니 이런 디테일들의 묶음이었다.

- 설정은 표준 spec에 칸이 없어서 annotation으로 들어간다(벤더 중립 설계).
- webhook은 controller와 달리 격리가 안 되니, controller를 늘릴 때 self-lock을 조심해야 한다.
- 공인인데 평문인 단계에선 whitelist로 사내만 열어 테스트한다.
- replica는 podAntiAffinity로 다른 노드에 흩뿌려 가용성을 지킨다.
- 리소스는 추측하지 말고 `kubectl top`으로 측정해서 정한다.

각각은 사소해 보여도, 모르고 지나가면 "왜 내부 배포가 다 막히지?" 같은 사고로 돌아오는 것들이었다. 한 번 부딪혀보고 나니 다음엔 미리 챙길 수 있겠다 싶어 기록으로 남긴다.

## 관련 글

- [외부 트래픽이 Pod까지 닿는 경로](./external-traffic-path.md) — 내부/외부 controller를 나눈 배경
- [쿠버네티스 핵심 객체 4종](./k8s-core-objects.md) — cluster-scoped 리소스가 뭔지
- [HTTPS는 어떻게 안전한가](../../http/https-tls-basics.md) — whitelist가 임시 보호막인 이유(TLS 전 단계)

## 참고 링크

- [ingress-nginx — Annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
- [Kubernetes — Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [Kubernetes — Assigning Pods to Nodes (Affinity)](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
