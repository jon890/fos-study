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

RUBRIC_HEAD = """당신은 한국 기술 블로그 글을 엄격하게 평가하는 시니어 개발자다.
다음 기준으로 글 품질을 0.0~1.0 으로 채점한다."""

# 모든 글 공통 축
RUBRIC_COMMON = """- AI 티 없음: "매우 중요합니다", "다음과 같이 정리할 수 있습니다", 기계적 나열, 대칭 양분, 과장이면 감점.
- 한국어 자연스러움: 영어 직역투·생소한 비유어(surgical→"외과적", triage→"트리아지" 류)로 한국 독자가 한 번에 못 읽으면 감점. 코드 식별자·표준 영어 용어는 예외."""

# 케이스 A — 본인이 직접 구현/운영한 업무 경험 글
RUBRIC_EXPERIENCE = """- 인사이트 독창성: 교과서에 있는 일반론이면 감점. 직접 삽질한 사람만 아는 관점이면 가점.
- 서사 흐름: 발견→분석→해결의 인과가 살아 있으면 가점. 사실 나열뿐이면 감점.
- 회고·협업의 자연스러움: 이력서 bullet 처럼 박제됐으면 감점. 서사에 녹았으면 가점."""

# 케이스 B — 외부 기술/개념을 공부해 정리한 스터디 글
# 직접 삽질·1차 경험·회고는 이 유형에 없는 게 정상이므로 평가하지 않는다.
RUBRIC_STUDY = """이 글은 본인이 직접 구현한 경험담이 아니라 외부 기술/개념을 공부해 정리한 스터디 글이다.
따라서 "직접 삽질한 경험"·"회고·협업"의 부재를 감점하지 마라. 그 대신 다음을 본다.
- 사실 정확성·교차검증: 공식 소스에 근거하는가. 통념을 비판적으로 따져보거나 잘못된 서술을 바로잡으면 가점. 부정확·근거 없는 단정이면 감점.
- 재해석: 검색 결과를 번역·복붙한 수준이면 감점. 본인 언어로 소화해 핵심을 추리고 구조를 부여했으면 가점.
- 개념 전달력: 처음 보는 독자가 따라올 수 있게 개념이 논리적으로 연결되면 가점. 목차식 사실 나열에 그치면 감점.
- 비판적 시각: 한계·트레이드오프·언제 쓰고 언제 피할지를 짚으면 가점."""

RUBRIC_TAIL = "후하게 주지 마라. 평범한 글은 0.5 근처다. 0.8 이상은 정말 뛰어난 글에만 준다."


def detect_type(path, text):
    """글 유형 자동 감지 — task/ 경로 또는 '진행 기간' 헤더면 experience, 그 외 study(보수적)."""
    p = path.replace("\\", "/")
    if "/task/" in p or p.startswith("task/"):
        return "experience"
    if re.search(r"\*\*진행\s*기간\*\*", text):
        return "experience"
    return "study"


def build_rubric(doc_type):
    body = RUBRIC_EXPERIENCE if doc_type == "experience" else RUBRIC_STUDY
    return f"{RUBRIC_HEAD}\n\n{body}\n{RUBRIC_COMMON}\n\n{RUBRIC_TAIL}"

PROMPT_TAIL = (
    "\n\n먼저 이 글의 가장 큰 약점 3가지를 찾아라. 그 약점을 반영해 점수를 정하라.\n"
    'Return ONLY JSON: {"weaknesses": ["...","...","..."], "score": <0.0~1.0>, "reason": "<한 줄>"}'
)


def judge_once(text, model="", doc_type="study"):
    prompt = f"{build_rubric(doc_type)}{PROMPT_TAIL}\n\n=== 평가 대상 글 ===\n{text}"
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


def score_quality(text, n=3, model="", doc_type="study"):
    results = [judge_once(text, model, doc_type) for _ in range(n)]
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
    ap.add_argument("--type", choices=["auto", "experience", "study"], default="auto",
                    help="글 유형 (기본 auto — task/ 경로·진행 기간 헤더로 감지)")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8", errors="ignore")
    doc_type = detect_type(args.file, text) if args.type == "auto" else args.type
    median, results = score_quality(text, n=args.n, model=args.model, doc_type=doc_type)

    if args.json:
        print(json.dumps({
            "file": args.file, "doc_type": doc_type, "quality": median,
            "n_valid": len(results), "judgements": results,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"# blog_judge — {args.file}")
    print(f"유형: {doc_type}  /  품질 점수 (median of {len(results)}): {median:.2f}\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] score={r.get('score')}  {r.get('reason','')}")
        for w in r.get("weaknesses", [])[:3]:
            print(f"     약점: {w}")
    thr = 0.7
    print(f"\n{'✓ 2계층 통과' if median >= thr else '✗ 2계층 미달'} (기준 {thr})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
