# OpenSearch로 RAG 검색 품질 높이기 — Hybrid Search, Reranking, Sentence Window

RAG 파이프라인에서 OpenSearch를 검색 엔진으로 쓸 때, 순수 벡터 검색만으로는 한계가 있다. 실제로 구현된 코드를 분석하면서 검색 품질을 높이는 세 가지 기법을 정리해봤다.

---

## 왜 벡터 검색만으론 부족한가

벡터 검색(kNN)은 의미적으로 유사한 문서를 찾는 데 강하다. 그런데 사용자가 고유명사, 코드명, 오타가 섞인 키워드로 검색하면 벡터 유사도가 낮게 나오는 경우가 있다. 반대로 전통적인 BM25 키워드 검색은 의미는 같지만 단어가 다른 경우를 잡아내지 못한다.

두 방식의 약점을 보완하기 위해 **Hybrid Search**가 등장했다. 그리고 Hybrid Search로 많이 召唤한 결과에서 진짜 관련 문서를 추리기 위해 **Reranking**을 붙인다. 거기에 더해 청크 단위 검색의 컨텍스트 단절 문제를 해결하는 **Sentence Window** 기법까지, 세 가지를 차례로 살펴본다.

---

## 1. Hybrid Search — BM25 + kNN 조합

### 인덱스 설계

Hybrid Search를 지원하려면 인덱스에 벡터 필드와 텍스트 필드를 함께 가지고 있어야 한다.

```json
{
  "settings": {
    "index": {
      "knn": true
    },
    "analysis": {
      "analyzer": {
        "custom_nori_speech": {
          "type": "custom",
          "tokenizer": "nori_tokenizer"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "engine": "faiss",
          "name": "hnsw",
          "space_type": "cosinesimil"
        }
      },
      "content": {
        "type": "text",
        "analyzer": "custom_nori_speech"
      }
    }
  }
}
```

- `embedding`: 1024차원 벡터, FAISS 엔진, HNSW 알고리즘, cosine similarity
- `content`: 한국어 형태소 분석(Nori)으로 역색인 생성

한국어 검색 품질을 위해 Nori 플러그인이 필요하다. OpenSearch에는 기본 포함이 아니라 별도 설치가 필요하다.

### 쿼리 구조

Hybrid Search는 `bool.should`로 kNN 쿼리와 키워드 쿼리를 함께 날린다.

```java
// kNN 쿼리: 의미 유사도 검색
KnnQuery knnQuery = KnnQuery.builder()
    .field("embedding")
    .vector(embeddingVector)
    .k(50)
    .boost(0.7f)
    .build();

// 키워드 쿼리: BM25 기반 텍스트 검색 (점수 정규화 적용)
// script score: (text_score / (text_score + 1)) * 0.3
FunctionScoreQuery textQuery = FunctionScoreQuery.of(fsq -> fsq
    .query(MatchQuery...)
    .boostMode(FunctionBoostMode.Replace)
    .functions(...)
);

// bool.should로 결합 → 두 점수 합산
BoolQuery hybridQuery = BoolQuery.of(b -> b
    .should(knnQuery.toQuery())
    .should(textQuery.toQuery())
    .minimumShouldMatch("1")
);
```

점수 정규화가 중요하다. BM25 점수는 문서 길이와 빈도에 따라 범위가 다르기 때문에 `(score / (score + 1)) * 0.3` 공식으로 0~0.3 사이로 눌러주고, kNN은 cosine similarity 특성상 이미 0~1 범위라 boost 0.7을 곱해 0~0.7로 맞춘다. 두 점수의 합이 최종 hybrid score가 된다.

### 세 가지 검색 API

실제 구현을 보면 검색 API를 세 가지로 분리해뒀다.

| API | 방식 | 특징 |
|-----|------|------|
| `searchByVector` | kNN only | 의미 유사도 중심, boost 0.7 |
| `searchByKeyword` | BM25 only | 정확 키워드 매칭 중심, score 정규화 |
| `searchByHybrid` | kNN + BM25 | 두 방식 결합, 가장 범용적 |

---

## 2. Reranking — Recall에서 Precision으로

### 2단계 검색 파이프라인

벡터 검색이나 Hybrid Search로 상위 50개를 가져와도, 그 중 진짜 관련 있는 문서 10개를 고르는 건 별개의 문제다. **Reranker**는 이 역할을 한다.

```
1단계 (Recall)  : OpenSearch → 상위 50개 (빠르게 많이)
2단계 (Precision): Reranker → 상위 10개 (정확하게 추림)
```

