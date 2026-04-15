# 하네스 엔지니어링 실전 — 4인 에이전트 팀으로 코딩 파이프라인 구축하기

이론은 알겠다. 생성과 평가를 분리하라. 상태를 파일에 외부화하라. Initializer-Executor 패턴으로 세션 간 기억을 만들어라. (→ [하네스 엔지니어링 이론편](./harness-engineering.md))

그런데 막상 이걸 실제 코딩 워크플로우에 적용하려고 하면 손이 잘 안 간다. "어떤 에이전트를 몇 개 만들어야 하는가", "critic이 REVISE를 냈을 때 어떻게 처리하는가", "docs-verifier가 실제로 뭔가를 잡아낼 수 있는가" — 이런 구체적인 질문에 이론편은 답을 주지 않는다.

이 글은 그 구체적인 질문들에 대한 답이다. 웹툰 제작 도구 프로젝트에서 하네스가 어떻게 진화했는지, 4인 에이전트 팀 파이프라인을 실제로 구축하면서 무엇을 배웠는지를 정리했다.

---

## 하네스가 진화한 과정

처음부터 4인 팀 파이프라인이 있었던 건 아니다. 실패를 반복하면서 구조가 생겼다.

### 1단계: 단일 에이전트 시절

처음에는 Claude Code에게 "이거 구현해줘"라고 직접 시켰다. 작은 작업은 잘 됐다. 컴포넌트 하나 만들거나, 타입 수정하거나, 함수 몇 개 추가하는 정도. 그 정도 범위면 대화 한 번으로 끝났다.

작업이 커지면서 문제가 드러났다.

**작업 항목 누락.** 큰 작업에서 뒤쪽 항목이 빠졌다. plan119 phase-02에서 11개 항목 중 뒤 3개가 누락됐다. 에이전트가 앞쪽 항목을 처리하면서 컨텍스트를 채우다 보면, 뒤쪽을 실행할 때는 이미 무언가를 빠뜨릴 상태가 된다. 그 상태에서 "다 했어?"라고 물으면 "네, 완료됐습니다"라고 답한다.

**문서 부패.** 코드는 고쳤는데 docs를 안 고쳐서 다음 세션에서 AI가 잘못된 문서를 참고했다. 한 번이면 넘어가지만 세션이 쌓일수록 코드 현실과 문서 현실이 점점 벌어졌다. 나중엔 AI가 이미 제거된 필드를 기준으로 작업하는 상황이 생겼다.

**컨텍스트 망각.** 컨텍스트가 길어지면 앞에서 내린 결정을 잊어버렸다. "이건 이미 논의해서 결정한 거야"가 통하지 않았다.

교훈은 하나였다. **프롬프트를 잘 짜는 것만으로는 한계가 있다. 구조가 필요하다.**

### 2단계: /plan-and-build 도입 — 해결한 것과 못한 것

단일 에이전트의 문제 세 가지를 각각 구조로 해결했다.

**작업 항목 누락 → phase당 5개 이하 원칙.** plan119에서 11개 항목 중 3개를 누락한 경험이 직접적인 근거다. 이후로 작업을 작게 쪼개서 각 phase가 집중하는 범위를 제한했다. 한 phase에 11개를 넣지 않고, 5개짜리 phase 두 개로 나눴다. 숫자 규칙이 아니라 "AI가 하나의 단위 안에서 잊어버리지 않을 수준"으로 쪼갠다는 원칙이다.

**문서 부패 → docs-first 원칙.** docs 반영 → docs 커밋 → task 생성 → 실행 순서를 강제했다. 코드를 고치기 전에 ADR과 data-schema를 먼저 업데이트했다. task가 실패해도 결정은 docs에 보존됐다. AI 에이전트는 새 세션을 시작할 때 `CLAUDE.md`, `docs/adr.md` 같은 문서를 컨텍스트로 읽는다. 이 문서가 현실을 반영해야 에이전트가 올바른 전제로 시작한다.

**컨텍스트 망각 → 자기완결적 phase 파일 + run-phases.py 하네스.** 각 phase 파일은 이전 대화 없이 독립 실행이 가능하도록 작성했다. `run-phases.py` Python 스크립트가 `index.json`을 읽고 `pending` 상태인 phase부터 순차 실행한다. `claude --print` 명령으로 각 phase를 독립된 세션에서 실행하기 때문에 컨텍스트 오염이 없다. 실패하면 `--from-phase N` 옵션으로 해당 phase부터 재시작한다.

