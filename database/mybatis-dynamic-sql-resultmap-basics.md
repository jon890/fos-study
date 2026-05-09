# [초안] MyBatis 기본기 — XML Mapper, resultMap, 동적 SQL, 운영 패턴 정리

## 왜 지금 다시 보는가

JPA 위주로 작업해 왔더라도, 레거시 비중이 큰 SI/유통 도메인에서는 MyBatis 코드를 읽고 고치는 능력이 곧 합류 첫 달의 생산성을 결정한다. CJ푸드빌처럼 메뉴/매장/가격/영양 같은 도메인 데이터가 다양한 외부 시스템과 맞물리는 환경에서는 단순 CRUD보다 동적 조건 검색, 다중 RESULT 매핑, 대량 INSERT/UPDATE, 통계 집계 쿼리가 자주 등장한다. 그리고 이 영역은 JPA가 손해를 보는 영역과 겹친다. 따라서 면접에서도 "JPA만 써 봤다"는 답보다 "JPA가 강한 부분과 MyBatis로 가는 게 합리적인 부분을 구분해서 써 왔다"는 답이 훨씬 안전하다.

이 문서는 MyBatis를 처음 배우는 입문서가 아니라, JPA에 익숙한 백엔드 엔지니어가 면접 직전에 다시 정렬해 두기 위한 정리다. 개념을 길게 늘어놓기보다, 실제로 자주 틀리는 지점과 운영 중 만나는 함정을 우선한다.

## 핵심 개념 한 번에 정렬

MyBatis는 SQL을 직접 적되, 파라미터 바인딩과 결과 매핑을 자동화해 주는 SQL 매퍼 프레임워크다. JPA가 "객체 모델로부터 SQL을 자동 생성"하는 방향이라면, MyBatis는 "SQL이 1급 시민이고 객체는 결과를 받는 그릇"에 가깝다. 다음 4가지가 뼈대다.

- **Mapper 인터페이스**: 자바 메서드 시그니처. 호출 진입점.
- **Mapper XML**: 같은 namespace로 묶인 SQL 정의. 메서드 id와 SQL을 잇는다.
- **parameterType / 자동 추론**: 메서드 파라미터를 SQL 안 `#{}`에 바인딩.
- **resultType / resultMap**: SQL 결과를 자바 객체로 매핑.

가장 자주 혼동하는 부분이 `#{}` vs `${}`다. `#{}`는 PreparedStatement 바인딩 변수로 들어가서 SQL 인젝션이 차단된다. `${}`는 단순 문자열 치환이다. ORDER BY 컬럼명, 동적 테이블명처럼 PreparedStatement가 바인딩할 수 없는 자리에서만 `${}`를 쓰고, 그때도 화이트리스트로 검증한 값만 넣는 게 운영 규칙이다.

## XML Mapper 기본 골격

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "https://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.menu.MenuMapper">

  <resultMap id="menuResult" type="com.example.menu.Menu">
    <id     property="menuId"    column="menu_id"/>
    <result property="storeId"   column="store_id"/>
    <result property="name"      column="name"/>
    <result property="price"     column="price"/>
    <result property="status"    column="status"/>
    <result property="createdAt" column="created_at"/>
  </resultMap>

  <select id="findById" resultMap="menuResult">
    SELECT menu_id, store_id, name, price, status, created_at
      FROM menu
     WHERE menu_id = #{menuId}
  </select>
</mapper>
```

이 구조에서 가장 많이 실수하는 지점은 두 가지다. 첫째, `namespace`가 인터페이스 fully-qualified name과 정확히 일치하지 않으면 mapper 바인딩 자체가 실패한다. 둘째, `<resultMap>`의 `<id>` 태그를 빠뜨리고 `<result>`만 쭉 나열하면, 동일 부모/자식 row가 묶일 때 PK 식별이 안 돼서 같은 부모 객체가 여러 개 생성되는 식의 미묘한 버그가 생긴다.

## resultType vs resultMap을 갈라 쓰는 기준

단일 테이블 조회면 `resultType="com.example.menu.Menu"` 한 줄로 끝낸다. 컬럼명을 카멜케이스로 바꾸려면 SQL 별칭을 쓰거나 MyBatis 설정에서 `mapUnderscoreToCamelCase=true`를 켜면 된다. 운영 코드에서 이 옵션은 거의 기본값처럼 켜 두는 편이 매핑 보일러플레이트를 줄여 준다.

`resultMap`은 다음 상황에서 강제된다.

- 컬럼명-필드명 규칙이 자동 변환으로 안 떨어지는 경우
- 1:N, 1:1 관계를 한 번의 조회로 묶어 가져오는 경우 (`<association>`, `<collection>`)
- 일부 필드를 무시하거나, JdbcType/타입핸들러를 명시해야 하는 경우

```xml
<resultMap id="menuWithOptions" type="com.example.menu.Menu">
  <id     property="menuId" column="menu_id"/>
  <result property="name"   column="name"/>
  <result property="price"  column="price"/>
  <collection property="options" ofType="com.example.menu.MenuOption">
    <id     property="optionId" column="option_id"/>
    <result property="label"    column="option_label"/>
    <result property="extra"    column="option_extra"/>
  </collection>
