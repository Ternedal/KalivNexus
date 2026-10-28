import json
import pytest
from nexus.credential_policy import CredentialScope
from nexus.credentials import CredentialBinding
from nexus.mcp_credentials import AuthenticatedMCPTransport, environment_secret_provider
from test_mcp_network import resolver, Response

class CapturingConnection:
    last_headers = None
    def __init__(self, hostname, ip, timeout):
        pass
    def request(self, method, path, body, headers):
        CapturingConnection.last_headers = headers
    def getresponse(self):
        return Response()
    def close(self):
        pass

def make(provider):
    return AuthenticatedMCPTransport('https://example.com/mcp', binding=CredentialBinding('example', 'NEXUS_TEST_TOKEN'), scope=CredentialScope(CredentialBinding('example', 'NEXUS_TEST_TOKEN'), 'https://example.com/mcp'), secret_provider=provider, enabled=True, resolver=resolver, connection_factory=CapturingConnection)

def test_bearer_injected_only_at_request_time():
    token = {'value': 'first'}
    t = make(lambda _: token['value'])
    payload = json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize'}).encode()
    t.exchange(payload)
    assert CapturingConnection.last_headers['Authorization'] == 'Bearer first'
    token['value'] = 'second'
    t.exchange(payload)
    assert CapturingConnection.last_headers['Authorization'] == 'Bearer second'

def test_missing_credential_fails_closed():
    t = make(lambda _: None)
    with pytest.raises(PermissionError, match='Credential unavailable'):
        t.exchange(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list'}).encode())

def test_secret_provider_error_redacted():
    def fail(_):
        raise RuntimeError('super-secret-value')
    t = make(fail)
    with pytest.raises(PermissionError, match='Credential unavailable') as e:
        t.exchange(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list'}).encode())
    assert 'super-secret-value' not in str(e.value)

def test_environment_provider(monkeypatch):
    monkeypatch.setenv('NEXUS_TEST_TOKEN', 'abc')
    assert environment_secret_provider('NEXUS_TEST_TOKEN') == 'abc'