이 구조로 대부분의 문제가 해결됐다. 그런데 두 가지 문제가 남았다.

**남은 문제 1: 계획 자체의 품질을 아무도 검증하지 않음.** 잘못된 계획이 그대로 실행됐다. executor가 한참 돌다가 타입 에러로 실패하고 나서야 "계획이 틀렸었구나"를 알았다. 실패가 늦게 발견될수록 복구 비용이 컸다.

**남은 문제 2: 실행 후 문서 정합성을 아무도 체크하지 않음.** docs-first 원칙으로 실행 전 문서는 맞게 고쳤다. 하지만 실행 결과로 코드가 바뀌면 문서가 다시 어긋났다. 특히 코드 리팩토링으로 타입이나 함수 구조가 바뀌었을 때 문서에 반영되지 않는 경우가 잦았다.

### 3단계: /build-with-teams 도입 — 평가 게이트 추가

run-phases.py는 잘 동작했지만 **백그라운드에서 뭘 하는지 보이지 않았다.** 계획이 잘못됐으면 executor가 한참 실행하다 실패하고 나서야 알 수 있었다.

두 가지 결론이 나왔다.

**"실행 전에 계획을 검증하는 에이전트가 필요하다."** → critic 도입. critic은 team-lead가 만든 task 파일을 실제 코드베이스와 대조한다. 계획의 가정이 현재 코드 현실과 맞는지 확인한다. 맞으면 APPROVE, 틀리면 REVISE와 함께 구체적인 수정 사항을 명시한다.

**"실행 후 문서 정합성을 체크하는 에이전트가 필요하다."** → docs-verifier 도입. 각 phase 완료 후 코드 변경이 `adr.md`, `data-schema.md` 같은 기술 문서와 일치하는지 확인한다. PASS 또는 UPDATE_NEEDED 판정만 내리고, UPDATE_NEEDED면 어떤 문서의 어떤 내용을 바꿔야 하는지 구체적으로 적는다.

Claude Agent Teams가 이 구조를 가능하게 했다. SendMessage로 에이전트 간 통신하고, 각자 독립 컨텍스트를 유지한다. critic이 REVISE 판정을 내리면 team-lead에게 메시지를 보내고, team-lead는 계획을 수정해서 다시 critic에게 보낸다. 파이프라인 전체가 비동기 메시지 흐름으로 연결된다.

이것이 이론편에서 Anthropic이 말한 "생성자와 평가자를 분리하라"의 실전 적용이다. 구조가 생기기까지 실제로 실패를 거쳤고, 각 실패가 하네스의 한 요소가 됐다.

---

## 4인 팀 구조

파이프라인은 `/build-with-teams` 스킬로 구현했다. 팀 구성은 이렇다.

```
team-lead (opus)
  └── 사용자와 논의, 계획 수립, task 파일 생성, 최종 커밋

critic (opus)
  └── 계획을 실제 코드와 대조 평가 → APPROVE / REVISE 판정

executor (sonnet)
  └── phase별 코드 수정 실행 (커밋은 하지 않음)

docs-verifier (opus)
  └── 코드 변경이 기술 문서(ADR 등)와 일치하는지 검증
```

흐름은 단순하다.

```
team-lead → task 파일 생성 → critic 평가
                                   ↓
                         APPROVE → executor (phase 순서 실행)
                         REVISE  → team-lead 계획 수정 → critic 재평가
                                                               ↓
                                          executor 완료 → docs-verifier 검증
                                                               ↓
                                                   PASS → team-lead 최종 커밋
                                                   UPDATE_NEEDED → 문서 보강 후 완료
```

자신이 만든 결과물을 자신이 평가하지 않는다. team-lead가 짠 계획을 team-lead가 평가하지 않는다. executor가 고친 코드를 executor가 검증하지 않는다.

에이전트 간 통신은 SendMessage로 이뤄진다. critic이 판정을 내리면 team-lead에게 메시지를 보내고, team-lead는 그 내용을 바탕으로 executor에게 지시한다. 파이프라인 전체가 Claude Code의 Agent Teams 위에서 돌아간다. (→ [Claude Teams 기본 개념](./claude-teams.md))

