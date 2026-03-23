# 블록체인 입출금 시스템 구현기

**진행 기간**: 2022
**소속**: 더퓨쳐컴퍼니

---

## 무엇을 만들었나

게임 내 블록체인 자산(BTC, ETH, USDT 등)의 **입금/출금 처리 시스템**이다. 사용자가 외부 지갑에서 게임 내 계정으로 코인을 보내거나, 반대로 게임 자산을 외부로 출금하는 흐름을 처리한다.

NestJS로 구현한 **데몬(Daemon) 서비스**가 블록체인 트랜잭션을 주기적으로 추적하며, 플랫폼 지갑에 들어온 입금을 감지하면 해당 유저의 잔액을 증가시킨다.

---

## 핵심 흐름

```
유저 가입
  └── 유저 전용 입금 주소 발급 (HD Wallet 서브 주소)

입금 흐름
  └── 데몬: 주기적으로 블록체인 API 폴링
        └── 플랫폼 지갑의 incoming 트랜잭션 조회
              └── 수신 주소 → 유저 매핑
                    └── 이미 처리된 트랜잭션인지 확인 (멱등성)
                          └── 신규이면 유저 잔액 증가 + 입금 이력 저장

출금 흐름
  └── 유저 출금 요청 → Pending 상태로 DB 저장
        └── 데몬: 주기적으로 Pending 출금 조회
              └── 블록체인 API로 실제 전송 요청
                    └── txId 저장, 상태 Complete/Failed 갱신
```

---

## 1. 유저별 전용 입금 주소 발급

유저마다 **개별 입금 주소**를 발급한다. 공용 주소를 쓰면 누가 보냈는지 구분할 수 없기 때문이다.

**HD Wallet(Hierarchical Deterministic Wallet)** 구조를 활용한다. 마스터 키 하나에서 경로(`m/44'/0'/0'/0/N`)에 따라 사실상 무한히 많은 하위 주소를 파생시킬 수 있다. 블록체인 API 서비스(CryptoAPIs 등)가 이 주소 생성을 추상화해주기 때문에, 플랫폼은 발급된 주소를 DB에 저장하고 유저와 연결하면 된다.

```
유저 A → 입금 주소: 0xAAAA...
유저 B → 입금 주소: 0xBBBB...
유저 C → 입금 주소: 0xCCCC...

모두 플랫폼의 마스터 지갑 하위 주소
```

```typescript
// 유저 지갑 엔티티 (개념)
interface UserWallet {
  userId: string;
  symbol: 'BTC' | 'ETH' | 'USDT';
  depositAddress: string;  // 유저 전용 입금 주소
  balance: Decimal;
}
```

---

## 2. 데몬 서비스 — 트랜잭션 폴링

NestJS의 `@Cron` 스케줄러로 **주기적으로 블록체인 API를 폴링**한다. 코인마다 인터벌을 다르게 설정해 API 부하를 분산한다.

```typescript
@Injectable()
export class DepositScheduler {
  @Cron('0 */7 * * * *')   // 7분마다
  async detectBitcoinDeposits() { ... }

  @Cron('0 */8 * * * *')   // 8분마다
  async detectEthereumDeposits() { ... }

  @Cron('0 */9 * * * *')   // 9분마다
  async detectUsdtDeposits() { ... }
}
```

각 스케줄러는 블록체인 API에서 플랫폼 지갑의 트랜잭션 목록을 페이지 단위로 가져온다. `direction: "incoming"`인 트랜잭션만 필터링하고, 수신 주소로 유저를 조회해 잔액을 처리한다.

```typescript
async processDeposits(symbol: string) {
  let offset = 0;

  while (true) {
    const { items } = await blockchainApi.getWalletTransactions({
      walletId: PLATFORM_WALLET_ID,
      limit: 50,
      offset,
    });

    const incomings = items.filter(tx => tx.direction === 'incoming');
    let allAlreadyProcessed = true;

    for (const tx of incomings) {
      const isNew = await this.handleDeposit(symbol, tx);
      if (isNew) allAlreadyProcessed = false;
    }

    // 이 페이지의 트랜잭션이 전부 이미 처리됐으면 더 이상 조회 불필요
    if (allAlreadyProcessed) break;
    offset += 50;
  }
}
```

---

## 3. 멱등성 보장 — 같은 트랜잭션을 두 번 처리하지 않는다

폴링 방식의 가장 큰 위험은 **같은 트랜잭션을 중복 처리**하는 것이다. 서버 재시작, 오류 재시도, 페이지 범위 중복 등 다양한 상황에서 같은 트랜잭션이 두 번 들어올 수 있다.

이를 막기 위해 **트랜잭션 ID + 수신자 인덱스 + 지갑**의 조합을 고유 키로 사용한다.

