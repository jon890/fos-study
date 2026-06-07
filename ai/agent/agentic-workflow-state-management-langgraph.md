# [초안] Agentic Workflow 상태 관리 — LangGraph로 보는 State Graph, Checkpoint, Human-in-the-loop, Tool 권한 경계

## 왜 이 주제가 중요한가

도구를 한 번 부르고 끝나는 에이전트는 함수 호출과 다를 게 없다. 진짜 어려움은 에이전트가 **여러 step에 걸쳐 오래 살아 있을 때** 생긴다. 사용자가 중간에 답을 주길 기다려야 하고, 외부 API가 죽으면 재시도해야 하고, 프로세스가 재시작돼도 진행 중이던 작업을 이어가야 한다. 이때 시스템이 다뤄야 하는 것은 모델의 출력이 아니라 **워크플로의 상태**(state)다.

상태 관리를 제대로 안 하면 다음 증상이 나타난다.

- 사용자 확인을 기다리는 동안 대화 컨텍스트를 메모리에 들고 있다가, 서버 재시작 한 번에 전부 날아간다.
- 도구를 5번 부르는 도중 3번째에서 죽으면, 처음부터 다시 돌린다. 이미 발송된 결제가 두 번 나간다.
- "사람이 승인하면 실행"을 콜백 지옥과 임시 테이블로 누더기처럼 구현한다.

LangGraph는 에이전트를 **상태 기계**(state machine)로 모델링하고, 그 상태를 checkpoint로 영속화해 이 문제들을 정면으로 다루는 프레임워크다. 이 문서는 LangGraph를 렌즈 삼아 agentic workflow의 상태 관리 네 축을 정리한다.

- State Graph — 에이전트를 노드와 상태 채널로 표현하기
- Checkpoint와 durable execution — 상태를 저장하고 재시작 후 이어가기
- Human-in-the-loop — 그래프를 중단하고 사람 입력으로 재개하기
- Tool 권한 경계 — 권한을 상태와 노드에 새겨 우회를 막기

도구 호출 자체의 메커니즘(레지스트리, 스키마 검증, dispatcher)은 [LLM Tool Calling과 Agent Workflow 설계](./llm-tool-calling-agent-workflow.md)에서, 평가와 risk gate는 [Agentic Workflow 평가와 Risk Gate 설계](./agentic-workflow-evaluation-risk-gate.md)에서 다룬다. 여기서는 그 위에 깔리는 **상태 레이어**에 집중한다.

## 핵심 개념 — 에이전트를 State Graph로 보기

LangGraph의 출발점은 "에이전트는 공유 상태를 갱신하는 노드들의 그래프"라는 시각이다. 세 가지를 정의하면 된다.

- **State** — 그래프 전체가 공유하는 데이터. 타입이 명시된 dict로 선언한다.
- **Node** — 상태를 입력으로 받아 상태의 일부를 갱신해 돌려주는 함수.
- **Edge** — 어느 노드 다음에 어느 노드로 갈지. 조건부 분기도 edge로 표현한다.

### State와 reducer

상태에서 가장 자주 헷갈리는 부분이 **reducer** 다. 노드가 상태를 돌려주면 LangGraph는 그것을 기존 상태에 어떻게 합칠지 결정해야 한다. 기본값은 덮어쓰기지만, 메시지 목록처럼 누적돼야 하는 필드는 reducer로 "합치는 방법"을 지정한다.

```python
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # add_messages reducer: 덮어쓰지 않고 메시지를 누적한다
    messages: Annotated[list, add_messages]
    # 기본 동작: 노드가 돌려준 값으로 덮어쓴다
    intent: str
    pending_action: dict | None
    approved: bool
```

`messages` 필드는 `add_messages` reducer 덕분에 노드가 새 메시지 하나만 돌려줘도 기존 목록에 append된다. `intent`처럼 reducer가 없는 필드는 노드가 돌려준 값으로 그대로 교체된다. 이 차이를 모르면 "왜 대화 기록이 매 step 사라지지?" 같은 버그에 시간을 쓴다.

### Node와 conditional edge

노드는 상태를 받아 갱신분만 돌려준다. 전체 상태를 다시 만들 필요 없이 **바뀐 키만** 반환하면 reducer가 알아서 합친다.

