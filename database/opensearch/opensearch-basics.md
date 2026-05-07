# [초안] OpenSearch 기초: 검색 엔진을 백엔드 관점에서 다루기

## 왜 지금 이 주제인가

관계형 DB만으로 운영하다가 검색 기능이 본격적으로 필요해지는 순간이 꼭 온다. 상품명 부분 일치, 오타 허용, 형태소 분석, 한/영 혼용, 가중치 기반 정렬, 집계(aggregation), 파사드 필터. 이런 요구가 쌓이면 `LIKE '%...%'` + 인덱스는 금세 깨진다. `FULLTEXT` 인덱스를 동원해도 한국어 형태소와 다국어 처리, 실시간 색인 토폴로지, 분산 집계까지 가면 MySQL 단독으로는 무겁다. CJ OliveYoung Wellness 플랫폼처럼 상품 카탈로그와 검색/추천/로그 분석이 동시에 돌아가는 도메인이라면 OpenSearch(또는 Elasticsearch) 계열은 사실상 표준 선택지다.

OpenSearch는 Elasticsearch 7.10 포크에서 출발한 Apache 2.0 라이선스의 분산 검색/분석 엔진이다. 이 문서는 OpenSearch를 "처음 운영해야 하는 Java 백엔드 엔지니어"가 필요한 최소 분량을 익히는 것을 목표로 한다. 운영 레벨 튜닝이나 ML 플러그인은 다른 문서로 미루고, 이 문서는 색인 설계 → 매핑 → 쿼리 DSL → Java 클라이언트 연동 → 운영 주의점까지의 직선 경로를 다룬다.

관련 개념은 `database/` 폴더의 MySQL 인덱스 문서, `architecture/`의 비동기 이벤트 반영 문서와 겹치는 부분이 있으므로, 아래에서는 중복 설명을 피하고 필요한 지점에 짧게 연결한다.

## 핵심 개념: 어떤 모델로 데이터를 다루는가

OpenSearch의 데이터 모델은 RDBMS와 다르게 "문서(document) 중심"이다. 용어를 RDBMS에 대응시키면 대략 이렇다.

- 인덱스(index) ≈ 테이블
- 문서(document) ≈ 행(row), JSON 한 덩어리
- 필드(field) ≈ 컬럼, 단 동적 타입 판별이 가능
- 샤드(shard) ≈ 인덱스를 물리적으로 나눈 단위, 각 샤드는 Lucene 인덱스 하나
- 레플리카(replica) ≈ 샤드 복제본, 읽기 성능과 장애 대응 목적
- 매핑(mapping) ≈ 스키마 정의
- 애널라이저(analyzer) ≈ 텍스트를 토큰으로 분해하는 파이프라인

여기서 가장 중요한 개념 두 가지는 역색인(inverted index)과 애널라이저다.

### 역색인

RDBMS의 B+Tree 인덱스는 "컬럼 값 → 행 위치"로 정렬되지만, 역색인은 "토큰 → 해당 토큰이 등장한 문서 목록"으로 저장된다. 예를 들어 `"아이오페 에어쿠션 N 커버"`라는 상품명이 색인될 때, 애널라이저가 `[아이오페, 에어쿠션, 커버]`로 토큰화하면 각 토큰마다 문서 ID 포스팅 리스트가 만들어진다. 검색어가 "에어쿠션"으로 들어오면 해당 포스팅 리스트만 조회하면 끝이라 빠르다.

이 구조 때문에 OpenSearch는 "텍스트가 어떻게 토큰화됐는가"에 성능과 정확도 둘 다 지배당한다. 즉, 스키마 설계보다 애널라이저 설계가 먼저다.

### 애널라이저 파이프라인

애널라이저는 세 단계로 구성된다.

1. Character filter — 원문 문자열 치환 (HTML 태그 제거, 특수문자 정규화)
2. Tokenizer — 토큰 단위 분리 (공백, n-gram, 형태소)
3. Token filter — 토큰 후처리 (소문자화, 동의어 확장, stopword 제거)

한국어 검색은 기본 `standard` 토크나이저로는 거의 쓸 수 없고, Nori 플러그인(공식 한국어 형태소 분석기) 또는 은전한닢, 맥락에 따라 `ngram`/`edge_ngram`을 조합해야 한다.

### 텍스트 필드 vs keyword 필드

같은 문자열이라도 두 가지 목적이 섞인다.

