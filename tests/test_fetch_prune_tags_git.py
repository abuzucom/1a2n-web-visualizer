"""Real Git keeps local tags under the fetch form that the gates allow.

`fetch.pruneTags` and `remote.<name>.pruneTags` delete local tags during a
pruning fetch even with `--no-tags`. The allowed form adds `--no-prune-tags`.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

GIT_IDENTITY = ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid")
LOCAL_TAG = "v0.0.1"
ALLOWED_FLAGS = ("--no-tags", "--no-prune-tags")


def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess:
    """Run one fixture Git command."""
    return subprocess.run(["git", "-C", str(cwd), *GIT_IDENTITY, *arguments],
                          capture_output=True, text=True, check=False)


class PruneTagsGitTest(unittest.TestCase):
    """The allowed fetch and pull forms keep a tag that the remote lacks."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.remote = root / "remote"
        self.local = root / "local"
        self.remote.mkdir()
        _git(self.remote, "init", "--quiet", "--initial-branch=main")
        (self.remote / "file.txt").write_text("x\n", encoding="utf-8")
        _git(self.remote, "add", "file.txt")
        _git(self.remote, "commit", "--quiet", "-m", "base")
        subprocess.run(["git", "clone", "--quiet", str(self.remote), str(self.local)],
                       capture_output=True, check=True)
        _git(self.local, "tag", LOCAL_TAG)
        _git(self.local, "config", "fetch.prune", "true")
        _git(self.local, "config", "fetch.pruneTags", "true")
        _git(self.local, "config", "remote.origin.pruneTags", "true")

    def has_tag(self) -> bool:
        return _git(self.local, "rev-parse", "--verify", f"refs/tags/{LOCAL_TAG}").returncode == 0

    def test_no_tags_alone_prunes(self) -> None:
        _git(self.local, "fetch", "--no-tags", "origin")
        self.assertFalse(self.has_tag())

    def test_allowed_fetch_keeps_tag(self) -> None:
        result = _git(self.local, "fetch", *ALLOWED_FLAGS, "origin")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.has_tag())

    def test_pull_rejects_no_prune_tags(self) -> None:
        result = _git(self.local, "pull", "--ff-only", *ALLOWED_FLAGS, "origin", "main")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.has_tag())

    def test_pull_no_prune_keeps_tag(self) -> None:
        result = _git(self.local, "pull", "--ff-only", "--no-tags", "--no-prune", "origin", "main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.has_tag())


if __name__ == "__main__":
    unittest.main()