```python
def classify(state: AgentState) -> dict:
    last = state["messages"][-1].content
    intent = "REFUND" if "환불" in last else "CHITCHAT"
    return {"intent": intent}


def route(state: AgentState) -> str:
    # 다음에 실행할 노드 이름을 문자열로 돌려준다
    return "refund_flow" if state["intent"] == "REFUND" else "chitchat"


builder = StateGraph(AgentState)
builder.add_node("classify", classify)
builder.add_node("refund_flow", refund_flow)
builder.add_node("chitchat", chitchat)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route, {"refund_flow": "refund_flow", "chitchat": "chitchat"})
builder.add_edge("chitchat", END)
```

ReAct 루프도 결국 "model 노드 → 도구가 필요하면 tool 노드 → 다시 model 노드"를 conditional edge로 잇는 사이클이다. 자유로워 보이는 에이전트 루프가 명시적인 그래프로 그려진다는 점이 핵심이다. 경로가 그래프로 보이면 감사·디버깅·테스트가 전부 쉬워진다.

## Checkpoint와 durable execution

여기서부터가 상태 관리의 본론이다. 위 그래프를 그냥 `compile()`하면 상태는 한 번의 실행 동안만 메모리에 산다. 실행이 끝나거나 프로세스가 죽으면 사라진다. **checkpointer** 를 붙이면 그래프는 매 step(super-step)마다 상태를 저장소에 스냅샷으로 남긴다.

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()          # 학습용 인메모리
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-42-session-7"}}
graph.invoke({"messages": [("user", "어제 주문 환불해줘")]}, config)
```

핵심은 `thread_id` 다. 같은 thread_id로 다시 호출하면, LangGraph는 그 thread의 마지막 checkpoint를 불러와 **이어서** 실행한다. 새로 시작하지 않는다. 이 한 가지가 다음을 한꺼번에 해결한다.

- **대화 메모리** — thread_id별로 메시지 누적이 저장소에 남으므로, 매 요청마다 컨텍스트를 직접 들고 다닐 필요가 없다.
- **crash recovery** — 노드 3개 실행 후 프로세스가 죽어도, 재시작 후 같은 thread_id로 호출하면 4번째 노드부터 재개한다.
- **durable execution** — 오래 걸리는 워크플로(사람 승인 대기, 외부 배치 대기)를 메모리에 묶어두지 않고, 상태를 디스크에 내려둔 채 기다릴 수 있다.

### 저장소 선택

```python
# 운영: SQLite (단일 노드) 또는 Postgres (다중 노드)
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver

# with 컨텍스트로 커넥션을 관리한다
with SqliteSaver.from_conn_string("checkpoints.sqlite") as cp:
    graph = builder.compile(checkpointer=cp)
```

- `MemorySaver` — 테스트·예제 전용. 프로세스가 죽으면 같이 죽는다.
- `SqliteSaver` — 단일 인스턴스 운영, 로컬 영속화.
- `PostgresSaver` — 다중 인스턴스에서 thread 상태를 공유해야 할 때. 운영 에이전트의 기본 선택.

### 상태 조회와 time travel

checkpoint가 쌓이면 thread의 과거 상태를 들여다보고, 특정 시점으로 되감을 수도 있다.

```python
# 현재 상태
snapshot = graph.get_state(config)
print(snapshot.values["intent"], snapshot.next)  # 다음에 실행될 노드

# 전체 히스토리 (최신순) — 디버깅·감사·되감기에 쓴다
for state in graph.get_state_history(config):
    print(state.config["configurable"]["checkpoint_id"], state.next)
```

`get_state_history`는 단순 디버깅을 넘어, "이 시점 상태에서 다른 입력으로 다시 가지치기" 같은 실험과, 운영 사고 분석 시 "에이전트가 정확히 어떤 상태에서 잘못된 도구를 골랐나"를 재현하는 데 쓴다.

## Human-in-the-loop — 중단하고 재개하기

오래 사는 에이전트의 절반은 "사람을 기다리는 시간"이다. checkpoint가 있으면 HITL은 콜백이 아니라 **그래프를 중단점에서 멈췄다가 사람 입력으로 재개하는 일**이 된다. 사람을 어디에 어떤 비용으로 끼울지에 대한 패턴(pre-action approval, post-hoc review, escalation)은 [risk gate 문서](./agentic-workflow-evaluation-risk-gate.md)에서 다뤘고, 여기서는 그 패턴을 LangGraph 메커니즘으로 어떻게 구현하는지를 본다.

### interrupt와 Command(resume=...)

`interrupt()`는 노드 한가운데서 실행을 멈추고, 사람에게 보여줄 값을 밖으로 내보낸다. 이때 상태는 checkpoint로 저장된 채 "대기" 상태가 된다. 나중에 `Command(resume=...)`로 사람 입력을 주입하면, 그 노드는 멈췄던 지점부터 다시 실행된다.

```python
from langgraph.types import interrupt, Command


