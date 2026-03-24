# Claude Code 멀티 에이전트 — Teams

Claude Code는 단일 에이전트로 동작하는 것 외에, 여러 전문화된 에이전트를 조율해서 복잡한 작업을 병렬로 처리하는 **팀 구조**를 지원한다.

---

## 기본 개념: Agent 도구

Claude Code는 `Agent` 도구로 하위 에이전트(서브프로세스)를 생성할 수 있다. 각 에이전트는 독립된 컨텍스트를 갖고, 자신에게 할당된 도구 셋과 역할로 동작한다.

```
오케스트레이터 (메인 Claude)
    ├─ Agent 1: 코드 탐색 (Explore)
    ├─ Agent 2: 구현 (Executor)
    └─ Agent 3: 검증 (Verifier)
```

단일 에이전트가 긴 작업을 처리하면 컨텍스트 한계에 부딪힌다. 팀 구조는 각 에이전트가 제한된 범위의 작업만 담당하게 해서 이 문제를 우회한다.

---

## 전문화된 에이전트 타입

| 에이전트 | 역할 | 특징 |
|---|---|---|
| `executor` | 구현 작업 | 코드 작성, 수정 |
| `verifier` | 검증 | 완성도 확인, 테스트 통과 여부 |
| `code-reviewer` | 코드 리뷰 | 품질, 스타일, 잠재 버그 |
| `debugger` | 디버깅 | 근본 원인 분석, 스택 트레이스 |
| `explore` | 코드베이스 탐색 | 파일 찾기, 패턴 검색 |
| `architect` | 아키텍처 설계 | 구조 분석, 트레이드오프 검토 |
| `test-engineer` | 테스트 전략 | 커버리지, 엣지 케이스 |
| `writer` | 문서 작성 | README, API 문서, 주석 |
| `security-reviewer` | 보안 검토 | OWASP, 취약점 탐지 |

---

## 팀 워크플로우

복잡한 작업은 단계별로 나눠서 각 단계에 맞는 에이전트를 배치한다.

```
team-plan  → 작업 계획 수립
team-prd   → 요구사항 문서화
team-exec  → 구현
team-verify → 검증
team-fix   → 실패 시 수정 (verify → fix 루프)
```

### 병렬 실행 패턴

독립적인 작업은 동시에 실행해서 시간을 줄인다.

```
오케스트레이터
    ├─ [병렬] Explore: "인증 관련 파일 탐색"
    ├─ [병렬] Explore: "API 엔드포인트 목록 파악"
    └─ [병렬] Explore: "테스트 커버리지 현황 파악"
         ↓ 결과 합산
    Executor: 구현 작업 시작
```

### 리뷰 파이프라인

구현 완료 후 자동으로 리뷰와 검증을 붙이는 패턴.

```
Executor → 코드 작성 완료
    ↓
Code Reviewer → 스타일, 품질 검토
    ↓
Security Reviewer → 보안 취약점 검토
    ↓
Verifier → 테스트 통과 확인
    ↓
완료
```

---

## 에이전트 간 통신

### SendMessage

이미 실행 중인 에이전트에 메시지를 보내서 대화를 이어갈 수 있다. 에이전트는 자신의 전체 컨텍스트를 유지한다.

```
Agent 생성 → name: "my-researcher"
나중에 → SendMessage(to: "my-researcher", message: "추가 조사해줘")
```

### 백그라운드 실행

`run_in_background: true`로 에이전트를 백그라운드에서 실행하고, 완료 통보를 받을 때까지 다른 작업을 계속할 수 있다.

```
빌드 검증 에이전트 → 백그라운드 실행
    ↓ 기다리는 동안
문서 작성 에이전트 → 포그라운드 실행
    ↓
빌드 검증 완료 알림 수신
```

---

## Worktree 격리

에이전트를 `isolation: "worktree"` 옵션으로 실행하면 임시 git worktree에서 독립된 환경으로 작업한다. 메인 브랜치에 영향 없이 실험적 변경을 시도할 수 있다.

```
메인 브랜치
    ├─ worktree-A: 기능 A 구현 에이전트
    ├─ worktree-B: 기능 B 구현 에이전트
    └─ worktree-C: 리팩터링 에이전트
```

변경이 없으면 worktree는 자동 삭제된다.

---

## tmux와 함께 사용하기

tmux의 멀티 페인 구조와 Claude Code 팀을 함께 쓰면 각 에이전트의 진행 상황을 시각적으로 확인할 수 있다.

```bash
#!/bin/bash
# 에이전트별 tmux 페인 구성

tmux new-session -d -s agents

# 오케스트레이터
tmux send-keys -t agents "claude" Enter

# 백그라운드 에이전트들
tmux split-window -h
tmux send-keys -t agents "# executor agent pane" Enter

tmux split-window -v
tmux send-keys -t agents "# verifier agent pane" Enter
```

`tmux capture-pane`으로 다른 페인의 에이전트 출력을 읽어서 오케스트레이터에게 전달하는 자동화도 가능하다. ([tmux 정리](../linux/tmux.md) 참고)

---

## 실무 활용 패턴

### 대규모 리팩터링

한 에이전트가 전체 코드베이스를 분석하면 컨텍스트가 부족해진다. 모듈 단위로 에이전트를 분배해서 병렬 리팩터링 후 통합한다.

### PR 리뷰 자동화

PR이 생성되면 코드 리뷰, 보안 검토, 테스트 커버리지 분석을 각각 전문 에이전트에게 위임하고 결과를 종합한다.

### 문서화 파이프라인

코드를 탐색하는 에이전트와 문서를 작성하는 에이전트를 분리해서, 탐색 결과를 바탕으로 정확한 문서를 생성한다.

---

## 관련 문서

- [tmux — 멀티 에이전트 환경 구성](../linux/tmux.md)
- [Claude Code 스킬 시스템](./claude-code-skill-system.md)
