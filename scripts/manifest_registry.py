"""Local, default-deny manifest catalog. No network or provider execution."""
import copy
import json
from pathlib import Path
from typing import Any

from scripts.validate_manifest import validate_manifest


class ManifestRegistry:
    """In-memory catalog: registration never means activation."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def register(self, manifest: dict[str, Any]) -> str:
        validate_manifest(manifest)
        identifier = manifest["capability_id"]
        if identifier in self._entries:
            raise ValueError(f"Capability already registered: {identifier}")
        self._entries[identifier] = {
            "manifest": copy.deepcopy(manifest),
            "status": "disabled",
        }
        return identifier

    def register_file(self, path: str | Path) -> str:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return self.register(data)

    def get(self, identifier: str) -> dict[str, Any]:
        if identifier not in self._entries:
            raise KeyError(identifier)
        return copy.deepcopy(self._entries[identifier])

    def list_capabilities(self) -> list[dict[str, str]]:
        return [
            {"capability_id": identifier, "status": entry["status"]}
            for identifier, entry in sorted(self._entries.items())
        ]

    def execute(self, identifier: str, **kwargs: Any) -> None:
        """Intentionally unavailable until authorization and transport exist."""
        raise PermissionError("Execution is disabled: no authorization/runtime adapter exists")
