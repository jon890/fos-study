# 슬롯 엔진 추상화 및 구조 개선

**진행 기간**: 2025.09 ~ 2025.10

---

## 배경

슬롯이 5종 이상 쌓이면서 공통 패턴이 보이기 시작했다. 처음부터 설계하려 했으면 너무 일렀을 것 같다. 반복이 눈에 보일 때 하나씩 정리했다.

개선 작업은 크게 네 가지로 나뉜다.

1. 슬롯 페이 방식 추상화 (SlotTemplate)
2. 서비스 공통 구현 추출 (BaseSlotService)
3. Config 구조 개선
4. BuyFeature 옵션 파싱 추상화

---

## 1. SlotTemplate — 페이 방식 추상화

슬롯 게임의 당첨 계산 방식은 크게 세 가지다.

| 방식 | 설명 |
|------|------|
| **라인(Line)** | 정해진 라인 위에 심볼이 일치하면 당첨 |
| **웨이(Way)** | 인접 릴에서 같은 심볼이 연속되면 당첨 (243 ways 등) |
| **클러스터(Cluster)** | 인접한 심볼끼리 묶여서 일정 수 이상이면 당첨 |

기존에는 각 슬롯이 이 계산을 직접 구현했다. 웨이 방식 슬롯을 만들 때마다 웨이 계산 로직을 직접 짰다.

`SlotTemplate`을 도입해서 페이 방식 자체를 추상화했다.

```java
// 이전: 슬롯마다 페이 계산 직접 구현
public class Slot47Service implements SlotService {
    public SpinResult spin(...) {
        // 243 way 계산 로직 직접 작성
        List<WayWin> wins = calculateWayWins(window, symbolTable);
        ...
    }
}

// 이후: 페이 방식은 템플릿에게 위임
public class Slot47Service extends BaseSlotService {
    @Override
    protected PayCalculator getPayCalculator() {
        return WayPayCalculator.INSTANCE; // 웨이 계산기 주입
    }
    // 슬롯 특화 로직만 구현
}
```

`Pay에 참여하지 않는 심볼`도 이 구조에서 해결했다. 특정 심볼을 페이 계산에서 제외해야 하는 경우가 있는데, 어드민에서 설정할 수 있도록 `SlotTemplate`에 기능을 추가했다.

---

## 2. BaseSlotService — 서비스 공통 구현 추출

`SlotService` 인터페이스에 `default` 구현이 점점 늘어나고 있었다. 인터페이스에 구현 로직이 있으면 테스트하기도 어렵고, Java의 `default` 메서드는 상태를 가질 수 없어서 한계가 있었다.

공통 구현을 `BaseSlotService` 추상 클래스로 옮겼다.

```
SlotService (인터페이스) → 계약 정의
    └─ BaseSlotService (추상 클래스) → 공통 구현
           └─ Slot47Service (구현체) → 슬롯 특화 로직
```

슬롯이 오버라이드해야 하는 메서드만 추상 메서드로 선언하고, 나머지는 `BaseSlotService`에서 처리한다.

---

## 3. Config 구조 개선

### ExtraConfig 분리

슬롯 게임 설정에는 공통 설정 외에 슬롯별 추가 설정(`ExtraConfig`)이 있다.

기존 구조:

```java
// SlotConfigFactory가 모든 슬롯의 ExtraConfig 생성 책임을 가짐
public class SlotConfigFactory {
    public ExtraConfig create(GameId gameId) {
        if (gameId == SLOT_36) return new Slot36ExtraConfig(...);
        if (gameId == SLOT_41) return new Slot41ExtraConfig(...);
        if (gameId == SLOT_47) return new Slot47ExtraConfig(...);
        ...
    }
}
```

슬롯이 늘어날수록 이 팩토리 클래스가 계속 커진다. 새 슬롯을 만들 때마다 다른 슬롯의 팩토리 코드를 수정해야 한다.

변경 후:

```java
// 각 슬롯이 자신의 ExtraConfig 구현체를 보유
public class Slot47Service extends BaseSlotService {
    @Override
    public ExtraConfig createExtraConfig(SlotConfig config) {
        return new Slot47ExtraConfig(config);
    }
}
```

팩토리는 슬롯에서 받아서 위임만 하는 역할로 단순화됐다.

### Config 응답 객체 모듈 이동

메타 서비스로 Config API를 이관하기 위한 사전 작업이다. Config 응답 객체들을 슬롯 서비스 내부에서 별도 모듈로 분리했다.

```
이전: nsc-slot-service 내부에 Config 응답 객체
이후: slot-config-model 모듈로 분리 (다른 서비스에서도 참조 가능)
```

실제 API 이관은 진행 중이고, 응답 객체 공유를 위한 모듈 구조만 먼저 잡아뒀다.

---

## 4. BuyFeature 옵션 파싱 추상화

바이피처 슬롯마다 옵션 구조가 달라서 각각 파싱 로직을 구현하고 있었다.

예를 들어 슬롯 A는 `{ "type": "SUPER", "multiplier": 3 }`이고, 슬롯 B는 `{ "featureType": "MEGA", "betMultiplier": 5 }`처럼 키 이름부터 다르다.

공통 파싱 인터페이스를 추상 클래스로 정의하고, 각 슬롯은 옵션 구조 정의만 내려주면 파싱 자체는 추상 클래스에서 처리하도록 했다.

---

## 5. StaticDataLoader 개선

### refreshAll 후 일시적 NPE

`StaticDataLoader.refreshAll()`은 슬롯의 정적 데이터(릴 테이블, 심볼 설정 등)를 전부 새로 로드하는 메서드다. 운영 중 설정이 바뀌면 이 메서드를 호출해서 갱신한다.

문제는 갱신 도중 다른 스레드가 데이터에 접근하면 NPE가 났다는 점이다.

```
스레드1: refreshAll() 진행 중
  → 기존 데이터 clear
  → 새 데이터 로드 중 ...
스레드2: 스핀 요청 → 데이터 접근 → NPE (이미 clear됨)
```

갱신이 완전히 완료된 새 데이터를 원자적으로 교체하는 방식으로 수정했다.

```java
// 수정 후: 새 데이터를 미리 만들고 교체
Map<GameId, StaticData> newData = loadAll();
this.staticData = newData; // 참조 교체는 원자적
```

### Alias 테이블 일괄 조회

슬롯의 Alias 테이블(심볼 별칭 정보)을 init, refresh할 때 게임별로 쿼리를 날리고 있었다.

게임이 수십 개면 쿼리가 수십 번 나간다. `IN` 절로 한 번에 조회하도록 수정했다.

---

## 테스트 정비

- `AbstractSlotUnitTest` → `AbstractSlotTest` 통합: 슬롯 단위 테스트의 기반 클래스를 정리
- `SlotStaticDataLoader` static 메서드 직접 호출 제거: 테스트에서 모킹이 가능하도록 스프링 빈으로 전환
- 이전 RTP 구현 제거: 새 구조로 전환한 후 남은 레거시 코드 정리

---

## 배운 것

**추상화는 반복을 충분히 경험한 뒤에.** SlotTemplate, BaseSlotService 모두 슬롯을 직접 여러 개 만들고 나서야 올바른 공통점이 보였다. 처음에 추상화하면 잘못된 경계를 그을 가능성이 높다.

**원자적 교체 패턴은 락 없이도 안전하다.** `refreshAll` 수정처럼, 새 데이터를 완성한 뒤 참조만 교체하면 읽기 스레드와의 동기화 없이도 일관성을 유지할 수 있다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JPA (Hibernate), QueryDSL
- JUnit 5, Spock
