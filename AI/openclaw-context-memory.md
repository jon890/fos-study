# OpenClaw는 context와 memory를 어떻게 관리하나 — 나만의 에이전트를 구성하는 법

OpenClaw를 쓰면서 "이 에이전트가 어제 일을 어떻게 기억하지?", "긴 대화가 쌓이면 context는 어떻게 관리되지?" 가 궁금해졌다.
config 파일 몇 개만 만지면 에이전트가 살아 움직이는데, 그 안에서 무슨 일이 벌어지는지 알아야 내가 원하는 대로 길들일 수 있다.

이 글은 OpenClaw의 context·memory 관리 방식을 공식 문서 기준으로 정리하고, 그 위에서 나만의 에이전트를 구성하는 흐름까지 다룬다.
오래 실행되는 AI 에이전트의 설계 관점은 [하네스 엔지니어링](./harness-engineering.md)에서 더 일반적으로 다루는데, OpenClaw는 그 원칙들이 실제 제품에서 어떻게 구현됐는지 보여주는 좋은 사례다.

> OpenClaw는 오픈소스 자율 AI 에이전트 프레임워크다(이전 이름 Clawdbot → Moltbot, MIT 라이선스).
> 채팅 앱에 붙어 사는 local-first 개인 비서로, 셸·파일·브라우저·Docker를 직접 다루고 20개가 넘는 메시징 플랫폼에 연결된다.

## context와 memory는 다르다 — 가장 중요한 구분

OpenClaw 문서가 가장 먼저 못 박는 개념이 이것이다.

> "Context is not the same thing as 'memory': memory can be stored on disk and reloaded later; context is what's inside the model's current window."

- **memory** — 디스크에 저장되고 나중에 다시 로드되는 영속 상태. 파일로 남는다.
- **context** — 지금 이 순간 모델 윈도우 안에 들어 있는 것. 매 호출마다 조립된다.

둘을 헷갈리면 "왜 기억은 하는데 지금 대화에선 모르지?" 같은 혼란이 생긴다.
memory에 저장돼 있어도 그게 context로 주입되지 않으면 모델은 그 순간 그걸 못 본다.
이 구분이 아래 모든 동작의 바탕이다.

## memory — 디스크에 저장된 것만 기억한다

OpenClaw의 메모리는 화려한 벡터 DB가 아니라 **plain Markdown 파일**이다.
기본 경로는 에이전트 workspace(`~/.openclaw/workspace`) 안이고, 설계 원칙은 단순하다.

> 시스템은 "디스크에 저장된 것만 기억하고, 숨은 상태는 없다(no hidden state)."

메모리 파일은 역할별로 나뉜다.

| 파일 | 역할 | 로드 시점 |
|---|---|---|
| `MEMORY.md` | 장기 기억 — 영속적 사실·선호·결정 | 모든 DM 세션 시작 시 자동 |
| `memory/YYYY-MM-DD.md` | 일일 노트 — 진행 중 맥락·관찰 (append-only) | 오늘·어제 노트 자동 |
| `DREAMS.md` (선택) | Dream Diary — dreaming sweep 요약 | 선택적 |

에이전트는 두 도구로 메모리에 접근한다.

- `memory_search` — 의미·키워드 검색
- `memory_get` — 파일·라인 직접 접근

흥미로운 디테일 하나. `MEMORY.md`가 너무 커져서 bootstrap 예산을 넘으면, **디스크 파일은 그대로 두고 context에 주입되는 사본만 잘라낸다**(truncate).
즉 기억 자체는 보존되지만 지금 윈도우에 다 들어가지 못할 뿐이다.
잘렸는지는 `/context list`나 `openclaw doctor`로 확인한다.
여기서도 context와 memory의 분리가 그대로 드러난다.

## context window 조립과 compaction

매 모델 호출마다 context는 다음을 조립해서 만든다.

- 시스템 프롬프트 — 도구 목록·스키마(JSON, 윈도우에 카운트됨), 스킬 목록(이름+설명만), workspace 메타데이터
- workspace bootstrap 파일 — `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md` 등
- 대화 레이어 — 현재 세션의 메시지, 도구 호출·결과, 첨부

bootstrap 파일에는 주입 상한이 걸려 있다.

