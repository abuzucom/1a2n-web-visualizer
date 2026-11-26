#!/usr/bin/env python3
"""Cover the foucault pull request security review wiring.

Adapted from the agents template test of the same name. This repository pins
a newer agents-personas release than the template. docs/template-drift.md
records the difference.
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "security-review-pr.yml"
# agents-personas 1.0.0. The uses: pin and personas_ref must name this commit.
PINNED_COMMIT = "1649e5c9710fd85d6cca12006e344af27a5404a6"
REUSABLE_WORKFLOW = (
    "abuzucom/agents-personas/.github/workflows/foucault-security-review.yml"
)
CHECK_NAME = "foucault / security"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
RESOLVED_INPUTS = (
    "pr_number",
    "base_sha",
    "head_sha",
    "head_repo_url",
    "head_repo_full_name",
)
REVIEW_PERMISSIONS = {
    "checks": "write",
    "contents": "read",
    "pull-requests": "write",
}


class SecurityReviewWiringTest(unittest.TestCase):
    """Keep the foucault caller workflow pinned, scoped, and complete."""

    def setUp(self):
        self.text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)
        self.jobs = self.workflow["jobs"]

    def test_workflow_parses_and_exists(self):
        self.assertTrue(WORKFLOW_PATH.is_file())
        self.assertIsInstance(self.workflow, dict)

    def test_triggers_after_immutable_compliance(self):
        # PyYAML 1.1 parses a bare `on:` key as the boolean True, so match the
        # trigger block as raw text instead of indexing the parsed mapping.
        self.assertIn("workflow_run:", self.text)
        self.assertIn("workflows: [Immutable Compliance]", self.text)
        self.assertIn("types: [completed]", self.text)

    def test_review_commit_pinning(self):
        review_job = self.jobs["review"]
        self.assertEqual(
            review_job["uses"], f"{REUSABLE_WORKFLOW}@{PINNED_COMMIT}")
        self.assertEqual(review_job["with"]["personas_ref"], PINNED_COMMIT)
        self.assertTrue(FULL_SHA.fullmatch(PINNED_COMMIT))

    def test_old_reviewer_absent(self):
        self.assertNotIn("abuzucom/foucault/", self.text)
        self.assertNotIn("audit_ref", self.text)
        self.assertNotIn("ci/call_model.py", self.text)

    def test_review_passes_resolved_pull(self):
        review_with = self.jobs["review"]["with"]
        for name in RESOLVED_INPUTS:
            self.assertEqual(
                review_with[name],
                f"${{{{ needs.resolve-pr.outputs.{name} }}}}",
            )

    def test_review_secret_mapping(self):
        self.assertEqual(
            self.jobs["review"]["secrets"],
            {"MODEL_API_KEY": "${{ secrets.OLLAMA_API_KEY }}"},
        )
        self.assertNotIn("secrets: inherit", self.text)

    def test_review_fails_closed(self):
        self.assertTrue(self.jobs["review"]["with"]["fail_on_block"])

    def test_review_skips_reviewed_head(self):
        self.assertIn(
            "needs.resolve-pr.outputs.already_reviewed != 'true'",
            self.jobs["review"]["if"],
        )
        script = self.jobs["resolve-pr"]["steps"][0]["with"]["script"]
        self.assertIn(f'check_name: "{CHECK_NAME}"', script)
        self.assertIn("VERDICT: (APPROVE|BLOCK|NEEDS-HUMAN)", script)

    def test_engine_owns_fork_skip(self):
        # The engine publishes a skipped check for a fork pull request and
        # withholds the provider key, so the caller holds no fork job.
        self.assertNotIn("fork-review-skipped", self.jobs)
        self.assertNotIn("fork_review", self.jobs["review"]["with"])

    def test_jobs_declare_least_privilege_permissions(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertNotIn(
            "write", self.jobs["resolve-pr"]["permissions"].values())
        self.assertEqual(
            self.jobs["review"]["permissions"], REVIEW_PERMISSIONS)

    def test_github_script_sha_pin(self):
        step = self.jobs["resolve-pr"]["steps"][0]
        action, _, revision = step["uses"].partition("@")
        self.assertEqual(action, "actions/github-script")
        self.assertTrue(FULL_SHA.fullmatch(revision.split()[0]))


if __name__ == "__main__":
    unittest.main()
