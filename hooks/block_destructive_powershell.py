#!/usr/bin/env python3
"""Gate destructive PowerShell commands via a PreToolUse hook.

Not part of AGENTS.md, which stays tool-agnostic and is synced to non-Claude
tools verbatim. This is a Claude-Code-specific hook under hooks/, wired via
`.claude/settings.json` (live in this repo) or
hooks/claude-code-settings.example.json (for adopting repos). It reads the
PreToolUse JSON payload from stdin and checks only PowerShell tool calls.

Every decision comes from hooks/_gate_core.py, which
hooks/block_destructive_bash.py also imports. Only the parsing is
shell-specific: statement boundaries, the call operator and the cmdlets that
run another command, PowerShell's redirection forms, and `Remove-Item` with
its aliases and prefix-abbreviated parameters. A verdict reached here is the
verdict the Bash gate reaches for the equivalent command, by construction
rather than by promise, and tests/test_gate_parity.py asserts it.

Verified against synthetic payloads only. It has not been exercised against a
live PowerShell tool call.

PowerShell parameters may be abbreviated to any unambiguous prefix, so
`-Recurse`, `-Rec`, and `-r` are the same switch, and matching is
case-insensitive. Matching the full spelling alone would read
`Remove-Item -r` as non-recursive.

Still a heuristic, not a sandbox. A command behind a function, a module, or a
variable holding a cmdlet name is invisible to it.
"""
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_CWD = [""]
GATE = "block_destructive_powershell.py"

try:
    import _gate_core as core
except ImportError as error:  # pragma: no cover - exercised by the adoption test
    # Fail closed. Claude Code treats any non-zero exit other than 2 as a
    # non-blocking error, so an unhandled ImportError would wave the command
    # through in exactly the repos that installed this gate.
    _REASON = (f"hooks/_gate_core.py could not be imported ({error}), so the "
               "gate cannot clear this command")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": _REASON,
    }}))
    print(_REASON, file=sys.stderr)
    sys.exit(2)

GATED_KEYWORDS = core.gated_keywords() + tuple(core.DELETE_PROGRAMS)
SEPARATORS = frozenset({";", "|", "&&", "||", "\n"})
# The call operator and the cmdlets that run a command given to them.
WRAPPERS = frozenset({"&", "start-process", "invoke-expression", "iex",
                      "invoke-command", "sudo"})
# Both shells are here, not only this one. A gate that knows only its own
# interpreters leaves `bash -c 'rm -rf /etc'` as a hole, and on a Windows box
# carrying Git Bash that line runs.
INTERPRETERS = core.SHELL_INTERPRETERS
INTERPRETER_PAYLOAD_FLAGS = core.SHELL_PAYLOAD_FLAGS
REDIRECTIONS = frozenset({">", ">>", "2>", "2>>", "*>", "*>>", "3>", "4>",
                          "5>", "6>"})
# Start-Process hands its target a plain argument list rather than a command
# string, so the payload has to be read as arguments to that program.
ARGUMENT_LIST_FLAGS = frozenset(
    [f"-{'argumentlist'[:n]}" for n in range(1, 13)] + ["-args"])
FILE_PATH_FLAGS = frozenset(f"-{'filepath'[:n]}" for n in range(2, 9))
SCRIPT_BLOCK_DELIMITERS = "{}"
MAX_WRAPPER_DEPTH = 4


