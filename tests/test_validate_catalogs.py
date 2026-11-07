"""Catalog validator regressions: the energy vocabulary, the catalog
identifiers, the one-category rule, and the runtime bundles."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "tools" / "validate_catalogs.py"
SPEC = importlib.util.spec_from_file_location("validate_catalogs", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

INVENTORY = "name,pack,chunk\n" "Alpha,presets-extra,0\n" "Beta,presets-extra,1\n"


class ValidateCatalogsTest(unittest.TestCase):
    """Run the catalog validator against a fixture tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inventory = self.root / "preset-inventory.csv"
        self.inventory.write_text(INVENTORY, encoding="utf-8")
        self.energy = self.root / "energy-catalog.json"
        self.performance = self.root / "performance-catalog.json"
        self.energy_bundle = self.root / "energy-catalog.js"
        self.performance_bundle = self.root / "performance-catalog.js"
        self.patches = [
            patch.object(VALIDATOR, "ROOT", self.root),
            patch.object(VALIDATOR, "ENERGY_CATALOG_PATH", self.energy),
            patch.object(VALIDATOR, "PERFORMANCE_CATALOG_PATH", self.performance),
            patch.object(VALIDATOR, "ENERGY_BUNDLE_PATH", self.energy_bundle),
            patch.object(VALIDATOR, "PERFORMANCE_BUNDLE_PATH", self.performance_bundle),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def write_catalogs(self, energy, performance):
        """Write both catalogs and the bundles that match them."""
        self.energy.write_text(json.dumps(energy, indent=2) + "\n", encoding="utf-8")
        self.performance.write_text(json.dumps(performance, indent=2) + "\n", encoding="utf-8")
        self.energy_bundle.write_text(
            "window.BCEnergyCatalog = " + json.dumps(energy, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )
        self.performance_bundle.write_text(
            "window.BCPerformanceCatalog = " + json.dumps(performance, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )

    def test_valid_catalogs_pass(self):
        self.write_catalogs(
            {"version": 1, "presets": {"presets-extra:Alpha": "low"}},
            {"version": 1, "presets": ["presets-extra:Beta"]},
        )

        self.assertEqual(VALIDATOR.main([]), 0)

    def test_an_unknown_category_fails(self):
        self.write_catalogs(
            {"version": 1, "presets": {"presets-extra:Alpha": "extreme"}},
            {"version": 1, "presets": []},
        )

        self.assertEqual(VALIDATOR.main([]), 1)

    def test_an_identifier_that_names_no_preset_fails(self):
        self.write_catalogs(
            {"version": 1, "presets": {"presets-extra:Missing": "low"}},
            {"version": 1, "presets": []},
        )

        self.assertEqual(VALIDATOR.main([]), 1)

    def test_a_preset_with_two_categories_fails(self):
        self.write_catalogs(
            {
                "version": 1,
                "presets": {"presets-extra:Alpha": "low", "butterchurnPresets:Alpha": "high"},
            },
            {"version": 1, "presets": []},
        )

        self.assertEqual(VALIDATOR.main([]), 1)

    def test_a_duplicate_performance_entry_fails(self):
        self.write_catalogs(
            {"version": 1, "presets": {}},
            {"version": 1, "presets": ["presets-extra:Alpha", "presets-extra:Alpha"]},
        )

        self.assertEqual(VALIDATOR.main([]), 1)

    def test_a_bundle_that_drifted_from_its_catalog_fails(self):
        self.write_catalogs(
            {"version": 1, "presets": {"presets-extra:Alpha": "low"}},
            {"version": 1, "presets": []},
        )
        self.energy_bundle.write_text("window.BCEnergyCatalog = {};\n", encoding="utf-8")

        self.assertEqual(VALIDATOR.main([]), 1)


if __name__ == "__main__":
    unittest.main()
