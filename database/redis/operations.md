# Redis 운영 가이드

캐시, 세션, 분산 락 등 다양한 역할로 Redis를 쓰다 보면 성능 한계, 메모리 부족, 장애 대응 같은 운영 이슈를 마주치게 된다. 이 문서는 Redis를 실무에서 운영할 때 알아야 할 것들을 정리한다.

---

## 성능 — 얼마나 낼 수 있나?

### 단일 인스턴스 기준 처리량

Redis는 싱글 스레드이므로 성능은 **단일 코어 성능**에 비례한다.

| 조건 | 처리량 (ops/sec) |
|------|----------------|
| 기본 (파이프라인 없음, 클라이언트 50개) | **80,000 ~ 200,000** |
| 파이프라인 적용 (P=16) | **1,000,000 ~ 1,800,000** |
| Unix Domain Socket (로컬) | TCP 대비 약 50% 빠름 |
| 가상화 환경 | 물리 서버 대비 10~20% 저하 |

```bash
# 실제 환경 벤치마크
redis-benchmark -q -n 100000                          # 기본
redis-benchmark -t set,get -n 1000000 -P 16 -q       # 파이프라인 포함
redis-benchmark -c 100 -n 100000 -d 256 -q            # 256바이트 페이로드, 클라이언트 100개
```

### 성능에 영향을 주는 요소

| 요소 | 영향도 | 설명 |
|------|--------|------|
| **CPU 단일 코어 성능** | 매우 높음 | 싱글 스레드라 클럭 속도가 중요 |
| **네트워크 RTT** | 높음 | 클라이언트-서버 거리가 멀수록 지연 |
| **데이터 크기** | 중간 | 10KB 이상부터 메모리 대역폭 영향 |
| **동시 연결 수** | 중간 | 30,000개 연결 시 처리량 약 50% 감소 |
| **O(N) 명령어** | 높음 | 하나가 전체 서버 블로킹 |
| **AOF fsync 정책** | 중간 | `always` 설정 시 쓰기 속도 급감 |
| **가상화** | 낮음~중간 | fork() 비용이 RDB/AOF 저장에 영향 |

### 응답 지연 목표치 (P99 기준)

| 환경 | 목표 지연 |
|------|---------|
| 같은 서버 (Unix Socket) | < 0.1ms |
| 같은 데이터센터 (내부망) | < 1ms |
| 다른 리전 | 10~50ms |

P99가 1ms를 넘기 시작하면 O(N) 명령어, Slow Query, 메모리 부족 중 하나를 의심해야 한다.

---

## 메모리 — 얼마가 적절하고, 몇 % 이상이면 위험한가?

### 메모리 사용률 임계값

| 사용률 | 상태 | 조치 |
|--------|------|------|
| ~60% | 정상 | 모니터링 유지 |
| 60~75% | 주의 | 증설 계획 수립 |
| 75% 초과 | 경고 | 즉시 증설 또는 데이터 정리 |
| 90% 초과 | 위험 | Eviction/OOM 발생 직전 |

**60~75%를 상한선으로 잡는 이유:**

1. **RDB 저장 시 fork()**: `BGSAVE` 실행 시 자식 프로세스가 메모리를 복사(Copy-on-Write)하므로 순간적으로 메모리 사용량이 2배까지 올라갈 수 있다.
2. **메모리 파편화**: 실제 데이터보다 더 많은 물리 메모리를 점유할 수 있다.
3. **트래픽 버스트**: 순간적인 데이터 급증에 대한 여유분.

### 적정 메모리 용량 계산

```
권장 메모리 = 피크 데이터 사용량 × 2 (RDB fork 고려) × 1.3 (파편화 여유)

예:
- 평상시 데이터: 4GB
- 피크 데이터: 6GB
- fork 여유: 6GB × 2 = 12GB
- 파편화 여유: 12GB × 1.3 = 15.6GB
- 권장: 16GB 이상
```

### maxmemory 설정

```bash
# redis.conf
maxmemory 12gb              # 실제 물리 메모리보다 낮게 설정 (여유분 확보)
maxmemory-policy noeviction # 메모리 초과 시 쓰기 거부 (권장)
```

**Eviction 정책 선택:**

