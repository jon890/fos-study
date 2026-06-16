---
id: workflow-blog-post-writer
name: blog-post-writer
description: 업무 경험이나 기술 스터디 내용을 개인 블로그 마크다운 포스팅으로 변환해 /Users/nhn/personal/fos-study에 저장. "블로그 포스팅", "블로그 글 써줘", "블로그에 정리", "TIL", "기술 블로그", "개발 블로그", "개발 정리", "blog post", "fos-study", "업무 내용 블로그", "이력 문서", "포트폴리오 정리", "작업 정리", "스터디 정리", "공부한 거 정리", "개념 정리해줘" 같은 요청 시 반드시 이 스킬 사용. 업무 경험은 git log 기반 기여 범위 파악 후 민감 정보 제거, 외부 기술 스터디는 WebSearch로 정보 수집 후 작성. 사용자가 이메일/문서/채팅에서 기술 내용을 공유하며 블로그 글을 요청하는 경우도 포함. 개인 블로그 글(업무 회고 포함, 회사/팀명 표기 가능)이 대상이며, career-os 이직·면접 준비용 비공개 학습팩(회사명 비표기)은 career-os study-pack-writer로 라우팅한다.
source: conversation
triggers:
  - "블로그 포스팅"
  - "블로그 글 써줘"
  - "블로그에 정리"
  - "blog post"
  - "fos-study"
  - "업무 내용 블로그"
  - "TIL"
  - "기술 블로그"
  - "개발 블로그"
  - "개발 정리"
  - "이력 문서"
  - "포트폴리오 정리"
  - "작업 정리"
  - "스터디 정리"
  - "공부한 거 정리"
  - "개념 정리해줘"
  - "블로그 글 작성"
quality: high
---

# 업무 내용 → 개인 블로그 포스팅 변환

## The Insight

업무에서 다룬 기술 내용을 블로그 글로 정리할 때 핵심은 다섯 가지다:
1. **본인 기여만 작성** — 팀 전체 업무가 아닌 git 커밋 기반으로 본인이 직접 한 것만
2. **공개 가능 수위(L2) 준수** — 회사명/팀명은 OK, 비즈니스 도메인 고유 클래스명과 사업 의사결정은 X (세부 기준은 publishing-policy 참조)
3. **자연스러운 문체** — AI 티 나지 않게, 직접 삽질하며 배운 사람의 말투로
4. **코드 흐름은 의사코드·구조 중심으로** — 실제 프로젝트 코드 전체 인용이 아니라 패턴과 구조를 보여주는 수준
5. **회고와 협업을 드러내기** — 기술 결정 + 내가 무엇을 했나 + 팀원들과 어떻게 합을 맞췄나

블로그는 GitHub MD 파일 → 자동 sync 방식이라 파일만 올바른 위치에 만들면 된다.

## Recognition Pattern

- "블로그에 정리해줘", "블로그 포스팅 만들어줘" 요청
- 업무/작업 내용을 개인 이력이나 블로그 글로 남기고 싶을 때
- 기술 주제: DevOps, K8s, Spring Batch, DB, 트러블슈팅 등
- 특정 git 저장소나 작업 내역을 기반으로 글을 쓰고 싶을 때

## 참조 문서 (progressive disclosure)

상세 규칙은 단계별로 아래 references 를 연다:

- **[publishing-policy](./references/publishing-policy.md)** — 공개 수위(L2)·코드 인용(L1/L2/L3)·파일명·기술 스택 L2 정책. **케이스 A(업무 글)에 필수.**
- **[writing-style](./references/writing-style.md)** — 문체·서사·회고/협업·얕은 주제 배제·코드 검증·글 구성 규칙. 본문 작성 단계에서 참조.
- **[markdown-pitfalls](./references/markdown-pitfalls.md)** — 마크다운 렌더 함정과 cross-link 규칙, **작성 직후 통합 자가점검 체크리스트**.

## The Approach

### 0. 기여 범위 먼저 파악 (팀 프로젝트일 경우 필수)

팀 프로젝트를 블로그로 정리할 때 가장 중요한 첫 단계다. **내가 실제로 한 것만 써야 한다.**

