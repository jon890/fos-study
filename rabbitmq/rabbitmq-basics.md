# [초안] RabbitMQ Basics — 실전 백엔드 관점에서 정리하는 메시지 브로커 기본기

## 왜 RabbitMQ를 다시 공부하는가

실무에서 메시지 브로커를 써본 경험이 있더라도, 면접에서 "왜 Kafka가 아니라 RabbitMQ를 썼나요?", "Exchange와 Queue의 차이는 뭔가요?", "메시지 유실을 어떻게 막았나요?" 같은 질문이 들어오면 의외로 말이 막힌다. 평소에는 라이브러리가 알아서 처리해주는 부분 — Exchange 타입, Binding, Ack 모드, Prefetch, DLQ, Publisher Confirm — 이 모두 질문의 단골 소재다.

RabbitMQ는 AMQP 0-9-1 프로토콜을 기반으로 한 "범용 메시지 브로커"다. Kafka가 로그 기반 스트리밍에 최적화되어 있다면, RabbitMQ는 **작업 분배(task queue), 요청/응답, 비동기 이벤트 팬아웃** 같은 전통적인 엔터프라이즈 메시징 패턴에 강점이 있다. 백엔드 엔지니어가 "비동기로 돌려야 하는데 트래픽이 아주 크진 않고, 메시지 단위의 라우팅이 필요하다"는 상황에서 가장 먼저 떠올리게 되는 후보다.

이 문서는 RabbitMQ를 "개념 + 실전 예제 + 흔한 실수 + 면접 답변"의 구조로 한 번에 정리하는 것이 목표다. Kafka와의 비교, Spring AMQP 기준의 Producer/Consumer 구현, 메시지 유실 방지 설정, 그리고 면접에서 바로 꺼낼 수 있는 대답 프레이밍까지 포함한다.

## 핵심 개념: Exchange, Queue, Binding, Routing Key

RabbitMQ의 메시지 흐름을 이해하려면 네 가지 요소가 어떻게 맞물리는지부터 잡아야 한다.

- **Producer**: 메시지를 보내는 쪽. 주의할 점은 Producer는 **Queue에 직접 메시지를 넣지 않는다**는 것이다. 항상 Exchange로 보낸다.
- **Exchange**: 메시지를 받아서, 자신에게 바인딩된 Queue 중 어디로 보낼지 라우팅하는 "분배기".
- **Queue**: 실제로 메시지가 쌓이는 FIFO 버퍼.
- **Binding**: Exchange ↔ Queue 사이의 연결 규칙. Routing Key 패턴이 함께 정의된다.
- **Consumer**: Queue에서 메시지를 꺼내 처리하는 쪽.

Producer → Exchange → (Binding 규칙에 따라) Queue → Consumer 의 흐름이다. 이 구조 덕에 RabbitMQ는 Kafka와 달리 "한 메시지가 여러 컨슈머에게 다르게 라우팅되는" 패턴을 자연스럽게 표현한다.

### Exchange 타입 네 가지

면접 단골 주제다. 각 타입의 "언제 쓰는가"를 같이 외워두는 게 좋다.

**1. Direct Exchange**
Routing Key가 Binding Key와 **정확히 일치**하는 Queue로만 메시지를 보낸다. 작업 분배(work queue)처럼 "특정 타입의 작업은 특정 워커 그룹으로"라는 요구에 맞는다. 예: `order.created` 키는 주문 처리 큐로, `order.cancelled` 키는 환불 처리 큐로.

**2. Fanout Exchange**
Routing Key를 무시하고 **자신에게 바인딩된 모든 Queue로 메시지를 복제**한다. 이벤트 브로드캐스트에 쓴다. 예: 사용자 회원가입 이벤트를 "이메일 발송 서비스, 추천 시스템 초기화, 분석 파이프라인"이 각각 받아야 할 때.

