# MySQL JDBC Cursor 방식

MySQL JDBC 드라이버의 기본 동작 방식과 대용량 처리 시 주의해야 할 Cursor(Streaming) 모드를 정리했다.

---

## MySQL JDBC의 기본 동작: Fetch All

`executeQuery()`를 실행하면 드라이버가 결과셋 **전체를 애플리케이션 메모리로 한 번에 가져온다**.
`next()`를 호출하면 메모리에 올라온 데이터를 순서대로 반환한다.

```
executeQuery() 호출
    → DB에서 전체 결과셋 조회
    → 애플리케이션 메모리(힙)에 전부 로드
    → next()로 하나씩 꺼냄 (DB 통신 없음)
```

**장점**: 네트워크 통신 1회 → 빠름
**단점**: 1,000만 건이면 힙에 전부 올라감 → `OutOfMemoryError` 위험

---

## Cursor 기반 Streaming 모드

결과셋을 한 건씩(또는 배치 단위로) 가져오는 방식이다. 메모리에 전체를 올리지 않는다.

### 활성화 방법

#### 1. URL 파라미터 방식 (useCursorFetch)

```
jdbc:mysql://localhost:3306/database?useCursorFetch=true
```

`useCursorFetch=true`를 설정하면 `Statement.setFetchSize(n)` 호출 시 실제로 n건씩 가져온다.

```java
PreparedStatement stmt = conn.prepareStatement(sql);
stmt.setFetchSize(1000);  // 1000건씩 가져옴
ResultSet rs = stmt.executeQuery();
while (rs.next()) {
    // 처리
}
```

#### 2. Integer.MIN_VALUE 방식 (Streaming)

`useCursorFetch` 없이도 `setFetchSize(Integer.MIN_VALUE)`를 설정하면 스트리밍 모드가 활성화된다.

```java
stmt.setFetchSize(Integer.MIN_VALUE);  // 한 건씩 스트리밍
```

주의: 스트리밍 모드에서는 ResultSet이 열려있는 동안 **같은 커넥션에서 다른 쿼리를 실행할 수 없다**.

---

## Spring Batch에서의 활용

Spring Batch의 `JdbcCursorItemReader`는 내부적으로 이 Cursor 방식을 사용한다.

```java
@Bean
public JdbcCursorItemReader<MyEntity> reader(DataSource dataSource) {
    return new JdbcCursorItemReaderBuilder<MyEntity>()
        .name("myReader")
        .dataSource(dataSource)
        .sql("SELECT * FROM my_table WHERE status = 'PENDING'")
        .rowMapper(new MyEntityRowMapper())
        .fetchSize(1000)          // 1000건씩 커서로 가져옴
        .build();
}
```

`JdbcPagingItemReader`는 OFFSET/LIMIT 방식으로 페이지 단위 조회하는 것과 달리, `JdbcCursorItemReader`는 커서를 열어두고 순차적으로 읽는다. 정렬이 보장된 대용량 순차 처리에 적합하다.

| Reader | 방식 | 특징 |
|---|---|---|
| `JdbcCursorItemReader` | DB 커서 유지 | 단일 커넥션 점유, 대용량 순차 처리 |
| `JdbcPagingItemReader` | OFFSET/LIMIT | 커넥션 재사용 가능, 페이지 처리 |

---

## 주의사항

- **커넥션 점유 시간**: Cursor 방식은 처리가 끝날 때까지 커넥션을 점유한다. 긴 배치 작업에서는 커넥션 풀이 고갈될 수 있다
- **트랜잭션 범위**: 커서가 열린 상태에서 트랜잭션이 커밋되면 커서가 닫힐 수 있다. Spring Batch chunk 처리 시 `read()` 단계와 `write()` 단계의 트랜잭션 경계를 이해해야 한다
- **MySQL 서버 부하**: Cursor 모드에서 MySQL은 서버 측 커서를 유지한다. 동시에 많은 커서를 열면 서버 부하가 증가한다
