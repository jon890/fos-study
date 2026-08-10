---
thumbnail: ./images/langgraph-checkpoint-durable-execution-thumbnail.jpg
series: "LangGraph로 에이전트 워크플로 만들기"
seriesOrder: 3
tags: [심화]
---

# LangGraph Checkpoint — 장애와 중단에서 살아남는 실행

> [LangGraph State와 Reducer](./langgraph-state-and-reducer.md)에서 이어진다.

LangGraph를 배우면서 "이거 어디서 본 구조인데"라는 느낌이 가장 강했던 부분이 checkpoint다.
Spring Batch를 써봤다면 이미 아는 개념이 거의 그대로 온다.

이 글에서 가져갈 것은 세 가지다.

- checkpoint는 **단계마다 상태 전체를 저장소에 스냅샷으로 남기는 것**이다.
- 그래서 장애 재개, 며칠짜리 사람 승인, 과거 시점 복원이 가능해진다.
- 대신 **노드는 재개할 때 처음부터 다시 실행된다.** 이걸 모르면 부작용이 중복된다.

---

## Spring Batch를 알면 절반은 안다

| Spring Batch | LangGraph | 역할 |
| --- | --- | --- |
| `JobInstance` | `thread_id` | 실행 단위를 식별한다 |
| `JobRepository` | checkpointer | 실행 상태를 저장한다 |
| `StepExecution` 스냅샷 | checkpoint | 한 단계가 끝난 시점의 상태 |
| `ExecutionContext` | `State` | 단계 사이로 흐르는 데이터 |
| 실패한 Step부터 재시작 | 중단 지점부터 재개 | 처음부터 다시 하지 않는다 |
| `JobRepository` 미설정 시 인메모리 | `InMemorySaver` | 재시작하면 사라진다 |

발상이 같은 이유는 풀려는 문제가 같아서다.
여러 단계로 이뤄진 긴 작업이 중간에 실패했을 때, 처음부터 다시 하지 않으려면 어디까지 했는지를 밖에 남겨야 한다.

차이도 있다. Spring Batch는 Step 단위로 저장하지만, LangGraph는 **super-step 단위**로 저장한다.
super-step은 병렬로 실행되는 노드들을 묶은 한 묶음이라, 병렬 분기가 있으면 여러 노드가 한 checkpoint에 함께 반영된다.

---

## 붙이는 방법

`compile()`에 checkpointer를 넘기고, 호출할 때 `thread_id`를 준다.

```python
from langgraph.checkpoint.postgres import PostgresSaver

graph = builder.compile(checkpointer=PostgresSaver(conn))

config = {"configurable": {"thread_id": "persona-1042"}}
result = graph.invoke({"question": "최근 상태가 어떤가요"}, config)
```

`thread_id`가 없으면 checkpointer를 붙여도 저장되지 않는다.
그리고 이 값은 255자를 넘기지 말라고 공식 문서가 명시한다.

같은 `thread_id`로 다시 호출하면 이전 상태를 이어받는다.
그래서 멀티턴 대화는 `thread_id`를 사용자 세션에 매핑하는 것으로 끝난다.

### 구현체 선택

| 구현체 | 용도 | 특징 |
| --- | --- | --- |
| `InMemorySaver` | 테스트, 로컬 실험 | 프로세스가 죽으면 사라진다 |
| `SqliteSaver` | 단일 노드 개발 환경 | 파일로 남아 재시작에 견딘다 |
| `PostgresSaver` · `AsyncPostgresSaver` | 운영 | 여러 인스턴스가 같은 상태를 공유한다 |

여러 파드가 뜨는 환경이라면 선택지는 사실상 Postgres 하나다.
`InMemorySaver`로 개발하다가 배포하면, 재시도가 다른 파드로 라우팅되는 순간 상태를 못 찾는다.

---

## 저장된 상태로 무엇을 할 수 있나

checkpointer가 붙으면 그래프 객체로 상태를 조회하고 조작할 수 있다.

```python
# 현재 상태
snapshot = graph.get_state(config)

# 전체 이력 (최신순)
for snap in graph.get_state_history(config):
    print(snap.config, snap.values)

# 상태를 사람이 고쳐서 덮어쓰기
graph.update_state(config, {"question": "고쳐 쓴 질문"})
```

`get_state()`가 돌려주는 `StateSnapshot`에는 그 시점의 값과 그 checkpoint를 가리키는 config가 들어 있다.

### 과거 시점부터 다시 실행하기

이력에서 특정 checkpoint의 config를 꺼내 그걸로 다시 호출하면, 그 지점부터 실행이 갈라진다.

```python
history = list(graph.get_state_history(config))
target = history[3]                       # 4단계 전 시점

graph.invoke(None, target.config)         # 그 시점에서 다시 진행
```

