# HTTP Connection Pool

- 요약 :
  > HTTP는 TCP/TLS 연결 비용이 크기 때문에, 매 요청마다 새 연결을 새엇ㅇ하면 latency와 CPU 부하가 커진다</br>
  > 그래서 Node.js에서는 keep-alive 기반의 connection pool을 사용해 연결을 재사용하는 것이 필수</br>
  > 보통 1개의 외부 API 서버에 대해 인스턴스당 10~100개의 커넥션 풀을 유지하는 것이 가장 안정적이며,</br>
  > Node 공식 undici client는 이 pool을 기본적으로 잘 지원합니다.

## HTTP에 왜 Connection Pool이 필요한가?

### 이유 1 - TCP 연결 비용이 생각보다 매우 비싸다

- HTTP 요청 1번을 하기 위해 실제로는

  - TCP 3-way handshake
  - TLS handshake(HTTPS 일 떄)
  - 이후 요청 전송
  - 즉 연결(Connection)은 **엄청 비싼 작업**이다.
  - TLS handshake는 보통 40~80ms 걸릴 수 있다.

- 만약 매 요청마다 연결을 새로 만들면
  - latency 늘어남
  - CPU 사용 증가
  - 서버/클라이언트 모두 리소스 낭비
  - TPS 저하
- 그래서 한번 만든 연결을 재사용하는 keep-alive 구조가 필요함

### 이유 2 - 외부 API는 대부분 Keep-Alive(지속 연결)을 지원한다

- HTTP/1.1은 기본적으로
  - ```text
    Connection: keep-alive
    ```
  - 이어서 같은 TCP 연결을 계속 재사용함
- > TCP 커넥션 하나가 여러 HTTP 요청을 처리할 수 있다
- 그런데 Node의 기본 HTTP client는 요청마다 기본적으로 새 연결을 열어버리는 경우가 있다
  - 특히 fetch, axios에서 agent 옵션 안 주면!

### 이유 3 - 서버 또는 외부 API도 connection 제한이 있다

- 외부 API 서버는 다음과 같은 제한을 건다
  - IP당 ㅇ녀결 개수 제한
  - Too many connections 보호
  - Rate limit - concurrency limit
- 한 인스턴스가 수백 개의 연결을 계속 만든다면 타 서버 입장에서는 DOS 처럼 보일 수 있음
- 그래서 커넥션 풀로 **적절한 연결 수를 유지**하는 것이 중요함

### 이유 4 - Node에서 커넥션 풀을 사용하면 GC/메모리 안정성도 올라간다

- Node에서 새로운 HTTP client를 계속 만들면
  - 새로운 Socket 객체 생성
  - Buffer 생성
  - GC pressure 증가
- 반대로 풀을 사용하면
  - Socket 재사용
  - Buffer 재사용
  - GC 부하 감소
- 안정성이 크게 올라감

## Keep-Alive가 켜져있으면 어떻게 동작하는가?

> 같은 서버 (출발지 /목적지)와의 동일 TCP 연결을 재상용한다.
> -> 따라서 TCP handshake + TLS handshake를 다시 하지 않아도 된다.

즉, **재요청 시 매우 작은 비용으로 바로 HTTP 요청을 보낼 수 있다.**

## HTTP/1.0 vs HTTP1.1 Keep-Alive 사양

### HTTP/1.0

- 기본 : 모든 요청 후 연결을 닫는다
- 지속 연결을 원할 떄만 Connection: keep-alive 헤더를 명시해야 했다
- 이게 없으면 반드시 Connection close

### HTTP/1.1

- 기본 : 지속 연결 (persistent connection)
  - 즉 연결을 유지하려고 시도함
- HTTP/1.1 명세(RFC 2068, RFC 2616)에서 이렇게 정의됨
  - 기본적으로 keep-alive 상태
  - 명시적으로 종료하고 싶은 경우만 Connection: close

### 그런데 왜 Node, axios, undici는 keep-alive 설ㅈ어이 필요한 것처럼 느껴질까?

- 실제로는 **HTTP 사양과 Node의 구현이 완전히 동일하게 작동하지 않는다**
- Node의 기본 http/https Agent는 keep-alive가 "비활성화" 되어 있음
  - Node의 기본 fetch/axios 요청은 내부적으로 Node의 http.Agent를 사용하는데 이 Agent는 직접 keepAlive: true 옵션을 줘야만 연결 재사용을 한다
- 그렇지 않으면 HTTP/1.1 이더라도 Node는 내부적으로 socket을 닫아버린다

### 그렇다면 undici는?

- undici는 Node 팀이 만든 고성능 HTTP 엔진이고 여기서는 HTTP/1.1 규격을 반영한다
  - keep-alive를 기본으로 사용한다
  - connection pool을 유지한다
- 그래서 fetch(Node 18+) = undici 기반 -> keep-alive 활성화됨
- ky = fetch 기반 -> undici 덕분에 keep-alive 사용
