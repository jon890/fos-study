# Spring Boot 인메모리 캐시 구조 — 다중 인스턴스 정합성

**진행 기간**: 2023.03 ~ 2024.02

스포츠 베팅 백엔드의 인메모리 캐시 전반을 구성했다. **다중 서버 환경에서 캐시 정합성을 어떻게 유지하는지**가 핵심이었다. Ehcache와 자체 `Map` 캐시 두 종류를 상황에 맞게 쓰고, 어드민에서 데이터가 바뀌면 MQ Fanout으로 모든 서버가 동시에 갱신하도록 했다. 설계 결정과 협업 맥락을 남긴다.

> 내부 공통 추상 기반 클래스명은 일반화(`ReloadableCache` 등)해서 표기했다. 구조와 의사결정 중심으로 읽으면 된다.

---

## 캐시 두 종류 — 언제 어떤 걸 쓰나

캐시는 **리로드 제어의 주체**에 따라 둘로 나눴다.

### 1. Ehcache (JSR-107, `@Cacheable`)

`ehcache.xml`에 선언하고 `@Cacheable`로 사용한다. TTL 기반 자동 만료에 맡기는 데이터에 쓴다. 주로 DB 조회 결과를 메서드 단위로 캐싱할 때.

```xml
<cache-template name="default">
    <expiry>
        <ttl unit="seconds">60</ttl>
    </expiry>
    <listeners>
        <listener>
            <class>...CacheEventLogger</class>
            <event-firing-mode>ASYNCHRONOUS</event-firing-mode>
            <events-to-fire-on>CREATED</events-to-fire-on>
            <events-to-fire-on>EXPIRED</events-to-fire-on>
        </listener>
    </listeners>
    <heap>10000</heap>
</cache-template>

<!-- 데이터 성격에 따라 TTL을 다르게 설정 -->
<cache alias="WHITE_LIST" uses-template="default">
    <expiry><ttl unit="minutes">10</ttl></expiry>
</cache>

<cache alias="static_banners" uses-template="default">
    <expiry><ttl unit="days">1</ttl></expiry>
</cache>

<cache alias="external_vendor_status" uses-template="default">
    <expiry><ttl>10</ttl></expiry>   <!-- 10초: 실시간성 필요 -->
</cache>
```

`CacheEventLogger`를 달아 캐시 생성/만료 이벤트를 비동기로 로깅한다. 운영 중에 캐시가 언제 갱신되는지 추적하는 데 유용하다.

### 2. 인메모리 Map 캐시 — 사내 공통 추상 기반

JVM 내부 `ConcurrentMap`으로 직접 관리하는 방식이다. 이벤트/설정 데이터처럼 **TTL 만료로 풀기에 부적절하고, 명시적 리로드 제어가 필요한 경우**에 쓴다. 팀이 공통으로 쓰는 추상 기반 클래스를 상속해서 만든다.

```java
// 개념 설명용 의사코드 — 실제 기반 클래스는 사내 공통 인프라
public abstract class ReloadableCache<T, Key> {
    protected final ConcurrentMap<Key, T> configMap = new ConcurrentHashMap<>();
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

    @PostConstruct
    public abstract void reload();            // 서버 기동 시 자동 로드
    public abstract DataTable watchedTable(); // 이 테이블 변경에 반응
}

public abstract class ReloadableKeyedCache<T, Key> extends ReloadableCache<T, Key> {
    protected final List<T> configList = new ArrayList<>();

    public void reload() {
        writeLockJob(() -> {
            configList.clear();
            configMap.clear();
            List<T> loaded = loadFromRepo();
            configList.addAll(loaded);
            loaded.forEach(a -> configMap.put(key(a), a));
        });
    }

    protected abstract List<T> loadFromRepo();
    protected abstract Key key(T t);
}
```

각 캐시는 이 클래스를 상속해 `loadFromRepo()`와 `watchedTable()`만 구현하면 된다.

```java
// 개념 설명용 의사코드 — 프로그램 목록 캐시
@Component
class ProgramListCache extends ReloadableKeyedCache<ProgramEvent, Long> {
    protected List<ProgramEvent> loadFromRepo() {
        return repository.findAllActive(...).stream()
                .map(Event::toProgramEvent).toList();
    }
    public DataTable watchedTable() { return DataTable.PROGRAM_EVENT; }
}
```

> **인사이트.** 공통 추상 기반을 두면 **"캐시 수가 늘어날수록 개별 캐시는 더 짧아진다"**. 새 캐시를 만들 때 개발자가 쓸 정보가 `loadFromRepo()`와 `watchedTable()` 두 개라는 게 명확해서, 내부 상태 관리(락, Map 구조, 리로드 훅)는 실수할 여지가 없다.

