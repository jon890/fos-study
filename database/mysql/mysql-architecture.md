# MySQL 아키텍처 (작성 중..)

- MySQL 서버는 머리 역할을 담당하는 MySQL 엔진과, 손발 역할을 담당하는 스토리지 엔진으로 구분할 수 있다.
- 스토리지 엔진은 핸들러 API를 만족하면 누구든지 스토리지 엔진을 구현해서 MySQL 서버에 추가해 사용할 수 있다.
- 이번 장에서는 InnoDB 스토리지 엔진과 MyISAM 스토리지 엔진을 구분해서 살펴보자.

## 1 MySQL 엔진 아키텍처

- MySQL 서버는 다른 DBMS에 비해 구조가 상당히 독특하다.
- 아래 구조도를 보면서 설명을 이어나가보자.

### 1-1. MySQL 전체 아키텍처 구조도

```mermaid
flowchart TB
    Client[Client / Application<br/>JDBC · ODBC · MySQL Client]

    subgraph Server[MySQL Server Layer]
        Conn[Connection Manager<br/>Auth · Thread]
        Parser[Parser<br/>SQL Parsing]
        Optimizer[Optimizer<br/>Execution Plan]
        Executor[Executor<br/>Query Execution]
        Binlog[Binlog<br/>Logical Log]
    end

    subgraph Engine[Storage Engine Layer]
        InnoDB[InnoDB Engine]
        MyISAM[MyISAM Engine]
    end

    subgraph InnoDBInternal[InnoDB Internal Structure]
        BP[Buffer Pool]
        Redo[Redo Log]
        Undo[Undo Log]
        TS[Tablespace]
    end

    Disk[OS / Disk<br/>Data Files · Log Files]

    Client --> Conn
    Conn --> Parser
    Parser --> Optimizer
    Optimizer --> Executor

    Executor --> InnoDB
    Executor --> MyISAM

    Executor --> Binlog

    InnoDB --> BP
    InnoDB --> Redo
    InnoDB --> Undo
    InnoDB --> TS

    BP --> Disk
    Redo --> Disk
    Undo --> Disk
    TS --> Disk

```

#### (1) MySQL 엔진

- 클라이언트로부터의 접속 및 쿼리 요청을 처리하는 커넥션 핸들러와 SQL 파서 및 전처리기, 쿼리의 최적화된 실행을 위한 옵티마이저가 중심을 이룬다.

#### (2) 스토리지 엔진

- 실제 데이터를 디스크 스토리지에 저장하거나 디스크 스토리지로부터 데이터를 읽어오는 부분을 담당한다.
- 스토리지 엔진은 여러 개를 동시에 사용할 수 있다.
  - 다음과 같이 테이블이 사용할 스토리지 엔진을 지정하면 이후 해당 테이블의 모든 읽기 작업이나 변경 작업은 정의된 스토리지 엔진이 처리한다

  ```sql
  CREATE TABLE test_table (fd1 INT, fd2 INT) ENGINE=InnoDB;
  ```

#### (3) 핸들러 API

- MySQL 엔진의 쿼리 실행기에서 데이터를 쓰거나 읽어야 할 때는 각 스토리지 엔진에 쓰기 또는 읽기를 요청하는데, 이러한 요청을 핸들러(Handler) 요청이라고 한다. 여기에서 사용되는 API를 핸들러 API라고 부른다.
- 핸들러 API를 통해 얼마나 많은 데이터(레코드) 작업이 있었는지는 `SHOW GLOBAL STATUS LIKE 'Handler%';` 명령어로 확인해볼 수 있다.
  - 현재 Spring Batch 메타데이터만 관리하는 DB에 요청해본결과

  ```markdown
  | Variable_name              | Value     |
  | -------------------------- | --------- |
  | Handler_commit             | 52788536  |
  | Handler_delete             | 1279      |
  | Handler_discover           | 0         |
  | Handler_external_lock      | 47244223  |
  | Handler_mrr_init           | 0         |
  | Handler_prepare            | 42530716  |
  | Handler_read_first         | 2641564   |
  | Handler_read_key           | 23349322  |
  | Handler_read_last          | 5         |
  | Handler_read_next          | 7360721   |
  | Handler_read_prev          | 2503      |
  | Handler_read_rnd           | 855       |
  | Handler_read_rnd_next      | 388011957 |
  | Handler_rollback           | 418       |
  | Handler_savepoint          | 0         |
  | Handler_savepoint_rollback | 0         |
  | Handler_update             | 10972053  |
  | Handler_write              | 191353285 |
  ```

### 2. MySQL 스레딩 구조

