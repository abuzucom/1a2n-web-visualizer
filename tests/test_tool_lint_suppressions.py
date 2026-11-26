"""The Python tools carry no linter suppressions.

AGENTS.md forbids silencing a linter check. CI runs ruff over tools/, and a
noqa comment would hide the finding instead of fixing it.
"""
import re
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
SUPPRESSION_PATTERN = re.compile(r"#\s*(?:ruff:\s*)?noqa\b", re.IGNORECASE)


class ToolLintSuppressionTests(unittest.TestCase):
    """Every tools/*.py file passes ruff without a noqa comment."""

    def test_no_tool_suppresses_lint(self):
        """No tool suppresses a lint check."""
        findings = []
        for path in sorted(TOOLS_DIR.glob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if SUPPRESSION_PATTERN.search(line):
                    findings.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(findings, [], "remove the suppression and fix the finding")


if __name__ == "__main__":
    unittest.main()
