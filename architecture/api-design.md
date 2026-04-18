# [초안] 시니어 백엔드를 위한 API 설계 실전 스터디 팩 — REST · 멱등성 · 페이지네이션 · 버전 전략

## 1. 왜 지금 이 주제를 다시 파야 하는가

API 설계는 "잘 돌아가는 코드"와 "시스템이 되는 코드"를 가르는 경계선이다. 시니어 백엔드는 엔드포인트를 만드는 사람이 아니라, 5년 뒤에도 deprecate 비용이 작게 드는 계약(contract)을 남기는 사람이다. 특히 커머스 백엔드처럼 주문, 결제, 쿠폰, 알림이 한 트랜잭션 스토리에 묶이는 도메인은 API 한 줄의 의미를 잘못 정하면, 몇 달 뒤 중복 결제 이슈, 외부 파트너 연동 롤백, 앱 강제 업데이트 같은 운영 사고로 돌아온다.

면접에서 "이 API를 설계해 주세요"라는 문제가 나오는 이유도 같다. 면접관은 엔드포인트 리스트를 듣고 싶은 게 아니라, 자원 모델링 → 메서드 의미 → 에러/멱등/페이지네이션 → 버전/배포/문서화로 이어지는 **일관된 설계 판단**을 듣고 싶어 한다. 이 문서는 그 판단 흐름을 재현할 수 있도록 실제 커머스 백엔드 관점에서 정리한다.

## 2. REST의 진짜 의미: 자원 중심 + 메서드 의미 + 상태 코드

### 2.1 자원 중심 URI

REST에서 URI는 **동사를 담지 않는다**. `POST /createOrder`는 REST가 아니라 "HTTP로 감싼 RPC"다. 자원(resource)은 명사, 동작은 메서드로 표현한다.

나쁜 예:
```
POST /api/createOrder
POST /api/cancelOrder?orderId=123
GET  /api/getOrderList?userId=7
```

개선:
```
POST   /v1/orders
POST   /v1/orders/{orderId}/cancellations
GET    /v1/users/{userId}/orders
```

포인트:
- `cancelOrder`가 아니라 "주문 취소"라는 **하위 자원**(`cancellations`)으로 모델링했다. 취소는 상태 전이 그 자체가 기록 대상이기 때문이다.
- 컬렉션(`/orders`)과 아이템(`/orders/{id}`)을 명확히 구분한다.
- 쿼리 파라미터는 필터/페이지네이션/정렬에만 쓴다. 식별자는 패스에 넣는다.

### 2.2 메서드 의미: 안전성(Safe)과 멱등성(Idempotent)

| 메서드 | Safe | Idempotent | 쓰는 곳 |
| --- | --- | --- | --- |
| GET | O | O | 조회 |
| HEAD | O | O | 존재/메타 확인 |
| PUT | X | O | 전체 교체, 식별자 클라이언트가 알 때 |
| DELETE | X | O | 삭제 |
| PATCH | X | 조건부 | 부분 수정 |
| POST | X | X (기본) | 생성, 트리거, 비정형 동작 |

여기서 자주 헷갈리는 두 지점:

- **Safe ≠ Idempotent.** Safe는 "서버 상태를 바꾸지 않는다", Idempotent는 "같은 요청을 N번 보내도 N=1과 결과가 같다"이다. DELETE는 Safe하지 않지만 Idempotent다.
- **PATCH는 기본적으로 멱등이 아니다.** `{"stock": {"op": "increment", "value": 1}}` 같은 델타 PATCH는 호출 횟수에 따라 결과가 달라진다. 멱등 PATCH를 원하면 JSON Merge Patch처럼 "결과 상태"를 보내야 한다.

### 2.3 상태 코드 설계

시니어 코드 리뷰에서 지적이 가장 많은 부분이 상태 코드다. 최소 다음 셋은 몸에 붙여 둬야 한다.

