#!/usr/bin/env python3
"""Deny GitHub MCP pull request tools that target a base outside the stable branches.

The stable branches are the primary branch, test, and develop. Every CI
workflow filters pull requests on those branches. A pull
request into another base runs no CI. The shell gates check gh and the
trusted wrapper. This hook covers GitHub MCP tools, which bypass both.
Claude Code registers it on PreToolUse for every MCP tool. Other clients
expose no MCP tool calls to repository hooks.
"""
import sys

import _gate_core as core

GATE = "enforce_pr_base.py"
MCP_PREFIX = "mcp__"
MCP_SEPARATOR = "__"
CREATE_TOOL = "create_pull_request"
PULL_REQUEST_TOOLS = frozenset({CREATE_TOOL, "update_pull_request"})
BASE_FIELD = "base"
MALFORMED_REASON = "the tool call could not be read, so the gate cannot check the pull request base"


def _tool_action(tool_name: str) -> str:
    """Return the tool name after the MCP server prefix, or an empty string."""
    if not tool_name.startswith(MCP_PREFIX):
        return ""
    return tool_name.rsplit(MCP_SEPARATOR, 1)[-1]


def base_decision(payload: dict) -> tuple:
    """Return (decision, reason) for one PreToolUse payload."""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return "deny", MALFORMED_REASON
    action = _tool_action(tool_name)
    if action not in PULL_REQUEST_TOOLS:
        return "", ""
    repository = core.project_dir(payload)
    if BASE_FIELD not in tool_input:
        # An update without a base keeps the current base. A create without a
        # base targets the GitHub default branch, so the gate checks the
        # primary branch that the shell gates add in that case.
        if action != CREATE_TOOL:
            return "", ""
        try:
            base = core.primary_branch(repository)
        except ValueError as error:
            return "deny", f"{error}, so the gate cannot check the pull request base"
        return core.pull_request_base_verdict(["pr", "create", "--base", base], repository)
    base = tool_input[BASE_FIELD]
    if not isinstance(base, str):
        return "deny", "the pull request base is not a branch name"
    return core.pull_request_base_verdict(["pr", "create", "--base", base], repository)


def main() -> int:
    """Read one PreToolUse payload and emit a deny or nothing."""
    try:
        payload = core.read_payload()
        if payload is None:
            return core.emit(GATE, "deny", MALFORMED_REASON)
        decision, reason = base_decision(payload)
        if decision:
            return core.emit(GATE, decision, reason)
        return 0
    except Exception:
        # Claude Code treats a non-2 exit as a non-blocking error, so an
        # unhandled exception would let the call through. Deny with a fixed reason.
        return core.emit(GATE, "deny", "the gate raised an unexpected error, so it "
                                       "cannot clear this call")


if __name__ == "__main__":
    sys.exit(main())
