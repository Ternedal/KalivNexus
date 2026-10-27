"""Offline-only manifest-bound adapter test harness.

Never activates registered capabilities or performs outbound requests.
"""
from collections.abc import Mapping

from scripts.read_only_adapter import ReadOnlyAdapter, ReadOnlyRequest
from scripts.validate_manifest import validate_manifest


def invoke_manifest_fixture(manifest: dict, adapter: ReadOnlyAdapter, arguments: Mapping) -> dict:
    """Validate the manifest and fixture boundaries without any provider access."""
    validate_manifest(manifest)
    if manifest["operation"] != "read":
        raise PermissionError("Only read-only fixture operations are supported")
    if manifest["enabled_by_default"] is not False:
        raise PermissionError("Capability must remain disabled")
    if adapter.capability_id != manifest["capability_id"]:
        raise PermissionError("Manifest and adapter capability mismatch")
    return adapter.invoke_for_test(
        ReadOnlyRequest(manifest["capability_id"], arguments),
        input_schema=manifest["input_schema"],
        output_schema=manifest["output_schema"],
    )