def approve_refund(state: AgentState) -> dict:
    action = state["pending_action"]
    # 여기서 그래프가 멈추고, 아래 dict가 호출자에게 반환된다
    decision = interrupt({
        "type": "approval_required",
        "action": action,
        "question": f"{action['amount']}원 환불을 승인할까요?",
    })
    if decision != "approve":
        return {"approved": False}
    return {"approved": True}
```

호출 측은 두 단계로 동작한다.

```python
# 1) 실행 → interrupt에서 멈춘다
result = graph.invoke({"messages": [("user", "환불해줘")]}, config)
print(result["__interrupt__"])      # 사람에게 보여줄 승인 요청

# (여기서 며칠이 지나도 된다. 상태는 checkpoint에 안전하게 남아 있다)

# 2) 사람 결정을 주입해 재개 — 같은 thread_id
graph.invoke(Command(resume="approve"), config)
```

콜백·임시 테이블·플래그 컬럼 없이, 그래프가 멈춘 지점과 상태가 그대로 보존된다는 점이 강력하다. 며칠 뒤에 재개해도 에이전트는 자기가 어디까지 했는지 정확히 안다.

### interrupt_before로 게이트 걸기

특정 노드 실행 *직전*에 무조건 멈추게 할 수도 있다. 비가역 행동 노드 앞에 거는 pre-action approval에 잘 맞는다.

```python
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["execute_refund"],   # 이 노드 실행 전 멈춤
)

graph.invoke(initial, config)              # execute_refund 직전에서 정지
# 사람이 검토 후
graph.invoke(None, config)                 # None = "그대로 이어서 진행"
```

`interrupt()`는 "노드 안에서 사람에게 물어보고 그 답을 쓴다"에, `interrupt_before`는 "이 행동은 무조건 사람 검토를 거친다"에 쓴다. 둘을 위험 등급에 맞게 섞는다.

## Tool 권한 경계 — 권한을 상태에 새기기

권한 검증을 모델이 도구를 부를 때마다 즉석에서 하면 우회 경로가 생긴다. 상태 그래프에서는 **권한을 상태의 일부로 두고, 권한 게이트를 명시적 노드로** 만들어 모든 도구 실행이 그 노드를 지나게 강제한다. 도구 dispatcher 레벨의 권한 검증과 idempotency는 [tool calling 문서](./llm-tool-calling-agent-workflow.md)에서 다뤘고, 여기서는 그것을 그래프 구조로 끌어올리는 부분을 본다.

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    scopes: set[str]            # 인증 컨텍스트에서 주입된 권한
    proposed_tool: dict | None  # 모델이 제안한 도구 호출


# 도구마다 필요한 스코프를 코드와 한 곳에 둔다
TOOL_SCOPES = {
    "find_order": {"order:read"},
    "issue_refund": {"order:read", "refund:write"},
}


def permission_gate(state: AgentState) -> dict:
    call = state["proposed_tool"]
    required = TOOL_SCOPES.get(call["name"], {"__deny__"})
    if not required.issubset(state["scopes"]):
        # 권한 부족: 도구를 비우고 일반화된 거절만 남긴다
        return {
            "proposed_tool": None,
            "messages": [("system", "요청한 작업에 대한 권한이 없습니다")],
        }
    return {}   # 통과 — 상태 변화 없음


def route_after_gate(state: AgentState) -> str:
    return "run_tool" if state["proposed_tool"] else "respond"
```

설계 원칙은 세 가지다.

- **권한은 상태에 들어온다** — 모델이 아니라 인증 컨텍스트가 `scopes`를 주입한다. 모델은 자기 권한을 모른다.
- **게이트는 우회 불가능한 노드** — 모든 도구 실행 경로가 `permission_gate → (통과 시) run_tool`을 지나도록 edge를 짠다. "이번만 권한 올려서 실행" 같은 샛길을 그래프에 만들지 않는다.
- **거절은 일반화** — 왜 거절됐는지 상세를 모델에 흘리지 않는다. 모델은 그것을 사용자에게 그대로 풀어 쓸 수 있다.

