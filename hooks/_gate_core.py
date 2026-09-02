#!/usr/bin/env python3
"""Shared decision logic for the shell gates.

Not part of AGENTS.md, which stays tool-agnostic and is synced to non-Claude
tools verbatim. This module holds everything the Bash and PowerShell gates
decide identically, so the two cannot drift: payload reading and field-type
validation, the deny and ask emission, the ask-to-deny downgrade for an
unattended session, root-target detection, and the whole git classification.

Each gate keeps only what its shell spells differently: how a command
tokenizes, where one statement ends, which wrappers and redirections lead a
command, and how a delete's flags are written. Both call in here for the
verdict.

A hook run as `python3 .../hooks/<gate>.py` gets `hooks/` as `sys.path[0]`,
so `import _gate_core` resolves with no packaging. A gate that cannot import
this module must fail closed rather than crash, because Claude Code treats a
non-zero exit other than 2 as a non-blocking error, which waves the command
through.
"""
import base64
import binascii
import json
import os
import posixpath
import re
import shlex
import sys

INTERACTIVE_MODES = frozenset({"default", "plan", "acceptEdits", "auto"})
AMBIGUOUS_MARKERS = ("$", "`")
FILESYSTEM_ROOTS = frozenset({"/", "//", "/*"})
# A UNC share root is \\\\server\\share, so at most two components; a drive
# root is two characters, C:. Both name a whole volume, not a path in one.
UNC_SHARE_ROOT_PARTS = 2
DRIVE_ROOT_LENGTH = 2
MAX_GIT_CONFIG_COUNT = 1000
MAX_GIT_ALIAS_DEPTH = 10
GIT_SHORT_OPTION_VALUE_INDEX = 2
# section.subsection.key, the only shape a driver name takes.
GIT_CONFIG_SUBSECTION_PARTS = 3
# Latin-1 renders as \\xNN; everything above it needs \\uNNNN.
MAX_LATIN1_CODEPOINT = 0xFF
# A forge delete reads as "<noun> delete <target>", so two words minimum.
FORGE_DELETE_MIN_WORDS = 2
# Directories whose removal takes the machine with them. These deny rather
# than ask: putting "delete /etc?" in front of a person is not consent, it
# is an invitation to a mistake nobody can undo.
SYSTEM_ROOTS = frozenset({
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32",
    "/lib64", "/libx32", "/media", "/mnt", "/opt", "/proc", "/root",
    "/run", "/sbin", "/srv", "/sys", "/temp", "/tmp", "/usr", "/var",
    "/system", "/library", "/applications", "/volumes", "/users",
    "/private", "/cores",
})

HOME_PREFIXES = ("~", "$HOME", "${HOME}", "$env:USERPROFILE",
                 "$Env:USERPROFILE", "%USERPROFILE%", "%HOMEPATH%")
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


def require_str(value):
    """Return `value` when it is a string, otherwise None.

    A gate that reads a field without checking its type crashes on a number
    or a list, and a crash is an exit code Claude Code ignores.
    """
    return value if isinstance(value, str) else None


def is_ambiguous(token: str) -> bool:
    """Return True if the token hides its value behind shell expansion."""
    return any(marker in token for marker in AMBIGUOUS_MARKERS)


def is_short_group(token: str) -> bool:
    """Return True if the token is a bundle of short flags such as -Rf."""
    return token.startswith("-") and not token.startswith("--") and len(token) > 1


def _is_drive_root(token: str) -> bool:
    """Return True for the root of any drive or share.

    C:\\, D:/, \\\\server\\share, and the bare drive letter C: all name a
    whole volume. No workflow deletes one, so these deny rather than ask:
    an agent has no business putting that choice in front of a person.
    """
    candidate = token.strip().strip('"').strip("'")
    if candidate.startswith("\\\\") or candidate.startswith("//"):
        parts = [part for part in candidate.replace("\\", "/").split("/") if part]
        return len(parts) <= UNC_SHARE_ROOT_PARTS
    stripped = candidate.rstrip("\\/")
    return (len(stripped) == DRIVE_ROOT_LENGTH and stripped[1] == ":"
            and stripped[0].isalpha())


def _is_system_root(token: str) -> bool:
    """Return True if the token names a system directory itself.

    A path inside one is an ordinary recursive delete and still asks. The
    directory itself is not a target any workflow has.
    """
    candidate = token.strip().strip('"').strip("'").replace("\\", "/")
    if not candidate:
        return False
    # posixpath, not os.path: on Windows os.path.normpath("/etc") returns
    # "\\etc", so a check anchored on a leading slash rejects every POSIX
    # system root on the platform where a Windows agent runs.
    normalized = posixpath.normpath(candidate).lower()
    if not normalized.startswith("/"):
        return False
    return normalized in SYSTEM_ROOTS


def is_root_target(token: str) -> bool:
    """Return True if the token names the filesystem root or a home directory."""
    if _is_system_root(token) or _is_drive_root(token):
        return True
    return token in FILESYSTEM_ROOTS or token.startswith(HOME_PREFIXES)


def strongest(first: tuple, second: tuple) -> tuple:
    """Return whichever (decision, reason) pair carries the stronger decision."""
    return second if STRENGTH[second[0]] > STRENGTH[first[0]] else first


def delete_verdict(recursive: bool, operands: list, noun: str) -> tuple:
    """Return (decision, reason) for a recursive delete over `operands`.

    Each shell parses its own flags and hands the result here, so `rm -Rf`
    and `Remove-Item -Recurse -Force` reach the same answer. `noun` carries
    the caller's own wording, so each gate names the command its user typed.
    """
    if not recursive:
        return "", ""
    if any(is_root_target(operand) for operand in operands):
        return "deny", f"{noun} targeting / or the home directory"
    return "ask", f"{noun}: Rule 2 gates every target, including one this session created"


def git_subcommand(args: list) -> tuple:
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


def _push_flag_reason(token: str, name: str) -> str:
    """Return why a git push flag needs consent, or an empty string."""
    if name.startswith("--force"):
        return "git push with a --force variant: a lease is not consent to rewrite pushed history"
    if name == "--mirror":
        return "git push --mirror: this overwrites and deletes published refs"
    if name == "--delete" or (is_short_group(token) and "d" in token):
        return "git push --delete: this removes a published ref"
    if name == "--prune":
        return "git push --prune: this deletes every remote ref with no local counterpart"
    return ""


def _push_operand_reason(token: str) -> str:
    """Return why a git push refspec needs consent, or an empty string.

    A refspec deletes or rewrites without carrying any flag: `+HEAD:main`
    forces, and `:main` pushes an empty source, which deletes the remote ref.
    """
    if token.startswith("+"):
        return "git push with a forced refspec: this rewrites pushed history"
    if token.startswith(":"):
        return "git push with an empty-source refspec: this deletes the remote ref"
    return ""


def push_ask_reason(token: str, name: str) -> str:
    """Return why a single git push argument needs consent, or an empty string."""
    if token.startswith("-"):
        return _push_flag_reason(token, name)
    return _push_operand_reason(token)


def push_verdict(args: list) -> tuple:
    """Return (decision, reason) for a git push argument list."""
    ask = ""
    for token in args:
        name = token.split("=", 1)[0]
        if name == "--force" or (is_short_group(token) and "f" in token):
            # Asked rather than refused, at the user's direction. A refusal
            # offers no way to consent, and the pushed-history rule is about
            # consent rather than impossibility.
            return "ask", ("git push --force rewrites published history, so "
                           "anyone who has fetched this branch keeps commits "
                           "that no longer exist upstream")
        ask = ask or push_ask_reason(token, name)
    return ("ask", ask) if ask else ("", "")


READ_SUBCOMMANDS = frozenset({"status", "diff", "log", "show", "blame",
                              "grep", "shortlog", "whatchanged"})


KNOWN_SUBCOMMANDS = frozenset({
    "push", "reset", "commit", "rebase", "filter-branch", "add", "checkout",
    "switch", "restore", "merge", "fetch", "pull", "clone", "branch", "tag",
    "remote", "stash", "config", "init", "rm", "mv", "cherry-pick", "revert",
    "bisect", "worktree", "submodule", "describe", "rev-parse", "ls-files",
    "clean",
    "cat-file", "hash-object", "check-attr", "replace", "update-index",
    "apply", "am", "format-patch", "archive", "gc", "reflog", "notes",
}) | READ_SUBCOMMANDS


