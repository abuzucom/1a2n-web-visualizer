#!/usr/bin/env python3
"""Cover the label-requested agents-personas review wiring.

Adapted from the agents template test of the same name. This repository pins
a newer agents-personas release than the template. docs/template-drift.md
records the difference.
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "persona-review-labels.yml"
# agents-personas 1.0.0. Every uses: pin and personas_ref names this commit.
PINNED_COMMIT = "1649e5c9710fd85d6cca12006e344af27a5404a6"
WRAPPER_PREFIX = "abuzucom/agents-personas/.github/workflows/"
PERSONA_WRAPPERS = {
    "adorno": "adorno-ui-review.yml",
    "generay": "generay-time-review.yml",
    "havel": "havel-privacy-review.yml",
}
FULL_SHA = re.compile(r"[0-9a-f]{40}")
REVIEW_PERMISSIONS = {
    "checks": "write",
    "contents": "read",
    "pull-requests": "write",
}
STOP_LABEL_CONDITION = (
    "github.event.action != 'unlabeled' || "
    "github.event.label.name == 'stop-requested'"
)


class PersonaLabelReviewWiringTest(unittest.TestCase):
    """Keep the label caller pinned, label gated, and least privileged."""

    def setUp(self):
        self.text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)
        self.jobs = self.workflow["jobs"]

    def test_workflow_parses_and_exists(self):
        self.assertTrue(WORKFLOW_PATH.is_file())
        self.assertIsInstance(self.workflow, dict)

    def test_triggers_on_label_and_push(self):
        # PyYAML 1.1 parses a bare `on:` key as the boolean True, so match the
        # trigger block as raw text instead of indexing the parsed mapping.
        self.assertIn("pull_request_target:", self.text)
        self.assertIn("types: [labeled, synchronize, unlabeled]", self.text)
        self.assertNotIn("workflow_run:", self.text)

    def test_jobs_cover_each_persona(self):
        self.assertEqual(set(self.jobs), set(PERSONA_WRAPPERS))

    def test_wrapper_single_commit_pin(self):
        for persona, wrapper in PERSONA_WRAPPERS.items():
            job = self.jobs[persona]
            self.assertEqual(
                job["uses"], f"{WRAPPER_PREFIX}{wrapper}@{PINNED_COMMIT}")
            self.assertEqual(job["with"]["personas_ref"], PINNED_COMMIT)
        self.assertTrue(FULL_SHA.fullmatch(PINNED_COMMIT))

    def test_jobs_require_scan_label(self):
        for persona in PERSONA_WRAPPERS:
            condition = " ".join(self.jobs[persona]["if"].split())
            self.assertIn(
                "contains(github.event.pull_request.labels.*.name, "
                f"'{persona}-scan-requested')",
                condition,
            )
            self.assertIn(STOP_LABEL_CONDITION, condition)

    def test_secret_mapping_only_provider(self):
        for persona in PERSONA_WRAPPERS:
            self.assertEqual(
                self.jobs[persona]["secrets"],
                {"MODEL_API_KEY": "${{ secrets.OLLAMA_API_KEY }}"},
            )
        self.assertNotIn("secrets: inherit", self.text)

    def test_jobs_declare_least_privilege_permissions(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        for persona in PERSONA_WRAPPERS:
            self.assertEqual(
                self.jobs[persona]["permissions"], REVIEW_PERMISSIONS)

    def test_no_step_runs_in_caller(self):
        # pull_request_target holds the provider key. The caller runs no
        # step and checks out nothing, so no pull request code executes.
        for persona in PERSONA_WRAPPERS:
            self.assertNotIn("steps", self.jobs[persona])
        self.assertNotIn("actions/checkout", self.text)

    def test_havel_reviews_baseline_scope(self):
        self.assertEqual(self.jobs["havel"]["with"]["regimes"], "")


if __name__ == "__main__":
    unittest.main()
