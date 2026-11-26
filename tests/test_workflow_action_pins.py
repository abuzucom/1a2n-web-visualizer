#!/usr/bin/env python3
"""Hold the repository's real workflows to the action pin rules."""
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_action_pins

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
DEPLOY_PAGES_ACTION = "actions/deploy-pages@"


def deploy_pages_references(workflow: dict) -> list:
    """Return every actions/deploy-pages reference in a workflow's steps."""
    references = []
    for job in (workflow.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            uses = step.get("uses", "")
            if uses.startswith(DEPLOY_PAGES_ACTION):
                references.append(uses)
    return references


class RepositoryWorkflowPinTest(unittest.TestCase):
    """Dependabot bumps must leave every workflow immutably pinned."""

    def test_every_workflow_pins_external_actions(self) -> None:
        paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        self.assertTrue(paths, "no workflow files found")
        for path in paths:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(check_action_pins.find_violations(text, path.name), [])


class DeployRetryPinTest(unittest.TestCase):
    """The repository holds no Pages deploy action that could drift."""

    def test_detector_flags_a_partial_bump(self) -> None:
        workflow = {"jobs": {"deploy": {"steps": [
            {"uses": DEPLOY_PAGES_ACTION + "a" * 40},
            {"uses": DEPLOY_PAGES_ACTION + "b" * 40},
        ]}}}
        self.assertEqual(len(set(deploy_pages_references(workflow))), 2)

    def test_no_pages_deploy_action(self) -> None:
        """No workflow references a pages deploy action."""
        paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        for path in paths:
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            with self.subTest(workflow=path.name):
                self.assertEqual(deploy_pages_references(workflow), [])


if __name__ == "__main__":
    unittest.main()
