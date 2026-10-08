#!/usr/bin/env python3
"""Verify reviewed GitHub Action release pins against workflow references."""
import unittest
from pathlib import Path


WORKFLOW_ROOT = Path(__file__).resolve().parent.parent / ".github" / "workflows"
REVIEWED_ACTION_PINS = {
    "actions/checkout": (
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "v7.0.1",
        {"v7", "v7.0.1"},
    ),
    "actions/setup-python": (
        "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "v7.0.0",
        {"v7.0.0"},
    ),
    "actions/github-script": (
        "3a2844b7e9c422d3c10d287c895573f7108da1b3",
        "v9.0.0",
        {"v9.0.0"},
    ),
    "actions/upload-code-coverage": (
        "2b21a77928be8d5168c2b9581a67f2adbebacc52",
        "v1.4.4",
        {"v1.4.4"},
    ),
}


class ActionVersionPinTest(unittest.TestCase):
    """Workflows use only the reviewed SHA for each listed action release."""

    def test_workflow_sha_pins_match_reviewed_release_allowlist(self):
        references = {action: [] for action in REVIEWED_ACTION_PINS}
        workflow_paths = sorted(WORKFLOW_ROOT.glob("*.yml"))
        workflow_paths.extend(sorted(WORKFLOW_ROOT.glob("*.yaml")))

        for path in workflow_paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                if "uses:" not in line:
                    continue
                reference, comment = self._parse_action_reference(line)
                action, separator, revision = reference.partition("@")
                if action not in REVIEWED_ACTION_PINS:
                    continue
                self.assertTrue(separator, f"Missing SHA in {path}: {line}")
                references[action].append((revision, comment, path))

        for action, (sha, version, comment_versions) in REVIEWED_ACTION_PINS.items():
            self.assertTrue(references[action], f"No workflow reference for {action}")
            for revision, comment, path in references[action]:
                self.assertEqual(revision, sha, f"Unexpected {action} SHA in {path}")
                if comment:
                    self.assertIn(
                        comment,
                        comment_versions,
                        f"Version comment for {action} does not match {version} in {path}",
                    )

    @staticmethod
    def _parse_action_reference(line):
        """Return a workflow action reference and its optional version comment."""
        _, _, value = line.partition("uses:")
        reference, marker, comment = value.partition("#")
        action_reference = reference.strip().split()[0]
        return action_reference, comment.strip() if marker else ""


if __name__ == "__main__":
    unittest.main()
