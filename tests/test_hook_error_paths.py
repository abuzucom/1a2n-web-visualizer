"""Shared hooks keep the fail-closed contract and close descriptors on error paths."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks"))
import _gate_core as core
import detect_prose_options
import enforce_pr_base

PRIMARY_NAME = "trunk"
QUESTION_TOOL = "AskUserQuestion"
PROSE_CHOICE = "Which option do you prefer? Option A rewrites the parser."


class _DescriptorTracker:
    """Record descriptors that os.open returns and make os.fstat fail."""

    def __init__(self) -> None:
        self.opened = []
        self._real_open = os.open

    def open(self, *args, **kwargs) -> int:
        descriptor = self._real_open(*args, **kwargs)
        self.opened.append(descriptor)
        return descriptor

    @staticmethod
    def fail_fstat(_descriptor: int):
        raise OSError("simulated fstat failure")

    def all_closed(self) -> bool:
        """Return whether every recorded descriptor is closed."""
        for descriptor in self.opened:
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            os.close(descriptor)
            return False
        return True


def _write_primary_branch(root: Path, name: str) -> None:
    """Write hooks/primary-branch.txt under a temporary repository root."""
    hooks = root / "hooks"
    hooks.mkdir()
    (hooks / "primary-branch.txt").write_text(name + "\n", encoding="ascii")


class PrimaryBranchErrorPathTest(unittest.TestCase):
    """An fstat failure in primary_branch raises ValueError and closes the descriptor."""

    def test_primary_branch_fstat_failure_closes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_primary_branch(root, "main")
            tracker = _DescriptorTracker()
            with patch.object(core.os, "open", tracker.open), \
                    patch.object(core.os, "fstat", tracker.fail_fstat):
                with self.assertRaises(ValueError):
                    core.primary_branch(str(root))
            self.assertEqual(len(tracker.opened), 1)
            self.assertTrue(tracker.all_closed())

    def test_primary_branch_read_failure_converts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_primary_branch(root, "main")
            real_fdopen = os.fdopen

            def failing_fdopen(descriptor: int, mode: str):
                handle = real_fdopen(descriptor, mode)

                def fail_read(_size: int):
                    raise OSError("simulated read failure")

                handle.read = fail_read
                return handle

            with patch.object(core.os, "fdopen", failing_fdopen):
                with self.assertRaises(ValueError):
                    core.primary_branch(str(root))


class MissingPullRequestBaseTest(unittest.TestCase):
    """A create_pull_request call with no base checks the primary branch."""

    def test_missing_base_valid_primary_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_primary_branch(root, PRIMARY_NAME)
            payload = {"tool_name": "mcp__github__create_pull_request",
                       "tool_input": {"title": "x", "head": "fix/x"}, "cwd": str(root)}
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}):
                decision, _reason = enforce_pr_base.base_decision(payload)
        self.assertEqual(decision, "")

    def test_missing_base_update_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_primary_branch(root, "not a branch")
            payload = {"tool_name": "mcp__github__update_pull_request",
                       "tool_input": {"pullNumber": 1, "title": "x"}, "cwd": str(root)}
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}):
                decision, _reason = enforce_pr_base.base_decision(payload)
        self.assertEqual(decision, "", "an update without base keeps the base unchanged")

    def test_missing_base_unusable_file_denies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_primary_branch(root, "not a branch")
            payload = {"tool_name": "mcp__github__create_pull_request",
                       "tool_input": {"title": "x", "head": "fix/x"}, "cwd": str(root)}
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}):
                decision, _reason = enforce_pr_base.base_decision(payload)
        self.assertEqual(decision, "deny")


def _record_line(record: dict) -> str:
    """Return one JSON transcript line."""
    return json.dumps(record) + "\n"


def _assistant(text: str = "", tool: str = "") -> dict:
    """Return an assistant record with optional text and an optional tool call."""
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if tool:
        content.append({"type": "tool_use", "id": "t1", "name": tool, "input": {}})
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


class TranscriptTailBoundaryTest(unittest.TestCase):
    """A tail read that starts on a record boundary keeps the first record."""

    def test_tail_boundary_keeps_record(self) -> None:
        question_line = _record_line(_assistant(tool=QUESTION_TOOL))
        final_prefix = _record_line(_assistant(text=PROSE_CHOICE))
        padding = detect_prose_options.TAIL_BYTES - len(question_line) - len(final_prefix)
        self.assertGreater(padding, 0)
        final_line = _record_line(_assistant(text=PROSE_CHOICE + " " * padding))
        tail = question_line + final_line
        self.assertEqual(len(tail.encode("utf-8")), detect_prose_options.TAIL_BYTES)
        prefix = _record_line({"type": "user", "message": {"role": "user", "content": "go"}})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "transcript.jsonl"
            # Exact bytes keep the tail on a record boundary. Text mode on
            # Windows writes CRLF and shifts every offset.
            path.write_bytes((prefix + tail).encode("utf-8"))
            records = detect_prose_options._records(detect_prose_options._read_tail(str(path)))
        self.assertFalse(detect_prose_options.needs_question_tool(records))

    def test_tail_midrecord_drops_partial(self) -> None:
        line = _record_line(_assistant(text="filler"))
        body = line * (detect_prose_options.TAIL_BYTES // len(line) + 2)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "transcript.jsonl"
            path.write_text("x" + body, encoding="utf-8")
            text = detect_prose_options._read_tail(str(path))
        for kept in text.splitlines():
            self.assertEqual(json.loads(kept)["type"], "assistant")

    def test_tail_fstat_failure_closes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "transcript.jsonl"
            path.write_text(_record_line(_assistant(text="x")), encoding="utf-8")
            tracker = _DescriptorTracker()
            with patch.object(detect_prose_options.os, "open", tracker.open), \
                    patch.object(detect_prose_options.os, "fstat", tracker.fail_fstat):
                with self.assertRaises(OSError):
                    detect_prose_options._read_tail(str(path))
            self.assertEqual(len(tracker.opened), 1)
            self.assertTrue(tracker.all_closed())


if __name__ == "__main__":
    unittest.main()
