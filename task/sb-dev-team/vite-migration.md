# Svelte 프론트엔드 번들러 Vite로 교체

**진행 기간**: 2023.12

기존에 Rollup 기반으로 직접 번들링하던 구조를 Vite로 교체했다. 환경별(dev/alpha/stage/release) 빌드가 복잡하게 얽혀 있었고, 특히 wemix SDK가 환경마다 다른 파일을 사용하는 구조라 처리할 게 좀 있었다.

---

## 왜 Vite로

당시 빌드 구조는 Rollup 설정 파일을 직접 관리하는 방식이었다. Svelte는 이미 공식적으로 Vite + `@sveltejs/vite-plugin-svelte` 조합을 권장하고 있었고, 설정이 단순해지는 것 외에도 개발 서버 HMR 속도 문제가 있어 전환을 결정했다.

---

## 주요 변경 사항

### 1. 환경 변수 prefix 추가

Rollup 때는 환경 변수를 자유롭게 사용할 수 있었는데, Vite는 클라이언트 측 환경 변수에 `VITE_` prefix를 강제한다. 기존 `.env` 파일을 전부 수정해야 했다.

```
# 기존
API_BASE_URL=https://...

# Vite 이후
VITE_API_BASE_URL=https://...
```

코드에서는 `import.meta.env.VITE_API_BASE_URL` 형태로 접근한다.

### 2. env 파일 디렉터리 분리

환경 파일이 프로젝트 루트에 섞여 있어서 별도 폴더로 정리했다.

```ts
// vite.config.ts
export default defineConfig({
  envDir: './env',
  // ...
})
```

### 3. base path 설정

배포 환경에서는 `/sports` 경로 하위에 올라가는 구조였다. Rollup 때는 이걸 별도 처리했는데 Vite는 `base` 옵션 하나로 해결됐다.

```ts
base: mode !== 'localdev' ? '/sports' : '/',
```

로컬에서는 `/` 그대로, 배포 환경에서는 `/sports`를 기본 경로로 쓴다.

### 4. sourcemap 제어

릴리즈 빌드에서는 소스맵을 포함하지 않도록 명시적으로 설정했다.

```ts
build: {
  sourcemap: mode !== 'release' ? true : false,
}
```

### 5. 빌드 버전 주입

빌드 시각을 `import.meta.env.VITE_BUILD_TIME`으로 주입해 런타임에서 확인할 수 있게 했다.

```ts
define: {
  'import.meta.env.VITE_BUILD_TIME': dayjs().unix(),
},
```

---

## wemix SDK 환경별 분리 문제

Vite 마이그레이션 이후 별도로 처리한 부분이다(2024.02). wemix SDK가 환경마다 다른 파일을 사용하는데, 5개 환경(localdev/dev/alpha/stage/release)의 SDK 파일이 모두 번들 결과물에 포함되는 문제가 있었다. 배포 시 필요없는 파일들이 같이 나가는 것도 문제지만, 파일 크기도 상당했다.

Vite 플러그인을 직접 작성해서 빌드 완료 후 현재 환경 외의 SDK 파일들을 삭제하도록 처리했다.

```ts
function wemixPlugin(): Plugin {
  let config: ResolvedConfig

  return {
    name: 'wemix-plugin',
    configResolved(_config) {
      config = _config
    },
    renderStart(outputOptions, inputOptions) {
      const modes = ['localdev', 'dev', 'alpha', 'stage', 'release']
      const wemixPrefix = 'wemix_'

      for (const mode of modes) {
        if (mode === config.mode) continue  // 현재 환경은 건너뜀
        const wemixPath = path.resolve(outputOptions.dir, wemixPrefix + mode + '.js')
        fs.rmSync(wemixPath)
      }
    },
  }
}
```

`renderStart` 훅은 번들 파일 생성이 시작될 때 호출된다. 여기서 현재 `mode`와 다른 환경 SDK 파일들을 `fs.rmSync`로 삭제한다.

---

## Node.js 폴리필 문제

wemix SDK 내부에서 Node.js 빌트인 모듈(`crypto`, `buffer` 등)을 사용하는 부분이 있어서, 브라우저 번들에서 이를 폴리필해줘야 했다.

```ts
import { nodePolyfills } from 'vite-plugin-node-polyfills'

plugins: [
  svelte(...),
  tsConfigPaths(),
  nodePolyfills(),   // wemix SDK가 Node.js API 사용
  wemixPlugin(),
]
```

Rollup 때도 비슷한 처리를 했지만 Vite 생태계에선 `vite-plugin-node-polyfills` 패키지로 해결했다.

---

## 정리

마이그레이션 자체는 하루 안에 끝났는데, 후처리(env prefix 전부 교체, CSS 경로 수정, wemix 플러그인 작성)가 더 시간이 걸렸다. 전환 후 개발 서버 기동 속도가 눈에 띄게 빨라졌고, 빌드 설정이 단일 파일(`vite.config.ts`)로 관리되어 훨씬 파악하기 쉬워졌다.

---

## 관련 문서

- [wemix 지갑 연동](./wemix-wallet-integration.md)
