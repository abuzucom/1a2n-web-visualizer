#!/usr/bin/env python3
"""Parse CMD command boundaries without executing command text."""
from dataclasses import dataclass


MAX_COMMAND_CHARACTERS = 65536
COMMAND_SEPARATORS = frozenset({"&", "|", "(", ")", "\n", "\r"})
OUTPUT_REDIRECT = ">"


@dataclass(frozen=True)
class CmdParseResult:
    """Store one exclusive parser state and its complete command segments."""

    status: str
    segments: tuple[tuple[str, ...], ...] = ()


def contains_dynamic_expansion(command_text: str) -> bool:
    """Return whether CMD expansion can change command structure."""
    escaped = False
    inside_quotes = False
    percent_open = False
    exclamation_open = False
    for current_character in command_text:
        if escaped:
            escaped = False
            continue
        if current_character == '"':
            inside_quotes = not inside_quotes
            continue
        if current_character == "^" and not inside_quotes:
            escaped = True
            continue
        if current_character == "%":
            if percent_open:
                return True
            percent_open = True
            continue
        if current_character == "!":
            if exclamation_open:
                return True
            exclamation_open = True
    return percent_open or exclamation_open


def append_token(
    token_characters: list[str],
    command_tokens: list[str],
) -> None:
    """Append one completed token and clear its character buffer."""
    if not token_characters:
        return
    command_tokens.append("".join(token_characters))
    token_characters.clear()


def append_segment(
    command_tokens: list[str],
    command_segments: list[tuple[str, ...]],
) -> None:
    """Append one nonempty command segment and clear its token buffer."""
    if not command_tokens:
        return
    command_segments.append(tuple(command_tokens))
    command_tokens.clear()


def split_output_redirects(
    command_tokens: tuple[str, ...],
) -> tuple[tuple[str, ...], list[str], bool]:
    """Return executable tokens, redirect targets, and syntax completeness."""
    executable_tokens: list[str] = []
    redirect_targets: list[str] = []
    token_index = 0
    while token_index < len(command_tokens):
        token = command_tokens[token_index]
        if token != OUTPUT_REDIRECT:
            executable_tokens.append(token)
            token_index += 1
            continue
        if executable_tokens and executable_tokens[-1].isdigit():
            executable_tokens.pop()
        token_index += 1
        while (token_index < len(command_tokens)
               and command_tokens[token_index] == OUTPUT_REDIRECT):
            token_index += 1
        if token_index >= len(command_tokens):
            return tuple(executable_tokens), redirect_targets, False
        target = command_tokens[token_index]
        if not target.startswith("&"):
            redirect_targets.append(target)
        token_index += 1
    return tuple(executable_tokens), redirect_targets, True


def parse_cmd_command(command_text: str) -> CmdParseResult:
    """Return bounded CMD segments or one fail-closed parser state."""
    if not isinstance(command_text, str):
        return CmdParseResult("malformed")
    if len(command_text) > MAX_COMMAND_CHARACTERS:
        return CmdParseResult("input_too_large")
    if not command_text.strip():
        return CmdParseResult("empty")
    if contains_dynamic_expansion(command_text):
        return CmdParseResult("dynamic")
    return scan_cmd_characters(command_text)


class _CmdScanner:
    """Carry CMD quoting, escaping, and token state across characters."""

    def __init__(self) -> None:
        self.command_segments: list[tuple[str, ...]] = []
        self.command_tokens: list[str] = []
        self.token_characters: list[str] = []
        self.inside_quotes = False
        self.escaped = False
        self.previous_character = ""

    def feed(self, current_character: str) -> None:
        """Consume one character of command text."""
        handled = (self._consume_escape_or_quote(current_character)
                   or self._consume_structural(current_character))
        if not handled:
            self.token_characters.append(current_character)
        self.previous_character = current_character

    def _consume_escape_or_quote(self, current_character: str) -> bool:
        """Handle an escaped character, a quote toggle, or a caret escape."""
        if self.escaped:
            if current_character == OUTPUT_REDIRECT:
                self.token_characters.append("^")
            self.token_characters.append(current_character)
            self.escaped = False
            return True
        if current_character == '"':
            self.inside_quotes = not self.inside_quotes
            return True
        if current_character == "^" and not self.inside_quotes:
            self.escaped = True
            return True
        return False

    def _consume_structural(self, current_character: str) -> bool:
        """Handle unquoted redirects, separators, and whitespace."""
        if self.inside_quotes:
            return False
        if current_character == OUTPUT_REDIRECT:
            append_token(self.token_characters, self.command_tokens)
            self.command_tokens.append(OUTPUT_REDIRECT)
            return True
        if current_character == "&" and self.previous_character == OUTPUT_REDIRECT:
            self.token_characters.append(current_character)
            return True
        if current_character in COMMAND_SEPARATORS:
            append_token(self.token_characters, self.command_tokens)
            append_segment(self.command_tokens, self.command_segments)
            return True
        if current_character.isspace():
            append_token(self.token_characters, self.command_tokens)
            return True
        return False

    def result(self) -> CmdParseResult:
        """Close the final token and segment and return the parse state."""
        if self.escaped or self.inside_quotes:
            return CmdParseResult("malformed")
        append_token(self.token_characters, self.command_tokens)
        append_segment(self.command_tokens, self.command_segments)
        if not self.command_segments:
            return CmdParseResult("empty")
        return CmdParseResult("complete", tuple(self.command_segments))


def scan_cmd_characters(command_text: str) -> CmdParseResult:
    """Scan CMD quoting, escaping, tokens, and command separators once."""
    scanner = _CmdScanner()
    for current_character in command_text:
        scanner.feed(current_character)
    return scanner.result()
