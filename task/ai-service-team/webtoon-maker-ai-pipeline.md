---
tags: [tasks]
---

# AI 웹툰 제작 도구 MVP: 6단계 생성 파이프라인과 운영 안정화

**진행 기간**: 2026.04.06 ~ 2026.04.30 (전반 12일 MVP, 후반 12일 안정화·운영 단계)

웹소설 원작을 입력하면 운영자가 세계관과 캐릭터를 검토하고 웹툰 컷 이미지까지 생성할 수 있는 내부 MVP를 만들었다. 프론트엔드, 백엔드, 데이터베이스, AI 생성 파이프라인을 한 명이 맡았고, 첫 12일에는 동작하는 흐름을 만든 뒤 다음 12일에는 운영 안정성과 코드 경계를 보강했다.

짧은 기간에 여러 영역을 함께 다루기 위해 계획, 구현, 검토 단계를 파일로 남기는 하네스를 사용했다. 이 글은 작업량보다 제품에서 마주친 문제와 해결 방법에 초점을 맞춘다. 하네스 자체의 설계는 [하네스 엔지니어링](../../AI/harness-engineering-practice.md)에 따로 정리했다.

---

## 뭘 만들었나

웹소설 .txt 파일을 넣으면 60컷짜리 웹툰 이미지가 나오는 웹 도구다. 파이프라인은 6단계.

```
[1] 작품 기획     ← 소설 분석, 세계관, 키워드, 화풍 추천
[2] 캐릭터/배경   ← 캐릭터 시트, 의상 세트, 배경 레퍼런스
[3] 스토리 각색   ← 기획안, 상세 각색안, 회차 매핑
[4] 글콘티        ← 회차별 트리트먼트, 50~60컷 글콘티
[5] 이미지 컷     ← 8대 요소 프롬프트 + Gemini Image
[6] 말풍선 편집   ← 후반부에 음악·애니메이션 단계 대신 도입
```

운영자가 단계별로 결과를 확인하고, 인라인으로 수정하고, 재생성한다. 앞 단계를 수정하면 이후 단계의 확정이 연쇄적으로 해제된다. 브라우저를 닫아도 작업 상태는 보존된다.

AI 엔진은 Gemini 계열로 통일했다. 하나의 SDK(`@google/genai`)로 텍스트/이미지/Structured Output을 모두 처리할 수 있다는 게 의사결정에 크게 작용했다. MVP에서 멀티 벤더를 동시에 붙일 이유가 없었다.

---

## 작업 흐름

| 기간 | 목표 | 주요 작업 |
| --- | --- | --- |
| 04.06~04.18 | MVP 구현 | 6단계 기본 흐름, 소설 분석, 캐릭터·각색·글콘티, 이미지 생성 |
| 04.19~04.30 | 안정화 | 코드 경계 재정리, 관측성, 환각 검증, 재시도 정책, 통합 테스트 |

---

## 기술 스택

짧은 기간에 전체 흐름을 구현해야 했기 때문에 "단일 코드베이스, 타입 안전성"을 기준으로 삼았다. Next.js 16, React 19, Prisma 7, Zod 4, Tailwind v4, `@google/genai`를 사용했다.

운영 범위가 제한된 내부 MVP라 새 기능의 이점이 마이그레이션 위험보다 크다고 판단했다. Server Actions, Zod 4의 `z.toJSONSchema()`, Tailwind v4의 `@theme inline`과 `@source inline`을 활용해 별도 변환 코드를 줄였다.

---

## Gemini 모델 선택: 재생성까지 포함한 비용 비교

처음엔 flash를 기본으로 썼다. pro의 1/4 비용이고 빨랐다. 며칠 써 보니 방향을 바꿨다.

**운영자가 결과물을 보고 "다시 해야겠다"라고 느끼면 총 비용이 오히려 증가한다.**

저가 모델에서 품질 문제로 재생성이 반복되면 총호출 비용이 늘었다. 운영자 검토 결과 pro 모델의 재생성 빈도가 더 낮아 **pro를 기본으로 사용하고 429 응답이 오면 flash, lite 순서로 전환**했다.

이 전략을 쓰면서 두 가지를 추가로 했다.

- **전역 Rate Limit Tracking.** 어떤 모델이 429를 받으면 그 모델을 일정 시간 "skip 대상"으로 표시하는 메모리 Map을 뒀다. 다른 요청들이 같은 모델을 반복 호출하지 않도록 했다.
- **30초 재시도 로직 제거.** TPM은 1분 단위로 풀리는데 30초 대기는 너무 짧아 또 실패한다. 429가 나면 즉시 다음 fallback으로 넘기는 게 빠르고 안정적이었다.

모델 비용은 호출 단가만이 아니라 운영자가 다시 생성한 횟수까지 포함해 비교해야 했다. 재시도 상태는 요청마다 따로 관리하지 않고 프로세스 안에서 공유했다.

---

## 통합 분석: API 경계 ≠ 논리 경계

