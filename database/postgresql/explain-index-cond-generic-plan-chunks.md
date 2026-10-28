---
series: "PostgreSQL 실행 계획 읽기"
seriesOrder: 1
tags: [study]
---

# PostgreSQL 실행 계획 읽기: Index Cond와 Filter, heap 접근, generic plan과 TimescaleDB 청크 제외

PostgreSQL 실행 계획에서 같은 인덱스를 탔는데도 느린 이유는 대개 세 가지 중 하나다.
조건 일부가 인덱스 탐색(`Index Cond`)이 아니라 읽은 뒤 버리는 `Filter`로 처리되거나, 찾은 행마다 테이블 본체(heap)를 다시 읽거나, 계획을 세운 시점에 값을 몰라 읽을 범위를 줄이지 못한 경우다.
이 글은 가상의 IoT 측정 테이블에 예제를 직접 돌려 이 세 가지가 실행 계획에서 어떻게 보이는지, 왜 성능에 영향을 주는지 정리한다.

MySQL 실행 계획은 읽을 수 있지만 PostgreSQL과 TimescaleDB는 낯선 Java 백엔드 개발자를 독자로 잡았다.
B-Tree와 복합 인덱스의 일반 원리는 다시 설명하지 않는다.

> [!TIP]
> **더 읽을 글**: [MySQL 복합 인덱스 완전 정복](../mysql/composite-index.md)의 「좌측 접두사 규칙」과 「커버링 인덱스」 절.
> 복합 인덱스의 칼럼 순서와 커버링 인덱스의 기본 개념은 MySQL과 PostgreSQL이 같다. 이 글은 PostgreSQL에서 달라지는 부분만 다룬다.

## 적용 버전과 근거의 구분

| 대상 | 버전 |
| --- | --- |
| PostgreSQL | 17.10 (`timescale/timescaledb:2.27.2-pg17` 이미지) |
| TimescaleDB | 2.27.2 |
| PostgreSQL JDBC 드라이버(pgjdbc) | 공식 문서 기준 |

본문에서는 근거의 종류를 다음처럼 구분한다.

- **출처**: PostgreSQL 17 공식 문서, PostgreSQL 소스(`REL_17_STABLE`), TimescaleDB 문서와 소스(`2.27.2` 태그), pgjdbc 문서에서 확인한 사실이다.
- **확인**: 아래 예제를 로컬 컨테이너에서 직접 실행한 결과다. 실행 계획 출력은 이 결과를 그대로 옮기고, 긴 줄과 반복되는 청크는 일부 생략했다.
- **추론**: 위 두 가지를 근거로 추정한 내용이다. 문장에 추론이라고 밝힌다.

## 예제 테이블

사이트 50곳에 기기가 4대씩 있고, 기기마다 온도(`temp`)와 누적 전력량(`energy`) 두 지표를 10분마다 보낸다고 가정했다.
60일치를 넣으면 345만 6천 행이다.

```sql
CREATE TABLE readings (
  site_id     int              NOT NULL,
  device_id   int              NOT NULL,
  metric      text             NOT NULL,
  value       double precision NOT NULL,
  measured_at timestamptz      NOT NULL
);
SELECT create_hypertable('readings', by_range('measured_at', INTERVAL '1 day'));

INSERT INTO readings
SELECT d / 4 + 1, d, m, random() * 100,
       timestamptz '2026-08-01 00:00+00' + make_interval(mins => 10 * t)
FROM generate_series(0, 199) d,
     unnest(ARRAY['temp', 'energy']) m,
     generate_series(0, 60 * 144 - 1) t;
ANALYZE readings;
```

`create_hypertable`은 이 테이블을 `measured_at` 기준 하루 단위 청크로 나눈다.
60일치를 넣었으니 청크가 60개 생겼고, TimescaleDB가 기본으로 `measured_at DESC` 인덱스를 만들었다(확인).

```text
Indexes:
    "readings_measured_at_idx" btree (measured_at DESC)
Number of child tables: 60 (Use \d+ to list them.)
```

컨테이너는 다음처럼 띄웠고 실습이 끝난 뒤 지웠다.

```bash
docker run -d --name pgplan-study -e POSTGRES_PASSWORD=pw timescale/timescaledb:2.27.2-pg17
docker exec -it pgplan-study psql -U postgres
# 끝나면
docker rm -f pgplan-study
```

## EXPLAIN과 EXPLAIN (ANALYZE, BUFFERS)

### 무엇인가

`EXPLAIN`은 계획만 세우고 쿼리를 실행하지 않는다. 출력의 `cost`와 `rows`는 통계로 낸 추정값이다.
`EXPLAIN ANALYZE`는 쿼리를 실제로 실행하고 노드마다 실제 시간과 행 수를 덧붙인다(출처: EXPLAIN).
`BUFFERS`를 붙이면 노드마다 읽은 8KB 블록 수가 나온다.
`shared hit`은 PostgreSQL 공유 버퍼에 이미 있어 디스크 읽기를 피한 블록이고, `shared read`는 공유 버퍼에 없어 운영체제에 읽기를 요청한 블록이다(출처: EXPLAIN).

