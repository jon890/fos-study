# NSC 슬롯팀 업무 기록

**회사**: NHN | **팀**: NSC슬롯개발팀

슬롯 게임 플랫폼에서 진행한 주요 업무를 정리한 문서 모음. (2024.06 ~ 2025.11)

> 내부 운영 중인 슬롯 상품명은 공개하지 않고, 메커닉 조합으로 일반화해서 표기한다.

---

## 문서 목록

### 신규 구현

| 기간              | 업무                                                             | 문서                                                                     |
| ----------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 2024.06 ~ 2024.12 | Slot 21 — 클러스터 + 텀블링 + 머지 슬롯                           | [slot-21-cluster-tumbling-merge.md](slot-21-cluster-tumbling-merge.md)   |
| 2024.07 ~ 2024.12 | Admin 슬롯 비교/복사 — Alpha ↔ Real 환경 동기화                  | [admin-slot-compare-copy.md](admin-slot-compare-copy.md)                 |
| 2024.10 ~ 2024.12 | Slot 33 — 링크게임 + 디스크 배수 + 홀드&스핀                      | [slot-33-linkgame-disk-multiplier.md](slot-33-linkgame-disk-multiplier.md) |
| 2024.12           | BuyFeature 티켓 & 시나리오 스핀 — 플랫폼 공통 기능               | [buyfeature-ticket-scenario-spin.md](buyfeature-ticket-scenario-spin.md) |
| 2025.02 ~ 2025.08 | 신규 슬롯 5종 — 라인/빙고/웨이(243) 메커닉 + AI 에이전트 협업     | [new-slot-games.md](new-slot-games.md)                                   |
| 2025.07 ~ 2025.10 | RCC (RTP Cache Control) — RTP 편차 보정을 위한 백그라운드 결과 생성 시스템 | [rcc-rtp-cache-control.md](rcc-rtp-cache-control.md)                     |
| 2025.08           | 어드민 슬롯 에셋 비동기 일괄 동기화 — 전략 패턴 + 진행 추적       | [admin-asset-async-sync.md](admin-asset-async-sync.md)                   |

### 아키텍처 개선

| 기간              | 업무                                                               | 문서                                                     |
| ----------------- | ------------------------------------------------------------------ | -------------------------------------------------------- |
| 2024.06 ~ 2025.10 | 슬롯 테스트 공통 템플릿 — 단위→통합 전환, AbstractSlotTest         | [slot-test-template.md](slot-test-template.md)           |
| 2025.04 ~ 2025.11 | AI 개발 도구 도입 — Cursor Rules 20종 이상, 에이전트 협업          | [ai-tool-adoption.md](ai-tool-adoption.md)               |
| 2025.08 ~ 2025.10 | 시뮬레이터 공통 템플릿 — ReactiveSimulator, 8종 전환               | [simulator-template.md](simulator-template.md)           |
| 2025.09           | 전역 개인화 데이터 — 베팅 인덱스 독립 구조 설계                    | [global-personal-data.md](global-personal-data.md)       |
| 2025.09 ~ 2025.10 | 슬롯 엔진 추상화 — SlotTemplate, BaseSlotService, ExtraConfig 분리 | [slot-engine-abstraction.md](slot-engine-abstraction.md) |
| 2024.06 ~ 2025.11 | 슬롯 아키텍처 점진 정리 — SpinOperationHandler 도입 + static 해체 1년 여정 | [slot-architecture-evolution.md](slot-architecture-evolution.md) |
| 2025 하반기       | 슬롯 페이 조건 체크 Factory — 제네릭 체커 + 런타임 타입 디스패치       | [slot-payment-factory.md](slot-payment-factory.md)       |
| 2025 하반기       | 슬롯 당첨 계산 Decorator 체인 — 우선순위 기반 누적 변환                | [slot-win-decorator-chain.md](slot-win-decorator-chain.md) |

### 트러블슈팅

| 기간              | 업무                                                                     | 문서                                                             |
| ----------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| 2025.01 ~ 2025.02 | 스핀 성능 최적화 — AliasMethod O(1), SecureRandom → ThreadLocalRandom    | [slot-spin-performance.md](slot-spin-performance.md)             |
| 2025.02           | 시뮬레이터 OOM — List<Long> 제거, Welford's Online Algorithm 도입        | [slot-simulator-oom.md](slot-simulator-oom.md)                   |
| 2025.09           | 시뮬레이터 잭팟 풀 ThreadLocal 버그 — 공유 상태를 AtomicReference로 전환 | [slot-simulator-jackpot-pool.md](slot-simulator-jackpot-pool.md) |

---

## 기간별 주요 업무

### 2024 하반기 (6월 ~ 12월) — 합류 첫 해

- **Slot 21 (클러스터 + 텀블링 + 머지)** 개발: 텀블링 중복 처리, 클러스터 머지 위치 결정, 와일드 스프레드 원본·파생 분리
- **Admin 슬롯 비교/복사**: Alpha ↔ Real 환경 데이터 비교 및 복사 기능
- **Slot 33 (링크게임 + 디스크 배수 + 홀드&스핀)** 개발: 고정/신규 심볼 공존 상태 관리, 이벤트 리스너 기반 위치 추적, 하드 캡 밸런싱
- **BuyFeature 티켓**: 티켓 기반 피처 구매, 시나리오 스핀 플랫폼 통합

### 2025 상반기 (1월 ~ 6월)

- **스핀 성능 최적화**: AliasMethod 적용, ThreadLocalRandom 전환
- **시뮬레이터 OOM 해결**: List<Long> winmoneyList → Welford's Online Algorithm
- **Slot 36 (라인 + 코인 레벨링)** 개발: 코인 레벨링 시스템, 시뮬레이터
- **Slot 38 (라인 + AnyBar 심볼)** 개발: 페이라인, AnyBar 심볼 우선순위
- **Slot 44 (라인 + 프리스핀/리트리거)** 개발: 프리스핀 진입 조건, 리트리거, AI 에이전트 협업
- **Slot 41 (빙고 메커니즘)** 개발: 빙고 보드 상태 관리, AI 에이전트 협업
- **Cursor Rules 구축 시작**: 슬롯 도메인 컨텍스트 문서화

### 2025 하반기 (7월 ~ 11월)

- **Slot 47 (웨이(243) + Sync Reel)** 개발: 동기화 릴 구현, AI 에이전트 협업
- **RCC 시스템 구축**: RTP Cache Control, 슬롯 6종 대응, 동시성 처리
- **시뮬레이터 공통 템플릿**: 8종 전환, 잭팟풀 스레드 버그 수정
- **전역 개인화 데이터**: 베팅 인덱스 독립 구조 설계 + 마이그레이션
- **슬롯 엔진 추상화**: SlotTemplate, BaseSlotService, ExtraConfig 분리, BuyFeature 파싱 통합
- **테스트 공통 템플릿**: AbstractSlotTest, JUnit5 Extension, 치트 데이터 기반 확정적 테스트

---

## 기술 키워드

`Spring Boot 3.x` `Java 17` `MySQL` `Redis` `JPA` `Project Reactor`
`슬롯 게임 엔진` `RTP` `시뮬레이터` `StampedLock` `Cursor Rules` `AI 에이전트 협업`
