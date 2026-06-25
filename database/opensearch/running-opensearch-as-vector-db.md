# OpenSearch를 벡터 DB로 굴리며 알게 된 것 — 벡터는 heap이 아니라 native에 산다

벡터 검색용 OpenSearch 클러스터의 모니터링 대시보드를 만들다가 이상한 걸 봤다.
JVM heap 사용량이 12%밖에 안 됐다.
"벡터 DB인데 메모리를 이것밖에 안 쓴다고?" 싶어 파봤더니, 정작 벡터는 heap이 아니라 **off-heap native memory**에 살고 있었다.

이 글의 결론을 먼저 적으면 이렇다.

- OpenSearch의 벡터(HNSW 그래프)는 JVM heap이 아니라 **native memory**에 로드된다. 그래서 heap 사용량만 보는 모니터링은 정작 중요한 벡터 메모리를 못 본다.
- 메모리는 `circuit_breaker`로 관리되는데, 이게 한도를 넘으면 검색이 느려진다. heap의 GC가 아니라 별도 장치다.
- 벡터 DB 운영에서 진짜 봐야 할 메모리 지표는 heap이 아니라 **k-NN graph memory와 circuit breaker 사용률**이다.

벡터 검색 자체의 사용법은 [OpenSearch를 VectorStore로 활용하기](../../AI/RAG/opensearch-vector.md)에 정리해뒀고, 이 글은 **운영하면서 메모리·샤드가 어떻게 움직이는지**에 집중한다.

## 발단 — heap이 톱니처럼 오르내리는데 12%밖에 안 쓴다

대시보드의 Memory Usage 패널(JVM heap)은 두 가지가 눈에 띄었다.

1. 값이 계단/톱니 모양으로 오르내린다.
2. 그런데 전체의 12%밖에 안 쓴다(32GB 중 약 4GB).

톱니부터. 이건 **가비지 컬렉션**(GC)의 정상 패턴이다. JVM은 검색·인덱싱을 처리하며 임시 객체를 heap에 쌓고(상승), GC가 돌면 안 쓰는 객체를 한꺼번에 회수한다(급락). 이 상승-급락이 반복되면 톱니가 된다. 오히려 회수가 잘 되고 있다는 신호다.

문제는 두 번째였다. 벡터 검색은 HNSW 그래프를 메모리에 올려두고 탐색하는 방식이라, 메모리에 벡터가 상주해야 한다. 그런데 heap이 12%라니. 벡터는 어디 있는 걸까.

## 핵심 — HNSW 그래프는 JVM 밖(native)에 로드된다

답은 간단했다. **벡터 그래프는 JVM heap이 아니라 off-heap native memory에 있다.**

OpenSearch의 k-NN은 HNSW 그래프를 `.hnsw` 파일로 만들어 두고, 검색 시 이걸 native memory에 로드해 캐싱한다. 이 로딩은 JVM 밖에서 일어난다. 그래서 heap을 보는 패널에는 안 잡힌다.

왜 굳이 밖에 둘까. 두 가지 이유가 겹친다.

**1. 구현 자체가 네이티브**(C++) **라이브러리다.**
k-NN의 HNSW는 OpenSearch가 Java로 짠 게 아니라 Faiss·nmslib 같은 C/C++ 라이브러리로 동작하고, JNI로 호출된다. 이 라이브러리는 C++ 자료구조라 메모리를 C++ 쪽에서 할당한다. JVM heap은 Java 객체 전용이라 C++ 그래프가 거기 못 들어간다.

**2. heap에 두면 GC가 발목을 잡는다.**
벡터 그래프는 수 GB에서 수십 GB이고 오래 살아있는 데이터다. 이런 큰 덩어리가 heap에 있으면 GC가 매번 그 영역을 스캔·관리해야 해서 GC 멈춤(stop-the-world)이 길어진다. native에 두면 GC가 아예 건드리지 않는다. 자주 안 바뀌고 큰 데이터는 off-heap에 두는 게 JVM 시스템의 정석이다.

즉 native에 있는 건 "C++ 구현이라 어쩔 수 없이"이면서 동시에 "GC를 피하려고 일부러"이기도 하다. 둘 다 같은 방향을 가리킨다.

## circuit breaker — 이름은 익숙한데 MSA의 그것과 다르다

heap은 GC가 알아서 비워주지만, native 벡터 메모리는 GC가 없다. 그래서 circuit breaker라는 별도 장치로 한도를 관리한다.

