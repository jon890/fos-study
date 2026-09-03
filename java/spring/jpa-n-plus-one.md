---
tags: [study]
---

# JPA N+1: 발생 원인, 탐지와 해결 선택지

JPA N+1은 연관 엔티티를 조회하는 과정에서 최초 쿼리 1번 뒤에 결과 수만큼 추가 쿼리가 실행되는 문제다. 도메인 종류와 무관하게 연관 관계와 조회 경로가 맞물리면 발생한다.

이 글은 Hibernate ORM 7.4.7.Final을 기준으로 N+1의 원인과 해결책을 정리한다.

## N+1은 언제 발생하는가

예를 들어 `Team`과 `Member`가 일대다 관계라고 하자.

```java
@Entity
public class Team {

    @Id
    private Long id;

    @OneToMany(mappedBy = "team", fetch = FetchType.LAZY)
    private List<Member> members = new ArrayList<>();
}
```

팀 목록을 조회한 뒤 각 팀의 구성원에 접근하면 다음 흐름이 만들어진다.

```java
List<Team> teams = teamRepository.findAll(); // 1번

for (Team team : teams) {
    team.getMembers().size();               // 팀 수만큼 N번
}
```

```text
Team 목록 조회 1번
 ├─ team_id = 1의 Member 조회
 ├─ team_id = 2의 Member 조회
 └─ team_id = N의 Member 조회
```

지연 로딩 자체가 문제는 아니다. 필요한 시점까지 조회를 미루는 전략은 유용하다. 문제는 목록 조회 뒤 반복문이나 직렬화 과정에서 초기화되지 않은 연관 관계를 하나씩 건드리는 접근 경로다.

`EAGER`로 바꾼다고 항상 해결되지는 않는다. JPQL이 연관 관계를 함께 가져오도록 지정하지 않았다면 Hibernate는 최초 쿼리 뒤에 별도 쿼리를 실행할 수 있다. 연관 관계의 기본 로딩 전략과 실제 조회 계획은 구분해서 봐야 한다.

## 먼저 쿼리 수를 확인한다

응답 시간이 느리다는 사실만으로 N+1을 단정하지 않는다. 실행된 SQL과 쿼리 수를 먼저 확인한다.

### SQL 로그

```yaml
logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.orm.jdbc.bind: TRACE
```

개발 환경에서는 같은 형태의 SQL이 식별자만 바뀌며 반복되는지 확인한다. 운영 환경에서는 전체 바인딩 값을 남기기보다 데이터베이스 관측 도구나 요청 단위 쿼리 계측을 사용한다. 민감 값 노출과 로그 양 증가를 피하기 위해서다.

### Hibernate 통계

```yaml
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
```

Hibernate 통계는 세션과 쿼리 실행 횟수를 확인하는 데 유용하다. 상시 활성화 여부는 애플리케이션 부하와 로그 정책을 함께 보고 결정한다.

### 회귀 테스트

조회 결과만 검증하면 N+1이 다시 생겨도 테스트가 통과한다. 핵심 조회에는 쿼리 수 상한이나 예상 SQL 형태를 함께 검증한다.

```java
@Test
void 팀과_구성원을_조회할_때_쿼리_수가_늘어나지_않는다() {
    // given: 여러 Team과 Member 저장 후 영속성 컨텍스트 초기화

    List<Team> teams = teamRepository.findAllWithMembers();
    teams.forEach(team -> team.getMembers().size());

    // datasource-proxy, StatementInspector 등으로 쿼리 수 검증
}
```

정확한 허용 횟수는 조회 구현에 맞춰 정한다. 중요한 점은 데이터 건수가 늘어날 때 쿼리 수도 함께 증가하지 않는지 확인하는 것이다.

## 해결책 1: Fetch Join

연관 데이터가 해당 조회에 항상 필요하면 `JOIN FETCH`로 한 번에 가져올 수 있다.

```java
@Query("""
    select distinct t
    from Team t
    join fetch t.members
    """)
List<Team> findAllWithMembers();
```

Fetch Join은 조회 의도를 쿼리에 드러낸다. 다만 컬렉션을 조인하면 루트 엔티티 행이 자식 수만큼 늘어나므로 결과 중복과 전송량을 확인해야 한다.

### 컬렉션 Fetch Join과 페이지네이션

컬렉션을 Fetch Join한 상태에서 페이지네이션하면 데이터베이스가 아닌 메모리에서 범위를 잘라낼 수 있다. 데이터가 많으면 메모리 사용량과 응답 시간이 급격히 늘어난다.

Hibernate는 이를 실패로 바꾸는 설정을 제공한다.

```yaml
spring:
  jpa:
    properties:
      hibernate:
        query:
          fail_on_pagination_over_collection_fetch: true
```

페이지가 필요하면 보통 다음과 같이 두 단계로 나눈다.

