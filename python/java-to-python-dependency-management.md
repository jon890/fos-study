---
series: "자바 백엔드 개발자를 위한 Python 입문"
seriesOrder: 2
---

# Python 의존성 관리 — Java Maven/Gradle 사용자가 만나는 첫 충격

자바 백엔드만 다뤄오다가 Python 프로젝트를 처음 받았을 때 가장 황당했던 게 의존성 관리였다. Maven 이면 `pom.xml` 한 파일, Gradle 이면 `build.gradle` 한 파일에서 의존성·빌드·플러그인이 다 처리된다. Python 프로젝트는 다음 파일이 섞여 있어 어디서부터 봐야 할지도 모르겠다.

- `requirements.txt`
- `pyproject.toml`
- `setup.py`
- `Pipfile`

게다가 `pip install` 한 줄로 시작하면 전역 환경이 오염되고, `venv` 가 등장하면서부터 다른 글이 또 필요하다.

이 글은 자바 개발자가 Python 의존성 도구 풍경을 빠르게 따라잡기 위한 노트다. 2026 년 기준으로 정리하면 결론은 **uv 하나면 거의 다 된다**.

## venv 가 왜 필요한가 — Java 와 결정적으로 다른 점

자바는 의존성이 프로젝트 단위로 격리된다. Maven 은 `~/.m2/repository` 에 모든 버전을 다 저장하고, 빌드 시점에 `pom.xml` 이 가리키는 버전만 클래스패스에 올린다. 같은 머신에 프로젝트 A 는 Spring 5, 프로젝트 B 는 Spring 6 가 있어도 충돌이 없다. JVM 이 시작될 때 정확한 jar 만 로딩하기 때문이다.

Python 은 다르다. `pip install requests` 를 그냥 실행하면 **시스템 Python 또는 사용자 홈 Python 의 site-packages 에 전역 설치된다**. 프로젝트 A 가 `requests 2.28` 를 쓰고 B 가 `2.32` 를 쓰면, 나중에 설치한 쪽이 이전 쪽을 덮어쓴다. Maven 으로 치면 `~/.m2` 에 같은 패키지의 한 버전만 살아 있는 셈.

이걸 해결하려고 **virtual environment** 가 들어왔다. 프로젝트마다 별도 디렉터리(`.venv/`) 를 만들고 그 안에 Python 인터프리터 사본과 의존성을 격리해 둔다. 자바로 치면 프로젝트마다 별도 `~/.m2` 를 두는 셈인데, 디스크는 좀 먹지만 격리는 확실하다.

```bash
python -m venv .venv         # .venv 생성
source .venv/bin/activate    # 활성화 (PATH 가 바뀜)
pip install requests         # 이제 .venv 안에 설치됨
```

`activate` 가 PATH 를 조작해서 `python` / `pip` 명령이 `.venv/bin/` 의 바이너리를 가리키게 한다. 셸이 닫히거나 `deactivate` 를 부르면 원래 PATH 로 돌아간다.

## pip 와 uv — 자바의 mvn/gradle 같은 명령들

`pip` 는 Python 의 기본 패키지 인스톨러다. Maven 의 `mvn install` 자리에 가깝다. 단 **pip 는 가상환경 자체를 만들지는 않는다**. `venv` 모듈이 환경을 만들고, `pip` 는 그 안에 패키지를 설치한다. 둘이 분리되어 있다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

이게 전통적 패턴이다. 단 느리다. 우리가 분석한 프로젝트의 `requirements.txt` 는 torch 2.7.1, paddleocr, docling 같은 수 GB짜리 패키지를 끌어와서 pip 로 받으면 첫 설치만 5-10분이 걸리기도 한다.

여기 등장한 것이 **uv** 다. Rust 로 작성된 의존성 매니저로, Python 패키지 매니저 진영의 게임을 바꿔놓았다. pip 대비 10-100배 빠르고, 캐시·병렬 다운로드·러스트 기반 의존성 해결자를 갖췄다. 자바에서 Maven → Gradle 로 넘어갔을 때의 속도 향상보다 더 극적이다.

uv 의 진짜 강점은 **하나의 도구가 여러 역할을 흡수**한다는 점이다.

