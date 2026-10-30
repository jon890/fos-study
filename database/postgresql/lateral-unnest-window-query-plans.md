---
series: "PostgreSQL 실행 계획 읽기"
seriesOrder: 3
tags: [study]
---

# PostgreSQL 쿼리 패턴과 실행 계획: LATERAL 최신 한 건, unnest와 Inner Unique, gaps and islands

시계열 데이터를 다루는 PostgreSQL 쿼리에는 자주 쓰는 패턴이 셋 있다.
그룹마다 최신 한 건을 읽는 `CROSS JOIN LATERAL ... ORDER BY ... LIMIT 1`, 애플리케이션이 보낸 여러 배열을 표로 펼치는 `unnest(arr1, arr2, ...)`, 끊김 없이 이어진 구간을 찾는 창 함수 `lag()`다.
이 글은 세 패턴이 실행 계획에서 어떻게 보이는지, 비용이 어디서 생기는지, 계획에 붙는 `loops`, `(never executed)`, `Inner Unique` 같은 표시를 어떻게 읽는지 직접 돌린 예제로 정리한다.

[앞 글](./explain-index-cond-generic-plan-chunks.md)의 예제 테이블과 개념을 이어서 쓴다.
`Index Cond`와 `Filter`, heap 접근, generic plan과 TimescaleDB 청크 제외는 앞 글에서 설명했다.

> [!TIP]
> **먼저 읽을 글**: [PostgreSQL 실행 계획 기초: 쿼리가 실행되는 순서부터 스캔, 조인, 통계까지](./execution-plan-basics.md).
> 페이지와 heap, 스캔과 조인 방법, `cost`와 `rows`, 통계 같은 기초 용어를 이 시리즈의 첫 편에서 설명한다. 이 글의 출력이 낯설면 첫 편을 먼저 읽는다.

## 적용 버전과 근거의 구분

| 대상 | 버전 |
| --- | --- |
| PostgreSQL | 17.10 (`timescale/timescaledb:2.27.2-pg17` 이미지) |
| TimescaleDB | 2.27.2 |

- **출처**: PostgreSQL 17 공식 문서와 소스(`REL_17_STABLE`), TimescaleDB 소스(`2.27.2` 태그)에서 확인한 사실이다.
- **확인**: 예제를 로컬 컨테이너에서 직접 실행한 결과다. 긴 줄과 반복되는 청크는 일부 생략했다.
- **추론**: 위 두 가지를 근거로 추정한 내용이다. 문장에 추론이라고 밝힌다.

예제 테이블 `readings(site_id, device_id, metric, value, measured_at)`는 하루 단위 청크 60개로 나뉜 hypertable이다.
기기 200대가 온도(`temp`)와 누적 전력량(`energy`)을 10분마다 보낸다. 만드는 SQL은 앞 글의 「예제 테이블」 절에 있다.

## LATERAL로 그룹마다 최신 한 건 읽기

### 무엇인가

누적 전력량처럼 계속 커지는 카운터 지표는 구간 사용량을 「구간 안의 값 − 구간 시작 직전의 마지막 값」으로 계산한다.
그러려면 (기기, 지표) 쌍마다 구간 시작 전 마지막 한 건이 필요하다.

`LATERAL` 서브쿼리는 앞에 나온 `FROM` 항목의 칼럼을 참조할 수 있다.
PostgreSQL은 앞 항목의 행마다 `LATERAL` 서브쿼리를 그 행의 값으로 평가하고 결과를 그 행과 조인한다(출처: Table Expressions).
`ORDER BY measured_at DESC LIMIT 1`을 붙이면 「행마다 최신 한 건」이 된다.

```sql
CREATE INDEX readings_device_metric_time_idx
  ON readings (device_id, metric, measured_at DESC);

SELECT k.device_id, k.metric, s.value, s.measured_at
FROM (VALUES (3, 'energy'), (17, 'energy'), (42, 'energy')) AS k(device_id, metric)
CROSS JOIN LATERAL (
  SELECT r.value, r.measured_at
  FROM readings r
  WHERE r.device_id = k.device_id
    AND r.metric = k.metric
    AND r.measured_at >= timestamptz '2026-09-01 00:00+00' - interval '1 day'
    AND r.measured_at <  timestamptz '2026-09-01 00:00+00'
  ORDER BY r.measured_at DESC
  LIMIT 1
) s;
```

