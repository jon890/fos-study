# NHN 서비스개발센터 AI서비스개발팀

- 모집직무 : AI 서비스 개발
- 주요 업무 :
  - ML 모델을 사용하여 AI 서비스 개발 및 유지보수
  - AI 서비스 인프라 구축 및 최적화
- 자격요건 :
  - Java & Spring Framework (Spring Boot) Backend 개발/운영 경험 5년 이상이신 분
  - RDBMS를 이용한 개발/운영 경험이 있으신분 (MSSQL, MySQL 등)
  - HTTP(RESTful) API에 대한 설계 및 개발역량 보유하신 분
  - 서버 Framework에 대한 이해가 있고 개발 경험이 있으신 분
- 우대사항 :
  - ElasticSearch 구성/운영 경험이 있으신 분
  - Docker, k8s 구성/운영 경험이 있으신 분
  - CI/CD 자동화 파이프라인 구축 경험이 있으신 분
  - FrontEnd 개발 가능하신분 (React, Vue)
  - ML 모델 서빙 환경 구축 경험 있으신 분

## 팀에선 어떤일을 하고 있는가?

- NHN Cloud를 통해 서비스하는 AI제품을 개발하는 것으로 보임
  - Face Recognition
    - https://www.nhncloud.com/kr/service/ai-service/face-recognition
  - AI Fashion
  - OCR
  - Playground Vector Search
  - AI 포토
  - AI 생활지원사

## 알아야 할 기본 지식

### Spring AI

- 엔터프라이즈 데이터, API들을 AI Model과 연결해주는 역할
- AI Provider들과 연동
  - Anthropic, OpenAI, Microsoft, Amazon, Google, Ollama
- AI 모델 output을 자바 POJO 객체로 매핑
- 모든 주요 벡터 데이터 베이스 지원
  - Apache Cassandra, Azure Cosmos DB, Azure Vector Search, Chroma
  - Elasticsearch, OpenSearch, GemFire
  - MariaDB, Milvus, MongoDB Atlas, Neo4j, Oracle
  - PostgreSQL/PGVector, Pinecone, Qdrant
  - Redis, SAP Hana, Typesense, Weaviate
- AI 관련 동작에 대한 관측가능성
- Chat Conversation Memory and Retrieval Augmented Generation(RAG) 지원
- 고급 사용 사례를 구현하기 위해 임베딩을 지원

### 프롬프트

- AI 모델이 특정 출력을 생성하도록 안내하는 언어 입력
- 많은 AI 모델에서 단순한 문자열이 아님
- ChatGPT API는 여러 텍스트 입력을 제공하며, 각 텍스트에는 역할이 할당 됨
  - 예를 들어, 동작 방식을 지정하고 상호작용의 컨텍스트를 설정하는 시스템 역할이 있음
  - 또한 일반적으로 사용자 입력인 사용자 역할도 있음
- 효과적인 프롬프트를 만드는것은 예술이자 과학
- 이러한 상호작용 스타일의 중요성 떄문에 "프롬프트 엔지니어링"이라는 용어가 별도의 분야로 부상했음
- 프롬프트 공유는 공동체적 관행이 되었으며, 이 주제애 대한 활발한 연구가 진행 중
- 효과적인 프롬프트를 만드는 것이 얼마나 반직관적인지를 보여주는 예
  - 최근 연구 논문에 따르면 가장 효과적인 프롬프트는, "깊이 숨을 들이쉬고 단계별로 연습해 보세요" 라는 문구로 시작한다고 함
  - 아직 ChatGPT와 같은 기술을 효과적으로 활용하는 방법을 완전히 이해하지 못함

### 임베딩

- 입력 간의 관계를 포착하는 텍스트, 이미지, 비디오의 숫자적 표현
- 벡터라고 하는 부동 소수점 숫자 배열로 변환하는 방식으로 작동함
- 텍스트로 부터 생성된 벡터로 거리를 계산하면, 두 텍스트가 유사한지 판단할 수 있음
- 임베딩은 특히 검색 증강 생성(RAG) 패턴과 같은 실용적인 분야에서 중요함
- AI가 확장된 의미 공간에서의 "위치"를 기반으로 관련 개념을 식별하고 그룹화 할 수 있도록 하기 떄문임

### Retrieval Augmented Generation (검색 증강 생성)

