---
tags: [study, insights]
---

# GitHub Actions 로 PR 마다 AI 코드 리뷰를 자동으로 돌리는 워크플로 설계

PR 이 열리면 AI 가 먼저 리뷰를 달아 주는 워크플로는 만들기는 쉽지만 운영하면 손볼 곳이 계속 나온다.
댓글이 중복으로 쌓이고, 봇이 봇을 다시 불러내고, 프롬프트 파일이 포맷터에 깨지고, 리뷰어가 엉뚱한 파일을 PR 에 올리기도 한다.
이 글은 공개 저장소 [nhncloud-cli](https://github.com/jon890/nhncloud-cli) 의 `claude-code-review.yml` 과 `code-review-prompt.txt` 를 운영하며 정리한 설계 기준이다.
두 구현 방식의 선택, 실행 제어, 프롬프트 분리, 게시 방식, 자주 실패하는 곳을 순서대로 다룬다.

## 구현 방식 두 가지

| 구분 | marketplace action | self-hosted CLI |
| --- | --- | --- |
| 구성 | `anthropics/claude-code-action` 을 step 으로 사용 | runner 에 `claude login` 해 두고 워크플로가 `claude` 바이너리를 직접 호출 |
| 장점 | 설정이 쉽다 | action 에 의존하지 않고 모델, 도구, 프롬프트를 모두 제어한다 |
| 비용 | action 이 내부에서 `git add -A` 같은 작업을 해 임시 파일이 PR 에 섞일 수 있다 | 인증과 도구 차단을 직접 챙겨야 한다 |

이 글의 설계 기준은 두 방식에 공통으로 적용된다.
차이는 분리한 프롬프트를 모델에 어떻게 전달하느냐뿐이며, 아래 「프롬프트 전달」 절에서 비교한다.

## 실행 제어

### 트리거

- `pull_request: [opened]` 로 PR 을 열 때 자동으로 리뷰한다.
- `issue_comment: [created]` 로 PR 댓글에 `/review` 가 달리면 다시 리뷰한다. `issue_comment` 는 일반 이슈 댓글에도 발생하므로 `github.event.issue.pull_request != null` 로 PR 댓글만 걸러야 한다.

### 봇과 중복 실행 제어

- 봇이 만든 이벤트는 제외한다. 사용하는 저장소의 워크플로는 `dependabot[bot]` 과 `claude[bot]` 을 명시해 제외한다. 봇 계정이 늘어날 것 같으면 `endsWith(github.actor, '[bot]')` 로 한꺼번에 제외하는 방식도 있다.
- `concurrency` 그룹을 PR 번호로 잡고 `cancel-in-progress: true` 로 같은 PR 의 이전 실행을 취소한다. 푸시마다 리뷰가 겹쳐 쌓이는 일을 막는다.

### 권한

`contents: read`, `pull-requests: write`, `issues: write` 를 기본으로 둔다.
`checks: write` 는 Check Run 을 만들 때만 필요하다. 아래 「자주 실패하는 곳」 에서 이유를 설명한다.

### 진행 표시

`/review` 로 시작한 실행은 사람이 결과를 기다리고 있다.
시작할 때 댓글에 `eyes` reaction 을 달고, 끝나면 성공 여부에 따라 `+1` 이나 `-1` reaction 을 단다.

## 프롬프트 설계

### `.txt` 파일로 분리한다

50줄이 넘는 프롬프트를 YAML 안에 heredoc 으로 넣으면 읽기 어렵다.
그래서 별도 파일로 분리하되 확장자는 `.md` 가 아니라 `.txt` 로 둔다.
IDE 의 Markdown 포맷터가 `*.lock` 같은 glob 을 `_.lock` 으로, `_x` 같은 식별자를 `\_x` 로 바꿔 프롬프트를 깨뜨리기 때문이다.
프롬프트는 문서가 아니라 모델에 넣는 평문이다.

변수는 `envsubst '$PR_NUMBER $REPO'` 처럼 치환할 이름을 명시해 바꾼다.
이름을 주지 않으면 프롬프트 안의 다른 `$` 표현이 모두 빈 값으로 바뀐다.
파일은 YAML 밖에 있어서 `${{ }}` 식이 평가되지 않으므로 `$VAR` 형태의 자리표시자를 쓴다.

### 개방형으로 시작한다

"리뷰 관점 네 가지" 처럼 닫힌 번호 목록을 주면 모델이 그 목록만 체크리스트처럼 따라가 일반 버그를 놓친다.
nhncloud-cli 의 프롬프트는 이 점을 반영해 로직, 타입, 안전처럼 일반 코드 리뷰 관점을 먼저 나열하고, 프로젝트 고유 규칙은 `AGENTS.md` 와 `docs/pitfalls/INDEX.md` 에서 읽어 오게 한다.
프롬프트에는 고정된 패턴 목록을 새로 만들지 않고, 규칙이 바뀌면 그 문서만 고치게 한다.

### 심각도를 표시한다

요약 댓글에서 🔴(머지 전에 고쳐야 하는 결함), 🟡(개선 항목), 잘된 점을 구분한다.
이 구분은 게시 후 점검에도 쓰인다. 심각도 표시가 하나도 없는 인라인 댓글은 형식을 어긴 것으로 보고 지울 수 있다.

### 프롬프트 전달

| 구분 | marketplace action | self-hosted CLI |
| --- | --- | --- |
| 프롬프트 | 사전 step 이 `envsubst` 로 치환해 `$GITHUB_OUTPUT` 의 멀티라인 output 으로 넘기고 action 의 `prompt:` 에 연결한다 | `envsubst ... < prompt.txt \| claude ... -p -` 로 stdin 에 직접 연결한다 |
| 모델과 도구 | `claude_args: '--model opus --allowedTools ... --disallowedTools ...'` | 같은 플래그를 CLI 에 직접 준다 |

marketplace action 의 멀티라인 output 은 다음 형태다.

```yaml
- id: prompt
  env:
    PR_NUMBER: ${{ env.PR_NUMBER }}
    REPO: ${{ github.repository }}
  run: |
    {
      echo 'text<<PROMPT_EOF'
      envsubst '$PR_NUMBER $REPO' < .github/workflows/code-review-prompt.txt
      echo 'PROMPT_EOF'
    } >> "$GITHUB_OUTPUT"
```

이후 action 에서 `prompt: ${{ steps.prompt.outputs.text }}` 로 받는다.
구분자(`PROMPT_EOF`)가 프롬프트 본문에 우연히 등장하면 output 이 거기서 끊기므로, 본문에 나올 수 없는 토큰으로 정한다.

## 모델 지정

모델을 `claude-opus-4-7` 같은 고정 태그로 쓰면 모델이 바뀔 때마다 워크플로를 고쳐야 한다.
설치된 CLI 나 action 이 그 태그를 모르면 실행도 실패한다.
`--model opus` 별칭을 쓰면 CLI 가 인식하는 최신 Opus 를 따라가므로 버전이 올라가도 워크플로를 고칠 필요가 없다.

self-hosted CLI 방식에서는 본 실행 전에 `claude --model <별칭> --print -p ok` 를 한 번 호출해 모델 인식을 확인하면 실패 원인이 모델인지 프롬프트인지 바로 갈린다.

## 리뷰어 구성

| 구성 | 장점 | 비용 |
| --- | --- | --- |
| 단일 opus 리뷰어 | 한 에이전트가 타입, 컨벤션, 보안, 구조를 직접 보므로 판정이 일관되고 구성이 단순하다 | 관점을 나누지 않으므로 속도와 토큰 절감은 기대하기 어렵다 |
| 병렬 specialist 네 개(sonnet 과 haiku 혼합) | 관점을 나눠 동시에 돌려 속도와 토큰을 줄일 수 있다 | 결과를 합치는 orchestration 이 복잡하다 |

dooray-cli 에서 쓰던 병렬 specialist 방식을 nhncloud-cli 로 옮겼다가 단일 opus 리뷰어로 바꿨다.
현재 nhncloud-cli 의 프롬프트는 "서브 에이전트를 만들지 말고 현재 PR 을 직접 검토한다" 로 시작한다.
일관성과 단순함이 속도나 비용보다 중요하면 단일 리뷰어가 맞다.
병렬 구성은 속도와 비용 최적화가 목표일 때 고른다.

## 게시 방식

### 요약과 인라인 댓글을 리뷰 하나로 묶는다

초기 구성은 변경된 파일의 줄에 인라인 댓글을 달고, 전체 요약은 `gh pr comment` 일반 댓글 하나로 따로 올렸다.
현재 워크플로는 `POST /repos/{repo}/pulls/{pr}/reviews` 를 한 번 호출해 요약(`body`)과 인라인 발견(`comments[]`)을 리뷰 하나로 올린다.
일반 댓글로 올리면 요약이 리뷰와 분리되기 때문이다.

- 인라인 발견은 변경된 새 줄을 정확히 특정할 수 있을 때만 쓰고, 위치가 불확실하면 요약 본문의 해당 심각도 절에 적는다.
- 발견이 없으면 `comments` 를 빈 배열로 두고 검토한 범위와 잘된 점만 `body` 에 남긴다.
- 요청 본문은 `mktemp` 로 만든 임시 파일에 JSON 으로 쓰고 `gh api ... --input` 으로 넘긴다. 인자로 직접 넘기면 줄바꿈이 깨진다.

### 이전 리뷰를 정리한다

같은 PR 에서 다시 실행하면 이전 봇 댓글이 남아 중복된다.
그래서 매 실행 전에 이전 댓글을 정리한다.

- 일반 댓글과 인라인 댓글은 REST API 로 삭제한다.
- 제출된 `COMMENT` 리뷰는 REST 로 삭제할 수 없고 dismiss 도 `APPROVED` 와 `CHANGES_REQUESTED` 에만 되므로, GraphQL `minimizeComment` 로 접는다.
- 목록은 페이지 단위로 내려오므로 `--paginate` 로 끝까지 훑어야 100개가 넘는 댓글도 정리된다.

### 읽기 전용으로 묶는다

Write 와 Edit 를 `--disallowedTools` 로 막아 리뷰어가 파일을 고치지 못하게 한다.
marketplace action 의 wrapper 는 내부에서 `git add -A` 를 돌리므로, 에이전트가 디스크에 임시 파일을 만들면 그 파일이 PR 브랜치 커밋에 섞여 들어갈 수 있다.
요약 댓글도 파일로 만들지 않고 quoted HEREDOC 으로 표준 입력에만 흘리는 이유다.

## 자주 실패하는 곳

- **줄바꿈이 깨진 댓글**: `--body "...\n..."` 는 shell 이 `\n` 을 두 글자 그대로 전달한다. `--body-file -` 와 quoted HEREDOC 으로 실제 개행을 넘긴다.
- **본문에 적은 명령어가 동작함**: 댓글 본문의 `/review` 는 리뷰를 다시 실행시키고, `@claude` 는 봇 멘션으로 인식되며, `#N` 은 엉뚱한 이슈로 링크된다. 백틱으로 감싸 평문으로 만든다.
- **`issue_comment` 실행이 Checks 탭에 보이지 않음**: 이 이벤트로 시작한 실행은 PR 의 Checks 탭에 자동으로 연결되지 않는다. head SHA 에 Check Run 을 직접 만들면 표시되지만 Checks API 는 GitHub App 인증을 요구한다. 일반 `GITHUB_TOKEN` 만 쓰는 구성에서는 Check Run 을 포기하고 reaction 으로 진행을 표시하는 편이 단순하다.
- **더미 댓글**: 모델이 지침을 무시하고 "test" 같은 댓글을 올린 적이 있다. 게시 후 jq 로 길이가 12자 미만이거나 자리표시자이거나 🔴, 🟡 표시가 없는 인라인 댓글을 삭제하는 단계를 `if: always()` 로 둔다. 프롬프트에 "더미를 올리지 말라" 고 적는 것만으로는 막히지 않았다.
- **묻혀 버리는 실패**: 부가 단계에 `|| true` 를 붙이면 인증 오류가 job 성공 표시 뒤에 가려진다. `|| echo "::warning::..."` 로 Annotations 에 드러내고 부가 작업은 계속 진행하게 한다.
- **토큰 표기 혼동**: `github.token` 과 `secrets.GITHUB_TOKEN` 은 같은 값이다. 표기를 바꿔도 권한은 바뀌지 않으므로 401, 403 은 표기가 아니라 호출한 API 와 호스트에서 원인을 찾는다.
- **모델 태그**: CLI 나 action 이 모르는 태그를 쓰면 실행이 실패한다. 위 「모델 지정」 의 별칭을 쓴다.

## 정리

| 결정 | 선택 |
| --- | --- |
| 구현 방식 | 설정이 쉬우면 marketplace action, 모델과 도구를 직접 제어해야 하면 self-hosted CLI |
| 프롬프트 | `.txt` 파일 분리, `envsubst` 로 이름을 지정해 치환, 일반 리뷰를 먼저 요구 |
| 모델 | `--model opus` 별칭 |
| 게시 | 요약과 인라인을 리뷰 한 건으로, 매 실행 전 이전 리뷰 정리 |
| 방어 | 읽기 전용 도구, 더미 댓글 삭제 단계, 실패는 warning 으로 노출 |

자동 리뷰가 통과해도 머지 여부는 사람이 판단한다.
리뷰 봇이 제안한 명령과 정규식을 그대로 적용할 때 생기는 문제는 [리뷰 봇이 제안한 명령과 정규식은 실제 데이터에 먼저 돌려 본다](./review-bot-suggestion-verify.md)에서 다룬다.
