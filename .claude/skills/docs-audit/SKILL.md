---
name: docs-audit
description: fos-study 저장소의 빠른 문서 구조 점검. 사용자가 `docs-audit`을 명시하거나 broken link, orphan 문서, README 미등재 검사를 요청할 때 사용한다. 의미 품질, AI slop, 중복과 문서 역할 판정은 공용 `docs-check`와 `.claude/docs-check-overlay.md`가 담당한다.
metadata:
  id: workflow-docs-audit
  source: conversation
  quality: high
  triggers:
    - "docs-audit"
    - "docs-link-audit"
    - "broken link"
    - "orphan doc"
    - "README 정합성"
    - "문서 링크 검사"
---

# fos-study 문서 구조 점검

이 스킬은 fos-study에만 필요한 결정적 검사 진입점이다.
문서 의미를 평가하는 별도 워크플로를 소유하지 않는다.

## 책임 경계

| 요청 | 소유자 |
| --- | --- |
| 깨진 내부 링크, orphan, README 미등재, 렌더링 문체 패턴 | 이 스킬의 `docs_score.py` |
| 부패, 과대화, 추론성, 중복, 자명성, 구조 의미 판정 | 공용 `docs-check` |
| 회사 맥락과 일반 지식 혼합, AI slop, 문서 보존 분류 | `docs-check`와 프로젝트 overlay |
| 개별 블로그 글 작성 직후의 문체와 미리보기 | `blog-post-writer` |

전체 문서 감사나 의미 품질 요청이면 먼저 `.claude/docs-check-overlay.md`를 읽고 `docs-check`를 적용한다.
사용자가 `docs-audit`만 명시한 경우에는 정적 점검을 실행하고, 의미 검사가 필요한 발견만 `docs-check`로 넘긴다.

## 정적 점검

저장소 루트에서 실행한다.

```bash
python3 .claude/skills/docs-audit/scripts/docs_score.py --json
```

출력의 `score`는 0이 만점이며 위반이 있으면 음수가 된다.
판정에는 `score`만 보지 말고 `details`의 파일과 패턴을 함께 읽는다.

검사 항목은 다음과 같다.

- 존재하지 않는 내부 Markdown 링크
- 다른 문서에서 링크되지 않은 orphan 문서
- 같은 폴더 README에 등재되지 않은 문서
- fos-blog 렌더링을 깨뜨리는 `~`, `§`, bold·italic 괄호 패턴

가시성과 cross-link는 정규식 점수로 확정하지 않는다.
필요하면 overlay가 지정한 read-only 검증 역할을 사용한다.

## 수정 경계

감사 요청은 발견 전용이다.
사용자가 수정까지 요청했거나 감사 결과를 보고 승인한 항목만 고친다.

- 누락 파일을 임의 카테고리에 넣지 않는다.
- orphan 문서는 삭제하지 않고 연결 후보를 먼저 제안한다.
- cross-link는 본문 흐름에 도움이 되는 경우만 제안한다.
- `resume/`는 프로젝트 지침의 보존 예외를 우선한다.

수정 후 같은 명령을 다시 실행하고 `git diff --check`를 확인한다.

## 스킬 자체를 변경했을 때

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .claude/skills/docs-audit
```

`docs_score.py`의 판정 로직을 바꾸면 실제 위반 표본과 정상 표본을 모두 검사한다.
