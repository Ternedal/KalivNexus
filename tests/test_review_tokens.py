"""Contract tests for signed review token verification and execution isolation."""
import base64
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

from scripts.persistent_registry import PersistentManifestRegistry
from scripts.review_authorization import ReviewService
from scripts.review_tokens import ReviewTokenVerifier, SignedReviewService

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))
KEY = b"test-signing-key-only-not-for-production-12345"


def encode(claims, key=KEY):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    signature = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return payload + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


class SignedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = PersistentManifestRegistry(Path(self.temp.name) / "registry.sqlite3")
        self.identifier = self.registry.register(EXAMPLE)
        verifier = ReviewTokenVerifier(KEY, "issuer-1", "kalivnexus-review", clock=lambda: 1000)
        self.service = SignedReviewService(ReviewService(self.registry, "issuer-1"), verifier)
        self.claims = dict(iss="issuer-1", aud="kalivnexus-review", sub="reviewer-123",
                           roles=["nexus:reviewer"], iat=990, exp=1100)

    def test_signed_review_stays_disabled(self):
        self.service.submit_review(self.identifier, encode(self.claims), "approved", "checked")
        self.assertEqual(self.registry.get(self.identifier)["status"], "disabled")
        self.assertEqual(self.registry.review_events(self.identifier)[0]["reviewer"], "reviewer-123")
        with self.assertRaises(PermissionError):
            self.registry.execute(self.identifier)

    def test_tampered_token_rejected(self):
        token = encode(self.claims)
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, "x" + token[1:], "approved", "checked")

    def test_wrong_signing_key_rejected(self):
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, encode(self.claims, b"wrong"), "approved", "checked")

    def test_expired_token_rejected(self):
        self.claims["exp"] = 1000
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, encode(self.claims), "approved", "checked")

    def test_wrong_audience_rejected(self):
        self.claims["aud"] = "other-service"
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, encode(self.claims), "approved", "checked")

    def test_missing_role_rejected(self):
        self.claims["roles"] = []
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, encode(self.claims), "approved", "checked")

    def test_future_issued_token_rejected(self):
        self.claims["iat"] = 1100
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, encode(self.claims), "approved", "checked")

    def test_overlong_lifetime_rejected(self):
        self.claims["exp"] = 2000
        with self.assertRaises(PermissionError):
            self.service.submit_review(self.identifier, encode(self.claims), "approved", "checked")

    def test_bad_key_rejected(self):
        with self.assertRaises(ValueError):
            ReviewTokenVerifier(b"short", "issuer-1", "kalivnexus-review")


if __name__ == "__main__":
    unittest.main()
