#!/usr/bin/env python3
"""Import supplied NestDrop MilkDrop archives as experimental presets.

Read only .milk files and files under a top-level Textures/ directory from
the supplied ZIPs. Never execute or extract unrelated archive
members. Skip DDS-dependent presets because browsers cannot load DDS
textures through the image bundle. Append deterministic ``[variant N]``
suffixes to duplicate basenames when their converted content differs.
Retain identical converted content once. Prefix experimental runtime names
with the reserved ``[EXP] `` string by default; pass ``--exp-prefix`` to use
a different one for a batch that should stay visually distinct from prior
imports during curation (e.g. ``[EXP2] ``).

Usage:
    python3 tools/import-nestdrop-presets.py --zip PACK.zip --dry-run
    python3 tools/import-nestdrop-presets.py --zip PACK1.zip --zip PACK2.zip
    python3 tools/import-nestdrop-presets.py --zip PACK.zip --offset 3000 --limit 1000
    python3 tools/import-nestdrop-presets.py --zip PACK.zip --exp-prefix "[EXP2] "

Logical chunk IDs remain contiguous in index.js. Experimental physical files
start at chunk-9000.js and are recorded in index.js's optional ``files`` map.
Never use 9000+ as a logical chunk ID.
"""

import argparse
import base64
import csv
import hashlib
import importlib.util
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
CONVERTER = ROOT / "tools" / "convert-milk-presets.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXP_PREFIX = "[EXP] "
PHYSICAL_CHUNK_BASE = 9000
PRESETS_PER_CHUNK = 128
# index.js format 2 adds the "files" map that experimental chunks need.
MIN_INDEX_FORMAT_VERSION = 2

PRESET_IO_SPEC = importlib.util.spec_from_file_location(
    "preset_io", Path(__file__).resolve().with_name("preset_io.py"),
)
PRESET_IO = importlib.util.module_from_spec(PRESET_IO_SPEC)
PRESET_IO_SPEC.loader.exec_module(PRESET_IO)
atomic_write_text = PRESET_IO.atomic_write_text
canonicalize = PRESET_IO.canonicalize
preset_hash = PRESET_IO.preset_hash

BUILTIN_TEXTURES = {
    "main", "blur1", "blur2", "blur3", "noise_lq", "noise_lq_lite",
    "noise_mq", "noise_hq", "noisevol_lq", "noisevol_hq",
}
SAMPLER_RE = re.compile(r"\bsampler_([A-Za-z0-9_]+)")
FILTER_PREFIX_RE = re.compile(r"^(?:fw|fc|pw|pc)_")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".dds"}
MAX_ZIP_ENTRIES = 50_000
MAX_ZIP_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_MEMBER_BYTES = 10 * 1024 * 1024
# ZIP archives made on Unix store st_mode in the high 16 bits of
# external_attr. The file-type bits identify symlink members.
ZIP_UNIX_MODE_SHIFT = 16
ZIP_FILE_TYPE_MASK = 0o170000
ZIP_SYMLINK_MODE = 0o120000
# Every JPEG segment marker starts with this byte.
JPEG_MARKER_PREFIX = 0xFF
EXISTING_TEXTURE_NAMES = {
    "cells", "cloudsImage", "lichen", "prayerwheel", "seaweed",
    "smalltiled_lizard_scales",
}
DUPLICATE_CONTENT_REASON = "duplicate experimental content"
# Re-running over the same archive reproduces these records. The key fields
# identify a record that the manifest already holds.
SKIP_RECORD_KEY = ("sourceName", "reason")
COLLISION_RECORD_KEY = ("sourcePath", "runtimeName")


def read_csv_names(path):
    """Read and return a set of preset names from the provided CSV file."""
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["name"] for row in csv.DictReader(handle)}


