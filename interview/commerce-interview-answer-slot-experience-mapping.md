# [초안] CJ푸드빌 디지털 채널 Back-end 면접 답변집 — 슬롯 도메인 경험을 커머스/F&B 설계로 번역하기

## 왜 이 문서가 필요한가

CJ푸드빌 디지털 채널 Back-end 포지션은 빕스·뚜레쥬르·계절밥상 등 매장 기반 외식·베이커리 브랜드의 주문·결제·멤버십·매장 운영 데이터를 다룬다. 반면 직전 경력은 NHN NSC 슬롯개발팀(2024.06\~2025.11)과 AI 서비스 개발팀(2025.12\~)이고, 도메인 표면만 보면 거리가 멀어 보인다. 면접관도 가장 먼저 떠올리는 의문이 "슬롯/AI 백엔드 한 사람이 외식 커머스 도메인을 빠르게 잡을 수 있는가"이다.

이 문서는 그 의문에 정면으로 답하기 위해, 슬롯 도메인에서 실제로 만들었던 코어 자산 — `SlotTemplate`/`BaseSlotService`, RCC(RTP Cache Control), 다중 서버 캐시 정합성, `StampedLock` 기반 정적 데이터 동시성, AliasMethod O(1) 가중치 랜덤, Kafka Transactional Outbox — 을 커머스/F&B 도메인 설계 어휘로 번역해 두는 답변집이다. 슬롯 용어를 사람이 알아듣게 풀어내는 것을 넘어, 같은 설계 패턴이 주문/결제/쿠폰/메뉴/매장 정책에서 어떻게 그대로 재사용되는지를 코드 수준에서 보여주는 것이 목적이다.

면접 흐름을 자기소개 → "왜 CJ푸드빌인가" → 도메인 전환 우려 → 기본기 검증 → 압박 질문 → 역질문 순으로 두고, 각 단계에서 30초·1분·2분 버전 답변을 짧게-길게-더 깊게 늘릴 수 있게 준비한다.

## 1. 자기소개 (Self Pitch)

### 30초 버전 (가장 좁은 자리 — 다대일 1라운드 인트로)

"4년차 자바 백엔드 김병태입니다. NHN에서 슬롯 게임 백엔드와 사내 AI 서비스 백엔드를 연속으로 다루며, 다중 서버 캐시 정합성과 트랜잭션-이벤트 발행 분리, 추상화-기반 도메인 확장에 집중해 왔습니다. 같은 기본기로 CJ푸드빌의 주문·결제·매장 정책을 풀어보고 싶어 지원했습니다."

### 1분 버전 (가장 자주 쓸 카드)

"4년차 자바 백엔드 개발자 김병태입니다. NHN에서 두 가지 성격이 다른 도메인을 연속으로 다뤘습니다. 슬롯개발팀에서는 동시 접속 환경의 게임 트랜잭션과 정적 설정 데이터 캐시 정합성, 비동기 후처리를 책임졌고, 직전에는 AI 서비스개발팀에서 사내 RAG용 OpenSearch 벡터 색인 배치 파이프라인을 처음부터 설계해 운영에 올렸습니다. 공통적으로 했던 일은 *반복되는 if-else를 본 다음에 추상화하기*, *트랜잭션 경계와 메시지 발행을 분리하기*, *다중 서버 환경에서 인메모리 캐시 정합성을 깨지지 않게 유지하기*, 이 세 가지였고, 이건 외식·커머스 도메인의 메뉴 마스터·매장 정책·주문·결제 흐름에도 그대로 통하는 기본기라고 생각해 지원했습니다."

### 2분 버전 — 프로젝트 3종 결합

자기소개를 길게 쓸 수 있는 자리에서는 다음 세 프로젝트를 한 줄씩 끼워 넣는다. 모두 CJ푸드빌이 운영해야 하는 시스템과 매핑되는 패턴이다.

- **슬롯 엔진 추상화**(`SlotTemplate` / `BaseSlotService`) — 슬롯 5종이 공통 흐름을 가졌지만 각자 다르게 살짝 변형되는 부분이 있어, 템플릿 메서드와 훅 메서드 조합으로 골격을 통일했다. *외식 커머스에서는 "포장/배달/매장 식사" 주문 플로우가 같은 골격에 결제 수단·배송 정책·할인 적용 시점만 다른 구조라 동일한 전략이 들어간다.*
- **RCC (RTP Cache Control) 백그라운드 캐시 시스템** — 무거운 계산 결과를 사전에 DB에 캐시해 요청 시점에 빠르게 내려주는 구조. *외식 도메인의 "혼잡도/대기시간 예측", "오늘의 메뉴 추천", "매장별 영업 가능 슬롯" 같은 컴퓨팅이 무거운 결과 캐시에 그대로 적용된다.*
- **Kafka Transactional Outbox** — 핵심 API의 동기 결과는 즉시 응답하고, 후처리(미션·통계·알림)는 메시지 유실 없이 비동기로 분리한 패턴. *주문 확정 → 포인트 적립/쿠폰 차감/CRM 발송/매장 KDS 푸시처럼 1차 트랜잭션 + N개 후처리 구조의 원형이다.*

