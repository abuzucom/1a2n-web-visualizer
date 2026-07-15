import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import scripts.jira_sync as jira_sync
from scripts.jira_sync import adf_text, issue_keys


class JiraSyncTests(unittest.TestCase):
    def test_extracts_project_keys_from_pr_metadata(self) -> None:
        values = ["VID-4: fix rendering", "feature/VID-12", "VID-4"]
        self.assertEqual(issue_keys(values), {"VID-4", "VID-12"})

    def test_builds_atlassian_document_format(self) -> None:
        self.assertEqual(adf_text("hello")["content"][0]["content"][0]["text"], "hello")

    def test_main_skips_without_jira_secrets_or_network_calls(self) -> None:
        output = StringIO()
        with (
            patch.object(jira_sync, "JIRA_EMAIL", ""),
            patch.object(jira_sync, "JIRA_API_TOKEN", ""),
            patch.object(jira_sync, "jira_request", side_effect=AssertionError("Jira request made")),
            patch.object(jira_sync, "github_request", side_effect=AssertionError("GitHub request made")),
            redirect_stdout(output),
        ):
            result = jira_sync.main()

        self.assertEqual(result, 0)
        self.assertIn("Jira secrets are not configured", output.getvalue())


if __name__ == "__main__":
    unittest.main()
