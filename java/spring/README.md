# Spring Framework

Spring Framework / Spring Boot 학습 기록. IoC, 생명주기, 트랜잭션, AOP, JPA, HTTP 클라이언트.

이 폴더는 **Spring 학습 허브**다. 문서가 늘어나도 한 문서가 모든 걸 설명하지 않도록 역할을 나눠 유지한다.
- 트랜잭션 실전 축은 [Spring Data JPA 트랜잭션 흔한 실수들](jpa-transaction.md), [Spring 트랜잭션 전파·격리수준·AFTER_COMMIT 실전 정리](transaction-propagation-isolation-after-commit.md), [Spring TransactionSynchronization 실전](transaction-synchronization.md)
- 횡단 관심사 선택 축은 [Filter, Interceptor, AOP](./filter-interceptor-aop.md)
- AOP 내부 동작 심화는 [Spring AOP와 프록시 심층 분석](./spring-aop-proxies-deep-dive.md)

## 컨테이너와 생명주기

- [Spring Framework vs Spring Boot](./spring-framework-vs-spring-boot.md) — 두 프로젝트의 경계와 자동 구성
- [IoC 컨테이너](./1_IoC_Container.md) — 스프링 프레임워크 기본
- [Application Context의 생명주기](./application-context-lifecycle.md)
- [InitializingBean](./initializing-bean.md) — 빈 초기화 콜백

## 트랜잭션

- [Spring Data JPA 트랜잭션 실수 모음](./jpa-transaction.md)
- [트랜잭션 전파·격리수준·AFTER_COMMIT 실전](./transaction-propagation-isolation-after-commit.md)
- [TransactionSynchronization 실전](./transaction-synchronization.md) — 커밋 이후 외부 호출을 안전하게 묶는 법
- [Spring 트랜잭션 전파, 커머스 주문/결제에서 실전으로 이해하기](./spring-transaction-propagation-commerce.md)

## JPA

- [JPA N+1](./jpa-n-plus-one.md) — 발생 원인, 탐지와 해결 선택지
- [JPA 벌크 변경과 트랜잭션 정합성](./jpa-bulk-update-isolation-and-consistency.md) — 영속성 컨텍스트, 낙관적 잠금, JDBC batch, bulk update

## 스케줄링

- [Spring 스케줄러 다중 인스턴스 안전성](./spring-scheduler-multi-instance-safety.md) — ShedLock, 분산 잠금, 리더 선출, 외부 스케줄러 선택

## 횡단 관심사 / AOP

- [Filter, Interceptor, AOP](./filter-interceptor-aop.md) — 요청 처리 파이프라인에서 무엇을 어디에 둘지 결정하는 비교/선택 가이드
- [DispatcherType과 서블릿 async 재디스패치](./servlet-async-dispatch.md) — Mono를 반환하면 preHandle이 두 번 도는 이유와 그때 깨지는 코드
- [Spring AOP와 프록시 심층 분석](./spring-aop-proxies-deep-dive.md) — JDK Dynamic Proxy, CGLIB, ByteBuddy
- [쿠버네티스에 올렸더니 X-Forwarded-For 가 사라졌다](./forwarded-headers-and-remote-ip.md) — 클라우드 플랫폼 감지로 자동으로 켜지는 forward-headers-strategy, RemoteIpValve 가 헤더를 소비하는 방식

## HTTP 클라이언트

- [RestClient](./rest-client.md)
- [WebClient가 큰 응답을 받으면 왜 죽는가](./webclient-max-in-memory-size.md) — maxInMemorySize, DataBufferLimitException, 컨테이너 메모리 limit과의 관계
