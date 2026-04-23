# [초안] OpenSearch 검색 품질을 좌우하는 analyzer 구조: nori, ngram, tokenizer, token filter 제대로 이해하기

## 왜 이 주제를 공부해야 하는가

검색 기능은 백엔드 엔지니어가 피할 수 없는 과제 중 하나다. 상품 검색, 로그 검색, 자동완성, 오타 보정, 다국어 처리 같은 요구사항이 쌓이다 보면 결국 Elasticsearch 혹은 OpenSearch 같은 검색 엔진을 도입하게 되고, 그 순간부터 "왜 이 키워드로는 안 나오지?", "왜 부분 일치가 이상하게 동작하지?", "왜 한글은 조사까지 걸리지?" 같은 질문이 쏟아진다.

이 모든 질문의 답은 결국 한 곳으로 귀결된다. **analyzer가 문자열을 어떻게 토큰으로 쪼개고 정규화하는가.** analyzer를 이해하지 못한 채로 OpenSearch를 도입하면, 인덱스에 이상한 토큰이 들어가 있고 쿼리 시점에는 다른 토큰이 생성되어 매칭 자체가 실패하는 버그를 잡는 데 며칠을 쓰게 된다. 반대로 analyzer 구성 요소(`character filter`, `tokenizer`, `token filter`)와 주요 플러그인(`nori`, `ngram`)의 동작 방식을 제대로 잡아두면, 검색 품질 이슈의 80%는 색인/쿼리 설정 수준에서 해결된다.

시니어 백엔드 관점에서는 한 단계 더 들어간다. nori를 쓰면 정확도는 올라가지만 인덱스 크기와 색인 시간이 늘어나고, ngram을 쓰면 부분 일치가 가능해지지만 인덱스가 폭발한다. 이 trade-off를 이해하고, 요구사항에 맞춰 analyzer 파이프라인을 설계할 수 있어야 한다. 이 문서는 그 설계 감각을 잡기 위한 실전 가이드다.

## OpenSearch analyzer의 기본 구조

OpenSearch의 analyzer는 세 단계 파이프라인이다.

```
입력 텍스트
   │
   ▼
[character filter] ── 원문 자체를 변형 (HTML 제거, 문자 치환 등)
   │
   ▼
[tokenizer] ─────── 문자열을 토큰(term) 단위로 분리
   │
   ▼
[token filter] ──── 토큰을 정규화, 확장, 제거
   │
   ▼
 인덱스에 저장되는 term
```

핵심은 **tokenizer는 반드시 하나**, **character filter와 token filter는 0개 이상**이라는 점이다. 많은 사람이 "analyzer = nori"라고 착각하지만, 실제로는 "nori_tokenizer + 여러 token filter의 조합"이 가장 현실적인 analyzer다.

예를 들어 검색 쿼리 `"올리브영 매장 영업시간"`이 들어왔을 때, standard analyzer는 공백으로만 자르기 때문에 `[올리브영, 매장, 영업시간]` 같은 토큰이 만들어진다. 문제는 사용자가 `"올리브영매장"`처럼 붙여 쓰면 하나의 토큰 `올리브영매장`이 되어버려 색인된 `올리브영`과 매칭되지 않는다. 한국어 검색에서 nori나 ngram이 필요한 이유가 여기에 있다.

## nori 플러그인: 한국어 형태소 분석기

nori는 Elasticsearch/OpenSearch 공식에서 제공하는 한국어 형태소 분석 플러그인이다. 내부적으로는 Lucene의 `KoreanAnalyzer`를 래핑하고 있으며, 사전 기반(mecab-ko-dic 유래)으로 단어를 분석한다.

### nori의 구성 요소

nori 플러그인은 설치 후 세 가지를 제공한다.

- `nori_tokenizer` — 한국어 문장을 형태소 단위로 분리
- `nori_part_of_speech` token filter — 특정 품사(조사, 어미 등)를 제거
- `nori_readingform` token filter — 한자를 한글 독음으로 변환

`nori_tokenizer`에는 `decompound_mode`라는 중요한 옵션이 있다.

