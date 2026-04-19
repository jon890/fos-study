# 첫 슬롯을 만들며 시작된 1년의 아키텍처 정리 — SpinOperationHandler와 static 해체, 그리고 남은 과제

**진행 기간**: 2024.06 ~ 2025.11

슬롯팀에 합류해 첫 슬롯([Slot 21 — 클러스터 + 텀블링 + 머지](./slot-21-cluster-tumbling-merge.md))을 맡으면서 마주친 코드베이스는 테스트를 붙이기가 매우 어려운 상태였다. 작은 단위로 TDD 형태로 접근해보려 했지만, 로직이 강결합되어 있고 스프링 컴포넌트를 static으로 호출하는 구조가 도처에 깔려 있어 곧 벽에 부딪혔다.

"이걸 한 번에 갈아엎는 건 불가능하다. 작은 영역부터 조금씩 풀자"는 결심으로 1년 반에 걸쳐 진행한 점진적 정리 기록이다. **한 번에 해결된 건 하나도 없고, 작은 PR을 수십 번 쌓아 조금씩 움직였다.** 그 과정에서 중간에 시도한 구조가 한계를 드러낸 순간도 있었고, 지금까지도 풀지 못한 문제가 있다.

---

## 첫 슬롯에서 마주친 네 개의 벽

코드를 파악하면서 TDD로 방어막을 치려 했는데 매번 같은 패턴으로 막혔다.

**벽 1 — 거대한 `SpinResultParameter`**. 스핀 요청은 이 객체 하나에 모든 맥락이 실려 서비스 레이어로 전달된다. 지금도 436줄이다. 신규 슬롯 하나를 만들려면 이 객체를 이해해야 하는데 필드가 너무 많아 "어디까지 필수고 어디까지 선택인지" 파악이 어려웠다.

**벽 2 — 혼동되는 네이밍**. `SpinResult`는 결과 객체로 의미가 명확한데, `SpinResultParameter`는 **스핀을 시작할 때 던지는 파라미터**다. "스핀 결과에 대한 파라미터?"라는 해석이 먼저 떠오른다. 더 난감한 건 `SpinParameter`라는 별도 클래스가 **따로 존재**한다는 점이다. 두 이름이 공존하면 어느 게 어느 맥락에 쓰이는지 코드를 열기 전에는 구분이 안 된다.

**벽 3 — static 강결합**. `SlotStaticDataLoader.getSlotProduct(slotId)` 같은 static 호출이 서비스/컴포넌트/인터페이스 default 메서드까지 퍼져 있었다. 스프링 빈으로 동작하는 컴포넌트들도 어느 지점에서는 static을 찔렀고, 인터페이스의 default 메서드가 내부에서 다른 정적 자원을 참조하는 패턴도 많았다. **Mock이 안 되니 테스트도 안 된다.** 모킹하려면 PowerMock 같은 방향으로 가야 하는데 그건 다른 종류의 기술 부채를 들여오는 일이었다.

**벽 4 — 카피된 3개 PlayService**. 스핀 요청 처리 서비스는 `NormalPlayService`, `TutorialPlayService`, `CheatPlayService` 3종으로 분리되어 있었는데, 내부 흐름이 거의 같은 카피였고 아주 작은 분기만 달랐다. 자주 읽지 않는 사람은 세 서비스의 차이를 잡아내기 어려웠고, 한쪽에 버그를 고치면 다른 쪽에 그대로 남아 있었다. **사이드이펙트에 매우 취약한 구조**였다.

> **인사이트.** 테스트 작성이 어렵다는 건 "이 코드가 잘 설계되지 않았다"는 가장 조용한 신호다. static/강결합/거대 객체는 각각으론 견딜 만 해 보여도, 이 셋이 동시에 있으면 테스트 불가능 지점이 교집합으로 만들어진다. 첫 슬롯 작업에서 이걸 체감하고부터 큰 리팩터링을 한 번에 하려는 유혹을 버렸다.

---

## 변곡점: 스핀 로직 템플릿화 (#5717, 2024.12)

첫 번째로 손에 잡은 건 카피된 PlayService였다. 튜토리얼 스핀을 계속 건드리다 보니 Normal과 중복된 흐름이 더 선명하게 눈에 띄었다.

### Before — 카피된 3개 PlayService

