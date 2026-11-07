"""Removal tool regressions: the catalog cleanup that follows a preset
removal, and the dry-run report that names those changes."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "remove_presets.js"

INDEX_TEXT = 'window.BCExtraPresetIndex={"v":2,"chunks":[["Alpha","Beta"],["Gamma"]],"files":["chunk-000.js","chunk-001.js"]};'
CHUNK_ZERO = 'window.__bcPresetChunk(0,{"Alpha":{"a":1},"Beta":{"b":2}});'
CHUNK_ONE = 'window.__bcPresetChunk(1,{"Gamma":{"g":3}});'
INVENTORY_TEXT = "name,pack,chunk\nAlpha,presets-extra,0\nBeta,presets-extra,0\nGamma,presets-extra,1\n"
LEDGER_TEXT = "name,pack,chunk,commit,date,subject\n"
ENERGY_TEXT = json.dumps(
    {"version": 1, "presets": {"presets-extra:Alpha": "low", "presets-extra:Beta": "high"}},
    indent=2,
) + "\n"
PERFORMANCE_TEXT = json.dumps(
    {"version": 1, "presets": ["presets-extra:Alpha", "presets-extra:Gamma"]},
    indent=2,
) + "\n"
ENERGY_BUNDLE = ('window.BCEnergyCatalog = {"version":1,"presets":'
                  '{"presets-extra:Alpha":"low","presets-extra:Beta":"high"}};\n')
PERFORMANCE_BUNDLE = ('window.BCPerformanceCatalog = {"version":1,"presets":'
                      '["presets-extra:Alpha","presets-extra:Gamma"]};\n')


class RemovePresetsCatalogTest(unittest.TestCase):
    """Run the removal tool against a fixture tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tools").mkdir()
        (self.root / "src" / "presets-extra").mkdir(parents=True)
        (self.root / "src" / "catalogs").mkdir(parents=True)
        shutil.copy(TOOL_PATH, self.root / "tools" / "remove_presets.js")
        self.write("src/presets-extra/index.js", INDEX_TEXT)
        self.write("src/presets-extra/chunk-000.js", CHUNK_ZERO)
        self.write("src/presets-extra/chunk-001.js", CHUNK_ONE)
        self.write("preset-inventory.csv", INVENTORY_TEXT)
        self.write("removed-presets.csv", LEDGER_TEXT)
        self.write("energy-catalog.json", ENERGY_TEXT)
        self.write("performance-catalog.json", PERFORMANCE_TEXT)
        self.write("src/catalogs/energy-catalog.js", ENERGY_BUNDLE)
        self.write("src/catalogs/performance-catalog.js", PERFORMANCE_BUNDLE)
        self.write("names.txt", "Alpha\n")

    def write(self, relative, text):
        """Write one fixture file."""
        (self.root / relative).write_text(text, encoding="utf-8")

    def read(self, relative):
        """Read one fixture file."""
        return (self.root / relative).read_text(encoding="utf-8")

    def run_tool(self, *arguments):
        """Run the removal tool and return its completed process."""
        return subprocess.run(
            ["node", str(self.root / "tools" / "remove_presets.js"), *arguments],
            capture_output=True, text=True, check=False, cwd=self.root,
        )

    def test_the_dry_run_reports_the_catalog_changes_and_writes_nothing(self):
        result = self.run_tool("--names-file", "names.txt", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("energy catalog entries: 1", result.stdout)
        self.assertIn("performance catalog entries: 1", result.stdout)
        self.assertEqual(self.read("energy-catalog.json"), ENERGY_TEXT)
        self.assertEqual(self.read("performance-catalog.json"), PERFORMANCE_TEXT)
        self.assertEqual(self.read("src/catalogs/energy-catalog.js"), ENERGY_BUNDLE)

    def test_a_removal_clears_the_references_from_both_catalogs(self):
        result = self.run_tool("--names-file", "names.txt")

        self.assertEqual(result.returncode, 0, result.stderr)
        energy = json.loads(self.read("energy-catalog.json"))
        performance = json.loads(self.read("performance-catalog.json"))
        self.assertEqual(energy["presets"], {"presets-extra:Beta": "high"})
        self.assertEqual(performance["presets"], ["presets-extra:Gamma"])

    def test_the_runtime_bundles_follow_the_catalogs(self):
        self.assertEqual(self.run_tool("--names-file", "names.txt").returncode, 0)

        energy = json.loads(self.read("energy-catalog.json"))
        performance = json.loads(self.read("performance-catalog.json"))
        self.assertEqual(
            self.read("src/catalogs/energy-catalog.js"),
            "window.BCEnergyCatalog = " + json.dumps(energy, separators=(",", ":")) + ";\n",
        )
        self.assertEqual(
            self.read("src/catalogs/performance-catalog.js"),
            "window.BCPerformanceCatalog = " + json.dumps(performance, separators=(",", ":")) + ";\n",
        )

    def test_the_preset_leaves_the_index_the_chunk_and_the_inventory(self):
        self.assertEqual(self.run_tool("--names-file", "names.txt").returncode, 0)

        self.assertNotIn("Alpha", self.read("src/presets-extra/index.js"))
        self.assertNotIn("Alpha", self.read("src/presets-extra/chunk-000.js"))
        self.assertNotIn("Alpha", self.read("preset-inventory.csv"))
        self.assertIn("Alpha", self.read("removed-presets.csv"))

    def test_the_consistency_check_reports_no_stale_catalog_entries(self):
        result = self.run_tool("--names-file", "names.txt")

        self.assertNotIn("still name a removed preset", result.stdout)
        self.assertNotIn("WARNING", result.stdout)


if __name__ == "__main__":
    unittest.main()
