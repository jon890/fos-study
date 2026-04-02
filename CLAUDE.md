# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

개인 기술 블로그 겸 학습 기록 저장소. 마크다운 파일로 구성되며 GitHub 자동 sync를 통해 블로그에 게시된다. 빌드/테스트 명령어 없음 — 파일 작성과 구조 관리가 주 작업이다.

## 폴더 구조와 배치 기준

```
fos-study/
├── task/               # 회사 업무 기록 (팀별 하위 디렉터리)
├── architecture/       # 설계 패턴, 원칙 등 언어/기술 독립적 개념
├── database/           # 데이터 스토어 전반
│   ├── mysql/
│   ├── opensearch/
│   └── redis/
├── java/               # Java 언어 및 Spring 생태계
│   ├── spring/
│   ├── spring-batch/
│   └── ...
├── devops/             # 인프라, 배포, 모니터링
│   ├── docker/
│   ├── k8s/
│   └── monitoring/
├── kafka/              # 메시지 브로커 (database가 아닌 최상위 유지)
├── network/            # HTTP, 인터넷 프로토콜 등
├── algorithm/
├── AI/
└── ...
```

### 폴더 배치 결정 기준

- **database/** — 데이터를 저장·검색하는 스토어. MySQL, OpenSearch, Redis 포함. Kafka는 메시지 브로커라 최상위 유지
- **task/** — 실제 업무 구현 경험. 개념 설명 아닌 "내가 이걸 왜, 어떻게 만들었나" 기록
- **architecture/** — 특정 기술에 종속되지 않는 설계 개념 (전략 패턴 등). 실제 사례 링크는 포함하되 사례 본문은 `task/`에 작성
- 신규 기술 문서는 기존 최상위 폴더에 맞는 게 없을 때만 새 폴더 생성

## 문서 작성 규칙

### 개념 문서 vs 업무 기록 분리

- `architecture/`, `database/`, `java/` 등: 기술 개념 설명. 언제 읽어도 유효한 내용
- `task/<팀명>/`: 특정 시점의 구현 경험. 진행 기간 헤더 필수, 민감 정보 제거

### 민감 정보 제거 기준

업무 기록(`task/`) 작성 시:

- 회사명, 팀명, 내부 시스템 이름 → 일반 표현으로 대체 (예: Dooray → "사내 협업 도구")
- 내부 URL, IP → 제거 또는 `<내부-엔드포인트>` 로 대체
- 오픈소스 도구명(OpenSearch, Spring Boot 등)은 그대로 유지

### 코드 예시 검증

문서에 코드 블록을 포함할 때는 반드시 실제 코드에서 클래스명·메서드명·필드명을 확인 후 기재. 기억에 의존한 재현 금지.

### 마크다운 Bold + 괄호 패턴

`**텍스트(영문)**` 형태는 일부 파서에서 bold가 렌더링되지 않는다.
반드시 `**텍스트**(영문)` 형태로 작성한다.

- 올바른 예: `**구조**(harness)`, `**제어**(Control)`
- 잘못된 예: `**구조(harness)**`, `**제어(Control)**`

메서드명처럼 괄호가 이름의 일부인 경우(`**canRetry()**`)는 코드 인라인으로 표기한다: `` `canRetry()` ``

### 하위 문서 링크

관련 상세 문서가 저장소 내에 있으면 상대 경로로 링크. 링크 전 파일 존재 여부 확인.

## task/ 구조

`task/AGENTS.md`에 팀별 디렉터리 목록과 문서 작성 가이드 상세 포함.

각 팀 디렉터리의 `README.md`:

- 문서 목록 테이블 (신규 구현 / 리팩터링 등 카테고리 구분)
- 기간별 주요 업무 요약
- 기술 키워드 태그

새 문서 추가 시 해당 팀 `README.md`도 함께 업데이트.