- 2xx: 성공
  - 200 OK — 일반 성공
  - 201 Created — 생성 성공, `Location` 헤더 필수
  - 202 Accepted — 비동기 접수(결제 승인 요청 등). 상태 조회 URL 동반
  - 204 No Content — 성공하지만 본문이 없음(DELETE)
- 4xx: 클라이언트 잘못
  - 400 Bad Request — 스키마/파라미터 자체가 깨짐
  - 401 Unauthorized — 인증 안 됨(토큰 없음/만료)
  - 403 Forbidden — 인증은 됐는데 권한 없음
  - 404 Not Found — 자원 없음
  - 409 Conflict — 상태 충돌(이미 취소된 주문 재취소)
  - 422 Unprocessable Entity — 스키마는 맞지만 비즈니스 규칙 위반(재고 부족)
  - 429 Too Many Requests — rate limit. `Retry-After` 헤더 동반
- 5xx: 서버 잘못
  - 500 — 처리되지 않은 예외
  - 502/503/504 — 업스트림/가용성/타임아웃

"재고 부족"을 400으로 주는 서비스가 아직도 많다. 400은 **요청이 말이 안 되는 경우**에 쓰고, 비즈니스 룰 위반은 422가 더 정확하다. 클라이언트 재시도 전략이 달라지기 때문이다.

## 3. Idempotency Keys: POST를 어떻게 안전하게 만들 것인가

POST는 본래 멱등하지 않다. 그런데 결제, 주문, 쿠폰 발급처럼 "두 번 실행되면 돈이 날아가는" 동작은 반드시 멱등이어야 한다. 네트워크 재시도, 타임아웃 재요청, 모바일 앱의 중복 탭은 현실에서 끊임없이 발생한다.

### 3.1 Stripe 패턴: `Idempotency-Key` 헤더

클라이언트가 요청마다 UUID를 만들어 헤더에 실어 보낸다.

```
POST /v1/payments
Idempotency-Key: 2f3d6b1e-0c2a-4a34-9f6f-7c4d9e01c5ad
Content-Type: application/json

{"orderId":"O-10293","amount":28900,"currency":"KRW","method":"card_token_xxx"}
```

서버는 `(route, key)` 조합으로 첫 요청의 **응답 전체**(HTTP status, headers, body, 그리고 부작용 커밋 여부)를 저장하고, 같은 키로 들어온 재요청에는 **저장된 응답을 그대로 재생**한다. 첫 요청이 아직 처리 중이면 `409` 또는 동일 키에 락을 걸고 대기한다.

테이블 예시(MySQL 8 기준):

```sql
CREATE TABLE idempotency_record (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    idem_key        VARCHAR(80)  NOT NULL,
    route           VARCHAR(120) NOT NULL,
    request_hash    CHAR(64)     NOT NULL,
    response_status SMALLINT     NULL,
    response_body   JSON         NULL,
    state           ENUM('IN_PROGRESS','DONE') NOT NULL,
    created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    completed_at    DATETIME(3)  NULL,
    UNIQUE KEY uq_idem (route, idem_key)
) ENGINE=InnoDB;
```

중요한 디테일 세 가지:
- `request_hash`를 같이 저장해 "같은 키인데 다른 body"가 오면 `422`로 거절한다. 그렇지 않으면 클라이언트 버그를 서버가 덮어 쓰게 된다.
- 부작용(결제 승인 호출 등)과 응답 저장은 **같은 트랜잭션/Outbox**로 묶는다. 외부 PG 호출은 멱등 보장이 없으므로 PG의 `merchantUid`를 키와 1:1로 연결해 두 번 승인되지 않게 한다.
- TTL(24~72시간)이 필요하다. 키를 영원히 잡아두면 스토리지만 늘어난다.

### 3.2 Outbox로 "부분 성공"을 없애라

