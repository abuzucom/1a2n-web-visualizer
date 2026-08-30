import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load_tool(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TextureBundleMergeTests(unittest.TestCase):
    def test_write_texture_bundle_merges_with_existing_vendored_images(self):
        tool = load_tool("import-nestdrop-presets.py")

        existing_images = {
            "seaweed": {"data": "data:image/jpeg;base64,AAA", "width": 1, "height": 1},
        }
        new_images = {
            "clouds": {"data": "data:image/jpeg;base64,BBB", "width": 2, "height": 2},
        }

        fake_splitter = mock.Mock()
        fake_splitter.read_images.return_value = dict(existing_images)
        recorded = {}

        def fake_write_parts(images, dry_run):
            recorded["images"] = images

        fake_splitter.write_parts.side_effect = fake_write_parts

        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "experimental-textures.json"
            manifest_path.write_text(
                json.dumps([{"name": "seaweed", "sha256": "x", "width": 1, "height": 1}]),
                encoding="utf-8",
            )

            with (
                mock.patch.object(tool, "load_texture_splitter", return_value=fake_splitter),
                mock.patch.object(tool, "TEXTURE_MANIFEST_PATH", manifest_path),
            ):
                tool.write_texture_bundle(
                    new_images,
                    [{"name": "clouds", "sha256": "y", "width": 2, "height": 2}],
                )

            written_records = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertIn(
            "seaweed", recorded["images"],
            "a new batch's texture write must not drop previously vendored textures",
        )
        self.assertIn("clouds", recorded["images"])
        names = {record["name"] for record in written_records}
        self.assertEqual(
            names, {"seaweed", "clouds"},
            "the texture manifest must accumulate records across batches, not be replaced",
        )


if __name__ == "__main__":
    unittest.main()
