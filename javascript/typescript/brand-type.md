# Typescript Brand Type (브랜드 타입)

> Brand 타입은 런타임에는 동일하지만,
> 컴파일 타임에서만 서로 다른 타입으로 취급되게 만드는 기법

Typescript는 구조적 타이핑(structural typing)이기 떄문에,
모양이 같으면 같은 타입으로 취급해버리는 문제가 있음

```ts
type UserId = string;
type OrderId = string;

const userId: UserId = 'u1';
const orderId: OrderID = 'o1';

// 컴파일 에러 없음
sendOrder(userId);
```

이걸 **컴파일 타임에 막고 싶을 때** brand 타입을 사용한다.

## 왜 Brand 타입이 필요한가?

- **TypeScript의 한계**
  - TS는 "값의 의미"를 모른다
  - `string`은 그냥 `string`
- **Brand 타입의 역할**
  - "이 string은 UserId다"
  - "이 number는 Money다"
  - 의미를 타입에 새겨서 실수를 막는다

특히 **SDK / 도메인 코드 / 금융, 결제 / POS**에서 중요

## 기본적인 Brand 타입 구현

가장 흔한 패턴

```ts
type Brand<K, T> = K & { __brand: T };

type UserId = Brand<string, 'UserId'>;
type OrderId = Brand<string, 'OrderId'>;
```

사용

```ts
const userId = 'u1' as UserId;
const orderId = 'o1' as OrderId;

// 컴파일 에러
sendOrder(userId);

// 정상
sendOrder(orderId);
```

- 런타임 비용 없음, 컴파일 후 JS에서는 그냥 string;

## "as 캐스팅 쓰면 무의미한 거 아냐"에 대한 정답

- 맞는말 + 틀린 말

  - 맞음 : `as`를 남용하면 의미 없음
  - 하지만 핵심은
    - 입구에서만 as를 허용
    - 이후에는 타입 시스템이 보호

- 권장 패턴 : 생성함수

  - ```ts
    function createUserId(value: string): UserId {
      // 여기서 검증 가능
      return value as UserId;
    }

    const userId = createUserId('u1');

    // 이후에는 타입 안전
    ```

- 좀더 안전한 패턴 (unique symbol)

  - ```ts
    declare const userIdBrand: unique symbol;

    type UserId = string & { [userIdBrand]: void };
    ```

  - 장점
    - 다른 브랜드와 절대 충돌 안 함
    - 라이브러리/SDK에 적합

## 실무에서 언제쓰면 좋은가?

- 쓰면 좋은 경우
  - 서로 다른 ID들이 많을 떄
  - 금액, 포인트, 수량 등 의미가 다른 숫자
  - SDK API boundary
  - 외부 입력을 내부 도메인으로 변환할 떄
- 안 써도 되는 경우
  - 단순 UI 코드
  - 수명 짧은 스크립트
  - 의미 구분이 필요 없는 값

## 정리

- "Brand 타입은 Typescript의 구조적 타이핑 한계를 보완해서, 같은 타입이라도 의미가 다른 값을 컴파일 타임에 구분하기 위한 기법입니다"
- "특히 SDK나 도메인 경계에서는 런타임 비용 없이 실수를 막을 수 있어서 brand 타입을 설계 도구로 사용할 수 있습니다"
