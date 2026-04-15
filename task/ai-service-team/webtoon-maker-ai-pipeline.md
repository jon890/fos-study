# 10일간 AI 웹툰 제작 도구 MVP 만들기 — 하네스 파이프라인으로 혼자 풀스택 돌리기

**진행 기간**: 2026.04.06 ~ 2026.04.15 (약 10일)

사내 AI 웹툰 제작 TF에 차출됐다. 웹소설 원작을 받아 PD가 작가 없이 숏웹툰 컷 이미지까지 뽑아내는 MVP를 만들어 보자는 과제였다. 참여 인원은 나 한 명이었고, 프론트/백/DB/AI 파이프라인을 전부 내가 붙여야 하는 상황이었다. TF에서 요구한 범위가 좁지 않았다 — 소설 분석, 세계관, 캐릭터 시트, 각색, 글콘티, 컷 이미지 생성까지 6단계 풀 파이프라인을 붙여야 했다.

시작할 때 회의적이었다. 혼자 10일에 이만큼? 가능하긴 한가?

결론부터 말하면, 10일 동안 167개 plan을 처리했고 555개 커밋을 쌓았다. 내가 키보드로 555번 커밋 메시지를 친 게 아니다. Claude Code 기반 하네스 파이프라인이 있었기 때문에 가능한 볼륨이었다. 이 글은 그 10일에 어떤 일이 있었고, 무엇을 배웠는지에 대한 기록이다. 하네스 자체의 설계에 대해서는 [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md)에 따로 정리했으니 이 글에서는 제품을 만들면서 내린 기술적 결정과 삽질을 다룬다.

---

## 뭘 만들었나

한 줄로 요약하면, 웹소설 .txt 파일을 넣으면 60컷짜리 숏웹툰 이미지가 나오는 웹 도구다. 파이프라인은 6단계로 쪼개져 있다.

```
[1] 작품 기획     ← 소설 분석, 세계관 구축, 키워드 추출, 화풍 프롬프트 추천
[2] 캐릭터/배경   ← 캐릭터 시트, 의상 세트, 배경 레퍼런스 이미지
[3] 스토리 각색   ← 기획안, 상세 각색안, 회차 매핑
[4] 글콘티        ← 회차별 트리트먼트, 50~60컷 글콘티
[5] 이미지 컷     ← 8대 요소 프롬프트 + Gemini Image 생성
[6] 동영상/음악   ← MVP 범위 제외 (Phase 2 이후)
```

PD 한 명이 웹 UI에서 단계별로 결과를 확인하고, 필요하면 인라인으로 수정하고, 재생성한다. 각 단계는 확정 상태를 가지며, 앞 단계를 수정하면 이후 단계의 확정이 연쇄적으로 해제된다 (FR30). 브라우저를 닫아도 작업 상태는 그대로 보존된다.

AI 엔진은 Gemini 계열로 통일했다. 텍스트는 Gemini 3 LLM, 이미지는 Gemini Image (gemini-3-pro-image-preview)다. MVP 단계에서 멀티 벤더를 동시에 붙일 이유가 없었고, 하나의 SDK(`@google/genai`)로 텍스트/이미지/Structured Output을 모두 처리할 수 있다는 게 의사결정에 크게 작용했다.

---

## 10일 타임라인

```
2026-04-06  11 커밋  — 프로젝트 초기 세팅
2026-04-07  60 커밋  — 6단계 기본 뼈대
2026-04-08  49 커밋  — 소설 분석, 세계관
2026-04-09 120 커밋  — 캐릭터 시트, 각색, 트리트먼트
2026-04-10  77 커밋  — 글콘티, 프롬프트 조립
2026-04-11  18 커밋  — 버그 수정
2026-04-13  48 커밋  — Step5 이미지 생성 리팩터링
2026-04-14 108 커밋  — 8대 요소 프롬프트 고도화, 소품 시트
2026-04-15  64 커밋  — 비율 선택 UI, 캐릭터 시트 프롬프트 실험
```

