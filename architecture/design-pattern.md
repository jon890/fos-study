# 디자인 패턴

**소프트웨어 설계 과정에서 반복적으로 발생하는 문제들에 대해 검증된 해결책을 정형화한 모범 사례**라고 정의할 수 있다.

이 문서는 아키텍처/설계 패턴의 가벼운 허브 문서다. 각 패턴의 핵심 개념만 빠르게 훑고, 자세한 학습은 개별 상세 문서로 이어지도록 구성한다.

## 빠른 포인터

- [전략 패턴 상세 문서](./strategy-pattern.md)
  - 런타임에 알고리즘을 교체하는 구조, 분기문 제거, OCP/테스트 용이성 중심 정리
- [분산 아키텍처 상세 문서](./distributed-architecture-study-pack.md)
  - 서비스 경계, 장애 전파, 일관성, 메시징, 멱등성, 시니어 인터뷰 관점 정리

## 언제 어떤 문서를 보면 좋을까

- 디자인 패턴을 빠르게 복습하고 싶다
  - 이 문서
- 전략 패턴을 실무 예시와 인터뷰 관점까지 깊게 보고 싶다
  - [strategy-pattern.md](./strategy-pattern.md)
- 시스템 규모 확장, 서비스 분리, 분산 트레이드오프까지 같이 보고 싶다
  - [distributed-architecture-study-pack.md](./distributed-architecture-study-pack.md)

## 전략 패턴 (Strategy Pattern)

**실행 중에 알고리즘을 선택할 수 있게 하는 패턴**

- 알고리즘을 선택한다? 
  - **특정 기능을 수행하는 여러 가지 방식 중 상황에 맞는 하나를 런타임에 동적으로 결정한다**
  - 실제 처리 로직을 인터페이스 뒤로 숨기고 클라이언트가 필요한 로직을 선택해 사용할 수 있게 만드는 것

### 핵심 구조

객체가 할 수 있는 행위들을 각각 전략(Strategy)이라는 클래스로 캡슐화하고, 이들을 인터페이스를 통해 추상화한다.
- Strategy (인터페이스) : 모든 지원하는 알고리즘에 공통적인 인터페이스를 정의한다.
- ConcreteStrategy (구현체) : 실제 알고리즘을 구현한 클래스들이다.
- Context (문맥) : Strategy를 사용하는 역할을 하며, 필요애 따라 전략 객체를 교체할 수 있다.

### 예시

결제 시스템에서 결제 수단(카드, 네이버페이, 카카오페이)에 따라 결제 로직이 달라지는 경우를 생각해보자.

- PaymentStrategy를 인터페이스를 정의한다
- CardPayment, NaverPayPayment, KakaoPayPayment 등의 실제 전략 구현체들을 정의한다.
- PaymentService 는, 런타임에 실제 구현체들을 사용해서 결제를 처리한다.

### 장단점

- OCP(개방-폐쇄 원칙) 준수 : 새로운 결제 수단이 추가되어도 기존 `PaymentService` 코드를 수정할 필요 없이, 새로운 `PaymentStrategy` 구현체만 추가하면 된다.

### 언제 사용하면 좋을까?

- 유사한 행위들이 데이터만 다른게 아니라 **로직 자체가 다를 때**
- 하나의 클래스 안에 `if-else` 분기가 너무 많아져 가독성을 해칠 때
- 런타임 중에 객체의 알고리즘을 동적으로 변경해야 할 때

### 실제 사례

- [임베딩 메타데이터 구성 방식 개선 — Blocklist에서 Allowlist로](../task/ai-service-team/embedding-metadata-provider.md): DocumentType별 메타데이터 구성 로직을 `EmbeddingMetadataProvider` 인터페이스로 분리. Spring DI의 자동 수집과 결합해 새 타입 추가 시 기존 코드 수정 없이 확장
- [Confluence 벡터 색인 배치](../task/ai-service-team/rag-vector-search-batch.md): 스페이스별 메타데이터 포맷 차이를 `ConfluenceDocumentMetadataProvider` 인터페이스로 추상화

