---
categories: [database]
tags: [학습중, 카카오뱅크, 금융도메인, 취소, 정정, 대사, 일마감, 배치]
---

# [학습중] 금융 거래 취소·정정·대사·일마감 운영

이 문서는 정상 거래보다 더 자주 운영자의 판단이 필요한 취소·정정·대사·일마감을 공부하기 위해 만들었다.
학습 목표는 확정 거래를 안전하게 되돌리는 방법, 내부 기록과 외부 결과의 차이를 찾는 방법, 영업일 단위로 장부를 닫는 방법을 하나의 운영 흐름으로 연결하는 것이다.
완료 기준은 불일치 데이터를 의도적으로 만들고, 대사 배치가 이를 분류하며, 정정 거래와 재실행으로 잔액을 복구하는 실습을 끝내는 것이다.

## 정상 처리보다 복구 경로가 더 중요하다

금융 거래는 요청과 응답이 한 번에 끝나는 것처럼 보여도 여러 시스템을 지난다.
내부 DB는 성공했지만 외부 기관 응답이 유실될 수 있다.
외부 기관은 성공했지만 내부 결과 저장이 실패할 수도 있다.

이때 단순 재시도는 같은 금액을 두 번 움직일 위험이 있다.
운영 가능한 시스템은 정상 경로뿐 아니라 다음 경로를 명시적으로 가진다.

- 아직 결과를 모르는 거래를 조회하고 확정한다.
- 잘못된 거래를 반대 거래로 상쇄한다.
- 두 시스템의 기록을 주기적으로 비교한다.
- 영업일 종료 시 미결 항목을 다음 날로 넘기거나 예외로 격리한다.
- 사람이 개입한 모든 결정을 감사 기록으로 남긴다.

## 취소와 정정은 같은 말이 아니다

**취소**는 아직 최종 확정되지 않은 거래를 무효화하는 동작이다.
예약된 금액을 해제하거나 승인 전 거래를 종료하는 흐름이 여기에 가깝다.

**정정**은 이미 확정된 결과가 잘못됐을 때 반대 효과를 가진 새 거래를 추가하는 동작이다.
확정 원장 항목을 UPDATE나 DELETE로 지우지 않는다.

**환불**은 고객에게 금액을 돌려주는 별도의 업무 거래다.
원거래와 연결되지만 처리 시점, 수수료, 한도, 외부 기관 상태가 다를 수 있다.

```text
원거래  T100: 고객 계정 -10,000 / 정산 계정 +10,000
정정거래 T101: 고객 계정 +10,000 / 정산 계정 -10,000
T101.original_transaction_id = T100
```

이 구조는 원거래가 존재했다는 사실과 이후 상쇄됐다는 사실을 모두 보존한다.

## 상태 기계에 불명확 상태를 넣는다

외부 호출 타임아웃을 곧바로 `FAILED`로 바꾸면 실제 외부 성공을 놓칠 수 있다.
결과를 모르는 상태를 별도로 두고 조회나 대사로 해소해야 한다.

```text
REQUESTED -> PROCESSING -> SUCCEEDED
                  |            |
                  v            v
               UNKNOWN      REVERSED
                  |
                  +-> SUCCEEDED
                  +-> FAILED
```

`UNKNOWN`은 기술적 실패가 아니라 판단 보류 상태다.
이 상태의 거래는 동일 명령을 다시 보내기 전에 외부 거래 식별자로 상태 조회를 시도한다.

## 대사는 무엇과 무엇을 비교하는가

대사(reconciliation)는 서로 독립적으로 기록된 두 데이터 집합이 같은 경제적 사실을 가리키는지 비교하는 작업이다.

대표 비교 축은 다음과 같다.

- 업무 거래 테이블과 내부 원장
- 내부 원장과 잔액 스냅샷
- 내부 거래와 외부 기관 거래 명세
- 원장과 회계 시스템 전표
- 전일 마감 잔액과 당일 기초 잔액

단순히 총액만 같다고 끝내면 안 된다.
한 건이 누락되고 다른 한 건이 중복돼도 총액은 우연히 같을 수 있다.
건별 일치와 집계 일치를 함께 확인해야 한다.

## 대사 키를 먼저 설계한다

대사는 비교 키가 없으면 시작할 수 없다.
내부 거래 식별자와 외부 기관 식별자를 양쪽에 보존해야 한다.

```sql
CREATE TABLE reconciliation_item (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    business_date DATE NOT NULL,
    internal_transaction_id VARCHAR(80),
    external_transaction_id VARCHAR(80),
    internal_amount DECIMAL(19, 2),
    external_amount DECIMAL(19, 2),
    result_type VARCHAR(30) NOT NULL,
    resolution_status VARCHAR(20) NOT NULL,
    detected_at TIMESTAMP(6) NOT NULL,
    resolved_at TIMESTAMP(6) NULL,
    UNIQUE KEY uk_reconciliation_pair (
        business_date,
        internal_transaction_id,
        external_transaction_id
    )
);
```

