---
tags: ["Model Router", "LiteLLM", "LLM 서빙", study]
series: "Model Router"
seriesOrder: 6
---

# LiteLLM 로 라우팅 정책을 설정하는 방법

> Model Router 시리즈 6번이다.
> 앞 글 [첫 토큰이 나간 뒤에는 재시도할 수 없다](./streaming-retry-boundary.md)에서 streaming 중 장애의 경계를 다뤘다.
> 이 글은 그 경계와 라우팅 판단을 실제 설정으로 옮기는 방법을 다룬다.

앞의 글들이 "무엇을 정해야 하는가" 를 다뤘다면 이 글은 "그것을 어디에 적는가" 를 다룬다.
대상은 LiteLLM proxy 다.
관리형 라우터로 부족하고 완전히 자체 구축하기에는 이른 구간에 놓이는 오픈소스이고, KT 의 Model Orchestrator 도 인증과 로깅과 모니터링을 여기에 맡겼다.

이 글의 설정 값은 공식 문서에서 확인한 것만 담는다.
문서로 확정할 수 없었던 것은 확정할 수 없다고 적는다.

## 라우팅 전략 다섯

`router_settings.routing_strategy` 에 둔다.
여기서 정하는 것은 **한 모델 그룹 안에서 어느 배포로 보낼지**다.
어느 모델을 쓸지는 애플리케이션이 모델 그룹 이름으로 지정하거나 fallback 이 정한다.

| 전략 | 읽는 값 | 판단 |
| --- | --- | --- |
| `simple-shuffle` (기본) | 배포별 `rpm`, `tpm`, 선택적 `weight` | rpm 이나 tpm 이 있으면 그 값 기준으로 고르고, 없으면 무작위. `weight` 를 주면 그 비율대로 선택 빈도가 갈린다 |
| `least-busy` | 배포별 진행 중인 요청 수 | 활성 요청이 가장 적은 배포 |
| `usage-based-routing` | 배포별 `tpm`, `rpm` 한도와 Redis 로 추적한 현재 사용량 | 현재 분 기준 TPM 사용량이 가장 낮은 배포. 한도를 넘긴 배포는 제외 |
| `latency-based-routing` | 배포별 응답 시간 이력 | 평균 지연이 가장 낮은 배포 |
| `cost-based-routing` | `litellm_model_cost_map` 또는 토큰당 단가 | rpm, tpm 한도 안의 배포 중 토큰당 비용이 가장 낮은 것 |

**다섯 중 캐시 상태를 보는 것이 없다.**
캐시 인식 라우팅은 vLLM production-stack 과 llm-d 가 아래 계층에서 제공한다.
계층이 다르므로 위 계층 도구에 아래 계층 기능을 기대하면 없는 것을 찾게 된다.
그 계층의 동작은 [캐시를 보고 인스턴스를 고른다](./cache-aware-routing.md)에서 다뤘다.

### 기본값이 `simple-shuffle` 인 이유

공식 문서는 고트래픽 프로덕션 기본으로 `simple-shuffle` 을 권장한다.
반대로 `usage-based-routing` 은 프로덕션에 권장되지 않는다.
요청 경로에 Redis 조회가 끼기 때문이다.

**여기서 읽을 것은 라우팅 판단이 요청 경로 안에 있다는 점이다.**
더 정밀한 판단을 하려고 외부 저장소를 읽으면 그 왕복 시간이 모든 요청에 얹힌다.
정밀도를 올리는 판단이 지연을 올리는 구조가 라우팅 계층 전체에 반복해서 나온다.

### 가장 빠른 하나로 몰리는 것을 막는 장치

`latency-based-routing` 을 그대로 쓰면 평균 지연이 가장 낮은 배포 하나로 요청이 계속 간다.
그 배포가 포화되어 느려질 때까지 몰린 뒤에야 다른 쪽으로 옮겨간다.

`routing_strategy_args.lowest_latency_buffer` 가 이것을 완화한다.
허용 오차 구간을 두면 그 범위 안의 배포끼리 요청을 분산한다.