- 학습 데이터의 무결성을 확보하기 위한 방법
- LLM의 환각 현상을 보완하기 위한 방법 중 하나
- LLM이 답변을 생성하기 전에 외부의 학습 데이터 소스를 참조하여 답변의 정확도를 높이는 방식
- 작동 방식
  - 외부 데이터 생성
    - API, 데이터베이스, 문서 등의 다양한 소스에서 원하는 데이터를 가져온다.
    - LLM이 이해할 수 있도록 복잡한 데이터를 임베딩 언어 모델을 사용하여 벡터 형태로 변환한다
    - 변환된 벡터 데이터를 벡터 데이터베이스에 저장하여 LLM이 이해할 수 있는 지식 라이브러리를 생성한다
  - 관련 정보 검색
    - 사용자가 프롬프트를 입력하면, 질의 인코더가 사용자 프롬프트를 벡터 형태로 인코딩한다
    - 인코딩된 프롬프트와 관련된 정보를 벡터 데이터베이스에서 검색하여 가져온다
    - 검색 키워드가 많이 포함된 문서를 찾는 키워드 검색, 의미를 분석하여 벡터 간의 유사도를 검색하는 시맨틱 검색, 두 방법을 결합한 하이브리드 검색 방법 등이 있다
  - LLM 프롬프트 확장
    - 검색된 데이터를 컨텍스트에 추가하여 사용자 프롬프트를 보강한다.
    - 확장된 프롬프트를 LLM에 전달하면, LLM이 검색된 데이터를 활용하여 답변을 생성한다
  - 외부 데이터 업데이트
    - 최신 데이터를 유지하기 위해 문서를 비동기적으로 업데이트한다

### 벡터 데이터베이스

## 아키텍처 설계

### RAG/AI 백엔드 설계

- 목표
  - 사내/서비스 문서를 기반으로 RAG 구성
  - 여러 모델(OpenAI, Claude, HuggingFace, 사내용 모델 서버)을 붙일 수 있음
  - 외부 클라이언트(웹/앱)는 하나의 통합 API만 호출
  - 우리는 Spring(Kotlin) 기반의 RAG/Orchestration 백엔드를 설계
- 핵심 역할

  > 문서 수집/벡터화 -> 벡터 스토어 관리 -> 쿼리 시 검색 -> 적절한 모델 선택/호출 -> 응답 조립 후 반환

#### 1. 아키텍처

- ```
  [Client(App/Web)]
          |
          v
  [API Gateway / Spring RAG API]  --(Auth, Rate Limit)
          |
          |---> [RAG Orchestrator(Service Layer)]
          |        |
          |        |---> [Vector Store (pgvector / Redis / Pinecone)]
          |        |---> [Document Store (RDB / S3)]
          |        |---> [Model Router]
          |                |---> [LLM Provider 1 (OpenAI, Claude, etc)]
          |                |---> [LLM Provider 2 (HuggingFace Inference)]
          |                |---> [Internal Model Server (Python, gRPC/HTTP)]
          |
          |---> [Monitoring/Logging (OTel, Prometheus, ELK)]
          |
  [Offline Ingestion Pipeline]
          |
          +---> [Document Collector/Parser]
              [Chunker + Embedder]
              [Vector Store Writer]
  ```

#### 2. Ingestion 파이프라인 설계 (문서 -> 벡터 DB)

- 컴포넌트
  - Document Collector
    - S3, DB, Notion, Git Repo, 파일 업로드 등에서 원문 수집
    - 결과를 raw_document 테이블/스토리지에 저장
  - Parser / Normalizer
    - PDF, HTML, Markdown, Word 등을 텍스트로 추출
    - 공통 포맷 : `Document(id, title, body, metadata)`
  - Chunker
    - 문서를 RAG용 청크로 분리
    - 전략 : sentence-aware + length + overlap (300 ~ 800 tokens, 50 ~ 100 overlap)
  - Embedder
    - EmbeddingClient로 chunk를 embedding vector로 변환
    - 예 : OpenAI `text-embedding-3-small`
  - Vector Store Writer
    - VectorStore에 (id, embedding, metadata) upsert
    - 예 : PostgreSQL + pgvector
- Ingestion은 배치(Spring Batch)나, 이벤트 기반(Kafka)로 돌리면 된다

#### 3. Query 파이프라인 설계 (질문 -> 검색 -> 모델 호출 -> 응답)

- 고수준 플로우
  - 클라이언트 요청
  - 인증/인가, Rate Limit
  - RAG Orchestrator가 :
    - Query Normalization (언어 감지, 길이 제한 등)
    - Vector Store에서 유사 청크 검색
    - ModelRouter를 통해 적절한 모델 선택
    - Prompt 구성 (reterieved context + user query)
    - LLM 호출
    - 응답 post-processing (필요하면 출처 하이라이트)
    - 응답 + 사용된 메타데이터 반환
