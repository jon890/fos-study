#!/usr/bin/env python3
"""승인된 시리즈 매핑을 .md frontmatter 에 적용한다.

입력 JSON(파일 또는 stdin):
    [{"path": "java/spring-batch/0.1-introduce.md", "series": "죽음의 스프링 배치", "seriesOrder": 1}, ...]

안전 가드:
- 기존 frontmatter 가 있으면 series/seriesOrder 키만 추가·갱신하고 나머지 키는 보존한다.
- 본문(첫 H1 등)은 건드리지 않는다.
- frontmatter 가 없던 글은 본문 맨 앞에 새 블록을 만들고, 블록과 본문 사이에 빈 줄 1개를 둔다.

YAML 전체를 파싱하지 않고 라인 단위로만 손대는 이유:
저장소 글의 들여쓰기·따옴표·리스트 값을 PyYAML round-trip 으로 바꾸면
의도치 않은 재포매팅이 생긴다. series/seriesOrder 두 줄만 정확히 다루는 게 안전하다.

사용법:
    python3 apply_series.py mapping.json            # 적용
    python3 apply_series.py --dry-run mapping.json  # 변경 미리보기(diff)
    cat mapping.json | python3 apply_series.py -     # stdin
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

# top-level(들여쓰기 없는) series/seriesOrder 키만 매치한다.
# 들여쓴 `  series:` 는 다른 키의 하위 값일 수 있어 건드리지 않는다.
TOP_KEY_RE = re.compile(r"^(series|seriesOrder)\s*:")


def split_frontmatter(text):
    """(frontmatter 줄 리스트[줄바꿈 포함], 본문) 반환. 없으면 (None, text).

    닫는 `---` 는 첫 단독 `---` 줄로 본다. 본문 자체가 `---` 수평선으로
    시작하는 글은 여는 가드(`text.startswith('---\\n')`)에서 frontmatter 가 아니라고 걸러진다.
    """
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return None, text
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return lines[1:i], "".join(lines[i + 1:])
    return None, text  # 닫는 --- 없음 -> frontmatter 아님


def strip_series_keys(fm_lines):
    """기존 series/seriesOrder 키와 그 multiline 연속 값(들여쓴 줄)을 함께 제거한다.

    `series: |` 블록 스칼라나 `series:\\n  - a` 리스트처럼 값이 여러 줄이면
    키 줄만 지울 때 들여쓴 줄이 고아로 남아 YAML 이 깨진다. 들여쓴 연속 줄도 같이 뺀다.
    """
    out, skipping = [], False
    for l in fm_lines:
        if TOP_KEY_RE.match(l):
            skipping = True
            continue
        if skipping:
            if l[:1] in (" ", "\t"):  # 들여쓴 연속 값 -> 계속 제거
                continue
            skipping = False
        out.append(l)
    return out


def yaml_scalar(v):
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(v)


def build(text, series, order):
    nl = "\r\n" if "\r\n" in text else "\n"  # 원본 줄바꿈에 맞춰 새 줄을 넣는다
    fm_lines, body = split_frontmatter(text)
    created = fm_lines is None
    if created:
        fm_lines, body = [], text

    kept = strip_series_keys(fm_lines)
    kept.append(f"series: {yaml_scalar(series)}{nl}")
    kept.append(f"seriesOrder: {order}{nl}")

    if created:
        # 새 frontmatter 와 본문 사이에 빈 줄 1개 보장
        body = body.lstrip("\r\n")
        sep = nl
    else:
        sep = ""
    return f"---{nl}" + "".join(kept) + f"---{nl}" + sep + body


def validate(mapping):
    """매핑 전체를 먼저 검증해 부분 적용(중간 KeyError 후 일부만 쓰임)을 막는다."""
    errors = []
    for i, item in enumerate(mapping):
        for k in ("path", "series", "seriesOrder"):
            if k not in item:
                errors.append(f"item {i}: '{k}' 키 누락")
        order = item.get("seriesOrder")
        if order is not None and (isinstance(order, bool) or not isinstance(order, int) or order < 0):
            errors.append(f"item {i}: seriesOrder 는 0 이상 정수여야 함 (got {order!r})")
        series = item.get("series")
        if isinstance(series, str) and "\n" in series:
            errors.append(f"item {i}: series 명에 줄바꿈을 넣을 수 없음")
        path = item.get("path")
        if path is not None and not Path(path).is_file():
            errors.append(f"item {i}: 파일 없음 -> {path}")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapping", help="매핑 JSON 파일 경로 또는 '-'(stdin)")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 diff 만 출력")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.mapping == "-" else Path(args.mapping).read_text(encoding="utf-8")
    mapping = json.loads(raw)

    errors = validate(mapping)
    if errors:
        print("매핑 검증 실패 (아무것도 쓰지 않음):", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)

    changed = 0
    for item in mapping:
        p = Path(item["path"])
        before = p.read_text(encoding="utf-8")
        after = build(before, item["series"], item["seriesOrder"])
        if before == after:
            print(f"[skip] {p} (변경 없음)")
            continue
        changed += 1
        if args.dry_run:
            diff = difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=str(p), tofile=str(p) + " (after)",
            )
            sys.stdout.writelines(diff)
            print()
        else:
            p.write_text(after, encoding="utf-8")
            print(f"[write] {p}  series={item['series']!r} order={item['seriesOrder']}")

    print(f"\n{'(dry-run) ' if args.dry_run else ''}변경 대상 {changed}건")


if __name__ == "__main__":
    main()
