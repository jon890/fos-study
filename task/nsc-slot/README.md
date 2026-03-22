# NSC 슬롯팀 업무 기록

슬롯 게임 플랫폼에서 진행한 주요 업무를 정리한 문서 모음.

---

## 업무 목록

| 기간 | 업무 | 문서 |
|------|------|------|
| 2025.02 ~ 2025.08 | 신규 슬롯 게임 5종 개발 (Slot 36, 38, 41, 44, 47) | [new-slot-games.md](new-slot-games.md) |
| 2025.04 ~ 2025.11 | AI 개발 도구 도입 및 Cursor Rules 구축 | [ai-tool-adoption.md](ai-tool-adoption.md) |
| 2025.07 ~ 2025.10 | RCC (RTP Cache Control) 시스템 설계 및 구축 | [rcc-rtp-cache-control.md](rcc-rtp-cache-control.md) |
| 2025.08 ~ 2025.10 | 시뮬레이터 공통 템플릿 도입 (8종 전환) | [simulator-template.md](simulator-template.md) |
| 2025.09 | 전역 개인화 데이터 구조 설계 | [global-personal-data.md](global-personal-data.md) |
| 2025.09 ~ 2025.10 | 슬롯 엔진 추상화 및 구조 개선 | [slot-engine-abstraction.md](slot-engine-abstraction.md) |

---

## 기간별 주요 업무

### 2025 상반기 (1월 ~ 6월)

- **Slot 36 (Magic Circus)** 개발: 코인 레벨링 시스템, 시뮬레이터
- **Slot 38 (Classic Diamonds)** 개발: 페이라인, AnyBar 심볼
- **Slot 44 (Fortune Blessing)** 개발: 프리스핀/리트리거, AI 에이전트 협업
- **Slot 41 (Bingoing)** 개발: 빙고 메커니즘, AI 에이전트 협업
- **Cursor Rules 구축 시작**: 슬롯 도메인 컨텍스트 문서화

### 2025 하반기 (7월 ~ 11월)

- **Slot 47 (Boogie Turkey)** 개발: Sync Reel 기능, AI 에이전트 협업
- **RCC 시스템 구축**: RTP Cache Control, 슬롯 6종 대응, 동시성 처리
- **시뮬레이터 공통 템플릿**: 8종 전환, 잭팟풀 스레드 버그 수정
- **전역 개인화 데이터**: 베팅 인덱스 독립 구조 설계 + 마이그레이션
- **슬롯 엔진 추상화**: SlotTemplate, BaseSlotService, ExtraConfig 분리, BuyFeature 파싱 통합

---

## 기술 키워드

`Spring Boot 3.x` `Java 17` `MySQL` `Redis` `JPA` `Project Reactor`
`슬롯 게임 엔진` `RTP` `시뮬레이터` `Cursor Rules` `AI 에이전트 협업`
