#!/usr/bin/env python3
"""Remove explicitly approved experimental presets."""

import argparse
import csv
import importlib.util
import json
import re
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
EXPERIMENTAL_NAME_PATTERN = re.compile(r"^\[EXP(?:[2-9]|[1-9][0-9]+)?\] .+$")
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


PRESET_IO_SPEC = importlib.util.spec_from_file_location(
    "preset_io", Path(__file__).resolve().with_name("preset_io.py"),
)
PRESET_IO = importlib.util.module_from_spec(PRESET_IO_SPEC)
PRESET_IO_SPEC.loader.exec_module(PRESET_IO)
atomic_write_text = PRESET_IO.atomic_write_text


LEDGER_HEADER = "name,pack,chunk,commit,date,subject\n"


def parse_arguments() -> argparse.Namespace:
    """Parse and return the command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", required=True, help="JSON report or list of approved experimental names")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-invalid", action="store_true",
        help="allow removal records without mainline matches when explicitly marked invalid",
    )
    parser.add_argument(
        "--allow-unmatched", action="store_true",
        help="allow approved curation targets without mainline matches",
    )
    parser.add_argument(
        "--reason", default="experimental duplicate approved",
        help="ledger and exclusion reason for the removal",
    )
    return parser.parse_args()


def load_decisions(path: Path) -> dict[str, Any]:
    """Return the approved decisions keyed by experimental runtime name."""
    decision_data = json.loads(path.read_text(encoding="utf-8"))
    decisions = decision_data.get("presets", decision_data) if isinstance(decision_data, dict) else decision_data
    decision_by_name = {
        item if isinstance(item, str) else item["experimentalName"]: item
        for item in decisions
    }
    if not decision_by_name or any(not EXPERIMENTAL_NAME_PATTERN.fullmatch(name) for name in decision_by_name):
        raise SystemExit("every target must use an [EXP], [EXP2], or later runtime prefix")
    return decision_by_name


def build_targets(decision_by_name: dict[str, Any], records: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one removal target per approved name, with decision matches applied."""
    missing = sorted(decision_by_name.keys() - records.keys())
    if missing:
        raise SystemExit(f"not found in experimental manifest: {missing}")
    targets = []
    for name in sorted(decision_by_name):
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
    return targets


def check_matches(targets: list[dict[str, Any]], args: argparse.Namespace) -> None:
    """Refuse targets without mainline matches unless an override allows them."""
    invalid = [
        item["displayName"] for item in targets
        if not (item.get("mainlineMatches") or item.get("normalizedNameMatches"))
    ]
    if invalid and not (args.allow_invalid or args.allow_unmatched):
        raise SystemExit(
            f"refusing experimental-only targets without mainline matches: {invalid}"
        )


def remove_from_index_and_chunks(targets: list[dict[str, Any]], allow_invalid: bool) -> None:
    """Remove the targets from index.js first and their chunk files second.

    A re-run treats a name already gone from the index as removed there.
    """
    data, files = read_index(INDEX_PATH)
    by_chunk = {}
    for item in targets:
        by_chunk.setdefault(item["logicalChunk"], []).append(item["displayName"])
    chunk_writes = []
    for cid, names in by_chunk.items():
        path, prefix, chunk = read_chunk(OUT_DIR / files[cid], cid)
        for name in names:
            if name in data["chunks"][cid]:
                if name not in chunk and not allow_invalid:
                    raise SystemExit(f"index/chunk mismatch for {name!r} in logical chunk {cid}")
                data["chunks"][cid].remove(name)
            chunk.pop(name, None)
        chunk_writes.append((path, f"{prefix}{json.dumps(chunk, separators=(',', ':'), sort_keys=True)});\n"))
    atomic_write_text(INDEX_PATH, INDEX_PREFIX + json.dumps(data, separators=(",", ":")) + ";\n")
    for path, text in chunk_writes:
        atomic_write_text(path, text)


def remove_inventory_rows(removed: set[str]) -> None:
    """Drop the removed names from preset-inventory.csv."""
    kept_lines = []
    for line in CSV_PATH.read_text(encoding="utf-8").splitlines():
        row = next(csv.reader([line])) if line else []
        if row and row[0].strip('"') in removed:
            continue
        kept_lines.append(line)
    atomic_write_text(CSV_PATH, "\n".join(kept_lines).rstrip("\n") + "\n")


def append_ledger_rows(targets: list[dict[str, Any]], reason: str) -> None:
    """Record each target in removed-presets.csv once, in the ledger's line ending."""
    ledger_exists = REMOVED_CSV_PATH.exists()
    ledger_bytes = REMOVED_CSV_PATH.read_bytes() if ledger_exists else b""
    ledger = ledger_bytes.decode("utf-8") if ledger_exists else LEDGER_HEADER
    ledger_newline = "\r\n" if b"\r\n" in ledger_bytes else "\n"
    if ledger_bytes and not ledger_bytes.endswith((b"\r", b"\n")):
        ledger += ledger_newline
    ledger_names = {row[0] for row in csv.reader(ledger.splitlines()) if row}
    ledger += "".join(
        f"{csv_escape(item['displayName'])},presets-extra,{item['logicalChunk']},,{date.today().isoformat()},"
        f"{reason}{ledger_newline}"
        for item in targets if item["displayName"] not in ledger_names
    )
    atomic_write_text(REMOVED_CSV_PATH, ledger)


def record_exclusions(targets: list[dict[str, Any]], reason: str) -> None:
    """Record each target in experimental-exclusions.json once."""
    exclusions = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8")) if EXCLUSIONS_PATH.exists() else []
    excluded_names = {item["displayName"] for item in exclusions}
    exclusions.extend({
        "displayName": item["displayName"],
        "sourceName": item["sourceName"],
        "mainlineMatches": item["mainlineMatches"],
        "reason": reason,
    } for item in targets if item["displayName"] not in excluded_names)
    atomic_write_text(EXCLUSIONS_PATH, json.dumps(exclusions, indent=2) + "\n")


def main() -> int:
    """Analyze and remove duplicate presets from the experimental collection.

    The index goes first and the manifest goes last. The manifest is the
    record of pending targets, so a crash leaves them pending. Every later
    write skips the work a previous run finished.
    """
    args = parse_arguments()
    decision_by_name = load_decisions(Path(args.decisions))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = {item["displayName"]: item for item in manifest.get("presets", [])}
    targets = build_targets(decision_by_name, records)
    check_matches(targets, args)

    if args.dry_run:
        for item in targets:
            print(f"would remove {item['displayName']} (mainline matches: {len(item['mainlineMatches'])})")
        return 0

    removed = set(decision_by_name)
    remove_from_index_and_chunks(targets, args.allow_invalid)
    remove_inventory_rows(removed)
    append_ledger_rows(targets, args.reason)
    record_exclusions(targets, args.reason)
    manifest["presets"] = [item for item in manifest.get("presets", []) if item["displayName"] not in removed]
    atomic_write_text(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")
    print(f"removed {len(targets)} experimental presets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
