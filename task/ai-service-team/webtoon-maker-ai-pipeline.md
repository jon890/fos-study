# 12일간 AI 웹툰 제작 도구 MVP 만들기 — 하네스 파이프라인으로 혼자 풀스택 돌리기

**진행 기간**: 2026.04.06 ~ 2026.04.30 (전반 12일 MVP + 후반 12일 안정화·운영 단계)

웹소설 원작을 받아 운영자가 작가 없이 웹툰 컷 이미지까지 뽑아내는 MVP를 짧은 기간에 만들어 보자는 사내 과제가 떨어졌다. 참여 인원은 나 한 명이었고, 프론트/백/DB/AI 파이프라인을 전부 내가 붙여야 하는 상황이었다. 요구한 범위가 좁지 않았다 — 소설 분석, 세계관, 캐릭터 시트, 각색, 글콘티, 컷 이미지 생성까지 6단계 풀 파이프라인이었다.

시작할 때 회의적이었다. 혼자 12일에 이만큼? 가능하긴 한가?

결론부터 말하면, **전반 12일 동안 199개 plan / 760개 커밋, 그 뒤 후반 12일 동안 추가로 36개 plan / 약 1,006개 커밋**이 쌓였다. 12일 시점에 한번 정리했던 이 글에 후반 12일 — "MVP에서 운영 단계로 끌어올린 작업"을 다시 보강해 24일 전체를 담는다. 내가 키보드로 1,700번 넘는 커밋 메시지를 친 게 아니다. Claude Code 기반 하네스 파이프라인이 있었기 때문에 가능한 볼륨이었다. 하네스 자체의 설계는 [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md)에 따로 정리했고, 이 글에서는 제품을 만들면서 얻은 인사이트를 다룬다.

---

## 뭘 만들었나

웹소설 .txt 파일을 넣으면 60컷짜리 웹툰 이미지가 나오는 웹 도구다. 파이프라인은 6단계.

```
[1] 작품 기획     ← 소설 분석, 세계관, 키워드, 화풍 추천
[2] 캐릭터/배경   ← 캐릭터 시트, 의상 세트, 배경 레퍼런스
[3] 스토리 각색   ← 기획안, 상세 각색안, 회차 매핑
[4] 글콘티        ← 회차별 트리트먼트, 50~60컷 글콘티
[5] 이미지 컷     ← 8대 요소 프롬프트 + Gemini Image
[6] 말풍선 편집   ← 후반부에 6단계 재정의 (음악/애니메이션 폐기, ADR-157)
```

운영자가 단계별로 결과를 확인하고, 인라인으로 수정하고, 재생성한다. 앞 단계를 수정하면 이후 단계의 확정이 연쇄적으로 해제된다. 브라우저를 닫아도 작업 상태는 보존된다.

AI 엔진은 Gemini 계열로 통일했다. 하나의 SDK(`@google/genai`)로 텍스트/이미지/Structured Output을 모두 처리할 수 있다는 게 의사결정에 크게 작용했다. MVP에서 멀티 벤더를 동시에 붙일 이유가 없었다.

---

## 12일 타임라인

```
04-06   11 커밋  — 프로젝트 초기 세팅
04-07   60 커밋  — 6단계 기본 뼈대
04-08   49 커밋  — 소설 분석, 세계관
04-09  120 커밋  — 캐릭터, 각색, 트리트먼트
04-10   77 커밋  — 글콘티, 프롬프트 조립
04-11   18 커밋  — 버그 수정
04-13   48 커밋  — Step5 이미지 생성 리팩터링
04-14  108 커밋  — 8대 요소 프롬프트, 소품 시트
04-15   81 커밋  — 비율 선택 UI, 캐릭터 시트 실험
04-16  102 커밋  — Semantic 토큰, 공통 컴포넌트
04-17   76 커밋  — Container/Presenter, Layout Primitives, conti 모듈화
04-18   10 커밋  — 캐릭터 외형 고정 (자동 레퍼런스 + outfit 모드)
```

11일간 총 760 커밋. 4/12는 쉬었다. 하루 최대 120 커밋이 나온 날이 있었다는 건, 내가 직접 타이핑해서 나올 수 있는 숫자가 아니라는 뜻이다.

---

## 기술 스택

혼자 12일에 풀스택을 쳐야 하니 "단일 코드베이스 + 타입 안전성 최대화"가 기준이었다. Next.js 16 / React 19 / Prisma 7 / Zod 4 / Tailwind v4 / `@google/genai` — 전부 당시 가장 최신을 골랐다.

선택 기준은 단순했다. 혼자 쓰는 MVP고 깨지면 내가 고치면 된다. 멀티 팀 엔터프라이즈처럼 "안정 버전 N-1" 같은 보수적 기준을 들이댈 필요가 없었다. 그 대신 얻는 건 Server Actions, Zod 4의 `z.toJSONSchema()`, Tailwind v4의 `@theme inline` / `@source inline` 같은 신기능이다. 우회 코드가 안 생긴다.

> **인사이트.** 보수적으로 N-1 버전을 고르는 건 팀이 공유하는 장기 프로젝트의 논리다. 개인 프로토타입에는 맞지 않는다.

---

## Gemini 모델 전략 — "싼 모델이 결과적으로 비싸다"

처음엔 flash를 기본으로 썼다. pro의 1/4 비용이고 빨랐다. 며칠 써 보니 방향을 바꿨다.

**운영자가 결과물을 보고 "다시 해야겠다"라고 느끼면 총 비용이 오히려 증가한다.**

저가 모델로 생성 → 퀄리티 불만족 → 재생성이 반복되면, 싸게 보이는 모델이 결과적으로 더 비싸다. pro 모델은 한 번에 만족하는 결과가 나올 확률이 훨씬 높았다. 그래서 ADR-072에서 전략을 뒤집었다. **pro가 기본, 429가 나면 flash → lite로 fallback.** 속도/비용을 우선 희생하고 퀄리티를 지킨다.

이 전략을 쓰면서 두 가지를 추가로 했다.

- **전역 Rate Limit Tracking (ADR-069).** 어떤 모델이 429를 받으면 그 모델을 일정 시간 "skip 대상"으로 마킹하는 메모리 Map을 뒀다. 다른 요청들이 같은 모델을 또 두드리지 않는다.
- **30초 재시도 로직 제거.** TPM은 1분 단위로 풀리는데 30초 대기는 너무 짧아 또 실패한다. 429가 나면 즉시 다음 fallback으로 넘기는 게 빠르고 안정적이었다.