</resultMap>

<select id="findMenuWithOptions" resultMap="menuWithOptions">
  SELECT m.menu_id, m.name, m.price,
         o.option_id, o.option_label, o.option_extra
    FROM menu m
    LEFT JOIN menu_option o ON o.menu_id = m.menu_id
   WHERE m.menu_id = #{menuId}
</select>
```

이 패턴은 JPA의 fetch join과 같은 효과를 낸다. JPA보다 좋은 점은 SQL이 그대로 보이기 때문에 인덱스 적합성, JOIN 순서를 직접 통제할 수 있고, EXPLAIN으로 바로 검증 가능하다는 것이다. 단점은 컬럼명을 손으로 맞춰야 하므로 스키마 변경에 대한 회귀 비용이 JPA보다 크다.

## parameterType과 바인딩 규칙

파라미터가 단일 값이면 `#{}` 안에 아무 이름이나 써도 되지만, 협업 코드에서는 `@Param`을 명시적으로 거는 게 안전하다.

```java
public interface MenuMapper {
    Menu findById(@Param("menuId") Long menuId);

    List<Menu> search(@Param("cond") MenuSearchCond cond,
                      @Param("page") PageRequest page);
}
```

여러 파라미터가 들어가면 `@Param`을 안 쓸 때 MyBatis가 `param1`, `param2`로 바인딩하기 때문에 XML에서 `#{param1}`처럼 의미 없는 이름을 쓰게 된다. 6개월 뒤 코드 읽기가 매우 괴로워진다. 운영 룰로 "다중 파라미터 메서드는 무조건 `@Param`"을 박아 두는 편이 낫다.

`Map<String, Object>` 파라미터는 동적 검색 조건처럼 키가 가변일 때만 쓰고, 정적 도메인에서는 전용 condition DTO를 만든다. Map을 쓰면 컴파일 타임에 오타가 잡히지 않는다.

## 동적 SQL — if / choose / foreach / where / set

동적 SQL이 MyBatis가 살아남은 진짜 이유다. 문자열 concatenation 없이 조건을 합치고, 끝에서 어색한 `AND`나 `,`를 자동 정리해 준다.

```xml
<select id="search" resultMap="menuResult">
  SELECT menu_id, store_id, name, price, status, created_at
    FROM menu
  <where>
    <if test="cond.storeId != null">
      AND store_id = #{cond.storeId}
    </if>
    <if test="cond.keyword != null and cond.keyword != ''">
      AND name LIKE CONCAT('%', #{cond.keyword}, '%')
    </if>
    <if test="cond.statuses != null and cond.statuses.size() > 0">
      AND status IN
      <foreach collection="cond.statuses" item="s" open="(" separator="," close=")">
        #{s}
      </foreach>
    </if>
    <if test="cond.minPrice != null">
      AND price &gt;= #{cond.minPrice}
    </if>
  </where>
  ORDER BY menu_id DESC
  LIMIT #{page.size} OFFSET #{page.offset}
</select>
```

`<where>`는 첫 조건 앞의 `AND`를 자동으로 떼 주고, 모든 조건이 false면 `WHERE` 키워드 자체를 출력하지 않는다. `<set>`은 UPDATE 문에서 같은 역할을 한다.

`<choose>`는 여러 조건 중 하나만 적용할 때 쓴다. 정렬 기준이 동적인 케이스에서 자주 등장한다.

```xml
<choose>
  <when test="sort == 'PRICE_ASC'">  ORDER BY price ASC </when>
  <when test="sort == 'PRICE_DESC'"> ORDER BY price DESC </when>
  <otherwise>                        ORDER BY menu_id DESC </otherwise>
</choose>
```

여기서 `sort` 값을 `${sort}`로 직접 박지 않고 `<choose>`로 화이트리스트화하는 게 핵심이다. 정렬 컬럼을 외부 입력으로 받는 코드는 SQL 인젝션의 단골 진입점이다.

