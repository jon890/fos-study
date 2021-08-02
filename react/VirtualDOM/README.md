# Understanding the Virtual DOM을 읽고

- https://bitsofco.de/understanding-the-virtual-dom/

## DOM

- 오브젝트를 기반으로하여 HTML 문서를 표헌하고, 오브젝트를 조작할 수 있게 하는 인터페이스이다
- Shadow DOM은 DOM의 "가벼운" 버전으로 생각 할 수 있다
- Shadow DOM은 HTML 요소들을 오브젝트 기반으로 나타내지만, 완전한 독립형 문서는 아니다
- 대신 Shadow DOM을 사용하면 DOM을 HTML 문서 전체에서 사용할 수 있는 더 작고 캡슐화된 비트로 분리할 수 있다

## Virtual DOM

- 이 개념은 몇 년동안 존재했지만, React 프레임워크에서 사용되면서 더 유명해졌다
- 이 문서에서는 가상 Virtual DOM이 정확히 무엇인지, 원래의 DOM과 어떻게 다른지, 어떻게 사용되는지에 대해서 설명한다

## 왜 Virtual DOM이 필요할까?

- 가상 DOM의 개념이 생겨난 이유를 이해하기 위해 원래 DOM을 다시 살펴보자
- DOM에는 HTML 문서의 오브젝트 기반 표현과 해당 오브젝트를 조작하기 위한 API의 두 부분이 있다
- 간단한 HTML 문서를 살펴보자

```
<!doctype html>
<html lang="en">
 <head></head>
 <body>
    <ul class="list">
        <li class="list__item">List item</li>
    </ul>
  </body>
</html>
```

- 이 문서는 다음 DOM 트리로 나타낼 수 있다

```
  HTML
   └ head lang="en"
   └ body
     └ ul class="list"
       └ li class="list__item"
         └ List item
```

- 첫 번째 목록 항목의 내용을 수정하고 => List item one
- 두 번째 목록 항목도 추가하려고 한다고 가정해보자
- 이렇게 하려면 다음과 같이 해야한다.

  1. DOM API를 사용하여 업데이트하려는 요소를 찾고
  2. 새 요소를 만들고
  3. 속성과 컨텐츠를 추가하고
  4. 마지막으로 DOM 요소 자체를 업데이트 해야한다

  ```
  const listItemOne = document.getElementsByClassName("list_item"")[0];
  listItemOne.textContent = "List item one";

  const list = document.getElementsByClassName("list")[0];
  const listItemTwo = document.createElement("li");
  listItemTwo.classList.add("list__item");
  listItemTwo.textContent = "List item two";
  list.appendChild(listItemTwo);
  ```

  ### DOM은 이것을 위해 만들어지지 않았습니다..

  - DOM에 대한 첫 번째 사양이 1998년에 발표 되었을 떄 우리는 웹 페이지를 매우 다른 방식으로 구축하고 관리했다
  - 오늘날처럼 자주 페이지 콘텐츠를 만들고 업데이트하기 위해 DOM API에 대한 의존도가 훨씬 낮았다
  - document.getElementsByClassName()은 소규모로 사용하는 것은 좋지만, 몇 초마다 페이지의 여러 요소를 업데이트하는 경우 DOM을 지속적으로 쿼리하고 업데이트하는데 시간이 많이 걸릴 수 있다
  - 더욱이 API가 설정되는 방식 때문에 일반적으로 특정 요소를 찾아 업데이트 하는것보다 문서의 더 큰 부분을 업데이트하는 더 비싼 작업을 수행하는 것이 더 간단하다
  - 목록 예제로 돌아가서 전체 목록을 새 목록으로 바꾸는 것이 어떤 면에서는 더 쉽다

  ```
  const list = document.getElementsByClassName("list")[0];
  list.innerHTML = `
    <li class="list__item">List item one</li>
    <li class="list__item">List item two</li>
  `
  ```

  - 특정 예에서는 메서드 간의 성능 차이가 미미할 수 있다
  - <b>그러나 웹 페이지의 크기가 커질수록 필요한 것만 선택하여 업데이트하는 것이 중요해지고 있다</b>

  ### 하지만 Virutal DOM은 그랬습니다!

  - Virtual DOM은 DOM을 더 성능이 좋은 방식으로 자주 업데이트해야 하는 이러한 문제를 해결하기 위해 만들어짐
  - DOM이나 Shadow DOM과 달리 Virtual DOM은 공식 사양이 아니라 DOM과 인터페이스하는 새로운 방법

  - Virtual DOM은 원본 DOM의 복사본으로 생각할 수 있다
  - 이 사본은 DOM API를 사용하지 않고도 자주 조작하고 업데이트 할 수 있다
  - 가상 DOM에 대한 모든 업데이트가 이루어지면 원본 DOM에 어떤 특정 변경이 필요한지 살펴보고 목표에 맞게 최적화된 방식으로 변경할 수 있다

## Virtual DOM은 어떻게 생겼는가?

- 위의 트리는 Javascript 객체로 나타낼 수도 있다

```
const virtualDOM = {
    tagName: "html",
    children: [
        { tagName: "head" },
        {
            tagName: "body",
            children: [
                {
                    tagName: "ul",
                    attributes: { "class" : "list" },
                    children: [
                        {
                            tagName: "li",
                            attributes: { "class": "list__item" },
                            textContent: "List item"
                        } // end li
                    ]
                } // end ul
            ]
        } // end body
    ]
} // end html
```

