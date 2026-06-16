# [초안] RAG 환각 제어 — grounding 재주입, sourceQuote 검증, 배치 정합성, bulk 색인

RAG(Retrieval-Augmented Generation)를 데모에서 제품으로 올릴 때 가장 자주 무너지는 지점이 **환각**(hallucination)이다. 검색은 잘 되는데 LLM이 검색되지 않은 사실을 지어내거나, 검색된 문서에 없는 인용을 만들어 붙이거나, 색인이 원본과 어긋나서 "맞는 답변인데 근거가 옛 문서"인 상황이 생긴다.

이 문서는 검색 품질 튜닝(Hybrid Search, Reranking)과는 다른 레이어인 **생성 단계와 색인 정합성에서의 환각 제어**를 다룬다. 검색 자체의 품질은 [OpenSearch RAG 검색 품질 높이기](../../database/opensearch/rag-search-quality.md)에서, 색인 배치의 전체 구현 흐름은 [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md)에서 다루므로, 여기서는 그 위에 얹는 **신뢰 레이어**에 집중한다.

---

## 왜 이 주제가 중요한가

비결정적인 LLM 위에 제품을 올린다는 것은, 모델이 틀릴 수 있다는 전제를 깔고 **틀린 출력이 사용자에게 도달하기 전에 거르는 구조**를 만든다는 뜻이다. 검색 정확도를 99%로 올려도 마지막 생성 단계에서 모델이 근거 없는 문장을 한 줄 끼워 넣으면 답변 전체의 신뢰가 깨진다.

RAG 환각은 크게 세 종류로 나뉜다.

- **검색 실패형** — 애초에 관련 문서가 검색되지 않아 모델이 빈손으로 답을 지어낸다.
- **불충실형**(unfaithful) — 문서는 검색됐는데 모델이 그 내용을 벗어나 답한다. 가장 잡기 어렵다.
- **정합성 붕괴형** — 검색·생성은 정상인데 색인된 문서가 원본과 어긋나(삭제된 문서, 옛 버전) 사실상 틀린 근거로 답한다.

세 종류는 막는 위치가 다르다. 검색 실패형은 검색 단계에서, 불충실형은 생성 전후에서, 정합성 붕괴형은 색인 파이프라인에서 막는다. 한 군데만 막으면 나머지가 새므로, 네 가지 기법을 레이어로 겹쳐 쌓는다.

---

## grounding 재주입 — 모델을 근거 안에 가둔다

grounding은 모델이 답변을 만들 때 참고해야 할 **근거 문맥을 명시적으로 묶어 주입**하는 것이다. 단순히 검색 결과를 프롬프트에 붙이는 것을 넘어서, "이 문맥 밖의 지식은 쓰지 말라"는 제약과 "근거를 못 찾으면 모른다고 답하라"는 탈출구를 함께 건다.

재주입(re-injection)이라고 부르는 이유는, 한 번 붙이고 끝이 아니라 **멀티턴이나 도구 호출 사이마다 grounding을 다시 박아 넣기** 때문이다. 대화가 길어지면 앞서 주입한 문맥이 컨텍스트 윈도우 뒤로 밀리거나, 모델이 자기 이전 답변을 사실처럼 재인용하면서 근거가 흐려진다. 매 생성 직전에 검색 결과를 다시 주입하면 모델의 "기준점"이 항상 최신 근거로 리셋된다.

### 나쁜 예 — 근거를 그냥 붙이기만 함

```text
다음은 참고 문서입니다:
{검색된 문서 3개를 이어붙인 긴 텍스트}

질문: 환불 정책이 어떻게 되나요?
```

이 구조는 모델이 문서를 "참고"만 하고 자기 사전지식으로 답을 보강하는 것을 막지 못한다. 근거 밖 문장이 섞여도 탐지할 방법이 없다.

### 개선 예 — 제약 + 인용 강제 + 탈출구

```text
당신은 아래 [근거] 안의 정보만 사용해 답한다.
[근거]에 없는 내용은 추측하지 않는다.
근거가 부족하면 정확히 "제공된 문서에서 확인할 수 없습니다"라고 답한다.
모든 핵심 주장 뒤에 근거의 [doc_id]를 붙인다.

[근거]
[doc_1] 환불은 결제일로부터 7일 이내 가능하다.
[doc_2] 디지털 상품은 다운로드 시작 시 환불이 제한된다.

질문: 환불 정책이 어떻게 되나요?
```

핵심은 세 가지다.

