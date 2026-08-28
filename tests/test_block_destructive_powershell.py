#!/usr/bin/env python3
"""Tests for hooks/block_destructive_powershell.py.

Runs the hook as a subprocess against synthetic Claude Code payloads,
which is the limit of what this suite proves: it has not been exercised
against a live PowerShell tool call.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest

# discover -s tests puts this directory on the path; a direct
# `unittest tests.<module>` run does not, and CI uses both.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_corpus
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "block_destructive_powershell.py"
BLOCKING_EXIT_CODE = 2


def run_hook(command, permission_mode: str = "default", cwd: str = "") -> tuple:
    """Return the hook's (exit code, permission decision) for `command`."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "PowerShell",
        "permission_mode": permission_mode,
        "tool_input": {"command": command},
    }
    if cwd:
        payload["cwd"] = cwd
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


def encoded(command: str) -> str:
    """Return PowerShell's UTF-16LE Base64 representation of `command`."""
    return base64.b64encode(command.encode("utf-16le")).decode("ascii")


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


class EncodedCommandTest(unittest.TestCase):
    """EncodedCommand is decoded before the nested command is classified."""

    FLAGS = (
        "-e", "-ec", "-en", "-enc", "-enco", "-encod", "-encode",
        "-encoded", "-encodedc", "-encodedco", "-encodedcom",
        "-encodedcomm", "-encodedcomma", "-encodedcomman",
        "-encodedcommand",
    )

    def test_every_supported_spelling_classifies_destructive_payloads(self):
        payload = encoded("Remove-Item -Recurse C:\\work\\build")
        for program in ("powershell", "powershell.exe", "pwsh", "pwsh.exe"):
            for flag in self.FLAGS:
                with self.subTest(program=program, flag=flag):
                    _, decision = run_hook(f"{program} {flag} {payload}")
                    self.assertEqual(decision, "ask")

    def test_benign_encoded_payload_passes(self):
        for flag in self.FLAGS:
            with self.subTest(flag=flag):
                _, decision = run_hook(f"pwsh {flag} {encoded('Get-ChildItem')}")
                self.assertEqual(decision, "")

    def test_malformed_encoded_payloads_deny(self):
        invalid_utf16 = base64.b64encode(bytes((0, 216))).decode("ascii")
        malformed = (
            "pwsh -enc",
            "pwsh -enc !!!",
            "pwsh -enc QQ==",
            f"pwsh -enc {invalid_utf16}",
        )
        for command in malformed:
            with self.subTest(command=command):
                code, decision = run_hook(command)
                self.assertEqual(code, BLOCKING_EXIT_CODE)
                self.assertEqual(decision, "deny")

    def test_encoded_recursion_exhaustion_denies(self):
        command = "Get-ChildItem"
        for _ in range(6):
            command = f"pwsh -enc {encoded(command)}"
        code, decision = run_hook(command)
        self.assertEqual(code, BLOCKING_EXIT_CODE)
        self.assertEqual(decision, "deny")

    def test_e_is_not_encoded_command_for_an_unrelated_interpreter(self):
        _, decision = run_hook("python -e not-base64")
        self.assertEqual(decision, "")


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

    def test_gate_file_writes_ask(self):
        commands = (
            "Write-Output x > hooks/new.py",
            "Write-Output x > scripts/check_branch_name.py",
            "Set-Content hooks/new.py x",
            "Add-Content .claude/settings.json x",
            "Set-Content scripts/check_git_identity.py x",
            "Copy-Item source.py hooks/new.py",
            "Move-Item source.py .claude/new.json",
            "Out-File .claude/settings.json -InputObject x",
        )
        for command in commands:
            with self.subTest(command=command):
                _, decision = run_hook(command)
                self.assertEqual(decision, "ask")

    def test_named_write_paths_gate_regardless_of_parameter_order(self):
        commands = (
            "Set-Content -Value x -Path hooks/new.py",
            "Add-Content -Value x -LiteralPath .claude/settings.json",
            "Out-File -InputObject x -FilePath hooks/new.py",
            "Copy-Item -Destination hooks/new.py -Path source.py",
            "Move-Item -Destination .claude/new.json -LiteralPath source.py",
            "sc -Value x -Path hooks/new.py",
            "cpi -Destination hooks/new.py -Path source.py",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command)[1], "ask")

    def test_abbreviated_write_parameters_gate_regardless_of_order(self):
        commands = (
            "Set-Content -Va x -Pat hooks/new.py",
            "Add-Content -Va x -L .claude/settings.json",
            "Out-File -Inp x -Fi hooks/new.py",
            "Copy-Item -Des hooks/new.py -Pat source.py",
            "Move-Item -Des .claude/new.json -L source.py",
            "sc -Va x -Pat hooks/new.py",
            "cpi -Des hooks/new.py -Pat source.py",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command)[1], "ask")

    def test_linked_directory_into_hooks_is_gated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hooks = root / "hooks"
            hooks.mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(hooks, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"this platform cannot create directory links: {error}")
            decision = run_hook(
                "Set-Content -Va x -Pat linked/new.py", cwd=directory)[1]
        self.assertEqual(decision, "ask")


class GitEnvironmentTest(unittest.TestCase):
    """Persistent PowerShell Git variables must not evade a later read."""

    def test_relevant_environment_assignments_are_gated(self):
        commands = (
            "$env:GIT_PAGER='/tmp/evil'; git status",
            "$env:GIT_EXTERNAL_DIFF='/tmp/evil'; git diff",
            "$env:GIT_CONFIG_GLOBAL='/tmp/evil'; git status",
            "$env:GIT_CONFIG_COUNT='1'; git status",
            "$env:GIT_CONFIG_KEY_0='core.pager'; git status",
            "$env:GIT_CONFIG_VALUE_0='/tmp/evil'; git status",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command)[1], "ask")

    def test_provider_and_braced_environment_assignments_are_gated(self):
        commands = (
            "${env:GIT_PAGER}='/tmp/evil'; git status",
            "Set-Item Env:GIT_EXTERNAL_DIFF /tmp/evil; git diff",
            "Set-Item -Path Env:GIT_CONFIG_GLOBAL -Value /tmp/evil; git status",
            "Set-Variable -Name env:GIT_PAGER -Value /tmp/evil; git status",
            "sv -Name env:GIT_CONFIG_COUNT -Value 1; git status",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command)[1], "ask")


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


class CorpusTest(unittest.TestCase):
    """Every known PowerShell bypass reaches the verdict the corpus records."""

    def test_every_corpus_row_reaches_its_verdict(self):
        for command, expected, why in gate_corpus.POWERSHELL_CASES:
            with self.subTest(command=command, why=why):
                _, decision = run_hook(command)
                self.assertEqual(decision or gate_corpus.ALLOW, expected)
