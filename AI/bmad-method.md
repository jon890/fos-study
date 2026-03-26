# BMAD Method — AI 에이전트로 애자일 개발하는 방법론

AI 코딩 도구를 사용할 때 늘 부딪히는 문제가 있다. 자연어 프롬프트로 코드를 빠르게 만들 수는 있는데, 프로젝트가 커질수록 AI가 생성한 코드의 의도와 결정 과정이 불투명해진다. 어느 순간부터 "이 코드가 왜 이렇게 돼 있지?"를 추적하기 어려워진다.

BMAD Method는 이 문제를 정면으로 다루는 오픈소스 방법론이다. 새 프로젝트에 적용해보기 전에 개념부터 정리해봤다.

## BMAD가 뭔가

**BMAD** = **Breakthrough Method for Agile AI-Driven Development**

AI를 단순한 코드 자동완성 도구로 쓰는 게 아니라, 실제 개발팀처럼 역할이 나뉜 **전문화된 AI 에이전트 팀**을 구성해서 프로젝트를 진행하는 방식이다. 오픈소스([github.com/bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD))로 공개돼 있고, Claude Code를 포함한 대부분의 AI 코딩 어시스턴트에서 쓸 수 있다.

핵심 철학은 이렇다:

> "자연어 프롬프트는 출력 속도를 높여주지만, 의도와 결정 과정과 제약 조건을 숨긴다. 이게 블랙박스 코드를 만든다."

그래서 BMAD는 **코드 작성 전에 모든 기획 아티팩트를 먼저 문서화**하는 방식으로 이 문제를 해결한다.

## 두 단계로 나뉜 워크플로우

BMAD의 개발 라이프사이클은 크게 두 단계다.

### Phase 1 — 기획 (코드 한 줄 없이)

전문화된 AI 에이전트들이 순서대로 기획 문서를 만들어낸다. 각 문서는 다음 에이전트의 입력이 된다.

| 에이전트 | 역할 | 산출물 |
|---|---|---|
| **Analyst** | 요구사항 탐색, 제약 조건 파악 | Project Brief |
| **Product Manager (PM)** | Brief → 제품 명세서 | PRD (Product Requirements Document) |
| **Architect** | 시스템 설계, 컴포넌트 구조, 데이터 흐름 | Architecture Document |
| **Scrum Master** | 스토리 작성, 수용 기준 정의 | User Stories |

모든 산출물은 Git에 버전 관리된다. 기획이 어떻게 변해왔는지 추적할 수 있다.

### Phase 2 — 구현

기획 문서를 기반으로 구현 에이전트들이 작동한다.

| 에이전트 | 역할 |
|---|---|
| **Developer** | 스토리 기반 구현, 테스트 코드 작성 |
| **QA** | 코드 리뷰, 품질 개선, 리팩터링 |

스펙 문서가 있으니 Developer 에이전트가 맥락 없이 코드를 "발명"하는 일이 줄어든다. AI 환각(hallucination)이 줄어드는 이유가 여기 있다.

## 왜 이 방식이 효과적인가

### 문서가 계약서 역할을 한다

프롬프트 히스토리 대신 명세서(PRD, Architecture doc)가 AI의 행동 기준이 된다. 채팅창을 닫아도 맥락이 사라지지 않는다.

### 에이전트 간 핸드오프가 명확하다

Analyst가 만든 Brief → PM의 PRD → Architect의 설계 → Developer의 구현. 각 단계에서 어떤 정보가 어떻게 변환됐는지 추적 가능하다.

### 기존 AI 도구와 호환된다

YAML 기반 워크플로우로 에이전트를 정의하기 때문에, Claude Code, Cursor, Copilot 등 시스템 프롬프트를 지원하는 도구라면 어디든 적용할 수 있다.

## agents.md와의 관계

BMAD의 각 에이전트는 결국 [agents.md](./agents/agents.md) 방식으로 역할을 정의한다. Analyst 에이전트는 "요구사항 분석가" 페르소나를 갖고, Developer 에이전트는 "구현 담당자"로서 특정 Boundary(건드리면 안 되는 것)를 갖는다.

agents.md가 "AI에게 역할을 부여하는 방법"이라면, BMAD는 "역할이 정해진 AI들을 어떤 순서로, 어떤 아티팩트를 주고받으며 협업시키는가"를 다루는 상위 레이어다.

## 2주 MVP 개발에 어떻게 쓸 수 있나

애자일하게 짧은 기간 내에 MVP를 만들어야 할 때 BMAD를 적용하면 이런 흐름이 된다:

