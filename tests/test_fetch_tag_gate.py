"""git fetch and git pull deny every form that can write a local tag ref.

Agents never create, push, move, or delete Git tags. Tag auto-follow,
--tags, a refs/tags/ destination, and a tagOpt setting all write tags
during a fetch. Every shell gate reads the shared core verdict, so the
Bash, PowerShell, and CMD gates must agree.
"""
import unittest

from tests.test_gate_parity import _gate_core, bash, cmd, powershell

TAG_OPT_GLOBALS = (
    ["-c", "remote.origin.tagOpt=--tags"],
    ["-cremote.origin.tagopt=--tags"],
    ["--config-env=remote.origin.tagOpt=TAG_SETTING"],
    ["--config-env", "remote.origin.tagOpt=TAG_SETTING"],
)
UNRELATED_GLOBALS = (["-c", "core.quotepath=false"], ["-C", "."], ["-c"])

TAG_WRITING_COMMANDS = (
    "git fetch origin main",
    "git fetch ./template refs/tags/v2.46.0:refs/remotes/template/v2.46.0",
    "git fetch --tags origin",
    "git fetch -t origin",
    "git fetch --no-tags --tags origin",
    "git fetch --no-tags origin refs/tags/v1.0.0:refs/tags/v1.0.0",
    "git fetch --no-tags origin +main:tags/v1.0.0",
    "git fetch --no-tags origin tag v1.0.0",
    "git fetch --no-tags --prune-tags origin",
    "git fetch -nP origin",
    "git -c remote.origin.tagOpt=--tags fetch --no-tags origin",
    "git --config-env remote.origin.tagOpt=TAG_SETTING fetch --no-tags origin",
    "git pull",
    "git pull -n origin main",
    "git pull --tags origin main",
    "git fetch --no-tags origin main",
    "git fetch --no-tags --no-prune origin main",
    "git pull --no-tags origin main",
    "git pull --no-tags --no-prune --prune origin main",
    "git pull --no-tags --no-prune -p origin main",
)
TAG_FREE_COMMANDS = (
    "git fetch --no-tags --no-prune-tags origin main",
    "git fetch -n --no-prune-tags origin main",
    "git fetch --no-tags --no-prune-tags --prune origin",
    "git fetch --no-tags --no-prune-tags ./template "
    "refs/tags/v2.46.0:refs/remotes/template/v2.46.0",
    "git pull --no-tags --no-prune origin main",
)


class FetchTagGateTest(unittest.TestCase):
    """Fetch and pull pass only when no local tag ref can change."""

    def test_tag_writing_fetch_denies(self) -> None:
        for command in TAG_WRITING_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(bash(command), "deny")
                self.assertEqual(powershell(command), "deny")
                self.assertEqual(cmd(command), "deny")

    def test_tag_free_fetch_passes(self) -> None:
        for command in TAG_FREE_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(bash(command), "")
                self.assertEqual(powershell(command), "")
                self.assertEqual(cmd(command), "")

    def test_global_tag_opt_forms(self) -> None:
        for global_args in TAG_OPT_GLOBALS:
            with self.subTest(global_args=global_args):
                self.assertTrue(_gate_core._global_config_sets_tag_opt(global_args))
        for global_args in UNRELATED_GLOBALS:
            with self.subTest(global_args=global_args):
                self.assertFalse(_gate_core._global_config_sets_tag_opt(global_args))


if __name__ == "__main__":
    unittest.main()