Routing Groups 로 모델 그룹마다 다른 전략을 쓸 수 있다.
품질이 중요한 모델 그룹은 `latency-based-routing` 으로 두고, 싼 모델 그룹은 `simple-shuffle` 로 두는 식이다.

## fallback 세 종류

**오류 종류에 따라 발동하는 키가 다르다.**
하나의 fallback 목록으로 모든 오류를 처리하지 않는다는 것이 이 설계의 핵심이다.

| 키 | 발동 조건 |
| --- | --- |
| `fallbacks` | 나머지 모든 오류. `litellm.RateLimitError` 등 |
| `context_window_fallbacks` | `litellm.ContextWindowExceededErrors` 에만 |
| `content_policy_fallbacks` | `litellm.ContentPolicyViolationError` 에만 |
| `default_fallbacks` | 모델 그룹 설정이 잘못됐을 때의 전역 기본값. 모델별 폴백이 우선한다 |

형식은 `[{"primary-model": ["fallback1", "fallback2"]}]` 이고 리스트 순서대로 시도한다.

키를 나눈 이유는 오류마다 옮겨갈 곳이 다르기 때문이다.

- 컨텍스트 초과는 **더 큰 컨텍스트를 가진 모델**로 가야 한다. 같은 크기의 다른 배포로 가면 같은 오류가 반복된다
- 콘텐츠 정책 위반은 **정책이 다른 제공자**로 가야 한다. 같은 제공자의 다른 배포는 같은 정책을 쓴다
- rate limit 은 **같은 모델의 다른 배포**로도 해결된다

`enable_pre_call_checks: true` 를 켜면 컨텍스트 초과 여부를 호출 전에 확인한다.
`context_window_fallbacks` 가 실패한 뒤에 옮기는 장치라면 이쪽은 실패 자체를 막는 장치다.
컨텍스트 한도가 라우팅에서 왜 먼저 걸리는지는 [모델을 골라주는 계층이 대신 가져오는 제약](./router-constraints.md)에서 다뤘다.

## cooldown

실패한 배포를 일정 시간 후보에서 빼는 장치다.

| 키 | 뜻 |
| --- | --- |
| `allowed_fails` | 분당 허용 실패 횟수 |
| `cooldown_time` | 배포가 cooldown 을 유지하는 시간 |
| `allowed_fails_policy` | 오류 유형별 임계치 |
| `disable_cooldowns` | 전체 비활성화 |
| `num_retries` | 요청당 재시도 횟수. 기본 3 |

진입 조건이 넷이다.

- 분당 실패가 `allowed_fails` 를 넘으면 진입한다
- 429 는 즉시 cooldown 이다
- 401, 404, 408 처럼 재시도가 무의미한 오류에서도 발동한다
- 분당 실패율이 50% 를 넘어도 발동한다

cooldown 에 들어간 배포나 모델 그룹에서 빠진 배포는 건너뛰고, 남은 정상 배포에 라우팅 전략을 다시 적용한다.
전략과 cooldown 이 순서대로 동작한다는 뜻이다. 먼저 후보를 걸러내고 그다음 전략이 고른다.

### 모든 실패를 같게 세지 않는다

**`allowed_fails_policy` 가 오류 유형마다 다른 임계치를 준다.**
공식 문서 예시는 인증 실패 1, 타임아웃 3, 잘못된 요청 1000 이다.

값의 크기 차이가 의도를 그대로 말한다.

| 오류 | 예시 임계치 | 뜻 |
| --- | --- | --- |
| 인증 실패 | 1 | 한 번 나면 설정이 잘못된 것이다. 재시도해도 같다 |
| 타임아웃 | 3 | 일시적일 수 있으므로 몇 번은 본다 |
| 잘못된 요청 | 1000 | 호출하는 쪽 잘못이다. 배포를 빼면 안 된다 |

