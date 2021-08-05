# 2장 자바스크립트의 독특한 특징

- 구문과 동작 방식에 있어 JS 지니는 예외적인 사례와 특징을 살펴볼 것이다
- JS는 동적 인터프리터 프로그래밍 언어이기 때문에 다른 전통적인 객체지향 프로그래밍 언어들과 구문이 다르다
- 이런 개념들은 JS의 근간을 이루고 있으며 우리가 JS 알고리즘을 설계하는 과정을 이해하는데 많은 도움이 된다

## 자바스크립트 스코프 (scope)

- 스코프는 자바스크립트 변수에 대한 접근 권한을 정의하는 것이다
- JS에서 변수는 전역 스코프 또는 지역 스코프에 속할 수 있다
- 전역 스코프에 속하는 변수는 전역 변수라고 부른다
- 전역 변수는 프로그램의 어디에서나 접근 가능하다

  ### 전역 선언 : 전역 스코프

  - JS에서 연산자 없이 변수를 선언할 수 있다

  ```
  foo = "I'm Global Variable";
  console.log(foo);
  ```

  - 위의 코드는 전역변수를 생성한다
  - 위와 같은 선언 방식은 JS에서 가장 안좋은 사용법 가운데 하나이다
  - 항상 JS에서는 var나 let를 사용해 변수를 선언하자
  - 마지막으로 수정하지 않을 변수를 선언할 때 const를 사용하자

  ### var를 사용해 선언하기 : 함수 범위

  - JS에서 var는 변수를 선언하는 데 사용하는 키워드다
  - 변수를 어디에서 선언하든 변수 선언이 함수의 맨 앞으로 이동한다
  - 이를 변수 호이스팅이라고도 한다
  - 스크립트 실행 시 변수가 스크립트의 가장 마지막에 선언됐다고 하더라도 해당 선언 코드가 가장 마지막에 실행되는 것이 아니다

  - var 키워드에 관해 주목해야 할 핵심적인 사항은 해당 변수의 범위가 <b>가장 가까운 함수 범위</b>리는 것이다
  - 다음 코드에서 scope2 함수는 insideIf 변수와 가장 가까운 함수 범위다

  ```
  function scope2(print) {
      if (print) {
          var insideIf = '12';
      }
      console.log(insideIf);
  }
  scope2(true); // 12를 출력하며 오류가 발생하지 않음
  ```

  - 자바에서 위의 구문은 오류를 일으킬 것이다
  - insideIf 변수가 if문 블록 내에서만 사용 가능하고 if문 블록 외부에서는 사용할 수 없기 때문이다

  ### let을 활용한 선언 : 블록 범위

  - 변수를 선언할 때 사용할 수 있는 또 다른 키워드로 let이 있다
  - let을 사용해 선언된 변수는 가장 가까운 블록 범위를 갖는다(즉, 변수가 선언된 {} 내에서 유효하다)

  ```
  function scope3(print) {
      if (print) {
          let insideif = '12';
      }
      console.log(insideIf);
  }
  scope3(true); // 오류 ReferenceError가 발생한다
  ```

## 등가와 형

- JS에는 전통적인 언어와 다른 자료형이 있다
- 이러한 점이 등가 비교와 같은 것들에 어떤 식으로 영향을 미치는지 살펴보자

  ### 변수형

  - JS에는 boolean, number, string, undefined, object, function, symbol과 같은 일곱 개의 기본 자료형이 있다
  - 여기서 특이한 점은 선언만 되고 값이 할당되지 않은 변수에 undefined가 할당된다는 것이다
  - typeof는 변수의 형을 반환하는 데 사용하는 기본 연산자다

  ```
  var is20 = false; // boolean
  typeof is20; // boolean

  var age = 19;
  typeof = age; // number

  var lastName = "Bae";
  typeof lastName; // string

  var fruits = ["Apple", "Banana", "Kiwi"];
  typeof fruits; // object

  var me = { firstName: "Sample", lastName: "Bae" };
  typeof me; // object

  var nullVar = null;
  typeof nullVar; // object

  var function1 = function() {
      console.log(i);
  }
  type function1 // function

  var blank;
  typeof blank; // undefined
  ```

  ### 참/거짓 확인

  - 하지만 JS에서(그리고 다른 동적으로 형이 결정되는 언어들)는 이 점에 있어 좀더 유연하다
  - 다음 예를 살펴보자

  ```
  if (node) {
      ...
  }
  ```

  - 여기서 node는 변수다
  - 해당 변수가 비었거나 null이거나 undefined이면 해당 변수는 false로 평가된다

  - 다음은 일반적으로 사용되는 표현식 중 false로 평가되는 경우다 (falsy)

    1. false
    2. 0
    3. 빈 문자열 ('')
    4. NaN
    5. undefined
    6. null

  - 다음은 일반적으로 사용되는 표현식 중 true로 평과디는 경우다 (truthy)

    1. true
    2. 0이 아닌 다른 숫자
    3. 비어있지 않은 문자열
    4. 비어 있지 않은 객체

  ### === vs ==

  - JS는 스크립트 언어이고 변수 선언 시 변수에 형이 할당되지 않는다
  - 대신에 코드가 실행될 때 해당 변수의 형이 해석된다
  - 따라서 ===는 ==보다 등가를 좀 더 엄격히 확인한다
  - ==가 값만은 확인하는 반면 ===는 형과 값 모두 확인한다

  ```
  "5" == 5 // true를 반환한다
  "5" === 5 // false를 반환한다
  ```

  ### 객체

  - 자바와 같은 강한 타입 언어는 equals()를 사용해 두 객체가 동일한지 확인한다
  - JS에서 두 객체가 동일한지 확인하고자 우리는 간단히 == 연산자를 사용해볼까 하는 생각이 들 수 있다
  - JS에서 객체의 비교를 할 떄 == 연산자를 사용하면 두 객체의 메모리상 주소가 같은지 확인한다
  - 이것이 대부분의 자바스크립트 애플리케이션이 lodash나 underscore와 같은 유틸리티 라이브러리를 사용하는 이유다

  - 다음 예제에서 객체가 같은지 정확하게 비교하기 위해 각 속성을 비교한다

  ```
  function isEquivalent(a, b) {
      // 속성 이름 배열
      var aProps = Object.getOwnPropertyNames(a);
      var bProps = Object.getOwnPropertyNames(b);

      // 속성 길이가 다른 경우 두 객체는 다른 객체다
      if (aProps.length !== bProps.length) {
          return false;
      }

      for (const propName of aProps) {
          if (a[propName] !== b[propName]) {
              return false;
          }
      }

      // 모든 것이 일치하면 두 객체는 일치한다
      return true
  }
  ```

  - 위 함수는 문자열이나 숫자 하나만을 속성으로 갖는 객채에 대해서도 잘 동작할 것것이다
  - 그렇지만 객체에 함수가 있다면 두 함수가 동일한 연산을 수행해도 두 함수의 메모리상 주소는 다르다
  - 기본 등가 확인 연산자인 ==와 ===는 문자열과 숫자에만 사용할 수 있다
  - 객체에 대한 등가 확인을 구현하려면 객체의 각 속성을 확인해야 한다
