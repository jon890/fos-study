# OpenClaw vs Hermes Agent — 갈아탈까 고민하며 정리한 비교

지금 나는 OpenClaw로 개인 에이전트를 돌리고 있다.
잘 동작하지만, 에이전트를 여러 개 구성하고 그 위에 제대로 된 화면을 얹는 그림을 그리다 보니 Hermes Agent가 자꾸 눈에 들어온다.
갈아탈지 말지를 결정하기 전에, 두 프레임워크가 메모리·구성·UI·자기개선에서 실제로 무엇이 다른지 공식 문서 기준으로 정리했다.

OpenClaw 자체의 내부 구조는 [OpenClaw는 context와 memory를 어떻게 관리하나](./openclaw-context-memory.md)에 따로 정리해 뒀고, 이 글은 두 프레임워크의 선택 기준에 집중한다.

> - **OpenClaw** — 채팅 앱에 붙어 사는 local-first 비서. config-first(SOUL.md + JSON5). TypeScript/Node 생태계.
> - **Hermes Agent** — Nous Research가 만든 self-improving 에이전트. Python 기반, MIT 라이선스. 스킬을 스스로 쓰고 고치는 학습 루프가 핵심.

## 정체성 차이

세부로 들어가기 전에 두 프레임워크의 지향점을 줄이면 이렇게 갈린다.

- **OpenClaw** — "내가 이미 쓰는 채팅 앱 안에 비서를 들여놓는다." 도달 범위(어디서 말을 거는가)가 강점.
- **Hermes** — "나만의 에이전트를 키운다." 자기개선과 구성 유연성이 강점.

내 고민이 "에이전트를 구성하고 화면을 얹는다"는 방향이라 여기서 이미 Hermes 쪽으로 무게가 실리는데, 그 대가가 무엇인지를 함께 봐야 한다.

## 메모리 — 수동 큐레이션 vs 다층 자동화

| 항목 | OpenClaw | Hermes Agent |
|---|---|---|
| 기본 구조 | workspace의 `MEMORY.md` + 일일 노트 (plain Markdown) | frozen-snapshot 파일 메모리 + SessionDB(SQLite/FTS5) |
| 검색 | `memory_search` / `memory_get` | `session_search`(FTS5) → LLM 요약 압축 |
| 확장 | 파일 기반 단일 구조 | 교체 가능한 Memory Provider 8종 (Honcho, Mem0 등) |
| 사용자 모델 | `USER.md` 수동 관리 | Honcho dialectic 추론으로 자동 누적 |

OpenClaw의 메모리는 **사람이 읽고 고치는 Markdown 파일**이다.
구조가 투명해서 무엇을 기억하는지 한눈에 보이고 직접 손댈 수 있다.

Hermes는 한 발 더 나갔다.
파일 메모리(`MEMORY.md`·`USER.md`)는 세션 시작 시 시스템 프롬프트에 불변(frozen)으로 박히고, 그와 별도로 모든 대화 턴이 SQLite(`~/.hermes/state.db`)에 FTS5 전문 인덱스로 쌓여 `session_search`로 과거를 끌어온다.
여기에 **Honcho** 같은 외부 메모리 provider를 꽂으면, 대화가 끝난 뒤 사후 추론(dialectic reasoning)으로 사용자의 선호·말투·목표를 자동으로 누적한다.
대화를 저장하는 게 아니라 거기서 결론을 도출하는 방식이다.

트레이드오프가 갈린다.
OpenClaw는 투명하고 단순한 대신 손이 간다.
Hermes는 자동화 폭이 넓은 대신 동작이 그만큼 불투명하고, provider를 붙이면 외부 의존이 늘어난다.

## 에이전트 구성 — JSON5 한 파일 vs 계층형 설정

OpenClaw는 `~/.openclaw/openclaw.json`(JSON5) 한 곳에서 `agents`·`channels`·`gateway`·`bindings`를 관리한다.
SOUL.md로 정체성을 주고 명령 한 번이면 산다 — 진입 장벽이 가장 낮다.

Hermes는 `~/.hermes/` 아래로 설정이 갈린다 — `config.yaml`(비밀 외 모든 설정), `.env`(시크릿), `SOUL.md`(정체성), `memories/`, `skills/`, `cron/`.
우선순위는 CLI 인자 > `config.yaml` > `.env` > 기본값으로 명확하다.
대신 `terminal` 백엔드를 local/docker/ssh/modal/daytona/singularity 중에서 고르는 등, 실행 환경을 갈아끼우는 유연성이 OpenClaw보다 넓다.

여러 에이전트를 서로 다른 실행 환경·권한으로 굴리려는 그림이라면 Hermes의 계층형 구성이 더 잘 맞는다.

