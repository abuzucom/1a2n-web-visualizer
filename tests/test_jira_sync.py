import unittest

from scripts.jira_sync import adf_text, issue_keys


class JiraSyncTests(unittest.TestCase):
    def test_extracts_project_keys_from_pr_metadata(self) -> None:
        values = ["VID-4: fix rendering", "feature/VID-12", "VID-4"]
        self.assertEqual(issue_keys(values), {"VID-4", "VID-12"})

    def test_builds_atlassian_document_format(self) -> None:
        self.assertEqual(adf_text("hello")["content"][0]["content"][0]["text"], "hello")


if __name__ == "__main__":
    unittest.main()
