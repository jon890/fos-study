# CJ 올리브영 커머스플랫폼유닛 Back-End 개발 지원 자료

> 공고 URL: https://recruit.cj.net/recruit/ko/recruit/recruit/bestDetail.fo?zz_jo_num=J20260122036765
> 작성일: 2026-03-21

---

## 1. 채용 공고 상세

### 포지션

- **회사**: CJ 올리브영
- **팀/유닛**: 커머스플랫폼유닛 (웰니스개발팀)
- **직군**: Back-End 개발 (경력)
- **근무지**: 서울
- **고용형태**: 정규직 (수습 3개월)
- **모집기간**: 2026.01.23 ~ 채용시까지 (상시)

### 팀 소개

올리브영 커머스플랫폼유닛은 **1,600만 이상 고객**에게 쇼핑 경험을 제공하는 온라인몰의 핵심 서버 구축을 담당한다. "빠르고 안정적인 고객 경험"을 제공하는 것이 팀의 미션이며, 대규모 트래픽 처리와 복잡한 비즈니스 로직 구현이 주요 업무다.

---

## 2. 담당 업무

- 온라인몰 핵심 비즈니스 로직 개발 및 운영 (상품 관리, 전시 로직, 검색 엔진 연동)
- Java/Kotlin 기반 Spring Framework를 활용한 고성능 서버 시스템 개발
- 데이터베이스 설계 및 ORM(JPA, Hibernate) 활용
- RESTful API 설계 및 개발
- 시스템 성능 모니터링 및 개선
- MSA 환경에서의 서비스 개발 및 운영
- 새로운 기술 도입 및 검토

---

## 3. 자격 요건 & 우대 사항

### 필수 자격 요건

- **경력**: 5년 이상 백엔드 애플리케이션 개발 경력
- Java/Kotlin + Spring Framework 기반 개발 경험
- JPA, Hibernate 등 ORM 사용 및 도메인 모델링 경험
- WEB 환경에 대한 기본 이해 및 지식
- 문제 해결을 위한 가설 수립 및 수행 경험
- 학습과 성장에 대한 관심 및 자기 개발 노력

### 우대 사항

- Spring Boot 프로젝트 수행 경험
- Docker, Kubernetes 등 컨테이너 기반 기술 경험
- MSA 환경 구축 및 운영 경험
- Kafka 등 비동기 처리 Stream Engine 경험
- 다양한 캐싱 전략 이해 및 경험
- 대용량 데이터/트래픽 개발 및 운영 경험

---

## 4. 기술 스택 (공고 + 기술 블로그 종합)

### 언어 & 프레임워크

| 기술                        | 사용 맥락                   |
| --------------------------- | --------------------------- |
| Java / Kotlin               | 백엔드 서버 메인 언어       |
| Spring Boot                 | 서비스 개발 기본 프레임워크 |
| Spring Authorization Server | OAuth2 인증 서버            |
| Spring Session              | 세션 관리                   |
| JPA / Hibernate             | ORM, 도메인 모델링          |

### 메시징 & 이벤트

| 기술         | 사용 맥락                                        |
| ------------ | ------------------------------------------------ |
| Apache Kafka | Event-Driven Architecture, 도메인 간 데이터 연동 |
| AWS SQS      | 알림톡 처리 등 비동기 큐                         |

### 데이터 & 캐싱

| 기술              | 사용 맥락                           |
| ----------------- | ----------------------------------- |
| Redis             | Cache-Aside, 선택적 API 호출 최적화 |
| Aurora Serverless | RDS (AWS 관리형 DB)                 |

### 인프라 & 클라우드

| 기술                | 사용 맥락                       |
| ------------------- | ------------------------------- |
| AWS                 | 전반적 인프라 (SQS, Aurora, 등) |
| Docker / Kubernetes | 컨테이너 오케스트레이션         |

### 모니터링 & 장애 대응

| 기술         | 사용 맥락                       |
| ------------ | ------------------------------- |
| Datadog      | APM, 모니터링                   |
| Resilience4j | Circuit Breaker, Timeout, Retry |

### 아키텍처 패턴

