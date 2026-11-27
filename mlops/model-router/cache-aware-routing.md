---
tags: ["Model Router", "LLM 서빙", "KV cache", study]
series: "GPU 로 LLM 서빙하기"
seriesOrder: 15
---

# 캐시를 보고 인스턴스를 고른다

**이전 글** [모델을 골라주는 계층이 대신 가져오는 제약](./router-constraints.md) · **다음 글** [첫 토큰이 나간 뒤에는 재시도할 수 없다](./streaming-retry-boundary.md) · [시리즈 목차](../README.md)

> 이 글은 [Model Router 란 무엇인가](./what-is-model-router.md)에서 나눈 두 계층 가운데 아래 계층(Gateway 계층), 즉 자체 호스팅 모델이 여러 대일 때 어느 인스턴스로 보낼지를 다룬다.
> 서빙 자체의 원리는 [GPU로 LLM을 서빙한다는 것](../llm-serving/gpu-llm-serving-basics.md)이 다룬다.

자체 호스팅 vLLM 을 세 대 띄우고 앞에 로드 밸런서를 두면 요청이 고르게 분산된다.
분산은 잘 되는데 응답이 예상보다 느리다.

원인은 로드 밸런서가 나쁜 것이 아니다.
**일반 로드 밸런서는 각 인스턴스가 무엇을 이미 계산해 두었는지 모른다.**
같은 앞부분을 가진 요청이 매번 다른 인스턴스로 가면 그 앞부분을 매번 다시 계산한다.

## 캐시라는 한 단어가 두 계층에서 다른 것을 가리킨다

앞 글에서 다룬 캐시와 이 글에서 다루는 캐시는 다른 것이다.

| 축 | 위 계층. 제공자 prompt caching | 아래 계층. prefix cache |
| --- | --- | --- |
| 누가 갖는가 | 외부 제공자 | 내가 띄운 vLLM 인스턴스 |
| 무엇을 아끼는가 | 입력 토큰 단가 | prefill 연산 시간 |
| 효과가 나타나는 곳 | 요금 | TTFT |
| 내가 제어하는가 | 캐시를 붙일지 여부만 | 어느 인스턴스로 보낼지까지 |
| 회계 | cache write 프리미엄과 cache read 할인 | 요금과 무관하다. GPU 시간만 아낀다 |

**둘을 섞으면 판단이 어긋난다.**
제공자 prompt caching 은 비용 문제이고, prefix cache 는 지연 문제다.
외부 제공자 API 만 쓰면 아래 계층은 아예 존재하지 않는다.

## 재사용할 수 있는 입력을 찾는다

같은 토큰 블록과 그 앞부분이 인스턴스 메모리에 남아 있으면 prefill 계산을 줄일 수 있다. 블록이 적중하는 조건과 프롬프트를 배치하는 방법은 [vLLM prefix cache를 살리는 프롬프트 배치](../llm-serving/vllm-prefix-cache-prompt-layout.md)에 있다.

라우터가 얻는 이득은 공통 부분의 길이와 반복 빈도에 달려 있다. 같은 긴 system 지시 뒤에 짧은 질문이 반복된다면 같은 인스턴스로 보내는 효과가 크다. 요청마다 긴 문서의 앞부분부터 달라지면 분산을 한쪽으로 치우치게 할 만큼 재사용할 블록이 있는지 먼저 확인한다.

## prefix aware 와 KV cache aware 는 판단하는 것이 다르다

캐시를 보고 인스턴스를 고르는 방식이 둘 있고, 이름이 비슷해 섞이기 쉽다.

| 방식 | 판단 |
| --- | --- |
| prefix aware | 같은 앞부분이면 항상 같은 인스턴스로 보낸다. 그 캐시가 이미 밀려났어도 |
| KV cache aware | 실제 적중률이 가장 높은 인스턴스로 보낸다 |

차이가 나는 지점은 캐시가 밀려난 뒤다.

KV cache 공간은 유한하다.
새 요청이 들어오면 오래된 블록이 제거된다.
prefix aware 는 그 사실을 모르고 계속 같은 인스턴스로 보낸다.
그 인스턴스에 캐시가 없어도 보내고, 옆 인스턴스가 같은 앞부분을 우연히 갖고 있어도 그쪽으로 보내지 않는다.

