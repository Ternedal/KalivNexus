"""SQLite registry persistence, revocation and audit contract tests."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.persistent_registry import PersistentManifestRegistry

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class PersistentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "registry.sqlite3"
        self.registry = PersistentManifestRegistry(self.path)

    def test_persists_disabled_across_restart(self):
        identifier = self.registry.register(EXAMPLE)
        restored = PersistentManifestRegistry(self.path)
        self.assertEqual(restored.get(identifier)["status"], "disabled")
        self.assertEqual(len(restored.audit_events(identifier)), 1)

    def test_revocation_persists_with_reason(self):
        identifier = self.registry.register(EXAMPLE)
        self.registry.revoke(identifier, "provider terms changed")
        restored = PersistentManifestRegistry(self.path)
        self.assertEqual(restored.get(identifier)["status"], "revoked")
        self.assertEqual([e["action"] for e in restored.audit_events(identifier)], ["registered", "revoked"])
        self.assertEqual(restored.audit_events(identifier)[1]["reason"], "provider terms changed")

    def test_duplicate_registration_rejected_without_extra_audit(self):
        identifier = self.registry.register(EXAMPLE)
        with self.assertRaises(sqlite3.IntegrityError):
            self.registry.register(EXAMPLE)
        self.assertEqual(len(self.registry.audit_events(identifier)), 1)

    def test_invalid_manifest_not_stored(self):
        invalid = copy.deepcopy(EXAMPLE)
        invalid["enabled_by_default"] = True
        with self.assertRaises(Exception):
            self.registry.register(invalid)
        self.assertEqual(self.registry.list_capabilities(), [])

    def test_revocation_requires_reason(self):
        identifier = self.registry.register(EXAMPLE)
        with self.assertRaises(ValueError):
            self.registry.revoke(identifier, " ")
        self.assertEqual(self.registry.get(identifier)["status"], "disabled")

    def test_unknown_and_double_revocation(self):
        with self.assertRaises(KeyError):
            self.registry.revoke("missing", "reason")
        identifier = self.registry.register(EXAMPLE)
        self.registry.revoke(identifier, "reason")
        with self.assertRaises(ValueError):
            self.registry.revoke(identifier, "again")

    def test_execution_never_allowed(self):
        identifier = self.registry.register(EXAMPLE)
        with self.assertRaises(PermissionError):
            self.registry.execute(identifier)
        self.registry.revoke(identifier, "test")
        with self.assertRaises(PermissionError):
            self.registry.execute(identifier)

    def test_input_is_serialized_not_referenced(self):
        item = copy.deepcopy(EXAMPLE)
        identifier = self.registry.register(item)
        item["display_name"] = "tampered"
        self.assertNotEqual(self.registry.get(identifier)["manifest"]["display_name"], "tampered")


if __name__ == "__main__":
    unittest.main()
