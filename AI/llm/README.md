# LLM 내부 구조

Transformer의 계산 구조에서 시작해 학습과 생성, 환각, 긴 컨텍스트 실패까지 연결하는 학습 문서다.

## 읽는 순서

1. [Transformer는 입력을 어떻게 다음 토큰 확률로 바꾸는가](./transformer-from-tokens-to-logits.md)
   token과 embedding부터 Q·K·V, FFN, positional encoding, logits, KV cache까지 계산 흐름을 따라간다.
2. [다음 토큰 예측은 왜 환각과 긴 컨텍스트 실패로 이어지는가](./why-llms-hallucinate-and-lose-context.md)
   next-token 학습과 자동회귀 생성이 truthfulness, source faithfulness, 긴 context 활용과 어떻게 어긋날 수 있는지 설명한다.
3. [Lost in the Middle와 컨텍스트 관리](../agent/lost-in-the-middle-context-management.md)
   관찰된 한계를 context 조립, 상태 외부화, 구현자와 검토자 분리 같은 시스템 설계로 연결한다.

## 문서별 경계

| 문서 | 중심 질문 | 다루지 않는 것 |
| --- | --- | --- |
| Transformer 계산 구조 | model 내부에서 token 하나가 어떻게 생성되는가 | 환각 완화 시스템의 상세 구현 |
| 환각과 긴 context | 왜 유창함이 사실성과 같지 않은가 | agent 상태 관리 절차 |
| context 관리 | model 한계를 시스템에서 어떻게 통제하는가 | Q·K·V 수식의 상세 유도 |