`measured_at >= 시작 - 1일` 하한은 「시작 직전 하루 안에서만 찾는다」는 뜻이다.
10분마다 값이 오는 지표라면 하루 안에 반드시 값이 있다고 보고 탐색 범위를 묶은 것이다.

### 실행 계획에서 어떻게 보이나

`EXPLAIN (ANALYZE, BUFFERS)` 결과다(확인).

```text
Nested Loop (actual rows=3 loops=1)
  Buffers: shared hit=7 read=5
  ->  Values Scan on "*VALUES*" (actual rows=3 loops=1)
  ->  Limit (actual rows=1 loops=3)
        ->  Custom Scan (ChunkAppend) on readings r (actual rows=1 loops=3)
              Order: r.measured_at DESC
              Chunks excluded during startup: 1
              Hypertables excluded during runtime: 0
              ->  Index Scan using _hyper_1_31_chunk_readings_device_metric_time_idx on _hyper_1_31_chunk r_1 (actual rows=1 loops=3)
                    Index Cond: ((device_id = "*VALUES*".column1) AND (metric = "*VALUES*".column2) AND (measured_at >= ('2026-09-01 00:00:00+00'::timestamp with time zone - '1 day'::interval)))
```

읽는 순서는 다음과 같다.

1. `Nested Loop`가 바깥 `Values Scan`의 3행을 하나씩 꺼낸다.
2. 행마다 안쪽 `Limit`을 한 번 실행한다. `loops=3`이 그 횟수다.
3. 안쪽의 `Index Scan`은 `(device_id, metric, measured_at DESC)` 인덱스에서 그 쌍의 가장 최근 항목 하나를 읽고 멈춘다. `rows=1`은 한 번 실행의 평균이다.
4. `Chunks excluded during startup: 1`은 계획 시점에 후보로 남은 청크 2개 중 1개를 실행 시작 때 뺐다는 뜻이다. 하한에 `interval` 연산이 들어 있어 계획 시점에는 여유를 두고 후보를 남겼다가 실행 시작 때 정확히 계산한 것으로 보인다(추론).

전체 반복 조회 횟수는 바깥 행 수, 즉 (기기, 지표) 쌍의 수와 같다.
한 번의 조회는 인덱스 몇 블록으로 끝나서 블록 12개로 3쌍을 처리했다.

### 하한이 없으면

같은 쿼리에서 하한을 빼면 `ChunkAppend`가 최근 청크부터 거꾸로 훑는다(확인).

```text
->  Custom Scan (ChunkAppend) on readings r (actual rows=1 loops=3)
      Order: r.measured_at DESC
      ->  Index Scan using _hyper_1_31_chunk_readings_device_metric_time_idx on _hyper_1_31_chunk r_1 (actual rows=1 loops=3)
      ->  Index Scan using _hyper_1_30_chunk_readings_device_metric_time_idx on _hyper_1_30_chunk r_2 (never executed)
      ->  Index Scan using _hyper_1_29_chunk_readings_device_metric_time_idx on _hyper_1_29_chunk r_3 (never executed)
      ... 청크 28~1 모두 (never executed)
```

값이 있는 기기는 첫 청크에서 한 건을 찾자마자 `Limit`이 멈추므로 나머지 청크는 `(never executed)`로 남는다.
`(never executed)`는 계획에는 있지만 한 번도 실행하지 않은 노드라는 뜻이다.

문제는 데이터가 없는 쌍이다. 존재하지 않는 기기로 돌리면 결과를 찾을 때까지 31개 청크의 인덱스를 모두 탐색한다(확인).

| 조건 | 탐색한 청크 | 실행 블록 | 계획 블록 |
| --- | --- | --- | --- |
| 하한 없음, 데이터 없는 쌍 | 31개 모두 | `shared hit=1 read=92` | `shared hit=3944` |
| 하한 1일, 데이터 없는 쌍 | 1개 | `shared hit=3` | `shared hit=65` |

### 왜 성능에 영향을 주나

`LATERAL ... LIMIT 1` 패턴의 비용은 「바깥 행 수 × 한 번 조회 비용」이다.
한 번 조회 비용을 인덱스 몇 블록으로 고정하려면 두 가지가 필요하다.