## 2. 왜 CJ푸드빌인가

### 답변 본체

"두 가지 이유입니다.

첫째, **운영 트래픽이 시간대 편향이 강한 도메인**을 다뤄보고 싶었습니다. 슬롯도 평일 저녁 피크가 분명하고, 그 피크를 견디기 위해 캐시 사전 적재(RCC)와 백그라운드 워커 분리에 많은 시간을 썼습니다. 외식·베이커리는 점심·저녁·주말 브런치 피크가 더 뚜렷하고, 같은 피크 흡수 패턴 — 사전 캐시·결제 외부 호출 비동기 분리·재고/잔량 동시성 — 을 더 직접적으로 풀 수 있는 환경입니다.

둘째, **B2C 트랜잭션의 정합성이 사용자의 실제 돈/시간과 직결되는 도메인**이라는 점입니다. 게임 도메인에서도 한 번의 스핀 결과가 사용자 머니와 직결되어 있어 트랜잭션 경계와 메시지 발행 분리에 민감했고, 이걸 푸드빌 환경의 *주문 확정 vs 결제 승인 vs 재고 차감 vs 쿠폰 차감* 처럼 복수 시스템이 얽힌 트랜잭션으로 확장해보고 싶었습니다.

추가로, 이력서에 적어둔 RAG 배치 파이프라인 경험은 매장 운영 매뉴얼·메뉴 가이드·CS 응대 같은 사내 지식 자산을 LLM 기반 검색·추천으로 연결하는 시점에서 자연스럽게 활용 가능하다고 생각했습니다."

### 회사 도메인 키워드와 본인 카드 빠른 매핑

| 회사 측 도메인 | 슬롯/AI 경험에서 끌어올 카드 |
|----------------|------------------------------|
| 매장·메뉴 마스터 캐시 | 다중 서버 인메모리 캐시 정합성, MQ Fanout 무효화, `StampedLock` writeLock + `tryReadLock` |
| 주문 확정 → 후처리 N개 | Kafka Transactional Outbox, `@TransactionalEventListener(AFTER_COMMIT)` + `Propagation.REQUIRES_NEW` |
| 매장 혼잡도/대기시간 사전 계산 | RCC 사전 캐시, `RccSpinResultAnalyzer` 식의 매장별 전략 인터페이스 |
| 쿠폰/멤버십 한도·동시 사용 | DB 유니크 키 기반 동시성, 낙관적 락 vs 분산 락 선택 기준 |
| 메뉴 추천/노출 가중치 | AliasMethod O(1) 가중치 샘플링 |
| 주문 트래픽 피크 흡수 | `ThreadLocalRandom` / 스레드 안전 패턴, `@Async` 스레드풀 분리 |
| 매장 KDS·POS 외부 연동 장애 | graceful shutdown 503 제거 예산 설계, traceId 발행 시점부터 저장 |
| 사내 운영 매뉴얼·CS 지식 검색 | OpenSearch 벡터 색인 + Spring Batch 11 Step 분리 |

## 3. 도메인 전환 우려에 대한 정면 답변

면접관이 가장 직설적으로 던질 카드는 "외식/커머스 도메인 경험이 없는데 적응 가능한가"이다. 회피하지 않고, *도메인 표면이 다를 뿐 시스템 설계 단위는 동일하다*는 논리로 답한다.

### 핵심 메시지 3종

1. **도메인 어휘 학습은 2\~4주 단위 작업이고 설계 패턴 학습은 분기 단위 작업이다.** 슬롯 도메인을 잡을 때도 RTP·페이라인·Wild·Scatter·Free Spin 같은 어휘를 빠르게 흡수했지만, 정작 운영을 안정화한 건 어휘가 아니라 추상화·캐시 정합성·트랜잭션 경계 설계였다. CJ푸드빌의 메뉴 옵션 트리·주문 상태 머신·결제 PG 응답 코드 같은 어휘는 동일한 페이스로 학습 가능하다고 본다.
2. **이전 도메인의 경계가 더 강했지 더 약하지 않았다.** 게임 도메인은 결과 한 건이 1초 내 화면에 노출되고 사용자 머니와 직결돼 트랜잭션·로그·관측성에 더 빡빡한 기준을 요구했다. 외식 주문 도메인이 더 느슨하다는 의미가 아니라, *예외 케이스 사고 방식이 이미 트레이닝되어 있다*는 점을 어필한다.
3. **AI 서비스개발팀에서의 도메인 전환을 이미 한 번 성공했다.** 슬롯 → RAG/배치/LLM Gateway로의 전환에서 한 분기 안에 11 Step Spring Batch 파이프라인을 운영 수준으로 올렸다. 같은 스타일로 외식·커머스 도메인을 잡는다.