def _git_alias_verdict(subcommand: str, rest: list, cwd: str) -> tuple:
    """Return (decision, reason) for a subcommand git does not define."""
    expansion = resolve_alias(cwd, subcommand)
    if not expansion:
        return "ask", (f"git {sanitize(subcommand)}: not a git subcommand "
                       "and not a declared alias, so the gate cannot tell "
                       "what this runs")
    if expansion.startswith("!"):
        # A shell alias. Classify the text; never expand or run it.
        return "ask", (f"git {sanitize(subcommand)} is a shell alias, "
                       "which the gate cannot read as a git command")
    return git_verdict(expansion.split() + rest, cwd)


def _git_resolution_verdict(subcommand: str, rest: list, args: list,
                            cwd: str, environment: list) -> tuple:
    """Return a verdict for a subcommand needing resolution, else None.

    None means git defines the subcommand and it is not a read, so the
    caller reads its flags.
    """
    if not subcommand or is_ambiguous(subcommand):
        return "ask", ("git with an unresolved subcommand: the gate cannot "
                       "tell what this runs")
    if subcommand in READ_SUBCOMMANDS:
        return git_read_verdict(args, cwd, environment)
    if subcommand in KNOWN_SUBCOMMANDS:
        return None
    return _git_alias_verdict(subcommand, rest, cwd)


def _git_branch_verdict(rest: list) -> tuple:
    """Return (decision, reason) for a git branch argument list."""
    # Case carries the meaning here: -d refuses an unmerged branch, -D
    # discards it. Lowercasing first would gate the safe one.
    lowered = [token.lower() for token in rest]
    forced = (("--delete" in lowered and "--force" in lowered)
              or any(token.startswith("-") and not token.startswith("--")
                     and "D" in token for token in rest))
    if forced:
        return "ask", ("git branch -D discards a branch whose commits "
                       "may not be merged anywhere else")
    return "", ""


def _git_clean_verdict(rest: list) -> tuple:
    """Return (decision, reason) for a git clean argument list."""
    lowered = [token.lower() for token in rest]
    if any(flag in lowered for flag in ("-n", "--dry-run")):
        return "", ""
    if any(flag.startswith("-") and ("d" in flag or "x" in flag)
           for flag in lowered):
        return "ask", ("git clean removing untracked files, over a set "
                       "decided at run time")
    return "", ""


def _git_flag_verdict(subcommand: str, rest: list) -> tuple:
    """Return (decision, reason) for the subcommands one flag decides."""
    if subcommand == "reset" and "--hard" in rest:
        return "deny", "git reset --hard"
    if subcommand == "commit" and "--amend" in rest:
        return "ask", "git commit --amend: this rewrites a commit"
    if subcommand in HISTORY_SUBCOMMANDS:
        return "ask", HISTORY_SUBCOMMANDS[subcommand]
    return "", ""


# Subcommands whose whole argument list decides the verdict, rather than
# one flag. push stays out: it runs before the alias check below.
GIT_SUBCOMMAND_READERS = {
    "branch": _git_branch_verdict,
    "clean": _git_clean_verdict,
}


def git_verdict(args: list, cwd: str = "", environment: list = None) -> tuple:
    """Return (decision, reason) for a git argument list."""
    subcommand, rest = git_subcommand(args)
    resolved = _git_resolution_verdict(
        subcommand, rest, args, cwd, environment or [])
    if resolved is not None:
        return resolved
    if subcommand == "push":
        return push_verdict(rest)
    alias_decision = alias_verdict("git", [subcommand] + rest)
    if alias_decision[0]:
        return alias_decision
    reader = GIT_SUBCOMMAND_READERS.get(subcommand)
    if reader:
        return reader(rest)
    return _git_flag_verdict(subcommand, rest)


def unparseable_verdict(command: str, keywords: tuple) -> tuple:
    """Fail closed when a command naming one of `keywords` will not tokenize.

    A command the gate cannot parse but which names a drive root or a
    system directory denies rather than asks. `rm -rf C:\\` ends in an
    unterminated escape, and no reading of it is one to put to a person.
    """
    if not any(keyword in command for keyword in keywords):
        return "", ""
    words = command.replace("\\", "/").split()
    for word in words:
        base = os.path.basename(word).lower().removesuffix(".exe")
        if base.split(".", 1)[0] in ALWAYS_DESTRUCTIVE:
            return "deny", (f"this command could not be parsed and names "
                            f"{sanitize(base)}, which only partitions, "
                            "formats, or wipes")
        if is_root_target(word) or is_root_target(word.rstrip("/") + "/"):
            return "deny", ("this command could not be parsed and names a "
                            "root or system directory")
    return "ask", "this command could not be parsed, so the gate cannot clear it"


def read_payload(empty_is_session_start: bool = False):
    """Return the stdin payload, or None when it cannot be parsed.

    `empty_is_session_start` yields an empty dict for empty stdin, which
    is how a SessionStart invocation arrives. Without it that hook would
    deny every session start. A gate that answers "fine" to input it
    could not read is worse than no gate, so anything else that will not
    parse is still None.
    """
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return None
    if empty_is_session_start and not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def emit(gate: str, decision: str, reason: str) -> int:
    """Print the gate's decision and return the exit code it needs."""
    message = f"blocked by hooks/{gate}: {reason}"
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


def decide(gate: str, payload: dict, decision: str, reason: str) -> int:
    """Emit the decision, turning an ask nobody can answer into a deny."""
    if decision == "deny":
        return emit(gate, "deny", reason)
    if require_str(payload.get("permission_mode")) in INTERACTIVE_MODES:
        return emit(gate, "ask", reason)
    return emit(gate, "deny", f"{reason}. No interactive session is available "
                              f"to consent (permission_mode {mode_label(payload)}).")


MAX_REASON_VALUE = 160


def mode_label(payload: dict) -> str:
    """Return the payload's permission_mode as text safe to put in a prompt.

    INTERACTIVE_MODES is a fixed list, so an interactive mode Claude Code
    adds later denies here. Naming the value is what separates that from a
    genuinely unattended session, which otherwise read identically.
    """
    mode = require_str(payload.get("permission_mode"))
    return sanitize(mode) if mode is not None else "absent"


def sanitize(value) -> str:
    """Render untrusted text as printable ASCII on a single line.

    An allowlist, not a strip. Zero-width characters, bidi overrides, and
    Unicode tag characters are not control characters, and they render
    invisibly or reverse the text around them, so a denylist of known-bad
    codepoints misses the cases that matter most. These values reach two
    readers who cannot afford to be misled: the human deciding on the
    permission prompt, and the model reading stderr as tool output.
    """
    rendered = []
    for character in str(value):
        if " " <= character <= "~":
            rendered.append(character)
        elif ord(character) <= MAX_LATIN1_CODEPOINT:
            rendered.append(f"\\x{ord(character):02x}")
        else:
            rendered.append(f"\\u{ord(character):04x}")
    text = "".join(rendered)
    if len(text) > MAX_REASON_VALUE:
        return text[:MAX_REASON_VALUE] + "...[truncated]"
    return text


def project_dir(payload: dict) -> str:
    """Return the repository root, preferring Claude Code's own variable."""
    return (os.environ.get("CLAUDE_PROJECT_DIR")
            or payload.get("cwd")
            or os.getcwd())


def resolved_under(root: str, *parts: str):
    """Return the joined path when it stays under `root`, else None.

    Joining a payload-supplied directory with a fixed relative path and
    running the result executes whatever sits at that path. Canonicalize
    first and require the result to stay inside the tree.
    """
    base = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(base, *parts))
    if candidate == base or candidate.startswith(base + os.sep):
        return candidate
    return None


