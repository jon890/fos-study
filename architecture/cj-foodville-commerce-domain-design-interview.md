# [초안] CJ푸드빌 커머스/F&B 도메인 설계 면접 대비 — 슬롯 경험을 주문·결제·쿠폰·매장 상태 설계로 번역하기

## 왜 지금 이 주제인가

CJ푸드빌 디지털 채널 백엔드 포지션은 빕스, 더플레이스, 제일제면소, 뚜레쥬르 같은 매장 운영과 모바일/웹 주문, 멤버십, 쿠폰, 예약, 키오스크가 한 도메인 안에서 맞물리는 자리다. 면접에서 검증하려는 핵심은 "F&B 커머스 도메인을 코드와 데이터로 풀어낼 수 있는가" 한 줄로 압축된다. 흔한 함정은 두 가지다. 하나는 이력서에 적힌 슬롯/예약/SaaS 백엔드 경험을 그대로 던져놓고 면접관이 알아서 번역해 주길 기대하는 태도다. 다른 하나는 일반론적인 DDD 용어집을 외워서 답하는 태도다. 지원자 입장에서 가장 위험한 건 "예약 도메인을 했어서 비슷할 거예요" 수준의 추상적 매핑이다. 면접관이 듣고 싶은 건 슬롯 도메인의 구체적 의사결정 — `SlotTemplate`로 정책을 캡슐화한 이유, `BaseSlotService`로 공통 흐름을 추출한 이유, RCC(Race Condition Control)와 `StampedLock`을 어디에 어떻게 썼는지 — 이 주문/결제/쿠폰/매장 상태 같은 F&B 모델에서 어떤 형태로 다시 나타나는가다.

이 문서는 그 번역 작업을 인터뷰 답변 단위까지 끌고 간다. 슬롯에서 했던 결정을 F&B 도메인 4개 영역(주문, 결제, 쿠폰/멤버십, 매장 운영 상태)에 1:1로 매핑하고, 각 영역에서 4년차+ 백엔드가 받을 법한 질문과 그에 대한 답변 골격을 다듬는다. 도메인 모델링, bounded context, 상태 전이, 불변 조건, 예외 복구, 운영 관측 — 이 6가지 축을 일관되게 통과시킨다.

관련 개념 문서가 이미 있다면 — 예를 들어 `architecture/ddd-bounded-context.md`나 `architecture/state-machine-design.md` 같은 — 거기서 배운 일반론을 여기서 반복하지 않는다. 이 문서는 "내 경험을 CJ푸드빌 도메인 언어로 옮기는 답변 매뉴얼"에 집중한다.

## 슬롯 경험을 F&B 도메인으로 옮기는 일대일 매핑

먼저 면접관이 알 리 없는 슬롯 도메인을 1분 안에 그릴 수 있게 정리한다. 이 정리가 흔들리면 그 다음 질문 전부가 흔들린다.

- `SlotTemplate`: 어떤 시간대에 몇 개의 슬롯을 만들지, 슬롯 간격은 얼마인지, 휴무일/특수일 정책은 무엇인지 — **공급 측 정책**을 담는 값 객체/엔티티. 정책이 바뀌어도 이미 생성된 슬롯에는 영향 없게 한다.
- `BaseSlotService`: 슬롯 생성/조회/예약/취소/만료의 공통 흐름을 추상 클래스로 잡고, 도메인별 변형(예: 시술 vs 클래스 vs 상담)은 하위 전략 클래스로 빼낸다. 이른바 템플릿 메서드 + 전략 패턴 혼합.
- RCC + `StampedLock`: 동일 슬롯에 대한 동시 예약을 막는 레이스 제어. DB 유니크 제약을 1차 방어선으로 두되, 단일 인스턴스 메모리 경합은 `StampedLock`의 낙관적 읽기로 줄이고, 충돌이 감지될 때만 쓰기 잠금으로 승격시킨다.
- 정책/전략 분리: 가격 정책, 노쇼 정책, 취소 수수료 정책, 동시 예약 제한 정책을 도메인 코어 안 인터페이스로 두고, 외부 운영 설정에 따라 구현체를 갈아끼울 수 있게 한다.

이 4개의 결정을 F&B 도메인 4개 영역으로 옮기면 다음과 같다.

