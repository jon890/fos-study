---
categories: [database]
tags: [학습중, 카카오뱅크, 금융도메인, JPA, BulkUpdate, 트랜잭션격리, 잠금, 영속성컨텍스트]
---

# [학습중] JPA 벌크 변경과 트랜잭션 정합성

이 문서는 JPA 조회 최적화 다음 단계로 벌크 변경, 영속성 컨텍스트, 트랜잭션 격리, 잠금의 상호작용을 공부하기 위해 만들었다.
학습 목표는 생성된 SQL과 DB 동작을 기준으로 변경 전략을 선택하고, 벌크 쿼리 뒤의 오래된 엔티티와 동시 갱신 손실을 재현하는 것이다.
완료 기준은 동일 시나리오를 엔티티 변경 감지, JDBC batch, JPQL bulk update로 구현해 쿼리 수와 정합성 차이를 설명하는 것이다.

> 조회 페치 전략은 [JPA N+1 문제 완전 정복 — 발생 원인부터 EXPLAIN 분석까지](./jpa-n-plus-one.md)를 먼저 읽는다. 이 글은 N+1 설명을 반복하지 않고 쓰기 경로와 트랜잭션 충돌에 집중한다.

## 세 가지 변경 방식을 구분한다

JPA에서 여러 행을 바꾸는 방법은 비슷해 보이지만 실행 모델이 다르다.

- 엔티티를 조회하고 변경 감지로 UPDATE한다.
- 여러 엔티티 UPDATE를 JDBC batch로 묶는다.
- JPQL 또는 native SQL bulk update로 DB가 한 문장에 변경한다.

변경 감지는 도메인 메서드, 엔티티 이벤트, 낙관적 잠금과 잘 결합한다.
대신 엔티티 수만큼 메모리와 변경 감지 비용을 사용한다.

JDBC batch는 UPDATE 문 개수를 없애는 것이 아니라 네트워크 왕복을 묶는다.
bulk update는 엔티티를 로딩하지 않고 한 SQL로 많은 행을 변경한다.
그 대신 영속성 컨텍스트와 엔티티 생명주기를 우회한다.

## 벌크 쿼리가 만드는 가장 큰 함정

JPQL bulk update는 DB를 직접 변경하지만 이미 로딩된 엔티티는 자동으로 갱신하지 않는다.

```java
@Transactional
public void demonstrateStaleEntity(Long accountId) {
    Account account = accountRepository.findById(accountId).orElseThrow();

    accountRepository.freezeAllDormantAccounts();

    // DB는 FROZEN이지만 account 객체는 이전 상태일 수 있다.
    log.info("status={}", account.getStatus());
}
```

같은 트랜잭션 안에서 오래된 엔티티를 다시 변경하면 벌크 쿼리 결과를 덮어쓸 수도 있다.
그래서 벌크 변경 뒤에는 `clear()`로 영속성 컨텍스트를 비우거나 벌크 작업 자체를 별도 경계로 분리한다.

```java
@Modifying(clearAutomatically = true, flushAutomatically = true)
@Query("""
    update Account a
       set a.status = 'FROZEN'
     where a.lastActivityAt < :threshold
       and a.status = 'ACTIVE'
    """)
int freezeDormantAccounts(Instant threshold);
```

`clearAutomatically`는 문제를 감추는 마법이 아니다.
아직 flush되지 않은 변경이 있다면 먼저 반영할지, 버릴지 경계를 설계해야 한다.

## 벌크 변경은 낙관적 잠금을 우회할 수 있다

`@Version`을 사용하는 엔티티의 일반 UPDATE에는 버전 조건이 포함된다.

```sql
UPDATE account
SET status = ?, version = version + 1
WHERE id = ? AND version = ?;
```

JPQL bulk update에서 버전 증가와 조건을 직접 넣지 않으면 동시 변경을 감지하지 못할 수 있다.

```java
@Modifying
@Query("""
    update Account a
       set a.status = :nextStatus,
           a.version = a.version + 1
     where a.id = :accountId
       and a.version = :expectedVersion
    """)
int updateStatus(
    Long accountId,
    long expectedVersion,
    AccountStatus nextStatus
);
```

영향받은 행 수가 0이면 동시 변경 충돌 또는 조건 불일치로 판단한다.

## JDBC batch가 적합한 경우

각 엔티티의 도메인 규칙을 실행하면서 많은 행을 변경해야 한다면 JDBC batch가 절충안이 된다.

```yaml
spring:
  jpa:
    properties:
      hibernate.jdbc.batch_size: 50
      hibernate.order_updates: true
      hibernate.order_inserts: true
```

`hibernate.order_updates`는 같은 형태의 UPDATE를 모으는 데 도움을 주고 데드락 가능성을 낮출 수 있다.
정렬 비용도 있으므로 적용 전후를 측정해야 한다.

긴 작업에서는 일정 단위로 flush와 clear를 수행해 1차 캐시가 계속 커지지 않도록 한다.

