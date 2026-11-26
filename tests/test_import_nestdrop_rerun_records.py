"""NestDrop importer regressions: manifest records stay stable across
re-runs over the same archive, and ZIP member paths stay confined."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = ROOT / "tools" / "import-nestdrop-presets.py"
SPEC = importlib.util.spec_from_file_location("import_nestdrop_rerun_records", TOOL_PATH)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

MAINLINE_NAME = "Mainline preset"
MAINLINE_PRESET = {"baseVals": {"zoom": 0.9}, "warp": "", "comp": ""}
FIRST_PRESET = {"baseVals": {"zoom": 1.1}, "warp": "", "comp": ""}
VARIANT_PRESET = {"baseVals": {"zoom": 1.2}, "warp": "", "comp": ""}
# "Bar" converts to the same content as "Foo". The importer visits names in
# sorted order, so it keeps "Bar" and records "Foo" as a duplicate skip on
# every run. That skip exposes records that accumulate per run.
CONVERTED_PRESETS = {
    "Foo": FIRST_PRESET,
    "Foo [variant 2]": VARIANT_PRESET,
    "Bar": FIRST_PRESET,
}
ZIP_MEMBERS = ("A/Foo.milk", "B/Foo.milk", "C/Bar.milk")
RUN_COUNT = 3


def write_fixture_tree(root):
    """Write a minimal presets-extra tree and return the paths to patch."""
    out_dir = root / "src" / "presets-extra"
    out_dir.mkdir(parents=True)
    index = {"v": 1, "chunks": [[MAINLINE_NAME]]}
    (out_dir / "index.js").write_text(
        TOOL.INDEX_PREFIX + json.dumps(index) + ";\n", encoding="utf-8",
    )
    (out_dir / "chunk-000.js").write_text(
        f"window.__bcPresetChunk(0,{json.dumps({MAINLINE_NAME: MAINLINE_PRESET})});\n",
        encoding="utf-8",
    )
    inventory = root / "preset-inventory.csv"
    inventory.write_text("name,collection,chunk\n", encoding="utf-8")
    removed = root / "removed-presets.csv"
    removed.write_text("name\n", encoding="utf-8")
    return {
        "OUT_DIR": out_dir,
        "INDEX_PATH": out_dir / "index.js",
        "CSV_PATH": inventory,
        "REMOVED_CSV_PATH": removed,
        "MANIFEST_PATH": root / "experimental-presets.json",
        "TEXTURE_MANIFEST_PATH": root / "experimental-textures.json",
    }


def write_fixture_zip(path):
    """Write a ZIP whose two Foo.milk members collide on their stem."""
    with zipfile.ZipFile(path, "w") as archive:
        for member in ZIP_MEMBERS:
            archive.writestr(member, "[preset00]\nzoom=1.0\n")


def convert_fixture(source_root, output_path):
    """Stand in for the Node converter, which needs npm dependencies."""
    del output_path
    milk_stems = {path.stem for path in source_root.rglob("*.milk")}
    return {name: copy.deepcopy(preset) for name, preset in CONVERTED_PRESETS.items() if name in milk_stems}


def skip_keys(manifest):
    """Return the (sourceName, reason) pair of every skip record."""
    return [(item["sourceName"], item["reason"]) for item in manifest["skipped"]]


class NestDropRerunRecordTests(unittest.TestCase):
    """Run the importer repeatedly against one fixture archive."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.paths = write_fixture_tree(self.root)
        self.zip_path = self.root / "pack.zip"
        write_fixture_zip(self.zip_path)
        splitter = unittest.mock.Mock()
        splitter.read_images.return_value = {}
        patches = [unittest.mock.patch.object(TOOL, name, value) for name, value in self.paths.items()]
        patches.append(unittest.mock.patch.object(TOOL, "run_converter", convert_fixture))
        patches.append(unittest.mock.patch.object(TOOL, "load_texture_splitter", return_value=splitter))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_import(self):
        """Run main() once and return the written manifest."""
        argv = [str(TOOL_PATH), "--zip", str(self.zip_path)]
        with unittest.mock.patch.object(sys, "argv", argv):
            TOOL.main()
        return json.loads(self.paths["MANIFEST_PATH"].read_text(encoding="utf-8"))

    def test_initial_run_records_one_collision(self):
        """First run records one collision and retains two presets."""
        manifest = self.run_import()

        self.assertEqual(len(manifest["collisions"]), 1)
        self.assertEqual(manifest["collisions"][0]["runtimeName"], "Foo [variant 2]")
        self.assertEqual(len(manifest["presets"]), 2)

    def test_reruns_keep_collision_records_unique(self):
        """Reruns do not duplicate collision records."""
        for run in range(RUN_COUNT):
            manifest = self.run_import()
            self.assertEqual(len(manifest["collisions"]), 1, f"run {run + 1}")

    def test_reruns_keep_skip_records_unique(self):
        """Reruns do not duplicate skip records."""
        manifests = [self.run_import() for _ in range(RUN_COUNT)]

        for run, manifest in enumerate(manifests, start=1):
            keys = skip_keys(manifest)
            self.assertEqual(len(keys), len(set(keys)), f"run {run}: {keys}")
        self.assertEqual(manifests[-1]["skipped"], manifests[-2]["skipped"])

    def test_reruns_keep_retained_presets(self):
        """Reruns keep the retained presets unchanged."""
        manifests = [self.run_import() for _ in range(RUN_COUNT)]

        names = [[item["displayName"] for item in manifest["presets"]] for manifest in manifests]
        self.assertEqual(names[0], ["[EXP] Bar", "[EXP] Foo [variant 2]"])
        self.assertEqual(names[-1], names[0])


class SafeMemberPathTests(unittest.TestCase):
    """Pin the ZIP member path checks."""

    def test_rejects_unsafe_member_names(self):
        root = Path("destination")
        for member_name in ("/abs", "a/../b", "..\\escape", "", "."):
            with self.subTest(member_name=member_name), self.assertRaises(ValueError):
                TOOL.safe_member_path(root, member_name)

    def test_accepts_a_nested_texture_member(self):
        root = Path("destination")
        self.assertEqual(TOOL.safe_member_path(root, "Textures/x.png"), root / "Textures" / "x.png")

    def test_collapses_a_leading_dot_segment(self):
        # PurePosixPath drops "." segments, so "./foo.milk" splits into
        # ("foo.milk",) and stays inside the destination root.
        root = Path("destination")
        self.assertEqual(TOOL.safe_member_path(root, "./foo.milk"), root / "foo.milk")


if __name__ == "__main__":
    unittest.main()