```
Day 1-2: Analyst → Project Brief 작성
Day 2-3: PM → PRD 작성 (기능 범위 명확화)
Day 3-4: Architect → 시스템 설계
Day 4-5: Scrum Master → 스토리 breakdown
Day 5-14: Developer + QA 루프
```

전통적인 방식에서 "요구사항 문서 먼저 → 개발"이 시간이 많이 걸리는 이유는 문서 작성이 사람에게 부담되기 때문이다. BMAD에서는 AI 에이전트가 문서 초안을 만들고 사람이 검토/보완하는 방식이라 훨씬 빠르다.

## BMAD의 한계 — 솔직하게

장점만 있는 건 아니다. GitHub 이슈([#2003](https://github.com/bmad-code-org/BMAD-METHOD/issues/2003))에서도 구조적 모순이 지적되고 있다.

| 한계 | 내용 |
|---|---|
| **컨텍스트 비용** | PRD + Architecture doc만 해도 수만 토큰. 작은 모델이나 컨텍스트 제한 환경에서는 버티기 어렵다 |
| **소규모 프로젝트엔 과도함** | 에이전트 7개, YAML 워크플로우, 문서 세트... 간단한 기능 추가에 이 셋업을 다 갖추는 건 배보다 배꼽이 크다 |
| **학습 곡선** | 단순 프롬프트 → 에이전트 역할/핸드오프/YAML 설정 이해까지 진입장벽이 있다 |
| **설계 역설** | "비개발자도 쓸 수 있다"고 홍보하지만, AI가 생성한 대량의 코드를 추적·검토하려면 결국 개발 경험이 필요하다 |

## 대안 비교

BMAD 말고 다른 선택지도 있다.

| 도구/방법론 | 성격 | BMAD 대비 |
|---|---|---|
| **[CrewAI](https://github.com/crewAIInc/crewAI)** | 역할 기반 멀티에이전트 실행 프레임워크 | BMAD는 방법론, CrewAI는 실행 엔진. 상호보완 가능 |
| **[AutoGen](https://github.com/microsoft/autogen)** | 멀티에이전트 대화 프레임워크 | 오픈엔디드 문제 해결에 강함. BMAD보다 유연하지만 구조가 약함 |
| **[LangGraph](https://github.com/langchain-ai/langgraph)** | 그래프 기반 워크플로우 | 복잡한 조건 분기에 강함. 엔지니어링 비용이 높아서 팀 규모가 있어야 효과적 |
| **Vibe Coding** | 그냥 프롬프트로 바로 코딩 | 속도는 빠르지만 BMAD가 해결하려는 "블랙박스 코드" 문제를 그대로 안고 간다 |
| **Spec Kit / OpenSpec** | 가벼운 스펙 문서 방식 | BMAD보다 오버헤드가 적고 실용적. 체계는 덜하지만 소규모 팀엔 오히려 맞을 수 있다 |

> CrewAI vs AutoGen 선택 기준: "어떻게 풀지 이미 알고 자동화하고 싶다" → CrewAI, "AI가 스스로 해법을 찾게 하고 싶다" → AutoGen

## 어떻게 접근하면 좋을까

풀 BMAD 워크플로우를 처음부터 다 적용하면 셋업 비용이 크다. **BMAD의 핵심 아이디어만 먼저 차용**하는 게 현실적이다:

1. 코드 전에 PRD/Brief를 AI로 초안 생성 → 사람이 검토·보완
2. 각 에이전트 역할을 명시한 시스템 프롬프트 준비
3. 산출물(기획 문서, 아키텍처 결정 등)을 Git에 커밋하는 습관

팀이 이 흐름에 익숙해지면 그때 YAML 워크플로우나 정식 에이전트 구조로 확장하는 방향이 낮은 리스크로 도입하는 방법이다.

## 참고

- [BMAD-METHOD GitHub](https://github.com/bmad-code-org/BMAD-METHOD)
- [공식 문서](https://docs.bmad-method.org/)
- [What is the BMad Method? — AngelHack DevLabs](https://devlabs.angelhack.com/blog/bmad-method/)
- [Applied BMAD — Reclaiming Control in AI Development](https://bennycheung.github.io/bmad-reclaiming-control-in-ai-dev)
- [BMAD Structural Issues #2003](https://github.com/bmad-code-org/BMAD-METHOD/issues/2003)
- [Vibe Coding vs BMAD Method](https://xantygc.medium.com/vibe-coding-vs-bmad-method-the-clash-of-titans-in-ai-development-f5ba2c0a5dcc)
- [Open-Source AI Agents 2026: CrewAI vs AutoGen vs OpenDevin](https://www.houseoffoss.com/post/open-source-ai-agents-in-2026-crewai-vs-autogen-vs-opendevin)
