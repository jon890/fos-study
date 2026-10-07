---
name: blog-post-writer
description: 업무 경험이나 기술 학습 내용을 fos-study의 공개 블로그 Markdown 문서로 작성하거나 기존 글을 고친다. task 업무 기록과 기술 study 문서의 분리, 공개 범위, 검증과 발행 전 미리보기가 필요한 요청에 사용한다.
---

# fos-study 블로그 글 작성

**목표: 공개해도 되는 범위의 글이 맞는 위치에 있고, 검사와 미리보기를 통과한 뒤에 블로그로 나간다.**

## 워크플로우 개요

| 단계 | 이름 | 통과 조건 | reference |
| --- | --- | --- | --- |
| 1 | 문서 역할 결정 | 판정(새 글, 보강, 기존 글 안내, 분리, 질문) 하나와 파일 경로가 정해졌다 | `../../references/repository-layout.md` |
| 2 | 근거 확인 | 글에 쓸 이름과 수치마다 출처(코드, 커밋, 공식 문서, 직접 실행 결과)가 있다 | `references/publishing-policy.md` |
| 3 | 본문 작성 | 제목과 첫 단락이 같은 질문에 답한다 | 업무 기록: `../../references/task-writing.md`, `references/writing-style.md` / 학습 문서: `../../references/blog-writing.md` |
| 4 | 검사 | 한국어 검사기 종료 코드가 0이고 내부 링크 대상이 모두 있다 | `references/markdown-pitfalls.md` |
| 5 | 미리보기 | `scripts/preview.sh` 종료 코드가 0이다 | |
| 6 | 커밋과 push | 사용자가 미리보기를 확인한 뒤 관심사별 커밋이 원격에 올라갔다 | |

로컬 파일 작성까지만 요청받았으면 5단계에서 멈춘다.
대표 이미지가 필요하면 3단계에서 `references/thumbnail-generation.md`를 따른다.

## 1. 문서 역할 결정

문서 위치, 카테고리, Frontmatter와 역할 태그를 정하기 전에
[저장소 구조와 문서 배치](../../references/repository-layout.md)를 읽는다.

글을 쓰기 전에 저장소 전체에서 같은 주제를 검색하고 다음 중 하나를 선택한다.

| 판정 | 동작 |
| --- | --- |
| 새 주제 | 새 파일을 만든다. |
| 기존 글의 빈 부분 | 기존 글을 보강한다. |
| 기존 글이 이미 충분함 | 새 파일을 만들지 않고 기존 글을 안내한다. |
| 업무 서사와 기술 개념이 섞임 | `task/`에는 경험을, 기술 폴더에는 일반 개념을 두고 서로 연결한다. |
| 두 글의 역할을 구분하기 어려움 | 사용자에게 방향을 묻는다. |

특정 회사·포지션·면접을 위한 가상 도메인을 일반 기술 주제에 붙이지 않는다.
이미 섞인 글을 고칠 때는 일반 개념만 기술 문서에 남기고 실제 업무 경험은 해당 `task/` 문서로 옮기거나 연결한다.

## 2. 근거 확인

기억으로 클래스명, 메서드명과 측정값을 만들지 않는다.

업무 기록은 다음을 먼저 확인한다.

- 본인 커밋, PR과 실제 코드에서 기여 범위와 진행 기간을 확인한다.
- 코드와 내부 식별자는 [공개 범위](./references/publishing-policy.md)를 적용한다.

학습 문서는 현재 동작이 바뀔 수 있는 주장을 공식 문서, 논문이나 원저장소에서 확인한다.
적용 버전을 밝히고 출처의 사실, 직접 확인한 결과와 추론을 구분한다.

## 3. 본문 작성

| 글 종류 | 읽을 문서 |
| --- | --- |
| 업무 기록과 팀 README | [업무 기록 작성](../../references/task-writing.md), 표현과 구성은 [작성 기준](./references/writing-style.md) |
| 학습 문서 | [공개 블로그 문서 작성](../../references/blog-writing.md). 깊이, 시각화, 용어와 링크 규칙이 있다 |

업무 기록에서 일반 기술 설명이 길어지면 기술 폴더 문서로 분리하고 링크한다.

초안을 쓴 뒤 다음을 확인한다.

1. 제목과 첫 단락이 같은 질문에 답한다.
2. 중복 결론, 장식용 표와 근거 없는 수치를 제거했다.

새 글에 대표 이미지가 필요하면 [썸네일 생성](./references/thumbnail-generation.md)을 따른다.
이미지 생성 도구가 없으면 썸네일 없이 진행하고 블로그 기본 이미지를 쓴다.

## 4. 검사

[fos-blog 마크다운](./references/markdown-pitfalls.md)의 렌더링 제약을 적용한 뒤 검사기를 돌린다.
검사기는 `korean-check` 스킬이 소유한다.

```bash
POST=database/postgresql/docker-parallel-query-dev-shm.md   # 검사할 글
bash ~/personal/fos-skills/korean-check/scripts/check.sh "$POST"
```

- 내부 링크는 대상 파일이 존재하는지 확인한다.
- 파일을 이동·삭제했거나 링크를 바꿨으면 `docs-audit` 구조 검사도 실행한다.

## 5. 미리보기

글을 쓴 워크트리 루트에서 실행한다.

```bash
POST=database/postgresql/docker-parallel-query-dev-shm.md   # 미리볼 글
bash .claude/skills/blog-post-writer/scripts/preview.sh "$POST"
```

스크립트가 하는 일과 종료 코드는 `scripts/preview.sh` 머리말이 소유한다.
요약하면 HTML을 `/private/tmp/fos-study-preview/` 아래에 만들고, 사용자가 보는 Orca 탭에 띄우고, 같은 탭에서 Mermaid 렌더링을 확인한다.

- 종료 코드가 1이면 Mermaid 문법 오류다. 글을 고치고 다시 실행하면 같은 탭이 갱신된다.
- Mermaid가 있으면 스크립트가 남긴 스크린숏을 열어 노드 잘림과 연결선 겹침을 본다.
- Playwright와 로컬 HTTP 서버는 쓰지 않는다. Playwright는 `file://` 주소를 막고, 연 화면이 Orca에 나타나지 않는다.

삭제만 한 변경에는 본문 미리보기가 필요하지 않다. 새로 작성하거나 의미 있게 고친 공개 글은 미리보기 대상이다.

## 6. 커밋과 push

- 미리보기를 보여준 턴에는 push하지 않는다. 사용자가 확인한 다음 push한다.
- 글, 목차 링크, 스킬 변경처럼 관심사별로 커밋을 나눈다.
- 작업 브랜치에서 만든 커밋을 블로그에 반영하려면 `origin/main`에 fast-forward로 올린다. fast-forward가 안 되면 사용자에게 묻는다.
