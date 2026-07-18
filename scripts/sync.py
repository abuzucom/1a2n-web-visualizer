#!/usr/bin/env python3
"""Sync AGENTS.md to tool-specific copies. --check verifies without writing."""
import filecmp
import shutil
import sys
from pathlib import Path

SOURCE = "AGENTS.md"
COPIES = [
    "CLAUDE.md",
    "GEMINI.md",
    "CONVENTIONS.md",
    ".cursorrules",
    ".clinerules",
    ".windsurfrules",
]


def sync_copies(check_only: bool) -> int:
    """Copy SOURCE over each target, or with --check report stale targets.

    Returns a process exit code: 0 on success, 1 if a check fails.
    """
    root = Path(__file__).resolve().parent.parent
    source = root / SOURCE
    if not source.is_file():
        print(f"error: {SOURCE} not found at {root}", file=sys.stderr)
        return 1

    stale = [
        name
        for name in COPIES
        if not (root / name).is_file()
        or not filecmp.cmp(source, root / name, shallow=False)
    ]

    if check_only:
        if stale:
            print(f"out of sync with {SOURCE}: {', '.join(stale)}", file=sys.stderr)
            print("run: python scripts/sync.py", file=sys.stderr)
            return 1
        print("all copies in sync")
        return 0

    for name in stale:
        shutil.copyfile(source, root / name)
        print(f"synced {name}")
    if not stale:
        print("all copies already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(sync_copies(check_only="--check" in sys.argv[1:]))
