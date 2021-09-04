# 데이터베이스 공부

## 0904 - SQL 기본, 활용, 최적화 원리 공부

### 데이터 언어

- DCL : Data Control Language
- DB접근, 객체의 사용 권한 부여 및 회수
- GRANT, REVOKE

- 데이터베이스에서 객체란 무엇인가?
- 데이터베이스 내에 존재하는 모든 논리적인 저장 구조

  1. 테이블 : 데이터를 담고 있는 객체
  2. 뷰 : 하나 이상의 테이블을 연결해 마치 테이블인 것처럼 사용하는 객체
  3. 인덱스 : 테이블에 있는 데이터를 빠르게 찾기 위한 객체
  4. 시노님(SYNOYM): 데이터베이스 객체에 대한 별칭을 부여한 객체
  5. 함수 : 특정 연산을 하고 값을 반환하는 객체
  6. 프로시저 : 함수와 비슷하지만 값을 반환하지 않는 객체
  7. 패키지 : 용도에 맞게 함수나 프로시저를 하나로 묶어 놓은 객체

- DDL : Data Definition Language
- CREATE, ALTER, DROP, <b>RENAME</b>(테이블의 이름을 변경하는 명령어)

- TCL : Transaction Control Language
- 논리적인 작업의 단위를 묶어서 DML에 의해 조작도힌 결과를 작업단위(트랜잭션) 별로 제어하는 명령어
- COMMIT, ROLLBACK, TRUNCATE

- DML : 비절차적 데이터 조작어 => 사용자가 무슨 데이터를 원하는지만 명세한다
- 사용자가 원하는 데이터만 선언 => 선언적 언어
- 어떻게 그 데이터를 검색하는지는 DBMS에게 위임함으로써 독자적으로 사용 가능하다
- PL/SQL(Oracle), T-SQL(SQLServer) : 절차적 데이터 조작어 => 어떻게 접근해야하는지까지 명세한다
- 초급 데이터 언어

- 호스트 프로그램속에 삽입되어 사용되는 DML 명령어들을 데이터 부속어(Data Sub Language)라고 한다

### 데이터 언어 사용법

- Primary Key 설정법
- ALTER TABLE 테이블명 ADD CONSTRAINT 제약조건명 PRIMARY KEY 컬럼명
- CREATE TABLE 내에서도 선언가능하다
- CONSTRAINT 제약조건명 PRIMARY KEY 컬럼명

- ALTER 사용시 주의할점
- SQLServer 에서는 컬럼에 괄호를 넣지 않는다
- NOT NULL을 지정하지 않으면 NULL로 변경된다
- 여러개의 컬럼을 한 문장으로 변경할 수 없다

- Primary Key = UNIQUE & NOT NULL
- Unique : Null도 입력가능 하다
- CHECK : DB에서 데이터 무결성을 유지하기위해 테이블의 특정 컬럼에 설정하는 제약이다
- 컬럼에 들어갈 수 있는 값들을 제한할 수 있다

- 테이블, 컬럼명은 문자로 시작해야한다
- 사용할 수 있는 문자는 A-Z, a-z, 0-9, \_, $, # 만 사용가능하다 (진짜?)

- COUNT 함수를 사용시 COUNT(\*), COUNT(컬럼)을 사용하면
- COUNT(\*)는 모든 컬럼의 갯수를 찾지만, COUNT(컬럼)에서 NULL이 있으면 NULL은 COUNT되지 않는다

- FK : Foreign Key => Null도 사용가능하다, 한 테이블에 여러개의 FK가 존재할 수 있다

- 테이블의 컬럼을 제거하는 법
- ALTER TABLE 테이블명 DROP COLUMN 컬럼명

- 테이블 명을 변경하는 법
- RENAME 기존테이블명 TO 변경할테이블명

- 삽입 시 액션 (Insert Action)

  1. Automatic : Master 테이블에 PK를 생성후 Child 테이블에 입력한다
  2. Set Null : Child 테이블에 null을 입력한다
  3. Set Default : Child 테이블에 기본 값을 입력한다
  4. Dependent : Master 테이블에 PK가 존재할 때만 입력한다
  5. No Action : 무결성을 지키기 위해 아무런 동작도 하지 않는다

- DROP, TRUNCATE, DELETE 차이점
  |drop|truncate|delete|
  |-----|--------|------|
  |DDL|DDL|DML|
  |Rollback 할 수 없음| Rollback 할 수 없음| Commit 이전에 대해서 Rollback 가능|
  |Auto Commit | Auto Commit | 사용자 Commit|
  |해당 Table에 대한 Storage를 모두 반환|초기에 생성된 테이블의 크기를 빼고 반환| Storage를 반환하지 않음|
  |테이블 정의 자체를 완전히 삭제| 테이블을 초기상태로 돌림| 데이터만 삭제함|

## 0904 - SQL 기본, 활용, 최적화 원리 공부2

