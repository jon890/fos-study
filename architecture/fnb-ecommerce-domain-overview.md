# [초안] F&B · e-Commerce 디지털 채널 도메인 한 장 정리

## 왜 이 문서가 필요한가

레스토랑·베이커리·면요리 등 여러 브랜드를 운영하는 멀티브랜드 F&B 운영사의 디지털 채널 백엔드는 단순히 "주문 API"를 만드는 일이 아니다. 같은 회원이 어제는 매장에서 결제하고 오늘은 앱에서 픽업을 잡고 내일은 외부 배달사로 같은 메뉴를 시킨다. 가격은 매장별·시간대별로 달라지고, 쿠폰은 브랜드 단위와 멤버십 등급에 따라 중첩되며, 정산은 결제대행사·배달사·매장 가맹주에게 동시에 분배된다. 이 도메인을 "주문 들어오면 결제하고 주방에 알려주는 시스템" 수준으로만 다루면 운영 중 터지는 정합성 문제를 감당하기 어렵다.

이 문서는 F&B 디지털 채널의 전체 그림을 bounded context 단위로 끊어서 정리한다. 각 컨텍스트에서 어떤 엔티티가 핵심이고, 데이터가 어떤 순서로 흐르며, 운영 중에 자주 깨지는 정합성·장애 패턴이 무엇인지까지 짚는다. 마지막으로 캐시 정합성·Kafka Outbox·운영 제약 대응 같은 인프라 패턴을 F&B 도메인 언어로 어떻게 적용하는지 설계 예시까지 둔다.

## 디지털 채널 비즈니스의 큰 그림

F&B e-Commerce의 가치사슬은 다섯 단계로 정리할 수 있다.

1. **매장·메뉴 운영** — 본사/가맹주가 어떤 매장을 열고, 어떤 메뉴를 어떤 가격으로 판다고 등록한다.
2. **고객 유치** — 회원/멤버십/쿠폰/프로모션으로 트래픽을 채널에 가둔다.
3. **주문 체결** — 앱·웹·키오스크·콜센터·외부 채널에서 주문이 들어와 결제까지 완료한다.
4. **이행**(fulfillment) — 매장 POS/주방/픽업 카운터/배달 라이더에게 작업이 분배되어 손님에게 전달된다.
5. **사후 처리** — 클레임/환불/리뷰/정산이 일어나고, 데이터가 분석/CRM/마케팅으로 환류된다.

겉에서 보면 "주문 → 결제 → 배달"이지만 운영 시스템 관점에서는 위 다섯 단계가 모두 별도 트랜잭션 경계, 별도 SLA, 별도 외부 연동 책임을 갖는다. 이게 그대로 bounded context의 후보가 된다.

## Bounded Context 구분

DDD 관점에서 F&B 디지털 채널은 보통 다음 컨텍스트로 쪼개진다. 모놀리스로 시작해도 모듈 경계는 이 라인을 따르는 것이 안전하다.

- **Identity / Member** — 회원, 인증, 등급, 동의/약관, 마케팅 수신.
- **Catalog** — 브랜드, 매장, 메뉴, 옵션, 카테고리, 매장-메뉴 가용성.
- **Pricing & Promotion** — 정상가, 매장별 가격, 시간대 가격, 쿠폰, 멤버십 할인, 적립.
- **Cart & Order** — 장바구니, 주문 생성, 상태 머신, 옵션 스냅샷.
- **Payment** — PG 연동, 승인, 부분 취소, 결제수단 토큰화.
- **Fulfillment** — 매장 접수, 조리 상태, 픽업 콜, 배달 디스패치, 배달 추적.
- **Claim / Refund** — 취소, 환불, CS 티켓, 보상 쿠폰 발행.
- **Settlement** — 매장/가맹주/배달사/PG 정산, 세금계산서.
- **Notification** — 푸시, LMS, 카카오 알림톡, 인앱 메시지.
- **Backoffice** — 본사 운영, 점주 운영, 마케터 운영, 권한 분리.
- **Integration / Anti-Corruption** — PG, 배달중개, 알림 채널, ERP, 회계, 데이터 웨어하우스.

"어디서부터 어디까지 한 서비스가 책임지는가"는 이 11개 컨텍스트 중 묶음을 어떻게 잡았는지로 결정된다. 예를 들어 모놀리스라면 주문/결제/이행을 한 서비스에 두되 모듈로 쪼개고, Catalog와 Member는 다른 채널과 공유 가능하도록 분리하는 식이다.

