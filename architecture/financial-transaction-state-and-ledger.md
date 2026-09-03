---
categories: [database]
tags: [학습중, 카카오뱅크, 금융도메인, 수신, 여신, 지급결제, 원장, 정합성, study]
---

# [학습중] 금융 거래 상태와 원장 설계

이 문서는 수신·여신·지급결제 서비스에서 돈의 상태가 어떻게 변하고, 그 변화를 원장에 어떻게 남기는지 공부하기 위해 만들었다.
학습 목표는 거래 상태와 잔액을 구분하고, 이중 기록과 불변 조건으로 오류를 탐지하며, 재시도에도 같은 거래를 한 번만 반영하는 설계를 설명하는 것이다.
완료 기준은 간단한 계좌이체를 상태 기계와 복식 원장으로 구현하고, 중복 요청·타임아웃·부분 실패 테스트를 통과시키는 것이다.

## 왜 금융 거래는 일반 상태 변경과 다른가

게시글의 상태를 `DRAFT`에서 `PUBLISHED`로 바꾸는 작업은 실패하면 다시 시도해도 대체로 안전하다.
돈을 옮기는 작업은 같은 명령이 두 번 적용되면 곧바로 손실이 생긴다.
응답이 유실됐을 때 클라이언트는 실패로 보지만 서버에서는 이미 원장 반영이 끝났을 수도 있다.

금융 백엔드는 다음 질문에 항상 답할 수 있어야 한다.

- 이 거래는 지금 어느 단계에 있는가.
- 고객이 사용할 수 있는 금액은 얼마인가.
- 실제로 확정된 금액은 얼마인가.
- 동일 요청이 다시 들어오면 이전 결과를 찾을 수 있는가.
- 잔액이 잘못됐다면 어떤 기록으로 재구성할 수 있는가.

핵심은 현재 잔액 한 칸만 믿지 않는 것이다.
잔액은 빠른 조회를 위한 파생 상태이고, 원장 항목이 금액 이동의 근거가 되어야 한다.

## 수신·여신·지급결제의 역할

**수신**은 고객으로부터 자금을 받아 계좌와 예금 상품으로 관리하는 영역이다.
입금, 출금, 이자 지급, 예금 만기, 지급 정지가 대표 흐름이다.

**여신**은 고객에게 자금을 빌려주고 회수하는 영역이다.
대출 실행, 원금 상환, 이자 발생, 연체, 중도 상환이 대표 흐름이다.

**지급결제**는 한 주체의 지급 지시를 다른 주체의 자금 수취로 연결하는 영역이다.
계좌이체, 카드 승인, 자동이체, 간편결제 충전과 인출이 이 범주에 들어간다.

세 영역은 상품 규칙이 다르지만 공통된 기술 문제를 가진다.

- 거래 명령과 회계 반영 사이의 상태 전이를 관리한다.
- 가용 잔액과 장부 잔액을 구분한다.
- 외부 기관과 상태가 어긋날 가능성을 전제로 한다.
- 이미 확정된 기록을 덮어쓰기보다 반대 기록으로 정정한다.

수신에서는 고객이 맡긴 돈을 언제 인출 가능한 상태로 볼지가 중요하다.
입금 전문을 받았다고 곧바로 가용 잔액을 늘릴지, 외부 결제망의 확정 이후에 늘릴지에 따라 상태가 달라진다.
여신에서는 대출 실행 원금, 아직 납부하지 않은 이자, 연체 금액을 같은 잔액으로 뭉개지 않는다.
각 금액의 발생 원인과 상환 순서를 별도 계정 또는 원장 속성으로 표현한다.
지급결제에서는 고객의 지급 지시, 자금 예약, 외부 전송, 최종 정산이 서로 다른 시점에 일어날 수 있다.
따라서 API 한 번의 성공 여부를 거래 전체의 완료 여부로 간주하지 않는다.

이 차이를 모델에 반영하면 상품별 세부 규칙이 달라도 공통된 처리 골격을 재사용할 수 있다.
명령을 검증하고, 자금을 예약하고, 원장에 반영하고, 외부 결과를 확인하고, 대사로 누락을 찾는 순서다.
공통 골격과 상품 정책을 분리하면 새로운 상품이 생겼을 때 원장 정합성 규칙을 다시 구현하는 위험도 줄어든다.

## 거래 상태와 원장 상태를 분리한다

거래 상태는 업무 절차의 진행 상황을 나타낸다.
원장 상태는 금액 변동이 회계적으로 반영됐는지를 나타낸다.

계좌이체의 단순화된 상태는 다음과 같이 표현할 수 있다.

```text
RECEIVED -> VALIDATED -> RESERVED -> POSTED -> COMPLETED
                |            |          |
                v            v          v
             REJECTED     RELEASED   REVERSAL_REQUIRED
```

