# Node.js

## V8 엔진

- V8은 Google이 만든 고성능 Javascript 엔진으로, JS 코드를 파싱, 컴파일, 최적화, 실행까지 모두 담당하는 VM (가상 머신)
- Node.js는 이 엔진을 그대로 가져와 서버 사이드 JS 실행 환경으로 만든 것
  - 브라우저에서는 Chrome
  - 서버에서는 Node, Deno, Bun 등 많은 런타임이 V8을 중심으로 움직인다.

### 1. V8의 전체 구조 개요

- V8은 대략 다음 구성 요소로 이루어짐

  1. Parser
  2. Ignition 바이트코드 인터프리터
  3. TurboFan JIT 컴파일러
  4. Garbage Collector (Orinoco) - 힙 메모리 관리
  5. 라이브러리(내장 객체 등)

- 흐름은 다음과 같이 동작

  > JS 코드 -> 파싱 -> AST -> 바이트코드 생성(Ignition) </br>
  > -> 실행 중 프로파일링 -> 최적 경로 수집 </br>
  > -> TurboFan이 최적화된 머신 코드를 생성

- 즉 "처음엔 인터프리터, 나중엔 JIT 컴파일러"
- -> 실행 시간이 길어질수록 성능이 빨라진다.

### 2. 간략 정리

> V8은 Node.js에서 JS를 빠르게 돌려주는 JIT + GC 기반 엔진이고, </br>
> Node는 이 위에 이벤트 루프/비동기 IO를 얹은 런타임이다. </br>
> Java(JVM)랑 비교하면, IO-bound에는 개발, 운영이 가볍고, </br>
> CPU-bound나 강한 타입/툴링 면에서는 Java가 더 유리하다.

### 3. Java(JVM) vs Node.js(V8) - 백엔드 관점에서 장단점 비교

- 공통점

  - JIT + GC가 있는 VM
  - 크로스 플랫폼
  - 장기 실행 서버 프로세스에 적합
  - 성능 튜닝 시, GC, 객체 할당 패턴, 스레드 모델을 의식해야 함

- ☕️ Java(JVM) 쪽이 강한 부분

  - **1. 멀티 스레드 & 병렬 처리**
    - JVM은 스레드/락/동시성 라이브러리/가상 스레드(Loom) 등 CPU-bound, 복잡한 동시성 처리에 훨씬 적합
    - 여러 코어를 적극 활용하기 좋은 구조 (물론 Node도 cluster나 worker로 나눌 수 있찌만 복잡함)
  - **2. 성숙한 GC & 튜닝 옵션**
    - G1, ZGC, Shenandoah 등 다양한 GC 알고리즘
    - GC pause를 줄이고 싶은 경우 선택지가 많음
    - 진짜 하드코어 튜닝도 가능
  - **3. 정적 타입 + 풍부한 엔터프라이즈 생태계**
    - 컴파일 타임 검증, IDE 지원, 리팩터링에 강함
    - 대규모 코드베이스, 금융, 엔터프라이즈 도메인에 강함
    - Spring 등 서버 프레임워크 성숙
  - **4. 툴링/옵저버빌러티**
    - JFR, JMX, VisualVM, Flight Recorder, Mission Control 등
    - JVM 프로파일링, 히스토리, 스레드 덤프, 힙 덤프 툴이 매우 뛰어남

- ✅ Node.js(V8) 쪽이 강한 부분

  - **1. 개발 생산성 & 언어 일원화**
    - 프론트/백 모두 JS/TS로 작성 -> 컨텍스트 전환 비용 낮음
    - 경량 API 서버, BFF, SPA 백엔드 등에 적합
  - **2. IO-bound 서비스에 강함**
    - 싱글 스레드 + 비동기 IO 모델 -> 적은 자원으로 많은 동시 연결 처리 (채팅, 게이트웨이, BFF 등)
  - **3. 경량 배포 & 빠른 부팅**
    - JAR/전통적 애플리케이션보다 부팅 속도 빠른 편
    - 컨테이너 환경에서 작은 서비스 여러 개 띄우기 좋음
  - **4. 생태계와 속도**
    - NPM 생태계 폭발적
  - 빠른 실험/PoC, API 게이트웨이, 엣지 컴퓨팅 등에 적합

## Node.js 운영시 주의해야하는 핵심 포인트 10가지

### 1. CPU-bound 작업을 메인 스레드에서 돌리지 말 것

- Node는 JS 실행이 싱글 스레드라서 CPU를 많이 쓰는 코드를 돌리면 이벤트 루프가 막힌다
- 막히면?
  - 전체 요청이 지연됨
  - 서버가 죽은 것 처럼 보임
  - TPS 급락