```
NormalPlayService                TutorialPlayService              CheatPlayService
 ├─ 요청 검증                      ├─ 요청 검증                       ├─ 요청 검증
 ├─ 유저 정보 조회                  ├─ 유저 정보 조회                   ├─ 유저 정보 조회
 ├─ 스핀 파라미터 조립               ├─ 스핀 파라미터 조립 (시나리오 분기)  ├─ 스핀 파라미터 조립 (치트 분기)
 ├─ 스핀 실행                      ├─ 스핀 실행 (시나리오 결과 주입)      ├─ 스핀 실행 (치트 결과 주입)
 ├─ 후처리 / 로그                   ├─ 후처리 / 로그                   ├─ 후처리 / 로그
 └─ 응답 변환                      └─ 응답 변환                      └─ 응답 변환
```

흐름이 거의 같고, 각 단계에 슬쩍 다른 분기가 들어가 있다. 이 구조에서 생긴 문제들:
- 한쪽을 고치면 다른 두 곳에 같은 변경을 반영해야 함
- 어떤 단계가 공통이고 어떤 단계가 분기인지 코드만 보고는 알기 어려움
- 리뷰어가 "이 변경이 Tutorial/Cheat에도 반영됐나?"를 매번 확인해야 함

### After — SpinOperationHandler + AbstractPlayService

템플릿 메서드 패턴으로 **공통 흐름을 AbstractPlayService로 올리고, 각 PlayService가 특수 동작만 hook으로 주입**하게 바꿨다.

```
AbstractPlayService (공통 흐름)
 ├─ 요청 검증
 ├─ handler.onStart()                 ← hook
 ├─ handler.onLoadLastSpinResult()    ← hook
 ├─ handler.onLoadUserInfo()          ← hook
 ├─ handler.validateAdditional()      ← hook
 ├─ handler.makeReelCategory()        ← 필수 구현
 ├─ handler.prepareSpinResultParameter() ← hook
 ├─ handler.makeSpinResult()          ← hook (default: slotService.makeSpinResult)
 ├─ handler.onFinish()                ← 필수 구현
 └─ handler.makeUserInfoResponse()    ← 필수 구현
       ↑
   NormalPlayService / TutorialPlayService / CheatPlayService
   각각 SpinOperationHandler 구현체를 제공. 필요한 hook만 오버라이드
```

`SpinOperationHandler` 인터페이스 자체는 9개 메서드 — 대부분 default 구현을 제공하고, 각 PlayService는 자기한테 필요한 것만 오버라이드한다. 예를 들어 Tutorial은 `makeSpinResult` hook을 덮어 "시나리오 결과"를 반환하도록, Cheat는 `prepareSpinResultParameter`를 덮어 치트 플래그를 삽입한다.

```java
// 개념 설명용 의사코드 — 실제 인터페이스 일부
public interface SpinOperationHandler {
    default void onStart(...) {}
    void onLoadLastSpinResult(...);
    default void validateAdditional(...) {}
    ReelCategory makeReelCategory(SpinResultParameter param, SlotService slotService);
    default SpinResult makeSpinResult(SlotService slotService, SpinResultParameter param) {
        return slotService.makeSpinResult(param);   // 기본은 그냥 위임
    }
    // ... 9개 hook
}
```

변경량은 +490 / -437. 새 파일이 생긴 게 아니라 **공통 흐름을 끌어올린 만큼 각 PlayService에서 같은 양이 빠진 것**이다.

**얻은 것**: 세 PlayService의 흐름이 한 곳에서 읽힌다. 새 분기가 필요하면 hook 하나만 오버라이드한다. 리뷰어가 "세 곳에 반영됐나"를 체크할 필요가 없어졌다.

**얻지 못한 것**: **테스트 방어막은 여전히 없었다.** 흐름은 정리됐지만 `SlotStaticDataLoader` static 호출, `SpinResultParameter` 거대 객체, 컴포넌트간 강결합은 그대로 남아 있어서 단위 테스트 작성은 여전히 막혔다. 눈으로 보는 구조가 좋아졌을 뿐이라는 걸 인정해야 했다.

---

## 꾸준한 static 해체 — 작은 영역부터

템플릿화로 흐름을 정리하고 나서 본격적으로 static을 걷어내기 시작했다. 한 번에는 불가능했다. PR마다 하나의 영역씩 풀었다.

