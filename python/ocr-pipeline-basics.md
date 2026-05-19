# OCR 동작 원리 — Layout · Text · Post-process 3단계

자바 백엔드만 다뤄오다가 OCR (Optical Character Recognition) 서비스를 분석할 일이 생겼다. "이미지에서 글자를 뽑는다" 라는 한 줄 요약은 알았지만, 실제 코드를 열어보면 모델이 둘이상이고, 여러 단계가 직렬·병렬로 엮여 있고, "왜 이 단계가 따로 있지" 같은 의문이 계속 생긴다.

이 글은 OCR 파이프라인의 표준 구조를 정리하고, 자바 백엔드 관점에서 ETL 파이프라인과 1:1 로 비유한다. 내가 직접 분석한 ML 서비스의 흐름을 일반화해서 예시로 든다.

## 큰 그림 — Layout → Text → Post-process

OCR 시스템은 보통 다음 3단계로 나뉜다.

```
이미지/PDF 페이지
    ↓ [1. Layout Detection]
박스 단위로 잘린 영역들 (텍스트 박스, 테이블 셀, 그림)
    ↓ [2. Text Recognition]
각 박스의 텍스트 + 신뢰도
    ↓ [3. Post-processing]
정렬된 글, 표 구조, markdown
```

자바 ETL 파이프라인에 비유하면 다음과 같다.

| ETL 단계 | OCR 대응 |
|---|---|
| Extract (소스 데이터 추출) | Layout Detection — "어디에 글이 있는가" |
| Transform (정제·변환) | Text Recognition — "이 박스에는 무슨 글자가 적혀 있는가" |
| Load (정형 저장) | Post-processing — "전체를 정렬해 markdown/JSON 으로" |

각 단계가 별도 모델 또는 라이브러리로 구현되어 있고, 자바 Spring Batch 의 `Reader → Processor → Writer` 와 같은 분리 패턴을 따른다.

## 1단계 — Layout Detection

목적: **이미지 안의 어디에 무엇이 있는지** 박스로 잡아낸다. 텍스트 영역, 테이블, 이미지, 헤더, 푸터, 페이지 번호 같은 구조 요소.

대표 모델은 LayoutLM, DocLayout-YOLO, PubLayNet, Donut 류의 transformer 기반 모델. CV (computer vision) 의 object detection 기법을 문서 영역에 특화한 것.

출력: 각 영역의 (x, y, width, height) 좌표 + 카테고리 (text / table / image / title 등).

```python
# Layout 모델 출력 예시
{
  "blocks": [
    {"bbox": (50, 100, 500, 150), "category": "title"},
    {"bbox": (50, 200, 500, 400), "category": "text"},
    {"bbox": (50, 450, 500, 600), "category": "table"},
    {"bbox": (200, 650, 300, 750), "category": "image"},
  ]
}
```

자바 백엔드 비유: HTML 페이지를 파싱해 `<div>`, `<table>`, `<img>` 같은 구조 요소를 식별하는 작업. JSoup 으로 DOM 트리를 만드는 것과 의도가 같다. 다만 입력이 HTML 마크업이 아니라 픽셀 이미지라 ML 모델이 필요한 것.

이 단계가 빠질 수도 있다. 단순히 "이 이미지의 모든 글자를 뽑아줘" 라면 Layout 없이 Text Recognition 으로 바로 갈 수 있다. 그러나 문서 구조 (표·헤더·본문 분리) 가 필요하면 Layout 이 선행돼야 한다.

## 2단계 — Text Recognition

목적: **잘린 박스 안의 픽셀을 글자 시퀀스로** 변환. OCR 의 핵심.

대표 라이브러리:
- **PaddleOCR** — 중국어·일본어·한국어·영어 다국어, 가볍고 빠름. det (detection) + rec (recognition) + cls (orientation) 세 모델 조합.
- **EasyOCR** — 다언어 지원, PyTorch 기반.
- **Tesseract** — 가장 오래된 OSS OCR, 정확도는 현대 ML 대비 떨어짐.
- **Cloud OCR API** (NHN Cloud OCR, AWS Textract, Google Vision 등) — REST 호출, 별도 인프라 불필요, 비용 발생.

