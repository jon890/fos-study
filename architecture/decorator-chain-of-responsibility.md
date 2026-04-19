# [초안] Decorator & Chain of Responsibility — 행동을 체인으로 조립하는 두 가지 방식

---

## 왜 이 두 패턴을 같이 보는가

둘 다 "여러 개의 작은 처리 단위를 체인으로 이어서 최종 결과를 만든다"는 공통 의도를 가진다. 그래서 현장에서 자주 혼동된다. 실제로 "데코레이터를 쓴다"고 말한 코드가 책임 연쇄 구조일 때도 있고, 반대인 경우도 있다.

이 글의 목적은 두 패턴의 **구조적 차이와 선택 기준**을 정리하는 것이다. 한 번 정리해두면 설계 단계에서 "우리 상황은 어느 쪽에 더 가까운가"를 분명히 고를 수 있다.

---

## 한 줄 요약

- **Decorator Pattern** — 대상 객체를 **감싸서 기능을 추가·변형**한다. 체인은 "원본 → 장식1 → 장식1+장식2 → ..." 식으로 **누적**된다. 매 단계가 다음 단계로 결과를 전달한다
- **Chain of Responsibility (CoR)** — 요청을 **핸들러 체인으로 흘려보내고**, 책임 있는 핸들러를 만나면 **거기서 멈추거나 통과**한다. 각 핸들러는 처리할지 말지, 다음으로 넘길지를 자기가 결정한다

| 축 | Decorator | Chain of Responsibility |
|----|-----------|-------------------------|
| 의도 | 기능 추가 | 요청 처리 위임 |
| 체인 종료 | 체인 끝까지 전달 | 조기 종료 가능 |
| 반환값 | 변환된 객체 | 처리 결과 또는 통과 |
| 각 단계 관점 | "나는 장식한다" | "내 책임인가? 아니면 다음에게" |
| 실행 순서 | 순서 중요 (누적) | 순서 중요 (우선순위) |

---

## 구조 비교

### Decorator

```
Original ──▶ DecoratorA(wraps) ──▶ DecoratorB(wraps) ──▶ 최종 결과
```

각 데코레이터는 같은 인터페이스를 구현하면서 내부에 원본을 품는다. 메서드 호출은 원본에 위임하되, 앞뒤로 자기 기능을 덧댄다.

```java
interface Coffee {
    int cost();
}

class BaseCoffee implements Coffee {
    public int cost() { return 3000; }
}

class MilkDecorator implements Coffee {
    private final Coffee base;
    MilkDecorator(Coffee base) { this.base = base; }
    public int cost() { return base.cost() + 500; }
}

class CaramelDecorator implements Coffee {
    private final Coffee base;
    CaramelDecorator(Coffee base) { this.base = base; }
    public int cost() { return base.cost() + 800; }
}

// 사용
Coffee order = new CaramelDecorator(new MilkDecorator(new BaseCoffee()));
order.cost(); // 4300
```

### Chain of Responsibility

```
Request ──▶ HandlerA ──▶ HandlerB ──▶ HandlerC ──▶ (처리 or 실패)
                    ↓(내가 처리)
                  [종료]
```

각 핸들러는 다음 핸들러를 참조로 가지고, 자기 책임이면 처리하고 끝내거나, 아니면 다음으로 넘긴다.

```java
abstract class AuthHandler {
    protected AuthHandler next;
    void setNext(AuthHandler next) { this.next = next; }
    abstract Result handle(Request req);
}

class JwtHandler extends AuthHandler {
    Result handle(Request req) {
        if (req.hasHeader("Authorization")) {
            return verifyJwt(req);  // 내 책임 → 처리하고 끝
        }
        return next != null ? next.handle(req) : Result.unauthorized();
    }
}

class ApiKeyHandler extends AuthHandler {
    Result handle(Request req) {
        if (req.hasHeader("X-API-Key")) {
            return verifyApiKey(req);
        }
        return next != null ? next.handle(req) : Result.unauthorized();
    }
}
```

Spring Security의 `FilterChain`, Servlet `Filter`, OkHttp `Interceptor`가 대표적인 CoR 구현이다.

---

## 실제 구분이 흐려지는 지점

두 패턴은 구현 관점에선 비슷한 뼈대를 가진다. 인터페이스 하나 + 여러 구현체 + 순서 있는 적용. 그래서 "체인"을 코드로 표현하는 순간 두 가지가 섞여 보이기도 한다.

핵심 질문 세 가지로 구별할 수 있다.

1. **각 단계가 결과를 변환하는가, 통과 여부를 결정하는가**
   - 변환(입력 → 새 입력) → Decorator
   - 통과 또는 종료 → Chain of Responsibility

2. **체인 끝까지 반드시 가는가, 중간에 끝날 수 있는가**
   - 반드시 끝까지 → Decorator
   - 중간에 종료 가능 → Chain of Responsibility

3. **각 단계가 "감싸는 구조"인가, "다음 핸들러를 참조하는 구조"인가**
   - 감쌈(composition) → Decorator
   - 참조(next pointer) → CoR

두 패턴이 자연스럽게 섞이는 경우도 있다. Servlet Filter는 CoR이지만 Filter 내부에서 `ServletRequest`나 `ServletResponse`를 감싸 새 객체로 전달하는 식으로 Decorator를 섞는다. 이땐 **"요청 라우팅은 CoR, 요청/응답 변환은 Decorator"**가 공존한다.

