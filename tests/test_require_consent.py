#!/usr/bin/env python3
"""Tests for hooks/require_consent.py and its wiring.

Runs the hook as a subprocess against synthetic Claude Code payloads, the
same path the harness uses, rather than asserting on mocks. Test files are
created on disk, because the hook distinguishes a new test file from an edit
to an existing one by looking at the filesystem.

The additive cases matter as much as the gated ones. AGENTS.md mandates a
test-first workflow, so a gate that prompted on every append to a test file
would be turned off within a day and enforce nothing.

The settings tests guard the wiring: a hook nobody registered enforces
nothing, and an edit to `.claude/settings.json` that drops an event would
otherwise pass every behavioral test in this file.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "require_consent.py"
LIVE_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
EXAMPLE_SETTINGS = REPO_ROOT / "hooks" / "claude-code-settings.example.json"
BLOCKING_EXIT_CODE = 2
EDIT_MATCHER = "Edit|Write|MultiEdit|NotebookEdit"
QUESTION_MATCHER = "AskUserQuestion"

EXISTING_TEST = """test('device switch failure leaves the visualizer silent', function () {
  assert.equal(deviceBCalls, 1, 'no retry attempted');
  // The old stream was already released before the failed switch, so the
  // visualizer is honestly silent rather than misreporting the old device.
  assert.equal(viz.diagnostics().trackState, 'none');
});
"""


def run_hook(payload: dict, env: dict = None) -> tuple:
    """Return the hook's (exit code, parsed stdout) for `payload`."""
    environment = dict(os.environ)
    environment.pop("AGENTS_CONSENT_GRANTED", None)
    environment.pop("CLAUDE_PROJECT_DIR", None)
    if env:
        environment.update(env)
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    parsed = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, parsed


def decision_of(parsed: dict) -> str:
    """Return the permission decision in `parsed`, or an empty string."""
    return parsed.get("hookSpecificOutput", {}).get("permissionDecision", "")


def edit_payload(file_path: str, old: str, new: str, mode: str = "default") -> dict:
    """Return a PreToolUse Edit payload for `file_path`."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "permission_mode": mode,
        "tool_input": {"file_path": file_path, "old_string": old, "new_string": new},
    }


class TestFileFixture(unittest.TestCase):
    """Base class providing a real test file on disk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.test_file = Path(self.tmp.name) / "tests" / "test_bcviz_api.js"
        self.test_file.parent.mkdir(parents=True)
        self.test_file.write_text(EXISTING_TEST, encoding="utf-8")
        self.source_file = Path(self.tmp.name) / "src" / "bcviz.js"
        self.source_file.parent.mkdir(parents=True)
        self.source_file.write_text("export function create() {}\n", encoding="utf-8")


class AllowTest(TestFileFixture):
    """Work the rules permit passes without a prompt."""

    def test_source_file_edit_passes(self):
        payload = edit_payload(str(self.source_file), "create() {}", "create() { return 1; }")
        code, parsed = run_hook(payload)
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "")

    def test_new_test_file_passes(self):
        target = str(Path(self.tmp.name) / "tests" / "test_new_feature.js")
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "permission_mode": "default",
            "tool_input": {"file_path": target, "content": "test('new', function () {});\n"},
        }
        code, parsed = run_hook(payload)
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "")

    def test_appending_a_test_passes(self):
        """The test-first workflow must stay frictionless."""
        old = "});\n"
        new = "});\n\ntest('a new case', function () {\n  assert.equal(1, 1);\n});\n"
        code, parsed = run_hook(edit_payload(str(self.test_file), old, new))
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "")


