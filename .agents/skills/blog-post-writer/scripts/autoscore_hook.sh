#!/usr/bin/env bash
# 자동 트리거 — blog 글 저장(Write/Edit) 직후 blog_score 자동 채점.
# PostToolUse(Write|Edit) hook 으로 등록한다. 글 저장 순간 정적 문체 위반을 노출하고
# 누적 로그에 기록해, 같은 위반이 반복되면 SKILL.md 강화(evolve) 신호로 쓴다.
#
# 피드백 루프의 "자동 트리거" 부품 — 사람이 자가점검을 시작하지 않아도 루프가 돈다.
set -euo pipefail

ROOT=/Users/nhn/personal/fos-study
SCORER="$ROOT/.claude/skills/blog-post-writer/scripts/blog_score.py"
LOGDIR="$ROOT/.claude/skills/blog-post-writer/.skill-loop"

# hook 입력(JSON) 에서 file_path 추출
input=$(cat)
fp=$(printf '%s' "$input" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))
except Exception: print("")' 2>/dev/null || true)

# fos-study 의 블로그 글(.md) 만 대상 — .claude/ 와 README 는 제외
case "$fp" in
  "$ROOT"/*.md) ;;
  *) exit 0 ;;
esac
case "$fp" in
  "$ROOT"/.claude/*|*/README.md) exit 0 ;;
esac
[ -f "$fp" ] || exit 0

mkdir -p "$LOGDIR"
# 채점 + 축별 누적 기록 (--log). 위반이 있으면 스크립트가 한 줄 경고를 출력한다.
python3 "$SCORER" --log "$LOGDIR/violations.jsonl" "$fp" 2>/dev/null || true
exit 0
