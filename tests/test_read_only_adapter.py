"""Offline adapter contract tests: no external network or secret access."""
import unittest
from jsonschema import ValidationError

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

    def test_input_schema_rejects_invalid_arguments(self):
        called = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: called.append(args) or {"summary": "ok"})
        with self.assertRaises(ValidationError):
            adapter.invoke_for_test(
                ReadOnlyRequest("weather.current.read", {"location": 42}),
                input_schema={"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]},
            )
        self.assertEqual(called, [])

    def test_output_schema_rejects_invalid_response(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": 42})
        with self.assertRaises(ValidationError):
            adapter.invoke_for_test(
                ReadOnlyRequest("weather.current.read", {}),
                output_schema={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
            )

    def test_nested_input_is_not_mutated_by_handler(self):
        original = {"context": {"tags": ["private"]}}
        def mutate(args):
            args["context"]["tags"].append("modified")
            return {"summary": "ok"}
        adapter = ReadOnlyAdapter("weather.current.read", mutate)
        adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", original))
        self.assertEqual(original, {"context": {"tags": ["private"]}})

    def test_nested_output_is_detached_from_handler_state(self):
        state = {"data": {"tags": ["initial"]}}
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: state)
        response = adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))
        state["data"]["tags"].append("later")
        self.assertEqual(response, {"data": {"tags": ["initial"]}})

    def test_non_json_input_is_rejected_before_handler(self):
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"unsafe": object()}))
        self.assertEqual(calls, [])

    def test_non_json_output_is_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"unsafe": object()})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))

    def test_nan_input_is_rejected_before_handler(self):
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaises(ValueError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"value": float("nan")}))
        self.assertEqual(calls, [])

    def test_non_string_nested_input_key_is_rejected(self):
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"nested": {1: "unsafe"}}))
        self.assertEqual(calls, [])

    def test_non_string_nested_output_key_is_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"nested": {1: "unsafe"}})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))

    def test_invalid_handler_rejected(self):
        with self.assertRaises(TypeError):
            ReadOnlyAdapter("weather.current.read", None)


if __name__ == "__main__":
    unittest.main()