Step1 소설 분석은 원래 5개 영역(작품 프로필, 스토리 구조, 관계도, 세계관, 장소)을 별도 호출로 처리했다. 관심사가 분리되어 보였지만, 63만자 소설을 4회 호출하면 분당 약 160만 토큰: flash TPM 한도(200만)에 거의 닿는다. 캐시 미스나 재시도가 섞이면 바로 429다.

5개 영역을 하나의 Structured Output으로 합친 결과 토큰 사용량은 75% 줄었고 처리 시간은 26.8초에서 13.1초로 줄었다. 각 영역은 Zod 스키마의 필드로 구분해 논리적 경계를 유지했다. 이 사례에서는 API 호출 경계와 데이터의 논리적 경계를 분리한 것이 효과적이었다.

---

## 60컷 일괄 생성: SSE vs Promise.allSettled

처음엔 서버 SSE로 60개 순회 생성, 진행률 스트리밍이었다. 부분 실패가 문제였다. rate limit 환경에서 60개 중 20~30개가 실패하면, 실패한 컷만 골라 재시도하는 상태 기계가 너무 복잡해졌다.

클라이언트에서 `Promise.allSettled`로 컷별 요청을 관리하도록 구조를 바꿨다.

- 60개가 각각 독립된 요청이니 실패는 per-Promise로 추적된다
- `AbortController`로 전체 취소
- 실패한 컷은 같은 엔드포인트를 다시 호출하면 끝. 별도 재시도 경로 불필요

DB에는 `lastGenerationStatus`, `lastGenerationError`, `lastGeneratedAt`을 컷별로 저장해 UI에 "이 컷은 safety filter에 걸렸다" 같은 구체적 메시지를 띄울 수 있게 했다.

글콘티처럼 하나의 긴 생성은 SSE를 유지하고, 컷 이미지처럼 서로 독립된 생성은 `Promise.allSettled`로 분리했다. 생성 단위와 실패 처리 방식에 따라 통신 구조를 달리했다.

---

## 프롬프트 환각 차단: Grounding 재주입과 Project Cache

Step4 글콘티에서 가장 골치 아팠던 건 환각이었다. 트리트먼트에 없는 사건이 컷에 등장하거나, 등록된 캐릭터 외 이름이 새로 나오거나, 다음 회차에 들어갈 사건이 미리 들어오거나. 운영자가 일일이 지웠다.

처음엔 프롬프트에 `DO NOT invent` 같은 anti-pattern을 추가했다. 효과가 미미했다. 며칠 디버깅 끝에 진짜 원인을 찾았다.

**Continuation 호출이 tail 5컷만 보고 다음 컷을 만들고 있었다.**

50~60컷짜리 글콘티를 한 번의 LLM 호출로 만들기엔 너무 길어서, 1차 호출로 N컷을 받고 그 뒤를 continuation 호출로 이어 받는 구조였다. continuation에는 마지막 5컷만 컨텍스트로 넘겼다. 토큰 절약 목적이었다. 그 결과 LLM 입장에서는 "트리트먼트 grounding이 완전히 사라진 상태"에서 다음 컷을 만들고 있었다. 환각이 안 나오는 게 이상한 구조였다.

두 가지를 바로잡았다.

1. **Grounding 블록을 프롬프트 앞부분에 둔다.** "원작과 트리트먼트 범위에서만 가져올 것", "허용되는 창의는 카메라·구도·조명·페이싱 같은 연출뿐"이라는 제약을 명시했다.
2. **Continuation에도 Grounding/Treatment 블록을 매번 재주입한다.** 토큰을 더 쓰는 비용은 받아들였다. 환각으로 운영자가 컷을 일일이 수정하는 비용이 토큰값보다 훨씬 컸다.

반복 입력 비용은 **원작 소설을 Project 단위 Gemini Context Cache로 묶어 모든 단계에서 공유**하는 방식으로 줄였다. Analysis, Content-review, Treatment, Conti, Continuation 다섯 단계가 같은 `novelText`를 사용하므로, 캐시 유효 시간 안에는 원문 전체를 매번 다시 전송하지 않았다.

이 김에 conti 프롬프트 모듈을 3-layer로 쪼갰다 (`types/`, `templates/`, `blocks/`, `build-*.ts`). 1차/continuation 양쪽이 같은 `buildGroundingBlock()`을 호출하게 만들어, 두 호출의 grounding이 절대 어긋나지 않는다는 걸 코드 레벨에서 보장했다. 같은 구조를 character-sheet 프롬프트에도 적용했다.

환각을 줄이는 데는 금지 문구를 늘리는 것보다 각 호출에 필요한 근거 문맥을 빠뜨리지 않는 것이 중요했다. 허용할 연출 범위도 함께 적어 서사 제약과 창작 범위를 분리했다. 자동 판정은 허용 범위를 정확히 규칙화하기 어려워 오탐과 누락 위험이 있었으므로, MVP에서는 운영자 검토 항목으로 남겼다.

한 가지 미해결 과제: Pro가 429로 Flash/Lite로 fallback하면 grounding 준수력이 약해진다. 같은 프롬프트인데도 모델 capability 차이로 환각이 다시 등장한다. 서비스 연속성을 우선해 fallback은 유지했다.

---

