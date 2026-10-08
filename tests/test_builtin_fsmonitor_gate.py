import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "block_destructive_bash.py"
SAFE_FS_MONITOR_VALUES = ("true", "yes", "on", "1")


def run_git_status_hook(fsmonitor_value: str) -> tuple[int, str]:
    """Run the real Bash hook in a temporary repository with fsmonitor set."""
    with tempfile.TemporaryDirectory() as directory:
        repository = Path(directory)
        subprocess.run(
            ["git", "init", "--quiet", str(repository)],
            check=True,
            capture_output=True,
            text=True,
        )
        config_path = repository / ".git" / "config"
        with config_path.open("a", encoding="utf-8", newline="") as config_file:
            config_file.write(f"\n[core]\n\tfsmonitor = {fsmonitor_value}\n")

        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "permission_mode": "default",
            "tool_input": {"command": "git status"},
        }
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            cwd=repository,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        decision = ""
        if result.stdout.strip():
            decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
        return result.returncode, decision


class BuiltinFsmonitorGateTests(unittest.TestCase):
    def test_builtin_boolean_values_allow_git_status(self):
        for value in SAFE_FS_MONITOR_VALUES:
            with self.subTest(value=value):
                code, decision = run_git_status_hook(value)
                self.assertEqual(code, 0)
                self.assertEqual(decision, "")

    def test_custom_fsmonitor_program_still_prompts(self):
        code, decision = run_git_status_hook("custom-fsmonitor")
        self.assertEqual(code, 0)
        self.assertEqual(decision, "ask")


if __name__ == "__main__":
    unittest.main()