9일간 총 555 커밋. 4/12는 쉬었다. 하루 최대 120 커밋이 나온 날이 있었다는 건, 내가 직접 타이핑해서 나올 수 있는 숫자가 아니라는 뜻이다.

이게 가능했던 구조를 짧게만 요약하면 이렇다. 논의는 내가 main 세션에서 Opus 모델로 한다. 논의가 끝나면 `tasks/planNNN-*/` 폴더에 phase 파일들을 만들어 저장한다. phase 파일은 자기완결적이라 이전 대화 없이 독립 실행이 가능하다. 그 파일을 Sonnet 모델 기반 executor 에이전트에게 넘기면, 알아서 코드를 수정하고 빌드 검증까지 마친다. critic 에이전트가 계획을 실제 코드와 대조해서 APPROVE/REVISE 판정을 내리고, docs-verifier가 코드 변경 후 문서 정합성을 확인한다. 상세한 구조는 [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md)에 적어뒀다.

이 구조 덕에 10일 동안 plan 단위로 167개의 작업 단위를 생성하고 실행할 수 있었다. 내가 한 일의 대부분은 논의/계획/검토였고, 실제 코드 타이핑은 에이전트가 했다.

---

## 기술 스택 선택

혼자 10일에 풀스택을 쳐야 하니 "풀스택 단일 코드베이스 + 타입 안전성 최대화"가 스택 선택 기준이었다.

| 레이어 | 선택 | 이유 |
|---|---|---|
| 프레임워크 | Next.js 16 (App Router) | Server Actions + API Route + SSE 한 프로젝트에 |
| 언어 | TypeScript (strict) | any 금지, Zod와 Prisma 타입 연동 |
| UI | Tailwind + Shadcn/ui | 탭/폼/다이얼로그 기본 제공, 컴포넌트 복붙 가능 |
| DB | PostgreSQL + Prisma 7 | 타입 안전 ORM, MVP 수준에 충분 |
| AI SDK | `@google/genai` | Gemini LLM + Image 통합 |
| 검증 | Zod 4 | 런타임 검증 + JSON Schema 자동 변환 |
| 스트리밍 | SSE (Server-Sent Events) | 장시간 생성 진행 표시 |
| DnD | @dnd-kit | 글콘티 컷 순서 변경 |
| 배포 | Docker Compose | 사내 인스턴스 |

최신 스택을 대담하게 골랐다. Next.js 16, React 19, Prisma 7, Zod 4 — 전부 당시 가장 최신이었다. 선택 기준은 단순했다. 혼자 쓰는 MVP 프로토타입이고, 깨지면 내가 고치면 된다. 멀티 팀 엔터프라이즈 프로젝트처럼 "안정 버전 N-1" 같은 보수적 기준을 들이댈 필요가 없었다. 그 대신 얻는 건 Server Actions, React 19 개선, Zod 4의 `z.toJSONSchema()` 같은 최신 기능들이다.

---

## Gemini 모델 전략 — 퀄리티 우선

처음엔 flash 모델을 기본으로 썼다. 비용이 pro의 1/4 수준이고 속도도 빨랐기 때문이다. 며칠 써 보니 방향을 바꿨다.

**PD가 결과물을 보고 "다시 해야겠다"라고 느끼면 오히려 총 비용이 증가한다.**

저가 모델로 생성 → 퀄리티 불만족 → 재생성이 반복되면, 싸게 보이는 모델이 결과적으로 더 비싸다. pro 모델은 입력/출력 모두 flash 대비 약 4배지만, 한 번에 만족하는 결과가 나올 확률이 훨씬 높다.

그래서 ADR-072에서 전략을 뒤집었다.

```
LLM:   pro → flash → lite   (429 시 fallback 순회)
Image: pro → flash
```

