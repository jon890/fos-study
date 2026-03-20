# K8s 위 Spring Boot 앱 메트릭 수집하기 (Prometheus Agent + remote_write)

K8s 클러스터에서 Spring Boot 애플리케이션을 운영하다 보면 JVM 힙 사용량, HTTP 요청 수, 응답 시간 같은 지표를 모니터링하고 싶어진다. 팀에 중앙 Grafana가 이미 있다면 클러스터 내에서 Prometheus로 긁어다가 remote_write로 쏴주기만 하면 된다.

이번에 실제로 적용하면서 삽질한 내용들을 정리해봤다.

## 전체 구조

```
Spring Boot Pod (/actuator/prometheus)
        ↓  scrape (15s)
  Prometheus (K8s 내, Agent 모드)
        ↓  remote_write
  중앙 Grafana (사내 공통 모니터링 플랫폼)
```

클러스터 안에 Prometheus를 띄우되, 로컬에 데이터를 쌓지 않고 중앙 플랫폼으로만 전달하는 구조다. 이걸 **Agent 모드**라고 한다.

## Helm Chart 구성

`prometheus-community/prometheus` 차트를 Wrapper 형태로 감싸서 사용했다.

```yaml
# Chart.yaml
apiVersion: v2
name: prometheus
type: application
version: 0.1.0
dependencies:
  - name: prometheus
    repository: https://prometheus-community.github.io/helm-charts
    version: "25.27.0"
```

## 최종 values.yaml

```yaml
prometheus:
  server:
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
      external_labels:
        cluster: ""

    defaultFlagsOverride:
      - --enable-feature=agent
      - --storage.agent.path=/data
      - --config.file=/etc/config/prometheus.yml
      - --web.console.libraries=/etc/prometheus/console_libraries
      - --web.console.templates=/etc/prometheus/consoles
      - --web.enable-lifecycle

    persistentVolume:
      enabled: false

    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        memory: 512Mi

    remoteWrite:
      - url: http://<중앙-grafana-수신-endpoint>/v1/prom/push
        headers:
          x-monitoring-service-code: "<서비스-식별-코드>"

  serverFiles:
    prometheus.yml:
      rule_files: []
      scrape_configs:
        - job_name: 'spring-apps'
          kubernetes_sd_configs:
            - role: endpoints
              namespaces:
                names:
                  - <앱-네임스페이스>
          relabel_configs:
            - source_labels: [__meta_kubernetes_endpoint_port_name]
              action: keep
              regex: metric
            - source_labels: [__meta_kubernetes_service_label_app]
              target_label: app
            - source_labels: [__meta_kubernetes_pod_node_name]
              target_label: node
            - source_labels: [__meta_kubernetes_pod_name]
              target_label: pod
          metrics_path: /actuator/prometheus

  alertmanager:
    enabled: false
  prometheus-pushgateway:
    enabled: false
  kube-state-metrics:
    enabled: false
  prometheus-node-exporter:
    enabled: false
```

설정 하나하나 짚어보자.

### Agent 모드 활성화 — defaultFlagsOverride

Prometheus를 Agent 모드로 실행한다. 일반 모드와 다른 점은 로컬 TSDB가 없다는 것이다.

- **일반 모드**: 수집 → 로컬 저장 → PromQL 쿼리 가능
- **Agent 모드**: 수집 → remote_write 전송 (WAL만 임시 사용)

Grafana가 사내 중앙 플랫폼에 있으니 클러스터 안에 데이터를 쌓을 필요가 없다. Agent 모드가 메모리도 훨씬 덜 먹는다. 실제로 일반 모드로 운영했을 때 519Mi를 쓰던 게 Agent 모드 전환 후 30Mi로 줄었다.

**왜 `defaultFlagsOverride`를 써야 하나?**

차트 deploy 템플릿의 args 블록이 이런 구조다.

