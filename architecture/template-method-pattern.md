# [초안] Template Method Pattern — 처리 골격을 고정하고 변형은 서브클래스에 맡기는 설계 전략

---

## 왜 이 패턴이 중요한가

백엔드 시스템을 설계하다 보면 반복적인 처리 흐름을 자주 만난다. 외부 API를 호출하는 모든 어댑터는 인증 → 요청 조립 → 호출 → 응답 파싱 → 에러 처리의 흐름을 거친다. 배치 잡은 데이터 읽기 → 검증 → 변환 → 저장의 단계를 반복한다. 결제, 쿠폰, 포인트는 각각 다르지만 모두 조건 확인 → 처리 실행 → 이력 기록 순서를 지킨다.

이 처리 흐름을 각 구현체마다 독립적으로 작성하면 어떻게 되는가? 로깅을 빠뜨리는 팀원이 생기고, 에러 처리를 제각각 구현하고, 감사 이력을 누락하는 케이스가 발생한다. 신규 기능을 추가할 때마다 "이전에 어떻게 했는지" 기존 구현을 참고해야 한다.

Template Method Pattern은 이 문제를 해결한다. **처리 골격(알고리즘의 순서와 구조)은 부모 클래스에 고정하고, 각 단계의 구체적 구현은 서브클래스에 위임**한다. 팀 전체가 지켜야 할 실행 규약을 코드로 강제할 수 있다.

시니어 엔지니어 인터뷰에서 이 패턴이 등장하는 이유는 단순히 "GoF 패턴을 아는가"를 확인하기 위해서가 아니다. **설계 원칙 이해, 상속 vs 조합의 트레이드오프 판단, 테스트 가능성까지 고려한 아키텍처 결정 능력**을 보는 것이다.

---

## 핵심 개념

### 패턴의 구조

Template Method Pattern의 핵심은 세 가지 구성 요소다.

**1. 추상 부모 클래스 (Abstract Class)**
- `templateMethod()`: `final`로 선언하여 실행 순서를 고정한다.
- 추상 메서드(abstract method): 서브클래스가 반드시 구현해야 하는 단계.
- 훅 메서드(hook method): 기본 구현이 있고, 서브클래스가 필요할 때 오버라이드할 수 있는 단계.

**2. 구체 서브클래스 (Concrete Class)**
- 추상 메서드를 구현하여 해당 단계의 구체적 행동을 정의한다.
- 필요하면 훅 메서드를 오버라이드한다.

**3. 실행 흐름의 불변성**
- 부모의 `templateMethod()`는 `final`이므로 서브클래스가 순서를 바꿀 수 없다.
- 이것이 Strategy Pattern과의 핵심 차이다.

```
AbstractClass
├── templateMethod() [final]
│   ├── step1()       [abstract]
│   ├── step2()       [abstract]
│   ├── hook()        [default no-op or default impl]
│   └── step3()       [abstract]
ConcreteClassA extends AbstractClass
├── step1() → A 방식으로 구현
├── step2() → A 방식으로 구현
└── step3() → A 방식으로 구현
ConcreteClassB extends AbstractClass
├── step1() → B 방식으로 구현
└── ...
```

---

## 패턴 적용 전: 중복과 순서 위반이 발생하는 코드

실제로 어떤 문제가 생기는지 먼저 본다.

```java
// 쿠폰 적용 서비스
@Service
public class CouponApplyService {
    public void apply(Long userId, String couponCode) {
        // 1. 쿠폰 유효성 검사
        Coupon coupon = couponRepository.findByCode(couponCode)
            .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 쿠폰"));
        if (coupon.isExpired()) throw new IllegalStateException("만료된 쿠폰");
        
        // 2. 처리 실행
        coupon.markUsed(userId);
        userRepository.deductFromCart(userId, coupon.getDiscountAmount());
        
        // 3. 이력 저장 — 누군가 빠뜨렸다
        // auditRepository.save(...) ← 빠진 경우
        
        log.info("쿠폰 적용 완료: {}", couponCode);
    }
}

// 포인트 사용 서비스
@Service
public class PointUseService {
    public void use(Long userId, int points) {
        // 검증
        UserPoint userPoint = pointRepository.findByUserId(userId)
            .orElseThrow();
        if (userPoint.getBalance() < points) throw new IllegalStateException("포인트 부족");
        
        // 실행
        userPoint.deduct(points);
        
        // 이력 — 이번엔 저장함
        auditRepository.save(new AuditLog(userId, "POINT_USE", points));
        
        // 로깅 — 포맷이 다름
        log.debug("포인트 사용: userId={}, amount={}", userId, points);
    }
}
```