디버깅에서 가치가 크다.
"3번째 검색에서 이상한 문서를 가져왔다"를 확인했을 때, 그 직전 상태로 돌아가 조건만 바꿔 재현할 수 있다.
로그만 보고 추측하는 것과 실제로 그 상태를 다시 돌려보는 것은 확인의 강도가 다르다.

---

## 노드는 재개할 때 처음부터 다시 실행된다

여기가 실제로 사람을 다치게 하는 부분이다.

LangGraph는 **노드 단위로 재개**한다.
중단된 노드는 그 안의 어느 줄에서 멈췄든 상관없이 **함수 첫 줄부터 다시 실행**된다.
공식 문서도 노드를 멱등하게 설계하라고 명시한다.

```python
def notify_and_record(state: State) -> dict:
    send_sms(state["guardian_phone"])          # 부작용
    record_id = db.insert_care_alert(state)    # 부작용
    result = interrupt("보호자 통보를 승인할까요")   # 여기서 멈춘다
    return {"record_id": record_id, "approved": result}
```

이 노드가 재개되면 `send_sms`와 `db.insert_care_alert`가 **한 번 더 실행된다.**
문자가 두 번 가고 알림 레코드가 중복 생성된다.

고치는 방법은 세 가지다.

**부작용을 중단 지점 뒤로 옮긴다.** 가장 단순하고 확실하다.

```python
def notify_and_record(state: State) -> dict:
    approved = interrupt("보호자 통보를 승인할까요")   # 먼저 멈춘다
    if not approved:
        return {"approved": False}
    send_sms(state["guardian_phone"])              # 재개 후 한 번만
    return {"record_id": db.insert_care_alert(state), "approved": True}
```

**멱등 키를 쓴다.** 외부 시스템 호출을 옮길 수 없을 때다.
`thread_id`와 단계 번호를 조합한 키로 중복 요청을 서버 쪽에서 걸러낸다.
결제 API에 idempotency key를 붙이는 것과 같은 방식이다.
[운영 환경의 실패 분류와 재시도 설계](./langgraph4j-production-operations.md)는 영속 saver와 함께 따로 다룬다.

**부작용을 별도 노드로 분리한다.** 중단이 있는 노드와 부작용이 있는 노드를 아예 나눈다.
재실행 범위가 좁아져서 사고 가능성이 줄어든다.

> 이 규칙은 LangGraph만의 특이사항이 아니다.
> 재시도 가능한 시스템을 만들 때 늘 나오는 요구다.
> 다만 LangGraph는 재개가 기본 동작이라 이 요구를 피해 갈 수 없게 만든다.

---

## thread 안과 밖 — checkpointer와 Store

checkpointer가 저장하는 건 **한 thread 안의 실행 상태**다.
thread를 넘어서 유지되어야 하는 값은 별도 장치인 Store가 담당한다.

| | checkpointer | Store |
| --- | --- | --- |
| 범위 | thread 하나 | thread 전체 |
| 저장 대상 | 그래프 실행 상태 | 애플리케이션이 정한 키와 값 |
| 예시 | 지금 어느 단계인지, 지금까지 모은 근거 | 이 대상자의 기저질환, 선호하는 응대 방식 |
| 수명 | 그 실행이 끝나면 역할이 끝난다 | 계속 남는다 |

돌봄 분석으로 예를 들면 이렇게 나뉜다.

- checkpointer — 이번 분석에서 어떤 기록을 읽었고 몇 번 재검색했는지
- Store — 이 대상자가 청력이 약해 문자를 선호한다는 사실

이 둘을 섞으면 두 방향으로 문제가 생긴다.
장기 정보를 상태에 담으면 매 단계 직렬화 비용이 붙고, 실행 상태를 Store에 담으면 재개가 안 된다.

---

## 저장 비용은 상태 크기에 비례한다

단계마다 상태 **전체**가 직렬화된다.
그래서 2편에서 다룬 상태 크기 문제가 여기서 실제 비용으로 나타난다.

```
상태 크기 40KB × 노드 8개 = 320KB   (한 번 실행에 쌓이는 양)
대상자 1,000명 × 하루 1회 = 하루 약 320MB
30일 = 약 9.6GB
```

공식 문서도 checkpoint가 쌓인다는 점을 명시하며 정리 정책을 두라고 권한다.
실무에서 붙일 장치는 세 가지다.

- 상태에는 다음 노드가 실제로 쓰는 값만 둔다. 문서 원문 대신 ID와 발췌만 넣는다.
- 완료된 thread의 checkpoint는 보존 기간을 정해 지운다.
- 재개가 필요 없는 그래프에는 checkpointer를 아예 붙이지 않는다.