1. 루트 엔티티 식별자를 페이지 단위로 조회한다.
2. 해당 식별자 목록으로 필요한 연관 데이터를 다시 조회한다.

### 여러 Bag 컬렉션

두 개 이상의 `List` 컬렉션을 동시에 Fetch Join하면 `MultipleBagFetchException`이 발생할 수 있다. 단순히 `List`를 `Set`으로 바꾸기 전에 중복 허용과 순서라는 도메인 의미를 확인한다. 보통 한 컬렉션만 Fetch Join하고 다른 컬렉션은 Batch Fetching이나 별도 조회로 처리한다.

## 해결책 2: EntityGraph

Spring Data JPA의 `@EntityGraph`는 Repository 메서드별로 함께 가져올 연관 관계를 선언한다.

```java
@EntityGraph(attributePaths = "members")
@Query("select t from Team t")
List<Team> findAllWithMembers();
```

조회별 Fetch Plan을 Repository 선언에 남길 수 있다는 장점이 있다. 조인이 복잡하거나 조건이 많다면 생성되는 SQL을 반드시 확인한다.

## 해결책 3: Batch Fetching

연관 데이터가 조건부로 필요하거나 컬렉션 Fetch Join을 쓰기 어려우면 Batch Fetching으로 여러 프록시를 `IN` 쿼리에 묶을 수 있다.

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 100
```

```sql
select *
from member
where team_id in (?, ?, ...);
```

배치 크기는 고정된 정답이 아니다. 데이터베이스의 `IN` 절 처리, 한 행의 크기, 네트워크 전송량과 실제 조회 분포를 측정해 정한다.

## 해결책 4: DTO Projection

화면이나 외부 API에 필요한 필드가 정해져 있다면 엔티티 그래프 전체를 로딩하지 않고 DTO로 바로 조회할 수 있다.

```java
@Query("""
    select new example.TeamSummary(t.id, t.name, count(m.id))
    from Team t
    left join t.members m
    group by t.id, t.name
    """)
List<TeamSummary> findTeamSummaries();
```

DTO Projection은 읽기 모델을 분명하게 만들고 전송량을 줄인다. 대신 영속성 컨텍스트의 변경 감지 대상이 아니며 조회 요구가 바뀔 때 DTO와 쿼리를 함께 수정해야 한다.

## 선택 기준

| 상황 | 우선 검토할 방법 | 확인할 위험 |
| --- | --- | --- |
| 연관 데이터가 항상 필요함 | Fetch Join, EntityGraph | 행 중복, 전송량 |
| 연관 데이터가 조건부로 필요함 | Batch Fetching | `IN` 절 크기, 추가 쿼리 수 |
| 컬렉션과 페이지가 함께 필요함 | 식별자 페이지 조회 후 별도 조회 | 정렬 유지, 쿼리 두 단계 |
| 반환 필드가 제한된 읽기 API | DTO Projection | 쿼리와 DTO 결합도 |
| 여러 컬렉션을 함께 조회함 | 조회 분리, 한 컬렉션 Fetch Join | 카테시안 곱, Bag 제약 |

한 가지 방법을 전역 규칙으로 정하기보다 조회 유스케이스별로 Fetch Plan을 선택한다.

## OSIV와 N+1

**OSIV**(Open Session in View)가 켜져 있으면 웹 응답을 만드는 동안에도 지연 로딩이 동작할 수 있다. 이 때문에 서비스 계층에서 보이지 않던 추가 쿼리가 직렬화 단계에서 실행되기도 한다.

OSIV를 끄면 이런 접근은 `LazyInitializationException`으로 빨리 드러난다. 그러나 OSIV 설정 자체가 N+1의 해결책은 아니다. 트랜잭션 경계, 화면 조합 방식과 조회 전용 모델을 함께 고려해 결정한다.

## 점검 순서

1. 요청 한 건에서 실행된 SQL과 쿼리 수를 확인한다.
2. 어느 연관 관계 접근이 추가 쿼리를 만드는지 찾는다.
3. 조회에 항상 필요한 데이터인지 판단한다.
4. Fetch Join, EntityGraph, Batch Fetching, DTO Projection 중 맞는 방식을 선택한다.
5. 데이터 건수를 늘려 실행 계획, 메모리와 응답 시간을 확인한다.
6. 쿼리 수가 데이터 건수에 비례해 늘지 않는 회귀 테스트를 남긴다.

## 참고 자료

- [Hibernate ORM User Guide: Fetching](https://docs.hibernate.org/orm/7.4/userguide/html_single/Hibernate_User_Guide.html#fetching)
- [Hibernate ORM User Guide: Batch Fetching](https://docs.hibernate.org/orm/7.4/userguide/html_single/Hibernate_User_Guide.html#batch-fetching)
- [Spring Data JPA: EntityGraph](https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html#jpa.entity-graph)
