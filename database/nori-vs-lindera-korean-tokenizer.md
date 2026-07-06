---
categories: [database]
tags: [심화]
---

# 한국어 형태소 분석기 Nori vs Lindera — OpenSearch에서 Milvus로 갈 때 어휘 검색은 유지되나

> [OpenSearch vs Milvus 비교](./milvus/opensearch-vs-milvus.md)의 "한국어 처리" 절을 먼저 읽으면 좋다.
> 이 글은 그 한 문단을 형태소 분석기 수준까지 파고든 심화판이다.

벡터 DB를 OpenSearch에서 Milvus로 옮기는 걸 검토하면서 계속 걸린 게 하나 있었다.
의미 기반 dense 벡터는 임베딩 모델이 만드니 DB를 바꿔도 같다.
그런데 하이브리드 검색의 나머지 절반, **어휘 기반 sparse 검색은 형태소 분석기가 만든다.**
OpenSearch는 `nori`, Milvus는 `lindera`를 쓴다 — 이 둘이 한국어를 같은 수준으로 쪼개지 못하면 검색 정확도가 조용히 떨어진다.

## 먼저 가져갈 결론

- **토큰화 품질의 뿌리는 같다.** nori도 lindera(ko-dic)도 결국 `mecab-ko-dic` 계열 사전을 쓴다.
  같은 문장을 넣으면 조사·어미를 걸러낸 의미 토큰은 사실상 같다. 어휘 검색 정확도의 하한은 둘 다 비슷하다.
- **갈리는 건 튜닝을 얼마나 세밀하게 노출하느냐다.** nori는 복합명사 분해 모드, 사용자 사전, 한자 독음, 숫자 정규화를 analyzer 설정으로 직접 연다.
  Milvus lindera는 사전 선택과 품사 stop 태그, 문장부호·길이 필터 정도까지만 공식 문서에 드러난다.
- **프로덕션에서 진짜 갈림길은 Milvus 버전이다.** lindera 한국어 사전은 **2.5.x에서는 직접 컴파일해야** 쓰고, **2.6부터 기본 내장**된다.
  관리형 상품이 어느 버전을 주느냐가 "한국어 sparse 검색을 바로 쓸 수 있나"를 결정한다.
- 그래서 선택 기준은 "어느 분석기가 더 정확한가"가 아니라 **내가 지금 쓰는 nori 튜닝을 옮겨갈 곳에서 재현할 수 있나**이다.

## 왜 이게 벡터 DB 선택 문제가 되는가

하이브리드 검색은 두 축을 한 쿼리에서 융합한다.

- dense 벡터 — 의미가 비슷하면 잡는다. 임베딩 모델 담당이라 DB를 바꿔도 불변.
- sparse 벡터(BM25 계열) — 정확한 단어·희귀어·고유명사를 잡는다. **형태소 분석기가 토큰을 어떻게 자르냐에 전적으로 의존한다.**

"삼성전자 주가"를 검색할 때 dense는 "코스피 시가총액" 같은 의미 이웃을 데려오고, sparse는 "삼성전자"라는 정확한 표층 단어를 잡는다.
sparse가 무너지면 정확한 키워드 매칭이 약해지고, RAG가 엉뚱한 문서를 근거로 답하기 시작한다.
그러므로 DB를 옮길 때 "형태소 분석기가 같은 토큰을 만드나"는 검색 품질 회귀를 좌우하는 문제다.

## 한눈에 — sparse 토큰이 만들어지는 경로

두 분석기 모두 같은 파이프라인을 거친다 — 형태소 tokenizer 로 자르고, 품사 필터로 조사·어미를 걸러 sparse 토큰을 남긴다.

```mermaid
flowchart LR
  d["한국어 문장"] --> t["형태소 tokenizer<br/>nori / lindera(ko-dic)"]
  t --> pos["품사 필터<br/>nori_part_of_speech / korean_stop_tags"]
  pos --> out["sparse 토큰<br/>(조사·어미 제거)"]
  out --> bm["BM25 sparse 색인"]
```

뿌리가 같아 이 경로는 거의 겹친다. 갈리는 건 이 위에 얹는 튜닝 손잡이(복합명사 모드·사용자 사전·독음)의 개수다 — 아래에서 짚는다.

## 뿌리는 같다 — 둘 다 mecab-ko-dic

