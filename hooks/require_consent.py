#!/usr/bin/env python3
"""Route rule-governed writes through a per-act human decision.

Not part of AGENTS.md, which stays tool-agnostic and is synced to non-Claude
tools verbatim. This is a Claude-Code-specific hook under hooks/, wired via
`.claude/settings.json` (live in this repo) or
hooks/claude-code-settings.example.json (for adopting repos). One file serves
three registrations, dispatched on `hook_event_name` and `tool_name`.

`PreToolUse` on Edit, Write, MultiEdit, and NotebookEdit gates writes to test
files. AGENTS.md Rule 3 says an agent that finds a test wrong stops, reports,
and waits for a human decision. An agent can talk itself out of that rule by
deciding the rule's purpose does not cover this case; it cannot talk itself
past a permission prompt. So the gate returns `ask` and the human answers.

The gate stays out of the way of the mandated test-first workflow. A new test
file passes. An append to an existing test file passes, detected by the old
string surviving verbatim inside the new one. What gets gated is an edit that
removes or rewrites existing test content, drops an assertion, or introduces
a skip marker. Existing test content is a human's recorded decision, and a
comment explaining why a test asserts what it asserts is the strongest form
of that signal, not a license to overrule it.

`PreToolUse` on AskUserQuestion injects a checklist and never a decision. A
question that hides the rule-governed cost of an option, and labels it
Recommended, takes the choice away from the user before any gate can fire.
The checklist is a reminder, not enforcement. The edit gate is what makes the
omission survivable.

`SessionStart` states which gates are live.

An `ask` needs a human to answer it. When `permission_mode` reports an
unattended session, or a mode this hook does not recognize, the ask becomes a
deny: absence of a human is absence of consent. For headless runs a human
sets AGENTS_CONSENT_GRANTED at launch to a comma-separated list of paths the
gate may release. The model cannot forge it, since Bash tool calls do not
persist shell state and this hook inherits Claude Code's environment rather
than the model's shell.

Known gap: a Bash call can still write a test file through a redirect or a
here-document, which no Edit or Write matcher sees. The CI backstop covers
that case by requiring code-owner approval on the pull request.
"""
import json
import os
import re
import sys

INTERACTIVE_MODES = frozenset({"default", "plan", "acceptEdits", "auto"})
GATED_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
TEST_DIR_PARTS = frozenset({"tests", "test", "__tests__", "spec"})
TEST_NAME = re.compile(
    r"^test_.+\.(py|js|mjs|cjs|ts|jsx|tsx|ipynb)$"
    r"|_test\.(py|js|mjs|cjs|ts|go|rb)$"
    r"|\.(test|spec)\.(js|mjs|cjs|jsx|ts|tsx)$"
)
PATH_KEYS = ("file_path", "notebook_path")
ASSERTION_TOKENS = ("assert", "expect(", "should.")
WEAKENING_MARKERS = (
    ".skip(", ".only(", "xit(", "xdescribe(", "test.todo", "it.todo",
    "skip: true", "todo: true", "@unittest.skip", "self.skipTest(",
    "@pytest.mark.skip", "@pytest.mark.xfail", "t.Skip(",
)
OVERRIDE_ENV = "AGENTS_CONSENT_GRANTED"

CHECKLIST = """GATE CHECKLIST before you ask this question.

Does any option require editing an existing test, deleting files or
directories, rewriting pushed history, adding or upgrading a dependency, or
changing a public API contract?

If yes, that option must name the artifact and the rule in its own text, and
must say it requires the user's sign-off. Do not label it Recommended. State
the rule-governed cost, not only the engineering trade-off: the user cannot
make a call you did not put in front of them."""

SESSION_NOTICE = """Consent gates are live in this repository.

Edits that remove, rewrite, or weaken existing test content route to the user
for a decision at the act (AGENTS.md Rule 3). Destructive and history
rewriting Bash commands do the same (Rule 2). Adding a new test, or appending
one to an existing file, is not gated.

Approval of a plan is not authorization for the individual acts inside it."""


def _read_payload() -> dict:
    """Return the hook's stdin JSON, or an empty dict when stdin carries none."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def _project_dir(payload: dict) -> str:
    """Return the repository root, preferring Claude Code's own variable."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()


def is_test_path(path: str) -> bool:
    """Return True if `path` names a test file by directory or by filename."""
    normalized = os.path.normpath(path).replace(os.sep, "/")
    parts = normalized.split("/")
    if TEST_DIR_PARTS.intersection(parts[:-1]):
        return True
    return bool(TEST_NAME.search(parts[-1]))


