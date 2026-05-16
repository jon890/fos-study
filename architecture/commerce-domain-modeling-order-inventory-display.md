# [초안] 커머스 도메인 모델링: 주문·재고·노출의 세 축을 분리해서 설계하기

## 왜 이 주제가 중요한가

커머스/F&B 백엔드에서 도메인 모델링 질문이 들어오면 대부분 답변이 **주문과 결제** 축에 쏠린다. 그러나 실제 운영에서 가장 자주 사고가 나는 곳은 그 옆에 붙은 두 축, **재고(Inventory)**와 **노출(Display/Catalog)**이다.

- "결제는 됐는데 매장에 재료가 없다고 거절당했다." → Inventory 축의 race condition.
- "장바구니에 담았는데 결제 직전 품절로 막혔다." → 재고 차감 시점 설계 실패.
- "행사 시작 시각이 됐는데 상품이 안 보인다." → Display 축의 노출 정책과 캐시 갱신 실패.
- "어드민에서 메뉴를 내렸는데 일부 매장에서 5분간 더 보였다." → Display 캐시 정합성.
- "재고는 0인데 상품이 검색에 떠 있다." → 재고와 노출의 데이터 출처 분리 실패.

[`commerce-order-state-consistency-fundamentals.md`](./commerce-order-state-consistency-fundamentals.md), [`ecommerce-order-payment-domain-modeling.md`](./ecommerce-order-payment-domain-modeling.md), [`fnb-order-store-pickup-state-machine.md`](./fnb-order-store-pickup-state-machine.md)이 주문·결제·상태머신을 다룬다면, 이 문서는 그 옆에 빠져 있던 **재고와 노출**을 채운다. 면접에서 "주문 시스템 어떻게 설계하시겠어요"에 결제·상태머신만 답하면 50점이고, 재고와 노출까지 자르면 70점, 셋 사이의 동기화·캐시 전략까지 말하면 90점이다.

## 핵심 통찰: 같은 "상품"이 컨텍스트마다 다른 모델이다

`Product`라는 단어 하나로 모든 컨텍스트가 같은 테이블을 바라보는 순간 설계는 무너진다. 같은 햄버거 상품이라도 다음 세 컨텍스트에서 의미가 다르다.

| 컨텍스트 | 같은 햄버거의 의미 | 변경 빈도 | 일관성 요구 |
|---|---|---|---|
| Catalog (마스터) | SKU, 영양정보, 알러지, 기본 가격 | 낮음(주 단위) | 강한 일관성 |
| Display (노출) | 매장 노출 여부, 시간대 메뉴, 정렬 순위, 품절 표시 | 중간(시간 단위) | 결과적 일관성 + 짧은 지연 허용 |
| Inventory (재고) | 매장별 잔여 수량, 예약/확정/취소 | 매우 높음(초 단위) | 강한 일관성 (트랜잭션) |
| Order (주문) | 주문 시점의 가격·옵션 스냅샷 | 한 번만 쓰임 | 불변(스냅샷) |

각 컨텍스트는 자체 Aggregate Root를 갖고, 컨텍스트 간 참조는 객체가 아니라 **ID와 도메인 이벤트**로만 한다. 이 원칙은 [`ddd-domain-modeling.md`](./ddd-domain-modeling.md)의 Bounded Context를 커머스 도메인에 그대로 적용한 결과다.

## Catalog: 변하지 않아야 할 진실의 원천

Catalog는 상품의 **불변에 가까운 본질**만 담는다.

```sql
CREATE TABLE catalog_item (
  item_id        BIGINT PRIMARY KEY,
  brand_id       BIGINT NOT NULL,
  sku            VARCHAR(64) NOT NULL UNIQUE,
  name_ko        VARCHAR(200) NOT NULL,
  default_price  INT NOT NULL,
  nutrition_json JSON,
  allergen_json  JSON,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     DATETIME(6) NOT NULL,
  updated_at     DATETIME(6) NOT NULL,
  KEY idx_brand_active (brand_id, is_active)
) ENGINE=InnoDB;
```

`default_price`는 기본값이고, 실제 매장·시간대 가격은 Display 쪽 정책으로 덮어쓴다. Catalog는 마스터 데이터에 가까워서 어드민 변경 빈도가 낮고, 변경되면 결과적으로 모든 매장이 따라간다.