내부적으로 Recognition 모델은 보통 CNN + RNN (또는 Transformer) 의 조합. CRNN, TrOCR 같은 아키텍처. 입력은 작은 텍스트 박스 이미지, 출력은 문자 시퀀스 + 각 문자의 신뢰도.

```python
# Text Recognition 출력 예시
{
  "text": "안녕하세요",
  "confidence": 0.92,
  "char_confidences": [0.95, 0.93, 0.91, 0.92, 0.89],
}
```

자바 비유: 한 문자열 필드에 대해 자연어 처리 후 정규화·검증을 적용하는 단계. Bean Validation 의 `@Pattern` 이 글자가 맞는지 확인하는 것과 비슷한 위치.

### 한국어·일본어 처리의 분기

언어별로 모델이 다르다. 한국어 OCR 은 한글 음절 + 한자 혼용, 일본어는 히라가나·가타카나·한자가 섞여 모델 학습 데이터가 다르다. 한 시스템 안에 두 OCR 엔진을 두는 게 흔하다.

분석한 ML 서비스도 같은 패턴이었다. KR (한국어) 워커는 Cloud OCR API 를 호출하고, JA (일본어) 워커는 로컬 PaddleOCR 모델을 사용. 같은 Docling 파이프라인 안에서 plugin 으로 분기하는 구조.

자바라면 같은 인터페이스를 구현하는 두 개의 `@Service` 빈을 `@Qualifier` 로 분기하는 패턴.

```python
# Python 의 OCR 엔진 추상화
class OcrEngine(Protocol):
    def recognize(self, image) -> list[OcrResult]: ...

class CloudOcr(OcrEngine):
    def recognize(self, image):
        return call_cloud_api(image)

class LocalOcr(OcrEngine):
    def recognize(self, image):
        return paddle_predict(image)
```

[Post 2 의 Protocol 패턴](./java-to-python-oop-decorator.md) 이 그대로 적용된다.

## 3단계 — Post-processing

목적: 박스별 인식 결과를 **사람이 읽을 수 있는 글로** 재조합. 페이지의 reading order 결정, 표 구조 복원, markdown 변환, 신뢰도 필터링.

가장 까다로운 단계. 픽셀 좌표만으로는 "이 박스가 다음 박스의 앞인가 뒤인가" 가 자명하지 않다. 다단 레이아웃, 표 안의 셀, 각주 같은 케이스가 여기서 다뤄진다.

대표적인 처리:
- **Reading order** — bbox 좌표 + Layout 카테고리로 자연스러운 순서 추정
- **Table extraction** — 셀의 행·열을 좌표로 복원해 표 JSON 만들기 (HTML → JSON, 또는 직접 grid 재구성)
- **Confidence filtering** — 낮은 신뢰도 박스 제외 (예: `< 0.3` 인 결과는 버림)
- **Cell matching** — Layout 의 표 영역과 텍스트 박스를 매칭. 표 영역 안에 있는 텍스트만 그 표의 셀로 인식
- **Markdown 변환** — 헤더·리스트·인용·이미지 임베딩 처리

자바 비유: Spring Batch 의 `ItemWriter` + JSON serialization 단계. 변환된 데이터를 출력 포맷에 맞게 정렬·구조화.

이 단계가 OCR 시스템의 품질을 좌우한다. 같은 모델 출력이라도 후처리가 약하면 표가 깨지거나 reading order 가 뒤죽박죽이 된다.

## PDF 처리의 추가 단계

이미지 OCR 은 위 세 단계지만 PDF 는 한 단계 더 있다. PDF 자체가 **벡터 + 텍스트 + 이미지** 가 섞인 포맷이기 때문.

```
PDF 파일
    ↓ [PDF Backend — pypdfium / poppler / docling-parse]
페이지별 이미지 (PNG/픽셀 데이터) + 메타데이터 (텍스트 레이어 있는 경우)
    ↓ [위 세 단계 OCR 파이프라인]
markdown
```