**prefix aware 는 해시 기반 분산이고, KV cache aware 는 상태를 조회하는 분산이다.**
앞의 것은 판단이 싸고 상태 조회가 필요하지 않다. 뒤의 것은 정확하지만 인스턴스 상태를 알아야 한다.
앞 글에서 본 것과 같은 구조가 여기서도 반복된다. 정밀도를 올리는 판단이 요청 경로에 조회를 얹는다.

### llm-d 의 구현

llm-d 는 Gateway API Inference Extension 과 External Processing Pod 로 이것을 구현한다.
Kubernetes Gateway 뒤에 별도 Pod 를 두고 그 Pod 가 라우팅 판단을 내리는 구조다.

판단 순서가 둘로 나뉘어 있다.

1. 강한 prefix 일치가 있으면 그 앞부분을 가진 replica 로 보낸다
2. 강한 일치가 없으면 `vllm:kv_cache_usage_perc` 를 보고 여유가 가장 많은 replica 로 보낸다

**두 번째 단계가 이 설계의 핵심이다.**
캐시로 고를 근거가 없을 때 아무 곳으로 보내지 않고, 앞으로 캐시가 쌓일 여유가 가장 많은 곳으로 보낸다.
지금의 적중이 아니라 다음 요청의 적중을 만드는 판단이다.

vLLM production-stack 도 같은 문제를 다루고, 공식 문서에 KV Cache Aware Routing 사용 사례가 있다.

## session affinity 로는 절반만 해결된다

캐시 기준 라우팅을 처음 만들 때 가장 먼저 떠오르는 것이 session affinity 다.
세션 식별자나 사용자 식별자를 해시해 같은 인스턴스로 보내는 방식이고, 웹 백엔드에서 오래 써온 sticky session 과 같은 발상이다.

같은 대화가 이어지는 서비스에서는 이것만으로도 상당히 맞는다.
대화 이력이 앞부분을 이루므로 같은 세션은 같은 앞부분을 갖는다.

한계가 셋 있다.

- **여러 사용자가 같은 앞부분을 공유하는 경우를 놓친다.** 긴 system prompt 는 모든 사용자에게 같다. 사용자별로 흩어 보내면 그 공통 부분의 캐시가 인스턴스마다 중복으로 쌓인다
- **세션 길이가 고르지 않다.** 긴 대화를 하는 사용자가 한 인스턴스에 붙으면 그 인스턴스만 포화된다. 캐시 적중은 오르는데 대기 시간이 늘어난다
- **인스턴스 수가 바뀌면 해시 결과가 달라진다**

## 인스턴스를 늘리거나 줄이면 적중이 무너진다

마지막 항목이 운영에서 가장 자주 걸린다.

인스턴스 수로 나눈 나머지를 쓰는 단순 해시는 인스턴스가 하나 늘거나 줄 때 거의 모든 키의 목적지가 바뀐다.
목적지가 바뀌면 그 앞부분의 캐시는 새 인스턴스에 없고, prefill 을 처음부터 다시 한다.

**오토스케일이 캐시 적중을 깨뜨리는 구간이 여기다.**
부하가 올라 인스턴스를 늘리면, 늘린 직후에 적중률이 떨어져 prefill 부하가 오히려 늘어난다.
새로 뜬 인스턴스가 캐시를 채울 시간도 필요하다.

대응을 셋으로 정리하면 이렇게 된다.
근거 문서에서 옮긴 것이 아니라 위의 사실들에서 끌어낸 것이므로, 실제 효과는 자기 트래픽에서 재야 한다.

| 대응 | 동작 |
| --- | --- |
| consistent hashing | 인스턴스가 바뀔 때 목적지가 바뀌는 키를 일부로 제한한다 |
| KV cache aware 로 전환 | 목적지를 해시로 정하지 않으므로 인스턴스 수가 바뀌어도 기존 목적지가 흔들리지 않는다 |
| 증감 속도를 늦춘다 | 캐시가 채워질 시간을 준다. 부하 급증에 늦게 반응하는 대가를 치른다 |

**앞의 둘은 지금 요청의 목적지를 다루고, 마지막은 캐시가 채워지는 속도를 다룬다.**
어느 쪽도 새로 뜬 인스턴스에 캐시가 없다는 사실 자체를 없애지는 못한다.
증감이 잦으면 그 손실이 계속 발생한다.

인스턴스를 줄일 때도 같은 문제가 있다.
줄인 인스턴스가 갖고 있던 캐시는 사라지고, 그 앞부분을 쓰던 요청은 다른 인스턴스에서 prefill 을 다시 한다.

