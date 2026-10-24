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

    def test_review_is_recorded_but_does_not_activate(self):
        identifier = self.registry.register(EXAMPLE)
        self.registry.record_review(identifier, "reviewer-1", "approved", "schema and terms reviewed")
        events = self.registry.review_events(identifier)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["decision"], "approved")
        self.assertEqual(events[0]["manifest_sha256"], self.registry.get(identifier)["manifest_sha256"])
        self.assertEqual(self.registry.get(identifier)["status"], "disabled")
        with self.assertRaises(PermissionError):
            self.registry.execute(identifier)

    def test_review_rejection_is_audited(self):
        identifier = self.registry.register(EXAMPLE)
        self.registry.record_review(identifier, "reviewer-1", "rejected", "provider not trusted")
        self.assertEqual(self.registry.review_events(identifier)[0]["decision"], "rejected")

    def test_review_rejects_missing_identity_reason_and_bad_decision(self):
        identifier = self.registry.register(EXAMPLE)
        for reviewer, decision, reason in (
            (" ", "approved", "reason"),
            ("reviewer", "unknown", "reason"),
            ("reviewer", "approved", " "),
        ):
            with self.assertRaises(ValueError):
                self.registry.record_review(identifier, reviewer, decision, reason)
        self.assertEqual(self.registry.review_events(identifier), [])

    def test_revoked_manifest_cannot_be_reviewed(self):
        identifier = self.registry.register(EXAMPLE)
        self.registry.revoke(identifier, "security concern")
        with self.assertRaises(PermissionError):
            self.registry.record_review(identifier, "reviewer", "approved", "review")
        self.assertEqual(self.registry.review_events(identifier), [])

    def test_review_survives_restart(self):
        identifier = self.registry.register(EXAMPLE)
        self.registry.record_review(identifier, "reviewer", "approved", "review")
        restored = PersistentManifestRegistry(self.path)
        self.assertEqual(len(restored.review_events(identifier)), 1)

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
