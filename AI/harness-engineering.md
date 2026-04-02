# 하네스 엔지니어링 — 오래 실행되는 AI 에이전트를 위한 설계

AI 에이전트가 복잡한 작업을 수행하게 하면서 한 가지 사실을 깨달았다. 프롬프트를 잘 짜는 것만으로는 한계가 있다. 에이전트가 몇 시간 동안 돌아가는 작업을 수행할 때 생기는 문제는 모델이 멍청해서가 아니라, 에이전트를 둘러싼 **구조**(harness)가 없기 때문이다.

2025~2026년을 기점으로 "하네스 엔지니어링(Harness Engineering)"이라는 개념이 AI 에이전트 개발에서 독립적인 분야로 자리를 잡고 있다. 이 글에서는 Anthropic 엔지니어링 블로그 글 두 편과 Martin Fowler의 시각을 중심으로 하네스가 무엇인지, 왜 필요한지, 실제로 어떻게 설계하는지 정리한다.

---

## 하네스(Harness)란 무엇인가

하네스는 AI 에이전트가 제대로 동작할 수 있도록 감싸는 **실행 구조** 다. 구체적으로는:

- **제어**(Control): 작업을 어떻게 분해하고 스케줄링할 것인가
- **계약**(Contracts): 어떤 산출물이 만들어져야 하며, 어떤 조건이 충족돼야 종료할 것인가
- **상태**(State): 여러 세션과 단계를 걸쳐 무엇을 유지할 것인가

프롬프트 엔지니어링이 "모델에게 무엇을 말할 것인가"에 관한 것이라면, 하네스 엔지니어링은 "모델이 어떤 환경에서 어떤 흐름으로 작동할 것인가"에 관한 것이다.

Martin Fowler는 이를 이렇게 정리한다. 하네스는 에이전트를 **제약하고 신뢰할 수 있게** 만드는 도구와 실천의 집합이다. 에이전트에게 무한한 자유를 주는 것이 아니라, 일관된 결과물을 내도록 안내하는 구조를 만드는 것이다.

---

## 장시간 실행 에이전트의 두 가지 실패 패턴

Anthropic의 엔지니어 Prithvi Rajasekaran이 장시간 에이전트 시스템을 만들면서 반복적으로 마주친 실패 패턴은 두 가지다.

### 1. 컨텍스트 저하 (Context Degradation)

컨텍스트 윈도우가 채워지면서 모델이 일관성을 잃는다. 더 심각한 것은 **"컨텍스트 불안(Context Anxiety)"** — 모델이 컨텍스트 한계에 가까워진다고 느끼면 작업을 제대로 완수하지 못했음에도 "완료됐습니다"라고 선언해버린다.

실제로 Claude Sonnet 4.5를 테스트했을 때 컨텍스트 압축(compaction)만으로는 충분하지 않았고, **컨텍스트 리셋** 이 하네스 설계의 핵심 요소가 됐다.

### 2. 자기 평가 편향 (Self-Evaluation Bias)

에이전트에게 자신이 생성한 결과물을 평가하게 하면 품질이 낮아도 높게 평가하는 경향이 강하다. "자신이 만든 작업을 평가하라고 하면 에이전트는 자신 있게 그 작업을 칭찬하는 경향이 있다."

이 두 문제를 해결하는 핵심 통찰은 단순하다. **생성과 평가를 분리하라.**

---

## Anthropic 사례: 하네스 설계 실전

### 단계 1 — 프론트엔드 디자인 하네스

Rajasekaran은 프론트엔드 디자인 품질을 높이기 위해 GAN(생성적 적대 신경망) 구조에서 아이디어를 가져왔다. 생성자(Generator)와 평가자(Evaluator)를 분리한 것이다.

평가자는 네 가지 기준으로 결과물을 채점한다:

| 기준 | 설명 |
|------|------|
| **디자인 품질** | 시각적 일관성, 정체성이 있는가 |
| **독창성** | AI 기본값이 아닌 커스텀한 결정이 있는가 |
| **완성도** | 기술 구현 수준이 충분한가 |
| **기능성** | 실제로 사용할 수 있는가 |