### 자주 받을 후속 질문 대응

- **"외식 산업 특화 이슈를 모르지 않나?"** — 모른다는 점을 인정하고, 학습 우선순위를 그 자리에서 명시한다. "메뉴 옵션 조합 폭발 → 주문 데이터 모델, 매장별 영업시간/휴무일 → 매장 정책 캐시, 일일 매출 마감 배치 → Spring Batch 적용, KDS/POS 연동 → 외부 시스템 통신과 idempotency. 이 순서로 잡겠습니다."
- **"외식 도메인 PM/기획자와 커뮤니케이션은?"** — 슬롯에서도 도메인 룰(잭팟 분배, RTP 보정)을 기획자와 직접 합의해야 했고, 결정 사항을 task 문서로 남겨 다른 개발자가 맥락 없이 읽어도 의도를 파악하게 만들었다(`task/**` 일관 포맷). 같은 문서화 습관을 그대로 가져간다.

## 4. 기본기 검증 질문 — 슬롯 카드를 푸드빌 답변으로 번역

### Q1. "트랜잭션과 메시지 발행을 어떻게 분리하나?"

슬롯에서는 *동기 핵심 처리(머니/레벨)* + *비동기 후처리(미션·통계·알림)* 분리를 위해 `@TransactionalEventListener(AFTER_COMMIT)` + `Propagation.REQUIRES_NEW` 기반 Kafka Outbox를 운영했다. 이걸 푸드빌 답변으로 옮기면 다음과 같다.

```java
@Service
@RequiredArgsConstructor
public class OrderConfirmService {

    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher events;

    @Transactional
    public Order confirm(OrderConfirmCommand cmd) {
        Order order = orderRepository.findByIdForUpdate(cmd.orderId());
        order.confirm(cmd.paidAt());
        events.publishEvent(new OrderConfirmedEvent(order.getId(), cmd.traceId()));
        return order;
    }
}

@Component
@RequiredArgsConstructor
public class OrderConfirmedEventHandler {

    private final OutboxStore outbox;
    private final KafkaTemplate<String, byte[]> kafka;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void on(OrderConfirmedEvent ev) {
        try {
            kafka.send("order.confirmed", ev.orderId().toString(), serialize(ev)).get();
        } catch (Exception e) {
            saveFailed(ev, e);
        }
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    void saveFailed(OrderConfirmedEvent ev, Exception e) {
        outbox.save(OutboxEntry.failed(ev, e, ev.traceId()));
    }
}
```

답변 포인트:
- **`AFTER_COMMIT`이어야 하는 이유** — 주문 트랜잭션이 롤백된 상황에서 메시지가 이미 떠나면 포인트 적립·쿠폰 차감·KDS 푸시가 거짓으로 일어난다.
- **`REQUIRES_NEW`이어야 하는 이유** — 발행 실패를 기록하는 트랜잭션이 외부 트랜잭션과 묶이면 *발행 실패 기록도 같이 롤백*되는 사고가 발생한다. 별도 트랜잭션이어야 실패가 살아남는다.
- **traceId** — 매장 KDS 미수신 클레임이 들어왔을 때 어디 단계에서 끊겼는지 1분 안에 추적할 수 있게 발행 시점부터 같이 저장한다.

### Q2. "메뉴/매장 마스터처럼 잘 안 바뀌는 데이터를 어떻게 캐시하나?"

슬롯에서 했던 *MQ Fanout 기반 다중 서버 인메모리 캐시 정합성 + `StampedLock`* 패턴을 그대로 옮긴다.

```java
public class MenuMasterCache implements StaticDataManager<Long, Menu> {

    private final StampedLock lock = new StampedLock();
    private volatile Map<Long, Menu> snapshot = Map.of();

    public Menu get(Long menuId) {
        long stamp = lock.tryReadLock(2_500, MILLISECONDS);
        if (stamp == 0L) throw new MenuCacheBusyException(menuId);
        try {
            return snapshot.get(menuId);
        } finally {
            lock.unlockRead(stamp);
        }
    }

    public void refresh(Set<Long> changedIds, MenuLoader loader) {
        Map<Long, Menu> next = new HashMap<>(snapshot);
        loader.loadAll(changedIds).forEach(m -> next.put(m.id(), m));
        long stamp = lock.writeLock();
        try {
            snapshot = Map.copyOf(next);
        } finally {
            lock.unlockWrite(stamp);
        }
    }
}
```

