MySQL과 JDBC Cursor 방식

- MySQL JDBC 드라이버에는 특유의 독특한 동작 방식이 있어 주의해야 한다.

## MySQL JDBC의 기본 동작 (Fetch All)

- 보통의 설정에서 `executeQuery()`를 날리면, 드라이버는 DB로부터 결과 셋 전체를 애플리케이션 메모리로 전부 가져온다.
- 그리고 `next()`를 호출할 때마다 메모리에 있는 데이터를 하나씩 넘겨준다.
  - 장점 : 네트워크 통신 횟수가 줄어들어 속도가 빠름
  - 단점 : 데이터가 1,000만 건이면 서버 메모리가 터짐

## Cursor 기반의 Streaming 동작 (진정한 한 건씩 가져오기)

- 위와 같이 동작하게 하려면 MySQL 드라이버에게 스트리밍 모드로 동작하라고 명시적으로 알려줘야 함
- JDBC 연결 URL에 옵션을 준다
  - URL : jdbc:mysql://localhost:3306/database?useCursorFetch=true
