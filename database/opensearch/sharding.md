# OpenSearch의 샤딩 — 개념, 공식, 실무 가이드

"HashMap의 동작 원리"를 떠올리면 이해가 가장 빠르다. 데이터를 여러 조각(샤드)으로 쪼개서 여러 노드에 분산하고, 특정 데이터가 어느 조각에 있는지는 결정론적 계산으로 즉시 찾아낸다.

## 샤딩이란 무엇인가 — 왜 필요한가

단일 노드는 저장 용량과 처리량에 물리적 한계가 있다. 데이터가 계속 늘면 노드 하나로는 감당이 안 되는 시점이 온다. 샤딩은 데이터를 여러 조각으로 나눠 여러 노드에 분산시켜, 이 한계를 수평으로 넓히는 방법이다.

문제는 "어떤 데이터를 어느 조각에 넣을지"를 어떻게 정하느냐다. 방식에 따라 분산 시스템의 성격이 크게 갈린다.

## 샤딩 전략 3가지

| 전략 | 배치 방식 | 장점 | 단점 | 대표 사용처 |
| --- | --- | --- | --- | --- |
| 해시 기반 | `hash(key) mod N` | 균일하게 분산됨, 계산이 단순 | 샤드 수(N)를 바꾸면 거의 모든 데이터의 계산 결과가 달라져 재배치 규모가 크다 | OpenSearch·Elasticsearch |
| 범위 기반 | 키 값의 범위로 구간 분할 | 범위 쿼리(예: 특정 기간 조회)가 빠름 | 특정 범위에 데이터가 몰리면 그 샤드만 뜨거워짐(hot shard) | HBase·BigTable |
| 컨시스턴트 해싱 | 해시 공간을 원형(ring)으로 두고 노드를 배치 | 노드 추가·제거 시 이동하는 데이터가 일부(약 1/N)로 제한됨 | 구현이 더 복잡하고, 가상 노드(virtual node) 튜닝이 필요 | Cassandra·DynamoDB |

세 전략의 핵심 차이는 **리샤딩(재샤딩) 시 데이터 이동량**이다. 해시 기반(`mod N`)은 N이 바뀌면 나머지 연산 결과가 통째로 달라져 거의 모든 키가 재배치 대상이 된다. 컨시스턴트 해싱은 원형 해시 공간에서 노드 하나만 추가·제거되므로, 그 노드 주변 구간만 영향을 받아 이동량이 훨씬 적다. 이게 왜 중요한지는 아래에서 OpenSearch 사례로 바로 이어진다 — OpenSearch는 해시 기반을 쓰기 때문에 정확히 이 문제(샤드 수를 나중에 못 바꿈)를 겪는다.

## OpenSearch는 해시 기반 샤딩을 쓴다 — 핵심 공식

OpenSearch가 "이 문서를 0번 샤드에 넣을지, 1번 샤드에 넣을지" 결정하는 방법은 **모듈러 연산** 공식이다.

```text
shard_num = hash(_routing) mod num_primary_shards
```

- `_routing` — 기본적으로 문서의 `_id` 값이 쓰인다(개발자가 임의로 지정 가능).
- `hash` — `Murmur3` 해시 함수로 문서를 균일하게 분산시킨다.
- `num_primary_shards` — 인덱스 생성 시 설정한 프라이머리 샤드 개수다.
- `mod` — 해시 값을 샤드 개수로 나눈 나머지로 샤드 번호를 정한다.

이 공식 덕분에 데이터가 들어올 때 랜덤하게 저장되는 게 아니라, 특정 값(`_id`)이 항상 같은 샤드로 배정됨이 보장된다.

## 논리적 구조 vs 물리적 배치

샤딩은 논리적인 인덱스를 물리적인 파일 덩어리로 쪼개는 과정이다.

- **Index**(논리적 개념) — 개발자가 바라보는 데이터의 집합
- **Shard**(물리적 개념) — 실제 데이터가 저장되는 Lucene 인스턴스. 각 샤드는 독립적인 검색 엔진이며 CPU·메모리·디스크 자원을 소비한다.
- **Node**(서버) — OpenSearch 프로세스가 실행되는 물리적 서버. 여러 샤드가 여러 노드에 분산 배치된다.

### 데이터 분산 예시 (샤드 3개, 레플리카 1개, 노드 3개)

- 프라이머리 샤드(P0, P1, P2)는 노드 1, 2, 3에 골고루 퍼진다.
- 레플리카 샤드(R0, R1, R2)는 자신의 원본과 **절대 같은 노드에 배치되지 않는다.**
- `P0`가 있는 노드 1이 죽으면, 다른 노드에 있는 `R0`가 즉시 `P0`으로 승격된다.

## 레플리카 — 왜 필요하고 몇 개가 적당한가

레플리카는 프라이머리 샤드의 복제본이다. 목적은 두 가지다.

- **장애 대응** — 위 예시처럼 프라이머리가 있는 노드가 죽으면 레플리카가 즉시 승격돼 서비스가 끊기지 않는다.
- **읽기 처리량 분산** — 검색 쿼리는 프라이머리든 레플리카든 어느 쪽으로도 라우팅될 수 있다. 레플리카를 늘리면 같은 데이터를 처리할 수 있는 검색 경로가 늘어나 읽기 처리량이 올라간다.

다만 **공짜가 아니다.** 쓰기는 프라이머리에 먼저 기록된 뒤 모든 레플리카에도 복제돼야 끝난다. 레플리카가 늘수록 쓰기 한 번의 복제 비용이 늘어난다 — 그래서 레플리카 수는 "읽기 처리량"과 "쓰기 비용·저장 공간" 사이의 트레이드오프다.

