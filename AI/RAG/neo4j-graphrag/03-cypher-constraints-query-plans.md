---
categories: [database]
tags: [심화]
---

# Cypher, 제약, 쿼리 계획으로 검색 안정화하기

GraphRAG에서 Cypher는 그래프를 읽는 문법이 아니라 컨텍스트 제공자의 품질 장치다.
제약은 중복과 결측을 막고, 인덱스와 실행 계획은 관계 탐색이 어디서 터지는지 드러낸다.

> 이전 글: [속성 그래프와 온톨로지 모델링](./02-property-graph-ontology-modeling.md)

이 글은 Neo4j 2026 계열과 Cypher 25 문서를 기준으로 쓴다.
특히 벡터 인덱스 조회는 Neo4j 2026.01부터 `SEARCH` 절이 권장 흐름이고, 기존 `db.index.vector.queryNodes()` 절차는 2026.04부터 deprecated로 표시된다.

이 글은 세 질문에 답한다.

- `Document`, `Chunk`, `Claim`, `Evidence`의 식별성과 출처를 어떻게 강제할 것인가.
- 관계 탐색 질의가 전체 스캔으로 무너지는지 어떻게 볼 것인가.
- 벡터 후보와 그래프 경로를 Cypher에서 어떻게 합칠 것인가.

가져갈 판단 기준은 세 가지다.

- 식별자와 출처는 애플리케이션 코드가 아니라 데이터베이스 제약으로도 막는다.
- `EXPLAIN`은 계획을 보고, `PROFILE`은 실제 비용을 볼 때만 쓴다.
- 벡터 점수와 그래프 경로는 같은 점수처럼 더하지 않는다.

## 제약은 컨텍스트의 안전장치다

Neo4j 제약은 그래프 데이터의 품질과 무결성을 지키는 장치다.
공식 문서는 유일성, 존재, 타입, 키 제약을 구분한다.
일부 제약은 Enterprise Edition에서만 쓸 수 있다.

컨텍스트 제공자에서 제약이 필요한 이유는 단순하다.
`Document`가 중복되거나 `Chunk`가 원문 없이 만들어지면 답변의 출처를 검증할 수 없다.

공식 문서 문법을 기반으로 하면 다음 같은 제약을 생각할 수 있다.
아직 실행한 예제가 아니라 설계 예시다.

```cypher
CREATE CONSTRAINT document_id IF NOT EXISTS
FOR (d:Document)
REQUIRE d.document_id IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
FOR (c:Chunk)
REQUIRE c.chunk_id IS UNIQUE;

CREATE CONSTRAINT claim_id IF NOT EXISTS
FOR (c:Claim)
REQUIRE c.claim_id IS UNIQUE;

CREATE CONSTRAINT evidence_id IF NOT EXISTS
FOR (e:Evidence)
REQUIRE e.evidence_id IS UNIQUE;
```

Community Edition에서도 노드와 관계 속성 유일성 제약은 사용할 수 있다.
반면 존재 제약, 타입 제약, 키 제약은 Enterprise Edition 차이를 확인해야 한다.
Neo4j 2026 문서의 graph types도 Enterprise Edition에서 시작했고, 2026.06부터 일반 제공 상태로 설명된다.

학습 단계에서는 유일성 제약부터 둔다.
운영 설계로 넘어가면 존재와 타입 제약, graph types를 검토한다.

## 인덱스는 시작점을 좁힌다

Cypher는 패턴을 선언적으로 적는다.
그 뒤 planner가 현재 데이터베이스 상태를 바탕으로 실행 계획을 만든다.

일반 검색 성능 인덱스는 `MATCH` 절에서 자동으로 쓰일 수 있다.
반대로 semantic index 계열인 벡터 인덱스는 자동으로 아무 질의에나 붙지 않는다.
Neo4j 2026.01 이후에는 Cypher 25의 `SEARCH` 절로 벡터 인덱스를 명시적으로 사용한다.

컨텍스트 제공자에서 자주 필요한 인덱스는 두 종류다.

| 목적 | 인덱스 후보 | 쓰임 |
| --- | --- | --- |
| 정확한 시작점 | `Service.name`, `API.path`, `Repository.name` | 질문에서 식별한 엔티티로 시작한다 |
| 후보 청크 검색 | `Chunk.embedding` 벡터 인덱스 | 의미 후보를 만든 뒤 그래프 경로로 확장한다 |

벡터 인덱스 생성 예시는 공식 문서 문법을 일반화한 것이다.

