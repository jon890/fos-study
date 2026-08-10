---
series: "LangGraph로 에이전트 워크플로 만들기"
seriesOrder: 6
tags: [심화]
categories: [java]
---

# langgraph4j 실전 — Java에서 LangGraph 돌려보기

> [Agentic GraphRAG](./langgraph-agentic-graphrag.md)에서 이어진다.
> 이 글만 Java를 본문에 두고 Python을 접이식으로 뺐다.

앞의 다섯 편은 Python 기준이었다.
공식 문서도 튜토리얼도 Python이라 배우기엔 그쪽이 낫지만, 내가 실제로 얹어야 할 곳은 Spring Boot다.

그래서 직접 붙여봤다.
**의존성을 해석하고, 컴파일하고, 실행까지 돌려서 확인한 결과**를 정리한다.
문서를 옮긴 게 아니라 실행 결과라, 버전이 올라가면 달라질 수 있다.

---

## 실측 요약

| 항목 | 확인한 값 |
| --- | --- |
| 최신 정식 릴리스 | `1.8.24` (2026년 8월 8일). 1.9.0은 beta 진행 중 |
| 컴파일 타깃 | Java 17 |
| 검증에 쓴 JVM | Temurin 21.0.11 |
| langchain4j 연동 | `langgraph4j-langchain4j` 가 langchain4j `1.18.1` 을 고정 |
| Spring AI 연동 | parent POM이 `spring-ai.version = 2.0.0` 고정 |
| 검증 범위 | 의존성 해석, 컴파일, 실제 실행까지 확인 |

---

## 함정 세 개를 먼저

붙이면서 실제로 걸린 것들이다.

### Maven Central 검색 API는 낡은 색인을 준다

처음에 `search.maven.org` 의 검색 API로 버전을 확인했더니 최신이 `1.6.0-beta5`로 나왔다.
그래서 "아직 beta라 프로덕션엔 이르다"고 판단했는데 틀렸다.

`maven-metadata.xml` 을 직접 받아보면 다르다.

```bash
curl -s https://repo1.maven.org/maven2/org/bsc/langgraph4j/langgraph4j-core/maven-metadata.xml
```

```xml
<version>1.8.22</version>
<version>1.8.23</version>
<version>1.8.24</version>
<version>1.9.0-beta1</version>
<version>1.9.0-beta2</version>
```

정식 릴리스가 1.8.24까지 나와 있었다.
**검색 API는 색인 갱신이 밀릴 수 있으니 버전 판단은 metadata에서 한다.**
이 한 번의 착오로 "beta라 위험하다"는 잘못된 결론을 낼 뻔했다.

### 버전이 조용히 갈린다

`langgraph4j-langchain4j` 는 langchain4j 1.18.1을 요구한다.
내 프로젝트는 1.18.0을 쓰고 있었다. 해석 결과를 보면 이렇게 된다.

```
dev.langchain4j:langchain4j:1.18.1              ← 1.18.1 로 올라감
dev.langchain4j:langchain4j-core:1.18.1         ← 1.18.1 로 올라감
dev.langchain4j:langchain4j-open-ai:1.18.0      ← 1.18.0 그대로
dev.langchain4j:langchain4j-http-client:1.18.0  ← 1.18.0 그대로
```

Gradle은 더 높은 버전으로 올려서 충돌을 푼다.
그런데 **내가 직접 선언한 `langchain4j-open-ai` 는 아무도 더 높은 버전을 요구하지 않아 1.18.0에 남는다.**

core는 1.18.1인데 open-ai 모듈은 1.18.0인 상태가 된다.
지금은 문제없이 돌지만, 두 버전 사이에 내부 API가 바뀌면 런타임에서 `NoSuchMethodError` 로 터진다.
컴파일은 통과하고 실행 중에만 드러나는 유형이라 찾기 나쁘다.

BOM으로 한 번에 맞추는 게 안전하다.

```kotlin
dependencies {
    implementation(platform("dev.langchain4j:langchain4j-bom:1.18.1"))
    implementation(platform("org.bsc.langgraph4j:langgraph4j-bom:1.8.24"))

    implementation("dev.langchain4j:langchain4j")
    implementation("dev.langchain4j:langchain4j-open-ai")
    implementation("org.bsc.langgraph4j:langgraph4j-core")
    implementation("org.bsc.langgraph4j:langgraph4j-langchain4j")
}
```

