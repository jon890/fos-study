# Spring Batch 공부 내용 모음

스프링 배치 레퍼런스 문서와, 강의를 통해 학습 후 Spring Batch의 기본 개념과 실전에 대해서 정리해보고자 합니다.

- 2025.11.20 - Spring Batch 6이 출시되며 Spring Boot 4 버전과 완전하게 통합되었습니다.
  - 해당 문서는 Spring Batch 6은 다루지 않고 5버전을 다룰 예정입니다.
  - 레퍼런스 문서 : [https://docs.spring.io/spring-batch/reference/5.2/index.html](https://docs.spring.io/spring-batch/reference/5.2/index.html)
  - 참고한 강의 : [죽음의 스프링 배치](https://www.inflearn.com/course/%EC%A3%BD%EC%9D%8C%EC%9D%98-spring-batch)

## 목차

### 죽음의 스프링 배치

- **0. 배치란 무엇인가?, Spring Batch 시작해보기**
  - [0.1. 배치란 무엇인가?](./0.1-introduce.md)
  - [0.2. 첫 번째 배치 만들어보기](./0.2-first-job-example.md)
- **1. 스프링 배치의 핵심 컴포넌트들**
  - [1.1. 스텝의 종류는 어떤 것이 있을까?](./1.1-type-of-steps.md)
  - [1.2. 잡 파라미터](./1.2-job-parameters.md)
  - [1.2. 리스너](./1.2-job-parameters.md)
- **2. 다양한 데이터 소스를 처리하는 법**
  - [2.1. 파일을 읽어보자 - FlatFileItemReader](./2.1-flat-file-item-reader.md)
  - [2.2. 파일에 써보자 - FlatFileItemWriter](./2.2-flat-file-item-writer.md)
- **4. 고급 스텝 기법 - 스텝을 해부해보자**
  - [4.1. 아이템 스트림](./4.1-item-stream.md)
  - [4.2. 아이템 프로세서](./4.2-item-processor.md)
  - [4.3. 내결함성](./4.3-fault-tolerant.md)

### 다양한 기법들

- **비동기 아이템 프로세서**
  - [AsyncItemProcessor](./async-item-processor.md)
