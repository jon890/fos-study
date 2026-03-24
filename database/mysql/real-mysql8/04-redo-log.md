# InnoDB Redo Log

InnoDB 아키텍처에서 Redo Log가 어떻게 동작하는지, 애플리케이션 개발자 입장에서 무엇을 신경 써야 하는지 정리했다.

---

## Redo Log의 목적

**Write-Ahead Log (WAL)** 패턴의 구현체다.

InnoDB는 성능을 위해 데이터 변경을 바로 데이터 파일에 쓰지 않는다. 변경 내용을 먼저 Redo Log에 순차적으로 기록하고, 나중에 Buffer Pool의 dirty page를 데이터 파일에 반영(checkpoint)한다.

크래시가 발생해서 Buffer Pool이 날아가도 Redo Log가 남아있으면 마지막 checkpoint 이후 변경사항을 재적용(redo)해서 복구할 수 있다. **트랜잭션의 Durability(지속성)를 보장하는 핵심 메커니즘이다.**

> Undo Log와 혼동하기 쉬운데 역할이 다르다.
> - **Redo Log**: 커밋된 변경을 재적용 — crash recovery
> - **Undo Log**: 커밋 전 변경을 되돌림 — rollback, MVCC

---

## 데이터 쓰기 흐름

```
트랜잭션 변경 발생
    ↓
1. Redo Log Buffer (메모리)에 기록

    ↓ flush (커밋 시점 또는 주기적으로)

2. Redo Log File (디스크)에 기록
   └─ ib_logfile0, ib_logfile1  (8.0.30 이전)
   └─ #ib_redo0 ~ #ib_redo31   (8.0.30+)

    ↓ (비동기, 나중에)

3. Buffer Pool dirty page → 데이터 파일(.ibd)에 반영
   ← 이 시점이 Checkpoint
```

Redo Log File은 **링 버퍼(circular)** 구조다. 가득 차면 checkpoint를 강제로 진행해서 공간을 확보한다.

---

## innodb_flush_log_at_trx_commit

Redo Log를 언제 디스크에 flush할지 결정한다. 성능과 내구성의 트레이드오프 설정이다.

| 값 | flush 시점 | 크래시 시 손실 가능 범위 | 성능 |
|---|---|---|---|
| **0** | 초당 1회 (백그라운드 스레드) | 최대 1초 | 가장 빠름 |
| **1 (기본값)** | 커밋마다 디스크까지 flush | 없음 (ACID D 보장) | 가장 느림 |
| **2** | 커밋마다 OS 버퍼까지 쓰기, 초당 1회 디스크 flush | MySQL 프로세스 크래시: 없음 / OS 크래시: 최대 1초 | 중간 |

**기본값 1이 ACID를 완전히 보장한다.** 값을 낮추면 쓰기 성능은 올라가지만 데이터 손실 위험이 생긴다. 배치 처리 등 일시적으로 성능이 필요한 경우 2로 내리는 경우가 있는데, 그 트레이드오프를 명확히 인지하고 써야 한다.

---

## Checkpoint와 Checkpoint Age

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

## MySQL 8.0.30+ Redo Log 변화

8.0.30에서 Redo Log 관리 방식이 크게 바뀌었다.

| 항목 | 8.0.30 이전 | 8.0.30+ |
|---|---|---|
| 파일 | `ib_logfile0`, `ib_logfile1` | `#ib_redo0` ~ `#ib_redo31` (최대 32개) |
| 크기 설정 | `innodb_log_file_size` × 파일 수 | `innodb_redo_log_capacity` (단일 파라미터) |
| 크기 변경 | 재시작 필요 | 동적 변경 가능 |
| 관리 | 고정 크기 파일 2개 | 필요에 따라 파일 수 자동 조절 |

`innodb_redo_log_capacity` 기본값은 100MB. 쓰기가 많은 워크로드에서는 부족할 수 있다.

---

## 애플리케이션 개발자가 주의할 부분

### 대용량 배치 트랜잭션

하나의 트랜잭션에서 수십만 건을 처리하면 Redo Log가 빠르게 차오른다. Checkpoint Age가 임계치에 달하면 처리 중간에 강제 checkpoint가 발생해서 배치 속도가 들쭉날쭉해진다.