푸드빌 면접에서 이 카드가 강한 이유는:
- 메뉴 마스터·옵션 트리·매장 영업시간·정책 플래그처럼 *조회는 초당 수천, 변경은 하루 수십*인 데이터가 외식 도메인에 흔하다.
- 어드민에서 메뉴를 변경하면 모든 서버가 동시에 *해당 메뉴만* 갱신해야 한다. Hibernate `PostCommitUpdateEventListener` → MQ Fanout → 각 서버 큐 수신은 그 그림에 정확히 맞는다.
- `tryReadLock(2.5s)` 타임아웃을 두는 이유는 갱신 중인 서버에서 무한 대기하지 않고 *메뉴 캐시 일시 미사용 fallback*으로 빠지게 만드는 운영 안전장치이다.

### Q3. "동시성 — 쿠폰 한도, 재고 차감은 어떻게 다루나?"

슬롯에서의 의사결정 — *충돌 빈도 낮음 + 정확성 절대 필요* → DB 유니크 키 + 예외 처리, *정적 데이터 갱신 + 읽기 압도적* → `StampedLock` — 을 그대로 푸드빌 카드로 옮기면 다음과 같다.

- **선착순 쿠폰**: Redis `INCR` 기반 카운터로 1차 컷 + DB의 `UNIQUE(coupon_id, user_id)`로 최종 보장. 분산 락(Redisson)은 핫 키에서만 선택적으로 적용.
- **매장 재고 차감**: 단일 매장 내라면 `SELECT ... FOR UPDATE` + 짧은 트랜잭션. 다매장 동시 차감 같은 고난도는 *Saga + 보상 트랜잭션* 으로 나간다고 답한다.
- **포인트 적립 멱등성**: 주문 ID 기반 idempotency key. Outbox로 한 번 더 발행되더라도 동일 키 충돌 시 무시.

### Q4. "메뉴 추천이나 노출 슬롯에 가중치를 둬야 한다면?"

AliasMethod O(1) 가중치 랜덤을 그대로 인용한다. 슬롯에서 100만 회 시뮬레이션 시 누적합 O(n) 방식이 병목이었던 사례가 있고, 멀티스레드 환경에서 `SecureRandom`은 내부 `synchronized`로 락 경합이 누적된다는 점을 근거로 `ThreadLocalRandom`으로 교체한 의사결정을 들 수 있다. 외식 도메인에서는 다음 사례에 적용 가능하다고 답한다.

- 추천 메뉴 슬롯의 **가중치 기반 노출** — 신메뉴 가중치 부스팅, 매장별 우선순위 다름.
- A/B 테스트 트래픽 분배 — 고정 비율로 빠르게 뽑아야 할 때.
- 주의 — 추천이 *결정적*이어야 할 때(개인화 결과 안정성)는 가중치 랜덤 대신 해시 기반 분배가 맞다는 trade-off도 같이 말한다.

### Q5. "EXPLAIN과 인덱스 — 자가 진단상 약점인데 어떻게 보완 중인가?"

정직하게 약점이라고 인정하고 *학습 경로*를 보여준다. RCC 캐시 충족 판정 쿼리를 복합 인덱스로 튜닝한 실 사례([`task/nsc-slot/rcc-rtp-cache-control.md`](../task/nsc-slot/rcc-rtp-cache-control.md)) 한 건을 가져온다.

- *type, key, rows, Extra* 네 컬럼을 우선 본다. `Using filesort`, `Using temporary`가 보이면 인덱스 설계 재검토.
- 복합 인덱스의 **leftmost prefix** 규칙, 커버링 인덱스로 IO 줄이기, InnoDB의 클러스터드 인덱스 특성 — 면접 직전까지 study-pack을 반복 학습 중이라고 답한다.
- 외식 도메인 적용 예 — `(store_id, ordered_at, status)` 조합이 매장별 특정일 주문 조회의 80%를 흡수할 수 있다는 식의 가상 시나리오로 실제 토론까지 끌어간다.

### Q6. "장애가 나면 첫 5분 동안 무엇을 보나?"

AI 서비스팀에서 직접 풀었던 *graceful shutdown 503 제거* 사례([`task/ai-service-team/graceful-shutdown-503-fix.md`](../task/ai-service-team/graceful-shutdown-503-fix.md))를 5분 응답 매뉴얼로 변환해 답한다.

```text
[T+0~30s]   영향 범위 확인 — error rate, latency p95, 5xx ratio 세 가지 동시 확인
[T+30~90s]  traceId 단위로 가장 짧은 실패 경로 한 건을 끝까지 따라간다
[T+90~180s] 외부 의존(PG, POS, KDS, Redis, Kafka) 응답 코드 / lag / circuit 상태
[T+180~300s] 직전 배포·설정 변경 diff, 피크 임박 여부, fallback / kill switch 가능 여부
```

