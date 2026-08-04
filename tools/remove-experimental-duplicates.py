#!/usr/bin/env python3
"""Remove explicitly approved EXP presets that have mainline counterparts."""

import argparse
import csv
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
INDEX_PATH = OUT_DIR / "index.js"
CSV_PATH = ROOT / "preset-inventory.csv"
REMOVED_CSV_PATH = ROOT / "removed-presets.csv"
MANIFEST_PATH = ROOT / "experimental-presets.json"
EXCLUSIONS_PATH = ROOT / "experimental-exclusions.json"
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXP_PREFIX = "[EXP] "
BASELINE_PHYSICAL_LIMIT = 9000


def read_index(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Read and return the experimental presets index mapping."""
    text = path.read_text(encoding="utf-8").strip()
    data = json.loads(text[len(INDEX_PREFIX):-1])
    files = data.get("files") or [f"chunk-{cid:03d}.js" for cid in range(len(data["chunks"]))]
    return data, files


def read_chunk(path: Path, cid: int) -> tuple[Path, str, dict[str, Any]]:
    """Read and return the presets from the specified experimental chunk file."""
    text = path.read_text(encoding="utf-8").strip()
    prefix = f"window.__bcPresetChunk({cid},"
    if not text.startswith(prefix) or not text.endswith(");"):
        raise ValueError(f"invalid chunk wrapper: {path}")
    return path, prefix, json.loads(text[len(prefix):-2])


def csv_escape(string_val: str) -> str:
    """Escape a string for safe inclusion in a CSV file."""
    if any(csv_char in string_val for csv_char in '",\n'):
        return f'"{string_val.replace(chr(34), chr(34) * 2)}"'
    return string_val


def atomic_write_text(path, text):
    """Write one generated file without exposing a partial file."""
    temporary = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False,
    )
    try:
        with temporary:
            temporary.write(text)
        os.replace(temporary.name, path)
    finally:
        Path(temporary.name).unlink(missing_ok=True)


def main() -> int:
    # ruff: noqa: C901, PLR0912, PLR0915
    """Analyze and remove duplicate presets from the experimental collection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", required=True, help="JSON report or list of approved experimental names")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-invalid", action="store_true",
        help="allow removal records without mainline matches when explicitly marked invalid",
    )
    parser.add_argument(
        "--reason", default="experimental duplicate approved",
        help="ledger and exclusion reason for the removal",
    )
    args = parser.parse_args()

    decision_data = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    decisions = decision_data.get("presets", decision_data) if isinstance(decision_data, dict) else decision_data
    decision_by_name = {
        item if isinstance(item, str) else item["experimentalName"]: item
        for item in decisions
    }
    approved = set(decision_by_name)
    if not approved or any(not name.startswith(EXP_PREFIX) for name in approved):
        raise SystemExit("every approved target must be a non-empty [EXP] runtime name")

    data, files = read_index(INDEX_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = {item["displayName"]: item for item in manifest.get("presets", [])}
    missing = sorted(approved - records.keys())
    if missing:
        raise SystemExit(f"not found in experimental manifest: {missing}")

    targets = []
    for name in sorted(approved):
        target = dict(records[name])
        decision = decision_by_name[name]
        if isinstance(decision, dict):
            target["mainlineMatches"] = decision.get(
                "exactMainlineMatches", target.get("mainlineMatches", [])
            )
            target["normalizedNameMatches"] = decision.get(
                "normalizedNameMatches", target.get("normalizedNameMatches", [])
            )
        targets.append(target)
    invalid = [
        item["displayName"] for item in targets
        if not (item.get("mainlineMatches") or item.get("normalizedNameMatches"))
    ]
    if invalid and not args.allow_invalid:
        raise SystemExit(f"refusing EXP-only targets without mainline matches: {invalid}")

    if args.dry_run:
        for item in targets:
            print(f"would remove {item['displayName']} (mainline matches: {len(item['mainlineMatches'])})")
        return

    by_chunk = {}
    for item in targets:
        by_chunk.setdefault(item["logicalChunk"], []).append(item["displayName"])

    for cid, names in by_chunk.items():
        path, prefix, chunk = read_chunk(OUT_DIR / files[cid], cid)
        for name in names:
            if name not in data["chunks"][cid]:
                raise SystemExit(f"index/chunk mismatch for {name!r} in logical chunk {cid}")
            data["chunks"][cid].remove(name)
            if name in chunk:
                del chunk[name]
            elif not args.allow_invalid:
                raise SystemExit(f"index/chunk mismatch for {name!r} in logical chunk {cid}")
        atomic_write_text(path, f"{prefix}{json.dumps(chunk, separators=(',', ':'), sort_keys=True)});\n")

    removed = set(approved)
    csv_lines = CSV_PATH.read_text(encoding="utf-8").splitlines()
    kept_lines = []
    for line in csv_lines:
        if not line:
            kept_lines.append(line)
            continue
        row = next(csv.reader([line]))
        if row and row[0].strip('"') in removed:
            continue
        kept_lines.append(line)
    atomic_write_text(CSV_PATH, "\n".join(kept_lines).rstrip("\n") + "\n")

    ledger_exists = REMOVED_CSV_PATH.exists()
    ledger = REMOVED_CSV_PATH.read_text(encoding="utf-8") if ledger_exists else "name,pack,chunk,commit,date,subject\n"
    ledger += "".join(
        f"{csv_escape(item['displayName'])},presets-extra,{item['logicalChunk']},,{date.today().isoformat()},"
        f"{args.reason}\n"
        for item in targets
    )
    atomic_write_text(REMOVED_CSV_PATH, ledger)

    manifest["presets"] = [item for item in manifest.get("presets", []) if item["displayName"] not in removed]
    exclusions = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8")) if EXCLUSIONS_PATH.exists() else []
    exclusions.extend({
        "displayName": item["displayName"],
        "sourceName": item["sourceName"],
        "mainlineMatches": item["mainlineMatches"],
        "reason": args.reason,
    } for item in targets)
    atomic_write_text(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")
    atomic_write_text(EXCLUSIONS_PATH, json.dumps(exclusions, indent=2) + "\n")
    atomic_write_text(INDEX_PATH, INDEX_PREFIX + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"removed {len(targets)} experimental presets")


if __name__ == "__main__":
    main()
