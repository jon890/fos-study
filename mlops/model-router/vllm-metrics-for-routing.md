---
tags: ["Model Router", "vLLM", "관측", study]
series: "Model Router"
seriesOrder: 7
---

# vLLM 지표를 라우팅 판단에 쓰는 방법

> Model Router 시리즈 7번이다.
> 앞 글 [LiteLLM 로 라우팅 정책을 설정하는 방법](./litellm-routing-strategies.md)에서 위 계층의 설정을 다뤘다.
> 이 글은 아래 계층이 읽는 값, 즉 자체 호스팅 vLLM 이 노출하는 지표를 다룬다.

아래 계층 라우팅은 인스턴스 상태를 보고 판단한다.
그 상태를 vLLM 이 `/metrics` 로 준다.
OpenAI 호환 API 와 같은 포트를 쓰고 기본값은 8000 이며, 지표 이름의 접두사는 `vllm:` 이다.

이 글의 목적은 지표 목록을 옮겨 적는 것이 아니다.
**어느 지표를 라우팅 판단에 넣을 수 있고 어느 지표는 사후 진단용인지**를 가른다.
둘을 섞으면 요청 경로에 넣지 않아도 되는 조회를 넣게 된다.

## 버전에 따라 이름이 다르다

**V1 엔진에서 이름이 바뀐 것과 사라진 것이 있다.**
대시보드나 라우터를 만들기 전에 이것을 먼저 확인해야 한다.

| 구버전 | 현재 |
| --- | --- |
| `vllm:gpu_cache_usage_perc` | `vllm:kv_cache_usage_perc` 로 이름이 바뀌었다 |
| `vllm:cpu_cache_usage_perc` | swap 방식이 폐기되어 없어졌다 |
| `vllm:num_requests_swapped` | 같은 이유로 없어졌다 |
| `vllm:time_in_queue_requests` | `vllm:request_queue_time_seconds` 로 대체됐다 |

블로그나 예제 설정에서 옮겨 온 이름이 지금 버전에 없으면, 그 지표는 조회 결과가 비어서 라우터가 판단 근거를 잃는다.
**운영 중인 버전의 `/metrics` 응답을 직접 확인한다.**

## 라우팅 판단에 쓰는 값과 사후 진단에 쓰는 값

지표를 두 갈래로 가른다.

| 갈래 | 조건 | 대표 지표 |
| --- | --- | --- |
| 라우팅 판단 | gauge 이고 현재 상태를 한 값으로 말한다 | `vllm:num_requests_waiting`, `vllm:num_requests_running`, `vllm:kv_cache_usage_perc` |
| 사후 진단 | histogram 이거나 counter 라 구간을 모아야 뜻이 생긴다 | `vllm:time_to_first_token_seconds`, `vllm:prefix_cache_hits`, `vllm:num_preemptions` |

**gauge 는 지금 값을 그대로 비교할 수 있고, histogram 과 counter 는 구간을 모아야 값이 나온다.**
histogram 을 라우팅 판단에 쓰려면 분위수를 계산해야 하고, 그 계산은 요청 하나를 처리하는 시간 안에 끝나지 않는다.
그래서 요청 경로에서는 gauge 를 보고, histogram 은 별도 수집 계통에서 모아 정책을 조정하는 데 쓴다.

llm-d 가 `vllm:kv_cache_usage_perc` 를 요청 경로에서 보는 것도 이 이유다.
gauge 하나를 replica 마다 읽어 비교하는 것으로 판단이 끝난다.

### 상태 지표

| 지표 | 종류 | 뜻 |
| --- | --- | --- |
| `vllm:num_requests_running` | gauge | 현재 실행 배치에 들어간 요청 수 |
| `vllm:num_requests_waiting` | gauge | 스케줄링을 기다리는 요청 수 |
| `vllm:num_requests_waiting_by_reason` | gauge | 대기 사유별 요청 수 |
| `vllm:kv_cache_usage_perc` | gauge | KV cache 사용률. 1 이 100% |
| `vllm:num_preemptions` | counter | 선점 누적 수 |

### 시간 지표

