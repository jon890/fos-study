# Argo CD

- "k8s를 제어하는 컨트롤러"

## 1. ArgoCD의 정체 : Kubernetes Controller

ArgoCD는 웹 UI가 있는 툴처럼 보이지만, 기술적으로는 **K8s Custom Controller**이다.

- **CRD(Custom Resource Definition)**: K8s에는 기본적으로 `Pod`, `Deployment`같은 리소스가 있다.
  - ArgoCD를 설치하면 **Application**과 **AppProject**라는 새로운 리소스 타입이 생긴다.
- **동작 원리**: 우리가 YAML 파일로 `Application` 객체를 생성하면, ArgoCD 컨트롤러가 이를 감지한다.
  - "이 Git 주소에 있는 내용을 저 클러스터에 배포하라는 거구나"라고 해석해서 일을 시작한다.

## 2. 핵심 아키텍처

ArgoCD는 마이크로서비스 구조로 되어 있다. 내부 동작을 알아보자.

- **1. API Server (gRPC/REST):**
  - 웹 UI와 CLI 요청을 받는 게이트웨이
  - 인증(SSO)와 인가(RBAC)를 담당한다.
- **2. Repository Server:**
  - 역할 : Git 저장소의 내용을 로컬에 캐싱하고, YAML을 파싱하는 **Git 전담 서비스**이다.
  - Helm 차트나 Kustomize 같은 템플릿을 렌더링해서 순수 YAML로 변환하는 작업을 수행한다.
- **3. Application Controller (핵심):**
  - 역할 : 무한 루프를 도는 스케줄러
  - `Live State`(K8s의 현재 상태)와 `Target State`(Repo Server가 준 Git 상태)를 비교한다.
  - 다르면 `Sync`(동기화) 로직을 실행한다.

## 3. 핵심 리소스 : Application

ArgoCD에서 가장 많이 다루게 될 `Application` 리소스의 실제 모습이다. <br />
이 YAML 하나가 서비스 하나의 배포 파이프라인을 정의한다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api # ArgoCD UI에 뜨는 이름
  namespace: argocd # ArgoCD가 설치된 네임스페이스
spec:
  project: default # 프로젝트 그룹 (권한 관리용)

  # 1. 어디서 가져올까?
  source:
    repoURL: https://github.com/jon890/k8s-manifests.git
    targetRevision: HEAD # 브랜치(main) 또는 태그 (v1.0.0)
    path: api # Git 내부 경로

  # 2. 어디에 배포할까?
  destination:
    server: https:.//kubernetes.default.svc # 타겟 클러스터 API 주소
    namespace: api # 배포될 k8s 네임스페이스

  # 3. 어떻게 동기화할까? (Sync Policy)
  syncPolicy:
    automated: # 자동 동기화 옵션
      prune: # Git에서 파일 지우면 k8s 리ㅗㅅ스도 삭제
      selfHeal: true # 누가 kubectl를 맘대로 고치면 원상 복구
    syncOptions:
      - CreateNamespace=true # 네임스페이스가 없으면 생성
```

## 4. 고급 기능: Sync Waves & Hooks (순서 제어)

K8s는 기본적으로 비동기 병렬로 뜬다. <br />
하지만 백엔드 앱은 **DB 마이그레이션이 끝나야 서버가 떠야 한다**와 같은 순서가 필요한 경우도 있다. <br />
이때 사용하는 것이 Wave와 Hook이다.

- Sync Waves (우선순위):
  - 리소스에 `argocd.argoproj.io/sync-wave: "1"`과 같은 어노테이션을 붙인다.
  - 낮은 숫자부터 먼저 배포된다
  - 예: ConfigMap(-1) -> Service(0) -> Deployment(1)
- Resource Hooks (생명주기 훅):
  - `PreSync`: 배포 시작 전에 실행
    - 예: DB 스키마 마이그레이션, 백업
  - `PostSync`: 배포 성공 후 실행
    - 예: Slack 알림, 헬스 체크
  - `SyncFail`: 실패 시 실행
    - 예: 롤백 트리거

## 5. ArgoCD 사용 시 주의사항

#### 1. OutofSync 상태:

- Git과 K8s가 다르다는 뜻이다.
- UI에서 `Diff` 탭을 눌러서 **무엇이 다른지**확인하는 습관이 필요하다.
- 때로는 K8s가 자동으로 생성하는 필드 떄문에 가짜 차이가 발생할 수 있는데, 이는 `ignoreDifferences` 설정으로 무시할 수 있다.

#### 2. 무한 Sync 루프:

- 가끔 ArgoCD가 고치고 -> K8s가 다시 원래대로 돌리고 -> ArgoCD가 다시 고치고를 반복할 때가 있다.
- 보통 서로 다른 컨트롤러가 충돌할 떄 발생한다.
  - 예: HPA와 Deployment의 replicas 설정

#### 3. Secret 관리:

- Git에는 비밀번호를 평문으로 올리면 안된다.
- 보통 `SealedSecrets`나 `Vault`, `SOPS` 같은 도구를 써서 암호화된 파일을 Git에 올리고, ArgoCD가 배포할 떄 복호화하거나 참조하도록 구성한다.

> 정리 : ArgoCD는 단순 툴이 아니라, `Application`이라는 CRD를 통해 Git의 상태를 K8s에 반영(Reconcile)하는 컨트롤러이다.