## 적중률을 어떻게 재는가

**vLLM 은 prefix cache 적중률을 지표로 주지 않는다.**
counter 둘로 직접 구한다.

| 지표 | 종류 | 뜻 |
| --- | --- | --- |
| `vllm:prefix_cache_queries` | counter | prefix cache 를 조회한 토큰 수 누적 |
| `vllm:prefix_cache_hits` | counter | 재사용된 토큰 수 누적 |

```promql
rate(vllm:prefix_cache_hits[5m]) / rate(vllm:prefix_cache_queries[5m])
```

counter 를 그대로 나누면 서버 시작 이후 전체 평균이 되어 최근 상태를 반영하지 못한다.
`rate()` 로 구간 증가율을 먼저 구한다.

적중률이 낮을 때 의심할 것이 셋이다.

- 요청 사이에 공통 앞부분이 거의 없는 작업이다. 이 경우 라우팅으로 해결되지 않는다
- KV cache 공간이 작아 블록이 금방 밀려난다. `vllm:kv_block_lifetime_seconds` 와 `vllm:kv_block_idle_before_evict_seconds` 로 확인한다
- **여러 인스턴스로 띄웠는데 라우팅이 캐시를 보지 않아 같은 앞부분을 가진 요청이 흩어진다**

마지막이 이 글의 주제다.
그런데 **몇 % 이하면 문제인지에 대한 공식 기준은 없다.**
서비스의 요청 분포에 따라 도달 가능한 최대치가 다르므로, 라우팅을 바꾸기 전과 후를 같은 트래픽에서 비교하는 편이 낫다.

지표를 라우팅 판단에 실제로 쓰는 방법과 다른 지표들과의 관계는 [vLLM 지표를 라우팅 판단에 쓰는 방법](./vllm-metrics-for-routing.md)에서 다룬다.

## 정리

- 위 계층의 제공자 prompt caching 은 비용 문제이고, 아래 계층의 prefix cache 는 지연 문제다. 둘을 섞으면 판단이 어긋난다.
- prefix cache 가 아끼는 것은 prefill 이므로 효과가 TTFT 에만 나타난다. system prompt 가 길고 질문이 짧은 서비스에서 효과가 가장 크다.
- prefix aware 는 해시로 목적지를 정하고 캐시가 밀려난 것을 모른다. KV cache aware 는 인스턴스 상태를 조회하므로 정확하지만 요청 경로에 조회가 얹힌다.
- llm-d 는 강한 prefix 일치가 없을 때 KV cache 여유가 가장 많은 replica 로 보낸다. 지금의 적중이 아니라 다음 요청의 적중을 만드는 판단이다.
- session affinity 는 여러 사용자가 공유하는 앞부분을 놓치고, 인스턴스 수가 바뀌면 목적지가 달라진다.
- 오토스케일 직후에 적중률이 떨어져 prefill 부하가 오히려 늘어난다. consistent hashing 이나 KV cache aware 로 완화한다.
- 적중률은 vLLM 이 지표로 주지 않아 counter 둘로 직접 구한다. 공식 기준값이 없으므로 같은 트래픽에서 전후를 비교한다.

## 참고 링크

- [vLLM production-stack KV Cache Aware Routing](https://docs.vllm.ai/projects/production-stack/en/vllm-stack-0.1.7/use_cases/kv-cache-aware-routing.html)
- [vllm-project/production-stack](https://github.com/vllm-project/production-stack)
- [llm-d Precise Prefix Cache Aware Routing](https://llm-d.ai/docs/guide/Installation/precise-prefix-cache-aware)
- [Red Hat. KV cache aware routing with llm-d](https://developers.redhat.com/articles/2025/10/07/master-kv-cache-aware-routing-llm-d-efficient-ai-inference)
- [TrueFoundry. KV cache routing](https://www.truefoundry.com/blog/kv-cache-routing-why-standard-load-balancers-break-prefix-caching-and-how-to-fix-it)
- [DigitalOcean. cache-aware inference router](https://www.digitalocean.com/blog/inference-router-cache-aware)
- [vLLM Metrics 설계](https://docs.vllm.ai/en/latest/design/metrics.html)
- [vLLM Forums. prefix cache hit rate](https://discuss.vllm.ai/t/prefix-cache-hit-rate/1111)
