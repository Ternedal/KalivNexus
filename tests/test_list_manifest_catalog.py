"""Offline manifest catalog CLI contract tests."""
import json
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

    def test_missing_manifest_is_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                build_catalog([str(Path(directory) / "missing.json")])


if __name__ == "__main__":
    unittest.main()
