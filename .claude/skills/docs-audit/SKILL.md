---
id: workflow-docs-audit
name: docs-audit
description: fos-study 저장소 전체의 문서 건전성을 7개 축으로 종합 감사한다. (1) 백틱으로만 적힌 path mention, (2) broken link, (3) orphan doc, (4) cross-link 제안, (5) 가시성·스캔 가능성, (6) 문체 정적 검사 (`~` 취소선, `§` 사용, Bold+괄호 패턴), (7) README ↔ 실제 파일 정합성. Hybrid 실행 모델 — 가벼운 정적 검사는 메인이 직접, 무거운 의미 검사(orphan/cross-link/README 정합성)는 sub-agent 병렬 위임. "문서 감사", "docs-audit", "문서 점검", "문서 종합 점검", "문서 링크 점검", "broken link", "orphan doc", "cross-link", "가시성 점검", "README 정합성", "전체 문서 검토" 같은 요청 시 반드시 이 스킬 사용. 저장소를 한 번 훑어 통합 리포트를 만들고, 사용자 승인 후 축 단위로 수정한다. **추가로 Quality Loop 모드** — 7축 구조 감사와 별도로 *의미 품질* (유효성·중복도·역할 분명·학습/면접 가치·diff 실제 개선)을 검토하고 문서를 `keep / refresh-needed / merge / archive / delete-candidate` 5단계로 분류. 큰 정리 직후 또는 주기 품질 점검 시 명시 호출. Quality Loop는 기본 실행 아님 — `quality-loop`, `diff 검증`, `문서 품질 루프` 등 명시 호출 시에만 작동.
source: conversation
triggers:
  - "문서 감사"
  - "docs-audit"
  - "docs-link-audit"
  - "문서 점검"
  - "문서 종합 점검"
  - "문서 링크 점검"
  - "문서 링크 감사"
  - "문서 연결 확인"
  - "문서 건전성"
  - "링크 정리"
  - "링크 상태"
  - "링크 검사"
  - "링크 깨진 거"
  - "broken link"
  - "orphan doc"
  - "cross-link"
  - "가시성 점검"
  - "README 정합성"
  - "전체 문서 검토"
  - "문서 품질 검토"
  - "문서 품질 루프"
  - "문체 검사"
  - "quality-loop"
  - "diff-validation"
  - "diff 검증"
  - "주기 품질 점검"
quality: high
---

# 문서 종합 감사 (docs-audit)

## The Insight

fos-study 는 마크다운 저장소이고 fos-blog 가 `resolveMarkdownLink()` 로 상대·절대 경로를 블로그 URL 로 변환한다.
그러므로 **"링크로 적힌 것은 자동으로 연결되지만, 백틱·일반 문장으로 적힌 경로는 그대로 문자열로 남는다"**.
동시에 시간이 지나면 글이 늘면서 가시성·문체·README 정합성도 어긋나기 시작한다.
이 스킬은 그걸 주기적으로 통합 감사한다.

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

**Hybrid 실행 모델**:

- 가벼운 정적 검사 4개 (축 1, 2, 5, 6) — 메인이 직접 ripgrep+python 으로 처리
- 무거운 의미 검사 3개 (축 3, 4, 7) — Agent 도구로 sub-agent 에 병렬 위임해 메인 컨텍스트를 보호

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

가벼운 정적 검사를 메인 세션에서 한 번에 돌린다.
ripgrep / Python 한 번이면 끝나고 결과도 작아 메인 컨텍스트 부담이 거의 없다.

구현 상세 (ripgrep 패턴·Python 코드·시그널 기준·필터 목록): `references/axis-detail.md`.

#### 축 1. Unlinked path mention

본문에 `경로/파일.md` 형태가 등장하지만 `[...](...)` 링크 안에 있지 않음.
백틱 경로가 링크의 표시 텍스트인 경우 (`[\`path\`](path)`) 는 false positive — 마스킹 후 검사.

**자동 변환은 H1 제목 기반으로 한다** (백틱 경로 그대로 사용 금지):

1. `` `path.md` `` 발견 시 대상 파일 존재 확인
2. 대상 파일의 H1 추출 (`grep -m1 '^# ' <file>`)
3. H1 정리:
   - `^\[초안\]\s*` prefix 제거
   - ' — ', ': ', ' (' 중 첫 매치 앞부분만 사용 (긴 부제 제거)
   - 길이 40자 초과 시 `?` 또는 `.` 위치에서 잘라 한 문장으로