def _tokenize(command: str):
    """Return the command's tokens, or None when it cannot be parsed."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    # PowerShell escapes with a backtick. A backslash is a path separator,
    # and treating it as an escape turns C:\work\build into C:workbuild,
    # which matches no root and no test path.
    lexer.escape = "`"
    try:
        return list(lexer)
    except ValueError:
        return None


def _segments(tokens: list) -> list:
    """Split tokens into the statements PowerShell would run separately."""
    segments = [[]]
    for token in tokens:
        if token in SEPARATORS or (token and set(token) <= set("&|;")):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _redirect_targets(tokens: list) -> list:
    """Return the files this statement redirects into."""
    targets = []
    for index, token in enumerate(tokens):
        if token in REDIRECTIONS and index + 1 < len(tokens):
            targets.append(tokens[index + 1])
    return targets


def _interpreter_verdict(program: str, args: list, depth: int = 0) -> tuple:
    """Return (decision, reason) for an interpreter handed a command.

    `depth` bounds the re-entry below, which follows one interpreter into
    the arguments another handed it. A hostile command can nest launches
    without limit; the gate reads a fixed number and then gives up, which
    the unparseable path turns into a prompt rather than a pass.
    """
    if depth >= MAX_WRAPPER_DEPTH:
        return "", ""
    for index, token in enumerate(args):
        lowered = token.lower()
        if lowered in ARGUMENT_LIST_FLAGS:
            rest = args[index + 1:]
            if not rest:
                return "", ""
            # -ArgumentList carries arguments for `program`, not a command
            # line of its own, so `/c rd /s /q C:\` has to be read as cmd's
            # arguments. Reading it as a statement finds a program named /c.
            nested = _tokenize(rest[0])
            if nested is None:
                return core.unparseable_verdict(rest[0])
            return _interpreter_verdict(program, nested, depth + 1)
        if lowered in INTERPRETER_PAYLOAD_FLAGS:
            rest = args[index + 1:]
            if not rest:
                return "", ""
            # cmd takes the remainder of the line; PowerShell takes one
            # string after -Command.
            if lowered.startswith("/"):
                return classify(" ".join(rest))
            return classify(rest[0])
    return "", ""


def _strip_wrappers(tokens: list) -> list:
    """Drop the call operator, the cmdlets that run a command, and braces.

    `& { Remove-Item -Recurse -Force /etc }` puts a script block where a
    program name goes. Reading `{` as the program sees no delete at all,
    so the braces come off with the wrapper that introduced them.
    """
    index = 0
    while index < len(tokens):
        token = tokens[index].strip(SCRIPT_BLOCK_DELIMITERS)
        name = os.path.basename(token).lower()
        if not token or name in WRAPPERS or name in FILE_PATH_FLAGS:
            index += 1
            continue
        break
    return [token.strip(SCRIPT_BLOCK_DELIMITERS) for token in tokens[index:]
            if token.strip(SCRIPT_BLOCK_DELIMITERS)]


def _statement_verdict(tokens: list) -> tuple:
    """Return (decision, reason) for one PowerShell statement."""
    privileged = core.privilege_verdict(tokens)
    redirects = _redirect_targets(tokens)
    return core.strongest(privileged, _program_verdict(tokens, redirects))


def _program_verdict(tokens: list, redirects: list) -> tuple:
    """Return (decision, reason) for the cmdlet this statement runs."""
    stripped = _strip_wrappers(tokens)
    if len(stripped) < len(tokens) and len(stripped) == 1 and " " in stripped[0]:
        # Invoke-Expression and the call operator take a command as one
        # string. Reading it as a program name sees the whole statement.
        return classify(stripped[0])
    tokens = [token for token in stripped if token not in REDIRECTIONS]
    if not tokens:
        return core.test_write_verdict("", [], redirects)
    program = os.path.basename(tokens[0]).lower()
    if program in INTERPRETERS:
        return _interpreter_verdict(program, tokens[1:])
    if program in core.DELETE_PROGRAMS:
        return core.any_delete_verdict(program, tokens[1:])
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
    return "", ""


def classify(command) -> tuple:
    """Return the strongest (decision, reason) across the command's statements."""
    if not isinstance(command, str):
        return "ask", "the command is not a string, so the gate cannot read it"
    verdict = ("", "")
    for line in command.splitlines():
        tokens = _tokenize(line)
        if tokens is None:
            return core.unparseable_verdict(command.lower(), GATED_KEYWORDS)
        segments = _segments(tokens)
        verdict = core.strongest(
            verdict, core.remote_execution_verdict(segments))
        for segment in segments:
            verdict = core.strongest(verdict, _statement_verdict(segment))
    return verdict


def main() -> int:
    payload = core.read_payload()
    if payload is None:
        return core.emit(GATE, "deny", "the hook payload could not be parsed, "
                                       "so the gate cannot clear this command")
    if payload.get("tool_name") != "PowerShell":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return core.emit(GATE, "deny", "the tool input is malformed, so the "
                                       "gate cannot read this command")
    _CWD[0] = core.project_dir(payload)
    command = core.require_str(tool_input.get("command", ""))
    if command is None:
        return core.emit(GATE, "deny", "the command field is not a string, so "
                                       "the gate cannot read it")
    _CWD[0] = core.project_dir(payload)
    decision, reason = classify(command)
    if not decision:
        return 0
    return core.decide(GATE, payload, decision, reason)


if __name__ == "__main__":
    sys.exit(main())