커밋 권한은 team-lead만 갖는다. executor는 코드를 수정하지만 커밋은 하지 않는다. 모든 phase가 완료되고 docs-verifier까지 통과한 뒤, team-lead가 한 번에 커밋한다. 각 커밋은 완결된 작업 단위를 나타낸다.

---

## critic이 실제로 잡아낸 것들

처음에는 critic이 형식적인 승인 도장이 될 것 같다는 의심을 했다. 계획을 짠 것도 같은 Claude 모델인데 다른 인스턴스가 평가한다고 다를까 싶었다.

핵심은 모델이 다른 것이 아니라 **컨텍스트와 역할이 다른 것**이다. 계획을 만든 team-lead는 그 계획이 옳다는 방향으로 이미 사고가 구성돼 있다. critic은 그 계획을 처음 보고, 회의적으로 보도록 설정돼 있다. 같은 모델이어도 시작 지점이 다르면 다른 결론을 낸다.

plan155에서 그 의심이 사라졌다. critic이 계획의 전제 자체가 틀렸다는 걸 잡아냈다. 이미 완료된 작업을 다시 수행하려는 계획이었다. 현재 코드베이스 상태를 실제로 읽은 에이전트만 잡을 수 있는 오류였다.

plan158에서는 REVISE 판정이 나왔다. critic이 지적한 누락 항목 4가지:

1. `CutContext` 타입에 이미지 생성에 필요한 8대 요소 필드가 없음
2. `route.ts`에서 `promptFields` 데이터를 AI 파이프라인에 전달하지 않음
3. `FloatingContiRegenBar`의 `onBlurCut` 타입이 너무 좁게 정의돼 있어 충돌 가능
4. 캐릭터 시트 필터링 코드가 실제 함수 구조와 맞지 않음

4번이 특히 흥미로웠다. 계획 작성 시점과 실행 시점 사이에 코드가 변경돼 있었고, critic이 현재 코드를 읽고 "계획의 가정과 다르다"를 잡아낸 것이다. critic 없이 바로 executor에게 넘겼으면 중간에 타입 에러로 실패했을 것이다.

critic이 보내는 메시지는 이런 형태다.

```
판정: REVISE

누락 항목:
1. CutContext 타입에 promptFields 필드가 정의돼 있지 않음.
   계획은 이 필드가 존재한다고 가정하나 실제 파일에 없다.

2. route.ts에서 buildImagePrompt() 호출 시 cut 데이터만 넘기고 있음.
   promptFields를 포함해서 넘겨야 하는데 계획에 이 단계가 빠져 있다.

3. buildCharacterRef()의 실제 시그니처:
   (characters: Character[], promptFields: PromptFields, characterSheets?: CharacterSheetRef[])
   계획에서는 characterSheets만 사용하는 로직을 가정하고 있음. 불일치.

재수립 후 재평가 요청.
```

이 메시지를 받으면 team-lead는 task 파일을 수정하고 다시 critic에게 보낸다. 이번 세션에서는 두 번째 제출에서 바로 APPROVE가 났다.

---

## docs-verifier가 잡아낸 것들

docs-verifier는 처음에는 선택 사항처럼 보였다. 코드가 잘 돌아가면 됐지 문서까지 확인해야 하나 싶었다.

생각이 바뀐 건 이 프로젝트의 특성 때문이다. `CLAUDE.md`, `docs/adr.md`, `docs/data-schema.md` 같은 기술 문서가 있고, AI 에이전트는 새 세션을 시작할 때 이 문서들을 컨텍스트로 읽는다. 코드는 바꿨는데 문서를 안 바꾸면 다음 세션에서 에이전트가 잘못된 정보를 읽고 시작한다. 2단계에서 docs-first 원칙을 도입했지만, 코드 실행 후 문서가 다시 어긋나는 경우는 여전히 생겼다.

plan156에서 docs-verifier가 코드 외부에서 문제를 찾았다. 코드 변경 자체는 정상이었는데, `adr.md` 파일이 1,581줄로 과도하게 비대해진 것을 지적했다. AI 에이전트가 읽기에 너무 길어서 컨텍스트를 낭비한다는 지적이었다. 결과적으로 약 900줄로 축소됐다. ADR-097 번호 충돌도 함께 잡아냈다.

plan159에서는 UPDATE_NEEDED 판정이 나왔다. `artStyle` 관련 잔여 참조가 `data-schema.md`와 `prd.md` 두 곳에 남아 있었다. 코드에서는 이미 제거된 개념인데 문서에만 남아 있던 것이다.

