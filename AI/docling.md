---
series: "AI 서빙 인프라: GPU부터 문서 파싱까지"
seriesOrder: 8
thumbnail: ./images/docling-thumbnail.jpg
---

# Docling — IBM Research 의 문서 파싱 toolkit 상세 정리

문서를 RAG·LLM 컨텍스트로 넣으려면 PDF·PPTX·HTML 같은 입력을 깨끗한 텍스트 (또는 markdown / JSON) 으로 변환해야 한다. 이걸 "쉽게" 해주는 라이브러리는 의외로 많지 않다. 표가 있는 PDF, 스캔본, 다단 레이아웃, 페이지 안의 그림과 캡션 같은 변형이 많기 때문.

**Docling** 은 IBM Research (Zurich) 가 2024 년에 오픈소스로 공개한 문서 파싱 toolkit 이다.
MIT 라이선스이고, 2025년 4월 IBM 이 **LF AI & Data Foundation** 에 기증해 지금은 재단이 호스팅한다.
LangChain·LlamaIndex 와도 곧바로 연결된다.

우리 팀은 Docling 위에 자체 OCR 플러그인을 얹은 문서 파싱 서비스를 GPU 클러스터에서 운영한다.
이 글은 Docling 의 구조·옵션·플러그인 시스템을 정리하고, 여기에 두 가지를 덧붙인 내용이다.

- 최근 업스트림이 어느 방향으로 움직이는지 (2.115 → 2.118, DocLang 표준화, 2-stage VLM)
- 우리가 실제로 어떤 설정으로 쓰고 있고 어떤 함정을 밟았는지

공식 문서와 코드에 운영에서 직접 본 것을 합쳤다.

## 한 줄 정의와 위치

> Docling 은 다양한 문서 포맷 (PDF·DOCX·PPTX·HTML·이미지) 을 `DoclingDocument` 라는 단일 중간 표현으로 변환한 뒤 markdown / JSON / HTML / DocTags 로 export 하는 Python 라이브러리다.

비슷한 위치의 다른 도구들과 비교하면 이렇다.

| 도구 | 특화 | 출력 |
|---|---|---|
| **Docling** | 다양한 포맷, 표·레이아웃 인식 | markdown, JSON, HTML, DocTags |
| `unstructured.io` | 폭넓은 포맷, 엔터프라이즈 SaaS 옵션 | element list |
| `pypdf` / `pdfplumber` | PDF 전용, 텍스트 레이어 위주 | text |
| `marker` | PDF → markdown, 학술 문서 강점 | markdown |
| LlamaParse | LlamaIndex 의 클라우드 서비스 | markdown, JSON |

오픈소스, 로컬 실행, 다포맷, 구조 인식을 한꺼번에 만족하는 것이 Docling 의 자리다.
RAG 파이프라인에서 "전처리 단계의 표준" 자리를 노린다.

## 두 가지 아키텍처 패러다임

Docling 은 흥미롭게도 같은 프로젝트 안에 두 가지 다른 접근을 가지고 있다.

### 1) 전통적 multi-stage 파이프라인

PDF → Layout 감지 → OCR → 표 인식 → reading order → markdown.

각 단계가 별도 모델 또는 라이브러리로 구현된다.

- **Layout** — RT-DETR 아키텍처를 DocLayNet 데이터셋으로 학습한 모델. 페이지에서 텍스트·표·그림·헤더 영역을 box 로 잡아낸다. 2025년 12월 도입된 **Heron layout model** 이 속도 개선판.
- **OCR** — 텍스트 박스의 픽셀을 글자로. EasyOCR (기본), Tesseract, RapidOCR, OcrMac (macOS Vision framework), 또는 사용자 정의 플러그인.
- **Table structure** — 표 영역을 셀 grid 로 복원. TableFormer 모델 사용.
- **Cell matching** — Layout 의 표 좌표와 텍스트 박스를 매칭해 셀 컨텐츠 채우기.
- **Reading order 와 markdown** — bbox 좌표와 카테고리로 자연스러운 순서를 정하고 markdown 으로 export 한다.

장점은 각 단계가 교체 가능하다는 점. OCR 만 클라우드 API 로 바꾸거나 layout 모델만 더 좋은 걸로 갈아끼울 수 있다.

단점은 **cascading error**. 앞 단계의 작은 실수가 뒤 단계로 누적된다. Layout 이 표 영역을 잘못 잡으면 cell matching 이 통째로 망가지는 식.

### 2) Granite-Docling VLM (2026년 1월 공개)

