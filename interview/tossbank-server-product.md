# 토스뱅크 Server Developer (Product) 지원 자료

> 공고 URL: https://toss.im/career/job-detail?job_id=4071141003&sub_position_id=4076109003&company=%ED%86%A0%EC%8A%A4%EB%B1%85%ED%81%AC
> 작성일: 2026-03-31

---

## 1. 채용 공고 상세

### 포지션

- **회사**: 토스뱅크 (Toss Bank)
- **직군**: Server Developer (Product)
- **근무지**: 서울
- **고용형태**: 정규직

### 팀 소개

유망한 IT기업과 스타트업 출신 개발자들이 은행 혁신을 위해 모인 조직이다. 금융의 시작부터 설계 가능한 토스뱅크는 개발자에게 많은 자유를 제공한다. 기존 은행 관례에 의문을 제기하며 불편한 사용자 경험을 제거하는 데 집중한다.

- **기술 철학**: 레거시가 거의 없고 Kotlin으로 구성된 진취적 기술 환경
- **배포 문화**: 하루에도 수차례 혁신적인 실험과 기능 추가를 위한 배포
- **조직 문화**: DRI(Directly Responsible Individual) — 최소한의 지시, 주도적 문제 정의·해결
- **최종 합격 시**: 지원자의 경험·강점·관심사를 고려해 적합한 조직에 배치

---

## 2. 담당 업무

- 복잡한 은행 시스템을 빠르고 간결한 구조로 고객에게 제공하는 방법 고민 및 실행
- 고객 경험 개선을 위한 빠르고 유연하며 확장 용이한 시스템 개발
- 대용량 트래픽 처리를 위한 안정적이고 안전한 시스템 개발
- 혁신적인 뱅킹 서비스 기획부터 개발까지 담당
- 대고객 서비스 및 내부 관리 웹 서비스 개발

---

## 3. 자격 요건 & 우대 사항

### 필수 자격 요건

- Kotlin/Java로 Spring Framework 기반 서비스 개발 경험
- 비즈니스 요건의 빠른 이해 및 데이터 모델/API 설계 능력

### 우대 사항

- 대용량 트래픽 안정적 운영 경험
- Redis 및 Kafka 사용 경험
- 지속적 성장 의지
- 팀 협업 및 지식 공유 역량

---

## 4. 기술 스택 (공고 + 기술 블로그 종합)

### 언어 & 프레임워크

| 기술 | 사용 맥락 | 출처 |
| --- | --- | --- |
| Kotlin | 주 언어 (레거시 거의 없음) | 공고 |
| Java | 일부 사용 | 공고 |
| Gradle | 빌드 도구 | 공고 |
| Spring Boot | 애플리케이션 프레임워크 | 공고 |
| Spring MVC | REST API | 공고 |
| Spring WebFlux | 비동기 리액티브 처리 | 공고 |
| Spring Cloud Gateway | API 게이트웨이 | 공고 |
| Spring Cloud Config | 설정 관리 | 공고 |
| Netty | 비동기 네트워크 레이어 | 공고 |

### 데이터 & 메시징

| 기술 | 사용 맥락 | 출처 |
| --- | --- | --- |
| MySQL | 주 RDB, 동시성 제어 락 활용 | 공고 + 블로그 |
| JPA/Hibernate | ORM | 공고 |
| Redis | 분산 락, 캐싱(TTL 1일), 캐시 전략 | 공고 + 블로그 |
| Kafka | 비동기 트랜잭션 분리, DLQ 패턴 | 공고 + 블로그 |
| MongoDB | 일부 데이터 스토어 | 공고 |
| Zookeeper | 분산 코디네이션 | 공고 |

### 인프라 & 클라우드

| 기술 | 사용 맥락 | 출처 |
| --- | --- | --- |
| Kubernetes | 컨테이너 오케스트레이션 | 공고 + 블로그 |
| Istio | Service Mesh (MSA 통신 관리) | 공고 + 블로그 |
| Docker | 컨테이너 | 공고 |
| ArgoCD | GitOps 배포 | 공고 |
| GoCD | CI/CD 파이프라인 | 공고 |
| Harbor | 컨테이너 레지스트리 | 공고 |
| Ceph | 분산 스토리지 | 공고 |
| Consul | 서비스 디스커버리 | 공고 |
| Vault | 시크릿 관리 | 공고 |

