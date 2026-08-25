#!/usr/bin/env python3
"""Tests for hooks/block_destructive_bash.py.

Runs the hook as a subprocess against synthetic Claude Code payloads, the
same path the harness uses, rather than asserting on mocks.

Two outcomes carry different weight. A `deny` is a command the hook refuses
outright; it exits 2 so the block holds even where stdout JSON is ignored.
An `ask` routes the decision to the human through the permission prompt,
which is the only consent AGENTS.md recognizes for Rule 2 and for rewriting
pushed history.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "block_destructive_bash.py"
BLOCKING_EXIT_CODE = 2


def run_hook(command: str, permission_mode: str = "default") -> tuple:
    """Return the hook's (exit code, permission decision) for `command`."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "permission_mode": permission_mode,
        "tool_input": {"command": command},
    }
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    decision = ""
    if result.stdout.strip():
        decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    return result.returncode, decision


class DenyTest(unittest.TestCase):
    """Commands the hook refuses outright keep refusing."""

    DENIED = (
        "git push --force origin feat/x",
        "git push -f origin feat/x",
        "rm -rf ~/.cache/foo",
        "rm -rf $HOME",
        "rm -rf /",
        "git reset --hard HEAD~1",
    )

    def test_denied_commands_exit_two(self):
        for command in self.DENIED:
            with self.subTest(command=command):
                code, decision = run_hook(command)
                self.assertEqual(code, BLOCKING_EXIT_CODE)
                self.assertEqual(decision, "deny")


class AskTest(unittest.TestCase):
    """Acts that need the user's decision at the act, not the model's."""

    ASKED = (
        "git push --force-with-lease origin feat/x",
        "git push --force-if-includes origin feat/x",
        "rm -rf /tmp/claude-scratch-profile",
        "rm -rf node_modules",
        "git commit --amend --no-edit",
        "git rebase -i origin/develop",
        "git push --delete origin feat/x",
        "git filter-branch --tree-filter true HEAD",
    )

    def test_asked_commands_route_to_the_human(self):
        for command in self.ASKED:
            with self.subTest(command=command):
                code, decision = run_hook(command)
                self.assertEqual(code, 0)
                self.assertEqual(decision, "ask")

    def test_scratch_directory_is_not_exempt(self):
        """Rule 2 carries no 'it is my own directory' carve-out."""
        _, decision = run_hook("rm -rf /tmp/my-own-scratch-dir")
        self.assertEqual(decision, "ask")

    def test_force_with_lease_is_not_exempt(self):
        """A lease does not make a history rewrite consented to."""
        _, decision = run_hook("git push --force-with-lease")
        self.assertEqual(decision, "ask")


class FailClosedTest(unittest.TestCase):
    """Absence of a human is absence of consent."""

    UNATTENDED_MODES = ("bypassPermissions", "dontAsk", "", "something-new")

    def test_unattended_modes_deny_instead_of_asking(self):
        for mode in self.UNATTENDED_MODES:
            with self.subTest(mode=mode):
                code, decision = run_hook("rm -rf /tmp/scratch", permission_mode=mode)
                self.assertEqual(code, BLOCKING_EXIT_CODE)
                self.assertEqual(decision, "deny")

    def test_interactive_modes_ask(self):
        for mode in ("default", "plan", "acceptEdits", "auto"):
            with self.subTest(mode=mode):
                _, decision = run_hook("rm -rf /tmp/scratch", permission_mode=mode)
                self.assertEqual(decision, "ask")


class AllowTest(unittest.TestCase):
    """Ordinary commands pass without a prompt."""

    ALLOWED = (
        "git push origin feat/x",
        "git push -u origin feat/consent-gate-hooks",
        "git commit -m 'feat: add a thing'",
        "rm build.log",
        "ls -la",
        "npm test",
        "git status",
    )

    def test_allowed_commands_pass_silently(self):
        for command in self.ALLOWED:
            with self.subTest(command=command):
                code, decision = run_hook(command)
                self.assertEqual(code, 0)
                self.assertEqual(decision, "")


class NonBashTest(unittest.TestCase):
    """The hook ignores tools other than Bash."""

    def test_edit_payload_passes(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "a.py", "old_string": "x", "new_string": "y"},
        }
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