### beta 아티팩트가 딸려온다

해석 결과에 이런 게 섞여 있었다.

```
dev.langchain4j:langchain4j-skills:1.12.1-beta21
```

내가 선언하지 않았는데 전이 의존으로 들어온다.
정식 릴리스만 쓰는 정책이 있는 팀이라면 이걸 먼저 확인해야 한다.
`./gradlew :모듈:dependencies --configuration runtimeClasspath` 로 전체를 한 번 훑어보는 게 좋다.

---

## 최소 그래프 — 실제로 돌아간 코드

이건 개념 설명용이 아니라 컴파일하고 실행한 코드다.

```java
import org.bsc.langgraph4j.StateGraph;
import org.bsc.langgraph4j.GraphStateException;
import org.bsc.langgraph4j.state.AgentState;
import org.bsc.langgraph4j.state.Channel;
import org.bsc.langgraph4j.state.Channels;
import static org.bsc.langgraph4j.action.AsyncNodeAction.node_async;
import static org.bsc.langgraph4j.StateGraph.START;
import static org.bsc.langgraph4j.StateGraph.END;
import java.util.*;

public class Spike {
    static class S extends AgentState {
        static final String MSGS = "messages";
        static final Map<String, Channel<?>> SCHEMA =
            Map.of(MSGS, Channels.appender(ArrayList::new));
        S(Map<String, Object> init) { super(init); }
    }

    public static void main(String[] args) throws GraphStateException {
        var g = new StateGraph<>(S.SCHEMA, S::new)
            .addNode("hello", node_async(s -> Map.of(S.MSGS, "hi")))
            .addEdge(START, "hello")
            .addEdge("hello", END)
            .compile();

        for (var step : g.stream(Map.of(S.MSGS, "start"))) {
            System.out.println(step);
        }
    }
}
```

실행 출력은 이렇게 나온다.

```
NodeOutput{ node=hello, state={
	messages=[
	start
	hi
	]
}}
NodeOutput{ node=__END__, state={
	messages=[
	start
	hi
	]
}}
```

`Channels.appender` 가 리듀서 역할을 해서 `start` 위에 `hi` 가 쌓였다.
2편에서 다룬 `Annotated[list, add]` 와 정확히 같은 동작이다.

---

## Python과 무엇이 다른가

| 개념 | Python | langgraph4j |
| --- | --- | --- |
| 상태 스키마 | `TypedDict` | `AgentState` 상속 |
| 리듀서 | `Annotated[list, add]` | `Channels.appender(...)` |
| 덮어쓰기 필드 | 리듀서 없이 선언 | `Channels.base(...)` |
| 노드 | 일반 함수 | `NodeAction<S>` · `AsyncNodeAction<S>` |
| 노드 반환 | `dict` | `Map<String, Object>` |
| 조건부 엣지 | `add_conditional_edges` | `addConditionalEdges` · `EdgeAction<S>` |
| 비동기 | `async` / `await` | `CompletableFuture` |
| 체크포인트 | `PostgresSaver` 등 | `CompileConfig.checkpointSaver(...)` |
| 시각화 | LangSmith | 내장 Studio (PlantUML · Mermaid 출력) |

핵심 개념은 그대로 옮겨온다.
상태 스키마를 선언하고, 노드가 부분 업데이트를 반환하고, 엣지가 흐름을 정한다.

가장 크게 체감되는 차이는 **타입**이다.
Python은 상태 필드를 `TypedDict` 로 선언하고 `state["question"]` 으로 바로 꺼낸다.
Java는 `Map<String, Object>` 기반이라 `value("question")` 이 `Optional` 을 돌려주고, 제네릭으로 타입을 지정해야 한다.

```java
List<String> messages = state.<List<String>>value("messages").orElse(List.of());
```

이 부분이 처음에 번거롭다.
상태 클래스에 접근자 메서드를 만들어 두면 나머지 코드가 깔끔해진다.

