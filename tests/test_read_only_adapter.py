"""Offline adapter contract tests: no external network or secret access."""
import unittest

from scripts.read_only_adapter import ReadOnlyAdapter, ReadOnlyRequest


class ReadOnlyAdapterTests(unittest.TestCase):
    def test_fixture_read(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "Clear in " + args["location"]})
        result = adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"location": "Copenhagen"}))
        self.assertEqual(result, {"summary": "Clear in Copenhagen"})

    def test_cross_capability_request_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "unsafe"})
        with self.assertRaises(PermissionError):
            adapter.invoke_for_test(ReadOnlyRequest("other.capability", {}))

    def test_invalid_result_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: "not an object")
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))

    def test_invalid_handler_rejected(self):
        with self.assertRaises(TypeError):
            ReadOnlyAdapter("weather.current.read", None)


if __name__ == "__main__":
    unittest.main()
