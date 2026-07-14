#!/usr/bin/env python3
"""
fetch-cream-of-the-crop-presets.py

Adds new presets to src/presets-extra/ from the "Cream of the Crop"
MilkDrop preset collection:

    https://github.com/projectM-visualizer/presets-cream-of-the-crop

Unlike the ansorre collection tools/fetch-extra-presets.py pulls, this
upstream repo ships raw MilkDrop .milk text (not pre-converted butterchurn
JSON), so this script also converts each preset via
tools/convert-milk-presets.js (the jberg toolchain: milkdrop-preset-utils +
milkdrop-eel-parser + milkdrop-shader-converter -- see that file's header
for details and the native-build prerequisite).

This is additive, not a full regenerate-from-scratch like
fetch-extra-presets.py: it downloads the upstream zip (pinned to a commit,
sha256-verified), converts every .milk file, filters out anything whose
name already exists in preset-inventory.csv or has ever been curated out
per removed-presets.csv, applies the same texture-availability filter as
the ansorre pipeline, and APPENDS the survivors as new chunk-NNN.js files
continuing from the current highest chunk id -- it never touches or
renumbers existing chunks.

Usage:
    python3 tools/fetch-cream-of-the-crop-presets.py            # download + generate
    python3 tools/fetch-cream-of-the-crop-presets.py --zip P    # use a local zip instead
    python3 tools/fetch-cream-of-the-crop-presets.py --dry-run  # print counts, write nothing

Requires the python3 standard library, plus Node with this repo's
devDependencies installed (npm install) and milkdrop-shader-converter's
native addon built (see tools/convert-milk-presets.js).
"""

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from zipfile import ZipFile

# Pinned to the master HEAD commit as of this script's authoring. Re-verify
# and update both values (see the sha256 mismatch message below) before
# relying on a newer upstream state.
PINNED_COMMIT = "0180df21f5e0bd39b9060cc5de420ed2f1f9e509"
ZIP_URL = (
    "https://github.com/projectM-visualizer/presets-cream-of-the-crop/"
    f"archive/{PINNED_COMMIT}.zip"
)
# Not yet verified end-to-end in a sandbox that could download the real
# archive -- fill in after the first successful run (see README).
ZIP_SHA256 = None

PRESETS_PER_CHUNK = 128

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
INDEX_PATH = OUT_DIR / "index.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
CSV_PATH = ROOT / "preset-inventory.csv"
REMOVED_CSV_PATH = ROOT / "removed-presets.csv"
IMAGE_NAMES_FILE = ROOT / "tools" / "butterchurn-image-names.json"
CONVERTER_SCRIPT = ROOT / "tools" / "convert-milk-presets.js"

# Kept in sync with tools/fetch-extra-presets.py's BUILTIN_TEXTURES.
BUILTIN_TEXTURES = {
    "main",
    "blur1", "blur2", "blur3",
    "noise_lq", "noise_lq_lite", "noise_mq", "noise_hq",
    "noisevol_lq", "noisevol_hq",
}
SAMPLER_RE = re.compile(r"\bsampler_([A-Za-z0-9_]+)")
WRAP_FILTER_PREFIX_RE = re.compile(r"^(?:fw|fc|pw|pc)_")


def referenced_textures(preset):
    names = set()
    for field in ("warp", "comp"):
        shader = preset.get(field)
        if not isinstance(shader, str):
            continue
        for match in SAMPLER_RE.finditer(shader):
            names.add(WRAP_FILTER_PREFIX_RE.sub("", match.group(1)))
    return names


def get_zip_bytes(zip_arg):
    if zip_arg:
        data = Path(zip_arg).read_bytes()
        print(f"using local zip: {zip_arg} ({len(data)/1e6:.1f} MB)")
    else:
        print(f"downloading {ZIP_URL} ...")
        with urllib.request.urlopen(ZIP_URL) as resp:
            data = resp.read()
        print(f"downloaded {len(data)/1e6:.1f} MB")
    digest = hashlib.sha256(data).hexdigest()
    if ZIP_SHA256 is None:
        print(f"NOTE: ZIP_SHA256 not yet pinned. This download's sha256 is:\n  {digest}\n"
              "Verify the zip contents are what you expect, then hardcode this value "
              "as ZIP_SHA256 in this script before relying on this check for integrity.",
              file=sys.stderr)
    elif digest != ZIP_SHA256:
        sys.exit(
            f"sha256 mismatch!\n  expected {ZIP_SHA256}\n  got      {digest}\n"
            "Upstream may have changed; verify the new zip manually, then "
            "update PINNED_COMMIT and ZIP_SHA256 in this script."
        )
    return data