```java
class AnalysisState extends AgentState {
    List<String> evidence() {
        return this.<List<String>>value(EVIDENCE).orElse(List.of());
    }
    double riskScore() {
        return this.<Double>value(RISK).orElse(0.0);
    }
}
```

---

## Spring Boot에 얹기

`CompiledGraph` 는 상태가 없는 불변 객체라 빈으로 등록해서 재사용하면 된다.

```java
@Configuration
class AnalysisGraphConfig {

    @Bean
    CompiledGraph<AnalysisState> analysisGraph(
            RetrieveNode retrieve,
            GradeNode grade,
            GenerateNode generate,
            CheckpointSaver checkpointSaver) throws GraphStateException {

        var builder = new StateGraph<>(AnalysisState.SCHEMA, AnalysisState::new)
            .addNode("retrieve", node_async(retrieve))
            .addNode("grade", node_async(grade))
            .addNode("generate", node_async(generate))
            .addEdge(START, "retrieve")
            .addEdge("retrieve", "grade")
            .addConditionalEdges("grade", edge_async(state ->
                state.hasEnoughEvidence() ? "generate" : "retrieve"))
            .addEdge("generate", END);

        return builder.compile(
            CompileConfig.builder().checkpointSaver(checkpointSaver).build());
    }
}
```

각 노드를 `@Component` 로 두면 기존 Spring 자원을 그대로 쓸 수 있다.
Neo4j 리포지토리, 다른 서비스를 부르는 HTTP 클라이언트, 트랜잭션 관리가 노드 안에서 평소처럼 동작한다.

```java
@Component
class RetrieveNode implements NodeAction<AnalysisState> {
    private final ConceptRepository conceptRepository;   // Spring Data Neo4j

    public Map<String, Object> apply(AnalysisState state) {
        var concepts = conceptRepository.findRelated(state.conceptName(), 2);
        return Map.of(AnalysisState.EVIDENCE, concepts);
    }
}
```

**이게 Java로 가는 실질적인 이유다.**
Python으로 별도 서비스를 세우면 DB 접근, 인증, 트랜잭션, 모니터링을 다시 만들어야 한다.
같은 앱 안에 두면 기존 인프라를 그대로 쓴다.

### 노드 안에서 트랜잭션을 잡을 때 주의할 점

3편에서 다룬 재실행 문제가 여기서 다시 나온다.
노드에 `@Transactional` 을 붙였는데 그 노드가 중단 지점을 포함하면, 재개할 때 트랜잭션이 처음부터 다시 시작된다.

DB 쓰기가 있는 노드는 중단 지점과 분리하고, 멱등하게 만드는 편이 안전하다.

---

## langchain4j와 Spring AI 중 무엇을 고를까

langgraph4j는 둘 다 지원한다. 선택 기준은 이렇다.

| 상황 | 선택 |
| --- | --- |
| 이미 Spring AI를 쓰고 있다 | Spring AI. MCP 애노테이션 API와 tool calling이 잘 정리돼 있다 |
| Python LangChain 예제를 옮겨온다 | langchain4j. 개념과 이름이 더 가깝다 |
| 둘 다 처음이다 | Spring Boot 프로젝트면 Spring AI 쪽이 자동 구성 이점이 크다 |

여기서 오해하기 쉬운 게 하나 있다.
**Spring AI를 쓴다고 langgraph4j가 필요 없어지는 게 아니다.**

Spring AI 2.0 문서가 소개하는 다섯 가지 워크플로 패턴은 `ChatClient` 를 쓰는 예제 코드다.
chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer 모두 프레임워크 기능이 아니라 구현 예시다.
상태 영속화, 중단과 재개, 과거 시점 복원은 Spring AI에 없다.

`ChatMemory` 가 있으니 상태 관리가 되는 것 아니냐는 오해가 여기서 나온다.
`ChatMemory` 가 저장하는 건 **대화 메시지**이고, 재개에 필요한 건 **워크플로 실행 상태**다.
3번 노드에서 죽었을 때 3번부터 재개하는 건 `ChatMemory` 로 못 한다.

그래서 둘은 층이 다르다. Spring AI가 LLM 호출을, langgraph4j가 흐름과 상태를 맡는다.

