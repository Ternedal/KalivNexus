"""Manifest-bound offline adapter tests."""
import copy
import json
import unittest
from pathlib import Path

from scripts.adapter_manifest_harness import invoke_manifest_fixture
from scripts.read_only_adapter import ReadOnlyAdapter

EXAMPLE = json.loads((Path(__file__).resolve().parents[1] / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class AdapterManifestHarnessTests(unittest.TestCase):
    def test_valid_read_fixture(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "Clear"})
        self.assertEqual(invoke_manifest_fixture(EXAMPLE, adapter, {"location": "Copenhagen"}), {"summary": "Clear"})

    def test_mismatched_capability_rejected(self):
        adapter = ReadOnlyAdapter("other.capability", lambda args: {"summary": "Clear"})
        with self.assertRaises(PermissionError):
            invoke_manifest_fixture(EXAMPLE, adapter, {})

    def test_write_operation_rejected(self):
        manifest = copy.deepcopy(EXAMPLE)
        manifest["operation"] = "write"
        manifest["approval"] = "explicit_user_confirmation"
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "Clear"})
        with self.assertRaises(PermissionError):
            invoke_manifest_fixture(manifest, adapter, {})

    def test_invalid_output_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": 12})
        with self.assertRaises(Exception):
            invoke_manifest_fixture(EXAMPLE, adapter, {})


if __name__ == "__main__":
    unittest.main()