def count_assertions(text: str) -> int:
    """Return how many assertion tokens `text` contains."""
    return sum(text.count(token) for token in ASSERTION_TOKENS)


def find_new_markers(old: str, new: str) -> list:
    """Return the skip or todo markers `new` introduces that `old` lacks."""
    return [marker for marker in WEAKENING_MARKERS if marker in new and marker not in old]


def classify_edit(old: str, new: str) -> str:
    """Return why replacing `old` with `new` weakens a test, or an empty string."""
    markers = find_new_markers(old, new)
    if markers:
        return f"introduces {', '.join(markers)}, which disables or weakens a test"
    if old not in new:
        return "removes or rewrites existing test content"
    if count_assertions(new) < count_assertions(old):
        return "drops an assertion"
    return ""


def read_text(path: str) -> str:
    """Return the file's contents, or an empty string when it cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ""


def collect_edits(tool_name: str, tool_input: dict, target: str) -> list:
    """Return the (old, new) text pairs this tool call would apply."""
    if tool_name == "MultiEdit":
        return [
            (edit.get("old_string", ""), edit.get("new_string", ""))
            for edit in tool_input.get("edits", [])
        ]
    if tool_name == "Write":
        return [(read_text(target), tool_input.get("content", ""))]
    return [(tool_input.get("old_string", ""), tool_input.get("new_string", ""))]


def find_gate_reason(tool_name: str, tool_input: dict, target: str) -> str:
    """Return why this write needs the user's consent, or an empty string."""
    if not is_test_path(target) or not os.path.exists(target):
        return ""
    if tool_name == "NotebookEdit":
        return "rewrites a cell in an existing test notebook"
    for old, new in collect_edits(tool_name, tool_input, target):
        reason = classify_edit(old, new)
        if reason:
            return reason
    return ""


def resolve_target(tool_input: dict, project_dir: str) -> str:
    """Return the absolute path this tool call writes to, or an empty string."""
    for key in PATH_KEYS:
        raw = tool_input.get(key)
        if raw:
            return raw if os.path.isabs(raw) else os.path.join(project_dir, raw)
    return ""


def is_override_granted(target: str) -> bool:
    """Return True if a human released `target` through the override variable."""
    normalized = os.path.normpath(target).replace(os.sep, "/")
    for entry in os.environ.get(OVERRIDE_ENV, "").split(","):
        cleaned = entry.strip().strip("/")
        if cleaned and (normalized == cleaned or normalized.endswith("/" + cleaned)):
            return True
    return False


def build_reason(target: str, reason: str) -> str:
    """Return the text the user reads on the permission prompt."""
    return (
        f"{os.path.basename(target)}: this edit {reason}. "
        "AGENTS.md Rule 3 says stop, report it, and wait for a human decision. "
        "Approving a plan is not authorization for this edit; consent is per act. "
        "Allow it only if you decided this test should change."
    )


def emit(decision: str, reason: str) -> int:
    """Print the hook's decision and return the exit code it needs."""
    message = f"gated by hooks/require_consent.py: {reason}"
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": message,
        }
    }
    print(json.dumps(output))
    if decision == "deny":
        print(message, file=sys.stderr)
        return 2
    return 0


def emit_context(event: str, context: str) -> int:
    """Print `context` for Claude to read before it acts."""
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": context}
    }))
    return 0


def _handle_write(payload: dict, project_dir: str) -> int:
    """Gate a write that would weaken an existing test."""
    tool_input = payload.get("tool_input", {})
    target = resolve_target(tool_input, project_dir)
    if not target:
        return 0
    reason = find_gate_reason(payload.get("tool_name", ""), tool_input, target)
    if not reason:
        return 0
    if is_override_granted(target):
        return 0
    if payload.get("permission_mode") in INTERACTIVE_MODES:
        return emit("ask", build_reason(target, reason))
    return emit(
        "deny",
        f"{build_reason(target, reason)} No interactive session is available to consent.",
    )


def _handle_pre_tool_use(payload: dict, project_dir: str) -> int:
    """Dispatch on the tool the session is about to call."""
    tool_name = payload.get("tool_name", "")
    if tool_name == "AskUserQuestion":
        return emit_context("PreToolUse", CHECKLIST)
    if tool_name in GATED_TOOLS:
        return _handle_write(payload, project_dir)
    return 0


def main() -> int:
    payload = _read_payload()
    project_dir = _project_dir(payload)
    if payload.get("hook_event_name") == "PreToolUse":
        return _handle_pre_tool_use(payload, project_dir)
    return emit_context("SessionStart", SESSION_NOTICE)


if __name__ == "__main__":
    sys.exit(main())
