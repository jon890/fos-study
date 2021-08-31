# 데이터 베이스 정규화

- https://3months.tistory.com/193

- 정규화 : 데이터베이스의 설계를 재구성하는 테크닉
- 정규화를 통해 불필요한 데이터(redundancy)를 없앨 수 있다
- 또한 삽입/갱신/삭제 시 발생할 수 있는 각종 이상현상(Anamolies)들을 방지할 수 있다

- 정규화의 목적

  1. 불필요한 데이터 제거
  2. 데이터 저장을 "논리적" 으로 함 => 논리적이고 직관적

- 정규화를 안했을 때의 문제점

| s_id | s_name | s_address | subject_opted |
| ---- | ------ | --------- | ------------- |
| 401  | Adam   | Noida     | bio           |
| 402  | Alex   | Panipat   | Maths         |
| 403  | Stuart | Jammu     | Maths         |
| 404  | Adam   | Noida     | Physics       |

- 위와 같이 정규화 되지 않은 테이블은 => Adam이라는 학생 이름 값이 두번 들어가있다
- 또한 데이터 핸들링시 다양한 이상현상이 발생한다

1. Update : Adam의 Address가 변경되었을 때, 여러줄의 데이터를 갱신해야 한다 => 이로 인해 데이터의 불일치(inconsistency)가 발생할 수 있다
2. Insert : 학생이 아무 과목도 수강하지 않는다고 하면, Subject_opted 컬럼에는 NULL 값이 들어간다
3. Deletion : 만약 Alex 학생이 과목 수강을 취소한다면 Alex의 레코드가 테이블에서 아예 사라진다

- 위와 같이 정규화가 제대로 되지 않는 테이블의 경우 갱신/삽입/삭제 시 다양한 문제점이 발생할 수 있다
- 테이블의 구성을 논리적으로 변경하여 해결하고자 하는 것이 바로 정규화이다

- 정규화의 법칙(Normalization Rule)은 1차 정규화, 2차 정규화, 3차 정규화, BCNF, 4차 정규화, 5차 정규화로 나뉜다
- 실무적으로 4차, 5차 정규화까지 하는 경우는 많지많다
- 이 글에서도 BCNF 까지 알아본다

## 1차 정규화

- 1차 정규형 : 각 로우마다 컬럼의 값이 1개씩만 있어야 한다
- 이를 컬럼이 원자값(Atomic Value)를 갖는다고 한다

- 아래의 테이블 구조를 보자

| Student | Age | Subject        |
| ------- | --- | -------------- |
| Adam    | 15  | Biology, Maths |
| Alex    | 14  | Maths          |
| Stuart  | 17  | Maths          |

- 위의 정보를 표현하고 싶은 경우는 아래와 같이 하나의 로우를 더 만들어야 한다
- 결과적으로 1차 정규화를 함으로써 데이터 redundancy는 더 증가하였다
- 데이터의 논리적 구성을 위해 이 부분을 희생한다고 볼 수 있다

| Student | Age | Subject |
| ------- | --- | ------- |
| Adam    | 15  | Biology |
| Adam    | 15  | Maths   |
| Alex    | 14  | Maths   |
| Stuart  | 17  | Maths   |

## 2차 정규화

- 본격적인 정규화의 시작
- 2차 졍규형 : 테이블의 모든 컬럼이 완전 함수적 종속을 만족
- 기본키중에 큭정 컬럼에만 종속된 컬럼(부분적 종속)이 없어야 한다
- 위 테이블의 경우 기본키는 (Student, Subject)로 두 개의 컬럼이 키가 된다고 볼 수 있다
- 그런데 Age의 경우 기본키 컬럼중에 Student에 종속되어 있다
- 즉, Student 컬럼의 값을 알면 Age의 값을 알 수 있게 된다.
- 따라서 Age가 여러번 들어가는 것은 불필요하다고 볼 수 있다

- Student Table

| Student | Age |
| ------- | --- |
| Adam    | 15  |
| Alex    | 14  |
| Stuart  | 17  |

- Subject Table

| Student | Subject |
| ------- | ------- |
| Adam    | Biology |
| Adam    | Maths   |
| Alex    | Maths   |
| Stuart  | Maths   |

- 이를 해결하기 위한 방법은 위처럼 테이블을 분리하는 것이다
- 그러면 두 테이블 모두 2차 정규형을 만족하게 된다
- 조금 더 복잡한 테이블의 경우, 3차 정규화를 해야한다

## 3차 정규화

- Student Detail Table

  | Student_id | Student_name | DOB | Street | City | State | Zip |
  | ---------- | ------------ | --- | ------ | ---- | ----- | --- |

- 위와 같은 테이블이 구성을 생각해보자
- Student_id가 기본키이고 기본키가 하나임으로 2차 정규형은 만족한다
- 하지만 이 데이터에서 Zip 컬럼을 알면, Street, City, State를 결정할 수 있다
- 또한 여러명의 학생들이 같은 Zip 코드를 갖는 경우도 생각할 수 있다
- 이 때에도 Zip 컬럼을 알면 Stree, City, State가 결졍된다
- 따라서 중복된 데이터가 생길 가능성이 있다

- 정리해보면 3차 정규형은 기본키를 제외한 속성들간의 이행적 함수 종속이 없는 것이다
- 기본키 이외의 다른 컬럼이 그외 다른 컬럼을 결정할 수 없다

- 3차 정규화도 2차 정규화와 마찬가지로 테이블을 분리함으로써 해결할 수 있다

- New Student Detail Table

| Student_id | Student_name | DOB | Zip |
| ---------- | ------------ | --- | --- |

- Address Table

| Zip | Street | City | State |
| --- | ------ | ---- | ----- |

## BCNF (Boyce and Codd Normal Form)

- 3차 정규형을 조금 더 강화한 버전
- 3차 정규형을 만족하면서 모든 결정자가 후보키 집합에 속한 정규형
- BCNF를 만족하지 않는 경우 => 일반 컬럼이 후보키를 결정하는 경우
