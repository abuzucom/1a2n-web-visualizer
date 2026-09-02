#!/usr/bin/env python3
"""Enforce the AGENTS.md dash and ASCII style rules on the source document.

Checks the source (AGENTS.md), not the generated copies, since sync.py keeps
the copies identical. Reports every violation and exits non-zero if any are
found, so CI can block a merge that reintroduces an em-dash substitute or a
stray non-ASCII character in prose.
"""
import re
import sys
from pathlib import Path

SOURCE = "AGENTS.md"
DASH_SUBSTITUTE = re.compile(r" -{1,3} ")
EM_EN_DASH = re.compile(r"[–—]")
MAX_ASCII_CODEPOINT = 127
# A Markdown table delimiter row carries only pipes, colons, dashes and
# spaces. It is table syntax, and rewriting it to satisfy the dash rule
# changes a document to satisfy a linter rather than a reader.
TABLE_SEPARATOR = re.compile(r"^\s*\|[\s:|-]*-[\s:|-]*\|\s*$")
# A list marker opens its line. It is syntax, not a dash between clauses.
LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+\.)\s")


def strip_code(line: str, in_span: bool = False) -> tuple:
    """Return the line's prose and whether a code span is still open.

    A span can open on one line and close on the next. Pairing backticks
    within a line pairs the wrong ones and leaks the text between them,
    which is how a preset name carrying a spaced hyphen reached the dash
    check.
    """
    prose = []
    for character in line:
        if character == "`":
            in_span = not in_span
        elif not in_span:
            prose.append(character)
    return "".join(prose), in_span


def strip_marker(line: str) -> str:
    """Remove a leading list marker, which is syntax rather than prose."""
    return LIST_MARKER.sub("", line, count=1)


def find_violations(text: str) -> list[str]:
    """Return one message per style violation in the prose of `text`."""
    violations = []
    in_fence = False
    in_span = False
    for number, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            in_span = False
            continue
        if in_fence:
            continue
        prose, in_span = strip_code(raw, in_span)
        if EM_EN_DASH.search(prose):
            violations.append(f"{SOURCE}:{number}: em/en dash character")
        if (not TABLE_SEPARATOR.match(raw)
                and DASH_SUBSTITUTE.search(strip_marker(prose))):
            violations.append(
                f"{SOURCE}:{number}: spaced hyphen used as an em-dash substitute"
            )
        if any(ord(char) > MAX_ASCII_CODEPOINT for char in prose):
            violations.append(f"{SOURCE}:{number}: non-ASCII character in prose")
    return violations


def lint() -> int:
    """Lint the source document. Return 0 when clean, 1 on any violation."""
    root = Path(__file__).resolve().parent.parent
    source = root / SOURCE
    if not source.is_file():
        print(f"error: {SOURCE} not found at {root}", file=sys.stderr)
        return 1

    violations = find_violations(source.read_text(encoding="utf-8"))
    if violations:
        for message in violations:
            print(message, file=sys.stderr)
        print(
            "fix: rewrite as separate sentences or use a comma/colon/semicolon",
            file=sys.stderr,
        )
        return 1
    print("style clean")
    return 0


if __name__ == "__main__":
    sys.exit(lint())
