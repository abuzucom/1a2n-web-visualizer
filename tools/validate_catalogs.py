#!/usr/bin/env python3
"""Validate the energy catalog and the performance catalog.

The checks cover the catalog contract: the energy vocabulary is limited to
low, medium and high, every catalog entry names a preset that exists, a
preset carries at most one energy category, and the runtime bundles match
the catalogs they were built from.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATION_PATH = Path(__file__).resolve().with_name("curate_catalogs.py")
SPEC = importlib.util.spec_from_file_location("curate_catalogs", CURATION_PATH)
CURATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CURATE)

CATEGORIES = CURATE.CATEGORIES
ENERGY_CATALOG_PATH = CURATE.ENERGY_CATALOG_PATH
PERFORMANCE_CATALOG_PATH = CURATE.PERFORMANCE_CATALOG_PATH
ENERGY_BUNDLE_PATH = CURATE.ENERGY_BUNDLE_PATH
PERFORMANCE_BUNDLE_PATH = CURATE.PERFORMANCE_BUNDLE_PATH
ENERGY_GLOBAL = CURATE.ENERGY_GLOBAL
PERFORMANCE_GLOBAL = CURATE.PERFORMANCE_GLOBAL
bundle_text = CURATE.bundle_text
id_name = CURATE.id_name
load_inventory = CURATE.load_inventory
read_catalog = CURATE.read_catalog


def check_categories(assignments, findings):
    """Return the findings for the energy vocabulary and one category rule."""
    for identifier, category in assignments.items():
        if category not in CATEGORIES:
            findings.append(f"energy catalog {identifier} has unknown category {category!r}")
    by_name = {}
    for identifier, category in assignments.items():
        name = id_name(identifier)
        if by_name.setdefault(name, category) != category:
            findings.append(f"energy catalog gives {name} more than one category")


def check_resolvable(identifier, inventory, findings, label):
    """Return the findings for one catalog entry that names no preset."""
    if ":" not in identifier:
        findings.append(f"{label} {identifier} does not name a pack")
        return
    pack, _, name = identifier.partition(":")
    packs = inventory.get(name)
    if not packs:
        findings.append(f"{label} {identifier} names no known preset")
        return
    if pack not in packs:
        findings.append(f"{label} {identifier} names pack {pack}, which does not hold that preset")


def check_energy(energy, inventory, findings):
    """Return the findings for the energy catalog."""
    assignments = energy.get("presets")
    if not isinstance(assignments, dict):
        findings.append("energy catalog needs a presets object")
        return
    check_categories(assignments, findings)
    for identifier in assignments:
        check_resolvable(identifier, inventory, findings, "energy catalog")


def check_performance(performance, inventory, findings):
    """Return the findings for the performance catalog."""
    entries = performance.get("presets")
    if not isinstance(entries, list):
        findings.append("performance catalog needs a presets list")
        return
    seen = set()
    for identifier in entries:
        if identifier in seen:
            findings.append(f"performance catalog lists {identifier} twice")
        seen.add(identifier)
        check_resolvable(identifier, inventory, findings, "performance catalog")


def check_bundle(path, global_name, data, findings):
    """Return the findings for a runtime bundle that drifted from its catalog."""
    if not path.exists():
        findings.append(f"missing runtime bundle {path.name}")
        return
    if path.read_text(encoding="utf-8") != bundle_text(global_name, data):
        findings.append(f"runtime bundle {path.name} does not match its catalog")


def main(argv=None):
    """Validate both catalogs and their runtime bundles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    findings = []
    inventory = load_inventory(ROOT / "preset-inventory.csv")
    energy = read_catalog(ENERGY_CATALOG_PATH)
    performance = read_catalog(PERFORMANCE_CATALOG_PATH, [])
    check_energy(energy, inventory, findings)
    check_performance(performance, inventory, findings)
    check_bundle(ENERGY_BUNDLE_PATH, ENERGY_GLOBAL, energy, findings)
    check_bundle(PERFORMANCE_BUNDLE_PATH, PERFORMANCE_GLOBAL, performance, findings)

    if findings:
        for finding in findings:
            print(f"error: {finding}", file=sys.stderr)
        return 1
    print("catalogs valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
