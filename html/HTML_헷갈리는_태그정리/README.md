# HTML 태그들, 헷갈리는거 정리해 보았다 🥳 (시맨틱 태그, 중요한 태그들 모음)

- https://www.youtube.com/watch?v=T7h8O7dpJIg

## 헷갈렸던 내용을 깔끔하게 정리해보자!!

- 시맨틱(semantic) 태그들
- section, article 차이점
- 똑같은 이탤릭체인 i, em의 <b>치명적인</b> 차이점
- 볼드를 나타낼때 쓰는 b, strong 차이점
- img 태그와 css background-image이 둘중에 언제 어떤걸 써야하는지
- 언제 a태그와 button을 써야하는지
- 목록 태그의 차이점 ol, ul, dl
- 스타일링을 위해서 테이블을 쓰면 안되는 이유!

### 시맨틱(semantic) 태그, 시맨틱 마크업

- semantic: 의미의, 의미가 있는
- html 태그도 저마다의 의미가 있다
- 예) 중요한 제목 => 글자만 키운다고 해서 의미를 가지진 않음! => h1 태그를 사용
- 모든 태그를 div 태그를 이용해서 만들수 도 있음
- 하지만 semantic tag를 적절히 사용하면 좋다!

- 장점

  1. SEO(Search Engine Optimization)
  2. Accessibility (Screen Reader, 키보드만을 사용해 웹 사이트를 사용)
  3. For us, Maintainability

- header: 브랜드 로고, 사용자 메뉴등
- nav: 메뉴가 모여있다면 사용
- footer: 부가적인 정보 : 링크
- main: 웹 사이트에서 중요한 컨텐츠
- aside: 메인에서 직접적이진 않은 컨텐츠, 연관된 링크
- section: !
- article: !

### article vs section

- article: 블로그에서 하나의 글, 신문에서 하나의 기사, 자체만으로 독립적으로 다른 페이지에 보여줬을 때 문제가 없다
- main과 상관없이 고유한 정보를 나타냄
- section: main, article등에서 연관있는 내용을 묶었을 때 section을 사용
- 카테고리 분류해서 포스트 나타내기

### i vs em

- screen reader에서 읽었을 때 강조하려면 em태그를 사용해야 함
- i는 별다른 의미가 없음 (책의 제목,인용구 등)
- em 강조하는 이탤릭체 (정말 강조하고 싶은 이탤릭체)

### b vs strong

- 위와 비슷함
- screen reader에서 읽었을 때 strong이 강조됨

### ul vs ol vs dl

- ul : unordered list, 순서가 없는 리스트
- ol : ordered list, 순서가 있는 리스트, 순서가 중요할 때 사용
- dl : description list, 어떠한 단어에 대한 설명이 묶여있을 때 사용

### img vs css background-image

- 웹 페이지에서 중요한 이미지일 때 => img 태그
- 문서의 일부분이 아닌경우 => css background-image
- 이 이미지가 없어도 문서를 읽었을 때 관계가 없음

### button vs a

- button => 사용자의 특정한 액션을 위해
- a => 사용자가 어디론가 이동할 때

### table vs css

- table 태그를 이용해서 스타일링을 하기보다는
- css flex, grid를 사용해서 스타일링을 하자!