```java
// ❌ 트랜잭션 하나에 전체 처리
@Transactional
public void processBatch(List<Entity> entities) {
    entities.forEach(repository::save);  // 100만 건이면 Redo Log 폭탄
}

// ✅ 청크 단위로 커밋 (Spring Batch chunk 방식)
// chunk-size = 1000~5000 정도가 일반적
```

Spring Batch의 chunk 처리가 이 문제를 자연스럽게 해결한다. chunk 단위로 커밋하면 Redo Log가 주기적으로 해제된다.

### 커밋 빈도

`innodb_flush_log_at_trx_commit=1` (기본값)이면 커밋마다 디스크 fsync가 발생한다. 짧은 트랜잭션을 초당 수천 번 커밋하는 패턴은 디스크 I/O 병목이 된다.

Group Commit이 이를 어느 정도 완화해주지만, 극단적으로 빠른 커밋이 필요하면 Group Replication이나 설정 조정을 검토한다.

### 긴 트랜잭션 + Undo Log 연계

[MVCC 문서](./05-transaction-lock.md)에서 다뤘듯이, 긴 트랜잭션은 Undo Log 비대화를 일으킨다. Redo Log와 직접적 관계는 아니지만 InnoDB 전체 I/O에 부담을 준다.

---

## Grafana로 Redo Log 모니터링

**prometheus/mysqld_exporter**로 MySQL 메트릭을 수집하면 Grafana에서 시각화할 수 있다.

### 핵심 메트릭

```promql
# Redo Log 쓰기량 (bytes/sec) — I/O 부하 파악
rate(mysql_global_status_innodb_os_log_written_total[1m])

# Redo Log Buffer 대기 횟수 — 버퍼가 너무 작으면 증가
increase(mysql_global_status_innodb_log_waits_total[5m])

# 현재 LSN vs 마지막 Checkpoint LSN — Checkpoint Age 계산
mysql_global_status_innodb_lsn_current
    - mysql_global_status_innodb_lsn_last_checkpoint
```

### Checkpoint Age 시각화

```promql
# Checkpoint Age (bytes)
mysql_global_status_innodb_lsn_current
    - mysql_global_status_innodb_lsn_last_checkpoint

# Redo Log 총 크기 (bytes)
mysql_global_variables_innodb_redo_log_capacity
# 또는 8.0.30 이전:
mysql_global_variables_innodb_log_file_size
    * mysql_global_variables_innodb_log_files_in_group

# Checkpoint Age 비율 (%) — 75% 이상이면 주의
(
    mysql_global_status_innodb_lsn_current
    - mysql_global_status_innodb_lsn_last_checkpoint
) / mysql_global_variables_innodb_redo_log_capacity * 100
```

Checkpoint Age 비율에 **75% 경고 / 85% 위험** 알림을 걸어두면 강제 checkpoint로 인한 지연을 사전에 감지할 수 있다.

### 추가로 볼 메트릭

```promql
# InnoDB dirty pages 수 — checkpoint 대상 페이지
mysql_global_status_innodb_buffer_pool_pages_dirty

# Buffer Pool dirty 비율 (%) — 높으면 flush 압박
mysql_global_status_innodb_buffer_pool_pages_dirty
    / mysql_global_status_innodb_buffer_pool_pages_total * 100

# 초당 Redo Log 쓰기 요청 수
rate(mysql_global_status_innodb_log_write_requests_total[1m])
```

### 흔히 보이는 이상 패턴

| 패턴 | 원인 추정 |
|---|---|
| `innodb_log_waits` 증가 | Redo Log Buffer 부족 (`innodb_log_buffer_size` 증가 검토) |
| Checkpoint Age 비율 주기적 스파이크 | Redo Log 크기 부족 또는 대용량 배치 |
| dirty pages 비율 지속 90% 이상 | Buffer Pool flush 능력 한계, I/O 병목 |

---

## 관련 문서

- [InnoDB 트랜잭션과 잠금 (MVCC)](./05-transaction-lock.md)