4. `[정리된 H1](path.md)` 형태로 치환

**이유** — `[\`path\`](path)` 형태는 markdown 으로 유효하지만 fos-blog 렌더링 시 백틱 + 경로가 그대로 노출돼 어색하다. 본문 한 줄에 link 3개가 모두 경로로 보이면 가독성이 급락한다. 표시 텍스트를 H1 제목으로 잡으면 자연스러운 문장이 된다.

**스크립트 참고**: `/tmp/relink_h1_v2.py` (이전 라운드 산출물). 62건/9파일 적용 사례.

#### 축 2. Broken link

`[text](target)` 안의 `target` 이 실제 파일이 아닌 경우.
`#앵커` 제거 후 상대/절대경로 기준으로 `Path.exists()` 확인.
없으면 Levenshtein 기준 "가까운 파일명" 후보 제시.

#### 축 5. 가시성·스캔 가능성

다음 4가지 패턴을 검사한다.

- 콤마-줄글 사례 단락
- 긴 인라인 부연
- 누적성 섹션 평탄화 부재
- 인라인 링크 폭주

코드/표 마스킹 후 시그널 강도 순 보고.
`interview/**`, `resume/**` 등 의도적 줄글 패턴은 제외.

**Detector 운영 노하우 (실전 라운드 반영)**:

- **node_modules / k8s-in-action 같은 외부 의존성 마스킹 필수**
  - 라이센스·라이브러리 README 가 콤마 8\~16회로 잡혀 신호를 묻는다.
  - `EXCLUDE_DIRS` 에 추가.

- **bullet list 안 sub-bullet 본문은 콤마 카운트에서 제외**
  - `1. 문제 재진술 ... 2. ...` 형태 narration 은 paragraph 자체는 bullet 인데 한 bullet 안 자연어가 콤마 7\~10회 등장.
  - `bullet_ct >= len(plines) * 0.5` 임계치로 보수적으로 컷.

- **`~` 짝수 카운트는 `\~` escape 인지 후 카운트**
  - 단순 `count('~')` 는 이미 escape 된 50건도 false positive 로 잡는다.
  - paragraph 마스킹 단계에서 `\~` 를 별도 sentinel 로 치환 후 카운트.

- **임계치는 5\~7 사이가 실용적**
  - 4회 콤마는 자연 산문에서도 흔함.
  - 첫 라운드는 7+ 로 강한 신호만 보고하고, 이후 라운드에서 5+ 로 내려서 잔여 검토.
  - 강한 신호는 거의 항상 enumeration 6\~8항목이라 bullet 분리 효과 큼.

- **수정 적용률 \~10%가 정상**
  - 첫 라운드 보고된 paragraph 중 실제 손볼 산문은 10건 중 1\~2건.
  - 나머지는 다음 셋 중 하나라 유지하는 게 맞다.
    - bullet list 내부 본문 카운트
    - 인라인 코드 마스킹 false positive
    - 도입부 자연 산문
  - 보고량에 압도되지 말 것.

#### 축 6. 문체 정적 검사

CLAUDE.md / blog-post-writer 룰 중 4가지를 본다.

1. `~` 취소선 함정 — paragraph 안에 unescaped `~` 짝수 개
2. `§` 특수문자 사용
3. `**텍스트(영문)**` 패턴 → `**텍스트**(영문)` 로 분리
4. `*한글(영문)*` 또는 `*영문(한글)*` 이탤릭+괄호 패턴 → **bold+괄호 분리** 로 교체
   - 예: `*격벽(bulkhead)*` → `**격벽**(bulkhead)`, `*연결성(connectivity)*` → `**연결성**(connectivity)`
   - GitHub Flavored Markdown / fos-blog 파서가 한글+괄호+`*` 조합에서 단어 경계 인식이 약해 이탤릭 렌더가 안 됨
   - 정규식: `re.compile(r'(?<!\*)\*([가-힣A-Za-z]+\([^)]+\))\*(?!\*)')`

자동 수정 가능.
단 `~` 는 의도적 범위 표기일 수도 있어 paragraph 컨텍스트를 보고 결정한다.

### Step B — Sub-agent 위임 검사 (축 3, 4, 7)

무거운 의미 검사 3개를 **전용 sub-agent 로 동시 fork** 한다.
한 번에 multiple Agent 호출을 하나의 메시지에 묶어 병렬 실행.

