# OpenSearch를 VectorStore로 활용하기 위한 가이드

- OpenSearch는 원래 Elasticsearch에서 파생된 **검색 엔진 기반 분산 데이터베이스**
- 최근에는 **벡터 검색(Vector Search)** 기능이 강화되어 RAG 시스템에서 많이 쓰임
  - 또 다른 활용으로는 추천 시스템, 이상 감지, 자연어 처리 등에도 사용 됨
  - 자세한 내용은
    - https://opensearch.org/platform/vector-search/
- 대규모, 정형화되어있지 않은 데이터셋, AI 애플리케이션을 위한 고성능 퍼포먼스를 제공함

## 1. OpenSearch 구조 간단 정리 (로그/매트릭이랑 같은 개념)

- Cluster : OpenSearch 전체 집합 (보통 하나의 서비스 단위)
- Node : 클러스터를 구성하는 서버 (인스턴스)
- Index : 논리적인 데이터 묶음 (RDB로 치면 테이블 느낌)
- Shard : 인덱스를 쪼갠 물리 단위 (실제 Lucene index), 샤드가 노드에 분산 저장됨
  - Primary shard
  - Replica shard (복제본, 장애 대비 + read 스케일 아웃)
- 로그/매트릭 수집용으로 이미 이런 구조는 경험했음
  - `logs-*`, `metrics-*` 같은 인덱스들
  - 샤드 수, replicas 수 결정
  - Kibana / OpenSearch Dashboards로 검색/집계

> 벡터 검색도 똑같이 "인덱스"에 문서가 들어가고, 단지 필드 중 하나가 벡터(knn_vector)인 것뿐이다

## 2. 벡터용 OpenSearch: k-NN 플러그인 + `knn_vector`

벡터 검색을 하려면 OpenSearch의 **k-NN 플러그인**을 써야하고,
이 플러그인이 제공하는 `knn_vector` 필드 타입을 사용하게 됨

- 1. `knn_vector`가 해주는 일
  - 문서에 **고차원 벡터**를 저장할 수 있게 해줌
  - 이 벡터들을 이용해 **k-Nearest Neighbor 검색**(가장 가까운 벡터들 찾기)을 수행
  - 내부적으로 HNSW 같은 **Approximate k-NN 알고리즘**으로 빠르게 탐색

즉, 일반 `text` 필드가 "키워드/문자열 검색"을 담당한다면,
`knn_vector` 필드는 **"의미적 유사도 기반 검색**을 담당한다고 보면 됨

### 3. 벡터 인덱스를 만들 때 신경 쓸 것들

인덱스 생성시 필수 설정

```json
{
    {
        "settings": {
            "index": {
                "knn": true // k-NN 기능 활성화
            }
        }
    },
    "mappings" :{
        "properties": {
            "embedding": {
                "type": "knn_vector"
                "dimension": 1536, // 임베딩 차원 수 (모델에 맞춰야 함)
                "method": {
                    "name" : "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                    "parameters": {
                        "ef_construction": 128,
                        "m": 16
                    }
                }
            }
            // .. other properties
        }
    }
}
```

중요한 포인트

- `index.knn: true`
  - 이 인덱스에서 k-NN 검색을 하겠다고 선언하는 것
- `knn_vector.dimension`
  - 사용 중인 임베딩 모델의 차원 수와 **무조건 일치**해야 함
  - 예: OpenAI `text-embedding-3-small` = 1536차원 -> dimension 1536

## 3. OpenSearch가 벡터 검색을 어떻게 수행하는가?

- 벡터 검색 알고리즘은 주로 **HNSW (Hierarchical Navigable Small World graph)** 기반
  - HNSW 핵심 요약
    - 벡터 간 유사도를 차직 위한 그래프 구조
    - 수백만 벡터까지 빠름
    - 근사 최근접 탐색(ANN, Approximate Nearest Neighbor)
    - 정확도는 조금 떨어지지만 속도가 매우 빠름

