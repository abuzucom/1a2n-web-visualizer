#!/usr/bin/env python3
"""Gate destructive and history-rewriting Bash commands via a PreToolUse hook.

Not part of AGENTS.md, which stays tool-agnostic and is synced to non-Claude
tools verbatim. This is a Claude-Code-specific hook under hooks/, wired via
`.claude/settings.json` (live in this repo) or
hooks/claude-code-settings.example.json (for adopting repos). It reads the
PreToolUse JSON payload from stdin and checks only Bash tool calls.

The command is tokenized and normalized before any decision. Matching the raw
string matches spelling rather than meaning, and every destructive command has
many spellings: `rm -Rf` for `rm -rf`, `git -C dir push --force` for
`git push --force`, `--force-with-lease=main:<oid>` for `--force-with-lease`,
`git push origin +HEAD:main` for a forced push with no flag at all. A gate
that reads the string lets each of those through while appearing to work.

Two outcomes, because two different rules are in play:

`deny` covers commands with no legitimate form in this workflow: a recursive
`rm` aimed at `/`, `~`, or `$HOME`, a bare `git push --force`/`-f`, and
`git reset --hard`. It prints the reason on stderr and exits 2, so the block
holds wherever stdout JSON is ignored.

`ask` covers acts that are legitimate with the user's consent and forbidden
without it: a recursive `rm` against any other target, the
`--force-with-lease` family, `git push --mirror`, `git push --delete`, a
forced (`+`) refspec, `git commit --amend`, `git rebase`, and
`git filter-branch`. Routing these through the permission prompt puts the
decision where AGENTS.md puts it, with the human, at the act. Rule 2 carries
no scope qualifier, so a scratch directory the session created itself is
gated like any other target, and a lease does not make a history rewrite
consented to.

Ambiguity fails closed. A command that will not tokenize, or a `git` whose
subcommand is hidden behind a variable, is gated rather than waved through:
the gate cannot clear what it cannot read.

An `ask` needs a human to answer it. When `permission_mode` reports an
unattended session, or a mode this hook does not recognize, the ask becomes a
deny: absence of a human is absence of consent.

Still a heuristic, not a sandbox. It does not execute the shell, so a command
hidden behind an alias, a wrapper script, or a variable holding the program
name is invisible to it.
"""
import json
import os
import shlex
import sys

INTERACTIVE_MODES = frozenset({"default", "plan", "acceptEdits", "auto"})
OPERATOR_CHARS = frozenset("&|;")
GROUPING = frozenset({"(", ")", "\n"})
WRAPPERS = frozenset({"sudo", "doas", "env", "time", "nohup", "nice", "command", "xargs"})
AMBIGUOUS_MARKERS = ("$", "`")
FILESYSTEM_ROOTS = frozenset({"/", "//", "/*"})
HOME_PREFIXES = ("~", "$HOME", "${HOME}")
GIT_VALUE_OPTIONS = frozenset({
    "-C", "-c", "--exec-path", "--git-dir", "--work-tree", "--namespace",
    "--config-env", "--super-prefix",
})
HISTORY_SUBCOMMANDS = {
    "rebase": "git rebase: this rewrites history",
    "filter-branch": "git filter-branch: this rewrites history",
    "filter-repo": "git filter-repo: this rewrites history",
}
STRENGTH = {"": 0, "ask": 1, "deny": 2}


def _tokenize(command: str):
    """Return the command's tokens, or None when it cannot be parsed."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _is_separator(token: str) -> bool:
    """Return True if the token separates one command from the next."""
    return token in GROUPING or (bool(token) and set(token) <= OPERATOR_CHARS)


def _segments(tokens: list) -> list:
    """Split tokens into the individual commands the shell would run."""
    segments = [[]]
    for token in tokens:
        if _is_separator(token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _is_env_assignment(token: str) -> bool:
    """Return True if the token is a leading VAR=value assignment."""
    if token.startswith("-") or "=" not in token:
        return False
    return token.split("=", 1)[0].isidentifier()


def _strip_prefixes(tokens: list) -> list:
    """Drop leading environment assignments and command wrappers."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if _is_env_assignment(token) or os.path.basename(token) in WRAPPERS:
            index += 1
            continue
        break
    return tokens[index:]


def _is_ambiguous(token: str) -> bool:
    """Return True if the token hides its value behind shell expansion."""
    return any(marker in token for marker in AMBIGUOUS_MARKERS)


def _is_short_group(token: str) -> bool:
    """Return True if the token is a bundle of short flags such as -Rf."""
    return token.startswith("-") and not token.startswith("--") and len(token) > 1


def _is_root_target(token: str) -> bool:
    """Return True if the token names the filesystem root or the home directory."""
    return token in FILESYSTEM_ROOTS or token.startswith(HOME_PREFIXES)


