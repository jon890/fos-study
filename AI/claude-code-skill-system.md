# Claude Code의 Skill 시스템 - 개발자를 위한 AI 자동화의 새로운 차원

최근 Claude Code를 쓰면서 느낀 생각이 있다. "이게 진짜 내 개발 경험을 바꿀 수 있겠다"는 확신이었다. 특히 **Skill 시스템**이라는 개념을 알게 된 이후로는 더욱 그렇다.

혹시 Claude Code를 써본 적 있는가? 그렇다면 `/commit`, `/review-pr`, `/pdf` 같은 명령어들을 마주쳤을 것이다. 이것들이 바로 **Skill**이다. 마치 터미널의 커스텀 명령어처럼, Claude Code에서 복잡한 워크플로우를 한 줄의 명령으로 실행할 수 있게 해주는 재사용 가능한 프롬프트와 자동화다.

이 글에서는 Skill이 정확히 무엇인지, 어떻게 쓰는지, 그리고 나만의 Skill을 만들어서 개발 생산성을 어떻게 높일 수 있는지 실제 경험 중심으로 풀어보겠다.

---

## 1. Skill이란 정확히 무엇인가?

### 기본 개념: 재사용 가능한 워크플로우

Skill은 다음과 같이 정의할 수 있다:

> **특정한 작업을 수행하기 위해 사전에 정의된 프롬프트, 도구 호출 순서, 그리고 로직을 묶어둔 재사용 가능한 자동화 단위**

일반적인 프롬프팅은 매번 상세한 지시사항을 적어야 한다.

```
Claude, 다음 코드를 검토해줄 수 있을까?
- 성능 이슈는 없는지
- 보안 취약점은 없는지
- 읽기 쉬운 코드인지
위 세 가지 관점에서 피드백을 줘.
```

하지만 Skill을 쓰면 한 줄이면 된다.

```
/review-code
```

차이가 느껴지는가? 이것이 Skill의 가치다. **반복되는 작업의 복잡성을 숨기고, 필요할 때 한 명령으로 꺼낼 수 있게 해준다.**

### Skill이 할 수 있는 것

Claude Code의 built-in Skill들은 매우 다양하다:

- **autopilot**: 프로젝트 상황을 분석해서 자동으로 다음 해야 할 일을 찾아주고 실행
- **ralph**: 반복적인 코드 작업을 지능적으로 처리 (변수명 변경, 리팩토링 등)
- **ultrawork**: 집중해서 여러 파일을 동시에 수정해야 할 때 사용
- **team**: 여러 AI 에이전트를 팀처럼 조율해서 복잡한 프로젝트를 병렬 처리
- **debugger**: 버그를 자동으로 찾고 수정하려는 시도
- **reviewer**: 코드 리뷰를 자동화

이 모든 것들이 백그라운드에서 이미 검증된 프롬프트와 도구 호출 체인(chain)으로 작동한다.

---

## 2. Oh-My-Claudecode의 Built-in Skills 둘러보기

Claude Code는 기본적으로 제공하는 Skill들이 있다. 특히 **oh-my-claudecode** 프로젝트에서 제공하는 skills들이 강력하다.

### 자주 쓰이는 Built-in Skills

#### 2.1 Autopilot

프로젝트 상태를 보고 자동으로 다음 액션을 생각해내서 실행한다.

```bash
/oh-my-claudecode:autopilot
```

내 경험상 이걸 실행하면:
1. 현재 프로젝트의 상태를 분석 (README, 소스코드, 테스트 상태 등)
2. 할 일 리스트를 생성
3. 우선순위를 정해서 하나씩 실행

특히 새로운 프로젝트에 들어갔을 때, 또는 오랜만에 옛날 코드를 봐야 할 때 정말 유용하다.

#### 2.2 Ralph

반복적인 수정 작업들을 모두 한 번에 처리한다. 변수명을 바꾼다거나, 패턴이 비슷한 코드들을 일괄 리팩토링할 때.

