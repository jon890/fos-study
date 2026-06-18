#!/usr/bin/env python3
"""fos-study 시리즈 후보 스캐너.

폴더별 .md 파일명의 선행 번호(`0.1`, `05`, `1_`, `2-` 등)를 파싱해
version sort 로 안정 정렬하고 seriesOrder 를 1,2,3... 정수로 제안한다.
README.md 는 시리즈 글에서 제외한다(시리즈명 추론에만 쓴다).

번호가 있는 글이 2편 이상이면 strong(바로 묶기 가능),
번호는 없지만 글이 3편 이상이면 medium(사람이 순서 부여 필요),
그 외는 weak 로 등급을 매긴다.

사용법:
    python3 scan_series.py <folder> [<folder> ...]   # 지정 폴더만
    python3 scan_series.py --root <repo-root>          # 하위 폴더 자동 탐지
    python3 scan_series.py --json ...                  # 기계 판독용 JSON

번호 파싱·정렬은 매 실행 반복되는 결정적 로직이라 스크립트로 분리했다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 파일명 선행 번호: 1 / 05 / 0.1 / 1_2 / 2.3.1 등. 구분자는 . 또는 _
NUM_RE = re.compile(r"^(\d+(?:[._]\d+)*)")


def parse_order_key(name):
    """파일명 선행 번호를 정수 튜플로. 없으면 None.

    '0.1-introduce.md' -> (0, 1), '05_foo.md' -> (5,), '1-bar.md' -> (1,).
    튜플 비교가 곧 version sort 라 소수점·언더스코어 체계가 섞여도 안정 정렬된다.
    """
    m = NUM_RE.match(name)
    if not m:
        return None
    parts = re.split(r"[._]", m.group(1))
    try:
        return tuple(int(p) for p in parts if p != "")
    except ValueError:
        return None


def first_h1(path):
    """본문 첫 H1(`# 제목`) 텍스트. frontmatter 가 있으면 건너뛴다."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    in_fm = False
    for i, line in enumerate(lines):
        s = line.strip()
        if i == 0 and s == "---":
            in_fm = True
            continue
        if in_fm:
            if s == "---":
                in_fm = False
            continue
        if s.startswith("# "):
            return s[2:].strip()
    return None


def has_frontmatter(path):
    try:
        with path.open(encoding="utf-8") as f:
            return f.readline().rstrip("\r\n") == "---"
    except OSError:
        return False


def scan_folder(folder):
    mds = sorted(p for p in folder.glob("*.md") if p.name.lower() != "readme.md")
    numbered, unnumbered = [], []
    for p in mds:
        key = parse_order_key(p.name)
        rec = {
            "file": p.name,
            "path": str(p),
            "h1": first_h1(p),
            "has_frontmatter": has_frontmatter(p),
        }
        if key is not None:
            rec["order_key"] = list(key)
            numbered.append(rec)
        else:
            unnumbered.append(rec)

    numbered.sort(key=lambda r: r["order_key"])
    for i, rec in enumerate(numbered, 1):
        rec["suggested_order"] = i
    for rec in unnumbered:
        rec["suggested_order"] = None  # 사람이 정해야 함

    # 시리즈명 추론: README H1 > 첫 번호글 H1 > 폴더명
    readme = folder / "README.md"
    series_name = first_h1(readme) if readme.exists() else None
    if not series_name and numbered:
        series_name = numbered[0]["h1"]
    if not series_name:
        series_name = folder.name

    if len(numbered) >= 2:
        strength = "strong"
    elif len(mds) >= 3:
        strength = "medium"
    else:
        strength = "weak"

    return {
        "folder": str(folder),
        "suggested_series": series_name,
        "numbered_count": len(numbered),
        "unnumbered_count": len(unnumbered),
        "strength": strength,
        "numbered": numbered,
        "unnumbered": unnumbered,
    }


def discover_folders(root):
    """하위 폴더 중 .md 가 2개 이상인 곳을 후보로. .git/.claude 등 제외."""
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_dir():
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        mds = [m for m in p.glob("*.md") if m.name.lower() != "readme.md"]
        if len(mds) >= 2:
            out.append(p)
    return out


def render_human(results):
    order = {"strong": 0, "medium": 1, "weak": 2}
    results = sorted(results, key=lambda r: (order[r["strength"]], r["folder"]))
    for r in results:
        print(f"\n=== [{r['strength']}] {r['folder']}")
        print(f"    시리즈명(제안): {r['suggested_series']}")
        print(f"    번호글 {r['numbered_count']}편 / 번호없음 {r['unnumbered_count']}편")
        for rec in r["numbered"]:
            fm = " (frontmatter 있음)" if rec["has_frontmatter"] else ""
            print(f"      {rec['suggested_order']:>2}. {rec['file']}  <- {rec['h1']}{fm}")
        for rec in r["unnumbered"]:
            fm = " (frontmatter 있음)" if rec["has_frontmatter"] else ""
            print(f"       ?. {rec['file']}  <- {rec['h1']}{fm}  [순서 미정]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*", help="스캔할 폴더(들)")
    ap.add_argument("--root", help="저장소 루트에서 후보 자동 탐지")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    targets = []
    if args.root:
        targets = discover_folders(Path(args.root))
    targets += [Path(f) for f in args.folders]
    if not targets:
        ap.error("폴더를 지정하거나 --root 를 주세요")

    results = [scan_folder(t) for t in targets if t.is_dir()]
    if args.json:
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        render_human(results)


if __name__ == "__main__":
    main()
