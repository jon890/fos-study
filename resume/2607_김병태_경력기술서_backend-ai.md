# 김병태 경력기술서

백엔드 코어 위에 AI를 제품과 개발 생산성으로 접목해 온 7년차 개발자입니다.

- 이메일: jon89071@gmail.com
- GitHub: https://github.com/jon890
- 주요 분야: Java·Kotlin 백엔드, AI 서비스, RAG, 개발 생산성 자동화

## 핵심 역량

### 백엔드 시스템 설계와 운영

- Java 17·21과 Spring Boot 2.6·3.x 기반 운영 서비스를 개발했습니다.
- 동시성 제어, 캐시 정합성, 배치 처리, 비동기 후처리와 장애 복구를 다뤘습니다.
- 기능을 한 번에 교체하기보다 테스트 안전망과 작은 변경을 통해 점진적으로 구조를 개선했습니다.

### AI 서비스와 지식 기반

- 사내 RAG를 위한 다중 소스 벡터 색인 파이프라인의 배치 구조와 주요 처리 단계를 개발했습니다.
- Python·FastAPI 기반 문서 파싱 서비스의 워커 병렬화, 품질 검증과 운영 문제를 개선했습니다.
- Next.js·TypeScript·Gemini 기반 AI 제품을 프론트엔드부터 데이터베이스와 AI 파이프라인까지 완성했습니다.

### AI 기반 개발 생산성

- 복잡한 도메인 지식을 20개 이상의 Cursor Rules로 구조화했습니다.
- AI 에이전트가 신규 슬롯 3종을 구현하고 사람이 검토하는 개발 흐름을 적용했습니다.
- 협업 도구와 클라우드 운영 기능을 CLI로 통합해 사람과 AI 에이전트가 같은 실행 도구를 사용하도록 만들었습니다.
- LLM 코드리뷰, 자동 테스트와 문서 검증을 개발 수명 주기에 연결했습니다.

### 검증 가능한 문제 해결

- RAG 배치를 11개 Step으로 분리해 실패를 격리하고 중단 지점부터 재시작할 수 있게 했습니다.
- 문서 변환 결과에 회귀 검증, golden 채점과 표 셀 F1을 적용했습니다.
- Python 워커의 RSS 증가를 메모리 단편화 문제로 진단하고 OS 메모리 반환 구조로 개선했습니다.

## 기술 스택

| 영역 | 기술과 경험 |
|---|---|
| Backend | Java 11·17·21, Kotlin, Spring Boot, Spring Batch, JPA, QueryDSL, WebClient·Reactor Netty, NestJS |
| AI / Data | RAG, LLM workflow, Gemini API, OpenSearch vector search, document parsing, OCR quality evaluation |
| Frontend | TypeScript, Next.js, React, Svelte, Server Actions, SSE |
| Storage | MySQL, PostgreSQL, Redis, OpenSearch, Ehcache, Azure Blob Storage |
| Messaging | RabbitMQ, Apache Kafka, Redis Streams, SQS |
| Infra | Kubernetes, Helm, ArgoCD, Docker, NHN Cloud, AWS, Azure, Prometheus, Grafana |
| Test / Quality | JUnit 5, Testcontainers, spring-batch-test, JaCoCo, SonarQube, golden set, NED, 표 셀 F1 |
| AI Development | Claude Code, Cursor Rules, agent workflow, LLM code review, reusable skills and CLI |

## 경력 요약

| 기간 | 회사와 역할 | 주요 경험 |
|---|---|---|
| 2022.12–현재 | NHN, 백엔드·AI 서비스 개발 | 스포츠 플랫폼, 슬롯 백엔드, AI 서비스, RAG, 문서 파싱, AI 제품 개발 |
| 2022.02–2022.11 | 더퓨쳐컴퍼니, Node.js 백엔드 | 게임 아이템 거래소 체결 엔진, 블록체인 입출금, 미니게임 |
| 2018.08–2020.12<br>2021.07–2022.01 | 엠씨에스텍, SI 개발 | Java·Spring 기반 공공기관 시스템 개발과 레거시 현대화 |

총 개발 경력은 SI 개발 약 3년을 포함해 약 7년입니다.

