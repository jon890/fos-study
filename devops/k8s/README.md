# Kubernetes

쿠버네티스 학습·운영 기록. 두 개의 시리즈로 나뉜다.

- **기본기 시리즈** — 개념을 순서대로 쌓는다. 처음 보는 사람은 1편부터.
- **실전 연재** — API Gateway 를 걷어내고 공인 LoadBalancer 로 직접 노출한 작업 기록. 기본기 3편(핵심 객체)까지 읽고 오면 따라가기 쉽다.

## 시리즈 1 — 백엔드 개발자를 위한 쿠버네티스 기본기

| # | 글 | 다루는 것 |
|---|---|---|
| 1 | [컨테이너와 쿠버네티스가 필요한 이유](./why-kubernetes.md) | jar 배포가 무너지는 지점, 클러스터 구성 |
| 2 | [선언형 API 와 reconcile loop](./declarative-api-reconcile-loop.md) | spec 과 status, 컨트롤러 루프, 문제 진단 순서 |
| 3 | [핵심 객체 4종](./k8s-core-objects.md) | Pod · Service · Ingress · Namespace 의 관계 |
| 4 | [Deployment · ReplicaSet · Pod](./deployment-pod.md) | 롤링 업데이트, probe 3종, graceful shutdown |
| 5 | [Admission](./admission-control.md) | etcd 저장 직전의 검문, webhook self-lock |
| 6 | [Helm](./helm.md) | 차트 구조, 값 우선순위, 렌더 검증 |
| 7 | [Argo CD](./argo-cd.md) | GitOps, Application, sync wave, 무한 sync |
| 8 | [Helm 과 ArgoCD 로 GitOps 하기](./helm-argocd-gitops.md) | 새 컴포넌트 추가 전체 흐름 |

## 시리즈 2 — API Gateway 를 걷어내고 쿠버네티스로 직접 노출하기

| # | 글 | 다루는 것 |
|---|---|---|
| 1 | [외부 트래픽은 어떻게 Pod까지 닿는가](./external-traffic-path.md) | LoadBalancer, Ingress Controller, 내부·외부 분리 |
| 2 | [선언한 LoadBalancer가 안 만들어질 때](./loadbalancer-pending-diagnosis.md) | cloud-controller-manager 장애 격리 |
| 3 | [관리형 클러스터는 누구의 권한으로 클라우드를 만지는가](./managed-cluster-identity-trust.md) | keystone trust, service user 전환 |
| 4 | [API Gateway를 걷어낸 자리 채우기](./api-gateway-removal-rewrite-and-https.md) | path rewrite, 요청 크기 병목, HTTPS 종료 위치 |
| 5 | [ingress-nginx 운영 디테일](./ingress-nginx-operations.md) | admission webhook, whitelist, 배치, 리소스 사양 |
| 6 | [IP whitelist가 조용히 뚫려 있었다](./client-ip-preservation.md) | L4 패스스루와 SNAT 로 클라이언트 IP 가 사라지는 구간 |
| 7 | [파드가 서비스 이름을 못 푸는 이유](./pod-dns-policy-and-ndots.md) | dnsPolicy 4종, ndots 와 search 도메인 전개 |

## 함께 보면 좋은 글

- [HTTPS는 어떻게 안전한가](../../http/https-tls-basics.md) — TLS termination 위치
- [L4와 VIP](../../network/L4-and-VIP.md) — 실전 연재 6편의 선행 지식
- [Linux 프로세스 격리](../docker/linux-process-isolation.md) — 컨테이너가 격리되는 원리
- [GPU 노드 /run tmpfs 포화](../../mlops/gpu-node-run-tmpfs-full.md) — GPU 노드 운영 사례

## 도서

- [쿠버네티스 인 액션](../k8s-in-action/README.md) — 책 정리
