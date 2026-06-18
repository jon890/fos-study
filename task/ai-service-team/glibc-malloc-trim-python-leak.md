---
series: "AI 서비스 실전 구축·운영"
seriesOrder: 5
---

# Python 서버 RSS 가 안 줄어들어 malloc_trim 을 박은 이야기

**진행 기간**: 2026.05

> 개념 정리는 [Python 서버의 RSS 가 안 줄어드는 이유 — gc.collect 의 한계와 malloc_trim](../../python/python-rss-leak-glibc-malloc-trim.md) 참고. 본 글은 그 개념을 실제 운영 환경에 적용한 작업기.

## 배경

문서 파싱 API 의 운영을 보다가 워커 프로세스의 실제 메모리 사용량(RSS)이 시간당 약 1.4 GB 씩 증가하는 패턴을 발견했다. PDF·PPTX·HWP 같은 문서를 Docling 파이프라인으로 markdown 으로 변환하는 서버고, `ProcessPoolExecutor` 로 띄운 워커가 요청을 처리한다.

운영에서는 이 누수를 막기 위해 `MAX_TASKS_PER_WORKER=3` 으로 박아두고 있었다. 워커가 3 작업만 처리하면 강제로 죽고 새로 spawn 한다. OS 가 죽은 프로세스의 모든 메모리를 회수하니 RSS 가 다시 깨끗해진다. 단순한 방어책인데, 매번 워밍업 비용이 발생한다 — 새 워커는 모델 가중치 로드와 cache 초기화를 처음부터 다시 한다.

처음에는 "그냥 `gc.collect()` 를 자주 부르면 되지 않나" 라고 안일하게 생각했다. 코드를 보니 이미 청크 처리 후마다 호출하고 있었다. 그런데도 RSS 가 줄지 않았다. 왜 안 줄어드는지 진단하면서 glibc malloc 의 동작을 다시 읽게 됐고, 그 결과로 `release_unused_memory()` 라는 helper 를 만들어 8 곳의 `gc.collect()` 호출을 일괄 교체했다.

본 글은 그 진단·결정·검증 과정을 정리한 기록이다.

## gc.collect() 가 RSS 를 안 줄이는 이유

먼저 짚어둘 것 — CPython 의 `gc.collect()` 는 OS 메모리 반환과 무관하다. 두 가지만 한다.

1. 참조 카운트 사이클 (cyclic reference) 정리
2. cyclic GC 가 모은 garbage 회수

회수된 객체는 결국 C 의 `free()` 로 반환되지만, 그 반환처가 OS 가 아니다. 두 단계의 캐시 계층을 거친다.

- (a) Python 의 pymalloc — 512 바이트 이하 객체. arena pool 에 보관
- (b) glibc 의 ptmalloc2 — 그 이상. bin 자료구조에 보관

(b) 단계의 free chunk 는 glibc 안에 머무르고 OS 의 RSS 카운터에는 그대로 남는다. `gc.collect()` 를 아무리 자주 불러도 이 계층을 비우는 호출이 아니라서 효과가 없다.

## glibc 의 메모리 할당 전략

glibc 의 `malloc()` 은 요청 크기에 따라 두 경로로 갈린다.

- **작은 청크**(< `M_MMAP_THRESHOLD`, 기본 128 KiB): `brk(2)` / `sbrk(2)` 로 확장된 heap 영역에 배치. 우리가 흔히 "프로세스의 heap" 이라고 부르는 영역
- **큰 청크**(≥ 임계값): `mmap(2)` 으로 별도 영역을 잡아 단독 chunk 로 둔다

큰 청크가 free 될 때는 `munmap(2)` 으로 OS 에 즉시 반환된다. 그래서 큰 텐서나 이미지 버퍼처럼 단일 할당이 큰 객체는 해제 직후 RSS 가 잘 줄어든다. 문제는 **작은 청크**다. brk heap 안에서 free 된 청크는 OS 로 안 가고 glibc 의 bin 자료구조 — fastbin, smallbin, largebin, unsorted bin — 중 하나로 들어간다.

heap 의 최상단(top chunk)에 인접한 연속 free 영역이 충분히 자랐을 때만 자동 트림이 발동한다. 임계값은 `M_TRIM_THRESHOLD` (기본 128 KiB) 이고, top chunk 가 이 값을 넘으면 `free()` 가 내부적으로 `sbrk(-N)` 으로 heap 을 줄인다. 단 — heap 중간에 갇힌 free chunk 는 트림 대상이 아니다. 이게 단편화(fragmentation)다.

## 우리 서버의 상황을 가설로 정리

진단 단계에서 내가 세운 가설은 다음과 같다.