| 지표 | 종류 | 뜻 |
| --- | --- | --- |
| `vllm:time_to_first_token_seconds` | histogram | TTFT |
| `vllm:inter_token_latency_seconds` | histogram | 토큰 간 지연. TPOT 에 대응 |
| `vllm:request_time_per_output_token_seconds` | histogram | 요청별 평균 출력 토큰당 시간 |
| `vllm:e2e_request_latency_seconds` | histogram | 요청 전체 지연 |
| `vllm:request_queue_time_seconds` | histogram | 대기 단계에 머문 시간 |
| `vllm:request_prefill_time_seconds` | histogram | prefill 단계 시간 |
| `vllm:request_decode_time_seconds` | histogram | decode 단계 시간 |

### 캐시 지표

| 지표 | 종류 | 뜻 |
| --- | --- | --- |
| `vllm:prefix_cache_queries` | counter | prefix cache 를 조회한 토큰 수 누적 |
| `vllm:prefix_cache_hits` | counter | 재사용된 토큰 수 누적 |
| `vllm:external_prefix_cache_queries` | counter | KV connector 를 통한 조회 |
| `vllm:external_prefix_cache_hits` | counter | KV connector 를 통한 적중 |
| `vllm:prompt_tokens_cached` | counter | 캐시에서 가져온 prompt 토큰 수 |
| `vllm:kv_block_lifetime_seconds` | histogram | KV 블록의 할당부터 해제까지 수명 |
| `vllm:kv_block_idle_before_evict_seconds` | histogram | 블록이 제거되기 전 유휴 시간 |
| `vllm:kv_block_reuse_gap_seconds` | histogram | 같은 블록이 재사용되기까지의 간격 |

캐시 지표를 라우팅에 쓰는 방법은 [캐시를 보고 인스턴스를 고른다](./cache-aware-routing.md)에서 다뤘다.

### 토큰 지표

| 지표 | 종류 | 뜻 |
| --- | --- | --- |
| `vllm:prompt_tokens` | counter | 처리한 prefill 토큰 수 |
| `vllm:generation_tokens` | counter | 생성한 토큰 수 |
| `vllm:request_prompt_tokens` | histogram | 요청별 prefill 토큰 수 분포 |
| `vllm:request_generation_tokens` | histogram | 요청별 생성 토큰 수 분포 |
| `vllm:iteration_tokens_total` | histogram | engine step 하나당 처리 토큰 수 |

## TTFT 와 TPOT 가 어떻게 연결돼 있는가

**TTFT 는 대기 시간과 prefill 시간의 합이다.**
둘 중 하나만 늘어도 TTFT 가 늘어난다.
그래서 TTFT 가 나빠졌다는 사실만으로는 원인을 좁힐 수 없고, `vllm:request_queue_time_seconds` 와 `vllm:request_prefill_time_seconds` 로 갈라 봐야 한다.

초당 생성 토큰은 TPOT 의 역수에 동시 처리 요청 수를 곱한 것에 가깝다.
이 관계에서 나오는 결론이 라우팅 판단에 직접 영향을 준다.

**요청 하나의 체감 속도와 서버 전체 처리량이 반대로 움직일 수 있다.**
배치가 커지면 TPOT 가 늘어 개별 요청은 느려지지만 서버 전체 처리량은 오른다.

라우팅에 옮기면 이렇게 된다.

| 목표 | 판단 |
| --- | --- |
| 요청 하나의 응답을 빠르게 | 배치가 작은 인스턴스로 보낸다. `num_requests_running` 이 낮은 쪽 |
| 서버 전체 처리량을 높게 | 배치를 채운다. 요청을 모아 보내는 쪽 |

둘을 동시에 최적화할 수 없으므로 어느 쪽인지 먼저 정해야 한다.
`least-busy` 계열 전략이 앞의 목표를 고른 것이고, 그 선택이 처리량을 조금 포기한다.

## 처리량이 떨어졌을 때 보는 순서

Red Hat 운영 글이 제시한 순서다.
vLLM 공식 문서는 무엇을 보는지만 설명하고 순서를 정하지 않는다.