**3. Topic Exchange**
Routing Key를 `.` 으로 구분된 패턴으로 해석한다. `*`는 한 단어, `#`는 0개 이상의 단어를 매칭한다. 가장 유연해서 실무에서 가장 많이 쓴다. 예: `order.kr.*` 바인딩은 `order.kr.created`, `order.kr.paid`는 받지만 `order.us.created`는 받지 않는다.

**4. Headers Exchange**
Routing Key 대신 메시지 헤더(key-value 쌍)를 기준으로 라우팅한다. 실무에서는 거의 쓰지 않고, 면접에서 "네 가지가 있다" 정도로 언급할 수 있으면 충분하다.

### Queue 속성에서 꼭 알아야 할 것들

- **durable**: 브로커 재시작 후에도 Queue 정의가 살아남는가. 보통 `true`.
- **exclusive**: 선언한 커넥션에서만 쓰고, 연결이 끊기면 자동 삭제. RPC 응답 큐 같은 임시 용도.
- **auto-delete**: 마지막 컨슈머가 끊기면 자동 삭제.
- **arguments**: `x-message-ttl`, `x-max-length`, `x-dead-letter-exchange` 같은 고급 옵션.

Queue가 durable이어도 **메시지가 persistent로 발행되지 않으면** 재시작 시 유실된다. durable Queue + persistent Message + Publisher Confirm + Consumer Ack — 이 네 가지가 메시지 유실 방지의 기본 세트다.

## Kafka와의 차이, 그리고 언제 RabbitMQ를 선택하는가

면접에서 거의 확정적으로 나오는 질문이다. 핵심은 "**브로커가 어디에 상태를 두느냐**"와 "**메시지가 어떻게 소비되느냐**"의 차이다.

| 관점 | RabbitMQ | Kafka |
|---|---|---|
| 모델 | 푸시 기반(실제로는 prefetch 기반 pull) 큐 | 로그 기반, 컨슈머가 offset으로 pull |
| 메시지 처리 후 | Ack 받으면 **큐에서 제거** | 제거 안 함, 보관 기간 동안 유지 |
| 재처리 | 같은 메시지를 재소비하려면 별도 메커니즘 필요 | offset만 되감으면 됨 |
| 라우팅 | Exchange 타입으로 복잡한 라우팅 가능 | Topic → Partition 단순 |
| 순서 보장 | 단일 Queue 내에서 보장 | Partition 내에서 보장 |
| 처리량 | 초당 수만~수십만 | 초당 수십만~수백만 |
| 주용도 | 작업 분배, RPC, 이벤트 팬아웃 | 로그 수집, 이벤트 소싱, 스트리밍 |

면접 답변 프레이밍의 기본은 이렇게 잡는다.
> "RabbitMQ는 큐에서 소비되면 메시지가 사라지는 전통적인 메시지 브로커고, Kafka는 소비 후에도 메시지가 로그로 남아 여러 컨슈머 그룹이 각자 offset으로 재처리할 수 있다는 점이 가장 큰 차이입니다. 그래서 작업 분배처럼 '한 번 처리되고 끝'인 워크로드에는 RabbitMQ를, 이벤트 소싱이나 여러 시스템이 같은 이벤트를 재처리해야 하는 경우에는 Kafka를 선호합니다."

## 실전 백엔드 활용 패턴

### 1. Work Queue (작업 분배)

대표적인 RabbitMQ 사용 패턴이다. API 서버가 무거운 작업(이미지 처리, 이메일 발송, PDF 생성)을 Queue에 밀어 넣고, 워커 프로세스 여러 개가 병렬로 꺼내 처리한다. Direct Exchange + 단일 Queue + N개의 Consumer 구성이 기본이다.

### 2. 이벤트 팬아웃

주문 생성 이벤트 하나를 "결제 서비스, 알림 서비스, 통계 서비스"가 각자 받아야 할 때. Fanout 또는 Topic Exchange로 라우팅한 뒤, 서비스별로 자기 Queue를 바인딩한다. 각 Queue는 독립적이므로 한 서비스가 느려도 다른 서비스에 영향이 없다.

### 3. RPC (요청/응답)

