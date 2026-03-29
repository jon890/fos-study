# 추천 프로그램(Referral) 시스템 설계

**진행 기간**: 2023.10 ~ 2024.02

스포츠 베팅 플랫폼에서 추천인 보너스 프로그램을 처음부터 설계하고 구현했다. 단순히 "A가 B를 추천하면 보상"이 아니라, 피추천인의 베팅 실적에 따라 포인트가 쌓이고 미션 달성 시 블록체인 토큰(BYLO)으로 보상받는 구조였다. 그 과정에서 설계 결정들을 정리해둔다.

---

## 전체 구조

추천 시스템은 두 레이어로 구성된다.

**1. 기본 추천 (1:1 연결)**
- A가 B의 닉네임을 입력해 추천인으로 등록
- A는 등록 즉시 LuckyBall 보상 수령
- B의 베팅 조건 충족 후 A에게 추가 보상

**2. 추천 보너스 프로그램 (미션 기반)**
- 이벤트 단위로 운영되는 별도 프로그램
- B(팔로워)의 베팅 실적만큼 A에게 포인트 적립
- 포인트가 미션 기준치 도달 시 BYLO 토큰 클레임 가능

```
A (추천인) ─── 추천 ──▶ B (피추천인)
     │                       │
     │  포인트 적립 ◀── B가 베팅할 때마다
     │
     ▼
미션 달성 → 클레임 생성 → QR 서명 → 완료
```

---

## DB 설계

### td_event_recommend (기본 추천 관계)

```java
@Entity
@Table(name = "td_event_recommend")
public class UserRecommend extends UserRecommendSchema {

    @OneToOne(optional = false)
    @JoinColumn(name = "mbr_no")
    private UserAccount user;       // 추천 받은 사람

    @OneToOne
    @JoinColumn(name = "recommend_mbr_no")
    private UserAccount recommendUser;  // 추천한 사람

    // recommenderRewardStatus: NOT(한도 초과), YET(대기), OK(완료)
}
```

추천인이 받을 수 있는 보상 한도는 이벤트 설정값(`apply3`)으로 관리한다. 팔로워가 한도를 초과하면 `RewardStatus.NOT`으로 처리해 보상이 나가지 않는다.

```java
Long followerCount = userRecommendRepository.countByRecommendUser(recommendUser);
if (followerCount > recommendEvent.getApply3()) {
    userRecommend.setRecommenderRewardStatus(RewardStatus.NOT);
} else {
    userRecommend.setRecommenderRewardStatus(RewardStatus.YET);
}
```

### td_user_recommend_program (미션 진행 상태)

미션 완료 여부를 `MissionStatus` 임베디드 객체로 저장한다. 미션 seq를 최대 20개 컬럼에 순서대로 기록한다.

```java
public void completeMission(Long missionSeq) {
    if (this.missionStatus == null) {
        this.missionStatus = new MissionStatus();
    }
    if (this.missionStatus.getMissionCompleteSeq1() == null) {
        this.missionStatus.setMissionCompleteSeq1(missionSeq);
        return;
    }
    // ... seq2 ~ seq20 동일
    throw new IllegalStateException("추천 미션은 최대 20개 까지 수행 가능합니다");
}
```

처음에는 별도 완료 테이블을 두는 방식도 고려했는데, 미션 수가 고정적이고 조회 시 조인이 없어도 되는 구조가 낫겠다고 판단해 이 방식으로 정했다. 다만 미션 수 제한이 하드코딩되는 건 아쉬운 부분이다.

---

## 캐시 설계

추천 프로그램 목록은 요청마다 DB를 치지 않도록 인메모리 캐시를 뒀다.

