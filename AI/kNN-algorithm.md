# kNN (k-Nearest Neighbors) 알고리즘

- knn = 어떤 벡터(쿼리)와 가장 가까운 k개의 이웃 벡터를 찾는 알고리즘
- 예를 들어
  - 문서 임베딩이 1536차원 벡터로 저장되어 있고
  - 사용자가 질문했을 때 질문도 벡터로 변환되면
    > "질문 벡터와 가장 가까운 문서 벡터 k개를 찾아라" 라고 하는 과정

## 벡터간 "가까움"은 어떻게 계산하는가?

- **1. Cosine Similarity (RAG에서 거의 표준)**

  - 각도 기반 유사도
  - **두 벡터의 방향이 얼마나 비슷한가**
  - 텍스트 임베딩에는 가장 잘 맞아서 일반적으로 이걸 사용

- **2. Euclidean Distance (L2 거리)**

  - 물리적으로 벡터 좌표 간 거리

- **3. Dot Product**

  - 값의 크기 + 방향을 모두 고려
  - OpenAI 등 최신 모델은 **dot product** 기반으로 search하면 더 성능 잘 나오는 경우도 있음

## kNN의 단점 : 느리다 (Brute-force)

- 벡터 하나와 모든 벡터 사이의 거리를 계산해야 한다면
  - 쿼리 벡터 1개
  - 문서 벡터 N개 (예: 1천만 개)
  - 계산량 = 1천만 번 거리 계산
- 이걸 "Brute force kNN" 이라고 해
  - 차원이 높고 데이터가 많으면 절대 실시간 서비스가 불가능함
  - 그래서 벡터 검색 기술이 필요함

## 그래서 등장한 것이 ANN (Approximate Nearest Neighbor)

ANN은 정확한 이웃을 찾는 대신

- 정확도 98 ~ 99% 수준
- 속도는 수백 ~ 수천 배 빠름

이라는 목표를 가진 알고리즘

대표 ANN 알고리즘이 바로 **HNSW, Faiss, ScaNN, IVF+PQ**등이 있다
OpenSearch는 HNSW를 핵심으로 사용

## HNSW가 kNN을 빠르게 하는 방법

kNN은 본래 모든 점을 비교해야 하지만,
HNSW는 그래프를 이용해 "빠르게 후보를 좁히는 구조"를 사용한다

핵심 아이디어

1. 임베딩 벡터들을 층(layer) 구조의 그래프로 만든다
2. 상위 층에서 빠르게 주위 후보를 찾는다 (rough search)
3. 하위 층으로 내려가며 점점 정밀하게 kNN을 찾는다

이 구조 덕분에

- 데이터 수가 늘어도 속도 저하가 적고
- 검색 속도는 O(log N)에 가까워짐

> 즉, "kNN을 실시간에 사용할 수 있도록 만든 알고리즘이 HNSW" 라고 이해하면 좋음

## OpenSearch에서 kNN 알고리즘은 어떻게 동작할까?

- OpenSearch에서 vector 인덱스를 생성하면 이렇게 설정함

```json
{
  "method": {
    "name": "hnsw",
    "engine": "faiss",
    "space_type": "cosinesimil"
  }
}
```

- `name: hnsw` -> ANN 기반 그래프 사용
- `engine: faiss` -> Facebook FAISS 사용 (가장 빠른 엔진 중 하나)
- `space_type: cosinesimil` -> 코사인 유사도로 계산

> 즉, OpenSearch는 내부적으로 kNN을 ANN 방식으로 최적화한 그래프 탐색을 한다"
