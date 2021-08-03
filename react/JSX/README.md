# JSX는 무엇인가요?

- JSX는 HTML처럼 보이는 코드를 작성할 수 있게 해주는 자바스크립트 문법의 확장입니다
- JSX는 자바스크립트 함수 호출 방식으로 컴파일되어 컴포넌트에 대한 마크업을 만들 수 있는 더 좋은 방법을 제공합니다

- 이 JSX를 보세요

```
<div className="sideBar">
```

- 이것은 아래의 자바스크립트로 변환됩니다

```
React.createElement(
    'div',
    { className: 'sidebar' }
)
```