class GateTest(TestFileFixture):
    """Edits that remove or weaken existing test content need the user."""

    def test_removing_an_assertion_asks(self):
        old = "  assert.equal(viz.diagnostics().trackState, 'none');\n"
        new = "  assert.equal(viz.diagnostics().trackState, 'device-b');\n"
        code, parsed = run_hook(edit_payload(str(self.test_file), old, new))
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "ask")

    def test_deleting_an_assertion_asks(self):
        old = "  assert.equal(viz.diagnostics().trackState, 'none');\n"
        code, parsed = run_hook(edit_payload(str(self.test_file), old, ""))
        self.assertEqual(decision_of(parsed), "ask")

    def test_introduced_skip_marker_asks_even_when_additive(self):
        old = "});\n"
        new = "});\n\ntest.skip('a case for later', function () {});\n"
        _, parsed = run_hook(edit_payload(str(self.test_file), old, new))
        self.assertEqual(decision_of(parsed), "ask")

    def test_overwriting_an_existing_test_file_asks(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "permission_mode": "default",
            "tool_input": {"file_path": str(self.test_file), "content": "test('x', function () {});\n"},
        }
        _, parsed = run_hook(payload)
        self.assertEqual(decision_of(parsed), "ask")

    def test_multiedit_asks_when_any_edit_is_not_additive(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "MultiEdit",
            "permission_mode": "default",
            "tool_input": {
                "file_path": str(self.test_file),
                "edits": [
                    {"old_string": "});\n", "new_string": "});\n\ntest('ok', function () {});\n"},
                    {"old_string": "assert.equal(deviceBCalls, 1, 'no retry attempted');", "new_string": ""},
                ],
            },
        }
        _, parsed = run_hook(payload)
        self.assertEqual(decision_of(parsed), "ask")

    def test_notebook_edit_uses_its_own_path_key(self):
        notebook = Path(self.tmp.name) / "tests" / "test_analysis.ipynb"
        notebook.write_text("{}", encoding="utf-8")
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "NotebookEdit",
            "permission_mode": "default",
            "tool_input": {"notebook_path": str(notebook), "new_source": "assert False"},
        }
        _, parsed = run_hook(payload)
        self.assertEqual(decision_of(parsed), "ask")

    def test_reason_names_the_file_and_the_rule(self):
        old = "  assert.equal(viz.diagnostics().trackState, 'none');\n"
        _, parsed = run_hook(edit_payload(str(self.test_file), old, ""))
        reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("test_bcviz_api.js", reason)
        self.assertIn("Rule 3", reason)

    def test_reason_states_that_plan_approval_is_not_consent(self):
        """Violation 3 of the incident: approval of a document read as per-act consent."""
        old = "  assert.equal(viz.diagnostics().trackState, 'none');\n"
        _, parsed = run_hook(edit_payload(str(self.test_file), old, ""))
        reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Approving a plan is not authorization for this edit", reason)


class PreservedTextEvasionTest(TestFileFixture):
    """Keeping the old text somewhere in the new text is not keeping the test.

    Every case here passed the original substring check, which asked only
    whether the old text still appeared anywhere in the new text. An
    assertion that is commented out, wrapped in a string, or moved into a
    branch that never runs is still present as text and no longer runs.
    """

    ASSERTION = "  assert.equal(viz.diagnostics().trackState, 'none');"

    def _decision_for(self, old: str, new: str) -> str:
        _, parsed = run_hook(edit_payload(str(self.test_file), old, new))
        return decision_of(parsed)

    def test_commenting_out_an_assertion_asks(self):
        for old, new in (
            ("assert authorized", "# assert authorized"),
            ("assert.ok(authorized)", "// assert.ok(authorized)"),
            (self.ASSERTION, "  // " + self.ASSERTION.strip()),
        ):
            with self.subTest(new=new):
                self.assertEqual(self._decision_for(old, new), "ask")

    def test_moving_an_assertion_into_dead_code_asks(self):
        new = "  if (false) {\n" + self.ASSERTION + "\n  }"
        self.assertEqual(self._decision_for(self.ASSERTION, new), "ask")

    def test_guarding_an_assertion_behind_a_condition_asks(self):
        new = "  if (process.env.CI) { assert.ok(x) }"
        self.assertEqual(self._decision_for("assert.ok(x)", new), "ask")

    def test_wrapping_an_assertion_in_a_string_asks(self):
        new = "  const dead = `" + self.ASSERTION + "`;"
        self.assertEqual(self._decision_for(self.ASSERTION, new), "ask")

    def test_appending_to_the_same_line_asks(self):
        """An addition that continues the last line can change its meaning."""
        self.assertEqual(self._decision_for("assert.ok(x)", "assert.ok(x) || true"), "ask")

    def test_insertion_into_the_middle_of_the_file_asks(self):
        """Only an end-of-file append can be verified as leaving the rest intact."""
        old = "  assert.equal(deviceBCalls, 1, 'no retry attempted');"
        new = old + "\n  assert.equal(2, 2);"
        self.assertEqual(self._decision_for(old, new), "ask")

    def test_end_of_file_append_still_passes(self):
        """The test-first workflow must stay unprompted for the normal case."""
        old = "});\n"
        new = "});\n\ntest('a new case', function () {\n  assert.equal(1, 1);\n});\n"
        self.assertEqual(self._decision_for(old, new), "")

    def test_whole_file_append_via_write_passes(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "permission_mode": "default",
            "tool_input": {
                "file_path": str(self.test_file),
                "content": EXISTING_TEST + "\ntest('added', function () {\n  assert.ok(1);\n});\n",
            },
        }
        _, parsed = run_hook(payload)
        self.assertEqual(decision_of(parsed), "")