### 모니터링 & 장애 대응

| 기술 | 사용 맥락 | 출처 |
| --- | --- | --- |
| ELK Stack | 로그 수집·분석 | 공고 |
| Prometheus + Thanos | 메트릭 수집 (장기 보존) | 공고 |
| Grafana | 시각화 대시보드 | 공고 |
| Kafka | 이벤트 스트리밍 + 모니터링 연계 | 공고 + 블로그 |

### 아키텍처 패턴 (블로그에서 파악)

- **MSA**: 코어뱅킹 모놀리식 → 마이크로서버 전환 (도메인 단위 분리)
- **Service Mesh (Istio)**: 서비스 간 통신 관리, 안정성 확보
- **Kafka DLQ 패턴**: 비동기 메시지 처리 실패 → Dead Letter Queue → 멱등성 설계로 안전한 재처리
- **카나리 배포**: 점진적 트래픽 전환 (개발팀 → 내부 팀원 → 일부 고객 → 전체)
- **온라인 A/B 검증**: 기존 시스템과 신규 시스템 동시 호출 후 결과 비교
- **CQRS 유사 패턴**: 쓰기(거래 처리)와 읽기(잔액 조회) 경로 분리
- **Redis Global Lock + JPA Pessimistic Lock**: 계좌 동시성 제어

---

## 5. 토스뱅크 기술 블로그 핵심 글 요약

### 은행 최초 코어뱅킹 MSA 전환기 (feat. 지금 이자 받기)
> https://toss.tech/article/slash23-corebanking

토스뱅크가 1970년대부터 이어진 모놀리식 코어뱅킹 구조를 MSA로 전환한 과정이다. MCI·FEP·EAI가 강결합된 구조에서는 카드 이벤트 하나의 트래픽 폭증 시 전체 시스템을 스케일 아웃해야 했고, 한 컴포넌트 장애가 전 업무 마비로 이어질 수 있었다.

**핵심 기술 결정**:
- 잔액·통장 기록(즉시성 필요)은 동기 처리, 세금·회계(지연 가능)는 Kafka 비동기 분리
- DML 80회 → 50회로 축소, 응답시간 대폭 개선 (성능 170배 향상 수준)
- Redis Global Lock + JPA `@Lock(PESSIMISTIC_WRITE)`으로 계좌 단위 동시성 제어
- Redis 캐싱: 첫 접근 시 이자 계산 → TTL 1일로 저장, 하루 중 재접근은 캐시 반환
- Kafka DLQ: 비동기 처리 실패 시 DLQ 이동, 멱등성 설계로 세금 DB 트랜잭션 보장

**무중단 마이그레이션 전략**: 온라인 이중 호출(결과 비교) → 배치 검증(스테이징) → 카나리 배포(점진적 트래픽 전환) → E2E 통합 테스트. "빅뱅 배포 탈피"가 핵심이었다.

---

### 은행 앱에도 Service Mesh 도입이 가능한가요? (SLASH 22)
> https://toss.im/slash-22/sessions/3-8

토스뱅크 DevOps 엔지니어들이 공유한 Kubernetes + Istio Service Mesh 운영기다. 은행 앱의 높은 안정성 기준을 충족하면서 MSA 간 통신 관리, 서킷브레이킹, 트래픽 제어를 Service Mesh로 해결했다. 채널계(MSA)와 코어뱅킹 사이의 복잡한 서비스 간 통신을 안정적으로 운영하는 방법을 다루며, 빠른 서비스 성장과 안정성을 동시에 달성하기 위한 인프라 철학을 공유했다.

---

### 슬기로운 토스뱅크 개발 인턴 생활
> https://toss.tech/article/toss-bank-interns

Loan Tech Platform 팀의 인턴 경험기로, 토스뱅크 개발 문화와 실제 기술 환경이 잘 드러난다.

