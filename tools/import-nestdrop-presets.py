#!/usr/bin/env python3
"""Import supplied NestDrop MilkDrop archives as experimental presets.

Only .milk files and files under a top-level Textures/ directory are read from
the supplied ZIPs. The importer never executes or extracts unrelated archive
members. DDS-dependent presets are skipped because browsers cannot load DDS
textures through the image bundle. Duplicate basenames receive deterministic
``[variant N]`` suffixes when their converted content differs; identical
converted content is retained once. Experimental runtime names receive the
reserved ``[EXP] `` prefix.

Usage:
    python3 tools/import-nestdrop-presets.py --zip PACK.zip --dry-run
    python3 tools/import-nestdrop-presets.py --zip PACK1.zip --zip PACK2.zip
    python3 tools/import-nestdrop-presets.py --zip PACK.zip --offset 3000 --limit 1000

Logical chunk IDs remain contiguous in index.js. Experimental physical files
start at chunk-9000.js and are recorded in index.js's optional ``files`` map.
Never use 9000+ as a logical chunk ID.
"""

import argparse
import base64
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
INDEX_PATH = OUT_DIR / "index.js"
CSV_PATH = ROOT / "preset-inventory.csv"
REMOVED_CSV_PATH = ROOT / "removed-presets.csv"
MANIFEST_PATH = ROOT / "experimental-presets.json"
TEXTURE_MANIFEST_PATH = ROOT / "experimental-textures.json"
TEXTURE_BUNDLE_PATH = ROOT / "src" / "vendor" / "butterchurnExtraImagesExp.js"
CONVERTER = ROOT / "tools" / "convert-milk-presets.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXP_PREFIX = "[EXP] "
PHYSICAL_CHUNK_BASE = 9000
PRESETS_PER_CHUNK = 128

BUILTIN_TEXTURES = {
    "main", "blur1", "blur2", "blur3", "noise_lq", "noise_lq_lite",
    "noise_mq", "noise_hq", "noisevol_lq", "noisevol_hq",
}
SAMPLER_RE = re.compile(r"\bsampler_([A-Za-z0-9_]+)")
FILTER_PREFIX_RE = re.compile(r"^(?:fw|fc|pw|pc)_")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".dds"}
EXISTING_TEXTURE_NAMES = {
    "cells", "cloudsImage", "lichen", "prayerwheel", "seaweed",
    "smalltiled_lizard_scales",
}


def read_csv_names(path):
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["name"] for row in csv.DictReader(handle)}


def read_index():
    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    if not text.startswith(INDEX_PREFIX) or not text.endswith(";"):
        raise ValueError(f"unexpected index wrapper in {INDEX_PATH}")
    data = json.loads(text[len(INDEX_PREFIX):-1])
    files = data.get("files")
    if files is None:
        files = [f"chunk-{cid:03d}.js" for cid in range(len(data["chunks"]))]
    if len(files) != len(data["chunks"]):
        raise ValueError("index.js chunks/files lengths differ")
    return data, files


def read_chunk(cid, filename):
    path = OUT_DIR / filename
    text = path.read_text(encoding="utf-8").strip()
    prefix = f"window.__bcPresetChunk({cid},"
    if not text.startswith(prefix) or not text.endswith(");"):
        raise ValueError(f"unexpected chunk wrapper in {path}")
    return json.loads(text[len(prefix):-2])


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