## SQL Injection — 절대 흐트러지면 안 되는 규칙

- WHERE 값, IN 절 원소, LIMIT/OFFSET 숫자: 모두 `#{}`만 쓴다.
- ORDER BY 컬럼, 테이블명, 동적 컬럼명: `${}`가 필요할 수 있다. 이때는 enum/화이트리스트 검증을 거친 값만 통과시킨다.
- LIKE 절: `'%' || ? || '%'`가 아니라 `CONCAT('%', #{kw}, '%')` 같이 DB 함수로 합친다. 자바에서 `"%"+kw+"%"`로 합쳐 넘기면 `%`, `_` 와일드카드를 사용자 입력이 그대로 갖게 되므로, 정책에 맞춰 escape를 별도로 처리한다.

면접에서 "MyBatis에서 SQL 인젝션은 어떻게 막나요"라는 질문이 나오면, `#{}`/`${}` 차이와 ORDER BY 같은 자리에서 화이트리스트로 보강한다는 두 축을 1분 안에 답할 수 있어야 한다.

## 페이징 — LIMIT/OFFSET vs 키셋

가장 흔한 구현은 `LIMIT #{size} OFFSET #{offset}`이다. 단순하지만 OFFSET이 커질수록 "건너뛸 row를 읽고 버리는" 비용이 선형 증가한다. 메뉴/매장 목록처럼 수십만 row 이하라면 충분하다.

데이터가 더 커지거나, 정렬 키가 단조 증가하는 경우엔 키셋 페이징을 쓴다.

```xml
<select id="searchKeyset" resultMap="menuResult">
  SELECT menu_id, name, price
    FROM menu
   WHERE store_id = #{storeId}
  <if test="lastMenuId != null">
     AND menu_id &lt; #{lastMenuId}
  </if>
   ORDER BY menu_id DESC
   LIMIT #{size}
</select>
```

이 방식은 정렬 컬럼이 인덱스의 leading column일 때만 효과를 본다. EXPLAIN의 `key`, `rows`를 같이 봐 두면 면접 답변 깊이가 달라진다.

`COUNT(*)` 쿼리는 본 쿼리와 별도 select id로 분리한다. WHERE 조건 동적 SQL을 두 군데 중복해 작성하기 싫으면 `<sql>` + `<include>` 조합으로 조건절을 공유한다.

```xml
<sql id="menuWhere">
  <where>
    <if test="cond.storeId != null"> AND store_id = #{cond.storeId} </if>
    <if test="cond.keyword != null and cond.keyword != ''">
      AND name LIKE CONCAT('%', #{cond.keyword}, '%')
    </if>
  </where>
</sql>

<select id="searchCount" resultType="long">
  SELECT COUNT(*) FROM menu <include refid="menuWhere"/>
</select>
```

## Batch — 대량 INSERT/UPDATE 패턴

영양/가격 일괄 갱신 같은 운영성 잡에서 쓰는 두 가지 길.

1) `<foreach>`로 다중 row INSERT를 만든다.

```xml
<insert id="insertMenuPrices">
  INSERT INTO menu_price (menu_id, price, valid_from)
  VALUES
  <foreach collection="list" item="p" separator=",">
    (#{p.menuId}, #{p.price}, #{p.validFrom})
  </foreach>
</insert>
```

장점: 단일 SQL이라 round-trip이 1번이다. 단점: row가 수만 건 단위가 되면 SQL 길이/패킷 크기 한계, 파서 비용이 문제가 된다. 보통 500\~2000건 단위로 청크를 끊어 호출한다.

2) `ExecutorType.BATCH` SqlSession을 열어 PreparedStatement에 addBatch/executeBatch 흐름을 태운다. Spring에서는 별도 SqlSessionTemplate을 BATCH 모드로 만들고, 트랜잭션 안에서 mapper 메서드를 반복 호출한다. 멱등성이 필요한 경우 `INSERT ... ON DUPLICATE KEY UPDATE`(MySQL 8) 같은 upsert 구문을 같이 사용한다.

면접에서는 "둘 중 무엇을 언제 쓰는가"를 묻는다. 답: 데이터 크기가 작고 명백히 한 트랜잭션이면 multi-row INSERT, 양이 크고 사용자별 row 빌드 로직이 자바 단에 있으면 BATCH executor.

## JPA와 혼용 — 트랜잭션, 1차 캐시, flush 타이밍

레거시에서 JPA로 점진 이행 중인 프로젝트는 한 트랜잭션 안에서 JPA와 MyBatis가 같은 데이터를 만지는 일이 흔하다. 함정 두 가지.