```typescript
async handleDeposit(symbol: string, tx: Transaction): Promise<boolean> {
  const wallet = await this.userWalletRepo.findBySymbolAndAddress(
    symbol, tx.recipientAddress
  );
  if (!wallet) return false;  // 플랫폼 지갑 주소가 아니면 스킵

  // 이미 처리된 트랜잭션인지 확인
  const exists = await this.depositRepo.existsByTxIdAndIndexAndWallet(
    tx.txId, tx.recipientIndex, wallet.id
  );
  if (exists) return false;  // 중복 → 처리하지 않음

  // 잔액 증가 + 입금 이력 저장 (트랜잭션으로 묶음)
  await this.dataSource.transaction(async manager => {
    wallet.balance = wallet.balance.plus(tx.amount);
    await manager.save(wallet);
    await manager.save(Deposit.of(wallet, tx));
  });

  return true;  // 신규 처리됨
}
```

`(txId, recipientIndex, walletId)` 조합이 사실상 유니크 키 역할을 한다. 멀티 아웃풋 트랜잭션(한 tx에 수신자가 여러 명)도 `recipientIndex`로 구분할 수 있다.

---

## 4. USDT (ERC-20 토큰) 처리

네이티브 코인(BTC, ETH)과 ERC-20 토큰(USDT)은 트랜잭션 구조가 다르다. ETH 트랜잭션의 `recipients` 필드에서 금액을 읽는 대신, USDT는 `fungibleTokens` 필드(토큰 전송 이벤트)를 읽어야 한다.

```typescript
// ETH: recipients 배열에서 수신 주소와 금액 추출
for (const recipient of tx.recipients) {
  await this.handleDeposit('ETH', recipient.address, recipient.amount, tx);
}

// USDT: fungibleTokens 배열에서 USDT 이벤트만 필터링
for (const token of tx.fungibleTokens) {
  if (token.symbol !== 'USDT') continue;
  await this.handleDeposit('USDT', token.recipient, token.amount, tx);
}
```

---

## 5. 출금 처리

출금은 **요청과 실행을 분리**한다. 유저가 출금을 요청하면 즉시 블록체인에 전송하지 않고 `Pending` 상태로 DB에 저장한 뒤, 데몬이 주기적으로 Pending 건을 가져와 블록체인 API로 실제 전송을 처리한다.

```
출금 요청 API
  └── 잔액 차감 + Withdrawal(status=Pending) 저장

출금 데몬 (@Cron 30분마다)
  └── status=Pending인 Withdrawal 조회
        └── 블록체인 API로 전송 요청
              ├── 성공: txId 저장, status=Complete
              └── 실패: status=Failed, 잔액 환불
```

요청과 실행을 분리하면 블록체인 API 장애 시 요청이 유실되지 않고, 실패한 건을 재처리하거나 관리자가 개입할 수 있다.

---

## 배운 것

### 블록체인 입금은 "이벤트 수신"이 아니라 "폴링"으로 구현했다

웹훅(Webhook)으로 트랜잭션 알림을 받는 방식도 있지만, 웹훅은 전달 실패 시 유실 위험이 있다. 폴링 방식은 느리지만 **데몬이 살아있는 한 반드시 처리된다**는 신뢰성이 있다. 입금 누락이 서비스 신뢰에 직결되는 도메인에서는 이 트레이드오프가 중요하다.

### 멱등성이 가장 중요한 설계 원칙이다

폴링 간격마다 같은 트랜잭션이 반복해서 조회된다. `txId + recipientIndex + walletId` 조합으로 중복 처리를 막지 않으면 유저 잔액이 무한정 늘어날 수 있다. 금융 도메인에서 멱등성은 선택이 아닌 필수다.

### 블록체인 노드를 직접 운영하지 않아도 된다

BTC 풀노드, ETH 아카이브 노드를 직접 운영하면 수백 GB의 저장소와 운영 비용이 필요하다. CryptoAPIs 같은 Blockchain-as-a-Service를 쓰면 REST API 한 번으로 트랜잭션 조회, 주소 생성, 전송이 가능하다. 도메인 로직에 집중할 수 있었다.

### 요청과 실행을 분리하면 장애에 강해진다

출금을 즉시 처리하지 않고 DB에 Pending 상태로 저장하는 패턴은, 블록체인 API 장애나 네트워크 오류 시 요청이 유실되지 않는다는 장점이 있다. 재처리, 관리자 개입, 감사 로그 모두 이 구조에서 자연스럽게 따라온다.

---

## 기술 스택

`NestJS` `TypeScript` `TypeORM` `PostgreSQL` `CryptoAPIs` (Blockchain-as-a-Service) `@nestjs/schedule`
