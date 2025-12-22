# L4와 VIP(Virtual IP Address)

## L4 Load Balancer - OSI 4 계층에서 트래픽을 분배하는 장치

### L4는 OSI 4계층 (Transport Layer)

TCP/UDP 레벨에서 트래픽을 보고 판단하는 Load Balancer

L4가 판단할 떄 보는 정보는 4가지

- Source IP
- Source Port
- Destination IP
- Destination PORT

> 즉, **패킷의 헤더만 보고 어디로 보낼지를 결정**하는 것

### 다음과 같은 기능을 제공함

- **1. 트래픽 분산 (로드밸런싱)**
  - 예:
    - ```text
      VIP(20.30.40.50:443)
        -> 내부 서버1 (10.0.1.10)
        -> 내부 서버2 (10.0.1.11)
        -> 내부 서버3 (10.0.1.12)
      ```
  - 패킷을 보고 균등하게 나누어주는 것이 핵심
- **2. Health Check**
  - 서버가 죽었는지 확인하고 죽은 서버로는 트래픽을 보내지 않음
- **3. Connection 유지**
  - TCP Connection을 proxy하거나 pass-through 방식으로 서버로 전달

### L4의 특징

| 특징              | 의미                                    |
| ----------------- | --------------------------------------- |
| 빠름              | HTTP 내용까지 안 보고, 헤더만 보고 판단 |
| 단순함            | 포트 기반 트래픽 분배                   |
| Layer 7 기능 없음 | URL path, header 기반 routing 불가      |
| 예                | AWS NLB, GCP TCP LB 등                  |

> 즉, **L4는 매우 빠르고 단순한 로드밸런서다**

## VIP (Virtual IP Address)

- VIP 개념을 명확히 이해하면, "서비스가 어떻게 장애 없이 외부에 노출되는지"가 보임

### VIP란 무엇인가?

**실제 물리 서버가 아닌, 서비스 전체를 대표하는 가상의 IP 주소**

즉, 클라이언트는 VIP만 알면 됨 <br/>
VIP 뒤에서는 여러 서버가 돌아가고 있지만, <br/>
클라이언트는 그 존재를 모름

예:
카카오 서버가 실재로 5000대라고 해도 <br/>
사용자는 단 하나의 IP(VIP) 또는 하나의 도메인만 접근함

서비스 대표 주소가 바로 VIP

### VIP는 왜 필요한가?

- **서버는 죽을 수 있지만, IP는 죽으면 안 된다**
  - 서버 1이 고장나도, 서버 2로 트래픽을 넘겨야 하는 경우에
  - 그런데 서버 1의 물리 IP를 서비스에 그대로 쓰면?
  - 서버 1이 죽는 순간 서비스 전체가 죽음
  - 따라서 "변하지 않는 서비스용 IP"가 필요 함
  - 그래서 등장한 것이 VIP

### VIP는 누가 가지고 있나?

- L4 로드밸런서
- L7 로드밸런서
- Keepalied VRRP (HA 구성)
- Kubernetes LoadBalancer -> 외부 IP
- MetalLB -> 할당된 VIP

즉, VIP는 **"특정 장비(또는 소프트웨어)가 소유하는 가상IP"**야

## L4와 VIP의 관계 (제일 많이 쓰이는 구조)

```text
  [클라이언트]
        |
        v
    [ VIP ]
        |
    [ L4 Load Balancer ]
        |
  -------------------------
  |         |            |
Server1   Server2     Server3

```

### 클라이언트는 VIP로 접속

### L4는 VIP로 받은 패킷을 내부 서버로 분산

- 각 서버는 private subnet(내부망)에 있음
- VIP는 보통 public 또는 shared subnet에 있음
- L4는 L3 라우팅을 통해 내부 서버에 전달

> 이 구조 덕분에 서버 100대를 운영해도 외부에 보이는 IP는 하나

### 정리

| 개념   | 설명                                            |
| ------ | ----------------------------------------------- |
| Subnet | 네트워크 구역                                   |
| L4     | TCP/UDP 기반 패킷 분배기                        |
| VIP    | 서비스 전체를 대표하는 단 하나의 IP             |
| 관계   | VIP는 L4가 바인딩하여 서비스 트래픽을 받는 주소 |

> 그래서 실무에서 자주 이렇게 말함 "VIP는 L4가 가지고 있는 서비스 대표 IP이다"

## Rserver(Real Server)란?

- 로드밸런더 뒤에서 실제 요청을 처리하는 서버를 말함
- VIP나 로드밸런서는 입구이고, Rserver는 일하는 주체
- 네트워크/로드밸런서 문맥에서 쓰이는 **약어성 용어**

```text
  [클라이언트]
        |
        v
    [ VIP ]
        |
    [ L4 Load Balancer ]
        |
  -------------------------
  |         |            |
RServer1   RServer2     RServer3

```

### 왜 "Real" Server라고 부를까?

- VIP는 가상(IP) 이고, Rserver는 **실제 물리/가상 서버**이기 떄문
- 그래서 로드밸런서 설정 문서나 장비(F5, A10등)에서 "VIP <-> Rserver Pool" 이라는 표현을 많이 씀

### 어디에서 주로 쓰이는 용어인가?

- **전통적인 L4/L7 로드밸런서 계열**에서 많이 등장
  - F5 BIG-IP
  - A10 Networks
  - LVS(Linux Virtual Server)
- 반면에 요즘 클라우드/쿠버네티스 쪽에서는 다른 이름을 더 많이 씀
  - Backend Server
  - Target
  - Endpoint
  - Pod
  - Instance

### Rserver의 공통 특징

- Private IP를 가짐
- 외부에서 직접 접근하지 않음
- Health Check 대상
- 장애 시 Pool에서 자동 제외됨