잘 쓰이진 않지만 가능하다. 요청 메시지에 `reply_to`(응답을 받을 임시 Queue 이름)와 `correlation_id`를 넣어 보내고, 서버가 해당 Queue로 응답을 보낸다. 동기 통신을 굳이 메시지 브로커로 할 이유는 많지 않아서, 실무에서는 gRPC/HTTP가 더 흔하다.

### 4. Delayed / Retry 패턴

RabbitMQ 자체에는 "지연 발행" 기능이 기본으로는 없다. 두 가지 방법이 있다.
- **rabbitmq-delayed-message-exchange 플러그인**: 지연 시간을 헤더로 지정.
- **DLX + TTL 조합**: TTL이 걸린 Queue에 메시지를 넣고, 만료되면 Dead Letter Exchange로 빠지게 해서 실제 처리 큐로 전달.

재시도 패턴도 같다. 처리 실패 → 짧은 TTL이 걸린 retry queue → TTL 만료 → 원래 큐로 되돌아와 재소비.

## Bad vs Improved: 흔한 실수와 개선

### 실수 1. auto-ack 로 개발 시작

**Bad**
```java
@RabbitListener(queues = "order.queue")
public void handle(OrderMessage msg) {
    paymentService.charge(msg);
}
```
기본 ack 모드가 무엇인지 모른 채 쓰는 경우. Spring AMQP는 기본이 AUTO지만, AUTO는 "예외가 나면 nack"을 의미할 뿐, 메시지가 꺼내지는 순간 바로 제거되는 것이 아니다. 하지만 만약 `acknowledgeMode=NONE`으로 설정되어 있으면, Consumer가 메시지를 받자마자 브로커는 지웠다고 간주하므로 처리 중 프로세스가 죽으면 **메시지가 유실된다**.

**Improved**
```java
@Bean
public SimpleRabbitListenerContainerFactory factory(ConnectionFactory cf) {
    SimpleRabbitListenerContainerFactory f = new SimpleRabbitListenerContainerFactory();
    f.setConnectionFactory(cf);
    f.setAcknowledgeMode(AcknowledgeMode.MANUAL);
    f.setPrefetchCount(20);
    return f;
}

@RabbitListener(queues = "order.queue", containerFactory = "factory")
public void handle(OrderMessage msg, Channel channel,
                   @Header(AmqpHeaders.DELIVERY_TAG) long tag) throws IOException {
    try {
        paymentService.charge(msg);
        channel.basicAck(tag, false);
    } catch (BusinessRetryableException e) {
        channel.basicNack(tag, false, true);  // requeue
    } catch (Exception e) {
        channel.basicNack(tag, false, false); // DLX로
    }
}
```
수동 ack로 바꾸고, 재처리 가능한 예외와 치명적 예외를 구분해 nack의 `requeue` 플래그를 다르게 준다.

### 실수 2. Prefetch 무제한

**Bad**: 설정을 건드리지 않으면 Consumer가 Queue에 있는 메시지를 무한정 가져가려 한다. 한 Consumer가 수천 건을 메모리에 안고 있다가 GC 폭주나 OOM이 난다.

**Improved**: `prefetchCount`를 10~50 사이에서 시작해서 처리 시간에 맞춰 조정한다. 처리 시간이 긴 작업은 낮게(1~5), 짧으면 높게.

### 실수 3. Publisher Confirm 미설정

**Bad**: `rabbitTemplate.convertAndSend(...)`를 호출했다고 브로커에 도달했다는 보장은 없다. TCP 레이어에서 끊기면 메시지는 사라진다.

**Improved**: `publisher-confirm-type: correlated`를 켜고 ConfirmCallback에서 ack/nack을 확인한다. 실패 시 Outbox 테이블에 기록하거나 재발행한다.

```yaml
spring:
  rabbitmq:
    publisher-confirm-type: correlated
    publisher-returns: true
    template:
      mandatory: true
```

### 실수 4. DLQ 없이 운영