그런데 이 이름을 처음 보고 MSA의 circuit breaker(Hystrix, Resilience4j)를 떠올렸다면 잠깐 멈추는 게 좋다. 이름만 같고 하는 일이 다르다.

| | MSA circuit breaker | OpenSearch circuit breaker |
| --- | --- | --- |
| 보호 대상 | 장애 전파 — 하류 서비스가 죽으면 상류도 줄줄이 | 메모리 — 요청이 heap·native를 터뜨려 노드 OOM |
| 트리거 | 호출 실패율·타임아웃 | 메모리 사용량이 한도 초과 |
| 동작 | 회로를 열어 한동안 호출 자체를 끊음 | 회로 상태 없이, 요청마다 메모리를 추정해 넘으면 그 요청만 거부 |

MSA가 "고장난 기계로 가는 전원을 한동안 내려두는 차단기"라면, OpenSearch는 "지금 이 작업이 과부하면 그 작업만 안 받는 차단기"에 가깝다. 그래서 OpenSearch에선 "회로가 열렸다"는 상태보다 사용률(estimated / limit)이 한도에 얼마나 가까운지를 본다. 100%에 닿으면 그때 요청이 거부된다.

그리고 OpenSearch엔 circuit breaker가 두 종류 있다.

- JVM circuit breaker — heap 보호. parent(전체 합산), fielddata(정렬·집계용 캐시), request(요청별 집계 구조) 등으로 나뉜다.
- k-NN circuit breaker — 아래에서 볼 native 벡터 메모리 보호.

아래는 k-NN circuit breaker 기준 설명이다.

`circuit_breaker_limit`은 기본 50%다. OpenSearch는 보통 시스템 RAM의 절반을 heap에 쓰고, k-NN은 나머지 절반의 50%까지 그래프에 쓴다. 그래서 RAM 32GiB짜리 인스턴스는 대략 그래프 8GiB까지 담을 수 있다는 계산이 나온다.

이 한도를 넘으면 어떻게 되나. 새 그래프를 로드할 때 기존 그래프를 메모리에서 밀어낸다(evict). 밀려난 그래프는 다음 검색 때 디스크에서 다시 로드되니 **검색 지연**이 생긴다. 즉 circuit breaker 사용률은 "벡터 검색이 느려지기 직전인가"를 보는 지표다.

한 가지 함정도 있다. 내부적으로 쓰는 Guava 캐시는 evict해도 메모리를 즉시 반환하지 않아, native 사용량이 한도를 잠깐 넘기는 경우가 보고돼 있다. 그래서 사용률이 한도(50%) 근처면 이미 여유가 빠듯하다고 봐야 한다.

## 실측 — heap 4GB 뒤에 벡터 13GB가 숨어 있었다

내가 본 운영 클러스터(데이터 노드 12대)의 한 노드를 실측하니 이렇게 갈렸다.

| 메모리 | 크기 | 대시보드에 보이나 |
| --- | --- | --- |
| JVM heap | 약 4GB / 32GB (12%) | Memory Usage 패널에 보임 |
| k-NN 그래프 (HNSW 벡터) | 약 13GB (native) | 안 보임 |
| 호스트 RAM | 62GB (heap + 벡터 native + 파일 캐시) | — |

`_plugins/_knn/stats`로 확인한 `graph_memory_usage`가 약 13GB였고, `graph_memory_usage_percentage`는 **51%**였다. circuit breaker 한도(50%)를 이미 살짝 넘긴 상태였다. heap 패널만 보면 "메모리 12%, 여유 만만"인데, 정작 벡터 메모리는 한도에 도달해 있던 것이다.

노드별 편차도 컸다(51%, 12%, 6%, 5%…). 벡터 샤드가 특정 노드에 몰려 있다는 뜻이다.

여기서 운영 교훈 하나가 나온다. **JVM heap만 보는 모니터링은 벡터 DB에선 위험하다.** heap이 한가해 보여도 벡터 메모리는 터지기 직전일 수 있다. k-NN을 쓴다면 `graph_memory_usage`와 `graph_memory_usage_percentage`를 노드별로 반드시 봐야 한다. 흔히 쓰는 `elasticsearch_exporter`는 이 메트릭을 기본 제공하지 않아서, `_plugins/_knn/stats`를 따로 긁는 수집 경로가 필요하다.

## 샤드 — 어쩌다 active 3000개가 됐나

메모리를 보다가 샤드 수도 눈에 들어왔다. active shard가 3000개를 넘었다(primary 약 1600 + replica). 노드 12대에 노드당 270개꼴. 왜 이렇게 많을까 파보니 두 원인이 겹쳐 있었다.

