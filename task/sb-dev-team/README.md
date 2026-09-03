# NHN SB 개발팀 업무 기록

**회사**: NHN | **팀**: SB 개발팀 (스포츠 베팅) | **기간**: 2023.01 \~ 2024.03

스포츠 베팅 플랫폼에서 진행한 주요 업무를 정리한 문서 모음. 블록체인 지갑 연동, 추천 프로그램, KYC 인증 등을 담당했다.

> 내부 엔티티/토큰/추상 클래스 고유 명칭은 일반화해서 표기했다.

## 기술 스택

- **백엔드**: Java 11, Spring Boot 2.6, Ehcache 3, QueryDSL
- **프론트엔드**: Svelte, Vite (사용자), SvelteKit (어드민)
- **KYC 서버**: NestJS, TypeScript, Prisma
- **인프라**: NHN Cloud, Azure (Blob Storage)
- **메시징**: RabbitMQ, Azure Service Bus (이중화)
- **블록체인**: wemix

---

## 문서 목록

### 신규 구현

| 기간              | 업무                                                              | 문서                                                       |
| ----------------- | ----------------------------------------------------------------- | ---------------------------------------------------------- |
| 2023.03 \~ 2023.12 | KYC 시스템: 신분증 인증, Azure Blob, AES-256-GCM 암호화           | [KYC 시스템 구현](kyc-system.md)                             |
| 2023.03 \~ 2024.02 | IP 화이트리스트: 점검 우회, Ehcache, MQ 기반 캐시 갱신           | [IP 화이트리스트 구현](whitelist.md)                               |
| 2023.04 \~ 2024.03 | wemix 지갑 연동: prepare/token 플로우, 환경별 SDK 분리           | [wemix 블록체인 지갑 연동](wemix-wallet-integration.md) |
| 2023.08 \~ 2024.02 | 13개 로케일 다국어: Svelte derived 합성, 백엔드 캐시 사전 구성  | [13개 로케일 다국어 시스템: Svelte derived 합성, 백엔드 캐시 사전 구성](i18n-system.md)                           |
| 2023.10 \~ 2024.02 | 추천 프로그램: 추천/피추천 보너스, 미션 기반 토큰 클레임 3단계   | [블록체인 토큰 기반 추천 프로그램: 설계와 협업 기록](referral-program.md)                 |

### 아키텍처 개선

| 기간              | 업무                                                                 | 문서                                       |
| ----------------- | -------------------------------------------------------------------- | ------------------------------------------ |
| 2023.03 \~ 2024.02 | 캐시 아키텍처: Ehcache, 인메모리 Map, MQ Fanout 정합성, 이중화 MQ | [Spring Boot 인메모리 캐시 구조: 다중 인스턴스 정합성](cache-architecture.md) |
| 2023.12           | Vite 번들러 마이그레이션: Rollup → Vite, wemix SDK 환경별 분리      | [Svelte 프론트엔드 번들러 Vite로 교체](vite-migration.md)     |

---

## 기술 키워드

`Java 11` `Spring Boot 2.6` `Ehcache 3` `QueryDSL` `Svelte` `SvelteKit` `Vite` `NestJS` `Prisma` `RabbitMQ` `Azure Service Bus` `Azure Blob` `wemix`
