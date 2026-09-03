---
tags: [입문, study]
series: "백엔드 개발자를 위한 쿠버네티스 기본기"
seriesOrder: 6
---

# Helm — 쿠버네티스 YAML 의 패키지 매니저이자 템플릿 엔진

> 여기까지 오면서 다룬 객체들(Deployment, Service, Ingress)은 전부 YAML 로 쓴다. 이 글부터는 **그 YAML 을 어떻게 관리할 것인가**로 넘어간다.

객체를 하나씩 배울 때는 YAML 을 손으로 쓰는 게 문제가 아니었다. 문제는 같은 서비스를 alpha · beta · real 세 환경에 올려야 할 때였다. 구조는 똑같고 replica 수와 리소스 값만 다른데, 파일을 세 벌 복사해서 관리하니 구조를 한 번 고칠 때마다 세 군데를 고쳐야 했다. 한 군데를 빠뜨려서 환경마다 설정이 어긋나는 것도 시간 문제였다.

**Helm 은 이 문제를 템플릿과 값의 분리로 푼다.** 백엔드에 비유하면 Gradle 에 가깝다. Gradle 이 `.jar` 의존성을 관리한다면 Helm 은 **YAML 뭉치**(Chart) 를 관리한다. 그리고 그 안에서 하드코딩을 없애는 템플릿 엔진 역할까지 겸한다.

GitOps 로 실제 배포하는 흐름은 [Helm 과 ArgoCD 로 GitOps 하기](./helm-argocd-gitops.md)에 따로 정리했고, 이 글은 Helm 자체의 구조·문법·명령어에 집중한다.

## 템플릿과 값을 나눈다

Helm 의 발상은 단순하다. 빈칸이 뚫린 틀 하나를 두고, 환경마다 값만 갈아 끼운다. JSP · Thymeleaf 를 떠올리면 그대로다.

```yaml
# templates/deployment.yaml — 틀 (Go Template 문법)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.appName }}
spec:
  replicas: {{ .Values.replicaCount }}
```

```yaml
# values-real.yaml — 환경마다 달라지는 값만
appName: api-real
replicaCount: 10
```

이 둘을 합쳐 렌더한 최종 결과물을 클러스터에 적용하고, 그 설치 단위를 **Release** 라고 부른다. 같은 차트로 이름만 달리해 여러 Release 를 만들 수 있다.

## 차트 구조

Chart 는 정해진 디렉터리 구조를 따른다. 각 파일에 역할이 있다.

```
my-chart/
├── Chart.yaml          # 차트 메타데이터 + 의존성 선언
├── values.yaml         # 기본 설정값
├── charts/             # 의존 차트(subchart)가 들어가는 곳
└── templates/          # 실제 YAML 템플릿
    ├── deployment.yaml
    ├── service.yaml
    ├── _helpers.tpl    # 재사용 템플릿 조각 (밑줄 prefix)
    └── NOTES.txt       # 설치 후 출력되는 안내문
```

- **`Chart.yaml`** — 차트 이름·버전·의존성을 적는 메타데이터.
- **`values.yaml`** — 템플릿이 참조하는 **기본값**. `{{ .Values.foo }}` 로 꺼내 쓴다.
- **`templates/`** — 가장 중요한 디렉터리. Deployment·Service 같은 실제 정의가 여기 들어간다.
- **`templates/_helpers.tpl`** — 밑줄로 시작하는 파일은 **매니페스트로 렌더되지 않고**, 다른 템플릿이 가져다 쓰는 재사용 조각을 담는다. 라벨 블록처럼 여러 곳에서 반복되는 것을 한 군데로 뺄 때 쓴다.
- **`charts/`** — 의존 차트가 압축 파일로 들어가는 곳.

## 값 우선순위 — 어느 값이 이기나

같은 키를 여러 곳에서 지정하면 **더 구체적인 쪽이 이긴다.** 낮은 것부터 나열하면 이렇다.

1. subchart 의 `values.yaml`
2. 부모 차트의 `values.yaml`
3. `-f` 로 넘긴 값 파일 — 여러 개면 **뒤에 온 파일이 앞을 덮어쓴다**
4. `--set` 으로 커맨드라인에서 직접 지정 (가장 강함)

그래서 공통값은 `values.yaml` 에, 환경별 차이는 `-f {stage}-values.yaml` 에, 임시 오버라이드는 `--set` 에 두는 계층이 자연스럽게 만들어진다.

한 가지 주의할 점은 **리스트는 병합되지 않고 통째로 교체된다**는 것이다. 맵(map)은 키 단위로 병합되지만 배열은 그렇지 않다. 환경별 파일에서 배열 항목 하나만 추가하려다가 기본값 전체가 날아가는 일이 실제로 자주 생긴다.

## 핵심 명령어