| 슬롯 도메인 결정 | F&B 도메인에서의 대응 |
| --- | --- |
| `SlotTemplate` (공급 정책) | `MenuAvailabilityPolicy`, `StoreOperationCalendar`, `CouponIssuancePolicy`, `ReservationCapacityTemplate` |
| `BaseSlotService` (공통 라이프사이클) | `BaseOrderLifecycleService`, `BasePaymentSagaService`, `BaseCouponLifecycleService` |
| RCC + `StampedLock` (동시성) | 재고 차감, 좌석/룸 예약, 쿠폰 1인 1매 제한, 결제 idempotency |
| 정책/전략 분리 | 브랜드별(빕스/더플레이스/뚜레쥬르) 가격/할인/노쇼/포장 정책 plug-in |

이 표를 머릿속에 박아 두면 어떤 도메인 질문이 와도 "슬롯에서 X였던 게 여기서는 Y입니다" 형태로 진입할 수 있다.

## 주문(Order) 도메인 — 상태 전이와 불변 조건이 핵심이다

F&B 주문은 e-commerce 주문보다 상태 전이가 더 짧고, 대신 **시간 의존 불변 조건**이 강하다. 매장이 닫히면 주문이 안 되고, 주방이 마감되면 메뉴가 빠지고, 픽업 시간이 지나면 자동 취소돼야 한다.

### 모델링 출발점

주문은 `Order`(애그리거트 루트), `OrderLine`, `OrderStatus`, `FulfillmentChannel`(매장 식사/포장/배달/사전 주문), `StoreSnapshot`(주문 시점의 매장 상태) 다섯 개로 잡는다. 여기서 `StoreSnapshot`이 핵심이다. 매장 운영 시간/메뉴/가격은 시간에 따라 바뀌지만, **이미 접수된 주문은 그 시점의 매장 상태에 묶여 있어야 한다**. 이건 슬롯에서 `SlotTemplate`이 바뀌어도 이미 생성된 슬롯은 그대로였던 결정과 똑같은 패턴이다. 주문 시점의 가격, 적용 쿠폰, 메뉴 옵션, 운영 시간은 `Order` 안에 스냅샷으로 박는다.

### 상태 전이

```
DRAFT → PLACED → ACCEPTED → IN_PREPARATION → READY → COMPLETED
                       ↓             ↓           ↓
                   REJECTED      CANCELLED   NO_SHOW
```

여기서 면접 단골 질문은 "취소 가능 시점을 어디까지 허용하는가"다. 답은 비즈니스 정책이지만, 설계 관점으로는 "취소 가능 여부는 `Order`가 자기 상태와 시간만 보고 스스로 판단할 수 있어야 한다"가 맞다. 즉 `order.cancel(now)` 호출 시 외부 서비스가 정책을 주입하는 게 아니라, 주문이 보유한 `CancellationPolicy`(스냅샷에 묶인) 가 판단한다. 이 분리가 중요한 이유는 정책이 바뀐 시점에 과거 주문이 영향받지 않게 하기 위해서다.

### 불변 조건

- 주문 총액 = 라인 금액 합 - 적용된 할인 - 사용된 포인트 + 배달료. 어떤 라인이 추가/제거돼도 이 식이 유지돼야 한다.
- `ACCEPTED` 이후 라인 변경 불가. 변경이 필요하면 별도 보정 트랜잭션(부분 취소 + 신규 주문)으로 처리한다.
- `COMPLETED` 와 `CANCELLED`는 종결 상태. 이 상태에서 들어오는 모든 명령은 idempotent 하게 무시되거나 명시적 예외가 발생해야 한다.

### 슬롯 경험을 어떻게 답변에 끼워 넣는가

> "예약 슬롯에서 슬롯 생성 시점에 가격/취소 정책 스냅샷을 슬롯에 같이 묶어 둔 적이 있습니다. 운영 측에서 정책을 바꿔도 이미 발급된 슬롯에는 영향이 없어야 했기 때문입니다. F&B 주문도 같은 구조가 필요하다고 봅니다. 메뉴 가격, 적용된 쿠폰 룰, 운영 시간 정책을 주문 시점에 `OrderSnapshot`으로 캡처해 두면, 마감 시간 변경이나 가격 인상이 진행 중인 주문에 부작용을 일으키지 않습니다."

이 한 문단이 "슬롯 도메인 경험을 F&B 주문에 어떻게 옮길 수 있나" 라는 질문의 표준 답이다.

## 결제(Payment) 도메인 — 정합성, idempotency, 보정