이 한계를 해결하려고 IBM 이 만든 **단일 추론** 모델. 258M parameter 의 Vision Language Model 로, 페이지 이미지를 받아 한 번에 구조화된 마크업을 토큰으로 생성한다.

- Layout · OCR · 표 · 순서를 모두 하나의 forward pass 에서 처리
- 출력은 DocTags 라는 마크업 (JSON 으로 변환 가능)
- 가중치는 Apache 2.0 으로 HuggingFace 에 공개

장점은 cascading error 가 사라지고, 단일 모델이라 배포가 단순하다는 것.
단점은 VLM 추론이 무겁고 (GPU 필요) 커스터마이징 여지가 적다는 점.
표 안의 표나 각주 같은 복잡한 케이스에서 멀티-스테이지가 더 잘 잡는 경우도 여전히 있다.

### 3) 두 패러다임이 다시 만나는 지점 — 2-stage 변형

흥미로운 건 이 두 갈래가 갈라지기만 한 게 아니라 다시 합쳐지고 있다는 점이다.

`granite-docling-2stage-258m` 은 단일 VLM 앞에 **layout 감지 단계를 되돌려 놓은** 변형이다.

1. RT-DETR 계열 detector (`docling-layout-heron`) 가 페이지의 layout 객체를 먼저 잡는다
2. 그 결과를 동적 prompt 로 만들어 Granite-Docling 에 먹인다

목적은 학습 분포를 벗어난 (out-of-distribution) 문서에서의 견고함이다.
공개된 평가값 기준으로 layout mAP 는 0.27 에서 0.31 로, OCR edit distance 는 0.45 에서 0.27 로 개선됐다.

정리하면 이렇다.
순수 단일 VLM 은 cascading error 를 없앴지만 처음 보는 레이아웃에서 흔들렸고,
그래서 layout 단계만 앞에 다시 붙여 "힌트를 주는" 형태로 절충한 것이다.
멀티-스테이지의 단계 교체 가능성과 VLM 의 통합 추론 중 어느 한쪽이 이겼다기보다,
**layout 은 별도 모델, 나머지는 VLM** 이라는 구도로 수렴하는 중으로 보인다.

우리 서비스는 다국어 OCR 분기와 외부 OCR API 연동 때문에 multi-stage 를 쓴다.
한국어는 사내 클라우드 OCR API, 일본어는 로컬 PaddleOCR 로 갈라야 하는데 단일 VLM 에는 그 갈래를 끼울 자리가 없다.
반대로 언어 분기가 필요 없고 GPU 여유가 있다면 VLM 경로가 더 단순한 선택이다.

## DoclingDocument — 단일 중간 표현

Docling 의 핵심 추상화. 모든 변환 경로가 결과적으로 `DoclingDocument` 를 만들고, 거기서 다양한 포맷으로 export 한다.

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("document.pdf")
doc = result.document          # DoclingDocument

# Export
md = doc.export_to_markdown()
data = doc.export_to_dict()    # JSON-serializable
html = doc.export_to_html()
tags = doc.export_to_doctags() # 학습용 마크업
```

`DoclingDocument` 안에는 다음이 들어 있다.

- **Pages** — 페이지별 메타데이터 (크기, 회전, 텍스트 레이어 여부)
- **Body** — 트리 구조의 콘텐츠 (제목·문단·리스트·표·그림)
- **Tables** — 별도 컬렉션으로 표 객체 (행·열·셀)
- **Pictures** — 그림 객체 (좌표·메타데이터·선택적 base64 PNG)
- **Provenance** — 각 요소가 어느 페이지 어느 좌표에서 왔는지 추적

자바로 비유하면 IR (Intermediate Representation) 또는 AST. 입력 포맷이 무엇이든 같은 트리로 정규화되고, export 단계가 포맷별 visitor 패턴.

## Pipeline 옵션 — 실전에서 만지는 부분

`DocumentConverter` 에 `PdfFormatOption(pipeline_options=...)` 으로 옵션을 주입한다. 자주 만지는 항목:

```python
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat

