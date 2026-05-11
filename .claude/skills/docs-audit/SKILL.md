---
id: workflow-docs-audit
name: docs-audit
description: fos-study 저장소 전체의 문서 건전성을 7개 축으로 종합 감사한다. (1) 백틱으로만 적힌 path mention, (2) broken link, (3) orphan doc, (4) cross-link 제안, (5) 가시성·스캔 가능성, (6) 문체 정적 검사 (`~` 취소선, `§` 사용, Bold+괄호 패턴), (7) README ↔ 실제 파일 정합성. Hybrid 실행 모델 — 가벼운 정적 검사는 메인이 직접, 무거운 의미 검사(orphan/cross-link/README 정합성)는 sub-agent 병렬 위임. "문서 감사", "docs-audit", "문서 점검", "문서 종합 점검", "문서 링크 점검", "broken link", "orphan doc", "cross-link", "가시성 점검", "README 정합성", "전체 문서 검토" 같은 요청 시 반드시 이 스킬 사용. 저장소를 한 번 훑어 통합 리포트를 만들고, 사용자 승인 후 축 단위로 수정한다.
source: conversation
triggers:
  - "문서 감사"
  - "docs-audit"
  - "문서 점검"
  - "문서 종합 점검"
  - "문서 링크 점검"
  - "문서 링크 감사"
  - "문서 연결 확인"
  - "문서 관계 파악"
  - "링크 정리"
  - "링크 상태"
  - "broken link"
  - "orphan doc"
  - "cross-link"
  - "가시성 점검"
  - "README 정합성"
  - "전체 문서 검토"
quality: high
---

# 문서 종합 감사 (docs-audit)

## The Insight

fos-study 는 마크다운 저장소이고 fos-blog 가 `resolveMarkdownLink()` 로 상대·절대 경로를 블로그 URL 로 변환한다. 그러므로 **"링크로 적힌 것은 자동으로 연결되지만, 백틱·일반 문장으로 적힌 경로는 그대로 문자열로 남는다"**. 동시에 시간이 지나면 글이 늘면서 가시성·문체·README 정합성도 어긋나기 시작한다. 이 스킬은 그걸 주기적으로 통합 감사한다.

이전에는 `docs-link-audit` 으로 링크만 보았으나, 이제 7개 축을 한 번의 호출로 본다.

| # | 축 | 분류 | 실행 위치 |
|---|---|---|---|
| 1 | Unlinked path mention | 링크 | 메인 직접 |
| 2 | Broken link | 링크 | 메인 직접 |
| 3 | Orphan doc | 링크 | sub-agent 위임 |
| 4 | Cross-link 제안 | 링크 | sub-agent 위임 |
| 5 | 가시성·스캔 가능성 | 가독성 | 메인 직접 |
| 6 | 문체 정적 검사 | 가독성 | 메인 직접 |
| 7 | README ↔ 실제 파일 정합성 | 구조 | sub-agent 위임 |

**Hybrid 실행 모델** — 가벼운 정적 검사 4개(1, 2, 5, 6) 는 메인이 직접 ripgrep+python 으로 처리한다. 무거운 의미 검사 3개(3, 4, 7) 는 Agent 도구로 sub-agent 에 병렬 위임해 메인 컨텍스트를 보호한다.

## Recognition Pattern

사용자가 아래 중 하나라도 말하면 이 스킬을 실행한다.

- "문서 감사 돌려줘", "docs-audit", "전체 문서 점검"
- "문서 링크 점검해줘", "broken link 있는지 확인", "orphan 문서 찾아줘"
- "서로 링크 걸면 좋은 문서 있나"
- "가시성 점검해줘", "README 정합성 확인"
- 슬래시 호출: `/docs-audit`, `/docs-link-audit` (구 이름도 인식)

## 실행 순서

### 0. 사전 체크

```bash
pwd  # /Users/nhn/personal/fos-study
```

`fos-blog/src/lib/resolve-markdown-link.ts` 가 지원하는 경로 형태:

- 절대경로: `/java/spring-batch/post.md` → `/posts/java/spring-batch/post.md`
- 상대경로: `./other.md`, `../category/post.md`
- 앵커: `post.md#section`

### Step A — 메인 직접 검사 (축 1, 2, 5, 6)

가벼운 정적 검사를 메인 세션에서 한 번에 돌린다. ripgrep / Python 한 번이면 끝나고 결과도 작아 메인 컨텍스트 부담이 거의 없다.

#### 축 1. Unlinked path mention

**정의** — 본문에 `경로/파일.md` 형태가 등장하지만 `[...](...)` 링크 안에 있지 않음.

**ripgrep 패턴**:

