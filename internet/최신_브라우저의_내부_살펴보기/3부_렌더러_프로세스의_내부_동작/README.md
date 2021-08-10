# 최신 브라우저의 내부 살펴보기를 읽고

# 3부 - 렌더러 프로세스의 내부 동작

- https://d2.naver.com/helloworld/5237120
- 원문 : https://developers.google.com/web/updates/2018/09/inside-browser-part3 (by. Mariko Kosaka)

- 시리즈 세 번째 글에서는 렌더러 프로세스가 HTML 문서를 받았을 때 어떤 절차를 거쳐 화면을 구성하는지를 설명합니다
- 이 과정을 효율적으로 처리하기 위해 렌더러 프로세스가 어떤 아키텍처를 가지고 있는지 살펴봅니다
- 또한 웹 개발자가 고려하면 좋을 내용을 소개합니다

## 렌더러 프로세스의 내부 동작

- 렌더러 프로세스는 여러 측면에서 웹 페이지의 성능에 영향을 미침
- 렌더러 프로세스 내부에서 많은 일이 일어나기 떄문에 이 글은 개요 수준의 일반적인 내용을 다룸
- 더 알아보려면 => Google Developers => Web Fundamentals => Performance
- https://developers.google.com/web/fundamentals/performance/why-performance-matters/

### 렌더러 프로세스는 웹 콘텐츠를 처리한다

- 렌더러 프로세스는 탭 내부에서 발생하는 모든 작업을 담당
- 렌더러 프로세스의 메인 스레드가 브라우저로 전송된 대부분 코드를 처리
- 간혹 웹 워커나 서비스 워커를 사용하는 경우에는 워커 스레드가 JavaScript 코드의 일부를 처리
- 웹 페이지를 효율적이고 부드럽게 렌더링하기 위해 별도의 컴포지터 스레드와 래스터 스레드가 렌더러 프로세스에서 실행

- 렌더러 프로세스의 주요 역할은 HTML과 CSS, JavaScript를 사용자와 상호작용을 할 수 잇는 웹 페이지로 변환하는 것이다

## 파싱

### DOM 구축

- 페이지를 이동하는 내비게이션 실행 메시지를 렌더러 프로세스가 받음
- HTML 데이터를 수신하기 시작
- 렌더러 프로세스의 메인 스레드는 문자열(HTML)을 파싱해서 DOM(Document object model)으로 변환하기 시작

- DOM은 브라우저가 내부적으로 웹 페이지를 표현하는 방법
- 또한 JavaScript를 통해 상호작용을 할 수 있는 데이터 구조이자 API

- HTML 문서를 DOM으로 파싱하는 방법은 HTML 표준에 정의
  https://html.spec.whatwg.org/
- 브라우저에서 HTML 문서를 열었을 때 오류를 반환받은 적이 없었을 것
- 예를 들어 닫는 &lt;/p&gt; 태그가 누락된 HTML도 유효한 HTML이다
- 오류를 우아하게 처리하도록 HTML 명세가 설계됐기 때문
- 이러한 일이 어떻게 처리되는지 궁금하다면 아래의 글을 읽어보기  
  https://html.spec.whatwg.org/multipage/parsing.html#an-introduction-to-error-handling-and-strange-cases-in-the-parser

### 하위 리소스 (subresource) 로딩

- 웹 사이트는 일반적으로 이미지, CSS, JavaScript와 같은 외부 리소스를 사용
- 이러한 파일은 네트워크나 캐시에서 로딩해야 함
- 속도를 높이기 위해 '프리로드(Preload) 스캐너'가 동시에 실행
- HTML 문서에 img, link 같은 태그가 있으면 프리로드 스캐너는 HTML 파서가 생성한 토큰을 확인하고 브라우저 프로세스의 네트워크 스레드에 요청을 보냄

