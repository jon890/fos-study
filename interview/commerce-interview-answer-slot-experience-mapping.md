# [초안] CJ푸드빌 디지털 채널 Back-end 면접 답변집 — 슬롯 도메인 경험을 커머스/F&B 설계로 번역하기

## 왜 이 문서가 필요한가

CJ푸드빌 디지털 채널 Back-end 포지션은 빕스·뚜레쥬르·계절밥상 등 매장 기반 외식·베이커리 브랜드의 주문·결제·멤버십·매장 운영 데이터를 다룬다. 반면 직전 경력은 NHN NSC 슬롯개발팀(2024.06\~2025.11)과 AI 서비스 개발팀(2025.12\~)이고, 도메인 표면만 보면 거리가 멀어 보인다. 면접관도 가장 먼저 떠올리는 의문이 "슬롯/AI 백엔드 한 사람이 외식 커머스 도메인을 빠르게 잡을 수 있는가"이다.

이 문서는 그 의문에 정면으로 답하기 위해, 슬롯 도메인에서 실제로 만들었던 코어 자산 — `SlotTemplate`/`BaseSlotService`, RCC(RTP Cache Control), 다중 서버 캐시 정합성, `StampedLock` 기반 정적 데이터 동시성, AliasMethod O(1) 가중치 랜덤, Kafka Transactional Outbox — 을 커머스/F&B 도메인 설계 어휘로 번역해 두는 답변집이다. 슬롯 용어를 사람이 알아듣게 풀어내는 것을 넘어, 같은 설계 패턴이 주문/결제/쿠폰/메뉴/매장 정책에서 어떻게 그대로 재사용되는지를 코드 수준에서 보여주는 것이 목적이다.

면접 흐름을 자기소개 → "왜 CJ푸드빌인가" → 도메인 전환 우려 → 기본기 검증 → 마무리 질문 순으로 두고, 각 단계에서 1분·2분·심층 답변 세 가지 길이로 준비한다.

## 1. 자기소개 (Self Pitch)

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

## 5. 마무리 질문 (역질문)

면접 마지막에 던질 질문도 도메인 적합성을 보여주는 도구다.

- "메뉴 마스터·매장 정책 같은 *변경 빈도가 낮은 데이터*의 캐시 무효화는 현재 어떤 패턴으로 운영되고 있나요? 인메모리 캐시 다중 인스턴스 정합성을 어떻게 보장하시는지가 궁금합니다."
- "주문 확정 후 포인트·쿠폰·매장 KDS·CRM 발송 같은 후처리는 동기인가요, 비동기인가요? Outbox나 Saga 같은 패턴이 도입되어 있는지 궁금합니다."
- "AI 활용은 어디까지 와 있나요? 매장 매뉴얼/CS 응대/추천 셋 중 우선순위가 어디인지 알고 싶습니다."

이 세 질문 모두, 답을 듣고 나서 *"제 슬롯/AI 경험에서 X 부분이 그대로 도움이 될 것 같다"*로 자연스럽게 연결할 수 있게 설계했다.

## 6. 자기 점검 체크리스트

- [ ] 1분 자기소개를 외워서 30초 단축 버전·90초 버전 둘 다 말할 수 있다.
- [ ] 슬롯 도메인 어휘(RTP·잭팟·Wild·Scatter·페이라인) 없이도 같은 설계 카드를 외식 어휘(메뉴·매장·옵션·재고·쿠폰)로 30초 안에 다시 설명할 수 있다.
- [ ] `@TransactionalEventListener(AFTER_COMMIT)`과 `Propagation.REQUIRES_NEW`가 *왜* 필요한지 한 문장으로 답한다.
- [ ] 다중 서버 인메모리 캐시 정합성을 *MQ Fanout + StampedLock + tryReadLock 타임아웃* 세 단계로 그림 없이 말로 설명한다.
- [ ] AliasMethod와 누적합 O(n) 방식의 차이를 종이 한 장에 그릴 수 있다.
- [ ] EXPLAIN 컬럼 네 가지(type / key / rows / Extra)를 외식 도메인 가상 쿼리에 즉석 적용해 본다.
- [ ] "외식 도메인 모르지 않냐" 질문에 *학습 우선순위 4종*을 막힘 없이 말한다.
- [ ] 역질문 3종을 외워둔다.

## 7. 연결 문서 (작성 후 채워 넣을 자리)

- 캐시 정합성 깊이 학습은 `database/[`task/sb-dev-team/cache-architecture.md`](../task/sb-dev-team/cache-architecture.md)) 또는 `task/sb-dev-team/cache-architecture.md`(사례)로 분리 연결.
- Outbox 패턴 깊이 학습은 `kafka/transactional-outbox-pattern.md`로 연결.
- EXPLAIN[`interview/cj-foodville-digital-channel-backend.md`](./cj-foodville-digital-channel-backend.md)x.md` study-pack과 페어링.
- 회사·포지션 카드 본체는 `interview/cj-foodville-digital-channel-backend.md`(별도 작성)로 두고 본 문서는 *답변 매핑 전용*으로 유지한다.