---

## 캐시 정합성: MQ Fanout

백엔드 서버가 여러 대 뜨는 환경에서 어드민이 데이터를 변경하면 모든 서버의 캐시를 동시에 갱신해야 한다. MQ Fanout으로 풀었다.

```
어드민 백엔드
POST /api/v2/admin/service/refresh
        │
        ▼
   서비스 계층 (reloadMemory(tableName))
        │
        ▼
   DataPublisher.reloadMemory(tableName)
        │
        ▼
   MQ Fanout 발행 (FANOUT_STATIC_DATA 토픽)
        │
   ┌────┴────┐
   ▼         ▼
백엔드 서버1  백엔드 서버2  ... (모두 동시 수신)
        │
        ▼
   리스너가 watchedTable()이 일치하는 캐시만 reload()
```

Fanout이라 모든 인스턴스가 동시에 같은 메시지를 받는다. 특정 서버만 갱신되는 상황이 발생하지 않는다.

### 발행: 어드민 백엔드

어드민 백엔드에 캐시 갱신 전용 엔드포인트를 뒀다.

```kotlin
// 개념 설명용 의사코드
@RestController
@RequestMapping("/api/v2/admin/service/refresh")
class RefreshResource(private val service: ServiceService) {

    @PostMapping
    fun refreshCache(@RequestBody dto: RefreshDto): BaseResponse<*> {
        when (dto.type) {
            MEMORY -> dto.tableNames?.forEach(service::reloadMemory)  // 인메모리 캐시
            EHCACHE -> dto.cacheNames?.forEach(service::reloadCache)  // Ehcache
        }
        return BaseResponse.ok()
    }
}
```

- `MEMORY + tableName`: 리로드 가능 캐시를 특정 테이블 이름으로 리로드
- `EHCACHE + cacheName`: Ehcache의 특정 캐시를 clear

어드민 프론트엔드에서 화이트리스트/이벤트 등을 수정한 후 이 API를 호출해 즉시 반영한다.

---

## MQ 이중화 — RabbitMQ / Azure Service Bus

MQ 구현체가 환경에 따라 달라진다. 인프라 벤더가 둘이어서(NHN Cloud의 RabbitMQ / Azure Service Bus) 각각의 구현을 두고 프로필 애너테이션으로 분기했다.

```java
// 개념 설명용 의사코드
@Configuration
@DataPublisher.rabbitmq   // Profile: !azure
public static class RabbitMqDataPublisher extends DataPublisher {
    public void reloadMemory(DataTable table) {
        template.convertAndSend(EXCHANGE_STATIC_DATA, "",
            ReloadCommand.toJson(ReloadType.MEMORY, table));
    }
}

@Configuration
@DataPublisher.azure      // Profile: azure
public static class ServiceBusDataPublisher extends DataPublisher {
    public void reloadMemory(DataTable table) {
        template.convertAndSend(EXCHANGE_STATIC_DATA,
            ReloadCommand.toJson(ReloadType.MEMORY, table));
    }
}
```

인터페이스(`DataPublisher`)가 동일해서 나머지 코드는 MQ 종류에 관계없이 그대로 동작한다. 환경 프로필만 바꾸면 된다. `if (azure) ... else ...` 분기로 풀면 로직이 뒤엉키는데, 프로필 기반 애너테이션 + 동일 인터페이스로 풀면 두 구현이 호출부에 대해 투명해진다. 수신 측 리스너도 같은 방식으로 분리되어 있다.

---

## 수신: 명령 디스패치

메시지를 받은 백엔드는 `ReloadCommand`의 타입에 따라 처리한다.

```java
// 개념 설명용 의사코드
public void onReloadStaticData(String json) {
    ReloadCommand cmd = ReloadCommand.fromJson(json);
    switch (cmd.getType()) {
        case ALL_EHCACHE:
            cacheManager.getCacheNames().forEach(n -> cacheManager.getCache(n).clear());
            break;
        case EHCACHE:
            cacheManager.getCache(cmd.getCacheName()).clear();
            break;
        case ALL_MEMORY:
            applicationContext.getBeansOfType(ReloadableCache.class).values()
                .forEach(ReloadableCache::reload);
            break;
        case MEMORY:
            applicationContext.getBeansOfType(ReloadableCache.class).values().stream()
                .filter(c -> c.watchedTable() == cmd.getTable())
                .forEach(ReloadableCache::reload);
            break;
    }
}
```

"어떤 테이블이 바뀌었다"는 정보 하나로 **자신이 구독 중인 캐시만 리로드**하는 구조다. 개별 캐시는 자신이 어느 테이블을 봐야 하는지만 알면 되고, 중앙 디스패처가 필터링을 담당한다.

