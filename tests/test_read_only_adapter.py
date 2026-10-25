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

    def test_nested_tuple_input_rejected_before_handler(self):
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"nested": {"items": (1, 2)}}))
        self.assertEqual(calls, [])

    def test_nested_tuple_output_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"nested": {"items": (1, 2)}})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))

    def test_json_list_remains_valid(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"items": [1, 2]})
        self.assertEqual(adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"items": [1, 2]})), {"items": [1, 2]})

    def test_cyclic_input_rejected_before_handler(self):
        calls = []
        cyclic = {}
        cyclic["self"] = cyclic
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaisesRegex(ValueError, "Circular"):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", cyclic))
        self.assertEqual(calls, [])

    def test_cyclic_output_rejected(self):
        cyclic = {}
        cyclic["self"] = cyclic
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: cyclic)
        with self.assertRaisesRegex(ValueError, "Circular"):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))

    def test_excessively_nested_input_rejected_before_handler(self):
        calls = []
        nested = {}
        for _ in range(70):
            nested = {"child": nested}
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaisesRegex(ValueError, "nesting depth"):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", nested))
        self.assertEqual(calls, [])

    def test_oversized_input_rejected_before_handler(self):
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"data": "x" * 1_048_576}))
        self.assertEqual(calls, [])

    def test_oversized_output_rejected(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"data": "x" * 1_048_576})
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))

    def test_utf8_byte_size_not_character_count(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "ok"})
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"data": "ø" * 600_000}))

    def test_invalid_input_rejected_before_deepcopy(self):
        from unittest.mock import patch
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"summary": "ok"})
        with patch("scripts.read_only_adapter.deepcopy", side_effect=AssertionError("deepcopy called")):
            with self.assertRaises(ValueError):
                adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"data": "x" * 1_048_576}))

    def test_invalid_output_rejected_before_deepcopy(self):
        from unittest.mock import patch
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"data": "x" * 1_048_576})
        from copy import deepcopy as original_deepcopy
        with patch("scripts.read_only_adapter.deepcopy", wraps=original_deepcopy) as copier:
            with self.assertRaises(ValueError):
                adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {}))
            self.assertEqual(copier.call_count, 1)  # Valid input only; output never copied

    def test_custom_json_encoder_hook_is_not_invoked_for_input(self):
        class Dangerous:
            def __repr__(self):
                raise AssertionError("unexpected object representation")
        calls = []
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: calls.append(args) or {"summary": "ok"})
        with self.assertRaises(TypeError):
            adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"nested": [Dangerous()]}))
        self.assertEqual(calls, [])

    def test_valid_json_scalars(self):
        adapter = ReadOnlyAdapter("weather.current.read", lambda args: {"items": [None, True, 1, 1.5, "text"]})
        result = adapter.invoke_for_test(ReadOnlyRequest("weather.current.read", {"items": [None, False, 0, 1.5, "text"]}))
        self.assertEqual(result, {"items": [None, True, 1, 1.5, "text"]})

    def test_invalid_handler_rejected(self):
        with self.assertRaises(TypeError):
            ReadOnlyAdapter("weather.current.read", None)


if __name__ == "__main__":
    unittest.main()
