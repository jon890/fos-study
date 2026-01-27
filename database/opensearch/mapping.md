# Mapping

- OpenSearch의 데이터 타입은 인덱스의 **Mapping**을 통해 결정 됨
  - 데이터가 어떻게 저장되고 검색될지 결정하는 핵심 요소

## 1. OpenSearch의 주요 데이터 타입

- **String Types**:
  - `text` : 전문 검색(Full-text search)용. Analyzed
  - `keyword` : 정확한 값(Exact value)용. Not Analyzed
- **Numeric Types**:
  - `long`, `integer`, `short`, `byte`, `double`, `float`, `half_float`, `scaled_float`
- **Date Types**:
  - `date`, `date_nanos`
- **Boolean**:
  - `boolean`
- **Binary**:
  - `binary` (Base64 인코딩된 문자열)
- **Range Types**:
  - `integer_range`, `float_range`, `long_range`, `double_range`, `date_range`, `ip_range`
- **Complex Types**:
  - `object`: JSON 객체 (기본값)
  - `nested`: 객체 배열을 독립적으로 쿼리해야 할 떄 사용 (내부적으로 별도 문서로 색인)
- **Geo Types**:
  - `geo_point` (위도/경도), `geo_shape` (복잡한 지형)
- **Specialised Types**:
  - `ip`, `completion` (자동완성), `token_count`, `percolator`

## 2. `text` vs `keyword`의 결정적 차이

이 두 타입의 차이는 **데이터를 저장할 떄 분석기(Analyzer)를 거치느냐, 거치지 않느냐**에 있다. <br>
이 차이가 검색(Search), 정렬(Sorting), 집계(Aggregation)의 동작 방식을 완전히 바꾼다.

### `text` 타입 (Full-Text Search)

- **동작 원리**:
  - 데이터 저장 시 **Analyzer**를 통과한다.
  - 문장을 토큰 단위로 쪼개고, 소문자로 변환하거나 불용어를 제거하는 등의 정제 과정을 거쳐 **역색인(Inverted Index)**을 생성한다.
- **용도**:
  - 본문 검색, 이메일 내요으, 제품 설명 등 긴 텍스트의 내용을 검색할 떄
- **특징**:
  - `Standard Analyzer` 기준, "Apple Pie"는 `["apple", "pie"]`로 저장된다.
  - 대소문자 구분 없이 검색 가능 하다 (일반적인 설정 시)
  - 주의: 기본적으로 정렬이나 집계에 사용할 수 없다. (메모리를 많이 소모하는 `fielddata`를 켜야 하는데, 성능상 권장하지 않음)

### `keyword` 타입 (Exact Match)

- **동작 원리**:
  - 데이터를 들어온 **그대로(Verbatim)** 단일 토큰으로 저장한다.
  - 분석기를 거치지 않는다
- **용도**:
  - ID, 이메일 주소, 상태 코드, 태그ㅜ, 카테고리 등 정확한 일치가 필요한 필드
- **특징**:
  - "Apple Pie"는 `["Apple Pie"]`라는 하나의 토큰으로 저장된다.
  - `apple`로 검색하면 검색되지 않는다. 반드시 `Apple Pie` 전체가 일치해야 한다.
  - **Doc Values**라는 열 지향(Columnar) 저장소 구조를 사용하여 **정렬과 집계**에 최적화 되어있다.

## 3. 비교 예시 및 검증

가장 흔히 하는 실수는 `keyword` 필드에 대해 부분 검색을 시도하거나, `text` 필드에 대해 정확한 일치를 기대하는 것이다.

### (1) 인덱스 매핑 생성

```json
PUT /dev_index
{
  "mappings": {
    "properties": {
      "product_desc": { "type": "text" },      // 분석됨
      "product_category": { "type": "keyword" } // 분석 안 됨 (정확한 값)
    }
  }
}
```

### (2) 데이터 삽입

```json
POST /dev_index/_doc/1
{
  "product_desc": "Super Fast Laptop",
  "product_category": "Electronics"
}
```

### (3) 검색 결과 차이

| 쿼리 타입 | 대상 필드        | 검색어              | 결과 | 원인                                                             |
| --------- | ---------------- | ------------------- | ---- | ---------------------------------------------------------------- |
| Match     | product_desc     | "laptop"            | 성공 | Super, Fast, Latop 으로 토크나이징 되어있고 소문자 처리됨        |
| Term      | product_desc     | "Super Fast Laptop" | 실패 | 텀 쿼리는 정확한 토큰을 찾는데 역색인에는 쪼개진 단어들만 존재함 |
| Term      | product_category | "Electronics"       | 성공 | 저장된 값 Electronics와 정확히 일치                              |
| Term      | product_category | "electronics"       | 실패 | keyword는 대소문자를 구분함                                      |

## 4. 실무 팁: Multi-fields (멀티 필드)

실무에서는 하나의 필들르 검색 용도와 정렬/집계 용도로 모두 사용해야 하는 경우가 많다 <br>
이 때 `fields` 속성을 사용한다

```json
{
  "mappings": {
    "properties": {
      "user_name": {
        "type": "text", // 검색용 (analyzed)
        "fields": {
          "raw": {
            "type": "keyword" // 정렬/집계용 (exact match)
          }
        }
      }
    }
  }
}
```

- 검색 시 : `user_name` 필드 사용 (유사도 검색)
- 정렬/집계 시 : `user_name.raw` 필드 사용 (정확한 값 기준)
