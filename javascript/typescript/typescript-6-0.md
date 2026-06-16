# TypeScript 6.0 — 마지막 JS 컴파일러, 그리고 Go로 가는 다리

**작성일**: 2026.05

TypeScript 6.0이 2026년 3월에 릴리스됐다. 이 버전을 정리하고 싶었던 이유는 단순히 새 기능이 들어와서가 아니라, **이게 마지막 JS 기반 TypeScript** 라는 의미가 컸다. TypeScript 7.0은 컴파일러 전체를 Go로 다시 쓴 버전으로 출시되고, 6.0은 거기로 넘어가는 다리 역할로 설계됐다.

그래서 6.0의 변경사항은 단순한 새 기능 추가가 아니라 **7.0 으로 안전하게 이사하려면 지금 뭘 정리해야 하나** 가 흐름의 중심이다. 새 기능보다도 기본값 변경·옵션 제거·지원 종료(deprecation) 가 더 많다.

이 글은 내가 공부하면서 정리한 노트다.

---

## TypeScript 6.0 의 정체성

마이크로소프트가 명시적으로 말하는 6.0 의 포지션은 이렇다.

- **마지막 JS 기반 TypeScript 컴파일러 릴리스**
- **TS 7.0 (Go 재작성) 으로 가는 마이그레이션 다리**
- **새 기능보다 deprecation·기본값 변경이 더 큰 비중**

이 포지션을 이해해야 6.0 변경사항이 "왜 이렇게 빡빡한가" 가 자연스럽게 읽힌다. Go 로 다시 쓰는 컴파일러는 기존 JS 컴파일러보다 빠른 대신, 기존 컴파일러의 모든 "조용한 추론·자동 보정" 동작을 그대로 따라갈 수는 없다. 그래서 6.0 에서 **기본값과 옵션을 한 번 정리하고 → 7.0 에서는 정리된 기준만 따른다** 는 전략이다.

---

## Breaking Changes — 기본값과 옵션 정리

### 2.1 기본값이 바뀐 5개 옵션

| 옵션 | 기존 기본값 | 6.0 기본값 | 의미 |
|---|---|---|---|
| `strict` | `false` | `true` | 엄격 모드가 기본 |
| `module` | `commonjs` | `esnext` | ESM 이 기본 |
| `target` | `es3` | `es2025` | 최신 JS 가 기본 |
| `rootDir` | 추론됨 | `tsconfig.json` 디렉터리 | 명시 권장 |
| `types` | `["*"]` (모두 로드) | `[]` (빈 배열) | 필요한 것만 로드 |

가장 임팩트 큰 변화는 **`types` 의 기본값이 `["*"]` 에서 `[]` 로** 바뀐 것이다. 기존엔 `node_modules/@types` 아래의 모든 타입 패키지를 자동 로드했는데, 이게 빌드 속도와 메모리 사용량의 숨은 비용이었다. 6.0 부터는 필요한 것만 명시한다.

```json
{
  "compilerOptions": {
    "types": ["node", "jest"]
  }
}
```

명시 안 하면 어떤 타입도 로드되지 않아 많은 에러가 나기 쉽다. 마이그레이션 시 첫 번째 체크 항목이다.

### 2.2 제거된 옵션

```bash
# 모두 deprecation error 발생
--target es5            # → es2015 이상
--module amd            # → 외부 번들러 사용
--module umd            # → 외부 번들러
--module system         # → 외부 번들러
--moduleResolution node     # → nodenext 또는 bundler
--moduleResolution classic  # → nodenext 또는 bundler
--baseUrl               # → paths 에 접두사 명시
--outFile               # → 외부 번들러
--downlevelIteration    # → target 을 es2015 이상으로
```

es5 가 빠진 게 가장 눈에 띈다. 2026년 시점에 ES5 만 지원하는 환경(IE 11 등) 은 사실상 사라졌고, 더 낮은 타겟이 필요하면 Babel 같은 외부 도구를 쓰면 된다는 입장이다.

`module: amd/umd/system` 도 같은 이유다. ESM 과 CommonJS 두 가지 외엔 번들러가 책임진다.

### 2.3 옵션 값이 강제된 경우

```typescript
// 6.0 에서는 모두 에러
"esModuleInterop": false
"allowSyntheticDefaultImports": false
"alwaysStrict": false
```

`esModuleInterop` 은 CommonJS 모듈을 `import x from "pkg"` 형태로 받을 수 있게 해주는 옵션이었다. 안전한 동작이라 6.0 에서는 항상 켜진다.

```typescript
// 이제 항상 동작
import express from "express";
```

### 2.4 문법 변경

```typescript
// ❌ 6.0 에서 제거
module Foo {
  export const bar = 10;
}

// ✅ 대체
namespace Foo {
  export const bar = 10;
}
```

`module` 키워드를 namespace 의미로 쓰던 옛 문법이 사라졌다. `declare module "some-module"` 같은 모듈 선언 문법은 그대로 유지된다.