CMD_DELETE_VERBS = frozenset({"del", "erase", "rd", "rmdir"})
# Both shells reach the other through an interpreter, so each gate has to
# read a delete spelled the other way. The readings live here rather than in
# a gate, so neither can learn a spelling the other does not.
POSIX_DELETE_PROGRAMS = frozenset({"rm"})
POWERSHELL_DELETE_PROGRAMS = frozenset({"remove-item", "ri", "remove-itemproperty"})
DELETE_PROGRAMS = (POSIX_DELETE_PROGRAMS | POWERSHELL_DELETE_PROGRAMS
                   | CMD_DELETE_VERBS)
# -Recurse abbreviates to any unambiguous prefix, and -Force to -fo.
RECURSE_PREFIXES = tuple(f"-{'recurse'[:n]}" for n in range(1, 8))
POWERSHELL_PATH_FLAGS = frozenset({"-path", "-literalpath"})


def posix_delete_verdict(args: list) -> tuple:
    """Return (decision, reason) for a POSIX rm argument list."""
    recursive = False
    operands = []
    parsing = True
    for token in args:
        if parsing and token == "--":
            parsing = False
        elif parsing and token.startswith("--"):
            recursive = recursive or token == "--recursive"
        elif parsing and is_short_group(token):
            recursive = recursive or "r" in token or "R" in token
        else:
            operands.append(token)
    return delete_verdict(recursive, operands, "recursive rm")


def powershell_delete_verdict(args: list) -> tuple:
    """Return (decision, reason) for a Remove-Item argument list."""
    recursive = False
    operands = []
    for token in args:
        if token.startswith("-"):
            recursive = recursive or token.lower() in RECURSE_PREFIXES
        elif token.lower() not in POWERSHELL_PATH_FLAGS:
            operands.append(token)
    return delete_verdict(recursive, operands, "recursive Remove-Item")


def any_delete_verdict(program: str, args: list) -> tuple:
    """Return the strongest verdict any shell's reading of a delete gives.

    rd, rmdir, del, and erase name both a Remove-Item alias and a CMD verb,
    and the three shells spell recursion differently (-r against -Recurse
    against /s). Take whichever reading is strongest rather than guessing
    which shell the caller meant, because guessing wrong clears the act.
    """
    return strongest(posix_delete_verdict(args),
                     strongest(powershell_delete_verdict(args),
                               cmd_delete_verdict(program, args)))


# Interpreters reach one shell from the other. A gate that knows only its
# own leaves `powershell -Command` and `bash -c` as holes in the other.
SHELL_INTERPRETERS = frozenset({
    "bash", "sh", "zsh", "dash", "ksh", "busybox",
    "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
})
SHELL_PAYLOAD_FLAGS = frozenset({"-c", "--command", "-command", "/c", "/k"})
POWERSHELL_PROGRAMS = frozenset({"powershell", "powershell.exe", "pwsh", "pwsh.exe"})
POWERSHELL_ENCODED_FLAGS = frozenset(
    {"-e", "-ec"}
    | {f"-{'encodedcommand'[:length]}"
       for length in range(2, len("encodedcommand") + 1)}
)
MAX_COMMAND_DEPTH = 4
CMD_RECURSIVE_FLAGS = frozenset({"/s"})


def decode_powershell_command(value: str) -> tuple:
    """Return a strict UTF-16LE EncodedCommand payload or a deny reason."""
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None, "PowerShell EncodedCommand is not strict Base64"
    if len(raw) % 2:
        return None, "PowerShell EncodedCommand has an odd UTF-16LE byte length"
    try:
        return raw.decode("utf-16le", errors="strict"), ""
    except UnicodeDecodeError:
        return None, "PowerShell EncodedCommand is not valid UTF-16LE"


def powershell_payload(args: list) -> tuple:
    """Return (kind, payload or reason) for PowerShell command arguments."""
    for index, token in enumerate(args):
        lowered = token.lower()
        if lowered in POWERSHELL_ENCODED_FLAGS:
            if index + 1 >= len(args):
                return "deny", "PowerShell EncodedCommand has no Base64 payload"
            payload, reason = decode_powershell_command(args[index + 1])
            return ("deny", reason) if payload is None else ("command", payload)
        if lowered in ("-c", "-command", "--command"):
            if index + 1 < len(args):
                return "command", args[index + 1]
            return "", ""
    return "", ""


