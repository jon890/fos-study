# 이력서 — 토스뱅크 Server Developer (Product)

**김병태** | Server Developer · Java / Spring · 7년 2개월
jon89071@gmail.com · 010-2753-2647 · [github.com/jon890](https://github.com/jon890)

---

## Summary

Java/Spring 기반 서버 개발자로 **스포츠 베팅 백엔드, P2P 거래소 매칭 엔진, 슬롯 게임 백엔드** 등 금융 메커니즘과 유사한 복잡도의 서비스를 설계·구현해왔습니다. 분산 환경에서 데이터 정합성 문제를 구조적으로 해결하는 것을 중요하게 생각합니다 — MQ Fanout으로 다중 서버 캐시 동기화를 설계하거나, Redis Streams 순서 보장으로 체결 경쟁 조건을 락 없이 제거하는 방식입니다. 최근에는 AI 서비스 개발팀으로 이동해 **AI RAG 시스템**을 구현하고, Cursor Rules 20종과 Dooray MCP 서버를 직접 제작해 **개발 기간 25% 단축**하는 개발 플로우를 팀 내에 정립했습니다.

---

## Experience

### NHN — AI 서비스 개발팀 `2025.12 ~ 현재`
Java 21 · Spring Boot 3 · Spring Batch · OpenSearch
> 사내 AI 플랫폼 **AI Playground** — 임직원이 사내 지식 베이스를 AI로 검색·질의할 수 있는 ChatGPT형 서비스

- Confluence 문서를 OpenSearch에 벡터 색인하는 **11-Step Spring Batch RAG 파이프라인** 설계·구현. 스페이스당 수천 개 문서를 Step별로 격리해 중간 실패 시 해당 Step부터 재시작 가능하도록 설계
- `AsyncItemProcessor` + `AsyncItemWriter`로 임베딩 API 병렬 처리 — 동기 방식 대비 청크 내 I/O 대기 시간을 병렬로 처리
- 수천 개 페이지 ID를 `JobExecutionContext`에 저장해 매 청크 커밋마다 DB에 직렬화되는 문제 직접 발견 → `@JobScope` 인메모리 홀더로 전환해 불필요한 DB 부하 제거
- **`@BatchComponentTest` 테스트 어노테이션 설계** — 외부 서비스 의존을 별도 Test Config로 분리해 Mock 교체 시 Spring Test Context 재생성 없이 처리. 빈 설정·Qualifier 충돌을 빌드 타임에 검출하도록 팀 테스트 인프라 표준화

### NHN — 슬롯 AI TF `2025.04 ~ 2025.11`
Cursor · Claude Code · Gemini CLI · Codex · MCP
> NSC 슬롯 개발팀 내 AI 에이전트 개발 생산성 도구 구축

- **AI 에이전트와의 대화만으로 슬롯 3종 구현** — 구현 과정에서 부족한 컨텍스트를 파악하며 Cursor Rules를 지속 고도화. 결과적으로 **20종 이상의 Rules**가 축적되어 다른 팀원도 Rules 파일만으로 신규 슬롯 제작 가능한 환경 구축
- **Dooray MCP 서버 자체 제작** — 사내 협업 도구(Dooray)와 코딩 에이전트를 연결하는 창구 구축. *기획서 읽기 → 1차 Rules 생성 → 슬롯 코드 제작 → 구축된 테스트 환경으로 1차 검증*으로 이어지는 AI 기반 개발 플로우 정립
- **슬롯 서버 개발 기간 4주 → 3주, 25% 단축**

### NHN — NSC 슬롯 개발팀 `2024.06 ~ 2025.11`
Java 17 · Spring Boot 3.5 · MySQL · Redis · JPA · Project Reactor
> 소셜카지노 **페블시티** 게임 백엔드 개발

- **슬롯 엔진 추상화** — 5종 이상 슬롯의 반복 패턴을 팀에 제안하고 자발적으로 설계. `SlotTemplate`·`BaseSlotService` 분리로 신규 슬롯 추가 시 페이 계산 재구현 불필요
- **스핀 성능 최적화** — 가중치 랜덤 O(n)→O(1) (Alias Method) 교체, `SecureRandom`→`ThreadLocalRandom` 전환. **JMH 실측 약 58배 처리량 향상**. `ThreadLocalRandom`을 필드로 저장하던 실제 운영 동시성 버그도 함께 발견·수정
- **시뮬레이터 OOM 해결 (어려운 과제 극복)** — 4인 동시 실행 시 반복되던 OOM의 근본 원인 추적. 1억 스핀 × 8B = 800MB/회 누적하던 `List<Long>` 구조를 Welford's Online Algorithm(스칼라 3개, 20B)으로 교체해 메모리 선형 증가 구조 제거. 문제를 회피하지 않고 알고리즘 수준까지 파고들어 근본 원인을 제거한 경험
- **슬롯 테스트 인프라 구축** — `AbstractSlotTest` 설계. 치트 데이터 기반 확정적 단위 테스트로 팀 전체 테스트 생산성 향상

### NHN — SB 개발팀 `2023.01 ~ 2024.03`
Java 11 · Spring Boot 2.6 · Ehcache · RabbitMQ · Azure Service Bus
> 스포츠 베팅 서비스 **Bylo Sports** 풀스택 개발

- 다중 서버 환경에서 어드민 변경 시 특정 서버만 캐시가 갱신되는 정합성 문제 → **MQ Fanout 구조** 설계. RabbitMQ/Azure Service Bus 이중화를 `DataPublisher` 인터페이스로 추상화해 환경 무관하게 동일 동작 보장
- 각 캐시마다 중복 구현되던 리로드·락 로직을 **`AbstractStaticReloadable` 추상 기반 클래스**로 표준화. `ReentrantReadWriteLock`으로 리로드 중 불완전 데이터 노출 차단
- **샤딩 DB 환경 동시성 제어** — 유저 데이터가 샤드별로 분산 저장된 환경에서 샤드 ID 기반 컨텍스트 전환 후 조회. 동시 요청으로 인한 중복 처리를 막기 위해 비관적 락 적용
- KYC 인증 시스템 구현 — 신분증 이미지 Azure Blob 저장, 개인정보보호법 준수 6개월 자동 삭제 Spring Batch 배치

### 더퓨쳐컴퍼니 `2022.02 ~ 2022.11`
NestJS · TypeScript · Redis Streams · Redis JSON · RediSearch

- **P2P 게임 아이템 거래소 엔진** 설계·구현 — 동시 주문 유입 시 체결 경쟁 조건을 Lock/트랜잭션 대신 Redis Streams 순서 보장 + Redis 플래그 직렬화 게이트로 구조적 해결. Price-Time Priority 체결, 부분 체결(Partial Fill), 잔량 등록(Resting Order) 구현
- **금액 정밀 연산** — 전체 가격·수량 연산에 Decimal.js 정밀 연산 적용. 부동소수점 오차로 인한 체결 금액 불일치(유저 신뢰 손실) 원천 차단
- CQRS 구조: 주문 접수(Pub) → 체결(Sub) → 호가창 조회(캐시 서빙) 3레이어 분리 — 체결 처리 지연이 주문 접수 HTTP 응답에 무영향
- RDB 영속성 구성으로 프로세스 재시작 시 거래 주문 데이터 유실 방지

### 엠씨에스텍 (프리랜서) `2021.08 ~ 2022.01`
Java · Spring Boot · MySQL · Caffeine Cache

- 공공기관(한전KDN) 헬스케어 앱 백엔드 1인 전담 — 아키텍처 설계부터 배포까지
- DB 프로시저 의존 비즈니스 로직을 애플리케이션 레벨로 전환 — 유지보수성 향상

### 엠씨에스텍 `2018.08 ~ 2020.12`
Java · Spring MVC · Oracle · TCP/IP Socket

- 동시 50건 한계였던 SMS 발송 로직 개선 — 동시 500건, 10배 처리량 향상
- TCP/IP 소켓 통신 기반 전기차 충전기 프로토콜 실시간 검증기 구현

---

## Key Projects

### P2P 거래소 매칭 엔진 — 금융 정합성과 동시성
*더퓨쳐컴퍼니 · 2022.08*

> 게임 내 플레이어 간 아이템 직거래 거래소 — 실제 주식 거래소와 동일한 지정가 주문(limit order) 방식. 금액 정확성·동시성·데이터 유실 방지가 핵심 요구사항이었다.

- **금액 정밀 연산**: 전체 체결 연산에 Decimal.js 적용 — 부동소수점 오차로 인한 금액 불일치 원천 차단. "미세한 숫자 하나가 유저 신뢰를 무너뜨린다"는 금융 시스템 원칙을 직접 체득
- **동시성을 구조로 해결**: DB Lock·트랜잭션 대신 Redis Streams 순서 보장 + Redis 플래그 직렬화 게이트 — 락 경합 자체를 발생하지 않는 구조. 호가창과 체결 상태의 정합성 보장
- **CQRS**: 주문 접수(Pub) → 체결(Sub) → 호가창 조회(캐시) 3레이어 분리. 체결 처리 지연이 주문 접수 HTTP 응답에 무영향. 토스뱅크 코어뱅킹의 동기/비동기 분리 패턴과 유사한 설계
- **왜 Redis Streams인가**: Kafka 대비 단순한 인프라. Consumer Group으로 미전달 메시지 보장, 스트림 자체가 주문 이력 로그. 단일 Redis로 큐·저장·검색을 통합해 인프라 복잡도 최소화

---

### 개발 환경 점진적 개선 + AI 도입
*NHN 슬롯팀 · 2024.06 ~ 2025.11*

> 신규 슬롯을 반복해서 만들며 코드의 문제를 직접 체감했고, 그때그때 구조를 개선해왔다. 아키텍처 추상화 → 테스트 인프라 → AI 도입으로 이어지는 흐름이 자연스럽게 형성됐다.

- **아키텍처 추상화**: 슬롯 6종을 직접 구현하며 페이 계산·공통 로직이 반복된다는 것을 파악. `SlotTemplate`·`BaseSlotService`로 추상화 제안·설계. 충분한 반복 후에 추상화했기 때문에 경계가 명확했다
- **어려운 과제 극복 — OOM 해결**: 4인 동시 실행 시 반복되던 OOM을 근본 원인까지 추적. 1억 스핀 × 8B = 800MB/회 누적하던 `List<Long>` 구조를 Welford's Online Algorithm(스칼라 3개, 20B)으로 교체해 메모리 선형 증가 구조 자체를 제거
- **AI 도입**: 구축된 도메인 지식을 Cursor Rules로 체계화(20종+), Dooray MCP 서버로 기획서를 에이전트에 직접 연결. *기획서 → Rules 생성 → 코드 제작 → 테스트 검증*의 플로우 정립. **개발 기간 4주 → 3주, 25% 단축**

---

### MQ Fanout 기반 다중 서버 캐시 정합성
*NHN SB개발팀 · 2023.01*

> 어드민에서 데이터를 변경했을 때 여러 서버 인스턴스 중 일부만 캐시가 갱신되어 유저가 서버마다 다른 데이터를 보는 문제. 로컬 캐시(Ehcache)의 한계였다.

- **왜 MQ Fanout인가**: 변경 이벤트를 모든 인스턴스에 브로드캐스트. Pub/Sub 방식으로 새 인스턴스가 추가돼도 설정 변경 불필요. Redis Pub/Sub 대신 MQ를 선택한 이유 — 메시지 지속성과 재처리 보장이 필요했기 때문
- RabbitMQ/Azure Service Bus 이중화를 `DataPublisher` 인터페이스로 추상화 — 인프라 변경 시 애플리케이션 코드 수정 불필요
- `AbstractStaticReloadable`로 리로드·락 로직 표준화. `ReentrantReadWriteLock`으로 리로드 중 불완전 데이터 노출 차단

---

## Tech Stack

| 분류 | 기술 |
|---|---|
| 언어 | Java 17/21, TypeScript |
| 프레임워크 | Spring Boot 3.5, Spring Batch, JPA/Hibernate, QueryDSL, NestJS |
| 데이터 & 메시징 | MySQL, Redis (Streams/JSON/Search), OpenSearch, RabbitMQ, Azure Service Bus |
| 동시성 & 테스트 | ReentrantReadWriteLock, AtomicReference, JMH, JUnit 5, spring-batch-test |
| AI 도구 | Cursor (Rules 20+), Claude Code, Gemini CLI, Codex, MCP Server |

---

## 학력

**전남대학교** `2012.03 ~ 2019.02`
수학 전공 · 소프트웨어공학 부전공 · 평점 3.18 / 4.5 · 졸업

---

## 자격증 / 기타

- 정보처리기사 (2018.08)
- TOEIC 860 (2017.01)
- GitHub: https://github.com/jon890