pro 모델을 기본으로 쓰고, 토큰 한도(TPM) 초과로 429가 나오면 하위 모델로 fallback한다. 속도/비용을 우선 희생하고 퀄리티를 지킨다. 대신 Gemini Context Caching (ADR-045)을 적극 활용해서 동일 소설 텍스트를 여러 번 재분석할 때 입력 토큰 비용을 크게 줄였다.

### 전역 Rate Limit Tracking

pro 우선 전략을 쓰면서 금방 문제가 생겼다. 요청 A가 `flash`를 호출해 429를 받았다고 하자. 이때 요청 B가 들어오면 또 `flash`부터 시도한다. 결과는 당연히 또 429. TPM은 1분 단위로 리셋되는데, 그동안 모든 요청이 `flash`에서 한 번 실패한 뒤 `lite`로 fallback하는 비효율이 쌓인다.

ADR-069에서 해결했다. 서버 메모리에 `Map<string, number>`를 두고, 429가 난 모델을 "retryAfter timestamp"와 함께 전역으로 마킹한다. 다른 요청은 fallback 순회할 때 이 Map을 확인해서 rate limited 상태인 모델을 그냥 skip한다.

```ts
// src/lib/ai/client/rate-limit-tracker.ts (개념 요약)
const rateLimited = new Map<string, number>();  // model → expireAt

export function markRateLimited(model: string, durationSec: number) {
  rateLimited.set(model, Date.now() + durationSec * 1000);
}

export function isModelAvailable(model: string): boolean {
  const expireAt = rateLimited.get(model);
  if (!expireAt) return true;
  if (Date.now() > expireAt) {
    rateLimited.delete(model);
    return true;
  }
  return false;
}
```

또 기존의 "429 → 같은 모델 30초 대기 → 재시도" 로직도 없앴다. TPM 한도 초과는 1분이 지나야 풀리는데, 30초 대기는 너무 짧아서 또 실패할 확률이 높았다. 429가 나면 바로 다음 fallback 모델로 넘어가는 게 훨씬 빠르고 안정적이다. 짧은 대기로 같은 모델을 두드리는 건 낭비였다.

디버깅용으로 `GET /api/model-status` 엔드포인트도 열었다. 어떤 모델이 지금 rate limited인지 바로 확인할 수 있어서, 개발 중에 "왜 fallback이 자꾸 이쪽으로만 가지?" 같은 의문을 빠르게 풀었다.

---

## 통합 분석 — 4회 → 1회 호출

Step1 소설 분석은 원래 5개 영역을 각각 별도 호출로 처리했다. 작품 프로필, 스토리 구조, 관계도, 세계관, 장소. 각 프롬프트를 분리하면 관심사가 명확해 보였지만, 곧 TPM 한도에 부딪혔다.

63만자짜리 소설이 들어왔을 때 수치는 이랬다.

```
63만자 × 토큰 환산 × 4회 호출 = 분당 약 160만 토큰
Gemini flash TPM 한도 = 200만
```

한도 안에 아슬아슬하게 들어오는 것처럼 보이지만, 캐시 미스나 재시도가 섞이면 바로 초과다. 실제로 429가 자주 터졌다.

ADR-059에서 5개 영역을 하나의 Structured Output으로 합쳤다.

```ts
const result = await genai.generateJSON({
  schema: novelAnalysisSchema,  // 5개 영역 전부 포함된 Zod 스키마
  contents: novelText,
  model: MODELS.llm.pro,
});
```

결과: 토큰 75% 절감, 속도 26.8s → 13.1s로 절반. 5개 영역의 논리적 경계가 필요하긴 했지만, 그건 Zod 스키마 안에서 필드로 나누는 것으로 충분했다. API 호출 경계와 논리적 경계가 꼭 일치할 필요가 없다는 걸 배웠다.

---

## 60컷 이미지 일괄 생성 — 부분 성공 보존

Step5에서 60컷 이미지를 일괄 생성해야 한다. 처음엔 서버에서 SSE로 60개를 순회하며 생성하고 진행률을 스트리밍하는 구조로 만들었다. 문제는 실패 복구였다.