- `none` — 복합명사를 분리하지 않는다. `백두산` → `[백두산]`
- `discard` — 복합명사를 분리한 토큰만 남긴다. `백두산` → `[백두, 산]`
- `mixed` — 원본 복합명사 + 분리된 구성 요소 모두 인덱싱. `백두산` → `[백두산, 백두, 산]`

검색 서비스 관점에서는 `mixed`가 흔히 선택된다. 사용자가 전체 단어로 검색하든 일부 단어로 검색하든 매칭되기 때문이다. 다만 인덱스 크기는 커진다.

### nori 설정 예시

```json
PUT /products
{
  "settings": {
    "analysis": {
      "tokenizer": {
        "my_nori_tokenizer": {
          "type": "nori_tokenizer",
          "decompound_mode": "mixed",
          "user_dictionary_rules": [
            "올리브영",
            "맥세이프",
            "멀티비타민민"
          ]
        }
      },
      "analyzer": {
        "korean_analyzer": {
          "type": "custom",
          "tokenizer": "my_nori_tokenizer",
          "filter": [
            "lowercase",
            "nori_part_of_speech_filter",
            "nori_readingform"
          ]
        }
      },
      "filter": {
        "nori_part_of_speech_filter": {
          "type": "nori_part_of_speech",
          "stoptags": [
            "E", "IC", "J", "MAG", "MAJ", "MM",
            "SP", "SSC", "SSO", "SC", "SE",
            "XPN", "XSA", "XSN", "XSV",
            "UNA", "NA", "VSV"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "korean_analyzer"
      }
    }
  }
}
```

여기서 주목할 점은 **사용자 사전(`user_dictionary_rules`)** 이다. 신조어, 브랜드명, 내부 도메인 용어는 기본 사전에 없기 때문에 nori가 엉뚱하게 쪼갠다. 예를 들어 `"맥세이프"`는 기본 사전에 없으면 `[맥, 세이프]`로 쪼개질 수 있다. 실제 서비스에서는 상품명, 브랜드, 카테고리를 사용자 사전으로 꾸준히 관리해야 한다.

`stoptags`는 제거할 품사 태그다. `J`(조사), `E`(어미), `MAG`(일반 부사) 같은 것들은 검색 매칭에 도움이 안 되기 때문에 걷어낸다. 이 리스트는 Lucene 문서에 전부 정의되어 있으니 프로젝트마다 조정하면 된다.

## ngram tokenizer: 부분 일치와 자동완성

ngram은 문자열을 n글자 단위로 잘라 모든 부분 문자열을 토큰화한다.

- `min_gram: 2, max_gram: 3`인 ngram으로 `"검색"`을 분석하면 `[검, 검색, 색]` 수준에서 토큰이 나온다(경계 설정에 따라 다르다).
- `"올리브영"`을 `min_gram: 2, max_gram: 3`으로 넣으면 `[올리, 올리브, 리브, 리브영, 브영]`이 된다.

이 덕분에 `"리브영"`으로 검색해도 `"올리브영"`이 매칭된다. 즉, 부분 일치(wildcard 없는 `LIKE '%xxx%'`와 유사한 UX)를 구현할 수 있다.

### ngram vs edge_ngram

두 가지는 자주 혼동되지만 용도가 다르다.

- `ngram` — 모든 위치의 부분 문자열. `"olive"` → `[ol, oli, liv, ive, ...]`
- `edge_ngram` — 앞에서부터 자르는 부분 문자열. `"olive"` → `[o, ol, oli, oliv, olive]`

**자동완성 기능에는 거의 항상 `edge_ngram`이 정답이다.** 사용자가 `"올"`을 입력하면 `"올리브영"`, `"올영"`이 떠야 하지만, `"리브"`만 입력했는데 `"올리브영"`이 떠서는 자동완성 UX가 어색해진다.

### 색인 시점 vs 검색 시점 analyzer

ngram을 설계할 때 가장 많이 하는 실수가 **색인 analyzer와 검색 analyzer를 동일하게 쓰는 것**이다.

