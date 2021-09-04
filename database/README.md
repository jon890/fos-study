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
