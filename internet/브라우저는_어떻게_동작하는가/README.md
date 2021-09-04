# 브라우저는 어떻게 동작하는가? 를 읽고

- https://d2.naver.com/helloworld/59361
- 원문 : "How Browsers Work: Behind the scenes of modern web browsers"
- http://www.html5rocks.com/en/tutorials/internals/howbrowserswork/
- 원작자는 몇 년간 브라우저 내부와 관련된 공개 자료를 확인 하고
- C++ 코드 수백만 줄 분량의 WebKit이나 Gecko 같은 오픈소스 렌더링 엔진의 소스 코드를 직접 분석하면서 어떻게 브라우저가 동작하는지 파악했다

## 소개

- 브라우저가 어떻게 동작하는지 설명
- 이 글을 읽고 나면, 주소 창에 www.naver.com을 입력했을 때 어떤 과정을 거쳐 페이지가 화면에 보이게 되는지 알게 될 것

## 이 글에서 설명하는 브라우저

- 오픈 소스 브라우저
- 파이어폭스, 크롬, 사파리

## 브라우저의 주요 기능

- 사용자가 선택한 자원을 서버에 요청하고 브라우저에 표시
- 자원 = 보통 HTML 문서, PDF, 이미지, 또 다른 형태
- 자원의 주소는 URI(Uniform Resource Identifier)에 의해 정해짐

- 브라우저는 HTML과 CSS명세에 따라 HTML 파일을 해석해서 표시
- 이 명세는 웹 표준화 기구인 W3C에서 정한다

## 브라우저의 기본 구조