| 자바 | Python 전통 | Python with uv |
|---|---|---|
| `sdkman` (JDK 버전 관리) | `pyenv`, `asdf` | `uv python install 3.11` |
| `mvn`/`gradle` (의존성) | `pip` | `uv pip install` |
| (없음, JVM 자체 격리) | `python -m venv` | `uv venv` |
| `pom.xml`/`build.gradle` (메타데이터) | `pyproject.toml` | `uv` 가 직접 해석 |
| `pom.xml` lock (Maven 4) | `pip freeze > requirements.txt` | `uv.lock` 자동 생성 |
| `mvnw`/`gradlew` (래퍼) | (관례 없음) | `uvx` 가 일회성 실행 |

`pyenv` + `venv` + `pip` + `pip-tools` 네 도구가 하던 일을 uv 한 명령이 한다. 자바 개발자가 Maven 하나로 의존성·빌드·라이프사이클을 처리하던 감각과 비슷해진다.

## requirements.txt vs pyproject.toml — pom.xml 의 자리

자바에서 `pom.xml` 은 두 역할을 한 파일에서 한다. 의존성 선언과 프로젝트 메타데이터. Python 은 둘이 분리되어 왔다.

**requirements.txt** 는 단순한 패키지 목록이다. `pip freeze` 결과를 그대로 받는 형태가 많다.

```text
torch==2.7.1
torchvision==0.22.1
fastapi==0.115.9
docling==2.52.0
paddleocr==3.3.2
```

장점: 단순함. CI/CD 에서 `pip install -r requirements.txt` 한 줄.
한계: Python 버전 제약을 명시할 곳이 없고, dev/prod 분리하려면 `requirements-dev.txt`, `requirements-test.txt` 파일을 추가로 만들어야 한다. 의존성 트리도 안 보인다.

**pyproject.toml** 은 자바 `pom.xml` 의 Python 버전이다. 표준 (PEP 621) 으로 정의되어 의존성·메타데이터·툴 설정 (black, ruff, pytest 등) 이 한 파일에 모인다.

```toml
[project]
name = "doc-parser"
version = "2.2.0"
requires-python = ">=3.11"
dependencies = [
    "torch>=2.7,<2.8",
    "fastapi>=0.115",
    "docling>=2.52",
]

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]

[tool.uv]
lockfile = "uv.lock"
```

자바 Maven 의 `<dependencies>` + `<properties>` + `<build><plugins>` 가 한 파일에 들어가는 그림. dev 의존성은 `optional-dependencies` 로 분리해 `uv sync --extra dev` 처럼 선택 설치.

## lock 파일 — Maven `dependency:resolve` 의 자동화

Maven 은 빌드할 때마다 의존성 트리를 다시 푼다 (resolve). 그래서 같은 코드라도 빌드 시점에 따라 transitive dependency 가 살짝 달라질 수 있다. Maven 4 에서 lockfile 이 정식 도입되어 이 문제를 해결하기 시작했지만, Gradle 도 `dependency-locking` 을 명시적으로 켜야 동작한다.

Python 의 `pip freeze` 는 사실상 수동 lock 이다. 개발자가 환경을 다 세팅한 뒤 `pip freeze > requirements.txt` 로 현재 버전을 박제하는 방식. 까먹으면 다른 사람과 환경이 어긋난다.

uv 는 `uv.lock` 을 자동 생성·갱신한다. `uv add fastapi` 한 줄이면 `pyproject.toml` 에 `fastapi` 를 추가하고 `uv.lock` 에 transitive 까지 박힌다. Gradle 의 `--write-locks` 가 자동으로 켜져 있는 셈.

```bash
uv add fastapi              # pyproject.toml + uv.lock 동시 갱신
uv sync                     # 락 그대로 .venv 에 설치
uv sync --frozen            # 락 변경 안 됨 보장 (CI 권장)
```

자바 Gradle 의 `./gradlew dependencies --update-locks` 처럼 명시적 명령이 필요하지 않다.

## 실제로 셋업하면서 마주친 함정들

Mac 에서 이 프로젝트의 로컬 개발 환경을 세팅하면서 부딪힌 것들을 그대로 기록한다.

### asdf 또는 pyenv 로 만든 venv 의 깨진 심볼릭 링크

`.venv/bin/python` 은 보통 시스템에 설치된 Python 인터프리터로 향하는 심볼릭 링크다. 내가 받은 프로젝트는 과거에 `asdf` 로 설치한 Python 3.13.9 로 `.venv` 를 만들었는데, 그 사이 `asdf` 를 정리하면서 `~/.asdf/installs/python/3.13.9/bin/python` 이 사라져 링크가 깨졌다. `.venv/bin/python --version` 이 "no such file or directory" 로 죽는다.

