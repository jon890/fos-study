# Cursor CLI

- 다른 Claude Code, Gemini CLI, Codex와 같이 Cursor에서도 CLI (Command Line Interface)에서 사용할 수 있는 프로그램이 개발되었다
- [공식 홈페이지](https://cursor.com/cli)

<br />

- 개인적인 경험이지만 Gemini CLI는 아직 뭔가 만듬새가 아쉽다.
  - 대화 중에, 갑자기 무한루프에 빠지면서 내가 했던 대화가 다시 노출되면서, 진행되지 않는 현상이 너무 빈번함.
- Claude Code를 사용해보고 싶은데, 비용을 또 결제해야하는 부담이 있었음..
  - 잘 사용했던 Cursor 제품이었으니깐, CLI도 잘 만들었을 것 같아서 CLI로 사용해보기로 결정
  - Java, Spring 개발에서는 IntelliJ가 거의 표준처럼 사용되다보니, Cursor에서 코딩 후, 왔다갔다하는게 생각보다 불편했음

## 설치 및 실행

```bash
# 설치
curl https://cursor.com/install -fsS | bash

# zsh 사용할 경우 환경변수 등록
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Agent 실행
cursor-agent
```

## 특징

### 파일 참조

다른 CLI들과 비슷하게 `@`를 입력하면, 프로젝트 내의 파일을 참조할 수 있음

![add-file-to-context](./image/add-file-to-context.png)

개인적으로, 아래와 같이
Agent Workflow를 정의하여, 해당 작업을 수행할 떄 컨텍스트로 전달하는 것을 선호하고 있음

![add-file-to-context2](./image/add-file-to-context2.png)

### Rules

- IDE에서 사용하던 것과 같은 방식의 Cursor Rules도 적용됨
  - Rule System에 의해 자동으로 적용
- 개인적으로는 아직까지는 여러 제품들이 경쟁적으로 나오고 있다보니, 그나마 표준적인 AGENTS.MD로 루트 컨텍스트를 공유할 수 있도록만 하는게 좋은 것 같습니다.
  - Cursor에서도 AGENTS.MD가 있다면, Rule로 인식하여 Context에 첨부되는 방식으로 작동합니다.
  - 개별 Agent Workflow는 `docs/agents` 정도의 폴더를 만들어서 관리하는 방식을 현재는 선호합니다.
- 참고
  - Rules : https://cursor.com/docs/context/rules

### 이전 대화 재개

- LLM을 사용하던 것 처럼, 이전 대화내역을 이어서 대화할 수 있습니다.
- 사용 방법은 다음과 같습니다
  – 대화 목록을 조회합니다.
  - 원하는 대화를 선택하고, 엔터를 누르면 이전 대화가 이어서 진행됩니다.

```bash
cursor-agent ls
```

![resume-last-chat](./image/resume-last-chat.png)

### 대화 도중 명령어 실행

- 대화도중 또다른 터미널을 열어서 명령어를 수행할 수 도 있지만, 대화 도중 명령어를 수행할 수 있도록하면 더 편함

```bash
# 예시 gradle test 수행
/shell ./gradlew test
! ./gradlew test # ! 는 alias라고 생각하면 됨
```
