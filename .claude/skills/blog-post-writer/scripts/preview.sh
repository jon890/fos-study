#!/usr/bin/env bash
# 글 하나를 fos-blog 형식 HTML 로 만들고, 사용자가 보는 Orca 탭에 띄운 뒤 Mermaid 렌더링을 확인한다.
#
# 사용법 (글을 쓴 워크트리 루트에서):
#   preview.sh <글.md> [출력.html]
#
# 출력 HTML 기본값: /private/tmp/fos-study-preview/<글 파일명>.html
# 같은 HTML 로 다시 실행하면 새 탭을 만들지 않고 기존 탭을 갱신한다.
#
# 왜 이렇게 하는가:
#   - 탭을 여는 일은 content-preview 의 show-preview.sh 가 맡는다. 설정 파일의 previewDriver 로
#     백엔드를 고르고, 탭이 사용자가 보는 워크트리에 열렸는지 대조한다. 그 판단을 여기서 다시 만들지 않는다.
#   - show-preview.sh 는 플러그인 설치 캐시에 있고 경로에 버전이 들어간다. 경로를 문서에 적으면
#     플러그인을 갱신할 때마다 틀리므로 여기서 찾는다. SHOW_PREVIEW 로 직접 줄 수도 있다.
#   - Playwright 는 file:// 주소를 막고, 연 화면이 Orca 에 나타나지 않는다. 같은 탭을 browser-driver 로 확인한다.
#
# 종료 코드: 0 통과, 1 Mermaid 렌더링 실패, 2 사용법이나 준비 오류

set -euo pipefail

POST="${1:?사용법: preview.sh <글.md> [출력.html]}"
[ -f "$POST" ] || { echo "글이 없다: $POST" >&2; exit 2; }
HTML="${2:-/private/tmp/fos-study-preview/$(basename "$POST" .md).html}"

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$(dirname "$HTML")"
node "$SKILL_DIR/scripts/render_preview.mjs" "$POST" "$HTML"
echo "HTML: $HTML"

SHOW="${SHOW_PREVIEW:-}"
if [ -z "$SHOW" ]; then
  SHOW="$(ls "$HOME"/.claude/plugins/cache/*/nhn-dev/*/skills/content-preview/scripts/show-preview.sh 2>/dev/null | sort -V | tail -1 || true)"
fi
[ -n "$SHOW" ] && [ -f "$SHOW" ] || { echo "show-preview.sh 를 찾지 못했다. SHOW_PREVIEW 로 경로를 준다." >&2; exit 2; }
bash "$SHOW" "$HTML"

B="${BROWSER_DRIVER_PATH:-$HOME/.claude/scripts/browser-driver}"
[ -x "$B" ] || { echo "browser-driver 가 없다: $B" >&2; exit 2; }
[ -f "$HTML.tabid" ] || { echo "탭 id 가 없다. 기본 브라우저로 열렸으면 Mermaid 는 화면에서 직접 본다." >&2; exit 2; }
PAGE="$(cat "$HTML.tabid")"

# show-preview.sh 가 탭을 연 백엔드와 같은 백엔드로 불러야 같은 탭을 찾는다.
BACKEND="${PREVIEW_BROWSER_DRIVER:-}"
if [ -z "$BACKEND" ]; then
  CFG="$("$B" config-path 2>/dev/null || true)"
  [ -f "$CFG" ] && BACKEND="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("previewDriver") or "")' "$CFG" 2>/dev/null || true)"
fi
drv() { if [ -n "$BACKEND" ]; then BROWSER_DRIVER="$BACKEND" "$B" "$@"; else "$B" "$@"; fi; }

COUNT="$(drv js "$PAGE" "document.querySelectorAll('.mermaid').length")"
if [ "$COUNT" = "0" ]; then
  echo "Mermaid: 없음"
  exit 0
fi

drv waitjs "$PAGE" "document.querySelectorAll('.mermaid svg').length === document.querySelectorAll('.mermaid').length" 10000 \
  || { echo "Mermaid: $COUNT 개 중 일부가 10초 안에 SVG 로 그려지지 않았다." >&2; exit 1; }
RESULT="$(drv js "$PAGE" "JSON.stringify([...document.querySelectorAll('.mermaid')].map(m => ({svg: !!m.querySelector('svg'), syntaxError: /Syntax error/.test(m.textContent)})))")"
echo "Mermaid: $RESULT"

SHOT="${HTML%.html}-mermaid.png"
drv js "$PAGE" "document.querySelector('.mermaid').scrollIntoView({block: 'center'}), true" >/dev/null
drv shot "$PAGE" "$SHOT" >/dev/null && echo "스크린숏: $SHOT"

case "$RESULT" in
  *'"svg":false'*|*'"syntaxError":true'*) exit 1 ;;
esac
