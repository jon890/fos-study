# 저장소 구조와 문서 배치

새 문서를 만들거나 위치, 카테고리, Frontmatter와 역할 태그를 바꿀 때 읽는다.

## 배치 기준

폴더 목록은 저장소 루트와 각 폴더의 `README.md`에서 확인한다.
아래는 폴더 이름만으로 위치를 정하기 어려운 경우의 기준이다.

- `database/`에는 데이터를 저장하고 검색하는 스토어를 둔다. MySQL, OpenSearch와 Redis가 해당한다.
- Kafka는 메시지 브로커이므로 `database/`가 아닌 최상위 `kafka/`에 둔다.
- `task/`에는 개념 설명이 아니라 실제 업무의 배경, 구현 과정과 회고를 둔다.
- `architecture/patterns/`에는 객체 협력 방식과 애플리케이션 경계를 둔다.
- `architecture/distributed-systems/`에는 통신, 정합성, 메시징과 회복성을 둔다.
- `architecture/evolution/`에는 API 호환성과 시스템 전환을 둔다.
- `architecture/domain/`에는 DDD와 비즈니스 도메인 모델링을 둔다.
- `observability/`에는 지표, 로그, 추적과 장애 탐지의 개념을 둔다. 실제 적용 경험은 `task/`에 둔다.
- 실제 업무 사례를 기술 폴더에 복제하지 않고 개념 문서와 상대 링크로 연결한다.

## 카테고리와 Frontmatter

글의 기본 카테고리는 최상위 폴더로 정해진다.
예를 들어 `AI/RAG/intro.md`의 기본 카테고리는 `AI`다.

다른 카테고리에도 노출할 때만 문서 최상단의 YAML Frontmatter에 `categories`를 추가한다.

```yaml
---
categories: [devops, database]
---
```

최종 카테고리는 폴더 카테고리와 `categories`의 합집합이며 중복은 제거된다.
값은 실제 폴더의 상대 경로와 대소문자를 그대로 사용하고,
하위 폴더는 `AI/RAG`처럼 전체 경로를 사용한다.

새 최상위 폴더에 글을 추가하면 블로그 카테고리로 자동 등록된다.
정적 메타데이터가 없으면 폴더명, 기본 아이콘과 이름 기반 색상을 사용한다.

## 썸네일

대표 썸네일의 위치, 구도와 검증은 [썸네일 생성](../skills/blog-post-writer/references/thumbnail-generation.md)이 정한다.
이미지는 문서와 함께 커밋한다.

## 역할 태그

기존 난이도와 도메인 태그는 유지하고 문서 역할 태그를 함께 붙인다.

| 태그 | 의미 |
| --- | --- |
| `tasks` | 실제 작업 결과와 업무 수행 과정 |
| `insights` | 실제 경험에서 얻은 재사용 가능한 판단과 회고 |
| `study` | 학습과 참조를 위한 기술 개념 |

- `task/` 업무 기록에는 기본적으로 `tasks`를 붙인다.
- 기술 카테고리 문서에는 기본적으로 `study`를 붙인다.
- `insights`는 본문에 실제 경험에서 얻은 판단이나 회고가 분명할 때만 붙인다.
- `resume/` 문서는 역할 태그 일괄 적용 대상에서 제외한다.