1. TTFT 와 토큰 간 지연을 나눠 본다. 증상을 prefill 문제와 decode 문제로 먼저 가른다
2. `num_requests_waiting` 과 `num_requests_running` 으로 포화 여부를 본다
3. `kv_cache_usage_perc` 와 `num_preemptions` 로 메모리 상태를 본다
4. 입력과 출력 길이 분포가 갑자기 달라졌는지 본다
5. 여기까지 안 잡히면 텐서 병렬화 구성과 하드웨어 연결을 본다

**1번이 순서의 첫 자리에 있는 이유가 나머지를 정한다.**
prefill 문제와 decode 문제는 원인이 겹치지 않으므로, 먼저 가르면 그 뒤에 볼 것이 절반으로 줄어든다.
4번은 서버 설정이 아니라 트래픽이 바뀐 경우다. 라우터를 고치기 전에 확인해야 하는 항목이라 순서에 들어 있다.

### 한쪽만 늘었을 때

**TTFT 만 늘고 토큰 간 지연은 그대로일 때**

- `num_requests_waiting` 이 늘었으면 유입이 처리 능력을 넘었다
- 입력 프롬프트가 길어졌으면 prefill 연산량 자체가 늘었다
- `max_num_batched_tokens` 가 작으면 긴 프롬프트의 prefill 이 여러 스텝에 나뉜다
- prefix cache 적중률이 떨어졌으면 건너뛰던 계산을 다시 하고 있다

마지막 항목이 라우팅과 직접 연결된다.
서버 설정을 하나도 바꾸지 않았는데 TTFT 가 오르는 경우가 여기다.
인스턴스를 늘렸거나 라우팅 규칙을 바꿨을 때 이 증상이 나온다.

**토큰 간 지연만 늘고 TTFT 는 그대로일 때**

- `num_requests_running` 이 늘었으면 배치가 커져 스텝당 연산량이 늘었다
- `num_preemptions` 가 늘었으면 decode 도중 선점되어 재계산이 생겼다
- `max_num_batched_tokens` 가 크면 prefill 이 decode 사이에 끼어든다
- 출력 길이 분포가 달라졌을 수 있다

## 한 설정이 두 지표를 반대로 민다

`max_num_batched_tokens` 는 스케줄링 한 번의 토큰 예산이다.
chunked prefill 이 켜져 있으면 이 값이 곧 청크 크기다.

| 값 | TTFT | 토큰 간 지연 |
| --- | --- | --- |
| 작게 | 긴 프롬프트에서 나빠진다 | 좋아진다. decode 를 자주 끼워 넣는다 |
| 크게 | 좋아진다 | 나빠진다. prefill 이 decode 를 막는다 |

**어느 쪽을 우선할지 먼저 정해야 값을 고를 수 있다.**
"둘 다 좋게" 는 이 설정으로 도달할 수 없다.

관련 설정이 둘 더 있다.

| 설정 | 영향 |
| --- | --- |
| `max_num_seqs` | 배치에 들어갈 최대 동시 요청 수. 낮추면 선점이 줄지만 처리량도 준다 |
| chunked prefill | V1 에서 기본으로 켜진다. decode 를 먼저 스케줄링하고 남는 예산으로 prefill 을 처리한다 |

**모델과 GPU 별 권장값은 확인하지 못했다.**
공식 문서가 트레이드오프의 방향만 제시하고 값을 주지 않는다.
실제 트래픽의 입력과 출력 길이 분포에 따라 값이 달라지므로, 자기 트래픽으로 재는 것 외에 방법이 없다.

라우팅 관점에서 이것이 중요한 이유가 하나 있다.
**인스턴스마다 이 값을 다르게 두면 인스턴스의 성격이 갈린다.**
긴 프롬프트를 받는 인스턴스와 짧은 대화를 받는 인스턴스를 나눠 두고 라우터가 요청 길이로 가르는 구성이 가능하다.
그 대신 인스턴스가 동질적이지 않으므로 `least-busy` 처럼 요청 수만 세는 전략은 맞지 않게 된다.

## 판단 기준은 사용률이 아니라 선점이다

