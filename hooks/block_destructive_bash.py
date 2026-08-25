#!/usr/bin/env python3
"""Gate destructive and history-rewriting Bash commands via a PreToolUse hook.

Not part of AGENTS.md, which stays tool-agnostic and is synced to non-Claude
tools verbatim. This is a Claude-Code-specific hook under hooks/, wired via
`.claude/settings.json` (live in this repo) or
hooks/claude-code-settings.example.json (for adopting repos). It reads the
PreToolUse JSON payload from stdin and checks only Bash tool calls.

Two outcomes, because two different rules are in play:

`deny` covers commands with no legitimate form in this workflow: `rm -rf`
aimed at `/`, `~`, or `$HOME`, a bare `git push --force`, and
`git reset --hard`. It prints the reason on stderr and exits 2, so the block
holds wherever stdout JSON is ignored.

`ask` covers acts that are legitimate with the user's consent and forbidden
without it: `rm -rf` against any other target, the `--force-with-lease`
family, `git push --delete`, `git commit --amend`, `git rebase`, and
`git filter-branch`. Routing these through the permission prompt puts the
decision where AGENTS.md puts it, with the human, at the act. Rule 2 carries
no scope qualifier, so a scratch directory the session created itself is
gated like any other target, and a lease does not make a history rewrite
consented to.

An `ask` needs a human to answer it. When `permission_mode` reports an
unattended session, or reports a mode this hook does not recognize, the ask
becomes a deny: absence of a human is absence of consent.

A heuristic, not a sandbox: broad on purpose, since a false positive here is
far cheaper than a missed destructive command. It does not parse the shell,
so a command hidden behind a variable, alias, or wrapper script is invisible
to it.
"""
import json
import re
import sys

INTERACTIVE_MODES = frozenset({"default", "plan", "acceptEdits", "auto"})
FORCE_VARIANT = re.compile(r"(?<!\S)--force-[a-z-]+(?!\S)")


def _has_flag(command: str, letter: str, long_name: str) -> bool:
    """Return True if a short flag token containing `letter` or `long_name` appears."""
    if re.search(rf"(?<!\S)-[a-zA-Z]*{re.escape(letter)}[a-zA-Z]*(?!\S)", command):
        return True
    return long_name in command


def _is_git(command: str, subcommand: str) -> bool:
    """Return True if `command` invokes `git <subcommand>`."""
    return re.search(rf"\bgit\s+{subcommand}\b", command) is not None


def _is_recursive_force_rm(command: str) -> bool:
    """Return True if `command` is an rm carrying both recursive and force."""
    if not re.search(r"\brm\b", command):
        return False
    return _has_flag(command, "r", "--recursive") and _has_flag(command, "f", "--force")


def find_reason(command: str) -> str:
    """Return why `command` is denied outright, or an empty string if it is not."""
    if _is_recursive_force_rm(command) and re.search(r"(?:^|\s)(/|~|\$HOME)(?:\s|/|$)", command):
        return "rm -rf targeting / or the home directory"
    if _is_git(command, "push") and re.search(r"(?<!\S)(--force|-f)(?!\S)", command):
        return "git push --force"
    if _is_git(command, "reset") and "--hard" in command:
        return "git reset --hard"
    return ""


CONSENT_CHECKS = (
    (
        _is_recursive_force_rm,
        "rm -rf: Rule 2 gates every target, including a directory this session created",
    ),
    (
        lambda command: _is_git(command, "push") and FORCE_VARIANT.search(command) is not None,
        "git push with a --force variant: a lease is not consent to rewrite pushed history",
    ),
    (
        lambda command: _is_git(command, "push") and _has_flag(command, "d", "--delete"),
        "git push --delete: this removes a published ref",
    ),
    (
        lambda command: _is_git(command, "commit") and "--amend" in command,
        "git commit --amend: this rewrites a commit",
    ),
    (
        lambda command: _is_git(command, "rebase"),
        "git rebase: this rewrites history",
    ),
    (
        lambda command: _is_git(command, "filter-branch"),
        "git filter-branch: this rewrites history",
    ),
)


def find_consent_reason(command: str) -> str:
    """Return why `command` needs the user's consent, or an empty string."""
    for matches, reason in CONSENT_CHECKS:
        if matches(command):
            return reason
    return ""


def emit(decision: str, reason: str) -> int:
    """Print the hook's decision and return the exit code it needs."""
    message = f"blocked by hooks/block_destructive_bash.py: {reason}"
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


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    denied = find_reason(command)
    if denied:
        return emit("deny", denied)
    consent = find_consent_reason(command)
    if not consent:
        return 0
    if payload.get("permission_mode") in INTERACTIVE_MODES:
        return emit("ask", consent)
    return emit("deny", f"{consent}. No interactive session is available to consent.")


if __name__ == "__main__":
    sys.exit(main())
