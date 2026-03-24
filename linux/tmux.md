# tmux — Terminal Multiplexer

"TMUX Masterclass: Terminal Multiplexing for the AI Agent Era" 영상을 보고 정리한 내용.

---

## tmux가 필요한 이유

일반 터미널 에뮬레이터(iTerm, Terminal.app 등)는 창을 닫으면 프로세스가 종료된다. tmux는 **서버 기반 세션 관리**를 제공해서 터미널 창을 닫아도 내부 프로세스가 계속 실행된다.

```
터미널 에뮬레이터:
  창 닫기 → 프로세스 종료

tmux:
  창 닫기(detach) → tmux 서버에서 세션 계속 실행
  다시 접속(attach) → 그대로 재개
```

개발 서버를 tmux에 올려두면 SSH 연결이 끊겨도, 터미널 앱을 재시작해도 서버는 계속 돌아간다.

---

## 3계층 구조

```
세션 (Session)
  └─ 윈도우 (Window)  ← 탭처럼 전환
       └─ 페인 (Pane)  ← 화면 분할
```

- **세션**: 가장 상위 단위. 프로젝트 단위로 구성하면 편하다 (백엔드 세션, 프론트엔드 세션 등)
- **윈도우**: 세션 내의 탭. 브라우저 탭과 유사
- **페인**: 윈도우를 수평/수직으로 분할한 단위. 같은 화면에 여러 터미널을 띄울 수 있다

---

## 기본 사용법 (터미널에서)

```bash
tmux            # 새 세션 시작
tmux new        # 새 세션 시작 (동일)
tmux ls         # 실행 중인 세션 목록
tmux attach     # 세션에 재접속 (tmux a 도 동일)
tmux a -t 이름  # 특정 이름의 세션에 접속
```

---

## 단축키

tmux의 모든 단축키는 **Prefix key**를 먼저 누른 뒤 입력한다. 기본 Prefix는 `Ctrl + b`.

### 세션

| 단축키 | 동작 |
|---|---|
| `Prefix + d` | 세션 빠져나오기 (detach, 세션 종료 아님) |
| `Prefix + s` | 세션 목록 보기 + 전환 |
| `Prefix + $` | 세션 이름 변경 |
| `Prefix + :new` | tmux 안에서 새 세션 생성 |

### 윈도우

| 단축키 | 동작 |
|---|---|
| `Prefix + c` | 새 윈도우 생성 |
| `Prefix + w` | 윈도우 전체 리스트 (선택해서 이동 가능) |
| `Prefix + p` | 이전 윈도우로 이동 |
| `Prefix + n` | 다음 윈도우로 이동 |
| `Prefix + 0~9` | 번호로 윈도우 바로 이동 |
| `Prefix + ,` | 윈도우 이름 변경 |

### 페인

| 단축키 | 동작 |
|---|---|
| `Prefix + %` | 수평 분할 (우측에 새 페인) |
| `Prefix + "` | 수직 분할 (아래에 새 페인) |
| `Prefix + 방향키` | 페인 간 이동 |
| `Prefix + z` | 현재 페인 최대화 / 원상복구 (zoom toggle) |

---

## .tmux.conf 설정

홈 디렉터리의 `~/.tmux.conf` 파일로 커스터마이징한다. 변경 후 `tmux source ~/.tmux.conf`로 적용.

### Prefix 키 변경

기본 `Ctrl+b`는 누르기 불편하다. `Ctrl+Space`나 `Ctrl+a`로 바꾸는 경우가 많다.

```bash
# Ctrl+Space로 변경
unbind C-b
set -g prefix C-Space
bind C-Space send-prefix
```

### 히스토리 늘리기

기본값 2,000줄은 개발 서버 로그 보기에 부족하다.

```bash
set -g history-limit 50000
```

### 마우스 활성화

마우스로 페인 클릭해서 이동하거나 경계선 드래그로 크기 조절이 가능해진다.

```bash
set -g mouse on
```

### VI 키로 페인 이동

`hjkl`로 페인 간 이동할 수 있게 설정하면 손 이동이 줄어든다.

```bash
# Alt + hjkl 로 페인 이동 (Prefix 없이)
bind -n M-h select-pane -L
bind -n M-j select-pane -D
bind -n M-k select-pane -U
bind -n M-l select-pane -R
```

### 테마 (Catppuccin)

상태바에 Git 브랜치, CPU, 메모리, 배터리, 시간을 표시하는 테마.

```bash
# TPM(Tmux Plugin Manager) 기반 설치
set -g @plugin 'catppuccin/tmux'
```

---

## AI 에이전트와 tmux 연동

tmux가 AI 에이전트 시대에 다시 주목받는 이유가 여기 있다. tmux 세션을 **프로그래매틱하게 제어**할 수 있는 CLI 명령어 덕분에, Claude Code 같은 터미널 기반 에이전트가 다른 페인이나 세션을 직접 조작할 수 있다.

### 핵심 명령어

```bash
# 특정 페인으로 명령어 전송
tmux send-keys -t 세션:윈도우.페인 "npm run dev" Enter

# 특정 페인의 출력 캡처
tmux capture-pane -t 세션:윈도우.페인 -p
```

### 활용 패턴 1 — 자동 로그 분석

한쪽 페인에 개발 서버, 다른 페인에 Claude Code를 실행해두면:

```
"0번 페인의 서버 로그를 확인해서 에러 원인 분석해줘"
```

Claude Code가 `capture-pane`으로 서버 로그를 직접 읽어와서 분석한다. 로그를 복사해서 붙여넣을 필요가 없다. 다른 세션의 윈도우 로그도 가져올 수 있다.

### 활용 패턴 2 — 스크립트로 개발 환경 일괄 구성

매번 수작업으로 페인 나누고 서버 올리는 작업을 스크립트로 자동화할 수 있다.

```bash
#!/bin/bash
# dev-setup.sh: 백엔드/프론트엔드/에이전트 환경 한 번에 구성

# 백엔드 세션
tmux new-session -d -s backend -n server
tmux send-keys -t backend:server "cd ~/project/backend && npm run dev" Enter

# 프론트엔드 세션
tmux new-session -d -s frontend -n server
tmux send-keys -t frontend:server "cd ~/project/frontend && npm run dev" Enter

# Claude Code 세션
tmux new-session -d -s agent
tmux send-keys -t agent "claude" Enter

tmux attach -t backend
```

스크립트 하나로 전체 개발 환경이 세팅된다.

### 활용 패턴 3 — 멀티 에이전트 병렬 실행

여러 페인에 각각 다른 Claude Code 인스턴스를 띄워서 병렬로 작업을 처리할 수 있다. 단일 에이전트의 컨텍스트 한계나 처리 속도 제약을 우회하는 방식이다.

```bash
# 3개 에이전트 병렬 실행
tmux split-window -h   # 수평 분할
tmux split-window -v   # 수직 분할

tmux send-keys -t 0 "claude --task 'API 구현'" Enter
tmux send-keys -t 1 "claude --task '테스트 작성'" Enter
tmux send-keys -t 2 "claude --task '문서 작성'" Enter
```

---

## 관련 도구

- **TPM (Tmux Plugin Manager)**: 플러그인 관리자. `~/.tmux/plugins/tpm`
- **yazi**: 터미널 파일 탐색기. tmux 단축키로 연동하면 `Prefix + Tab`으로 즉시 파일 탐색 가능
- **tmuxinator**: YAML로 복잡한 세션 레이아웃을 정의해서 재사용하는 도구