## 캐릭터 외형 고정: 텍스트가 아니라 이미지 레퍼런스로

Step2 캐릭터 시트는 한 캐릭터의 여러 의상(외출복, 잠옷, 전투복...)을 시트로 관리한다. 옷만 갈아입혀도 얼굴/머리/체형이 드리프트하는 게 문제였다. 같은 캐릭터인데 시트마다 얼굴이 미묘하게 달라지면, 후속 컷 생성에서 매번 다른 사람으로 보였다.

처음엔 텍스트 anti-drift로 막아보려고 했다. `[FIXED ANCHOR: DO NOT change] 얼굴 생김새: 기본 시트와 동일` 같은 식. 효과 없었다. **Gemini Image는 이미지 모델인데 텍스트로 "이전에 만든 시트와 동일하게"를 강제하는 건 근본적으로 한계가 있다. 모델은 그 "이전 시트"를 본 적이 없다.**

텍스트 지시 대신 이미지 레퍼런스를 사용하는 방식으로 바꿨다.

- **스키마에서 "기본 시트" 개념을 만든다.** `CharacterSheet.isDefault`를 추가해 `(characterId, typeId)`마다 isDefault=true 시트가 정확히 1개 보장되게 했다. label="기본" 같은 관행은 다국어/이름 변경에 취약하고 자동화의 안정적 판별 기준이 못 된다.
- **비기본 시트 생성 시 기본 시트의 선택 이미지를 서버가 자동으로 레퍼런스 첫 번째에 prepend한다.** 운영자가 매번 기본 시트 이미지를 찾아 선택하지 않아도 된다.
- **mode 분기.** `default` 모드는 레퍼런스 미주입(외형 자유 변형), `outfit` 모드는 reference-bind 블록이 들어가 "첫 레퍼런스의 얼굴/머리/체형을 유지하고 의상만 변경"을 강제한다.
- **사전 체크.** 기본 시트 이미지가 없으면 서버가 400 `BASE_SHEET_REQUIRED`를 반환하고, 프론트는 모달로 기본 시트 카드로 스크롤 유도한다. 기본 시트 자동 생성은 안 한다: 외형 확인이 필요한 단계라 자동 생성하면 운영자를 혼란시킨다.

이미지 일관성은 텍스트만으로 지시하기보다 기준 이미지를 함께 제공할 때 더 안정적이었다.

---

## 타입 시스템: Zod 단일 소스, 레이어별 분리

### Zod 단일 소스

처음엔 Gemini Structured Output용 스키마와 Zod 검증 스키마를 따로 유지했다. 한쪽만 고치면 "API는 통과했는데 Zod parse에서 터지는" 버그가 났다.

Zod 4의 `z.toJSONSchema()`로 단일 소스로 합쳤다. Zod 스키마 → JSON Schema 자동 변환 → Gemini `responseJsonSchema`로 사용 → 응답은 다시 Zod parse로 런타임 검증. 같은 개념을 두 번 적지 않게 됐다.

Structured Output도 응답 파싱을 단순하게 만들었다. `responseMimeType: "application/json"`과 `responseJsonSchema`를 사용해 마크다운 코드 블록이나 잘못된 쉼표 때문에 JSON 파싱이 실패하는 경우를 줄였다.

### 레이어별 타입 소스

Zod 단일 소스를 일관되게 적용하려고 Repository까지 `Partial<XxxFields>`로 통일하려 했다. 며칠 써 보니 어색한 매핑이 자꾸 생겼다.

특히 두 지점에서 부딪혔다.
- **Json 컬럼의 명시적 NULL.** Prisma는 `null`(필드 업데이트 안 함)과 `Prisma.DbNull`(NULL로 비우기)을 구분한다. Zod 추론 타입의 `null | undefined`로는 표현이 안 돼서 Repository 안에서 매번 수동 변환을 했다.
- **관계 처리.** `connect`/`create`/`disconnect` 같은 Prisma 고유 semantic을 외부 도메인 타입으로 흉내 내는 건 추상화 누수였다.

레이어마다 목적에 맞는 타입 소스를 사용하도록 정리했다.

| 레이어 | 타입 소스 |
|---|---|
| Action 파라미터 | Zod `XxxFields`, TS 유틸(`Partial`/`Pick`): 외부 경계 도메인 검증, AI 응답/UI 폼과 타입 공유 |
| Repository 파라미터 | `Prisma.XxxCreateInput` / `Prisma.XxxUpdateInput`: DB 연산 semantic, 관계 처리 네이티브 |
| 경계 | `actions/mappers/xxx-mapper.ts`의 작은 변환 함수 |

Action에서는 Prisma가 안 보이고, Repository에서는 Zod가 안 보인다. 양 레이어가 깨끗해졌다.

Zod 스키마는 입력 경계의 구조도 강제했다. 예를 들어 `Character`에서 외형 필드를 빼고 `CharacterType`에만 두면 Action에서 잘못된 필드를 수정하려는 시도를 타입 검사로 막을 수 있다. 반면 ORM 연산은 Prisma 타입으로 표현하고, 두 타입 사이에는 작은 mapper를 뒀다.

