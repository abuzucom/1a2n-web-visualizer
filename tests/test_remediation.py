import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parent.parent


def load_tool(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RemediationTests(unittest.TestCase):
    def test_history_analyzer_runs_without_bundle_execution(self):
        result = subprocess.run(
            ["node", "tools/analyze_curation_history.js"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Curation commits analyzed:", result.stdout)
        source = (ROOT / "tools/analyze_curation_history.js").read_text(encoding="utf-8")
        self.assertNotIn("require(tmp)", source)
        self.assertNotIn("execSync(`", source)

    def test_extra_archive_rejects_oversized_member(self):
        tool = load_tool("fetch-extra-presets.py")

        class FakeZip:
            def infolist(self):
                return [type("Info", (), {"file_size": tool.MAX_MEMBER_BYTES + 1})()]

            def namelist(self):
                return ["converted/large.json"]

            def getinfo(self, _member):
                return self.infolist()[0]

            def read(self, _member):
                return b"{}"

        _kept, _excluded, bad_json = tool.collect_presets(FakeZip(), set())
        self.assertEqual(bad_json, ["large"])

    def test_nestdrop_archive_rejects_oversized_member(self):
        tool = load_tool("import-nestdrop-presets.py")
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "input.zip"
            with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
                archive.writestr("Textures/large.png", b"x" * (tool.MAX_MEMBER_BYTES + 1))
            with self.assertRaises(ValueError):
                tool.extract_source(archive_path, Path(directory) / "out")

    def test_curation_tool_reads_three_column_inventory(self):
        result = subprocess.run(
            [
                "node", "tools/remove_presets.js", "--dry-run",
                "--name", "Aderrasi - Afterimage Cyclotron",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Would remove 1 presets", result.stdout)


if __name__ == "__main__":
    unittest.main()
