---
categories: [AI]
tags: [입문]
---

# Vespa 아키텍처 입문 — 왜 강력한데 학습 곡선이 가파른가

[벡터 DB 어떻게 고를까](../vectordb-comparison.md)에서 "Vespa 는 강력하지만 학습 곡선이 가팔라서, 대규모 서빙·복잡한 ML 랭킹이 필요한 게 아니면 과한 선택이 되기 쉽다"라고 짧게 정리했었다. 정확히 뭐가 강력하고 뭐가 가파른지 근거를 파봤다.

결론부터 말하면, Vespa 는 **서버 사이드에서 임의 랭킹 함수와 ML 모델 추론을 인라인 실행하는 유일한 엔진**이다. 그 표현력을 얻는 대가로 스키마·랭킹·클러스터 배치까지 3가지 새 문법을 배워야 한다.

## 컴포넌트 구성 — Milvus 와 Qdrant 사이

Vespa 는 세 종류의 노드로 나뉜다.

- **container node** — 무상태 Java 프로세스. 쿼리를 받아 처리한다.
- **content node** — 데이터를 저장하고 분산 인덱스를 관리한다. 여러 대가 모여 content cluster 를 이룬다.
- **config server** — ZooKeeper 기반 단일 config cluster. 전체 설정을 관리하고, 각 노드의 config sentinel 이 이를 구독해 서비스를 기동·재시작한다.

