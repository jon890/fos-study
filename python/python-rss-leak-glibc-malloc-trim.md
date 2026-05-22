# Python 서버의 RSS 가 안 줄어드는 이유 — gc.collect 의 한계와 malloc_trim

Python 으로 long-running 서버 (FastAPI / Flask / Celery / uWSGI 등) 를 운영하다 보면 한 번쯤 마주치는 증상이 있다.

- 워커 프로세스의 RSS 가 시간이 지날수록 단조 증가한다
- 큰 객체를 `del` 하고 `gc.collect()` 를 불러도 RSS 가 줄지 않는다
- 결국 `max-requests` / `worker_max_tasks_per_child` / 주기적 재시작으로 우회한다

이 글은 그 안에서 무슨 일이 일어나는지 — 한국 개발자가 가끔 헷갈리는 **CPython 의 메모리 관리 계층** 과 **glibc malloc 의 동작** 을 한 번에 정리한 문서다. 깊은 디버깅보다는 "구조를 이해하고 진단 출발선을 갖추는" 게 목적이다.

## 메모리 관리의 4 단계 계층

CPython 의 메모리 흐름은 네 단계를 지난다.

```
Python 객체  →  pymalloc (arena/pool)  →  glibc malloc (bin/heap)  →  OS (RSS)
```

각 단계는 자신만의 캐시 정책이 있다. 어느 한 단계가 free 했다고 곧바로 위 단계로 메모리가 올라가지 않는다.

| 단계 | 역할 | 캐시 정책 |
|---|---|---|
| Python 객체 | `obj = SomeClass()` 같은 user-space 객체 | 참조 카운트가 0 이 되면 `__del__` + 메모리 반환 |
| pymalloc | 512 바이트 이하 객체용 전용 allocator | arena (256 KiB) 단위로 OS 와 거래, 그 안의 pool 은 회수 안 함 |
| glibc malloc | 그 이상의 `malloc()` 호출 | bin 자료구조에 보관, 자동 트림 임계값 도달 시에만 OS 반환 |
| OS | 실제 RAM | RSS 카운터 — 우리가 `ps`, `top`, `/proc/pid/status` 로 보는 값 |

RSS 가 안 줄어드는 건 보통 (b) 와 (c) 단계의 캐시 때문이다. (b) pymalloc 도 영향이 있지만 더 큰 그림은 (c) glibc malloc 의 단편화다.

## glibc malloc 의 메모리 할당 전략

glibc 의 ptmalloc2 는 요청 크기에 따라 두 경로로 갈린다.

### brk 와 mmap 분기

```
malloc(size) 호출
   │
   ├── size < M_MMAP_THRESHOLD (기본 128 KiB)
   │   └── brk(2) / sbrk(2) 로 확장된 heap 영역에 배치
   │       — 우리가 흔히 "프로세스의 heap" 이라고 부르는 그 영역
   │
   └── size ≥ M_MMAP_THRESHOLD
       └── mmap(2) 으로 별도 영역을 잡아 단독 chunk
           — free 시 munmap(2) 으로 OS 에 즉시 반환
```

여기서 첫 번째 직관이 깨진다. **큰 객체는 free 하면 OS 로 잘 돌아가지만, 작은 객체는 안 돌아간다.**

PyTorch 의 큰 텐서, NumPy 의 큰 배열, Pillow 의 큰 이미지 버퍼는 단일 할당이 128 KiB 를 훌쩍 넘어 mmap 경로로 가는 게 보통이다. 이런 객체는 `del` 후 RSS 가 잘 줄어든다. 문제는 **작은 메타데이터 버퍼·내부 청크가 수없이 alloc/free 되는 워크로드** 다. 이것들은 모두 brk heap 으로 들어간다.

### free 된 청크는 어디로 가나

`free()` 가 호출돼도 OS 로 곧바로 안 간다. 다음 bin 중 하나에 보관된다.

- **fastbin** — 매우 작은 청크 (대개 ≤ 64 또는 80 바이트). LIFO single-linked
- **smallbin** — 512 바이트 미만, 정확 크기별 double-linked
- **largebin** — 그 이상, 크기 정렬된 double-linked
- **unsorted bin** — 방금 free 된 청크의 임시 보관소. 다음 malloc 에서 분류됨
- **top chunk** — heap 최상단의 연속 free 영역. heap 을 줄여 OS 로 반환할 수 있는 유일한 부분

