---
name: series-organizer
description: fos-study의 기존 Markdown 글을 frontmatter의 series와 seriesOrder로 묶는다. 후보 탐색, 순서 제안과 승인된 메타데이터 적용에 사용하며 본문은 수정하지 않는다.
---

# fos-study 시리즈 구성

시리즈는 같은 주제를 읽는 순서가 분명할 때만 만든다. 같은 폴더에 있다는 이유만으로 모든 글을 묶지 않는다.

## 지켜야 할 범위

- 본문과 H1은 수정하지 않는다.
- 기존 frontmatter의 `tags`, `categories`, `thumbnail`과 다른 키를 보존한다.
- `series`와 `seriesOrder`만 추가하거나 갱신한다.
- 순서나 포함 범위가 모호하면 적용 전에 사용자에게 확인한다.

## 후보 확인

번호가 붙은 글은 파일명 순서를 우선 참고한다. 번호가 없는 글은 내용의 선행 관계를 직접 확인한다.

```bash
python3 .claude/skills/series-organizer/scripts/scan_series.py --json <폴더>
```

저장소 전체를 살펴볼 때만 `--root .`을 사용한다. 스캔 결과의 강도는 후보 탐색용이며 자동 적용 근거가 아니다.

사용자에게는 시리즈명, 포함할 글과 순서를 제안한다. 사용자가 승인한 결과를 다음 형식의 JSON으로 만든다.

```json
[
  {"path": "경로.md", "series": "시리즈 이름", "seriesOrder": 1}
]
```

## 적용

먼저 dry-run으로 실제 diff를 확인한다.

```bash
python3 .claude/skills/series-organizer/scripts/apply_series.py --dry-run <매핑.json>
```

본문과 기존 frontmatter가 보존됐으면 같은 매핑을 실제 적용한다.

```bash
python3 .claude/skills/series-organizer/scripts/apply_series.py <매핑.json>
```

적용 뒤에는 변경된 글의 frontmatter와 첫 H1을 확인하고, 프로젝트 문체 검사와 `docs-audit` 구조 검사를 실행한다. 블로그 push까지 요청받았다면 `content-preview` 절차를 먼저 따른다.