두 분석기의 계보를 보면 왜 토큰화 결과가 비슷한지 납득된다.

- **nori** — Lucene에 내장된 `analysis-nori` 모듈이다. 일본어 분석기 Kuromoji 코드에서 출발해 한국어 모듈로 독립했고, 사전은 `mecab-ko-dic`(21세기 세종계획 말뭉치, 약 81만 어휘)을 쓴다.
  입력 문장으로 분절 후보 격자(lattice)를 만들고 Viterbi 탐색으로 누적 비용이 최소인 경로를 고른다.
- **lindera** — Rust로 작성된 형태소 분석 라이브러리다. 일본어 분석기 kuromoji-rs에서 fork됐고, 한국어는 `ko-dic`(역시 mecab-ko-dic 계열)을 쓴다.

즉 둘 다 "kuromoji 계보 + mecab-ko-dic 사전 + 비용 기반 Viterbi"라는 같은 뼈대다.
품사(POS) 태그 체계도 같은 세종 태그셋을 공유한다.
그래서 조사·어미를 걸러낸 의미 토큰은 사실상 일치하고, 오히려 복합명사에서 lindera가 덜 쪼개는 경향이 관찰된다(예: "데이터베이스"를 통째로 두는 쪽 vs "데이터/베이스"로 나누는 쪽).

차이는 사전 뼈대가 아니라 **그 위에 얹는 제어 손잡이의 개수**에서 나온다.

## 기능 동등성 — nori가 여는 손잡이, Milvus lindera가 여는 손잡이

nori가 analyzer 레벨에서 노출하는 기능과, Milvus의 lindera analyzer가 공식 문서에 드러내는 기능을 맞대면 이렇다.

참고로 Milvus 텍스트 analyzer가 제공하는 필터는 공식 문서 기준 12종이다 — `lowercase`, `asciifolding`, `alphanumonly`, `cnalphanumonly`, `cncharonly`, `stop`, `length`, `stemmer`, `removepunct`, `regex`, `decompounder`, `synonym`.
그리고 lindera tokenizer가 받는 키는 딱 3개다 — `type`, `dict_kind`, `filter`(그 안에 `korean_stop_tags` 같은 `kind`). 이 목록 밖의 기능은 지금 노출되지 않는다.

| 기능 | nori (OpenSearch) | Milvus lindera | 전환 |
| --- | --- | --- | --- |
| 사전 | mecab-ko-dic 고정 | `dict_kind: ko-dic` | 대응 |
| 품사 필터 | `nori_part_of_speech` (stoptags) | `korean_stop_tags` (tags) | 부분 대응 (태그 재매핑 필요) |
| 문장부호 제거 | `discard_punctuation` | `removepunct` 필터 | 대응 |
| 길이 필터 | 표준 `length` 필터 | `length` (min/max) | 대응 |
| 동의어 | 표준 `synonym` / `synonym_graph` | `synonym` 필터 | 대응 (그래프 동의어는 검증) |
| 복합명사 분해 모드 | `decompound_mode`: none / discard / mixed | **없음** | **재현 불가** |
| 사용자 사전 | `user_dictionary` / `user_dictionary_rules` | **없음** (open FR) | **재현 불가** |
| 한자→한글 독음 | `nori_readingform` | **없음** | **재현 불가** |
| 숫자 정규화 | `nori_number` | **없음** | **재현 불가** |

핵심 그림은 이렇다.
**의미 토큰을 만드는 핵심 경로(사전 + 품사 필터 + 동의어)는 옮겨간다.**
반면 recall을 끌어올리는 세밀 손잡이 — 복합명사 mixed 모드, 사용자 사전, 한자 독음, 숫자 정규화 — 는 Milvus lindera에서 재현되지 않는다.
이 네 가지는 아래 "전환 시 재현 못 하는 nori 튜닝"에서 각각 무엇을 잃는지 짚는다.

방법론 주의 — "재현 불가" 넷 중 `user_dictionary`는 Milvus가 아직 미지원(공개 feature request)이라 근거가 강하다.
나머지 셋(분해 모드, 독음, 숫자)은 lindera 엔진에는 능력이 있어도 **Milvus가 파라미터로 노출하지 않는** 것일 수 있다 — "엔진 미지원"이 아니라 "Milvus 미노출"이라, 대상 버전 릴리스 노트로 다시 확인하는 게 안전하다.