결제는 분산 트랜잭션의 교과서다. PG, 포인트, 쿠폰, 주문, 정산이 각자의 라이프사이클을 갖는다. 4년차 백엔드에게 면접관이 보고 싶은 건 "PG 응답이 timeout 났을 때 어떻게 합니까?" 같은 단답형이 아니라 — 그 단답을 도메인 모델 위에서 일관되게 풀어낼 수 있는가다.

### 결제 상태 전이와 보정 흐름

```
INITIATED → AUTHORIZED → CAPTURED → SETTLED
       ↓           ↓            ↓
    FAILED    AUTH_VOIDED   REFUNDED (부분/전체)
```

핵심 결정은 두 가지다.

1. **INITIATED → AUTHORIZED 사이의 unknown 상태를 명시 모델링한다.** PG 호출 후 응답이 timeout이면 결과는 셋 중 하나다 — 성공, 실패, 모름. 모름을 실패로 처리하면 중복 결제가 발생하고, 성공으로 처리하면 미결제 주문이 발생한다. 그래서 `PENDING_RECONCILIATION` 상태를 별도로 두고, 비동기 reconciliation 잡이 PG 조회 API로 진실을 확정한다.
2. **idempotency key를 결제 요청의 1급 시민으로 둔다.** `paymentRequestId`(클라가 발급) + `orderId` 조합을 unique key로 잡고, 같은 키로 들어온 재시도는 직전 결과를 그대로 반환한다.

### 슬롯 RCC 경험의 매핑

슬롯에서 `StampedLock`으로 동시 예약을 막은 경험은 결제에서는 살짝 다르게 적용된다. 결제는 단일 인스턴스 메모리 락으로 충분하지 않다. 멀티 인스턴스에서 같은 주문에 대한 결제 시도가 두 번 들어올 수 있기 때문에, **DB 레벨의 unique constraint + 분산 락(Redis 기반) + idempotency key** 3중 방어선이 표준이다. 면접 답변은 이렇게 짠다.

> "슬롯에서는 단일 프로세스 안의 메모리 경합을 `StampedLock`의 낙관적 읽기로 잡고, DB unique 제약을 최후 보루로 뒀습니다. 결제는 인스턴스 간 동시성까지 다뤄야 해서 같은 패턴을 한 단계 위로 올립니다 — 1차는 idempotency key 기반의 빠른 short-circuit, 2차는 Redis 분산 락, 3차는 `payment(order_id, idempotency_key)` 컬럼 unique 제약. PG timeout처럼 결과를 모르는 상태는 별도 상태로 모델링하고, reconciliation 잡으로 확정합니다."

### 보정 트랜잭션과 saga

부분 환불, 쿠폰 복원, 포인트 복원, 재고 복원이 결제 1건과 묶인다. 동기 트랜잭션으로 묶을 수 없어서 saga로 푼다. 이때 `BasePaymentSagaService`처럼 공통 흐름(시도 → 보상 → 결과 기록 → 알림)을 추상 클래스로 잡고, 환불 사유별 보상 정책은 전략으로 빼는 구조가 슬롯의 `BaseSlotService` 경험과 1:1로 대응한다.

## 쿠폰/멤버십 도메인 — 동시성과 정책 plug-in

쿠폰은 보기에 단순해 보이지만 면접에서 깊이 있게 들어가는 영역이다.

### 쿠폰의 본질적 모델

`CouponPolicy`(발급 가능 조건/할인 룰), `CouponIssuance`(개별 발급 인스턴스), `CouponUsage`(사용 기록) 세 개로 분리한다. 흔한 실수는 `Coupon` 한 개 엔티티에 정책+상태를 다 욱여넣는 것이다. 이러면 정책이 바뀔 때 발급된 쿠폰을 어떻게 처리할지 결정이 안 선다.

### 핵심 동시성 시나리오

- 1인 1매 쿠폰을 동시에 두 번 받기 시도
- 한도 1만 장 쿠폰의 마지막 1장을 동시에 발급 시도
- 한 주문에 같은 쿠폰을 두 번 적용 시도

세 시나리오 모두 슬롯의 RCC 경험과 동형이다. "공급이 유한한데 수요가 동시에 몰린다"는 똑같은 문제다. 답변 골격은:

> "한도형 쿠폰은 슬롯 동시 예약과 같은 문제로 봤습니다. 1차로 `coupon_policy.issued_count` 를 atomic update(`UPDATE ... WHERE issued_count < total_limit`)로 처리하고, 2차로 `coupon_issuance(policy_id, user_id)` unique 제약으로 1인 1매를 강제합니다. 인스턴스 내 burst가 심한 시간대(이벤트 오픈 직후)는 슬롯에서 했던 것처럼 짧게 메모리 락으로 묶어 DB 부하를 줄이는 것도 검토합니다."