rate limit이 타이트한 환경에서는 60개 중 20~30개가 실패하는 경우가 종종 생긴다. SSE 기반 일괄 생성에서 실패한 컷만 골라 재시도하려면 별도의 상태 관리가 필요했고, 부분 성공/실패를 추적하는 상태 기계가 복잡해졌다.

ADR-073에서 구조를 바꿨다. **클라이언트에서 `Promise.allSettled`로 60개 병렬 fetch.**

```ts
// src/lib/ai/generators/image/cut-generation.ts (개념 요약)
export async function* generateCuts(
  cuts: Cut[],
  signal?: AbortSignal,
): AsyncIterable<CutGenerationProgress> {
  const promises = cuts.map((cut) =>
    fetch(`/api/generate/cut-image/${cut.id}`, {
      method: "POST",
      signal,
    }).then((r) => r.json())
  );

  // settled 순서대로 yield
  for await (const result of settleAsYielded(promises)) {
    yield result;
  }
}
```

- 60개 Promise가 각각 독립된 요청이다. 실패는 per-Promise로 추적된다
- 브라우저의 호스트당 6 동시 연결 제한이 자연스러운 throttling 역할을 한다. 서버를 배려해서 따로 rate limiting을 짤 필요가 없었다
- `AbortController` 하나로 전체 취소 가능
- 실패한 컷은 같은 엔드포인트를 다시 호출하면 끝. 재시도 경로가 따로 필요 없다

DB 쪽도 바꿨다. `CutPrompt`에 `lastGenerationStatus`, `lastGenerationError`, `lastGeneratedAt` 컬럼을 추가해서 각 컷의 마지막 생성 결과를 저장했다. 실패했을 때 reason/model/safetyRatings를 Json으로 저장해 두면, UI에서 "이 컷은 safety filter에 걸렸다" 같은 구체적 메시지를 보여줄 수 있다.

UI는 상단 진행 바에 `완료 N / 진행 M / 실패 K / 전체 60`을 표시했고, 실패한 카드에는 에러 메시지와 개별 "재시도" 버튼을 붙였다. PD는 실패한 컷만 골라 재시도하면 되는 자연스러운 흐름이 됐다.

다만 추상화 레이어(`generateCuts()`)는 유지했다. 나중에 서버 리소스 낭비가 측정되거나, 컷별 멀티스텝 체이닝이 필요해지거나, 백그라운드 생성이 필요해지면 SSE 기반 서버 배치로 갈아끼울 수 있다. 지금은 클라이언트 병렬이 가장 단순한 답이었다.

한 가지 배운 점: **"1개의 긴 생성"은 SSE, "N개의 독립 생성"은 Promise.allSettled가 맞다.** 글콘티 생성(`/api/generate/conti`)은 1개의 긴 LLM 호출이라 SSE를 유지했다. 성격이 다른 두 패턴을 한 구조로 묶지 않은 게 나중에 편했다.

---

## Zod 단일 소스로 전환

Gemini Structured Output을 쓰려면 `responseJsonSchema`가 필요하다. 처음엔 같은 데이터 구조에 대해 두 개의 스키마 정의를 유지했다.

```ts
// Gemini용 — Gemini 전용 Type.OBJECT 문법
const GEMINI_SCHEMA = {
  type: Type.OBJECT,
  properties: { ... }
};

// 검증용 — Zod
const zodSchema = z.object({ ... });
```

스키마를 바꿀 때마다 양쪽을 동시에 고쳐야 했다. 한쪽만 고치면 "API는 통과했는데 Zod parse에서 터지는" 버그가 났다. 같은 개념을 두 번 적는 건 언젠가 한쪽이 드리프트한다는 뜻이다.

ADR-109에서 Zod 단일 소스로 통일했다. Zod 4의 `z.toJSONSchema()`를 쓰면 Zod 스키마에서 JSON Schema가 자동 생성된다.

