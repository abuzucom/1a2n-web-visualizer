"""Shared file and hash helpers for the preset tools.

The tools load this module by file path, the same way validate_catalogs.py
loads curate_catalogs.py. Hyphenated tool filenames and test loaders then
need no change to sys.path.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    """Replace path with text through a same-directory temporary file.

    A reader or a crash sees the old content or the new content, never a
    partial file. newline="" keeps LF line endings on every platform. A
    failed write removes the temporary file and leaves path unchanged.
    """
    temporary = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, newline="",
    )
    try:
        with temporary:
            temporary.write(text)
        os.replace(temporary.name, path)
    finally:
        Path(temporary.name).unlink(missing_ok=True)


def canonicalize(value: Any) -> Any:
    """Return a normalized copy of preset data for exact comparison.

    Line endings collapse to LF. Every value equal to zero becomes the integer
    0. That rule also maps False to 0. experimental-presets.json records
    digests built on these exact rules, so a change would invalidate them.
    """
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if value == 0:
        return 0
    return value


def preset_hash(preset: dict[str, Any]) -> str:
    """Return the SHA-256 digest of the canonicalized preset."""
    payload = json.dumps(
        canonicalize(preset), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