`ANALYZE`는 실제로 실행하므로 `UPDATE`나 `DELETE`에 붙이면 데이터가 바뀐다.
공식 문서는 `BEGIN; EXPLAIN ANALYZE ...; ROLLBACK;`으로 감싸라고 안내한다(출처: EXPLAIN).
PostgreSQL 18부터는 `EXPLAIN ANALYZE`가 `BUFFERS`를 기본으로 함께 출력한다(출처: PostgreSQL 18 릴리스 노트).

### 실행 계획에서 어떻게 보이나

같은 쿼리를 두 방식으로 돌렸다(확인).

```sql
EXPLAIN
SELECT device_id, metric, value, measured_at FROM readings
WHERE site_id = 7
  AND measured_at >= '2026-09-01 06:00+00' AND measured_at < '2026-09-01 09:00+00';
```

```text
Index Scan using _hyper_1_32_chunk_readings_measured_at_idx on _hyper_1_32_chunk  (cost=0.29..232.24 rows=144 width=25)
  Index Cond: ((measured_at >= '2026-09-01 06:00:00+00'::timestamp with time zone) AND (measured_at < '2026-09-01 09:00:00+00'::timestamp with time zone))
  Filter: (site_id = 7)
```

`EXPLAIN (ANALYZE, BUFFERS)`로 바꾸면 실제 값이 붙는다.

```text
Index Scan using _hyper_1_32_chunk_readings_measured_at_idx on _hyper_1_32_chunk  (cost=0.29..232.24 rows=144 width=25) (actual time=0.031..0.397 rows=144 loops=1)
  Index Cond: ((measured_at >= ...) AND (measured_at < ...))
  Filter: (site_id = 7)
  Rows Removed by Filter: 7056
  Buffers: shared hit=81
Planning Time: 0.134 ms
Execution Time: 0.410 ms
```

`Rows Removed by Filter`와 `Buffers`는 실행해야만 알 수 있어 `EXPLAIN`에는 없다.
이 쿼리는 144행을 돌려주려고 7,200행을 읽고 7,056행을 버렸다.

`loops`도 함께 본다. 한 노드가 여러 번 실행되면 `actual time`과 `rows`는 한 번 실행의 평균이고, 노드 전체 값은 `loops`를 곱해야 나온다(출처: Using EXPLAIN).
중첩 루프의 안쪽에서 `rows=1 loops=3`이면 그 노드는 모두 3행을 냈다.

### 왜 성능에 영향을 주나

`EXPLAIN`만 보면 어느 인덱스를 타는지는 알 수 있지만 얼마나 읽고 버리는지는 모른다.
느린 원인이 「인덱스를 안 탄다」가 아니라 「인덱스를 타고도 많이 읽는다」인 경우가 많아서, 성능 검토에는 `ANALYZE`와 `BUFFERS`가 붙은 계획이 필요하다.
`Buffers`의 `read`가 크면 디스크나 운영체제 캐시까지 내려간 것이고, `hit`이 크면 메모리에서 끝난 것이다.
같은 쿼리도 캐시가 데워진 뒤에는 `read`가 `hit`으로 바뀌므로, 측정값을 비교할 때는 캐시 상태를 맞춘다.

### Java와 MySQL에 빗대면

MySQL 8.0.18부터 있는 `EXPLAIN ANALYZE`가 PostgreSQL의 `EXPLAIN ANALYZE`에 해당한다.
`BUFFERS`는 쿼리 하나 동안 InnoDB 버퍼 풀에서 몇 페이지를 찾았고 몇 페이지를 디스크에서 올렸는지를 노드별로 보여 주는 것과 비슷하다.
Java로 비유하면 `EXPLAIN`은 코드 리뷰로 복잡도를 짐작하는 것이고, `EXPLAIN (ANALYZE, BUFFERS)`는 프로파일러를 붙여 실제 호출 횟수와 I/O를 재는 것이다.

> [!TIP]
> **더 읽을 글**: [MySQL EXPLAIN / EXPLAIN ANALYZE 완전 정복](../mysql/explain-plan.md).
> MySQL의 `type`, `key`, `Extra` 칼럼으로 같은 질문에 답하는 방법을 다룬다.

## Index Cond와 Filter

### 무엇인가

인덱스 스캔 노드 아래에는 조건이 두 줄로 나뉘어 나온다.

| 줄 | 하는 일 |
| --- | --- |
| `Index Cond` | 인덱스 트리에서 탐색 범위를 정하는 조건이다. 조건에 맞지 않는 항목은 아예 읽지 않는다 |
| `Filter` | 인덱스로 찾은 행을 가져온 뒤 하나씩 검사하는 조건이다. 맞지 않으면 버린다 |

