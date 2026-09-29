"""Keep attacker-controlled expressions out of workflow run scripts."""
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# Contexts a pull request author controls. GitHub expands `${{ }}` into the
# script text before bash parses it, so any of these inside `run:` executes
# shell metacharacters from a branch name, title, or body. Pass them through
# `env:` instead, where bash sees them as data.
EXPRESSION = re.compile(r"\$\{\{[^}]*\}\}")
UNTRUSTED_CONTEXT = re.compile(
    r"\b(?:"
    r"github\.head_ref"
    r"|github\.event\.pull_request\.head\.ref"
    r"|github\.event\.pull_request\.head\.label"
    r"|github\.event\.pull_request\.title"
    r"|github\.event\.pull_request\.body"
    r"|github\.event\.(?:issue|comment|review|review_comment)\.(?:title|body)"
    r"|github\.event\.head_commit\.(?:message|author\.name|author\.email)"
    r"|github\.event\.workflow_run\.head_branch"
    r")\b"
)


def find_untrusted_run_expressions(workflow: dict) -> list:
    """Return (job, step, expression) for each untrusted `run:` interpolation."""
    findings = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            script = step.get("run", "")
            label = step.get("name", f"step {index}")
            findings.extend(
                (job_name, label, expression)
                for expression in EXPRESSION.findall(script)
                if UNTRUSTED_CONTEXT.search(expression)
            )
    return findings


class WorkflowScriptInjectionTest(unittest.TestCase):
    """Reject PR-controlled expressions expanded into shell scripts."""

    def test_detector_flags_head_ref_in_run(self) -> None:
        workflow = {"jobs": {"j": {"steps": [
            {"name": "s", "run": 'python3 check.py "${{ github.head_ref }}"'},
        ]}}}
        self.assertEqual(
            find_untrusted_run_expressions(workflow),
            [("j", "s", "${{ github.head_ref }}")],
        )

    def test_detector_allows_env_indirection(self) -> None:
        workflow = {"jobs": {"j": {"steps": [
            {"name": "s", "env": {"HEAD": "${{ github.head_ref }}"},
             "run": 'python3 check.py "$HEAD"'},
        ]}}}
        self.assertEqual(find_untrusted_run_expressions(workflow), [])

    def test_workflows_do_not_interpolate_untrusted_context(self) -> None:
        paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        self.assertTrue(paths, "no workflow files found")
        for path in paths:
            with self.subTest(workflow=path.name):
                workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertEqual(find_untrusted_run_expressions(workflow), [])


if __name__ == "__main__":
    unittest.main()