- 안쪽 조건과 정렬을 그대로 받는 인덱스. 여기서는 `(device_id, metric, measured_at DESC)`다. 정렬 칼럼이 인덱스에 없으면 쌍마다 모든 행을 읽고 정렬한다.
- 탐색 범위의 하한. 하한이 있으면 청크 제외로 후보가 줄고, 데이터가 빠진 쌍에서도 최악의 비용이 하한 범위로 묶인다.

바깥 행 수가 크면 같은 일을 `DISTINCT ON (device_id, metric) ... ORDER BY device_id, metric, measured_at DESC`로 한 번에 처리하는 편이 나을 수 있다.
그룹이 적고 그룹마다 행이 많을 때는 `LATERAL`이, 그룹이 많고 그룹마다 행이 적을 때는 한 번 훑는 방식이 유리하다(추론: 두 방식의 비용 구조에서 끌어낸 일반론이며 이 글에서 측정하지 않았다).

### Java와 MySQL에 빗대면

MySQL도 8.0.14부터 `LATERAL` 파생 테이블을 지원한다.
MySQL에서는 같은 일을 `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ... DESC) = 1`로 처리하는 경우가 많은데, 이 방식은 그룹의 모든 행에 번호를 매긴 뒤 하나만 남긴다.

Java로 비유하면 다음 코드와 같다.

```java
for (Key k : keys) {                       // Nested Loop의 바깥, loops = keys.size()
    Optional<Reading> latest =
        repository.findFirstByDeviceIdAndMetricAndMeasuredAtBetweenOrderByMeasuredAtDesc(
            k.deviceId(), k.metric(), start.minus(Duration.ofDays(1)), start);
}
```

N+1처럼 보이지만 DB 안의 루프라 네트워크 왕복이 없고, 한 번 조회가 인덱스 끝에서 바로 끝나므로 키 수가 적으면 빠르다.

## unnest로 배열을 표로 펼치기와 Inner Unique

### 무엇인가

애플리케이션에서 계산한 여러 행을 한 번에 DB로 보낼 때, 칼럼마다 배열을 하나씩 만들어 보내고 SQL에서 `unnest`로 펼치는 방법이 있다.
`unnest`에 배열을 여러 개 넘기면 배열마다 칼럼 하나씩, 같은 위치의 원소끼리 한 행으로 묶은 표가 된다.
배열 길이가 다르면 짧은 쪽을 `NULL`로 채운다. 이 형태는 `FROM` 절에서만 쓸 수 있다(출처: Array Functions and Operators).

```sql
SELECT * FROM unnest(
  ARRAY[1, 2],
  ARRAY['temp', 'energy'],
  ARRAY[date '2026-09-01', date '2026-09-01'],
  ARRAY[1.5, 2.5]
) AS u(device_id, metric, day, avg_value);
```

```text
 device_id | metric |    day     | avg_value
-----------+--------+------------+-----------
         1 | temp   | 2026-09-01 |       1.5
         2 | energy | 2026-09-01 |       2.5
```

배열 길이가 어긋나면 `NULL`이 섞인 행이 생기므로, 보내는 쪽에서 모든 배열을 같은 목록에서 만들어 길이를 맞춘다.

이 표로 일별 통계 테이블을 갱신하는 예제를 만들었다.

```sql
CREATE TABLE daily_stats (
  device_id int, metric text, day date, avg_value double precision,
  PRIMARY KEY (device_id, metric, day)
);

UPDATE daily_stats d SET avg_value = u.avg_value
FROM unnest($1::int[], $2::text[], $3::date[], $4::float8[])
     AS u(device_id, metric, day, avg_value)
WHERE d.device_id = u.device_id AND d.metric = u.metric AND d.day = u.day;
```

### 실행 계획에서 어떻게 보이나

400개 원소 배열로 돌린 계획이다. 해시 조인과 중첩 루프를 꺼서 Merge Join을 고르게 했다(확인).

```text
Update on public.daily_stats d
  ->  Merge Join
        Merge Cond: ((d.device_id = u.device_id) AND (d.metric = u.metric) AND (d.day = u.day))
        ->  Index Scan using daily_stats_pkey on public.daily_stats d
        ->  Sort
              Sort Key: u.device_id, u.metric, u.day
              ->  Function Scan on u
```

