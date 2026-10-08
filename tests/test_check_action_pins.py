#!/usr/bin/env python3
"""Test workflow action pin validation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_action_pins


class ActionPinTest(unittest.TestCase):
    """External actions require immutable revisions."""

    def test_full_sha_passes(self):
        text = "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@" + "a" * 40
        self.assertEqual(check_action_pins.find_violations(text, "x.yml"), [])

    def test_tag_fails(self):
        found = check_action_pins.find_violations(
            "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n", "x.yml")
        self.assertEqual(len(found), 1)

    def test_local_reference_passes(self):
        text = "jobs:\n  test:\n    uses: ./.github/workflows/reuse.yml\n"
        self.assertEqual(check_action_pins.find_violations(text, "x.yml"), [])

    def test_container_digest_passes(self):
        text = "jobs:\n  test:\n    steps:\n      - uses: docker://alpine@sha256:" + "a" * 64
        self.assertEqual(check_action_pins.find_violations(text, "x.yml"), [])

    def test_container_tag_fails(self):
        text = "jobs:\n  test:\n    steps:\n      - uses: docker://alpine:latest\n"
        found = check_action_pins.find_violations(text, "x.yml")
        self.assertEqual(len(found), 1)

    def test_repository_workflows_use_full_sha_pins(self):
        """All external actions in this repository's workflows use full SHAs."""
        root = Path(__file__).resolve().parent.parent
        workflow_root = root / ".github" / "workflows"
        violations = []
        for path in sorted(
            (*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))
        ):
            violations.extend(check_action_pins.find_violations(
                path.read_text(encoding="utf-8"), str(path)))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