def read_index():
    """Read and return the index data and file list from index.js."""
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
    """Read and return the presets from the specified experimental chunk file."""
    path = OUT_DIR / filename
    text = path.read_text(encoding="utf-8").strip()
    prefix = f"window.__bcPresetChunk({cid},"
    if not text.startswith(prefix) or not text.endswith(");"):
        raise ValueError(f"unexpected chunk wrapper in {path}")
    return json.loads(text[len(prefix):-2])


def format_chunk_text(cid, payload):
    """Return the chunk file text for one logical chunk."""
    return f"window.__bcPresetChunk({cid},{json.dumps(payload, separators=(',', ':'), sort_keys=True)});\n"


def normalize_equation_fields(preset):
    """Ensure optional equation fields are defined for Butterchurn's compiler."""
    changed = False
    for field in ("init_eqs_str", "frame_eqs_str", "pixel_eqs_str"):
        if field not in preset:
            preset[field] = ""
            changed = True
    for item in preset.get("shapes", []):
        for field in ("init_eqs_str", "frame_eqs_str"):
            if field not in item:
                item[field] = ""
                changed = True
    for item in preset.get("waves", []):
        for field in ("init_eqs_str", "frame_eqs_str", "point_eqs_str"):
            if field not in item:
                item[field] = ""
                changed = True
    return changed


def normalize_experimental_chunks(data, files):
    """Normalize existing EXP chunks and return their changed file payloads."""
    changed = {}
    for cid, filename in enumerate(files):
        if not filename.startswith("chunk-9"):
            continue
        path = OUT_DIR / filename
        chunk = read_chunk(cid, filename)
        chunk_changed = False
        for preset in chunk.values():
            chunk_changed = normalize_equation_fields(preset) or chunk_changed
        if chunk_changed:
            changed[cid] = (path, chunk)
    return changed


def build_mainline_hashes(data, files):
    """Compute and return the set of SHA-256 hashes for all mainline presets."""
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
    """Return a safe destination path for a ZIP archive member."""
    normalized = member_name.replace("\\", "/")
    member_path = PurePosixPath(normalized)
    parts = member_path.parts
    if not parts or member_path.is_absolute() or ".." in parts:
        raise ValueError(f"unsafe ZIP member path: {member_name}")
    return root.joinpath(*parts)


def check_archive_limits(infos):
    """Reject an archive with too many entries or too many uncompressed bytes."""
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ValueError(f"ZIP contains more than {MAX_ZIP_ENTRIES} entries")
    if sum(info.file_size for info in infos) > MAX_ZIP_UNCOMPRESSED_BYTES:
        raise ValueError("ZIP exceeds the uncompressed-size limit")


def count_milk_stems(infos):
    """Return how many .milk members share each basename stem."""
    counts = {}
    for info in infos:
        if not info.is_dir() and info.filename.lower().endswith(".milk"):
            stem = PurePosixPath(info.filename).stem
            counts[stem] = counts.get(stem, 0) + 1
    return counts


def check_member_safety(info):
    """Reject an oversized member or a symlink member."""
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"ZIP member exceeds {MAX_MEMBER_BYTES} byte limit: {info.filename}")
    mode = (info.external_attr >> ZIP_UNIX_MODE_SHIFT) & ZIP_FILE_TYPE_MASK
    if mode == ZIP_SYMLINK_MODE:
        raise ValueError(f"ZIP symlink is not allowed: {info.filename}")


def classify_member(info):
    """Return whether a member is a .milk preset and whether it is a texture."""
    lower = info.filename.replace("\\", "/").lower()
    is_milk = lower.endswith(".milk")
    in_textures = lower.startswith("textures/") or "/textures/" in lower
    is_texture = in_textures and Path(lower).suffix in IMAGE_SUFFIXES
    return is_milk, is_texture


