#!/usr/bin/env python3
"""
docs_score.py — fos-study 문서 건전성 점수 측정기

docs-audit 7축 중 *객관적으로 채점 가능한* 축만 점수로 환산한다.
가시성(축 5)·cross-link(축 4) 은 주관 판단이라 점수에서 제외한다.

reward = -(가중 위반 합).  위반이 0이면 score = 0 (만점).
SkillOpt 의 reward 함수 역할 — 규칙 편집이 직전 버전 대비 개선인지 게이트로 쓴다.

사용:
  python3 docs_score.py                 # 측정 + 직전 대비 delta 출력
  python3 docs_score.py --save          # 측정 후 history 에 기록 (게이트 통과 시)
  python3 docs_score.py --json          # 기계 판독용 JSON 만 출력
  python3 docs_score.py --root <path>   # 대상 저장소 루트 지정
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 설정 ────────────────────────────────────────────────────────────────
# 점수에서 제외할 디렉터리 (외부 의존성·도구 문서·룰 인용 문서)
EXCLUDE_DIR_PARTS = {".git", "node_modules", ".claude", "k8s-in-action"}

# 문체 검사에서 제외할 파일 — 룰 자체를 예시로 인용하는 문서는 의도적 위반이 정답
STYLE_EXEMPT_PATTERNS = [
    "CLAUDE.md",
    "claude-code-usage-reflection",
    "blog-post-writer",
]

# orphan 판정 시 진입점으로 보아 제외 (어디서도 링크 안 돼도 정상)
ORPHAN_ENTRYPOINTS = {"README.md", "INDEX.md", "CLAUDE.md", "AGENTS.md"}

# 위반 가중치 — docs-audit 리포트 우선순위(높음/중간) 반영
WEIGHTS = {
    "broken_link": 5,      # 높음 — 링크가 깨지면 독자가 막힘
    "readme_missing": 3,   # 높음 — README 가 폴더 내용과 어긋남
    "orphan_doc": 2,       # 중간 — 어디서도 닿을 수 없는 문서
    "style_tilde": 2,      # 중간 — 취소선 오발동 (자동 수정 가능)
    "style_section": 2,    # 중간 — § 특수문자
    "style_bold_paren": 2, # 중간 — **텍스트(영문)** 렌더 실패
    "style_italic_paren": 2,
}

# ── 유틸 ────────────────────────────────────────────────────────────────
CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
LINK = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# **텍스트(영문)** — bold 본문이 닫는 ) 로 끝나는 패턴. 괄호 2회 이상이면 제외.
BOLD_PAREN = re.compile(r"\*\*([^*]*?\([^)]*\))\*\*")
# *한글/영문(...)* — 이탤릭+괄호
ITALIC_PAREN = re.compile(r"(?<!\*)\*([가-힣A-Za-z]+\([^)]+\))\*(?!\*)")


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIR_PARTS for part in path.parts)


def is_style_exempt(path: Path) -> bool:
    name = path.name
    return any(pat in name for pat in STYLE_EXEMPT_PATTERNS)


def mask_code(text: str) -> str:
    """코드 펜스·인라인 코드를 공백으로 치환해 문체 검사 false positive 차단."""
    text = CODE_FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = INLINE_CODE.sub(" ", text)
    return text


def paragraphs(text: str):
    for para in re.split(r"\n\s*\n", text):
        yield para


# ── 축별 검사 ────────────────────────────────────────────────────────────
def check_broken_links(md_files, root):
    """축 2 — [text](target) 의 .md/.mdx 내부 링크가 실제 파일인지."""
    findings = []
    file_set = {p.resolve() for p in md_files}
    for f in md_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        masked = INLINE_CODE.sub(" ", CODE_FENCE.sub(" ", text))
        for lineno, line in enumerate(masked.splitlines(), 1):
            for m in LINK.finditer(line):
                target = m.group(1).strip().split()[0]  # "url title" 형태 방어
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path_part = target.split("#")[0]
                if not path_part:
                    continue
                if not path_part.endswith((".md", ".mdx")):
                    continue
                if path_part.startswith("/"):
                    resolved = (root / path_part.lstrip("/")).resolve()
                else:
                    resolved = (f.parent / path_part).resolve()
                if resolved not in file_set and not resolved.exists():
                    findings.append({
                        "file": str(f.relative_to(root)),
                        "line": lineno,
                        "target": target,
                    })
    return findings


def check_orphans(md_files, root):
    """축 3 — 어느 문서에서도 링크되지 않은 .md (진입점 제외)."""
    linked = set()
    for f in md_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        masked = INLINE_CODE.sub(" ", CODE_FENCE.sub(" ", text))
        for m in LINK.finditer(masked):
            target = m.group(1).strip().split()[0]
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = target.split("#")[0]
            if not path_part.endswith((".md", ".mdx")):
                continue
            if path_part.startswith("/"):
                resolved = (root / path_part.lstrip("/")).resolve()
            else:
                resolved = (f.parent / path_part).resolve()
            linked.add(resolved)
    findings = []
    for f in md_files:
        if f.name in ORPHAN_ENTRYPOINTS:
            continue
        if f.resolve() not in linked:
            findings.append({"file": str(f.relative_to(root))})
    return findings


def check_readme_integrity(md_files, root):
    """축 7(부분) — 폴더 README 가 있으면 같은 폴더 .md 가 README 에 등재됐는지."""
    findings = []
    by_dir = {}
    for f in md_files:
        by_dir.setdefault(f.parent, []).append(f)
    for d, files in by_dir.items():
        readme = d / "README.md"
        if not readme.exists():
            continue
        readme_text = readme.read_text(encoding="utf-8", errors="ignore")
        for f in files:
            if f.name in ("README.md",):
                continue
            # README 본문에 파일명이 어떤 형태로든 언급되면 등재로 본다
            if f.name not in readme_text and f.stem not in readme_text:
                findings.append({
                    "readme": str(readme.relative_to(root)),
                    "missing": f.name,
                })
    return findings


def check_style(md_files, root):
    """축 6 — 문체 정적 위반 4종. 코드 마스킹 후 검사."""
    out = {"style_tilde": [], "style_section": [],
           "style_bold_paren": [], "style_italic_paren": []}
    for f in md_files:
        if is_style_exempt(f):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        masked = mask_code(text)
        rel = str(f.relative_to(root))

        # § 특수문자
        if "§" in masked:
            out["style_section"].append({"file": rel})

        # ~ 취소선 함정 — paragraph 내 unescaped ~ 가 2개 이상이고 home path 가 아님
        for para in paragraphs(masked):
            tmp = para.replace("\\~", "")          # escape 된 건 제외
            tmp = re.sub(r"~/[\w./-]+", "", tmp)   # shell home path 제외
            if tmp.count("~") >= 2:
                out["style_tilde"].append({"file": rel})
                break

        # **텍스트(영문)** 위반 — 단어 뒤에 괄호가 바로 붙어 bold 렌더가 깨지는 형태만.
        # 제외(false positive): 괄호 2회 이상, 빈 괄호(메서드명),
        #   bold 안 markdown 링크([..](..)), 괄호로 시작(**(VO)** 통괄호 강조)
        for m in BOLD_PAREN.finditer(masked):
            body = m.group(1)
            if body.count("(") >= 2 or "()" in body:
                continue
            if "[" in body or "]" in body:        # bold 안 markdown 링크
                continue
            before_paren = body[:body.index("(")].strip()
            if not before_paren:                  # **(영문)** — 괄호만 강조
                continue
            out["style_bold_paren"].append({"file": rel})
            break

        # *한글(영문)* 이탤릭+괄호
        if ITALIC_PAREN.search(masked):
            out["style_italic_paren"].append({"file": rel})
    return out


# ── 메인 ────────────────────────────────────────────────────────────────
def measure(root: Path):
    md_files = [p for p in root.rglob("*.md") if not is_excluded(p)]
    axes = {}
    axes["broken_link"] = check_broken_links(md_files, root)
    axes["orphan_doc"] = check_orphans(md_files, root)
    axes["readme_missing"] = check_readme_integrity(md_files, root)
    axes.update(check_style(md_files, root))

    penalty = sum(WEIGHTS[k] * len(v) for k, v in axes.items())
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files_scanned": len(md_files),
        "counts": {k: len(v) for k, v in axes.items()},
        "weights": WEIGHTS,
        "penalty": penalty,
        "score": -penalty,
        "details": axes,
    }


def load_last(history: Path):
    if not history.exists():
        return None
    lines = [l for l in history.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


def print_report(result, last):
    c = result["counts"]
    w = result["weights"]
    print(f"# 문서 건전성 점수 — {result['timestamp'][:19]}Z")
    print(f"스캔 파일: {result['files_scanned']}개\n")
    print(f"{'축':<22}{'위반':>6}{'가중':>6}{'감점':>8}")
    print("-" * 42)
    for k in WEIGHTS:
        sub = w[k] * c[k]
        print(f"{k:<22}{c[k]:>6}{w[k]:>6}{-sub:>8}")
    print("-" * 42)
    print(f"{'SCORE':<22}{'':>6}{'':>6}{result['score']:>8}")
    if last is not None:
        delta = result["score"] - last["score"]
        arrow = "▲ 개선" if delta > 0 else ("▼ 악화" if delta < 0 else "= 동일")
        print(f"\n직전: {last['score']}  →  현재: {result['score']}  "
              f"(Δ {delta:+d}  {arrow})")
        print(f"직전 시점: {last['timestamp'][:19]}Z")
    else:
        print("\n(직전 기록 없음 — 이번이 baseline)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--save", action="store_true", help="history 에 기록 (게이트 통과 시)")
    ap.add_argument("--json", action="store_true", help="JSON 만 출력")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else \
        script_dir.parents[3]  # .claude/skills/docs-audit/scripts → repo root
    history = script_dir / "score-history.jsonl"

    result = measure(root)
    last = load_last(history)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result, last)

    if args.save:
        with history.open("a", encoding="utf-8") as fh:
            # 본문은 빼고 카운트만 누적 (history 비대화 방지)
            slim = {k: result[k] for k in
                    ("timestamp", "files_scanned", "counts", "penalty", "score")}
            fh.write(json.dumps(slim, ensure_ascii=False) + "\n")
        print(f"\n→ history 기록: {history}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
