#!/usr/bin/env python3
"""
blog_judge.py — blog-post-writer 글 품질 reward (2계층, LLM judge)

blog_score(1계층·정적)가 못 잡는 *의미 품질*을 claude CLI 로 채점한다.
인사이트 독창성·AI 티·서사 흐름·회고 자연스러움 같은 건 정규식으로 못 본다.

LLM judge 의 함정(grade inflation·비결정)을 두 장치로 막는다:
  1. 다수결 — N회 호출의 median (이상치 제거)
  2. adversarial — 매 호출이 "약점 3개를 먼저 찾고" 채점 (후한 점수 방어)

2계층 reward 의 천장. 1계층(blog_score 위반 0) 통과분만 여기 올려 비용을 아낀다.

사용:
  python3 blog_judge.py <글.md>            # 품질 채점 (기본 3회 다수결)
  python3 blog_judge.py --n 5 <글.md>       # 호출 횟수
  python3 blog_judge.py --json <글.md>
요구: claude CLI 가 PATH 에 있어야 한다 (기존 자격증명 사용, API 비용 발생).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RUBRIC = """당신은 한국 기술 블로그 글을 엄격하게 평가하는 시니어 개발자다.
다음 기준으로 글 품질을 0.0~1.0 으로 채점한다.

- 인사이트 독창성: 교과서에 있는 일반론이면 감점. 직접 삽질한 사람만 아는 관점이면 가점.
- AI 티 없음: "매우 중요합니다", "다음과 같이 정리할 수 있습니다", 기계적 나열, 과장이면 감점.
- 서사 흐름: 발견→분석→해결의 인과가 살아 있으면 가점. 사실 나열뿐이면 감점.
- 회고·협업의 자연스러움: 이력서 bullet 처럼 박제됐으면 감점. 서사에 녹았으면 가점.

후하게 주지 마라. 평범한 글은 0.5 근처다. 0.8 이상은 정말 뛰어난 글에만 준다."""

PROMPT_TAIL = (
    "\n\n먼저 이 글의 가장 큰 약점 3가지를 찾아라. 그 약점을 반영해 점수를 정하라.\n"
    'Return ONLY JSON: {"weaknesses": ["...","...","..."], "score": <0.0~1.0>, "reason": "<한 줄>"}'
)


def judge_once(text, model=""):
    prompt = f"{RUBRIC}{PROMPT_TAIL}\n\n=== 평가 대상 글 ===\n{text}"
    cmd = ["claude", "-p", prompt]
    if model:
        cmd += ["--model", model]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180).stdout
    except subprocess.TimeoutExpired:
        return None
    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def score_quality(text, n=3, model=""):
    results = [judge_once(text, model) for _ in range(n)]
    results = [r for r in results if r and "score" in r]
    if not results:
        return 0.0, results
    scores = sorted(float(r["score"]) for r in results)
    median = scores[len(scores) // 2]
    return median, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--model", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8", errors="ignore")
    median, results = score_quality(text, n=args.n, model=args.model)

    if args.json:
        print(json.dumps({
            "file": args.file, "quality": median,
            "n_valid": len(results), "judgements": results,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"# blog_judge — {args.file}")
    print(f"품질 점수 (median of {len(results)}): {median:.2f}\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] score={r.get('score')}  {r.get('reason','')}")
        for w in r.get("weaknesses", [])[:3]:
            print(f"     약점: {w}")
    thr = 0.7
    print(f"\n{'✓ 2계층 통과' if median >= thr else '✗ 2계층 미달'} (기준 {thr})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