> **인사이트.** "비용 최적화"는 단가가 아니라 총 호출 횟수(재생성 포함)로 봐야 한다. 그리고 분산된 재시도 정책은 전역 상태가 있어야 비효율이 안 쌓인다.

---

## 통합 분석 — API 경계 ≠ 논리 경계

Step1 소설 분석은 원래 5개 영역(작품 프로필, 스토리 구조, 관계도, 세계관, 장소)을 별도 호출로 처리했다. 관심사가 분리되어 보였지만, 63만자 소설을 4회 호출하면 분당 약 160만 토큰 — flash TPM 한도(200만)에 거의 닿는다. 캐시 미스나 재시도가 섞이면 바로 429다.

ADR-059에서 5개 영역을 하나의 Structured Output으로 합쳤다. 결과: 토큰 75% 절감, 속도 26.8s → 13.1s. 5개 영역의 논리적 경계는 Zod 스키마 안에서 필드로 나누는 것으로 충분했다.

> **인사이트.** API 호출 경계와 논리적 경계가 꼭 일치할 필요가 없다. Structured Output은 "한 번의 호출로 여러 관심사"를 열어준다.

---

## 60컷 일괄 생성 — SSE vs Promise.allSettled

처음엔 서버 SSE로 60개 순회 생성 + 진행률 스트리밍이었다. 부분 실패가 문제였다. rate limit 환경에서 60개 중 20~30개가 실패하면, 실패한 컷만 골라 재시도하는 상태 기계가 너무 복잡해졌다.

ADR-073에서 구조를 바꿨다. **클라이언트에서 `Promise.allSettled`로 60개 병렬 fetch.**

- 60개가 각각 독립된 요청이니 실패는 per-Promise로 추적된다
- 브라우저의 호스트당 6 동시 연결 제한이 자연스러운 throttling이다 — 따로 rate limiting을 짤 필요가 없었다
- `AbortController`로 전체 취소
- 실패한 컷은 같은 엔드포인트를 다시 호출하면 끝. 별도 재시도 경로 불필요

DB에는 `lastGenerationStatus`, `lastGenerationError`, `lastGeneratedAt`을 컷별로 저장해 UI에 "이 컷은 safety filter에 걸렸다" 같은 구체적 메시지를 띄울 수 있게 했다.

> **인사이트.** "1개의 긴 생성"은 SSE, "N개의 독립 생성"은 `Promise.allSettled`가 맞다. 글콘티 생성(LLM 단일 호출)은 SSE를 유지했고, 컷 이미지(N개 독립)는 클라이언트 병렬로 갔다. 성격이 다른 두 패턴을 한 구조로 묶지 않은 게 나중에 편했다.

---

## 프롬프트 환각 차단 — Grounding 재주입과 Project Cache

Step4 글콘티에서 가장 골치 아팠던 건 환각이었다. 트리트먼트에 없는 사건이 컷에 등장하거나, 등록된 캐릭터 외 이름이 새로 나오거나, 다음 회차에 들어갈 사건이 미리 들어오거나. 운영자가 일일이 지웠다.

처음엔 프롬프트에 `DO NOT invent` 같은 anti-pattern을 추가했다. 효과가 미미했다. 며칠 디버깅 끝에 진짜 원인을 찾았다.

**Continuation 호출이 tail 5컷만 보고 다음 컷을 만들고 있었다.**

50~60컷짜리 글콘티를 한 번의 LLM 호출로 만들기엔 너무 길어서, 1차 호출로 N컷을 받고 그 뒤를 continuation 호출로 이어 받는 구조였다. continuation에는 마지막 5컷만 컨텍스트로 넘겼다. 토큰 절약 목적이었다. 그 결과 LLM 입장에서는 "트리트먼트 grounding이 완전히 사라진 상태"에서 다음 컷을 만들고 있었다. 환각이 안 나오는 게 이상한 구조였다.

ADR-132에서 두 가지로 바로잡았다.

1. **Grounding 블록을 프롬프트 최우선에 박는다.** "원작/트리트먼트 범위에서만 가져올 것" + "허용되는 창의는 연출(카메라/구도/조명/페이싱)뿐" 같은 6개 제약. 핵심은 단순 금지가 아니라 **"연출은 자유, 서사는 grounding"이라는 경계 명시**였다. 금지만 나열하면 모델이 답답해서 클리셰로 도망가거나 grounding 자체를 무시한다.
2. **Continuation에도 Grounding/Treatment 블록을 매번 재주입한다.** 토큰을 더 쓰는 비용은 받아들였다. 환각으로 운영자가 컷을 일일이 수정하는 비용이 토큰값보다 훨씬 컸다.

토큰 비용은 다른 트릭으로 메웠다. **원작 소설은 Project 단위 Gemini Context Cache로 묶어 모든 단계에서 공유했다.** Analysis, Content-review, Treatment, Conti, Continuation — 다섯 단계가 같은 novelText를 본다. 매번 보내면 단계마다 수십만 토큰을 다시 결제하는 셈이다. cachedContent로 묶으면 만료(5분) 안에 들어오는 호출은 입력 토큰 비용이 0에 가깝다.

이 김에 conti 프롬프트 모듈을 3-layer로 쪼갰다 (`types/`, `templates/`, `blocks/`, `build-*.ts`). 1차/continuation 양쪽이 같은 `buildGroundingBlock()`을 호출하게 만들어, 두 호출의 grounding이 절대 어긋나지 않는다는 걸 코드 레벨에서 보장했다. 같은 구조를 character-sheet 프롬프트에도 적용했다.

> **인사이트 1.** AI 환각 차단은 "프롬프트 카피라이팅"이 아니라 "호출 구조 설계"의 영역이다. anti-pattern 문구 추가가 아니라, 어떤 컨텍스트가 어느 호출에 들어가는지가 본질이다.
>
> **인사이트 2.** "허용되는 창의의 범위"를 명시하면 금지가 더 잘 먹는다. 모델에게 도망갈 자리를 줘야 한다.
>
> **인사이트 3.** 환각 자동 판정기를 만들지 않았다. 환각의 경계가 fuzzy해서 자동 판정 자체가 또 다른 환각 소스가 된다. 사람 판정 + 체크리스트가 MVP에서는 가장 신뢰도가 높았다.

