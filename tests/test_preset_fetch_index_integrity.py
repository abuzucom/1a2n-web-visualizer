"""Behavioral tests for preset fetch tools that write src/presets-extra/index.js.

Each test points a tool at a temporary presets-extra directory. No test reads or
writes the committed preset data.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_PREFIX = "window.BCExtraPresetIndex="
SAMPLE_PRESET = {"baseVals": {"decay": 0.98}}


def load_tool(name):
    """Load a tools/ script with a hyphenated filename as a module."""
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_index(out_dir, data):
    """Write an index.js file with the runtime wrapper."""
    text = INDEX_PREFIX + json.dumps(data, separators=(",", ":")) + ";\n"
    (out_dir / "index.js").write_text(text, encoding="utf-8")


def read_index(out_dir):
    """Return the parsed payload of an index.js file."""
    text = (out_dir / "index.js").read_text(encoding="utf-8").strip()
    return json.loads(text[len(INDEX_PREFIX):].rstrip(";"))


def experimental_index():
    """Return an index payload holding one mainline and one experimental chunk."""
    return {
        "v": 2,
        "chunks": [["Mainline A"], ["[EXP] Sample"]],
        "files": ["chunk-000.js", "chunk-9000.js"],
    }


class CreamAppendIndexTests(unittest.TestCase):
    """fetch-cream-of-the-crop-presets.py appends chunks to an existing index."""

    def setUp(self):
        self.tool = load_tool("fetch-cream-of-the-crop-presets.py")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.out_dir = Path(self.directory.name)
        for name, value in (("OUT_DIR", self.out_dir), ("INDEX_PATH", self.out_dir / "index.js")):
            patcher = unittest.mock.patch.object(self.tool, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def append(self, names):
        start = self.tool.load_next_chunk_id(self.out_dir / "index.js")
        kept = {name: dict(SAMPLE_PRESET) for name in names}
        return start, self.tool.append_chunks(kept, start)

    def test_append_extends_files_map_with_each_new_chunk(self):
        write_index(self.out_dir, experimental_index())

        start, _ = self.append(["Cream One"])

        data = read_index(self.out_dir)
        self.assertEqual(start, 2)
        self.assertEqual(
            len(data["files"]), len(data["chunks"]),
            "every logical chunk needs a physical file entry, or index readers reject the index",
        )
        self.assertEqual(data["files"][2], "chunk-002.js")
        self.assertEqual(data["chunks"][2], ["Cream One"])
        chunk_text = (self.out_dir / "chunk-002.js").read_text(encoding="utf-8")
        self.assertTrue(chunk_text.startswith("window.__bcPresetChunk(2,"))

    def test_append_keeps_version_one_index_without_files_map(self):
        write_index(self.out_dir, {"v": 1, "chunks": [["Mainline A"]]})

        self.append(["Cream One"])

        data = read_index(self.out_dir)
        self.assertNotIn("files", data)
        self.assertEqual(data["chunks"], [["Mainline A"], ["Cream One"]])

    def test_append_creates_index_when_none_exists(self):
        start, _ = self.append(["Cream One"])

        self.assertEqual(start, 0)
        self.assertEqual(read_index(self.out_dir)["chunks"], [["Cream One"]])


class FetchExtraRegenerationTests(unittest.TestCase):
    """fetch-extra-presets.py regenerates only an index without experimental output."""

    def setUp(self):
        self.tool = load_tool("fetch-extra-presets.py")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.out_dir = Path(self.directory.name) / "presets-extra"
        self.out_dir.mkdir()

    def test_write_output_refuses_index_with_files_map(self):
        write_index(self.out_dir, experimental_index())
        experimental_chunk = self.out_dir / "chunk-9000.js"
        experimental_chunk.write_text("window.__bcPresetChunk(1,{});\n", encoding="utf-8")

        with self.assertRaises(self.tool.RegenerationRefusedError):
            self.tool.write_output({"Fresh": dict(SAMPLE_PRESET)}, self.out_dir)

        self.assertTrue(experimental_chunk.exists(), "a refused regeneration must not delete experimental chunks")
        self.assertEqual(read_index(self.out_dir), experimental_index())

    def test_write_output_regenerates_version_one_index(self):
        write_index(self.out_dir, {"v": 1, "chunks": [["Old"]]})

        chunks, _ = self.tool.write_output({"Fresh": dict(SAMPLE_PRESET)}, self.out_dir)

        self.assertEqual(chunks, [["Fresh"]])
        self.assertEqual(read_index(self.out_dir)["chunks"], [["Fresh"]])

    def test_download_passes_a_timeout(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"payload"
        with (
            unittest.mock.patch.object(self.tool.urllib.request, "urlopen", return_value=response) as urlopen,
            unittest.mock.patch.object(self.tool, "ZIP_SHA256", self.tool.hashlib.sha256(b"payload").hexdigest()),
        ):
            self.tool.get_zip_bytes(None)

        self.assertEqual(urlopen.call_args.kwargs.get("timeout"), self.tool.DOWNLOAD_TIMEOUT_S)

    def test_main_refuses_before_download(self):
        write_index(self.out_dir, experimental_index())
        with (
            unittest.mock.patch.object(self.tool, "OUT_DIR", self.out_dir),
            unittest.mock.patch.object(self.tool, "get_zip_bytes") as get_zip_bytes,
            unittest.mock.patch.object(sys, "argv", ["fetch-extra-presets.py"]),
            self.assertRaises(SystemExit) as raised,
        ):
            self.tool.main()

        get_zip_bytes.assert_not_called()
        self.assertIn("files map", str(raised.exception.code))


class FetchExtraCuratedRegenerationTests(unittest.TestCase):
    """fetch-extra-presets-curated.py refuses before any download or write."""

    def test_main_refuses_index_with_files_map(self):
        curated = load_tool("fetch-extra-presets-curated.py")
        fetch = load_tool("fetch-extra-presets.py")
        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory)
            write_index(out_dir, experimental_index())
            with (
                unittest.mock.patch.object(curated, "OUT_DIR", out_dir),
                unittest.mock.patch.object(curated, "INDEX_PATH", out_dir / "index.js"),
                unittest.mock.patch.object(curated, "_load_fetch_module", return_value=fetch),
                unittest.mock.patch.object(fetch, "get_zip_bytes") as get_zip_bytes,
                unittest.mock.patch.object(sys, "argv", ["fetch-extra-presets-curated.py"]),
                self.assertRaises(SystemExit) as raised,
            ):
                curated.main()

            get_zip_bytes.assert_not_called()
            self.assertIn("files map", str(raised.exception.code))
            self.assertEqual(read_index(out_dir), experimental_index())


if __name__ == "__main__":
    unittest.main()
