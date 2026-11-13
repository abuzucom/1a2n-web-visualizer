"""Preset validator regressions: the exit status that CI gates on, and an
index without the physical `files` map."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("validate-experimental-presets.js", "validate-preset-chunks.js", "convert-milk-presets.js")
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

VALID_PRESET = {"init_eqs_str": "", "frame_eqs_str": "a['zoom'] = 1;", "shapes": [], "waves": []}
INVALID_PRESET = {"init_eqs_str": "", "frame_eqs_str": "a['zoom'] = ;", "shapes": [], "waves": []}


class PresetValidatorExitStatusTest(unittest.TestCase):
    """Run both preset validators against fixture trees."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tools").mkdir()
        (self.root / "src" / "presets-extra").mkdir(parents=True)
        for tool in TOOLS:
            shutil.copy(REPO_ROOT / "tools" / tool, self.root / "tools" / tool)

    def write_index(self, index):
        """Write the fixture preset index."""
        text = f"{INDEX_PREFIX}{json.dumps(index)};\n"
        (self.root / "src" / "presets-extra" / "index.js").write_text(text, encoding="utf-8")

    def write_chunk(self, filename, logical_id, presets):
        """Write one fixture chunk file under its physical name."""
        text = f"window.__bcPresetChunk({logical_id},{json.dumps(presets)});\n"
        (self.root / "src" / "presets-extra" / filename).write_text(text, encoding="utf-8")

    def run_validator(self, tool):
        """Run one validator and return its process and reported preset names."""
        report_path = self.root / "report.json"
        environment = {**os.environ, "NODE_PATH": str(REPO_ROOT / "node_modules")}
        result = subprocess.run(
            ["node", str(self.root / "tools" / tool), str(report_path)],
            capture_output=True, text=True, check=False, cwd=self.root, env=environment,
        )
        names = None
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            names = [entry.get("experimentalName", entry.get("name")) for entry in report["presets"]]
        return result, names

    def test_experimental_validator_fails_on_an_invalid_equation(self):
        self.write_index({"v": 2, "chunks": [["Mainline"], ["[EXP] Broken"]],
                          "files": ["chunk-000.js", "chunk-9000.js"]})
        self.write_chunk("chunk-000.js", 0, {"Mainline": VALID_PRESET})
        self.write_chunk("chunk-9000.js", 1, {"[EXP] Broken": INVALID_PRESET})

        result, names = self.run_validator("validate-experimental-presets.js")

        self.assertEqual(names, ["[EXP] Broken"], result.stderr)
        self.assertEqual(result.returncode, EXIT_FAILURE, result.stdout)

    def test_experimental_validator_passes_valid_presets(self):
        self.write_index({"v": 2, "chunks": [["Mainline"], ["[EXP] Valid"]],
                          "files": ["chunk-000.js", "chunk-9000.js"]})
        self.write_chunk("chunk-000.js", 0, {"Mainline": VALID_PRESET})
        self.write_chunk("chunk-9000.js", 1, {"[EXP] Valid": VALID_PRESET})

        result, names = self.run_validator("validate-experimental-presets.js")

        self.assertEqual(names, [], result.stderr)
        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)

    def test_experimental_validator_accepts_an_index_without_files(self):
        self.write_index({"v": 1, "chunks": [["Mainline"]]})
        self.write_chunk("chunk-000.js", 0, {"Mainline": VALID_PRESET})

        result, names = self.run_validator("validate-experimental-presets.js")

        self.assertEqual(names, [], result.stderr)
        self.assertEqual(result.returncode, EXIT_SUCCESS, result.stderr)

    def test_chunk_validator_reads_padded_names_without_files(self):
        self.write_index({"v": 1, "chunks": [["Valid"], ["Broken"]]})
        self.write_chunk("chunk-000.js", 0, {"Valid": VALID_PRESET})
        self.write_chunk("chunk-001.js", 1, {"Broken": INVALID_PRESET})

        result, names = self.run_validator("validate-preset-chunks.js")

        self.assertEqual(names, ["Broken"], result.stderr)
        self.assertEqual(result.returncode, EXIT_FAILURE, result.stdout)


if __name__ == "__main__":
    unittest.main()
