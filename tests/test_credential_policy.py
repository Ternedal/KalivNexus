import json
import pytest
from nexus.credentials import CredentialBinding
from nexus.credential_policy import CredentialScope
from nexus.mcp_credentials import AuthenticatedMCPTransport
from test_mcp_credentials import CapturingConnection
from test_mcp_network import resolver

B = CredentialBinding('service-a', 'SERVICE_A_TOKEN')
URL = 'https://example.com/mcp'

def make(scope):
    return AuthenticatedMCPTransport(URL, binding=B, scope=scope, secret_provider=lambda _: 'secret', enabled=True, resolver=resolver, connection_factory=CapturingConnection)

def payload(method):
    return json.dumps({'jsonrpc':'2.0','id':1,'method':method}).encode()

def test_scoped_discovery_allowed():
    make(CredentialScope(B, URL)).exchange(payload('tools/list'))
    assert CapturingConnection.last_headers['Authorization'] == 'Bearer secret'

def test_scoped_tool_execution_denied():
    with pytest.raises(PermissionError, match='scope denied'):
        make(CredentialScope(B, URL)).exchange(payload('tools/call'))

def test_connection_binding_mismatch_denied():
    with pytest.raises(PermissionError, match='scope denied'):
        make(CredentialScope(CredentialBinding('service-b', 'SERVICE_B_TOKEN'), URL))

def test_endpoint_mismatch_denied():
    with pytest.raises(PermissionError, match='scope denied'):
        make(CredentialScope(B, 'https://other.example/mcp'))

def test_scope_blocks_insecure_endpoint():
    with pytest.raises(ValueError):
        CredentialScope(B, 'http://example.com/mcp')

def test_scope_denies_invalid_payload():
    with pytest.raises(PermissionError, match='scope denied'):
        make(CredentialScope(B, URL)).exchange(b'not-json')


def test_scope_is_mandatory():
    with pytest.raises(PermissionError, match='scope required'):
        AuthenticatedMCPTransport(URL, binding=B, secret_provider=lambda _: 'secret', enabled=True, resolver=resolver, connection_factory=CapturingConnection)

def test_missing_scope_rejected_before_secret_lookup():
    calls = []
    with pytest.raises(PermissionError):
        AuthenticatedMCPTransport(URL, binding=B, secret_provider=lambda _: calls.append('called'), enabled=True, resolver=resolver, connection_factory=CapturingConnection)
    assert calls == []