def preset_hash(preset):
    payload = json.dumps(
        canonicalize(preset), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_mainline_hashes(data, files):
    by_hash = {}
    by_name = {}
    for cid, names in enumerate(data["chunks"]):
        chunk = read_chunk(cid, files[cid])
        for name in names:
            if name not in chunk:
                raise ValueError(f"{name!r} missing from {files[cid]}")
            digest = preset_hash(chunk[name])
            by_hash.setdefault(digest, []).append({"name": name, "chunk": cid})
            by_name[name] = {"hash": digest, "chunk": cid}
    return by_hash, by_name


def safe_member_path(root, member_name):
    parts = PurePosixPath(member_name.replace("\\", "/")).parts
    if not parts or parts[0] in ("", ".") or ".." in parts:
        raise ValueError(f"unsafe ZIP member path: {member_name}")
    destination = root.joinpath(*parts)
    if root not in destination.parents:
        raise ValueError(f"ZIP member escaped extraction root: {member_name}")
    return destination


def extract_source(zip_path, destination, offset=0, max_milk=None):  # noqa: C901
    milk_count = 0
    skipped_milk = 0
    texture_files = []
    collision_counts = {}
    collision_records = []
    source_entries = []
    with ZipFile(zip_path) as archive:
        milk_members = [
            info for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".milk")
        ]
        for info in milk_members:
            stem = PurePosixPath(info.filename).stem
            collision_counts[stem] = collision_counts.get(stem, 0) + 1
        collision_seen = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            lower = info.filename.replace("\\", "/").lower()
            is_milk = lower.endswith(".milk")
            is_texture = (
                lower.startswith("textures/") or "/textures/" in lower
            ) and Path(lower).suffix in IMAGE_SUFFIXES
            if not is_milk and not is_texture:
                continue
            if is_milk:
                stem = PurePosixPath(info.filename).stem
                ordinal = collision_seen.get(stem, 0) + 1
                collision_seen[stem] = ordinal
                runtime_stem = stem
                if collision_counts[stem] > 1 and ordinal > 1:
                    runtime_stem = f"{stem} [variant {ordinal}]"
                if skipped_milk < offset:
                    skipped_milk += 1
                    continue
                if max_milk is not None and milk_count >= max_milk:
                    continue
                source_entries.append({
                    "sourcePath": info.filename,
                    "originalName": stem,
                    "runtimeName": runtime_stem,
                })
                if collision_counts[stem] > 1 and ordinal > 1:
                    collision_records.append({
                        "sourcePath": info.filename,
                        "originalName": stem,
                        "runtimeName": runtime_stem,
                        "variant": ordinal,
                    })
            destination_path = safe_member_path(destination, info.filename)
            if is_milk and runtime_stem != PurePosixPath(info.filename).stem:
                destination_path = destination_path.with_name(
                    runtime_stem + destination_path.suffix
                )
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(archive.read(info))
            if is_milk:
                milk_count += 1
            else:
                texture_files.append(destination_path)
    return milk_count, texture_files, collision_records, source_entries


def run_converter(source_root, output_path):
    with output_path.open("wb") as output:
        subprocess.run(
            ["node", str(CONVERTER), "--dir", str(source_root)],
            cwd=ROOT, stdout=output, check=True,
        )
    return json.loads(output_path.read_text(encoding="utf-8"))


def image_dimensions(data, suffix):
    if suffix in {".png"} and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if suffix in {".gif"} and data[:6] in (b"GIF87a", b"GIF89a"):
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if suffix == ".bmp" and data[:2] == b"BM":
        return int.from_bytes(data[18:22], "little"), abs(int.from_bytes(data[22:26], "little", signed=True))
    if suffix in {".jpg", ".jpeg"} and data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 9 < len(data):
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            pos += 2
            if marker in (0xD8, 0xD9):
                continue
            if pos + 2 > len(data):
                break
            length = int.from_bytes(data[pos:pos + 2], "big")
            is_frame_marker = (
                marker in range(0xC0, 0xC4)
                or marker in range(0xC5, 0xC8)
                or marker in range(0xC9, 0xCC)
                or marker in range(0xCD, 0xD0)
            )
            if is_frame_marker:
                return int.from_bytes(data[pos + 5:pos + 7], "big"), int.from_bytes(data[pos + 3:pos + 5], "big")
            pos += length
    raise ValueError("unsupported or malformed image dimensions")


def texture_names(preset):
    refs = set()
    for field in ("warp", "comp"):
        shader = preset.get(field, "")
        if isinstance(shader, str):
            for match in SAMPLER_RE.finditer(shader):
                refs.add(FILTER_PREFIX_RE.sub("", match.group(1)).lower())
    return refs - BUILTIN_TEXTURES