---

## Studio로 그래프 보기

langgraph4j에는 그래프 구조와 실행을 웹으로 보는 Studio가 딸려 있다.
Jetty, Quarkus, Spring Boot 세 가지 형태로 나온다.

```kotlin
implementation("org.bsc.langgraph4j:langgraph4j-studio-springboot:1.8.24")
```

그래프를 PlantUML이나 Mermaid로 뽑을 수도 있어서, 설계 문서에 붙일 다이어그램을 코드에서 바로 생성할 수 있다.
분기가 많아지면 코드만 봐서는 흐름이 안 잡히는데 이때 유용하다.

---

## 감수해야 할 것들

### 문서가 얇다

Python LangGraph는 개념 문서, 하우투, 튜토리얼이 촘촘하다.
langgraph4j는 README와 Javadoc, 그리고 저장소의 예제가 사실상 전부다.

그래서 **Python 문서로 개념을 배우고 Java로 옮기는 순서**가 현실적이다.
이 시리즈를 Python 중심으로 쓴 이유도 그것이다.

### API가 버전 사이에 움직인다

1.5 대에서 1.8 대로 오면서 모듈 구성과 일부 API가 바뀌었다.
인터넷의 예제 코드가 지금 버전에서 안 맞는 경우가 있다.

버전을 고정하고, 예제를 볼 때는 그게 어느 버전 기준인지 먼저 확인하는 습관이 필요하다.

### 유지보수 규모가 작다

Python LangGraph는 회사가 만들고 유지하는 프로젝트다.
langgraph4j는 그렇지 않다. 이슈 대응 속도와 장기 유지에 대한 기대치를 다르게 잡아야 한다.

다만 checkpoint 저장소만 여덟 종류를 지원하고 OpenTelemetry 연동까지 있는 걸 보면 관리는 꾸준히 되고 있다.

---

## 언제 langgraph4j를 쓰지 말아야 하나

**노드가 서너 개이고 분기가 하나뿐일 때.**
그 정도면 평범한 서비스 클래스와 `if` 문으로 충분하다.
프레임워크가 주는 건 상태 영속화와 재개인데, 그게 필요 없으면 추상화 비용만 남는다.

**재개가 필요 없는 동기 요청.**
응답을 주면 잊어도 되는 작업이면 checkpoint가 DB 쓰기만 늘린다.

**Python 생태계 기능이 꼭 필요할 때.**
LangGraph Platform, LangSmith 연동, 최신 프리빌트 에이전트 같은 건 Python 쪽에만 있다.
이게 핵심 요구라면 Python 서비스를 따로 세우는 편이 맞다.
다만 그러면 배포 단위와 운영 부담이 하나 늘어난다는 걸 함께 계산해야 한다.

---

## Python으로는 어떻게 되나

<details>
<summary>Python — 같은 그래프</summary>

```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    messages: Annotated[list[str], add]

builder = StateGraph(State)
builder.add_node("hello", lambda s: {"messages": ["hi"]})
builder.add_edge(START, "hello")
builder.add_edge("hello", END)

graph = builder.compile()
for step in graph.stream({"messages": ["start"]}):
    print(step)
```

Java 쪽 40줄이 여기서는 12줄이다.
이 차이가 Python 문서로 배우고 Java로 옮기라고 권하는 이유이기도 하다.
개념을 익히는 단계에서는 문법 부담이 적은 쪽이 낫다.
</details>

---

## 다음 편

마지막 7편은 학습 로드맵이다.
공식 문서를 어떤 순서로 읽을지, 무엇을 건너뛰어도 되는지, 그리고 단계별 실습 과제를 정리한다.

---

## 참고

- [langgraph4j GitHub](https://github.com/langgraph4j/langgraph4j)
- [langgraph4j 공식 문서](https://langgraph4j.github.io/langgraph4j/)
- [Spring AI 2.0.0 GA 릴리스 노트](https://spring.io/blog/2026/06/12/spring-ai-2-0-0-GA-available-now/)
- [Spring AI — Agentic Patterns](https://spring.io/blog/2025/01/21/spring-ai-agentic-patterns)
- [Docs by LangChain — Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