---

## 한글 입력 문제: onBlur 저장과 IME

글콘티 화면은 운영자가 60컷을 인라인 편집하는 거대한 폼이다. 초기 버전은 `onChange`로 매 입력마다 서버 액션을 호출했는데, 한글 IME에서 조합 중인 글자가 깨졌다. "안녕"의 "ㅇ-ㅏ-ㄴ" 입력 도중 서버 응답이 돌아오면 Server Component 리렌더로 미완성 글자가 덮어써진다.

로컬 draft state와 `onBlur` 저장으로 바꿨다. 입력 중에는 로컬 state만 갱신하고, 포커스를 잃을 때 서버에 저장한다. 같은 문제가 반복되지 않도록 프로젝트 지침에 편집 컴포넌트 규칙으로 남겼다.

Dialog가 다시 열릴 때 초기값이 갱신되지 않는 문제는 `key={cut.id}`로 리마운트해 해결했다. React `useState`의 초기값은 첫 렌더에서만 설정되므로, 다른 컷을 열 때 컴포넌트 인스턴스도 바뀌어야 했다.

Server Action을 입력 이벤트에 직접 연결하면 IME 조합과 서버 응답 시점이 충돌할 수 있다. 입력 상태와 저장 시점을 분리해 이 경계를 명확히 했다.

---

## 아키텍처 레이어: Server Action은 AI를 모르고, AI는 DB를 모른다

다음과 같이 경계를 정했다.

| 레이어 | 담당 | 금지 |
|---|---|---|
| `actions/` | `"use server"`, 검증, repository 호출, `revalidatePath` | 직접 Prisma, AI 호출 |
| `lib/db/` | Prisma 쿼리, 트랜잭션 | 비즈니스 로직, `revalidatePath` |
| `lib/ai/client/` | Gemini SDK 래퍼, 모델 상수 | DB 접근 |
| `lib/ai/generators/` | AI 호출, 결과 파싱 | DB 접근, `revalidatePath` |
| `api/generate/` | SSE, AI 파이프라인 오케스트레이션 | 직접 DB 쓰기 |

이미지 생성처럼 AI+DB가 둘 다 필요한 흐름은 API Route가 오케스트레이션한다. 이 경계 덕에 AI 리팩터링이 DB를 건드릴 일이 없었고 반대도 마찬가지였다.

또 하나: **모델명 문자열 리터럴 금지.** `MODELS.llm.pro` 같은 상수만 허용. 오타가 컴파일 시간에 잡힌다.

---

## 디자인 시스템, Container/Presenter: 디자이너와 충돌 해소

후반부에 UX 디자이너 한 분이 합류했다. Claude Code를 같이 쓰면서 디자이너가 시각 변경을 PR로 올리는 구조였다. 며칠 같이 일하면서 두 가지 문제가 또렷이 보였다.

- **같은 파일을 동시에 건드린다.** `StepConti.tsx` 같은 503줄 god component에 상태 / 데이터 / 레이아웃 / 이벤트가 다 섞여 있었다. 디자이너가 카드 spacing을 바꾸려면 이 파일, 내가 컷 재정렬 로직을 바꾸려면 이 파일. PR 두 개가 동시에 올라오면 매번 충돌.
- **인라인 magic spacing이 너무 많았다.** `flex flex-col gap-4`가 28곳에 흩어져 있어, "카드 사이 간격을 줄여달라"는 요구에 일일이 grep해서 바꿨다.

두 단계로 나눠 해결했다.

**1. Semantic CSS 토큰과 공통 컴포넌트.** Tailwind v4 `@theme inline`으로 `--color-card-surface` 같은 semantic 토큰을 정의하면 `bg-card-surface` 클래스가 생성된다. 카드 색은 `globals.css` 한 곳에서 바꿀 수 있다. "동일 구조가 세 곳 이상 반복될 때"를 추출 기준으로 삼아 `components/common/`에 공통 컴포넌트를 모았다.

**2. Container/Presenter와 Layout Primitives.** 상태와 화면이 섞인 큰 컴포넌트를 두 층으로 나눴다.

```
src/components/step4-conti/
├── containers/   # 상태 + 데이터 + 이벤트 wiring (로직)
├── components/   # JSX + 시각 (UI)
├── hooks/        # 상태 추출
└── adapters/     # 도메인별 차이 흡수
```

원칙은 두 줄.

> 디자인 변경은 globals.css, 시각 컴포넌트만 건드려서 가능해야 한다.
> 로직 변경은 상태·데이터 파일만 건드려서 가능해야 한다.

이 원칙을 `docs/collaboration.md`의 **파일 소유권 표**로 구체화했다. 디자이너는 `globals.css`, `components/common/layout/`, `components/**/components/`를 맡고, 백엔드는 `actions/`, `lib/`, `components/**/hooks/`, `components/**/containers/`를 맡았다. 수정 영역을 나눈 뒤 같은 파일에서 발생하는 충돌이 줄었다.