이 자료구조는 **재사용 효율** 을 위한 것이다. 다음 malloc 이 같은 크기를 요구하면 bin 에서 꺼내쓴다. 매번 OS 에 syscall 을 보내지 않아도 되니 빠르다.

대가는 — heap 중간에 free chunk 가 흩어진 채로 남는다는 것. 이게 **단편화(fragmentation)** 다.

### 자동 트림 (M_TRIM_THRESHOLD)

heap 최상단(top chunk) 의 연속 free 영역이 충분히 자랐을 때만 자동 트림이 발동한다.

> When the amount of contiguous free memory at the top of the heap grows sufficiently large, free() employs sbrk(2) to release this memory back to the system. (`man mallopt`)

기본값은 `128 * 1024` 바이트 (128 KiB). top chunk 가 이걸 넘으면 `free()` 가 내부적으로 `sbrk(-N)` 으로 heap 을 줄인다.

**중요한 함정** — 자동 트림은 **top chunk** 만 본다. heap 중간에 갇힌 free chunk 는 트림 대상이 아니다. 위쪽에 살아있는 객체가 하나라도 있으면 그 아래의 free 영역은 OS 로 못 돌아간다.

## gc.collect() 가 못 푸는 것

CPython 의 `gc.collect()` 는 두 가지를 한다.

1. cyclic reference 가 만든 garbage 정리 (사이클이 아닌 garbage 는 참조 카운트가 평소에 자동 회수)
2. 회수한 객체에 대한 `__del__` 호출 + 메모리 반환

여기까지 끝나면 객체는 C 의 `free()` 로 반환된다. 그런데 그 반환처는 OS 가 아니다. **pymalloc 의 arena pool 또는 glibc 의 bin** 이다. 두 단계 모두 캐시 계층이라 OS RSS 는 그대로다.

흔한 오해 — "메모리 누수가 있나? `gc.collect()` 를 더 자주 부르자". 부르는 건 자유지만 안 풀린다. 누수가 아니라 **계층 캐시의 가시화 지연** 이다.

## malloc_trim(0) 의 역할

`malloc_trim(pad)` 는 glibc 가 제공하는 명시적 트림 요청 API 다.

```c
#include <malloc.h>
int malloc_trim(size_t pad);
```

- `pad`: heap top 에 남겨둘 여유 공간. `0` 이면 한 페이지(4 KiB) 만 남기고 모두 반환
- 반환 값: 실제 OS 로 반환했으면 `1`, 못 했으면 `0`
- 메인 아레나는 `sbrk(-N)` 으로, 스레드 아레나는 `madvise(MADV_DONTNEED)` 로 페이지 단위 반환

자동 트림과 다른 점 — **모든 아레나를 순회하며 적극적으로 회수를 시도한다.** glibc 2.8 이후로는 메인 아레나 top 외에도 page-aligned whole free page 가 있는 chunk 도 `madvise` 로 OS 에 반환한다.

### 한계

`malloc_trim` 도 만능이 아니다.

- **단편화가 있으면 효과 제한** — heap 최상단의 연속 free 영역만 회수 대상. 중간에 갇힌 free chunk 는 그대로
- **호출 비용** — heap 전체를 스캔. fastbin 통합, top chunk 검사 등의 작업이 따라온다. 모든 `free()` 후마다 부르면 성능 저하

## Python 에서 호출하는 패턴

`ctypes` 로 직접 호출한다.

```python
import ctypes, gc, sys

_libc = ctypes.CDLL("libc.so.6") if sys.platform == "linux" else None

def release_unused_memory() -> None:
    gc.collect()
    if _libc is not None:
        _libc.malloc_trim(0)
```

호출 시점 결정이 핵심이다.

- **너무 자주** — heap 스캔 비용 누적, 처리량 저하
- **너무 드물게** — RSS 가 충분히 줄어들 시점을 놓침

실용적인 패턴은 "큰 작업 단위 종료 후" 다. 예를 들어 문서 한 건 변환 후, 배치 한 사이클 후, 청크 처리 후. 매 요청마다는 보통 과하다.

## 다른 회피책 비교

### 워커 재활용

가장 흔하고 확실한 방법. Gunicorn `--max-requests`, uWSGI `max-requests`, Celery `worker_max_tasks_per_child`. 워커가 N 요청 처리 후 죽고 OS 가 모든 메모리를 회수한다.

장점 — 단순하고 예측 가능. malloc_trim 이 단편화 때문에 부분 효과만 보이는 케이스에서도 확실히 회수한다.

