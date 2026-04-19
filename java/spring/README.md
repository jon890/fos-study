# Spring Framework

Spring Framework / Spring Boot 학습 기록. IoC·생명주기·트랜잭션·AOP·JPA·HTTP 클라이언트.

## 컨테이너와 생명주기

- [IoC 컨테이너](./1_IoC_Container.md) — 스프링 프레임워크 기본
- [Application Context의 생명주기](./application-context-lifecycle.md)
- [InitializingBean](./initializing-bean.md) — 빈 초기화 콜백
- [`bootRun` 명령어](./boot-run.md)

## 트랜잭션

- [Spring Data JPA 트랜잭션 실수 모음](./jpa-transaction.md)
- [트랜잭션 전파·격리수준·AFTER_COMMIT 실전](./transaction-propagation-isolation-after-commit.md)
- [TransactionSynchronization 실전](./transaction-synchronization.md) — 커밋 이후 외부 호출을 안전하게 묶는 법

## JPA

- [JPA N+1 문제 완전 정복](./jpa-n-plus-one.md) — 발생 원인부터 EXPLAIN 분석까지

## AOP

- [Spring AOP와 프록시 심층 분석](./spring-aop-proxies-deep-dive.md) — JDK Dynamic Proxy, CGLIB, ByteBuddy

## HTTP 클라이언트

- [RestClient](./rest-client.md)