def cmd_delete_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a CMD deletion verb.

    CMD flags are slash-prefixed and case-insensitive, and rd and rmdir
    remove a directory tree whenever /s is present. del and erase take
    /s to recurse into subdirectories.
    """
    if program.lower() not in CMD_DELETE_VERBS:
        return "", ""
    recursive = False
    operands = []
    for token in args:
        if token.startswith("/"):
            recursive = recursive or token.lower() in CMD_RECURSIVE_FLAGS
        else:
            operands.append(token)
    return delete_verdict(recursive, operands, f"recursive {program.lower()}")


TEST_DIR_PARTS = frozenset({"tests", "test", "__tests__", "spec"})
TEST_NAME = re.compile(
    r"^test_.+\.(py|js|mjs|cjs|ts|jsx|tsx|ipynb)$"
    r"|_test\.(py|js|mjs|cjs|ts|go|rb)$"
    r"|\.(test|spec)\.(js|mjs|cjs|jsx|ts|tsx)$",
    re.IGNORECASE,
)
# Commands whose named operand is a file they overwrite in place.
WRITE_PROGRAMS = {
    "tee": 0, "sed": -1, "cp": -1, "mv": -1,
    "set-content": 0, "sc": 0, "add-content": 0, "ac": 0,
    "out-file": 0, "copy-item": -1, "cpi": -1, "move-item": -1,
    "mi": -1,
}
# (canonical name, shortest valid unambiguous prefix, names an output target).
CONTENT_PARAMETERS = (
    ("path", 3, True), ("literalpath", 1, True), ("value", 2, False),
)
OUTPUT_PARAMETERS = (("filepath", 2, True), ("inputobject", 3, False))
COPY_PARAMETERS = (
    ("path", 3, False), ("literalpath", 1, False),
    ("destination", 3, True),
)
POWERSHELL_WRITE_PARAMETERS = {
    "set-content": CONTENT_PARAMETERS, "sc": CONTENT_PARAMETERS,
    "add-content": CONTENT_PARAMETERS, "ac": CONTENT_PARAMETERS,
    "out-file": OUTPUT_PARAMETERS,
    "copy-item": COPY_PARAMETERS, "cpi": COPY_PARAMETERS,
    "move-item": COPY_PARAMETERS, "mi": COPY_PARAMETERS,
}
PROTECTED_PATH_PARTS = frozenset({"hooks", ".claude", "scripts"})


def strip_windows_decorations(name: str) -> str:
    """Return the filename Windows opens for `name`.

    An NTFS alternate data stream (`test_x.py:evil`) writes into the same
    file, and Windows discards a trailing dot or space.
    """
    base = name.split(":", 1)[0] if ":" in name[2:] else name
    return base.rstrip(". ")


def is_test_path(path: str) -> bool:
    """Return True if `path` names a test file by directory or filename."""
    normalized = os.path.normpath(path).replace("\\", "/").replace(os.sep, "/")
    parts = [part.lower() for part in normalized.split("/")]
    if TEST_DIR_PARTS.intersection(parts[:-1]):
        return True
    return bool(TEST_NAME.search(strip_windows_decorations(parts[-1])))


def test_write_verdict(program: str, args: list, redirect_targets: list) -> tuple:
    """Return (decision, reason) for a command that writes to a test file.

    A redirect or an in-place edit reaches a test file where no Edit or
    Write matcher can see it, so Rule 3 would apply to the same act
    through one tool and not the other.
    """
    targets = _known_write_targets(program, args, redirect_targets)
    for target in targets:
        if is_test_path(target):
            return "ask", ("writes to an existing test file, which Rule 3 "
                           "puts in front of the user at the act")
    return "", ""


def _powershell_write_operands(name: str, args: list) -> tuple:
    """Return named targets and unused positional write operands."""
    targets = []
    operands = []
    index = 0
    while index < len(args):
        token = args[index]
        flag, separator, attached = token.lower().partition(":")
        parameter = _powershell_write_parameter(name, flag)
        if parameter:
            value = attached if separator else ""
            if not separator and index + 1 < len(args):
                index += 1
                value = args[index]
            if parameter[2] and value:
                targets.append(value)
        elif not token.startswith("-"):
            operands.append(token)
        index += 1
    return targets, operands


def _powershell_write_parameter(name: str, flag: str):
    """Return the parameter matched by a valid unambiguous prefix."""
    candidate = flag.lstrip("-")
    for parameter in POWERSHELL_WRITE_PARAMETERS.get(name, ()):
        canonical, minimum, _target = parameter
        if len(candidate) >= minimum and canonical.startswith(candidate):
            return parameter
    return None


def _known_write_targets(program: str, args: list, redirects: list) -> list:
    """Return known output operands for redirects and write programs."""
    targets = list(redirects)
    name = os.path.basename(program).lower().removesuffix(".exe")
    position = WRITE_PROGRAMS.get(name)
    if position is None:
        return targets
    named_targets, operands = _powershell_write_operands(name, args)
    targets.extend(named_targets)
    if operands:
        targets.append(operands[position])
    return targets


def _protected_path(path: str, cwd: str) -> bool:
    """Return True when a literal path is under a protected gate directory."""
    cleaned = path.strip().strip('"').strip("'")
    if not cleaned or is_ambiguous(cleaned):
        return False
    root = os.path.realpath(cwd or ".")
    candidate = cleaned if os.path.isabs(cleaned) else os.path.join(root, cleaned)
    candidate = os.path.realpath(candidate)
    try:
        relative = os.path.relpath(candidate, root)
    except ValueError:
        return False
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return False
    head = relative.replace("\\", "/").split("/", 1)[0].lower()
    return head in PROTECTED_PATH_PARTS


def protected_write_verdict(program: str, args: list,
                            redirects: list, cwd: str) -> tuple:
    """Gate known shell writes to repository-controlled hook files."""
    for target in _known_write_targets(program, args, redirects):
        if _protected_path(target, cwd):
            return "ask", ("a known shell write to hooks/, .claude/, or scripts/. "
                           "These prompts are best-effort workflow checks")
    return "", ""


MAX_CONFIG_BYTES = 256 * 1024
MAX_REPO_DISCOVERY_DEPTH = 100
# Keys whose value names a program git runs during an ordinary read.
EXEC_CAPABLE_KEYS = frozenset({
    "core.fsmonitor", "core.pager", "core.editor", "core.sshcommand",
    "core.hookspath", "core.alternaterefscommand", "core.askpass",
    "diff.external", "log.showsignature", "gpg.program",
    "uploadpack.packobjectshook", "sequence.editor", "pager.diff",
})
# Sections where any driver name carries an exec-capable key.
EXEC_CAPABLE_SUBSECTIONS = {
    "filter": ("clean", "smudge", "process"),
    "diff": ("textconv", "command"),
    "gpg": ("program",),
    "merge": ("driver",),
}


def _read_config_path(path: str):
    """Return config text, "" when absent, or None when unreadable."""
    try:
        if os.path.getsize(path) > MAX_CONFIG_BYTES:
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError):
        return None


def _section_name(header: str) -> str:
    """Return the normalized section name for a [section "sub"] header."""
    name, _, subsection = header.partition(" ")
    if not subsection:
        return name.lower()
    return f"{name.lower()}.{subsection.strip().strip(chr(34))}"


def _parse_git_config_path(path: str):
    """Return normalized config entries from `path`, or None on failure.

    The file is read, never queried through `git config`: running git to
    decide whether running git is safe is the bug this exists to close.
    Format is git's own, which configparser does not implement.
    """
    raw = _read_config_path(path)
    if raw is None:
        return None
    entries = {}
    section = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = _section_name(stripped[1:-1].strip())
            continue
        key, separator, value = stripped.partition("=")
        if not separator:
            parts = stripped.split(None, 1)
            key = parts[0]
            value = parts[1] if len(parts) > 1 else "true"
        key = key.strip().lower()
        if (not section or not key or not key[0].isalpha()
                or not key.replace("-", "").isalnum()):
            return None
        entries[f"{section}.{key}"] = value.strip()
    return entries


def parse_git_config(cwd: str):
    """Return normalized entries from the repository config under `cwd`."""
    path = os.path.join(cwd or ".", ".git", "config")
    return _parse_git_config_path(path)


def _exec_capable_key(entries: dict) -> str:
    """Return the first exec-capable key present, or an empty string."""
    for name, value in entries.items():
        if name in EXEC_CAPABLE_KEYS and value.lower() not in ("", "false", "0"):
            return name
        if name.startswith("pager.") and value.lower() not in ("", "false", "0"):
            return name
        if ((name.startswith("include.") or name.startswith("includeif."))
                and name.endswith(".path") and value):
            return name
        parts = name.split(".")
        if (len(parts) == GIT_CONFIG_SUBSECTION_PARTS
                and parts[2] in EXEC_CAPABLE_SUBSECTIONS.get(parts[0], ())
                and value.lower() not in ("", "false", "0")):
            return name
    return ""


def _assignment_map(assignments: list) -> dict:
    """Return leading environment assignments with last-value-wins order."""
    values = {}
    for name, value in assignments:
        values[name] = value
    return values


def _parse_config_setting(setting: str):
    """Return a normalized git config pair, or None when malformed."""
    key, separator, value = setting.partition("=")
    key = key.strip().lower()
    if not separator or not key:
        return None
    return key, value


def _apply_git_environment_locations(state: dict, environment: dict) -> str:
    """Apply repository locations supplied through the environment."""
    if not state["explicit_git_dir"] and "GIT_DIR" in environment:
        value = environment["GIT_DIR"]
        if not value or is_ambiguous(value):
            return "GIT_DIR names an unresolved repository"
        state["git_dir"] = os.path.realpath(os.path.join(state["cwd"], value))
        state["explicit_git_dir"] = True
        state["repository_override"] = True
    if "GIT_COMMON_DIR" in environment:
        value = environment["GIT_COMMON_DIR"]
        if not value or is_ambiguous(value):
            return "GIT_COMMON_DIR names an unresolved repository"
        state["common_dir"] = os.path.realpath(os.path.join(state["cwd"], value))
        state["repository_override"] = True
    if not state["work_tree"] and "GIT_WORK_TREE" in environment:
        value = environment["GIT_WORK_TREE"]
        if not value or is_ambiguous(value):
            return "GIT_WORK_TREE names an unresolved work tree"
        state["work_tree"] = os.path.realpath(os.path.join(state["cwd"], value))
        state["repository_override"] = True
    return ""


def _finalize_git_state(state: dict, environment: dict) -> tuple:
    """Apply environment locations and return Git state or its error."""
    reason = _apply_git_environment_locations(state, environment)
    return (None, reason) if reason else (state, "")


def _apply_git_config_argument(args: list, index: int,
                               token: str, state: dict) -> tuple:
    """Apply one -c setting and return its last argument index."""
    setting = token[GIT_SHORT_OPTION_VALUE_INDEX:] if token != "-c" else ""
    if token == "-c":
        index += 1
        setting = args[index] if index < len(args) else ""
    parsed = _parse_config_setting(setting)
    if parsed is None:
        return index, "git -c has a missing or malformed setting"
    state["settings"].append(parsed)
    return index, ""


def _apply_git_path_argument(args: list, index: int,
                             token: str, state: dict) -> tuple:
    """Apply one repository path option and return its last argument index."""
    name, separator, attached = token.partition("=")
    value = attached if separator else ""
    if not separator:
        index += 1
        value = args[index] if index < len(args) else ""
    if not value or is_ambiguous(value):
        return index, f"git {name} has a missing or unresolved path"
    resolved = os.path.realpath(os.path.join(state["cwd"], value))
    if name == "-C":
        state["cwd"] = resolved
    elif name == "--git-dir":
        state["git_dir"] = resolved
        state["explicit_git_dir"] = True
    else:
        state["work_tree"] = resolved
    state["repository_override"] = True
    return index, ""


def _apply_git_global_argument(args: list, index: int, state: dict) -> tuple:
    """Apply one Git global argument and return its last index or an error."""
    token = args[index]
    name = token.partition("=")[0]
    if (token == "-c" or token.startswith("-c")
            and len(token) > GIT_SHORT_OPTION_VALUE_INDEX):
        return _apply_git_config_argument(args, index, token, state)
    if name in ("-C", "--git-dir", "--work-tree"):
        return _apply_git_path_argument(args, index, token, state)
    if name == "--config-env":
        return index, "git --config-env cannot be inspected from command text"
    return index, ""


def _git_global_state(args: list, cwd: str, environment: dict = None) -> tuple:
    """Return invocation settings and repository location, or an error."""
    environment = environment or {}
    state = {
        "settings": [],
        "cwd": os.path.realpath(cwd or "."),
        "git_dir": "",
        "common_dir": "",
        "work_tree": "",
        "explicit_git_dir": False,
        "repository_override": False,
    }
    index = 0
    while index < len(args) and args[index].startswith("-"):
        index, reason = _apply_git_global_argument(args, index, state)
        if reason:
            return None, reason
        index += 1
    return _finalize_git_state(state, environment)


def _read_gitdir_pointer(path: str, marker: str):
    """Return a path stored in a small git administrative pointer file."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read(MAX_REASON_VALUE).strip()
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError):
        return None
    if marker:
        name, separator, raw = raw.partition(":")
        if name.strip().lower() != marker or not separator:
            return None
    return raw.strip() or None