## NHN AI 서비스 개발

**기간**: 2025.12–현재

**역할**: Java 백엔드, AI 서비스 파이프라인, Python 워커 운영, 풀스택 AI 제품 개발

### 다중 소스 RAG 벡터 색인 파이프라인

#### 배경

사내 지식 검색 서비스가 여러 원천의 문서를 OpenSearch에 벡터로 색인해야 했습니다.
임베딩 API와 문서 파싱은 I/O 대기가 길었고, 중간 실패 시 전체 작업을 다시 실행하는 비용이 컸습니다.

#### 기여

- Java 21·Spring Boot·Spring Batch 기반 파이프라인의 구조와 주요 처리 단계를 설계·구현했습니다.
- 수집, 변환, 임베딩, 색인, 삭제 동기화와 완료 처리를 11개 Step으로 분리했습니다.
- `AsyncItemProcessor`와 `AsyncItemWriter`로 I/O 작업을 병렬화했습니다.
- `CompositeItemProcessor`로 변경 감지, 데이터 보강, 본문 변환과 임베딩 단계를 조합했습니다.
- 변경되지 않은 문서는 임베딩을 건너뛰도록 version 비교 필터를 적용했습니다.
- 커서 기반 Reader와 실행 상태를 연결해 실패 지점부터 재시작할 수 있게 했습니다.
- 단일 문서 원천에서 사내 위키의 문서·댓글·첨부파일과 다중 스페이스를 포함하는 구조로 확장했습니다.
- Testcontainers, JaCoCo와 SonarQube로 회귀 검증을 자동화했습니다.

#### 결과

- 사내 AI 서비스의 RAG 색인 기반을 여러 기여자와 함께 구축했습니다.
- Step별 실패 격리와 재시작이 가능한 운영 구조를 마련했습니다.
- 문서 원천이 늘어나도 메타데이터 Provider를 추가해 확장할 수 있게 했습니다.

#### 기술

Java 21, Spring Boot 3.5, Spring Batch, OpenSearch, MySQL, Testcontainers

자세한 내용은 [RAG 벡터 색인 배치](../task/ai-service-team/rag-vector-search-batch.md)에서 확인할 수 있습니다.

### 문서 파싱 서비스 운영과 품질 검증

#### 배경

PDF, DOCX, PPTX, XLSX, HWP와 이미지 등 다양한 입력을 LLM이 사용할 수 있는 Markdown으로 변환하는 서비스입니다.
OCR과 문서 변환 결과는 라이브러리나 설정 변경에 따라 쉽게 달라져 품질 회귀를 자동으로 판별할 필요가 있었습니다.

#### 기여

- 단일 처리 구조를 한국어, 일본어와 우선순위 워커 풀로 분리했습니다.
- 인스턴스당 4개 워커와 운영 8대 환경에서 문서를 동시에 처리하도록 개선했습니다.
- 비대해진 파서를 입력, 적재, 변환과 Markdown 생성 단계로 분해했습니다.
- 지표, 로그와 조회 API에 중복된 관측 정보를 Grafana 중심으로 정리했습니다.
- pending 작업과 크기가 고정된 call queue를 구분해 실제 적체 판단 기준을 정립했습니다.
- 이전 출력과 비교하는 NED 회귀 검증에 사람이 확정한 golden 채점을 추가했습니다.
- 표는 전체 텍스트 점수와 분리해 셀 단위 F1으로 평가했습니다.
- 운영 서버를 사용하던 검증 방식을 일회성 클라우드 인스턴스로 전환했습니다.
- `gc.collect()` 뒤에도 남는 워커 RSS를 glibc 메모리 단편화 관점에서 진단했습니다.
- `malloc_trim`을 환경변수로 제어하고 카나리에서 메모리 추이를 검증했습니다.
- 대용량 XLSX를 행 단위로 처리해 27GiB 제한을 채우던 입력의 RSS를 약 92MB로 낮췄습니다.
- 중복 CUDA 의존성을 제거해 컨테이너 이미지 압축 크기를 9.89GB에서 6.82GB로 줄였습니다.

#### 결과

