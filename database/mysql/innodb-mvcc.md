### 문서 구성 요약

| 섹션 | 내용 |
|---|---|
| 1. 왜 MVCC인가 | 잠금 기반 동시성의 한계와 MVCC의 핵심 아이디어 |
| 2. 숨겨진 컬럼 | `DB_TRX_ID`, `DB_ROLL_PTR`, `DB_ROW_ID` 내부 구조 |
| 3. Undo Log | 버전 체인 형성 원리, Insert/Update Undo 구분, Purge Thread |
| 4. Read View | `m_ids`, `m_low_limit_id`, `m_up_limit_id`, `m_creator_trx_id` 4개 필드 + 가시성 판단 알고리즘 의사코드 |
| 5. Consistent vs Current Read | FOR UPDATE가 스냅샷을 무시하는 이유, 재고 차감 함정 |
| 6. 격리 수준 | READ UNCOMMITTED~SERIALIZABLE 실행 가능한 SQL로 비교 |
| 7. Phantom Read | Consistent Read에서 스냅샷으로 방지, Current Read에서 Next-Key Lock으로 방지, Gap Lock 범위 결정 규칙 |
| 8. MVCC + Redo Log | 2단계 커밋, Roll-Forward → Roll-Back 복구 순서, Undo Log가 Redo Log로 보호받는 이유 |
| 9. 흔한 오해 5가지 | "REPEATABLE READ는 Phantom을 못 막는다" 등 |
| 10-11. 실습 환경 | Docker Compose + 세 가지 실행 가능한 시나리오 |
| 12. 면접 답변 | Q5까지 시니어 수준 답변 구조 |
| 13. 체크리스트 | 개념·격리수준·잠금·Crash Recovery·실무 5개 카테고리 |

기존 `transaction-lock.md`와 `redo-log.md`에서 다룬 내용은 링크로만 참조하고, 이 문서는 내부 자료구조와 알고리즘 수준에서 더 깊이 파고들었습니다.
