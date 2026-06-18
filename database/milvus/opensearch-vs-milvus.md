# OpenSearch vs Milvus — 벡터 검색, 무엇이 어떻게 다른가

RAG 를 OpenSearch 의 k-NN 으로 운영하다가 전용 벡터 DB 인 Milvus 로 옮길지 검토하면서, 두 제품을 아키텍처부터 검색·메모리·운영까지 1:1 로 뜯어봤다.
4제품을 훑는 [선택 가이드](../vectordb-comparison.md)와 달리, 이 글은 실제로 저울에 올린 두 후보를 깊게 대조한다.

한 줄 요약 — 검색 품질은 사실상 동등하고, 진짜 차이는 **아키텍처 철학(범용 검색엔진 vs 전용 분산 DB)과 기능의 폭**이다.

---

## 출발점이 다르다

- **OpenSearch** — Elasticsearch 계열의 범용 검색·분석 엔진. 원래 텍스트 검색(역색인, BM25)이 본업이고, 여기에 k-NN 플러그인으로 벡터 검색을 얹었다. 벡터는 `knn_vector` 필드 타입으로 들어간다.
- **Milvus** — 처음부터 벡터를 위해 설계된 전용 분산 DB. 컴포넌트를 잘게 쪼개고 저장과 연산을 분리했다.

이 출발점 차이가 아래 모든 차이의 뿌리다.

---

## 아키텍처와 노드 역할

### OpenSearch

- **Master node** — 클러스터 상태·메타 관리(샤드 할당 등). 데이터를 직접 검색하지 않는다.
- **Data node** — 샤드를 보관하고 색인·검색을 실제로 수행. **벡터도 여기 메모리에 올라간다.**
- **Coordinating node** — 요청을 받아 data node 에 분산하고 결과를 합친다.
- 데이터는 인덱스 → 샤드 단위로 나뉘고, 각 data node 가 자기 샤드를 책임진다. 저장과 연산이 같은 노드에 묶여 있다.

### Milvus

저장(storage)과 연산(compute)을 완전히 분리한 게 핵심이다.

- **Proxy** — 요청 진입점(무상태).
- **Coordinator** — 일명 MixCoord, 두뇌 역할. 스케줄링·메타·일관성을 맡고 데이터 메모리는 거의 안 짊어진다.
- **QueryNode** — 영속화된 과거 데이터(sealed segment) 검색. **벡터 메모리의 주력.**
- **StreamingNode** — 최신 인입 데이터(growing segment) 검색.
- **DataNode** — 컴팩션·인덱스 빌드.
- **Storage** — etcd(메타) + Object Storage(벡터 원본) + WAL.

| 관점 | OpenSearch | Milvus |
| --- | --- | --- |
| 설계 | 범용 검색엔진 + 벡터 플러그인 | 전용 벡터 DB |
| 저장·연산 | 같은 노드(data node)에 결합 | 분리(QueryNode 연산 / S3 저장) |
| 메타 관리 | master node | Coordinator + etcd |
| 데이터 단위 | 인덱스/샤드 | collection/partition/segment |

---

## 벡터는 어떤 노드가 메모리에 들고 있나

전환을 검토하며 가장 헷갈렸던 지점이다. 결론은 **둘 다 master/coordinator 가 아니다.**

- OpenSearch — **data node** 가 자기 샤드의 벡터를 메모리(주로 off-heap, faiss/lucene)에 올려 검색한다.
- Milvus — **QueryNode** 가 sealed segment 의 벡터를 메모리에 로드해 검색한다. 평소 원본은 Object Storage(S3)에 있다가 검색을 위해 로드된다.

차이는 **확장 방식**이다. OpenSearch 는 검색 부하가 늘면 data node 를 늘리고 샤드를 리밸런싱한다(저장과 연산이 같이 움직인다). Milvus 는 저장은 그대로 두고 **QueryNode 만 늘려** 검색 메모리·연산을 분산한다. 검색만 따로 키우기는 Milvus 쪽이 깔끔하다.

---

## 인덱스 선택지

| | OpenSearch | Milvus |
| --- | --- | --- |
| HNSW | ◎ (lucene / faiss / nmslib) | ◎ |
| IVF 계열 | ◎ (faiss) | ◎ |
| DiskANN(온디스크) | △ | ◎ |
| GPU 인덱스 | ✗ | ◎ |
| 양자화(PQ/SQ) | ○ | ◎ |

기본 HNSW 는 둘 다 잘 된다. 벌어지는 지점은 **대규모·메모리 제약**일 때다 — DiskANN(그래프를 디스크에 두고 일부만 메모리), GPU 인덱스가 Milvus 에만 있다. 다만 이건 수억 벡터·초고QPS 에서 의미가 크고, 수천만 규모에선 둘 다 HNSW 로 충분하다.

---

## 검색 기능 — RAG 관점

| 기능 | OpenSearch | Milvus |
| --- | --- | --- |
| dense ANN | ◎ | ◎ |
| 하이브리드(키워드+벡터) | ◎ | ◎ |
| 학습형 sparse(SPLADE) | ✗ | ◎ |
| multi-vector | ✗ | ◎ |
| 메타데이터 필터링 | ◎ | ◎ |

둘 다 dense + 키워드(BM25) 하이브리드는 된다. Milvus 만 있는 건 두 가지다. 하나는 **학습형 sparse** — SPLADE 처럼 BM25 를 넘는 신경망 희소 임베딩이다. 다른 하나는 **multi-vector** — 한 컬렉션에 여러 벡터 필드를 두고 함께 검색·reranking 하는 기능이다. 이게 필요 없다면 OpenSearch 로도 충분하고, 필요하다면 Milvus 가 앞선다.

---

## 한국어 처리