평가자는 Playwright MCP를 통해 실제 렌더링된 페이지를 직접 조작해본 뒤 점수를 매겼다. 생성자는 평가자의 피드백을 받아 반복적으로 개선했다.

핵심 발견: **독립된 평가자를 회의적으로 튜닝하는 게, 생성자가 스스로 비판적이 되도록 만드는 것보다 훨씬 쉽다.**

### 단계 2 — 풀스택 애플리케이션 하네스

더 복잡한 작업(풀스택 앱 개발)에는 3개 에이전트 구조가 등장한다.

```
[Planner]
 └── 간단한 브리프를 상세 스펙으로 확장
 └── AI 기능 기회 식별
       ↓
[Generator]
 └── React + FastAPI + SQLite로 기능 구현
 └── 기능을 점진적으로 추가
       ↓
[Evaluator]
 └── Playwright로 기능 테스트
 └── 기준에 따라 점수 및 피드백 제공
 └── 다시 Generator로 피드백 전달
```

에이전트 간 통신은 **구조화된 파일** 을 통해 이뤄진다. Planner가 "스프린트 계약(sprint contract)"을 파일로 남기면, Generator는 이를 읽고 구현 전에 성공 조건을 미리 파악한다.

#### 결과 비교

| 방식 | 소요 시간 | 비용 | 품질 |
|------|-----------|------|------|
| 단일 에이전트 | 20분 | $9 | 핵심 기능 동작 안 함 |
| 풀 하네스 | 6시간 | $200 | 물리 엔진, 반응형 UI, AI 기능 모두 동작 |

비용이 22배 더 들었지만, 단일 에이전트로는 불가능했던 결과물이 나왔다.

---

## 장기 실행을 위한 하네스 — Initializer-Executor 패턴

에이전트가 여러 세션에 걸쳐 작업할 때의 핵심 문제는 **세션 간 기억이 없다는 것** 이다. 새 세션이 시작될 때마다 이전에 뭘 했는지 모른다. Anthropic의 두 번째 글은 이 문제를 다룬다.

비유: "교대 근무하는 엔지니어들. 새 엔지니어가 올 때마다 이전 교대의 기억이 없다."

### Initializer Agent

첫 세션에서 딱 한 번 실행된다. 이후 모든 세션이 의존할 인프라를 만드는 것이 역할이다.

```
Initializer가 만드는 것:
├── feature_list.json       # 전체 기능 목록 (초기에는 모두 "failing")
├── claude-progress.txt     # 에이전트 행동 기록
├── init.sh                 # 개발 환경을 한 번에 실행하는 스크립트
└── 초기 git commit         # 생성된 모든 것을 기록
```

`feature_list.json`에는 200개 이상의 기능이 "failing" 상태로 표시된다. 에이전트에게 이 리스트 없이 작업하면 "완료됐다"고 선언하기 너무 쉽기 때문이다. 그리고 엄격한 규칙이 들어간다: "테스트를 삭제하거나 수정하는 것은 허용되지 않는다. 이는 기능 누락이나 버그로 이어질 수 있다."

### Coding Agent (Executor)

이후 모든 세션에서 실행된다. 각 세션 시작 시 정해진 절차를 따른다:

```
1. pwd 실행 (작업 디렉토리 확인)
2. git log + progress 파일 읽기 (현재 상태 파악)
3. feature_list.json에서 우선순위 높은 미완성 기능 선택
4. init.sh 실행 (환경 세팅)
5. 기본 e2e 테스트 실행 (앱이 깨진 상태에서 시작하지 않도록)
6. 기능 하나 구현 → 커밋 → progress 업데이트
```

앱이 깨진 상태에서 새 기능을 추가하기 시작하는 것을 방지하는 게 핵심이다.

### 실패 패턴별 해결책

| 실패 패턴 | Initializer 해결책 | Coding Agent 해결책 |
|------------|-------------------|---------------------|
| 너무 일찍 완료 선언 | feature_list.json 생성 | 리스트를 읽고 하나씩 처리 |
| 버그 있는 코드 방치 | git + progress 노트 | 검증 테스트로 시작 |
| 앱 실행 방법 모름 | init.sh 스크립트 작성 | 세션 시작 시 init.sh 실행 |
| 기능 완료 조기 선언 | feature list scaffold | e2e 테스트로 자기 검증 |