내부 이벤트 발행(쿠폰 사용 → 알림 발송)을 멱등으로 만들려면, DB 트랜잭션과 메시지 발행을 한 커밋으로 묶어야 한다. Outbox 테이블에 이벤트 레코드를 같이 쓰고, 별도 디스패처가 읽어 발행하면 "DB는 커밋됐는데 메시지는 안 나감" 또는 그 반대가 사라진다. 멱등 키는 이 이벤트의 `event_id`로 끝까지 따라간다.

## 4. Pagination: 왜 대규모 데이터에선 keyset이 정답인가

### 4.1 세 가지 방식

- **Offset pagination**: `?page=10&size=20` → `LIMIT 20 OFFSET 200`
  - 장점: 직관적, 임의 페이지 점프 가능.
  - 단점: OFFSET이 커질수록 DB가 앞 데이터를 전부 세어 버린다. 100만 행 이후 페이지는 수 초씩 걸린다. 또한 새 데이터 삽입 시 중복/누락이 생긴다.
- **Cursor pagination**: 서버가 불투명한 `next_cursor` 토큰을 준다.
  - 장점: 클라이언트는 구현 세부를 모름. 정렬 기준을 바꿔도 API 모양이 유지됨.
  - 단점: 뒤로 가기/점프가 제한적.
- **Keyset(Seek) pagination**: 마지막으로 본 키를 조건으로 넘긴다.
  - 예: `WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC LIMIT 20`
  - 장점: 인덱스만 잘 타면 페이지 수와 무관하게 O(log N + page size). 삽입이 일어나도 중복/누락 없음.
  - 단점: 임의 페이지 점프 불가, 정렬 키가 유니크 조합이어야 안전.

실무에서 cursor와 keyset은 거의 같은 말이다. 공개 API는 cursor로 감싸고, 내부 구현은 keyset으로 한다.

### 4.2 실전 예 (MySQL 8)

나쁜 쿼리:
```sql
SELECT id, order_no, total_price
FROM orders
WHERE user_id = 42
ORDER BY created_at DESC
LIMIT 20 OFFSET 100000;
```

