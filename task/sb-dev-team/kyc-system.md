# KYC 시스템 구현

**진행 기간**: 2023.03 ~ 2023.12

스포츠 베팅 서비스에서 KYC(Know Your Customer, 본인 인증) 기능을 구현했다. 신분증 이미지를 안전하게 저장하고, 어드민에서 승인/반려 처리하며, 법적 보존 기간이 지난 데이터를 자동 삭제하는 전체 흐름이다.

---

## 아키텍처

KYC는 민감한 개인 정보(신분증 이미지, 개인 식별 정보)를 다루기 때문에 별도 서버로 분리했다. 메인 백엔드와 어드민 백엔드가 KYC 서버를 통해서만 파일에 접근하는 구조다.

```
사용자 ──▶ kyc-server (NestJS) ──▶ Azure Blob Storage
                  │                        │
                  ▼                        │
            KYC DB (Prisma)               │
                                           │
어드민 ──▶ admin-v2 (Spring Boot) ──────▶ 복호화 후 조회
                  │
                  ▼
           메인 DB (승인/반려 상태)
```

kyc-server는 NestJS + TypeScript로 구현했고, 메인 백엔드와 다른 스택이다. 당시에 PII 격리 목적으로 별도 서비스를 두는 방향으로 결정이 났고, 내가 kyc-server와 어드민 백엔드의 KYC 관련 부분을 맡았다.

---

## kyc-server: 파일 업로드

신분증 이미지를 받아 Azure Blob Storage에 저장한다. 파일명은 날짜 + UUID 조합으로 생성해서 유추가 불가능하게 했다.

```typescript
@Injectable()
export class BlobStorageService {
  private kycContainer: ContainerClient;

  async upload(data: HttpRequestBody, contentLength: number) {
    const now = dayjs().format('YYYY-MM-DD');
    const blobName = `${now}/${randomUUID()}`;
    const blockBlockClient = this.kycContainer.getBlockBlobClient(blobName);

    const uploadBlobResponse = await blockBlockClient.upload(data, contentLength);
    return blobName;  // DB에 저장할 경로
  }
}
```

파일 업로드 후 반환된 `blobName`을 KYC DB에 저장한다. 실제 파일은 Azure에만 있고, DB에는 경로만 기록된다.

### AES-256-GCM 암호화 모듈

파일 경로, 개인 식별 정보 같은 DB 필드는 저장 시 암호화했다. 초기엔 간단한 대칭 암호 라이브러리를 쓸까 했는데, 결국 `node:crypto` 기반으로 직접 `CryptService`를 구성했다. 외부 의존이 줄어들고, 내부적으로 같은 패턴이 여러 서비스에 재사용될 여지가 있어서다.

핵심은 **IV와 salt를 매 호출마다 새로 생성**하는 것이다. 같은 평문이 항상 다른 암호문으로 나오게 해서 패턴 유추를 막는다.

```typescript
// src/crypt/crypt.service.ts
@Injectable()
export class CryptService {
  private readonly MASTER_KEY: string;
  private IV_LENGTH = 16;
  private SALT_LENGTH = 64;

  constructor(private readonly configService: ConfigService) {
    this.MASTER_KEY = configService.getOrThrow<string>('ENCRYPTION_MASTER_KEY');
  }

  encrypt(text: string) {
    const iv = crypto.randomBytes(this.IV_LENGTH);
    const salt = crypto.randomBytes(this.SALT_LENGTH);

    // MASTER_KEY + salt → 32byte key 파생 (PBKDF2)
    const key = crypto.pbkdf2Sync(this.MASTER_KEY, salt, 2145, 32, 'sha512');
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);

    const encrypted = Buffer.concat([cipher.update(text, 'utf-8'), cipher.final()]);
    const tag = cipher.getAuthTag();

    // salt + iv + tag + encrypted 를 하나의 base64 문자열로
    return Buffer.concat([salt, iv, tag, encrypted]).toString('base64');
  }
}
```

결과 포맷이 `[salt(64) | iv(16) | tag(16) | ciphertext]`로 한 덩어리라, DB에는 컬럼 하나만 잡으면 된다. 복호화 시 같은 순서로 잘라서 복원한다.

PBKDF2 iteration을 2145로 둔 이유는 코드 주석에 남겨뒀다 — MASTER_KEY 자체가 이미 암호학적으로 강한 키라면 password 기반처럼 수만 번 돌릴 이유가 없다. KDF 비용이 요청당 암·복호화 레이턴시에 직결되니 불필요하게 높이지 말 것. (사용자가 입력한 password를 돌리는 경우는 10만 회 이상이 기본)

GCM 모드는 auth tag를 함께 저장해야 복호화 시 무결성 검증이 된다. CBC만 쓰다가 GCM으로 넘어올 때 이 부분을 빼먹으면 "복호화는 되는데 변조 감지가 안 되는" 반쪽짜리 상태가 된다.

