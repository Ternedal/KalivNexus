import pytest
from nexus.executor import execute_get

class Response:
    status = 200
    def getheader(self, key): return None
    def read(self, count): return b'{"ok":true}'

class FakeConnection:
    def __init__(self, hostname, ip, timeout):
        assert hostname == 'api.example.com' and ip == '8.8.8.8'
    def request(self, method, path, headers):
        assert method == 'GET' and path == '/items'
    def getresponse(self): return Response()
    def close(self): pass

def test_pinned_execution_mock_only():
    resolver = lambda *args, **kwargs: [(2, 1, 6, '', ('8.8.8.8', 443))]
    result = execute_get('https://api.example.com/items', resolver=resolver, connection_factory=FakeConnection)
    assert result['status_code'] == 200 and result['bytes'] == 11

def test_private_dns_blocked_before_connection():
    resolver = lambda *args, **kwargs: [(2, 1, 6, '', ('127.0.0.1', 443))]
    with pytest.raises(PermissionError):
        execute_get('https://api.example.com/items', resolver=resolver, connection_factory=FakeConnection)


def test_deadline_expired_during_dns():
    ticks = iter([0.0, 9.0])
    resolver = lambda *args, **kwargs: [(2, 1, 6, '', ('8.8.8.8', 443))]
    with pytest.raises(TimeoutError):
        execute_get('https://api.example.com/items', resolver=resolver, connection_factory=FakeConnection, clock=lambda: next(ticks))

def test_invalid_deadline_rejected():
    with pytest.raises(ValueError):
        execute_get('https://api.example.com/items', deadline_seconds=100)

def test_deadline_expired_during_response():
    ticks = iter([0, 0, 0, 0, 0, 9])
    resolver = lambda *args, **kwargs: [(2, 1, 6, '', ('8.8.8.8', 443))]
    with pytest.raises(TimeoutError):
        execute_get('https://api.example.com/items', resolver=resolver, connection_factory=FakeConnection, clock=lambda: next(ticks))
