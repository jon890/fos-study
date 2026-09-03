---
name: docs-audit
description: fos-study 저장소에서 깨진 내부 링크, 고아 Markdown 문서와 폴더 README 누락을 검사한다. 문서의 의미 품질이나 삭제 판단은 docs-check가 담당한다.
---

# fos-study 문서 구조 점검

이 스킬은 저장소 구조에서 기계적으로 판정할 수 있는 문제만 찾는다.

## 실행

저장소 루트에서 다음 명령을 실행한다.

```bash
python3 .claude/skills/docs-audit/scripts/docs_score.py --json
```

결과의 `ok`가 `true`이고 프로세스 종료 코드가 0이면 구조 점검을 통과한다. 실패하면 `details`에 나온 파일과 링크를 확인한다.

검사 범위는 다음과 같다.

- 존재하지 않는 내부 Markdown 링크
- 다른 문서에서 링크되지 않은 문서
- 같은 폴더의 `README.md`에 등재되지 않은 문서

문체와 한국어 표현은 프로젝트 지침에 적힌 공용 검사기가 소유한다. 문서의 부패, 중복, 관심사 혼합과 삭제 후보 판단은 `.claude/docs-check-overlay.md`를 읽고 `docs-check`로 처리한다.

## 수정 경계

감사만 요청받았다면 결과를 보고하고 파일을 고치지 않는다. 수정까지 요청받았거나 사용자가 결과를 승인한 경우에만 다음 원칙으로 교정한다.

- 고아 문서는 곧바로 삭제하지 않고 의미상 연결 위치를 먼저 판단한다.
- README 누락 문서는 실제 폴더 역할과 맞을 때만 등재한다.
- `resume/`는 프로젝트 지침의 보존 예외를 따른다.

수정 후 같은 명령과 `git diff --check`를 다시 실행한다.

스킬이나 검사기를 변경했으면 `skill-creator`의 `quick_validate.py`와 `tests/test_docs_score.py`를 실행한다.