Merge Join은 양쪽을 같은 키 순서로 정렬해 지퍼처럼 맞춰 나간다.
테이블 쪽은 PK 인덱스가 이미 정렬돼 있어 `Index Scan`으로 읽고, `unnest` 쪽은 `Sort`로 정렬했다.

같은 계획을 `FORMAT YAML`로 보면 텍스트 출력에 없던 줄이 나온다(확인).

```text
- Node Type: "Merge Join"
  Join Type: "Inner"
  Inner Unique: false
  Merge Cond: "((d.device_id = u.device_id) AND (d.metric = u.metric) AND (d.day = u.day))"
```

조인 방향을 바꿔 PK 테이블이 안쪽에 오게 하면 텍스트 `VERBOSE` 출력에도 `Inner Unique: true`가 보인다(확인).

```text
Nested Loop
  Inner Unique: true
  ->  Function Scan on u
  ->  Index Scan using daily_stats_pkey on public.daily_stats d
        Index Cond: ((d.device_id = u.device_id) AND (d.metric = u.metric) AND (d.day = u.day))
```

### Inner Unique는 무엇을 뜻하나

`Inner Unique`는 조인 조건만 보고 「바깥 행 하나에 맞는 안쪽 행이 많아야 하나」임을 플래너가 증명했는지를 나타낸다.
증명되면 실행기는 첫 일치를 찾은 뒤 같은 바깥 행에 대해 안쪽을 더 찾지 않는다(출처: PostgreSQL 소스 `plannodes.h`의 `inner_unique` 주석).

플래너는 안쪽 입력이 유일하다는 것을 PK나 유일 인덱스 같은 근거로만 증명한다.

- PK 테이블이 안쪽이면 조인 조건이 PK 칼럼 전체를 덮으므로 `true`다.
- `unnest`가 안쪽이면 함수 결과에 유일 제약이 없어 증명할 수 없으므로 `false`다. 실제 데이터에 중복이 없어도 `false`로 나온다.

텍스트 형식의 `EXPLAIN`은 `VERBOSE`이고 값이 `true`일 때만 이 줄을 출력하고, JSON이나 YAML 형식은 항상 출력한다(출처: PostgreSQL 소스 `explain.c`).
그래서 `Inner Unique: false`는 주로 JSON 형식을 받아 그리는 실행 계획 시각화 도구에서 눈에 띈다.

### 왜 성능에 영향을 주나

`Inner Unique: false`는 오류 표시가 아니다.
실행기가 「첫 일치 뒤에 멈추기」 최적화를 못 쓴다는 뜻이다. Merge Join은 `inner_unique`일 때만 이 최적화(`single_match`)를 켠다(출처: PostgreSQL 소스 `nodeMergejoin.c`).
안쪽에 같은 키가 실제로 없다면 결과는 같고, 비용 차이는 측정하지 않았지만 크지 않을 것으로 본다(추론).

정말 중요한 것은 중복이 있을 때의 의미다.
`UPDATE ... FROM`에서 대상 행 하나가 `FROM` 쪽 여러 행과 조인되면 그중 한 행만 반영되고, 어느 행일지는 예측할 수 없다(출처: UPDATE).
배열 쪽에 같은 (기기, 지표, 날짜)가 두 번 들어가면 어느 값으로 갱신될지 모른다.
따라서 보내는 쪽이 키마다 한 행만 넣는다는 보장이 있어야 하고, 그 보장은 계획이 대신해 주지 않는다.

보장을 계획에도 알리고 싶으면 `unnest` 결과를 `GROUP BY device_id, metric, day`로 묶은 서브쿼리로 감싼다.
이렇게 하면 같은 `UPDATE`의 Merge Join이 `Inner Unique: true`로 바뀌었다(확인).
대신 `GroupAggregate`와 `Sort` 단계가 늘고, 중복이 있을 때 어느 값을 쓸지를 `max()` 같은 집계 함수로 직접 정해야 한다.

### Java와 MySQL에 빗대면

JDBC에서는 `connection.createArrayOf("integer", ids)`처럼 배열을 만들어 `setArray`로 바인딩한다.
행 수만큼 `addBatch()`하는 JDBC 배치와 달리 SQL 문장 하나와 파라미터 몇 개로 끝나므로, 행 수가 달라져도 문장 모양이 같아 prepared statement 재사용에도 유리하다.
MySQL에는 배열 타입이 없어 같은 일을 여러 행 `VALUES`나 `JSON_TABLE`로 한다.

