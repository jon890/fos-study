# Slot 33 (Wanted) — 링크게임 구현기

**진행 기간**: 2024.10 ~ 2024.12

---

## 어떤 슬롯인가

Wanted는 **링크게임(Link Game)** 이 핵심인 슬롯이다.

베이스 스핀에서 링크 심볼을 모아서 윈도우를 채우면 링크게임에 진입하고, 링크게임에서 추가 심볼을 모아 최종 보상을 결정한다. 윈도우가 완전히 링크 심볼로 채워지면 Grand Jackpot이 발생한다.

여기에 텀블링 메커니즘(당첨 심볼 제거 후 새 심볼 낙하)까지 더해진다. 두 가지 메커니즘이 섞이면서 구현 복잡도가 올라갔다.

---

## 1. 링크게임의 상태 관리

### 두 가지 심볼이 공존한다

링크게임의 핵심 난점은 **고정된 심볼과 새로 생성된 심볼이 같은 윈도우에 공존한다**는 점이다.

```
[링크게임 진입 시점]
  위치 (0,0): 링크 심볼 ← 베이스에서 모은 것, 고정
  위치 (1,2): 링크 심볼 ← 베이스에서 모은 것, 고정
  나머지: BLANK ← 링크게임에서 새로 채워질 자리

[링크게임 스핀 후]
  위치 (0,0): 링크 심볼 (기존, 고정)
  위치 (1,2): 링크 심볼 (기존, 고정)
  위치 (2,1): 링크 심볼 ← 이번 스핀에서 새로 등장
  나머지: BLANK
```

이 구분이 중요한 이유가 있다. 링크게임의 종료 조건은 **"새로 링크 심볼이 나오지 않는 스핀이 3연속"** 이다. 고정된 심볼과 새로운 심볼을 구분하지 않으면 매 스핀마다 기존 심볼을 새 심볼로 오인해서 종료 조건을 못 만족하게 된다.

```java
// 링크게임 상태를 명시적으로 추적
Set<Position> fixedLinkPositions = new HashSet<>(); // 이전 스핀에서 고정된 심볼
Set<Position> newLinkPositions = new HashSet<>();    // 이번 스핀에서 새로 등장한 심볼

// 새 심볼이 없으면 카운터 증가
if (newLinkPositions.isEmpty()) {
    noNewLinkCount++;
} else {
    noNewLinkCount = 0; // 리셋
    fixedLinkPositions.addAll(newLinkPositions);
}
```

### 초기 윈도우 처리

베이스에서 링크게임으로 진입할 때 윈도우 설정도 주의해야 한다.

링크게임 진입 시 다음 상태의 릴에서 링크 심볼이 없는 자리는 BLANK로 채워야 한다. 처음 구현에서는 링크 심볼 위치를 제외하지 않고 전체를 BLANK로 초기화해버렸다. 베이스에서 모은 링크 심볼이 사라지는 버그였다.

```java
// 잘못된 초기화
window.fillAll(BLANK);

// 올바른 초기화: 링크 심볼 위치는 유지
for (Position pos : window.allPositions()) {
    if (!fixedLinkPositions.contains(pos)) {
        window.set(pos, BLANK);
    }
}
```

---

## 2. 종료 조건 검사 순서

### 스핀 결과 처리 전에 먼저 검사해야 한다

링크 심볼이 윈도우를 가득 채우면 즉시 종료(Grand Jackpot)가 발생한다. 이 검사를 스핀 결과 처리 **이후**에 하면 문제가 생긴다.

시나리오를 생각해보면:

```
[스핀 결과 처리]
  새 링크 심볼 4개 추가
  → fixedLinkPositions 업데이트
  → noNewLinkCount = 0 리셋
  → RTP 누적 로직 실행 ...

[종료 조건 검사] ← 이미 상태가 바뀐 후
  윈도우 가득 참 → Grand Jackpot?
```