```
if defaultFlagsOverride 설정됨
  → defaultFlagsOverride 내용만 사용
else
  → --storage.tsdb.retention.time   (retention 설정 시)
  → --storage.tsdb.path             ← 조건 없이 항상 추가
  → extraFlags
```

Prometheus는 Agent 모드에서 `--storage.tsdb.path`가 있으면 시작을 거부한다. `else` 블록 안에서는 이 플래그를 피할 방법이 없다.

`defaultFlagsOverride`를 쓰면 `else` 블록 자체를 건너뛰기 때문에 tsdb 플래그가 아예 추가되지 않는다. 그래서 아래처럼 시도했다가 실패한 방법들이 있다.

```yaml
# ❌ 이 차트에 없는 필드 — 그냥 무시됨
agentMode: true

# ❌ else 블록 안에서 실행됨 — tsdb 플래그와 함께 추가되어 충돌
extraFlags:
  - enable-feature=agent
```

### persistentVolume.enabled: false

PVC를 끄고 emptyDir을 쓴다. Agent 모드에서는 로컬 저장이 없으니 영구 볼륨이 필요 없고, 클러스터에 StorageClass가 없는 경우에도 이 설정이 필요하다.

StorageClass 없이 PVC를 만들면 Pending 상태로 계속 머물러 Pod가 뜨지 않는다.

### resources

```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    memory: 512Mi
```

리소스 제한을 꼭 걸어야 한다. 처음에 limits 없이 배포했다가 Prometheus가 메모리를 무제한으로 써서 노드 전체가 NotReady가 됐다. 2core/4GB 노드에서 다른 앱들과 함께 돌아야 하니 512Mi로 잡았다.

CPU limit은 의도적으로 안 걸었다. 메모리 OOM은 프로세스 종료로 이어지지만 CPU 스로틀링은 그냥 느려지는 거라서, 수집 지연은 감수할 수 있어도 OOM은 막아야 하기 때문이다.

### remoteWrite

```yaml
remoteWrite:
  - url: http://<엔드포인트>/v1/prom/push
    headers:
      x-monitoring-service-code: "<코드>"
```

수집한 메트릭을 Prometheus remote_write 프로토콜로 중앙 플랫폼에 전송한다. 중앙 플랫폼마다 인증 방식이 다를 텐데, HTTP 헤더로 서비스 식별 코드를 넘기는 방식이었다.

### serverFiles로 scrape job 정의

차트 기본값에는 `kubernetes-apiservers`, `kubernetes-nodes` 같은 k8s 시스템 scrape job이 10개 들어있다. OCR 앱 메트릭만 필요하므로 `serverFiles`로 완전히 덮어쓴다.

```yaml
serverFiles:
  prometheus.yml:
    rule_files: []          # Agent 모드에서 rule_files 미지원
    scrape_configs:
      - job_name: 'spring-apps'
        ...
```

`rule_files: []`도 명시해야 한다. Agent 모드는 alerting/recording rule을 지원하지 않아서, 기본값으로 들어오는 `rule_files` 항목이 있으면 설정 로드 자체가 실패한다.

`extraScrapeConfigs`를 쓰지 않는 이유도 있다. 차트 템플릿이 `serverFiles`의 `scrape_configs` 뒤에 `extraScrapeConfigs` 내용을 이어붙이는 방식인데, `scrape_configs: []`로 비워두면 빈 배열 뒤에 리스트 아이템이 붙는 구조가 되어 YAML 파싱 오류가 난다.

```yaml
# 이렇게 렌더링됨 → 파싱 에러
scrape_configs: []
- job_name: 'spring-apps'   ← invalid
```

scrape job을 직접 `serverFiles.prometheus.yml.scrape_configs`에 넣으면 이 문제가 없다.

### kubernetes_sd_configs (서비스 디스커버리)

```yaml
kubernetes_sd_configs:
  - role: endpoints
    namespaces:
      names:
        - <네임스페이스>
```