- 색인 시점: 문서의 `"올리브영"`을 `[올, 올리, 올리브, 올리브영]`로 쪼개 저장
- 검색 시점 사용자가 `"올리"`라고 입력했을 때 또 edge_ngram을 적용하면 `[올, 올리]`로 쪼개져 두 토큰 모두 매칭을 시도한다.

만약 검색 시점에도 edge_ngram을 쓰면, `"올리"`가 `[올, 올리]`로 확장되고, 이 중 `"올"`은 전혀 다른 상품(`"올영세일"`의 `올` 부분)과도 매칭되어 정확도가 급락한다. 그래서 일반적으로 다음 패턴을 쓴다.

```json
"mappings": {
  "properties": {
    "name": {
      "type": "text",
      "analyzer": "autocomplete_index_analyzer",
      "search_analyzer": "standard"
    }
  }
}
```

색인은 edge_ngram으로 넓게 쪼개고, 검색은 `standard`나 `keyword`로 그대로 넣는다. 이 비대칭이 성능과 정확도 양쪽의 핵심이다.

## bad vs improved 예제

### Bad: 맹목적으로 nori만 적용하기

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "default": {
          "type": "nori"
        }
      }
    }
  }
}
```

이 설정의 문제는 세 가지다.

1. `decompound_mode`가 기본값(`discard`)이라 원본 단어가 사라진다. `"올리브영"`이 사전에 없거나 다르게 분해되면 `"올리브영"`이라는 완전한 토큰이 인덱스에 아예 없다.
2. 불용 품사 필터가 없어 조사·어미가 그대로 들어간다. `"검색했다"`가 `[검색, 하, 였, 다]` 같은 토큰으로 쪼개져 저장된다.
3. 브랜드/상품 사전 관리가 없어 신조어마다 결과가 깨진다.

### Improved: 역할별 analyzer 분리

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "korean_search": {
          "type": "custom",
          "tokenizer": "nori_tokenizer_mixed",
          "filter": ["lowercase", "ko_pos_filter"]
        },
        "autocomplete_index": {
          "type": "custom",
          "tokenizer": "edge_ngram_tokenizer",
          "filter": ["lowercase"]
        },
        "autocomplete_search": {
          "type": "custom",
          "tokenizer": "keyword",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "nori_tokenizer_mixed": {
          "type": "nori_tokenizer",
          "decompound_mode": "mixed"
        },
        "edge_ngram_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 1,
          "max_gram": 15,
          "token_chars": ["letter", "digit"]
        }
      },
      "filter": {
        "ko_pos_filter": {
          "type": "nori_part_of_speech",
          "stoptags": ["E", "J", "MAG", "SP"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "korean_search"
      },
      "name_autocomplete": {
        "type": "text",
        "analyzer": "autocomplete_index",
        "search_analyzer": "autocomplete_search"
      }
    }
  }
}
```

핵심은 **한 필드에 여러 analyzer를 쓰지 않고, 목적별로 필드를 분리**한다는 점이다. `name`은 정확도 중심, `name_autocomplete`은 부분 일치 중심으로 가고, 애플리케이션에서 용도에 맞게 쿼리한다.

## 로컬 연습 환경

도커로 OpenSearch를 띄우고 nori 플러그인을 설치한다.

```bash
# docker-compose.yml
version: "3"
services:
  opensearch:
    image: opensearchproject/opensearch:2.13.0
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
    ports:
      - "9200:9200"
    volumes:
      - ./data:/usr/share/opensearch/data
```

컨테이너에 들어가 nori 플러그인을 설치한다.

```bash
docker exec -it <container> bash
./bin/opensearch-plugin install analysis-nori
exit
docker restart <container>
```

## 실행 가능한 예제

`_analyze` API로 analyzer의 결과를 직접 확인할 수 있다. 이 API는 평소 디버깅에서 가장 많이 쓰는 도구다.

### 예제 1: nori decompound_mode 비교

```bash
curl -X POST "localhost:9200/_analyze" -H 'Content-Type: application/json' -d'
{
  "tokenizer": {
    "type": "nori_tokenizer",
    "decompound_mode": "mixed"
  },
  "text": "대한민국헌법재판소"
}'
```

