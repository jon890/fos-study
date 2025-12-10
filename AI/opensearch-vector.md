# OpenSearch를 VectorStore로 활용하기 위한 가이드

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
