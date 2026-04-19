# Slot 21 — 클러스터 + 텀블링 + 머지 슬롯 구현기

**진행 기간**: 2024.06 ~ 2024.12

---

## 텀블링 슬롯이란

일반 슬롯은 스핀 한 번으로 게임이 끝난다. **텀블링 슬롯**은 다르다. 당첨 심볼이 제거되고 빈 자리를 위에서 새 심볼이 채운 뒤, 다시 당첨 여부를 판정한다. 당첨이 나면 이 과정이 반복된다.

이 슬롯은 여기에 고유한 **머지(Merge)** 메커니즘을 더했다. 클러스터 당첨 방식 + 텀블링 + 머지 세 가지가 맞물린 구조다.

---

## 핵심 흐름

```
텀블링 확인 → 클러스터 존재?
  ├─ 예: 머지 (클러스터 심볼 → 상위 심볼 1개로 변환)
  │      └─ 캐스케이딩 (빈 자리에 새 심볼 낙하)
  │           └─ 다시 텀블링 확인 (반복)
  └─ 아니오: 게임 종료
```

---

## 1. 텀블링: 중복 처리를 막는 상태 추적

텀블링에서 가장 까다로운 부분은 **"이미 처리된 심볼을 다음 사이클에서 다시 처리하지 않는 것"** 이다.

클러스터에 포함됐지만 제거되지 않고 남은 심볼(머지 결과물 등)은 다음 사이클에서 새로 낙하한 심볼과 함께 새 클러스터를 만들 수 있다. 여기까진 괜찮다. 문제는 이 심볼이 이미 처리된 심볼인지 아닌지를 구분하지 않으면 같은 심볼이 중복 계산된다는 것이다.

```java
Set<Position> processedPositions = new HashSet<>();

while (hasWin(window)) {
    List<Position> winPositions = calculateWinPositions(window);

    removeSymbols(window, winPositions);
    fillNewSymbols(window);

    // 처리된 위치를 기록 → 다음 사이클에서 제외
    processedPositions.addAll(winPositions);
}
```

각 사이클마다 처리한 위치를 명시적으로 기록하고, 다음 사이클에서는 새로 낙하한 심볼 범위만 대상으로 삼는다.

---

## 2. 머지: 클러스터 심볼을 상위 심볼 하나로 합치기

머지는 이 슬롯에만 있는 메커니즘이다.

인접한 같은 심볼이 N개 이상 모이면 **클러스터**로 인식된다. 클러스터가 생기면 해당 심볼들은 제거되고, 그 자리 중 하나에 **한 단계 위의 심볼 1개**가 배치된다.

```
RUBY 5개 클러스터 감지
  → RUBY 5개 제거
  → 클러스터 내 최하단·최좌측 위치에 SAPPHIRE 1개 배치
  → 나머지 4자리는 새 심볼 낙하
```

심볼에는 변환 체인이 있다.

```
RUBY → SAPPHIRE → EMERALD → DIAMOND → GOLD → WILD
```

머지로 생성된 상위 심볼이 새로운 클러스터를 만들면 다시 머지가 일어난다. 이 연쇄가 텀블링 슬롯 특유의 당첨 확장을 만든다.

### 여러 클러스터가 동시에 존재할 때

한 사이클에 클러스터가 여럿이면 **심볼 가치가 높은 클러스터부터** 처리한다. 머지 위치가 겹칠 수 있어서 높은 가치 심볼이 낮은 심볼의 머지 위치를 선점하면 더 유리한 결과가 나온다.

```java
// 심볼 enum 값 기준 내림차순 정렬 후 순차 처리
clusterData.currentClusterList()
    .sort((o1, o2) -> symbolEnum(o2).getValue() - symbolEnum(o1).getValue());

for (CurrentCluster cluster : sortedClusters) {
    int mergedPosition = getMergedSymbolPosition(
        reelSize,
        cluster.positions(),
        alreadyMergedPositions  // 이미 사용된 위치 제외
    );
    alreadyMergedPositions.add(mergedPosition);
    ...
}
```

`alreadyMergedPositions`로 이미 선점된 위치를 추적해 중복 배치를 막는다.

### 머지 위치 결정 방식

클러스터 내에서 **Y 내림차순(최하단), X 오름차순(최좌측)** 순서로 위치를 선택한다.

```java
Comparator<VisibleWindowPosition> mergePositionComparator =
    Comparator.comparing(VisibleWindowPosition::y, (o1, o2) -> Integer.compare(o2, o1))
              .thenComparing(VisibleWindowPosition::x);
```

화면에서 가장 아래쪽·왼쪽 위치를 기준으로 삼는 것은 클라이언트 애니메이션과의 계약이다. 머지 위치가 예측 가능해야 클라이언트가 어느 셀에서 상위 심볼을 보여줄지 일관되게 처리할 수 있다.

---

## 3. 와일드 스프레드: 원본과 파생의 경계

와일드 심볼이 나오면 인접 셀로 퍼진다. 여기서 지켜야 할 것이 하나 있다. **스프레드로 생성된 와일드가 또 다른 스프레드를 트리거하면 안 된다.**

스프레드 와일드가 다시 퍼지면 연쇄 폭발이 일어난다. 의도된 스펙이 아니다.

```java
// 원본 와일드만 먼저 확정
Set<Position> originalWilds = findOriginalWilds(window);
Set<Position> spreadPositions = new HashSet<>();

for (Position wildPos : originalWilds) {
    spreadPositions.addAll(calculateSpreadArea(wildPos, spreadConfig));
}

applyWilds(window, spreadPositions);
// spreadPositions의 와일드는 스프레드 기준에서 제외
```

원본 집합을 먼저 확정하고, 그 집합만 기준으로 스프레드를 계산한다. 텀블링과 동일한 패턴이다. 원본과 파생을 구분해야 루프가 닫힌다.

---

## 배운 것

**원본과 파생을 구분하는 것이 핵심이다.** 텀블링에서 처리된 심볼 추적, 와일드 스프레드에서 원본 와일드 확정, 머지에서 선점된 위치 관리 — 세 가지 모두 "처음 생성된 것"과 "그 결과로 파생된 것"을 명시적으로 구분하지 않으면 중복 처리나 무한 루프로 이어진다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JUnit 5