- 파일당 `bootstrapMaxChars` — 기본 20,000자
- 전체 `bootstrapTotalMaxChars` — 기본 60,000자

핵심은 **스킬 본문이 on-demand로만 로드된다**는 점이다.
시스템 프롬프트에는 스킬의 이름과 설명만 들어가고, `SKILL.md` 전문은 그 스킬이 필요할 때만 읽힌다.
이 progressive disclosure 덕에 스킬을 수십 개 등록해도 평소 context가 가볍게 유지된다.

대화가 길어지면 `/compact` 명령이 오래된 이력을 요약 항목으로 압축한다.
최근 메시지는 그대로 두고, 디스크의 전체 이력은 보존한 채 윈도우 공간만 비운다.

여기에 영리한 안전장치가 하나 있다.
**compaction 직전에 OpenClaw는 보이지 않는 턴(silent turn)을 한 번 돌려**, 에이전트에게 "중요한 맥락을 메모리 파일에 저장하라"고 상기시킨다.
요약 과정에서 맥락이 날아가기 전에 디스크로 한 번 흘려보내는 것이다(memory flush).
context는 휘발성이고 memory는 영속이라는 설계가, 압축이라는 위험한 순간에 둘을 잇는 방식이다.

context가 지금 무엇으로 차 있는지는 명령으로 들여다볼 수 있다.

- `/status` — 윈도우 충만도, 세션 설정
- `/context list` — 주입된 파일과 대략적 토큰 수
- `/context detail` — 파일·도구 스키마·스킬별 분해
- `/context map` — context 기여자를 treemap으로

## SOUL.md — 에이전트의 목소리

memory가 "무엇을 아는가"라면, SOUL.md는 "어떻게 말하는가"다.

> "SOUL.md is where your agent's voice lives."

이 파일은 일반 세션에 주입되어 모든 응답의 톤에 직접 영향을 준다.
문서가 권하는 내용은 다음과 같다.

- 톤과 커뮤니케이션 스타일
- 표명된 의견, 간결함 선호, 유머 접근 방식
- 경계와 제약, 기본 직설성 수준

반대로 담지 말라는 것도 분명하다 — 인생 이야기, 변경 이력, 보안 정책 덤프, "분위기만 잔뜩 늘어놓은 글(wall of vibes)".
설계 철학은 한 줄로 압축된다.

> "Short beats long. Sharp beats vague."

**주의할 점** — SOUL.md에는 강제된 고정 스키마가 없다.
커뮤니티 템플릿들이 "Core Identity / Responsibilities / Communication Style ..." 같은 섹션 구조를 쓰지만, 그건 관례이지 규칙이 아니다.
정확히 말하면 SOUL.md는 **자유 형식 Markdown으로 쓰는 행동 규칙 모음**이다.
이 점은 [CLAUDE.md를 규칙으로 쓰는 법](./claude-code-memory-rules.md)에서 다루는 "규칙 파일을 주입한다"는 발상과 같은 계열이다.

## AgentSkill — 스킬이 곧 능력 단위

OpenClaw에서 에이전트에 능력을 더하는 단위가 스킬이다.
각 스킬은 `SKILL.md`(YAML frontmatter + Markdown 본문)를 담은 디렉터리다.

frontmatter의 핵심 필드:

- 필수 — `name`(슬래시 커맨드·allowlist 키), `description`
- 선택 — `user-invocable`(기본 true), `command-dispatch`, `metadata`(`requires.env`/`requires.bins` 같은 게이팅)

스킬도 메모리처럼 progressive disclosure를 따른다.
시작 시 각 스킬의 **이름과 설명만** 로드하고, 작업이 그 설명에 매칭될 때만 전문을 읽는다.
스킬 하나의 평소 토큰 오버헤드는 24토큰 남짓에 불과하다.
이 구조는 [Claude Code의 Skill 시스템](./claude-code-skill-system.md)과 사실상 같은 발상이고, 포맷도 Claude Code·Cursor 컨벤션과 호환된다.

스킬은 6계층 우선순위로 탐색된다.

| 우선순위 | 소스 | 경로 |
|---|---|---|
| 1 | Workspace skills | `<workspace>/skills` |
| 2 | Project agent skills | `<workspace>/.agents/skills` |
| 3 | Personal agent skills | `~/.agents/skills` |
| 4 | Managed/local skills | `~/.openclaw/skills` |
| 5 | Bundled skills | 설치 시 동봉 |
| 6 | Extra directories | `skills.load.extraDirs` + 플러그인 |