`Inner Unique`는 Java의 `Map<Key, Row>`와 `Map<Key, List<Row>>` 차이로 보면 쉽다.
안쪽이 `Map<Key, Row>`라는 것이 타입으로 보장되면 `get` 한 번으로 끝나고, `List<Row>`일 수 있으면 리스트를 끝까지 봐야 한다.
`unnest` 결과는 실제로는 키마다 한 행이어도 타입이 `List`라서 플래너가 `Map`으로 취급하지 못한다.

## 창 함수로 연속 구간 찾기

> [!TIP]
> **먼저 읽을 글**: [gaps and islands: SQL 창 함수로 이어진 구간 찾기](../gaps-and-islands-window-functions.md).
> `OVER`와 프레임 기초부터 풀이 세 가지를 단계별 표로 설명한다. 이 절은 그중 `lag()` 풀이의 실행 계획을 다룬다.

### 무엇인가

**gaps and islands**는 정렬된 행에서 끊김 없이 이어진 구간(island)과 그 사이의 빈 곳(gap)을 찾는 문제다.
기기가 측정값을 보내지 않은 기간을 찾거나, 연속 사용 일수를 세는 데 쓴다.

`lag(value)`는 같은 파티션에서 현재 행보다 한 행 앞의 값을 돌려준다. 앞 행이 없으면 `NULL`이다(출처: Window Functions).
「앞 행」은 창의 `ORDER BY`가 정한다.
풀이는 세 단계다.

1. `lag()`로 직전 행과의 시간 차이를 구한다.
2. 차이가 측정 주기(10분)보다 크면 새 구간의 시작으로 표시한다.
3. 시작 표시를 누적 합계로 더하면 같은 구간의 행은 같은 번호를 갖는다. 그 번호로 묶는다.

기기 5의 온도 측정값 중 두 구간을 지워 빈 곳을 만든 뒤 실행했다.

```sql
WITH marked AS (
  SELECT measured_at,
         CASE WHEN measured_at - lag(measured_at) OVER w > interval '10 minutes'
              THEN 1 ELSE 0 END AS is_new
  FROM readings
  WHERE device_id = 5 AND metric = 'temp'
    AND measured_at >= '2026-09-01 00:00+00' AND measured_at < '2026-09-08 00:00+00'
  WINDOW w AS (ORDER BY measured_at)
), grouped AS (
  SELECT measured_at, sum(is_new) OVER (ORDER BY measured_at) AS island
  FROM marked
)
SELECT island, min(measured_at) AS started_at, max(measured_at) AS ended_at, count(*) AS readings
FROM grouped GROUP BY island ORDER BY island;
```

1단계의 중간 값은 다음과 같다(확인). 02:50 다음 행이 05:30이라 차이가 2시간 40분이고, 이 행에서 새 구간이 시작된다.

```text
      measured_at       |        prev_at         |   gap
------------------------+------------------------+----------
 2026-09-02 02:40:00+00 |                        |
 2026-09-02 02:50:00+00 | 2026-09-02 02:40:00+00 | 00:10:00
 2026-09-02 05:30:00+00 | 2026-09-02 02:50:00+00 | 02:40:00
 2026-09-02 05:40:00+00 | 2026-09-02 05:30:00+00 | 00:10:00
```

최종 결과는 구간 세 개다(확인).

```text
 island |       started_at       |        ended_at        | readings
--------+------------------------+------------------------+----------
      0 | 2026-09-01 00:00:00+00 | 2026-09-02 02:50:00+00 |      162
      1 | 2026-09-02 05:30:00+00 | 2026-09-03 11:50:00+00 |      183
      2 | 2026-09-03 12:20:00+00 | 2026-09-07 23:50:00+00 |      646
```

### 실행 계획에서 어떻게 보이나

