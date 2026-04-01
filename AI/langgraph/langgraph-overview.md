# LangGraph — 에이전트 워크플로를 그래프로 통제하기

AI 에이전트를 만들다 보면 "LLM을 한 번 호출하고 끝"이 아니라, 조건에 따라 분기하고, 루프를 돌고, 중간에 사람이 개입하고, 실패하면 다시 시도하는 식의 복잡한 흐름이 필요한 순간이 온다. LangGraph는 그 흐름을 **그래프**로 표현하고 통제하는 프레임워크다.

---

## LangGraph가 뭔지

LangGraph는 LangChain 생태계에서 만든 오픈소스 프레임워크다. 에이전트 워크플로를 **노드(Node)와 엣지(Edge)로 구성된 방향 그래프**로 정의해서, LLM 호출 → 툴 실행 → 결과 판단 → 다음 단계 결정 같은 흐름을 코드로 명확하게 표현할 수 있다.

LangChain v1.0부터는 모든 LangChain 에이전트가 LangGraph 위에서 동작한다. 사실상 LangChain 에이전트의 실행 엔진이 LangGraph로 바뀐 셈이다.

단순히 "LLM에 툴을 붙이는" 수준을 넘어서, 실패 복구, 장기 실행, 사람 개입, 멀티 에이전트 조율 같은 프로덕션 수준의 요구사항을 다루기 위해 만들어졌다.

---

## 핵심 개념 4가지

### 1. State — 그래프를 흐르는 공유 메모리

State는 그래프 전체를 흐르는 공유 상태 객체다. 메시지 히스토리, 중간 결과, 변수, 판단 이력 같은 정보를 담는다. 각 노드는 State를 받아서 처리하고, 업데이트된 State를 다음 노드로 넘긴다.

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]
    next_step: str
```

`add_messages`처럼 **reducer 함수**를 붙이면 State 필드를 어떻게 병합할지 정의할 수 있다. 메시지는 덮어쓰지 않고 누적되어야 하니까.

### 2. Nodes — 실제 작업을 하는 함수

노드는 Python 함수다. State를 받아서 처리하고, 업데이트할 State 딕셔너리를 반환한다. LLM 호출, 툴 실행, 데이터 처리 — 실제 작업은 모두 노드 안에서 일어난다.

```python
def call_llm(state: State):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def run_tool(state: State):
    tool_result = some_tool.run(...)
    return {"messages": [tool_result]}
```

### 3. Edges — 다음에 어디로 갈지

엣지는 노드 간 연결이다. 두 종류가 있다.

**일반 엣지**: 항상 같은 노드로 간다.
```python
graph.add_edge("node_a", "node_b")
```

**조건부 엣지**: State를 보고 다음 노드를 동적으로 결정한다. 여기가 핵심이다.
```python
def should_continue(state: State) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

graph.add_conditional_edges("llm", should_continue)
```

LLM 응답에 툴 호출이 있으면 툴 노드로, 없으면 종료. 이 패턴이 ReAct 에이전트의 기본 루프다.

### 4. Graph — 전체 흐름 조립

노드와 엣지를 조립해서 그래프를 만든다.

```python
from langgraph.graph import StateGraph, END

builder = StateGraph(State)
builder.add_node("llm", call_llm)
builder.add_node("tools", run_tool)

builder.set_entry_point("llm")
builder.add_conditional_edges("llm", should_continue)
builder.add_edge("tools", "llm")  # 툴 실행 후 다시 LLM으로

graph = builder.compile()
```

흐름은 이렇다: `llm` → (툴 호출 있으면) `tools` → 다시 `llm` → (툴 호출 없으면) `END`. LLM이 충분한 정보를 모을 때까지 루프를 돈다.

---

## 뭘 만들 수 있나

### ReAct 에이전트 (가장 기본)
LLM이 생각하고(Reasoning) → 툴을 쓰고(Acting) → 결과를 보고 다시 생각하는 루프. 검색, 계산, API 호출 같은 툴을 LLM이 자율적으로 조합해서 사용한다.

### 코딩 에이전트
코드 작성 → 실행 → 에러 확인 → 수정 → 다시 실행 루프. LLM이 코드를 작성하고, 실행 결과를 받아서 디버깅까지 스스로 한다. Replit이 실시간 코드 생성에 LangGraph를 쓰고 있다.

### 리서치 에이전트
질문을 받으면 → 검색 쿼리를 만들고 → 여러 소스를 탐색하고 → 결과를 종합해서 답변. 단순 검색이 아니라 멀티스텝 탐색이 필요할 때 유용하다.

### 멀티 에이전트 시스템
에이전트 여러 개를 그래프로 연결한다. 오케스트레이터 에이전트가 작업을 분배하고, 서브 에이전트들이 각자 처리한 뒤 결과를 모은다. Uber가 LangGraph로 유닛 테스트 자동 생성 파이프라인을 만들었다.

### 고객 지원 봇
의도 분류 → 해당 전문 에이전트로 라우팅 → 필요하면 사람에게 에스컬레이션. Klarna(MAU 8500만)가 이 패턴으로 고객 지원 봇을 운영 중이다.

---

## 워크플로를 어떻게 통제하나

### 조건부 엣지로 분기 제어

앞서 본 `add_conditional_edges`가 분기의 핵심이다. State를 받아서 문자열을 반환하는 함수만 있으면 된다. 반환값이 다음 노드 이름이 된다.

```python
def route_by_intent(state: State) -> str:
    intent = state["intent"]
    if intent == "refund":
        return "refund_agent"
    elif intent == "technical":
        return "tech_support_agent"
    else:
        return "general_agent"
