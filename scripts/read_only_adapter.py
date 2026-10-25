"""Pure read-only adapter contract. No HTTP, credentials, or activation."""
from dataclasses import dataclass
from copy import deepcopy
import json
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class ReadOnlyRequest:
    capability_id: str
    arguments: Mapping[str, Any]


def _require_json_object(value: dict[str, Any]) -> None:
    """Reject non-JSON containers, cycles and excessive nesting."""
    ancestors: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > 64:
            raise ValueError("JSON payload exceeds maximum nesting depth")
        if isinstance(item, tuple):
            raise TypeError("JSON arrays must be lists, not tuples")
        if isinstance(item, (dict, list)):
            identifier = id(item)
            if identifier in ancestors:
                raise ValueError("Circular JSON payload")
            ancestors.add(identifier)
            try:
                if isinstance(item, dict):
                    for key, child in item.items():
                        if not isinstance(key, str):
                            raise TypeError("JSON object keys must be strings")
                        visit(child, depth + 1)
                else:
                    for child in item:
                        visit(child, depth + 1)
            finally:
                ancestors.remove(identifier)

    visit(value, 0)
    serialized = json.dumps(value, allow_nan=False, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > 1_048_576:
        raise ValueError("JSON payload exceeds 1 MiB")


class ReadOnlyAdapter:
    """An injected, offline callable with an explicit capability binding."""

    def __init__(self, capability_id: str, handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]):
        if not isinstance(capability_id, str) or not capability_id.strip():
            raise ValueError("Capability ID is required")
        if not callable(handler):
            raise TypeError("Adapter handler must be callable")
        self.capability_id = capability_id
        self._handler = handler

    def invoke_for_test(self, request: ReadOnlyRequest, *, input_schema=None, output_schema=None) -> dict[str, Any]:
        """Exercise a fixture handler, never a live provider."""
        if request.capability_id != self.capability_id:
            raise PermissionError("Adapter capability mismatch")
        if not isinstance(request.arguments, Mapping):
            raise TypeError("Arguments must be a mapping")
        # Validate before copying so malformed, cyclic or oversized data fails early.
        _require_json_object(dict(request.arguments))
        arguments = deepcopy(dict(request.arguments))
        if input_schema is not None:
            Draft202012Validator.check_schema(input_schema)
            Draft202012Validator(input_schema).validate(arguments)
        result = self._handler(arguments)
        if not isinstance(result, Mapping):
            raise TypeError("Adapter response must be a mapping")
        _require_json_object(dict(result))
        response = deepcopy(dict(result))
        if output_schema is not None:
            Draft202012Validator.check_schema(output_schema)
            Draft202012Validator(output_schema).validate(response)
        return response
