# 블록체인 입출금 시스템 구현기

**진행 기간**: 2022.09 ~ 2022.10
**소속**: 더퓨쳐컴퍼니

---

## 무엇을 만들었나

게임 내 블록체인 자산의 **입금/출금 처리 시스템**이다. 서비스의 주력 코인은 **Solana(SOL)** 이며, BTC·ETH·USDT도 함께 지원했다.

사용자가 외부 지갑에서 게임 계정으로 코인을 보내거나, 반대로 게임 자산을 외부로 출금하는 흐름 전체를 NestJS 데몬 서비스가 처리한다. 입금은 블록체인을 주기적으로 폴링해서 감지하고, 출금은 요청을 DB에 쌓아두고 배치로 처리하는 방식이다.

---

## 핵심 흐름

```
유저 가입
  └── 유저 전용 입금 주소 발급 (코인별 1개)

입금 흐름
  └── 데몬: 주기적으로 블록체인 API 폴링 (Solana → Alchemy, BTC/ETH → CryptoAPIs)
        └── 플랫폼 지갑 또는 유저 주소의 트랜잭션 조회
              └── 수신 주소 → 유저 매핑
                    └── 이미 처리된 시그니처(txId)인지 확인 (멱등성)
                          └── 신규이면 유저 잔액 증가 + 입금 이력 저장

출금 흐름
  └── 유저 출금 요청 → Pending 상태로 DB 저장
        └── 데몬: 주기적으로 Pending 출금 조회
              └── 블록체인 API로 실제 전송
                    └── txId(signature) 저장, 상태 Complete/Failed 갱신
```

---

## 1. 유저별 전용 입금 주소 발급

유저마다 **코인별 전용 입금 주소**를 하나씩 발급한다. 공용 주소를 쓰면 누가 보냈는지 구분할 수 없기 때문이다.

```
유저 A → SOL 입금 주소: AbCD...XyZ  /  BTC 입금 주소: bc1q...
유저 B → SOL 입금 주소: EfGH...WvU  /  BTC 입금 주소: bc1p...
```

Solana는 각 유저에게 독립된 keypair에서 파생된 주소를 발급한다. BTC·ETH는 HD Wallet(`m/44'/0'/0'/0/N`) 경로에서 인덱스 N을 늘려가며 주소를 파생시킨다. 어느 방식이든 플랫폼이 발급된 주소와 유저를 DB에서 매핑해두는 것이 핵심이다.

```typescript
interface UserWallet {
  userId: string;
  symbol: 'SOL' | 'BTC' | 'ETH' | 'USDT';
  depositAddress: string;  // 유저 전용 입금 주소
  balance: Decimal;
}
```

---

## 2. Solana 입금 감지 — Alchemy로 트랜잭션 추적

Solana 트랜잭션 추적에는 **Alchemy**를 사용했다. Alchemy는 Solana RPC 노드를 직접 운영하지 않아도 REST/WebSocket API로 블록체인 데이터를 조회할 수 있는 서비스다.

### 주소별 트랜잭션 시그니처 조회

Solana에서 트랜잭션을 추적하는 기본 패턴은 `getSignaturesForAddress`다. 특정 주소에 관련된 트랜잭션 시그니처 목록을 최신순으로 반환한다.

```typescript
// Alchemy Solana API: 주소에 연관된 트랜잭션 시그니처 목록 조회
const response = await alchemy.core.getSignaturesForAddress(
  depositAddress,
  { limit: 50 }
);
// response: [{ signature, slot, blockTime, confirmationStatus, ... }, ...]
```

시그니처 목록을 받은 뒤, 각 시그니처로 트랜잭션 상세 내용을 조회한다.

```typescript
const tx = await alchemy.core.getTransaction(signature);
```

### 입금액 계산 — 잔액 변화로 판단

SOL 입금은 트랜잭션의 **preBalances / postBalances** 차이로 계산한다. Solana 트랜잭션에는 변경된 모든 계정의 전후 잔액이 포함되어 있어서, 특정 주소의 잔액이 얼마나 늘었는지 직접 계산할 수 있다.

```typescript
function extractSolDeposit(tx: SolanaTransaction, depositAddress: string): Decimal | null {
  const accountIndex = tx.transaction.message.accountKeys
    .findIndex(key => key.toString() === depositAddress);

  if (accountIndex === -1) return null;

  const pre = tx.meta.preBalances[accountIndex];   // lamports
  const post = tx.meta.postBalances[accountIndex]; // lamports
  const diff = post - pre;

  if (diff <= 0) return null;  // 입금이 아닌 경우
  return new Decimal(diff).dividedBy(1e9);  // lamports → SOL
}
```

### SPL 토큰(USDT-SPL 등) 처리

SOL 네이티브 코인이 아닌 SPL 토큰(Solana의 ERC-20 격)은 `preTokenBalances / postTokenBalances`에서 읽는다.

```typescript
function extractSplDeposit(tx: SolanaTransaction, depositAddress: string, mint: string) {
  const pre = tx.meta.preTokenBalances
    .find(b => b.owner === depositAddress && b.mint === mint);
  const post = tx.meta.postTokenBalances
    .find(b => b.owner === depositAddress && b.mint === mint);

  const preAmount = new Decimal(pre?.uiTokenAmount.uiAmountString ?? '0');
  const postAmount = new Decimal(post?.uiTokenAmount.uiAmountString ?? '0');
  const diff = postAmount.minus(preAmount);

  return diff.greaterThan(0) ? diff : null;
}
```

---

## 3. 데몬 서비스 — 코인별 폴링 스케줄러

NestJS `@Cron`으로 코인마다 독립된 스케줄러를 돌린다. 인터벌을 다르게 설정해 API 요청이 동시에 몰리지 않도록 한다.