def _parent_repository_dir(current: str, device: int) -> tuple:
    """Return the next parent on the same device, or an inspection error."""
    parent = os.path.dirname(current)
    if parent == current:
        return "", ""
    try:
        parent_device = os.stat(parent).st_dev
    except OSError:
        return None, "a parent repository directory could not be inspected"
    if parent_device != device:
        return "", ""
    return parent, ""


def _discover_dot_git(cwd: str) -> tuple:
    """Return the .git entry Git discovers upward, or an inspection error."""
    current = os.path.realpath(cwd or ".")
    try:
        device = os.stat(current).st_dev
    except OSError:
        return None, "the repository search root could not be inspected"
    for _depth in range(MAX_REPO_DISCOVERY_DEPTH):
        dot_git = os.path.join(current, ".git")
        try:
            os.stat(dot_git)
        except FileNotFoundError:
            pass
        except OSError:
            return None, "a parent repository entry could not be inspected"
        else:
            return dot_git, ""
        parent, reason = _parent_repository_dir(current, device)
        if parent is None:
            return None, reason
        if not parent:
            return "", ""
        current = parent
    return None, "the parent repository search exceeded its depth limit"


def _redirected_repo_config_paths(dot_git: str) -> tuple:
    """Return config paths reached through a .git pointer file."""
    value = _read_gitdir_pointer(dot_git, "gitdir")
    if value is None:
        return None, "the redirected repository config could not be resolved"
    git_dir = os.path.realpath(os.path.join(os.path.dirname(dot_git), value))
    common = _read_gitdir_pointer(os.path.join(git_dir, "commondir"), "")
    if common is None:
        return None, "the redirected repository common config could not be resolved"
    if not common:
        return [(os.path.join(git_dir, "config"), True)], ""
    common_dir = os.path.realpath(os.path.join(git_dir, common))
    return [
        (os.path.join(common_dir, "config"), True),
        (os.path.join(git_dir, "config"), False),
        (os.path.join(git_dir, "config.worktree"), False),
    ], ""


def _repo_config_paths(state: dict) -> tuple:
    """Return repository config paths with required-file markers."""
    if state["common_dir"]:
        paths = [(os.path.join(state["common_dir"], "config"), True)]
        if state["git_dir"] and state["git_dir"] != state["common_dir"]:
            paths.append((os.path.join(state["git_dir"], "config.worktree"), False))
        return paths, ""
    if state["explicit_git_dir"]:
        return [(os.path.join(state["git_dir"], "config"), True)], ""
    dot_git, reason = _discover_dot_git(state["cwd"])
    if dot_git is None:
        return None, reason
    if not dot_git:
        return [(os.path.join(state["cwd"], ".git", "config"), False)], ""
    if not os.path.isfile(dot_git):
        return [(os.path.join(dot_git, "config"), False)], ""
    return _redirected_repo_config_paths(dot_git)


def _environment_config(environment: dict) -> tuple:
    """Return config settings supplied through GIT_CONFIG_COUNT."""
    raw_count = environment.get("GIT_CONFIG_COUNT")
    if raw_count is None:
        return [], ""
    try:
        count = int(raw_count)
    except ValueError:
        return None, "GIT_CONFIG_COUNT is not a non-negative integer"
    if count < 0 or count > MAX_GIT_CONFIG_COUNT:
        return None, "GIT_CONFIG_COUNT is outside the inspectable range"
    settings = []
    for index in range(count):
        key = environment.get(f"GIT_CONFIG_KEY_{index}")
        value = environment.get(f"GIT_CONFIG_VALUE_{index}")
        if key is None or value is None:
            return None, "GIT_CONFIG_COUNT names an incomplete key/value vector"
        parsed = _parse_config_setting(f"{key}={value}")
        if parsed is None:
            return None, "GIT_CONFIG_COUNT names a malformed setting"
        settings.append(parsed)
    return settings, ""


CONFIG_PATH_ENV = (
    "GIT_CONFIG", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_LOCAL", "GIT_CONFIG_WORKTREE",
)


def _read_invocation_configs(state: dict, environment: dict,
                             assigned_names: set = None) -> tuple:
    """Return merged file config entries or a fail-closed reason."""
    assigned_names = assigned_names or set()
    entries = {}
    for variable in CONFIG_PATH_ENV:
        path = environment.get(variable)
        if path is None:
            continue
        if not path or is_ambiguous(path):
            return None, f"{variable} names an uninspectable config path"
        resolved = os.path.realpath(os.path.join(state["cwd"], path))
        parsed = _parse_git_config_path(resolved)
        if parsed is None or (variable in assigned_names and not os.path.isfile(resolved)):
            return None, f"{variable} config could not be read"
        entries.update(parsed)
    repo_paths, reason = _repo_config_paths(state)
    if repo_paths is None:
        return None, reason
    for repo_path, required in repo_paths:
        parsed = _parse_git_config_path(repo_path)
        if parsed is None or (required and not os.path.isfile(repo_path)):
            return None, "the redirected repository config could not be read"
        entries.update(parsed)
    return entries, ""


def _environment_exec_key(environment: dict) -> str:
    """Return the first environment variable that makes a git read execute."""
    pager = environment.get("GIT_PAGER")
    if pager is None:
        pager = environment.get("PAGER")
        pager_name = "PAGER"
    else:
        pager_name = "GIT_PAGER"
    if pager:
        return pager_name
    if environment.get("GIT_EXTERNAL_DIFF"):
        return "GIT_EXTERNAL_DIFF"
    return ""


def is_relevant_git_environment(name: str) -> bool:
    """Return True when a variable can alter inspected Git behavior."""
    return (name in {
        "GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_PAGER", "PAGER",
        "GIT_EXTERNAL_DIFF", "GIT_CONFIG", "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_GLOBAL", "GIT_CONFIG_LOCAL", "GIT_CONFIG_WORKTREE",
        "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL",
    } or name.startswith("GIT_CONFIG_KEY_")
        or name.startswith("GIT_CONFIG_VALUE_"))


def _git_environment(assignments: list) -> dict:
    """Return effective relevant environment values for one invocation."""
    environment = {
        name: value for name, value in os.environ.items()
        if is_relevant_git_environment(name)
    }
    environment.update(_assignment_map(assignments))
    return environment


def _effective_git_entries(state: dict, environment: dict,
                           assigned_names: set = None) -> tuple:
    """Return merged config entries and ordered invocation settings."""
    entries, reason = _read_invocation_configs(
        state, environment, assigned_names)
    if entries is None:
        return None, None, reason
    env_settings, reason = _environment_config(environment)
    if env_settings is None:
        return None, None, reason
    settings = env_settings + state["settings"]
    for key, value in settings:
        entries[key] = value
    return entries, settings, ""


