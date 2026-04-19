# 어드민 슬롯 에셋 비동기 일괄 동기화 — 전략 패턴 + 진행 추적

**진행 기간**: 2025.08

운영 슬롯이 수십 개로 늘어나면서 **슬롯 아이콘 / 심볼 아이콘 에셋**을 FTP에 올리고 오브젝트 스토리지에 반영하는 작업이 병목이 됐다. 기존엔 파일을 손으로 FTP에 올리고 개별 슬롯 단위로 동기화 API를 치는 방식이었는데, 슬롯이 늘면 선형으로 작업 시간이 증가했다. 전체 슬롯을 대상으로 **한 번의 API 호출로 백그라운드 병렬 동기화**를 돌릴 수 있게 만든 과정과 설계 포인트를 정리한다.

---

## 요구사항의 결

이 기능이 떠오른 배경엔 구체적인 운영 마찰이 있었다.

- **슬롯 수가 많다**: 신규 슬롯이 추가될 때마다 관리자가 한 슬롯씩 동기화 버튼을 눌러야 했다
- **에셋 유형이 다르다**: 슬롯 아이콘(목록 썸네일)은 `slot/icon/XX.png`, 심볼 아이콘은 `slot/<slotId>/symbols/<symbolCode>.png` 식으로 저장 경로 규칙이 다르다
- **수동 업로드가 휴먼 에러를 부른다**: 잘못된 심볼 코드 파일명, 확장자 대소문자 불일치, 불필요한 파일 포함 등
- **장시간 걸린다**: 전체 슬롯 심볼을 순차 처리하면 FTP I/O + 오브젝트 스토리지 업로드 시간이 누적

즉, "전체 슬롯 에셋을 버튼 한 번으로 안정적·병렬로 반영"이 목표였다.

---

## 설계 결정 3가지

### 1. 전략 패턴으로 에셋 유형을 추상화

"슬롯 아이콘"과 "심볼 아이콘"은 공통 구조(FTP → 필터 → 업로드)지만 세부가 다르다 — 소스 디렉토리, 어떤 파일을 받을지 판단 기준, 오브젝트 스토리지 키 규칙. 이걸 전략 인터페이스 하나로 묶었다.

```java
// 개념 설명용 의사코드 (실제 인터페이스)
public interface SlotAssetSyncStrategy {
    boolean accept(FTPFile file);   // 이 파일을 처리할지 여부
    String toKey(String filename);  // ObjectStorage 업로드 키 생성
    String sourceDir();             // FTP에서 읽을 소스 디렉토리
}
```

심볼 아이콘용 구현에서는 "확장자가 `.png`이고, 파일명이 해당 슬롯의 심볼 집합에 속하는가"를 `accept`에서 판단하고, `toKey`에서는 파일명을 파싱해 업로드용 심볼 코드로 **매핑 전략**을 거쳐 최종 키(`slot/<numericId>/symbols/<uploadCode>.png`)를 만든다. 다른 슬롯 유형(슬롯 아이콘 등)은 별도 구현체로 붙이면 FTP 동기화 서비스(`FtpSyncService`)는 건드리지 않아도 된다.

> **인사이트.** 전략 패턴의 실제 이점은 "새 유형을 추가할 때 기존 서비스를 건드리지 않는다"가 아니라, **"기존 유형이 고장 났을 때 영향 반경이 그 전략 안에서 멈춘다"**는 것이었다. 심볼 파일명 규칙이 바뀌어도 서비스 레이어는 같은 인터페이스로 계속 돈다.

### 2. 전용 ThreadPool로 도메인 영향 격리

FTP I/O + 오브젝트 스토리지 업로드는 슬롯 서비스의 핵심 도메인과 무관하다. 이 작업이 Spring 기본 `ApplicationEventMulticaster` 스레드풀이나 공용 `TaskExecutor`를 점유하면 도메인 요청에 지연이 생길 위험이 있다. 전용 executor를 뒀다.

```java
// 개념 설명용 의사코드
@Bean(name = "slotAssetSyncExecutor")
public ThreadPoolTaskExecutor slotAssetSyncExecutor() {
    final ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(2);
    executor.setMaxPoolSize(4);
    executor.setQueueCapacity(10);
    executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
    executor.setWaitForTasksToCompleteOnShutdown(true);
    executor.setAwaitTerminationSeconds(30);
    executor.initialize();
    return executor;
}
```

