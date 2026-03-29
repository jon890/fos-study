# Spring Boot 인메모리 캐시 구조

**진행 기간**: 2023.03 ~ 2024.02

스포츠 베팅 백엔드의 인메모리 캐시 전반을 구성했다. 다중 서버 환경에서 캐시 정합성을 어떻게 유지하는지가 핵심이었다.

---

## 캐시 두 종류

캐시는 성격에 따라 두 가지로 나뉜다.

### 1. Ehcache (JSR-107, `@Cacheable`)

`ehcache.xml`에 선언하고 `@Cacheable`로 사용하는 방식이다. TTL 기반 자동 만료가 필요한 데이터에 쓴다. 주로 DB에서 조회한 결과를 메서드 단위로 캐싱할 때 사용한다.

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

<cache alias="betradar_status" uses-template="default">
    <expiry><ttl>10</ttl></expiry>   <!-- 10초: 실시간성 필요 -->
</cache>
```

`CacheEventLogger`를 달아 캐시 생성/만료 이벤트를 비동기로 로깅한다. 운영 중에 캐시가 언제 갱신되는지 추적하는 데 유용하다.

### 2. 인메모리 Map 캐시 (`AbstractStaticReloadable`)

JVM 내부 `ConcurrentMap`으로 직접 관리하는 방식이다. 이벤트/설정 데이터처럼 명시적으로 리로드 제어가 필요한 경우에 사용한다.

```java
// 추상 기반 클래스
public abstract class AbstractStaticReloadable<T, Key> {
    protected final ConcurrentMap<Key, T> configMap = Maps.newConcurrentMap();
    final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

    @PostConstruct
    public abstract void reload();         // 서버 기동 시 자동 로드

    public abstract DataTableName tableName(); // 어떤 테이블 변경에 반응할지
}
```

```java
// AbstractStaticKeyReloadable: Key→T 맵 + List 형태
public void reload() {
    writeLockJob(() -> {
        configList.clear();
        configMap.clear();
        List<T> loaded = loadFromRepo();    // DB에서 새로 조회
        configList.addAll(loaded);
        loaded.forEach(a -> configMap.put(key(a), a));
        return true;
    });
}
```

각 캐시는 이 클래스를 상속해 `loadFromRepo()`와 `tableName()`만 구현하면 된다.

```java
// 추천 프로그램 목록 캐시
@Component
public class RecommendProgramCache extends AbstractStaticKeyReloadable<Event.RecommendProgramEvent, Long> {

    @Override
    protected List<Event.RecommendProgramEvent> loadFromRepo() {
        return repository.findAllByTypeAndActiveOrderByEndDateDesc(
                EventSchema.EventType.RECOMMENDER_BONUS_PROGRAM, ACTIVE)
                .stream().map(Event::toRecommendProgramEvent).collect(Collectors.toList());
    }

    @Override
    public DataTableName tableName() {
        return DataTableName.EventRecommendProgram;  // 이 테이블이 변경되면 reload
    }
}
```

---

## 캐시 정합성: MQ Fanout 구조

백엔드 서버가 여러 대 뜨는 환경에서 어드민이 데이터를 변경하면 모든 서버의 캐시를 동시에 갱신해야 한다. 이를 MQ Fanout으로 해결한다.

```
어드민 백엔드
POST /api/v2/admin/service/refresh
        │
        ▼
ServiceService.reloadMemory(tableName)
        │
        ▼
DataPublisher.reloadMemory(tableName)
        │
        ▼
   MQ Fanout 발행
(FANOUT_STATIC_DATA 토픽)
        │
   ┌────┴────┐
   ▼         ▼
백엔드 서버1  백엔드 서버2  ... (모두 동시 수신)
        │
        ▼
MqDataListener.onReloadStaticData()
        │
        ▼
해당 DataTableName의 캐시 reload()
```

Fanout 방식이라 모든 서버 인스턴스가 동시에 같은 메시지를 받는다. 특정 서버만 갱신되는 상황이 발생하지 않는다.

---

## 메시지 발행: 어드민 백엔드

어드민 백엔드에 캐시 갱신 전용 엔드포인트가 있다.

```kotlin
@RestController
@RequestMapping("/api/v2/admin/service/refresh")
class RefreshResource(private val service: ServiceService) {