답변 포인트:
- **지표 → 표본 → 의존 → 직전 변경** 순서가 정해져 있어야 사고 직후 머리가 비어도 따라갈 수 있다.
- traceId가 발행 시점부터 저장돼 있어야 위 흐름이 1분 내로 줄어든다. Outbox 답변(Q1)과 자연스럽게 연결된다.
- "원인 미상이라도 일단 사용자 영향을 줄이는 카드 — circuit, fallback, rate limit — 를 먼저 작동시킨다"가 직전에 만들었던 503 예산 설계의 핵심이었다고 말한다.

### Q7. "MyBatis와 JSP/jQuery 레거시가 섞여 있다면?"

직접 경험은 *제한적*이라는 점을 인정한 뒤, **이미 잡힌 다른 도메인의 레거시 전환 경험과 코드 읽기 속도**로 답을 메운다.

- *어색하지만 못 다루지 않는다.* JPA 중심으로 운영했지만 MyBatis XML mapper, 동적 SQL(`<if>`, `<foreach>`), resultMap은 SI 시절에 직접 다뤘다. 첫 1\~2주는 *기존 mapper / resultMap 컨벤션을 통째로 읽고 따라간다*가 기본 원칙이라고 답한다.
- *세션 기반 인증과 토큰 인증이 공존하는 환경*은 SB 개발팀 시절 KYC 시스템 + 모바일 토큰 인증 분리를 같은 코드베이스에서 운영해 본 적이 있다고 답한다.
- 점진적 마이그레이션 시 **Strangler Fig 패턴** — 화면 단위로 새 API/SPA를 끼우되 기존 화면은 살려둔다 — 의 위험 관리법을 짧게 설명한다. 큰 빅뱅보다 *작은 단위 + 회수 가능성 확보*가 항상 안전하다.

### Q8. "정량 TPS 숫자가 자료에 없는데, 그게 운영 경험이라 할 수 있나?"

회피 금지. *측정하지 않은 부분은 측정하지 않았다고 명시*하고, 측정한 부분만 정확히 말한다.

- "이력서·task 문서에 *부풀린 TPS를 적지 않았기 때문에* 자료에 숫자가 없습니다. 슬롯 도메인은 정확한 운영 TPS 공개가 회사 보안 정책에 묶여 있었습니다."
- 대신 *측정 단위가 명확한 결과*는 그 자리에서 인용한다. JMH 기준 `ThreadLocalRandom` **70.241 ops/s** vs `SecureRandom` **1.197 ops/s** (`task/nsc-slot/slot-spin-performance.md`), 447개 테스트 파일 운영 등 출처가 분명한 숫자.
- "운영 감각은 TPS 숫자보다 *피크 시간대 어떤 카드를 사전 적재했고, 어떤 호출을 비동기로 떼냈는지, 어떤 fallback을 두었는지*로 증명한다고 생각합니다. 그 카드는 RCC·Outbox·503 예산 설계 세 가지로 보여드릴 수 있습니다." 로 정면 돌파한다.

### Q9. "무거운 계산 결과를 미리 캐시해서 응답 시간을 줄인다 — 푸드빌에 적용한다면?"

슬롯에서 운영한 RCC(RTP Cache Control) 패턴이 그대로 옮겨가는 카드다. 슬롯에서는 *"좋은 결과"* 를 사전에 DB에 캐시해 두고, 사용자 요청 시점에 즉시 내려준 뒤 다음 캐시를 비동기로 생성했다. 푸드빌에서는 *매장 혼잡도·픽업 대기시간·예약 가능 슬롯* 같이 계산 비용이 크고 짧은 시간 안에 결과가 자주 바뀌지 않는 데이터가 같은 패턴에 정확히 들어맞는다.

```java
@Service
@RequiredArgsConstructor
public class StoreCongestionService {

    private final StoreCongestionCacheRepository cache;
    private final StoreCongestionCalculator calculator;
    private final ApplicationEventPublisher events;

    @Transactional(readOnly = true)
    public StoreCongestion query(long storeId, LocalDateTime requestedAt) {
        StoreCongestionCache hit = cache.findValid(storeId, requestedAt).orElse(null);
        if (hit != null) {
            events.publishEvent(new CongestionPrefetchEvent(storeId, requestedAt.plusMinutes(15)));
            return hit.toView();
        }
        return calculator.fallback(storeId, requestedAt);
    }
}

@Component
@RequiredArgsConstructor
public class CongestionPrefetchHandler {

    private final StoreCongestionCacheRepository cache;
    private final StoreCongestionCalculator calculator;

    @Async("congestionPrefetchExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onPrefetch(CongestionPrefetchEvent ev) {
        try {
            cache.upsert(calculator.compute(ev.storeId(), ev.targetTime()));
        } catch (DuplicateKeyException dup) {
            // 동시 prefetch 충돌 — 다른 워커가 이미 채움. 정상 케이스로 처리.
        }
    }
}
```