class MilkSelector:
    """Assign runtime names to .milk members and apply --offset and --limit."""

    def __init__(self, collision_counts, offset, max_milk):
        self.collision_counts = collision_counts
        self.offset_remaining = offset
        self.max_milk = max_milk
        self.seen = {}
        self.source_entries = []
        self.collision_records = []

    def select(self, info):
        """Return the runtime stem of a selected member, or None for a skipped one."""
        stem = PurePosixPath(info.filename).stem
        ordinal = self.seen.get(stem, 0) + 1
        self.seen[stem] = ordinal
        is_variant = self.collision_counts[stem] > 1 and ordinal > 1
        runtime_stem = f"{stem} [variant {ordinal}]" if is_variant else stem
        if self.offset_remaining > 0:
            self.offset_remaining -= 1
            return None
        if self.max_milk is not None and len(self.source_entries) >= self.max_milk:
            return None
        entry = {"sourcePath": info.filename, "originalName": stem, "runtimeName": runtime_stem}
        self.source_entries.append(entry)
        if is_variant:
            self.collision_records.append({**entry, "variant": ordinal})
        return runtime_stem


def member_destination(destination, info, runtime_stem):
    """Return the extraction path of a member, renamed for a variant preset."""
    path = safe_member_path(destination, info.filename)
    if runtime_stem is None or runtime_stem == PurePosixPath(info.filename).stem:
        return path
    return path.with_name(runtime_stem + path.suffix)