공식 문서는 `Filter`를 「노드가 스캔한 행마다 조건을 검사하고 통과한 행만 내보낸다」고 설명한다.
인덱스에 없는 칼럼의 조건은 인덱스 조건으로 쓸 수 없어 가져온 행에 필터로 적용된다(출처: Using EXPLAIN).

### 실행 계획에서 어떻게 보이나

위 예제에서 인덱스는 `measured_at` 하나뿐이었다.
그래서 시간 범위는 `Index Cond`로 처리됐지만 `site_id = 7`은 `Filter`로 처리됐다.
3시간 동안 사이트 50곳의 모든 행(7,200행)을 읽고 그중 사이트 7의 144행만 남겼다(확인).

`(site_id, measured_at DESC)` 복합 인덱스를 추가하면 두 조건이 모두 `Index Cond`로 올라간다(확인).

```sql
CREATE INDEX readings_site_time_idx ON readings (site_id, measured_at DESC);
```

```text
Bitmap Heap Scan on _hyper_1_32_chunk  (cost=3.30..139.69 rows=150 width=26) (actual time=0.068..0.103 rows=144 loops=1)
  Recheck Cond: ((site_id = 7) AND (measured_at >= ...) AND (measured_at < ...))
  Heap Blocks: exact=36
  Buffers: shared hit=36 read=3
  ->  Bitmap Index Scan on _hyper_1_32_chunk_readings_site_time_idx  (cost=0.00..3.27 rows=150 width=0) (actual time=0.057..0.057 rows=144 loops=1)
        Index Cond: ((site_id = 7) AND (measured_at >= ...) AND (measured_at < ...))
        Buffers: shared read=3
```

`Rows Removed by Filter`가 사라졌고 읽은 블록이 81개에서 39개로 줄었다.
플래너는 이번에 `Bitmap Index Scan`과 `Bitmap Heap Scan` 두 단계를 골랐다.
인덱스로 행 위치를 먼저 모은 뒤 heap 블록 순서대로 읽는 방식이다(출처: Using EXPLAIN).
`Heap Blocks: exact=36`은 heap 블록 36개를 읽었다는 뜻이다.

### 왜 성능에 영향을 주나

`Filter`로 버린 행도 읽는 비용은 그대로 낸다.
위 예제처럼 버리는 비율이 98%면 일의 98%가 낭비다.
인덱스 스캔에서 `Filter`가 걸리면 버릴 행도 heap에서 가져온 뒤에 검사하므로, 다음 절의 heap 접근 비용까지 버리는 행에 함께 든다.

`Filter`가 보인다고 늘 문제는 아니다.
`Rows Removed by Filter`가 돌려준 행 수보다 훨씬 크고, 그 노드가 전체 시간의 큰 몫을 차지할 때 원인으로 본다.
필터 대상 칼럼을 인덱스 앞쪽에 넣을지, 좌측 접두사 규칙에 맞는지는 MySQL과 같은 기준으로 판단한다.

### Java와 MySQL에 빗대면

MySQL `EXPLAIN`의 `key_len`이 인덱스의 몇 칼럼까지 탐색에 썼는지 보여 준다면, PostgreSQL은 그 칼럼들을 `Index Cond`에 직접 적는다.
`Filter`는 MySQL `Extra`의 `Using where`처럼 스토리지에서 행을 받아 온 뒤 서버가 조건으로 버리는 단계에 가깝다.

Java로 비유하면 `Index Cond`는 `TreeMap.subMap(from, to)`로 필요한 구간만 꺼내는 것이고, `Filter`는 꺼낸 컬렉션을 `stream().filter()`로 다시 검사하는 것이다.
`subMap`의 범위가 넓으면 `filter`가 아무리 빨라도 순회 비용이 남는다.

## heap 접근과 커버링 인덱스

### 무엇인가

PostgreSQL 테이블은 행을 들어온 순서대로 쌓는 **heap** 구조다.
인덱스 항목에는 키와 그 행의 heap 위치(`ctid`)가 들어 있고, 인덱스 스캔은 항목마다 heap을 찾아가 나머지 칼럼을 읽는다.

**커버링 인덱스**는 쿼리에 필요한 칼럼을 인덱스에 모두 넣어 heap을 읽지 않게 만든 인덱스다.
PostgreSQL 11부터 `INCLUDE` 절로 탐색 키가 아닌 칼럼을 인덱스에 실을 수 있다(출처: Index-Only Scans and Covering Indexes).
`INCLUDE` 칼럼은 탐색에 쓰이지 않고 값만 저장된다. 표현식은 넣을 수 없고 B-Tree, GiST, SP-GiST만 지원한다(출처: 같은 문서).

