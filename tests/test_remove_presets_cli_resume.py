"""Removal tool regressions: argument handling, a re-run after a partial
write, and error messages that name the physical chunk file."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "remove_presets.js"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

INDEX_PREFIX = "window.BCExtraPresetIndex="
INDEX_DATA = {"v": 2, "chunks": [["Alpha", "Beta"], ["Gamma"]], "files": ["chunk-000.js", "chunk-9000.js"]}
INVENTORY_TEXT = "name,pack,chunk\nAlpha,presets-extra,0\nBeta,presets-extra,0\nGamma,presets-extra,1\n"
LEDGER_HEADER = "name,pack,chunk,commit,date,subject\n"


def chunk_text(logical_id, presets):
    """Return chunk file text for one logical chunk."""
    return f"window.__bcPresetChunk({logical_id},{json.dumps(presets, separators=(',', ':'))});"


class RemovePresetsCliResumeTest(unittest.TestCase):
    """Run the removal tool against a fixture tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tools").mkdir()
        (self.root / "src" / "presets-extra").mkdir(parents=True)
        shutil.copy(TOOL_PATH, self.root / "tools" / "remove_presets.js")
        self.write("src/presets-extra/index.js", INDEX_PREFIX + json.dumps(INDEX_DATA, separators=(",", ":")) + ";")
        self.write("src/presets-extra/chunk-000.js", chunk_text(0, {"Alpha": {"a": 1}, "Beta": {"b": 2}}))
        self.write("src/presets-extra/chunk-9000.js", chunk_text(1, {"Gamma": {"g": 3}}))
        self.write("preset-inventory.csv", INVENTORY_TEXT)
        self.write("removed-presets.csv", LEDGER_HEADER)
        self.write("names.txt", "Alpha\n")

    def write(self, relative, text):
        """Write one fixture file."""
        (self.root / relative).write_text(text, encoding="utf-8")

    def read(self, relative):
        """Read one fixture file."""
        return (self.root / relative).read_text(encoding="utf-8")

    def read_index(self):
        """Return the parsed fixture index payload."""
        return json.loads(self.read("src/presets-extra/index.js")[len(INDEX_PREFIX):].rstrip(";"))

    def run_tool(self, *arguments):
        """Run the removal tool and return its completed process."""
        return subprocess.run(
            ["node", str(self.root / "tools" / "remove_presets.js"), *arguments],
            capture_output=True, text=True, check=False, cwd=self.root,
        )

    def test_unknown_argument_warns_and_continues(self):
        result = self.run_tool("--names-file", "names.txt", "--dry-run", "--dryrun")

        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)
        self.assertIn("--dryrun", result.stderr)
        self.assertIn("Dry run", result.stdout)
        self.assertEqual(self.read_index(), INDEX_DATA)

    def test_name_without_value_exits_with_error(self):
        result = self.run_tool("--name")

        self.assertEqual(result.returncode, EXIT_FAILURE)
        self.assertIn("--name requires a value", result.stderr)
        self.assertEqual(self.read_index(), INDEX_DATA)

    def test_names_file_without_value_exits_with_error(self):
        result = self.run_tool("--names-file")

        self.assertEqual(result.returncode, EXIT_FAILURE)
        self.assertIn("--names-file requires a value", result.stderr)
        self.assertEqual(self.read_index(), INDEX_DATA)

    def test_rerun_completes_after_chunk_was_written(self):
        # A failed run recorded the ledger row and rewrote the chunk file,
        # then stopped before index.js and the inventory.
        self.write("src/presets-extra/chunk-000.js", chunk_text(0, {"Beta": {"b": 2}}))
        self.write("removed-presets.csv", LEDGER_HEADER + "Alpha,presets-extra,0,,2026-11-13,\n")

        result = self.run_tool("--names-file", "names.txt")

        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)
        self.assertEqual(self.read_index()["chunks"], [["Beta"], ["Gamma"]])
        self.assertNotIn("Alpha,", self.read("preset-inventory.csv"))
        self.assertEqual(self.read("removed-presets.csv").count("Alpha,"), 1)

    def test_missing_chunk_key_names_the_physical_file(self):
        self.write("src/presets-extra/chunk-9000.js", chunk_text(1, {}))
        self.write("names.txt", "Gamma\n")

        result = self.run_tool("--names-file", "names.txt")

        self.assertEqual(result.returncode, EXIT_FAILURE)
        self.assertIn("chunk-9000.js", result.stderr)
        self.assertEqual(self.read_index(), INDEX_DATA)

    def test_names_file_outside_the_repository_warns_and_continues(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        names_path = Path(outside.name) / "names.txt"
        names_path.write_text("Alpha\n", encoding="utf-8")

        result = self.run_tool("--names-file", str(names_path), "--dry-run")

        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)
        self.assertIn("outside the repository", result.stderr)
        self.assertIn("Dry run", result.stdout)
        self.assertEqual(self.read_index(), INDEX_DATA)

    def test_symlinked_names_file_outside_the_repository_warns(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = Path(outside.name) / "names.txt"
        target.write_text("Alpha\n", encoding="utf-8")
        (self.root / "linked-names.txt").symlink_to(target)

        result = self.run_tool("--names-file", "linked-names.txt", "--dry-run")

        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)
        self.assertIn("outside the repository", result.stderr)
        self.assertIn("Dry run", result.stdout)

    def test_names_file_inside_the_repository_does_not_warn(self):
        result = self.run_tool("--names-file", "names.txt", "--dry-run")

        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)
        self.assertNotIn("outside the repository", result.stderr)

    def test_unindexed_unrecorded_name_aborts_before_the_ledger(self):
        # A presets-extra row with no chunk that neither the index nor the
        # ledger records must stop the run. No ledger row with an empty
        # chunk may reach removed-presets.csv.
        self.write("preset-inventory.csv", INVENTORY_TEXT + "Delta,presets-extra,\n")
        self.write("names.txt", "Delta\n")

        result = self.run_tool("--names-file", "names.txt")

        self.assertEqual(result.returncode, EXIT_FAILURE)
        self.assertIn('"Delta" not found in index.js', result.stderr)
        self.assertEqual(self.read("removed-presets.csv"), LEDGER_HEADER)
        self.assertEqual(self.read_index(), INDEX_DATA)


if __name__ == "__main__":
    unittest.main()