한 가지 미해결 과제: Pro가 429로 Flash/Lite로 fallback하면 grounding 준수력이 약해진다. 같은 프롬프트인데도 모델 capability 차이로 환각이 다시 등장한다. 서비스 연속성을 우선해 fallback은 유지했다.

---

## 캐릭터 외형 고정 — 텍스트가 아니라 이미지 레퍼런스로

Step2 캐릭터 시트는 한 캐릭터의 여러 의상(외출복, 잠옷, 전투복...)을 시트로 관리한다. 옷만 갈아입혀도 얼굴/머리/체형이 드리프트하는 게 문제였다. 같은 캐릭터인데 시트마다 얼굴이 미묘하게 달라지면, 후속 컷 생성에서 매번 다른 사람으로 보였다.

처음엔 텍스트 anti-drift로 막아보려고 했다. `[FIXED ANCHOR — DO NOT change] 얼굴 생김새: 기본 시트와 동일` 같은 식. 효과 없었다. **Gemini Image는 이미지 모델인데 텍스트로 "이전에 만든 시트와 동일하게"를 강제하는 건 근본적으로 한계가 있다. 모델은 그 "이전 시트"를 본 적이 없다.**

ADR-133/134에서 갈아엎었다.

- **스키마에서 "기본 시트" 개념을 만든다.** `CharacterSheet.isDefault`를 추가해 `(characterId, typeId)`마다 isDefault=true 시트가 정확히 1개 보장되게 했다. label="기본" 같은 관행은 다국어/이름 변경에 취약하고 자동화의 안정적 판별 기준이 못 된다.
- **비기본 시트 생성 시 기본 시트의 선택 이미지를 서버가 자동으로 레퍼런스 첫 번째에 prepend한다.** 운영자가 매번 기본 시트 이미지를 찾아 선택하지 않아도 된다.
- **mode 분기.** `default` 모드는 레퍼런스 미주입(외형 자유 변형), `outfit` 모드는 reference-bind 블록이 들어가 "첫 레퍼런스의 얼굴/머리/체형을 유지하고 의상만 변경"을 강제한다.
- **사전 체크.** 기본 시트 이미지가 없으면 서버가 400 `BASE_SHEET_REQUIRED`를 반환하고, 프론트는 모달로 기본 시트 카드로 스크롤 유도한다. 기본 시트 자동 생성은 안 한다 — 외형 확인이 필요한 단계라 자동 생성하면 운영자를 혼란시킨다.

> **인사이트.** 모델에 신호를 줄 때는 그 모델이 잘 다루는 채널로 줘야 한다. 이미지 일관성을 텍스트 프롬프트로 강제하는 건 채널 mismatch였다. 이미지 모델한테는 이미지 레퍼런스를 줘야 한다.

---

## 타입 시스템 — Zod 단일 소스 + 레이어별 분리

### Zod 단일 소스 (ADR-109)

처음엔 Gemini Structured Output용 스키마와 Zod 검증 스키마를 따로 유지했다. 한쪽만 고치면 "API는 통과했는데 Zod parse에서 터지는" 버그가 났다.

Zod 4의 `z.toJSONSchema()`로 단일 소스로 합쳤다. Zod 스키마 → JSON Schema 자동 변환 → Gemini `responseJsonSchema`로 사용 → 응답은 다시 Zod parse로 런타임 검증. 같은 개념을 두 번 적지 않게 됐다.

별개로 Structured Output 자체가 매우 유용했다. 옛날의 "JSON으로 답해줘 + 정규식 파싱" 패턴은 마크다운 백틱이나 trailing comma로 자주 깨졌다. `responseMimeType: "application/json"` + `responseJsonSchema` 조합은 파싱 실패 가능성이 사실상 사라졌다.

### 레이어별 타입 소스 (ADR-131)

Zod 단일 소스를 일관되게 적용하려고 Repository까지 `Partial<XxxFields>`로 통일하려 했다. 며칠 써 보니 어색한 매핑이 자꾸 생겼다.

특히 두 지점에서 부딪혔다.
- **Json 컬럼의 명시적 NULL.** Prisma는 `null`(필드 업데이트 안 함)과 `Prisma.DbNull`(NULL로 비우기)을 구분한다. Zod 추론 타입의 `null | undefined`로는 표현이 안 돼서 Repository 안에서 매번 수동 변환을 했다.
- **관계 처리.** `connect`/`create`/`disconnect` 같은 Prisma 고유 semantic을 외부 도메인 타입으로 흉내 내는 건 추상화 누수였다.

ADR-131에서 레이어별로 가장 적합한 타입 소스를 쓰기로 정리했다.

| 레이어 | 타입 소스 |
|---|---|
| Action 파라미터 | Zod `XxxFields` + TS 유틸(`Partial`/`Pick`) — 외부 경계 도메인 검증, AI 응답/UI 폼과 타입 공유 |
| Repository 파라미터 | `Prisma.XxxCreateInput` / `Prisma.XxxUpdateInput` — DB 연산 semantic, 관계 처리 네이티브 |
| 경계 | `actions/mappers/xxx-mapper.ts`의 작은 변환 함수 |

Action에서는 Prisma가 안 보이고, Repository에서는 Zod가 안 보인다. 양 레이어가 깨끗해졌다.

추가로 얻은 것: **Zod 스키마가 ADR 설계 원칙을 타입 수준에서 강제한다.** 예를 들어 ADR-099에 따라 `Character`는 외형 필드를 갖지 않고 `CharacterType`이 갖는다. `characterFieldsSchema`에서 `appearance`를 빼버리면 Action에서 `appearance` 수정 시도가 컴파일 시간에 막힌다. ESLint 룰로 표현하기 어려운 구조적 제약을 스키마 하나로 강제할 수 있다.

> **인사이트.** "단일 소스"가 항상 옳은 건 아니다. 외부 도메인과 ORM semantic은 추상화 수준이 다르다. 한쪽으로 통일하려고 하면 어느 쪽이든 어색해진다. 레이어 경계에 작은 mapper만 두면 양쪽이 깨끗해진다.

---

## UX 삽질 — onBlur 저장과 IME

글콘티 화면은 운영자가 60컷을 인라인 편집하는 거대한 폼이다. 초기 버전은 `onChange`로 매 입력마다 서버 액션을 호출했는데, 한글 IME에서 조합 중인 글자가 깨졌다. "안녕"의 "ㅇ-ㅏ-ㄴ" 입력 도중 서버 응답이 돌아오면 Server Component 리렌더로 미완성 글자가 덮어써진다.