레이아웃 magic number는 layout primitive 5종(`Stack`, `Cluster`, `Grid`, `Sidebar`, `Frame`)으로 흡수했다. every-layout.dev 스타일이다. `<Stack gap="4">` 같은 식으로 의미를 부여하니 인라인 `flex flex-col gap-4`가 사라졌다.

Tailwind v4에서 한 가지 함정은 있었다. primitive가 `GAP_MAP[gap]` 같은 객체 조회로 클래스를 조립하다 보니, JIT 정적 분석이 일부 클래스를 못 잡아 빌드 후 누락이 났다. v4 공식 API인 `@source inline("gap-2 gap-4 ...")` 한 줄로 해결. 또 한 가지 룰: **동적 클래스는 객체 매핑만 허용, 템플릿 리터럴 금지.** `` `gap-${x}` ``는 JIT이 잡을 길이 없다.

추상적인 관심사 분리 원칙보다 디렉터리별 수정 책임을 적은 표가 실제 협업에서 더 직접적인 기준이 됐다.

---

## 하네스 개선: 즉석 구현에서 명세 기반 작업으로

12일 동안 가장 많이 바뀐 게 하네스 자체였다. 기억나는 단계만 추리면 이렇다.

### 1단계: 한 세션에서 바로 구현

처음에는 한 세션에서 논의 → 즉석 구현 → 빌드 → 테스트를 모두 처리했다. 짧은 작업은 잘 됐지만 작업이 길어지면 컨텍스트 한도에 걸렸고, 잘못된 가정으로 시작한 구현을 되돌리거나 비슷한 결정을 반복하는 일이 생겼다.

가장 큰 문제는 **"무엇을 할지"를 충분히 잡지 못한 채 코드부터 쳤다는 것**이었다. 모호한 상태에서 시작하면 모델이 실행 중에 임의 결정을 한다. 그 결정이 틀리면 결과를 통째로 버린다.

### 2단계: `/planning`으로 명세 작성

설계 단계를 별도 워크플로우로 분리했다. 기능 구현 전에 8단계로 논의한다: 기술 가능성, 사용자 흐름, 데이터 모델, API 설계, 화면 동작, 엣지 케이스, 마이그레이션, 검증 방법. 모든 결정이 합의되어야 task 파일을 만든다.

설계 단계에서는 구현 전에 사용자 흐름, 데이터 모델, 경계 조건과 검증 방법을 정했다. 결정하지 못한 항목은 task 파일에 미결 상태로 명시해 실행 에이전트가 임의로 채우지 않도록 했다.

### 3단계: `/plan-and-build`로 단계 분할

planning 결과물은 `tasks/planNNN-*/index.json`, 여러 phase 파일로 떨어진다. phase 파일은 자기완결적이라 이전 대화 없이 독립 실행이 가능하다. `run-phases.py` 하네스가 `index.json`을 읽고 pending phase부터 순차 실행한다.

핵심 속성은 **재시작 가능성**이다. 세션이 끊겨도, executor가 중간에 실패해도, git에 task 파일이 있으니 어디서든 이어받을 수 있다. 1회성 휘발 세션이 아니라 task가 영속 상태가 됐다.

### 4단계: `/build-with-teams`로 계획과 문서 검토

`plan-and-build`에 두 검토 단계를 추가했다.

- **critic.** 계획을 실제 코드와 대조해 APPROVE/REVISE 판정을 내린다. "이 phase 파일이 현재 코드 상태에서 실행 가능한가? 가정이 맞는가?"를 체크. REVISE면 phase 파일을 고치고 다시 critic을 돌린다.
- **docs-verifier.** executor가 코드를 바꾼 뒤 ADR/data-schema 같은 문서가 정합성을 유지하는지 확인. 코드와 문서의 드리프트를 다음 세션이 시작되기 전에 잡는다.

계획 작성자와 검토자를 분리하자 실행 전에 잘못된 가정과 누락된 문서 변경을 찾을 수 있었다. planner, critic, executor, docs-verifier가 한 작업을 순서대로 처리했다.

### 5단계: `/integrate-ux`로 디자이너 목업 통합

후반에 UX 디자이너 한 분이 합류해 Claude Code로 컴포넌트 목업 PR을 올렸다. 화면 결과는 요구에 맞았지만 데이터 흐름과 컴포넌트 구조는 프로젝트 규칙과 달랐다.

- 로컬 state로 데이터를 시뮬레이션 (Server Action 대신 useState, 하드코딩)
- 공통 컴포넌트를 모르고 인라인으로 새로 그린 카드/버튼
- 기존 디자인 시스템 토큰 대신 인라인 색상값
- Container/Presenter 분리 무시

반복되는 변환 절차를 스킬 파일로 정리했다.

`/integrate-ux`는 이런 일을 한다.
- 디자이너 PR을 rebase하고 동작 확인
- 로컬 state 목업을 실제 Server Action 호출로 치환
- 인라인 카드/버튼을 `components/common/`의 공통 컴포넌트로 교체
- 인라인 색상을 semantic 토큰으로 매핑
- god component를 Container/Presenter로 분리
- 변환 후 빌드, 시각 회귀 체크

