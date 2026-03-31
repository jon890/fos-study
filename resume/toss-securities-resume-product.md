# 이력서 — 토스증권 Server Developer (Product) 지원

> 작성일: 2026-03-31  
> 공고: https://toss.im/career/job-detail?job_id=4071141003&sub_position_id=4076140003&company=%ED%86%A0%EC%8A%A4%EC%A6%9D%EA%B6%8C

---

## 기본 정보

| | |
|---|---|
| **이름** | 김병태 |
| **연락처** | jon89071@gmail.com / 010-2753-2647 |
| **GitHub** | https://github.com/jon890 |
| **경력** | 7년 2개월 |

---

## 요약

Java/Spring 기반 서버 개발자로 **슬롯 게임 백엔드, 스포츠 베팅 백엔드, 거래소 매칭 엔진** 등 다양한 도메인의 서비스를 설계·구현해왔습니다. 반복 코드는 공통 추상화로 정리하는 작업을 자발적으로 추진합니다. 게임, 베팅, 거래소, AI 서비스 등 다양한 도메인을 거치며 각 분야의 핵심 문제를 직접 다뤄왔고, 새로운 기술과 도메인에 빠르게 흥미를 붙이고 깊이 파고드는 것을 즐깁니다. 최근에는 AI 서비스 개발팀으로 이동해 **AI RAG 시스템**을 구현하고, 사내 협업 도구 연동 MCP 서버와 Claude Skills를 직접 제작해 팀 내 반복 작업을 자동화하며 개발 생산성을 높이고 있습니다.

---

## 경력

### NHN — AI 서비스 개발팀 (2025.12 ~ 현재)

Java 21 / Spring Boot 3 / Spring Batch / OpenSearch  
*사내 AI 플랫폼 **AI Playground** — 임직원이 사내 지식 베이스를 AI로 검색·질의할 수 있는 ChatGPT형 서비스*

- Confluence 문서를 OpenSearch에 벡터 색인하는 **11-Step Spring Batch RAG 파이프라인** 설계·구현. 스페이스당 수천 개 문서를 Step별로 격리해 중간 실패 시 해당 Step부터 재시작 가능하도록 설계
- `AsyncItemProcessor` + `AsyncItemWriter`로 임베딩 API 병렬 처리 — 동기 방식 대비 청크 내 I/O 대기 시간을 병렬 처리로 단축
- 수천 개 페이지 ID를 `JobExecutionContext`에 저장해 매 청크 커밋마다 DB에 직렬화되는 문제 직접 발견 → `@JobScope` 인메모리 홀더로 전환해 불필요한 DB 부하 제거
- **`@BatchComponentTest` 테스트 어노테이션 설계** — 외부 서비스 의존을 별도 Test Config로 분리해 Mock 교체 시 Spring Test Context 재생성 없이 처리. 빈 설정·Qualifier 충돌을 런타임이 아닌 빌드 타임에 검출하도록 팀 테스트 인프라 표준화

### NHN — NSC 슬롯 개발팀 (2024.06 ~ 2025.11)

Java 17 / Spring Boot 3.5 / MySQL / Redis / JPA / Project Reactor  
*소셜카지노 **페블시티** 게임 백엔드 개발*

- **신규 슬롯 6종 개발** — 페이 계산(Line/Way/Cluster) 방식이 각각 다른 슬롯을 처음부터 설계·구현. 반복 과정에서 공통 패턴을 직접 파악해 추상화 제안으로 이어짐
- **슬롯 엔진 추상화** — 5종 이상 슬롯의 반복 패턴을 팀에 제안하고 자발적으로 설계. `SlotTemplate`·`BaseSlotService` 분리로 신규 슬롯 추가 시 페이 계산 재구현 불필요
- **슬롯 테스트 인프라 구축** — `AbstractSlotTest` 설계. 치트 데이터 기반 확정적 단위 테스트로 팀 전체 테스트 생산성 향상, 신규 슬롯 개발 시 기반 클래스 상속만으로 핵심 테스트 구성
- **스핀 성능 최적화** — 가중치 랜덤 O(n)→O(1) (Alias Method) 교체, `SecureRandom`→`ThreadLocalRandom` 전환. **JMH 실측 약 58배 처리량 향상**. `ThreadLocalRandom`을 필드로 저장하던 실제 운영 동시성 버그도 함께 발견·수정
- **시뮬레이터 OOM 해결** — 4인 동시 실행 시 반복되던 OOM의 근본 원인 추적. 1억 스핀 × 8B = 800MB/회 누적하던 `List<Long>` 구조를 Welford's Online Algorithm(스칼라 3개, 20B)으로 교체해 메모리 선형 증가 구조 제거