```cypher
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk)
ON c.embedding
OPTIONS { indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

Neo4j 2026.06 문서에는 `vector.default_search_expansion_factor`와 `vector.quantization.type` 같은 설정도 나온다.
검색 확장 계수는 정확도를 높일 수 있지만 질의 시간이 늘 수 있다.
양자화는 메모리와 속도를 얻는 대신 정확도를 조금 잃을 수 있다.

이 값들은 처음부터 튜닝하지 않는다.
먼저 기준선 질문에서 필수 근거 재현율과 지연을 측정한 뒤 바꾼다.

## `SEARCH`는 후보 생성이고, 그래프 탐색은 그 다음이다

Cypher 25의 `SEARCH`는 `MATCH` 안에서 벡터 인덱스 결과로 패턴을 제한한다.
공식 문서의 핵심은 `SEARCH`가 독립 절이 아니라 `MATCH`와 `OPTIONAL MATCH` 안에서 쓰이는 하위 절이라는 점이다.

컨텍스트 제공자에서는 다음처럼 생각할 수 있다.

```cypher
MATCH (chunk:Chunk)
  SEARCH chunk IN (
    VECTOR INDEX chunk_embedding
    FOR $queryEmbedding
    LIMIT 20
  ) SCORE AS vectorScore
MATCH (chunk)-[:PART_OF]->(doc:Document)
WHERE $user_group IN doc.allowed_groups
OPTIONAL MATCH (claim:Claim)-[:SUPPORTED_BY]->(:Evidence)-[:LOCATED_IN]->(chunk)
RETURN chunk.chunk_id AS chunk_id,
       doc.document_id AS document_id,
       claim.claim_id AS claim_id,
       vectorScore AS vectorScore
