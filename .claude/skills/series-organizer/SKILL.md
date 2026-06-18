---
name: series-organizer
description: fos-study 저장소의 기존 글들을 블로그 시리즈로 묶는다. 폴더를 스캔해 시리즈 후보를 탐지하고 시리즈명·seriesOrder 를 제안한 뒤, 사용자 승인을 받아 글 frontmatter 에 series + seriesOrder 메타를 추가한다. "시리즈로 묶어", "시리즈 정리", "연재로 묶어", "series-organizer", "seriesOrder 부여", "이 폴더 시리즈로", "시리즈 메타 추가", "스프링 배치 시리즈로" 같은 요청 시 반드시 이 스킬을 사용한다. 개별 글을 새로 *작성*하는 것은 blog-post-writer 가 담당하고, 이 스킬은 이미 있는 글들을 시리즈 메타로 *묶는* 역할만 한다(본문은 건드리지 않는다). 일괄 자동 적용하지 않고 반드시 사용자 승인 단계를 거친다.
---

# 기존 글을 블로그 시리즈로 묶기

## The Insight

fos-blog 는 시리즈 기능이 이미 구현돼 있는데(`/series` 페이지) 정작 시리즈로 묶인 글이 없다.
기능은 완성됐고 콘텐츠에 메타만 안 붙은 상태다.
이 스킬은 글 **본문을 건드리지 않고** frontmatter 메타(`series` 와 `seriesOrder`)만 부여해 그 간극을 메운다.

핵심 원칙 세 가지:

1. **본문 불가침** — 첫 H1 제목·본문은 절대 수정하지 않는다. frontmatter 두 줄만 추가·갱신한다.
2. **사용자 승인 기반** — 스캔으로 후보를 제안하되, 시리즈/글 단위로 사용자가 확인한 것만 적용한다. 일괄 자동 적용하지 않는다.
3. **frontmatter 보존** — 기존 frontmatter 가 있으면 `series`/`seriesOrder` 만 다루고 다른 키(`categories` 등)는 그대로 둔다.

## 발행 메커니즘 (블로그 측 — 알아둘 것)

- frontmatter 에 `series`(시리즈명) + `seriesOrder`(0 이상 정수)가 **둘 다** 있어야 묶인다.
- `seriesOrder` 가 없거나 유효하지 않으면 시리즈 메타가 무시된다(블로그 sync 가 경고 로그만 남김).
- 같은 `series` 값을 가진 글들이 `seriesOrder` 오름차순으로 `/series/<이름>` 페이지에 노출된다.
- 적용 흐름: 글에 frontmatter 추가 → 커밋 → 블로그 `POST /api/sync` → DB 반영 → `/series` 노출.

예시 frontmatter:

```yaml
---
series: "죽음의 스프링 배치"
seriesOrder: 1
---
```

> 이 저장소는 현재 frontmatter 를 쓰는 글이 0건이다. 즉 이 스킬이 붙이는 메타가 첫 frontmatter 가 된다.
> 그래서 적용 후 **본문 렌더가 깨지지 않는지**(특히 첫 H1) 확인하는 단계가 형식이 아니라 실제로 중요하다.

## 설계 결정 (확정)

| 쟁점 | 결정 |
|---|---|
| seriesOrder 부여 | 파일명 번호를 version sort 한 뒤 **1,2,3… 정수로 재부여**한다. `0.1`·`0.2`·`1.1` 같은 장·절 2단계 구조는 단일 정렬키로 평탄화되지만, 원래 장 구조는 본문·제목에 그대로 남는다. |
| 번외편(번호 없는 글) | 시리즈 포함 여부를 **글 단위로 사용자에게 확인**한다. 포함하면 순서를 사용자가 지정한다(기본은 제외). |
| 시리즈명 | `README.md` 의 H1 → 첫 번호글의 H1 → 폴더명 순으로 추론해 **제안**하되, 최종값은 사용자가 확정한다. |

## 워크플로우

### 1. 스캔 — 시리즈 후보 탐지

`scripts/scan_series.py` 가 폴더의 .md 파일명 선행 번호를 파싱해 version sort 하고 seriesOrder 를 제안한다.
README.md 는 시리즈 글에서 제외하고 시리즈명 추론에만 쓴다.

```bash
# 저장소 전체에서 후보 자동 탐지(.md 2개 이상인 폴더)
python3 .claude/skills/series-organizer/scripts/scan_series.py --root .

# 특정 폴더만
python3 .claude/skills/series-organizer/scripts/scan_series.py java/spring-batch devops/k8s-in-action

# 기계 판독용 JSON (승인 매핑을 조립할 때)
python3 .claude/skills/series-organizer/scripts/scan_series.py --json java/spring-batch
```