- MySQL 서버는 스레드 기반으로 동작한다.
- 크게 포그라운드(Foreground) 스레드와 백그라운드(Background) 스레드로 구분할 수 있다.
- Thread per Connection으로 동작한다. (커넥션당 포그라운드 스레드 1개)
  - 일부 배포버전이나 엔터프라이즈 버전은 Thread Pool을 사용한다.
  - (내 생각) 보통 Application에서 커넥션 풀을 사용하므로 크게 문제되지는 않을 것 같아 보임

```mermaid
flowchart TB
    Client1[Client 1]
    Client2[Client 2]
    ClientN[Client N]

    subgraph Server[MySQL Server Process]
        subgraph CM[Connection Manager]
            Listener[Connection Listener]
            Auth[Authentication & Authorization]
            ThreadCache[Thread Cache]
        end

        subgraph WorkerThreads[Worker Threads]
            T1[Thread #1<br/>Query Execution]
            T2[Thread #2<br/>Query Execution]
            TN[Thread #N<br/>Query Execution]
        end

        subgraph Shared[Shared Components]
            Parser[Parser]
            Optimizer[Optimizer]
            Metadata[Metadata Lock]
            BufferPool[InnoDB Buffer Pool]
            Log[Redo / Binlog]
        end
    end

    Client1 --> Listener
    Client2 --> Listener
    ClientN --> Listener

    Listener --> Auth
    Auth --> ThreadCache

    ThreadCache --> T1
    ThreadCache --> T2
    ThreadCache --> TN

    T1 --> Parser
    T2 --> Parser
    TN --> Parser

    T1 --> Optimizer
    T2 --> Optimizer
    TN --> Optimizer

    T1 --> BufferPool
    T2 --> BufferPool
    TN --> BufferPool

    T1 --> Log
    T2 --> Log
    TN --> Log
```

#### 포그라운드 스레드 (클라이언트 스레드)

- 각 클라이언트 사용자가 요청하는 쿼리 문장을 처리한다.
- 클라이언트 사용자가 작업을 마치고 커넥션을 종료하면 해당 커넥션을 담당하던 스레드는 다시 스레드 캐시(Thread Cache)로 돌아간다.
- 이떄 스레드 캐시에 유지할 수 있는 최대 스레드 개수는 `thread_cache_size` 시스템 변수로 설정한다.
- (내 생각) Thread Pool과 Thread Cache가 다른건 뭐지?
  - Thread Cache - 종료된 스레드를 버리지 않고 보관했다가 재사용 - 스레드를 덜 만들 뿐, 많이 쓰는 건 그대로다.

    ```text
    Connection 종료
    → Thread 종료 ❌
    → Thread Cache에 보관
    새 Connection
    → Thread 생성 ❌
    → Cache에서 재사용
    ```

  - Thread Pool
    - 커넥션 수와 스레드 수를 분리
    - 요청을 큐잉해서 제한된 스레드로 처리
    - 애초에 스레드를 많이 못 쓰게 막는다.

    ```text
    Connection 1,000개
    ↓
    Request Queue
    ↓
    Worker Thread 32개
    ```

    > 정리, Thread Cache는 Thread-per-Connection 모델을 유지한 채 <br/ >
    > 스레드 생성 비용을 줄이는 기능이다. <br/ >
    > Thread Pool은 커넥션과 스레드를 분리해서 <br/ >
    > 서버의 동시성을 제어하는 아키텍처적인 변화이다.

- 데이터를 MySQL의 버퍼나 캐시로부터 가져오며, 버퍼나 캐시에 없는 경우에는 직접 디스크의 데이터나 인덱스 파일로부터 데이터를 읽어와서 작업을 처리한다.
- InnoDB에서 쓰기 작업은 데이터 버퍼나 캐시까지만 포그라운드 스레드가 처리하고, 버퍼로부터 디스크까지 기록하는 작업은 백그라운드 스레드가 처리한다.

#### 백그라운드 스레드

InnoDB는 다음과 같은 여러 가지 작업이 백그라운드 스레드로 처리된다.

- 인서트 버퍼 (Insert Buffer)를 병합하는 스레드
- **로그를 디스크로 기록하는 스레드**
- **InnoDB 버퍼 풀의 데이터를 디스크에 기록하는 스레드**
- 데이터를 버퍼로 읽어오는 스레드
- 잠금이나 데드락을 모니터링하는 스레드

상용 DBMS에는 대부분 쓰기 작업을 버퍼링해서 일괄 처리하는 기능이 탑재되어 있으며, InnoDB 또한 이러한 방식으로 처리한다.
INSERT, UPDATE, DELETE 쿼리로 데이터가 변경되는 경우 데이터가 디스크의 데이터 파일로 완전히 저장될 때까지 기다리지 않아도 된다.
