import json
import pytest
from nexus.mcp_relay_client import MCPRelayTransport, MAX_BODY

SECRET = 'a' * 40
REQUEST = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}).encode()

class Response:
    status = 200
    def getheader(self, name):
        return {'Content-Type': 'application/json', 'Content-Length': '2'}.get(name)
    def read(self, limit):
        return b'{}'

class Connection:
    def __init__(self, host, port, timeout):
        assert (host, port, timeout) == ('mcp-relay', 8787, 5)
    def request(self, method, path, body, headers):
        assert method == 'POST' and path == '/mcp'
        assert body == REQUEST
        assert headers['Authorization'] == 'Bearer ' + SECRET
    def getresponse(self):
        return Response()
    def close(self):
        pass

def make(**kwargs):
    return MCPRelayTransport(host='mcp-relay', secret=SECRET, enabled=True, connection_factory=Connection, **kwargs)

def test_disabled_by_default():
    with pytest.raises(PermissionError):
        MCPRelayTransport(host='mcp-relay', secret=SECRET)

def test_exchange_through_relay():
    assert make().exchange(REQUEST) == (200, 'application/json', b'{}')

@pytest.mark.parametrize('host', ['localhost:8787', 'http://evil', '../evil', 'bad/path', ''])
def test_invalid_relay_host(host):
    with pytest.raises(ValueError):
        MCPRelayTransport(host=host, secret=SECRET, enabled=True)

def test_weak_secret():
    with pytest.raises(ValueError):
        MCPRelayTransport(host='mcp-relay', secret='short', enabled=True)

@pytest.mark.parametrize('payload', [b'[]', b'{}', b'not-json', b'x' * (MAX_BODY + 1)])
def test_invalid_request_rejected_before_network(payload):
    with pytest.raises(ValueError):
        make().exchange(payload)

def test_response_size_limit():
    class Oversized(Response):
        def getheader(self, name):
            return str(MAX_BODY + 1) if name == 'Content-Length' else super().getheader(name)
    class Conn(Connection):
        def getresponse(self):
            return Oversized()
    t = MCPRelayTransport(host='mcp-relay', secret=SECRET, enabled=True, connection_factory=Conn)
    with pytest.raises(ValueError):
        t.exchange(REQUEST)
