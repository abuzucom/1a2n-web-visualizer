#!/usr/bin/env python3
"""Verify reviewed GitHub Action release pins against workflow references."""
import unittest
from pathlib import Path


WORKFLOW_ROOT = Path(__file__).resolve().parent.parent / ".github" / "workflows"
# Each action maps every reviewed SHA to its release and accepted comments.
# The adopted abuzucom/agents workflows keep the template pins because the
# immutable checker trusts only those steps. The repository workflows keep
# the repository pins. docs/template-drift.md records the split.
REVIEWED_ACTION_PINS = {
    "actions/checkout": {
        "3d3c42e5aac5ba805825da76410c181273ba90b1": ("v7.0.1", {"v7", "v7.0.1"}),
        "11d5960a326750d5838078e36cf38b85af677262": ("v4.4.0", {"v4.4.0"}),
    },
    "actions/setup-python": {
        "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0": ("v7.1.0", {"v7.1.0"}),
        "a26af69be951a213d495a4c3e4e4022e16d87065": ("v5.6.0", {"v5.6.0"}),
    },
    "actions/github-script": {
        "3a2844b7e9c422d3c10d287c895573f7108da1b3": ("v9.0.0", {"v9.0.0"}),
        "f28e40c7f34bde8b3046d885e986cb6290c5673b": ("v7.1.0", {"v7.1.0"}),
    },
    "actions/upload-code-coverage": {
        "2b21a77928be8d5168c2b9581a67f2adbebacc52": ("v1.4.4", {"v1.4.4"}),
    },
}


class ActionVersionPinTest(unittest.TestCase):
    """Workflows use only the reviewed SHA for each listed action release."""

    def test_workflow_pins_match_reviewed_releases(self):
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

        for action, releases in REVIEWED_ACTION_PINS.items():
            self.assertTrue(references[action], f"No workflow reference for {action}")
            for revision, comment, path in references[action]:
                self.assertIn(revision, releases, f"Unexpected {action} SHA in {path}")
                version, comment_versions = releases[revision]
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