## 핵심 엔티티 모델 — 각 컨텍스트별로 뼈대만

### Identity / Member

- `Member` (id, ci/di, status, tier, joinedAt)
- `Auth` (member_id, provider, externalId)
- `Consent` (member_id, type, agreedAt, version)
- `Address` (member_id, label, addr1, addr2, lat/lng)
- `Device` (member_id, pushToken, platform)

CI/DI 같은 본인확인값은 PII 등급 최상위라 컬럼 자체를 KMS 암호화 + 별도 테이블로 분리하는 게 일반적이다. 등급 변경은 이벤트로 발행해서 가격/쿠폰 컨텍스트가 구독한다.

### Catalog

- `Brand` (id, code, name)
- `Store` (id, brand_id, code, type[direct/franchise], lat/lng, openHours)
- `Menu` (id, brand_id, name, baseImage, taxType, allergens[])
- `MenuOptionGroup` (id, menu_id, type[single/multi], min/max)
- `MenuOption` (id, group_id, name, extraPrice)
- `StoreMenu` (store_id, menu_id, isAvailable, soldOutUntil)

`Menu`와 `StoreMenu`를 분리하는 게 핵심이다. 본사가 정의한 "메뉴 마스터"와 매장에서 실제 팔 수 있는지 여부는 별개이고, "오늘 떡갈비 떨어졌어요" 같은 운영 이벤트는 `StoreMenu`만 건드린다.

### Pricing & Promotion

- `Price` (menu_id, store_id?, channel?, validFrom, validTo, amount)
- `Coupon` (id, code, type[fixed/percent], min/max, target[brand/menu/store], stackable)
- `IssuedCoupon` (id, coupon_id, member_id, status, issuedAt, usedAt)
- `Promotion` (id, period, target, ruleJson)
- `LoyaltyPoint` (member_id, balance) + `LoyaltyTxn`

가격 결정은 "가장 좁은 범위가 이긴다" 규칙(매장-채널-시간 구간이 우선, 없으면 브랜드 정상가)으로 풀면 설명이 깔끔하다.

### Cart & Order

- `Cart` (id, member_id or guestKey, store_id, channel, expiresAt)
- `CartItem` (cart_id, menu_id, qty, optionsJson, unitPriceSnapshot)
- `Order` (id, orderNo, member_id, store_id, channel, status, totalAmount, payAmount, discountAmount, placedAt)
- `OrderItem` (order_id, menu_id, qty, optionsJson, unitPriceSnapshot, discountAllocated)
- `OrderEvent` (order_id, type, payloadJson, occurredAt) — 상태 머신 이력

"옵션 스냅샷"이 중요하다. 메뉴/옵션이 나중에 바뀌어도 과거 주문 영수증·정산은 주문 시점 가격으로 굳어 있어야 한다. 마스터 테이블 조인으로만 영수증을 그리는 설계는 정산이 깨진다.

### Payment

- `Payment` (id, order_id, pg, method, amount, status, approvedAt, approvalNo)
- `PaymentEvent` (payment_id, type, rawPayloadJson)
- `PaymentMethodToken` (member_id, pg, billingKey)
- `Refund` (payment_id, amount, reason, refundedAt, status)

PG 연동은 반드시 ACL(Anti-Corruption Layer)로 감싼다. 카드사 응답 코드, 부분 취소 가능 여부, 빌링키 발급 흐름이 PG마다 달라서 도메인 모델이 PG 어휘에 오염되면 다른 PG로 바꾸기 매우 어렵다.

### Fulfillment

- `OrderFulfillment` (order_id, type[dineIn/pickup/delivery], status)
- `KitchenTicket` (id, order_id, station, status, startedAt, finishedAt)
- `PickupSlot` (store_id, slot, capacity)
- `DeliveryDispatch` (order_id, agency, externalId, riderInfo, etaAt, status)

배달은 자체 배달과 배달중개사(배민/요기요/쿠팡이츠 등) 위탁의 두 가지 패턴이 공존하고, 같은 주문이라도 매장별·시간대별로 분기된다. `agency` 컬럼이 있고 ACL로 감싸야 추후 변동에 견딘다.

### Claim / Refund

- `Claim` (id, order_id, type[cancel/refund/compensation], reason, status)
- `ClaimItem` (claim_id, order_item_id, qty, refundAmount)
- `CsTicket` (id, member_id, order_id?, channel, status)

