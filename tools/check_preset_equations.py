#!/usr/bin/env python3
"""Reject preset equations that reach beyond the butterchurn equation vocabulary.

Butterchurn compiles every equation field with new Function. Each
src/presets-extra/ chunk is therefore executable code. Converted MilkDrop
equations use a small vocabulary. It covers reads and writes of a['name'],
the helper functions butterchurn installs on window, Math members, and the
loop forms milkdrop-eel-parser emits. This checker tokenizes every compiled
field and rejects any token outside that vocabulary. An equation without a
disallowed identifier, string position, member access, or call shape cannot
reach window, Function, or a string-building gadget. The checker never
executes preset text.

Usage:
    python3 tools/check_preset_equations.py
"""

import functools
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESET_DIR = ROOT / "src" / "presets-extra"
INDEX_FILE = "index.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
INDEX_SUFFIX = ";"
CHUNK_SUFFIX = ");"
CHUNK_FILE = re.compile(r"chunk-[0-9]+\.js")
DEFAULT_CHUNK_WIDTH = 3
MAX_REPORTED = 10

TOP_FIELDS = ("init_eqs_str", "frame_eqs_str", "pixel_eqs_str")
ITEM_FIELDS = ("init_eqs_str", "frame_eqs_str", "point_eqs_str")
ITEM_GROUPS = ("shapes", "waves")

STATE_NAME = "a"
MATH_NAME = "Math"
# Helpers butterchurn assigns to window in src/vendor/butterchurn.min.js.
HELPERS = frozenset({
    "sqr", "sqrt", "log10", "sign", "rand", "randint", "bnot", "pow", "div",
    "mod", "bitor", "bitand", "sigmoid", "bor", "band", "equal", "above",
    "below", "ifcond", "memcpy",
})
# Keywords milkdrop-eel-parser emits for loop() and while() blocks.
KEYWORDS = frozenset({"var", "for", "do", "while", "function", "return"})
# Keywords that may directly precede "(" without forming a call.
GROUP_KEYWORDS = frozenset({"function", "for", "while", "return"})
MATH_MEMBERS = frozenset({
    "abs", "acos", "asin", "atan", "atan2", "ceil", "cos", "exp", "floor",
    "log", "max", "min", "pow", "round", "sign", "sin", "sqrt", "tan", "PI", "E",
})
ALLOWED_NAMES = HELPERS | KEYWORDS | {STATE_NAME, MATH_NAME}
LOOP_VARIABLE = re.compile(r"mdparser_(?:idx|count)[0-9]+")
PROPERTY_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Object.prototype members reachable through a['name'] on a plain object.
FORBIDDEN_PROPERTIES = frozenset({
    "constructor", "prototype", "__proto__", "toString", "toLocaleString",
    "valueOf", "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable",
    "__defineGetter__", "__defineSetter__", "__lookupGetter__", "__lookupSetter__",
})
ASSIGNMENT_OPERATORS = frozenset({
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", ">>>=", "**=",
})

# The state alternative reads a['name'] as one token. That shortcut keeps the
# corpus scan fast. Spaced forms such as a[ 'name' ] fall through to the
# single-token rules. The alternatives never overlap. A failed match therefore
# cannot backtrack across them. The bad alternative catches every other
# character.
TOKEN_PATTERN = re.compile(
    r"(?P<state>a\[(?:'[A-Za-z_][A-Za-z0-9_]*'|\"[A-Za-z_][A-Za-z0-9_]*\")\])"
    r"|(?P<space>\s+)"
    r"|(?P<number>[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?|\.[0-9]+(?:[eE][+-]?[0-9]+)?)"
    r"|(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"|(?P<string>'[^'\\\n]*'|\"[^\"\\\n]*\")"
    r"|(?P<punct>>>>=|===|!==|>>>|<<=|>>=|\*\*=|==|!=|<=|>=|&&|\|\||\+\+|--"
    r"|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|\*\*|[-+*/%<>=!&|^~?:;,(){}\[\].])"
    r"|(?P<bad>[\s\S])"
)
STATE_KEY_START = len("a['")
STATE_KEY_END = -len("']")
NO_TOKEN = ("", "")