- 해결책
  - worker thread
  - child process
  - Redis queue / Kafka 등으로 다른 프로세스로 오프로딩
  - WebAssembly(특정 경우)
  - 서버를 분리 (API 서버, 배치 서버 역할 분리)
- 체크해야할 패턴 예
  - bcrypt 패스워드 해싱 -> CPU Heavy
  - 이미지 처리, PDF 생성 등
  - 10만 건 이상 배열 sort, map, reduce
  - 복잡한 JSON 변환
  - 암호화 연산

### 2. 큰 객체/배열/Buffer를 오래 들고 있지 않기

- V8 힙은 기본적으로 1.5~2GB 정도 크기 제한이 걸려있음
  - 큰 배열/버퍼를 오래 잡고 있으면
    - Old Generation으로 승격됨
    - GC 비용 올라감
    - latency spike 발생
    - OOM 위험
  - 실제로 발생하는 케이스
    - DB에서 20MB JSON 결과를 한 번에 들고 있음
    - 이미지 / 파일 버퍼를 메모리에 다 올림
    - 파일을 chunk 처리 안하고 전체 read 함
  - 해결책
    - stream 방식 처리
    - chunk 단위 분할
    - Buffer pooling
    - 압축/압축해제 과정에서도 스트림 사용

### 3. JSON.parse / stringify 과사용 피하기

- Node.js에서 JSON 처리 비용이 생각보다 큼
- 문제
  - JSON.parse는 full parsing + deep copy 수준의 비용
  - stringify는 메모리 재할당 잦음
  - deep clone을 반복하면 GC 압박
- 해결 방법
  - 변환 횟수 최소화
  - 객체 복제할 떄 structruedClone 또는 shallow copy
  - 대용량 JSON을 stream 기반 파싱 (JSONStream 등)

### 4. Promise 폭주 / 메모리 누수 주의

- 비동기 leak이 실무에서 진짜 많이 발생함

  - 예시

    - ```ts
      setInterval(() => {
        // ...
      }, 1000); // clear 안함

      async function loop() {
        while (true) {
          await doSomething(); // break 없음
        }
      }
      ```

  - Promise가 계속 쌓이고 GC가 회수할 타이밍 놓치면
    - 메모리 점점 증가
    - 이벤트 루프 압박
    - 서버가 뻗음
  - 해결책
    - setInterval 대신 setTimeout chain 사용
    - Promise.all 남발 주의
    - 끝없는 await 루프 금지
    - async resource leak을 추 적 (AsyncLocalStorage, autocannon 테스팅 등)

### 5. EventEmitter 리스너 누수 주의

- 이것도 실무에서 은근히 흔함

  - 예시

  - ```ts
    emitter.on('event', handler);
    ```
  - 핸들러를 계속 등록하는데 제거 안하면 메모리 누수 발생
  - Node가 다음 경고를 띄움
    - MaxListenersExceededWarning
  - 해결
    - emitter.removeListener
    - emitter.once
    - 리스너 개수 확인

### 6. 클러스터링 / 다중 프로세스 활용

- Node는 싱글 스레드라 CPU 코어를 하나만 씀, 인스턴스를 늘리지 않으면 성능 제대로 나오지 않음
- 대안
  - PM2 cluster mode
  - Node cluster API
  - Docker/K8s 에서 복수 replica
  - Worker Threads로 CPU offload 패턴

### 7. 동시성 제어 필요할 떄 Lock/Mutex 개념 의식하기

- Node는 싱글 스레드지만 I/O 비동기기 때문에 race condition은 존재함
- Node의 싱글 스레드는 공유 메모리 문제는 적지만, 공유 리소스(DB/Redis/S3)을 다룰 떄는 여전히 race condition 생김
- 해결
  - Redis distributed lock
  - DB optimistic lock
  - queue 기반 처리
  - Atomic operation 적극 사용

### 8. 메모리 프로파일링 / CPU 프로파일링을 할 줄 알아야 함

- 필수 도구
  - Chrome DevTools (Profiler)
  - Clinic.js
  - 0x
  - Node heap snapshot
  - flamegraph
- 특히 메모리 누수와 CPU block은 Node 운영의 큰 이슈

### 9. GC Pause 고려

- Node는 GC가 자동이라 편하지만, latency-sensitive 서비스에서는 중요한 문제
- 문제 시나리오
  - API에서 대용량 JSON 한번에 처리
  - 서버 내부에서 캐시 객체 overly large
  - 자주 생성 / 버려지는 작은 객체가 많음
- 해결
  - 객체 재사용
  - 버퍼 풀링
  - stream 기반 IO
  - GC 옵션 조정 (`--max-old-space-size`, `expose-gc` 등)
