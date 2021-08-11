# Error Handling in React 16

- https://ko.reactjs.org/blog/2017/07/26/error-handling-in-react-16.html

- 컴포넌트 안의 자바스크립트 에러를 어떻게 처리하는 방법에 대한 몇 가지 변경 사항을 발표하고자 한다

- React 15 및 이전 버전의 동작
- 이전에는, 컴포넌트안의 자바스크립트 에러는 리액트의 내부 상태를 오염시키고 다음 렌더에 숨은(cryptic) 에러를 방출 시켰다
- 이러한 에러는 항상 애플리케이션 코드의 이전 에러로 인해 발생했지만 React는 컴포넌트에서 이를 정상적으로 처리하는 방법을 제공하지 않았고 복구할 수 없었다

## 에러 바운더리 (Error Boundaries) 소개

- UI 일부의 JavaScript 에러로 인해 전체 앱이 중단되어서는 안 된다
- React 사용자를 위해 이 문제를 해결하기 위해 React 16에서는 에러 바운더리라는 새로운 개념을 도입했다

- 에러 바운더리는 자식 구성 요소 트리의 모든 위치에서 JavaScript 에러를 포착하고 해당 에러를 기록하고 충돌한 구성 요소 트리 대신 대체 UI를 표시하는 React의 컴포넌트이다
- 에러 바운더리는 렌더린 중, 라이프 사이클 메서드 및 그 아래 전체 트리 생성자에서 에러를 잡는다

- 클래스 컴포넌트는 다음과 같은 새 라이프 사이클 메서드를 정의하는 경우 에러 바운더리가 된다
- componentDidCatch(error, info)

```
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }

    componentDidCatch(error, info) {
        // Display fallback UI
        this.setState({ hasError: true });
        // You can also log the error to an error reporting service
        logErrorToMyService(error, info);
    }

    render() {
        if (this.state.hasError) {
            return <h1>무언가가 잘못되었습니다!</h1>;
        }

        return this.props.children;
    }
}
```

- 그런 다음 컴포넌트로 사용할 수 있다

```
<ErrorBoundary>
    <MyWidget />
</ErrorBoundary>
```

- 이 componentDidCatch() 메서드는 JavaScript catch {} 블록 처럼 작동하지만 컴포넌트 용이다
- 클래스 컴포넌트만 에러 바운더리가 될 수 있다
- 실제로 대부분의 경우 에러 바운더리 컴포넌트를 한 번 선언하고 애플리케이션 전체에서 사용하려고 한다

- <b>에러 바운더리는 트리에서 그 아래에 있는 컴포넌트의 오류만 잡는다</b>는 점에 유의하자
- 에러 바운더리 자체 내의 오류는 잡을 수 없다
- 에러 바운더리가 에러 메시지를 렌더링하는데 실패하면 에러는 그 위의 가장 가까운 에러 바운더리로 전파된다
- 이 역시 JavaScript에서 catch {} 블록이 작동 하는 방식과 유사하다

## 에러 바운더리를 배치할 위치

- 에러 바운더리의 세분화는 사용자에게 달려 있다
- 서버 측 프레임워크가 종종 충돌(crash) 처리하는 것처럼 최상위 컴포넌트를 감싸(wrapping) 사용자에게 "문제가 발생했습니다" 메시지를 표시할 수 있다
- 또한 애플리케이션 나머지 부분이 충돌하지 않도록 개별 위젯을 에러 바운더리로 감쌀 수 있다

## 잡지 않은 에러에 대한 새로운 동작

- React 16부터 에러 바운더리에 의해 포착되지 않은 에러는 전체 React 컴포넌트 트리의 마운트 해제로 이어진다

- 우리는 이 결정에 대해 논의했다
- 경험상 손상된 UI를 완전히 제거하는 것보다 그대로 두는 것이 더 나쁘다
- 예를 들어 Messenger와 같은 제품에서 깨진 UI를 표시하면 누군가 잘못된 사람에게 메시지를 보낼 수 있다

- 이 변경은 React 16으로 마이그레이션할 때 이전에 눈치채지 못했던 기존 충돌을 애플리케이션에서 발견할 가능성이 있음을 의미한다
- 에러 바운더리를 추가하면 문제가 발생했을 때 더 나은 사용자 경험을 제공할 수 있다

- 예를 들어 Facebook Messenger는 사이드바, 정보 패널, 대화 로그 및 메시지 입력 내용을 별도의 에러 바운더리로 감싼다
- 이러한 UI 영역 중 하나의 일부 구성 요소가 충돌하는 경우 나머지 구성 요소는 대화형으로 유지된다

## 구성 요소 스택 추적

- React 16은 애플리케이션이 실수로 오류를 삼켰더라도(swallow) 개발 중인 콘솔에 렌더링하는 동안 발생한 모든 에러를 출력한다
- 에러 메시지 및 JavaScript 스택 외에도 컴포넌트 스택 추적도 제공한다
- 이제 컴포넌트 트리에서 에러가 발생한 위치를 정확히 확인할 수 있다

- Create React App 프로젝트에서 기본적으로 작동 한다
- 만약 Create React App을 사용하지 않는 경우
- https://www.npmjs.com/package/babel-plugin-transform-react-jsx-source
- 플러그인을 Babel 구성에 수동으로 추가할 수 있다
- <b>개발 전용이며 프로덕션 환경에서는 비활성화해야 한다</b>

## try/catch를 사용하지 않는 이유는 무엇일까?

- try/catch는 훌륭하지만 명령형 코드에서만 작동한다
- React 컴포넌트는 선언적이며 <i>무엇</i>을 렌더링해야 <i>하는지</i> 지정 한다
- 에러 바운더리는 React의 선언적 특성을 유지하고 예상대로 작동한다
