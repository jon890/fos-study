#!/usr/bin/env python3
"""fos-study의 깨진 링크, 고아 문서와 README 누락을 검사한다."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


EXCLUDE_DIR_PARTS = {
    ".git",
    ".claude",
    ".codex",
    ".agents",
    "node_modules",
    "k8s-in-action",
}
ENTRYPOINTS = {"README.md", "INDEX.md", "CLAUDE.md", "AGENTS.md"}
CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
LINK = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIR_PARTS for part in path.parts)


def git_visible_markdown(root: Path) -> list[Path] | None:
    """git 이 무시하지 않는 .md 를 낸다. git 저장소가 아니면 None 이다.

    .orch, .omc 같은 작업 폴더는 .gitignore 나 .git/info/exclude 로 빠져 있어
    폴더 이름을 하나씩 등록하지 않아도 공개 문서만 남는다.
    """
    try:
        output = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", "--", "*.md"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = {root / name for name in output.decode("utf-8").split("\0") if name}
    return sorted(path for path in paths if path.is_file())


def markdown_files(root: Path) -> list[Path]:
    candidates = git_visible_markdown(root)
    if candidates is None:
        candidates = root.rglob("*.md")
    return [
        path for path in candidates
        if not is_excluded(path.relative_to(root))
    ]


def visible_links(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    masked = INLINE_CODE.sub(" ", CODE_FENCE.sub(" ", text))
    for line_number, line in enumerate(masked.splitlines(), 1):
        for match in LINK.finditer(line):
            yield line_number, match.group(1).strip().split()[0]


def resolve_link(source: Path, target: str, root: Path) -> Path | None:
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    path_part = unquote(target.split("#")[0]).strip("<>")
    if not path_part.endswith((".md", ".mdx")):
        return None
    if path_part.startswith("/"):
        return (root / path_part.lstrip("/")).resolve()
    return (source.parent / path_part).resolve()


def check_broken_links(files: list[Path], root: Path) -> list[dict]:
    findings = []
    file_set = {path.resolve() for path in files}
    for source in files:
        for line_number, target in visible_links(source):
            resolved = resolve_link(source, target, root)
            if resolved is not None and resolved not in file_set and not resolved.exists():
                findings.append({
                    "file": str(source.relative_to(root)),
                    "line": line_number,
                    "target": target,
                })
    return findings


def check_orphans(files: list[Path], root: Path) -> list[dict]:
    linked = set()
    for source in files:
        for _, target in visible_links(source):
            resolved = resolve_link(source, target, root)
            if resolved is not None:
                linked.add(resolved)

    return [
        {"file": str(path.relative_to(root))}
        for path in files
        if path.name not in ENTRYPOINTS and path.resolve() not in linked
    ]


def check_readme_integrity(files: list[Path], root: Path) -> list[dict]:
    findings = []
    by_directory: dict[Path, list[Path]] = {}
    for path in files:
        by_directory.setdefault(path.parent, []).append(path)

    for directory, siblings in by_directory.items():
        readme = directory / "README.md"
        if not readme.exists():
            continue
        linked = {
            resolved
            for _, target in visible_links(readme)
            if (resolved := resolve_link(readme, target, root)) is not None
        }
        for path in siblings:
            if path.name == "README.md":
                continue
            if path.resolve() not in linked:
                findings.append({
                    "readme": str(readme.relative_to(root)),
                    "missing": path.name,
                })
    return findings


def measure(root: Path) -> dict:
    files = markdown_files(root)
    details = {
        "broken_link": check_broken_links(files, root),
        "orphan_doc": check_orphans(files, root),
        "readme_missing": check_readme_integrity(files, root),
    }
    counts = {name: len(items) for name, items in details.items()}
    return {
        "files_scanned": len(files),
        "ok": all(count == 0 for count in counts.values()),
        "counts": counts,
        "details": details,
    }


def print_report(result: dict) -> None:
    print(f"검사 문서: {result['files_scanned']}개")
    for name, count in result["counts"].items():
        print(f"{name}: {count}")
        for finding in result["details"][name]:
            print(f"  - {finding}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else script_dir.parents[3]
    result = measure(root)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
