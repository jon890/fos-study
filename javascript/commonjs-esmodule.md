# CommonJS와 ECMAScript Modules

- Node.js에는 CommonJS, ECMAScript Modules(이하 CJS, ESM)라는 두가지 모듈 시스템이 있음

### CommmonJS (CJS)

```js
// add.js
module.exports.add = (x, y) => x + y;

// main.js
const { add } = require('./add');

add(1, 2);
```

### ECMAScript Module (ESM)

```js
// add.js
export function add(x, y) {
  return x + y;
}

// main.js
import { add } from './add.js';

add(1, 2);
```

- CJS는 `require` / `module.exports` 를 사용하고, ESM은 `import` / `export` 문을 사용한다
- CJS module loader는 동기적으로 작동하고, ESM module loader는 비동기적으로 작동한다
  - ESM은 Top-level Await을 지원하기 때문에 비동기적으로 작동함

## 추가자료

### 참고 : Node.js는 언제부터 ESM을 지원했는가?

- **1. Node.js 8.5 (2017년) - 가장 최초, 실험적 지원 시작**

  - `--experimental-modules` 플래그 필요
  - .mjs 확장자로만 사용 가능
  - 매우 초기 버전, 실무 사용 불가 수준
  - CJS와 ESM의 상호윤용성 거의 없음
  - "Node가 ESM을 넣기 시작한 최초 시점"

- **2. Node.js 10.x (2018) - 여전히 실험적, 기본 구조 정비**

  - import resolution, loader 구조 개선
  - flag 여전히 필요
  - 생태계가 ESM을 쓰기엔 불안정

- **3. Node.js 12.17 (2020년 5월) - 플래그 없이 '실험적' ESM 도입**

  - `--experimental-modules`없이 ESM 가능
  - `.mjs`, `"type": module` 도입
  - 점진적 실사용 시작
  - 여기서 부터 "현대 Node.js ESM 형태"가 만들어짐

- **4. Node.js 13.2 (2019년 말) - ESM 지원 안정화 단계 진입**

  - CJS <-> ESM 상호운용성 개선
  - 동적 import 안정화
  - loader 훅 안정화 작업 시작

- **5. Node.js 14 LTS (2020년 10월) - 공식적인 안정화**

  - Node 공식 문서에서 "ESM is stable" 명시
  - 대부분 기능이 실무에서 사용 가능한 수준
  - "Node.js에서 ESM이 정식 지원으로 인정받은 버전"

- **6. Node.js 16 (2021) - ESM 사용자가 실무 다수로 전환**
  - ESM 로더 속도 개선
  - CJS <-> ESM 상호운용성 강화
  - fetch API 등 브라우저 API와의 통합도 증가
  - 프론트 영역과 호환을 위해 ESM 중심으로 발전

### Node.js 에서 ESM 도입은 왜 늦어진걸까?

- **1. Node.js는 원래 CommonJS를 전제로 설계되었기 떄문**

  - Node.js는 2009년에 만들어졌고, 그때는 ESModule이라는 개념이 존재하지 않았음
  - 그래서 Node는 CommonJS를 기반으로 다음의 기능을 제공했음
    - `require()` (동기)
    - `module.exports`
    - `__dirname`, `__filename`
    - `require.cache`
    - 동적 require
    - 조건부 require
    - 런타임 import 패스 계산
  - 문제는, 이런 CJS 기능 대부분이 ESM 스펙과 충돌한다는 것
  - 즉 Node는 CJS를 깊게 내장한 플랫폼이라, ESM을 단순히 "붙여넣기"가 불가능했다

- **2. ESM 스펙이 너무 늦게 확정됐다**

  - ESM의 역사가 굉장히 꼬여 있었다
    - 초창기 브라우저 진영에서 ES6 모듈 도입을 추진했음
    - 모듈 로더 설계가 여러 번 뒤집힘
    - 파일 확장자 의미, import semantics, dynamic import, cycle resolution 같은 부분이 수 년간 논쟁
  - ESM 스펙이 "진짜 사용 가능한 수준"으로 확정된 건 2017년 이후
  - Node는 스펙이 안정되지 않은 상태에서 구현할 수 없었음

