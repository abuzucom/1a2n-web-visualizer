#!/usr/bin/env python3
"""CI scans cover hooks/, and checker dependencies install by hash (S-16, S-17)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SHA256_HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}")
PINNED_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([0-9][0-9A-Za-z.]*)")
LOCAL_INSTALL = "python -m pip install --requirement requirements-checkers.txt"
# PyYAML 6.0.3 publishes cp314 wheels for every runner. A newer Python has
# none, and its sdist build would run an unhashed build backend.
PINNED_PYTHON = "python-version: '3.14'"
# Five installs come from the adopted template workflows. Four more come from
# this repository's checks.yml. docs/template-drift.md records the count.
CHECKER_INSTALL_COUNT = 9
SYNC_CHECK_INSTALL_COUNT = 3


def read_text(path: Path) -> str:
    """Return one repository file as text."""
    return path.read_text(encoding="utf-8")


def step_block(workflow: str, step_name: str) -> str:
    """Return the text of one named workflow step up to the next step."""
    text = read_text(WORKFLOWS / workflow)
    start = text.index(f"- name: {step_name}")
    end = text.find("\n      - ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def requirement_blocks() -> list:
    """Return each requirement in requirements-checkers.txt with its hash lines."""
    blocks = []
    for line in read_text(ROOT / "requirements-checkers.txt").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("--hash="):
            blocks[-1].append(stripped)
        else:
            blocks.append([stripped])
    return blocks


class ScanCoverageTest(unittest.TestCase):
    """The weak-hash and secrets scans include the hook sources."""

    def test_ci_scans_include_hooks(self):
        for step in ("Check for unjustified MD5/SHA-1", "Check for likely secrets"):
            with self.subTest(step=step):
                self.assertIn("hooks/*.py", step_block("agents-compliance.yml", step))

    def test_pre_commit_scans_include_hooks(self):
        text = read_text(ROOT / ".pre-commit-config.yaml")
        for hook_id in ("check-weak-hashing", "check-secrets-heuristic"):
            with self.subTest(hook_id=hook_id):
                block = text[text.index(f"id: {hook_id}"):]
                files_line = next(line for line in block.splitlines() if "files:" in line)
                pattern = re.compile(files_line.split("files:", 1)[1].strip())
                self.assertTrue(pattern.search("hooks/_gate_core.py"))
                self.assertTrue(pattern.search("scripts/sync.py"))


class HashPinTest(unittest.TestCase):
    """Every checker requirement carries an exact version and sha256 hashes."""

    def test_each_requirement_is_hash_pinned(self):
        blocks = requirement_blocks()
        self.assertTrue(blocks)
        for block in blocks:
            with self.subTest(requirement=block[0]):
                self.assertRegex(block[0].rstrip(" \\"), PINNED_REQUIREMENT)
                self.assertTrue(block[1:], "no --hash lines")
                for hash_line in block[1:]:
                    self.assertRegex(hash_line.rstrip(" \\"), SHA256_HASH)

    def test_local_installs_require_hashes(self):
        text = read_text(WORKFLOWS / "sync-check.yml")
        self.assertEqual(text.count(LOCAL_INSTALL), SYNC_CHECK_INSTALL_COUNT)
        self.assertEqual(text.count(LOCAL_INSTALL + " --require-hashes"),
                         SYNC_CHECK_INSTALL_COUNT)

    def test_install_commands_parse_as_written(self):
        """A plain YAML scalar ending in `:all:` would parse as a mapping."""
        import yaml
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            data = yaml.safe_load(read_text(workflow))
            for job in data["jobs"].values():
                for step in job.get("steps", []):
                    run = step.get("run", "")
                    if "requirements-checkers.txt" in run and "pip install" in run:
                        with self.subTest(workflow=workflow.name):
                            self.assertTrue(" ".join(run.split()).endswith("--only-binary :all:"))

    def test_checker_installs_use_wheels(self):
        """No install may build an sdist. The sdist build backend skips hash checks."""
        installs = 0
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            lines = read_text(workflow).splitlines()
            for index, line in enumerate(lines):
                if "requirements-checkers.txt" not in line or "pip install" not in "".join(
                        lines[max(index - 2, 0):index + 1]):
                    continue
                installs += 1
                command = " ".join(lines[max(index - 2, 0):index + 2])
                with self.subTest(workflow=workflow.name, line=index + 1):
                    self.assertIn("--only-binary :all:", command)
                    setup = [entry for entry in lines[:index] if "python-version:" in entry]
                    self.assertTrue(setup)
                    self.assertIn(PINNED_PYTHON, setup[-1])
        self.assertEqual(installs, CHECKER_INSTALL_COUNT)

    def test_pre_commit_pins_match(self):
        name, version = PINNED_REQUIREMENT.match(requirement_blocks()[0][0]).groups()
        pins = re.findall(re.escape(name) + r"==([0-9][0-9A-Za-z.]*)",
                          read_text(ROOT / ".pre-commit-config.yaml"))
        self.assertTrue(pins)
        self.assertEqual(set(pins), {version})


if __name__ == "__main__":
    unittest.main()
