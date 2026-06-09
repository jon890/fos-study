# Helm — 쿠버네티스 YAML의 패키지 매니저이자 템플릿 엔진

- k8s의 **Gradle**.
- Gradle이 `.jar` 파일을 관리한다면, Helm은 **k8s YAML 파일 뭉치**(Chart)를 관리한다.
- 개발자 입장에서 Helm이 해결해 주는 핵심은 **하드코딩 제거**(템플릿)와 **재사용성**(패키지)이다.

GitOps(ArgoCD)와 함께 쓰는 실전 흐름은 [Helm과 ArgoCD로 GitOps 하기](./helm-argocd-gitops.md)에 따로 정리했고, 이 글은 Helm 자체의 구조·문법·명령어에 집중한다.

## 왜 Helm이 필요한가

Helm 없이 k8s를 운영하면 "복붙의 지옥"에 빠진다.

- 상황: `api` 서비스를 Alpha, Beta, Real 환경에 배포해야 한다.
- 문제: 세 환경은 구조(Deployment, Service)는 똑같은데 **설정값**(변수)만 다르다.
  - Alpha: `replicas=1, cpu=0.5`
  - Real: `replicas=10, cpu=4.0`
- Helm이 없으면: `deployment-alpha.yaml`, `deployment-beta.yaml`, `deployment-real.yaml`을 복사해서 각각 관리해야 한다. 구조가 바뀌면 세 파일을 다 고쳐야 한다.

## 해결책: 템플릿과 값의 분리

Helm은 이 문제를 **템플릿**(Template)과 **설정값**(Values)의 분리로 푼다. 백엔드의 JSP·Thymeleaf를 떠올리면 된다 — 틀은 하나, 값만 갈아끼운다.

```yaml
# templates/deployment.yaml (Go Template 문법)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.appName }}
spec:
  replicas: {{ .Values.replicaCount }}
```

```yaml
# values-real.yaml — 환경별로 달라지는 값만 모음
appName: api-real
replicaCount: 10
```

`helm` 명령으로 템플릿에 값을 채워 최종 YAML(**Release**)을 만들어 배포한다.

## 차트 구조

Chart는 정해진 디렉터리 구조를 따른다. 각 파일에 역할이 있다.

```
my-chart/
├── Chart.yaml          # 차트 메타데이터 + 의존성 선언
├── values.yaml         # 기본 설정값
├── charts/             # 의존 차트(subchart)들이 들어가는 곳
└── templates/          # 실제 YAML 템플릿
    ├── deployment.yaml
    ├── service.yaml
    ├── _helpers.tpl    # 재사용 템플릿 조각(밑줄 prefix)
    └── NOTES.txt       # 설치 후 출력되는 안내문
```

- **`Chart.yaml`** — 차트 이름·버전·의존성(dependencies)을 적는 메타데이터.
- **`values.yaml`** — 템플릿이 참조하는 **기본값**. `{{ .Values.foo }}`로 꺼내 쓴다.
- **`templates/`** — 가장 중요한 디렉터리. Service·Deployment 등의 YAML 정의가 여기 들어간다.
- **`templates/_helpers.tpl`** — 밑줄(`_`)로 시작하는 파일은 **k8s 매니페스트로 렌더되지 않고**, 다른 템플릿에서 가져다 쓰는 **재사용 조각**(named template)을 모아둔다. 라벨 블록처럼 여러 곳에서 반복되는 조각을 한 군데로 뺄 때 쓴다.
- **`charts/`** — 의존 차트(subchart)가 압축 파일로 들어가는 곳.

## 값 우선순위 — 어느 값이 이기나

같은 키를 여러 곳에서 지정하면 **더 구체적인 쪽이 이긴다.** 우선순위는 낮은 것부터:

1. subchart의 `values.yaml`
2. 부모 차트의 `values.yaml`
3. `-f`로 넘긴 값 파일 (여러 개면 **뒤에 온 파일**이 앞을 덮어씀)
4. `--set`으로 커맨드라인에서 직접 지정 (가장 강함)

그래서 공통값은 `values.yaml`에, 환경별 차이는 `-f {stage}-values.yaml`에, 임시 오버라이드는 `--set`에 두는 식으로 계층을 만든다.

## 핵심 명령어

| 명령 | 역할 |
|---|---|
| `helm install <name> <chart>` | 차트를 클러스터에 설치(새 Release 생성) |
| `helm upgrade --install <name> <chart>` | 있으면 업그레이드, 없으면 설치(멱등) |
| `helm template <name> <chart> -f values.yaml` | **클러스터에 적용하지 않고** 렌더 결과만 출력(배포 전 검증) |
| `helm lint <chart>` | 차트 문법·구조 점검 |
| `helm rollback <name> <revision>` | 이전 Release 버전으로 되돌리기 |
| `helm uninstall <name>` | Release 제거 |
| `helm dependency update` | `Chart.yaml`의 의존성을 `charts/`로 내려받아 동기화 |

특히 `helm template`은 배포 전에 "실제로 어떤 YAML이 나오는지" 눈으로 확인하는 용도라, 사고를 미리 막는 핵심 도구다.

`helm upgrade --install`은 "있으면 갱신, 없으면 설치"를 한 명령으로 처리해서 CI/CD 스크립트에서 자주 쓴다.

## 의존성과 Subchart

큰 애플리케이션은 여러 컴포넌트(앱 + Redis + MySQL 등)로 쪼개진다. 이때 다른 차트를 **의존성(subchart)**으로 가져와 조합할 수 있다.

```yaml
# Chart.yaml
dependencies:
  - name: redis
    version: "17.x.x"
    repository: https://charts.bitnami.com/bitnami
```

- `Chart.yaml`의 `dependencies`에 선언하면, `helm dependency update`가 해당 차트를 `charts/`로 내려받고 **lock 파일**을 만들어 정확한 버전을 고정한다.
- subchart는 `charts/` 디렉터리에 들어가며, 부모 차트의 values로 subchart 설정을 덮어쓸 수 있다.
- 이 방식 덕에 공식으로 잘 만들어진 차트(Redis, MySQL, ingress-nginx 등)를 직접 작성하지 않고 의존성으로 끌어와 쓴다.

## 패키지 매니저로서의 Helm

Maven Repository에서 라이브러리를 받듯, 남들이 검증해 둔 k8s 설정(Redis, MySQL, Jenkins, Prometheus 등)을 명령어 한 줄로 설치할 수 있다.

- Linux: `apt-get install nginx`
- Helm: `helm install my-nginx bitnami/nginx`

Nginx용 Service·Deployment·ConfigMap을 처음부터 짤 필요 없이, 검증된 패키지를 받아 값만 조정해 설치하면 끝이다.

## 관련 글

- [Helm과 ArgoCD로 GitOps 하기](./helm-argocd-gitops.md) — Helm 차트를 GitOps로 배포하는 실전 흐름
- [Argo CD](./argo-cd.md) — Helm으로 만든 매니페스트를 git 기준으로 동기화

## 참고 링크

- [Charts — Helm 공식 문서](https://helm.sh/docs/topics/charts/)
- [Named Templates(_helpers.tpl) — Helm 공식 문서](https://helm.sh/docs/chart_template_guide/named_templates/)
- [helm dependency — Helm 공식 문서](https://helm.sh/docs/helm/helm_dependency/)