def write_member(archive, info, path):
    """Write one archive member to its extraction path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(archive.read(info))


def extract_source(zip_path, destination, offset=0, max_milk=None):
    """Extract authorized preset files from the ZIP archive and return their paths."""
    texture_files = []
    with ZipFile(zip_path) as archive:
        infos = archive.infolist()
        check_archive_limits(infos)
        selector = MilkSelector(count_milk_stems(infos), offset, max_milk)
        for info in infos:
            if info.is_dir():
                continue
            check_member_safety(info)
            is_milk, is_texture = classify_member(info)
            if not is_milk and not is_texture:
                continue
            runtime_stem = selector.select(info) if is_milk else None
            if is_milk and runtime_stem is None:
                continue
            path = member_destination(destination, info, runtime_stem)
            write_member(archive, info, path)
            if not is_milk:
                texture_files.append(path)
    return len(selector.source_entries), texture_files, selector.collision_records, selector.source_entries


def run_converter(source_root, output_path):
    """Run the Node.js MilkDrop to JSON converter on the provided directory."""
    with output_path.open("wb") as output:
        subprocess.run(
            ["node", str(CONVERTER), "--dir", str(source_root)],
            cwd=ROOT, stdout=output, check=True,
        )
    return json.loads(output_path.read_text(encoding="utf-8"))


def image_dimensions(data, suffix):
    """Read and return the width and height of an image file."""
    if suffix in {".png"} and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if suffix in {".gif"} and data[:6] in (b"GIF87a", b"GIF89a"):
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if suffix == ".bmp" and data[:2] == b"BM":
        return int.from_bytes(data[18:22], "little"), abs(int.from_bytes(data[22:26], "little", signed=True))
    if suffix in {".jpg", ".jpeg"} and data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 9 < len(data):
            if data[pos] != JPEG_MARKER_PREFIX:
                pos += 1
                continue
            marker = data[pos + 1]
            pos += 2
            if marker in (0xD8, 0xD9):
                continue
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
    """Return a set of texture filenames referenced in the given preset."""
    refs = set()
    for field in ("warp", "comp"):
        shader = preset.get(field, "")
        if isinstance(shader, str):
            for match in SAMPLER_RE.finditer(shader):
                refs.add(FILTER_PREFIX_RE.sub("", match.group(1)).lower())
    return refs - BUILTIN_TEXTURES


def compute_available_textures(texture_images, previously_vendored):
    """Return the case-insensitive set of texture names presets may use.

    texture_names() always lowercases sampler references, so every source
    here is lowercased too; EXISTING_TEXTURE_NAMES otherwise keeps its
    original mixed case (e.g. "cloudsImage") and would never match.
    previously_vendored covers textures already shipped by prior import
    batches, which texture_images (this run's own batch) does not include.
    """
    return (
        BUILTIN_TEXTURES
        | {name.lower() for name in EXISTING_TEXTURE_NAMES}
        | {name.lower() for name in previously_vendored}
        | {name.lower() for name in texture_images}
    )


def build_texture_bundle(texture_files):
    """Pack and write authorized textures into a JSON payload."""
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
    """Merge this batch's textures into the vendored bundle and manifest.

    A batch's Textures/ folder rarely carries every texture already vendored
    from prior imports, so the new images and manifest records are merged
    with what is already on disk rather than replacing it outright; without
    the merge, splitter.write_parts would treat this batch's images as the
    complete set and delete every previously vendored texture part.
    """
    splitter = load_texture_splitter()
    merged_images = {**splitter.read_images(), **images}
    splitter.write_parts(merged_images, dry_run=False)
    existing_records = (
        json.loads(TEXTURE_MANIFEST_PATH.read_text(encoding="utf-8"))
        if TEXTURE_MANIFEST_PATH.exists() else []
    )
    records_by_name = {record["name"]: record for record in existing_records}
    for record in records:
        records_by_name[record["name"]] = record
    merged_records = [records_by_name[name] for name in sorted(records_by_name)]
    atomic_write_text(TEXTURE_MANIFEST_PATH, json.dumps(merged_records, indent=2) + "\n")


def load_texture_splitter():
    """Load tools/split-extra-images.py as a module (hyphenated filename)."""
    path = ROOT / "tools" / "split-extra-images.py"
    spec = importlib.util.spec_from_file_location("split_extra_images", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def csv_escape(value):
    """Escape a string for safe inclusion in a CSV file."""
    text = str(value)
    return f'"{text.replace(chr(34), chr(34) * 2)}"' if any(csv_char in text for csv_char in '",\n') else text


def append_new_records(existing, new, key_fields):
    """Return the existing records plus each new record whose key is absent.

    Existing records stay unchanged and in order. A re-run over the same
    archive reproduces its skip and collision records, and the key fields
    keep those copies out of the manifest.
    """
    seen = {tuple(record.get(field) for field in key_fields) for record in existing}
    merged = list(existing)
    for record in new:
        key = tuple(record.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        merged.append(record)
    return merged


def strip_exp_prefix(name):
    """Return a source name without the reserved experimental prefix."""
    return name[len(EXP_PREFIX):] if name.startswith(EXP_PREFIX) else name


def build_name_match(name, match):
    """Return the manifest record of a mainline preset with the same name."""
    return {"name": name, "chunk": match["chunk"], "canonicalHash": match["hash"]}


def parse_arguments():
    """Parse and validate the command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zip", action="append", help="local source ZIP; repeat for multiple archives")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--normalize-existing", action="store_true",
        help="repair equation fields in already imported EXP chunks without importing archives",
    )
    parser.add_argument("--offset", type=int, default=0, help="skip this many .milk files per archive")
    parser.add_argument("--limit", type=int, help="convert at most this many .milk files per archive")
    parser.add_argument(
        "--exp-prefix", default=EXP_PREFIX,
        help="display-name prefix for presets imported by this run (default: %(default)r); "
             "lets a distinct batch stay visually identifiable during curation",
    )
    args = parser.parse_args()
    if not args.zip and not args.normalize_existing:
        parser.error("provide --zip or --normalize-existing")
    return args


def validate_zip_paths(zip_arguments):
    """Resolve the --zip arguments and reject anything but readable ZIP files."""
    zip_paths = [Path(path).resolve() for path in (zip_arguments or [])]
    for path in zip_paths:
        if not path.is_file() or path.suffix.lower() != ".zip":
            raise SystemExit(f"not a readable ZIP file: {path}")
    return zip_paths


def refresh_manifest_locations(data, files, manifest_by_name):
    """Record the current chunk location of every indexed experimental preset."""
    for cid, names in enumerate(data["chunks"]):
        if not files[cid].startswith("chunk-9"):
            continue
        for name in names:
            if name in manifest_by_name:
                manifest_by_name[name].update({"logicalChunk": cid, "physicalFile": files[cid]})


