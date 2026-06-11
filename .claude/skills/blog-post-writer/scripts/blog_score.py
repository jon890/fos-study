#!/usr/bin/env python3
"""
blog_score.py — blog-post-writer 단일 글 품질 reward (정적 축)

한 블로그 글(.md)의 *정적으로 채점 가능한* 문체 위반을 가중 감점으로 환산한다.
docs_score(저장소 전체) 와 달리 단일 글 대상이라, 두 용도로 쓴다.

  1. 글 작성 직후 자가점검 자동화 (markdown-pitfalls 체크리스트의 코드화)
  2. SkillOpt-Sleep 의 external_score reward (단일 response 채점)

정적이 못 잡는 의미 품질(인사이트·AI 티·흐름)은 LLM judge 영역 — 여기 없음.
이것은 2계층 reward 의 *1계층(회귀 방지 바닥)* 이다.

사용:
  python3 blog_score.py <글.md>          # 위반 리포트
  python3 blog_score.py --json <글.md>    # 기계 판독용 (sleep 연동)
  라이브러리: from blog_score import score_text; n, details = score_text(md)
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 위반 가중치 — markdown-pitfalls 우선순위 반영
WEIGHTS = {
    "bold_quote": 3,      # **"..."** — bold 렌더 실패
    "bold_paren": 3,      # **텍스트(영문)** — bold 렌더 실패
    "heading_number": 3,  # ## 1. 제목 — fos-blog 자동번호와 이중
    "ascii_box": 2,       # ┌│▼ 박스 다이어그램 — mermaid 권장
    "tilde": 2,           # ~ 취소선 함정
    "section_sign": 2,    # § 특수문자
    "italic_paren": 2,    # *한글(영문)* — 이탤릭 렌더 실패
    "number_crossref": 1, # "위 3번", "섹션 2" — 자동번호와 어긋남
}

CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE = re.compile(r"`[^`]*`")

BOLD_QUOTE = re.compile(r'\*\*"|"\*\*')
BOLD_PAREN = re.compile(r"\*\*([^*]*?\([^)]*\))\*\*")
ITALIC_PAREN = re.compile(r"(?<!\*)\*([가-힣A-Za-z]+\([^)]+\))\*(?!\*)")
HEADING_NUM = re.compile(r"(?m)^#+\s+[0-9]+\.")
NUMBER_CROSSREF = re.compile(r"위 [0-9]+|[0-9]+개 항목|[0-9]+번 항목|섹션 [0-9]+")
# 박스 전용 글자만 (트리 ├└─ 는 디렉터리 트리라 제외; ┌┐┘▼ 는 박스에만 등장)
ASCII_BOX = re.compile(r"[┌┐┘▼]")


def _mask(text):
    text = CODE_FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return INLINE.sub(" ", text)


def score_text(text):
    """단일 글 텍스트 → (위반 총수, {축: [근거...]})."""
    masked = _mask(text)
    d = {k: [] for k in WEIGHTS}

    for m in BOLD_QUOTE.finditer(masked):
        d["bold_quote"].append(m.group(0))
    for m in BOLD_PAREN.finditer(masked):
        body = m.group(1)
        if body.count("(") >= 2 or "()" in body or "[" in body or "]" in body:
            continue
        if not body[:body.index("(")].strip():
            continue
        d["bold_paren"].append(m.group(0))
    for m in HEADING_NUM.finditer(masked):
        d["heading_number"].append(m.group(0))
    # ascii_box 만 원문 검사 — 박스 다이어그램은 코드펜스 안에 두는 게 보통이고
    # 그걸 mermaid 로 바꾸라는 규칙이라 마스킹하면 안 잡힌다 (트리 ├└─ 는 제외)
    if ASCII_BOX.search(text):
        d["ascii_box"].append("box-drawing char")
    d["section_sign"] += ["§"] * masked.count("§")
    if ITALIC_PAREN.search(masked):
        d["italic_paren"].append("italic+paren")
    for m in NUMBER_CROSSREF.finditer(masked):
        d["number_crossref"].append(m.group(0))
    # tilde — paragraph 내 unescaped non-homepath ~ 2개+
    for para in re.split(r"\n\s*\n", masked):
        tmp = re.sub(r"~/[\w./-]+", "", para.replace("\\~", ""))
        if tmp.count("~") >= 2:
            d["tilde"].append("range-tilde paragraph")

    total = sum(len(v) for v in d.values())
    return total, d


def penalty(details):
    return sum(WEIGHTS[k] * len(v) for k, v in details.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--log", default="", help="축별 위반을 이 경로에 누적 기록 (hook 용)")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8", errors="ignore")
    total, d = score_text(text)
    pen = penalty(d)

    if args.log:
        import datetime
        rel = args.file.split("/fos-study/")[-1]
        rec = {
            "file": rel, "violations": total,
            "counts": {k: len(v) for k, v in d.items()},
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with open(args.log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if total > 0:
            print(f"⚠ 자동 채점 — {rel} 정적 문체 위반 {total}건 (blog_score.py 로 상세 확인)")
        return 0

    if args.json:
        print(json.dumps({
            "file": args.file, "violations": total,
            "penalty": pen, "score": -pen,
            "counts": {k: len(v) for k, v in d.items()},
            "details": d,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"# blog_score — {args.file}")
    print(f"위반 {total}건  /  score {-pen}\n")
    print(f"{'축':<18}{'위반':>5}{'가중':>5}{'감점':>7}")
    print("-" * 35)
    for k in WEIGHTS:
        n = len(d[k])
        print(f"{k:<18}{n:>5}{WEIGHTS[k]:>5}{-WEIGHTS[k]*n:>7}")
        for ex in d[k][:3]:
            print(f"    └ {ex}")
    print("-" * 35)
    print(f"{'SCORE':<18}{'':>5}{'':>5}{-pen:>7}")
    if total == 0:
        print("\n✓ 정적 문체 위반 없음 — 1계층 게이트 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