### 정책 plug-in

브랜드별(빕스 vs 뚜레쥬르) 할인 룰, 등급별 멤버십 할인, 시간대별 happy hour 할인이 같은 주문에 동시에 걸린다. 이걸 `if-else`로 풀면 6개월 안에 코드가 못 읽게 된다. `DiscountStrategy` 인터페이스 + 우선순위 기반 체인으로 풀고, 적용 결과를 `AppliedDiscount` VO 리스트로 주문에 박아 둔다. 슬롯에서 노쇼 정책/취소 수수료 정책을 전략으로 분리한 경험이 그대로 옮겨진다.

## 매장 운영 상태 — 시간 의존 도메인

빕스 한 매장은 영업 중/휴게/마감 준비/마감/임시 휴무/시스템 점검 같은 상태를 가진다. 이 상태가 주문 가능 여부, 예약 가능 여부, 픽업 가능 여부를 좌우한다.

### 잘못된 설계와 개선된 설계

나쁜 예 — 매장 상태를 boolean 플래그로 흩뿌려 두는 것:

```java
class Store {
    boolean isOpen;
    boolean isAcceptingOrders;
    boolean isAcceptingReservations;
    boolean isOnBreak;
}
```

이러면 "주문은 받지만 예약은 안 받는 마감 30분 전" 같은 조합이 발생할 때 플래그 4개의 조합을 운영자가 일일이 맞춰야 한다. 곧 데이터가 깨진다.

개선된 예 — 상태를 단일 enum으로 좁히고, 능력(capability)을 상태에서 파생시킨다:

```java
enum StoreOperationalState {
    OPEN, BREAK, CLOSING_SOON, CLOSED, TEMPORARY_CLOSED, MAINTENANCE;

    boolean canAcceptDineIn() { /* OPEN, CLOSING_SOON */ }
    boolean canAcceptTakeout() { /* OPEN, CLOSING_SOON */ }
    boolean canAcceptReservation() { /* OPEN only */ }
}
```

상태 전이는 운영 시간 캘린더(`StoreOperationCalendar`)와 운영자 수동 개입(`ManualStateOverride`) 두 입력으로 결정되고, 이 결정은 `StoreOperationStateService`가 매분 단위 스케줄러 + 이벤트 트리거로 갱신한다.

### 슬롯 `SlotTemplate` 경험과의 매핑

`StoreOperationCalendar`는 사실상 슬롯의 `SlotTemplate`이 매장 운영에 옮겨 온 형태다. "특정 요일/시간/특수일에 어떤 운영 상태가 활성화되는가"를 정의하고, 캘린더가 바뀌어도 진행 중인 주문/예약은 영향받지 않게 한다.

## 운영 관측 — 면접에서 가산점이 되는 영역

도메인 설계 답변에서 4년차+ 후보를 가르는 건 "이 모델이 운영 중에 어떻게 보일까"를 같이 말할 수 있는가다.

- 주문 상태 전이마다 도메인 이벤트(`OrderPlaced`, `OrderAccepted`, `OrderCancelled`)를 발행하고, 이벤트 자체를 outbox 테이블에 기록한다. 이게 audit log + 분석 파이프라인 + 알림의 단일 진실 원본이 된다.
- 결제 `PENDING_RECONCILIATION` 상태에 머무는 결제의 개수/시간을 메트릭으로 노출한다. 이게 임계치 넘으면 PG 장애 의심 신호다.
- 쿠폰 발급 실패율을 `policy_id` 단위로 메트릭화한다. 한도 소진 vs 시스템 오류를 구분할 수 있어야 한다.
- 매장 상태 전이가 캘린더와 어긋나는 케이스(수동 override가 풀리지 않은 상태)를 일일 리포트로 뽑는다.

## 로컬 실습 환경

개념만 이해하고 면접장에 가면 한 단계 더 깊은 질문에서 흔들린다. 다음 미니 프로젝트로 손에 익혀 둔다.

### 환경

- Java 17, Spring Boot 3, MySQL 8, Redis 7
- `docker-compose.yml` 한 파일로 MySQL + Redis 띄움

### 실습 1: 주문 상태 전이 + 스냅샷

`Order` 애그리거트, `OrderSnapshot` 값 객체, 상태 전이를 `state` 패턴으로 구현. `order.cancel(now)`가 스냅샷에 묶인 `CancellationPolicy`로만 판단하도록 강제한다.

