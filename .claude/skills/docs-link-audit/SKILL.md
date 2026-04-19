---
id: workflow-docs-link-audit
name: docs-link-audit
description: fos-study 저장소 전체의 문서 링크 건전성을 감사한다. (1) 백틱 경로만 쓰고 링크가 아닌 곳, (2) 링크는 있지만 타겟 파일이 없는 broken link, (3) 아무도 참조하지 않는 orphan 문서, (4) 키워드 겹침 기반 cross-link 제안 후보 4가지 축을 스캔한다. "문서 링크 점검", "문서 연결 확인", "문서 링크 감사", "링크 정리", "broken link", "orphan doc", "cross-link", "docs-link-audit", "check-docs-relationship", "링크 상태", "문서 관계 파악", "문서 점검" 같은 요청 시 반드시 이 스킬 사용. 저장소 전체를 한 번 훑어 리포트를 만들고, 사용자 승인 후 일괄 수정을 제안한다.
source: conversation
triggers:
  - "문서 링크 점검"
  - "문서 링크 감사"
  - "문서 연결 확인"
  - "문서 관계 파악"
  - "링크 정리"
  - "링크 상태"
  - "문서 점검"
  - "broken link"
  - "orphan doc"
  - "cross-link"
  - "docs-link-audit"
  - "check-docs-relationship"
quality: high
---

# 문서 링크 감사 (docs-link-audit)

## The Insight

fos-study는 마크다운 저장소이고 fos-blog가 `resolveMarkdownLink()`로 상대·절대 경로를 블로그 URL로 변환한다. 그러므로 **"링크로 적힌 것은 자동으로 연결되지만, 백틱·일반 문장으로 적힌 경로는 그대로 문자열로 남는다"**. 저장소가 커질수록 이 두 형태가 뒤섞이며 연결이 끊어진 문서가 늘어난다. 이 스킬은 그걸 주기적으로 스캔해 원상 복구한다.

감사의 축은 4가지다.

1. **Unlinked path mention** — 경로가 본문에 등장하지만 마크다운 링크 문법(`[...](...)`) 안에 있지 않음
2. **Broken link** — 링크 문법은 올바른데 타겟 파일이 존재하지 않음
3. **Orphan doc** — 저장소 어느 문서에서도 참조하지 않는 `.md` 파일 (README/인덱스 예외)
4. **Cross-link 제안** — 두 문서가 같은 기술 키워드를 상호 언급하는데 양방향 링크가 없음

## Recognition Pattern

사용자가 아래 중 하나라도 말하면 이 스킬을 실행한다.

- "문서 링크 점검해줘"
- "fos-study 링크 상태 봐줘"
- "broken link 있는지 확인"
- "orphan 문서 찾아줘"
- "서로 링크 걸면 좋은 문서 있나"
- "/check-docs-relationship" 또는 "/docs-link-audit" 슬래시 호출

## 실행 순서

### 0. 사전 체크

```bash
# 저장소 루트 확인 — 반드시 /Users/nhn/personal/fos-study
pwd

# blog rendering 규칙 확인 (참고용, 매번은 불필요)
# fos-blog/src/lib/resolve-markdown-link.ts 가 지원하는 것:
# - 절대경로: /java/spring-batch/post.md → /posts/java/spring-batch/post.md
# - 상대경로: ./other.md, ../category/post.md
# - 앵커: post.md#section
```

### 1. Unlinked path mention 스캔

**정의** — 다음 두 조건 모두 만족:
- 본문에 `경로/파일.md` 또는 `경로/파일.mdx` 형태의 문자열이 등장
- 그 문자열이 `[...](...)` 링크 안에 있지 않음

**ripgrep 패턴** (Grep 도구 사용, `-n` true):