```bash
# git config에서 author 이름 먼저 확인 (글로벌과 로컬이 다를 수 있음)
git config user.name
git config user.email

# 회사 프로젝트는 회사 이메일/한글 이름으로 커밋된 경우가 많음 — 양쪽 모두 확인
git log --format="%an <%ae>" | sort -u | head -20

# 본인 커밋만 필터링 (여러 표기가 있으면 OR로)
git log --author="bifos\|김병태" --oneline | head -30

# 진행 기간 추출
git log --author="bifos\|김병태" --format="%ad" --date=short | tail -1  # 시작
git log --author="bifos\|김병태" --format="%ad" --date=short | head -1  # 종료

# 특정 주제 관련 커밋만 필터링
git log --author="bifos\|김병태" --oneline --grep="키워드" -i
```

이 결과를 바탕으로 블로그 내용을 구성한다. 다른 팀원이 한 작업은 포함하지 않는다.

### 1. 폴더 구조 파악

```bash
ls /Users/nhn/personal/fos-study/
```

```
/Users/nhn/personal/fos-study/
├── task/           # 회사 업무/프로젝트 관련 포스팅
│   └── <팀명>/    # 예: ai-service-team, nsc-slot, sb-dev-team
├── devops/
│   ├── docker/
│   ├── k8s/
│   └── monitoring/
├── database/
├── java/
│   └── spring-batch/   # Spring Batch 상세 개념 문서들
├── network/
...
```

**저장 위치 결정 기준:**
- **회사 프로젝트 작업기**: `task/<팀명>/<파일명>.md`
- **기술 개념/튜토리얼**: 해당 기술 폴더 — 예: `java/spring-batch/step-scope.md`
- **트러블슈팅**: 해당 기술 폴더 또는 `task/`

### 2. 문서 헤더 — 진행 기간 포함

회사 프로젝트 작업기라면 문서 상단에 진행 기간을 반드시 포함한다.

```markdown
# 제목

**진행 기간**: 2026.01 ~ 2026.03

본문 시작...
```

git log에서 추출한 첫 커밋/마지막 커밋 날짜를 `YYYY.MM` 형식으로 기재한다. git 정보 없이 작성 요청이 오면 사용자에게 진행 기간을 물어본 뒤 기재한다. 추측해서 쓰지 않는다.

### 공개 수위·코드 인용·파일명 정책

공개 수위(L2)·코드 인용(L1/L2/L3)·파일명·기술 스택 L2 정책은 [publishing-policy](./references/publishing-policy.md) 참조 (케이스 A 업무 글에 필수).

### 문체·서사·글 구성

문체·서사·회고/협업·얕은 주제 배제·코드 예시 검증·글 구성 규칙은 [writing-style](./references/writing-style.md) 참조.

### 마크다운 함정·cross-link·자가점검

마크다운 렌더 함정과 cross-link 규칙, **작성 직후 자가점검 체크리스트**는 [markdown-pitfalls](./references/markdown-pitfalls.md) 참조.

### 13. 외부 개념/방법론 스터디 글 — 웹 자료 참고

업무 경험 기록이 아닌 **외부 기술/방법론을 공부한 내용**을 글로 쓸 때는 웹 검색으로 정확한 정보를 먼저 수집한다.

**적용 케이스:**
- 새로운 방법론, 프레임워크, 오픈소스 프로젝트 스터디 기록
- git 커밋이 없는 주제 (본인 코드베이스 없음)
- "공부해야 한다", "스터디", "개념 정리" 같은 맥락

**웹 검색 방식:**
```
# 1. 공식 소스부터 확인
WebSearch: "<기술명> official documentation site:github.com OR site:docs.*"

# 2. 실용적인 적용 사례 검색
WebSearch: "<기술명> how it works workflow agents 2025"

# 3. 한계/비판적 시각도 포함
WebSearch: "<기술명> limitations tradeoffs when to use"
```

**웹 자료 활용 규칙:**
- 공식 GitHub/공식 docs를 1순위로 참고
- 블로그 글은 여러 소스를 교차 검증 후 사용
- 글 하단에 **참고 링크 섹션** 반드시 포함 (URL 명시)
- 검색 결과를 그대로 번역하지 않는다 — 핵심만 추려서 본인 언어로 재해석

**저장 위치:** 개인 경험이 없는 순수 개념 스터디는 `task/` 가 아닌 해당 기술 폴더에 저장
- 예: AI 방법론 → `AI/bmad-method.md`
- 예: 새 DB 기술 → `database/<기술명>.md`

### 기존 짧은 글 보강 — 통합보다 보충이 기본