`RESERVED`는 출금 계좌의 가용 잔액을 먼저 줄여 동시 출금을 막은 상태다.
`POSTED`는 차변과 대변 원장 항목이 같은 거래 묶음으로 확정된 상태다.
`COMPLETED`는 후속 알림이나 외부 결과 전달까지 끝난 업무 상태다.

원장 반영은 성공했는데 알림이 실패했다고 원장을 롤백해서는 안 된다.
알림은 재시도하고, 거래의 금전적 결과는 유지해야 한다.

## 장부 잔액과 가용 잔액

**장부 잔액**(ledger balance)은 확정된 원장 항목을 반영한 잔액이다.
**가용 잔액**(available balance)은 지금 고객이 추가로 사용할 수 있는 금액이다.

출금 요청이 승인 대기 중이면 장부 잔액은 그대로여도 가용 잔액은 줄어들 수 있다.
이 차이를 표현하지 않으면 동시에 들어온 두 출금이 모두 잔액 검사를 통과할 수 있다.

```text
장부 잔액 100,000원
출금 예약 30,000원
가용 잔액 70,000원
```

예약이 확정되면 장부 잔액이 70,000원으로 바뀌고 예약 금액은 사라진다.
예약이 취소되면 장부 잔액은 그대로이고 가용 잔액만 다시 100,000원이 된다.

## 복식 원장의 최소 모델

복식 원장은 한 거래가 둘 이상의 계정에 동일한 총액으로 반영되도록 만든다.
단순 계좌이체에서는 출금 계정에서 10,000원을 빼고 입금 계정에 10,000원을 더한다.

원장 구현에서 중요한 불변 조건은 다음과 같다.

- 한 거래 묶음의 차변 합과 대변 합이 같다.
- 원장 항목은 확정 후 수정하지 않는다.
- 모든 항목은 원래 업무 거래 식별자를 가진다.
- 같은 멱등성 키는 하나의 거래 결과에만 연결된다.
- 잔액은 원장 항목으로 다시 계산할 수 있다.

```sql
CREATE TABLE ledger_transaction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    transaction_key VARCHAR(80) NOT NULL,
    transaction_type VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    UNIQUE KEY uk_ledger_transaction_key (transaction_key)
);

CREATE TABLE ledger_entry (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    transaction_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    direction VARCHAR(10) NOT NULL,
    amount DECIMAL(19, 2) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    CONSTRAINT fk_entry_transaction
        FOREIGN KEY (transaction_id) REFERENCES ledger_transaction(id),
    CONSTRAINT ck_entry_amount CHECK (amount > 0)
);
```

`direction`을 부호 있는 금액 하나로 표현할 수도 있다.
어느 방식을 택하든 거래 단위 합계가 0이라는 불변 조건을 코드와 검증 쿼리로 보장해야 한다.

```sql
SELECT transaction_id,
       SUM(CASE WHEN direction = 'DEBIT' THEN amount ELSE -amount END) AS difference
FROM ledger_entry
GROUP BY transaction_id
HAVING difference <> 0;
```

이 쿼리 결과는 항상 비어 있어야 한다.
결과가 한 건이라도 나오면 단순 로그 경고가 아니라 금전 정합성 사고 후보로 다뤄야 한다.

## 잔액 스냅샷은 원장을 대체하지 않는다

매 요청마다 전체 원장을 합산하면 조회 비용이 계속 증가한다.
실무에서는 계좌별 잔액 스냅샷을 유지하고 원장과 같은 트랜잭션에서 갱신한다.

```sql
CREATE TABLE account_balance (
    account_id BIGINT PRIMARY KEY,
    ledger_balance DECIMAL(19, 2) NOT NULL,
    reserved_amount DECIMAL(19, 2) NOT NULL,
    version BIGINT NOT NULL
);
```

스냅샷은 성능을 위한 캐시와 비슷하지만 일반 캐시보다 강한 정합성 요구를 가진다.
원장과 잔액이 어긋나면 원장을 기준으로 잔액을 재구축할 수 있어야 한다.

## 멱등성과 동시성 제어

멱등성 키는 같은 업무 요청을 시간적으로 연결한다.
행 잠금이나 낙관적 잠금은 동시에 실행되는 요청의 충돌을 제어한다.
둘은 대체 관계가 아니다.

```java
@Transactional
public TransferResult transfer(TransferCommand command) {
    return transactionRepository.findByTransactionKey(command.transactionKey())
        .map(TransferResult::from)
        .orElseGet(() -> executeNewTransfer(command));
}

private TransferResult executeNewTransfer(TransferCommand command) {
    AccountBalance source = balanceRepository.findForUpdate(command.sourceAccountId())
        .orElseThrow();

    if (source.availableBalance().compareTo(command.amount()) < 0) {
        throw new InsufficientBalanceException();
    }

    LedgerTransaction transaction = ledgerWriter.postTransfer(command);
    balanceUpdater.apply(transaction);
    return TransferResult.from(transaction);
}
```