처리 실패한 메시지를 계속 requeue 하면 **poison message**가 큐에 남아 같은 메시지를 무한 재시도하게 된다. 반드시 재시도 횟수를 제한하고, 한도를 넘으면 DLX로 보내 DLQ에 쌓아두고 알람을 띄운다.

## 로컬 실습 환경

Docker 한 줄이면 충분하다.

```bash
docker run -d --name rabbit \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin \
  rabbitmq:3.13-management
```

`http://localhost:15672` 로 접속하면 관리 UI가 뜬다. Exchange, Queue, Binding, 메시지 레이트를 눈으로 확인할 수 있어서 학습용으로 가장 빠른 피드백 루프가 나온다.

Spring Boot 프로젝트의 `build.gradle`.
```groovy
implementation 'org.springframework.boot:spring-boot-starter-amqp'
```

`application.yml`.
```yaml
spring:
  rabbitmq:
    host: localhost
    port: 5672
    username: admin
    password: admin
    publisher-confirm-type: correlated
    publisher-returns: true
    listener:
      simple:
        acknowledge-mode: manual
        prefetch: 20
```

## 실행 가능한 예제: 주문 이벤트 팬아웃 + DLQ

Exchange와 Queue 선언.

```java
@Configuration
public class RabbitConfig {

    public static final String ORDER_EXCHANGE = "order.exchange";
    public static final String ORDER_DLX      = "order.dlx";
    public static final String EMAIL_QUEUE    = "order.email.queue";
    public static final String EMAIL_DLQ      = "order.email.dlq";

    @Bean
    TopicExchange orderExchange() {
        return ExchangeBuilder.topicExchange(ORDER_EXCHANGE).durable(true).build();
    }

    @Bean
    DirectExchange orderDlx() {
        return ExchangeBuilder.directExchange(ORDER_DLX).durable(true).build();
    }

    @Bean
    Queue emailQueue() {
        return QueueBuilder.durable(EMAIL_QUEUE)
                .withArgument("x-dead-letter-exchange", ORDER_DLX)
                .withArgument("x-dead-letter-routing-key", "email.failed")
                .build();
    }

    @Bean
    Queue emailDlq() {
        return QueueBuilder.durable(EMAIL_DLQ).build();
    }

    @Bean
    Binding emailBinding() {
        return BindingBuilder.bind(emailQueue()).to(orderExchange()).with("order.created");
    }

    @Bean
    Binding emailDlqBinding() {
        return BindingBuilder.bind(emailDlq()).to(orderDlx()).with("email.failed");
    }
}
```

Producer.

```java
@Service
@RequiredArgsConstructor
public class OrderPublisher {
    private final RabbitTemplate rabbitTemplate;

    public void publishOrderCreated(OrderCreatedEvent event) {
        CorrelationData cd = new CorrelationData(event.orderId());
        rabbitTemplate.convertAndSend(
            RabbitConfig.ORDER_EXCHANGE,
            "order.created",
            event,
            message -> {
                message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                return message;
            },
            cd
        );
    }
}
```

Consumer (재시도 한도 포함).

```java
@Component
public class EmailConsumer {

    @RabbitListener(queues = RabbitConfig.EMAIL_QUEUE)
    public void onMessage(OrderCreatedEvent event,
                          Channel channel,
                          @Header(AmqpHeaders.DELIVERY_TAG) long tag,
                          @Header(name = "x-death", required = false) List<Map<String,?>> xDeath) throws IOException {
        int retry = xDeath == null ? 0 : ((Long) xDeath.get(0).get("count")).intValue();
        try {
            if (retry >= 3) {
                channel.basicNack(tag, false, false); // DLQ로
                return;
            }
            emailService.sendOrderEmail(event);
            channel.basicAck(tag, false);
        } catch (Exception e) {
            channel.basicNack(tag, false, false); // DLX 경유 후 retry → DLQ
        }
    }
}
```

`x-death` 헤더는 DLX를 거쳐 재큐잉될 때 브로커가 자동으로 채워주는 재시도 이력이다. 이걸 이용해 "재시도 3회 초과면 DLQ로 고정" 같은 정책을 간단하게 쓸 수 있다.