class FailClosedTest(TestFileFixture):
    """Absence of a human is absence of consent."""

    def test_unattended_modes_deny(self):
        old = "  assert.equal(viz.diagnostics().trackState, 'none');\n"
        for mode in ("bypassPermissions", "dontAsk", "", "something-new"):
            with self.subTest(mode=mode):
                code, parsed = run_hook(edit_payload(str(self.test_file), old, "", mode))
                self.assertEqual(code, BLOCKING_EXIT_CODE)
                self.assertEqual(decision_of(parsed), "deny")

    def test_override_releases_only_the_named_path(self):
        old = "  assert.equal(viz.diagnostics().trackState, 'none');\n"
        granted = {"AGENTS_CONSENT_GRANTED": "tests/test_bcviz_api.js"}
        payload = edit_payload(str(self.test_file), old, "", "bypassPermissions")
        payload["cwd"] = self.tmp.name
        code, parsed = run_hook(payload, granted)
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "")

    def test_override_does_not_release_other_paths(self):
        other = Path(self.tmp.name) / "tests" / "test_other.js"
        other.write_text(EXISTING_TEST, encoding="utf-8")
        granted = {"AGENTS_CONSENT_GRANTED": "tests/test_bcviz_api.js"}
        payload = edit_payload(str(other), "  assert.equal(viz.diagnostics().trackState, 'none');\n", "")
        code, parsed = run_hook(payload, granted)
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "ask")