```bash
/oh-my-claudecode:ralph "변수명 oldName을 newName으로 전체 변경"
```

Ralph는 한 번에 여러 파일을 수정할 수 있고, 각 수정 사항을 검증해서 실수를 방지한다.

#### 2.3 Ultrawork

복잡한 다중 파일 작업을 집중해서 처리한다. 특히 전체 구조 변경이 필요할 때.

```bash
/oh-my-claudecode:ultrawork "전체 프로젝트를 TypeScript strict mode로 마이그레이션"
```

이 명령어는 단순한 일괄 처리가 아니라, 각 파일의 타입 체크 에러를 하나씩 해결해나가는 식으로 작동한다.

#### 2.4 Team

여러 개의 AI 에이전트를 팀으로 구성해서 동시에 다른 작업을 처리한다. 예를 들어:
- 한 에이전트는 API 엔드포인트 작성
- 다른 에이전트는 테스트 코드 작성
- 또 다른 에이전트는 문서 작성

모두 동시에 병렬로 진행되고, 마지막에 통합된다.

```bash
/oh-my-claudecode:team 3
```

(3명의 에이전트로 팀 구성)

---

## 3. Skill 사용하기

### 기본 사용법

#### 방법 1: Slash Command

가장 간단한 방법이다.

```
/oh-my-claudecode:autopilot
```

채팅 인터페이스에 위 명령어를 입력하면, Claude Code가 해당 Skill을 즉시 실행한다.

#### 방법 2: Skill Tool

프롬프트나 다른 자동화 워크플로우 내에서 Skill을 호출할 때는 **Skill Tool**을 사용한다.

```python
# 내부적으로 이렇게 호출됨
Skill(skill="autopilot")
```

### 실제 사용 사례

**케이스 1: 새 프로젝트 시작**

```
/oh-my-claudecode:autopilot
```

→ 프로젝트 구조 분석 → package.json 확인 → 테스트 상태 확인 → 빌드 가능한지 확인 → 다음 해야 할 일 제시

**케이스 2: 버그 찾기**

```
/oh-my-claudecode:debugger "로그인 API에서 토큰이 null로 반환되는 문제"
```

→ 해당 코드 분석 → 문제점 파악 → 수정 시도 → 테스트 실행 → 결과 보고

**케이스 3: 대규모 리팩토링**

```
/oh-my-claudecode:ultrawork "모든 console.log 제거하고 logger 사용으로 통일"
```

→ 모든 파일 순회 → console.log 찾기 → logger 임포트 추가 → 치환 → 타입 체크

---

## 4. Skill Creator: 나만의 Skill 만들기

여기부터가 정말 신나는 부분이다. built-in Skill들도 좋지만, **나만의 Skill을 만들어서 반복되는 내 개발 패턴을 자동화할 수 있다.**

### 4.1 기존 대화에서 Skill 추출하기 (learner)

가장 쉬운 방법이다. 이미 한 번 성공적으로 해낸 작업이 있다면, 그것을 Skill로 만들 수 있다.

```
/oh-my-claudecode:learner "이전 대화에서 했던 Spring Boot 프로젝트 셋업을 skill로 만들어줄래?"
```

learner는 당신의 대화 이력을 분석해서:
1. 반복되는 패턴을 찾음
2. 도구 호출 순서를 정리
3. 변수화할 부분을 식별
4. 새로운 Skill 정의 파일 생성

### 4.2 skill-creator로 처음부터 만들기

더 커스텀한 Skill을 만들고 싶다면 **skill-creator**를 사용한다.

```
/oh-my-claudecode:skill-creator
```

이 명령어를 실행하면:

```
당신의 새로운 Skill을 만들겠습니다.

1. Skill의 이름은?
   → my-db-migration

2. 이 Skill이 하는 일을 설명해주세요
   → 기존 MySQL 테이블을 PostgreSQL로 마이그레이션하는 자동화

3. 필요한 도구들은? (선택지 제시)
   → Bash, Read, Edit, Grep

4. Skill이 실행될 순서는?
   → 1) MySQL 스키마 덤프
   → 2) PostgreSQL 호환 문법으로 변환
   → 3) 타입 매핑 확인
   → 4) 마이그레이션 스크립트 생성
```

이런 식으로 대화형 인터페이스를 통해 나만의 Skill을 정의할 수 있다.

### 4.3 실제 Skill 정의 파일 예시

Skill이 정의되면 보통 다음과 같은 파일 구조로 저장된다:

```yaml
# ~/.claude/agents/my-db-migration.md

---
name: my-db-migration
description: MySQL에서 PostgreSQL로 스키마 마이그레이션 자동화
triggers:
  - "db migration"
  - "mysql to postgres"

steps:
  1. 현재 MySQL 스키마 분석
  2. DDL 구문 파싱
  3. PostgreSQL 호환 문법 변환
  4. 데이터 타입 매핑
  5. 검증 및 테스트
---

## 이 Skill이 하는 일

MySQL의 테이블 구조를 PostgreSQL로 변환합니다.
- AUTO_INCREMENT → SERIAL
- VARCHAR → character varying
- DATETIME → timestamp
등의 변환을 자동으로 처리합니다.
```

정의된 Skill은 이제 다음과 같이 사용할 수 있다:

```
/my-db-migration "users 테이블을 PostgreSQL로 변환해줄래?"
```

---

## 5. Skill 성능 테스트와 벤치마크

만든 Skill이 제대로 작동하는지 검증하는 것도 중요하다.

### Skill 테스트하기

```bash
/oh-my-claudecode:skill-test "my-db-migration"
```

이 명령어는:
1. 테스트 프로젝트 생성
2. Skill 실행
3. 결과 검증
4. 성능 측정
5. 리포트 생성

### 실제 벤치마크 예시

내가 만든 `auto-docstring` Skill의 성능 테스트 결과:

```
Skill: auto-docstring
테스트 파일: 50개 Python 함수

결과:
- 성공률: 98% (49/50)
- 평균 처리 시간: 2.3초/함수
- 토큰 사용량: 약 1,200 tokens/함수

실패 케이스:
- 1개: 복잡한 제네릭 타입 함수에서 docstring 형식 오류
  → 후처리 규칙 추가로 개선 가능
```

이런 식으로 Skill의 신뢰성을 미리 검증하고 개선할 수 있다.

---

## 6. 실제 사용 사례 - 내가 만든 Skill들

### 사례 1: blog-post-writer

업무에서 다룬 기술 내용을 개인 블로그 마크다운 포스팅으로 자동 변환.

```
/blog-post-writer
```

**작동 원리:**
1. 현재 대화/작업 내용에서 기술 주제 파악
2. 블로그 디렉토리 구조 확인 후 적절한 위치 결정
3. 회사 내부 정보(내부 URL, 서비스 코드, 시스템 이름 등) 제거/대체
4. 자연스러운 문체로 마크다운 작성 (AI 티 나지 않게)
5. 파일 저장 후 경로 안내

**효과:** 업무 중 쌓은 기술 노하우를 블로그 글로 남기는 시간이 거의 0에 가까워짐. 민감 정보 실수로 올리는 위험도 사전 차단.

> 이 글도 사실 이 Skill로 작성 흐름을 잡았다.

### 사례 2: cmux-browser (사내 SSO 인증 자동화)

WebFetch로 접근 불가한 SSO/IAM 인증 필요 내부 시스템을 cmux 내장 브라우저로 자동화.

```
/cmux-browser
```

**배경:**
회사 내부 시스템들은 SSO 세션 없이는 접근이 막혀 있다. `WebFetch`는 단순 HTTP 요청이라 인증을 통과하지 못한다. 반면 cmux의 내장 브라우저는 이미 로그인된 세션을 유지하고 있어서, 이걸 활용하면 복잡한 인증 게이트웨이 뒤의 페이지도 자동화할 수 있다.