---

## Martin Fowler가 본 하네스 엔지니어링의 세 축

Fowler는 OpenAI 팀의 사례를 바탕으로 하네스를 세 가지 범주로 정리한다.

### 1. 컨텍스트 엔지니어링 (Context Engineering)

에이전트가 올바른 컨텍스트에 접근할 수 있도록 만드는 작업이다.

- 코드베이스에 **강화된 지식 베이스** 를 내장 (curated docs, API 스펙, 예시 패턴)
- 관찰 데이터(observability data), 네비게이션 도구를 동적으로 제공
- 기술 문서를 코드베이스의 일부로 관리

### 2. 아키텍처 제약 (Architectural Constraints)

에이전트가 의도된 설계 경계를 벗어나지 않도록 하는 구조적 가드레일이다.

- 결정론적 커스텀 린터로 코딩 표준 강제
- 설계 경계를 검증하는 구조 테스트
- 의도된 토폴로지에서 벗어나는 패턴 모니터링

### 3. 엔트로피 관리 (Entropy Management)

코드베이스가 시간이 지나면서 썩는 것을 방지한다.

- 주기적으로 비일관성을 찾아내는 "가비지 컬렉션 에이전트"
- 문서 위반 감지
- 아키텍처 드리프트에 지속적으로 저항

핵심 원칙: "에이전트가 어려움을 겪을 때, 그것을 신호로 받아들인다. 무엇이 없는지를 — 도구, 가드레일, 문서 — 파악하고 저장소에 피드백한다."

---

## 실제로 하네스를 설계하는 방법

이론은 충분하다. 실제로 하네스를 만들 때 어떻게 접근하면 좋을지 정리한다.

### Step 1: 작업을 세션 단위로 분해한다

장시간 작업은 단일 컨텍스트 안에서 완주하려 하지 말고, 명확한 체크포인트를 가진 **독립 세션** 으로 나눈다. 각 세션은:
- 어떤 상태로 시작하는지 (입력 계약)
- 무엇을 만들어야 끝나는지 (출력 계약)
- 실패 시 어디서 재개하는지 (복구 경로)

를 명확히 해야 한다.

### Step 2: 상태를 파일에 외부화한다

에이전트의 기억은 컨텍스트 윈도우뿐이다. 세션 간 유지할 것들은 반드시 파일 시스템(또는 DB)에 써둔다.

```
project/
├── .agent/
│   ├── progress.md          # 완료된 것, 현재 상태
│   ├── feature_list.json    # 남은 작업 목록
│   ├── decisions.md         # 중요한 아키텍처 결정 기록
│   └── init.sh              # 환경 재현 스크립트
```

에이전트가 새 세션을 시작할 때 가장 먼저 이 파일들을 읽게 만든다.

### Step 3: 생성자와 평가자를 분리한다

자기 평가 편향을 없애려면 평가를 독립 에이전트에게 맡겨야 한다. 평가자 에이전트는:
- 다른 시스템 프롬프트를 가진다 ("skeptical reviewer" 페르소나)
- 생성 과정을 보지 않는다 (결과물만 본다)
- 구체적인 채점 기준을 가진다

평가자가 테스트 도구(Playwright, 단위 테스트 실행기)를 직접 사용할 수 있으면 더 좋다.

### Step 4: 점진적으로 추가하고 항상 커밋한다

에이전트에게 기능을 한 번에 하나씩 구현하게 하고, 각 기능 완료 후 반드시 커밋하게 한다. 이유:
- 잘못됐을 때 롤백 지점이 생긴다
- git log가 progress 기록의 역할을 한다
- 에이전트가 "현재 상태"를 git에서 파악할 수 있다

### Step 5: 에이전트가 막히는 곳에서 하네스를 개선한다

하네스는 한 번 만들고 끝이 아니다. 에이전트가 같은 지점에서 반복적으로 실패한다면 그것은 **하네스에 무언가가 빠졌다는 신호** 다. 도구인지, 컨텍스트 정보인지, 가드레일인지 파악해서 하네스에 추가한다.

