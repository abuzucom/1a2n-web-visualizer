"""Report counts of tools/fetch-cream-of-the-crop-presets.py.

Each converted preset lands in exactly one reported bucket. The bucket
counts therefore add up to the converted count.
"""

import contextlib
import importlib.util
import io
import re
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = ROOT / "tools" / "fetch-cream-of-the-crop-presets.py"
COUNT_LINE = re.compile(r"^(?P<label>[^:]+): (?P<count>\d+)$")

PLAIN_PRESET = {"warp": "", "comp": ""}
MISSING_TEXTURE_PRESET = {"warp": "uniform sampler2D sampler_absent_texture;", "comp": ""}
CONVERTED = {
    "Alpha": PLAIN_PRESET,
    "beta": PLAIN_PRESET,
    "Gamma": PLAIN_PRESET,
    "Delta": PLAIN_PRESET,
    "Epsilon": MISSING_TEXTURE_PRESET,
    "Eta": PLAIN_PRESET,
    "theta": PLAIN_PRESET,
}
# Beta and Theta differ from the converted names only by case. Eta sits in
# both ledgers. The case misses outnumber the double count, so an exact-match
# report cannot add up by coincidence.
INVENTORY_TEXT = (
    "name,pack,chunk\nBeta,presets-extra,0\nGamma,presets-extra,0\n"
    "Eta,presets-extra,0\nTheta,presets-extra,0\n"
)
LEDGER_TEXT = (
    "name,pack,chunk,commit,date,subject\n"
    "Delta,presets-extra,0,abc1234,2026-01-01,removal\n"
    "Eta,presets-extra,0,abc1234,2026-01-01,removal\n"
)


def load_tool():
    """Load the hyphenated tool script as a module."""
    spec = importlib.util.spec_from_file_location("fetch_cream_of_the_crop_presets", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_zip_bytes():
    """Return a small archive with one top-level folder."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("presets-cream-of-the-crop-sample/placeholder.milk", "[preset00]\n")
    return buffer.getvalue()


class CreamFetchReportCountTests(unittest.TestCase):
    """Run main() in dry-run mode against fixture ledgers."""

    def setUp(self):
        self.tool = load_tool()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        inventory = root / "preset-inventory.csv"
        ledger = root / "removed-presets.csv"
        image_names = root / "butterchurn-image-names.json"
        inventory.write_text(INVENTORY_TEXT, encoding="utf-8")
        ledger.write_text(LEDGER_TEXT, encoding="utf-8")
        image_names.write_text("[]", encoding="utf-8")
        replacements = {
            "CSV_PATH": inventory,
            "REMOVED_CSV_PATH": ledger,
            "IMAGE_NAMES_FILE": image_names,
            "get_zip_bytes": unittest.mock.Mock(return_value=build_zip_bytes()),
            "convert_presets": unittest.mock.Mock(return_value=dict(CONVERTED)),
        }
        for name, value in replacements.items():
            patcher = unittest.mock.patch.object(self.tool, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_dry_run(self):
        """Run main() with --dry-run and return the reported counts by label."""
        output = io.StringIO()
        with (
            unittest.mock.patch.object(sys, "argv", ["fetch-cream-of-the-crop-presets.py", "--dry-run"]),
            contextlib.redirect_stdout(output),
        ):
            self.tool.main()
        counts = {}
        for line in output.getvalue().splitlines():
            match = COUNT_LINE.match(line)
            if match:
                counts[match.group("label")] = int(match.group("count"))
        return counts

    def test_bucket_counts_add_up_to_the_converted_count(self):
        counts = self.run_dry_run()

        converted = counts.pop("converted")
        self.assertEqual(sum(counts.values()), converted, counts)

    def test_inventory_match_ignores_case(self):
        counts = self.run_dry_run()

        self.assertEqual(counts["already in preset-inventory.csv"], 4, counts)

    def test_name_in_both_ledgers_counts_once_as_present(self):
        counts = self.run_dry_run()

        self.assertEqual(counts["already in removed-presets.csv ledger"], 1, counts)
        self.assertEqual(counts["excluded (missing textures)"], 1, counts)
        self.assertEqual(counts["net new presets to add"], 1, counts)


if __name__ == "__main__":
    unittest.main()