부분 취소가 자주 깨진다. 결제 부분 취소 ↔ 정산 분개 ↔ 적립금 회수 ↔ 쿠폰 복원이 묶여 있어서 한쪽만 성공하면 즉시 데이터 정합성 오류가 된다.

### Settlement

- `SettlementBatch` (id, period, status)
- `SettlementEntry` (batch_id, partyType[store/agency/pg], partyId, amount, basis)
- `Invoice` / `TaxInvoice`

정산은 주문/결제와 다른 시간 축으로 일어난다. 주문은 실시간이지만 정산은 일/주/월 배치다. 그래서 주문 컨텍스트가 발행한 도메인 이벤트를 정산 컨텍스트가 별도 테이블에 누적하고, 배치가 그 누적분을 읽어 분개한다.

### Notification

- `NotificationOutbox` (id, type, target, payloadJson, status)
- 채널 어댑터(`PushAdapter`, `KakaoAlimtalkAdapter`, `LmsAdapter`)

알림은 도메인 이벤트의 가장 흔한 소비자다. 동기 송신은 절대 금지(외부 API 장애가 주문 체결을 막는다).

### Backoffice

- 본사 마스터 등록(브랜드/메뉴/가격)
- 점주 운영(매장 영업시간/품절/슬롯)
- 마케터(쿠폰/프로모션 발행)
- CS(클레임 처리)

권한은 RBAC + ABAC(특정 매장만 보이는 점주) 복합이 일반적이다.

## 채널 토폴로지 — 누가 누구에게 말하는가

```
[앱/웹/키오스크/콜센터]
        |
        v
   [BFF / API Gateway]
        |
        v
+----------------------+        +-----------+
| 디지털 채널 백엔드      |<----->|  Catalog  |
|  (주문/결제/이행)       |        +-----------+
+----------------------+        +-----------+
        |  ^   ^   ^             |  Member   |
        |  |   |   |             +-----------+
        v  |   |   |             +-----------+
       [PG] |   |   +----------> | Pricing   |
            |   |                +-----------+
            |   +-> [배달중개사 API]
            +-> [매장 POS / KDS]
```

핵심은 "프론트 → BFF → 도메인 백엔드"의 계층 분리다. 외부 채널(키오스크, 콜센터, 외부 배달앱)은 별도의 진입점을 갖지만 내부 도메인 백엔드의 API 계약은 단일하게 유지하는 게 운영상 유리하다.

## 핵심 데이터 흐름 6가지

### 1. 주문 체결 흐름 (앱 픽업 주문 기준)

1. 클라이언트가 매장+메뉴+옵션으로 견적 요청 → 가격/쿠폰 적용 결과 반환(서버 권위 가격).
2. 클라이언트가 주문 생성 요청 → `Order`가 `PENDING_PAYMENT`로 저장 + `OrderItem`에 가격 스냅샷.
3. PG 결제 승인 → `Payment` `APPROVED`.
4. `Order`가 `PAID`로 전이 → 도메인 이벤트 `OrderPaid` 발행.
5. Fulfillment가 이벤트 구독 → `KitchenTicket` 생성, 매장 KDS 푸시.
6. 알림 컨텍스트가 같은 이벤트 구독 → 알림톡 발송.

이 흐름의 핵심 정합성 포인트는 "결제 승인과 주문 상태 전이의 원자성"이다. PG 콜백이 두 번 오거나, 결제 성공 후 주문 갱신이 실패하는 케이스가 가장 흔하다. Outbox + idempotency key가 표준 답이다.

### 2. 배달 외부 채널 주문 유입 (배달중개사 → 자사 시스템)

1. 배달앱이 자사 매장에 주문을 푸시 → ACL이 매장/메뉴 매핑(외부 메뉴ID ↔ 내부 menuId)을 통해 정규화.
2. `Order` 생성, `payment` 컨텍스트는 외부 정산 모드로 마킹(자사 PG 미사용).
3. 매장 KDS로 전달, 라이더 디스패치는 외부 시스템 책임.
4. 정산 시 외부 채널 수수료를 포함해 분개.

여기서 자주 깨지는 게 메뉴 매핑이다. 본사에서 메뉴를 리뉴얼했는데 외부앱의 매핑 테이블이 갱신 안 되면 주문은 들어오는데 매장에서 못 만든다.

### 3. 쿠폰/프로모션 적용 흐름