```text
Sort (actual rows=3 loops=1)
  Sort Key: (sum((CASE WHEN ((readings.measured_at - lag(readings.measured_at) OVER (?)) > '00:10:00'::interval) THEN 1 ELSE 0 END)) OVER (?))
  ->  HashAggregate (actual rows=3 loops=1)
        ->  WindowAgg (actual rows=991 loops=1)
              ->  WindowAgg (actual rows=991 loops=1)
                    ->  Merge Append (actual rows=991 loops=1)
                          Sort Key: readings.measured_at
                          ->  Index Only Scan Backward using _hyper_1_32_chunk_readings_device_metric_time_idx on _hyper_1_32_chunk (actual rows=144 loops=1)
                                Index Cond: ((device_id = 5) AND (metric = 'temp'::text))
                                Heap Fetches: 0
                          ... 청크 33~38 생략
```

아래에서 위로 읽는다.

1. 청크마다 `(device_id, metric, measured_at DESC)` 인덱스를 거꾸로(`Backward`) 읽어 `measured_at` 오름차순 행을 얻는다.
2. `Merge Append`가 청크 7개의 정렬된 흐름을 하나로 합친다. 별도 `Sort` 노드가 없다.
3. 첫 `WindowAgg`가 `lag()`를, 두 번째 `WindowAgg`가 누적 `sum()`을 계산한다.
4. `HashAggregate`가 구간 번호로 묶고, 마지막 `Sort`가 3행을 정렬한다.

### 왜 성능에 영향을 주나

창 함수는 입력이 창의 `ORDER BY` 순서로 정렬돼 있어야 한다.
인덱스가 그 순서를 주면 위처럼 `Sort` 없이 흘려보내고, 그렇지 않으면 대상 행 전체를 정렬하는 `Sort` 노드가 `WindowAgg` 아래에 생긴다.
행이 많아 정렬이 `work_mem`을 넘으면 임시 파일을 쓴다.

정렬 순서는 성능만이 아니라 결과도 정한다.
`lag()`의 「앞 행」은 `ORDER BY`가 정하므로, 정렬 칼럼을 바꾸거나 빼면 다른 행과 비교하게 되어 구간이 달라진다.
같은 `measured_at`을 가진 행이 둘 있으면 그 둘의 순서가 정해지지 않아 실행할 때마다 결과가 달라질 수 있으므로, 이런 데이터에서는 정렬에 고유한 칼럼을 하나 더 붙인다(추론: SQL의 정렬은 `ORDER BY`가 정하지 않은 순서를 보장하지 않는다는 일반 원칙을 적용했다).
그래서 성능 검토에서 「정렬을 빼면 빨라지지 않느냐」는 제안이 나와도, 결과에 영향을 주는 정렬은 그대로 두고 인덱스로 정렬 비용을 없애는 쪽을 택한다.
`LATERAL ... ORDER BY ... LIMIT 1`의 정렬도 같다. 정렬이 「어느 한 건」을 정하므로 뺄 수 없다.

### Java와 MySQL에 빗대면

MySQL도 8.0부터 `LAG()`와 창 함수를 지원하므로 같은 SQL이 거의 그대로 동작한다.

Java로 비유하면 정렬된 리스트를 한 번 순회하며 직전 원소를 변수에 들고 있는 루프다.

```java
int island = 0;
Instant prev = null;
for (Reading r : readingsSortedByTime) {            // ORDER BY measured_at
    if (prev != null && Duration.between(prev, r.measuredAt()).compareTo(TEN_MINUTES) > 0) {
        island++;                                    // 새 구간 시작 = sum(is_new)
    }
    islands.computeIfAbsent(island, i -> new ArrayList<>()).add(r);
    prev = r.measuredAt();                           // lag(measured_at)
}
```

리스트가 정렬돼 있지 않으면 이 루프는 틀린 답을 낸다. SQL의 창 `ORDER BY`도 같은 역할이다.

## 이런 문장을 읽으면

DB 담당자의 성능 검토 회신에 자주 나오는 유형의 문장을 이 글의 개념에 대응시켰다.

> 「직전 값 조회는 키마다 한 번씩만 돌고, 조회 범위는 시작 시각 전 24시간으로 묶여 있습니다.」

`LATERAL ... LIMIT 1`의 안쪽 노드는 바깥 행 수만큼 실행된다. `loops`가 그 횟수다.
바깥 행이 키 몇 개뿐이면 반복 횟수도 몇 번뿐이다.
「24시간으로 묶여 있다」는 하한 조건이 청크 제외로 탐색 범위를 묶어, 데이터가 빠진 쌍에서도 오래된 청크까지 내려가지 않는다는 뜻이다.