def _rm_targets(args: list) -> tuple:
    """Return (recursive, operands) for an rm argument list."""
    recursive = False
    operands = []
    parsing = True
    for token in args:
        if parsing and token == "--":
            parsing = False
        elif parsing and token.startswith("--"):
            recursive = recursive or token == "--recursive"
        elif parsing and _is_short_group(token):
            recursive = recursive or "r" in token or "R" in token
        else:
            operands.append(token)
    return recursive, operands


def _rm_verdict(args: list) -> tuple:
    """Return (decision, reason) for an rm argument list."""
    recursive, operands = _rm_targets(args)
    if not recursive:
        return "", ""
    if any(_is_root_target(operand) for operand in operands):
        return "deny", "recursive rm targeting / or the home directory"
    return "ask", "recursive rm: Rule 2 gates every target, including one this session created"


def _git_subcommand(args: list) -> tuple:
    """Return (subcommand, remaining args) after skipping git's global options."""
    index = 0
    while index < len(args):
        token = args[index]
        if not token.startswith("-"):
            return token, args[index + 1:]
        if token.split("=", 1)[0] in GIT_VALUE_OPTIONS and "=" not in token:
            index += 2
        else:
            index += 1
    return "", []


def _push_ask_reason(token: str, name: str) -> str:
    """Return why a single git push argument needs consent, or an empty string."""
    if name.startswith("--force"):
        return "git push with a --force variant: a lease is not consent to rewrite pushed history"
    if name == "--mirror":
        return "git push --mirror: this overwrites and deletes published refs"
    if name == "--delete" or (_is_short_group(token) and "d" in token):
        return "git push --delete: this removes a published ref"
    if not token.startswith("-") and token.startswith("+"):
        return "git push with a forced refspec: this rewrites pushed history"
    return ""


def _push_verdict(args: list) -> tuple:
    """Return (decision, reason) for a git push argument list."""
    ask = ""
    for token in args:
        name = token.split("=", 1)[0]
        if name == "--force" or (_is_short_group(token) and "f" in token):
            return "deny", "git push --force"
        ask = ask or _push_ask_reason(token, name)
    return ("ask", ask) if ask else ("", "")


def _git_verdict(args: list) -> tuple:
    """Return (decision, reason) for a git argument list."""
    subcommand, rest = _git_subcommand(args)
    if not subcommand or _is_ambiguous(subcommand):
        return "ask", "git with an unresolved subcommand: the gate cannot tell what this runs"
    if subcommand == "push":
        return _push_verdict(rest)
    if subcommand == "reset" and "--hard" in rest:
        return "deny", "git reset --hard"
    if subcommand == "commit" and "--amend" in rest:
        return "ask", "git commit --amend: this rewrites a commit"
    if subcommand in HISTORY_SUBCOMMANDS:
        return "ask", HISTORY_SUBCOMMANDS[subcommand]
    return "", ""


def _segment_verdict(tokens: list) -> tuple:
    """Return (decision, reason) for one command segment."""
    tokens = _strip_prefixes(tokens)
    if not tokens:
        return "", ""
    program = os.path.basename(tokens[0])
    if program == "rm":
        return _rm_verdict(tokens[1:])
    if program == "git":
        return _git_verdict(tokens[1:])
    return "", ""


def _unparseable_verdict(command: str) -> tuple:
    """Fail closed when a destructive-looking command will not tokenize."""
    if "rm" in command or "git" in command:
        return "ask", "this command could not be parsed, so the gate cannot clear it"
    return "", ""


def classify(command: str) -> tuple:
    """Return the strongest (decision, reason) across the command's segments."""
    tokens = _tokenize(command)
    if tokens is None:
        return _unparseable_verdict(command)
    strongest = ("", "")
    for segment in _segments(tokens):
        verdict = _segment_verdict(segment)
        if STRENGTH[verdict[0]] > STRENGTH[strongest[0]]:
            strongest = verdict
    return strongest


def find_reason(command: str) -> str:
    """Return why `command` is denied outright, or an empty string if it is not."""
    decision, reason = classify(command)
    return reason if decision == "deny" else ""


def find_consent_reason(command: str) -> str:
    """Return why `command` needs the user's consent, or an empty string."""
    decision, reason = classify(command)
    return reason if decision == "ask" else ""


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
    decision, reason = classify(payload.get("tool_input", {}).get("command", ""))
    if not decision:
        return 0
    if decision == "deny":
        return emit("deny", reason)
    if payload.get("permission_mode") in INTERACTIVE_MODES:
        return emit("ask", reason)
    return emit("deny", f"{reason}. No interactive session is available to consent.")


if __name__ == "__main__":
    sys.exit(main())