```typescript
// ❌ 6.0 에서 제거
import json from "data.json" assert { type: "json" };

// ✅ 대체
import json from "data.json" with { type: "json" };
```

Import attributes 문법이 stage 3 시절 `assert` 에서 stage 4 정식 표준 `with` 로 바뀌었다.

---

## 새 기능 — 추론·import 편의

### 3.1 `this`-less 함수의 컨텍스트 민감도 완화

기존 TypeScript 는 메서드 문법(`method() {}` 형태) 의 함수 파라미터 추론에 컨텍스트 민감도가 강했다. 같은 객체 안의 다른 메서드 위치에 따라 추론이 깨지는 경우가 있었다.

```typescript
declare function callIt<T>(arg: {
  consume: (y: T) => void;
  produce: () => T;
}): void;

// 6.0 이전: 순서 따라 추론 실패 가능
callIt({
  consume(y) { return y.toFixed(); },
  produce() { return 42; },
});
```

6.0 부터는 함수가 `this` 를 참조하지 않으면 컨텍스트 민감도를 약하게 적용한다. 결과적으로 위 코드에서 `y` 가 `number` 로 안정적으로 추론된다.

실무에서 자주 만나던 "왜 여기서 타입이 `any` 가 되지?" 케이스의 일부가 줄어들 것으로 보인다.

### 3.2 `#/*` 형태 subpath imports

Node.js 의 `imports` 필드를 활용한 내부 alias 가 더 짧아졌다.

```json
{
  "imports": {
    "#/*": "./dist/*"
  }
}
```

```typescript
import { something } from "#/utils";
```

기존엔 `#root/*` 같이 prefix 가 필요했는데, 이제 `#/` 만으로도 패키지 root alias 를 잡을 수 있다. Node.js 20+ 기준.

### 3.3 `--stableTypeOrdering` 플래그

```bash
tsc --stableTypeOrdering
```

7.0 (Go 컴파일러) 은 타입 ID 를 선언 순서에 의존하지 않고 결정적으로 부여한다. 6.0 컴파일러로 동일한 결정 알고리즘을 미리 시뮬레이션해서, **6.0 → 7.0 마이그레이션 시 타입 추론이 달라지는 케이스를 사전 검출하는 용도** 다.

단점: 이 플래그를 켜면 빌드가 약 25% 느려진다. 운영 빌드에 상시 적용하는 게 아니라 **마이그레이션 검증용으로만 일시 사용** 하는 게 맞다.

### 3.4 ES2025 와 Temporal

표준 라이브러리 타입이 확장됐다.

```typescript
// ES2025
RegExp.escape("hello.world");  // 정규식 안전 이스케이프
new Map().getOrInsert(key, defaultValue);
new Map().getOrInsertComputed(key, () => compute());

// stage 4 (esnext)
import { Temporal } from "temporal";
Temporal.Now.instant();
```

`Temporal` 은 `Date` 의 후속 표준 API 다. 시간대·달력·duration 을 명시적으로 다루는 타입 시스템을 제공한다. 6.0 에서 타입 정의가 들어왔다. 런타임 구현은 환경에 따라 별도 polyfill 필요.

---

## TypeScript 7.0 — Go 재작성

6.0 의 거의 모든 결정이 결국 7.0 을 위한 것이다. 7.0 의 핵심을 이해해야 6.0 변경이 왜 이런지 이해된다.

### 4.1 왜 Go 인가