| 시점 | PR | 푼 영역 |
|---|---|---|
| 2024.10 | #5560 | 유효성 검증을 `SpinValidator` 컴포넌트로 분리 (첫 컴포넌트 추출) |
| 2025.04 | #6041 | `ThreadLocalRandom`을 `Random` 컴포넌트로 추상화 |
| 2025.07 | #7320 | `AbstractPlayService`의 응답 변환 로직을 `ResponseMapper` 유틸로 분리 |
| 2025.08 | **#7338** | **`SlotStaticDataLoader.getSlotProduct()` static 메서드 제거 → 빈 주입으로 전환** |
| 2025.08 | #7483 | `StaticDataLoader.refreshAll()` 중 NPE 현상 방지 (`StampedLock` 도입) |
| 2025.08 | #7491 | Alias 테이블 init/refresh 시 `IN` 절로 일괄 조회 |
| 2025.09 | #7513 | `SlotService` 인터페이스의 default 구현을 `BaseSlotService` 추상 클래스로 이동 |
| 2025.10 | #7619 | `JackpotService`가 `SlotStaticLoader`를 **주입받아** 사용하도록 변경 |

### SlotStaticDataLoader 여정만 따로 보면

가장 강결합이 심했던 `SlotStaticDataLoader`의 변화가 이 중 핵심이다.

1. **#5425 (2024.10)** — 애플리케이션 기동 전에 로더가 수행되도록 순서만 정리. **static 호출 구조는 그대로** 유지. 당시엔 근본 문제를 건드릴 여유가 없었다.
2. **#7338 (2025.8)** — static 메서드를 빈 메서드로 전환. 이 PR이 static 해체의 실질적 시작점. 같은 PR에서 테스트 정리도 함께 했다. static일 때는 Mock이 안 됐지만 빈이 되자 `@Autowired`로 주입받아 테스트에서 행동을 대체할 수 있게 됐다.
3. **#7483 (2025.8)** — 빈 전환 후 드러난 새 문제. `refreshAll()` 중 `clear + 재로드` 도중 다른 스레드가 조회하면 NPE가 났다. `StampedLock`으로 리로드 구간을 보호(상세는 [슬롯 엔진 추상화](./slot-engine-abstraction.md)).
4. **#7491 (2025.8)** — Alias 테이블을 게임별로 쿼리하던 걸 `IN` 절로 일괄화. 빈으로 전환하면서 호출 경로가 명확해지자 최적화 포인트도 보였다.
5. **#7619 (2025.10)** — 마지막 남은 `JackpotService`까지 `SlotStaticLoader` 주입으로 전환. **이 시점에서 프로덕션 코드 기준 `SlotStaticDataLoader.<static>` 호출이 사라졌다.**

> **인사이트.** static 제거는 단일 PR이 아니라 **"드러나지 않은 의존 그래프를 한 노드씩 잘라내는"** 작업이었다. 한 곳을 잘라내면 그걸 호출하던 다음 지점이 보였고, 그 지점을 고치면 또 다음이 보였다. 중간에 #7483 같은 부수 효과(락이 필요해짐)도 같이 처리해야 했다. 결국 **시간이 해결해주는 게 아니라, 시간과 함께 작은 PR을 쌓아야 해결되는** 성격의 작업이었다.

테스트 인프라 자체의 변화(단위 → 통합, Extension 기반, 치트 데이터)는 별도 글 [슬롯 테스트 공통 템플릿](./slot-test-template.md)에서 다뤘다. 이 글은 **프로덕션 코드의 강결합 해체**에 집중했고, 두 흐름이 합쳐져 2025.10 즈음에는 "새 슬롯을 만들 때 통합 테스트로 실제 동작을 검증할 수 있다"는 상태에 도달했다.

---

## 여전히 남은 것 — SpinResultParameter 436줄

벽 1과 벽 2는 아직 풀지 못했다.

### 네이밍 재정립 — 미완

`SpinParameter`와 `SpinResultParameter`가 **현재도 공존**한다. 둘의 역할을 구분하는 관례가 있지만, 이름만 보면 여전히 서로를 뒤바꿀 수 있을 것처럼 읽힌다. "재정립이 필요하다"고 판단한 뒤 구체 작업으로 옮기지 못한 건, 두 이름이 프로젝트 전반의 메서드 시그니처에 퍼져 있어 이름 바꾸기 작업 자체가 다른 리팩터링과 엉켜 들어갈 위험이 컸기 때문이다. 지금도 아쉬운 부분이다.

### 거대 파라미터 객체 쪼개기 — 배제

`SpinResultParameter`는 436줄이다. 안에는 잭팟 관련 필드처럼 **잭팟을 쓰지 않는 슬롯에는 불필요한 필드**도 포함되어 있다. 모든 슬롯의 스핀 요청이 같은 객체를 통과하니, 잭팟 없는 슬롯도 잭팟 필드를 끼고 흘러간다.

