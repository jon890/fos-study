# Docling — IBM Research 의 문서 파싱 toolkit 상세 정리

문서를 RAG·LLM 컨텍스트로 넣으려면 PDF·PPTX·HTML 같은 입력을 깨끗한 텍스트 (또는 markdown / JSON) 으로 변환해야 한다. 이걸 "쉽게" 해주는 라이브러리는 의외로 많지 않다. 표가 있는 PDF, 스캔본, 다단 레이아웃, 페이지 안의 그림과 캡션 같은 변형이 많기 때문.

**Docling** 은 IBM Research (Zurich) 가 2024 년에 오픈소스로 공개한 문서 파싱 toolkit 이다. Apache 2.0 라이선스. LangChain·LlamaIndex 와도 곧바로 연결된다.

내가 분석한 한 ML 문서 파싱 서비스가 Docling 위에 자체 OCR 플러그인을 얹어 운영하고 있어서 코드를 좀 깊게 봤다. 이 글은 Docling 의 구조·옵션·플러그인 시스템을 정리한 내용이다. 공식 문서 + 코드 + 실제 운영에서 본 함정을 합쳤다.

## 한 줄 정의와 위치

> Docling 은 다양한 문서 포맷 (PDF·DOCX·PPTX·HTML·이미지) 을 `DoclingDocument` 라는 단일 중간 표현으로 변환한 뒤 markdown / JSON / HTML / DocTags 로 export 하는 Python 라이브러리다.

비슷한 위치의 다른 도구들과 비교하면 이렇다.

| 도구 | 특화 | 출력 |
|---|---|---|
| **Docling** | 다양한 포맷 + 표·레이아웃 인식 | markdown, JSON, HTML, DocTags |
| `unstructured.io` | 폭넓은 포맷, 엔터프라이즈 SaaS 옵션 | element list |
| `pypdf` / `pdfplumber` | PDF 전용, 텍스트 레이어 위주 | text |
| `marker` | PDF → markdown, 학술 문서 강점 | markdown |
| LlamaParse | LlamaIndex 의 클라우드 서비스 | markdown, JSON |

OSS + 로컬 실행 + 다포맷 + 구조 인식의 조합이 Docling 의 자리. RAG 파이프라인에서 "전처리 단계의 표준" 자리를 노린다.

## 두 가지 아키텍처 패러다임

Docling 은 흥미롭게도 같은 프로젝트 안에 두 가지 다른 접근을 가지고 있다.

### 1) 전통적 multi-stage 파이프라인

PDF → Layout 감지 → OCR → 표 인식 → reading order → markdown.

각 단계가 별도 모델 또는 라이브러리로 구현된다.

- **Layout** — RT-DETR 아키텍처 + DocLayNet 데이터셋. 페이지에서 텍스트·표·그림·헤더 영역을 box 로 잡아낸다. 2025년 12월 도입된 **Heron layout model** 이 속도 개선판.
- **OCR** — 텍스트 박스의 픽셀을 글자로. EasyOCR (기본), Tesseract, RapidOCR, OcrMac (macOS Vision framework), 또는 사용자 정의 플러그인.
- **Table structure** — 표 영역을 셀 grid 로 복원. TableFormer 모델 사용.
- **Cell matching** — Layout 의 표 좌표와 텍스트 박스를 매칭해 셀 컨텐츠 채우기.
- **Reading order + markdown** — bbox 좌표 + 카테고리로 자연스러운 순서 결정, markdown export.

장점은 각 단계가 교체 가능하다는 점. OCR 만 클라우드 API 로 바꾸거나 layout 모델만 더 좋은 걸로 갈아끼울 수 있다.

단점은 **cascading error**. 앞 단계의 작은 실수가 뒤 단계로 누적된다. Layout 이 표 영역을 잘못 잡으면 cell matching 이 통째로 망가지는 식.

### 2) Granite-Docling VLM (2026년 1월 공개)

이 한계를 해결하려고 IBM 이 만든 **단일 추론** 모델. 258M parameter 의 Vision Language Model 로, 페이지 이미지를 받아 한 번에 구조화된 마크업을 토큰으로 생성한다.

- Layout · OCR · 표 · 순서를 모두 하나의 forward pass 에서 처리
- 출력은 DocTags 라는 마크업 (JSON 으로 변환 가능)
- Apache 2.0 + HuggingFace 에서 가중치 공개

장점은 cascading error 가 사라지고, 단일 모델이라 배포가 단순. 단점은 VLM 추론이 무겁고 (GPU 필요) 커스터마이징 여지가 적다는 점. 표·표 안의 표·각주 같은 복잡한 케이스에서 멀티-스테이지가 더 잘 잡는 경우도 여전히 있다.

내가 분석한 서비스는 다국어 OCR 분기 필요성·외부 OCR API 연동 같은 이유로 multi-stage 를 쓰고 있었다. RAG 용도로 정확도가 우선이고 GPU 충분하다면 Granite-Docling 단일 모델 쪽도 고려할 만한 옵션.

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

