# Redis 세션 저장소 (Session Store)

HTTP는 무상태(Stateless) 프로토콜이라 서버가 클라이언트를 기억하지 못한다. 세션은 이 문제를 해결하기 위해 서버 측에 사용자 상태를 저장하는 방식이다. 단일 서버에서는 메모리 세션으로 충분하지만, **다중 서버 환경에서는 서버 간 세션 공유**가 필요하다.

---

## 문제: 다중 서버의 세션 불일치

```
사용자 로그인 요청 → 로드 밸런서 → 서버 A (세션 생성)
다음 요청          → 로드 밸런서 → 서버 B (세션 없음 → 로그인 필요!)
```

해결 방법은 세 가지가 있다.

| 방법 | 설명 | 단점 |
|------|------|------|
| **Sticky Session** | 같은 사용자를 항상 같은 서버로 라우팅 | 특정 서버에 부하 집중, 서버 장애 시 세션 유실 |
| **세션 복제** | 모든 서버가 세션을 복제해서 보유 | 서버 수 증가 시 복제 비용 폭증 |
| **중앙 세션 저장소** | Redis 같은 외부 저장소에 세션 저장 | 네트워크 호출 추가, 저장소 장애 대응 필요 |

다중 서버 환경에서는 **중앙 세션 저장소**(Redis) 방식이 가장 일반적이다.

---

## Redis를 쓰는 이유

- **인메모리**: 세션 조회가 매 요청마다 발생하므로 속도가 중요
- **TTL 기반 자동 만료**: 세션 만료를 별도 배치 없이 자동 처리
- **원자적 갱신**: 세션 마지막 접근 시간 갱신이 안전
- **수평 확장**: 서버를 아무리 늘려도 세션 저장소는 Redis 하나

---

## 기본 구현

```bash
# 세션 생성 (로그인 시)
SET session:{sessionId} {user_info_json} EX 1800   # 30분

# 세션 조회 (매 요청마다)
GET session:{sessionId}

# 세션 갱신 (접근 시마다 만료 시간 연장)
EXPIRE session:{sessionId} 1800

# 세션 삭제 (로그아웃)
DEL session:{sessionId}
```

세션 데이터는 Hash로 저장하면 필드 단위 접근이 가능하다.

```bash
# Hash로 세션 저장
HSET session:{sessionId} userId 1001 email "user@example.com" role "ADMIN"
EXPIRE session:{sessionId} 1800

# 특정 필드만 조회
HGET session:{sessionId} userId
HGET session:{sessionId} role

# 세션 전체 조회
HGETALL session:{sessionId}
```

---

## Spring Session + Redis

Spring Boot에서는 **Spring Session**이 Redis 세션을 자동으로 처리해준다. `HttpSession` API를 그대로 사용하면 되고, 내부적으로 Redis에 저장된다.

### 설정

```groovy
// build.gradle
implementation 'org.springframework.boot:spring-boot-starter-data-redis'
implementation 'org.springframework.session:spring-session-data-redis'
```

```yaml
# application.yml
spring:
  session:
    store-type: redis
    timeout: 1800s       # 세션 만료 시간
    redis:
      namespace: "myapp:session"  # Redis 키 접두사
  data:
    redis:
      host: localhost
      port: 6379
```

```java
// 활성화
@SpringBootApplication
@EnableRedisHttpSession
public class Application { ... }
```

### 사용

```java
@RestController
public class AuthController {

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest req,
                                    HttpSession session) {
        User user = authService.authenticate(req);
        session.setAttribute("userId", user.getId());
        session.setAttribute("role", user.getRole());
        return ResponseEntity.ok("로그인 성공");
    }

    @GetMapping("/profile")
    public ResponseEntity<?> profile(HttpSession session) {
        Long userId = (Long) session.getAttribute("userId");
        if (userId == null) {
            return ResponseEntity.status(401).build();
        }
        return ResponseEntity.ok(userService.findById(userId));
    }

    @PostMapping("/logout")
    public ResponseEntity<?> logout(HttpSession session) {
        session.invalidate();  // Redis에서 세션 삭제
        return ResponseEntity.ok("로그아웃 성공");
    }
}
```

