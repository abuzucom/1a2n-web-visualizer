#!/usr/bin/env python3
"""Hold the lodash override, the Caddy base image, and ruff to exact pins.

An open range, a mutable image tag, or an unversioned linter lets an
install or a CI run pick up a different build than the one reviewed.
"""
import json
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON = REPO_ROOT / "package.json"
PACKAGE_LOCK = REPO_ROOT / "package-lock.json"
DOCKERFILE = REPO_ROOT / "Dockerfile"
RUFF_REQUIREMENTS = REPO_ROOT / "requirements-ruff.txt"
CHECKS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "checks.yml"
BASELINE_DIR = REPO_ROOT / ".github" / "ruff-baseline"
BASELINE_CONFIGS = ("ruff.toml", "ruff.warn.toml")
# Ruff reads these names from the nearest directory of each linted file.
RUFF_CONFIG_NAMES = {"ruff.toml", ".ruff.toml", "pyproject.toml"}
CADDY_FROM_RE = re.compile(r"^FROM\s+caddy:[^\s@]+@sha256:[0-9a-f]{64}\s*$", re.MULTILINE)
RUFF_PIN_RE = re.compile(r"^ruff==\d+\.\d+\.\d+\s*\\?\s*$")
HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}")
RUFF_ACTION = "astral-sh/ruff-action"


def read_requirement_lines(text):
    """Return the requirement lines of a requirements file, without comments."""
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("--hash"):
            continue
        lines.append(line)
    return lines


def lint_steps():
    """Return the steps of the checks.yml lint job."""
    workflow = yaml.safe_load(CHECKS_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["lint"]["steps"]


class LodashOverridePinTest(unittest.TestCase):
    """The lodash override names the exact locked version."""

    def test_override_matches_the_locked_version(self):
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
        locked = lock["packages"]["node_modules/lodash"]["version"]
        self.assertEqual(package["overrides"]["lodash"], locked)


class CaddyImagePinTest(unittest.TestCase):
    """The Dockerfile pulls the Caddy base image by digest."""

    def test_from_line_names_a_sha256_digest(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertRegex(text, CADDY_FROM_RE)


class RuffRequirementPinTest(unittest.TestCase):
    """requirements-ruff.txt pins one exact ruff version with hashes."""

    def test_file_pins_only_ruff_with_hashes(self):
        text = RUFF_REQUIREMENTS.read_text(encoding="utf-8")
        requirements = read_requirement_lines(text)
        self.assertEqual(len(requirements), 1, requirements)
        self.assertRegex(requirements[0], RUFF_PIN_RE)
        self.assertGreaterEqual(len(HASH_RE.findall(text)), 1)


class LintJobRuffInstallTest(unittest.TestCase):
    """The lint job installs the pinned ruff and only reports the baseline."""

    def test_installs_ruff_with_required_hashes(self):
        runs = [step.get("run", "") for step in lint_steps()]
        installs = [run for run in runs if "requirements-ruff.txt" in run]
        self.assertEqual(len(installs), 1, runs)
        self.assertIn("--require-hashes", installs[0])

    def test_does_not_use_the_unversioned_ruff_action(self):
        uses = [step.get("uses", "") for step in lint_steps()]
        self.assertFalse(any(use.startswith(RUFF_ACTION) for use in uses), uses)

    def test_baseline_survey_never_fails_the_job(self):
        surveys = [step for step in lint_steps() if "ruff-baseline" in step.get("run", "")]
        self.assertEqual(len(surveys), 1, surveys)
        self.assertIs(surveys[0].get("continue-on-error"), True)
        self.assertIn("--exit-zero", surveys[0]["run"])


class RuffBaselineConfigTest(unittest.TestCase):
    """The survey configs exist where ruff never applies them to tools/."""

    def test_baseline_configs_exist(self):
        for name in BASELINE_CONFIGS:
            with self.subTest(name=name):
                self.assertTrue((BASELINE_DIR / name).is_file())

    def test_baseline_directory_holds_no_python(self):
        self.assertEqual(sorted(BASELINE_DIR.rglob("*.py")), [])

    def test_no_ruff_config_sits_above_tools_besides_pyproject(self):
        found = sorted(
            path.name for path in REPO_ROOT.iterdir() if path.name in RUFF_CONFIG_NAMES and path.is_file()
        )
        self.assertEqual(found, ["pyproject.toml"])
        tools_configs = sorted(path.name for path in (REPO_ROOT / "tools").iterdir() if path.name in RUFF_CONFIG_NAMES)
        self.assertEqual(tools_configs, [])


if __name__ == "__main__":
    unittest.main()
