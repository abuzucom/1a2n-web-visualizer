#!/usr/bin/env python3
"""Tests for hooks/block_destructive_powershell.py.

Runs the hook as a subprocess against synthetic Claude Code payloads,
which is the limit of what this suite proves: it has not been exercised
against a live PowerShell tool call.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "block_destructive_powershell.py"
BLOCKING_EXIT_CODE = 2


def run_hook(command, permission_mode: str = "default") -> tuple:
    """Return the hook's (exit code, permission decision) for `command`."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "PowerShell",
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
    try:
        decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError):
        decision = ""
    return result.returncode, decision


class RemoveItemTest(unittest.TestCase):
    """Remove-Item and its aliases, across PowerShell's parameter forms."""

    CASES = (
        ("Remove-Item -Recurse -Force C:\\work\\build", "ask"),
        ("Remove-Item -Rec -Fo C:\\work\\build", "ask"),
        ("Remove-Item -r C:\\work\\build", "ask"),
        ("remove-item -RECURSE C:\\work\\build", "ask"),
        ("ri -Recurse C:\\work\\build", "ask"),
        ("rm -Recurse C:\\work\\build", "ask"),
        ("del -Recurse C:\\work\\build", "ask"),
        ("rd -Recurse C:\\work\\build", "ask"),
        ("rmdir -Recurse C:\\work\\build", "ask"),
        ("Remove-Item -Recurse $env:USERPROFILE", "deny"),
        ("Remove-Item -Recurse $HOME", "deny"),
        ("Remove-Item -Recurse C:\\", "deny"),
        ("Remove-Item build.log", ""),
        ("Get-ChildItem -Recurse C:\\work", ""),
    )

    def test_deletion_forms_are_classified(self):
        for command, expected in self.CASES:
            with self.subTest(command=command):
                _, decision = run_hook(command)
                self.assertEqual(decision, expected)


class StatementBoundaryTest(unittest.TestCase):
    """A destructive statement after a separator is still a statement."""

    CASES = (
        ("Write-Output x; Remove-Item -Recurse C:\\work\\build", "ask"),
        ("Write-Output x\nRemove-Item -Recurse C:\\work\\build", "ask"),
        ("Get-Process | Remove-Item -Recurse C:\\work\\build", "ask"),
        ("Test-Path x && Remove-Item -Recurse C:\\work\\build", "ask"),
        ("Test-Path x || Remove-Item -Recurse C:\\work\\build", "ask"),
        ("Remove-Item -Recurse C:\\work\\build > log.txt", "ask"),
    )

    def test_statements_after_a_separator_are_classified(self):
        for command, expected in self.CASES:
            with self.subTest(command=command):
                _, decision = run_hook(command)
                self.assertEqual(decision, expected)


class WrapperTest(unittest.TestCase):
    """Indirection hides the command the same way a shell does."""

    CASES = (
        ("& Remove-Item -Recurse C:\\work\\build", "ask"),
        ("Start-Process Remove-Item -Recurse C:\\work\\build", "ask"),
        ("powershell -Command 'Remove-Item -Recurse C:\\work\\build'", "ask"),
        ("pwsh -c 'Remove-Item -Recurse C:\\work\\build'", "ask"),
        ("cmd /c rd /s /q C:\\work\\build", "ask"),
        ("Invoke-Expression 'Remove-Item -Recurse C:\\work\\build'", "ask"),
    )

    def test_wrapped_commands_are_classified(self):
        for command, expected in self.CASES:
            with self.subTest(command=command):
                _, decision = run_hook(command)
                self.assertEqual(decision, expected)


class GitDelegationTest(unittest.TestCase):
    """git decisions come from the shared core, so both shells agree."""

    CASES = (
        ("git push --force", "ask"),
        ("git reset --hard", "deny"),
        ("git push --force-with-lease", "ask"),
        ("git push origin :main", "ask"),
        ("git commit --amend", "ask"),
        ("git status", ""),
        ("git push origin feat/x", ""),
    )

    def test_git_commands_match_the_bash_gate(self):
        for command, expected in self.CASES:
            with self.subTest(command=command):
                _, decision = run_hook(command)
                self.assertEqual(decision, expected)


class TestWriteTest(unittest.TestCase):
    """A redirect into a test file is an edit no Edit matcher sees."""

    def test_redirect_into_a_test_file_gates(self):
        _, decision = run_hook("Write-Output x > tests/test_auth.py")
        self.assertEqual(decision, "ask")

    def test_redirect_into_a_source_file_passes(self):
        _, decision = run_hook("Write-Output x > src/app.js")
        self.assertEqual(decision, "")


class FailClosedTest(unittest.TestCase):
    """A gate that cannot read its input must not answer 'fine'."""

    def test_unattended_modes_deny(self):
        for mode in ("bypassPermissions", "dontAsk", "", "something-new"):
            with self.subTest(mode=mode):
                code, decision = run_hook(
                    "Remove-Item -Recurse C:\\work\\build", mode)
                self.assertEqual(code, BLOCKING_EXIT_CODE)
                self.assertEqual(decision, "deny")

    def test_non_string_command_denies(self):
        for value in (None, 5, ["Remove-Item"], {"a": 1}):
            with self.subTest(value=value):
                code, decision = run_hook(value)
                self.assertEqual(code, BLOCKING_EXIT_CODE)
                self.assertEqual(decision, "deny")

    def test_malformed_payload_denies(self):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not json", capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, BLOCKING_EXIT_CODE)

    def test_other_tools_are_ignored(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "permission_mode": "default",
            "tool_input": {"file_path": "x"},
        }
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(payload), capture_output=True, text=True,
            check=False)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