개선 (keyset):
```sql
SELECT id, order_no, total_price, created_at
FROM orders
WHERE user_id = 42
  AND (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

필요한 인덱스: `INDEX idx_orders_user_created (user_id, created_at DESC, id DESC)`.

응답 스키마:
```json
{
  "items": [ ... ],
  "page_info": {
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wNC0xOFQwNDozMDoxMloiLCJpZCI6MTIzNDV9",
    "has_next": true
  }
}
```

커서는 Base64(JSON)로 감싸 **포맷을 언제든 바꿀 수 있게** 해 둔다. 다만 커서 내부에 민감 정보를 담지 않는다(HMAC 서명을 붙이는 것도 방법).

## 5. Versioning 전략과 Deprecation

### 5.1 URI vs Header vs Content Negotiation

- **URI 버전**: `/v1/orders`, `/v2/orders`. 캐싱/라우팅이 단순하고, CDN 로그만 봐도 트래픽 분포가 보인다. 실무 기본값.
- **Custom Header**: `X-API-Version: 2026-01-15`. Stripe 방식. 날짜 기반 버전을 계정 단위로 고정해 점진 이관.
- **Accept Header (content negotiation)**: `Accept: application/vnd.company.order.v2+json`. 순수주의엔 맞지만 클라이언트 구현 비용이 높고 CDN에 불친절하다.

선택 기준:
- 외부 공개 + 다수 파트너: URI + 장기 지원(최소 12개월 deprecation).
- 내부 마이크로서비스: 날짜/헤더 기반이 유연. 서비스 메시/게이트웨이에서 라우팅 가능.
- 모바일 앱처럼 강제 업데이트가 어려운 클라이언트: URI가 안전.

### 5.2 Deprecation 플랜

버전을 올리는 것보다 **내리는 것**이 진짜 설계다.

1. `Deprecation: true` 및 `Sunset: Wed, 01 Oct 2026 00:00:00 GMT` 응답 헤더 부착.
2. 문서에 제거 일정, 마이그레이션 가이드, 대체 엔드포인트 명시.
3. 대시보드로 구버전 호출자 TOP N 추적 → 직접 연락.
4. Sunset 전에 **Brownout**(특정 시각에 일시적으로 503 반환)으로 파트너에게 실감.
5. Sunset 이후 410 Gone.

## 6. Error Contract: 에러는 문서다

에러 응답이 자유 형식이면 클라이언트마다 파싱 로직이 다르고, 결국 "status 200에 error 필드" 같은 반(反) 패턴이 생긴다. 표준화가 필요하다. RFC 7807(Problem Details)이 출발점이지만 커머스에는 살짝 확장해 쓴다.

```json
{
  "type": "https://errors.example.com/orders/stock-insufficient",
  "title": "Stock insufficient",
  "status": 422,
  "code": "ORDER_STOCK_INSUFFICIENT",
  "detail": "Requested 3 but only 1 available.",
  "instance": "/v1/orders",
  "trace_id": "b7c9...e3",
  "errors": [
    {"field": "items[0].quantity", "code": "QUANTITY_EXCEEDS_STOCK", "max": 1}
  ]
}
```

원칙:
- **HTTP status**는 전송/의미 계층. **`code`**는 도메인 계층. 둘을 분리한다. 같은 422라도 `ORDER_STOCK_INSUFFICIENT`와 `COUPON_EXPIRED`는 다르다.
- `trace_id`는 분산 트레이스 ID와 동일하게 두어 고객 문의 1회로 원인을 찾을 수 있게 한다.
- 메시지는 사람용(`title`, `detail`)과 기계용(`code`)을 섞지 않는다.
- 보안 관련 에러(401/403)는 원인을 과하게 노출하지 않는다. "비밀번호가 틀렸습니다"와 "아이디가 없습니다"를 구분하면 계정 열거 공격에 취약해진다.

## 7. 스키마 진화: Backward / Forward Compatibility

한 번 공개한 API는 "살아 있는 DB 스키마"로 취급해야 한다.

Backward compatible 변경(허용):
- optional 필드 추가
- enum 값 추가(단, 클라이언트가 모르는 값을 무시하도록 계약해야 함)
- 응답에 새 필드 추가

Breaking 변경(버전 업 필요):
- 필드 제거
- 필드 타입 변경
- required 필드 추가
- enum 값 제거 또는 의미 변경
- 응답 에러 스키마 재배치

실전 규칙:
- **Tolerant Reader**: 클라이언트는 모르는 필드를 무시한다.
- **Strict Writer**: 서버는 스키마에 없는 필드를 받으면 400 또는 경고 로그.
- 응답에 새 필드를 넣을 때는 기존 필드의 의미를 바꾸지 않는다. `price`를 그대로 두고 `price_with_tax`를 추가하는 식.
- 삭제는 "읽기만 하고 쓰지 않음" → "deprecation 헤더" → "문서 제거" → "실제 제거" 4단 절차를 밟는다.

## 8. REST vs gRPC vs GraphQL — 어떻게 고르나

| 축 | REST+JSON | gRPC | GraphQL |
| --- | --- | --- | --- |
| 주 사용처 | 공개 API, 웹, 모바일 | 내부 서비스 간, 저지연 | 프론트 주도 조합형 조회 |
| 스키마 | OpenAPI(옵션) | Proto(강제) | SDL(강제) |
| 성능 | JSON 파싱 비용 | HTTP/2 + Protobuf | 쿼리에 따라 들쭉날쭉 |
| 캐싱 | HTTP 캐시 친화 | 제한적 | GET+persisted query 필요 |
| 러닝 커브 | 낮음 | 보통 | 높음(N+1, 권한 경계) |

선택 기준을 한 문장으로 쓰면:
- **외부로 공개**하고 다양한 클라이언트가 붙는다 → REST+JSON. OpenAPI로 계약 공개.
- **내부 마이크로서비스**가 강한 스키마와 성능을 원한다 → gRPC. 단, 브라우저 직접 호출은 grpc-web/게이트웨이 필요.
- **화면별 데이터 조합이 자주 바뀐다**(예: 앱의 마이페이지가 주/월마다 구성 변경) → GraphQL을 게이트웨이/BFF에서만. 백엔드 모든 층을 GraphQL로 덮으면 권한·N+1·퍼시스턴스 캐시가 어려워진다.

## 9. BFF(Backend For Frontend)는 언제 쓰는가

BFF는 **프론트별 전용 백엔드**를 둬서, 공용 내부 API를 그 프론트의 화면 형태로 조합·가공한다.

쓸 만할 때:
- 웹/iOS/Android가 요구 데이터 모양이 서로 다르다.
- 공용 API를 바꿀 때마다 3개 앱이 영향을 받는다.
- 모바일은 왕복 비용이 크니 한 번에 조합된 응답을 줘야 한다.

피해야 할 때:
- 클라이언트가 하나뿐인데 BFF를 만들면 **그냥 레이어 하나 늘어난 것**.
- BFF가 도메인 로직을 들고 가면 마이크로서비스 경계가 무너진다. BFF는 "조합·표현"에 머물러야 한다.

## 10. 인증/인가, Rate Limit, 문서화

- 인증은 보통 Bearer JWT 또는 OAuth2. 헤더 이름은 `Authorization: Bearer ...`로 고정한다. 자체 헤더는 피한다.
- 인가는 **스코프**(e.g. `orders:read`, `payments:write`)와 **리소스 소유권 검사**를 분리한다. 스코프만 검사하면 "내 권한으로 남의 주문 조회"가 뚫린다.
- Rate limit 응답 헤더는 업계 관례를 따른다:
  - `RateLimit-Limit: 1000`
  - `RateLimit-Remaining: 37`
  - `RateLimit-Reset: 42`
  - 429 응답엔 `Retry-After`.
- 문서화는 OpenAPI 3.1을 단일 소스로 두고, 코드에서 생성하거나 반대로 코드가 OpenAPI를 검증한다. 문서와 구현이 다르면 **문서가 공식**이라는 규칙을 팀 합의로 박아 둔다.

## 11. 커머스 도메인 실전 예: 나쁜 설계 vs 개선 설계

### 11.1 주문 생성

나쁜 예:
```
POST /api/order/new
Body: {"user":7,"products":[{"pid":1,"qty":2}],"pay":"card","coupon":"X"}
Response 200 OK
{"success": true, "orderId": 10293, "errorMsg": null}
```

문제: 동사 URI, `success` 플래그 반패턴, 쿠폰·결제·주문이 한 엔드포인트에 엉켜 있음, 201 대신 200.

개선:
```
POST /v1/orders
Idempotency-Key: <uuid>
Authorization: Bearer <token>
{
  "items": [{"sku": "SKU-001", "quantity": 2}],
  "shipping_address_id": "addr_123",
  "coupon_code": "SPRING10",
  "payment_method_id": "pm_456"
}

