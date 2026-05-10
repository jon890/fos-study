# 톤 변환 빠른 참고

SKILL.md 의 함정 1, 3 회피 룰 적용 시 참조. 작성 직후 grep 매치된 표현을 이 표대로 치환.

## 코드명·내부 명칭 → 일반 표현

| 노출형 | 변환 |
|---|---|
| `@TransactionalEventListener(AFTER_COMMIT)` | "트랜잭션 커밋 후 이벤트 리스너" 또는 "커밋 이후 외부 발행" |
| `Propagation.REQUIRES_NEW` | "별도 트랜잭션" |
| `JPA Hibernate PostCommit` | "ORM 커밋 후 훅" |
| `Promise.allSettled` | "클라이언트 병렬 호출" |
| `AsyncItemProcessor` | "비동기 처리 / I/O 병렬화" |
| `@Async` 스레드풀 | "백그라운드 비동기" |
| `Welford's Online Algorithm` | "단일 패스 분산 계산 알고리즘" 또는 그대로 (알고리즘 명) |
| `ThreadLocalRandom` vs `SecureRandom` | "락 경합 없는 RNG로 교체" |
| `AliasMethod` | "가중치 랜덤 O(1) 알고리즘" |
| `StampedLock` writeLock + tryReadLock 2.5초 | "갱신 중 일관성 락" (수치는 본인 답변용 보존) |
| `AbstractPlayService`, `SpinOperationHandler` | "단일 템플릿", "핸들러 패턴" |
| `PostCommitUpdateEventListener` + Fanout | "트랜잭션 커밋 후 메시지 브로커로 변경 전파하는 패턴" |
| `StaticDataManager` 인터페이스 | "캐시 데이터를 인터페이스로 추상화" |
| ADR-XXX, ADR-059 같은 번호 | 빼고 내용만 풀어 쓰기 |
| `/planning`, `/plan-and-build` 슬래시 명령 | 빼거나 워크플로 단계 한국어로 |
| planner / critic / executor / docs-verifier | "계획 / 검증 / 실행 / 문서 정합성" |
| `Cut.sourceQuote` | "출력에 원작 인용 함께 받아 검증" |
| `ConfluenceDocumentMetadataProvider` 전략 패턴 | (빼고 핵심만 또는 통째 제거 — 어필 약하면 안 보강) |
| Envoy `drain_listeners`, `terminationGracePeriodSeconds`, supervisord `stopwaitsecs=17` | "트래픽 차단", "종료 대기 시간", "프로세스 매니저 강제 종료 유예" |
| pino, MSW, Testcontainers, ESLint, Prisma 직접 import | (Tech 라인에만 두거나 빼기. 본문 안에 라이브러리 함수 노출 X) |

## "내가 한 것" 강조 → 사실 진술

| PR 톤 | 사실 진술 |
|---|---|
| 직접 설계·구현했습니다 | 설계·구현을 맡았습니다 |
| 본인 주도 + 팀 전파 | 팀에 전파해 후속 X가 동일 구조 위에 얹히도록 정리 |
| 단독 구현 / 1인 구현 | 그냥 "구현" |
| 도입을 주도했습니다 | 도입했습니다 / 도입 작업을 맡았습니다 |
| 본인 작성·유지 N개 테스트 | N개 테스트 작성·유지 |
| 한 축의 커리어로 이어져 | (빼거나 사실 진술로) "X · Y · Z 도메인 경험" |
| 두 팀을 잇는 설계 자산으로 정착 | "이때 다듬은 패턴이 이후 X에 적용됨" |
| 작업 결을 보여주는 보조 경험 | (통째 제거) |
