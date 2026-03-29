# SB 개발팀

스포츠 베팅 플랫폼 개발 경험 기록. 블록체인(wemix) 지갑 연동, 추천 프로그램, KYC 인증 시스템 등을 담당했다.

**기간**: 2023.01 ~ 2024.03

## 기술 스택

- **백엔드**: Java 11, Spring Boot 2.6, Ehcache 3, QueryDSL
- **프론트엔드**: Svelte + Vite (사용자), SvelteKit (어드민)
- **KYC 서버**: NestJS + TypeScript, Prisma
- **인프라**: NHN Cloud, Azure
- **블록체인**: wemix

## 문서 목록

| 문서 | 설명 |
|------|------|
| [추천 프로그램 시스템](./referral-program.md) | 추천인/피추천인 보너스, 미션 기반 BYLO 토큰 클레임 플로우 |
| [Vite 번들러 마이그레이션](./vite-migration.md) | Rollup → Vite 전환, wemix SDK 환경별 분리 |
| [KYC 시스템 구현](./kyc-system.md) | 신분증 인증, Azure Blob 저장, 6개월 자동 삭제 배치 |
| [캐시 아키텍처](./cache-architecture.md) | Ehcache + 인메모리 Map, MQ Fanout 캐시 정합성, RabbitMQ/Azure Service Bus 이중화 |
| [IP 화이트리스트 구현](./whitelist.md) | 서비스 점검 우회 IP 관리, Ehcache 적용, MQ 기반 캐시 갱신 |
| [wemix 지갑 연동](./wemix-wallet-integration.md) | 블록체인 지갑 연결, prepare/token 플로우, 환경별 SDK 관리 |