- `text`: 애널라이저로 토큰화되어 **검색**에 사용. 정렬/집계 비효율.
- `keyword`: 원문 그대로 한 토큰으로 저장. **정확 일치, 정렬, 집계**에 사용.

그래서 상품명 같은 필드는 관례적으로 `text`로 매핑하고, 하위 필드 `name.keyword`를 같이 둔다. 이걸 multi-field라고 부른다.

## 백엔드 실무에서의 위치

Wellness/이커머스 도메인에서 OpenSearch를 얹는 방식은 보통 이렇게 자리 잡는다.

- 원장(System of Record)은 RDBMS. 주문, 결제, 정산은 RDBMS가 진실의 원천.
- 검색 인덱스는 **복제본 성격**. 상품, 카탈로그, 브랜드, 리뷰 같은 읽기 많은 데이터의 검색/집계용 사본.
- 반영 경로는 CDC(Debezium 등) + Kafka, 또는 애플리케이션이 도메인 이벤트 발행 → 소비자 서비스가 색인 업데이트.
- 동기식 더블라이트(MySQL 저장 직후 바로 OpenSearch 호출)는 실패 시 일관성 복구가 어려워서 되도록 피한다.

즉, OpenSearch는 **"쓰기는 느슨하고 읽기는 최적"**인 파이프라인의 끝단이다. 여기서 나오는 인터뷰 질문의 90%는 "어떻게 일관성을 맞췄는가", "재색인 전략은 무엇인가", "검색 품질 A/B를 어떻게 잡았는가"다.

## 인덱스 설계: 처음 만드는 매핑

첫 인덱스를 만들 때 다음을 명시적으로 결정해야 한다.

- 샤드 수: 한 번 정하면 재색인 없이는 바꿀 수 없다. 단일 상품 카탈로그처럼 규모가 아직 작다면 primary 1~3, replica 1 정도로 시작.
- 매핑: dynamic mapping에 전부 맡기지 말고, 핵심 필드는 명시한다.
- 애널라이저: 한국어 필드에는 반드시 지정.
- 별칭(alias): 운영 인덱스는 반드시 alias 뒤에 둔다. 재색인 시 무중단 전환의 유일한 경로다.

예시 매핑:

```json
PUT products-v1
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "ko_analyzer": {
          "type": "custom",
          "tokenizer": "nori_tokenizer",
          "filter": ["lowercase", "nori_part_of_speech"]
        },
        "ko_ngram_analyzer": {
          "type": "custom",
          "tokenizer": "ngram_tokenizer",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "ngram_tokenizer": {
          "type": "ngram",
          "min_gram": 2,
          "max_gram": 3,
          "token_chars": ["letter", "digit"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "productId":   { "type": "keyword" },
      "name":        {
        "type": "text",
        "analyzer": "ko_analyzer",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 },
          "ngram":   { "type": "text", "analyzer": "ko_ngram_analyzer" }
        }
      },
      "brand":       { "type": "keyword" },
      "categoryPath":{ "type": "keyword" },
      "price":       { "type": "integer" },
      "tags":        { "type": "keyword" },
      "createdAt":   { "type": "date" },
      "stockQty":    { "type": "integer" },
      "isActive":    { "type": "boolean" }
    }
  }
}

POST _aliases
{
  "actions": [
    { "add": { "index": "products-v1", "alias": "products" } }
  ]
}
```

여기서 `name.ngram`을 둔 이유는 "크러쉬" 같은 짧은 부분 일치 검색을 보완하기 위해서다. Nori는 형태소 단위라 "크"나 "크러" 검색에서 미끄러질 수 있어 n-gram 서브필드를 병행한다.

## 쿼리 DSL: 꼭 알아야 할 네 가지

### 1) match — 기본 풀텍스트 검색

```json
GET products/_search
{
  "query": {
    "match": {
      "name": { "query": "에어쿠션 N 커버", "operator": "and" }
    }
  }
}
```

`operator: and`는 토큰 전부가 포함돼야 매칭된다는 뜻. 사용자가 긴 검색어를 넣을 때 상위 정확도를 올리려면 `minimum_should_match`를 튜닝한다.

### 2) term / terms — 정확 일치

```json
GET products/_search
{
  "query": {
    "bool": {
      "filter": [
        { "term":  { "brand": "아이오페" } },
        { "terms": { "categoryPath": ["뷰티>베이스메이크업>쿠션"] } },
        { "term":  { "isActive": true } }
      ]
    }
  }
}
```