권한을 상태로 두면 보너스가 따라온다. checkpoint에 남는 상태에 "어떤 권한으로 어떤 도구가 제안·거절됐는지"가 자동으로 기록돼, 그대로 감사 로그이자 평가 입력이 된다.

## 나쁜 예 vs 개선된 예

### 나쁜 예 1 — 대화 상태를 프로세스 메모리에 들고 있기

```python
# 안티패턴: 세션 dict를 전역 메모리에 보관
SESSIONS: dict[str, list] = {}

def handle(user_id, msg):
    SESSIONS.setdefault(user_id, []).append(msg)
    ...
```

문제: 서버 재시작·스케일아웃 한 번에 전 사용자 대화가 사라진다. 다중 인스턴스에서는 인스턴스마다 다른 상태를 본다.

### 개선

checkpointer(`PostgresSaver`) + thread_id로 상태를 외부 저장소에 둔다. 어느 인스턴스가 받아도 같은 thread를 이어간다.

### 나쁜 예 2 — 사람 승인을 폴링 플래그로 구현

```python
# 안티패턴: 승인 대기 동안 상태를 임시 테이블에 수동 직렬화
save_pending(user_id, serialize(workflow_context))
# ... 나중에 ...
ctx = deserialize(load_pending(user_id))
resume_somehow(ctx)   # 어디서부터 재개할지 직접 관리
```

문제: 직렬화 포맷이 코드 변경마다 깨지고, "어디서 멈췄는지"를 개발자가 손으로 추적해야 한다.

### 개선

`interrupt()` + `Command(resume=...)`로 그래프가 멈춘 지점과 상태를 프레임워크가 보존하게 한다. 재개 위치를 사람이 관리하지 않는다.

### 나쁜 예 3 — 비-idempotent 행동을 재시작 시 무조건 재실행

```python
# 안티패턴: 재시작하면 처음부터 다시
def run_workflow(req):
    order = find_order(req)
    issue_refund(order)   # crash 후 재시작하면 환불이 두 번 나간다
```

문제: durable execution이 없으니 crash 복구가 곧 중복 실행이다.

### 개선

checkpointer로 "어느 노드까지 끝났는지"를 상태로 남긴다. 재시작 시 같은 thread_id로 호출하면 이미 끝난 노드는 건너뛰고 다음 노드부터 재개해, 환불 노드가 두 번 실행되지 않는다. 외부 호출에는 idempotency key를 같이 둬 이중 안전망으로 쓴다.

## 로컬 실습 환경

진짜 모델 비용 없이 상태 관리 골격을 손에 익히는 게 목적이다.

- Python 3.11+, `pip install langgraph langgraph-checkpoint-sqlite`
- LLM: 실 키 대신 **fake model 노드**로 시작한다. 시나리오별로 미리 정한 도구 호출/최종 답변을 돌려주는 결정적 함수면 충분하다. 상태·checkpoint·interrupt 로직을 검증할 때는 진짜 모델보다 결정적인 가짜가 낫다.
- 저장소: 학습 초기엔 `MemorySaver`, crash recovery를 체험할 땐 `SqliteSaver`로 파일에 남겨 프로세스를 죽였다 살린다.
- 관측: `get_state_history(config)`로 매 super-step 상태를 덤프해 그래프가 실제로 어떤 경로를 밟았는지 눈으로 확인한다.

```bash
pip install langgraph langgraph-checkpoint-sqlite
python agent_demo.py            # 1차 실행 — interrupt에서 멈춤
# 프로세스를 강제 종료한 뒤
python resume_demo.py           # 같은 thread_id로 재개되는지 확인
```

## 실행 가능한 시나리오

손으로 굴려보며 상태 관리의 동작을 익히는 데 유용한 시나리오다.