면접 포인트: "기본 가격을 Catalog에 두느냐 Display에 두느냐"는 흔한 질문이다. 답은 **둘 다**다. Catalog의 `default_price`는 가격 정책이 비어 있을 때의 안전망이고, 실제 노출/주문 가격은 Display의 정책 테이블에서 결정한다. 정책이 통째로 비어 있어도 가격은 노출돼야 하기 때문이다.

## Display: 노출은 재고와 다르다

Display 컨텍스트는 "이 매장에서, 지금 시각에, 이 상품을 어떤 모습으로 보여줄 것인가"를 다룬다. 운영자가 가장 자주 만지는 영역이지만 모델링이 가장 자주 망가지는 영역이기도 하다.

핵심 분리 원칙: **"안 보임"의 이유가 무엇인지 코드가 답할 수 있어야 한다.**

다음 다섯 가지 "안 보임" 사유는 절대 같은 컬럼으로 표현하면 안 된다.

1. **운영자가 내렸다** (`is_visible=false`) — 의도된 비노출
2. **시간대 메뉴가 아니다** (`hour_window`에 포함 안 됨) — 자동 노출 제어
3. **품절이다** (`Inventory.qty_available <= 0`) — 재고 컨텍스트 사실
4. **노출 정책이 없다** — 매장별 정책 미설정
5. **Catalog가 비활성이다** (`catalog_item.is_active=false`) — 상품 전체 단종

이걸 한 컬럼(예: `display_status`)에 우겨넣으면 운영 알림이 "이거 왜 안 보여요?"로 가득 찬다. 사유가 분리돼야 어드민이 "운영자가 내림"으로 표시할지 "품절"로 표시할지를 결정할 수 있다.

### Display 모델 예시

```sql
CREATE TABLE display_policy (
  policy_id       BIGINT PRIMARY KEY AUTO_INCREMENT,
  store_id        BIGINT NOT NULL,
  item_id         BIGINT NOT NULL,
  is_visible      BOOLEAN NOT NULL DEFAULT TRUE,
  price_override  INT NULL,
  sort_priority   INT NOT NULL DEFAULT 0,
  start_at        DATETIME(6) NULL,
  end_at          DATETIME(6) NULL,
  hour_window     JSON NULL,         -- [[11,15],[17,21]] 등
  updated_at      DATETIME(6) NOT NULL,
  UNIQUE KEY uk_store_item (store_id, item_id),
  KEY idx_store_visible (store_id, is_visible)
) ENGINE=InnoDB;

CREATE TABLE display_visibility_log (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  store_id    BIGINT NOT NULL,
  item_id     BIGINT NOT NULL,
  from_state  VARCHAR(32) NOT NULL,
  to_state    VARCHAR(32) NOT NULL,
  reason_code VARCHAR(32) NOT NULL,  -- ADMIN_HIDE, HOUR_WINDOW, OUT_OF_STOCK, POLICY_MISSING, CATALOG_INACTIVE
  changed_at  DATETIME(6) NOT NULL,
  KEY idx_store_item (store_id, item_id, changed_at)
);
```

`reason_code`가 사유 분리의 핵심이다. 같은 "안 보임"이라도 사유가 운영 알림 단계에서 갈린다.

### Display 조회는 read-optimized

PLP(상품 목록) 응답은 매장당 수십~수백 상품을 한 번에 본다. Catalog + Display + Inventory를 JOIN해서 매번 계산하면 매장 트래픽이 몰릴 때 DB가 죽는다. 그래서 **읽기 전용 read model**을 별도로 둔다.

```java
public record DisplayItem(
    long itemId,
    String nameKo,
    int price,
    int sortPriority,
    boolean soldOut,
    String hiddenReason   // null이면 노출
) {}
```

이 read model을 채우는 방식은 세 가지가 있고 트래픽 크기와 정합성 요구에 따라 선택한다.

