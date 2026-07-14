import tempfile
import unittest
from pathlib import Path

from scripts.check_action_pins import find_failures


PINNED_ACTION = "a" * 40


class CheckActionPinsTests(unittest.TestCase):
    def test_checks_yml_and_yaml_and_both_uses_forms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow_dir = Path(directory)
            (workflow_dir / "checks.yml").write_text(
                f"steps:\n  - uses: actions/checkout@{PINNED_ACTION}\n",
                encoding="utf-8",
            )
            (workflow_dir / "deploy.yaml").write_text(
                f"steps:\n  uses: actions/deploy@{PINNED_ACTION}\n",
                encoding="utf-8",
            )

            self.assertEqual(find_failures(workflow_dir), [])

    def test_rejects_mutable_refs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow_dir = Path(directory)
            (workflow_dir / "checks.yml").write_text(
                "steps:\n  - uses: actions/checkout@v7\n",
                encoding="utf-8",
            )

            failures = find_failures(workflow_dir)

            self.assertEqual(len(failures), 1)
            self.assertIn("must use a 40-character commit SHA", failures[0])

    def test_allows_local_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow_dir = Path(directory)
            (workflow_dir / "checks.yml").write_text(
                "steps:\n  - uses: ./actions/local\n",
                encoding="utf-8",
            )

            self.assertEqual(find_failures(workflow_dir), [])


if __name__ == "__main__":
    unittest.main()
