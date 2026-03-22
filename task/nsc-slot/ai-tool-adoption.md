# AI 개발 도구 도입 및 Cursor Rules 구축

**진행 기간**: 2025.04 ~ 2025.11

---

## 배경

슬롯 게임 하나를 개발하려면 알아야 할 게 많다.

- 슬롯의 당첨 방식(라인/웨이/클러스터)
- 심볼 구성과 각 심볼의 역할
- 개인화 데이터 구조
- 시뮬레이터 연동 방식
- 프로젝트 패키지 구조와 핵심 클래스 위치

사람이 처음 슬롯을 개발할 때도 이 맥락을 파악하는 데 시간이 걸린다. AI 에이전트는 이 맥락이 없으면 엉뚱한 코드를 만들어낸다.

팀에서 AI 에이전트를 개발에 쓰기 시작하면서 "어떻게 에이전트에게 우리 도메인을 이해시킬 것인가"가 핵심 문제였다.

---

## Cursor Rules

Cursor는 `.cursor/rules/` 디렉토리의 `.mdc` 파일을 에이전트 컨텍스트로 자동으로 제공한다.

이 프로젝트에서 구축한 rules 파일 구조:

```
.cursor/rules/
├── nsc-slot-service/
│   ├── slot-rules.mdc          # 슬롯 개발 공통 규칙 (패키지 위치, 아키텍처)
│   ├── slot-simulator.mdc      # 시뮬레이터 작성 가이드
│   ├── slot-test-rules.mdc     # 테스트 코드 작성 규칙
│   ├── user-engage.mdc         # UserEngageService 사용 규칙
│   ├── rcc-slot.mdc            # RCC 시스템 구조 및 슬롯별 대응 방법
│   ├── nsc_00000036-rules.mdc  # Slot 36 (Magic Circus) 전용 규칙
│   ├── nsc_00000041-rules.mdc  # Slot 41 (Bingoing) 전용 규칙
│   ├── nsc_00000047-rules.mdc  # Slot 47 (Boogie Turkey) 전용 규칙
│   └── ... (슬롯별 10종 이상)
└── meta-service-rules.mdc      # 메타 서비스 규칙
```

총 20개 이상의 rules 파일을 구축했다.

---

## rules 파일에 담은 것들

### 공통 슬롯 rules (slot-rules.mdc)

에이전트가 슬롯 코드를 작성할 때 반드시 알아야 하는 것들이다.

```markdown
## 핵심 도메인 객체 및 패키지 위치

- SlotStageType: com.nhn.nscplatform.constants.slot.SlotStageType
- ReelResult: com.nhn.slot.slotcore.application.valueobject.ReelResult
- SpinResultParameter: com.nhn.slot.slotcore.application.valueobject.slot.SpinResultParameter

## 슬롯 아키텍처

- 새 슬롯은 BaseSlotService를 상속해서 구현
- 당첨 방식은 SlotTemplate으로 추상화됨
- 개인화 데이터는 SlotPersonalDataService를 통해 접근
```

패키지 경로가 없으면 에이전트가 존재하지 않는 클래스를 import하거나 직접 구현을 만들어버리는 경우가 많았다.

### 슬롯별 전용 rules

각 슬롯의 구조, 심볼, 게임 로직을 문서화했다.

```markdown
# 47번 슬롯 - BoogieTurkey 가이드

## 슬롯 기본 정보
- 당첨 방식: 웨이(WAY) - 243 ways to win
- 주요 특징: Sync 릴, 프리스핀, 재트리거 없음

## 심볼 구성
- H01: 최고 가치 심볼
- WLD: 와일드 (릴 2-5에만 등장)
- SCT: 스캐터 (프리스핀 트리거)

## Sync Reel 동작 방식
- 랜덤하게 선택된 릴이 동기화됨
- 동기화된 릴은 동일한 심볼로 채워짐
```

이 파일이 없으면 에이전트는 심볼 이름, 릴 구성, Sync Reel 스펙을 모른다.

### RCC rules (rcc-slot.mdc)

RCC 시스템 패키지 구조와 슬롯별 대응 방법을 담았다.

```markdown
## RccSpinResultAnalyzer

슬롯별로 어떤 결과를 캐시할지 결정하는 인터페이스.
새 슬롯 RCC 대응 시 이 인터페이스를 구현해야 함.

## 주의사항

- 시뮬레이터에서는 RCC 캐시가 생성되지 않도록 분기 처리 필수
- 튜토리얼/치트 스핀은 RccHandler를 타지 않음
```

---

## 에이전트 활용 결과

rules 파일을 구축한 후 에이전트를 실제 개발에 활용했다.

| 작업 | 결과 |
|------|------|
| Slot 44 (Fortune Blessing) 초기 구현 | 에이전트 단독 구현 |
| Slot 41 (Bingoing) 전체 구현 | 에이전트 단독 구현 |
| Slot 47 (Boogie Turkey) 전체 구현 | 에이전트 단독 구현 |
| 슬롯별 리팩토링, 버그 수정 다수 | 에이전트 협업 |

커밋 메시지에 `by agent` 표기를 남겨서 어떤 작업이 에이전트로 진행됐는지 추적할 수 있도록 했다.

---

## 겪은 문제들

**컨텍스트가 부족하면 에이전트가 잘못된 클래스를 사용한다.** 패키지 경로가 rules에 없으면 에이전트가 비슷한 이름의 다른 클래스를 가져오거나, 존재하지 않는 메서드를 호출하는 코드를 만든다. rules 파일을 작성할 때는 클래스 이름만이 아니라 정확한 패키지 경로까지 포함해야 한다.

**rules 파일도 유지보수가 필요하다.** 코드 구조가 바뀌면 rules 파일도 함께 업데이트해야 한다. 오래된 rules 파일은 없는 것보다 나쁠 수 있다. 에이전트가 이미 삭제된 클래스를 기반으로 코드를 작성한다.

**에이전트 구현 후 검토는 필수다.** 에이전트가 작성한 코드를 그대로 쓰면 안 된다. 특히 도메인 규칙(RTP 계산, 특수 심볼 처리 등)이 맞는지, 기존 패턴과 일관성이 있는지 직접 검토해야 한다.

---

## 배운 것

**AI 에이전트는 맥락이 있어야 제대로 동작한다.** rules 파일 작성에 들인 시간이 에이전트 활용 과정에서 그대로 돌아왔다. 특히 복잡한 도메인일수록 rules 파일의 품질이 결과물의 품질을 결정한다.

**rules 파일은 도메인 지식의 문서화이기도 하다.** 에이전트를 위해 만든 파일이지만, 새로운 팀원이 온보딩할 때도 쓸 수 있다. 도메인 지식을 명시적으로 문서화하는 습관이 생겼다.

---

## 사용 도구

- **Cursor**: AI 에이전트 기반 IDE, `.cursor/rules/` 기반 컨텍스트 관리
- **Claude Sonnet**: 에이전트 모델
