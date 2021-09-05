# 2부. 바이트코드 조작

## 6. javaagent 실습

```
public class Masulsa {

    public static void main(String[] args) {
        try {
             new ByteBuddy.redefine(Moja.class)
                .method(named("pullOut)).intercept(FixedValue.value("Rabiit!))
                .make().saveIn(new File("/Users/gimbyoungtae/workspace/thejava/target/classes/));
        } catch (IOExpcetion e) {
            e.printStackTrace();
        }

        System.out.prinlnt(new Moja().pullOut());
    }
}
```

- 위와같이 작성하지 않고
- 마술사는 모자에서 꺼내기만해도 토끼가 나오게 해보자

- 위와 같은 코드가 우리의 예상대로 동작하지 않는이유는
- 이미 클래스 로더가 Moja.class를 읽어버렸기 때문이다

```
public class Masulsa {

    public static void main(String[] args) {
        ClassLoader classLoader = Masulsa.class.getClassLoader();
        TYpePoll typePool = TypePool.Default.of(classLoader);

        try {
             new ByteBuddy.redefine(

                 typePool.describe("com.bifos.Moja").resolve(),
                 ClassFileLocator.ForClassLoader.of(classLoader))
                .method(named("pullOut)).intercept(FixedValue.value("Rabiit!))
                .make()
                .saveIn(new File("/Users/gimbyoungtae/workspace/thejava/target/classes/));
        } catch (IOExpcetion e) {
            e.printStackTrace();
        }

        System.out.prinlnt(new Moja().pullOut());
    }
}
```

- 위와 같이 변형해보자
- 모자라는 클래스를 읽지않고
- 바이트코드를 조작한뒤
- 모자 클래스를 만들어 클래스를 로딩한다

### 이제 바이트 코드를 조작하는 Agent를 만들어보자

```
public class MasulasaAgent {

    public static void premain(String agentArgs, Instrumentation inst) {
        new AgentBuilder.Default()
            .type(ElementMacters.any())
            .transform((builder, typeDescription, classLoader, javaModule) ->
                builder.method(named("pullOut"))
                    .intercept(FixedValue.value("Rabiit!)))
                    .installOn(inst);
    };
}
```

- 위 패키지를 jar로 만들어보자
- maven jar plugin

- 위 패키지를 VM Option에 추가하면
- Rabbit이 나온다!

- 파일시스템에 있는 파일을 변경하는 것이 아니라
- 지금 이 방식은 Javaagent가 클래스를 로딩할 때 변경된 바이트코드를 읽어온다
- Transparent(비침투적인)한 코드