```typescript
@Injectable()
export class DepositScheduler {
  @Cron('0 */5 * * * *')   // 5분마다 — 메인 코인
  async detectSolDeposits() { ... }

  @Cron('0 */7 * * * *')   // 7분마다
  async detectBitcoinDeposits() { ... }

  @Cron('0 */8 * * * *')   // 8분마다
  async detectEthereumDeposits() { ... }

  @Cron('0 */9 * * * *')   // 9분마다
  async detectUsdtDeposits() { ... }
}
```

각 스케줄러는 유저 지갑 주소 목록을 DB에서 읽어, 각 주소에 대해 최신 트랜잭션을 조회하고 입금 여부를 판단한다.

```typescript
async processAllSolDeposits() {
  const wallets = await this.userWalletRepo.findAllBySymbol('SOL');

  for (const wallet of wallets) {
    const signatures = await alchemy.core.getSignaturesForAddress(
      wallet.depositAddress,
      { limit: 50 }
    );

    for (const { signature } of signatures) {
      await this.handleSolDeposit(wallet, signature);
    }
  }
}
```

---

## 4. 멱등성 보장 — 같은 트랜잭션을 두 번 처리하지 않는다

폴링 방식의 가장 큰 위험은 **같은 트랜잭션을 중복 처리**하는 것이다. Solana의 트랜잭션 식별자는 **시그니처(signature)** 다. 이 값을 이미 처리된 입금 이력에서 확인해 중복을 막는다.

```typescript
async handleSolDeposit(wallet: UserWallet, signature: string): Promise<void> {
  // 이미 처리된 시그니처인지 확인
  const exists = await this.depositRepo.existsBySignatureAndWallet(
    signature, wallet.id
  );
  if (exists) return;

  const tx = await alchemy.core.getTransaction(signature);
  if (!tx || tx.meta?.err) return;  // 실패한 트랜잭션 스킵

  const amount = extractSolDeposit(tx, wallet.depositAddress);
  if (!amount) return;  // 이 주소로 들어온 금액이 없으면 스킵

  // 잔액 증가 + 입금 이력 저장 (DB 트랜잭션으로 묶음)
  await this.dataSource.transaction(async manager => {
    wallet.balance = wallet.balance.plus(amount);
    await manager.save(wallet);
    await manager.save(new Deposit({ wallet, amount, signature, txTimestamp: tx.blockTime }));
  });
}
```

Solana 시그니처는 전 세계적으로 유일하기 때문에, `signature + walletId` 조합으로 충분한 멱등성 키가 된다.

---

## 5. 출금 처리

출금은 **요청과 실행을 분리**한다. 유저가 출금 요청을 하면 즉시 블록체인에 전송하지 않고 `Pending` 상태로 DB에 저장한다. 데몬이 주기적으로 Pending 건을 가져와 실제 전송을 처리한다.

```
출금 요청 API
  └── 잔액 차감 + Withdrawal(status=Pending) 저장

출금 데몬 (@Cron 30분마다)
  └── status=Pending인 Withdrawal 조회
        └── Alchemy (SOL) / CryptoAPIs (BTC·ETH)로 전송 요청
              ├── 성공: signature(txId) 저장, status=Complete
              └── 실패: status=Failed, 잔액 환불
```

요청과 실행을 분리하면 블록체인 API 장애 시 요청이 유실되지 않고, 실패한 건을 재처리하거나 관리자가 개입할 수 있다.

---

## 배운 것

### Solana 트랜잭션 구조는 EVM 계열과 다르다

ETH 트랜잭션은 `from → to`의 단순한 구조다. Solana는 하나의 트랜잭션이 여러 계정의 잔액을 동시에 변경할 수 있고, 토큰 전송은 별도의 `Token Program` 명령으로 처리된다. 처음에는 어디서 입금액을 읽어야 할지 파악하는 데 시간이 걸렸고, `preBalances / postBalances` 차이를 계산하는 방식으로 해결했다.

### Alchemy 덕분에 노드 운영 없이 Solana 데이터를 다룰 수 있었다

Solana 노드를 직접 운영하면 고성능 서버와 고속 SSD가 필요하고 운영 복잡도가 높다. Alchemy의 Solana API를 사용하면 `getSignaturesForAddress`, `getTransaction` 같은 RPC 메서드를 REST로 호출할 수 있어서 인프라 부담 없이 개발에 집중할 수 있었다.

### 블록체인 입금은 "이벤트 수신"이 아니라 "폴링"으로 구현했다

웹훅으로 트랜잭션 알림을 받는 방식도 있지만, 웹훅은 전달 실패 시 유실 위험이 있다. 폴링 방식은 느리지만 **데몬이 살아있는 한 반드시 처리된다**는 신뢰성이 있다. 입금 누락이 서비스 신뢰에 직결되는 도메인에서는 이 트레이드오프가 중요하다.

### 멱등성이 가장 중요한 설계 원칙이다

폴링 간격마다 같은 트랜잭션이 반복 조회된다. Solana 시그니처를 고유 키로 사용해 중복 처리를 막지 않으면 유저 잔액이 무한정 늘어날 수 있다. 금융 도메인에서 멱등성은 선택이 아닌 필수다.

### 요청과 실행을 분리하면 장애에 강해진다

출금을 즉시 처리하지 않고 DB에 Pending 상태로 저장하면, 블록체인 API 장애나 네트워크 오류 시 요청이 유실되지 않는다. 재처리, 관리자 개입, 감사 로그 모두 이 구조에서 자연스럽게 따라온다.

---

## 기술 스택

`NestJS` `TypeScript` `TypeORM` `PostgreSQL` `Alchemy` (Solana RPC) `CryptoAPIs` (BTC·ETH) `@nestjs/schedule`
