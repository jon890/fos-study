# Admin 슬롯 비교/복사 기능 개발

**진행 기간**: 2024.07 ~ 2024.12

---

## 배경

슬롯 개발 배포 파이프라인은 dev → alpha → real 순서다. dev에서 시뮬레이터로 최종 검증을 마치고, alpha에서 QA를 거친 뒤 real로 올라간다.

문제는 환경 간 슬롯 설정 데이터를 동기화하는 방법이었다. 슬롯이 20~30개일 때는 수동으로 JSON을 복사해서 붙여넣는 방식으로 버텼다. 그런데 슬롯 수가 30개를 넘어 40개를 향해가면서 두 가지 문제가 커졌다.

1. **시간**: 슬롯마다 직접 JSON을 복사하면 슬롯 수에 비례해서 작업 시간이 늘어났다
2. **가시성**: 어떤 슬롯이 동기화됐는지, 어떤 슬롯이 환경 간에 달라졌는지 알 수가 없었다

두 번째 문제가 더 컸다. 특정 슬롯이 alpha에서 수정됐는데 real에 반영됐는지 아닌지를 누군가 직접 확인해야 했다. 시스템적으로 변경 내역을 추적하고 동기화하는 기능이 필요해서 어드민에 비교/복사 기능을 만들게 됐다.

---

## 구조 설계

### source → target 방식

처음에 고려한 것은 JSON export/import였다. 슬롯 설정을 JSON으로 내보내고, 다른 환경에서 붙여넣는 방식이다. 단순하고 구현도 쉽다.

그런데 이 방식은 "가시성" 문제를 해결하지 못한다. JSON을 복사해서 붙여넣었는지 안 했는지는 여전히 사람이 기억해야 한다. 슬롯이 40개면 40번의 판단이 필요하다.

최종적으로 선택한 구조는 **두 환경 DB를 하나의 어드민 앱에서 직접 연결해서 비교/복사하는 방식**이다. 어드민이 두 DB에 동시에 접근하므로, 비교와 복사가 서버 사이드에서 처리된다.

```
ORIGINAL DB (현재 환경)   COMPARE DB (다음 환경)
      슬롯 설정 ──── 비교 ────▶ 슬롯 설정
                              (다른 항목 목록 반환)

      슬롯 설정 ──── 복사 ────▶ 슬롯 설정 (덮어쓰기)
                              version은 복사 시각으로 신규 부여
                              잭팟 UUID는 target에서 새로 생성
```

파이프라인에서 dev→alpha, alpha→real은 같은 기능을 재사용한다. 어드민 앱이 어느 환경에 배포되느냐에 따라 ORIGINAL/COMPARE가 달라지는 구조다.

### 두 DB 동시 연결 방식의 트레이드오프

**장점:**

- 비교와 복사가 사람 손을 거치지 않아 human error 없음
- 전체 슬롯 비교를 시스템이 자동으로 처리 → 가시성 확보
- 슬롯 수가 늘어도 작업 시간이 일정

**고려한 위험:**

- 하나의 앱이 두 환경 DB 자격증명을 동시에 보유

이 위험을 완화하는 방법으로 **feature flag 패턴**을 적용했다.

### Feature Flag — `@CompareSlotEnabled`

real 환경에서는 복사할 "다음 환경"이 없다. 그런데 real 어드민에도 같은 코드가 배포된다. 잘못 설정되면 real DB에서 다른 환경으로 복사하는 사고가 날 수 있다.

이를 위해 `@CompareSlotEnabled`를 만들었다.

```java
@ConditionalOnProperty(
    name = "spring.datasource.hikari.compare-product-enabled",
    havingValue = "true"
)
public @interface CompareSlotEnabled {}
```

`compare-product-enabled=true`가 명시적으로 설정되어 있어야만 비교/복사 관련 Bean이 생성된다. 설정이 없으면 Bean 자체가 없으므로, real 환경에서는 기능이 완전히 비활성화된다. property 누락이 안전한 기본값(비활성화)이 되는 구조다.

`CompareSlotService`, `SlotCompareRepositoryFactory` 등 비교/복사 관련 클래스 전체에 이 어노테이션이 붙어 있다.

---

## 구현에서 어려웠던 것들

### 깊은 비교 (Deep Comparison)

슬롯 설정은 중첩된 객체 구조다. Reflection으로 필드를 순회하면서 비교하는 `SlotGameComparer`를 만들었다.

