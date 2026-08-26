#!/usr/bin/env python3
"""Assert the Bash and PowerShell gates reach the same verdicts.

Parity is a promise unless something checks it. This session watched
scripts/check_commit_message.py diverge between two repositories until a
merge commit exposed it, so the shared corpus is a test rather than a
convention: a fix landing in one gate and not the other fails here.

Each row pairs a command with its equivalent in the other shell. Where a
form exists in only one shell, the pair repeats the same string, which
still asserts that both gates read it identically.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASH_HOOK = REPO_ROOT / "hooks" / "block_destructive_bash.py"
POWERSHELL_HOOK = REPO_ROOT / "hooks" / "block_destructive_powershell.py"


def _decision(hook: Path, tool: str, command, mode: str = "default") -> str:
    """Return the permission decision one gate reaches for `command`."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "permission_mode": mode,
        "tool_input": {"command": command},
    }
    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload), capture_output=True, text=True, check=False)
    try:
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError):
        return ""


def bash(command, mode: str = "default") -> str:
    return _decision(BASH_HOOK, "Bash", command, mode)


def powershell(command, mode: str = "default") -> str:
    return _decision(POWERSHELL_HOOK, "PowerShell", command, mode)


class GitParityTest(unittest.TestCase):
    """git decisions come from the shared core, so they cannot differ."""

    COMMANDS = (
        "git push --force",
        "git push -f origin main",
        "git reset --hard",
        "git push --force-with-lease",
        "git push --force-with-lease=main:abc123",
        "git push --mirror",
        "git push --delete origin feat/x",
        "git push origin +HEAD:main",
        "git push origin :main",
        "git push --prune origin",
        "git commit --amend",
        "git rebase -i HEAD~3",
        "git filter-branch --tree-filter true HEAD",
        "git -C /repo push --force",
        "git status",
        "git log --oneline -5",
        "git push origin feat/x",
        "git push -u origin feat/x",
    )

    def test_both_gates_agree_on_git(self):
        for command in self.COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(bash(command), powershell(command))


class MalformedParityTest(unittest.TestCase):
    """Both gates must fail closed on the same malformed inputs."""

    def test_non_string_commands_agree(self):
        for value in (None, 5, ["rm"], {"a": 1}):
            with self.subTest(value=value):
                self.assertEqual(bash(value), powershell(value))

    def test_unattended_modes_agree(self):
        for mode in ("bypassPermissions", "dontAsk", "", "unknown-mode"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    bash("git push --force-with-lease", mode),
                    powershell("git push --force-with-lease", mode))


class BoundaryParityTest(unittest.TestCase):
    """Each boundary class, in both spellings, reaches the same verdict."""

    PAIRS = (
        ("true\nrm -rf /tmp/x", "Write-Output x\nRemove-Item -Recurse /tmp/x"),
        ("true; rm -rf /tmp/x", "Write-Output x; Remove-Item -Recurse /tmp/x"),
        ("true && rm -rf /tmp/x", "Test-Path x && Remove-Item -Recurse /tmp/x"),
        ("true || rm -rf /tmp/x", "Test-Path x || Remove-Item -Recurse /tmp/x"),
        ("echo x | xargs rm -rf /tmp/x", "Get-Process | Remove-Item -Recurse /tmp/x"),
        ("rm -rf /", "Remove-Item -Recurse /"),
        ("rm -rf $HOME", "Remove-Item -Recurse $HOME"),
        ("rm -rf ~", "Remove-Item -Recurse ~"),
        ("rm -rf /tmp/scratch", "Remove-Item -Recurse /tmp/scratch"),
        ("rm build.log", "Remove-Item build.log"),
        ("ls -la", "Get-ChildItem"),
        ("echo x > tests/test_auth.py", "Write-Output x > tests/test_auth.py"),
        ("echo x > src/app.js", "Write-Output x > src/app.js"),
        ("cmd /c rd /s /q C:/work", "cmd /c rd /s /q C:/work"),
    )

    def test_equivalent_commands_agree(self):
        for bash_command, powershell_command in self.PAIRS:
            with self.subTest(bash=bash_command):
                self.assertEqual(bash(bash_command), powershell(powershell_command))


class CoreOwnershipTest(unittest.TestCase):
    """Every decision function lives in the core, not in one gate."""

    def test_neither_gate_defines_its_own_verdict_helpers(self):
        shared = ("delete_verdict", "git_verdict", "push_verdict",
                  "is_root_target", "strongest", "is_test_path",
                  "cmd_delete_verdict", "sanitize")
        for hook in (BASH_HOOK, POWERSHELL_HOOK):
            source = hook.read_text(encoding="utf-8")
            for name in shared:
                with self.subTest(hook=hook.name, function=name):
                    self.assertNotIn(
                        f"def {name}(", source,
                        f"{hook.name} redefines {name}; it belongs to the core "
                        f"so both gates cannot drift")


if __name__ == "__main__":
    unittest.main()