> **인사이트.** 암호화 스펙을 택할 때 **알고리즘 선택(AES-GCM)**과 **부가 데이터 저장 위치**(auth tag, salt, iv)는 하나의 결정으로 묶여야 한다. 알고리즘만 보고 auth tag를 빠뜨리면 보안이 형식만 갖춘 상태가 된다.

### 객체 단위 암·복호화 유틸

필드 단위로 매번 `encrypt()`를 호출하는 건 누락되기 쉬워서 객체 단위 유틸을 뒀다.

```typescript
encryptObject(object: { [key: string]: unknown }, exclude?: string[]) {
  const encrypted: { [key: string]: unknown } = {};
  Object.entries(object).forEach(([k, v]) => {
    if (!exclude?.includes(k)) {
      encrypted[k] = this.encrypt(v.toString());
    } else {
      encrypted[k] = v;   // seq, regDate 같은 비민감 필드는 평문 유지
    }
  });
  return encrypted;
}
```

`exclude`로 비민감 필드(seq, 날짜, 상태 플래그)를 넘기면 그것만 평문으로 통과된다. 새 필드 추가 시 기본이 "암호화"가 되니, 실수로 평문 저장되는 경로가 막힌다.

### 복호화 누락 버그

반려 처리 시 Azure Blob에서 파일을 삭제하는 로직에서 암호화된 경로를 그대로 Azure에 넘기고 있었다. Blob SDK는 "존재하지 않는 경로"를 조용히 처리하는 경우가 있어서 한참 못 잡았다. 

> **인사이트 3.** "평문/암호문이 섞인 동일 필드"는 언제든 이런 버그를 만든다. 설계 단계에서 **암호문은 레포지토리 레이어에서만 머물고, 서비스 레이어는 항상 평문만 본다**는 규칙을 그었어야 했다. 경로 값이 서비스 전체를 암호문 상태로 돌아다니다 보니 어떤 지점에서 복호화가 필요한지 매번 체크해야 했다.

---

## 어드민: 승인/반려

어드민 백엔드(Spring Boot)에서 KYC 데이터를 조회하고 승인/반려 처리한다.

주요 기능:
- KYC 목록 조회 (상태별 필터링)
- KYC 상세 조회 (이미지 포함)
- 승인/반려 처리 (단건, 다건)
- 재인증 요청

승인/반려를 다건으로 처리하는 기능도 넣었다. 처음에는 단건만 있었는데 어드민 쪽에서 목록에서 체크박스로 여러 건을 한 번에 처리하고 싶다는 요청이 있어서 추가했다.

```java
// 여러 건을 동시에 승인, 반려할 수 있도록 구조를 변경했습니다. (#55)
```

반려 시에는 사유를 입력받는다. `reason`(주 사유)과 `additionalReason`(추가 설명)을 분리해서 저장한다.

승인/반려 상태가 변경되면 시스템 알림이 발송된다.

---

## Spring Batch: KYC 데이터 6개월 후 자동 삭제

신분증 이미지는 법적으로 정해진 보존 기간 이후에 반드시 삭제해야 한다. 이걸 Spring Batch Job으로 처리했다.

```java
// 6개월 이상 보관된 KYC 상세 정보를 제거하는 Job을 추가했습니다. (#48)
```

Job 흐름:
1. KYC DB에서 6개월 이상 된 레코드 조회
2. 각 레코드의 blob 경로를 복호화
3. Azure Blob Storage에서 파일 삭제
4. KYC DB에서 상세 정보 레코드 삭제

Blob 삭제와 DB 삭제를 같이 처리하는 게 트랜잭션으로 묶이지 않아서 순서가 중요했다. Blob을 먼저 삭제하고 DB를 지우는 방향으로 했다. Blob 삭제가 실패하면 재시도할 수 있도록.

---

## 두 개의 DB

KYC 데이터는 메인 DB와 별도 KYC 전용 DB에 저장된다. Spring Boot에서 멀티 DataSource를 설정해서 메인과 KYC DB를 분리해서 접근했다.

```java
// KyC DB 설정
@Configuration
public class KycConfiguration {
    // KYC 전용 DataSource, TransactionManager 설정
}
```

kyc-server에서는 Prisma ORM을 사용해 두 개 DB(`common-prisma.service.ts`, `kyc-prisma.service.ts`)를 각각 관리했다.

---

## 환경별 운영 구성 — Logger 전략 + CORS

KYC 서버는 dev / alpha / stage / release 네 개 환경으로 배포됐다. 환경마다 로깅 요구가 달랐고(stage는 컨테이너 stdout만, release는 파일 + 일일 로테이션), CORS도 환경마다 허용 origin이 다르다. 이걸 `if (profile === 'stage')` 식으로 뿌리면 환경 추가 시 매번 코드를 뒤져야 하니, 시작점부터 분리했다.

