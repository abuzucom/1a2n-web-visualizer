#!/usr/bin/env python3
"""Sync AGENTS.md to tool-specific copies, and watch the shared gate files.

--check verifies the AGENTS.md copies without writing.
--check-shared verifies the files that must stay byte-identical with the
other repositories adopting these gates, against SHARED_MANIFEST.
--write-shared rewrites that manifest from what is on disk.

sync.py covers the AGENTS.md family by copying. It cannot copy the gate
files, which live in repositories it cannot see, so it compares hashes
against a manifest committed in each of them instead. A file that differs
is either a fix one repository has and the other does not, or drift that
belongs in the drift record. Both need somebody to look.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

SOURCE = "AGENTS.md"
SHARED_MANIFEST = "shared-files.json"
# Files that must be byte-identical wherever these gates are installed. A
# decision reached by one gate and not the other is the failure the whole
# design exists to prevent, so the files carrying decisions are listed here
# and their hashes are committed in every repository holding them.
SHARED_FILES = [
    "hooks/_gate_core.py",
    "hooks/block_destructive_bash.py",
    "hooks/block_destructive_powershell.py",
    "hooks/require_consent.py",
    "tests/gate_corpus.py",
    "tests/test_block_destructive_bash.py",
    "tests/test_block_destructive_powershell.py",
]
COPIES = [
    "CLAUDE.md",
    "GEMINI.md",
    "CONVENTIONS.md",
    ".cursorrules",
    ".clinerules",
    ".windsurfrules",
    ".copilot-instructions",
    ".github/copilot-instructions.md",
]


def files_match(source: Path, target: Path) -> bool:
    """Compare file contents, normalizing line endings."""
    try:
        if not target.is_file():
            return False
        return (
            source.read_text(encoding="utf-8").replace("\r\n", "\n")
            == target.read_text(encoding="utf-8").replace("\r\n", "\n")
        )
    except (OSError, UnicodeDecodeError):
        return False


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
        if not files_match(source, root / name)
    ]

    if check_only:
        if stale:
            print(f"out of sync with {SOURCE}: {', '.join(stale)}", file=sys.stderr)
            print("run: make sync (or python scripts/sync.py)", file=sys.stderr)
            return 1
        print("all copies in sync")
        return 0

    for name in stale:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        print(f"synced {name}")
    if not stale:
        print("all copies already in sync")
    return 0


def content_digest(path: Path) -> str:
    """Return the file's SHA-256 with line endings normalized.

    Normalizing is what keeps a Windows checkout from reporting every
    shared file as drift. SHA-256 rather than a faster hash because this
    is an integrity comparison, not a cache key (Rule 7).
    """
    body = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_manifest(root: Path) -> dict:
    """Return the shared-file manifest, or an empty one when absent."""
    manifest = root / SHARED_MANIFEST
    if not manifest.is_file():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as error:
        print(f"error: {SHARED_MANIFEST} is not valid JSON ({error})",
              file=sys.stderr)
        return {}


def shared_problems(root: Path, recorded: dict) -> list:
    """Return one line per shared file that does not match the manifest."""
    problems = []
    for name in SHARED_FILES:
        path = root / name
        if not path.is_file():
            problems.append(f"{name}: listed as shared but not present here")
            continue
        if name not in recorded:
            problems.append(f"{name}: shared but absent from {SHARED_MANIFEST}")
            continue
        try:
            actual = content_digest(path)
        except (OSError, UnicodeDecodeError) as error:
            problems.append(f"{name}: cannot be read ({error})")
            continue
        if actual != recorded[name]:
            problems.append(f"{name}: differs from the recorded copy")
    return problems


def check_shared(root: Path) -> int:
    """Report shared files that no longer match the committed manifest."""
    manifest = read_manifest(root)
    if not manifest:
        print(f"error: {SHARED_MANIFEST} is missing or unreadable",
              file=sys.stderr)
        return 1
    problems = shared_problems(root, manifest.get("shared", {}))
    if not problems:
        print(f"all {len(SHARED_FILES)} shared files match {SHARED_MANIFEST}")
        return 0
    for line in problems:
        print(line, file=sys.stderr)
    print("Mirror the change into every repository holding these files, then "
          "run: python scripts/sync.py --write-shared in each. If the "
          "difference is deliberate, record it in the drift file and move the "
          "file out of SHARED_FILES.", file=sys.stderr)
    return 1


def write_shared(root: Path) -> int:
    """Rewrite the manifest from the shared files on disk."""
    recorded = {}
    for name in SHARED_FILES:
        path = root / name
        if not path.is_file():
            print(f"error: {name} is listed as shared but not present here",
                  file=sys.stderr)
            return 1
        recorded[name] = content_digest(path)
    body = {
        "note": ("SHA-256 of every file that must stay byte-identical across "
                 "the repositories adopting these gates. Line endings are "
                 "normalized before hashing. Regenerate with "
                 "scripts/sync.py --write-shared and commit the result in "
                 "every one of them."),
        "shared": recorded,
    }
    (root / SHARED_MANIFEST).write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"recorded {len(recorded)} shared files in {SHARED_MANIFEST}")
    return 0


def main(argv: list) -> int:
    """Dispatch on the mode flag and return a process exit code."""
    root = Path(__file__).resolve().parent.parent
    if "--check-shared" in argv:
        return check_shared(root)
    if "--write-shared" in argv:
        return write_shared(root)
    return sync_copies(check_only="--check" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