## nori 튜닝 옵션 — 실제로 recall을 움직이는 것들

### decompound_mode — 복합명사 분해가 recall/precision 절충

`가곡역`(고유명 복합어)을 기준으로:

| 모드 | 동작 | 출력 |
| --- | --- | --- |
| `none` | 분해 안 함 | `가곡역` |
| `discard` (기본값) | 분해하고 원형 버림 | `가곡`, `역` |
| `mixed` | 분해하되 원형도 유지 | `가곡역`, `가곡`, `역` |

`mixed`는 원형과 부분을 모두 색인해 recall이 오르지만 색인 크기와 노이즈가 는다.
`discard`는 정밀하고 가볍지만 원형 그대로 질의하면 놓칠 수 있다.
흔한 전략은 색인 시 `mixed`로 넓게 깔고 검색 시 `search_analyzer`를 따로 둬 과매칭을 줄이는 것인데, 이건 공식이 강제하는 조합이 아니라 커뮤니티 관행이다.

### 품사 필터 — 편리하지만 함정이 있다

`nori_part_of_speech`의 `stoptags`로 조사·어미·부호를 걸러 명사 위주로 남긴다.
문제는 **기본 stoptags에 접두사 `XPN`이 들어 있다**는 점이다.
그래서 `비급여`가 기본 분석에서 `급여`만 남는다 — 부정·범위를 뒤집는 접두사(비-, 무-, 미-)가 사라져 검색 의미가 왜곡된다.
도메인에 이런 접두사가 중요하면 stoptags에서 빼야 한다. 이건 공식 문서에 명시된 실사례라 반드시 점검할 지점이다.

### 그 밖의 필터

- `nori_readingform` — 한자 토큰을 한글 독음으로(`鄕歌` → `향가`). 한자 원문을 한글 질의로 매칭.
- `nori_number` — 한글·혼용 숫자를 아라비아 숫자로(`삼천2백2십삼` → `3223`). 단 이걸 쓰려면 `discard_punctuation`을 `false`로 둬야 해서 색인에 구두점 노이즈가 생기고, 후단 `stop` 필터로 정리해야 한다.

## Milvus lindera 튜닝 옵션

Milvus의 analyzer는 **토크나이저 1개 + 필터 0개 이상**으로 구성된다.
한국어 권장 구성은 lindera + ko-dic이다. 공식 문서의 한국어 예시(품사 필터 방식):

```json
{
  "tokenizer": {
    "type": "lindera",
    "dict_kind": "ko-dic",
    "filter": [
      {
        "kind": "korean_stop_tags",
        "tags": ["SP", "SSC", "SSO", "SC", "SE", "SF",
                 "JKS", "JKC", "JKG", "JKO", "JKB", "JKV",
                 "JKQ", "JX", "JC", "UNK", "EP", "ETM"]
      }
    ]
  }
}
```

조정 축은 사전(`dict_kind`), 품사 stop 태그(`korean_stop_tags`), 문장부호 제거(`removepunct`), 길이 필터(`length`)다.
nori와 품사 태그 체계가 같아 stop 태그 설정이 거의 그대로 옮겨간다.
단 주의할 표기 함정이 있다 — 사전 지정 키가 문서 페이지마다 `dict_kind`와 `dict`로 엇갈린다.
lindera 전용 페이지는 `dict_kind`를 쓰니 그걸 우선하되, 실제 배포 버전 스키마로 확정하는 게 안전하다.

## 사내 현행 nori 설정을 뜯어보면

지금 운영 중인 OpenSearch의 한국어 analyzer는 이렇게 잡혀 있다.

```json
{
  "korean_analyzer": {
    "type": "custom",
    "tokenizer": "nori_tokenizer",
    "filter": ["lowercase", "asciifolding", "nori_readingform", "my_pos_filter"]
  },
  "my_pos_filter": {
    "type": "nori_part_of_speech",
    "stoptags": ["EP","EF","EC","ETN","ETM","IC","JKS","JKC","JKG","JKO",
                 "JKB","JKV","JKQ","JX","JC","MAG","MAJ","MM","SF","SP",
                 "SSC","SSO","SC","SY","SE","XPN","XSA","XSN","XSV"]
  }
}
```

이 설정을 위 원리에 비추면 개선 여지가 바로 보인다.

