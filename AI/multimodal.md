---
series: "AI 서빙 인프라: GPU부터 문서 파싱까지"
seriesOrder: 10
---

# 멀티모달 LLM (Multimodal Large Language Model)

- 여러 종류의 입력을 동시에 이해하고 처리할 수 있는 LLM
- 즉, 기존 LLM이 텍스트만 이해했다면, 멀티모달 LLM은 다음을 모두 처리할 수 있다
  - 텍스트
  - 이미지
  - 음성
  - 비디오
  - 코드

이미지와 텍스트를 함께 다루는 모델을 특히 **VLM**(Vision-Language Model)이라고 부른다.
요즘 쓰는 GPT-4o, Claude, Gemini가 모두 이 계열이다.

## 멀티모달(Multimodal)의 의미

- Modal(모달) = 정보의 형태(표현 방식)
  - 텍스트 = 언어 모달
  - 이미지 = 시각 모달
  - 음성 = 오디오 모달
- Multi-modal = 여러 모달을 한 번에 다루는 것
  - 예:
    - 이미지 + 텍스트
    - 음성 + 텍스트
    - 비디오 + 텍스트
    - 이미지 + 텍스트 + 오디오

## 모델은 이미지를 어떻게 "이해"하나

텍스트만 받던 LLM이 어떻게 이미지를 같이 읽는지가 핵심이다.
VLM은 보통 세 부품으로 나뉜다.

1. **Vision encoder** — 이미지를 패치(작은 사각형)로 쪼개고, 각 패치를 벡터(visual token)로 바꾼다. CLIP·SigLIP 같은 인코더가 이 역할을 한다.
2. **Projector** — vision encoder가 만든 visual token을, LLM이 알아듣는 텍스트 토큰과 **같은 공간**으로 옮긴다. MLP 한 층이거나 Q-Former 같은 구조를 쓴다.
3. **LLM** — 이렇게 변환된 이미지 토큰을 텍스트 토큰과 나란히 이어 붙여, 평소처럼 다음 토큰을 생성한다.

흐름을 한 줄로 줄이면 이렇다.

```text
이미지 → 패치 분할 → vision encoder → visual token → projector → (텍스트 토큰과 결합) → LLM
```

즉 모델은 이미지를 "픽셀"로 보는 게 아니라, 텍스트와 같은 좌표계의 토큰으로 바꿔 놓고 언어처럼 읽는다.
이 발상은 [임베딩](./RAG/embedding.md)이 텍스트를 벡터 공간에 올리는 것과 같은 계열이다 — 다른 모달을 공통 벡터 공간에서 만나게 한다.

## 텍스트와 이미지를 합치는 방식 (fusion)

두 모달을 어느 지점에서 섞느냐로 갈린다.

- **Early fusion** — 이미지 토큰을 입력 시퀀스에 텍스트 토큰과 함께 넣어 처음부터 같이 처리한다. 시각적 근거(visual grounding)를 일찍 잡는다.
- **Cross-attention fusion** — 텍스트는 텍스트대로 흐르고, 중간중간 cross-attention으로 이미지 정보를 끌어와 참조한다. 깊은 층에서 효율이 좋다.

요즘 모델은 둘을 섞은 **hybrid**가 많다 — 앞쪽 몇 층은 early fusion으로 근거를 잡고, 이후는 sparse cross-attention으로 비용을 아낀다.

## 멀티모달 LLM이 할 수 있는 일

- 이미지 분석 + 설명
  - "이 사진에서 문제가 뭐야?"
- 이미지 기반 Q&A
  - "이 에러 로그가 뜻하는 게 뭐야?"
  - "이 설계도에서 문제점을 찾아줘."
- 문서 이미지 → 내용 이해
  - 스캔된 PDF를 이해하고 요약하기 (문서 파싱은 [Docling](./docling.md)·[STORM Parse](./RAG/storm-parse.md)에서 더 다룬다)
- 음성 → 의미 분석
  - 통화 녹음 요약, 감정 분석, 지시사항 추출
- 비디오 기초 분석
  - 장면 요약, 객체 설명 등
- 여러 모달 결합 reasoning
  - 사진 속 화이트보드 그림을 보고 코드 생성
  - UI 캡처 화면을 보고 UX 개선안 도출
  - 시스템 구조도를 보고 리뷰 작성

## 실제 모델들 (2025~2026)

- **proprietary** — GPT-4o, Claude, Gemini가 이미지·텍스트(일부는 음성·비디오)를 함께 다룬다.
- **vision encoder의 진화** — SigLIP 2가 다국어와 dense feature를 더해 Qwen3-VL·Gemma 3의 기본 인코더로 쓰인다. 여러 인코더를 묶어 더 풍부한 표현을 얻는 시도(Cambrian-1)도 있다.
- **open-source의 추격** — Qwen2.5-VL, InternVL3 같은 오픈 모델이 상용 모델과 5~10% 차이까지 좁혔다. Qwen-VL 계열은 임의 해상도 입력을 지원하고 visual token을 75%까지 압축한다.

## 참고 링크

- [Vision Encoders in Vision-Language Models: A Survey (Jina AI)](https://jina.ai/vision-encoder-survey.pdf)
- [VLM: How Vision-Language Models Work (Label Your Data)](https://labelyourdata.com/articles/machine-learning/vision-language-models)
- [FastVLM — Efficient Vision Encoding (Apple ML Research)](https://machinelearning.apple.com/research/fast-vision-language-models)