`kv_cache_usage_perc` 에 대해 **"몇 % 를 넘으면 무엇을 하라" 는 공식 기준이 없다.**
90% 라는 값을 자주 보는데, 이것은 Red Hat 운영 글의 관찰이고 공식 문서의 기준값이 아니다.

공식 튜닝 문서가 제시하는 신호는 선점 발생이다.

- `num_preemptions` 가 늘면 `gpu_memory_utilization` 을 올린다
- 또는 `max_num_seqs` 나 `max_num_batched_tokens` 를 낮춘다

**사용률이 아니라 선점을 기준으로 두는 이유는 사용률이 높은 것 자체가 문제가 아니기 때문이다.**
KV cache 를 90% 쓰면서 선점이 없으면 메모리를 잘 쓰고 있는 상태다.
선점이 나기 시작하면 그때부터 실제 손해가 발생한다.

V1 의 선점 방식은 `RECOMPUTE` 다.
선점된 요청은 공간이 생겼을 때 **처음부터 다시 계산한다.**
그래서 선점 하나가 그 요청의 prefill 전체를 다시 하게 만든다.
이 값이 오르는 것을 보면 라우터가 그 인스턴스로 요청을 덜 보내야 한다.

같은 이유로 KV cache 사용률과 대기 요청 수의 공식 기준값도 없다.
라우팅에 쓸 때는 절대 기준값을 두는 대신 인스턴스끼리 비교하는 편이 낫다.
여유가 가장 많은 쪽으로 보내는 판단은 기준값을 필요로 하지 않는다.

## 정리

- V1 에서 지표 이름이 바뀌고 사라진 것이 있다. 예제에서 옮겨 온 이름이 지금 버전에 없으면 라우터가 판단 근거를 잃는다.
- 요청 경로에서는 gauge 를 보고 histogram 과 counter 는 사후 진단에 쓴다. histogram 의 분위수를 요청 처리 시간 안에 계산할 수 없다.
- TTFT 는 대기 시간과 prefill 시간의 합이므로 TTFT 하나로는 원인을 좁힐 수 없다. 두 histogram 으로 갈라 본다.
- 요청 하나의 속도와 서버 전체 처리량이 반대로 움직인다. `least-busy` 계열은 앞을 고른 것이고 처리량을 조금 포기한다.
- 진단 순서의 첫 자리가 prefill 과 decode 를 가르는 것이다. 먼저 가르면 뒤에 볼 것이 절반으로 줄어든다.
- `max_num_batched_tokens` 는 TTFT 와 토큰 간 지연을 반대로 민다. 둘 다 좋게 하는 값이 없으므로 우선순위를 먼저 정한다.
- KV cache 사용률에 공식 기준값이 없다. 90% 는 특정 운영 글의 관찰이고, 공식 문서가 제시하는 신호는 선점 발생이다.

## 다음 편

다음 글에서 시리즈를 마친다.
지금까지 계층과 판단 방식과 설정을 다뤘는데, 실제 회사들은 같은 문제를 서로 다른 층에서 풀고 있다.
토스증권과 Netflix 와 Uber 와 KT 의 공개 사례를 계층 경계로 늘어놓고, 그 갈림이 무엇에서 왔는지 읽는다.

[같은 문제를 회사마다 다른 층에서 푼다](./industry-cases.md)로 이어진다.

## 참고 링크

- [vLLM Metrics 설계](https://docs.vllm.ai/en/latest/design/metrics.html)
- [vLLM 최적화 설정](https://docs.vllm.ai/en/stable/configuration/optimization/)
- [vllm/v1/metrics/loggers.py](https://github.com/vllm-project/vllm/blob/main/vllm/v1/metrics/loggers.py)
- [Red Hat. vLLM 성능 문제를 다섯 단계로 좁히기](https://developers.redhat.com/articles/2026/03/09/5-steps-triage-vllm-performance)
- [vLLM Forums. prefix cache hit rate](https://discuss.vllm.ai/t/prefix-cache-hit-rate/1111)
- [llm-d Precise Prefix Cache Aware Routing](https://llm-d.ai/docs/guide/Installation/precise-prefix-cache-aware)