값을 고를 때 신경 쓴 건 두 가지다.
- **코어 2 / 맥스 4**: 슬롯 수에 비례해 스레드를 찍어내지 않는다. 오히려 병렬도를 좁게 두고 개별 슬롯을 순차에 가깝게 처리한다. 오브젝트 스토리지 쪽 요율(throttling)과 동시 연결 수 제한을 고려한 의도적 제한
- **`CallerRunsPolicy`**: 큐가 찼을 때 요청을 버리거나 예외를 던지는 대신 **호출자 스레드가 직접 작업을 처리**한다. 쉽게 말해 백프레셔 — 너무 몰리면 제출 측이 자연스럽게 느려진다. 에셋 동기화 실패가 전체 업로드 누락으로 이어지면 안 되기에 선택했다.

### 3. `@ConditionalOnProperty`로 환경별 Bean 활성화

슬롯메이커 FTP 연동은 운영/스테이지 환경에서만 동작해야 한다. 개발 환경이나 로컬에서 빈이 생성되면 FTP 연결 실패로 앱이 뜨지 않는다. 관련 Bean 전체에 `@ConditionalOnProperty(name = "nsc.slotmaker.ftp.enabled", havingValue = "true")`를 박았다.

```java
@Service
@ConditionalOnProperty(name = "nsc.slotmaker.ftp.enabled", havingValue = "true")
public class SlotAssetSyncService { ... }

@Configuration
@EnableAsync
@ConditionalOnProperty(name = "nsc.slotmaker.ftp.enabled", havingValue = "true")
public class SlotAssetSyncAsyncConfig { ... }
```

- 기본값이 "비활성화"가 되도록(`havingValue = "true"` 명시) 설계했다. property 누락이 안전한 쪽으로 떨어진다
- 같은 패턴을 다른 글에서도 썼다(어드민 비교/복사의 `@CompareSlotEnabled`). 코드베이스에서 **"프로퍼티 있어야 Bean 생성"** 이라는 룰이 일관되게 적용된다 — [어드민 슬롯 비교/복사](./admin-slot-compare-copy.md)에 관련 내용

> **인사이트.** feature flag 설계에서 가장 중요한 건 **"설정이 없을 때 어느 쪽이 기본값인가"**다. 운영에 영향을 주는 기능일수록 "없음 = 꺼짐"이 맞다. 한 번 잘못 설정된 프로퍼티가 다른 환경에 복사되어도, 기본값 규칙 덕에 최악 시나리오가 "작동 안 함"에 머문다.

---

## 병렬 동기화 + 진행 추적

백그라운드 일괄 동기화는 단일 작업이 아니라 "슬롯 아이콘 1건 + N개 슬롯 각각의 심볼 아이콘"으로 쪼개진다. `CompletableFuture.supplyAsync` + `allOf`로 병렬 조립했다.

```java
// 개념 설명용 의사코드 — 실제 흐름 축약
public String startAllSync() {
    final String taskId = DataKeyGenerator.generateUniqueId();
    final SyncProgress progress = new SyncProgress(taskId, "전체 에셋 동기화");
    progressMap.put(taskId, progress);
    CompletableFuture.runAsync(() -> performBackgroundAllSync(taskId, progress), executor);
    return taskId;
}

private void performBackgroundAllSync(String taskId, SyncProgress progress) {
    progress.updateStatus(IN_PROGRESS);

    final List<CompletableFuture<SyncResult>> futures = new ArrayList<>();
    futures.add(CompletableFuture.supplyAsync(
        () -> ftpSyncService.sync(slotIconAssetSyncStrategy), executor));

    for (SlotGame slot : slotGameRepository.getAllActiveSlots()) {
        futures.add(CompletableFuture.supplyAsync(() -> {
            try {
                return ftpSyncService.sync(createSymbolSyncStrategy(slot));
            } catch (Exception e) {
                log.error("[{}] 심볼 동기화 실패", slot.getGameId(), e);
                return new SyncResult(List.of());  // 개별 실패는 전체 중단 X
            }
        }, executor));
    }

    CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();
    // 결과 집계 + progress 완료 처리
}
```