답변 포인트:
- **언제 사전 캐시를 쓰는가** — 계산 비용 ≥ N00ms + 결과 유효 시간 ≥ 분 단위 + 동일 결과 재사용 가능. 셋 중 하나라도 깨지면 *실시간 계산이 더 정직하다*는 의사결정을 슬롯 운영에서 배웠다.
- **캐시 미스 fallback** — 슬롯은 "좋은 결과 없으면 일반 스핀"으로 빠졌다. 푸드빌은 *직전 10분 평균값*이나 *해당 요일·시간대 평균*으로 빠지면 사용자 체감 끊김 없이 흡수된다.
- **충돌 처리는 DB 유니크 키 우선** — `(store_id, target_window)` 유니크 키 + `DuplicateKeyException` 무시. 분산 락(Redisson)은 *충돌 빈도를 측정한 뒤* 도입한다는 의사결정 원칙도 함께 말한다.
- **피크 전 워밍** — 점심 11:30, 저녁 18:00 같은 확정 피크에는 prefetch 트리거를 10\~15분 앞당겨 사전 적재. RCC 운영에서 "스핀 직전이 아니라 그 전 분기에 캐시를 만들었다"는 디테일을 그대로 인용 가능.
- **관측성** — RCC 운영 시 캐시 히트/미스/생성 실패를 로그 테이블 컬럼으로 따로 떼서 봤다. 푸드빌 환경에서도 매장별 prefetch 성공률을 대시보드에 두면 *어느 매장이 정책 변경을 자주 받는지*가 자연스럽게 보인다.

## 5. 압박 질문 정면 대응

기본기 질문 외에 면접 후반에 던지는 *압박 질문*에 정직-방어 균형을 잡는 카드를 정리한다. 약점을 인정하면서 *학습 경로*로 즉시 연결하는 게 패턴이다.

| 질문 유형 | 위험 답변 | 권장 답변 패턴 |
|----------|-----------|---------------|
| "외식 도메인 경험 없는데 왜 외식인가" | "공부하면 됩니다" 식 추상 답변 | 시간대 편향·B2C 트랜잭션 정합성·RAG 활용 가능성 3축으로 *이미 본인 카드와 매칭된 이유*를 말함 |
| "왜 다른 커머스(이커머스/패션) 아닌가" | 회사 비교 발언 | "오프라인 매장 + 디지털 채널의 *KDS/POS 연동 비동기 정합성*은 일반 이커머스보다 본인의 Outbox·캐시 정합성 경험과 더 가까움"이라고 답함 |
| "Kotlin 안 쓰는데 괜찮나" | 학습 가능성만 강조 | Java 17/21 운영 + Spring Boot 3.x 깊이가 우선, Kotlin은 *공식 시작일 기준 1\~2주 안에 일상 코드 쓰기 가능* 라인을 분명히 함 |
| "TPS / 팀 규모 / 매출 영향 숫자 안 나오는데" | 회피 또는 추측 | "출처 문서에 기재 없는 숫자는 추측하지 않는다"가 본인의 운영 원칙이라고 답함 (Q8와 동일) |
| "AI 협업 비중이 너무 높지 않은가 — 본인 실력이 흐려 보일까 봐 우려" | 부정 | *에이전트 파이프라인 설계자* 레벨로 본인 일을 정의한다. plan/critic/executor/docs-verifier를 본인이 설계했고, 결과물 검토는 사람이 한다는 점을 강조 |
| "DB는 약점이라고 자가 진단했다는데 그럼 채용해도 되나" | "지금부터 공부합니다"만 | study-pack 토픽 큐 — composite-index / EXPLAIN / mysql-index-explain-commerce-api — 를 그 자리에서 보여주며 *진행 중인 작업물*로 답함 |

### 약점을 강점으로 옮기는 한 줄 패턴

- "현재 부족한 영역은 X이고, 보완 중인 자산은 Y이고, 입사 후 한 분기 안에 도달하려는 수준은 Z입니다."
- 이 한 줄을 머릿속에 박아두면 모든 압박 질문이 *학습 로드맵 답변*으로 흡수된다.

## 6. 슬롯 → 외식 도메인 어휘 매핑 사전

면접 중 슬롯 용어를 무심코 꺼냈을 때 *바로 외식 용어로 다시 표현*할 수 있도록 단어 단위 변환 카드를 둔다.

