# Flex Box

- 브라우저의 호환성을 위해서 Position, Float, Table을 이용해서 레이아웃을 하곤 했다
- 하지만 박스 아이템을 수직으로 정렬하는 것은 까다로웠다.
- 또한 아이템의 사이즈에 상관없이 동일한 간격으로, 박스안에 배치하는 것은 까다로웠다.
- 이제는 Flex Box로 손쉽게 구현이 가능하다

- Float의 원래 목적은
- 이미지와 텍스트들을 어떻게 배치할지에 대한 속성이었다.
- 이미지를 왼쪽, 중간, 오른쪽에 배치할 수 있다.
- 이 기능을 이용해서 박스를 왼쪽, 오른쪽에 배치하는 Hack을 많이 사용하였다.

## Flexbox의 2가지 중요 컨셉

1. container and item (컨테이너와 아이템)
2. main axis and cross axis (중심축과 반대축)

## 본격적인 공부

- 쉽게 div 만드는 법 : div.container>div.item.item${$}\*10 => emmet
- 100% vs 100vh => % 부모의 높이의 비율, vh: 보이는 viewport의 height
- Meterial Design의 Color Tool을 사용해서 예쁜 색상 팔레트를 사용해보자
- 새로운 속성들을 많이 공부하되 Can I Use 등에서 브라우저에서 사용 가능 한지 확인 해보기
- 현업에서도 계속 찾아보게될 것, 큰 그림을 이해하고, 자세한 내용은 꾸준히 공부하기

  ### Container의 속성값

  - 일반 속성
  - display : flex (flexbox로 보여주겠다)
  - flex-direction : row, row-reverse, column, column-reverse (중심축을 변경)
  - flex-wrap : nowrap, wrap, wrap-reverse (아이템들이 한줄에 꽉차게 되면 다음줄으로 변경할 것인가)
  - flex-flow : column nowrap (direction, wrap을 한 줄에 작성)

  - 아이템들을 배치
  - justify-content: flex-start (왼쪽에서 오른쪽, 위에서 아래), flex-end, center, space-around (박스를 둘러싸게 spacing을 넣어줌), space-evenly, space-between [중심축에서 아이템을 배치]
  - align-items: center, baseline (텍스트의 기준에 맞춰서 보여줌 => 아이템의 크기가 다를 때) [반대축에서 아이템을 배치]
  - align-content: center, space-between

  ### Item의 속성값

  - order : 0, 1, 2 ... (html에 관계없이, 잘 쓰여지지는 않는것 같다)
  - flex-grow : 0 (default), constraint and linear layout weight와 비슷 (남은 영역을 차지하거나 다른 아이템과 비교해서 크기를 결정)
  - flex-shrink: 0 (default) 1, 2, 3, ... (컨테이너가 작아졌을 때 행동을 결정)
  - flex-basis : auto (default), n% (아이템이 얼마나 공간을 차지하는지 세부적으로 결정)
  - align-self: center (특정 아이템을 정렬)