    @PostMapping
    fun refreshCache(@RequestBody dto: ServiceDto.RefreshCache.Request): BaseResponseDto<*> {
        when (dto.type) {
            2 -> dto.tableNames?.forEach { service.reloadMemory(it) }   // 인메모리 캐시
            1 -> dto.cacheNames?.forEach { service.reloadCache(it) }    // Ehcache
        }
        return BaseResponseDto(data = null)
    }
}
```

- `type=2 + tableName`: `AbstractStaticReloadable` 기반 인메모리 캐시를 특정 테이블 이름으로 리로드
- `type=1 + cacheName`: Ehcache의 특정 캐시를 clear

어드민 프론트엔드에서 화이트리스트/이벤트 등을 수정한 후 이 API를 호출해 즉시 반영한다.

---

## MQ 이중화: RabbitMQ / Azure Service Bus

MQ 구현체가 환경에 따라 달라진다. `@DataPublisher.toast`와 `@DataPublisher.azure` 프로필 애너테이션으로 구분한다.

```java
// NHN Cloud 환경: RabbitMQ
@Configuration
@DataPublisher.toast   // Profile: !azure
public static class RabbitMqDataPublisher extends DataPublisher {
    public void reloadMemory(DataTableName tableName) {
        template.convertAndSend(ExchangeNames.FANOUT_STATIC_DATA, "",
            ReloadCommand.createToJson(ReloadCommandType.Memory, tableName));
    }
}

// Azure 환경: Azure Service Bus
@Configuration
@DataPublisher.azure   // Profile: azure
public static class ServiceBusDataPublisher extends DataPublisher {
    public void reloadMemory(DataTableName tableName) {
        template.convertAndSend(ExchangeNames.FANOUT_STATIC_DATA,
            ReloadCommand.createToJson(ReloadCommandType.Memory, tableName));
    }
}
```

인터페이스(`DataPublisher`)가 동일해서 나머지 코드는 MQ 종류에 관계없이 그대로 동작한다. 환경 프로필만 바꾸면 된다.

수신 측 `MqDataListener`도 같은 방식으로 분리되어 있다.

```java
@Component
@DataPublisher.toast
static class RabbitMqDataListener extends MqDataListener {
    @RabbitCommonConfig.FanoutListenBindingStaticData
    public void onRabbitMqReloadStaticData(String json) {
        onReloadStaticData(json);
    }
}

@Component
@DataPublisher.azure
static class ServiceBusDataListener extends MqDataListener {
    @PostConstruct
    public void init() {
        config.subscribe(ExchangeNames.FANOUT_STATIC_DATA, ..., (j) -> {
            onReloadStaticData((String) j);
        });
    }
}
```

---

## 수신 처리: MqDataListener

메시지를 받은 백엔드에서는 `ReloadCommand`의 타입에 따라 처리한다.

```java
public void onReloadStaticData(String json) {
    ReloadCommand command = ReloadCommand.jsonToObject(json);

    switch (command.getType()) {
        case AllEhcache:
            // 모든 Ehcache clear
            cacheManager.getCacheNames().forEach(name -> cacheManager.getCache(name).clear());
            break;
        case Ehcahe:
            // 특정 Ehcache clear
            cacheManager.getCache(command.getEhcacheName().ehcacheName).clear();
            break;
        case AllMemory:
            // 모든 AbstractStaticReloadable bean의 reload() 호출
            applicationContext.getBeansOfType(AbstractStaticReloadable.class)
                .values().forEach(r -> r.reload());
            break;
        case Memory:
            // tableName이 일치하는 캐시만 reload()
            applicationContext.getBeansOfType(AbstractStaticReloadable.class)
                .values().stream()
                .filter(r -> command.getTableName() == r.tableName())
                .forEach(r -> r.reload());
            break;
    }
}
```

---

## 동시성: ReentrantReadWriteLock

`reload()`는 `writeLock`을 잡고 실행하고, 조회(`list()`, `one()`)는 `readLock`을 잡는다. 리로드 중에 다른 스레드가 불완전한 데이터를 읽는 상황을 방지한다.

```java
public void reload() {
    writeLockJob(() -> {     // 쓰기 락: 리로드 중 읽기 차단
        configList.clear();
        configMap.clear();
        List<T> loaded = loadFromRepo();
        configList.addAll(loaded);
        loaded.forEach(a -> configMap.put(key(a), a));
        return true;
    });
}

public List<T> list() {
    return readLockJob(() -> new ArrayList<>(configList));  // 읽기 락
}
```

---

## 서버 기동 시 자동 로드

`AbstractStaticReloadable`의 `reload()`에 `@PostConstruct`가 붙어있어서 서버가 뜰 때 자동으로 DB에서 캐시를 채운다. 콜드 스타트 문제가 없다.

```java
@PostConstruct
public void reload() {
    writeLockJob(() -> {
        // 서버 기동 시 DB에서 전체 로드
        ...
    });
}
```

---

## 관련 문서

- [캐시 설계 전략](../../architecture/cache-strategies.md)
- [추천 프로그램 시스템](./referral-program.md)
