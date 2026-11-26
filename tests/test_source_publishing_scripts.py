"""Source publishing scripts live in the source repository's local script list.

An adopter takes hooks/workflow-scripts.txt byte for byte. That shared list
must name no script that only the source repository ships.
"""
import unittest
from pathlib import Path

from tests.test_command_execution_gate import _load_gate_module

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PUBLISHING_SCRIPT = "scripts/release.py"
CHECK_TAG_COMMAND = "python scripts/release.py check-tag v1.0.0"


class SourcePublishingScriptListTest(unittest.TestCase):
    """The shared list omits release.py and the local list supplies it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = _load_gate_module()

    def test_shared_list_omits_release(self) -> None:
        scripts = {script for script, _pattern, _verdict in self.gate._load_shared_scripts()}
        self.assertNotIn(SOURCE_PUBLISHING_SCRIPT, scripts)


if __name__ == "__main__":
    unittest.main()