### 트랜잭션

- 트랜잭션 : 쪼개질 수 없는 업무처리의 단위
- 안전성을 확보
- 처리 도중 오류가 발생하면 모든 작업을 원상태로 되돌림
- 커밋 : Commit => 모든 부분작업이 정상적으로 완료되면 변경사항을 DB에 반영
- 롤백 : Rollback => 부분 작업이 실패하면 트랜잭션 실행 전으로 되돌림

- 모든 연산을 취소하지 않고 정해진 부분까지만 되돌리고 싶을 때? => 저장점 : SAVEPOINT
- 전체가 아닌 특정 부분에서 트랜잭션을 취소시킬 수 있다
- 취소하려는 지점을 SAVEPOINT로 명시한뒤 ROLLBACK TO 세이브포인트이름을 실행하면 지정한 해당 SAVEPOINT 지점까지 처리한 작업이 ROLLBACK 된다

- SAVEPOINT SV1
- ROLLBACK TO SV1

- 트랜잭션의 연산과정

  1. 활성 : 트랜잭션이 정상적으로 실행중인 상태
  2. 실패 : 트랜잭션 실해엥 오류가 발생하여 중단된 상태
  3. 철회 : 트랜잭션이 비정상적으로 종료되어 Rollback 연산을 수행한 상태
  4. 부분 완료 : 트랜잭션의 마지막 연산까지 실행했지만, Commit 연산이 실행되기 직전의 상태
  5. 완료 : 트랜잭션이 성공적으로 종료되어 Commit 연산을 실행한 후의 상태

- 트랜잭션의 특징
- ACID (Atomicity, Consistency, Isolation, Durability)
- 트랜잭션이 안전하게 수행된다는 것을 보장하기 위한 트랜잭션의 특징

  1. 원자성 : 트랜잭션이 DB에 모두 반영되거나, 혹은 전혀 반영되지 않아야한다. All or Nothing
  2. 일관성 : 트랜잭션이 실행되기 전의 DB 내용이 잘못되어 있다면 트랜잭셔 후에도 데이터베이스의 내용이 잘못되어 있으면 안된다 (? 뭔가이상한데)
  3. 고립성, 독립성 : 둘 이상의 트랜잭션이 동시에 병행 실행되고 있을 때, 어떤 트랜잭션도 다른 트랜잭션 연산에 끼어들 수 없다
  4. 지속성 : 트랜잭션이 성공적으로 수행되면 트랜잭션이 갱신한 DB 내용은 영구적으로 저장된다

- 고립성이 약하면 어떻게 될까?
- Dirty Read : 다른 트랜잭션에 의해 수정되었지만 아직 커밋되어있지 않은 데이터를 읽음

- Oracle, SQLServer의 Auto Commit, Transaction 차이
- Oracle에서는 DDL 수행후 Auto Commit
- SQLServer에서는 DDL 수행후 Auto Commit 하지 않음
- Oracle에서는 DDL의 수행은 내부적으로 Transaction을 종료
- SQLServer에서는 CREATE TABLE도 Transaction의 범주에 포함 => Rollback 가능

### 연산자 및 함수

- 논리연산자 우선순위 NOT > AND > OR

- 사칙연산에 NULL이 포함되면 결과는 항상 NULL이다
- NULL과 비교연산하면 항상 false이다
- 특정값보다 크거나 작다라고 표현할 수 없기 때문이다
- INSERT시 Oracle에서 ''는 null로 삽입되며, SQLServer에서는 ''로 삽입된다

- 내장함수는 단일행 함수, 다중행 함수로 나뉜다
- 다중행 함수는 집계함수, 그룹함수, 윈도우 함수로 나뉜다
- 단일행 함수, 다중행 함수는 단일값을 반환한다
- 1:M 조인된 테이블에서도 사용이 가능하다

- LENGTH : 문자열의 길이 반환
- CHR : 주어진 ASCII에 대한 문자 반환
- CHR(10) : 줄 바꿈 문자 반환
- 특정 날짜에 + 1 => 하루가 더해짐
- 따라서 특정 날짜 + 1/24 => 1시간 더함
- 1/24/60 => 1분
- 1/24(60/10) => 10분

- CASE 문을 사용하는 두 가지 방법
- CASE WHEN COLUMN1 = 'VALUE' THEN 'OTHER_VALUE' END
- CASE COLUMN WHEN 'VALUE' THEN 'OTHER_VALUE' END

- NVL, ISNULL(표현식1, 표현식2) : 표현식1이 NULL이면 표현식2를 출력
- NULLIF(표현식1, 표현식2) : 표현식1과 표현식2가 같으면 NULL 출력, 그렇지 않으면 표현식1 출력
- COALESCE(표현식1, 표현식2, ...) : 최초로 NULL이 아닌값 출력, 모두 NULL이면 NULL 출력
