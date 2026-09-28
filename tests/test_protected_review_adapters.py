import unittest

from scripts.check_protected_files import is_protected


class ProtectedReviewAdapterTests(unittest.TestCase):
    def test_protects_the_review_adapters(self) -> None:
        """The security review runs these files with the provider secret."""
        for path in (
            "ci/call_model.py", "ci/build_pr_case.py",
            "ci/run_model_command.py", "ci/model_providers.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))


if __name__ == "__main__":
    unittest.main()