- **즉시 계산**: 매 요청마다 Catalog/Display/Inventory join. 정합성 최고, 성능 최악. 소규모 매장 운영.
- **매장 단위 캐시 + 무효화**: Redis에 `display:store:{storeId}` 전체 목록 캐시. 도메인 이벤트로 무효화. F&B/커머스 대부분이 여기.
- **CDC 기반 비동기 read model**: Catalog/Display/Inventory 변경을 CDC로 받아 별도 검색 인덱스(OpenSearch)에 투영. 검색·랭킹 요구가 강할 때.

후보자 경험과 연결하면, RabbitMQ Fanout으로 다중 서버 인메모리 캐시를 무효화한 사례가 이 패턴의 변형이다. "정적 설정 데이터 갱신 시 전 서버 동시 무효화 + StampedLock으로 갱신 구간 보호"를 매장 메뉴 캐시로 옮기면 동일한 구조가 된다.

## Inventory: 트랜잭션이 가장 짧아야 하는 곳

재고는 모든 컨텍스트 중 **가장 짧은 트랜잭션**을 요구한다. 재고 차감이 5초 걸리면 동시 결제가 줄을 서고, 결제 PG에 영향이 간다.

### 매장 단위 재고가 자연 키다

F&B/매장 픽업 도메인에서 재고는 거의 항상 **매장별**이다. 중앙 창고 모델(전자상거래)과 다르다.

```sql
CREATE TABLE inventory (
  store_id      BIGINT NOT NULL,
  item_id       BIGINT NOT NULL,
  qty_on_hand   INT NOT NULL,        -- 매장 실재 수량
  qty_reserved  INT NOT NULL DEFAULT 0,  -- 결제 진행 중 예약분
  version       INT NOT NULL DEFAULT 0,
  updated_at    DATETIME(6) NOT NULL,
  PRIMARY KEY (store_id, item_id)
) ENGINE=InnoDB;
```

`qty_available = qty_on_hand - qty_reserved`가 사용자에게 노출되는 잔여수량이다.

### Reserve-then-Confirm 패턴

결제 직전에 재고를 잠시 예약하고, 결제 승인 후 확정한다. 결제 실패/취소 시 예약을 푼다.

1. 주문 생성 시: `qty_reserved += qty`, 단 `qty_on_hand - qty_reserved >= qty` 조건이 동시에 성립해야 함
2. 결제 승인 시: `qty_on_hand -= qty`, `qty_reserved -= qty`
3. 결제 실패/취소 시: `qty_reserved -= qty`
4. 예약 후 일정 시간(예: 5분) 경과 시 자동 해제(janitor)

핵심은 1번 단계의 **조건부 UPDATE**다. SELECT 후 UPDATE를 분리하면 동시 차감이 음수 재고를 만든다.

```sql
-- 예약: 재고 충분할 때만 성공
UPDATE inventory
   SET qty_reserved = qty_reserved + :qty,
       version      = version + 1,
       updated_at   = NOW(6)
 WHERE store_id    = :storeId
   AND item_id     = :itemId
   AND qty_on_hand - qty_reserved >= :qty;
```

`affected rows = 1`이면 예약 성공, 0이면 실패. 락 없이도 InnoDB row-level lock + WHERE 조건 평가가 동시성을 막아준다. 분산 락(Redisson 등)을 매번 끼우면 결제 PG 호출 시간까지 락이 끼어 운영 사고가 난다.

### 확정 단계

```sql
UPDATE inventory
   SET qty_on_hand  = qty_on_hand - :qty,
       qty_reserved = qty_reserved - :qty,
       version      = version + 1,
       updated_at   = NOW(6)
 WHERE store_id    = :storeId
   AND item_id     = :itemId
   AND qty_reserved >= :qty;
```

`qty_reserved >= :qty` 조건이 멱등성을 보장한다. 같은 결제 승인 이벤트가 중복 도착해도 두 번째는 affected rows 0으로 끝난다(`inbox` 테이블과 함께 쓰면 더 안전).

### 예약 만료 janitor

```sql
UPDATE inventory i
JOIN order_reservation r ON r.store_id = i.store_id AND r.item_id = i.item_id
   SET i.qty_reserved = i.qty_reserved - r.qty
 WHERE r.status      = 'RESERVED'
   AND r.reserved_at < NOW(6) - INTERVAL 5 MINUTE;
```