- 품질 저하를 자동으로 차단하면서 개선 실험을 반복할 수 있는 기반을 만들었습니다.
- 운영 인스턴스에 영향을 주지 않는 검증 환경을 마련했습니다.
- 메모리, 좀비 프로세스와 GPU 이미지 크기를 운영 지표와 회귀 검증으로 관리할 수 있게 했습니다.

#### 기술

Python 3.11, FastAPI, ProcessPoolExecutor, docling, PaddleOCR, Docker, Prometheus, Grafana

자세한 내용은 [문서 파싱 파이프라인](../task/ai-service-team/playground-document-parser.md)에서 확인할 수 있습니다.

### OCR API와 배포 경로 안정화

OCR 모델 서버의 배포·오토스케일 전환 때 기동 전 요청과 종료 중 연결 단절이 발생했습니다.
기존 API Gateway를 제거한 뒤에는 HTTPS, 경로 변환과 접근 제어를 직접 책임져야 했습니다.

- 모델 서버의 준비 신호 뒤에 Envoy가 요청을 받도록 기동 순서를 고쳤습니다.
- gRPC 종료 유예, 프로세스 신호 전달과 Envoy drain 순서를 맞췄습니다.
- OCR API의 커넥션 수명, 2초 연결 제한과 안전한 오류만 다시 보내는 재시도 정책을 적용했습니다.
- Gateway부터 모델 서버까지 `X-Request-Id`를 전파해 로그를 연결했습니다.
- 외부용 Ingress Controller, LoadBalancer, HTTPS와 IP 접근 제어를 구성했습니다.
- 기존 경로와 새 경로의 응답 등가성, 접근 차단과 지속 부하를 검증했습니다.

도달할 수 없는 모델 주소의 연결 실패를 약 30초에서 2.1초로 줄였습니다.
기동과 종료 양쪽의 연결 실패를 서버와 호출자 계층에서 함께 방어했습니다.

Java 21, Spring Boot 3.x, WebClient, Reactor Netty, Python, gRPC, Envoy, Kubernetes, Helm, ArgoCD

- [OCR 오토스케일 연결 안정화](../task/ai-service-team/ocr-scale-connection-resilience.md)
- [OCR 공인 진입점 전환](../task/ai-service-team/ocr-api-gateway-removal.md)

### AI 웹툰 제작 도구

#### 배경

웹소설 분석부터 세계관, 캐릭터, 각색, 글콘티와 이미지 컷 생성까지 이어지는 AI 제품 MVP를 혼자 완성해야 했습니다.

#### 기여

- Next.js 16, TypeScript, PostgreSQL, Prisma와 Gemini를 사용하는 단일 코드베이스를 설계했습니다.
- 프론트엔드, 백엔드, 데이터베이스와 AI 호출 파이프라인을 End-to-End로 구현했습니다.
- 모델 품질과 비용을 함께 고려해 pro, flash, lite 순서의 fallback 정책을 설계했습니다.
- 전역 rate limit 상태를 공유해 제한된 모델에 반복 요청하는 문제를 막았습니다.
- 소설 반복 입력은 Gemini Context Caching으로 공유했습니다.
- 60컷 이미지 생성은 `Promise.allSettled`로 부분 실패를 격리했습니다.
- continuation 호출에도 원작과 treatment를 다시 주입해 환각을 줄였습니다.
- 이미지 모델에는 텍스트 지시 대신 기준 이미지를 전달해 캐릭터 외형을 유지했습니다.
- Zod를 AI 응답과 외부 입력 검증의 단일 소스로 사용했습니다.
- Container와 Presenter를 분리하고 파일 소유권을 정해 디자이너와의 충돌을 줄였습니다.

#### 결과

- 전반 12일 동안 199개 계획과 760개 커밋으로 MVP 범위를 완성했습니다.
- 후반 12일에는 구조, 관측성, 오류 처리와 통합 테스트를 보강해 운영 단계로 확장했습니다.
- 본인은 요구사항, 설계, 계획과 검토를 맡고 에이전트가 구현하는 개발 하네스를 정착시켰습니다.
- 운영자가 단계별 결과를 검토하고 수정·재생성할 수 있는 제품 흐름을 만들었습니다.

