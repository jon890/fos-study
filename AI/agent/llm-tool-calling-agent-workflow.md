# [초안] LLM Tool Calling과 Agent Workflow 설계

## 왜 이 주제가 중요한가

LLM은 그 자체로는 "텍스트를 잘 만들어내는 함수"에 가깝다. 사용자의 문의, 예약 변경, 문서 조회, 알림 발송처럼 실제 업무를 처리해야 하는 AI Agent 시스템에서는 모델이 "그럴듯한 답"을 생성하는 것만으로는 충분하지 않다. 진짜 가치는 모델이 **외부 시스템을 안전하게 호출**하고, 그 결과를 바탕으로 **다음 행동을 결정**하며, 실패했을 때 **사람에게 다시 넘기거나 재시도**할 수 있을 때 만들어진다.

이 흐름의 가운데에 있는 것이 **Tool Calling**(또는 Function Calling)이고, 그 위에서 도구 호출을 여러 번 엮어 하나의 사용자 의도를 처리하는 것이 **Agent Workflow**다. 실무 설계에서 확인해야 할 지점은 다음과 같다.

- LLM의 비결정성을 어떻게 결정적인 시스템과 연결할 것인가
- 사용자 발화 → 의도 분류 → 도구 선택 → 권한 검증 → 호출 → 결과 검증 → 후속 행동의 흐름을 어떻게 설계할 것인가
- 도구 호출 실패, hallucinated argument, 권한 누락, 부분 성공 같은 실패 모드를 어떻게 다룰 것인가
- Spring 기반 마이크로서비스 환경에서 이 흐름을 어떻게 안정적으로 운영할 것인가

이 문서는 이 네 가지를 도구 호출 기반 AI 백엔드 설계 예시로 풀어 쓴다.

## 핵심 개념 — Tool Calling이란 무엇인가

Tool Calling은 LLM이 자연어 응답 대신, **사전에 정의된 함수 시그니처에 맞는 JSON 인자**를 출력하도록 유도하는 메커니즘이다. OpenAI, Anthropic, Bedrock, Vertex 등 주요 제공자는 동일한 모양의 인터페이스를 갖는다.

1. 백엔드는 모델에게 "사용 가능한 도구 목록"을 JSON Schema로 전달한다.
2. 모델은 사용자의 발화를 보고, 텍스트로 답할지 도구를 호출할지 결정한다.
3. 도구를 호출하기로 결정하면, `{"tool": "...", "arguments": {...}}` 형태의 구조화된 응답을 돌려준다.
4. 백엔드는 그 JSON을 검증한 뒤, **자기 책임 하에** 실제 함수/HTTP API를 호출한다.
5. 결과를 다시 모델에게 도구 응답으로 주입한다.
6. 모델은 그 결과를 바탕으로 다음 도구를 또 호출하거나, 최종 텍스트 답변을 생성한다.

여기서 가장 자주 오해받는 부분은 "모델이 도구를 호출했다"가 아니라 **모델이 도구를 호출하자고 제안했고, 백엔드가 검증하고 실행했다** 라는 점이다. 모델은 어디까지나 인자 후보를 만든다. 실행 권한은 항상 백엔드에 있다. 이 분리를 흐리면 권한, 감사, 비용, 신뢰성 모두가 무너진다.

### Agent Workflow의 두 가지 패턴

도구 호출을 한 번 하면 끝나는 단순 케이스는 거의 없다. 보통 두 가지 패턴 중 하나를 쓴다.

- **ReAct (Reason + Act) 루프**: 모델이 "Thought → Action → Observation"을 반복한다. 백엔드는 Action을 실행하고 Observation을 다시 주입한다. 종료 조건은 모델이 `final_answer`를 내거나, 최대 step 수를 초과하거나, 실패 가드가 발동했을 때다.
- **Plan-then-Execute**: 먼저 모델에게 전체 계획(여러 도구를 어떤 순서로 부를지)을 짜게 한 뒤, 백엔드가 결정적인 워크플로 엔진으로 실행한다. 헬스케어처럼 감사 추적이 중요한 도메인에서는 이쪽이 잘 맞는다. 계획이 사람 검토 가능한 형태로 남기 때문이다.