**실제 기술 환경**:
- Kotlin 컴파일러 플러그인 레벨의 커스터마이징: `@Secret` 애노테이션이 붙은 필드를 빌드 시점에 IR 트리 변환으로 자동 마스킹 → 계좌번호·주민등록번호 로그 노출 원천 차단
- LLM 내재화: 사내 자체 구축 LLM으로 변수명 번역, 오타 검증 등 개발 생산성 도구 직접 제작
- 은행 도메인 특유의 복잡한 변수명(`installmentRepaymentManagementNumber` 등) 관리 체계화

**개발 문화**:
- DRI 문화: 인턴도 문제를 스스로 정의하고 해결책을 제안
- 수평적 구조: 직급 구분 없이 의견 제안 가능
- 제품 관점의 사고: 단순 코드 작성이 아닌 "왜 필요한가"를 항상 질문

---

## 6. 전형 절차

```
서류 접수
    ↓
(필요 시) 사전 인터뷰
    ↓
직무 인터뷰
    ↓
문화 적합성 인터뷰
    ↓
레퍼런스 체크
    ↓
처우 협의
    ↓
최종 합격 및 입사
```

---

## 7. 면접 준비 포인트

### 기술 면접 예상 주제

- [ ] Kotlin 코루틴 vs Java 스레드 모델 차이점 및 실무 적용 경험
- [ ] Spring WebFlux + 리액티브 프로그래밍 실제 사용 경험
- [ ] 분산 환경에서 동시성 제어 방법 (Redis Lock, DB Lock, 낙관적/비관적 락)
- [ ] Kafka Consumer Group, 파티션, 오프셋 관리, DLQ 패턴
- [ ] MSA 환경에서 데이터 정합성 확보 방법 (Saga 패턴, 이벤트 소싱)
- [ ] Redis 캐싱 전략 (TTL, Cache Aside, Write-Through, 캐시 정합성)
- [ ] 무중단 배포 전략 (카나리, 블루-그린)
- [ ] 금융 시스템에서 트랜잭션 경계 설계 원칙
- [ ] JPA N+1 문제 해결, 쿼리 최적화 경험
- [ ] Kubernetes 환경 운영 경험 (HPA, 리소스 설정 등)
- [ ] 서비스 장애 대응 경험 및 재발 방지 방법론
- [ ] 이력서에 작성한 "어려운 과제 극복 사례" 상세 설명

### 내 경험 매핑

| 공고 요구사항 | 내 경험 |
| --- | --- |
| Kotlin/Java Spring Framework 개발 | Java 17 + Spring Boot 3.x (NSC 슬롯팀, 2024.06~2025.11), Java 11 + Spring Boot 2.6 (SB개발팀, 2023~2024), NestJS/TypeScript도 보유 |
| 대용량 트래픽 안정적 운영 | RCC 시스템: 슬롯 6종 백그라운드 캐시 생성, 복합 인덱스 최적화로 COUNT 쿼리 성능 개선, 동시성 DB 유니크 키 + 예외처리로 제어 |
| Redis 사용 경험 | NSC 슬롯팀: Spring Boot + Redis (JPA + QueryDSL). 더퓨쳐컴퍼니: Redis Streams(이벤트 큐), Redis JSON(호가창 저장), RediSearch(가격 범위 조회·집계), Redis 분산 세마포어(직렬화 게이트), RDB 영속성 구성 |
| Kafka 사용 경험 | 직접 Kafka 운영 경험은 없음. Redis Streams로 유사한 이벤트 스트리밍 패턴(Consumer Group, 순서 보장, 미처리 메시지 구독) 직접 구현한 경험 있음 |
| 데이터 모델/API 설계 능력 | 거래소 체결 엔진: 호가창·주문 도메인 설계, Price-Time Priority 매칭 알고리즘 구현. RAG 배치: 11개 Step 파이프라인 설계, 전략 패턴 기반 메타데이터 확장 구조 |
| 비즈니스 요건 이해 | 더퓨쳐컴퍼니: 게임 거래소 기획부터 설계·구현. NHN: 슬롯 게임 RTP 보장 시스템(RCC) 설계, 금융 법적 요건 반영 |
| 캐시 아키텍처 설계 | SB개발팀: Ehcache + 인메모리 Map(`AbstractStaticReloadable`) + MQ Fanout 멀티서버 캐시 정합성 (RabbitMQ/Azure Service Bus 이중화). NSC슬롯: Spring @Async 비동기 캐시 생성 시스템 |
| 성능 최적화 | AliasMethod O(1) 가중치 랜덤 선택 도입, SecureRandom → ThreadLocalRandom 전환(58배 개선), JMH 벤치마킹으로 측정 |
| 아키텍처 추상화 | SlotTemplate/BaseSlotService/ExtraConfig 분리로 슬롯 엔진 추상화. RccSpinResultAnalyzer 인터페이스로 슬롯별 캐시 조건 캡슐화. EmbeddingMetadataProvider 전략 패턴 도입(OCP 준수) |
| Spring Batch 경험 | RAG 배치 파이프라인: AsyncItemProcessor + AsyncItemWriter 병렬 처리, CompositeItemProcessor 체이닝, @JobScope 데이터 홀더, 재시작 가능 설계 (allowStartIfComplete) |

