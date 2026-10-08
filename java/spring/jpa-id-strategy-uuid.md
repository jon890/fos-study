---
tags: [study, jpa, mysql, uuid]
categories: [database/mysql]
---

# JPA 식별자 전략: Long IDENTITY와 외부용 UUID v7

JPA 엔티티의 기본키를 정할 때는 INSERT 성능, 인덱스 크기와 외부 API의 식별자를 함께 봐야 한다.
이 글에서 다루는 선택은 **일반 엔티티의 기본키를 `Long IDENTITY`로 통일하고, 외부에 노출할 식별자가 필요한 엔티티에만 UUID v7 컬럼을 추가하는 방식**이다.
분석 결과를 저장하는 서비스에서 검토한 판단을 일반화했으며, 특정 업무의 구현 과정과 운영 수치는 다루지 않는다.

기술 설명은 Jakarta Persistence 3.1, Hibernate ORM 6.6, MySQL 8.4와 Java 21을 기준으로 한다.
아래 결정은 이 조건에서의 선택이며, 분산 환경에서 INSERT 전에 기본키가 필요하거나 대량 삽입이 핵심이라면 다른 전략이 더 적합할 수 있다.

## 생성 전략과 식별자가 생기는 시점

`@Id`는 엔티티 식별자를 지정하고, `@GeneratedValue`는 그 값을 생성하는 전략을 지정한다.
기본키가 있다는 사실과 자동으로 생성된다는 사실은 별개다.
애플리케이션에서 UUID를 직접 할당하거나 업무 키를 쓰면 `@GeneratedValue` 없이 `@Id`를 사용할 수 있다.

| 전략 | INSERT 전에 ID 확보 | Hibernate JDBC INSERT batch | 장점 | 비용과 이식성 |
| --- | --- | --- | --- | --- |
| `IDENTITY` | 불가. DB INSERT 후 확보 | 해당 엔티티는 비활성화 | 짧은 숫자 키, DB가 생성 책임 보유 | DB identity 지원 필요, 배치 제약 |
| `SEQUENCE` | 가능. 시퀀스에서 먼저 할당 | 가능 | ID 선할당, 할당 묶음으로 호출 감소 | DB 시퀀스 지원과 할당 크기 설정 필요 |
| `TABLE` | 가능. 생성용 테이블에서 먼저 할당 | 가능 | 시퀀스 없는 DB에서도 구현 가능 | 추가 조회·갱신과 잠금 경합 |
| 애플리케이션 UUID | 가능. 객체 생성 때 할당 가능 | 가능 | DB와 독립적으로 생성, 분산 생성에 유리 | 키 크기, 정렬 특성과 저장 형식 검토 필요 |
| 자연키·복합키 | 가능. 업무 값이 확정되어야 함 | 가능 | 업무상 유일성을 식별자에 표현 | 키 변경과 넓은 외래키, 매핑 복잡도 |