```
# 1차 후보 — 백틱 안에 .md 경로가 있는 모든 줄
pattern: `\`[a-zA-Z0-9_./\-]+\.mdx?\``
output_mode: content
-n: true
glob: "*.md"
```

추가로 백틱 없이 본문에 경로가 있는 경우(예: "`database/mysql/innodb-mvcc.md` 참고")도 잡는다:

```
pattern: `(?:[a-z0-9\-]+/)+[a-z0-9\-]+\.mdx?`
output_mode: content
-n: true
glob: "*.md"
```

**필터링** — 한 줄씩 검사해 그 경로가 이미 `](path)` 또는 `](./path)` 형태로 감싸여 있으면 제외. Python 또는 awk로 후처리 가능:

```bash
# 개념: 각 매치의 주변 문자를 확인해 이미 링크인지 판단
```

간단한 정규식으로 제외 조건을 표현하기 어려우면 매치 결과를 읽어서 프로그램적으로 판별한다(Read로 컨텍스트 읽어보기).

**수정 제안**
- 같은 폴더 파일: `[짧은 제목](./file.md)`
- 다른 폴더 파일: 저장소 루트 기준 상대경로 `[제목](../folder/file.md)` 또는 절대경로 `[제목](/folder/file.md)`
- 섹션 참조 시: `[제목 N장](./file.md#섹션-앵커)` — 앵커는 heading을 kebab-case로

### 2. Broken link 스캔

**정의** — `[text](target)` 문법 안의 `target`이 실제로 존재하지 않는 경우.

**절차**

```
# 모든 마크다운 링크 추출
pattern: `\]\(([^)]+\.mdx?(?:#[^)]*)?)\)`
output_mode: content
-n: true
glob: "*.md"
```

추출한 각 링크에 대해:
1. `#앵커`가 있으면 제거
2. 상대경로면 현재 파일 디렉터리 기준으로 해석
3. 절대경로면 저장소 루트 기준으로 해석
4. `fs.existsSync` 또는 `Bash("test -f ...")`로 존재 확인
5. 없으면 리포트에 포함

### 3. Orphan doc 스캔

**정의** — 저장소 내 어느 문서에서도 링크되지 않은 `.md` 파일.

**예외 — orphan 허용**:
- 각 폴더의 `README.md`, `AGENTS.md`, `CLAUDE.md`
- `task/*/README.md` (팀별 인덱스)
- 저장소 루트의 `CLAUDE.md`

**절차**

```bash
# 1. 저장소 모든 .md 파일 목록 수집
Glob: "**/*.md"

# 2. 모든 마크다운 링크 대상 수집
# (Broken link 스캔에서 사용한 패턴 재활용)

# 3. 각 파일별로 "참조당한 횟수" 계산
# 4. 참조 0 + 예외 목록에 없으면 orphan
```

### 4. Cross-link 제안

**정의** — 두 문서가 같은 주요 키워드를 상호 언급하는데 한쪽만 링크되거나 양쪽 모두 링크 없음.

**주요 키워드 소스** — 각 문서의 제목(H1) 및 상위 헤딩(H2)을 키워드로 취급. 문서 파일명도 키워드로 포함.

**절차 (경량 휴리스틱)**

```
# 각 .md 파일의 H1 제목 추출
pattern: `^# (.+)$`
output_mode: content
multiline: false

# 각 파일의 파일명 kebab-case도 키워드로 등록
```

문서 A의 본문에 문서 B의 제목/파일명 키워드가 등장하고, 그 등장이 링크가 아니면 "cross-link 후보"로 기록.

이 축은 false positive가 많으므로 **수정 자동 적용 금지**. 사용자에게 제안만.

## 리포트 형식

감사 결과는 아래 구조로 출력한다. 화면에만 표시(파일 생성 금지 — 사용자가 명시 요청 시에만).

```markdown
# 문서 링크 감사 리포트 — YYYY-MM-DD

## 요약
- Unlinked path mention: N건
- Broken link: N건
- Orphan doc: N건
- Cross-link 제안: N건

## 1. Unlinked path mention
| 파일 | 줄 | 현재 | 제안 |
|------|----|------|------|
| database/mysql/foo.md | 12 | `` `database/mysql/bar.md` `` | `[Bar](./bar.md)` |

## 2. Broken link
| 파일 | 줄 | 링크 | 상태 |
|------|----|------|------|
| AI/rag.md | 44 | `./embedding.md` | 파일 없음 (가까운 후보: `./embeddings.md`) |

## 3. Orphan doc
- `algorithm/foo.md` — 어느 문서에서도 참조되지 않음

## 4. Cross-link 제안 (선택 반영)
- `database/mysql/innodb-mvcc.md` ↔ `java/spring/jpa-transaction.md` — 양쪽이 "트랜잭션 격리"를 언급하나 상호 링크 없음
```

## 수정 적용 단계

1. 리포트 출력 후 **사용자에게 어떤 축을 수정할지 묻는다**. 축 단위 일괄 적용이 원칙. 예: "Unlinked path mention 5건 전부 적용할까?"
2. Unlinked/Broken은 **Edit 도구로 자동 적용 가능**. 단 broken link는 "가까운 파일명" 추천을 동반하고 사용자가 최종 선택.
3. Orphan은 **자동 수정 불가** — 어디에 링크를 달아야 할지는 사용자 판단 영역. 후보 위치만 제안(같은 폴더 README, 상위 인덱스).
4. Cross-link 제안은 **수동 반영**.
5. 변경 후 커밋 1개에 묶어서 만든다. 커밋 메시지 예:
   ```
   docs: 저장소 전체 링크 감사 — unlinked N건, broken N건 수정
   ```

## 안티패턴

- **앵커 자동 검증 시도** — heading-to-anchor 규칙은 렌더러마다 달라 완벽한 검증이 어렵다. 앵커가 끊어졌다고 단정하지 말고 "heading 텍스트와 앵커 문자열 불일치 가능성"으로만 표시.
- **경로만 보고 orphan 단정** — 코드 블록, 표, quote 안의 언급도 참조로 간주한다. 텍스트 문맥이 코드일 때도 검사 대상.
- **대량 자동 수정** — 한 번에 100건 넘는 Edit은 diff를 사람이 따라갈 수 없다. 축 단위로 끊어서 적용하고 중간에 사용자 확인.
- **외부 URL 포함 감사** — 이 스킬은 저장소 내부 링크만 대상. 외부 URL(HTTPS) 유효성은 별도 작업.
- **규모 과장** — 감사는 건전성 체크다. "저장소를 전부 재구성하자"는 권고는 범위 이탈. 발견한 문제만 보고한다.

## 주기

월 1회 또는 큰 문서 batch 작업 후 1회 수동 실행 권장. 자동화(cron/hook)는 현 시점에서 불필요.

## 참고

- 블로그 링크 렌더러: `/Users/nhn/personal/fos-blog/src/lib/resolve-markdown-link.ts`
- 저장소 컨벤션: `/Users/nhn/personal/fos-study/CLAUDE.md` "하위 문서 링크" 섹션