```

### Command로 상태 업데이트와 라우팅을 동시에

노드 안에서 직접 다음 노드를 지정하고 싶을 때는 `Command`를 쓴다.

```python
from langgraph.types import Command

def my_node(state: State) -> Command:
    if state["foo"] == "bar":
        return Command(update={"foo": "baz"}, goto="next_node")
    return Command(goto="other_node")
```

조건부 엣지를 별도로 정의하지 않고 노드 내부에서 처리할 수 있어서, 복잡한 분기 로직을 노드 안에 응집시킬 수 있다.

### Checkpointer로 상태 영속화

그래프 실행 중에 State를 저장해두는 기능이다. 실패해도 중간부터 재시작할 수 있고, 대화 히스토리를 세션 간에 유지할 수 있다.

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# thread_id로 대화 세션을 구분
config = {"configurable": {"thread_id": "user-123"}}
result = graph.invoke({"messages": [...]}, config=config)
```

프로덕션에서는 MemorySaver 대신 PostgreSQL, Redis 기반 체크포인터를 쓴다.

### Human-in-the-Loop

특정 지점에서 실행을 일시정지하고 사람의 확인을 받는 패턴이다. `interrupt_before`나 `interrupt_after`로 어느 노드 전후에 멈출지 지정한다.

```python
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["dangerous_action"]  # 이 노드 실행 전에 멈춤
)

# 사람이 확인하고 재개
graph.invoke(None, config=config)  # None을 넘기면 중단 지점부터 재개
```

돈을 이체한다거나, 외부 API를 호출한다거나, 되돌리기 어려운 작업 전에 사람이 검토할 수 있다.

### 병렬 실행 (Super-steps)

의존성이 없는 노드들은 같은 super-step에서 병렬로 실행된다. Google의 Pregel 시스템에서 영감을 받은 방식이다.

```python
# node_a와 node_b를 병렬 실행한 뒤 merge_node로 모음
builder.add_edge("start", "node_a")
builder.add_edge("start", "node_b")
builder.add_edge(["node_a", "node_b"], "merge_node")
```

리서치 에이전트에서 여러 소스를 동시에 검색하거나, 멀티 에이전트에서 각 에이전트를 병렬로 실행할 때 쓴다.

---

## LangGraph.js — TypeScript/JavaScript 버전

Python 버전과 개념은 동일하고 API 형태만 다르다. `@langchain/langgraph` 패키지로 설치한다.

```bash
npm install @langchain/langgraph @langchain/core
```

Python의 `TypedDict` 대신 `Annotation.Root`로 State를 정의한다.

```typescript
import { Annotation, StateGraph, END, START } from "@langchain/langgraph";
import { BaseMessage } from "@langchain/core/messages";

// State 정의
const StateAnnotation = Annotation.Root({
  messages: Annotation<BaseMessage[]>({
    reducer: (x, y) => x.concat(y),  // Python의 add_messages에 해당
  }),
  nextStep: Annotation<string>,
});

// 노드 함수 (async 함수)
const callLLM = async (state: typeof StateAnnotation.State) => {
  const response = await llm.invoke(state.messages);
  return { messages: [response] };
};

// 조건부 엣지
const shouldContinue = (state: typeof StateAnnotation.State) => {
  const lastMessage = state.messages[state.messages.length - 1];
  if ("tool_calls" in lastMessage && lastMessage.tool_calls?.length) {
    return "tools";
  }
  return END;
};

// 그래프 조립
const graph = new StateGraph(StateAnnotation)
  .addNode("llm", callLLM)
  .addNode("tools", runTools)
  .addEdge(START, "llm")
  .addConditionalEdges("llm", shouldContinue)
  .addEdge("tools", "llm")
  .compile();
```

Python과의 주요 차이점:

| 항목 | Python | LangGraph.js |
|---|---|---|
| State 정의 | `TypedDict` + `Annotated` | `Annotation.Root` |
| 시작/종료 노드 | `set_entry_point()` / `END` | `START` / `END` 상수 |
| 노드 추가 | `builder.add_node()` | `.addNode()` 메서드 체이닝 |
| 조건부 엣지 | `add_conditional_edges()` | `.addConditionalEdges()` |
| 노드 함수 | 일반 함수 / async 모두 | async 함수 권장 |