`result_type`은 최소한 다음 유형을 구분해야 한다.

- `MATCHED`: 양쪽에 있고 핵심 값이 같다.
- `INTERNAL_ONLY`: 내부에는 있지만 외부에는 없다.
- `EXTERNAL_ONLY`: 외부에는 있지만 내부에는 없다.
- `AMOUNT_MISMATCH`: 거래는 같지만 금액이 다르다.
- `STATUS_MISMATCH`: 금액은 같지만 성공·취소 상태가 다르다.
- `DUPLICATED`: 한쪽에 동일 거래가 여러 건 존재한다.

## 일마감은 날짜가 바뀌는 이벤트가 아니다

일마감(end-of-day close)은 특정 영업일의 거래를 더 이상 자유롭게 변경하지 못하도록 경계를 확정하는 운영 절차다.
달력 날짜와 영업일은 항상 같지 않다.
자정 이후 처리된 거래가 전 영업일에 속할 수도 있고 휴일 정책이 개입할 수도 있다.

마감에는 다음 입력이 필요하다.

- 영업일과 컷오프 시각
- 해당 영업일에 포함할 거래 상태
- `UNKNOWN`과 미결 거래의 이월 정책
- 외부 명세 도착 지연 허용 범위
- 마감 결과를 다시 열 수 있는 권한과 절차

마감 상태를 별도 엔티티로 관리하면 재실행과 운영 판단이 명확해진다.

```sql
CREATE TABLE business_day_close (
    business_date DATE PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    expected_count BIGINT NOT NULL,
    matched_count BIGINT NOT NULL,
    exception_count BIGINT NOT NULL,
    started_at TIMESTAMP(6),
    closed_at TIMESTAMP(6),
    version BIGINT NOT NULL
);
```

```text
OPEN -> CLOSING -> CLOSED
          |
          +-> BLOCKED
CLOSED -> REOPENED -> CLOSING
```

재마감이 필요하면 기존 결과를 덮어쓰기보다 실행 이력과 사유를 남긴다.

## 대사 배치의 처리 순서

대사 배치는 입력 파일을 읽어 테이블에 넣는 것만으로 끝나지 않는다.
재실행과 부분 실패를 견디는 단계 분리가 필요하다.

- 외부 명세의 파일 식별자와 체크섬을 검증한다.
- 원본을 변경하지 않는 staging 영역에 적재한다.
- 형식 오류와 중복 행을 격리한다.
- 거래 키로 내부 기록과 외부 기록을 매칭한다.
- 건별 차이와 집계 차이를 계산한다.
- 자동 복구 가능한 항목과 사람 판단이 필요한 항목을 분리한다.
- 마감 게이트를 평가하고 결과를 고정한다.

```java
public record ReconciliationDecision(
    ReconciliationType type,
    ResolutionAction action,
    String reason
) {}

public ReconciliationDecision compare(
    InternalTransaction internal,
    ExternalTransaction external
) {
    if (internal == null) {
        return new ReconciliationDecision(
            ReconciliationType.EXTERNAL_ONLY,
            ResolutionAction.INVESTIGATE,
            "외부 성공에 대응하는 내부 거래가 없음"
        );
    }
    if (external == null) {
        return new ReconciliationDecision(
            ReconciliationType.INTERNAL_ONLY,
            ResolutionAction.QUERY_EXTERNAL,
            "외부 명세에서 거래를 찾지 못함"
        );
    }
    if (internal.amount().compareTo(external.amount()) != 0) {
        return new ReconciliationDecision(
            ReconciliationType.AMOUNT_MISMATCH,
            ResolutionAction.MANUAL_REVIEW,
            "거래 금액 불일치"
        );
    }
    return new ReconciliationDecision(
        ReconciliationType.MATCHED,
        ResolutionAction.NONE,
        "일치"
    );
}
```

## 자동 정정의 경계를 좁힌다

모든 불일치를 자동 정정하면 잘못된 규칙이 대량 금액 이동으로 이어질 수 있다.
자동 처리 범위는 결정적이고 되돌릴 수 있는 경우로 제한한다.

자동화하기 좋은 사례는 이미 취소 확정된 예약 금액을 해제하는 작업이다.
사람 검토가 필요한 사례는 외부 성공 거래가 내부에 전혀 없거나 금액이 다른 경우다.

각 조치에는 다음 정보가 남아야 한다.

- 어떤 차이를 근거로 판단했는가.
- 어떤 규칙 버전이 결정을 내렸는가.
- 자동 처리인지 운영자 처리인지 구분된다.
- 원거래와 정정 거래가 서로 연결된다.
- 재실행해도 같은 조치가 중복 적용되지 않는다.

## 나쁜 설계와 개선된 설계

### 타임아웃을 실패로 확정한다

