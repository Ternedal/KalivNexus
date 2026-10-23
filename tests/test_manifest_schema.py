"""Structural manifest tests; no network calls or provider activation."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/capability-manifest-v0.1.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((ROOT / "examples/weather-readonly.manifest.json").read_text(encoding="utf-8"))


class ManifestContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Draft202012Validator.check_schema(SCHEMA)
        cls.validator = Draft202012Validator(SCHEMA)

    def assert_rejected(self, change):
        item = copy.deepcopy(EXAMPLE)
        change(item)
        self.assertFalse(self.validator.is_valid(item), item)

    def test_example_valid(self):
        self.assertTrue(self.validator.is_valid(EXAMPLE))
        for key in ("input_schema", "output_schema"):
            Draft202012Validator.check_schema(EXAMPLE[key])

    def test_required_field(self):
        self.assert_rejected(lambda m: m.pop("capability_id"))

    def test_unknown_property(self):
        self.assert_rejected(lambda m: m.update({"unexpected": True}))

    def test_default_disabled(self):
        self.assert_rejected(lambda m: m.update({"enabled_by_default": True}))

    def test_destructive_requires_confirmation(self):
        self.assert_rejected(lambda m: m.update({"operation": "destructive"}))

    def test_write_requires_confirmation(self):
        self.assert_rejected(lambda m: m.update({"operation": "write"}))

    def test_invalid_limits(self):
        self.assert_rejected(lambda m: m["limits"].update({"max_concurrency": 0}))

    def test_redirects_blocked(self):
        self.assert_rejected(lambda m: m["network"].update({"allow_redirects": True}))

    def test_ip_host_rejected(self):
        self.assert_rejected(lambda m: m["network"].update({"allowed_https_hosts": ["127.0.0.1"]}))

    def test_http_url_rejected(self):
        self.assert_rejected(lambda m: m["network"].update({"allowed_https_hosts": ["http://example.com"]}))

    def test_unknown_auth(self):
        self.assert_rejected(lambda m: m["auth"].update({"type": "anonymous"}))

    def test_invalid_manifest_version(self):
        self.assert_rejected(lambda m: m.update({"manifest_version": "999"}))

    def test_invalid_nested_schema_rejected_at_compile_stage(self):
        item = copy.deepcopy(EXAMPLE)
        item["input_schema"] = {"type": "not-a-json-schema-type"}
        self.assertTrue(self.validator.is_valid(item))
        with self.assertRaises(Exception):
            Draft202012Validator.check_schema(item["input_schema"])


if __name__ == "__main__":
    unittest.main()