docs-verifier의 시스템 프롬프트는 역할이 명확하다. "코드 변경이 기술 문서와 일치하는가"만 확인한다. 코드의 품질을 평가하거나 버그를 찾는 게 아니다. PASS 또는 UPDATE_NEEDED 판정만 내리고, UPDATE_NEEDED면 구체적으로 어떤 문서의 어떤 내용을 바꿔야 하는지 적어서 보낸다.

이게 이론편에서 Fowler가 말한 "엔트로피 관리(Entropy Management)"다. docs-verifier가 phase 완료마다 이 역할을 자동으로 수행한다.

---

## Task 파일 = 세션 간 기억

이론편에서 Initializer가 `feature_list.json`을 만들고, Executor가 새 세션마다 이 파일을 읽는다는 구조를 다뤘다. 이 프로젝트에서 같은 역할을 task 파일이 한다.

```
tasks/plan158-image-prompt-enhancement/
├── index.json          ← 전체 phase 목록, 상태(pending/done), 담당 모델
├── phase-01.md         ← phase 1 자기완결적 프롬프트
├── phase-02.md         ← phase 2 자기완결적 프롬프트
└── phase-03.md         ← phase 3 자기완결적 프롬프트
```

`index.json`은 이렇게 생겼다.

```json
{
  "name": "plan158-image-prompt-enhancement",
  "description": "이미지 생성 파이프라인 프롬프트 고도화",
  "status": "pending",
  "current_phase": 1,
  "total_phases": 3,
  "phases": [
    {
      "number": 1,
      "title": "8대 요소 가이드라인 공통 모듈 + conti-system 고도화",
      "status": "pending",
      "model": "sonnet"
    },
    {
      "number": 2,
      "title": "cut-regen 확장 — 텍스트 + 8대 요소 한번에 재생성",
      "status": "pending",
      "model": "sonnet"
    },
    {
      "number": 3,
      "title": "캐릭터 시트 필터링 + dead code 삭제 + 빌드 검증",
      "status": "pending",
      "model": "sonnet"
    }
  ]
}
```

executor는 새 세션을 시작할 때 `index.json`을 먼저 읽고 `pending` 상태인 phase를 찾는다. 어느 세션에서 시작해도 같은 지점에서 이어받는다.

각 phase 파일은 이전 대화 없이 독립 실행이 가능하도록 작성된다. 성공 조건도 명시적이다. grep 명령으로 검증 가능한 형태로 적는다.

```bash
# phase 파일의 성공 기준 예시
grep -n "characters\|facialExpression\|costume" src/lib/ai/prompts/cut-regen-system.ts
# 위 필드가 존재해야 함
```

그리고 이 모든 것이 git에 커밋된다. task 파일 생성 즉시 커밋하고, phase 완료마다 커밋한다. git이 progress 기록의 역할을 한다. 세션이 끊겨도 `git log`로 어디까지 됐는지 파악할 수 있다.

---

## 스킬 시스템 — 삽질의 코드화

이 프로젝트에서 만든 스킬들이 있다. 각 스킬이 어떤 문제를 해결하는지, 왜 만들었는지를 적는다.

### /planning — 모호함을 실행 전에 제거

가장 앞단에 있는 스킬이다. 기능 구현을 시작하기 전에 8단계 설계 워크플로우를 밟는다. 기술 가능성, 사용자 흐름, API 설계, 데이터 스키마를 모두 논의하고 확정한다.

핵심 원칙은 "조금이라도 모호하면 넘어가지 않는다"다. 전에는 모호한 상태에서 task 파일을 만들고 executor에게 넘겼다. 실행 중에 모호한 부분에 부딪히면 executor가 임의로 결정하거나 멈췄다. 이제는 계획이 확정된 후에야 task 파일을 만들기 때문에 executor가 모호한 지시를 받는 일이 없다.

### /plan-and-build — 장시간 실행의 구조화

run-phases.py 하네스가 핵심이다. `index.json`을 읽고 pending 상태인 phase부터 순차 실행한다. 실패하면 해당 phase부터 재시작한다. 세션이 끊겨도 task 파일이 git에 있으므로 어디서든 이어받을 수 있다.