```ts
// src/lib/ai/client/generate-json.ts (개념 요약)
async generateJSON<T>({ schema, contents, model }: {
  schema: z.ZodType<T>;
  contents: string;
  model: LlmModel;
}): Promise<T> {
  const jsonSchema = z.toJSONSchema(schema);  // Zod → JSON Schema
  const response = await genai.models.generateContent({
    model,
    contents,
    config: {
      responseMimeType: "application/json",
      responseJsonSchema: jsonSchema,
    },
  });
  const parsed = schema.parse(JSON.parse(response.text));  // Zod 이중 검증
  return parsed;
}
```

스키마 하나만 고치면 Gemini 쪽도 동기화되고, 반환값은 Zod parse로 런타임 검증까지 된다. `any` 없이 타입이 끝까지 흐른다.

### Structured Output 자체의 효용

별개로, Gemini Structured Output 자체가 굉장히 유용했다. 옛날엔 LLM한테 "JSON으로 답해줘"라고 프롬프트에 적고 응답을 정규식으로 파싱했는데, 마크다운 백틱이 붙거나 trailing comma가 있거나 해서 자주 깨졌다. JSON 자동 복구 로직도 불안정했다.

Structured Output을 쓰면 Gemini가 스키마에 맞는 순수 JSON만 반환한다. `responseMimeType: "application/json"`을 같이 주면 마크다운 래핑도 없다. 파싱 실패 가능성이 사실상 사라졌다 (ADR-043).

---

## UX 쪽 삽질 — onBlur 저장 패턴과 IME

글콘티 화면은 PD가 60컷을 인라인으로 편집하는 거대한 폼이다. 초기 버전은 `onChange`로 서버 저장을 호출했다. 매 키 입력마다 서버 액션이 날아가는 구조. 성능도 성능이지만, 한글 IME에서 조합 중인 글자가 깨지는 치명적인 버그가 있었다.

예를 들어 "안녕"을 치려고 "ㅇ", "ㅏ", "ㄴ"을 순차 입력하는 중에 서버 응답이 돌아오면, Server Component가 리렌더되면서 조합 중이던 글자가 완성되지 않은 상태로 덮어써진다. 한국어 사용자에게 치명적이다.

표준 패턴으로 바꿨다 — 로컬 draft state + `onBlur` 저장.

```tsx
function InlineCutEditor({ cut, onSave }: Props) {
  const [draft, setDraft] = useState(cut.description);

  return (
    <textarea
      value={draft}
      onChange={(e) => setDraft(e.target.value)}  // 로컬 state만
      onBlur={() => {
        if (draft !== cut.description) onSave(draft);  // 서버 저장
      }}
    />
  );
}
```

포커스를 잃을 때만 서버에 저장한다. 입력 중에는 로컬 state로만 쌓이고, IME 조합이 깨질 여지가 없다. CLAUDE.md에 이 패턴을 코딩 규칙으로 박아두고, 새 편집 컴포넌트를 만들 때마다 이 규칙을 따르도록 했다.

### Dialog 리마운트 트릭

편집 Dialog가 열릴 때 초기값이 갱신되지 않는 문제도 있었다. React의 `useState` 초기값은 첫 렌더 시점에만 설정된다. Dialog를 다시 열어도 컴포넌트가 살아있으면 이전 상태가 남는다.

```tsx
// ADR-019 — key prop으로 강제 리마운트
<EditDialog key={cut.id} cut={cut} ... />
```

`key={cut.id}`를 주면 다른 컷을 선택할 때마다 컴포넌트가 언마운트/리마운트되어 초기값이 새로 설정된다. 공식 문서에도 있지만 실제로 부딪혀 보기 전까진 와닿지 않는 패턴이었다.

---

## 아키텍처 레이어 — Actions / Repository / AI

