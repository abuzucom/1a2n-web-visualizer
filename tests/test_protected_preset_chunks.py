"""Require owner review for the generated preset chunks.

The pages load every file under src/presets-extra/ as a classic script.
Butterchurn compiles each preset equation with new Function. A chunk file is
therefore executable code like src/js/ and src/vendor/.
"""

import unittest

from scripts.check_protected_files import is_protected


class ProtectedPresetChunkTests(unittest.TestCase):
    def test_protects_preset_index_and_chunk_files(self) -> None:
        for path in (
            "src/presets-extra/index.js",
            "src/presets-extra/chunk-000.js",
            "src/presets-extra/chunk-9000.js",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))


if __name__ == "__main__":
    unittest.main()
