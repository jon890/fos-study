# npm vs pnpm — 어떤 기준으로 선택했나

pnpm이 성능이 좋다는 건 누구나 안다. 그런데 단순히 "더 빨라서 좋다"가 선택의 충분한 이유가 되진 않는다. 이미 잘 굴러가는 npm 프로젝트를 굳이 옮길 필요는 없으니까. 내가 fos-blog(이 블로그를 돌리는 Next.js 프로젝트)를 시작할 때 pnpm을 고른 이유와, 그 후 운영하면서 실제로 도움이 됐던 부분을 정리해둔다.

## 선택 기준

### 의존성 관리 방식과 재현성

lockfile이 팀 전체(또는 본인의 여러 환경에서) **같은 트리를 재현해주는지**가 가장 중요하다.

이전에 npm을 쓸 때는 같은 `package-lock.json`을 두고도 환경마다 `npm install` 결과가 미묘하게 달랐다. 회사 PC와 개인 노트북에서 같은 브랜치를 받아도 한쪽에서만 빌드가 깨지는 일이 종종 있었고, 그때마다 `node_modules` 폴더를 통째로 지우고 `npm cache clean --force` 후 재설치하는 식으로 풀었다. 매번 같은 의식을 반복하는 게 비합리적이라고 느꼈다.

pnpm으로 바꾼 뒤로는 그 사이클이 거의 없어졌다. 같은 `pnpm-lock.yaml`로는 어느 환경에서 풀어도 같은 트리가 나왔다. lockfile 자체가 **content-addressable**이라 패키지 무결성을 해시로 보장하는 구조가 도움이 됐다.

### 유령 의존성(phantom dependency)을 못 쓰게 하는 엄격함

npm의 기본 hoisting은 의존성 트리를 평평하게 만들어 `node_modules` 최상위에 모든 패키지를 끌어올린다. 그래서 `package.json`에 직접 명시하지 않은 패키지를 `import`해도 동작한다. 처음에는 편하지만, 나중에 그 패키지의 직접 의존이 빠지면 갑자기 빌드가 깨진다.

pnpm은 `node_modules/<pkg>` 안에 그 패키지가 직접 의존하는 것만 두는 구조라, **package.json에 적어두지 않은 패키지는 import할 수 없다**. fos-blog에서도 이 동작 덕에 "어디서 들어왔는지 모르는 import"가 코드 리뷰에 올라오는 일이 거의 없다. 처음에 pnpm으로 시작한 게 후반에 큰 정리 비용을 절약해줬다.

### 설치 성능과 디스크 효율

pnpm은 **content-addressable store**(`~/.pnpm-store`)에 패키지를 한 번만 받아두고 프로젝트마다 하드링크로 연결한다. 효과는 두 가지다.

- 같은 패키지를 여러 프로젝트에서 받으면 디스크에 한 벌만 존재
- CI에서 캐시 적중률이 좋으면 설치가 눈에 띄게 빨라짐

체감상 fos-blog의 GitHub Actions에서 pnpm 캐시가 들어맞을 때 npm 대비 절반 가까이 줄었다. 모노레포가 아니더라도 CI를 자주 돌리는 프로젝트라면 시간 절감이 의미 있다.

### 호환성 리스크 — 모든 툴이 평평한 구조를 안다고 가정함

가장 큰 함정. 일부 도구(번들러, 테스트 러너, 일부 CLI)가 `node_modules`의 hoisted 구조를 은근히 가정해서, pnpm의 엄격한 트리에서 깨지는 경우가 있다. 가장 흔한 케이스는 "패키지 A가 의존하는 B를 우리 코드에서 직접 import하던" 패턴이다.

대응은 두 가지였다.

- 직접 의존이 필요한 패키지는 **`package.json`에 명시적으로 추가**해서 더 이상 phantom dependency가 아니게 만든다 (정공법)
- 어쩔 수 없이 hoist가 필요한 라이브러리는 `.npmrc`에 `public-hoist-pattern`을 지정해 일부만 hoist (절충)

fos-blog에서는 거의 1번 방식으로 풀었다. 한 번 정리해두면 그 후에는 새 의존성 추가 시 어디에 뭘 넣어야 하는지가 명확하다.

## 그래서 어떻게 결정했나

fos-blog는 **단일 Next.js 프로젝트**(모노레포 아님)인데도 pnpm을 골랐다. 이유를 정리하면:

- 환경 간 재현성을 lockfile 레벨에서 강하게 보장하고 싶음
- 처음부터 phantom dependency를 못 쓰게 묶어두면 후반 정리 비용이 적음
- CI가 자주 돌아 설치 시간 절감이 누적 효과로 큼

반대로 **이미 잘 굴러가는 npm 프로젝트라면** 강제로 옮길 필요는 없다고 본다. 옮기는 비용(host 호환성 검증, lockfile 재생성, CI 캐시 재구성)이 작지 않고, 그 보상이 신규 프로젝트만큼 크지 않다.

yarn은 어떤가 — yarn classic은 npm과 비슷한 hoisting이라 pnpm 대비 변별점이 약하고, yarn berry(PnP)는 hoisted를 가정하는 도구와의 충돌 비용이 pnpm보다 더 크다고 본다. pnpm이 "엄격함의 이득"과 "생태계 호환성"의 균형이 좋아서 결국 pnpm으로 갔다.

## 참고

- [pnpm Motivation — phantom dependencies, NPM doppelgangers](https://pnpm.io/motivation)
- [pnpm `.npmrc` — public-hoist-pattern](https://pnpm.io/npmrc#public-hoist-pattern)