**문제점:**
- `CouponApplyService`는 감사 이력을 빠뜨렸다.
- 로그 레벨과 포맷이 제각각이다.
- 새로운 결제 수단이 추가될 때마다 "이 세 단계를 반드시 지켜야 한다"는 규약을 문서로만 공유해야 한다.
- 코드 리뷰에서 매번 확인해야 한다.

---

## Template Method Pattern 적용 후

```java
// 처리 골격 정의 — 추상 부모 클래스
public abstract class BenefitApplyTemplate {

    // 실행 순서가 고정된 템플릿 메서드
    public final void execute(Long userId) {
        log.info("[{}] 혜택 적용 시작: userId={}", getClass().getSimpleName(), userId);
        
        validate(userId);          // 추상: 각 혜택마다 다른 검증
        applyBenefit(userId);      // 추상: 실제 처리 로직
        saveAuditLog(userId);      // 훅: 기본 구현 제공, 오버라이드 가능
        
        log.info("[{}] 혜택 적용 완료: userId={}", getClass().getSimpleName(), userId);
    }

    protected abstract void validate(Long userId);
    protected abstract void applyBenefit(Long userId);

    // 훅 메서드: 기본 감사 로그, 필요하면 오버라이드
    protected void saveAuditLog(Long userId) {
        auditRepository.save(new AuditLog(userId, getClass().getSimpleName(), Instant.now()));
    }
    
    @Autowired
    private AuditRepository auditRepository;
}

// 쿠폰 구현체
@Service
public class CouponApplyService extends BenefitApplyTemplate {
    private final CouponRepository couponRepository;
    private final String couponCode; // 실제로는 파라미터 전달 방식을 고려

    @Override
    protected void validate(Long userId) {
        Coupon coupon = couponRepository.findByCode(couponCode)
            .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 쿠폰"));
        if (coupon.isExpired()) throw new IllegalStateException("만료된 쿠폰");
    }

    @Override
    protected void applyBenefit(Long userId) {
        couponRepository.markUsed(userId, couponCode);
    }
}

// 포인트 구현체
@Service
public class PointUseService extends BenefitApplyTemplate {
    @Override
    protected void validate(Long userId) {
        // 포인트 잔액 확인
    }

    @Override
    protected void applyBenefit(Long userId) {
        // 포인트 차감
    }
    
    // 포인트는 감사 로그에 추가 정보 필요 → 훅 오버라이드
    @Override
    protected void saveAuditLog(Long userId) {
        super.saveAuditLog(userId);
        // 추가로 포인트 이력 테이블에도 기록
        pointHistoryRepository.save(...);
    }
}
```

이제 어떤 새로운 혜택 구현체가 추가되더라도 반드시 `validate → applyBenefit → saveAuditLog → 로깅` 순서를 따른다. 감사 로그를 빠뜨리는 것은 구조적으로 불가능하다.

---

## 실전 백엔드 적용 사례

### 사례 1: Spring Batch 처리 파이프라인

Spring Batch의 `ItemProcessor`, `ItemReader`, `ItemWriter` 자체가 Template Method 개념을 채용한다. 하지만 내부적으로 커스텀 배치 처리 골격을 정의할 때도 이 패턴이 유용하다.

```java
public abstract class DataMigrationTemplate<S, T> {

    public final MigrationResult migrate(MigrationContext context) {
        log.info("마이그레이션 시작: {}", context.getJobName());
        
        List<S> rawData = readData(context);          // 추상
        List<S> validData = filterInvalid(rawData);   // 훅 (기본: 전체 통과)
        List<T> transformed = transform(validData);    // 추상
        int saved = save(transformed, context);        // 추상
        
        return MigrationResult.of(rawData.size(), saved);
    }

    protected abstract List<S> readData(MigrationContext context);
    protected abstract List<T> transform(List<S> data);
    protected abstract int save(List<T> data, MigrationContext context);

    // 기본 구현: 필터링 없음
    protected List<S> filterInvalid(List<S> data) {
        return data;
    }
}

// 레거시 주문 마이그레이션
public class OrderMigration extends DataMigrationTemplate<LegacyOrder, Order> {
    @Override
    protected List<LegacyOrder> readData(MigrationContext ctx) {
        return legacyOrderRepository.findAll();
    }
    
    @Override
    protected List<LegacyOrder> filterInvalid(List<LegacyOrder> data) {
        return data.stream()
            .filter(o -> o.getStatus() != null)
            .collect(toList());
    }

    @Override
    protected List<Order> transform(List<LegacyOrder> data) {
        return data.stream().map(OrderMapper::convert).collect(toList());
    }

    @Override
    protected int save(List<Order> data, MigrationContext ctx) {
        return orderRepository.saveAll(data).size();
    }
}
```