해결책은 `.venv` 통째로 다시 만드는 것.

```bash
uv venv .venv --clear --python 3.11
```

`--clear` 는 기존 디렉터리를 지우고 새로 만든다. `--python 3.11` 은 uv 가 Python 3.11 을 알아서 다운로드해 박아준다 (없으면 `uv python install 3.11` 먼저).

### uv venv 에는 pip 가 들어 있지 않다

전통적 `python -m venv .venv` 는 venv 안에 `pip` 를 같이 깔아준다. 그런데 `uv venv` 는 기본적으로 **pip 를 포함하지 않는다**. 빠르게 만들기 위해서다.

```bash
.venv/bin/pip install -r requirements.txt
# zsh: no such file or directory: .venv/bin/pip
```

이 메시지 처음 봤을 때 한참 헤맸다. uv 가 권장하는 방식은 그냥 `uv pip install ...` 또는 `uv add ...` 다. uv 자체가 pip 와 동등한 명령을 직접 제공한다.

```bash
VIRTUAL_ENV=$(pwd)/.venv uv pip install -r requirements.txt
```

또는 `source .venv/bin/activate` 후 `uv pip install -r requirements.txt`. uv 는 활성화된 venv 를 자동 인식한다.

### Apple Silicon 에서 CUDA 패키지

이 프로젝트의 운영 환경은 NVIDIA T4 GPU. Mac M-series 는 CUDA 를 지원하지 않는다. `requirements.txt` 가 `torch==2.7.1` 만 박혀 있으면 Mac 에서는 자동으로 MPS (Metal Performance Shaders) 빌드를 받는다. `pynvml` 같은 NVIDIA 전용 라이브러리는 import 자체는 되지만 런타임에 사용할 일이 없다 (워닝만 뜬다).

paddlepaddle 도 Mac M-series 용 빌드가 한정적이라 Dockerfile 에서는 별도 인덱스로 paddlepaddle-gpu 를 설치하고 Mac 에서는 paddlepaddle (CPU) 만 받는다. 운영과 로컬의 의존성 분리 지점.

자바 개발자 입장에서 "JVM 은 어디서든 똑같이 도는데" 와 비교되는 부분. Python ML 라이브러리는 OS·아키텍처·GPU 종류에 따라 휠 (wheel) 이 달라진다.

## 권장 워크플로

자바 백엔드에서 Python 으로 넘어올 때 처음부터 익히면 좋은 명령은 다섯 개다.

```bash
# 1. Python 버전 설치
uv python install 3.11

# 2. 프로젝트 venv 만들기
uv venv .venv --python 3.11

# 3. pyproject.toml 의존성 설치
uv sync

# 4. 패키지 추가
uv add fastapi

# 5. CI 에서 락 고정한 채 설치
uv sync --frozen
```

`pip install` 을 직접 칠 일이 거의 없다. 자바에서 `mvn install` 만 알면 90% 의 케이스가 처리되는 것과 비슷.

기존 `requirements.txt` 만 있는 프로젝트라도 uv 가 그대로 읽어준다.

```bash
uv pip install -r requirements.txt
```

이 형태는 점진적 이전 경로다. 새 프로젝트는 처음부터 `pyproject.toml` 로 시작하는 것을 권장한다.

## 다음 글로 넘기는 것

이 글은 의존성 도구만 다뤘다. 본격적으로 Python ML 서비스를 다루려면 GPU·CUDA·PyTorch 모델 로딩 비용 같은 인프라 개념이 필요한데, 그건 다음 글에서 정리한다.

자바와 비교했을 때 가장 큰 차이는 다음 한 줄로 요약된다.

> 자바는 JVM 이 의존성 격리를 책임지고, Python 은 가상환경 + 락파일이 사람의 협업으로 격리를 책임진다.

uv 가 등장하면서 그 사람의 부담이 크게 줄었다. 2026 년 시점이면 새 Python 프로젝트는 uv 부터 깔고 시작해도 후회 없다.

## 참고

- [uv 공식 문서](https://docs.astral.sh/uv/)
- [PEP 621 — Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [Real Python — uv vs pip: Managing Python Packages and Dependencies](https://realpython.com/uv-vs-pip/)
- [pydevtools — Why pyproject.toml over requirements.txt](https://pydevtools.com/handbook/explanation/pyproject-vs-requirements/)
- [DataCamp — Python UV Complete Guide](https://www.datacamp.com/tutorial/python-uv)
