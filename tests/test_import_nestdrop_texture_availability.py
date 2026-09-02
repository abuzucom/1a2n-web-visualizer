import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_tool(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComputeAvailableTexturesTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool("import-nestdrop-presets.py")

    def test_includes_previously_vendored_textures(self):
        available = self.tool.compute_available_textures(
            texture_images={},
            previously_vendored={"OIcafewall": {"data": "x", "width": 1, "height": 1}},
        )
        self.assertIn(
            "oicafewall", available,
            "a texture already vendored by a prior batch must remain available "
            "even when the current batch's own archive does not resupply it",
        )

    def test_existing_texture_names_matches_lowercased_sampler_reference(self):
        self.assertIn("cloudsImage", self.tool.EXISTING_TEXTURE_NAMES)
        available = self.tool.compute_available_textures(
            texture_images={}, previously_vendored={},
        )
        self.assertIn(
            "cloudsimage", available,
            "sampler_cloudsImage lowercases to 'cloudsimage'; the mixed-case "
            "EXISTING_TEXTURE_NAMES entry must still match it",
        )

    def test_includes_current_batch_textures(self):
        available = self.tool.compute_available_textures(
            texture_images={"NewTexture": {"data": "x", "width": 1, "height": 1}},
            previously_vendored={},
        )
        self.assertIn("newtexture", available)


if __name__ == "__main__":
    unittest.main()