## self-improving — 과장 없이 정확히

Hermes의 간판 기능이 "self-improving"이라 여기서 갈아타려는 사람이 많다.
그런데 이 표현은 오해되기 쉬워서 정확히 짚고 간다.

Hermes의 자기개선은 **실시간 강화학습이 아니다.** 두 축으로 이뤄진다.

- **스킬 누적**(런타임) — 에이전트가 도구를 5번 넘게 써서 어려운 작업을 끝내거나 막힌 길을 뚫으면, "다시 알아내지 않도록 스킬을 써라"는 시스템 프롬프트 유도에 따라 `skill_manage`로 `~/.hermes/skills/`에 절차를 기록한다. 다음에 같은 일을 만나면 그 스킬을 `patch`로 다듬는다. 이게 디스크에 영속된다.
- **GEPA 오프라인 진화**(별도 트랙) — `hermes-agent-self-evolution`이라는 **별개 연구 repo**에서, 실행 trace를 평가 데이터로 만들어 스킬·프롬프트를 진화시키고 사람 리뷰를 거쳐 PR로 제안한다. in-session 루프가 아니라 벤치마크 기반 batch 최적화다.

정리하면 Hermes의 "self-improving"은 절차 메모리(스킬)를 스스로 쌓고 다듬는 능력이지, 모델 가중치가 실시간으로 학습되는 게 아니다.
OpenClaw와 갈리는 지점은 여기다 — OpenClaw에서 스킬은 기본적으로 사람이 쓰고 고치는 반면, Hermes는 에이전트가 자기 경험에서 스킬을 만들어 낸다.
스킬을 학습 가능한 산출물로 보는 관점은 [SkillOpt 분석](./skillopt-skill-as-trainable-artifact.md)과 같은 결이다.

안전장치도 있다 — `skills.write_approval: true`로 두면 모든 스킬 쓰기가 `~/.hermes/pending/`에 staging되고, `/skills diff`·`/skills approve`로 검토한 뒤에야 반영된다.

## UI와 화면 얹기 — 내 고민의 핵심

내가 갈아타려는 가장 큰 이유가 "에이전트 위에 화면을 얹는다"이므로 여기를 자세히 본다.

**OpenClaw**는 채팅 앱 자체가 곧 UI다.
별도 화면을 만들기보다, 이미 쓰는 메신저(WhatsApp·iMessage·Telegram 등 20개 이상)와 companion 앱의 Live Canvas로 결과를 렌더링하는 모델이다.
"앱을 새로 만들지 않고 내가 있는 곳에서 쓴다"가 강점이지, "내 전용 대시보드를 짓는다"는 방향과는 결이 다르다.

**Hermes**는 화면 선택지가 단계적으로 준비돼 있다.

- **Classic CLI** (`hermes`) — Rich 패널·자동완성. 가장 가볍고 이식성 높다.
- **TUI** (`hermes --tui`) — 오픈소스 에이전트 중 손꼽히는 완성도의 터미널 UI. 모델·세션 선택과 승인은 모달 오버레이, 무깜빡임 렌더링. (내부 구현 스택은 Node.js subprocess까지만 공식 확인되고, 일부 글의 "React Ink" 서술은 공식 확정은 아니다.)
- **Web UI** (`hermes web`) — React SPA + FastAPI. Status·Sessions(FTS5 검색)·Config·Cron·Skills 탭. 기본 `http://localhost:8000`.
- **Hermes Studio** — 별도 데스크톱 앱 + 로컬 런타임 + 웹 콘솔. **Vue 3 + Naive UI** 스택. 채팅·모델/프로필 관리·플랫폼 채널 연결·잡 자동화·파일 검사·웹 터미널·Kanban 보드까지 로컬로 묶는다.

방향이 갈린다.
OpenClaw는 남이 만든 채팅 화면을 빌려 쓰고, Hermes는 에이전트 위에 내 화면(TUI → Web → Studio)을 직접 얹는 경로를 공식으로 깔아 둔다.
에이전트를 구성하고 그 위에 화면을 올리려는 내 그림에는 Hermes 쪽이 더 맞는다.

한 가지 사실 정정 — Hermes Web UI를 "3-panel Claude 스타일"로 소개하는 글이 있는데, 공식 소스에는 그런 표현이 없다.
메인 repo의 `hermes web`은 탭 기반 React UI이고, Vue 3 데스크톱/웹 콘솔은 Hermes Studio라는 별도 산출물이다.

## 멀티플랫폼과 실행 환경

