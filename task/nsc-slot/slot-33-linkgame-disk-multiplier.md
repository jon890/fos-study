# Slot 33 — 링크게임 + 디스크 배수 + 홀드&스핀 구현기

**진행 기간**: 2024.10 ~ 2024.12

---

## 어떤 슬롯인가

이 슬롯은 **링크게임(Link Game) + 홀드&스핀(Hold & Spin)** 이 핵심이다.

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

이 구분이 중요한 이유가 있다. 링크게임 종료 조건은 **이번 스핀에서 새로 등장한 링크 심볼이 없는 것**이다. 고정 심볼과 새 심볼을 구분하지 않으면 기존 심볼을 매 스핀마다 새 심볼로 오인해서 종료 조건을 만족할 수 없다.

코드에서는 이걸 `addedLinkSymbolCount`로 처리한다. 이번 스핀에 새로 생긴 링크 심볼과 하이 심볼만 따로 집계하고, 그 합이 0이면 리트리거 없이 종료된다.

```java
Triggers checkTriggers(int addedLinkSymbolCount, int totalReelSize, int currentLinkSymbolCount) {
    if (totalReelSize == currentLinkSymbolCount) {
        triggers.satisfyConditions(LINK_SYMBOL_IS_FULL);  // Grand Jackpot
    }
    if (addedLinkSymbolCount > 0) {
        triggers.satisfyConditions(LINK_RE_TRIGGER_KEY);  // 새 심볼 있으면 계속
    }
    return triggers;
}
```

### 초기 윈도우 처리

베이스에서 링크게임으로 진입할 때 윈도우 설정도 주의해야 한다.

링크게임 진입 시 링크 심볼이 없는 자리는 BLANK로 채워야 한다. 처음 구현에서는 링크 심볼 위치를 제외하지 않고 전체를 BLANK로 초기화해버렸다. 베이스에서 모은 링크 심볼이 사라지는 버그였다.

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

링크 심볼이 윈도우를 가득 채우면 즉시 Grand Jackpot이 발생한다. 이 검사를 보상 계산 **이후**에 하면 문제가 생긴다.

스핀 결과를 반영한 뒤 보상을 누적하고, 그 다음에 Grand Jackpot 여부를 판단하면 일반 보상과 잭팟 보상이 중복으로 계산될 수 있다.

종료 조건 검사를 보상 계산보다 먼저 실행하도록 순서를 앞당겼다.

```java
// 새 링크 심볼 반영
fixedLinkPositions.addAll(newLinkPositions);

// 먼저 종료 조건 검사 (check-before-mutate)
if (isFullyFilled(window, fixedLinkPositions)) {
    return LinkGameResult.grandJackpot(fixedLinkPositions);
}

// 그 다음에 보상 계산
accumulateRewards(newLinkPositions);
```

---

## 3. 텀블링 중 링크 심볼 위치 추적 — 이벤트 리스너 패턴

베이스 스핀에서 텀블링이 일어나면 심볼이 아래로 낙하(캐스케이딩)한다. 링크 심볼도 예외가 아니다. 링크 심볼이 이동하면, 나중에 링크게임으로 가져갈 위치 정보도 함께 업데이트해야 한다.

처음에는 캐스케이딩이 끝난 뒤 전체 윈도우를 다시 스캔해서 링크 심볼 위치를 재수집했다. 동작은 했지만, 캐스케이딩 로직과 링크 심볼 추적 로직이 타이밍으로 결합되어 있었다.

이를 이벤트 리스너로 분리했다.

```java
final CascadingEventListener cascadingEventListener =
    (currentX, currentY, nextY, symbolCode) -> {
        if (SymbolEnum.isLinkSymbol(symbolCode, BASE.getCode())) {
            final LinkSymbol linkSymbol = resultLinkSymbols.getLinkSymbol(currentPosition);
            resultLinkSymbols.remove(currentPosition);
            resultLinkSymbols.add(cascadingPosition, linkSymbol);  // 위치 변경 추적
        }
    };
```

캐스케이딩 로직은 심볼이 어디서 어디로 이동했는지 이벤트를 발행하고, 링크 심볼 추적은 그 이벤트를 구독해서 위치를 갱신한다. 캐스케이딩 로직이 링크 심볼의 존재를 알 필요가 없다.