표준 패턴으로 바꿨다 — 로컬 draft state + `onBlur` 저장. 입력 중에는 로컬 state로만 쌓이고, 포커스를 잃을 때만 서버 저장. CLAUDE.md에 코딩 규칙으로 박아 새 편집 컴포넌트에 일관 적용했다.

Dialog가 다시 열릴 때 초기값이 갱신 안 되는 문제는 `key={cut.id}`로 강제 리마운트했다 (ADR-019). React `useState` 초기값은 첫 렌더에만 설정되니, key가 바뀌어 언마운트/리마운트되어야 새 초기값이 들어간다.

> **인사이트.** Server Action은 편한 만큼 위험하다. UI 입력 흐름을 단순히 "입력 = 서버 저장"으로 매핑하면 IME, 디바운싱, 부분 실패가 다 한꺼번에 터진다. 입력은 로컬, 저장은 명시적 트리거.

---

## 아키텍처 레이어 — Server Action은 AI를 모르고, AI는 DB를 모른다

ADR-068에서 경계를 그었다.

| 레이어 | 담당 | 금지 |
|---|---|---|
| `actions/` | `"use server"`, 검증, repository 호출, `revalidatePath` | 직접 Prisma, AI 호출 |
| `lib/db/` | Prisma 쿼리, 트랜잭션 | 비즈니스 로직, `revalidatePath` |
| `lib/ai/client/` | Gemini SDK 래퍼, 모델 상수 | DB 접근 |
| `lib/ai/generators/` | AI 호출 + 결과 파싱 | DB 접근, `revalidatePath` |
| `api/generate/` | SSE, AI 파이프라인 오케스트레이션 | 직접 DB 쓰기 |

이미지 생성처럼 AI+DB가 둘 다 필요한 흐름은 API Route가 오케스트레이션한다. 이 경계 덕에 AI 리팩터링이 DB를 건드릴 일이 없었고 반대도 마찬가지였다.

또 하나 — **모델명 문자열 리터럴 금지.** `MODELS.llm.pro` 같은 상수만 허용. 오타가 컴파일 시간에 잡힌다.

---

## 디자인 시스템 + Container/Presenter — 디자이너와 충돌 해소

후반부에 UX 디자이너 한 분이 합류했다. Claude Code를 같이 쓰면서 디자이너가 시각 변경을 PR로 올리는 구조였다. 며칠 같이 일하면서 두 가지 문제가 또렷이 보였다.

- **같은 파일을 동시에 건드린다.** `StepConti.tsx` 같은 503줄 god component에 상태 / 데이터 / 레이아웃 / 이벤트가 다 섞여 있었다. 디자이너가 카드 spacing을 바꾸려면 이 파일, 내가 컷 재정렬 로직을 바꾸려면 이 파일. PR 두 개가 동시에 올라오면 매번 충돌.
- **인라인 magic spacing이 너무 많았다.** `flex flex-col gap-4`가 28곳에 흩어져 있어, "카드 사이 간격을 줄여달라"는 요구에 일일이 grep해서 바꿨다.

ADR-129/130에서 두 단계로 풀었다.

**1. Semantic CSS 토큰 + 공통 컴포넌트 (ADR-129).** Tailwind v4 `@theme inline`으로 `--color-card-surface` 같은 semantic 토큰을 정의하면 `bg-card-surface` 클래스가 자동 생성된다. 디자이너가 카드 색을 바꾸려면 `globals.css` 한 곳만 고치면 된다. "동일 구조 3곳 이상 반복"을 추출 기준으로 `components/common/`에 공통 컴포넌트를 모았다. 너무 빨리 추상화하면 prop drilling만 늘어난다는 걸 다른 프로젝트에서 데여서, 의도적으로 보수적인 기준을 잡았다.

**2. Container/Presenter + Layout Primitives (ADR-130).** god component를 두 층으로 쪼갰다.

```
src/components/step4-conti/
├── containers/   # 상태 + 데이터 + 이벤트 wiring (로직)
├── components/   # JSX + 시각 (UI)
├── hooks/        # 상태 추출
└── adapters/     # 도메인별 차이 흡수
```

원칙은 두 줄.

> 디자인 변경은 globals.css + 시각 컴포넌트만 건드려서 가능해야 한다.
> 로직 변경은 상태·데이터 파일만 건드려서 가능해야 한다.

이걸 ADR뿐만 아니라 `docs/collaboration.md`의 **파일 소유권 매트릭스**로 박았다. 디자이너는 `globals.css`, `components/common/layout/`, `components/**/components/`만 수정. 백엔드는 `actions/`, `lib/`, `components/**/hooks/`, `components/**/containers/`만 수정. 동일 파일 동시 수정이 발생하면 그 자체가 "구조 위반 신호"다. git conflict가 거짓말처럼 사라졌다.

레이아웃 magic number는 layout primitive 5종(`Stack`, `Cluster`, `Grid`, `Sidebar`, `Frame`)으로 흡수했다. every-layout.dev 스타일이다. `<Stack gap="4">` 같은 식으로 의미를 부여하니 인라인 `flex flex-col gap-4`가 사라졌다.

Tailwind v4에서 한 가지 함정은 있었다. primitive가 `GAP_MAP[gap]` 같은 객체 조회로 클래스를 조립하다 보니, JIT 정적 분석이 일부 클래스를 못 잡아 빌드 후 누락이 났다. v4 공식 API인 `@source inline("gap-2 gap-4 ...")` 한 줄로 해결. 또 한 가지 룰: **동적 클래스는 객체 매핑만 허용, 템플릿 리터럴 금지.** `` `gap-${x}` ``는 JIT이 잡을 길이 없다.

> **인사이트.** 디자이너와의 협업은 추상적인 ADR이 아니라 **파일 소유권 매트릭스**로 정리된다. "관심사 분리" 원칙보다 "이 디렉터리는 누가 건드린다"는 구체적 룰이 협업에서 훨씬 잘 동작한다.

---

## 하네스 진화 — vibe 코딩에서 spec 기반 코딩으로

12일 동안 가장 많이 바뀐 게 하네스 자체였다. 기억나는 단계만 추리면 이렇다.

### 1단계 — vibe 코딩