| 축 | subagent_type | 정의 파일 |
|---|---|---|
| 3. Orphan | `orphan-doc-auditor` | `.claude/agents/orphan-doc-auditor.md` |
| 4. Cross-link | `cross-link-auditor` | `.claude/agents/cross-link-auditor.md` |
| 7. README 정합성 | `readme-integrity-auditor` | `.claude/agents/readme-integrity-auditor.md` |

반환 YAML schema 상세: `references/axis-detail.md` Step B 항목.

#### 메인의 책임

- 3 agent 를 한 메시지에 multiple Agent tool calls 로 동시 fork (`run_in_background: true` 권장)
- 결과 도착 시 schema 검증 (axis / findings / total 필드 존재)
- spot-check 3건 정도 sampling 해 정확성 검증 (agent 의 보고는 의도이지 실측이 아닐 수 있음)
- 통합 리포트의 해당 축 채우기

### Step C — 결과 통합 + 리포트

메인 세션이 sub-agent 3개의 결과를 받아 직접 검사 결과 4개와 합쳐 단일 리포트로 출력.

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

1. **사용자에게 어떤 축을 수정할지 묻는다** — 축 단위 일괄 적용이 원칙.
2. **자동 수정 가능 축** — Broken link, Unlinked path mention, 문체 정적 위반 (축 6).
   - Edit 도구로 일괄 적용.
   - 단 broken link 는 후보 제시 후 사용자가 최종 선택.
3. **반자동 축** — README 정합성.
   - 누락 등재는 자동 추가 가능.
   - 카테고리 재배치는 사용자 판단.
4. **수동 축** — Orphan, Cross-link, 가시성.
   - 후보만 제시.
   - 사용자가 직접 수정.
   - Orphan 은 후보 위치 (같은 폴더 README, 상위 인덱스) 만 제안.
5. 변경 후 **관심사별 커밋으로 분리** (한 커밋에 합치지 않음). 메시지 예:

   ```
   docs: 종합 감사 — broken N건 + 문체 N건 + README 정합성 N건 수정
   ```

## Quality Loop — 의미 품질 검토 (수동 판단 후보 확장)

7축 정적 감사는 *구조 정합성*을 본다.
Quality Loop는 *의미 품질*을 본다.
사용자가 "큰 정리 직후 검토" 또는 "주기 품질 점검" 요청 시 추가 실행.
단순 docs-audit 호출 시에는 실행 안 함 (명시 호출 모드).

### 트리거

다음 중 하나면 Quality Loop 모드를 켠다.

- "최근 mysql 정리 diff 기준으로 실제로 좋아졌는지 봐줘"
- "spring 문서 품질 평가해줘"
- "문서 품질 검토", "diff 검증", "quality-loop"
- "최근 생성 문서 N개 품질 점검"
- 슬래시 호출: `/docs-audit quality-loop`

### 6 검사 축 (의미)

| # | 축 | 내용 |
|---|---|---|
| Q1 | 유효성 | 문서가 지금도 유효한가 (옛 가정·룰·코드가 바뀌어 본문이 깨졌는가) |
| Q2 | 중복도 | 다른 문서와 *본질적* 중복이 큰가 (허브-심화 역할 분명하면 중복 X) |
| Q3 | 역할 분명함 | 허브 / 심화 / 사례 / 레퍼런스 역할이 명확한가 |
| Q4 | 링크 자연스러움 | 관련 문서로 자연스럽게 이어지는가 (Step B 축 4 cross-link 와 다른 의미: 의미 흐름) |
| Q5 | 학습·면접 가치 | 실무 학습 가치와 면접 가치가 있는가 |
| Q6 | diff 품질 (writer/maintainer 직후) | 최근 diff가 실제 개선인지, 단지 문장을 옮긴 것인지 |

Q6는 *writer/maintainer 사이클 직후* (예: study-pack-writer 호출 후 또는 큰 정리 commit 후) 특별히 활성. git diff 기준 판단.

### 분류 라벨 (각 문서에 1개 부여)

| 라벨 | 의미 | 다음 동작 |
|---|---|---|
| `keep` | 그대로 유지 | 변경 없음 |
| `refresh-needed` | 내용은 유효하지만 현재 품질 기준 미달 | 다음 사이클에 갱신 후보 (즉시 X) |
| `merge` | 다른 문서와 통합 권장 | 통합 대상 명시 + 사용자 검토 |
| `archive` | 가치는 있지만 최신성 떨어짐 | archive 영역 이동 (즉시 삭제 X) |
| `delete-candidate` | 즉시 삭제 후보 | 사용자 최종 확인 후 삭제 |

