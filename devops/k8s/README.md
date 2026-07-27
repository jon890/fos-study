# Kubernetes

쿠버네티스 기본기와 배포 도구 학습 기록. 외부 노출 작업(API Gateway 제거)을 계기로 정리한 시리즈.

## 시작

- [Kubernetes 공부 시작](./start-k8s.md) — 컨테이너 개념부터 핵심 구성까지

## 핵심 개념

- [쿠버네티스 핵심 객체 4종](./k8s-core-objects.md) — Pod·Service·Ingress·Namespace의 관계, namespaced vs cluster-scoped
- [Deployment와 Pod](./deployment-pod.md) — 파드 라이프사이클, ReplicaSet, Rolling Update

## 외부 노출 / 네트워크

- [외부 트래픽이 Pod까지 닿는 경로](./external-traffic-path.md) — LoadBalancer, Ingress Controller, 내부/외부 분리
- [ingress-nginx 운영 디테일](./ingress-nginx-operations.md) — admission webhook, whitelist, podAntiAffinity, 리소스 사양
- [IP whitelist가 조용히 뚫려 있었다](./client-ip-preservation.md) — 클라이언트 IP가 사라지는 구간, L4 패스스루와 externalTrafficPolicy SNAT (위 글의 후속)
- (참고) [HTTPS는 어떻게 안전한가](../../http/https-tls-basics.md) — TLS termination 위치

## 배포 자동화

- [Helm](./helm.md) — 차트 구조, 값 우선순위, 명령어, dependencies
- [Argo CD](./argo-cd.md) — GitOps, Custom Controller, Sync Waves
- [Helm과 ArgoCD로 GitOps 하기](./helm-argocd-gitops.md) — chart 와 Application, 새 컴포넌트 추가 흐름

## 운영 트러블슈팅

- [선언한 LoadBalancer가 안 만들어질 때](./loadbalancer-pending-diagnosis.md) — cloud-controller-manager, subnet-id, trust 인증 장애 격리
- [관리형 클러스터는 누구의 권한으로 클라우드를 만지는가](./managed-cluster-identity-trust.md) — keystone trust, service user 전환, 사람에 묶인 인프라 의존성 (위 글의 후속)
- [API Gateway를 걷어낸 자리 채우기](./api-gateway-removal-rewrite-and-https.md) — path rewrite, 요청 크기 병목 4개, LB 리스너 프로토콜과 HTTPS (위 글의 후속)
- [GPU 노드 /run tmpfs 포화](../../mlops/gpu-node-run-tmpfs-full.md) — GPU 운영 글은 mlops 카테고리로 이동

## 도서

- [쿠버네티스 인 액션](../k8s-in-action/README.md) — 책 정리