### NHN — 슬롯 AI TF (2025.04 ~ 2025.11)

Cursor · Claude Code · Gemini CLI · Codex · MCP  
*NSC 슬롯 개발팀 내 AI 에이전트 개발 생산성 도구 구축*

- **AI 에이전트와의 대화만으로 슬롯 3종 구현** — 구현 과정에서 부족한 컨텍스트를 파악하며 Cursor Rules를 지속 고도화. 결과적으로 **20종 이상의 Rules**가 축적되어 다른 팀원도 Rules 파일만으로 신규 슬롯을 제작할 수 있는 환경 구축
- **Dooray MCP 서버 자체 제작** — 사내 협업 도구(Dooray)와 코딩 에이전트를 연결하는 창구 구축. 이를 통해 *기획서 읽기 → 1차 Rules 생성 → 슬롯 코드 제작 → 구축된 테스트 환경으로 1차 검증*으로 이어지는 AI 기반 개발 플로우 정립
- **슬롯 서버 개발 기간 4주 → 3주, 25% 단축**

### NHN — SB 개발팀 (2023.01 ~ 2024.03)

Java 11 / Spring Boot 2.6 / Ehcache / RabbitMQ / Azure Service Bus / Kotlin  
*스포츠 베팅 서비스 **Bylo Sports** 풀스택 개발*

- 다중 서버 환경에서 어드민 변경 시 특정 서버만 캐시가 갱신되어 유저가 서버마다 다른 데이터를 보는 정합성 문제 → **MQ Fanout 구조** 설계. RabbitMQ/Azure Service Bus 이중화를 `DataPublisher` 인터페이스로 추상화해 환경 무관하게 동일 동작 보장
- 각 캐시마다 중복 구현되던 리로드·락 로직을 **`AbstractStaticReloadable` 추상 기반 클래스**로 표준화. `ReentrantReadWriteLock`으로 리로드 중 불완전 데이터 노출 차단. 이후 새 캐시 추가 시 `loadFromRepo()`·`tableName()` 2개 메서드만 구현
- KYC 인증 시스템 구현 — 신분증 이미지 Azure Blob 저장, 개인정보보호법 준수 6개월 자동 삭제 Spring Batch 배치
- **샤딩 DB 환경 대응** — 유저 데이터가 샤드별로 분산 저장된 환경에서 샤드 ID 기반 컨텍스트 전환 후 조회. 동시 요청으로 인한 중복 처리를 막기 위해 비관적 락 적용

### 더퓨쳐컴퍼니 (2022.02 ~ 2022.11)

NestJS / TypeScript / Redis Streams / Redis JSON / RediSearch

- **P2P 게임 아이템 거래소 엔진** 설계·구현 — 동시 주문 유입 시 체결 경쟁 조건을 Lock/트랜잭션 대신 Redis Streams 순서 보장 + Redis 플래그 직렬화 게이트로 구조적 해결. Price-Time Priority 체결, 부분 체결(Partial Fill), 잔량 등록(Resting Order) 구현
- 금액 연산 전체에 Decimal.js 정밀 연산 적용 — 부동소수점 오차로 인한 체결 금액 불일치(유저 신뢰 손실) 원천 차단
- RDB 영속성 구성으로 프로세스 재시작 시 거래 주문 데이터 유실 방지
- CQRS 구조로 읽기·쓰기 분리 — 체결 처리 지연이 주문 접수 HTTP 응답에 무영향, 호가창 조회는 in-memory 캐시에서 서빙

