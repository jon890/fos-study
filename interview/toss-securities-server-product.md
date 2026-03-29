# 토스증권 Server Developer (Product) 지원 자료

> 공고 URL: https://toss.im/career/job-detail?job_id=4071141003&sub_position_id=4076140003&company=%ED%86%A0%EC%8A%A4%EC%A6%9D%EA%B6%8C
> 작성일: 2026-03-29

---

## 1. 채용 공고 상세

### 포지션

- **회사**: 토스증권 (Toss Securities)
- **팀**: Server Chapter (Product)
- **직군**: Server Developer (경력)
- **근무지**: 서울
- **고용형태**: 정규직

### 팀 소개

토스증권 서버 챕터는 "어떻게 하면 될까?"를 먼저 고민하는 문화를 지향한다. 적극적인 코드 리뷰, 기술 토론, 스터디를 통한 지속적 학습을 중시하며, 엔지니어링 이벤트·주간 서버 챕터 미팅을 통한 수평적 협업이 특징이다.

Product 파트는 **유저 대면 서비스**를 담당한다 — 계좌 정보, 실시간 주식 거래, 검색, 시세, 커뮤니티, 알림 등.

---

## 2. 담당 업무

- Java/Kotlin + Spring Framework 기반 서버 솔루션 개발
- 배포 용이성·유지보수성·안정성·성능을 고려한 시스템 아키텍처 설계 및 개선
- Redis, Kafka, Kubernetes를 활용한 고트래픽 처리 및 동시성 관리
- 계좌 정보, 실시간 주식 거래, 검색, 시세, 커뮤니티, 알림 등 유저 대면 서비스 구축
- 담당 프로덕트·기술에 대한 오너십 발휘 및 최종 기술 의사결정권 행사

---

## 3. 자격 요건 & 우대 사항

### 필수 자격 요건

- 복잡한 기술 문제 해결에 대한 지속적인 끈기
- 조직 개선을 주도적으로 이끄는 리더십
- 장기 서비스에서 코드 품질 유지에 대한 헌신
- 비판 없는 협업 문화에 대한 편안함

### 우대 사항

- Java/Kotlin 및 Spring Framework 숙련도
- Redis, Kafka, ELK 스택, Kubernetes 경험
- Spring, Tomcat, JVM, OS, 네트워킹, 인프라 레이어 전반 트러블슈팅 역량
- 실시간 데이터 처리 및 네트워크 프로그래밍 경험
- 서비스 개선 실적 (성능, 생산성, UX)

---

## 4. 기술 스택

### 언어 & 프레임워크

| 기술                   | 사용 맥락                     |
| ---------------------- | ----------------------------- |
| Java / Kotlin          | 서버 메인 언어                |
| Spring Framework       | 서비스 개발 기본 프레임워크   |
| JPA / Hibernate        | ORM, 도메인 모델링            |
| Netty                  | 네트워크 프로그래밍           |
| Golang                 | 일부 인프라/도구 레이어       |

### 데이터 & 메시징

| 기술            | 사용 맥락                          |
| --------------- | ---------------------------------- |
| MySQL / Oracle  | 주요 RDB                           |
| Redis           | 캐싱, 실시간 데이터 처리           |
| MongoDB         | 비정형 데이터                      |
| Kafka           | 이벤트 스트리밍, 비동기 처리       |
| Elasticsearch   | 검색, 로그 분석 (ELK)              |
| InfluxDB        | 시계열 데이터 (모니터링)           |

### 인프라 & 모니터링

| 기술        | 사용 맥락          |
| ----------- | ------------------ |
| Kubernetes  | 컨테이너 오케스트레이션 |
| Grafana     | 대시보드, 모니터링 |

---

## 5. 전형 절차

```
서류 전형
  ↓
라이브 코딩 인터뷰 (선택)
  ↓
기술 인터뷰
  ↓
컬쳐핏 인터뷰
  ↓
레퍼런스 체크
  ↓
처우 협의
  ↓
최종 합격
```

---

## 6. 면접 준비 포인트

### 이력서 작성 가이드 (토스증권 권장)

- 폭넓은 프로젝트보다 **구체적으로 만든 기능과 해결한 문제** 중심
- 기술적 챌린지와 해결 과정을 서술
- 팀·조직 단위 지식 공유 활동 강조
- 서비스에 적용한 **고객 중심 사고** 구체화
- 데이터 무결성 및 신뢰성 개발 경험 포함

### 기술 면접 예상 주제

- [ ] Java/Kotlin 동시성 제어 (ReentrantLock, AtomicReference, ConcurrentHashMap)
- [ ] JVM 튜닝 및 GC 이슈 분석 경험
- [ ] Redis 캐싱 전략 (Cache-Aside, Write-Through, TTL 전략)
- [ ] Kafka 기반 이벤트 스트리밍 설계
- [ ] 고트래픽 환경에서의 병목 분석 및 성능 개선
- [ ] Spring Transaction 동작 원리 및 트랜잭션 경합 해결
- [ ] RESTful API 설계 및 실시간 데이터 일관성 보장
- [ ] 테스트 전략 및 테스트 인프라 설계

### 내 경험 매핑

| 공고 요구사항 | 내 경험 |
| --- | --- |
| Redis 캐싱 설계 | Ehcache + MQ Fanout 기반 다중 서버 캐시 동기화 설계 |
| Kafka 이벤트 스트리밍 | Redis Streams 기반 거래소 이벤트 큐 (순차 처리 보장) |
| 고트래픽 동시성 관리 | ReentrantReadWriteLock, AtomicReference 활용 동시성 버그 수정 |
| 성능 최적화 | Alias Method O(1) 가중 랜덤, Welford 알고리즘으로 OOM 해결 |
| Spring Framework 숙련 | Spring Boot 2.6 → 3.x, Spring Batch, JPA 실무 다수 |
| 실시간 데이터 처리 | 거래소 매칭 엔진 (가격-시간 우선순위), 슬롯 스핀 실시간 RTP 계산 |
| 아키텍처 개선 | SlotTemplate 추상화로 5개 게임 공통 엔진 통합 |

### 상대적 약점 (보완 필요)

- 금융/증권 도메인 직접 경험 없음 → 게임 금융 메커니즘(RTP, 거래소 매칭)으로 유사성 강조
- Kubernetes 직접 운영 경험 제한적
- Oracle DB 경험 없음 (MySQL 중심)

---

## 7. 기타 유의 사항

- 이력서에 관여한 서비스와 구체적 문제 해결 사례 필수 기재
- 라이브 코딩 인터뷰 존재 (알고리즘 + 설계 양쪽 대비)
- 토스 계열사 중복 지원 정책 확인 필요

---

## 8. 참고 링크

- [채용 공고](https://toss.im/career/job-detail?job_id=4071141003&sub_position_id=4076140003&company=%ED%86%A0%EC%8A%A4%EC%A6%9D%EA%B6%8C)
- [토스증권 기술 블로그](https://toss.im/blog/engineering)
