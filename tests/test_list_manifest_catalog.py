"""Offline manifest catalog CLI contract tests."""
import json
import os
import stat
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.list_manifest_catalog import build_catalog


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "weather-readonly.manifest.json"


class ManifestCatalogCliTests(unittest.TestCase):
    def test_valid_manifest_is_listed_disabled(self):
        self.assertEqual(build_catalog([str(EXAMPLE)]), [
            {"capability_id": "weather.current.read", "status": "disabled"}
        ])

    def test_duplicate_manifest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "already registered"):
            build_catalog([str(EXAMPLE), str(EXAMPLE)])

    def test_invalid_manifest_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"capability_id": "bad"}), encoding="utf-8")
            with self.assertRaises(Exception):
                build_catalog([str(path)])

    def test_directory_discovers_only_manifest_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(EXAMPLE, root / "weather.manifest.json")
            (root / "ignore.json").write_text("not json", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "invalid.manifest.json").write_text("not json", encoding="utf-8")
            self.assertEqual(build_catalog([directory]), [
                {"capability_id": "weather.current.read", "status": "disabled"}
            ])

    def test_empty_directory_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "no \\*\\.manifest\\.json"):
                build_catalog([directory])

    def test_directory_and_explicit_duplicate_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "weather.manifest.json"
            shutil.copyfile(EXAMPLE, path)
            with self.assertRaisesRegex(ValueError, "already registered"):
                build_catalog([directory, str(path)])

    def test_cli_exports_redacted_catalog_without_overwriting(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "catalog.json"
            command = [sys.executable, "-m", "scripts.list_manifest_catalog", str(EXAMPLE), "--output", str(target)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {
                "capabilities": [{"capability_id": "weather.current.read", "status": "disabled"}]
            })
            self.assertNotIn("secret_ref", target.read_text(encoding="utf-8"))
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("Cannot write catalog", second.stderr)

    def test_prefix_filter_matches_and_non_matches(self):
        self.assertEqual(build_catalog([str(EXAMPLE)], prefix="weather."), [
            {"capability_id": "weather.current.read", "status": "disabled"}
        ])
        self.assertEqual(build_catalog([str(EXAMPLE)], prefix="calendar."), [])

    def test_filter_does_not_skip_validation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.manifest.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(Exception):
                build_catalog([str(path)], prefix="weather.")

    def test_cli_prefix_filter(self):
        result = subprocess.run(
            [sys.executable, "-m", "scripts.list_manifest_catalog", str(EXAMPLE), "--prefix", "calendar."],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"capabilities": []})

    def test_symlinked_manifest_file_rejected(self):
        with TemporaryDirectory() as directory:
            link = Path(directory) / "linked.manifest.json"
            try:
                link.symlink_to(EXAMPLE)
            except (OSError, NotImplementedError):
                self.skipTest("Symbolic links unavailable")
            with self.assertRaisesRegex(ValueError, "symbolic links"):
                build_catalog([str(link)])
            with self.assertRaisesRegex(ValueError, "symbolic links"):
                build_catalog([directory])

    def test_symlinked_directory_rejected(self):
        with TemporaryDirectory() as directory:
            link = Path(directory) / "linked-dir"
            try:
                link.symlink_to(EXAMPLE.parent, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symbolic links unavailable")
            with self.assertRaisesRegex(ValueError, "symbolic links"):
                build_catalog([str(link)])

    @unittest.skipUnless(os.name == "posix", "POSIX permission bits only")
    def test_cli_export_is_private_on_posix(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "catalog.json"
            result = subprocess.run(
                [sys.executable, "-m", "scripts.list_manifest_catalog", str(EXAMPLE), "--output", str(target)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_cli_invalid_utf8_is_reported_without_traceback(self):
        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.manifest.json"
            invalid.write_bytes(b"\\xff\\xfe")
            result = subprocess.run(
                [sys.executable, "-m", "scripts.list_manifest_catalog", str(invalid)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Invalid manifest catalog: UnicodeDecodeError", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_missing_manifest_is_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                build_catalog([str(Path(directory) / "missing.json")])


if __name__ == "__main__":
    unittest.main()