1. 장바구니 시점에 `PromotionEvaluator`가 후보 쿠폰을 모아 적용 시뮬레이션.
2. 동시에 사용 가능한 쿠폰의 stack 가능 여부 판정(중복 사용 정책).
3. 주문 확정 시 `IssuedCoupon`을 `RESERVED` 상태로 잡고 결제 성공 후 `USED`로 전이.
4. 결제 실패/취소 시 자동 복원.

쿠폰의 동시성 이슈는 "한 사람이 같은 쿠폰으로 여러 디바이스에서 동시 결제"다. `IssuedCoupon`에 (coupon_id, member_id) 유니크 + 상태 컬럼 CAS 갱신이 표준이다.

### 4. 부분 취소 / 환불 흐름

1. CS가 주문 일부 항목 환불 요청.
2. `Claim` 생성, 환불 금액 계산(할인 안분이 핵심).
3. PG 부분 취소 호출.
4. 적립금 회수 / 쿠폰 복원 / 정산 마이너스 분개.
5. 알림.

할인 안분이 까다롭다. 1만원짜리에 2천원 쿠폰 + A(7000)/B(3000) 2개 항목인데 A만 환불할 때 얼마를 환불할지 명확히 정의해야 한다. 결제 시점에 `discountAllocated`를 항목별로 미리 계산해 저장해 두는 설계가 운영적으로 가장 안전하다.

### 5. 가격/메뉴 변경 전파

1. 본사 백오피스에서 가격 변경 저장 → `PriceChanged` 이벤트.
2. 디지털 채널 캐시 무효화.
3. 외부 배달앱 메뉴판 동기화 잡 트리거.
4. 매장 KDS 메뉴 표시 갱신.

이 흐름이 캐시 정합성 설계와 직접 연결된다.

### 6. 정산 흐름

1. 일배치가 전일자 `OrderPaid`/`Refunded` 이벤트 누적분을 스캔.
2. 매장/가맹주/PG/배달사 단위로 분개 생성.
3. 검증 후 회계 ERP 전송.
4. 지급/세금계산서 발행 트리거.

정산은 "돈"이라 멱등성과 재처리 가능성이 절대 깨지면 안 된다. 입력은 이벤트 스트림이지만 출력은 항상 같은 분개가 나오는 결정론적 함수여야 한다.

## 자주 터지는 정합성 / 장애 이슈

### A. 가격 스냅샷 미보존

마스터만 참조하다가 메뉴 가격이 바뀐 뒤 영수증/정산이 어긋난다. → 주문 시점에 `unitPriceSnapshot`, `discountAllocated`를 반드시 저장.

### B. 결제-주문 원자성 파괴

PG 승인은 났는데 주문 갱신 트랜잭션이 실패. → Outbox + 보상 트랜잭션 + 결제 콜백 idempotency key.

### C. 캐시-DB 정합성 깨짐

매장 메뉴 품절 처리가 일부 서버에만 반영. → DB 커밋 이후 이벤트 발행, Fanout으로 전 인스턴스 동시 무효화, 갱신 구간 lock.

### D. 외부 배달사 메뉴 매핑 드리프트

본사 리뉴얼 vs 배달앱 매핑이 시간차. → 메뉴 변경 시 외부 채널 동기화 잡을 반드시 트리거하고, 매핑 미존재 메뉴 주문은 ACL에서 즉시 거부.

### E. 쿠폰 중복 사용

동시 결제로 한 쿠폰이 2건에 적용. → `IssuedCoupon` 상태를 CAS로 RESERVED 전이, 실패 시 즉시 결제 차단.

### F. 부분 취소 안분 오차

라운딩으로 1원 차이가 누적. → 안분은 정수 원 단위 + 잔여는 가장 큰 항목에 가산하는 결정론 규칙 고정.

### G. 픽업 슬롯 오버부킹

`PickupSlot.capacity`를 단순 `count + 1`로 늘리면 동시성 시 초과. → DB 유니크/조건부 업데이트 또는 Redis 카운터 + 정합 검증 잡.

### H. 알림 폭주

OrderPaid에 동기 푸시 발송 코드를 박으면 외부 알림톡 장애가 결제 흐름을 막는다. → 알림은 항상 Outbox 비동기.

### I. 멀티 채널 회원 정합성

앱 회원과 매장 멤버십 회원이 다른 ID로 존재. → CI 기반 통합 키 + 머지 잡 + 적립금 통합 정책.

