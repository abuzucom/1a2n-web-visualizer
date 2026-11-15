"""Experimental removal regressions: the ledger reason field and the
energy and performance catalog entries of removed presets."""
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
TOOL_PATH = TESTS_DIR.parent / "tools" / "remove-experimental-duplicates.py"
SPEC = importlib.util.spec_from_file_location("remove_experimental_duplicates_catalogs", TOOL_PATH)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "remove_experimental_presets_fixture", TESTS_DIR / "test_remove_experimental_presets.py",
)
FIXTURE = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(FIXTURE)

LEDGER_FIELDS = 6
KEPT_ID = "presets-extra:Kept preset"
ENERGY_DATA = {
    "version": 1,
    "presets": {"presets-extra:[EXP] sample": "low", "presets-extra:[EXP2] sample": "high", KEPT_ID: "medium"},
}
PERFORMANCE_DATA = {"version": 1, "presets": ["presets-extra:[EXP3] sample", KEPT_ID]}


class RemoveExperimentalLedgerCatalogTests(unittest.TestCase):
    """Run the experimental removal tool against fixture records."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.paths = FIXTURE.write_fixture_files(self.root)
        (self.root / "src" / "catalogs").mkdir(parents=True)
        self.catalogs = {
            "ENERGY_CATALOG_PATH": self.root / "energy-catalog.json",
            "PERFORMANCE_CATALOG_PATH": self.root / "performance-catalog.json",
            "ENERGY_BUNDLE_PATH": self.root / "src" / "catalogs" / "energy-catalog.js",
            "PERFORMANCE_BUNDLE_PATH": self.root / "src" / "catalogs" / "performance-catalog.js",
        }
        self.catalogs["ENERGY_CATALOG_PATH"].write_text(json.dumps(ENERGY_DATA), encoding="utf-8")
        self.catalogs["PERFORMANCE_CATALOG_PATH"].write_text(json.dumps(PERFORMANCE_DATA), encoding="utf-8")

    def run_tool(self, *arguments):
        """Run main() against the fixture tree and return its exit code."""
        replacements = {
            "OUT_DIR": self.paths["output_dir"],
            "INDEX_PATH": self.paths["output_dir"] / "index.js",
            "CSV_PATH": self.paths["inventory"],
            "REMOVED_CSV_PATH": self.paths["removed"],
            "MANIFEST_PATH": self.paths["manifest"],
            "EXCLUSIONS_PATH": self.paths["exclusions"],
            **self.catalogs,
        }
        argv = [str(TOOL_PATH), "--decisions", str(self.paths["decisions"]), "--allow-unmatched", *arguments]
        with patch.object(sys, "argv", argv):
            for name, value in replacements.items():
                patcher = patch.object(TOOL, name, value, create=True)
                patcher.start()
                self.addCleanup(patcher.stop)
            return TOOL.main()

    def read_json(self, key):
        """Return one parsed catalog file."""
        return json.loads(self.catalogs[key].read_text(encoding="utf-8"))

    def test_ledger_reason_with_a_comma_stays_one_field(self):
        reason = "approved, duplicate of mainline"

        self.assertEqual(self.run_tool("--reason", reason), 0)

        rows = list(csv.reader(self.paths["removed"].read_text(encoding="utf-8").splitlines()))
        self.assertEqual(len(rows), 4)
        for row in rows[1:]:
            self.assertEqual(len(row), LEDGER_FIELDS, row)
            self.assertEqual(row[-1], reason)

    def test_removal_clears_catalog_entries_and_bundles(self):
        self.assertEqual(self.run_tool("--reason", "curation approved"), 0)

        self.assertEqual(self.read_json("ENERGY_CATALOG_PATH")["presets"], {KEPT_ID: "medium"})
        self.assertEqual(self.read_json("PERFORMANCE_CATALOG_PATH")["presets"], [KEPT_ID])
        energy_bundle = self.catalogs["ENERGY_BUNDLE_PATH"].read_text(encoding="utf-8")
        performance_bundle = self.catalogs["PERFORMANCE_BUNDLE_PATH"].read_text(encoding="utf-8")
        self.assertIn("window.BCEnergyCatalog", energy_bundle)
        self.assertNotIn("[EXP", energy_bundle)
        self.assertIn("window.BCPerformanceCatalog", performance_bundle)
        self.assertNotIn("[EXP", performance_bundle)

    def test_dry_run_leaves_the_catalogs_unchanged(self):
        self.assertEqual(self.run_tool("--dry-run"), 0)

        self.assertEqual(self.read_json("ENERGY_CATALOG_PATH"), ENERGY_DATA)
        self.assertEqual(self.read_json("PERFORMANCE_CATALOG_PATH"), PERFORMANCE_DATA)


if __name__ == "__main__":
    unittest.main()
