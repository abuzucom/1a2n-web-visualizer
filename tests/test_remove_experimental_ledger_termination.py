import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "remove-experimental-duplicates.py"
)
SPEC = importlib.util.spec_from_file_location(
    "remove_experimental_duplicates_termination", TOOL_PATH
)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class ExperimentalLedgerTerminationTests(unittest.TestCase):
    def test_appends_after_unterminated_ledger_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_dir = root / "src" / "presets-extra"
            output_dir.mkdir(parents=True)
            name = "[EXP2] sample"
            index_path = output_dir / "index.js"
            index_data = {"chunks": [[name]], "files": ["chunk-9000.js"]}
            index_path.write_text(
                f"{TOOL.INDEX_PREFIX}{json.dumps(index_data)};\n",
                encoding="utf-8",
            )
            (output_dir / "chunk-9000.js").write_text(
                f"window.__bcPresetChunk(0,{json.dumps({name: {}})});\n",
                encoding="utf-8",
            )

            inventory_path = root / "preset-inventory.csv"
            inventory_path.write_text(
                f"name,pack,chunk\n{name},presets-extra,0\n",
                encoding="utf-8",
            )
            removed_path = root / "removed-presets.csv"
            removed_path.write_bytes(
                b"name,pack,chunk,commit,date,subject\n"
                b"legacy,presets-extra,0,,2026-01-01,legacy record"
            )
            manifest_path = root / "experimental-presets.json"
            manifest_path.write_text(
                json.dumps({
                    "presets": [{
                        "displayName": name,
                        "sourceName": "sample",
                        "logicalChunk": 0,
                        "mainlineMatches": [],
                        "normalizedNameMatches": [],
                    }]
                }),
                encoding="utf-8",
            )
            exclusions_path = root / "experimental-exclusions.json"
            exclusions_path.write_text("[]\n", encoding="utf-8")
            decisions_path = root / "decisions.json"
            decisions_path.write_text(json.dumps([name]), encoding="utf-8")

            with (
                patch.object(TOOL, "OUT_DIR", output_dir),
                patch.object(TOOL, "INDEX_PATH", index_path),
                patch.object(TOOL, "CSV_PATH", inventory_path),
                patch.object(TOOL, "REMOVED_CSV_PATH", removed_path),
                patch.object(TOOL, "MANIFEST_PATH", manifest_path),
                patch.object(TOOL, "EXCLUSIONS_PATH", exclusions_path),
                patch.object(
                    sys,
                    "argv",
                    [
                        str(TOOL_PATH),
                        "--decisions",
                        str(decisions_path),
                        "--allow-unmatched",
                        "--reason",
                        "curation approved",
                    ],
                ),
            ):
                self.assertEqual(TOOL.main(), 0)

            ledger_rows = list(
                csv.reader(removed_path.read_text(encoding="utf-8").splitlines())
            )
            self.assertEqual(ledger_rows[1][-1], "legacy record")
            self.assertEqual(ledger_rows[2][0], name)


if __name__ == "__main__":
    unittest.main()