### 사례 2: 외부 API 통합 어댑터

CJ OliveYoung 같은 이커머스 플랫폼에서는 여러 외부 파트너 API와 통신한다. 각 파트너마다 인증 방식은 다르지만 호출 구조는 동일하다.

```java
public abstract class ExternalApiTemplate<REQ, RES> {

    public final ApiResult<RES> call(REQ request) {
        String token = authenticate();          // 훅: 기본 Bearer 토큰
        REQ enriched = enrichRequest(request, token); // 추상: 요청 조립
        
        HttpResponse rawResponse = executeHttp(enriched); // 추상: 실제 HTTP 호출
        
        if (!isSuccess(rawResponse)) {          // 훅: 기본 200 체크
            handleError(rawResponse);           // 훅: 기본 예외 던지기
        }
        
        return parseResponse(rawResponse);      // 추상: 응답 파싱
    }

    protected String authenticate() {
        return tokenStore.getToken(getApiName());
    }
    
    protected boolean isSuccess(HttpResponse response) {
        return response.getStatusCode() == 200;
    }
    
    protected void handleError(HttpResponse response) {
        throw new ExternalApiException(getApiName(), response.getStatusCode());
    }

    protected abstract String getApiName();
    protected abstract REQ enrichRequest(REQ request, String token);
    protected abstract HttpResponse executeHttp(REQ request);
    protected abstract ApiResult<RES> parseResponse(HttpResponse response);
}

// 특정 물류 파트너 — OAuth2 + 응답 포맷이 다름
public class LogisticsApiAdapter extends ExternalApiTemplate<ShipmentRequest, ShipmentResponse> {
    
    @Override
    protected String authenticate() {
        // OAuth2 클라이언트 크리덴셜 방식
        return oauthClient.getClientCredentialToken("logistics");
    }
    
    @Override
    protected boolean isSuccess(HttpResponse response) {
        // 이 파트너는 202도 성공으로 처리
        return response.getStatusCode() == 200 || response.getStatusCode() == 202;
    }
    
    @Override
    protected String getApiName() { return "LOGISTICS_PARTNER"; }
    
    // ... 나머지 추상 메서드 구현
}
```

### 사례 3: 검증-처리-저장 서비스 골격

가장 흔한 백엔드 패턴이다. 주문, 결제, 반품 처리 모두 이 흐름을 따른다.

```java
public abstract class TransactionProcessTemplate<CMD, RESULT> {

    @Transactional
    public final RESULT process(CMD command) {
        RESULT result;
        try {
            preProcess(command);          // 훅: 선처리 (잠금, 캐시 무효화 등)
            validate(command);            // 추상: 비즈니스 검증
            result = execute(command);    // 추상: 핵심 처리
            postProcess(command, result); // 훅: 후처리 (알림, 이벤트 발행 등)
        } catch (BusinessException e) {
            handleBusinessError(command, e); // 훅: 비즈니스 에러 처리
            throw e;
        }
        return result;
    }

    protected void preProcess(CMD command) {}
    protected abstract void validate(CMD command);
    protected abstract RESULT execute(CMD command);
    protected void postProcess(CMD command, RESULT result) {}
    protected void handleBusinessError(CMD command, BusinessException e) {
        log.warn("처리 실패: cmd={}, error={}", command, e.getMessage());
    }
}

@Service
public class OrderRefundProcessor extends TransactionProcessTemplate<RefundCommand, RefundResult> {
    
    @Override
    protected void preProcess(RefundCommand cmd) {
        // 해당 주문에 비관적 잠금
        orderRepository.findByIdWithLock(cmd.getOrderId());
    }
    
    @Override
    protected void validate(RefundCommand cmd) {
        Order order = orderRepository.findById(cmd.getOrderId()).orElseThrow();
        if (!order.isRefundable()) throw new BusinessException("환불 불가 상태");
        if (cmd.getAmount() > order.getPaidAmount()) throw new BusinessException("환불액 초과");
    }
    
    @Override
    protected RefundResult execute(RefundCommand cmd) {
        // 실제 환불 처리
        return paymentGateway.refund(cmd.getPaymentId(), cmd.getAmount());
    }
    
    @Override
    protected void postProcess(RefundCommand cmd, RefundResult result) {
        eventPublisher.publish(new RefundCompletedEvent(cmd.getOrderId(), result));
    }
}
```

