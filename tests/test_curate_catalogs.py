"""Curation tool regressions: performance membership, energy assignments, and
the runtime bundles that follow the catalogs."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "curate_catalogs.py"
SPEC = importlib.util.spec_from_file_location("curate_catalogs", TOOL_PATH)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

INVENTORY = (
    "name,pack,chunk\n"
    "Alpha,presets-extra,0\n"
    "Beta,presets-extra,1\n"
    "Shared,butterchurnPresetsExtra,\n"
    "Shared,presets-extra,2\n"
)


class CurationToolTest(unittest.TestCase):
    """Exercise the catalog curation tool against a fixture tree."""

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
        self.energy.write_text(json.dumps({"version": 1, "presets": {}}), encoding="utf-8")
        self.performance.write_text(json.dumps({"version": 1, "presets": []}), encoding="utf-8")
        self.patches = [
            patch.object(TOOL, "INVENTORY_PATH", self.inventory),
            patch.object(TOOL, "ENERGY_CATALOG_PATH", self.energy),
            patch.object(TOOL, "PERFORMANCE_CATALOG_PATH", self.performance),
            patch.object(TOOL, "ENERGY_BUNDLE_PATH", self.energy_bundle),
            patch.object(TOOL, "PERFORMANCE_BUNDLE_PATH", self.performance_bundle),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def read_energy(self):
        """Return the energy catalog payload."""
        return json.loads(self.energy.read_text(encoding="utf-8"))

    def read_performance(self):
        """Return the performance catalog payload."""
        return json.loads(self.performance.read_text(encoding="utf-8"))

    def test_adding_a_preset_resolves_its_pack_and_writes_the_bundle(self):
        self.assertEqual(TOOL.main(["--add", "Alpha"]), 0)

        self.assertEqual(self.read_performance()["presets"], ["presets-extra:Alpha"])
        bundle = self.energy_bundle.read_text(encoding="utf-8")
        self.assertTrue(bundle.startswith("window.BCEnergyCatalog = "))
        self.assertTrue(bundle.endswith(";\n"))

    def test_adding_an_unknown_preset_fails_and_changes_nothing(self):
        self.assertEqual(TOOL.main(["--add", "Missing Preset"]), 1)

        self.assertEqual(self.read_performance()["presets"], [])
        self.assertFalse(self.performance_bundle.exists())

    def test_an_assignment_replaces_the_prior_category(self):
        block = self.root / "block.json"
        block.write_text(json.dumps({"presets": {"Alpha": "low"}}), encoding="utf-8")
        self.assertEqual(TOOL.main(["--apply-assignments", str(block)]), 0)
        self.assertEqual(self.read_energy()["presets"]["presets-extra:Alpha"], "low")

        block.write_text(json.dumps({"presets": {"Alpha": "high"}}), encoding="utf-8")
        self.assertEqual(TOOL.main(["--apply-assignments", str(block)]), 0)
        self.assertEqual(self.read_energy()["presets"]["presets-extra:Alpha"], "high")

    def test_an_unknown_category_is_rejected(self):
        block = self.root / "block.json"
        block.write_text(json.dumps({"presets": {"Alpha": "extreme"}}), encoding="utf-8")

        self.assertEqual(TOOL.main(["--apply-assignments", str(block)]), 1)
        self.assertEqual(self.read_energy()["presets"], {})

    def test_an_assignment_for_an_unknown_preset_is_rejected(self):
        block = self.root / "block.json"
        block.write_text(json.dumps({"presets": {"Missing Preset": "low"}}), encoding="utf-8")

        self.assertEqual(TOOL.main(["--apply-assignments", str(block)]), 1)
        self.assertEqual(self.read_energy()["presets"], {})

    def test_removing_a_preset_drops_it_from_the_performance_catalog(self):
        TOOL.main(["--add", "Alpha"])
        TOOL.main(["--add", "Beta"])

        self.assertEqual(TOOL.main(["--remove", "Alpha"]), 0)
        self.assertEqual(self.read_performance()["presets"], ["presets-extra:Beta"])

    def test_two_removals_in_one_run_drop_both_presets(self):
        TOOL.main(["--add", "Alpha"])
        TOOL.main(["--add", "Beta"])

        self.assertEqual(TOOL.main(["--remove", "Alpha", "--remove", "Beta"]), 0)
        self.assertEqual(self.read_performance()["presets"], [])
        bundle = self.performance_bundle.read_text(encoding="utf-8")
        self.assertNotIn("Alpha", bundle)
        self.assertNotIn("Beta", bundle)

    def test_a_preset_in_two_packs_uses_the_pack_the_runtime_plays(self):
        self.assertEqual(TOOL.main(["--add", "Shared"]), 0)

        self.assertEqual(
            self.read_performance()["presets"],
            ["butterchurnPresetsExtra:Shared"],
        )

    def test_an_assignment_replaces_the_category_of_the_same_preset(self):
        first = self.root / "first.json"
        first.write_text(json.dumps({"presets": {"butterchurnPresetsExtra:Shared": "low"}}),
                         encoding="utf-8")
        second = self.root / "second.json"
        second.write_text(json.dumps({"presets": {"presets-extra:Shared": "high"}}),
                          encoding="utf-8")

        self.assertEqual(TOOL.main(["--apply-assignments", str(first)]), 0)
        self.assertEqual(TOOL.main(["--apply-assignments", str(second)]), 0)

        self.assertEqual(
            self.read_energy()["presets"],
            {"presets-extra:Shared": "high"},
        )

    def test_an_assignment_for_a_pack_that_holds_no_preset_is_rejected(self):
        block = self.root / "block.json"
        block.write_text(json.dumps({"presets": {"butterchurnPresets:Alpha": "low"}}),
                         encoding="utf-8")

        self.assertEqual(TOOL.main(["--apply-assignments", str(block)]), 1)
        self.assertEqual(self.read_energy()["presets"], {})

    def test_a_missing_performance_catalog_starts_empty(self):
        self.performance.unlink()

        self.assertEqual(TOOL.main(["--add", "Alpha"]), 0)
        self.assertEqual(self.read_performance()["presets"], ["presets-extra:Alpha"])

    def test_a_dry_run_writes_nothing(self):
        self.assertEqual(TOOL.main(["--add", "Alpha", "--dry-run"]), 0)

        self.assertEqual(self.read_performance()["presets"], [])
        self.assertFalse(self.performance_bundle.exists())

    def test_the_bundle_matches_the_catalog(self):
        TOOL.main(["--add", "Alpha"])

        payload = json.loads(self.performance_bundle.read_text(encoding="utf-8")
                             .split(" = ", 1)[1].rstrip().rstrip(";"))
        self.assertEqual(payload, self.read_performance())


if __name__ == "__main__":
    unittest.main()