def git_read_verdict(args: list, cwd: str, assignments: list) -> tuple:
    """Classify executable settings and config paths for one git read."""
    environment = _git_environment(assignments)
    if "GIT_CONFIG_PARAMETERS" in environment:
        return "ask", "GIT_CONFIG_PARAMETERS cannot be inspected safely"
    state, reason = _git_global_state(args, cwd, environment)
    if state is None:
        return "ask", reason
    assigned_names = {name for name, _value in assignments}
    entries, _, reason = _effective_git_entries(
        state, environment, assigned_names)
    if entries is None:
        return "ask", reason
    found = _environment_exec_key(environment) or _exec_capable_key(entries)
    if not found:
        return "", ""
    return "ask", (f"a git read sets {found}, which names a program git runs")


def _shell_alias_write_label(expansion: str, entries: dict,
                             depth: int) -> tuple:
    """Return a write label found inside a Git shell alias."""
    try:
        shell_tokens = shlex.split(expansion[1:])
    except ValueError:
        return "", "git shell alias could not be inspected"
    for index, token in enumerate(shell_tokens):
        if os.path.basename(token).lower().removesuffix(".exe") != "git":
            continue
        nested, nested_rest = git_subcommand(shell_tokens[index + 1:])
        label, reason = _alias_write_label(
            nested, nested_rest, entries, depth + 1)
        if label or reason:
            return label, reason
        return "", "git shell alias may hide a Git write"
    return "", "git shell alias may execute an uninspectable command"


def _alias_write_label(subcommand: str, rest: list,
                       entries: dict, depth: int = 0) -> tuple:
    """Return a resolved write label and an alias-resolution error."""
    if subcommand in ("commit", "push"):
        return f"git {subcommand}", ""
    expansion = entries.get(f"alias.{subcommand.lower()}", "")
    if not expansion:
        return "", ""
    if depth >= MAX_GIT_ALIAS_DEPTH:
        return "", "git alias expansion exceeds the inspection limit"
    if expansion.startswith("!"):
        return _shell_alias_write_label(expansion, entries, depth)
    try:
        expanded = shlex.split(expansion)
    except ValueError:
        return "", "git alias could not be inspected"
    nested, nested_rest = git_subcommand(expanded + rest)
    return _alias_write_label(nested, nested_rest, entries, depth + 1)


def _git_write_context(state: dict, environment: dict, assignments: list,
                       settings: list, resolution: tuple) -> dict:
    """Return structured context for an effective Git write."""
    label, error = resolution
    return {
        "label": label,
        "error": error,
        "cwd": state["cwd"],
        "git_dir": state["git_dir"],
        "common_dir": state["common_dir"],
        "work_tree": state["work_tree"],
        "repository_override": state["repository_override"],
        "assignments": assignments,
        "settings": settings,
        "environment": environment,
    }


def _could_be_alias(subcommand: str) -> bool:
    """Return True when an unknown subcommand may resolve through config."""
    return bool(subcommand) and (
        is_ambiguous(subcommand) or subcommand not in KNOWN_SUBCOMMANDS)


def _ambiguous_git_context(state: dict, environment: dict,
                           assignments: list, subcommand: str,
                           reason: str) -> dict:
    """Return a fail-closed context for an alias source we cannot inspect."""
    label = f"git {sanitize(subcommand)}" if subcommand else "ambiguous git write"
    return _git_write_context(
        state, environment, assignments, [], (label, reason))


def _fallback_git_state(cwd: str) -> dict:
    """Return minimal state for a Git write whose globals were malformed."""
    return {
        "cwd": os.path.realpath(cwd or "."), "git_dir": "",
        "common_dir": "", "work_tree": "", "repository_override": True,
    }


def _resolve_git_write_context(state: dict, environment: dict,
                               assignments: list, subcommand: str,
                               rest: list) -> dict:
    """Resolve aliases and return context for a Git write."""
    direct_label = f"git {subcommand}" if subcommand in ("commit", "push") else ""
    assigned_names = {name for name, _value in assignments}
    entries, settings, reason = _effective_git_entries(
        state, environment, assigned_names)
    if entries is None:
        if direct_label or _could_be_alias(subcommand):
            return _git_write_context(
                state, environment, assignments, [],
                (direct_label or f"git {sanitize(subcommand)}", reason))
        return {}
    if is_ambiguous(subcommand):
        return _ambiguous_git_context(
            state, environment, assignments, subcommand,
            "git subcommand is nonliteral and cannot be resolved")
    label, alias_error = _alias_write_label(subcommand, rest, entries)
    if not label and not alias_error:
        return {}
    return _git_write_context(
        state, environment, assignments, settings,
        (label or f"git {sanitize(subcommand)}", alias_error))


def git_write_context(args: list, cwd: str, assignments: list) -> dict:
    """Return effective context for a Git commit or push, including aliases."""
    subcommand, rest = git_subcommand(args)
    direct_label = f"git {subcommand}" if subcommand in ("commit", "push") else ""
    environment = _git_environment(assignments)
    state, reason = _git_global_state(args, cwd, environment)
    if state is None:
        if direct_label or _could_be_alias(subcommand):
            return _ambiguous_git_context(
                _fallback_git_state(cwd), environment, assignments,
                subcommand, reason)
        return {}
    if "GIT_CONFIG_PARAMETERS" in environment:
        if direct_label or _could_be_alias(subcommand):
            return _ambiguous_git_context(
                state, environment, assignments, subcommand,
                "GIT_CONFIG_PARAMETERS cannot be inspected safely")
        return {}
    return _resolve_git_write_context(
        state, environment, assignments, subcommand, rest)


def git_checker_environment(context: dict) -> dict:
    """Return a constrained child environment matching a Git invocation."""
    environment = dict(os.environ)
    for name, value in context.get("assignments", []):
        if is_relevant_git_environment(name):
            environment[name] = value
    locations = {
        "GIT_DIR": context.get("git_dir", ""),
        "GIT_COMMON_DIR": context.get("common_dir", ""),
        "GIT_WORK_TREE": context.get("work_tree", ""),
    }
    for name, value in locations.items():
        if value:
            environment[name] = value
    settings = context.get("settings", [])
    if settings:
        for name in list(environment):
            if (name == "GIT_CONFIG_COUNT" or name.startswith("GIT_CONFIG_KEY_")
                    or name.startswith("GIT_CONFIG_VALUE_")):
                environment.pop(name)
        environment["GIT_CONFIG_COUNT"] = str(len(settings))
        for index, (key, value) in enumerate(settings):
            environment[f"GIT_CONFIG_KEY_{index}"] = key
            environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


def environment_assignment_verdict(program: str, args: list) -> tuple:
    """Gate persistent shell assignment of variables that alter Git reads."""
    name = os.path.basename(program).lower()
    exports = name == "export"
    if name in ("declare", "typeset"):
        exports = any(
            token == "--export" or (is_short_group(token) and "x" in token)
            for token in args)
    if not exports:
        return "", ""
    for token in args:
        if token.startswith("-"):
            continue
        name = token.split("=", 1)[0]
        if is_relevant_git_environment(name):
            return "ask", (f"exporting {sanitize(name)} changes how a later "
                           "git read resolves or executes programs")
    return "", ""


def resolve_alias(cwd: str, subcommand: str) -> str:
    """Return what `subcommand` expands to, or an empty string."""
    entries = parse_git_config(cwd)
    if not entries:
        return ""
    return entries.get(f"alias.{subcommand.lower()}", "")


# Removing recovery data is the step that makes destruction irreversible,
# and it is the highest-signal indicator in the data-destruction family.
# No agent workflow deletes a shadow copy or a backup catalog.
RECOVERY_DESTRUCTION = {
    "vssadmin": ("delete",),
    "wmic": ("shadowcopy",),
    "wbadmin": ("delete",),
    "bcdedit": ("recoveryenabled", "bootstatuspolicy", "safeboot"),
}
# Programs that write over a device or lay down a filesystem.
DEVICE_WRITERS = frozenset({"mkfs", "diskpart", "format", "cipher", "fdisk",
                            "parted", "sgdisk", "wipefs", "blkdiscard",
                            "shred", "sdelete", "wipe", "dd", "hdparm",
                            "badblocks", "nvme"})
# Programs with no purpose but to partition, format, or wipe. Unlike dd or
# shred, no invocation of these operates on a single ordinary file, so an
# unparseable one has no benign reading to fall back on.
ALWAYS_DESTRUCTIVE = frozenset({"diskpart", "fdisk", "sgdisk", "parted",
                                "wipefs", "blkdiscard", "mkfs", "format",
                                "cipher", "dd", "hdparm"})