---

## 잘못된 사용 패턴과 개선

### 실수 1: 템플릿 메서드를 `final`로 선언하지 않음

```java
// 잘못된 코드
public abstract class ReportGenerator {
    public void generate(ReportContext ctx) {  // final 없음!
        collectData(ctx);
        format(ctx);
        export(ctx);
    }
    protected abstract void collectData(ReportContext ctx);
    protected abstract void format(ReportContext ctx);
    protected abstract void export(ReportContext ctx);
}

// 서브클래스가 순서를 재정의해버림
public class CustomReport extends ReportGenerator {
    @Override
    public void generate(ReportContext ctx) {
        export(ctx);    // 순서 바뀜: export 먼저
        collectData(ctx);
        format(ctx);
    }
}
```

**개선:** `generate()`를 `final`로 선언하면 서브클래스의 순서 변경이 컴파일 에러로 막힌다.

### 실수 2: 부모 클래스에 너무 많은 상태를 쌓는다

```java
// 나쁜 예: 부모 클래스가 상태를 직접 관리
public abstract class ProcessingTemplate {
    protected Order currentOrder;  // 상태가 부모에 있음
    protected User currentUser;
    
    public final void process(Long orderId) {
        this.currentOrder = orderRepository.findById(orderId).orElseThrow(); // 부모가 조회
        this.currentUser = userRepository.findById(currentOrder.getUserId()).orElseThrow();
        doProcess();
    }
    protected abstract void doProcess(); // 서브클래스는 부모 상태에 의존
}
```

이 구조는 멀티스레드 환경에서 상태 공유 문제를 일으키고, 서브클래스가 부모 상태에 강하게 결합된다.

```java
// 좋은 예: 필요한 데이터를 파라미터로 전달
public abstract class ProcessingTemplate {
    public final void process(Long orderId) {
        Order order = orderRepository.findById(orderId).orElseThrow();
        User user = userRepository.findById(order.getUserId()).orElseThrow();
        doProcess(order, user);  // 필요한 것을 파라미터로 넘김
    }
    protected abstract void doProcess(Order order, User user);
}
```

### 실수 3: 훅 메서드를 너무 많이 만들어 서브클래스가 혼란스러워짐

훅 메서드가 10개를 넘으면 서브클래스 작성자가 어떤 것을 오버라이드해야 하는지 알 수 없다. 이 시점이 Strategy Pattern이나 Composite Pattern으로 전환할 신호다.

```java
// 과도한 훅 — 냄새나는 코드
public abstract class OverEngineeredTemplate {
    public final void run() {
        beforeStart();        // 훅
        onStarted();          // 훅
        beforeValidate();     // 훅
        validate();           // 추상
        afterValidate();      // 훅
        beforeExecute();      // 훅
        execute();            // 추상
        afterExecute();       // 훅
        onSuccess();          // 훅
        onFinally();          // 훅
    }
    // ...
}
```

---

## Strategy Pattern과의 비교

이 비교는 인터뷰에서 반드시 나온다.

| 구분 | Template Method | Strategy |
|------|----------------|---------|
| 확장 메커니즘 | 상속 (Inheritance) | 조합 (Composition) |
| 알고리즘 순서 | 부모가 고정 | 전략 객체가 독립적으로 정의 |
| 런타임 교체 | 불가 (컴파일 타임 결정) | 가능 (의존성 주입으로 교체) |
| 결합도 | 부모-자식 강결합 | 인터페이스를 통한 느슨한 결합 |
| 테스트 용이성 | 서브클래스 단위 테스트 필요 | 전략 객체를 Mock으로 교체 가능 |
| 적합한 상황 | 처리 순서가 반드시 동일해야 할 때 | 동일 목적의 다양한 알고리즘을 런타임에 교체할 때 |

