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

### 벡터 데이터베이스