### 상대적 약점 (보완 필요)

- **Kotlin 실무 경험 없음**: Java 17을 주력으로 사용. Kotlin 문법과 코루틴은 학습 중이지만 실제 프로덕션 적용 경험이 없다. 토스뱅크는 Kotlin을 주 언어로 사용하므로 빠른 전환이 필요.
  - 보완: Java 경험이 탄탄하고 NestJS TypeScript 경험으로 Null-Safety, data class 개념에 익숙함. Kotlin 컴파일러 플러그인 수준까지 파고드는 팀 문화에 맞게 학습 깊이를 높여야 함.
- **Kafka 직접 운영 경험 없음**: Redis Streams로 유사 패턴을 구현한 경험이 있지만 Kafka 특유의 파티션 전략, Consumer Lag 모니터링, 스키마 레지스트리 운영 경험이 없다.
  - 보완: Redis Streams 경험에서 Consumer Group, 순서 보장, DLQ 패턴을 직접 구현한 경험을 연결해서 설명하고, Kafka 공부를 병행.
- **금융 도메인 경험 없음**: 게임 아이템 거래소(더퓨쳐컴퍼니)에서 가상 자산 거래 엔진을 만든 경험은 있으나, 실제 금융 규제·회계 처리·이중화 요건 등의 경험은 없다.
  - 보완: 거래소 도메인의 정밀 연산(Decimal.js), 동시성 제어, 부분 체결·잔량 등록·취소 등 금융과 유사한 복잡도를 다룬 경험을 구체적으로 어필.
- **Spring WebFlux 실무 경험 부족**: Project Reactor는 슬롯 시뮬레이터(`ReactiveSimulator`)에서 활용했으나, 프로덕션 WebFlux 서버 운영 경험은 없다.

---

## 8. 이력서 작성 가이드 (공고 지침)

- 실제 참여 프로젝트와 기여도, **어려운 과제 극복 사례 1가지 이상** 필수 포함
- 문제 정의 → 해결 시도 → 결과까지 **상세한 문제 해결 과정** 기재
- **대규모 트래픽 처리 또는 개선 경험** 명시
- **개발자로서의 성장 목표 및 노력 내용** 작성
- 허위 사실 발견 시 채용 취소 가능
- AI 도구 활용 경험 관련 별도 질문 포함 (Cursor Rules 20종 이상 구축 경험 어필 가능)
- 장애인 및 국가보훈대상자 우대

---

## 9. 참고 링크

- [채용 공고](https://toss.im/career/job-detail?job_id=4071141003&sub_position_id=4076109003&company=%ED%86%A0%EC%8A%A4%EB%B1%85%ED%81%AC)
- [토스 기술 블로그](https://toss.tech/)
- [은행 최초 코어뱅킹 MSA 전환기 (SLASH 23)](https://toss.tech/article/slash23-corebanking)
- [은행 앱에도 Service Mesh 도입이 가능한가요? (SLASH 22)](https://toss.im/slash-22/sessions/3-8)
- [슬기로운 토스뱅크 개발 인턴 생활](https://toss.tech/article/toss-bank-interns)
- [유연하지만 견고한 은행 시스템을 만들어요](https://toss.im/career/article/tossbank-system)
