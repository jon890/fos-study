# [초안] InnoDB Redo Log & Undo Log — WAL, Crash Recovery, Rollback 연계

InnoDB의 내구성(Durability)과 원자성(Atomicity)을 지탱하는 두 로그가 Redo Log와 Undo Log다. 애플리케이션 개발자 입장에서 두 로그가 어떤 목적을 가지고, 어떻게 협력해서 커밋/롤백/크래시 복구를 구현하는지 정리했다.

MVCC 관점의 Undo 깊은 내용(버전 체인, Read View, Purge, 격리 수준)은 별도 문서 [InnoDB MVCC 완전 분석](./innodb-mvcc.md)에서 다룬다. 이 문서는 **"로그로서의 redo/undo 역할"** 에 집중한다.

---

## 1. 두 로그의 목적 한눈에

| 구분 | Redo Log | Undo Log |
|---|---|---|
| 핵심 역할 | 커밋된 변경을 **재적용**하여 Durability 보장 | 커밋 전 변경을 **되돌림** + MVCC 이전 버전 제공 |
| 해결하는 문제 | 크래시 시 잃어버린 dirty page 변경을 복구 | 롤백 / 일관 읽기 / Crash Recovery의 Roll-Back 단계 |
| 저장 위치 | `#ib_redo0 ~ #ib_redo31` (8.0.30+) / `ib_logfile0,1` (이전) | Undo Tablespace (`undo_001`, `undo_002` …) |
| 기록 내용 | 변경 **이후** 값 (WAL) | 변경 **이전** 값 |
| 기록 시점 | 페이지 수정 직후, 커밋 시 디스크 flush | 페이지 수정 **직전** |
| 삭제 시점 | Checkpoint 완료 후 영역 재사용 | 참조하는 Read View가 사라진 후 Purge Thread가 정리 |
| 구조 | 링 버퍼 (circular) | Rollback Segment 내 Undo Log 페이지 |
| ACID 관여 | Durability | Atomicity + Isolation(MVCC) |

핵심: **Redo는 "앞으로 밀기(roll-forward)", Undo는 "뒤로 되돌리기(roll-back)"**. 트랜잭션 하나가 발생하면 두 로그가 **동시에** 기록된다. 그리고 놀랍게도 **Undo Log 자체도 Redo Log에 의해 보호받는다**(뒤에서 설명).

---

## 2. Redo Log의 목적

**Write-Ahead Log (WAL)** 패턴의 구현체다.

InnoDB는 성능을 위해 데이터 변경을 바로 데이터 파일에 쓰지 않는다. 변경 내용을 먼저 Redo Log에 순차적으로 기록하고, 나중에 Buffer Pool의 dirty page를 데이터 파일에 반영(checkpoint)한다.

크래시가 발생해서 Buffer Pool이 날아가도 Redo Log가 남아있으면 마지막 checkpoint 이후 변경사항을 재적용(redo)해서 복구할 수 있다. **트랜잭션의 Durability(지속성)를 보장하는 핵심 메커니즘이다.**

---

## 3. Undo Log의 목적

Undo Log는 변경 **이전** 상태를 보관한다. 목적은 두 가지다.

1. **Atomicity 보장** — 트랜잭션이 `ROLLBACK` 되거나 크래시로 미완료 상태로 남으면, Undo Log를 이용해 변경을 되돌려 "아예 일어나지 않은 것"으로 만든다.
2. **MVCC의 이전 버전 제공** — 다른 트랜잭션의 Read View가 오래된 스냅샷을 요구하면, 레코드의 `DB_ROLL_PTR`를 따라 Undo Log에 저장된 이전 버전을 읽어 돌려준다. 읽기가 쓰기에 블로킹되지 않는 핵심 이유다.

### Insert Undo vs Update Undo

| 구분 | Insert Undo | Update/Delete Undo |
|---|---|---|
| 생성 | `INSERT` 시 | `UPDATE`, `DELETE` 시 |
| 커밋 후 즉시 삭제 가능? | ✅ (다른 트랜잭션이 이 버전을 볼 이유가 없음) | ❌ (참조 Read View가 있으면 남아야 함) |
| 비대화 위험 | 낮음 | **높음 — 장기 트랜잭션 + UPDATE 폭풍이 전형** |