**Strategy Pattern 동일 예제:**

```java
// Strategy Pattern으로 재작성
public interface BenefitStrategy {
    void validate(Long userId);
    void apply(Long userId);
}

@Component
public class BenefitProcessor {
    private final AuditRepository auditRepository;
    
    public void process(Long userId, BenefitStrategy strategy) {
        log.info("처리 시작: userId={}", userId);
        strategy.validate(userId);
        strategy.apply(userId);
        auditRepository.save(new AuditLog(userId, Instant.now()));
        log.info("처리 완료: userId={}", userId);
    }
}

// 사용 시
benefitProcessor.process(userId, couponStrategy);
benefitProcessor.process(userId, pointStrategy);
```

**언제 Template Method, 언제 Strategy?**

- 처리 단계의 **순서가 비즈니스 규약으로 강제**되어야 한다 → Template Method
- 알고리즘을 **런타임에 교체**해야 한다 (A/B 테스트, 피처 플래그) → Strategy
- **Spring Bean으로 관리**되어야 한다 (서브클래스 각각을 Bean으로) → 둘 다 가능, Strategy가 더 자연스러움
- **테스트 커버리지**가 최우선이고 격리 테스트가 필요하다 → Strategy 선호

---

## 테스트 가능성 트레이드오프

Template Method Pattern의 가장 큰 약점은 테스트다.

```java
// 부모 클래스에 외부 의존성이 있을 때 테스트가 어려워진다
public abstract class BenefitApplyTemplate {
    @Autowired
    private AuditRepository auditRepository; // 부모에 주입된 의존성
    
    public final void execute(Long userId) {
        validate(userId);
        applyBenefit(userId);
        auditRepository.save(...); // 서브클래스 테스트에서 이것도 Mocking 필요
    }
}

// 테스트에서:
@ExtendWith(MockitoExtension.class)
class CouponApplyServiceTest {
    @InjectMocks
    private CouponApplyService service; // 부모의 auditRepository도 주입 필요
    
    @Mock
    private AuditRepository auditRepository; // 이걸 어디에 주입?
    // 부모 클래스의 private 필드에 주입하려면 리플렉션이 필요하거나 복잡해짐
}
```

**해결책 1: 생성자 주입으로 공유 의존성을 명시화**

```java
public abstract class BenefitApplyTemplate {
    private final AuditRepository auditRepository;
    
    protected BenefitApplyTemplate(AuditRepository auditRepository) {
        this.auditRepository = auditRepository;
    }
}

public class CouponApplyService extends BenefitApplyTemplate {
    private final CouponRepository couponRepository;
    
    public CouponApplyService(AuditRepository auditRepository, CouponRepository couponRepository) {
        super(auditRepository); // 부모 의존성 명시
        this.couponRepository = couponRepository;
    }
}
```

**해결책 2: 부모 클래스에 protected 오버라이드 가능한 의존성 접근점 제공**

```java
public abstract class BenefitApplyTemplate {
    // 테스트에서 오버라이드 가능
    protected AuditRepository getAuditRepository() {
        return SpringContext.getBean(AuditRepository.class);
    }
}
```

이 방식은 테스트에서 `getAuditRepository()`를 오버라이드해서 Mock을 반환할 수 있다. 다만 이 자체가 Template Method의 변형이기도 하다.

---

## 로컬 실습 환경 구성

### 빠르게 실습할 수 있는 독립 프로젝트 구조

```bash
mkdir template-method-practice && cd template-method-practice
```

```
template-method-practice/
├── src/main/java/
│   ├── template/
│   │   ├── DataExportTemplate.java       # 추상 부모
│   │   ├── CsvExportService.java         # CSV 구현체
│   │   └── JsonExportService.java        # JSON 구현체
│   └── Main.java
└── pom.xml  (Spring Boot 없이 순수 Java로 시작)
```

### 실행 가능한 전체 예제: 데이터 내보내기 파이프라인

