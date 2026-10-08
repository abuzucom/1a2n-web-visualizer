import importlib.util
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch


CORE_PATH = Path(__file__).resolve().parents[1] / "hooks" / "_gate_core.py"
SPEC = importlib.util.spec_from_file_location(
    "gate_core_fsmonitor_compatibility", CORE_PATH
)
CORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)


class FsmonitorVersionCompatibilityTests(unittest.TestCase):
    def test_boolean_values_require_a_supported_git_version(self):
        for version, expected in (
            ((2, 35, 1), "ask"),
            ((2, 35, 2), ""),
        ):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                git_directory = repository / ".git"
                git_directory.mkdir()
                (git_directory / "config").write_text(
                    "[core]\n\tfsmonitor = true\n",
                    encoding="utf-8",
                )

                with patch.object(
                    CORE,
                    "_read_git_version",
                    return_value=version,
                    create=True,
                ):
                    verdict, _reason = CORE.git_read_verdict(
                        ["status"], str(repository), []
                    )

                self.assertEqual(verdict, expected)


class GitVersionReaderTests(unittest.TestCase):
    def test_parses_numeric_version_and_platform_suffix(self):
        with patch.object(
            CORE.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=0,
                stdout="git version 2.35.2.windows.1\n",
            ),
        ):
            self.assertEqual(
                CORE._read_git_version("."),
                (2, 35, 2),
            )

    def test_probe_errors_and_unrecognized_output_are_not_confirmed(self):
        for result in (
            OSError("Git is unavailable"),
            SimpleNamespace(returncode=1, stdout=""),
            SimpleNamespace(returncode=0, stdout="x" * 129),
            SimpleNamespace(returncode=0, stdout="not a Git version"),
            SimpleNamespace(returncode=0, stdout="git version 2.35"),
            SimpleNamespace(returncode=0, stdout="git version 2.x.2"),
        ):
            with self.subTest(result=result):
                if isinstance(result, BaseException):
                    patched_run = patch.object(
                        CORE.subprocess,
                        "run",
                        side_effect=result,
                    )
                else:
                    patched_run = patch.object(
                        CORE.subprocess,
                        "run",
                        return_value=result,
                    )
                with patched_run:
                    self.assertIsNone(CORE._read_git_version("."))


if __name__ == "__main__":
    unittest.main()