```java
@Component
public class RecommendProgramCache extends AbstractStaticKeyReloadable<Event.RecommendProgramEvent, Long> {

    @Override
    protected List<Event.RecommendProgramEvent> loadFromRepo() {
        return repository.findAllByTypeAndActiveOrderByEndDateDesc(
                EventSchema.EventType.RECOMMENDER_BONUS_PROGRAM, ACTIVE)
                .stream()
                .map(Event::toRecommendProgramEvent)
                .collect(Collectors.toList());
    }
}
```

`AbstractStaticKeyReloadable`는 MQ(DataTable) 메시지를 받으면 캐시를 새로 로드하는 구조다. 어드민에서 프로그램을 수정하면 메시지가 발행되고, 백엔드가 이를 수신해 캐시를 갱신한다.

유저에게 프로그램 목록을 내려줄 때는 캐시에서 시작 날짜가 지난 것만 필터링하고, 보상 수령 가능 여부도 함께 계산해서 응답한다.

```java
List<Event.RecommendProgramEvent> cachedPrograms = recommendProgramCache.list()
        .stream()
        .filter(event -> event.getStartDate().isBefore(now) || event.getStartDate().isEqual(now))
        .collect(Collectors.toList());
```

---

## 클레임 플로우 (블록체인 연동)

미션 달성 보상은 BYLO 토큰으로 지급되는데, 블록체인 특성상 단순 지급이 아니라 지갑 서명이 필요하다. 그래서 3단계 구조로 설계했다.

```
1. 클레임 생성 (createIfNotExistClaimForMission)
   → ByloClaim 레코드 저장 (claimDate = null)
   → claimId 반환

2. QR 코드 서명 (wemix 지갑)
   → 프론트에서 claimId로 QR 생성
   → 유저가 wemix 지갑 앱으로 서명

3. 클레임 완료 (completeMission)
   → byloClaim.claimDate 가 채워졌는지 확인
   → 완료 처리 후 program에 미션 seq 기록
```

```java
@Transactional
public void completeMission(Long mbrNo, Long eventSeq, Long missionSeq, Long claimId) {
    // ...
    ByloClaim byloClaim = byloClaimRepository.findById(claimId)
            .orElseThrow(() -> new ContentsException(ErrorCode.NOT_FOUND_CLAIM));

    // claimDate 없으면 QR 서명 미완료
    if (byloClaim.getClaimDate() == null) {
        throw new ContentsException(ErrorCode.REMAIN_RECOMMEND_MISSION_REWARD);
    }

    userRecommendProgram.completeMission(missionSeq);
    userRecommendProgram.addClaimAmount(mission.getRewardAmount());
}
```

중간에 이중 처리 방어 로직을 넣는 게 꽤 신경 쓰였다. 클레임이 이미 완료됐는데 다시 완료 요청이 들어오는 경우를 `createIfNotExistClaimForMission`에서 처리했다.

```java
// claim이 이미 완료됐는데 다시 요청이 들어올 경우
if (byloClaim.getClaimDate() != null) {
    userRecommendProgram.completeMission(missionSeq);
    userRecommendProgram.addClaimAmount(mission.getRewardAmount());
    return new RecommendBonusProgramClaimResponseDto(claimId, false);
}
```

---

## 샤딩 처리

유저 데이터는 샤딩된 DB에 분산 저장되어 있어서, 유저별 추천 프로그램 데이터 조회 시 항상 샤드 ID를 먼저 확인하고 컨텍스트를 전환해야 했다.

```java
UserAccount user = userService.getUserAccount(mbrNo);
DatabaseContextHolder.useShardDB(user.getShardId());

UserRecommendProgram userRecommendProgram =
    userRecommendProgramRepository.findByEventSeqAndMbrNoWithLock(eventSeq, mbrNo)
        .orElseThrow(() -> ...);
```

락을 잡고 조회하는 이유는 동시에 같은 미션을 완료 처리하는 경우를 막기 위해서다.

---

## 관련 문서

- [wemix 지갑 연동](./wemix-wallet-integration.md)
- [Ehcache 캐시 설계](./ehcache-whitelist-cache.md)