처음엔 "Claude한테 시키면 알아서 하겠지" 정도였다. 한 세션에서 논의 → 즉석 구현 → 빌드 → 테스트를 다 했다. 짧은 작업은 잘 됐다. 그런데 작업이 길어지면 세션이 컨텍스트 한도에 걸리거나, 도중에 잘못된 가정으로 시작해 한참 가다가 갈아엎거나, 비슷한 결정을 매번 다시 내려야 했다.

가장 큰 문제는 **"무엇을 할지"를 충분히 잡지 못한 채 코드부터 쳤다는 것**이었다. 모호한 상태에서 시작하면 모델이 실행 중에 임의 결정을 한다. 그 결정이 틀리면 결과를 통째로 버린다.

### 2단계 — `/planning`: 스펙을 먼저 잡는다

설계 단계를 별도 워크플로우로 분리했다. 기능 구현 전에 8단계로 논의한다 — 기술 가능성, 사용자 흐름, 데이터 모델, API 설계, 화면 동작, 엣지 케이스, 마이그레이션, 검증 방법. 모든 결정이 합의되어야 task 파일을 만든다.

Opus 모델에서 진행한다. 비싸지만 설계 단계의 판단 정확도가 결과에 미치는 영향이 압도적으로 크다. 잘못된 task로 executor를 돌리면 그 시간/토큰이 더 비싸다.

> **인사이트.** AI 시대의 "vibe 코딩 → spec 기반 코딩" 전환은 사람이 더 많이 쓰는 게 아니라 **에이전트에게 줄 입력의 정확도를 올리는 것**이다. 모호한 입력은 모호한 출력을 낳는다. 결정의 80%는 task 파일 안에 박혀 있어야 한다.

### 3단계 — `/plan-and-build`: phase 분할 + 재시작 가능

planning 결과물은 `tasks/planNNN-*/index.json` + 여러 phase 파일로 떨어진다. phase 파일은 자기완결적이라 이전 대화 없이 독립 실행이 가능하다. `run-phases.py` 하네스가 `index.json`을 읽고 pending phase부터 순차 실행한다.

핵심 속성은 **재시작 가능성**이다. 세션이 끊겨도, executor가 중간에 실패해도, git에 task 파일이 있으니 어디서든 이어받을 수 있다. 1회성 휘발 세션이 아니라 task가 영속 상태가 됐다.

### 4단계 — `/build-with-teams`: critic + docs-verifier 게이트

`plan-and-build`에 두 개의 검증 게이트를 추가했다.

- **critic.** 계획을 실제 코드와 대조해 APPROVE/REVISE 판정을 내린다. "이 phase 파일이 현재 코드 상태에서 실행 가능한가? 가정이 맞는가?"를 체크. REVISE면 phase 파일을 고치고 다시 critic을 돌린다.
- **docs-verifier.** executor가 코드를 바꾼 뒤 ADR/data-schema 같은 문서가 정합성을 유지하는지 확인. 코드와 문서의 드리프트를 다음 세션이 시작되기 전에 잡는다.

이 두 게이트가 추가되면서 잘못된 계획이 실행 중에 터지는 일이 거의 사라졌다. 4인 에이전트 팀(planner / critic / executor / docs-verifier)이 한 plan을 함께 처리하는 구조다.

> **인사이트.** 단일 에이전트보다 **역할 분리된 에이전트 팀**이 훨씬 안정적이다. 같은 모델이라도 역할에 맞는 시스템 프롬프트를 받으면 다른 시야로 본다. 자기가 짠 계획을 자기가 검증하면 잘 못 본다 — 별도 에이전트한테 critic 역할을 주면 본다.

### 5단계 — `/integrate-ux`: 디자이너 vibe 코드를 정상 통합하기

후반에 UX 디자이너 한 분이 합류했다. React를 모르지만 Claude Code로 vibe 코딩하면서 컴포넌트 목업 PR을 올렸다. 디자인 감각으로 만든 결과물은 좋았는데, 코드는 "프로젝트 컨벤션과 다른 방식"으로 짜여 있었다.

- 로컬 state로 데이터를 시뮬레이션 (Server Action 대신 useState + 하드코딩)
- 공통 컴포넌트를 모르고 인라인으로 새로 그린 카드/버튼
- 기존 디자인 시스템 토큰 대신 인라인 색상값
- Container/Presenter 분리 무시

매번 같은 변환을 내가 손으로 했다. 패턴이 보였다. 스킬 파일로 박았다.

`/integrate-ux`는 이런 일을 한다.
- 디자이너 PR을 rebase하고 동작 확인
- 로컬 state 목업을 실제 Server Action 호출로 치환
- 인라인 카드/버튼을 `components/common/`의 공통 컴포넌트로 교체
- 인라인 색상을 semantic 토큰으로 매핑
- god component를 Container/Presenter로 분리
- 변환 후 빌드 + 시각 회귀 체크

이걸 스킬화하니 디자이너가 PR을 올린 직후에 `/integrate-ux <PR번호>` 한 줄로 통합이 끝난다. 디자이너는 "동작하는 디자인"을 자유롭게 만들고, 나는 그걸 컨벤션에 맞춰 통합하는 역할에 집중한다.

> **인사이트.** **vibe 코딩 결과물을 spec 기반 코드로 정착시키는 변환 자체가 반복 가능한 워크플로우**다. 디자이너의 vibe 코드를 "다시 짜야 한다"고 생각하지 말고, "정해진 변환 룰로 흡수한다"고 생각하니 협업의 마찰이 사라졌다. AI 협업 시대의 페어 프로그래밍은 사람-사람이 아니라 사람-에이전트, 그리고 에이전트가 만든 결과물 사이의 정합성 유지였다.

### 정리

처음의 vibe 코딩에서 시작해서, planning으로 입력 정확도를 올리고, plan-and-build로 재시작 가능한 실행을 만들고, build-with-teams로 검증 게이트를 추가하고, integrate-ux로 협업자의 vibe 결과물을 흡수하는 — 이 다섯 단계가 12일 동안 단계적으로 쌓였다. 199개 plan을 처리할 수 있었던 건 이 진화의 결과다. 새 스킬을 만든 시점부터는 같은 종류의 작업이 한 줄 명령으로 끝났다.

상세한 구조와 진화 과정은 [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md)에 정리해뒀다.

---

## docs-first

코드를 고치기 전에 ADR과 data-schema를 먼저 업데이트한다. task가 실패해도 결정은 docs에 보존된다. AI 에이전트는 새 세션에서 `CLAUDE.md`, `docs/adr.md` 같은 문서를 컨텍스트로 읽는다. 이 문서가 현실을 반영해야 에이전트가 올바른 전제로 시작한다.

