# 13개 로케일 다국어 시스템 — Svelte derived 합성 + 백엔드 캐시 사전 구성

**진행 기간**: 2023.08 ~ 2024.02

스포츠 베팅 플랫폼의 다국어 시스템을 프론트엔드부터 백엔드 캐시까지 설계·구현했다. 글로벌 대응을 위해 13개 로케일을 지원했고, 스포츠 베팅이라는 도메인 특성상 UI 문구뿐 아니라 **경기 마켓 이름, 선수 이름 치환, 핸디캡 표기** 같은 템플릿 번역까지 필요했다.

---

## 요구사항이 만든 제약

일반 웹 서비스의 i18n과는 결이 달랐다.

- **13개 로케일을 런타임에 전환** — 페이지 리로드 없이 즉시 반영
- **두 가지 메시지 소스** — 앱 UI 문구(내부 관리)와 경기 용어(Betradar 같은 외부 스포츠 데이터 공급사 제공)가 별개
- **템플릿 치환** — `"{$competitor1} vs {$competitor2}"`처럼 선수/팀 이름을 실시간 경기 데이터와 합성
- **핫 리로드** — 운영 중 어드민에서 번역을 수정하면 앱 재배포 없이 즉시 반영
- **로케일 의존 파싱** — 일본어는 괄호가 전각(`（`)이라 마켓 이름 정리 정규식이 다르다

이 조합이면 `svelte-i18n` 같은 라이브러리 하나로는 부족했다. Svelte derived store 기반으로 직접 구성했다.

---

## 전체 구조

```
[어드민] ─ MQ(정적 데이터 리로드) ─▶ [백엔드 캐시 리로드]
                                 │
[DB: 언어 / 외부 벤더 언어 테이블]
                                 │
                        [백엔드: 13 로케일 × N 키 맵 사전 구성]
                                 │
                          GET /api/lang/{locale}
                                 │
                                 ▼
      [프론트: LANG_STORE (writable)] ← init(data)
                 │
                 ▼
  [LanguageService: derived 체인]
      └─▶ 템플릿 치환 derived 여러 개 (선수 이름, 핸디캡, outcome)
           └─▶ 상위 합성 derived (marketName, outcomeName …)
                 │
                 ▼
   [컴포넌트: $message('key') — 언어 변경 시 자동 리렌더]
```

**응답 시점 계산을 사전 계산으로 밀어 넣는다**는 방향이 양쪽에 공통이다. 백엔드는 캐시 빌드 시점에, 프론트는 derived 그래프 빌드 시점에 계산을 끝낸다.

---

## 프론트엔드 — Svelte derived로 반응형 다국어

### 언어 데이터 store

두 소스(`system`/외부 벤더)를 하나의 writable에 묶었다.

```ts
// 개념 설명용 의사코드
type LangData = {
  vendor: Record<string, string>,   // Betradar 같은 외부 공급사 용어
  system: Record<string, string>,   // 앱 UI 문구
}

export const LANG_STORE = writable<LangData>({ vendor: {}, system: {} })
```

묶은 이유는 단순하다. **언어 변경은 항상 두 맵을 같이 교체**한다. 따로 관리하면 둘 중 하나만 갱신된 중간 상태가 UI에 노출될 여지가 있다.

### derived를 "함수를 반환하는 store"로 쓴다

핵심 트릭이다. `derived`가 값이 아니라 `(key) => string` **함수**를 반환하게 만든다.

```ts
// 개념 설명용 의사코드
export const message = derived(
  LANG_STORE,
  $store => (key, ...args) => interpolate($store.system[key] ?? key, ...args)
)
```

컴포넌트에서 `$message('login.title')`로 쓴다. store가 바뀌면 `message` 자체가 재구성되고, 이 함수를 호출하는 모든 컴포넌트가 자동 재평가된다.

이 한 줄이 다국어 시스템의 반응성 전부를 담고 있었다. "언어 데이터 + 호출 시 파라미터"를 derived의 클로저 + 반환 함수로 분리하는 덕분에 언어 변경 1번이 모든 소비처에 전파된다.

### 템플릿 치환 — derived의 합성

스포츠 베팅 마켓 이름은 `"Over {total}"`, `"Handicap {$competitor1} +{hcp}"` 같은 템플릿. 로케일이 바뀌면 템플릿이 바뀌고 거기에 실시간 경기 데이터가 합성된다. derived를 여러 단계로 쌓아서 풀었다.

```ts
// 개념 설명용 의사코드
export const replaceCompetitors = derived(
  vendorMessage,
  $vendor => (template, match) =>
    template
      .replace('{$competitor1}', $vendor(match.homeId, match.homeName))
      .replace('{$competitor2}', $vendor(match.awayId, match.awayName))
)

// 상위 합성
export const marketName = derived(
  [vendorMessage, replaceCompetitors],
  ([$vendor, $replace]) => (key, defaultValue, match) => { /* ... */ }
)
```

실제로는 이런 합성 derived가 6~7개 있다(`marketName`, `outcomeName`, 변형 몇 개, `highlight` 등). 전부 `LANG_STORE`에 궁극적으로 의존하니 **언어 변경 1번이 그래프 전체를 자동 갱신**한다.

> **인사이트.** derived 합성은 "의존 그래프"를 선언적으로 표현한다. 새 치환 함수를 추가해도 그래프 끝에 노드 하나 달면 된다. 명령형이었다면 "A 갱신, 그다음 B 갱신..." 같은 순서 관리 코드가 붙었을 것이다.

### 미번역 키 감지

치환 후에도 `{...}` placeholder가 남아 있으면 raw가 화면에 노출된다. 모든 derived 끝에 `hasLeftoverPlaceholder` 가드를 붙여 남아 있으면 `defaultValue`로 fallback. 번역 키 누락이나 placeholder 불일치가 있어도 깨진 문자열이 직접 노출되진 않는다.