```java
for (int index = 0; index < accounts.size(); index++) {
    accounts.get(index).recalculateGrade();

    if (index > 0 && index % 50 == 0) {
        entityManager.flush();
        entityManager.clear();
    }
}
```

clear 이후 기존 객체는 준영속 상태가 된다.
이 객체를 후속 로직에서 계속 사용하지 않도록 처리 단위를 분리한다.

## 격리 수준은 애플리케이션 규칙을 대신하지 않는다

MySQL InnoDB는 `READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ`, `SERIALIZABLE`을 지원한다.
기본 격리 수준은 `REPEATABLE READ`다.

격리 수준을 높이면 모든 동시성 문제가 자동으로 사라지는 것은 아니다.
어떤 행과 범위를 읽고 어떤 불변 조건을 지켜야 하는지 먼저 정의해야 한다.

예를 들어 잔액을 읽은 뒤 출금하는 코드는 일반 SELECT만으로 충분하지 않다.
다른 트랜잭션이 같은 잔액을 동시에 읽고 변경할 수 있기 때문이다.

```sql
START TRANSACTION;

SELECT ledger_balance, reserved_amount
FROM account_balance
WHERE account_id = 100
FOR UPDATE;

UPDATE account_balance
SET reserved_amount = reserved_amount + 10000
WHERE account_id = 100;

COMMIT;
```

`FOR UPDATE`는 조회한 인덱스 레코드에 변경을 위한 잠금을 건다.
검색 조건과 인덱스에 따라 잠금 범위가 달라질 수 있으므로 실행 계획과 실제 대기를 함께 확인한다.

## 낙관적 잠금과 비관적 잠금

낙관적 잠금은 충돌이 드물고 재시도가 가능한 업무에 적합하다.
DB 잠금을 오래 유지하지 않지만 충돌 뒤 전체 명령을 다시 평가해야 한다.

비관적 잠금은 같은 자원에 충돌이 잦고 처리 순서를 직렬화해야 할 때 고려한다.
대기 시간과 데드락 위험이 있으므로 트랜잭션을 짧게 유지해야 한다.

```java
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("select b from AccountBalance b where b.accountId = :accountId")
Optional<AccountBalance> findForUpdate(Long accountId);
```

외부 API 호출을 비관적 잠금 트랜잭션 안에서 수행하면 네트워크 지연 동안 행과 커넥션을 붙잡는다.
예약과 결과 반영을 짧은 트랜잭션으로 나누고 상태 기계로 연결하는 편이 안전하다.

## 데드락과 재시도 가능성을 함께 설계한다

비관적 잠금이 필요한 경우에도 잠금 획득 순서가 요청마다 다르면 데드락이 생길 수 있다.
계좌 A에서 B로 보내는 거래와 B에서 A로 보내는 거래가 동시에 실행되면 각 트랜잭션이 먼저 잡은 계좌를 놓지 않은 채 상대 계좌를 기다릴 수 있다.

두 계좌를 잠가야 한다면 식별자 정렬처럼 모든 요청이 따르는 일관된 순서를 정한다.

```java
List<Long> lockOrder = Stream.of(sourceAccountId, targetAccountId)
    .sorted()
    .toList();

List<AccountBalance> balances = lockOrder.stream()
    .map(id -> balanceRepository.findForUpdate(id).orElseThrow())
    .toList();
```

일관된 순서는 데드락 가능성을 줄이지만 완전히 없애지는 않는다.
DB가 데드락 피해 트랜잭션을 롤백하면 애플리케이션은 전체 업무 명령을 안전하게 다시 실행할 수 있어야 한다.

재시도에는 상한과 지수 백오프를 둔다.
같은 트랜잭션 객체나 영속성 컨텍스트를 재사용하지 않고 새 트랜잭션에서 명령을 다시 평가한다.
외부 부수 효과가 이미 일어날 수 있는 작업은 멱등성 키로 이전 결과를 먼저 확인한다.

데드락을 단순 예외 횟수로만 보지 않는다.
어떤 SQL과 인덱스 범위가 서로 기다렸는지 DB의 deadlock log를 확인한다.
벌크 UPDATE가 예상보다 넓은 범위를 스캔하면 많은 행과 gap을 잠가 충돌을 키울 수 있으므로 실행 계획도 함께 본다.

## N+1과 fetch 전략을 쓰기 경로에 연결한다

쓰기 작업 전에 연관 엔티티를 순회하면 N+1이 숨어들 수 있다.
무조건 fetch join으로 모든 컬렉션을 올리면 행 수 폭증과 메모리 사용이 발생한다.

선택 기준은 다음과 같다.

- 단건 aggregate 변경에는 필요한 연관을 명시적으로 가져온다.
- 대량 상태 변경에는 엔티티 전체 로딩 대신 bulk update 가능성을 검토한다.
- 도메인 규칙이 필요한 대량 변경에는 ID 페이지 조회와 batch 처리를 사용한다.
- 읽기 모델에는 DTO projection을 사용해 쓰기 aggregate와 분리한다.