| 명령 | 역할 |
|---|---|
| `helm install <name> <chart>` | 차트를 설치 (새 Release 생성) |
| `helm upgrade --install <name> <chart>` | 있으면 업그레이드, 없으면 설치 (멱등) |
| `helm template <name> <chart> -f values.yaml` | **클러스터에 적용하지 않고** 렌더 결과만 출력 |
| `helm lint <chart>` | 차트 문법·구조 점검 |
| `helm diff upgrade <name> <chart>` | 지금 떠 있는 것과의 차이 미리보기 (플러그인) |
| `helm rollback <name> <revision>` | 이전 Release 로 되돌리기 |
| `helm uninstall <name>` | Release 제거 |
| `helm dependency update` | `Chart.yaml` 의 의존성을 `charts/` 로 내려받아 동기화 |

이 중 실제로 사고를 막아 주는 건 `helm template` 이다. **클러스터에 보내기 전에 최종 YAML 을 눈으로 확인하는 유일한 수단**이라, 값 파일을 여러 겹 얹는 구조에서는 이 단계를 건너뛰면 안 된다. 내 경우 값이 의도한 대로 안 들어가는 문제를 이 명령으로 잡은 적이 여러 번 있다.

`helm upgrade --install` 은 "있으면 갱신, 없으면 설치"를 한 명령으로 처리해서 CI 스크립트에서 쓰기 좋다.

## 의존성과 subchart

큰 애플리케이션은 여러 컴포넌트로 쪼개진다. 이때 다른 차트를 **의존성**으로 가져와 조합할 수 있다.

```yaml
# Chart.yaml
dependencies:
  - name: redis
    version: "17.x.x"
    repository: https://charts.bitnami.com/bitnami
```

- `helm dependency update` 가 해당 차트를 `charts/` 로 내려받고 lock 파일로 버전을 고정한다.
- 부모 차트의 values 로 subchart 설정을 덮어쓸 수 있다. 이때 **subchart 이름을 키로 한 블록 아래에 써야** 전달된다. `redis:` 아래에 쓴 값만 redis subchart 로 들어간다.
- 덕분에 검증된 공식 차트(Redis, MySQL, ingress-nginx 등)를 직접 작성하지 않고 끌어와 쓸 수 있다.

패키지 매니저로서의 성격이 여기서 드러난다. Maven Repository 에서 라이브러리를 받듯, 남이 검증해 둔 쿠버네티스 설정을 명령 한 줄로 설치한다.

## 실제로 걸리는 지점들

Helm 을 쓰면서 부딪힌 것들을 남겨둔다.

- **템플릿 오류는 렌더 시점에야 드러난다.** 오타 난 `.Values.replicaCont` 는 에러가 아니라 **빈 문자열**로 렌더된다. `replicas:` 뒤가 비어버려 이상한 YAML 이 만들어지는 식이다. 필수값에는 `{{ required "replicaCount 필요" .Values.replicaCount }}` 를 걸어 렌더 단계에서 실패하게 만드는 편이 낫다.
- **들여쓰기가 템플릿 함수의 책임이 된다.** 여러 줄 값을 끼워 넣을 때 `{{ toYaml .Values.resources | nindent 12 }}` 처럼 들여쓰기를 명시해야 한다. YAML 은 들여쓰기가 문법이라 이 한 칸이 어긋나면 전혀 다른 구조가 된다.
- **`--set` 을 습관적으로 쓰면 기록이 사라진다.** 커맨드라인 오버라이드는 어디에도 남지 않아서, 나중에 "이 값이 왜 이렇지"를 추적할 수 없다. 값은 파일에 두고 git 에 남기는 쪽이 안전하다.
- **Helm 이 관리하지 않는 리소스는 지워지지 않는다.** `kubectl` 로 직접 만든 것이 섞이면 차트를 지워도 남는다. 리소스의 주인을 한쪽으로 정해두는 게 좋다.

## 정리

- Helm 은 **템플릿과 값을 나눠** 환경별 YAML 복제를 없앤다.
- 값은 낮은 우선순위부터 겹겹이 덮이며, **배열은 병합되지 않고 교체**된다.
- 배포 전 `helm template` 로 최종 YAML 을 확인하는 습관이 사고를 가장 많이 막는다.
- 오타 난 값 참조는 에러가 아니라 빈 문자열이다. 필수값은 `required` 로 막는다.

다음 글에서는 이렇게 만든 매니페스트를 **언제 어떻게 클러스터에 반영할지** 맡는 [Argo CD](./argo-cd.md) 를 본다.

## 참고 링크

- [Charts — Helm 공식 문서](https://helm.sh/docs/topics/charts/)
- [Values Files — Helm 공식 문서](https://helm.sh/docs/chart_template_guide/values_files/)
- [Named Templates — Helm 공식 문서](https://helm.sh/docs/chart_template_guide/named_templates/)
- [helm dependency — Helm 공식 문서](https://helm.sh/docs/helm/helm_dependency/)
