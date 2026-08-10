# AI / LLM 엔지니어링

AI 에이전트·LLM·RAG·하네스 엔지니어링 학습 기록. 이론편과 실전편을 모두 다룬다.

## 하위 주제

- [RAG (Retrieval-Augmented Generation)](./RAG/README.md) — 임베딩, 벡터 검색, 실무 사례
- [Neo4j GraphRAG 학습 시리즈](./RAG/neo4j-graphrag/README.md) — 관계 탐색과 원문 근거를 제공하는 에이전트 검색 도구 구축
- [LangGraph](./langgraph/langgraph-overview.md) — 에이전트 워크플로를 그래프로 통제하기
- [LangGraph로 에이전트 워크플로 만들기 (시리즈)](./langgraph/langchain-vs-langgraph-boundary.md) — Java 백엔드 관점의 7편 (아래 목록 참고)
- [AGENTS.md 포맷](./agents-md-format.md) — AI coding agent 동작 지침서
- [DESIGN.md, Google Stitch, Claude Design](./design-md-and-ai-design-tools.md) — AI 에이전트와 디자인의 새 컨벤션 + fos-blog 6주 도입 회고

## LangGraph 시리즈 (langgraph/)

Java 백엔드 관점에서 LangGraph를 처음부터 익히고 langgraph4j로 옮기기까지 7편으로 정리했다.

1. [LangChain과 LangGraph는 왜 나뉘어 있나](./langgraph/langchain-vs-langgraph-boundary.md) — 체인과 런타임의 경계, Java 진영 3자 비교
2. [State와 Reducer](./langgraph/langgraph-state-and-reducer.md) — 그래프를 흐르는 상태 설계, 병렬에서 예외가 나는 이유
3. [Checkpoint](./langgraph/langgraph-checkpoint-durable-execution.md) — 장애와 중단에서 살아남는 실행, Spring Batch 대응 구조
4. [Human-in-the-Loop](./langgraph/langgraph-human-in-the-loop.md) — 사람 승인을 그래프에 새기기, 함정 다섯 가지
5. [Agentic GraphRAG](./langgraph/langgraph-agentic-graphrag.md) — 지식그래프 검색 통제, Corrective RAG와 Self-RAG와 Adaptive RAG
6. [langgraph4j 실전](./langgraph/langgraph4j-in-spring-boot.md) — Spring Boot에 얹기, 버전과 의존성 실측
7. [학습 로드맵](./langgraph/langgraph-learning-roadmap.md) — 읽는 순서와 단계별 실습 과제

## Agent 설계 (agent/)

- [엔터프라이즈 AI Agent 설계](./agent/enterprise-ai-agent-design.md) — reasoning, tool, memory, cost, governance를 운영 시스템으로 묶는 허브 문서
- [온톨로지에서 코딩 에이전트 컨텍스트까지](./ontology-knowledge-graph-agent-context.md) — 클래스·별칭·관계 설계와 벡터 RAG 비교 평가
- [LLM Tool Calling 에이전트 워크플로](./agent/llm-tool-calling-agent-workflow.md) — Tool Use 루프, 결정성/관측성 설계
- [Agentic Workflow 상태 관리](./agent/agentic-workflow-state-management-langgraph.md) — LangGraph State Graph, Checkpoint, HITL, Tool 권한 경계
- [Agentic Workflow 평가와 Risk Gate](./agent/agentic-workflow-evaluation-risk-gate.md) — 궤적 평가, LLM-as-a-judge, HITL, 안전 게이트

## 평가와 운영 (Applied AI)

- [LLM 평가 프레임워크](./llm-evaluation-framework.md) — 골든셋·회귀 테스트·LLM-as-a-judge·사람 피드백 루프
- [AI 제품 백엔드 안정성](./backend-reliability-for-ai-products.md) — 지연·비용·도구 실패·폴백/재시도/사람 에스컬레이션

## 하네스 엔지니어링

- [하네스 엔지니어링 이론편](./harness-engineering.md) — 개념, Anthropic/Fowler 사례, 설계 원칙
- [하네스 엔지니어링 실전편](./harness-engineering-practice.md) — 4인 에이전트 팀 파이프라인의 진화

## 에이전트 프레임워크

- [OpenClaw는 context와 memory를 어떻게 관리하나](./openclaw-context-memory.md) — SOUL.md·MEMORY.md·progressive disclosure·heartbeat, 나만의 에이전트 구성
- [OpenClaw vs Hermes Agent](./openclaw-vs-hermes-agent.md) — 메모리·구성·UI·self-improving 비교, 갈아탈지 선택 가이드

## Claude Code

- [Claude Code 스킬 시스템](./claude-code-skill-system.md)
- [Claude Teams 기본 개념](./claude-teams.md) — Agent Teams, SendMessage, 에이전트 타입
- [Claude Code 11일 사용 회고](./claude-code-usage-reflection.md) — 1탄: 데이터로 본 사용 패턴
- [Claude Code 5주 더 쓴 결과](./claude-code-usage-reflection-2.md) — 2탄: 스킬·CLAUDE.md를 키워가는 방식
- [Claude Code 메모리 규칙](./claude-code-memory-rules.md) — CLAUDE.md와 .claude/rules를 규칙으로 쓰는 법

## 방법론

- [사람용 CLI와 AI 에이전트용 CLI 설계](./agent-friendly-cli-design.md) — 구조화 출력, 미리보기, 비대화형 모드, 안전한 기본값
- [AI 에이전트와 함께 MVP 만들기 (dooray-cli 사례)](./mvp-with-ai-agent.md)

## 멀티모달

- [멀티모달 LLM](./multimodal.md) — 이미지·음성을 함께 다루는 모델

## 문서 도구

- [Docling](./docling.md) — IBM Research 문서 변환 툴킷