예약 테이블을 따로 두고(`order_reservation`) 어떤 주문이 어느 매장의 어느 상품을 얼마나 예약했는지 추적해야 자동 해제가 가능하다. 이 테이블 없이 `qty_reserved`만 운영하면 "누가 점유 중인지" 알 수 없어 운영 장애가 난다.

## 세 축이 만나는 결정점: 주문 생성

주문 생성 트랜잭션은 세 컨텍스트와 어떻게 상호작용해야 하는가. 다음 흐름이 기본이다.

```java
@Transactional
public OrderResult placeOrder(PlaceOrderCommand cmd) {
    // 1. Display에서 노출 가능 여부 + 가격 스냅샷
    DisplayItem item = displayQuery.snapshot(cmd.storeId(), cmd.itemId(), cmd.requestedAt());
    if (item.hiddenReason() != null) {
        throw new ItemNotAvailableException(item.hiddenReason());
    }

    // 2. Inventory 예약 (조건부 UPDATE)
    int reserved = inventoryRepo.tryReserve(
        cmd.storeId(), cmd.itemId(), cmd.qty()
    );
    if (reserved == 0) {
        throw new OutOfStockException(cmd.storeId(), cmd.itemId());
    }

    // 3. Order Aggregate 생성. Display 스냅샷을 그대로 동결.
    Order order = Order.place(
        cmd, OrderPriceSnapshot.from(item)
    );
    orderRepo.save(order);

    // 4. 같은 트랜잭션에 outbox 적재
    outboxPublisher.append(new OrderPlacedEvent(order.id()));

    // 5. order_reservation에 예약 추적 row 적재
    reservationRepo.save(OrderReservation.of(order.id(), cmd, NOW));

    return OrderResult.of(order);
}
```

이 흐름이 명시적으로 분리하는 것:

- Display 조회는 **읽기**(query model)이고 변경하지 않는다.
- Inventory는 **조건부 UPDATE 한 줄**로 예약. 락이나 분산 락이 끼지 않는다.
- Order는 **스냅샷을 동결**한다. 이후 Display 가격이 바뀌어도 주문 금액은 변하지 않는다.
- 이벤트는 **outbox**로 같이 커밋된다. 트랜잭션 밖에서 Kafka 호출하지 않는다.

## 결제 승인 ↔ 재고 확정 ↔ 노출 갱신

결제 승인 이후의 흐름은 비동기로 풀린다.

1. PG 승인 응답 → Order.markPaid + outbox에 `OrderPaymentApprovedEvent`
2. Inventory consumer가 받아 `confirm()` 호출 (조건부 UPDATE로 멱등)
3. Display read model이 받아 `qty_available` 캐시 갱신
4. 매장 알림 consumer가 받아 POS에 전달
5. 매장 거절 시 Saga로 보상: `Inventory.cancelConfirm()` → `Payment.cancel()` → `Order.markCanceledByStore()`

핵심은 **각 consumer가 자기 컨텍스트의 사실만 책임진다**는 것. Inventory consumer는 Display 캐시를 직접 무효화하지 않고, Display consumer가 별도로 `OrderPaymentApprovedEvent`를 구독해 자기 캐시를 갱신한다. 의존 방향을 컨텍스트별로 분리해야 한 컨텍스트의 장애가 다른 컨텍스트를 막지 않는다.

## Bad vs Improved

### 나쁜 패턴: 한 트랜잭션에 다 우겨넣기

```java
@Transactional
public OrderResult placeOrder(PlaceOrderCommand cmd) {
    Product p = productRepo.findById(cmd.itemId()).orElseThrow();
    if (!p.isVisibleAt(cmd.storeId())) throw new NotVisibleException();
    int stock = stockRepo.findStock(cmd.storeId(), cmd.itemId());
    if (stock < cmd.qty()) throw new OutOfStockException();
    stockRepo.decrease(cmd.storeId(), cmd.itemId(), cmd.qty()); // SELECT 후 UPDATE
    Order order = Order.create(cmd, p.getPrice());              // 가격 직접 참조
    orderRepo.save(order);
    kafkaTemplate.send("order.placed", order);                  // 트랜잭션 밖 발행
    posClient.notify(cmd.storeId(), order);                     // 외부 호출이 트랜잭션 안
    return OrderResult.of(order);
}
```

문제 6가지:

1. Display/Inventory/Catalog가 한 객체(`Product`)에 섞임 — Aggregate 경계 붕괴
2. 재고 SELECT 후 UPDATE — 동시성 깨짐 → 음수 재고
3. 가격을 Catalog에서 직접 참조 — 정책 변경 시 과거 주문 금액 흔들림
4. 가격 스냅샷 미보관
5. Kafka 발행이 트랜잭션 밖 — 커밋 후 실패 시 메시지 유실
6. 외부 POS 호출이 트랜잭션 안 — 락 시간 폭증, 외부 장애가 DB로 전파

### 개선 패턴

```java
@Transactional
public OrderResult placeOrder(PlaceOrderCommand cmd) {
    DisplayItem snapshot = displayQuery.snapshot(cmd.storeId(), cmd.itemId(), NOW);
    if (snapshot.hiddenReason() != null) throw new ItemNotAvailableException(snapshot.hiddenReason());

    int reserved = inventoryRepo.tryReserve(cmd.storeId(), cmd.itemId(), cmd.qty());
    if (reserved == 0) throw new OutOfStockException();

    Order order = Order.place(cmd, snapshot);
    orderRepo.save(order);
    reservationRepo.save(OrderReservation.of(order.id(), cmd, NOW));
    outboxPublisher.append(new OrderPlacedEvent(order.id()));
    return OrderResult.of(order);
}
```

차이: 세 컨텍스트가 분리되고, 재고는 조건부 UPDATE, 가격은 스냅샷, 외부 호출은 outbox, 예약 추적까지 보장.

