#!/usr/bin/env python3
"""Hold the repository's real workflows to the action pin rules."""
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_action_pins

WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
DEPLOY_WORKFLOW = WORKFLOW_DIR / "deploy.yml"
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
    """The deploy retry must run the same action revision as the first attempt."""

    def test_detector_flags_a_partial_bump(self) -> None:
        workflow = {"jobs": {"deploy": {"steps": [
            {"uses": DEPLOY_PAGES_ACTION + "a" * 40},
            {"uses": DEPLOY_PAGES_ACTION + "b" * 40},
        ]}}}
        self.assertEqual(len(set(deploy_pages_references(workflow))), 2)

    def test_first_attempt_and_retry_share_one_revision(self) -> None:
        workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
        references = deploy_pages_references(workflow)
        # deploy.yml tolerates one Pages failure, then retries. Both steps
        # must move together or the retry runs a different action version.
        self.assertGreaterEqual(len(references), 2)
        self.assertEqual(len(set(references)), 1, references)


if __name__ == "__main__":
    unittest.main()