헬스케어, 예약, 고객 지원처럼 "사용자 → 1차 분류 → 도메인별 분기 → 도구 호출 → 응답"이 어느 정도 정형화된 도메인은 **Plan-then-Execute의 약식 버전 + ReAct를 도구 호출 단계에서만 허용**하는 하이브리드가 실용적이다. 자유도는 줄이고, 감사·재현성·비용 통제는 늘리는 방향이다.

## 백엔드 워크플로 설계 — 헬스케어 AI 예시

다음 흐름을 백엔드 설계 예시로 단계별로 본다. 사용자 발화: "어제 처방받은 약 다시 보내줄 수 있어요? 이름은 김OO이에요."

### 1) Intent Classification (의도 분류)

가장 먼저 하는 일은 **이 발화가 어떤 카테고리인지**를 판별하는 것이다. 두 가지 접근이 있다.

- **LLM 단일 호출로 분류 + 도구 호출까지 한 번에**: 모델 자유도가 높지만 도구 후보가 많아질수록 hallucination 위험이 커진다.
- **얕은 분류기로 먼저 좁힌 뒤, 좁혀진 도구 집합만 LLM에 노출**: 분류 모델은 작은 fine-tuned 모델이거나, 정규식/임베딩 기반 룰일 수도 있다.

헬스케어 도메인은 후자가 안전하다. "처방 재발송"은 의료기록 접근 권한이 필요한 민감 카테고리이고, "오늘 날씨" 같은 잡담과 같은 도구 풀에 두면 안 된다. 분류 결과에 따라 **다른 system prompt + 다른 tool subset**을 모델에 주입한다.

```
1차 분류: { category: "PRESCRIPTION_RESEND", confidence: 0.92 }
→ 도구 풀: [findPatient, findRecentPrescription, resendPrescription, escalateToHuman]
→ 시스템 프롬프트: "본인 확인이 끝나기 전에는 처방 정보를 노출하지 마라"
```

### 2) Tool Registry

도구는 코드 곳곳에 흩어두지 않고 하나의 **레지스트리**에 등록한다. 각 도구는 다음 메타데이터를 가진다.

- 이름 (`resend_prescription`)
- JSON Schema 형식의 인자 스펙
- 필요한 권한 스코프 (`prescription:read`, `prescription:send`)
- 외부에서 호출 가능한지 여부 (LLM이 직접 부를 수 있는지, 내부 워크플로 전용인지)
- idempotency 정책
- 평균/최대 응답 시간
- 실패 시 fallback 정책 (`retry`, `escalate`, `apologize`)
- audit 카테고리 (`PHI_READ`, `PHI_WRITE`, `BENIGN`)

레지스트리는 단순한 Java 인터페이스 + Spring Bean 등록으로 충분하다. 추후 모델에 노출할 JSON Schema는 이 레지스트리에서 자동 생성한다. **메타데이터를 코드와 따로 두지 않는 것**이 핵심이다. 따로 두면 둘이 어긋나고, 어긋난 순간이 가장 위험한 순간이다.

### 3) Schema Validation

모델이 돌려준 `arguments` JSON은 절대 그대로 실행하지 않는다. 두 단계 검증을 거친다.

- **구조 검증**: JSON Schema validator로 타입/필수필드/enum/포맷을 확인한다. Java 진영에서는 `networknt/json-schema-validator` 같은 라이브러리가 표준이다.
- **의미 검증**: 환자 ID는 현재 인증된 사용자가 접근 권한을 가진 ID인지, 날짜는 미래가 아닌지, 약품 코드가 실제 코드 마스터에 존재하는지를 도메인 레이어에서 다시 확인한다.

구조 검증이 통과해도 의미 검증에서 떨어지는 경우가 가장 흔한 hallucination 패턴이다. 모델은 그럴듯한 환자 ID를 만들어낸다. 백엔드는 그것을 정중히 거절해야 한다.