pipeline_opts = PdfPipelineOptions(
    do_ocr=True,
    do_table_structure=True,
    table_structure_options={"do_cell_matching": True},
    images_scale=2.0,
    generate_picture_images=False,
    accelerator_options={"num_threads": 4, "device": "auto"},
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts),
    }
)
```

주요 옵션과 성능 영향:

| 옵션 | 의미 | 성능 영향 |
|---|---|---|
| `do_ocr` | OCR 활성화 | OCR 이 대체로 가장 비싼 단계 |
| `do_table_structure` | 표 구조 복원 | 표 많은 PDF 에서 중요 |
| `do_cell_matching` | 표 영역과 텍스트 매칭 | 항상 활성 시 페이지당 추가 비용 |
| `images_scale` | 페이지 렌더링 해상도 배율 (기본 1.0) | 픽셀 제곱으로 비용 증가. 3.0 이면 9배 |
| `generate_picture_images` | 그림 PNG 렌더링 & base64 임베딩 | 출력에 픽셀이 필요 없으면 False 권장 |
| `accelerator_options.num_threads` | CPU 스레드 수 | 워커 수 × num_threads 가 CPU 코어 초과하면 컨텍스트 스위치 손해 |
| `accelerator_options.device` | `cpu`/`cuda`/`mps`/`auto` | GPU 가용 시 자동 선택 |

우리 서비스도 여기서 한 번 손해를 봤다.
`images_scale=3.0` (기본 1.0 대비 9배 픽셀) 과 `generate_picture_images=True` 를 함께 켜 두고 있었는데,
정작 최종 markdown 에서는 그 base64 픽셀을 쓰지 않았다.
페이지마다 렌더링과 인코딩 비용만 내고 결과는 버린 셈이다.
지금은 `generate_picture_images=False` 로 내렸고 `images_scale=3.0` 은 OCR 인식률 때문에 유지한다.

이런 옵션은 한 번 잘못 박히면 요청 수에 비례해 손해가 누적된다.
"켜 둔 옵션의 산출물을 실제로 소비하고 있는가" 를 초기에 한 번 확인하는 게 싸게 먹힌다.

## ThreadedPdfPipelineOptions — 단계 간 파이프라이닝

PDF 처리는 페이지 단위로 layout → OCR → table → assemble 같은 단계가 직렬로 흐른다. 페이지 N개를 순차 처리하면 한 페이지가 모두 끝나야 다음 페이지가 시작.

`ThreadedPdfPipelineOptions` 는 단계들을 별도 thread 로 분리해 **다른 페이지가 다른 단계에 있어도 동시에 처리**되게 한다. CPU/GPU 단계가 섞여 있을 때 GPU 가 idle 한 시간이 줄어든다.

```python
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions

opts = ThreadedPdfPipelineOptions(
    ocr_batch_size=8,
    layout_batch_size=4,
    batch_concurrency_settings={...},
)
```

자바로 비유하면 Spring Batch 의 `chunk` 에 단계별 `TaskExecutor` 를 따로 붙인 구조다.
ETL 파이프라인에서 단계마다 스레드 풀을 다르게 잡는 패턴과 같다.

### 함정 — 옵션만 넣으면 켜지지 않는다

여기서 우리가 오래 못 알아챈 버그가 하나 있었다.
`ThreadedPdfPipelineOptions` 를 만들어 넘기는 것만으로는 threaded pipeline 이 켜지지 않는다.
파이프라인 **클래스**를 함께 지정해야 한다.

```python
# 잘못된 코드 — 실제로는 기본 StandardPdfPipeline 이 돈다
PdfFormatOption(ThreadedPdfPipelineOptions=ThreadedStandardPdfPipeline, ...)

# 올바른 코드
PdfFormatOption(
    pipeline_cls=ThreadedStandardPdfPipeline,
    pipeline_options=pipeline_options,
    backend=PyPdfiumDocumentBackend,
)
```

`ThreadedPdfPipelineOptions=` 는 `PdfFormatOption` 에 없는 필드명이다.
그런데 pydantic 이 이걸 extra 로 조용히 버리고 예외를 내지 않는다.
결과적으로 코드에는 threaded 라고 적혀 있고 실제로는 기본 파이프라인이 도는 상태가 유지됐다.

**교훈은 하나다. 옵션을 넣었다고 믿지 말고 생성된 객체를 확인한다.**

```python
converter = get_converter()
opt = converter.format_to_options[InputFormat.PDF]
print(opt.pipeline_cls)   # ThreadedStandardPdfPipeline 인지 눈으로 확인
```

자바에서 Spring 설정을 바꿔 놓고 `@Bean` 이 실제로 교체됐는지 런타임에서 확인하는 것과 같다.
설정 객체가 관대할수록 (extra 허용, 무효 kwarg 무시) 이 확인이 필요해진다.

한 가지 더 — docling 2.96 부터 threaded 구현이 `StandardPdfPipeline` 본체에 흡수됐다.
`ThreadedStandardPdfPipeline` 은 하위 호환 alias 로 남아 있다.
그래서 최신 버전에서는 이 함정 자체가 덜 위험해졌지만, 명시 선언은 의도를 코드에 남기는 값이 있어 유지하고 있다.

### 외부 OCR 을 쓰면 효과가 줄어든다

OCR 단계가 외부 API 호출이라면 이 파이프라이닝의 효과가 거의 사라진다. 내부 처리 단계만 빨라지고 외부 호출 지연이 그대로 노출되기 때문. 외부 OCR 을 쓰면 단계 안에서 영역 단위 병렬 호출 (ThreadPoolExecutor) 이 별도로 필요하다.

## OCR 엔진 플러그인 시스템

Docling 은 OCR 엔진을 plugin 인터페이스로 추상화한다. 기본 엔진들 (`EasyOcrOptions`, `TesseractOcrOptions`, `RapidOcrOptions`, `OcrMacOptions`) 외에 사용자 정의 엔진을 패키지로 등록할 수 있다.

플러그인 구조:

```python
# my_ocr_plugin/options.py
from docling.datamodel.pipeline_options import OcrOptions
from pydantic import BaseModel

