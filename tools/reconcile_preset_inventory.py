#!/usr/bin/env python3
"""Reconcile preset-inventory.csv with the authoritative presets-extra index.

The inventory is bookkeeping, not runtime data. Earlier curation passes left
it missing rows for presets that still ship in src/presets-extra/. This tool
restores the invariant that every presets-extra row corresponds to a live
index entry and vice versa:

- rows whose preset name is no longer in index.js are dropped,
- live index names missing from the inventory are appended as one sorted
  section, matching the file's historical append-sectioned layout.

Vendored-pack rows are preserved untouched. The tool is idempotent and only
reads generated data; it never touches chunk files or index.js.
"""

import argparse
import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "src" / "presets-extra" / "index.js"
CSV_PATH = ROOT / "preset-inventory.csv"
INDEX_PREFIX = "window.BCExtraPresetIndex="
PACK = "presets-extra"


def read_live_presets() -> dict:
    """Return {name: logical chunk id} for every preset in index.js."""
    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    data = json.loads(text[len(INDEX_PREFIX):-1])
    live = {}
    for cid, names in enumerate(data["chunks"]):
        for name in names:
            live[name] = cid
    return live


def format_rows(rows: list) -> str:
    """Serialize inventory rows with the file's minimal-quoting style."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    live = read_live_presets()
    rows = list(csv.reader(CSV_PATH.open(encoding="utf-8")))
    header, body = rows[0], rows[1:]

    kept = [r for r in body if r[1] != PACK or r[0] in live]
    dropped = len(body) - len(kept)
    inventoried = {r[0] for r in kept if r[1] == PACK}
    missing = sorted(name for name in live if name not in inventoried)
    appended = [[name, PACK, str(live[name])] for name in missing]

    print(f"live index presets: {len(live)}")
    print(f"dropped stale presets-extra rows: {dropped}")
    print(f"appended missing presets-extra rows: {len(appended)}")
    if args.dry_run:
        print("Dry run, no files written.")
        return

    CSV_PATH.write_text(format_rows([header] + kept + appended), encoding="utf-8")
    total = len(kept) + len(appended)
    print(f"preset-inventory.csv now has {total} rows plus header.")


if __name__ == "__main__":
    main()