```java
class Order {
    private OrderStatus status;
    private OrderSnapshot snapshot;
    private Instant placedAt;

    void cancel(Instant now) {
        if (!status.isCancellable()) {
            throw new IllegalOrderStateException(status);
        }
        var fee = snapshot.cancellationPolicy().calculateFee(this, now);
        this.status = OrderStatus.CANCELLED;
        registerEvent(new OrderCancelled(id, fee, now));
    }
}
```

테스트는 "정책이 바뀐 뒤에 취소해도 옛날 정책으로 계산되는가"를 검증한다.

### 실습 2: 쿠폰 한도형 발급 동시성

100개 한도 쿠폰을 1000명이 동시에 받는 시나리오를 JMeter로 재현. 세 가지 구현을 비교한다.

1. 단순 `SELECT count + INSERT`: race condition으로 한도 초과 발생 확인
2. `UPDATE coupon_policy SET issued_count = issued_count + 1 WHERE issued_count < limit_count`: 한도 정확히 지켜짐 확인
3. Redis `INCR` + 사후 DB 동기화: 처리량은 더 높지만 장애 시 정합성 회복 비용 발생 확인

이 비교 결과를 면접에서 그대로 말할 수 있게 숫자를 같이 외워 둔다.

### 실습 3: 결제 idempotency

같은 `paymentRequestId`로 동일 주문에 결제 요청을 5번 동시에 보내는 테스트. 1번만 PG로 나가고 나머지 4번은 같은 결과를 반환하는지 확인한다. PG timeout을 인위적으로 흉내 내는 mock 어댑터를 두고 `PENDING_RECONCILIATION` 상태가 정상 형성되는지 확인한다.

## 면접 답변 프레이밍

같은 질문도 4년차의 답은 "구조 + 트레이드오프 + 운영"이 한 답에 들어 있어야 한다. 자주 나올 질문 5개와 답변 골격이다.

**Q1. 메뉴 가격이 자주 바뀌는데 진행 중인 주문이 영향받지 않게 하려면 어떻게 설계하시겠어요?**

> "정책과 주문을 분리합니다. 메뉴 가격은 `Menu`/`Price`에 살아 있지만, 주문이 들어오는 시점에 `OrderSnapshot`으로 가격/적용 쿠폰/운영 시간을 박아 둡니다. 이후 가격 변경은 신규 주문에만 영향이 가고, 진행 중인 주문은 스냅샷 기반으로 계산이 끝까지 일관됩니다. 비슷한 패턴을 슬롯 예약에서 `SlotTemplate` 변경이 기존 슬롯에 영향 없게 처리할 때 썼고, 그때의 핵심 학습은 '정책 객체를 도메인에서 끌어다 쓰는 것이 아니라, 도메인이 자기 안에 정책의 결정 결과를 들고 있는 게 더 안정적이다' 였습니다."

**Q2. 한도 1만 장 쿠폰 발급에 동시 요청이 몰리면 어떻게 처리하시나요?**

> "DB atomic update를 1차 방어선으로 둡니다. `UPDATE coupon_policy SET issued_count = issued_count + 1 WHERE id = ? AND issued_count < total_limit` — affected rows가 1이면 발급, 0이면 한도 초과로 fail-fast 합니다. 1인 1매는 `coupon_issuance(policy_id, user_id)` unique 제약으로 강제합니다. 인스턴스 안 burst가 심한 구간은 슬롯에서 했던 것처럼 짧은 메모리 락으로 DB 부하를 줄이는 옵션을 둡니다. Redis `INCR` 같은 캐시 기반 카운터는 처리량은 매력적이지만 장애 시 정합성 회복 비용이 커서 한도형은 DB를 1차로 두는 편을 선호합니다."

**Q3. PG 결제 응답이 타임아웃 됐어요. 클라이언트 입장에서 결제가 됐는지 모르는 상태인데 어떻게 풀어요?**

> "결과를 모르는 상태를 명시적으로 모델링합니다. `INITIATED` → `AUTHORIZED` 사이에 `PENDING_RECONCILIATION` 상태를 두고, 그 상태에 들어간 결제는 별도 reconciliation 잡이 PG 조회 API로 사후 확정합니다. 이렇게 하면 timeout을 무리하게 실패로 단정해서 발생하는 중복 결제, 또는 성공으로 단정해서 발생하는 미결제 주문 둘 다 막을 수 있습니다. 추가로 idempotency key를 결제 요청에 강제해서, 같은 키 재시도가 들어오면 직전 결과를 그대로 반환합니다."