def build_texture_bundle(texture_files):
    images = {}
    records = []
    unavailable = []
    seen_digests = {}
    for path in sorted(texture_files):
        if path.suffix.lower() == ".dds":
            unavailable.append({"name": path.stem, "reason": "unsupported DDS"})
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        suffix = path.suffix.lower()
        stem = path.stem
        try:
            width, height = image_dimensions(data, suffix)
        except ValueError as exc:
            unavailable.append({"name": stem, "reason": str(exc)})
            continue
        if stem.lower() in seen_digests and seen_digests[stem.lower()] != digest:
            raise ValueError(f"texture name collision with different bytes: {stem}")
        seen_digests[stem.lower()] = digest
        encoded = base64.b64encode(data).decode("ascii")
        mime = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".gif": "gif", ".bmp": "bmp", ".dds": "dds"}[suffix]
        value = {"data": f"data:image/{mime};base64,{encoded}", "width": width, "height": height}
        for name in {stem, stem.lower()} - EXISTING_TEXTURE_NAMES:
            images[name] = value
        records.append({"name": stem, "sha256": digest, "width": width, "height": height})
    return images, records, unavailable


def write_texture_bundle(images, records):
    TEXTURE_BUNDLE_PATH.write_text(
        "window.butterchurnExtraImagesExp="
        + "{getImages:function(){return "
        + json.dumps(images, separators=(",", ":"))
        + "}};\n",
        encoding="utf-8",
    )
    TEXTURE_MANIFEST_PATH.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def csv_escape(value):
    text = str(value)
    return f'"{text.replace(chr(34), chr(34) * 2)}"' if any(c in text for c in '",\n') else text


