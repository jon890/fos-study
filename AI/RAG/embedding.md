# Embedding(임베딩)

- 텍스트(문장, 단락, 문서 등)를 **고차원 실수 벡터**(예: 768차원, 1536차원)로 변환하는 기술
- 이 벡터는 **의미적 유사도**를 반영하도록 학습되어 있어서, 서로 의미가 비슷한 문장은 벡터 공간에서 가깝다

이렇게 만든 벡터로 "가까운 문서"를 찾는 게 [kNN·HNSW 같은 벡터 검색 알고리즘](./vector-search-algorithms.md)이고, 그 위에 RAG가 올라간다.

## Embedding 내부 구조

### Embedding Vector 특징

- 고정 길이 : 모든 문장은 768차원 같은 고정된 벡터로 변환됨
- 의미 기반 거리 : 코사인 유사도(cosine similarity)로 의미적 거리 측정
- 문서 길이 제한 존재 : 모델 입력 토큰 제한이 있어 텍스트 chunking 필요
- 분포 기반 : 의미가 비슷한 문장은 같은 방향의 벡터를 가짐

> 단순 Bag-of-Words가 아니라 Transformer 기반 문장 의미 표현이기 때문에 검색 품질이 매우 높음

### "의미가 비슷하면 가깝다"는 어떻게 학습되나

임베딩 모델이 처음부터 의미를 아는 건 아니다. **contrastive learning**(대조 학습)으로 그렇게 만든다.

- 의미가 같은 문장 쌍(positive)은 벡터를 **가깝게**, 무관한 쌍(negative)은 **멀게** 당기도록 학습한다.
- 대부분의 최신 모델이 **InfoNCE**라는 손실 함수를 쓴다 — 한 positive를 여러 negative와 동시에 비교해, 정답 쌍만 가깝게 만든다.
- 그래서 임베딩의 "가까움"은 사람이 정의한 게 아니라, 수많은 쌍을 보고 모델이 익힌 결과다.

### 차원은 왜 768·1536이고, 줄일 수 있나

- 차원이 클수록 표현력은 늘지만 저장·검색 비용도 커진다.
- 2025년 들어 **Matryoshka Representation Learning**(MRL)이 사실상 표준이 됐다 — 한 번 만든 임베딩의 **앞쪽 일부 차원만 잘라 써도** 품질이 급격히 무너지지 않고 완만하게 떨어진다.
- 덕분에 같은 모델로 "정밀하게(전체 차원) vs 싸게(잘라서)"를 상황에 따라 고를 수 있다. Gemini·Voyage·Cohere·OpenAI `text-embedding-3-*` 등이 지원한다.

## 어떤 임베딩 모델을 쓸까

- 모델 성능 비교의 사실상 표준은 **MTEB**(Massive Text Embedding Benchmark) 리더보드다.
- 상위권 예 — Cohere `embed-v4`, OpenAI `text-embedding-3-large`, 오픈소스 `BGE-M3`.
- 한국어·다국어가 중요하면 multilingual 모델(`multilingual-e5`, `BGE-M3`)을 우선 본다.
- 점수만 보지 말고 **차원·비용·라이선스·다국어 지원**을 함께 따져야 실무에서 안 후회한다.

## 궁금한 점

### 검색할 때마다 임베딩을 계산해야 하는가?

- 결론
  - 그렇다. 검색(질문)할 때마다 새로운 임베딩 벡터를 생성해야 한다.
- 검색 과정은 다음과 같다
  ```text
  [사용자 질문] -> 임베딩 생성 -> 벡터 DB 검색 -> 결과 변환
  ```
- 왜 매번 생성해야 하는가?

  - 사용자가 입력하는 질문은 매번 다름
  - 그 질문과 "의미적으로 가까운 문서"를 찾기 위해 **질문 벡터**가 필요함
  - 벡터 DB는 "벡터 간 거리"로 검색하기 때문에 질문을 벡터로 바꿔야 함

> 즉, 사용자 입력은 사전에 임베딩해둘 수 없어서 **실시간 임베딩 생성**이 필수

### 그럼 외부 모델을 쓰면 매번 과금되는가?

- 결론
  - 그렇다. 외부 임베딩 API(OpenAI, Cohere 등)를 사용하면 질문 1번마다 과금된다
- 예를 들어 OpenAI의 `text-embedding-3-small` 기준
  - 1000 tokens당 0.02달러 정도 (2025 기준)
  - 질문 하나는 보통 5~40 tokens -> 매우 저렴하지만 **누적되면 비용이 된다**
- (예) 하루에 10,000번 검색
  - 각각 평균 20 tokens -> 1000 tokens = 50 query
  - 하루에 200개의 1000-token 단위 = 200 \* $0.02 = $4/day
  - 한달 약 $120
- 작게 시작하면 문제없지만 규모가 커지면 꽤 나간다

### 비용을 줄이는 실무적 해결책

- **방법A. 자체 임베딩 모델 로컬/온프레미스 구축**

  - HuggingFace SentenceTransformer(예: `bge-large`, `multilingual-e5-large`)등을 GPU 서버에 띄우기
  - 사내 검색에는 충분히 높은 성능
  - 비용 -> **고정비**(서버 비용)로 변환
  - 대기업/스타트업 대부분이 결국 이 방향으로 감

- **방법B. 임베딩 캐싱**

  - 같은 질문이 자주 나온다면 cache hit률을 높일 수 있음
  - 경험적으로:
    - 사내 FAQ, 정책 질문 -> 패턴이 반복됨
      - lookup table 캐시로 30~60% 절감 가능

- **방법C. Hybrid Search로 임베딩 요청 횟수 줄이기**
  - BM25(키워드 검색) 필터링으로 후보를 좁힌 뒤
  - 임베딩 모델을 적용하는 방식
  - 이렇게 하면 질문이 임베딩을 반드시 필요로 하지 않는 경우도 있음

### 문서 청크 임베딩은 같은 모델로 만들어야 하는가?

- **100% 그렇다. 반드시 동일한 임베딩 모델을 사용해야 한다**
  - 이유 : 임베딩은 **각 모델이 가진 좌표계**(embedding space)가 다르다
  - 예
    - OpenAI `embedding-3-large`로 만든 벡터는 1536차원에서 특정 방향 의미를 가짐
    - SentenceTransformer `bge-large`는 1024차원에서 완전히 다른 공간 구조를 가짐
  - 질문 벡터와 문서 벡터가 같은 좌표계여야 거리 계산이 의미를 가진다

## 참고 링크

- [MTEB Leaderboard (Hugging Face)](https://huggingface.co/spaces/mteb/leaderboard)
- [Recent advances in text embedding — MTEB 리뷰 (arXiv)](https://arxiv.org/html/2406.01607v1)
- [Best Embedding Models 2025 — MTEB Scores (Ailog)](https://app.ailog.fr/en/blog/guides/choosing-embedding-models)
