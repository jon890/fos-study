# AI / LLM 엔지니어링

AI 에이전트·LLM·RAG·하네스 엔지니어링 학습 기록. 이론편과 실전편을 모두 다룬다.

## 하위 폴더

| 폴더 | 담는 것 |
| --- | --- |
| `agent/` | 에이전트를 운영 시스템으로 묶는 설계 |
| `llm/` | 모델 내부 계산과 입력 종류 |
| `RAG/` | 검색 증강 생성과 문서 파싱 |
| `ops/` | 평가 기준과 백엔드 안정성 |
| `harness/` | 에이전트에게 줄 지침과 실행 환경 설계 |
| `claude-code/` | Claude Code 제품 사용 기록 |
| `practice/` | 에이전트를 도구로 써서 개발하는 방법 |

## Agent 설계 (agent/)

- [엔터프라이즈 AI Agent 설계](./agent/enterprise-ai-agent-design.md) — reasoning, tool, memory, cost, governance를 운영 시스템으로 묶는 허브 문서
- [코딩 에이전트 장기 기억은 무엇을 저장하고 언제 다시 읽어야 할까](./agent/coding-agent-long-term-memory-design.md) — Codex·Claude Code의 파일 기반 기억에서 저장·조회·정정·삭제와 면접 설계 순서까지
- [Lost in the Middle와 컨텍스트 관리](./agent/lost-in-the-middle-context-management.md) — 긴 컨텍스트에서 가운데 정보가 사라지는 이유와 결정론적 조립 규칙
- [온톨로지에서 코딩 에이전트 컨텍스트까지](./agent/ontology-knowledge-graph-agent-context.md) — 클래스·별칭·관계 설계와 벡터 RAG 비교 평가
- [LLM Tool Calling 에이전트 워크플로](./agent/llm-tool-calling-agent-workflow.md) — Tool Use 루프, 결정성/관측성 설계

## LLM 내부 구조 (llm/)

- [LLM 내부 구조 읽는 순서](./llm/README.md) — Transformer 계산에서 환각과 긴 컨텍스트 실패까지 잇는 학습 순서
- [Transformer는 입력을 어떻게 다음 토큰 확률로 바꾸는가](./llm/transformer-from-tokens-to-logits.md) — token, embedding, Q·K·V, FFN, logits, KV cache
- [다음 토큰 예측은 왜 환각과 긴 컨텍스트 실패로 이어지는가](./llm/why-llms-hallucinate-and-lose-context.md) — 학습 목표와 자동회귀 생성에서 환각·위치 편향까지 이어지는 원리
- [멀티모달 LLM](./llm/multimodal.md) — 이미지·음성을 함께 다루는 모델

## RAG (RAG/)

- [RAG 학습 기록 전체 목록](./RAG/README.md) — 임베딩, 벡터 검색, 평가와 실무 사례
- [Neo4j GraphRAG 학습 시리즈](./RAG/neo4j-graphrag/README.md) — 관계 탐색과 원문 근거를 제공하는 에이전트 검색 도구 구축
- [Docling](./RAG/docling.md) — IBM Research 문서 변환 툴킷

## 평가와 운영 (ops/)

- [LLM 평가 프레임워크](./ops/llm-evaluation-framework.md) — 골든셋·회귀 테스트·LLM-as-a-judge·사람 피드백 루프
- [AI 제품 백엔드 안정성](./ops/backend-reliability-for-ai-products.md) — 지연·비용·도구 실패·폴백/재시도/사람 에스컬레이션

## 하네스 엔지니어링 (harness/)

- [하네스 엔지니어링 이론편](./harness/harness-engineering.md) — 개념, Anthropic/Fowler 사례, 설계 원칙
- [하네스 엔지니어링 실전편](./harness/harness-engineering-practice.md) — 4인 에이전트 팀 파이프라인의 진화
- [AGENTS.md 포맷](./harness/agents-md-format.md) — AI coding agent 동작 지침서
- [Claude Code 메모리 규칙](./harness/claude-code-memory-rules.md) — CLAUDE.md와 .claude/rules를 규칙으로 쓰는 법
- [DESIGN.md, Google Stitch, Claude Design](./harness/design-md-and-ai-design-tools.md) — AI 에이전트와 디자인의 새 컨벤션, fos-blog 6주 도입 회고

## Claude Code (claude-code/)

- [Claude Code 스킬 시스템](./claude-code/claude-code-skill-system.md)
- [Claude Teams 기본 개념](./claude-code/claude-teams.md) — Agent Teams, SendMessage, 에이전트 타입
- [Claude Code 11일 사용 회고](./claude-code/claude-code-usage-reflection.md) — 1탄: 데이터로 본 사용 패턴
- [Claude Code 5주 더 쓴 결과](./claude-code/claude-code-usage-reflection-2.md) — 2탄: 스킬·CLAUDE.md를 키워가는 방식

## 에이전트와 함께 개발하기 (practice/)

- [사람용 CLI와 AI 에이전트용 CLI 설계](./practice/agent-friendly-cli-design.md) — 구조화 출력, 미리보기, 비대화형 모드, 안전한 기본값
- [AI 에이전트와 함께 MVP 만들기 (dooray-cli 사례)](./practice/mvp-with-ai-agent.md)