#### 기술

Next.js 16, React 19, TypeScript, PostgreSQL, Prisma, Zod, Gemini API

자세한 내용은 [AI 웹툰 제작 도구](../task/ai-service-team/webtoon-maker-ai-pipeline.md)에서 확인할 수 있습니다.

## NHN 슬롯 백엔드 개발

**기간**: 2024.06–2025.11

**역할**: Java 백엔드, 슬롯 도메인 개발, 아키텍처 개선, AI 개발 방식 도입

### 슬롯 도메인과 아키텍처 개선

- Spring Boot 3·Java 17 기반 신규 슬롯 5종 개발에 참여했습니다.
- 여러 슬롯 구현에서 반복되는 패턴을 확인한 뒤 `BaseSlotService`와 페이 조건 추상화(`SlotPayConditionChecker`)를 도입했습니다.
- 플레이 모드별 중복 흐름을 템플릿과 핸들러 구조로 통합했습니다.
- 슬롯별 당첨 계산 규칙은 Decorator와 Strategy 조합으로 확장했습니다.
- 정적 데이터 갱신 구간을 `StampedLock`으로 보호해 조회 중 NPE를 막았습니다.
- 백그라운드 결과 캐시 시스템을 여러 슬롯에 적용했습니다.
- 테스트가 어려운 레거시 코드를 1년 반 동안 작은 변경으로 통합 테스트 가능한 구조로 전환했습니다.

### 성능과 동시성 문제 해결

- 가중치 랜덤 선택의 O(n) 누적합 병목을 분석하고 O(1) Alias Method 적용 근거를 정리했습니다.
- 1억 건 데이터를 메모리에 누적하던 시뮬레이터를 Welford Online Algorithm으로 변경해 공간 복잡도를 O(1)로 줄였습니다.
- 캐시 생성 충돌은 DB 유니크 키와 예외 처리를 사용해 단순하게 제어했습니다.

자세한 내용은 다음 문서에서 확인할 수 있습니다.

- [슬롯 엔진 추상화](../task/nsc-slot/slot-engine-abstraction.md)
- [슬롯 스핀 성능 개선](../task/nsc-slot/slot-spin-performance.md)

### AI 에이전트 기반 개발 방식 도입

- 코드 위치, 도메인 객체, 게임 규칙과 검토 기준을 20개 이상의 Cursor Rules로 만들었습니다.
- 에이전트가 존재하지 않는 클래스나 메서드를 사용하는 문제를 정확한 패키지와 제약 정보로 줄였습니다.
- 에이전트 구현은 `by agent` 커밋으로 구분해 추적했습니다.
- Slot 41, 44와 47을 에이전트가 구현하고 사람이 도메인 규칙을 검토하는 흐름을 운영했습니다.
- 에이전트용 문서가 신규 팀원의 도메인 온보딩 자료로도 재사용되도록 만들었습니다.

자세한 내용은 [AI 개발 도구 도입](../task/nsc-slot/ai-tool-adoption.md)에서 확인할 수 있습니다.

## NHN 스포츠 플랫폼 개발

**기간**: 2023.01–2024.03

**역할**: Java·Kotlin 백엔드, 어드민과 일부 프론트엔드, 캐시·정산 시스템 개발

- Java 11·Spring Boot 2.6 기반 서비스와 Kotlin 기반 어드민 백엔드를 개발했습니다.
- 추천·미션 보상 프로그램을 상태 머신과 비관적 락으로 구현해 중복 지급을 방지했습니다.
- 다중 서버 정산 워커에서 `SELECT FOR UPDATE`로 작업을 선점하고 중복 정산을 막았습니다.
- 정적 데이터 캐시 갱신 구간을 `ReentrantReadWriteLock`으로 보호했습니다.
- 캐시 응답 객체를 재사용해 갱신 중 부분 상태 노출과 불필요한 객체 생성을 줄였습니다.
- 13개 로케일 다국어 시스템을 프론트엔드부터 백엔드 캐시까지 단독 설계했습니다.
- 트랜잭션 커밋 이후 이벤트 발행과 실패 기록을 분리하는 후처리 구조를 운영했습니다.