class MyOcrOptions(OcrOptions):
    kind: ClassVar[str] = "my_ocr"
    api_endpoint: str = "https://ocr.example.com/v1"
    api_key: str = ""
    confidence_threshold: float = 0.5

# my_ocr_plugin/model.py
from docling.models.base_ocr_model import BaseOcrModel

class MyOcrModel(BaseOcrModel):
    def __init__(self, options: MyOcrOptions, ...):
        super().__init__(...)
        self.options = options

    def __call__(self, page_image, ocr_rects):
        # 각 박스에 대해 OCR 수행, 결과 cells 반환
        ...

# my_ocr_plugin/plugin.py
def ocr_engines():
    return {
        "ocr_engines": [
            {"kind": "my_ocr", "options_cls": MyOcrOptions, "model_cls": MyOcrModel},
        ]
    }

# pyproject.toml
[project.entry-points."docling"]
ocr_engines = "my_ocr_plugin.plugin:ocr_engines"
```

`pip install` 만 하면 Docling 이 entry-point 로 발견해 사용 가능하다. 자바 SPI (Service Provider Interface) 와 같은 패턴.

한 가지 주의할 점은 `allow_external_plugins=True` 를 파이프라인 옵션에 켜 줘야 외부 플러그인이 실제로 로드된다는 것이다.
설치만 해 놓고 이 플래그를 안 켜면 기본 엔진으로 조용히 넘어간다.

### 우리가 플러그인을 두 개 쓰는 이유

우리는 언어별로 OCR 엔진을 갈라야 해서 플러그인을 둘 만들었다.

| 언어 | 엔진 | 형태 | 이유 |
| --- | --- | --- | --- |
| 한국어 | 사내 클라우드 OCR API | 외부 HTTP 호출 | 한국어 인식 정확도가 로컬 모델보다 확실히 높다 |
| 일본어 | PaddleOCR | 로컬 GPU 모델 | 일본어에서는 반대로 로컬 모델이 낫고, 외부 API 비용도 없다 |

Docling 본체는 한 줄도 고치지 않았다.
fork 를 뜨면 업스트림 패치를 계속 따라가야 하고 보안 패치를 놓칠 위험이 생기는데, entry-point 방식은 그 비용이 없다.

### 함정 — 플러그인이 base 를 덮으면 업스트림 개선이 안 들어온다

`BaseOcrModel` 에는 `get_ocr_rects` 라는 메서드가 있다.
페이지에서 "OCR 을 돌릴 영역" 을 계산하는 함수인데, 우리 한국어 플러그인은 이걸 자체 구현으로 덮어써 놓았다.

그러다 업스트림이 이 함수 안의 dilation 연산을 scipy 에서 OpenCV 로 바꾸는 개선을 넣었다.
A4 한 장 기준으로 **95ms 에서 0.25ms** 로 줄어드는 변화였다 (출력은 비트 단위로 동일한 것을 확인했다).

그런데 이 개선이 일본어 경로에만 들어왔다.
한국어 경로는 `get_ocr_rects` 를 자체 구현으로 덮고 있어서 업스트림이 고친 함수 자체를 타지 않기 때문이다.

**base class 메서드를 override 하는 순간, 그 메서드에 대한 업스트림 개선은 우리 것이 아니게 된다.**
자바에서 라이브러리 클래스를 상속해 메서드를 덮어 놓고 라이브러리 버전을 올리는 것과 같은 상황이다.
override 한 지점은 목록으로 관리하고, 버전을 올릴 때 그 지점의 업스트림 diff 를 따로 봐야 한다.

## PDF Backend

PDF 자체를 파싱해 페이지 이미지·텍스트 레이어를 뽑는 단계. Docling 은 backend 도 교체 가능하다.

- **PyPdfiumDocumentBackend** — pypdfium2 기반 (Chromium 의 PDFium). 기본값에 가까움.
- **DoclingParseDocumentBackend** — IBM 자체 파서, 더 정확하지만 느릴 수 있음.
- **PdfPlumberBackend** — pdfplumber 기반.

대부분 케이스에 pypdfium2 가 적당. 텍스트 레이어가 깨진 PDF·복잡한 폼은 다른 backend 를 시도해볼 가치가 있다.

## LangChain / LlamaIndex 통합

Docling 은 RAG 파이프라인의 전처리 자리를 노리고 있어서 LangChain·LlamaIndex 와 곧바로 연결된다.

```python
# LangChain
from langchain_docling import DoclingLoader

