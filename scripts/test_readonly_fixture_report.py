"""Offline regression tests for the read-only fixture report."""
import json
import tempfile
import unittest
from pathlib import Path
from readonly_fixture_report import build_report, summarize_fixture


class FixtureReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def fixture(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_ha_nas_report_has_provenance_and_no_live_claim(self):
        ha = self.fixture("ha.json", {"source": "home_assistant", "records": [{"healthy": True}]})
        nas = self.fixture("nas.json", {"source": "nas", "records": [{"healthy": False}, {"healthy": True}]})
        report = build_report([ha, nas])
        self.assertFalse(report["live_verified"])
        self.assertEqual(report["execution"], "offline_fixture_only")
        self.assertEqual(report["sources"][0]["healthy_count"], 1)
        self.assertEqual(report["sources"][1]["unhealthy_count"], 1)
        self.assertTrue(all(item["provenance"] == "local_fixture" for item in report["sources"]))

    def test_rejects_unexpected_source_and_non_boolean_health(self):
        bad_source = self.fixture("bad.json", {"source": "other", "records": []})
        with self.assertRaisesRegex(ValueError, "invalid_source"):
            summarize_fixture(bad_source)
        bad_health = self.fixture("health.json", {"source": "nas", "records": [{"healthy": 1}]})
        with self.assertRaisesRegex(ValueError, "invalid_record"):
            summarize_fixture(bad_health)

    def test_rejects_duplicate_sources(self):
        first = self.fixture("a.json", {"source": "nas", "records": []})
        second = self.fixture("b.json", {"source": "nas", "records": []})
        with self.assertRaisesRegex(ValueError, "duplicate_source"):
            build_report([first, second])

    def test_rejects_oversized_fixture(self):
        path = self.root / "oversized.json"
        path.write_bytes(b"x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "fixture_too_large"):
            summarize_fixture(path)


if __name__ == "__main__":
    unittest.main()