`filter` 절은 점수 계산을 생략하고 캐시되기 때문에 카테고리/브랜드 파사드처럼 반복되는 조건은 반드시 여기로.

### 3) bool — must / should / filter / must_not 조합

```json
GET products/_search
{
  "query": {
    "bool": {
      "must":   [{ "match": { "name": "쿠션" } }],
      "should": [{ "match": { "name.ngram": "에어쿠" } }],
      "filter": [
        { "term":  { "isActive": true } },
        { "range": { "price": { "gte": 10000, "lte": 50000 } } }
      ],
      "must_not": [{ "term": { "brand": "블랙리스트브랜드" } }]
    }
  }
}
```

점수에 영향을 주는 건 `must`와 `should`, 영향을 주지 않는 건 `filter`와 `must_not`. 이 구분은 성능과 랭킹 품질에 직결된다.

### 4) aggregation — 파사드, 통계

```json
GET products/_search
{
  "size": 0,
  "aggs": {
    "by_brand": {
      "terms": { "field": "brand", "size": 20 }
    },
    "price_stats": {
      "stats": { "field": "price" }
    }
  }
}
```

`size: 0`으로 본문 검색 결과는 비우고 집계만 받는 패턴이 실무에서 가장 흔하다. 집계 필드는 반드시 `keyword`나 숫자형이어야 한다는 점을 잊지 말 것.

## Java 백엔드 연동: Spring Boot 기준

OpenSearch는 공식적으로 두 개의 Java 클라이언트를 제공한다.

- `opensearch-java`(권장) — 타입 세이프, 빌더 기반
- `opensearch-rest-high-level-client`(레거시) — Elasticsearch 7.x에서 포크된 것

신규 프로젝트라면 `opensearch-java`가 정답이다. Spring Data OpenSearch는 CRUD 편의는 좋지만, 매핑/쿼리 제어가 약해지기 쉬워 검색 품질이 중요한 서비스에서는 로우레벨 클라이언트를 쓰는 편이 안전하다.

최소 Bean 설정:

```java
@Configuration
public class OpenSearchConfig {

    @Bean
    public OpenSearchClient openSearchClient() {
        HttpHost host = new HttpHost("localhost", 9200, "http");
        RestClient restClient = RestClient.builder(host).build();
        OpenSearchTransport transport =
            new RestClientTransport(restClient, new JacksonJsonpMapper());
        return new OpenSearchClient(transport);
    }
}
```

간단한 색인/검색 서비스:

```java
@Service
@RequiredArgsConstructor
public class ProductSearchService {

    private final OpenSearchClient client;
    private static final String ALIAS = "products";

    public void index(Product product) throws IOException {
        client.index(b -> b
            .index(ALIAS)
            .id(product.getId())
            .document(product)
        );
    }

    public List<Product> searchByName(String keyword, int from, int size) throws IOException {
        SearchResponse<Product> resp = client.search(s -> s
            .index(ALIAS)
            .from(from)
            .size(size)
            .query(q -> q
                .bool(b -> b
                    .must(m -> m.match(mm -> mm.field("name").query(FieldValue.of(keyword))))
                    .filter(f -> f.term(t -> t.field("isActive").value(FieldValue.of(true))))
                )
            ),
            Product.class);

        return resp.hits().hits().stream()
            .map(Hit::source)
            .filter(Objects::nonNull)
            .toList();
    }
}
```

실제 서비스 코드에서 주의할 지점은 다음과 같다.

- 단건 `index` API는 실시간성은 좋지만 대량 적재에는 부적합. 배치 시 `BulkRequest` 사용.
- `refresh=wait_for`를 남용하면 처리량이 크게 떨어진다. 실시간성이 꼭 필요한 경로만 선택적으로.
- 검색 결과 DTO와 색인 DTO를 분리. 색인 포맷은 내부 표현이고, API 응답은 변동성이 크다.

## 안 좋은 예 vs 개선된 예

### 예 1: 매핑 없이 dynamic에 의존

```java
// BAD — 필드가 들어올 때마다 동적 타입 추론
product.setPrice("10000");    // 문자열로 들어감
product.setStockQty("0");     // 문자열로 들어감

// 결과: price가 text로 매핑되어 range 쿼리 불가,
// 이후 integer로 재매핑하려면 reindex 필요
```

개선:

```java
// GOOD — 명시적 DTO + 매핑 사전 정의
@Data
public class ProductDoc {
    private String productId;
    private String name;
    private Integer price;
    private Integer stockQty;
    private boolean isActive;
    private Instant createdAt;
}
```