---

## 동시성: ReentrantReadWriteLock

`reload()`는 `writeLock`을 잡고 실행하고, 조회(`list()`, `one()`)는 `readLock`을 잡는다. 리로드 중에 다른 스레드가 불완전한 데이터를 읽는 상황을 방지한다.

```java
// 개념 설명용 의사코드
public void reload() {
    writeLockJob(() -> {      // 쓰기 락: 리로드 중 읽기 차단
        configList.clear();
        configMap.clear();
        List<T> loaded = loadFromRepo();
        configList.addAll(loaded);
        loaded.forEach(a -> configMap.put(key(a), a));
    });
}

public List<T> list() {
    return readLockJob(() -> new ArrayList<>(configList));  // 읽기 락
}
```

`ConcurrentMap`만으로는 부족하다 — put/get 원자성은 있지만 "clear + 여러 put"처럼 **여러 연산을 묶은 스냅샷 일관성**은 보장 못 한다. 읽기/쓰기 락으로 그 구간을 감싸야 리로드 중에 "절반쯤 비어 있는 Map"이 응답으로 나가지 않는다.

> **인사이트.** 이 구조를 선택한 뒤로 리로드 타이밍에 간헐적으로 잡히던 "빈 상태 응답 버그"가 사라졌다. **기본 스레드 안전 자료구조로 충분한 경우와 부족한 경우를 구분**하는 게 동시성 설계의 첫 체크포인트다.

---

## 서버 기동 시 자동 로드

`@PostConstruct`로 `reload()`를 호출해서 서버가 뜰 때 자동으로 DB에서 캐시를 채운다. 콜드 스타트 문제가 없다 — 첫 요청이 들어오기 전에 캐시가 이미 채워져 있다.

---

## 협업이 공통 기반의 품질을 결정했다

이 문서가 다루는 건 팀 공통 인프라라, **내가 만든 기반을 다른 팀원이 얼마나 쉽게 쓰느냐**가 품질의 기준이었다. 추상 클래스의 abstract 메서드를 2개(`loadFromRepo`, `watchedTable`)로 좁히는 데 꽤 시간을 썼는데, 여기가 넓어지면 새 캐시를 붙이는 도메인 담당자가 상태 관리 실수를 할 여지가 생긴다. 좁힐수록 **다른 사람이 쓸 때의 인지 부담이 줄어든다**는 감각이 이 작업에서 생겼다.

어드민 팀과는 **"테이블 이름(enum) + 명령 타입"** 두 필드 계약으로 인터페이스를 단순화했다. 캐시가 새로 추가돼도 어드민 코드는 enum 값 하나만 더하면 끝이라, 새 캐시를 붙이는 사이클에서 백엔드·어드민 동시 수정 부담을 줄였다. 인프라 담당과는 RabbitMQ/Azure Service Bus 전환 시기의 환경 설정을 같이 디버깅했는데, MQ 선택 자체는 인프라 제약이었고 구현체 추상화는 내 몫이었다.

PR 리뷰 단계에서는 "새 캐시 추가 시 checklist"를 PR 템플릿에 박았다. "테이블 enum 등록했는가", "`@PostConstruct reload()`가 비어 있지 않은가", "어드민 쪽 enum도 같이 갱신됐는가" — 신규 캐시 추가 시 한쪽만 등록되는 실수가 눈에 띄게 줄었다.

---

## 지금 보면

2년 지난 지금 다시 본다면:

- **`ReloadableCache`를 Bean 자동 스캔에 의존**하는 부분(`applicationContext.getBeansOfType`)은 편했지만 런타임에만 바인딩이 검증된다. Spring의 `@EventListener` 기반으로 명시적 이벤트 구독으로 갔어도 괜찮았겠다.
- **Caffeine 기반으로 갈지 고민한 적도 있었지만 결국 자체 구현**을 유지했다. 전체 원자적 리로드 + 테이블 단위 구독이라는 요구 조합을 라이브러리로 만족시키기 어려워서였다. 지금도 같은 결정을 내릴 것 같다.

반대로 잘 했다고 생각하는 건 **공통 기반을 충분히 얇게** 만든 부분이다. abstract 메서드 2개(`loadFromRepo`, `watchedTable`)만 요구하니 도메인 담당자가 캐시를 붙일 때 학습 곡선이 거의 없었다.

---

## 관련 문서

- [IP 화이트리스트 구현](./whitelist.md) — Ehcache + 공통 기반 캐시를 함께 쓴 사례
- [추천 프로그램 시스템](./referral-program.md) — `ReloadableKeyedCache` 기반 캐시의 실 예시