def _tokenize(source: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Split equation text into (kind, text) tokens, skipping whitespace."""
    tokens = []
    for match in TOKEN_PATTERN.finditer(source):
        kind = match.lastgroup
        if kind == "space":
            continue
        if kind == "bad":
            return [], [f"character {match.group()!r} is not allowed"]
        tokens.append((kind, match.group()))
    return tokens, []


def _token(tokens: list[tuple[str, str]], index: int) -> tuple[str, str]:
    """Return the token at index, or an empty token outside the list."""
    return tokens[index] if 0 <= index < len(tokens) else NO_TOKEN


def _follows_dot(tokens: list[tuple[str, str]], index: int) -> bool:
    """Return whether the token at index is a member name after '.'."""
    return _token(tokens, index - 1) == ("punct", ".")


def _check_name(tokens: list[tuple[str, str]], index: int, _closed_function: bool) -> str:
    """Allow only the equation vocabulary and Math members after '.'."""
    text = tokens[index][1]
    if _follows_dot(tokens, index):
        return "" if text in MATH_MEMBERS else f"Math member {text!r} is not allowed"
    if text in ALLOWED_NAMES or LOOP_VARIABLE.fullmatch(text):
        return ""
    return f"identifier {text!r} is not allowed"


def _check_dot(tokens: list[tuple[str, str]], index: int, _closed_function: bool) -> str:
    """Allow '.' only as Math.<member>."""
    previous = _token(tokens, index - 1)
    if previous != ("name", MATH_NAME) or _follows_dot(tokens, index - 1):
        return "member access is allowed only on Math"
    if _token(tokens, index + 1)[0] != "name":
        return "member access must name a Math member"
    return ""


def _check_string(tokens: list[tuple[str, str]], index: int, _closed_function: bool) -> str:
    """Allow a string only as the key in a['name']."""
    in_state_access = (
        _token(tokens, index - 1) == ("punct", "[")
        and _token(tokens, index - 2) == ("name", STATE_NAME)
        and not _follows_dot(tokens, index - 2)
        and _token(tokens, index + 1) == ("punct", "]")
    )
    if not in_state_access:
        return "string literal outside a['name'] access"
    name = tokens[index][1][1:-1]
    if not PROPERTY_NAME.fullmatch(name) or name in FORBIDDEN_PROPERTIES:
        return f"property {name!r} is not allowed"
    return ""


def _check_state(tokens: list[tuple[str, str]], index: int, _closed_function: bool) -> str:
    """Apply the a['name'] rules to one combined state token."""
    if _follows_dot(tokens, index):
        return "Math member 'a' is not allowed"
    name = tokens[index][1][STATE_KEY_START:STATE_KEY_END]
    return f"property {name!r} is not allowed" if name in FORBIDDEN_PROPERTIES else ""


def _check_bracket(tokens: list[tuple[str, str]], index: int, _closed_function: bool) -> str:
    """Allow '[' only after a or after another index."""
    previous = _token(tokens, index - 1)
    if previous in (("name", STATE_NAME), ("punct", "]")) or previous[0] == "state":
        return ""
    return "indexing is allowed only on a and on a['name'] values"


def _call_target_problem(tokens: list[tuple[str, str]], index: int) -> str:
    """Allow a call only on a helper, a Math member, or a grouping keyword."""
    name = _token(tokens, index - 1)[1]
    if _follows_dot(tokens, index - 1) or name in HELPERS or name in GROUP_KEYWORDS:
        return ""
    return f"call to {name!r} is not allowed"


def _check_paren(tokens: list[tuple[str, str]], index: int, closed_function: bool) -> str:
    """Reject calls on values other than helpers, Math members, and IIFEs."""
    kind, text = _token(tokens, index - 1)
    if kind == "name":
        return _call_target_problem(tokens, index)
    if kind in ("number", "string", "state") or text == "]":
        return "call on a value is not allowed"
    if text == ")" and not closed_function:
        return "call on an expression result is not allowed"
    return ""


def _check_assignment(tokens: list[tuple[str, str]], index: int, _closed_function: bool) -> str:
    """Reject overwriting a shared helper, Math, or a Math member."""
    kind, text = _token(tokens, index - 1)
    if kind != "name":
        return ""
    if text in HELPERS or text == MATH_NAME or _follows_dot(tokens, index - 1):
        return f"assignment to {text!r} is not allowed"
    return ""


TOKEN_CHECKS = {
    "name": _check_name,
    "state": _check_state,
    "string": _check_string,
    ".": _check_dot,
    "[": _check_bracket,
    "(": _check_paren,
    **{operator: _check_assignment for operator in ASSIGNMENT_OPERATORS},
}


def _token_problem(tokens: list[tuple[str, str]], index: int, closed_function: bool) -> str:
    """Return the rule violation for one token, or an empty string."""
    kind, text = tokens[index]
    check = TOKEN_CHECKS.get(text if kind == "punct" else kind)
    return check(tokens, index, closed_function) if check else ""


def find_equation_violations(source: str) -> list[str]:
    """Return every rule violation in one equation string."""
    tokens, violations = _tokenize(source)
    open_groups = []
    closed_function = False
    for index, (kind, text) in enumerate(tokens):
        problem = _token_problem(tokens, index, closed_function)
        if problem:
            violations.append(problem)
        closed_function = False
        if kind != "punct":
            continue
        if text == "(":
            # A group opening with "function" is an IIFE that may be called.
            open_groups.append(_token(tokens, index + 1) == ("name", "function"))
        elif text == ")":
            if not open_groups:
                violations.append("unbalanced ')'")
                continue
            closed_function = open_groups.pop()
    return violations


def _field_violations(label: str, value: object, check: Callable[[str], Sequence[str]]) -> list[str]:
    """Return labeled violations for one field that holds equation text."""
    if not isinstance(value, str):
        return []
    return [f"{label}: {problem}" for problem in check(value)]


def preset_violations(preset: dict,
                      check: Callable[[str], Sequence[str]] = find_equation_violations) -> list[str]:
    """Return labeled violations for every equation field butterchurn compiles."""
    violations = []
    for field in TOP_FIELDS:
        violations.extend(_field_violations(field, preset.get(field), check))
    for group in ITEM_GROUPS:
        items = preset.get(group)
        for item_index, item in enumerate(items if isinstance(items, list) else []):
            if not isinstance(item, dict):
                continue
            for field in ITEM_FIELDS:
                label = f"{group}[{item_index}].{field}"
                violations.extend(_field_violations(label, item.get(field), check))
    return violations


def _violation_tuple(source: str) -> tuple[str, ...]:
    """Return violations as an immutable value that a cache can share."""
    return tuple(find_equation_violations(source))


def _read_wrapped_json(path: Path, prefix: str, suffix: str) -> object:
    """Return the JSON value of a file that is exactly prefix + JSON + suffix."""
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith(prefix) or not text.endswith(suffix):
        raise ValueError(f"unexpected wrapper in {path.name}")
    try:
        return json.loads(text[len(prefix):-len(suffix)])
    except json.JSONDecodeError as error:
        raise ValueError(f"{path.name} holds code outside its JSON payload") from error


def read_index(preset_dir: Path = PRESET_DIR) -> dict:
    """Return the preset index stored in index.js."""
    index = _read_wrapped_json(preset_dir / INDEX_FILE, INDEX_PREFIX, INDEX_SUFFIX)
    if not isinstance(index, dict) or not isinstance(index.get("chunks"), list):
        raise ValueError(f"{INDEX_FILE} has no chunk list")
    return index


def chunk_files(index: dict) -> list[str]:
    """Return validated chunk file names in logical chunk order."""
    files = index.get("files") or [
        f"chunk-{cid:0{DEFAULT_CHUNK_WIDTH}d}.js" for cid in range(len(index["chunks"]))
    ]
    if not isinstance(files, list) or len(files) != len(index["chunks"]):
        raise ValueError(f"{INDEX_FILE} file list does not match its chunk list")
    for filename in files:
        if not isinstance(filename, str) or not CHUNK_FILE.fullmatch(filename):
            raise ValueError(f"{INDEX_FILE} names an unexpected chunk file: {filename!r}")
    return files


def read_chunk(cid: int, filename: str, preset_dir: Path = PRESET_DIR) -> dict:
    """Return the preset mapping stored in one chunk file."""
    prefix = f"window.__bcPresetChunk({cid},"
    chunk = _read_wrapped_json(preset_dir / filename, prefix, CHUNK_SUFFIX)
    if not isinstance(chunk, dict):
        raise ValueError(f"{filename} does not hold a preset mapping")
    return chunk


def corpus_violations(preset_dir: Path = PRESET_DIR) -> list[str]:
    """Return one report line per preset equation violation in the corpus."""
    index = read_index(preset_dir)
    # Most equation strings repeat across presets. The cache checks each once.
    check = functools.lru_cache(maxsize=None)(_violation_tuple)
    offenders = []
    for cid, filename in enumerate(chunk_files(index)):
        for name, preset in read_chunk(cid, filename, preset_dir).items():
            problems = preset_violations(preset, check) if isinstance(preset, dict) else []
            offenders.extend(f"{filename}: {name!r}: {problem}" for problem in problems)
    return offenders


def main() -> int:
    """Check every shipped preset and report violations."""
    try:
        offenders = corpus_violations()
    except (OSError, ValueError) as error:
        print(f"error: cannot read the preset corpus: {error}. Repair src/presets-extra/.", file=sys.stderr)
        return 1
    for line in offenders[:MAX_REPORTED]:
        print(line)
    print(f"preset equation violations: {len(offenders)}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