201 Created
Location: /v1/orders/O-10293
{
  "order_id": "O-10293",
  "status": "PENDING_PAYMENT",
  "total_price": 28900,
  "currency": "KRW",
  "payment": {"status": "REQUIRES_ACTION", "next_action_url": "..."}
}
```

### 11.2 결제 승인

```
POST /v1/orders/{orderId}/payments
Idempotency-Key: <uuid>
```
- 비동기면 202 Accepted + `GET /v1/payments/{paymentId}`로 폴링/웹훅.
- 실패는 422 + `code=PAYMENT_DECLINED`. 카드사 원문은 `detail`에만, `code`는 우리 쪽 도메인 코드로.

### 11.3 쿠폰 사용

쿠폰 사용은 "쿠폰 자원의 상태 전이"다.
```
POST /v1/users/me/coupons/{couponId}/redemptions
```
- 이미 쓴 쿠폰: 409 + `code=COUPON_ALREADY_USED`.
- 만료: 422 + `code=COUPON_EXPIRED`.
- 대상 주문 미충족(최소 금액): 422 + `code=COUPON_MIN_AMOUNT_NOT_MET`.

### 11.4 알림 목록

```
GET /v1/users/me/notifications?limit=20&cursor=<opaque>
```
- keyset 기반, `cursor=`가 없으면 최신부터.
- 읽음 처리: `POST /v1/users/me/notifications/{id}/reads` (상태 전이를 하위 자원으로).

## 12. 로컬 실습 환경

### 12.1 준비물

- JDK 21, Spring Boot 3.3(또는 취향의 백엔드 스택)
- MySQL 8 (Docker 권장)
- `httpie` 또는 `curl`
- `k6`(부하 테스트)
- `redoc-cli`(OpenAPI 문서 렌더)

### 12.2 MySQL 8 스키마(주문 + 멱등 키)

```sql
CREATE TABLE orders (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no        CHAR(12)    NOT NULL UNIQUE,
    user_id         BIGINT      NOT NULL,
    status          VARCHAR(32) NOT NULL,
    total_price     INT         NOT NULL,
    currency        CHAR(3)     NOT NULL,
    created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    KEY idx_user_created (user_id, created_at DESC, id DESC)
) ENGINE=InnoDB;
```

### 12.3 keyset 페이지네이션 실습

```sql
-- 1페이지
SELECT id, order_no, total_price, created_at
FROM orders
WHERE user_id = 42
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- 다음 페이지 (커서에서 꺼낸 값)
SELECT id, order_no, total_price, created_at
FROM orders
WHERE user_id = 42
  AND (created_at, id) < ('2026-04-18 04:30:12.000', 12345)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