같은 이름이 여러 곳에 있으면 최상위 우선순위가 이긴다.
스킬은 ClawHub 레지스트리에서 설치할 수도 있다.

```bash
openclaw skills install <slug>              # workspace 설치
openclaw skills install <slug> --global     # 모든 에이전트
openclaw skills install git:owner/repo@ref  # Git 소스
openclaw skills verify <slug>               # 보안 스캔
```

ClawHub 설치는 보안 스캔을 거친다 — frontmatter가 선언한 비밀(`requires.env` 등)과 실제 코드가 참조하는 비밀이 일치하는지 검사해 불일치를 표시한다.

## Gateway와 heartbeat — 에이전트가 살아 있게 하는 것

지금까지가 "한 번의 대화"를 구성하는 요소였다면, Gateway는 그것들을 **항상 켜진 프로세스**로 묶는다.

Gateway는 단일 장기 실행 Node.js 프로세스다(기본 포트 18789).
macOS는 launchd, Linux는 systemd user 서비스로 데몬화하길 권한다.
담당하는 일은 채널 연결, 세션 상태, 에이전트 루프, 모델 호출, 도구 실행, 메모리 영속화까지 전부다.

내부는 대략 다섯 서브시스템으로 나뉜다.

- **Channel adapters** — 플랫폼별 인바운드 메시지를 정규화 (WhatsApp은 Baileys, Telegram은 grammY 등)
- **Session manager** — 발신자 신원 해소. DM은 main 세션으로, 그룹 채팅은 자체 세션으로
- **Queue** — 세션별 실행을 직렬화
- **Agent runtime** — context 조립 → 모델 호출 → 도구 실행 → 결과 피드백을 완료까지 반복
- **Control plane** — WebSocket API

그리고 OpenClaw를 단순 챗봇과 구분 짓는 기능이 **heartbeat**다.
Gateway 데몬은 주기적으로 에이전트를 깨워 능동적으로 일하게 한다.

- 기본 간격은 30분 (Anthropic OAuth/토큰 인증이 감지되면 1시간)
- 매 tick마다 에이전트는 "Read HEARTBEAT.md if it exists. Follow it strictly." 프롬프트를 받는다
- `HEARTBEAT.md`는 workspace의 선택적 체크리스트 — 30분마다 고려해도 안전할 만큼 작고 안정적인 것만 담는다
- 처리할 게 없으면 `HEARTBEAT_OK`로 끝나고, 있으면 알림을 보낸다

heartbeat 설정의 주요 키:

- `heartbeat.every` — 간격 (기본 `30m`, `0m`이면 비활성)
- `heartbeat.target` — 알림 라우팅 대상 (`none`/`last`/명시 채널)
- `heartbeat.directPolicy` — DM 전달 허용 여부
- `isolatedSession: true` — 매 heartbeat를 이력 없는 fresh 세션으로 (토큰 약 100K → 2~5K로 절감)
- `activeHours` — 지정 시간대 밖에서는 heartbeat skip

여기서 다시 메모리·context 설계가 빛난다.
`isolatedSession`을 켜면 heartbeat는 과거 대화 이력 없이 fresh 세션으로 돌아 토큰을 아끼는데, 그래도 `MEMORY.md`는 세션 시작 시 로드되므로 "기억은 유지하되 대화 맥락은 비운" 상태로 점검만 수행한다.
영속 memory와 휘발 context를 분리해 둔 덕에 가능한 최적화다.

## 나만의 에이전트를 구성하는 흐름

OpenClaw의 슬로건은 "Write a SOUL.md, run a command, your agent is live"다.
config-first라 Python도, 체인도, 그래프도 없다.

설치와 온보딩:

```bash
# 설치 (Node 22.19+ 권장)
curl -fsSL https://openclaw.ai/install.sh | bash

# 온보딩 — 모델 provider 선택, API 키, Gateway 설정 (약 2분)
openclaw onboard --install-daemon

# Gateway 상태 확인 (포트 18789)
openclaw gateway status

# 대시보드
openclaw dashboard        # http://127.0.0.1:18789/
```

그다음 config-first 흐름은 이렇게 이어진다.