- **`nori_tokenizer`에 옵션이 없다** → `decompound_mode`가 기본값 `discard`로 돈다.
  복합명사를 부분으로만 색인하고 원형을 버린다. 원형 그대로 질의하면 놓칠 수 있어, recall이 중요하면 `mixed`를 검토할 만하다.
- **`user_dictionary`가 없다** → 신조어·제품명·브랜드가 mecab-ko-dic에 없으면 잘못 분해된다. 도메인 용어 사전 등록이 recall을 크게 올릴 수 있는 지점이다.
- **`synonym` 필터가 없다** → 동의어·약어 확장이 없다. 어휘가 정확히 일치할 때만 잡힌다.
- **`stoptags`에 `XPN`이 들어 있다** → 위에서 본 `비급여` → `급여` 함정에 그대로 노출된다. 접두사가 의미를 가르는 도메인이면 재검토가 필요하다.

즉 현행은 "무난한 기본형"이고, mixed 모드·사용자 사전·동의어·XPN 재검토 네 가지가 손대볼 만한 개선 축이다.
이 개선을 Milvus로 옮겨간 뒤에도 똑같이 할 수 있느냐가 전환 판단의 실질 기준이 된다.

## 전환 시 재현 못 하는 nori 튜닝

위 개선 축을 Milvus lindera에 맞대 보면, 지금 쓰는 것과 앞으로 튜닝할 것이 갈린다.

**지금 실제로 쓰는데 못 옮기는 것 — `nori_readingform`.**
현행 `korean_analyzer` 필터 체인에 `nori_readingform`이 들어 있다(한자 토큰을 한글 독음으로: `鄕歌` → `향가`).
Milvus 필터 12종에 독음 변환 계열이 없다 → 전환 시 이 기능은 사라진다.
다만 코퍼스가 순수 한글 위주면 실제 영향은 작다. 한자·한글 혼용 문서가 얼마나 되는지로 판단하면 된다.

**앞으로 튜닝하려면 필요한데 막히는 것.**

| 튜닝하려던 것 | nori | Milvus lindera | 잃는 것 |
| --- | --- | --- | --- |
| 도메인 고유명사 등록 | `user_dictionary` | 없음 (open FR) | 상품명·사내 용어를 한 토큰으로 묶는 튜닝. 미등록어가 잘게 쪼개져 정확도 손실. **가장 직접적 타격** |
| 복합명사 재현율 상향 | `decompound_mode: mixed` | 없음 | 복합어 원형+부분 동시 색인으로 recall 올리기. `decompounder` 필터는 조각을 사람이 손으로 나열하는 수동 방식(독일어용)이라 대체가 안 됨 |
| 한자 독음 통일 | `nori_readingform` | 없음 | 위와 동일 |
| 숫자 표기 정규화 | `nori_number` | 없음 | 한글 수사(`삼천2백` → `3223`) 매칭. RAG에서 사용 빈도는 낮은 편 |

**반대로 문제없이 옮겨가는 것.**
동의어는 nori 기능이 아니라 Lucene 표준 `synonym` 필터인데, Milvus에도 `synonym` 필터가 있어 거의 손실 없이 이전된다(다중어 그래프 동의어만 검증 권장).
품사 필터도 `korean_stop_tags`로 대응되지만, nori 태그 체계와 mecab-ko-dic 원본 태그 체계가 달라 **stoptags 문자열을 그대로 복사하면 안 되고 ko-dic 세분 태그로 재매핑**해야 한다(오히려 더 정밀한 제어가 가능해진다).

정리하면 — 사내 현행에서 실제 잃는 건 `nori_readingform` 하나이고(영향은 코퍼스 의존), **앞으로 recall을 끌어올릴 핵심 손잡이인 사용자 사전과 복합명사 mixed 모드가 Milvus에서 막힌다**는 게 진짜 리스크다.

## 프로덕션 레벨 차이 — 버전이 가른다

기능 표만 보면 "nori가 손잡이가 더 많다" 정도지만, 운영에서 더 크게 갈리는 건 성숙도와 버전이다.

- **Milvus 2.5.x** — lindera 한국어를 쓰려면 해당 사전을 넣어 Milvus를 직접 컴파일해야 한다(`make milvus TANTIVY_FEATURES=lindera-ko-dic` 형태). 빌드에 안 넣은 사전은 못 쓴다.
  즉 기본 바이너리로는 한국어 sparse 검색을 바로 못 쓴다.
