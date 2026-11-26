"""trusted_git.py fetch never writes a local tag ref."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import trusted_git

TAG_DESTINATIONS = ("refs/tags/v2.46.0:refs/tags/v2.46.0", "+main:tags/v1.0.0",
                    "main:REFS/TAGS/v1.0.0")
TAG_READ_REFSPEC = "refs/tags/v2.46.0:refs/remotes/template/v2.46.0"


class TrustedFetchNoTagsTest(unittest.TestCase):
    """The fetch form passes --no-tags and refuses tag destinations."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        (self.workspace / "repo" / ".git").mkdir(parents=True)
        self.repository = os.path.abspath(self.workspace / "repo")

    def test_tag_destination_refspec_rejected(self) -> None:
        for refspec in TAG_DESTINATIONS:
            with self.subTest(refspec=refspec):
                self.assertIsNone(trusted_git._transport_arguments(
                    self.workspace, ["fetch", "repo", "origin", refspec]))

    def test_tag_writing_arguments_rejected(self) -> None:
        for arguments in (["origin", "--tags"], ["origin", "main", "--prune-tags"],
                          ["origin", "-t"], ["origin", "-P"], ["origin", "tag", "v1.0.0"]):
            with self.subTest(arguments=arguments):
                self.assertIsNone(trusted_git._transport_arguments(
                    self.workspace, ["fetch", "repo", *arguments]))

    def test_tag_read_passes_no_tags(self) -> None:
        self.assertEqual(
            trusted_git._transport_arguments(
                self.workspace, ["fetch", "repo", "origin", TAG_READ_REFSPEC]),
            ["-C", self.repository, "fetch", "--no-tags", "--no-prune-tags", "origin",
             TAG_READ_REFSPEC])


if __name__ == "__main__":
    unittest.main()