## 면접 답변 프레이밍

**Q. RabbitMQ와 Kafka의 차이를 설명해 달라.**
> 가장 큰 차이는 메시지가 소비된 이후의 보관 모델입니다. RabbitMQ는 Ack가 돌아오면 메시지를 큐에서 지우는 전통적인 브로커고, Kafka는 소비 후에도 로그로 보관해 offset 기반으로 재소비할 수 있습니다. 그래서 작업 분배나 이벤트 팬아웃처럼 "한 번 처리되면 끝"인 경우 RabbitMQ, 이벤트 소싱이나 스트리밍 분석처럼 같은 이벤트를 여러 번 재처리해야 하는 경우 Kafka를 선택했습니다.

**Q. RabbitMQ에서 메시지 유실을 막기 위해 어떤 설정을 켭니까?**
> 네 가지를 세트로 봅니다. Queue durable, Message persistent, Publisher Confirm, Consumer manual ack 입니다. 여기에 더해서 처리 실패 메시지를 위한 DLX + DLQ를 구성하고, Publisher 쪽에서는 Confirm nack이 왔을 때 재발행할 수 있도록 Outbox 패턴으로 묶어두는 편입니다.

**Q. Prefetch는 왜 설정하나요?**
> Consumer가 아직 ack하지 않은 메시지를 얼마나 미리 받아올지 제한하는 값입니다. 기본값이 무제한이라 놔두면 한 Consumer가 수천 건을 메모리에 안고 있다가 OOM이 나거나, 불균등 분배가 심해집니다. 처리 시간이 긴 작업은 낮게(1~5), 짧은 작업은 높게(50~) 잡아 분배를 평탄하게 만듭니다.

**Q. 같은 메시지가 여러 번 처리되는 문제를 어떻게 다루나요?**
> RabbitMQ는 기본이 at-least-once이기 때문에 중복은 언제든 발생할 수 있다고 전제합니다. 그래서 Consumer 측에서 메시지 ID를 기준으로 **idempotent** 하게 처리하도록 만듭니다. 예를 들어 주문 이벤트 처리 전에 `processed_message(message_id)` 테이블을 확인하거나, 결제 호출에 `idempotency_key`를 실어 보내는 식입니다.

**Q. Exchange 타입 중 어떤 걸 가장 많이 썼나요?**
> Topic Exchange를 기본으로 썼습니다. `도메인.액션.리전` 같은 라우팅 키로 설계해두면, 새로운 Consumer가 특정 패턴만 구독해서 붙기가 쉽고, 초기 설계를 크게 바꾸지 않고 확장할 수 있었습니다.

## 학습 체크리스트

- [ ] Exchange 네 가지 타입을 각 한 줄 예시와 함께 설명할 수 있다.
- [ ] Producer → Exchange → Queue → Consumer 흐름을 그림 없이 말로 설명할 수 있다.
- [ ] durable / persistent / Publisher Confirm / manual ack 의 역할을 각각 구분해 설명할 수 있다.
- [ ] Prefetch를 설정하는 이유와 조정 기준을 말할 수 있다.
- [ ] DLX + DLQ 구성법과 `x-death` 헤더를 이용한 재시도 제한 패턴을 코드로 쓸 수 있다.
- [ ] RabbitMQ와 Kafka를 선택하는 기준을 워크로드 관점에서 구분해 말할 수 있다.
- [ ] at-least-once 전제 하에 idempotent 소비자를 어떻게 구현하는지 설명할 수 있다.
- [ ] 로컬 Docker로 RabbitMQ를 띄우고, 관리 UI에서 Exchange/Queue/Binding을 직접 생성해본 경험이 있다.
- [ ] Spring AMQP로 Producer/Consumer를 작성하고, 의도적으로 예외를 던져 DLQ에 메시지가 쌓이는 것을 확인해봤다.
- [ ] Delayed Message 플러그인과 TTL + DLX 방식의 차이를 설명할 수 있다.