---

## 실제 사례 — 개인 블로그 프로젝트에서 본 하네스

이론을 쌓고 나면 자연스럽게 이런 질문이 생긴다. "내가 만든 것에는 하네스가 얼마나 있는가?"

개인 프로젝트 하나를 분석해봤다. GitHub에서 마크다운을 가져와 MySQL에 캐싱하고 렌더링하는 Next.js 블로그다. AI 에이전트가 직접 코딩에 참여했고, 그 결과물을 하네스 엔지니어링 관점에서 평가했다.

**종합 점수: 72 / 100**

### 잘 된 것들

**1. 계층형 AGENTS.md — 컨텍스트 엔지니어링의 정석**

프로젝트 루트부터 모든 서브 디렉터리에 `AGENTS.md`가 있다.

```
fos-blog/
├── CLAUDE.md           ← 전체 프로젝트 맥락 (기술 스택, 환경변수, 컨벤션)
├── AGENTS.md           ← 데이터 흐름, 디렉터리 안내
└── src/
    ├── AGENTS.md       ← 레이어 아키텍처 상세
    ├── services/
    │   └── AGENTS.md   ← 서비스 레이어 규칙
    └── infra/
        ├── db/
        │   └── AGENTS.md   ← DB 스키마, 레포지터리 패턴
        └── github/
            └── AGENTS.md   ← GitHub API 클라이언트 설명
```

에이전트가 `src/services/`를 작업할 때 `src/services/AGENTS.md`가 정확히 그 레이어에 필요한 맥락을 제공한다. 전체 프로젝트를 다 읽지 않아도 된다.

CLAUDE.md의 마지막 섹션에는 우선순위까지 명시돼 있다:

```markdown
**Agents should prioritize:**
1. Schema integrity (Drizzle types)
2. Sync idempotency (no duplicate/lost data)
3. Markdown fidelity (GFM, mermaid, links)
4. Type safety across API boundaries
```

**2. 의존성 주입으로 구현된 교체 가능한 하네스**

`SyncService`는 모든 외부 의존성을 생성자로 받는다. GitHub API를 실제 구현체 대신 mock으로 교체할 수 있어 테스트가 쉽다.

```typescript
export class SyncService {
  constructor(
    private postSyncService: PostSyncService,
    private metadataSyncService: MetadataSyncService,
    private postRepo: PostRepository,
    private syncLogRepo: SyncLogRepository,
    private githubApi: GithubApi,  // ← 인터페이스 타입, mock 교체 가능
  ) {}
}
```

에이전트가 이 코드를 수정할 때 "새 의존성을 추가하려면 생성자에 주입하라"는 패턴이 강제된다. 하네스가 코드 구조를 통해 제약을 만드는 예시다.

**3. 상태 외부화와 멱등성**

sync가 실패하거나 재실행됐을 때 중복 처리를 막는 체크포인트가 DB에 있다.

```typescript
const headSha = await this.githubApi.getCurrentHeadSha();
const lastSyncedSha = (await this.syncLogRepo.getLatest())?.commitSha;

if (lastSyncedSha === headSha) {
  return { upToDate: true };  // 이미 최신 → 재처리 없음
}
```

SHA 비교로 멱등성을 보장하는 구조다. cron이 매 시간 실행돼도 변경 없으면 아무것도 하지 않는다.

**4. 폴백 전략**

증분 sync(빠름)가 실패하면 전체 sync(안전)로 자동 폴백한다. 하네스의 복구 경로가 코드에 내장돼 있다.

```typescript
const changedFiles = await this.githubApi.getChangedFilesSince(lastSyncedSha, headSha);
if (changedFiles === null) {
  // 증분 불가 → 전체 sync로 폴백
  ({ added, updated, deleted } = await this.performFullSync());
} else {
  ({ added, updated, deleted } = await this.performIncrementalSync(changedFiles));
}
```

**5. 파일 필터를 통한 범위 제어**

`shouldSyncFile()`이 동기화 범위를 명확히 정의한다. AGENTS.MD, CLAUDE.MD 같은 에이전트 컨텍스트 파일이 블로그 포스트로 발행되는 것을 명시적으로 막는다.

