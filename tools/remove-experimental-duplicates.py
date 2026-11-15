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
ENERGY_CATALOG_PATH = ROOT / "energy-catalog.json"
PERFORMANCE_CATALOG_PATH = ROOT / "performance-catalog.json"
ENERGY_BUNDLE_PATH = ROOT / "src" / "catalogs" / "energy-catalog.js"
PERFORMANCE_BUNDLE_PATH = ROOT / "src" / "catalogs" / "performance-catalog.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXPERIMENTAL_NAME_PATTERN = re.compile(r"^\[EXP(?:[2-9]|[1-9][0-9]+)?\] .+$")
BASELINE_PHYSICAL_LIMIT = 9000
EXPERIMENTAL_PACK = "presets-extra"
LEDGER_HEADER = "name,pack,chunk,commit,date,subject\n"


def load_sibling_module(module_name: str, filename: str) -> Any:
    """Load and return a module that lives next to this script."""
    spec = importlib.util.spec_from_file_location(module_name, Path(__file__).resolve().with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRESET_IO = load_sibling_module("preset_io", "preset_io.py")
CATALOGS = load_sibling_module("curate_catalogs", "curate_catalogs.py")
atomic_write_text = PRESET_IO.atomic_write_text


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


def parse_arguments() -> argparse.Namespace:
    """Parse and return the command-line arguments."""
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


def resolve_targets(decision_by_name: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the manifest records for the approved names with decision matches applied."""
    records = {item["displayName"]: item for item in manifest.get("presets", [])}
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


def refuse_unmatched_targets(targets: list[dict[str, Any]], args: argparse.Namespace) -> None:
    """Stop when a target has no mainline match and no override flag allows it."""
    invalid = [
        item["displayName"] for item in targets
        if not (item.get("mainlineMatches") or item.get("normalizedNameMatches"))
    ]
    if invalid and not (args.allow_invalid or args.allow_unmatched):
        raise SystemExit(
            f"refusing experimental-only targets without mainline matches: {invalid}"
        )


def remove_from_index_and_chunks(targets: list[dict[str, Any]], allow_invalid: bool) -> None:
    """Drop the targets from index.js and their chunk files.

    Every chunk is read and checked before the first write. The index goes
    first and the manifest goes last. The manifest is the record of pending
    targets, so a crash leaves them pending. A re-run treats a name already
    gone from the index as removed there. Every later write skips the work a
    previous run finished.
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
        if not line:
            kept_lines.append(line)
            continue
        row = next(csv.reader([line]))
        if row and row[0].strip('"') in removed:
            continue
        kept_lines.append(line)
    atomic_write_text(CSV_PATH, "\n".join(kept_lines).rstrip("\n") + "\n")


def append_ledger_rows(targets: list[dict[str, Any]], reason: str) -> None:
    """Append one removed-presets.csv row per target the ledger lacks."""
    ledger_exists = REMOVED_CSV_PATH.exists()
    ledger_bytes = REMOVED_CSV_PATH.read_bytes() if ledger_exists else b""
    ledger = ledger_bytes.decode("utf-8") if ledger_exists else LEDGER_HEADER
    ledger_newline = "\r\n" if b"\r\n" in ledger_bytes else "\n"
    if ledger_bytes and not ledger_bytes.endswith((b"\r", b"\n")):
        ledger += ledger_newline
    ledger_names = {row[0] for row in csv.reader(ledger.splitlines()) if row}
    today = date.today().isoformat()
    ledger += "".join(
        f"{csv_escape(item['displayName'])},{EXPERIMENTAL_PACK},{item['logicalChunk']},,{today},"
        f"{csv_escape(reason)}{ledger_newline}"
        for item in targets if item["displayName"] not in ledger_names
    )
    atomic_write_text(REMOVED_CSV_PATH, ledger)


def clear_catalog_entries(removed: set[str]) -> None:
    """Drop catalog entries that name a removed preset and rewrite the bundles.

    Each catalog entry names its preset as ``pack:name``. Only entries of the
    experimental pack refer to the removed presets. A catalog without a
    matching entry stays untouched.
    """
    removed_ids = {CATALOGS.catalog_id(EXPERIMENTAL_PACK, name) for name in removed}
    energy = CATALOGS.read_catalog(ENERGY_CATALOG_PATH)
    kept_energy = {key: value for key, value in energy["presets"].items() if key not in removed_ids}
    if len(kept_energy) != len(energy["presets"]):
        energy["presets"] = kept_energy
        atomic_write_text(ENERGY_CATALOG_PATH, CATALOGS.catalog_text(energy))
        atomic_write_text(ENERGY_BUNDLE_PATH, CATALOGS.bundle_text(CATALOGS.ENERGY_GLOBAL, energy))
    performance = CATALOGS.read_catalog(PERFORMANCE_CATALOG_PATH, [])
    kept_performance = [entry for entry in performance["presets"] if entry not in removed_ids]
    if len(kept_performance) != len(performance["presets"]):
        performance["presets"] = kept_performance
        atomic_write_text(PERFORMANCE_CATALOG_PATH, CATALOGS.catalog_text(performance))
        atomic_write_text(
            PERFORMANCE_BUNDLE_PATH, CATALOGS.bundle_text(CATALOGS.PERFORMANCE_GLOBAL, performance),
        )


def append_exclusions(targets: list[dict[str, Any]], reason: str) -> None:
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
    """Remove the approved presets from the experimental collection."""
    args = parse_arguments()
    decision_by_name = load_decisions(Path(args.decisions))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    targets = resolve_targets(decision_by_name, manifest)
    refuse_unmatched_targets(targets, args)

    if args.dry_run:
        for item in targets:
            print(f"would remove {item['displayName']} (mainline matches: {len(item['mainlineMatches'])})")
        return 0

    removed = set(decision_by_name)
    remove_from_index_and_chunks(targets, args.allow_invalid)
    remove_inventory_rows(removed)
    append_ledger_rows(targets, args.reason)
    clear_catalog_entries(removed)
    append_exclusions(targets, args.reason)
    manifest["presets"] = [item for item in manifest.get("presets", []) if item["displayName"] not in removed]
    atomic_write_text(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")
    print(f"removed {len(targets)} experimental presets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
