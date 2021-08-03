# 자바스크립트 프로처럼 쓰는 팁 (드림코딩 by 엘리)님의 유튜브를 보고

- https://www.youtube.com/watch?v=BUAhpB3FmS4

## 팁1. Tenary Operator (삼항 연산자)

- 우선 안좋은 코드를 살펴보자

```
// Bad Code ㅠㅠ
function getResult(score) {
    let result;
    if (score > 5) {
        result = 'Good';
    } else if (score <= 5) {
        result = 'Study Hard!';
    }
    return result;
}
```

- 삼항 연산자를 활용한 개선 코드

```
function getResult(score) {
    return score > 5 ? 'Good' : 'Study Hard!';
}
```

## 팁2. Nullish Coalescing Operator (Null을 Pro처럼 다루기)

- 안좋은 코드

```
function printMessage(text) {
    let message = text;
    if (text == null || text == undefined) {
        message = 'Nothing to display';
    }
    console.log(message);
}
```

- 개선 코드

```
function printMessage(text) {
    const message = text ?? 'Nothing to display';
    console.log(message);
}
```

### Default Parameter와 비교

```
function printMessage(text = 'Nothing to display') {
    console.log(text);
}

printMessage(undefined);
nullish coalescing vs default parameter => o.k.

printMessage(null);
nullish coalescing vs default parameter => Default Parameter를 사용하면 null이 출력됨
```

- Default Parameter는 undefined에서만 적용된다!

### Logical Operator과 비교

- Nullish Coalescing Operator ??
- leftExpr ?? rightExpr
- 왼쪽 표현식이 null, undefined일 때만 오른쪽 표현식이 실행된다

- Logical OR operator ||
- leftExpr || rightExpr
- 왼쪽 표현식이 falsy한 경우에 오른쪽 표현식이 실행된다

- 비슷하지만 nullish coalescing은 null, undefined에만 적용된다!

- 참고 falsy: 0, -0, Nan, "", '' 등
- 차이점을 명확히 이해하고 사용하자

## 팁3. Object Destructuring (객체 구조분해)

- 안좋은 코드

```
const person = {
    name: 'Julia',
    age: 20,
    phone: '01077777777',
};

function displayPerson(person) {
    displayAvatar(person.name);
    displayName(person.name);
    displayProfile(person.name, person.age);
}

// 반복되는 코드를 줄이기 => 코드의 양이 많아짐
function displayPerson(person) {
    const name = person.name;
    const age = person.age;
    displayAvatar(name);
    displayName(name);
    displayProfile(name, age);
}
```

- 개선 코드

```
function displayPerson(person) {
    const { name, age } = person;
    displayAvatar(name);
    displayName(name);
    displayProfile(name, age);
}
```

## 팁4. Spread Syntax (전개 연산자)

- 두 개의 객체를 합치는 경우를 생각해보자

- 안좋은 코드

```
const item = { type: 'tie', size: 'M' };
const detail = { price: 20, made: 'Korea', gender: 'M' };

// 하나의 객체에 다른 속성을 할당 => ..
item['price'] = detail.price

// 새로운 객체를 할당하여 속성들을 모두 복사
const newObject = {};
newObject['type'] = item.type;
...
```

- 개선 코드

```
// ES6
const shirt0 = Object.assign(item, detail);

// Spread Syntax
// 원하는 속성을 업데이트도 가능!
const shirt = { ...item, ...detail, price: 40};
```

- Spread Syntax는 배열에도 사용 가능 하다

## 팁5. Optional Chaining (옵셔널 체이닝)

- 직업을 구하고 있는 Bob과
- 직업을 구한 Anna가 있다고 해보자

```
const bob = {
    name: 'bob'
    age: 20,
}

const anna = {
    name: 'anna'
    age: 21,
    job: {
        title: 'Software Engineer',
    },
};
```

- 이때 직책을 표현하는 함수가 있다고 한다
- 안좋은 코드를 살펴보자

```
function displayJobTitle(person) {
    if (person.job && person.job.title) {
        console.log(person.job.title);
    }
}
```

- 개선 코드

```
function displayJobTitle(person) {
    if (person.job?.title) {
        console.log(person.job.title);
    }
}

// Nullish Coalescing도 활용해보기
function displayJob(person) {
    const title = person.job?.title ?? 'No Job Yet';
    console.log(title);
}
```

## 팁6. Template Literals

```
const person = {
    name: 'Julia',
    score: 4,
}

// 안좋은 코드
console.log(
    'Hello ' + person.name + ', Your current score is: ' + person.score
);

// 개선 코드
console.log(`Hello ${person.name}, Your current score is: ${person.score}`);
```

## 팁7. Loop

- 아래의 배열에서 짝수만 4를 곱한다음 합을 계산해보자
- 함수를 분리하지 말고, 배열의 API을 사용해보고, 더 나아가 체이닝 할 수 있다

```
const numbers = [1, 2, 3, 4, 5, 6];

const result = numbers.filter(n => n % 2 === 0)
    .map(n => n * 4)
    .reduce((acc, cur) => acc + cur, 0);
```

## 팁8 Promise -> Async/Await

- Promise 사용시 then 지옥에 빠지는 것을 개선하는 법을 알아보자

```
function displayUser() {
    fetchUser()
        .then((user) => {
            fetchProfile(user)
                .then((profile) => {
                    updateUI(user, profile);
                })
        })
}
```

- Async/Await을 통해서 개선
- 순차적으로 읽어낼 수 있으므로 가독성이 좋아진다
- 근본적인 개념은 Promise이므로 Prosmie에 대해서도 반드시 알아야함

```
async function displayUser() {
    const user = await fetchUser();
    const profile = await fetchProfile(user);
    updateUI(user, profile);
}
```

## 퀴즈 -> 배열 아이템의 중복 제거

```
const array = [1, 2, 3, 4, 1, 1];
console.log([...new Set(array)]);
```