PostgreSQL은 인덱스에 필요한 칼럼이 다 있어도 바로 heap을 건너뛰지 못한다.
행이 지금 트랜잭션에 보이는지(MVCC 가시성) 정보는 heap에만 있기 때문이다.
그래서 PostgreSQL은 heap 페이지마다 「이 페이지의 모든 행이 모든 트랜잭션에 보인다」는 비트를 **visibility map**에 둔다.
Index Only Scan은 이 비트가 켜진 페이지만 heap 방문을 건너뛰고, 꺼진 페이지는 heap을 찾아가 가시성을 확인한다(출처: Index-Only Scans and Covering Indexes).
비트는 `VACUUM`이 켜고, 페이지의 행이 바뀌면 꺼진다.

### 실행 계획에서 어떻게 보이나

조회 칼럼을 `INCLUDE`에 넣었다.

```sql
CREATE INDEX readings_site_time_cov_idx
  ON readings (site_id, measured_at DESC) INCLUDE (device_id, metric, value);
```

노드가 `Index Only Scan`으로 바뀌고 `Heap Fetches`가 붙는다(확인).

```text
Index Only Scan using _hyper_1_32_chunk_readings_site_time_cov_idx on _hyper_1_32_chunk  (cost=0.41..5.79 rows=141 width=25) (actual time=0.012..0.021 rows=144 loops=1)
  Index Cond: ((site_id = 7) AND (measured_at >= ...) AND (measured_at < ...))
  Heap Fetches: 0
  Buffers: shared hit=5
```

`Heap Fetches: 0`은 heap을 한 번도 읽지 않았다는 뜻이다. 블록 5개로 끝났다.

같은 시간 범위의 행을 `UPDATE`한 직후에 다시 돌리면 `Heap Fetches`가 생긴다(확인).
autovacuum은 꺼 두었다.

```text
Index Only Scan using _hyper_1_32_chunk_readings_site_time_cov_idx on _hyper_1_32_chunk (actual time=0.026..0.190 rows=144 loops=1)
  Index Cond: ((site_id = 7) AND (measured_at >= ...) AND (measured_at < ...))
  Heap Fetches: 288
  Buffers: shared hit=79
```

결과는 144행인데 `Heap Fetches`는 288이다.
`UPDATE`가 새 행 버전을 만들어 인덱스에 옛 버전과 새 버전 항목이 함께 남았고, 바뀐 페이지는 visibility map 비트가 꺼져 두 항목 모두 heap에서 가시성을 확인했기 때문이다(추론: 결과 행 수의 정확히 두 배라는 확인 결과와 공식 문서의 설명을 맞춘 해석이다).
`VACUUM readings`를 실행한 뒤에는 다시 `Heap Fetches: 0`, `shared hit=7`로 돌아왔다(확인).

### 왜 성능에 영향을 주나

heap 접근은 행마다 다른 블록을 찾아가는 임의 읽기다.
캐시가 비어 있으면 행마다 디스크 읽기가 하나씩 생길 수 있어, 인덱스 탐색보다 heap 읽기가 실행 시간의 대부분을 차지하기 쉽다.

7일 범위(8,064행)를 컨테이너를 재시작해 공유 버퍼를 비운 상태에서 두 인덱스로 비교했다(확인).
운영체제 페이지 캐시는 비우지 않았으므로 `read`의 일부는 실제 디스크가 아니라 메모리에서 왔을 수 있다.

| 인덱스 | 노드 | 읽은 블록 | 실행 시간 |
| --- | --- | --- | --- |
| `(site_id, measured_at DESC)` | Index Scan, 행마다 heap 접근 | `shared read=2044` | 25.4ms |
| 위 인덱스에 `INCLUDE (device_id, metric, value)` | Index Only Scan, `Heap Fetches: 0` | `shared read=88` | 1.2ms |

탐색 조건은 둘 다 `Index Cond`로 같다. 차이는 heap을 읽었는지뿐이다.

커버링 인덱스에도 비용이 있다.
공식 문서는 `INCLUDE` 칼럼이 테이블 데이터를 복제해 인덱스를 키우고, 테이블이 자주 바뀌어 heap 방문을 피하기 어렵다면 넣을 이유가 적다고 경고한다(출처: Index-Only Scans and Covering Indexes).
쓰기가 잦은 테이블이면 `Heap Fetches`가 0으로 유지되는지, autovacuum이 따라오는지 함께 봐야 한다.
TimescaleDB처럼 오래된 청크가 더 바뀌지 않는 시계열 데이터는 vacuum 뒤 visibility map 비트가 유지되기 쉬워 Index Only Scan과 잘 맞는다(추론).

### Java와 MySQL에 빗대면

InnoDB 보조 인덱스는 행 위치 대신 PK를 담고 있어, 인덱스로 찾은 뒤 PK로 클러스터 인덱스를 한 번 더 탐색한다.
PostgreSQL의 heap 접근이 이 두 번째 탐색에 해당하고, MySQL `Extra`의 `Using index`가 PostgreSQL의 `Index Only Scan`에 해당한다.
PostgreSQL은 여기에 visibility map 조건이 하나 더 붙는다. 같은 `Index Only Scan`이라도 `Heap Fetches`가 크면 일반 인덱스 스캔과 다를 바 없다.