단점 — 새 워커 spawn 비용 (warmup). 모델 가중치 로드, cache 초기화, JIT compile 등이 다시 일어난다.

### M_TRIM_THRESHOLD 임계값 낮춤

`mallopt(M_TRIM_THRESHOLD, ...)` 로 자동 트림 임계값을 낮춘다. 모든 `free()` 마다 트림 시도가 활발해진다.

단점 — 매 `free()` 마다 overhead. 명시적 `malloc_trim` 호출이 호출 시점 통제 면에서 더 유리하다.

### jemalloc / mimalloc 같은 대체 allocator

`LD_PRELOAD` 로 glibc malloc 을 다른 allocator 로 갈아끼운다. 단편화 특성이 다르고, 메모리를 OS 로 더 적극적으로 돌려주는 정책을 갖는 경우가 많다.

주의 — Polars (Rust) 처럼 자체 allocator 를 빌드 타임에 박은 라이브러리는 glibc `malloc_trim` 영향권 밖이다. 별도 API 가 필요. allocator 선택은 라이브러리 조합에 따라 다르니 일반화하기 어렵다.

## 정리

- `gc.collect()` 는 Python 객체 사이클만 정리한다. OS 메모리 반환과 무관
- glibc malloc 은 free 된 청크를 bin 에 캐시한다. 자동 트림은 heap top 의 연속 영역만 대상
- 단편화가 있으면 자동 트림은 발동 조건을 못 만난다. RSS 가 단조 증가하는 주된 메커니즘
- `malloc_trim(0)` 은 모든 아레나를 순회하며 적극적으로 회수를 시도. 단편화 시 한계는 있지만 자동 트림보다 효과적
- 워커 재활용 (`max-requests`) 과 `malloc_trim` 은 보완적이다. 둘 다 박는 것도 흔한 패턴

진단 출발선 — `/proc/<pid>/status` 의 `VmRSS` 와 `VmData` 추세를 본다. 큰 객체 alloc/free 가 잘 회수되면 mmap 경로. 잘 안 회수되면 brk heap 의 단편화 의심.

## 실제 적용 사례

### 문서 파싱 API 의 워커 RSS 누적 해결

본 글의 "Python 에서 호출하는 패턴" 단락이 정확히 그 상황이다.

- `ProcessPoolExecutor` 기반 워커가 Docling 파이프라인으로 PDF·PPTX 등을 markdown 으로 변환
- 워커당 RSS 가 시간당 약 1.4 GB 증가, `MAX_TASKS_PER_WORKER=3` 으로 방어 중이었음
- `gc.collect()` 8 곳 호출을 `release_unused_memory()` helper 로 일괄 교체
- ca901 카나리에서 180 호출 부하 테스트로 회귀 0 건 검증

→ [Python 서버 RSS 가 안 줄어들어 malloc_trim 을 박은 이야기](../task/ai-service-team/glibc-malloc-trim-python-leak.md)

## 참고

- [malloc_trim(3) — Linux manual page](https://man7.org/linux/man-pages/man3/malloc_trim.3.html)
- [mallopt(3) — Linux manual page](https://man7.org/linux/man-pages/man3/mallopt.3.html)
- [Malloc Internals and You — Red Hat Developer](https://developers.redhat.com/blog/2017/03/02/malloc-internals-and-you)
- [Run Python Applications Efficiently With malloc_trim — Software at Scale](https://www.softwareatscale.dev/p/run-python-servers-more-efficiently)
- [Stop Python from Hoarding Memory with One Extra Step — Medium](https://medium.com/programmed-iq/stop-python-from-hoarding-memory-with-one-extra-step-b495d67e4f08)
- [Working Around Memory Leaks in Your Django Application — Adam Johnson](https://adamj.eu/tech/2019/09/19/working-around-memory-leaks-in-your-django-app/)
- [GLibc malloc internal: arena, bin, chunk and sub heap — jipanyang](https://jipanyang.wordpress.com/2014/06/09/glibc-malloc-internal-arena-bin-chunk-and-sub-heap-1/)
- [Glibc Malloc Source Code Analysis — openEuler](https://www.openeuler.org/en/blog/wangshuo/Glibc_Malloc_Source_Code_Analysis_(1).html)
- [HN discussion: Run Python Applications Efficiently with malloc_trim](https://news.ycombinator.com/item?id=25113636)
- [glandium — When the memory allocator works against you](https://glandium.org/blog/?p=3723)
