#!/usr/bin/env python3
"""Split the experimental texture bundle into lazy-loaded part files.

Read the generated single-file bundle or existing part files on re-runs.
Losslessly optimize each embedded image. Write deterministic part
files src/vendor/butterchurnExtraImagesExp-part-N.js. Each part calls
window.__bcExtraImagesExpPart(N, TOTAL, {name: {data, width, height}}).
visualizer-core.js injects the parts on demand and feeds each payload to
butterchurn as it arrives.

Use only lossless optimization. Skip gracefully when a helper is
missing. Optimize JPEG via jpegtran, convert BMP and single-frame GIF to PNG via
Pillow, and optimize PNG via optipng. Decode every optimized variant and compare
pixel-for-pixel against the original before accepting it.
"""

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    Image = None

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "src" / "vendor"
BUNDLE = VENDOR / "butterchurnExtraImagesExp.js"
PART_GLOB = "butterchurnExtraImagesExp-part-*.js"
BUNDLE_HEAD = "window.butterchurnExtraImagesExp={getImages:function(){return "
BUNDLE_TAIL = "}};\n"
PART_COUNT = 8
DATA_URI_RE = re.compile(r"^data:image/([a-z]+);base64,(.*)$", re.S)


def read_images() -> dict:
    """Load the image map from the single bundle or existing part files."""
    if BUNDLE.is_file():
        text = BUNDLE.read_text(encoding="utf-8")
        if not text.startswith(BUNDLE_HEAD) or not text.endswith(BUNDLE_TAIL):
            raise SystemExit(f"unexpected bundle wrapper in {BUNDLE}")
        return json.loads(text[len(BUNDLE_HEAD):-len(BUNDLE_TAIL)])
    images = {}
    parts = sorted(VENDOR.glob(PART_GLOB))
    if not parts:
        raise SystemExit("no butterchurnExtraImagesExp bundle or parts found")
    for path in parts:
        text = path.read_text(encoding="utf-8")
        prefix = "window.__bcExtraImagesExpPart("
        suffix = ");\n"
        if not text.startswith(prefix) or not text.endswith(suffix):
            raise SystemExit(f"unexpected part wrapper in {path}")
        inner = text[len(prefix):-len(suffix)]
        tokens = inner.split(",", 2)
        expected_tokens = 3
        if len(tokens) != expected_tokens:
            raise SystemExit(f"unexpected part wrapper in {path}")
        images.update(json.loads(tokens[2]))
    return images


def decoded_pixels(payload: bytes):
    """Return the fully decoded pixel content of an image, or None."""
    if Image is None:
        return None
    with Image.open(io.BytesIO(payload)) as image:
        return image.convert("RGBA").tobytes()


def run_optimizer(command: list, payload: bytes, suffix: str) -> bytes:
    """Run one optimizer CLI on payload and return the optimized bytes."""
    with tempfile.TemporaryDirectory() as workdir:
        src = Path(workdir) / f"in{suffix}"
        dst = Path(workdir) / f"out{suffix}"
        src.write_bytes(payload)
        argv = [arg.format(src=str(src), dst=str(dst)) for arg in command]
        subprocess.run(argv, check=True, capture_output=True)
        return dst.read_bytes()


def optimize_payload(kind: str, payload: bytes, stats: dict):
    """Return (mime, losslessly optimized payload) for one image."""
    original = decoded_pixels(payload)
    candidate = None
    mime = kind
    if kind == "jpeg" and shutil.which("jpegtran"):
        candidate = run_optimizer(
            ["jpegtran", "-copy", "none", "-optimize", "-outfile", "{dst}", "{src}"],
            payload, ".jpg")
    elif kind in ("bmp", "gif") and Image is not None:
        with Image.open(io.BytesIO(payload)) as image:
            if getattr(image, "n_frames", 1) > 1:
                stats["skipped_animated"] += 1
                return kind, payload
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
        candidate, mime = buffer.getvalue(), "png"
    elif kind == "png" and shutil.which("optipng"):
        candidate = run_optimizer(
            ["optipng", "-quiet", "-o2", "-out", "{dst}", "{src}"], payload, ".png")
    if candidate is None or len(candidate) >= len(payload):
        return kind, payload
    if original is None or decoded_pixels(candidate) != original:
        stats["rejected_mismatch"] += 1
        return kind, payload
    stats["saved"][kind] = stats["saved"].get(kind, 0) + len(payload) - len(candidate)
    return mime, candidate


def optimize_images(texture_data: dict[str, Any]) -> dict[str, Any]:
    """Compress and return a dictionary of optimized image payloads."""
    stats = {"saved": {}, "rejected_mismatch": 0, "skipped_animated": 0}
    for name, record in texture_data.items():
        match = DATA_URI_RE.match(record["data"])
        if not match:
            raise SystemExit(f"unexpected data URI for image {name!r}")
        kind, payload = match.group(1), base64.b64decode(match.group(2))
        mime, optimized = optimize_payload(kind, payload, stats)
        record["data"] = "data:image/%s;base64,%s" % (
            mime, base64.b64encode(optimized).decode("ascii"))
    for kind, saved in sorted(stats["saved"].items()):
        print(f"lossless savings ({kind}): {saved / 1e6:.1f} MB")
    if stats["rejected_mismatch"]:
        print(f"rejected non-identical variants: {stats['rejected_mismatch']}")
    if stats["skipped_animated"]:
        print(f"skipped animated images: {stats['skipped_animated']}")
    return texture_data


def write_parts(images: dict, dry_run: bool) -> None:
    """Write size-balanced deterministic part files and drop the old bundle."""
    names = sorted(images)
    total_bytes = sum(len(images[name]["data"]) for name in names)
    if not PART_COUNT:
        raise ValueError("PART_COUNT cannot be zero")
    target = total_bytes / PART_COUNT
    parts, current, filled = [], {}, 0
    for name in names:
        current[name] = images[name]
        filled += len(images[name]["data"])
        if filled >= target and len(parts) < PART_COUNT - 1:
            parts.append(current)
            current, filled = {}, 0
    parts.append(current)
    for number, payload in enumerate(parts):
        path = VENDOR / f"butterchurnExtraImagesExp-part-{number}.js"
        text = "window.__bcExtraImagesExpPart(%d,%d,%s);\n" % (
            number, len(parts),
            json.dumps(payload, separators=(",", ":"), sort_keys=True))
        print(f"{path.name}: {len(payload)} images, {len(text) / 1e6:.1f} MB")
        if not dry_run:
            path.write_text(text, encoding="utf-8")
    if not dry_run:
        for stale in sorted(VENDOR.glob(PART_GLOB)):
            number = int(stale.stem.rsplit("-", 1)[-1])
            if number >= len(parts):
                stale.unlink()
        if BUNDLE.is_file():
            os.remove(BUNDLE)


def main() -> None:
    """Repackage experimental textures into optimized, chunked JSON payloads."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-optimize", action="store_true",
        help="split without recompressing image payloads")
    args = parser.parse_args()
    images = read_images()
    print(f"images: {len(images)}")
    if not args.no_optimize:
        images = optimize_images(images)
    write_parts(images, args.dry_run)


if __name__ == "__main__":
    main()