### 엠씨에스텍 (프리랜서, 2021.08 ~ 2022.01)

Java · Spring Boot · MySQL · Caffeine Cache

- 공공기관(한전KDN) 헬스케어 앱 백엔드 **1인 전담** — 아키텍처 설계부터 배포까지. 조직도 기반 랭킹·건강 데이터 Batch 시스템 설계
- DB 프로시저 의존 비즈니스 로직을 애플리케이션 레벨로 전환 — 유지보수성 향상
- Caffeine 캐시 도입으로 공통 설정 데이터 반복 조회 성능 개선
- 인사평가 시스템 마이그레이션 참여

### 엠씨에스텍 (2018.08 ~ 2020.12)

Java · Spring MVC · Oracle · TCP/IP Socket · JNI · d3.js

- Struts 기반 레거시 홈페이지 **Spring MVC 마이그레이션** 및 신규 퍼블리싱 적용
- 동시 50건 한계였던 SMS 발송 로직 개선 — **동시 500건, 10배 처리량 향상**
- TCP/IP 소켓 통신 기반 전기차 충전기 프로토콜 실시간 검증기 구현 — JNI 네트워크 메시지 추출 + d3.js 모니터링 대시보드

### Key Projects

#### 1. NHN 슬롯팀 — 개발 환경 점진적 개선 (2024.06 ~ 2025.11)

신규 슬롯을 반복해서 만들며 코드의 문제를 직접 체감했고, 그때그때 구조를 개선해왔다. 아키텍처 추상화 → 테스트 인프라 구축 → AI 도입으로 이어지는 흐름이 자연스럽게 형성됐다.

- **아키텍처 추상화**: 슬롯 6종을 직접 구현하며 페이 계산·공통 로직이 반복된다는 것을 파악. `SlotTemplate`·`BaseSlotService`로 추상화해 신규 슬롯 추가 시 페이 계산 재구현 불필요. 충분한 반복을 겪은 후에 추상화했기 때문에 경계가 명확했다
- **테스트 인프라**: `AbstractSlotTest` 설계 — 치트 데이터 기반 확정적 단위 테스트로 팀 전체 테스트 생산성 향상. 추상화된 엔진 덕분에 신규 슬롯은 기반 클래스 상속만으로 핵심 테스트 구성 가능. 이 테스트 환경은 이후 AI 도입 시 검증 수단으로도 활용됨
- **성능 개선**: 가중치 랜덤 O(n)→O(1) (Alias Method), `SecureRandom`→`ThreadLocalRandom` 전환. **JMH 실측 약 58배 처리량 향상**. 시뮬레이터 OOM은 `List<Long>` 누적 구조(800MB/회)를 Welford's Online Algorithm(20B)으로 교체해 해결
- **AI 도입**: 구축된 도메인 지식을 Cursor Rules로 체계화(20종+), Dooray MCP 서버로 기획서를 에이전트에 직접 연결. *기획서 → Rules 생성 → 코드 제작 → 테스트 검증*의 개발 플로우 정립. AI 에이전트와의 대화만으로 슬롯 3종 구현, 개발 기간 25% 단축

#### 2. P2P 거래소 매칭 엔진 | 더퓨쳐컴퍼니 (2022.08)

**배경**: 게임 내 플레이어 간 아이템 직거래 거래소 — 주식 거래소와 동일한 지정가 주문(limit order) 체결 방식.

