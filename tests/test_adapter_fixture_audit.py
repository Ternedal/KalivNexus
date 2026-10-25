"""Ensure fixture audit does not retain arguments or response bodies."""
import copy
import json
import unittest
from pathlib import Path

from scripts.adapter_fixture_audit import FixtureAuditEvent, invoke_with_fixture_audit
from scripts.read_only_adapter import ReadOnlyAdapter

EXAMPLE = json.loads((Path(__file__).resolve().parents[1] / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class FixtureAuditTests(unittest.TestCase):
    def test_success_does_not_log_payload(self):
        events = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "private-result"})
        result = invoke_with_fixture_audit(EXAMPLE, adapter, {"location": "secret-location"}, events.append)
        self.assertEqual(result, {"summary": "private-result"})
        self.assertEqual(events, [FixtureAuditEvent("weather.current.read", "succeeded")])
        self.assertNotIn("secret-location", repr(events))
        self.assertNotIn("private-result", repr(events))

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