def main():  # noqa: C901
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zip", action="append", required=True, help="local source ZIP; repeat for multiple archives")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offset", type=int, default=0, help="skip this many .milk files per archive")
    parser.add_argument("--limit", type=int, help="convert at most this many .milk files per archive")
    args = parser.parse_args()

    zip_paths = [Path(path).resolve() for path in args.zip]
    for path in zip_paths:
        if not path.is_file() or path.suffix.lower() != ".zip":
            raise SystemExit(f"not a readable ZIP file: {path}")

    data, files = read_index()
    mainline_hashes, mainline_names = build_mainline_hashes(data, files)
    removed_names = read_csv_names(REMOVED_CSV_PATH)
    existing_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    existing_exp_names = {item["displayName"] for item in existing_manifest.get("presets", [])}
    existing_exp_hashes = {
        item["canonicalHash"] for item in existing_manifest.get("presets", [])
    }
    for item in existing_manifest.get("presets", []):
        if "normalizedNameMatches" not in item:
            normalized = item["sourceName"]
            if normalized.startswith(EXP_PREFIX):
                normalized = normalized[len(EXP_PREFIX):]
            match = mainline_names.get(normalized)
            item["normalizedNameMatches"] = [] if not match else [{
                "name": normalized,
                "chunk": match["chunk"],
                "canonicalHash": match["hash"],
            }]
    converted = {}
    source_records = []
    texture_files = []
    collision_records = []
    source_metadata = {}
    texture_images = {}
    texture_records = []

    with tempfile.TemporaryDirectory(prefix="nestdrop-import-") as temp:
        temp_root = Path(temp)
        for archive_number, zip_path in enumerate(zip_paths):
            source_root = temp_root / f"source-{archive_number:02d}"
            milk_count, textures, source_collisions, source_entries = extract_source(
                zip_path, source_root, args.offset, args.limit
            )
            digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            output_path = temp_root / f"converted-{archive_number:02d}.json"
            source_result = run_converter(source_root, output_path)
            source_records.append({
                "archive": zip_path.name, "sha256": digest,
                "milk_files": milk_count, "offset": args.offset,
                "converted": len(source_result),
            })
            texture_files.extend(textures)
            collision_records.extend(source_collisions)
            source_metadata.update({
                entry["runtimeName"]: entry for entry in source_entries
            })
            for name, preset in source_result.items():
                if name in converted:
                    print(f"warning: duplicate source name {name!r}; keeping first", file=sys.stderr)
                    continue
                converted[name] = preset
        texture_images, texture_records, unavailable_textures = build_texture_bundle(texture_files)
    available_textures = BUILTIN_TEXTURES | EXISTING_TEXTURE_NAMES | set(texture_images)
    unavailable_texture_names = {
        item["name"].lower() for item in unavailable_textures
    }

    kept = {}
    skipped = []
    seen_hashes = set(existing_exp_hashes)
    for source_name, preset in sorted(converted.items()):
        normalized = source_name[len(EXP_PREFIX):] if source_name.startswith(EXP_PREFIX) else source_name
        if normalized in removed_names:
            skipped.append({"sourceName": source_name, "reason": "curated-out name"})
            continue
        display = EXP_PREFIX + normalized
        if display in existing_exp_names:
            skipped.append({"sourceName": source_name, "reason": "already imported"})
            continue
        digest = preset_hash(preset)
        if digest in existing_exp_hashes:
            skipped.append({
                "sourceName": source_name,
                "reason": "duplicate experimental content",
            })
            continue
        matches = mainline_hashes.get(digest, [])
        name_matches = []
        if normalized in mainline_names:
            name_matches.append({
                "name": normalized,
                "chunk": mainline_names[normalized]["chunk"],
                "canonicalHash": mainline_names[normalized]["hash"],
            })
        missing = sorted(texture_names(preset) - available_textures)
        if missing:
            unavailable = sorted(set(missing) & unavailable_texture_names)
            skipped.append({
                "sourceName": source_name,
                "reason": "unavailable texture" if unavailable else "missing textures",
                "textures": missing,
                **({"unavailableTextures": unavailable} if unavailable else {}),
            })
            continue
        if digest in seen_hashes:
            skipped.append({
                "sourceName": source_name,
                "reason": "duplicate experimental content",
            })
            continue
        seen_hashes.add(digest)
        kept[display] = {
            "preset": preset, "sourceName": source_name, "displayName": display,
            "canonicalHash": digest, "mainlineMatches": matches,
            "normalizedNameMatches": name_matches, "missingTextures": missing,
            "sourcePath": source_metadata.get(source_name, {}).get(
                "sourcePath", source_name
            ),
        }

    print(f"archives: {len(zip_paths)}")
    print(f"converted: {len(converted)}")
    print(f"retained: {len(kept)}")
    print(f"skipped: {len(skipped)}")
    print(f"exact mainline hash matches: {sum(bool(item['mainlineMatches']) for item in kept.values())}")
    print(
        "retained presets with missing texture references: "
        f"{sum(bool(item['missingTextures']) for item in kept.values())}"
    )

    if args.dry_run:
        return

    manifest = {
        "version": 1,
        "prefix": EXP_PREFIX,
        "physicalChunkBase": PHYSICAL_CHUNK_BASE,
        "sources": [
            source for source in existing_manifest.get("sources", [])
            if source.get("milk_files", 0)
        ] + [source for source in source_records if source.get("milk_files", 0)],
        "presets": existing_manifest.get("presets", []),
        "skipped": existing_manifest.get("skipped", []) + skipped,
        "collisions": existing_manifest.get("collisions", []) + collision_records,
    }
    start_logical = len(data["chunks"])
    existing_physical = [
        int(Path(name).stem.split("-")[-1])
        for name in files if Path(name).stem.split("-")[-1].isdigit()
    ]
    next_physical = max([PHYSICAL_CHUNK_BASE - 1, *existing_physical]) + 1
    names = sorted(kept)
    new_chunks = [names[i:i + PRESETS_PER_CHUNK] for i in range(0, len(names), PRESETS_PER_CHUNK)]
    for offset, chunk_names in enumerate(new_chunks):
        logical = start_logical + offset
        physical = next_physical + offset
        filename = f"chunk-{physical}.js"
        payload = {name: kept[name]["preset"] for name in chunk_names}
        (OUT_DIR / filename).write_text(
            f"window.__bcPresetChunk({logical},{json.dumps(payload, separators=(',', ':'), sort_keys=True)});\n",
            encoding="utf-8",
        )
        data["chunks"].append(chunk_names)
        files.append(filename)
        for name in chunk_names:
            record = dict(kept[name])
            record.update({"logicalChunk": logical, "physicalFile": filename})
            del record["preset"]
            manifest["presets"].append(record)

    data["v"] = max(2, data.get("v", 1))
    data["files"] = files
    INDEX_PATH.write_text(INDEX_PREFIX + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
    with CSV_PATH.open("a", encoding="utf-8") as handle:
        for offset, chunk_names in enumerate(new_chunks):
            logical = start_logical + offset
            for name in chunk_names:
                handle.write(f"{csv_escape(name)},presets-extra,{logical}\n")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_texture_bundle(texture_images, texture_records)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"import failed: {exc}") from exc