구조적으로 보면 OpenSearch는 **bi-encoder** 방식이다. 쿼리와 문서를 각각 임베딩해서 벡터 거리를 비교하기 때문에 빠르다. Reranker는 보통 **cross-encoder** 방식으로, 쿼리와 문서를 쌍으로 입력해 더 정교하게 관련도를 계산한다. 느리지만 정확하다.

```
OpenSearch 쿼리 실행
    ↓
상위 50개 문서 + 쿼리 텍스트를 reranker API로 전송
    ↓
reranker가 각 문서의 relevance score 계산
    ↓
score 기준 정렬 후 상위 10개 반환
```

### 응답에서 두 점수 확인

```json
{
  "contents": "...",
  "url": "...",
  "score": 0.76,        // OpenSearch 검색 점수 (벡터 유사도)
  "rerankScore": 0.91   // Reranker가 계산한 관련도 점수
}
```

`score`와 `rerankScore`를 둘 다 노출하는 건 디버깅에 유용하다. 두 점수 순서가 뒤집힌 문서를 보면 reranker가 어떤 기준으로 판단하는지 감을 잡을 수 있다.

> 실제로 hybrid 검색 시 `rerankScore`가 모든 문서에서 `1e-06`으로 동일하게 찍히는 버그가 리포트된 적 있다. `score`(벡터 유사도)는 정상인데 reranker 결과만 이상한 케이스라 reranker API 입력/출력 파싱 쪽을 먼저 의심해볼 것 같다.

---

## 3. Sentence Window — 청크 검색, 확장 컨텍스트 반환

### 문제: 청크가 너무 작으면 컨텍스트가 끊긴다

RAG에서 문서를 청크로 나눠 색인하면 검색 정밀도는 올라가지만, LLM에게 전달하는 컨텍스트가 너무 짧아지는 문제가 생긴다. 앞뒤 맥락 없이 잘린 청크는 답변 품질을 떨어뜨린다.

### 해결: extra_content 필드

**Sentence Window(Small-to-Big)** 기법은 이렇게 동작한다.

1. 색인할 때: 각 청크에 앞뒤 청크를 붙인 `extra_content` 필드를 함께 저장
2. 검색할 때: `content`(원본 청크)로 검색 → 반환은 `extra_content`(확장 컨텍스트)로

```json
{
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "custom_nori_speech"
      },
      "extra_content": {
        "type": "text",
        "index": false
      }
    }
  }
}
```

`extra_content`는 `"index": false`로 검색 대상에서 제외한다. 저장만 하고 반환용으로만 쓴다.

```
extra_content = 이전 청크 + "\n" + 현재 청크 + "\n" + 다음 청크
```

작은 단위로 정확하게 검색하되, LLM에게는 충분한 컨텍스트를 주는 방식이다.

---

## 세 기법의 조합

정리하면 이렇게 연결된다.

```
사용자 쿼리
    │
    ├─ 텍스트 임베딩 → kNN 검색 (embedding 필드)
    ├─ 형태소 분석 → BM25 검색 (content 필드)
    │    └─ Hybrid Search로 두 결과 합산
    │
    ↓ 상위 50개

Reranker API (cross-encoder)
    ↓ 상위 10개

응답: extra_content (앞뒤 청크 포함 확장 컨텍스트)
```

각 기법이 서로 다른 문제를 해결한다.
- Hybrid Search: 검색 recall 향상 (키워드도, 의미도 잡는다)
- Reranking: precision 향상 (50개 중 진짜 관련 문서를 추린다)
- Sentence Window: LLM 입력 품질 향상 (잘린 컨텍스트 문제를 해결한다)

---

## 운영 측면에서 기억할 것

- **Native memory 관리**: OpenSearch k-NN 인덱스는 JVM 힙이 아닌 native memory를 쓴다. 문서 수가 늘어나면 heap과 native memory 사용량을 함께 모니터링해야 한다
- **임베딩 모델 교체 시 전체 재색인**: dimension이나 similarity 함수가 바뀌면 인덱스를 새로 만들고 전체 재색인이 필요하다. 배치 파이프라인이 있더라도 부담스러운 작업이다
- **메타데이터는 OpenSearch에 두지 않는 것 고려**: index group, source 관계 같은 메타데이터를 OpenSearch에 넣으면 FK/트랜잭션 보장이 안 된다. MySQL 같은 RDBMS에서 관리하고 OpenSearch는 검색에만 집중하는 구조가 장기적으로 더 낫다
