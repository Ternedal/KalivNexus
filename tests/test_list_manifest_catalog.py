"""Offline manifest catalog CLI contract tests."""
import json
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

    def test_missing_manifest_is_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                build_catalog([str(Path(directory) / "missing.json")])


if __name__ == "__main__":
    unittest.main()