인덱스 생성 단계에서 숫자형/불리언은 반드시 명시해야 런타임에 예기치 않은 매핑 폭발이 안 생긴다.

### 예 2: 정렬/집계를 text 필드에 시도

```json
// BAD — text는 fielddata가 꺼져 있어 기본적으로 정렬 불가
"sort": [{ "name": "asc" }]
```

개선:

```json
// GOOD — 하위 keyword 필드를 정렬 대상으로
"sort": [{ "name.keyword": "asc" }]
```

### 예 3: 샤드 수를 과하게 잡고 시작

초기 트래픽이 작은데 샤드를 20개로 잡으면 샤드당 데이터가 너무 적어지고, 각 검색 요청이 모든 샤드에 팬아웃되면서 오히려 레이턴시가 올라간다. 경험칙: **샤드 하나당 10~40GB**, 총 문서 수와 쓰기 속도를 기준으로 계산. 애매하면 작게 시작하고 reindex로 늘리는 편이 안전하다.

### 예 4: 재색인 없이 인덱스를 직접 교체

```bash
# BAD
DELETE products
PUT products { ...새 매핑... }
# 서비스 다운타임 발생
```

개선:

```bash
# GOOD
PUT products-v2 { ...새 매핑... }
POST _reindex { "source": {"index":"products-v1"}, "dest": {"index":"products-v2"} }
POST _aliases
{
  "actions": [
    { "remove": { "index": "products-v1", "alias": "products" } },
    { "add":    { "index": "products-v2", "alias": "products" } }
  ]
}
```

alias 스위칭은 원자적으로 수행된다. 무중단 재색인의 표준 패턴.

## 로컬 실습 환경

Docker Compose로 OpenSearch 2.x + 대시보드를 띄운다. 개발 환경에서는 보안 플러그인을 끄는 게 편하다.

```yaml
# docker-compose.yml
version: "3.8"
services:
  opensearch:
    image: opensearchproject/opensearch:2.11.1
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
    ports:
      - "9200:9200"
  dashboards:
    image: opensearchproject/opensearch-dashboards:2.11.1
    environment:
      - OPENSEARCH_HOSTS=http://opensearch:9200
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    ports:
      - "5601:5601"
```

기동 확인:

```bash
curl -s localhost:9200 | jq
curl -s localhost:9200/_cat/nodes?v
```

## 실제로 돌려보는 최소 시나리오

1. 인덱스 생성 + alias 연결 (위 매핑 사용)
2. 문서 색인

```bash
POST products/_doc/p-001
{
  "productId": "p-001",
  "name": "아이오페 에어쿠션 N 커버 21호",
  "brand": "아이오페",
  "categoryPath": "뷰티>베이스메이크업>쿠션",
  "price": 28000,
  "tags": ["쿠션", "커버", "21호"],
  "createdAt": "2026-04-10T09:00:00Z",
  "stockQty": 42,
  "isActive": true
}
```

3. 애널라이저가 어떻게 토큰화했는지 확인

```bash
POST products/_analyze
{
  "field": "name",
  "text": "아이오페 에어쿠션 N 커버"
}
```

출력 토큰을 보면서 "이게 내가 기대한 분리인가?"를 검증한다. Nori가 명사만 남기는지, 원하는 수준에서 멈추는지.

4. 부분 일치 보강 확인

```bash
GET products/_search
{
  "query": {
    "multi_match": {
      "query": "에어쿠",
      "fields": ["name^2", "name.ngram"]
    }
  }
}
```

`^2`는 필드 가중치. 같은 토큰이 매칭되어도 `name`에서 맞으면 2배 점수.

5. 집계

```bash
GET products/_search
{
  "size": 0,
  "aggs": {
    "brand_counts": { "terms": { "field": "brand" } }
  }
}
```

6. 재색인 연습: 매핑을 바꾼 `products-v2`를 만들고 `_reindex` → alias 스위칭을 직접 해본다. 이걸 한 번도 안 해보고 면접에서 설명하면 금방 들통난다.

## 자주 밟는 지뢰