1. **SOUL.md 작성** — workspace에 톤·의견·경계를 담는다. 없으면 기본 비서로 동작한다.
2. **스킬 추가** — `openclaw skills install <slug>`로 ClawHub에서 가져오거나, `<workspace>/skills/<name>/SKILL.md`를 직접 쓴다. 에이전트별 노출은 `agents.list[].skills`로 제어한다.
3. **메모리·heartbeat** — `MEMORY.md`와 일일 노트는 에이전트가 채워가고, 능동 동작이 필요하면 `HEARTBEAT.md` 체크리스트를 둔다.
4. **설정 파일** — `~/.openclaw/openclaw.json`(JSON5). 주요 키는 `agents`(모델·스킬·sandbox), `channels`, `gateway`, `session`, `bindings`(멀티 에이전트 라우팅), `cron`, `hooks`. 모델은 `agents.defaults.model.primary`에 `"anthropic/claude-sonnet-4-6"`처럼 `provider/model` 형식으로 지정한다.

디렉터리 레이아웃은 단일 에이전트와 멀티 에이전트가 다르다는 점만 기억하면 된다.

단일 에이전트(기본):

```
~/.openclaw/
├── openclaw.json          # JSON5 설정
├── .env
└── workspace/
    ├── SOUL.md, AGENTS.md, TOOLS.md, USER.md ...
    ├── MEMORY.md
    ├── memory/YYYY-MM-DD.md
    └── skills/<name>/SKILL.md
```

멀티 에이전트일 때는 에이전트마다 상태가 분리된다 — 세션 이력은 `~/.openclaw/agents/<agentId>/sessions`, 인증은 같은 디렉터리 하위로 격리된다.

## 정리 — 단순한 파일이 만드는 견고함

OpenClaw의 memory·context 설계에서 배울 점은, 화려한 인프라 없이 **plain Markdown 파일과 명확한 구분**만으로 오래 사는 에이전트를 만들었다는 것이다.

- memory와 context를 개념적으로 분리해 "기억하지만 지금 모르는" 상황을 설명 가능하게 만들었다.
- progressive disclosure로 스킬과 메모리를 평소엔 가볍게, 필요할 때만 무겁게 로드한다.
- compaction 직전의 memory flush처럼, 위험한 순간에 휘발성 context를 영속 memory로 흘려보내는 안전장치를 뒀다.
- heartbeat로 "요청에 답하는 봇"을 "스스로 점검하는 비서"로 끌어올렸다.

나만의 에이전트를 만들려면 결국 이 네 가지를 내 손으로 설계하는 셈이다 — 무엇을 기억할지(MEMORY.md), 어떤 목소리로 말할지(SOUL.md), 무슨 능력을 가질지(skills), 언제 스스로 움직일지(HEARTBEAT.md).
이 관점은 같은 발상을 학습 가능한 산출물로 끌고 가는 [SkillOpt 분석](./skillopt-skill-as-trainable-artifact.md)과도 이어진다.

다른 선택지인 Hermes Agent와의 비교는 [OpenClaw vs Hermes Agent](./openclaw-vs-hermes-agent.md)에서 다룬다.

## 참고 링크

- [OpenClaw 공식 문서 — Context](https://docs.openclaw.ai/concepts/context)
- [OpenClaw 공식 문서 — Memory](https://docs.openclaw.ai/concepts/memory)
- [OpenClaw 공식 문서 — SOUL](https://docs.openclaw.ai/concepts/soul)
- [OpenClaw 공식 문서 — Skills](https://docs.openclaw.ai/tools/skills)
- [OpenClaw 공식 문서 — Gateway Configuration](https://docs.openclaw.ai/gateway/configuration)
- [OpenClaw 공식 문서 — Heartbeat](https://docs.openclaw.ai/gateway/heartbeat)
- [OpenClaw 공식 문서 — Multi-agent](https://docs.openclaw.ai/concepts/multi-agent)
- [awesome-openclaw-agents — SOUL.md 템플릿 모음](https://github.com/mergisi/awesome-openclaw-agents)
- [How OpenClaw Works — 아키텍처 해설 (Milvus Blog)](https://milvus.io/blog/openclaw-formerly-clawdbot-moltbot-explained-a-complete-guide-to-the-autonomous-ai-agent.md)