### 4) Permission Check

도구 호출은 **항상 현재 인증 컨텍스트의 권한**과 함께 검증한다. 모델은 권한을 알 필요가 없고, 알게 해서도 안 된다. Spring Security 환경이라면 다음과 같은 모양이 된다.

- 도구 등록 시 필요한 스코프를 선언
- Tool Dispatcher가 호출 직전에 `SecurityContext`의 권한과 도구 스코프를 비교
- 권한 부족이면 도구는 실행되지 않고, 모델에게는 "이 도구는 현재 사용자에게 허용되지 않음" 같은 일반화된 거절 메시지를 돌려준다 (왜 거절됐는지 상세 정보는 노출하지 않는다)

여기서 자주 하는 실수는 "모델이 시킨 일이니까 잠깐 권한을 올려서 실행한다"는 우회다. 어떤 경우에도 도구 실행은 사용자 컨텍스트에서 벌어진다. 모델은 권한 상승의 근거가 될 수 없다.

### 5) Fallback과 Retry

도구는 실패한다. HTTP 5xx, timeout, 부분 성공, 외부 EMR의 일시 장애. 각 실패에 대해 다음 정책을 미리 정한다.

- **Idempotent + 안전한 도구** (`findPatient`, `findRecentPrescription`): 지수 백오프 + jitter로 2~3회 재시도. 결과적으로 모델에게 보여줄 observation은 "성공" 또는 "최종 실패".
- **Side-effect 있는 도구** (`resendPrescription`, `cancelAppointment`): 재시도는 idempotency key가 있을 때만. 없으면 즉시 실패로 보고. 모델이 같은 도구를 반복 호출해 부작용이 누적되는 사고를 막는다.
- **부분 성공**: SMS는 보냈지만 푸시 알림 큐에 넣는 단계에서 실패한 경우, 부분 성공임을 모델이 알 수 있도록 observation 페이로드에 명시한다. 모델이 "보냈습니다"라고 단정하지 않게 한다.

루프 전체에는 **최대 step 수**, **최대 누적 토큰**, **최대 누적 비용** 가드를 둔다. 한 사용자 발화당 도구 호출 6회, 누적 LLM 토큰 30k, 시간 20초가 흔한 출발점이다. 가드에 걸리면 친절한 fallback 답변과 함께 사람 상담사로 escalate한다.

### 6) Audit Log

규제 도메인에서 audit log는 후순위가 아니라 **1차 산출물**이다. 한 번의 사용자 발화에 대해 다음을 모두 남긴다.

- correlation id (요청-응답 추적용), trace id (분산 추적용)
- 인증 사용자 식별자 (PHI는 토큰화/해시)
- 분류 결과와 confidence
- 모델에게 노출한 도구 목록과 system prompt 버전
- 모델이 제안한 각 tool call의 이름·인자·정당화(있다면)
- 검증 결과 (통과/거절 사유)
- 실제 실행된 도구의 입력·출력 요약, 응답 시간, 결과 코드
- 최종 모델 답변과 사용자에게 노출된 텍스트

audit는 운영뿐 아니라 **모델 평가**의 입력이 된다. 어떤 분류가 자주 잘못되는지, 어떤 도구의 인자 hallucination이 잦은지, 어떤 fallback 경로가 가장 많이 도는지를 정량적으로 본다. 이 데이터 없이는 LLM 시스템은 개선되지 않는다.

## Java/Spring 연동 패턴

다음은 헬스케어 AI 백엔드에서 자주 쓰는 구조다. 코드는 핵심만 추렸다.

### Tool 인터페이스와 레지스트리

