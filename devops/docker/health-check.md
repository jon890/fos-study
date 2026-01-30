# Dockerfile의 HeatlCheck

```Dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8080}/actuator/health || exit 1
```

단순 상태 표시용 데코레이션이 아니라, 컨테이너 오케스트레이션(순서 제어, 복구)의 핵심 메커니즘이 된다.

## 1. 동작 메커니즘: "내부 프로세스 실행 & 종료 코드 감지"

`HEALTHCHECK`는 마법이 아님. Docker 데몬이 호스트에서 컨테이너 내부로 <br>
**`exec` 명령을 주기적으로 날리는 크론잡**과 같다.

- **1. 실행**:
  - 설정된 `interval` 마다 Docker는 컨테이너 내부 쉘에서 정의된 명령을 실행한다.
- **2. 판단(Exit Code)**:
  - 명령어의 종료 코드를 확인한다
    - 0: 성공
    - 1: 실패
- **3. 상태 전이**:
  - 실패했다고 바로 `Unhealthy`가 되는 것이 아니라, `retries` 횟수만큼 연속으로 실패해야 상태가 변한다

## 2. 생명 주기 (State Machine)

컨테이너는 3가지 헬스 상태 중 하나를 가진다

- **1. staring**
  - 컨테이너가 막 시작된 상태
  - 이때는 실패해도 카운트하지 않음
  - `start-period` 설정 동안 유지됨
- **2. healthy**
  - 명령어가 성공(0)함
- **3. unhealthy**
  - `retries` 횟수만큼 연속으로 실패(1)함

## 3. 디버깅: "왜 Unhealthy인지 로그 보기"

`docker inspect`에는 최근 헬스체크 기록이 보관된다.

```bash
docker inspect --format "{{json .State.Health}}" [컨테이너명] | jq
```

출력 예시:

```json
{
  "Status": "unhealthy",
  "FailingStreak": 3,
  "Log": [
    {
      "Start": "2026-01-30T14:00:00Z",
      "End": "2026-01-30T14:00:01Z",
      "ExitCode": 1,
      "Output": "curl: (7) Failed to connect to localhost port 8080: Connection refused"
    }
  ]
}
```

## 4. 실전 활용: Docker compose `depends_on`

"DB가 먼저 뜨고 앱이 떠야 한다"라는 조건이 있을 떄 `HEALTHCHECK`가 바로 그 열쇠이다.

```yml
services:
  db:
    image: mysql
    healthcheck:
      test: ['CMD', 'mysqladmin', 'ping', '-h', 'localhost']
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    depends_on:
      db:
        condition: service_healthy # <--- 핵심!
```

이렇게 하면 백엔드 컨테이너는 MySQL 컨테이너가 단순히 "생성"된 시점이 아니라, <br>
**"실제로 쿼리를 받을 준비가 된(Healthy)"** 시점에 시작된다.