타임아웃은 결과를 받지 못했다는 뜻이지 외부 처리가 실패했다는 뜻이 아니다.
`UNKNOWN`으로 두고 거래 조회와 대사 경로로 넘긴다.

### 원거래 행을 수정한다

운영자가 원거래 금액이나 상태를 직접 바꾸면 당시의 사실과 수정 과정을 구분할 수 없다.
정정 명령과 반대 원장 항목을 추가한다.

### 총액만 비교한다

총액 일치는 필요한 조건이지만 충분하지 않다.
거래 식별자, 금액, 통화, 상태를 건별로 비교한 뒤 집계 검증을 추가한다.

### 배치 성공 여부만 본다

프로세스 exit code가 0이어도 예외 항목이 남아 마감을 막을 수 있다.
처리 건수, 매칭률, 미결 금액, 가장 오래된 미결 건의 나이를 함께 관찰한다.

## 로컬 실습

앞선 [금융 거래 상태와 원장 설계](./financial-transaction-state-and-ledger.md)의 테이블을 재사용한다.

다음 데이터를 의도적으로 만든다.

- 내부와 외부가 완전히 일치하는 거래
- 내부에만 존재하는 거래
- 외부에만 존재하는 거래
- 금액이 다른 거래
- 외부에는 취소됐지만 내부에는 성공으로 남은 거래
- 같은 외부 거래 식별자가 두 번 등장한 거래

대사 프로그램을 두 번 실행해 결과 행이 중복되지 않는지 확인한다.
일부 항목을 정정한 뒤 다시 실행해 `resolution_status`가 안정적으로 전이되는지 확인한다.

```sql
SELECT result_type,
       COUNT(*) AS item_count,
       SUM(ABS(COALESCE(internal_amount, 0) - COALESCE(external_amount, 0))) AS difference_amount
FROM reconciliation_item
WHERE business_date = DATE '2026-07-20'
GROUP BY result_type;
```

마감은 `exception_count = 0`만으로 결정하지 않는다.
허용된 이월 유형과 금액 한도를 정책으로 분리하고, 정책 버전을 마감 이력에 남긴다.

## 운영 대시보드에서 볼 지표

- 영업일별 거래 건수와 금액
- 대사 일치율과 불일치 금액
- `UNKNOWN` 상태 건수와 최고 체류 시간
- 자동 정정과 수동 정정 건수
- 마감 시작부터 완료까지 걸린 시간
- 재실행 횟수와 같은 항목의 반복 실패 횟수

개별 고객 거래 식별자나 계좌 정보는 일반 메트릭 라벨에 넣지 않는다.
고카디널리티와 개인정보 노출을 피하고, 상세 추적은 권한이 통제된 조회 도구로 분리한다.

## 설명할 때의 답변 구조

> 확정 전 취소와 확정 후 정정을 구분합니다. 외부 호출 타임아웃은 실패로 단정하지 않고 UNKNOWN 상태로 두며, 외부 거래 조회와 대사로 해소합니다. 확정 원장은 수정하지 않고 원거래를 참조하는 반대 원장 항목으로 상쇄합니다. 대사는 건별 키·금액·상태 비교와 집계 비교를 함께 수행하고, 일마감은 미결 항목과 외부 명세 도착 여부를 확인하는 영업일 게이트로 관리합니다. 배치는 멱등하게 재실행할 수 있어야 하며 자동 정정 범위는 결정적인 경우로 제한합니다.

이 답변 뒤에는 직접 만든 불일치 데이터와 재실행 테스트 결과를 설명해야 한다.
직접 운영 경험이 없다면 경험처럼 말하지 않고 어떤 실패를 재현했고 어떤 불변 조건을 검증했는지 구분한다.

## 학습 완료 체크리스트

- [ ] 취소, 환불, 정정의 차이를 설명할 수 있다.
- [ ] 외부 타임아웃에 `UNKNOWN` 상태가 필요한 이유를 설명할 수 있다.
- [ ] 건별 대사와 집계 대사를 함께 구현했다.
- [ ] 불일치 유형별 조치 정책을 분리했다.
- [ ] 확정 원장을 UPDATE하지 않고 정정 거래를 생성했다.
- [ ] 영업일과 달력 날짜의 차이를 모델에 반영했다.
- [ ] 대사 배치를 두 번 실행해도 결과가 중복되지 않는다.
- [ ] 마감 차단 조건과 이월 정책을 설명할 수 있다.
- [ ] 운영자 개입 기록과 규칙 버전을 보존한다.

## 참고 자료

- [SAP Help Portal — Universal Journal](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/651d8af3ea974ad1a4d74449122c620e/523b8a55559ad007e10000000a44538d.html)
- [MySQL 8.4 Reference Manual — InnoDB Transaction Model](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-model.html)
- [Spring Batch Reference Documentation](https://docs.spring.io/spring-batch/reference/)
- [AWS Prescriptive Guidance — Transactional Outbox Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