이론편에서 다룬 Initializer-Executor 패턴의 실전 적용이다. task 파일이 `feature_list.json` 역할을 한다.

이 스킬만으로도 단일 에이전트 시절의 주요 문제 세 가지는 해결된다. 다만 평가 게이트가 없다는 한계가 있다. 잘못된 계획이 그대로 실행된다.

### /build-with-teams — 평가 게이트 포함

plan-and-build의 진화판이다. 같은 task 파일 구조를 쓰되, 실행을 4인 에이전트 팀이 담당한다.

plan-and-build에 없었던 것이 두 개 추가됐다. 실행 전 critic의 계획 검증, 실행 후 docs-verifier의 문서 정합성 검증. 이 두 게이트가 있으면 잘못된 계획이 실행 도중에 터지는 일이 줄어든다. 실패 지점이 앞으로 당겨진다.

### /integrate-ux — 반복 작업의 스킬화

UX 디자이너가 Claude Code로 PR을 올리는 상황이 반복됐다. 문제가 패턴처럼 반복됐다. 로컬 state 목업, 공통 컴포넌트 미사용, `window.prompt` 같은 금지 패턴.

처음엔 매번 "이 PR 분석해줘, rebase 해줘, 목업을 서버 액션으로 바꿔줘" 같은 지시를 반복했다. 작업이 반복되면서 패턴이 보였고, 스킬로 만들었다. 이제는 `/integrate-ux PR#25` 한 줄이면 된다.

스킬 파일에 "main에 바로 merge 금지, rebase 후 merge" 같은 규칙이 박혀 있어서 실수로 conflict를 만드는 일이 없어졌다. 실제로 conflict로 코드가 깨진 경험에서 나온 규칙이다.

**핵심 교훈은 이것이다.** 처음엔 계속 지시했다. 작업이 반복되면서 패턴을 스킬 파일로 만들었다. 이제는 논의만 이어가면 되는 구조가 됐다. 반복되는 판단을 내가 매번 내리는 게 아니라, 스킬 파일이 대신한다.

---

스킬 파일은 반복되는 워크플로우를 코드처럼 관리하는 방법이다. 프롬프트를 매번 타이핑하는 것이 아니라, 검증된 절차를 파일로 저장하고 재사용한다. 새로운 실패가 생기면 스킬 파일에 반영한다. 하네스가 진화하듯 스킬도 진화한다.

---

## 모델 라우팅과 비용

4인 팀에서 역할마다 다른 모델을 쓴다.

| 역할 | 모델 | 이유 |
|------|------|------|
| team-lead | opus | 계획 수립, 의사결정, 불확실한 판단 |
| critic | opus | 코드 대조 평가, 숨은 가정 발견 |
| executor | sonnet | 결정된 것을 수행하는 기계적 작업 |
| docs-verifier | opus | 코드↔문서 대조, 판단력 필요 |

opus는 sonnet의 약 5배 비용이다. 처음에는 task phase 실행에도 opus를 썼는데, sonnet으로 바꿔도 결과 품질이 거의 같았다. rename, 리팩토링, 다중 파일 수정 같은 기계적 작업은 opus가 필요 없다.

반면 critic과 docs-verifier에서 sonnet으로 바꾸면 차이가 난다. "이 계획의 가정이 실제 코드와 맞는가"를 판단하는 작업, "이 문서가 현재 코드 현실을 반영하는가"를 판단하는 작업은 더 세밀한 추론이 필요하다. plan158에서 "캐릭터 시트 필터링 함수 시그니처 불일치"를 잡아낸 것처럼.

판단 기준: **"무엇을 할지 결정하는 작업 = opus, 결정된 것을 수행하는 작업 = sonnet".**

이 구분을 명확히 해두면 비용을 예측할 수 있다. plan 하나에 3~4개 phase가 있다면, opus 사용은 team-lead 계획 수립, critic 평가 1~2회, docs-verifier 검증으로 한정된다. executor 실행이 가장 토큰을 많이 쓰는 구간인데 — 파일을 읽고, 수정하고, 검증하는 반복 작업 — 여기서 sonnet을 쓴다.

잘못된 APPROVE 판정 하나가 나중에 고치는 비용보다 비싸기 때문에 critic과 docs-verifier는 opus를 유지했다.

---

## 실전 수치

이 세션에서 처리한 작업 (plan156~159, 총 4개 plan):

