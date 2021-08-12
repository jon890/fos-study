function Heap() {
  this.items = [];
  return this;
}

// 프로토타입 객체에 메소드 정의
// 모든 객체는 프로토타입이라는 다른 객체를 가리키는 내부 링크를 가지고 있다
// 즉, 프로토타입을 통해 직접 객체를 연결할 수 있다 => 이를 프로토타입 체인이라고 한다

// 프로토타입을 이용하여 생성자 함수 내부의 메소드를 생성자 함수의 prototype 프로퍼티가
// 가리키는 프로토타입 객체로 이동시키면
// 생성자 함수에 의해 생성된 모든 인스턴스는 프로토타입 체인을 통해 프로토타입 객체의 메소드를 참조할 수 있다

Heap.prototype.swap = function (i1, i2) {
  let temp = this.items[i1];
  this.items[i1] = this.items[i2];
  this.items[i2] = temp;
};

Heap.prototype.getParentIndex = function getParentIndex(index) {
  return Math.floor((index - 1) / 2);
};

Heap.prototype.getParent = function getParent(index) {
  return this.items[this.getParentIndex(index)];
};

Heap.prototype.getLeftChildIndex = function getLeftChildIndex(index) {
  return index * 2 + 1;
};

Heap.prototype.getLeftChild = function getLeftChild(index) {
  return this.items[this.getLeftChildIndex(index)];
};

Heap.prototype.getRightChildIndex = function getRightChildIndex(index) {
  return index * 2 + 2;
};

Heap.prototype.getRightChild = function getRightChild(index) {
  return this.items[this.getRightChildIndex(index)];
};

Heap.prototype.peek = function peek() {
  const firstItem = this.item[0];
  if (!firstItem) {
    throw new Error('Heap is Empty!');
    return;
  }

  return firstItem;
};

Heap.prototype.size = function size() {
  return this.item.length;
};

export default Heap;