- **닫힌 도메인 지시** — "근거 안의 정보만" 제약으로 외부 지식 사용을 억제한다.
- **명시적 abstention** — 모른다고 답할 정확한 문구를 정해 둔다. 이게 없으면 모델은 빈칸을 지어내서 채운다.
- **doc_id 인용 강제** — 다음 단계인 sourceQuote 검증의 입력이 된다. 인용이 없으면 검증할 대상도 없다.

grounding은 환각을 "줄이지만" 없애지는 못한다. 모델은 여전히 제약을 어길 수 있다. 그래서 출력을 믿지 말고 **검증 단계**를 뒤에 둔다.

---

## sourceQuote 검증 — 인용이 진짜 원문에 있는가

sourceQuote 검증은 모델이 답변에 붙인 인용·근거가 **실제 검색된 문서 안에 존재하는지 기계적으로 확인**하는 단계다. grounding이 "근거를 잘 주입하는" 입력 측 방어라면, sourceQuote 검증은 "출력이 근거를 지켰는지" 확인하는 출력 측 방어다.

전략은 두 단계로 나뉜다.

### 구조화된 인용 추출

모델에게 자유 텍스트가 아니라 **인용 가능한 구조**로 출력하게 한다.

```json
{
  "answer": "환불은 결제일로부터 7일 이내 가능합니다.",
  "claims": [
    {
      "statement": "환불은 결제일로부터 7일 이내 가능하다",
      "source_doc_id": "doc_1",
      "source_quote": "환불은 결제일로부터 7일 이내 가능하다"
    }
  ]
}
```

`source_quote`는 모델이 "이 문장이 근거 문서에 있다"고 주장하는 원문 조각이다. 이제 이게 거짓인지 검사할 수 있다.

### 원문 대조 검증

각 `source_quote`를 해당 `source_doc_id`의 원본 텍스트와 대조한다. 완전 일치는 너무 빡빡하므로 보통 정규화 후 부분 문자열 매칭이나 임베딩 유사도로 판정한다.

```java
public record QuoteCheck(String docId, String quote, boolean grounded, double score) {}

public QuoteCheck verify(String docId, String quote, Map<String, String> sourceDocs) {
    String source = sourceDocs.get(docId);
    if (source == null) {
        // 모델이 검색되지도 않은 문서를 인용 -> 명백한 환각
        return new QuoteCheck(docId, quote, false, 0.0);
    }
    String normSource = normalize(source);
    String normQuote = normalize(quote);

    if (normSource.contains(normQuote)) {
        return new QuoteCheck(docId, quote, true, 1.0);   // 원문에 그대로 존재
    }
    double sim = embeddingSimilarity(normQuote, normSource);   // 의역 인용 대비
    return new QuoteCheck(docId, quote, sim >= 0.85, sim);
}

private String normalize(String s) {
    return s.replaceAll("\\s+", " ").trim().toLowerCase();
}
```

검증 결과로 무엇을 할지는 제품 성격에 따라 다르다.

- **grounded = false인 claim을 답변에서 제거**하고 나머지만 사용자에게 보여준다.
- claim 다수가 실패하면 **답변 전체를 폐기하고 재생성**하거나 abstention 메시지로 대체한다.
- 실패율을 지표로 쌓아 **모델·프롬프트 회귀를 감지**한다.

이 단계는 LLM-as-a-judge로 대체하거나 보강할 수도 있다. judge를 언제 믿고 언제 의심할지는 [Agentic Workflow 평가와 Risk Gate 설계](../../ai/agent/agentic-workflow-evaluation-risk-gate.md)에서 다룬 신뢰 기준과 같은 맥락이다. 핵심 원칙은 같다. **모델 출력을 또 다른 모델로만 검증하면 두 모델이 같은 방식으로 틀릴 때 못 잡는다.** 문자열 대조 같은 결정적 검증을 1차로 깔고, 의역·요약처럼 결정적으로 못 잡는 부분만 judge에 위임한다.

---

## RAG 배치 정합성 — 색인이 원본을 따라가는가

검색과 생성이 완벽해도 **색인된 문서가 원본과 어긋나면** 모델은 "옛 사실"을 충실하게 인용한다. 충실하지만 틀린 답이다. 이건 프롬프트로 못 막고 색인 파이프라인에서 막아야 한다.

정합성이 깨지는 전형적 경로는 다음과 같다.

