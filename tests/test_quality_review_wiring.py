#!/usr/bin/env python3
"""Cover the euler pull request quality review wiring.

Adapted from the agents template test of the same name. This repository pins
a newer agents-personas release than the template. Its Immutable Compliance
workflow runs on pull_request instead of pull_request_target.
docs/template-drift.md records both differences.
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "quality-review-pr.yml"
# agents-personas 1.0.0. The uses: pin and personas_ref must name this commit.
PINNED_COMMIT = "1649e5c9710fd85d6cca12006e344af27a5404a6"
REUSABLE_WORKFLOW = (
    "abuzucom/agents-personas/.github/workflows/euler-quality-review.yml"
)
CHECK_NAME = "euler / quality"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
UPSTREAM_WORKFLOWS = ("Convention Sync Check", "Immutable Compliance")
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


class QualityReviewWiringTest(unittest.TestCase):
    """Keep the euler caller workflow pinned, gated, and fork safe."""

    def setUp(self):
        self.text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)
        self.jobs = self.workflow["jobs"]

    def test_workflow_parses_and_exists(self):
        self.assertTrue(WORKFLOW_PATH.is_file())
        self.assertIsInstance(self.workflow, dict)

    def test_upstream_workflow_names_exist(self):
        # A workflow_run trigger naming a missing workflow never fires.
        names = set()
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
            names.add(parsed.get("name"))
        for upstream in UPSTREAM_WORKFLOWS:
            self.assertIn(upstream, names)

    def test_triggers_after_tests_and_compliance(self):
        # PyYAML 1.1 parses a bare `on:` key as the boolean True, so match the
        # trigger block as raw text instead of indexing the parsed mapping.
        self.assertIn("workflow_run:", self.text)
        self.assertIn(
            'workflows: ["Convention Sync Check", "Immutable Compliance"]',
            self.text,
        )
        self.assertIn("types: [completed]", self.text)

    def test_review_waits_for_upstream(self):
        review_if = self.jobs["review"]["if"]
        self.assertIn("needs.resolve.outputs.tests_passed == 'true'", review_if)
        self.assertIn(
            "needs.resolve.outputs.compliance_passed == 'true'", review_if)
        self.assertIn(
            "needs.resolve.outputs.already_reviewed == 'false'", review_if)
        script = self.jobs["resolve"]["steps"][0]["with"]["script"]
        for upstream in UPSTREAM_WORKFLOWS:
            self.assertIn(f"'{upstream}'", script)

    def test_upstream_run_lookup_matches_trigger_events(self):
        # The resolve step filters upstream runs by event. A wrong event finds
        # no run. The review then never starts.
        script = self.jobs["resolve"]["steps"][0]["with"]["script"]
        for upstream in UPSTREAM_WORKFLOWS:
            with self.subTest(upstream=upstream):
                self.assertRegex(
                    script,
                    rf"latestRun\(\s*'{upstream}', 'pull_request'\)",
                )
        self.assertNotIn("'pull_request_target')", script)
        compliance = yaml.safe_load((
            ROOT / ".github" / "workflows" / "immutable-conflict-check.yml"
        ).read_text(encoding="utf-8"))
        # PyYAML 1.1 parses a bare `on:` key as the boolean True.
        triggers = compliance.get("on", compliance.get(True))
        self.assertIn("pull_request", triggers)
        self.assertNotIn("pull_request_target", triggers)

    def test_review_skips_reviewed_head(self):
        script = self.jobs["resolve"]["steps"][0]["with"]["script"]
        self.assertIn(f"check_name: '{CHECK_NAME}'", script)
        self.assertIn("VERDICT: (APPROVE|BLOCK|NEEDS-HUMAN)", script)

    def test_review_job_single_commit_pin(self):
        review_job = self.jobs["review"]
        self.assertEqual(
            review_job["uses"], f"{REUSABLE_WORKFLOW}@{PINNED_COMMIT}")
        self.assertEqual(review_job["with"]["personas_ref"], PINNED_COMMIT)
        self.assertTrue(FULL_SHA.fullmatch(PINNED_COMMIT))

    def test_old_reviewer_absent(self):
        self.assertNotIn("abuzucom/euler/", self.text)
        self.assertNotIn("quality_ref", self.text)
        review_with = self.jobs["review"]["with"]
        self.assertNotIn("pr_title", review_with)
        self.assertNotIn("pr_body", review_with)

    def test_review_passes_resolved_pull(self):
        review_with = self.jobs["review"]["with"]
        for name in RESOLVED_INPUTS:
            self.assertEqual(
                review_with[name],
                f"${{{{ needs.resolve.outputs.{name} }}}}",
            )

    def test_review_excludes_test_fixtures(self):
        self.assertEqual(
            self.jobs["review"]["with"]["exclude_paths"], "tests/**")

    def test_review_job_secret_mapping(self):
        self.assertEqual(
            self.jobs["review"]["secrets"],
            {"MODEL_API_KEY": "${{ secrets.OLLAMA_API_KEY }}"},
        )
        self.assertNotIn("secrets: inherit", self.text)

    def test_review_job_fails_closed(self):
        self.assertTrue(self.jobs["review"]["with"]["fail_on_block"])

    def test_engine_owns_fork_skip(self):
        # The engine publishes a skipped check for a fork pull request and
        # withholds the provider key, so the caller holds no fork job.
        self.assertNotIn("fork-review-skipped", self.jobs)
        self.assertNotIn("fork_review", self.jobs["review"]["with"])
        reusable_calls = [
            name for name, job in self.jobs.items()
            if str(job.get("uses", "")).startswith(REUSABLE_WORKFLOW)
        ]
        self.assertEqual(reusable_calls, ["review"])

    def test_jobs_declare_least_privilege_permissions(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertNotIn("write", self.jobs["resolve"]["permissions"].values())
        self.assertEqual(
            self.jobs["review"]["permissions"], REVIEW_PERMISSIONS)

    def test_github_script_actions_pinned(self):
        step = self.jobs["resolve"]["steps"][0]
        action, _, revision = step["uses"].partition("@")
        self.assertEqual(action, "actions/github-script")
        self.assertTrue(FULL_SHA.fullmatch(revision.split()[0]))


if __name__ == "__main__":
    unittest.main()
