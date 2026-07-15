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

    def test_leaves_content_and_style_files_unprotected(self) -> None:
        self.assertFalse(is_protected("README.md"))
        self.assertFalse(is_protected("src/css/fullscreen.css"))

    def test_owner_authored_change_does_not_require_self_approval(self) -> None:
        event = {"pull_request": {"user": {"login": "itsjustatank"}}}
        self.assertFalse(requires_owner_approval(event))

    def test_agent_authored_change_requires_owner_approval(self) -> None:
        event = {"pull_request": {"user": {"login": "automation-bot"}}}
        self.assertTrue(requires_owner_approval(event))

    def test_missing_author_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            requires_owner_approval({"pull_request": {}})


if __name__ == "__main__":
    unittest.main()