```java
// DataExportTemplate.java
public abstract class DataExportTemplate {

    public final ExportResult export(ExportRequest request) {
        System.out.println("=== 내보내기 시작: " + request.getFormat() + " ===");
        
        List<Map<String, Object>> data = fetchData(request);
        
        if (shouldApplyFilter(request)) {
            data = applyFilter(data, request);
        }
        
        String content = serialize(data);
        String destination = writeOutput(content, request);
        
        System.out.println("=== 내보내기 완료: " + destination + " ===");
        return new ExportResult(destination, data.size());
    }

    protected abstract List<Map<String, Object>> fetchData(ExportRequest request);
    protected abstract String serialize(List<Map<String, Object>> data);
    protected abstract String writeOutput(String content, ExportRequest request);

    // 훅: 기본적으로 필터 없음
    protected boolean shouldApplyFilter(ExportRequest request) {
        return false;
    }

    protected List<Map<String, Object>> applyFilter(List<Map<String, Object>> data, ExportRequest request) {
        return data;
    }
}

// CsvExportService.java
public class CsvExportService extends DataExportTemplate {

    @Override
    protected List<Map<String, Object>> fetchData(ExportRequest request) {
        // 실습에서는 더미 데이터
        return List.of(
            Map.of("id", 1, "name", "김철수", "score", 95),
            Map.of("id", 2, "name", "이영희", "score", 87),
            Map.of("id", 3, "name", "박민준", "score", 42)
        );
    }

    @Override
    protected boolean shouldApplyFilter(ExportRequest request) {
        return request.isFilterLowScore(); // 낮은 점수 필터링 여부
    }

    @Override
    protected List<Map<String, Object>> applyFilter(List<Map<String, Object>> data, ExportRequest request) {
        return data.stream()
            .filter(row -> (int) row.get("score") >= 60)
            .collect(java.util.stream.Collectors.toList());
    }

    @Override
    protected String serialize(List<Map<String, Object>> data) {
        StringBuilder sb = new StringBuilder("id,name,score\n");
        for (var row : data) {
            sb.append(row.get("id")).append(",")
              .append(row.get("name")).append(",")
              .append(row.get("score")).append("\n");
        }
        return sb.toString();
    }

    @Override
    protected String writeOutput(String content, ExportRequest request) {
        String filename = "export_" + System.currentTimeMillis() + ".csv";
        System.out.println("CSV 내용:\n" + content);
        return filename;
    }
}

// Main.java — 실행
public class Main {
    public static void main(String[] args) {
        DataExportTemplate csvExport = new CsvExportService();
        
        // 필터 없이 전체 내보내기
        ExportResult result1 = csvExport.export(new ExportRequest("CSV", false));
        System.out.println("내보낸 행 수: " + result1.getRowCount());
        
        // 낮은 점수 필터링
        ExportResult result2 = csvExport.export(new ExportRequest("CSV", true));
        System.out.println("필터 후 행 수: " + result2.getRowCount());
    }
}
```

### 테스트 작성 연습

```java
@ExtendWith(MockitoExtension.class)
class DataExportTemplateTest {

    // 추상 클래스 테스트를 위한 테스트 전용 구체 구현
    private static class TestableExport extends DataExportTemplate {
        boolean filterCalled = false;
        
        @Override
        protected List<Map<String, Object>> fetchData(ExportRequest request) {
            return List.of(Map.of("id", 1, "value", "test"));
        }
        
        @Override
        protected String serialize(List<Map<String, Object>> data) {
            return data.toString();
        }
        
        @Override
        protected String writeOutput(String content, ExportRequest request) {
            return "test-output";
        }
    }

    @Test
    void 필터훅이_false이면_applyFilter가_호출되지_않는다() {
        TestableExport service = new TestableExport();
        ExportResult result = service.export(new ExportRequest("TEST", false));
        
        assertThat(result.getRowCount()).isEqualTo(1);
        assertThat(service.filterCalled).isFalse();
    }
    
    @Test
    void 반환값이_항상_ExportResult_타입이다() {
        TestableExport service = new TestableExport();
        ExportResult result = service.export(new ExportRequest("TEST", false));
        assertThat(result).isNotNull();
        assertThat(result.getDestination()).isEqualTo("test-output");
    }
}
```

---

## 인터뷰 답변 프레이밍

### Q1. "Template Method Pattern이 무엇이고 언제 사용하나요?"

**답변 구조: 정의 → 문제 상황 → 해결 방식 → 실전 경험 → 한계 인지**