이걸 쪼개려면 `makeSpinResult(SpinResultParameter)` 시그니처를 건드려야 하는데, 이 메서드가 **서비스·템플릿·hook·테스트**의 거의 모든 경로를 통과한다. 시그니처 변경이 도미노로 번지면서 PR 하나로 끝낼 수 없는 규모가 된다. **쪼개기 이득 대비 전파 비용이 너무 커서 배제**했다. 지금도 이 판단이 옳았다고 생각하지만, "언젠가는 풀어야 할 부채"로 남겨뒀다.

---

## 협업은 의견을 구하고 머지하는 방식이었다

팀은 4명이었고, 선배 개발자 한 명이 있었다. 다만 구조 개선에 적극 관심을 보이는 팀원은 많지 않아, 위 리팩터링 대부분은 **내가 먼저 제안하고 의견을 구한 뒤 머지**하는 방식으로 진행됐다. 큰 변경을 한 번에 제안하면 리뷰 부담이 커서 거부감이 생기니, 작은 단위로 쪼개서 한 번에 하나씩 머지하는 걸 의도적으로 지켰다.

이 과정에서 의식적으로 지킨 세 가지 원칙이 있다.

- **PR 하나에 한 가지 주제만**. "static 제거 + 테스트 정리"를 섞어 올릴 때도 리뷰어가 섞어 보지 않도록 PR 설명에서 의도를 분명히 구분했다.
- **Before/After를 PR 설명에 직접 그렸다**. 코드 diff만 보면 "왜 이렇게 바꿨나"가 안 보이는 케이스가 많다. 흐름도나 짧은 표를 넣어 의도를 먼저 보여주고 코드를 보도록 유도했다.
- **한 번에 원하는 종착지로 가지 않았다**. 예를 들어 `SlotStaticDataLoader`도 한 PR에서 static 제거 + 락 도입 + Alias 일괄 조회를 전부 시도하고 싶었지만, 네 개의 PR로 쪼갰다. 각 단계가 실제로 작동하는지 리뷰하기 쉬워졌다.

---

## 지금 보면

이 여정 전체를 돌아보면 **"큰 PR로 한 번에 갈아엎는 것"이 답이 아니었던 영역**이었다. 초기엔 "전체 리팩터링 계획서"를 쓰고 싶은 유혹이 있었지만, 팀 분위기와 일정 안에서 그건 가능하지 않았다. 대신 **"코드를 건드릴 때마다 한 층씩 벗기는 보이 스카우트 룰"**에 가까운 접근이 실제로 잘 먹혔다. 1년에 걸쳐 누적된 작은 PR들이 결국 "static이 제거된 빈 주입 구조 + 통합 테스트 가능한 인프라"를 만들어냈다.

다르게 갔으면 좋았을 것:
- **네이밍 재정립을 조금 더 일찍** 시도했어야 한다. 시그니처 전파를 무서워하지 말고, 이름만 바꾸는 PR을 한 번 올리고 리뷰어들과 합의했다면 지금도 남은 혼동을 줄일 수 있었다.
- **`SpinResultParameter` 쪼개기의 "시작점"만이라도 만들어둘 수 있었다.** 예를 들어 잭팟 필드만 별도 객체로 분리하는 식으로. 전체 도미노를 다 치지 않아도 "이 경계는 이미 나눠져 있다"는 시그널은 남길 수 있었다.

반대로 잘 했다 싶은 건 **"한 번에 가지 않겠다"는 결정을 일관되게 지킨 것**이다. 템플릿화 PR(#5717)도 한 번에 끝내고 싶은 유혹이 있었지만, 그 전에 `SpinValidator` 분리(#5560)와 바이피처 검증 개선(#5696)을 먼저 머지해 코드를 익숙하게 만든 뒤에야 템플릿화를 올렸다. 그 순서가 없었으면 템플릿화 PR 리뷰가 훨씬 까다로웠을 것이다.

---

## 관련 문서

- [Slot 21 — 클러스터 + 텀블링 + 머지 슬롯 구현기](./slot-21-cluster-tumbling-merge.md) — 이 여정의 시작이 된 첫 슬롯
- [슬롯 테스트 공통 템플릿](./slot-test-template.md) — 테스트 인프라 진화(단위 → 통합) 허브
- [슬롯 엔진 추상화](./slot-engine-abstraction.md) — `StampedLock` 기반 정적 데이터 리로드 등 후속 아키텍처 정리