**여기서 샤드 수와 정확히 대조되는 지점이 나온다.** 프라이머리 샤드 수(`number_of_shards`)는 인덱스 생성 후 고정되는 static 설정이지만, 레플리카 수(`number_of_replicas`)는 언제든 API 호출 한 번으로 바꿀 수 있는 **dynamic 설정**이다([Update Settings API](https://docs.opensearch.org/latest/api-reference/index-apis/update-settings/)). 검색 트래픽이 늘면 레플리카만 늘려서 대응할 수 있지만, 데이터 자체가 늘어서 샤드를 더 쪼개야 하는 상황이라면 앞서 본 Split API나 Reindex 로 가야 한다 — "무엇이 늘었는가(트래픽 vs 데이터 크기)"가 레플리카를 늘릴지 샤드를 늘릴지를 가른다.

## 왜 프라이머리 샤드 개수를 나중에 못 바꿀까

OpenSearch를 운영하다 보면 "처음에 샤드 5개로 잡았는데, 데이터가 너무 많으니 10개로 늘리고 싶다"는 상황이 온다. 하지만 이미 생성된 인덱스의 프라이머리 샤드 개수는 변경할 수 없다.

이유는 바로 위 공식 때문이다. 데이터를 저장할 때 `5`로 나눈 나머지로 위치를 정했는데, 나중에 샤드 개수를 `10`으로 바꿔버리면 조회할 때 엉뚱한 샤드를 뒤지게 된다 — 데이터가 증발한 것처럼 보인다. 위에서 본 "해시 기반 샤딩은 N이 바뀌면 재배치 규모가 크다"는 일반론이 여기서 실제로 발생하는 것이다.

## 실무 적용 가이드 — 샤드 크기와 개수 정하기

### 샤드 크기 권장 가이드라인

OpenSearch 공식 블로그가 권장하는 샤드 크기는 워크로드에 따라 다르다([Optimize OpenSearch index shard sizes](https://opensearch.org/blog/optimize-opensearch-index-shard-size/)).

- **검색/저지연 워크로드**: 샤드당 10-30GB. 읽기가 잦으면 Lucene 인덱스를 자주 훑어야 해서, 샤드를 작게 유지해 지연을 낮춘다.
- **쓰기 위주 워크로드**(로그 분석 등): 샤드당 30-50GB. 인입 처리량을 우선한다.

### 오버샤딩 · 언더샤딩의 구체적 문제

- **오버샤딩**(샤드가 너무 많을 때) — 샤드마다 메타데이터가 JVM heap 메모리에 상주한다. 샤드가 지나치게 많으면 이 메타데이터만으로 메모리를 불필요하게 소모한다.
- **언더샤딩**(샤드가 너무 적을 때) — 인덱싱·검색의 병렬성이 샤드 수에 묶여 있어서, 노드는 여러 대인데 샤드가 적으면 일부 노드가 놀게 된다.

### Split / Shrink API — 그래도 나중에 바꿀 수는 있다

샤드 개수를 나중에 "그냥 바꾸는" 건 안 되지만, 새 인덱스로 재구성하는 API 는 있다([Split Index API](https://docs.opensearch.org/latest/api-reference/index-apis/split/), [Shrink Index API](https://docs.opensearch.org/latest/api-reference/index-apis/shrink-index/)).

- **Split** — 샤드 수를 늘린다. 새 프라이머리 샤드 수는 원본 샤드 수의 **배수**(multiple)여야 한다(예: 2개 → 4개·6개·8개는 가능, 3개는 불가능).
- **Shrink** — 샤드 수를 줄인다. 새 프라이머리 샤드 수는 원본 샤드 수의 **약수**(factor)여야 한다 — Split 과 정반대 제약이다.
- 둘 다 실행 전 대상 인덱스를 **read-only**로 만들어야 한다(`index.blocks.write: true`). 클러스터 상태도 green 이어야 한다.

결국 완전히 자유로운 배수가 아니라 배수·약수 관계라는 제약이 있어서, `Reindex`(새 인덱스를 만들고 데이터를 처음부터 다시 이관)가 여전히 가장 유연한 방법이다. 다만 Reindex 는 전체 데이터를 다시 써야 해서 Split/Shrink 보다 비용이 크다.

### 시계열 데이터라면 — rollover로 아예 문제를 피한다

로그처럼 시간 순으로 계속 쌓이는 데이터는 애초에 "샤드 개수를 미리 정확히 맞추는" 문제 자체를 피할 수 있다. Index Lifecycle Management(ISM)의 rollover 정책으로 일정 크기·기간마다 새 인덱스를 자동 생성하면, 각 인덱스는 작고 예측 가능한 크기를 유지하고 오래된 인덱스는 삭제·아카이브한다. 샤드 크기가 한 인덱스에 갇히지 않고 시간 축으로 자연스럽게 나뉜다.

## 참고 링크

- [Optimize OpenSearch index shard sizes](https://opensearch.org/blog/optimize-opensearch-index-shard-size/)
- [Amazon OpenSearch Service 101: How many shards do I need](https://aws.amazon.com/blogs/big-data/amazon-opensearch-service-101-how-many-shards-do-i-need/)
- [Choosing the number of shards — AWS OpenSearch Service](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/bp-sharding.html)
- [Split Index API — OpenSearch Documentation](https://docs.opensearch.org/latest/api-reference/index-apis/split/)
- [Shrink Index API — OpenSearch Documentation](https://docs.opensearch.org/latest/api-reference/index-apis/shrink-index/)
- [Update Settings API — OpenSearch Documentation](https://docs.opensearch.org/latest/api-reference/index-apis/update-settings/)
