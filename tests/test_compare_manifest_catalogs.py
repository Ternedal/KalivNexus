"""Tests for offline capability catalog comparison."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.compare_manifest_catalogs import compare_catalogs, read_catalog


class CatalogComparisonTests(unittest.TestCase):
    def write(self, directory: str, name: str, entries: list[dict]) -> Path:
        path = Path(directory) / name
        path.write_text(json.dumps({"capabilities": entries}), encoding="utf-8")
        return path

    def test_added_removed_sorted(self):
        with TemporaryDirectory() as directory:
            before = self.write(directory, "before.json", [
                {"capability_id": "z.read", "status": "disabled"},
                {"capability_id": "a.read", "status": "disabled"}
            ])
            after = self.write(directory, "after.json", [
                {"capability_id": "b.read", "status": "disabled"},
                {"capability_id": "c.read", "status": "disabled"}
            ])
            self.assertEqual(compare_catalogs(before, after), {
                "added": ["b.read", "c.read"], "removed": ["a.read", "z.read"]
            })

    def test_no_changes(self):
        with TemporaryDirectory() as directory:
            path = self.write(directory, "same.json", [{"capability_id": "a", "status": "disabled"}])
            self.assertEqual(compare_catalogs(path, path), {"added": [], "removed": []})

    def test_rejects_duplicate_and_non_disabled_entries(self):
        with TemporaryDirectory() as directory:
            for entries in (
                [{"capability_id": "a", "status": "disabled"}] * 2,
                [{"capability_id": "a", "status": "enabled"}],
                [{"capability_id": "a", "status": "disabled", "secret_ref": "secret"}]
            ):
                path = self.write(directory, "invalid.json", entries)
                with self.assertRaises(ValueError):
                    read_catalog(path)

    def test_cli_fail_on_change_exit_code(self):
        with TemporaryDirectory() as directory:
            before = self.write(directory, "before.json", [])
            after = self.write(directory, "after.json", [
                {"capability_id": "weather.current.read", "status": "disabled"}
            ])
            command = [sys.executable, "-m", "scripts.compare_manifest_catalogs",
                       str(before), str(after)]
            default = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(default.returncode, 0, default.stderr)
            strict = subprocess.run(command + ["--fail-on-change"], capture_output=True, text=True)
            self.assertEqual(strict.returncode, 2, strict.stderr)
            self.assertEqual(json.loads(strict.stdout), {
                "added": ["weather.current.read"], "removed": []
            })
            same = subprocess.run(
                [sys.executable, "-m", "scripts.compare_manifest_catalogs",
                 str(before), str(before), "--fail-on-change"],
                capture_output=True, text=True
            )
            self.assertEqual(same.returncode, 0, same.stderr)

    def test_rejects_oversized_input(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "huge.json"
            path.write_bytes(b" " * 1_048_577)
            with self.assertRaisesRegex(ValueError, "1 MiB"):
                read_catalog(path)

    def test_rejects_symlinked_input(self):
        with TemporaryDirectory() as directory:
            target = self.write(directory, "target.json", [])
            link = Path(directory) / "link.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symbolic links unavailable")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                read_catalog(link)

    def test_rejects_malformed_shape(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"capabilities":{}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_catalog(path)


if __name__ == "__main__":
    unittest.main()
