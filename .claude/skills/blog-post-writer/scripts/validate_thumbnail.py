#!/usr/bin/env python3
"""블로그 글의 thumbnail 앞표지와 로컬 이미지 파일을 검증한다."""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
THUMBNAIL_RE = re.compile(r"^thumbnail:\s*['\"]?(?P<path>[^'\"\n]+)['\"]?\s*$", re.MULTILINE)


def image_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            length = struct.unpack(">H", data[offset:offset + 2])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return width, height
            offset += length
    return None


def validate(markdown_path: Path) -> list[str]:
    errors: list[str] = []
    text = markdown_path.read_text(encoding="utf-8")
    front_matter = FRONT_MATTER_RE.match(text)
    if not front_matter:
        return ["thumbnail 앞표지가 없습니다"]

    thumbnail = THUMBNAIL_RE.search(front_matter.group("body"))
    if not thumbnail:
        return ["thumbnail 값이 없습니다"]

    relative = thumbnail.group("path").strip()
    if not relative.startswith("./") or "?" in relative or "#" in relative:
        errors.append("thumbnail은 query와 fragment가 없는 ./ 상대 경로여야 합니다")

    candidate = (markdown_path.parent / relative).resolve()
    repository_root = Path.cwd().resolve()
    try:
        candidate.relative_to(repository_root)
    except ValueError:
        errors.append("thumbnail 경로가 저장소 루트를 벗어납니다")

    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        errors.append("지원하지 않는 이미지 확장자입니다")
    if not candidate.is_file():
        errors.append(f"이미지 파일이 없습니다: {candidate}")
        return errors

    dimensions = image_size(candidate)
    if dimensions is None:
        errors.append("PNG 또는 JPEG 이미지 크기를 확인할 수 없습니다")
    else:
        width, height = dimensions
        ratio = width / height
        if not 1.7 <= ratio <= 1.9:
            errors.append(f"16:9 권장 범위를 벗어났습니다: {width}x{height}")

    if candidate.stat().st_size > 2 * 1024 * 1024:
        errors.append("이미지 크기가 2 MiB를 넘습니다")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_thumbnail.py <post.md>", file=sys.stderr)
        return 2

    markdown_path = Path(sys.argv[1])
    errors = validate(markdown_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"OK: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