```typescript
export const EXCLUDED_FILENAMES = new Set([
  "AGENTS.MD", "CLAUDE.MD", "GEMINI.MD", "CURSOR.MD", ...
]);

export function shouldSyncFile(filename: string): boolean {
  if (!filename.endsWith(".md") && !filename.endsWith(".mdx")) return false;
  if (parts.some((p) => p.startsWith("."))) return false;
  if (EXCLUDED_FILENAMES.has(basename)) return false;
  return true;
}
```

---

### 부족한 것들

**1. 핵심 오케스트레이터에 테스트가 없다**

`MetadataSyncService.test.ts`와 `PostService.test.ts`는 잘 작성돼 있다. 하지만 "전체 sync vs 증분 sync 결정" 같은 가장 복잡한 로직이 담긴 `SyncService.ts`에는 테스트 파일 자체가 없다. 테스트가 계약(contract) 역할을 하려면 가장 중요한 흐름부터 커버해야 한다.

```
src/services/
├── SyncService.ts             ← 테스트 없음
├── PostSyncService.ts         ← parsePath만 테스트 (upsert 미검증)
├── PostService.test.ts        ← 잘 됨
└── MetadataSyncService.test.ts ← 잘 됨
```

**2. 평가자(Evaluator)가 없다**

sync가 완료되면 `{ added: 3, updated: 0, deleted: 0 }` 을 반환하고 끝난다. 3개가 실제로 올바른 내용으로 저장됐는지, 렌더링에 문제는 없는지 검증하는 단계가 없다. "생성자와 평가자를 분리하라"는 하네스의 핵심 원칙이 여기서는 적용되지 않았다.

**3. API 레이어가 서비스 조합 규칙을 알고 있다**

```typescript
// api/sync/route.ts
const syncResult = await syncGitHubToDatabase();
const retitleResult = await retitleExistingPosts();  // ← 왜 여기에?
```

"sync할 때 retitle도 해야 한다"는 비즈니스 규칙이 API 레이어에 노출돼 있다. 이 규칙은 `SyncService` 안에 있어야 한다. 다른 진입점에서 sync를 호출하면 retitle을 빼먹을 수 있다.

**4. GitHub API 재시도 없음**

`getDirectoryContents`는 전체 sync 시 수십 번 호출된다. 여기에 재시도 로직이 없으면 429 하나에 sync 전체가 실패한다.

---

### 평가 요약

| 항목 | 점수 |
|------|------|
| 컨텍스트 엔지니어링 (계층형 AGENTS.md) | 9/10 |
| 아키텍처 제약 (레이어 규칙, TypeScript strict) | 8/10 |
| 상태 외부화 (SyncLog, SHA 멱등성) | 8/10 |
| 폴백/복구 전략 | 7/10 |
| 테스트 커버리지 (계약으로서의 테스트) | 4/10 |
| 평가자 분리 | 3/10 |
| 엔트로피 관리 | 3/10 |
| **종합** | **72/100** |

컨텍스트 엔지니어링은 잘 됐다. 에이전트가 이 저장소에서 작업할 때 방향을 잃지 않는다. 반면 "생성 후 평가"하는 루프와 핵심 로직의 테스트 커버리지가 약하다. 하네스 점수를 올리려면 SyncService 테스트와 Evaluator 레이어가 먼저다.

---

## gstack — 역할 기반 하네스의 실용 구현

Y Combinator CEO Garry Tan이 자신의 실제 Claude Code 개발 환경을 오픈소스로 공개한 것이 **gstack**이다.

> "The model is commodity. The harness is moat."

모델 자체보다 모델을 감싸는 구조가 경쟁력이라는 하네스 엔지니어링의 핵심 명제를 그대로 실천한 프로젝트다.

### 아이디어: 만능 어시스턴트 대신 역할 조직

하나의 AI에게 모든 걸 맡기는 대신, 실제 엔지니어링 조직의 역할 구조를 하네스로 투영한다. Claude라는 동일한 모델이지만 각 커맨드마다 독립된 시스템 프롬프트를 가진 다른 "역할"로 동작한다.