- **MSA** (Microservices Architecture)
- **Event-Driven Architecture**
- **Cache-Aside Pattern**
- **Feature Flag 기반 무중단 배포**
- **Shadow Mode 배포 전략**

---

## 5. 올리브영 기술 블로그 핵심 글 요약

> 면접 준비 및 기술 트렌드 파악용

### 1) MSA 환경에서 도메인 데이터 연동 전략 (2026-03-18)

**Redis Cache-Aside + Kafka Event-Driven 하이브리드 설계**

- 데이터의 사용처·변경 빈도·라이프사이클 분석 → 최적 연동 방식 결정
- 변경이 적은 데이터 → Cache-Aside
- 실시간 이벤트 데이터 → Kafka 이벤트 수신 + Redis Key만 캐싱 → 선택적 API 호출
- **핵심 포인트**: 불필요한 API 호출 감소 + 실시간성 + 정확성 동시 확보

### 2) 대규모 트래픽 중 무중단 OAuth2 전환 (2025-10-28)

**올영세일(평소 대비 10배 트래픽) 중 100% 안정 배포 달성**

- Feature Flag(Strategy Pattern) → 런타임 DB 설정 변경만으로 코드 배포 없이 전환
- Shadow Mode → 토큰 선배포 후 점진적 전환
- Resilience4j Circuit Breaker 3단계 보호 (Timeout → Retry → Circuit Breaker)
- Jitter(±30초 랜덤) → Peak TPS 40% 감소
- **핵심 결과**: P95 레이턴시 50ms, 성공률 100%

### 3) SQS 기반 알림톡 DB 커넥션 데드락 분석 (2025-12-30)

- AWS SQS 기반 이벤트 드리븐 알림 시스템
- 트랜잭션 경합(데드락) 분석 및 해결

### 4) Spring 트랜잭션 동기화로 레거시 알림톡 발송 시스템 개선 (2026-02-23)

- 레거시 시스템 현대화 과정
- Spring 트랜잭션 동기화 메커니즘 활용

---

## 6. 전형 절차

```
서류전형
  ↓
1차 면접 (Live Coding / 구술)
  ↓
온라인 인성검사 (CJAT)
  ↓
2차 면접 (Whiteboard Test / 구술)
  ↓
Reference Check
  ↓
처우전형 / 건강검진
  ↓
최종 합격
```

---

## 7. 면접 준비 포인트

### 기술 면접 예상 주제

- [ ] MSA 환경에서의 서비스 간 통신 방식 (Sync vs Async)
- [ ] Kafka 사용 경험 및 Event-Driven Architecture 설계
- [ ] Redis 캐싱 전략 (Cache-Aside, Write-Through 등)
- [ ] JPA 성능 최적화 (N+1, 지연 로딩, 벌크 연산)
- [ ] 대용량 트래픽 처리 경험 (TPS, 병목 분석)
- [ ] Spring Transaction 동작 원리
- [ ] Circuit Breaker 패턴 및 장애 격리 전략
- [ ] Feature Flag 기반 무중단 배포 경험
- [ ] 도메인 모델링 / DDD 경험

---

## 8. 기타 유의 사항

- **이력서**: 프로젝트 상세 기술 필수 (파일 첨부)
- **수습기간**: 합격 후 3개월
- **유닛 간 중복 지원 불가**
- CJ계열사 재직자 지원 제한
- 병역필 또는 면제 필요
- 국가보훈대상자 및 장애인 우대

---

## 9. 참고 링크

- [채용 공고](https://recruit.cj.net/recruit/ko/recruit/recruit/bestDetail.fo?zz_jo_num=J20260122036765)
- [올리브영 기술 블로그](https://oliveyoung.tech/blog/)
- [MSA 데이터 연동 전략](https://oliveyoung.tech/blog/2026-03-18/oy-store-data-interconnection-strategy/)
- [무중단 OAuth2 전환기](https://oliveyoung.tech/blog/2025-10-28/oliveyoung-zero-downtime-oauth2-migration/)
- [SQS 데드락 분석기](https://oliveyoung.tech/blog/2025-12-30/alimtalk_improve_event_driven_architecture/)
- [Spring 트랜잭션 동기화](https://oliveyoung.tech/blog/2026-02-23/from-legacy-to-modern-architecture-journey/)
