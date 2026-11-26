"""Review callers trust a prior verdict check only from their own workflow_run execution.

Any workflow with checks: write can publish a check with a VERDICT title. A
pull request workflow runs with a pull_request event. A review skip needs a
check suite from the caller's own workflow_run execution.
"""
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CALLERS = {
    ".github/workflows/quality-review-pr.yml": "resolve",
    ".github/workflows/security-review-pr.yml": "resolve-pr",
}
PRODUCER_MARKERS = ("check_suite_id", "workflow_run", "run.path")


def _resolve_job(path: str, job_name: str) -> dict:
    """Return one caller's resolve job mapping."""
    document = yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))
    return document["jobs"][job_name]


class ReviewVerdictProducerTest(unittest.TestCase):
    """Each caller verifies the producer of a prior verdict check."""

    def test_prefilter_verifies_caller_producer(self) -> None:
        for path, job_name in CALLERS.items():
            with self.subTest(path=path):
                job = _resolve_job(path, job_name)
                script = job["steps"][0]["with"]["script"]
                for marker in PRODUCER_MARKERS:
                    self.assertIn(marker, script)
                self.assertIn(path, script)
                self.assertEqual(job["permissions"].get("actions"), "read")


if __name__ == "__main__":
    unittest.main()