```java
public interface AgentTool<I, O> {
    String name();
    Class<I> inputType();
    JsonNode jsonSchema();
    Set<String> requiredScopes();
    SideEffect sideEffect(); // NONE, IDEMPOTENT_WRITE, NON_IDEMPOTENT_WRITE
    O invoke(I input, ToolContext ctx);
}

@Component
public class ToolRegistry {
    private final Map<String, AgentTool<?, ?>> byName;

    public ToolRegistry(List<AgentTool<?, ?>> tools) {
        this.byName = tools.stream().collect(toMap(AgentTool::name, t -> t));
    }

    public List<JsonNode> exposedSchemasFor(IntentCategory category, Authentication auth) {
        return byName.values().stream()
            .filter(t -> categoryAllows(category, t))
            .filter(t -> hasAllScopes(auth, t.requiredScopes()))
            .map(AgentTool::jsonSchema)
            .toList();
    }
}
```

핵심은 모델에 "노출되는 도구 목록"이 **카테고리 + 권한**으로 동적으로 좁혀진다는 점이다. 정적 전체 노출은 헬스케어에서는 위험하다.

### Dispatcher

```java
public ToolResult dispatch(ToolCall call, ToolContext ctx) {
    AgentTool<Object, Object> tool = registry.require(call.name());

    if (!ctx.hasAllScopes(tool.requiredScopes())) {
        audit.permissionDenied(call, ctx);
        return ToolResult.refused("not_authorized");
    }

    Object input = schemaValidator.validateAndBind(call.arguments(), tool.inputType());
    domainValidator.validate(input, ctx); // 환자 소유권, 날짜 sanity 등

    try {
        Object output = retryPolicy.runWithIdempotency(
            tool.sideEffect(), call.idempotencyKey(),
            () -> tool.invoke(input, ctx)
        );
        audit.success(call, output, ctx);
        return ToolResult.ok(output);
    } catch (DomainRefusal r) {
        audit.domainRefused(call, r, ctx);
        return ToolResult.refused(r.reasonCode());
    } catch (Exception e) {
        audit.failure(call, e, ctx);
        return ToolResult.error("tool_failed");
    }
}
```

모델에게 돌려주는 `ToolResult`는 항상 **사용자에게 그대로 노출되어도 안전한 수준의 메시지**여야 한다. 스택 트레이스, 내부 환자 ID, 외부 시스템의 원시 에러 코드를 모델에 흘리지 않는다. 모델은 그것을 사용자에게 그대로 풀어 쓸 수 있다.

### Agent 루프

```java
public AgentReply run(UserMessage msg, AgentContext ctx) {
    Intent intent = intentClassifier.classify(msg, ctx);
    LlmSession session = llm.openSession(intent.systemPrompt(),
                                         registry.exposedSchemasFor(intent.category(), ctx.auth()));
    session.append(msg);

    for (int step = 0; step < ctx.maxSteps(); step++) {
        LlmResponse r = session.next(ctx.budget());
        if (r.isFinal()) return AgentReply.text(r.text());

        ToolResult tr = dispatcher.dispatch(r.toolCall(), ctx.toToolContext());
        session.appendObservation(r.toolCall(), tr);

        if (ctx.budget().exhausted()) break;
    }
    return AgentReply.escalate("budget_exceeded");
}
```

루프는 단순해 보이지만, 실제 운영에서 어렵게 만드는 것은 **루프 외부의 가드**다. 토큰 예산, 시간 예산, step 수, 외부 의존성의 헬스 상태, circuit breaker — 이 모든 것을 `ctx.budget()` 안에 모아둔다. 모델이 무한히 도구를 부르거나, 같은 도구를 반복 호출해 비용을 폭발시키지 않게 하는 마지막 안전망이다.

## 나쁜 예 vs 개선된 예

### 나쁜 예 1 — 모델 출력을 그대로 실행

```java
// 안티패턴
Map args = objectMapper.readValue(modelJson, Map.class);
String patientId = (String) args.get("patientId");
prescriptionService.resend(patientId);
```

문제: schema 검증 없음, 권한 검증 없음, 환자 소유권 검증 없음, audit 없음. 모델이 임의 환자 ID를 만들면 그대로 처방이 재발송된다.

### 개선

`ToolCall` → `Dispatcher.dispatch` 경로를 강제한다. 모델 출력은 항상 dispatcher 입구에서만 시스템 안으로 들어온다.