### 추천 사용 시점

1. **문서가 꽤 쌓였을 때** — 예: `mysql` 문서군 구조가 복잡해졌을 때, `spring` 문서군이 횡단 관심사·트랜잭션·JPA 축으로 늘어났을 때
2. **Claude maintainer / writer가 큰 정리를 한 직후** — 반드시 diff-validation 모드로 본다 (Q6 축 활성). git diff 기준 *실제 개선인지 문장만 옮긴 건지* 판단
3. **주기 점검** — 최근 생성 문서 2-5개 또는 특정 폴더 하나 골라 품질 점검

### 운영 원칙

- 바로 삭제하지 않는다 — 5 분류 라벨로 먼저 분류
- 최근 문서는 공격적으로 정리하지 않는다 — `refresh-needed` 보수적 적용
- 허브와 심화 문서는 역할 분명하면 *중복으로 간주하지 않는다* — Q2 판단 시 Q3 우선

### 확인된 패턴 (참고)

- MySQL 인덱스 문서군은 허브 + 심화 분리가 실제로 품질 개선 효과가 있었다
- 오래된 학습 노트는 내용이 유효해도 현재 품질 기준에서는 `refresh-needed`로 판정될 수 있다
- README / 허브 문서가 있으면 새 문서가 늘어도 역할 충돌을 줄이기 쉽다

### Quality Loop 리포트 형식 (7축 리포트 뒤 추가 섹션)

```markdown
## Quality Loop — 의미 품질 (수동 판단)

### 분류 요약
- keep: N건
- refresh-needed: N건
- merge: N건 (통합 대상 명시)
- archive: N건
- delete-candidate: N건

### 분류 상세
| 파일 | 라벨 | 근거 (Q1~Q6 어느 축) | 다음 동작 |
|---|---|---|---|
| database/mysql/foo.md | refresh-needed | Q1 (옛 룰 기준), Q5 (면접 가치 약함) | 다음 사이클 |
| algorithm/legacy-bar.md | delete-candidate | Q1 (가정 무효), Q5 (학습 가치 없음) | 사용자 확인 후 삭제 |

### diff-validation (Q6, writer/maintainer 직후만)
- 대상 commit / diff 범위: <hash 또는 path>
- 판정: 실제 개선 / 단지 문장 옮김 / 부분 개선
- 근거: <짧은 코멘트>
```

## 안티패턴

- **앵커 자동 검증 시도** — heading-to-anchor 규칙은 렌더러마다 달라 완벽한 검증이 어렵다. 앵커 끊어짐은 단정하지 말고 "heading 텍스트와 앵커 문자열 불일치 가능성" 으로만 표시
- **경로만 보고 orphan 단정** — 코드 블록, 표, quote 안의 언급도 참조로 간주. 텍스트 문맥이 코드일 때도 검사 대상
- **대량 자동 수정** — 한 번에 100건 넘는 Edit 은 diff 를 사람이 따라갈 수 없다. 축 단위로 끊어 적용하고 중간 사용자 확인
- **외부 URL 포함 감사** — 이 스킬은 저장소 내부 링크만 대상. 외부 URL 유효성은 별도 작업
- **규모 과장** — 감사는 건전성 체크다. "저장소를 전부 재구성하자" 는 권고는 범위 이탈. 발견한 문제만 보고
- **Sub-agent 결과 신뢰 과다** — agent 의 보고는 의도이지 실측이 아닐 수 있음. 자동 수정 전 메인이 spot-check (3건 정도 샘플) 로 정확성 검증
- **html / pdf / 이미지 파일을 마크다운 링크로 걸기**
  - fos-blog 의 `resolveMarkdownLink()` 는 `.md` 와 `.mdx` 만 처리.
  - `.html`, `.pdf`, `.png` 같은 비-md 파일을 `[text](path.html)` 형태로 걸면 blog 렌더링 시 깨지거나 잘못된 URL 로 변환됨.
  - 이런 파일은 **텍스트 참조** (백틱 또는 일반 텍스트) 로 위치만 표시.
  - 수정 적용 시 unlinked path mention 자동 링크화 스크립트가 비-md 확장자를 건드리지 않도록 패턴 제한 필수.