스킬은 디자이너 목업을 실제 데이터 흐름과 공통 컴포넌트에 맞추는 반복 작업을 줄였다. 디자이너는 화면 동작을 제안하고, 나는 프로젝트 구조에 맞게 통합하는 책임을 맡았다.

### 정리

즉석 구현에서 시작해 명세 작성, 재시작 가능한 단계 실행, 독립 검토, 목업 통합 순서로 하네스를 보완했다. 작업 상태와 결정 근거를 파일에 남겨 세션이 끊겨도 이어갈 수 있었고, 반복되는 통합 절차는 스킬로 재사용했다.

상세한 구조와 진화 과정은 [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md)에 정리해뒀다.

---

## 구현 전에 문서 갱신

코드를 고치기 전에 ADR과 data-schema를 먼저 업데이트한다. task가 실패해도 결정은 docs에 보존된다. AI 에이전트는 새 세션에서 `CLAUDE.md`, `docs/adr.md` 같은 문서를 컨텍스트로 읽는다. 이 문서가 현실을 반영해야 에이전트가 올바른 전제로 시작한다.

ADR이 한 파일에 계속 쌓이면서 1,581줄까지 늘어난 적이 있다. 필요한 결정을 찾기 어려워져 중복 설명과 종료된 내용을 정리했고 약 700줄로 줄였다. 에이전트가 이 문서를 입력으로 사용하므로 최신 결정과 현재 구조만 남기는 것이 중요했다.

---

## 후반 12일: MVP에서 운영 단계로

4월 19일부터 30일까지는 MVP의 기능 범위를 넓히기보다 운영에 필요한 경계를 보강했다. 빠르게 만든 코드의 책임을 다시 나누고, 관측성, 환각 검증, 실패 처리와 테스트를 추가했다.

### 6단계 재정의: 음악·애니메이션 폐기, 말풍선 편집 도입

원래 6단계는 "동영상/음악"이었고 MVP 범위 밖의 빈 화면만 있었다. 후반부에 이 단계를 제거하고 **말풍선 편집**으로 재정의했다. 음악과 애니메이션은 별도 작업으로 분리할 수 있지만, 컷 위에 대사를 배치하는 기능은 웹툰 결과물을 완성하는 데 필요했다.

이 결정 하나로 글 첫머리의 6단계 표가 바뀐다. 12일 시점에서 "Phase 2"로 미뤄뒀던 영역이 후반에 와서 "사실 우리에게 필요한 건 이게 아니었다"로 결론났다는 건, MVP 범위를 정할 때 **"무엇을 빼는지"가 "무엇을 하는지"만큼 중요하다**는 걸 다시 확인한 사건이었다. 빼두는 단계도 시간이 지나면 다시 평가받아야 한다.

### 도메인 레이어 분리: Controller / Application / Domain

초기에는 Action은 Zod, Repository는 Prisma를 쓰는 타입 경계만 나눴다. 코드가 늘자 SSE 도중 Action을 호출해 revalidate 시점이 불명확해지거나, repository에 비즈니스 정책이 들어가고, AI 레이어에서 Project row를 직접 쓰는 문제가 생겼다. 후반부에는 코드 위치도 도메인 단위로 정리했다.

**Controller / Application / Domain**의 책임을 다음과 같이 정했다.

- **Controller**(`actions/`·`app/api/`): Zod 파싱, application 호출, 응답 변환
- **Application**(`lib/application/`, 도메인별 `lib/domains/{domain}/application/`): 트랜잭션 경계, revalidate 부수효과, 다중 도메인 조합
- **Domain**(`lib/ai`·`lib/db`·`lib/schemas`, 도메인 vertical slice): 순수 기능

Application을 거치는 기준은 트랜잭션, revalidate 부수효과, 둘 이상의 도메인 조합, `projectId`가 필요한 경로로 정했다. 단일 repository 호출과 단일 revalidate는 Controller에서 직접 처리해 의미 없는 wrapper가 늘지 않도록 했다.

`lib/db/repository/`의 평면 구조를 `lib/db/domains/{domain}/`로 나눈 뒤 `lib/domains/{domain}/` 형태의 vertical slice를 일부 도메인에 적용했다. **`prisma` 직접 import는 repository 밖에서 금지**하고, 트랜잭션은 application의 `withTransaction`을 통해 받도록 ESLint 규칙을 추가했다.

전반 12일에 "빠르게 짠 코드"의 부채를 후반 12일에 "경계를 다시 그어 갚는" 흐름이 자연스럽게 따라왔다.

### 운영 관측성: pino, AsyncLocalStorage MDC

12일 동안에는 `console.log` / `console.error`만으로 충분했다. 혼자 돌리는 MVP고 로그를 직접 보면 됐다. 후반부에 운영 시점이 가까워지면서 한계가 보였다. 같은 시간에 두 프로젝트가 돌면 **어느 요청·어느 프로젝트에서 발생한 로그인지** 추적이 안 됐고, 에러 전후 문맥을 재구성하려면 로그 줄을 수동으로 묶어야 했다.

**pino와 `AsyncLocalStorage` 기반 MDC**를 도입했다. Java SLF4J의 MDC, Python의 `contextvars`와 같은 역할이다.