### 나쁜 예 2 — 비-idempotent 도구를 자동 재시도

```java
// 안티패턴
@Retryable(maxAttempts = 3)
public void resend(String prescriptionId) { ... }
```

문제: 첫 호출이 외부 시스템에는 성공했는데 응답 타임아웃으로 우리 쪽이 실패라고 판단하면, 두 번 재시도가 추가로 발송된다. 환자에게 같은 SMS가 세 번 간다.

### 개선

idempotency key (예: `agentRequestId + toolName`) 를 외부 시스템과 합의해 같이 보낸다. 외부가 idempotency를 지원하지 않으면 재시도하지 않는다. 모델에게는 "발송 시도 결과 확인 불가, 사람 상담사로 연결" 같은 정직한 observation을 돌려준다.

### 나쁜 예 3 — 모든 도구를 항상 노출

```java
// 안티패턴
session = llm.open(systemPrompt, registry.allSchemas());
```

문제: 잡담 컨텍스트에서도 `resendPrescription` 같은 민감 도구가 노출된다. prompt injection이나 사회공학 발화에 모델이 끌려갈 여지가 커진다.

### 개선

intent 분류 결과 + 사용자 권한으로 도구 풀을 좁힌다. 잡담 컨텍스트에는 PHI 도구를 절대 노출하지 않는다.

## 로컬 실습 환경

학습용으로 가볍게 굴릴 수 있는 환경.

- JDK 21, Spring Boot 3.x
- 의존성: `spring-boot-starter-web`, `spring-boot-starter-validation`, `networknt/json-schema-validator`, `resilience4j-retry`, `micrometer-tracing`
- LLM: Anthropic 또는 OpenAI Java SDK. 키가 없으면 **fake LLM**으로 대체 — 정해진 시나리오에 따라 미리 준비된 tool call JSON을 돌려주는 단순 구현으로 시작한다. 워크플로 자체를 검증할 때는 진짜 모델보다 결정적인 가짜가 낫다.
- 외부 의존성: `findPatient`, `findRecentPrescription`, `resendPrescription`을 인메모리 `Map<String, ...>`으로 구현한 fake adapter. 일정 비율로 5xx와 timeout을 주입할 수 있게 둔다.
- 관측: `logs/agent-audit.jsonl` 파일에 줄 단위 JSON으로 audit를 적재. 분석은 `jq`로 충분하다.

## 실행 가능한 시나리오

다음 시나리오는 손으로 굴려보면서 워크플로의 실패 모드를 익히는 데 유용하다.

1. **정상 경로**: "처방 다시 보내줘" → 분류 → `findPatient` → `findRecentPrescription` → `resendPrescription` → 최종 답변. audit log 4줄, 모두 성공.
2. **권한 부족**: 인증된 사용자가 가족 계정 권한이 없는데 가족의 처방 재발송을 요청. 모델은 도구를 부르려 하지만 dispatcher가 `not_authorized`로 거절. 모델이 사람 상담사로 escalate.
3. **Hallucinated 환자 ID**: 모델이 그럴듯하지만 존재하지 않는 환자 ID를 만들어냄. 의미 검증에서 거절. 모델이 본인 확인 단계로 되돌아감.
4. **외부 SMS 게이트웨이 5xx**: `resendPrescription`이 idempotency key와 함께 한 번 호출되고 실패. 재시도 정책 상 비-idempotent로 분류돼 있다면 재시도 없이 사용자에게 사과 + 콜백 예약 도구로 우회.
5. **부분 성공**: SMS는 발송됐으나 알림 푸시 큐 적재 실패. observation에 `{"sms": "sent", "push": "queue_failed"}`로 정직히 기록. 모델 답변은 "문자로는 보내드렸고 앱 알림은 잠시 후 다시 시도하겠다"가 돼야 한다. "모두 발송 완료"가 되어선 안 된다.
6. **루프 폭주**: 모델이 같은 도구를 반복 호출. step 가드가 6회에서 끊고 escalate.