**Undo Log 비대화(Undo Bloat)는 거의 항상 Update Undo 문제다.** 장기 실행 SELECT 트랜잭션이 Read View를 붙잡고 있는 동안 다른 세션의 수많은 UPDATE가 이전 버전을 Purge하지 못한 채 쌓이면 Undo Tablespace가 폭증한다. 자세한 진단은 [innodb-mvcc.md 섹션 3](./innodb-mvcc.md#3-undo-log--버전-체인의-저장소) 참고.

---

## 4. 데이터 쓰기 흐름 — Redo와 Undo의 동시 기록

```
트랜잭션 변경 발생 (예: UPDATE products SET price=20000 WHERE id=1)
    │
    ▼
(1) Undo Log 페이지에 이전 값 기록
      └─ 이 Undo 페이지의 변경 자체도 Redo Log Buffer에 기록된다
    │
    ▼
(2) Buffer Pool의 실제 데이터 페이지 수정 (price 15000 → 20000)
      └─ 레코드의 DB_TRX_ID = 현재 트랜잭션 ID
      └─ 레코드의 DB_ROLL_PTR = 방금 만든 Undo 레코드를 가리킴
    │
    ▼
(3) 데이터 페이지 수정 내용을 Redo Log Buffer에 기록
    │
    ▼
(4) 커밋 시: Redo Log Buffer → Redo Log File (fsync)
      └─ innodb_flush_log_at_trx_commit = 1 이면 여기서 디스크까지 내려감
      └─ 이 fsync 완료 시점이 "커밋 완료" 응답의 기준
    │
    ▼
(5) (비동기) Buffer Pool의 dirty page → 데이터 파일 (.ibd) 반영
      └─ 이 시점이 Checkpoint
      └─ Checkpoint 이전의 Redo Log 영역은 재사용 가능
```

여기서 중요한 포인트:

- **Undo Log 자체의 변경도 Redo Log에 기록된다.** 크래시가 (1)과 (4) 사이 어디에서 터져도 Redo Log만 있으면 Undo Log 페이지를 복원할 수 있어야 한다. 그래야 (5)에서 설명할 Roll-Back이 가능하다.
- 커밋 성공의 기준은 **데이터 파일이 아니라 Redo Log의 디스크 flush**다. 데이터 파일 반영은 나중에 천천히 일어난다.
- 따라서 커밋 TPS는 상당 부분 **Redo Log fsync의 지연**에 의해 결정된다. NVMe vs SATA SSD 차이가 OLTP 벤치에서 체감되는 이유다.

Redo Log File은 **링 버퍼**(circular) 구조다. 가득 차면 checkpoint를 강제로 진행해서 공간을 확보한다.

---

## 5. innodb_flush_log_at_trx_commit

Redo Log를 언제 디스크에 flush할지 결정한다. 성능과 내구성의 트레이드오프 설정이다.

| 값 | flush 시점 | 크래시 시 손실 가능 범위 | 성능 |
|---|---|---|---|
| **0** | 초당 1회 (백그라운드 스레드) | 최대 1초 | 가장 빠름 |
| **1 (기본값)** | 커밋마다 디스크까지 flush | 없음 (ACID D 보장) | 가장 느림 |
| **2** | 커밋마다 OS 버퍼까지 쓰기, 초당 1회 디스크 flush | MySQL 프로세스 크래시: 없음 / OS 크래시: 최대 1초 | 중간 |

**기본값 1이 ACID를 완전히 보장한다.** 값을 낮추면 쓰기 성능은 올라가지만 데이터 손실 위험이 생긴다. 배치 처리 등 일시적으로 성능이 필요한 경우 2로 내리는 경우가 있는데, 그 트레이드오프를 명확히 인지하고 써야 한다.

> 주의: 이 옵션은 **Redo Log의 flush 전략**만 바꾼다. Undo Log는 일반 테이블스페이스처럼 취급되며, 별도 "flush 타이밍 노브"가 사용자에게 노출되지 않는다. Undo의 내구성은 Redo Log가 대신 책임진다.

---

## 6. Checkpoint와 Checkpoint Age

**Checkpoint**: Buffer Pool의 dirty page를 데이터 파일에 쓰는 작업. 이 시점까지의 Redo Log는 더 이상 필요 없어서 공간을 재사용할 수 있다.

**Checkpoint Age**: 마지막 checkpoint 이후 얼마나 많은 Redo Log가 쌓였는가.

```
Checkpoint Age = 현재 LSN - 마지막 checkpoint LSN
```

LSN(Log Sequence Number)은 Redo Log 위치를 나타내는 단조증가 숫자다.

Checkpoint Age가 Redo Log 전체 크기의 약 75~80%에 도달하면 **Async checkpoint**, 90% 이상이면 **Sharp checkpoint**가 강제 발생한다. 이 시점에 대량의 dirty page flush가 일어나 I/O 스파이크와 쿼리 지연이 생긴다.

```
Redo Log 크기가 너무 작으면:
    쓰기 많은 워크로드 → Checkpoint Age 빠르게 차오름
    → 잦은 강제 checkpoint → I/O 스파이크 반복
```

Redo Log 크기 설정:
- **8.0.30 이전**: `innodb_log_file_size` × `innodb_log_files_in_group`
- **8.0.30+**: `innodb_redo_log_capacity` 단일 파라미터로 통합, 동적 변경 가능

---

## 7. MySQL 8.0.30+ Redo Log 변화

8.0.30에서 Redo Log 관리 방식이 크게 바뀌었다.

| 항목 | 8.0.30 이전 | 8.0.30+ |
|---|---|---|
| 파일 | `ib_logfile0`, `ib_logfile1` | `#ib_redo0` ~ `#ib_redo31` (최대 32개) |
| 크기 설정 | `innodb_log_file_size` × 파일 수 | `innodb_redo_log_capacity` (단일 파라미터) |
| 크기 변경 | 재시작 필요 | 동적 변경 가능 |
| 관리 | 고정 크기 파일 2개 | 필요에 따라 파일 수 자동 조절 |

`innodb_redo_log_capacity` 기본값은 100MB. 쓰기가 많은 워크로드에서는 부족할 수 있다.

---

## 8. Undo Tablespace와 Purge 간단 정리

MySQL 8에서 Undo Log는 기본 Undo Tablespace(`undo_001`, `undo_002`)에 저장된다. 설정 관련 핵심은 세 가지다.

| 파라미터 | 의미 | 운영 포인트 |
|---|---|---|
| `innodb_undo_tablespaces` | Undo Tablespace 개수 | 8에서는 기본 2개, 동적 추가 가능 |
| `innodb_max_undo_log_size` | 단일 Undo Tablespace 자동 truncate 임계 크기 (기본 1GB) | 넘어가면 자동 축소 시도 |
| `innodb_purge_batch_size`, `innodb_purge_threads` | Purge Thread 배치 크기와 개수 | 쓰기 많은 워크로드에서 Purge 지연 시 튜닝 대상 |

### Purge가 밀리는 신호

```sql
SHOW ENGINE INNODB STATUS\G
-- TRANSACTIONS 섹션의 "History list length" 값 확인
-- 이 숫자가 지속적으로 증가하면 → 오래된 Read View가 Purge를 막고 있음

SELECT trx_id, trx_started, trx_isolation_level, trx_query
FROM information_schema.INNODB_TRX
ORDER BY trx_started ASC;
-- 가장 오래된 트랜잭션이 범인일 가능성 높음
```

Undo Bloat는 "디스크가 커진다" 문제로 끝나지 않는다. 버전 체인이 길어지면 **일관 읽기마다 체인을 더 오래 거슬러 올라가야 해서 SELECT 성능도 함께 떨어진다.** 실무에서는 이것이 "어제까지 멀쩡했던 조회가 오늘 갑자기 느려짐"의 원인이 되곤 한다.

세부 내부 동작(버전 체인, Read View 가시성 알고리즘, 격리 수준별 차이)은 [innodb-mvcc.md 섹션 3–6](./innodb-mvcc.md#3-undo-log--버전-체인의-저장소) 참고.

---

## 9. Crash Recovery — Redo와 Undo의 협력

이 섹션이 이 문서의 하이라이트다. 면접에서 "MySQL이 비정상 종료된 후 어떻게 복구되나요?"라는 질문은 대부분 이 그림을 그릴 수 있는지 본다.

### 9-1. 복구 순서

```
 MySQL 비정상 종료 후 재시작
        │
        ▼
 ┌────────────────────────────────────────┐
 │ (A) Redo Log 스캔 & 적용 (Roll-Forward) │
 │                                        │
 │  - 마지막 Checkpoint LSN 이후의         │
 │    모든 Redo Log를 순차 재생           │
 │  - 데이터 페이지에 누락된 변경사항     │
 │    + Undo Log 페이지 자체도 같이 복원  │
 │                                        │
 │  이 단계가 끝나면 Buffer Pool / 데이터 │
 │  페이지가 "크래시 직전 상태"로 복원됨. │
 │  단, 미커밋 트랜잭션의 변경도 포함됨.  │
 └────────────────────────────────────────┘
        │
        ▼
 ┌────────────────────────────────────────┐
 │ (B) 미커밋 트랜잭션 Rollback (Roll-Back)│
 │                                        │
 │  - (A)에서 복원된 Undo Log를 사용       │
 │  - 커밋 마커가 없는 트랜잭션의         │
 │    모든 변경을 Undo로 되돌림           │
 │                                        │
 │  이 단계가 끝나면 DB는 "마지막으로     │
 │  커밋된 상태"로 정확히 돌아감.         │
 └────────────────────────────────────────┘
        │
        ▼
 서비스 재개
```

### 9-2. 왜 Redo가 먼저, Undo가 나중인가

Roll-Forward 단계에서 Redo Log는 **모든 변경(커밋 여부 불문)을 그대로 재적용한다.** 이 단계만 보면 미커밋 트랜잭션의 변경까지 데이터 페이지에 반영되어 데이터가 "더러워진 상태"다.

그 다음 Roll-Back 단계에서 Undo Log로 미커밋 트랜잭션만 되돌린다. 이렇게 두 단계로 나누는 이유는 단순하다. 크래시 직전 어떤 트랜잭션이 어디까지 진행되었는지 Redo만으로는 정확히 구분할 수 없다. **"일단 다 재적용하고, Undo로 잘못된 것만 되돌린다"** 는 설계가 구현이 깔끔하고 안전하다.

### 9-3. 왜 Undo Log 자체가 Redo Log에 기록되는가

시나리오를 상상해보자.

1. 트랜잭션 T가 UPDATE 실행 → Undo Log 페이지에 이전 값 기록
2. Buffer Pool의 Undo 페이지는 수정됐지만 아직 디스크에 내려가지 않음
3. MySQL 크래시

재시작 후 Redo Log를 재생한다. 데이터 페이지의 새 값은 Redo로 복원된다. 그런데 **Undo Log 페이지가 복원되지 않으면 Roll-Back을 할 수 없다.** 미커밋 트랜잭션의 이전 값이 어디에도 없기 때문이다.

이 문제를 막기 위해 InnoDB는 **Undo Log 페이지의 모든 변경도 Redo Log에 기록한다.** Roll-Forward 단계에서 Redo가 Undo 페이지를 먼저 살려놓고, 그 다음 Roll-Back 단계에서 그 Undo를 사용해 미커밋 트랜잭션을 되돌린다. 두 로그가 서로 독립적이지 않고 **계층적으로 의존한다**는 점이 중요하다.

---

## 10. Rollback의 실제 동작

`ROLLBACK` 명령이 실행되면 InnoDB는 다음을 수행한다.

```
1. 해당 트랜잭션의 Undo Log 레코드 목록을 최신 → 과거 순으로 스캔
2. 각 Undo 레코드마다 반대 연산 수행
   - Insert Undo → 해당 레코드 DELETE
   - Update Undo → 이전 값으로 되돌리는 UPDATE
   - Delete Undo → 이전 값 그대로 INSERT (마킹 해제)
3. 모든 Undo 적용이 끝나면 트랜잭션 상태를 "Rolled Back"으로 마킹
4. 이 과정의 변경사항 자체도 Redo Log에 기록된다
   (롤백 도중 또 크래시가 나도 복구 가능하도록)
```

중요한 함의:

- **롤백은 공짜가 아니다.** 큰 트랜잭션을 롤백하면 그만큼의 역연산이 실행되고 Redo Log도 더 쌓인다. 수백만 건 UPDATE 뒤의 ROLLBACK이 커밋보다 훨씬 오래 걸리는 이유다.
- 실무에서 "트랜잭션 롤백이 10분째 안 끝난다"는 상황은 대부분 이 역연산 대량 실행이 원인이다. `information_schema.INNODB_TRX.trx_rows_modified`로 규모를 가늠할 수 있다.
- 따라서 **대용량 변경은 애초에 청크 단위로 쪼개 커밋하는 것이 안전하다.** 중간에 실패해도 롤백 비용이 작고, 재시도도 쉽다.

---

## 11. MVCC에서 Undo Log의 역할 (요약)

자세한 내용은 [innodb-mvcc.md](./innodb-mvcc.md)에 있고, 여기서는 Redo Log 문서에서 잊지 말아야 할 연결만 짚는다.

- 모든 레코드에는 숨겨진 `DB_TRX_ID`, `DB_ROLL_PTR` 컬럼이 있다.
- `UPDATE`가 일어나면 이전 값이 Undo Log 레코드가 되고, `DB_ROLL_PTR`가 그것을 가리킨다 → **버전 체인 형성**.
- 일관 읽기(Snapshot Read)는 Read View의 가시성 규칙에 따라 이 체인을 거슬러 올라가며 자신에게 보이는 버전을 찾는다.
- 따라서 **Undo Log는 단순한 "롤백용 백업"이 아니라 읽기 트랜잭션의 데이터 소스이기도 하다.** 이것이 "읽기가 쓰기를 막지 않는다"는 InnoDB 동시성의 근거다.
- Read View가 살아있는 한 해당 Undo Log는 Purge 대상이 아니다 → 장기 트랜잭션이 Undo Bloat를 만든다.

---

## 12. 애플리케이션 개발자가 주의할 부분

### 12-1. 대용량 배치 트랜잭션

하나의 트랜잭션에서 수십만 건을 처리하면 Redo Log와 Undo Log가 동시에 빠르게 차오른다.

- **Redo 쪽**: Checkpoint Age가 임계치에 달하면 강제 checkpoint로 I/O 스파이크 발생.
- **Undo 쪽**: 트랜잭션이 커밋될 때까지 Undo 레코드가 정리되지 않는다. 롤백이 필요해지면 전부 역재생해야 한다.

```java
// ❌ 트랜잭션 하나에 전체 처리
@Transactional
public void processBatch(List<Entity> entities) {
    entities.forEach(repository::save);  // 100만 건이면 Redo/Undo 모두 폭탄
}

// ✅ 청크 단위로 커밋 (Spring Batch chunk 방식)
// chunk-size = 1000~5000 정도가 일반적
```

Spring Batch의 chunk 처리가 이 문제를 자연스럽게 해결한다. chunk 단위로 커밋하면 Redo Log는 해제되고, Purge Thread가 Undo Log를 정리할 기회를 얻는다.

### 12-2. 커밋 빈도

`innodb_flush_log_at_trx_commit=1` (기본값)이면 커밋마다 디스크 fsync가 발생한다. 짧은 트랜잭션을 초당 수천 번 커밋하는 패턴은 디스크 I/O 병목이 된다.

Group Commit이 이를 어느 정도 완화해주지만, 극단적으로 빠른 커밋이 필요하면 Group Replication이나 설정 조정을 검토한다.

### 12-3. 장기 트랜잭션 = Undo Bloat

의도치 않은 장기 트랜잭션이 가장 흔한 범인이다.

- 트랜잭션 안에서 외부 API 호출
- 트랜잭션 안에서 큰 파일 읽기/쓰기
- `@Transactional(readOnly = true)`로 열어놓고 컨트롤러 전체를 감싼 경우 (MVCC Read View는 여전히 고정됨)
- 개발자가 콘솔에서 `START TRANSACTION; SELECT ...;` 실행 후 그대로 퇴근

진단 쿼리:

```sql
-- 오래 실행 중인 트랜잭션 상위 10개
SELECT trx_id, trx_started,
       TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS age_sec,
       trx_rows_modified, trx_query
FROM information_schema.INNODB_TRX
ORDER BY trx_started ASC
LIMIT 10;
```

> 자세한 Undo Bloat 재현/진단 시나리오는 [innodb-mvcc.md 섹션 11 시나리오 3](./innodb-mvcc.md#시나리오-3-undo-log-비대화-재현과-진단) 참고.

### 12-4. Rollback 비용 인지

큰 변경 후 `ROLLBACK`은 값비싼 연산이다. 애플리케이션에서 "실패하면 롤백" 패턴에 기대지 말고, **애초에 실패 가능성이 큰 검증은 트랜잭션 시작 전에 처리**하는 것이 좋다 (검증 단계 → 실제 쓰기 트랜잭션 분리).

---

## 13. Grafana로 Redo/Undo 모니터링

**prometheus/mysqld_exporter**로 MySQL 메트릭을 수집하면 Grafana에서 시각화할 수 있다.

### 13-1. Redo Log 핵심 메트릭

```promql
# Redo Log 쓰기량 (bytes/sec) — I/O 부하 파악
rate(mysql_global_status_innodb_os_log_written_total[1m])

# Redo Log Buffer 대기 횟수 — 버퍼가 너무 작으면 증가
increase(mysql_global_status_innodb_log_waits_total[5m])

# 현재 LSN vs 마지막 Checkpoint LSN — Checkpoint Age 계산
mysql_global_status_innodb_lsn_current
    - mysql_global_status_innodb_lsn_last_checkpoint
```

### 13-2. Checkpoint Age 비율

```promql
# Checkpoint Age 비율 (%) — 75% 이상이면 주의
(
    mysql_global_status_innodb_lsn_current
    - mysql_global_status_innodb_lsn_last_checkpoint
) / mysql_global_variables_innodb_redo_log_capacity * 100
```

Checkpoint Age 비율에 **75% 경고 / 85% 위험** 알림을 걸어두면 강제 checkpoint로 인한 지연을 사전에 감지할 수 있다.

### 13-3. Undo / Purge 관련 메트릭

```promql
# History List Length — 가장 중요한 Undo 건강 지표
# 수만 이상으로 지속 증가하면 장기 트랜잭션을 찾아야 함
mysql_global_status_innodb_history_list_length

# 현재 활성 트랜잭션 수
mysql_global_status_innodb_trx_active_transactions

# Purge가 처리한 Undo 레코드 수 (처리 처리량)
rate(mysql_global_status_innodb_purge_undo_log_pages[1m])
```

### 13-4. Dirty Page / Buffer Pool

```promql
# InnoDB dirty pages 수 — checkpoint 대상 페이지
mysql_global_status_innodb_buffer_pool_pages_dirty

# Buffer Pool dirty 비율 (%) — 높으면 flush 압박
mysql_global_status_innodb_buffer_pool_pages_dirty
    / mysql_global_status_innodb_buffer_pool_pages_total * 100
```

### 13-5. 흔히 보이는 이상 패턴

| 패턴 | 원인 추정 |
|---|---|
| `innodb_log_waits` 증가 | Redo Log Buffer 부족 (`innodb_log_buffer_size` 증가 검토) |
| Checkpoint Age 비율 주기적 스파이크 | Redo Log 크기 부족 또는 대용량 배치 |
| dirty pages 비율 지속 90% 이상 | Buffer Pool flush 능력 한계, I/O 병목 |
| History List Length 단조 증가 | 장기 트랜잭션 존재. Purge가 Read View에 막혀있음 |
| Undo Tablespace 용량 급증 | 장기 트랜잭션 + UPDATE 폭풍 조합 |

---

## 14. 면접 대응 프레이밍

### Q1. Redo Log와 Undo Log의 차이를 설명해주세요.

> 두 로그는 목적이 완전히 다릅니다. Redo Log는 변경 **이후** 값을 WAL 방식으로 기록해 크래시 시 커밋된 변경을 재적용(Roll-Forward)하는 용도이고, Durability를 보장합니다. Undo Log는 변경 **이전** 값을 기록해 롤백 시 복원하거나, MVCC에서 다른 트랜잭션의 Read View가 요구하는 이전 버전을 제공하는 용도입니다. Atomicity와 Isolation에 관여합니다. 한 번의 UPDATE가 발생하면 두 로그가 모두 기록되고, 심지어 **Undo Log 페이지의 변경 자체도 Redo Log에 기록**되어 크래시 후 Undo를 먼저 복원할 수 있게 됩니다.

### Q2. MySQL이 비정상 종료된 후 어떻게 일관성을 복구하나요?

> 두 단계로 복구합니다. 첫째, Roll-Forward 단계에서 마지막 Checkpoint 이후의 Redo Log를 재생해서 데이터 페이지와 Undo Log 페이지를 모두 크래시 직전 상태로 복원합니다. 이 시점에는 미커밋 트랜잭션의 변경도 함께 반영되어 있습니다. 둘째, Roll-Back 단계에서 복원된 Undo Log를 사용해 커밋 마커가 없는 트랜잭션의 변경을 되돌립니다. Redo가 먼저인 이유는 Undo Log 페이지 자체가 복원되어야 Roll-Back이 가능하기 때문입니다.

### Q3. innodb_flush_log_at_trx_commit을 0이나 2로 내리는 게 왜 위험한가요?

> 기본값 1은 커밋마다 Redo Log를 디스크까지 fsync해 ACID의 Durability를 완전히 보장합니다. 값을 2로 내리면 커밋은 OS 페이지 캐시까지만 쓰고 초당 한 번만 fsync하므로 OS 크래시 시 최대 1초 데이터가 증발할 수 있고, 0은 MySQL 프로세스 크래시에도 같은 손실이 발생합니다. 읽기-쓰기 비율이 높은 OLTP 환경에서 TPS를 올리기 위해 유혹되지만, 금융/결제처럼 손실이 치명적인 도메인에서는 반드시 1을 유지해야 합니다. 성능이 문제라면 Group Commit, 하드웨어(NVMe), Redo Log 크기 증가부터 검토하는 것이 순서입니다.

### Q4. 장기 트랜잭션이 시스템에 미치는 영향을 로그 관점에서 설명해주세요.

> Redo 관점에서는 직접적 비대화는 아니지만, 커밋이 늦어지는 동안 대용량 변경이 축적되면 롤백 시 Undo를 대량 역재생하면서 Redo Log 쪽 I/O 스파이크를 만듭니다. Undo 관점의 영향이 더 치명적입니다. 장기 트랜잭션은 Read View를 오래 유지하기 때문에 Purge Thread가 Update Undo를 정리하지 못합니다. Undo Tablespace가 비대해지고 버전 체인이 길어져 SELECT의 일관 읽기 성능까지 함께 떨어집니다. `information_schema.INNODB_TRX`와 `SHOW ENGINE INNODB STATUS`의 History List Length로 모니터링하고, 애플리케이션에서는 트랜잭션 경계를 짧게 유지하고 외부 I/O를 트랜잭션 밖으로 빼는 설계가 필수입니다.

---

## 15. 체크리스트

- [ ] Redo Log와 Undo Log의 목적과 기록 내용의 방향(이후 값 vs 이전 값)을 구분할 수 있다.
- [ ] 커밋 시 무엇이 디스크에 내려가야 "커밋 완료"인지 설명할 수 있다 (= Redo Log fsync).
- [ ] Undo Log 자체가 Redo Log로 보호받는 이유를 크래시 복구 시나리오로 설명할 수 있다.
- [ ] Crash Recovery의 Roll-Forward → Roll-Back 순서와 각 단계에서 사용되는 로그를 말할 수 있다.
- [ ] `innodb_flush_log_at_trx_commit` 0/1/2의 차이와 권장값을 설명할 수 있다.
- [ ] Checkpoint Age 비율이 높을 때 일어나는 현상과 완화 방법을 알고 있다.
- [ ] Insert Undo와 Update Undo의 생명주기 차이를 설명할 수 있다.
- [ ] History List Length가 증가하는 의미와 진단 쿼리를 쓸 수 있다.
- [ ] 대용량 배치 ROLLBACK이 오래 걸리는 이유를 Undo 역재생 관점으로 설명할 수 있다.
- [ ] MVCC의 일관 읽기가 Undo Log를 어떻게 활용하는지 연결할 수 있다.

---

## 관련 문서

- [InnoDB MVCC 완전 분석](./innodb-mvcc.md) — Undo Log 내부 구조, 버전 체인, Read View 가시성, 격리 수준, Gap/Next-Key Lock
- [InnoDB 트랜잭션과 잠금](./transaction-lock.md)
- [fsync — 리눅스 파일 동기화 시스템 콜](../../linux/fsync.md)
