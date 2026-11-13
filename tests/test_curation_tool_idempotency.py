"""Re-run safety for the Python curation tools.

Each test stops a tool partway through its writes, then runs it again, and
checks the generated records. Every test works on temporary copies and never
touches the committed preset data.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
INDEX_PREFIX = "window.BCExtraPresetIndex="


def load_tool(name):
    """Load a tools/ script as a module, including hyphenated filenames."""
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_index(path, data):
    """Write an index.js payload with the runtime wrapper."""
    path.write_text(INDEX_PREFIX + json.dumps(data) + ";\n", encoding="utf-8")


def read_index(path):
    """Return the parsed payload of an index.js file."""
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text[len(INDEX_PREFIX):].rstrip(";"))


def failing_writer(real_writer, failing_path):
    """Return a writer that raises once when it reaches failing_path."""
    state = {"failed": False}

    def write(path, text):
        if Path(path) == failing_path and not state["failed"]:
            state["failed"] = True
            raise OSError("simulated crash")
        real_writer(path, text)

    return write


class FakeSplitter:
    """Stand-in for split-extra-images.py inside the importer."""

    def __init__(self, fail=False):
        self.fail = fail
        self.written = []

    def read_images(self):
        return {}

    def write_parts(self, images, dry_run):
        if self.fail:
            raise OSError("simulated texture failure")
        self.written.append(images)


class ImporterRerunTests(unittest.TestCase):
    """import-nestdrop-presets.py never duplicates or half-applies a batch."""

    def setUp(self):
        self.tool = load_tool("import-nestdrop-presets.py")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.out_dir = root / "presets-extra"
        self.out_dir.mkdir()
        (self.out_dir / "chunk-000.js").write_text(
            'window.__bcPresetChunk(0,{"Mainline":{"baseVals":{}}});\n', encoding="utf-8",
        )
        self.index = self.out_dir / "index.js"
        write_index(self.index, {"v": 2, "chunks": [["Mainline"]], "files": ["chunk-000.js"]})
        self.csv = root / "preset-inventory.csv"
        self.csv.write_text("name,pack,chunk\nMainline,presets-extra,0\n", encoding="utf-8")
        self.manifest = root / "experimental-presets.json"
        self.archive = root / "batch.zip"
        self.archive.write_bytes(b"archive")
        self.splitter = FakeSplitter()
        source = {"sourcePath": "Sample.milk", "originalName": "Sample", "runtimeName": "Sample"}
        patches = {
            "OUT_DIR": self.out_dir,
            "INDEX_PATH": self.index,
            "CSV_PATH": self.csv,
            "REMOVED_CSV_PATH": root / "removed-presets.csv",
            "MANIFEST_PATH": self.manifest,
            "TEXTURE_MANIFEST_PATH": root / "experimental-textures.json",
            "extract_source": lambda *args: (1, [], [], [source]),
            "run_converter": lambda *args: {"Sample": {"baseVals": {}}},
            "build_texture_bundle": lambda *args: ({}, [], []),
            "load_texture_splitter": lambda: self.splitter,
        }
        for name, value in patches.items():
            patcher = patch.object(self.tool, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_import(self):
        with patch.object(sys, "argv", ["import-nestdrop-presets.py", "--zip", str(self.archive)]):
            self.tool.main()

    def indexed_names(self):
        return [name for names in read_index(self.index)["chunks"] for name in names]

    def test_rerun_after_a_crash_past_the_index_imports_each_preset_once(self):
        writer = failing_writer(self.tool.atomic_write_text, self.manifest)
        with patch.object(self.tool, "atomic_write_text", writer), self.assertRaises(OSError):
            self.run_import()

        self.run_import()

        self.assertEqual(self.indexed_names().count("[EXP] Sample"), 1)

    def test_texture_failure_leaves_the_index_unchanged(self):
        self.splitter.fail = True

        with self.assertRaises(OSError):
            self.run_import()

        self.assertEqual(self.indexed_names(), ["Mainline"], "no preset lands without its textures")


class RemovalRerunTests(unittest.TestCase):
    """remove-experimental-duplicates.py finishes on a re-run without duplicates."""

    NAMES = ["[EXP] one", "[EXP] two"]

    def setUp(self):
        self.tool = load_tool("remove-experimental-duplicates.py")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        out_dir = root / "presets-extra"
        out_dir.mkdir()
        files = [f"chunk-{9000 + cid}.js" for cid in range(len(self.NAMES))]
        self.index = out_dir / "index.js"
        write_index(self.index, {"chunks": [[name] for name in self.NAMES], "files": files})
        for cid, (name, filename) in enumerate(zip(self.NAMES, files, strict=True)):
            (out_dir / filename).write_text(
                f"window.__bcPresetChunk({cid},{json.dumps({name: {}})});\n", encoding="utf-8",
            )
        self.csv = root / "preset-inventory.csv"
        self.csv.write_text(
            "name,pack,chunk\n" + "".join(f"{n},presets-extra,{i}\n" for i, n in enumerate(self.NAMES)),
            encoding="utf-8",
        )
        self.ledger = root / "removed-presets.csv"
        self.ledger.write_text("name,pack,chunk,commit,date,subject\n", encoding="utf-8")
        self.manifest = root / "experimental-presets.json"
        self.manifest.write_text(json.dumps({"presets": [
            {"displayName": n, "sourceName": n[len("[EXP] "):], "logicalChunk": i,
             "mainlineMatches": [], "normalizedNameMatches": []}
            for i, n in enumerate(self.NAMES)
        ]}), encoding="utf-8")
        self.exclusions = root / "experimental-exclusions.json"
        self.exclusions.write_text("[]\n", encoding="utf-8")
        self.decisions = root / "decisions.json"
        self.decisions.write_text(json.dumps(self.NAMES), encoding="utf-8")
        patches = {
            "OUT_DIR": out_dir,
            "INDEX_PATH": self.index,
            "CSV_PATH": self.csv,
            "REMOVED_CSV_PATH": self.ledger,
            "MANIFEST_PATH": self.manifest,
            "EXCLUSIONS_PATH": self.exclusions,
        }
        for name, value in patches.items():
            patcher = patch.object(self.tool, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_removal(self):
        argv = ["remove-experimental-duplicates.py", "--decisions", str(self.decisions), "--allow-unmatched"]
        with patch.object(sys, "argv", argv):
            return self.tool.main()

    def test_rerun_after_a_crash_completes_once(self):
        writer = failing_writer(self.tool.atomic_write_text, self.manifest)
        with patch.object(self.tool, "atomic_write_text", writer), self.assertRaises(OSError):
            self.run_removal()

        self.assertEqual(self.run_removal(), 0)

        self.assertEqual(read_index(self.index)["chunks"], [[], []])
        ledger = self.ledger.read_text(encoding="utf-8")
        for name in self.NAMES:
            self.assertEqual(ledger.count(name), 1, f"one ledger row for {name}")
        exclusions = json.loads(self.exclusions.read_text(encoding="utf-8"))
        self.assertEqual(sorted(item["displayName"] for item in exclusions), self.NAMES)
        self.assertEqual(json.loads(self.manifest.read_text(encoding="utf-8"))["presets"], [])


class TexturePartTests(unittest.TestCase):
    """split-extra-images.py writes every part or none."""

    def test_failure_while_building_parts_keeps_existing_parts(self):
        tool = load_tool("split-extra-images.py")
        with tempfile.TemporaryDirectory() as directory:
            vendor = Path(directory)
            existing = vendor / "butterchurnExtraImagesExp-part-0.js"
            existing.write_text("window.__bcExtraImagesExpPart(0,1,{});\n", encoding="utf-8")
            images = {f"image{n}": {"data": "x" * 10, "width": 1, "height": 1} for n in range(16)}
            # The size sum reads only "data". The JSON encoding of the last
            # part then fails after the earlier parts are built.
            images["image15"]["width"] = object()
            with (
                patch.object(tool, "VENDOR", vendor),
                patch.object(tool, "BUNDLE", vendor / "butterchurnExtraImagesExp.js"),
                self.assertRaises(TypeError),
            ):
                tool.write_parts(images, dry_run=False)

            self.assertEqual(existing.read_text(encoding="utf-8"), "window.__bcExtraImagesExpPart(0,1,{});\n")
            self.assertEqual([path.name for path in vendor.iterdir()], [existing.name])


class ReconcileTests(unittest.TestCase):
    """reconcile_preset_inventory.py rewrites the inventory through the shared writer."""

    def test_reconcile_uses_the_atomic_writer(self):
        tool = load_tool("reconcile_preset_inventory.py")
        self.assertEqual(Path(tool.atomic_write_text.__code__.co_filename).name, "preset_io.py")

    def test_reconcile_rebuilds_rows_from_the_index(self):
        tool = load_tool("reconcile_preset_inventory.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "index.js"
            write_index(index, {"chunks": [["Kept", "Missing"]]})
            inventory = root / "preset-inventory.csv"
            inventory.write_text(
                "name,pack,chunk\nKept,presets-extra,0\nStale,presets-extra,0\nVendor,butterchurnPresets,\n",
                encoding="utf-8",
            )
            argv = ["reconcile_preset_inventory.py"]
            with (
                patch.object(tool, "INDEX_PATH", index),
                patch.object(tool, "CSV_PATH", inventory),
                patch.object(sys, "argv", argv),
            ):
                tool.main()

            self.assertEqual(
                inventory.read_bytes(),
                b"name,pack,chunk\nKept,presets-extra,0\nVendor,butterchurnPresets,\nMissing,presets-extra,0\n",
            )


if __name__ == "__main__":
    unittest.main()
