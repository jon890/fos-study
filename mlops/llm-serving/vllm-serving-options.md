---
tags: ["LLM 서빙", "vLLM", "구조화 출력", study]
---

# vLLM에서 JSON 형식과 동시 처리량을 조절하는 법

XGrammar는 모델이 JSON을 생성하는 동안 스키마를 어기는 토큰을 후보에서 뺀다. 선택적 공백을 제한하면 출력 토큰을 공백에 쓰는 문제를 줄일 수 있고, 배열 길이를 제한하면 항목이 끝없이 늘어나는 경로를 닫을 수 있다. 서버의 동시 처리 상한은 GPU에서 한 번에 처리할 시퀀스 수를, 요청의 출력 상한은 한 응답에서 생성할 토큰 수를 제한한다.

공개 구현은 vLLM v0.23.0을 기준으로 읽었다. 운영 사례는 별도로 패치가 있는 이미지와 XGrammar 0.2.8에서 확인했다. [운영 설정과 확인 결과](../../task/ai-service-team/llm-server-structured-output-tuning.md)

## XGrammar가 다음 토큰을 제한하는 방식

Java 서버의 JSON 역직렬화와 Bean Validation은 응답이 만들어진 뒤에 실패를 발견한다. 구조화 출력은 생성 중에 개입한다. 호출자가 JSON Schema를 보내면 vLLM은 선택한 백엔드에 스키마를 넘긴다. XGrammar는 스키마를 문법으로 바꾸고 모델의 토크나이저에 맞춰 컴파일한다. 요청마다 지금까지 생성한 토큰을 반영하는 문법 상태를 유지한다. [vLLM 구조화 출력](https://docs.vllm.ai/en/v0.23.0/features/structured_outputs/), [vLLM XGrammar 백엔드 구현](https://github.com/vllm-project/vllm/blob/v0.23.0/vllm/v1/structured_output/backend_xgrammar.py)

1. 모델이 다음 토큰 후보마다 점수(logit)를 계산한다.
2. XGrammar가 현재 문법 상태에서 이어 붙일 수 있는 토큰을 비트마스크로 표시한다. 예를 들어 숫자 필드의 값을 시작할 자리에 설명 문구를 넣는 토큰은 후보에서 빠진다. 실제 검사는 토큰이 담은 문자열 전체에 적용되므로 한 토큰에 여러 글자나 구두점이 들어가도 처리할 수 있다.
3. vLLM은 허용 후보에서 토큰을 뽑고, 선택한 토큰으로 문법 상태를 갱신한다. 이 과정을 반복한다.

스키마 컴파일과 문법 검사에 시간과 메모리가 든다. XGrammar는 문법 상태에 따라 미리 계산한 마스크를 재사용해 토큰마다 검사할 일을 줄인다. 실제 지연은 스키마 복잡도와 캐시 재사용에 따라 달라진다. 콘텐츠의 사실성이나 업무 규칙은 응답을 받아 별도로 검증한다. [XGrammar 논문](https://arxiv.org/abs/2411.15100)

### 백엔드를 고를 때 보는 차이

vLLM v0.23.0에는 `auto`, `xgrammar`, `guidance`, `outlines`, `lm-format-enforcer`가 있다. `auto`는 vLLM에 선택을 맡긴다. `xgrammar`로 고정하면 요청이 같은 백엔드를 사용하며, 해당 백엔드에서 처리할 수 없는 스키마는 요청 오류로 드러난다. `guidance`도 JSON Schema 기반 제약을 적용할 수 있다. Outlines와 LM Format Enforcer도 후보지만 지원하는 입력 형식, 정규식 문법, JSON Schema 키워드와 공백 처리 방식이 구현마다 다르다. 같은 스키마를 각 백엔드에 넣어 컴파일 여부와 허용·거부 결과를 확인하고, 지연을 비교할 때는 토크나이저와 부하를 맞춘다. [vLLM 백엔드 설정](https://github.com/vllm-project/vllm/blob/v0.23.0/vllm/config/structured_outputs.py), [vLLM 요청 검증 구현](https://github.com/vllm-project/vllm/blob/v0.23.0/vllm/sampling_params.py)

## 공백과 스키마가 닫는 생성 경로

JSON 문법에서 중괄호나 쉼표 주변의 공백은 선택 사항이다. 이를 허용하는 문법에서는 다음 필드 대신 공백을 반복해도 문법을 지킨다. 응답이 길어지면 그만큼 디코딩과 KV cache 점유가 이어지고, 닫는 괄호를 쓰기 전에 출력 상한에 도달할 수 있다.

```bash
--structured-outputs-config '{"backend":"xgrammar","disable_any_whitespace":true}'
```

vLLM v0.23.0의 XGrammar 백엔드는 서버 설정을 읽어 JSON 문법을 컴파일할 때 `any_whitespace`를 끈다. 구분 기호 주변의 임의 공백을 제한하면서 `"hello world"`처럼 문자열 값에 들어 있는 공백은 허용한다. 공백 반복을 막으면 낭비하는 토큰을 줄일 수 있다. XGrammar 0.2.8에는 쉼표 뒤의 공백을 지우도록 구분 기호를 지정해도 공백 하나가 남는 버그가 있었고, 0.2.9에서 수정됐다. 반복 공백을 막는지와 한 칸도 없는 JSON을 만드는지는 대상 이미지에서 각각 확인한다. [vLLM XGrammar 구현](https://github.com/vllm-project/vllm/blob/v0.23.0/vllm/v1/structured_output/backend_xgrammar.py), [XGrammar 공백 버그](https://github.com/mlc-ai/xgrammar/issues/945), [XGrammar 0.2.9 릴리스](https://github.com/mlc-ai/xgrammar/releases/tag/v0.2.9)

| 허용되는 출력 | 적용할 제약 | 바뀌는 동작 |
| --- | --- | --- |
| 배열에 같은 객체를 계속 추가 | `maxItems` | 상한에 도달하면 다음 항목을 시작할 수 없다. 상한 안의 중복은 내용 검증으로 잡는다 |
| 근거가 있어야 하는 항목에 빈 근거 배열 | 근거 배열에 `minItems: 1` | 근거를 한 개 이상 써야 배열을 닫을 수 있다. 결과가 0건일 수 있다면 바깥 배열은 비울 수 있게 둔다 |
| 필드가 빠진 빈 객체 또는 빈 문자열 | `required`와 값의 타입, 필요하면 `minLength` | `required`는 필드가 있는지 제한한다. 빈 문자열이나 `null`까지 금지하려면 값에도 제약을 건다 |

강한 제약은 무의미하게 길어지는 응답을 줄일 수 있다. 상한을 너무 낮추면 필요한 항목도 누락될 수 있고, 최소 개수를 과하게 요구하면 근거가 없을 때도 모델이 무언가 채우게 된다. 빈 결과, 최소·최대 경계, 경계를 하나씩 넘는 입력을 실제 백엔드에서 검증한다. [XGrammar 0.2.8 JSON Schema 변환 구현](https://github.com/mlc-ai/xgrammar/blob/v0.2.8/cpp/json_schema_converter.cc)

## 동시 처리 상한과 대기 시간

`--max-num-seqs`는 한 스케줄러 반복에서 처리할 시퀀스 수의 상한이다. HTTP 연결 수를 제한하는 옵션과는 적용 위치가 다르다. 연속 배칭에서는 한 시퀀스가 끝나면 다음 반복에서 대기하던 시퀀스를 넣을 수 있다. 상한에 닿기 전에도 계산할 토큰 수(`--max-num-batched-tokens`)나 KV cache가 부족하면 기다릴 수 있다. [vLLM 스케줄러 옵션](https://docs.vllm.ai/en/v0.23.0/cli/serve/#schedulerconfig)

상한을 올리면 GPU가 한 번에 더 많은 시퀀스를 처리해 전체 출력 토큰 수가 늘 수 있다. 그만큼 길이가 제각각인 시퀀스의 KV cache가 동시에 필요하다. GPU가 이미 포화라면 반복 한 번이 길어지고, 토큰 사이 지연이나 p95 완료 시간이 늘 수 있다. 상한을 낮추면 동시에 쓰는 자원을 줄이는 대신 초과 요청의 큐 대기와 첫 토큰까지의 시간이 길어질 수 있다. 부하 비교에서는 입력·출력 길이 분포를 맞추고, 출력 tok/s와 함께 큐 대기, 첫 토큰 지연, 토큰 사이 지연, KV cache 사용률과 선점을 본다.

> [!TIP]
> **더 읽을 글** [배칭과 GPU 활용률](./continuous-batching-gpu-utilization.md). 요청을 묶으면 같은 가중치를 읽는 비용을 어떻게 나눠 갖는지 설명한다.

## 다른 기동 옵션이 바꾸는 자원과 동작

| 옵션 | 올리거나 켜면 달라지는 것 |
| --- | --- |
| `--gpu-memory-utilization` | vLLM 인스턴스의 GPU 메모리 예산 비율이다. 높이면 KV cache에 쓸 공간이 늘 수 있고 다른 프로세스나 일시적인 메모리 사용에 남는 여유가 줄어든다 |
| `--max-model-len` | 입력과 출력의 합으로 보는 문맥 길이 상한이다. 길게 허용하면 큰 요청을 처리할 수 있지만, 그런 요청이 들어오면 KV cache와 입력 계산 비용이 커진다 |
| `--tensor-parallel-size` | 가중치와 연산을 여러 GPU에 분할한다. GPU당 가중치 부담을 줄이는 대신 GPU 간 통신이 들어간다 |
| `--enable-expert-parallel` | MoE의 expert를 GPU에 나눠 배치한다. 토큰을 선택된 expert에 보내고 결과를 모으므로 GPU 연결과 expert별 부하 분포가 처리량에 영향을 준다 |
| `--speculative-config` | 초안 토큰을 여러 개 제안하고 본 모델이 검증한다. 여러 개가 수락되면 생성 반복을 줄일 수 있다. 초안이 자주 거절되거나 GPU가 바쁘면 추가 계산과 메모리가 부담이 된다 |
| `--reasoning-parser`, `--tool-call-parser`, `--enable-auto-tool-choice` | 모델 출력에서 추론과 도구 호출을 분리하고 자동 도구 선택 요청을 받는다. 모델 출력 형식과 파서가 어긋나면 응답 해석이나 도구 호출이 실패할 수 있다 |
| 모델 위치, `--served-model-name`, `--host`, `--port` | 로딩할 모델, 클라이언트가 요청할 이름, 서버가 수신할 인터페이스와 포트를 정한다. 모델 선택은 메모리와 출력 품질에 영향을 주며, 나머지는 연결 계약과 배포 설정에 해당한다 |

[vLLM v0.23.0 기동 옵션](https://docs.vllm.ai/en/v0.23.0/cli/serve/), [추측 디코딩과 vLLM 적응형 검증](./speculative-decoding-adaptive-verification.md)

## 출력 상한과 해석 실패를 확인하는 법

출력 상한은 디코딩에 쓰는 비용을 제한한다. Chat Completions에서는 `max_completion_tokens` 또는 기존 `max_tokens`를, Responses에서는 `max_output_tokens`를 확인한다. 요청 예산에는 추론 모델이 생성한 추론 토큰이 포함될 수 있다. 모델 문맥에 남은 토큰 수도 실제 출력 길이를 제한한다. [vLLM Chat Completions 요청 구현](https://github.com/vllm-project/vllm/blob/v0.23.0/vllm/entrypoints/openai/chat_completion/protocol.py), [vLLM Responses 요청 구현](https://github.com/vllm-project/vllm/blob/v0.23.0/vllm/entrypoints/openai/responses/protocol.py)

| 관찰한 현상 | 확인할 것 |
| --- | --- |
| 토큰 상한에 도달하고 JSON이 중간에서 끊김 | 종료 사유와 사용량을 먼저 본다. Chat Completions의 `finish_reason: length`가 대표 신호다. 마지막 부분을 보고 정상 데이터에 예산이 부족했는지, 공백이나 반복에 예산을 썼는지 구분한다 |
| 정상 종료했지만 JSON 앞에 설명 또는 도구 표식이 붙음 | JSON 필드의 원문, 프록시가 upstream에 전달한 스키마, 도구 선택과 추론 파서 설정을 확인한다. 스키마가 실제 응답 구간에 적용됐다면 객체 앞 설명은 허용되지 않으므로, 어느 단계에서 붙었는지 확인한다 |
| JSON은 읽히지만 항목이 비거나 중복됨 | 스키마가 허용한 형태인지 본다. 항목 수와 필수 필드를 제한하고, 사실성 및 내용 중복은 애플리케이션 검증으로 다룬다 |

상한을 높이기 전 정상 응답의 출력 길이 분포와 실패한 응답의 끝부분을 대조한다. 정상 데이터 때문에 잘렸다면 예산 조정이 도움이 되고, 공백이나 반복이 원인이면 문법이나 스키마에서 그 경로를 닫아야 한다.
