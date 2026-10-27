"""Redacted, in-memory audit events for offline adapter fixture tests.

This is not a durable or tamper-resistant audit trail.
"""
from dataclasses import dataclass
import re
from typing import Callable

from scripts.adapter_manifest_harness import invoke_manifest_fixture
from scripts.read_only_adapter import ReadOnlyAdapter


@dataclass(frozen=True)
class FixtureAuditEvent:
    capability_id: str
    outcome: str
    correlation_id: str = ""


def invoke_with_fixture_audit(
    manifest: dict,
    adapter: ReadOnlyAdapter,
    arguments: dict,
    record: Callable[[FixtureAuditEvent], None],
    *,
    correlation_id: str = "",
) -> dict:
    """Record only capability ID and outcome, never input, output, or secrets."""
    if not isinstance(correlation_id, str) or (correlation_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", correlation_id)):
        raise ValueError("Invalid correlation ID")
    if not callable(record):
        raise TypeError("Audit recorder must be callable")
    identifier = manifest.get("capability_id") if isinstance(manifest, dict) else None
    # Never emit unvalidated, attacker-controlled manifest text to audit sinks.
    safe_id = identifier if isinstance(identifier, str) and re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+", identifier) and len(identifier) <= 120 else "<invalid>"
    try:
        result = invoke_manifest_fixture(manifest, adapter, arguments)
    except Exception:
        record(FixtureAuditEvent(capability_id=safe_id, outcome="rejected", correlation_id=correlation_id))
        raise
    record(FixtureAuditEvent(capability_id=safe_id, outcome="succeeded", correlation_id=correlation_id))
    return result