- **삭제 누락** — 원본에서 지운 문서가 색인에는 남아 검색된다.
- **갱신 지연** — 원본은 바뀌었는데 임베딩 재계산이 밀려 옛 벡터가 검색된다.
- **부분 실패** — 배치 도중 임베딩 API가 실패해 일부 문서만 갱신되고 나머지는 옛 상태로 남는다.
- **중복 색인** — 재시도 과정에서 같은 문서가 두 번 들어가 검색 결과를 오염시킨다.

대응 설계의 핵심은 **원본을 진실의 단일 출처로 두고 색인을 그 파생으로 취급**하는 것이다.

### 콘텐츠 해시로 변경 감지

문서 본문의 해시를 메타데이터로 함께 색인하면, 다음 배치에서 해시가 같은 문서는 임베딩을 다시 계산하지 않고 건너뛴다. 비용을 줄이면서 갱신 누락도 줄인다.

```java
String contentHash = sha256(document.body());
if (contentHash.equals(indexedHashOf(document.id()))) {
    return;   // 변경 없음 -> 재색인 스킵
}
// 변경됨 -> 임베딩 재계산 후 같은 doc_id로 덮어쓰기(upsert)
```

### 삭제 동기화

원본에 없는데 색인에 있는 문서를 주기적으로 청소한다. 매 배치마다 "이번에 본 doc_id 집합"을 모아 두고, 색인에는 있지만 그 집합에 없는 문서를 삭제하거나 soft-delete 플래그를 세운다.

### 멱등 upsert

문서 ID를 결정적으로 만들어(원본 ID 기반) 같은 문서는 항상 같은 `_id`로 들어가게 한다. 재시도해도 새 문서가 추가되지 않고 덮어써지므로 중복이 원천 차단된다. 배치의 재시작 가능성과 청크 처리 설계는 [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md)에서 이어진다.

---

## OpenSearch bulk indexing — 대량 색인을 안전하게

수만\~수십만 문서를 한 건씩 색인하면 네트워크 왕복 비용이 폭발한다. OpenSearch는 `_bulk` API로 여러 작업을 한 요청에 묶는다. 다만 bulk는 빠른 만큼 **부분 실패와 정합성 함정**이 있어 그냥 쓰면 위험하다.

### bulk 요청 형태

bulk는 액션 메타 줄과 본문 줄을 번갈아 보내는 NDJSON 포맷이다.

```bash
curl -s -X POST "localhost:9200/_bulk" \
  -H 'Content-Type: application/x-ndjson' \
  --data-binary @- <<'EOF'
{ "index": { "_index": "docs", "_id": "doc_1" } }
{ "title": "환불 정책", "body": "환불은 7일 이내", "embedding": [0.12, 0.04], "content_hash": "a1b2" }
{ "index": { "_index": "docs", "_id": "doc_2" } }
{ "title": "디지털 상품", "body": "다운로드 시 제한", "embedding": [0.31, 0.22], "content_hash": "c3d4" }
EOF
```

`_id`를 명시하면 멱등 upsert가 되어 재시도 시 중복이 생기지 않는다. ID를 비우면 OpenSearch가 임의 ID를 부여해 재시도마다 새 문서가 쌓이므로 정합성이 깨진다.

### 부분 실패를 반드시 확인한다

bulk는 요청 단위로 200을 반환해도 **개별 항목이 실패할 수 있다.** 응답의 `errors` 플래그와 각 항목 status를 검사하지 않으면 일부 문서가 누락된 채로 "성공"으로 넘어간다.

```java
BulkResponse resp = client.bulk(bulkRequest);
if (resp.errors()) {
    for (BulkResponseItem item : resp.items()) {
        if (item.error() != null) {
            log.warn("bulk item 실패 docId={} reason={}", item.id(), item.error().reason());
            retryQueue.add(item.id());   // 실패 항목만 재시도 큐로
        }
    }
}
```

### 배치 크기와 refresh 튜닝

- **배치 크기** — 한 bulk에 너무 많이 담으면 메모리·타임아웃 위험이 커진다. 보통 문서당 크기에 따라 500\~5000건, 또는 5\~15MB를 한 묶음으로 잡고 실측으로 조정한다.
- **refresh 끄기** — 대량 색인 중에는 `refresh_interval`을 `-1`로 두어 세그먼트 생성 비용을 줄이고, 색인이 끝난 뒤 한 번 refresh 한다. 색인 중 검색 가시성과 처리량의 trade-off다. 세부 동작은 [refresh interval](../../database/opensearch/refresh-interval.md) 참고.