```
/plan-ceo-review      ← CEO 페르소나로 전략 검토
/plan-eng-review      ← 엔지니어링 매니저로 기술 계획 검토
/review               ← 코드 리뷰어
/qa                   ← QA 리드
/ship                 ← 릴리스 매니저
```

개발 사이클 전체를 커버한다: Think → Plan → Build → Review → Test → Ship → Retro

### 하네스 원칙과의 대응

| gstack 커맨드 | 하네스 원칙 |
|--------------|------------|
| `/qa`, `/qa-only` | **생성자-평가자 분리** — 만든 사람과 검증하는 사람을 분리 |
| `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review` | **역할별 평가자** — 관점이 다른 독립 평가자 |
| `/learn` | **상태 외부화** — 프로젝트별 패턴을 세션 간 누적 |
| `/guard`, `/careful` | **아키텍처 제약** — 에이전트가 경계를 벗어나지 않도록 제어 |
| `/investigate` | **컨텍스트 엔지니어링** — 작업 전 충분한 맥락 수집 |
| `/retro` | **엔트로피 관리** — 반복 패턴 인식 및 개선 |

### 주목받는 이유

실제 검증된 워크플로우다. YC CEO가 자신의 일상 개발에 쓰는 설정을 그대로 공개했다. 한 CTO는 gstack의 코드 리뷰 기능이 팀이 발견하지 못한 XSS 취약점을 잡아냈다고 보고했다.

`/learn` 커맨드는 프로젝트별 패턴을 세션을 넘어 누적한다. 사용할수록 해당 코드베이스에 맞는 하네스로 진화한다. 하네스가 고정된 구조가 아니라 **적응하는 구조**가 될 수 있다는 걸 보여준다.

Google Gemini 환경으로 포팅한 파생 프로젝트까지 등장했다. 아이디어 자체가 모델에 종속되지 않는다는 뜻이다.

```bash
# 설치
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup
```

---

## 모델이 좋아질수록 하네스는 어떻게 되는가

흥미로운 관찰이 있다. Rajasekaran은 Claude Opus 4.6으로 테스트하면서 하네스 컴포넌트를 하나씩 제거해봤다.

강력한 모델에서는:
- 스프린트 분해(sprint decomposition)가 불필요해졌다
- 플래너의 역할이 줄었다

하지만 평가자는 여전히 필요했다. 특히 작업 복잡도가 높아질수록 평가자의 가치가 오히려 커졌다.

결론: **하네스의 각 컴포넌트는 모델이 스스로 할 수 없다는 가정을 인코딩한다. 그 가정이 여전히 유효한지 주기적으로 검증해야 한다.**

---

## 2025~2026의 흐름

LangChain은 모델 교체 없이 하네스 엔지니어링만으로 14퍼센트포인트 성능 향상을 이뤄냈다. Vercel은 도구 복잡도를 줄이는 하네스 개선으로 100% 정확도를 달성했다. 하네스 엔지니어링은 "프롬프트 엔지니어링"의 다음 단계로 자리잡고 있다.

프롬프트 엔지니어링 → 컨텍스트 엔지니어링 → 하네스 엔지니어링

에이전트를 만드는 것보다 에이전트를 둘러싼 **시스템** 을 설계하는 것이 점점 더 중요해지고 있다.

---

## 참고

- [Harness design for long-running application development (Anthropic Engineering)](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Effective harnesses for long-running agents (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Harness Engineering (Martin Fowler)](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html)
- [Harness engineering: leveraging Codex in an agent-first world (OpenAI)](https://openai.com/index/harness-engineering/)
- [2025 Was Agents. 2026 Is Agent Harnesses (Aakash Gupta / Medium)](https://aakashgupta.medium.com/2025-was-agents-2026-is-agent-harnesses-heres-why-that-changes-everything-073e9877655e)
- [Building AI Coding Agents for the Terminal (arXiv)](https://arxiv.org/html/2603.05344v1)
- [gstack — Garry Tan의 역할 기반 Claude Code 하네스 (GitHub)](https://github.com/garrytan/gstack)