Java로 비유하면 heap 접근은 `List<Long> ids`를 얻은 뒤 `repository.findById(id)`를 id마다 호출하는 N+1이고, 커버링 인덱스는 필요한 필드를 DTO 프로젝션으로 한 번에 받는 것이다.

## custom plan과 generic plan

### 무엇인가

prepared statement는 SQL을 한 번 파싱해 두고 파라미터만 바꿔 여러 번 실행한다.
이때 실행 계획을 세우는 방법이 둘이다(출처: PREPARE).

| 계획 | 세우는 방법 | 장점 | 단점 |
| --- | --- | --- | --- |
| custom plan | 실행할 때마다 그 회차의 파라미터 값을 보고 새로 세운다 | 값에 맞는 계획을 고른다 | 실행마다 계획 비용이 든다 |
| generic plan | 값과 무관한 계획을 한 번 세워 재사용한다 | 계획 비용이 없다 | 값을 모르고 세운 계획이라 비효율적일 수 있다 |

기본값인 `plan_cache_mode = auto`에서는 처음 다섯 번을 custom plan으로 실행하고 그 추정 비용의 평균을 낸다.
그다음 generic plan을 만들어 추정 비용이 평균보다 크게 높지 않으면 이후로 generic plan을 쓴다.
`plan_cache_mode`를 `force_custom_plan`이나 `force_generic_plan`으로 바꾸면 이 판단을 덮어쓸 수 있다(출처: PREPARE).
`plan_cache_mode`는 PostgreSQL 12에서 생겼다.

### 실행 계획에서 어떻게 보이나

`EXPLAIN EXECUTE`로 prepared statement의 계획을 보면 generic plan에는 `$1` 같은 파라미터 기호가 남고, custom plan에는 값이 들어간다(출처: PREPARE).

```sql
PREPARE q(int, timestamptz, timestamptz) AS
SELECT device_id, metric, value, measured_at FROM readings
WHERE site_id = $1 AND measured_at >= $2 AND measured_at < $3;

SET plan_cache_mode = force_custom_plan;
EXPLAIN (COSTS OFF) EXECUTE q(7, '2026-09-01 00:00+00', '2026-09-08 00:00+00');
SET plan_cache_mode = force_generic_plan;
EXPLAIN (COSTS OFF) EXECUTE q(7, '2026-09-01 00:00+00', '2026-09-08 00:00+00');
```

custom plan은 값 `7`이 박힌 일반 `Append` 아래에 7일치 청크 7개만 있다(확인).

```text
Append
  ->  Index Only Scan using _hyper_1_32_chunk_readings_site_time_cov_idx on _hyper_1_32_chunk
        Index Cond: (site_id = 7)
  ... 청크 33~38 생략
```

generic plan은 TimescaleDB의 `ChunkAppend` 노드가 되고 조건에 `$1`, `$2`, `$3`이 남는다(확인).

```text
Custom Scan (ChunkAppend) on readings
  Chunks excluded during startup: 53
  ->  Index Only Scan using _hyper_1_32_chunk_readings_site_time_cov_idx on _hyper_1_32_chunk
        Index Cond: ((site_id = $1) AND (measured_at >= $2) AND (measured_at < $3))
  ... 청크 33~38 생략
```

custom plan의 `Index Cond`에 시간 조건이 없는 것은 7일 범위가 청크 경계와 딱 맞아, 청크를 고른 것만으로 시간 조건이 이미 만족되기 때문이다(추론).

기본 `auto` 모드에서 같은 문장을 일곱 번 실행한 뒤 `pg_prepared_statements`를 보면 다섯 번은 custom, 두 번은 generic으로 실행됐다(확인).

```text
 name | generic_plans | custom_plans
------+---------------+--------------
 q    |             2 |            5
```

애플리케이션 로그에 남은 SQL처럼 값이 없는 문장의 generic plan을 보고 싶으면 PostgreSQL 16부터 있는 `EXPLAIN (GENERIC_PLAN)`을 쓴다.
`$1` 같은 기호를 그대로 둔 채 값에 의존하지 않는 계획을 보여 준다. `ANALYZE`와 함께 쓸 수는 없다(출처: EXPLAIN).
다음 절에서 이 출력이 왜 청크를 전부 보여 주는지 다룬다.

### 왜 성능에 영향을 주나

generic plan은 값의 분포를 모른다.
`site_id = $1`이 1행에 해당하는 값인지 전체의 절반에 해당하는 값인지 모르고 평균적인 선택도로 계획을 세운다.
값마다 최적 계획이 크게 다른 쿼리는 여섯 번째 실행부터 갑자기 느려질 수 있다.
반대로 계획 비용이 큰 쿼리는 generic plan으로 계획 시간을 아낀다.

