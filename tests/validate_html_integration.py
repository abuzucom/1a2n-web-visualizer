#!/usr/bin/env python3
"""Exercise the HTML validator with the Java available to the CI job."""
import subprocess
import tempfile
import unittest
from pathlib import Path


VALID_HTML = "<!doctype html><html lang='en'><head><title>Test</title></head><body></body></html>"
INVALID_HTML = "<!doctype html><html lang='en'><head><title>Test</title></head><body><img></body></html>"
VALIDATOR = Path("vnu.jar").resolve()


class HtmlValidatorIntegrationTest(unittest.TestCase):
    """The validator accepts valid HTML and reports invalid HTML."""

    def test_validator_checks_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.html"
            path.write_text(VALID_HTML, encoding="utf-8")
            valid = self.run_validator(path)
            self.assertEqual(valid.returncode, 0, valid.stderr)

            path.write_text(INVALID_HTML, encoding="utf-8")
            invalid = self.run_validator(path)
            self.assertNotEqual(invalid.returncode, 0, invalid.stderr)
            self.assertIn("Error:", invalid.stderr)

    @staticmethod
    def run_validator(path: Path) -> subprocess.CompletedProcess:
        """Run the same validator command used by the HTML validation job."""
        return subprocess.run(
            ["java", "-jar", str(VALIDATOR), "--also-check-css", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )


if __name__ == "__main__":
    unittest.main()