조회 후 삽입만으로 멱등성을 보장하려 하면 두 요청이 동시에 `없음`을 확인할 수 있다.
DB의 고유 제약을 최종 방어선으로 두고 중복 키 예외가 발생하면 기존 결과를 다시 조회해야 한다.

## 나쁜 설계와 개선된 설계

### 잔액만 직접 수정한다

```java
source.decrease(amount);
target.increase(amount);
```

이 코드는 결과 잔액은 남기지만 왜 변했는지 재구성하기 어렵다.
중간 실패가 발생하면 어느 계정까지 반영됐는지 판단할 근거도 약하다.

개선된 구조는 거래 묶음과 원장 항목을 먼저 정의하고, 같은 DB 트랜잭션에서 잔액 스냅샷을 갱신한다.

### 확정 기록을 UPDATE로 고친다

과거 원장 금액을 직접 수정하면 감사 추적과 시점별 잔액 재현이 깨진다.
잘못된 기록은 반대 방향의 정정 거래를 추가하고 원거래 식별자를 연결한다.

### 모든 후속 작업을 한 트랜잭션에 넣는다

외부 알림과 메시지 발행까지 DB 트랜잭션 안에서 기다리면 잠금과 커넥션 점유 시간이 길어진다.
금전 반영과 Outbox 저장까지만 같은 트랜잭션에 두고 외부 전달은 별도 처리한다.

관련 패턴은 [분산 트랜잭션과 Outbox 패턴 — 왜 2PC를 피하고 어떻게 대신할 것인가](./distributed-transaction-outbox-pattern.md)에서 더 깊게 다룬다.

## 로컬 실습

MySQL 하나로 작은 계좌이체 원장을 구현한다.

```bash
docker run --name ledger-mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=ledger_lab \
  -p 3307:3306 \
  -d mysql:8.4
```

실습은 다음 순서로 진행한다.

- 계좌 두 개와 초기 입금 원장 항목을 만든다.
- 동일한 `transaction_key`로 계좌이체를 동시에 두 번 호출한다.
- 거래 행과 원장 항목이 한 묶음만 생성되는지 확인한다.
- 원장 저장 직후 예외를 발생시켜 잔액까지 함께 롤백되는지 확인한다.
- Outbox 발행 전에 프로세스를 종료하고 재시작 후 다시 발행되는지 확인한다.
- 원장을 합산한 값과 `account_balance`를 비교하는 검증 쿼리를 실행한다.

성공 기준은 단순히 API가 200을 반환하는 것이 아니다.
중복 호출과 장애 주입 뒤에도 거래별 합계가 0이고 잔액 스냅샷이 원장 합계와 같아야 한다.

## 설명할 때의 답변 구조

금융 거래 정합성을 설명할 때는 제품 이름보다 불변 조건에서 시작한다.

> 거래 상태와 금액 반영 상태를 분리하고, 금액 이동은 수정 가능한 잔액 한 칸이 아니라 append-only 원장 항목으로 남깁니다. 같은 거래의 차변과 대변 합이 일치하도록 검증하고, 계좌 잔액은 조회 성능을 위한 스냅샷으로 관리하되 원장에서 재구축할 수 있게 합니다. 재시도에는 멱등성 키와 DB 고유 제약을 사용하고, 동시 출금에는 행 잠금이나 낙관적 잠금을 함께 적용합니다. 외부 메시지는 같은 트랜잭션에 Outbox를 저장해 이중 쓰기 문제를 줄입니다.

후속 질문에는 다음 근거를 붙인다.

- 가용 잔액과 장부 잔액이 왜 다른가.
- 멱등성 키와 잠금이 왜 둘 다 필요한가.
- 원장과 잔액이 어긋났을 때 무엇을 기준으로 복구하는가.
- 외부 시스템의 성공 여부가 불명확할 때 어떤 상태를 두는가.

## 학습 완료 체크리스트

- [ ] 수신·여신·지급결제의 공통 상태 모델을 설명할 수 있다.
- [ ] 거래 상태와 원장 반영 상태를 분리할 수 있다.
- [ ] 장부 잔액과 가용 잔액의 차이를 예로 설명할 수 있다.
- [ ] 차변과 대변 합계 불변 조건을 SQL로 검증할 수 있다.
- [ ] 잔액 스냅샷을 원장에서 재구축할 수 있다.
- [ ] 중복 요청과 동시 요청을 서로 다른 문제로 다룰 수 있다.
- [ ] 확정 원장을 수정하지 않고 정정 거래를 추가해야 하는 이유를 설명할 수 있다.
- [ ] 실패 주입 테스트로 원장과 잔액의 원자성을 검증했다.

## 참고 자료

- [SAP Help Portal — Universal Journal](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/651d8af3ea974ad1a4d74449122c620e/523b8a55559ad007e10000000a44538d.html)
- [MySQL 8.4 Reference Manual — InnoDB Transaction Model](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-model.html)
- [MySQL 8.4 Reference Manual — Locking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html)
- [AWS Prescriptive Guidance — Transactional Outbox Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