loader = DoclingLoader(file_path="doc.pdf")
docs = loader.load()                    # LangChain Document list

# LlamaIndex
from llama_index.readers.docling import DoclingReader

reader = DoclingReader()
documents = reader.load_data(file_path="doc.pdf")
```

`DoclingDocument` → LangChain `Document` 자동 변환. markdown 출력을 그대로 청크 분할기로 넘기는 흐름.

## 우리 운영 설정 — 전체 그림

지금까지의 조각을 우리 서비스가 실제로 어떻게 조립해 쓰는지로 모아 본다.
FastAPI 앞단에 GPU 워커 풀을 두고, 워커 프로세스마다 Docling converter 를 만들어 쓰는 구조다.

```python
accelerator_options = AcceleratorOptions(
    num_threads=min(4, os.cpu_count()),
    device=AcceleratorDevice.AUTO,
)

pipeline_options = ThreadedPdfPipelineOptions()
pipeline_options.accelerator_options = accelerator_options
pipeline_options.do_table_structure = do_table
pipeline_options.allow_external_plugins = True      # 외부 OCR 플러그인 로드에 필수
pipeline_options.do_ocr = do_ocr

if ja_doc:
    pipeline_options.ocr_options = PaddleOcrOptions(ocr_engine=..., lang=["en", "ja"])
else:
    pipeline_options.ocr_options = CloudOcrOptions(connect_timeout=..., read_timeout=...)   # 자체 플러그인

pipeline_options.ocr_options.confidence_threshold = 0.0
pipeline_options.table_structure_options.do_cell_matching = True
pipeline_options.images_scale = 3.0
pipeline_options.generate_picture_images = False

converter = DocumentConverter(format_options={
    InputFormat.PDF: PdfFormatOption(
        pipeline_cls=ThreadedStandardPdfPipeline,
        pipeline_options=pipeline_options,
        backend=PyPdfiumDocumentBackend,
    )
})
```

각 선택의 이유는 이렇다.

| 설정 | 값 | 이유 |
| --- | --- | --- |
| `num_threads` | `min(4, cpu_count())` | 워커 여러 개가 한 호스트에 뜨므로 워커당 스레드를 묶어 둔다.<br>안 묶으면 워커 수 × 스레드 수가 코어 수를 넘어 컨텍스트 스위치 손해가 난다 |
| `device` | `AUTO` | GPU 가 있으면 CUDA, 로컬 Mac 개발에서는 MPS 또는 CPU 로 알아서 내려간다 |
| `confidence_threshold` | `0.0` | OCR 결과를 임계값으로 버리지 않고 전부 받는다.<br>버릴지 말지는 우리가 뒷단에서 정한다 |
| `images_scale` | `3.0` | OCR 인식률 때문에 유지한다. 픽셀은 제곱으로 늘어 기본값 대비 9배다 |
| `generate_picture_images` | `False` | 최종 markdown 이 base64 픽셀을 안 쓴다. 켜 두면 비용만 낸다 |
| `backend` | `PyPdfiumDocumentBackend` | 명시 선언. docling 이 자동으로 골라 주던 것을 의도가 드러나게 고정했다 |

### converter 캐시 — 옵션 조합마다 하나

`do_ocr`, `do_table`, `ja_doc` 세 스위치의 조합마다 converter 가 달라진다.
매 요청마다 새로 만들면 모델 로딩 비용을 반복해서 낸다.
그래서 조합을 키로 하는 캐시를 워커 프로세스 안에 둔다.

```python
cache_key = f"ocr_{do_ocr}_table_{do_table}_ja_{ja_doc}"
if cache_key in _converter_cache:
    return _converter_cache[cache_key]