```
pattern: `\`[a-zA-Z0-9_./\-]+\.mdx?\``       # 백틱 안의 .md 경로
pattern: `(?:[a-z0-9\-]+/)+[a-z0-9\-]+\.mdx?`  # 백틱 없이 본문에 등장한 경로
```

매치 줄에서 그 경로가 이미 `](path)` 형태로 감싸여 있으면 제외한다. **추가 마스킹** — `[\`path\`](path)` 형태처럼 백틱 경로가 마크다운 링크의 표시 텍스트인 경우도 false positive 다 (실측 확인됨). 다음 패턴으로 사전 제거:

```python
# 백틱이 link 표시 텍스트인 경우 제거
text = re.sub(r'\[`[^`]+`\]\([^)]+\)', '', text)
```

**수정 제안 형식**:

- 같은 폴더 파일: `[짧은 제목](./file.md)`
- 다른 폴더 파일: `[제목](../folder/file.md)` 또는 절대경로 `[제목](/folder/file.md)`
- 섹션 참조: `[제목 N장](./file.md#섹션-앵커)` (앵커는 heading 의 kebab-case)

#### 축 2. Broken link

**정의** — `[text](target)` 안의 `target` 이 실제 파일이 아닌 경우.

**절차**:

```
pattern: `\]\(([^)]+\.mdx?(?:#[^)]*)?)\)`
```

추출한 각 링크에 대해:

1. `#앵커` 제거
2. 상대경로면 현재 파일 디렉터리 기준 해석, 절대경로면 저장소 루트 기준
3. `Path(...).exists()` 로 존재 확인
4. 없으면 보고 + "가까운 파일명" 후보 제시 (Levenshtein 또는 prefix 일치)

#### 축 5. 가시성·스캔 가능성

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

#### 축 6. 문체 정적 검사

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

**자동 수정 가능** — 명확한 룰이라 LLM 검토 후 일괄 Edit OK. 단 `~` 는 의도적 범위 표기일 수도 있어 paragraph 컨텍스트 보고 결정.

### Step B — Sub-agent 위임 검사 (축 3, 4, 7)

무거운 의미 검사 3개를 **전용 sub-agent 로 동시 fork** 한다. 각 agent 는 별도 정의 파일로 관리되며 (`fos-study/.claude/agents/`), Agent 도구의 `subagent_type` 으로 호출한다. 한 번에 multiple Agent 호출을 하나의 메시지에 묶어 병렬 실행.

#### 호출 형식

| 축 | subagent_type | 정의 파일 |
|---|---|---|
| 3. Orphan | `orphan-doc-auditor` | `.claude/agents/orphan-doc-auditor.md` |
| 4. Cross-link | `cross-link-auditor` | `.claude/agents/cross-link-auditor.md` |
| 7. README 정합성 | `readme-integrity-auditor` | `.claude/agents/readme-integrity-auditor.md` |

#### 표준 schema (모든 agent 공통)

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

#### 호출 시 프롬프트 (간단)

각 agent 정의 파일에 system prompt 가 박혀 있으므로 호출 시 프롬프트는 **간단한 task 트리거**만 필요하다.

> "fos-study 저장소를 검사하고 표준 YAML schema 로 결과를 반환해라."

#### 메인의 책임

- 3 agent 를 한 메시지에 multiple Agent tool calls 로 동시 fork (`run_in_background: true` 권장)
- 결과 도착 시 schema 검증 (axis / findings / total 필드 존재)
- spot-check 3건 정도 sampling 해 정확성 검증 (agent 의 보고는 의도이지 실측이 아닐 수 있음)
- 통합 리포트의 해당 축 채우기

### Step C — 결과 통합 + 리포트

메인 세션이 sub-agent 3개의 결과를 받아 직접 검사 결과 4개와 합쳐 단일 리포트로 출력. 표준 schema 덕분에 통합이 단순.

## 리포트 형식

화면에만 표시(파일 생성 금지 — 사용자가 명시 요청 시에만).

```markdown
# 문서 종합 감사 리포트 — YYYY-MM-DD

## 요약 (우선순위순)
- Broken link: N건                    [높음]
- README 정합성 위반: N건             [높음]
- Orphan doc: N건                     [중간]
- Unlinked path mention: N건          [중간]
- 문체 정적 위반: N건                 [중간]
- 가시성 점검 후보: N건               [낮음 — 후보만]
- Cross-link 제안: N건                [낮음 — 후보만]

## 1. Broken link
| 파일 | 줄 | 링크 | 상태 |
|---|---|---|---|
| AI/rag.md | 44 | `./embedding.md` | 파일 없음 (가까운: `./embeddings.md`) |

## 2. README 정합성
| README | 패턴 | 대상 |
|---|---|---|
| task/sb-dev-team/README.md | 누락 | new-feature.md (폴더에 있으나 등재 X) |

## 3. Orphan doc
- `algorithm/foo.md` — 어느 문서에서도 참조되지 않음

## 4. Unlinked path mention
| 파일 | 줄 | 현재 | 제안 |
|---|---|---|---|
| database/mysql/foo.md | 12 | `` `database/mysql/bar.md` `` | `[Bar](./bar.md)` |

## 5. 문체 정적 위반
| 파일 | 줄 | 패턴 | 제안 |
|---|---|---|---|
| foo.md | 10 | `~` 취소선 위험 | `\~` 이스케이프 또는 `–` 로 변경 |

## 6. 가시성 점검 후보 (수동 판단)
| 파일 | 줄 | 패턴 | 제안 |
|---|---|---|---|
| foo.md | 70 | 콤마-줄글 7개 항목 | bullet 분리 |

## 7. Cross-link 제안 (수동 판단)
- `database/mysql/innodb-mvcc.md` ↔ `java/spring/jpa-transaction.md` — 양쪽이 "트랜잭션 격리" 언급, 상호 링크 없음
```

## 수정 적용 단계

1. 리포트 출력 후 **사용자에게 어떤 축을 수정할지 묻는다**. 축 단위 일괄 적용이 원칙
2. **자동 수정 가능 축**: Broken link, Unlinked path mention, 문체 정적 위반(축 6) — Edit 도구로 일괄 적용. 단 broken link 는 후보 제시 후 사용자가 최종 선택
3. **반자동 축**: README 정합성 — 누락 등재는 자동 추가 가능. 카테고리 재배치는 사용자 판단
4. **수동 축**: Orphan, Cross-link, 가시성 — 후보만 제시. 사용자가 직접 수정. Orphan 은 후보 위치(같은 폴더 README, 상위 인덱스) 만 제안
5. 변경 후 커밋 1개에 묶는다. 메시지 예:

   ```
   docs: 종합 감사 — broken N건 + 문체 N건 + README 정합성 N건 수정
   ```

## 안티패턴

- **앵커 자동 검증 시도** — heading-to-anchor 규칙은 렌더러마다 달라 완벽한 검증이 어렵다. 앵커 끊어짐은 단정하지 말고 "heading 텍스트와 앵커 문자열 불일치 가능성" 으로만 표시
- **경로만 보고 orphan 단정** — 코드 블록, 표, quote 안의 언급도 참조로 간주. 텍스트 문맥이 코드일 때도 검사 대상
- **대량 자동 수정** — 한 번에 100건 넘는 Edit 은 diff 를 사람이 따라갈 수 없다. 축 단위로 끊어 적용하고 중간 사용자 확인
- **외부 URL 포함 감사** — 이 스킬은 저장소 내부 링크만 대상. 외부 URL 유효성은 별도 작업
- **규모 과장** — 감사는 건전성 체크다. "저장소를 전부 재구성하자" 는 권고는 범위 이탈. 발견한 문제만 보고
- **Sub-agent 결과 신뢰 과다** — agent 의 보고는 의도이지 실측이 아닐 수 있음. 자동 수정 전 메인이 spot-check (3건 정도 샘플) 로 정확성 검증
- **html / pdf / 이미지 파일을 마크다운 링크로 걸기** — fos-blog 의 `resolveMarkdownLink()` 는 `.md` 와 `.mdx` 만 처리. `.html`, `.pdf`, `.png` 같은 비-md 파일을 `[text](path.html)` 형태로 걸면 blog 렌더링 시 깨지거나 잘못된 URL 로 변환됨. 이런 파일은 **텍스트 참조** (백틱 또는 일반 텍스트) 로 위치만 표시: `` `resume/cj-foodville-resume-backend.html` `` 형태. 수정 적용 시 unlinked path mention 자동 링크화 스크립트가 비-md 확장자를 건드리지 않도록 패턴 제한 필수
- **자동 변환 스크립트의 중첩 백틱·링크 손상** — `\`path\`` 형태를 `[\`path\`](path)` 로 치환할 때 이미 nested 한 케이스 (`\`path1[..](path2)\``) 가 있으면 결과가 망가짐. 변환 전 paragraph 단위로 정상성 확인, 또는 정규식에서 nested 명확히 제외

## 주기

월 1회 또는 큰 문서 batch 작업 후 1회 수동 실행 권장. 자동화(cron/hook) 는 현 시점에서 불필요.

## 참고

- 블로그 링크 렌더러: `/Users/nhn/personal/fos-blog/src/lib/resolve-markdown-link.ts`
- 저장소 컨벤션: `/Users/nhn/personal/fos-study/CLAUDE.md` "하위 문서 링크" / "가시성 원칙" / "마크다운 Bold + 괄호 패턴"
- 문체 룰 출처: `.claude/skills/blog-post-writer/SKILL.md` 14-G/H/I/J 항목
