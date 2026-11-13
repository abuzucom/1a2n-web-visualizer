"""Behavioral tests for the shared preset tool helpers in tools/preset_io.py."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_WITH_WRITER = (
    "curate_catalogs.py",
    "fetch-cream-of-the-crop-presets.py",
    "import-nestdrop-presets.py",
    "remove-experimental-duplicates.py",
)


def load_tool(name):
    """Load a tools/ script as a module, including hyphenated filenames."""
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def defined_in_preset_io(function):
    """Return whether a function object comes from tools/preset_io.py."""
    return Path(function.__code__.co_filename).name == "preset_io.py"


class AtomicWriteTests(unittest.TestCase):
    """atomic_write_text replaces a file whole or leaves it untouched."""

    def setUp(self):
        self.preset_io = load_tool("preset_io.py")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "index.js"

    def test_write_keeps_line_feeds_exactly(self):
        self.preset_io.atomic_write_text(self.path, "a\nb\n")

        self.assertEqual(self.path.read_bytes(), b"a\nb\n")

    def test_failed_write_keeps_old_content_and_leaves_no_temporary_file(self):
        self.path.write_text("old\n", encoding="utf-8")

        with self.assertRaises(TypeError):
            self.preset_io.atomic_write_text(self.path, None)

        self.assertEqual(self.path.read_text(encoding="utf-8"), "old\n")
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ["index.js"])


class PresetHashTests(unittest.TestCase):
    """preset_hash keeps the digest recorded in experimental-presets.json."""

    def test_hash_normalizes_line_endings_and_zero(self):
        preset_io = load_tool("preset_io.py")
        preset = {"frame_eqs_str": "a=1;\r\nb=2;\r", "baseVals": {"zoom": 0.0, "rot": 1.5}}
        canonical = {"baseVals": {"rot": 1.5, "zoom": 0}, "frame_eqs_str": "a=1;\nb=2;\n"}
        payload = json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")

        self.assertEqual(preset_io.preset_hash(preset), hashlib.sha256(payload).hexdigest())


class SharedHelperTests(unittest.TestCase):
    """Every tool reaches the one shared implementation."""

    def test_tools_write_through_the_shared_helper(self):
        for name in TOOLS_WITH_WRITER:
            with self.subTest(tool=name):
                self.assertTrue(defined_in_preset_io(load_tool(name).atomic_write_text))

    def test_tools_hash_through_the_shared_helper(self):
        self.assertTrue(defined_in_preset_io(load_tool("import-nestdrop-presets.py").preset_hash))
        self.assertTrue(defined_in_preset_io(load_tool("compare-experimental-presets.py").digest))


if __name__ == "__main__":
    unittest.main()