12일 동안 134개 ADR이 쌓였다 (ADR-001 ~ ADR-134). 한 번 ADR이 1,581줄까지 비대해졌는데, docs-verifier가 "AI 에이전트 컨텍스트 효율 관점에서 너무 길다"고 지적해서 700줄 수준으로 줄였다. **ADR도 결국 AI 에이전트를 위한 문서**라는 관점을 잊으면 안 된다.

---

## 후반 12일 — MVP에서 운영 단계로

전반 12일이 끝났을 때 글을 한번 정리했다. 그 뒤 4-19부터 4-30까지 약 12일 동안 plan185부터 plan235까지 51개 plan, 약 1,006개 커밋이 더 쌓였다. ADR도 ADR-134에서 ADR-186까지 52개가 추가됐다. **혼자 돌리는 MVP를 운영 가능한 상태로 끌어올린다** 한 줄이 이 12일의 성격이다. 처음에는 손으로 빠르게 박은 코드가 많았는데, 후반부엔 그 빠른 코드들의 경계를 다시 그리고, 관찰 가능하게 만들고, 환각·실패·테스트의 빈틈을 채우는 일이었다.

### 6단계 재정의 — 음악·애니메이션 폐기, 말풍선 편집 도입 (ADR-157)

원래 6단계는 "동영상/음악"이었다. MVP 범위 밖으로 미뤄둔 채 스켈레톤만 박아둔 상태였다. 후반부에 **6단계를 통째로 폐기하고 "말풍선 편집"으로 재정의**했다. 웹툰의 최종 산출물 흐름을 보니, 음악·애니메이션은 별도 트랙으로 분리하는 게 맞았고 정작 컷 위에 말풍선을 얹는 단계가 없으면 "웹툰 제작 도구"로 완결이 안 됐다.

이 결정 하나로 글 첫머리의 6단계 표가 바뀐다. 12일 시점에서 "Phase 2"로 미뤄뒀던 영역이 후반에 와서 "사실 우리에게 필요한 건 이게 아니었다"로 결론났다는 건, MVP 범위를 정할 때 **"무엇을 빼는지"가 "무엇을 하는지"만큼 중요하다**는 걸 다시 확인한 사건이었다. 빼두는 단계도 시간이 지나면 다시 평가받아야 한다.

### 도메인 레이어 분리 — Controller / Application / Domain 3-tier (ADR-135, 156, 159, 160)

12일 시점에 박았던 ADR-131 "레이어별 타입 소스"는 **타입 수준의 분리**였다. Action은 Zod, Repository는 Prisma. 그 위에 후반부에는 **코드 위치 자체를 도메인 단위로 정리**하는 작업이 필요해졌다. 빠르게 짠 코드가 누적되면서 SSE 도중 Action을 호출해 revalidate 타이밍이 비결정이 되거나, repository에 비즈니스 정책이 박히거나, AI 레이어에서 Project row를 직접 쓰는 경계 위반이 쌓였다.

ADR-135에서 **Controller / Application / Domain 3-tier**를 명시했다.

- **Controller**(`actions/`·`app/api/`): Zod 파싱 + application 호출 + 응답 변환
- **Application**(`lib/application/` + 도메인별 `lib/domains/{domain}/application/`): 트랜잭션 경계 + revalidate 부수효과 + 다중 도메인 조합
- **Domain**(`lib/ai`·`lib/db`·`lib/schemas` + 도메인 vertical slice): 순수 기능

핵심은 **Application 경유 기준**을 4개로 못박은 것이다. 트랜잭션 필요, revalidate 부수효과, 2개 이상 도메인 조합, projectId 개입 경로. 단일 repo + 단일 revalidate는 Controller에서 직통 허용 — "모든 걸 application 거치게" 강제하면 얇은 wrapper만 남발된다는 걸 미리 차단했다.

코드 위치도 같은 흐름으로 점진 이동했다. ADR-156에서 `lib/db/repository/` 평면 구조를 `lib/db/domains/{domain}/`로 도메인 폴더화했고, ADR-159에서 다시 한 단계 더 올라가 `lib/domains/{domain}/`로 vertical slice를 파일럿했다. ADR-160으로는 **`prisma` 직접 import를 repository 외부에서 금지**하는 ESLint 룰을 박았다. 트랜잭션은 application의 `withTransaction`을 통해서만 받는다. 경계가 코드 레벨에서 강제되니, 후속 plan들이 무심코 경계를 넘는 일이 사라졌다.

전반 12일에 "빠르게 짠 코드"의 부채를 후반 12일에 "경계를 다시 그어 갚는" 흐름이 자연스럽게 따라왔다.

### 운영 관찰성 — pino + AsyncLocalStorage MDC (ADR-154)

12일 동안에는 `console.log` / `console.error`만으로 충분했다. 혼자 돌리는 MVP고 로그를 직접 보면 됐다. 후반부에 운영 시점이 가까워지면서 한계가 보였다. 같은 시간에 두 프로젝트가 돌면 **어느 요청·어느 프로젝트에서 발생한 로그인지** 추적이 안 됐고, 에러 전후 문맥을 재구성하려면 로그 줄을 수동으로 묶어야 했다.

ADR-154에서 **pino + `AsyncLocalStorage` 기반 MDC**를 도입했다. Java SLF4J의 MDC, Python의 `contextvars`와 같은 역할이다.

- 고정 bindings: `service`, `env`
- request-scoped: `requestId`, `projectId`, `projectName`
- `src/proxy.ts`(Next.js 16+의 옛 `middleware.ts`)에서 `X-Request-ID` 생성·반사
- 각 Server Action / Route Handler 진입점을 `withLogContext(fn)` wrapper로 감싸 als.run 시작
- application의 `loadProjectForContext(id)`가 project 로드 직후 `logContext.update({projectId, projectName})` 주입
- `console.*`는 서버 코드에서 ESLint `no-console` error로 금지. 클라이언트는 대상 외

도입할 때 가장 신경 쓴 건 **점진 교체가 아니라 원샷 전수 교체**였다. 신규 코드만 새 logger를 쓰는 점진 방식은 혼재 기간이 길어 디버깅 시 두 종류 로그를 동시에 봐야 한다. 한 번에 다 갈아엎는 게 결과적으로 빠르다.

