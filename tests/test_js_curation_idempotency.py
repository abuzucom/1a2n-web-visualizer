"""Re-run and accuracy regressions for the JavaScript curation tools.

Each test copies one tool into a temporary tree and runs it with node. No
test reads or writes the committed preset data.
"""
import csv
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PREFIX = "window.BCExtraPresetIndex="
LEDGER_HEADER = "name,pack,chunk,commit,date,subject\n"
GIT_IDENTITY = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]


def index_text(chunks, files):
    """Return an index.js payload with the runtime wrapper."""
    return INDEX_PREFIX + json.dumps({"v": 2, "chunks": chunks, "files": files}) + ";"


def chunk_text(cid, presets):
    """Return a chunk file payload with the runtime wrapper."""
    return f"window.__bcPresetChunk({cid},{json.dumps(presets)});"


class RemovalFixture(unittest.TestCase):
    """A temporary tree for tools/remove_presets.js."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tools").mkdir()
        (self.root / "src" / "presets-extra").mkdir(parents=True)
        shutil.copy(REPO_ROOT / "tools" / "remove_presets.js", self.root / "tools" / "remove_presets.js")
        self.write("names.txt", "Alpha\n")

    def write(self, relative, text):
        (self.root / relative).write_text(text, encoding="utf-8")

    def read(self, relative):
        return (self.root / relative).read_text(encoding="utf-8")

    def run_removal(self):
        return subprocess.run(
            ["node", str(self.root / "tools" / "remove_presets.js"), "--names-file", "names.txt"],
            capture_output=True, text=True, check=False, cwd=self.root,
        )


class RemovalRerunTests(RemovalFixture):
    """A removal that stopped after the chunk write finishes on a re-run."""

    def test_rerun_after_the_chunk_write_completes_the_removal(self):
        # The ledger and the chunk record the first run. The index and the
        # inventory still name the preset, because the run stopped there.
        self.write("src/presets-extra/index.js", index_text([["Alpha", "Beta"]], ["chunk-000.js"]))
        self.write("src/presets-extra/chunk-000.js", chunk_text(0, {"Beta": {"b": 2}}))
        self.write("preset-inventory.csv", "name,pack,chunk\nAlpha,presets-extra,0\nBeta,presets-extra,0\n")
        self.write("removed-presets.csv", LEDGER_HEADER + "Alpha,presets-extra,0,,2026-11-13,\n")

        result = self.run_removal()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Alpha", self.read("src/presets-extra/index.js"))
        self.assertNotIn("Alpha", self.read("preset-inventory.csv"))
        self.assertEqual(self.read("removed-presets.csv").count("Alpha"), 1)


class RemovalPackTests(RemovalFixture):
    """A name held by two packs leaves the other pack's inventory row."""

    def test_removal_keeps_the_row_of_the_pack_it_does_not_touch(self):
        self.write("src/presets-extra/index.js", index_text([["Alpha"]], ["chunk-000.js"]))
        self.write("src/presets-extra/chunk-000.js", chunk_text(0, {"Alpha": {"a": 1}}))
        self.write(
            "preset-inventory.csv",
            "name,pack,chunk\nAlpha,butterchurnPresetsExtra,\nAlpha,presets-extra,0\n",
        )
        self.write("removed-presets.csv", LEDGER_HEADER)

        result = self.run_removal()

        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.reader(io.StringIO(self.read("preset-inventory.csv"))))
        self.assertEqual(rows, [["name", "pack", "chunk"], ["Alpha", "butterchurnPresetsExtra", ""]])


class CurationHistoryTests(unittest.TestCase):
    """tools/analyze_curation_history.js reports removals, not moves."""

    def git(self, *arguments):
        subprocess.run(["git", *GIT_IDENTITY, *arguments], cwd=self.root, check=True, capture_output=True)

    def commit_index(self, chunks, message):
        files = [f"chunk-{cid:03d}.js" for cid in range(len(chunks))]
        (self.root / "src" / "presets-extra" / "index.js").write_text(
            index_text(chunks, files), encoding="utf-8",
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def test_a_preset_moved_to_another_chunk_is_not_a_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            self.root = Path(directory)
            (self.root / "tools").mkdir()
            (self.root / "src" / "presets-extra").mkdir(parents=True)
            shutil.copy(
                REPO_ROOT / "tools" / "analyze_curation_history.js",
                self.root / "tools" / "analyze_curation_history.js",
            )
            self.git("init", "-q")
            self.commit_index([["Moved", "Removed", "Kept"]], "add presets")
            self.commit_index([["Kept"], ["Moved"]], "regenerate chunks")

            result = subprocess.run(
                ["node", "tools/analyze_curation_history.js", "--csv", "out.csv"],
                capture_output=True, text=True, check=False, cwd=self.root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = list(csv.DictReader(io.StringIO((self.root / "out.csv").read_text(encoding="utf-8"))))
            self.assertEqual([row["name"] for row in rows], ["Removed"])
            self.assertEqual(rows[0]["chunk"], "0", "the record names the chunk the preset left")


if __name__ == "__main__":
    unittest.main()
