#!/usr/bin/env python3
"""Compare experimental presets with the baseline lazy-loaded collection.

The report deliberately considers only mainline chunk files below the
reserved experimental physical range. EXP-only presets are reported but are
never removal candidates.
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
INDEX_PATH = OUT_DIR / "index.js"
MANIFEST_PATH = ROOT / "experimental-presets.json"
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXP_PREFIX = "[EXP] "
EXPERIMENTAL_PHYSICAL_BASE = 9000


def canonicalize(value):
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if value == 0:
        return 0
    return value


def digest(preset):
    payload = json.dumps(
        canonicalize(preset), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_index():
    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    data = json.loads(text[len(INDEX_PREFIX):-1])
    files = data.get("files") or [f"chunk-{cid:03d}.js" for cid in range(len(data["chunks"]))]
    if len(files) != len(data["chunks"]):
        raise ValueError("index chunks/files lengths differ")
    return data, files


def read_chunk(cid, filename):
    text = (OUT_DIR / filename).read_text(encoding="utf-8").strip()
    prefix = f"window.__bcPresetChunk({cid},"
    if not text.startswith(prefix) or not text.endswith(");"):
        raise ValueError(f"invalid chunk wrapper: {filename}")
    return json.loads(text[len(prefix):-2])


def physical_id(filename):
    stem = Path(filename).stem
    suffix = stem.rsplit("-", 1)[-1]
    return int(suffix) if suffix.isdigit() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default="experimental-duplicate-report.json")
    args = parser.parse_args()

    data, files = read_index()
    mainline_by_hash = {}
    mainline_by_name = {}
    for cid, filename in enumerate(files):
        if (physical_id(filename) or 0) >= EXPERIMENTAL_PHYSICAL_BASE:
            continue
        chunk = read_chunk(cid, filename)
        for name in data["chunks"][cid]:
            if name not in chunk:
                raise ValueError(f"{name!r} missing from {filename}")
            item = {"name": name, "logicalChunk": cid, "physicalFile": filename}
            mainline_by_hash.setdefault(digest(chunk[name]), []).append(item)
            mainline_by_name[name] = item | {"canonicalHash": digest(chunk[name])}

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results = []
    for record in manifest.get("presets", []):
        source_name = record["sourceName"]
        normalized = source_name[len(EXP_PREFIX):] if source_name.startswith(EXP_PREFIX) else source_name
        matches = list(mainline_by_hash.get(record["canonicalHash"], []))
        same_name = mainline_by_name.get(normalized)
        results.append({
            "experimentalName": record["displayName"],
            "sourceName": source_name,
            "canonicalHash": record["canonicalHash"],
            "logicalChunk": record["logicalChunk"],
            "physicalFile": record["physicalFile"],
            "exactMainlineMatches": matches,
            "normalizedNameMatches": [same_name] if same_name else [],
            "removalEligible": bool(matches or same_name),
        })

    report = {
        "version": 1,
        "mainlineChunkCount": sum(
            1 for filename in files if (physical_id(filename) or 0) < EXPERIMENTAL_PHYSICAL_BASE
        ),
        "experimentalCount": len(results),
        "exactDuplicateCount": sum(bool(item["exactMainlineMatches"]) for item in results),
        "nameMatchCount": sum(bool(item["normalizedNameMatches"]) for item in results),
        "removalEligibleCount": sum(item["removalEligible"] for item in results),
        "presets": results,
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "presets"}, indent=2))


if __name__ == "__main__":
    main()