`mixed`에서는 `[대한민국헌법재판소, 대한민국, 헌법, 재판소, ...]`처럼 원본과 분해본이 모두 나온다. `discard`로 바꾸면 원본이 사라진다.

### 예제 2: edge_ngram 자동완성 확인

```bash
curl -X POST "localhost:9200/_analyze" -H 'Content-Type: application/json' -d'
{
  "tokenizer": {
    "type": "edge_ngram",
    "min_gram": 1,
    "max_gram": 10,
    "token_chars": ["letter", "digit"]
  },
  "text": "올리브영"
}'
```

결과로 `[올, 올리, 올리브, 올리브영]`이 나오면 색인이 제대로 되는지 쉽게 눈으로 확인할 수 있다.

### 예제 3: 사용자 사전 적용 후 비교

사전 없는 경우와 있는 경우의 토큰을 `_analyze`로 각각 실행해 비교한다. 사전에 `"맥세이프"`를 추가하기 전에는 `[맥, 세이프]`로 쪼개지지만, 추가 후에는 `[맥세이프]` 하나로 유지된다. 이 차이가 실제 검색 품질에서 눈에 보일 만큼 크다는 점을 직접 확인하는 것이 중요하다.

### 예제 4: 비대칭 analyzer로 자동완성 끝까지 검증

색인 후 실제 검색을 날려 본다.

```bash
curl -X POST "localhost:9200/products/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "name_autocomplete": {
        "query": "올리",
        "operator": "and"
      }
    }
  }
}'
```

검색어 `"올리"`가 `standard`로 분석되어 그대로 들어가고, 색인된 edge_ngram 토큰 중 `"올리"`와 정확히 일치하는 항목이 걸린다. 만약 검색 시에도 edge_ngram을 쓰고 있다면 정확도가 떨어진다는 점을 직접 비교해 본다.

## 흔한 오해와 실패 패턴

- **오해: "nori를 쓰면 자동으로 검색 품질이 좋아진다."** 사용자 사전 관리, 품사 필터 튜닝 없이 넣으면 오히려 엉망이 된다. 운영 중 검색 로그를 보면서 사전 관리는 꾸준히 해야 한다.
- **오해: "ngram과 edge_ngram은 같은 것이다."** 용도가 완전히 다르다. 자동완성에는 edge_ngram, 중간 부분 일치(한정적으로)에는 ngram이다.
- **실패 패턴: 색인/검색 analyzer를 동일하게 두기.** ngram류에서 가장 빈번한 버그다. `search_analyzer`를 명시하지 않아 검색 정확도가 무너지는 경우가 매우 많다.
- **실패 패턴: `min_gram`을 1로 두기.** 인덱스 크기가 수 배로 커지고 아무 단어나 매칭되기 시작한다. 자동완성이라도 보통 2부터 시작하는 것을 고려한다.
- **실패 패턴: analyzer를 바꾸고 reindex를 안 하기.** analyzer 변경은 새로 색인된 문서에만 적용된다. 기존 문서는 예전 토큰을 가지고 있기 때문에, analyzer 변경 후에는 새 인덱스를 만들고 alias 스왑으로 이관하는 패턴이 정석이다.

## 설계 관점에서의 trade-off

실무에서는 단일 analyzer로 모든 요구사항을 만족시킬 수 없다. 보통 다음처럼 간다.

- **정확한 의미 검색**: nori + 품사 필터 + 사용자 사전
- **부분 일치/오타 관대 검색**: ngram 또는 nori + synonym filter
- **자동완성**: edge_ngram (색인) + keyword/standard (검색)
- **다국어 상품명**: 필드 분리 후 각 언어별 analyzer

필드를 분리하는 설계가 핵심이다. `multi_fields`를 써서 `name`, `name.autocomplete`, `name.raw` 같이 한 소스를 여러 형태로 색인하면, 쿼리 레이어에서 가중치만 조정해도 깔끔하게 검색 품질을 튜닝할 수 있다.

