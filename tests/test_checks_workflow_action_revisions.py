#!/usr/bin/env python3
"""Hold checks.yml to one revision per action that appears in several jobs."""
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "checks.yml"
# Upload and download jobs exchange coverage artifacts. A partial bump would run
# one side on a different artifact client version than the other.
SHARED_REVISION_ACTIONS = (
    "actions/setup-node",
    "actions/upload-artifact",
    "actions/download-artifact",
)


def action_references(workflow: dict, action: str) -> list:
    """Return every reference to an action across a workflow's job steps."""
    prefix = action + "@"
    references = []
    for job in (workflow.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            uses = step.get("uses", "")
            if uses.startswith(prefix):
                references.append(uses)
    return references


class ChecksWorkflowRevisionTest(unittest.TestCase):
    """Dependabot group bumps must move every use of an action together."""

    def test_detector_flags_a_partial_bump(self) -> None:
        workflow = {"jobs": {
            "first": {"steps": [{"uses": "actions/setup-node@" + "a" * 40}]},
            "second": {"steps": [{"uses": "actions/setup-node@" + "b" * 40}]},
        }}
        references = action_references(workflow, "actions/setup-node")
        self.assertEqual(len(set(references)), 2)

    def test_detector_ignores_other_actions(self) -> None:
        workflow = {"jobs": {"only": {"steps": [
            {"uses": "actions/checkout@" + "c" * 40},
            {"run": "echo no uses key"},
        ]}}}
        self.assertEqual(action_references(workflow, "actions/setup-node"), [])

    def test_each_shared_action_uses_one_revision(self) -> None:
        workflow = yaml.safe_load(CHECKS_WORKFLOW.read_text(encoding="utf-8"))
        for action in SHARED_REVISION_ACTIONS:
            with self.subTest(action=action):
                references = action_references(workflow, action)
                self.assertGreaterEqual(len(references), 2, references)
                self.assertEqual(len(set(references)), 1, references)


if __name__ == "__main__":
    unittest.main()