# Programs that fetch a remote resource to standard output.
DOWNLOADERS = frozenset({"curl", "wget", "fetch", "invoke-webrequest", "iwr",
                         "invoke-restmethod", "irm", "httpie", "http", "aria2c"})
# Programs that execute whatever they are handed on standard input.
INPUT_EXECUTORS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "busybox",
                             "fish", "csh", "tcsh", "python", "python3",
                             "perl", "ruby", "node", "php", "iex",
                             "invoke-expression", "pwsh", "powershell"})
DEVICE_PATH_MARKERS = ("/dev/", "\\\\.\\physicaldrive", "\\\\.\\",
                       "/dev/disk")
# Commands whose target set is decided at run time rather than written out.
LOGGING_DISABLERS = {
    "aws": ("stop-logging", "delete-trail", "delete-log-group"),
    "az": ("diagnostic-settings",),
    "gcloud": ("sinks",),
    "vim-cmd": ("destroy", "unregister"),
    "esxcli": ("destroy",),
    "auditctl": ("-D",),
    "systemctl": ("auditd", "rsyslog"),
}
# Mount points and shared temp directories DET0146 calls out by name: a
# volume mount is somebody else's data reached through this filesystem.
VOLUME_PREFIXES = ("/mnt/", "/media/", "/volumes/", "/private/tmp",
                   "/var/tmp", "/srv/", "/net/", "/mounts/")

UNBOUNDED_OPERATIONS = {
    "find": ("-delete", "-exec", "-execdir", "-ok"),
    "git": ("clean",),
    "truncate": ("-s",),
    "sed": ("-i",),
    "perl": ("-i",),
    "xargs": ("rm", "shred", "truncate"),
}
GLOB_CHARACTERS = "*?["


def _mentions_device(args: list) -> bool:
    """Return True if any operand names a raw device rather than a file."""
    for token in args:
        lowered = token.lower()
        value = lowered.partition("=")[2] if "=" in lowered else lowered
        if any(marker in value for marker in DEVICE_PATH_MARKERS):
            # /dev/zero and /dev/urandom are sources, not targets.
            if value.rstrip("0123456789").endswith(("/zero", "/urandom",
                                                    "/random", "/null")):
                continue
            return True
        if len(value) == DRIVE_ROOT_LENGTH and value[1] == ":":
            return True
        if lowered.startswith("/w:"):
            return True
    return False


def recovery_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a command that destroys recovery data."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    markers = RECOVERY_DESTRUCTION.get(name)
    if not markers:
        return "", ""
    lowered = [token.lower() for token in args]
    if not any(marker in token for marker in markers for token in lowered):
        return "", ""
    return "deny", (f"{name} removing recovery data: this is what makes a "
                    "destructive act irreversible")


def device_write_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a device wipe or a file overwrite."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    # mkfs ships as mkfs.ext4, mkfs.xfs, and so on.
    base = name.split(".", 1)[0] if name.startswith("mkfs") else name
    if base not in DEVICE_WRITERS:
        return "", ""
    name = base
    # These exist only to partition or wipe, so any invocation counts.
    if name in ALWAYS_DESTRUCTIVE and name not in ("cipher",):
        return "deny", (f"{name} partitions or lays down a filesystem, which "
                        "destroys every file on the target at once")
    if _mentions_device(args):
        return "deny", (f"{name} writing over a device or filesystem, which "
                        "destroys every file on it at once")
    if name in ("shred", "sdelete", "wipe"):
        return "ask", f"{name} overwriting file contents in place"
    return "", ""


def _is_shallow_glob(token: str) -> bool:
    """Return True for a glob whose parent is a root, such as /* or ~/*."""
    if not any(character in token for character in GLOB_CHARACTERS):
        return False
    parent = token.rstrip("*?[]/")
    return is_root_target(parent) or is_root_target(parent + "/")


def mass_operation_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a command with an unbounded target set.

    A glob rooted at a system directory denies for the same reason the
    directory itself does. Everything else asks: the gate cannot count
    what a pattern will match, and a command that decides its own targets
    at run time is one a person should see.
    """
    for token in args:
        if _is_shallow_glob(token):
            return "deny", ("an operation over every entry of a root or "
                            "system directory")
    name = os.path.basename(program).lower()
    markers = UNBOUNDED_OPERATIONS.get(name)
    if not markers:
        return "", ""
    lowered = [token.lower() for token in args]
    if any(flag in lowered for flag in ("-n", "--dry-run", "--no-act")):
        return "", ""
    if not any(marker in lowered for marker in markers):
        return "", ""
    if any(any(character in token for character in GLOB_CHARACTERS)
           for token in args) or name in ("find", "git", "xargs"):
        return "ask", (f"{name} over a target set decided at run time, which "
                       "the gate cannot count before it runs")
    return "", ""


def destruction_verdict(program: str, args: list) -> tuple:
    """Return the strongest data-destruction verdict for one command."""
    verdict = ("", "")
    for check in (recovery_verdict, device_write_verdict,
                  mass_operation_verdict, logging_verdict,
                  disguised_destruction_verdict):
        verdict = strongest(verdict, check(program, args))
    return verdict


def logging_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for disabling logging or purging a disk.

    Destroying the record of an act belongs to the same campaign as the
    act. These are read as commands rather than counted as events, which
    is all a per-call gate can do.
    """
    name = os.path.basename(program).lower().removesuffix(".exe")
    markers = LOGGING_DISABLERS.get(name)
    if not markers:
        return "", ""
    lowered = " ".join(args).lower()
    if not any(marker in lowered for marker in markers):
        return "", ""
    if name in ("vim-cmd", "esxcli"):
        return "deny", f"{name} destroying a virtual disk or registration"
    return "ask", (f"{name} disabling an audit or logging service, which "
                   "removes the record of what follows")


def volume_verdict(recursive: bool, operands: list) -> tuple:
    """Return (decision, reason) for a recursive act on a mounted volume."""
    if not recursive:
        return "", ""
    for token in operands:
        candidate = token.strip().strip('"').strip("'").replace("\\", "/")
        lowered = posixpath.normpath(candidate).lower() + "/"
        if any(lowered.startswith(prefix) for prefix in VOLUME_PREFIXES):
            return "ask", ("a recursive act under a mount point or shared "
                           "temp directory, which is not this project's data")
    return "", ""


def gated_keywords() -> tuple:
    """Return every program name this core classifies.

    Derived rather than written out. A hardcoded list is a second place to
    remember, and the one that decides whether an unparseable command
    fails closed: cipher /w:C:\\ does not tokenize, and a list that had
    not learned "cipher" waved it through.
    """
    names = {"rm", "git"}
    names.update(DEVICE_WRITERS)
    names.update(RECOVERY_DESTRUCTION)
    names.update(LOGGING_DISABLERS)
    names.update(UNBOUNDED_OPERATIONS)
    names.update(CMD_DELETE_VERBS)
    names.update(FORGE_PROGRAMS)
    names.update({"mv", "move", "chmod", "chown", "chgrp", "cat", "tee",
                  "alias", "kill", "killall", "pkill", "hdparm", "install"})
    names.update({"mkfs.ext4", "mkfs.xfs", "mkfs.btrfs", "mkfs.vfat"})
    return tuple(sorted(names))


def _segment_program(segment: list) -> str:
    """Return the real program a segment runs, past any wrapper."""
    for token in segment:
        name = os.path.basename(token).lower().removesuffix(".exe")
        if name not in ("sudo", "doas", "env", "command", "nohup", "time"):
            return name
    return ""


def remote_execution_verdict(segments: list) -> tuple:
    """Return (decision, reason) for anything piped into an interpreter.

    Whatever arrives on standard input is executed without being read, so
    the producer of that stream decides what runs. `curl | bash` hands the
    choice to a remote host; `history | sh` hands it to whatever the shell
    happens to remember. Neither is a decision anyone can give consent to
    in advance, so both are prohibited rather than asked about.
    """
    previous = ""
    for segment in segments:
        if not segment:
            continue
        program = _segment_program(segment)
        if previous and program in INPUT_EXECUTORS:
            source = ("the remote host" if previous in DOWNLOADERS
                      else f"whatever {sanitize(previous)} produces")
            return "deny", (f"a pipe into {sanitize(program)}: {source} "
                            "chooses what runs, and nothing reads it first")
        previous = program
    return "", ""