기존 글이 짧다고 **통합(삭제)부터 하지 않는다.** 짧은 글에도 다른 글에 없는 고유 내용(고유 비유, 특정 개념, YAML 예시, 운영 디테일)이 있을 수 있고, 삭제하면 그게 사라진다.

판단 순서:

1. **고유 내용 점검** — 이 글이 가진 것 중 다른(특히 상위/신규) 글에 없는 게 무엇인가.
2. **고유 내용이 있으면 → 보충**. 케이스 B(외부 개념)처럼 `WebSearch` 로 공식 자료를 수집해 다른 글 수준까지 채운다. 그리고 관련 글과 cross-link 로 시리즈를 엮는다. 단 신규 글과 **중복되지 않게 역할을 가른다**(예: `helm.md`=Helm 자체 구조·명령어, `helm-argocd-gitops.md`=GitOps 맥락).
3. **고유 내용이 거의 없고 상위 글에 포함되면 → 통합**. 짧은 글의 고유 비유·예시를 상위 글로 흡수한 뒤 삭제하고, 그 글을 링크하던 **모든 파일의 경로를 갱신**한다(`grep -rn "<파일명>"` 로 누락 점검). 삭제 후 README 도 갱신한다.

통합·삭제는 사용자에게 방향을 확인하고 진행한다(고유 내용 손실 위험).

## 작성 직전 중복 판정 (4-decision)

새 파일을 만들기 전에 fos-study 전역과의 중복을 판정한다.
같은 fos-study에 쓰는 career-os study-pack-writer의 ADR-033 중복 가드와 같은 4-decision 패턴이며, 위 "기존 짧은 글 보강 — 통합보다 보충" 원칙을 결정 게이트로 형식화한 것이다.

판정 입력 — Cross-link 후보 발굴(케이스 A 7-A / 케이스 B 3-A)에서 이미 `rg -l` 로 글 키워드 전역 검색을 했다. 그 매치 중 같은 주제를 다루는 문서를 후보로 본다.

| decision | 조건 | 동작 |
|---|---|---|
| `new` | 같은 주제 문서 없음 | 새 파일 작성으로 진행 |
| `update-existing` | 같은 주제 문서가 이미 있음 | 새 파일 만들지 말고 기존 문서를 보충(누락·약한 항목만 patch). "통합보다 보충" 원칙 적용 |
| `skip` | 기존 문서가 이미 충분 | 작성 중단, 기존 문서 경로를 사용자에게 안내 |
| `needs-confirmation` | 판정 모호(부분 중복, 역할 분담 애매) | 사용자에게 방향 확인 후 진행 |

안전 기본값 — 판정이 모호하면 `new`로 기울지 않고 **`needs-confirmation`** 으로 분류한다.
silent 새 파일 생성이 같은 주제 문서를 단편화시키는 것을 막는 핵심 기본값이다.

## 실행 단계

### Step 0. 케이스 판단 (필수)

먼저 어떤 유형인지 판단한다:

| 판단 기준 | 케이스 |
|---|---|
| 본인이 직접 구현/작업한 코드가 있음, git 커밋 추적 가능 | → **A. 업무 경험 기록** |
| 외부 기술/방법론/개념을 공부한 내용, 코드베이스 없음 | → **B. 스터디/개념 정리** |

애매할 때는 "이게 본인 코드인가요, 아니면 외부 기술을 공부한 건가요?"를 먼저 물어본다.

---

### A. 업무 경험 기록 (git 커밋 있음)

