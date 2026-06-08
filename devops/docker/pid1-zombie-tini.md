# Docker에서 좀비 프로세스가 쌓이는 이유 — PID 1 문제와 tini

운영 중인 문서 파싱 서비스 인스턴스에 들어가서 `ps`를 쳤다가, `soffice.bin <defunct>` 가 화면을 가득 채우는 걸 봤다. 세어보니 420개였다. 컨테이너가 뜬 지 일주일밖에 안 됐는데 좀비가 420마리.

처음엔 "좀비는 메모리도 거의 안 먹는다는데 그냥 둬도 되나?" 싶었다. 그런데 좀비는 PID 슬롯을 하나씩 점유한다. 계속 쌓이면 결국 PID가 고갈되고, 그러면 새 프로세스를 `fork` 하지 못해 서비스 전체가 멈춘다. 무시할 문제가 아니었다.

이 글은 내가 그 420개의 정체를 추적하면서 다시 정리한 리눅스 프로세스의 기초 — 좀비와 고아의 차이, PID 1이 왜 특별한지, 그리고 tini가 무슨 일을 하는지에 대한 기록이다.

## 좀비가 뭔지부터 — 종료했는데 안 사라지는 프로세스

리눅스에서 자식 프로세스가 `exit()` 로 종료해도 곧바로 사라지지 않는다. 커널은 그 프로세스의 최소 정보(PID, 종료 코드, CPU 사용 시간)를 프로세스 테이블에 남겨둔다. 부모가 자식의 종료 상태를 **거둬갈(reap) 때까지** 기다리는 것이다.

이 "종료했지만 아직 거둬지지 않은" 상태가 바로 **좀비**(zombie, `Z` 또는 `<defunct>`)다.

부모가 자식을 거두는 방법은 `wait()` / `waitpid()` 시스템 콜이다. 흐름은 이렇다:

1. 자식이 종료한다.
2. 커널이 부모에게 `SIGCHLD` 시그널을 보낸다 — "네 자식 하나가 죽었어."
3. 부모가 `wait()` 를 호출해 종료 상태를 읽어간다.
4. 그 순간 커널은 프로세스 테이블에서 자식의 엔트리를 지운다. 좀비 소멸.

문제는 **부모가 `wait()` 를 안 부를 때**다. 부모에 버그가 있거나, `SIGCHLD` 를 무시하도록 짜여 있으면 자식은 영원히 좀비로 남는다. 좀비는 자기 스스로 사라질 수 없다. 거두는 건 전적으로 부모(또는 부모를 대신할 누군가)의 책임이다.

```c
// 부모가 SIGCHLD 핸들러에서 죽은 자식을 모두 거두는 전형적 패턴
// (개념 설명용)
void reap(int sig) {
    while (waitpid(-1, NULL, WNOHANG) > 0)
        ;  // 거둘 자식이 없을 때까지 반복
}
```

## 고아는 좀비와 다르다 — 부모가 먼저 죽은 경우

좀비랑 헷갈리기 쉬운 게 **고아**(orphan)다. 둘은 방향이 반대다.

- **좀비**: 자식이 먼저 죽었는데 부모가 안 거둬감 (자식은 이미 죽은 상태)
- **고아**: 부모가 먼저 죽었는데 자식은 아직 살아서 돌아감 (자식은 멀쩡히 실행 중)

부모가 죽으면 그 밑의 살아있는 자식들은 고아가 된다. 그런데 리눅스에서 고아는 떠돌게 두지 않는다. **PID 1 프로세스(init)가 고아를 입양**한다. 고아의 부모 PID가 1로 바뀐다.

여기서 두 개념이 만난다. **고아가 나중에 종료하면, 입양한 PID 1이 그 고아를 거둬야 한다.** PID 1이 제대로 `wait()` 를 부르는 init이면 고아는 종료 즉시 거둬져 깨끗이 사라진다. 그런데 PID 1이 거두는 일을 안 하면? 고아가 죽은 자리에 좀비가 남고, 그게 계속 쌓인다.

내가 본 420개가 정확히 이 경우였다.

## PID 1은 왜 특별한가

컨테이너든 일반 리눅스든, PID 1 프로세스에는 일반 프로세스에 없는 두 가지 의무가 따라붙는다.

**첫째, 고아 reaping.** 위에서 말한 대로 모든 고아는 PID 1이 입양하고, 그 고아들이 종료하면 PID 1이 거둬야 한다. init 계열 프로그램(systemd, tini 등)은 이걸 위해 주기적으로 `wait()` 를 돈다.

**둘째, 시그널 처리.** PID 1은 커널로부터 시그널에 대한 **기본 핸들러를 받지 못한다**. 일반 프로세스라면 `SIGTERM` 을 받으면 기본 동작으로 종료하지만, PID 1은 명시적인 핸들러를 등록하지 않는 한 `SIGTERM` 을 그냥 무시한다. `docker stop` 을 쳤을 때 컨테이너가 10초를 버티다 강제 종료(`SIGKILL`)되는 흔한 현상이 바로 이것이다 — PID 1이 된 앱이 `SIGTERM` 을 못 받아서 graceful하게 안 죽는 것이다. (이 시그널 쪽 이야기는 [Graceful Shutdown](../graceful-shutdown.md) 에서 더 다뤘다.)