### 12.4 멱등성 실습 (curl)

```bash
KEY=$(uuidgen)
for i in 1 2 3; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8080/v1/payments \
    -H "Authorization: Bearer dev" \
    -H "Idempotency-Key: $KEY" \
    -H "Content-Type: application/json" \
    -d '{"orderId":"O-10293","amount":28900,"currency":"KRW"}'
done
# 기대 출력: 201, 200(재생), 200(재생)
```

세 번째 요청에서 **중복 결제가 일어나지 않는지**, DB에 승인 기록이 1건인지 확인하는 것이 핵심이다.

### 12.5 OpenAPI 계약 검증

```yaml
paths:
  /v1/orders:
    post:
      operationId: createOrder
      parameters:
        - in: header
          name: Idempotency-Key
          required: true
          schema: { type: string, format: uuid }
      requestBody: { ... }
      responses:
        "201": { $ref: "#/components/responses/Order" }
        "409": { $ref: "#/components/responses/Problem" }
        "422": { $ref: "#/components/responses/Problem" }
```

`spectral lint openapi.yaml`로 네이밍/필수 필드 규칙을 자동 검사한다. 문서-코드 불일치는 CI에서 막는다.

## 13. 흔한 실수 패턴

- 200 OK에 `success:false`를 실어 에러를 감춘다 → 모니터링이 전부 녹색으로 보인다.
- POST에 멱등 키가 없어서 재시도 시 중복 결제/중복 쿠폰 발급 발생.
- OFFSET 페이지네이션으로 대용량 리스트를 그대로 서비스하다가 트래픽 몰릴 때 DB가 녹는다.
- 에러 메시지를 과하게 상세히 돌려주다가 계정 열거/스키마 노출.
- 필드명을 snake_case와 camelCase로 섞어 쓴다(한 서비스 안에서는 반드시 통일).
- "내부 API니까 버전 안 붙여도 돼"라고 시작 → 2년 뒤 파트너 개방 때 전면 재설계.
- PATCH를 "델타 증가"로 정의해 멱등성을 잃는다.
- 시간 필드를 로컬 타임/포맷 혼용으로 보낸다 → ISO 8601 UTC로 통일하고 `created_at_ts`(epoch ms)를 병기하는 식으로 합의.