**작동 원리:**
1. `cmux browser open <URL>` 로 브라우저 열기 (surface ID 메모)
2. `wait --load-state complete` 로 페이지 로드 대기
3. `snapshot --interactive` 로 DOM 구조 파악
4. CSS selector 또는 `eval`로 JS 직접 실행해서 폼 조작
5. `screenshot` 으로 결과 확인

```bash
# 핵심 패턴: ref보다 eval이 안정적
cmux browser surface:16 eval "document.querySelector('#search').value = '검색어';"
cmux browser surface:16 click "button:has-text('검색')"
cmux browser surface:16 screenshot --out /tmp/result.png
```

**효과:** 반복적인 내부 시스템 작업을 Claude에게 위임 가능. 특히 cross-origin iframe 처리, JS 콜백 직접 호출 등 일반적인 방법으로 안 되는 폼들도 해결.

### 사례 3: 결재 시스템 폼 자동화

사내 결재 시스템에서 반복적으로 작성하는 서식을 자동 제출.

```
/권한신청-자동화 "서버 목록: host-1, host-2, host-3"
```

**배경:**
권한 신청이나 서버 접근 요청같은 결재 서식은 구조는 매번 같은데, 입력할 항목이 많고 폼이 jQuery/JS 기반이라 일반적인 DOM 조작이 안 된다. 특히 autocomplete가 걸려 있는 필드는 `fill` + Enter로 선택이 안 되고, 내부 JS 콜백 함수를 직접 eval로 호출해야 한다.

**작동 원리:**
1. 서식 URL로 직접 navigate
2. 폼의 JS 콜백 함수 구조 파악 (autocomplete, hidden field 등)
3. `eval`로 콜백 함수 직접 호출해서 값 설정
4. 대량 입력이 필요하면 textarea에 줄바꿈 구분으로 한번에 입력
5. 상신 버튼 클릭 후 URL로 성공 여부 확인

```bash
# 일반적인 fill + Enter가 안 될 때 → 내부 콜백 직접 호출
cmux browser surface:N eval "
callBackSelectItem({
  id: 'item-123',
  name: '선택값',
  category: '카테고리'
});
"
```

**효과:** 서버가 20대든 50대든 입력 시간은 동일. 실수 없이 일관된 형식으로 제출 가능.

### 사례 4: 월별 공수 입력 자동화

매월 마감이 있는 공수 입력 시스템을 자동화.

```
/공수입력
```

**배경:**
공수 입력 시스템은 Toast UI Grid 기반이라 일반 CSS selector나 fill 명령으로는 값 설정이 안 된다. Grid 인스턴스를 직접 찾아서 API를 호출해야 한다. 거기에 더해 이번 달 내가 어떤 업무를 했는지 이슈 트래커에서 조회해서 배분 비율까지 제안받는다.

**작동 원리:**
1. SSO 인증 확보 (연관 페이지 먼저 열기)
2. 공수 입력 페이지 열기 + Grid 인스턴스 접근
3. 이슈 트래커 MCP로 이번 달 담당 업무 조회
4. 업무 목록을 카테고리별로 분류해서 배분 비율 제안
5. 사용자 확인 후 Grid API로 값 설정 + 저장

```bash
# Toast UI Grid API로 직접 값 설정
cmux browser surface:N eval "
const grid = gridInstance.core.publicInstance;
const rows = grid.getRowList();
const target = rows.find(r => r.categoryName.includes('키워드'));
grid.setValue(target.rowKey, 'workRate', 60);
"
```

**효과:** 업무 목록 조회부터 입력까지 수동 작업 시간을 대폭 단축. 합계가 100%인지 검증도 자동화.

---

## 7. Skill 만들 때의 팁과 주의사항

### 좋은 Skill의 특징