문제는, **우리가 컨테이너에 띄우는 앱 대부분은 init이 아니라는 점**이다. uvicorn, gunicorn, node, java… 이들은 웹 서버나 애플리케이션 런타임이지, "버려진 자식 뒷정리"를 하라고 만들어진 프로그램이 아니다. 그런데 `docker run`으로 앱을 직접 띄우면 그 앱이 PID 1이 된다. init이 할 일을 떠안지만 할 줄은 모르는 상태가 된다.

> PID 1은 직책이지 능력이 아니다. uvicorn을 PID 1 자리에 앉혀도, uvicorn이 고아를 거두는 법을 배우는 건 아니다.

## 내 케이스 — LibreOffice가 좀비를 만든 경로

420개의 정체를 추적한 과정은 단순했다.

```bash
# 좀비만 세기 — STAT가 Z로 시작하는 것
ps -eo stat,ppid,pid,comm | awk '$1 ~ /^Z/' | wc -l
# → 420

# 부모 PID별로 묶어보기
ps -eo stat,ppid,pid,comm | awk '$1 ~ /^Z/ {print $2}' | sort | uniq -c | sort -rn
# → 420개 전부 같은 부모 PID 하나

# 그 부모가 누구인가
ps -p <부모PID> -o comm,args
# → uvicorn (컨테이너의 PID 1)

# 좀비들의 정체
ps -eo stat,ppid,pid,comm | awk '$1 ~ /^Z/' | head
# → 전부 soffice.bin <defunct>
```

좀비 420개가 전부 `soffice.bin` 이고, 부모는 PID 1인 uvicorn이었다. 그림이 그려졌다.

이 서비스는 `.doc`, `.ppt` 같은 구버전 오피스 파일을 받으면 LibreOffice를 headless 모드로 띄워 PDF로 변환한다. 코드는 이렇게 생겼다.

```python
# 개념 설명용 의사코드
proc = subprocess.Popen(
    ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", out, src]
)
proc.communicate(timeout=180)  # libreoffice 프로세스가 끝나길 기다림
```

`communicate()` 가 `wait` 를 포함하니까 거두는 것 같은데, 왜 좀비가 쌓일까. 함정은 **`libreoffice` 명령이 실제 작업 프로세스가 아니라 런처(wrapper)라는 점**이었다.

`libreoffice` 를 실행하면 그건 내부적으로 `soffice.bin` 을 띄우고 변환 작업을 넘긴 뒤 **런처 자신은 먼저 종료**한다. 그래서 일어나는 일:

1. 워커가 `libreoffice` 런처를 `Popen` 으로 띄운다.
2. 런처가 `soffice.bin` 을 spawn 한다.
3. 런처가 먼저 끝난다 → `communicate()` 는 **런처만** 거둔다.
4. `soffice.bin` 은 부모(런처)가 죽었으니 **고아**가 된다 → PID 1(uvicorn)이 입양.
5. `soffice.bin` 이 변환을 마치고 종료한다 → 입양한 PID 1이 거둬야 하는데…
6. uvicorn은 reaper가 아니다 → `soffice.bin` 이 **좀비로 남는다.**

`.doc`/`.ppt` 변환 요청이 한 번 들어올 때마다 좀비가 하나씩 쌓였다. 일주일에 420개. 코드의 `communicate()` 나 `finally` 정리 블록은 **런처**를 다룰 뿐이고, 고아가 된 손주 `soffice.bin` 은 어느 경로로도 거둬지지 않았다.

핵심은 코드의 버그라기보다 **구조의 문제**였다. 손주 프로세스가 고아가 되는 건 LibreOffice 런처의 동작 방식이라 코드로 일일이 막기 까다롭다. 진짜 빈자리는 **PID 1에 reaper가 없다는 것**이었다.

## tini — PID 1 자리에 앉히는 최소 init