[Milvus](../milvus/milvus-architecture-and-performance.md#아키텍처--storage-와-compute-를-분리한다)는 proxy·coordinator·query/data/index node 등 최소 7개 마이크로서비스에 etcd·Pulsar·MinIO 외부 의존성까지 필요하다. [Qdrant](../qdrant/qdrant-architecture-and-performance.md)는 단일 바이너리다. Vespa 는 그 중간이다 — 외부 의존성을 강제하지는 않지만(단일 노드에 container·content·config 를 모두 올릴 수 있다), container/content/config 라는 3가지 클러스터 유형 개념은 배워야 한다.

Hacker News 사용자 dathinab 의 표현이 이 구조를 정확히 짚는다.

> "It's more a platform to build complex search systems with, then 'just' a vector database."

## 스키마·설정 — 왜 3가지 새 문법이 필요한가

Vespa 는 `.sd`(schema definition) 파일에서 필드마다 인덱싱 파이프라인을 지정한다.

```
field embedding type tensor<float>(x[768]) {
    indexing: attribute | index
}
```

`indexing: summary | index | attribute` 조합으로 "이 필드를 검색 결과에 보여줄지, 인덱싱할지, 랭킹 계산에 쓸지"를 필드 단위로 세밀하게 정한다. 여기에 랭킹 표현식을 담는 `rank-profile` 블록, 클러스터 배치를 선언하는 `services.xml`(`<nodes count>`, `<redundancy>`, `<resources vcpu/memory/disk>`)까지 더해진다.

Qdrant·Milvus 는 REST/YAML 로 컬렉션 필드 타입과 인덱스 파라미터만 선언하면 끝난다. Vespa 는 (1) 인덱싱 파이프라인 문법, (2) 랭킹 표현식 언어, (3) 클러스터 배치 XML — 이 3가지를 따로 배워야 한다. 표현력과 학습 곡선은 여기서부터 트레이드오프가 시작된다.

## 랭킹 — 서버 사이드에서 ML 모델을 인라인 실행한다

Vespa 랭킹의 핵심은 **2-phase 랭킹**이다.

```mermaid
flowchart LR
    A[전체 매칭 문서] -->|first-phase: 저비용 수식| B[상위 후보 100개]
    B -->|second-phase: 고비용 수식·ML 모델| C[최종 순위]
```

first-phase 가 매칭된 문서 전체를 저비용 수식(BM25, 벡터 거리 등)으로 빠르게 채점하고, second-phase 가 그 상위 후보(기본 100개)만 고비용 수식(XGBoost, ONNX 모델 등)으로 재정렬한다. ONNX 모델은 `onnx-model` 블록에 선언해두면 `onnx(모델명).출력명` 형태로 랭킹 표현식 안에서 직접 참조할 수 있다 — 모델 추론이 랭킹 계산의 한 항이 되는 것이다.

이건 다른 제품에는 없는 방식이다. Qdrant 의 Score Boosting 은 `constant, sum, mult, decay` 같은 규칙 기반 연산만 지원하고 ONNX·커스텀 ML 모델 실행은 없다. Milvus 의 `hybrid_search()`는 `WeightedRanker`/`RRFRanker`만 서버 내부에서 실행하고, [그 외 재정렬은 클라이언트 라이브러리(PyMilvus) 몫](../milvus/milvus-architecture-and-performance.md#multi-vector-와-하이브리드-재정렬)이다. 서버 사이드에서 임의 랭킹 함수와 ML 모델 추론을 실행하는 건 Vespa 뿐이다.

## 텐서 1급 지원 — 스키마 자체가 벡터 연산을 안다

필드를 `tensor<float>(x[128])`(dense) 또는 `tensor<float>(category{})`(sparse mapped) 로 선언하면, 랭킹 표현식에서 `sum`, `reduce`, `join`, `map`, `matmul` 같은 텐서 연산을 직접 쓸 수 있다.

```
sum(query(q_embedding) * attribute(embedding))
```

이 한 줄이 그대로 dot product(코사인 유사도의 핵심 연산)다. multi-vector 는 mixed tensor(예: `tensor<float>(paragraph{}, embedding[768])`, sparse+dense 결합)로 표현한다 — 문서 하나에 문단별 벡터를 여러 개 담아 한 필드로 관리한다.

## 분산·스케일링 — bucket 단위 자동 재분배

문서는 bucket 단위로 자동 관리되고, 수동 샤딩이 필요 없다. bucket을 노드에 배치하는 알고리즘은 공식 문서에 "a variant of the CRUSH algorithm"으로 명시돼 있다 — bucket ID를 시드로 한 pseudo-random weighted election으로 replica 노드를 정한다. 노드를 추가하면 기존 노드 간 이동 없이 신규 노드가 전체 bucket의 평균 `1/n`만 기존 노드들로부터 가져오고, 제거하면 나머지 노드가 부하를 나눠 갖는다.

이 자동 재분배는 갓 나온 기능이 아니다. Vespa 는 2004년 Yahoo 내부에서 개발돼 2017년 오픈소스로 공개, 2023년 독립 분사했다. 공식 자료가 명시하는 프로덕션 규모는 150개 이상 애플리케이션(Yahoo·Spotify·Perplexity·Vinted 등), 초당 80만 건 이상 쿼리, 전 세계 약 10억 사용자다. Yahoo 내부 사례로는 광고 서빙 초당 최대 14만 건·하루 30억 건, Flickr 수십억 이미지에 초당 수백 쿼리 처리 실적이 공개돼 있다. 자체 벤치마크(SPACEV-1B, 10억 벡터×100차원)에서는 72 vCPU 단일 노드로 90% recall 근사 검색 시 지연 4ms·코어당 약 250 QPS를 기록했다.

> 개별 회사의 구체 수치(예: 특정 기업의 벡터 수 언급)는 제3자 블로그 출처가 많아 이 글에서는 공식 자료로 확인된 수치만 남겼다 — 나머지는 확인 필요로 남긴다.

## 설치·운영 — 실제로 얼마나 가파른가

공식 quick-start 는 9단계다.

1. Docker/Podman 메모리 확인
2. `brew install vespa-cli`
3. `vespa config set target local`
4. `vespaengine/vespa` 이미지로 컨테이너 기동(포트 8080/19071)
5. `vespa clone`으로 샘플 앱 복제
6. `vespa deploy --wait 300`
7. `vespa feed`로 문서 입력
8. 쿼리 실행
9. ID로 문서 조회

[Qdrant](../qdrant/qdrant-architecture-and-performance.md)는 `docker run` 한 줄 + 클라이언트 초기화 + 컬렉션 생성 + 쿼리, 총 5단계로 끝난다. 별도 스키마 파일이나 CLI 설치가 필요 없다.

커뮤니티 반응도 이 격차를 그대로 보여준다. Elsevier Labs 의 Sujit Pal(Vespa 공식 블로그 게스트 포스트)은 이렇게 썼다.

> "I had been put off by what seemed like a pretty steep learning curve compared with Solr and Elasticsearch... the steepness is not an illusion, but it is justified, because Vespa offers many capabilities and customization opportunities."

## 정리

- **왜 강력한가** — 서버 사이드에서 임의 랭킹 표현식과 ONNX/XGBoost 모델을 2-phase 로 인라인 실행하는 유일한 엔진이다. 텐서가 스키마 1급 타입이라 dot product·multi-vector 연산을 표현식 그대로 쓴다. Yahoo 기원의 수백억 문서·초당 수십만 쿼리급 프로덕션 실적이 공개돼 있다.
- **왜 학습 곡선이 가파른가** — 인덱싱 파이프라인·랭킹 표현식 언어·클러스터 배치 XML, 3가지 새 문법을 익혀야 하고 quick-start 도 9단계다. "단순 벡터 DB가 아니라 검색 시스템 구축 플랫폼"이라는 HN 커뮤니티 평가가 이 지점을 정확히 짚는다.
- 그래서 [벡터 DB 어떻게 고를까](../vectordb-comparison.md)의 결론대로, 대규모 서빙이나 복잡한 ML 랭킹이 필요하지 않다면 이 학습 비용을 감당할 이유가 없다.

## 참고 링크

- [Vespa Overview](https://docs.vespa.ai/en/overview.html)
- [Vespa Config Sentinel](https://docs.vespa.ai/en/config-sentinel.html)
- [Vespa Schemas](https://docs.vespa.ai/en/schemas.html)
- [Vespa services.xml Reference](https://docs.vespa.ai/en/reference/services.html)
- [Vespa Ranking](https://docs.vespa.ai/en/ranking.html)
- [Vespa Phased Ranking](https://docs.vespa.ai/en/phased-ranking.html)
- [Vespa ONNX Ranking](https://docs.vespa.ai/en/ranking/onnx.html)
- [Vespa Tensor User Guide](https://docs.vespa.ai/en/tensor-user-guide.html)
- [Vespa Elasticity](https://docs.vespa.ai/en/elasticity.html)
- [Vespa Buckets](https://docs.vespa.ai/en/content/buckets.html)
- [Vespa Quick Start](https://docs.vespa.ai/en/vespa-quick-start.html)
- [Why Vespa](https://vespa.ai/why-vespa/)
- [Open-Sourcing Vespa](https://blog.vespa.ai/open-sourcing-vespa-yahoos-big-data-processing/)
- [Billion-scale kNN, Part Two](https://blog.vespa.ai/billion-scale-knn-part-two/)
- [How I Learned Vespa by Thinking in Solr](https://blog.vespa.ai/how-i-learned-vespa-by-thinking-in-solr/)
- [Hacker News 스레드](https://news.ycombinator.com/item?id=37764489)