```

주의할 점은 캐시가 프로세스 수명만큼 메모리를 잡는다는 것이다.
우리는 워커에 `max_tasks_per_child` 를 걸어 일정 요청마다 프로세스를 재시작하는데, 그때 캐시도 함께 해제된다.
캐시 해제를 따로 구현하지 않고 프로세스 수명에 얹은 셈이다.

### 부팅 시 warmup

워커가 뜨면 대표 조합 (한국어 OCR, 일본어 OCR, OCR 없음) 마다 converter 를 만들어 sample 문서를 한 번 변환한다.
PyTorch 와 cuDNN 의 JIT 비용 때문에 첫 변환이 수십 초 걸리기 때문이다.
이 warmup 이 없으면 그 비용을 첫 실사용자가 낸다.

Docling 은 warmup 헬퍼를 제공하지 않으므로 직접 짜야 한다.
모델 파일 자체도 마찬가지다 — 아래 "모델 다운로드 비용" 을 함께 본다.

## 최근 업스트림의 방향 — 변환 도구에서 문서 표준으로

이 글을 처음 쓴 뒤로도 릴리스가 계속 나왔다.
우리는 2.115 에 고정해 두었고, 그사이 업스트림은 2.118 까지 왔다.
방향성을 세 갈래로 정리할 수 있다.

### 1) DocLang — 출력 포맷의 표준화

2026년 6월, LF AI & Data 재단이 **DocLang Specification Working Group** 을 만들었다.
IBM·NVIDIA·Red Hat 이 창립 멤버이고 ABBYY·HumanSignal 이 참여한다.

목표는 "AI 가 읽기 위한 문서 포맷" 의 개방 표준이다.
PDF 는 사람이 보라고 만든 포맷이라 기계가 구조를 복원하려면 지금 우리가 하는 짓 (layout 감지, OCR, 표 복원) 을 매번 해야 한다.
그 복원 결과를 표현하고 시스템 사이에 주고받는 형식을 표준으로 못박겠다는 것이다.

기반은 Docling 이 이미 쓰고 있는 것들이다.

- `DoclingDocument` — 구조를 담는 내부 표현
- `DocTags` — 구조를 보존하는 마크업
- `OTSL` — 표를 표현하는 형식

Docling 이 변환(ingestion) 을 맡고 DocLang 이 교환 형식을 맡는 분업 구도다.
우리 입장에서는 당장 바뀌는 게 없지만, 파싱 결과를 다른 저장소에 넘기는 계약이 있는 팀이라면 지켜볼 가치가 있다.

### 2) 라이브러리에서 서비스로

최근 릴리스 노트를 보면 SDK 자체보다 **서비스 계층** 쪽 변화가 눈에 띈다.

- 서비스 API 에 PDF 제목 계층 추론 노출 (2.118)
- 서비스 데이터모델에 청킹 옵션과 대상 추가 (2.117)
- 파이프라인 stage 종료 타임아웃을 설정 가능하게 (2.116)
- DOCX 변환의 LibreOffice 호출에 타임아웃과 격리 프로파일 (2.116)
- Google Cloud Storage 사용 가이드 추가 (2.116)
- Red Hat 과 함께 만든 OpenShift Operator

"라이브러리를 import 해서 쓰는 것" 에서 "문서 변환을 서비스로 띄워 운영하는 것" 으로 무게가 옮겨 가고 있다.
운영 안정성 수정이 꾸준히 들어오는 것도 같은 맥락이다.
우리가 2.115 로 올리며 받은 것도 이런 종류였다.

- 모델 다운로드 요청 타임아웃 (워커 초기화가 무한정 기다리던 경로를 막는다)
- 파이프라인 초기화 실패 시 입력 백엔드 해제 (실패가 메모리를 붙잡던 누수를 막는다)
- 타입 기반 에러 분류와 예외 체이닝 (에러 사유를 문자열 매칭으로 가르던 코드를 제거할 근거가 된다)

마지막 항목은 특히 반갑다.
예외를 문자열로 분류하는 코드는 업스트림 메시지가 바뀌는 순간 조용히 오분류를 시작하기 때문이다.

### 3) OCR 단계 자체의 재정비

2.116 에 **layout 기반 OCR 파이프라인** 과 OCR 모드 설정이 들어왔고,
2.117 에서 OCR 렌더링 배율이 하드코딩에서 설정값으로 바뀌었다.
2.118 은 RapidOcrModel 을 리팩터링해 PP-OCR 의 모든 언어를 지원하게 했다.

우리처럼 OCR 을 플러그인으로 갈아끼운 쪽에는 양날이다.
공통 계층이 좋아지는 건 이득이지만, 앞서 적은 `get_ocr_rects` 사례처럼 **덮어쓴 지점은 그 개선을 받지 못한다.**
OCR 계층 리팩터링이 계속되면 우리 플러그인과 base 사이의 간격도 함께 벌어진다.

## 한계와 함정

운영하면서 몇 가지 함정을 봤다.

### 모델 다운로드 비용

처음 사용 시 HuggingFace 에서 layout/table/OCR 모델을 자동 다운로드한다. 합쳐서 수백 MB. Docker 빌드 시점에 미리 받아두지 않으면 첫 컨테이너 시작이 매우 느려진다.

```bash
# 빌드 시점에 미리 다운로드
docling-tools models download
```

자바 진영의 Maven 의존성 사전 다운로드 (`mvn dependency:go-offline`) 같은 패턴.

### 청크 처리

매우 큰 PDF (수백 페이지) 는 메모리 부담이 크다. 페이지를 N개씩 잘라 별도로 변환하고 합치는 chunking 패턴이 일반적. Docling 의 `page_range` 옵션을 활용해 페이지 범위로 잘라 처리할 수 있다.

다만 청크 경계에서 표·각주가 잘리면 후처리가 까다롭다. 표 영역이 페이지 경계를 넘는 케이스가 특히 어려움.

### 멀티 페이지 표

여러 페이지에 걸친 표는 Docling 이 페이지마다 독립 표로 인식한다. RAG 용도로 쓸 때 헤더가 두 번째 페이지에서 사라지는 등의 이슈가 생기므로 후처리에서 결합하는 로직이 필요할 수 있다.

### 옵션 조합의 explosion

`do_ocr`, `do_table`, `do_picture_classification`, OCR engine, layout model, table model 같은 옵션이 곱셈으로 늘어난다.
각 조합마다 converter 객체를 따로 만들면 메모리 압박이 온다.
조합별 캐시가 필요하지만, 캐시 키에 스위치 하나를 빠뜨리면 다른 설정의 converter 를 재사용하는 버그가 조용히 생긴다.

### 프로파일링 스위치가 두 개다

단계별 소요 시간을 보려고 `result.timings` 를 읽었는데 계속 비어 있었다.
원인은 스위치가 두 겹이라는 것이었다.

- 우리 쪽 환경변수 — timings 를 **로그로 출력할지**
- Docling 쪽 `settings.debug.profile_pipeline_timings` — timings 를 **수집할지**

Docling 의 `TimeRecorder` 는 뒤쪽 플래그가 켜져 있을 때만 `result.timings` 를 채운다.
그런데 이 값의 기본값이 False 라 수집 자체가 0 이었고, 우리는 "출력" 스위치만 켜 놓고 "프로파일링 결과 없음" 경고만 보고 있었다.

여기에 함정이 하나 더 겹쳤다.
워커가 spawn 방식 프로세스라 부모 프로세스에서 플래그를 켜도 자식에 전파되지 않는다.
워커 초기화 코드 안에서 켜야 한다.

버전 업그레이드 전에는 Docling 쪽 수집 기본값이 켜져 있어 우리가 잇지 않아도 값이 나왔다.
업그레이드 후 기본값이 바뀌면서 "우리 코드가 망가진 것처럼" 보였는데 실제로는 라이브러리 기본값 변경이었다.

### 버전 업그레이드는 출력이 바뀌는 변경이다

Docling 업그레이드는 의존성 버전 하나 올리는 일이 아니다.
layout 모델과 표 복원 모델이 바뀌면 **같은 입력에서 다른 markdown 이 나온다.**
RAG 라면 청크 경계가 달라지고 색인 결과가 달라진다.

우리는 이걸 두 가지로 관리한다.

- **4개 패키지를 동시에 핀** — `docling`, `docling-core`, `docling-parse`, `docling-ibm-models` 는 서로 맞물려 있어 하나만 올리면 조합이 어긋난다
- **출력 diff 를 세 갈래로 분류** — 정합 (원래 이래야 했던 것), 개선, 회귀. 회귀 0건일 때만 통과시킨다

여기에 정답지 (golden) 기반 채점을 붙였다.
대표 문서에 사람이 검수한 정답 markdown 을 두고 파싱 결과와 비교해 절대 점수를 낸다.
정답지를 만들 수 없는 문서 (수백 쪽 분량, 텍스트 레이어 없는 스캔본) 는 정답지 없이 구조 지표만 잰다.
제목 표기 비율, 표 구문 온전성, 이미지 태그 짝, 한글 띄어쓰기 밀도 같은 것들인데,
원문과 대조하지 않고 출력물만 보고 판정할 수 있는 항목들이다.

여기서 배운 게 하나 있다.
**축 이름이 주장하는 것과 계산이 실제로 재는 것이 어긋나기 쉽다.**
예를 들어 이미지 태그 짝 비율을 "열림 태그 수" 로 나누면 닫힘 태그가 초과로 있어도 만점이 나온다.
잴 수 없는 항목을 0 으로 채우지 않고 "미측정" 으로 남기는 것도 같은 이유다.
0 은 "나쁨" 으로 읽히지만 미측정은 판단을 유보하기 때문이다.

### 표 복원 모델 업그레이드는 따로 판단한다

`docling-ibm-models` 의 TableFormer v2 는 우리 환경에서 회귀를 냈다.

- 병합된 셀이 잘려 나감
- 컬럼 수 오인식
- 셀 값 소실

셋 다 업스트림에 이슈로 올라와 있고 아직 닫히지 않았다.
그래서 다른 패키지를 올릴 때도 표 모델은 v1 에 붙들어 두고 있다.

교훈은 **"라이브러리 업그레이드" 를 한 덩어리로 다루지 않는 것**이다.
같은 업그레이드 안에서도 출력을 바꾸는 축 (layout 모델, 표 모델) 과 그렇지 않은 축 (버그 수정, 성능 개선) 은 위험도가 다르다.
우리는 표 모델 축만 따로 떼어 보류하고 나머지를 받았다.

## 정리

> Docling 은 PDF·DOCX·PPTX 같은 다양한 입력을 `DoclingDocument` 라는 단일 중간 표현으로 정규화한 뒤
> markdown 또는 JSON 으로 export 하는 오픈소스 toolkit 이다.
> IBM Research 가 만들어 LF AI & Data 재단에 기증했고, multi-stage 파이프라인과 Granite-Docling VLM 두 패러다임을 함께 지원한다.

운영에서 만지는 핵심 다이얼은 `do_ocr`, `do_table_structure`, `images_scale`, `accelerator_options` 네 개다.
OCR 엔진은 entry-point 플러그인으로 교체 가능해서 클라우드 OCR API 도 자연스럽게 끼울 수 있다.

직접 운영하며 배운 것을 세 줄로 줄이면 이렇다.

- **설정은 넣었다고 켜진 게 아니다** — 무효 kwarg 가 조용히 버려지므로 생성된 객체를 확인한다
- **override 한 지점은 업스트림 개선의 사각지대다** — base 메서드를 덮으면 그 함수의 개선은 우리 것이 아니다
- **버전 업그레이드는 출력이 바뀌는 변경이다** — 회귀를 가릴 채점 수단을 먼저 갖추고 올린다

업스트림은 변환 도구를 넘어 문서 표준 (DocLang) 과 서비스 운영 쪽으로 무게를 옮기는 중이다.
RAG 파이프라인의 전처리 자리를 노리던 라이브러리가 문서 데이터 계층 전체를 노리는 방향으로 커지고 있다.

## 참고

- [GitHub — docling-project/docling](https://github.com/docling-project/docling)
- [Docling CHANGELOG](https://github.com/docling-project/docling/blob/main/CHANGELOG.md)
- [Docling 공식 문서 — Pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)
- [Docling Technical Report (arXiv)](https://arxiv.org/html/2408.09869v5)
- [IBM Research — Docling announcement](https://research.ibm.com/blog/docling-generative-AI)
- [IBM — Granite-Docling end-to-end document conversion](https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion)
- [HuggingFace — granite-docling-2stage-258m](https://huggingface.co/docling-project/granite-docling-2stage-258m)
- [LF AI & Data — IBM 의 Docling·BeeAI·Data Prep Kit 기증 (2025-04)](https://lfaidata.foundation/blog/2025/04/29/ai-workflows-get-new-open-source-tools-to-advance-document-intelligence-data-quality-and-decentralized-ai-with-ibms-contribution-of-3-projects-to-linux-foundation-ai-and-data/)
- [Linux Foundation — DocLang Specification Working Group 출범 (2026-06)](https://www.linuxfoundation.org/press/lf-ai-data-foundation-launches-doclang-specification-working-group-to-advance-an-open-standard-for-ai-native-documents)
- [Behind the scenes of Docling PDF Parsing (Medium)](https://alain-airom.medium.com/behind-the-scenes-of-docling-pdf-parsing-20f557b289da)
- [Docling — Force full page OCR example](https://docling-project.github.io/docling/examples/full_page_ocr/)
- [Docling — Custom conversion example](https://docling-project.github.io/docling/examples/custom_convert/)
