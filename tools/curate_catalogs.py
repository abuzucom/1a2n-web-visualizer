#!/usr/bin/env python3
"""Curate the energy catalog and the performance catalog.

The energy catalog assigns each preset one energy category. The performance
catalog lists the presets curated for performance playback. Both files are
checked in at the repository root, and both have a generated runtime bundle
under src/catalogs/ so the pages can load them as scripts. A catalog entry
names its preset as ``pack:name`` because the same preset name exists in more
than one pack.
"""
import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENERGY_CATALOG_PATH = ROOT / "energy-catalog.json"
PERFORMANCE_CATALOG_PATH = ROOT / "performance-catalog.json"
INVENTORY_PATH = ROOT / "preset-inventory.csv"
ENERGY_BUNDLE_PATH = ROOT / "src" / "catalogs" / "energy-catalog.js"
PERFORMANCE_BUNDLE_PATH = ROOT / "src" / "catalogs" / "performance-catalog.js"
ENERGY_GLOBAL = "BCEnergyCatalog"
PERFORMANCE_GLOBAL = "BCPerformanceCatalog"
CATALOG_VERSION = 1
CATEGORIES = ("low", "medium", "high")
MAIN_PACK = "presets-extra"


PRESET_IO_SPEC = importlib.util.spec_from_file_location(
    "preset_io", Path(__file__).resolve().with_name("preset_io.py"),
)
PRESET_IO = importlib.util.module_from_spec(PRESET_IO_SPEC)
PRESET_IO_SPEC.loader.exec_module(PRESET_IO)
atomic_write_text = PRESET_IO.atomic_write_text


def read_catalog(path, default_presets=None):
    """Read one catalog file and return its payload with the expected shape."""
    empty = {} if default_presets is None else default_presets
    if not path.exists():
        return {"version": CATALOG_VERSION, "presets": empty}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    presets = data.get("presets")
    if presets is None:
        data["presets"] = empty
    elif not isinstance(presets, type(empty)):
        raise ValueError(f"{path.name} needs a presets {type(empty).__name__}")
    return data


def catalog_text(data):
    """Return the catalog file text for one payload."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def bundle_text(global_name, data):
    """Return the script bundle text for one catalog payload."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"window.{global_name} = {payload};\n"


def write_catalog(path, data):
    """Write one catalog file in the repository's JSON style."""
    atomic_write_text(path, catalog_text(data))


def write_bundle(path, global_name, data):
    """Write the script bundle that the pages load for one catalog."""
    atomic_write_text(path, bundle_text(global_name, data))


def load_inventory(path):
    """Return every inventory preset name with the packs that hold it."""
    packs = {}
    if not path.exists():
        return packs
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row.get("name")
            pack = row.get("pack")
            if not name or not pack:
                continue
            packs.setdefault(name, []).append(pack)
    return packs


def catalog_id(pack, name):
    """Return the catalog identifier for one preset."""
    return f"{pack}:{name}"


def id_name(identifier):
    """Return the preset name inside a catalog identifier."""
    _, separator, name = identifier.partition(":")
    return name if separator else identifier


def resolve_identifier(name, inventory):
    """Return the catalog identifier for one preset name.

    The runtime merges the vendored packs before the lazy collection, so a
    name that exists in both plays from the vendored pack. The catalog
    records that pack, so an entry names the preset the app loads.
    """
    packs = inventory.get(name)
    if not packs:
        raise ValueError(f"preset not found in the inventory: {name}")
    vendored = [pack for pack in packs if pack != MAIN_PACK]
    pack = vendored[0] if vendored else MAIN_PACK
    return catalog_id(pack, name)


def resolve_key(key, inventory):
    """Return the catalog identifier for a name or an identifier."""
    if key in inventory:
        return resolve_identifier(key, inventory)
    pack, separator, name = key.partition(":")
    if separator and name in inventory:
        if pack in inventory[name]:
            return catalog_id(pack, name)
        raise ValueError(f"pack {pack} does not hold the preset {name}")
    raise ValueError(f"preset not found in the inventory: {key}")


def read_name_file(path):
    """Return the preset names listed in one file."""
    names = []
    for line in path.read_text(encoding="utf-8-sig").split("\n"):
        name = line.replace("\r", "")
        if name:
            names.append(name)
    return names


