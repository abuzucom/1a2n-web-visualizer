import unittest

from scripts.check_protected_files import is_protected, requires_owner_approval


class ProtectedFileTests(unittest.TestCase):
    def test_protects_instruction_and_automation_files(self) -> None:
        for path in ("AGENTS.md", "nested/AGENTS.md", ".github/workflows/deploy.yml", "scripts/sync.py"):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))

    def test_protects_runtime_and_deployment_files(self) -> None:
        for path in (
            "package-lock.json", "infra/Dockerfile", "deploy/Caddyfile",
            "infra/docker-compose.yml", "src/fullscreen.html", "src/js/app.js",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))

    def test_protects_tests_and_enforcement(self) -> None:
        """A gate anyone can quietly edit or delete is not a gate."""
        for path in (
            "tests/test_bcviz_api.js", "tests/test_protected_files.py",
            "hooks/require_consent.py", "hooks/block_destructive_bash.py",
            ".claude/settings.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))

    def test_content_and_style_stay_unprotected(self) -> None:
        """Leaves content and style files unprotected."""
        self.assertFalse(is_protected("README.md"))
        self.assertFalse(is_protected("src/css/fullscreen.css"))

    def test_owner_change_skips_self_approval(self) -> None:
        """Owner authored change does not require self approval."""
        event = {"pull_request": {"user": {"login": "itsjustatank"}}}
        self.assertFalse(requires_owner_approval(event))

    def test_agent_change_requires_owner_approval(self) -> None:
        """Agent authored change requires owner approval."""
        event = {"pull_request": {"user": {"login": "automation-bot"}}}
        self.assertTrue(requires_owner_approval(event))

    def test_missing_author_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            requires_owner_approval({"pull_request": {}})


if __name__ == "__main__":
    unittest.main()