- **3. npm 생태계가 이미 CommonJS에 "완전히 고착되어 있었기 때문**

  - npm은 2010년 이후 수천만 패키지가 모두 CJS기반으로 만들어졌고
    - require() 사용
    - main 필드가 CJS 기반
    - 디렉토리 index.js 로딩
    - 자동 확장자 처리
    - require.resolve 규칙
  - 같은 Node 특유의 CJS 확장 규칙을 전제로 생태계가 굳어졌다.

  - 이 상태에서 Node가 갑자기 ESM을 공식 채택하면
    - 패키지 충돌
    - import와 require 혼용 오류
    - 의존성 resolution 완전히 깨짐
    - 런타임 semantics 달라져 동작이 바뀜
  - 이런 대혼란이 발생함

  - 즉 Node는 레거시 생태계를 깨지 않고 ESM을 넣어야 했기 떄문에 도입이 극도로 어렵고 느려질 수 밖에 없었다

- **4. CJS <-> ESM 상호운용성이 악몽 수준으로 어렵다**

  - Node는 웹 브라우저처럼 "ESM"만 사용할 수가 없다.
  - 왜냐면 기존 CJS 패키지가 너무 많아서 둘을 함꼐 운용해야 한다.
  - 하지만 이 두 모듈 시스템은 철학이 완전 다르다
  - 이 차이 때문에 Node가 아래 기능을 만들어야 했는데.. 이게 진짜 어려웠다
    - CJS -> ESM require 내부 변환 (Promise -> sync 변환)
    - ESM -> CJS import 시 createRequire 생성
    - 모듈 캐시를 양쪽에서 공유하지만 동일하게 유지
    - 디렉토리 해석 규칙 통일
    - `.js` 파일이 CJS인지 ESM인지 판단해야 하는 규칙
  - 이런 "브릿지 레이어" 때문에 ESM 도입은 자연스럽게 몇 년씩 지연된 것

- **5. Node.js의 모듈 해석 규칙(require resolution)이 ESM과 충돌**

  - Node의 CJS는 아래 같은 비표준 기능을 사용한다
    - `require('loadsh')` -> node_modules에서 자동 탐색
    - `require('./foo')` -> 확장자 자동 추론 (.js/.json/.node)
    - package.json의 `main` 사용
    - `index.js` 자동 로딩
  - 이런 규칙들은 ESM의 정적/URL 기반 모듈 해석 규칙과 전혀 맞지 않는다.

  - 브라우저 ESM은
    - 반드시 URL(또는 확장자) 명시
    - 디렉토리 추론 없음
    - node_modules 해석 없음
    - main 필드 없음
  - Node는 이 간극을 "최대한 안 깨지게" 메꾸느라 시간이 오래 걸렸음

- **6. ESM 도입을 늦춘 또 다른 이유 : 보안, 성능 문제**

- ESM은 본직적으로 비동기 로더 기반이라
  - 초기 로딩 성능
  - require -> import 변환 비용
  - module graph 해결 시간
  - 캐싱 정책 변화
- 이런 부분에서 Node core 팀은 매우 보수적이었음

- Node의 철학은
  > "런타임 안정성과 backwards compatibility를 최우선으로 한다
- 그래서 조금이라도 위험한 변화는 수 년 검증 후에만 적용한다

- **7. 정리**

  > Node는 CJS 기반으로 설계된 런타임이고, npm 생태계도 CJS를 기반으로 성장했기 때문에</br>
  > 완전히 다른 철학의 ESM을 통합하기 위해선 호환성, 성능, 스펙, 모듈 해석 규칙 모두를 재설계 해야 했으며</br>
  > 그 과정이 엄청난 난이도와 시간이 필요했다.