def add_to_performance(names, performance, inventory):
    """Add presets to the performance catalog and report each change."""
    entries = performance.setdefault("presets", [])
    changes = []
    for name in names:
        identifier = resolve_identifier(name, inventory)
        if identifier in entries:
            changes.append(f"performance catalog already holds {identifier}")
            continue
        entries.append(identifier)
        changes.append(f"performance catalog += {identifier}")
    return changes


def remove_from_performance(names, performance, inventory):
    """Remove presets from the performance catalog and report each change."""
    entries = performance.get("presets", [])
    changes = []
    dropped = set()
    for name in names:
        identifier = resolve_identifier(name, inventory)
        matching = [entry for entry in entries if id_name(entry) == id_name(identifier)]
        if not matching:
            changes.append(f"performance catalog does not hold {identifier}")
            continue
        dropped.update(matching)
        changes.append(f"performance catalog -= {identifier}")
    if dropped:
        performance["presets"] = [entry for entry in entries if entry not in dropped]
    return changes


def apply_assignments(block_path, energy, inventory):
    """Apply one assignment block to the energy catalog."""
    block = json.loads(block_path.read_text(encoding="utf-8-sig"))
    entries = block.get("presets") if isinstance(block, dict) else None
    if not isinstance(entries, dict):
        raise ValueError("the assignment block needs a presets object")
    assignments = energy.setdefault("presets", {})
    changes = []
    for key, category in entries.items():
        if category not in CATEGORIES:
            raise ValueError(f"unknown energy category {category!r} for {key!r}")
        identifier = resolve_key(key, inventory)
        name = id_name(identifier)
        for existing in list(assignments):
            if existing != identifier and id_name(existing) == name:
                del assignments[existing]
        assignments[identifier] = category
        changes.append(f"energy catalog {identifier} = {category}")
    return changes


def print_catalogs(energy, performance):
    """Print both catalogs."""
    print("performance catalog:")
    for identifier in performance.get("presets", []):
        print(f"  {identifier}")
    print("energy catalog:")
    for identifier, category in sorted(energy.get("presets", {}).items()):
        print(f"  {identifier} = {category}")


def main(argv=None):
    """Curate the energy catalog and the performance catalog."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print both catalogs")
    parser.add_argument("--add", action="append", default=[], metavar="NAME",
                        help="add a preset to the performance catalog")
    parser.add_argument("--add-names-file", type=Path, metavar="FILE",
                        help="add one preset name per line")
    parser.add_argument("--remove", action="append", default=[], metavar="NAME",
                        help="remove a preset from the performance catalog")
    parser.add_argument("--remove-names-file", type=Path, metavar="FILE",
                        help="remove one preset name per line")
    parser.add_argument("--apply-assignments", type=Path, metavar="BLOCK",
                        help="apply an assignment block to the energy catalog")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the changes without writing")
    args = parser.parse_args(argv)

    inventory = load_inventory(INVENTORY_PATH)
    energy = read_catalog(ENERGY_CATALOG_PATH)
    performance = read_catalog(PERFORMANCE_CATALOG_PATH, [])

    try:
        changes = []
        changes += add_to_performance(args.add, performance, inventory)
        if args.add_names_file:
            changes += add_to_performance(read_name_file(args.add_names_file), performance, inventory)
        changes += remove_from_performance(args.remove, performance, inventory)
        if args.remove_names_file:
            changes += remove_from_performance(read_name_file(args.remove_names_file), performance, inventory)
        if args.apply_assignments:
            changes += apply_assignments(args.apply_assignments, energy, inventory)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.list:
        print_catalogs(energy, performance)
    for change in changes:
        print(change)
    if not changes:
        print("no catalog changes")
    if args.dry_run:
        print("dry run: no files written")
        return 0
    write_catalog(ENERGY_CATALOG_PATH, energy)
    write_catalog(PERFORMANCE_CATALOG_PATH, performance)
    write_bundle(ENERGY_BUNDLE_PATH, ENERGY_GLOBAL, energy)
    write_bundle(PERFORMANCE_BUNDLE_PATH, PERFORMANCE_GLOBAL, performance)
    return 0


if __name__ == "__main__":
    sys.exit(main())