def backfill_name_matches(manifest_presets, mainline_names):
    """Add normalizedNameMatches to manifest records that predate the field."""
    for item in manifest_presets:
        if "normalizedNameMatches" in item:
            continue
        normalized = strip_exp_prefix(item["sourceName"])
        match = mainline_names.get(normalized)
        item["normalizedNameMatches"] = [build_name_match(normalized, match)] if match else []


def load_existing_manifest(data, files, mainline_names):
    """Read the experimental manifest and refresh its derived fields."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    presets = manifest.get("presets", [])
    refresh_manifest_locations(data, files, {item["displayName"]: item for item in presets})
    backfill_name_matches(presets, mainline_names)
    return manifest


def convert_archive(zip_path, temp_root, archive_number, offset, limit):
    """Extract and convert one archive and return its source record and presets."""
    source_root = temp_root / f"source-{archive_number:02d}"
    milk_count, textures, collisions, entries = extract_source(zip_path, source_root, offset, limit)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    presets = run_converter(source_root, temp_root / f"converted-{archive_number:02d}.json")
    record = {
        "archive": zip_path.name, "sha256": digest,
        "milk_files": milk_count, "offset": offset,
        "converted": len(presets),
    }
    return {"record": record, "textures": textures, "collisions": collisions, "entries": entries, "presets": presets}


def merge_converted(converted, presets):
    """Add one archive's presets and keep the first preset of a repeated name."""
    for name, preset in presets.items():
        if name in converted:
            print(f"warning: duplicate source name {name!r}; keeping first", file=sys.stderr)
            continue
        converted[name] = preset


def convert_archives(zip_paths, offset, limit):
    """Convert every archive and pack its textures into one import batch."""
    batch = {"converted": {}, "sources": [], "collisions": [], "metadata": {}}
    texture_files = []
    with tempfile.TemporaryDirectory(prefix="nestdrop-import-") as temp:
        temp_root = Path(temp)
        for archive_number, zip_path in enumerate(zip_paths):
            result = convert_archive(zip_path, temp_root, archive_number, offset, limit)
            batch["sources"].append(result["record"])
            texture_files.extend(result["textures"])
            batch["collisions"].extend(result["collisions"])
            batch["metadata"].update({entry["runtimeName"]: entry for entry in result["entries"]})
            merge_converted(batch["converted"], result["presets"])
        images, records, unavailable = build_texture_bundle(texture_files)
    batch.update({"texture_images": images, "texture_records": records, "unavailable_textures": unavailable})
    return batch


def build_selection_context(existing_manifest, indexed_chunks, batch, zip_paths):
    """Collect the names, hashes, and textures that decide which presets stay."""
    presets = existing_manifest.get("presets", [])
    previously_vendored = load_texture_splitter().read_images() if zip_paths else {}
    # An import that stopped after the index write but before the manifest
    # write left indexed names without manifest records. A name in the index
    # counts as imported, so a re-run never indexes it twice.
    indexed_names = {name for names in indexed_chunks for name in names}
    return {
        "removed_names": read_csv_names(REMOVED_CSV_PATH),
        "existing_names": {item["displayName"] for item in presets} | indexed_names,
        "existing_hashes": {item["canonicalHash"] for item in presets},
        "seen_hashes": {item["canonicalHash"] for item in presets},
        "available_textures": compute_available_textures(batch["texture_images"], previously_vendored),
        "unavailable_textures": {item["name"].lower() for item in batch["unavailable_textures"]},
        "source_metadata": batch["metadata"],
    }


def build_skip_record(source_name, reason):
    """Return the manifest record of a skipped preset."""
    return {"sourceName": source_name, "reason": reason}


def build_texture_skip_record(source_name, missing, unavailable_names):
    """Return the manifest record of a preset skipped for its textures."""
    unavailable = sorted(set(missing) & unavailable_names)
    record = {
        "sourceName": source_name,
        "reason": "unavailable texture" if unavailable else "missing textures",
        "textures": missing,
    }
    if unavailable:
        record["unavailableTextures"] = unavailable
    return record


