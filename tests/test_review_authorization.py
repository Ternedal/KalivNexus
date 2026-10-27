"""Trusted-caller review boundary tests; no real identity provider involved."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.persistent_registry import PersistentManifestRegistry
from scripts.review_authorization import AuthenticatedPrincipal, ReviewService

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class ReviewAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = PersistentManifestRegistry(Path(self.tmp.name) / "review.db")
        self.identifier = self.registry.register(EXAMPLE)
        self.service = ReviewService(self.registry, trusted_issuer="trusted-idp")

    def principal(self, issuer="trusted-idp", roles=frozenset({"nexus:reviewer"})):
        return AuthenticatedPrincipal(subject="user-123", roles=roles, issuer=issuer)

    def test_authorized_review_is_audited_but_disabled(self):
        self.service.submit_review(self.identifier, self.principal(), "approved", "reviewed")
        self.assertEqual(self.registry.review_events(self.identifier)[0]["reviewer"], "user-123")
        self.assertEqual(self.registry.get(self.identifier)["status"], "disabled")
        with self.assertRaises(PermissionError):
            self.registry.execute(self.identifier)

    def test_rejects_untrusted_issuer(self):
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, self.principal(issuer="attacker"), "approved", "reason")
        self.assertEqual(self.registry.review_events(self.identifier), [])

    def test_rejects_missing_role(self):
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, self.principal(roles=frozenset()), "approved", "reason")

    def test_rejects_plain_text_identity(self):
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, "admin", "approved", "reason")

    def test_rejects_invalid_review(self):
        with self.assertRaises(ValueError):
            self.service.submit_review(self.identifier, self.principal(), "unknown", "reason")

    def test_revoked_cannot_be_reviewed(self):
        self.registry.revoke(self.identifier, "security")
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, self.principal(), "approved", "reason")


if __name__ == "__main__":
    unittest.main()