> Template Method Pattern은 알고리즘의 처리 골격을 추상 부모 클래스의 `final` 메서드로 고정하고, 각 단계의 구체적인 구현을 서브클래스에 위임하는 패턴입니다.
>
> 실무에서는 여러 서비스가 동일한 처리 순서를 반드시 따라야 할 때 사용했습니다. 예를 들어 외부 파트너 API 통합에서 인증 → 요청 조립 → 호출 → 응답 파싱 순서를 모든 어댑터가 반드시 따르도록 강제해야 했는데, 이 순서를 `final` 템플릿 메서드로 선언하여 팀원이 임의로 순서를 바꾸거나 단계를 누락하는 것을 컴파일 타임에 막았습니다.
>
> 다만 상속을 기반으로 하기 때문에 부모 클래스 변경이 모든 서브클래스에 영향을 미치는 취약성이 있습니다. 알고리즘을 런타임에 교체해야 하거나 더 유연한 조합이 필요하면 Strategy Pattern으로 전환을 고려합니다.

### Q2. "Template Method vs Strategy, 어떤 기준으로 선택하나요?"

> 두 패턴 모두 "공통 흐름에서 변하는 부분을 격리"하는 목적을 갖지만 접근이 다릅니다. Template Method는 상속으로 변형 지점을 강제하고 순서를 부모가 소유합니다. Strategy는 조합으로 알고리즘 자체를 교체 가능한 객체로 분리합니다.
>
> 저는 세 가지 기준으로 판단합니다. 첫째, 처리 순서가 비즈니스 규약으로 불변이면 Template Method입니다. 환불 처리에서 검증을 건너뛰는 것은 절대 허용해서는 안 됩니다. 둘째, 런타임에 행동을 교체해야 한다면 Strategy입니다. 배송지 유효성 검사 알고리즘을 국내/해외에 따라 실시간 교체하는 경우가 그렇습니다. 셋째, Spring Bean 컨텍스트에서 관리해야 하는 경우에는 Strategy가 더 자연스럽습니다. `@Qualifier`나 `List<BenefitStrategy>` 주입으로 구현체를 깔끔하게 관리할 수 있습니다.

### Q3. "상속의 단점을 알면서도 Template Method를 선택할 때가 있나요?"

> 있습니다. '상속보다 조합을 선호하라'는 원칙은 중요하지만 절대 규칙은 아닙니다. Template Method를 선택하는 타당한 상황은 처리 단계 수가 적고(3~5개), 처리 순서가 비즈니스 규약으로 고정되어 있으며, 서브클래스 계층이 2단계를 넘지 않을 것이 확실할 때입니다. 이때는 Strategy보다 Template Method가 코드량도 적고 의도가 더 명확합니다.
>
> 반대로 훅 메서드가 7개를 넘거나 서브클래스가 부모 상태에 의존하기 시작하거나 런타임 교체 요구가 생기면 Strategy로 리팩토링합니다.

---

## 체크리스트

인터뷰 전 확인할 사항:

- [ ] 추상 부모 클래스의 `templateMethod()`를 `final`로 선언해야 하는 이유를 설명할 수 있다
- [ ] 추상 메서드(abstract)와 훅 메서드(hook)의 차이와 각각 언제 쓰는지 말할 수 있다
- [ ] Template Method와 Strategy의 차이를 상속 vs 조합, 컴파일 타임 vs 런타임 교체 관점에서 설명할 수 있다
- [ ] Spring 실무에서 Template Method를 적용한 구체적 예시를 하나 이상 말할 수 있다 (배치, 외부 API, 결제 처리 등)
- [ ] 부모 클래스에 `@Autowired` 필드가 있을 때 서브클래스 테스트에서 발생하는 문제와 해결책을 설명할 수 있다
- [ ] 훅 메서드가 너무 많아지면 어떤 패턴으로 전환할지 말할 수 있다
- [ ] Spring의 `JdbcTemplate`, `RestTemplate`이 Template Method Pattern과 어떻게 연결되는지 설명할 수 있다
- [ ] "상속보다 조합을 선호하라"는 원칙과 Template Method Pattern의 관계를 설명하되, 맹목적으로 한쪽만 주장하지 않는다

---

*Spring의 `JdbcTemplate`은 JDBC 연결 → 쿼리 실행 → 결과 매핑 → 연결 해제의 골격을 내부에 고정하고 SQL과 `RowMapper`만 개발자가 제공하게 한다. `AbstractRoutingDataSource`는 `determineCurrentLookupKey()`라는 훅 메서드 하나로 다중 데이터소스 라우팅을 구현한다. 이 두 클래스를 직접 읽어보면 Template Method Pattern의 실전 활용이 어떻게 우아한지 체감할 수 있다.*