1. **기여 정도 파악** — "엄청 기여한 건 아닌데" 맥락이면 탐구/기록 톤 ([writing-style](./references/writing-style.md))
2. **git log로 본인 커밋만 필터링** (author 이름 여러 표기 고려) → 기여 범위 및 진행 기간
3. **얕은 주제 배제 판단** ([writing-style](./references/writing-style.md)) — 커밋 수 5\~6개 이하 + 클래식한 결론 + 재사용 인사이트 부족 시 배제/후순위 후 사용자 동의
4. **코드 검증** — 클래스명, 메서드명, 필드명을 코드에서 Read/Grep으로 직접 확인 ([writing-style](./references/writing-style.md) 코드 예시 검증)
5. `ls /Users/nhn/personal/fos-study/`로 폴더 구조 확인 → 적절한 위치 결정
6. **L2 공개 수위 점검** ([publishing-policy](./references/publishing-policy.md)) — 비즈니스 도메인 고유 클래스명 / 상품명 / 사업 의사결정 일반화
7. 관련 상세 문서 존재 여부 확인 → 링크 결정 (존재 검증 필수)
7-A. **Cross-link 후보 발굴** ([markdown-pitfalls](./references/markdown-pitfalls.md)) — 글 키워드 5\~10개 추출 → `rg -l` 로 전역 grep → H1 추출 → 본문 흐름상 자연스러운 자리 1\~2건만 선정. 표시 텍스트는 H1 제목, 깊은 link 면 앵커, 이탤릭+괄호 강조는 bold+괄호.
7-B. **중복 판정** ([작성 직전 중복 판정](#작성-직전-중복-판정-4-decision)) — 7-A 매치 중 같은 주제 문서가 있으면 new / update-existing / skip / needs-confirmation으로 판정. 모호하면 needs-confirmation(사용자 확인).
8. 마크다운 작성 — 자연스러운 문체, AI 티 제거, 1인칭 단수, **"내 기여 + 협업 방식 + 짧은 회고"** 섹션 포함
9. **글 자가 점검** — 작성 직후 [markdown-pitfalls](./references/markdown-pitfalls.md) 의 "작성 직후 통합 자가점검 체크리스트"를 순서대로 전부 실행한다. 하나도 건너뛰지 않는다. **정적 위반은 `scripts/blog_score.py <글>` 로 한 번에 측정한다** ([1계층 reward](#자가점검-자동화--blog_score-1계층-reward)).
10. 파일 저장 (파일명도 L2 적용) 후 경로 알려주기

---

### B. 스터디/개념 정리 (외부 기술, git 커밋 없음)

1. **WebSearch로 정보 수집** — 공식 docs/GitHub → 실용 사례 → 한계/비판 순으로 검색
2. `ls /Users/nhn/personal/fos-study/`로 저장 위치 결정 (`task/` 아닌 해당 기술 폴더)
3. 저장소 내 관련 기존 문서 확인 → 링크 연결
3-A. **Cross-link 후보 발굴** ([markdown-pitfalls](./references/markdown-pitfalls.md)) — 글 키워드 5\~10개 추출 → `rg -l` 로 전역 grep → H1 추출 → 본문 흐름상 자연스러운 자리 1\~2건만 선정. 표시 텍스트는 H1 제목, 깊은 link 면 앵커, 이탤릭+괄호 강조는 bold+괄호.
3-B. **중복 판정** ([작성 직전 중복 판정](#작성-직전-중복-판정-4-decision)) — 3-A 매치 중 같은 주제 문서가 있으면 new / update-existing / skip / needs-confirmation으로 판정. 모호하면 needs-confirmation(사용자 확인). 외부 개념 글은 같은 기술 폴더에 중복이 쌓이기 쉬우니 특히 점검.
4. 마크다운 작성 — 검색 결과 번역 말고, 본인이 이해한 방식으로 재해석
5. 글 하단에 **참고 링크 섹션** 포함 (URL 명시)
6. **글 자가 점검** — 작성 직후 [markdown-pitfalls](./references/markdown-pitfalls.md) 의 "작성 직후 통합 자가점검 체크리스트"를 순서대로 전부 실행한다. 하나도 건너뛰지 않는다. **정적 위반은 `scripts/blog_score.py <글>` 로 한 번에 측정한다** ([1계층 reward](#자가점검-자동화--blog_score-1계층-reward)).
7. 파일 저장 후 경로 알려주기

---

## 자가점검 자동화 — blog_score (1계층 reward)

[markdown-pitfalls](./references/markdown-pitfalls.md) 의 수동 grep 체크리스트를 `scripts/blog_score.py` 가 한 번에 측정한다.
docs-audit 의 docs_score 와 같은 패턴이며, **글 품질 2계층 reward 의 1계층(정적·회귀 방지)** 이다.

```bash
python3 scripts/blog_score.py <글.md>          # 위반 리포트
python3 scripts/blog_score.py --json <글.md>    # 기계 판독용
```

채점 축 (정적): `bold_quote`, `bold_paren`, `heading_number`, `ascii_box`, `tilde`, `section_sign`, `italic_paren`, `number_crossref`.
위반 0이면 1계층 통과. 위반이 있으면 저장 전 교정한다.

**안전 위반 일괄 교정 — `scripts/blog_fix.py`**:
`heading_number`(`## N.` 자동번호)와 `bold_quote`(`**"..."**`)는 기계적으로 안전하게 되돌릴 수 있어 `blog_fix.py` 가 일괄 교정한다.

```bash
python3 scripts/blog_fix.py            # 현재 경로 이하 전체
python3 scripts/blog_fix.py <dir>      # 특정 폴더만
```

- 안전 조건 — `number_crossref` 가 없는 글만 손댄다(있으면 heading 번호를 떼는 순간 본문 "섹션 N" 참조가 깨짐). `ascii_box`·`bold_paren`·`tilde` 같은 다른 축이 동반돼 있어도 fix 는 `heading_number`·`bold_quote` 만 건드리므로 그 두 축만 부분 교정하고 나머지는 그대로 둔다(수동 판단).
- 코드펜스 인식은 blog_score 와 **동일한 정규식 쌍 매칭**(```` ```...``` ````)을 쓴다. 단순 `startswith("```")` 토글은 리스트 안 들여쓴 펜스(`  - ```md`)를 놓쳐 이후 줄을 통째로 코드펜스로 오판한다(실측: agents-md 누락).

### 2계층 reward — blog_judge (LLM judge)

정적 위반 0은 *회귀가 없다*는 바닥일 뿐, *글이 좋다*는 보장이 아니다.
인사이트 독창성·AI 티·서사 흐름·회고 자연스러움 같은 **의미 품질은 `scripts/blog_judge.py` 가 claude CLI 로 채점**한다.

```bash
python3 scripts/blog_judge.py <글.md>                  # 유형 자동 감지 + 3회 다수결
python3 scripts/blog_judge.py --type study <글.md>      # 유형 강제 지정
```

grade inflation·비결정을 두 장치로 막는다:

- **다수결** — N회 호출의 median (이상치 제거)
- **adversarial** — 매 호출이 "약점 3개를 먼저 찾고" 채점 (후한 점수 방어)

**글 유형별 차등 평가 (필수 설계)** — judge 는 글 유형에 따라 RUBRIC 을 분기한다.
케이스 A(업무 경험)와 케이스 B(스터디/개념)는 평가 기준이 다르기 때문이다.
스터디 글은 본인이 직접 안 써본 외부 기술을 정리한 것이라 "직접 삽질·회고"가 없는 게 정상인데,
이를 일률로 감점하면 스터디 글이 구조적으로 0.7 을 못 넘는다.

- `experience` — 직접 삽질·서사(발견→해결)·회고/협업 축으로 평가. `task/` 경로 또는 "진행 기간" 헤더로 자동 감지.
- `study` — 직접 삽질·회고를 평가하지 않고, 사실 정확성·교차검증·재해석·개념 전달력·비판적 시각으로 평가. 그 외 글의 기본값.
- 공통 축(AI 티 없음·한국어 자연스러움)은 두 유형 모두 적용.
- 자동 감지가 틀리면 `--type` 으로 강제한다.

1계층(blog_score 위반 0) 통과분만 2계층에 올려 LLM 호출 비용을 아낀다.
실측 — 좋은 글 0.62 vs AI 티 나는 글 0.05 (구분 폭 0.57, 점수 분산 거의 0).

이 1계층(정적)+2계층(LLM)이 **세션이 거듭될수록 글쓰기 스킬이 복리로 개선되는 피드백 루프의 채점 엔진**이다.
SkillOpt-Sleep 에 두 reward 를 judge 로 주입하면 글 작성 스킬이 자동 학습된다.

### 자동 트리거 — 사람이 시작하지 않아도 도는 루프

채점 엔진이 자동으로 돌도록 두 부품을 얹었다.

- **자동 채점** — `scripts/autoscore_hook.sh` 를 PostToolUse(Write|Edit) hook 으로 등록(`.claude/settings.local.json`).
  fos-study 글을 저장하는 순간 `blog_score --log` 가 자동 실행돼 위반을 노출하고
  `.skill-loop/violations.jsonl` 에 축별로 누적한다.
- **개선 신호** — `scripts/evolve_check.py` 가 누적 로그를 집계해 반복 위반 축을 SKILL.md 강화 후보로 보고한다.
  ```bash
  python3 scripts/evolve_check.py        # 누적 집계 + 강화 권장 축
  ```

루프 — 글 저장 → 자동 채점·누적 → (반복 시) evolve_check 신호 → 사람이 규칙 강화 → 다음 글 개선.
실제 SKILL.md 수정은 자동으로 하지 않는다(안전) — 반복되는 위반만 사람이 규칙으로 승격한다(거부 편집 버퍼 정신).
