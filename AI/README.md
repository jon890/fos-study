# AI / LLM 엔지니어링

AI 에이전트·LLM·RAG·하네스 엔지니어링 학습 기록. 이론편과 실전편을 모두 다룬다.

## 하위 주제

- [RAG (Retrieval-Augmented Generation)](./RAG/README.md) — 임베딩, 벡터 검색, 실무 사례
- [LangGraph](./langgraph/langgraph-overview.md) — 에이전트 워크플로를 그래프로 통제하기
- [AGENTS.md 포맷](./agents-md-format.md) — AI coding agent 동작 지침서
- [DESIGN.md, Google Stitch, Claude Design](./design-md-and-ai-design-tools.md) — AI 에이전트와 디자인의 새 컨벤션 + fos-blog 6주 도입 회고

## Agent 설계 (agent/)

- [LLM Tool Calling 에이전트 워크플로](./agent/llm-tool-calling-agent-workflow.md) — Tool Use 루프, 결정성/관측성 설계
- [멀티턴 메모리 헬스케어 에이전트](./agent/multi-turn-memory-healthcare-agent.md) — 4계층 메모리, 헬스케어 도메인 특화 정책
- [Agentic Workflow 상태 관리](./agent/agentic-workflow-state-management-langgraph.md) — LangGraph State Graph, Checkpoint, HITL, Tool 권한 경계
- [Agentic Workflow 평가와 Risk Gate](./agent/agentic-workflow-evaluation-risk-gate.md) — 궤적 평가, LLM-as-a-judge, HITL, 안전 게이트

## 평가와 운영 (Applied AI)

- [LLM 평가 프레임워크](./llm-evaluation-framework.md) — 골든셋·회귀 테스트·LLM-as-a-judge·사람 피드백 루프
- [AI 제품 백엔드 안정성](./backend-reliability-for-ai-products.md) — 지연·비용·도구 실패·폴백/재시도/사람 에스컬레이션

## 하네스 엔지니어링

- [하네스 엔지니어링 이론편](./harness-engineering.md) — 개념, Anthropic/Fowler 사례, 설계 원칙
- [하네스 엔지니어링 실전편](./harness-engineering-practice.md) — 4인 에이전트 팀 파이프라인의 진화

## Claude Code

- [Claude Code 스킬 시스템](./claude-code-skill-system.md)
- [Claude Teams 기본 개념](./claude-teams.md) — Agent Teams, SendMessage, 에이전트 타입
- [Claude Code 11일 사용 회고](./claude-code-usage-reflection.md) — 1탄: 데이터로 본 사용 패턴
- [Claude Code 5주 더 쓴 결과](./claude-code-usage-reflection-2.md) — 2탄: 스킬·CLAUDE.md를 키워가는 방식
- [Claude Code 메모리 규칙](./claude-code-memory-rules.md) — CLAUDE.md와 .claude/rules를 규칙으로 쓰는 법

## 방법론

- [BMAD Method](./bmad-method.md) — AI 에이전트로 애자일 개발하는 방법론
- [AI 에이전트와 함께 MVP 만들기 (dooray-cli 사례)](./mvp-with-ai-agent.md)
- [SkillOpt — 스킬 문서를 신경망처럼 학습시킨다](./skillopt-skill-as-trainable-artifact.md) — 텍스트 공간 옵티마이저, 검증 게이트, 개인 스킬 적용 한계

## 멀티모달

- [멀티모달 LLM](./multimodal.md) — 이미지·음성을 함께 다루는 모델

## 문서 도구

- [Docling](./docling.md) — IBM Research 문서 변환 툴킷
