# Map 구조에서 객체를 키로 사용하려면 어떻게 해야할까?

- 맵 구조에서 객체를 키로 사용하고자 하면 어떻게 해야할까?
- 아래의 샘플 코드를 보자

```
package javastudy;

import java.util.HashMap;
import java.util.Map;

public class MapUsingObjectKey {

    public static void main(String[] args) {
        Map<Foo, Integer> map = new HashMap<>();

        Foo a = new Foo("a");
        Foo b = new Foo("b");
        Foo c = new Foo("a");
        map.put(a, 1);
        map.put(b, 2);
        map.put(c, 3);

        System.out.println(map);
    }

    public static class Foo {
        String key;

        public Foo(String key) {
            this.key = key;
        }
    }
}
```

- 위의 코드에서는 Foo라는 클래스를 정의하였다
- 메인 코드에서는 Foo를 키로 사용하고, Integer를 값으로 하는 맵을 선언하고 초기화하였다
- 각각 a, b, c라는 Foo 클래스의 인스턴스를 생성하였고 맵에다가 넣었다

- 우리가 기대한 코드는 a 인스턴스와 b 인스턴스가 동등하다!
- 여기서 동일하다와 동등하다를 구별하자
- 동일하다는 것은 두 참조 변수가 완전히 같음을 의미한다(= 같은 객체)
- 동등하다는 것은 두 객체가 같은 정보를 지니고 있음을 의미한다

- 위의 코드에서는 a 인스턴스와 c 인스턴스가 동등함을 보장하지 않는다
- 따라서 해쉬맵에서 사용하는 해쉬가 결과적으로 같지 않고
- 맵의 크기는 2가 아닌 3이 될 것이다

- 그렇다면 어떻게 해야 동등한 객체에 대해서는 같은 해쉬값을 가지게 할 수 있을까?
- 일단 객체가 동등하다는 것을 판별하는 메소드를 먼저 재정의 해야한다
- 바로 Object.eqauls() 이다

```
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        Foo foo = (Foo) o;

        return Objects.equals(key, foo.key);
    }
```

- 그렇다면 equals()만 오버라이딩하면 원하는 결과를 얻을 수 있을까?
- 결과를 확인해보자

- 결과는?

```
> Task :MapUsingObjectKey.main()
{Foo{key='a'}=3, Foo{key='a'}=1, Foo{key='b'}=2}
```

- 왜 a 인스턴스와 c 인스턴스가 같음에도 불구하고 해쉬맵에는 다른 키로 들어가 있을까?
- 좀더 살펴보기 위해서 HashMap 소스로 들어가보자
- HashMap.put() 메서드는 다음과 같이 정의되어있다

```
    public V put(K key, V value) {
        return putVal(hash(key), key, value, false, true);
    }
```

- 어떤식으로 키가 같음을 확인하는지 hash 값으로 판단한다고 대강은 모두 알고 있을것이다
- 그렇다면 hash() 메서드를 확인해보면 될 것같다

```
    static final int hash(Object key) {
        int h;
        return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
    }
```

- 해쉬 메서드는 위와 같이 되어있다
- 키가 널이면 0을 반환하고
- 그렇지 않다면 해당 객체의 hashCode() 메서드를 호출하고 연산을 하게 된다

- 이에 대한 이유는 hash() 메서드의 설명을 읽어보자

  key.hashCode()를 계산하고 해시의 상위 비트를 하위 비트로 확산(XOR)합니다. 테이블은 2의 거듭제곱 마스킹을 사용하기 때문에 현재 마스크 위의 비트만 달라지는 해시 집합은 항상 충돌합니다. (알려진 예 중에는 작은 테이블에 연속적인 정수를 보유하는 Float 키 세트가 있습니다.) 따라서 상위 비트의 영향을 아래쪽으로 분산시키는 변환을 적용합니다. 비트 확산의 속도, 유틸리티 및 품질 간에는 절충점이 있습니다. 많은 공통 해시 집합이 이미 합리적으로 분포되어 있으므로(확산의 이점을 얻지 못함) 트리를 사용하여 빈에서 대규모 충돌 집합을 처리하기 때문에 시스템 손실을 줄이기 위해 가능한 가장 저렴한 방법으로 일부 이동된 비트를 XOR합니다. 뿐만 아니라 테이블 경계로 인해 인덱스 계산에 사용되지 않는 최상위 비트의 영향을 통합합니다.

- 그렇다면 현재 a 인스턴스와 c 인스턴스의 해쉬코드는 무엇일까?

```
1562557367
942731712
```

- 위와 같은 결과가 나왔다
- Object.hashCode() 메서드를 확인해보니 native 메서드였고, 메모리 상의 주소와 연관이 있는듯 하다
- 따라서 우리는 같은 객체에 대한 같은 해쉬코드 값을 가지길 원하므로
- Foo 클래스에 hashCode() 메서드를 오버라이딩 함으로써 우리가 원하는 결과를 얻을 수 있게 되었다

- 결론: 맵에서 key를 객체로 사용하려면 객체의 동등성을 보장하는 equals()를 오버라이딩 하자. 또한 동등성을 가지는 객체에 대해서 같은 해쉬 값을 가져야함으로 hashCode() 메서드를 오버라이딩 하자.

- HashMap에서 사용하는 hash메서드와, Object.hashCode()를 더 공부하면 좋겠다
