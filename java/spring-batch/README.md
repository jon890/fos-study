# Spring Batch 학습 문서

Spring Batch 5를 기준으로 생명주기, 내결함성과 메타데이터처럼 운영에서 다시 확인할 주제를 정리한다.

- 2025.11.20 - Spring Batch 6이 출시되며 Spring Boot 4 버전과 완전하게 통합되었습니다.
  - 해당 문서는 Spring Batch 6은 다루지 않고 5버전을 다룰 예정입니다.
  - 레퍼런스 문서 : [https://docs.spring.io/spring-batch/reference/5.2/index.html](https://docs.spring.io/spring-batch/reference/5.2/index.html)
  - 참고한 강의 : [죽음의 스프링 배치](https://www.inflearn.com/course/%EC%A3%BD%EC%9D%8C%EC%9D%98-spring-batch)

## 목차

### 실행 생명주기와 내결함성

- **핵심 컴포넌트**
  - [리스너](/java/spring-batch/1.3-listener.md)
- **스텝 생명주기**
  - [4.1. 아이템 스트림](/java/spring-batch/4.1-item-stream.md)
  - [4.3. 내결함성](/java/spring-batch/4.3-fault-tolerant.md)
- **메타데이터**
  - [5.1. Job과 메타데이터 저장소](/java/spring-batch/5.1-job-and-metadata-repository.md)

### 다양한 기법들

- **성능 최적화**
  - [AsyncItemProcessor — 비동기 아이템 프로세서](async-item-processor.md)
- **빈 스코프와 생명주기**
  - [@StepScope / @JobScope — Step·Job 실행마다 새로운 빈을 만드는 이유](step-scope.md)