각 시나리오는 통합 테스트로 묶어둘 수 있다. fake LLM은 시나리오별 스크립트를 받아 결정적으로 동작하게 만든다. 이렇게 하면 모델 응답이 바뀌어도 워크플로 가드가 잘 작동하는지를 회귀 테스트로 묶을 수 있다.

## 설계 점검 질문

설계를 검토할 때 스스로 던져볼 질문과 답의 뼈대.

### "LLM Agent 시스템에서 가장 어려운 부분은 무엇인가?"

핵심은 모델의 비결정성과 시스템의 결정성을 잇는 경계 설계다. 구체적으로는 (1) 도구 메타데이터를 코드와 한 곳에 두는 레지스트리, (2) 모델 출력에 대한 두 단계 검증(스키마 + 의미), (3) 권한·idempotency·audit를 dispatcher 한 지점에 모아 우회 경로를 없애는 것이다.

### "Tool Calling에서 hallucination을 어떻게 줄이는가?"

모델은 "잘 모를 때도 그럴듯한 인자"를 만든다는 전제에서 시작한다. 막는 게 아니라 **걸러내는** 설계라고 표현한다. 스키마 검증, 도메인 의미 검증, 사용자 권한·소유권 검증, 그리고 거절을 모델에게 정중한 observation으로 돌려보내 다음 step이 본인 확인 같은 안전한 경로로 흐르도록 유도한다. 거절 메시지에 내부 정보를 흘리지 않는다는 점도 같이 말한다.

### "ReAct와 Plan-then-Execute 중 무엇을 선택할 것인가?"

도메인이 정형화돼 있고 감사 추적이 중요하다면 Plan-then-Execute의 약식 버전이 잘 맞는다. 자유도는 줄지만 재현성과 비용 통제가 좋아진다. ReAct는 도구 단계 안에서 제한적으로만 허용한다. 중요한 것은 어떤 패턴이 더 멋진지가 아니라, 도메인의 위험도와 감사 요구에 맞게 선택하는 것이다.

### "비용·지연 폭주를 어떻게 막을 것인가?"

루프당 step 수, 누적 토큰, 누적 시간, 누적 비용 가드를 sessions 단위로 두고, 각 도구의 평균/최대 응답 시간을 SLO로 관리한다. 외부 의존성에는 circuit breaker. 사용자 발화 1건에 대한 budget을 사전에 정하고, 초과 시 사람 상담사로 escalate.

### "관측은 어떻게 설계할 것인가?"

분류 결과, 노출 도구 목록, 모델 제안 tool call, 검증 결과, 실제 실행 결과, 최종 답변까지를 한 correlation id로 묶어 audit JSONL에 적재한다. 운영뿐 아니라 모델 평가의 입력이 된다는 점을 강조한다.

## 체크리스트

- [ ] 도구는 레지스트리 한 곳에서 등록되고, JSON Schema는 자동 생성되는가
- [ ] intent 분류 결과와 사용자 권한으로 노출 도구 풀이 동적으로 좁혀지는가
- [ ] 모델 출력은 dispatcher 입구에서만 시스템에 들어오는가
- [ ] 스키마 검증과 도메인 의미 검증이 모두 있는가
- [ ] 권한 검증은 도구 실행 직전에 dispatcher에서 이루어지는가
- [ ] side-effect가 있는 도구의 재시도는 idempotency key가 있을 때만 일어나는가
- [ ] 부분 성공이 모델에게 부분 성공으로 정확히 전달되는가
- [ ] step 수, 토큰, 시간, 비용 가드가 모두 있는가, 가드 발동 시 escalate 경로가 있는가
- [ ] 모든 단계가 하나의 correlation id로 묶여 audit JSONL에 적재되는가
- [ ] 거절·실패 메시지가 사용자에게 노출되어도 안전한 수준으로 일반화돼 있는가
- [ ] fake LLM 기반 통합 테스트로 정상·권한 부족·hallucination·외부 실패·부분 성공·루프 폭주 시나리오가 회귀 보호되는가