| 정책 | 설명 | 적합 케이스 |
|------|------|-----------|
| `noeviction` | 메모리 초과 시 쓰기 에러 반환 | 데이터 유실 불허 (기본 권장) |
| `allkeys-lru` | 전체 키 중 LRU 제거 | 모든 키가 캐시 성격일 때 |
| `volatile-lru` | TTL 있는 키 중 LRU 제거 | 중요 키(TTL 없음)는 유지하고 캐시만 제거 |
| `allkeys-lfu` | 사용 빈도 기준 제거 | 특정 키에 집중 접근하는 워크로드 |
| `volatile-ttl` | 만료 임박 순으로 제거 | TTL 관리가 잘 된 경우 |

> `noeviction`이 가장 안전하다. OOM보다 에러가 낫다 — 에러는 모니터링으로 잡히지만, 조용히 데이터가 사라지는 건 더 위험하다.

### 메모리 파편화 관리

```bash
# 파편화 비율 확인
redis-cli INFO memory | grep mem_fragmentation_ratio

# 해석
# 1.0 ~ 1.3 : 정상
# 1.3 ~ 1.5 : 주의
# 1.5 이상   : 높은 파편화 → 조치 필요
```

**파편화 해소 방법:**

```bash
# Redis 4.0+: 온라인 파편화 정리
redis-cli CONFIG SET activedefrag yes
redis-cli CONFIG SET active-defrag-ignore-bytes 100mb  # 100MB 이상 파편화 시 시작
redis-cli CONFIG SET active-defrag-enabled yes

# 수동 정리 (Redis 재시작 없이)
redis-cli MEMORY PURGE
```

---

## 모니터링 — 어떤 지표를 봐야 하나

### 핵심 지표

```bash
# 전체 상태 조회
redis-cli INFO all

# 섹션별 조회
redis-cli INFO memory      # 메모리
redis-cli INFO stats       # 연결, 명령어 처리
redis-cli INFO replication # 복제 상태
redis-cli INFO persistence # RDB/AOF 상태
redis-cli INFO clients     # 연결 클라이언트
```

### 주요 모니터링 항목과 알림 기준

| 지표 | 명령어 | 정상 | 경고 기준 |
|------|--------|------|---------|
| **메모리 사용률** | `used_memory / maxmemory` | < 60% | > 75% |
| **파편화 비율** | `mem_fragmentation_ratio` | 1.0~1.3 | > 1.5 |
| **캐시 히트율** | `keyspace_hits / (hits + misses)` | > 90% | < 80% |
| **연결 수** | `connected_clients` | 서비스마다 다름 | 최대치 80% 이상 |
| **차단된 클라이언트** | `blocked_clients` | 0 | > 0 지속 시 |
| **거부된 연결** | `rejected_connections` | 0 | > 0 |
| **Evicted 키** | `evicted_keys` | 0 | > 0 (noeviction이면 발생 안 함) |
| **만료된 키** | `expired_keys` | — | 급격히 증가 시 |
| **복제 지연** | `master_repl_offset - slave_repl_offset` | < 100KB | > 1MB |

### Slow Log (느린 쿼리 로그)

```bash
# 10ms 이상 걸린 명령어 기록 (기본: 10000μs = 10ms)
redis-cli CONFIG SET slowlog-log-slower-than 10000
redis-cli CONFIG SET slowlog-max-len 128

# 슬로우 로그 조회
redis-cli SLOWLOG GET 10     # 최근 10개
redis-cli SLOWLOG LEN        # 전체 개수
redis-cli SLOWLOG RESET      # 초기화
```

출력 형식:
```
1) 1) (integer) 14           # 순번
   2) (integer) 1711500000   # 실행 시각 (unix timestamp)
   3) (integer) 15000        # 소요 시간 (μs) → 15ms
   4) 1) "KEYS"              # 실행 명령어
      2) "*"
```

### 실시간 모니터링 (주의: 운영 환경에서 짧게만)

```bash
# 실시간 명령어 스트리밍 (성능 영향 큼 → 운영 환경 사용 주의)
redis-cli MONITOR

# 1초 간격 통계 (이쪽이 안전)
redis-cli --stat

# 메모리 사용 분석
redis-cli MEMORY USAGE key:name          # 특정 키 메모리 사용량
redis-cli MEMORY DOCTOR                  # 메모리 상태 진단
```

---

## 장애 유형별 대응

### 1. 메모리 부족 (OOM / Eviction)

