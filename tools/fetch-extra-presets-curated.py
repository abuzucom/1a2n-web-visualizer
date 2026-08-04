#!/usr/bin/env python3
"""
fetch-extra-presets-curated.py

Regenerates src/presets-extra/ the same way fetch-extra-presets.py does, but
preserves this deployment's preset curation two ways: any preset present in
a fresh upstream pull that is missing from the *currently committed*
index.js is treated as intentionally curated out (see the "Curation"
section in README.md), and any preset whose name appears in
removed-presets.csv -- the durable ledger of everything ever curated out,
maintained by tools/remove_presets.js -- is excluded too, even if it isn't
(or was never) present in the current index.js snapshot. Either signal is
enough to exclude a name from the regenerated output.

This only covers src/presets-extra/. Presets curated out of the vendored
.min.js packs (src/vendor/) are npm-packaged and out of scope here -- if one
of those bundles is ever regenerated, that curation must still be re-applied
by hand.

Usage:
    python3 tools/fetch-extra-presets-curated.py            # download + generate
    python3 tools/fetch-extra-presets-curated.py --zip P    # use a local zip instead
    python3 tools/fetch-extra-presets-curated.py --dry-run  # print the diff, write nothing

Requires only the python3 standard library.
"""

import argparse
import csv
import importlib.util
import io
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
INDEX_PATH = OUT_DIR / "index.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
REMOVED_CSV_PATH = ROOT / "removed-presets.csv"


def _load_fetch_module():
    """Import fetch-extra-presets.py (hyphenated filename, not a normal
    import target) to reuse its zip-fetch, texture-filter, and chunk-writing
    logic verbatim."""
    path = Path(__file__).resolve().parent / "fetch-extra-presets.py"
    spec = importlib.util.spec_from_file_location("fetch_extra_presets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_current_names(index_path):
    """Flat set of preset names in the currently committed index.js, or None
    if it doesn't exist yet (first-run case: no prior curation state, so
    nothing should be treated as curated-out)."""
    if not index_path.exists():
        return None
    text = index_path.read_text(encoding="utf-8").strip()
    payload = text[len(INDEX_PREFIX):].rstrip(";")
    data = json.loads(payload)
    names = set()
    for chunk_names in data["chunks"]:
        names.update(chunk_names)
    return names


def load_removed_names(csv_path):
    """Flat set of every preset name ever curated out of this repo, per
    removed-presets.csv. Empty set if the ledger doesn't exist yet."""
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["name"] for row in csv.DictReader(f)}


def main() -> None:
    """Fetch and organize curated experimental presets into the presets-extra directory."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--zip", help="path to a local copy of the upstream zip")
    parser.add_argument("--dry-run", action="store_true",
                         help="print the curated-out diff, write nothing")
    args = parser.parse_args()

    fetch = _load_fetch_module()

    allowed = set(fetch.BUILTIN_TEXTURES)
    allowed.update(json.loads(fetch.IMAGE_NAMES_FILE.read_text()))

    # Must read the current tree before write_output() wipes OUT_DIR.
    current_names = load_current_names(INDEX_PATH)
    removed_names = load_removed_names(REMOVED_CSV_PATH)

    zf = ZipFile(io.BytesIO(fetch.get_zip_bytes(args.zip)))
    fresh_presets, excluded_textures, bad_json = fetch.collect_presets(zf, allowed)

    snapshot_diff = set(fresh_presets) - current_names if current_names is not None else set()
    ledger_hits = set(fresh_presets) & removed_names
    curated_out = snapshot_diff | ledger_hits
    final_kept = {name: preset for name, preset in fresh_presets.items() if name not in curated_out}

    print(f"fresh upstream (post texture-filter): {len(fresh_presets)}")
    print(f"currently curated in (index.js):      "
          f"{0 if current_names is None else len(current_names)}")
    print(f"removed-presets.csv ledger entries:   {len(removed_names)}")
    print(f"re-excluding as curated-out:          {len(curated_out)}"
          f" ({len(snapshot_diff)} by snapshot diff, {len(ledger_hits)} by ledger)")
    for name in sorted(curated_out):
        print(f"  - {name}")
    print(f"final kept:                           {len(final_kept)}")

    if args.dry_run:
        print("dry run: nothing written")
        return

    chunks, total_bytes = fetch.write_output(final_kept, OUT_DIR)
    print(f"chunks:      {len(chunks)} x <= {fetch.PRESETS_PER_CHUNK} presets")
    print(f"output size: {total_bytes/1e6:.1f} MB in {OUT_DIR}")


if __name__ == "__main__":
    main()