```bash
# 색인 시작 전: refresh 비활성화
curl -X PUT "localhost:9200/docs/_settings" -H 'Content-Type: application/json' -d'
{ "index": { "refresh_interval": "-1" } }'

# 대량 bulk 색인 ...

# 색인 종료 후: 원복 + 강제 refresh
curl -X PUT "localhost:9200/docs/_settings" -H 'Content-Type: application/json' -d'
{ "index": { "refresh_interval": "1s" } }'
curl -X POST "localhost:9200/docs/_refresh"
```

---

## 로컬 실습 환경

도커로 단일 노드 OpenSearch를 띄우고 위 흐름을 직접 돌려 본다.

```bash
docker run -d --name opensearch-lab \
  -p 9200:9200 -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "DISABLE_SECURITY_PLUGIN=true" \
  opensearchproject/opensearch:2.13.0

# 헬스 체크
curl -s "localhost:9200/_cluster/health?pretty"

# 색인 생성 (knn 활성화 + content_hash 매핑)
curl -X PUT "localhost:9200/docs" -H 'Content-Type: application/json' -d'
{
  "settings": { "index": { "knn": true, "refresh_interval": "1s" } },
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "body": { "type": "text" },
      "content_hash": { "type": "keyword" },
      "embedding": { "type": "knn_vector", "dimension": 2 }
    }
  }
}'
```

이 위에서 (1) bulk로 문서를 넣고, (2) 같은 `_id`로 다시 넣어 중복이 안 생기는지 확인하고, (3) content_hash가 같을 때 스킵 로직을 태우고, (4) 삭제 동기화로 사라진 문서가 검색에서 빠지는지 본다.

---

## 점검 질문 (면접·복습용)

특정 조직 맥락이 아니라 일반 RAG 제품 설계 관점의 질문이다.

- RAG에서 환각을 검색·생성·색인 세 레이어로 나눠 막아야 하는 이유는 무엇인가. 한 레이어만 막으면 어디가 새는가.
- grounding을 매 턴 재주입하는 이유는 무엇인가. 한 번만 주입하면 어떤 문제가 생기는가.
- 모델이 "모른다"고 답하게 만드는 abstention 문구가 왜 환각 제어에 중요한가.
- sourceQuote 검증을 LLM-as-a-judge로만 하지 않고 문자열 대조를 1차로 까는 이유는 무엇인가.
- 검색과 생성이 정상인데도 답이 틀릴 수 있는 색인 정합성 붕괴 시나리오를 설명해 보라.
- bulk 색인에서 `_id`를 명시하지 않으면 재시도 시 무슨 일이 생기는가.
- bulk 응답이 200인데도 일부 문서가 누락될 수 있는 이유와, 그것을 탐지하는 방법은 무엇인가.
- 대량 색인 중 `refresh_interval`을 끄는 이유와 그 trade-off는 무엇인가.

---

## 체크리스트

- [ ] 생성 프롬프트에 닫힌 도메인 제약 + abstention 문구 + 인용 강제가 모두 들어가 있는가.
- [ ] 멀티턴·도구 호출 사이에 grounding을 재주입하는가.
- [ ] 모델 출력을 구조화(claim + source_quote)해서 검증 가능한 형태로 받는가.
- [ ] source_quote를 원문과 결정적으로 대조하고, 실패한 claim을 제거/재생성하는가.
- [ ] 검색되지 않은 doc_id 인용을 명백한 환각으로 즉시 걸러내는가.
- [ ] 콘텐츠 해시로 변경 없는 문서의 재색인을 스킵하는가.
- [ ] 원본에서 삭제된 문서를 색인에서 동기화 제거하는가.
- [ ] 문서 `_id`를 결정적으로 만들어 멱등 upsert를 보장하는가.
- [ ] bulk 응답의 `errors`와 항목별 status를 검사하고 실패 항목만 재시도하는가.
- [ ] 대량 색인 시 refresh를 끄고, 종료 후 원복 + 강제 refresh 하는가.

---

## 관련 문서

- [OpenSearch RAG 검색 품질 높이기](../../database/opensearch/rag-search-quality.md) — Hybrid Search, Reranking, Sentence Window (검색 레이어)
- [Confluence 벡터 색인 배치](../../task/ai-service-team/rag-vector-search-batch.md) — Spring Batch 색인 파이프라인 구현
- [Agentic Workflow 평가와 Risk Gate 설계](../../ai/agent/agentic-workflow-evaluation-risk-gate.md) — LLM-as-a-judge 신뢰 기준, risk gate
- [refresh interval](../../database/opensearch/refresh-interval.md) — 색인 가시성과 처리량 trade-off
