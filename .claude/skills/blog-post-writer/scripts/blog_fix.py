#!/usr/bin/env python3
"""정적 위반 안전 자동교정 — bold_quote / heading_number, 코드펜스 보호.

blog_score 의 markdown-pitfalls 위반 중 *기계적으로 안전하게 되돌릴 수 있는* 두 축만
일괄 교정한다. docs-audit 의 정적 교정과 같은 계열이며, blog_score 의 짝이다.

코드펜스 인식은 blog_score 와 **동일한 정규식 쌍 매칭**(```...```)을 쓴다.
단순 `lstrip().startswith("```")` 토글은 리스트 안 들여쓴 펜스(`  - ```md`)의
여는 펜스를 놓쳐(앞에 `- ` 가 붙어서) 이후 줄을 통째로 코드펜스로 오판한다.
실제로 agents-md 가 이 버그로 (a) 일괄 교정에서 누락됐다 — 그래서 채점기와
같은 인식으로 맞춰 둔다.

교정 대상은 heading_number 와 bold_quote 두 축뿐이다(ascii_box·bold_paren·tilde 등은
손대지 않고 그대로 둔다). 그래서 안전 조건은 하나다:
  - number_crossref 위반 없음 (있으면 heading 번호를 떼는 순간 본문 "섹션 N" 참조가 깨짐)
다른 축(ascii_box 등)이 동반된 글도 heading/bold 부분 교정은 안전하므로 처리한다.

사용:
  python3 blog_fix.py            # 현재 경로 이하 전체
  python3 blog_fix.py <dir>      # 특정 폴더만
"""
import glob
import os
import re
import sys
from importlib import util

_here = os.path.dirname(os.path.abspath(__file__))
spec = util.spec_from_file_location("bs", os.path.join(_here, "blog_score.py"))
bs = util.module_from_spec(spec)
spec.loader.exec_module(bs)

AUTO = {"bold_quote", "heading_number"}
CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
EXCLUDE = (".git/", ".claude/", ".agents/", "node_modules/", "k8s-in-action/")  # 외부 책 노트는 챕터 번호 보존


def _fenced_line_indices(text):
    """코드펜스 안에 속한 0-based 줄 인덱스 집합 (blog_score 와 동일 인식)."""
    fenced = set()
    for m in CODE_FENCE.finditer(text):
        start = text.count("\n", 0, m.start())
        end = text.count("\n", 0, m.end())
        fenced.update(range(start, end + 1))
    return fenced


def fix(text):
    """코드펜스 밖 줄에서만 heading 번호·bold 따옴표를 교정."""
    fenced = _fenced_line_indices(text)
    out = []
    for i, ln in enumerate(text.split("\n")):
        if i not in fenced:
            ln = re.sub(r"^(#{2,6})\s+\d+(\.\d+)*\.?\s+", r"\1 ", ln)  # ## 1. / ### 2.1 / 2.1.3 → ##
            ln = re.sub(r"^(#{2,6})\s+\d+-\d+\.\s+", r"\1 ", ln)        # ### 3-1. → ###
            ln = re.sub(r'\*\*"([^"]*)"\*\*', r"**\1**", ln)           # **"x"** → **x**
        out.append(ln)
    return "\n".join(out)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    changed = 0
    for f in glob.glob(os.path.join(root, "**/*.md"), recursive=True):
        if any(x in f for x in EXCLUDE) or os.path.basename(f) == "README.md":
            continue
        t = open(f, encoding="utf-8", errors="ignore").read()
        n, d = bs.score_text(t)
        if n == 0:
            continue
        cnt = {k: len(v) for k, v in d.items() if v}
        # fix() 는 heading_number 와 bold_quote 만 건드린다(ascii_box·bold_paren·tilde 등은
        # 손대지 않는다). 그래서 number_crossref 만 없으면 다른 축이 동반돼 있어도
        # heading/bold 부분 교정은 안전하다. number_crossref 가 있으면 heading 번호를
        # 떼는 순간 본문 "섹션 N" 참조가 깨지므로 그 글만 skip 한다.
        if cnt.get("number_crossref", 0) > 0:
            continue
        new = fix(t)
        if new != t:
            open(f, "w", encoding="utf-8").write(new)
            changed += 1
            print(f"fixed {f}  {cnt}")
    print(f"\n총 {changed}개 교정")
    return 0


if __name__ == "__main__":
    sys.exit(main())
