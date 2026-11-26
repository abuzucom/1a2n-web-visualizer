"""Reviewed pull_request_target workflows fail closed on a job that is not a mapping."""

import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_compliance_tree

WORKFLOW_PATH = ".github/workflows/x.yml"
WORKFLOW_TEMPLATE = """name: x
"on":
  pull_request_target:
    types: [labeled]
permissions:
  contents: read
jobs:
  broken: {job}
"""
NON_MAPPING_JOBS = {"scalar": "just-a-string", "list": "[a, b]", "null": "null"}
EXPECTED_FINDING = (f"{WORKFLOW_PATH}: reviewed pull_request_target "
                    "has a non-mapping job value")


class ReviewedNonMappingJobTest(unittest.TestCase):
    """The reviewed rule set adds one finding per job value that is not a mapping."""

    def test_nonmapping_job_adds_finding(self) -> None:
        reviewed = check_compliance_tree.ReviewedWorkflow(
            secrets=frozenset(), reusable_workflows=frozenset())
        for label, job in NON_MAPPING_JOBS.items():
            with self.subTest(job=label):
                text = WORKFLOW_TEMPLATE.format(job=job)
                document = yaml.safe_load(text)
                violations = check_compliance_tree._reviewed_pull_target_violations(
                    document, text, WORKFLOW_PATH, reviewed)
                self.assertEqual(violations, [EXPECTED_FINDING])


if __name__ == "__main__":
    unittest.main()