마이크로소프트가 공개한 [native port 글](https://devblogs.microsoft.com/typescript/typescript-native-port/) 에서 정리한 이유:

- **네이티브 컴파일** — JS V8 위 인터프리트 대신 바로 머신 코드
- **shared memory + goroutine 병렬성** — 파일·타입 체크 병렬화
- **GC 친화적** — JS heap 의 보수적 동작 회피
- **Go 의 표준 라이브러리** — 파일 I/O, 메모리 관리 안정적

C++/Rust 가 더 빠를 수도 있지만, Go 는 빌드·동시성 모델이 TS 컴파일러 구조와 잘 맞고, 마이크로소프트 내부에서 다른 도구도 Go 로 가는 추세라 선택했다.

### 4.2 성능 — 10배

마이크로소프트가 공유한 벤치마크:

- **Sentry 코드베이스**: 60초 → **7초** (약 8.5배)
- **VS Code 코드베이스**: 약 10배 빠름
- 평균적으로 **10배 빠른 type check 가 일반적**

이 수치는 단순한 컴파일 시간 줄어드는 게 아니라, **에디터 hover·자동완성 응답 속도** 가 즉각 빨라진다는 의미다. 대형 monorepo 에서 가장 큰 임팩트가 나올 영역이다.

### 4.3 현재 상태 — Native Preview

```bash
npm install @typescript/native-preview
```

또는 VS Code 확장으로도 nightly preview 가 배포돼 있다. 하지만 7.0 정식 릴리스 전까지 한계가 있다.

- **declaration emit (`.d.ts` 생성) 미완**
- **JS 파일 (`allowJs: true`) 지원 미완**
- **에디터 기능 일부 미완** — rename, find-all-references, auto-imports 등
- **호환성 검증 진행 중** — 대형 코드베이스에서 추론 차이 케이스 수집 중

당장 운영에 쓰기엔 이르고, **6.0 으로 코드를 정리해두고 → 7.0 정식 릴리스 시점에 native 로 점진 전환** 하는 게 권장 경로다.

---

## 마이그레이션 전략

마이크로소프트가 만들어둔 도구가 있다.

```bash
npx @andrewbranch/ts5to6
```

이 CLI 는 mechanical 한 변환을 대부분 자동화한다. tsconfig.json 의 deprecated 옵션 제거, 기본값 명시화, 문법 변경(`module` → `namespace`, `assert` → `with`) 등을 다룬다.

### 5.1 단계별 체크리스트

```
1. npx @andrewbranch/ts5to6 실행 — 자동 변환
2. tsconfig.json 직접 점검
   ├─ types: ["node", "..."] 명시
   ├─ rootDir 명시
   ├─ module: "nodenext" 또는 "preserve"
   └─ moduleResolution: "nodenext" 또는 "bundler"
3. baseUrl 사용 중이면 paths 에 prefix 로 이동
4. esModuleInterop / allowSyntheticDefaultImports 의 false 값 제거
5. tsc 한 번 돌려서 deprecation 에러 잡기
6. (선택) --stableTypeOrdering 으로 7.0 추론 차이 사전 검출
7. 추론이 달라지는 곳은 명시 타입 추가
```

### 5.2 baseUrl 대체 패턴

`baseUrl` 이 가장 흔한 마이그레이션 함정이다.

```json
// Before
{
  "baseUrl": "./src",
  "paths": {
    "@app/*": ["app/*"]
  }
}

// After
{
  "paths": {
    "@app/*": ["./src/app/*"]
  }
}
```

`paths` 의 값에 `baseUrl` 이 묵시적으로 prepend 되던 동작이 없어졌으므로, **모든 path 값에 명시적 prefix** 가 필요하다.

### 5.3 추론 차이 해소

7.0 의 stableTypeOrdering 이 켜지면 일부 코드에서 추론 결과가 달라질 수 있다. 해결은 단순하다.

```typescript
// 추론에 의존하던 코드
const value = someGeneric({ /*...*/ });

// 명시 타입으로 고정
const value: ExpectedType = someGeneric({ /*...*/ });
// 또는
const value = someGeneric<ExpectedType>({ /*...*/ });
```

명시할수록 7.0 으로 넘어갈 때 손볼 일이 줄어든다.

---

## 정리하면서 느낀 점

- TypeScript 가 **"새 기능 추가" 라는 흐름에서 "구조 정리" 라는 흐름으로 한 번 끊고 가는 버전** 이다. 5.x 시리즈가 5.0 부터 5.9 까지 새 기능을 잔뜩 넣었던 것과 대조적이다.
- 기본값 변경이 많아 보이지만 대부분 **더 안전한 쪽으로 통일** 한 것이라, 새 프로젝트 시작할 땐 오히려 가벼워졌다. 마이그레이션이 어려운 건 기존 프로젝트의 누적된 옵션 설정 때문이다.
- TS 7.0 의 10배 성능은 단순 빌드 시간이 아니라 **에디터 응답성 (large monorepo) 에서 가장 체감** 될 것 같다. 백엔드보단 프론트엔드·풀스택 모노레포가 가장 큰 수혜다.
- 마이크로소프트가 Go 로 갈 정도면 **JS/TS 생태계의 도구들이 점점 네이티브로 가는 흐름** 이 확정적이다. esbuild/swc 같은 빌드 도구가 그 신호였고, 이제 컴파일러 본체도 합류했다.

내가 운영에 즉시 적용할 필요는 없지만, 다음 새 프로젝트 시작할 땐 처음부터 6.0 기준으로 시작하면 7.0 으로 넘어갈 때 부담이 적다.

---

## 참고

- [Announcing TypeScript 6.0 (공식 release blog)](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/)
- [A 10x Faster TypeScript (Go port 배경)](https://devblogs.microsoft.com/typescript/typescript-native-port/)
- [Announcing TypeScript Native Previews](https://devblogs.microsoft.com/typescript/announcing-typescript-native-previews/)
- [TypeScript 5.x to 6.0 Migration Guide (gist)](https://gist.github.com/privatenumber/3d2e80da28f84ee30b77d53e1693378f)
- [@typescript/native-preview (npm)](https://www.npmjs.com/package/@typescript/native-preview)
- [microsoft/typescript-go (GitHub)](https://github.com/microsoft/typescript-go)