`AsyncLocalStorage` 전파 경계는 한 가지 함정이 있다 — Prisma EventEmitter나 AI retry/fallback 루프에서 컨텍스트가 끊길 수 있다. 이 경로들은 통합 테스트로 검증하고, 끊기면 request-scoped 필드 없이 고정 bindings만 남기는 식으로 받아들였다.

> **인사이트.** 관찰성 도입 시점은 "코드를 더 짤 시간 vs 운영을 시작할 시간"이 교차할 때다. MVP 시작 시점에 도입하면 과투자고, 운영 직전에 도입하면 늦다. 후반 12일 어귀가 그 교차점이었다.

### 환각 차단의 다음 단계 — sourceQuote와 트리트먼트 슬라이싱 (ADR-149, 176)

전반 12일 ADR-132로 환각 차단을 정리했다고 생각했다. 본문에 적은 그대로 — Grounding 블록을 프롬프트 최상단에 박고, continuation에 매번 재주입하고, 허용되는 창의의 범위를 명시. 후반부에 두 번 더 진화했다.

**ADR-149: sourceQuote 필수 + substring 검증.** ADR-132는 원칙을 선언했지만 구현이 그 원칙을 **구조적으로 강제하지는 않았다**. continuation 후반 컷에 원작 외 환각이 다시 등장하는 사례가 보였다. 진단해보니 `buildContiPrompt`(1차)와 `buildContinuationPrompt`(이어쓰기)의 프롬프트 구성이 비대칭이었다. 1차에는 PERSONA / CUT_WRITING_RULES / charactersBlock 등이 들어가는데 continuation에는 grounding + treatment + tail + 짧은 rules만 있었다. 두 가지로 풀었다.

1. **continuation 프롬프트 파리티** — 1차와 동일한 구성 블록을 continuation에 재주입. 토큰 비용 감수
2. **`Cut.sourceQuote` 필수** — 각 컷이 원작 novelText에서 글자 그대로 추출한 인용을 함께 생성. generator가 `novelText.includes(sourceQuote)`로 substring 검증, 실패 시 logger().warn

**ADR-176: 트리트먼트 소설 범위 슬라이싱.** sourceQuote가 들어간 뒤에도 빈틈이 있었다. `novelText.includes`는 **소설 전체를 검증**하므로 "트리트먼트 범위 밖 원작 인용"은 통과했다. 트리트먼트 schema의 `novelRange`가 자연어 라벨("1부 5장 도입~중반")이라 모델이 어떤 글자 범위인지 매칭할 수 없었다.

해법은 schema에 `Treatment.novelRangeStart: Int?` / `novelRangeEnd: Int?` 인덱스를 추가하고, application에서 `novelText.slice(start, end)`만 generator에 전달하는 것. 모델 입력 자체가 좁아져 **범위 밖 텍스트를 볼 수도 없다**. sourceQuote substring 검증도 자동으로 "트리트먼트 범위 내 인용" 검증으로 강화됐다 — 같은 코드 라인 변경 없이.

> **인사이트.** "원칙을 선언했다"와 "원칙이 코드 레벨에서 강제된다"는 다르다. ADR-132 → 149 → 176의 흐름은 **선언적 grounding이 점점 구조적 grounding으로 내려간 과정**이다. 모델이 무엇을 보면 안 되는지를 프롬프트로 말하는 단계 → 출력 형식으로 검증하는 단계 → 입력 자체를 좁히는 단계.

### 이미지 파이프라인 후속 — AbortSignal SDK까지 + 사용자 레퍼런스 첨부 (ADR-137, 150)

전반 12일에 60컷 일괄 생성을 클라이언트 `Promise.allSettled`로 옮긴 게 ADR-073이었다. 후반부에 같은 패턴을 컷·배경·소품 3종으로 통일하고, SDK까지 신호를 전파하는 작업이 들어갔다.

**ADR-137: 배치 생성 통합.** 컷은 `AsyncIterable` + `[AbortController](../../javascript/abort-controller.md)` + 전량 병렬, 배경/소품은 `CONCURRENCY=3` 슬라이스 + `batchAbortedRef` boolean — 같은 일을 두 패턴이 하고 있었다. 후자를 폐기하고 전자로 수렴했다. 핵심은 **`AbortSignal`을 SDK까지 전파**한 부분이다. 클라이언트 `fetch(signal)` → route의 `request.signal` → application → generator → `@google/genai` SDK의 `config.abortSignal`까지.

`@google/genai`의 `abortSignal`은 client-only로 명시되어 있어 Google 서버의 작업 자체는 중단 안 된다. 비용은 발생한다. 그럼에도 전파한 이유는 (1) 대기 중이던 요청의 시작 억제, (2) 네트워크/메모리 즉시 회수, (3) 향후 SDK가 실제 취소를 지원하면 자동 수혜. **지금은 이득이 작지만 차후 공짜 업그레이드를 받기 위해 시그니처를 미리 정비**가 의도였다.

**ADR-150: Step5 컷 레퍼런스 첨부.** FloatingRegenBar(ADR-148)와 즉시 재생성은 텍스트 기반이었다. "사소한 수정(포즈 미세 조정, 컬러 유지)"은 텍스트보다 **현재 컷 자체를 레퍼런스로 재주입**해 seed를 유지하는 편이 의도 전달이 쉬웠다. 1장 한정, 세션 일시 state(스키마 변경 없음), 재생성 3경로(Floating / 즉시 / 실패 재시도) 모두 자동 주입.

DB 영속화는 의도적으로 뺐다. "사소한 수정은 한 세션 안에 끝난다"는 가정 + 스키마 변경 + 마이그레이션 비용을 피했다. 가정이 깨지면 후속 plan에서 영속화로 전환할 여지를 남긴 결정.

### 안정화 — Trophy 테스트 모델 + retry 정책 테이블 (ADR-136, 145, 147)

전반 12일에는 테스트가 거의 없었다. 운영자 한 명이 직접 돌리며 검증하는 단계라 자동화 테스트 투자가 과해 보였다. 후반부에 plan195부터 통합 테스트가 들어가기 시작했다.

**ADR-136: Trophy 모델.** Kent C. Dodds Trophy(정적 5% + 유닛 45% + 통합 45% + E2E 5%)로 정책을 잡았다. 우선순위는 (1) 순수 함수(schemas / mappers / prompts / classifyAiError), (2) application 유즈케이스(실 DB + Gemini mock). Storybook · Visual Regression · Playwright E2E · Testcontainers는 **명시적으로 보류**.

