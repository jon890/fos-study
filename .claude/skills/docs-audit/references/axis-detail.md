# 축별 구현 상세 — docs-audit

SKILL.md Step A / Step B 에서 참조하는 구현 상세.
메인 직접 검사(축 1, 2, 5, 6) ripgrep·Python 코드 + Sub-agent 표준 schema.

---

## 축 1 — Unlinked path mention 구현 상세

**ripgrep 패턴**:

```
pattern: `\`[a-zA-Z0-9_./\-]+\.mdx?\``       # 백틱 안의 .md 경로
pattern: `(?:[a-z0-9\-]+/)+[a-z0-9\-]+\.mdx?`  # 백틱 없이 본문에 등장한 경로
```

매치 줄에서 그 경로가 이미 `](path)` 형태로 감싸여 있으면 제외한다.

**추가 마스킹** — `[\`path\`](path)` 형태처럼 백틱 경로가 마크다운 링크의 표시 텍스트인 경우도 false positive다 (실측 확인됨).
다음 패턴으로 사전 제거:

```python
# 백틱이 link 표시 텍스트인 경우 제거
text = re.sub(r'\[`[^`]+`\]\([^)]+\)', '', text)
```

**수정 제안 형식**:

- 같은 폴더 파일: `[짧은 제목](./file.md)`
- 다른 폴더 파일: `[제목](../folder/file.md)` 또는 절대경로 `[제목](/folder/file.md)`
- 섹션 참조: `[제목 N장](./file.md#섹션-앵커)` (앵커는 heading 의 kebab-case)

---

## 축 2 — Broken link 구현 상세

**추출 패턴**:

```
pattern: `\]\(([^)]+\.mdx?(?:#[^)]*)?)\)`
```

추출한 각 링크에 대해:

1. `#앵커` 제거
2. 상대경로면 현재 파일 디렉터리 기준 해석, 절대경로면 저장소 루트 기준
3. `Path(...).exists()` 로 존재 확인
4. 없으면 보고 + "가까운 파일명" 후보 제시 (Levenshtein 또는 prefix 일치)

---

## 축 5 — 가시성·스캔 가능성 구현 상세

**검사 항목**:

1. **콤마-줄글 사례 단락** — 정보 항목 4개 이상이 `,` / `·` / `+` 로 한 줄에 이어진 paragraph
2. **긴 인라인 부연** — `](path) — ` 뒤에 70자 이상이 같은 줄에 이어짐
3. **누적성 섹션의 평탄화 부재** — `## 실제 적용 사례` / `## 관련 사례` / `## 적용 케이스` 헤더 아래 bullet 1개만 있고 그 bullet 이 1, 2번 패턴과 겹침
4. **인라인 링크 폭주** — 한 paragraph 안에 markdown 링크가 5개 이상

**전처리 — 코드/표 마스킹** (false positive 차단):

```python
text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # 펜스 코드 블록
text = re.sub(r'`[^`]+`', '', text)                     # 인라인 코드
# 표 행(| 시작) 은 콤마 카운트에서 별도 임계치
```

**시그널 우선순위 (강 → 약)**:

1. `,` 콤마 또는 `·` **4회 이상** — 가장 강한 시그널. 자연어에서 4개 이상 항목 enumeration 은 거의 항상 줄글이 약함
2. ` + ` **4회 이상** — 중간 시그널. `+` 는 문자열 concat / 합산식 / 스택 나열이 많아 단독으로는 약함
3. ` + ` **3회** — 가장 약함. 단독으로는 보고하지 않음

**의도적 줄글 패턴 — 사전 필터링 (보고 제외)**:

- `interview/**` 디렉터리의 면접 답변 카드 (한 호흡 키워드 enumeration)
- `resume/**` — 이력서 본문은 자연스러운 줄글
- `architecture/cj-foodville-*-interview.md`, `architecture/fnb-*.md` 등 면접 컨텍스트 파일 (이름에 "interview" / "fnb" / "foodville" 포함되면 보수적 처리)
- 자기소개 / 1분 발화 템플릿
- 5개 이내 기술 스택 단순 나열 (`Prometheus + Grafana + Tempo + Loki + OTel`)
- 메모리/사이즈/시간 합산식 (`7 + 100 + 8 = 115 bytes`)

---

## 축 6 — 문체 정적 검사 구현 상세

CLAUDE.md / blog-post-writer 룰 중 grep 한 줄로 잡히는 항목.

**검사 항목**:

1. **`~` 취소선 함정** — 한 paragraph(빈 줄 분리 단위) 안에 `~` 가 짝수 개로 등장 → 두 `~` 사이가 취소선으로 렌더링될 위험
2. **`§` 특수문자** — section sign 사용 금지 룰 위반
3. **Bold + 괄호 패턴** — `**텍스트(영문)**` 형태 (CLAUDE.md 룰: `**텍스트**(영문)` 으로 써야 함). **검증 권장** — 이 룰은 "일부 파서에서 깨진다" 추정 기반이라 fos-blog 실제 렌더링이 정상이라면 룰 자체를 완화 검토

**검사 코드**:

```python
# 1. ~ 취소선 함정 — 코드 블록 마스킹 후 paragraph 단위로 카운트
for paragraph in text.split('\n\n'):
    masked = re.sub(r'```.*?```|`[^`]+`', '', paragraph, flags=re.DOTALL)
    if masked.count('~') >= 2:
        flag(paragraph, 'tilde-strikethrough-risk')

# 2. § 잔존
if '§' in text:
    flag(line, 'section-sign-forbidden')

# 3. **텍스트(영문)** 패턴
re.findall(r'\*\*[^*]+\([^)]+\)\*\*', text)
```

**자동 수정 가능** — 명확한 룰이라 LLM 검토 후 일괄 Edit OK.
단 `~` 는 의도적 범위 표기일 수도 있어 paragraph 컨텍스트 보고 결정.

---

## Sub-agent 표준 schema

모든 sub-agent (orphan / cross-link / readme-integrity) 공통 출력 schema:

```yaml
axis: <orphan | cross-link | readme-integrity>
findings:
  - file: <repo root 기준 상대경로>
    line: <number 또는 null>
    severity: <high | medium | low>
    pattern: <짧은 패턴 식별자>
    related: <연관 파일 경로 또는 null>
    suggestion: <한 줄 제안>
total: <number>
notes: <짧은 메타 코멘트, 없으면 빈 문자열>
```

**호출 시 프롬프트 (간단)**:

각 agent 정의 파일에 system prompt 가 박혀 있으므로 호출 시 프롬프트는 간단한 task 트리거만 필요하다.

> "fos-study 저장소를 검사하고 표준 YAML schema 로 결과를 반환해라."