마지막 항목이 중요하다.
**checkpointer는 공짜가 아니다.** 단발 분류나 요약처럼 응답을 주면 잊어도 되는 작업에 붙이면 DB 쓰기만 늘어난다.

---

## 그래프를 고쳐도 기존 thread가 살아남나

운영에서 곧 만나게 되는 질문이다. 공식 문서가 답하는 범위는 이렇다.

| 상황 | 가능 여부 |
| --- | --- |
| 이미 끝난 thread | 그래프 구조를 자유롭게 바꿔도 된다 |
| 중단된 상태의 thread | 구조 변경은 되지만 **노드 이름 변경과 삭제는 안 된다** |
| 상태 키 추가·제거 | 호환된다 |
| 상태 키 이름 변경 | 이전 값을 잃는다 |

중단된 thread가 남아 있는 상태로 배포하면서 노드 이름을 바꾸면 그 thread는 재개할 수 없다.
사람 승인을 기다리는 흐름이 있다면 배포 전에 대기 중인 thread를 확인하는 절차가 필요하다.

---

## Java와 JavaScript에서는

<details>
<summary>Java (langgraph4j) — CheckpointSaver</summary>

`CompileConfig`에 saver를 넘기는 구조다.

```java
import org.bsc.langgraph4j.CompileConfig;
import org.bsc.langgraph4j.RunnableConfig;
import org.bsc.langgraph4j.checkpoint.MemorySaver;

var compileConfig = CompileConfig.builder()
    .checkpointSaver(new MemorySaver())
    .build();

var graph = stateGraph.compile(compileConfig);

var runConfig = RunnableConfig.builder()
    .threadId("persona-1042")
    .build();

var result = graph.invoke(Map.of("question", "최근 상태가 어떤가요"), runConfig);
```

운영용 저장소 모듈이 별도 아티팩트로 나와 있다.
Postgres, MySQL, SQLite, Redis, DynamoDB, Oracle, CockroachDB, Hazelcast를 지원한다.

```kotlin
// Gradle
implementation("org.bsc.langgraph4j:langgraph4j-core:1.8.24")
implementation("org.bsc.langgraph4j:langgraph4j-postgres-saver:1.8.24")
```

Spring Boot 환경이라면 `langgraph4j-studio-springboot`를 함께 넣어 그래프 구조와 실행 이력을 웹 UI로 볼 수 있다.
</details>

<details>
<summary>JavaScript (LangGraph.js) — checkpointer</summary>

```typescript
import { MemorySaver } from "@langchain/langgraph";

const graph = builder.compile({ checkpointer: new MemorySaver() });

const config = { configurable: { thread_id: "persona-1042" } };
await graph.invoke({ question: "최근 상태가 어떤가요" }, config);

const snapshot = await graph.getState(config);
for await (const snap of graph.getStateHistory(config)) {
  console.log(snap.values);
}
```

운영에서는 `@langchain/langgraph-checkpoint-postgres` 같은 별도 패키지를 쓴다.
</details>

---

## 읽고 바로 따라 해보기

checkpoint는 저장 코드를 보기 전에 식별자와 재실행 의미를 설계해야 한다.

1. 한 사용자가 동시에 두 계획을 검토하는 상황을 만든다.
2. 사용자 ID와 각 작업의 thread ID를 따로 적는다.
3. 입력, 정규화, 검토, 계획 작성 뒤에 어떤 상태가 저장될지 그린다.
4. 검토가 끝난 과거 checkpoint에서 계획 작성만 다시 실행하는 상황을 만든다.
5. 이미 외부에 저장한 결과가 있다면 재실행 때 무엇이 중복되는지 표시한다.

이 글에서 State, checkpoint와 thread를 먼저 구분한다.
재개, 과거 상태에서의 분기와 영속 저장소 운영은 [LangGraph4j 실무 운영](./langgraph4j-production-operations.md)으로 이어진다.
직접 코드를 작성할 때는 [LangGraph4j in Action 저장소](https://github.com/jon890/langgraph4j-in-action)를 사용한다.

코드 실습에서는 메모리 저장소로 실행 의미부터 확인하고, 데이터베이스 연결은 마지막에 한다.
저장소와 재개 동작을 동시에 디버깅하지 않기 위해서다.

---

## 다음 편

checkpoint가 있으면 실행을 **멈췄다가 이어갈 수** 있다.
4편에서는 그 위에 사람 승인을 얹는 Human-in-the-Loop를 다룬다.
공식 문서가 경고하는 함정이 다섯 가지 있는데, 그중 절반이 이 글에서 다룬 재실행 문제에서 나온다.

---

## 참고

- [Docs by LangChain — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Docs by LangChain — Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [langgraph4j GitHub](https://github.com/langgraph4j/langgraph4j)