---

## 언제 Decorator가 더 적합한가

- 처리 로직이 **순서 있는 누적 변환**일 때. 각 단계가 앞 단계의 결과를 받아 변형한다
- **모든 단계가 실행되어야** 할 때(또는 조건부로 스킵만 하고 반드시 다음으로 넘길 때)
- 반환값이 **변환된 같은 타입의 객체**일 때
- 단위 테스트가 순수 함수 스타일로 쉬운 경우

대표 사례 — Java IO Stream (`BufferedReader → InputStreamReader → FileInputStream`), 할인 계산 체인, 슬롯 당첨 금액의 단계별 배수 적용.

## 언제 Chain of Responsibility가 더 적합한가

- **누가 처리할지 미리 알 수 없을 때**. 요청에 따라 서로 다른 핸들러가 책임을 가진다
- **조기 종료 가능성**이 있을 때. 한 핸들러가 처리하면 이후 핸들러는 실행하지 않아도 된다
- **횡단 관심사**(logging, auth, rate limiting)를 체인으로 조립할 때
- 요청이 어떤 핸들러에도 매칭되지 않아 **전체 통과 실패**가 유효한 결과일 때

대표 사례 — 웹 프레임워크 Filter/Interceptor, 인증 미들웨어 체인, Approval 워크플로우(1차 승인 → 2차 승인 → ...).

---

## Spring/Java 생태계에서의 예시

### Decorator
- `java.io.InputStream` 계열 — `BufferedInputStream`이 `FileInputStream`을 감싸서 버퍼링 추가
- Spring의 `TransactionAwareCacheDecorator` — Cache에 트랜잭션 동기화 추가
- 도메인 레벨 커스텀 Decorator — 당첨 계산, 가격 할인, 배송비 계산 등

### Chain of Responsibility
- Servlet `Filter` + `FilterChain.doFilter()`
- Spring Security의 `SecurityFilterChain`
- Spring MVC의 `HandlerInterceptor`
- OkHttp `Interceptor`
- Micrometer Observation 체인

---

## 실제 사례 — 슬롯 당첨 계산 데코레이터 체인

Decorator Pattern이 도메인 로직에 깔끔하게 맞는 사례 하나를 언어·도메인 독립적으로 정리했다: [슬롯 당첨 계산 — Decorator 체인 + 우선순위 정렬](../task/nsc-slot/slot-win-decorator-chain.md).

요점만 옮기면 이렇다.

- `PayableItemDecorator<C>` 인터페이스 — `decorate()`, `isApplicable()`, `getPriority()`, `createContext()`
- 프리게임 배수 · 프로그레시브 · 멀티플라이어 심볼 등 각 변환을 독립 Decorator로 구현
- `AbstractWinService.applyDecorators()`가 우선순위 정렬 후 순차 적용
- 새 변환 규칙 추가 시 기존 서비스·데코레이터 코드 무변경(OCP)

이 사례에서 Decorator를 선택한 이유는 "순서 있는 누적 변환"이라는 본질이 분명했기 때문이다. CoR로 구현하면 "다음 단계로 넘기지 않는 경우"가 거의 없어서 구조가 어색해진다.

---

## 설계 체크리스트

### Decorator를 고를 때

- [ ] 체인의 모든(또는 대부분) 단계가 결과를 변환하는가
- [ ] 반환 타입이 입력과 동일한가
- [ ] 단계가 누적되는 순서가 명확히 정의 가능한가
- [ ] 각 Decorator가 `isApplicable()` 같은 조건으로 스스로 스킵 판단할 수 있는가
- [ ] 불변 객체 기반으로 설계 가능한가(`withX()` / builder)

### Chain of Responsibility를 고를 때

- [ ] 요청마다 담당 핸들러가 달라지는가
- [ ] 조기 종료가 자연스러운가
- [ ] 핸들러들이 서로 다른 종류의 처리를 수행하는가(auth, log, rate limit 등)
- [ ] 마지막 핸들러에 도달했는데도 처리되지 않는 경우가 유효한 상태인가

### 공통 안티패턴

- [ ] 체인 길이가 2 이하인데 패턴을 썼다면 과설계 — `if-else`가 더 단순할 수 있다
- [ ] 각 단계가 서로 의존하면서 "다음 단계가 뭔지 알아야 내 동작을 결정한다" — 체인 구조가 본질과 안 맞는 신호
- [ ] `@SuppressWarnings("unchecked")`가 여러 레이어에 퍼져 있다면 제네릭 설계를 다시 보라 — 컨텍스트 타입을 좁혀 한 레이어에서만 캐스팅하게 구성

---

## 한 줄 정리

> Decorator는 **"결과를 층층이 덧붙이는 변환기"**, CoR는 **"책임 있는 처리기를 찾아가는 라우터"**. 체인처럼 보여도 의도가 다르다.

---

## 참고

- GoF, *Design Patterns*, 1994 — Decorator와 Chain of Responsibility 원전
- Spring Framework Reference — FilterChain / HandlerInterceptor 구조
- [Strategy Pattern](./strategy-pattern.md) — Decorator 안에 전략을 품는 조합 사례