1. **대화 누적** — 같은 thread_id로 두 번 호출하고, 두 번째 호출에서 첫 메시지가 `messages`에 남아 있는지 확인. reducer가 없으면 사라진다.
2. **crash recovery** — `SqliteSaver`로 노드 2개 실행 후 프로세스를 강제 종료. 재시작 후 같은 thread_id로 호출해 3번째 노드부터 재개되는지 확인.
3. **pre-action approval** — `interrupt_before=["execute_refund"]`로 환불 직전 정지. `invoke(None, config)`로 이어서 실행되는지 확인.
4. **승인 거절 분기** — `interrupt()`에 `"reject"`를 resume으로 주입해 환불 노드 대신 사과·escalate 경로로 가는지 확인.
5. **권한 게이트** — `scopes`에서 `refund:write`를 빼고 호출해, `permission_gate`가 도구를 비우고 일반화된 거절만 남기는지 확인.
6. **time travel** — `get_state_history`로 분기 직전 상태를 꺼내, 다른 입력으로 다시 진행시켜 경로가 갈라지는지 확인.

각 시나리오는 통합 테스트로 묶을 수 있다. fake model이 시나리오별 스크립트를 받아 결정적으로 동작하면, 모델 응답이 바뀌어도 상태·checkpoint·게이트 로직이 회귀 보호된다.

## 설계 점검 질문

상태 관리 설계를 스스로 검토할 때 던져볼 질문과 답의 뼈대다.

### "에이전트의 상태를 어디에 두는가?"

프로세스 메모리는 답이 아니다. 상태는 checkpointer를 통해 외부 저장소(다중 인스턴스면 Postgres)에 thread_id 단위로 둔다. 그래야 재시작·스케일아웃·장시간 대기를 견딘다. 대화 메모리, crash recovery, durable execution이 모두 같은 checkpoint 메커니즘 위에서 풀린다는 점이 핵심이다.

### "오래 걸리는 사람 승인을 어떻게 다루는가?"

워크플로 컨텍스트를 메모리에 묶어두지 않는다. `interrupt()`로 상태를 checkpoint에 내려둔 채 멈추고, 사람 결정이 오면 `Command(resume=...)`로 같은 thread를 재개한다. 재개 위치는 프레임워크가 보존하므로 개발자가 직렬화·복원을 손으로 관리하지 않는다.

### "재시작 시 중복 실행을 어떻게 막는가?"

durable execution이 답의 절반이다. 끝난 노드는 checkpoint에 기록돼 재시작 후 건너뛴다. 나머지 절반은 비가역 외부 호출의 idempotency key다. 둘을 같이 둔다.

### "권한 우회를 그래프에서 어떻게 차단하는가?"

권한을 상태에 주입하고, 모든 도구 실행 경로가 우회 불가능한 `permission_gate` 노드를 지나게 edge를 짠다. 모델은 자기 권한을 모르고, 거절 사유는 일반화해 모델에 흘리지 않는다.

### "상태가 그래프로 표현되면 무엇이 좋아지는가?"

경로가 명시적이라 감사·디버깅·테스트가 쉬워진다. `get_state_history`로 사고 시점 상태를 재현하고, fake model로 경로별 회귀 테스트를 묶는다. 자유로운 루프를 결정적인 그래프로 내려두는 것이 운영 가능성의 출발점이다.

## 체크리스트

- [ ] 상태(State)가 타입이 명시된 형태로 선언돼 있고, 누적 필드에는 reducer가 지정돼 있는가
- [ ] 에이전트 루프가 명시적 노드와 conditional edge로 그려져 있는가
- [ ] checkpointer가 붙어 있고, 운영은 다중 인스턴스 공유가 가능한 저장소(Postgres 등)인가
- [ ] thread_id 단위로 대화 메모리·crash recovery·장시간 대기가 모두 풀리는가
- [ ] 사람 승인이 `interrupt()` / `interrupt_before` + `Command(resume=...)`로 구현돼 있는가
- [ ] 비가역 행동 노드 앞에 pre-action 게이트가 걸려 있는가
- [ ] 재시작 시 끝난 노드를 건너뛰어 비-idempotent 행동이 중복 실행되지 않는가
- [ ] 외부 비가역 호출에 idempotency key가 함께 있는가
- [ ] 권한이 상태에 주입되고, 모든 도구 경로가 우회 불가능한 권한 게이트 노드를 지나는가
- [ ] 거절·실패 메시지가 사용자에게 노출돼도 안전한 수준으로 일반화돼 있는가
- [ ] `get_state_history`로 사고 시점 상태를 재현할 수 있는가
- [ ] fake model 기반 통합 테스트로 상태·checkpoint·interrupt·권한 게이트가 회귀 보호되는가
