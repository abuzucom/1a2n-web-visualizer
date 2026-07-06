#!/usr/bin/env python3
"""
fetch-extra-presets.py

Regenerates src/presets-extra/ from the "tens of thousands of Milkdrop
presets for butterchurn" collection:

    https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn

The upstream repo is a single zip of ~15k butterchurn-converted preset JSON
files. This script downloads it (pinned to a commit, sha256-verified),
filters out presets that reference custom textures we can't supply, and
packs the rest into classic-script chunk files that the app lazy-loads via
injected <script> tags (fetch() of local JSON doesn't work from file://,
so the presets must live in .js files to keep the app portable).

Output (all of src/presets-extra/ is wiped and regenerated):
    index.js      window.BCExtraPresetIndex = {v:1, chunks:[[names...],...]}
    chunk-NNN.js  window.__bcPresetChunk(NNN, { "<name>": <preset>, ... });

Usage:
    python3 tools/fetch-extra-presets.py            # download + generate
    python3 tools/fetch-extra-presets.py --zip P    # use a local zip instead

Requires only the python3 standard library.
"""

import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path
from zipfile import ZipFile

PINNED_COMMIT = "8b47ff45a40a9e5a0fe7319bde19e3633a01b45f"
ZIP_URL = (
    "https://raw.githubusercontent.com/ansorre/"
    "tens-of-thousands-milkdrop-presets-for-butterchurn/"
    f"{PINNED_COMMIT}/milkdrop-presets-for-butterchurn.zip"
)
ZIP_SHA256 = "6d907cf1a47af50332301ddd171164c9b593eed2b02659fe183b72319274fa86"

PRESETS_PER_CHUNK = 128

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
IMAGE_NAMES_FILE = ROOT / "tools" / "butterchurn-image-names.json"

# Textures butterchurn provides on its own (see src/vendor/butterchurn.min.js):
# the main/framebuffer samplers, the blur passes, and the generated noise
# textures. Anything else must come from the vendored extra-images pack.
BUILTIN_TEXTURES = {
    "main",
    "blur1", "blur2", "blur3",
    "noise_lq", "noise_lq_lite", "noise_mq", "noise_hq",
    "noisevol_lq", "noisevol_hq",
}

# sampler_fw_x / sampler_fc_x / sampler_pw_x / sampler_pc_x are wrap/filter
# variants of texture "x"; a bare sampler_x uses defaults.
SAMPLER_RE = re.compile(r"\bsampler_([A-Za-z0-9_]+)")
WRAP_FILTER_PREFIX_RE = re.compile(r"^(?:fw|fc|pw|pc)_")


def referenced_textures(preset):
    """Texture names referenced by the preset's warp/comp shaders."""
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
    if digest != ZIP_SHA256:
        sys.exit(
            f"sha256 mismatch!\n  expected {ZIP_SHA256}\n  got      {digest}\n"
            "Upstream may have changed; verify the new zip manually, then "
            "update PINNED_COMMIT and ZIP_SHA256 in this script."
        )
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--zip", help="path to a local copy of the upstream zip")
    args = parser.parse_args()

    allowed = set(BUILTIN_TEXTURES)
    allowed.update(json.loads(IMAGE_NAMES_FILE.read_text()))

    zf = ZipFile(io.BytesIO(get_zip_bytes(args.zip)))
    members = sorted(
        m for m in zf.namelist()
        if m.startswith("converted/") and m.endswith(".json")
    )

    kept = {}          # preset name -> parsed preset
    bad_json = []
    excluded = {}      # preset name -> sorted missing texture names
    for member in members:
        name = member[len("converted/"):-len(".json")]
        try:
            preset = json.loads(zf.read(member).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            bad_json.append(name)
            print(f"warning: skipping unparseable {name!r}: {exc}", file=sys.stderr)
            continue
        missing = referenced_textures(preset) - allowed
        if missing:
            excluded[name] = sorted(missing)
            continue
        kept[name] = preset

    names = sorted(kept)
    chunks = [names[i:i + PRESETS_PER_CHUNK]
              for i in range(0, len(names), PRESETS_PER_CHUNK)]

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    total_bytes = 0
    for cid, chunk_names in enumerate(chunks):
        payload = json.dumps(
            {n: kept[n] for n in chunk_names},
            separators=(",", ":"), sort_keys=True,
        )
        text = f"window.__bcPresetChunk({cid},{payload});\n"
        path = OUT_DIR / f"chunk-{cid:03d}.js"
        path.write_text(text, encoding="utf-8")
        total_bytes += path.stat().st_size

    index_payload = json.dumps(
        {"v": 1, "chunks": chunks}, separators=(",", ":")
    )
    index_path = OUT_DIR / "index.js"
    index_path.write_text(
        f"window.BCExtraPresetIndex={index_payload};\n", encoding="utf-8"
    )
    total_bytes += index_path.stat().st_size

    missing_counts = {}
    for texs in excluded.values():
        for t in texs:
            missing_counts[t] = missing_counts.get(t, 0) + 1
    top_missing = sorted(missing_counts.items(), key=lambda kv: -kv[1])[:10]

    print(f"presets in zip:        {len(members)}")
    print(f"unparseable (skipped): {len(bad_json)}")
    print(f"excluded (textures):   {len(excluded)}")
    print(f"kept:                  {len(names)}")
    print(f"chunks:                {len(chunks)} x <= {PRESETS_PER_CHUNK} presets")
    print(f"output size:           {total_bytes/1e6:.1f} MB in {OUT_DIR}")
    if top_missing:
        print("most-missed textures:  "
              + ", ".join(f"{t} ({c})" for t, c in top_missing))


if __name__ == "__main__":
    main()
