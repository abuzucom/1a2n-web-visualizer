import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_PATH = Path(__file__).resolve().parents[1] / "hooks" / "_gate_core.py"
SPEC = importlib.util.spec_from_file_location(
    "gate_core_unc_infrastructure_paths", CORE_PATH
)
CORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)


class UncInfrastructurePathTests(unittest.TestCase):
    def test_unc_namespaces_exclude_device_paths(self):
        """Recognizes unc namespaces but not device paths."""
        paths = (
            (r"\\server\share", True),
            (r"\\?\UNC\server\share", True),
            (r"\\.\PhysicalDrive0", False),
            (r"\\?\C:\repo", False),
            (r"C:\repo", False),
        )
        for path, expected in paths:
            with self.subTest(path=path):
                self.assertEqual(CORE._is_unc_path(path), expected)

    def test_remote_yaml_stays_unopened(self):
        """Inspects unc markers and remote yaml without opening them."""
        self.assertTrue(CORE.is_protected_infrastructure_path(
            r"\\server\share\.kube\config",
            r"K:\repo",
        ))
        with patch.object(
            CORE,
            "_infrastructure_manifest_text",
            side_effect=AssertionError("remote manifests must not be opened"),
        ):
            self.assertTrue(CORE.is_protected_infrastructure_path(
                r"\\server\share\manifest.yaml",
                r"K:\repo",
            ))

    def test_relative_path_uses_unc_root(self):
        """Resolves relative path lexically from unc repository root."""
        self.assertTrue(CORE.is_protected_infrastructure_path(
            ".kube/config",
            r"\\server\share",
        ))

    def test_ordinary_unc_path_not_infrastructure(self):
        """Does not classify an ordinary unc path as infrastructure."""
        self.assertFalse(CORE.is_protected_infrastructure_path(
            r"\\server\share\notes.txt",
            r"K:\repo",
        ))

    def test_rejects_empty_and_option_paths(self):
        """Rejects empty and option like paths."""
        for path in ("", "-Recurse"):
            with self.subTest(path=path):
                self.assertFalse(CORE.is_protected_infrastructure_path(
                    path,
                    r"K:\repo",
                ))


if __name__ == "__main__":
    unittest.main()