표의 ‘가능’은 생성 전략이 배치를 막지 않는다는 뜻이다.
`hibernate.jdbc.batch_size` 설정, SQL 형태와 flush 경계 등 실제 배치 조건도 맞아야 한다.
`saveAll()`을 호출한다고 곧바로 JDBC batch가 되는 것은 아니다.
IDENTITY는 Hibernate가 ID를 받기 위해 INSERT를 실행해야 하므로 해당 INSERT의 JDBC 배치를 비활성화한다.
이 제약을 DB의 다중 행 INSERT 자체가 불가능하다는 뜻으로 읽으면 안 된다.
[Hibernate JDBC batching](https://docs.hibernate.org/orm/6.6/userguide/html_single/#batch-session-batch)

‘INSERT 전’과 ‘`persist()` 호출 전’도 다르다.
SEQUENCE와 TABLE의 값은 보통 영속화 과정에서 생성기에 요청해 받는다.
애플리케이션 UUID는 영속화 요청 전에 직접 생성할 수 있다.
IDENTITY의 실제 INSERT 시점은 트랜잭션과 구현체 동작에 영향을 받으므로 모든 `save()`가 같은 시점에 SQL을 보낸다고 가정하지 않는다.

MySQL의 `AUTO_INCREMENT`는 IDENTITY에 대응한다.
MySQL 8.4에는 PostgreSQL처럼 독립적인 사용자 시퀀스 객체가 없으므로 SEQUENCE를 그대로 쓰는 선택은 맞지 않는다.
Hibernate가 시퀀스 생성기를 테이블로 대체할 수도 있지만, 실제 SQL과 잠금 비용을 확인해야 한다.
[Hibernate 시퀀스 생성기](https://docs.hibernate.org/orm/6.6/userguide/html_single/#identifiers-generators-sequence)

자연키는 코드처럼 업무 의미를 가진 값을 기본키로 사용하는 방식이다.
복합키는 여러 값을 하나의 식별자로 묶으며, `@EmbeddedId`나 `@IdClass`로 매핑한다.
일별 통계의 ‘날짜와 분류 코드’처럼 조합 자체가 행의 의미인 경우에는 자연스럽다.
반면 변경 가능한 이메일 등을 기본키로 쓰면 관련 외래키까지 변경해야 할 수 있다.
복합키 클래스에는 규격에 맞는 `equals()`와 `hashCode()` 등이 필요하다.
[Jakarta Persistence 식별자 규격](https://jakarta.ee/specifications/persistence/3.1/jakarta-persistence-spec-3.1#primary-keys-and-entity-identity)

Jakarta Persistence 3.1의 `GenerationType.UUID`도 선택지다.
다만 이 선언만으로 UUID v7 생성이 보장되지는 않는다.
버전이 계약의 일부라면 실제 생성기를 확인한다.
`AUTO` 역시 특정 DB에서 항상 IDENTITY를 선택한다는 선언이 아니다.

## InnoDB 기본키의 비용

### 클러스터드 인덱스와 삽입 위치

InnoDB는 기본키를 클러스터드 인덱스로 사용하고, 그 리프 페이지에 행 데이터를 저장한다.
행은 B-tree 안에서 기본키 순서로 조직된다.
이것은 디스크 파일 전체가 기본키 순서대로 연속 배치된다는 뜻도, `ORDER BY` 없는 조회 결과가 정렬된다는 뜻도 아니다.
[MySQL 클러스터드 인덱스](https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html)

증가하는 숫자 키는 대체로 인덱스의 끝부분에 삽입된다.
랜덤 UUID v4는 여러 기존 페이지에 삽입을 분산시킨다.
페이지에 여유가 없으면 분할이 필요하고, 여러 페이지를 읽고 변경하면서 버퍼 풀의 지역성이 떨어질 수 있다.
순차 키도 페이지 분할을 없애지는 않으며, 높은 동시성에서는 끝부분의 경합이 생길 수 있다.
따라서 UUID v7을 쓰면 모든 삽입이 빨라진다고 단정하지 않고, 실제 인덱스 구성과 부하로 비교한다.
[MySQL InnoDB 인덱스의 물리 구조](https://dev.mysql.com/doc/refman/8.4/en/innodb-physical-structure.html)

### 보조 인덱스에도 붙는 기본키

InnoDB의 보조 인덱스 레코드에는 기본키가 포함된다.
보조 인덱스에서 찾은 기본키로 클러스터드 인덱스의 행을 조회하기 때문이다.
기본키가 커지면 기본키 인덱스뿐 아니라 여러 보조 인덱스의 공간과 캐시 사용량에도 영향을 준다.
[MySQL 보조 인덱스](https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html)

| 저장 형식 | 값의 크기 기준 | 주의점 |
| --- | --- | --- |
| `BIGINT` | 8바이트 | Java `Long`과 대응하는 숫자 키 |
| `CHAR(36)` | utf8mb4 선언상 최대 144바이트 | 36문자와 문자당 최대 4바이트의 곱 |
| `BINARY(16)` | 16바이트 | UUID 128비트를 문자열 없이 저장 |

144바이트는 문자 집합에 따른 최대 길이 계산이다.
일반 UUID 문자열의 영문 숫자와 하이픈은 ASCII 문자이므로, utf8mb4라는 이유만으로 모든 값이 실제로 144바이트를 차지한다고 계산하면 틀린다.
실제 레코드 크기에는 행 형식과 인덱스 메타데이터도 관여한다.
이 표는 인덱스 전체 크기나 성능 배수를 제시하는 표가 아니다.
[MySQL 자료형 저장 공간](https://dev.mysql.com/doc/refman/8.4/en/storage-requirements.html)

UUID를 저장할 때는 `BINARY(16)`을 우선 검토한다.
문자열의 편의가 필요하면 ASCII 문자 집합과 비교 규칙도 검토할 수 있다.
Java 필드가 `UUID`라는 것만으로 모든 DB에서 같은 SQL 타입이 선택되지는 않으므로 ORM 매핑과 DDL을 함께 확인한다.

## UUID v4와 v7의 차이

두 버전 모두 128비트다.
v4는 버전·variant 비트를 제외한 122비트를 랜덤 값으로 사용한다.
v7은 앞부분에 시간을 넣고, 나머지 부분에 랜덤 값 등을 넣는다.
[RFC 9562 UUID v4](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.4)

| UUID v7 필드 | 비트 수 | 내용 |
| --- | --- | --- |
| `unix_ts_ms` | 48 | Unix epoch 기준 밀리초 |
| `ver` | 4 | 버전 7 |
| `rand_a` | 12 | 랜덤 값 또는 규격이 허용하는 순서 보강 값 |
| `var` | 2 | UUID variant |
| `rand_b` | 62 | 랜덤 값 또는 규격이 허용하는 순서 보강 값 |

일반적인 v7 구현은 시간 외 74비트를 랜덤 값으로 채운다.
규격은 같은 밀리초 내 순서를 보강하기 위한 카운터와 더 세밀한 시간의 사용도 허용한다.
따라서 **v7이라는 사실만으로 같은 밀리초 안에서 생성 순서가 보장되지는 않는다**.
순수 랜덤 구현에서는 그 구간의 순서가 랜덤이다.
시계가 뒤로 이동하거나 여러 노드의 시간이 어긋나면 전체 생성 순서도 보장되지 않는다.
[RFC 9562 UUID v7](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.7)

v7의 정렬성은 표준 바이트 순서에서 시간 필드가 앞에 있다는 특성이다.
DB에 바이트 순서를 바꿔 저장하면 이 이점을 잃을 수 있다.
MySQL의 `UUID_TO_BIN(uuid, 1)`은 v1의 시간 부분 재배열을 위한 옵션이므로 v7에 그대로 적용하지 않는다.
v7은 기본 바이트 순서를 유지하고 읽기와 쓰기에 같은 변환을 사용한다.
[MySQL UUID_TO_BIN](https://dev.mysql.com/doc/refman/8.4/en/miscellaneous-functions.html#function_uuid-to-bin)

외부에 v7을 노출하면 앞의 48비트에서 생성 시각을 읽을 수 있다.
랜덤 부분 때문에 다음 식별자를 순차적으로 알아내기는 어렵지만, 시각을 숨기는 식별자는 아니다.
또한 UUID의 유일성은 확률과 생성기 품질에 의존하므로 DB의 UNIQUE 제약도 유지한다.
[RFC 9562 보안 고려사항](https://www.rfc-editor.org/rfc/rfc9562.html#section-6.12)

### Java에서 생성하는 방법

Java 21의 `UUID.randomUUID()`는 v4를 만든다.
`UUID` 생성자로 v7 비트를 담을 수는 있지만, `randomUUID()`를 v7 생성기로 사용할 수는 없다.
[Java 21 UUID API](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/UUID.html#randomUUID())

직접 구현할 때 필요한 비트 배치는 다음과 같다.
아래 코드는 RFC 구조를 설명하기 위한 일반화한 예제이며, 같은 밀리초 내 단조 증가와 시계 역행 처리는 제공하지 않는다.

```java
import java.security.SecureRandom;
import java.util.UUID;

public final class UuidV7Example {
    private static final SecureRandom RANDOM = new SecureRandom();

    public static UUID create() {
        long timestamp = System.currentTimeMillis();
        long most = ((timestamp & 0xFFFFFFFFFFFFL) << 16)
                | 0x7000L
                | (RANDOM.nextLong() & 0x0FFFL);
        long least = (RANDOM.nextLong() & 0x3FFFFFFFFFFFFFFFL)
                | 0x8000000000000000L;
        return new UUID(most, least);
    }
}
```

직접 만든 생성기에는 버전 7, variant 2, 시간 필드 복원과 바이트 변환 왕복 검사가 필요하다.
정렬 순서가 계약이라면 동일 시각, 시계 역행과 동시 호출 테스트를 별도로 추가해야 한다.
충돌을 못 봤다는 테스트만으로 유일성을 증명할 수는 없다.

운영에서는 검증된 라이브러리를 먼저 검토할 수 있다.
`uuid-creator`는 `UuidCreator.getTimeOrderedEpoch()`로 v7을 생성한다.
[uuid-creator 공식 예제](https://github.com/f4b6a3/uuid-creator)
다른 선택지인 Java UUID Generator도 v7을 제공한다.
생성기의 단조 증가 범위, 시계 역행 정책, 스레드 안전성, 라이선스와 지원 Java 버전을 채택 버전에서 확인한다.
[Java UUID Generator](https://github.com/cowtowncoder/java-uuid-generator)

## 내부 숫자 키와 외부 UUID의 분리

내부 `id`는 조인과 외래키에 사용하고, 외부 `uuid`는 API 경로와 응답에서 사용한다.
예를 들어 `GET /reports/{uuid}` 요청은 UUID로 행을 찾지만, 다른 테이블은 그 행의 숫자 ID를 참조한다.
아래 DDL은 관계를 설명하는 예제다.

```sql
CREATE TABLE report (
    id BIGINT NOT NULL AUTO_INCREMENT,
    uuid BINARY(16) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_report_uuid (uuid)
);
```

숫자 ID를 외부에 그대로 내보내면 값을 하나씩 바꾸는 열거가 쉬워지고, 데이터 규모나 생성 순서를 추정하는 단서도 생긴다.
UUID를 외부 식별자로 고정하면 DB 이관이나 데이터 통합 때 내부 숫자 키를 다시 배정할 여지도 생긴다.
이때 기존 UUID와 새 내부 ID의 대응은 보존해야 한다.

UUID는 접근 권한을 대신하지 않는다.
사용자는 UUID를 알더라도 해당 행을 조회할 권한이 있어야 하며, 서버는 소유자나 권한 범위를 함께 검사해야 한다.
v7의 생성 시각 노출을 허용할 수 없는 데이터라면 외부 식별자에 v4 등 다른 방식을 검토한다.

비용도 있다.
UUID 컬럼과 UNIQUE 인덱스가 추가되고, 애플리케이션에는 두 식별자가 공존한다.
UUID 보조 인덱스에는 숫자 기본키도 포함되며, UUID로 조회한 뒤 행을 읽는 경로도 고려해야 한다.
API DTO, 로그와 서비스 메서드가 어느 식별자를 받는지 명확히 정해야 한다.

## 선택한 규칙과 예외

우리의 선택은 일반 엔티티 기본키를 `Long`과 `GenerationType.IDENTITY`로 통일하는 것이었다.
외부 식별자가 필요한 엔티티에만 UUID v7을 추가하고, 내부 외래키는 숫자로 유지한다.
이는 특정 테이블만 UUID 기본키로 바꾸는 것보다 서비스 전체의 관계 매핑과 식별자 취급을 일관되게 유지하려는 판단이다.

대안 B는 외부 식별자가 필요한 엔티티의 기본키 자체를 v7으로 바꾸는 방식이었다.
UUID 컬럼을 중복으로 두지 않고 INSERT 전에 기본키를 확보할 수 있다.
반면 UUID가 기본키인 엔티티와 숫자가 기본키인 엔티티가 섞이고, 외래키 타입과 공통 코드의 전제가 달라진다.
v7이어도 기본키는 16바이트이므로 숫자 키와 같은 인덱스 비용은 아니다.
이 조건에서는 서비스 전체의 일관성을 우선해 대안 B를 선택하지 않았다.

IDENTITY의 JDBC batch 제약은 남는다.
대량 저장이 핵심인 경로라면 별도 JDBC 삽입, 다른 저장 모델이나 생성 전략을 검토하고 실제 부하로 판단해야 한다.
UUID 컬럼을 추가한다고 IDENTITY의 배치 제약이 해결되지는 않는다.

예외는 값 자체가 업무 키인 사전·통계 테이블과 고정된 한 행을 표현하는 테이블로 한정한다.
사전은 불변 코드, 통계는 날짜와 분류의 조합처럼 의미가 분명한 키를 사용할 수 있다.
고정 한 행 테이블은 정해진 ID를 직접 할당할 수 있지만, 그것만으로 두 번째 행의 생성을 막지는 못한다.
필요하면 DB 제약도 함께 둔다.
각 예외에는 키 형태, 자동 생성하지 않는 이유와 변경 조건을 기록한다.

## ArchUnit으로 기본 규칙 검사

문서만으로는 새 엔티티의 다른 타입이나 기본 전략 `AUTO`를 발견하기 어렵다.
ArchUnit으로 `@Entity`를 수집하고 사용자 정의 `ArchCondition`으로 식별자 규칙을 검사하면 CI에서 위반을 찾을 수 있다.
[ArchUnit 사용자 정의 조건](https://www.archunit.org/userguide/html/000_Index.html#_the_lang_api)

다음 코드는 **필드 접근을 쓰는 프로젝트**를 위한 일반화한 JUnit 5 예제다.
예제 검증 환경은 Java 21, ArchUnit 1.4.1, Jakarta Persistence API 3.1.0과 JUnit 5.11.4다.
상속한 ID 필드도 확인하고, 예외가 아닌 엔티티의 프로퍼티 ID와 `@EmbeddedId`는 실패시킨다.
프로퍼티 접근을 허용하는 프로젝트라면 getter의 반환 타입과 애너테이션을 검사하는 조건을 별도로 작성한다.
XML 매핑을 사용하는 프로젝트에는 그 매핑까지 검사하는 추가 검증이 필요하다.

```java
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Map;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;

class EntityIdRuleTest {
    // 일반화한 예외 이름이다. 실제 코드에서는 완전한 클래스명으로 관리한다.
    private static final Map<String, String> EXCEPTIONS = Map.of(
            "example.domain.DictionaryEntry", "불변 업무 코드",
            "example.domain.DailyStatistic", "날짜와 분류의 복합키",
            "example.domain.GlobalSettings", "고정 한 행의 명시적 ID"
    );

    @Test
    void entitiesUseLongIdentity() {
        var imported = new ClassFileImporter().importPackages("example.domain");
        classes().that().areAnnotatedWith(Entity.class)
                .should(new ArchCondition<JavaClass>("use one Long IDENTITY field") {
                    @Override
                    public void check(JavaClass entity, ConditionEvents events) {
                        if (EXCEPTIONS.containsKey(entity.getName())) {
                            return;
                        }
                        var ids = new ArrayList<Field>();
                        boolean unsupported = false;
                        for (Class<?> type = entity.reflect();
                             type != null && type != Object.class;
                             type = type.getSuperclass()) {
                            for (Field field : type.getDeclaredFields()) {
                                if (field.isAnnotationPresent(Id.class)) {
                                    ids.add(field);
                                }
                                unsupported |= field.isAnnotationPresent(EmbeddedId.class);
                            }
                            unsupported |= Arrays.stream(type.getDeclaredMethods())
                                    .anyMatch(method -> method.isAnnotationPresent(Id.class)
                                            || method.isAnnotationPresent(EmbeddedId.class));
                        }
                        boolean valid = !unsupported && ids.size() == 1;
                        if (valid) {
                            Field id = ids.get(0);
                            GeneratedValue generated = id.getAnnotation(GeneratedValue.class);
                            valid = id.getType() == Long.class && generated != null
                                    && generated.strategy() == GenerationType.IDENTITY;
                        }
                        events.add(new SimpleConditionEvent(entity, valid,
                                entity.getName() + " must declare one Long IDENTITY field"));
                    }
                }).check(imported);
    }
}
```

ArchUnit의 `reflect()`를 사용하므로 테스트 실행 시 엔티티와 관련 타입이 클래스패스에 있어야 한다.
패키지 범위도 실제 모든 엔티티를 포함하도록 지정한다.
빈 범위가 검사 성공으로 처리되지 않도록 기본 빈 규칙 실패 동작을 유지한다.

예외 목록은 전체 검사의 무조건 면제 목록으로 끝내지 않는다.
각 예외가 여전히 존재하는지 확인하고, 자연키·복합키·고정 ID의 기대 형태를 별도 테스트로 검사한다.
사용하지 않는 예외는 삭제하며, 새 예외를 추가할 때 이유도 함께 리뷰한다.

기본 규칙의 검증에는 정상 `Long IDENTITY`, 잘못된 UUID·primitive `long`, 빠진 `@GeneratedValue`, `AUTO`, 상속 ID, 복합키와 프로퍼티 ID를 각각 넣는다.
외부 UUID의 v7 생성과 UNIQUE 제약, 실제 DB의 `BINARY(16)` 매핑은 이 구조 검사만으로 증명되지 않으므로 생성기 테스트와 DB 통합 테스트에서 확인한다.

## 관련 문서

- [JPA 벌크 변경과 트랜잭션 정합성](./jpa-bulk-update-isolation-and-consistency.md)
- [Spring Data JPA 트랜잭션 흔한 실수들](./jpa-transaction.md)
- [MySQL / InnoDB 인덱스 허브](../../database/mysql/b-tree-index.md)