이 문제의 정석 해법이 [tini](https://github.com/krallin/tini)다. 수십 KB짜리 단일 바이너리로, 오직 컨테이너의 PID 1 노릇을 하려고 만들어진 미니 init이다. 하는 일은 딱 두 가지다.

**고아 reaping.** tini는 PID 1로 앉아서, 입양한 고아들이 종료하면 주기적으로 `wait` 를 돌며 거둬간다. soffice.bin이 고아가 되어 tini에게 입양되면, 종료하는 즉시 tini가 거둬서 좀비가 안 쌓인다.

**시그널 forwarding.** tini는 `SIGTERM`, `SIGINT` 같은 시그널을 받아 자식(실제 앱)에게 그대로 전달한다. 덕분에 `docker stop` 이나 `Ctrl+C` 가 앱까지 도달해서 graceful shutdown이 정상 동작한다. PID 1이 시그널을 무시하던 문제가 풀린다.

비유하자면, uvicorn은 "웹 서버 일"만 하는 전문가다. 집안에 버려진 아이들 뒷정리(reaping)와 현관 초인종 응대(시그널)는 관리인의 일인데, uvicorn은 관리인이 아니다. tini는 그 관리인 역할만 가볍게 맡는다. uvicorn은 자기 일에 집중하고, tini가 PID 1의 잡일을 처리한다.

## 적용 — Dockerfile 한 곳 vs `--init` 매번

tini를 넣는 방법은 크게 둘이다.

**`docker run --init`.** Docker가 내장 init(tini와 같은 메커니즘)을 PID 1에 자동으로 끼워준다. 가장 간단하지만, **컨테이너를 띄우는 모든 경로에 매번 `--init` 을 붙여야 한다.** 수동 `docker run`, 배포 스크립트, 배포 도구 콘솔 설정… 한 곳이라도 빠지면 그 컨테이너는 좀비가 다시 쌓인다. 앞으로 새 실행 경로가 생길 때마다 또 챙겨야 하는 영구적인 누락 위험이 있다.

**Dockerfile ENTRYPOINT를 tini로 감싸기.** 이미지 자체에 init을 박는 방법이다.

```dockerfile
# ubuntu 계열이면 apt 한 줄로 설치
RUN apt-get install -y tini

# 기존
# ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# 변경 — tini를 PID 1로
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
```

이러면 tini가 PID 1이 되고, 그 아래에서 엔트리포인트 스크립트와 앱이 돈다. **누가 어떤 방법으로 띄우든**(수동 run이든 배포 도구든) 이미지에 init이 들어있으니 항상 적용된다. 새 실행 경로가 생겨도 자동으로 커버된다.

직관적으로는 "이미지 안 건드리는 `--init` 이 간단하지 않나" 싶지만, 실제로는 반대다. `--init` 은 손댈 곳이 여러 군데인데다 미래 누락 위험이 영구적이고, Dockerfile tini는 **한 곳을 고치면 끝**이다. 나는 단일 지점이라는 이유로 Dockerfile 방식을 택했다.

한 가지 더 — 엔트리포인트 스크립트가 내부에서 분기를 타거나(예: GPU MPS 모드 on/off) 앱을 백그라운드로 띄우는 경우가 있다. 이때 tini를 스크립트 안의 `exec` 줄에만 넣으면 한쪽 분기만 커버될 수 있다. ENTRYPOINT 최상위를 tini로 감싸면 **스크립트 내부 동작과 무관하게** tini가 항상 최상위 PID 1이라, 모든 분기의 고아를 거둔다. 그래서 스크립트를 건드리는 것보다 ENTRYPOINT를 감싸는 쪽이 안전했다.

## 지금 보면

좀비를 처음 봤을 때 "메모리 안 먹으니 괜찮겠지"라고 넘겼다면, PID 고갈로 서비스가 멈춘 뒤에야 원인을 찾았을 거다. 좀비는 양성이지만 **누적은 양성이 아니다.** 증상이 가벼워 보여도 누적되는 종류의 문제는, 발견 시점에 한가하더라도 끝까지 따라가 보는 게 맞다.

그리고 이번 일로 다시 새긴 건, **컨테이너에서 PID 1이 누구인지는 항상 의식해야 할 질문**이라는 점이다. `docker run app` 처럼 무심코 앱을 직접 띄우면 그 앱이 init의 의무를 떠안는다. 평소엔 자식 프로세스를 안 만드니 티가 안 나다가, LibreOffice처럼 손주 프로세스를 고아로 흘리는 코드가 끼는 순간 좀비가 새어나온다. 베이스 이미지에 init을 깔아두는 건 "지금 당장 필요해서"가 아니라 **"언제 필요해질지 모르니까"** 미리 해두는 보험에 가깝다.

마지막으로, 이건 우리 코드의 LibreOffice 호출 방식이 만든 특수한 사례지만 — 자식·손주 프로세스를 띄우는 컨테이너라면 어디서든 같은 함정에 빠질 수 있다. PID namespace 안에서 PID 1이 갖는 역할은 [리눅스에서 프로세스를 격리시키는 방법](./linux-process-isolation.md) 과도 이어진다.

## 참고

- [tini — A tiny but valid init for containers (GitHub)](https://github.com/krallin/tini)
- [Zombie process (Wikipedia)](https://en.wikipedia.org/wiki/Zombie_process)
- [Docker and the PID 1 zombie reaping problem (Hacker News 토론)](https://news.ycombinator.com/item?id=8916785)
- [Why Your Docker Containers Refuse to Die: The PID 1 Problem (DEV)](https://dev.to/alanwest/why-your-docker-containers-refuse-to-die-the-pid-1-problem-e70)
- [Container Init Process (DevOps Directive)](https://devopsdirective.com/posts/2023/06/container-init-process/)
