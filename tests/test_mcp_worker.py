import pytest
from nexus.mcp_worker import exchange_isolated
from nexus.sandbox import SandboxPolicy


def test_disabled_by_default():
    with pytest.raises(PermissionError):
        exchange_isolated('https://example.com/mcp', b'{}')


def test_requires_https():
    with pytest.raises(ValueError):
        exchange_isolated('http://localhost/mcp', b'{}', enabled=True)


def test_rejects_oversized_payload():
    with pytest.raises(ValueError):
        exchange_isolated('https://example.com/mcp', b'x' * (1024 * 1024 + 1), enabled=True)


def test_rejects_invalid_timeout():
    with pytest.raises(ValueError):
        exchange_isolated('https://example.com/mcp', b'{}', enabled=True, timeout=11)


def test_child_failure_is_redacted():
    # Invalid JSON-RPC envelope is rejected inside the child without networking.
    with pytest.raises(RuntimeError, match='MCP worker failed') as exc:
        exchange_isolated('https://example.com/mcp', b'{}', enabled=True, timeout=5, sandbox_policy=SandboxPolicy(True, 'host-firewall', 'https://example.com', True))
    assert 'example.com' not in str(exc.value)