테스트 인프라 핵심은 **격리 방식**이었다. tx rollback은 application이 자체 `withTransaction`을 쓰니까 외부 savepoint가 bypass되어 불가. 그래서 각 테스트 `afterEach`에서 `TRUNCATE CASCADE`로 정리. 기존 docker-compose PostgreSQL을 `?schema=test` URL로 재사용해서 Testcontainers 대신. AI는 MSW로 Gemini HTTP를 intercept (Imagen SDK는 HTTP intercept 불가라 `vi.mock`으로 직접). 통합 테스트는 `pnpm ci`에 포함하지 않고 `pnpm test:integration`으로 분리해 PR CI 시간 30초 이내 목표를 지켰다.

**ADR-145 / 147: retry 정책 통합.** 전반 12일 ADR-069에서 "429 즉시 fallback"을 박았는데, 후반부에 conti 생성이 10회 중 8회 수준으로 `fetch failed` @ ~5분에 실패하는 패턴을 발견했다. undici 기본 `headersTimeout`(5분)에 걸린 거였다. ADR-145에서 두 레이어로 막았다.

1. **undici 전역 Agent 10분** — `instrumentation.ts`에서 `setGlobalDispatcher`로 timeout 교체
2. **`withRetry` 네트워크 에러 분기** — `fetch failed` / `UND_ERR_HEADERS_TIMEOUT` / `ECONNRESET` 등을 감지해 기존 rate-limit fallback과 같은 흐름으로 모델 순회 (Pro→Flash→Lite)

ADR-147에서는 **분기 자체를 테이블화**했다. 429 / 503 / network 세 분기가 각각 ~50줄씩 거의 같은 fallback 순회 루프를 복붙하고 있었다. `ErrorPolicy` 인터페이스 1개 + 정책 객체 3개(rateLimit / serviceUnavailable / network)로 압축하고 `classify(err)`가 가장 구체적인 에러부터 매칭. 새 에러 타입 추가는 정책 파일 1개 + POLICIES 배열에 1줄.

> **인사이트.** **에러 분기는 코드 분기보다 데이터로 두는 게 늘 낫다.** 처음 한두 개일 때는 if-else가 자연스럽지만 세 개 넘어가면 각 분기의 공통점이 빠르게 새어나간다. 정책 객체로 추출해두면 새 분기가 코드를 바꾸지 않고 데이터만 추가한다.

---

## 남은 것, 배운 것

### 남은 것

- 음악·애니메이션·음성은 후반에 6단계에서 폐기되고 말풍선 편집으로 재정의됐다. 음악/애니 자체는 별도 트랙으로 미정
- 버전 관리 (단계별 생성 이력 / 롤백 / 비교)
- API 비용 모니터링
- 표지 생성, 외부 플랫폼 연동
- Pro fallback 시 환각 약화 — Flash/Lite로 떨어졌을 때 grounding 준수력이 약해지는 현상에 대한 별도 대응
- 말풍선 합성 파이프라인의 본 도입 (후반부에 ADR-166까지 진화. 실제 운영 적용은 진행 중)

### 배운 것

**하네스가 없으면 12일은 불가능했다.** 생성을 에이전트가, 평가를 critic이, 문서 정합성을 docs-verifier가 한다. 내가 하는 일은 "무엇을 할지 결정"에 집중된다. 이 분업이 안 되면 같은 시간에 1/5 수준의 결과만 나왔을 것이다.

**vibe 코딩에서 spec 기반 코딩으로의 전환이 핵심.** 에이전트에게 줄 입력의 정확도를 올리는 게 곧 결과 품질이다. planning에서 결정이 안 된 부분이 나중에 어떻게든 터진다. 80%는 task 파일에 박혀 있어야 한다.

**역할 분리된 에이전트 팀이 단일 에이전트보다 안정적.** 같은 모델이라도 critic 역할을 받으면 다른 시야로 본다. 자기 계획을 자기가 검증하는 건 잘 안 된다.

**최신 스택을 두려워하지 않기.** 개인 프로토타입에는 N-1 보수주의가 안 맞는다. v4의 `@source inline`이나 Zod 4의 `z.toJSONSchema()`가 없었으면 우회 코드가 한참 늘어났다.

**AI 환각은 프롬프트 카피라이팅이 아니라 호출 구조 설계.** anti-pattern 문구 추가 vs. continuation에 grounding 재주입 — 후자만이 본질적 해결이었다. 모델 입력 채널의 본질에 맞는 신호를 줘야 한다 (이미지 일관성도 마찬가지로 텍스트 anti-drift가 아니라 이미지 레퍼런스).

**타입 소스는 레이어마다 달라도 된다.** "단일 소스 통일"이 항상 옳은 건 아니다. 외부 도메인은 Zod, ORM semantic은 Prisma. 경계에 작은 mapper만 두면 양쪽이 깨끗해진다.

**디자이너와의 협업은 ADR이 아니라 파일 소유권으로.** Container/Presenter + collaboration.md의 매트릭스가 git conflict를 거의 0으로 줄였다. 그리고 디자이너의 vibe 결과물을 "다시 짜야 할 것"이 아니라 "정해진 변환으로 흡수할 것"으로 보면 마찰이 사라진다 (`/integrate-ux`).

**문서 부패가 컨텍스트 부패다.** AI 에이전트 시대에는 문서가 사람뿐 아니라 에이전트의 컨텍스트가 된다. ADR 하나를 잘못 유지하면 다음 세션의 에이전트가 잘못된 전제로 시작한다. docs-first는 매너가 아니라 생산성 도구다.

**"팔 쓰는 건 모델, 머리 쓰는 건 사람"이 점점 옛말이 된다.** Sonnet도 critic 역할에서 내 계획의 구멍을 잡아낸다. 다만 구조 설계, 트레이드오프 판단, 제품 방향은 여전히 사람이 한다. 경계가 흐려지는 만큼 사람의 역할은 "더 상위 수준의 판단"으로 이동한다.

---

## 참고

- [하네스 엔지니어링 실전편](../../AI/harness-engineering-practice.md) — 4인 에이전트 팀 파이프라인의 구조와 진화
- [하네스 엔지니어링 이론편](../../AI/harness-engineering.md) — 하네스 개념, Anthropic/Fowler 사례, 설계 원칙