![subresource](https://user-images.githubusercontent.com/36876250/128839963-64f23753-2bb2-4b31-b876-30f9aed16ffe.png)

### 자바 스크립트가 파싱을 막을 수 있다

- script 태그를 만나면 HTML 파서는 HTML 문서의 파싱을 일시 중지한 다음 JavaScript 코드를 로딩하고 파싱해 실행해야 한다
- 왜 그럴까?
- JavaScript는 DOM 구조 전체를 바꿀 수 있는 document.write() 메서드와 같은 것을 사용해 문서의 모양을 변경할 수 있기 때문이다
- HTML 파싱을 재개하기 전에 HTML 파서는 JavaScript의 실행이 끝나기를 기다려야 한다
- JavaScript를 실행할 때 어떤 일이 발생하는지 궁금하다면 https://mathiasbynens.be/notes/shapes-ics 글의 영상과 내용을 참고한다

### 리소스를 어떻게 로딩하길 원하는지 브라우저에 힌트를 주는 방법

- 웹 개발자가 브라우저에 리소스 로딩에 대한 힌트를 보내는 방법에는 여러 가지가 있다
- JavaScript에서 document.write() 메서드를 사용하지 않는다면 script 태그에 async 속성이나 defer 속성을 추가할 수 있다
- 이 속성이 있으면 브라우저가 JavaScript 코드를 비동기적으로 로딩하고 실행하면서 HTML 파싱을 막지 않는다
- JavaScript 모듈을 사용할 수도 있다
- &lt;link rel="preload"&gt;는 현재 내비게이션을 실행하기 위해 리소스가 반드시 필요하다는 것을 브라우저에 알려서 리소스를 가능한 한 빨리 다운로드하려는 경우에 사용할 수 있다
- 브라우저에 힌트를 주는 방법에 관해 더 알고 싶다면 https://developers.google.com/web/fundamentals/performance/resource-prioritization 를 참고한다

### 스타일 계산

- 메인 스레드는 CSS를 파싱하고 각 DOM 노드에 해당되는 계산된 스타일(computed style)을 확정한다
- 계산된 스타일은 CSS 선택자(selector)로 구분되는 요소에 적용될 스타일에 관한 정보이다
- 개발자 도구의 <b>computed</b> 패널에서 이 정보를 볼 수 있다

- CSS를 전혀 적용하지 않아도 DOM 노드에는 계산된 스타일이 적용되어 있다
- h1 태그는 h2 태그보다 크게 표시되며 바깥 여백(margin)이 모든 요소에 적용된다
- 브라우저에 기본 스타일 시트가 있기 때문이다
- Chromium 소스 코드의 html.css https://cs.chromium.org/chromium/src/third_party/blink/renderer/core/html/resources/html.css

### 레이아웃

- 이제 렌더러 프로세스가 문서의 구조와 각 노드의 스타일을 알지만 페이지를 렌더링하기에는 충분하지 않다
- 레이아웃은 요소의 기하학적 속성(geometry)를 찾는 과정
- 메인 스레드는 DOM과 계산된 스타일을 훑어가며 레이아웃 트리를 만든다
- 레이아웃 트리는 x, y, 좌표, 박스 영역 (bounding box)의 크기와 같은 정보를 가지고 있다
- 레이아웃 트리는 DOM 트리와 비슷한 구조일 수 있지만 웹 페이지에 보이는 요소에 관련된 정보만 가지고 있다
- display: none속성이 적용된 요소는 레이아웃 트리에 포함되지 않는다
- 이와 비슷하게 p::before{content:"Hi!"} 속성과 같은 의사 클래스(pseudo class)의 콘텐츠는 DOM에는 포함되지 않지만 레이아웃 트리에는 포함된다

![layout](https://user-images.githubusercontent.com/36876250/128842531-b60c7e9f-8dba-4c52-9436-839f5a601167.png)

- 계산된 스타일이 있는 DOM 트리를 돌며 레이아웃 트리를 생성하는 메인 스레드

- 웹 페이지의 레이아웃을 결정하는 것은 어려운 작업
- 가장 단순하게 위에서 아래로 펼쳐지는 블록 영역 하나만 있는 웹 페이지의 레이아웃을 결정할 때에도 폰트의 크기가 얼마이고 줄 바꿈을 어디서 해야 하는지 고려해야 함
- 단락의 크기와 모양이 바뀔 수 있고, 다음 단락의 위치에 영향이 있기 때문

- CSS는 요소를 한쪽으로 흐르게(float) 하거나, 크기를 벗어난 부분을 보이지 않게 하거나, 글이 쓰이는 방향을 변경할 수 있음
- 레이아웃 단계가 엄청난 임무를 맡고 있다는 것을 알 수 있음
- Chrome에서는 한 팀이 레이아웃만 전담하고 있을 정도
- 레이아웃 전담 팀이 하는 일을 자세히 알고 싶다면 https://www.youtube.com/watch?v=Y5Xa4H2wtVA

- 파싱, 스타일 계산, 레이아웃에 관한 더 자세한 내용
- 브라우저는 어떻게 동작하는가? https://d2.naver.com/helloworld/59361

- 레이아웃 ~ 페인트 사이에 한 가지 작업이 더 있음
- 레이아웃 트리를 순회하면서 속성 트리(property tree)를 만드는 작업
- 속성 트리는 clip, transform, opacity등의 속성 정보만 가진 트리
- 기존에는 이런 정보를 분리하지 않고 노드마다 가지고 있었음
- 그래서 특정 노드의 속성이 변경되면 해당 노드의 하위 노드에도 이 값을 다시 반영하면서 노드를 순회해야 했음
- 최신 Chrome에서는 이런 속성만 별도로 관리하고 각 노드에서는 속성 트리의 노드를 참조하는 방식으로 변경되고 있음

### 페인트

- DOM, 스타일, 레이아웃을 가지고도 여전히 페이지를 렌더링할 수 없음
- 요소의 크기, 모양, 위치를 알더라도 어떤 순서로 그려야 할지 판단해야 함
- 예를 들어 어떤 요소에 z-index 속성이 적용되었다면 HTML에 작성된 순서로 요소를 그리면 잘못 렌더링된 화면이 나옴

- 페인트 단계에서 메인 스레드는 페인트 기록(paint record)을 생성하기 위해 레이아웃 트리를 순회 함
- 페인트 기록은 '배경 먼저, 다음은 텍스트, 그리고 직사각형'과 같이 페인팅 과정을 기록한 것

![paint_record](https://user-images.githubusercontent.com/36876250/128843673-da846339-21f9-4553-9f40-3d6bc255a64b.png)

#### 렌더링 파이프라인을 갱신하는 데는 많은 비용이 든다

- DOM 트리 및 스타일
- 레이아웃 트리
- 페인트 트리의 순서로 생성

- 렌더링 파이프라인에서 중요한 점 : 각 단계에서 이전 작업의 결과가 새 데이터를 만드는데 사용
- 예를 들어 레이아웃 트리에서 변경이 생겨 문서의 일부가 영향을 받으면 페인팅 순서도 새로 생성해야 함

- 요소에 애니메이션을 적용하면 브라우저는 모든 프레임 사이에서 이러한 작업을 해야 함
- 요소의 움직임이 모든 프레임에 반영되어야 사람이 볼 때 부드럽게 느껴짐
- 애니메이션에서 프레임이 누락되면 웹 페이지가 '버벅대는(janky)' 것처럼 보임

- 화면 주사율에 맞추어 렌더링 작업이 이루어져도 이 작업은 메인 스레드에서 실행되기 때문에 애플리케이션이 JavaScript르 실행하는 동안 렌더링이 막힐 수 있음
- JavaScript 작업을 작은 덩어리로 나누고 requestAnimationFrame() 메서드를 사용해 프레임마다 실행하도록 스케쥴을 관리할 수 있음
- 자세한 내용은 https://developers.google.com/web/fundamentals/performance/rendering/optimize-javascript-execution 을 참고
- 메인 스레드를 막지 않기 위해 웹 워커에서 JavaScript를 실행할 수 도 있음
  https://www.youtube.com/watch?v=X57mh8tKkgE

        참고
        requestAnimationFrame() 메서드를 통해 등록한 콜백 함수는 프레임마다 실행된다
        프레임의 간격은 모니터의 주사율에 따라 다를 수 있다
        브라우저는 VSync 시그널로 프레임 간격을 파악한다
        브라우저와 VSync에 관한 더 자세한 내용은
        "브라우저는 VSync를 어떻게 활용하고 있을까" 발표의 자료를 참고한다
        https://deview.kr/2015/schedule#session/87