Spring Session이 생성하는 Redis 키 구조:

```
myapp:session:sessions:{sessionId}           # 세션 데이터 (Hash)
myapp:session:sessions:expires:{sessionId}   # 만료 처리용
myapp:session:index:...                      # 인덱스 (사용자별 세션 목록)
```

---

## JWT vs Redis 세션

현대 웹 서비스에서 세션 방식과 JWT 방식 중 무엇을 선택할지는 자주 논의되는 주제다.

| 항목 | Redis 세션 | JWT |
|------|-----------|-----|
| 저장 위치 | 서버 (Redis) | 클라이언트 (토큰) |
| 무효화 | 즉시 가능 (DEL) | 어려움 (토큰 만료 전까지) |
| 서버 부하 | 매 요청마다 Redis 조회 | 서명 검증만 (Redis 불필요) |
| 수평 확장 | Redis 필요 | Redis 없어도 가능 |
| 세션 데이터 크기 | 제한 없음 | 토큰 크기 제한 (~수 KB) |
| 보안 | 서버 통제 | 토큰 탈취 시 만료 전까지 유효 |

**선택 기준:**
- 즉각적인 로그아웃/계정 정지가 중요하다 → **Redis 세션**
- 마이크로서비스 간 인증 전파가 필요하다 → **JWT**
- 실시간 세션 무효화 + 확장성 둘 다 필요하다 → **JWT + Redis 블랙리스트** 조합

### JWT + Redis 블랙리스트 패턴

JWT는 유지하면서 강제 만료가 필요한 경우(로그아웃, 계정 정지)에만 Redis를 사용한다.

```bash
# 로그아웃 시 해당 토큰을 블랙리스트에 등록
SET jwt:blacklist:{jti} 1 EX {remaining_ttl}

# 요청마다 블랙리스트 확인
EXISTS jwt:blacklist:{jti}
# 1이면 → 거부 (로그아웃된 토큰)
# 0이면 → 허용
```

---

## 사용자별 다중 세션 관리

같은 사용자가 여러 디바이스에서 로그인한 경우, 사용자별 세션 목록을 관리할 수 있다.

```bash
# 로그인 시 사용자 세션 목록에 추가
SADD user:sessions:{userId} {sessionId}

# 세션 생성
SET session:{sessionId} {data} EX 1800

# 사용자의 모든 세션 강제 만료 (계정 정지, 비밀번호 변경 시)
SMEMBERS user:sessions:{userId}
# → 각 sessionId에 DEL session:{sessionId}
DEL user:sessions:{userId}
```

---

## 주의사항

### 세션 고정 공격 (Session Fixation)

로그인 성공 후 반드시 **새 세션 ID를 발급**해야 한다. 로그인 전 세션 ID를 그대로 사용하면 공격자가 미리 세션 ID를 심어놓을 수 있다.

```java
// Spring Security는 기본적으로 로그인 시 세션을 재생성
// session-fixation: migrate-session (기본값) 또는 new-session
```

### Redis 장애 대응

Redis 세션 저장소가 다운되면 모든 사용자가 로그아웃되는 상황이 발생한다. 고가용성을 위해 Redis Sentinel 또는 Cluster 구성을 권장한다.

→ 고가용성 구성 상세: [Redis 영속성과 클러스터](./backup.md)

### 세션 크기 관리

세션에 대용량 객체를 저장하면 매 요청마다 Redis에서 큰 데이터를 직렬화/역직렬화한다. 세션에는 **userId, role** 같은 최소한의 식별 정보만 저장하고, 나머지는 요청마다 조회하는 방식이 낫다.

---

## 관련 문서

- [Redis 기본](./basic.md) — Redis String, Hash 자료구조
- [캐시 설계 전략](../../architecture/cache-strategies.md) — 캐싱 패턴
- [Redis 영속성과 클러스터](./backup.md) — 고가용성 구성