인덱스 크기와 색인 속도도 반드시 같이 본다. edge_ngram `min_gram: 1, max_gram: 20`은 이론적으로는 가능하지만, 실제로는 인덱스가 몇 배로 불어나 색인 처리량이 눈에 띄게 떨어진다. 자동완성은 보통 `min_gram: 2, max_gram: 10~15` 범위에서 타협한다.

## 면접 답변 프레임

면접에서 "OpenSearch analyzer를 어떻게 설계하셨나요?"라는 질문이 나오면 다음 구조로 답하는 게 안정적이다.

1. **문제 정의 먼저**: "상품 검색에서 한글 부분 일치와 자동완성이 모두 필요했다. 단일 필드·단일 analyzer로는 정확도와 재현율을 동시에 만족시킬 수 없었다."
2. **구성 요소로 분해**: "analyzer는 character filter → tokenizer → token filter 파이프라인이고, 한국어는 nori_tokenizer, 자동완성은 edge_ngram tokenizer로 분리했다."
3. **선택 근거**: "정확도 중심 필드에는 nori + part_of_speech filter로 조사/어미를 제거했고, 자동완성 필드에는 edge_ngram을 색인 analyzer로, standard를 search analyzer로 둬 비대칭 구성을 했다."
4. **운영 관점 언급**: "브랜드명·신조어는 user_dictionary로 관리하고, analyzer 변경 시에는 새 인덱스 + alias 스왑으로 무중단 reindex했다."
5. **숫자로 마무리**: "그 결과 검색 누락 케이스를 약 X% 줄였고, 자동완성 latency도 Y ms 이내로 유지됐다."

즉답보다는 "왜 이런 구성이 필요했는지"를 문제 정의부터 풀어가는 게 시니어다운 답변이다. 인덱스 크기, 색인 속도, reindex 전략까지 자연스럽게 언급할 수 있으면 운영 경험이 있는 엔지니어라는 인상을 준다.

## 관련 예상 질문

- nori의 `decompound_mode` 세 가지 차이를 설명하라. 어떤 상황에서 어떤 모드를 쓰는가.
- edge_ngram과 ngram의 차이, 그리고 각각의 대표적인 유스케이스는.
- 색인 analyzer와 검색 analyzer를 다르게 가져가는 이유는.
- 사용자 사전은 왜 필요하고, 운영상 어떤 리스크가 있나.
- analyzer를 변경할 때 기존 문서에는 왜 바로 반영되지 않는가. 어떻게 처리하는가.
- `min_gram`을 너무 작게 잡으면 어떤 문제가 생기는가.
- 특정 쿼리에서 기대한 결과가 나오지 않을 때 어떤 순서로 디버깅하는가. (힌트: `_analyze`, `explain`, `profile` API)

## 체크리스트

- [ ] character filter, tokenizer, token filter의 역할과 순서를 그림 없이 설명할 수 있다.
- [ ] nori_tokenizer의 `decompound_mode` 세 가지를 상황별로 고를 수 있다.
- [ ] `nori_part_of_speech`의 `stoptags` 의미를 이해하고 필요한 품사를 고를 수 있다.
- [ ] 사용자 사전을 추가하고 `_analyze`로 토큰 변화를 검증할 수 있다.
- [ ] edge_ngram과 ngram을 용도에 맞춰 고르고, `min_gram`/`max_gram`의 영향을 설명할 수 있다.
- [ ] 색인 analyzer와 검색 analyzer를 비대칭으로 설정하는 이유를 설명할 수 있다.
- [ ] analyzer 변경 시 reindex + alias 스왑 흐름을 실제로 구성해 본 적이 있다.
- [ ] `_analyze` API로 실제 토큰을 확인하고 검색 버그를 추적해 본 경험이 있다.
- [ ] 인덱스 크기와 색인 속도 관점에서 ngram 설정을 튜닝할 수 있다.
- [ ] 면접에서 "문제 정의 → 구성 요소 분해 → 선택 근거 → 운영 관점 → 결과" 순으로 답변 가능한 사례 하나가 준비되어 있다.