IP/포트를 직접 쓰는 게 아니라 K8s API를 통해 타겟을 자동으로 찾는다. `role: endpoints`는 Service에 연결된 Pod IP와 포트를 읽어온다. 네임스페이스를 지정하지 않으면 클러스터 전체를 뒤지니 필요한 곳만 지정하자.

### relabel_configs

서비스 디스커버리로 찾은 타겟을 필터링하고 레이블을 붙이는 규칙들이다.

```yaml
relabel_configs:
  # metric 포트만 수집
  - source_labels: [__meta_kubernetes_endpoint_port_name]
    action: keep
    regex: metric

  # 메트릭에 app, node, pod 레이블 추가
  - source_labels: [__meta_kubernetes_service_label_app]
    target_label: app
  - source_labels: [__meta_kubernetes_pod_node_name]
    target_label: node
  - source_labels: [__meta_kubernetes_pod_name]
    target_label: pod
```

Spring Boot 앱 Service에 포트가 두 개 있다. HTTP 트래픽용 포트와 메트릭용 포트. 이름으로 구분해서 메트릭 포트만 수집하도록 필터링한다.

Service에 포트 이름을 붙이는 방법:

```yaml
spec:
  ports:
    - name: server    # 앱 트래픽용
      port: 80
      targetPort: 8080
    - name: metric    # 메트릭 수집용
      port: 8081
      targetPort: 8081
```

## 환경별 오버라이드

ArgoCD에서 `values.yaml`과 `alpha-values.yaml`을 순서대로 적용한다. 공통 설정은 `values.yaml`에, 환경별 차이는 오버라이드 파일에만 넣는다.

```yaml
# alpha-values.yaml
prometheus:
  server:
    global:
      external_labels:
        cluster: my-cluster-alpha
```

`cluster` 레이블을 환경마다 다르게 찍어두면 Grafana에서 클러스터별로 필터링하기 편하다.

## 트러블슈팅 정리

| 문제 | 원인 | 해결 |
|---|---|---|
| Pod가 Pending에서 안 뜸 | PVC Pending (StorageClass 없음) | `persistentVolume.enabled: false` |
| 노드 NotReady, 앱 전체 Terminating | limits 없는 Prometheus가 노드 메모리 고갈 | `memory limits: 512Mi` 설정 |
| CrashLoopBackOff | `extraFlags: enable-feature=agent` + 차트 기본 `--storage.tsdb.path` 충돌 | `defaultFlagsOverride`로 전환 |
| 앱 메트릭이 Grafana에 안 들어옴 | `extraScrapeConfigs`를 `server` 하위에 잘못 배치 | 차트 루트 레벨로 이동 후 `serverFiles`로 통합 |
| OOMKilled 반복 | Agent 모드 미적용으로 TSDB 15일 보관 + 기본 scrape job 10개 | `defaultFlagsOverride` + `serverFiles`로 기본 job 제거 |
| 설정 로드 실패 (`scrape_configs` 파싱 오류) | `serverFiles.scrape_configs: []` + `extraScrapeConfigs` 병용 시 YAML 구조 깨짐 | scrape job을 `serverFiles`에 직접 정의 |
| 설정 로드 실패 (`rule_files not allowed`) | Agent 모드에서 `rule_files` 미지원 | `rule_files: []` 명시 |

삽질을 정말 많이 했다. 차트 소스를 직접 뜯어보지 않으면 알기 어려운 것들이 있었다. `defaultFlagsOverride` 같은 건 values.yaml 주석에 예시가 있어서 찾을 수 있었지만, deploy 템플릿의 분기 구조를 이해하지 못하면 왜 `extraFlags`로는 안 되는지 납득하기 어렵다.

최종적으로 Agent 모드가 정상 동작하면 메모리 사용량이 드라마틱하게 줄어든다. 519Mi → 30Mi. TSDB가 없으니 당연한 결과다.