- **매핑 폭발**: 동적으로 들어오는 JSON에 신규 필드가 계속 생기면 매핑이 수천 개로 불어나고 메타데이터 오버헤드가 누적된다. 의도치 않은 필드는 `dynamic: "strict"` 또는 `dynamic: "false"`로 차단.
- **deep pagination**: `from + size`로 10만 건 이상 넘겨받으려 하면 메모리 폭발. `search_after`나 `scroll`/`PIT`를 사용.
- **자주 업데이트되는 문서**: OpenSearch의 update는 내부적으로 삭제 후 재색인이다. 핫 레코드에 초당 업데이트가 수십 건씩 쏟아지면 세그먼트 머지 부담이 커진다. 업데이트가 잦은 필드는 별도 인덱스로 분리하거나, 업데이트 간격을 배치화하는 걸 고려.
- **검색어 동의어**: "클렌징오일" vs "클렌징 오일" 같은 띄어쓰기 이슈는 synonym filter 없이는 영영 안 맞는다. 운영 초기부터 동의어 사전 관리 계획이 필요.
- **refresh interval**: 기본 1초. 대량 적재 시에는 `-1`로 껐다가 끝나고 `1s`로 복구하는 패턴이 정석.

## 면접에서 묻는 방식과 답 프레임

면접관이 "OpenSearch 써보셨어요?"라고 물을 때 원하는 답은 "색인 파이프라인 + 재색인 + 품질 관측"의 3축이다.

### 예상 질문 1: "MySQL FULLTEXT가 있는데 왜 OpenSearch를 썼나요?"

답 프레임:
- 한국어 형태소 분석과 n-gram 조합, 동의어 관리, 가중치 정렬이 RDBMS에서 비대칭적으로 비싸다.
- 상품 검색은 읽기가 지배적이고 스케일아웃이 필요해서 검색 전용 복제본을 두는 편이 원장 RDBMS 부하를 낮춘다.
- 파사드 집계(브랜드별, 가격 구간별)가 검색과 동시에 나와야 해서 `aggs`가 네이티브로 있는 엔진이 유리.

### 예상 질문 2: "색인 반영은 어떻게 했나요?"

답 프레임:
- 원장 RDBMS에 쓰고 도메인 이벤트 발행.
- 컨슈머 서비스가 Kafka에서 받아 OpenSearch에 bulk 색인.
- 실패 시 DLQ + 리트라이, 최종적으로 재색인 작업으로 복구 가능.
- 동기 더블라이트는 피했다 — 부분 실패 시 정합성 복구가 비싸서.

### 예상 질문 3: "매핑 바꾸면 어떻게 하나요?"

답 프레임:
- `products-v{n}` 네이밍 + alias.
- 새 인덱스 생성 → `_reindex` → alias 스위칭.
- 읽기는 alias만 보고, 쓰기는 배포 시 새 인덱스로 방향 전환.
- 용량이 크면 `_reindex`를 슬라이스 병렬화 + throttling.

### 예상 질문 4: "검색 품질은 어떻게 측정했나요?"

답 프레임:
- CTR, zero-result rate, 상위 N 클릭률을 운영 지표로.
- 랭킹 변경은 shadow query 또는 인터리빙 A/B.
- 로그는 별도 인덱스에 적재해 분석.

### 예상 질문 5: "샤드는 몇 개로 잡았나요?"

답 프레임:
- 데이터 크기와 쓰기 속도 기반으로 샤드당 10~40GB 목표.
- 초기엔 보수적으로 잡고, reindex로 재조정.
- 노드 수와 힙 사이즈도 같이 본다 — 샤드 수가 힙을 소모하므로 과잉 샤드는 오히려 독이다.

## 학습 체크리스트

- [ ] 역색인이 왜 빠른지 토큰 단위로 설명할 수 있다.
- [ ] `text` vs `keyword`의 용도를 구분하고, multi-field 패턴을 말할 수 있다.
- [ ] 한국어 검색에 Nori와 n-gram을 병행하는 이유를 설명할 수 있다.
- [ ] `bool` 쿼리의 must/should/filter/must_not 차이와 캐시 영향을 말할 수 있다.
- [ ] alias 기반 무중단 재색인을 직접 한 번 이상 수행해봤다.
- [ ] bulk 색인에서 refresh interval과 replica 조정 패턴을 알고 있다.
- [ ] deep pagination 대안(`search_after`, PIT)을 설명할 수 있다.
- [ ] CDC 또는 이벤트 기반 반영 경로에서 실패 복구 전략을 그릴 수 있다.
- [ ] 동적 매핑 폭발과 `dynamic: strict`의 트레이드오프를 말할 수 있다.
- [ ] Java 클라이언트로 인덱스/검색/벌크 세 가지를 구현해본 경험이 있다.