### J. 시간대 이슈

매장 영업시간/슬롯/쿠폰 유효기간이 매장 로컬 시간 기준인데 서버는 UTC. → 모든 시간 컬럼 타임존 명시, 매장 단위 영업일 정의(예: 02:00까지가 전일자).

## 인프라 패턴을 F&B 디지털 채널에 적용하기

다른 도메인에서 익힌 인프라 패턴은 어휘만 다를 뿐 F&B 디지털 채널에서도 뼈대 문제가 동일하다. "일반 패턴 → 같은 구조의 F&B 문제 → 풀이"로 매핑해 보면 설계 근거가 분명해진다.

### 적용 예시 1 — 캐시 정합성

정적 설정 데이터를 메모리에 캐싱하면 다중 서버 정합성이 깨진다. JPA `PostCommitUpdateEventListener`로 커밋 이후에만 RabbitMQ Fanout 발행, 각 인스턴스가 자기 큐에서 받아 해당 키만 갱신, 갱신 구간은 `StampedLock` writeLock으로 막고 조회는 `tryReadLock(2.5s)` 타임아웃으로 보호하는 패턴이 있다.

이 패턴은 F&B 디지털 채널의 매장 메뉴/가격 변경 전파에 그대로 적용된다. 본사에서 가격을 바꾸면 채널 백엔드 인스턴스마다 캐시가 살아 있는데, 트랜잭션 커밋 이전에 이벤트를 보내면 갱신 직후 조회가 옛 데이터를 다시 캐시해버린다. AFTER_COMMIT + Fanout + 인스턴스별 lock 패턴이면 매장이 'X메뉴 품절'을 토글했을 때 KDS와 앱 모두 일관된 상태로 수렴한다.

### 적용 예시 2 — Kafka Outbox

핵심 API의 동기 처리(금액·상태 갱신)와 비동기 후처리(통계·알림)를 분리하면서 메시지 유실을 막으려면 Transactional Outbox Pattern을 쓴다. `@TransactionalEventListener(AFTER_COMMIT)`으로 커밋 이후 발행, 발행 실패 시 `Propagation.REQUIRES_NEW`로 별도 트랜잭션에 실패 메시지를 저장하고 스케줄러가 재전송, traceId까지 같이 적재해 추적한다.

F&B 디지털 채널에서는 이게 OrderPaid 이벤트 처리에 정확히 대응한다. 결제 승인 직후 주방 KDS 푸시·알림톡·적립금 적립·정산 누적이 동시에 일어나는데, 이걸 동기로 묶으면 알림톡 장애가 결제 자체를 막아 매장 매출이 끊긴다. Outbox로 분리하면 알림톡이 막혀도 주문은 살고, 알림은 재전송으로 따라잡는다. 정산 누적도 같은 outbox 경로를 타기 때문에 일배치 정산이 결정론적으로 같은 분개를 만든다.

### 적용 예시 3 — 운영 제약 하 장애 대응

컨테이너 오케스트레이션에서 `terminationGracePeriodSeconds`가 고정된 제약 하에서는 gRPC 서버 graceful shutdown 중 503이 발생할 수 있다. preStop sleep으로 트래픽 차단 전파, gRPC graceful 종료, 여유 구간으로 예산을 쪼개 SIGTERM 핸들러와 프로세스 관리자 종료 대기 시간을 맞추는 패턴이 있다.

F&B 디지털 채널에서도 같은 클래스의 문제가 발생한다. 결제 승인 콜백이 막 들어오는 도중 배포가 시작되면 인스턴스가 내려가면서 콜백을 잃고 주문이 PENDING에 박힌다. 콜백 idempotency 키 + 짧은 grace + 미수신 콜백을 PG에 재조회하는 reconciliation 잡 조합으로 풀어야 운영이 안전하다. 외부에 의존하는 흐름은 'grace 안에 끝낸다'가 아니라 '재조회로 따라잡는다'로 설계해야 한다.

### 적용 예시 4 — 부분 취소 / 할인 안분

지급률·분개 계산 같은 결정론적 계산은 '입력이 같으면 출력이 항상 같다'를 강제해야 재처리가 안전하다. 그래서 라운딩 규칙을 한 곳에 못 박고 잔여 단위는 가장 큰 단위 항목에 가산하는 식으로 1원 오차를 흡수한다.

