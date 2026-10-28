import json
import pytest
from nexus.mcp_relay_client import AttestedMCPRelayTransport
from nexus.relay_attestation import proof

SECRET = 'x' * 40
UPSTREAM = 'https://mcp.example.org/mcp'

class Response:
    def __init__(self, status, body):
        self.status, self.body = status, body
    def getheader(self, key):
        return 'application/json' if key == 'Content-Type' else None
    def read(self, limit):
        return self.body[:limit]

class Factory:
    def __init__(self, upstream=UPSTREAM):
        self.upstream, self.calls = upstream, []
    def __call__(self, host, port, timeout):
        outer = self
        class Conn:
            def request(self, method, path, body=None, headers=None):
                outer.calls.append(path)
                self.challenge = headers.get('X-Nexus-Challenge')
            def getresponse(self):
                if self.challenge:
                    return Response(200, json.dumps(proof(SECRET, self.challenge, outer.upstream)).encode())
                return Response(200, b'{"jsonrpc":"2.0","id":1,"result":{}}')
            def close(self): pass
        return Conn()

def transport(factory):
    return AttestedMCPRelayTransport(expected_upstream=UPSTREAM, host='relay', secret=SECRET, enabled=True, connection_factory=factory)

def test_attestation_before_every_exchange():
    f = Factory()
    t = transport(f)
    payload = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
    t.exchange(payload)
    t.exchange(payload)
    assert f.calls == ['/attest','/mcp','/attest','/mcp']

def test_mismatch_never_posts():
    f = Factory('https://wrong.example.org/mcp')
    with pytest.raises(PermissionError):
        transport(f).exchange(b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
    assert f.calls == ['/attest']

def test_write_method_never_contacts_relay():
    f = Factory()
    with pytest.raises(PermissionError):
        transport(f).exchange(b'{"jsonrpc":"2.0","id":1,"method":"tools/call"}')
    assert f.calls == []

def test_invalid_upstream_fails_before_network():
    f = Factory()
    with pytest.raises(ValueError):
        AttestedMCPRelayTransport(expected_upstream='http://localhost', host='relay', secret=SECRET, enabled=True, connection_factory=f)
    assert f.calls == []