## 로컬 실습 환경

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: commerce
    ports: ["3306:3306"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

세 컨텍스트 스키마(요약):

```sql
CREATE TABLE inventory (
  store_id BIGINT, item_id BIGINT,
  qty_on_hand INT NOT NULL, qty_reserved INT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (store_id, item_id)
);

CREATE TABLE display_policy (
  store_id BIGINT, item_id BIGINT,
  is_visible BOOLEAN NOT NULL DEFAULT TRUE,
  price_override INT NULL, hour_window JSON NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (store_id, item_id)
);

CREATE TABLE order_reservation (
  order_id BIGINT, store_id BIGINT, item_id BIGINT,
  qty INT NOT NULL, status VARCHAR(16) NOT NULL,
  reserved_at DATETIME(6) NOT NULL, confirmed_at DATETIME(6) NULL,
  PRIMARY KEY (order_id, item_id)
);
```

## 실습 시나리오

1. **음수 재고 재현**: `qty_on_hand=1`로 두고 두 세션에서 동시에 `UPDATE inventory SET qty_on_hand = qty_on_hand - 1 WHERE store_id=? AND item_id=?`만 실행. 둘 다 성공해서 `qty_on_hand=-1`이 되는 것을 확인. 그 다음 `AND qty_on_hand >= 1`을 추가한 조건부 UPDATE로 한 쪽만 성공함을 확인.
2. **예약 만료 janitor**: 예약을 만들고 5분이 지나면 자동 해제되는 잡을 cron으로 돌려보고, 그 사이에 결제 승인이 도착하면 어떻게 처리할지 시나리오를 그린다(이미 해제된 예약을 다시 살릴지, 새 예약을 시도할지).
3. **노출 사유 분리**: `display_policy.is_visible=false`로 두고 PLP 응답이 "운영자가 내림"으로 표시되는지, `qty_on_hand=0`인 경우 "품절"로 표시되는지 별 사유 코드를 검증.
4. **시간대 메뉴 전환**: `hour_window=[[11,15]]`로 설정하고 11시 정각에 노출이 켜지는지, 15시 정각에 꺼지는지 검증. 캐시 무효화가 정시 ±1초 안에 일어나는지 확인.
5. **결제 승인 후 재고 확정 멱등성**: 같은 `OrderPaymentApprovedEvent`를 컨슈머에 두 번 흘려서 재고가 한 번만 차감되는지 확인.

## 면접 답변 프레이밍

### "주문 시스템에서 재고는 어떻게 다루시겠어요?"

> F&B나 매장 픽업 도메인에서는 재고가 매장 단위라 자연 키가 (매장ID, 상품ID)가 됩니다. 재고 차감은 결제 직전에 일시 예약하고 결제 승인 후 확정하는 Reserve-then-Confirm 패턴을 기본으로 둡니다. 핵심은 예약 단계의 조건부 UPDATE 한 줄로 `qty_on_hand - qty_reserved >= 요청수량`을 평가하는 거고, 이게 InnoDB row lock과 결합해 분산 락 없이도 음수 재고를 막아줍니다. 분산 락을 결제 PG 호출 시간까지 끼면 락 점유가 길어져 운영 장애가 나기 쉽습니다. 예약은 일정 시간 후 janitor가 자동 해제하고, 어느 주문이 점유 중인지는 별도 `order_reservation` 테이블로 추적합니다.

### "노출 정책과 재고를 한 테이블에 넣으면 안 되나요?"

> '왜 안 보이는가'를 코드가 다섯 가지 사유로 답할 수 있어야 운영 알림이 분리됩니다. 운영자가 내린 것, 시간대 메뉴가 아닌 것, 품절인 것, 정책 미설정인 것, 단종된 것은 운영자가 봐야 할 대시보드가 다릅니다. 한 컬럼으로 합치면 어드민이 사유별 액션을 못 합니다. 그래서 Display는 노출 정책만 책임지고, 품절 여부는 Inventory가 진실의 원천을 갖고, PLP 응답을 만드는 read model이 둘을 합쳐 `soldOut`/`hiddenReason`을 채워줍니다.

### "Display 캐시 정합성은 어떻게 잡으시겠어요?"

> 운영자 변경, 시간대 전환, 재고 변경 세 가지가 트리거입니다. 도메인 이벤트를 outbox로 발행하고, Display consumer가 매장 단위로 캐시를 무효화합니다. 캐시 키는 매장 ID 단위가 자연스럽고, 상품 단건이 아니라 매장 전체 목록을 통째로 다시 만드는 편이 PLP 응답 시간 면에서 안정적입니다. 시간대 전환은 cron 기반 정시 발행 + TTL 안전망을 같이 둡니다. 이전 업무에서 정적 설정 데이터를 다중 서버 인메모리 캐시로 운영할 때 RabbitMQ Fanout으로 전 서버 무효화하고 StampedLock writeLock으로 갱신 구간을 보호한 경험이 있어서, 매장 메뉴 캐시도 같은 구조로 풀 수 있습니다.

### "장바구니에 담아둔 동안 가격이 바뀌면 어떻게 처리하나요?"

> 장바구니는 Display 가격을 그때그때 다시 조회해서 보여줍니다. 사용자가 결제 버튼을 누르는 순간 Display 스냅샷을 Order Aggregate에 동결하고, 그 이후의 정책 변경은 이미 생성된 주문에 영향이 없습니다. 만약 장바구니 진입 시 가격과 결제 시점 가격이 다르면 사용자에게 변경 사실을 한 번 확인받는 UX가 안전합니다. 핵심은 'Order는 과거의 사실을 불변으로 보존한다'는 원칙입니다.

### "재고가 0이면 PLP에 안 보이게 하시나요, 품절 표시하시나요?"

> 운영 정책에 따라 다르지만, 기본은 **품절 표시 + 노출 유지**가 더 좋습니다. 안 보이면 사용자가 "내가 잘못 봤나" 혼동하고, 매장에서는 "그 메뉴 있는 줄 알고 왔는데" 컴플레인이 옵니다. Display read model에 `soldOut=true` 플래그로 노출하고, 정렬 우선순위만 뒤로 미루는 게 일반적입니다. 단, 시즌 메뉴처럼 "끝났음"을 명확히 알려야 하는 경우는 운영자가 명시적으로 내리도록 합니다.

## 후보자 경험을 세 축으로 번역하기

### StampedLock 기반 정적 데이터 캐시 경험

> 정적 설정 데이터를 다중 서버 인메모리 캐시로 운영할 때 갱신 빈도는 낮고 조회가 압도적이라 `StampedLock` + optimistic read로 reader가 락 없이 흐르게 만들고, writer 진입 시점에만 `tryWriteLock` 타임아웃을 박았습니다. 커머스로 옮기면 매장 메뉴 노출 캐시가 정확히 같은 패턴입니다 — 운영자 변경 빈도는 낮고 PLP 조회는 매장 트래픽 그대로 받는 영역.

### RabbitMQ Fanout 캐시 정합성 경험

> 어드민 변경 시 다중 서버 정합성이 깨져 일시적 NPE가 났던 사고를 Hibernate `PostCommitUpdateEventListener` → RabbitMQ Fanout으로 전 서버 동시 무효화하면서 해소했습니다. Display 컨텍스트의 매장별 메뉴 노출 정책 변경도 같은 구조로 무효화합니다 — 변경은 한 곳에서, 무효화 신호는 fanout으로.

### Kafka Transactional Outbox 경험

> 주문 생성 트랜잭션 안에서 `outbox_message`에 `OrderPlacedEvent`를 같이 INSERT하고, 별도 publisher가 polling/CDC로 Kafka에 발행하는 구조를 운영했습니다. 커머스에서는 Order/Inventory/Display/Payment 네 컨텍스트가 각자 자기 consumer로 자기 사실만 책임지는 구조가 자연스럽게 따라옵니다. 매장 거절 같은 보상 흐름도 Saga로 풀립니다.

## 운영 모니터링 체크리스트

- 재고 예약 만료 누적 건수(janitor 처리 lag) — 1분 이상 적체 시 알람
- `qty_reserved` 누수(예약 추적 테이블 vs 합계 불일치) — 일 단위 reconciliation
- Display 캐시 무효화 lag — outbox publisher와 consumer 사이 지연
- 품절 자동 표시 정확도 — Inventory 사실과 Display 응답 일치율
- `display_visibility_log` 사유별 분포 — 운영자 내림 vs 품절 vs 시간대 비율
- 음수 재고 발생 카운트 — 0이어야 함, 1건이라도 발생 시 즉시 알림

## 학습 체크리스트

- [ ] Catalog/Display/Inventory/Order 네 컨텍스트의 책임과 변경 빈도를 표로 그릴 수 있다
- [ ] "안 보임" 사유 다섯 가지를 사유 코드로 분리해 설계할 수 있다
- [ ] 재고 예약을 조건부 UPDATE 한 줄로 동시성 안전하게 만들 수 있다
- [ ] Reserve-then-Confirm 패턴의 만료 janitor와 멱등 확정을 설명할 수 있다
- [ ] Display 가격 스냅샷을 Order Aggregate에 동결하는 이유를 답변할 수 있다
- [ ] PLP 응답을 위한 read model 패턴 세 가지(즉시 계산/매장 캐시/CDC 인덱스)를 트레이드오프와 함께 비교할 수 있다
- [ ] 결제 승인 후 Inventory 확정과 Display 캐시 갱신이 분리된 consumer 책임임을 설명할 수 있다
- [ ] 매장 거절 시 Inventory → Payment → Order 순의 Saga 보상을 멱등하게 설계할 수 있다
- [ ] StampedLock·RabbitMQ Fanout·Kafka Outbox 경험을 세 컨텍스트 언어로 30초 내 번역할 수 있다
- [ ] 면접에서 "재고 동시성 어떻게 막나"에 분산 락 없이 조건부 UPDATE로 답할 수 있다

## 관련 문서

- [`commerce-order-state-consistency-fundamentals.md`](./commerce-order-state-consistency-fundamentals.md) — 주문 상태머신과 정합성 기본기 허브
- [`ecommerce-order-payment-domain-modeling.md`](./ecommerce-order-payment-domain-modeling.md) — Order/Payment/Coupon/Promotion 도메인 경계
- [`fnb-order-store-pickup-state-machine.md`](./fnb-order-store-pickup-state-machine.md) — F&B 픽업·배달 상태머신 운영
- [`coupon-promotion-concurrency-basics.md`](./coupon-promotion-concurrency-basics.md) — 쿠폰/프로모션 동시성
- [`ddd-domain-modeling.md`](./ddd-domain-modeling.md) — Bounded Context와 Aggregate 일반 원칙
- [`distributed-transaction-outbox-pattern.md`](./distributed-transaction-outbox-pattern.md) — Outbox 패턴 심화
- [`outbox-inbox-pattern.md`](./outbox-inbox-pattern.md) — Inbox 측 멱등성 보장
