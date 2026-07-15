#!/usr/bin/env python3
"""Remove explicitly approved EXP presets that have mainline counterparts."""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

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


def read_index():
    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    data = json.loads(text[len(INDEX_PREFIX):-1])
    files = data.get("files") or [f"chunk-{cid:03d}.js" for cid in range(len(data["chunks"]))]
    return data, files


def read_chunk(cid, filename):
    path = OUT_DIR / filename
    text = path.read_text(encoding="utf-8").strip()
    prefix = f"window.__bcPresetChunk({cid},"
    if not text.startswith(prefix) or not text.endswith(");"):
        raise ValueError(f"invalid chunk wrapper: {path}")
    return path, prefix, json.loads(text[len(prefix):-2])


def csv_escape(value):
    text = str(value)
    return f'"{text.replace(chr(34), chr(34) * 2)}"' if any(c in text for c in '",\n') else text


def main():  # noqa: C901
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

    data, files = read_index()
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
        path, prefix, chunk = read_chunk(cid, files[cid])
        for name in names:
            if name not in data["chunks"][cid]:
                raise SystemExit(f"index/chunk mismatch for {name!r} in logical chunk {cid}")
            data["chunks"][cid].remove(name)
            if name in chunk:
                del chunk[name]
            elif not args.allow_invalid:
                raise SystemExit(f"index/chunk mismatch for {name!r} in logical chunk {cid}")
        path.write_text(f"{prefix}{json.dumps(chunk, separators=(',', ':'), sort_keys=True)});\n", encoding="utf-8")

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
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(kept_lines).rstrip("\n") + "\n")

    ledger_exists = REMOVED_CSV_PATH.exists()
    with REMOVED_CSV_PATH.open("a", encoding="utf-8", newline="") as handle:
        if not ledger_exists:
            handle.write("name,pack,chunk,commit,date,subject\n")
        for item in targets:
            handle.write(
                f"{csv_escape(item['displayName'])},presets-extra,{item['logicalChunk']},,{date.today().isoformat()},"
                f"{args.reason}\n"
            )

    manifest["presets"] = [item for item in manifest.get("presets", []) if item["displayName"] not in removed]
    exclusions = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8")) if EXCLUSIONS_PATH.exists() else []
    exclusions.extend({
        "displayName": item["displayName"],
        "sourceName": item["sourceName"],
        "mainlineMatches": item["mainlineMatches"],
        "reason": args.reason,
    } for item in targets)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    EXCLUSIONS_PATH.write_text(json.dumps(exclusions, indent=2) + "\n", encoding="utf-8")
    INDEX_PATH.write_text(INDEX_PREFIX + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"removed {len(targets)} experimental presets")


if __name__ == "__main__":
    main()
