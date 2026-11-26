#!/usr/bin/env python3
"""Pin the retained foucault 3.3.14 review adapter copies.

The agents-personas engine supplies its own adapter. The old foucault caller
on the base branch still runs these copies until the persona callers reach
`main`. The template upgrade deletes the copies together with this test.
"""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# SHA-256 of each adapter file, line endings normalized. ci/call_model.py,
# ci/run_model_command.py, and scripts/check_pr_review_response.py carry
# local lint fixes over foucault 3.3.14 (see docs/template-drift.md).
ADAPTER_DIGESTS = {
    "ci/build_pr_case.py": (
        "5af5b24708f7d3c5ce0c07b84e6627d3a6b5f7151a57f2b07569553e941e7223"
    ),
    "ci/run_model_command.py": (
        "36b04d0514430cb3b6330c2c69a63a88aa161dc5fb11e01dbe91fbcac8aa73fe"
    ),
    "ci/call_model.py": (
        "9075cdd498e252967d0cb806848efb2edf800f49dc40a6ddc5f6026cb518dd23"
    ),
    "ci/model_providers.json": (
        "9544f1a5cd6602cb1114b482b200fd286cdfcdb17a918034499534e6e124db06"
    ),
    "scripts/check_pr_review_response.py": (
        "2037854faf4ced5908d2cddfc217fa05dcff12b9422a80ca3eb79325e90160ac"
    ),
}


class ReviewAdapterDigestTest(unittest.TestCase):
    """Keep the retained adapter copies verbatim until the template upgrade."""

    def test_adapter_files_exist(self) -> None:
        for relative_path in ADAPTER_DIGESTS:
            with self.subTest(path=relative_path):
                self.assertTrue(
                    (ROOT / relative_path).is_file(),
                    f"missing vendored adapter file: {relative_path}",
                )

    def test_adapter_files_match_recorded_digests(self) -> None:
        for relative_path, expected in ADAPTER_DIGESTS.items():
            with self.subTest(path=relative_path):
                content = (ROOT / relative_path).read_bytes()
                normalized = content.replace(b"\r\n", b"\n")
                self.assertEqual(hashlib.sha256(normalized).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
