# IP 화이트리스트 구현

**진행 기간**: 2023.03 ~ 2024.02

특정 IP만 서비스 점검(maintenance)을 우회할 수 있도록 화이트리스트 기능을 구현했다. 처음에는 요청마다 DB를 조회하는 방식이었고, 이후 Ehcache를 적용해 개선했다.

---

## 목적

서버 점검 중에도 내부 QA나 특정 파트너사는 서비스에 접근할 수 있어야 했다. 점검 모드가 활성화되면 일반 요청은 `MAINTENANCE` 에러를 반환하지만, 화이트리스트에 등록된 IP는 통과시키는 방식으로 구현했다.

---

## 구현 구조

`MaintenanceInterceptor`에서 모든 요청을 가로채 점검 상태와 화이트리스트를 함께 처리한다.

```java
@Override
public boolean preHandle(HttpServletRequest request, ...) {
    Maintenance.Status gameStatus = cache.status(Maintenance.Type.Game);

    if (gameStatus == Maintenance.Status.Maintenance) {
        if (!canBypass(request) && !request.getMethod().equals("OPTIONS"))
            throw new ContentsException(ErrorCode.MAINTENANCE);  // 점검 차단
    }

    return HandlerInterceptor.super.preHandle(request, response, handler);
}

private boolean canBypass(HttpServletRequest request) {
    String ip = getRemoteAddress(request);
    List<WhiteList> whiteList = whiteListRepository.findAll();
    return whiteList.stream().anyMatch(w -> w.getIp().equals(ip));
}
```

점검 상태(`Maintenance.Status`)는 별도 `MaintenanceCache`에서 관리하고, 화이트리스트는 요청 시 DB에서 조회한다(초기 구현).

---

## IP 추출 로직

Azure 환경에 배포했기 때문에 클라이언트 IP 추출이 단순하지 않았다. 로드 밸런서나 프록시를 거치면 `request.getRemoteAddr()`는 실제 IP가 아닌 프록시 IP를 반환하기 때문이다.

```java
private String getRemoteAddress(HttpServletRequest request) {
    final String[] IP_HEADER_CANDIDATES = {
        "x-azure-clientip",       // Azure가 전달하는 실제 클라이언트 IP (1순위)
        "X-Forwarded-For",
        "Proxy-Client-IP",
        "WL-Proxy-Client-IP",
        "HTTP_X_FORWARDED_FOR",
        // ...
        "REMOTE_ADDR"
    };

    for (String header : IP_HEADER_CANDIDATES) {
        String ip = request.getHeader(header);
        if (ip != null && !ip.isEmpty() && !"unknown".equalsIgnoreCase(ip)) {
            return ip.split(",")[0];  // X-Forwarded-For는 콤마로 여러 IP가 올 수 있음
        }
    }
    return request.getRemoteAddr();
}
```

Azure 환경에서는 `x-azure-clientip` 헤더에 실제 클라이언트 IP가 담겨 오기 때문에 이걸 1순위로 체크한다. 이 부분은 배포 후 실제 헤더 로그를 찍어보면서 확인했다.

```java
// 확인 로그 (배포 후 제거 예정)
log.info("canByPass ip: {}", ip);
log.info("canByPass HEADER {}: {}", name, request.getHeader(name));
```

---

## 초기 문제: 매 요청마다 DB 조회

초기 구현에서는 `canBypass()` 호출마다 `whiteListRepository.findAll()`로 DB를 조회했다. 모든 API 요청이 `MaintenanceInterceptor`를 거치는 구조라 화이트리스트 조회가 빈번하게 발생했다.

화이트리스트 목록은 거의 바뀌지 않는 데이터인데 요청마다 DB를 치는 건 낭비였다.

---

## 개선: Ehcache 적용 (2024.02)

Ehcache에 `WHITE_LIST` 캐시를 추가하고 `@Cacheable`을 붙여 DB 조회 결과를 캐싱했다.

```xml
<!-- ehcache.xml -->
<cache alias="WHITE_LIST" uses-template="default">
    <expiry>
        <ttl unit="minutes">10</ttl>  <!-- 10분 TTL -->
    </expiry>
</cache>
```

TTL을 10분으로 설정해서 최대 10분 지연이 생기지만, 화이트리스트 변경이 즉각 반영되어야 하는 상황을 위해 어드민에서 캐시 강제 갱신 기능도 함께 제공했다.

어드민에서 화이트리스트를 등록/삭제한 후 캐시 갱신 요청을 보내면 MQ를 통해 모든 백엔드 서버의 `WHITE_LIST` 캐시가 동시에 초기화된다.

```
어드민: 화이트리스트 변경
    ↓
POST /api/v2/admin/service/refresh { type: 1, cacheNames: ["WHITE_LIST"] }
    ↓
MQ Fanout → 모든 백엔드 서버
    ↓
cacheManager.getCache("WHITE_LIST").clear()
```

캐시 갱신 전파 구조 상세는 [캐시 아키텍처](./cache-architecture.md)를 참고.

---

## 관련 문서

- [캐시 아키텍처](./cache-architecture.md) — MQ 기반 캐시 전파 구조
