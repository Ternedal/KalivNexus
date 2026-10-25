import pytest
from nexus.egress_proxy import relay, make_handler, ProxyError
from nexus.egress_proxy_policy import EgressGrant, EgressDenied

URL = 'https://mcp.example.org/mcp'

class FakeTransport:
    def __init__(self, url, *, enabled):
        assert enabled and url == URL
    def _post(self, payload):
        return 200, 'application/json', b'{"ok":true}'


def test_relay_approved():
    assert relay(b'{}', target=URL, grant=EgressGrant(origin=URL), transport_factory=FakeTransport)[2] == b'{"ok":true}'


def test_relay_wrong_origin():
    with pytest.raises(EgressDenied):
        relay(b'{}', target='https://evil.example/mcp', grant=EgressGrant(origin=URL), transport_factory=FakeTransport)


def test_relay_size():
    with pytest.raises(EgressDenied):
        relay(b'123', target=URL, grant=EgressGrant(origin=URL, max_request_bytes=2), transport_factory=FakeTransport)


def test_secret_required():
    with pytest.raises(ValueError):
        make_handler(grant=EgressGrant(origin=URL), secret='weak')


def test_upstream_error():
    class Failed(FakeTransport):
        def _post(self, payload):
            return 500, 'application/json', b'error'
    with pytest.raises(ProxyError):
        relay(b'{}', target=URL, grant=EgressGrant(origin=URL), transport_factory=Failed)
