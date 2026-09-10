#!/usr/bin/env python3
"""Verify the published index template against the files in this Skill tree.

``docs/paos-forge-packages.template.yaml`` records a ``sha256`` and ``size`` for
every Skill file so a maintainer can inspect or register the bundle without
unpacking it.  Nothing reads those entries at install time, so editing any Skill
file makes them stale silently.  Run this before publishing:

    python3 scripts/check_bundle_inventory.py --check   # exit 1 on drift
    python3 scripts/check_bundle_inventory.py --write   # rewrite the inventory

``--write`` regenerates only the Skill inventory block; the header comments and
the node entries keep their formatting.  Categories are re-derived from the file
mode, so run ``--write`` on the pack host: a Windows checkout has no executable
bit, and ``--write`` there keeps the categories already recorded instead.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "docs" / "paos-forge-packages.template.yaml"
# The template cannot hash itself, and the packager generates archive-manifest.json.
SKIPPED = {"docs/paos-forge-packages.template.yaml", "archive-manifest.json"}
# Windows checkouts do not carry the executable bit.
CHECK_CATEGORY = os.name != "nt"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filesystem_category(path: Path) -> str:
    return "executable" if path.stat().st_mode & 0o111 else "file"


def actual_files(root: Path) -> list[dict[str, object]]:
    found = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
            "category": filesystem_category(path),
        }
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in SKIPPED
    ]
    return sorted(found, key=lambda item: str(item["path"]))


def skill_bounds(lines: list[str]) -> tuple[int, int]:
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == "- kind: skill_bundle"),
        None,
    )
    if start is None:
        raise SystemExit(f"{TEMPLATE} has no skill_bundle entry")
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("- kind:")),
        len(lines),
    )
    return start, end


def recorded_entries(lines: list[str], start: int, end: int) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped.startswith("- path: "):
            current = stripped[len("- path: ") :].strip()
            entries[current] = {}
        elif current and ":" in stripped:
            key, _, value = stripped.partition(":")
            if key in {"sha256", "size", "category"}:
                entries[current][key] = value.strip()
    return entries


def render_block(expected: list[dict[str, object]], recorded: dict[str, dict[str, str]]) -> list[str]:
    lines = ["  inventory:"]
    for item in expected:
        path = str(item["path"])
        lines.append(f"  - path: {path}")
        lines.append(f"    sha256: {item['sha256']}")
        lines.append(f"    size: {item['size']}")
        # Keep a recorded category on hosts that cannot report the mode; otherwise
        # derive it from the file so a Linux pack host stays authoritative.
        category = item["category"] if CHECK_CATEGORY else recorded.get(path, {}).get(
            "category", item["category"]
        )
        lines.append(f"    category: {category}")
    return lines


def rewrite(lines: list[str], start: int, end: int, block: list[str]) -> list[str]:
    output = list(lines[:start])
    index = start
    while index < end:
        line = lines[index]
        if line.strip() == "inventory:":
            output.extend(block)
            index += 1
            while index < end:
                current = lines[index]
                if current.startswith("  - path:"):
                    index += 1
                    while index < end and lines[index].startswith("    "):
                        index += 1
                    continue
                break
            continue
        output.append(line)
        index += 1
    return output + list(lines[end:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift (default)")
    parser.add_argument("--write", action="store_true", help="rewrite the Skill inventory")
    args = parser.parse_args()

    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    start, end = skill_bounds(lines)
    recorded = recorded_entries(lines, start, end)
    expected = actual_files(SKILL_ROOT)
    by_path = {str(item["path"]): item for item in expected}

    problems: list[str] = []
    for item in expected:
        path = str(item["path"])
        entry = recorded.get(path)
        if entry is None:
            problems.append(f"missing from inventory: {path}")
            continue
        if entry.get("sha256") != item["sha256"] or entry.get("size") != str(item["size"]):
            problems.append(f"stale hash/size: {path}")
        elif CHECK_CATEGORY and entry.get("category") != item["category"]:
            problems.append(f"stale category: {path}")
    for path in sorted(set(recorded) - set(by_path)):
        problems.append(f"inventory lists a missing file: {path}")

    if not problems:
        print(f"ok: {len(expected)} Skill files match {TEMPLATE.name}")
        return 0
    for problem in problems:
        print(problem)
    if not args.write:
        print("run with --write to regenerate the Skill inventory")
        return 1
    block = render_block(expected, recorded)
    TEMPLATE.write_text("\n".join(rewrite(lines, start, end, block)) + "\n", encoding="utf-8", newline="")
    print(f"rewrote the Skill inventory in {TEMPLATE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())