### Winston Logger — 프로파일별 전략 패턴

로거 옵션은 프로파일별 클래스로 분리했다.

```typescript
// src/common/get-logger-options.ts
type ProfileType = 'dev' | 'alpha' | 'stage' | 'release';

class LoggerOptionsFactory {
  static getInstance(profile: ProfileType) {
    switch (profile) {
      case 'dev':     return new DevLoggerOption();
      case 'alpha':   return new AlphaLoggerOption();
      case 'stage':   return new StageLoggerOption();
      case 'release': return new ReleaseLoggerOption();
      default: throw new Error(`Illegal Profile ===> ${profile}`);
    }
  }
}

class StageLoggerOption extends LoggerOption {
  get(): WinstonModuleOptions {
    return { transports: [getConsoleLogOption()] };   // 컨테이너 stdout만
  }
}

class ReleaseLoggerOption extends LoggerOption {
  get(): WinstonModuleOptions {
    return { transports: [getConsoleLogOption(), getFileLogOption()] };   // 파일 + stdout
  }
}
```

`getFileLogOption`은 `winston-daily-rotate-file`로 날짜별 로그 파일을 생성한다. handleExceptions를 켜서 uncaught exception도 같이 떨어지게 했다. 프로파일을 `if/else`로 분기하지 않고 Factory + 클래스로 쪼갠 이유는 단순히 취향이 아니라 **각 환경 정책을 한 파일에서 완결시키기 위해서**였다. 나중에 "이 환경에선 뭐가 달랐지?"를 추적할 때 그 환경의 클래스 하나만 읽으면 된다.

### CORS — 환경변수 기반 origin 주입

허용 origin은 코드에 하드코딩하지 않고 `CORS_ALLOW_ORIGIN` 환경변수를 콤마 split해서 넘겼다.

```typescript
// src/main.ts
app.enableCors({
  allowedHeaders: [
    'Accept', 'Content-Type', 'Referer', 'User-Agent',
    'Authorization', 'X-Requested-With', 'X-Timezone-Offset',
  ],
  methods: ['POST', 'OPTIONS'],
  origin: process.env.CORS_ALLOW_ORIGIN
    ? process.env.CORS_ALLOW_ORIGIN.split(',')
    : '',
  preflightContinue: false,
  optionsSuccessStatus: 204,
});
```

- **origin은 env로, 허용 헤더는 코드로**. origin은 환경별로 빈번히 달라지지만, 허용 헤더 목록은 앱 요구에 따라 정해지는 불변이다. 변동 축(config)과 고정 축(코드)을 구분해서 배치했다.
- **methods는 POST/OPTIONS만**. KYC 서버는 내부 API 엔드포인트라 GET/PUT/DELETE가 필요 없었다. 명시적으로 좁혀 공격 표면을 줄였다.
- `preflightContinue: false`로 브라우저 preflight 요청이 핸들러 체인까지 내려가지 않도록.

---

## 협업

KYC는 PII를 다루는 기능이라 관여한 팀이 많았다. 백엔드 메인 서비스와 어드민 백엔드 양쪽이 `kyc-server`를 **파일 접근의 단일 창구**로 쓰도록 계약했고, 승인/반려 정책은 운영팀과 같이 정했다. 다건 승인/반려 같은 어드민 UX 요구는 운영팀이 실제로 쓰면서 올린 피드백을 받아 추가한 것이다. 보안 리뷰에서 받은 지적 중 기억에 남는 건 **"암호화 키가 env에 직접 있는 것이 CI/CD 파이프라인의 실수에 취약하다"**였는데, 당시엔 배포 단계 시크릿 관리 프로세스로 마무리했다. 이 피드백이 아래 "지금 보면"의 KMS 회고로 이어진다.

---

## 지금 보면

2023년 초 작업이라 지금이라면 몇 가지는 다르게 갔을 것이다.

- **MASTER_KEY 관리**: env에서 직접 읽는 대신 Azure Key Vault / AWS KMS에 위탁했을 것이다. env 파일에 마스터 키가 들어 있는 건 배포 실수에 취약하다.
- **암호화 경계**: 암호문이 서비스 전 레이어를 떠도는 패턴 대신, Repository 레이어에서만 처리되도록 Prisma middleware나 entity extension으로 묶었을 것이다. "복호화 누락 버그"가 같은 자리에서 다시 생길 여지가 없어진다.

반대로 잘 했다고 생각하는 건 **프로파일별 Logger를 전략 패턴으로 분리**한 부분이다. 당시엔 다소 과하다 싶었는데, 운영하면서 qa/performance 같은 추가 환경을 붙일 때 클래스 하나만 추가하면 돼서 부담이 적었다.

---

## 관련 문서

- [Ehcache 캐시 설계](./cache-architecture.md) — 메인 서비스의 멀티 인스턴스 캐시 정합성 패턴