RTP 누적이 먼저 실행된 후 Grand Jackpot을 선언하면, 누적된 일반 보상과 잭팟 보상이 중복으로 계산될 수 있다.

종료 조건 검사를 스핀 결과 처리 **전**으로 앞당겼다.

```java
// 새 링크 심볼 반영
fixedLinkPositions.addAll(newLinkPositions);

// 먼저 종료 조건 검사
if (isFullyFilled(window, fixedLinkPositions)) {
    return LinkGameResult.grandJackpot(fixedLinkPositions);
}

// 그 다음에 보상 계산 및 상태 업데이트
accumulateRewards(newLinkPositions);
```

---

## 3. 베이스 → 링크 전환 시 windowHeight 문제

베이스 스핀과 링크게임은 윈도우 높이(`windowHeight`)가 다를 수 있다.

베이스는 3x5 윈도우를 쓰고, 링크게임은 4x5 윈도우를 쓰는 구조였다. 진입 시점에 windowHeight 계산 로직이 달라서 클라이언트가 잘못된 크기로 윈도우를 렌더링하는 현상이 있었다.

원인은 두 곳에서 windowHeight를 각자 계산하고 있었기 때문이다. 링크게임 진입 시점에 명시적으로 windowHeight를 링크게임 기준값으로 덮어쓰도록 처리했다.

---

## 4. 바이피처 진입 조건 처리

일반적으로 링크게임 진입에는 **최소 디스크 배수** 조건이 있다. 베이스 스핀에서 모은 링크 심볼의 배수 합이 일정 기준을 넘어야 링크게임에 진입할 수 있다.

바이피처(BuyFeature)는 이 조건을 다르게 적용해야 했다. 유저가 직접 돈을 내고 링크게임에 바로 진입하는 것이기 때문에, 최소 디스크 배수 조건을 완화하거나 우회해야 했다.

```java
// 진입 조건 검사
boolean canEnterLinkGame(SpinContext context, int diskMultiplierSum) {
    if (context.isBuyFeature()) {
        return diskMultiplierSum >= BUY_FEATURE_MIN_DISK_MULTIPLIER; // 완화된 조건
    }
    return diskMultiplierSum >= BASE_MIN_DISK_MULTIPLIER;
}
```

바이피처와 일반 스핀의 분기를 한 곳에서 처리해서 조건이 흩어지지 않도록 했다.

---

## 5. 시뮬레이터

링크게임은 베이스 스핀과 별도 루프로 진행된다. 시뮬레이터도 이 구조를 따라야 한다.

```
베이스 스핀 루프
  → 링크게임 진입 조건 충족
  → 링크게임 루프 (별도)
  → 결과 집계 (링크게임 보상 포함)
  → 다시 베이스 스핀 루프
```

처음에 베이스 스핀 RTP만 집계했다가 링크게임 보상이 누락됐다. 링크게임 결과를 베이스 루프에서 합산하도록 수정했다.

릴별 평균 디스크 배수도 시뮬레이터 항목으로 추가했다. 어떤 릴에서 디스크 배수가 높게 나오는지 분포를 파악하는 게 밸런싱에 필요한 데이터였다.

---

## 배운 것

**링크게임처럼 스테이지 간 상태가 이어지는 구조는 "무엇이 어느 스테이지에서 만들어진 것인가"를 항상 추적해야 한다.** 고정된 심볼과 새로운 심볼을 구분하지 않으면 종료 조건, 보상 계산, 윈도우 초기화 모든 곳에서 버그가 생긴다. 심볼의 출처를 명시적으로 관리하는 코드 구조가 훨씬 안전하다.

**상태 전이 시점에 검사 순서가 결과를 바꾼다.** 종료 조건을 언제 검사하느냐에 따라 보상 중복 계산이 생길 수 있다. 상태를 바꾸기 전에 먼저 조건을 확인하는 "check-before-mutate" 패턴이 여기서 맞다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JUnit 5