**1. 감사 로그가 매일 인덱스를 만들며 쌓였다.**
security audit log를 켜두면 OpenSearch가 `security-auditlog-YYYY.MM.dd` 인덱스를 하루 하나씩 만든다. 정리 정책이 없으면 무한히 쌓인다. 내가 본 클러스터는 이게 277개까지 누적돼 있었고, 전체 active 샤드의 약 17%를 차지했다. 게다가 감사 로그를 계속 인덱스에 쓰는 부하 때문에 thread pool에서 요청이 거부되는 로그까지 보였다.

**2. 작은 인덱스를 과하게 쪼갰다**(over-sharding).
문서 35만 개짜리 인덱스가 primary 샤드를 36개나 쓰고 있었다. 조각당 1만 문서, 수 MB짜리 아주 작은 샤드 36개가 생긴 셈이다.

샤드가 왜 많으면 문제인지는 [OpenSearch에서의 Sharding](./sharding.md)에서 라우팅 관점으로 다뤘는데, 운영 관점에서 한 줄로 요약하면 '샤드는 공짜가 아니다'이다. 샤드 하나하나가 독립된 Lucene 인덱스라 고정 메모리·파일 핸들·스레드를 점유하고, 클러스터 상태에 메타데이터로 등록돼 master 노드 부담이 된다. 특히 **샤드 메타데이터는 JVM heap에 저장**되므로, 작은 샤드가 수천 개면 heap을 메타데이터로 낭비한다.

공식 가이드의 기준은 명확하다.

- 샤드 하나당 **10-30GB**(검색 위주) 또는 30-50GB(쓰기 위주)를 권장한다.
- 노드당 샤드는 **heap 1GiB당 25개 이하**를 권장한다(버전에 따라 16GB heap당 1000개, 노드당 최대 4000개로 완화되기도 한다).

문서 35만 개짜리는 샤드 크기 기준으로 보면 **primary 1개로 충분**하다. 36개는 분산은커녕 오버헤드만 늘린다. 다만 주의할 점은 primary 샤드 수가 **인덱스 생성 시 고정**돼 나중에 못 바꾼다는 것이다. 줄이려면 `_shrink`나 reindex가 필요하다. 그래서 처음 만들 때 데이터 규모를 보고 정하는 게 중요하다.

감사 로그 쪽은 ISM(Index State Management) 정책으로 오래된 `security-auditlog-*` 인덱스를 자동 삭제하면 샤드 수와 쓰기 부하를 한 번에 줄일 수 있다.

## 운영하며 남긴 체크리스트

벡터 DB로 OpenSearch를 굴린다면 이 정도는 보고 시작하는 게 좋겠다.

- **메모리는 heap 말고 k-NN graph memory를 본다.** `graph_memory_usage_percentage`가 50%(circuit breaker 한도) 근처면 검색 지연 위험. heap 사용률은 벡터 메모리와 무관하다.
- **circuit breaker 한도와 RAM 배분을 맞춘다.** heap을 너무 키우면 벡터가 올라갈 native 공간이 줄어든다. RAM 절반 heap, 나머지 절반에서 k-NN이라는 기본 배분을 기억한다.
- **인덱스 생성 시 샤드 수를 신중히 정한다.** 작은 인덱스를 잘게 쪼개지 않는다. 샤드당 10-30GB, 노드당 heap GiB당 25개 이하를 기준으로 본다. 나중에 못 바꾸니 처음이 중요하다.
- **감사 로그 같은 일별 인덱스에 ISM 정책을 건다.** 정리 없이 두면 샤드가 무한 누적된다.
- **모니터링 대시보드에 k-NN 메모리 패널을 넣는다.** 기본 exporter엔 없으니 `_plugins/_knn/stats`를 긁어야 한다.

heap이 한가하다고 안심하지 말 것 — 벡터는 그 뒤 native에 따로 살고 있다. 이 한 문장이 이번에 가장 크게 남은 교훈이다.

## 참고

- [k-NN settings — OpenSearch Documentation](https://docs.opensearch.org/latest/vector-search/settings/)
- [Circuit breaker settings — OpenSearch Documentation](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/circuit-breaker/)
- [k-NN Performance Tuning — Open Distro Documentation](https://opendistro.github.io/for-elasticsearch-docs/docs/knn/performance-tuning/)
- [Optimize OpenSearch index shard size — OpenSearch Blog](https://opensearch.org/blog/optimize-opensearch-index-shard-size/)
- [Choosing the number of shards — Amazon OpenSearch Service](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/bp-sharding.html)
