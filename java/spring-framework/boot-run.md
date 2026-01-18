# `bootRun` 명령어는 뭘까?

- Spring Boot Gradle Plugin이 제공하는 애플리케이션 실행용 Gradle Task
- 즉 `./gradlew bootRun` : Spring Boot 앱을 소스 코드 그대로 JVM에서 실행해라

## bootRun은 어떤 명령어인가?

- Gradle 프로젝트에서 \*\*Spring Boot 애플리케이션을 실행하기 위한 Task
- **1. `mainClass`를 찾아서 JVM으로 실행**
  - `SpringApplication.run()`이 있는 클래스를 실행한다.
- **2. 빌드 없이 (=jar 파일 생성 없이) 바로 실행**
  - `bootRun`은 소스 변경 -> 바로 재실행이 가능한 개발 편의 기능
  - `bootJar` 같이 jar 생성이 필요한 정식 빌드는 하지 않음
- **3. 클래스패스를 Gradle이 구성**
  - Gradle이 프로젝트 dependencies를 모아 **classpath**를 구성해 JVM에 넘겨 실행

## 내부적으로 어떻게 동작할까?

1. Gradle이 `mainClass`를 설정한 Application 엔트리 포인트를 찾는다
2. 프로젝트 dependency를 모두 classpath로 구성한다
3. 아래와 같은 JVM 실행을 내부적으로 수행한다

```bash
java -cp <Gradle-created-classpath> com.example.MyApplication
```

> 즉 `bootRun`은 Gradle이 classpath를 관리하면서 Java 애플리케이션을 실행해주는 래퍼 역할
