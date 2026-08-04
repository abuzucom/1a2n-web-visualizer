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
fetch-extra-presets.py: it downloads the upstream zip (pinned to a commit;
sha256-checked once ZIP_SHA256 below is pinned to a known-good value --
see get_zip_bytes()), converts every .milk file, filters out anything whose
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
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from zipfile import ZipFile
from typing import Any

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


def referenced_textures(preset: dict[str, Any]) -> set[str]:
    """Return a set of texture filenames referenced in the given preset."""
    names = set()
    for field in ("warp", "comp"):
        shader = preset.get(field)
        if not isinstance(shader, str):
            continue
        for match in SAMPLER_RE.finditer(shader):
            names.add(WRAP_FILTER_PREFIX_RE.sub("", match.group(1)))
    return names


DOWNLOAD_TIMEOUT_S = 60
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024  # 200 MB -- generous headroom over the
# ~1-2 MB/1k-preset scale this collection actually is; a response anywhere
# near this is a sign something's wrong (redirect to the wrong resource,
# compromised upstream, etc.), not real preset data.


def _read_capped(resp: Any, max_bytes: int) -> bytes:
    """Download and return content from a URL response up to a maximum byte limit."""
    data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        sys.exit(f"download exceeded the {max_bytes/1e6:.0f} MB safety cap -- aborting")
    return data


def get_zip_bytes(zip_arg: str) -> bytes:
    """Fetch and return the bytes of a ZIP archive from the specified path or URL."""
    if zip_arg:
        data = Path(zip_arg).read_bytes()
        print(f"using local zip: {zip_arg} ({len(data)/1e6:.1f} MB)")
    else:
        if ZIP_SHA256 is None:
            sys.exit(
                "ZIP_SHA256 is not pinned -- refusing to download unverified upstream "
                "content. Run once with --zip against a manually-downloaded and "
                "reviewed copy of the archive to learn its digest (printed below), "
                "then hardcode that value as ZIP_SHA256 in this script before running "
                "a real network fetch."
            )
        print(f"downloading {ZIP_URL} ...")
        with urllib.request.urlopen(ZIP_URL, timeout=DOWNLOAD_TIMEOUT_S) as resp:
            data = _read_capped(resp, MAX_DOWNLOAD_BYTES)
        print(f"downloaded {len(data)/1e6:.1f} MB")
    digest = hashlib.sha256(data).hexdigest()
    if ZIP_SHA256 is None:
        print(f"NOTE: ZIP_SHA256 not yet pinned. This zip's sha256 is:\n  {digest}\n"
              "Verify the zip contents are what you expect, then hardcode this value "
              "as ZIP_SHA256 in this script -- required before this script will "
              "perform a real (non---zip) download; see the check above.",
              file=sys.stderr)
    elif digest != ZIP_SHA256:
        sys.exit(
            f"sha256 mismatch!\n  expected {ZIP_SHA256}\n  got      {digest}\n"
            "Upstream may have changed; verify the new zip manually, then "
            "update PINNED_COMMIT and ZIP_SHA256 in this script."
        )
    return data


def load_existing_names(csv_path: Path) -> set[str]:
    """Return a set of all preset names from the provided CSV file."""
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["name"] for row in csv.DictReader(f)}


MAX_ZIP_ENTRIES = 50_000
MAX_ZIP_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB


def safe_extract(zf, dest):
    """Extract all files with zip-bomb guards.

    Caps total entry count and total uncompressed size before extracting anything.
    Path traversal or zip-slip is handled by zipfile itself on modern Python.
    extractall normalizes and rejects unsafe member paths."""
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        sys.exit(f"zip has {len(infos)} entries, over the {MAX_ZIP_ENTRIES} safety cap -- aborting")
    total_size = sum(info.file_size for info in infos)
    if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
        sys.exit(
            f"zip would extract to {total_size/1e6:.0f} MB, over the "
            f"{MAX_ZIP_UNCOMPRESSED_BYTES/1e6:.0f} MB safety cap -- aborting"
        )
    zf.extractall(dest)


def load_next_chunk_id(index_path: Path) -> int:
    """Return the next available sequential chunk ID from the index."""
    if not index_path.exists():
        return 0
    text = index_path.read_text(encoding="utf-8").strip()
    payload = text[len(INDEX_PREFIX):].rstrip(";")
    data = json.loads(payload)
    return len(data["chunks"])