비교 대상 필드는 명시적으로 관리한다.

```java
private static final Set<String> compareFieldNames = Set.of(
    "title", "reelSize", "credit", "tumble", "volatility",
    "symbols", "payline", "reelGroups", "slotExtra", "jackpotType",
    "totalBetItem", "mathType", "description", ...
);
```

비교에서 의도적으로 제외하는 필드들이 있다.

**잭팟 UUID**: 환경마다 UUID가 달라서 단순 비교 시 항상 "다르다"고 나온다. 잭팟은 UUID를 제외하고 실제 내용(jackpotElements)만 비교하도록 별도 처리했다.

**version**: 복사 시각을 기준으로 새로 부여되는 값이라 비교 대상이 아니다.

HibernateProxy로 래핑된 연관 엔티티도 처리가 필요했다. 프록시 객체를 그대로 비교하면 항상 다르다고 판정된다. 프록시 여부를 확인하고 실제 ID를 꺼내서 비교하는 로직을 추가했다.

### 복사 시 고유값 재생성

Alpha 데이터를 Real로 복사할 때 그대로 복사하면 안 되는 값들이 있다.

| 항목            | 처리 방법                                                          |
| --------------- | ------------------------------------------------------------------ |
| `version`       | 복사 시각(`yyyy.MM.dd.HHmmss`)으로 새로 부여                       |
| 잭팟 `uuid`     | target에 기존 잭팟이 있으면 내용만 업데이트, 없으면 새 UUID로 생성 |
| 시나리오 `uuid` | 복사 시 새로 발급                                                  |

잭팟 복사는 멱등성을 고려해서 설계했다. 같은 슬롯을 여러 번 복사해도 잭팟이 중복 생성되지 않는다. target에 잭팟이 이미 있으면 내용만 갱신한다.

### 비교 대상 DB가 null인 경우

target DB에 아직 없는 슬롯을 비교할 때 target 객체가 null이면 예외가 났다. target이 null이면 비교하지 않고 바로 "다르다"고 판정하도록 처리했다. 신규 슬롯도 비교 목록에 정상 표시된다.

### 어드민 슬로우 쿼리

슬롯 목록 전체 비교 시 슬롯이 늘수록 응답 시간이 길어졌다. 쿼리 실행 계획을 확인해서 불필요한 JOIN을 제거하고, N+1 문제도 해결했다.

---

## 배운 것

**가시성이 생기면 운영이 달라진다.** 이 기능을 만들고 나서 두 가지가 편해졌다. 첫째, 어떤 슬롯이 환경 간에 다른지 한눈에 볼 수 있게 됐다. 어떤 프로퍼티가 다른지도 필드 단위로 확인할 수 있어서 "뭔가 다른데 뭐가 다른지 모르겠다"는 상황이 사라졌다. 둘째, version이 복사 시각(`yyyy.MM.dd.HHmmss`)으로 기록되기 때문에 언제 동기화가 이뤄졌는지 바로 파악할 수 있다.

**JSON copy/paste는 규모가 커지면 한계가 온다.** 슬롯이 적을 때는 수동 방식이 더 빠르게 느껴진다. 그런데 "어떤 슬롯이 동기화됐는지 알 수 없다"는 문제는 슬롯이 많아질수록 점점 더 크게 느껴진다. 이런 가시성 문제는 수동 방식으로는 해결이 안 된다.

**feature flag는 "설정 없음"이 안전한 기본값이 되도록 설계해야 한다.** `@ConditionalOnProperty`로 property가 없으면 Bean이 생성되지 않는 구조를 선택한 이유다. 반대로 "설정 없음 = 기능 활성화"였다면, real 환경에서 실수로 활성화될 위험이 있었다.

**깊은 객체 비교는 엣지 케이스가 많다.** UUID처럼 환경마다 다른 게 당연한 필드, HibernateProxy로 래핑된 연관 엔티티, null 처리 등 실제로 써봐야 보이는 케이스들이 있었다. 복잡한 도메인 객체의 비교 로직은 단위 테스트를 꼼꼼하게 작성해야 한다.

---

## 사용 기술

- Java 17, Spring Boot 3.x
- JPA (다중 DataSource, `@Qualifier` 기반 Repository 분기)
- `@ConditionalOnProperty` (feature flag 패턴)
- JUnit 5