- **Milvus 2.6+** — 모든 lindera 사전이 미리 컴파일돼 내장된다. 별도 빌드 없이 `dict_kind: ko-dic`으로 바로 쓴다.

관리형 상품(예: 클라우드형 Milvus)이라면 **제공 버전이 2.5인지 2.6인지가 한국어 어휘 검색 사용 난이도를 결정한다.**
nori는 이 문제가 없다 — OpenSearch 2.x·3.x 모두 `analysis-nori`를 정식 플러그인으로 제공하고, 관리형 서비스도 옵션 플러그인으로 지원한다.
lindera의 한국어 지원은 상대적으로 최근이라, 프로덕션 채택 전 대상 버전에서 실제 토큰화를 찍어보는 검증이 nori보다 더 중요하다.

## 그래서 무엇을 고르나

검색 정확도만 놓고 "nori가 lindera보다 정확하다"고 말할 근거는 없다.
뿌리 사전이 같아 의미 토큰은 비슷하게 나온다.
갈림은 다른 데 있다 — **지금 쓰는 nori 튜닝을 옮겨갈 곳에서 재현할 수 있느냐**이다.

전환을 검토할 때 이 순서로 점검하면 된다.

1. **현행 nori 설정에서 실제로 쓰는 손잡이를 적는다.** decompound 모드, 사용자 사전 유무, readingform, synonym, 커스텀 stoptags.
2. **그 각각이 대상 Milvus 버전의 lindera analyzer로 표현되는지 확인한다.** 특히 사용자 사전 노출과 복합명사 분해 모드는 문서만 보지 말고 실제로 찍어본다.
3. **대상 버전이 2.5면 lindera-ko-dic 컴파일 포함 여부를, 2.6+면 기본 내장을 확인한다.**
4. **같은 문장 세트를 양쪽에 넣어 토큰 스트림을 바이트 단위로 비교한다.** 도메인 용어·복합명사·접두사가 든 문장을 반드시 포함한다.

핵심 한 줄 — **분석기 자체보다, 내 튜닝을 옮길 수 있느냐가 전환 리스크를 정한다.**

## 아직 검증 안 된 것

블로그로 단정하기 전에 대상 버전에서 직접 확인해야 할 것들을 남겨 둔다.

- **사전 키 표기** — Milvus 문서가 `dict_kind`와 `dict`로 엇갈린다. 대상 버전 스키마로 확정.
- **분해 모드·독음·숫자 — 미노출인가 미지원인가** — 사용자 사전은 공개 feature request라 미지원이 확실하지만, 나머지 셋은 lindera 엔진에 능력이 있어도 Milvus가 파라미터로 안 여는 것일 수 있다. 릴리스 노트·소스로 재확인하면 판정이 바뀔 여지가 있다.
- **동의어 그래프** — Milvus `synonym`이 OpenSearch `synonym_graph`의 다중어 처리까지 동일한지는 복합 규칙이 많으면 검증 필요.

"재현 불가"로 적은 항목의 1차 근거는 "공식 문서 필터 목록에 없음"이다.
사용자 사전을 빼면 Milvus가 명시적으로 "지원 안 함"이라 쓴 건 아니므로, 대상 버전에서 직접 찍어보는 검증을 권한다.

## 참고 링크

- [Elasticsearch: Korean (nori) analysis plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori)
- [nori_tokenizer 레퍼런스](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer)
- [nori_part_of_speech 레퍼런스](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-speech)
- [Elastic 블로그: Nori 소개 (Viterbi·mecab-ko-dic)](https://www.elastic.co/blog/nori-the-official-elasticsearch-plugin-for-korean-language-analysis)
- [Lindera GitHub](https://github.com/lindera/lindera)
- [Milvus: Analyzer Overview](https://milvus.io/docs/analyzer-overview.md)
- [Milvus: Lindera tokenizer](https://milvus.io/docs/lindera-tokenizer.md)
- [Milvus: Choose the Right Analyzer](https://milvus.io/docs/choose-the-right-analyzer-for-your-use-case.md)
- [Milvus 2.6 다국어 하이브리드 검색](https://milvus.io/blog/how-milvus-26-powers-hybrid-multilingual-search-at-scale.md)
