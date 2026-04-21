# Spring Framework

Spring Framework / Spring Boot 학습 기록. IoC, 생명주기, 트랜잭션, AOP, JPA, HTTP 클라이언트.

이 폴더는 **Spring 학습 허브**다. 문서가 늘어나도 한 문서가 모든 걸 설명하지 않도록 역할을 나눠 유지한다.
- 트랜잭션 실전 축은 `jpa-transaction.md`, `transaction-propagation-isolation-after-commit.md`, `transaction-synchronization.md`
- 횡단 관심사 선택 축은 [Filter, Interceptor, AOP](./filter-interceptor-aop.md)
- AOP 내부 동작 심화는 [Spring AOP와 프록시 심층 분석](./spring-aop-proxies-deep-dive.md)

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

## 횡단 관심사 / AOP

- [Filter, Interceptor, AOP](./filter-interceptor-aop.md) — 요청 처리 파이프라인에서 무엇을 어디에 둘지 결정하는 비교/선택 가이드
- [Spring AOP와 프록시 심층 분석](./spring-aop-proxies-deep-dive.md) — JDK Dynamic Proxy, CGLIB, ByteBuddy

## HTTP 클라이언트

- [RestClient](./rest-client.md)
