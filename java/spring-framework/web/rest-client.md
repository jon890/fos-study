# RestClient

- 스프링 부트 3.2에서 새롭게 도입
- `RestTemplate`이나 `WebClient`를 사용했을 텐데 `RestClient`로 그 간극을 메워줄 수 있다.

## 1. RestClient란 무엇인가?

- `RestClient`란 **동기식(Synchronous) API 호출**을 위한 현대적인 인터페이스
- 기존 `RestTemplate`의 고질적인 문제인 "지나치게 많은 오버로딩 메서드"와 `WebClient`의 장점인 "Fluent API(체이닝)" 방식을 결합함
  - 동기 방식 : `RestTemplate` 처럼 블로킹 방식으로 동작
  - 현대적 문법 : `WebClient` 처럼 `.get()`, `uri()`, `retrieve()` 형태로 가독성 좋게 코드를 짤 수 있음
  - Spring Boot 3.2+ : 최신 버전 프로젝트라면 이제 `RestTemplate` 대신 권장되는 선택지

## 2. 기본적으로 어떤 HTTP Client를 사용하는가?

- 실제 통신은 하위의 `ClientHttpREquestFactory`가 담당하는 추상화 구조를 가짐
- 기본 라이브러리
  - 따로 설정을 하지 않는다면, **JDK의 표준 `HttpURLConnection`**을 사용함
  - 하지만 이는 커넥션 풀링 같은 고급 기능을 지원하지 않아 운영 환경에서는 보통 교체해서 사용함
- 라이브러리 감지 및 자동 설정
  - Spring Boot는 클래스패스에 어떤 라이브러리가 있느냐에 따라 우선순위를 두고 라이브러리를 선택
  - **Apache HttpClient 5** : 클래스패스에 있으면 최우선으로 사용 (가장 많이 쓰이는 옵션)
    - `HttpComponentsClientHttpRequestFactory`
  - **Jetty HttpClient** : Apache가 없고 Jetty가 있으면 사용
  - **Reactor Netty** : WebFlux 환경일 떄 주료 사용
  - **JDK HttpClient** : Java 11 이상에서 제공하는 표준 클라이언트를 명시적으로 설정할 수 있음

## 3. Apache HttpClient 5를 사용하면 좋은 이유?

- Connection Pooling : 매 요청마다 연걸을 맺고 끊는 오버헤드를 줄임
- Keep-Alive 전략 : 서버와의 연결 유지 시간을 정교하게 제어
- Retry 전략 : 네트워크 일시 오류 시 재시도 로직을 태울 수 있음
