# Refresh Interval

## 1. 내부 동작 메커니즘: 데이터가 검색되기까지

OpenSearch의 근간인 **Apache Lucene**은 불변의 **Segment** 단위로 데이터를 저장한다.

- **1. In-memory Buffer (메모리 버퍼)**:
  - 데이터가 들어오면 가장 먼저 **메모리 버퍼**에 쌓인다.
  - 동시에 데이터 유실 방지를 위해 **Translog**에도 기록된다.
  - **이 상태에서는 아직 검색(Search)이 불가능하다**
- **2. Refresh**
  - `refresh_interval` 주기 (기본 1초)가 되면, 버퍼에 있던 내용이 새로운 **Segment**라는 단위로 만들어져 **운영체제의 파일시스템 캐시**로 넘어간다.
  - 이 과정을 **Open**이라고 하며, **이 시점부터 비로소 검색이 가능**해진다.
  - 이때 생성된 세그먼트는 아직 디스크에 물리적으로 `fsync`된 상태는 아니다. (성능을 위해 메모리 캐시에만 존재)
- **3. Flush**
  - 별도의 주기에 따라 파일시스템 캐시의 세그먼트들이 실제 **디스크**에 영구 저장(`fsync`)되고, Translog가 비워진다.

> 요약 : Refresh는 메모리 버퍼 -> 파일시스템 캐시(Segment 생성) 과정이며, 이 주기가 바로 `refresh_interval` 이다.

## 2. 왜 실시간이 아닌가?

왜 들어오자마자 바로 Segment로 만들지 않느냐? 라고 물을 수 있다.

- **비용 문제**: Segment를 생성하고 Open 하는 작업은 시스템 리소스를 꽤 소모한다.
- **Merge Overhead**:
  - 데이터가 들어올 때마다 Segment를 만들면, 수천, 수만 개의 아주 작은 Segment가 생긴다.
  - OpenSearch는 백그라운드에서 이들을 합치는 **Segment Merge** 작업을 수행하는데, 작은 파일이 너무 많으면 이 작업에 CPU가 폭발적으로 사용되어 전체 성능이 저하된다.

> 그래서 "기본 1초"라는 버퍼링 시간을 두어, 어느 정도 모아서 Segment를 만들게끔 설계된 것이다. <br>
> 이를 Near Real Time(NRT)라고 부른다.

## 3. 상황별 튜닝 전략

개발자로서 이 값을 언제, 어떻게 조절해야 할지 아는 것이 중요하다.

### (1) 대량 색인 (Bulk Insert) 시: `refresh_interval: -1`

초기 데이터를 마이그레이션하거나 수백만 건을 한 번에 넣을 떄는 Refresh를 끄는 것이 정석이다.

- 설정: "-1"로 설정하면 자동 Refresh가 비활성화된다.
- 이점: 불필요한 Segment 생성을 막아 색인 속도가 빨라진다.
- 주의: 작업이 끝난 후 반드시 원래대로 (예: "1s") 돌려놔야 검색이 된다.

```bash
# 색인 전: Refresh 끄기
PUT /my-index/_settings
{ "index": { "refresh_interval": "-1" } }

# ... 대량 Bulk Insert 수행 ...

# 색인 후: Refresh 켜기 (복구)
PUT /my-index/_settings
{ "index": { "refresh_interval": "1s" } }
```

### (2) 검색 위주의 인덱스: 30s ~ 60s

실시간성이 크게 중요하지 않은 로그 데이터나 상품 정보라면 주기를 늘리자.

- 이점: Segment 수가 줄어들어 검색 성능이 좋아지고, 리소스 사용량이 감소한다.

## 궁금한 점

### (1) 운영 중에 `refresh_interval`을 변경해도 괜찮은가?

"아주 권장되는 표준 운영 패턴이다"

OpenSearch의 모든 인덱스 설정(`_settings`)은 동적으로 변경 가능하도록 설계되었다. <br>
클러스터 재시작은 커녕 인덱스를 닫을 필요조차 없다.

#### 언제 변경하면 좋을까?

- **대량 배치 작업 (Bulk Indexing)**:
  - 밤 12시에 1억 건의 데이터를 밀어 넣어야 한다면?
  - Action: 작업 시작전 "-1"(비활성)로 설정 -> 작업 후 "1s"(복구)
  - 이유: 리프레시 오버헤드를 없애 색인 속돌르 2배 이상 끌어올릴 수 있다.
- **색인 부하가 심할 때(Heavy Indexing Load)**:
  - 갑자기 트래픽이 몰려 CPU가 튀고 `Rejection` 에러가 발생한다면?
  - Action: "1s" -> "30s"로 늘림
  - 이유: 세그먼트 생성 빈도를 줄여 CPU 부하를 즉시 낮출 수 있다. 단, 데이터 검색 지연 시간은 30초로 늘어난다.
- **과거 데이터(Log Data)**:
  - 어제 자 로그 인덱스(오늘 더 이상 데이터가 안 들어옴)라면?
  - Action: 아예 끄거나 길게 설정

<br>

참고

- [Optimize Refresh Interval](https://opensearch.org/blog/optimize-refresh-interval/)