def build_kept_record(source_name, normalized, preset, digest, context):
    """Return the import record of a retained preset."""
    mainline_names = context["mainline_names"]
    name_matches = []
    if normalized in mainline_names:
        name_matches.append(build_name_match(normalized, mainline_names[normalized]))
    return {
        "preset": preset, "sourceName": source_name, "displayName": context["exp_prefix"] + normalized,
        "canonicalHash": digest, "mainlineMatches": context["mainline_hashes"].get(digest, []),
        "normalizedNameMatches": name_matches, "missingTextures": [],
        "sourcePath": context["source_metadata"].get(source_name, {}).get("sourcePath", source_name),
    }


def classify_converted_preset(source_name, preset, context):
    """Return (skip record, None) for a skipped preset or (None, kept record)."""
    normalized = strip_exp_prefix(source_name)
    if normalized in context["removed_names"]:
        return build_skip_record(source_name, "curated-out name"), None
    if context["exp_prefix"] + normalized in context["existing_names"]:
        return build_skip_record(source_name, "already imported"), None
    digest = preset_hash(preset)
    if digest in context["existing_hashes"]:
        return build_skip_record(source_name, DUPLICATE_CONTENT_REASON), None
    missing = sorted(texture_names(preset) - context["available_textures"])
    if missing:
        return build_texture_skip_record(source_name, missing, context["unavailable_textures"]), None
    if digest in context["seen_hashes"]:
        return build_skip_record(source_name, DUPLICATE_CONTENT_REASON), None
    context["seen_hashes"].add(digest)
    # Fill absent equation fields before the preset is written. Butterchurn
    # compiles them as "".concat(field, " return a;"), so a missing field
    # becomes the literal "undefined" and raises SyntaxError at load time;
    # visualizer-core's own guards skip non-string values and never catch
    # it. Run after the digest above so dedup keeps comparing the same
    # canonical content earlier imports recorded.
    normalize_equation_fields(preset)
    return None, build_kept_record(source_name, normalized, preset, digest, context)


def select_presets(converted, context):
    """Split converted presets into retained records and skip records."""
    kept = {}
    skipped = []
    for source_name, preset in sorted(converted.items()):
        skip, record = classify_converted_preset(source_name, preset, context)
        if skip is not None:
            skipped.append(skip)
            continue
        kept[record["displayName"]] = record
    return kept, skipped


def prepare_import(args, zip_paths, data, files):
    """Read the existing state, convert the archives, and select presets."""
    mainline_hashes, mainline_names = build_mainline_hashes(data, files)
    existing_manifest = load_existing_manifest(data, files, mainline_names)
    batch = convert_archives(zip_paths, args.offset, args.limit)
    context = build_selection_context(existing_manifest, data["chunks"], batch, zip_paths)
    context.update({
        "exp_prefix": args.exp_prefix,
        "mainline_hashes": mainline_hashes,
        "mainline_names": mainline_names,
    })
    kept, skipped = select_presets(batch["converted"], context)
    return existing_manifest, batch, kept, skipped


def print_summary(archive_count, converted_count, kept, skipped):
    """Print the import counts."""
    print(f"archives: {archive_count}")
    print(f"converted: {converted_count}")
    print(f"retained: {len(kept)}")
    print(f"skipped: {len(skipped)}")
    print(f"exact mainline hash matches: {sum(bool(item['mainlineMatches']) for item in kept.values())}")
    print(
        "retained presets with missing texture references: "
        f"{sum(bool(item['missingTextures']) for item in kept.values())}"
    )


