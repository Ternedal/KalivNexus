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
    """Validate JSON object keys and values without coercing key types."""
    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
    visit(value)
    json.dumps(value, allow_nan=False)


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
        arguments = deepcopy(dict(request.arguments))
        # Enforce a JSON-only boundary; fixture objects cannot smuggle Python instances.
        _require_json_object(arguments)
        if input_schema is not None:
            Draft202012Validator.check_schema(input_schema)
            Draft202012Validator(input_schema).validate(arguments)
        result = self._handler(arguments)
        if not isinstance(result, Mapping):
            raise TypeError("Adapter response must be a mapping")
        response = deepcopy(dict(result))
        _require_json_object(response)
        if output_schema is not None:
            Draft202012Validator.check_schema(output_schema)
            Draft202012Validator(output_schema).validate(response)
        return response
