# Http Client

- Node.js 진영에서의 Http Client들

  - **1. Node.js native fetch**

    - Node 18 이상은 브라우저 fetch가 기본 탑재됨
    - 가장 중요한 포인트
      - Node 18부터 fetch가 기본 내장
      - Node 20부터 안정성 + 성능 올라가면서 완전 실용적
      - Node 팀은 fetch 사용을 권장하는 방향으로 감
    - 장점
      - 브라우저 API와 100% 동일
      - 별도 패키지 설치 필요 없음
      - ES module 친화적
      - async/await 기반으로 사용성 좋음
      - JSON, stream, blob 처리도 좋음
    - 단점
      - axios 같은 request/response interceptor 기능 부족
      - timeout/retry 기능 부족
      - multipart/form-data는 다소 번거로움
    - 결론
      > 브라우저/Node 양쪽을 모두 고려한 가장 모던한 선택. </br>
      > 99% 경우 fetch면 충분

  - **2. undici (Node 공식 HTTP 라이브러리)**

    - Node 팀에서 만든 가장 빠르고 안정적인 HTTP/1.1 클라이언트
    - 심지어 Node 내부에서도 http 모듈보다 undici가 더 빠름
    - 그리고 이게 중요함
      - **Node의 fetch 구현도 내부적으로 undici 기반이다**
    - 그래서
      > fetch는 "편의 API", undici는 "더 낮은 레벨 + 고성능 API"
    - 장점
      - 매우 빠름 (axios, got보다 빠름)
      - Node 공식 팀에서 직접 관리
      - HTTP Connection pool 지원
      - 매우 안정적
      - stream 처리 우수
      - fetch보다 고급 기능 많음
    - 단점
    - axios처럼 편의성 높은 API는 아님
    - 브라우저 호환 API 아님
    - 옵션이 상대적으로 저수준
    - 결론
      > 성능, 안정성, Node 공식성 면에서 최고의 선택 </br>
      > Node 백엔드라면 fetch + undici 조합이 현재 표준

  - **3. axios - 전통의 강자 (하지만 2025년 기준 만능은 아님)**

    - 장점
      - request/response interceptor
      - transform, default config, instance
      - form-data 자동 처리
      - 에러 핸들링 편함
      - 레거시 프로젝트에서 압도적으로 많음
    - 단점
      - CJS 중심이라 Tree-Shaking 약함
      - fetch 시대 기준으로 무거움
      - 성능이 undici보다 떨어짐
      - Node 환경에서는 fetch 대비 이점 적음
    - 결론
      > 레거시/기업용 프로젝트에서는 여전히 많이 쓰지만 </br>
      > 모던 Node.js에서는 꼭 필요한 도구는 아님

  - **4. ky - fetch 기반 ES module HTTP 클라이언트**

    - 브라우저용으로 만들었지만 Node에서도 잘 돌아감
    - 장점
      - fetch 기반 -> 브라우저/Node 모두 동일하게 사용
      - 훨씬 가벼움 (axios 대비)
      - retry, timeout, hooks 지원
      - 타입스크립트 지원 매우 좋음
    - 단점
      - Node 환경에서는 undici만큼 빠르지 않음
      - fetch wrapper라 아주 복잡한 기능은 제한적
    - 결론
      > SPA/BFF/프론트 특별히 fetch 지향 프로젝트에 좋음
      > Node 단독 서버라면 undici 대비 장점은 적다

  - **5. got - 기능 많은 Node 전용 HTTP 클라이언트**

    - 유럽 개발자들 사이에서 여전히 인기가 많고, axios보다 "Node 환경에 더 맞는" 라이브러리
    - 장점
      - retry, timeout, caching, agents, pagination, streams 등 기능 매우 풍부
      - 플러그인 시스템 뛰어남
      - 에러 메시지가 아주 친절
      - promisify 기반의 API 완성도 높음
    - 단점
      - esbuild/swc 번들에서 약간 무거움
      - 브라우저 환경에서는 사용 불가
      - fetch가 내장된 시대에는 우선순위 떨어짐
    - 결론
      > Node 전용 고급 HTTP 유틸 필요하면 아직도 강하게 선호됨 </br>
      > 하지만 Node 공식 fetch 시대에서는 위상이 예전보다 낮아짐