- Docling 파이프라인이 페이지마다 작은 버퍼를 수없이 alloc/free 한다 (이미지 cell, OCR 영역, 텍스트 chunk 등)
- 이 중 상당수가 `M_MMAP_THRESHOLD` 미만이라 brk heap 으로 간다
- 작업이 끝나도 heap 중간에 free chunk 가 흩어져 단편화. top chunk 가 충분히 자라지 않아 자동 트림 발동 조건을 못 만난다
- `gc.collect()` 는 Python 객체만 정리하고 이 단편화에는 손도 못 댄다
- 결과: RSS 단조 증가 → `MAX_TASKS_PER_WORKER=3` 의 워커 강제 종료만이 회수 수단

가설은 가설이지만, 적어도 "gc.collect() 만으로 안 풀린다" 는 결론은 확실했다.

## malloc_trim(0) 의 정확한 동작

glibc 매뉴얼 (`man 3 malloc_trim`) 인용:

> attempts to release free memory from the heap (by calling sbrk(2) or madvise(2) with suitable arguments).

- 인자 `pad` 는 heap top 에 남겨둘 여유 공간. `0` 이면 한 페이지(4 KiB)만 남기고 모두 반환
- 반환 값: 실제 OS 로 반환했으면 `1`, 못 했으면 `0`
- 메인 아레나는 `sbrk(-N)` 으로, 스레드 아레나는 `madvise(MADV_DONTNEED)` 로 페이지 단위 반환

**핵심 제약** — 단편화가 있으면 효과가 제한된다. heap 최상단의 연속 free 영역만 회수 대상이고, 중간에 갇힌 free chunk 는 그대로 남는다. 그래도 자동 트림보다 적극적으로 회수를 시도하므로 정기 호출 가치는 있다.

glibc 2.8 이후로는 메인 아레나 top 외에도 모든 아레나를 순회하며 page-aligned whole free page 가 있는 chunk 도 `madvise` 로 반환한다. 우리 운영 컨테이너는 그 이후 버전이라 이 동작도 기대할 수 있다.

## helper 함수 설계

`gc.collect()` 8 곳을 그냥 `malloc_trim` 으로 바꿀 수도 있었지만, "메모리 회수" 의도를 한 함수에 캡슐화하는 편이 향후 변경 (예: CUDA 메모리 해제 추가) 에 유리하다고 봤다. 그래서 `util/memory.py` 를 신설하고 `release_unused_memory()` 라는 한 함수로 묶었다.

```python
# util/memory.py — 개념 설명용 의사코드
import ctypes, gc, logging, os, sys

_log = logging.getLogger(__name__)
_ENABLE_MALLOC_TRIM = os.environ.get("ENABLE_MALLOC_TRIM", "true").lower() == "true"
_IS_LINUX = sys.platform == "linux"

try:
    _libc = ctypes.CDLL("libc.so.6") if (_IS_LINUX and _ENABLE_MALLOC_TRIM) else None
except OSError as e:
    _log.warning("libc.so.6 로드 실패 (malloc_trim 비활성): %s", e)
    _libc = None

def release_unused_memory() -> None:
    gc.collect()
    if _libc is not None:
        try:
            _libc.malloc_trim(0)
        except Exception as e:
            _log.warning("malloc_trim 호출 실패: %s", e, exc_info=True)
```

설계 결정 몇 가지를 메모로 남겨둔다.

- **모듈 로드 시 1회 분기** — 런타임마다 `sys.platform` 체크하는 비용을 회피. mac 로컬 개발 환경에서는 `_libc = None` 이 되어 noop
- **env 토글**(`ENABLE_MALLOC_TRIM`, 기본 `true`) — 운영 사고 시 즉시 비활성할 수 있는 hot config. 트림 자체가 일으킨 회귀가 의심되면 컨테이너 재시작 없이 끄려고 했지만, 결국 env 변경 자체가 재시작을 요구한다는 한계는 있다
- **`mallopt(M_TRIM_THRESHOLD)` 임계값 낮춤은 기각** — 매 `free()` 마다 자동 적용되어 호출 overhead. 우리 patch 의 명시 호출(청크 단위) 이 비용 통제하기 쉽다

## ca901 카나리에서 검증

검증은 한 대(ca901)만 swap-container.sh 로 새 이미지(`TEST_2026.05.21-3`) 로 교체한 뒤 진행했다. drain 으로 LB 격리 후 180 호출 (30 라운드 × 6 sample, 동시 6) 부하 테스트.

| 시점 | kr 워커 RSS 합 (GB) | restart_kr |
|---|---|---|
| T0 baseline | 13.20 | 0 |
| 부하 5분 | 13.88 | 0 |
| 부하 6분 | 12.73 | 1 (첫 워커 자연 종료) |
| 부하 10분 | 13.33 | 6 (모두 1회씩 종료) |
| 부하 종료 직후 | 12.39 | 6 |
| 안정화 | 12.39 | 6 |

결과 정리:

- 180/180 HTTP 200, 회귀 0건
- RSS 가 13\~14 GB 사이 진동, 단조 증가 패턴은 나타나지 않았다
- cgroup memory 한도 27g (32GB 호스트의 85%) 미발동, `RAM_RESTART_THRESHOLD=80%` 도 미발동

### 검증의 한계

부하 테스트 동안 `MAX_TASKS_PER_WORKER=20` 으로 올려뒀다. 이렇게 하면 워커가 20 작업마다 자연 종료해 그 시점에 OS 가 메모리를 회수한다. 즉, RSS 가 안정적이었던 게 plan009 의 `release_unused_memory()` 단독 효과인지, max_tasks 종료 효과인지 격리하지 못했다.

엄밀히 격리하려면 `MAX_TASKS_PER_WORKER=50` 이상으로 올려 워커가 죽기 전 누적 효과를 봐야 한다. 그건 별도 사이클로 미뤘다. 적어도 회귀 0건은 확인됐고, 단편화로 트림 효과가 제한되더라도 추가 안전망(`--memory` cgroup 한도) 이 작동하니 운영 배포 가능하다고 판단했다.

## 같은 함정에 빠진 다른 사례들

조사 중에 알게 된 사실 — 이 패턴은 Python 진영에서 잘 알려진 함정이다.

- uWSGI / Gunicorn 의 `max-requests` 옵션, Celery 의 `worker_max_tasks_per_child` 가 모두 같은 문제의 우회책이다. 우리의 `MAX_TASKS_PER_WORKER=3` 도 본질은 동일하다
- Polars 처럼 Rust 의 자체 allocator (jemalloc / mimalloc) 를 쓰는 라이브러리는 glibc `malloc_trim` 영향권 밖이다. 별도 API 필요
- PyTorch / NumPy 같은 C-extension 은 큰 텐서는 mmap 경로로 가서 free 시 즉시 반환되지만, 작은 메타데이터 버퍼는 brk heap 에 누적된다

Adam Johnson (Django 코어 컨트리뷰터) 의 글이 "결국 워커 재활용이 가장 단순하고 예측 가능하다" 고 결론지은 게 인상적이었다. 우리는 워커 재활용(`MAX_TASKS=3`)에 더해 `malloc_trim` 까지 박은 셈인데, 그 둘 사이의 정량적 효과 비교는 아직 못 했다.

## 지금 보면

helper 함수로 묶은 결정은 옳았지만, 검증 설계는 약했다. `MAX_TASKS=20` 으로 부하를 돌린 시점에 "trim 단독 효과를 격리할 수 없는 설정" 임을 충분히 인지하지 못했다. 검증 결과가 좋아 보였던 건 trim 과 워커 재활용이 함께 일하면서 어느 쪽이 얼마나 기여했는지 분리되지 않았기 때문이다.

malloc_trim 도 만능이 아니다. 단편화가 심한 워크로드라면 호출해도 RSS 가 잘 안 줄어든다. 운영에서 정말 의미 있게 동작하는지는 `MAX_TASKS_PER_WORKER` 를 단계적으로 올리면서 (3 → 10 → 20 → 50) RSS 추세를 비교해야 알 수 있다. 그건 다음 사이클의 숙제로 남겨뒀다.

코드보다 "왜 그게 안 통하는가" 에 대한 답을 손에 쥐는 게 더 큰 수확이었다. `gc.collect()` 를 부르면 메모리가 회수된다는 흔한 직관이 어디서 깨지는지 — pymalloc 의 arena, glibc 의 bin, brk vs mmap, 그리고 단편화 — 를 한 번 정리해두면 다음에 비슷한 증상을 만났을 때 진단 출발선이 달라진다.

## 참고

- [malloc_trim(3) — Linux manual page](https://man7.org/linux/man-pages/man3/malloc_trim.3.html)
- [mallopt(3) — Linux manual page](https://man7.org/linux/man-pages/man3/mallopt.3.html)
- [Malloc Internals and You — Red Hat Developer](https://developers.redhat.com/blog/2017/03/02/malloc-internals-and-you)
- [Run Python Applications Efficiently With malloc_trim — Software at Scale](https://www.softwareatscale.dev/p/run-python-servers-more-efficiently)
- [Stop Python from Hoarding Memory with One Extra Step — Medium](https://medium.com/programmed-iq/stop-python-from-hoarding-memory-with-one-extra-step-b495d67e4f08)
- [Working Around Memory Leaks in Your Django Application — Adam Johnson](https://adamj.eu/tech/2019/09/19/working-around-memory-leaks-in-your-django-app/)
- [GLibc malloc internal: arena, bin, chunk and sub heap — jipanyang](https://jipanyang.wordpress.com/2014/06/09/glibc-malloc-internal-arena-bin-chunk-and-sub-heap-1/)
- [HN discussion: Run Python Applications Efficiently with malloc_trim](https://news.ycombinator.com/item?id=25113636)