- **flush 타이밍**: JPA로 엔티티를 저장하고 같은 트랜잭션 안에서 MyBatis로 SELECT 하면, JPA의 변경분이 아직 DB에 flush 되지 않아 MyBatis 쿼리가 옛 상태를 본다. JPA `EntityManager.flush()`를 명시 호출하거나, 갱신 -> 조회 흐름을 같은 도구로 맞춘다.
- **1차 캐시 불일치**: JPA의 1차 캐시는 MyBatis가 만진 변경을 모른다. MyBatis로 UPDATE한 후 같은 트랜잭션 안에서 JPA로 같은 엔티티를 조회하면 JPA가 캐시된 옛 값을 돌려줄 수 있다. 필요한 경우 `entityManager.clear()`로 컨텍스트를 비우거나, 해당 흐름을 한쪽 도구로 통일한다.

트랜잭션 매니저는 같은 DataSource를 쓰면 Spring `DataSourceTransactionManager` 하나로 충분하다. 두 도구가 같은 PlatformTransactionManager를 공유하므로 `@Transactional` 한 번으로 둘 다 묶인다. 멀티 데이터소스가 되면 그때부터 어느 한쪽으로 통일하거나, 분산 트랜잭션이 아닌 사가/보상 패턴 같은 application-level 일관성 전략을 검토해야 한다.

## 레거시 mapper를 빠르게 읽는 방법

처음 들어간 프로젝트의 mapper XML을 빠르게 파악하는 순서.

1. `namespace`를 보고 대응 인터페이스를 찾는다. IDE에서 namespace 클릭 → 인터페이스로 점프.
2. `<resultMap>`을 먼저 본다. 도메인 형태가 한눈에 들어온다.
3. `<sql>` 조각을 본다. 이것이 어떤 조건절/컬럼셋을 공통으로 쓰는지 보여 준다.
4. 가장 긴 select를 EXPLAIN에 그대로 붙여 본다. 인덱스 가정이 맞는지 즉시 확인 가능.
5. 각 select의 `id`로 해당 메서드 사용처를 검색한다. 도메인 흐름이 거꾸로 보인다.

수정할 때 가장 위험한 건 동적 SQL의 조건 누락이다. `<if test="...">`가 false가 되면 그 라인 자체가 사라지므로, 테스트 데이터에서는 통과하다가 운영에서 빈 검색 결과나 의도치 않은 전체 스캔이 발생한다. 실제 호출 케이스를 XML 옆에 주석으로 적어 둔 코드면 다행이고, 아니면 mapper 단위 테스트가 사실상 회귀 안전망이 된다.

## 로컬 실습 환경 (MySQL 8 + Spring Boot 3 + MyBatis)

`docker compose`로 MySQL을 띄우고 동일 스키마에 대해 동작하는 최소 예제를 만들어 둔다.

`docker-compose.yml`:

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: lab
    ports:
      - "3306:3306"
```

스키마:

```sql
CREATE TABLE menu (
  menu_id    BIGINT       NOT NULL AUTO_INCREMENT,
  store_id   BIGINT       NOT NULL,
  name       VARCHAR(100) NOT NULL,
  price      INT          NOT NULL,
  status     VARCHAR(20)  NOT NULL,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (menu_id),
  KEY ix_menu_store_status (store_id, status, menu_id)
);