---

## 백엔드 — 응답 시점 계산을 캐시 시점으로

백엔드는 13개 로케일 × 수백 개 키를 요청마다 조립하는 구조에서, **로케일별 `Map`을 캐시가 유지**하는 구조로 바꿨다.

```java
// 개념 설명용 의사코드
class LanguageCache extends ReloadableKeyedCache<...> {
    private Map<Locale, Map<String, String>> perLocale = new HashMap<>();

    protected List<LangRow> loadFromRepo() {
        List<LangRow> rows = repo.findAll();
        writeLockJob(() -> {
            perLocale.clear();
            for (LangRow r : rows)
                for (Locale loc : Locale.values())
                    perLocale.computeIfAbsent(loc, k -> new HashMap<>())
                             .put(r.getKey(), r.getValue(loc));
        });
        return rows;
    }

    public Map<String, String> get(Locale loc) {
        return readLockJob(() -> perLocale.get(loc));
    }
}
```

요청 시엔 `cache.get(locale)` 한 줄. 응답 객체가 **캐시 안에서 참조로 공유**된다. 요청마다 수백 개 키 × 로케일별 분기를 돌려 `HashMap`을 새로 만들던 로직이 사라졌고 GC 압력이 확 줄었다.

리로드 시 부분 상태가 노출되지 않도록 `ReentrantReadWriteLock`으로 일관성을 잡았다. `ConcurrentMap`만으로는 "clear + 여러 put"의 스냅샷 일관성이 보장되지 않는다 — [캐시 아키텍처](./cache-architecture.md)의 동시성 섹션에 같은 패턴을 더 자세히 풀어뒀다.

외부 벤더 메시지(Betradar 등)는 데이터 소스와 업데이트 주기가 달라서 별도 캐시로 분리했다. 같은 캐시에 묶으면 한쪽 변경에 다른 쪽까지 불필요하게 리로드된다.

---

## 삽질 포인트

**외부 라이브러리와의 키 충돌**. 특정 키 네임스페이스가 라이브러리 내부 예약어와 겹쳐 번역이 엉뚱하게 뜨는 hotfix를 한 번 쳤다. 근본 수정은 앱 키에 prefix를 박아 공간 자체를 분리한 것. 외부 라이브러리와 번역 키 공간을 공유하면 언제든 터진다.

**일본어만 전각 괄호**. 마켓 이름 정리 정규식이 `(`, `)`를 타겟으로 했는데, 일본어 마켓 이름은 전각 `（`, `）`로 들어왔다. 한 정규식으로 다 처리하려다 실패했고 로케일 체크 후 분기했다. "i18n은 문자열 치환이 아니라 **로케일별 파싱 규칙**"이라는 걸 실감한 지점이다. 숫자 구분자, 날짜 포맷, 괄호 — 로케일마다 다 다르다.

---

## 협업

이 시스템은 프론트·백엔드 양쪽을 내가 작업한 드문 케이스였다. 덕분에 **번역 키 네임스페이스를 앱 → 번역팀 → DB → 캐시 → derived까지 한 사람이 설계**할 수 있었다. 결정적이었던 건 번역팀과의 계약이었다 — "키는 앱이 정의, 값은 번역팀이 운영"이라는 경계를 먼저 세웠고, 위치 파악이 쉬운 네이밍(`home.header.title` 같은 점 구분 계층)을 정해서 넘겼다. 이 네이밍이 나중에 키 충돌 이슈를 prefix로 풀 때 기반이 됐다.

어드민팀과의 계약은 **"어떤 테이블이 바뀌었다"를 한 필드로 전달**하는 것. 리스트 UI 변경과 저장 트리거만 어드민이 담당하고, 캐시 내부는 내가 맡았다. 이 계약을 MQ 단계에서 단순히 유지한 덕에 캐시 종류가 늘어나도 어드민은 건드리지 않아도 됐다.

PR 리뷰에서는 **치환 파이프라인 의존 그래프**를 직접 그려 올렸다. derived가 어떻게 합성되는지 코드만으로는 파악이 어려워서, 화살표 다이어그램으로 "이 derived는 무엇에 의존하는가"를 한 장으로 보여줬다.

---

## 지금 보면

Svelte 5의 rune(`$derived`)을 쓰면 합성이 더 깔끔해진다는 건 명확하다. 더 의미 있는 회고는 다른 지점에 있다.

**번역 키 관리를 코드에서 완전히 분리하지 못한 것**. 당시엔 "키는 앱이 정의"라고 선을 그었지만 결과적으로 코드에 상수 문자열로 키가 박혔다. 번역 키를 타입 시스템으로 뽑아내서 "존재하지 않는 키를 참조하면 컴파일 에러"가 되도록 했다면, 키 누락 버그가 prod에 올라가는 경로 자체가 닫혔을 것이다. 다음에 같은 문제를 풀면 **빌드 타임에 키를 검증하는 파이프라인**을 먼저 세울 것 같다.

**외부 벤더 캐시의 데이터 동기화 전략**. 외부 공급사 데이터 업데이트 주기를 깊게 파악하지 않고 "다르니까 분리"까지만 했다. 실제로는 공급사 업데이트 이벤트를 받는 웹훅이나 스케줄 기반 폴링 중 어느 쪽이 맞는지를 운영 중에 자꾸 조정했다. 설계 단계에서 공급사 API 계약을 더 파고들었으면 이 흔들림을 줄일 수 있었다.

---

## 관련 문서

- [Ehcache 캐시 설계](./cache-architecture.md) — 같은 리로드 캐시 기반 + MQ 전파 구조