- 고정 bindings: `service`, `env`
- request-scoped: `requestId`, `projectId`, `projectName`
- `src/proxy.ts`(Next.js 16+의 옛 `middleware.ts`)에서 `X-Request-ID` 생성·반사
- 각 Server Action / Route Handler 진입점을 `withLogContext(fn)` wrapper로 감싸 als.run 시작
- application의 `loadProjectForContext(id)`가 project 로드 직후 `logContext.update({projectId, projectName})` 주입
- `console.*`는 서버 코드에서 ESLint `no-console` error로 금지. 클라이언트는 대상 외

신규 코드만 새 logger를 쓰면 디버깅할 때 두 형식의 로그를 함께 봐야 하므로, 서버 로그 호출부를 한 번에 교체했다.

`AsyncLocalStorage` 전파 경계는 한 가지 함정이 있다: Prisma EventEmitter나 AI retry/fallback 루프에서 컨텍스트가 끊길 수 있다. 이 경로들은 통합 테스트로 검증하고, 끊기면 request-scoped 필드 없이 고정 bindings만 남기는 식으로 받아들였다.

초기 MVP에서는 직접 로그를 확인했지만 동시 요청이 생기는 운영 단계에서는 요청별 문맥이 필요했다. 기능 구현에서 운영 준비로 넘어가는 시점에 관측성을 보강했다.

### 환각 차단 보강: sourceQuote와 트리트먼트 슬라이싱

초기에는 Grounding 블록을 프롬프트 앞부분과 continuation에 넣고 허용되는 창작 범위를 명시했다. 후반부에는 출력 근거 검증과 입력 범위 제한을 추가했다.

**sourceQuote 필수화와 부분 문자열 검증.** continuation 후반 컷에 원작 밖의 내용이 다시 등장했다. `buildContiPrompt`와 `buildContinuationPrompt`를 비교해보니, 첫 호출에는 PERSONA, CUT_WRITING_RULES, charactersBlock이 들어가지만 이어쓰기에는 grounding, treatment, tail과 짧은 rules만 있었다. 두 가지로 수정했다.

1. **continuation 프롬프트 파리티**: 1차와 동일한 구성 블록을 continuation에 재주입. 토큰 비용 감수
2. **`Cut.sourceQuote` 필수**: 각 컷이 원작 novelText에서 글자 그대로 추출한 인용을 함께 생성. generator가 `novelText.includes(sourceQuote)`로 substring 검증, 실패 시 logger().warn

**트리트먼트 소설 범위 슬라이싱.** sourceQuote를 추가한 뒤에도 `novelText.includes`는 **소설 전체를 검증**하므로 트리트먼트 범위 밖의 원작 인용까지 통과했다. 트리트먼트 schema의 `novelRange`가 자연어 라벨("1부 5장 도입~중반")이라 정확한 글자 범위를 알 수 없었다.

schema에 `Treatment.novelRangeStart: Int?`와 `novelRangeEnd: Int?`를 추가하고, application에서 `novelText.slice(start, end)`만 generator에 전달했다. 모델이 보는 입력을 해당 범위로 제한하면서 기존 sourceQuote 검사도 트리트먼트 범위 안의 인용만 통과시키게 됐다. 프롬프트의 원칙을 출력 검증과 입력 제한으로 옮긴 과정이었다.

### 이미지 파이프라인 보강: AbortSignal 전파와 레퍼런스 첨부

60컷 일괄 생성을 클라이언트 `Promise.allSettled`로 옮긴 뒤 컷, 배경, 소품 생성도 같은 패턴으로 맞추고 취소 신호를 SDK까지 전달했다.

**배치 생성 통합.** 컷은 `AsyncIterable`과 [AbortController](../../javascript/abort-controller.md)를 사용하고, 배경과 소품은 `CONCURRENCY=3` 슬라이스와 `batchAbortedRef`로 취소를 처리하고 있었다. 후자를 제거하고 같은 흐름으로 맞췄다. 클라이언트 `fetch(signal)`에서 route의 `request.signal`, application, generator, `@google/genai` SDK의 `config.abortSignal`까지 신호를 전달했다.

`@google/genai`의 `abortSignal`은 클라이언트 요청만 중단하므로 Google 서버에서 이미 시작한 작업 비용은 발생할 수 있다. 그래도 대기 중인 요청의 시작을 막고 클라이언트의 네트워크와 메모리를 회수할 수 있어 신호를 끝까지 전달했다.

**Step5 컷 레퍼런스 첨부.** FloatingRegenBar와 즉시 재생성은 텍스트 지시만 사용했다. 포즈를 조금 바꾸거나 색을 유지하려는 경우에는 현재 컷을 레퍼런스로 다시 넣는 편이 의도 전달이 쉬웠다. 한 장만 세션 상태에 보관하고 Floating, 즉시 재생성, 실패 재시도 세 경로에 자동으로 주입했다.

수정 작업이 한 세션 안에 끝난다는 전제로 DB에는 저장하지 않았다. 세션을 넘겨 편집해야 한다면 영속화가 필요하다는 제한도 남겼다.

