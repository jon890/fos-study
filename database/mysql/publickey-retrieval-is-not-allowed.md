# PublicKeyRetrieval is not allowed!

- 이 오류가 나는 원인은 무엇인가?

  - MySQL 8.x + `caching_sha2_password` 인증방식에서 나오는 오류
    - `Public Key Retrieval is not allowed`
    - `The public key is not available Client side`

- 오류의 진짜 원인

  - MySQL 8의 기본 인증 방식 : `caching_sha2_password`
    - MySQL 8부터 기본 인증 플러그인이 `mysql_native_password`에서 `caching_sha2_password`로 변경됨
    - 이때 클라이언트가 비밀번호 인증을 할 때, 서버의 RSA public key를 사용해서 암호화 통신을 하는 흐름이 있고, 그걸 클라이언트가 자동으로 가져오려고 할 떄 이런 제한이 걸림
      > "Public Key Retrieval is not allowed"
      > -> 클라이언트가 서버에서 공개키를 가져오려고 했는데, `allowPublicKeyRetrieval` 옵션이 false라서 막혔다는 뜻

- 언제 특히 잘 발생할까?
  - Docker로 MySQL 8을 띄워놓고
  - JDBC URL 또는 Node MySQL 연결 설정에서
    - SSL 설정이 애매하거나
    - `allowPublicKeyRetrieval=true` 안 넣었거나
    - 사용자 계정이 `caching_sha2_password`로 생성된 경우

## 운영환경에서도 필요한 옵션일까?

- 대부분 운영 DB 계정이 `mysql_native_password`로 생성되어 있기 때문
  - MySQL에서는 계정마다 인증 플러그인을 다르게 설정할 수 있음
- 운영환경은 대부분 SSL/TLS가 강제됨
  - AWS RDS / Aurora 같은 서비스에서는 기본적으로 SSL이 활성화 되어있다
  - 클라이언트 <-> 서버 간 비밀번호 암호화는 TLS로 처리
  - 더 이상 RSA public key 가져와서 암호화할 필요 없음
  - 그래서 public key retrieval이 아예 트리거되지 않음