def convert_presets(milk_dir, tmp_dir):
    """Run tools/convert-milk-presets.js --dir over milk_dir.

    Return the {name: preset} dict it printed to stdout. Progress and warnings go to
    stderr and are passed through to this process's stderr. Redirect the child's
    stdout straight to a file rather than buffering it in a subprocess.PIPE.
    The full output can run to tens of MB for a large collection. This
    avoids holding two in-memory copies before json.loads starts."""
    out_path = tmp_dir / "converted.json"
    with out_path.open("wb") as out_file:
        subprocess.run(
            ["node", str(CONVERTER_SCRIPT), "--dir", str(milk_dir)],
            cwd=ROOT, stdout=out_file, check=True,
        )
    with out_path.open(encoding="utf-8") as f:
        return json.load(f)


def atomic_write_text(path, text):
    """Write text to path via a same-directory temp file and os.replace.

    A reader or a crash never observes a partially-written file. The path
    either has the old content or the new content, never a half-written mix."""
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def append_chunks(kept, start_chunk_id):
    """Append `kept` as new chunk-NNN.js files starting at start_chunk_id.

    Extend the index.js chunks array to match. Return a tuple of
    (new_chunk_id_to_names, total_bytes_written).

    Write chunk files atomically before index.js is updated to
    reference them. A crash mid-way leaves at worst harmless orphaned
    chunk files. It never leaves an index.js referencing an incomplete chunk."""
    names = sorted(kept)
    new_chunks = [names[i:i + PRESETS_PER_CHUNK] for i in range(0, len(names), PRESETS_PER_CHUNK)]

    total_bytes = 0
    for offset, chunk_names in enumerate(new_chunks):
        chunk_id = start_chunk_id + offset
        chunk = {name: kept[name] for name in chunk_names}
        text = f"window.__bcPresetChunk({chunk_id},{json.dumps(chunk, separators=(',', ':'))});\n"
        path = OUT_DIR / f"chunk-{chunk_id:03d}.js"
        atomic_write_text(path, text)
        total_bytes += path.stat().st_size

    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    payload = text[len(INDEX_PREFIX):].rstrip(";")
    data = json.loads(payload)
    data["chunks"].extend(new_chunks)
    atomic_write_text(INDEX_PATH, f"{INDEX_PREFIX}{json.dumps(data, separators=(',', ':'))};\n")

    return new_chunks, total_bytes


def append_inventory_rows(kept: dict[str, Any], start_chunk_id: int) -> None:
    """Append the provided preset records to the inventory file."""
    def esc(string_val: str) -> str:
        """Escape a string for safe inclusion in a CSV file."""
        return f'"{string_val.replace(chr(34), chr(34)*2)}"' if re.search(r'[",\n]', str(string_val)) else string_val

    names = sorted(kept)
    rows = []
    for offset in range(0, len(names), PRESETS_PER_CHUNK):
        chunk_id = start_chunk_id + offset // PRESETS_PER_CHUNK
        for name in names[offset:offset + PRESETS_PER_CHUNK]:
            rows.append(f"{esc(name)},presets-extra,{chunk_id}")

    existing = CSV_PATH.read_bytes()
    needs_leading_newline = existing and not existing.endswith(b"\n")
    with CSV_PATH.open("a", encoding="utf-8") as f:
        if needs_leading_newline:
            f.write("\n")
        f.write("\n".join(rows) + "\n")


def main() -> None:
    """Fetch, convert, and integrate the Cream of the Crop presets."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--zip", help="path to a local copy of the upstream zip")
    parser.add_argument("--dry-run", action="store_true",
                         help="print counts, write nothing")
    args = parser.parse_args()

    allowed = set(BUILTIN_TEXTURES)
    allowed.update(json.loads(IMAGE_NAMES_FILE.read_text()))

    existing = load_existing_names(CSV_PATH)
    lower_existing = {name.lower() for name in existing}
    removed = load_existing_names(REMOVED_CSV_PATH)

    zip_bytes = get_zip_bytes(args.zip)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with ZipFile(io.BytesIO(zip_bytes)) as zf:
            safe_extract(zf, tmp_path)
        # The archive unpacks into a single "<repo>-<sha>" root folder.
        roots = list(tmp_path.iterdir())
        milk_root = roots[0] if len(roots) == 1 else tmp_path

        print("converting .milk files (this can take a while)...")
        converted = convert_presets(milk_root, tmp_path)

    print(f"converted: {len(converted)}")

    already_present = {name for name in converted if name in existing}
    already_removed = {name for name in converted if name in removed}
    excluded_texture = {}
    kept = {}
    for preset_name, preset in converted.items():
        if preset_name.lower() in lower_existing or preset_name in removed:
            continue
        missing = referenced_textures(preset) - allowed
        if missing:
            excluded_texture[preset_name] = sorted(missing)
            continue
        kept[preset_name] = preset

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