| 슬롯 도메인 어휘 | 외식·F&B 커머스 어휘 | 같은 설계 패턴 |
|------------------|----------------------|----------------|
| 스핀 / 1회 게임 결과 | 주문 1건 / 결제 1건 | 트랜잭션 경계와 동기 응답 |
| RTP (return-to-player) | 매장 정산 마진 / 프로모션 비용율 | 사후 측정 + 정책 보정 |
| 잭팟 풀 | 이벤트 한정 수량·선착순 쿠폰 풀 | 동시성·재고 차감·중복 사용 방지 |
| 페이라인·심볼 매트릭스 | 메뉴-옵션 트리·주문 라인 아이템 | 정적 마스터 데이터 + 캐시 정합성 |
| Free Spin / 보너스 게임 | 1+1·BOGO 프로모션 | 정책 엔진·할인 우선순위 |
| 슬롯 5종·기능 변형 | 브랜드 N종·매장 N종·옵션 N종 | 템플릿 메서드 + 훅 메서드 추상화 |
| RCC 사전 캐시 | 매장 혼잡도/대기시간 사전 계산 | 백그라운드 워커 + 사전 적재 |
| 스핀 후처리(미션·통계) | 주문 후처리(포인트·CRM·KDS 푸시) | Kafka Outbox 비동기 분리 |
| 정적 설정 데이터 | 메뉴 마스터·매장 정책 | MQ Fanout + StampedLock |
| AI 에이전트 룰셋 | 브랜드별 도메인 정책 가이드 | 도메인 문서화 + 검토 first |

이 표를 자기소개 직전 5분 동안 한 번 훑고 들어가면 슬롯 용어가 새어 나가는 것을 막을 수 있다.

## 7. 마무리 질문 (역질문)

면접 마지막에 던질 질문도 도메인 적합성을 보여주는 도구다.

- "메뉴 마스터·매장 정책 같은 *변경 빈도가 낮은 데이터*의 캐시 무효화는 현재 어떤 패턴으로 운영되고 있나요? 인메모리 캐시 다중 인스턴스 정합성을 어떻게 보장하시는지가 궁금합니다."
- "주문 확정 후 포인트·쿠폰·매장 KDS·CRM 발송 같은 후처리는 동기인가요, 비동기인가요? Outbox나 Saga 같은 패턴이 도입되어 있는지 궁금합니다."
- "AI 활용은 어디까지 와 있나요? 매장 매뉴얼/CS 응대/추천 셋 중 우선순위가 어디인지 알고 싶습니다."
- "디지털 채널 백엔드 팀은 매장 POS/KDS와의 통신 장애에 대해 어떤 첫 5분 매뉴얼을 갖고 있나요? 운영 관측성 측면에서 합류 직후 가장 먼저 익혀야 할 것이 무엇인지 듣고 싶습니다."

이 네 질문 모두, 답을 듣고 나서 *"제 슬롯/AI 경험에서 X 부분이 그대로 도움이 될 것 같다"*로 자연스럽게 연결할 수 있게 설계했다.

## 8. 자기 점검 체크리스트

- [ ] 30초·1분·2분 자기소개를 모두 외워서, 면접관 컷오프 시 즉시 다음 버전으로 점프할 수 있다.
- [ ] 슬롯 도메인 어휘(RTP·잭팟·Wild·Scatter·페이라인) 없이도 같은 설계 카드를 외식 어휘(메뉴·매장·옵션·재고·쿠폰)로 30초 안에 다시 설명할 수 있다.
- [ ] `@TransactionalEventListener(AFTER_COMMIT)`과 `Propagation.REQUIRES_NEW`가 *왜* 필요한지 한 문장으로 답한다.
- [ ] 다중 서버 인메모리 캐시 정합성을 *MQ Fanout + StampedLock + tryReadLock 타임아웃* 세 단계로 그림 없이 말로 설명한다.
- [ ] AliasMethod와 누적합 O(n) 방식의 차이를 종이 한 장에 그릴 수 있다.
- [ ] EXPLAIN 컬럼 네 가지(type / key / rows / Extra)를 외식 도메인 가상 쿼리에 즉석 적용해 본다.
- [ ] "외식 도메인 모르지 않냐" 질문에 *학습 우선순위 4종*을 막힘 없이 말한다.
- [ ] 장애 첫 5분 매뉴얼(지표 → 표본 → 의존 → 직전 변경)을 30초 안에 읊는다.
- [ ] "TPS 숫자 없는데 운영 경험인가" 질문에 *측정 기준·출처 원칙*으로 정면 돌파한다.
- [ ] 슬롯 → 외식 어휘 매핑 사전을 면접 직전 5분 안에 한 번 훑는다.
- [ ] 역질문 4종을 외워둔다.

## 9. 면접 직전 5분 cheatsheet

면접실 입장 직전에 종이 한 장으로 훑을 핵심 키워드만 모아둔다. 길게 외운 답변이 무너져도 이 카드가 살아 있으면 핵심 메시지는 회수 가능하다.

### 한 줄 자기 정체성

"운영 안정성·트랜잭션 경계·캐시 정합성을 자사 서비스 백엔드 관점으로 풀어 본 4년차+ 시니어 Java 백엔드 개발자."

### 5초 답변용 키워드 카드

