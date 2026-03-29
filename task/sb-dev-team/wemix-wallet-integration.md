# wemix 블록체인 지갑 연동

**진행 기간**: 2023.04 ~ 2024.03

서비스 내 보상을 블록체인 토큰(BYLO)으로 지급하는 구조가 있었다. 유저가 wemix 지갑을 연결하고, 보상을 수령할 때 지갑 서명을 통해 실제 토큰이 지급되는 방식이다. wemix SDK 연동과 환경별 빌드 처리에서 겪은 내용을 정리한다.

---

## wemix란

wemix는 국내 게임사에서 만든 블록체인 플랫폼이다. 지갑 앱(wemix wallet)을 통해 QR 코드를 스캔하거나 딥링크로 트랜잭션에 서명하는 방식으로 토큰을 전송한다. 일반적인 이더리움 계열 지갑 연동과 유사하지만 전용 SDK를 사용한다.

---

## 백엔드: prepare / token 엔드포인트

```java
@RequestMapping("/v1/wemix")
@RestController
public class WemixController {

    @PostMapping("/common/prepare")
    public PrepareResponse prepare(@RequestBody Map req) throws Exception {
        String type = (String) req.get("type");
        String data = (String) req.get("data");
        return wemixService.prepare(type, data);
    }

    @PostMapping("/common/token")
    public TokenResponse token(@RequestBody Map data) throws Exception {
        String code = (String) data.get("code");
        return wemixService.token(code);
    }
}
```

`PrepareResponse`와 `TokenResponse`는 내부 wemix SDK(`tornado` 라이브러리)에서 제공하는 타입이다.

- `/common/prepare`: 어떤 트랜잭션을 서명할지 정의하고, 지갑 앱에서 보여줄 QR 데이터를 생성
- `/common/token`: 유저가 지갑 앱에서 서명 완료 후 돌아오는 auth code를 토큰으로 교환

백엔드에서는 이 두 엔드포인트를 wemix SDK에 위임하는 얇은 래퍼 역할이다. 비즈니스 로직(어떤 클레임을 처리할지)은 `WemixService` 내부에서 처리한다.

wemix 지갑 주소는 유저 계정과 연결되어 있고, 주소가 없으면 일부 기능(토큰 보상 수령)이 제한된다.

```java
// 지갑 연결 여부 확인
.hasWallet(StringUtils.isNotEmpty(user.getAddress()))
```

---

## 프론트엔드: SDK 연동과 환경별 분리

wemix SDK는 환경(dev/alpha/stage/release)마다 다른 파일을 사용한다. 개발 환경 SDK로 프로덕션 트랜잭션을 보내면 안 되기 때문이다.

처음에는 환경별 SDK 파일 5개가 빌드 결과물에 모두 포함되는 문제가 있었다. 배포 시 불필요한 파일이 나가는 것도 문제지만, 환경이 섞일 위험도 있었다.

Vite 플러그인을 직접 작성해서 빌드 완료 후 현재 환경 외의 SDK 파일을 삭제한다.

```ts
function wemixPlugin(): Plugin {
  let config: ResolvedConfig

  return {
    name: 'wemix-plugin',
    configResolved(_config) {
      config = _config
    },
    renderStart(outputOptions) {
      const modes = ['localdev', 'dev', 'alpha', 'stage', 'release']

      for (const mode of modes) {
        if (mode === config.mode) continue   // 현재 환경은 유지
        const wemixPath = path.resolve(
          outputOptions.dir,
          `wemix_${mode}.js`
        )
        fs.rmSync(wemixPath)
      }
    },
  }
}
```

`vite build --mode alpha`로 빌드하면 `wemix_alpha.js`만 남고 나머지는 삭제된다.

### Node.js 폴리필

wemix SDK 내부에서 Node.js 빌트인 모듈(crypto, buffer 등)을 사용한다. 브라우저 환경에서는 이 모듈이 없어서 폴리필이 필요했다.

```ts
import { nodePolyfills } from 'vite-plugin-node-polyfills'

plugins: [
  svelte(...),
  nodePolyfills(),   // wemix SDK 의존성 처리
  wemixPlugin(),
]
```

---

## 클레임 플로우 연동

실제 토큰 지급은 단순한 API 호출이 아니라 블록체인 서명이 필요하다. 추천 미션 보상 수령 흐름이 이를 잘 보여준다.

```
1. 클레임 생성 요청 (백엔드)
   → ByloClaim 레코드 생성 (claimDate = null)
   → claimId 반환

2. QR 서명 (프론트 ↔ wemix 지갑 앱)
   → claimId로 /v1/wemix/common/prepare 호출
   → PrepareResponse의 QR 데이터로 지갑 앱 실행
   → 유저가 지갑 앱에서 트랜잭션 서명

3. 클레임 완료 (백엔드)
   → byloClaim.claimDate 채워진 것 확인
   → 미션 완료 처리
```

2단계에서 유저가 지갑 앱을 열어 직접 확인하고 서명하는 과정이 들어간다. 서명 없이는 토큰이 지급되지 않는 구조다. 지갑을 연결하지 않은 유저는 3단계를 진행할 수 없어서, 보상 수령 전에 지갑 연결 여부를 체크한다.

```java
// 지갑 주소 없으면 예외
UserAccount userAccount = userService.getUserAccountWithAddress(mbrNo);
```

---

## wemix SDK 버전 변경 대응

개발 기간 중 wemix 플랫폼이 3.0으로 업그레이드되면서 SDK 변경이 있었다. BYLO 토큰 보유량 조회 방식이 바뀐 것과 SDK 환경 변수 구조가 바뀐 것 두 가지를 대응했다.

```
// wemix 3.0 대응 - BYLO 보유 토큰 조회 변경 (#98)
// wemix sdk env 변경 대응 (#841)
```

SDK 버전이 올라갈 때마다 프론트엔드 SDK 파일과 백엔드 라이브러리를 같이 업그레이드해야 했다. 버전 관리가 번거로웠는데, 이후에는 SDK 버전을 환경 변수로 분리해서 파일만 교체하면 되도록 개선했다.

---

## 관련 문서

- [Vite 마이그레이션](./vite-migration.md)
- [추천 프로그램 시스템](./referral-program.md)