> 「전달하는 배열들은 같은 원본 리스트에서 만들어 길이가 같고, 복합 키 중복이 없습니다.」

`unnest`는 길이가 다른 배열을 `NULL`로 채우므로 길이가 같아야 행이 어긋나지 않는다.
키가 겹치면 `UPDATE ... FROM`이 어느 값을 반영할지 예측할 수 없으므로, 보내는 쪽이 키마다 한 행을 보장한다는 설명이다.

> 「계획의 Inner Unique: false는 배열을 펼친 입력이라 플래너가 중복 없음을 증명하지 못해 붙은 표시이고, 문제는 아닙니다.」

플래너는 PK나 유일 인덱스가 없는 입력의 유일성을 증명하지 못한다.
`false`는 「중복이 있다」가 아니라 「중복이 없다고 증명하지 못했다」는 뜻이고, 실행기가 첫 일치 뒤에 멈추는 최적화를 못 쓸 뿐이다.

> 「ORDER BY를 지우면 결과가 바뀌므로 정렬은 유지합니다.」

창 함수의 `lag()`와 `LIMIT 1`이 고르는 행은 `ORDER BY`가 정한다.
정렬을 빼면 빨라질 수는 있어도 결과가 달라지므로, 정렬 비용은 인덱스 순서로 줄인다는 뜻이다.

## 정리

| 실행 계획에서 본 것 | 뜻 | 먼저 볼 것 |
| --- | --- | --- |
| 안쪽 노드의 큰 `loops` | 바깥 행마다 안쪽을 다시 실행한다 | 바깥 행 수와 한 번 실행 비용 |
| 많은 `(never executed)` 청크 | `LIMIT`이 일찍 끝나 나머지를 실행하지 않았다 | 데이터가 없는 키에서의 최악 비용, 탐색 하한 |
| `Inner Unique: false` | 안쪽 입력의 유일성을 증명하지 못했다 | 입력에 실제 중복이 있는지, `UPDATE ... FROM`의 의미 |
| `WindowAgg` 아래의 `Sort` | 창 순서를 인덱스가 주지 못했다 | 창 `ORDER BY`와 같은 순서의 인덱스 |

## 참고 자료

- [PostgreSQL 17: Table Expressions](https://www.postgresql.org/docs/17/queries-table-expressions.html) — `LATERAL`, 여러 인자의 `UNNEST`와 `ROWS FROM`
- [PostgreSQL 17: Array Functions and Operators](https://www.postgresql.org/docs/17/functions-array.html) — `unnest(anyarray, anyarray [, ...])`
- [PostgreSQL 17: Window Functions](https://www.postgresql.org/docs/17/functions-window.html) — `lag`
- [PostgreSQL 17: UPDATE](https://www.postgresql.org/docs/17/sql-update.html) — `FROM`으로 여러 행이 조인될 때
- [PostgreSQL 17: Table Partitioning](https://www.postgresql.org/docs/17/ddl-partitioning.html) — 실행 중 제외와 `(never executed)`
- [PostgreSQL 소스: plannodes.h](https://github.com/postgres/postgres/blob/REL_17_STABLE/src/include/nodes/plannodes.h) — `inner_unique`
- [PostgreSQL 소스: explain.c](https://github.com/postgres/postgres/blob/REL_17_STABLE/src/backend/commands/explain.c) — `Inner Unique` 출력 조건
- [PostgreSQL 소스: nodeMergejoin.c](https://github.com/postgres/postgres/blob/REL_17_STABLE/src/backend/executor/nodeMergejoin.c) — `single_match`
- [TimescaleDB 소스: chunk_append/exec.c](https://github.com/timescale/timescaledb/blob/2.27.2/src/nodes/chunk_append/exec.c)

## 관련 문서

- [PostgreSQL 실행 계획 기초: 쿼리가 실행되는 순서부터 스캔, 조인, 통계까지](./execution-plan-basics.md)
- [PostgreSQL 실행 계획 읽기: Index Cond와 Filter, heap 접근, generic plan과 TimescaleDB 청크 제외](./explain-index-cond-generic-plan-chunks.md)
- [MySQL EXPLAIN / EXPLAIN ANALYZE 완전 정복](../mysql/explain-plan.md)
