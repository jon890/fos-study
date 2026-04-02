# Redis 실시간 랭킹 (Leaderboard)

실시간 랭킹은 Redis의 **Sorted Set**(ZSet)이 가장 빛을 발하는 사용 사례다. RDB에서 `ORDER BY score DESC` 쿼리를 매번 날리는 것과 달리, Sorted Set은 score 기반 정렬 상태를 항상 유지하므로 **순위 조회가 O(log N)**이다.

---

## 왜 Sorted Set인가?

| 방법 | 삽입 | 순위 조회 | 범위 조회 |
|------|------|---------|---------|
| RDB `ORDER BY` | O(1) | O(N log N) | O(N log N) |
| Redis Sorted Set | O(log N) | O(log N) | O(log N + K) |

내부적으로 **Skip List + Hash Table** 이중 구조로 구현되어 있다. Hash Table은 멤버 → score를 O(1)로 찾고, Skip List는 score 기준 정렬과 범위 탐색을 O(log N)으로 처리한다.

---

## 핵심 명령어

```bash
# 점수 추가 / 갱신
ZADD leaderboard 1500 "user:1001"
ZADD leaderboard NX 1500 "user:1001"   # 없을 때만 추가
ZADD leaderboard XX 1500 "user:1001"   # 있을 때만 갱신
ZINCRBY leaderboard 100 "user:1001"    # 점수 증가 (원자적)

# 순위 조회 (0-based index)
ZRANK leaderboard "user:1001"          # 오름차순 순위 (낮은 점수 = 0위)
ZREVRANK leaderboard "user:1001"       # 내림차순 순위 (높은 점수 = 0위) ← 랭킹에 사용

# 범위 조회
ZREVRANGE leaderboard 0 9 WITHSCORES  # 상위 10명 + 점수
ZRANGE leaderboard 0 9 WITHSCORES     # 하위 10명 + 점수
ZRANGEBYSCORE leaderboard 1000 2000   # 점수 1000~2000 사이

# 점수 조회
ZSCORE leaderboard "user:1001"

# 삭제
ZREM leaderboard "user:1001"

# 전체 크기
ZCARD leaderboard
```

---

## 구현 패턴

### 1. 단순 글로벌 랭킹

```bash
# 게임 점수 기록
ZINCRBY game:leaderboard 500 "user:1001"

# 상위 10명 조회
ZREVRANGE game:leaderboard 0 9 WITHSCORES

# 내 순위 조회 (1-based로 변환하려면 +1)
ZREVRANK game:leaderboard "user:1001"

# 내 주변 순위 (내 순위 ± 2명)
# 내 순위가 5라면
ZREVRANGE game:leaderboard 3 7 WITHSCORES
```

### 2. 기간별 랭킹 (일간/주간/월간)

날짜를 키에 포함시켜 자연스럽게 기간을 분리한다.

```bash
# 일간 랭킹
ZINCRBY leaderboard:daily:20260327 100 "user:1001"
EXPIRE leaderboard:daily:20260327 86400    # 1일 후 자동 삭제

# 주간 랭킹 (주차 번호 활용)
ZINCRBY leaderboard:weekly:2026-W13 100 "user:1001"
EXPIRE leaderboard:weekly:2026-W13 604800  # 7일 후 자동 삭제

# 월간 랭킹
ZINCRBY leaderboard:monthly:2026-03 100 "user:1001"
```

**기간별 랭킹 조회 흐름:**
```
요청: 이번 주 TOP 10 조회
   ↓
ZREVRANGE leaderboard:weekly:2026-W13 0 9 WITHSCORES
   ↓
결과 캐시 (인기 랭킹은 1~5초 TTL로 별도 캐싱)
```

### 3. 카테고리별 랭킹

```bash
# 장르별 게임 랭킹
ZINCRBY leaderboard:genre:action 200 "user:1001"
ZINCRBY leaderboard:genre:rpg   150 "user:1001"

# 지역별 랭킹
ZINCRBY leaderboard:region:seoul 300 "user:1001"
```

### 4. 동점자 처리

Sorted Set은 score가 같으면 **멤버 이름의 사전순**으로 정렬한다. 동점자를 먼저 달성한 순으로 처리하려면 score에 타임스탬프를 소수점으로 인코딩하는 방법을 쓴다.

```python
# score = 실제점수 + (1 - 타임스탬프 정규화값)
# 같은 점수면 먼저 달성한 사람이 앞에 오도록
score = actual_score + (1 - timestamp / MAX_TIMESTAMP)
```

또는 score를 복합값으로 인코딩한다.
```bash
# 점수 * 10^10 + (MAX_TIMESTAMP - 현재 타임스탬프)
# 점수가 같으면 먼저 달성한 사람이 더 큰 값
ZADD leaderboard 15000000000000 "user:1001"
```

---

## 인기 상품 / 검색어 랭킹

e커머스에서 자주 쓰는 패턴이다.

```bash
# 상품 조회 시마다 score 증가
ZINCRBY popular:products:hourly 1 "product:9901"

# 검색어 입력 시마다 score 증가
ZINCRBY search:keywords:daily 1 "아이폰케이스"

# 실시간 인기 검색어 TOP 10
ZREVRANGE search:keywords:daily 0 9

# 오래된 데이터 정리 (score가 낮은 것 제거)
ZREMRANGEBYRANK popular:products:hourly 0 -101  # 상위 100개만 유지
```

---

## 주의사항

### 키 개수 관리

기간별 랭킹을 날짜마다 만들면 키가 쌓인다. TTL을 반드시 설정하거나, 배치 작업으로 오래된 키를 정리해야 한다.

```bash
# TTL 확인
TTL leaderboard:daily:20260101   # -1이면 만료 없음 → 위험
```

### 대규모 Sorted Set

멤버가 수백만 개가 넘으면 `ZRANGE`, `ZREVRANGE` 등의 범위 조회가 느려진다. 상위 N개만 유지하는 정책을 적용하는 것이 좋다.

```bash
# 삽입 후 상위 1000개만 유지
ZINCRBY leaderboard 100 "user:1001"
ZREMRANGEBYRANK leaderboard 0 -1001   # 1001번째 이하 모두 삭제
```

### ZRANGEBYSCORE vs ZRANGE (Redis 6.2+)

Redis 6.2부터 `ZRANGE`에 `REV`, `BYSCORE`, `LIMIT` 옵션이 추가되어 `ZRANGEBYSCORE`, `ZREVRANGEBYSCORE`를 대체한다.

```bash
# Redis 6.2+
ZRANGE leaderboard 0 9 REV WITHSCORES          # 상위 10명
ZRANGE leaderboard "(1000" "+inf" BYSCORE REV  # 1000점 초과 내림차순
```

---

## 관련 문서

- [Redis 기본](./basic.md) — Sorted Set 명령어 전체 목록
- [캐시 설계 전략](../../architecture/cache-strategies.md) — 랭킹 결과 캐싱 전략
