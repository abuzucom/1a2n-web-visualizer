import unittest

from scripts.check_protected_files import is_protected


class ProtectedClientConfigTests(unittest.TestCase):
    def test_protects_every_client_hook_registration(self) -> None:
        """Each client registration decides which gates run for that client."""
        for path in (
            ".codex/hooks.json", ".codex/config.toml",
            ".gemini/settings.json", ".agents/hooks.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))

    def test_protects_assembled_policy_inputs_and_gate_manifests(self) -> None:
        """These files feed the injected policy or pin the gate set."""
        for path in (
            "docs/agent-policy/enforcement.md", "docs/project-orientation.md",
            "shared-files.json", "hook-coverage-baseline.json",
            "requirements-checkers.txt",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))

    def test_leaves_other_docs_unprotected(self) -> None:
        self.assertFalse(is_protected("docs/obs-setup.md"))


if __name__ == "__main__":
    unittest.main()