성능 검토에서 「운영에서 실제 값으로 계획을 확인했다」는 말은 이 차이를 의식한 것이다.
리터럴을 넣은 `EXPLAIN`은 custom plan에 가깝고, 애플리케이션이 실제로 쓰는 계획은 generic plan일 수 있다.

### Java에서는 언제 generic plan이 되나

Spring의 `JdbcTemplate`, MyBatis의 `#{}`, JPA는 모두 JDBC `PreparedStatement`를 쓴다.
pgjdbc는 같은 `PreparedStatement`의 실행 횟수를 세고, `prepareThreshold`(기본 5)에 닿기 전에는 이름 없는 임시 문장으로 실행한다.
이 횟수에 닿으면 이름 있는 서버 측 prepared statement로 바꿔 `Prepare`와 `Execute`를 쓴다.
`prepareThreshold=0`이면 서버 측 prepared statement를 쓰지 않는다(출처: pgjdbc Server Prepared Statements).

PostgreSQL의 다섯 번 규칙은 이름 있는 서버 측 문장에 적용된다.
그래서 기본 설정에서는 같은 커넥션에서 같은 문장을 대략 열 번째쯤 실행할 때부터 generic plan이 쓰일 수 있다(추론: pgjdbc의 전환 시점과 PostgreSQL의 다섯 번 규칙을 합친 계산이며, 직접 측정하지 않았다).
커넥션 풀이 커넥션을 재사용하므로 운영에서는 이 횟수에 금방 닿는다.

generic plan 때문에 느려지는 쿼리가 확인되면 다음 중에서 고른다.

- 해당 세션이나 역할에 `SET plan_cache_mode = force_custom_plan`을 건다. 계획 비용은 매번 낸다.
- pgjdbc의 `prepareThreshold=0`으로 서버 측 prepared statement를 끈다. 서버 측 준비가 주는 바이너리 전송 이점도 함께 잃는다(출처: pgjdbc Server Prepared Statements).
- 쿼리를 고쳐 generic plan으로도 충분히 좋은 계획이 나오게 만든다. 다음 절의 청크 제외처럼 실행 시점에 범위를 줄이는 장치가 있으면 generic plan도 문제가 되지 않는다.

Java로 비유하면 custom plan은 호출마다 인자를 보고 분기 전략을 고르는 메서드이고, generic plan은 처음 몇 번 호출을 본 뒤 하나의 전략으로 굳혀 캐시해 두는 메서드다.
JIT 컴파일러가 처음 관찰한 타입으로 최적화했다가 다른 타입이 들어오면 손해를 보는 것과 비슷하다.

## TimescaleDB 청크와 청크 제외

### 무엇인가

TimescaleDB의 **hypertable**은 시간 칼럼을 기준으로 데이터를 여러 **청크**로 나눠 저장하는 테이블이다.
각 청크는 일정 시간 범위를 담는 실제 PostgreSQL 테이블이다.
기본 청크 간격은 7일이고 `create_hypertable`에서 바꿀 수 있다(출처: TimescaleDB 문서).
이 글의 예제는 하루로 잡았다.

쿼리의 `WHERE`에 시간 조건이 있으면 범위에 들지 않는 청크를 아예 읽지 않는다. 이것을 **청크 제외**라고 한다.
제외는 세 시점에 일어날 수 있다.

| 시점 | 언제 값을 아나 | 실행 계획 표시 |
| --- | --- | --- |
| 계획 시점 | 조건이 리터럴이라 계획을 세울 때 이미 안다 | 범위 밖 청크가 계획에 아예 없다 |
| 실행 시작 시점(startup) | generic plan의 파라미터처럼 실행을 시작할 때 안다 | `ChunkAppend`의 `Chunks excluded during startup: N` |
| 실행 중(runtime) | 중첩 루프 안쪽처럼 바깥 행마다 값이 바뀐다 | `Chunks excluded during runtime: N`, 노드별 `loops`와 `(never executed)` |

실행 시작 시점과 실행 중 제외는 TimescaleDB의 `ChunkAppend` 노드가 맡는다.
`ChunkAppend`는 실행 시작 시점에 제외한 청크를 출력 목록에서 빼고 그 개수를 `Chunks excluded during startup`으로 보여 준다(출처: TimescaleDB 소스 `src/nodes/chunk_append/exec.c`).

일반 PostgreSQL 파티션 테이블도 같은 일을 하고 이름만 다르다.
실행 계획 초기화 단계에서 제외한 파티션은 `Subplans Removed`로 개수만 남고, 실행 중 제외는 `loops`와 `(never executed)`로 드러난다(출처: Table Partitioning).

### 실행 계획에서 어떻게 보이나

리터럴로 7일 범위를 주면 계획 시점에 청크 7개만 남는다. 앞 절의 custom plan 출력이 이 경우다(확인).

generic plan을 `EXPLAIN EXECUTE`로 보면 값을 넘겼기 때문에 실행 시작 시점 제외가 일어나 7개만 보이고 `Chunks excluded during startup: 53`이 붙는다(확인).