한국어는 띄어쓰기만으로 단어가 안 갈려서 형태소 분석이 필수다.

- OpenSearch — `nori` (nori_tokenizer + nori_part_of_speech 필터)
- Milvus — `lindera` + ko-dic(MeCab 한국어 사전) + korean_stop_tags 필터

같은 품사 태그 체계를 쓰기 때문에 설정이 거의 1:1 로 대응한다. 직접 같은 문장을 양쪽에 넣어보면, 조사·어미를 걸러낸 의미 토큰은 사실상 같았다. 오히려 복합명사는 lindera 쪽이 덜 쪼갰다("데이터베이스"를 통째로 vs nori 는 "데이터/베이스").

---

## 검색 품질 — 직접 비교해 봤다

로컬에 Milvus 와 OpenSearch 를 같이 띄우고, 같은 임베딩(bge-m3, 1024차원)과 같은 한국어 데이터(KorQuAD)로 비교했다.

먼저 recall 개념부터. **recall@k** 는 전수 비교로 찾은 진짜 최근접 k 개 중 근사 검색이 실제로 회수한 비율이다. ANN 은 빠른 대신 가끔 진짜 정답을 놓치므로 recall 이 1.0 보다 낮을 수 있다.

결과는 이랬다.

- **dense 검색 정합성** — 같은 임베딩이라 OpenSearch 와 Milvus 의 상위 결과가 약 95% 겹쳤다. 의미 검색 엔진으로서 사실상 동등하다는 뜻이다.
- **하이브리드 recall** — Milvus 하이브리드(dense + BM25, RRF 융합)가 0.99 대로 단일 모드보다 높았다.

즉 검색 품질에서 둘은 우열을 가리기 어렵다. 같은 벡터를 넣으면 같은 결과가 나온다.

---

## 메모리와 비용

벡터를 메모리에 올리는 비용은 양쪽 다 든다. 1,600만 벡터 × 1024차원이면 raw 약 68GB 다.

다만 풀 메모리가 강제는 아니다.

- **양자화** — float32 → int8(SQ, 약 1/4) 또는 PQ(1/8 이상)로 줄인다. recall 을 조금 내주는 대신 메모리를 크게 아낀다.
- **온디스크** — Milvus 는 DiskANN/mmap 으로 벡터를 디스크에 두고 일부만 메모리에 둘 수 있다. OpenSearch 도 디스크 기반 옵션이 있지만 선택지는 Milvus 가 넓다.
- **저QPS 환경** — 검색이 초당 몇 건 수준이면 디스크 기반의 추가 지연을 충분히 감당한다. 굳이 다 메모리에 올릴 이유가 없다.

여기서 중요한 점 — 이 메모리 비용은 OpenSearch 로 운영 중이라면 **이미 내고 있는 비용**이다. Milvus 로 옮긴다고 새로 생기는 게 아니라, 오히려 줄일 선택지가 늘어난다.

---

## 운영과 확장

| 관점 | OpenSearch | Milvus |
| --- | --- | --- |
| 운영 난이도 | 중 (ELK 에 익숙하면 친숙) | 높음 (컴포넌트 다수: etcd·메시지 큐·S3·여러 노드) |
| 확장 | data node 추가 + 샤드 리밸런싱 | 컴포넌트별 독립 확장(QueryNode 만 등) |
| 스키마 변경 | 필드 타입 변경 불가 → 재색인·alias 전환 | 상대적으로 유연 |
| 생태계 | 크고 성숙(ELK) | 큼(LangChain·LlamaIndex 등 LLM 친화) |

OpenSearch 는 이미 쓰던 팀이라면 학습 비용이 거의 없다는 게 강점이다. Milvus 는 분리 구조 덕에 확장은 유연하지만, self-host 하면 컴포넌트가 많아 운영이 무겁다(관리형 상품을 쓰면 이 부담은 상품이 흡수한다).

---

## 언제 무엇을

- **이미 OpenSearch/ELK 를 운영 중이고, 하이브리드(키워드+벡터) 수준이면 충분** → OpenSearch 유지가 합리적. 새 시스템 비용이 없다.
- **학습형 sparse·multi-vector·GPU·대규모 분산 같은 기능이 필요하거나, 벡터를 1급으로 다루고 싶다** → Milvus.
- 수천만 벡터 이하라면 **성능은 변별점이 아니다.** 둘 다 충분하니 기능과 운영으로 고르면 된다.

---

## 정리

- 검색 품질은 같은 임베딩이면 사실상 동등하다(직접 비교 시 dense 결과 약 95% 일치).
- 한국어도 nori ↔ lindera ko-dic 으로 거의 1:1 대응한다.
- 메모리는 OpenSearch 의 data node, Milvus 의 QueryNode 가 담당한다 — master/coordinator 가 아니다.
- 진짜 차이는 **아키텍처 철학(결합 vs 분리)과 기능의 폭(학습형 sparse·multi-vector·GPU)**이다.
- 수천만 규모에선 성능이 아니라 **기능·운영·생태계가 선택을 가른다.**

벡터 DB 일반론과 다른 후보까지 보려면 [벡터 DB 선택 가이드](../vectordb-comparison.md)를, Milvus 내부 동작이 궁금하면 [Milvus 아키텍처 글](./milvus-architecture-and-performance.md)을 참고.

---

## 참고 링크

- [Milvus Architecture Overview](https://milvus.io/docs/architecture_overview.md)
- [OpenSearch k-NN](https://docs.opensearch.org/latest/search-plugins/knn/index/)
- [Milvus vs OpenSearch (Zilliz)](https://zilliz.com/comparison/milvus-vs-opensearch)
- [Milvus Index Explained](https://milvus.io/docs/index-explained.md)