- 처리한 phase: 총 8개
- 변경 파일: 약 30개
- 커밋: 8개
- critic REVISE 발생: 1회 (plan158) → 재수립 후 APPROVE
- docs-verifier UPDATE_NEEDED: 2회 → 즉시 반영

REVISE 1회, UPDATE_NEEDED 2회. 비율로 보면 낮다. 하지만 그 1회가 executor를 중간에 멈추게 할 타입 에러였고, 그 2회가 다음 세션 에이전트를 잘못된 정보로 시작하게 만들 문서 불일치였다. 잡지 못했을 때의 비용이 크다.

4개 plan 중 3개는 critic이 APPROVE를 바로 냈다. REVISE가 모든 plan에서 나오는 것이 아니라 실제로 문제가 있을 때만 나온다. 무조건 의심하는 게 아니라 실제 문제를 감지하는 것이다.

파이프라인이 없었을 때 비슷한 규모의 작업을 단일 세션으로 처리하면 중간에 멈추는 지점이 생겼다. 파이프라인이 생긴 뒤로는 REVISE나 UPDATE_NEEDED로 그 지점이 앞으로 당겨졌다. 실행 시작 전에, 또는 코드 커밋 전에 잡힌다.

---

## 직접 해보고 나서

이론편을 쓸 때 "생성자와 평가자를 분리하라"는 원칙이 얼마나 강력한지 머리로는 이해했다. 직접 구축하고 나서 느낀 건 다르다.

critic이 없을 때는 "계획이 잘못됐어도 executor가 실행하다가 나중에 실패한다". critic이 있으면 "실행 전에 계획의 구멍을 잡는다". 실패가 뒤로 갈수록 복구 비용이 커진다는 소프트웨어 공학의 기본 원칙과 같다. 코딩 절반 하다가 타입 에러로 멈추는 것보다, 코딩 시작 전에 계획을 고치는 게 훨씬 싸다.

docs-verifier는 예상보다 훨씬 유용했다. 코드 변경에만 집중하면 당장 돌아가는 것처럼 보이지만, 다음 세션 에이전트가 읽을 문서가 현실과 괴리되는 건 눈에 안 보인다. 이 눈에 안 보이는 문제를 매번 체크하는 것이 장기적으로 에이전트 세션의 품질을 유지하는 방법이다.

하네스가 잘 작동할수록 에이전트가 아니라 **구조**가 품질을 보장하게 된다. 특정 에이전트가 실수해도 critic이나 docs-verifier가 잡는다. 에이전트 개별의 능력에 의존하는 것이 아니라, 파이프라인 구조 자체가 품질의 하한선을 만든다. 모델이 아무리 좋아져도 자기 평가 편향은 사라지지 않는다. 구조로 해결해야 하는 문제다.

그리고 이 파이프라인은 처음부터 완성된 형태로 만들어지지 않았다. 처음에는 단일 에이전트였고, 누락 문제를 겪으면서 phase 분리가 생겼고, 계획 실패를 겪으면서 critic이 생겼고, 문서 부패를 겪으면서 docs-verifier가 생겼다. 이론편에서 Fowler가 말한 것과 정확히 같다. "에이전트가 막히는 곳에서 하네스를 개선한다." 하네스는 처음부터 설계하는 것이 아니라 반복적으로 진화하는 것이다.

스킬도 마찬가지다. `/integrate-ux`의 rebase 규칙, `/plan-and-build`의 5개 이하 원칙 — 모두 실제 실패에서 나온 것이다. 삽질한 경험이 구조가 되고, 구조가 스킬 파일이 되고, 스킬 파일이 다음 번 같은 실수를 막는다.

"The model is commodity. The harness is moat." — 이 말이 진짜로 이해된 건 몇 번의 실패를 구조로 바꾸고 나서였다.

---

## 참고

- [하네스 엔지니어링 이론편](./harness-engineering.md) — 하네스의 개념, Anthropic/Fowler 사례, 설계 원칙
- [Claude Teams 기본 개념](./claude-teams.md) — Agent Teams, SendMessage, 에이전트 타입
- [Harness design for long-running application development (Anthropic Engineering)](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Effective harnesses for long-running agents (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Harness Engineering (Martin Fowler)](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html)
- [Building AI Coding Agents for the Terminal (arXiv)](https://arxiv.org/html/2603.05344v1) — Initializer-Executor 패턴 상세