| 항목 | OpenClaw | Hermes Agent |
|---|---|---|
| 메시징 채널 | 20개 이상 (iMessage·Matrix·Nostr·WeChat 등 폭넓음) | 20개 어댑터 (telegram·discord·slack·feishu 등) |
| 실행 환경 | Docker·SSH 중심 | local·Docker·SSH·Modal·Daytona·Singularity 등 |
| 스케줄링 | Gateway heartbeat (능동 점검) | gateway 내 cron 스레드 (`~/.hermes/cron/jobs.json`) |
| 생태계 | TypeScript/Node | Python |

채널 도달 범위는 OpenClaw가 약간 더 넓고, 실행 환경의 다양성은 Hermes가 앞선다.
둘 다 "하나의 게이트웨이에서 여러 표면(surface)"이라는 같은 철학을 공유하지만, OpenClaw는 채널 쪽으로, Hermes는 실행 백엔드 쪽으로 무게가 다르다.

## 언제 무엇을 — 선택 가이드

조사한 내용을 내 고민에 비춰 정리하면 이렇다.

**OpenClaw가 맞는 경우**

- 이미 쓰는 메신저 안에서 비서를 굴리고 싶다.
- 메모리·스킬을 직접 읽고 고치는 투명한 구조를 선호한다.
- TypeScript 생태계가 편하고, 빠르게 띄우는 게 우선이다.

**Hermes가 맞는 경우**

- 에이전트를 여러 개 구성하고 그 위에 전용 화면(TUI·Web·Studio)을 얹고 싶다. ← 내 경우
- 에이전트가 경험에서 스킬을 스스로 쌓는 자기개선을 원한다.
- 실행 환경(Docker·SSH·서버리스 등)을 갈아끼우는 유연성이 필요하다.
- Python 생태계가 편하다.

참고로 같은 계열에 GoClaw라는 세 번째 선택지도 있다 — single binary 배포와 멀티테넌트 보안(row-level 격리)에 강점이 있어 SaaS·B2B 플랫폼에 어울린다.
다만 라이선스가 CC BY-NC라 상업용은 별도 협약이 필요하고, 공개 자료가 적어 개인 용도에서 우선순위는 낮다.

## 갈아탄다면 — 이주 경로

마음이 Hermes로 기울 때 다행인 점은, **이주 도구가 공식으로 있다**는 것이다.

```bash
hermes claw migrate --dry-run             # 먼저 무엇이 옮겨지는지 확인
hermes claw migrate                       # 실제 이주
hermes claw migrate --preset user-data    # 사용자 데이터 위주
```

`~/.openclaw`를 자동 감지해서 SOUL.md·메모리·사용자 스킬(`~/.hermes/skills/openclaw-imports/`)·allowlist·플랫폼 설정·API 키를 가져온다.
`--dry-run`으로 먼저 점검한 뒤 옮길 수 있으니, 전부 버리고 처음부터 시작하는 부담은 없다.

## 내 결론

조사를 마치고 나니 고민의 축이 분명해졌다.
"화면을 얹는다"가 핵심 동기라면 Hermes가 그 경로를 공식으로 깔아 두었으니 방향은 맞다.
다만 갈아타며 받아들여야 할 것은 두 가지다 — Python 생태계로의 이동과, 메모리·자기개선이 자동화되는 만큼 늘어나는 불투명함이다.

그래서 내 다음 행동은 이렇게 잡았다.
바로 갈아타는 대신, `hermes claw migrate --dry-run`으로 내 OpenClaw 설정이 얼마나 매끄럽게 옮겨지는지부터 확인하고, Hermes Studio를 띄워 화면 경험이 내 기대에 맞는지 본 다음 결정한다.
self-improving이라는 간판에 끌려서가 아니라, 그 실체(스킬을 스스로 쌓는 절차 메모리)가 내 사용 패턴에서 실제로 이득인지를 보고 판단할 생각이다.

## 참고 링크

- [OpenClaw 공식 문서](https://docs.openclaw.ai/)
- [Hermes Agent 공식 문서](https://hermes-agent.nousresearch.com/docs/)
- [Hermes Agent — GitHub (Nous Research)](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent Deep Dive & Build-Your-Own Guide (dev.to)](https://dev.to/truongpx396/hermes-agent-deep-dive-build-your-own-guide-1pcc)
- [Hermes vs OpenClaw vs GoClaw 비교 (dev.to)](https://dev.to/truongpx396/hermes-agent-the-self-improving-agent-framework-and-how-it-compares-to-openclaw-goclaw-22mc)
- [Hermes Studio — 데스크톱·웹 콘솔 (GitHub)](https://github.com/EKKOLearnAI/hermes-studio)
- [Honcho — dialectic user modeling (Plastic Labs)](https://github.com/plastic-labs/honcho)