F&B 환불 안분도 같은 문제다. 1만원 주문에 2천원 쿠폰을 항목 A(7000)/B(3000)에 안분할 때 1400/600 또는 1399/601처럼 라운딩이 갈라지면 부분 환불 금액이 어긋나 정산이 깨진다. 결제 시점에 `discountAllocated`를 정수 원 단위로 미리 굳히고, 잔여 1원은 단가가 큰 항목에 가산하는 결정론 규칙으로 고정해 두면 부분 환불·재환불·재정산이 항상 같은 결과를 낸다.

## 로컬 학습 환경 만들기

도메인을 머리로만 이해하지 않으려면 작은 모형을 굴려보는 게 빠르다. MySQL 8 + Spring Boot로 다음 최소 스키마를 띄워 두고 시나리오를 흘려본다.

```sql
CREATE TABLE store (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  brand_code VARCHAR(20) NOT NULL,
  code VARCHAR(40) NOT NULL,
  name VARCHAR(100) NOT NULL,
  UNIQUE KEY uk_store (brand_code, code)
);

CREATE TABLE menu (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  brand_code VARCHAR(20) NOT NULL,
  name VARCHAR(100) NOT NULL,
  base_price INT NOT NULL
);

CREATE TABLE store_menu (
  store_id BIGINT NOT NULL,
  menu_id BIGINT NOT NULL,
  is_available TINYINT(1) NOT NULL DEFAULT 1,
  sold_out_until DATETIME NULL,
  PRIMARY KEY (store_id, menu_id)
);

CREATE TABLE orders (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no VARCHAR(32) NOT NULL UNIQUE,
  member_id BIGINT NULL,
  store_id BIGINT NOT NULL,
  channel VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL,
  total_amount INT NOT NULL,
  discount_amount INT NOT NULL,
  pay_amount INT NOT NULL,
  placed_at DATETIME NOT NULL,
  KEY idx_orders_store_placed (store_id, placed_at)
);

CREATE TABLE order_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_id BIGINT NOT NULL,
  menu_id BIGINT NOT NULL,
  qty INT NOT NULL,
  unit_price_snapshot INT NOT NULL,
  options_json JSON NULL,
  discount_allocated INT NOT NULL DEFAULT 0,
  KEY idx_order_item_order (order_id)
);

CREATE TABLE outbox_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  aggregate_type VARCHAR(40) NOT NULL,
  aggregate_id VARCHAR(40) NOT NULL,
  type VARCHAR(60) NOT NULL,
  payload JSON NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  created_at DATETIME NOT NULL,
  KEY idx_outbox_status (status, created_at)
);
```

이 위에서 다음을 직접 굴려본다.

- 주문 생성 시 `unit_price_snapshot`을 반드시 채우는 서비스 작성 → 메뉴 가격을 도중에 바꿔도 영수증이 변하지 않는지 확인.
- 결제 성공 처리에 `OrderPaid`를 outbox로 적재하는 트랜잭션 작성 → outbox publisher 별도 스레드에서 발행.
- 매장 메뉴 품절 토글 API → AFTER_COMMIT 이벤트로 캐시 무효화 호출.
- 부분 환불 시 `discount_allocated` 기준 환불 금액 계산 함수 단위 테스트 작성.

## Bad vs Improved 예제 — 가격 스냅샷

```java
// Bad — 마스터를 그대로 참조해 영수증을 그린다
public BigDecimal receiptTotal(Order order) {
  return order.getItems().stream()
    .map(it -> menuRepo.findById(it.getMenuId())
                       .orElseThrow().getBasePrice()
                       .multiply(BigDecimal.valueOf(it.getQty())))
    .reduce(BigDecimal.ZERO, BigDecimal::add);
}
```

가격이 바뀌면 어제 손님 영수증이 바뀐다. 정산이 즉시 깨진다.

```java
// Improved — 주문 시점 스냅샷만 사용
public long receiptTotal(Order order) {
  return order.getItems().stream()
    .mapToLong(it -> (long) it.getUnitPriceSnapshot() * it.getQty()
                     - it.getDiscountAllocated())
    .sum();
}
```

마스터는 신규 주문에만 영향을 주고, 기존 주문은 절대 변하지 않는다.

## Bad vs Improved 예제 — 동기 알림