스트리밍도 Python과 동일하게 지원한다. Next.js 같은 서버 환경에서 토큰을 스트리밍으로 클라이언트에 내려줄 때 유용하다.

```typescript
const stream = await graph.stream({ messages: [...] });
for await (const chunk of stream) {
  console.log(chunk);
}
```

---

## LangGraph4j — Java 버전

Python LangGraph에서 영감을 받은 Java 구현체다. Langchain4j, Spring AI 양쪽과 모두 연동된다. Java 17 이상 필요(JDK 8 호환 버전도 별도 제공).

```xml
<!-- Maven -->
<dependency>
    <groupId>org.bsc.langgraph4j</groupId>
    <artifactId>langgraph4j-core</artifactId>
    <version>1.5.12</version>
</dependency>

<!-- Spring AI 연동 시 추가 -->
<dependency>
    <groupId>org.bsc.langgraph4j</groupId>
    <artifactId>langgraph4j-spring-ai-agent</artifactId>
    <version>1.5.12</version>
</dependency>
```

Java에서는 State를 `AgentState`를 상속해서 정의한다. 노드는 `AsyncNodeAction` 함수형 인터페이스로 구현한다.

```java
import org.bsc.langgraph4j.StateGraph;
import org.bsc.langgraph4j.state.AgentState;

// State 정의
public class MyState extends AgentState {
    public MyState(Map<String, Object> initData) {
        super(initData);
    }

    public Optional<String> result() {
        return value("result");
    }
}

// 그래프 조립
var graph = new StateGraph<>(MyState::new)
    .addNode("llm", state -> {
        // LLM 호출 로직
        return Map.of("result", response);
    })
    .addNode("tools", state -> {
        // 툴 실행 로직
        return Map.of("toolResult", result);
    })
    .addEdge(START, "llm")
    .addConditionalEdges("llm", state -> {
        // 조건 판단
        return state.result().isPresent() ? END : "tools";
    })
    .addEdge("tools", "llm")
    .compile();

// 실행
var result = graph.invoke(Map.of("input", "질문"));
```

Python/JS와 구조는 동일하지만 Java 특유의 차이가 있다.

| 항목 | Python/JS | LangGraph4j |
|---|---|---|
| State | `TypedDict` / `Annotation` | `AgentState` 상속 |
| 노드 함수 | 일반 함수 | `AsyncNodeAction` (람다 가능) |
| 비동기 처리 | async/await | `CompletableFuture` |
| 병렬 실행 | 자동 | Fork-Join 모델 |
| 시각화 | LangSmith | 내장 Studio UI (PlantUML/Mermaid) |

특히 내장 Studio UI가 유용하다. 그래프 구조를 PlantUML이나 Mermaid 다이어그램으로 바로 시각화할 수 있어서, 복잡한 워크플로를 디버깅할 때 Python 버전보다 편한 면이 있다.

Spring AI와 조합하면 Spring Boot 애플리케이션에 에이전트를 자연스럽게 통합할 수 있다. 기존 Spring 생태계(DI, 트랜잭션, 모니터링)를 그대로 활용하면서 에이전트 워크플로를 얹는 방식이다.

---

## 정리

LangGraph의 핵심 아이디어는 단순하다. 에이전트 워크플로를 "함수(노드) + 흐름(엣지) + 공유 상태(State)"로 분리해서 표현하는 것. 이렇게 하면 복잡한 분기, 루프, 병렬 실행, 재시작을 명시적으로 제어할 수 있다.

LLM 호출 한 번으로 끝나는 단순한 작업이라면 LangGraph가 오버엔지니어링이다. 하지만 여러 단계를 거치고, 실패를 처리하고, 상태를 유지해야 하는 에이전트라면 LangGraph가 그 복잡성을 관리할 명확한 구조를 준다.

언어별로 선택 기준은 명확하다. Python은 레퍼런스 구현이라 기능이 가장 빠르게 추가된다. TypeScript/JS는 Next.js 같은 웹 프레임워크와 붙일 때 자연스럽다. Java는 Spring Boot 기반 서비스에 에이전트를 통합할 때 쓴다.

---

## 참고

- [LangGraph GitHub (Python)](https://github.com/langchain-ai/langgraph)
- [LangGraph.js GitHub](https://github.com/langchain-ai/langgraphjs)
- [LangGraph4j GitHub](https://github.com/langgraph4j/langgraph4j)
- [LangGraph Conceptual Guide (JS)](https://langchain-ai.github.io/langgraphjs/concepts/)
- [LangGraph4j 공식 문서](https://langgraph4j.github.io/langgraph4j/)
- [LangGraph Blog — 원조 소개글](https://blog.langchain.com/langgraph/)
- [Top 5 LangGraph Agents in Production 2024](https://blog.langchain.com/top-5-langgraph-agents-in-production-2024/)
- [LangGraph Deep Dive: State Machines, Tools, and Human-in-the-Loop](https://blog.premai.io/langgraph-deep-dive-state-machines-tools-and-human-in-the-loop/)
