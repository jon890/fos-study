# Envoy Proxy

Lyft가 만들고 CNCF가 관리하는 고성능 L7 프록시. 마이크로서비스 환경에서 서비스 간 통신을 중개하도록 설계됐다.

---

## 왜 nginx 말고 Envoy인가

사실 처음엔 "그냥 nginx 쓰면 안 되나?"라고 생각했다. nginx도 충분히 강력하고 익숙하니까. 근데 유지보수 맡은 OCR 프로젝트를 뜯어보니 Envoy를 쓸 수밖에 없는 이유가 명확했다.

| 항목 | nginx | Envoy |
|------|-------|-------|
| 설계 시점 | 2000년대 초 (정적 웹 서버 중심) | 2016년 (마이크로서비스 중심) |
| 설정 반영 | 파일 수정 후 reload 필요 | xDS API로 재시작 없이 동적 반영 |
| gRPC 지원 | 기본 미지원 (모듈 추가 필요) | gRPC 네이티브 지원 |
| HTTP/JSON ↔ gRPC 변환 | 불가 | `grpc_json_transcoder` 필터로 자동 변환 |
| 관측성 (Observability) | 기본 로그 중심, 추가 설정 필요 | 기본으로 메트릭/트레이싱/로그 지원 |
| 서비스 메시 통합 | 별도 솔루션 필요 | Istio 등의 데이터 플레인으로 직접 활용 |
| 리소스 사용량 | 가볍고 효율적 | nginx 대비 메모리/CPU 더 사용 |

요약하면, nginx는 정적 파일 서빙이나 전통적인 리버스 프록시에 강하고, Envoy는 gRPC 변환이나 동적 설정이 필요한 마이크로서비스 환경에 강하다. OCR 프로젝트처럼 HTTP 클라이언트가 gRPC 백엔드를 호출해야 하는 구조에서는 Envoy가 사실상 유일한 선택지다.

---

## 핵심 개념: Listener / Filter Chain / Cluster

Envoy 설정을 보면 처음엔 용어가 낯설다. 세 가지만 이해하면 전체 구조가 보인다.

### Listener

Envoy가 바인딩하는 포트. 외부에서 들어오는 트래픽의 진입점이다.

```
클라이언트 → Listener(:5000) → ...
```

여러 포트를 동시에 리스닝할 수 있고, 포트마다 독립적인 처리 파이프라인을 구성할 수 있다.

### Filter Chain

Listener에 연결된 처리 파이프라인. 실제 요청 처리 로직이 여기에 정의된다.

연결이 들어오면 Envoy는 매칭 조건에 따라 적절한 Filter Chain을 선택하고, 체인에 등록된 필터들을 순서대로 실행한다.

```
Listener → Filter Chain 선택
              └─ HTTP Connection Manager
                    └─ HTTP Filter 1 (grpc_json_transcoder)
                    └─ HTTP Filter 2 (router)
```

필터 종류:
- **Listener Filter**: 네트워크 필터보다 먼저 실행. 커넥션 메타데이터 조작 (예: TLS 감지)
- **Network Filter**: L3/L4 처리 (예: HTTP Connection Manager)
- **HTTP Filter**: HTTP 레이어 처리 (예: grpc_json_transcoder, CORS, rate limiting)

### Cluster

업스트림 서비스를 정의하는 단위. "어디로 보낼 것인가"를 정의한다.

```
Filter Chain → (route_config) → Cluster → 실제 백엔드 서버
```

Cluster에는 로드밸런싱 정책, 헬스체크, 타임아웃, 프로토콜(HTTP/1.1 or HTTP/2) 등을 설정한다. gRPC는 HTTP/2 기반이므로 gRPC 백엔드 Cluster에는 `http2_protocol_options`를 설정해야 한다.

---

## grpc_json_transcoder 동작 원리

이게 이 프로젝트에서 Envoy를 쓰는 핵심 이유다.

### 구조

```
클라이언트 (HTTP/JSON)
    ↓  POST /ocr.OcrService/Recognize
    ↓  Body: {"image_url": "..."}
Envoy (:5000)
    ↓  grpc_json_transcoder 필터가 JSON → Protobuf 변환
    ↓  gRPC 호출로 래핑
OCR gRPC 서버 (localhost:50051)
    ↓  응답: Protobuf
Envoy
    ↓  Protobuf → JSON 변환
클라이언트 (JSON 응답 수신)
```

### 사전 조건: Proto Descriptor

Envoy는 어떤 필드를 어떻게 변환할지 알기 위해 `.proto` 파일에서 생성한 binary descriptor가 필요하다. 이걸 미리 컴파일해서 파일로 제공해야 한다.

```bash
# googleapis 리포지토리 클론 (google/api/annotations.proto 필요)
git clone https://github.com/googleapis/googleapis.git

# descriptor 생성
protoc \
  -I${GOOGLEAPIS_DIR} \
  -I. \
  --include_imports \
  --include_source_info \
  --descriptor_set_out=protos/service.pb \
  protos/service.proto
```

`google.api.http` 옵션으로 HTTP 매핑을 `.proto`에 직접 정의한다:

```protobuf
syntax = "proto3";
package ocr;

import "google/api/annotations.proto";

service OcrService {
  rpc Recognize (RecognizeRequest) returns (RecognizeResponse) {
    option (google.api.http) = {
      post: "/v1/recognize"
      body: "*"
    };
  }
}
```

이 매핑이 있어야 `POST /v1/recognize`로 들어온 요청을 `OcrService.Recognize` gRPC 메서드로 라우팅할 수 있다.

### Envoy 설정 예시

```yaml
static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 5000
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                codec_type: AUTO
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: grpc_backend
                http_filters:
                  # 1. JSON ↔ gRPC 변환 필터
                  - name: envoy.filters.http.grpc_json_transcoder
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.grpc_json_transcoder.v3.GrpcJsonTranscoder
                      proto_descriptor: "/etc/envoy/protos/service.pb"
                      services: ["ocr.OcrService"]
                      print_options:
                        add_whitespace: true
                        always_print_primitive_fields: true
                        preserve_proto_field_names: true
                  # 2. 라우팅 필터 (항상 마지막)
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
    - name: grpc_backend
      connect_timeout: 5s
      type: LOGICAL_DNS
      lb_policy: ROUND_ROBIN
      # gRPC는 HTTP/2 필수
      typed_extension_protocol_options:
        envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
          "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
          explicit_http_config:
            http2_protocol_options: {}
      load_assignment:
        cluster_name: grpc_backend
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: localhost
                      port_value: 50051
```

### 변환 흐름 요약

1. 클라이언트가 `POST /v1/recognize` 로 JSON 요청 전송
2. Envoy가 proto descriptor를 참조해서 어느 gRPC 메서드로 라우팅할지 결정
3. JSON body를 Protobuf 바이너리로 직렬화
4. gRPC 프레이밍(length-prefixed message + HTTP/2 trailer)으로 감싸서 백엔드로 전송
5. gRPC 응답(Protobuf)을 역직렬화해서 JSON으로 변환 후 클라이언트에 반환

---

## Istio와의 관계

Envoy를 혼자 띄워서 쓰는 게 위의 OCR 프로젝트 구조다. 근데 Envoy가 더 유명해진 건 Istio 때문이다.

### 서비스 메시에서 Envoy의 역할

Istio는 쿠버네티스 위에서 동작하는 서비스 메시다. 구조상 두 개의 플레인이 있다.

```
[Control Plane]
  Istiod (Pilot + Citadel + Galley 통합)
    └─ 트래픽 정책, 인증서, 설정을 xDS API로 배포

[Data Plane]
  Pod A: [App Container] + [Envoy Sidecar]
  Pod B: [App Container] + [Envoy Sidecar]
  Pod C: [App Container] + [Envoy Sidecar]
```

Istio가 Pod를 배포할 때 자동으로 Envoy 컨테이너를 사이드카로 주입(`istio-proxy`)한다. 동시에 init 컨테이너가 iptables 규칙을 설정해서 Pod의 모든 인바운드/아웃바운드 트래픽을 Envoy를 거치도록 강제한다. 앱 코드는 Envoy 존재를 모른다.

### Envoy 단독 vs Istio 속 Envoy

| | Envoy 단독 (OCR 프로젝트) | Istio 속 Envoy |
|---|---|---|
| 설정 방식 | 직접 YAML 작성 | Istiod가 xDS API로 자동 배포 |
| 역할 | HTTP↔gRPC 게이트웨이 | 모든 서비스 간 통신 중개 |
| 규모 | 1개 프록시 | 모든 Pod마다 1개 |
| 관측성 | 직접 설정 | Jaeger/Prometheus 자동 연동 |

Istio는 Envoy를 데이터 플레인 엔진으로 쓴다. Envoy를 추상화해서 운영자는 Istio의 `VirtualService`, `DestinationRule` 같은 고수준 리소스만 다루면 된다. Istiod가 이걸 Envoy 설정으로 변환해서 각 사이드카에 xDS API로 밀어준다.

---

## 참고 링크

- [Envoy 공식 문서 - gRPC-JSON transcoder filter](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/grpc_json_transcoder_filter)
- [Envoy 공식 문서 - Listeners 아키텍처](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/listeners/listeners)
- [Envoy 설정 개요 - Listeners, Clusters (CodiLime 블로그)](https://codilime.com/blog/envoy-configuration/)
- [Istio 공식 문서 - 아키텍처](https://istio.io/latest/docs/ops/deployment/architecture/)
- [Istio 사이드카 트래픽 인터셉트 원리 (Jimmy Song)](https://jimmysong.io/blog/understanding-how-envoy-sidecar-intercept-and-route-traffic-in-istio-service-mesh/)
- [Envoy vs NGINX 비교 (Wallarm)](https://www.wallarm.com/cloud-native-products-101/envoy-vs-nginx-edge-and-service-proxy)
- [JSON to gRPC transcoding with Envoy (Aapeli Vuorinen)](https://www.aapelivuorinen.com/blog/2020/08/01/envoy-json-grpc-transcoding/)