```java
// Bad — 결제 승인 처리에서 알림톡을 동기로 발송
@Transactional
public void onPaymentApproved(Long orderId) {
  Order o = orderRepo.findById(orderId).orElseThrow();
  o.markPaid();
  alimtalkClient.sendOrderPaid(o);   // 외부 API. 장애 시 결제 처리가 막힘
  kdsClient.push(o);                 // 매장 KDS API. 장애 시 결제 처리가 막힘
}
```

```java
// Improved — outbox로 분리, 트랜잭션은 DB만 책임
@Transactional
public void onPaymentApproved(Long orderId) {
  Order o = orderRepo.findById(orderId).orElseThrow();
  o.markPaid();
  outboxRepo.save(OutboxEvent.of("ORDER", o.getId(), "OrderPaid", o.toEventPayload()));
}

// 별도 publisher가 outbox를 읽어 Kafka 토픽에 발행
// 알림 / KDS / 정산 누적 모두 같은 토픽을 구독
```

## 핵심 설계 질문과 정리

- 주문 상태 머신은 어떻게 설계하는가
  - 상태 enum + 허용 전이 표 + `OrderEvent` 이력 + 동시성은 낙관적 락(@Version) 또는 상태 컬럼 CAS.
- PG 결제 콜백이 두 번 오면 어떻게 처리하는가
  - 결제 승인번호 또는 PG 거래키를 idempotency key로 두고, payment 테이블 유니크 키 + 첫 처리 후 같은 key는 no-op.
- 본사에서 가격을 바꾸면 매장 KDS와 앱이 어떻게 동시에 갱신되는가
  - 가격 변경 트랜잭션 커밋 이후 PriceChanged 이벤트 발행 → 채널 캐시 무효화 + 외부 배달앱 동기화 잡 + 매장 KDS 토픽 푸시. 캐시 갱신 구간은 인스턴스별 lock.
- 부분 환불 시 할인 안분은 어떻게 하는가
  - 결제 시점에 항목별 `discountAllocated`를 결정론 규칙(원 단위, 잔여는 단가 큰 항목에 가산)으로 미리 굳혀 둔다.
- 외부 배달앱 주문 유입은 자사 주문과 어떻게 통합하는가
  - ACL에서 외부 메뉴/매장 ID를 내부 ID로 정규화, 결제 모드 컬럼으로 자사 PG/외부 정산 분기, 매핑 미존재는 즉시 거부 + 운영 알림.
- 정산은 실시간 주문 처리와 어떻게 분리되는가
  - 주문/결제 이벤트를 outbox에 누적 → 정산 컨텍스트가 별도 스토어에 적재 → 일배치가 결정론 함수로 분개. 실시간 경로와 정산 경로는 SLA가 다르고 장애도 격리된다.
- F&B 도메인의 캐시 핫키는 무엇이고 어떻게 보호하는가
  - 인기 매장의 메뉴 카탈로그가 핫키. TTL + jitter, 만료 직전 비동기 재계산(소프트 만료), 동시 갱신은 인스턴스별 lock 또는 분산 락 1개 인스턴스만 채우기.

## 학습 체크리스트

- [ ] 11개 bounded context를 보지 않고 한 줄씩 설명할 수 있다.
- [ ] 주문 상태 머신을 enum + 전이표로 그릴 수 있다.
- [ ] 가격 스냅샷이 왜 필요한지, 마스터 참조 설계가 어디서 깨지는지 사례로 말할 수 있다.
- [ ] PG 콜백 idempotency를 어디 키로 잡는지(승인번호 vs 우리 발급 key) 답할 수 있다.
- [ ] 외부 배달앱 주문이 자사 주문과 정산 단계에서 어떻게 다른지 설명할 수 있다.
- [ ] 매장 품절 토글이 다중 인스턴스에 어떻게 전파되는지 설명할 수 있다.
- [ ] OrderPaid 이벤트가 어떤 컨텍스트들에 의해 어떻게 소비되는지 토폴로지를 그릴 수 있다.
- [ ] 부분 환불 안분 라운딩 규칙을 결정론으로 정의해 코드로 옮길 수 있다.
- [ ] 픽업 슬롯 오버부킹 방지 전략 두 가지 이상(DB 조건부 업데이트, Redis 카운터)을 비교할 수 있다.
- [ ] 정산 배치가 멱등하려면 입력 이벤트가 어떻게 적재되어야 하는지 설명할 수 있다.
- [ ] 캐시 정합성 / Outbox / graceful shutdown 패턴을 F&B 도메인 어휘로 적용할 수 있다.
