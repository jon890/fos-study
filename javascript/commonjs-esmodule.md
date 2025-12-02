# CommonJS와 ECMAScript Modules

- Node.js에는 CommonJS, ECMAScript Modules(이하 CJS, ESM)라는 두가지 모듈 시스템이 있음

  > 참고 : Node.js는 언제부터 ESM을 지원했는가?
  >
  > - **1. Node.js 8.5 (2017년) - 가장 최초, 실험적 지원 시작**
  >
  >   - `--experimental-modules` 플래그 필요
  >   - .mjs 확장자로만 사용 가능
  >   - 매우 초기 버전, 실무 사용 불가 수준
  >   - CJS와 ESM의 상호윤용성 거의 없음
  >   - "Node가 ESM을 넣기 시작한 최초 시점"
  >
  > - **2. Node.js 10.x (2018) - 여전히 실험적, 기본 구조 정비**
  >
  >   - import resolution, loader 구조 개선
  >   - flag 여전히 필요
  >   - 생태계가 ESM을 쓰기엔 불안정
  >
  > - **3. Node.js 12.17 (2020년 5월) - 플래그 없이 '실험적' ESM 도입**
  >
  >   - `--experimental-modules`없이 ESM 가능
  >   - `.mjs`, `"type": module` 도입
  >   - 점진적 실사용 시작
  >   - 여기서 부터 "현대 Node.js ESM 형태"가 만들어짐
  >
  > - **4. Node.js 13.2 (2019년 말) - ESM 지원 안정화 단계 진입**
  >
  >   - CJS <-> ESM 상호운용성 개선
  >   - 동적 import 안정화
  >   - loader 훅 안정화 작업 시작
  >
  > - **5. Node.js 14 LTS (2020년 10월) - 공식적인 안정화**
  >
  >   - Node 공식 문서에서 "ESM is stable" 명시
  >   - 대부분 기능이 실무에서 사용 가능한 수준
  >   - "Node.js에서 ESM이 정식 지원으로 인정받은 버전"
  >
  > - **6. Node.js 16 (2021) - ESM 사용자가 실무 다수로 전환**
  >   - ESM 로더 속도 개선
  >   - CJS <-> ESM 상호운용성 강화
  >   - fetch API 등 브라우저 API와의 통합도 증가
  >   - 프론트 영역과 호환을 위해 ESM 중심으로 발전

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
