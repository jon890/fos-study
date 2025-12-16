# agents.md

- `agents.md`는 AI coding agent(예: Github Coplit)의 **동작 지침서** 역할을 하는 문서
- 프로젝트에서 AI 에이전트가 **어떤 역할을 수행해야 하는지, 어떤 정보가 필요한지, 무엇을 건드리면 안 되는지** 명확히 알려주는 표준 형식 문서

다르게 보면, 사람 개발자가 프로젝트 README/CONTRIBUTING을 통해 협업 지침을 제공하듯, **AI 에이전트에게 하는 운영 메뉴얼/컨텍스트 제공**이라고 보면됨

## 좋은 agents.md의 핵심 - 요약

- 좋은 `agents.md` 파일은 단순한 "도움말 풍의 프롬프트"가 아니라 **구체적인 운영 설명서** 수준으로 작성돼야 성공확률이 높다

### 1. 역할과 페르소나를 명확히 한다

- "일반적인 코딩 도우미" 대신 **특정 역할(agent)** 을 정의한다
  - 예: docs-agent, test-agent, security-agent 등
- 각 에이전트가 "누구인지", "무엇을 담당하는지", "어떤 능력을 가지고 있는지"를 명확히 설명해야 해

```md
---
name: docs_agent
description: Exper technical writer
---

You are an expert Markdown writer...
```

### 2. 수행할 명령어(Base Commands)를 초반에 정리

- 에이전트가 실제로 **실행해야 할 명령어를 구체적으로** 적는다.
  - 예: 테스트, 빌드, 린트 등 전체 실행 커맨드 + 플래그 포함

> `pytest -v`, `npm test`, `npm run docs:build`, `npx markdownlint docs/` 처럼
> 실제로 실행 가능하게 적는게 중요함

### 3. 구체적 코드 예시 제공

- 설명이 아니라 **실제 코드 스니펫**을 넣어야 AI가 스타일을 참고해서 안착된다
- 포맷팅, 스타일, 역할별 예시를 보이는 게 효과적

### 4. 명확한 경계(Boundaries) 설정

- 좋은 agents.md에는 다음과 같은 경계가 정의됨
  - **✅ Always do**: 반드시 지켜야 할 행동
  - **⚠️ Ask first**: 변경 전 질문/확인 필요
  - **🚫 Never do**: 절대 건드리면 안 되는 것들
  - 예시:
    - 🚫 시크릿 / 비밀번호 커밋 금지
    - 🚫 production config 변경 금지
    - ⚠️ 기존 문서 대규모 변경은 요청 필요

### 5. 프로젝트 구조 & 스택 명시

AI가 문맥을 이해하려면 "얘는 어떤 프로젝트야?"를 충분히 알려줘야 함 <br/>
-> 단순히 React project가 아니라 <br/>
**React 18 + TypeScript + Vite + Tailwind CSS**처럼 구체적으로

### 6. 다뤄야 할 6가지 핵심 영역

Github 분석에서 상위권 agents.md는 아래 항목들을 빠짐없이 다뤘음

- 1. 명령어(Commmands)
- 2. 테스트(Test instructions)
- 3. 프로젝트 구조(Project structure)
- 4. 코드 스타일(Code style)
- 5. Git 워크플로우(Git workflow)
- 6. 경계(Boundaires)

## Codex에서도 위와 같은 방식이 통하는가?

- 결론부터 말하면 **역시 agents.md 형태의 "프로젝트 컨텍스트 파일"을 읽고 그 지침에 맞춰 행동할 수 있음**
- 단, **중요한 차이점과 실제 동작 방식**이 있음

### 1. Codex(GPT Coding Agent)는 agents.md를 "표준 형식"으로 인식하나?

- 그렇다, 충분히 인식하고 그 지침을 따라 행동할 수 있다
- `agents.md`는 사실 Github Copilot 팀이 제안한 "AI 코드 에이전트용 컨텍스트 문서 포맷"일 뿐
- **OpenAI 모델이 특별히 전용 기능으로 지원하는 것은 아님**
- **일반적인 시스템 프롬프트 + 문맥 문서로서 매우 잘 작동한다**

> Codex도 프로젝트의 agents.md를 모델 입력으로 주면
> 역할, 경계, 코딩 스타일, 명령어 규칙을 그대로 따르는 멀티-에이전트처럼 작동한다

### 2. Codex가 agents.md의 지침을 실제로 따르는가?