def build_manifest(existing_manifest, exp_prefix, batch, skipped):
    """Return the updated manifest before this run's presets are appended."""
    return {
        "version": 1,
        "prefix": exp_prefix,
        "physicalChunkBase": PHYSICAL_CHUNK_BASE,
        "sources": [
            source for source in existing_manifest.get("sources", [])
            if source.get("milk_files", 0)
        ] + [source for source in batch["sources"] if source.get("milk_files", 0)],
        "presets": existing_manifest.get("presets", []),
        "skipped": append_new_records(existing_manifest.get("skipped", []), skipped, SKIP_RECORD_KEY),
        "collisions": append_new_records(
            existing_manifest.get("collisions", []), batch["collisions"], COLLISION_RECORD_KEY,
        ),
    }


def next_physical_chunk(files):
    """Return the first free physical experimental chunk number."""
    existing_physical = [
        int(Path(name).stem.split("-")[-1])
        for name in files if Path(name).stem.split("-")[-1].isdigit()
    ]
    return max([PHYSICAL_CHUNK_BASE - 1, *existing_physical]) + 1


def build_manifest_record(kept_record, logical, filename):
    """Return the manifest record of a retained preset at its chunk location."""
    record = {key: value for key, value in kept_record.items() if key != "preset"}
    record.update({"logicalChunk": logical, "physicalFile": filename})
    return record


def write_new_chunks(data, files, kept, manifest):
    """Write retained presets to new chunks and return (logical ID, names) pairs."""
    start_logical = len(data["chunks"])
    next_physical = next_physical_chunk(files)
    names = sorted(kept)
    new_chunks = [names[i:i + PRESETS_PER_CHUNK] for i in range(0, len(names), PRESETS_PER_CHUNK)]
    for offset, chunk_names in enumerate(new_chunks):
        logical = start_logical + offset
        filename = f"chunk-{next_physical + offset}.js"
        payload = {name: kept[name]["preset"] for name in chunk_names}
        atomic_write_text(OUT_DIR / filename, format_chunk_text(logical, payload))
        data["chunks"].append(chunk_names)
        files.append(filename)
        manifest["presets"].extend(build_manifest_record(kept[name], logical, filename) for name in chunk_names)
    return [(start_logical + offset, chunk_names) for offset, chunk_names in enumerate(new_chunks)]


def write_index_and_inventory(data, files, new_chunks):
    """Write index.js and append the new presets to the inventory."""
    data["v"] = max(MIN_INDEX_FORMAT_VERSION, data.get("v", 1))
    data["files"] = files
    atomic_write_text(INDEX_PATH, INDEX_PREFIX + json.dumps(data, separators=(",", ":")) + ";\n")
    csv_rows = [
        f"{csv_escape(name)},presets-extra,{logical}\n"
        for logical, chunk_names in new_chunks for name in chunk_names
    ]
    atomic_write_text(CSV_PATH, CSV_PATH.read_text(encoding="utf-8") + "".join(csv_rows))


def write_presets(data, files, kept, manifest, normalized_chunks):
    """Write new chunks, normalized chunks, the index, and the inventory."""
    new_chunks = write_new_chunks(data, files, kept, manifest)
    for cid, (path, chunk) in normalized_chunks.items():
        atomic_write_text(path, format_chunk_text(cid, chunk))
    write_index_and_inventory(data, files, new_chunks)


def main():
    """Import and normalize NestDrop presets into the experimental collection."""
    args = parse_arguments()
    zip_paths = validate_zip_paths(args.zip)
    data, files = read_index()
    normalized_chunks = normalize_experimental_chunks(data, files)
    existing_manifest, batch, kept, skipped = prepare_import(args, zip_paths, data, files)
    print_summary(len(zip_paths), len(batch["converted"]), kept, skipped)
    if args.dry_run:
        return

    # Textures go first. A texture failure then leaves no preset indexed
    # without the textures it samples. The manifest goes last.
    if zip_paths:
        write_texture_bundle(batch["texture_images"], batch["texture_records"])
    manifest = build_manifest(existing_manifest, args.exp_prefix, batch, skipped)
    write_presets(data, files, kept, manifest, normalized_chunks)
    atomic_write_text(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"import failed: {exc}") from exc