혼자 쓰는 코드라도 레이어를 안 나누면 금방 엉킨다. 특히 Next.js Server Actions는 편한 만큼 위험했다 — 하나의 함수 안에 유효성 검증, Prisma 쿼리, 캐시 무효화, AI 호출이 다 섞이기 쉽다.

ADR-068에서 경계를 그었다.

| 레이어 | 담당 | 금지 |
|---|---|---|
| `actions/` | `"use server"`, 유효성, repository 호출, `revalidatePath` | 직접 Prisma, AI 호출 |
| `lib/db/` (Repository) | Prisma 쿼리, 트랜잭션, 순수 데이터 반환 | `revalidatePath`, 비즈니스 로직 |
| `lib/ai/client/` | Gemini SDK 래퍼, 모델 상수 | DB 접근 |
| `lib/ai/generators/` | AI 호출 + 결과 파싱 | DB 접근, `revalidatePath` |
| `api/generate/` | SSE 스트리밍, AI 파이프라인 오케스트레이션 | 직접 DB 쓰기 |

규칙은 단순하다. **Server Action은 AI를 모르고, AI 모듈은 DB를 모른다.** 이미지 생성 같이 둘 다 필요한 흐름은 API Route에서 오케스트레이션한다. 이 경계 덕에 AI 쪽 리팩터링을 해도 DB 쪽을 건드릴 일이 없었고, 반대도 마찬가지였다.

또 한 가지 — **모델명 문자열 리터럴 금지.** `"gemini-3-flash-preview"` 같은 걸 직접 쓰면 오타가 나도 타입 체커가 못 잡는다. `MODELS.llm.pro` 같은 상수만 쓰도록 강제해서, 허용된 모델 외에는 컴파일 시간에 실패하도록 했다.

---

## Claude Code 스킬 — 반복되는 워크플로우의 코드화

10일 동안 내가 만든 스킬 몇 개가 실제로 시간을 크게 절약했다.

- **`/planning`** — 기능 구현 전 8단계 설계 워크플로우. 기술 가능성, 사용자 흐름, API 설계, 데이터 스키마까지 모두 논의하고 확정한 뒤에야 task를 만든다. 모호한 상태로 task를 만들면 executor가 실행 중에 임의 결정을 하거나 멈추는데, planning을 먼저 하면 이게 줄어든다.
- **`/plan-and-build`** — `run-phases.py` 하네스. `tasks/planNNN/index.json`을 읽고 pending phase부터 순차 실행. 실패하면 해당 phase부터 재시작. 세션이 끊겨도 git에 task 파일이 있으니 어디서든 이어받을 수 있다.
- **`/build-with-teams`** — `plan-and-build`에 critic + docs-verifier 게이트를 추가한 진화판. 계획 검증 → 실행 → 문서 정합성 검증. 잘못된 계획이 실행 중에 터지는 일이 줄었다.
- **`/integrate-ux`** — UX 디자이너가 Claude Code로 목업 PR을 올리면, 그걸 rebase하고 로컬 state 목업을 Server Action으로 바꾸고 공통 컴포넌트로 교체하는 워크플로우를 스킬화했다. 반복 지시를 하다가 패턴이 보여서 스킬 파일로 박았다.

처음에는 매번 지시했다. 작업이 반복되면서 패턴을 스킬 파일로 만들었고, 이제는 논의만 이어가면 되는 구조가 됐다. 반복되는 판단을 내가 매번 내리는 게 아니라, 스킬 파일이 대신한다. 이게 10일에 167개 plan을 돌린 핵심 생산성 장치다.

---

## docs-first 원칙

코드를 고치기 전에 ADR과 data-schema를 먼저 업데이트한다. task가 실패해도 결정은 docs에 보존된다. AI 에이전트는 새 세션을 시작할 때 `CLAUDE.md`, `docs/adr.md` 같은 문서를 컨텍스트로 읽는다. 이 문서가 현실을 반영해야 에이전트가 올바른 전제로 시작한다.

