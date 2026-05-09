# Redis

Redis 자료구조·패턴·운영 학습 기록. 캐시, 분산 락, Pub/Sub, 세션, 랭킹 등 실전 주제를 묶었다.

## 기본

- [Redis 기본](./basic.md) — 아키텍처, 자료구조, 사용 사례 전반
- [Redis 영속성과 클러스터](./backup.md) — RDB/AOF, Cluster 구성
- [Redis 운영 가이드](./operations.md) — 성능 벤치마크, 메모리 설계, 장애 대응
- [Redis Lua 스크립트](./lua-script.md) — 원자적 복합 연산

## 캐시 패턴

- [Cache-Aside 완전 정복](./cache-aside.md) — 흐름, 정합성, 스탬피드 대응, 장애 격리
- [Redis 고급 패턴](./redis-advanced-patterns.md) — Bitmap, HyperLogLog, GEO 등 응용 자료구조 패턴

## 분산 처리

- [분산 락](./distributed-lock.md) — SET NX, Redisson, Redlock
- [Rate Limiting](./rate-limiting.md) — 고정/슬라이딩 윈도우, 토큰 버킷
- [Pub/Sub & Stream](./pub-sub.md) — 브로드캐스트 vs 신뢰성 이벤트 큐
- [Redis Cluster 운영](./redis-cluster-operations.md) — 16384 슬롯, MOVED/ASK, 노드 추가, split-brain 대응

## 응용

- [실시간 랭킹 (Leaderboard)](./leaderboard.md) — Sorted Set 기반 랭킹
- [세션 저장소](./session.md) — Spring Session, JWT vs 세션

## 면접 대비 — 커머스 응용 (초안)

- [Redis 캐시 무효화 — 커머스 메뉴/프로모션/회원 정합성 실전](./redis-cache-invalidation-commerce.md)

## 관련 문서

- [캐시 설계 전략 총정리](../../architecture/cache-strategies.md)