## 4. OpenSearch를 벡터 스토어로 운영할 떄 중요한 점

- **1. 데이터를 많이 넣을 떄 고려해야 하는 요소**
  - OpenSearch는 "검색엔진"이라 대구모 데이터를 처리하려면 아래를 반드시 고려해야 함
  - 샤드 수 설정
    - 일반적으로 데이터량에 맞춰서 샤드를 결정해야 함
    - ~1M 문서 : 1 ~ 3 샤드
    - 10M 문서 : 3 ~ 6 샤드
    - 100M 문서 : 6 ~ 12 샤드
    - 1B 문서 : 20+
    - 샤드 수는 인덱스를 만들 떄만 결정 가능하니 신중해야 함
  - 복제본(Replicas) 설정
    - 추천 구조:
      - Primary Shard: 3 ~ 6
      - Replica : 1 (운영 필수)
    - Replica를 두면:
      - 노드 장애 시 검색이 유지 됨
      - 분산 검색 성능이 올라감
  - 노드 수 & 스펙 규모 확장
    - 대규모 embedding 저장 시 CPU 보다 **메모리, 디스크 I/O**가 훨씬 중요함
    - 권장 스펙:
      - RAM: 최소 32GB (아니면 evict 발생)
      - SDD NVMe
      - JVM Heap: RAM의 50% 이하
- **2. 인덱스 성능 최적화 팁**
  - Bulk API 사용
    - 1000 ~ 5000개 정도의 문서를 Batch로 넣기
    - -> 성능 10 ~ 20배 증가
  - Refresh Interval 늘리기
    - 기본값 1초 -> 30초로 늘리기 (쓰기 성능 급상승)
  - replicas=0 로 먼저 넣고 나중에 늘리기
    - 레플리카 복제 비용이 줄어 성능이 대폭 증가

## 5. 검색 품질을 위한 알고리즘 선택

벡터 검색 품질은 아래 두 요소로 결정됨

1. Similarity Metric (코사인 vs L2 vs dot)
2. Indexing method (HNSW)

- **1. Similarity Metric 선택법**
  - 문서 검색 : cosine_similarity
  - 이미지/멀티모달 : dot_product
  - 유사도 기반 RAG : cosine
- **2. HNSW 파라미터 튜닝**
  - `ef_construction` : 인덱싱 정확도
    - 높을수록 정확하지만 느림
  - `ef_search` : 검색 정확도
    - 높을수록 recall 증가
  - `m` : 그래프 branching factor
    - 메모리 사용량 영향
  - 추천값
    - ef_construction: 128 ~ 256
    - ef_search: 40 ~ 200
    - m: 16 ~ 32
  - RAG 서비스라면 ef_search를 높일수록 "정확한 문서"를 찾게 됨

## 5. 검색 품질을 더 올리기 위한 실전 팁

사실 embedding + vector search만으로는 검색 품질이 100% 나오지 않음
그래서 대규모 서비스는 다음을 조합함

- **1. Hybrid Search (BM25 + Vector)**
  - BM25(키워드 검색)와 벡터 검색을 합친 방식
  - 예
    - `score = 0.7 * vector_score + 0.3 * bm25_score`
  - 결과
    - 오타/키워드 검색 강해짐
    - 문맥 검색도 가능함
    - RAG 품질 대폭 상승
  - OpenSearch 2.x에서 공식 지원
- **2. Reranking (re-ranking 모델 적용)**
  - 검색 결과 Top N개를 가져온 다음, LLM 또는 corss-encoder 모델로 다시 랭킹
  - `Vector Search -> Top 200 전달 -> Reranker -> Top 5 추출`
  - 검색 품질이 극적으로 개선됨
- **3. Chunking 전략 조정**
  - RAG의 핵심은 "적절한 청크 크기"
  - 추천
    - 청크 크기 : 200 ~ 500 tokens
    - overlap : 20 ~ 30%
  - 문서가 가벼우면 더 작게 나눠도 좋음