마지막 줄이 이 설정을 두는 이유다.
잘못된 요청을 실패로 세면 애플리케이션 버그 하나가 정상인 배포를 후보에서 빼낸다.
직접 라우터를 만들 때도 실패 카운터를 오류 유형별로 나눠야 하는 근거가 여기 있다.

### `cooldown_time` 기본값은 문서로 확정할 수 없었다

**공식 문서마다 예시값이 다르다.**
설정 문서는 30초를 들고, 라우팅 문서는 5초를 든다.
어느 쪽이 코드상 기본값인지 문서만으로 가릴 수 없어 이 글에서는 값을 단정하지 않는다.

운영에 넣을 때는 값을 명시적으로 지정하는 편이 낫다.
기본값에 의존하면 버전이 올라갈 때 동작이 바뀌어도 알아채기 어렵다.

같은 이유로 이 글에서 다루지 않는 것들이 있다.
`disable_cooldowns` 의 기본값, `routing_strategy_args.ttl` 의 기본값, `least-busy` 가 활성 요청을 어느 시점부터 어느 시점까지로 세는지를 문서에서 확인하지 못했다.
`usage-based-routing` 의 v1 과 v2 계산식 차이도 그렇다.

## 예산과 rate limit 계층

라우팅과 별개로 누가 얼마까지 쓸 수 있는지를 정하는 층이 있다.
**계층은 Keys, Teams, Global 순으로 우선한다.**

| 대상 | 키 | 초과 시 |
| --- | --- | --- |
| 팀 | `max_budget`, `budget_duration` | HTTP 400, `auth_error` 타입 |
| 키와 사용자 | `max_budget`, `budget_duration` | HTTP 401 또는 400 |
| 모델별 예산 | `model_max_budget` | 그 모델에만 예산 오류 |
| 키와 사용자의 호출 한도 | `rpm_limit`, `tpm_limit`, `max_parallel_requests` | HTTP 429 |
| 모델별 호출 한도 | `model_rpm_limit`, `model_tpm_limit` | 그 모델 요청에 429 |
| 배포 자체 | `litellm_params.rpm`, `litellm_params.tpm` | 라우팅 후보에서 제외 |

**마지막 줄만 성격이 다르다.**
앞의 것들은 호출하는 쪽에 오류를 돌려주고, 배포 자체의 한도는 오류 없이 라우팅 후보에서 빠진다.
같은 `rpm` 이라는 이름이 두 자리에서 다르게 동작한다.

단가가 0 인 모델은 예산 검사를 건너뛴다.
자체 호스팅 모델의 단가를 설정하지 않은 채 두면 예산 통제 밖에 놓인다는 뜻이다.

`/budget/new` 로 예산 티어를 만들어 키에 `budget_id` 로 붙일 수 있다.
팀마다 값을 반복해 적지 않고 티어 하나를 여러 키에 재사용하는 방식이다.

## 관측

라우팅 결정을 사후에 되짚는 방법이다.

| 방법 | 담는 것 |
| --- | --- |
| 응답 헤더 | `x-litellm-model-id`, `x-litellm-model-api-base`, `x-litellm-response-cost`, `x-litellm-call-id` |
| 로그 | `StandardLoggingPayload` 에 비용, 토큰 수, 모델 정보 |
| 라우팅 지표 | `litellm_deployment_success_responses`, `litellm_deployment_failure_responses`, `litellm_deployment_total_requests` |
| fallback 지표 | `litellm_deployment_successful_fallbacks`, `litellm_deployment_failed_fallbacks`, `litellm_deployment_cooled_down` |
| 예산 지표 | `litellm_remaining_team_budget_metric`, `litellm_remaining_api_key_budget_metric` 계열 |
| 호출 한도 지표 | `litellm_remaining_api_key_requests_for_model`, `litellm_remaining_api_key_tokens_for_model` |

**어느 배포가 선택됐는지는 응답 헤더로 확인한다.**
직접 만드는 라우터도 이 정보를 남겨야 결정을 사후에 되짚을 수 있다.