### 안정화: 테스트 범위와 retry 정책 정리

전반부에는 운영자 한 명이 직접 흐름을 검증했다. 후반부에는 변경 범위가 넓어져 순수 함수와 application 유즈케이스부터 자동화 테스트를 추가했다.

**테스트 범위.** 순수 함수(schemas, mappers, prompts, `classifyAiError`)와 application 유즈케이스(실제 DB, Gemini mock)를 먼저 검증했다. Storybook, Visual Regression, Playwright E2E, Testcontainers는 MVP 범위에서 보류했다.

테스트 인프라 핵심은 **격리 방식**이었다. tx rollback은 application이 자체 `withTransaction`을 쓰니까 외부 savepoint가 bypass되어 불가. 그래서 각 테스트 `afterEach`에서 `TRUNCATE CASCADE`로 정리. 기존 docker-compose PostgreSQL을 `?schema=test` URL로 재사용해서 Testcontainers 대신. AI는 MSW로 Gemini HTTP를 intercept (Imagen SDK는 HTTP intercept 불가라 `vi.mock`으로 직접). 통합 테스트는 `pnpm ci`에 포함하지 않고 `pnpm test:integration`으로 분리해 PR CI 시간 30초 이내 목표를 지켰다.

**retry 정책 통합.** conti 생성이 10회 중 약 8회 `fetch failed`로 5분 부근에서 실패하는 패턴을 발견했다. undici 기본 `headersTimeout`에 걸린 것이어서 두 레이어를 수정했다.

1. **undici 전역 Agent 10분**: `instrumentation.ts`에서 `setGlobalDispatcher`로 timeout 교체
2. **`withRetry` 네트워크 에러 분기**: `fetch failed` / `UND_ERR_HEADERS_TIMEOUT` / `ECONNRESET` 등을 감지해 기존 rate-limit fallback과 같은 흐름으로 모델 순회 (Pro→Flash→Lite)

429, 503, network 세 분기에 약 50줄씩 반복되던 fallback 순회 로직은 `ErrorPolicy` 인터페이스와 rateLimit, serviceUnavailable, network 정책 객체로 바꿨다. `classify(err)`가 구체적인 오류부터 정책을 고르고, 새 오류 유형은 정책 객체와 `POLICIES` 배열에 추가하도록 했다.

---

## 남은 것, 배운 것

### 남은 것

- 음악·애니메이션·음성은 후반에 6단계에서 폐기되고 말풍선 편집으로 재정의됐다. 음악/애니 자체는 별도 트랙으로 미정
- 버전 관리 (단계별 생성 이력 / 롤백 / 비교)
- API 비용 모니터링
- 표지 생성, 외부 플랫폼 연동
- Pro fallback 시 환각 약화: Flash/Lite로 떨어졌을 때 grounding 준수력이 약해지는 현상에 대한 별도 대응
- 말풍선 합성 파이프라인의 운영 적용

### 배운 것

**하네스는 반복 작업과 재시작 비용을 줄였다.** 구현, 계획 검토, 문서 정합성 확인을 단계로 나누고 작업 상태를 파일에 남겼다. 나는 기능 범위와 트레이드오프를 결정하고 각 단계의 결과를 확인했다.

**명세에 미결 사항을 드러내야 했다.** 사용자 흐름, 데이터 경계와 검증 방법을 먼저 적고 결정하지 못한 항목은 실행 전에 다시 다뤘다.

**계획 작성과 검토를 분리했다.** 별도 critic 단계가 현재 코드와 맞지 않는 가정과 빠진 검증을 실행 전에 찾았다.

**기술 선택은 제품 수명과 운영 범위에 맞췄다.** 이 내부 MVP에서는 Tailwind v4의 `@source inline`과 Zod 4의 `z.toJSONSchema()`가 별도 변환 코드를 줄이는 데 도움이 됐다.

**환각 대응은 프롬프트, 입력, 출력 검증을 함께 다뤄야 했다.** continuation에 grounding을 다시 넣고, 입력 범위를 좁히고, sourceQuote를 검사했다. 이미지 일관성에는 텍스트 지시 대신 이미지 레퍼런스를 사용했다.

**타입 소스는 레이어의 책임에 맞췄다.** 외부 입력은 Zod, ORM 연산은 Prisma 타입을 사용하고 경계에서 mapper로 변환했다.

**디자이너와는 파일 수정 책임을 나눴다.** Container/Presenter 구조와 `collaboration.md`의 소유권 표로 같은 파일을 동시에 수정하는 일을 줄였다. 목업을 실제 데이터 흐름에 맞추는 반복 작업은 `/integrate-ux`로 정리했다.

**문서는 다음 작업의 입력으로 사용됐다.** 종료된 결정과 중복 설명을 제거하고 현재 코드와 맞는 ADR만 남겨야 새 세션도 올바른 전제에서 시작할 수 있었다.

---

## 참고

- [하네스 엔지니어링](../../AI/harness-engineering-practice.md): 에이전트 작업 파이프라인의 구조와 변화
- [하네스 설계 원칙](../../AI/harness-engineering.md): 하네스 개념과 설계 기준