자세한 내용은 [인메모리 캐시 구조](../task/sb-dev-team/cache-architecture.md)에서 확인할 수 있습니다.

## 더퓨쳐컴퍼니

**기간**: 2022.02–2022.11

**역할**: TypeScript·NestJS 백엔드

- Redis Streams의 순서를 이용해 게임 아이템 거래소 체결 엔진을 설계했습니다.
- Redis 기반 원자적 상태 관리로 동일 주문과 아이템의 동시 진입을 차단했습니다.
- 유저별 Solana 지갑 발급, 입금 폴링과 출금 흐름을 구현했습니다.
- 게임 상태를 저장해 브라우저 이탈 후에도 마지막 지점부터 이어서 진행할 수 있게 했습니다.

자세한 내용은 [거래소 체결 엔진](../task/the-future-company/trading-engine.md)에서 확인할 수 있습니다.

## 엠씨에스텍

**기간**: 2018.08–2020.12, 2021.07–2022.01

**역할**: Java·Spring 기반 SI 개발

- 공공기관 헬스케어 앱의 조직도 기반 랭킹과 Batch를 개발했습니다.
- 인사평가 시스템의 DB 프로시저 중심 로직을 애플리케이션으로 이전했습니다.
- Struts 기반 사내 홈페이지를 Spring MVC로 현대화했습니다.
- 전기차 충전 진단 Android 앱과 DDS 네트워크 모니터링 웹을 개발했습니다.

## 개인 프로젝트

### dooray-cli

- 협업 시스템의 업무, 위키, 메일과 첨부 기능을 TypeScript CLI로 통합했습니다.
- 모든 명령에 `--json`과 `--quiet` 계약을 제공해 AI 에이전트가 결과를 파싱할 수 있게 했습니다.
- 비대화형 실행과 파일 입력을 지원해 자동화 파이프라인에서 재사용할 수 있게 했습니다.
- LLM 4개 역할을 이용한 PR 코드리뷰를 CI에 연결했습니다.
- GitHub: https://github.com/jon890/dooray-cli

### nhncloud-cli

- Compute, VPC, Deploy, Container Registry와 Kubernetes 등 98개 클라우드 명령을 하나의 CLI로 통합했습니다.
- `commands --json`으로 에이전트가 런타임에 전체 명령 구조를 발견할 수 있게 했습니다.
- 명령별 JSON 응답과 표준 종료 코드를 정의해 자동 운영의 실패 판단을 일관되게 만들었습니다.
- GitHub: https://github.com/jon890/nhncloud-cli

## 협업 방식

- 주요 의사결정을 배경, 대안, 선택과 결과가 드러나는 문서로 남깁니다.
- AI 에이전트 결과물도 코드리뷰, 테스트와 도메인 검증을 통과해야 병합합니다.
- 기능 구현과 함께 팀이 반복 사용할 수 있는 테스트, 규칙, CLI와 문서를 남깁니다.
- 모호한 요구사항을 작은 검증 단위로 나누고, 실패 시 다시 시작할 수 있는 실행 구조를 선호합니다.
- 기술 구현의 완료보다 실제 사용 흐름과 운영 피드백까지 확인하는 개발자로 성장하고 있습니다.

## 학력과 자격

- 전남대학교 수학 전공, 소프트웨어공학 부전공
- 2019.02 졸업
- 정보처리기사

## 지원 역할과의 연결

- Java·Kotlin 백엔드 역량을 바탕으로 전사 프로젝트의 설계와 구현에 참여할 수 있습니다.
- RAG, 문서 파싱과 AI 제품 경험을 이용해 업무 현장의 문제를 AI 기능과 지식 기반으로 전환할 수 있습니다.
- CLI와 에이전트 컨텍스트 설계 경험을 이용해 반복 업무를 실행 가능한 도구로 만들 수 있습니다.
- End-to-End 제품 경험을 이용해 아이디어를 배포 가능한 형태까지 완결할 수 있습니다.
- 다음 단계에서는 도구 도입 전후의 시간, 사용률, 자동화 성공률과 지식 최신성을 측정해 개선 효과를 검증하고자 합니다.