| 질문 패턴 | 핵심 키워드 |
|----------|-------------|
| 자기소개 | 슬롯/AI 두 도메인 연속, 캐시 정합성·Outbox·추상화 3축, 같은 기본기를 푸드빌로 |
| 왜 푸드빌인가 | 시간대 편향 피크 + B2C 트랜잭션 정합성 + 매장 운영 매뉴얼 RAG 활용 |
| 캐시 정합성 | MQ Fanout + StampedLock writeLock + tryReadLock 2.5s 타임아웃 |
| 트랜잭션-메시지 | AFTER_COMMIT으로 거짓 후처리 차단 + REQUIRES_NEW로 실패 기록 보존 |
| 동시성 선택 | 충돌 빈도 측정 → DB 유니크 키 우선 → 분산 락은 핫 키 한정 |
| 가중치 샘플링 | AliasMethod O(1) + ThreadLocalRandom, JMH 58배 근거 |
| 성능 의사결정 | 측정 → 의사결정 → 측정. JMH·EXPLAIN·로그 컬럼 셋 중 하나는 항상 |
| 사전 캐시 (RCC) | 계산 비용 큰 + 분 단위 유효 + 피크 전 워밍 + DB 유니크 키 충돌 처리 |
| 약점(DB) | EXPLAIN type/key/rows/Extra 4컬럼 + leftmost prefix + 커버링 인덱스 |
| 장애 첫 5분 | 지표 → traceId 표본 → 외부 의존 → 직전 변경 diff |
| TPS 숫자 | 출처 없으면 만들지 않음. JMH 70.241 ops/s 같은 측정된 부분만 인용 |
| MyBatis/JSP | SI 시절 직접 경험. 신규는 JPA 중심. 기존 컨벤션을 1\~2주 흡수 후 따라감 |
| Kotlin | Java 17·21 깊이 우선. Kotlin은 1\~2주 안에 일상 코드 작성 가능 라인 |

### 호흡이 무너졌을 때 회복 문장 3종

- "질문을 한 번만 다시 정리해 주실 수 있을까요." — 5초 시간을 확보한다.
- "정확히 측정된 부분과 그렇지 않은 부분을 나눠서 답변드리겠습니다." — 숫자 압박을 정직-방어로 흡수한다.
- "슬롯 도메인에서는 X였고, 푸드빌에서는 Y가 더 적합할 것 같습니다." — 도메인 차이 질문을 학습 답변으로 회수한다.

### 절대 말하지 않을 단어

- "잘 모르겠지만 공부하면 됩니다" — *학습 우선순위 4종* 카드(메뉴 옵션 모델 → 매장 정책 캐시 → 마감 배치 → KDS/POS 연동)로 대체.
- "TPS 약 N입니다" (출처 미상 수치) — "측정 단위·측정 시점·체감 변화 기준으로 말씀드리면..." 으로 대체.
- "AI가 대신 짜줬습니다" — *에이전트 파이프라인 설계자* 라는 정체성 문장과 *검토는 사람이 한다* 원칙으로 대체.

### 마지막 30초 — 입장 직전 묵상

1. 슬롯 어휘(RTP·페이라인·잭팟·Wild·Scatter)는 외식 어휘(메뉴·옵션·매장·재고·쿠폰)로 한 번 더 변환해서 입에 붙인다.
2. 자기소개 1분 버전을 머릿속으로 한 번 읊는다 — 막히는 단어가 있으면 30초 버전으로 즉시 다운그레이드 가능하다는 점만 확인.
3. 첫 질문이 어떤 카드든 *결국은 캐시 정합성·트랜잭션 경계·추상화 셋 중 하나로 회수* 한다는 큰 그림을 머릿속에 둔다.

## 10. 연결 문서

- 캐시 정합성 깊이 학습은 [Redis 캐시 무효화 (커머스)](../database/redis/redis-cache-invalidation-commerce.md)(개념) 또는 [SB 팀 캐시 아키텍처](../task/sb-dev-team/cache-architecture.md)(사례)로 분리 연결.
- Outbox 패턴 깊이 학습은 [분산 트랜잭션 — Outbox 패턴](../architecture/distributed-transaction-outbox-pattern.md)으로 연결.
- EXPLAIN 학습은 [MySQL EXPLAIN 플랜](../database/mysql/explain-plan.md) 및 [복합 인덱스·EXPLAIN 커머스 API 시나리오](../database/mysql/mysql-index-explain-commerce-api.md) study-pack과 페어링.
- 장애 첫 5분 / 관측성 깊이 학습은 [커머스 관측성 첫 5분](../devops/commerce-observability-first-five-minutes.md)으로 연결.
- 압박 질문 일반 패턴은 [면접 압박 질문 방어](./experience-based/pressure-question-defense.md)에서 참고.
- 회사·포지션 카드 본체는 [CJ푸드빌 디지털 채널 백엔드 면접](./cj-foodville-digital-channel-backend.md)으로 두고 본 문서는 *답변 매핑 전용*으로 유지한다.
