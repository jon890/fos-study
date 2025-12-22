# Java의 로깅 환경

- 자바 로깅은 API <-> 구현체 <> 수집/분석 시스템으로 나뉜다고 보면 됨

```text
코드 -> 로깅 API -> 로깅 구현체 -> 로그 저장/분석 서비스
```

## 1. 로깅 API (인터페이스 계층)

- slf4j (사실상 표준)
- 역할:

  ```java
    log.info("orderId = {}", orderId);
  ```

  - 같은 공통 인터페이스 제공

- 장점
  - 구현체 교체 가능
  - 라이브러리간 로깅 충돌 최소화

## 2. 로깅 구현체 (실제 동작)

- 여기서 **Logback**이 등장

| 구현체            | 특징                              |
| ----------------- | --------------------------------- |
| Logback           | Spring Boot 기본, 빠름, 설정 유연 |
| Log4j2            | 고성능, 대규모 트래픽             |
| java.util.logging | JDK 기본 (실무에선 거의 안씀)     |

### Logback은 정확히 무슨 역할일까?

- Logback = sl4fj를 실제로 구현한 로깅 엔진
- 하는일:
  - 로그 레벨 관리 (TRACE ~ ERROR)
  - 로그 포맷 지정
  - 로그 출력 위치 제어
    - 콘솔
    - 파일
    - JSON
    - 외부 시스템 전송
  - 비동기 로깅

<br />

- 핵심 구성 요소

| 구성     | 설명                         |
| -------- | ---------------------------- |
| Appender | 로그를 "어디로" 보낼지       |
| Encoder  | 로그 포맷                    |
| Logger   | 패키지/클래스 단위 레벨 제어 |

<br />

- Spring Boot + Logback 구조

```text
application.yml
logback-spring.yml
```

- `logback-spring.yml` 사용하면
  - profile별 로그 분리
  - Spring property 사용 가능