- Codex/GPT 계열 모델은 다음 순서로 문서를 처리함
  - **1. 문서를 읽고 -> 역할(Role)을 구성**
  - **2. Boundary (Always / Ask / Never) 를 규칙으로 설정**
  - **3. 프로젝트 구조, 코드 스타일, 명령어 -> 정책 세팅**
  - **4. 유저 요청이 들어오면 -> 규칙에 맞게 실행하려고 함**
  - 5. 규칙 위반 요청이면 거절하거나 수정 제안하기도 함
- 예를 들어 agents.md에 이렇게 적어두면

  - ```md
    ## Boundaries

    Never modify files under /config/prod
    Ask before changing database schema
    Always write tests for new code
    ```

- Codex에게 작업을 요청하면
  - `/config/prod` 하위 수정 요청 -> 자동 거절
  - 마이그레이션 요청 -> "스키마 변경 전 확인 필요합니다." 라고 응답
  - 새 서비스 코드 작성 요청 -> 테스트 코드도 자동 생성
- **이게 실제로 Codex가 아주 잘하는 "규칙 기반 행동"**

## 결론 : agents.md 같은 컨텍스트 문서를 잘 정리해두면 어느 AI coding agnets를 쓰더라도 효과가 좋다

- 다만 완전한 "표준"은 아직 없다
- 그래도 사실상 표준처럼 굳어져 가는 패턴이 이미 존재하고 있고, 앞으로 더 통일될 가능성도 큼

### 1. agents.md는 "사실상 emerging standard"다

- Github Copilot 팀이 제안한 구조지만,
- Claude Ciode, Cursor, Gemini, Codex, Continue.dev 등 AI 툴들 전부가 **텍스트 기반 컨텍스트를 제공하면 지침을 따르는 구조**로 작동한다

> 즉 형식이 정해진 표준은 없지만, "역할 섬여 + 규칙 + 파일 구조 + 명령어"라는 패턴은 모든 LLM에게 잘 먹힌다.

모델들이 필요한 건 "파싱 가능한 구조화된 정보"지, 특정 포맷을 강제하는 표준이 아니기 떄문

그래서 agents.md 스타일은 모든 코드 모델이 이해하기 좋다

- Claude -> 자연어 지침 매우 잘 따름
- Codex/GPT -> 시스템 역할 기반 프롬프트에 최적화
- Cursor -> workspace 컨텍스트 기반의 규칙 잘 따름
- Gemini CLI –> 워크플로우 가이드 잘 인식

### 2. 왜 "표준"이 아직 없나?

- **1. LLM은 특정 포맷이 아니라 "자연어 규칙"을 이해하는 방식이라서**
  - JSON schema나 XML처럼 정확한 표준이 필요하지 않다
  - 즉, **사람처럼 설명하면 바로 이해하는 존재**라 표준의 필요성이 낮다
- **2. 각 회사가 자기 에이전트 생태계를 키우려 하기 때문**
  - Github -> agents.md
  - OpenAI -> system prompt + project context
  - Anthropic -> Claude project instructions
  - Cursor -> `.cursor/rules`
- **3. 에이전트 기능 자체가 아직 발전 중**
  - 표준을 만들기엔 업계가 너무 빠르게 변화하고 있음

## 최종 : 그렇다면 어떻게 작성하는게 좋을까?

현재 여러 에이전트를 테스트해본 개발자들과 Github의 분석까지 종합하면 <br/>
"LLM이 가장 잘 파싱하는 문서 구조"는 다음 6개 영역

### 1. 역할 정의 (Role / Persona)

```md
You are the <role>.
You responsibilities:
```

모든 LLM이 이 섹션을 가장 중요하게 본다

### 2. 프로젝트 개요 (Project Overview)

- 기술 스택
- 빌드 시스템
- 중요한 의존성
- 핵심 폴더 설명

LLM이 "이 프로젝트는 어떤 세계인지" 이해하는 단계

### 3. 디렉토리 구조 (File Structure)

```text
src/
  api/
  core/
  domain/
```

Cursor, Claude 모두 이런 트리는 아주 정확하게 인식한다

### 4. 스타일 가이드 & 코드 예시

이것도 모든 모델에서 효과가 좋다

- 네이밍 규칙
- 폴더별 책임
- 테스트 코드 샘플
- API 응답 포맷

예시는 말보다 강력하다

### 5. 명령어 목록 (Commands)

```sh
npm run test
npm run dev
npm run lint
```

모델이 로컬 환경을 실행하는 척 할 떄 중요

### 6. Boundaries (중요함)

모든 에이전트에서 **가장 강한 영향**을 끼치는 영역

```markdown
Always:

- 테스트 추가

Never:

- cofig/prod 수정
- secrets 노출

Ask Before:

- database schema changes
```