- **자동 변환 스크립트의 중첩 백틱·링크 손상**
  - `` `path` `` 형태를 `[\`path\`](path)` 로 치환할 때 이미 nested 한 케이스 (`\`path1[..](path2)\``) 가 있으면 결과가 망가짐.
  - 변환 전 paragraph 단위로 정상성 확인, 또는 정규식에서 nested 명확히 제외.
  - **한 줄 중복 path 함정** — 한 줄에 같은 백틱 path 가 두 번 등장하면 `new_line.replace(m.group(0), repl, 1)` 가 두 번째 iteration 에서 이미 변환된 자리를 다시 잡아 `[[\`X\`](X)](X)` 식으로 다중 nest 가 생긴다.
  - 한 line 내 동일 backtick path 가 2회 이상 등장하면 그 line 은 자동 변환 skip, 사람 수정 권고로 보고.

- **`~` 자동 escape 시 shell home path 오인**
  - 축 6의 `~` 취소선 자동 escape 를 돌릴 때 `~/.dooray/config.json`, `mkdir -p ~/livecoding/tree` 같은 **shell home path** 까지 `\~/...` 로 escape 해버리면 본문이 깨진다.
  - 사전 필터:
    - `~/` 뒤에 영문/`.` 으로 이어지는 path 형태 (`~/foo`, `~/.dooray`) 는 home path 후보 → escape 제외
    - 코드 블록 / 인라인 코드 안의 `~` 는 항상 마스킹 (이미 적용 중)
    - 보수적으로 `숫자~숫자`, `날짜~날짜`, `한글~한글` 같이 **양쪽이 같은 종류 token** 일 때만 escape. 한쪽이 path token 이면 skip.
  - 자동 적용 후 diff 검사:
    - ` ``` ` 펜스 안 라인이 변경됐는가
    - path token (`/`, `.`) 이 포함된 라인이 변경됐는가
    - 둘 중 하나라도 yes 면 그 파일만 즉시 revert

- **bold-paren 자동 분리는 nested 괄호·메서드명·코드 인용을 깬다**
  - `**텍스트(영문)**` → `**텍스트**(영문)` 변환을 무차별 적용하면 다음 케이스가 깨진다.
  - **nested 괄호 bold** — `**Slot 47 (웨이(243) + Sync Reel)**` 처럼 bold 본문에 괄호가 2회 이상이면 마지막 `(` 기준 분리가 잘못된 위치를 자른다.
    - 사전 필터: bold 본문에 `(` 또는 `)` 가 2회 이상 등장하면 skip.
  - **메서드명 bold** — `**doOpen()**`, `**update()**`, `**canRetry()**` 같은 메서드 시그니처는 CLAUDE.md 룰상 코드 인라인 (`` `doOpen()` ``) 으로 바꿔야 한다. `**doOpen**()` 로 분리하면 더 어색.
    - 사전 필터: 괄호 안이 비어 있거나 `()` 패턴이면 skip. 별도 round 에서 backtick 화 제안만.
  - **예외 파일** — `CLAUDE.md`, `*claude-code-usage-reflection*.md`, `*blog-post-writer*.md` 같이 룰 자체를 인용·예시로 보여주는 문서는 의도적 위반 형태가 정답.
    - skip 리스트로 관리하고 새 위반 문서 생길 때마다 추가.
  - **사후 검증** — 변환 후 diff 에서 코드 블록 (` ``` ` 펜스, 인라인 ` `` `) 안이 건드려졌으면 즉시 그 파일만 revert.

- **잘못된 자동 변환 발견 시 부분 revert 흐름**
  - 자동 변환을 적용한 뒤 spot-check 단계에서 한 파일에서 손상을 발견하면 그 파일만 `git checkout -- <path>` 로 revert 한다.
  - 전체 stage 를 reset 하지 말 것.
  - 변환 함수는 그대로 두고 다음 round 에서 입력 필터만 강화한다.
  - 본 스킬 적용 사례에서 7개 파일 revert + 13개 파일 유지가 가장 깔끔했다.

## 주기

월 1회 또는 큰 문서 batch 작업 후 1회 수동 실행 권장. 자동화(cron/hook) 는 현 시점에서 불필요.

## 참고

- 블로그 링크 렌더러: `/Users/nhn/personal/fos-blog/src/lib/resolve-markdown-link.ts`
- 저장소 컨벤션: `/Users/nhn/personal/fos-study/CLAUDE.md` "하위 문서 링크" / "가시성 원칙" / "마크다운 Bold + 괄호 패턴"
- 문체 룰 출처: `.claude/skills/blog-post-writer/SKILL.md` 14-G/H/I/J 항목
- 축별 구현 상세 (ripgrep·Python 코드·YAML schema): `references/axis-detail.md`
