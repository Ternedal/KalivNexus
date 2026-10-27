"""Regression for Codex P2 4394805170 on #39: the relay must carry the upstream MCP session.

The relay builds a fresh upstream transport for every POST. Before the fix,
the Mcp-Session-Id the upstream assigned at initialize was dropped, never
returned to the client, and never sent on notifications/initialized or
tools/list, so discovery failed against servers that require a session.
These tests run the real relay handler on loopback with the real relay
client; only the upstream transport is a fake.
"""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from nexus.egress_proxy import make_handler, relay, relay_session
from nexus.egress_proxy_policy import EgressGrant
from nexus.mcp_relay_client import MCPRelayTransport

URL = "https://mcp.example.org/mcp"
SECRET = "relay-secret-for-tests-0123456789abcdef"
ASSIGNED = "sess-7f3a"


class SessionUpstream:
    """Stands in for MCPNetworkTransport: session_id is what would be sent upstream."""

    seen: list = []
    assign = ASSIGNED

    def __init__(self, url, *, enabled):
        assert enabled and url == URL
        self.session_id = None

    def _post(self, payload):
        method = json.loads(payload)["method"]
        SessionUpstream.seen.append((method, self.session_id))
        if method == "initialize":
            if self.session_id is None:
                self.session_id = SessionUpstream.assign  # the upstream's Mcp-Session-Id response header
            return 200, "application/json", b'{"jsonrpc":"2.0","id":1,"result":{}}'
        if self.session_id is None:
            return 400, "application/json", b'{"error":"session required"}'
        if method == "notifications/initialized":
            return 202, "application/json", b""
        return 200, "application/json", b'{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}'


@pytest.fixture
def relay_port():
    SessionUpstream.seen = []
    handler = make_handler(grant=EgressGrant(origin=URL), secret=SECRET, transport_factory=SessionUpstream)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def message(method, **extra):
    return json.dumps({"jsonrpc": "2.0", "method": method, **extra}).encode()


def test_session_survives_initialize_notify_and_tools_list(relay_port):
    client = MCPRelayTransport(host="localhost", port=relay_port, secret=SECRET, enabled=True)
    client.exchange(message("initialize", id=1, params={}))
    assert client.session_id == ASSIGNED
    client.notify(message("notifications/initialized"))
    status, _, body = client.exchange(message("tools/list", id=2))
    assert status == 200 and json.loads(body)["result"] == {"tools": []}
    assert SessionUpstream.seen == [("initialize", None), ("notifications/initialized", ASSIGNED),
                                    ("tools/list", ASSIGNED)]


def test_relay_rejects_a_malformed_client_session_header(relay_port):
    import http.client

    conn = http.client.HTTPConnection("127.0.0.1", relay_port, timeout=5)
    payload = message("tools/list", id=2)
    conn.request("POST", "/mcp", body=payload, headers={
        "Authorization": "Bearer " + SECRET, "Content-Type": "application/json",
        "Mcp-Session-Id": "bad session"})
    assert conn.getresponse().status == 400
    conn.close()
    assert SessionUpstream.seen == []


class FakeResponse:
    def __init__(self, status, headers, body=b'{"jsonrpc":"2.0","id":1,"result":{}}'):
        self.status, self._headers, self._body = status, headers, body

    def getheader(self, name, default=None):
        return self._headers.get(name, default)

    def read(self, n=-1):
        return self._body


class FakeConnection:
    sent: list = []
    replies: list = []

    def __init__(self, host, port, timeout):
        pass

    def request(self, method, path, body=None, headers=None):
        FakeConnection.sent.append(dict(headers or {}))

    def getresponse(self):
        return FakeConnection.replies.pop(0)

    def close(self):
        pass


def client_with(*replies):
    FakeConnection.sent, FakeConnection.replies = [], list(replies)
    return MCPRelayTransport(host="relay", secret=SECRET, enabled=True, connection_factory=FakeConnection)


def test_client_sends_the_session_it_was_given():
    client = client_with(FakeResponse(200, {"Content-Type": "application/json", "Mcp-Session-Id": ASSIGNED}),
                         FakeResponse(200, {"Content-Type": "application/json"}))
    client.exchange(message("initialize", id=1))
    client.exchange(message("tools/list", id=2))
    assert "Mcp-Session-Id" not in FakeConnection.sent[0]
    assert FakeConnection.sent[1]["Mcp-Session-Id"] == ASSIGNED


@pytest.mark.parametrize("bad", ["has space", "x" * 257, "tab\there"])
def test_client_rejects_a_malformed_session_from_the_relay(bad):
    client = client_with(FakeResponse(200, {"Content-Type": "application/json", "Mcp-Session-Id": bad}))
    with pytest.raises(ValueError):
        client.exchange(message("initialize", id=1))
    assert client.session_id is None


def test_client_rejects_a_session_change():
    client = client_with(FakeResponse(200, {"Content-Type": "application/json", "Mcp-Session-Id": ASSIGNED}),
                         FakeResponse(200, {"Content-Type": "application/json", "Mcp-Session-Id": "sess-other"}))
    client.exchange(message("initialize", id=1))
    with pytest.raises(ValueError):
        client.exchange(message("tools/list", id=2))
    assert client.session_id == ASSIGNED


def test_relay_session_validates_and_forwards():
    grant = EgressGrant(origin=URL)
    SessionUpstream.seen = []
    status, _, _, session = relay_session(message("initialize", id=1), target=URL, grant=grant,
                                          transport_factory=SessionUpstream)
    assert status == 200 and session == ASSIGNED
    with pytest.raises(ValueError):
        relay_session(message("tools/list", id=2), target=URL, grant=grant, session_id="bad session",
                      transport_factory=SessionUpstream)
    # The original three-value relay() keeps its signature for existing callers.
    assert len(relay(message("initialize", id=1), target=URL, grant=grant, transport_factory=SessionUpstream)) == 3
