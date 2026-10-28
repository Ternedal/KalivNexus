"""Fail-closed deployment attestation for MCP worker network isolation.

An attestation is configuration evidence, NOT proof of effective kernel firewall rules.
The worker is intentionally denied execution unless an external supervisor provides
an explicitly enabled, destination-bound sandbox policy.
"""
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SandboxPolicy:
    enabled: bool = False
    enforced_by: str = ''
    allowed_origin: str = ''
    egress_isolated: bool = False


def validate_sandbox(url: str, policy: SandboxPolicy | None) -> None:
    if not isinstance(policy, SandboxPolicy) or not policy.enabled:
        raise PermissionError('Sandbox policy required')
    if policy.enforced_by not in {'container-firewall', 'host-firewall'} or not policy.egress_isolated:
        raise PermissionError('External network isolation required')
    try:
        target = urlsplit(url)
        allowed = urlsplit(policy.allowed_origin)
        if (target.scheme != 'https' or allowed.scheme != 'https' or
                not target.hostname or not allowed.hostname or
                target.username or target.password or allowed.username or allowed.password or
                target.port not in (None, 443) or allowed.port not in (None, 443) or
                target.hostname.lower() != allowed.hostname.lower() or
                target.fragment or allowed.path not in ('', '/') or allowed.query or allowed.fragment):
            raise PermissionError('Destination not allowed by sandbox policy')
    except ValueError as exc:
        raise PermissionError('Invalid sandbox destination') from exc
