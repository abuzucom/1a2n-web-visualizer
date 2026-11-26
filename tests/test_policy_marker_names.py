#!/usr/bin/env python3
"""Tests for the renamed policy markers and the handoff exemption scope.

The local policy and source orientation markers replace two older marker
names. The handoff exemption scope replaces an older section name in the
prose denylist. Adopters still hold the older names, so both readers
accept them and print a notice that names the new spelling.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import prose_policy
import sync

LEGACY_LOCAL_START = "<!-- repository-only:start -->"
LEGACY_LOCAL_END = "<!-- repository-only:end -->"
LEGACY_SOURCE_START = "<!-- source-only:start -->"
LEGACY_SOURCE_END = "<!-- source-only:end -->"
LEGACY_HANDOFF_SCOPE = "handoff-exempt"
HANDOFF_SCOPE = "handoff exemption"


def run_adoptable(content: str) -> tuple:
    """Return adoptable content and the notice text printed to stderr."""
    notices = io.StringIO()
    with contextlib.redirect_stderr(notices):
        result = sync.adoptable_content(content)
    return result, notices.getvalue()


class MarkerNameTest(unittest.TestCase):
    """Adoption strips the new markers and still strips the legacy ones."""

    def test_new_marker_strings(self):
        self.assertEqual(sync.LOCAL_POLICY_START, "<!-- local policy:start -->")
        self.assertEqual(sync.LOCAL_POLICY_END, "<!-- local policy:end -->")
        self.assertEqual(sync.SOURCE_ORIENTATION_START, "<!-- source orientation:start -->")
        self.assertEqual(sync.SOURCE_ORIENTATION_END, "<!-- source orientation:end -->")

    def test_constants_point_to_new_markers(self):
        self.assertEqual(sync.REPOSITORY_ONLY_START, sync.LOCAL_POLICY_START)
        self.assertEqual(sync.REPOSITORY_ONLY_END, sync.LOCAL_POLICY_END)
        self.assertEqual(sync.SOURCE_ONLY_START, sync.SOURCE_ORIENTATION_START)
        self.assertEqual(sync.SOURCE_ONLY_END, sync.SOURCE_ORIENTATION_END)

    def test_new_markers_strip_without_notice(self):
        content = (
            f"before\n{sync.LOCAL_POLICY_START}\nlocal facts\n"
            f"{sync.LOCAL_POLICY_END}\nafter\n"
            f"{sync.SOURCE_ORIENTATION_START}\nsource facts\n"
            f"{sync.SOURCE_ORIENTATION_END}\n"
        )
        result, notices = run_adoptable(content)
        self.assertEqual(result, "before\nafter\n\n")
        self.assertEqual(notices, "")

    def test_legacy_markers_strip_with_notice(self):
        content = (
            f"before\n{LEGACY_LOCAL_START}\nlocal facts\n"
            f"{LEGACY_LOCAL_END}\nafter\n"
            f"{LEGACY_SOURCE_START}\nsource facts\n"
            f"{LEGACY_SOURCE_END}\n"
        )
        result, notices = run_adoptable(content)
        self.assertEqual(result, "before\nafter\n\n")
        self.assertIn(sync.LOCAL_POLICY_START, notices)
        self.assertIn(sync.SOURCE_ORIENTATION_START, notices)

    def test_mixed_markers_single_block(self):
        content = f"before\n{LEGACY_LOCAL_START}\nlocal\n{sync.LOCAL_POLICY_END}\nafter\n"
        result, _ = run_adoptable(content)
        self.assertEqual(result, "before\nafter\n")

    def test_mixed_starts_separate_blocks(self):
        content = (
            f"{sync.LOCAL_POLICY_START}\n{sync.LOCAL_POLICY_END}\n"
            f"{LEGACY_LOCAL_START}\n{LEGACY_LOCAL_END}\n"
        )
        with self.assertRaises(ValueError):
            run_adoptable(content)


class HandoffScopeTest(unittest.TestCase):
    """The denylist accepts the new scope name and still reads the legacy one."""

    def load(self, section: str) -> tuple:
        """Load a two-scope denylist and return entries and printed notices."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bans.txt"
            path.write_text(f"[global]\nfirst entry\n\n[{section}]\nsecond entry\n",
                            encoding="ascii")
            notices = io.StringIO()
            with contextlib.redirect_stderr(notices):
                entries = prose_policy.load_denylist(path)
        return entries, notices.getvalue()

    def test_new_scope_no_notice(self):
        entries, notices = self.load(HANDOFF_SCOPE)
        self.assertEqual([entry.scope for entry in entries], ["global", HANDOFF_SCOPE])
        self.assertEqual(notices, "")

    def test_legacy_scope_maps_with_notice(self):
        entries, notices = self.load(LEGACY_HANDOFF_SCOPE)
        self.assertEqual([entry.scope for entry in entries], ["global", HANDOFF_SCOPE])
        self.assertIn(f"[{HANDOFF_SCOPE}]", notices)

    def test_handoff_example_skips_scope(self):
        entries, _ = self.load(HANDOFF_SCOPE)
        handoff = prose_policy.HANDOFF_PATH
        self.assertEqual(
            prose_policy.find_violations("A second entry here.\n", handoff, entries), [])
        self.assertEqual(
            len(prose_policy.find_violations("A second entry here.\n", "README.md", entries)), 1)

    def test_live_denylist_new_scope(self):
        text = prose_policy.DENYLIST_PATH.read_text(encoding="ascii")
        self.assertIn(f"[{HANDOFF_SCOPE}]", text)
        self.assertNotIn(f"[{LEGACY_HANDOFF_SCOPE}]", text)


if __name__ == "__main__":
    unittest.main()