1. **명확한 목적**
   - Skill 하나 = 하나의 명확한 작업
   - "이것저것 하는" 일반적인 Skill보다는 "OO만 하는" 구체적인 Skill이 낫다

2. **실패 처리**
   - 모든 단계에 검증 로직 포함
   - 실패했을 때 롤백하거나 명확한 에러 메시지 표시

3. **문서화**
   - Skill의 입력 파라미터 명확히 정의
   - 예상 출력 형식 정의
   - 실패 케이스 문서화

4. **테스트 가능성**
   - Skill을 사용하기 전에 미리 테스트할 수 있어야 함
   - 테스트 데이터셋 포함

### 피해야 할 것

1. **너무 복잡한 로직**
   - 단계가 10개 이상이면, 여러 작은 Skill로 나누는 게 낫다
   - 각 Skill은 최대 5~7개 단계 정도가 이상적

2. **하드코딩된 설정**
   - 프로젝트마다 다른 경로, 파라미터는 변수로 만들기
   - 재사용성이 떨어진다

3. **검증 없이 바로 실행**
   - "정말 이렇게 할 건가요?" 같은 확인 단계 포함
   - 특히 파일 삭제나 변경할 때는 필수

---

## 8. Skill이 가져온 변화

개인적으로 Skill 시스템을 쓰면서 느낀 변화들:

### 생산성 측면

- **반복 작업 시간 60~80% 단축**
  - 매번 같은 명령어를 치거나 같은 지시사항을 적을 필요가 없음

- **버그 감소**
  - 사람 손이 덜 가므로 인간 실수 감소
  - 자동화된 검증으로 잘못된 수정 방지

- **일관성 유지**
  - 모든 커밋이 같은 형식
  - 모든 코드 리뷰가 같은 기준
  - 모든 문서가 같은 구조

### 개발 경험 측면

- **지루한 작업에서 해방**
  - "이 모든 파일을 다 확인해야 하나?" 같은 생각이 없어짐
  - 창의적인 일에 더 집중 가능

- **Skill 만드는 재미**
  - 한 번의 성공 패턴을 재사용 가능하게 만드는 경험
  - "아, 이것도 자동화할 수 있겠네?"라는 새로운 관점

- **팀 협업 개선**
  - 내가 만든 Skill을 팀원과 공유
  - 모두가 같은 자동화의 혜택을 받음

---

## 9. 마치며

Claude Code의 Skill 시스템은 단순한 "명령어 모음"이 아니다. 이것은 **당신의 개발 패턴을 학습하고, 반복되는 작업을 지능적으로 처리하고, 더 중요한 일에 집중하게 해주는 개인 AI 어시스턴트를 만드는 도구**다.

처음에는 built-in Skill들로 시작해서:
- `/autopilot`로 프로젝트 분석해보고
- `/ralph`로 대규모 리팩토링 경험해보고
- `/ultrawork`로 복잡한 작업의 편리함을 느껴보고
- 마지막으로 `/skill-creator`로 나만의 자동화를 만들어보자

이 과정을 통해 느껴질 것이다. **AI는 이제 단순히 "대화하는 도구"가 아니라, 실제로 내 개발 생산성을 몇 배로 높이는 동료가 될 수 있다**는 것을.

당신도 오늘 하나의 반복되는 작업을 찾아서 Skill로 만들어보면 어떨까? 분명 "어? 이게 이렇게 되네?"라는 감동을 느낄 것이다.

---

### 더 알아보기

- Claude Code 공식 문서: https://docs.anthropic.com/claude-code
- oh-my-claudecode 프로젝트: GitHub에서 "oh-my-claudecode" 검색
- Skill 예제 모음: 당신의 Claude Code 설정에서 `~/.claude/agents/` 디렉토리 확인

Skill을 만들면서 막히는 부분이 있다면, Claude Code 자체에게 물어보면 된다. 역설적이지만, 이것이 Skill 시스템의 가장 아름다운 점이다. **도구를 만드는 데 도구를 사용한다.**