중요한 설계 세 가지가 녹아 있다.

**(1) API는 즉시 taskId만 반환**. 슬롯 수가 많으면 동기 응답이 수 분 걸릴 수 있다. 클라이언트가 타임아웃을 맞기 전에 taskId로 작업을 구분해 비동기로 돌리고, 어드민 UI는 별도 조회 API(`/progress`)로 상태를 폴링한다.

**(2) 개별 슬롯 실패는 격리된다**. `CompletableFuture.supplyAsync` 람다 안에서 try/catch로 잡아 `SyncResult(List.of())`(빈 결과)을 반환한다. 50개 슬롯 중 1개가 FTP 연결 실패로 죽어도 나머지 49개는 업로드가 완료된다. 실패 로그는 남겨서 재시도 대상을 파악할 수 있게 한다.

**(3) 진행 상태는 `ConcurrentHashMap<String, SyncProgress>`**. 서버 인스턴스가 1대 전제인 단순 구조다. 복수 인스턴스 환경이라면 Redis로 승격해야 하지만, 어드민 기능은 관리자 몇 명만 쓰는 저빈도 작업이라 여기까지는 YAGNI.

---

## 협업이 이 기능을 만들었다

이 기능의 발단은 **슬롯 운영팀의 요청**이었다. 신규 슬롯이 계속 늘면서 에셋 올리는 시간이 실제 업무 병목이 됐고, "버튼 하나로 끝낼 수 있게 해달라"가 원래 요구였다. 어드민 프론트 담당자와는 **"API는 taskId만 돌려주고, 진행률은 별도 엔드포인트로 폴링"**이라는 계약을 먼저 정해서, 프론트가 긴 응답을 기다리는 구조가 만들어지지 않게 했다.

인프라 담당과는 **FTP 접근 권한 + 오브젝트 스토리지 키 규칙**을 합의했다. 슬롯 번호 2자리 + 심볼 코드 소문자 같은 규칙을 문서화해두고, `@ConditionalOnProperty` 토글로 운영 환경에서만 동작하도록 경계를 그어서 다른 환경에 영향이 없도록 했다.

PR 리뷰에서 받은 가장 큰 피드백은 "개별 슬롯 실패 시 나머지는 어떻게 되나"였다. 초안에서는 `CompletableFuture.allOf`가 하나라도 예외가 나면 전체 실패로 흘러갔다. 리뷰 과정에서 "하나 실패했다고 전체를 다시 돌리면 안 된다"는 합의를 거쳐, 각 람다 내부에서 try/catch로 격리하는 현재 구조가 됐다.

---

## 지금 보면

**진행 상태를 메모리로 둔 건 제약이 있다.** `ConcurrentHashMap`이라 서버 재시작 시 진행 중 작업 정보가 사라진다. 관리자 화면에서 "어제 돌린 전체 동기화 결과는 뭐였지"를 다시 보려면 로그를 뒤져야 한다. 설계 단계에서 "비낙관 경로(서버 재시작)"를 고려했다면 DB나 Redis로 진행 이력을 남겼을 것이다. 이 도메인에서는 저빈도라 실제 문제로 번지진 않았지만, 유사 패턴을 다른 기능에서 재사용할 땐 먼저 잡아둘 부분이다.

**`CallerRunsPolicy`의 트레이드오프를 명시하지 않았다.** 큐가 가득 찼을 때 호출자 스레드로 작업이 넘어가는 건 백프레셔 관점에선 좋지만, 호출자가 HTTP 요청 처리 스레드였다면 어드민 API 응답이 늘어질 수 있다. 현재는 비동기 진입점(`runAsync`) 뒤에 숨어 있어 문제가 없지만, 이 executor를 다른 곳에서 재사용하면 예상 못한 지연이 생길 여지가 있다. 재사용 시에는 이 특성을 주석으로 남겨야 한다.

---

## 관련 문서

- [어드민 슬롯 비교/복사](./admin-slot-compare-copy.md) — 같은 `@ConditionalOnProperty` 기반 환경별 활성화 패턴
- [슬롯 엔진 추상화](./slot-engine-abstraction.md) — `StampedLock` 기반 정적 데이터 리로드와 대조되는 비동기 처리 관점