## 14. 면접 답변 구조: "이 API를 설계해 주세요"

시니어 백엔드 면접에서 이런 열린 문제를 받으면 다음 순서로 **말하면서** 설계를 내려간다. 면접관이 중간에 끊지 않으면 약 8~10분짜리 talk-through가 된다.

1. 문제 재정의(30초): "요구사항을 제가 이렇게 이해했습니다 — 대상 클라이언트, 규모, SLA, 외부 공개 여부."
2. 자원 모델링(1분): 명사 나열. "주문, 결제, 쿠폰, 사용자, 알림. 주문 취소는 별도 하위 자원으로 두겠습니다."
3. 엔드포인트 초안(1분): 메서드 + URI + 상태 코드. 화이트보드에 줄을 긋는다.
4. 멱등성/일관성(1~2분): "주문 생성과 결제 승인은 Idempotency-Key를 필수로 두고, 이유는 ...".
5. 데이터 볼륨/페이지네이션(1분): "목록은 keyset, 이유는 트래픽과 삽입 패턴 때문입니다."
6. 에러 계약(1분): Problem Details + 도메인 코드 분리.
7. 버전/배포/문서(1분): URI v1, OpenAPI로 계약 공유, deprecation은 Sunset 헤더 + 6개월.
8. 비기능(1~2분): 인증/인가, rate limit, 관측(로그/트레이스/메트릭), 보안.
9. 트레이드오프 정리(30초): "여기선 REST를 골랐습니다. gRPC가 좋았을 조건은 X이고, 그땐 Y를 바꿀 겁니다."

중요한 태도: **완벽한 설계**보다 **근거 있는 선택과 폐기 가능한 설계**를 보여준다. 면접관이 "재고 부족은 400 아닌가요?"처럼 찌르면, "422로 놓은 이유는 ... 다만 클라이언트가 단순 재시도만 한다면 400으로도 타협 가능합니다"처럼 조건부로 답한다.

## 15. 체크리스트 (실무/면접 공용)

- [ ] URI가 명사 중심이고 동사가 없다.
- [ ] 메서드 의미(Safe/Idempotent)가 맞다.
- [ ] 생성에는 201 + Location, 비동기에는 202 + 상태 조회 URL이 있다.
- [ ] 상태 코드와 도메인 `code`가 분리돼 있다.
- [ ] 결제/주문/쿠폰 생성 같은 POST는 `Idempotency-Key` 필수다.
- [ ] 멱등 키 저장소에 TTL과 `request_hash` 검증이 있다.
- [ ] 외부 부작용은 Outbox로 커밋과 묶여 있다.
- [ ] 목록 API는 keyset/cursor 기반이고, 필요한 복합 인덱스가 있다.
- [ ] 모든 요청/응답 스키마가 OpenAPI에 정의돼 있고 CI에서 lint된다.
- [ ] 버전 전략(URI/header)과 Sunset 헤더 운영 절차가 팀 합의로 문서화돼 있다.
- [ ] 에러 응답에 `trace_id`가 실려 있다.
- [ ] 인가 검사는 스코프와 소유권을 둘 다 한다.
- [ ] Rate limit 응답에 표준 헤더와 `Retry-After`가 있다.
- [ ] 깨지는 변경은 새 버전, 비깨지는 추가는 기존 버전에서 한다.
- [ ] 면접 talk-through 순서(문제 재정의 → 자원 → 엔드포인트 → 멱등 → 페이지네이션 → 에러 → 버전 → 비기능 → 트레이드오프)를 입으로 한 번은 리허설했다.
