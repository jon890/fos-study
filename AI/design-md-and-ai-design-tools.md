# AI 에이전트와 디자인의 새 컨벤션 — DESIGN.md, Google Stitch, Claude Design

1년 안에 디자인-개발 경계에서 셋이 동시에 등장했다. 2025년 5월 구글 I/O에서 **Stitch**가 발표됐고, 2026년 3월 그 안에서 **DESIGN.md** 포맷이 따로 오픈소스로 떨어졌고, 같은 해 4월에 Anthropic Labs가 **Claude Design**을 띄웠다. 같은 달에 VoltAgent의 [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 같은 71개 브랜드 DESIGN.md 컬렉션이 등장했다.

이 글에서는 셋이 같은 문제를 다른 각도로 풀고 있다는 시각을 정리한다. 그리고 fos-blog(이 블로그를 돌리는 Next.js 프로젝트)에 Claude Design을 6주간 도입하면서 발견한 것 — 그중 흥미로웠던 건 **DESIGN.md 표준 자체는 도입하지 않았는데도 도입 이득이 적지 않더라**는 점이었다.

---

## 큰 그림 — AI가 만드는 화면이 일관되지 않은 문제

코드 생성 단계에서 AI 에이전트는 이미 충분히 쓸 만하다. 다음 병목은 화면이다. "버튼을 추가해 줘" 한 번에는 잘 만들지만, 같은 프로젝트의 다른 페이지에서 같은 지시를 또 내리면 **색이 한 톤 어긋나고, 간격이 4px 다르고, hover 동작이 다르게 잡힌다**. 한 번 마무리한 화면을 다시 손대면 처음과 다른 디자인 결정이 들어온다.

세 도구는 이 문제에 각각 다른 각도로 답한다.

- **DESIGN.md**: 디자인 시스템을 마크다운으로 박아 두면 에이전트가 매번 동일한 기준으로 본다 → "**텍스트 표준**으로 일관성을 강제"
- **Google Stitch**: 자연어로 멀티 스크린·일관 컴포넌트를 한 번에 생성 → "**한 번 생성**에서 일관성을 만든다"
- **Claude Design**: 온보딩에서 codebase와 기존 디자인 파일을 읽어 design system을 자동 구성 → "**codebase가 곧 진실 소스**"

세 길이 동시에 굴러간다는 사실이 이 시점의 특징이다. 어느 길이 표준이 될지는 아직 정해지지 않았다.

---

## DESIGN.md — 디자인 시스템을 마크다운으로

Stitch 팀이 도입한 포맷이다. 2026년 3월 19일 Google Labs가 [드래프트 스펙을 오픈소스](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/)로 풀어 다른 도구가 채택할 수 있게 했다.

구조는 두 부분이다.

```yaml
---
# YAML front matter — machine-readable tokens
colors:
  primary: "#0070f3"
  background: "#0a0a0a"
typography:
  font-family: "Geist Sans"
spacing:
  base: 8px
---

## 비주얼 테마 — Markdown prose
무드, 밀도, 설계 철학을 사람이 읽기 좋은 산문으로 풀어 쓴다.
"왜 이 값을 골랐는지" rationale이 들어가는 자리.

## 색상 팔레트
의미론적 명칭 + HEX + 기능 역할.

## 컴포넌트
버튼, 카드, 입력 필드, 네비게이션의 상태별 정의.

## Do's and Don'ts
설계 가이드라인.
```

핵심 결정은 세 가지다.

- **framework-agnostic** — React/Vue/Svelte를 가리지 않고 **시각 규칙만** 정의한다. 구현은 에이전트가 알아서.
- **프로젝트 root에 `DESIGN.md`로 두면 자동 발견** — Stitch뿐 아니라 Claude·Cursor 같은 다른 코딩 에이전트도 컨벤션상 이 위치를 본다.
- **YAML 토큰 + Markdown 산문 결합** — JSON 스키마 단독이라면 LLM이 토큰의 의도를 추론하기 어렵고, Markdown 단독이라면 기계 추출이 어렵다. 둘을 한 파일에 묶어 양쪽을 모두 만족시킨다.

이 결정은 [AGENTS.md 포맷](./agents-md-format.md)과 결이 같다. 코딩 에이전트의 동작 지침서가 마크다운 한 파일로 수렴했듯이, 디자인 에이전트의 일관성 지침서도 같은 자리로 수렴하고 있다.

### awesome-design-md — 71개 브랜드 컬렉션

[VoltAgent의 awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 저장소는 Apple, Stripe, Vercel, Nike, Spotify, Linear, Notion 등 71개 유명 브랜드의 DESIGN.md를 모아 둔다. 각 항목은 `DESIGN.md` + `preview.html` + `preview-dark.html` 세 파일로 구성된다.

이용 패턴이 단순하다.

1. 원하는 브랜드의 `DESIGN.md`를 복사
2. 자기 프로젝트 root에 drop
3. 에이전트에게 "이 디자인과 일치하는 UI를 만들어 줘"

빠른 출발점으로는 강력하다. 단점은 **brand 종속**이다 — Stripe DESIGN.md를 그대로 쓰면 Stripe 톤이 그대로 들어온다. 자기 브랜드를 만들고 싶다면 결국 자체 작성으로 넘어가야 한다.

[getdesign.md](https://getdesign.md/), [designmd.app](https://designmd.app/en/) 같은 별도 컬렉션 사이트도 등장했다. 454개 디자인 시스템을 정리한 곳도 있다.

---

## Google Stitch — 자연어로 멀티 스크린

Stitch는 2025년 초 Google이 [Galileo AI](https://www.fastcompany.com/91528198/anthropic-claude-design-ai-design-tool)를 인수해 Gemini와 통합한 뒤 Google Labs 실험으로 띄운 도구다. 2025년 5월 I/O에서 발표됐다. 2026년 3월 19일 큰 업데이트로 정식 디자인 플랫폼 형태로 진화했다.

핵심 특징은 네 가지다.

- **멀티 스크린 생성** — 자연어로 앱 흐름 전체를 묘사하면 5개의 연결된 화면을 한 번에 생성. 일관된 타이포·컬러·컴포넌트 라이브러리를 자동으로 공유한다. "각 화면을 따로 만들고 합치는" 식이 아니라 처음부터 한 design system을 가지고 출발한다.
- **AI-native infinite canvas** — 초기 아이디어부터 작동하는 프로토타입까지 같은 캔버스 위에서 자라게 한다.
- **Voice Canvas** — 캔버스에 직접 말로 지시한다. AI 에이전트가 듣고 명확화 질문을 던지고 실시간 비평·라이브 업데이트를 한다.
- **모델 선택** — Gemini 2.5 Pro(production-quality)와 Flash(rapid iteration) 중 선택. 속도/품질 트레이드오프를 사용자가 통제.

DESIGN.md는 이 도구 안에서 "디자인 시스템을 외부로 내보내는 표준 출력 포맷"이다. Stitch 캔버스에서 작업한 결과를 DESIGN.md로 export하면 다른 코딩 에이전트(Claude Code, Cursor 등)가 그대로 읽고 코드를 생성한다.

---

## Claude Design — codebase를 읽고 시각을 만든다

Anthropic Labs가 [2026년 4월 17일 출시한 research preview](https://www.anthropic.com/news/claude-design-anthropic-labs)다. Claude Pro / Max / Team / Enterprise 구독자가 사용할 수 있다. 가장 강력한 vision model인 Opus 4.7이 엔진이다.

특징을 한 줄로 요약하면 **"코드와 디자인의 양쪽을 다 인지하는 도구"**다.

- **온보딩에서 codebase + 디자인 파일을 읽어** 사용자 팀의 design system을 자동 구성한다. 사용자가 별도로 토큰·룰을 적어 줄 필요가 없다.
- 출력 형태가 다양하다 — UI mockup뿐 아니라 슬라이드 덱, 원페이저, 마케팅 비주얼까지.
- **inline 코멘트로 수정** — 특정 요소에 직접 코멘트를 달거나, 텍스트를 인라인 편집하거나, adjustment knobs로 spacing·color·layout을 라이브 조정한다. 그 변경을 "전체 디자인에 적용해 줘"로 일괄 반영.
- export — Canva, PDF, PPTX, 단독 HTML 파일. 기업 내부 URL로 공유.

PM이 기능 흐름을 스케치해 Claude Code에 넘기거나, 창업자가 거친 outline으로 브랜드 일관 덱을 분 단위로 만들거나, 마케터가 랜딩 페이지·SNS 자산·캠페인 비주얼을 한 자리에서 만드는 시나리오가 공식 사례로 나와 있다.

---

## 셋의 비교축

같은 문제를 다른 각도로 풀고 있다.

| | DESIGN.md (Stitch 본가) | awesome-design-md (컬렉션) | Claude Design (Anthropic) |
|---|---|---|---|
| **형태** | 텍스트 스펙 포맷 | 미리 작성된 스펙 71개 | 비주얼 디자인 도구 |
| **주된 입력** | 사람이 작성 (또는 Stitch export) | 컬렉션에서 복사 | 자연어 + codebase |
| **주된 출력** | UI mockup(Stitch) + 스펙 자체 | 스펙 + 그 스펙으로 만든 UI | UI mockup + design system |
| **강점** | 표준, framework-agnostic, 다른 도구에 휴대 | 빠른 출발점 | codebase 인지, 미세 조정 |
| **약점** | 작성·유지 비용 | 브랜드 종속 | DESIGN.md 외부 호환성 약함 |
| **누가 쓰면 좋은가** | 자기 브랜드를 코드 + 마크다운으로 통일하고 싶은 팀 | 빠르게 시제품을 만드는 사람 | 이미 codebase가 있고 그 위에서 일관 시각을 빠르게 뽑고 싶은 사람 |

세 길이 모두 살아있다. 표준이 어디로 수렴할지는 도구 사용자가 어느 흐름을 더 많이 채택하는지가 결정할 것이다.

---

## fos-blog에 Claude Design을 6주간 도입한 회고

이 셋 중 내가 실제로 도입한 건 Claude Design이다. fos-blog(Next.js 16 + Tailwind v4)의 모던 dev-tool 톤 리디자인 작업에 6주간 적용했고, 그 흔적은 ADR-017, plan009부터 plan023까지의 phase 파일들, 자체 web-design-guidelines 스킬에 남아 있다. 흥미로운 건 **DESIGN.md 표준은 채택하지 않았는데도 Claude Design의 도입 이득은 작지 않았다**는 점이다.

도입 흐름은 시간순으로 이렇다.

1. **2026-04-25 design-inspiration.md 작성** — Vercel(베이스 톤) + Stripe(그라디언트 액센트) + Linear(미세 디테일)을 영감 보드로 잡았다. 각 브랜드의 컬러·타이포·레이아웃·개성을 표로 정리하고 "fos-blog에서 무엇을 차용할지"를 한 줄씩 박았다.
2. **ADR-017 디자인 시스템 결정** — 영감 보드를 토대로 "다크 기본 + Geist + Pretendard + oklch 토큰 + shadcn/ui foundation"을 ADR로 결정했다.
3. **plan009 design-tokens-foundation** — Claude Design에서 mockup으로 받은 디자인 토큰을 fos-blog의 `globals.css`에 1차 적용했다. dark default 전환, body font-family 단순화, 카테고리 9개 클래스를 oklch + color-mix 패턴으로 교체, shadcn init.
4. **plan010~023 페이지별 redesign 8건** — card-list, article-page, code-block, header-hero, categories, posts-index, comments, about. 각 plan마다 Claude Design에서 mockup을 받아 task 디렉터리에 `design-*.{css,jsx}` 형태로 저장하고, 그 spec을 phase 파일에 박아 executor가 구현하게 했다.
5. **web-design-guidelines 스킬 신설** — Vercel Web Interface Guidelines를 fetch해 UI 코드를 자체 점검하는 스킬을 박았다. Claude Design이 만든 mockup이 실제 코드로 옮겨질 때 접근성·UX 룰을 자동으로 점검한다.

핵심 워크플로우는 **"Claude Design mockup → tasks/planXXX/design-*.{css,jsx} → plan phase로 핸드오프 → executor가 토큰 매핑 룰 따라 구현"**이다. mockup의 짧은 토큰명(`var(--bg-base)`)을 plan009의 토큰명(`var(--color-bg-base)`)으로 일괄 치환하는 매핑 표를 phase 파일에 박아 두면, executor가 수십 줄짜리 mockup CSS를 fos-blog 토큰 컨벤션에 맞춰 자동으로 정착시켰다.

### DESIGN.md를 안 쓴 이유

검토는 했다. 다만 도입하지 않은 결론에 도달한 이유가 명확했다 — **Claude Design이 codebase를 읽고 알아서 design system을 구성하기 때문**이다. 별도 DESIGN.md를 두면 토큰 정의가 두 곳(`globals.css`와 `DESIGN.md`)에 살게 되고, 두 진실 소스가 동기화되지 않을 위험이 생긴다. fos-blog의 토큰은 `globals.css`의 `@theme` 블록 한 곳에 있고, rationale은 ADR-017과 design-inspiration.md에 분산되어 있다. Claude Design은 이 셋을 모두 읽는다.

DESIGN.md의 강점인 "다른 도구에 휴대 가능"은 fos-blog 컨텍스트에서 큰 이득이 아니었다. fos-blog는 Claude Code 한 도구로 일관되게 작업하므로, DESIGN.md를 별도로 만들어 다른 도구로 옮길 일이 거의 없다. 이득이 작은 추상화는 두지 않는다는 결정.

> **인사이트.** **DESIGN.md와 Claude Design의 codebase 인지는 같은 문제의 두 답이다.** 한쪽은 "디자인 시스템을 텍스트로 명시하자", 다른 쪽은 "codebase가 이미 충분히 디자인 시스템이다, 그걸 직접 읽자". 두 도구를 동시에 쓰면 진실 소스가 둘로 갈라지므로, 도입 시점에 한쪽을 골라야 한다. 코드 위주의 1인 프로젝트라면 후자가 자연스럽고, 디자이너·개발자가 분리된 팀이라면 전자가 자연스러울 것이다.

### 6주 후 정착한 것

Claude Design 도입 자체는 부분 성공이다. 정착한 것과 안 정착한 것이 갈렸다.

- **정착함**: mockup → task 디렉터리 → plan phase로 흐르는 핸드오프 패턴, oklch + color-mix 토큰 구조, web-design-guidelines 스킬을 통한 접근성 자동 점검, design-inspiration.md를 영감 보드로 유지
- **정착 안 함**: Claude Design 안에서 디자인을 끝내고 코드로 export하는 흐름. 실제로는 mockup만 받고 그 뒤는 plan/phase로 작업한다. Claude Design의 inline 코멘트·adjustment knobs 같은 미세 조정 기능은 거의 안 쓰게 됐다.

이건 도구 자체의 한계가 아니라 **혼자 작업하는 컨텍스트 + 코드 위주 워크플로우의 결과**다. 디자이너가 따로 있고 매번 mockup을 주고받는 팀이라면 Claude Design 안에서 더 오래 머무는 게 자연스러울 것이다.

---

## AGENTS.md와의 비교 — 에이전트 지침서의 두 축

[AGENTS.md 포맷 글](./agents-md-format.md)에서 정리한 대로, AGENTS.md는 **AI 코딩 에이전트의 동작 지침서**다. 같은 자리(프로젝트 root, 마크다운 한 파일, 자동 발견)에 DESIGN.md가 들어왔다.

| | AGENTS.md | DESIGN.md |
|---|---|---|
| **대상 에이전트** | 코딩 에이전트 (Claude Code, Cursor, Copilot 등) | 디자인 에이전트 (Stitch, Claude Design 등) |
| **내용** | 빌드·테스트 명령, 컨벤션, PR 룰, 디렉터리 가드 | 컬러·타이포·간격, 컴포넌트 상태, Do's & Don'ts |
| **자동 발견 위치** | 프로젝트 root | 프로젝트 root |
| **포맷** | Markdown | YAML front matter + Markdown |
| **표준화 시점** | 2025년 본격 확산 | 2026-03 오픈소스 스펙 |

같은 컨벤션이 두 영역에서 동시에 자리 잡고 있다. **AI 에이전트가 코드 영역과 디자인 영역으로 갈라지면서, 각각의 "지침서" 컨벤션이 나란히 등장하는 흐름**이다. 둘 다 LLM이 가장 잘 읽는 마크다운으로 수렴했고, 둘 다 프로젝트 root 자동 발견 패턴으로 통일됐다는 것 자체가 의미가 있다.

---

## 의의 — 디자인 시스템의 위치 이동

이전 워크플로우는 이렇게 굴러갔다.

```
디자이너 (Figma) → 핸드오프 (디자인 시스템 PDF/Figma 라이브러리)
  → 개발자 → 코드
```

지금 굳어지는 흐름은 다르다.

```
사용자 (자연어 + 영감 보드)
  → AI 디자인 도구 (Claude Design / Stitch)
    → mockup + DESIGN.md
      → AI 코딩 에이전트 (codebase 인지)
        → 코드
```

**디자인 시스템의 위치가 "Figma 파일"에서 "마크다운 / codebase"로 이동했다.** Figma가 사라지는 게 아니라, "디자인 시스템의 진실 소스"가 옮겨가는 것이다. AI 에이전트가 읽기 좋은 형식으로.

DESIGN.md는 그 진실 소스를 텍스트 표준으로 명시한다. Claude Design은 같은 진실 소스를 codebase에서 추출한다. 둘은 경쟁자가 아니라 **같은 방향으로 가는 두 갈래**다.

---

## 마무리

세 도구 모두 research preview 또는 초기 단계다. 6개월 뒤에는 이 글의 절반은 낡아 있을 것이다. 그래도 지금 시점에서 잡아둘 만한 큰 그림은 다음과 같다.

- **AI가 만드는 화면 일관성 문제**가 코드 생성 다음 병목이라는 인식이 자리 잡았다
- DESIGN.md 같은 **마크다운 표준**과 Claude Design 같은 **codebase 인지** 두 흐름이 공존한다
- AGENTS.md와 결이 같은 컨벤션이 디자인 영역에도 등장했다 — **프로젝트 root + 마크다운 + 자동 발견**
- 도입 시 어느 쪽을 진실 소스로 정할지 한 번에 결정해야 한다. 둘을 동시에 두면 동기화 비용이 든다

내 fos-blog 경험으로는 1인 코드 위주 프로젝트는 Claude Design + ADR + plan/phase 조합이 더 자연스러웠고, DESIGN.md는 보류했다. 다른 컨텍스트(디자이너가 따로 있는 팀, 여러 코딩 에이전트를 동시에 쓰는 환경)라면 결정이 달라질 것이다.

[Claude Code 사용기 2탄](./claude-code-usage-reflection-2.md)에서 정리했듯이 운용 시스템은 사고 한 번에 룰 한 줄씩 박혀 진화한다. 이 글의 비교 결과도 그 진화의 한 시점이다 — 6개월 뒤 다시 보면 어느 쪽이 표준으로 굳었는지 명확해질 것이다.

---

## 참고

- [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) — 71개 브랜드 DESIGN.md 컬렉션
- [Stitch — Design with AI](https://stitch.withgoogle.com/) — Google Labs 공식
- [Stitch's DESIGN.md format is now open-source](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/) — 2026-03-19 발표
- [Introducing Claude Design](https://www.anthropic.com/news/claude-design-anthropic-labs) — 2026-04-17 출시
- [getdesign.md](https://getdesign.md/), [designmd.app](https://designmd.app/en/) — 추가 DESIGN.md 컬렉션
- [AGENTS.md 포맷](./agents-md-format.md) — 같은 결의 코딩 에이전트 지침서 컨벤션
- [Claude Code 사용기 2탄](./claude-code-usage-reflection-2.md) — 운용 시스템 진화 회고