LIMIT 10;
```

이 예시는 실행 결과가 아니라 공식 문서 문법을 바탕으로 한 일반화 예시다.
실제 관계 타입은 앞 글에서 정한 모델과 맞춰야 한다.
또한 `WHERE $user_group IN doc.allowed_groups`는 벡터 후보를 만든 뒤 적용되는 후처리다.
여러 권한 범위가 섞인 인덱스의 엄격한 후보 선필터로 사용하면 안 된다.
권한이 필요한 검색은 필터 가능한 단일 범위 속성이나 접근 범위별 검색 공간에서 시작해야 한다.

중요한 점은 순서다.
벡터 후보를 먼저 만들 수는 있다.
하지만 권한 필터와 원문 추적을 통과하지 못하면 최종 컨텍스트로 내보내지 않는다.

## 쿼리 계획은 의심할 때 보는 것이 아니다

Neo4j 문서에 따르면 `EXPLAIN`은 질의를 실행하지 않고 계획과 예상 행 수를 보여준다.
`PROFILE`은 질의를 실제 실행하고 DB hits 같은 실측 값을 보여준다.
또한 `PROFILE`을 붙인 쓰기 질의는 실제로 데이터를 쓸 수 있으므로 주의해야 한다.

학습 프로젝트에서는 읽기 질의부터 본다.

```cypher
EXPLAIN
MATCH (service:Service {service_id: $service_id})-[:AFFECTED_BY]->(incident:Incident)
MATCH (claim:Claim)-[:ABOUT]->(incident)
MATCH (claim)-[:SUPPORTED_BY]->(:Evidence)-[:LOCATED_IN]->(chunk:Chunk)-[:PART_OF]->(doc:Document)
WHERE $user_group IN doc.allowed_groups
RETURN incident.incident_id, chunk.chunk_id;
```

계획에서 확인할 것은 세 가지다.

- 시작점이 `Service.service_id` 제약 인덱스를 타는가.
- 중간 확장에서 예상 행 수가 갑자기 커지는가.
- 마지막 `Document` 권한 필터가 너무 늦게 적용되는가.

그다음 읽기 전용 데이터에서 `PROFILE`로 실제 DB hits와 rows를 본다.
예상 행 수와 실제 행 수가 크게 다르면 통계, 인덱스, 모델링 중 하나를 의심해야 한다.

## 정량 트레이드오프

그래프 탐색은 `top_k`를 키우면 안정적으로 좋아지지 않는다.
후보가 늘면 관계 확장 비용도 같이 커진다.

단순 계산을 해보자.

- 벡터 후보 `top_k = 20`
- 후보 청크당 연결 엔티티 평균 5개
- 엔티티당 관련 문서 평균 8개

최악의 단순 확장은 `20 * 5 * 8 = 800`개 문서 후보가 된다.
권한 필터와 중복 제거가 늦으면 LLM에 전달되기 전에 이미 비용이 커진다.

반대로 `top_k = 5`로 줄이면 확장 후보는 200개로 줄지만 필수 근거를 놓칠 수 있다.
따라서 튜닝 기준은 지연 하나가 아니다.

- 필수 근거 재현율
- 권한 위반 수
- `PROFILE`의 DB hits와 rows
- 최종 컨텍스트 토큰 수

이 네 값을 함께 봐야 한다.

## 실패 모드

| 실패 모드 | 증상 | 확인 방법 |
| --- | --- | --- |
| 숨은 전체 스캔 | 데이터가 늘수록 질의가 갑자기 느려진다 | `EXPLAIN`에서 시작 연산자와 인덱스 사용을 본다 |
| 늦은 권한 필터 | 권한 밖 경로를 많이 확장한 뒤 버린다 | `PROFILE`에서 필터 전후 rows를 비교한다 |
| 점수 오용 | 벡터 점수와 전문 검색 점수를 그대로 더한다 | 출처별 순위를 따로 보고 후처리한다 |
| 제약 부재 | 같은 `Document`나 `Chunk`가 중복된다 | 유일성 제약과 중복 적재 테스트를 둔다 |

특히 점수 오용을 조심해야 한다.
Neo4j 문서는 `SEARCH`의 점수가 벡터 유사도 점수이며, 다른 점수 소스와 원시 값을 직접 비교하지 말라고 안내한다.
하이브리드 검색을 쓸 때는 각 소스의 순위를 따로 다루는 편이 안전하다.

## 언제 쓰지 말아야 하는가

Cypher 튜닝으로 모든 문제를 해결하려 하면 안 된다.

- 엔티티 추출 품질이 낮아 관계 자체가 틀린 경우
- 문서 권한 메타데이터가 없어서 필터 기준이 없는 경우
- 질문이 단순 의미 검색이라 그래프 확장이 잡음만 늘리는 경우
- 데이터가 작아 인덱스와 계획 튜닝보다 모델 검증이 더 중요한 경우

이때는 Cypher를 고치는 것이 아니라 앞 단계로 돌아가야 한다.
모델, 추출, 평가 질문이 먼저다.

## 작은 실습

실습 목표는 같은 질의를 인덱스와 제약 유무에 따라 비교하는 것이다.
Neo4j 인스턴스가 필요하며, 아래 명령은 공식 문서 문법에 맞춘 일반화 예시다.

재현 단계다.

- `Document`, `Chunk`, `Service`, `Incident`, `Claim`, `Evidence` 샘플 노드를 적재한다.
- `document_id`, `chunk_id`, `service_id`, `claim_id`, `evidence_id` 유일성 제약을 만든다.
- 표시 속성 검색을 위해 `Service.name`에 일반 인덱스를 만든다.
- `Chunk.embedding`에 벡터 인덱스를 만든다.
- 관계형 질문 하나를 `EXPLAIN`으로 본다.
- 같은 질의를 읽기 전용 샘플에서 `PROFILE`로 실행한다.

확인할 결과다.

- 중복 `chunk_id` 적재가 실패해야 한다.
- `Service.service_id` 정확 조회는 유일성 제약 인덱스를 사용해야 한다.
- `Service.name` 표시 속성 조회는 일반 인덱스를 사용해야 한다.
- 권한 필터 뒤 최종 반환 청크가 모두 접근 가능한 `Document`에 속해야 한다.

실패 판정이다.

- 제약이 있는데 중복 노드가 들어가면 스키마가 잘못됐다.
- `PROFILE`에서 중간 rows가 예상보다 크게 튀면 관계 방향이나 시작점이 잘못됐을 수 있다.
- 권한 필터가 없는 쿼리가 컨텍스트 제공자 코드로 들어가면 실패다.

## 다음 글

다음 글에서는 Neo4j GraphRAG Python의 Knowledge Graph Builder와 Pipeline을 읽고, 문서에서 그래프를 만드는 실습 경계를 정한다.

- [문서에서 근거를 보존한 지식 그래프 구축하기](./04-knowledge-graph-builder.md)

## 참고 링크

- Neo4j Cypher queries: https://neo4j.com/docs/cypher-manual/current/queries/
- Neo4j Cypher constraints: https://neo4j.com/docs/cypher-manual/current/schema/constraints/
- Neo4j create constraints: https://neo4j.com/docs/cypher-manual/current/schema/constraints/create-constraints/
- Neo4j search-performance indexes: https://neo4j.com/docs/cypher-manual/current/indexes/search-performance-indexes/
- Neo4j vector indexes: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/
- Neo4j Cypher 25 SEARCH: https://neo4j.com/docs/cypher-manual/25/clauses/search/
- Neo4j execution plans: https://neo4j.com/docs/cypher-manual/current/planning-and-tuning/execution-plans/
- Neo4j graph types: https://neo4j.com/docs/cypher-manual/current/schema/graph-types/