**증상:**
- `evicted_keys` 증가
- `OOM command not allowed` 에러 (noeviction 정책 시)
- 응답 속도 급격히 저하

**즉각 대응:**
```bash
# 1. 메모리 사용량 확인
redis-cli INFO memory

# 2. 큰 키 찾기
redis-cli --bigkeys
redis-cli MEMORY USAGE {key}

# 3. 불필요한 키 즉시 삭제
redis-cli DEL {unnecessary_key}

# 4. TTL 없는 키에 만료 시간 부여
redis-cli OBJECT ENCODING {key}
redis-cli TTL {key}                  # -1이면 TTL 없음
redis-cli EXPIRE {key} 3600
```

**근본 해결:**
- maxmemory 증설 (서버 메모리 업그레이드)
- 데이터 분산 (Redis Cluster)
- 불필요한 데이터 캐싱 정책 재검토

### 2. 서버 다운 / 재시작

**RDB만 사용 중:**
```bash
# 마지막 스냅샷 이후 데이터 유실
# 재시작하면 .rdb 파일에서 자동 복구
redis-server /etc/redis/redis.conf

# 복구 확인
redis-cli INFO persistence
# rdb_last_bgsave_status: ok
# rdb_last_bgsave_time_sec: 3
```

**AOF 사용 중:**
```bash
# AOF 파일 손상 여부 확인
redis-check-aof --fix appendonly.aof

# 복구 (appendonly.aof 재실행)
redis-server /etc/redis/redis.conf
# aof_enabled: 1
# aof_rewrite_in_progress: 0
```

**복구 우선순위:** AOF > RDB (AOF가 더 최신 데이터)

### 3. 복제 지연 (Replica Lag)

**증상:**
- `master_repl_offset`와 `slave_repl_offset` 차이가 큼
- Replica에서 구 데이터가 읽힘

```bash
# 복제 상태 확인
redis-cli INFO replication

# 출력 예시
# role:master
# connected_slaves:2
# slave0:ip=10.0.0.2,port=6379,state=online,offset=12345678,lag=0
# slave1:ip=10.0.0.3,port=6379,state=online,offset=12300000,lag=2  ← lag 주의
```

**원인별 대응:**
- 네트워크 대역폭 부족 → `repl-backlog-size` 증가
- Master 부하 과다 → Replica에 읽기 트래픽 분산
- Replica 서버 성능 부족 → 서버 스펙 업그레이드

### 4. Master 장애 (Failover)

**Sentinel 환경:**
```bash
# Sentinel이 자동으로 Replica → Master 승격
# 상태 확인
redis-cli -p 26379 SENTINEL masters
redis-cli -p 26379 SENTINEL slaves mymaster

# 수동 Failover (Sentinel에 명령)
redis-cli -p 26379 SENTINEL failover mymaster
```

**Cluster 환경:**
```bash
# 클러스터 상태 확인
redis-cli CLUSTER INFO
redis-cli CLUSTER NODES

# 장애 노드 확인
# cluster_state: fail → 클러스터 불안정
# cluster_state: ok   → 정상

# 수동 Failover (Replica에서 실행)
redis-cli CLUSTER FAILOVER
```

**Sentinel/Cluster 없는 단독 장애:**
```bash
# 1. Replica를 새 Master로 승격
redis-cli -h replica-host REPLICAOF NO ONE

# 2. 애플리케이션의 Redis 연결 주소 변경
# 3. 장애 Master 복구 후 새 Replica로 편입
redis-cli -h old-master REPLICAOF new-master-host 6379
```

### 5. Cache Stampede (캐시 폭풍)

**증상:**
- TTL 만료 순간 DB CPU/응답 시간 급증
- Redis 히트율 급락

**즉각 대응:**
```bash
# 해당 키 즉시 Pre-warming
redis-cli SET hot:key {value} EX 3600

# 또는 TTL 연장
redis-cli EXPIREAT hot:key {future_timestamp}
```