내가 분석한 운영 서비스는 `images_scale=3.0` (기본 1.0 대비 9배 픽셀) + `generate_picture_images=True` (실제 markdown 에서는 안 씀) 조합으로 페이지당 렌더링·인코딩 비용이 컸다. 이런 옵션은 한 번 잘못 박히면 운영 내내 누적 손해라 초기 튜닝이 중요하다.

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

자바로 비유하면 Spring Batch 의 `chunk` + 별도 `TaskExecutor` 조합. ETL 파이프라인에서 단계별 스레드 풀을 다르게 잡는 패턴과 같다.

다만 OCR 단계가 외부 API 호출이라면 이 파이프라이닝의 효과가 거의 사라진다. 내부 처리 단계만 빨라지고 외부 호출 지연이 그대로 노출되기 때문. 외부 OCR 을 쓰면 단계 안에서 영역 단위 병렬 호출 (ThreadPoolExecutor) 이 별도로 필요하다.

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

내가 분석한 서비스도 자체 클라우드 OCR API 를 Docling 플러그인으로 감싸 사용하고 있었다. 한국어/일본어 분기, 신뢰도 임계값, 영역 병렬 호출 같은 커스터마이징을 이 플러그인 단에서 처리. Docling 본체는 그대로 두고 OCR 만 교체하는 깔끔한 구조.

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

## 한계와 함정

운영하면서 몇 가지 함정을 봤다.

### 모델 다운로드 비용

처음 사용 시 HuggingFace 에서 layout/table/OCR 모델을 자동 다운로드한다. 합쳐서 수백 MB. Docker 빌드 시점에 미리 받아두지 않으면 첫 컨테이너 시작이 매우 느려진다.

```bash
# 빌드 시점에 미리 다운로드
docling-tools models download
```

자바 진영의 Maven 의존성 사전 다운로드 (`mvn dependency:go-offline`) 같은 패턴.

### Warmup 의 필요성

PyTorch / cuDNN 의 JIT 비용 때문에 첫 변환이 매우 느리다 (수십 초). 서비스 부팅 시 sample PDF 를 한 번 변환해 캐시를 채우는 게 거의 필수. Docling 자체가 warmup 헬퍼를 제공하지는 않으므로 직접 짜야 한다.

### 청크 처리

매우 큰 PDF (수백 페이지) 는 메모리 부담이 크다. 페이지를 N개씩 잘라 별도로 변환하고 합치는 chunking 패턴이 일반적. Docling 의 `page_range` 옵션을 활용해 페이지 범위로 잘라 처리할 수 있다.

다만 청크 경계에서 표·각주가 잘리면 후처리가 까다롭다. 표 영역이 페이지 경계를 넘는 케이스가 특히 어려움.

### 멀티 페이지 표

여러 페이지에 걸친 표는 Docling 이 페이지마다 독립 표로 인식한다. RAG 용도로 쓸 때 헤더가 두 번째 페이지에서 사라지는 등의 이슈가 생기므로 후처리에서 결합하는 로직이 필요할 수 있다.

### 옵션 조합의 explosion

`do_ocr`, `do_table`, `do_picture_classification`, OCR engine, layout model, table model 같은 옵션이 곱셈으로 늘어난다. 각 조합마다 converter 객체를 따로 만들면 메모리 압박. 옵션 조합 캐시 (`_converter_cache`) 가 필요하지만 캐시 키 누락 같은 버그가 생기기 쉽다. 분석한 코드에서도 이 함정이 잡혔다.

## 정리

> Docling 은 PDF·DOCX·PPTX 같은 다양한 입력을 `DoclingDocument` 라는 단일 중간 표현으로 정규화한 뒤 markdown / JSON 으로 export 하는 IBM 의 OSS 토킷. multi-stage 파이프라인 + Granite-Docling 단일 VLM 두 패러다임을 동시에 지원한다.

운영에서 만지는 핵심 다이얼은 `do_ocr`, `do_table_structure`, `images_scale`, `accelerator_options`. OCR 엔진은 entry-point 플러그인으로 교체 가능해서 클라우드 OCR API 도 자연스럽게 끼울 수 있다.

LangChain·LlamaIndex 와 곧바로 연결되어 RAG 파이프라인의 전처리 표준 자리를 노리는 라이브러리다. 한국 기업의 OCR/문서 처리 사용 사례에서도 이미 운영 환경에 들어가 있는 케이스가 늘고 있다.

## 참고

- [GitHub — docling-project/docling](https://github.com/docling-project/docling)
- [Docling 공식 문서 — Pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)
- [Docling Technical Report (arXiv)](https://arxiv.org/html/2408.09869v5)
- [IBM Research — Docling announcement](https://research.ibm.com/blog/docling-generative-AI)
- [IBM — Granite-Docling end-to-end document conversion](https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion)
- [Behind the scenes of Docling PDF Parsing (Medium)](https://alain-airom.medium.com/behind-the-scenes-of-docling-pdf-parsing-20f557b289da)
- [Docling — Force full page OCR example](https://docling-project.github.io/docling/examples/full_page_ocr/)
- [Docling — Custom conversion example](https://docling-project.github.io/docling/examples/custom_convert/)
