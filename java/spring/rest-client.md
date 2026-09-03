---
tags: [study]
---

# RestClient

- API 자체는 **Spring Framework 6.1**에서 도입되고, **Spring Boot 3.2**가 빌더 자동 설정을 제공한다
- `RestTemplate`이나 `WebClient`를 사용했을 텐데 `RestClient`로 그 간극을 메워줄 수 있다.

## RestClient란 무엇인가?

- `RestClient`란 **동기식(Synchronous) API 호출**을 위한 현대적인 인터페이스
- 기존 `RestTemplate`의 고질적인 문제인 "지나치게 많은 오버로딩 메서드"와 `WebClient`의 장점인 "Fluent API(체이닝)" 방식을 결합함
  - 동기 방식 : `RestTemplate` 처럼 블로킹 방식으로 동작
  - 현대적 문법 : `WebClient` 처럼 `.get()`, `uri()`, `retrieve()` 형태로 가독성 좋게 코드를 짤 수 있음
  - Spring Boot 3.2+ : 최신 버전 프로젝트라면 이제 `RestTemplate` 대신 권장되는 선택지

## 어떻게 쓰는가?

Spring Boot는 `RestClient.Builder`를 자동 설정해 두므로 주입받아 쓰면 된다.
직접 `RestClient.create()`로 만들면 타임아웃 같은 Boot 설정이 적용되지 않는다.

```java
@Service
public class UserClient {

    private final RestClient restClient;

    public UserClient(RestClient.Builder builder) {
        this.restClient = builder.baseUrl("https://api.example.com").build();
    }

    public User findById(long id) {
        return restClient.get()
                .uri("/users/{id}", id)
                .retrieve()
                .body(User.class);
    }

    public User create(CreateUserRequest request) {
        return restClient.post()
                .uri("/users")
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(User.class);
    }
}
```

### 에러 처리 — `onStatus`

`retrieve()`는 4xx·5xx에서 예외를 던진다.
상태 코드별로 다르게 처리하려면 `onStatus`로 가로챈다.

```java
return restClient.get()
        .uri("/users/{id}", id)
        .retrieve()
        .onStatus(HttpStatusCode::is4xxClientError, (req, res) -> {
            if (res.getStatusCode() == HttpStatus.NOT_FOUND) {
                throw new UserNotFoundException(id);
            }
            throw new IllegalArgumentException("잘못된 요청: " + res.getStatusCode());
        })
        .onStatus(HttpStatusCode::is5xxServerError, (req, res) -> {
            throw new ExternalApiException("상대 서버 오류: " + res.getStatusCode());
        })
        .body(User.class);
```

- 예외를 던지지 않고 응답을 그대로 받고 싶으면 `retrieve()` 대신 `exchange()`를 쓴다
- 제네릭 타입은 `body(new ParameterizedTypeReference<List<User>>() {})` 형태로 받는다

## 기본적으로 어떤 HTTP Client를 사용하는가?

- 실제 통신은 하위의 `ClientHttpRequestFactory`가 담당하는 추상화 구조를 가짐
- 따로 설정하지 않으면 Spring Boot가 **클래스패스를 보고 선호 순서대로** 고른다
  - 공식 문서의 순서는 다음과 같다 (In order of preference)
    1. Apache HttpClient — `HttpComponentsClientHttpRequestFactory`
    2. Jetty HttpClient
    3. Reactor Netty HttpClient
    4. JDK client (`java.net.http.HttpClient`)
    5. Simple JDK client (`java.net.HttpURLConnection`)
  - 여러 개가 함께 있으면 **가장 앞선 것**이 선택됨
  - `spring.http.clients.imperative.factory` 로 명시 지정할 수 있음
- **`HttpURLConnection`은 기본값이 아니라 마지막 폴백**이다
  - 위 네 가지가 하나도 없을 때만 여기까지 내려온다
  - 커넥션 풀링을 지원하지 않아, 여기까지 내려왔다면 운영 환경에서는 교체 대상이다
  - 출처: [Spring Boot — HTTP Clients](https://docs.spring.io/spring-boot/reference/io/rest-client.html)

## Apache HttpClient 5를 사용하면 좋은 이유?

- Connection Pooling : 매 요청마다 연결을 맺고 끊는 오버헤드를 줄임
- Keep-Alive 전략 : 서버와의 연결 유지 시간을 정교하게 제어
- Retry 전략 : 네트워크 일시 오류 시 재시도 로직을 태울 수 있음