- **왜 Redis Streams인가**: Kafka보다 단순한 인프라 구성, Consumer Group으로 미전달 메시지 보장, 스트림 자체가 주문 이력 로그 역할. 인프라를 단일 Redis로 유지하면서 큐·저장·검색을 모두 처리
- **동시성 처리**: Lock/트랜잭션 대신 스트림 순서 보장 + Redis 플래그 직렬화 게이트 — 락 경합 자체를 구조로 제거
- **Price-Time Priority**: RediSearch로 가격 범위 쿼리 → Decimal.js 정밀 연산 → 부분 체결 처리
- **읽기·쓰기 분리**: 주문 접수(Pub) → 체결(Sub) → 호가창 조회(캐시 서빙) 3레이어 분리 — 체결 지연이 접수 응답에 무영향
- Redis Cluster + AOF/RDB 이중 영속성으로 주문 데이터 유실 방지

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| **언어** | Java 17/21 (주력), TypeScript |
| **프레임워크** | Spring Boot 3.5, Spring Batch, JPA/Hibernate, QueryDSL |
| **데이터** | MySQL, Redis (Streams/JSON/Search/Cluster), OpenSearch |
| **메시징** | RabbitMQ, Azure Service Bus, Redis Streams |
| **동시성** | StampedLock, ReentrantReadWriteLock, AtomicReference, ThreadLocalRandom |
| **테스트** | JUnit 5, JMH, MockRestServiceServer, spring-batch-test |
| **인프라** | NHN Cloud, Azure |
| **AI 도구** | Cursor (Rules 20+), Claude Code, Gemini CLI, Codex, MCP Server |

---

## 학력

| | |
|---|---|
| **전남대학교** | 2012.03 ~ 2019.02 · 졸업 |
| 수학 전공 · 소프트웨어공학 부전공 | 평점 3.18 / 4.5 |

---

## 자격증 / 기타

- 정보처리기사 (2018.08)
- TOEIC 860 (2017.01)
- GitHub: https://github.com/jon890

---

## 토스증권 Product 직무 자기 적합도

| 공고 요구사항 | 내 경험 | 강도 |
|---|---|---|
| 복잡한 기술 문제 해결 끈기 | OOM Welford 교체, ThreadLocal 버그 수정, RCC 잭팟 엣지케이스 | ★★★★★ |
| 조직 개선 주도 | 슬롯 엔진 추상화 자발적 설계, 캐시 인프라 표준화, 테스트 템플릿 | ★★★★☆ |
| 장기 코드 품질 유지 | AbstractSlotTest, BaseSlotService, AbstractStaticReloadable 공통화 | ★★★★☆ |
| Redis 고급 활용 | Streams/JSON/Search/Cluster + Ehcache MQ Fanout 정합성 | ★★★★★ |
| 실시간 데이터 처리 | 거래소 매칭 엔진(Price-Time Priority), RCC 비동기 캐시 | ★★★★☆ |
| 고트래픽 동시성 | StampedLock, AtomicReference, ReentrantReadWriteLock, DB 락 | ★★★★☆ |
| Spring Framework 숙련 | Spring Boot 2.6→3.x, Spring Batch 11-Step, JPA 실무 | ★★★★☆ |
| 서비스 성능 개선 | AliasMethod O(1), ThreadLocalRandom 58배, OOM 해결 | ★★★★★ |

### 상대적 약점 (보완 준비)

- **Kafka**: 직접 운영 경험 없음 → Redis Streams로 유사 패턴 경험(Consumer Group, 순차 처리, 스트림 트리밍) 강조. Kafka 파티셔닝·컨슈머 그룹 개념 사전 학습
- **Kubernetes**: 직접 운영 제한 → 서비스 배포·운영 레벨 이해 보강
- **증권 도메인**: 직접 경험 없음 → P2P 거래소(체결 엔진, 호가창, 부분 체결) 설계·구현 경험으로 금융 메커니즘 이해도 입증

---

## Excalidraw 아키텍처 준비 목록

인터뷰 중 아키텍처 설명 요청에 대비해 준비할 다이어그램:

- [ ] RCC 전체 흐름 (스핀 요청 → RccHandler → 비동기 캐시 생성 → DB)
- [ ] 거래소 매칭 엔진 (HTTP → Streams → 직렬화 게이트 → 체결 → 호가창 캐시)
- [ ] MQ Fanout 캐시 정합성 (어드민 → MQ → 전 인스턴스 동시 갱신)
- [ ] Spring Batch RAG 파이프라인 (11-Step 구조, AsyncItemProcessor 흐름)