PDF 에 텍스트 레이어가 있으면 OCR 없이도 글자 추출 가능 (PyPDF2, pdfplumber). 하지만 스캔본·이미지화된 PDF 는 OCR 이 필수.

분석한 서비스의 Docling 라이브러리가 이 PDF rendering + OCR 통합을 담당한다. PDF backend 선택, page batch size, image scale 같은 옵션이 성능에 직결되는 부분.

## 성능 함정 — OCR 단계가 외부 API 직렬 호출일 때

OCR 단계가 클라우드 API 호출이면 latency 의 지배 요인이 GPU 가 아니라 네트워크가 된다. 우리 분석에서 가장 큰 병목으로 잡힌 패턴.

```python
# 안티 패턴 — 페이지마다 직렬 API 호출
for page in pdf_pages:
    for region in page.text_regions:
        result = call_cloud_ocr_api(region.image)   # 동기 HTTP, 페이지당 N번
        merge(result)
```

페이지 수 × 영역 수만큼 RTT 가 누적된다. 30 페이지 PDF + 페이지당 평균 5 영역 = 150 회 직렬 HTTP. GPU 는 idle 한 채로 네트워크 대기.

[async/await 글](./java-to-python-async-blocking-io.md) 의 `run_in_executor` 또는 `ThreadPoolExecutor` 를 활용한 동시 호출이 거의 무조건 필요. 자바 진영에서 마이크로서비스 호출을 `CompletableFuture.allOf(...)` 로 fan-out 하는 것과 같은 패턴.

```python
# 권장 패턴 — 영역 병렬 호출
with ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(call_cloud_ocr_api, regions))
```

OCR API 의 rate limit 와 동시 호출 제한을 확인해 worker 수를 결정한다. 너무 많이 동시 호출하면 429 (Too Many Requests) 가 난다.

## 신뢰도 (confidence) 의 의미

OCR 모델은 각 문자·박스에 0.0 - 1.0 사이의 신뢰도를 부여한다. 자바에서는 직접 다룰 일이 거의 없던 개념.

이걸 후처리 임계값으로 쓴다. 예: `confidence_threshold=0.3` 이면 30% 미만은 버림. 너무 낮으면 노이즈 (이미지의 점·얼룩을 글자로 인식한 결과) 가 포함되고, 너무 높으면 흐릿한 글자가 누락된다.

분석한 서비스는 기본값이 `0.0` 으로 모든 결과를 통과시키고 있었다. 표·작은 글자 인식에는 안전하지만 후처리·markdown 생성 부담이 늘어 성능 이슈로 잡혔다. A/B 로 0.3 정도까지 올려도 회귀가 적으면 throughput 이득.

## 정리

자바 백엔드 개발자가 OCR 시스템을 처음 마주할 때 외울 한 줄.

> OCR 은 Layout (어디에 글이 있나) → Recognition (어떤 글자인가) → Post-process (어떻게 묶나) 의 3단계 파이프라인이다. 각 단계는 독립 ML 모델 또는 외부 API 로 구현되며, 자바 ETL 파이프라인의 Extract/Transform/Load 와 같은 분리 원칙을 따른다.

다음 글은 이 시리즈의 마무리 — 자바 백엔드 개발자 시각에서 ML 서비스 성능 분석 워크플로를 정리한다. 분석한 실제 사례 (이슈 17개 등록) 를 자바 백엔드 트러블슈팅과 비교한다.

## 참고

- [PaddleOCR — Architecture](https://github.com/PaddlePaddle/PaddleOCR)
- [Docling — Document parsing toolkit](https://github.com/docling-project/docling)
- [LayoutLM — Pre-training for Document AI](https://arxiv.org/abs/1912.13318)
- [Donut — OCR-free Document Understanding](https://arxiv.org/abs/2111.15664)
- [Awesome OCR — curated list](https://github.com/kba/awesome-ocr)