---

## 4. 하이 심볼 개수 제한 — 밸런싱을 코드로 강제하기

링크게임에서 하이 심볼(H01, H02, H03)은 디스크 배수를 크게 올리는 고가치 심볼이다. 확률 테이블만으로 이를 조절하면 기댓값은 맞출 수 있지만, 특정 스핀에서 하이 심볼이 몰려 나오는 극단적인 경우를 막을 수 없다.

**하드 캡(hard cap)** 을 추가했다.

```java
if (SymbolEnum.isHighSymbol(decidedSymbol)) {
    final int current = currentHighSymbolCounts.getOrDefault(decidedSymbol, 0);
    final int max = linkHighSymbolMaxCounts.getOrDefault(decidedSymbol, Integer.MAX_VALUE);

    // 최대 개수 초과 시 링크 심볼로 강제 치환
    if (current >= max) {
        decidedSymbol = SymbolEnum.LINK.getCode();
    }
}
```

확률로 조절하기 어려운 극단값을 코드 레벨 상한선으로 막는다. 밸런싱 의도가 런타임에서 보장된다.

---

## 5. 뱃지 심볼별 디스크 배수 증가 방식

베이스 스핀에서 H01, H02, H03 심볼이 나오면 디스크 배수가 올라간다. 세 심볼의 증가 방식이 서로 다르다.

- **H01**: 고정값으로 증가. 예측 가능한 안정적인 상승.
- **H02**: 알리아스 테이블에서 랜덤으로 증가량을 결정.
- **H03**: 어느 릴(열)에서 나왔느냐에 따라 올라가는 디스크가 다르다.

```java
switch (symbolEnum) {
    case H01 -> increments = personalData.incrementByH01(diskMaxMultiplier);
    case H02 -> {
        final int count = h02DiskIncrementAliasTable.pickToInt();
        increments = personalData.incrementByH02(randomUtil, count, diskMaxMultiplier);
    }
    case H03 -> {
        final int reelIndex = visibleWindowPosition.x();
        increments = personalData.incrementByH03(reelIndex, diskMaxMultiplier);
    }
}
```

심볼마다 다른 증가 방식은 게임 내 전략 요소다. 동일한 목적(디스크 배수 증가) 뒤에 다른 전략을 두는 구조다.

---

## 6. 바이피처 진입 조건 처리

일반적으로 링크게임 진입에는 **최소 디스크 배수** 조건이 있다. 바이피처(BuyFeature)는 유저가 직접 돈을 내고 링크게임에 바로 진입하는 것이기 때문에, 이 조건을 완화해야 했다.

바이피처 진입 시 디스크 테이블을 최소 배수값으로 초기화하는 방식으로 처리했다.

```java
void handleBuyFeatureOption1(final int totalDiskValue, final int minimumDiskValue, ...) {
    // 모든 릴을 최소 배수로 초기화 → 조건 자동 충족
    Arrays.fill(buyFeatureDiskTable, minimumDiskValue);
}
```

바이피처와 일반 스핀의 분기를 한 곳에서 처리해서 조건이 흩어지지 않도록 했다.

---

## 7. 시뮬레이터

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

**스테이지 간 상태가 이어지는 구조는 심볼의 출처를 명시적으로 관리해야 한다.** 고정된 심볼과 새로운 심볼을 구분하지 않으면 종료 조건, 보상 계산, 윈도우 초기화 모든 곳에서 버그가 생긴다.

**상태를 바꾸기 전에 조건을 먼저 확인해야 한다.** 종료 조건 검사를 보상 계산 이후로 미루면 중복 계산이 생긴다. check-before-mutate 순서가 여기서 중요하다.

**확률 테이블만으로는 극단값을 막을 수 없다.** 기댓값은 확률로 조절하되, 허용할 수 없는 극단값은 코드 레벨 상한선으로 보장하는 것이 안전하다.

**로직 간 결합은 이벤트로 끊는다.** 캐스케이딩 로직이 링크 심볼을 직접 알 필요가 없다. 이벤트 리스너로 분리하면 각 로직이 자기 책임에만 집중할 수 있다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JUnit 5
