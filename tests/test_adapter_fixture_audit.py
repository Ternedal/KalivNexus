"""Ensure fixture audit does not retain arguments or response bodies."""
import copy
import json
import unittest
from pathlib import Path

from scripts.adapter_fixture_audit import FixtureAuditEvent, invoke_with_fixture_audit
from scripts.read_only_adapter import ReadOnlyAdapter

EXAMPLE = json.loads((Path(__file__).resolve().parents[1] / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class FixtureAuditTests(unittest.TestCase):
    def test_correlation_id_is_recorded_without_payload(self):
        events = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "Clear"})
        invoke_with_fixture_audit(EXAMPLE, adapter, {"location": "private"}, events.append, correlation_id="request-123")
        self.assertEqual(events, [FixtureAuditEvent("weather.current.read", "succeeded", "request-123")])

    def test_invalid_correlation_id_rejected_before_handler(self):
        events = []
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "Clear"})
        with self.assertRaises(ValueError):
            invoke_with_fixture_audit(EXAMPLE, adapter, {}, events.append, correlation_id="secret value")
        self.assertEqual(calls, [])
        self.assertEqual(events, [])

    def test_malformed_capability_id_is_redacted(self):
        events = []
        manifest = copy.deepcopy(EXAMPLE)
        manifest["capability_id"] = "private-token\\nAuthorization: secret"
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "ok"})
        with self.assertRaises(Exception):
            invoke_with_fixture_audit(manifest, adapter, {}, events.append)
        self.assertEqual(events, [FixtureAuditEvent("<invalid>", "rejected")])
        self.assertNotIn("private-token", repr(events))
        self.assertNotIn("secret", repr(events))

    def test_valid_capability_id_remains_visible_on_rejection(self):
        events = []
        adapter = ReadOnlyAdapter("other.capability", lambda args: {"summary": "ok"})
        with self.assertRaises(PermissionError):
            invoke_with_fixture_audit(EXAMPLE, adapter, {}, events.append)
        self.assertEqual(events, [FixtureAuditEvent("weather.current.read", "rejected")])

    def test_success_does_not_log_payload(self):
        events = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "private-result"})
        result = invoke_with_fixture_audit(EXAMPLE, adapter, {"location": "secret-location"}, events.append)
        self.assertEqual(result, {"summary": "private-result"})
        self.assertEqual(events, [FixtureAuditEvent("weather.current.read", "succeeded")])
        self.assertNotIn("secret-location", repr(events))
        self.assertNotIn("private-result", repr(events))

    def test_handler_failure_is_audited_without_error_details(self):
        events = []
        def failing_handler(args):
            raise RuntimeError("provider secret must not enter audit")
        adapter = ReadOnlyAdapter("weather.current.read", failing_handler)
        with self.assertRaisesRegex(RuntimeError, "provider secret"):
            invoke_with_fixture_audit(EXAMPLE, adapter, {"location": "private"}, events.append)
        self.assertEqual(events, [FixtureAuditEvent("weather.current.read", "rejected")])
        self.assertNotIn("provider secret", repr(events))

    def test_recorder_failure_is_not_silently_ignored(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "Clear"})
        def failing_recorder(event):
            raise RuntimeError("audit unavailable")
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            invoke_with_fixture_audit(EXAMPLE, adapter, {}, failing_recorder)

    def test_rejection_audited_without_payload(self):
        events = []
        manifest = copy.deepcopy(EXAMPLE)
        manifest["input_schema"]["required"] = ["location"]
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "private-result"})
        with self.assertRaises(Exception):
            invoke_with_fixture_audit(manifest, adapter, {"private": "secret-value"}, events.append)
        self.assertEqual(events, [FixtureAuditEvent("weather.current.read", "rejected")])
        self.assertNotIn("secret-value", repr(events))


if __name__ == "__main__":
    unittest.main()
