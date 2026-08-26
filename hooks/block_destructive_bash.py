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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import _gate_core as core
except ImportError as error:  # pragma: no cover - exercised by the adoption test
    # Fail closed. Claude Code treats any non-zero exit other than 2 as a
    # non-blocking error, so an unhandled ImportError would wave the command
    # through in exactly the repos that installed this gate.
    _REASON = f"hooks/_gate_core.py could not be imported ({error}), so the gate cannot clear this command"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": _REASON,
    }}))
    print(_REASON, file=sys.stderr)
    sys.exit(2)

_CWD = [""]
GATE = "block_destructive_bash.py"
GATED_KEYWORDS = core.gated_keywords()
OPERATOR_CHARS = frozenset("&|;")
GROUPING = frozenset({"(", ")", "\n"})
WRAPPERS = frozenset({"sudo", "doas", "env", "time", "nohup", "nice", "command", "xargs", "timeout"})
# A shell handed a command string is a wrapper whose payload is another
# command. Reading only the program name sees "bash" and stops there.
INTERPRETERS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "busybox",
                          "cmd", "cmd.exe"})
INTERPRETER_PAYLOAD_FLAGS = frozenset({"-c", "--command", "/c", "/k"})
# Wrapper options that consume the token after them. Without these,
# `sudo -u root rm -rf /` leaves `root` as the apparent program.
WRAPPER_VALUE_OPTIONS = {
    "sudo": frozenset({"-u", "-g", "-p", "-C", "-h", "-U", "-r", "-t",
                       "--user", "--group", "--prompt", "--close-from", "--host", "--role", "--type"}),
    "doas": frozenset({"-u", "-C"}),
    "env": frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}),
    "xargs": frozenset({"-n", "-I", "-L", "-P", "-s", "-d", "-E", "-a",
                        "--max-args", "--replace", "--max-procs", "--delimiter", "--arg-file"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "timeout": frozenset({"-k", "-s", "--kill-after", "--signal"}),
}
REDIRECTION_CHARS = frozenset("<>&0123456789")
IMPLAUSIBLE_PROGRAM_CHARS = frozenset("<>&|;")


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


def _is_redirection(token: str) -> bool:
    """Return True if the token is a redirection operator such as > or 2>&1."""
    return bool(token) and ("<" in token or ">" in token) and set(token) <= REDIRECTION_CHARS


def _is_plausible_program(token: str) -> bool:
    """Return True if the token could name a command.

    A leading flag, a bare file descriptor, or a stray operator means the
    prefix strip did not reach the real program, so the caller fails closed
    rather than reporting that nothing gated was found.
    """
    if not token or token.startswith("-") or token.isdigit():
        return False
    return not (set(token) & IMPLAUSIBLE_PROGRAM_CHARS)


def _consumes_value(wrapper: str, token: str) -> bool:
    """Return True if this wrapper option takes the following token as its value."""
    if "=" in token:
        return False
    return token in WRAPPER_VALUE_OPTIONS.get(wrapper, frozenset())


def _redirect_targets(tokens: list) -> list:
    """Return the files this segment redirects into.

    Both spellings matter: `> path` arrives as two tokens under
    punctuation_chars, and `>path` as one.
    """
    targets = []
    for index, token in enumerate(tokens):
        if _is_redirection(token) and index + 1 < len(tokens):
            targets.append(tokens[index + 1])
        elif ">" in token and not _is_redirection(token):
            _, _, tail = token.partition(">")
            if tail:
                targets.append(tail)
    return targets


def _strip_prefixes(tokens: list) -> list:
    """Drop leading redirections, environment assignments, and wrappers.

    A wrapper's own options are consumed too. Stopping at the first token
    that begins with a dash left `-n` as the program of `sudo -n rm -rf /`,
    which is how an unguarded root delete read as an unknown command.
    """
    index = 0
    wrapper = ""
    while index < len(tokens):
        token = tokens[index]
        if _is_redirection(token):
            index += 2
            continue
        if _is_env_assignment(token):
            index += 1
            continue
        name = os.path.basename(token)
        if name in WRAPPERS:
            wrapper = name
            index += 1
            continue
        if wrapper and token.startswith("-"):
            index += 2 if _consumes_value(wrapper, token) else 1
            continue
        break
    return tokens[index:]


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
        elif parsing and core.is_short_group(token):
            recursive = recursive or "r" in token or "R" in token
        else:
            operands.append(token)
    return recursive, operands


def _rm_verdict(args: list) -> tuple:
    """Return (decision, reason) for an rm argument list."""
    recursive, operands = _rm_targets(args)
    return core.delete_verdict(recursive, operands, "recursive rm")


def _interpreter_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a shell handed a command string.

    Only the payload after -c, /c, or /k is another command. A shell
    invoked without one runs a script or a REPL, which this gate cannot
    read either way, so it is not gated on the interpreter's own name.
    """
    for index, token in enumerate(args):
        lowered = token.lower()
        if lowered in INTERPRETER_PAYLOAD_FLAGS:
            rest = args[index + 1:]
            if not rest:
                return "", ""
            # A POSIX shell takes one string after -c. CMD takes the whole
            # remainder of the line after /c or /k.
            if lowered.startswith("/"):
                return classify(" ".join(rest))
            return classify(rest[0])
        # busybox sh -c: the applet name precedes the flag
        if not token.startswith(("-", "/")) and lowered in INTERPRETERS:
            return _interpreter_verdict(lowered, args[index + 1:])
        # a combined short group such as -lc still carries the payload
        if token.startswith("-") and not token.startswith("--") and "c" in token:
            payload = args[index + 1:index + 2]
            return classify(payload[0]) if payload else ("", "")
    return "", ""


def _segment_verdict(tokens: list) -> tuple:
    """Return (decision, reason) for one command segment.

    The privilege verdict is folded into whatever the wrapped command
    yields, so `sudo ls` asks and `sudo rm -rf /` still denies.
    """
    privileged = core.privilege_verdict(tokens)
    redirects = _redirect_targets(tokens)
    tokens = _strip_prefixes(tokens)
    return core.strongest(privileged, _program_verdict(tokens, redirects))


def _program_verdict(tokens: list, redirects: list) -> tuple:
    """Return (decision, reason) for the program this segment runs."""
    if not tokens:
        return core.strongest(
            core.truncation_verdict("", [], redirects),
            core.test_write_verdict("", [], redirects))
    program = os.path.basename(tokens[0])
    if program.lower() in INTERPRETERS:
        return _interpreter_verdict(program, tokens[1:])
    if program == "rm":
        return _rm_verdict(tokens[1:])
    if program == "git":
        return core.git_verdict(tokens[1:], _CWD[0])
    args = tokens[1:]
    for verdict in (core.destruction_verdict(program, args),
                    core.alias_verdict(program, args),
                    core.mode_change_verdict(program, args),
                    core.truncation_verdict(program, args, redirects),
                    core.process_verdict(program, args),
                    core.schedule_verdict(program, args),
                    core.forge_verdict(program, args),
                    core.filesystem_repair_verdict(program, args),
                    core.profile_verdict(program, args, redirects),
                    core.cmd_delete_verdict(program, args),
                    core.test_write_verdict(program, args, redirects)):
        if verdict[0]:
            return verdict
    if not _is_plausible_program(program) and _mentions_gated_command(tokens):
        return "ask", ("the command boundaries could not be interpreted, so "
                       "the gate cannot clear it")
    return "", ""


def _mentions_gated_command(tokens: list) -> bool:
    """Return True if any token in the segment names a command this gate covers."""
    return any(os.path.basename(token) in GATED_KEYWORDS for token in tokens)


def classify(command: str) -> tuple:
    """Return the strongest (decision, reason) across the command's segments."""
    if not isinstance(command, str):
        return "ask", "the command is not a string, so the gate cannot read it"
    verdict = ("", "")
    for line in command.splitlines():
        tokens = _tokenize(line)
        if tokens is None:
            return core.unparseable_verdict(command, GATED_KEYWORDS)
        segments = _segments(tokens)
        verdict = core.strongest(
            verdict, core.remote_execution_verdict(segments))
        for segment in segments:
            verdict = core.strongest(verdict, _segment_verdict(segment))
    return verdict


def find_reason(command: str) -> str:
    """Return why `command` is denied outright, or an empty string if it is not."""
    decision, reason = classify(command)
    return reason if decision == "deny" else ""


def find_consent_reason(command: str) -> str:
    """Return why `command` needs the user's consent, or an empty string."""
    decision, reason = classify(command)
    return reason if decision == "ask" else ""


def emit(decision: str, reason: str) -> int:
    """Print the gate's decision and return the exit code it needs."""
    return core.emit(GATE, decision, reason)


def main() -> int:
    payload = core.read_payload()
    if payload is None:
        return emit("deny", "the hook payload could not be parsed, so the gate cannot clear this command")
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return emit("deny", "the tool input is malformed, so the gate cannot read this command")
    _CWD[0] = core.project_dir(payload)
    command = core.require_str(tool_input.get("command", ""))
    if command is None:
        return emit("deny", "the command field is not a string, so the gate cannot read it")
    decision, reason = classify(command)
    if not decision:
        return 0
    return core.decide(GATE, payload, decision, reason)


if __name__ == "__main__":
    sys.exit(main())
