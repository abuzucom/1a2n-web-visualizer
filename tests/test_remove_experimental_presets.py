import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "remove-experimental-duplicates.py"
SPEC = importlib.util.spec_from_file_location("remove_experimental_duplicates", TOOL_PATH)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def write_fixture_files(root: Path) -> dict[str, Path]:
    """Create a minimal experimental collection for removal tests."""
    output_dir = root / "src" / "presets-extra"
    output_dir.mkdir(parents=True)
    names = ["[EXP] sample", "[EXP2] sample", "[EXP3] sample"]
    files = [f"chunk-{9000 + index}.js" for index in range(len(names))]
    index_data = {"chunks": [[name] for name in names], "files": files}
    index_path = output_dir / "index.js"
    index_path.write_text(
        f"{TOOL.INDEX_PREFIX}{json.dumps(index_data)};\n",
        encoding="utf-8",
    )
    for logical_chunk, (name, filename) in enumerate(zip(names, files, strict=True)):
        (output_dir / filename).write_text(
            f"window.__bcPresetChunk({logical_chunk},{json.dumps({name: {}})});\n",
            encoding="utf-8",
        )

    inventory_path = root / "preset-inventory.csv"
    inventory_path.write_text(
        "name,pack,chunk\n" + "".join(
            f"{name},presets-extra,{index}\n" for index, name in enumerate(names)
        ),
        encoding="utf-8",
    )
    removed_path = root / "removed-presets.csv"
    removed_path.write_text("name,pack,chunk,commit,date,subject\n", encoding="utf-8")
    manifest_path = root / "experimental-presets.json"
    manifest_path.write_text(
        json.dumps({
            "presets": [
                {
                    "displayName": name,
                    "sourceName": name.split("] ", 1)[1],
                    "logicalChunk": index,
                    "mainlineMatches": [],
                    "normalizedNameMatches": [],
                }
                for index, name in enumerate(names)
            ]
        }),
        encoding="utf-8",
    )
    exclusions_path = root / "experimental-exclusions.json"
    exclusions_path.write_text("[]\n", encoding="utf-8")
    decisions_path = root / "decisions.json"
    decisions_path.write_text(json.dumps(names), encoding="utf-8")
    return {
        "output_dir": output_dir,
        "inventory": inventory_path,
        "removed": removed_path,
        "manifest": manifest_path,
        "exclusions": exclusions_path,
        "decisions": decisions_path,
    }


class RemoveExperimentalPresetsTests(unittest.TestCase):
    def test_removes_numbered_batches_and_updates_generated_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = write_fixture_files(root)

            with (
                patch.object(TOOL, "OUT_DIR", paths["output_dir"]),
                patch.object(TOOL, "INDEX_PATH", paths["output_dir"] / "index.js"),
                patch.object(TOOL, "CSV_PATH", paths["inventory"]),
                patch.object(TOOL, "REMOVED_CSV_PATH", paths["removed"]),
                patch.object(TOOL, "MANIFEST_PATH", paths["manifest"]),
                patch.object(TOOL, "EXCLUSIONS_PATH", paths["exclusions"]),
                patch.object(
                    sys,
                    "argv",
                    [
                        str(TOOL_PATH), "--decisions", str(paths["decisions"]),
                        "--allow-unmatched", "--reason", "curation approved",
                    ],
                ),
            ):
                self.assertEqual(TOOL.main(), 0)

            updated_index = json.loads(
                (paths["output_dir"] / "index.js").read_text(encoding="utf-8")
                [len(TOOL.INDEX_PREFIX):-2]
            )
            self.assertEqual(updated_index["chunks"], [[], [], []])
            self.assertEqual(
                json.loads(paths["manifest"].read_text(encoding="utf-8"))["presets"],
                [],
            )
            exclusions = json.loads(paths["exclusions"].read_text(encoding="utf-8"))
            self.assertEqual(len(exclusions), 3)
            self.assertEqual(
                paths["removed"].read_text(encoding="utf-8").count("curation approved"),
                3,
            )


if __name__ == "__main__":
    unittest.main()