값 없이 `EXPLAIN (GENERIC_PLAN)`으로 보면 이야기가 다르다(확인).

```sql
EXPLAIN (GENERIC_PLAN, COSTS OFF)
SELECT device_id, metric, value, measured_at FROM readings
WHERE site_id = $1 AND measured_at >= $2 AND measured_at < $3;
```

```text
Custom Scan (ChunkAppend) on readings
  Chunks excluded during startup: 0
  ->  Index Only Scan using _hyper_1_1_chunk_readings_site_time_cov_idx on _hyper_1_1_chunk
        Index Cond: ((site_id = $1) AND (measured_at >= $2) AND (measured_at < $3))
  ... 청크 60개가 모두 나온다
```

계획 시점에는 `$2`, `$3`을 모르므로 60개 청크를 모두 계획에 넣는다.
실제로 실행하면 값이 정해지는 순간 범위 밖 청크를 빼고 7개만 읽는다.
generic plan 출력에 청크가 많이 보인다고 실행 때 모두 읽는 것은 아니다.

일반 파티션 테이블에 같은 실험을 하면 `Subplans Removed`가 보인다(확인).

```text
Append (actual rows=0 loops=1)
  Subplans Removed: 8
  ->  Seq Scan on p_2 p_1 (actual rows=0 loops=1)
        Filter: ((ts >= $1) AND (ts < $2))
  ->  Seq Scan on p_3 p_2 (actual rows=0 loops=1)
        Filter: ((ts >= $1) AND (ts < $2))
```

실행 중 제외는 [다음 글](./lateral-unnest-window-query-plans.md)의 `LATERAL` 예제에서 `(never executed)`로 다시 나온다.

### 왜 성능에 영향을 주나

청크 제외가 되면 읽을 인덱스와 테이블 자체가 줄어든다.
시간 조건이 없거나 함수로 감싸 제외가 안 되면 모든 청크의 인덱스를 하나씩 탐색해야 한다.
청크가 많을수록 계획을 세우는 비용도 커진다. 다음 글의 `LATERAL` 실험에서 하한 없이 청크 31개를 후보로 넣은 계획은 계획 단계에서만 `shared hit=3944` 블록을 읽었고, 하한을 두어 청크 1개로 줄인 계획은 `shared hit=65`였다(확인).

generic plan의 출력을 읽을 때는 두 가지를 구분한다.

- 계획에 보이는 청크 수는 계획 시점에 값을 몰라 넣어 둔 후보 수다.
- 실제로 읽은 청크 수는 `EXPLAIN ANALYZE`의 `Chunks excluded during startup`과 실제 실행된 자식 노드로 확인한다.

PostgreSQL 공식 문서는 실행 계획 초기화 단계에서 제외한 파티션도 실행 시작 때 잠금은 잡는다고 적었다(출처: Table Partitioning).
파티션이 매우 많으면 제외된 파티션도 공짜가 아니라는 뜻이다.

### Java와 MySQL에 빗대면

MySQL의 `PARTITION BY RANGE`와 파티션 프루닝이 같은 개념이다.
MySQL `EXPLAIN`의 `partitions` 칼럼이 읽을 파티션 목록을 보여 주는 것처럼, PostgreSQL은 자식 노드 목록과 `Subplans Removed`로, TimescaleDB는 `Chunks excluded during startup`으로 보여 준다.
TimescaleDB는 시간 범위마다 청크를 자동으로 만들어 주므로, MySQL에서 월별 파티션을 배치로 미리 추가하던 일을 하지 않아도 된다.

Java로 비유하면 청크는 날짜별로 나눈 `Map<LocalDate, List<Reading>>`이고, 청크 제외는 조회 기간의 키만 골라 그 리스트만 순회하는 것이다.

## 이런 문장을 읽으면

DB 담당자의 성능 검토 회신에 자주 나오는 유형의 문장을 이 글의 개념에 대응시켰다.

> 「계획에 청크가 전부 나열된 것은 파라미터 값을 모르고 세운 계획이라서 그렇고, 실행할 때는 기간에 맞는 청크만 스캔됩니다.」

값을 모르고 세운 generic plan은 모든 청크를 후보로 넣는다.
실행을 시작할 때 파라미터 값이 정해지면 `ChunkAppend`가 범위 밖 청크를 뺀다.
`EXPLAIN ANALYZE`에서 `Chunks excluded during startup`과 실제 실행된 자식 노드 수를 보면 확인할 수 있다.

> 「고객 ID 조건이 인덱스 탐색에 쓰이지 못하고 Filter에서 검사되는 것이 지연 원인으로 보입니다.」

그 칼럼이 인덱스의 탐색 키가 아니어서 인덱스로 범위를 좁히지 못하고, 읽은 행을 하나씩 검사해 버리고 있다는 뜻이다.
`Rows Removed by Filter`가 결과 행보다 훨씬 크면 확실하다.
해결은 보통 그 칼럼을 앞에 둔 복합 인덱스다.

