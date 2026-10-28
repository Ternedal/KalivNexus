import json
import pytest
from nexus.mcp_network import MCPNetworkTransport


def resolver(*args, **kwargs):
    return [(2, 1, 6, '', ('8.8.8.8', 443))]


class Response:
    status = 200
    def __init__(self, headers=None, body=b'{}'):
        self.headers = headers or {'Content-Type': 'application/json'}
        self.body = body
    def getheader(self, key):
        return self.headers.get(key)
    def read(self, n):
        return self.body[:n]


class Connection:
    def __init__(self, hostname, ip, timeout):
        assert hostname == 'example.com' and ip == '8.8.8.8'
        self.response = Response()
        self.sent = None
    def request(self, method, path, body, headers):
        self.sent = (method, path, body, headers)
    def getresponse(self):
        return self.response
    def close(self):
        pass


def test_disabled():
    with pytest.raises(PermissionError):
        MCPNetworkTransport('https://example.com/mcp')


def test_pinned_exchange():
    t = MCPNetworkTransport('https://example.com/mcp', enabled=True, resolver=resolver, connection_factory=Connection)
    assert t.exchange(json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize'}).encode())[0] == 200


def test_private_dns_rejected():
    t = MCPNetworkTransport('https://example.com/mcp', enabled=True, resolver=lambda *a, **k: [(2,1,6,'',('127.0.0.1',443))], connection_factory=Connection)
    with pytest.raises(PermissionError):
        t.exchange(b'{"jsonrpc":"2.0"}')


def test_invalid_request_rejected():
    t = MCPNetworkTransport('https://example.com/mcp', enabled=True, resolver=resolver, connection_factory=Connection)
    with pytest.raises(ValueError):
        t.exchange(b'not json')


def test_fragment_rejected():
    t = MCPNetworkTransport('https://example.com/mcp#frag', enabled=True, resolver=resolver, connection_factory=Connection)
    with pytest.raises(PermissionError):
        t.exchange(b'{"jsonrpc":"2.0"}')