**Q4. 매장 상태가 영업 중/마감 준비/임시 휴무 같이 여러 가지인데, boolean 플래그 여러 개로 관리하는 게 나은가요 단일 enum이 나은가요?**

> "단일 enum + 능력 파생이 더 안전합니다. boolean이 4개 있으면 16가지 조합 중 의미 없는 조합이 9개쯤 됩니다. 운영자가 실수로 isAcceptingOrders=false인데 isOpen=true인 상태를 만드는 게 가능해지죠. 단일 `StoreOperationalState` enum을 두고 dine-in/takeout/reservation 가능 여부는 상태에서 파생시키면, 잘못된 조합 자체가 표현 불가능해집니다. 도메인 설계에서 'illegal state unrepresentable'을 우선시하는 편입니다."

**Q5. 본인이 가장 자신 있게 설계한 도메인 사례 한 가지를 말해 주세요.**

> "예약 슬롯 도메인입니다. `SlotTemplate`로 공급 측 정책을 캡슐화하고, `BaseSlotService`로 라이프사이클 공통 흐름을 잡고, 정책별 변형은 전략 클래스로 빼서 브랜드/카테고리별로 plug-in 했습니다. 동시 예약은 DB unique 제약을 최후 보루로 두고, 단일 인스턴스 burst는 `StampedLock`의 낙관적 읽기로 줄였습니다. 이 설계의 가장 큰 효과는 신규 카테고리가 들어올 때 코어를 안 건드리고 전략 하나만 추가하면 됐다는 점입니다. F&B 주문/결제/쿠폰 도메인도 정책-전략-공통 라이프사이클의 같은 구조로 풀 수 있다고 봅니다."

## 자주 빠지는 함정

- 슬롯 경험을 그대로 옮기려다 "예약은 슬롯이고 주문은 슬롯이 아닌데요?" 같은 반박에 막힘. 슬롯의 **결정 패턴**을 옮기는 거지 **자료 구조**를 옮기는 게 아니라는 점을 분명히 한다.
- DDD 용어(애그리거트, 바운디드 컨텍스트)를 써놓고 정작 코드 예시는 트랜잭션 스크립트로 답하기. 용어를 썼으면 코드도 그 형태여야 한다.
- 동시성 답변에서 "락을 거시면 됩니다"로 끝내기. 어느 레벨의 락인지(메모리/분산/DB), 왜 그 레벨인지, 실패 시 회복은 어떻게 되는지까지 30초 안에 한 묶음으로 말한다.
- 운영 관측을 빼먹기. 도메인 이벤트, 메트릭, 보정 잡까지 한 답에 묶여야 4년차 답이 된다.
- 보안/민감 정보를 면접 답변에서 흘리기. 이전 회사의 내부 시스템 명, 파트너사 명, 매출 수치는 일반화해서 말한다.

## 체크리스트

- [ ] 슬롯 도메인의 4가지 결정(`SlotTemplate`, `BaseSlotService`, RCC+`StampedLock`, 정책/전략 분리)을 30초 안에 설명할 수 있다
- [ ] 위 4가지를 주문/결제/쿠폰/매장 상태에 어떻게 매핑하는지 영역별 1문단으로 답할 수 있다
- [ ] `OrderSnapshot`이 왜 필요한지 가격 변경 시나리오로 답할 수 있다
- [ ] 결제 timeout 시 `PENDING_RECONCILIATION` + idempotency key + reconciliation 잡 3중 구조를 묘사할 수 있다
- [ ] 한도형 쿠폰 발급에 atomic update vs Redis `INCR` 트레이드오프를 비교할 수 있다
- [ ] 매장 상태를 단일 enum + 파생 능력으로 모델링하는 이유를 'illegal state unrepresentable' 관점에서 답할 수 있다
- [ ] 모든 답변에 운영 관측(이벤트, 메트릭, 알림) 한 줄을 같이 붙일 수 있다
- [ ] 회사 내부 시스템 명/매출 수치 없이 일반화된 표현으로 경험을 말한다
- [ ] 로컬 실습 3개를 직접 돌려서 숫자(처리량, 성공률, 타임아웃 비율)를 외워 두었다
- [ ] DDD 용어를 쓰면 그 답의 코드 형태도 같은 패러다임으로 일관되게 답한다
