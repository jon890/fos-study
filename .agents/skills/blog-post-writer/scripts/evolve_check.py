#!/usr/bin/env python3
"""
evolve_check.py — 누적 채점 로그에서 SKILL.md 강화 신호를 뽑는다.

자동 트리거 루프의 마지막 조각.
hook(autoscore) 이 글 저장마다 violations.jsonl 에 축별 위반을 누적하면,
이 도구가 그 로그를 집계해 "어떤 위반이 반복되는가 → 어떤 규칙을 강화할까" 를 알린다.

실제 SKILL.md 수정은 자동으로 하지 않는다 — 신호만 내고 사람이 결정한다(안전).
SkillOpt 의 거부 편집 버퍼·검증 게이트 정신: 반복되는 위반만 규칙으로 승격한다.

사용:
  python3 evolve_check.py            # 누적 집계 + 강화 권장 축
  python3 evolve_check.py --threshold 5
"""
import argparse
import json
from collections import Counter
from pathlib import Path

# 축 → SKILL.md / markdown-pitfalls 에서 강화할 규칙 포인터
AXIS_RULE = {
    "bold_quote": "L. bold 안 따옴표 — `**\"...\"**` → 따옴표 제거",
    "bold_paren": "Bold+괄호 — `**텍스트(영문)**` → `**텍스트**(영문)`",
    "heading_number": "K. heading 숫자 prefix 금지 (fos-blog 자동번호 이중)",
    "ascii_box": "M. ASCII 박스 → mermaid 전환",
    "tilde": "G. `~` 취소선 함정 — 범위 표기 escape",
    "section_sign": "H. `§` 특수문자 → 평문 치환",
    "italic_paren": "10-C. 이탤릭+괄호 → bold+괄호 분리",
    "number_crossref": "K. 본문 숫자 cross-ref → 문맥 참조로",
}

LOG = Path(__file__).resolve().parent.parent / ".skill-loop" / "violations.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=3,
                    help="이 횟수 이상 누적된 축을 강화 후보로 (기본 3)")
    args = ap.parse_args()

    if not LOG.exists():
        print("누적 로그 없음 — 아직 자동 채점 기록이 없다.")
        return 0

    records = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not records:
        print("누적 로그 비어 있음.")
        return 0

    axis_total = Counter()
    axis_files = {}
    for r in records:
        for axis, n in r.get("counts", {}).items():
            if n:
                axis_total[axis] += n
                axis_files.setdefault(axis, set()).add(r["file"])

    print(f"# evolve_check — 누적 채점 기록 {len(records)}건\n")
    if not axis_total:
        print("위반 누적 없음 — 글들이 정적 문체 게이트를 잘 통과하고 있다. 강화 불필요.")
        return 0

    print(f"{'축':<18}{'누적위반':>8}{'발생글수':>8}")
    print("-" * 34)
    for axis, total in axis_total.most_common():
        print(f"{axis:<18}{total:>8}{len(axis_files[axis]):>8}")

    print()
    hot = [a for a, t in axis_total.items() if t >= args.threshold]
    if hot:
        print(f"## 강화 권장 (누적 {args.threshold}회 이상)\n")
        for a in sorted(hot, key=lambda x: -axis_total[x]):
            print(f"- **{a}** ({axis_total[a]}회) → {AXIS_RULE.get(a, '규칙 검토')}")
            print(f"  발생: {', '.join(sorted(axis_files[a])[:5])}")
        print("\n이 축들은 반복 위반이라 SKILL.md / markdown-pitfalls 의 해당 규칙을")
        print("더 눈에 띄게(예시 추가·자가점검 상단 배치) 강화할 후보다. 적용은 사람이 결정한다.")
    else:
        print(f"누적 {args.threshold}회 넘는 축 없음 — 아직 규칙 강화 시점 아님.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
