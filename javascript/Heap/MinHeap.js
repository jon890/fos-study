function Heap() {
  this.items = [];
  return this;
}

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
  if (!firstItem) throw new Error('Heap is Empty!');
  return firstItem;
};

Heap.prototype.size = function size() {
  return this.item.length;
};

class MinHeap extends Heap {
  bubbleUp() {
    // 힙의 맨 마지막 아이템을 가져온다
    let index = this.items.length - 1;

    // 부모노드와 비교해서 더 작다면 값을 위로 올린다
    // 부모노드가 크거나 루트노드에 도달할 때 까지 반복한다
    while (true) {
      const parentValue = this.getParent(index);
      const parentIndex = this.getParentIndex(index);
      const currentValue = this.items[index];

      if (!parentValue) break;
      if (currentValue > parentValue) break;

      this.swap(index, parentIndex);
      index = parentIndex;
    }
  }

  bubbleDown() {
    // 힙의 첫 번째 아이템을 가져온다
    let index = 0;

    // 아래 자식들과 비교해서 값이 크면
    // 자식노드의 제일 작은값과 교환한다
    while (true) {
      const currentValue = this.items[index];
      const leftChildValue = this.getLeftChild(index);
      const leftChildIndex = this.getLeftChildIndex(index);
      const rightChildValue = this.getRightChild(index);
      const rightChildIndex = this.getRightChildIndex(index);

      // 왼쪽 자식이 존재하지 않으면 종료
      if (!leftChildValue) break;
      // 이미 내가 자식 노드보다 작으면 종료
      if (
        currentValue < leftChildValue ||
        (rightChildValue && currentValue < rightChildValue)
      )
        break;

      // 더 값이 작은 노드와 교체한다
      let smallerIndex =
        rightChildValue && rightChildValue < leftChildValue
          ? rightChildIndex
          : leftChildIndex;

      this.swap(index, smallerIndex);
      index = smallerIndex;
    }
  }

  add(item) {
    this.items[this.items.length] = item;
    this.bubbleUp();
  }

  poll() {
    const item = this.items[0]; // 첫 번째 원소 임시로 저장
    this.items[0] = this.items[this.items.length - 1]; // 맨 마지막 원소를 첫 번째 원소로 복사
    this.items.pop(); // 맨 마지막 원소 삭제
    this.bubbleDown();
    return item;
  }
}

const myHeap = new MinHeap();
myHeap.add(1);
myHeap.add(10);
myHeap.add(5);
myHeap.add(100);
myHeap.add(8);

let result;
result = myHeap.poll();
result = myHeap.poll();
result = myHeap.poll();
result = myHeap.poll();
result = myHeap.poll();
