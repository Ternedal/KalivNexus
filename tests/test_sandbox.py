import pytest
from nexus.sandbox import SandboxPolicy, validate_sandbox
from nexus.mcp_worker import exchange_isolated


def test_default_deny():
    with pytest.raises(PermissionError):
        validate_sandbox('https://api.example.com/mcp', None)


def test_attestation_required():
    with pytest.raises(PermissionError):
        validate_sandbox('https://api.example.com/mcp', SandboxPolicy(True, 'container-firewall', 'https://api.example.com'))


def test_wrong_destination():
    policy = SandboxPolicy(True, 'host-firewall', 'https://api.example.com', True)
    for url in ['https://other.example.com/mcp', 'http://api.example.com/mcp', 'https://api.example.com:8443/mcp', 'https://user@api.example.com/mcp']:
        with pytest.raises(PermissionError):
            validate_sandbox(url, policy)


def test_valid_policy():
    validate_sandbox('https://api.example.com/mcp', SandboxPolicy(True, 'container-firewall', 'https://api.example.com', True))


def test_worker_rejects_without_policy_before_spawn():
    with pytest.raises(PermissionError):
        exchange_isolated('https://api.example.com/mcp', b'{}', enabled=True)