CREATE TABLE menu_option (
  option_id     BIGINT NOT NULL AUTO_INCREMENT,
  menu_id       BIGINT NOT NULL,
  option_label  VARCHAR(100) NOT NULL,
  option_extra  INT NOT NULL DEFAULT 0,
  PRIMARY KEY (option_id),
  KEY ix_menu_option_menu (menu_id)
);
```

Spring Boot 의존성: `mybatis-spring-boot-starter`, `mysql-connector-j`. `application.yml`에서 `mybatis.mapper-locations=classpath:mapper/*.xml`, `mybatis.configuration.map-underscore-to-camel-case=true`만 잡으면 위 XML들이 그대로 동작한다.

연습 과제 4가지를 권장한다.

1. `MenuMapper.search`를 만들고 storeId/keyword/statuses 조합 케이스 6개에 대해 mapper 단위 테스트를 짠다. 각 케이스마다 `<if>` 분기 한 줄씩이 켜지고 꺼지는지 SQL 로깅으로 직접 확인한다.
2. `findMenuWithOptions`를 LEFT JOIN 1회 호출과 2-step 조회(menu 1번 + options N번) 두 방식으로 만들어 본 뒤, 옵션이 평균 5개일 때와 50개일 때 각각 응답 시간을 비교한다.
3. 1만 건 가격을 갱신하는 잡을 multi-row INSERT 청크 1000건 vs BATCH ExecutorType 두 방식으로 만들어 시간/메모리를 비교한다.
4. 같은 트랜잭션 안에서 JPA로 메뉴를 저장한 직후 MyBatis로 같은 storeId를 조회해, flush가 일어났는지/안 했는지를 SQL 로그로 확인한다.

## 흔한 실수 패턴

- `${}`로 검색어를 그대로 박아 둔 코드. 인젝션 직격이다. 코드 리뷰에서 가장 먼저 잡아야 한다.
- `<resultMap>`에 `<id>`를 빠뜨리고 1:N 매핑을 시도한 코드. 부모 row가 자식 수만큼 중복으로 만들어진다.
- `@Param`을 안 쓴 다중 파라미터 메서드. `param1`, `param2`로 도배된 XML이 된다.
- `<if test="status != null and status != ''">`에서 `status`가 String이 아니라 enum일 때도 `!= ''` 비교를 그대로 둔 코드. 의미는 없지만 OGNL 평가 비용을 매번 낸다.
- LIMIT/OFFSET을 `${}`로 받은 코드. 숫자 검증 없이 들어오면 인젝션 가능.
- 동적 ORDER BY를 `${sort}`로 직접 받은 코드. 화이트리스트 분기로 바꿔야 한다.

## 면접 답변 프레이밍

"JPA와 MyBatis 중 무엇을 선호하는가"가 가장 자주 나오는 질문이다. 정답이 정해진 질문이 아니므로, 다음 골격으로 답한다.

> 도메인 모델을 풍부하게 가져가는 트랜잭션 흐름은 JPA가 유리합니다. 영속성 컨텍스트가 변경 추적과 1차 캐시를 처리해 주기 때문에 코드 양이 줄고, fetch join, dirty checking, optimistic lock 같은 도구가 표준화되어 있습니다. 반대로 통계, 동적 검색, 복잡한 JOIN, 리포팅성 SQL은 MyBatis가 유리합니다. SQL이 1급 시민이라 EXPLAIN으로 바로 튜닝할 수 있고, 인덱스 활용을 직접 통제할 수 있습니다. 실제 프로젝트에서는 도메인 트랜잭션은 JPA로, 검색/배치/리포팅은 MyBatis로 나눠 쓰는 게 무난한 절충이었습니다.

"MyBatis에서 SQL 인젝션을 막는 원칙"은 `#{}`/`${}` 구분과 화이트리스트 보강을 두 축으로 답한다. "1:N 매핑 어떻게 하느냐"는 resultMap의 `<collection>` + `<id>` 중요성으로 답한다. "대량 INSERT는 어떻게 처리했나"는 multi-row INSERT vs BATCH executor 비교와 청크 사이즈 결정 근거로 답한다. "JPA와 같이 쓰면 주의할 점"은 flush 타이밍과 1차 캐시 일관성으로 답한다. 4개의 답이 모두 1\~2분 안에 떨어져야 한다.

## 체크리스트

- [ ] `#{}`와 `${}`의 차이를 즉답할 수 있고, `${}`가 필요한 자리를 화이트리스트로 보강하는 코드를 적을 수 있다.
- [ ] 1:N 관계를 `<resultMap>` + `<collection>`으로 매핑할 수 있고, `<id>`를 빠뜨리면 어떤 버그가 나는지 설명할 수 있다.
- [ ] `<where>`, `<set>`, `<choose>`, `<foreach>`를 모두 사용해 동적 검색 mapper를 빈 상태에서 작성할 수 있다.
- [ ] `<sql>`/`<include>`로 조건절을 공유하고, 같은 조건으로 list/count 두 select를 만들 수 있다.
- [ ] 키셋 페이징을 인덱스 leading column 기준으로 작성할 수 있고, OFFSET 페이징의 비용을 EXPLAIN으로 설명할 수 있다.
- [ ] multi-row INSERT와 BATCH executor를 각각 언제 쓰는지 답할 수 있고, 청크 사이즈 결정 근거를 댈 수 있다.
- [ ] JPA + MyBatis 동일 트랜잭션에서 flush/clear가 필요한 시점을 사례로 설명할 수 있다.
- [ ] 레거시 mapper XML을 처음 받았을 때 namespace → resultMap → sql 조각 → EXPLAIN 순으로 분석하는 흐름을 따라갈 수 있다.