> 「실행 시간 대부분은 인덱스로 찾은 행을 테이블에서 하나씩 가져오는 데 쓰였습니다.」

인덱스 탐색은 빨랐지만 찾은 행마다 테이블 본체를 임의로 읽는 비용이 컸다는 뜻이다.
`Buffers`의 `read`가 크고 `Heap Fetches`가 많거나 일반 `Index Scan`이 행 수만큼 블록을 읽는 모습으로 나타난다.
`INCLUDE` 커버링 인덱스로 Index Only Scan을 만들고, `VACUUM`으로 visibility map을 유지하면 줄일 수 있다.

> 「이 쿼리의 실제 파라미터로 뽑은 계획은 운영 데이터를 복제한 환경에서 확인했습니다.」

리터럴을 넣은 `EXPLAIN`은 custom plan을, 애플리케이션의 prepared statement는 generic plan을 쓸 수 있다.
그래서 실제 파라미터 값과 실제 데이터 분포로 `EXPLAIN (ANALYZE, BUFFERS)`를 돌려야 판단할 수 있다.
`ANALYZE`는 쿼리를 실제로 실행하므로 운영 DB가 아니라 사본에서 돌렸다는 뜻이기도 하다.

반복 조회, 배열 펼치기, `Inner Unique`, 연속 구간과 정렬 순서에 관한 문장은 다음 글에서 다룬다.

> [!TIP]
> **더 읽을 글**: [PostgreSQL 쿼리 패턴과 실행 계획: LATERAL 최신 한 건, unnest와 Inner Unique, gaps and islands](./lateral-unnest-window-query-plans.md).
> 그룹마다 최신 한 건 읽기, 여러 배열을 표로 펼치기, 창 함수로 연속 구간 찾기를 같은 예제 테이블로 이어서 다룬다.

## 정리

| 실행 계획에서 본 것 | 뜻 | 먼저 볼 것 |
| --- | --- | --- |
| `Filter`와 큰 `Rows Removed by Filter` | 인덱스로 좁히지 못한 조건을 읽은 뒤 버린다 | 조건 칼럼을 탐색 키에 넣은 복합 인덱스 |
| 일반 `Index Scan`의 큰 `Buffers: read` | 행마다 heap을 읽는다 | `INCLUDE` 커버링 인덱스 |
| `Index Only Scan`인데 큰 `Heap Fetches` | visibility map 비트가 꺼진 페이지가 많다 | `VACUUM`과 autovacuum 설정 |
| `$1`이 남은 계획 | generic plan이다 | 실제 값으로 `EXPLAIN ANALYZE`, `plan_cache_mode` |
| 청크가 모두 보이는 `ChunkAppend` | 계획 시점에 값을 몰랐다 | `Chunks excluded during startup`과 실제 실행된 자식 수 |

## 참고 자료

- [PostgreSQL 17: EXPLAIN](https://www.postgresql.org/docs/17/sql-explain.html) — `ANALYZE`, `BUFFERS`, `GENERIC_PLAN`, `VERBOSE`
- [PostgreSQL 17: Using EXPLAIN](https://www.postgresql.org/docs/17/using-explain.html) — `Filter`, `Rows Removed by Filter`, `loops`
- [PostgreSQL 17: Index-Only Scans and Covering Indexes](https://www.postgresql.org/docs/17/indexes-index-only-scans.html) — visibility map, `INCLUDE`
- [PostgreSQL 17: PREPARE](https://www.postgresql.org/docs/17/sql-prepare.html) — custom plan과 generic plan, 다섯 번 규칙
- [PostgreSQL 17: Query Planning](https://www.postgresql.org/docs/17/runtime-config-query.html) — `plan_cache_mode`
- [PostgreSQL 17: Table Partitioning](https://www.postgresql.org/docs/17/ddl-partitioning.html) — 실행 시점 파티션 제외, `Subplans Removed`
- [PostgreSQL 18 릴리스 노트](https://www.postgresql.org/docs/18/release-18.html) — `EXPLAIN ANALYZE`의 `BUFFERS` 기본 출력
- [pgjdbc: Server Prepared Statements](https://jdbc.postgresql.org/documentation/server-prepare/) — `prepareThreshold`
- [TimescaleDB: Improve hypertable performance](https://www.tigerdata.com/docs/docs/build/performance-optimization/improve-hypertable-performance) — 기본 청크 간격
- [TimescaleDB 소스: chunk_append/exec.c](https://github.com/timescale/timescaledb/blob/2.27.2/src/nodes/chunk_append/exec.c) — `Chunks excluded during startup`, `Chunks excluded during runtime`

## 관련 문서

- [MySQL EXPLAIN / EXPLAIN ANALYZE 완전 정복](../mysql/explain-plan.md)
- [MySQL 복합 인덱스 완전 정복](../mysql/composite-index.md)
- [MySQL / InnoDB 인덱스 허브](../mysql/b-tree-index.md)