class PathAliasTest(unittest.TestCase):
    """A path is only as trustworthy as what it resolves to.

    Classifying the string the caller supplied, rather than the file it
    reaches, lets a symlink with an innocuous name carry an edit straight
    into a test file.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.realpath(self.tmp.name)
        os.makedirs(os.path.join(self.root, "tests"))
        self.test_file = Path(self.root) / "tests" / "test_auth.js"
        self.test_file.write_text(EXISTING_TEST, encoding="utf-8")

    def _edit(self, target: str, env: dict = None, mode: str = "default") -> str:
        payload = edit_payload(target, "  assert.equal(deviceBCalls, 1, 'no retry attempted');", "", mode)
        payload["cwd"] = self.root
        _, parsed = run_hook(payload, env)
        return decision_of(parsed)

    def test_symlink_with_an_innocuous_name_is_still_a_test(self):
        alias = Path(self.root) / "notes.txt"
        alias.symlink_to(self.test_file)
        self.assertEqual(self._edit(str(alias)), "ask")

    def test_test_named_symlink_pointing_outside_the_root_is_gated(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = Path(os.path.realpath(outside.name)) / "payload.js"
        target.write_text(EXISTING_TEST, encoding="utf-8")
        alias = Path(self.root) / "tests" / "test_escape.js"
        alias.symlink_to(target)
        self.assertEqual(self._edit(str(alias)), "ask")

    def test_ordinary_non_test_file_still_passes(self):
        source = Path(self.root) / "src.js"
        source.write_text("export function create() {}\n", encoding="utf-8")
        payload = edit_payload(str(source), "create() {}", "create() { return 1; }")
        payload["cwd"] = self.root
        _, parsed = run_hook(payload)
        self.assertEqual(decision_of(parsed), "")


class OverrideScopeTest(unittest.TestCase):
    """A grant names one file, not every file whose path ends the same way."""

    GRANT = {"AGENTS_CONSENT_GRANTED": "tests/test_auth.js"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.realpath(self.tmp.name)
        self.granted = self._make_test("tests")
        self.other = self._make_test(os.path.join("elsewhere", "tests"))

    def _make_test(self, relative_dir: str) -> Path:
        directory = Path(self.root) / relative_dir
        directory.mkdir(parents=True)
        path = directory / "test_auth.js"
        path.write_text(EXISTING_TEST, encoding="utf-8")
        return path

    def _edit(self, target: Path) -> str:
        payload = edit_payload(str(target), "  assert.equal(deviceBCalls, 1, 'no retry attempted');", "")
        payload["cwd"] = self.root
        _, parsed = run_hook(payload, self.GRANT)
        return decision_of(parsed)

    def test_grant_releases_the_named_file(self):
        self.assertEqual(self._edit(self.granted), "")

    def test_grant_does_not_release_a_matching_suffix_elsewhere(self):
        self.assertEqual(self._edit(self.other), "ask")


class QuestionChecklistTest(unittest.TestCase):
    """AskUserQuestion gets the gate checklist and never a decision."""

    def test_checklist_is_injected(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "AskUserQuestion",
            "permission_mode": "default",
            "tool_input": {"questions": []},
        }
        code, parsed = run_hook(payload)
        self.assertEqual(code, 0)
        self.assertEqual(decision_of(parsed), "")
        self.assertIn("existing test", parsed["hookSpecificOutput"]["additionalContext"])
        self.assertIn("Recommended", parsed["hookSpecificOutput"]["additionalContext"])


class SessionStartTest(unittest.TestCase):
    """The session is told which gates are live."""

    def test_session_start_states_the_gates(self):
        code, parsed = run_hook({"hook_event_name": "SessionStart"})
        self.assertEqual(code, 0)
        self.assertIn("Rule 3", parsed["hookSpecificOutput"]["additionalContext"])


class SettingsWiringTest(unittest.TestCase):
    """The hook enforces nothing unless the settings files register it."""

    @staticmethod
    def _matchers_for(settings: dict, command_fragment: str, event: str) -> list:
        """Return every matcher registering `command_fragment` for `event`."""
        return [
            matcher.get("matcher", "")
            for matcher in settings.get("hooks", {}).get(event, [])
            for entry in matcher.get("hooks", [])
            if command_fragment in entry.get("command", "")
        ]

    def _assert_registered(self, path: Path):
        settings = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(
            self._matchers_for(settings, "require_consent.py", "SessionStart"),
            f"{path.name} does not register require_consent.py for SessionStart",
        )
        pre_tool_use = self._matchers_for(settings, "require_consent.py", "PreToolUse")
        self.assertIn(
            EDIT_MATCHER, pre_tool_use,
            f"{path.name} does not register require_consent.py for {EDIT_MATCHER}",
        )
        self.assertIn(
            QUESTION_MATCHER, pre_tool_use,
            f"{path.name} does not register require_consent.py for {QUESTION_MATCHER}",
        )

    def test_live_settings_register_the_hook(self):
        self._assert_registered(LIVE_SETTINGS)

    def test_example_settings_register_the_hook(self):
        self._assert_registered(EXAMPLE_SETTINGS)

    def test_destructive_bash_hook_is_registered(self):
        """The incident's rm -rf and force-push ran because nothing wired this."""
        for path in (LIVE_SETTINGS, EXAMPLE_SETTINGS):
            with self.subTest(path=path.name):
                settings = json.loads(path.read_text(encoding="utf-8"))
                matchers = self._matchers_for(settings, "block_destructive_bash.py", "PreToolUse")
                self.assertIn("Bash", matchers, f"{path.name} does not register the Bash gate")


if __name__ == "__main__":
    unittest.main()