# Moving a file to a device discards it. The command reads as a move, and
# the file is gone with no delete anywhere in the line.
DISCARD_DESTINATIONS = ("/dev/null", "/dev/random", "/dev/urandom",
                        "/dev/zero", "nul", "nul:")
# chmod 000 and its symbolic equivalents leave a file nobody can open.
NO_ACCESS_MODES = frozenset({"000", "0000", "00000", "a-rwx", "ugo-rwx",
                             "ug-rwx", "a=", "ugo=", "u-rwx,g-rwx,o-rwx"})


def disguised_destruction_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for destruction wearing another name."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    operands = [token for token in args if not token.startswith("-")]
    if name in ("mv", "move") and operands:
        destination = operands[-1].strip().strip('"').strip("'").lower()
        if destination.rstrip("/") in DISCARD_DESTINATIONS:
            return "deny", (f"mv to {sanitize(destination)} discards the "
                            "file: a delete that reads as a move")
    if name == "chmod":
        for token in operands:
            if token.strip().lower() in NO_ACCESS_MODES:
                return "deny", ("chmod to a mode nobody can read, write, or "
                                "execute, which makes the file unusable "
                                "without deleting it")
    return "", ""


# Running as another user is a decision about authority, not about the
# command. It is asked for on its own terms, then the wrapped command is
# judged separately and the stronger verdict wins.
PRIVILEGE_PROGRAMS = frozenset({"sudo", "su", "doas", "pkexec", "runas",
                                "gsudo", "please"})


def privilege_verdict(tokens: list) -> tuple:
    """Return (decision, reason) when a statement escalates privilege."""
    for token in tokens:
        name = os.path.basename(token).lower().removesuffix(".exe")
        if name in PRIVILEGE_PROGRAMS:
            return "ask", (f"{name}: running as another user is the user's "
                           "call, whatever the command does")
        if not token.startswith("-"):
            break
    return "", ""


# A shell rc file runs on every future session, so a line added to one
# outlives the change that added it.
SHELL_PROFILES = ("/.bashrc", "/.bash_profile", "/.bash_login",
                  "/.bash_aliases", "/.bash_logout", "/.profile",
                  "/.zshrc", "/.zshenv", "/.zprofile", "/.zlogin",
                  "/.zlogout", "/.cshrc", "/.kshrc", "/.inputrc",
                  "/.config/fish/config.fish")
SCHEDULE_PROGRAMS = frozenset({"crontab", "schtasks", "at"})
FILESYSTEM_REPAIR = frozenset({"fsck", "e2fsck", "xfs_repair", "ntfsfix",
                               "chkdsk", "resize2fs", "tune2fs"})
PROCESS_PROGRAMS = frozenset({"kill", "killall", "pkill", "skill",
                              "taskkill", "stop-process"})
ALIAS_PROGRAMS = frozenset({"alias", "set-alias", "new-alias", "doskey"})
MODE_PROGRAMS = frozenset({"chmod", "chown", "chgrp", "icacls", "takeown"})
# Emptying a file destroys it without naming a delete.
TRUNCATION_SOURCES = ("/dev/null", "nul")


def _names_shell_profile(tokens: list) -> str:
    """Return the shell profile a token names, or an empty string."""
    for token in tokens:
        candidate = token.strip().strip('"').strip("'").replace("\\", "/")
        lowered = candidate.lower()
        if any(lowered.endswith(profile) or lowered == profile.lstrip("/")
               for profile in SHELL_PROFILES):
            return candidate
    return ""


def profile_verdict(program: str, args: list, redirects: list) -> tuple:
    """Return (decision, reason) for a write to a shell startup file."""
    name = os.path.basename(program).lower()
    writes = name in ("tee", "sed", "cp", "mv", "install", "truncate", "dd")
    named = _names_shell_profile(list(redirects) + (args if writes else []))
    if not named:
        return "", ""
    return "ask", (f"a write to {sanitize(named)}, which runs at the start of "
                   "every future shell session")


def process_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for terminating processes."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    if name not in PROCESS_PROGRAMS:
        return "", ""
    return "ask", (f"{name} terminating a process: what it stops and what "
                   "that loses is the user's call")


def alias_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for defining a command alias.

    An alias makes one name run another command, which defeats reading a
    command to know what it does. Listing aliases is not defining one.
    """
    name = os.path.basename(program).lower().removesuffix(".exe")
    if name in ALIAS_PROGRAMS:
        if not args or not any("=" in token or not token.startswith("-")
                               for token in args):
            return "", ""
        return "deny", (f"{name} defining a command alias, which makes a name "
                        "run something the name does not say")
    if name == "git" and args and args[0] == "config":
        settings = [token for token in args[1:] if not token.startswith("-")]
        if settings and settings[0].lower().startswith("alias.") and len(settings) > 1:
            return "deny", ("git config defining an alias, which makes a "
                            "subcommand run something it does not name")
    return "", ""


def truncation_verdict(program: str, args: list, redirects: list) -> tuple:
    """Return (decision, reason) for emptying a file or writing a device."""
    for target in redirects:
        cleaned = target.strip().strip('"').strip("'")
        if _mentions_device([cleaned]):
            return "deny", (f"a redirect onto {sanitize(cleaned)}, which "
                            "writes over a device rather than a file")
    if not redirects:
        return "", ""
    name = os.path.basename(program).lower() if program else ""
    if not name or name == ":":
        return "deny", ("a bare redirect, which empties the target without "
                        "naming a delete")
    if name == "cat" and any(
            token.strip().lower().rstrip("/") in TRUNCATION_SOURCES
            for token in args):
        return "deny", ("a redirect from an empty device, which empties the "
                        "target without naming a delete")
    return "", ""


def mode_change_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a recursive mode change on a root."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    if name not in MODE_PROGRAMS:
        return "", ""
    # Recursion is not what makes this dangerous. chown nobody /etc breaks
    # the machine with no -R anywhere in the line.
    for token in args:
        if token.startswith("-"):
            continue
        if is_root_target(token) or is_root_target(token.rstrip("/") + "/"):
            return "deny", (f"recursive {name} across a root or system "
                            "directory, which breaks every program that "
                            "depends on those permissions")
    return "", ""


def schedule_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for removing scheduled work."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    if name not in SCHEDULE_PROGRAMS:
        return "", ""
    lowered = [token.lower() for token in args]
    if name == "crontab" and ("-r" in lowered or "--remove" in lowered):
        return "deny", ("crontab -r removes every scheduled job at once, "
                        "with no copy kept and no prompt from crontab itself")
    if name == "schtasks" and "/delete" in lowered:
        return "deny", "schtasks deleting a scheduled task"
    return "", ""


def filesystem_repair_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a filesystem repair tool."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    if name not in FILESYSTEM_REPAIR:
        return "", ""
    return "deny", (f"{name} rewrites filesystem metadata in place and can "
                    "discard data it cannot reconcile")


# Deleting a repository, a release, or a tag on the forge destroys work
# that is not in any local clone.
FORGE_PROGRAMS = frozenset({"gh", "glab", "hub", "tea"})
FORGE_DELETE_NOUNS = frozenset({"repo", "repository", "release", "project",
                                "org", "organization", "gist", "secret",
                                "environment", "cache", "run"})


def forge_verdict(program: str, args: list) -> tuple:
    """Return (decision, reason) for a destructive forge command."""
    name = os.path.basename(program).lower().removesuffix(".exe")
    if name not in FORGE_PROGRAMS:
        return "", ""
    words = [token.lower() for token in args if not token.startswith("-")]
    if len(words) < FORGE_DELETE_MIN_WORDS or "delete" not in words[:3]:
        return "", ""
    noun = words[0]
    if noun not in FORGE_DELETE_NOUNS:
        return "", ""
    return "deny", (f"{name} {sanitize(noun)} delete removes work that no "
                    "local clone holds, and no local action undoes it")