**근본 해결:** 확률적 조기 갱신(Probabilistic Early Expiration) 또는 Lock 기반 갱신 → [캐시 설계 전략](../../architecture/cache-strategies.md#3-cache-stampede-캐시-폭풍)

---

## 운영 금지 명령어

다음 명령어는 운영 환경에서 사용하면 전체 서버가 블로킹될 수 있다.

| 명령어 | 문제 | 대안 |
|--------|------|------|
| `KEYS *` | O(N) 전체 스캔 → 서버 블로킹 | `SCAN 0 COUNT 100` (커서 기반 반복) |
| `FLUSHALL` | 모든 데이터 즉시 삭제 | `FLUSHALL ASYNC` (Redis 4.0+, 백그라운드) |
| `FLUSHDB` | 현재 DB 즉시 삭제 | `FLUSHDB ASYNC` |
| `DEBUG SLEEP` | 의도적 블로킹 | 사용 금지 |
| `SMEMBERS` (대형 Set) | O(N) | `SSCAN` |
| `HGETALL` (필드 수천 개) | O(N) | `HSCAN` 또는 필요 필드만 `HMGET` |
| `LRANGE 0 -1` (긴 List) | O(N) | 페이지네이션 |
| `MONITOR` | 성능 50% 저하 | `SLOWLOG GET` 또는 짧게만 사용 |

---

## 하드웨어 권장 사항

### CPU

- **코어 수보다 클럭 속도**가 중요 (싱글 스레드 특성)
- Redis 인스턴스 하나당 코어 1개 사용
- 여러 인스턴스를 실행하는 경우 코어 수 확보
- Intel > AMD Opteron (Redis 공식 벤치마크 기준)

### 메모리

```
권장 구성:
- Redis 데이터: 최대 maxmemory의 60%까지 사용 목표
- OS 및 기타: 여유분 (최소 2~4GB)
- fork() 여유: maxmemory만큼 추가 확보 (RDB/AOF 사용 시)

예시: 32GB 서버
- maxmemory: 24GB (OS용 8GB 남김)
- 피크 데이터 목표: 14~15GB (60%)
- fork() 발생 시 최대: 24 + 15 = 39GB → 서버 물리 메모리 초과!
→ RDB/AOF 사용 시 서버 메모리를 maxmemory의 2배 이상 권장
```

### 스토리지 (RDB/AOF 저장 시)

- **로컬 SSD** 필수 (NAS/NFS 사용 시 I/O 지연으로 성능 급락)
- AOF 파일 크기가 maxmemory를 초과할 수 있음 → 별도 볼륨 권장
- `dir` 설정으로 데이터 디렉터리 분리

```bash
# redis.conf
dir /data/redis               # RDB/AOF 저장 경로 (SSD 마운트)
dbfilename dump.rdb
appendfilename appendonly.aof
```

### 네트워크

- 대용량 데이터(4KB × 100,000 ops/s)는 **3.2 Gbit/s** 대역폭 사용
- 10Gbps NIC 권장 (고부하 환경)
- 동일 데이터센터 내 Redis-애플리케이션 배치 (네트워크 RTT 최소화)

---

## 설정 체크리스트

```bash
# redis.conf 핵심 설정

# 메모리
maxmemory 12gb
maxmemory-policy noeviction

# 영속성 (캐시 전용이면 비활성화)
save ""                              # RDB 비활성화 (캐시 전용)
appendonly no                        # AOF 비활성화 (캐시 전용)

# 또는 영속성 필요 시
save 900 1
save 300 10
appendonly yes
appendfsync everysec                 # 성능과 안전의 균형

# 보안
requirepass {strong_password}
bind 127.0.0.1 10.0.0.1             # 내부망 IP만 바인딩
protected-mode yes

# 슬로우 로그
slowlog-log-slower-than 10000       # 10ms 이상 기록
slowlog-max-len 128

# 파편화 자동 정리 (Redis 4.0+)
activedefrag yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10    # 10% 파편화부터 시작

# 클라이언트 연결
maxclients 10000
tcp-keepalive 300

# 커널 설정 (OS 레벨)
# vm.overcommit_memory = 1          # fork() 메모리 할당 보장
# net.core.somaxconn = 511          # 연결 큐 크기
# transparent_hugepage = madvise    # THP 비활성화 (지연 방지)
```

---

## 관련 문서

- [Redis 기본](./basic.md) — 아키텍처, 자료구조, 사용 사례
- [Redis 영속성과 클러스터](./backup.md) — RDB/AOF 상세 설정, Cluster 구성
- [캐시 설계 전략](../../architecture/cache-strategies.md) — Cache Stampede 해결책 포함