def load_existing_names(csv_path):
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["name"] for row in csv.DictReader(f)}


def load_next_chunk_id(index_path):
    if not index_path.exists():
        return 0
    text = index_path.read_text(encoding="utf-8").strip()
    payload = text[len(INDEX_PREFIX):].rstrip(";")
    data = json.loads(payload)
    return len(data["chunks"])


def convert_presets(milk_dir):
    """Runs tools/convert-milk-presets.js --dir over milk_dir, returns the
    {name: preset} dict it prints to stdout (progress/warnings go to
    stderr, passed through to this process's stderr)."""
    result = subprocess.run(
        ["node", str(CONVERTER_SCRIPT), "--dir", str(milk_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, check=True,
    )
    return json.loads(result.stdout.decode("utf-8"))


def append_chunks(kept, start_chunk_id):
    """Appends `kept` (name -> preset) as new chunk-NNN.js files starting at
    start_chunk_id, and extends index.js's chunks array to match. Returns
    (new_chunk_id_to_names, total_bytes_written)."""
    names = sorted(kept)
    new_chunks = [names[i:i + PRESETS_PER_CHUNK] for i in range(0, len(names), PRESETS_PER_CHUNK)]

    total_bytes = 0
    for offset, chunk_names in enumerate(new_chunks):
        cid = start_chunk_id + offset
        payload = json.dumps(
            {n: kept[n] for n in chunk_names}, separators=(",", ":"), sort_keys=True,
        )
        text = f"window.__bcPresetChunk({cid},{payload});\n"
        path = OUT_DIR / f"chunk-{cid:03d}.js"
        path.write_text(text, encoding="utf-8")
        total_bytes += path.stat().st_size

    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    payload = text[len(INDEX_PREFIX):].rstrip(";")
    data = json.loads(payload)
    data["chunks"].extend(new_chunks)
    INDEX_PATH.write_text(
        f"{INDEX_PREFIX}{json.dumps(data, separators=(',', ':'))};\n", encoding="utf-8",
    )

    return new_chunks, total_bytes


def append_inventory_rows(kept, start_chunk_id):
    def esc(s):
        return f'"{s.replace(chr(34), chr(34)*2)}"' if re.search(r'[",\n]', str(s)) else s

    names = sorted(kept)
    rows = []
    for offset in range(0, len(names), PRESETS_PER_CHUNK):
        cid = start_chunk_id + offset // PRESETS_PER_CHUNK
        for name in names[offset:offset + PRESETS_PER_CHUNK]:
            rows.append(f"{esc(name)},presets-extra,{cid}")

    with CSV_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--zip", help="path to a local copy of the upstream zip")
    parser.add_argument("--dry-run", action="store_true",
                         help="print counts, write nothing")
    args = parser.parse_args()

    allowed = set(BUILTIN_TEXTURES)
    allowed.update(json.loads(IMAGE_NAMES_FILE.read_text()))

    existing = load_existing_names(CSV_PATH)
    removed = load_existing_names(REMOVED_CSV_PATH)

    zip_bytes = get_zip_bytes(args.zip)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp_path)
        # The archive unpacks into a single "<repo>-<sha>" root folder.
        roots = list(tmp_path.iterdir())
        milk_root = roots[0] if len(roots) == 1 else tmp_path

        print("converting .milk files (this can take a while)...")
        converted = convert_presets(milk_root)

    print(f"converted: {len(converted)}")

    already_present = {n for n in converted if n in existing}
    already_removed = {n for n in converted if n in removed}
    excluded_texture = {}
    kept = {}
    for name, preset in converted.items():
        if name in existing or name in removed:
            continue
        missing = referenced_textures(preset) - allowed
        if missing:
            excluded_texture[name] = sorted(missing)
            continue
        kept[name] = preset

    print(f"already in preset-inventory.csv: {len(already_present)}")
    print(f"already in removed-presets.csv ledger: {len(already_removed)}")
    print(f"excluded (missing textures): {len(excluded_texture)}")
    print(f"net new presets to add: {len(kept)}")

    if args.dry_run:
        print("dry run: nothing written")
        return

    if not kept:
        print("nothing to add")
        return

    start_chunk_id = load_next_chunk_id(INDEX_PATH)
    new_chunks, total_bytes = append_chunks(kept, start_chunk_id)
    append_inventory_rows(kept, start_chunk_id)

    print(f"chunks added: {len(new_chunks)} x <= {PRESETS_PER_CHUNK} presets "
          f"(chunk-{start_chunk_id:03d} .. chunk-{start_chunk_id + len(new_chunks) - 1:03d})")
    print(f"output size: {total_bytes/1e6:.1f} MB")


if __name__ == "__main__":
    main()