10일 동안 111개 ADR이 쌓였다 (ADR-001 ~ ADR-111). 하나하나가 "왜 이렇게 결정했는가"의 기록이다. 나중에 "왜 Pro 모델을 기본으로 썼더라?" 같은 질문이 생겼을 때, ADR-072를 열면 "PD 재생성 비용이 단건 호출 비용보다 크다"는 맥락이 그대로 있다. 내 기억에 의존하지 않아도 된다.

ADR이 비대해지는 것도 문제였다. 한 번은 1,581줄까지 커졌는데, docs-verifier가 "AI 에이전트 컨텍스트 효율 관점에서 너무 길다"고 지적해서 900줄 수준으로 축소했다. ADR 자체도 AI 에이전트를 위한 문서라는 관점을 잊으면 안 된다.

---

## 남은 것, 배운 것

### 남은 것

MVP 범위에서 빠진 것들이 Phase 2로 넘어갔다.

- 동영상/음악/음성 (단계 6) — 컷 기반 자동 영상 생성, AI 배경음악
- 버전 관리 — 단계별 생성 이력 보존, 롤백/비교
- API 비용 모니터링 — 실시간 토큰/API 사용량 추적
- 표지 생성, 외부 플랫폼 연동

동영상을 붙이면 이 도구가 진짜로 숏폼 채널에 배포 가능한 결과물을 뽑게 된다. 10일에 거기까지는 못 갔다.

### 배운 것

**하네스가 없으면 10일은 불가능했다.** 혼자서 프론트/백/DB/AI/UX를 10일에 커버하는 건 사람이 풀스택 타이핑을 하는 구조로는 안 된다. 생성을 에이전트가 하고, 평가를 critic이 하고, 문서 정합성을 docs-verifier가 한다. 내가 하는 일은 "무엇을 할지 결정"에 집중된다. 이 분업이 안 되면 같은 시간에 아마 1/5 수준의 결과만 나왔을 것이다.

**최신 스택을 두려워하지 않기.** Next.js 16, React 19, Prisma 7, Zod 4, Gemini 3 — 10일짜리 MVP라 안 깨지면 다행이고 깨지면 내가 고친다. 보수적으로 N-1 버전을 고르는 건 팀이 공유하는 장기 프로젝트의 논리고, 개인 프로토타입에는 맞지 않는다.

**AI 프롬프트에도 아키텍처가 있다.** 모델 선택 전략(pro 우선 + fallback), rate limit 추적, 통합 호출로 토큰 절감, Structured Output, Context Caching, 8대 요소 프롬프트 조립 순서 — 전부 코드 아키텍처 결정과 동등한 수준의 의사결정이다. AI 파이프라인은 단순히 "프롬프트 잘 짜기"가 아니다.

**문서 부패가 컨텍스트 부패다.** AI 에이전트 시대에는 문서가 사람뿐 아니라 에이전트의 컨텍스트가 된다. ADR 하나를 잘못 유지하면 다음 세션의 에이전트가 잘못된 전제로 시작한다. docs-first 원칙이 단순한 매너가 아니라 생산성 도구라는 걸 체감했다.

**"팔 쓰는 건 모델이고, 머리 쓰는 건 사람이다"는 전제가 점점 옛말이 된다.** Sonnet은 단순 실행이라지만 실제로는 상당히 복잡한 판단도 한다. critic이 내 계획의 구멍을 잡아내는 건 단순 실행을 넘는 일이다. 다만 구조 설계, 트레이드오프 판단, 제품 방향은 여전히 사람이 해야 한다. 이 경계는 점점 흐려지겠지만, 경계가 흐려지는 만큼 사람의 역할은 "더 상위 수준의 판단"으로 이동한다.

---

## 참고

- [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md) — 이 프로젝트에서 쓴 4인 에이전트 팀 파이프라인의 구조와 진화 과정
- [하네스 엔지니어링 이론편](../../AI/harness-engineering.md) — 하네스 개념, Anthropic/Fowler 사례, 설계 원칙