`litellm_deployment_cooled_down` 을 지표로 보는 것이 특히 유용하다.
cooldown 은 설정대로 조용히 동작하므로, 이 값이 오르는 것을 보지 않으면 특정 배포가 계속 빠진 채로 운영되는 것을 모른다.

## MCP gateway

라우팅과 직접 관련은 없지만 같은 proxy 가 겸하는 기능이라 적어 둔다.

여러 MCP 서버를 등록해 단일 endpoint 로 노출하고 키와 팀 단위로 접근을 통제한다.
전송 방식은 Streamable HTTP, SSE, Standard I/O 셋을 지원한다.
인증은 OAuth 2.0, AWS SigV4, API key, 헤더 전달을 지원한다.

MCP Cost Tracking 으로 도구 호출별 비용을 집계한다.
`default_cost_per_query` 나 `tool_name_to_cost_per_query` 로 고정 비용을 주거나 훅으로 계산한다.

모델 호출과 도구 호출의 비용을 한 곳에서 합산한다는 것이 이 기능의 의미다.
agent 를 운영하면 도구 호출 비용이 모델 호출 비용과 같은 크기로 커질 수 있다.

## 정리

- `routing_strategy` 다섯은 한 모델 그룹 안에서 어느 배포로 보낼지를 정한다. 다섯 중 캐시 상태를 보는 것은 없다.
- 정밀한 판단은 지연을 얹는다. `usage-based-routing` 이 프로덕션에 권장되지 않는 이유가 요청 경로의 Redis 조회다.
- fallback 키가 셋으로 나뉜 이유는 오류마다 옮겨갈 곳이 다르기 때문이다. 컨텍스트 초과는 더 큰 모델로, 정책 위반은 다른 제공자로 가야 한다.
- `allowed_fails_policy` 가 오류 유형별 임계치를 준다. 잘못된 요청을 실패로 세면 애플리케이션 버그가 정상 배포를 후보에서 빼낸다.
- `cooldown_time` 의 기본값은 공식 문서만으로 확정할 수 없었다. 운영에서는 값을 명시적으로 지정한다.
- 같은 `rpm` 이라는 이름이 키 계층에서는 429 를 돌려주고 배포 계층에서는 후보 제외로 동작한다.

## 다음 편

다음 글에서는 자체 호스팅 vLLM 이 노출하는 지표를 라우팅 판단에 쓰는 방법을 다룬다.
TTFT 와 토큰 간 지연이 어떻게 연결돼 있는지, 처리량이 떨어졌을 때 무엇을 어느 순서로 보는지, 한 설정 값이 두 지표를 반대로 미는 구간이 주제다.

[vLLM 지표를 라우팅 판단에 쓰는 방법](./vllm-metrics-for-routing.md)으로 이어진다.

## 참고 링크

- [LiteLLM Router. Load Balancing](https://docs.litellm.ai/docs/routing)
- [LiteLLM Proxy. Load Balancing](https://docs.litellm.ai/docs/proxy/load_balancing)
- [LiteLLM Fallbacks](https://docs.litellm.ai/docs/proxy/reliability)
- [LiteLLM proxy 설정 값](https://docs.litellm.ai/docs/proxy/config_settings)
- [LiteLLM. Setting Team Budgets](https://docs.litellm.ai/docs/proxy/team_budgets)
- [LiteLLM. Budgets, Rate Limits](https://docs.litellm.ai/docs/proxy/users)
- [LiteLLM Logging](https://docs.litellm.ai/docs/proxy/logging)
- [LiteLLM. Manage Routing Groups](https://docs.litellm.ai/docs/proxy/ui/routing_groups)
- [LiteLLM MCP Overview](https://docs.litellm.ai/docs/mcp)
- [LiteLLM MCP Cost Tracking](https://docs.litellm.ai/docs/mcp_cost)
- [KT. Model Orchestrator](https://enterprise.kt.com/bt/blog/3691.do)