## 나쁜 설계와 개선된 설계

### saveAll이면 한 번의 UPDATE라고 생각한다

`saveAll`은 SQL 한 문장을 의미하지 않는다.
엔티티별 UPDATE가 발생할 수 있으며 batch 설정과 ID 생성 전략에 따라 묶임 여부가 달라진다.
SQL 로그와 Hibernate 통계로 확인한다.

### bulk update 뒤 같은 엔티티를 계속 사용한다

1차 캐시가 DB보다 오래된 상태가 된다.
flush와 clear 경계를 명시하고 필요한 값은 다시 조회한다.

### 격리 수준을 SERIALIZABLE로 올린다

정합성은 강해질 수 있지만 동시성과 처리량 비용이 매우 크다.
보호할 불변 조건에 맞춰 고유 제약, 조건부 UPDATE, 잠금을 조합한다.

### 잠금 안에서 외부 IO를 호출한다

트랜잭션 시간이 네트워크 지연에 종속된다.
짧은 예약 트랜잭션과 결과 반영 트랜잭션으로 나누고 멱등성을 적용한다.

## 로컬 실습

계좌 1,000건을 만들고 다음 세 방식으로 상태를 변경한다.

- 엔티티를 모두 조회해 변경 감지한다.
- ID를 100건씩 조회하고 JDBC batch로 변경한다.
- 조건이 같은 행을 JPQL bulk update로 변경한다.

각 실험에서 다음을 기록한다.

- 실행된 SELECT와 UPDATE 수
- DB 왕복 시간
- 최대 영속성 컨텍스트 크기
- 동시에 다른 트랜잭션이 변경했을 때 결과
- `@Version` 값 변화

측정 결과에는 사용한 데이터 건수, 인덱스, 트랜잭션 격리 수준, batch 크기를 함께 남긴다.
이 조건이 빠지면 실행 시간 숫자만으로 다른 전략을 공정하게 비교할 수 없다.

오래된 엔티티 재현 테스트도 작성한다.

```java
@Test
void bulkUpdateLeavesManagedEntityStaleUntilClear() {
    Account managed = accountRepository.findById(accountId).orElseThrow();

    accountRepository.freezeDormantAccounts(threshold);

    assertThat(managed.getStatus()).isEqualTo(AccountStatus.ACTIVE);

    entityManager.clear();
    Account reloaded = accountRepository.findById(accountId).orElseThrow();
    assertThat(reloaded.getStatus()).isEqualTo(AccountStatus.FROZEN);
}
```

동시성 실험은 두 스레드가 같은 버전의 계좌를 읽게 한 뒤 동시에 상태를 바꾸도록 한다.
낙관적 잠금 예외, 비관적 잠금 대기, 조건부 UPDATE의 영향 행 수를 비교한다.

## 설명할 때의 답변 구조

> JPA 대량 변경은 변경 감지, JDBC batch, bulk update를 구분해 선택합니다. 도메인 규칙과 엔티티 이벤트가 필요하면 변경 감지와 batch를 사용하고, 동일 조건의 대량 상태 변경이면 bulk update를 고려합니다. bulk update는 영속성 컨텍스트와 @Version 처리를 자동으로 맞춰주지 않으므로 flush·clear와 버전 조건을 명시합니다. 동시성은 격리 수준만 높이기보다 불변 조건에 맞춰 고유 제약, 낙관적 잠금, SELECT FOR UPDATE를 선택하고 트랜잭션 안의 외부 IO를 피합니다.

## 학습 완료 체크리스트

- [ ] 변경 감지, JDBC batch, bulk update의 SQL 차이를 확인했다.
- [ ] bulk update 뒤 오래된 엔티티를 재현했다.
- [ ] flush와 clear 순서가 중요한 이유를 설명할 수 있다.
- [ ] bulk update에서 `@Version`을 직접 다뤘다.
- [ ] fetch join과 batch fetch의 적용 범위를 구분한다.
- [ ] MySQL 격리 수준과 consistent read를 설명할 수 있다.
- [ ] 낙관적 잠금과 비관적 잠금의 비용을 비교했다.
- [ ] `FOR UPDATE`의 잠금 범위를 인덱스와 연결해 설명할 수 있다.
- [ ] 트랜잭션 안에서 외부 IO를 피해야 하는 이유를 설명할 수 있다.

## 참고 자료

- [Hibernate ORM User Guide — Fetching and Batching](https://docs.hibernate.org/orm/6.6/userguide/html_single/)
- [Spring Data JPA — Locking](https://docs.spring.io/spring-data/jpa/reference/jpa/locking.html)
- [Spring Data JPA — Transactionality](https://docs.spring.io/spring-data/jpa/reference/jpa/transactions.html)
- [MySQL 8.0 Reference Manual — Transaction Isolation Levels](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html)
- [MySQL 8.4 Reference Manual — Locking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html)