- 이 객체를 가상 DOM으로 생각할 수 있다
- 원본 DOM과 마찬가지로 HTML 문서의 객체 기반 표현이다
- 그러나 그것은 평범한 자바스크립트 객체이기 때문에 필요할 때 까지 실제 DOM을 건드리지 않고도 자유롭고 자주 조작할 수 있다

- 전체 개체에 대해 하나의 개체를 사용하는 대신 가상 DOM의 작은 섹션으로 작업하는 것이 더 일반적이다
- 예를 들어 list순서가 지정되지 않은 목록 요소에 대응 하는 구성 요소에 대해 작업할 수 있다

```
const list = {
    tagName: "ul",
    attributes: { "class": "list" },
    children: [
        {
            tagName: "li",
            attributes: { "class": "list__item" },
            textContent: "List item"
        }
    ]
};
```

## Virtual DOM의 내부

- DOM의 성능 및 사용성 문제를 해결하기 위해서 Virtual DOM은 어떻게 작동할까?
- 앞서 언급했듯이 가상 DOM을 사용하여 DOM에 적용해야 하는 특정 변경 사항을 골라내고 이러한 특정 업데이트만 수행할 수 있다
- 이전 예제로 돌아가서 DOM API를 수행하여 수행한 것과 동일한 변경을 수행해보자
- 우리가 할 첫 번째 일은 Virtual DOM의 복사본을 만드는 것이다
- DOM API를 사용할 필요가 없기 떄문에 실제로 새 객체로 만들 수 있다

```
const copy = {
    tagName: "ul",
    attributes: { "class": "list" },
    children: [
        {
            tagName: "li",
            attributes: { "class": "list__item" },
            textContent: "List item one"
        },
        {
            tagName: "li",
            attributes: { "class": "list__item" },
            textContent: "List item two"
        }
    ]
};
```

- 이것은 copy 원래 Virtual DOM과 업데이트된 Virtual DOM 사이에 "차이"라고 불리는 것을 생성하는데 사용된다
- diff는 다음과 같이 보일 수 있다

```
const diffs = [
    {
        newNode: { /* new version of list item one */ },
        oldNode: { /* original version of list item one */ },
        index: /* index of element in parent's list of child nodes */
    },
    {
        newNode: { /* list item two */ },
        index: { /* */ }
    }
]
```

- 이 diff는 실제 DOM을 업데이트하는 방법에 대한 지침을 제공한다
- 모든 diff가 수집되면 DOM에 대한 변경 사항을 일괄 처리하여 필요한 업데이트만 수행할 수 있다
- 예를 들어 우리는 각 diff를 반복하고 diff가 지정하느 것에 따라 새 자식을 추가하거나 이전 자식을 업데이트 할 수 있다

```
const domElement = document.getElementsByClassName("list")[0];

diffs.forEach((diff) => {

    const newElement = document.createElement(diff.newNode.tagName);
    /* Add attributes ... */

    if (diff.oldNode) {
        // If there is an old version, replace it with the new version
        domElement.replaceChild(diff.newNode, diff.index);
    } else {
        // If no old version exists, create a new node
        domElement.appendChild(diff.newNode);
    }
})
```

- 이것은 Virtual DOM이 작동하는 방식에 대한 단순화된 버전이고, 여기에서 다루지 않은 많은 경우가 있다

## Virtual DOM과 Framework

- 위의 예에서 보여준 것처럼 Virtual DOM과 직접 인터페이스하는 것보다 Framework를 통해 Virtual DOM으로 작업하는 것이 더 일반적이다
- React 및 Vue와 같은 Framework는 Virtual DOM 개념을 사용하여 DOM을 보다효과적으로 업데이트 한다
- 예를 들어, 우리 list 컴포넌트는 다음과 같은 방식으로 React로 작성할 수 있다

```
import React from 'react';
import ReactDOM from 'react-dom';

const list = React.createElement("ul", { className: "list" },
    React.createElement("li", { className: "list__item" }, "List item")
);

ReactDOM.render(list, document.body);
```

- 목록을 업데이트하려면 전체 목록 템플릿을 다시 작성하고 <b>ReactDOM.render()</b>를 다시 호출 하여 새 목록을 전달하면 된다

```
const newList = React.createElement("ul", { className: "list" },
    React.createElement("li", { className: "list__item" }, "List item one"),
    React.createElement("li", { className: "list__item" }, "List item two");
);

setTimeout(() => ReactDOM.render(newList, document.body), 5000);
```

- React는 Virtual DOM을 사용하기 때문에 전체 템플릿을 다시 렌더링하더라도 실제로 변경된 부분만 업데이트된다
- 변경 사항이 발생할 때 개발자 도구를 보면 특정 요소와 변경되는 요소의 특정 부분을 볼 수 있다

## DOM vs Virtual DOM

- 요약하자면 Virtual DOM은 DOM 요소와 더 쉽고 성능이 좋은 방식으로 인터페이스 할 수 있게 해주는 도구이다
- 이것은 DOM의 Javascript 객체 표현으로, 필요할때마다 수정할 수 있다
- 그런 다음 이 개체에 대한 변경 사항을 대조하고 실제 DOM에 대한 수정 사항을 대상으로 지정하고 덜 자주 수행한다
