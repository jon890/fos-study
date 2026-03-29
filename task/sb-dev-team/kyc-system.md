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

### 암호화

파일 경로를 포함한 민감 정보는 DB에 저장 시 암호화했다. `CryptService`를 별도로 구성해서 저장/조회 시 자동으로 처리하도록 했다. 어드민에서 파일을 조회할 때는 암호화된 경로를 복호화한 뒤 Azure Blob에서 읽어온다.

```java
// admin-v2: KYC 반려 시 파일 제거
// KYC 경로가 암호화되어 있으므로 복호화 후 삭제
// :bug: KYC 반려 시, 파일 제거할 때 복호화 후 진행하도록 (#77)
```

이 부분에서 버그가 있었다. 반려 처리 시 파일을 삭제하는 로직에서 암호화된 경로를 그대로 Azure에 넘기고 있었다. 복호화 단계가 빠져있던 것.

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

## 관련 문서

- [Spring Batch @StepScope 정리](../../java/spring-batch/step-scope.md)
