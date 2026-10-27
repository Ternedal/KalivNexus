"""Contract tests for the intentionally non-executing manifest catalog."""
import copy
import json
import unittest
from pathlib import Path

from scripts.manifest_registry import ManifestRegistry

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class ManifestRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ManifestRegistry()

    def test_register_is_disabled(self):
        identifier = self.registry.register(EXAMPLE)
        self.assertEqual(self.registry.get(identifier)["status"], "disabled")

    def test_registration_does_not_execute(self):
        identifier = self.registry.register(EXAMPLE)
        with self.assertRaises(PermissionError):
            self.registry.execute(identifier)

    def test_duplicate_rejected(self):
        self.registry.register(EXAMPLE)
        with self.assertRaises(ValueError):
            self.registry.register(EXAMPLE)

    def test_invalid_manifest_rejected(self):
        bad = copy.deepcopy(EXAMPLE)
        bad["enabled_by_default"] = True
        with self.assertRaises(Exception):
            self.registry.register(bad)
        self.assertEqual(self.registry.list_capabilities(), [])

    def test_registry_does_not_expose_internal_mutable_state(self):
        identifier = self.registry.register(EXAMPLE)
        EXAMPLE_COPY = self.registry.get(identifier)
        EXAMPLE_COPY["manifest"]["display_name"] = "tampered"
        self.assertNotEqual(self.registry.get(identifier)["manifest"]["display_name"], "tampered")

    def test_register_copies_input(self):
        item = copy.deepcopy(EXAMPLE)
        identifier = self.registry.register(item)
        item["display_name"] = "tampered"
        self.assertNotEqual(self.registry.get(identifier)["manifest"]["display_name"], "tampered")

    def test_sorted_listing(self):
        second = copy.deepcopy(EXAMPLE)
        second["capability_id"] = "alpha.current.read"
        self.registry.register(EXAMPLE)
        self.registry.register(second)
        self.assertEqual([entry["capability_id"] for entry in self.registry.list_capabilities()], ["alpha.current.read", "weather.current.read"])


if __name__ == "__main__":
    unittest.main()