등급의 의미:

- **strong** — 번호글이 2편 이상. 파일명 번호로 순서가 정해져 바로 묶을 수 있다.
- **medium** — 번호는 없지만 글이 3편 이상. 학습 순서를 사람이 정해야 한다.
- **weak** — 그 외. 시리즈로 묶기 애매하다.

번호 체계가 깨끗하지 않은 폴더(중간에 번호 누락, 번호글과 무번호글 혼재)는 strong 으로 잡혀도
사실상 사람 판단이 필요하다. 스캔 결과를 사용자에게 보여줄 때 이런 폴더는 그 점을 함께 짚는다.

### 2. 제안 — 사용자에게 시리즈 매핑 보여주기

스캔 결과를 폴더별로 사용자에게 보고한다. 폴더마다 다음을 제시한다:

- 제안 시리즈명(추론 근거: README H1 / 첫 글 H1 / 폴더명 중 무엇인지)
- 글 순서(seriesOrder)와 각 글 제목
- 번외편(번호 없는 글) 목록 — 포함할지 물을 대상

여러 폴더를 한 번에 처리할 때는 `AskUserQuestion` 으로 어느 시리즈를 적용할지 고르게 한다.
시리즈명·번외편 포함 여부처럼 사용자 판단이 필요한 항목은 적용 전에 확정한다.

### 3. 승인 — 매핑 JSON 조립

사용자가 확정한 내용으로 적용 매핑 JSON 을 만든다. 형식:

```json
[
  {"path": "java/spring-batch/0.1-introduce.md", "series": "죽음의 스프링 배치", "seriesOrder": 1},
  {"path": "java/spring-batch/0.2-first-job-example.md", "series": "죽음의 스프링 배치", "seriesOrder": 2}
]
```

`scan_series.py --json` 출력의 `path`·`suggested_order` 를 그대로 쓰되,
시리즈명·번외편 포함·순서 조정 같은 사용자 결정만 반영하면 된다.

### 4. 적용 — frontmatter 추가

먼저 **반드시 dry-run 으로 diff 를 확인**한 뒤 실제 쓰기를 한다.

```bash
# 변경 미리보기 (쓰지 않음)
python3 .claude/skills/series-organizer/scripts/apply_series.py --dry-run /tmp/series-map.json

# 실제 적용
python3 .claude/skills/series-organizer/scripts/apply_series.py /tmp/series-map.json
```

`apply_series.py` 의 안전 동작:

- 기존 frontmatter 가 있으면 `series`/`seriesOrder` 만 추가·갱신하고 나머지 키는 보존한다.
- frontmatter 가 없던 글은 본문 맨 앞에 새 블록을 만들고, 블록과 본문 사이에 빈 줄 1개를 둔다.
- 멱등성 — 같은 매핑을 다시 적용하면 변경 없음(skip)으로 처리된다.
- 본문(첫 H1 등)은 건드리지 않는다.

### 5. 보고 + 렌더 확인

적용 후 사용자에게 보고한다:

- 변경된 파일 목록
- 시리즈 → 글(seriesOrder) 매핑

그리고 **frontmatter 추가가 본문 렌더를 깨지 않는지** 확인한다.
적용한 글 1~2편의 상단을 직접 열어 `---` 블록 → 빈 줄 → 첫 H1 순서가 맞는지 본다.
이 저장소는 frontmatter 첫 도입이라 이 점검을 생략하지 않는다.

최종 확인은 커밋 → 블로그 sync 후 `/series/<이름>` 페이지에 시리즈가 노출되는지로 한다.

## blog-post-writer 와의 관계

- `blog-post-writer` — 개별 글을 **작성**(업무 경험·스터디 → 마크다운).
- `series-organizer`(이 스킬) — 이미 있는 글들을 **시리즈로 묶기**(frontmatter 메타 부여).

cross-link(본문 링크)와 series(메타)는 별개 레이어로 공존한다.
blog-post-writer 가 번호 매겨진 시리즈 폴더(예: `java/spring-batch`)에 새 글을 추가하면,
이 스킬을 다시 돌려 새 글의 seriesOrder 를 부여하고 기존 순서를 재조정한다.

## 커밋

frontmatter 부여는 단일 관심사다. 시리즈 단위로 원자적 커밋한다.
예: `docs(spring-batch): 시리즈 frontmatter 부여 (series + seriesOrder)`.
